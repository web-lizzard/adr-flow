"""add active ADR title uniqueness index

Revision ID: 002_adrs_title_unique
Revises: 001_initial
Create Date: 2026-06-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_adrs_title_unique"
down_revision: str | Sequence[str] | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_adrs_active_user_title_ci",
        "adrs",
        ["user_id", sa.text("lower(title)")],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_index("uq_adrs_active_user_title_ci", table_name="adrs")
