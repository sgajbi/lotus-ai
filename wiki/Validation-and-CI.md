# Validation and CI

## Lane Model

`lotus-ai` follows the Lotus CI lane model:

1. `Remote Feature Lane`
2. `Pull Request Merge Gate`
3. `Main Releasability Gate`

The repo-native commands are designed to map to those lanes rather than to ad hoc local habits.

## Primary Commands

- `make check` - fast local gate
- `make ci` - PR-grade local gate
- `make runtime-mode-smoke` - targeted startup and runtime-mode smoke
- `make migration-apply` - apply Alembic migrations
- `make docker-build` - Docker build validation

## What `make check` Protects

`make check` is the fast local gate. It currently covers:

1. lint,
2. typecheck,
3. OpenAPI quality,
4. evaluation manifest validation,
5. evaluation run artifact validation,
6. async job artifact validation,
7. migration smoke,
8. runtime-mode smoke,
9. unit-test execution.

Use it for:

1. narrow code changes,
2. contract and routing changes,
3. documentation updates that mention commands or runtime posture,
4. focused task/runtime work that does not need the full PR-grade proof.

## What `make ci` Adds

`make ci` is the local PR-grade gate. It adds:

1. dependency verification,
2. project-scoped security audit,
3. coverage-backed test execution,
4. Docker build validation.

This is the right gate when the change affects:

1. persistence mode or startup behavior,
2. provider policy or rollout posture,
3. retrieval, evaluation, safety, or async runtime,
4. public contracts or operator-facing platform surfaces.

## Why These Gates Matter Here

The important CI posture in `lotus-ai` is not only about test count. The gates protect:

1. public contract truth,
2. runtime evidence inventory,
3. async and evaluation artifact consistency,
4. migration-managed durability expectations,
5. security posture for a banking-oriented AI platform.

In other words, many of the gates are contract and governance guards, not only code-quality checks.

## Evaluation and Evidence Gates

Three gates deserve special attention because they are easy to misread:

1. `eval-manifest-gate`
   validates the fixture-manifest structure and referenced fixture files.
2. `eval-run-gate`
   validates the recorded evaluation run artifacts.
3. `async-job-gate`
   validates the governed async job artifact inventory.

These keep the evidence layer truthful. They are part of the product contract for `lotus-ai`, not
just developer convenience.

## Validation Sources

- `Makefile`
- `REPOSITORY-ENGINEERING-CONTEXT.md`
- `docs/evals/evaluation-strategy.md`
- `docs/runbooks/service-operations.md`

## Read Next

1. use [Development Workflow](./Development-Workflow.md) for the repo's actual working loop,
2. use [Troubleshooting](./Troubleshooting.md) when a local gate fails for runtime or policy reasons,
3. use [Operations Runbook](./Operations-Runbook.md) when the issue is about live runtime posture.
