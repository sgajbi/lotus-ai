# RFC-0032: Governed Workflow-Pack Registry and Activation Posture

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
  - maintainers of any repository that will own workflow-pack definitions under this model
- Related:
  - `RFC-0021-domain-ai-capability-packs-and-product-maturity.md`
  - `RFC-0023-multi-app-adoption-and-capability-rollout-governance.md`
  - `RFC-0031-governed-agent-workflow-packs-and-bounded-ai-runtime.md`
  - `../../../lotus-platform/rfcs/RFC-0069-lotus-ai-shared-ai-platform-service.md`
  - `../../../lotus-platform/rfcs/RFC-0070-gold-standard-product-experience-foundation-and-ownership-model.md`
  - `../../../lotus-platform/rfcs/RFC-0072-platform-wide-multi-lane-ci-validation-and-release-governance.md`
  - `../../../lotus-platform/rfcs/RFC-0080-lotus-agent-runtime-demo-skill-pack-and-guidance-hardening.md`
  - `../../../lotus-platform/rfcs/RFC-0081-slice-9-ai-surface-governance-and-assistive-workflow-controls-evidence.md`

## Summary

`RFC-0031` establishes that Lotus should adopt workflow packs as the bounded, runtime-bearing
evolution of the existing capability-pack model.

That creates a new platform problem:

1. where those packs are physically defined,
2. how they become known to the runtime,
3. how Lotus decides which callers may invoke them,
4. how rollout posture is controlled across tenant, channel, workflow, and environment boundaries,
5. how a pack is paused, superseded, or retired without losing auditability.

This RFC defines the registry and activation layer for workflow packs.

The decision is:

1. workflow-pack definitions remain code-owned in the repository that owns their business meaning,
2. `lotus-ai` owns the runtime registry and activation posture for those packs,
3. execution is allowed only for registered workflow-pack versions with explicit activation state,
4. activation posture is policy-aware rather than a single global on/off switch,
5. rollout, pause, deprecation, and retirement remain inspectable and auditable.

The goal is to give Lotus a banking-grade control plane for workflow-pack availability without
collapsing business ownership into the runtime service.

## Implementation Status

This RFC is now partially implemented in `lotus-ai`.

Completed implementation slices on the current branch:

1. registry contracts, catalog-backed services, and read-only registration APIs,
2. explicit eligibility evaluation with bounded denial reasons,
3. bounded control history plus pause, resume, deprecate, and retire actions,
4. migration-backed durable workflow-pack registration, activation state, and control-history
   storage with memory and SQL store modes,
5. owner-grounded onboarding for the Phase-1 `advisor_brief.pack` family,
6. caller-policy-backed workflow-pack control authorization plus durable control-event authorization
   evidence for bounded operator actions,
7. readiness-aware degradation for registry-backed workflow-pack routes so unmigrated SQL-backed
   registry posture returns explicit service-unavailable behavior instead of surfacing raw store failures,
8. documentation, repository context, wiki-source, and branch-hygiene updates,
9. green canonical live proof for the registered `advisor_brief.pack` family through the governed
   `lotus-workbench` -> `lotus-gateway` -> `lotus-ai` path, showing that the registry-backed
   reference family now executes and reviews truthfully in the real front-office runtime,
10. owner-grounded onboarding and explicit execution binding for the domain-owned
    `workspace_rationale.pack` family used by the `lotus-advise` workspace rationale seam, and
11. owner-grounded onboarding and explicit execution binding for the domain-owned
    `twr_inspection_support_brief.pack` family used by the `lotus-performance` TWR inspection
    supportability seam.

Still pending before this RFC should be considered fully implemented:

1. broader operator authorization beyond the current bounded caller-policy control-plane posture,
2. broader rollout posture beyond the current pilot and discovery reference family,
3. broader downstream proof and operator rollout posture beyond the current Phase-1
   `advisor_brief.pack`, `workspace_rationale.pack`, and
   `twr_inspection_support_brief.pack` families,
4. convergence with the durable run-ledger and review-state model proposed in `RFC-0033`.

