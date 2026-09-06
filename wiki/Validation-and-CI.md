# Validation and CI

## Lane Model

`lotus-ai` follows the Lotus CI lane model:

1. `Remote Feature Lane`
2. `Pull Request Merge Gate`
3. `Main Releasability Gate`

The repo-native commands are designed to map to those lanes rather than to ad hoc local habits.
When a PR is merged into `main`, `.github/workflows/merged-pr-main-releasability.yml` dispatches
`main-releasability.yml` on `main` so release evidence and RFC closure can cite exact-main proof
rather than branch-only checks.

### What CI actually invokes

The mapping is deliberate but not one-to-one, and the difference matters when deciding what a green
local run has proven. **No workflow invokes `make check` or `make ci`.** The lanes call individual
targets, measured across `.github/workflows/*.yml` on `main`:

```
async-job-gate   branch-protection-policy-gate     docker-build
eval-manifest-gate   eval-run-gate   install   lint   migration-smoke
openapi-gate   runtime-mode-smoke   security-audit   test-postgres
test-unit   typecheck   verify-dependencies
```

Two consequences to keep in mind:

1. **`rfc0002-idea-proof-gate` runs locally only.** It is a prerequisite of both `check` and `ci`,
   and no workflow invokes it. Passing `make check` proves the RFC-0002 Idea explanation path; CI
   does not re-prove it, so a change that breaks only that path will not be caught by a lane.
2. CI runs `test-unit` rather than the broader `test` / `test-coverage` targets that `check` and
   `ci` pull in. Coverage-bearing runs come from the lane's own steps, not from these targets.

Neither is a defect in the commands; both are reasons to run `make check` before pushing rather than
relying on the lanes to repeat it.

## Primary Commands

- `make check` - fast local gate
- `make ci` - PR-grade local gate
- `make rfc0002-idea-proof-gate` - RFC-0002 Idea explanation local-dev proof gate
- `make runtime-mode-smoke` - targeted startup and runtime-mode smoke
- `make test-postgres` - CAS fence proofs on real PostgreSQL (see below)
- `make branch-protection-policy-gate` - branch-protection policy shape (see below)
- `make migration-apply` - apply Alembic migrations
- `make docker-build` - Docker build validation

## What `make check` Protects

`make check` is the fast local gate. It currently covers:

1. lint (ruff check, ruff format, and the runtime-purity guard —
   `scripts/check_runtime_purity.py` fails when production code under `src/`
   imports test tooling, assigns a secret-shaped api-key literal, or assigns
   to any `settings` attribute: process configuration is immutable after
   startup, and per-execution variation goes through the execution-scoped
   config overrides),
2. typecheck,
3. OpenAPI quality,
4. evaluation manifest validation,
5. evaluation run artifact validation,
6. async job artifact validation,
7. RFC-0002 Idea explanation local-dev proof validation,
8. branch-protection policy document shape,
9. migration smoke,
10. runtime-mode smoke,
11. unit-test execution.

The RFC-0002 proof gate executes `idea_explanation.pack@v1` through the governed HTTP boundary,
accepts the review-gated run, validates source-safe consumer/source-event evidence, and proves that
local stub execution cannot issue signed attestation or provider-retention confirmation. It is not
live-provider, provider-native retention/deletion, or downstream Idea consumption evidence.

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

## Branch Protection Policy Gate

Live branch protection is configuration that nothing exercises: if `enforce_admins`, the required
contexts, or conversation resolution were silently weakened, every merge would still look normal.
`quality/branch_protection_policy.v1.json` declares main's governed posture field by field, and
`scripts/check_branch_protection_policy.py` compares live protection against it, failing in **both**
drift directions — when protection weakens, and when an exception's text is removed without the
configuration strengthening. Both the checker and its unit tests are **verbatim lifts** of the
platform reference (`lotus-gateway`), kept byte-identical so a canonical fix propagates by
re-lifting; the policy table is the only repository-specific input. `mypy.ini` carries a narrow,
named exemption for exactly those two files for that reason.

`make branch-protection-policy-gate` runs the **offline shape check** and is part of `make check`
and both blocking merge lanes, so the table cannot rot. The **live comparison** runs in the daily
`Main Gate Coverage Audit`, invoked bare — piping it through `tee` would report `tee`'s exit status
and let the checker raise beneath a green check.

Two honest limits apply today, both tracked in issue #358:

1. **The live comparison is scheduled, not blocking.** The pattern requires a blocking pre-merge home
   because a scheduled-only run cannot stop a merge. This adoption begins from *known drift*, which
   the pattern's drift-first transition rule permits: a blocking live step today would deadlock every
   PR on an operator action that has not happened. The blocking step is a committed follow-up for
   when the drift clears.
