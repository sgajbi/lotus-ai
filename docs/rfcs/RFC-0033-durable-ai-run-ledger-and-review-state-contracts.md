# RFC-0033: Durable AI Run Ledger and Review-State Contracts

- Status: In Progress
- Date: 2026-04-18
- Owners:
  - lotus-ai maintainers
  - lotus-gateway maintainers
  - lotus-workbench maintainers
- Requires Approval From:
  - lotus-ai maintainers
  - lotus-gateway maintainers
  - lotus-workbench maintainers
  - lotus-platform maintainers
  - maintainers of any repository that introduces consequence-bearing review flows backed by this
    model
- Related:
  - `RFC-0006-durable-async-execution-backbone.md`
  - `RFC-0013-runtime-observability-and-incident-evidence.md`
  - `RFC-0014-governed-artifact-and-object-storage-backbone.md`
  - `RFC-0023-multi-app-adoption-and-capability-rollout-governance.md`
  - `RFC-0026-operator-control-plane-dashboard-and-observability-integration.md`
  - `RFC-0031-governed-agent-workflow-packs-and-bounded-ai-runtime.md`
  - `RFC-0032-governed-workflow-pack-registry-and-activation-posture.md`
  - `../../../lotus-platform/rfcs/RFC-0070-gold-standard-product-experience-foundation-and-ownership-model.md`
  - `../../../lotus-platform/rfcs/RFC-0072-platform-wide-multi-lane-ci-validation-and-release-governance.md`
  - `../../../lotus-platform/rfcs/RFC-0081-slice-9-ai-surface-governance-and-assistive-workflow-controls-evidence.md`
  - `../../../lotus-workbench/docs/rfcs/RFC-0020-ai-advisor-brief-copilot.md`

## Summary

`RFC-0031` defines the bounded workflow-pack runtime direction.

`RFC-0032` defines how workflow-pack definitions become registered and activated in `lotus-ai`.

What Lotus still lacks is a durable, inspectable record of actual workflow-pack runs and a shared
contract model for review-bearing AI output.

This RFC defines that missing layer.

The decision is:

1. every workflow-pack execution that is async, review-bearing, or artifact-producing must create a
   durable pack-run ledger record,
2. runtime execution state and product review state must be modeled separately,
3. `lotus-ai` owns the durable run ledger and runtime evidence references,
4. calling systems own consequence-bearing review actions and workflow authority,
5. `lotus-gateway` and `lotus-workbench` consume one standard review-state contract family rather
   than inventing page-local AI status semantics.

The goal is to make every meaningful AI-assisted workflow run:

1. auditable,
2. supportable,
3. reviewable,
4. operationally truthful,
5. clearly subordinate to business workflow truth.

## Implementation Status

This RFC is now partially implemented.

Current prerequisite foundations that now exist in `lotus-ai`:

1. workflow-pack registry identity and owner-artifact grounding from `RFC-0032`,
2. eligibility evaluation and bounded activation posture for registered workflow-pack versions,
3. migration-backed registry activation state and control history that make current runtime posture durable when the SQL-backed registry store is enabled and ready.

Implemented on the current branch:

1. workflow-pack run-ledger contract models for runtime state, review state, lineage-ready run identity, and run-history events,
2. workflow-pack run store seam and in-memory repository implementation,
3. read-only workflow-pack run catalog and detail APIs,
4. Phase-1 explicit execution for `advisor_brief.pack`, with run recording bound to a dedicated workflow-pack execution route instead of relying only on the generic task path,
5. migration-managed SQL-backed workflow-pack run and event tables plus a SQLAlchemy repository implementation,
6. runtime-readiness, startup-policy, and platform-status integration for the workflow-pack run store so durable ledger posture is inspectable instead of implied,
7. bounded review-action contracts and service seams for actor-attributed `ACCEPT`, `REJECT`, `REVISE`, `SUPERSEDE`, and `ABANDON` transitions, including lineage preservation between original and replacement runs,
8. bounded `allowed_review_actions` emitted on workflow-pack run descriptors so downstream consumers can render ledger-compatible next-step posture without inferring review semantics from raw state alone,
9. a bounded workflow-pack run consumer view that groups runtime, review, lineage, and provenance into one shared contract candidate for downstream composition layers.