## Requirement Traceability And Evidence

The implemented portions of this RFC map to concrete branch evidence as follows.

1. Registry shape and owner-grounded metadata:
   `src/app/contracts/workflow_packs.py`, `src/app/services/workflow_pack_registry.py`,
   `tests/unit/test_workflow_pack_registry.py`,
   `tests/integration/test_workflow_pack_registry_api_contract.py`
2. Registration catalog and detail inspection surfaces:
   `src/app/routers/workflow_packs.py`, `src/app/main.py`,
   `tests/integration/test_health.py`, `tests/unit/test_openapi_contract.py`
3. Explicit eligibility evaluation over caller, environment, tenant, and workflow surface:
   `src/app/services/workflow_pack_activation.py`,
   `tests/unit/test_workflow_pack_activation.py`,
   `tests/integration/test_workflow_pack_activation_api_contract.py`
4. Bounded operator pause, resume, deprecate, and retire controls:
   `src/app/services/workflow_pack_control.py`,
   `tests/unit/test_workflow_pack_control.py`,
   `tests/integration/test_workflow_pack_control_api_contract.py`
5. Durable workflow-pack registration, activation state, and control history through the
   migration-backed registry store:
   `src/app/services/workflow_pack_registry_store.py`,
   `src/app/repositories/sqlalchemy_workflow_pack_registry_repository.py`,
   `alembic/versions/0029_add_workflow_pack_registry_state_tables.py`,
   `tests/unit/test_workflow_pack_registry_store.py`,
   `tests/integration/test_runtime_modes.py`
6. Phase-1 owner-artifact onboarding and downstream truth preservation for `advisor_brief.pack`:
   `src/app/services/workflow_pack_registry.py`,
   `docs/guides/workflow-pack-owner-onboarding.md`,
   `docs/guides/integration-guide.md`, `docs/runbooks/service-operations.md`,
   `wiki/Integrations.md`, `wiki/Operations-Runbook.md`, `wiki/Platform-Surfaces.md`
7. readiness-aware API degradation for registry, control, eligibility, and execute surfaces when
   the SQL-backed registry store is configured but not yet migration-ready:
   `src/app/services/workflow_pack_registry.py`,
   `src/app/routers/workflow_packs.py`,
   `tests/integration/test_workflow_pack_registry_api_contract.py`,
   `tests/integration/test_workflow_pack_control_api_contract.py`,
   `tests/integration/test_workflow_pack_activation_api_contract.py`,
   `tests/integration/test_workflow_pack_run_api_contract.py`,
   `tests/unit/test_openapi_contract.py`
8. Caller-policy-backed workflow-pack operator control authorization and durable authorization
   evidence on workflow-pack control events:
   `src/app/services/access_control_authorization.py`,
   `src/app/services/workflow_pack_control.py`,
   `src/app/contracts/workflow_packs.py`,
   `src/app/repositories/sqlalchemy_workflow_pack_registry_repository.py`,
   `alembic/versions/0030_add_workflow_pack_control_event_authorization_payload.py`,
   `tests/unit/test_access_control_authorization.py`,
   `tests/unit/test_workflow_pack_control.py`,
   `tests/integration/test_workflow_pack_control_api_contract.py`

Open gaps that remain consistent with this RFC's still-pending scope:

1. operator authorization is now caller-policy-backed for bounded workflow-pack control actions but
   is not yet a broader enterprise entitlement model,
2. broader activation rollout posture beyond the current Phase-1 `advisor_brief.pack`,
   `workspace_rationale.pack`, and `twr_inspection_support_brief.pack` families is not yet
   onboarded,
3. the current registry and activation evidence now proves reuse beyond the reference path across
   three Phase-1 families, but RFC-0032 still should not be declared fully complete until operator
   rollout and downstream adoption are broader than the current bounded Phase-1 slice.

## Why This RFC Exists

Lotus now has two important truths that need to be reconciled.

The first truth:

1. reusable AI-assisted workflows should be packaged as governed workflow packs,
2. those packs must stay close to the repository that owns their business meaning,
3. downstream business authority must remain in the owning services and product surfaces.

