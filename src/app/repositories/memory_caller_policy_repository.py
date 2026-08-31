from __future__ import annotations

from copy import deepcopy

from app.contracts.access_control import (
    CallerLifecycleStatus,
    CallerPolicyDescriptor,
    TenantPolicyMode,
)
from app.repositories.caller_policy_repository import CallerPolicyRepository

_DEFAULT_POLICIES = [
    CallerPolicyDescriptor(
        caller_app="lotus-manage",
        lifecycle_status=CallerLifecycleStatus.ACTIVE,
        description="Primary managed-app integration for bounded task execution.",
        allowed_task_ids=[
            "explain.v1",
            "summarize.v1",
            "generate_structured.v1",
            "knowledge_search.v1",
            "knowledge_answer.v1",
        ],
        allowed_retrieval_source_ids=["lotus-platform-rfcs", "lotus-ai-architecture"],
        allow_live_provider=True,
        allow_async_control=False,
        allow_prompt_control=False,
        allow_provider_control=False,
        allow_audit_read_all_tenants=False,
        tenant_policy_mode=TenantPolicyMode.RESTRICTED,
        restricted_tenant_ids=["tenant-sg-001"],
    ),
    CallerPolicyDescriptor(
        caller_app="lotus-advise",
        lifecycle_status=CallerLifecycleStatus.ACTIVE,
        description="Advisory application integration with bounded task access.",
        allowed_task_ids=["explain.v1", "summarize.v1", "knowledge_answer.v1"],
        allowed_retrieval_source_ids=["lotus-platform-rfcs"],
        allow_live_provider=False,
        allow_async_control=False,
        allow_prompt_control=False,
        allow_provider_control=False,
        allow_audit_read_all_tenants=False,
        tenant_policy_mode=TenantPolicyMode.RESTRICTED,
        restricted_tenant_ids=["tenant-us-002", "tenant-sg-001"],
    ),
    CallerPolicyDescriptor(
        caller_app="lotus-platform",
        lifecycle_status=CallerLifecycleStatus.ACTIVE,
        description="Platform operator and automation caller for governed control planes.",
        allowed_task_ids=[],
        allowed_retrieval_source_ids=[],
        allow_live_provider=False,
        allow_async_control=True,
        allow_prompt_control=True,
        allow_provider_control=True,
        allow_audit_read_all_tenants=True,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        restricted_tenant_ids=[],
    ),
    CallerPolicyDescriptor(
        caller_app="lotus-performance",
        lifecycle_status=CallerLifecycleStatus.ACTIVE,
        description="First-production-use-case integration for explanation-only analytics commentary.",
        allowed_task_ids=["explain.v1"],
        allowed_retrieval_source_ids=[],
        allow_live_provider=False,
        allow_async_control=False,
        allow_prompt_control=False,
        allow_provider_control=False,
        allow_audit_read_all_tenants=False,
        tenant_policy_mode=TenantPolicyMode.RESTRICTED,
        restricted_tenant_ids=["tenant-sg-001"],
    ),
    CallerPolicyDescriptor(
        caller_app="lotus-gateway",
        lifecycle_status=CallerLifecycleStatus.ACTIVE,
        description=(
            "Gateway BFF caller for source-bounded advisor brief generation over pre-assembled "
            "portfolio and performance facts."
        ),
        allowed_task_ids=["explain.v1"],
        allowed_retrieval_source_ids=[],
        allow_live_provider=True,
        allow_async_control=False,
        allow_prompt_control=False,
        allow_provider_control=False,
        allow_audit_read_all_tenants=False,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        restricted_tenant_ids=[],
    ),
    CallerPolicyDescriptor(
        caller_app="lotus-idea",
        lifecycle_status=CallerLifecycleStatus.ACTIVE,
        description=(
            "Idea service caller for review-gated explanation generation over redacted "
            "opportunity evidence packets."
        ),
        allowed_task_ids=["explain.v1"],
        allowed_retrieval_source_ids=[],
        allow_live_provider=False,
        allow_async_control=False,
        allow_prompt_control=False,
        allow_provider_control=False,
        allow_audit_read_all_tenants=False,
        tenant_policy_mode=TenantPolicyMode.RESTRICTED,
        restricted_tenant_ids=["tenant-sg-001"],
    ),
    CallerPolicyDescriptor(
        caller_app="lotus-workbench",
        lifecycle_status=CallerLifecycleStatus.ACTIVE,
        description="Workbench caller for bounded retrieval exploration.",
        allowed_task_ids=["knowledge_search.v1", "knowledge_answer.v1"],
        allowed_retrieval_source_ids=["lotus-platform-rfcs", "lotus-ai-architecture"],
        allow_live_provider=False,
        allow_async_control=False,
        allow_prompt_control=False,
        allow_provider_control=False,
        allow_audit_read_all_tenants=False,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        restricted_tenant_ids=[],
    ),
    CallerPolicyDescriptor(
        caller_app="lotus-ai-provider-operations",
        lifecycle_status=CallerLifecycleStatus.ACTIVE,
        description=(
            "Internal provider-operations recorder identity for retention and deletion "
            "confirmations; grants no task, retrieval, or control capability."
        ),
        allowed_task_ids=[],
        allowed_retrieval_source_ids=[],
        allow_live_provider=False,
        allow_async_control=False,
        allow_prompt_control=False,
        allow_provider_control=False,
        allow_audit_read_all_tenants=False,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        restricted_tenant_ids=[],
    ),
]


class InMemoryCallerPolicyRepository(CallerPolicyRepository):
    def __init__(self) -> None:
        self._policies = {policy.caller_app: deepcopy(policy) for policy in _DEFAULT_POLICIES}

    def list_policies(self) -> list[CallerPolicyDescriptor]:
        policies = [deepcopy(policy) for policy in self._policies.values()]
        policies.sort(key=lambda policy: policy.caller_app)
        return policies

    def get_policy(self, caller_app: str) -> CallerPolicyDescriptor | None:
        policy = self._policies.get(caller_app)
        if policy is None:
            return None
        return deepcopy(policy)
