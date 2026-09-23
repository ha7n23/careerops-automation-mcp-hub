"""Synchronise pending review actions.

Revision ID: 198e093819dd
Revises: b2df53836a53
Create Date: 2026-09-23 14:34:22.347223

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "198e093819dd"
down_revision: str | Sequence[str] | None = "b2df53836a53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Backfill review actions and enforce one pending review per application."""

    # Preserve the oldest pending review action and cancel accidental duplicates.
    op.execute(
        sa.text(
            """
            WITH ranked_actions AS (
                SELECT
                    action_id,
                    row_number() OVER (
                        PARTITION BY application_id
                        ORDER BY created_at, action_id
                    ) AS position
                FROM action_items
                WHERE status = 'pending'
                  AND action_type = 'review_cv'
            )
            UPDATE action_items AS action
            SET status = 'cancelled'
            FROM ranked_actions AS ranked
            WHERE action.action_id = ranked.action_id
              AND ranked.position > 1
            """
        )
    )

    # Repair existing preparations created before action synchronisation existed.
    op.execute(
        sa.text(
            """
            INSERT INTO action_items (
                action_id,
                application_id,
                user_id,
                action_type,
                description,
                status,
                due_at,
                created_at,
                completed_at
            )
            SELECT
                gen_random_uuid(),
                preparation.application_id,
                preparation.user_id,
                'review_cv',
                'Review tailored CV changes for '
                    || application.role_title
                    || ' at '
                    || application.company_name
                    || '.',
                'pending',
                NULL,
                preparation.updated_at,
                NULL
            FROM application_preparations AS preparation
            JOIN job_applications AS application
              ON application.application_id = preparation.application_id
            WHERE preparation.status = 'awaiting_review'
              AND NOT EXISTS (
                  SELECT 1
                  FROM action_items AS action
                  WHERE action.application_id = preparation.application_id
                    AND action.action_type = 'review_cv'
                    AND action.status = 'pending'
              )
            """
        )
    )

    op.create_index(
        "uq_action_items_pending_review_per_application",
        "action_items",
        ["application_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending' AND action_type = 'review_cv'"),
    )


def downgrade() -> None:
    """Remove the pending-review uniqueness index."""

    op.drop_index(
        "uq_action_items_pending_review_per_application",
        table_name="action_items",
    )
