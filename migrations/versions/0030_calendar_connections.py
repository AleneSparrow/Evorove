"""Tenant Google Calendar grants plus booking<->event mirror rows.

Revision ID: 0030
Revises: 0029
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calendar_connections",
        sa.Column("business_id", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("calendar_id", sa.String(255), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scopes", sa.String(255), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("business_id", name="pk_calendar_connections"),
        sa.CheckConstraint("provider = 'google'", name="ck_calendar_connections_provider"),
    )
    op.create_table(
        "calendar_event_links",
        sa.Column("business_id", sa.String(128), nullable=False),
        sa.Column("booking_id", sa.String(128), nullable=False),
        sa.Column("google_event_id", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("booking_id", name="pk_calendar_event_links"),
    )
    op.create_index(
        "ix_calendar_event_links_business",
        "calendar_event_links",
        ["business_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_calendar_event_links_business", table_name="calendar_event_links")
    op.drop_table("calendar_event_links")
    op.drop_table("calendar_connections")
