# Glossary

The vocabulary `lotus-ai` uses in its routes, contracts and evidence. Definitions are taken from the
implementation on `main`, not from intent. `src/app/contracts/` declares 124 enum types; this page
covers the terms you need to read the service, not all of them.

## The four posture questions

Almost every platform group answers the same four questions, which is why the surface is large
without being complicated. **57 of the 163 `/platform` operations are these four repeated per
domain** — learn them once.

| surface | question it answers | groups exposing it | key fields |
|---|---|---|---|
| `runtime-status` | *What is true right now?* | 14 | `posture`, `domains`, `freshness`, `*_count` |
| `activation-readiness` | *Could this be switched on?* | 12 | `activation_ready`, `activation_path`, `blocking_findings` |
| `runbook-readiness` | *Have the operator prerequisites been completed?* | 14 | `runbook_ready`, `items`, `required_item_count`, `completed_required_item_count` |
| `governance-status` | *Do the three above agree?* | 17 | `governance_ready`, and nested `runtime_status`, `activation_readiness`, `runbook_readiness` |

`governance-status` is the composite: it embeds the other three and adds `blocking_area_count`. When
a group is not behaving, read `governance-status` first and follow `blocking_findings` down.

**Readiness is not authorization.** A permissive readiness posture never relaxes a security control.

## Execution vocabulary

**Task** — the bounded unit of AI execution, submitted to `POST /ai/tasks/execute`. A task has an
identifier, a declared contract in `src/app/contracts/`, and a resolved prompt, provider and safety
posture at execution time.

**Workflow pack** — a registered, governed bundle executed through
`POST /platform/workflow-packs/execute` when a caller needs registered-pack eligibility, run
recording and explicit run identity in one step. Workflow packs are the largest platform group (29
operations) and carry their own registry, run store, task-flow store and queue-event store.

**Capability pack** — an *app-facing* packaging of AI capability, distinct from a workflow pack. It
carries `pack_id`, `family_id` and a `family_kind` of `COMMENTARY` or `EXPLANATION`, and a
`CapabilityPackMaturityStage` of `EXPERIMENTAL`, `REUSABLE` or `APPROVED`. Workflow packs are *what
runs*; capability packs are *what an application adopts*.

**Task flow** — the recorded progression of a workflow-pack run, stored separately from the run
itself so review state and heartbeat/attention posture survive independently.

**Output label** — the declared intended use of AI output, one of `EXPLANATION_ONLY`, `DRAFT`,
`CLASSIFICATION`, `RETRIEVAL_ANSWER`. **No label implies authoritative business execution.** Labels
are enforced; they are the contract between the service and a consuming application about what the
output may be used for.

**Async job status** — `STAGED`, `QUEUED`, `CLAIMED`, `RUNNING`, `FAILED`, `COMPLETED`,
`ABANDONED`, `SUPERSEDED`. Staging and queueing are distinct: a staged job exists durably before any
queue backend accepts it, which is what makes recovery possible when a queue loses a delivery.
`ABANDONED` and `SUPERSEDED` are outcomes of operator recovery actions, not of execution.

## Identity and scope

**Caller app** — the upstream service identity, supplied in the `X-Caller-App` header. Every
published operation except six operational paths refuses a caller with no identity.

**Caller policy** — the server-side `CallerPolicyDescriptor` for a caller app, holding its
lifecycle status, tenant restrictions and capabilities. It is the authority for what a caller may
read; the request never carries it.

**Tenant scope** — the set of tenants a caller may read audit records for, derived from caller
policy by `resolve_audit_read_scope`. Either `RESTRICTED_TENANTS` (a named list, applied as a SQL
predicate) or all-tenants (privileged identity only). See
[Security and Governance](Security-and-Governance) for the rules and for the one route that
sits outside them.

**Trust source** — how the caller identity arrived: `trusted_http_header`, a verified service JWT,
or an mTLS SAN. The header source is *asserted*, not verified
([#149](https://github.com/sgajbi/lotus-ai/issues/149)).

## Evidence vocabulary

**Audit record** — the durable record of one execution, readable through `/ai/audit`. Persisted only
when `LOTUS_AI_AUDIT_STORE_MODE=sqlalchemy`; the default `memory` mode discards it on restart.

**Correlation id** — the identifier threading a request through middleware, execution, evidence and
problem responses. Present in every `application/problem+json` body; use it rather than parsing
`detail`.

**Attestation** — a signed statement about a workflow run. Signing material is configured through
`LOTUS_AI_WORKFLOW_RUN_ATTESTATION_*`; public keys are served from
`/.well-known/lotus-ai-workflow-attestation-keys`, which **requires caller identity**. Stub
execution is `test_only` and cannot receive an approved attestation.

**Retention confirmation** — provider-side evidence that data was retained or deleted as governed,
tracked in its own store and surface. Distinct from the audit record, which is the service's own
account of what it did.

**Supportability** — whether an AI-backed surface can currently be supported, exposed as
`ai_surface_supportability` on `runtime-status` with a bounded `supportability_reason` per surface.
It covers 17 workflow-pack surfaces and carries `no_sensitive_content_telemetry` so an operator can
judge telemetry posture without inspecting prompts or generated content.

**Posture** — a bounded summary value rather than a raw state dump. The service prefers reporting a
posture with a reason code over exposing internals; operators and tooling should read the posture
and its reason, not infer from absence.

## Modes and stages

**Store mode** — `memory` or `sqlalchemy`, chosen independently for each of fourteen stores. See
[Configuration Reference](Configuration-Reference).

**Provider mode / retrieval mode / embedding provider mode** — `disabled` by default. A disabled
mode is a governed state, not a broken one.

**Safety mode** — `documented_only` by default: redaction posture is declared per task rather than
enforced at runtime.

**Rollout state** — the provider's governed activation position, defaulting to `STUB_DEFAULT`.

**Cutover state** — the async runtime's position between in-process execution
(`in_process_only`) and a managed queue.

**Deployment split stage** — whether runtime, retrieval and evals are deployed together (`unified`)
or separately.

**Delivery phase** — the service's own declared maturity, `foundation` by default.

## Terms used precisely

**Governed** — subject to an explicit, inspectable policy surface rather than an implicit default.
Used throughout the codebase and not as a synonym for "good".

**Bounded** — deliberately limited in size or shape, and documented as such: bounded samples,
bounded problem responses, bounded summaries. Bounded output is a safety property, not a limitation.

**Fail closed** — refuse rather than proceed when a control cannot be evaluated. Applies to unknown
caller identity, unresolvable tenant scope, unsupported store modes, and evidence that cannot be
persisted.

**Source-safe** — evidence shaped so it can be shown to an operator without exposing prompts,
generated content, credentials or tenant-sensitive identifiers.

**Review-gated** — an execution path whose result requires explicit review before it can be treated
as accepted.

## Read next

1. [Architecture](Architecture) — how these pieces fit together
2. [Platform Surfaces](Platform-Surfaces) — the grouped route map
3. [Configuration Reference](Configuration-Reference) — every mode and switch
4. [Security and Governance](Security-and-Governance) — identity, labelling, evidence
