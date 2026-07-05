# Provider Mode Switching Runbook

This runbook defines the approved operator procedure for switching `lotus-ai` between:

1. deterministic stub execution,
2. managed OpenAI execution,
3. local OpenAI-compatible execution.

Use this runbook together with:

1. `GET /platform/providers/operator-profile`
2. `GET /platform/providers`
3. `GET /platform/providers/policy`
4. `GET /platform/providers/operations-status`
5. `GET /platform/providers/activation-readiness`

## Common Verification Rule

After every provider-mode change:

1. recreate `lotus-ai` and `lotus-ai-worker`,
2. verify `/health/ready`,
3. verify `/platform/providers/operator-profile`,
4. verify `/platform/providers`,
5. verify `/platform/providers/policy`,
6. verify `/platform/providers/operations-status`,
7. run one bounded `POST /ai/tasks/execute` request and confirm:
   1. `audit.provider_mode`
   2. `audit.stubbed`
   3. `result.structured_output.provider_id`
   4. `result.structured_output.model_id` when live execution is expected.

The active provider path is not considered verified until all of those agree.

## Profile 1: Deterministic Stub

Use when:

1. billing must be fully off,
2. local validation should remain deterministic,
3. live provider posture is not approved.

Required `.env` settings:

```env
LOTUS_AI_PROVIDER_MODE=disabled
```

Switch procedure:

```powershell
cd C:\Users\Sandeep\projects\lotus-ai
docker compose up -d --force-recreate lotus-ai lotus-ai-worker
```

Expected verification:

1. `/platform/providers/operator-profile` shows `selected_profile_id = stubbed_disabled`
2. `/platform/providers` shows no text provider enabled for execution
3. `POST /ai/tasks/execute` returns `audit.provider_mode = disabled`
4. `POST /ai/tasks/execute` returns `audit.stubbed = true`

## Profile 2: Managed OpenAI

Use when:

1. managed-provider quality is required,
2. external billing is approved,
3. allowlisted live text execution is acceptable.

Required `.env` settings:

```env
LOTUS_AI_PROVIDER_MODE=openai
LOTUS_AI_PROVIDER_ROLLOUT_STATE=CANARY_ENABLED
LOTUS_AI_LIVE_TEXT_PROVIDER_ID=text.openai
LOTUS_AI_LIVE_TEXT_MODEL_ID=<approved model>
LOTUS_AI_LIVE_TEXT_PROVIDER_API_KEY=<deployment secret>
LOTUS_AI_LIVE_TEXT_ALLOWED_TASK_IDS=explain.v1
LOTUS_AI_PROVIDER_TIMEOUT_MS=45000
LOTUS_AI_PROVIDER_RETRY_LIMIT=1
LOTUS_AI_PROVIDER_MAX_OUTPUT_TOKENS=4096
```

Switch procedure:

```powershell
cd C:\Users\Sandeep\projects\lotus-ai
docker compose up -d --force-recreate lotus-ai lotus-ai-worker
```

Expected verification:

1. `/platform/providers/operator-profile` shows `selected_profile_id = managed_openai`
2. `/platform/providers` shows `text.openai` enabled for execution when live posture is valid
3. `POST /ai/tasks/execute` returns `audit.provider_mode = openai`
4. `POST /ai/tasks/execute` returns `audit.stubbed = false`

## Profile 3: Local OpenAI-Compatible via Ollama

Use when:

1. local execution is preferred,
2. managed-provider billing should be avoided,
3. developer-local or workstation-local validation is sufficient.

Bring up Ollama:

```powershell
cd C:\Users\Sandeep\projects\lotus-ai
docker compose --profile local-llm up -d ollama
docker compose exec ollama ollama pull qwen3:8b
```

Required `.env` settings:

```env
LOTUS_AI_PROVIDER_MODE=local_openai_compatible
LOTUS_AI_PROVIDER_ROLLOUT_STATE=CANARY_ENABLED
LOTUS_AI_LIVE_TEXT_PROVIDER_ID=text.local
LOTUS_AI_LIVE_TEXT_MODEL_ID=qwen3:8b
LOTUS_AI_LIVE_TEXT_API_BASE=http://ollama:11434/v1
LOTUS_AI_LIVE_TEXT_ALLOWED_TASK_IDS=explain.v1
LOTUS_AI_PROVIDER_TIMEOUT_MS=45000
LOTUS_AI_PROVIDER_RETRY_LIMIT=1
LOTUS_AI_PROVIDER_MAX_OUTPUT_TOKENS=4096
```

Switch procedure:

```powershell
cd C:\Users\Sandeep\projects\lotus-ai
docker compose up -d --force-recreate lotus-ai lotus-ai-worker
```

Expected verification:

1. `/platform/providers/operator-profile` shows `selected_profile_id = local_ollama`
2. `/platform/providers/operations-status` is not rollout-blocked for the local live path
3. `/platform/providers/activation-readiness` does not report missing local model catalog posture
4. `POST /ai/tasks/execute` returns `audit.provider_mode = local_openai_compatible`
5. `POST /ai/tasks/execute` returns `audit.stubbed = false`

## Profile 4: Local OpenAI-Compatible via vLLM

Use when:

1. a stronger workstation or shared host is available,
2. OpenAI-compatible local serving is still preferred,
3. higher local throughput is required than a simple developer-local setup.

Example vLLM Docker command:

```powershell
docker run --rm -p 8000:8000 `
  vllm/vllm-openai:latest `
  --model mistralai/Mistral-7B-Instruct-v0.2
```

Then set:

```env
LOTUS_AI_PROVIDER_MODE=local_openai_compatible
LOTUS_AI_PROVIDER_ROLLOUT_STATE=CANARY_ENABLED
LOTUS_AI_LIVE_TEXT_PROVIDER_ID=text.local
LOTUS_AI_LIVE_TEXT_MODEL_ID=mistralai/Mistral-7B-Instruct-v0.2
LOTUS_AI_LIVE_TEXT_API_BASE=http://host.docker.internal:8000/v1
LOTUS_AI_LIVE_TEXT_ALLOWED_TASK_IDS=explain.v1
LOTUS_AI_PROVIDER_RETRY_LIMIT=1
```

Expected verification:

1. `/platform/providers/operator-profile` shows `selected_profile_id = local_vllm`
2. `/platform/providers/activation-readiness` reports local live posture as activatable
3. `POST /ai/tasks/execute` returns `audit.provider_mode = local_openai_compatible`
4. `result.structured_output.model_id` matches the configured vLLM model id

## Rollback Rule

If any provider-mode change produces ambiguous results:

1. switch immediately back to `LOTUS_AI_PROVIDER_MODE=disabled`
2. recreate `lotus-ai` and `lotus-ai-worker`
3. verify the deterministic stub profile is restored before investigating the failed live path

Do not leave the platform in a half-switched live configuration.

## Retry And Error Boundary Rule

Managed OpenAI and local OpenAI-compatible text execution share the same HTTP retry controls. Text
and embedding live-provider failures share the same safe error boundary.

Operator expectations:

1. `LOTUS_AI_PROVIDER_RETRY_LIMIT` is a bounded retry count for transient timeout, rate-limit, and retryable upstream HTTP failures.
2. successful responses report the actual retry count in provider execution evidence.
3. exhausted retries preserve the typed `ProviderFailureCategory` used by provider operations and degradation tracking.
4. caller-facing API errors use Lotus-owned safe text and must not include raw provider `error.message` content, raw prompt fragments, generated output, credentials, account metadata, client identifiers, or local endpoint internals.
5. use `/platform/providers/operations-status` and provider degradation counters for triage instead of relying on raw upstream error bodies.
