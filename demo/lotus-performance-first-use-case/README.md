# lotus-performance First Use-Case Demo

This demo shows the first bounded `lotus-ai` use case end to end:

1. `lotus-performance` computes real structured analytics.
2. `lotus-ai` accepts those facts through the bounded `explain.v1` contract.
3. `lotus-ai` returns explanation-only output with audit, evidence, access-control, safety, and rollout-governance metadata.
4. the first-use-case rollout gate moves from blocked to ready once runtime-backed evaluation evidence is recorded.

## What This Demo Captures

The demo writes every invoked API input and output to:

- [generated/captures](/C:/Users/Sandeep/projects/lotus-ai/demo/lotus-performance-first-use-case/generated/captures)

It also stores local runtime logs and demo state in:

- [generated/runtime](/C:/Users/Sandeep/projects/lotus-ai/demo/lotus-performance-first-use-case/generated/runtime)

That runtime directory is scratch space for local reruns and keeps only a checked-in `.gitignore`.

## Demo Shape

This first pass is intentionally:

- real `lotus-performance` analytics
- real `lotus-ai` platform and governance surfaces
- source-run `lotus-ai` from the current local branch
- governed stub execution for `explain.v1`
- SQL-backed platform stores with the artifact object store kept in memory for a reproducible local loop
- no live LLM key required

The next pass can reuse the same flow with `lotus-ai` brought up via Docker, and then a later pass can swap the stub provider path for live provider execution.

## Prerequisites

1. Docker Desktop is running.
2. `lotus-performance` repo exists at `../lotus-performance`.
3. Python dependencies for `lotus-ai` are installed locally.
4. canonical local performance service identity is `http://performance.dev.lotus`.

For the standalone source-run path in this demo:

- `lotus-ai` defaults to the direct local process URL `http://127.0.0.1:8140`
- override it with `LOTUS_AI_BASE_URL` if you are routing through a local ingress layer

## Run

From the `lotus-ai` repo root:

```powershell
powershell -ExecutionPolicy Bypass -File demo/lotus-performance-first-use-case/run-demo.ps1
```

## What The Script Does

1. brings up `lotus-performance` through Docker
2. starts `lotus-ai` from the current local source branch with a fresh demo database
3. captures core platform, governance, runtime, and use-case surfaces
4. submits a real `lotus-performance` analytics request
5. transforms that result into a bounded `lotus-ai` `explain.v1` request
6. captures the explanation response plus audit detail
7. submits and executes the first-use-case runtime-backed eval fixture family
8. captures the post-eval readiness and governance state

## Key Files

- [run-demo.ps1](/C:/Users/Sandeep/projects/lotus-ai/demo/lotus-performance-first-use-case/run-demo.ps1)
- [requests/lotus-performance-twr.request.json](/C:/Users/Sandeep/projects/lotus-ai/demo/lotus-performance-first-use-case/requests/lotus-performance-twr.request.json)
- [requests/lotus-ai-explain.request.json](/C:/Users/Sandeep/projects/lotus-ai/demo/lotus-performance-first-use-case/requests/lotus-ai-explain.request.json)
- [requests/lotus-ai-first-use-case-eval.request.json](/C:/Users/Sandeep/projects/lotus-ai/demo/lotus-performance-first-use-case/requests/lotus-ai-first-use-case-eval.request.json)

## Expected Outcome

After the script completes:

1. `lotus-performance` should be healthy on `http://performance.dev.lotus`
2. `lotus-ai` should be healthy on the configured `LOTUS_AI_BASE_URL` or the direct local default `http://127.0.0.1:8140`
3. pre-eval first-use-case governance should show one blocker: runtime-backed eval evidence
4. post-eval first-use-case governance should report `LIMITED_ROLLOUT_READY`
5. the captured `explain.v1` response should show:
   - `output_label = EXPLANATION_ONLY`
   - `authorization.outcome = ALLOWED`
   - prompt, safety, provider, retrieval, and access-control evidence descriptors
