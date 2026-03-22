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
