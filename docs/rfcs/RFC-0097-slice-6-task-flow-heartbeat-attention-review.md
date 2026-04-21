# RFC-0097 Slice 6 Task-Flow Heartbeat Attention Review

## Scope

Slice 6 adds heartbeat-style task-flow attention to `/platform/runtime-status`. The summary is
derived from durable task-flow posture and highlights waiting, blocked, stale, and action-required
flows without becoming a separate task-flow authority.

## Implemented

1. Added `WorkflowPackTaskFlowAttentionSummaryResponse` and bounded attention item contracts.
2. Added `task_flow_attention` to `WorkflowPackRuntimeStatusSummaryResponse`.
3. Runtime status now reports task-flow attention when the task-flow store is ready.
4. Runtime status reports explicit unavailable posture when the task-flow store is not ready.
5. Attention reasons cover waiting-for-review, blocked, action-required supportability, and stale
   active flows.
6. The heartbeat stale threshold is 24 hours for active, waiting, or blocked task flows.

## Review Findings

1. The implementation reuses the task-flow read model instead of adding another persistence seam.
2. Attention items carry reasons, not decisions; run-ledger review state and task-flow contracts
   remain authoritative.
3. The item list is bounded while `attention_count` remains the full backlog count.
4. Stale detection is deterministic in tests through an injected `now_utc`.

## Proof

1. `python -m pytest tests\unit\test_workflow_pack_runtime_status.py tests\integration\test_runtime_modes.py tests\integration\test_health.py tests\unit\test_platform_status.py tests\unit\test_openapi_contract.py -q`
   - 40 passed.
2. `python -m ruff check src\app\contracts\workflow_packs.py src\app\services\workflow_pack_runtime_status.py tests\unit\test_workflow_pack_runtime_status.py`
   - passed.
3. `python -m pytest tests\unit\test_workflow_pack_task_flow_contracts.py tests\unit\test_workflow_pack_task_flow_store.py tests\unit\test_workflow_pack_task_flow_service.py tests\unit\test_workflow_pack_runtime_status.py tests\unit\test_runtime_readiness.py tests\integration\test_workflow_pack_task_flow_api_contract.py tests\integration\test_workflow_pack_run_api_contract.py tests\integration\test_runtime_modes.py tests\integration\test_health.py tests\unit\test_platform_status.py tests\unit\test_openapi_contract.py -q`
   - 106 passed.
4. `git diff --check`
   - passed with existing CRLF normalization warnings only.
5. `powershell -ExecutionPolicy Bypass -File C:\Users\Sandeep\projects\lotus-platform\automation\Sync-RepoWikis.ps1 -CheckOnly -Repository lotus-ai`
   - reported expected branch-local drift for `Platform-Surfaces.md`; publish after merge to `main`.

## Remaining RFC-0097 Gaps

1. Gateway and Workbench RFC-0097 task-flow posture slices exist on sibling feature branches and
   still need final PR/merge/live validation.
2. Domain handoff execution remains a future cross-service slice.
3. Second-last governance review and final docs/context/wiki/skills/branch-hygiene slices remain
   required before RFC closure.
