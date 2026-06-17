"""add review_error metadata column

Revision ID: 003_review_error
Revises: 002_adrs_title_unique
Create Date: 2026-06-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_review_error"
down_revision: str | Sequence[str] | None = "002_adrs_title_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "adrs",
        sa.Column(
            "review_error",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("adrs", "review_error")
