"""add agent_version to devices

Revision ID: l9m1n3o5p7q9
Revises: k8l0m2n4o6p8
Create Date: 2026-05-12 00:00:00

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "l9m1n3o5p7q9"
down_revision = "k8l0m2n4o6p8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("agent_version", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("devices", "agent_version")
