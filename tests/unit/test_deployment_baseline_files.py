from pathlib import Path


def test_docker_compose_represents_prod_shaped_local_baseline() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "postgres:16-alpine" in compose_text
    assert "./scripts/docker/start-api.sh" in compose_text
    assert "./scripts/docker/start-worker.sh" in compose_text
    assert "postgresql+psycopg://lotus:lotus@postgres:5432/lotus_ai" in compose_text
    assert "LOTUS_AI_ARTIFACT_OBJECT_STORE_MODE: filesystem" in compose_text
    assert "LOTUS_AI_SECRET_SOURCE_MODE: local_or_unspecified" in compose_text
    assert '"8140:8140"' in compose_text
    assert '"5432:5432"' not in compose_text
    assert '"6379:6379"' not in compose_text


def test_env_example_matches_prod_shaped_local_baseline() -> None:
    env_example_text = Path(".env.example").read_text(encoding="utf-8")

    assert (
        "LOTUS_AI_DATABASE_URL=postgresql+psycopg://lotus:lotus@postgres:5432/lotus_ai"
        in env_example_text
    )
    assert "LOTUS_AI_ARTIFACT_OBJECT_STORE_MODE=filesystem" in env_example_text
    assert "LOTUS_AI_SECRET_SOURCE_MODE=local_or_unspecified" in env_example_text
    assert "LOTUS_AI_ASYNC_CUTOVER_STATE=dedicated_workers_active" in env_example_text


def test_readme_documents_internal_infra_ports_stay_unpublished() -> None:
    readme_text = Path("README.md").read_text(encoding="utf-8")

    assert "PostgreSQL stays internal to the Compose network on `postgres:5432`" in readme_text
    assert "Redis stays internal to the Compose network on `redis:6379`" in readme_text
    assert "only the application port `8140` is published" in readme_text
