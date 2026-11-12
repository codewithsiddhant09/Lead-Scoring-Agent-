"""Tier calculation: blended score + hard overrides + authority function multiplier."""
from __future__ import annotations

from dataclasses import dataclass

from app.lead_scoring.config import ScoringConfig
from app.lead_scoring.models import (
    LeadInput,
    PrefilterResult,
    ScoringResult,
    Tier,
)


@dataclass(frozen=True)
class AxisScores:
    """Raw 0-100 axis scores BEFORE the authority multiplier and tier overrides."""

    authority: int
    fit: int
    intent: int
    reachability: int


# ---- Function multiplier classification ------------------------------------
# Bucket order is significant: revenue_leadership is checked BEFORE ops_director so
# that "Director of Growth" with "Head of Marketing" headline doesn't match on the
# generic "director" substring first.
_FUNCTION_BUCKETS: list[tuple[set[str], str]] = [
    (
        {
            "founder", "co-founder", "cofounder", "ceo", "managing director", "md",
            "owner", "president",
        },
        "general_management",
    ),
    (
        {"cmo", "cro", "vp sales", "vp marketing", "head of marketing", "head of sales",
         "bd", "business development", "partnerships", "head of partnerships",
         "chief marketing officer", "chief revenue officer", "chief sales officer",
         "chief business officer", "head of revenue", "head of growth",
         "growth", "marketing", "sales"},
        "revenue_leadership",
    ),
    (
        {"cto", "vp engineering", "vp of engineering", "head of product", "vp product",
         "chief technology officer", "chief product officer", "head of engineering",
         "vp engineering"},
        "technical_leadership",
    ),
    (
        {"coo", "vp operations", "director of operations", "operations director",
         "chief operating officer"},
        "ops_director",
    ),
]


def classify_function_bucket(lead: LeadInput) -> tuple[str, float]:
    """Return (bucket_name, multiplier) based on current_position + headline.

    Order matters: revenue/tech/ops buckets are checked BEFORE general_management
    so that "Chief Revenue Officer" doesn't fall into the "chief" fallback.
    """
    text = f"{lead.current_position} {lead.headline}".lower()
    if not text.strip():
        return ("individual_contributor", 0.20)

    # Seniority floor: anything with "junior", "intern", "analyst" -> IC bucket
    if any(j in text for j in ("intern", "junior", "assistant ", "analyst")):
        return ("individual_contributor", 0.20)

    # 1. Specific function buckets first — so "Chief Marketing Officer" -> revenue, not general.
    for needles, bucket in _FUNCTION_BUCKETS:
        for needle in needles:
            if needle in text:
                return (bucket, _MULTIPLIER[bucket])

    # 2. Senior generic-title words -> general_management (Founder / CEO / President / Owner)
    if any(w in text for w in ("founder", "co-founder", "cofounder", "ceo", "md",
                               "managing director", "owner", "president")):
        return ("general_management", _MULTIPLIER["general_management"])

    # 3. Has title-ish seniority word but didn't match above -> default to general
    if any(w in text for w in ("chief", "head", "vp", "vice president")):
        return ("general_management", _MULTIPLIER["general_management"])

    return ("individual_contributor", _MULTIPLIER["individual_contributor"])


_MULTIPLIER: dict[str, float] = {
    "general_management": 1.00,
    "technical_leadership": 0.85,
    "ops_director": 0.80,
    "revenue_leadership": 0.50,
    "individual_contributor": 0.20,
}


# ---- Reachability computation (deterministic; never LLM) -------------------
def compute_reachability_score(lead: LeadInput) -> int:
    """0-100 score from email status, email quality, and LinkedIn activity flags."""
    score = 0.0

    # Emails (up to 60 points)
    if lead.emails:
        statuses = [s.lower() for s in lead.email_statuses] or ["unknown"] * len(lead.emails)
        qualities = lead.email_quality_scores or [None] * len(lead.emails)

        best_email_score = 0.0
        for status, quality in zip(statuses, qualities, strict=False):
            per_email = 0.0
            if status == "valid":
                per_email = 60.0
            elif status == "catch_all":
                per_email = 35.0
            elif status == "unknown":
                per_email = 20.0
            # invalid -> 0
            if quality is not None:
                per_email = max(per_email, float(quality) * 0.6)
            best_email_score = max(best_email_score, per_email)
        score += best_email_score

    # LinkedIn activity (up to 40 points)
    if lead.linkedin_premium:
        score += 15
    if lead.linkedin_verified:
        score += 15
    if lead.linkedin_open_profile:
        score += 10

    return max(0, min(100, int(round(score))))


# ---- Blended score + tier ---------------------------------------------------
def compute_blended_score(authority: int, fit: int, intent: int, reachability: int,
                          cfg: ScoringConfig) -> float:
    w = cfg.weights
    raw = (
        w.authority * authority
        + w.fit * fit
        + w.intent * intent
        + w.reachability * reachability
    )
    return round(raw, 1)


def tier_for(blended: float, fit: int, pre: PrefilterResult, cfg: ScoringConfig) -> tuple[Tier, str | None]:
    """Pure function — easy to unit-test boundary cases.

    Returns (tier, disqualify_reason). disqualify_reason is None for non-disqualified leads.
    """
    # Hard override #1: prefilter disqualified
    if pre.disqualified:
        return (Tier.COLD, pre.reason or "prefilter")

    # Hard override #2: fit floor
    if fit < cfg.fit_floor:
        return (Tier.COLD, f"fit floor (< {cfg.fit_floor})")

    # Apply tier bands top-down
    if blended >= cfg.tiers.hot_min:
        return (Tier.HOT, None)
    if blended >= cfg.tiers.hot_lean_min:
        return (Tier.HOT_LEANING_WARM, None)
    if blended >= cfg.tiers.warm_min:
        return (Tier.WARM, None)
    return (Tier.COLD, None)