2. **It authenticates with a PAT that does not exist yet.** `github.token` cannot carry
   `administration: read`. Until an operator provisions `LOTUS_AUTOMERGE_TOKEN`, the step fails
   closed on authentication — deliberately, because a silent pass without the token is the exact
   gate-liveness defect this control exists to prevent.

The declared posture is the **target**, so the table currently reports one real divergence:
`PR Merge Gate / PostgreSQL Fence Proof` is declared required but is not yet in live protection.
That is recorded as a documented exception with its compensating control (Coverage Gate is
live-required and fails explicitly when the fence fails) and a `retires_when` naming the operator
write. The gap now reports itself daily instead of living in a merged PR body.

## PostgreSQL Fence Proof

`make test-postgres` runs `tests/postgres` against a real PostgreSQL, certifying the compare-and-set
fences behind governed claims and hard-budget accounting on the engine operators actually deploy:
the claim fence, the claim-instant rotation fence, release-versus-resume, reserve admission of the
last headroom, reconcile-releases-once, settle-versus-hold for evidenced `ACTUAL_USAGE`, and
release-versus-hold for a proven non-billable attempt (the two resolve a reservation in opposite
budget directions, so both belong in the proof). Every scenario races two independent repository
sessions (separate engines and pools, asserted distinct backends), and mirrors a SQLite counterpart
in `tests/unit` so backend drift stays visible.

The lane runs in both `pr-merge-gate` and `main-releasability`, backed by a `postgres:16-alpine`
service container. **A red fence produces a FAILED required check, not a skipped one:**
`coverage-gate` (a required context) runs with `if: always()` and asserts every upstream job
succeeded, so a fence failure fails that gate explicitly rather than leaving it skipped. A skipped
required check still blocks the merge button, but it reports as absent rather than as a refusal -
"not applicable" instead of "this gate said no". The same guard covers the unit/integration/e2e
suites and the runtime-mode smoke.

The lane is **fail-closed**, and all three postures are verified rather than assumed: with
`LOTUS_AI_POSTGRES_TEST_REQUIRED` set, a missing URL fails and an unreachable database fails; without
it, a local run skips with an actionable reason. A non-PostgreSQL URL always fails, since pointing
this lane at SQLite would make it tautological rather than merely absent. The posture decisions live
in `tests/support/postgres_lane.py` and are pinned in `tests/unit/test_postgres_lane_gating.py`, so
the failure modes are provable in the fast lane without a database. Locally, set
`LOTUS_AI_POSTGRES_TEST_URL` to a disposable database (for example
`postgresql+psycopg://lotus_ai:lotus_ai@localhost:5433/lotus_ai`).

Isolation baseline is READ COMMITTED (asserted, not assumed): single-statement CAS needs no elevated
isolation, since a blocked guarded `UPDATE` re-evaluates its `WHERE` against the committed winner and
matches zero rows.

**Retry certification is observed, not inferred.** One scenario raises isolation to REPEATABLE READ
to prove the repository's retry path. A barrier alone would not establish this: under REPEATABLE READ
the snapshot opens at the transaction's first statement, so two barrier-synchronised calls can still
run sequentially and produce the same one-winner outcome as a real conflict. The test therefore
forces the ordering - the loser's transaction opens its snapshot with a priming read, the winner
commits its transition, and only then does the loser's guarded `UPDATE` run - and asserts that
PostgreSQL raised **SQLSTATE 40001** (`serialization_failure`), captured at the engine's error
boundary, before the repository's retry opened a fresh snapshot and converged to an honest `False`.
Removing the retry handling makes the `SerializationFailure` escape and the test fail, which is the
property that makes it certification rather than assumption.

This lane found a real defect on its first run: scaled `ROUND` is `NUMERIC`-only on PostgreSQL, so
every guarded budget statement raised `round(double precision, integer) does not exist` there while
passing on SQLite - the hard-budget guarantee was unreachable on the production engine. The fix casts
through `NUMERIC` once, in `_rounded_spend_sql`, and a dialect-compilation pin in the unit lane keeps
the divergence catchable without a database.

## Validation Sources

- `Makefile`
- `REPOSITORY-ENGINEERING-CONTEXT.md`
- `scripts/generate_rfc0002_idea_explanation_proof.py`
- `docs/evals/evaluation-strategy.md`
- `docs/runbooks/service-operations.md`

## Read Next

1. use [Development Workflow](Development-Workflow) for the repo's actual working loop,
2. use [Troubleshooting](Troubleshooting) when a local gate fails for runtime or policy reasons,
3. use [Operations Runbook](Operations-Runbook) when the issue is about live runtime posture.
