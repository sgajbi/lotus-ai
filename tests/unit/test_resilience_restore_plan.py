from app.contracts.resilience import ResilienceDeliveryStage, ResilienceRestoreClassification
from app.services.resilience_restore_plan import build_resilience_restore_plan


def test_resilience_restore_plan_is_ordered_and_bounded() -> None:
    plan = build_resilience_restore_plan()

    assert plan.delivery_stage is ResilienceDeliveryStage.DRILL_VERIFIED
    assert plan.restore_step_count == 4
    assert plan.restore_steps[0].step_id == "restore_authoritative_relational_metadata"
    assert plan.restore_steps[0].classification is (
        ResilienceRestoreClassification.PLATFORM_METADATA_RESTORE
    )
    assert plan.restore_steps[1].requires_completed_steps == [
        "restore_authoritative_relational_metadata"
    ]
    assert plan.restore_steps[2].requires_completed_steps == [
        "restore_authoritative_relational_metadata",
        "reconcile_artifact_payload_storage",
    ]
    assert plan.restore_steps[3].classification is (
        ResilienceRestoreClassification.EXTERNAL_DEPENDENCY_VALIDATION
    )
    assert any(
        "rollback of application behavior" in summary.lower()
        for summary in plan.restore_validation_summary
    )
