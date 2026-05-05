from app.contracts.workflow_packs import (
    WorkflowPackActivationState,
    WorkflowPackCallerIdentityClass,
    WorkflowPackDefinitionReferenceDescriptor,
    WorkflowPackDefinitionReferenceType,
    WorkflowPackEnvironment,
    WorkflowPackExecutionMode,
    WorkflowPackRegistrationDescriptor,
    WorkflowPackRegistrationStatus,
)
from app.services.workflow_pack_registry import (
    build_workflow_pack_registration_detail,
    build_workflow_pack_registry_catalog,
    get_workflow_pack_registration,
    save_workflow_pack_registration,
)
from app.services.workflow_pack_registry_seed import (
    _validate_registered_entries_have_scope,
    _validate_retired_entries_are_not_active,
    _validate_unique_registration_identity,
)


def test_build_workflow_pack_registry_catalog_exposes_registration_posture() -> None:
    catalog = build_workflow_pack_registry_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.phase == "foundation"
    assert catalog.registration_count == 5
    assert catalog.registered_count == 4
    assert catalog.production_eligible_count == 0
    advisor_brief_registration = next(
        registration
        for registration in catalog.registrations
        if registration.pack_id == "advisor_brief.pack" and registration.version == "v1"
    )
    workspace_rationale_registration = next(
        registration
        for registration in catalog.registrations
        if registration.pack_id == "workspace_rationale.pack"
    )
    twr_inspection_registration = next(
        registration
        for registration in catalog.registrations
        if registration.pack_id == "twr_inspection_support_brief.pack"
    )
    outcome_review_narrative_registration = next(
        registration
        for registration in catalog.registrations
        if registration.pack_id == "outcome_review_narrative.pack"
    )
    assert (
        advisor_brief_registration.registration_status == WorkflowPackRegistrationStatus.REGISTERED
    )
    assert advisor_brief_registration.activation_state == WorkflowPackActivationState.PILOT
    assert advisor_brief_registration.owner_repository == "lotus-gateway"
    assert advisor_brief_registration.workflow_authority_owner == "lotus-gateway"
    assert advisor_brief_registration.definition_ref == (
        "repo://lotus-gateway/src/app/contracts/advisor_brief.py"
    )
    assert any(
        definition_ref.repository == "lotus-gateway"
        and definition_ref.path == "src/app/services/advisor_brief_service.py"
        and definition_ref.required_for_registration is True
        for definition_ref in advisor_brief_registration.definition_refs
    )
    assert workspace_rationale_registration.registration_status == (
        WorkflowPackRegistrationStatus.REGISTERED
    )
    assert workspace_rationale_registration.owner_repository == "lotus-advise"
    assert workspace_rationale_registration.workflow_authority_owner == "lotus-advise"
    assert twr_inspection_registration.registration_status == (
        WorkflowPackRegistrationStatus.REGISTERED
    )
    assert twr_inspection_registration.owner_repository == "lotus-performance"
    assert twr_inspection_registration.workflow_authority_owner == "lotus-performance"
    assert outcome_review_narrative_registration.registration_status == (
        WorkflowPackRegistrationStatus.REGISTERED
    )
    assert outcome_review_narrative_registration.owner_repository == "lotus-manage"
    assert outcome_review_narrative_registration.workflow_authority_owner == "lotus-manage"
    assert outcome_review_narrative_registration.supported_callers == [
        "lotus-manage",
        "lotus-gateway",
    ]
    assert any(
        definition_ref.repository == "lotus-manage"
        and definition_ref.path == "src/core/outcomes/handoffs.py"
        and definition_ref.required_for_registration is True
        for definition_ref in outcome_review_narrative_registration.definition_refs
    )
    assert len(catalog.execution_bindings) == 4
    assert len(catalog.queue_policies) == 4
    assert any(
        binding.pack_id == "advisor_brief.pack" and binding.task_id == "explain.v1"
        for binding in catalog.execution_bindings
    )
    assert any(
        policy.workflow_pack_id == "advisor_brief.pack"
        and policy.workflow_pack_version == "v1"
        and policy.default_lane.value == "LATENCY_SENSITIVE"
        for policy in catalog.queue_policies
    )
    assert any(
        binding.pack_id == "workspace_rationale.pack" and binding.task_id == "explain.v1"
        for binding in catalog.execution_bindings
    )
    assert any(
        binding.pack_id == "twr_inspection_support_brief.pack" and binding.task_id == "explain.v1"
        for binding in catalog.execution_bindings
    )
    assert any(
        binding.pack_id == "outcome_review_narrative.pack" and binding.task_id == "explain.v1"
        for binding in catalog.execution_bindings
    )