The second truth:

1. runtime execution cannot safely discover behavior from arbitrary repository state at request time,
2. activation posture cannot live only in static code if Lotus wants disciplined rollout and rollback,
3. operator and support teams need one inspectable answer to "what is currently allowed to run?"

Without a dedicated registry and activation RFC, Lotus will drift into one of three bad outcomes:

1. **runtime-centralized ownership**
   `lotus-ai` becomes the editorial owner of every workflow-pack definition and steals domain-local
   ownership from the services that should own business meaning.
2. **code-only rollout**
   the only way to enable or disable a pack becomes a code deployment, which is too blunt for
   enterprise rollout, emergency pause, and environment-specific control.
3. **fragmented local allowlists**
   each caller or downstream application grows its own activation rules, causing inconsistent
   platform behavior and weak supportability.

This RFC exists to define the middle path:

1. canonical definition stays in the owning repo,
2. runtime registration lives in `lotus-ai`,
3. activation posture is explicit, governed, and inspectable,
4. callers remain bounded by centrally evaluated policy.

## Problem Statement

The workflow-pack direction in `RFC-0031` is correct, but the platform still lacks a precise answer
to a set of operationally important questions.

Today Lotus cannot answer these questions through one standard control surface:

1. which workflow-pack ids exist,
2. which repository owns each pack,
3. which version is currently eligible for execution,
4. which applications, callers, tenants, or workflow surfaces may invoke it,
5. which environments are allowed to activate it,
6. whether the pack is:
   - draft only,
   - registered but dark,
   - pilot-enabled,
   - active,
   - paused,
   - deprecated,
   - retired,
7. which replacement pack supersedes a deprecated one,
8. whether a run was allowed because of durable policy or because a caller made a local exception.

That gap is not merely administrative.

It creates real platform risk:

1. business-owned packs may become runtime-owned by accident,
2. experimental packs may leak into broader usage,
3. limited pilot posture may be impossible to distinguish from full production approval,
4. different applications may behave differently for the same pack id,
5. incident response may not have a clean kill switch,
6. audit review may not be able to reconstruct why a run was allowed on a given date.

Lotus needs a formal registry and activation model before workflow packs can scale safely.

## Goals

1. Define the canonical ownership split between workflow-pack definition and runtime registration.
2. Introduce a formal registry model for workflow-pack metadata in `lotus-ai`.
3. Define a policy-based activation posture for pack versions.
4. Standardize rollout, pause, rollback, deprecation, and retirement semantics.
5. Preserve auditability for why a specific workflow-pack run was allowed.
6. Support environment-aware and caller-aware activation without turning the runtime into an
   uncontrolled policy maze.
7. Keep the model compatible with existing capability-pack and multi-app rollout governance.

## Non-Goals

1. Defining the full execution runtime for workflow packs.
2. Defining review-state UX or user-facing acceptance/rejection semantics.
3. Turning `lotus-ai` into the business owner of advisory, management, reporting, or analytics
   workflows.
4. Allowing end-user or operator ad hoc editing of workflow-pack logic in production.
5. Replacing platform-wide production-approval and CI governance.
6. Solving every activation decision with arbitrary dynamic rules at runtime.
7. Introducing a plugin ecosystem or community-installed workflow packs.

## Scope Boundary

This RFC is intentionally narrower than the broader workflow-pack runtime RFC.

It defines:

1. registry shape,
2. ownership split,
3. activation posture,
4. eligibility evaluation,
5. registry-state transitions,
6. auditability of activation decisions.

It does not define:

1. pack-run lifecycle persistence,
2. review-state lifecycle for generated outputs,
3. Workbench UX contracts for review and feedback,
4. artifact storage shape beyond the registry references needed for truthful run audit.

## Decision

Lotus will introduce a governed workflow-pack registry and activation control layer with the
following rules.

### Rule 1: Canonical definition lives in the owning repository

Each workflow pack has one owning repository and one owning service boundary.

