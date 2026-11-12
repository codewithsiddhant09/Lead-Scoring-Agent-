"""add stable source key for Excel lead imports

Revision ID: 0002_add_lead_source_key
Revises: 0001_initial
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_add_lead_source_key"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("source_key", sa.String(length=512), nullable=True))
    op.create_index("ix_leads_source_key", "leads", ["source_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_leads_source_key", table_name="leads")
    op.drop_column("leads", "source_key")
