"""Pain first, then touch: keep the cycle-1 observed pain on the cold prospect.

Revision ID: 0031
Revises: 0030
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("outreach_prospects", sa.Column("observed_pain", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("outreach_prospects", "observed_pain")