That repository owns:

1. pack identifier and version,
2. pack contract and schemas,
3. pack-specific builder logic,
4. business-local design reasoning,
5. required source and truth-owner declarations,
6. degraded and refusal posture.

### Rule 2: Runtime registration lives in `lotus-ai`

`lotus-ai` owns the runtime registration record for each pack version.

That record is the operational answer to:

1. whether a version is known to the runtime,
2. whether it is eligible for execution,
3. what callers and environments may invoke it,
4. what rollout stage it is in,
5. whether it is paused, deprecated, or retired.

### Rule 3: Only registered versions may execute

Workflow-pack execution must not resolve directly from arbitrary repository state at request time.

The runtime may execute only versions that are:

1. declared by the owning repository,
2. registered into `lotus-ai`,
3. evaluated against current activation posture,
4. not blocked by pause, retirement, or environment policy.

### Rule 4: Activation posture is explicit and policy-based

Activation is not a single boolean.

Every workflow-pack version must have explicit activation posture across at least:

1. environment,
2. caller application,
3. caller identity class,
4. tenant or tenant group where relevant,
5. workflow surface or use-context where relevant,
6. rollout state,
7. emergency pause state.

### Rule 5: Registration and activation remain auditable

The platform must be able to explain:

1. why a pack version was allowed,
2. why it was denied,
3. what registration record was in force,
4. what activation policy dimensions were applied,
5. when the record changed and who changed it.

## Relationship to Existing RFCs

### Relationship to RFC-0021

`RFC-0021` introduced capability packs as the product-maturity layer above generic task families.

This RFC does not replace that model.

It refines the runtime-control posture for the subset of packs that have evolved into
workflow-bearing capabilities.

In practical terms:

1. capability-pack identity remains the conceptual product layer,
2. workflow-pack registration becomes the runtime activation layer,
3. `lotus-ai` now needs a stronger operational catalog than the simple capability-pack listing used
   for earlier maturity phases.

### Relationship to RFC-0023

`RFC-0023` introduced multi-app rollout governance.

This RFC is the runtime-facing counterpart.

`RFC-0023` describes the application and adoption posture.

This RFC describes the registry and activation mechanism that makes that posture enforceable at
runtime.

### Relationship to RFC-0031

`RFC-0031` states that workflow packs are the runtime-bearing, orchestration-capable subclass of the
capability-pack model.

This RFC defines the first required control-plane layer under that decision:

1. registry,
2. activation,
3. operational state transitions.

## Principles

### 1. Runtime control must not erase domain ownership

The runtime needs operational control.

It does not need editorial ownership of business workflow semantics.

### 2. Registration is a control-plane record, not a second source of truth

The registry should carry the metadata necessary to execute and govern packs safely.

It must not become a second place where business logic is rewritten.

### 3. Activation should be narrow by default

New workflow-pack versions should enter the runtime in a posture that is:

1. explicit,
2. limited,
3. inspectable,
4. easy to pause.

### 4. Policy dimensions should be finite and governed

Lotus needs policy-aware activation, but not an arbitrary rules engine for every edge case.

The allowed activation dimensions should remain bounded, documented, and testable.

### 5. History must remain inspectable

The system should preserve historical registry and activation truth so audit and support teams can
reconstruct what was active at a given time.

## Workflow-Pack Identity Model

Every workflow pack must have a stable identity shape.

Minimum required fields:

1. `pack_id`
2. `pack_family`
3. `version`
4. `owner_repository`
5. `owner_service`
6. `truth_owner_services`
7. `primary_use_case`
8. `workflow_authority_owner`
9. `default_execution_mode`
10. `definition_ref`
11. `compatibility_contract_version`

### Identity rules

1. `pack_id` must be stable across revisions of the same named workflow family.
2. `version` identifies the executable versioned shape, not just documentation revision.
3. `owner_repository` names the repository that owns the pack definition in code.
4. `workflow_authority_owner` must identify the service or composition layer that owns downstream
   consequence-bearing workflow state.
