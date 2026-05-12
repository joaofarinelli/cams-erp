"""add consent_attested_at and consent_attested_by_user_id to cameras (LGPD C.2)

Revision ID: h5i7j9k1l3m5
Revises: g4h6i8j0k2l4
Create Date: 2026-05-12 00:00:00

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision = "h5i7j9k1l3m5"
down_revision = "g4h6i8j0k2l4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cameras",
        sa.Column("consent_attested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cameras",
        sa.Column(
            "consent_attested_by_user_id",
            PGUUID(as_uuid=True),
            nullable=True,
        ),
    )
    # Backfill: legacy cameras are treated as having been attested at creation time
    op.execute("UPDATE cameras SET consent_attested_at = created_at WHERE consent_attested_at IS NULL")


def downgrade() -> None:
    op.drop_column("cameras", "consent_attested_by_user_id")
    op.drop_column("cameras", "consent_attested_at")