What is not implemented yet:

1. shared runtime-state and review-state contracts exposed across `lotus-ai`, `lotus-gateway`, and
   `lotus-workbench`,
2. broader durable linkage expansion from workflow-pack execution into downstream artifact,
   review-action entitlement, and support-evidence flows beyond the current bounded Phase-1 slice,
3. UI and gateway consumption that renders run state and review state as separate dimensions,
4. consequence-bearing downstream review integration flows and allowed-action shaping outside the bounded lotus-ai ledger surface,
5. broader workflow-pack runtime adoption beyond the current Phase-1 advisor-brief recording path.

This RFC now correctly moves to `In Progress`, but it should not be treated as complete until downstream contract adoption, artifact and evidence linkage expansion, and broader runtime integration are implemented and reflected in the RFC, RFC index, and branch evidence together.

## Prerequisite Evidence And Open Gaps

This RFC now has clearer prerequisites because the workflow-pack registry layer exists.

Evidence the prerequisite layer is real:

1. workflow-pack identity, owner-artifact grounding, and activation metadata in
   `src/app/contracts/workflow_packs.py` and `src/app/services/workflow_pack_registry.py`,
2. current registry, eligibility, and operator-control surfaces in `src/app/routers/workflow_packs.py`,
3. branch coverage for those foundations in `tests/unit/test_workflow_pack_registry.py`,
   `tests/unit/test_workflow_pack_activation.py`, `tests/unit/test_workflow_pack_control.py`,
   `tests/integration/test_workflow_pack_registry_api_contract.py`,
   `tests/integration/test_workflow_pack_activation_api_contract.py`, and
   `tests/integration/test_workflow_pack_control_api_contract.py`.

Open gaps this RFC is still meant to close:

1. no durable run identity beyond current request and control-plane surfaces,
2. no shared run-status and review-status contract family exposed for product consumption,
3. no broad downstream contract family yet carries durable artifact, review-action entitlement, and
   support-evidence linkage for workflow-pack executions beyond the bounded Phase-1 slice,
4. no gateway or Workbench contract proving that runtime state and review state remain separate in
   user-facing flows.

## Why This RFC Exists

Once Lotus introduces workflow packs, "request in, response out" is no longer enough for the
important cases.

The platform now needs to support flows where:

1. a pack run may take time,
2. output may be partial or staged,
3. a human reviewer may need to inspect it before consequence-bearing use,
4. generated artifacts may need durable references,
5. support teams may need to explain what happened after the fact.

If Lotus does not define one durable run ledger and one review-state contract family, the likely
outcome is fragmented local behavior:

1. one application invents its own status values,
2. another stores AI drafts in workflow tables with no clean runtime lineage,
3. a third has async jobs but no review linkage,
4. support teams cannot reconstruct whether a user saw a draft, a completed result, a partial
   result, or a rejected one.

The platform already has strong foundations for:

1. durable async execution,
2. runtime observability,
3. governed artifact references,
4. operator control-plane posture.

This RFC uses those foundations to define the application-facing execution ledger and review-state
truth required for workflow-pack adoption.

## Problem Statement

Today Lotus does not yet have one shared answer to these questions for workflow-pack executions:

1. what run id represents this invocation,
2. which workflow pack and version produced the output,
3. whether the run is still executing, has completed, failed, partially completed, or expired,
4. what evidence or artifacts were produced,
5. whether the output is still awaiting human review,
6. whether it was accepted, rejected, revised, superseded, or abandoned,
7. which service owns consequence-bearing workflow action after the AI output exists,
8. how a UI should render AI-generated output versus authoritative workflow truth.

That gap is a serious product and supportability problem.

Without a standard run ledger and review-state model:

1. AI-generated output can be mistaken for workflow truth,
2. async work can complete with no clean product linkage,
3. review actions can be recorded inconsistently or not at all,
4. operational triage can become a manual reconstruction exercise,
5. applications can drift into incompatible AI state models.

