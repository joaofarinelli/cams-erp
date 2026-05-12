"""add enabled column to cameras

Revision ID: k8l0m2n4o6p8
Revises: j7k9l1m3n5o7
Create Date: 2026-05-12 00:00:00

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "k8l0m2n4o6p8"
down_revision = "j7k9l1m3n5o7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cameras",
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("cameras", "enabled")
