"""Governed per-identity connection material (issue #295, S1).

The serving universe is catalogue-derived (#244), but connection material -
endpoint and credential - lived in exactly two settings slots, so no third
approved identity could legally serve. This module gives every governed
identity its own connection entry:

- the legacy primary/fallback settings pair is the SEED (exactly as the
  legacy cost scalars seeded the rate-card catalogue): with only the pair
  configured, behaviour is byte-equivalent to before;
- ``LOTUS_AI_PROVIDER_CONNECTIONS_JSON`` declares additional identities (or
  overrides a seeded one) as ``{provider_id, model_id, model_version?,
  api_base, api_key_env?}`` - the credential is a REFERENCE to an
  environment variable, never the secret itself, and the resolved secret
  reaches only the frozen execution config, never a response, log, or
  evidence surface;
- entries key by the same catalogue identity the candidate universe
  enumerates, so resolution and eligibility can never disagree about who
  an identity is.

Ordering stays governed elsewhere: this module answers "how do I connect
to identity X", never "who serves first" - that is the S2 serving-policy
artifact. No ranking, no optimizer.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache

from app.config import settings
from app.contracts.model_catalogue import derive_candidate_identity_v2
from app.services.provider_execution_config import (
    ProviderExecutionConfig,
    derive_fallback_execution_config,
)


@dataclass(frozen=True)
class ProviderConnectionMaterial:
    """One identity's connection facts. ``api_key_env`` names the variable
    holding the credential; the secret itself is resolved lazily at config
    derivation and lives nowhere else. ``seeded`` marks material sourced
    from the legacy settings pair rather than declared JSON: a seeded entry
    renders back to exactly the legacy config (byte-equivalence), while a
    declared entry - including a deliberate override of a seeded identity -
    is the connection truth execution runs under (issue #298)."""

    entry_id: str
    provider_id: str
    model_id: str
    model_version: str | None
    api_base: str
    api_key_env: str | None
    seeded: bool = False
    # Deployment participates in the catalogue identity (issue #303); region
    # is informational residency posture - surfaced for operators, never an
    # eligibility gate until a governed residency requirement exists.
    deployment: str | None = None
    region: str | None = None


def _entry_id(
    provider_id: str,
    model_id: str,
    model_version: str | None,
    deployment: str | None = None,
) -> str:
    """The CANONICAL candidate identity for one connection entry (issue
    #314): connection material keys by the identity that cannot collide,
    matching the canonical ids the candidate universe enumerates - the
    delimiter-ambiguous v1 row key is never a resolution key here."""

    return derive_candidate_identity_v2(
        provider_id=provider_id,
        model_family=model_id,
        model_revision=model_version or model_id,
        deployment=deployment,
    )


def _parse_declared_connections(raw: str) -> list[ProviderConnectionMaterial]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "provider connection material: LOTUS_AI_PROVIDER_CONNECTIONS_JSON is not valid JSON"
        ) from exc
    if not isinstance(parsed, list):
        raise ValueError(
            "provider connection material: LOTUS_AI_PROVIDER_CONNECTIONS_JSON must be a JSON list"
        )
    materials: list[ProviderConnectionMaterial] = []
    for index, entry in enumerate(parsed):
        if not isinstance(entry, dict):
            raise ValueError(f"provider connection material: entry {index} must be a JSON object")
        provider_id = entry.get("provider_id")
        model_id = entry.get("model_id")
        api_base = entry.get("api_base")
        for name, value in (
            ("provider_id", provider_id),
            ("model_id", model_id),
            ("api_base", api_base),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"provider connection material: entry {index} requires a non-empty '{name}'"
                )
        model_version = entry.get("model_version")
        if model_version is not None and (
            not isinstance(model_version, str) or not model_version.strip()
        ):
            raise ValueError(
                f"provider connection material: entry {index} 'model_version' must be a "
                "non-empty string when present"
            )
        api_key_env = entry.get("api_key_env")
        if api_key_env is not None and (
            not isinstance(api_key_env, str) or not api_key_env.strip()
        ):
            raise ValueError(
                f"provider connection material: entry {index} 'api_key_env' must name an "
                "environment variable when present"
            )
        deployment = entry.get("deployment")
        if deployment is not None and (not isinstance(deployment, str) or not deployment.strip()):
            raise ValueError(
                f"provider connection material: entry {index} 'deployment' must be a "
                "non-empty string when present"
            )
        region = entry.get("region")
        if region is not None and (not isinstance(region, str) or not region.strip()):
            raise ValueError(
                f"provider connection material: entry {index} 'region' must be a "
                "non-empty string when present"
            )
        assert isinstance(provider_id, str) and isinstance(model_id, str)
        assert isinstance(api_base, str)
        materials.append(
            ProviderConnectionMaterial(
                entry_id=_entry_id(provider_id, model_id, model_version, deployment),
                provider_id=provider_id,
                model_id=model_id,
                model_version=model_version,
                api_base=api_base,
                api_key_env=api_key_env,
                deployment=deployment,
                region=region,
            )
        )
    return materials


