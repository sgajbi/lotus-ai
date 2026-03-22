# Decision Log

This file records the core architectural decisions for `lotus-ai` in a concise format.

## Decision 1: Separate AI Platform Service

Decision:

`lotus-ai` is a separate Lotus application rather than embedding all AI capability directly into every Lotus repo.

Why:

1. central prompt and safety governance,
2. shared auditability,
3. reusable retrieval and evaluation tooling,
4. lower duplication across apps.

Trade-off:

Requires careful ownership discipline so the service does not absorb business logic.

## Decision 2: Domain Apps Keep Business Ownership

Decision:

Each Lotus app keeps ownership of the business meaning of AI features that touch its workflows.

Why:

1. domain services understand their own semantics,
2. deterministic systems remain authoritative,
3. AI remains assistive rather than authoritative.

## Decision 3: Build Contract-First

Decision:

Introduce capability and task contracts before real provider integrations.

Why:

1. easier integration with downstream apps,
2. clearer versioning and testing,
3. avoids provider-driven architecture drift.

## Decision 4: Start With Explanation and Retrieval

Decision:

Initial business-facing AI value should come from explanation, summarization, retrieval, and drafting.

Why:

1. lower risk,
2. high user value,
3. fits well with Lotus deterministic services,
4. easier to govern in a banking context.

## Decision 5: Enterprise-Grade Controls, Startup-Grade Scope

Decision:

Use bank-grade engineering controls, but keep the actual feature scope narrow and incremental.

Why:

1. target customers require strong governance,
2. startup constraints require disciplined sequencing rather than big-bang builds.

## Decision 6: No Large AI Framework as the Core Architecture

Decision:

Do not make a large AI framework the primary architectural foundation of `lotus-ai`.

Why:

1. we need explicit control over contracts, safety, auditability, and request flow,
2. framework abstractions can hide important behavior,
3. bank-grade platform services need clarity over convenience,
4. our current use cases do not justify an agent-first architecture.

Allowed use:

Frameworks or helper libraries may be used in narrow internal roles where they reduce plumbing without taking over the service design.

## Decision 7: LangGraph Is Deferred, Not Rejected

Decision:

LangGraph is deferred from the initial implementation of `lotus-ai`.

Why:

1. early `lotus-ai` slices are contract-first and explanation-first,
2. graph orchestration is not yet the main bottleneck,
3. we should first prove the need for multi-step agent workflows with real usage evidence.

Future position:

LangGraph can be reconsidered for bounded internal orchestration later, especially for async multi-step flows, but it should remain an implementation detail rather than the public platform architecture.

## Decision 8: Startup and Readiness Policies Are Separate Controls

Decision:

`lotus-ai` treats startup blocking policy and readiness-probe degradation policy as separate operational controls.

Why:

1. some environments need visibility without startup failure,
2. enterprise environments need stricter rollout behavior,
3. orchestration signaling and startup permissiveness solve different problems,
4. separating them keeps policy explicit instead of embedding assumptions in one switch.

Current target posture:

1. local development: `warn` + `observe`
2. shared integration: `warn` + `degrade`
3. enterprise / production-like: `enforce` + `degrade`

## Decision 9: Prompt Promotion Is Read-Only at Runtime

Decision:

Prompt definitions in `lotus-ai` are inspectable through APIs, but runtime mutation and promotion remain disabled.

Why:

1. prompt changes are platform-governed behavior changes and must stay reviewable,
2. bank-grade environments need provenance and controlled rollout for prompt changes,
3. repository-reviewed changes plus Alembic-managed persistence keep promotion traceable without adding unsafe runtime write paths too early.

Current posture:

1. prompt definitions expose lifecycle and provenance metadata,
2. SQL-backed prompt definitions are promoted through migrations,
3. runtime prompt write APIs remain disabled until a stronger approval and rollout model exists.

## Decision 10: Provider Gateway Before Live Models

Decision:

`lotus-ai` routes task execution through an explicit provider gateway before any live model SDK is enabled.

Why:

1. provider selection needs its own typed boundary instead of being hidden inside task orchestration,
2. we want to prove audit and policy flow through a stable execution seam before introducing real providers,
3. this keeps the public task API stable while letting provider internals evolve safely.

Current posture:

1. the gateway currently routes only to deterministic stub providers,
2. provider inventory is visible through the provider catalog,
3. live model execution remains disabled until safety, approval, and rollout controls mature.

## Decision 11: Provider Modes Must Fail Explicitly

Decision:

Unsupported provider modes must fail explicitly through a governed provider policy instead of falling
through silently.

Why:

1. enterprise operators need deterministic behavior when runtime configuration drifts,
2. silent fallback hides rollout mistakes and weakens auditability,
3. a policy layer lets us expand from `disabled` and `stub` toward future allowlisted live modes without reshaping task contracts.

Current posture:

1. provider policy is inspectable through `/platform/providers/policy`,
2. only `disabled` and `stub` modes are currently supported for text and embedding capabilities,
3. unsupported modes are rejected with a service-unavailable response.

## Decision 11A: Provider Activation Readiness Should Be Exposed Before Live Rollout

Decision:

`lotus-ai` exposes a dedicated provider activation-readiness view before any live provider execution is enabled.

Why:

1. provider rollout is a higher-level operational decision than catalog and policy inspection alone,
2. bank-grade activation review needs explicit blocking findings and activation path for provider execution,
3. this keeps live model enablement governed and reviewable before any runtime execution changes.

Current posture:

1. `/platform/providers/activation-readiness` exposes whether provider execution is activatable today,
2. the endpoint returns explicit blocking findings and a governed activation path,
3. foundation phase remains not activatable until a separate provider rollout slice changes execution posture.

## Decision 11B: Provider Runbook Readiness Should Be Exposed As A Separate Operational Contract

Decision:

`lotus-ai` exposes provider runbook readiness separately from provider technical activation readiness.

Why:

1. live-provider rollout needs operational preparedness that is distinct from provider configuration and policy posture,
2. bank-grade activation review should explicitly cover vendor escalation, rate-limit response, and observability readiness,
3. separating runbook readiness keeps provider activation governance explicit and auditable.

Current posture:

1. `/platform/providers/runbook-readiness` exposes required provider operational readiness items,
2. required runbook items remain not ready in foundation phase,
3. live-provider activation should not be considered complete in future rollout slices without both technical and runbook readiness.

## Decision 11C: Provider Governance Review Should Have A Single Summary Surface

Decision:

`lotus-ai` exposes a combined provider governance-status view for rollout review.

Why:

1. provider rollout review should not require operators to manually merge multiple endpoints to assess activation posture,
2. a bank-grade live-provider activation review needs both technical and operational provider posture in one governed response,
3. the summary endpoint reduces interpretation drift while preserving the more detailed provider readiness endpoints underneath.

Current posture:

1. `/platform/providers/governance-status` embeds both activation readiness and runbook readiness,
2. the response explicitly reports blocked provider governance posture in foundation phase,
3. detailed provider readiness endpoints remain available for deeper inspection and future rollout work.

## Decision 11D: Platform Runtime Status Should Embed Provider Governance Posture

Decision:

`/platform/runtime-status` now embeds provider governance posture in addition to the dedicated provider governance endpoint.

Why:

1. platform operators should have one primary runtime entry point that includes the top-level provider rollout posture,
2. provider governance is operationally significant once multiple provider readiness surfaces exist,
3. embedding the summary reduces endpoint hopping while preserving the dedicated provider governance endpoint.

Current posture:

1. platform runtime status includes `provider_governance`,
2. provider governance remains separately inspectable through `/platform/providers/governance-status`,
3. foundation phase continues to report blocked provider governance in both views.

## Decision 12: Safety Posture Must Be Inspectable

Decision:

`lotus-ai` exposes a read-only safety policy surface before introducing runtime redaction engines.

Why:

1. downstream teams need to know which controls are enforced versus documented,
2. bank-grade platform behavior should not rely on tribal knowledge,
3. task-level output-label and redaction posture should be visible before live model execution exists.

Current posture:

1. safety policy is inspectable through `/platform/safety/policy`,
2. response labeling and audit evidence are enforced controls,
3. redaction remains documented guidance at this phase rather than a runtime mutation engine.

## Decision 13: Safety Outcomes Belong In Audit Metadata

Decision:

Each task execution must persist the safety posture that applied to the run, not just expose safety policy separately.

Why:

1. audit consumers need execution-specific evidence instead of only a platform-wide policy view,
2. future safety rollout changes should remain traceable per request,
3. this creates a clean bridge from documented safety posture to future enforced runtime controls.

Current posture:

1. execution audit metadata now records `safety_mode`,
2. task-specific `redaction_posture` is persisted per run,
3. enforced safety-control identifiers are stored with each audit record.

## Decision 14: Runtime Safety Status Should Be Observable

Decision:

`lotus-ai` exposes a dedicated runtime safety status surface in addition to policy and audit metadata.

Why:

1. operators need a quick operational view without inspecting individual audit records,
2. platform runtime status should summarize safety posture just like persistence posture,
3. it creates a clean place to surface future runtime redaction or policy-engine activation.

Current posture:

1. runtime safety status is inspectable through `/platform/safety/runtime-status`,
2. platform runtime status now embeds a safety runtime summary,
3. runtime redaction remains inactive in the foundation phase.

## Decision 15: Retrieval Needs Its Own Execution Gateway

Decision:

Retrieval search now flows through an explicit execution gateway before any live vector search backend is introduced.

Why:

1. search execution needs a clean boundary separate from catalog and indexing metadata,
2. this lets us make disabled-versus-enabled retrieval behavior explicit and testable,
3. future live retrieval backends can be introduced behind the same seam without changing the public retrieval API.

Current posture:

1. retrieval execution is inspectable through `/platform/retrieval/execution-status`,
2. the gateway rejects live retrieval execution while the platform remains in staged retrieval mode,
3. catalog, indexing, and execution status are now separate but coordinated surfaces.

## Decision 15A: Retrieval Activation Readiness Should Be Exposed Before Live Search Rollout

Decision:

`lotus-ai` exposes a dedicated retrieval activation-readiness view before any live retrieval execution is enabled.

Why:

1. retrieval rollout is a higher-level operational decision than execution-status inspection alone,
2. bank-grade activation review needs explicit blocking findings and activation path for live search and indexing,
3. this keeps retrieval activation governed and reviewable before any runtime execution changes.

Current posture:

1. `/platform/retrieval/activation-readiness` exposes whether retrieval execution is activatable today,
2. the endpoint returns explicit blocking findings and a governed activation path,
3. foundation phase remains not activatable until a separate retrieval rollout slice changes execution posture.

## Decision 15B: Retrieval Runbook Readiness Should Be Exposed As A Separate Operational Contract

Decision:

`lotus-ai` exposes retrieval runbook readiness separately from retrieval technical activation readiness.

Why:

1. live retrieval rollout needs operational preparedness that is distinct from retrieval execution posture,
2. bank-grade activation review should explicitly cover reindex, replay, and retrieval observability readiness,
3. separating runbook readiness keeps retrieval activation governance explicit and auditable.

Current posture:

1. `/platform/retrieval/runbook-readiness` exposes required retrieval operational readiness items,
2. required runbook items remain not ready in foundation phase,
3. live retrieval activation should not be considered complete in future rollout slices without both technical and runbook readiness.

## Decision 15C: Retrieval Governance Review Should Have A Single Summary Surface

Decision:

`lotus-ai` exposes a combined retrieval governance-status view for rollout review.

Why:

1. retrieval rollout review should not require operators to manually merge multiple endpoints to assess activation posture,
2. a bank-grade live-retrieval activation review needs both technical and operational retrieval posture in one governed response,
3. the summary endpoint reduces interpretation drift while preserving the more detailed retrieval readiness endpoints underneath.

Current posture:

1. `/platform/retrieval/governance-status` embeds both activation readiness and runbook readiness,
2. the response explicitly reports blocked retrieval governance posture in foundation phase,
3. detailed retrieval readiness endpoints remain available for deeper inspection and future rollout work.

## Decision 15D: Platform Runtime Status Should Embed Retrieval Governance Posture

Decision:

`/platform/runtime-status` now embeds retrieval governance posture in addition to the dedicated retrieval governance endpoint.

Why:

1. platform operators should have one primary runtime entry point that includes the top-level retrieval rollout posture,
2. retrieval governance is operationally significant once multiple retrieval readiness surfaces exist,
3. embedding the summary reduces endpoint hopping while preserving the dedicated retrieval governance endpoint.

Current posture:

1. platform runtime status includes `retrieval_governance`,
2. retrieval governance remains separately inspectable through `/platform/retrieval/governance-status`,
3. foundation phase continues to report blocked retrieval governance in both views.

## Decision 16: Prompt Runtime Selection Should Be Inspectable

Decision:

`lotus-ai` exposes prompt runtime selection status separately from prompt definition and governance views.

Why:

1. operators and downstream teams need to know which prompt version is actually active per task,
2. rollout state should be inspectable even before a write-based promotion workflow exists,
3. this gives us a stable runtime-selection surface before future prompt promotion or rollback mechanics are introduced.

Current posture:

1. prompt runtime selection is inspectable through `/platform/prompts/runtime-status`,
2. the current selection mode is static active-prompt selection,
3. runtime promotion remains read-only and repository-governed.

## Decision 17: Platform Runtime Status Should Summarize Prompt Runtime

Decision:

`/platform/runtime-status` now embeds prompt runtime status instead of leaving prompt rollout posture on a separate island.

Why:

1. operators need one primary runtime dashboard for the service,
2. prompt runtime selection is operationally important once multiple governance surfaces exist,
3. embedding the summary reduces the number of calls required for routine checks while preserving the dedicated prompt endpoint.

Current posture:

1. platform runtime status includes prompt runtime selection summary,
2. dedicated prompt runtime status remains available for focused inspection,
3. the embedded view remains read-only and aligned with the prompt governance model.

## Decision 17A: Prompt Activation Readiness Should Be Exposed Before Live Prompt Rollout

Decision:

`lotus-ai` exposes a dedicated prompt activation-readiness view before any live prompt promotion path is enabled.

Why:

1. prompt rollout is a higher-level operational decision than prompt definition and runtime-selection inspection alone,
2. bank-grade prompt activation review needs explicit blocking findings and activation path for live rollout changes,
3. this keeps prompt promotion governed and reviewable before any runtime write path is introduced.

Current posture:

1. `/platform/prompts/activation-readiness` exposes whether prompt rollout is activatable today,
2. the endpoint returns explicit blocking findings and a governed activation path,
3. foundation phase remains not activatable until a separate prompt rollout slice changes promotion posture.

## Decision 17B: Prompt Runbook Readiness Should Be Exposed As A Separate Operational Contract

Decision:

`lotus-ai` exposes prompt runbook readiness separately from prompt technical activation readiness.

Why:

1. live prompt rollout needs operational preparedness that is distinct from prompt definition and runtime-selection posture,
2. bank-grade prompt activation review should explicitly cover change approval, rollback, and audit-evidence support procedures,
3. separating runbook readiness keeps prompt rollout governance explicit and auditable.

Current posture:

1. `/platform/prompts/runbook-readiness` exposes required prompt operational readiness items,
2. required runbook items remain not ready in foundation phase,
3. live prompt activation should not be considered complete in future rollout slices without both technical and runbook readiness.

## Decision 17C: Prompt Governance Review Should Have A Single Summary Surface

Decision:

`lotus-ai` exposes a combined prompt governance-status view for rollout review.

Why:

1. prompt rollout review should not require operators to manually merge multiple endpoints to assess activation posture,
2. a bank-grade live-prompt activation review needs both technical and operational prompt posture in one governed response,
3. the summary endpoint reduces interpretation drift while preserving the more detailed prompt readiness endpoints underneath.

Current posture:

1. `/platform/prompts/governance-status` embeds both activation readiness and runbook readiness,
2. the response explicitly reports blocked prompt governance posture in foundation phase,
3. detailed prompt readiness endpoints remain available for deeper inspection and future rollout work.

## Decision 17D: Platform Runtime Status Should Embed Prompt Governance Posture

Decision:

`/platform/runtime-status` now embeds prompt governance posture in addition to the dedicated prompt governance endpoint.

Why:

1. platform operators should have one primary runtime entry point that includes the top-level prompt rollout posture,
2. prompt governance is operationally significant once multiple prompt readiness surfaces exist,
3. embedding the summary reduces endpoint hopping while preserving the dedicated prompt governance endpoint.

Current posture:

1. platform runtime status includes `prompt_governance`,
2. prompt governance remains separately inspectable through `/platform/prompts/governance-status`,
3. foundation phase continues to report blocked prompt governance in both views.

## Decision 17E: Prompt Evidence Readiness Should Be Exposed Before Live Prompt Rollout

Decision:

`lotus-ai` exposes prompt evidence readiness separately from prompt technical and operational readiness.

Why:

1. bank-grade prompt activation review should require explicit evaluation, audit, and rollback evidence rather than assuming those concerns are covered by technical or runbook posture alone,
2. prompt rollout needs a stable evidence contract before any live promotion path is introduced,
3. separating evidence readiness keeps future prompt activation criteria inspectable and auditable.

Current posture:

1. `/platform/prompts/evidence-readiness` exposes required prompt evidence items,
2. required evidence items remain not ready in foundation phase,
3. prompt governance review can now inspect evidence posture separately while the combined governance summary remains unchanged in this slice.

## Decision 18: Task Runs Should Emit Structured Execution Evidence

Decision:

Task execution responses now include a typed execution evidence bundle describing the main decision inputs used for the run.

Why:

1. enterprise review needs more than a raw message and audit id,
2. a stable evidence schema gives later evaluation work a clean foundation,
3. this improves explainability without changing the deterministic execution posture.

Current posture:

1. task responses emit evidence for task contract, prompt selection, provider resolution, safety outcome, and retrieval posture,
2. evidence is deterministic and read-only in foundation phase,
3. live provider behavior is still disabled; the evidence model exists ahead of it.

## Decision 19: Evaluation Readiness Should Be Discoverable

Decision:

`lotus-ai` exposes a read-only evaluation catalog so teams can inspect execution evidence categories and staged fixture families directly from the service.

Why:

1. evaluation posture should be visible as a platform capability, not buried only in docs,
2. regression and governance workflows need a stable surface to target,
3. this prepares the service for future fixture manifests and evaluation APIs without overbuilding them now.

Current posture:

1. evaluation readiness is inspectable through `/platform/evals/catalog`,
2. evidence categories mirror the deterministic execution evidence bundle,
3. fixture families are staged and documented before a fuller evaluation runner exists.

## Decision 20: Platform Runtime Status Should Summarize Evaluation Posture

Decision:

`/platform/runtime-status` now embeds evaluation runtime posture in addition to the dedicated evaluation endpoints.

Why:

1. evaluation readiness is part of operational platform posture, not just developer documentation,
2. operators should not need multiple endpoint hops for routine readiness checks,
3. this keeps evaluation aligned with the same runtime-summary pattern already used for prompt and safety posture.

Current posture:

1. evaluation runtime status is available through `/platform/evals/runtime-status`,
2. platform runtime status embeds the same evaluation summary,
3. the evaluation runner remains inactive in the foundation phase.

## Decision 21: Evaluation Inventory Should Live In A Versioned Manifest

Decision:

Evaluation fixture families and evidence-category inventory are now sourced from a versioned in-repo manifest.

Why:

1. evaluation readiness should be backed by a governed artifact, not only service code,
2. a manifest creates a stable bridge to future fixture files and evaluation runners,
3. runtime and catalog surfaces can now report manifest version as part of the operational contract.

Current posture:

1. the evaluation manifest lives under `docs/evals/fixture-manifest.json`,
2. evaluation catalog and runtime status are sourced from that manifest,
3. the manifest remains read-only and repository-governed in the foundation phase.

## Decision 22: At Least One Evaluation Family Should Be File-Backed Early

Decision:

The first real staged evaluation family is now backed by fixture files for `explain.v1`.

Why:

1. a manifest alone does not prove the asset shape we want future evaluation tooling to consume,
2. one concrete family lets us validate file format, counting, and runtime inventory behavior early,
3. it creates a practical template for later summarization, retrieval, and domain-specific fixture families.

Current posture:

1. `explanation_task_examples` is now staged with a backing fixture file,
2. evaluation catalog reports manifest path and case count per family,
3. evaluation runtime status reports total staged case count.

## Decision 23: Core Task Families Should Gain File-Backed Fixtures Early

Decision:

Summarization joins explanation as an early file-backed evaluation family in foundation phase.

Why:

1. explanation alone is not enough to validate that multiple task families can share the same governed fixture shape,
2. summarization is one of the first public task contracts and should have real staged artifacts before provider rollout begins,
3. this keeps evaluation posture aligned with the actual task surface rather than trailing behind it.

Current posture:

1. `summarization_task_examples` is now staged with a backing fixture file,
2. evaluation runtime status counts staged cases across both explanation and summarization,
3. retrieval and citation fixture families remain documented until retrieval execution is activated.

## Decision 24: Evaluation Fixture Inventory Must Be Enforced By A Gate

Decision:

The evaluation fixture manifest is now a validated repository contract, not just a convention consumed by runtime code.

Why:

1. file-backed evaluation assets are becoming part of the platform's governed surface area,
2. malformed fixture files or broken manifest references should fail fast in CI before they affect runtime inspection surfaces,
3. one shared validator keeps loader behavior, local checks, and CI enforcement aligned.

Current posture:

1. `make eval-manifest-gate` validates the manifest and referenced fixture files,
2. CI now runs the evaluation manifest gate alongside OpenAPI and migration checks,
3. runtime manifest loading uses the same validation rules as the CLI gate.

## Decision 25: Retrieval Evaluation Should Be Staged Before Live Search

Decision:

Retrieval citation and refusal fixtures are staged before live retrieval execution is enabled.

