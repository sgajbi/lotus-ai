# lotus-ai

Governed AI execution for Lotus wealth applications.

`lotus-ai` is the shared service Lotus applications call when they need AI work done under
banking-grade controls. A calling service sends bounded business context; `lotus-ai` executes the
task against a governed model candidate and returns output that carries its own evidence — what
served it, what grounded it, how it was validated, and what it cost. Domain decisions stay with the
calling services: `lotus-ai` never owns portfolio, analytics, workflow, or advisory truth, and its
output is always marked non-authoritative until the caller applies it.

## What It Does

- **Explanations and summaries** (`explain.v1`, `summarize.v1`) — narrative output over
  caller-supplied evidence: advisor briefs, proposal memo commentary, portfolio-management memos,
  idea explanations.
- **Structured outputs** — classification, extraction, and schema-validated generation
  (`classify.v1`, `extract.v1`, `generate_structured.v1`).
- **Governed retrieval** — search and citation-carrying answers over curated, attributable sources
  (`knowledge_search.v1`, `knowledge_answer.v1`) — bounded retrieval, not a general search platform.
- **Traceable execution** — every run records its routing decision, serving identity, prompt
  version, safety verdict, grounding validation, cost evidence, and audit trail; reviewed non-stub
  runs can expose signed attestations.

Consumers integrate through one public execution contract, `POST /ai/tasks/execute`, and through
review-gated workflow packs registered for specific Lotus applications
([task execution contract](docs/guides/task-execution-contract.md),
[integration guide](docs/guides/integration-guide.md)).

## Availability

The task contracts, workflow packs, governance surfaces, and durable stores above are implemented
and tested. Live model providers are separately rollout-governed: the enabled live-provider
allowlist is narrower than the implemented capability catalog, and certified live use additionally
requires evaluation-gate and model-risk approval per pack. The current state of each capability is
maintained in [feature status and roadmap](docs/architecture/feature-status-and-roadmap.md).

## Quick Start

Prerequisites, each pinned by a source you can check:

| Tool | Version | Needed for | Where that version is pinned |
| --- | --- | --- | --- |
| Python | 3.12 | everything | `pyproject.toml` (`requires-python = ">=3.12"`), `mypy.ini`, ruff `target-version`, all three CI lanes, and the `Dockerfile` base image |
| `make` | any | every repo-native command | `Makefile` |
| Docker | any current release | the prod-shaped stack, `make docker-build`, `make test-postgres` | `docker-compose.yml`, `Dockerfile` |

`>=3.12` permits newer interpreters, but every gate — CI, type checking, lint target, and the
runtime image — runs 3.12, so 3.12 is what reproduces the gates locally.

Two tools are deliberately *not* prerequisites: `uv` is a dev dependency installed by
`make install`, and `gh` is needed only for the main-gate coverage audit and the live
branch-protection comparison, never for `make check`.

From a fresh checkout, create and activate a virtual environment first — `make install` installs
into whichever interpreter `python` resolves to, and installing into a system Python fails outright
on distributions that follow PEP 668:

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
```

Then, from the repository root:

```bash
make install
make check
uvicorn app.main:app --reload --port 8140
```

Dependencies install from `requirements-dev.lock.txt` under `--require-hashes`, so the resulting
environment is identical on any machine.

Expected result: `make check` finishes green (lint, typecheck, fast tests), and
`http://localhost:8140/docs` serves the interactive API documentation. For the prod-shaped local
stack instead, run `docker compose up --build`:
PostgreSQL stays internal to the Compose network on `postgres:5432`,
Redis stays internal to the Compose network on `redis:6379`,
and only the application port `8140` is published.

## Where To Go Next

| Topic | Start here |
| --- | --- |
| Integration | [Task execution contract](docs/guides/task-execution-contract.md), [integration guide](docs/guides/integration-guide.md), [workflow-pack owner onboarding](docs/guides/workflow-pack-owner-onboarding.md) |
| Capabilities and status | [Feature status and roadmap](docs/architecture/feature-status-and-roadmap.md), [platform surfaces](wiki/Platform-Surfaces.md) |
| Architecture | [System overview](docs/architecture/system-overview.md), [scalability and deployment](docs/architecture/scalability-and-deployment-model.md), [REPOSITORY-ENGINEERING-CONTEXT.md](REPOSITORY-ENGINEERING-CONTEXT.md) |
| Operations | [Service operations runbook](docs/runbooks/service-operations.md), [provider mode switching](docs/runbooks/provider-mode-switching.md) |
| Security and governance | [Security and governance](docs/security/security-and-governance.md) |
| Evaluation | [Evaluation strategy](docs/evals/evaluation-strategy.md) |
| Contribution | [Local standards](docs/standards/), [RFC index](docs/rfcs/README.md) |

## Architecture In Brief

A FastAPI application with explicit control-plane and data-plane seams. A task request flows
through capability validation, runtime-context construction, prompt and safety resolution, provider
or retrieval execution, evidence assembly, and audit persistence — in that order, deterministically.
Provider serving follows a governed candidate policy (order is policy, never ranking); each
candidate passes kill-switch, circuit-breaker, catalogue-binding, quota, and budget fences under
its own frozen execution config. Prompt bodies are repository-managed; prompt selection, provider
controls, evaluation gates, retrieval sources, async execution, and workflow-pack activation are
durable governed state with operator surfaces.

Ownership boundary in one rule: calling services own business context and remain accountable for
user-facing consequences; `lotus-ai` executes governed AI behavior against that context. Pack-level
authority boundaries (what each workflow pack may consume and must never do) are specified in
[workflow-pack owner onboarding](docs/guides/workflow-pack-owner-onboarding.md).

## Validation

Three CI lanes gate every change: Remote Feature Lane, Pull Request Merge Gate, and Main
Releasability Gate (merged PRs dispatch exact-main evidence automatically). Locally, `make check`
is the fast gate and `make ci` the PR-grade gate; the enforced checks and operator procedures are
documented in the [service operations runbook](docs/runbooks/service-operations.md).

## Wiki

The [GitHub wiki](https://github.com/sgajbi/lotus-ai/wiki) is published from the `wiki/` directory
in this repository — authored source lives here, the wiki repository is only a publish target.
