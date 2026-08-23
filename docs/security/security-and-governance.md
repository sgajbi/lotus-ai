# Security and Governance

`lotus-ai` is intended for a banking-oriented platform, so security and governance are first-class design concerns.

## Core Security Posture

1. Least privilege for all integrations.
2. No uncontrolled tool execution in production-facing paths.
3. No silent use of sensitive data.
4. Explicit redaction and output labeling policies.
5. Full correlation and audit metadata for every AI run.

## Governance Rules

1. `lotus-ai` must not become the source of truth for business decisions.
2. Domain apps remain accountable for the user-facing consequences of AI output.
3. New task categories require documentation and test coverage.
4. Prompt changes must be reviewable.
5. Retrieval sources must be curated and attributable.
6. Frameworks must not obscure audit, safety, or approval boundaries.

## Data Handling

Initial rule set:

1. only send the minimum context required,
2. keep caller identity and correlation metadata,
3. separate raw domain data from AI-generated output,
4. preserve audit references for source documents and prompt versions.

## Output Policy

AI output should be labeled by intended use:

1. `EXPLANATION_ONLY`
2. `DRAFT`
3. `CLASSIFICATION`
4. `RETRIEVAL_ANSWER`

No output label should imply authoritative domain execution.

The current platform inspection surface for this policy is:

1. `GET /platform/safety/policy`

Current foundation enforcement posture:

1. response labeling is enforced,
2. audit and correlation evidence are enforced,
3. redaction posture is declared per task but not yet runtime-enforced,
4. callers remain responsible for context minimization.

Current audit evidence retained for executions now includes:

1. applied `safety_mode`,
2. resolved task `redaction_posture`,
3. enforced safety-control identifiers,
4. output label and prompt/provider context already attached to the execution.

## Provider Error Boundary

Live-provider failures are mapped to stable Lotus failure categories before they cross the API
boundary. Managed OpenAI and local OpenAI-compatible text execution use the same bounded retry
controls. Text and embedding live-provider failures use the same safe-error behavior:

1. transient text timeout, rate-limit, and retryable upstream HTTP failures can retry up to the configured
   `LOTUS_AI_PROVIDER_RETRY_LIMIT`,
2. successful retry evidence records the actual retry count,
3. exhausted failures retain the typed `ProviderFailureCategory`,
4. caller-facing error detail uses Lotus-owned safe text rather than raw upstream `error.message`
   payloads.

Raw provider prompts, generated output, credentials, account details, client identifiers, and local
endpoint internals must not be returned in API errors.

## HTTP Boundary And API Error Contract

`lotus-ai` owns a thin FastAPI perimeter in addition to any ingress or gateway controls. The
service-owned boundary is transport-only and must not contain task, workflow-pack, retrieval,
prompt, provider, or domain business logic.

Protected data-plane and control-plane POST routes require a trusted `X-Caller-App` header from
ingress or an equivalent service-to-service boundary. The request body `caller_app` remains part of
the API contract for audit and evidence, but it is treated as declared metadata and must match the
authenticated HTTP caller before task execution, retrieval execution, async submission or control,
prompt control, provider control, workflow-pack execution, workflow-pack review, or queue recovery
side effects run. Authorization decisions now preserve `authenticated_caller_app`,
`caller_identity_source`, and `caller_identity_bound` so operators can distinguish trusted
caller-binding evidence from legacy body-only metadata. The current header represents a Lotus
service caller, not a human end-user entitlement model.

Environment-backed controls use the `LOTUS_AI_` prefix:

1. `LOTUS_AI_HTTP_ALLOWED_HOSTS`
2. `LOTUS_AI_HTTP_CORS_ALLOWED_ORIGINS`
3. `LOTUS_AI_HTTP_CORS_ALLOWED_METHODS`
4. `LOTUS_AI_HTTP_CORS_ALLOWED_HEADERS`
5. `LOTUS_AI_HTTP_CORS_ALLOW_CREDENTIALS`
6. `LOTUS_AI_HTTP_SECURE_HEADERS_ENABLED`
7. `LOTUS_AI_HTTP_HSTS_ENABLED`
8. `LOTUS_AI_HTTP_HSTS_MAX_AGE_SECONDS`
9. `LOTUS_AI_HTTP_MAX_REQUEST_BODY_BYTES`

The service adds secure response headers, enforces configured host and CORS posture, and rejects
oversized requests with `413` before endpoint handlers parse AI task, retrieval, or workflow-pack
payloads. HSTS is disabled by default because TLS termination may sit at ingress; enable it only
when the deployment boundary is correct for service-emitted HSTS.

This service-level caller binding does not replace caller-policy authorization. The existing
caller-policy registry still decides whether the authenticated caller is active and allowed to use a
capability. Missing caller identity, empty caller identity, unknown callers, disabled callers, and
body/header caller mismatches fail closed with a safe `403` response. Tokens, upstream credentials,
raw request bodies, prompts, tenant-sensitive identifiers, and caller spoofing details must not be
logged or echoed in problem responses.

Audit-record reads use the same caller-policy authority. `GET /ai/audit` and
`GET /ai/audit/{request_id}` derive their tenant scope on the server; callers cannot supply a tenant
query override. Restricted callers see only records for their configured tenant set, and a
cross-scope identifier is indistinguishable from a missing identifier through the same safe `404`
contract. Only the explicit `allow_audit_read_all_tenants` capability grants an all-tenant read; the
initial capability is limited to `lotus-platform`. All-tenant reads include legacy unattributed
records and synchronously write a separate, identifier-minimized access event. If that evidence
cannot be persisted, the read fails closed before an audit response is returned.

The current `X-Caller-App` trust boundary is deployment-established service identity, not
cryptographic proof. Issue #149 owns verified service JWT or mTLS identity and remains required for
the promoted-production boundary; audit tenant isolation does not weaken or absorb that work.

API errors now use a bounded `application/problem+json` response envelope with stable fields:
`type`, `title`, `status`, `detail`, `error_code`, `correlation_id`, and optional source-safe
`metadata`. FastAPI validation errors, router/service `HTTPException` failures, perimeter
rejections, and unexpected failures are mapped through the same handler. Unexpected failures return
sanitized detail and must not expose stack traces, raw upstream payloads, credentials, prompts,
generated output, tenant-sensitive identifiers, or internal endpoint internals.

## Deferred Security Work

1. secret scanning for prompt assets,
2. sensitive-data classifiers,
3. role-aware redaction policy engine,
4. production-grade provider credential rotation,
5. formal threat model.

## Framework Governance

Any future framework adoption, including LangGraph or similar orchestration libraries, should be judged against these questions:

1. Does it preserve explicit task contracts?
2. Does it preserve traceable request and response boundaries?
3. Does it make audit logging easier rather than harder?
4. Does it keep human-approval and policy gates explicit?
5. Can the team explain the runtime behavior without relying on framework magic?

If the answer to any of these is no, the framework should not be introduced into a production-facing path.
