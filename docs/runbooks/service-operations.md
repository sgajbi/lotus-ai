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
3. verify `GET /platform/retrieval/runtime-status` when retrieval persistence is relevant
4. only then proceed with rollout if readiness is `READY`

CI also runs `make runtime-mode-smoke` as a dedicated gate so SQL-backed startup, readiness, and migration behavior remain continuously verified.

## Incident First Checks

1. Check container logs for request failures and stack traces.
2. Verify /health/ready and metrics endpoint.
3. Run local parity check (make ci) before hotfix PR.
