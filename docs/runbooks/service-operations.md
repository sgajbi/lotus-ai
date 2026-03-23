# Service Operations Runbook

## Standard Commands

- make lint
- make typecheck
- make runtime-mode-smoke
- make ci
- docker compose up --build

`make ci` runs the security audit inside a temporary project-only virtual environment. This is intentional: the security gate should evaluate the `lotus-ai` dependency set, not unrelated packages installed in a shared developer workstation environment.

## Health and Readiness

- Liveness: /health/live
- Readiness: /health/ready
- General health: /health
- Metadata: /metadata
- Platform runtime status: /platform/runtime-status
- Async activation readiness: /platform/async/activation-readiness
- Async runbook readiness: /platform/async/runbook-readiness
- Async governance status: /platform/async/governance-status
- Async control-plane history: /platform/async/control-plane-actions
- Provider activation readiness: /platform/providers/activation-readiness
- Provider quota policy: /platform/providers/quota-policy
- Provider budget policy: /platform/providers/budget-policy
- Provider operations status: /platform/providers/operations-status
- Provider operations control history: /platform/providers/control-plane-actions
- Provider runbook readiness: /platform/providers/runbook-readiness
- Provider evidence readiness: /platform/providers/evidence-readiness
- Provider governance status: /platform/providers/governance-status
- Prompt activation readiness: /platform/prompts/activation-readiness
- Prompt runbook readiness: /platform/prompts/runbook-readiness
- Prompt evidence readiness: /platform/prompts/evidence-readiness
- Prompt governance status: /platform/prompts/governance-status
- Retrieval activation readiness: /platform/retrieval/activation-readiness
- Retrieval runbook readiness: /platform/retrieval/runbook-readiness
- Retrieval evidence readiness: /platform/retrieval/evidence-readiness
- Retrieval governance status: /platform/retrieval/governance-status
- Evaluation runtime status: /platform/evals/runtime-status
- Evaluation run catalog: /platform/evals/runs
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

Before any broader async activation slice:

1. verify `GET /platform/async/governance-status`
2. inspect `GET /platform/async/activation-readiness` when technical blockers need detail
3. inspect `GET /platform/async/runbook-readiness` when operational blockers need detail
4. confirm the embedded `async_governance` block in `GET /platform/runtime-status` matches the detailed async governance view
5. confirm queue backend and worker execution posture are still governed and explicitly selected
6. confirm retrieval indexing remains the only runtime-backed async consumer unless a broader rollout slice has been explicitly approved
7. confirm observability, replay, escalation, and incident procedures are documented and approved
8. only then proceed with any activation rollout review

## Durable Async Recovery

When `LOTUS_AI_ASYNC_RUNTIME_STORE_MODE=sqlalchemy`, runtime-backed async job, attempt, and lease state are durable rather than process-local.

Operator rules:

1. do not treat a service restart as a queue, claim, or recovery reset for runtime-backed async jobs
2. review `/platform/async/runtime-status`, `/platform/async/jobs`, and the relevant domain job-detail surface before assuming a claimed or failed job has cleared
3. treat staged async artifacts as historical or staged reference records; they do not override runtime-backed job truth
4. treat lease-expiry recovery as a durable control-plane transition that should be visible through async job attempt history rather than inferred from missing worker processes

Current recovery expectations:

1. queued, claimed, running, failed, completed, and abandoned posture must survive restart when the SQL-backed async-runtime store is active
2. lease expiry should record an `ABANDONED` attempt and queue a new retryable attempt rather than mutating the prior attempt in place
3. retrieval index jobs submitted through `POST /platform/retrieval/index-jobs/{job_id}/submit-async` should remain linked to their async runtime records after restart
4. duplicate runtime-backed retrieval-index submissions should be rejected while an active queued, claimed, or running job already owns the same caller and target
5. operator retry, replay, requeue, and abandon actions should be applied through `/platform/async/control-plane-actions/apply` rather than ad hoc table edits
6. dedicated queue-backed worker fleet procedures remain out of scope until a later rollout slice activates them
7. runtime-backed evaluation runs should preserve queued, claimed, running, completed, failed, and abandoned attempt history across async replay and recovery actions

