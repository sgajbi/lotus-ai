"""seed prompt rollout candidates

Revision ID: 0017_seed_prompt_rollout_candidates
Revises: 0016_add_prompt_rollout_state_tables
Create Date: 2026-03-23 00:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_seed_prompt_rollout_candidates"
down_revision = "0016_add_prompt_rollout_state_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO prompt_definition_versions (
                task_id,
                prompt_version,
                prompt_kind,
                lifecycle_status,
                management_mode,
                source_reference,
                system_instructions,
                output_contract_notes,
                created_at
            ) VALUES
            (
                'explain.v1',
                'foundation.explain.v2',
                'system',
                'CANDIDATE',
                'MIGRATION_MANAGED',
                'alembic:0017_seed_prompt_rollout_candidates',
                'Explain structured Lotus domain outputs clearly, conservatively, and ground the response in the supplied fields before adding decision-support framing.',
                'Output must remain explanation-oriented, enterprise-safe, non-authoritative, and concise enough for operator review.',
                '2026-03-23T00:30:00+00:00'
            ),
            (
                'knowledge_answer.v1',
                'foundation.knowledge_answer.v2',
                'system',
                'CANDIDATE',
                'MIGRATION_MANAGED',
                'alembic:0017_seed_prompt_rollout_candidates',
                'Answer questions from approved Lotus knowledge sources with explicit citations, call out weak support plainly, and prefer refusal over unsupported synthesis.',
                'Refuse when sources are insufficient or unsupported, and keep the answer operator-reviewable.',
                '2026-03-23T00:30:00+00:00'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE prompt_rollout_state
            SET rollout_mode = 'GOVERNED_CONTROL_ACTIONS',
                runtime_mutation_enabled = TRUE,
                updated_at = '2026-03-23T00:30:00+00:00'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM prompt_definition_versions
            WHERE (task_id = 'explain.v1' AND prompt_version = 'foundation.explain.v2')
               OR (task_id = 'knowledge_answer.v1' AND prompt_version = 'foundation.knowledge_answer.v2')
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE prompt_rollout_state
            SET candidate_prompt_version = NULL,
                previous_active_prompt_version = NULL,
                rollout_mode = 'GOVERNED_STATE_READ_ONLY',
                runtime_mutation_enabled = FALSE,
                updated_at = '2026-03-23T00:00:00+00:00'
            """
        )
    )
