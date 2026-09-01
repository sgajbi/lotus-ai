from fastapi.testclient import TestClient
import pytest

from app.config import settings
from app.services.audit_store import get_audit_store


def _execute_task(
    client: TestClient,
    *,
    caller_app: str,
    tenant_id: str,
    correlation_id: str,
) -> str:
    task_id = "summarize.v1" if caller_app == "lotus-advise" else "explain.v1"
    response = client.post(
        "/ai/tasks/execute",
        json={
            "task_id": task_id,
            "input_mode": "STRUCTURED_CONTEXT",
            "caller": {
                "caller_app": caller_app,
                "correlation_id": correlation_id,
                "requested_by": f"{caller_app}.operator",
                "tenant_id": tenant_id,
            },
            "context": {
                "summary": "Tenant isolation audit fixture.",
                "payload": {"status": "READY"},
                "source_refs": [f"{caller_app}:tenant-isolation:{correlation_id}"],
            },
        },
    )
    assert response.status_code == 200
    return str(response.json()["audit"]["request_id"])


def test_audit_routes_require_authenticated_caller(client: TestClient) -> None:
    catalog_response = client.get("/ai/audit", headers={"X-Caller-App": ""})
    detail_response = client.get("/ai/audit/missing", headers={"X-Caller-App": ""})

    assert catalog_response.status_code == 403
    assert detail_response.status_code == 403


def test_audit_routes_enforce_server_derived_tenant_scope_and_indistinguishable_404(
    client: TestClient,
) -> None:
    sg_request_id = _execute_task(
        client,
        caller_app="lotus-manage",
        tenant_id="tenant-sg-001",
        correlation_id="corr-audit-scope-sg",
    )
    us_request_id = _execute_task(
        client,
        caller_app="lotus-advise",
        tenant_id="tenant-us-002",
        correlation_id="corr-audit-scope-us",
    )

    catalog_response = client.get(
        "/ai/audit",
        headers={"X-Caller-App": "lotus-manage"},
        params={"limit": 100},
    )
    cross_scope_response = client.get(
        f"/ai/audit/{us_request_id}",
        headers={"X-Caller-App": "lotus-manage"},
    )
    missing_response = client.get(
        "/ai/audit/does-not-exist",
        headers={"X-Caller-App": "lotus-manage"},
    )

    assert catalog_response.status_code == 200
    body = catalog_response.json()
    assert body["filters_applied"]["tenant_scope"] == "RESTRICTED_TENANTS"
    returned_ids = {record["request_id"] for record in body["records"]}
    assert sg_request_id in returned_ids
    assert us_request_id not in returned_ids
    assert all(record["tenant_id"] == "tenant-sg-001" for record in body["records"])
    assert cross_scope_response.status_code == missing_response.status_code == 404
    assert cross_scope_response.json()["detail"] == missing_response.json()["detail"]
    assert cross_scope_response.json()["error_code"] == missing_response.json()["error_code"]


