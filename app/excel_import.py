"""Excel lead import parsing and stable identity helpers."""
from __future__ import annotations

import hashlib
import re
import uuid
from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

try:
    import pandas as pd
except ImportError:  # pragma: no cover - optional legacy .xls support
    pd = None


EXCEL_EXTENSIONS = {".xlsx", ".xls"}


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10_000


def _header_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()


HEADER_ALIASES: dict[str, str] = {
    "full name": "Full Name",
    "full name s": "Full Name",
    "fullname": "Full Name",
    "name": "Full Name",
    "first name": "First Name",
    "firstname": "First Name",
    "first name s": "First Name",
    "given name": "First Name",
    "last name": "Last Name",
    "lastname": "Last Name",
    "last name s": "Last Name",
    "surname": "Last Name",
    "family name": "Last Name",
    "public identifier": "Public Identifier",
    "publicidentifier": "Public Identifier",
    "public identifier s": "Public Identifier",
    "vanity": "Public Identifier",
    "vanity url": "Public Identifier",
    "headline": "Headline",
    "position": "Current Position",
    "current position": "Current Position",
    "company": "Current Company",
    "current company": "Current Company",
    "country": "Country",
    "about": "About",
    "top skills": "Top Skills",
    "skills": "Top Skills",
    "company websites": "Company Website(s)",
    "company website s": "Company Website(s)",
    "company website": "Company Website(s)",
    "open to work": "Open To Work",
    "hiring": "Hiring",
    "connections": "Connections",
    "followers": "Followers",
    "email": "Email(s)",
    "emails": "Email(s)",
    "email s": "Email(s)",
    "email statuses": "Email Status(es)",
    "email status es": "Email Status(es)",
    "email status": "Email Status(es)",
    "email quality scores": "Email Quality Score(s)",
    "email quality score s": "Email Quality Score(s)",
    "email quality score": "Email Quality Score(s)",
    "email quality scores s": "Email Quality Score(s)",
    "email quality score es": "Email Quality Score(s)",
    "premium": "Premium",
    "linkedin premium": "Premium",
    "verified": "Verified",
    "linkedin verified": "Verified",
    "open profile": "Open Profile",
    "linkedin open profile": "Open Profile",
    "linkedin url": "LinkedIn URL",
    "linkedinurl": "LinkedIn URL",
    "linkedin": "LinkedIn URL",
    "profile url": "LinkedIn URL",
    "url": "LinkedIn URL",
    "website": "Company Website(s)",
    "websites": "Company Website(s)",
    "company websites": "Company Website(s)",
    "lead id": "Lead ID",
    "id": "Lead ID",
}


def _scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    return value


def _list_value(value: Any) -> list[str]:
    value = _scalar(value)
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r"[,;\n]", str(value)) if item.strip()]


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"true", "yes", "1", "on", "open", "y"}


def _looks_like_name_slug(value: Any) -> bool:
    """Public Identifier columns sometimes hold a LinkedIn vanity slug that
    doubles as a person-name when nothing else is present (e.g. `john-doe-smith`).
    Return True if the value is a sluggy name candidate rather than a numeric
    ID or a LinkedIn URL fragment."""
    text = str(value or "").strip()
    if not text or len(text) > 80:
        return False
    # Reject anything that looks like a numeric ID, email, URL, or hash.
    if "@" in text or "/" in text or "." in text:
        return False
    if any(ch.isdigit() for ch in text):
        return False
    # At least one letter; allow hyphens (linkedin-slug style).
    return bool(re.match(r"^[A-Za-z][A-Za-z\-]+$", text))


