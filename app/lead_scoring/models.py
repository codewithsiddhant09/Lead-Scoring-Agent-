"""Pydantic models for the lead-scoring module."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CompanyStage(str, Enum):
    SOLO = "Solo"
    STARTUP = "Startup"
    SMB = "SMB"
    SCALEUP = "Scaleup"
    ENTERPRISE = "Enterprise"
    UNKNOWN = "Unknown"


class Tier(str, Enum):
    HOT = "Hot"
    HOT_LEANING_WARM = "Hot-leaning Warm"
    WARM = "Warm"
    COLD = "Cold"


class LeadInput(BaseModel):
    """Normalized lead record fed into scoring (post-Apify + post-enrichment)."""

    model_config = ConfigDict(extra="ignore")

    lead_id: UUID
    full_name: str
    headline: str = ""
    current_position: str = ""
    current_company: str = ""
    company_websites: list[str] = Field(default_factory=list)
    country: str = ""
    about: str = ""
    top_skills: list[str] = Field(default_factory=list)
    open_to_work: bool = False
    hiring: bool = False
    connections: int | None = None
    followers: int | None = None
    emails: list[str] = Field(default_factory=list)
    email_statuses: list[str] = Field(default_factory=list)  # valid / invalid / catch_all / unknown
    email_quality_scores: list[float | None] = Field(default_factory=list)  # 0-100
    linkedin_premium: bool = False
    linkedin_verified: bool = False
    linkedin_open_profile: bool = False
    linkedin_url: str | None = None


class PrefilterResult(BaseModel):
    disqualified: bool
    reason: str | None = None
    skip_llm: bool = False


class ScoringResult(BaseModel):
    """Final scoring output — one row per lead, ready for persistence."""

    lead_id: UUID
    authority_score: int = Field(ge=0, le=100)
    fit_score: int = Field(ge=0, le=100)
    intent_score: int = Field(ge=0, le=100)
    reachability_score: int = Field(ge=0, le=100)
    blended_score: float
    tier: Tier
    is_competitor: bool = False
    disqualify_reason: str | None = None
    technical_founder: bool = False
    company_stage: CompanyStage = CompanyStage.UNKNOWN
    industry_match: str | None = None
    notes: str = ""
    scoring_model: str
    scoring_config_version: str
    scored_at: datetime = Field(default_factory=lambda: datetime.utcnow())

    # Raw helpful diagnostics (not persisted in DB; surfaced in logs/exports)
    authority_reasoning: str | None = None
    intent_signals: list[str] = Field(default_factory=list)
    competitor_reason: str | None = None
    function_bucket: str | None = None
    company_size: str | None = None
    buying_needs: list[str] = Field(default_factory=list)


class LeadScoreRow(BaseModel):
    """ORM-shaped row that the persistence layer writes into lead_scores."""

    lead_id: UUID
    authority_score: int
    fit_score: int
    intent_score: int
    reachability_score: int
    blended_score: float
    tier: str
    is_competitor: bool
    disqualify_reason: str | None
    technical_founder: bool | None
    company_stage: str | None
    industry_match: str | None
    notes: str | None
    scoring_model: str
    scoring_config_version: str


class CommandEnvelope(BaseModel):
    """Wrapper used for tool-use extraction from Claude responses."""

    raw: dict[str, Any]


# ---- JSON schema for the Claude tool ----------------------------------------
SCORING_TOOL: dict[str, Any] = {
    "name": "score_lead",
    "description": (
        "Score a B2B lead for TechGropse's custom software outsourcing ICP. "
        "Output four 0-100 axis scores plus a competitor flag and company stage."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "authority_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Base authority (title/seniority) before the function multiplier.",
            },
            "authority_reasoning": {"type": "string"},
            "fit_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "How well the company matches the target ICP (industry + company size 50-1000 + plausible software need).",
            },
            "industry_match": {
                "type": "string",
                "description": "Free-text industry tag, e.g. 'Fintech - payments infrastructure' or 'Edtech - K-12 SaaS'.",
            },
            "intent_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Explicit buying/building signals: custom web/app dev, iOS mobile, website revamp, staff augmentation, hiring engineers, digital transformation.",
            },
            "intent_signals": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short quoted phrases that drove the intent score.",
            },
            "company_size": {
                "type": ["string", "null"],
                "description": "Estimated employee count or range if mentioned in the bio, e.g. '50-200' or '500'. null if unknown.",
            },
            "buying_needs": {
                "type": "array",
                "items": {"type": "string"},
                "enum": ["custom_web_app", "ios_mobile", "website_revamp", "staff_augmentation", "other"],
                "description": "Specific buying needs detected in the profile. Empty array if none detected.",
            },
            "is_competitor": {
                "type": "boolean",
                "description": "True if this is a software/dev agency, freelancer collective, or IT services firm.",
            },
            "competitor_reason": {
                "type": ["string", "null"],
                "description": "One-line justification when is_competitor=true; null otherwise.",
            },
            "technical_founder": {"type": "boolean"},
            "company_stage": {
                "type": "string",
                "enum": [s.value for s in CompanyStage],
            },
            "notes": {
                "type": "string",
                "description": "1-2 sentence qualification summary.",
            },
        },
        "required": [
            "authority_score",
            "fit_score",
            "intent_score",
            "is_competitor",
            "technical_founder",
            "company_stage",
            "notes",
            "company_size",
            "buying_needs",
        ],
    },
}


SYSTEM_PROMPT = """You are a B2B lead-scoring assistant for TechGropse, a custom software / AI development agency.

