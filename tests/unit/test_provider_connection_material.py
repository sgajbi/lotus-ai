"""Governed per-identity connection material (issue #295, S1).

The settings pair seeds two entries so behaviour at two candidates is
byte-equivalent to before; declared JSON entries add (or deliberately
override) identities; a third identity resolves a full execution config
under the primary's shared protections; malformed material fails closed
with bounded findings; credentials stay environment references.
"""

import json

import pytest

from app.config import settings
from app.contracts.model_catalogue import derive_model_catalogue_entry_id
from app.services.provider_connection_material import (
    configured_connection_materials,
    connection_material_findings,
    derive_candidate_execution_config,
    reset_connection_material_cache,
)
from app.services.provider_execution_config import (
    derive_fallback_execution_config,
    resolve_provider_execution_config,
)


def _pair_settings() -> None:
    settings.provider_mode = "openai"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_model_version = "gpt-5.4-2026-06-01"
    settings.live_text_api_base = "https://api.openai.com/v1"
    settings.live_text_provider_api_key = "primary-secret"
    settings.live_text_fallback_provider_id = "text.local"
    settings.live_text_fallback_model_id = "qwen2.5"
    settings.live_text_fallback_model_version = None
    settings.live_text_fallback_api_base = "http://localhost:1234/v1"
    settings.live_text_fallback_api_key = None


def _entry(provider: str, model: str, version: str | None) -> str:
    return derive_model_catalogue_entry_id(
        provider_id=provider, model_revision=version or model, deployment=None
    )


def test_settings_pair_seeds_two_identities_byte_equivalently() -> None:
    _pair_settings()
    config = resolve_provider_execution_config()

    materials = configured_connection_materials(config)
    primary_id = _entry("text.openai", "gpt-5.4", "gpt-5.4-2026-06-01")
    alternate_id = _entry("text.local", "qwen2.5", None)
    assert set(materials) == {primary_id, alternate_id}

    # The seam returns EXACTLY the configs the pair always produced: the
    # primary config itself and the derived alternate - byte-equivalence at
    # two candidates is the S1 invariant.
    assert derive_candidate_execution_config(config, primary_id) is config
    assert derive_candidate_execution_config(config, alternate_id) == (
        derive_fallback_execution_config(config)
    )
    assert derive_candidate_execution_config(config, "entry-unknown") is None


