# Getting Started

## Local Modes

There are two useful local postures for `lotus-ai`:

1. a fast local loop driven directly from the repo,
2. a prod-shaped local Docker stack with SQL-backed stores and dedicated-worker posture.

Use the first when you are changing code quickly. Use the second when you need to exercise runtime
and durability behavior more truthfully.

## Prerequisites

| Tool | Version | Needed for | Where that version is pinned |
| --- | --- | --- | --- |
| Python | 3.12 | everything | `pyproject.toml` (`requires-python = ">=3.12"`), `mypy.ini`, ruff `target-version`, all three CI lanes, and the `Dockerfile` base image |
| `make` | any | every repo-native command | `Makefile` |
| Docker | any current release | the prod-shaped stack, `make docker-build`, `make test-postgres` | `docker-compose.yml`, `Dockerfile` |

`>=3.12` permits newer interpreters, but every gate runs 3.12, so 3.12 is what reproduces the
gates locally. `uv` and `gh` are not prerequisites: `uv` is a dev dependency installed by
`make install`, and `gh` is needed only for the main-gate coverage audit and the live
branch-protection comparison.

## Fast Local Loop

From a fresh checkout, create and activate a virtual environment first — `make install` installs
into whichever interpreter `python` resolves to, and installing into a system Python fails outright
on distributions that follow PEP 668:

Linux and macOS:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

Then install dependencies from the repository root:

```bash
make install
```

Run the fast local gate:

```powershell
make check
```

Start the API directly:

```powershell
uvicorn app.main:app --reload --port 8140
```

This path is best for:

1. API and contract iteration,
2. task-runtime changes,
3. focused unit and integration work,
4. documentation and router-surface review.

## Prod-Shaped Local Docker Stack

Run the local Docker stack:

```powershell
docker compose up --build
```

The checked-in Docker stack is intentionally more realistic than a toy local setup:

1. SQL-backed stores are active by default in `.env.example`,
2. Redis-backed async queue posture is active,
3. dedicated-worker cutover is active,
4. PostgreSQL and Redis remain internal to the Compose network,
5. only the application port is published for local API access.

Important defaults from `.env.example`:

1. `LOTUS_AI_AUDIT_STORE_MODE=sqlalchemy`
2. `LOTUS_AI_PROMPT_STORE_MODE=sqlalchemy`
3. `LOTUS_AI_RETRIEVAL_STORE_MODE=sqlalchemy`
4. `LOTUS_AI_ASYNC_RUNTIME_STORE_MODE=sqlalchemy`
5. `LOTUS_AI_EVALUATION_RUNTIME_STORE_MODE=sqlalchemy`
6. `LOTUS_AI_STARTUP_READINESS_POLICY=warn`
7. `LOTUS_AI_READINESS_PROBE_POLICY=observe`
8. `LOTUS_AI_LOCAL_HEADER_CALLER_IDENTITY_ENABLED=true` for this explicit local runtime only
9. `LOTUS_AI_RETRIEVAL_MODE=disabled`
10. `LOTUS_AI_EMBEDDING_PROVIDER_MODE=disabled`

## First Checks

After startup, inspect:

1. `/health/live`
2. `/health/ready`
3. `/platform/runtime-status`
4. `/metadata`
5. `/docs`

These endpoints tell you more than a simple process-up signal:

1. `/health/ready` reflects the configured readiness-probe policy,
2. `/platform/runtime-status` shows the actual mode and store posture,
3. `/metadata` shows the active store and policy modes,
4. `/docs` shows the current public API surface.

## Startup Readiness Policy

`lotus-ai` separates startup policy from readiness-probe policy.

Important flags:

1. `LOTUS_AI_STARTUP_READINESS_POLICY`
2. `LOTUS_AI_READINESS_PROBE_POLICY`

Recommended local posture:

1. `warn`
2. `observe`

That keeps local development fast while still surfacing readiness findings through runtime-status
endpoints.

For SQL-backed or enterprise-like environments, the intended stronger posture is:

1. `enforce`
2. `degrade`

Source:

- `docs/architecture/startup-readiness-deployment-policy.md`

## Provider Mode Choices

For most local work, keep provider execution deterministic:

1. `LOTUS_AI_PROVIDER_MODE=disabled`

Only switch to live or local OpenAI-compatible providers when the work actually requires provider
behavior. When you do, use the provider switching runbook and verify the resulting runtime posture.

Source:

- `docs/runbooks/provider-mode-switching.md`

## Read Next

After the service is up:

1. use [Platform Surfaces](Platform-Surfaces) to understand the API groups,
2. use [Validation and CI](Validation-and-CI) to choose the right gate,
3. use [Operations Runbook](Operations-Runbook) when the runtime posture matters,
4. use [Troubleshooting](Troubleshooting) when startup or readiness is not behaving as expected.
