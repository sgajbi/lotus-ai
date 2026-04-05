# Integration Guide

## Platform Discovery

Before integrating a Lotus app with `lotus-ai`, upstream teams should inspect:

1. `GET /platform/runtime-status` for the current operating posture,
2. `GET /platform/capabilities` for currently exposed task contracts,
3. `GET /platform/providers` for the current provider execution posture,
4. `GET /platform/providers/policy` for supported provider modes and rejection semantics,
5. `GET /platform/providers/quota-policy` for configured live-provider quota scopes and typed configuration findings,
6. `GET /platform/providers/budget-policy` for current tracked spend, configured soft and hard budgets, and budget blocking posture,
7. `GET /platform/providers/operations-status` for one combined provider operations view across rollout, quota, budget, and degradation posture,
8. `GET /platform/safety/policy` for task-level output-label and redaction posture,
9. `GET /platform/safety/runtime-status` for current enforced-versus-documented safety controls,
10. `GET /platform/safety/evidence-readiness` for runtime-backed safety approval posture,
11. `GET /platform/safety/runbook-readiness` for operational safety rollout posture,
12. `GET /platform/safety/governance-status` for the combined safety rollout view,
13. `GET /platform/retrieval/runtime-status` for retrieval-specific persistence and corpus posture when retrieval features are relevant.

This keeps downstream integration decisions grounded in actual runtime capability rather than assumptions.

For live-provider integrations, teams should read `/platform/providers/operations-status` as the
operator truth for:

1. `ROLLOUT_BLOCKED`
2. `OPERATIONS_INVALID`
3. `QUOTA_BLOCKED`
4. `BUDGET_SOFT_LIMIT`
5. `BUDGET_BLOCKED`
6. `DEGRADED_UPSTREAM`
7. `CIRCUIT_OPEN`

That surface is more authoritative than inferring provider health from individual task failures.

## Runtime Readiness Semantics

Runtime status endpoints use explicit readiness states for persistence-backed components:

1. `READY`: the configured backend is operational for the current phase.
2. `CONFIGURATION_REQUIRED`: the selected mode requires configuration that is not present.
3. `MIGRATION_REQUIRED`: the backend is reachable but the expected schema is not available yet.
4. `UNAVAILABLE`: the backend could not be reached or the configured mode is unsupported.

Teams should treat `READY` as the only state suitable for relying on durable platform behavior. The other states are informative and should block assumptions about operational persistence.

## Startup Policy

`lotus-ai` supports two startup readiness policies:

1. `warn`
   startup completes and readiness findings are surfaced through runtime-status endpoints
2. `enforce`
   startup is blocked when configured persistence backends are not operational

For shared or enterprise environments, downstream teams should assume `enforce` is the target posture once SQL-backed stores become part of the deployment contract.

## Readiness Probe Policy

`lotus-ai` also separates startup policy from readiness-probe policy:

1. `observe`
   `/health/ready` remains green while runtime-status endpoints expose findings
2. `degrade`
   `/health/ready` reflects startup readiness findings as degraded readiness

This allows teams to adopt stricter operational signaling without forcing an all-or-nothing startup failure policy in every environment.

This guide explains how other Lotus apps should integrate with `lotus-ai`.

## Core Rule

The calling Lotus application owns the business context.

`lotus-ai` should receive structured context that has already been curated by the calling service or by `lotus-gateway`.

For `lotus-workbench` Advisor Brief, the browser should call `lotus-gateway`, and `lotus-gateway`
should assemble the performance fact bundle before invoking `POST /ai/tasks/execute` with
`task_id=explain.v1`. `lotus-ai` should explain only the caller-supplied facts and preserve audit
and evidence metadata; it should not recompute returns, attribution, or benchmark values.

For live LLM-backed Advisor Brief generation in local Docker, `lotus-ai/.env` must enable the
OpenAI text-provider path and the bounded task allowlist:

1. `LOTUS_AI_PROVIDER_MODE=openai`
2. `LOTUS_AI_PROVIDER_ROLLOUT_STATE=CANARY_ENABLED`
3. `LOTUS_AI_LIVE_TEXT_PROVIDER_ID=text.openai`
4. `LOTUS_AI_LIVE_TEXT_MODEL_ID=<approved model>`
5. `LOTUS_AI_LIVE_TEXT_PROVIDER_API_KEY=<deployment secret>`
6. `LOTUS_AI_LIVE_TEXT_ALLOWED_TASK_IDS=explain.v1`

The `lotus-gateway` caller policy must also allow live-provider execution for `explain.v1`; all
other browser callers should continue to call `lotus-gateway` rather than `lotus-ai` directly.

