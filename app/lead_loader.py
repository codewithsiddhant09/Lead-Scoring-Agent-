"""Convert raw Apify/CRM-shaped dicts into LeadInput."""
from __future__ import annotations

import uuid
from typing import Any

from app.lead_scoring.models import LeadInput


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def _as_float_list(value: Any) -> list[float | None]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[float | None] = []
        for v in value:
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                out.append(None)
        return out
    try:
        return [float(value)]
    except (TypeError, ValueError):
        return [None]


def lead_from_apify(payload: dict[str, Any]) -> LeadInput:
    """Accept whatever shape the Apify LinkedIn scraper emits (best-effort).

    All fields fall back to defaults so a partial row from a slow Apify run still scores.
    The `lead_id` is generated if missing — callers who have a real UUID should override it
    AFTER calling this with `lead.model_copy(update={"lead_id": ...})` once the row is persisted.
    """
    open_to_work_raw = payload.get("Open To Work") or payload.get("open_to_work") or False
    if isinstance(open_to_work_raw, str):
        open_to_work = open_to_work_raw.strip().lower() in ("yes", "true", "1", "open")
    else:
        open_to_work = bool(open_to_work_raw)

    hiring_raw = payload.get("Hiring") or payload.get("hiring") or False
    if isinstance(hiring_raw, str):
        hiring = hiring_raw.strip().lower() in ("yes", "true", "1", "hiring")
    else:
        hiring = bool(hiring_raw)

    return LeadInput(
        lead_id=uuid.uuid4(),
        full_name=str(payload.get("Full Name") or payload.get("full_name") or ""),
        headline=str(payload.get("Headline") or payload.get("headline") or ""),
        current_position=str(
            payload.get("Current Position") or payload.get("current_position") or ""
        ),
        current_company=str(
            payload.get("Current Company") or payload.get("current_company") or ""
        ),
        company_websites=_as_list(payload.get("Company Website(s)") or payload.get("websites")),
        country=str(payload.get("Country") or payload.get("country") or ""),
        about=str(payload.get("About") or payload.get("about") or ""),
        top_skills=_as_list(payload.get("Top Skills") or payload.get("top_skills")),
        open_to_work=open_to_work,
        hiring=hiring,
        connections=payload.get("Connections") or payload.get("connections"),
        followers=payload.get("Followers") or payload.get("followers"),
        emails=_as_list(payload.get("Email(s)") or payload.get("emails")),
        email_statuses=_as_list(payload.get("Email Status(es)") or payload.get("email_statuses")),
        email_quality_scores=_as_float_list(
            payload.get("Email Quality Score(s)") or payload.get("email_quality_scores")
        ),
        linkedin_premium=bool(payload.get("linkedin_premium") or payload.get("Premium")),
        linkedin_verified=bool(payload.get("linkedin_verified") or payload.get("Verified")),
        linkedin_open_profile=bool(
            payload.get("linkedin_open_profile") or payload.get("Open Profile")
        ),
        linkedin_url=str(
            payload.get("LinkedIn URL") or payload.get("linkedin_url")
            or payload.get("linkedinUrl") or ""
        ) or None,
    )
