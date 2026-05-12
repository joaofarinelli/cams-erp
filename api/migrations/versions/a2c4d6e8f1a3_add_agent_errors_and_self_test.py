"""add agent_errors table + devices.last_self_test_json

Revision ID: a2c4d6e8f1a3
Revises: 9b3c5d7e8f01
Create Date: 2026-05-12 17:30:00

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "a2c4d6e8f1a3"
down_revision = "9b3c5d7e8f01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column(
            "last_self_test_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_table(
        "agent_errors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("message", sa.String(1024), nullable=False),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column("agent_version", sa.String(32), nullable=True),
        sa.Column(
            "context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_agent_errors_device_occurred",
        "agent_errors",
        ["device_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_errors_device_occurred", table_name="agent_errors")
    op.drop_table("agent_errors")
    op.drop_column("devices", "last_self_test_json")