5. `truth_owner_services` must enumerate the authoritative services the pack is allowed to rely on.

## Registry Model

The runtime registry in `lotus-ai` should store one registration record per pack version.

### Registration record

Minimum required fields:

1. `pack_id`
2. `version`
3. `registration_status`
4. `activation_state`
5. `owner_repository`
6. `owner_service`
7. `registered_definition_digest`
8. `definition_ref`
9. `supported_callers`
10. `supported_environments`
11. `tenant_scope`
12. `surface_scope`
13. `default_rollout_stage`
14. `pause_state`
15. `supersedes`
16. `superseded_by`
17. `registered_at`
18. `registered_by`
19. `last_activated_at`
20. `last_changed_at`

### What the registry is allowed to store

The registry may store:

1. normalized metadata required for execution eligibility,
2. digests and references to the owning-repo definition,
3. rollout and activation posture,
4. caller and environment eligibility,
5. version relationships such as supersession and retirement,
6. governance metadata such as change actor and change timestamp.

### What the registry must not store as editable business truth

The registry must not become the editable home of:

1. full business logic,
2. prompt bodies as an uncontrolled fork of repo-owned definitions,
3. domain-local interpretation rules that belong in the owning repository,
4. caller-local hidden exceptions not represented in the shared policy model.

## Registration Status Model

Registration status answers whether the runtime knows about a pack version as a control-plane
artifact.

Recommended statuses:

1. `DISCOVERED`
2. `REGISTERED`
3. `VALIDATION_FAILED`
4. `WITHDRAWN`
5. `RETIRED`

### Meaning

1. `DISCOVERED`
   the owning repository has declared a candidate pack version, but runtime registration is not yet
   finalized.
2. `REGISTERED`
   the pack version is valid in the registry and may be evaluated for activation.
3. `VALIDATION_FAILED`
   the candidate failed schema, ownership, or policy validation and is not eligible for execution.
4. `WITHDRAWN`
   the owning repo or platform has intentionally pulled the registration back before retirement.
5. `RETIRED`
   the version is preserved for history but cannot be reactivated for normal execution.

## Activation State Model

Activation state answers whether a registered pack version is operationally allowed to execute.

Recommended states:

1. `DARK`
2. `PILOT`
3. `LIMITED_ACTIVE`
4. `ACTIVE`
5. `PAUSED`
6. `DEPRECATED`
7. `RETIRED`

### Meaning

1. `DARK`
   registered, but not allowed for normal execution.
2. `PILOT`
   allowed only for explicitly scoped limited rollout.
3. `LIMITED_ACTIVE`
   active for a bounded subset of callers or tenants under monitored rollout.
4. `ACTIVE`
   approved for the declared eligible scope.
5. `PAUSED`
   execution blocked without deleting registration history.
6. `DEPRECATED`
   still inspectable and potentially callable only where specifically permitted, but replaced for
   normal forward use.
7. `RETIRED`
   no longer executable.

### Important distinction

`registration_status` and `activation_state` are not the same thing.

Examples:

1. a version can be `REGISTERED` but `DARK`,
2. a version can be `REGISTERED` and `PAUSED`,
3. a version can be `RETIRED` in both dimensions,
4. a version with `VALIDATION_FAILED` must never evaluate as runnable regardless of activation
   settings.

## Activation Policy Dimensions

The runtime should evaluate a finite set of policy dimensions for every workflow-pack invocation.

### 1. Environment scope

Examples:

1. local development,
2. shared development,
3. QA,
4. UAT,
5. production.

Rule:

1. no pack may inherit production activation merely because it is active elsewhere.

### 2. Caller application scope

Examples:

1. `lotus-gateway`,
2. `lotus-advise`,
3. `lotus-manage`,
4. `lotus-report`.

Rule:

1. supported callers must be explicit in the registration record.

### 3. Caller identity class

Examples:

1. internal service caller,
2. banker-facing product caller,
3. operator/support caller,
4. platform automation caller.

Rule:

1. identity class should remain bounded and mapped to existing caller-identity controls.

### 4. Tenant or tenant-group scope

