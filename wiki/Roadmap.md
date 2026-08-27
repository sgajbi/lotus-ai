# Roadmap

## Current Phase

`lotus-ai` is in a foundation phase with substantial bounded runtime already implemented. The
service is past the "documentation-only" stage, but it is still intentionally sequencing capability
expansion through governed rollout rather than broad feature activation.

## What Is Already Real

The following foundations are already part of the runtime or governance contract:

1. bounded task execution contracts,
2. prompt rollout state and audit traceability,
3. governed retrieval and citation-carrying answer flows,
4. runtime safety posture,
5. runtime-backed evaluations and approval gates,
6. durable async runtime and worker-backed execution,
7. caller identity and tenant-aware authorization,
8. provider policy and operations control surfaces,
9. artifact-backed evidence and observability surfaces,
10. bounded downstream use-case onboarding surfaces.

The current bounded task catalog already includes:

1. `explain.v1`
2. `summarize.v1`
3. `classify.v1`
4. `extract.v1`
5. `generate_structured.v1`
6. `knowledge_search.v1`
7. `knowledge_answer.v1`

That means the roadmap is not only about adding more task ids. It is also about:

1. deepening evaluation and evidence for the existing catalog,
2. governing which tasks can use live-provider paths,
3. hardening downstream adoption and rollout truth.

## What Remains Intentionally Bounded

Important limitations still matter:

1. live provider rollout is controlled and not generally enabled,
2. retrieval remains curated and bounded rather than broad enterprise search,
3. embeddings and corpus expansion remain governed rather than assumed,
4. production-go-live posture requires stronger runtime and governance evidence than local success,
5. downstream adoption is being shaped through bounded use cases and capability packs rather than
   open-ended enablement.

## Roadmap Shape

The roadmap still follows the phased architecture plan:

1. service foundation,
2. contract-first task layer,
3. prompt registry and settings,
4. audit, safety, and redaction,
5. knowledge retrieval,
6. first real domain integration,
7. expansion across Lotus apps,
8. async runs and controlled tool use.

Source:

- `docs/architecture/phased-roadmap.md`

## Near-Term Focus

Based on the current repo posture, the next meaningful work is not generic feature growth. It is:

1. tightening rollout governance around provider, retrieval, and production readiness,
2. improving downstream adoption through capability packs and onboarding templates,
3. hardening operational evidence so rollout claims stay truthful,
4. extending bounded use cases where there is strong domain value and low authority risk.

## Likely Downstream Expansion

The current roadmap points toward expansion across Lotus repos such as:

1. `lotus-performance`
2. `lotus-manage`
3. `lotus-advise`
4. `lotus-risk`
5. `lotus-core`

The important rule is that expansion should follow evidence and rollout discipline, not availability
of an AI runtime alone.

## Source Documents

- `docs/architecture/feature-status-and-roadmap.md`
- `docs/architecture/phased-roadmap.md`
- `docs/architecture/decision-log.md`

## Read Next

1. use [RFC Index](RFC-Index) for the governing decision inventory,
2. use [Integrations](Integrations) to see how roadmap expansion affects downstream adoption,
3. use [Security and Governance](Security-and-Governance) to understand why some expansion remains intentionally bounded.
