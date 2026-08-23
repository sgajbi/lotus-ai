# RFC-0012: Caller Identity and Tenant Isolation Controls

- Status: Implemented
- Date: 2026-03-23
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should introduce first-class caller identity, tenant isolation, and bounded authorization controls so the service can operate as a shared enterprise platform without relying primarily on caller honesty and metadata discipline.

RFC-0003 introduced controlled live-provider rollout and task allowlisting.
RFC-0005 made provider operations state durable with caller- and tenant-aware quota posture.
RFC-0011 defines the dedicated worker and managed-queue deployment model for a more production-grade runtime.

The next high-value shared-platform gap is that caller and tenant identity are now recorded broadly, but still not enforced as a first-class access-control plane.

## Implementation Notes

RFC-0012 is now implemented in five slices:

1. a durable caller-policy registry seam with memory and SQL-backed repositories,
2. enforced data-plane authorization for task execution, retrieval execution, and live-provider execution with typed authorization decisions persisted into audit and execution evidence,
3. enforced control-plane authorization for async control, prompt control, and provider control actions with durable authorization context preserved in control history,
4. dedicated activation-readiness, runbook-readiness, and composed governance surfaces so access-control rollout posture is inspectable and not overstated.
5. server-derived tenant isolation for audit-record reads, with an explicit all-tenant platform capability, indistinguishable cross-scope/missing detail responses, and a separate fail-closed access-evidence ledger for all-tenant inspection.

The current HTTP caller trust source remains the deployment-established `X-Caller-App` boundary.
Cryptographically verified service identity is deliberately separate and remains owned by issue
#149; this RFC implementation does not claim JWT or mTLS caller proof.

## Why This Is Next

The platform already carries identity-like metadata:

1. task, provider, retrieval, and audit contracts carry `caller_app`, optional `requested_by`, and optional `tenant_id`,
2. provider quotas already model caller- and tenant-aware scopes,
3. audit inspection can filter by caller and requester while tenant scope is derived from caller policy,
4. async jobs, retrieval submission, and evaluation submission all preserve caller identity in durable state.

But that identity is still mostly descriptive:

1. it improves traceability,
2. it supports quotas and support workflows,
3. but it does not yet enforce which callers may access which capabilities, prompts, retrieval sources, or control-plane actions.

That is acceptable in a foundation phase, but weak for a shared enterprise service.

## Problem Statement

`lotus-ai` is becoming a real shared platform:

1. provider execution is governed,
2. retrieval is becoming live,
3. evaluation evidence is runtime-backed,
4. async execution is durable,
5. prompt and safety control planes are being defined.

But the service still lacks a real authorization posture around the callers using those capabilities.

Current limitations:

1. `caller_app`, `requested_by`, and `tenant_id` are mostly treated as request metadata rather than enforced identity,
2. capability access is primarily bounded by global rollout and allowlist posture, not by caller-specific authorization,
3. retrieval governance does not yet express caller- or tenant-level source access,
4. control-plane actions rely on recorded operator identity but not yet a bounded authorization model,
5. the service architecture documents auth as part of the API layer target, but the actual control model is still incomplete.

## Goals

1. Introduce a first-class caller-identity and tenant-isolation control model.
2. Enforce bounded capability authorization by caller and, where relevant, tenant.
3. Keep control-plane and data-plane authorization explicit and reviewable.
4. Reuse existing audit, quota, and governance seams rather than inventing parallel identity plumbing.
5. Preserve operator truth about what is authorized, blocked, or partially configured.

## Non-Goals

1. Building a general IAM platform.
2. Replacing upstream authentication systems used by Lotus apps.
3. Fine-grained end-user authorization inside domain data flows.
4. General-purpose RBAC across all future platform components.
5. Mixing domain-business entitlements into `lotus-ai`.

## Current State

The service already has building blocks:

1. caller and tenant metadata are present in public contracts,
2. audit persistence captures them durably,
3. provider quotas and operations already model caller and tenant scopes,
4. provider task allowlisting exists for live-provider rollout,
5. async jobs and evaluation runs preserve caller identity durably.

The missing part is enforcement:

1. no authoritative caller registry or policy exists,
2. no bounded tenant-isolation policy exists,
3. no capability-to-caller authorization model exists,
4. no consistent control-plane authorization model exists for runtime actions.

## Decision

`lotus-ai` will implement explicit caller identity and tenant isolation controls as a shared-platform capability.

The first production-capable access model should:

1. define which caller apps are recognized by the platform,
2. define which capabilities and control-plane surfaces each caller may use,
3. support optional tenant-scoped restrictions where the platform contract already carries tenant metadata,
4. fail conservatively when caller or tenant authorization is invalid or missing for a protected path,
5. expose operator-facing status for configuration, enforcement, and blocked posture.

The first implementation remains intentionally bounded:

1. the caller-app registry is authoritative for platform access decisions,
2. enforcement is capability-scoped rather than a generic RBAC system,
3. tenant restrictions are optional and explicit rather than inferred,
4. unknown callers fail conservatively on protected paths,
5. prompt-body editing and end-user entitlements remain out of scope.

## State Model and Invariants

This RFC establishes the following invariants:

1. identity recorded in audit must match identity used for authorization decisions,
2. unknown callers must not silently inherit broad capability access,
3. tenant-scoped restrictions must be durable and reviewable where enforced,
4. caller authorization posture must not be inferred only from quota configuration,
5. control-plane actions must distinguish who requested an action from who was authorized to perform it,
6. runtime status and governance surfaces must not overstate protection when access control remains documentary or partial.

## Architecture Direction

### Caller Registry and Policy Model

Introduce a bounded caller registry and authorization policy.

Required behavior:

1. recognized caller applications are explicit,
2. each caller can be mapped to allowed capability classes or task ids,
3. caller policy is inspectable and durable,
4. unknown or malformed caller identity fails conservatively,
5. the registry is the only authoritative source for caller capability posture; quota configuration does not imply authorization.

### Tenant Isolation Controls

Add bounded tenant-isolation posture where the current API model already carries tenant identity.

Required behavior:

1. tenant-aware policy remains optional but explicit,
2. protected capabilities can require tenant scope,
3. retrieval, provider, and future prompt control paths can consume that scope consistently,
4. missing or mismatched tenant posture blocks protected execution truthfully,
5. unrestricted callers do not inherit tenant restrictions implicitly.

### Control-Plane Authorization

Operator and administrative actions must have a bounded authorization model.

Required behavior:

1. reset, replay, promotion, rollback, and similar control actions can be restricted by caller/operator role,
2. action history records both actor identity and authorization context,
3. invalid actor or approver combinations fail conservatively,
4. control-plane status surfaces remain reviewable.

### Runtime and Audit Convergence

The same identity model must appear across runtime behavior and audit evidence.

Required behavior:

1. task execution, retrieval, provider, async, and evaluation surfaces all use the same caller identity rules,
2. audit records preserve both request identity and enforcement outcome,
3. operator inspection can explain why a request was allowed or blocked,
4. platform runtime status can summarize whether access control is documentary, partial, or enforced.

The first enforcement wave is explicitly limited to:

1. task execution,
2. retrieval execution and async-backed retrieval submission,
3. live provider execution,
4. async control actions,
5. prompt control actions,
6. provider control actions.

The following remain out of scope for this RFC:

1. generic IAM integration,
2. multi-level role hierarchies,
3. end-user entitlements inside Lotus domain applications,
4. retrofitting domain-level authorization semantics into `lotus-ai`.

## Data and Operational Requirements

