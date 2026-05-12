"""data_export_requests table

Revision ID: j7k9l1m3n5o7
Revises: i6j8k0l2m4n6
Create Date: 2026-05-12 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "j7k9l1m3n5o7"
down_revision = "i6j8k0l2m4n6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_export_requests",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("s3_key", sa.String(512), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
    )
    op.create_index("ix_data_export_requests_user_id", "data_export_requests", ["user_id"])
    op.create_index("ix_data_export_requests_requested_at", "data_export_requests", ["requested_at"])


def downgrade() -> None:
    op.drop_index("ix_data_export_requests_requested_at", table_name="data_export_requests")
    op.drop_index("ix_data_export_requests_user_id", table_name="data_export_requests")
    op.drop_table("data_export_requests")
