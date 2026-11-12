"""Tests for the authority function multiplier classification."""
from __future__ import annotations

from uuid import uuid4

from app.lead_scoring.models import LeadInput
from app.lead_scoring.tiering import classify_function_bucket


def _lead(position: str, headline: str = "") -> LeadInput:
    return LeadInput(lead_id=uuid4(), full_name="x", current_position=position, headline=headline)


def test_founder_bucket():
    b, m = classify_function_bucket(_lead("Founder", "Founder & CEO"))
    assert b == "general_management"
    assert m == 1.00


def test_ceo_bucket():
    b, m = classify_function_bucket(_lead("CEO"))
    assert b == "general_management"


def test_cto_bucket():
    b, m = classify_function_bucket(_lead("CTO"))
    assert b == "technical_leadership"
    assert m == 0.85


def test_cmo_bucket():
    b, m = classify_function_bucket(_lead("CMO"))
    assert b == "revenue_leadership"
    assert m == 0.50


def test_cro_bucket():
    b, m = classify_function_bucket(_lead("Chief Revenue Officer"))
    assert b == "revenue_leadership"


def test_coo_bucket():
    b, m = classify_function_bucket(_lead("COO"))
    assert b == "ops_director"
    assert m == 0.80


def test_junior_bucket():
    b, m = classify_function_bucket(_lead("Junior Analyst"))
    assert b == "individual_contributor"
    assert m == 0.20


def test_empty_defaults_to_ic():
    b, m = classify_function_bucket(_lead(""))
    assert b == "individual_contributor"


def test_headline_classification_promotes_role():
    b, m = classify_function_bucket(_lead("Director of Growth", "Head of Marketing"))
    # "Head of Marketing" wins -> revenue_leadership
    assert b == "revenue_leadership"
