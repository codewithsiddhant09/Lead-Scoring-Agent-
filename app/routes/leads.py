"""Lead routes: on-demand scoring + intake endpoint."""
from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.excel_import import parse_workbook
from app.persistence import upsert_lead_from_payload

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.lead_loader import lead_from_apify
from app.lead_scoring.claude_client import score_lead_sync, score_leads_batch
from app.lead_scoring.config import load_scoring_config
from app.lead_scoring.models import LeadInput, ScoringResult, Tier
from app.lead_scoring.prefilter import rule_prefilter
from app.lead_scoring.tiering import compute_reachability_score
from app.models import Lead, LeadScore
from app.persistence import write_score_with_review
from app.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/leads", tags=["leads"])


# Tier 1 Anthropic keys are capped at 60 requests/minute. Fire too many
# concurrent calls and we trip 429s, which cascade into ScoringError, which
# the upload handler used to surface as a 500 — losing the lead rows we
# already inserted. Bound the per-lead sync path so the burst stays well
# under the ceiling, regardless of how big the uploaded file is.
_SCORE_SEMAPHORE = asyncio.Semaphore(8)


def _score_with_semaphore(loop: asyncio.AbstractEventLoop, lead_input: LeadInput, cfg):
    """Wrap `score_lead_sync` in a semaphore so the upload handler never fires
    more than `_SCORE_SEMAPHORE` Claude calls in parallel. Returns the future."""
    return loop.run_in_executor(None, _score_one_bounded, lead_input, cfg)


def _score_one_bounded(lead_input: LeadInput, cfg) -> ScoringResult:
    """Single-shot sync scoring with a semaphore acquired from a worker thread.

    Blocking on the semaphore from a thread is fine — `asyncio.Semaphore` is
    awaitable only, so we wait on its underlying `_value` instead. This keeps
    the executor pool from queuing dozens of in-flight Claude requests that
    would all 429 together.
    """
    # Acquire with a busy-wait — the loop's running elsewhere, so a short
    # poll is the simplest correct primitive without rewriting the scoring
    # client to be fully async.
    while _SCORE_SEMAPHORE._value <= 0:  # type: ignore[attr-defined]
        import time
        time.sleep(0.05)
    _SCORE_SEMAPHORE._value -= 1  # type: ignore[attr-defined]
    try:
        return score_lead_sync(lead_input, cfg=cfg)
    finally:
        _SCORE_SEMAPHORE._value += 1  # type: ignore[attr-defined]


def _failure_result(lead_input: LeadInput, cfg, exc: BaseException) -> ScoringResult:
    """Synthesize a Cold result with the error message baked into the notes
    so the lead still persists. Without this a single rate-limited lead would
    fail the entire upload via `asyncio.gather`'s default behaviour."""
    reason = f"{type(exc).__name__}: {exc}"[:255]
    return ScoringResult(
        lead_id=lead_input.lead_id,
        authority_score=0,
        fit_score=0,
        intent_score=0,
        reachability_score=compute_reachability_score(lead_input),
        blended_score=0.0,
        tier=Tier.COLD,
        is_competitor=False,
        disqualify_reason=reason,
        scoring_model=cfg.model.name,
        scoring_config_version=cfg.version,
        notes=f"scoring failed — {reason}",
    )


@router.post("/{lead_id}/score")
async def score_one(lead_id: UUID, session: AsyncSession = Depends(get_session)):
    """Score a single lead on demand. Loads the lead from `leads`, scores it, persists."""
    lead_row = await session.get(Lead, lead_id)
    if lead_row is None:
        raise HTTPException(status_code=404, detail="lead not found")

    raw = lead_row.raw_payload or {}
    payload_input: LeadInput = lead_from_apify(raw)
    payload_input = payload_input.model_copy(update={"lead_id": lead_row.id})

    cfg = load_scoring_config(get_settings().scoring_config_path)
    result = score_lead_sync(payload_input, cfg=cfg)

    inserted, review = await write_score_with_review(session, result)
    return {
        "score_id": str(inserted.id),
        "blended_score": float(inserted.blended_score),
        "tier": inserted.tier,
        "needs_review_id": str(review.id) if review else None,
        "is_competitor": inserted.is_competitor,
        "disqualify_reason": inserted.disqualify_reason,
    }


