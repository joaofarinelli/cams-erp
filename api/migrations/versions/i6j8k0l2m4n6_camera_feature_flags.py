"""add face_recognition_enabled, audio_enabled, retention_days to cameras (LGPD C.3)

Revision ID: i6j8k0l2m4n6
Revises: h5i7j9k1l3m5
Create Date: 2026-05-12 00:00:00

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "i6j8k0l2m4n6"
down_revision = "h5i7j9k1l3m5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cameras",
        sa.Column(
            "face_recognition_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "cameras",
        sa.Column(
            "audio_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "cameras",
        sa.Column(
            "retention_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("7"),
        ),
    )


def downgrade() -> None:
    op.drop_column("cameras", "retention_days")
    op.drop_column("cameras", "audio_enabled")
    op.drop_column("cameras", "face_recognition_enabled")
