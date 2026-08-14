# lotus-ai

Shared AI capability service for the Lotus ecosystem.

Repository-local engineering context: `REPOSITORY-ENGINEERING-CONTEXT.md`

`lotus-ai` provides governed AI execution and control-plane capabilities for Lotus applications. It
exists to let downstream services use prompts, retrieval, safety controls, evaluation gates, async
execution, and provider-routing seams without moving portfolio, analytics, workflow, or business
authority out of the services that already own those domains.

## What This Repository Owns

`lotus-ai` owns:

1. bounded AI task execution contracts,
2. prompt rollout and audit traceability,
3. governed retrieval and citation-carrying answer paths,
4. safety labeling, redaction posture, and safety evidence surfaces,
5. runtime-backed evaluation and approval-gate posture,
6. async runtime and worker-backed job execution for governed AI work,
7. provider policy, quota, budget, and degradation control surfaces,
8. workflow-pack registry and activation-control discovery surfaces,
9. AI-specific observability, evidence, and control-plane APIs.

`lotus-ai` does not own:

1. portfolio, holdings, booking, or transaction truth,
2. performance or risk analytics truth,
3. advisory or management workflow authority,
4. user-facing business decisions outside the explicit task contracts it exposes.

Calling systems remain responsible for assembling business context, preserving domain semantics, and
deciding how AI output is applied or rejected.

## Current Product Shape

`lotus-ai` is in a governed foundation phase. This is not a placeholder repository. The service
already has real runtime seams, durable stores, and operator-facing governance surfaces for prompt
selection, retrieval posture, provider controls, evaluation approval, async execution, and caller
authorization.

The current supported task families are:

1. `explain.v1`
2. `summarize.v1`
3. `classify.v1`
4. `extract.v1`
5. `generate_structured.v1`
6. `knowledge_search.v1`
7. `knowledge_answer.v1`

Important posture limits:

1. live provider execution remains deliberately rollout-governed,
2. the bounded capability catalog is broader than the current live-provider allowlist,
3. retrieval is governed and bounded rather than a general search platform,
4. prompt bodies remain repository-managed even though runtime prompt selection is durable,
5. workflow-pack registry records are control-plane metadata, not a second editable home for workflow logic,
6. workflow-pack registrations must point to real owning-repository artifacts rather than placeholder definitions in `lotus-ai`,
7. workflow-pack registry and control state can now run either in-memory or through a SQL-backed durable store, and the current executable workflow-pack set includes advisor brief, workspace rationale, TWR inspection support brief, the review-gated `proposal_memo_commentary.pack@v1` contract for `lotus-advise` advisor proposal memo evidence, the six review-gated `advisory_copilot_*.pack@v1` contracts for RFC-0027 `lotus-advise` evidence packets, the review-gated `dpm_pm_memo.pack@v1` contract for `lotus-manage` `DpmProofPackAiEvidenceInput`, the review-gated `dpm_wave_pm_memo.pack@v1` and `dpm_operations_handoff_summary.pack@v1` contracts for `lotus-manage` `DpmWaveReportInput`, the review-gated `dpm_exception_summary.pack@v1` contract for bounded `lotus-manage` monitoring exception evidence, the review-gated `outcome_review_narrative.pack@v1` contract for `lotus-manage` `DpmOutcomeAiEvidenceInput`, and the review-gated `idea_explanation.pack@v1` contract for `lotus-idea` redacted opportunity evidence packets,
8. the service should be treated as a governed capability layer, not a business-domain authority.
9. AI provider operations can issue a limited, not-certified Ed25519-signed retention/deletion
   confirmation for completed live `idea_explanation.pack` runs. The recorder is AI-owned;
   `lotus-idea` is only the audience. SQL persistence, tenant binding, idempotency, provider failure
   posture, and no-raw-content claims are implementation-backed, while provider-native and bank
   approvals remain blocked.

For proposal memo commentary, RFC-0027 advisory copilot, DPM PM memo, exception summary,
operations handoff summary, and idea explanation support, `lotus-ai` owns workflow-pack execution, provider mode, safety, guardrail validation,
run-ledger posture, queue policy, and deterministic stub behavior.
`lotus-advise` remains the advisor proposal memo evidence, review, and client-ready boundary
authority. The proposal memo commentary pack consumes bounded memo evidence only and cannot mutate
memo status, suitability, approval, or client-ready posture.
The advisory copilot packs consume only `lotus-advise` copilot evidence packets with source refs,
model-risk controls, blocked client-ready posture, unsupported-claim posture, and human-review
requirements. They cannot approve advice, approve or waive policy, place orders, send client
messages, expose raw prompts or raw payloads, or infer missing advisory evidence.
`lotus-manage` remains the proof-pack and rebalance-wave evidence authority. The proof-pack pack
consumes `DpmProofPackAiEvidenceInput`; the wave PM memo and operations handoff summary packs
consume `DpmWaveReportInput`; the exception summary pack consumes bounded manage-owned monitoring
exception evidence. These packs are pilot-scoped, support-only, and review-gated; they must not
approve rebalances, place orders, produce client messages, score PMs, claim external execution,
produce routing instructions, or invent missing proof-pack, wave, exception, or handoff evidence.
`lotus-idea` remains the opportunity-intelligence and idea-evidence authority. The idea explanation
pack consumes only redacted evidence packets, bounded explanation requests, and supportability
posture from `lotus-idea`; it cannot create suitability approval, proposal authority, rebalance
authority, client-ready publication, supported-feature promotion, or missing source evidence. The
caller policy recognizes `lotus-idea` only for restricted-tenant, review-gated `explain.v1`
execution and does not grant live-provider, prompt-control, provider-control, or async-control
privilege.

