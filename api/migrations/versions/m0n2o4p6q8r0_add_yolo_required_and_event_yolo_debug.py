"""add yolo_required to rules + yolo_max_conf/vlm_skipped_reason to events

Revision ID: m0n2o4p6q8r0
Revises: l9m1n3o5p7q9
Create Date: 2026-05-12 21:00:00

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "m0n2o4p6q8r0"
down_revision = "l9m1n3o5p7q9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rules",
        sa.Column(
            "yolo_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "events",
        sa.Column("yolo_max_conf", sa.Float(), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("vlm_skipped_reason", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("events", "vlm_skipped_reason")
    op.drop_column("events", "yolo_max_conf")
    op.drop_column("rules", "yolo_required")