Lotus needs one durable runtime ledger and one bounded review-state contract family before these
workflows scale.

## Goals

1. Introduce a durable pack-run ledger for workflow-pack executions.
2. Keep runtime execution state separate from review-state semantics.
3. Standardize the minimum review-state contract for AI-generated workflow output.
4. Preserve clear ownership boundaries between runtime, composition, and workflow authority.
5. Make evidence, artifact, and review linkage durable and inspectable.
6. Support both synchronous and asynchronous workflow-pack executions through one consistent model.
7. Improve supportability and operator diagnosis through explicit ledger records and state history.

## Non-Goals

1. Defining the workflow-pack registry or activation model.
2. Defining every application-specific Workbench interaction detail.
3. Letting `lotus-ai` take workflow authority over approval, consent, booking, execution, or source
   truth.
4. Replacing domain workflow tables with one central AI workflow database.
5. Turning the pack-run ledger into a generic business process engine.
6. Storing all artifact payloads directly in the pack-run ledger rather than using governed artifact
   references.

## Scope Boundary

This RFC defines:

1. pack-run ledger identity and persistence model,
2. runtime-state and review-state separation,
3. review-state contract vocabulary,
4. evidence and artifact linkage requirements,
5. caller-facing and UI-facing contract expectations,
6. operator and supportability implications.

This RFC does not define:

1. registry activation rules,
2. the full workflow-pack runtime engine,
3. full UI layouts,
4. business-domain workflow schemas beyond the integration points required for review-bearing AI
   output.

## Decision

Lotus will introduce a durable AI run ledger and standard review-state contracts for workflow-pack
executions.

### Rule 1: Every meaningful workflow-pack execution gets a durable run record

At minimum, this applies to:

1. asynchronous runs,
2. review-bearing runs,
3. artifact-producing runs,
4. runs whose output may be revisited after the original request/response cycle.

### Rule 2: Runtime execution state and review state are separate dimensions

The runtime answers:

1. has the run started,
2. is it still executing,
3. did it complete,
4. did it fail,
5. did it expire.

The review layer answers:

1. is the output awaiting review,
2. was it accepted,
3. was it rejected,
4. was it revised,
5. was it superseded.

Those two dimensions must not be merged into one ambiguous status field.

### Rule 3: `lotus-ai` owns the pack-run ledger, not workflow authority

`lotus-ai` owns:

1. pack-run identity,
2. runtime timestamps and state,
3. evidence and artifact references,
4. generated output references,
5. review-state linkage metadata,
6. run history needed for audit and support.

It does not own:

1. final workflow decisions,
2. business approval state,
3. consent state,
4. booking or execution authority.

### Rule 4: Consequence-bearing review actions remain owned by the calling workflow

The calling service or composition layer remains responsible for:

1. who may review,
2. what acceptance means,
3. what rejection means,
4. what revisions do to downstream workflow state,
5. what authoritative business state changes when an AI output is accepted.

### Rule 5: Gateway and Workbench must consume one bounded contract family

`lotus-gateway` and `lotus-workbench` should not invent local AI state vocabularies for each flow.

They should consume one shared contract family for:

1. run identity,
2. runtime status,
3. review status,
4. provenance,
5. supportability and degradation,
6. allowed next actions.

## Relationship to Existing RFCs

### Relationship to RFC-0006

`RFC-0006` created the durable async execution backbone.

This RFC builds on that backbone, but is narrower in one sense and broader in another.

It is narrower because it does not redefine the async runtime itself.

It is broader because it defines the application-facing run-ledger model for workflow-pack
executions, including synchronous runs that still need durable review linkage.

### Relationship to RFC-0013

`RFC-0013` created runtime observability and incident evidence.

This RFC depends on those surfaces for supportability and diagnosis, but focuses on the execution
ledger and review semantics rather than platform telemetry.

### Relationship to RFC-0014

`RFC-0014` defines governed artifact storage.

This RFC assumes artifacts are referenced, not inlined.