def _derive_full_name(payload: dict[str, Any]) -> str:
    """Build a canonical Full Name from any combination of name columns.

    Priority:
      1. Existing `Full Name` if non-empty.
      2. `First Name` + `Last Name` joined with a single space.
      3. `First Name` alone (trimmed).
      4. `Last Name` alone (trimmed).
      5. `Public Identifier` if it looks like a name slug (no digits, no '@',
         no slashes, no dots).
    Returns an empty string when nothing usable is present so the row-level
    validator can flag the row with a clear "Full Name is required" message.
    """
    existing = str(payload.get("Full Name") or "").strip()
    if existing:
        return re.sub(r"\s+", " ", existing)

    first = str(payload.get("First Name") or "").strip()
    last = str(payload.get("Last Name") or "").strip()
    if first and last:
        return f"{first} {last}"
    if first:
        return first
    if last:
        return last

    slug = payload.get("Public Identifier")
    if _looks_like_name_slug(slug):
        return str(slug).strip().replace("-", " ").title()

    return ""


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert workbook headers and cells to the canonical Apify-shaped payload."""
    normalized: dict[str, Any] = {}
    for raw_key, value in row.items():
        canonical = HEADER_ALIASES.get(_header_key(raw_key))
        if canonical:
            normalized[canonical] = _scalar(value)

    for key in ("Company Website(s)", "Top Skills", "Email(s)", "Email Status(es)"):
        if key in normalized:
            normalized[key] = _list_value(normalized[key])
    for key in ("Open To Work", "Hiring", "Premium", "Verified", "Open Profile"):
        if key in normalized:
            normalized[key] = _parse_bool(normalized[key])

    # Synthesize Full Name from First Name / Last Name / Public Identifier when
    # the workbook doesn't carry a combined name column. The row-level
    # validator downstream only needs a non-empty `Full Name`, so deriving
    # here keeps the Apify profile-scraper exports (split first/last columns)
    # importable without manual edits.
    derived = _derive_full_name(normalized)
    if derived:
        normalized["Full Name"] = derived

    return normalized


def source_key_for(payload: dict[str, Any]) -> str:
    """Build a stable, namespaced identity for repeated imports."""
    explicit = str(payload.get("Lead ID") or "").strip()
    if explicit:
        try:
            return f"id:{uuid.UUID(explicit)}"
        except ValueError:
            return f"source-id:{explicit.lower()}"

    # LinkedIn URL is the strongest natural identity for LinkedIn-sourced
    # leads — prefer it over email / name-company hash so cross-tool joins
    # (Leadbizz deterministic + Lead Scoring LLM) are deterministic.
    linkedin = (
        payload.get("LinkedIn URL")
        or payload.get("linkedin_url")
        or payload.get("linkedinUrl")
        or ""
    ).strip()
    if linkedin:
        return f"linkedin:{linkedin.lower()}"

    emails = [e.lower() for e in payload.get("Email(s)", []) if e]
    if emails:
        return f"email:{emails[0]}"

    name = re.sub(r"\s+", " ", str(payload.get("Full Name") or "").strip().lower())
    company = re.sub(r"\s+", " ", str(payload.get("Current Company") or "").strip().lower())
    raw = f"{name}|{company}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"name-company:{digest}"


def parse_workbook(content: bytes, filename: str = "upload.xlsx") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse first worksheet, returning (valid canonical rows, row errors)."""
    suffix = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix not in EXCEL_EXTENSIONS:
        raise ValueError("Only .xlsx or .xls files are supported")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")
    if suffix == ".xls":
        if pd is None:
            raise ValueError("Legacy .xls files require pandas and xlrd; save the file as .xlsx")
        try:
            frame = pd.read_excel(BytesIO(content), sheet_name=0)
        except Exception as exc:
            raise ValueError("The uploaded .xls file could not be read") from exc
        rows = frame.where(frame.notna(), None).to_dict(orient="records")
        valid: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for row_number, raw in enumerate(rows, start=2):
            payload = normalize_row(raw)
            if not any(value not in (None, "") for value in raw.values()):
                continue
            if not str(payload.get("Full Name") or "").strip():
                errors.append({"row": row_number, "message": "Full Name is required"})
            else:
                valid.append(payload)
        return valid, errors

    # Modern .xlsx path below uses openpyxl.
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")

    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except (InvalidFileException, OSError, ValueError) as exc:
        raise ValueError("The uploaded file is not a readable .xlsx workbook") from exc

    worksheet = workbook.active
    headers = next(worksheet.iter_rows(values_only=True), None)
    if not headers:
        raise ValueError("Workbook is empty")

    mapped_headers = [HEADER_ALIASES.get(_header_key(h)) for h in headers]
    # A name is required to identify the row, but the source workbook may
    # carry it as a combined "Full Name" column or split across "First Name"
    # / "Last Name" (Apify profile-scraper export). "Public Identifier"
    # counts as a name proxy only when it looks like a vanity slug.
    name_sources = {"Full Name", "First Name", "Last Name", "Public Identifier"}
    if not any(h in name_sources for h in mapped_headers):
        raise ValueError(
            "Workbook must contain at least one of: Full Name, First Name + Last Name, "
            "or Public Identifier"
        )

    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for excel_row, values in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
        if excel_row > MAX_ROWS + 1:
            errors.append({"row": excel_row, "message": f"Maximum of {MAX_ROWS} rows exceeded"})
            break
        if not any(value not in (None, "") for value in values):
            continue
        raw = {headers[i]: values[i] for i in range(len(headers))}
        payload = normalize_row(raw)
        if not str(payload.get("Full Name") or "").strip():
            errors.append({"row": excel_row, "message": "Full Name is required"})
            continue
        valid.append(payload)

    workbook.close()
    return valid, errors
