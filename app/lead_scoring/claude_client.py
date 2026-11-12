"""Claude client — sync single-lead + async batch (Message Batches API) paths.

Both paths share the same tool-use schema and retry policy.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Iterable
from uuid import uuid4

import anthropic
from anthropic import APIError, APIStatusError

from app.lead_scoring.config import ScoringConfig, load_scoring_config
from app.lead_scoring.models import (
    LeadInput,
    SCORING_TOOL,
    SYSTEM_PROMPT,
    CommandEnvelope,
    user_message_for,
)
from app.lead_scoring.tiering import (
    classify_function_bucket,
    compute_blended_score,
    compute_reachability_score,
    tier_for,
)
from app.lead_scoring.prefilter import rule_prefilter
from app.lead_scoring.models import ScoringResult, Tier

logger = logging.getLogger(__name__)


class ScoringError(RuntimeError):
    """Raised when the LLM call or its parsing fails irrecoverably."""


# ---- Internal helpers ------------------------------------------------------
def _extract_tool_input(response) -> dict:
    """Pull the score_lead tool input dict out of a Messages response."""
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "score_lead":
            return dict(block.input)
    raise ScoringError("No score_lead tool_use block in Claude response")


def _enforce_payload(payload: dict, lead_id) -> dict:
    """Coerce/clip the LLM payload into clean ints."""
    try:
        return {
            "authority_score": int(payload.get("authority_score", 0)),
            "authority_reasoning": str(payload.get("authority_reasoning", "")),
            "fit_score": int(payload.get("fit_score", 0)),
            "industry_match": payload.get("industry_match") or None,
            "intent_score": int(payload.get("intent_score", 0)),
            "intent_signals": list(payload.get("intent_signals") or []),
            "is_competitor": bool(payload.get("is_competitor", False)),
            "competitor_reason": payload.get("competitor_reason"),
            "technical_founder": bool(payload.get("technical_founder", False)),
            "company_stage": payload.get("company_stage", "Unknown"),
            "notes": str(payload.get("notes", "")),
            "company_size": payload.get("company_size") or None,
            "buying_needs": list(payload.get("buying_needs") or []),
        }
    except (TypeError, ValueError) as e:
        raise ScoringError(f"Malformed payload for lead {lead_id}: {e}") from e


def _assemble_result(
    lead: LeadInput,
    pre,
    payload: dict,
    cfg: ScoringConfig,
) -> ScoringResult:
    """Combine LLM payload + deterministic reachability + function multiplier + tiering."""
    clipped = {
        **payload,
        "authority_score": max(0, min(100, payload["authority_score"])),
        "fit_score": max(0, min(100, payload["fit_score"])),
        "intent_score": max(0, min(100, payload["intent_score"])),
    }

    # Apply authority function multiplier on top of the LLM base score.
    bucket, multiplier = classify_function_bucket(lead)
    authority_after = int(round(clipped["authority_score"] * multiplier))
    authority_after = max(0, min(100, authority_after))

    reachability = compute_reachability_score(lead)
    blended = compute_blended_score(
        authority_after, clipped["fit_score"], clipped["intent_score"], reachability, cfg
    )

    tier, disqualify_reason = tier_for(blended, clipped["fit_score"], pre, cfg)

    # Competitor override forces Cold regardless of blended score.
    is_competitor = clipped["is_competitor"] or pre.disqualified and "competitor" in (pre.reason or "")
    if is_competitor and tier != Tier.COLD:
        tier = Tier.COLD
        disqualify_reason = disqualify_reason or "competitor flagged by LLM"

    return ScoringResult(
        lead_id=lead.lead_id,
        authority_score=authority_after,
        fit_score=clipped["fit_score"],
        intent_score=clipped["intent_score"],
        reachability_score=reachability,
        blended_score=blended,
        tier=tier,
        is_competitor=is_competitor,
        disqualify_reason=disqualify_reason,
        technical_founder=clipped["technical_founder"],
        company_stage=clipped["company_stage"],
        industry_match=clipped["industry_match"],
        notes=clipped["notes"],
        scoring_model=cfg.model.name,
        scoring_config_version=cfg.version,
        authority_reasoning=clipped["authority_reasoning"],
        intent_signals=clipped["intent_signals"],
        competitor_reason=clipped["competitor_reason"],
        function_bucket=bucket,
        company_size=clipped.get("company_size"),
        buying_needs=clipped.get("buying_needs", []),
    )


# ---- Sync single-lead path -------------------------------------------------
def score_lead_sync(lead: LeadInput, cfg: ScoringConfig | None = None) -> ScoringResult:
    """Score a single lead synchronously. Use for webhook / on-demand / API."""
    cfg = cfg or load_scoring_config()
    pre = rule_prefilter(lead)
    if pre.disqualified and pre.skip_llm:
        # Job-seeker path: no LLM call, but produce a result row for traceability.
        return ScoringResult(
            lead_id=lead.lead_id,
            authority_score=0,
            fit_score=0,
            intent_score=0,
            reachability_score=compute_reachability_score(lead),
            blended_score=0.0,
            tier=Tier.COLD,
            is_competitor=False,
            disqualify_reason=pre.reason,
            scoring_model=cfg.model.name,
            scoring_config_version=cfg.version,
            notes=pre.reason or "Disqualified before LLM scoring",
        )

    client = anthropic.Anthropic()
    payload = _call_with_retry(
        client=client,
        model=cfg.model.name,
        max_tokens=cfg.model.max_tokens,
        temperature=cfg.model.temperature,
        system=SYSTEM_PROMPT,
        user=user_message_for(lead),
        cfg=cfg,
    )
    return _assemble_result(lead, pre, payload, cfg)


# ---- Async batch path ------------------------------------------------------
async def score_leads_batch(
    leads: Iterable[LeadInput],
    cfg: ScoringConfig | None = None,
) -> list[ScoringResult]:
    """Score many leads via the Message Batches API (50% cheaper, async).

    Submits a batch, polls until done, then maps results back to leads.
    """
    cfg = cfg or load_scoring_config()
    leads_list = list(leads)

    # Local prefilter: keep only leads that need LLM work
    prefilters = {lead.lead_id: rule_prefilter(lead) for lead in leads_list}
    llm_leads = [
        lead for lead in leads_list
        if not (prefilters[lead.lead_id].disqualified and prefilters[lead.lead_id].skip_llm)
    ]

    results: dict = {lead.lead_id: None for lead in leads_list}

    # Pre-compute short-circuit results for skip_llm leads
    for lead in leads_list:
        pre = prefilters[lead.lead_id]
        if pre.disqualified and pre.skip_llm:
            results[lead.lead_id] = ScoringResult(
                lead_id=lead.lead_id,
                authority_score=0,
                fit_score=0,
                intent_score=0,
                reachability_score=compute_reachability_score(lead),
                blended_score=0.0,
                tier=Tier.COLD,
                is_competitor=False,
                disqualify_reason=pre.reason,
                scoring_model=cfg.model.name,
                scoring_config_version=cfg.version,
                notes=pre.reason or "Disqualified before LLM scoring",
            )

    if not llm_leads:
        return [results[l.lead_id] for l in leads_list]

    client = anthropic.AsyncAnthropic()

    # Submit batch
    requests_payload = [
        {
            "custom_id": str(lead.lead_id),
            "params": {
                "model": cfg.model.name,
                "max_tokens": cfg.model.max_tokens,
                "temperature": cfg.model.temperature,
                "system": SYSTEM_PROMPT,
                "tools": [SCORING_TOOL],
                "tool_choice": {"type": "tool", "name": "score_lead"},
                "messages": [{"role": "user", "content": user_message_for(lead)}],
            },
        }
        for lead in llm_leads
    ]

    batch = await client.messages.batches.create(requests=requests_payload)
    logger.info("Submitted batch %s with %d requests", batch.id, len(requests_payload))

    # Poll until terminal state
    poll_interval = 5.0
    deadline = time.time() + 60 * 30  # 30 min ceiling
    while batch.processing_status in ("in_progress", "validating", "finalizing"):
        if time.time() > deadline:
            raise ScoringError(f"Batch {batch.id} did not complete within 30 min")
        await asyncio.sleep(poll_interval)
        batch = await client.messages.batches.retrieve(batch.id)
        poll_interval = min(poll_interval * 1.5, 30.0)

    logger.info("Batch %s terminal status: %s", batch.id, batch.processing_status)

    # Stream results
    async for result in client.messages.batches.results(batch.id):
        custom_id = result.custom_id
        lead = next((l for l in llm_leads if str(l.lead_id) == custom_id), None)
        if lead is None:
            logger.warning("Orphan batch result custom_id=%s", custom_id)
            continue
        if result.result.type != "succeeded":
            logger.error("Batch item %s failed: %s", custom_id, result.result.type)
            continue
        # The batched result mirrors a normal Message response
        response = result.result.message
        payload = _extract_tool_input(response)
        payload = _enforce_payload(payload, lead.lead_id)
        results[lead.lead_id] = _assemble_result(lead, prefilters[lead.lead_id], payload, cfg)

    # Anything still None fell out of the batch; fail loud rather than silently dropping.
    missing = [l.lead_id for l in leads_list if results[l.lead_id] is None]
    if missing:
        raise ScoringError(f"Batch completed but missing results for {len(missing)} leads")

    return [results[l.lead_id] for l in leads_list]


# ---- Retry helper for sync path -------------------------------------------
def _call_with_retry(
    *,
    client: anthropic.Anthropic,
    model: str,
    max_tokens: int,
    temperature: float,
    system: str,
    user: str,
    cfg: ScoringConfig,
) -> dict:
    """Run a single Messages call with exponential backoff for rate/5xx errors."""
    attempt = 0
    backoff = cfg.retry.initial_backoff_seconds
    last_err: Exception | None = None
    while attempt < cfg.retry.max_attempts:
        attempt += 1
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                tools=[SCORING_TOOL],
                tool_choice={"type": "tool", "name": "score_lead"},
                messages=[{"role": "user", "content": user}],
            )
            payload = _extract_tool_input(response)
            return _enforce_payload(payload, lead_id="sync")
        except APIStatusError as e:
            last_err = e
            # Retry only on 429 / 5xx
            if e.status_code not in (408, 409, 429, 500, 502, 503, 504, 529):
                raise ScoringError(f"Non-retryable Claude error: {e}") from e
            logger.warning("Claude API status %s on attempt %d: %s", e.status_code, attempt, e)
        except APIError as e:
            last_err = e
            logger.warning("Claude API error on attempt %d: %s", attempt, e)

        time.sleep(backoff)
        backoff = min(backoff * 2, cfg.retry.max_backoff_seconds)

    raise ScoringError(f"Claude call failed after {cfg.retry.max_attempts} attempts: {last_err}")
