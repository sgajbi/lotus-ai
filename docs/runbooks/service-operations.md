# Service Operations Runbook

## Standard Commands

- make lint
- make typecheck
- make runtime-mode-smoke
- make ci
- docker compose up --build

`make ci` runs the security audit inside a temporary project-only virtual environment. This is intentional: the security gate should evaluate the `lotus-ai` dependency set, not unrelated packages installed in a shared developer workstation environment. Any temporary vulnerability ignore must remain explicit in `scripts/run_security_audit.py` with an upstream-fix note so operators can remove it once a patched release exists.

## Health and Readiness

- Liveness: /health/live
- Readiness: /health/ready
- General health: /health
- Metadata: /metadata
- Platform runtime status: /platform/runtime-status
- Resilience runtime status: /platform/resilience/runtime-status
- Resilience restore plan: /platform/resilience/restore-plan
- Resilience drill evidence: /platform/resilience/drill-evidence
- Resilience activation readiness: /platform/resilience/activation-readiness
- Resilience runbook readiness: /platform/resilience/runbook-readiness
- Resilience governance status: /platform/resilience/governance-status
- Deployment-split runtime status: /platform/deployment-split/runtime-status
- Deployment-split activation readiness: /platform/deployment-split/activation-readiness
- Deployment-split runbook readiness: /platform/deployment-split/runbook-readiness
- Deployment-split governance status: /platform/deployment-split/governance-status
- Production baseline runtime status: /platform/production-baseline/runtime-status
- Production baseline activation readiness: /platform/production-baseline/activation-readiness
- Production baseline runbook readiness: /platform/production-baseline/runbook-readiness
- Production baseline governance status: /platform/production-baseline/governance-status
- Artifact runtime status: /platform/artifacts/runtime-status
- Artifact catalog: /platform/artifacts
- Artifact activation readiness: /platform/artifacts/activation-readiness
- Artifact runbook readiness: /platform/artifacts/runbook-readiness
- Artifact governance status: /platform/artifacts/governance-status
- Observability runtime status: /platform/observability/runtime-status
- Observability activation readiness: /platform/observability/activation-readiness
- Observability runbook readiness: /platform/observability/runbook-readiness
- Observability governance status: /platform/observability/governance-status
- Observability incident summary: /platform/observability/incident-summary
- Observability breakdowns: /platform/observability/breakdowns
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
- Access-control activation readiness: /platform/access-control/activation-readiness
- Access-control runbook readiness: /platform/access-control/runbook-readiness
- Access-control governance status: /platform/access-control/governance-status
- Retrieval activation readiness: /platform/retrieval/activation-readiness
- Retrieval runbook readiness: /platform/retrieval/runbook-readiness
- Retrieval evidence readiness: /platform/retrieval/evidence-readiness
- Retrieval governance status: /platform/retrieval/governance-status
- Evaluation runtime status: /platform/evals/runtime-status
- Evaluation run catalog: /platform/evals/runs
- Safety runtime status: /platform/safety/runtime-status
- Safety evidence readiness: /platform/safety/evidence-readiness
- Safety runbook readiness: /platform/safety/runbook-readiness
- Safety governance status: /platform/safety/governance-status
- Retrieval runtime status: /platform/retrieval/runtime-status
- First production use-case contract: /platform/use-cases/first-production-use-case
- First production use-case readiness: /platform/use-cases/first-production-use-case/readiness
- First production use-case runbook readiness: /platform/use-cases/first-production-use-case/runbook-readiness
- First production use-case governance status: /platform/use-cases/first-production-use-case/governance-status

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
6. verify `GET /platform/safety/evidence-readiness` when runtime safety approval posture matters
7. verify `GET /platform/safety/governance-status` when runtime safety rollout posture matters
8. verify `GET /platform/retrieval/runtime-status` when retrieval persistence is relevant
9. only then proceed with rollout if readiness is `READY`

## Resilience Governance

Before treating service continuity posture as anything stronger than bounded governed recovery truth:

1. verify `GET /platform/resilience/runtime-status`
2. inspect `GET /platform/resilience/restore-plan` to confirm restore ordering, validation criteria, and rollback boundaries before treating continuity as operator-ready
3. inspect `GET /platform/resilience/drill-evidence` to confirm required recovery-proof evidence is current rather than only staged
4. inspect `GET /platform/resilience/activation-readiness` when technical blockers need detail
5. inspect `GET /platform/resilience/runbook-readiness` when operator-readiness blockers need detail
6. inspect `GET /platform/resilience/governance-status` for the composed recovery view
7. confirm the embedded `resilience_runtime` and `resilience_governance` blocks in `GET /platform/runtime-status` match the detailed resilience views
8. inspect `recovery_state`, `recovery_attention_dependency_count`, and dependency-level `recovery_findings` before treating a restart as a restored platform
9. treat `LOCAL_OR_DEMO_CONTINUITY` as local or demo durability only, not as restart-safe production posture
10. treat `PARTIAL_RUNTIME_DURABILITY` as evidence that some critical dependencies are durable while others still require external recovery or remain blocked
11. treat current drill-evidence posture as bounded platform proof only; it does not imply backup automation or full disaster-recovery orchestration