This dimension is required only where the pack is intended for tenant-scoped rollout.

Rule:

1. tenant scoping must be explicit and deny-by-default when present.

### 5. Workflow surface scope

Examples:

1. advisor brief panel,
2. proposal-review screen,
3. reporting QA console,
4. operator incident workspace.

Rule:

1. the platform should support named surface scoping where a pack is not meant for all caller
   surfaces within the same application.

### 6. Emergency pause override

Rule:

1. emergency pause must short-circuit normal eligibility evaluation.

## Eligibility Evaluation Model

At invocation time, the runtime should evaluate:

1. whether the requested pack version exists,
2. whether its registration status is executable,
3. whether activation state allows execution,
4. whether the caller app is permitted,
5. whether the environment is permitted,
6. whether caller identity class is permitted,
7. whether tenant scope is permitted where applicable,
8. whether workflow surface is permitted where applicable,
9. whether pause or retirement blocks execution.

### Result categories

The evaluation result should be one of:

1. `ALLOWED`
2. `DENIED_NOT_REGISTERED`
3. `DENIED_NOT_ACTIVE`
4. `DENIED_CALLER_SCOPE`
5. `DENIED_ENVIRONMENT_SCOPE`
6. `DENIED_TENANT_SCOPE`
7. `DENIED_SURFACE_SCOPE`
8. `DENIED_PAUSED`
9. `DENIED_RETIRED`
10. `DENIED_VALIDATION_STATUS`

This matters because supportability is stronger when the denial reason is explicit.

## Ownership Model

Each workflow pack must have explicit ownership split across four concerns.

### 1. Definition ownership

Owned by the repository that defines the pack in code.

### 2. Runtime ownership

Owned by `lotus-ai`, which is responsible for:

1. registration mechanics,
2. activation evaluation,
3. auditability,
4. operator control surfaces.

### 3. Caller/composition ownership

Owned by the service that assembles facts and invokes the pack.

For cross-service product flows, this will often be `lotus-gateway`.

### 4. Workflow authority ownership

Owned by the service or product surface responsible for consequence-bearing workflow state.

This must never be silently delegated to `lotus-ai`.

## Registry Change Management

The platform needs clear semantics for how registration records change over time.

### Allowed change actions

1. `REGISTER_VERSION`
2. `ACTIVATE_SCOPE`
3. `NARROW_SCOPE`
4. `PAUSE`
5. `RESUME`
6. `DEPRECATE`
7. `SUPERSEDE`
8. `RETIRE`
9. `WITHDRAW`

### Requirements

1. every change action must be timestamped,
2. every change action must record actor identity,
3. every change action must preserve previous state for audit reconstruction,
4. emergency actions such as `PAUSE` must be fast and reversible without editing the pack definition
   itself.

## Registration Workflow

The intended path is:

1. owning repository defines or updates a workflow-pack version in code,
2. validation checks confirm schema, ownership, and required metadata,
3. the pack version is registered into `lotus-ai`,
4. the registration initially lands in a non-broad activation posture such as `DARK` or `PILOT`,
5. rollout posture is widened only through explicit activation changes,
6. deprecated versions remain inspectable until retired.

### Why this workflow matters

It separates three concerns that should not be conflated:

1. definition authorship,
2. runtime registration,
3. rollout activation.

## Versioning and Supersession

Workflow-pack versioning must support clean forward evolution.

### Required behavior

1. a pack family may have multiple known versions in the registry,
2. only explicitly activated versions are eligible to run,
3. deprecation must point to the replacement version where applicable,
4. retirement must not delete historical references,
5. callers must not resolve implicitly to a newer version unless the runtime contract explicitly
   defines default-version behavior.

### Default-version posture

For Phase 1, the safest posture is:

1. callers request a stable named version explicitly,
2. runtime default-resolution remains conservative and inspectable,
3. auto-upgrade between versions is not assumed.

## Audit and Evidence Requirements

Every workflow-pack run should be able to point back to:

1. the pack id and version,
2. the registration record in force,
3. the evaluated activation dimensions,
4. the allow or deny result,
5. the actor and change history relevant to that posture.

This RFC does not define the full pack-run ledger.

That is handled by the next RFC track.

But the registry must expose enough immutable reference data for that run ledger to remain
truthful.

## Security and Governance Posture

This registry model supports a stricter security posture than ad hoc caller allowlists.

### Required posture

1. deny execution for unknown versions,
2. deny execution for unsupported caller scope,
3. deny execution when the pack is paused or retired,
4. make environment eligibility explicit,
5. record every activation change as auditable control-plane state,
6. avoid hidden operator-only overrides that bypass the registry record.

### Explicitly rejected patterns

Lotus should reject:

1. runtime execution from unregistered repo state,
2. user-installed or dynamically downloaded workflow packs,
3. local caller-managed activation exceptions that are not reflected in central control-plane truth,
4. mutable production editing of workflow-pack behavior through the registry.

## Alternatives Considered

### Alternative 1: Store all workflow-pack definitions centrally in `lotus-ai`

Rejected because it would:

1. make `lotus-ai` the editorial owner of business-local workflow semantics,
2. weaken ownership boundaries between runtime governance and domain meaning,
3. increase the risk that domain repositories stop treating pack design as part of their own code
   contract.

### Alternative 2: Keep definitions in owning repositories but allow direct runtime discovery

Rejected because it would:

1. make execution posture dependent on repository deployment state rather than explicit activation
   control,
2. weaken emergency pause and rollback discipline,
3. make audit reconstruction harder because execution would not be tied to one durable registry
   record.

### Alternative 3: Let each caller maintain its own pack activation allowlist

Rejected because it would:

1. fragment rollout truth,
2. create inconsistent behavior across Lotus applications,
3. make incident response and supportability materially weaker,
4. increase the chance of caller-local exceptions silently bypassing shared governance.

## Cross-Repository Impact

### `lotus-ai`

High impact:

1. new registry model,
2. activation evaluation logic,
3. control-plane APIs or service seams,
4. audit change record support.

### `lotus-gateway`

Medium to high impact:

1. caller identity and workflow-surface declaration must be clean enough to support activation
   evaluation,
2. gateway-owned flows must request registered pack ids and versions explicitly,
3. product composition logic must respect activation denial semantics.

### `lotus-workbench`

Medium impact:

1. product surfaces may need stable surface identifiers so gateway and runtime can apply surface
   scope cleanly,
2. UI should be ready to render activation-based unavailability honestly.

### Domain repositories

Medium impact for repositories that own pack definitions:

1. they must define ownership, truth-owner, and schema metadata cleanly,
2. they must adopt the registration path instead of assuming direct runtime discovery.

### `lotus-platform`

Medium impact:

1. platform standards and validation posture should eventually include registry and activation truth
   checks for workflow-pack-enabled surfaces.

## Implementation Plan

Every completed slice under this RFC should be reviewed before the next slice begins.

That review should verify:

1. the slice still keeps workflow logic out of the registry and control plane,
2. the implementation remains simpler and more maintainable than the prior state,
3. tests, docs, context, wiki source, and PR evidence still match the actual delivered posture,
4. any repeated lesson is promoted into durable guidance instead of remaining trapped in chat or
   branch-only memory.

### Slice 1: Registration contract

1. define workflow-pack registration schema,
2. define required ownership and identity fields,
3. define status and activation enumerations,
4. define validation rules for registration ingestion.

Deliverables:

1. registry contract documentation,
2. schema validation tests,
3. initial registration APIs or internal service seams.

### Slice 2: Activation evaluation

1. implement runtime eligibility evaluation,
2. enforce caller, environment, and state checks,
3. expose clear denial reasons,
4. add audit-friendly evaluation metadata.

Deliverables:

1. activation evaluator,
2. eligibility tests,
3. denial-reason contract coverage.

### Slice 3: Change management and operator controls

1. implement activation transitions such as pause, resume, deprecate, retire,
2. persist change history,
3. expose operator-facing status surfaces.

