"""user soft-delete: add deleted_at and deletion_reason

Revision ID: f3g5h7i9j1k3
Revises: e2f4g6h8i0j2
Create Date: 2026-05-12 21:00:00

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "f3g5h7i9j1k3"
down_revision = "e2f4g6h8i0j2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("deletion_reason", sa.String(500), nullable=True))
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_column("users", "deletion_reason")
    op.drop_column("users", "deleted_at")
