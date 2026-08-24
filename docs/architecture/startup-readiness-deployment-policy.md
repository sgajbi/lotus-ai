# Startup Readiness Deployment Policy

This document defines the intended deployment posture for `lotus-ai` startup readiness and readiness-probe behavior across environments.

The purpose is to make environment expectations explicit and stable, so operators and downstream teams do not infer policy from defaults alone.

## Policy Dimensions

`lotus-ai` exposes two independent controls:

1. `LOTUS_AI_STARTUP_READINESS_POLICY`
2. `LOTUS_AI_READINESS_PROBE_POLICY`

These controls answer different questions:

1. should the process start at all when required persistence backends are not ready?
2. should `/health/ready` degrade when startup readiness findings exist?

## Allowed Values

### Startup Readiness Policy

- `warn`
  - startup succeeds
  - readiness findings are captured in logs and runtime-status endpoints
- `enforce`
  - startup fails when configured persistence backends are not operational

### Readiness Probe Policy

- `observe`
  - `/health/ready` stays green unless the service is draining
  - operators use runtime-status endpoints for readiness detail
- `degrade`
  - `/health/ready` returns `503` with `status=degraded` when startup readiness findings exist

## Environment Matrix

Readiness controls own availability posture only. They must never enable privileged caller
identity or change authorization outcomes. Local header identity for privileged all-tenant audit
reads is controlled independently by the default-closed
`LOTUS_AI_LOCAL_HEADER_CALLER_IDENTITY_ENABLED` security setting and must remain disabled outside an
explicit local runtime.

### Local Development

Recommended posture:

1. `LOTUS_AI_STARTUP_READINESS_POLICY=warn`
2. `LOTUS_AI_READINESS_PROBE_POLICY=observe`
3. in-memory stores by default unless working directly on persistence

Why:

1. keeps local iteration fast,
2. avoids blocking developers on durable infrastructure by default,
3. still preserves visibility into readiness findings.

### Shared Development / Integration

Recommended posture:

1. `LOTUS_AI_STARTUP_READINESS_POLICY=warn`
2. `LOTUS_AI_READINESS_PROBE_POLICY=degrade`
3. use SQL-backed stores when the environment is intended to exercise persistence behavior

Why:

1. startup remains developer-friendly,
2. orchestrators and QA can still detect degraded persistence posture,
3. runtime-status endpoints remain the source of detailed diagnosis.

### Enterprise / Production-Like Environments

Recommended posture:

1. `LOTUS_AI_STARTUP_READINESS_POLICY=enforce`
2. `LOTUS_AI_READINESS_PROBE_POLICY=degrade`
3. SQL-backed stores must be migrated before rollout

Why:

1. bank-grade environments should fail clearly rather than run in an ambiguous persistence state,
2. readiness probes should stop routing traffic if required persistence posture is not operational,
3. migration-managed storage is part of the deployment contract, not an optional enhancement.

## Operational Interpretation

The intended operator sequence for SQL-backed environments is:

1. configure `LOTUS_AI_DATABASE_URL`
2. apply migrations with `make migration-apply`
3. start the service
4. verify `GET /platform/runtime-status`
5. verify `GET /platform/retrieval/runtime-status` when retrieval persistence is relevant
6. verify `/health/ready`

`READY` is the only acceptable durable-state result for enterprise rollouts.

## Governance Rule

Changing the recommended environment matrix or the meaning of these policy flags is an operational contract change.

Such changes should be reviewed as architecture or deployment-governance changes, not treated as incidental configuration cleanup.
