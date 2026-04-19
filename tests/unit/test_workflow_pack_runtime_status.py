from _pytest.monkeypatch import MonkeyPatch

from app.contracts.workflow_packs import WorkflowPackRegistrationStatus
from app.services.workflow_pack_bindings import get_workflow_pack_execution_binding_descriptor
from app.services.workflow_pack_registry import get_workflow_pack_registration
from app.services.workflow_pack_runtime_status import build_workflow_pack_runtime_status_summary


def test_build_workflow_pack_runtime_status_summary_separates_catalog_from_execution_readiness(
    monkeypatch: MonkeyPatch,
) -> None:
    registered = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    discovered = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v2")
    binding = get_workflow_pack_execution_binding_descriptor(
        pack_id="advisor_brief.pack",
        version="v1",
    )

    assert registered is not None
    assert discovered is not None
    assert binding is not None

    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.list_workflow_pack_registrations",
        lambda: [
            registered,
            discovered.model_copy(
                update={"registration_status": WorkflowPackRegistrationStatus.REGISTERED}
            ),
        ],
    )
    monkeypatch.setattr(
        "app.services.workflow_pack_runtime_status.list_workflow_pack_execution_binding_descriptors",
        lambda: [binding],
    )

    summary = build_workflow_pack_runtime_status_summary()

    assert summary.registration_count == 2
    assert summary.registered_count == 2
    assert summary.execution_binding_count == 1
    assert summary.executable_registration_count == 1
    assert summary.registered_without_execution_binding_count == 1
    assert summary.executable_registration_refs == ["advisor_brief.pack@v1"]
