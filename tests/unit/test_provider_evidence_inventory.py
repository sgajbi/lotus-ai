from app.services.provider_evidence_inventory import build_provider_evidence_inventory


def test_provider_evidence_inventory_reports_staged_and_recorded_provider_assets() -> None:
    inventory = build_provider_evidence_inventory()

    assert "provider_policy_examples" in inventory.staged_fixture_ids
    assert "provider_runtime_examples" in inventory.staged_fixture_ids
    assert "provider_failure_mode_examples" in inventory.staged_fixture_ids
    assert "provider_resolution" in inventory.evidence_category_ids
    assert inventory.latest_recorded_provider_run_id == "foundation_eval_2026_03_22_001"
    assert inventory.recorded_provider_fixture_ids == frozenset(
        {
            "provider_policy_examples",
            "provider_runtime_examples",
            "provider_failure_mode_examples",
            "provider_operations_examples",
            "provider_degradation_examples",
        }
    )
