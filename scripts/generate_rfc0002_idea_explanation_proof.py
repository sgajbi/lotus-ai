from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from _repo_imports import ensure_repo_src_first  # type: ignore[import-not-found]

REPO_ROOT = ensure_repo_src_first(script_file=__file__)

SCHEMA_VERSION = "lotus-ai.rfc0002.idea-explanation-workflow-proof.v1"
ISSUE_URL = "https://github.com/sgajbi/lotus-ai/issues/122"
CONTRACT_PATH = "contracts/rfc-0002/lotus-ai-idea-explanation-workflow-proof.v1.json"
SENSITIVE_MARKERS = ("PB_SG_GLOBAL_BAL_001",)
FORBIDDEN_PROOF_KEYS = {
    "raw_payload",
    "raw_prompt",
    "raw_provider_output",
    "provider_response",
}


class IdeaExplanationProofError(AssertionError):
    """Raised when the RFC-0002 Idea explanation proof is incomplete or unsafe."""


def build_rfc0002_idea_explanation_proof() -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from app.main import app
    from app.provider_retention_confirmations.store import (
        reset_provider_retention_confirmation_store_cache,
    )
    from app.services.artifact_store import reset_artifact_store_cache
    from app.services.workflow_pack_queue_event_store import (
        reset_workflow_pack_queue_event_store_cache,
    )
    from app.services.workflow_pack_run_store import reset_workflow_pack_run_store_cache
    from app.services.workflow_pack_task_flow_store import (
        reset_workflow_pack_task_flow_store_cache,
    )

    reset_artifact_store_cache()
    reset_workflow_pack_run_store_cache()
    reset_workflow_pack_task_flow_store_cache()
    reset_workflow_pack_queue_event_store_cache()
    reset_provider_retention_confirmation_store_cache()

    client = TestClient(app)
    execute_response = client.post(
        "/platform/workflow-packs/execute",
        json=_idea_explanation_request(),
        headers={"X-Caller-App": "lotus-idea"},
    )
    _expect_http(execute_response.status_code, 200, "Idea explanation execution")
    execution = execute_response.json()
    run = _require_dict(execution, "workflow_pack_run")
    run_id = _require_text(run, "run_id")

    structured_output = _require_dict(
        _require_dict(_require_dict(execution, "execution"), "result"),
        "structured_output",
    )
    _validate_review_gated_output(structured_output)
    _validate_initial_run(run)

    review_response = client.post(
        f"/platform/workflow-packs/runs/{run_id}/review-actions",
        json={
            "action_type": "ACCEPT",
            "caller_app": "lotus-idea",
            "reviewed_by": "idea-reviewer.sg.001",
            "reason": "Accepted for RFC-0002 local owner-repo proof boundary.",
        },
        headers={"X-Caller-App": "lotus-idea"},
    )
    _expect_http(review_response.status_code, 200, "Idea explanation review action")
    reviewed_run = _require_dict(review_response.json(), "run")
    _expect_value(reviewed_run.get("review_state"), "ACCEPTED", "review_state")
    _expect_value(reviewed_run.get("supportability_status"), "READY", "supportability_status")

    consumer_response = client.get(f"/platform/workflow-packs/runs/{run_id}/consumer-view")
    _expect_http(consumer_response.status_code, 200, "Idea explanation consumer view")
    consumer_view = consumer_response.json()
    _validate_consumer_view(consumer_view)

    source_events_response = client.get(f"/platform/workflow-packs/runs/{run_id}/source-events")
    _expect_http(source_events_response.status_code, 200, "Idea explanation source events")
    source_events = source_events_response.json()
    _validate_source_events(source_events)

    attestation_response = client.get(f"/platform/workflow-packs/runs/{run_id}/attestation")
    _expect_http(attestation_response.status_code, 409, "local-dev attestation boundary")
    attestation_problem = attestation_response.json()
    _expect_problem_reason(
        attestation_problem,
        "model_risk_not_approved",
        "local-dev attestation boundary",
    )

    retention_response = client.post(
        f"/platform/provider-operations/workflow-runs/{run_id}/retention-confirmations",
        json={
            "provider_confirmation_ref": "provider-confirmation-rfc0002-local-proof-001",
            "retention_policy_id": "provider-retention-policy.v1",
            "outcome": "NO_PROVIDER_STORAGE",
            "provider_decision_at_utc": "2026-07-28T00:00:00Z",
            "evidence_sha256": "a" * 64,
        },
        headers={
            "X-Caller-App": "lotus-ai-provider-operations",
            "X-Tenant-Id": "tenant-sg-001",
            "Idempotency-Key": "rfc0002-idea-explanation-local-proof-001",
        },
    )
    _expect_http(retention_response.status_code, 409, "local-dev provider retention boundary")
    retention_problem = retention_response.json()
    _expect_problem_reason(
        retention_problem,
        "provider_execution_not_live",
        "local-dev provider retention boundary",
    )

    proof = _build_source_safe_proof(
        run=reviewed_run,
        consumer_view=consumer_view,
        source_events=source_events,
        attestation_problem=attestation_problem,
        retention_problem=retention_problem,
    )
    _validate_source_safe_proof(proof)
    return proof


