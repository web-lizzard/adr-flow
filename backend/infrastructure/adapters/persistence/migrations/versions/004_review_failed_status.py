"""review_failed status migration

Revision ID: 004_review_failed
Revises: 003_review_error
Create Date: 2026-07-05

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_review_failed"
down_revision: str | Sequence[str] | None = "003_review_error"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE adrs
        SET status = 'review_failed',
            review_error = (
                review_error - 'code'
                || jsonb_build_object(
                    'kind',
                    COALESCE(
                        review_error->>'kind',
                        CASE review_error->>'code'
                            WHEN 'retryable_internal_error'
                                THEN 'retryable_internal_error'
                            WHEN 'internal_error' THEN 'internal_error'
                            ELSE 'internal_error'
                        END
                    )
                )
            )
        WHERE status = 'in_review'
          AND review_error IS NOT NULL
          AND (review_error->>'kind') IS NULL
        """
    )


def downgrade() -> None:
    # Best-effort: cannot restore exact pre-migration state for legacy payloads.
    op.execute(
        """
        UPDATE adrs
        SET status = 'in_review',
            review_error = review_error - 'kind'
        WHERE status = 'review_failed'
          AND review_error IS NOT NULL
          AND review_error->>'kind' IS NOT NULL
        """
    )
