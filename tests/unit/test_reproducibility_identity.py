"""Reproducibility identity (issue #151): prompt content hashes, explicit
sampling parameters, and provider configuration digests."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from pytest import MonkeyPatch, raises

from app.contracts.prompts import compute_prompt_content_sha256
from app.contracts.tasks import (
    CallerMetadata,
    OutputLabel,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskInputMode,
)
from app.db.models import PromptDefinitionVersionModel
from app.providers.openai_compatible_text_transport import (
    LOCAL_OPENAI_COMPATIBLE_TEXT_DESCRIPTOR,
    execute_openai_compatible_text_request,
)
from app.repositories.sqlalchemy_prompt_repository import SqlAlchemyPromptRepository
from app.repositories.sqlalchemy_workflow_pack_run_repository import (
    SqlAlchemyWorkflowPackRunRepository,
)
from app.services.prompt_store import get_prompt_repository
from app.services.provider_execution_controls import (
    build_provider_execution_controls,
    compute_provider_config_sha256,
)
from app.services.task_executor import execute_task
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings
from tests.unit.test_provider_gateway import _request as _provider_request
from tests.unit.test_sqlalchemy_prompt_repository import _authorization
from tests.unit.test_task_executor import _request as _task_request
from tests.unit.test_workflow_pack_run_store import _workflow_pack_run_record


def test_prompt_content_hash_is_canonical_and_stable() -> None:
    first = compute_prompt_content_sha256(
        system_instructions="Explain conservatively.",
        output_contract_notes="Explanation only.",
    )
    second = compute_prompt_content_sha256(
        system_instructions="Explain conservatively.",
        output_contract_notes="Explanation only.",
    )
    independent = hashlib.sha256(
        json.dumps(
            {
                "output_contract_notes": "Explanation only.",
                "system_instructions": "Explain conservatively.",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    assert first == second == independent
    assert len(first) == 64
    assert first != compute_prompt_content_sha256(
        system_instructions="Explain conservatively.",
        output_contract_notes="Explanation only, with citations.",
    )
    # Field names are part of the canonical form: swapping the two texts
    # must not collide.
    assert first != compute_prompt_content_sha256(
        system_instructions="Explanation only.",
        output_contract_notes="Explain conservatively.",
    )


def test_prompt_descriptor_computes_and_serialises_content_hash() -> None:
    prompt = get_prompt_repository().get_prompt("explain.v1")
    assert prompt is not None

    expected = compute_prompt_content_sha256(
        system_instructions=prompt.system_instructions,
        output_contract_notes=prompt.output_contract_notes,
    )

    assert prompt.content_sha256 == expected
    assert prompt.model_dump(mode="json")["content_sha256"] == expected


def _config_digest(
    *,
    temperature: float = 0.0,
    seed: int | None = None,
    model_version: str | None = "2026-06-01",
) -> str:
    return compute_provider_config_sha256(
        provider_mode="openai",
        provider_id="text.openai",
        model_id="gpt-5.4",
        model_version=model_version,
        temperature=temperature,
        top_p=None,
        seed=seed,
        max_output_tokens=512,
    )


def test_provider_config_digest_tracks_sampling_and_model_identity() -> None:
    digest = _config_digest()

    assert digest == _config_digest()
    assert len(digest) == 64
    assert digest != _config_digest(temperature=0.2)
    assert digest != _config_digest(seed=42)
    assert digest != _config_digest(model_version="2026-07-01")


def test_execution_controls_carry_sampling_settings() -> None:
    defaults = build_provider_execution_controls()
    assert defaults.temperature == 0.0
    assert defaults.top_p is None
    assert defaults.seed is None

    with override_runtime_settings(
        live_text_temperature=0.35, live_text_top_p=0.9, live_text_seed=11
    ):
        overridden = build_provider_execution_controls()
        assert overridden.temperature == 0.35
        assert overridden.top_p == 0.9
        assert overridden.seed == 11


def _capture_transport_payload(monkeypatch: MonkeyPatch) -> dict[str, object]:
    captured: dict[str, object] = {}

    def _fake_post(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs["payload"])  # type: ignore[call-overload]
        return {"id": "resp_sampling", "model": "local-model", "output_text": "OK"}

    monkeypatch.setattr(
        "app.providers.openai_compatible_text_transport.post_openai_compatible_response",
        _fake_post,
    )
    return captured


def test_transport_sends_explicit_default_sampling(monkeypatch: MonkeyPatch) -> None:
    captured = _capture_transport_payload(monkeypatch)

    response = execute_openai_compatible_text_request(
        descriptor=LOCAL_OPENAI_COMPATIBLE_TEXT_DESCRIPTOR,
        request=_provider_request(),
        api_base="http://localhost:1234/v1",
        api_key=None,
        require_api_key=False,
    )

    assert response.message == "OK"
    # Temperature is always explicit - reproducibility must not depend on
    # provider-side defaults; unset top_p/seed are omitted, not sent as null.
    assert captured["temperature"] == 0.0
    assert "top_p" not in captured
    assert "seed" not in captured


def test_openai_live_provider_sends_explicit_sampling(monkeypatch: MonkeyPatch) -> None:
    from app.providers.openai_live_text_provider import OpenAILiveTextProvider

    captured = _capture_transport_payload(monkeypatch)

    with override_runtime_settings(
        live_text_provider_api_key="test-key", live_text_model_id="gpt-5.4"
    ):
        response = OpenAILiveTextProvider().execute(_provider_request())

    # The managed-OpenAI path shares the payload builder with the local
    # path, so recorded sampling is truthful for both live providers.
    assert response.message == "OK"
    assert captured["model"] == "gpt-5.4"
    assert captured["temperature"] == 0.0
    assert "top_p" not in captured
    assert "seed" not in captured


def test_transport_sends_configured_sampling_parameters(monkeypatch: MonkeyPatch) -> None:
    captured = _capture_transport_payload(monkeypatch)

    execute_openai_compatible_text_request(
        descriptor=LOCAL_OPENAI_COMPATIBLE_TEXT_DESCRIPTOR,
        request=_provider_request(temperature=0.7, top_p=0.9, seed=42),
        api_base="http://localhost:1234/v1",
        api_key=None,
        require_api_key=False,
    )

    assert captured["temperature"] == 0.7
    assert captured["top_p"] == 0.9
    assert captured["seed"] == 42


def test_stub_execution_audit_carries_reproducibility_identity() -> None:
    response = execute_task(
        _task_request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )

    prompt = get_prompt_repository().get_prompt("explain.v1")
    assert prompt is not None
    assert response.audit.prompt_content_sha256 == prompt.content_sha256
    assert response.audit.sampling_parameters == {
        "temperature": 0.0,
        "top_p": None,
        "seed": None,
        "max_output_tokens": 512,
    }
    # The digest is deterministic even for stub executions, so identical
    # configurations are provably identical across audit rows.
    assert response.audit.provider_config_sha256 == compute_provider_config_sha256(
        provider_mode="disabled",
        provider_id="text.stub",
        model_id=None,
        model_version=None,
        temperature=0.0,
        top_p=None,
        seed=None,
        max_output_tokens=512,
    )


def test_knowledge_execution_audit_has_prompt_hash_but_no_sampling() -> None:
    response = execute_task(
        TaskExecutionRequest(
            task_id="knowledge_search.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-manage",
                correlation_id="corr-repro-ks",
                tenant_id="tenant-sg-001",
            ),
            context=TaskContextEnvelope(
                summary="Search Lotus knowledge sources",
                payload={
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                source_refs=["lotus-manage:knowledge-search:repro"],
            ),
            expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
        )
    )

    assert response.status == "COMPLETED"
    assert response.audit.prompt_content_sha256 is not None
    # No provider text request is built on retrieval paths: recording
    # sampling or a config digest there would fabricate reproducibility.
    assert response.audit.sampling_parameters is None
    assert response.audit.provider_config_sha256 is None


def _prompt_repository(tmp_path: Path) -> SqlAlchemyPromptRepository:
    database_url = f"sqlite:///{tmp_path / 'prompt-registry.db'}"
    upgrade_database_to_head(database_url)
    return SqlAlchemyPromptRepository(database_url)


def _promote_explain_v2(repository: SqlAlchemyPromptRepository) -> None:
    from app.contracts.prompts import (
        PromptControlActionType,
        PromptLifecycleStatus,
        PromptRolloutSelectionMode,
    )
    from app.services.prompt_rollout_models import (
        PromptRolloutEventRecord,
        PromptRolloutStateRecord,
    )

    promoted = repository.get_prompt_version("explain.v1", "foundation.explain.v2")
    retired = repository.get_prompt_version("explain.v1", "foundation.explain.v1")
    assert promoted is not None and retired is not None
    repository.save_prompt_rollout_transition(
        rollout_state=PromptRolloutStateRecord(
            task_id="explain.v1",
            active_prompt_version="foundation.explain.v2",
            candidate_prompt_version=None,
            previous_active_prompt_version="foundation.explain.v1",
            rollout_mode=PromptRolloutSelectionMode.GOVERNED_CONTROL_ACTIONS,
            runtime_mutation_enabled=True,
        ),
        updated_prompts=[
            retired.model_copy(update={"lifecycle_status": PromptLifecycleStatus.RETIRED}),
            promoted.model_copy(update={"lifecycle_status": PromptLifecycleStatus.ACTIVE}),
        ],
        event=PromptRolloutEventRecord(
            event_id="prompt_evt_repro_promote",
            task_id="explain.v1",
            action_type=PromptControlActionType.PROMOTE_CANDIDATE,
            requested_by="alice@lotus.test",
            approved_by="bob@lotus.test",
            reason="Promote candidate",
            prior_active_prompt_version="foundation.explain.v1",
            resulting_active_prompt_version="foundation.explain.v2",
            prior_candidate_prompt_version=None,
            resulting_candidate_prompt_version=None,
            authorization=_authorization(),
            recorded_at="2026-08-30T09:00:00Z",
        ),
    )


def test_sqlalchemy_prompt_read_tolerates_legacy_rows_without_hash(tmp_path: Path) -> None:
    repository = _prompt_repository(tmp_path)

    with repository._session_factory() as session:
        model = session.get(PromptDefinitionVersionModel, ("explain.v1", "foundation.explain.v1"))
        assert model is not None
        assert model.content_sha256 is None

    prompt = repository.get_prompt("explain.v1")
    assert prompt is not None
    assert prompt.content_sha256 == compute_prompt_content_sha256(
        system_instructions=prompt.system_instructions,
        output_contract_notes=prompt.output_contract_notes,
    )


def test_sqlalchemy_prompt_transition_backfills_content_hash(tmp_path: Path) -> None:
    repository = _prompt_repository(tmp_path)

    _promote_explain_v2(repository)

    with repository._session_factory() as session:
        model = session.get(PromptDefinitionVersionModel, ("explain.v1", "foundation.explain.v2"))
        assert model is not None
        assert model.content_sha256 == compute_prompt_content_sha256(
            system_instructions=model.system_instructions,
            output_contract_notes=model.output_contract_notes,
        )

    active = repository.get_prompt("explain.v1")
    assert active is not None
    assert active.prompt_version == "foundation.explain.v2"


def test_sqlalchemy_prompt_transition_refuses_content_edit(tmp_path: Path) -> None:
    from app.contracts.prompts import PromptControlActionType, PromptRolloutSelectionMode
    from app.services.prompt_rollout_models import (
        PromptRolloutEventRecord,
        PromptRolloutStateRecord,
    )

    repository = _prompt_repository(tmp_path)
    active = repository.get_prompt_version("explain.v1", "foundation.explain.v1")
    assert active is not None

    with raises(RuntimeError) as exc_info:
        repository.save_prompt_rollout_transition(
            rollout_state=PromptRolloutStateRecord(
                task_id="explain.v1",
                active_prompt_version="foundation.explain.v1",
                candidate_prompt_version=None,
                previous_active_prompt_version=None,
                rollout_mode=PromptRolloutSelectionMode.GOVERNED_CONTROL_ACTIONS,
                runtime_mutation_enabled=True,
            ),
            updated_prompts=[
                active.model_copy(update={"system_instructions": "Edited under a fixed label."})
            ],
            event=PromptRolloutEventRecord(
                event_id="prompt_evt_repro_edit",
                task_id="explain.v1",
                action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Attempt an in-place edit",
                prior_active_prompt_version="foundation.explain.v1",
                resulting_active_prompt_version="foundation.explain.v1",
                prior_candidate_prompt_version=None,
                resulting_candidate_prompt_version=None,
                authorization=_authorization(),
                recorded_at="2026-08-30T09:05:00Z",
            ),
        )

    assert "immutable" in str(exc_info.value)
    reloaded = repository.get_prompt_version("explain.v1", "foundation.explain.v1")
    assert reloaded is not None
    assert reloaded.system_instructions == active.system_instructions


def test_sqlalchemy_prompt_read_detects_out_of_band_tamper(tmp_path: Path) -> None:
    repository = _prompt_repository(tmp_path)
    _promote_explain_v2(repository)

    with repository._session_factory() as session:
        model = session.get(PromptDefinitionVersionModel, ("explain.v1", "foundation.explain.v2"))
        assert model is not None
        model.system_instructions = "Tampered outside governance."
        session.commit()

    with raises(RuntimeError) as exc_info:
        repository.get_prompt_version("explain.v1", "foundation.explain.v2")

    assert "outside governance" in str(exc_info.value)


def test_sqlalchemy_run_repository_round_trips_provider_config_digest(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-runs.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyWorkflowPackRunRepository(database_url)
    record = replace(
        _workflow_pack_run_record(run_id="run-repro-1"),
        provider_config_sha256="a" * 64,
    )

    repository.save_run(record)
    loaded = repository.get_run(run_id="run-repro-1")

    assert loaded is not None
    assert loaded.provider_config_sha256 == "a" * 64