def write_proof_artifact(proof: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and validate the RFC-0002 local-dev Idea explanation workflow-pack proof."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON artifact path. Defaults to validation-only mode.",
    )
    parser.add_argument(
        "--require-live-provider",
        action="store_true",
        help=(
            "Fail when the generated proof is the local-dev partial proof rather than live-provider "
            "certification evidence."
        ),
    )
    args = parser.parse_args(argv)

    try:
        proof = build_rfc0002_idea_explanation_proof()
        if args.require_live_provider:
            raise IdeaExplanationProofError(
                "Live-provider certification is not proven by the deterministic local-dev proof; "
                "run against an approved non-stub provider, approved model-risk inventory, and "
                "provider-native retention/deletion evidence."
            )
    except IdeaExplanationProofError as exc:
        print(f"RFC-0002 Idea explanation proof failed: {exc}", file=sys.stderr)
        return 1

    if args.output is not None:
        write_proof_artifact(proof, args.output)

    print(
        "RFC-0002 Idea explanation local-dev proof passed "
        f"({proof['workflow_pack']['registration_ref']}; "
        f"{len(proof['blockers_cleared'])} controls proven; "
        f"{len(proof['blockers_preserved'])} blockers preserved)"
    )
    return 0


def _idea_explanation_request() -> dict[str, Any]:
    return {
        "pack_id": "idea_explanation.pack",
        "version": "v1",
        "environment": "DEVELOPMENT",
        "caller_identity_class": "INTERNAL_SERVICE",
        "workflow_surface": "idea-explanation-evidence",
        "task_request": {
            "task_id": "explain.v1",
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": "lotus-idea",
                "correlation_id": "corr-rfc0002-idea-explanation-proof-001",
                "tenant_id": "tenant-sg-001",
            },
            "context": {
                "summary": "Generate a review-gated Idea explanation from redacted source evidence.",
                "payload": _idea_explanation_payload(),
                "source_refs": [
                    "lotus-idea:evidence-packet:idea_evidence_high_cash_001",
                    "lotus-core:positions:PB_SG_GLOBAL_BAL_001:2026-06-25",
                    "lotus-risk:concentration:PB_SG_GLOBAL_BAL_001:2026-06-25",
                ],
            },
            "expected_output_label": "EXPLANATION_ONLY",
        },
    }


