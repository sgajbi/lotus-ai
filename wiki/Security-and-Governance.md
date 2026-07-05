# Security and Governance

## Governance Posture

`lotus-ai` is built for a banking-oriented environment, so governance is part of the product
surface, not an implementation detail. The service is intentionally designed around bounded,
reviewable control planes rather than implicit AI behavior.

The important operational truth is that prompt rollout, provider rollout, retrieval activation,
safety posture, evaluation approval, caller authorization, and use-case onboarding all have
explicit runtime or governance surfaces.

Production go-live approval is stricter than runtime availability. It now requires deployment-managed
secret posture for configured live-provider secret material, including text-generation and embedding
provider credentials, and it treats enabled retrieval as blocked until retrieval governance and
runtime-backed evaluation evidence are approval-ready.

Another distinction matters when reading the platform:

1. a task can be enabled in the bounded capability catalog,
2. that does not mean the same task is approved for live-provider execution.

Use `/platform/capabilities` to understand the governed task catalog, then inspect provider-policy
and operator-profile surfaces to understand what execution path is actually permitted.

## Core Security Rules

The baseline rules are:

1. least privilege for integrations,
2. no uncontrolled tool execution in production-facing paths,
3. no silent use of sensitive data,
4. explicit output labeling and safety posture,
5. full correlation and audit metadata for every AI execution.

## Boundary Rules

`lotus-ai` must not become:

1. the source of truth for business decisions,
2. the place where domain services quietly outsource business meaning,
3. an opaque framework runtime that hides policy and approval boundaries,
4. a production-ready platform by implication rather than by evidence.

This means:

1. domain services stay accountable for business meaning,
2. prompt changes must remain reviewable,
3. retrieval sources must remain curated and attributable,
4. provider rollout must remain explicit and inspectable,
5. approval-gate posture must stay visible through runtime evidence.

Live-provider error handling is also a governed boundary. Managed OpenAI and local
OpenAI-compatible text execution use bounded retries for transient failures and report the actual
retry count after a successful retry. Text and embedding live-provider failures return Lotus-owned
safe error text rather than raw upstream provider `error.message` payloads.

The FastAPI HTTP perimeter is now also explicit. `lotus-ai` owns service-level allowed-host,
bounded CORS, secure-header, optional HSTS, and maximum request body-size controls under
`LOTUS_AI_HTTP_*` settings. These controls are transport-only; they do not contain task,
workflow-pack, retrieval, prompt, provider, or domain business logic. Ingress can be stricter, but
direct service access is no longer left to implicit defaults.

All API failures use a bounded `application/problem+json` envelope with stable `error_code`,
`correlation_id`, and optional source-safe metadata. Clients and support tooling should use those
fields instead of parsing prose-only FastAPI `detail` values.

## Data Handling and Output Policy

The initial data-handling posture is deliberately conservative:

1. send only the minimum context required,
2. preserve caller identity and correlation metadata,
3. separate raw domain data from AI-generated output,
4. preserve references for source documents, prompt versions, and execution evidence.

AI output is labeled by intended use. Current output-label categories include:

1. `EXPLANATION_ONLY`
2. `DRAFT`
3. `CLASSIFICATION`
4. `RETRIEVAL_ANSWER`

No label implies authoritative business execution.

Current runtime nuance from the deeper security docs:

1. response labeling is enforced,
2. audit and correlation evidence are enforced,
3. redaction posture is declared per task,
4. callers still remain responsible for context minimization.

## Runtime Governance Surfaces

The key governance surfaces are grouped by domain:

1. providers
   - rollout, policy, quota, budget, degradation, and control-plane actions
2. prompts
   - runtime selection, control history, promotion and rollback posture
3. retrieval
   - source governance, document governance, activation readiness, and evidence readiness
4. safety
   - policy, runtime status, evidence readiness, and governance status
5. evaluations
   - runtime status, fixtures, recorded runs, and approval-gate evidence
6. access control
   - runtime posture and governance status for caller authorization
7. use cases
   - bounded downstream rollout readiness and onboarding templates

For the grouped route map, use [Platform Surfaces](./Platform-Surfaces.md).

## Operational Security Interpretation

In practice, the right security question is rarely "is the feature implemented?" The right question
is "what does the current runtime posture actually permit?"

Examples:

1. provider support does not mean live provider rollout is approved,
2. embedding-provider support does not mean live embedding execution is production-approved,
3. retrieval support does not mean broad corpus onboarding or production go-live retrieval approval is approved,
4. durable stores existing in code does not mean production-ready posture is satisfied,
5. task support does not mean every caller is authorized to use that path.

This is why the runtime and governance surfaces matter more than static repo claims.

## Deferred Hardening Areas

Some security work is intentionally not being overstated as complete:

1. secret scanning for prompt assets,
2. sensitive-data classifiers,
3. role-aware redaction policy engine,
4. production-grade provider credential rotation,
5. formal threat modeling.

## Source Documents

- `docs/security/security-and-governance.md`
- `docs/architecture/startup-readiness-deployment-policy.md`
- `docs/runbooks/service-operations.md`
- `docs/runbooks/provider-mode-switching.md`

## Read Next

1. use [Platform Surfaces](./Platform-Surfaces.md) for the grouped governance route map,
2. use [RFC Index](./RFC-Index.md) to find the decision trail behind a capability area,
3. use [Troubleshooting](./Troubleshooting.md) when the runtime posture and expected governance state do not align.
