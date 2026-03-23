# RFC-0016: First Production Use-Case Onboarding

- Status: Draft
- Date: 2026-03-23
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should onboard its first real Lotus application use case through a governed, production-oriented integration sequence, using the platform capabilities and control planes established by the prior RFCs.

The platform has now built a substantial shared foundation:

1. retrieval and provider runtime control planes,
2. runtime-backed evaluation and approval gates,
3. durable async execution,
4. prompt, safety, identity, observability, artifact, and deployment evolution paths.

The next high-value milestone is to prove that this platform can safely deliver one real business-adjacent use case end to end.

## Why This Is Next

The architecture and integration guidance have consistently pointed toward one principle:

1. `lotus-ai` should be a shared platform,
2. but platform abstractions should be validated by real Lotus application usage rather than only internal architecture work.

The current docs already identify the preferred first integration path:

1. [README.md](C:/Users/Sandeep/projects/lotus-ai/README.md#L1) says cross-app adoption should start with one Lotus app integration,
2. [integration-guide.md](C:/Users/Sandeep/projects/lotus-ai/docs/guides/integration-guide.md#L1) highlights `lotus-manage` explanation and support-oriented use cases,
3. [phased-roadmap.md](C:/Users/Sandeep/projects/lotus-ai/docs/architecture/phased-roadmap.md#L1) identifies `lotus-manage` explanation of rebalance outcomes as the preferred first integration.

Without a real first-use-case RFC:

1. platform work can continue to drift toward abstract completeness,
2. integration risks stay unproven,
3. adoption readiness remains theoretical,
4. the service does not yet validate its own “shared platform” claim in production-like conditions.

## Problem Statement

`lotus-ai` is increasingly capable, but still lacks proof through one governed downstream use case.

Current limitations:

1. task, retrieval, provider, audit, and evaluation flows exist independently,
2. many rollout and governance surfaces are strong,
3. but there is no RFC-governed first-use-case onboarding path tying those pieces together for a real Lotus application,
4. no downstream application has yet become the proving ground for the platform’s operational, safety, and supportability promises.

This means:

1. platform maturity is still being judged mostly from internal architecture progress,
2. the highest-risk integration assumptions remain untested,
3. the platform does not yet have a concrete adoption template for other Lotus apps.

## Goals

1. Select and onboard the first real Lotus application use case.
2. Keep the use case narrow, bounded, and enterprise-safe.
3. Validate platform runtime, safety, audit, evaluation, and operational behavior end to end.
4. Produce a reusable downstream onboarding pattern for later Lotus apps.
5. Define clear rollout, rollback, support, and success criteria.

## Non-Goals

1. Broad multi-app rollout in the same RFC.
2. Expanding `lotus-ai` into domain-owned decision-making.
3. Replacing deterministic domain workflows with AI-generated behavior.
4. Simultaneously onboarding many unrelated use cases.
5. Treating “first use case” as permission to bypass existing governance controls.

## Proposed First Use Case

The preferred first production-oriented use case should be:

1. `lotus-manage` explanation of rebalance outcome or blocker posture,
2. with optional support-facing diagnostic summarization as a second bounded variant only if the primary path succeeds.

Why this is the right first use case:

1. it is bounded and explanatory,
2. it does not ask `lotus-ai` to become the source of truth for business execution,
3. the output can stay clearly labeled as `EXPLANATION_ONLY`,
4. it exercises exactly the kind of supportability and operational narrative generation the platform is already designed for.

## Decision

`lotus-ai` will onboard one first real Lotus application use case through a governed production-onboarding sequence.

The first delivery should:

1. use one bounded task shape,
2. use one named downstream app as the integration owner,
3. require runtime-backed evaluation and rollout review before activation,
4. define support, rollback, and incident procedures before production exposure,
5. treat the resulting integration pattern as the template for future Lotus app onboarding.

## State Model and Invariants

This RFC establishes the following invariants:

1. the downstream app remains the owner of business context and final business decisions,
2. `lotus-ai` output remains bounded by its task contract and output label,
3. the first use case must be reviewable end to end through audit, evaluation, observability, and incident evidence,
4. activation must be reversible,
5. success must be measured through both runtime correctness and supportability, not only by “it responds.”

## Architecture Direction

### Use-Case Contract Hardening

The selected use case should have one explicit integration contract.

Required behavior:

1. request shape is minimal and domain-owned by the downstream app,
2. task selection is bounded and explicit,
3. output label and intended use are clear,
4. downstream rendering and review semantics are defined.

### Rollout and Evaluation

The first use case should consume the platform’s runtime-backed evaluation model rather than rely on ad hoc manual testing.

Required behavior:

1. dedicated evaluation fixtures exist for the use case,
2. approval-gate evidence is current,
3. rollout posture distinguishes pre-prod validation, limited rollout, and active production posture,
4. rollback criteria are explicit.

### Operational Readiness

The first use case is where platform promises become operational obligations.

Required behavior:

1. caller identity and authorization posture are defined for the downstream app,
2. observability and incident evidence cover the actual use case path,
3. audit and support workflows can inspect real executions,
4. downstream and platform runbooks define shared ownership and escalation.

### Adoption Template

The output of this RFC should not be just “one use case works.”

Required behavior:

1. the downstream integration pattern is documented,
2. onboarding prerequisites are explicit,
3. later app teams can follow the same model with less ambiguity,
4. future adoption is driven by evidence from this first use case rather than guesswork.

## Data and Operational Requirements

1. The use case must use real caller identity and bounded task contracts.
2. Audit records must remain sufficient for support and review.
3. Evaluation evidence must be runtime-backed.
4. Safety posture must be appropriate for the output label and downstream usage.
5. Rollback must be operationally realistic.
6. Runbooks must define shared ownership between `lotus-ai` and the downstream app.
7. Success criteria must include supportability and incident handling, not only output quality.

## Delivery Slices

### Slice 1: First Use-Case Selection and Integration Contract

Outcome:

1. the first downstream app and bounded use case are selected explicitly,
2. the request/response integration contract is hardened,
3. ownership boundaries are documented.

Acceptance gate:

1. the use case is narrow and safe,
2. the contract is explicit,
3. downstream and platform ownership are clear,
4. no domain-authoritative behavior is delegated to `lotus-ai`.

### Slice 2: Runtime, Evaluation, and Safety Readiness for the Use Case

Outcome:

1. the selected use case has dedicated runtime-backed evaluation coverage,
2. safety, identity, and observability posture are defined for the real flow,
3. rollout can be reviewed concretely.

Acceptance gate:

1. evaluation evidence is runtime-backed,
2. safety and audit posture are explicit,
3. blocked and degraded behavior are testable,
4. the platform can explain why the use case is or is not rollout-ready.

### Slice 3: Limited Rollout and Operational Validation

Outcome:

1. the use case can run in a bounded real environment,
2. operator review, support, and rollback procedures are exercised,
3. platform and downstream runbooks are validated.

Acceptance gate:

1. limited rollout is observable and reviewable,
2. rollback works,
3. support paths are usable,
4. incident evidence is sufficient.

### Slice 4: Adoption Template and Generalization

Outcome:

1. the first use case becomes the template for later Lotus app onboarding,
2. downstream prerequisites and platform guarantees are documented,
3. future adoption can proceed with less ambiguity.

Acceptance gate:

1. onboarding guidance is explicit,
2. lessons learned are captured,
3. future use-case approval criteria are reusable,
4. the platform has a proven first real production-oriented integration pattern.

## Risks

1. choosing too broad a first use case could overexpose weak spots,
2. choosing too trivial a use case would fail to validate the platform meaningfully,
3. weak shared ownership between the platform and downstream app could create support confusion,
4. rushing rollout before evaluation and operational readiness would undermine trust.

## Alternatives Considered

### Alternative 1: Keep Building Platform RFCs Without a Real Use Case

Rejected.

Reason:

1. architecture quality now needs downstream proof,
2. a shared platform that is never actually adopted stays speculative.

### Alternative 2: Onboard Multiple Apps at Once

Rejected.

Reason:

1. it would widen risk and ambiguity,
2. one strong first template is more valuable than several weak parallel starts.

### Alternative 3: Start With a Generative Drafting Use Case Instead of Explanations

Deferred.

Reason:

1. explanatory support-oriented flows are safer and more bounded,
2. they exercise platform value without putting too much pressure on unproven generative risk early.

## Acceptance Criteria

This RFC is complete when:

1. one first real Lotus application use case is integrated through `lotus-ai`,
2. the use case is bounded, supportable, and reviewable,
3. runtime-backed evaluation, audit, safety, and observability support the rollout,
4. rollback and shared ownership are operationally real,
5. the platform has a credible first-use-case template for broader adoption.

## Approval Requested

Approve this RFC if the team agrees that:

1. the next major milestone after the current platform RFC sequence is a real downstream use-case onboarding,
2. `lotus-manage` explanation of rebalance outcome or blocker posture is the best first candidate,
3. the use case should be governed through the same runtime, evaluation, safety, and observability controls as the rest of the platform,
4. delivery should proceed in the slices defined above.