Current governed control-action procedure:

1. inspect `/platform/async/control-plane-actions` to review recent async recovery and replay actions
2. inspect `/platform/async/jobs/{job_id}` to confirm the current runtime attempt history, active lease posture, and existing control events
3. apply `POST /platform/async/control-plane-actions/apply` with explicit operator reason and approver metadata
4. verify the resulting control-plane event is visible in both `/platform/async/control-plane-actions` and `/platform/async/jobs/{job_id}`
5. confirm the resulting job status and attempt history match the intended retry, replay, requeue, or abandon action

## Evaluation Approval Review

Before treating retrieval or provider evaluation evidence as approval-ready:

1. verify `GET /platform/evals/runtime-status`
2. confirm the `approval_gates` block distinguishes `STAGED_ONLY`, `RUNTIME_PARTIAL`, `RUNTIME_PASS`, `RUNTIME_FAIL`, or `RUNTIME_STALE`
3. inspect `GET /platform/evals/runs` to confirm the latest runtime-backed run is newer than historical staged baselines for the target rollout domain
4. inspect `GET /platform/evals/runs/{run_id}` to confirm attempt history and case outcomes explain the verdict
5. if replay or retry is required, apply the governed async control action first and then verify a new evaluation attempt appears instead of mutating prior case evidence in place
6. treat `foundation_eval_*` run artifacts as historical baselines only; they do not satisfy current runtime-backed approval posture by themselves

## Provider Activation Governance

Before any future live-provider activation slice:

1. verify `GET /platform/providers/governance-status`
2. inspect `GET /platform/providers/activation-readiness` when technical blockers need detail
3. inspect `GET /platform/providers/quota-policy`, `GET /platform/providers/budget-policy`, and `GET /platform/providers/operations-status` when quota, budget, or degradation blockers need detail
4. inspect `GET /platform/providers/runbook-readiness` when operational blockers need detail
5. inspect `GET /platform/providers/evidence-readiness` when evaluation, audit, or failover evidence blockers need detail
6. confirm the embedded `provider_governance` and `provider_operations` blocks in `GET /platform/runtime-status` match the detailed provider views
7. confirm provider policy and catalog still reflect governed disabled or stub posture unless explicitly approved otherwise
8. confirm staged provider policy, runtime, failure-mode, operations, and degradation fixtures plus the recorded provider regression baseline still match the intended rollout posture
9. confirm vendor escalation, quota response, spend-anomaly response, circuit-open response, rollback, and provider observability procedures are documented and approved
10. confirm provider-backed task runtime notes still describe the current rollout truthfully, especially when a live provider is allowlisted but intentionally disabled
11. treat technical, operational, and evidence blockers as separate activation gates that all must be satisfied
12. only then proceed with any live-provider activation rollout review

## Durable Provider Operations Recovery

When `LOTUS_AI_PROVIDER_OPERATIONS_STORE_MODE=sqlalchemy`, quota, budget, and degradation posture are durable rather than process-local.

Operator rules:

1. do not treat a service restart as a quota, spend, or circuit reset
2. review `/platform/providers/quota-policy`, `/platform/providers/budget-policy`, and `/platform/providers/operations-status` before assuming provider posture has cleared
3. investigate persistent blocking posture as durable control-plane state, not as stale process memory
4. use `POST /platform/providers/control-plane-actions/reset` for governed quota, budget, and degradation resets rather than ad hoc table edits

Current recovery expectations:

1. quota exhaustion remains durable until a governed rollover or reset action is applied and recorded
2. tracked spend remains durable until a governed budget reset action is applied and recorded
3. circuit-open posture remains durable until the persisted cooldown expires or a governed degradation reset action is applied and recorded
4. restart alone must not be used as an operational workaround for provider controls

