# Integration Guide

This guide explains how other Lotus apps should integrate with `lotus-ai`.

## Core Rule

The calling Lotus application owns the business context.

`lotus-ai` should receive structured context that has already been curated by the calling service or by `lotus-gateway`.

## Recommended Integration Pattern

1. Build a domain-owned context payload.
2. Select a bounded AI task id.
3. Call `lotus-ai` with correlation id and caller metadata.
4. Receive structured AI output and audit metadata.
5. Apply that output only within the calling service's own business rules.

## Good Use Cases

### lotus-manage

1. Explain rebalance outcome.
2. Summarize blocking diagnostics.
3. Draft reviewer notes for support or operations.

### lotus-advise

1. Summarize proposal workflow status.
2. Draft approval-pack commentary.
3. Explain suitability or gate recommendations.

### lotus-risk and lotus-performance

1. Turn structured analytics into narrative explanations.
2. Summarize material changes between periods or scenarios.

### lotus-core

1. Summarize ingestion or support anomalies.
2. Explain likely causes from structured lineage/support data.

## Bad Use Cases

1. Replacing domain calculations with LLM guesses.
2. Letting `lotus-ai` invent missing core business data.
3. Asking `lotus-ai` to authoritatively decide approvals or trade execution.
4. Sending uncurated, overly broad data just because it might help.

## Request Design Guidance

Every request should include:

1. `task_id`
2. `caller_app`
3. `correlation_id`
4. `input_mode`
5. structured context object
6. expected output mode

Prefer smaller, explicit context bundles over large raw payload dumps.

## Retrieval Guidance

If retrieval is used:

1. retrieval sources should be explicit,
2. cited output should keep source references,
3. platform docs and approved standards should be favored over ad hoc notes.