The pack-run ledger stores artifact descriptors and lineage refs, not arbitrary payload blobs.

### Relationship to RFC-0031

`RFC-0031` defines the workflow-pack runtime direction.

This RFC defines the durable run-ledger and review-state contract layer needed to make that runtime
operationally usable in product surfaces.

### Relationship to RFC-0032

`RFC-0032` answers:

1. what is registered,
2. what is active,
3. who may invoke it.

This RFC answers:

1. what happened when it ran,
2. what output exists,
3. what review state that output is in,
4. how product surfaces and support teams should understand that run.

## Principles

### 1. Every meaningful AI workflow run must be reconstructable

The system should be able to explain:

1. what was invoked,
2. when it ran,
3. what happened,
4. what it produced,
5. who reviewed it,
6. what state it is now in.

### 2. Review state is not runtime state

A run may complete successfully and still be awaiting review.

A run may fail and therefore never enter review.

A run may be superseded after completion.

That separation is essential for truthful product behavior.

### 3. Output state must remain subordinate to workflow truth

Review status exists to govern AI-generated output.

It must never impersonate authoritative domain workflow state.

### 4. Supportability needs stable identifiers and explicit transitions

State transitions should be finite, inspectable, and durable.

Ad hoc prose or page-local booleans are not enough.

### 5. Evidence and artifacts must be linkable without duplicating storage concerns

The run ledger should reference evidence bundles and generated artifacts.

It should not become an uncontrolled content store.

## State Authority and Invariants

This RFC establishes the following authority rules.

1. pack-run identity, runtime state, review state linkage, and run history must come from one
   durable ledger in `lotus-ai`,
2. artifact payload content must remain in the governed artifact backbone where payload size or
   retention posture requires it,
3. gateway and Workbench views must derive run and review truth from the shared ledger contract
   rather than page-local reconstruction,
4. consequence-bearing business workflow state must remain in the owning workflow system rather than
   being mirrored as if it were runtime truth in `lotus-ai`,
5. revision, rejection, acceptance, supersession, and expiry history must remain reconstructable
   after restart and across deployment instances.

The following invariants must hold:

1. every review-bearing output maps to exactly one durable `pack_run_id`,
2. every durable `pack_run_id` resolves to exactly one pack id, version, and registration lineage,
3. review transitions must be actor-attributed and timestamped,
4. supersession must preserve links between the prior and replacement output or run,
5. no UI surface may silently collapse runtime state and review state into one ambiguous value.

## Pack-Run Identity Model

Every durable workflow-pack execution should have one stable run identity.

Minimum required fields:

1. `pack_run_id`
2. `pack_id`
3. `pack_version`
4. `registration_ref`
5. `caller_app`
6. `caller_correlation_id`
7. `requested_by`
8. `tenant_id`
9. `workflow_surface`
10. `workflow_authority_owner`
11. `requested_at`
12. `execution_mode`

### Identity rules

1. `pack_run_id` is the durable primary reference for runtime, support, and UI contracts.
2. `registration_ref` must point to the registry record that allowed the run.
3. `caller_correlation_id` should preserve caller-side traceability without replacing `pack_run_id`
   as ledger truth.
4. `workflow_authority_owner` must be explicit so review-bearing output never loses its downstream
   owner.

## Pack-Run Ledger Model

The ledger should store one primary row or durable record per pack run plus durable related history
records.

### Minimum primary fields

1. `pack_run_id`
2. `pack_id`
3. `pack_version`
4. `registration_ref`
5. `runtime_state`
6. `review_state`
7. `review_required`
8. `output_ref`
9. `evidence_bundle_ref`
10. `artifact_refs`
11. `error_code`
12. `error_summary`
13. `supportability_state`
14. `submitted_at`
15. `started_at`
16. `completed_at`
17. `expired_at`
18. `last_updated_at`

### Minimum related history

1. runtime transition history,
2. review transition history,
3. operator or reviewer action history,
4. artifact lineage changes where relevant,
5. supersession links where a newer run replaces an older output.

## Runtime State Model

