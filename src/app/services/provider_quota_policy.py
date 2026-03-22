from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.config import settings
from app.contracts.providers import (
    ProviderExecutionRequest,
    ProviderFailureCategory,
    ProviderQuotaDescriptor,
    ProviderQuotaPolicyResponse,
    ProviderQuotaScope,
)
from app.providers.base import ProviderExecutionError
from app.services.capability_catalog import get_capability_by_task_id
from app.services.provider_operations_store import get_provider_operations_store

_MATCHING_ORDER = [
    ProviderQuotaScope.TENANT,
    ProviderQuotaScope.CALLER_APP,
    ProviderQuotaScope.TASK,
    ProviderQuotaScope.DEFAULT,
]


@dataclass(frozen=True)
class ParsedProviderQuotaPolicy:
    quota_enforced: bool
    configuration_valid: bool
    findings: list[str]
    quotas: list[ProviderQuotaDescriptor]


def build_provider_quota_policy() -> ProviderQuotaPolicyResponse:
    parsed = parse_provider_quota_policy()
    return ProviderQuotaPolicyResponse(
        service=settings.service_name,
        version=settings.service_version,
        provider_mode=settings.provider_mode,
        quota_enforced=parsed.quota_enforced,
        configuration_valid=parsed.configuration_valid,
        findings=parsed.findings,
        matching_order=_MATCHING_ORDER,
        quotas=parsed.quotas,
    )


def parse_provider_quota_policy() -> ParsedProviderQuotaPolicy:
    findings: list[str] = []
    configuration_valid = True
    quotas: list[ProviderQuotaDescriptor] = []
    current_counts = _load_quota_counts()

    task_entries, task_findings = _parse_quota_mapping(
        settings.live_text_task_quota_limits,
        scope=ProviderQuotaScope.TASK,
        current_counts=current_counts,
    )
    caller_entries, caller_findings = _parse_quota_mapping(
        settings.live_text_caller_quota_limits,
        scope=ProviderQuotaScope.CALLER_APP,
        current_counts=current_counts,
    )
    tenant_entries, tenant_findings = _parse_quota_mapping(
        settings.live_text_tenant_quota_limits,
        scope=ProviderQuotaScope.TENANT,
        current_counts=current_counts,
    )
    default_quota, default_findings = _parse_default_quota(
        settings.live_text_default_quota_limit,
        current_counts=current_counts,
    )

    findings.extend(task_findings)
    findings.extend(caller_findings)
    findings.extend(tenant_findings)
    findings.extend(default_findings)

    invalid_task_ids = [
        entry.scope_key
        for entry in task_entries
        if get_capability_by_task_id(entry.scope_key) is None
        or entry.scope_key.startswith("knowledge_")
    ]
    if invalid_task_ids:
        configuration_valid = False
        findings.append(
            "Provider quota task scopes contain unknown or retrieval-backed task ids, which are not valid for live text-generation quota enforcement."
        )

    quotas.extend(tenant_entries)
    quotas.extend(caller_entries)
    quotas.extend(task_entries)
    if default_quota is not None:
        quotas.append(default_quota)

    if findings:
        configuration_valid = False

    if settings.live_text_quota_enforced and not quotas:
        configuration_valid = False
        findings.append(
            "Live-provider quota enforcement is enabled but no valid quota scopes are configured."
        )

    if not findings:
        findings.append("Provider quota posture is internally consistent for the current phase.")

    return ParsedProviderQuotaPolicy(
        quota_enforced=settings.live_text_quota_enforced,
        configuration_valid=configuration_valid,
        findings=findings,
        quotas=quotas,
    )


def enforce_provider_quota(request: ProviderExecutionRequest) -> None:
    parsed = parse_provider_quota_policy()
    if not parsed.quota_enforced:
        return
    if not parsed.configuration_valid:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.INVALID_QUOTA_CONFIGURATION,
            message="Live-provider quota configuration is invalid and cannot be enforced safely.",
        )

    applicable = _matching_quota_descriptors(parsed.quotas, request=request)
    for quota in applicable:
        if quota.current_request_count >= quota.request_limit:
            raise ProviderExecutionError(
                category=ProviderFailureCategory.QUOTA_EXCEEDED,
                message=(
                    f"Live-provider quota exceeded for {quota.scope.value.lower()} scope "
                    f"'{quota.scope_key}'."
                ),
            )

    for quota in applicable:
        _increment_quota_count(scope=quota.scope, scope_key=quota.scope_key)


def reset_provider_quota_counters() -> None:
    # Quota reset remains a test-only convenience helper until governed rollover/reset semantics
    # are introduced in later RFC-0005 slices.
    from app.services.provider_operations_store import reset_provider_operations_store_cache

    reset_provider_operations_store_cache()


def _parse_quota_mapping(
    raw_value: str,
    *,
    scope: ProviderQuotaScope,
    current_counts: dict[tuple[ProviderQuotaScope, str], int],
) -> tuple[list[ProviderQuotaDescriptor], list[str]]:
    descriptors: list[ProviderQuotaDescriptor] = []
    findings: list[str] = []
    if not raw_value.strip():
        return (descriptors, findings)

    for item in [segment.strip() for segment in raw_value.split(",") if segment.strip()]:
        if "=" not in item:
            findings.append(
                f"Provider quota entry '{item}' is malformed; expected '<scope_key>=<positive_limit>'."
            )
            continue
        scope_key, raw_limit = [segment.strip() for segment in item.split("=", maxsplit=1)]
        if not scope_key:
            findings.append("Provider quota entries must include a non-empty scope key before '='.")
            continue
        limit = _parse_positive_limit(raw_limit, scope_key=scope_key, findings=findings)
        if limit is None:
            continue
        descriptors.append(
            _build_quota_descriptor(
                scope=scope,
                scope_key=scope_key,
                request_limit=limit,
                current_counts=current_counts,
            )
        )

    return (_dedupe_quota_descriptors(descriptors), findings)


