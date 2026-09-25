"""Owner marketing packet: drafts plus an activated snapshot the engine reads.

Revision ID: 0029
Revises: 0028
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "marketing_assets",
        sa.Column("id", sa.String(128), nullable=False),
        sa.Column("business_id", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_marketing_assets"),
        sa.CheckConstraint("kind IN ('notes', 'offer', 'media')", name="ck_marketing_assets_kind"),
    )
    op.create_index(
        "ix_marketing_assets_business_created",
        "marketing_assets",
        ["business_id", "created_at"],
    )
    op.create_table(
        "marketing_guidance",
        sa.Column("business_id", sa.String(128), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot_text", sa.Text(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("business_id", name="pk_marketing_guidance"),
        sa.CheckConstraint("revision > 0", name="ck_marketing_guidance_revision"),
    )


def downgrade() -> None:
    op.drop_table("marketing_guidance")
    op.drop_index("ix_marketing_assets_business_created", table_name="marketing_assets")
    op.drop_table("marketing_assets")