def test_build_workflow_pack_registry_catalog_exposes_validation_rules() -> None:
    catalog = build_workflow_pack_registry_catalog()

    assert len(catalog.validation_rules) == 4
    assert any(rule.rule_id == "unique_pack_version_identity" for rule in catalog.validation_rules)
    assert any(
        rule.rule_id == "definition_refs_ground_registry_truth" for rule in catalog.validation_rules
    )
    assert any("configured registry store" in line for line in catalog.status_summary)
    assert any(
        "valid ownership, scope, and definition references" in line
        for line in catalog.status_summary
    )
    assert any(
        "Internal execution bindings are validated" in line for line in catalog.status_summary
    )
    assert any(
        "Queue-policy inspection is version-scoped" in line for line in catalog.status_summary
    )


def test_build_workflow_pack_registration_detail_exposes_deny_by_default_registration_truth() -> (
    None
):
    detail = build_workflow_pack_registration_detail(pack_id="advisor_brief.pack", version="v1")

    assert detail.registration.pack_id == "advisor_brief.pack"
    assert detail.registration.version == "v1"
    assert detail.registration.definition_ref == (
        "repo://lotus-gateway/src/app/contracts/advisor_brief.py"
    )
    assert any(
        definition_ref.reference_id == "owner_router"
        and definition_ref.repository == "lotus-gateway"
        and definition_ref.path == "src/app/routers/workbench.py"
        for definition_ref in detail.registration.definition_refs
    )
    assert detail.execution_binding is not None
    assert detail.execution_binding.task_id == "explain.v1"
    assert detail.execution_binding.default_workflow_surface == "advisor-brief-workspace"
    assert detail.queue_policy is not None
    assert detail.queue_policy.policy_id == "queue-policy.advisor-brief.v1"
    assert detail.queue_policy.default_lane.value == "LATENCY_SENSITIVE"
    assert detail.denied_without_registration is True
    assert any(
        rule.rule_id == "registered_entries_require_scope" for rule in detail.validation_rules
    )


def test_build_workflow_pack_registration_detail_omits_execution_binding_for_discovery_only_version() -> (
    None
):
    detail = build_workflow_pack_registration_detail(pack_id="advisor_brief.pack", version="v2")

    assert detail.execution_binding is None
    assert detail.queue_policy is None


def test_build_workspace_rationale_registration_detail_exposes_advise_owned_binding() -> None:
    detail = build_workflow_pack_registration_detail(
        pack_id="workspace_rationale.pack",
        version="v1",
    )

    assert detail.registration.owner_repository == "lotus-advise"
    assert detail.registration.workflow_authority_owner == "lotus-advise"
    assert detail.execution_binding is not None
    assert detail.execution_binding.task_id == "explain.v1"
    assert detail.execution_binding.default_workflow_surface == "advisory-workspace-assistant"


def test_build_twr_inspection_support_brief_registration_detail_exposes_performance_owned_binding() -> (
    None
):
    detail = build_workflow_pack_registration_detail(
        pack_id="twr_inspection_support_brief.pack",
        version="v1",
    )

    assert detail.registration.owner_repository == "lotus-performance"
    assert detail.registration.workflow_authority_owner == "lotus-performance"
    assert detail.execution_binding is not None
    assert detail.execution_binding.task_id == "explain.v1"
    assert detail.execution_binding.default_workflow_surface == "twr-supportability-inspection"


def test_build_workflow_pack_registration_detail_rejects_unknown_registration() -> None:
    try:
        build_workflow_pack_registration_detail(pack_id="missing.pack", version="v1")
    except ValueError as exc:
        assert "Unknown workflow-pack registration" in str(exc)
    else:
        raise AssertionError("Expected unknown workflow-pack registration lookup to fail")


