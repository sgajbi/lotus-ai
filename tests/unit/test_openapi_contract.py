from app.main import app


def test_governed_endpoints_define_explicit_operation_ids() -> None:
    spec = app.openapi()

    assert spec["paths"]["/platform/runtime-status"]["get"]["operationId"] == (
        "getPlatformRuntimeStatus"
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
    assert spec["paths"]["/platform/prompts"]["get"]["operationId"] == "listPromptDefinitions"
    assert spec["paths"]["/platform/prompts/runtime-status"]["get"]["operationId"] == (
        "getPromptRuntimeStatus"
    )
    prompt_runtime_schema = spec["components"]["schemas"]["PromptRuntimeStatusResponse"]
    assert "rollout_mode" in prompt_runtime_schema["properties"]
    assert "candidate_prompt_count" in prompt_runtime_schema["properties"]
    assert "rollout_states" in prompt_runtime_schema["properties"]
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