def _idea_explanation_payload() -> dict[str, Any]:
    return {
        "redacted_evidence_packet": {
            "candidate_id": "idea_high_cash_001",
            "family": "HIGH_CASH",
            "lifecycle_status": "READY_FOR_REVIEW",
            "review_posture": "ADVISOR_REVIEW_REQUIRED",
            "evidence_packet_id": "idea_evidence_high_cash_001",
            "evidence_content_hash": "sha256:idea-evidence-high-cash-001",
            "supportability": "READY",
            "score_policy_version": "idea-score-policy.v1",
            "score": "0.82",
            "source_signal_count": 3,
            "reason_codes": ["HIGH_CASH_WEIGHT", "BENCHMARK_DRIFT_ATTENTION"],
            "source_refs": [
                {
                    "source_system": "lotus-core",
                    "product_id": "core-position-snapshot",
                    "product_version": "2026.06",
                    "source_id": "PB_SG_GLOBAL_BAL_001:positions:2026-06-25",
                    "content_hash": "sha256:core-position-snapshot-001",
                },
                {
                    "source_system": "lotus-risk",
                    "product_id": "risk-concentration-snapshot",
                    "product_version": "2026.06",
                    "source_id": "PB_SG_GLOBAL_BAL_001:risk:2026-06-25",
                    "content_hash": "sha256:risk-concentration-snapshot-001",
                },
            ],
        },
        "explanation_request": {
            "request_id": "idea-explanation-request-001",
            "workflow_pack_id": "lotus-ai:idea-explanation:v1",
            "workflow_pack_version": "v1",
            "purpose": "unsupported_claim_verification",
            "evaluation_ref": "idea-explanation-eval-pack.v1",
            "audience": "advisor",
            "requested_outputs": [
                "advisor_review_summary",
                "source_evidence_summary",
                "unsupported_claim_check",
            ],
        },
        "supportability": {
            "human_review_required": True,
            "client_ready_publication": "BLOCKED",
            "forbidden_actions": [
                "approve_suitability",
                "contact_client",
                "invent_missing_evidence",
                "make_final_recommendation",
                "place_orders",
            ],
            "unsupported_claims": [
                "client_ready_publication",
                "final_investment_recommendation",
                "suitability_approval",
                "trade_or_order_action",
            ],
        },
    }


def _build_source_safe_proof(
    *,
    run: dict[str, Any],
    consumer_view: dict[str, Any],
    source_events: dict[str, Any],
    attestation_problem: dict[str, Any],
    retention_problem: dict[str, Any],
) -> dict[str, Any]:
    lineage = _require_dict(consumer_view, "lineage")
    idea_lineage = _require_dict(lineage, "idea_lineage")
    provenance = _require_dict(consumer_view, "provenance")
    runtime = _require_dict(consumer_view, "runtime")
    review = _require_dict(consumer_view, "review")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "repository": "lotus-ai",
        "issue_url": ISSUE_URL,
        "rfc": "RFC-0002",
        "slices": ["09", "17"],
        "proof_status": "LOCAL_DEV_PARTIAL_BLOCKED",
        "workflow_pack": {
            "pack_id": run["pack_id"],
            "pack_version": run["pack_version"],
            "registration_ref": run["registration_ref"],
            "workflow_surface": run["workflow_surface"],
            "workflow_authority_owner": run["workflow_authority_owner"],
            "caller_app": run["caller_app"],
        },
        "execution": {
            "runtime_state": runtime["state"],
            "review_state": review["state"],
            "review_required": review["required"],
            "supportability_status": run["supportability_status"],
            "provider_mode": runtime["provider_mode"],
            "stubbed": runtime["stubbed"],
            "artifact_ref_count": len(_require_list(provenance, "artifact_refs")),
            "structured_output_key_count": len(provenance["structured_output_keys"]),
        },
        "source_lineage": {
            "no_raw_payloads": source_events["no_raw_payloads"],
            "source_authority_policy_present": bool(source_events["source_authority_policy"]),
            "source_event_count": source_events["event_count"],
            "idea_lineage_present": True,
            "idea_source_ref_count": idea_lineage["source_ref_count"],
            "idea_source_signal_count": idea_lineage["source_signal_count"],
            "evidence_hash_present": str(idea_lineage["evidence_content_hash"]).startswith(
                "sha256:"
            ),
        },
        "guardrails": {
            "human_review_required": True,
            "client_ready_publication": "BLOCKED",
            "downstream_authority": "BLOCKED",
            "forbidden_actions_enforced": True,
            "unsupported_claims_enforced": True,
            "no_autonomous_advice": True,
        },
        "attestation": {
            "local_dev_status": "NOT_ISSUABLE",
            "http_status": attestation_problem["status"],
            "error_code": attestation_problem["error_code"],
            "reason_code": _problem_reason(attestation_problem),
        },
        "provider_retention": {
            "local_dev_status": "NOT_ISSUABLE",
            "http_status": retention_problem["status"],
            "error_code": retention_problem["error_code"],
            "reason_code": _problem_reason(retention_problem),
        },
        "blockers_cleared": [
            "idea_explanation_workflow_pack_executes_through_governed_http_boundary",
            "idea_explanation_output_is_review_gated_and_not_client_ready",
            "consumer_view_projects_source_safe_idea_lineage",
            "source_events_preserve_no_raw_payload_policy",
            "local_stub_attestation_fails_closed_without_model_risk_approval",
            "local_stub_provider_retention_confirmation_fails_closed_without_live_execution",
        ],
        "blockers_preserved": [
            "approved_non_stub_live_provider_execution",
            "effective_model_risk_inventory_approval_for_live_model",
            "signed_workflow_run_attestation_for_non_stub_run",
            "provider_native_retention_or_deletion_confirmation",
            "bank_or_platform_approval_to_promote_ai_explanation_as_supported_live_capability",
        ],
        "non_claim_boundaries": [
            "This proof does not certify production provider execution.",
            "This proof does not certify provider-native retention or deletion.",
            "This proof does not grant Idea suitability, proposal, rebalance, report, archive, or client-publication authority.",
            "This proof is not downstream Idea consumption proof.",
        ],
        "validation_command": "python scripts/generate_rfc0002_idea_explanation_proof.py",
        "contract_path": CONTRACT_PATH,
    }


