"""Excel export — colored tier cells, full 4-axis breakdown.

Color spec (matches existing palette per requirements):
    Hot               -> C6EFCE (green)
    Hot-leaning Warm  -> FFEB9C (yellow)
    Warm              -> FFEB9C (yellow)
    Cold              -> FFC7CE (red)
"""
from __future__ import annotations

import io
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead, LeadScore
from app.settings import get_settings

TIER_FILL = {
    "Hot": PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
    "Hot-leaning Warm": PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"),
    "Warm": PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"),
    "Cold": PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
}

EXCEL_COLUMNS: list[tuple[str, str]] = [
    ("lead_id", "Lead ID"),
    ("linkedin_url", "LinkedIn URL"),
    ("public_identifier", "Public Identifier"),
    ("full_name", "Full Name"),
    ("headline", "Headline"),
    ("current_position", "Position"),
    ("current_company", "Company"),
    ("country", "Country"),
    ("emails", "Email(s)"),
    ("email_statuses", "Email Status(es)"),
    ("email_quality_scores", "Email Quality Score(s)"),
    ("company_websites", "Company Website(s)"),
    ("top_skills", "Top Skills"),
    ("authority_score", "Authority (0-100)"),
    ("fit_score", "Fit (0-100)"),
    ("intent_score", "Intent (0-100)"),
    ("reachability_score", "Reachability (0-100)"),
    ("blended_score", "Blended Score"),
    ("tier", "Tier"),
    ("is_competitor", "Is Competitor"),
    ("disqualify_reason", "Disqualify Reason"),
    ("industry_match", "Industry"),
    ("company_stage", "Company Stage"),
    ("technical_founder", "Technical Founder"),
    ("notes", "Notes"),
    ("scoring_model", "Model"),
    ("scoring_config_version", "Config Version"),
    ("scored_at", "Scored At"),
]


# raw_payload keys we read for fields that aren't typed columns on Lead.
# Keys match the canonical names produced by app/excel_import.py:HEADER_ALIASES.
_RAW_KEYS = {
    "emails": "Email(s)",
    "email_statuses": "Email Status(es)",
    "email_quality_scores": "Email Quality Score(s)",
    "company_websites": "Company Website(s)",
    "top_skills": "Top Skills",
}


def _read_raw_payload(lead: Lead, key: str) -> object:
    """Read a list-typed value from raw_payload, returning [] when absent."""
    raw_key = _RAW_KEYS.get(key)
    if not raw_key or not lead.raw_payload:
        return []
    value = lead.raw_payload.get(raw_key)
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


# Apify's email-verifier actor stores the email + its deliverability metadata
# as a dict encoded into a string cell. _extract_email_dict handles three
# shapes — a real dict, a single stringified-dict cell, and a list of
# fragment strings that Excel split across cells when the source workbook
# stored the dict-as-string with embedded commas. The last case is the
# most common with the user's actual exports.
def _extract_email_dict(entry: object) -> dict | None:
    if isinstance(entry, dict):
        return entry
    if isinstance(entry, str):
        text = entry.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                import ast
                parsed = ast.literal_eval(text)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, SyntaxError):
                return None
    return None


def _coalesce_email_fragments(entries: list[object]) -> list[dict | str]:
    """Reassemble dict-as-string fragments that Excel split across cells.

    The Apify email-verifier actor stores the deliverability record as a
    single dict encoded as a Python repr (e.g. "{'email': 'a@b.com',
    'status': 'valid', 'qualityScore': 80}"). When that string is written
    to an .xlsx and then read back via openpyxl, Excel's comma splitter
    breaks it into a list of substrings like ["{'email': 'a@b.com'",
    "'status': 'valid'", "'qualityScore': 80}"]. We stitch those fragments
    back together here before attempting the literal_eval parse.
    """
    if not entries:
        return []
    # Detect the split-dict pattern: the first fragment starts with "{'" and
    # the last fragment ends with "}". When that matches, merge them.
    if (
        len(entries) > 1
        and isinstance(entries[0], str)
        and isinstance(entries[-1], str)
        and entries[0].lstrip().startswith("{'")
        and entries[-1].rstrip().endswith("}")
    ):
        merged = ", ".join(str(e).strip() for e in entries)
        return [merged]
    return entries


