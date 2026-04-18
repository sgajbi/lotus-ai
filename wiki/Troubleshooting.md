# Troubleshooting

## How to Use This Page

Start with the symptom you see, then verify the corresponding runtime surface rather than guessing
from configuration alone.

The most common failure pattern in `lotus-ai` is not "the service is down." It is "the service is
up, but the runtime posture is not the one you think it is."

## Service Starts but Readiness Is Wrong

Symptoms:

1. `/health/live` is healthy but `/health/ready` is degraded,
2. the process starts, but runtime-backed features are unavailable,
3. startup behavior differs between local and stronger environments.

Check:

1. `/platform/runtime-status`
2. `/metadata`
3. `LOTUS_AI_STARTUP_READINESS_POLICY`
4. `LOTUS_AI_READINESS_PROBE_POLICY`

Interpretation:

1. `warn + observe` favors developer convenience,
2. `warn + degrade` allows startup but tells orchestrators the posture is degraded,
3. `enforce + degrade` is the stronger enterprise-like model.

If the runtime depends on SQL-backed stores, also verify migrations have been applied:

```powershell
make migration-apply
```

Then recheck `/platform/runtime-status`.

## Runtime Surface Says the Wrong Store or Mode Is Active

Symptoms:

1. a feature appears present in code but not in runtime,
2. prompt, retrieval, async, or evaluation behavior looks process-local when you expected durability,
3. local and Docker runs behave differently.

Check:

1. `/metadata`
2. `/platform/runtime-status`
3. `.env` or `.env.example`

Focus on:

1. store modes,
2. startup and readiness policy,
3. provider mode,
4. retrieval mode,
5. async queue and worker posture.

This usually means the service is running in a different mode than expected, not that the feature is absent.

## Provider Path Is Not What You Expected

Symptoms:

1. you expected live generation but got stubbed behavior,
2. the provider profile changed but the task output did not,
3. local OpenAI-compatible mode does not behave like the configured profile.

Check, in order:

1. `/platform/providers/operator-profile`
2. `/platform/providers`
3. `/platform/providers/policy`
4. `/platform/providers/operations-status`
5. one bounded `POST /ai/tasks/execute` call

Verify in the task result:

1. `audit.provider_mode`
2. `audit.stubbed`
3. `result.structured_output.provider_id`
4. `result.structured_output.model_id` when live execution is expected

If the results are ambiguous, roll back to:

1. `LOTUS_AI_PROVIDER_MODE=disabled`

Then recreate `lotus-ai` and `lotus-ai-worker` and verify the stubbed profile again.

Source:

- `docs/runbooks/provider-mode-switching.md`

## Retrieval Support Exists but Search Does Not Behave as Expected

Symptoms:

1. retrieval endpoints exist but live search is unavailable,
2. `knowledge_answer.v1` refuses instead of answering,
3. retrieval results look like catalog fallback rather than live indexed search.

Check:

1. `/platform/retrieval/runtime-status`
2. `/platform/retrieval/execution-status`
3. `/platform/retrieval/source-governance`
4. `/platform/retrieval/document-governance`

Interpretation:

1. retrieval support does not mean broad live corpus search is active,
2. live retrieval can be enabled in principle while the searchable promoted corpus is still unavailable,
3. refusal can be the correct conservative behavior for low-support answers.

## A Validation Gate Fails but the Code Change Looks Small

Symptoms:

1. `make check` fails on a non-obvious governance gate,
2. `make ci` fails even though the code change seems local,
3. documentation work unexpectedly trips a runtime or contract gate.

Check what category failed:

1. contract and OpenAPI gate,
2. evaluation manifest or run gate,
3. async job artifact gate,
4. migration smoke,
5. runtime-mode smoke,
6. security audit,
7. Docker build.

In `lotus-ai`, these gates protect public runtime and evidence truth, not just code style. A small
change can still affect a large platform surface.

Use:

- [Validation and CI](./Validation-and-CI.md)
- [Development Workflow](./Development-Workflow.md)

## The Wiki or Docs Feel Out of Sync with the Runtime

Symptoms:

1. page descriptions do not match the current route layout,
2. runtime surfaces exist but are not explained,
3. rollout posture in docs sounds stronger than the actual platform status.

Start from code:

1. `src/app/main.py`
2. `src/app/routers/`
3. `src/app/contracts/`

Then compare against:

1. [Platform Surfaces](./Platform-Surfaces.md)
2. [Security and Governance](./Security-and-Governance.md)
3. [Roadmap](./Roadmap.md)

In `lotus-ai`, docs are part of the control-plane contract. If the runtime truth changed, the docs
should change in the same slice.
