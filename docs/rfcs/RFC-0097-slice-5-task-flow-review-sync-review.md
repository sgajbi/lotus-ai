# RFC-0097 Slice 5 Task-Flow Review Sync Review

## Scope

Slice 5 synchronizes workflow-pack run review actions into task-flow posture. This keeps the
task-flow read model truthful after `ACCEPT`, `REVISE`, `SUPERSEDE`, `REJECT`, and `ABANDON`
actions update the run ledger.

## Implemented

1. Review actions now preflight task-flow store readiness before mutating run review state.
2. Task-flow review state mirrors updated run review state.
3. Accepted runs move their task flow to `COMPLETED` and supportability to `READY`.
4. Revised and superseded runs move their originating task flow to `SUPERSEDED` and supportability
   to `HISTORICAL`.
5. Replacement lineage is written to both the superseded task flow and the replacement task flow.
6. Review checkpoints are recorded with actor, transition, evidence, and reason.

## Review Findings

1. Review-state synchronization belongs in the task-flow service, not in router code, because it is
   an internal read-model maintenance concern.
2. The implementation keeps task-flow state derived from the run ledger and does not create a
   separate review authority.
3. The replacement-lineage descriptor is idempotent, so duplicate review synchronization will not
   append duplicate lineage payloads.
4. Gateway and Workbench still should consume read-only posture through governed contracts rather
   than inferring lineage from narrative text.

## Proof

1. `python -m pytest tests\integration\test_workflow_pack_run_api_contract.py tests\integration\test_workflow_pack_task_flow_api_contract.py -q`
   - 36 passed.
2. `python -m ruff check ...touched review-sync files...`
   - passed.
3. `git diff --check`
   - passed with existing CRLF normalization warnings only.
4. `python -m pytest tests\unit\test_workflow_pack_task_flow_contracts.py tests\unit\test_workflow_pack_task_flow_store.py tests\unit\test_workflow_pack_task_flow_service.py tests\unit\test_runtime_readiness.py tests\integration\test_workflow_pack_task_flow_api_contract.py tests\integration\test_workflow_pack_run_api_contract.py tests\integration\test_runtime_modes.py tests\integration\test_health.py tests\unit\test_platform_status.py tests\unit\test_openapi_contract.py -q`
   - 96 passed.

## Remaining RFC-0097 Gaps

1. Gateway publication and Workbench rendering of task-flow posture.
2. Heartbeat attention adapter for stale, blocked, degraded, and review-waiting task flows.
3. Domain handoff contract integration with owner services.
4. Second-last governance review and final docs/context/wiki/skills/branch-hygiene slices.