def _coalesce_skill_fragments(entries: list[object]) -> list[object]:
    """Reassemble a list-of-dicts stored as a single string and broken
    across cells by Excel's comma splitter.

    Apify's profile-scraper returns skills as a list of `{name, positions,
    endorsements}` dicts. When that list is written to .xlsx as a repr, the
    result looks like `[{"name": "AI Workflow Automation"}, {"name": "AI
    Governance"}, ...]`. Excel splits at the comma, so openpyxl returns the
    list as ['[{"name": "AI Workflow Automation"}', '{"name": "AI
    Governance"}', ...]'. We detect that shape and merge the fragments back
    into a single string, then parse it as Python.
    """
    if not entries:
        return []
    if not all(isinstance(e, str) for e in entries):
        return entries
    first, last = entries[0].lstrip(), entries[-1].rstrip()
    if first.startswith("[{") and last.endswith("}]"):
        merged = ", ".join(str(e).strip() for e in entries)
        try:
            import ast
            parsed = ast.literal_eval(merged)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, SyntaxError):
            pass
    return entries


def _extract_email_addresses(lead: Lead) -> list[str]:
    """Plain email addresses, one per entry."""
    out: list[str] = []
    entries = _read_raw_payload(lead, "emails") or []
    for entry in _coalesce_email_fragments(entries):
        # Empty-list-as-string ("[]") shows up when the source cell was blank
        # but openpyxl still surfaced a one-element list with the literal text.
        if isinstance(entry, str) and entry.strip() in ("[]", ""):
            continue
        d = _extract_email_dict(entry)
        if d and d.get("email"):
            out.append(str(d["email"]).strip())
        elif isinstance(entry, str) and entry.strip():
            out.append(entry.strip())
    return out


def _extract_email_statuses(lead: Lead) -> list[str]:
    """Deliverability status ('valid', 'invalid', 'risky', ...) per email."""
    out: list[str] = []
    entries = _read_raw_payload(lead, "emails") or []
    for entry in _coalesce_email_fragments(entries):
        d = _extract_email_dict(entry)
        if d and d.get("status"):
            out.append(str(d["status"]).strip())
    return out


def _extract_email_quality_scores(lead: Lead) -> list[str]:
    """Quality score (0-100) per email."""
    out: list[str] = []
    entries = _read_raw_payload(lead, "emails") or []
    for entry in _coalesce_email_fragments(entries):
        d = _extract_email_dict(entry)
        if d and d.get("qualityScore") is not None:
            out.append(str(d["qualityScore"]).strip())
    return out


def _extract_skills(lead: Lead) -> list[str]:
    """Skill names, ignoring endorsement metadata."""
    out: list[str] = []
    entries = _read_raw_payload(lead, "top_skills") or []
    for entry in _coalesce_skill_fragments(entries):
        if isinstance(entry, str) and entry.strip() in ("[]", ""):
            continue
        if isinstance(entry, dict) and entry.get("name"):
            out.append(str(entry["name"]).strip())
        elif isinstance(entry, str) and entry.strip():
            out.append(entry.strip())
    return out


def _extract_websites(lead: Lead) -> list[str]:
    """Lower-cased, scheme-stripped domain list."""
    out: list[str] = []
    for entry in _read_raw_payload(lead, "company_websites") or []:
        if not isinstance(entry, str):
            continue
        text = entry.strip()
        if not text:
            continue
        # Drop scheme and path so a row shows just "acme.com"
        for prefix in ("https://", "http://"):
            if text.lower().startswith(prefix):
                text = text[len(prefix):]
                break
        out.append(text.split("/", 1)[0].strip().lower())
    return [s for s in out if s]


def _public_identifier(lead: Lead) -> str:
    """Extract the vanity slug from the LinkedIn URL or raw_payload fallback.

    The typed `Lead.linkedin_url` column is the source of truth, but older
    rows imported before the LinkedIn URL header alias existed may only have
    the slug in raw_payload. Returning a value even when the URL is missing
    lets the SDR locate the profile by slug.
    """
    url = lead.linkedin_url or ""
    if url:
        slug = url.rstrip("/").rsplit("/", 1)[-1].strip()
        if slug and slug != "in":
            return slug
    raw = lead.raw_payload or {}
    for key in ("Public Identifier", "publicIdentifier", "public_identifier"):
        slug = str(raw.get(key) or "").strip()
        if slug:
            return slug
    return ""


