# Integrations

## Integration Model

`lotus-ai` is consumed through governed task and platform contracts.

The rule that matters most is:

1. the calling application owns the business context,
2. `lotus-ai` executes bounded AI behavior against that context,
3. the calling system remains accountable for business meaning and user-facing consequences.

## Primary Executable Contracts

The main executable contracts are:

1. `POST /ai/tasks/execute`
2. `GET /ai/audit`
3. `GET /ai/audit/{request_id}`

These three routes cover the real minimum integration loop:

1. submit one bounded task request,
2. receive a structured result plus audit and evidence metadata,
3. inspect the persisted audit trail when support or governance review is required.

The task execution contract itself requires:

1. `task_id`
2. `input_mode`
3. `caller`
4. `context`

The response returns:

1. execution status,
2. task category and output label,
3. result payload,
4. audit metadata,
5. structured execution evidence.

That audit and evidence shape is part of the real integration contract and should be preserved by
downstream systems.

## Direct Task API Versus Task-Runtime Inspection

Do not confuse the direct execution route with the task-runtime inspection surface.

These are different:

1. direct execution
   - `POST /ai/tasks/execute`
2. task-runtime inspection
   - `/platform/tasks/runtime-status`
   - `/platform/tasks/execution-summary`
   - `/platform/tasks/evidence-summary`
   - `/platform/tasks/retrieval-summary`
3. capability discovery
   - `/platform/capabilities`

Downstream systems should call the direct execution route for work, and use the task-runtime and
capability surfaces for onboarding, support review, and rollout decisions.

## Platform Discovery Contracts

Before integrating deeply, downstream teams should inspect the platform surfaces rather than infer
capability from one successful task response.

The most important discovery endpoints are:

1. `/platform/runtime-status`
2. `/platform/capabilities`
3. `/platform/providers`
4. `/platform/providers/policy`
5. `/platform/providers/operator-profile`
6. `/platform/providers/operations-status`
7. `/platform/prompts/runtime-status`
8. `/platform/safety/policy`
9. `/platform/retrieval/runtime-status`
10. `/platform/evals/runtime-status`

For more rollout-sensitive integrations, also inspect:

1. `/platform/tasks/runtime-status`
2. `/platform/access-control/caller-policies`
3. `/platform/capability-packs`
4. `/platform/workflow-packs/registry`
5. `/platform/use-cases/first-production-use-case`
6. `/platform/app-capability-rollouts`

## Gateway-First Rule

For product flows, the browser should normally call `lotus-gateway`, not `lotus-ai` directly.

The intended pattern is:

1. the browser calls `lotus-gateway`,
2. `lotus-gateway` assembles the governed fact bundle,
3. `lotus-gateway` invokes `lotus-ai`,
4. downstream UI preserves audit and evidence metadata from the result.

This keeps business context assembly and product ownership in the correct Lotus layer.

Direct service-to-service callers can integrate with `lotus-ai` directly, but they should still
follow the same ownership boundary:

1. the caller owns the business fact bundle,
2. `lotus-ai` owns bounded AI execution and evidence assembly,
3. the caller owns the business decision made from the result.

## Retrieval-Backed Integrations

Retrieval-backed tasks are special because they expose more than a plain text response.

`knowledge_search.v1` and `knowledge_answer.v1` can carry:

1. bounded retrieval hits,
2. citations,
3. support or refusal posture,
4. retrieval execution details such as catalog fallback versus live indexed retrieval.

Downstream systems should preserve those distinctions instead of flattening them into one generic
answer string.

They should also inspect retrieval posture directly when retrieval-backed behavior matters:

1. `/platform/retrieval/runtime-status`
2. `/platform/retrieval/execution-status`
3. `/platform/retrieval/source-governance`
4. `/platform/retrieval/document-governance`
5. `/platform/retrieval/search`

## Downstream Adoption Surfaces

`lotus-ai` also exposes higher-level adoption surfaces:

1. `/platform/capability-packs`
2. `/platform/workflow-packs/registry`
3. `/platform/use-cases/first-production-use-case`
4. `/platform/use-cases/onboarding-template`
5. `/platform/app-capability-rollouts`

These are useful when the integration work is about productized downstream rollout rather than only
calling one task endpoint.

The practical sequence for a new downstream adoption is:

1. inspect `/platform/capability-packs`
2. inspect the selected pack detail and adoption template
3. inspect `/platform/workflow-packs/registry` when the pack is intended to become a workflow-bearing runtime family
4. inspect `/platform/use-cases/onboarding-template`
5. inspect `/platform/use-cases/first-production-use-case`
6. inspect `/platform/app-capability-rollouts`

That sequence keeps app-facing productization separate from low-level task execution.

## Provider and Safety Expectations

Callers must not assume that one successful response means unrestricted live-provider or safety
posture.

When the integration depends on live generation rather than deterministic stub behavior, inspect:

1. `/platform/providers`
2. `/platform/providers/policy`
3. `/platform/providers/operator-profile`
4. `/platform/providers/operations-status`

When the integration depends on blocked, redacted, or label-sensitive output handling, inspect:

1. `/platform/safety/policy`
2. `/platform/safety/runtime-status`
3. `/platform/safety/evidence-readiness`
4. `/platform/safety/governance-status`

## Integration Sources

- `docs/guides/integration-guide.md`
- `docs/guides/task-execution-contract.md`
- `docs/guides/prompt-registry-and-audit.md`
- `docs/guides/retrieval-and-vector-store.md`
- `docs/guides/lotus-performance-first-use-case.md`
- `demo/lotus-performance-first-use-case/README.md`

## Read Next

1. use [Platform Surfaces](./Platform-Surfaces.md) for the grouped public route map,
2. use [Security and Governance](./Security-and-Governance.md) for the boundary rules that constrain integrations,
3. use [Troubleshooting](./Troubleshooting.md) when a runtime mode or provider path is not behaving as expected.
