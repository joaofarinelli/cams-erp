"""add policy_versions and consent_log tables for LGPD C.1

Revision ID: g4h6i8j0k2l4
Revises: f3g5h7i9j1k3
Create Date: 2026-05-12 00:00:00

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "g4h6i8j0k2l4"
down_revision = "f3g5h7i9j1k3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_versions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("doc_type", sa.String(32), nullable=False),
        sa.Column("version", sa.String(16), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "consent_log",
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
            index=True,
        ),
        sa.Column(
            "policy_version_id",
            sa.Integer,
            sa.ForeignKey("policy_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("doc_type", sa.String(32), nullable=False),
        sa.Column("version", sa.String(16), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.add_column("users", sa.Column("policy_version", sa.String(16), nullable=True))

    op.execute("""
INSERT INTO policy_versions (doc_type, version, effective_at)
VALUES
  ('privacy', 'v1.0', '2026-05-12 00:00:00+00'),
  ('terms', 'v1.0', '2026-05-12 00:00:00+00')
""")


def downgrade() -> None:
    op.drop_table("consent_log")
    op.drop_table("policy_versions")
    op.drop_column("users", "policy_version")
