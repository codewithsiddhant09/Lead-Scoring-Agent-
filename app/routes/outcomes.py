"""Outcome logging — manual or webhook-driven."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Lead, LeadOutcome

router = APIRouter(prefix="/outcomes", tags=["outcomes"])


class OutcomeIn(BaseModel):
    lead_id: UUID
    contacted_at: datetime | None = None
    contact_channel: str | None = None  # linkedin / email
    replied: bool | None = None
    replied_at: datetime | None = None
    converted: bool | None = None
    deal_value: float | None = None


@router.post("")
async def upsert_outcome(payload: OutcomeIn, session: AsyncSession = Depends(get_session)):
    lead = await session.get(Lead, payload.lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="lead not found")

    outcome = LeadOutcome(
        lead_id=payload.lead_id,
        contacted_at=payload.contacted_at,
        contact_channel=payload.contact_channel,
        replied=payload.replied,
        replied_at=payload.replied_at,
        converted=payload.converted,
        deal_value=payload.deal_value,
    )
    session.add(outcome)
    await session.commit()
    await session.refresh(outcome)
    return {"id": str(outcome.id), "lead_id": str(outcome.lead_id)}
