# Enterprise Readiness

- Service: `lotus-ai`
- Status: baseline adopted

## Minimum Enterprise Expectations

1. migration-managed relational persistence
2. explicit runtime-status endpoints
3. explicit startup readiness policy
4. explicit readiness-probe policy
5. CI verification of SQL-backed runtime behavior
6. branch protection and required checks

## Current Compliance Notes

`lotus-ai` currently enforces:

1. OpenAPI quality gates
2. migration contract checks
3. dedicated SQL-backed runtime mode smoke tests
4. runtime readiness classification across audit and retrieval stores
5. separate startup and readiness-probe controls for operational environments

## Deployment Reference

The canonical deployment posture for readiness policy is documented in:

- `docs/architecture/startup-readiness-deployment-policy.md`
