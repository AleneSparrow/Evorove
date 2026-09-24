"""People from the CRM Cold tab that cycle 2 writes to first.

Revision ID: 0026
Revises: 0025
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outreach_prospects",
        sa.Column("business_id", sa.String(128), nullable=False),
        sa.Column("person_id", sa.String(128), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reason_source", sa.Text(), nullable=False),
        sa.Column("hypothesis_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("skip_reason", sa.String(64), nullable=True),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("outbox_id", sa.String(128), nullable=True),
        sa.Column("approved_by", sa.String(320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("business_id", "person_id"),
        sa.CheckConstraint(
            "status IN ('drafted','approved','sent','skipped','stopped')",
            name="ck_outreach_prospects_status",
        ),
    )
    op.create_index("ix_outreach_prospects_status", "outreach_prospects", ["business_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_outreach_prospects_status", table_name="outreach_prospects")
    op.drop_table("outreach_prospects")
