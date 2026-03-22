# Retrieval and Vector Store

This guide records the current retrieval-storage direction for `lotus-ai`.

## Current State

Right now, `lotus-ai` has a bounded indexed retrieval path over persisted preview embeddings,
but it does not yet push similarity search down into PostgreSQL with `pgvector`.

That split is intentional. We are building retrieval in disciplined slices and keeping the
current live path honest about what is already implemented versus what remains planned.

## Storage Decision

The first vector-store architecture for `lotus-ai` is:

1. PostgreSQL as the canonical durable database
2. `pgvector` as the first vector-store extension

## Why PostgreSQL + pgvector

1. It fits the existing Lotus backend architecture.
2. It keeps operational complexity lower than introducing a separate vector database early.
3. It is appropriate for the first retrieval phases:
   - RFCs
   - standards
   - architecture docs
   - OpenAPI-derived documentation
4. It allows metadata filtering and source provenance to remain close to the rest of the retrieval model.

## What We Are Avoiding For Now

We are intentionally not introducing a separate dedicated vector database yet.

Reasons:

1. retrieval scale has not justified it,
2. a separate runtime would increase operational surface area,
3. the team benefits more from a clean Lotus-owned retrieval contract than from early infrastructure sprawl.

## Decision Boundary

We should only consider a separate vector database later if we have evidence such as:

1. retrieval corpus size materially outgrows `pgvector` practicality,
2. latency or throughput requirements exceed acceptable PostgreSQL behavior,
3. operational isolation becomes necessary for a proven production workload.

## Retrieval Principles

1. Retrieval should remain a Lotus-owned capability.
2. Every retrieved answer should preserve provenance.
3. Source curation matters more than index size.
4. Vector search is a means to governed retrieval, not the product architecture itself.

## Indexing Lifecycle

The retrieval indexing lifecycle is intentionally staged.

What exists today:

1. approved sources are registered explicitly,
2. documents are inventoried per source with explicit promotion posture,
3. staged chunks are visible per document with stable content checksums,
4. durable embedding-record schema now exists beside staged chunks,
5. indexing jobs now expose persisted lifecycle events, deterministic chunking strategy, and replay posture,
6. retrieval metadata is served through a repository seam rather than hard-coded module state,
7. retrieval search now flows through an explicit execution gateway before any live backend is introduced,
8. retrieval execution status is exposed separately from retrieval catalog status.

What exists now:

1. searchable document promotion is explicit,
2. chunk durability includes stable content checksums,
3. embedding records now persist deterministic preview vectors,
4. retrieval can execute bounded indexed search over those persisted vectors when enabled,
5. catalog-only search remains available as the governed fallback when live retrieval is disabled.

What does not exist yet:

1. provider-backed embedding generation,
2. PostgreSQL-side `pgvector` similarity execution,
3. runtime vector writes from a live ingestion pipeline,
4. production-scale retrieval rollout.

This split is deliberate. We want the retrieval contract, governance posture, and observability model to become stable before live indexing is enabled.

## Retrieval Metadata Ownership

The current retrieval metadata posture is:

1. `lotus-ai` owns the retrieval repository interface,
2. the current default implementation is a seeded in-memory repository,
3. service logic reads retrieval metadata through that interface,
4. a SQLAlchemy-backed retrieval repository can read the same metadata from Alembic-managed tables,
5. future retrieval persistence changes should preserve the repository contract and API surface.

This keeps the service modular and makes the next move to SQL-backed retrieval metadata a persistence change rather than a product-surface rewrite.

Current configuration modes:

1. `LOTUS_AI_RETRIEVAL_STORE_MODE=memory` for the default seeded repository,
2. `LOTUS_AI_RETRIEVAL_STORE_MODE=sqlalchemy` with `LOTUS_AI_DATABASE_URL` for Alembic-managed retrieval metadata.

## Retrieval API Surface

The current retrieval API exposes:

1. source discovery,
2. source governance,
3. document governance,
4. retrieval runtime status,
5. retrieval execution status,
6. retrieval activation readiness,
7. retrieval runbook readiness,
8. retrieval governance status,
9. source-level index status,
10. indexing policy,
11. indexing job catalog and job detail,
12. document inventory,
13. chunk inventory.

Retrieval runtime status and job catalog now also expose embedding-record counts so operators can
see whether the durable schema is populated before live indexing is introduced.

Retrieval job detail now also exposes:

1. deterministic chunking strategy,
2. replay support posture,
3. persisted indexing lifecycle events,
4. explicit blocked or failed indexing states for sources that are not yet promotable.

The search endpoint remains governed. In foundation phase it now supports:

1. bounded indexed hits from promoted persisted preview embeddings when retrieval is enabled,
2. bounded catalog-only hits from the same promoted corpus when retrieval is disabled.

Current searchable documents are a promoted subset of the staged corpus. Today they
sit under these enabled sources:

1. `lotus-platform-rfcs`
2. `lotus-ai-architecture`

`/platform/runtime-status` now embeds retrieval governance posture directly so operators can review
retrieval rollout state from the same top-level runtime surface that already carries async and
provider governance posture.

`/platform/retrieval/execution-status` distinguishes the two execution stages explicitly, so
operators can tell whether retrieval is currently running through the indexed path or the
catalog-only fallback.

## Retrieval Evaluation Posture

Retrieval evaluation is now staged with file-backed fixture inventory.

Current staged retrieval evaluation assets:

1. [basic_cases.json](C:/Users/Sandeep/projects/lotus-ai/docs/evals/fixtures/retrieval.search/basic_cases.json)

These fixtures currently validate the governed pre-activation posture:

1. citation expectations remain explicit for RFC-backed questions,
2. refusal or conflict behavior is staged for insufficient or disabled retrieval paths,
3. retrieval evaluation assets evolve under the same manifest and CI gate as the rest of the evaluation inventory.
