# Workflow-Pack Owner Onboarding

This guide is the practical follow-on to `RFC-0032`.

Use it when a Lotus repository wants to onboard a new workflow-pack family into `lotus-ai`
without turning the registry into a shadow copy of workflow logic.

## Core Rule

The owning repository still owns the workflow-bearing implementation.

`lotus-ai` owns only:

1. registration truth,
2. eligibility evaluation,
3. activation posture,
4. bounded operator controls,
5. control-plane inspection surfaces.

Do not move workflow definitions into `lotus-ai` just to make registration easier.

## Minimum Owner Artifacts

Every workflow-pack registration should point back to real owner artifacts.

At minimum, a truthful registration should include:

1. one primary contract artifact,
2. one owner service or router artifact,
3. one owner-repository regression test artifact,
4. optional supporting RFC or UI-validation artifacts when those help explain the product surface.

For `repo://` references:

1. `definition_ref` must point at the primary owner artifact,
2. `definition_refs` must enumerate the owner-artifact set explicitly,
3. at least one required reference must live in `owner_repository`,
4. supporting cross-repo references do not replace owner-repository truth.

## Recommended Onboarding Sequence

For each new workflow-pack family:

1. Define or confirm the workflow-pack identity in the owning repository.
2. Confirm which service boundary owns workflow authority.
3. Confirm which downstream services remain authoritative truth owners.
4. Collect the owner artifacts that justify the registration.
5. Add the registration record to `lotus-ai`.
6. Add eligibility coverage for the real caller, environment, tenant, and workflow-surface posture.
7. Add operator control-history and control-action coverage where activation posture matters.
8. Update docs, repository context, wiki source, RFC status, and PR evidence together.

## Owner Questions To Answer Before Registration

Do not register a workflow pack until these questions have clear answers:

1. What repository owns the workflow-bearing code?
2. What service boundary owns workflow authority?
3. Which Lotus services are allowed to provide domain truth to the pack?
4. What caller applications are allowed to request it?
5. What identity classes are allowed to request it?
6. Which environments are allowed to activate it?
7. Does tenant scope apply?
8. Does workflow-surface scope apply?
9. What is the initial rollout posture?
10. What is the safe pause, deprecate, or retire path?

If those answers are unclear, the registration is premature.

## Phase-1 Reference Example

The current Phase-1 reference family is `advisor_brief.pack`.

Why it is a useful reference:

1. the gateway composition layer owns the workflow-bearing advisor-brief contract and service,
2. the workbench RFC and validation artifacts exist as supporting evidence,
3. the runtime registry can describe ownership and rollout posture without pretending to own the workflow itself.

The current seeded registration demonstrates this split:

1. `owner_repository = lotus-gateway`
2. `owner_service = lotus-gateway`
3. `workflow_authority_owner = lotus-gateway`
4. `definition_ref` points at a gateway contract or service artifact,
5. `definition_refs` include owner-repo contract, service, router, and tests, plus optional workbench support artifacts.

## Registration Quality Checks

Before treating a workflow-pack registration as real:

1. verify the `owner_repository` is truthful,
2. verify the `definition_ref` resolves to a real owner artifact,
3. verify `definition_refs` are concrete and useful rather than decorative,
4. verify required owner artifacts are present,
5. verify the registry does not duplicate business-local workflow semantics already owned elsewhere,
6. verify tests cover both registration truth and eligibility behavior.

## Common Failure Modes

Avoid these patterns:

1. using `lotus-ai` docs as the primary definition for a downstream-owned workflow,
2. registering a pack before the owner repository has stable contract and regression evidence,
3. letting optional UI or RFC references substitute for owner-repository artifacts,
4. keeping rollout posture only in prose rather than in the registry record,
5. treating process-local control history as if it were durable production truth.

## Documentation And Context Updates

When onboarding a new workflow-pack family, update all of these together:

1. registration contract and tests,
2. integration and operations guides,
3. repository engineering context when repository truth changed,
4. wiki-source pages used for operator navigation,
5. RFC document status and implementation-status sections when the work changes RFC reality,
6. PR summary so branch evidence matches the delivered slice.

## Future-Agent Guidance

If onboarding work exposes a repeated lesson, promote it instead of leaving it in chat history:

1. add or tighten repository context,
2. update the relevant repo guide or runbook,
3. update a shared Codex skill only when the lesson is reusable across repositories or repeated RFC loops,
4. keep those updates narrowly scoped and truthful.