def test_a_third_identity_resolves_under_the_primary_protections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The steering's acceptance: a third approved identity resolves a full
    candidate config from governed connection material - same timeout,
    retry, output, sampling and enforcement posture as the primary, its own
    endpoint and credential reference."""

    _pair_settings()
    monkeypatch.setenv("THIRD_IDENTITY_KEY", "third-secret")
    settings.provider_connections_json = json.dumps(
        [
            {
                "provider_id": "text.regional",
                "model_id": "claude-sonnet-5",
                "model_version": "claude-sonnet-5-2026-05",
                "api_base": "https://regional.example/v1",
                "api_key_env": "THIRD_IDENTITY_KEY",
            }
        ]
    )
    config = resolve_provider_execution_config()

    materials = configured_connection_materials(config)
    assert len(materials) == 3
    third_id = _entry("text.regional", "claude-sonnet-5", "claude-sonnet-5-2026-05")

    third = derive_candidate_execution_config(config, third_id)
    assert third is not None
    assert third.provider_id == "text.regional"
    assert third.api_base == "https://regional.example/v1"
    assert third.api_key == "third-secret"
    assert third.routing_strategy == "fixed"
    # Shared protections: a third candidate never runs under a weaker posture.
    assert third.timeout_ms == config.timeout_ms
    assert third.retry_limit == config.retry_limit
    assert third.max_output_tokens == config.max_output_tokens
    assert third.enforcement == config.enforcement
    assert third.failed_attempt_cost_posture == config.failed_attempt_cost_posture


def test_declared_material_overrides_the_seeded_identity() -> None:
    _pair_settings()
    settings.provider_connections_json = json.dumps(
        [
            {
                "provider_id": "text.local",
                "model_id": "qwen2.5",
                "api_base": "http://replacement-host:9999/v1",
            }
        ]
    )
    config = resolve_provider_execution_config()

    alternate_id = _entry("text.local", "qwen2.5", None)
    materials = configured_connection_materials(config)
    assert len(materials) == 2
    assert materials[alternate_id].api_base == "http://replacement-host:9999/v1"


def test_a_declared_override_drives_the_actual_execution_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #298: one catalogue identity -> one effective connection material
    -> one execution config. A declared override of a seeded identity is not
    merely visible in configuration inspection - it IS the config the
    candidate executes under, endpoint and credential reference both."""

    _pair_settings()
    settings.live_text_fallback_api_key = "legacy-alternate-secret"
    monkeypatch.setenv("REPLACEMENT_PRIMARY_KEY", "replacement-secret")
    settings.provider_connections_json = json.dumps(
        [
            {
                "provider_id": "text.openai",
                "model_id": "gpt-5.4",
                "model_version": "gpt-5.4-2026-06-01",
                "api_base": "https://override.example/v1",
                "api_key_env": "REPLACEMENT_PRIMARY_KEY",
            },
            {
                "provider_id": "text.local",
                "model_id": "qwen2.5",
                "api_base": "http://replacement-host:9999/v1",
            },
        ]
    )
    config = resolve_provider_execution_config()
    primary_id = _entry("text.openai", "gpt-5.4", "gpt-5.4-2026-06-01")
    alternate_id = _entry("text.local", "qwen2.5", None)

    primary = derive_candidate_execution_config(config, primary_id)
    assert primary is not None
    assert primary.api_base == "https://override.example/v1"
    assert primary.api_key == "replacement-secret"
    # The override replaces the connection, never the identity: inspection
    # and execution resolve the same candidate.
    assert (primary.provider_id, primary.model_id, primary.model_version) == (
        config.provider_id,
        config.model_id,
        config.model_version,
    )
    # Shared protections still come from the primary config.
    assert primary.timeout_ms == config.timeout_ms
    assert primary.enforcement == config.enforcement

    alternate = derive_candidate_execution_config(config, alternate_id)
    assert alternate is not None
    assert alternate.api_base == "http://replacement-host:9999/v1"
    # The override replaces the credential reference too: none declared means
    # no credential - the legacy alternate secret never silently follows the
    # replacement endpoint.
    assert alternate.api_key is None
    assert alternate.provider_id == "text.local"

    # Inspection truth == execution truth, per identity.
    materials = configured_connection_materials(config)
    assert materials[primary_id].api_base == primary.api_base
    assert materials[alternate_id].api_base == alternate.api_base


