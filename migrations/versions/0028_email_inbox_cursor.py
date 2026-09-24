"""Remember the last IMAP UID read from each business mailbox (roadmap step 16).

Revision ID: 0028
Revises: 0027
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("email_connections", sa.Column("imap_last_uid", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("email_connections", "imap_last_uid")
