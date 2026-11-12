"""Persistence helpers for scoring results and uploaded leads."""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.excel_import import source_key_for
from app.lead_scoring.models import ScoringResult
from app.models import Lead, LeadScore, NeedsReview

logger = logging.getLogger(__name__)


async def fetch_last_score(session: AsyncSession, lead_id: UUID) -> LeadScore | None:
    res = await session.execute(
        select(LeadScore).where(LeadScore.lead_id == lead_id).order_by(LeadScore.scored_at.desc()).limit(1)
    )
    return res.scalar_one_or_none()


async def upsert_lead_from_payload(
    session: AsyncSession, payload: dict
) -> tuple[Lead, bool]:
    """Insert or update a lead using a stable upload identity."""
    key = source_key_for(payload)
    result = await session.execute(select(Lead).where(Lead.source_key == key).limit(1))
    lead = result.scalar_one_or_none()
    created = lead is None

    values = {
        "full_name": str(payload.get("Full Name") or "").strip(),
        "headline": payload.get("Headline"),
        "current_position": payload.get("Current Position"),
        "current_company": payload.get("Current Company"),
        "country": payload.get("Country"),
        "about": payload.get("About"),
        "open_to_work": bool(payload.get("Open To Work", False)),
        "raw_payload": payload,
        "source_key": key,
        "linkedin_url": payload.get("LinkedIn URL") or payload.get("linkedin_url"),
    }
    if lead is None:
        lead = Lead(**values)
        session.add(lead)
    else:
        for field, value in values.items():
            setattr(lead, field, value)
    await session.flush()
    return lead, created


async def write_score_with_review(
    session: AsyncSession, result: ScoringResult
) -> tuple[LeadScore, NeedsReview | None]:
    """Insert a new lead_scores row and a needs_review row on tier disagreement."""
    previous = await fetch_last_score(session, result.lead_id)

    row = LeadScore(
        lead_id=result.lead_id,
        authority_score=result.authority_score,
        fit_score=result.fit_score,
        intent_score=result.intent_score,
        reachability_score=result.reachability_score,
        blended_score=result.blended_score,
        tier=result.tier.value,
        is_competitor=result.is_competitor,
        disqualify_reason=result.disqualify_reason,
        technical_founder=result.technical_founder,
        company_stage=result.company_stage.value,
        industry_match=result.industry_match,
        notes=result.notes,
        scoring_model=result.scoring_model,
        scoring_config_version=result.scoring_config_version,
    )
    session.add(row)
    await session.flush()

    review: NeedsReview | None = None
    if previous and previous.tier != result.tier.value:
        review = NeedsReview(
            lead_id=result.lead_id,
            previous_tier=previous.tier,
            new_tier=result.tier.value,
            previous_score_id=previous.id,
            new_score_id=row.id,
            reason="tier disagreement",
        )
        session.add(review)
        await session.flush()
        logger.info("Tier disagreement for lead %s: %s -> %s", result.lead_id, previous.tier, result.tier.value)

    await session.commit()
    await session.refresh(row)
    return row, review
