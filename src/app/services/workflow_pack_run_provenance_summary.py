from __future__ import annotations

from app.contracts.workflow_pack_runs import (
    WorkflowPackRunDescriptor,
    WorkflowPackRunProvenanceSummaryDescriptor,
)


def build_workflow_pack_run_provenance_summary(
    *,
    run: WorkflowPackRunDescriptor,
) -> WorkflowPackRunProvenanceSummaryDescriptor:
    return WorkflowPackRunProvenanceSummaryDescriptor(
        artifact_ref_count=len(run.artifact_refs),
        artifact_types=sorted({artifact.artifact_type for artifact in run.artifact_refs}),
        evidence_descriptor_count=len(run.evidence_descriptors),
        evidence_types=sorted(
            {descriptor.evidence_type for descriptor in run.evidence_descriptors}
        ),
    )
