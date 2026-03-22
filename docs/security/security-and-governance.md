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