def test_platform_all_tenant_reads_are_capability_gated_and_durably_audited(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", True)
    sg_request_id = _execute_task(
        client,
        caller_app="lotus-manage",
        tenant_id="tenant-sg-001",
        correlation_id="corr-audit-operator-sg",
    )
    us_request_id = _execute_task(
        client,
        caller_app="lotus-advise",
        tenant_id="tenant-us-002",
        correlation_id="corr-audit-operator-us",
    )

    response = client.get(
        "/ai/audit",
        headers={"X-Caller-App": "lotus-platform"},
        params={"limit": 100},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["filters_applied"]["tenant_scope"] == "ALL_TENANTS"
    returned_ids = {record["request_id"] for record in body["records"]}
    assert {sg_request_id, us_request_id}.issubset(returned_ids)
    event = get_audit_store().list_access_events(limit=1)[0]
    assert event.caller_app == "lotus-platform"
    assert event.scope_mode.value == "ALL_TENANTS"
    assert event.operation.value == "LIST_RECORDS"
    assert event.outcome.value == "SUCCEEDED"
    assert event.returned_record_count == body["record_count"]
    event_payload = event.model_dump(mode="json")
    assert "tenant_id" not in event_payload
    assert "request_id" not in event_payload


@pytest.mark.parametrize("path", ["/ai/audit", "/ai/audit/request-platform"])
def test_platform_header_only_all_tenant_read_fails_closed_outside_local_posture(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    monkeypatch.setattr(settings, "startup_readiness_policy", "warn")
    monkeypatch.setattr(settings, "readiness_probe_policy", "degrade")

    response = client.get(path, headers={"X-Caller-App": "lotus-platform"})

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Caller is not authorized to inspect lotus-ai audit records."
    )


@pytest.mark.parametrize("path", ["/ai/audit", "/ai/audit/missing"])
def test_platform_audit_read_fails_closed_when_access_evidence_cannot_be_saved(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", True)
    audit_store = get_audit_store()

    def fail_access_evidence(*args: object, **kwargs: object) -> None:
        raise RuntimeError("sentinel audit access persistence failure")

    monkeypatch.setattr(audit_store, "save_access_event", fail_access_evidence)

    failure_client = TestClient(client.app, raise_server_exceptions=False)
    response = failure_client.get(path, headers={"X-Caller-App": "lotus-platform"})

    assert response.status_code == 500
    assert response.json()["error_code"] == "LOTUS_AI_INTERNAL_ERROR"
    assert "sentinel" not in response.text


def test_audit_list_applies_the_category_filter_within_the_caller_scope(
    client: TestClient,
) -> None:
    response = client.get(
        "/ai/audit",
        params={"category": "explain"},
        headers={"X-Caller-App": "lotus-idea"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filters_applied"]["category"] == "explain"
    assert all(record["category"] == "explain" for record in body["records"])


def test_the_access_event_ledger_is_readable_by_the_privilege_it_describes(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #167 S2: evidence an operator cannot read is evidence in name only.

    The ledger records who read audit records and who was refused, so reading
    it requires the same all-tenant privilege those events describe — and the
    read is itself recorded, like every other privileged audit read.
    """

    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", True)
    _execute_task(
        client,
        caller_app="lotus-manage",
        tenant_id="tenant-sg-001",
        correlation_id="corr-access-events-seed",
    )
    # A privileged read, so the ledger has something to show.
    assert (
        client.get(
            "/ai/audit", headers={"X-Caller-App": "lotus-platform"}, params={"limit": 10}
        ).status_code
        == 200
    )

    response = client.get(
        "/ai/audit/access-events",
        headers={"X-Caller-App": "lotus-platform"},
        params={"limit": 50},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["returned_event_count"] == len(body["events"])
    assert body["events"], "the ledger returned nothing despite a recorded privileged read"
    operations = [event["operation"] for event in body["events"]]
    assert "LIST_RECORDS" in operations
    # Newest first.
    recorded = [event["recorded_at"] for event in body["events"]]
    assert recorded == sorted(recorded, reverse=True)

    # Reading the ledger is itself privileged access, so it is on the ledger.
    follow_up = client.get(
        "/ai/audit/access-events",
        headers={"X-Caller-App": "lotus-platform"},
        params={"limit": 50},
    )
    assert follow_up.status_code == 200
    assert "LIST_ACCESS_EVENTS" in [event["operation"] for event in follow_up.json()["events"]]


def test_a_restricted_tenant_caller_is_refused_the_ledger_and_recorded(
    client: TestClient,
) -> None:
    """A valid restricted scope is not the privilege this surface requires, and
    the refusal is itself evidence — recorded as INSUFFICIENT_PRIVILEGE rather
    than as a caller with no usable scope."""

    response = client.get(
        "/ai/audit/access-events",
        headers={"X-Caller-App": "lotus-manage"},
        params={"limit": 10},
    )

    assert response.status_code == 403
    event = get_audit_store().list_access_events(limit=1)[0]
    assert event.caller_app == "lotus-manage"
    assert event.outcome.value == "DENIED"
    assert event.denial_reason is not None
    assert event.denial_reason.value == "INSUFFICIENT_PRIVILEGE"
    assert event.operation.value == "LIST_ACCESS_EVENTS"
    assert event.scope_mode.value == "UNRESOLVED"


def test_the_ledger_carries_no_tenant_or_record_identifiers(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ledger describes access, not content. Publishing record or tenant
    identifiers here would turn an access log into a second, less governed
    route to the records it describes."""

    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", True)
    _execute_task(
        client,
        caller_app="lotus-manage",
        tenant_id="tenant-sg-001",
        correlation_id="corr-access-events-shape",
    )
    assert client.get("/ai/audit", headers={"X-Caller-App": "lotus-platform"}).status_code == 200

    body = client.get("/ai/audit/access-events", headers={"X-Caller-App": "lotus-platform"}).json()

    for event in body["events"]:
        assert "tenant_id" not in event
        assert "request_id" not in event
        assert set(event).issubset(
            {
                "event_id",
                "caller_app",
                "caller_trust_source",
                "scope_mode",
                "operation",
                "outcome",
                "denial_reason",
                "returned_record_count",
                "recorded_at",
            }
        )
