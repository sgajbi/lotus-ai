from app.main import app


def test_governed_endpoints_define_explicit_operation_ids() -> None:
    spec = app.openapi()

    assert spec["paths"]["/platform/runtime-status"]["get"]["operationId"] == (
        "getPlatformRuntimeStatus"
    )
    assert spec["paths"]["/platform/capabilities"]["get"]["operationId"] == "getCapabilityCatalog"
    assert spec["paths"]["/platform/providers"]["get"]["operationId"] == "getProviderCatalog"
    assert spec["paths"]["/platform/providers/policy"]["get"]["operationId"] == "getProviderPolicy"
    assert spec["paths"]["/platform/safety/policy"]["get"]["operationId"] == "getSafetyPolicy"
    assert spec["paths"]["/platform/safety/runtime-status"]["get"]["operationId"] == (
        "getSafetyRuntimeStatus"
    )
    assert spec["paths"]["/platform/prompts"]["get"]["operationId"] == "listPromptDefinitions"
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
    assert (
        spec["paths"]["/platform/retrieval/documents/{document_id}/chunks"]["get"]["operationId"]
        == "listRetrievalDocumentChunks"
    )
    assert spec["paths"]["/platform/retrieval/search"]["post"]["operationId"] == (
        "searchRetrievalSources"
    )
    assert spec["paths"]["/ai/tasks/execute"]["post"]["operationId"] == "executeTask"
    assert spec["paths"]["/ai/audit/{request_id}"]["get"]["operationId"] == "getAuditRecord"
    assert spec["paths"]["/metadata"]["get"]["operationId"] == "getServiceMetadata"
    assert spec["paths"]["/"]["get"]["operationId"] == "getServiceOverview"
