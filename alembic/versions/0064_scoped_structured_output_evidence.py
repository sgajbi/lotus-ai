"""scoped structured output evidence

Revision ID: 0064_scoped_structured_output_evidence
Revises: 0063_capability_degradations
Create Date: 2026-09-03

Issue #244 correction: the seeder used to set the model-global
supports_structured_output fact from pack approval plus output-contract
existence - evidence that only proves effective structured output for that
pack's governed scope. No production assessment path exists, so every stored
True is seed-derived and over-broad; reset the fact to unknown. Scoped
eligibility now consults the fields that actually carry the evidence
(approved_workflow_pack_ids plus the execution's output-contract key), and
the global fact stays unknown until an assessment proves it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0064_scoped_structured_output_evidence"
down_revision = "0063_capability_degradations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE model_catalogue_entries SET supports_structured_output = NULL"))


def downgrade() -> None:
    # The over-broad claim is deliberately not restorable: downgrading the
    # schema does not re-manufacture evidence. Reseeding under the old code
    # would repopulate it.
    pass
