# RFC-0097 Slice 1 Review: Task-Flow Contract

Date: 2026-04-21

Branch: `feature/rfc0097-task-flow-contract`

## Scope

Implemented the first `lotus-ai` source-contract slice for platform RFC-0097:

1. `src/app/contracts/workflow_pack_task_flows.py`
2. `src/app/services/workflow_pack_task_flow_contracts.py`
3. `tests/unit/test_workflow_pack_task_flow_contracts.py`
4. `docs/architecture/feature-status-and-roadmap.md`

This slice intentionally does not add a store, migration, router, gateway endpoint, Workbench
surface, heartbeat adapter, or domain handoff execution path.

## Slice 0 Alignment Outcome

Current implementation evidence points to `advisor_brief.pack@v1` as the safest first-wave runtime
candidate for later slices because it already has explicit binding metadata, run-ledger recording,
review actions, replacement lineage, gateway facade coverage, and Workbench proof. The task-flow
contract is still generic enough for `workspace_rationale.pack@v1` and
`twr_inspection_support_brief.pack@v1`, but implementation should start with one narrow flow.

## Review Findings

1. Finding: RFC-0097 needed a source-truth contract before storage or gateway work.
   Resolution: added Pydantic descriptors for task flow, step, checkpoint, replacement lineage,
   blocking condition, and domain handoff.
2. Finding: flow state could easily collapse run and review state if modeled loosely.
   Resolution: task-flow descriptors keep `flow_status`, per-run `runtime_states`, and per-review
   `review_states` as separate fields.
3. Finding: terminal state behavior needed a reusable seam before service implementation.
   Resolution: added a small bounded transition table with a validator that rejects terminal
   advancement.
4. Finding: implementation truth changed enough to require local documentation.
   Resolution: updated the architecture roadmap to say the task-flow contract foundation exists
   while runtime/storage/API/downstream adoption remain future slices.

## Complexity Review

The contract and transition validator are intentionally split:

1. contracts own shape and source-truth language,
2. the service helper owns transition policy,
3. no router or persistence layer is introduced before the contract is proven.

This keeps Slice 2 free to implement storage without duplicating enum definitions or inventing a
different transition vocabulary.

## Proof

Commands run:

```powershell
python -m pytest tests\unit\test_workflow_pack_task_flow_contracts.py -q
python -m ruff check src\app\contracts\workflow_pack_task_flows.py src\app\services\workflow_pack_task_flow_contracts.py tests\unit\test_workflow_pack_task_flow_contracts.py
git diff --check
```

Results:

1. `6 passed`
2. Ruff passed.
3. `git diff --check` passed.

## Remaining RFC-0097 Work

1. Slice 2 must add durable storage and restart-safe service behavior.
2. Slice 3 must bind one first-wave flow to actual workflow-pack execution and run-ledger evidence.
3. Gateway, Workbench/domain adoption, heartbeat, API certification, and final docs/context/wiki
   remain future slices.