CI also runs `make runtime-mode-smoke` as a dedicated gate so SQL-backed startup, readiness, and migration behavior remain continuously verified.

## Production Baseline Governance

Before treating any environment as the accepted RFC-0020 production baseline:

1. verify `GET /platform/production-baseline/runtime-status`
2. inspect `GET /platform/production-baseline/activation-readiness` when technical blockers need detail
3. inspect `GET /platform/production-baseline/runbook-readiness` when operator-readiness blockers need detail
4. inspect `GET /platform/production-baseline/governance-status` for the composed go-live view
5. confirm the embedded `production_baseline` and `production_baseline_governance` blocks in `GET /platform/runtime-status` match the detailed production-baseline views
6. treat PostgreSQL-backed durable stores plus Redis and dedicated workers as the minimum prod-shaped local boundary, not as full production readiness
7. keep local env-file secret handling and filesystem or memory-backed artifact payload storage classified as non-production even if Docker bring-up and live-provider execution both succeed

## Deployment-Split Governance

Before treating any RFC-0015 split stage as a governed active topology:

1. verify `GET /platform/deployment-split/runtime-status`
2. inspect `GET /platform/deployment-split/activation-readiness` when configured-stage versus effective-stage blockers need detail
3. inspect `GET /platform/deployment-split/runbook-readiness` when operator-readiness blockers need detail
4. inspect `GET /platform/deployment-split/governance-status` for the composed rollout view
5. confirm the embedded `deployment_split` and `deployment_split_governance` blocks in `GET /platform/runtime-status` match the detailed deployment-split views
6. treat the runtime plane as the only supported external front door even when retrieval and eval planes are active internally
7. treat rollback to `UNIFIED` as the first supported rollback target whenever retrieval or eval split posture remains blocked or degraded
8. confirm `GET /platform/observability/runtime-status` and the retrieval and evaluation runtime surfaces still expose coherent split-plane truth before treating an active split stage as healthy

## Artifact Governance

Before treating the artifact backbone as stronger governed rollout posture:

1. verify `GET /platform/artifacts/runtime-status`
2. inspect `GET /platform/artifacts` to confirm active, superseded, archived, and staged posture are explicitly visible through descriptors
3. inspect `GET /platform/artifacts/activation-readiness` when technical blockers need detail
4. inspect `GET /platform/artifacts/runbook-readiness` when operational blockers need detail
5. inspect `GET /platform/artifacts/governance-status` for the composed governance view
6. confirm the embedded `artifact_runtime` and `artifact_governance` blocks in `GET /platform/runtime-status` match the detailed artifact views
7. treat artifact archive posture as a reviewable metadata transition rather than ad hoc payload deletion or raw filesystem cleanup

## Observability Governance

Before treating the in-service observability layer as governed rollout posture:

1. verify `GET /platform/observability/runtime-status`
2. inspect `GET /platform/observability/activation-readiness` when technical blockers need detail
3. inspect `GET /platform/observability/runbook-readiness` when operational blockers need detail
4. inspect `GET /platform/observability/governance-status` for the composed governance view
5. confirm the embedded `observability_runtime` and `observability_governance` blocks in `GET /platform/runtime-status` match the detailed observability views
6. confirm `GET /platform/observability/incident-summary` covers provider, retrieval, async, evaluation, prompt, and safety domains without unavailable telemetry posture
7. confirm `GET /platform/observability/breakdowns` still exposes bounded caller, tenant, and capability samples without leaking unauthorized tenant data
8. confirm observability incident items now expose governed artifact descriptors rather than raw payloads or backend URLs
9. treat SQL-backed audit and caller-policy stores as the activation gate for restart-safe observability governance

Current incident-review expectations:

1. use `GET /platform/observability/incident-summary` as the summary-first entrypoint for provider, retrieval, async, evaluation, prompt, and safety review
2. inspect the `artifact_refs` attached to each incident-evidence item when bounded historical or diagnostic context is needed
3. treat those artifact refs as governed snapshots of the domain incident bundle rather than as a raw export surface
4. use the linked domain endpoints for deeper runtime and governance inspection instead of expecting observability routes to dump raw payloads inline

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
6. when `cutover_state=dedicated_workers_active`, queue backlog, duplicate/redelivery counts, active worker identities, and degraded findings should be reviewed through `/platform/async/runtime-status`
7. `LOTUS_AI_ASYNC_WORKER_DRAIN_ENABLED=true` should prevent new dedicated worker claims while leaving queued runtime truth and governed replay/requeue actions intact
8. runtime-backed evaluation runs should preserve queued, claimed, running, completed, failed, and abandoned attempt history across async replay and recovery actions

Current dedicated worker operational checks:

1. review `/platform/async/runtime-status` for `queue_backlog_count`, `active_worker_ids`, `duplicate_delivery_count`, `redelivery_count`, `drain_mode_active`, and `degraded_findings`
2. if queue backlog is growing while `active_worker_ids` is empty, treat the worker fleet as unavailable rather than assuming in-process execution has taken over
3. if `drain_mode_active=true`, expect queued jobs to remain queued until drain mode is cleared; do not bypass the queue by manually invoking in-process worker paths
4. if `cutover_state=degraded_fallback`, treat the worker fleet as explicitly degraded and require operator review before considering the rollout healthy again

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

## Safety Governance Review

Before treating runtime safety enforcement as governed rollout posture:

1. verify `GET /platform/safety/runtime-status`
2. verify `GET /platform/safety/runbook-readiness`
3. verify `GET /platform/safety/evidence-readiness`
4. verify `GET /platform/safety/governance-status`
5. confirm the safety approval gate distinguishes `STAGED_ONLY`, `RUNTIME_PARTIAL`, `RUNTIME_PASS`, `RUNTIME_FAIL`, and `RUNTIME_STALE`
6. confirm task execution, audit records, and execution evidence still agree on blocked, degraded, redacted, and pass-through safety outcomes
7. treat runtime safety enforcement as stateless: persisted audit records, execution evidence, and runtime-backed evaluation runs are authoritative, not process-local reset behavior
8. treat staged safety fixture packs and historical `foundation_eval_*` artifacts as continuity evidence only; they do not satisfy current runtime-backed safety approval posture by themselves

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
9. confirm vendor escalation, quota response, spend-anomaly response, circuit-open response, rollback, and provider incident-review procedures are documented and approved
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

Before applying a governed prompt promotion or rollback:

1. verify `GET /platform/prompts/governance-status`
2. inspect `GET /platform/prompts/activation-readiness` when technical blockers need detail
3. inspect `GET /platform/prompts/runbook-readiness` when operational blockers need detail
4. inspect `GET /platform/prompts/evidence-readiness` when evaluation, audit, or rollback evidence blockers need detail
5. confirm the embedded `prompt_governance` block in `GET /platform/runtime-status` matches the detailed prompt governance view
6. confirm prompt governance and runtime-selection posture still reflect reviewed repository-governed prompt bodies plus governed rollout-state actions
7. confirm prompt promotion is blocked unless the prompt approval gate reports `RUNTIME_PASS`
8. treat technical, operational, and evidence blockers as separate activation gates that all must be satisfied
9. only then proceed with any live-prompt activation rollout review

Current governed control-action procedure:

1. inspect `/platform/prompts/control-history?task_id=<task_id>` to review the latest promote or rollback actions for the target task
2. inspect `/platform/prompts/runtime-status` to confirm the current active, candidate, and previous-active prompt versions for that task
3. inspect `/platform/prompts/evidence-readiness` to confirm the prompt approval gate reports `RUNTIME_PASS` before promotion
4. apply `POST /platform/prompts/control-actions` with explicit requested-by, approved-by, and reason metadata
5. verify the resulting control-plane event is visible in both `/platform/prompts/control-history` and the task-specific rollout state in `/platform/prompts/runtime-status`
6. verify post-change task execution and `/ai/audit` records show the expected selected prompt version and latest control event

Current rollback and incident-response expectations:

1. use the governed rollback action instead of mutating prompt rows or rollout state directly
2. confirm `/platform/prompts/runtime-status` shows the restored active prompt version and the latest rollback event after the action completes
3. inspect `/platform/prompts/evidence-readiness` and the relevant runtime-backed evaluation run before re-promoting a candidate after a regression
4. treat prompt regression review as an evidence-backed operator process: compare the current runtime prompt selection, recent control history, and task-linked audit traces before deciding whether to re-promote or keep the rollback in place

Restart-survival expectations:

1. when `LOTUS_AI_PROMPT_STORE_MODE=sqlalchemy`, the active prompt version, candidate prompt version, previous-active lineage, and prompt control history must survive service restart
2. when `LOTUS_AI_EVALUATION_RUNTIME_STORE_MODE=sqlalchemy`, prompt approval evidence must survive service restart and remain inspectable through the prompt approval gate
3. restart must not be used as a workaround to clear prompt rollout history or revert a prompt change

