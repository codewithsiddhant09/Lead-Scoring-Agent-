"""Read-only analytics — the calibration loop's source of truth."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/by-tier")
async def reply_conversion_by_tier(session: AsyncSession = Depends(get_session)):
    """Reply + conversion rate grouped by the most recent tier per lead.

    Uses the LATEST lead_scores row per lead so re-scored leads count under their
    newest tier — matches what outreach dispatch sees.
    """
    sql = text(
        """
        WITH ranked_scores AS (
            SELECT
                lead_id,
                tier,
                ROW_NUMBER() OVER (
                    PARTITION BY lead_id
                    ORDER BY scored_at DESC, id DESC
                ) AS score_rank
            FROM lead_scores
        ), latest AS (
            SELECT lead_id, tier
            FROM ranked_scores
            WHERE score_rank = 1
        )
        SELECT
            l.tier,
            COUNT(*) AS total,
            COALESCE(AVG(CASE WHEN o.replied IS TRUE THEN 1.0 ELSE 0.0 END), 0) AS reply_rate,
            COALESCE(AVG(CASE WHEN o.converted IS TRUE THEN 1.0 ELSE 0.0 END), 0) AS conversion_rate,
            COALESCE(AVG(o.deal_value), 0) AS avg_deal_value
        FROM latest l
        LEFT JOIN lead_outcomes o ON o.lead_id = l.lead_id
        GROUP BY l.tier
        ORDER BY
            CASE l.tier
                WHEN 'Hot' THEN 0
                WHEN 'Hot-leaning Warm' THEN 1
                WHEN 'Warm' THEN 2
                WHEN 'Cold' THEN 3
                ELSE 4
            END;
        """
    )
    rows = (await session.execute(sql)).mappings().all()
    return [dict(r) for r in rows]


@router.get("/calibration-summary")
async def calibration_summary(session: AsyncSession = Depends(get_session)):
    """Lightweight stats useful when recalibrating thresholds."""
    sql = text(
        """
        WITH ranked_scores AS (
            SELECT
                lead_id,
                tier,
                blended_score,
                ROW_NUMBER() OVER (
                    PARTITION BY lead_id
                    ORDER BY scored_at DESC, id DESC
                ) AS score_rank
            FROM lead_scores
        ), latest AS (
            SELECT lead_id, tier, blended_score
            FROM ranked_scores
            WHERE score_rank = 1
        )
        SELECT
            tier,
            COUNT(*) AS n,
            MIN(blended_score) AS min_score,
            AVG(blended_score) AS avg_score,
            MAX(blended_score) AS max_score
        FROM latest
        GROUP BY tier;
        """
    )
    rows = (await session.execute(sql)).mappings().all()
    return [dict(r) for r in rows]
