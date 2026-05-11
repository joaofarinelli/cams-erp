"""add edge_yolo_enabled to devices

Revision ID: 9b3c5d7e8f01
Revises: 7f1a3b2c4d5e
Create Date: 2026-05-11 13:00:00

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "9b3c5d7e8f01"
down_revision = "7f1a3b2c4d5e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column(
            "edge_yolo_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("devices", "edge_yolo_enabled")
