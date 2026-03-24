from __future__ import annotations

from app.contracts.evals import EvaluationApprovalGateSummaryDescriptor
from app.services.eval_approval_gate_summary import (
    build_analytics_commentary_pack_approval_gate_summary,
    build_decision_explanation_pack_approval_gate_summary,
)


def build_capability_pack_approval_gate(*, pack_id: str) -> EvaluationApprovalGateSummaryDescriptor:
    if pack_id == "analytics_commentary.pack.v1":
        return build_analytics_commentary_pack_approval_gate_summary()
    if pack_id == "decision_explanation.pack.v1":
        return build_decision_explanation_pack_approval_gate_summary()
    raise ValueError(f"Unknown capability pack: {pack_id}")
