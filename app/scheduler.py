"""APScheduler integration.

Pipeline (hourly by default):
    1. Find unscored leads (or leads flagged for re-score).
    2. rule_prefilter -> skip LLM for job-seekers, flag competitors.
    3. If >= batch_size_threshold, use Message Batches API; else sync.
    4. Persist rows + needs_review rows.

The function `score_unscored_leads_job` is the entry point. Wire it to your
existing Apify ingestion by calling it after your scraper stores rows.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.db import SessionLocal
from app.lead_loader import lead_from_apify
from app.lead_scoring.claude_client import score_lead_sync, score_leads_batch
from app.lead_scoring.config import load_scoring_config
from app.models import Lead, LeadScore
from app.persistence import write_score_with_review
from app.settings import get_settings

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


async def _fetch_unscored_leads(limit: int = 500) -> list[Lead]:
    """Leads that have no lead_scores row at all are the priority."""
    async with SessionLocal() as session:
        # Subquery of leads that already have a score row
        scored_ids = select(LeadScore.lead_id).distinct()
        res = await session.execute(
            select(Lead).where(Lead.id.not_in(scored_ids)).limit(limit)
        )
        return list(res.scalars().all())


async def _fetch_leads_to_rescore(older_than_days: int = 30, limit: int = 200) -> list[Lead]:
    """Leads whose latest score is older than `older_than_days` — re-scored with current config."""
    async with SessionLocal() as session:
        threshold = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        sql = select(Lead).join(LeadScore, LeadScore.lead_id == Lead.id).group_by(Lead.id).having(
            # using scalar subquery via HAVING would be awkward; instead fetch candidates then filter in code
            Lead.id.is_not(None)
        ).limit(limit)
        rows = list((await session.execute(sql)).scalars().all())
        # Filter to those whose latest score is older than threshold
        ids = [r.id for r in rows]
        if not ids:
            return []
        latest_sql = (
            select(LeadScore.lead_id, LeadScore.scored_at)
            .where(LeadScore.lead_id.in_(ids))
            .order_by(LeadScore.lead_id, LeadScore.scored_at.desc())
        )
        latest_rows = (await session.execute(latest_sql)).all()
        latest_map = {}
        for lead_id, scored_at in latest_rows:
            latest_map.setdefault(lead_id, scored_at)

        def as_utc(value):
            if value is None:
                return datetime.min.replace(tzinfo=timezone.utc)
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)

        return [r for r in rows if as_utc(latest_map.get(r.id)) < threshold]


async def score_unscored_leads_job() -> dict:
    """Scheduler entry point. Scores unscored leads + re-scores stale ones."""
    settings = get_settings()
    cfg = load_scoring_config(settings.scoring_config_path)

    unscored = await _fetch_unscored_leads()
    stale = await _fetch_leads_to_rescore()
    leads = unscored + stale

    if not leads:
        logger.info("No leads to score; idle cycle.")
        return {"scored": 0}

    inputs = []
    for lead_row in leads:
        raw = lead_row.raw_payload or {}
        li = lead_from_apify(raw).model_copy(update={"lead_id": lead_row.id})
        inputs.append(li)

    if len(inputs) >= cfg.model.batch_size_threshold:
        results = await score_leads_batch(inputs, cfg=cfg)
    else:
        # Run sync calls in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        results = await asyncio.gather(
            *(loop.run_in_executor(None, score_lead_sync, li, cfg) for li in inputs)
        )

    review_count = 0
    async with SessionLocal() as session:
        for r in results:
            _, rev = await write_score_with_review(session, r)
            if rev:
                review_count += 1

    logger.info("Scored %d leads; %d flagged for review", len(results), review_count)
    return {"scored": len(results), "needs_review": review_count}


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        score_unscored_leads_job,
        "interval",
        minutes=60,
        id="score_unscored_leads",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.utcnow() + timedelta(seconds=10),  # fire shortly after boot
    )
    _scheduler.start()
    logger.info("Scheduler started — score_unscored_leads_job every 60 min")


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
