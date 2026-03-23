# RFC-0014: Governed Artifact and Object Storage Backbone

- Status: Draft
- Date: 2026-03-23
- Owners: lotus-ai
- Requires Approval From: lotus-ai maintainers

## Summary

`lotus-ai` should introduce a governed artifact and object-storage backbone so large evaluation outputs, retrieval traces, async payloads, and operational incident evidence can scale beyond relational rows and static repository artifacts without breaking auditability or platform control boundaries.

RFC-0006 and RFC-0007 made async and evaluation execution runtime-backed.
RFC-0011 defines a dedicated worker and managed-queue deployment model.
RFC-0013 defines a runtime observability and incident-evidence backbone.

The next storage-focused gap is that the platform architecture already expects object storage for larger artifacts, but the actual governed artifact backbone does not yet exist.

## Why This Is Next

The platform currently stores or exposes:

1. runtime-backed evaluation runs, attempts, and case outcomes,
2. async job and control history,
3. audit records and execution evidence,
4. staged historical run artifacts and async artifacts,
5. growing observability and incident-evidence expectations.

This is acceptable while payloads remain small, but it does not scale well for:

1. larger evaluation result bodies,
2. retrieval trace and search evidence payloads,
3. prompt rollback evidence packs,
4. incident evidence bundles,
5. future document-ingestion and worker-generated artifacts.

The architecture already documents the target:

1. [scalability-and-deployment-model.md](C:/Users/Sandeep/projects/lotus-ai/docs/architecture/scalability-and-deployment-model.md#L1) explicitly calls for object storage once evaluation, retrieval, or trace payloads outgrow relational storage.

## Problem Statement

`lotus-ai` now has several runtime domains that can generate durable evidence and operational artifacts, but no first-class artifact storage model for them.

Current limitations:

1. historical artifacts are still file-backed JSON in the repository,
2. runtime-backed records are stored relationally with no clear large-artifact escape hatch,
3. the architecture assumes object storage, but the implementation does not yet provide it,
4. future observability and incident-evidence work will increase pressure on artifact handling.

This creates risk:

1. large payloads could bloat relational storage or be artificially truncated,
2. operational evidence could end up fragmented across ad hoc files and rows,
3. runbook and support workflows will have no authoritative artifact-handling path,
4. future worker and evaluation growth will hit storage-model limits before runtime-control limits.

## Goals

1. Introduce a governed artifact-storage model for large runtime and historical evidence.
2. Preserve relational state as the authoritative metadata and indexing layer.
3. Add object storage as the scalable backing store for larger governed payloads.
4. Keep artifact access auditable, bounded, and reviewable.
5. Align evaluation, async, retrieval, observability, and future worker outputs with one artifact model.

## Non-Goals

1. Building a generic document-management system.
2. Storing arbitrary caller payloads outside governed platform workflows.
3. Replacing relational metadata with blob-only storage.
4. Opening unrestricted artifact browsing or download surfaces.
5. Introducing object storage for tiny records that fit the current relational model cleanly.

## Current State

The platform already has:

1. durable relational stores for audit, provider ops, async, evaluation, and retrieval metadata,
2. staged file-backed artifact registries for historical evaluation and async records,
3. an architecture requirement for object storage once artifact size justifies it.

The missing layer is the governed bridge between relational metadata and large artifact payloads.

## Decision

`lotus-ai` will implement a governed artifact and object-storage backbone.

The first production-capable artifact model should:

1. keep relational metadata authoritative,
2. store large payloads in object storage behind governed references,
3. expose typed artifact descriptors rather than raw storage details,
4. preserve auditability, retention posture, and access reviewability,
5. support historical, runtime, and incident-evidence artifacts through one bounded storage model.

## State Model and Invariants

This RFC establishes the following invariants:

1. relational metadata remains the source of truth for artifact identity, lineage, and access posture,
2. object storage holds payload content, not authoritative business state,
3. artifact references must be durable and reviewable,
4. no runtime domain may bypass artifact governance with ad hoc file writes,
5. artifact access must respect the shared-platform identity and authorization model,
6. runtime and historical artifact posture must remain distinguishable.

## Architecture Direction

### Artifact Metadata Model

Introduce explicit artifact metadata records.

Required behavior:

1. artifact id, domain, type, source object, lineage, retention posture, and storage reference are explicit,
2. metadata can link to evaluation runs, async jobs, retrieval jobs, prompt rollbacks, or incident reviews,
3. metadata remains queryable through bounded service seams,
4. artifact state distinguishes staged historical, runtime-produced, superseded, and archived posture.

### Object Storage Integration

Introduce object storage behind a bounded service seam.

Required behavior:

1. storage providers are abstracted behind a governed repository/service boundary,
2. payload upload and retrieval paths are explicit and reviewable,
3. runtime workers can emit large artifacts without inventing new storage patterns,
4. object references remain stable even if backing storage changes later.

### Domain Consumer Integration

The first consumers should be the places already generating governed evidence.

Required behavior:

1. evaluation runtime can store larger case-result or evidence bundles,
2. async runtime can attach artifact references for larger job outputs,
3. observability and incident-evidence flows can persist larger diagnostic bundles,
4. retrieval or prompt control planes can persist approval and rollback evidence packs where needed.

### Access and Governance Convergence

Artifact storage must stay within the shared platform’s governance model.

Required behavior:

1. artifact descriptors integrate with caller identity and tenant isolation controls,
2. audit evidence can explain artifact creation and access context,
3. runbooks can define artifact retention and incident-review handling,
4. observability and supportability views can link to governed artifact references rather than only prose or in-row summaries.

## Data and Operational Requirements

1. Artifact metadata must survive restart and remain relationally queryable.
2. Object-storage references must be durable and bounded.
3. Sensitive payloads must not bypass safety or authorization controls.
4. Artifact retention and supersession posture must be explicit.
5. SQL-backed and storage-backed tests must prove metadata and payload consistency.
6. Runbooks must define artifact retention, cleanup, incident handling, and recovery procedures.
7. Platform status and governance surfaces must describe artifact-storage posture truthfully.

## Delivery Slices

### Slice 1: Artifact Metadata Schema and Storage Seam

Outcome:

1. artifact metadata schema exists,
2. object-storage repository/service seam exists,
3. no major runtime consumer cutover yet.

Acceptance gate:

1. metadata is migration-managed,
2. repository contracts are explicit and tested,
3. runtime status remains truthful,
4. relational metadata remains authoritative.

### Slice 2: Evaluation and Async Artifact Cutover

Outcome:

1. evaluation and async domains can persist governed large artifacts through the new backbone,
2. relational records link to object-backed payloads,
3. historical artifact posture remains distinguishable.

Acceptance gate:

1. runtime-backed artifact references are durable,
2. integration tests cover artifact creation and retrieval metadata,
3. existing evaluation and async contracts remain stable,
4. no ad hoc storage paths remain for those consumers.

### Slice 3: Observability and Incident-Evidence Integration

Outcome:

1. runtime observability and incident-review bundles can use governed artifact storage,
2. operator support workflows improve materially,
3. larger diagnostic payloads no longer need to live only in rows or repository files.

Acceptance gate:

1. incident evidence is storable and reviewable through the backbone,
2. sensitive payload handling remains bounded,
3. observability surfaces align with artifact references,
4. runbooks can point to actual artifact workflows.

### Slice 4: Retention, Archival, and Governance Hardening

Outcome:

1. artifact retention and supersession posture are explicit,
2. archival and cleanup controls are reviewable,
3. platform governance reflects the real artifact model.

Acceptance gate:

1. retention state is inspectable,
2. archived versus active artifacts are explicit,
3. governance and runbook surfaces match implementation reality,
4. the platform is materially closer to production-grade evidence handling.

## Risks

1. object-storage integration could introduce opaque payload handling if metadata is not kept strong,
2. weak retention rules could create sprawl or compliance ambiguity,
3. access control gaps could expose sensitive artifacts,
4. premature artifact generalization could overcomplicate domains that still fit relational storage.

## Alternatives Considered

### Alternative 1: Keep Everything in Relational Storage Longer

Rejected as the long-term approach.

Reason:

1. the architecture already anticipates object storage for scale,
2. evaluation, observability, and incident evidence will eventually outgrow that approach.

### Alternative 2: Keep Artifact Handling as Repository Files Plus Runtime Rows

Rejected.

Reason:

1. that would maintain split-brain artifact handling,
2. it would not scale operationally or support worker-generated evidence cleanly.

### Alternative 3: Build Object Storage Before Observability and Control-Plane Work

Deferred previously and still not the first step.

Reason:

1. the platform first needed stronger runtime and governance foundations,
2. after those are in place, artifact storage becomes the right next storage-focused milestone.

## Acceptance Criteria

This RFC is complete when:

1. `lotus-ai` has a governed artifact metadata model,
2. larger governed payloads can live in object storage behind durable references,
3. evaluation, async, and operational evidence can consume that backbone,
4. access, retention, and archival posture are explicit and reviewable,
5. the platform is materially closer to production-grade evidence and artifact handling.

## Approval Requested

Approve this RFC if the team agrees that:

1. governed artifact and object storage is the next storage-focused platform gap after the current runtime and observability sequence,
2. relational metadata should remain authoritative while payloads can move to object storage,
3. evaluation, async, and incident-evidence consumers should converge on one artifact model,
4. delivery should proceed in the slices defined above.
