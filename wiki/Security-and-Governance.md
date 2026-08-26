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
provider credentials. It treats enabled retrieval as blocked until retrieval governance and
runtime-backed evaluation evidence are approval-ready, treats SQL-backed live prompt activation as
blocked until prompt governance is approval-ready, and treats runtime-enforced safety as blocked
until safety governance is approval-ready. Memory-backed prompt posture and documented-only safety
posture remain visible but informational for production go-live.

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
6. provider retention/deletion outcomes are recorded only by AI provider operations and signed for
   bounded consumers; domain consumers cannot self-assert provider deletion.

Provider retention confirmation for Idea explanation runs is currently `not_certified`. The
implementation binds provider/model/tenant identity to the durable workflow run, signs source-safe
outcomes with Ed25519, and persists idempotency through memory or SQL adapters. Provider-native
confirmation, managed-key runtime proof, and bank privacy/outsourcing/model-risk approvals remain
required; `PROVIDER_FAILURE` is explicitly blocked posture rather than deletion evidence.

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

Protected data-plane and control-plane routes require a trusted upstream caller identity in
`X-Caller-App`. Measured on `main`: of **173 published operations, the 167 that are not on the
public allowlist all refuse a caller with no identity**; the six allowlisted paths (`/`, `/health`,
`/health/live`, `/health/ready`, `/metadata`, `/metrics`) still answer. `lotus-ai` binds that authenticated caller to request-declared `caller_app`
metadata before protected routes mutate state, invoke retrieval or provider execution, retain
audit/control evidence, or run workflow-pack retry/replay execution. Missing, empty, unknown,
disabled, or mismatched caller identity fails closed with a safe `403` response.

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

Every published non-public operation binds caller-policy authorization to a trusted `X-Caller-App`
HTTP caller identity supplied by ingress or service-to-service routing. The guarantee is stated over
the *published* surface rather than over a list of routers on purpose: a router included outside the
protected inventory would otherwise be unenforced and invisible to the check that claims to cover
it.

**This identity is asserted by the upstream, not cryptographically verified.** The trust source is
`trusted_http_header`, so the guarantee holds only as far as ingress is trusted to set the header
and to strip any value a client supplies. A caller that can reach the service directly can assert
any identity. Binding coverage is complete; verification is not, and issue #149 remains open for it.
Do not read `403` on a missing header as proof that the caller is who it claims to be. Where a
route declares body-level `caller_app`, it remains API and audit metadata, and missing, empty,
unknown, disabled, or body-mismatched caller identity fails closed before protected task, retrieval,
async, prompt, provider, workflow-pack, review, or queue recovery side effects. Authorization
evidence preserves the authenticated caller, identity source, and match result for operator review.

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
