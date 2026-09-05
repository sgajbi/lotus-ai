from pathlib import Path

from app.repositories.sqlalchemy_caller_policy_repository import SqlAlchemyCallerPolicyRepository
from tests.support.migration_runner import upgrade_database_to_head


def test_sqlalchemy_caller_policy_repository_lists_seeded_policies(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'caller-policy-repository.db'}"
    upgrade_database_to_head(database_url)

    repository = SqlAlchemyCallerPolicyRepository(database_url)
    policies = repository.list_policies()

    assert len(policies) >= 5
    assert any(policy.caller_app == "lotus-platform" for policy in policies)
    assert any(policy.caller_app == "lotus-gateway" for policy in policies)
    assert any(policy.caller_app == "lotus-performance" for policy in policies)
    assert any(policy.caller_app == "lotus-idea" for policy in policies)


def test_sqlalchemy_caller_policy_repository_survives_reopen(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'caller-policy-repository-reopen.db'}"
    upgrade_database_to_head(database_url)

    first_repository = SqlAlchemyCallerPolicyRepository(database_url)
    first_policy = first_repository.get_policy("lotus-manage")
    second_repository = SqlAlchemyCallerPolicyRepository(database_url)
    second_policy = second_repository.get_policy("lotus-manage")
    lotus_advise_policy = second_repository.get_policy("lotus-advise")
    lotus_performance_policy = second_repository.get_policy("lotus-performance")
    lotus_gateway_policy = second_repository.get_policy("lotus-gateway")
    lotus_idea_policy = second_repository.get_policy("lotus-idea")
    lotus_platform_policy = second_repository.get_policy("lotus-platform")

    assert first_policy is not None
    assert second_policy is not None
    assert first_policy.allowed_task_ids == second_policy.allowed_task_ids
    assert second_policy.restricted_tenant_ids == ["tenant-sg-001"]
    assert lotus_advise_policy is not None
    assert lotus_advise_policy.allowed_task_ids == [
        "explain.v1",
        "summarize.v1",
        "knowledge_answer.v1",
    ]
    assert lotus_advise_policy.restricted_tenant_ids == ["tenant-us-002", "tenant-sg-001"]
    assert lotus_performance_policy is not None
    assert lotus_performance_policy.allowed_task_ids == ["explain.v1"]
    assert lotus_gateway_policy is not None
    assert lotus_gateway_policy.allowed_task_ids == ["explain.v1"]
    assert lotus_gateway_policy.tenant_policy_mode == "OPTIONAL"
    assert lotus_idea_policy is not None
    assert lotus_idea_policy.allowed_task_ids == ["explain.v1"]
    assert lotus_idea_policy.allow_live_provider is False
    assert lotus_idea_policy.tenant_policy_mode == "RESTRICTED"
    assert lotus_idea_policy.restricted_tenant_ids == ["tenant-private-bank-sg", "tenant-sg-001"]
    assert lotus_platform_policy is not None
    assert lotus_platform_policy.allow_audit_read_all_tenants is True
    assert all(
        not policy.allow_audit_read_all_tenants
        for policy in second_repository.list_policies()
        if policy.caller_app != "lotus-platform"
    )


def test_sqlalchemy_caller_policy_repository_returns_none_for_unknown_caller(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'caller-policy-repository-missing.db'}"
    upgrade_database_to_head(database_url)

    repository = SqlAlchemyCallerPolicyRepository(database_url)

    assert repository.get_policy("unknown-app") is None
