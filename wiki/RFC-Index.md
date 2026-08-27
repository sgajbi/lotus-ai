# RFC Index

## How to Use This Page

The local RFC set for `lotus-ai` is broad enough that a flat list is not very useful. This page
groups the RFCs by the capability areas they govern so engineers can find the right decision trail
faster.

The source inventory remains:

- `docs/rfcs/README.md`

## Platform-Level Governing RFCs

The main Lotus platform RFCs that shape this repository are:

1. `RFC-0069`
   shared AI platform service role and boundaries
2. `RFC-0072`
   CI, validation, and release governance
3. `RFC-0073`
   context and guidance-system governance
4. `RFC-0108`
   front-office analytics UI observability and operational posture; in `lotus-ai`, this is
   represented by the `ai_surface_supportability` runtime-status block and the bounded
   `lotus_ai_surface_supportability_state` metric

These live under:

- `../lotus-platform/rfcs/`

## Implemented Foundation RFCs

These RFCs established the core bounded platform:

1. `RFC-0001` shared AI platform service
2. `RFC-0002` real retrieval backbone
3. `RFC-0003` controlled live provider backbone
4. `RFC-0006` durable async execution backbone
5. `RFC-0007` runtime-backed evaluation execution and approval gates
6. `RFC-0009` runtime safety enforcement and redaction
7. `RFC-0010` governed prompt activation and rollback
8. `RFC-0012` caller identity and tenant isolation controls
9. `RFC-0013` runtime observability and incident evidence
10. `RFC-0014` governed artifact and object storage backbone

## Retrieval, Provider, and Runtime Expansion RFCs

These RFCs govern the current deeper runtime posture:

1. `RFC-0004` provider operations hardening
2. `RFC-0005` durable provider operations state
3. `RFC-0008` governed live retrieval activation
4. `RFC-0011` dedicated worker fleet and managed queue
5. `RFC-0015` deployment split into runtime, retrieval, and evals
6. `RFC-0017` production resilience and disaster recovery
7. `RFC-0018` governed embeddings and provider expansion
8. `RFC-0019` governed document ingestion and corpus refresh
9. `RFC-0020` production standard deployment baseline
10. `RFC-0022` production go-live approval and managed infrastructure
11. `RFC-0027` local and remote OpenAI-compatible provider routing

## Downstream Adoption and Productization RFCs

These RFCs are about how `lotus-ai` becomes useful across Lotus applications:

1. `RFC-0016` first production use-case onboarding
2. `RFC-0021` domain AI capability packs and product maturity
3. `RFC-0023` multi-app adoption and capability-rollout governance

## Draft or Future-Facing RFCs

These RFCs are important for the forward path but are not yet implemented as settled platform
posture:

1. `RFC-0024` portfolio narrative copilot for `lotus-performance`
2. `RFC-0025` operational root-cause copilot for `lotus-core`
3. `RFC-0026` operator control-plane dashboard and observability integration
4. `RFC-0028` relationship-manager briefing agent for the Lotus ecosystem
5. `RFC-0029` portfolio situation room agent
6. `RFC-0030` client mandate integrity and action orchestration

## Practical Rule

When working in `lotus-ai`, start with:

1. the repo `README.md`,
2. `REPOSITORY-ENGINEERING-CONTEXT.md`,
3. the architecture docs,
4. the specific RFC family for the capability you are changing.

Do not load the entire RFC estate unless the task is specifically governance-heavy.

## Read Next

1. use [Roadmap](Roadmap) for how the RFC program translates into platform phases,
2. use [Security and Governance](Security-and-Governance) for the practical runtime interpretation,
3. use [Development Workflow](Development-Workflow) when the RFC work implies code and docs changes in the same slice.
