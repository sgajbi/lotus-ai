from app.repositories.memory_caller_policy_repository import InMemoryCallerPolicyRepository


def test_memory_caller_policy_repository_lists_seeded_policies() -> None:
    repository = InMemoryCallerPolicyRepository()

    policies = repository.list_policies()

    assert len(policies) >= 5
    assert policies[0].caller_app == "lotus-advise"
    assert any(policy.caller_app == "lotus-platform" for policy in policies)
    assert any(policy.caller_app == "lotus-performance" for policy in policies)
    assert any(policy.caller_app == "lotus-idea" for policy in policies)


def test_memory_caller_policy_repository_returns_policy_by_caller_app() -> None:
    repository = InMemoryCallerPolicyRepository()

    policy = repository.get_policy("lotus-manage")

    assert policy is not None
    assert policy.allow_live_provider is True
    assert policy.tenant_policy_mode.value == "RESTRICTED"
    assert policy.restricted_tenant_ids == ["tenant-sg-001"]


def test_memory_caller_policy_repository_allows_lotus_gateway_live_explain() -> None:
    repository = InMemoryCallerPolicyRepository()

    policy = repository.get_policy("lotus-gateway")

    assert policy is not None
    assert policy.allow_live_provider is True
    assert policy.allowed_task_ids == ["explain.v1"]
    assert policy.tenant_policy_mode.value == "OPTIONAL"


def test_memory_caller_policy_repository_allows_lotus_idea_review_gated_explain() -> None:
    repository = InMemoryCallerPolicyRepository()

    policy = repository.get_policy("lotus-idea")

    assert policy is not None
    assert policy.allow_live_provider is False
    assert policy.allowed_task_ids == ["explain.v1"]
    assert policy.tenant_policy_mode.value == "RESTRICTED"
    assert policy.restricted_tenant_ids == ["tenant-sg-001"]


def test_memory_caller_policy_repository_returns_none_for_unknown_caller() -> None:
    repository = InMemoryCallerPolicyRepository()

    assert repository.get_policy("unknown-app") is None


def test_memory_caller_policy_repository_grants_all_tenant_audit_only_to_platform() -> None:
    repository = InMemoryCallerPolicyRepository()

    policies = repository.list_policies()

    assert [policy.caller_app for policy in policies if policy.allow_audit_read_all_tenants] == [
        "lotus-platform"
    ]