def _validate_review_gated_output(output: dict[str, Any]) -> None:
    _expect_value(output.get("workflow_pack_family"), "idea_explanation", "workflow_pack_family")
    _expect_value(output.get("state"), "REVIEW_REQUIRED", "state")
    _expect_value(output.get("client_ready_publication"), "BLOCKED", "client_ready_publication")
    _expect_value(output.get("downstream_authority"), "BLOCKED", "downstream_authority")
    _expect_value(output.get("human_review_required"), True, "human_review_required")
    requested_outputs = set(_require_list(output, "requested_outputs"))
    forbidden_outputs = {"client_message", "trade_or_order", "publish_to_client"}
    if forbidden_outputs.intersection(requested_outputs):
        raise IdeaExplanationProofError("Idea explanation output contains forbidden request scope.")
    for action in ("place_orders", "contact_client", "make_final_recommendation"):
        if action not in _require_list(output, "forbidden_actions"):
            raise IdeaExplanationProofError(f"Missing forbidden action in output: {action}")


def _validate_initial_run(run: dict[str, Any]) -> None:
    _expect_value(run.get("pack_id"), "idea_explanation.pack", "pack_id")
    _expect_value(run.get("pack_version"), "v1", "pack_version")
    _expect_value(run.get("caller_app"), "lotus-idea", "caller_app")
    _expect_value(run.get("workflow_authority_owner"), "lotus-idea", "workflow_authority_owner")
    _expect_value(run.get("runtime_state"), "COMPLETED", "runtime_state")
    _expect_value(run.get("review_state"), "AWAITING_REVIEW", "initial review_state")
    _expect_value(run.get("review_required"), True, "review_required")
    _expect_value(run.get("stubbed"), True, "stubbed")
    if len(_require_list(run, "artifact_refs")) != 1:
        raise IdeaExplanationProofError("Idea explanation run must retain one output artifact ref.")


def _validate_consumer_view(consumer_view: dict[str, Any]) -> None:
    runtime = _require_dict(consumer_view, "runtime")
    review = _require_dict(consumer_view, "review")
    lineage = _require_dict(consumer_view, "lineage")
    provenance = _require_dict(consumer_view, "provenance")
    idea_lineage = _require_dict(lineage, "idea_lineage")
    _expect_value(runtime.get("state"), "COMPLETED", "consumer runtime state")
    _expect_value(runtime.get("stubbed"), True, "consumer stubbed posture")
    _expect_value(review.get("state"), "ACCEPTED", "consumer review state")
    _expect_value(review.get("required"), True, "consumer review requirement")
    _expect_value(lineage.get("pack_id"), "idea_explanation.pack", "consumer lineage pack_id")
    _expect_value(lineage.get("caller_app"), "lotus-idea", "consumer lineage caller_app")
    if not str(idea_lineage.get("evidence_content_hash", "")).startswith("sha256:"):
        raise IdeaExplanationProofError("Consumer view lacks Idea evidence content hash.")
    if idea_lineage.get("source_ref_count") != 2 or idea_lineage.get("source_signal_count") != 3:
        raise IdeaExplanationProofError("Consumer view has unexpected Idea source lineage counts.")
    if len(_require_list(provenance, "artifact_refs")) != 1:
        raise IdeaExplanationProofError(
            "Consumer view must expose exactly one output artifact ref."
        )


