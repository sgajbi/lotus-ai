from __future__ import annotations

from app.main import app


def test_openapi_documents_shared_problem_details_for_representative_routes() -> None:
    spec = app.openapi()
    assert "ProblemDetails" in spec["components"]["schemas"]

    representative_responses = [
        spec["paths"]["/ai/tasks/execute"]["post"]["responses"]["422"],
        spec["paths"]["/ai/tasks/execute"]["post"]["responses"]["503"],
        spec["paths"]["/ai/audit/{request_id}"]["get"]["responses"]["404"],
        spec["paths"]["/platform/retrieval/search"]["post"]["responses"]["409"],
        spec["paths"]["/platform/workflow-packs/runs/{run_id}"]["get"]["responses"]["404"],
    ]

    for response in representative_responses:
        schema = response["content"]["application/problem+json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/ProblemDetails"}


def test_problem_details_schema_exposes_stable_support_fields() -> None:
    schema = app.openapi()["components"]["schemas"]["ProblemDetails"]

    assert set(schema["properties"]) >= {
        "type",
        "title",
        "status",
        "detail",
        "error_code",
        "correlation_id",
        "metadata",
    }
