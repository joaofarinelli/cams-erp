"""add lpr/face/audio columns for F4.x scaffolding

Revision ID: b5d7f9c1e3a5
Revises: a2c4d6e8f1a3
Create Date: 2026-05-12 18:00:00

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "b5d7f9c1e3a5"
down_revision = "a2c4d6e8f1a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column(
            "detected_plates",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "events",
        sa.Column(
            "audio_class",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "rules",
        sa.Column(
            "rule_type",
            sa.String(length=32),
            nullable=False,
            server_default="vlm",
        ),
    )
    op.add_column(
        "rules",
        sa.Column(
            "plate_whitelist",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "rules",
        sa.Column(
            "plate_blacklist",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "rules",
        sa.Column(
            "audio_classes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_table(
        "face_enrollments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "embeddings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "photo_s3_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("face_enrollments")
    op.drop_column("rules", "audio_classes")
    op.drop_column("rules", "plate_blacklist")
    op.drop_column("rules", "plate_whitelist")
    op.drop_column("rules", "rule_type")
    op.drop_column("events", "audio_class")
    op.drop_column("events", "detected_plates")