def _validate_source_events(source_events: dict[str, Any]) -> None:
    _expect_value(source_events.get("no_raw_payloads"), True, "source event no_raw_payloads")
    _expect_value(source_events.get("event_count"), 2, "source event count")
    policy = _require_text(source_events, "source_authority_policy")
    if "must not reconstruct" not in policy:
        raise IdeaExplanationProofError("Source authority policy must prohibit reconstruction.")
    events = _require_list(source_events, "events")
    event_types = {
        _require_text(_require_dict_from_value(event, "source event"), "event_type")
        for event in events
    }
    if event_types != {"AI_WORKFLOW_PACK_RUN_RECORDED", "AI_WORKFLOW_PACK_REVIEW_STATE_UPDATED"}:
        raise IdeaExplanationProofError(
            f"Source events must include run-recorded and review-state-updated events; got {sorted(event_types)}."
        )
    for event_value in events:
        event = _require_dict_from_value(event_value, "source event")
        _expect_value(event.get("pack_id"), "idea_explanation.pack", "source event pack_id")
        _expect_value(event.get("caller_app"), "lotus-idea", "source event caller_app")
        _expect_value(event.get("redaction_policy"), "NO_RAW_PAYLOADS", "redaction_policy")
        _expect_value(event.get("review_state"), "ACCEPTED", "source event review_state")
        _expect_value(
            event.get("supportability_status"),
            "READY",
            "source event supportability_status",
        )
        if not str(event.get("content_hash", "")).startswith("sha256:"):
            raise IdeaExplanationProofError("Source event must expose a content hash.")


def _validate_source_safe_proof(proof: dict[str, Any]) -> None:
    if proof.get("schema_version") != SCHEMA_VERSION:
        raise IdeaExplanationProofError("Proof schema version mismatch.")
    contract_path = REPO_ROOT / CONTRACT_PATH
    if not contract_path.exists():
        raise IdeaExplanationProofError(f"Proof contract is missing: {CONTRACT_PATH}")
    leaked = _find_sensitive_proof_entries(proof)
    if leaked:
        raise IdeaExplanationProofError(
            "Proof artifact includes forbidden raw or client-specific marker(s): "
            + ", ".join(leaked)
        )


def _find_sensitive_proof_entries(value: Any) -> list[str]:
    leaked: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_PROOF_KEYS:
                leaked.append(key)
            leaked.extend(_find_sensitive_proof_entries(child))
    elif isinstance(value, list):
        for child in value:
            leaked.extend(_find_sensitive_proof_entries(child))
    elif isinstance(value, str):
        leaked.extend(marker for marker in SENSITIVE_MARKERS if marker in value)
    return sorted(set(leaked))


def _expect_http(actual: int, expected: int, label: str) -> None:
    if actual != expected:
        raise IdeaExplanationProofError(f"{label} returned HTTP {actual}; expected {expected}.")


def _expect_problem_reason(problem: dict[str, Any], expected_reason: str, label: str) -> None:
    actual = _problem_reason(problem)
    if actual != expected_reason:
        raise IdeaExplanationProofError(
            f"{label} returned reason `{actual}`; expected `{expected_reason}`."
        )


def _problem_reason(problem: dict[str, Any]) -> str:
    metadata = _require_dict(problem, "metadata")
    return _require_text(metadata, "reason_code")


def _expect_value(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise IdeaExplanationProofError(f"{label} was {actual!r}; expected {expected!r}.")


def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return _require_dict_from_value(value, key)


def _require_dict_from_value(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IdeaExplanationProofError(f"{label} must be an object.")
    return value


def _require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise IdeaExplanationProofError(f"{key} must be a list.")
    return value


def _require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise IdeaExplanationProofError(f"{key} must be a non-empty string.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
