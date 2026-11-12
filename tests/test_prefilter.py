"""Unit tests for the rule-based prefilter."""
from __future__ import annotations

from uuid import uuid4

from app.lead_scoring.models import LeadInput
from app.lead_scoring.prefilter import rule_prefilter


def _lead(**kwargs) -> LeadInput:
    base = dict(
        lead_id=uuid4(),
        full_name="Test User",
        headline="",
        current_position="",
        current_company="",
        about="",
    )
    base.update(kwargs)
    return LeadInput(**base)


def test_job_seeker_disqualified_with_skip_llm():
    lead = _lead(open_to_work=True, headline="PM looking for new role")
    res = rule_prefilter(lead)
    assert res.disqualified is True
    assert res.reason == "job seeker"
    assert res.skip_llm is True


def test_dev_agency_keyword_match_still_calls_llm():
    lead = _lead(headline="Co-founder at dev agency", about="We build apps for clients")
    res = rule_prefilter(lead)
    assert res.disqualified is True
    assert res.skip_llm is False
    assert "competitor" in (res.reason or "")


def test_clean_healthcare_founder_passes():
    lead = _lead(
        headline="Founder at HealthCo",
        about="Non-technical founder building patient scheduling tools",
    )
    res = rule_prefilter(lead)
    assert res.disqualified is False
    assert res.reason is None


def test_freelance_keyword_caught():
    lead = _lead(headline="Freelance developer available for hire")
    res = rule_prefilter(lead)
    assert res.disqualified is True
    assert "competitor" in (res.reason or "")


def test_outsource_keyword_caught():
    lead = _lead(headline="We help clients outsource their engineering teams")
    res = rule_prefilter(lead)
    assert res.disqualified is True


def test_clean_enterprise_lead_passes():
    lead = _lead(
        headline="COO at a logistics company",
        about="Modernizing TMS, hiring, RFP issued",
    )
    res = rule_prefilter(lead)
    assert res.disqualified is False
