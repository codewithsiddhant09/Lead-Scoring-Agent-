"""add linkedin_url on leads so Leadbizz can join deterministic + LLM scores

Revision ID: 0003_add_lead_linkedin_url
Revises: 0002_add_lead_source_key
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_add_lead_linkedin_url"
down_revision = "0002_add_lead_source_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("linkedin_url", sa.String(length=512), nullable=True))
    op.create_index("ix_leads_linkedin_url", "leads", ["linkedin_url"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_leads_linkedin_url", table_name="leads")
    op.drop_column("leads", "linkedin_url")
