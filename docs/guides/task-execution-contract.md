# Task Execution Contract

This document describes the first executable integration surface for `lotus-ai`.

## Endpoint

- `POST /ai/tasks/execute`

## Purpose

Provide a governed, contract-first task execution API that Lotus apps can integrate with before live provider execution is enabled.

During foundation phase, supported tasks return deterministic stub results.

Exception:

1. `knowledge_search.v1` now returns bounded catalog-only retrieval hits from the enabled
   staged-source subset instead of the generic text stub.
2. `knowledge_answer.v1` now returns a conservative citation-carrying answer built from the
   same bounded retrieval hits instead of the generic text stub.

This is intentional:

1. downstream apps can integrate early,
2. audit metadata shape becomes stable,
3. task contracts can evolve under test before model providers are introduced.

## Request Shape

Required fields:

1. `task_id`
2. `input_mode`
3. `caller`
4. `context`

### caller

Includes:

1. `caller_app`
2. `correlation_id`
3. optional `requested_by`
4. optional `tenant_id`

### context

Includes:

1. `summary`
2. `payload`
3. `source_refs`

## Response Shape

Returns:

1. `status`
2. `task_id`
3. `category`
4. `output_label`
5. `result`
6. `audit`

The `audit` block is part of the core platform contract and should be preserved by calling systems.

## Current Execution Behavior

Supported enabled tasks in foundation phase:

1. `explain.v1`
2. `summarize.v1`
3. `classify.v1`
4. `extract.v1`
5. `generate_structured.v1`
6. `knowledge_search.v1`
7. `knowledge_answer.v1`

`knowledge_search.v1` expects retrieval-specific context in `context.payload`:

1. required `query: string`
2. optional `source_ids: string[]`
3. optional `limit: int` between `1` and `20`

`knowledge_answer.v1` expects the same retrieval-specific context and returns:

1. a conservative answer string in `result.message`
2. `citations` in `result.structured_output`
3. the bounded retrieval hits used to assemble the answer

## Error Behavior

1. unknown `task_id` returns `404`
2. disabled task in current phase returns `409`
3. output-label mismatch returns `409`

## Integration Guidance

Calling Lotus apps should treat current results as contract-valid placeholders, not final business value.

The correct use right now is:

1. integrate request/response handling,
2. preserve audit metadata,
3. validate downstream UI or service compatibility,
4. avoid assuming live model execution.
