"""Tests for the deterministic reachability computation."""
from __future__ import annotations

from uuid import uuid4

from app.lead_scoring.models import LeadInput
from app.lead_scoring.tiering import compute_reachability_score


def _lead(**kwargs) -> LeadInput:
    base = dict(lead_id=uuid4(), full_name="x")
    base.update(kwargs)
    return LeadInput(**base)


def test_no_signals_is_zero():
    assert compute_reachability_score(_lead()) == 0


def test_valid_email_only():
    lead = _lead(emails=["a@b.com"], email_statuses=["valid"])
    assert compute_reachability_score(lead) == 60


def test_valid_email_plus_premium_plus_verified_plus_open():
    lead = _lead(
        emails=["a@b.com"],
        email_statuses=["valid"],
        email_quality_scores=[100.0],
        linkedin_premium=True,
        linkedin_verified=True,
        linkedin_open_profile=True,
    )
    # 60 (email) + 15 + 15 + 10 = 100 -> clipped to 100
    assert compute_reachability_score(lead) == 100


def test_invalid_email_no_linkedin():
    lead = _lead(emails=["bad@b.com"], email_statuses=["invalid"])
    assert compute_reachability_score(lead) == 0


def test_catch_all_partial_credit():
    lead = _lead(emails=["a@b.com"], email_statuses=["catch_all"])
    assert compute_reachability_score(lead) == 35


def test_best_email_wins():
    """When multiple emails, the best one's score is used."""
    lead = _lead(
        emails=["bad@b.com", "good@b.com"],
        email_statuses=["invalid", "valid"],
    )
    assert compute_reachability_score(lead) == 60
