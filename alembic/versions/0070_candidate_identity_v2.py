"""candidate identity v2

Revision ID: 0070_candidate_identity_v2
Revises: 0069_candidate_debit_identity
Create Date: 2026-09-04

Issue #314: the v1 delimiter-concatenated entry id is not sufficient as the
canonical independently-routable serving identity (an actual collision exists:
two distinct tuples render 'text.local:qwen3:8b'). Each catalogue row gains
the canonical versioned opaque identity derived from its structured serving
tuple, plus a NULL-safe deployment key, and persistence enforces uniqueness
over BOTH - so a future regression in id derivation can never let two logical
candidates collapse into one row. The backfill derives from each row's
structured fields, which is provably one-to-one per row; nothing historical
is rewritten.
"""

from __future__ import annotations

import hashlib
import json

import sqlalchemy as sa
from alembic import context, op

# revision identifiers, used by Alembic.
revision = "0070_candidate_identity_v2"
down_revision = "0069_candidate_debit_identity"
branch_labels = None
depends_on = None


def _derive_candidate_identity_v2(
    provider_id: str, model_family: str, model_revision: str, deployment: str | None
) -> str:
    # Frozen copy of the v2 derivation at this migration's point in time: a
    # migration must replay identically forever, so it does not import the
    # live derivation function.
    canonical = json.dumps(
        {
            "v": 2,
            "provider_id": provider_id,
            "model_family": model_family,
            "model_revision": model_revision,
            "deployment": deployment,
        },
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    )
    return "cand2_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def upgrade() -> None:
    op.add_column(
        "model_catalogue_entries",
        sa.Column("candidate_id_v2", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "model_catalogue_entries",
        sa.Column("deployment_key", sa.String(length=128), nullable=False, server_default=""),
    )

    if context.is_offline_mode():
        # Offline SQL generation cannot run the Python backfill; the schema
        # shape is what the offline contract validates. An online upgrade
        # (the deployment path and the smoke's apply mode) backfills below.
        op.create_index(
            "uq_model_catalogue_candidate_id_v2",
            "model_catalogue_entries",
            ["candidate_id_v2"],
            unique=True,
        )
        op.create_index(
            "uq_model_catalogue_serving_tuple",
            "model_catalogue_entries",
            ["provider_id", "model_family", "model_revision", "deployment_key"],
            unique=True,
        )
        return

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT entry_id, provider_id, model_family, model_revision, deployment "
            "FROM model_catalogue_entries"
        )
    ).fetchall()
    for entry_id, provider_id, model_family, model_revision, deployment in rows:
        bind.execute(
            sa.text(
                "UPDATE model_catalogue_entries "
                "SET candidate_id_v2 = :candidate_id_v2, deployment_key = :deployment_key "
                "WHERE entry_id = :entry_id"
            ),
            {
                "candidate_id_v2": _derive_candidate_identity_v2(
                    provider_id, model_family, model_revision, deployment
                ),
                "deployment_key": deployment or "",
                "entry_id": entry_id,
            },
        )

    op.create_index(
        "uq_model_catalogue_candidate_id_v2",
        "model_catalogue_entries",
        ["candidate_id_v2"],
        unique=True,
    )
    op.create_index(
        "uq_model_catalogue_serving_tuple",
        "model_catalogue_entries",
        ["provider_id", "model_family", "model_revision", "deployment_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_model_catalogue_serving_tuple", table_name="model_catalogue_entries")
    op.drop_index("uq_model_catalogue_candidate_id_v2", table_name="model_catalogue_entries")
    op.drop_column("model_catalogue_entries", "deployment_key")
    op.drop_column("model_catalogue_entries", "candidate_id_v2")
