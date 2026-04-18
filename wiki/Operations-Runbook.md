# Operations Runbook

## Operational Entry Points

The most important operator-facing endpoints are:

- `/health/live`
- `/health/ready`
- `/platform/runtime-status`
- `/metadata`

These tell you:

1. whether the process is running,
2. whether readiness is degraded,
3. which runtime and store modes are active,
4. which startup and readiness policies are currently configured.

For startup and rollout review, treat this as the first-pass sequence:

1. `/health/live`
2. `/health/ready`
3. `/metadata`
4. `/platform/runtime-status`

## Grouped Platform Surfaces

The service exposes a broad platform surface. The main groups are:

1. providers
   catalog, policy, operator profile, quota, budget, operations status, and control-plane actions
2. prompts
   catalog, control history, control actions, runtime status, and governance readiness
3. retrieval
   source governance, document governance, runtime status, execution status, and indexing or
   ingestion jobs
4. safety
   policy, runtime status, activation, evidence readiness, and governance
5. artifacts
   runtime status, descriptor-first catalog, activation readiness, and governance
6. evaluations
   catalog, runtime status, fixtures, and recorded runs
7. async runtime
   runtime status, queue backends, worker executions, jobs, and control-plane actions
8. observability
   runtime status, governance posture, incident summary, domain summaries, and bounded breakdowns
9. access control
   runtime, caller-policy catalog, and governance posture for caller authorization
10. task-runtime inspection
   runtime status plus execution, evidence, and retrieval summaries
11. capability packs, app-capability rollouts, and first-use-case surfaces
   adoption and rollout governance rather than direct execution

For the grouped route map, use [Platform Surfaces](./Platform-Surfaces.md).

## Operator-First Route Families

If the issue is broad and you do not yet know which subsystem is wrong, start here:

1. `/platform/runtime-status`
2. `/platform/observability/incident-summary`
3. `/platform/tasks/runtime-status`
4. the subsystem-specific governance or operations surface you depend on

Good examples:

1. provider posture
   - `/platform/providers/operator-profile`
   - `/platform/providers/operations-status`
2. retrieval posture
   - `/platform/retrieval/runtime-status`
   - `/platform/retrieval/execution-status`
3. async posture
   - `/platform/async/runtime-status`
   - `/platform/async/jobs`
4. prompt posture
   - `/platform/prompts/runtime-status`
   - `/platform/prompts/control-history`
5. evaluation posture
   - `/platform/evals/runtime-status`
   - `/platform/evals/runs`

## Readiness Semantics

Two configuration flags matter operationally:

1. `LOTUS_AI_STARTUP_READINESS_POLICY`
2. `LOTUS_AI_READINESS_PROBE_POLICY`

Interpret them separately:

1. startup policy determines whether the process should start at all,
2. readiness-probe policy determines whether `/health/ready` should degrade.

In stronger environments, the intended posture is:

1. `enforce`
2. `degrade`

In local development, the normal posture is:

1. `warn`
2. `observe`

The practical reading rule is:

1. startup policy tells you whether the process should have been allowed to come up,
2. readiness-probe policy tells you whether traffic should still be routed.

## Provider Changes

Treat provider-mode changes as operational changes, not just config edits.

After every provider-mode change:

1. recreate `lotus-ai` and `lotus-ai-worker`,
2. verify `/health/ready`,
3. verify `/platform/providers/operator-profile`,
4. verify `/platform/providers`,
5. verify `/platform/providers/policy`,
6. verify `/platform/providers/operations-status`,
7. run one bounded `POST /ai/tasks/execute` request and confirm the audit fields match the expected
   provider path.

Source:

- `docs/runbooks/provider-mode-switching.md`

## SQL-Backed Environments

For SQL-backed environments, the intended operator flow is:

1. configure `LOTUS_AI_DATABASE_URL`,
2. apply migrations with `make migration-apply`,
3. start the service,
4. verify `/platform/runtime-status`,
5. inspect the specific runtime surfaces you depend on,
6. only then treat the runtime as ready.

`READY` is the only durable-state posture that should be treated as sufficient for stronger rollout
claims.

For SQL-backed stronger environments, also treat these as first-class checks rather than optional
detail:

1. `/platform/artifacts/runtime-status`
2. `/platform/access-control/runtime-status`
3. `/platform/evals/runtime-status`
4. `/platform/async/runtime-status`

## Detailed Runbook Sources

- `docs/runbooks/service-operations.md`
- `docs/runbooks/provider-mode-switching.md`
- `docs/architecture/startup-readiness-deployment-policy.md`

## Read Next

1. use [Platform Surfaces](./Platform-Surfaces.md) for the grouped route map,
2. use [Troubleshooting](./Troubleshooting.md) for common failure patterns,
3. use [Security and Governance](./Security-and-Governance.md) when the question is about what the runtime is actually allowed to do.