def test_a_deployment_scoped_identity_is_its_own_catalogue_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #303: deployment participates in the catalogue identity exactly
    as the catalogue derives it - a deployment-scoped declared entry is a
    DIFFERENT governed identity from the direct-API entry of the same
    provider and revision, and its execution config carries the deployment
    so binding, debits and audit name the right entry."""

    _pair_settings()
    monkeypatch.setenv("EU_IDENTITY_KEY", "eu-secret")
    settings.provider_connections_json = json.dumps(
        [
            {
                "provider_id": "text.regional",
                "model_id": "claude-sonnet-5",
                "model_version": "claude-sonnet-5-2026-05",
                "api_base": "https://eu.example/v1",
                "api_key_env": "EU_IDENTITY_KEY",
                "deployment": "eu-frankfurt-1",
                "region": "eu-central",
            }
        ]
    )
    config = resolve_provider_execution_config()

    scoped_id = derive_model_catalogue_entry_id(
        provider_id="text.regional",
        model_revision="claude-sonnet-5-2026-05",
        deployment="eu-frankfurt-1",
    )
    unscoped_id = derive_model_catalogue_entry_id(
        provider_id="text.regional",
        model_revision="claude-sonnet-5-2026-05",
        deployment=None,
    )
    assert scoped_id != unscoped_id

    materials = configured_connection_materials(config)
    assert scoped_id in materials
    assert unscoped_id not in materials
    assert materials[scoped_id].deployment == "eu-frankfurt-1"
    assert materials[scoped_id].region == "eu-central"

    derived = derive_candidate_execution_config(config, scoped_id)
    assert derived is not None
    assert derived.deployment == "eu-frankfurt-1"
    assert derived.api_base == "https://eu.example/v1"
    assert derived.api_key == "eu-secret"
    # The direct-API identity of the same provider+revision has no material.
    assert derive_candidate_execution_config(config, unscoped_id) is None


def test_malformed_declared_material_fails_closed_with_bounded_findings() -> None:
    _pair_settings()

    settings.provider_connections_json = "{not json"
    assert any("not valid JSON" in finding for finding in connection_material_findings())

    settings.provider_connections_json = json.dumps([{"provider_id": "x"}])
    assert any(
        "requires a non-empty 'model_id'" in finding for finding in connection_material_findings()
    )

    settings.provider_connections_json = json.dumps(
        [
            {"provider_id": "p", "model_id": "m", "api_base": "http://a"},
            {"provider_id": "p", "model_id": "m", "api_base": "http://b"},
        ]
    )
    config = resolve_provider_execution_config()
    with pytest.raises(ValueError, match="declared more than once"):
        configured_connection_materials(config)

    settings.provider_connections_json = json.dumps(
        [{"provider_id": "p", "model_id": "m", "api_base": "http://a", "deployment": "  "}]
    )
    assert any("'deployment' must be a non-empty" in f for f in connection_material_findings())

    settings.provider_connections_json = json.dumps(
        [{"provider_id": "p", "model_id": "m", "api_base": "http://a", "region": ""}]
    )
    assert any("'region' must be a non-empty" in f for f in connection_material_findings())

    settings.provider_connections_json = "[]"
    reset_connection_material_cache()
    assert connection_material_findings() == []


def test_a_missing_credential_reference_resolves_to_no_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unset api_key_env resolves to None - the existing require_api_key
    fence then refuses at execution with INVALID_LIVE_CONFIGURATION rather
    than this module inventing or leaking anything."""

    _pair_settings()
    monkeypatch.delenv("ABSENT_KEY_ENV", raising=False)
    settings.provider_connections_json = json.dumps(
        [
            {
                "provider_id": "text.regional",
                "model_id": "claude-sonnet-5",
                "api_base": "https://regional.example/v1",
                "api_key_env": "ABSENT_KEY_ENV",
            }
        ]
    )
    config = resolve_provider_execution_config()
    third = derive_candidate_execution_config(
        config, _entry("text.regional", "claude-sonnet-5", None)
    )
    assert third is not None
    assert third.api_key is None


def test_a_same_provider_sibling_fallback_is_a_legitimate_candidate() -> None:
    """Issue #314 fossil removal: the pair-era rejection of ANY same-provider
    alternate is gone - breaker state is candidate-scoped (#304), so a
    same-provider sibling model is real failover. Only a fallback that is
    the SAME candidate as the primary remains a misconfiguration."""

    from app.services.provider_execution_config import fallback_configuration_findings

    _pair_settings()
    settings.routing_strategy = "ordered_fallback"
    settings.live_text_fallback_provider_id = "text.openai"
    settings.live_text_fallback_model_id = "gpt-5.4-mini"
    settings.live_text_fallback_model_version = None
    settings.live_text_fallback_api_base = "https://sibling.example/v1"
    config = resolve_provider_execution_config()
    assert fallback_configuration_findings(config) == []

    # The same candidate as the primary provides no failover at all.
    settings.live_text_fallback_model_id = "gpt-5.4"
    settings.live_text_fallback_model_version = "gpt-5.4-2026-06-01"
    config = resolve_provider_execution_config()
    findings = fallback_configuration_findings(config)
    assert any("no failover" in finding for finding in findings)