async def build_latest_scores_view(session: AsyncSession, limit: int = 10000) -> list[dict]:
    """Fetch one row per lead (latest score only), joined with lead profile."""
    sql = (
        select(Lead, LeadScore)
        .join(LeadScore, LeadScore.lead_id == Lead.id)
        .order_by(Lead.id, LeadScore.scored_at.desc())
        .limit(limit * 2)
    )
    rows = (await session.execute(sql)).all()
    seen: set = set()
    out: list[dict] = []
    for lead, score in rows:
        if lead.id in seen:
            continue
        seen.add(lead.id)
        out.append({
            "lead_id": lead.id,
            "linkedin_url": lead.linkedin_url or "",
            "public_identifier": _public_identifier(lead),
            "full_name": lead.full_name,
            "headline": lead.headline or "",
            "current_position": lead.current_position or "",
            "current_company": lead.current_company or "",
            "country": lead.country or "",
            "emails": _extract_email_addresses(lead),
            "email_statuses": _extract_email_statuses(lead),
            "email_quality_scores": _extract_email_quality_scores(lead),
            "company_websites": _extract_websites(lead),
            "top_skills": _extract_skills(lead),
            "authority_score": score.authority_score,
            "fit_score": score.fit_score,
            "intent_score": score.intent_score,
            "reachability_score": score.reachability_score,
            "blended_score": float(score.blended_score),
            "tier": score.tier,
            "is_competitor": score.is_competitor,
            "disqualify_reason": score.disqualify_reason,
            "industry_match": score.industry_match,
            "company_stage": score.company_stage,
            "technical_founder": score.technical_founder,
            "notes": score.notes,
            "scoring_model": score.scoring_model,
            "scoring_config_version": score.scoring_config_version,
            "scored_at": score.scored_at,
        })
        if len(out) >= limit:
            break
    return out


def _set_auto_widths(ws) -> None:
    for idx, col in enumerate(EXCEL_COLUMNS, start=1):
        max_len = len(col[1])
        for cell in ws[get_column_letter(idx)]:
            if cell.value is not None:
                max_len = max(max_len, min(len(str(cell.value)), 60))
        ws.column_dimensions[get_column_letter(idx)].width = max_len + 2


def render_workbook(rows: Iterable[dict]) -> bytes:
    """Render the latest-scores view as a styled .xlsx and return the bytes."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Lead Scores"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="305496", end_color="305496", fill_type="solid")
    for col_idx, (_, label) in enumerate(EXCEL_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=label)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    tier_col_idx = next(i for i, (k, _) in enumerate(EXCEL_COLUMNS, start=1) if k == "tier")

    for row_idx, row in enumerate(rows, start=2):
        for col_idx, (key, _) in enumerate(EXCEL_COLUMNS, start=1):
            value = row.get(key)
            # List-typed fields (emails, websites, skills) flow out of raw_payload
            # as Python lists. Excel cells don't represent lists natively, so
            # join them with `, ` and surface each value as its own token.
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value if item not in (None, ""))
            elif hasattr(value, "isoformat"):
                value = value.isoformat()
            elif hasattr(value, "hex"):  # UUID
                value = str(value)
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            if col_idx == tier_col_idx and isinstance(value, str) and value in TIER_FILL:
                cell.fill = TIER_FILL[value]
                cell.font = Font(bold=True)

    ws.freeze_panes = "A2"
    _set_auto_widths(ws)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def export_to_bytes(session: AsyncSession) -> bytes:
    """High-level helper used by the FastAPI route."""
    rows = await build_latest_scores_view(session)
    return render_workbook(rows)


def filter_for_outreach(rows: list[dict]) -> list[dict]:
    """Outreach gate: only Hot + Hot-leaning Warm pass; competitor/Cold never do."""
    settings = get_settings()
    auto = settings.auto_outreach_tier_set
    return [
        r for r in rows
        if r["tier"] in auto and not r["is_competitor"]
    ]
