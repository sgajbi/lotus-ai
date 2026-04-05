# RFC-0027: Local and Remote OpenAI-Compatible Provider Routing

- Status: Active
- Date: 2026-04-05
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers, lotus-platform maintainers, lotus-gateway maintainers

## Summary

`lotus-ai` already exposes one bounded AI execution seam to downstream Lotus applications:

1. callers send structured task requests to `POST /ai/tasks/execute`,
2. `lotus-ai` applies caller policy, runtime safety, audit, and provider controls,
3. callers receive one stable execution contract regardless of whether the runtime path is stubbed
   or live.

That platform shape is correct and should be preserved.

What is still missing is a production-grade way to run the same bounded task contract against:

1. a remote managed provider such as OpenAI,
2. a local open-source model served behind an OpenAI-compatible endpoint,
3. a deterministic stub path when billing, quota, or operational posture requires it.

This RFC defines that routing model.

## Implementation Progress

Completed:

1. Slice 1: provider abstraction normalization
2. Slice 2: local OpenAI-compatible runtime support
3. Slice 3: operator switching and runbooks
4. Slice 4: evaluation and operational hardening
5. Slice 5: downstream adoption validation and local-output quality guardrails

Remaining:
1. final merge, rollout, and cross-repo acceptance closure

The decision is to keep one stable Lotus AI task contract and add a second live-provider mode:
`local_openai_compatible`.

That mode will allow `lotus-ai` to route the same task contract to a local model server such as
Ollama or vLLM without changing `lotus-gateway` or `lotus-workbench`.

## Why This RFC Exists

The current provider path solves only part of the problem.

Today:

1. `provider_mode=disabled` preserves deterministic stub execution,
2. `provider_mode=openai` enables a live managed provider path,
3. downstream Lotus apps remain decoupled from direct model-provider integration.

That is a good baseline, but it is incomplete for real platform usage.

The missing capability is controlled local model execution.

Without it:

1. every live narrative or copilot workflow depends on external provider billing and quota,
2. offline or restricted-network environments cannot use the live AI path,
3. model experimentation is artificially coupled to one vendor path,
4. local privacy-preserving deployments require ad hoc workarounds outside the governed platform,
5. switching between local and remote execution is operationally awkward and under-documented.

This RFC closes that gap without weakening the existing bounded execution contract.

## Problem Statement

The current `lotus-ai` provider implementation is materially tied to one remote provider family.

In practice, the codebase currently assumes:

1. `provider_mode=openai` means a remote OpenAI Responses API execution path,
2. `provider_mode=disabled` means deterministic stub execution,
3. one set of live text configuration values is sufficient because only one live mode exists.

That is too narrow for the platform direction we now need.

We need:

1. one caller contract,
2. one provider gateway,
3. one audit and supportability posture,
4. multiple live execution backends,
5. an operator-controlled way to switch between them without code forks in downstream apps.

The key design risk is obvious:

If local model support is added as a one-off path, we will duplicate routing logic, fragment
observability, and make downstream behavior harder to reason about.

That is not acceptable.

## Goals

1. Add a governed local live-provider mode for text generation tasks.
2. Preserve the existing `lotus-ai` task contract for downstream callers.
3. Keep `lotus-gateway` and `lotus-workbench` unaware of whether the active provider is local or
   remote.
4. Support fast operator switching between:
   1. `disabled`
   2. `openai`
   3. `local_openai_compatible`
5. Reuse as much of the current OpenAI-compatible transport and parsing stack as possible.
6. Preserve bounded caller policy, rollout, safety, audit, and evidence behavior across all modes.
7. Make the local model path observable and supportable to the same standard as the remote path.

## Non-Goals

1. Direct browser-to-model calls.
2. Allowing `lotus-gateway` or `lotus-workbench` to choose raw model endpoints directly.
3. Building a separate local-only contract or second task API.
4. Supporting every open-source serving framework in the first slice.
5. Introducing unrestricted provider fallback chains that obscure what actually executed.
6. Treating local model execution as exempt from safety, caller policy, or audit requirements.

## Current Baseline

Today, the relevant `lotus-ai` seams already exist:

1. provider configuration lives in `src/app/config.py`,
2. provider selection flows through `src/app/providers/registry.py`,
3. bounded execution posture is derived in `src/app/services/task_execution_path.py`,
4. audit, rollout, and readiness surfaces already exist under `src/app/services/*provider*`,
5. task callers integrate through `POST /ai/tasks/execute`.

This is the right architecture base.

The limitation is not architectural absence. It is provider specialization.

Specifically:

1. `OpenAILiveTextProvider` is currently both the transport implementation and the provider-mode
   specialization,
2. the runtime posture mostly distinguishes only `disabled`, `stub`, and `openai`,
3. local OpenAI-compatible servers are not modeled explicitly as a first-class live mode,
4. operator docs cover turning OpenAI on and off, but not switching between remote and local live
   backends.

## Decision

`lotus-ai` will add a new live-provider mode:

1. `provider_mode=local_openai_compatible`

The platform will treat this as:

1. a non-stub live-provider mode,
2. governed by the same caller allowlist and task allowlist controls,
3. executed through the same provider gateway and task runtime mapping,
4. exposed to callers through the same task response contract,
5. auditable as a distinct provider mode with explicit provider identity and model identity.

This RFC does not create a second API.

It extends the existing one.

## Architecture Decision

### 1. Keep One Caller Contract

The correct boundary remains:

1. `lotus-workbench` and other apps call `lotus-gateway`,
2. `lotus-gateway` calls `lotus-ai`,
3. `lotus-ai` chooses the provider backend,
4. callers see one stable task result contract.

No downstream app should need to know:

1. whether the provider is local or remote,
2. which serving framework is in use,
3. which API base is configured.

That separation is the core platform value.

### 2. Separate Provider Mode from Provider Adapter Implementation

The current `OpenAILiveTextProvider` implementation should be split conceptually into:

1. an OpenAI-compatible transport and response parser,
2. mode-specific provider descriptors and governance posture.

That allows:

1. `openai` to remain the managed remote mode,
2. `local_openai_compatible` to become the local live mode,
3. both modes to reuse the same wire-format handling where compatible,
4. differences in readiness, quota, budget, and incident handling to remain explicit.

This is the right design pattern because the protocol is shared while the operational posture is
not.

### 3. Preserve One Registry and One Gateway

Provider routing should still happen through `src/app/providers/registry.py`.

The registry should resolve:

1. stub adapters,
2. remote managed text adapters,
3. local OpenAI-compatible text adapters,
4. embedding adapters as a separate concern.

The provider gateway should continue to own:

1. runtime selection,
2. failure mapping,
3. audit capture,
4. response normalization.

No task-specific code should bypass that gateway.

### 4. Reuse OpenAI-Compatible APIs Deliberately

The first local provider path should target OpenAI-compatible text endpoints.

That is the right first step because it:

1. minimizes duplicated transport logic,
2. allows easier evaluation across local and remote backends,
3. supports developer-friendly local serving options such as Ollama,
4. supports higher-throughput workstation or server serving options such as vLLM.

This RFC explicitly prefers:

1. Ollama for developer-local simplicity,
2. vLLM for stronger workstation or shared-host throughput,
3. one normalized `local_openai_compatible` mode in Lotus regardless of which underlying local
   server is used.

### 5. Keep Operator Intent Explicit

We should not introduce silent live-provider fallback between remote and local backends in the first
implementation.

Reason:

1. silent fallback hides which model actually wrote the result,
2. it weakens audit clarity,
3. it makes quality debugging materially harder,
4. it complicates spend and operational incident review.

The first implementation should support explicit switching, not implicit failover.

If fallback is needed later, it should be a separate governed RFC with explicit audit fields and
operator controls.

## Provider Modes and Configuration

The provider-mode contract should become:

1. `disabled`
2. `stub`
3. `openai`
4. `local_openai_compatible`

The first local-provider slice should avoid introducing a second parallel configuration namespace if
the existing live-text fields can already carry the correct values.

That means the active live-provider configuration remains:

1. `LOTUS_AI_PROVIDER_MODE`
2. `LOTUS_AI_LIVE_TEXT_PROVIDER_ID`
3. `LOTUS_AI_LIVE_TEXT_MODEL_ID`
4. `LOTUS_AI_LIVE_TEXT_API_BASE`
5. `LOTUS_AI_LIVE_TEXT_PROVIDER_API_KEY`
6. timeout, token, budget, and degradation controls already present in `Settings`

This is deliberate.

It reduces configuration complexity while still allowing operators to switch backends by changing:

1. provider mode,
2. model identifier,
3. API base,
4. API key requirement.

### Operational Profiles

The documented operator profiles should be:

1. `disabled`
   1. deterministic stub output
   2. no external billing
2. `openai`
   1. remote managed provider
   2. governed live-provider usage
3. `local_openai_compatible`
   1. local or self-hosted model server
   2. OpenAI-compatible API base
   3. optional API key depending on server

The switching mechanism should be configuration-only plus service restart or container recreate.

## Audit, Evidence, and Supportability Requirements

The local provider path must not be a hidden variant of the remote path.

The task audit response should continue to include:

1. `provider_mode`
2. `provider_id`
3. `model_id`
4. `stubbed`

The provider evidence and platform status surfaces should additionally make it easy to distinguish:

1. whether execution was local or remote,
2. which API base class was used,
3. whether the result came from an OpenAI-compatible local server versus the OpenAI-hosted service.

The right way to model that is not necessarily a new top-level task field in the first slice.

It may be better represented through:

1. provider catalog metadata,
2. provider operations status,
3. readiness and observability endpoints,
4. evidence descriptors attached to the provider execution record.

The RFC requirement is clarity, not field sprawl.

## Readiness and Governance Requirements

`local_openai_compatible` should be treated as a governed live mode.

That means it must still respect:

1. caller policy allowlists,
2. task allowlists,
3. rollout posture,
4. safety-mode enforcement,
5. timeout and degradation policy,
6. audit persistence.

