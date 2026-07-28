from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from scripts.generate_rfc0002_idea_explanation_proof import (  # noqa: E402
    IdeaExplanationProofError,
    build_rfc0002_idea_explanation_proof,
    main,
    write_proof_artifact,
)


def test_rfc0002_idea_explanation_proof_preserves_live_provider_blockers() -> None:
    proof = build_rfc0002_idea_explanation_proof()

    assert proof["schema_version"] == "lotus-ai.rfc0002.idea-explanation-workflow-proof.v1"
    assert proof["contract_path"] == (
        "contracts/rfc-0002/lotus-ai-idea-explanation-workflow-proof.v1.json"
    )
    assert proof["proof_status"] == "LOCAL_DEV_PARTIAL_BLOCKED"
    assert proof["workflow_pack"] == {
        "pack_id": "idea_explanation.pack",
        "pack_version": "v1",
        "registration_ref": "idea_explanation.pack@v1",
        "workflow_surface": "idea-explanation-evidence",
        "workflow_authority_owner": "lotus-idea",
        "caller_app": "lotus-idea",
    }
    assert proof["execution"]["runtime_state"] == "COMPLETED"
    assert proof["execution"]["review_state"] == "ACCEPTED"
    assert proof["execution"]["review_required"] is True
    assert proof["execution"]["supportability_status"] == "READY"
    assert proof["execution"]["stubbed"] is True
    assert proof["source_lineage"] == {
        "no_raw_payloads": True,
        "source_authority_policy_present": True,
        "source_event_count": 2,
        "idea_lineage_present": True,
        "idea_source_ref_count": 2,
        "idea_source_signal_count": 3,
        "evidence_hash_present": True,
    }
    assert proof["attestation"]["reason_code"] == "model_risk_not_approved"
    assert proof["provider_retention"]["reason_code"] == "provider_execution_not_live"
    assert "signed_workflow_run_attestation_for_non_stub_run" in proof["blockers_preserved"]
    assert "provider_native_retention_or_deletion_confirmation" in proof["blockers_preserved"]


def test_rfc0002_idea_explanation_proof_artifact_is_source_safe(tmp_path: Path) -> None:
    output_path = tmp_path / "proof.json"
    proof = build_rfc0002_idea_explanation_proof()

    write_proof_artifact(proof, output_path)

    written = json.loads(output_path.read_text(encoding="utf-8"))
    serialized = json.dumps(written, sort_keys=True)
    assert "PB_SG_GLOBAL_BAL_001" not in serialized
    assert '"raw_payload"' not in serialized
    assert '"raw_prompt"' not in serialized
    assert '"raw_provider_output"' not in serialized
    assert (
        written["validation_command"] == "python scripts/generate_rfc0002_idea_explanation_proof.py"
    )


def test_rfc0002_idea_explanation_live_provider_mode_fails_until_external_proof_exists() -> None:
    assert main(["--require-live-provider"]) == 1


def test_source_safe_validator_rejects_sensitive_marker() -> None:
    from scripts.generate_rfc0002_idea_explanation_proof import _validate_source_safe_proof

    try:
        _validate_source_safe_proof(
            {
                "schema_version": "lotus-ai.rfc0002.idea-explanation-workflow-proof.v1",
                "leak": "PB_SG_GLOBAL_BAL_001",
            }
        )
    except IdeaExplanationProofError as exc:
        assert "forbidden raw or client-specific marker" in str(exc)
    else:
        raise AssertionError("Expected sensitive proof marker to fail closed.")
