"""ORM models. NOTE: I assume the existing `leads` table uses UUID PKs and the
columns below. Adapt this file to your existing schema if it differs — the
scoring module only requires `leads.id` to be a UUID.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import CHAR, JSON, TypeDecorator
import uuid as _uuid

from app.db import Base


class PortableJSON(TypeDecorator):
    """JSONB on Postgres, JSON on SQLite (test DBs)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class PortableUUID(TypeDecorator):
    """UUID-as-UUID on Postgres, CHAR(36) on SQLite so tests round-trip correctly."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, _uuid.UUID):
            return value
        return _uuid.UUID(str(value))


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    headline: Mapped[str | None] = mapped_column(String(512))
    current_position: Mapped[str | None] = mapped_column(String(255))
    current_company: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(120))
    about: Mapped[str | None] = mapped_column(Text)
    open_to_work: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_payload: Mapped[dict | None] = mapped_column(PortableJSON)
    source_key: Mapped[str | None] = mapped_column(String(512), unique=True, index=True)
    # LinkedIn URL captured at ingest time so Leadbizz can join its
    # deterministic-score rows to the LLM-enriched rows by URL.
    linkedin_url: Mapped[str | None] = mapped_column(String(512), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scores: Mapped[list["LeadScore"]] = relationship(back_populates="lead", cascade="all,delete-orphan")
    outcomes: Mapped[list["LeadOutcome"]] = relationship(back_populates="lead", cascade="all,delete-orphan")


class LeadScore(Base):
    """Append-only scoring history. Never UPDATE existing rows — insert a new row on re-score."""

    __tablename__ = "lead_scores"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )

    authority_score: Mapped[int] = mapped_column(Integer, nullable=False)
    fit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    intent_score: Mapped[int] = mapped_column(Integer, nullable=False)
    reachability_score: Mapped[int] = mapped_column(Integer, nullable=False)
    blended_score: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    is_competitor: Mapped[bool] = mapped_column(Boolean, default=False)
    disqualify_reason: Mapped[str | None] = mapped_column(Text)
    technical_founder: Mapped[bool | None] = mapped_column(Boolean)
    company_stage: Mapped[str | None] = mapped_column(String(32))
    industry_match: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    scoring_model: Mapped[str] = mapped_column(String(64), nullable=False)
    scoring_config_version: Mapped[str] = mapped_column(String(32), nullable=False)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lead: Mapped[Lead] = relationship(back_populates="scores")


class LeadOutcome(Base):
    __tablename__ = "lead_outcomes"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )

    contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contact_channel: Mapped[str | None] = mapped_column(String(32))  # linkedin / email
    replied: Mapped[bool | None] = mapped_column(Boolean)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    converted: Mapped[bool | None] = mapped_column(Boolean)
    deal_value: Mapped[float | None] = mapped_column(Numeric(12, 2))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    lead: Mapped[Lead] = relationship(back_populates="outcomes")


class NeedsReview(Base):
    """Surfaced when a re-score disagrees with the previous stored tier."""

    __tablename__ = "needs_review"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID(), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    new_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_score_id: Mapped[uuid.UUID | None] = mapped_column(PortableUUID())
    new_score_id: Mapped[uuid.UUID | None] = mapped_column(PortableUUID())
    reason: Mapped[str] = mapped_column(String(255), default="tier disagreement")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