Why:

1. provenance and refusal behavior are core governance concerns for retrieval and should be specified before vector search turns on,
2. staged fixtures let us define expected citation posture even while search remains intentionally disabled,
3. this keeps retrieval activation aligned with the same evidence-first rollout model used for prompts, safety, and task execution.

Current posture:

1. `retrieval_citation_examples` is now backed by a fixture file,
2. evaluation runtime status counts retrieval cases alongside explanation and summarization cases,
3. live retrieval execution remains disabled until the retrieval gateway is explicitly activated.

## Decision 26: Evaluation Fixtures Should Be Inspectable By Family

Decision:

`lotus-ai` exposes read-only detail for a single evaluation fixture family instead of limiting evaluation inspection to aggregate catalog views.

Why:

1. downstream teams and QA workflows often need to target one governed fixture family at a time,
2. case-level metadata should be discoverable without requiring direct repository file access,
3. read-only fixture detail improves inspectability without exposing mutable evaluation execution behavior.

Current posture:

1. `GET /platform/evals/fixtures/{fixture_id}` returns fixture descriptor, task association, and case-level metadata,
2. the endpoint intentionally excludes raw mutable execution payloads,
3. fixture inventory remains repository-governed and manifest-validated.

## Decision 27: Provider Policy Should Be Covered By Evaluation Fixtures Before Live Provider Rollout

Decision:

Provider-policy behavior is staged as a governed evaluation family before any live provider SDK is enabled.

Why:

1. provider selection and disabled-execution behavior are core control points that should be specified before rollout,
2. fixture-backed expectations keep stub and disabled modes explicit and reviewable,
3. this extends the same evidence-first discipline already applied to tasks and retrieval into provider governance.

Current posture:

1. `provider_policy_examples` is now backed by a fixture file,
2. evaluation runtime status counts provider-policy cases alongside task and retrieval cases,
3. live provider execution remains disabled until a separate governed activation slice exists.

## Decision 28: Safety Policy Should Be Covered By Evaluation Fixtures Before Runtime Redaction Exists

Decision:

Safety policy and runtime safety posture are staged as governed evaluation fixtures before any runtime redaction engine is introduced.

Why:

1. safety semantics are already part of the public platform contract and should be regression-tested as such,
2. enforced-versus-documented control separation is a core governance promise in foundation phase,
3. fixture-backed expectations let us evolve safety implementation later without losing the documented operational posture.

Current posture:

1. `safety_policy_examples` is now backed by a fixture file,
2. evaluation runtime status counts safety-policy cases alongside task, retrieval, and provider-policy cases,
3. runtime redaction remains documented-only until a later governed activation slice.

## Decision 29: The Initial Evaluation Inventory Should Be Fully File-Backed

Decision:

The remaining task-capability contract family is staged so the initial evaluation inventory is fully backed by governed fixture files.

Why:

1. leaving one documented-only family weakens the promise that current evaluation posture is artifact-backed,
2. task enablement and output-label contracts are part of the service surface and deserve the same governed treatment as the other seams,
3. fully staged inventory gives later evaluation tooling a clean, uniform substrate.

Current posture:

1. `task_capability_contracts` is now backed by a fixture file,
2. the initial evaluation manifest no longer has documented-only families,
3. every current fixture family is discoverable, validated, and file-backed.

## Decision 30: Evaluation Runtime Should Summarize Coverage By Platform Seam

Decision:

Evaluation runtime status now reports staged coverage by major lotus-ai platform seam rather than only aggregate totals.

Why:

1. operators and reviewers need a faster way to see which governed boundaries are actually covered,
2. seam-oriented summaries are more actionable than raw fixture counts once the inventory grows,
3. this improves runtime inspectability without introducing mutable evaluation behavior.

Current posture:

1. evaluation runtime status summarizes staged coverage for task execution, retrieval, provider policy, and safety policy,
2. platform runtime status inherits the same seam summary through the embedded evaluation runtime contract,
3. fixture-family detail remains available for deeper inspection.

## Decision 31: Evaluation Run Artifacts Should Exist Before A Live Runner

Decision:

`lotus-ai` exposes governed, read-only evaluation run artifacts before introducing live evaluation execution.

Why:

1. the platform needs a durable artifact shape for recorded evaluation outcomes before a mutable runner exists,
2. artifact inspection helps reviewers reason about baseline evaluation posture without conflating it with execution infrastructure,
3. this creates a stable bridge from fixture inventory to future persisted evaluation runs.

