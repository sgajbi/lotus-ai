# Service Operations Runbook

## Standard Commands

- make lint
- make typecheck
- make runtime-mode-smoke
- make ci
- docker compose up --build

## Health and Readiness

- Liveness: /health/live
- Readiness: /health/ready
- General health: /health
- Metadata: /metadata
- Platform runtime status: /platform/runtime-status
- Async activation readiness: /platform/async/activation-readiness
- Async runbook readiness: /platform/async/runbook-readiness
- Async governance status: /platform/async/governance-status
- Provider activation readiness: /platform/providers/activation-readiness
- Provider runbook readiness: /platform/providers/runbook-readiness
- Provider governance status: /platform/providers/governance-status
- Retrieval activation readiness: /platform/retrieval/activation-readiness
- Retrieval runbook readiness: /platform/retrieval/runbook-readiness
- Retrieval governance status: /platform/retrieval/governance-status
- Evaluation runtime status: /platform/evals/runtime-status
- Safety runtime status: /platform/safety/runtime-status
- Retrieval runtime status: /platform/retrieval/runtime-status

## Startup Readiness Policy

- `LOTUS_AI_STARTUP_READINESS_POLICY=warn`
  - startup succeeds
  - readiness findings are recorded in runtime status and logs
- `LOTUS_AI_STARTUP_READINESS_POLICY=enforce`
  - startup fails when configured persistence backends are not ready
  - use this for environments that require SQL-backed stores to be migrated before rollout

- `LOTUS_AI_READINESS_PROBE_POLICY=observe`
  - `/health/ready` stays ready unless the service is draining
  - runtime-status endpoints carry the readiness findings
- `LOTUS_AI_READINESS_PROBE_POLICY=degrade`
  - `/health/ready` returns `503` with `status=degraded` when startup readiness findings exist
  - use this when orchestrators should stop routing traffic until persistence posture is operational

Expected operator flow for SQL-backed stores:

1. apply migrations with `make migration-apply`
2. verify `GET /platform/runtime-status`
3. confirm evaluation runtime posture in the embedded evaluation summary
4. confirm prompt runtime selection in the embedded prompt runtime summary
5. verify `GET /platform/safety/runtime-status`
6. verify `GET /platform/retrieval/runtime-status` when retrieval persistence is relevant
7. only then proceed with rollout if readiness is `READY`

CI also runs `make runtime-mode-smoke` as a dedicated gate so SQL-backed startup, readiness, and migration behavior remain continuously verified.

## Async Activation Governance

Before any future async activation slice:

1. verify `GET /platform/async/governance-status`
2. inspect `GET /platform/async/activation-readiness` when technical blockers need detail
3. inspect `GET /platform/async/runbook-readiness` when operational blockers need detail
4. confirm the embedded `async_governance` block in `GET /platform/runtime-status` matches the detailed async governance view
5. confirm queue backend and worker execution posture are still governed and explicitly selected
6. confirm observability, replay, escalation, and incident procedures are documented and approved
7. only then proceed with any activation rollout review

## Provider Activation Governance

Before any future live-provider activation slice:

1. verify `GET /platform/providers/governance-status`
2. inspect `GET /platform/providers/activation-readiness` when technical blockers need detail
3. inspect `GET /platform/providers/runbook-readiness` when operational blockers need detail
4. confirm the embedded `provider_governance` block in `GET /platform/runtime-status` matches the detailed provider governance view
5. confirm provider policy and catalog still reflect governed disabled or stub posture unless explicitly approved otherwise
6. confirm vendor escalation, rate-limit response, and provider observability procedures are documented and approved
7. only then proceed with any live-provider activation rollout review

## Retrieval Activation Governance

Before any future live-retrieval activation slice:

1. verify `GET /platform/retrieval/governance-status`
2. inspect `GET /platform/retrieval/activation-readiness` when technical blockers need detail
3. inspect `GET /platform/retrieval/runbook-readiness` when operational blockers need detail
4. confirm the embedded `retrieval_governance` block in `GET /platform/runtime-status` matches the detailed retrieval governance view
5. confirm retrieval indexing policy and execution status still reflect governed staged posture unless explicitly approved otherwise
6. confirm reindex, replay, and retrieval observability procedures are documented and approved
7. only then proceed with any live-retrieval activation rollout review

## Incident First Checks

1. Check container logs for request failures and stack traces.
2. Verify /health/ready and metrics endpoint.
3. Run local parity check (make ci) before hotfix PR.
