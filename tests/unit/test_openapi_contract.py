from app.main import app


def test_governed_endpoints_define_explicit_operation_ids() -> None:
    spec = app.openapi()

    assert spec["paths"]["/platform/runtime-status"]["get"]["operationId"] == (
        "getPlatformRuntimeStatus"
    )
    assert spec["paths"]["/platform/resilience/runtime-status"]["get"]["operationId"] == (
        "getResilienceRuntimeStatus"
    )
    assert spec["paths"]["/platform/resilience/restore-plan"]["get"]["operationId"] == (
        "getResilienceRestorePlan"
    )
    assert spec["paths"]["/platform/deployment-split/runtime-status"]["get"]["operationId"] == (
        "getDeploymentSplitRuntimeStatus"
    )
    assert (
        spec["paths"]["/platform/deployment-split/activation-readiness"]["get"]["operationId"]
        == "getDeploymentSplitActivationReadiness"
    )
    assert (
        spec["paths"]["/platform/deployment-split/runbook-readiness"]["get"]["operationId"]
        == "getDeploymentSplitRunbookReadiness"
    )
    assert (
        spec["paths"]["/platform/deployment-split/governance-status"]["get"]["operationId"]
        == "getDeploymentSplitGovernanceStatus"
    )
    assert spec["paths"]["/platform/production-baseline/runtime-status"]["get"]["operationId"] == (
        "getProductionBaselineRuntimeStatus"
    )
    assert (
        spec["paths"]["/platform/production-baseline/activation-readiness"]["get"]["operationId"]
        == "getProductionBaselineActivationReadiness"
    )
    assert (
        spec["paths"]["/platform/production-baseline/runbook-readiness"]["get"]["operationId"]
        == "getProductionBaselineRunbookReadiness"
    )
    assert (
        spec["paths"]["/platform/production-baseline/governance-status"]["get"]["operationId"]
        == "getProductionBaselineGovernanceStatus"
    )
    assert spec["paths"]["/platform/observability/runtime-status"]["get"]["operationId"] == (
        "getObservabilityRuntimeStatus"
    )
    assert spec["paths"]["/platform/artifacts/runtime-status"]["get"]["operationId"] == (
        "getArtifactRuntimeStatus"
    )
    assert spec["paths"]["/platform/artifacts"]["get"]["operationId"] == "getArtifactCatalog"
    assert spec["paths"]["/platform/artifacts/activation-readiness"]["get"]["operationId"] == (
        "getArtifactActivationReadiness"
    )
    assert spec["paths"]["/platform/artifacts/runbook-readiness"]["get"]["operationId"] == (
        "getArtifactRunbookReadiness"
    )
    assert spec["paths"]["/platform/artifacts/governance-status"]["get"]["operationId"] == (
        "getArtifactGovernanceStatus"
    )
    assert spec["paths"]["/platform/observability/activation-readiness"]["get"]["operationId"] == (
        "getObservabilityActivationReadiness"
    )
    assert spec["paths"]["/platform/observability/runbook-readiness"]["get"]["operationId"] == (
        "getObservabilityRunbookReadiness"
    )
    assert spec["paths"]["/platform/observability/governance-status"]["get"]["operationId"] == (
        "getObservabilityGovernanceStatus"
    )
    assert spec["paths"]["/platform/observability/incident-summary"]["get"]["operationId"] == (
        "getObservabilityIncidentSummary"
    )
    assert spec["paths"]["/platform/observability/provider-summary"]["get"]["operationId"] == (
        "getProviderObservabilitySummary"
    )
    assert spec["paths"]["/platform/observability/retrieval-summary"]["get"]["operationId"] == (
        "getRetrievalObservabilitySummary"
    )
    assert spec["paths"]["/platform/observability/async-summary"]["get"]["operationId"] == (
        "getAsyncObservabilitySummary"
    )
    assert spec["paths"]["/platform/observability/evaluation-summary"]["get"]["operationId"] == (
        "getEvaluationObservabilitySummary"
    )
    assert spec["paths"]["/platform/observability/prompt-summary"]["get"]["operationId"] == (
        "getPromptObservabilitySummary"
    )
    assert spec["paths"]["/platform/observability/safety-summary"]["get"]["operationId"] == (
        "getSafetyObservabilitySummary"
    )
    assert spec["paths"]["/platform/observability/breakdowns"]["get"]["operationId"] == (
        "getObservabilityBreakdownSummary"
    )
    assert spec["paths"]["/platform/access-control/runtime-status"]["get"]["operationId"] == (
        "getAccessControlRuntimeStatus"
    )
    assert spec["paths"]["/platform/access-control/governance-status"]["get"]["operationId"] == (
        "getAccessControlGovernanceStatus"
    )
    assert spec["paths"]["/platform/access-control/caller-policies"]["get"]["operationId"] == (
        "listCallerPolicies"
    )
    assert spec["paths"]["/platform/async/runtime-status"]["get"]["operationId"] == (
        "getAsyncRuntimeStatus"
    )
    assert spec["paths"]["/platform/async/queue-backends"]["get"]["operationId"] == (
        "getAsyncQueueBackendCatalog"
    )
    assert spec["paths"]["/platform/async/worker-executions"]["get"]["operationId"] == (
        "getAsyncWorkerExecutionCatalog"
    )
    assert spec["paths"]["/platform/async/activation-readiness"]["get"]["operationId"] == (
        "getAsyncActivationReadiness"
    )
    assert spec["paths"]["/platform/async/runbook-readiness"]["get"]["operationId"] == (
        "getAsyncRunbookReadiness"
    )
    assert spec["paths"]["/platform/async/governance-status"]["get"]["operationId"] == (
        "getAsyncGovernanceStatus"
    )
    assert spec["paths"]["/platform/async/control-plane-actions"]["get"]["operationId"] == (
        "getAsyncControlHistory"
    )
    assert (
        spec["paths"]["/platform/async/control-plane-actions/apply"]["post"]["operationId"]
        == "applyAsyncControlAction"
    )
    assert spec["paths"]["/platform/async/jobs"]["get"]["operationId"] == "getAsyncJobCatalog"
    assert spec["paths"]["/platform/async/jobs/{job_id}"]["get"]["operationId"] == (
        "getAsyncJobDetail"
    )
    assert spec["paths"]["/platform/async/jobs/submit"]["post"]["operationId"] == ("submitAsyncJob")
    assert spec["paths"]["/platform/capabilities"]["get"]["operationId"] == "getCapabilityCatalog"
    assert (
        spec["paths"]["/platform/use-cases/first-production-use-case"]["get"]["operationId"]
        == "getFirstProductionUseCaseStatus"
    )
    assert (
        spec["paths"]["/platform/use-cases/first-production-use-case/readiness"]["get"][
            "operationId"
        ]
        == "getFirstProductionUseCaseReadiness"
    )
    assert (
        spec["paths"]["/platform/use-cases/first-production-use-case/runbook-readiness"]["get"][
            "operationId"
        ]
        == "getFirstProductionUseCaseRunbookReadiness"
    )
    assert (
        spec["paths"]["/platform/use-cases/first-production-use-case/governance-status"]["get"][
            "operationId"
        ]
        == "getFirstProductionUseCaseGovernanceStatus"
    )
    assert (
        spec["paths"]["/platform/use-cases/onboarding-template"]["get"]["operationId"]
        == "getUseCaseOnboardingTemplate"
    )
    assert spec["paths"]["/platform/evals/catalog"]["get"]["operationId"] == "getEvaluationCatalog"
    assert spec["paths"]["/platform/evals/runs"]["get"]["operationId"] == "getEvaluationRunCatalog"
    assert spec["paths"]["/platform/evals/runs/submit"]["post"]["operationId"] == (
        "submitEvaluationRun"
    )
    assert spec["paths"]["/platform/evals/fixtures/{fixture_id}"]["get"]["operationId"] == (
        "getEvaluationFixtureDetail"
    )
    assert spec["paths"]["/platform/evals/runs/{run_id}"]["get"]["operationId"] == (
        "getEvaluationRunDetail"
    )
    assert spec["paths"]["/platform/evals/runtime-status"]["get"]["operationId"] == (
        "getEvaluationRuntimeStatus"
    )
    assert spec["paths"]["/platform/providers"]["get"]["operationId"] == "getProviderCatalog"
    assert spec["paths"]["/platform/providers/policy"]["get"]["operationId"] == "getProviderPolicy"
    assert spec["paths"]["/platform/providers/quota-policy"]["get"]["operationId"] == (
        "getProviderQuotaPolicy"
    )
    assert spec["paths"]["/platform/providers/budget-policy"]["get"]["operationId"] == (
        "getProviderBudgetPolicy"
    )
    assert spec["paths"]["/platform/providers/operations-status"]["get"]["operationId"] == (
        "getProviderOperationsStatus"
    )
    assert spec["paths"]["/platform/providers/control-plane-actions"]["get"]["operationId"] == (
        "getProviderOperationsControlHistory"
    )
    assert (
        spec["paths"]["/platform/providers/control-plane-actions/reset"]["post"]["operationId"]
        == "applyProviderOperationsControlAction"
    )
    assert spec["paths"]["/platform/providers/activation-readiness"]["get"]["operationId"] == (
        "getProviderActivationReadiness"
    )
    assert spec["paths"]["/platform/providers/runbook-readiness"]["get"]["operationId"] == (
        "getProviderRunbookReadiness"
    )
    assert spec["paths"]["/platform/providers/evidence-readiness"]["get"]["operationId"] == (
        "getProviderEvidenceReadiness"
    )
    assert spec["paths"]["/platform/providers/governance-status"]["get"]["operationId"] == (
        "getProviderGovernanceStatus"
    )
    assert spec["paths"]["/platform/safety/policy"]["get"]["operationId"] == "getSafetyPolicy"
    assert spec["paths"]["/platform/safety/runtime-status"]["get"]["operationId"] == (
        "getSafetyRuntimeStatus"
    )
    assert spec["paths"]["/platform/safety/evidence-readiness"]["get"]["operationId"] == (
        "getSafetyEvidenceReadiness"
    )
    assert spec["paths"]["/platform/safety/runbook-readiness"]["get"]["operationId"] == (
        "getSafetyRunbookReadiness"
    )
    assert spec["paths"]["/platform/safety/governance-status"]["get"]["operationId"] == (
        "getSafetyGovernanceStatus"
    )
    safety_runtime_schema = spec["components"]["schemas"]["SafetyRuntimeStatusResponse"]
    assert "runtime_redaction_disposition" in safety_runtime_schema["properties"]
    assert "supported_execution_dispositions" in safety_runtime_schema["properties"]
    safety_outcome_schema = spec["components"]["schemas"]["SafetyExecutionOutcome"]
    assert "disposition" in safety_outcome_schema["properties"]
    assert "control_results" in safety_outcome_schema["properties"]
    audit_record_schema = spec["components"]["schemas"]["AuditRecordResponse"]
    assert "execution_status" in audit_record_schema["properties"]
    assert "safety_outcome" in audit_record_schema["properties"]
    assert "authorization" in audit_record_schema["properties"]
    observability_runtime_schema = spec["components"]["schemas"][
        "ObservabilityRuntimeStatusResponse"
    ]
    assert "domains" in observability_runtime_schema["properties"]
    assert "incident_evidence_items" in observability_runtime_schema["properties"]
    observability_activation_schema = spec["components"]["schemas"][
        "ObservabilityActivationReadinessResponse"
    ]
    assert "activation_ready" in observability_activation_schema["properties"]
    observability_runbook_schema = spec["components"]["schemas"][
        "ObservabilityRunbookReadinessResponse"
    ]
    assert "items" in observability_runbook_schema["properties"]
    observability_governance_schema = spec["components"]["schemas"][
        "ObservabilityGovernanceStatusResponse"
    ]
    assert "runtime_status" in observability_governance_schema["properties"]
    assert "activation_readiness" in observability_governance_schema["properties"]
    assert "runbook_readiness" in observability_governance_schema["properties"]
    incident_summary_schema = spec["components"]["schemas"]["ObservabilityIncidentSummaryResponse"]
    assert "summaries" in incident_summary_schema["properties"]
    domain_incident_schema = spec["components"]["schemas"]["DomainIncidentSummaryResponse"]
    assert "telemetry" in domain_incident_schema["properties"]
    assert "incident_evidence_items" in domain_incident_schema["properties"]
    incident_item_schema = spec["components"]["schemas"]["IncidentEvidenceSummaryItem"]
    assert "artifact_refs" in incident_item_schema["properties"]
    breakdown_schema = spec["components"]["schemas"]["ObservabilityBreakdownSummaryResponse"]
    assert "caller_apps" in breakdown_schema["properties"]
    assert "tenants" in breakdown_schema["properties"]
    assert "capabilities" in breakdown_schema["properties"]
    artifact_runtime_schema = spec["components"]["schemas"]["ArtifactRuntimeStatusResponse"]
    assert "metadata_store" in artifact_runtime_schema["properties"]
    assert "object_store" in artifact_runtime_schema["properties"]
    artifact_catalog_schema = spec["components"]["schemas"]["ArtifactCatalogResponse"]
    assert "artifacts" in artifact_catalog_schema["properties"]
    artifact_activation_schema = spec["components"]["schemas"][
        "ArtifactActivationReadinessResponse"
    ]
    assert "activation_ready" in artifact_activation_schema["properties"]
    artifact_runbook_schema = spec["components"]["schemas"]["ArtifactRunbookReadinessResponse"]
    assert "items" in artifact_runbook_schema["properties"]
    artifact_governance_schema = spec["components"]["schemas"]["ArtifactGovernanceStatusResponse"]
    assert "runtime_status" in artifact_governance_schema["properties"]
    assert "activation_readiness" in artifact_governance_schema["properties"]
    assert "runbook_readiness" in artifact_governance_schema["properties"]
    async_job_schema = spec["components"]["schemas"]["AsyncJobArtifactDescriptor"]
    assert "artifact_refs" in async_job_schema["properties"]
    evaluation_case_schema = spec["components"]["schemas"]["EvaluationCaseResultDescriptor"]
    assert "artifact_refs" in evaluation_case_schema["properties"]
    platform_runtime_schema = spec["components"]["schemas"]["PlatformRuntimeStatusResponse"]
    resilience_runtime_schema = spec["components"]["schemas"]["ResilienceRuntimeStatusResponse"]
    resilience_restore_plan_schema = spec["components"]["schemas"][
        "ResilienceRestorePlanResponse"
    ]
    resilience_dependency_schema = spec["components"]["schemas"][
        "ResilienceDependencyDescriptor"
    ]
    production_baseline_schema = spec["components"]["schemas"][
        "ProductionBaselineRuntimeStatusResponse"
    ]
    deployment_split_schema = spec["components"]["schemas"]["DeploymentSplitRuntimeStatusResponse"]
    deployment_split_activation_schema = spec["components"]["schemas"][
        "DeploymentSplitActivationReadinessResponse"
    ]
    deployment_split_runbook_schema = spec["components"]["schemas"][
        "DeploymentSplitRunbookReadinessResponse"
    ]
    deployment_split_governance_schema = spec["components"]["schemas"][
        "DeploymentSplitGovernanceStatusResponse"
    ]
    production_baseline_activation_schema = spec["components"]["schemas"][
        "ProductionBaselineActivationReadinessResponse"
    ]
    production_baseline_runbook_schema = spec["components"]["schemas"][
        "ProductionBaselineRunbookReadinessResponse"
    ]
    production_baseline_governance_schema = spec["components"]["schemas"][
        "ProductionBaselineGovernanceStatusResponse"
    ]
    assert "configured_stage" in deployment_split_schema["properties"]
    assert "effective_stage" in deployment_split_schema["properties"]
    assert "planes" in deployment_split_schema["properties"]
    assert "routes" in deployment_split_schema["properties"]
    assert "degraded" in deployment_split_schema["properties"]
    assert "degraded_findings" in deployment_split_schema["properties"]
    assert "activation_ready" in deployment_split_activation_schema["properties"]
    assert "items" in deployment_split_runbook_schema["properties"]
    assert "runtime_status" in deployment_split_governance_schema["properties"]
    assert "observability_governance_ready" in deployment_split_governance_schema["properties"]
    assert "posture" in production_baseline_schema["properties"]
    assert "dependencies" in production_baseline_schema["properties"]
    assert "activation_ready" in production_baseline_activation_schema["properties"]
    assert "items" in production_baseline_runbook_schema["properties"]
    assert "runtime_status" in production_baseline_governance_schema["properties"]
    assert "dependent_rollout_findings" in production_baseline_governance_schema["properties"]
    assert "posture" in resilience_runtime_schema["properties"]
    assert "delivery_stage" in resilience_runtime_schema["properties"]
    assert "recovery_state" in resilience_runtime_schema["properties"]
    assert "dependencies" in resilience_runtime_schema["properties"]
    assert "restart_survivable_dependency_count" in resilience_runtime_schema["properties"]
    assert "recovery_attention_dependency_count" in resilience_runtime_schema["properties"]
    assert "recovery_findings" in resilience_runtime_schema["properties"]
    assert "restore_steps" in resilience_restore_plan_schema["properties"]
    assert "restore_validation_summary" in resilience_restore_plan_schema["properties"]
    assert "recovery_state" in resilience_dependency_schema["properties"]
    assert "recovery_findings" in resilience_dependency_schema["properties"]
    assert "artifact_runtime" in platform_runtime_schema["properties"]
    assert "artifact_governance" in platform_runtime_schema["properties"]
    assert "resilience_runtime" in platform_runtime_schema["properties"]
    assert "first_use_case" in platform_runtime_schema["properties"]
    assert "first_use_case_governance" in platform_runtime_schema["properties"]
    assert "deployment_split" in platform_runtime_schema["properties"]
    assert "deployment_split_governance" in platform_runtime_schema["properties"]
    assert "production_baseline" in platform_runtime_schema["properties"]
    assert "production_baseline_governance" in platform_runtime_schema["properties"]
    first_use_case_schema = spec["components"]["schemas"]["FirstUseCaseRuntimeStatusResponse"]
    assert "downstream_contract_fields" in first_use_case_schema["properties"]
    assert "ownership_boundaries" in first_use_case_schema["properties"]
    first_use_case_readiness_schema = spec["components"]["schemas"]["FirstUseCaseReadinessResponse"]
    assert "approval_gate" in first_use_case_readiness_schema["properties"]
    assert "items" in first_use_case_readiness_schema["properties"]
    first_use_case_runbook_schema = spec["components"]["schemas"][
        "FirstUseCaseRunbookReadinessResponse"
    ]
    assert "items" in first_use_case_runbook_schema["properties"]
    first_use_case_governance_schema = spec["components"]["schemas"][
        "FirstUseCaseGovernanceStatusResponse"
    ]
    assert "rollout_stage" in first_use_case_governance_schema["properties"]
    assert "active_production_ready" in first_use_case_governance_schema["properties"]
    assert "readiness" in first_use_case_governance_schema["properties"]
    assert "runbook_readiness" in first_use_case_governance_schema["properties"]
    onboarding_template_schema = spec["components"]["schemas"]["UseCaseOnboardingTemplateResponse"]
    assert "checklist" in onboarding_template_schema["properties"]
    assert "approval_criteria" in onboarding_template_schema["properties"]
    assert spec["paths"]["/platform/prompts"]["get"]["operationId"] == "listPromptDefinitions"
    assert spec["paths"]["/platform/prompts/runtime-status"]["get"]["operationId"] == (
        "getPromptRuntimeStatus"
    )
    assert spec["paths"]["/platform/prompts/control-history"]["get"]["operationId"] == (
        "getPromptControlHistory"
    )
    assert spec["paths"]["/platform/prompts/control-actions"]["post"]["operationId"] == (
        "applyPromptControlAction"
    )
    prompt_runtime_schema = spec["components"]["schemas"]["PromptRuntimeStatusResponse"]
    assert "rollout_mode" in prompt_runtime_schema["properties"]
    assert "candidate_prompt_count" in prompt_runtime_schema["properties"]
    assert "rollout_states" in prompt_runtime_schema["properties"]
    prompt_rollout_schema = spec["components"]["schemas"]["PromptRolloutDescriptor"]
    assert "latest_control_event" in prompt_rollout_schema["properties"]
    prompt_governance_schema = spec["components"]["schemas"]["PromptGovernanceStatusResponse"]
    assert "control_history_endpoint" in prompt_governance_schema["properties"]
    prompt_evidence_schema = spec["components"]["schemas"]["PromptEvidenceReadinessResponse"]
    assert "approval_gate" in prompt_evidence_schema["properties"]
    task_audit_schema = spec["components"]["schemas"]["TaskAuditMetadata"]
    assert "prompt_selection" in task_audit_schema["properties"]
    assert "authorization" in task_audit_schema["properties"]
    audit_record_schema = spec["components"]["schemas"]["AuditRecordResponse"]
    assert "prompt_selection" in audit_record_schema["properties"]
    assert "authorization" in audit_record_schema["properties"]
    assert spec["paths"]["/platform/tasks/runtime-status"]["get"]["operationId"] == (
        "getTaskRuntimeStatus"
    )
    assert spec["paths"]["/platform/tasks/execution-summary"]["get"]["operationId"] == (
        "getTaskExecutionSummary"
    )
    assert spec["paths"]["/platform/tasks/evidence-summary"]["get"]["operationId"] == (
        "getTaskExecutionEvidenceSummary"
    )
    assert spec["paths"]["/platform/tasks/retrieval-summary"]["get"]["operationId"] == (
        "getTaskRetrievalExecutionSummary"
    )
    assert spec["paths"]["/platform/prompts/activation-readiness"]["get"]["operationId"] == (
        "getPromptActivationReadiness"
    )
    assert spec["paths"]["/platform/prompts/runbook-readiness"]["get"]["operationId"] == (
        "getPromptRunbookReadiness"
    )
    assert spec["paths"]["/platform/prompts/evidence-readiness"]["get"]["operationId"] == (
        "getPromptEvidenceReadiness"
    )
    assert spec["paths"]["/platform/prompts/governance-status"]["get"]["operationId"] == (
        "getPromptGovernanceSummary"
    )
    assert spec["paths"]["/platform/prompts/governance"]["get"]["operationId"] == (
        "getPromptGovernanceStatus"
    )
    assert (
        spec["paths"]["/platform/prompts/{task_id}"]["get"]["operationId"] == "getPromptDefinition"
    )
    assert (
        spec["paths"]["/platform/retrieval/sources"]["get"]["operationId"] == "listRetrievalSources"
    )
    assert spec["paths"]["/platform/retrieval/index-status"]["get"]["operationId"] == (
        "getRetrievalIndexStatus"
    )
    assert spec["paths"]["/platform/retrieval/runtime-status"]["get"]["operationId"] == (
        "getRetrievalRuntimeStatus"
    )
    assert spec["paths"]["/platform/retrieval/execution-status"]["get"]["operationId"] == (
        "getRetrievalExecutionStatus"
    )
    retrieval_execution_schema = spec["components"]["schemas"]["RetrievalExecutionStatusResponse"]
    assert "owning_plane" in retrieval_execution_schema["properties"]
    assert "route_mode" in retrieval_execution_schema["properties"]
    assert "split_route_degraded" in retrieval_execution_schema["properties"]
    assert "split_route_findings" in retrieval_execution_schema["properties"]
    eval_runtime_schema = spec["components"]["schemas"]["EvaluationRuntimeStatusResponse"]
    assert "owning_plane" in eval_runtime_schema["properties"]
    assert "submission_route_mode" in eval_runtime_schema["properties"]
    assert "async_execution_route_mode" in eval_runtime_schema["properties"]
    assert "split_route_degraded" in eval_runtime_schema["properties"]
    assert "split_route_findings" in eval_runtime_schema["properties"]
    assert spec["paths"]["/platform/retrieval/activation-readiness"]["get"]["operationId"] == (
        "getRetrievalActivationReadiness"
    )
    assert spec["paths"]["/platform/retrieval/runbook-readiness"]["get"]["operationId"] == (
        "getRetrievalRunbookReadiness"
    )
    assert spec["paths"]["/platform/retrieval/evidence-readiness"]["get"]["operationId"] == (
        "getRetrievalEvidenceReadiness"
    )
    assert spec["paths"]["/platform/retrieval/governance-status"]["get"]["operationId"] == (
        "getRetrievalGovernanceStatus"
    )
    assert spec["paths"]["/platform/retrieval/indexing-policy"]["get"]["operationId"] == (
        "getRetrievalIndexingPolicy"
    )
    assert spec["paths"]["/platform/retrieval/index-jobs"]["get"]["operationId"] == (
        "listRetrievalIndexJobs"
    )
    assert spec["paths"]["/platform/retrieval/index-jobs/{job_id}"]["get"]["operationId"] == (
        "getRetrievalIndexJob"
    )
    assert (
        spec["paths"]["/platform/retrieval/sources/{source_id}/documents"]["get"]["operationId"]
        == "listRetrievalSourceDocuments"
    )
    assert spec["paths"]["/platform/retrieval/source-governance"]["get"]["operationId"] == (
        "getRetrievalSourceGovernance"
    )
    assert spec["paths"]["/platform/retrieval/document-governance"]["get"]["operationId"] == (
        "getRetrievalDocumentGovernance"
    )
    assert (
        spec["paths"]["/platform/retrieval/documents/{document_id}/chunks"]["get"]["operationId"]
        == "listRetrievalDocumentChunks"
    )
    assert spec["paths"]["/platform/retrieval/search"]["post"]["operationId"] == (
        "searchRetrievalSources"
    )
    assert spec["paths"]["/ai/tasks/execute"]["post"]["operationId"] == "executeTask"
    assert spec["paths"]["/ai/audit/{request_id}"]["get"]["operationId"] == "getAuditRecord"
    assert spec["paths"]["/ai/audit"]["get"]["operationId"] == "listAuditRecords"
    assert spec["paths"]["/metadata"]["get"]["operationId"] == "getServiceMetadata"
    assert spec["paths"]["/"]["get"]["operationId"] == "getServiceOverview"