## Local Provider Toggle

Use this when switching between cost-free deterministic mode and live OpenAI-backed generation in
local Docker.

### Disable OpenAI billing

Set this in `lotus-ai/.env`:

```env
LOTUS_AI_PROVIDER_MODE=disabled
```

Then recreate the API and worker containers:

```powershell
cd C:\Users\Sandeep\projects\lotus-ai
docker compose up -d --force-recreate lotus-ai lotus-ai-worker
```

Expected result:

1. `POST /ai/tasks/execute` stays available,
2. responses use the deterministic non-LLM provider path,
3. OpenAI API calls and billing stop,
4. Advisor Brief remains source-grounded but no longer uses live model generation.

### Re-enable OpenAI generation

Set these values in `lotus-ai/.env`:

```env
LOTUS_AI_PROVIDER_MODE=openai
LOTUS_AI_PROVIDER_ROLLOUT_STATE=CANARY_ENABLED
LOTUS_AI_LIVE_TEXT_PROVIDER_ID=text.openai
LOTUS_AI_LIVE_TEXT_MODEL_ID=<approved model>
LOTUS_AI_LIVE_TEXT_PROVIDER_API_KEY=<deployment secret>
LOTUS_AI_LIVE_TEXT_ALLOWED_TASK_IDS=explain.v1
LOTUS_AI_PROVIDER_TIMEOUT_MS=45000
LOTUS_AI_PROVIDER_MAX_OUTPUT_TOKENS=4096
```

Then recreate the same containers with `docker compose up -d --force-recreate lotus-ai lotus-ai-worker`.

Verification:

1. `GET /health/ready` should return `200`,
2. `POST /ai/tasks/execute` should return `audit.provider_mode = "openai"` and `audit.stubbed = false`
   when the live provider key has quota,
3. if billing must remain off, verify `audit.provider_mode` is not `openai` before using Advisor Brief.

## Recommended Integration Pattern

1. Build a domain-owned context payload.
2. Select a bounded AI task id.
3. Call `lotus-ai` with correlation id and caller metadata.
4. Receive structured AI output and audit metadata.
5. Apply that output only within the calling service's own business rules.

For new downstream onboarding, start with the capability-pack layer first:

1. `GET /platform/capability-packs`
2. `GET /platform/capability-packs/{pack_id}`
3. `GET /platform/capability-packs/{pack_id}/adoption-template`
4. `GET /platform/capability-packs/{pack_id}/governance-status`

Then use the first-use-case surfaces as the concrete reference path when the selected pack already has one:

1. `GET /platform/use-cases/onboarding-template`
2. `GET /platform/use-cases/first-production-use-case`
3. `GET /platform/use-cases/first-production-use-case/governance-status`

That sequence keeps downstream adoption pack-oriented first, while still preserving the currently implemented reference use case and its bounded rollout truth.

## Good Use Cases

### Preferred first integration: lotus-performance

1. Explain already computed performance deltas.
2. Summarize material attribution or period-over-period changes.
3. Keep outputs commentary-oriented and grounded in structured analytics owned by `lotus-performance`.
4. Review `GET /platform/use-cases/first-production-use-case/readiness` before treating the integration as ready for limited governed onboarding.
5. Review `GET /platform/use-cases/first-production-use-case/governance-status` before treating the integration as ready for limited governed rollout.

### lotus-manage

1. Explain rebalance outcome.
2. Summarize blocking diagnostics.
3. Draft reviewer notes for support or operations.

### lotus-advise

1. Summarize proposal workflow status.
2. Draft approval-pack commentary.
3. Explain suitability or gate recommendations.

### lotus-risk and lotus-performance

1. Turn structured analytics into narrative explanations.
2. Summarize material changes between periods or scenarios.

### lotus-core

1. Summarize ingestion or support anomalies.
2. Explain likely causes from structured lineage/support data.

## Bad Use Cases

1. Replacing domain calculations with LLM guesses.
2. Letting `lotus-ai` invent missing core business data.
3. Asking `lotus-ai` to authoritatively decide approvals or trade execution.
4. Sending uncurated, overly broad data just because it might help.

## Request Design Guidance

Every request should include:

1. `task_id`
2. `caller_app`
3. `correlation_id`
4. `input_mode`
5. structured context object
6. expected output mode

Prefer smaller, explicit context bundles over large raw payload dumps.

## Retrieval Guidance

If retrieval is used:

1. retrieval sources should be explicit,
2. cited output should keep source references,
3. platform docs and approved standards should be favored over ad hoc notes.
