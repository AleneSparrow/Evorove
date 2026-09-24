"""Per-business outreach mailbox for cycle-2 cold email.

Revision ID: 0025
Revises: 0024
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_connections",
        sa.Column("business_id", sa.String(128), nullable=False),
        sa.Column("from_address", sa.String(320), nullable=False),
        sa.Column("from_name", sa.String(255), nullable=False),
        sa.Column("postal_address", sa.String(500), nullable=False),
        sa.Column("smtp_host", sa.String(255), nullable=False),
        sa.Column("smtp_port", sa.Integer(), nullable=False),
        sa.Column("smtp_security", sa.String(16), nullable=False),
        sa.Column("smtp_username", sa.String(320), nullable=False),
        sa.Column("password_encrypted", sa.Text(), nullable=False),
        sa.Column("imap_host", sa.String(255), nullable=True),
        sa.Column("imap_port", sa.Integer(), nullable=True),
        sa.Column("daily_limit", sa.Integer(), nullable=False),
        sa.Column("warmup_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("business_id"),
        sa.CheckConstraint("smtp_security IN ('ssl','starttls')", name="ck_email_connections_security"),
        sa.CheckConstraint("daily_limit BETWEEN 1 AND 500", name="ck_email_connections_daily_limit"),
    )


def downgrade() -> None:
    op.drop_table("email_connections")
