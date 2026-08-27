# Development Workflow

## Working Model

Use a small, truthful loop:

1. understand the affected runtime surface from code,
2. run the smallest repo-native gate that proves the change,
3. update docs when the runtime or operator truth changes,
4. move to the PR-grade gate when the change touches contracts, rollout posture, or durability.

In `lotus-ai`, this matters because many changes affect public platform surfaces and governance
claims, not just internal code paths.

## Common Commands

- `make install`
- `make check`
- `make ci`
- `make runtime-mode-smoke`
- `make migration-apply`
- `make docker-build`

## When to Use Which Gate

Use `make check` for:

1. router and contract changes,
2. task-runtime logic changes,
3. prompt, retrieval, safety, or provider logic that does not need full PR-grade proof yet,
4. documentation changes that mention commands, modes, or runtime posture.

Use `make ci` when the change affects:

1. persistence or migration behavior,
2. provider rollout or operations posture,
3. retrieval, evaluation, safety, or async evidence posture,
4. public operator-facing platform surfaces,
5. any change where the local PR-grade truth should be known before review.

## Read the Code Surface First

For documentation, integration, or runtime work, start from the app’s real surface:

1. `src/app/main.py`
2. `src/app/routers/`
3. `src/app/contracts/`
4. the relevant service modules behind those routers

This repo is broad enough that existing prose alone is not a safe source of truth.

## Docs-With-Code Rule

Update docs in the same slice when:

1. commands change,
2. runtime posture changes,
3. rollout semantics change,
4. grouped platform surfaces change,
5. a bounded capability moves from planned to implemented,
6. onboarding or operator interpretation would otherwise drift.

For `lotus-ai`, this is not optional cleanup. The docs are part of the control-plane contract.

## Practical Sources

Use these as the main working references:

- `README.md`
- `REPOSITORY-ENGINEERING-CONTEXT.md`
- `wiki/Platform-Surfaces.md`
- `docs/architecture/system-overview.md`
- `docs/architecture/feature-status-and-roadmap.md`
- `docs/runbooks/service-operations.md`
- `docs/security/security-and-governance.md`

## Read Next

1. use [Validation and CI](Validation-and-CI) for the gate meanings,
2. use [Platform Surfaces](Platform-Surfaces) when the change touches public APIs,
3. use [RFC Index](RFC-Index) when the change is governed by a specific capability RFC family.
