# Configuration Reference

Every setting `lotus-ai` reads, with the default that applies when the variable is unset. Generated
from `src/app/config.py` on `main` and verified against it; if this page and that file disagree, the
file is right and this page is a bug.

All variables take the **`LOTUS_AI_`** prefix (`env_prefix="LOTUS_AI_"`). Unknown variables are
ignored (`extra="ignore"`), so a misspelled name is silently inert rather than an error — check the
spelling against this page when a setting appears to have no effect.

## Reading the defaults

Two things are true of the default configuration and are easy to miss because they are spread across
many settings:

1. **Nothing is persisted.** All seventeen `*_STORE_MODE` settings default to `memory`. A restart
   discards audit records, prompt rollout state, workflow-pack runs, artifacts and everything else.
2. **Nothing is called.** `PROVIDER_MODE`, `RETRIEVAL_MODE` and `EMBEDDING_PROVIDER_MODE` default to
   `disabled`; `SAFETY_MODE` defaults to `documented_only`; `ASYNC_QUEUE_BACKEND_MODE` to `none`.

An unconfigured instance is therefore a governed, inspectable, entirely local service that executes
nothing against a provider and remembers nothing across restarts. That is a deliberate posture, not
an incomplete install.

## Durable stores

Each accepts `memory` or `sqlalchemy`. Selecting `sqlalchemy` requires `LOTUS_AI_DATABASE_URL`;
omitting it raises at first use with a message naming the missing variable. Any other value raises
`Unsupported ..._STORE_MODE`. Selection is fail-closed, and because these are plain strings with no
`Literal` constraint, a typo surfaces on the first request that touches the store rather than at
startup — smoke-test a route that uses the store after changing one.

| variable | default |
|---|---|
| `LOTUS_AI_AUDIT_STORE_MODE` | `memory` |
| `LOTUS_AI_PROMPT_STORE_MODE` | `memory` |
| `LOTUS_AI_RETRIEVAL_STORE_MODE` | `memory` |
| `LOTUS_AI_ACCESS_CONTROL_STORE_MODE` | `memory` |
| `LOTUS_AI_WORKFLOW_PACK_REGISTRY_STORE_MODE` | `memory` |
| `LOTUS_AI_PROVIDER_OPERATIONS_STORE_MODE` | `memory` |
| `LOTUS_AI_PROVIDER_RETENTION_CONFIRMATION_STORE_MODE` | `memory` |
| `LOTUS_AI_ASYNC_RUNTIME_STORE_MODE` | `memory` |
| `LOTUS_AI_WORKFLOW_PACK_RUN_STORE_MODE` | `memory` |
| `LOTUS_AI_WORKFLOW_PACK_TASK_FLOW_STORE_MODE` | `memory` |
| `LOTUS_AI_WORKFLOW_PACK_QUEUE_EVENT_STORE_MODE` | `memory` |
| `LOTUS_AI_MODEL_CATALOGUE_STORE_MODE` | `memory` |
| `LOTUS_AI_KILL_SWITCH_STORE_MODE` | `memory` |
| `LOTUS_AI_RATE_CARD_STORE_MODE` | `memory` |
| `LOTUS_AI_EVALUATION_RUNTIME_STORE_MODE` | `memory` |
| `LOTUS_AI_ARTIFACT_STORE_MODE` | `memory` |
| `LOTUS_AI_ARTIFACT_OBJECT_STORE_MODE` | `memory` |
| `LOTUS_AI_DATABASE_URL` | *(none)* — required by any `sqlalchemy` mode |
| `LOTUS_AI_ARTIFACT_OBJECT_STORE_ROOT` | *(none)* |

## Logging