@lru_cache(maxsize=1)
def _declared_connections_cached(raw: str) -> tuple[ProviderConnectionMaterial, ...]:
    return tuple(_parse_declared_connections(raw))


def configured_connection_materials(
    config: ProviderExecutionConfig,
) -> dict[str, ProviderConnectionMaterial]:
    """Every identity's connection material, keyed by catalogue entry id.

    Seed order then declared order: a declared entry for a seeded identity
    overrides the seed (declared material is the stronger, deliberate
    statement); duplicate declared identities are refused - one identity,
    one connection truth.
    """

    materials: dict[str, ProviderConnectionMaterial] = {}
    if config.provider_id and config.model_id:
        primary_id = _entry_id(config.provider_id, config.model_id, config.model_version)
        materials[primary_id] = ProviderConnectionMaterial(
            entry_id=primary_id,
            provider_id=config.provider_id,
            model_id=config.model_id,
            model_version=config.model_version,
            api_base=config.api_base,
            api_key_env=None,
            seeded=True,
        )
    if config.fallback_provider_id and config.fallback_model_id and config.fallback_api_base:
        alternate_id = _entry_id(
            config.fallback_provider_id,
            config.fallback_model_id,
            config.fallback_model_version,
        )
        materials[alternate_id] = ProviderConnectionMaterial(
            entry_id=alternate_id,
            provider_id=config.fallback_provider_id,
            model_id=config.fallback_model_id,
            model_version=config.fallback_model_version,
            api_base=config.fallback_api_base,
            api_key_env=None,
            seeded=True,
        )
    seen_declared: set[str] = set()
    for declared in _declared_connections_cached(settings.provider_connections_json):
        if declared.entry_id in seen_declared:
            raise ValueError(
                "provider connection material: identity "
                f"'{declared.entry_id}' is declared more than once"
            )
        seen_declared.add(declared.entry_id)
        materials[declared.entry_id] = declared
    return materials


def connection_material_findings() -> list[str]:
    """Bounded startup statements for malformed declared material."""

    try:
        _declared_connections_cached(settings.provider_connections_json)
    except ValueError as exc:
        return [str(exc)]
    return []


def reset_connection_material_cache() -> None:
    _declared_connections_cached.cache_clear()


def derive_candidate_execution_config(
    config: ProviderExecutionConfig, entry_id: str
) -> ProviderExecutionConfig | None:
    """The execution config one governed identity would serve under.

    The merged material map is the ONE connection authority (issue #298):
    every entry id resolves through it, so what configuration inspection
    reports and what execution runs under can never disagree. An untouched
    seeded entry renders back to exactly the config the legacy pair always
    produced (byte-equivalence at two candidates, pinned by test). A
    declared entry - a third identity or a deliberate override of a seeded
    one - builds a fixed-strategy config from its declared endpoint and
    credential reference under the SAME shared protections as the
    alternate: timeout, retry budget, output bound, sampling, task
    allowlist, and enforcement thresholds all come from the primary config
    - a declared candidate never runs under a weaker posture. A declared
    override replaces the connection whole: endpoint AND credential
    reference (an omitted ``api_key_env`` means no credential, and the
    existing require-api-key fence refuses at execution rather than the
    old secret silently following a new endpoint). Returns None for an
    identity with no connection material.
    """

    material = configured_connection_materials(config).get(entry_id)
    if material is None:
        return None
    if material.seeded:
        # By construction a seeded material is the settings pair: render the
        # primary as the config itself and the alternate as its legacy
        # derivation - byte-equivalent to the pre-material behaviour.
        if config.provider_id and config.model_id:
            primary_id = _entry_id(config.provider_id, config.model_id, config.model_version)
            if entry_id == primary_id:
                return config
        return derive_fallback_execution_config(config)
    api_key = os.environ.get(material.api_key_env) if material.api_key_env else None
    return ProviderExecutionConfig(
        provider_mode=config.provider_mode,
        rollout_state=config.rollout_state,
        provider_id=material.provider_id,
        model_id=material.model_id,
        model_version=material.model_version,
        api_base=material.api_base,
        api_key=api_key,
        deployment=material.deployment,
        allowed_task_ids=config.allowed_task_ids,
        timeout_ms=config.timeout_ms,
        retry_limit=config.retry_limit,
        failed_attempt_cost_posture=config.failed_attempt_cost_posture,
        max_output_tokens=config.max_output_tokens,
        temperature=config.temperature,
        top_p=config.top_p,
        seed=config.seed,
        enforcement=config.enforcement,
        routing_strategy="fixed",
    )
