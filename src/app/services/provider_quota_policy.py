from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

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

_MATCHING_ORDER = [
    ProviderQuotaScope.TENANT,
    ProviderQuotaScope.CALLER_APP,
    ProviderQuotaScope.TASK,
    ProviderQuotaScope.DEFAULT,
]
_COUNTERS: dict[tuple[ProviderQuotaScope, str], int] = {}


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

    task_entries, task_findings = _parse_quota_mapping(
        settings.live_text_task_quota_limits,
        scope=ProviderQuotaScope.TASK,
    )
    caller_entries, caller_findings = _parse_quota_mapping(
        settings.live_text_caller_quota_limits,
        scope=ProviderQuotaScope.CALLER_APP,
    )
    tenant_entries, tenant_findings = _parse_quota_mapping(
        settings.live_text_tenant_quota_limits,
        scope=ProviderQuotaScope.TENANT,
    )
    default_quota, default_findings = _parse_default_quota(settings.live_text_default_quota_limit)

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
        counter_key = (quota.scope, quota.scope_key)
        _COUNTERS[counter_key] = _COUNTERS.get(counter_key, 0) + 1


def reset_provider_quota_counters() -> None:
    _COUNTERS.clear()


def _parse_quota_mapping(
    raw_value: str,
    *,
    scope: ProviderQuotaScope,
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
            findings.append(
                "Provider quota entries must include a non-empty scope key before '='."
            )
            continue
        limit = _parse_positive_limit(raw_limit, scope_key=scope_key, findings=findings)
        if limit is None:
            continue
        descriptors.append(
            _build_quota_descriptor(
                scope=scope,
                scope_key=scope_key,
                request_limit=limit,
            )
        )

    return (_dedupe_quota_descriptors(descriptors), findings)


def _parse_default_quota(
    raw_limit: int | None,
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
        findings.append(
            f"Provider quota limit for scope '{scope_key}' must be a positive integer."
        )
        return None
    return parsed_limit


def _build_quota_descriptor(
    *,
    scope: ProviderQuotaScope,
    scope_key: str,
    request_limit: int,
) -> ProviderQuotaDescriptor:
    counter_key = (scope, scope_key)
    current_count = _COUNTERS.get(counter_key, 0)
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
    matched: list[ProviderQuotaDescriptor] = []
    for quota in quotas:
        if quota.scope == ProviderQuotaScope.DEFAULT:
            matched.append(_build_quota_descriptor(
                scope=quota.scope,
                scope_key=quota.scope_key,
                request_limit=quota.request_limit,
            ))
        elif quota.scope == ProviderQuotaScope.TASK and quota.scope_key == request.task_id:
            matched.append(_build_quota_descriptor(
                scope=quota.scope,
                scope_key=quota.scope_key,
                request_limit=quota.request_limit,
            ))
        elif quota.scope == ProviderQuotaScope.CALLER_APP and quota.scope_key == request.caller_app:
            matched.append(_build_quota_descriptor(
                scope=quota.scope,
                scope_key=quota.scope_key,
                request_limit=quota.request_limit,
            ))
        elif (
            quota.scope == ProviderQuotaScope.TENANT
            and request.tenant_id is not None
            and quota.scope_key == request.tenant_id
        ):
            matched.append(_build_quota_descriptor(
                scope=quota.scope,
                scope_key=quota.scope_key,
                request_limit=quota.request_limit,
            ))
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
