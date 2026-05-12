"""add stripe_events_processed table for webhook idempotency

Revision ID: d9e1f3b5g7i9
Revises: c7e9f1b3d5g7
Create Date: 2026-05-12 20:00:00

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "d9e1f3b5g7i9"
down_revision = "c7e9f1b3d5g7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stripe_events_processed",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("stripe_events_processed")
