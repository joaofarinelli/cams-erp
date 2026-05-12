"""add billing columns to users + usage_monthly table

Revision ID: c7e9f1b3d5g7
Revises: b5d7f9c1e3a5
Create Date: 2026-05-12 19:30:00

"""
from __future__ import annotations

from datetime import timedelta

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "c7e9f1b3d5g7"
down_revision = "b5d7f9c1e3a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "tier",
            sa.String(length=16),
            nullable=False,
            server_default="trial",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "trial_ends_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "stripe_customer_id",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "stripe_subscription_id",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "subscription_status",
            sa.String(length=24),
            nullable=True,
        ),
    )

    # Backfill trial_ends_at for existing users so they're not immediately
    # locked out by the trial expiry cron when it ships.
    op.execute(
        "UPDATE users SET trial_ends_at = now() + INTERVAL '30 days' "
        "WHERE trial_ends_at IS NULL"
    )

    op.create_table(
        "usage_monthly",
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("events_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vlm_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vlm_cascade_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vlm_tokens_in", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("vlm_tokens_out", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("alerts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_gb_hours", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("owner_id", "month", name="pk_usage_monthly"),
    )


def downgrade() -> None:
    op.drop_table("usage_monthly")
    op.drop_column("users", "subscription_status")
    op.drop_column("users", "stripe_subscription_id")
    op.drop_column("users", "stripe_customer_id")
    op.drop_column("users", "trial_ends_at")
    op.drop_column("users", "tier")