Completed, reviewed, supportable non-stub workflow-pack runs can expose short-lived signed
provenance through `/platform/workflow-packs/runs/{run_id}/attestation`, with public Ed25519 key
discovery at `/.well-known/lotus-ai-workflow-attestation-keys`. Issuance requires an exact effective
model-risk inventory match and excludes raw prompts, generated output, and client or portfolio
payloads. See [Workflow-Run Attestations](docs/guides/workflow-run-attestations.md).

For DPM portfolio-memory support, the proof-pack PM memo, wave PM memo, operations handoff summary,
and outcome-review narrative packs can consume optional `portfolio_memory_context` emitted by
`lotus-manage` report-input handoffs. `lotus-ai` validates that the context is portfolio-matched,
source-lineage-only, capped to the bounded event-ref limit, governed by `NO_RAW_PAYLOADS`, and
explicitly marked as source-owned truth that consumers must not reconstruct. Generated outputs
expose only a compact portfolio-memory lineage summary, content hash, event count, source systems,
event types, and review guidance.

## Architectural Shape

The service is a FastAPI application with explicit control-plane and data-plane seams.

Core areas:

1. `src/app/contracts/`
   public task and platform contract models.
2. `src/app/services/`
   orchestration, runtime-context assembly, evidence mapping, and audit flow.
3. `src/app/providers/`
   provider adapters, policy, rollout, quota, budget, and degradation handling.
4. `src/app/prompts/`
   prompt definitions, rollout state, and prompt governance surfaces.
5. `src/app/retrieval/`
   source governance, indexed-search posture, and retrieval execution seams.
6. `src/app/safety/`
   output-label-aware policy and runtime safety posture.
7. `src/app/evals/`
   evaluation inventory, runtime execution, and approval-gate evidence.
8. `src/app/routers/`
   public API surfaces.
9. `src/app/services/workflow_pack_registry.py`
   workflow-pack registration catalog, owner-artifact references, and validation seams.

Task execution is intentionally explicit. A request flows through:

1. capability and request validation,
2. runtime-context construction,
3. prompt and safety posture resolution,
4. provider or retrieval execution,
5. evidence assembly,
6. audit persistence.

Detailed architecture references:

- `docs/architecture/system-overview.md`
- `docs/architecture/scalability-and-deployment-model.md`
- `docs/architecture/startup-readiness-deployment-policy.md`
- `docs/architecture/feature-status-and-roadmap.md`

## Repository Layout

- `src/` application code
- `tests/` unit, integration, and e2e validation
- `docs/architecture/` architecture and roadmap guidance
- `docs/guides/` integration and contract guidance
- `docs/runbooks/` service operations guidance
- `docs/security/` security and governance posture
- `docs/standards/` local standards
- `docs/rfcs/` repo-local RFC inventory
- `docs/evals/` evaluation strategy and fixtures
- `wiki/` canonical source pages for the GitHub wiki

## Quick Start

Install dependencies and run the fast local gate:

```powershell
make install
make check
```

Run the API directly:

```powershell
uvicorn app.main:app --reload --port 8140
```

Run the prod-shaped local Docker stack:

```powershell
docker compose up --build
```

API docs are available at `http://localhost:8140/docs`.

Local Docker runtime notes:

1. PostgreSQL stays internal to the Compose network on `postgres:5432`,
2. Redis stays internal to the Compose network on `redis:6379`,
3. only the application port `8140` is published for local API access.

## Common Commands

- `make install` - install development dependencies
- `make check` - fast local gate
- `make ci` - PR-grade local gate
- `make rfc0002-idea-proof-gate` - deterministic local-dev proof for
  `idea_explanation.pack@v1` execution, review, source-safe lineage, and fail-closed live-provider
  certification boundaries
- `make runtime-mode-smoke` - verify startup, migration, and runtime-mode posture
- `make migration-apply` - apply Alembic migrations
- `make docker-build` - Docker build validation

## Validation and CI

`lotus-ai` follows the Lotus lane model:

1. `Remote Feature Lane`
2. `Pull Request Merge Gate`
3. `Main Releasability Gate`

Merged pull requests to `main` also dispatch `main-releasability.yml` through
`.github/workflows/merged-pr-main-releasability.yml`, giving RFC and release-governance work
exact-main evidence instead of relying on stale branch checks or manual reruns.

Repo-native validation mapping:

- fast local gate: `make check`
- PR-grade gate: `make ci`
- runtime smoke: `make runtime-mode-smoke`
- Docker validation: `make docker-build`

The enforced gates currently include:

1. lint and typecheck,
2. OpenAPI quality,
3. evaluation fixture manifest validation,
4. evaluation run artifact validation,
5. async job artifact validation,
6. RFC-0002 Idea explanation local-dev proof validation,
7. migration smoke,
8. dependency health and security audit,
9. coverage-backed test execution,
10. Docker build validation.

The RFC-0002 Idea proof gate is intentionally conservative. It executes
`idea_explanation.pack@v1` through the governed HTTP boundary, applies a reviewer acceptance,
verifies source-safe consumer/source-event projections, and verifies that signed workflow-run
attestation and provider-retention confirmation remain non-issuable in local stub mode. It clears
local owner-repo proof for guardrails and lineage, but preserves live-provider, approved
model-risk-inventory, signed non-stub attestation, and provider-native retention/deletion blockers.
The artifact contract is
`contracts/rfc-0002/lotus-ai-idea-explanation-workflow-proof.v1.json`.
Generate a source-safe handoff artifact when needed:

```powershell
python scripts/generate_rfc0002_idea_explanation_proof.py `
  --output output/rfc0002-idea-explanation-proof.json
```

## Integration Contract

The first executable public contract is:

- `POST /ai/tasks/execute`

Downstream teams should integrate against the contract and preserve the audit metadata rather than
assuming unrestricted live-model behavior.

The core integration references are:

- `docs/guides/task-execution-contract.md`
- `docs/guides/integration-guide.md`
- `docs/guides/workflow-pack-owner-onboarding.md`
- `docs/guides/prompt-registry-and-audit.md`
- `docs/guides/retrieval-and-vector-store.md`

For a grouped map of the current execution, audit, task-runtime, and platform surfaces derived from
the actual router layout, use the wiki page:

- `wiki/Platform-Surfaces.md`

Practical rule:

1. calling services own business context,
2. `lotus-ai` executes governed AI behavior against that context,
3. downstream systems remain accountable for user-facing consequences.

## Operations and Runtime Posture

Key health and operator surfaces:

- `/health/live`
- `/health/ready`
- `/platform/runtime-status`
- `/platform/providers/operations-status`
- `/platform/prompts/runtime-status`
- `/platform/retrieval/runtime-status`
- `/platform/safety/runtime-status`
- `/platform/evals/runtime-status`
- `/platform/async/governance-status`
- `/platform/workflow-packs/registry`
- `/platform/workflow-packs/registry/{pack_id}/default`
- `/platform/workflow-packs/eligibility/evaluate`
- `/platform/workflow-packs/control-history`
- `/platform/workflow-packs/runs`

Workflow-pack registry records should be read as control-plane onboarding truth:

1. the primary `definition_ref` must resolve to a real owner artifact,
2. `definition_refs` show the contract, service, router, tests, and optional RFC or UI evidence used to justify the registration,
3. `GET /platform/workflow-packs/registry/{pack_id}/default` resolves only registered, activation-eligible, non-superseded versions and does not auto-promote discovered or dark successor versions,
4. when `LOTUS_AI_WORKFLOW_PACK_REGISTRY_STORE_MODE=sqlalchemy`, activation state and control history are restart-safe only after migrations are applied and `/platform/runtime-status` reports the embedded registry store as `READY`,
5. `lotus-ai` tracks those references for governance, but the implementation remains owned by the downstream repository.

Operational guidance lives in:

- `docs/runbooks/service-operations.md`
- `docs/runbooks/provider-mode-switching.md`

For a grouped operator-facing and control-plane view of those surfaces, use:

- `wiki/Platform-Surfaces.md`

## Security and Governance

The service is built for a banking-oriented environment with explicit governance boundaries:

1. domain apps remain accountable for business meaning,
2. prompt changes must remain reviewable,
3. retrieval sources must remain curated and attributable,
4. safety, audit, and approval boundaries must stay explicit,
5. framework adoption must not obscure runtime behavior or policy gates.

Source:

- `docs/security/security-and-governance.md`

## Documentation Map

Best starting points:

- system overview: `docs/architecture/system-overview.md`
- feature status and roadmap: `docs/architecture/feature-status-and-roadmap.md`
- phased roadmap: `docs/architecture/phased-roadmap.md`
- first use-case guide: `docs/guides/lotus-performance-first-use-case.md`
- service operations runbook: `docs/runbooks/service-operations.md`
- evaluation strategy: `docs/evals/evaluation-strategy.md`
- local RFC index: `docs/rfcs/README.md`

Platform governance:

- `../lotus-platform/rfcs/RFC-0069-lotus-ai-shared-ai-platform-service.md`
- `../lotus-platform/rfcs/RFC-0072-platform-wide-multi-lane-ci-validation-and-release-governance.md`
- `../lotus-platform/context/LOTUS-ENGINEERING-CONTEXT.md`

## Wiki

The live GitHub wiki is:

- `https://github.com/sgajbi/lotus-ai/wiki`

The canonical authored source for that wiki lives under `wiki/` in this repository.

If you use a separate local clone of `https://github.com/sgajbi/lotus-ai.wiki.git`, treat it only
as a publish target for the live wiki, not as a second maintained documentation tree.
