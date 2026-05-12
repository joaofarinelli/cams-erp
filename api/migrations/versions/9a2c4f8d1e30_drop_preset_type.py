"""drop preset_type from rules

Revision ID: 9a2c4f8d1e30
Revises: 12f25173a198
Create Date: 2026-05-06 13:30:00

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "9a2c4f8d1e30"
down_revision = "12f25173a198"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make custom_prompt NOT NULL with empty-string default for any existing
    # rows lacking one (we'll backfill from preset_type when available).
    op.execute(
        """
        UPDATE rules SET custom_prompt = preset_type::text
        WHERE custom_prompt IS NULL OR custom_prompt = ''
        """
    )
    op.alter_column("rules", "custom_prompt", existing_type=sa.String(4000), nullable=False)
    op.drop_column("rules", "preset_type")
    op.execute("DROP TYPE IF EXISTS preset_type")


def downgrade() -> None:
    preset_enum = sa.Enum("cash_register", "kitchen_consumption", "retail_shelf", name="preset_type")
    preset_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "rules",
        sa.Column("preset_type", preset_enum, nullable=False, server_default="cash_register"),
    )
    op.alter_column("rules", "custom_prompt", existing_type=sa.String(4000), nullable=True)