Runtime state describes execution posture only.

Recommended states:

1. `SUBMITTED`
2. `VALIDATING`
3. `RUNNING`
4. `PARTIAL`
5. `COMPLETED`
6. `FAILED`
7. `CANCELLED`
8. `EXPIRED`

### Meaning

1. `SUBMITTED`
   the run exists durably but execution has not yet started.
2. `VALIDATING`
   the runtime is validating activation, inputs, or pack prerequisites.
3. `RUNNING`
   the pack is actively executing.
4. `PARTIAL`
   the runtime produced incomplete or degraded output that is still durably recorded.
5. `COMPLETED`
   the runtime finished and the output is available.
6. `FAILED`
   execution ended without a usable output.
7. `CANCELLED`
   the run was explicitly stopped.
8. `EXPIRED`
   the run or its pending output is no longer valid for continued use.

### Runtime invariants

1. only `COMPLETED` or `PARTIAL` runs may produce reviewable outputs,
2. `FAILED`, `CANCELLED`, and `EXPIRED` runs may still carry evidence and incident references,
3. runtime transitions must be durably timestamped and reconstructable.

## Review State Model

Review state describes the posture of AI-generated output after or around execution.

Recommended states:

1. `NOT_APPLICABLE`
2. `AWAITING_REVIEW`
3. `IN_REVIEW`
4. `ACCEPTED`
5. `REJECTED`
6. `REVISED`
7. `SUPERSEDED`
8. `ABANDONED`
9. `EXPIRED`

### Meaning

1. `NOT_APPLICABLE`
   no review is required for this run or no output exists to review.
2. `AWAITING_REVIEW`
   output exists and is waiting for explicit review.
3. `IN_REVIEW`
   the output is being actively assessed or revised by the owning workflow.
4. `ACCEPTED`
   the owning workflow accepted the AI-generated output for its intended use.
5. `REJECTED`
   the output was explicitly declined.
6. `REVISED`
   the output was modified or redrafted through a governed revision path.
7. `SUPERSEDED`
   a newer run or newer output replaced this one.
8. `ABANDONED`
   the review path was intentionally dropped without acceptance.
9. `EXPIRED`
   the reviewable output is no longer valid for use because of time, state change, or policy.

### Review invariants

1. review state must not exist without durable linkage to a run or run output,
2. `ACCEPTED` is a statement about AI output usage, not about authoritative domain workflow truth,
3. `SUPERSEDED` must preserve lineage to the replacing run or output,
4. `REVISED` must not erase original output lineage.

## Runtime and Review State Interaction

These dimensions must remain separate but related.

Examples:

1. `COMPLETED` + `AWAITING_REVIEW`
   normal path for a completed draft awaiting human action.
2. `PARTIAL` + `AWAITING_REVIEW`
   degraded output exists but remains reviewable with explicit supportability signaling.
3. `COMPLETED` + `ACCEPTED`
   output was produced and then accepted by the owning workflow.
4. `FAILED` + `NOT_APPLICABLE`
   no reviewable output exists.
5. `COMPLETED` + `SUPERSEDED`
   output existed, but a later run replaced it.

This separation is what prevents AI state from being conflated with business workflow state.

## Output, Evidence, and Artifact Model

The ledger should reference three related but distinct objects.

### 1. Output reference

The canonical generated output payload or structured result that the calling workflow uses.

### 2. Evidence bundle reference

The provenance bundle that explains:

1. source refs,
2. retrieval posture,
3. supportability warnings,
4. registration and activation lineage,
5. relevant prompt or provider metadata.

### 3. Artifact references

Generated or attached durable artifacts such as:

1. document drafts,
2. review summaries,
3. operator evidence bundles,
4. large structured outputs stored via the governed artifact backbone.

## Caller Contract Shape

The exact wire schema can evolve, but the contract family should support a shape like:

```json
{
  "pack_run_id": "prun-123",
  "pack": {
    "pack_id": "advisor_brief",
    "version": "v1"
  },
  "runtime": {
    "state": "COMPLETED",
    "submitted_at": "2026-04-18T10:00:00Z",
    "completed_at": "2026-04-18T10:00:12Z",
    "supportability_state": "SUPPORTED_WITH_WARNINGS"
  },
  "review": {
    "required": true,
    "state": "AWAITING_REVIEW",
    "allowed_actions": ["accept", "reject", "request_revision"]
  },
  "lineage": {
    "registration_ref": "preg-456",
    "evidence_bundle_ref": "evid-789",
    "artifact_refs": ["art-001"]
  }
}
```

## Gateway Responsibilities

`lotus-gateway` should own:

1. mapping ledger records into product-safe response contracts,
2. preserving distinction between authoritative workflow state and AI output state,
3. exposing allowed next actions according to the owning workflow,
4. carrying supportability and provenance fields through to Workbench.

It should not:

1. rewrite runtime history,
2. invent new review-state semantics,
3. blur review acceptance into authoritative workflow approval.

## Workbench Responsibilities

`lotus-workbench` should render:

1. runtime state,
2. review state,
3. provenance and evidence availability,
4. allowed next actions,
5. degradation and supportability signals.

It should not:

1. locally infer pack-run truth,
2. invent page-specific AI status vocabularies,
3. treat `ACCEPTED` as equivalent to business workflow completion unless the owning workflow says
   so through gateway contracts.

## Ownership Model

Each run has explicit ownership layers.

### 1. Runtime ledger ownership

Owned by `lotus-ai`.

### 2. Product composition ownership

Owned by the calling application or composition layer, often `lotus-gateway`.

### 3. Review authority ownership

Owned by the service or product surface that controls workflow consequences.

### 4. Domain truth ownership

Remains with the authoritative domain services.

## Supportability and Operator Posture

The run ledger must support:

1. operator inspection by `pack_run_id`,
2. review of runtime and review transition history,
3. visibility into error codes and supportability warnings,
4. linkage to artifacts and evidence bundles,
5. supersession and expiration explanation.

This is where the ledger and observability RFCs meet:

1. observability shows platform posture at scale,
2. the run ledger explains one workflow-pack execution precisely.

## Security and Governance Posture

Required posture:

1. every review-bearing output is durably attributable to one run record,
2. review transitions are actor-attributed and timestamped,
3. supportability warnings remain visible when output is partial or degraded,
4. the ledger does not weaken caller identity, tenant isolation, or artifact governance.

Explicitly rejected patterns:

1. storing only ephemeral in-memory run state for review-bearing output,
2. page-local review booleans with no durable lineage,
3. treating accepted AI output as if `lotus-ai` approved the business workflow itself,
4. overwriting prior run or review history in place.

## Alternatives Considered

### Alternative 1: Keep only async job records and let each app manage review state locally

Rejected because it would:

1. duplicate semantics across applications,
2. create weak supportability,
3. make workflow-pack adoption inconsistent,
4. disconnect runtime truth from product review truth.

### Alternative 2: Store review state only in the calling workflow service

Rejected because it would:

1. make pack-run supportability fragmented,
2. remove the central runtime view needed for operator diagnosis,
3. make it harder to preserve one standard contract family across callers.

### Alternative 3: Collapse runtime state and review state into one field

Rejected because it would:

1. make supportability worse,
2. blur execution truth and workflow review truth,
3. encourage UI ambiguity.

## Cross-Repository Impact

### `lotus-ai`

High impact:

1. durable pack-run ledger schema,
2. runtime and review transition recording,
3. evidence and artifact linkage,
4. operator inspection seams.

### `lotus-gateway`

High impact:

1. standardized product contract shaping for run and review state,
2. allowed-action mapping,
3. provenance-preserving envelopes for Workbench.

### `lotus-workbench`

High impact:

1. shared primitives for rendering run status, review status, provenance, and next actions,
2. removal of page-local AI status semantics over time.

### Domain repositories

Medium impact:

1. explicit integration for review ownership,
2. clear acceptance/rejection semantics where AI-assisted workflows exist.

### `lotus-platform`

Medium impact:

1. validation and governance posture should eventually verify AI provenance and review-state
   integrity for pack-backed product surfaces.

## Implementation Plan

Every completed slice under this RFC should be reviewed before the next slice begins.

That review should confirm:

1. runtime state and review state are still clearly separated,
2. the ledger remains reference-oriented rather than turning into a business workflow database,
3. tests, docs, context, wiki source, and PR evidence still describe the same implementation truth,
4. any repeated lesson should be promoted into durable docs, context, or skill guidance.

### Slice 1: Pack-run ledger contract and persistence

1. define pack-run identity and primary ledger schema,
2. define runtime-state and review-state enumerations,
3. define history and lineage models,
4. define evidence and artifact reference seams.

Deliverables:

1. schema and contract documentation,
2. persistence model,
3. unit and integration tests for state transitions.

### Slice 2: Runtime integration

1. create pack-run records at execution time,
2. persist runtime transitions,
3. preserve error and supportability posture,
4. attach evidence and artifact refs durably.

Deliverables:

1. runtime integration seams,
2. transition tests,
3. supportability and failure-path coverage.

### Slice 3: Review-state integration

1. add explicit review-state transitions,
2. support actor-attributed accept, reject, revise, supersede, and abandon actions,
3. preserve lineage between original and revised or superseded outputs.

Deliverables:

1. review transition APIs or service seams,
2. actor and timestamp history model,
3. tests for review-state progression and supersession.

Current branch status:

1. bounded `lotus-ai` review-action recording is implemented through the workflow-pack run-ledger APIs and service layer,
2. actor attribution, timestamps, invalid-transition rejection, and supersession lineage are now covered by unit and integration tests,
3. Phase-1 advisor-brief run records now emit governed workflow-pack artifact refs through the shared artifact backbone so support and downstream reviewers can inspect bounded output-summary provenance without expanding the ledger contract into raw payload transport,
4. a bounded workflow-pack run operator profile is now exposed for support and operator diagnosis, making review-pending, failure, expiry, supersession, partial-output, evidence, and artifact posture visible without collapsing business workflow authority into lotus-ai,
5. `lotus-gateway` now receives the advisor-brief pack-run identity directly from the explicit workflow-pack execution response, reads the consumer-view and operator-profile surfaces, and emits one compact `workflow_pack_run` contract on the advisor-brief response,
6. `lotus-workbench` now consumes that compact `workflow_pack_run` contract through the existing advisor-brief supportability, review-notes, and audit-provenance path rather than introducing a parallel operator-only UI concept,
7. consequence-bearing meaning, user-entitlement shaping for review actions, and broader non-reference workflow-pack runtime adoption remain future slices.

This branch now also emits bounded ledger-compatible `allowed_review_actions` on run descriptors.
That posture is intentionally narrower than downstream business authorization: it tells consumers
which transitions the ledger can accept from the current run posture, not which actions a product
surface is entitled to execute for a given user or workflow.

This branch also now exposes a bounded workflow-pack run consumer view in `lotus-ai`. That view is
meant to act as a shared contract candidate for composition layers by grouping runtime posture,
review posture, lineage identity, and provenance summary into one response. It is still a
foundation-layer contract: downstream gateway shaping, UI rendering, and business-authority rules
remain separate work.

### Slice 4: Gateway and Workbench contract adoption

1. define gateway-facing contract family for runtime and review state,
2. define allowed-action posture and provenance shape,
3. onboard the first pack-backed surface through the shared model.

Deliverables:

1. gateway response contracts,
2. integration guidance for Workbench,
3. first end-to-end adoption slice, likely `advisor_brief`.

Current branch status:

1. the first end-to-end downstream adoption slice now exists on the advisor-brief path,
2. `lotus-gateway` surfaces a bounded `workflow_pack_run` posture that merges lotus-ai runtime, review, lineage, and supportability facts without taking workflow authority,
3. `lotus-workbench` renders that posture through existing supportability and review-note affordances, and appends workflow-pack run provenance into advisor-brief audit references,
4. `lotus-gateway` now also exposes a bounded advisor-brief review-action seam that derives the pack-run identity from the existing advisor-brief audit trail, records ledger-compatible review transitions through `lotus-ai`, clears stale brief cache, and returns refreshed workflow-pack posture in the same advisor-brief contract,
5. `lotus-workbench` now has a typed client seam for that bounded advisor-brief review-action route, so future UI slices can record ledger-compatible actions without inventing a parallel contract family,
6. broader downstream adoption beyond advisor brief remains future work.

### Slice 5: Operator and supportability integration

1. expose pack-run inspection and supportability views,
2. connect run-level history to observability and artifact references,
3. make supersession, expiry, and partial output visible to operators.

Deliverables:

1. operator service seams or dashboards,
2. support runbook guidance,
3. issue-diagnosis contract coverage.

### Slice 6: Documentation, Agent Context, Wiki Update, and Branch Hygiene

1. update `lotus-ai` docs to reflect the run-ledger and review-state posture once implemented,
2. update repository and platform context artifacts where implementation truth changes,
3. update wiki-source pages for operator and onboarding guidance,
4. update agent skills where implementation changes durable agent workflow guidance, execution
   posture, or delivery standards,
5. keep PR evidence, branch cleanup, and implementation status truthful.

Deliverables:

1. updated docs and wiki-source pages,
2. updated context files where architecture truth changed,
3. updated skill files where needed,
4. PR and branch-hygiene evidence,
5. no stale documentation or skill guidance that implies broader implementation than was actually
   delivered.

## Risks and Mitigations

### Risk: Review-state semantics drift across applications despite the shared model

Mitigation:

1. define one bounded contract family centrally,
2. require gateway shaping rather than page-local inventions,
3. add contract and integration tests for the first adopters.

### Risk: Ledger and workflow authority become blurred

Mitigation:

1. keep workflow-authority owner explicit on every run,
2. document that review acceptance is not business approval,
3. keep domain workflow state outside the pack-run ledger.

### Risk: Too much content is stored in the ledger itself

Mitigation:

1. keep the ledger reference-oriented,
2. rely on governed artifact storage for larger payloads,
3. keep evidence and output seams typed and bounded.

## Open Questions

1. Should `IN_REVIEW` exist in Phase 1, or should the first delivery stay narrower with
   `AWAITING_REVIEW`, `ACCEPTED`, `REJECTED`, and `SUPERSEDED` only?
2. Should every synchronous review-bearing run be persisted immediately in the same ledger, or
   should the first slice prioritize async and explicitly flagged review-bearing runs first?
3. Which first adopter should prove the review-state model end to end after `advisor_brief`:
   `lotus-advise`, `lotus-manage`, or `lotus-report`?

## Acceptance Criteria

1. Lotus has one documented durable pack-run ledger model for workflow-pack executions.
2. Runtime execution state and review state are modeled as separate dimensions with explicit
   contracts.
3. The RFC defines stable lineage between:
   1. run identity,
   2. registry identity,
   3. evidence bundles,
   4. artifacts,
   5. review transitions.
4. Gateway and Workbench have one shared contract vocabulary for pack-run and review-state posture.
5. The implementation plan includes a final slice for documentation, agent context, wiki update,
   skill update where needed, and branch hygiene.
6. No slice under this RFC allows `lotus-ai` to assume workflow authority over approval, consent,
   booking, execution, or domain truth.

## Final Position

Workflow packs will not be enterprise-ready in Lotus until the platform can answer, durably and
truthfully:

1. what ran,
2. what it produced,
3. whether it is complete or partial,
4. what evidence and artifacts support it,
5. whether the output is awaiting review, accepted, rejected, revised, or superseded,
6. who owns the consequence-bearing workflow after the AI output exists.

The correct Lotus answer is:

1. one durable pack-run ledger in `lotus-ai`,
2. one explicit separation between runtime state and review state,
3. one bounded contract family for gateway and Workbench consumption,
4. one clear preservation of downstream workflow authority.

That is the minimum truthful model for AI-assisted workflow adoption in a banking-grade platform.