def _parse_default_quota(
    raw_limit: int | None,
    *,
    current_counts: dict[tuple[ProviderQuotaScope, str], int],
) -> tuple[ProviderQuotaDescriptor | None, list[str]]:
    findings: list[str] = []
    if raw_limit is None:
        return (None, findings)
    if raw_limit <= 0:
        findings.append("Default provider quota limit must be a positive integer.")
        return (None, findings)
    return (
        _build_quota_descriptor(
            scope=ProviderQuotaScope.DEFAULT,
            scope_key="global",
            request_limit=raw_limit,
            current_counts=current_counts,
        ),
        findings,
    )


def _parse_positive_limit(
    raw_limit: str,
    *,
    scope_key: str,
    findings: list[str],
) -> int | None:
    try:
        parsed_limit = int(raw_limit)
    except ValueError:
        findings.append(
            f"Provider quota limit '{raw_limit}' for scope '{scope_key}' is not an integer."
        )
        return None
    if parsed_limit <= 0:
        findings.append(f"Provider quota limit for scope '{scope_key}' must be a positive integer.")
        return None
    return parsed_limit


def _build_quota_descriptor(
    *,
    scope: ProviderQuotaScope,
    scope_key: str,
    request_limit: int,
    current_counts: dict[tuple[ProviderQuotaScope, str], int],
) -> ProviderQuotaDescriptor:
    counter_key = (scope, scope_key)
    current_count = current_counts.get(counter_key, 0)
    return ProviderQuotaDescriptor(
        scope=scope,
        scope_key=scope_key,
        request_limit=request_limit,
        current_request_count=current_count,
        remaining_request_count=max(request_limit - current_count, 0),
        notes=_build_quota_notes(scope=scope, scope_key=scope_key),
    )


def _build_quota_notes(*, scope: ProviderQuotaScope, scope_key: str) -> str:
    if scope == ProviderQuotaScope.DEFAULT:
        return "Applies to all accepted live-provider requests when no narrower quota scope blocks earlier."
    if scope == ProviderQuotaScope.TASK:
        return f"Applies to accepted live-provider requests for task '{scope_key}'."
    if scope == ProviderQuotaScope.CALLER_APP:
        return f"Applies to accepted live-provider requests from caller app '{scope_key}'."
    return f"Applies to accepted live-provider requests for tenant '{scope_key}'."


def _matching_quota_descriptors(
    quotas: Iterable[ProviderQuotaDescriptor],
    *,
    request: ProviderExecutionRequest,
) -> list[ProviderQuotaDescriptor]:
    current_counts = _load_quota_counts()
    matched: list[ProviderQuotaDescriptor] = []
    for quota in quotas:
        if quota.scope == ProviderQuotaScope.DEFAULT:
            matched.append(
                _build_quota_descriptor(
                    scope=quota.scope,
                    scope_key=quota.scope_key,
                    request_limit=quota.request_limit,
                    current_counts=current_counts,
                )
            )
        elif quota.scope == ProviderQuotaScope.TASK and quota.scope_key == request.task_id:
            matched.append(
                _build_quota_descriptor(
                    scope=quota.scope,
                    scope_key=quota.scope_key,
                    request_limit=quota.request_limit,
                    current_counts=current_counts,
                )
            )
        elif quota.scope == ProviderQuotaScope.CALLER_APP and quota.scope_key == request.caller_app:
            matched.append(
                _build_quota_descriptor(
                    scope=quota.scope,
                    scope_key=quota.scope_key,
                    request_limit=quota.request_limit,
                    current_counts=current_counts,
                )
            )
        elif (
            quota.scope == ProviderQuotaScope.TENANT
            and request.tenant_id is not None
            and quota.scope_key == request.tenant_id
        ):
            matched.append(
                _build_quota_descriptor(
                    scope=quota.scope,
                    scope_key=quota.scope_key,
                    request_limit=quota.request_limit,
                    current_counts=current_counts,
                )
            )
    return sorted(matched, key=lambda item: _MATCHING_ORDER.index(item.scope))


def _dedupe_quota_descriptors(
    descriptors: list[ProviderQuotaDescriptor],
) -> list[ProviderQuotaDescriptor]:
    unique: dict[tuple[ProviderQuotaScope, str], ProviderQuotaDescriptor] = {}
    for descriptor in descriptors:
        unique[(descriptor.scope, descriptor.scope_key)] = descriptor
    return sorted(
        unique.values(),
        key=lambda item: (_MATCHING_ORDER.index(item.scope), item.scope_key),
    )


def _load_quota_counts() -> dict[tuple[ProviderQuotaScope, str], int]:
    repository = get_provider_operations_store()
    return {
        (record.scope, record.scope_key): record.request_count
        for record in repository.list_quota_states()
    }


def _increment_quota_count(*, scope: ProviderQuotaScope, scope_key: str) -> None:
    repository = get_provider_operations_store()
    repository.increment_quota_state(
        scope=scope,
        scope_key=scope_key,
        amount=1,
        updated_at=_utcnow(),
    )


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()
