"""Config endpoints — view current + hot-reload after editing scoring_config.yaml."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.export import export_to_bytes, filter_for_outreach, build_latest_scores_view
from app.lead_scoring.config import load_scoring_config, reload_scoring_config
from app.settings import get_settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/scoring")
async def get_scoring_config():
    cfg = load_scoring_config(get_settings().scoring_config_path)
    return cfg.model_dump(mode="json")


@router.post("/scoring/reload")
async def reload_scoring():
    cfg = reload_scoring_config(get_settings().scoring_config_path)
    return {"version": cfg.version, "reloaded": True}


# ---- Export routes ---------------------------------------------------------
@router.get("/export.xlsx")
async def export_xlsx(session: AsyncSession = Depends(get_session)):
    """Download the latest-scores view as a styled .xlsx file."""
    data = await export_to_bytes(session)
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=lead_scores.xlsx"},
    )


@router.get("/outreach-queue")
async def outreach_queue(session: AsyncSession = Depends(get_session)):
    """JSON list of leads eligible for HeyReach/Smartlead auto-dispatch."""
    rows = await build_latest_scores_view(session)
    return filter_for_outreach(rows)