It should differ from `openai` only where operationally necessary, especially:

1. spend budgeting may be irrelevant or reduced,
2. quota posture may be local-capacity based rather than vendor-billing based,
3. readiness checks should validate local endpoint reachability and model availability,
4. documentation should reflect whether the local provider is workstation-scoped or shared-service
   scoped.

## Design Pattern

The right implementation pattern is:

1. one provider gateway,
2. one shared OpenAI-compatible transport layer,
3. thin provider-mode adapters,
4. explicit runtime posture mapping,
5. explicit operator profiles,
6. no task-specific branching in downstream callers.

This is preferable to:

1. separate OpenAI and Ollama codepaths with duplicated request handling,
2. environment-specific hardcoding in Gateway or Workbench,
3. local-only shortcuts that bypass audit and policy seams.

In practical terms, the first refactor should move toward:

1. `OpenAICompatibleTextTransport`
2. `OpenAIManagedTextProvider`
3. `LocalOpenAICompatibleTextProvider`

The same pattern may later be applied to embeddings, but embeddings are out of scope for this RFC.

## Delivery Slices

### Slice 1: Provider Abstraction Normalization

Outcome:

1. split current live text execution into a reusable OpenAI-compatible transport plus mode-specific
   adapters,
2. add `local_openai_compatible` as a recognized provider mode,
3. preserve current `openai` behavior without regression.

Acceptance gate:

1. all current OpenAI provider tests still pass,
2. no downstream API contract changes are required,
3. provider registry and task execution path remain the single routing seam.

### Slice 2: Local OpenAI-Compatible Runtime Support

Outcome:

1. `lotus-ai` can execute `explain.v1` against a local OpenAI-compatible endpoint,
2. audit captures the new provider mode cleanly,
3. readiness surfaces report local provider posture accurately.

Acceptance gate:

1. deterministic contract tests pass against a mocked local endpoint,
2. runtime status exposes `provider_mode=local_openai_compatible`,
3. no unsupported-mode regressions appear in gateway or caller-policy enforcement.

### Slice 3: Operator Switching and Runbooks

Outcome:

1. operators can switch between `disabled`, `openai`, and `local_openai_compatible` with
   documented configuration changes,
2. developer-local setup is documented for Ollama,
3. stronger-host setup is documented for vLLM.

Acceptance gate:

1. one documented local quickstart works end to end,
2. the integration guide documents both billing-off and local-live flows,
3. supportability guidance is explicit about how to verify the active provider path.

### Slice 4: Evaluation and Operational Hardening

Outcome:

1. provider tests prove behavior parity across stub, remote, and local paths,
2. latency and failure mapping are explicitly tested,
3. readiness and incident evidence are sufficient for operations review.

Acceptance gate:

1. contract tests cover local success, timeout, malformed response, and unavailable model cases,
2. provider evidence and task audit remain coherent across modes,
3. no ambiguous silent fallback remains in the runtime path.

### Slice 5: Downstream Adoption Validation

Outcome:

1. `lotus-gateway` Advisor Brief generation is verified against both remote and local provider
   modes,
2. `lotus-workbench` remains unchanged at the contract level,
3. cross-repo runbooks document how to validate which provider authored the brief.
4. low-quality local advisor-brief generations are bounded by deterministic source-grounded
   fallback rather than leaking prompt or contract text into downstream UI.

Acceptance gate:

1. Gateway integration tests pass without contract drift,
2. Workbench UI continues to render the same bounded evidence-backed brief contract,
3. local and remote provider runs are distinguishable in support evidence,
4. malformed or contract-echo local outputs do not reach downstream callers as visible brief
   text.

## Testing Requirements

This RFC should not be implemented with superficial "mode switched" tests.

The test bar must include:

1. provider registry resolution tests,
2. task execution path tests for the new provider mode,
3. provider transport tests covering OpenAI-compatible response handling,
4. malformed JSON and partial JSON output handling for structured Advisor Brief responses,
5. readiness and platform status tests,
6. gateway integration tests proving no downstream contract drift,
7. documentation-backed smoke validation against a real local model server in at least one
   supported setup.

## Risks

1. If local-provider support is added as a provider-specific shortcut, the platform will regress
   into duplicated routing logic.
2. If local and remote execution share transport but not explicit audit metadata, supportability
   will degrade.
3. If we silently fall back between local and remote providers, the resulting narratives will be
   difficult to trust operationally.
4. If we introduce a second redundant configuration namespace, switching will become harder rather
   than easier.
5. If the local model path is treated as exempt from safety and governance because it is "local,"
   the platform contract will become internally inconsistent.

## Success Criteria

This RFC is successful when:

1. `lotus-ai` can run the same bounded task contract against stub, remote, and local live text
   providers,
2. `lotus-gateway` and `lotus-workbench` do not need provider-specific code,
3. operators can switch provider backends intentionally and verify the active mode through runtime
   status and audit evidence,
4. local model adoption improves cost control and deployment flexibility without weakening trust,
5. the codebase becomes more modular by sharing one OpenAI-compatible transport seam instead of
   accumulating special-case provider paths.
