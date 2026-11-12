"""Stage 1: rule-based pre-filter. Runs on every lead, no LLM call."""
from __future__ import annotations

from app.lead_scoring.models import LeadInput, PrefilterResult


# These catch obvious cases. The LLM still independently flags competitors because
# phrasing varies wildly ("we build apps for clients", "freelance React dev", etc.).
COMPETITOR_KEYWORDS: list[str] = [
    "dev agency",
    "software agency",
    "we build apps",
    "app development",
    "web development agency",
    "freelance developer",
    "fullstack developer",
    "it services",
    "it consultancy",
    "outsourc",
    "qa testing",
    "test automation",
    "ai consulting",
    "staff augmentation",
    "staffing agency",
    "talent augmentation",
    "mobile app development agency",
    "ios development agency",
    "android development agency",
    "web design agency",
    "digital agency",
    "software development company",
    "custom software development",
    "it outsourcing",
    "nearshore",
    "offshore development",
]


def rule_prefilter(lead: LeadInput) -> PrefilterResult:
    """Cheap, deterministic gate.

    Returns:
        - disqualified + skip_llm=True  -> drop without an LLM call (job seekers)
        - disqualified + skip_llm=False -> still call LLM to confirm the flag
                                            (saves a wasted call only when obvious)
        - not disqualified              -> proceed to LLM
    """
    if lead.open_to_work:
        return PrefilterResult(
            disqualified=True,
            reason="job seeker",
            skip_llm=True,
        )

    text = f"{lead.headline} {lead.about}".lower()
    keyword_hits = [kw for kw in COMPETITOR_KEYWORDS if kw in text]
    if keyword_hits:
        return PrefilterResult(
            disqualified=True,
            reason=f"likely competitor (keyword match: {keyword_hits[0]})",
            skip_llm=False,
        )

    return PrefilterResult(disqualified=False, reason=None, skip_llm=False)
