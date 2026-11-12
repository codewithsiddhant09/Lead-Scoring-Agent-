"""initial lead + scoring + outcomes schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-09 13:55:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("headline", sa.String(512)),
        sa.Column("current_position", sa.String(255)),
        sa.Column("current_company", sa.String(255)),
        sa.Column("country", sa.String(120)),
        sa.Column("about", sa.Text),
        sa.Column("open_to_work", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "lead_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("authority_score", sa.Integer, nullable=False),
        sa.Column("fit_score", sa.Integer, nullable=False),
        sa.Column("intent_score", sa.Integer, nullable=False),
        sa.Column("reachability_score", sa.Integer, nullable=False),
        sa.Column("blended_score", sa.Numeric(5, 1), nullable=False),
        sa.Column("tier", sa.String(32), nullable=False),
        sa.Column("is_competitor", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("disqualify_reason", sa.Text),
        sa.Column("technical_founder", sa.Boolean),
        sa.Column("company_stage", sa.String(32)),
        sa.Column("industry_match", sa.String(255)),
        sa.Column("notes", sa.Text),
        sa.Column("scoring_model", sa.String(64), nullable=False),
        sa.Column("scoring_config_version", sa.String(32), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lead_scores_lead_id", "lead_scores", ["lead_id"])
    op.create_index("ix_lead_scores_tier", "lead_scores", ["tier"])
    op.create_index("ix_lead_scores_scored_at", "lead_scores", ["scored_at"])

    op.create_table(
        "lead_outcomes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contacted_at", sa.DateTime(timezone=True)),
        sa.Column("contact_channel", sa.String(32)),
        sa.Column("replied", sa.Boolean),
        sa.Column("replied_at", sa.DateTime(timezone=True)),
        sa.Column("converted", sa.Boolean),
        sa.Column("deal_value", sa.Numeric(12, 2)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lead_outcomes_lead_id", "lead_outcomes", ["lead_id"])

    op.create_table(
        "needs_review",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_tier", sa.String(32), nullable=False),
        sa.Column("new_tier", sa.String(32), nullable=False),
        sa.Column("previous_score_id", postgresql.UUID(as_uuid=True)),
        sa.Column("new_score_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reason", sa.String(255), server_default="tier disagreement", nullable=False),
        sa.Column("resolved", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_needs_review_lead_id", "needs_review", ["lead_id"])


def downgrade() -> None:
    op.drop_index("ix_needs_review_lead_id", table_name="needs_review")
    op.drop_table("needs_review")
    op.drop_index("ix_lead_outcomes_lead_id", table_name="lead_outcomes")
    op.drop_table("lead_outcomes")
    op.drop_index("ix_lead_scores_scored_at", table_name="lead_scores")
    op.drop_index("ix_lead_scores_tier", table_name="lead_scores")
    op.drop_index("ix_lead_scores_lead_id", table_name="lead_scores")
    op.drop_table("lead_scores")
    op.drop_table("leads")