@router.post("/upload")
async def upload_excel(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    """Import an .xlsx workbook, upsert leads, and score valid rows."""
    content = await file.read()
    try:
        payloads, errors = parse_workbook(content, file.filename or "upload.xlsx")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not payloads:
        return {"created": 0, "updated": 0, "scored": 0, "needs_review": 0, "errors": errors}

    cfg = load_scoring_config(get_settings().scoring_config_path)
    lead_rows: list[Lead] = []
    created = updated = 0
    scoring_errors: list[dict[str, str]] = []
    try:
        for payload in payloads:
            lead_row, was_created = await upsert_lead_from_payload(session, payload)
            lead_rows.append(lead_row)
            if was_created:
                created += 1
            else:
                updated += 1

        inputs = [
            lead_from_apify(payload).model_copy(update={"lead_id": lead_row.id})
            for payload, lead_row in zip(payloads, lead_rows, strict=True)
        ]
        loop = asyncio.get_running_loop()
        # Tier 1 Anthropic keys are 60 RPM. The previous `asyncio.gather` fired
        # `len(inputs)` parallel Claude calls in the same second, which tripped
        # 429s and surfaced as a 500 that rolled back every lead we just
        # inserted. Bound concurrency AND tolerate per-lead failures so a
        # single rate-limited lead can't take the rest down.
        batch_outcome = "sync"
        if len(inputs) >= cfg.model.batch_size_threshold:
            try:
                results = await score_leads_batch(inputs, cfg=cfg)
                batch_outcome = "batch"
            except Exception as batch_error:
                logger.warning(
                    "Batch scoring failed; falling back to sync scoring: %s", batch_error,
                )
                batch_outcome = "batch-failed-sync-fallback"
                results = await asyncio.gather(
                    *(_score_with_semaphore(loop, lead_input, cfg) for lead_input in inputs),
                    return_exceptions=True,
                )
                results = [
                    _failure_result(li, cfg, exc) if isinstance(exc, BaseException) else exc
                    for li, exc in zip(inputs, results, strict=True)
                ]
        else:
            results = await asyncio.gather(
                *(_score_with_semaphore(loop, lead_input, cfg) for lead_input in inputs),
                return_exceptions=True,
            )
            results = [
                _failure_result(li, cfg, exc) if isinstance(exc, BaseException) else exc
                for li, exc in zip(inputs, results, strict=True)
            ]

        review_count = 0
        scored_count = 0
        for lead_input, result in zip(inputs, results, strict=True):
            if result is None:
                scoring_errors.append({
                    "lead_id": str(lead_input.lead_id),
                    "name": lead_input.full_name,
                    "error": "no result returned",
                })
                continue
            try:
                _, review = await write_score_with_review(session, result)
                review_count += bool(review)
                scored_count += 1
            except Exception as persist_exc:
                # Don't fail the whole upload because one row couldn't be
                # persisted; surface it in the response instead.
                logger.warning(
                    "Failed to persist score for lead %s: %s",
                    lead_input.lead_id, persist_exc,
                )
                scoring_errors.append({
                    "lead_id": str(lead_input.lead_id),
                    "name": lead_input.full_name,
                    "error": f"persist: {persist_exc}",
                })
                await session.rollback()
    except Exception:
        await session.rollback()
        raise

    if scoring_errors:
        logger.info(
            "Upload completed with %d scoring errors out of %d leads (path=%s)",
            len(scoring_errors), len(inputs), batch_outcome,
        )

    return {
        "created": created,
        "updated": updated,
        "scored": scored_count,
        "needs_review": review_count,
        "scoring_errors": scoring_errors,
        "scoring_path": batch_outcome,
        "errors": errors,
    }


@router.post("/score-batch")
async def score_batch(leads: list[dict], session: AsyncSession = Depends(get_session)):
    """Score a list of Apify-shaped payloads. Uses Message Batches API automatically
    when the count exceeds `model.batch_size_threshold`."""
    if not leads:
        return {"scored": 0}

    cfg = load_scoring_config(get_settings().scoring_config_path)
    persisted: list[Lead] = []
    for payload in leads:
        lead_row, _ = await upsert_lead_from_payload(session, payload)
        persisted.append(lead_row)
    inputs: list[LeadInput] = [
        lead_from_apify(payload).model_copy(update={"lead_id": lead_row.id})
        for payload, lead_row in zip(leads, persisted, strict=True)
    ]

    if len(inputs) >= cfg.model.batch_size_threshold:
        results = await score_leads_batch(inputs, cfg=cfg)
    else:
        loop = asyncio.get_running_loop()
        results = await asyncio.gather(
            *(loop.run_in_executor(None, score_lead_sync, lead_input, cfg) for lead_input in inputs)
        )

    written = 0
    review_count = 0
    for result in results:
        _, review = await write_score_with_review(session, result)
        written += 1
        if review:
            review_count += 1
    return {"scored": written, "needs_review": review_count}


@router.get("/{lead_id}/scores")
async def list_scores(lead_id: UUID, session: AsyncSession = Depends(get_session)):
    """Return every scoring row for a lead (history / audit)."""
    from sqlalchemy import select

    res = await session.execute(
        select(LeadScore).where(LeadScore.lead_id == lead_id).order_by(LeadScore.scored_at.desc())
    )
    rows = res.scalars().all()
    return [
        {
            "id": str(r.id),
            "authority_score": r.authority_score,
            "fit_score": r.fit_score,
            "intent_score": r.intent_score,
            "reachability_score": r.reachability_score,
            "blended_score": float(r.blended_score),
            "tier": r.tier,
            "is_competitor": r.is_competitor,
            "disqualify_reason": r.disqualify_reason,
            "scoring_model": r.scoring_model,
            "scoring_config_version": r.scoring_config_version,
            "scored_at": r.scored_at.isoformat() if r.scored_at else None,
        }
        for r in rows
    ]


@router.get("/latest")
async def latest_leads(session: AsyncSession = Depends(get_session)):
    """Latest score per lead, joined with lead profile — used by the dashboard."""
    from app.export import build_latest_scores_view
    return await build_latest_scores_view(session)


@router.get("/needs-review")
async def needs_review(session: AsyncSession = Depends(get_session)):
    """Open tier-disagreement rows, joined with the lead's display name."""
    from sqlalchemy import select
    from app.models import NeedsReview, Lead

    sql = (
        select(NeedsReview, Lead.full_name)
        .join(Lead, Lead.id == NeedsReview.lead_id)
        .where(NeedsReview.resolved == False)  # noqa: E712
        .order_by(NeedsReview.created_at.desc())
        .limit(200)
    )
    rows = (await session.execute(sql)).all()
    return [
        {
            "id": str(nr.id),
            "lead_id": str(nr.lead_id),
            "full_name": name,
            "previous_tier": nr.previous_tier,
            "new_tier": nr.new_tier,
            "reason": nr.reason,
            "created_at": nr.created_at.isoformat() if nr.created_at else None,
        }
        for nr, name in rows
    ]