Deliverables:

1. change-action service seams,
2. audit history model,
3. operator documentation.

### Slice 4: Owning-repo onboarding

1. onboard the first workflow-pack family through the new registration path,
2. validate that owning-repo definition and runtime registry stay cleanly separated,
3. prove the posture with the Phase-1 `advisor_brief` pack family.

Deliverables:

1. first real registration path,
2. end-to-end tests across registration and invocation eligibility,
3. documentation for future pack owners.

### Slice 5: Documentation, Agent Context, Wiki Update, and Branch Hygiene

1. update `lotus-ai` documentation so the repository-local architecture truth reflects the registry
   and activation model once implementation starts,
2. update agent context and repository context artifacts when the runtime-control posture becomes
   implemented truth rather than RFC intent,
3. update the `lotus-ai` wiki source where workflow-pack ownership, registration, and activation
   posture need operator-facing explanation,
4. update shared skills where implementation changes durable agent workflow guidance, RFC review
   standards, or delivery posture,
5. ensure feature-branch work, PR description, and branch cleanup remain truthful and aligned with
   actual implementation evidence.

Deliverables:

1. updated repository docs and wiki-source pages,
2. updated context artifacts where architecture truth changed,
3. updated skill files where needed,
4. PR and branch-hygiene checklist evidence,
5. no stale branch, skill, or RFC wording that implies implementation beyond what was actually
   delivered.

## Risks and Mitigations

### Risk: Registry metadata becomes a shadow copy of business logic

Mitigation:

1. keep the registry schema deliberately narrow,
2. store references and digests rather than editable business semantics,
3. require pack-definition changes to remain code-reviewed in the owning repository.

### Risk: Activation policy grows into an unbounded rule engine

Mitigation:

1. restrict Phase-1 policy dimensions to a finite documented set,
2. reject ad hoc caller-local exceptions,
3. require schema and contract tests for every newly introduced activation dimension.

### Risk: Operational teams cannot distinguish registration failure from activation denial

Mitigation:

1. keep `registration_status` and `activation_state` separate,
2. standardize explicit denial categories,
3. make those categories visible in control-plane and support surfaces.

## Open Questions

These questions remain intentionally open, but they do not block the core registry decision.

1. Should Phase 1 support tenant-group activation immediately, or start with environment and caller
   scope only?
2. Should default-version resolution exist at all in the first production posture, or should every
   caller request an explicit version?
3. Which operator surfaces should own activation change workflows first: `lotus-ai` internal
   control-plane surfaces, `lotus-platform` governance tooling, or both?

## Acceptance Criteria

1. Lotus has one documented workflow-pack registry model that separates owning-repository definition
   from `lotus-ai` runtime registration.
2. The registry model defines explicit status, activation, and change-management semantics that can
   be implemented without caller-local ambiguity.
3. The RFC defines a finite set of activation policy dimensions and explicit denial outcomes.
4. The RFC preserves clear ownership boundaries between:
   1. pack definition ownership,
   2. runtime ownership,
   3. caller/composition ownership,
   4. workflow-authority ownership.
5. The implementation plan includes documentation, context, wiki, and branch-hygiene closure rather
   than treating them as optional follow-up work, with skill updates where durable agent guidance
   changed.
6. No slice under this RFC allows runtime execution of unregistered workflow-pack definitions or
   mutable production editing of pack logic through the registry.

## Final Position

Workflow packs cannot scale safely in Lotus without a clean control-plane answer to:

1. what exists,
2. who owns it,
3. what is registered,
4. what is active,
5. who is allowed to invoke it,
6. how it is paused or retired.

The correct Lotus answer is not runtime-centralized authorship and not caller-local sprawl.

It is:

1. code-owned pack definitions in the repository that owns business meaning,
2. runtime registration and activation control in `lotus-ai`,
3. explicit, auditable policy dimensions for activation,
4. conservative rollout posture with fast pause and clear retirement semantics.

That gives Lotus the control-plane discipline needed for enterprise AI workflow adoption without
weakening domain ownership boundaries.