TechGropse's ICP:
- Non-technical founders / decision-makers at companies that need custom web & app development,
  iOS mobile apps, website revamps, or staff augmentation.
- Target industries: Fintech, Real Estate, Edtech, Healthcare, Manufacturing & Logistics,
  Retail & E-commerce.
- Target company size: 50 to 1,000 employees (mid-market; not solo founders, not enterprise).
- Explicitly EXCLUDED: software / dev agencies, freelancer collectives, IT consultancies,
  QA shops, staff augmentation firms, and any company that builds software for clients as its
  own product.

You will be given a lead's structured profile. Output a `score_lead` tool call with:
- authority_score (0-100): base on title and seniority BEFORE function multiplier is applied.
- fit_score (0-100): industry fit (one of the 6 target industries) + company size fit
  (50-1000 employees) + plausibility of a custom-software need.
- intent_score (0-100): explicit buying/building signals in the bio. Look for: custom web/app
  development needs, iOS mobile app projects, website revamp/rebuild, staff augmentation,
  hiring engineers, digital transformation, funding rounds, "looking for a dev team",
  "we need to build", modernization language. 0 if none.
- is_competitor + competitor_reason: independent of any keyword pre-filter; flag anything that looks
  like a dev shop, agency, freelance collective, IT consultancy, QA/testing shop, or staff
  augmentation firm.
- technical_founder: true only if the founder is personally technical AND the company has no separate
  CTO/VP Eng.
- company_stage: best guess from the available data.
- notes: a 1-2 sentence qualification summary you would show to a human reviewer.

Be honest. A 0 is a valid score when no signals are present. Do not invent signals.
"""


def user_message_for(lead: LeadInput) -> str:
    """Serialize a LeadInput into a compact user message for Claude."""
    return (
        "Score this lead against TechGropse's ICP:\n"
        f"- Name: {lead.full_name}\n"
        f"- Headline: {lead.headline}\n"
        f"- Current Position: {lead.current_position}\n"
        f"- Current Company: {lead.current_company}\n"
        f"- Country: {lead.country}\n"
        f"- Open To Work: {lead.open_to_work}\n"
        f"- Hiring: {lead.hiring}\n"
        f"- Top Skills: {', '.join(lead.top_skills)}\n"
        f"- About: {lead.about}\n"
        f"- Company Websites: {', '.join(lead.company_websites)}\n"
        f"- LinkedIn Premium/Verified/Open: "
        f"{lead.linkedin_premium}/{lead.linkedin_verified}/{lead.linkedin_open_profile}\n"
        "\n"
        "Target industries: Fintech, Real Estate, Edtech, Healthcare, Manufacturing & Logistics, "
        "Retail & E-commerce.\n"
        "Target company size: 50-1000 employees.\n"
        "Buying needs to detect: custom web & app development, iOS mobile, website revamp, "
        "staff augmentation.\n"
    )
