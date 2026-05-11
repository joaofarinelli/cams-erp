"""add analysis_intensity to rules

Revision ID: 7f1a3b2c4d5e
Revises: 9a2c4f8d1e30
Create Date: 2026-05-11 12:30:00

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "7f1a3b2c4d5e"
down_revision = "9a2c4f8d1e30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rules",
        sa.Column(
            "analysis_intensity",
            sa.String(length=16),
            nullable=False,
            server_default="normal",
        ),
    )


def downgrade() -> None:
    op.drop_column("rules", "analysis_intensity")
