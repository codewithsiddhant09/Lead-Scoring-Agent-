"""Shared pytest fixtures and helpers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from app.lead_scoring.config import load_scoring_config
from app.lead_scoring.models import LeadInput


@pytest.fixture(scope="session")
def cfg():
    return load_scoring_config(str(ROOT / "scoring_config.yaml"))


# ---- Five canonical example leads (mix of profiles) -----------------------
@pytest.fixture
def healthcare_founder_lead() -> LeadInput:
    return LeadInput(
        lead_id="11111111-1111-1111-1111-111111111111",
        full_name="Avery Quinn",
        headline="Founder & CEO at CareRoute Health — building scheduling tools for clinics",
        current_position="Founder",
        current_company="CareRoute Health",
        company_websites=["https://careroute.health"],
        country="United States",
        about=(
            "Non-technical founder running a 12-person clinic-operations startup. "
            "We're hiring our first mobile app team and looking for a partner to build "
            "a patient-facing booking platform. Open to engaging an external team."
        ),
        top_skills=["Operations", "Healthcare", "Fundraising"],
        hiring=True,
        emails=["avery@careroute.health"],
        email_statuses=["valid"],
        email_quality_scores=[92.0],
        linkedin_premium=True,
        linkedin_verified=True,
    )


@pytest.fixture
def dev_agency_lead() -> LeadInput:
    return LeadInput(
        lead_id="22222222-2222-2222-2222-222222222222",
        full_name="Riley DevShop",
        headline="Co-founder at PixelForge — we build apps for clients",
        current_position="Co-founder",
        current_company="PixelForge Studio",
        company_websites=["https://pixelforge.dev"],
        country="Canada",
        about="Full-service dev agency. We ship mobile + web for startups.",
        top_skills=["React Native", "Node.js"],
        emails=["riley@pixelforge.dev"],
        email_statuses=["valid"],
        email_quality_scores=[88.0],
    )


@pytest.fixture
def job_seeker_lead() -> LeadInput:
    return LeadInput(
        lead_id="33333333-3333-3333-3333-333333333333",
        full_name="Sam Jobless",
        headline="Senior Product Manager — Open To Work",
        current_position="Senior PM",
        current_company="(unemployed)",
        open_to_work=True,
        emails=["sam@gmail.com"],
        email_statuses=["catch_all"],
        email_quality_scores=[40.0],
    )


@pytest.fixture
def borderline_fit_lead() -> LeadInput:
    return LeadInput(
        lead_id="44444444-4444-4444-4444-444444444444",
        full_name="Casey Logan",
        headline="Fractional CMO at NorthBay Consulting",
        current_position="Fractional CMO",
        current_company="NorthBay Consulting",
        company_websites=["https://northbay.io"],
        country="United States",
        about="Marketing consultant. I advise e-commerce founders on growth.",
        top_skills=["Growth", "Lifecycle", "Brand"],
        emails=["casey@northbay.io"],
        email_statuses=["valid"],
        email_quality_scores=[85.0],
        linkedin_open_profile=True,
    )


@pytest.fixture
def enterprise_logistics_lead() -> LeadInput:
    return LeadInput(
        lead_id="55555555-5555-5555-5555-555555555555",
        full_name="Pat Hernandez",
        headline="Chief Operating Officer at Meridian Freight",
        current_position="COO",
        current_company="Meridian Freight",
        company_websites=["https://meridianfreight.com"],
        country="Mexico",
        about=(
            "Modernizing our fleet ops. RFP out for a custom TMS — interested in partners "
            "with logistics software experience. Digital transformation underway."
        ),
        top_skills=["Operations", "Logistics", "Procurement"],
        hiring=True,
        emails=["pat@meridianfreight.com"],
        email_statuses=["valid"],
        email_quality_scores=[95.0],
        linkedin_premium=True,
        linkedin_verified=True,
        linkedin_open_profile=True,
    )