Current posture:

1. `/platform/evals/runs` and `/platform/evals/runs/{run_id}` expose recorded evaluation artifacts,
2. evaluation runtime status now reports recorded run count and latest run identifiers,
3. live evaluation execution remains inactive and separate from artifact inspection.

## Decision 32: Evaluation Run Artifacts Must Be Validated By A Dedicated Gate

Decision:

Recorded evaluation run artifacts are governed by a dedicated validation gate, not just runtime parsing.

Why:

1. recorded evaluation artifacts are part of the platform’s inspection contract and should fail fast when malformed,
2. artifact drift against the fixture manifest would weaken traceability,
3. one shared validation path keeps CLI checks, CI enforcement, and runtime loading consistent.

Current posture:

1. `make eval-run-gate` validates `docs/evals/run-artifacts.json`,
2. CI runs the evaluation run gate alongside the fixture-manifest gate,
3. runtime loading uses the same validation rules as the dedicated gate.

## Decision 33: Evaluation Run Lifecycle Should Include Superseded History

Decision:

The seeded evaluation run registry now includes both current and superseded artifacts.

Why:

1. enterprise auditability benefits from showing history, not just the latest baseline snapshot,
2. lifecycle-aware artifacts let us exercise the contract before a live runner introduces real history,
3. this keeps the registry realistic without adding mutable execution behavior.

Current posture:

1. the latest run remains `RECORDED`,
2. an older run is exposed as `SUPERSEDED`,
3. run catalogs now summarize artifacts by lifecycle status.

## Decision 34: Scalability Must Be Designed In As A First-Class Platform Constraint

Decision:

`lotus-ai` must scale as a stateless platform API plus independently scalable background workers around governed durable stores.

Why:

1. bank-grade platform services cannot depend on in-process state for production correctness,
2. the main scaling pressure will come from external providers, retrieval/indexing work, and shared-service noisy-neighbor effects,
3. clean internal seams keep the path open for future deployment splits without forcing external contract rewrites.

Current posture:

1. the canonical scalability document is `docs/architecture/scalability-and-deployment-model.md`,
2. API-serving components are expected to remain stateless,
3. long-running and high-latency work is expected to move through worker-style execution paths,
4. provider gateway, retrieval, evaluation, safety, prompt governance, and audit/supportability must remain separable subdomains.

## Decision 35: Async Runtime Should Be Exposed Before Live Queue Execution

Decision:

`lotus-ai` exposes a read-only async runtime contract before queue-backed execution is activated.

Why:

1. the scaling architecture should be visible in service contracts before heavy background execution arrives,
2. callers and operators need to know that async job types exist even when they are not yet enabled,
3. this creates a stable seam for future worker rollout without overcommitting to a queue implementation too early.

Current posture:

1. `/platform/async/runtime-status` exposes queue mode, worker mode, and known async job types,
2. platform runtime status embeds the async runtime summary,
3. async execution remains disabled in the foundation phase while the contract is now explicit.

## Decision 36: Async Job Artifacts Should Be Inspectable Before Live Queue Execution

Decision:

`lotus-ai` exposes seeded, read-only async job artifacts before any real worker queue is enabled.

Why:

1. operators and engineers need an explicit artifact model for future background work,
2. async history and queue posture should be inspectable before they become mutable operational state,
3. this mirrors the artifact-first pattern already used for evaluation history and keeps async rollout disciplined.

Current posture:

1. `/platform/async/jobs` and `/platform/async/jobs/{job_id}` expose seeded async job artifacts,
2. async runtime status now reports queued and recorded job counts,
3. async job artifacts are validated by a dedicated gate before being exposed through the API.

## Decision 37: Async Submission Should Be Contract-First And Explicitly Rejected Before Activation

Decision:

`lotus-ai` exposes an async job submission contract before live queue execution is enabled, and supported submissions return explicit rejected responses during foundation phase.

Why:

1. callers should be able to integrate to the future submission surface before workers are activated,
2. explicit rejected responses are more useful than missing endpoints or undocumented refusal behavior,
3. this keeps the path from synchronous to async execution governed and testable.

Current posture:

1. `/platform/async/jobs/submit` validates known job types,
2. supported job types return a typed `REJECTED` response while queue execution remains disabled,
3. unknown job types are rejected explicitly with a not-found response.

## Decision 38: Async Job Artifacts Should Link To Evaluation History When Relevant

Decision:

Async job artifacts can carry typed references to related evaluation run artifacts.

Why:

1. future worker-backed evaluation execution will need traceable linkage across async and evaluation seams,
2. seeded cross-references let us validate that relationship model before live workers exist,
3. this improves supportability without changing external business-facing contracts.

Current posture:

1. async job artifacts may include `related_evaluation_run_id`,
2. the async job registry validates related evaluation run references against the governed evaluation run registry,
3. evaluation-linked async history is now inspectable through the async job APIs.

## Decision 39: Queue Backend Strategy Should Be Inspectable Before Activation

Decision:

`lotus-ai` exposes a governed queue-backend catalog before any live async backend is turned on.

Why:

1. operators need to understand not only that async execution is disabled, but also which backend strategies are recognized by the platform,
2. queue-selection posture should be explicit and reviewable before rollout introduces mutable infrastructure state,
3. this keeps future Redis-style queue activation or event-stream integration behind a stable inspection surface.

Current posture:

1. `/platform/async/queue-backends` exposes the current foundation default and documented future backend options,
2. async runtime status now includes the supported queue backend descriptors,
3. the active backend remains `none` until a separate governed activation slice enables live queue execution.

## Decision 40: Worker Execution Strategy Should Be Inspectable Before Activation

Decision:

`lotus-ai` exposes a governed worker-execution catalog before any live worker runtime is turned on.

Why:

1. worker posture should be explicit independently from queue posture because queue selection and worker rollout are separate operational concerns,
2. bank-grade async architecture needs a clear line between API-serving nodes and future isolated worker execution paths,
3. this keeps worker rollout options reviewable without implying that any live background processing is already active.

Current posture:

1. `/platform/async/worker-executions` exposes the current foundation default and documented future worker options,
2. async runtime status now includes the supported worker execution descriptors,
3. the active worker execution remains `none` until a separate governed activation slice enables live workers.

## Decision 41: Async Activation Readiness Should Be Summarized Explicitly

Decision:

`lotus-ai` exposes a dedicated async activation-readiness view instead of expecting operators to infer readiness by manually combining queue, worker, and submission posture.

Why:

1. rollout readiness is a higher-level operational question than catalog inspection alone,
2. bank-grade services should expose blocking findings and activation path explicitly rather than relying on implicit interpretation,
3. this creates a stable operator-facing contract for future async rollout reviews.

Current posture:

1. `/platform/async/activation-readiness` exposes whether async execution is activatable today,
2. the endpoint returns explicit blocking findings and a governed activation path,
3. foundation phase remains not activatable until a separate rollout slice changes queue, worker, and job enablement posture together.

## Decision 42: Async Runbook Readiness Should Be Exposed As A Separate Operational Contract

Decision:

`lotus-ai` exposes async runbook readiness separately from technical activation readiness.

Why:

1. operational preparedness is a first-class bank-grade requirement, not an implied consequence of technical configuration,
2. queue and worker posture may be ready before on-call, replay, or observability procedures are ready,
3. separating runbook readiness keeps rollout governance explicit and auditable.

Current posture:

1. `/platform/async/runbook-readiness` exposes required operational readiness items,
2. required runbook items remain not ready in foundation phase,
3. async activation should not be considered complete in future rollout slices without both technical and runbook readiness.

## Decision 43: Async Governance Review Should Have A Single Summary Surface

Decision:

`lotus-ai` exposes a combined async governance-status view for rollout review.

Why:

1. governance review should not require operators to manually merge multiple endpoints in order to answer whether async rollout is currently supportable,
2. a bank-grade activation review needs both technical and operational posture in one governed response,
3. the summary endpoint reduces interpretation drift while preserving the more detailed readiness endpoints underneath.

Current posture:

1. `/platform/async/governance-status` embeds both activation readiness and runbook readiness,
2. the response explicitly reports blocked governance posture in foundation phase,
3. detailed readiness endpoints remain available for deeper inspection and future rollout work.

## Decision 44: Platform Runtime Status Should Embed Async Governance Posture

Decision:

`/platform/runtime-status` now embeds async governance posture in addition to async runtime posture.

Why:

1. platform operators should have one primary runtime entry point that includes both execution posture and rollout-governance posture,
2. async governance is operationally significant once multiple async readiness surfaces exist,
3. embedding the summary reduces endpoint hopping while preserving the dedicated async governance endpoint.

Current posture:

1. platform runtime status includes both `async_runtime` and `async_governance`,
2. async governance remains separately inspectable through `/platform/async/governance-status`,
3. foundation phase continues to report blocked async governance in both views.
