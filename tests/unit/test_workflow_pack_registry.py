from app.contracts.workflow_packs import (
    WorkflowPackActivationState,
    WorkflowPackRegistrationStatus,
)
from app.services.workflow_pack_registry import (
    build_workflow_pack_registration_detail,
    build_workflow_pack_registry_catalog,
)


def test_build_workflow_pack_registry_catalog_exposes_registration_posture() -> None:
    catalog = build_workflow_pack_registry_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.phase == "foundation"
    assert catalog.registration_count == 2
    assert catalog.registered_count == 1
    assert catalog.production_eligible_count == 0
    assert catalog.registrations[0].pack_id == "advisor_brief.pack"
    assert catalog.registrations[0].version == "v1"
    assert catalog.registrations[0].registration_status == WorkflowPackRegistrationStatus.REGISTERED
    assert catalog.registrations[0].activation_state == WorkflowPackActivationState.PILOT
    assert catalog.registrations[0].owner_repository == "lotus-manage"
    assert catalog.registrations[0].workflow_authority_owner == "lotus-gateway"
    assert catalog.registrations[1].version == "v2"
    assert catalog.registrations[1].registration_status == WorkflowPackRegistrationStatus.DISCOVERED


def test_build_workflow_pack_registry_catalog_exposes_validation_rules() -> None:
    catalog = build_workflow_pack_registry_catalog()

    assert len(catalog.validation_rules) == 3
    assert any(rule.rule_id == "unique_pack_version_identity" for rule in catalog.validation_rules)
    assert any("read-only and catalog-backed" in line for line in catalog.status_summary)


def test_build_workflow_pack_registration_detail_exposes_deny_by_default_registration_truth() -> (
    None
):
    detail = build_workflow_pack_registration_detail(pack_id="advisor_brief.pack", version="v1")

    assert detail.registration.pack_id == "advisor_brief.pack"
    assert detail.registration.version == "v1"
    assert detail.registration.definition_ref == (
        "repo://lotus-manage/docs/ai/workflow-packs/advisor_brief/v1"
    )
    assert detail.denied_without_registration is True
    assert any(
        rule.rule_id == "registered_entries_require_scope" for rule in detail.validation_rules
    )


def test_build_workflow_pack_registration_detail_rejects_unknown_registration() -> None:
    try:
        build_workflow_pack_registration_detail(pack_id="missing.pack", version="v1")
    except ValueError as exc:
        assert "Unknown workflow-pack registration" in str(exc)
    else:
        raise AssertionError("Expected unknown workflow-pack registration lookup to fail")
