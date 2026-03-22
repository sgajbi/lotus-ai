# Retrieval and Vector Store

This guide records the current retrieval-storage direction for `lotus-ai`.

## Current State

Right now, `lotus-ai` does not have a live vector store wired into runtime retrieval.

That is intentional. We are still building the retrieval layer in disciplined slices.

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
2. documents are inventoried per source,
3. staged chunks are visible per document,
4. indexing jobs and indexing policy are exposed through API contracts,
5. retrieval metadata is served through a repository seam rather than hard-coded module state,
6. retrieval search now flows through an explicit execution gateway before any live backend is introduced,
7. retrieval execution status is exposed separately from retrieval catalog status.

What does not exist yet:

1. live embedding generation,
2. runtime vector writes,
3. production retrieval execution over indexed vectors.

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
2. retrieval runtime status,
3. retrieval execution status,
4. retrieval activation readiness,
5. retrieval runbook readiness,
6. source-level index status,
7. indexing policy,
8. indexing job catalog and job detail,
9. document inventory,
10. chunk inventory.

The search endpoint remains governed and intentionally disabled until the retrieval execution layer is ready.

## Retrieval Evaluation Posture

Retrieval evaluation is now staged with file-backed fixture inventory.

Current staged retrieval evaluation assets:

1. [basic_cases.json](C:/Users/Sandeep/projects/lotus-ai/docs/evals/fixtures/retrieval.search/basic_cases.json)

These fixtures currently validate the governed pre-activation posture:

1. citation expectations remain explicit for RFC-backed questions,
2. refusal or conflict behavior is staged for insufficient or disabled retrieval paths,
3. retrieval evaluation assets evolve under the same manifest and CI gate as the rest of the evaluation inventory.