1. Caller authorization state must be durable.
2. Authorization decisions must be auditable.
3. Unknown callers must fail safely.
4. Tenant restrictions must be explainable and reviewable.
5. Control-plane authorization must not depend on undocumented conventions.
6. SQL-backed tests must prove authorization behavior and restart survival where relevant.
7. Runbooks must define onboarding, revocation, incident review, and emergency override posture.

## Delivery Slices

### Slice 1: Caller Registry and Authorization Seam

Outcome:

1. explicit caller registry and policy contracts exist,
2. service seams can perform caller authorization decisions,
3. public behavior remains mostly descriptive at first.

Acceptance gate:

1. policy model is explicit and durable,
2. unit tests cover recognized and unknown callers,
3. runtime status remains truthful about enforcement level,
4. no hidden auth behavior is introduced.

### Slice 2: Capability Authorization for Data-Plane Paths

Outcome:

1. task, retrieval, and provider entry points can enforce caller authorization,
2. blocked behavior is explicit and reviewable,
3. tenant scope can be applied to protected paths.

Acceptance gate:

1. unauthorized callers are rejected conservatively,
2. authorized callers retain bounded access,
3. meaningful integration tests cover protected and blocked paths,
4. audit evidence records authorization outcome truthfully.

### Slice 3: Control-Plane Authorization and Action History Upgrade

Outcome:

1. async, provider, prompt, and future control actions enforce bounded actor authorization,
2. action history includes authorization context,
3. operator identity is no longer only documentary.

Acceptance gate:

1. unauthorized control actions fail conservatively,
2. authorized actions remain auditable,
3. approval and actor semantics are explicit,
4. integration tests cover control-plane paths.

### Slice 4: Runtime, Governance, and Runbook Convergence

Outcome:

1. access-control posture appears explicitly in runtime and governance summaries,
2. runbooks document onboarding, revocation, override, and incident procedures,
3. the service reflects shared-platform access truth honestly.

Acceptance gate:

1. runtime and governance surfaces describe actual enforcement posture,
2. runbooks match implementation reality,
3. stale or documentary access-control posture is not misrepresented as enforced,
4. the platform is materially closer to enterprise-grade shared-service access control.

## Risks

1. over-broad authorization rules could recreate domain authorization in the wrong layer,
2. under-scoped rules could leave the platform too open while appearing governed,
3. inconsistent caller identity handling across subsystems could weaken audit trust,
4. tenant controls could add complexity if not kept bounded to real platform needs.

## Alternatives Considered

### Alternative 1: Leave Authorization Entirely to Upstream Gateways

Rejected.

Reason:

1. upstream auth is necessary but not sufficient for a shared platform with internal rollout and capability boundaries,
2. `lotus-ai` already owns task, provider, retrieval, and control-plane semantics that need their own bounded authorization layer.

### Alternative 2: Do Only Quota and Audit, No Authorization Layer

Rejected.

Reason:

1. quota and audit improve visibility, not permissioning,
2. a shared enterprise platform needs explicit allow/deny posture, not just retrospective evidence.

### Alternative 3: Build Full RBAC Before Any Enforcement

Rejected.

Reason:

1. it would overbuild beyond the bounded needs of the current platform,
2. a narrower caller- and tenant-aware authorization model is the more pragmatic next step.

## Acceptance Criteria

This RFC is complete when:

1. caller identity and tenant scope are part of an explicit authorization model,
2. bounded data-plane and control-plane paths can enforce that model,
3. audit and runtime surfaces reflect actual authorization decisions,
4. runbooks and governance surfaces describe enforcement truthfully,
5. the platform is materially closer to enterprise-grade shared-service isolation and access control.

## Approval Requested

Approve this RFC if the team agrees that:

1. caller identity and tenant isolation are the next high-value shared-platform gap after the current runtime/control-plane sequence,
2. `lotus-ai` should enforce bounded capability authorization instead of relying primarily on caller honesty and metadata discipline,
3. control-plane actions should use the same explicit identity model,
4. delivery should proceed in the slices defined above.