def test_save_workflow_pack_registration_rejects_missing_owner_repository_reference() -> None:
    invalid_registration = WorkflowPackRegistrationDescriptor(
        pack_id="proposal_brief.pack",
        pack_family="proposal_brief",
        version="v1",
        owner_repository="lotus-advise",
        owner_service="lotus-advise",
        truth_owner_services=["lotus-advise"],
        primary_use_case="proposal_brief",
        workflow_authority_owner="lotus-advise",
        default_execution_mode=WorkflowPackExecutionMode.REVIEW_GATED,
        definition_ref="repo://lotus-workbench/docs/rfcs/RFC-0020-ai-advisor-brief-copilot.md",
        definition_refs=[
            WorkflowPackDefinitionReferenceDescriptor(
                reference_id="ui_rfc",
                repository="lotus-workbench",
                path="docs/rfcs/RFC-0020-ai-advisor-brief-copilot.md",
                reference_type=WorkflowPackDefinitionReferenceType.RFC,
                required_for_registration=True,
                description="Intentionally invalid test fixture with no owner-repository reference.",
            )
        ],
        compatibility_contract_version="workflow-pack-contract.v1",
        registration_status=WorkflowPackRegistrationStatus.REGISTERED,
        activation_state=WorkflowPackActivationState.PILOT,
        registered_definition_digest="sha256:test-invalid-owner-ref",
        supported_callers=["lotus-gateway"],
        supported_identity_classes=[WorkflowPackCallerIdentityClass.INTERNAL_SERVICE],
        supported_environments=[WorkflowPackEnvironment.QA],
        tenant_scope=[],
        surface_scope=["proposal-brief-panel"],
        default_rollout_stage="PILOT_SCOPED",
        pause_state="NOT_PAUSED",
        supersedes=None,
        superseded_by=None,
        registered_at="2026-04-18T10:00:00Z",
        registered_by="test.fixture",
        last_activated_at=None,
        last_changed_at="2026-04-18T10:00:00Z",
        status_summary=["Invalid test registration for owner-repository validation."],
    )

    try:
        save_workflow_pack_registration(invalid_registration)
    except ValueError as exc:
        assert "owner_repository" in str(exc)
    else:
        raise AssertionError("Expected missing owner_repository reference validation to fail")


def test_save_workflow_pack_registration_rejects_non_repo_definition_ref() -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None

    try:
        save_workflow_pack_registration(
            registration.model_copy(update={"definition_ref": "docs/advisor_brief.md"})
        )
    except ValueError as exc:
        assert "repo://" in str(exc)
    else:
        raise AssertionError("Expected non-repo definition_ref to fail")


def test_save_workflow_pack_registration_rejects_missing_definition_refs() -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None

    try:
        save_workflow_pack_registration(registration.model_copy(update={"definition_refs": []}))
    except ValueError as exc:
        assert "missing definition_refs" in str(exc)
    else:
        raise AssertionError("Expected missing definition_refs to fail")


def test_save_workflow_pack_registration_rejects_primary_ref_not_in_definition_refs() -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None

    try:
        save_workflow_pack_registration(
            registration.model_copy(
                update={
                    "definition_ref": "repo://lotus-gateway/src/app/routers/missing_router.py",
                }
            )
        )
    except ValueError as exc:
        assert "must match one structured definition ref" in str(exc)
    else:
        raise AssertionError("Expected mismatched primary definition_ref to fail")


def test_save_workflow_pack_registration_rejects_missing_required_owner_artifacts() -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    downgraded_refs = [
        definition_ref.model_copy(update={"required_for_registration": False})
        for definition_ref in registration.definition_refs
    ]

    try:
        save_workflow_pack_registration(
            registration.model_copy(update={"definition_refs": downgraded_refs})
        )
    except ValueError as exc:
        assert "missing required owner artifacts" in str(exc)
    else:
        raise AssertionError("Expected missing required owner artifacts to fail")


def test_seed_registration_validation_rejects_duplicate_identity_scope_and_retired_drift() -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None

    try:
        _validate_unique_registration_identity([registration, registration])
    except ValueError as exc:
        assert "Duplicate workflow-pack registration identity" in str(exc)
    else:
        raise AssertionError("expected duplicate registration identity to fail")

    try:
        _validate_registered_entries_have_scope(
            [registration.model_copy(update={"supported_callers": []})]
        )
    except ValueError as exc:
        assert "missing execution scope" in str(exc)
    else:
        raise AssertionError("expected registered entry without caller scope to fail")

    try:
        _validate_retired_entries_are_not_active(
            [
                registration.model_copy(
                    update={
                        "registration_status": WorkflowPackRegistrationStatus.RETIRED,
                        "activation_state": WorkflowPackActivationState.PILOT,
                    }
                )
            ]
        )
    except ValueError as exc:
        assert "Retired workflow-pack cannot remain active" in str(exc)
    else:
        raise AssertionError("expected retired active entry to fail")