Current governed reset procedure:

1. inspect `/platform/providers/control-plane-actions` to review recent provider control-plane actions
2. confirm `/platform/providers/quota-policy`, `/platform/providers/budget-policy`, and `/platform/providers/operations-status` reflect the blocking posture that requires intervention
3. apply `POST /platform/providers/control-plane-actions/reset` with explicit operator reason, requester, and approver metadata
4. verify the resulting control-plane event is visible in `/platform/providers/control-plane-actions`
5. re-check `/platform/providers/quota-policy`, `/platform/providers/budget-policy`, `/platform/providers/operations-status`, and the embedded `provider_operations` block in `/platform/runtime-status`

## Prompt Activation Governance

Before any future live-prompt activation slice:

1. verify `GET /platform/prompts/governance-status`
2. inspect `GET /platform/prompts/activation-readiness` when technical blockers need detail
3. inspect `GET /platform/prompts/runbook-readiness` when operational blockers need detail
4. inspect `GET /platform/prompts/evidence-readiness` when evaluation, audit, or rollback evidence blockers need detail
5. confirm the embedded `prompt_governance` block in `GET /platform/runtime-status` matches the detailed prompt governance view
6. confirm prompt governance and runtime-selection posture still reflect reviewed repository-governed rollout unless explicitly approved otherwise
7. confirm named approvers, rollback procedures, and prompt audit-evidence procedures are documented and approved
8. treat technical, operational, and evidence blockers as separate activation gates that all must be satisfied
9. only then proceed with any live-prompt activation rollout review

## Retrieval Activation Governance

Before any future live-retrieval activation slice:

1. verify `GET /platform/retrieval/governance-status`
2. inspect `GET /platform/retrieval/activation-readiness` when technical blockers need detail
3. inspect `GET /platform/retrieval/runbook-readiness` when operational blockers need detail
4. inspect `GET /platform/retrieval/evidence-readiness` when evaluation, citation, or rollback evidence blockers need detail
5. confirm the embedded `retrieval_governance` block in `GET /platform/runtime-status` matches the detailed retrieval governance view
6. confirm retrieval indexing policy and execution status still reflect governed staged posture unless explicitly approved otherwise
7. confirm the retrieval approval gate is backed by current runtime-produced live-search evidence rather than historical staged baselines alone
8. confirm reindex, replay, rollback, and retrieval observability procedures are documented and approved
9. treat technical, operational, and evidence blockers as separate activation gates that all must be satisfied
10. only then proceed with any live-retrieval activation rollout review

## Durable Retrieval Recovery

When `LOTUS_AI_RETRIEVAL_STORE_MODE=sqlalchemy`, searchable retrieval corpus state is durable rather than process-local.

Operator rules:

1. do not treat service restart as a retrieval index reset or corpus rollback
2. review `/platform/retrieval/execution-status`, `/platform/retrieval/source-governance`, and `/platform/retrieval/document-governance` before assuming live-search posture has changed
3. treat promoted indexed corpus state as authoritative durable metadata, not cache-like worker memory
4. use governed reindex and rollback procedures instead of ad hoc table edits when searchable corpus posture must change

Current recovery expectations:

1. promoted indexed documents remain searchable after repository or service restart when the SQL-backed retrieval store is active
2. rollback from `INDEXED` back to `STAGED` removes those documents from live search after restart or repository reinitialization
3. `/platform/retrieval/execution-status` must continue to report the live path truthfully even when the active searchable corpus is temporarily empty
4. retrieval search requests may still execute through the live path during rollback posture, but they must return explicit empty-hit behavior rather than silently degrading into catalog-only semantics

## Incident First Checks

1. Check container logs for request failures and stack traces.
2. Verify /health/ready and metrics endpoint.
3. Run local parity check (make ci) before hotfix PR.
