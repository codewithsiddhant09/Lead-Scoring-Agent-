"""End-to-end: mock Anthropic -> score -> persist -> export -> gate for outreach."""
from __future__ import annotations

import io
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.db import Base
from app.export import filter_for_outreach, render_workbook
from app.lead_loader import lead_from_apify
from app.lead_scoring.claude_client import score_lead_sync
from app.lead_scoring.config import load_scoring_config
from app.models import Lead, LeadScore
from app.persistence import write_score_with_review

# ---- Fake tool_use block matching the real SCORING_TOOL schema --------------
def _fake_response(payload: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = "score_lead"
    block.input = payload
    response = MagicMock()
    response.content = [block]
    return response


CLEAN_HEALTHCARE_PAYLOAD = {
    "authority_score": 80,
    "authority_reasoning": "Founder at a 12-person healthcare startup",
    "fit_score": 88,
    "industry_match": "Healthcare - clinic operations",
    "intent_score": 72,
    "intent_signals": ["hiring", "looking for a partner", "open to outsourcing the build"],
    "is_competitor": False,
    "competitor_reason": None,
    "technical_founder": False,
    "company_stage": "Startup",
    "notes": "Strong ICP fit; non-technical founder with explicit buying intent.",
}

COMPETITOR_PAYLOAD = {
    "authority_score": 70,
    "authority_reasoning": "Co-founder of a dev shop",
    "fit_score": 15,
    "industry_match": "Software Agency",
    "intent_score": 0,
    "intent_signals": [],
    "is_competitor": True,
    "competitor_reason": "Builds apps for clients; explicitly a dev agency.",
    "technical_founder": True,
    "company_stage": "SMB",
    "notes": "Excluded — competitor.",
}


@pytest.fixture
async def async_session():
    """In-memory SQLite (async) — Postgres-only types like UUID[] aren't used here."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        # SQLite doesn't have UUID natively; use CHAR(36) for tests
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_score_clean_lead_via_mocked_claude(healthcare_founder_lead, cfg):
    with patch("app.lead_scoring.claude_client.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _fake_response(CLEAN_HEALTHCARE_PAYLOAD)
        result = score_lead_sync(healthcare_founder_lead, cfg=cfg)

    assert result.tier.value in {"Hot", "Hot-leaning Warm"}
    assert result.is_competitor is False
    # Founder bucket -> multiplier 1.00 -> authority unchanged
    assert result.authority_score == 80


@pytest.mark.asyncio
async def test_score_competitor_forces_cold(dev_agency_lead, cfg):
    with patch("app.lead_scoring.claude_client.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _fake_response(COMPETITOR_PAYLOAD)
        result = score_lead_sync(dev_agency_lead, cfg=cfg)

    assert result.tier.value == "Cold"
    assert result.is_competitor is True


@pytest.mark.asyncio
async def test_persistence_inserts_and_flags_review_on_disagreement(async_session, healthcare_founder_lead, cfg):
    # First score: Hot
    with patch("app.lead_scoring.claude_client.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _fake_response(CLEAN_HEALTHCARE_PAYLOAD)
        first = score_lead_sync(healthcare_founder_lead, cfg=cfg)

    inserted, review = await write_score_with_review(async_session, first)
    assert inserted.id is not None
    assert review is None  # first score, no prior row

    # Second score (different payload) — forces tier disagreement
    different_payload = dict(CLEAN_HEALTHCARE_PAYLOAD, fit_score=20)  # -> Cold
    with patch("app.lead_scoring.claude_client.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _fake_response(different_payload)
        second = score_lead_sync(healthcare_founder_lead, cfg=cfg)

    inserted2, review2 = await write_score_with_review(async_session, second)
    assert review2 is not None
    assert review2.previous_tier != review2.new_tier


def test_excel_export_renders_with_color_coding():
    rows = [
        {
            "lead_id": uuid4(),
            "full_name": "Avery Quinn",
            "headline": "Founder at CareRoute Health",
            "current_position": "Founder",
            "current_company": "CareRoute Health",
            "country": "US",
            "authority_score": 80,
            "fit_score": 88,
            "intent_score": 72,
            "reachability_score": 90,
            "blended_score": 81.9,
            "tier": "Hot",
            "is_competitor": False,
            "disqualify_reason": None,
            "industry_match": "Healthcare",
            "company_stage": "Startup",
            "technical_founder": False,
            "notes": "Strong ICP fit.",
            "scoring_model": "claude-sonnet-4-6",
            "scoring_config_version": "1.0.0",
            "scored_at": None,
        },
        {
            "lead_id": uuid4(),
            "full_name": "Riley DevShop",
            "headline": "dev agency owner",
            "current_position": "Co-founder",
            "current_company": "PixelForge",
            "country": "CA",
            "authority_score": 80,
            "fit_score": 10,
            "intent_score": 0,
            "reachability_score": 60,
            "blended_score": 38.0,
            "tier": "Cold",
            "is_competitor": True,
            "disqualify_reason": "competitor flagged by LLM",
            "industry_match": "Software Agency",
            "company_stage": "SMB",
            "technical_founder": True,
            "notes": "Excluded.",
            "scoring_model": "claude-sonnet-4-6",
            "scoring_config_version": "1.0.0",
            "scored_at": None,
        },
    ]
    data = render_workbook(rows)
    assert len(data) > 0

    wb = load_workbook(io.BytesIO(data))
    ws = wb.active
    tier_col = next(i for i, cell in enumerate(ws[1], start=1) if cell.value == "Tier")
    hot_cell = ws.cell(row=2, column=tier_col)
    cold_cell = ws.cell(row=3, column=tier_col)
    # Verify fill colors via openpyxl internal
    assert hot_cell.fill.start_color.rgb in ("00C6EFCE", "FFC6EFCE")
    assert cold_cell.fill.start_color.rgb in ("00FFC7CE", "FFFFC7CE")


def test_outreach_filter_excludes_competitors_and_cold():
    rows = [
        {"tier": "Hot", "is_competitor": False},
        {"tier": "Hot-leaning Warm", "is_competitor": False},
        {"tier": "Warm", "is_competitor": False},
        {"tier": "Hot", "is_competitor": True},       # excluded
        {"tier": "Cold", "is_competitor": False},
    ]
    eligible = filter_for_outreach(rows)
    tiers = [r["tier"] for r in eligible]
    assert "Warm" not in tiers
    assert "Cold" not in tiers
    assert len(eligible) == 2


def test_apify_loader_maps_fields():
    raw = {
        "Full Name": "Jane Smith",
        "Headline": "Founder & CEO at Acme",
        "Current Position": "Founder & CEO",
        "Current Company": "Acme",
        "Country": "USA",
        "About": "Building a fintech app",
        "Open To Work": "no",
        "Email(s)": ["jane@acme.com"],
        "Email Status(es)": ["valid"],
        "Email Quality Score(s)": [90.0],
        "Top Skills": ["Fintech", "Product"],
    }
    lead = lead_from_apify(raw)
    assert lead.full_name == "Jane Smith"
    assert lead.current_company == "Acme"
    assert lead.emails == ["jane@acme.com"]
    assert lead.email_statuses == ["valid"]
    assert lead.email_quality_scores == [90.0]
    assert lead.open_to_work is False


def test_apify_loader_handles_open_to_work_string():
    raw = {"Full Name": "x", "Open To Work": "yes"}
    lead = lead_from_apify(raw)
    assert lead.open_to_work is True