| variable | default |
|---|---|
| `LOTUS_AI_LOG_LEVEL` | `INFO` — level for the structured JSON app logger (issue #152 S1) |

## Service identity

| variable | default |
|---|---|
| `LOTUS_AI_SERVICE_NAME` | `lotus-ai` |
| `LOTUS_AI_SERVICE_VERSION` | `0.1.0` |
| `LOTUS_AI_DELIVERY_PHASE` | `foundation` |

## Provider execution

| variable | default |
|---|---|
| `LOTUS_AI_PROVIDER_MODE` | `disabled` |
| `LOTUS_AI_PROVIDER_ROLLOUT_STATE` | `STUB_DEFAULT` |
| `LOTUS_AI_PROVIDER_TIMEOUT_MS` | `4000` |
| `LOTUS_AI_PROVIDER_RETRY_LIMIT` | `0` |
| `LOTUS_AI_PROVIDER_MAX_OUTPUT_TOKENS` | `512` |
| `LOTUS_AI_SECRET_SOURCE_MODE` | `local_or_unspecified` |

### Live text provider

| variable | default |
|---|---|
| `LOTUS_AI_LIVE_TEXT_PROVIDER_ID` | *(none)* |
| `LOTUS_AI_LIVE_TEXT_MODEL_ID` | *(none)* |
| `LOTUS_AI_LIVE_TEXT_MODEL_VERSION` | *(none)* |
| `LOTUS_AI_LIVE_TEXT_PROVIDER_API_KEY` | *(none)* |
| `LOTUS_AI_LIVE_TEXT_API_BASE` | `https://api.openai.com/v1` |
| `LOTUS_AI_LIVE_TEXT_ALLOWED_TASK_IDS` | `""` — empty allows none |
| `LOTUS_AI_LIVE_TEXT_LOCAL_PROBE_TIMEOUT_MS` | `1500` |
| `LOTUS_AI_LIVE_TEXT_LOCAL_PROBE_CACHE_SECONDS` | `15` |

### Cost, quota, budget and degradation

Each enforcement switch is **off** by default. Turning enforcement on without setting the
corresponding limit leaves the limit `None`; set both together.

| variable | default |
|---|---|
| `LOTUS_AI_LIVE_TEXT_INPUT_COST_PER_1K_TOKENS` | *(none)* |
| `LOTUS_AI_LIVE_TEXT_OUTPUT_COST_PER_1K_TOKENS` | *(none)* |
| `LOTUS_AI_LIVE_TEXT_QUOTA_ENFORCED` | `false` |
| `LOTUS_AI_LIVE_TEXT_DEFAULT_QUOTA_LIMIT` | *(none)* |
| `LOTUS_AI_LIVE_TEXT_TASK_QUOTA_LIMITS` | `""` |
| `LOTUS_AI_LIVE_TEXT_CALLER_QUOTA_LIMITS` | `""` |
| `LOTUS_AI_LIVE_TEXT_TENANT_QUOTA_LIMITS` | `""` |
| `LOTUS_AI_LIVE_TEXT_BUDGET_ENFORCED` | `false` |
| `LOTUS_AI_LIVE_TEXT_SOFT_BUDGET_USD` | *(none)* |
| `LOTUS_AI_LIVE_TEXT_HARD_BUDGET_USD` | *(none)* |
| `LOTUS_AI_LIVE_TEXT_DEGRADATION_ENFORCED` | `false` |
| `LOTUS_AI_LIVE_TEXT_DEGRADED_FAILURE_COUNT_THRESHOLD` | *(none)* |
| `LOTUS_AI_LIVE_TEXT_CIRCUIT_OPEN_FAILURE_COUNT_THRESHOLD` | *(none)* |
| `LOTUS_AI_LIVE_TEXT_CIRCUIT_OPEN_SECONDS` | *(none)* |

### Embeddings

| variable | default |
|---|---|
| `LOTUS_AI_EMBEDDING_PROVIDER_MODE` | `disabled` |
| `LOTUS_AI_LIVE_EMBEDDING_PROVIDER_ID` | *(none)* |
| `LOTUS_AI_LIVE_EMBEDDING_MODEL_ID` | *(none)* |
| `LOTUS_AI_LIVE_EMBEDDING_PROVIDER_API_KEY` | *(none)* |

## Retrieval and safety

| variable | default |
|---|---|
| `LOTUS_AI_RETRIEVAL_MODE` | `disabled` |
| `LOTUS_AI_SAFETY_MODE` | `documented_only` — posture is declared per task, not enforced at runtime |

## Async runtime and worker fleet

The worker is a second process (`src/app/worker_main.py`) sharing this configuration.

| variable | default |
|---|---|
| `LOTUS_AI_ASYNC_CUTOVER_STATE` | `in_process_only` |
| `LOTUS_AI_ASYNC_QUEUE_BACKEND_MODE` | `none` |
| `LOTUS_AI_ASYNC_QUEUE_REDIS_URL` | *(none)* |
| `LOTUS_AI_ASYNC_QUEUE_NAME` | `lotus-ai:async:jobs` |
| `LOTUS_AI_ASYNC_WORKER_ID` | `lotus-ai-worker-1` |
| `LOTUS_AI_ASYNC_WORKER_QUEUE_POLL_SECONDS` | `5` |
| `LOTUS_AI_ASYNC_WORKER_DRAIN_ENABLED` | `false` |

## Workflow-run attestation

Signing material for workflow-run attestations. The public keys are served from
`GET /.well-known/lotus-ai-workflow-attestation-keys`, which **requires caller identity** — it is
not in the public allowlist, so an anonymous verifier cannot fetch them.

| variable | default |
|---|---|
| `LOTUS_AI_WORKFLOW_RUN_ATTESTATION_KEY_ID` | *(none)* |
| `LOTUS_AI_WORKFLOW_RUN_ATTESTATION_PRIVATE_KEY_BASE64URL` | *(none)* |
| `LOTUS_AI_WORKFLOW_RUN_ATTESTATION_ROTATION_EPOCH` | *(none)* |
| `LOTUS_AI_WORKFLOW_RUN_ATTESTATION_KEY_NOT_BEFORE_UTC` | *(none)* |
| `LOTUS_AI_WORKFLOW_RUN_ATTESTATION_KEY_NOT_AFTER_UTC` | *(none)* |
| `LOTUS_AI_WORKFLOW_RUN_ATTESTATION_ROTATED_PUBLIC_KEYS_JSON` | `[]` |
| `LOTUS_AI_WORKFLOW_RUN_ATTESTATION_TTL_SECONDS` | `300` |
| `LOTUS_AI_WORKFLOW_RUN_MODEL_RISK_INVENTORY_JSON` | `[]` — seed input only: mirrored into APPROVED model-catalogue rows at seed time; model-risk evaluation reads the catalogue, never this variable (#191) |

## Deployment, startup and readiness

| variable | default |
|---|---|
| `LOTUS_AI_DEPLOYMENT_SPLIT_STAGE` | `unified` |
| `LOTUS_AI_STARTUP_READINESS_POLICY` | `warn` |
| `LOTUS_AI_READINESS_PROBE_POLICY` | `observe` |

Readiness policy does not alter authorization — a permissive readiness posture never relaxes a
security control.

## HTTP boundary

Transport-only controls. They contain no task, workflow-pack, retrieval, prompt, provider or domain
logic, and ingress may be stricter.

| variable | default |
|---|---|
| `LOTUS_AI_HTTP_ALLOWED_HOSTS` | `*` |
| `LOTUS_AI_HTTP_CORS_ALLOWED_ORIGINS` | *(bounded list in `config.py`)* |
| `LOTUS_AI_HTTP_CORS_ALLOWED_METHODS` | `GET,POST,PUT,PATCH,DELETE,OPTIONS` |
| `LOTUS_AI_HTTP_CORS_ALLOWED_HEADERS` | *(bounded list in `config.py`)* |
| `LOTUS_AI_HTTP_CORS_ALLOW_CREDENTIALS` | `false` |
| `LOTUS_AI_HTTP_SECURE_HEADERS_ENABLED` | `true` |
| `LOTUS_AI_HTTP_HSTS_ENABLED` | `false` |
| `LOTUS_AI_HTTP_HSTS_MAX_AGE_SECONDS` | `31536000` |
| `LOTUS_AI_HTTP_MAX_REQUEST_BODY_BYTES` | `1048576` — oversize requests get `413 application/problem+json` before any handler runs |

## Caller identity

| variable | default |
|---|---|
| `LOTUS_AI_LOCAL_HEADER_CALLER_IDENTITY_ENABLED` | `false` |

Default-closed. When enabled, header-asserted identity may exercise the privileged all-tenant audit
capability — intended for local runtimes only. In a promoted runtime the privileged path fails
closed unless the caller trust source is a verified service JWT or mTLS SAN. The effective posture
is exposed by `GET /platform/runtime-status`.

Caller identity itself is **asserted by the upstream, not cryptographically verified**
([#149](https://github.com/sgajbi/lotus-ai/issues/149)); see
[Security and Governance](Security-and-Governance).

## Read next

1. [Getting Started](Getting-Started) — choosing a local runtime posture
2. [Architecture](Architecture) — what these switches select between
3. [Operations Runbook](Operations-Runbook) — changing posture on a running service
4. [Security and Governance](Security-and-Governance) — the controls these settings bound
