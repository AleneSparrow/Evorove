"""Addresses that unsubscribed from a business's cold email (roadmap step 15).

Revision ID: 0027
Revises: 0026
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_suppressions",
        sa.Column("business_id", sa.String(128), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("suppressed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("business_id", "email"),
    )


def downgrade() -> None:
    op.drop_table("email_suppressions")
