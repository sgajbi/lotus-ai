# lotus-ai

Shared AI platform service for Lotus applications.

`lotus-ai` provides the reusable AI infrastructure layer for the Lotus estate. It exists to help the other Lotus apps build governed AI features without moving domain ownership out of the services that already own portfolio data, analytics, workflow state, and deterministic decision logic.

## What lotus-ai Does

- LLM gateway and model routing
- prompt and prompt-version management
- retrieval over approved Lotus docs, RFCs, schemas, and standards
- AI safety controls such as redaction, output labeling, and role-aware gating
- AI audit logging, cost tracking, and evaluations
- reusable AI task APIs for explanation, summarization, extraction, classification, and structured generation
- async AI run orchestration for longer jobs

## What lotus-ai Does Not Do

- own portfolio or transaction truth
- replace deterministic logic in `lotus-core`, `lotus-performance`, `lotus-risk`, `lotus-advise`, or `lotus-manage`
- become the source of truth for approvals, consent, risk, or reporting decisions
- own UI lifecycle orchestration from `lotus-gateway` or `lotus-workbench`
- autonomously execute trades or workflow transitions

## How Other Lotus Apps Should Use It

The preferred integration model is:

1. a Lotus app prepares the structured context it owns,
2. it calls `lotus-ai` for a bounded AI task,
3. `lotus-ai` returns a governed result with audit metadata,
4. the calling app remains responsible for business meaning and user-facing application.

Examples:

- `lotus-manage` can ask `lotus-ai` to explain why a rebalance is `BLOCKED`.
- `lotus-advise` can ask `lotus-ai` to draft a reviewer summary for a proposal.
- `lotus-performance` and `lotus-risk` can ask `lotus-ai` for analytics commentary.
- `lotus-core` can ask `lotus-ai` to summarize supportability anomalies.

## Initial Repository Layout

- `src/app/providers/`: provider adapters and model routing
- `src/app/prompts/`: prompt registry and prompt-version assets
- `src/app/retrieval/`: knowledge indexing and retrieval services
- `src/app/safety/`: redaction, policy checks, and output controls
- `src/app/evals/`: evaluation and regression helpers
- `src/app/services/`: service-layer orchestration
- `src/app/contracts/`: request and response models
- `src/app/routers/`: API surfaces
- `docs/rfcs/`: service-local architecture decisions

## Quick Start

```powershell
make install
make lint
make typecheck
make openapi-gate
make ci
```

## Run

```powershell
uvicorn app.main:app --reload --port 8140
```

## Docker

```powershell
docker compose up --build
```

## Documentation

- service-local RFCs: `docs/rfcs/`
- service standards: `docs/standards/`
- platform governance source: `../lotus-platform/rfcs/RFC-0069-lotus-ai-shared-ai-platform-service.md`