## Access-Control Governance

Before treating caller identity and tenant isolation as fully governed rollout posture:

1. verify `GET /platform/access-control/runtime-status`
2. inspect `GET /platform/access-control/activation-readiness` when technical blockers need detail
3. inspect `GET /platform/access-control/runbook-readiness` when operational blockers need detail
4. inspect `GET /platform/access-control/governance-status` for the composed governance view
5. confirm the embedded `access_control_runtime` and `access_control_governance` blocks in `GET /platform/runtime-status` match the detailed access-control views
6. confirm unknown callers still fail closed on protected data-plane and control-plane paths
7. treat SQL-backed caller policy storage as the activation gate for restart-safe access-control governance

Current operational expectations:

1. caller onboarding, revocation, tenant restriction changes, blocked-authorization review, and emergency-override posture are documented runbook items
2. there is no hidden emergency bypass API in RFC-0012; fail-closed behavior is intentional and should be treated as the documented emergency posture
3. blocked task requests should be reviewed through `/ai/audit` and task execution evidence, while blocked control-plane actions should be reviewed through the relevant control history endpoint
4. authorized async, prompt, and provider control actions must preserve the recorded caller authorization decision in durable control history

## Retrieval Activation Governance

Before any future live-retrieval activation slice:

1. verify `GET /platform/retrieval/governance-status`
2. inspect `GET /platform/retrieval/activation-readiness` when technical blockers need detail
3. inspect `GET /platform/retrieval/runbook-readiness` when operational blockers need detail
4. inspect `GET /platform/retrieval/evidence-readiness` when evaluation, citation, or rollback evidence blockers need detail
5. confirm the embedded `retrieval_governance` block in `GET /platform/runtime-status` matches the detailed retrieval governance view
6. confirm retrieval indexing policy and execution status still reflect governed staged posture unless explicitly approved otherwise
7. confirm the retrieval approval gate is backed by current runtime-produced live-search evidence rather than historical staged baselines alone
8. inspect `GET /platform/retrieval/ingestion-status` and `GET /platform/retrieval/document-governance` to confirm refresh-pending, withdrawn, and index-pending corpus posture is explicit before treating a search outage as a generic indexing failure
9. inspect `GET /platform/retrieval/ingestion-jobs/{job_id}` and the attached `artifact_refs` when a corpus-change job reaches failed or completed posture and bounded diagnostics are needed
10. confirm reindex, replay, rollback, and retrieval incident-review procedures are documented and approved
11. treat technical, operational, and evidence blockers as separate activation gates that all must be satisfied
12. only then proceed with any live-retrieval activation rollout review

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
4. retrieval search requests must reject explicitly when live retrieval is enabled but the searchable promoted corpus is unavailable, rather than silently degrading into catalog-only semantics or pretending the request was a normal empty-result live search

## Incident First Checks

1. Check container logs for request failures and stack traces.
2. Verify /health/ready and metrics endpoint.
3. Run local parity check (make ci) before hotfix PR.

## First Use-Case Governance

Before treating `lotus-performance` analytics commentary as limited governed rollout posture:

1. verify `GET /platform/use-cases/first-production-use-case`
2. inspect `GET /platform/use-cases/first-production-use-case/readiness` when runtime-backed evidence, audit durability, or bounded incident-review blockers need detail
3. inspect `GET /platform/use-cases/first-production-use-case/runbook-readiness` when shared ownership, rollback, support, or unsupported-input triage posture needs detail
4. inspect `GET /platform/use-cases/first-production-use-case/governance-status` for the composed limited-rollout view
5. confirm the embedded `first_use_case` and `first_use_case_governance` blocks in `GET /platform/runtime-status` match the detailed use-case views
6. confirm `GET /platform/evals/runtime-status` still reports the `first_use_case_onboarding` approval gate truthfully
7. confirm `GET /platform/resilience/governance-status` is also ready before treating limited rollout as credible continuity-backed posture
8. confirm `GET /platform/observability/incident-summary` and any attached artifact descriptors remain available for bounded incident review of the first use case
9. only then proceed with any limited downstream rollout review

Current rollback and support expectations:

1. if first-use-case governance becomes blocked, treat downstream activation as blocked rather than treating commentary variance as a normal runtime fluctuation
2. inspect `/ai/audit`, `/platform/observability/incident-summary`, and attached artifact descriptors before re-enabling downstream exposure
3. treat incomplete or unsupported analytics input shape as a distinct support path owned jointly by lotus-performance and lotus-ai, not as a prompt-tuning issue alone
