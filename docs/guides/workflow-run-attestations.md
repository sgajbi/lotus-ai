# Workflow-Run Attestations

## Purpose And Current Scope

`lotus-ai` can issue a short-lived Ed25519-signed attestation for a durable workflow-pack run. The
attestation lets a Lotus consumer verify bounded execution provenance without receiving prompts,
raw provider payloads, generated content, or client and portfolio identifiers.

This contract authenticates AI execution facts. It does not transfer opportunity, advisory,
suitability, compliance, execution, reporting, or client-publication authority to `lotus-ai`.

## API Contract

| Operation | Endpoint | Result |
|---|---|---|
| Issue run attestation | `GET /platform/workflow-packs/runs/{run_id}/attestation` | Short-lived signed claims for an eligible durable run |
| Discover verification keys | `GET /.well-known/lotus-ai-workflow-attestation-keys` | Active, rotated, and revoked public Ed25519 keys |

The versioned schemas are `lotus-ai.workflow-run-attestation.v1` and
`lotus-ai.workflow-run-attestation-keys.v1`. Canonical serialization uses ASCII JSON with sorted
keys and compact separators. Signatures cover run/request identity, workflow and evaluator
identity, provider/model identity, model-risk approval, evidence/output digests, temporal bounds,
replay nonce, stub posture, and supportability.

## Issuance Gates

| Control | Required posture |
|---|---|
| Runtime | `COMPLETED` with truthful execution start and completion timestamps |
| Review | Accepted when review is required |
| Supportability | `READY`, including retained evidence and output-summary artifact |
| Provider | Non-stub execution |
| Model risk | Exact approved provider mode, provider ID, model ID, model version, and workflow-pack scope |
| Approval evidence | Non-placeholder `model_risk_approval_ref` |
| Signing | Valid active Ed25519 private key and rotation metadata |

Pending review, failed execution, missing evidence, unapproved models, stubs, malformed durable
facts, and invalid signing configuration fail closed. The caller cannot override audience, TTL,
model posture, digests, or supportability through request parameters.

## Configuration

| Environment variable | Purpose | Rule |
|---|---|---|
| `LOTUS_AI_WORKFLOW_RUN_ATTESTATION_KEY_ID` | Active signing-key identifier | Stable and unique across retained keys |
| `LOTUS_AI_WORKFLOW_RUN_ATTESTATION_ROTATION_EPOCH` | Monotonic rotation sequence | Positive integer |
| `LOTUS_AI_WORKFLOW_RUN_ATTESTATION_PRIVATE_KEY_BASE64URL` | Raw 32-byte Ed25519 private key | Inject at runtime from the approved secret manager |
| `LOTUS_AI_WORKFLOW_RUN_ATTESTATION_KEY_NOT_BEFORE_UTC` | Active-key validity start | Timezone-aware ISO-8601 |
| `LOTUS_AI_WORKFLOW_RUN_ATTESTATION_KEY_NOT_AFTER_UTC` | Optional active-key validity end | Timezone-aware ISO-8601 |
| `LOTUS_AI_WORKFLOW_RUN_ATTESTATION_ROTATED_PUBLIC_KEYS_JSON` | Historical rotated or revoked public keys | Governed JSON; must not contain another active key |
| `LOTUS_AI_WORKFLOW_RUN_MODEL_RISK_INVENTORY_JSON` | Exact approved model inventory | Governed JSON with unique identities |
| `LOTUS_AI_WORKFLOW_RUN_ATTESTATION_TTL_SECONDS` | Attestation lifetime | 1 through 3600 seconds; default 300 |
| `LOTUS_AI_LIVE_TEXT_MODEL_VERSION` | Governed live model release/deployment version | Required for an approvable live run |

Do not put private keys in source control, Compose files, image layers, Docker build arguments, OCI
labels, logs, or release manifests. Runtime injection is a transport from the approved secret
manager, not permission to bake the value into an image.

## Model-Risk Inventory

Approval requires one effective exact match:

```json
[
  {
    "provider_id": "text.openai",
    "provider_mode": "openai",
    "model_id": "gpt-5.4",
    "model_version": "2026-06-01",
    "workflow_pack_ids": ["idea_explanation.pack"],
    "approval_ref": "model-risk://lotus-ai/gpt-5.4/2026-06-01",
    "approved_from_utc": "2026-06-01T00:00:00Z",
    "approved_until_utc": "2026-09-01T00:00:00Z"
  }
]
```

The end time is exclusive. Missing, expired, duplicated, differently scoped, or partially matching
entries produce `approval_unverified`. Stub execution always produces `test_only`.

## Key Rotation Procedure

1. Generate a new Ed25519 key through the approved key-management process.
2. Increment the rotation epoch and deploy the new private key, key ID, and validity window.
3. Retain the previous public key in the rotated-key JSON with status `rotated` and a governed end.
4. Verify discovery exposes exactly one active key and every retained historical key.
5. Verify active and rotated fixtures; verify unknown and revoked keys fail closed.
6. Publish a compromised key as `revoked`; retain its revocation evidence for the governed period.
7. Confirm consumers refreshed discovery before removing an expired rotated key.

## Consumer Responsibilities

Consumers such as `lotus-idea` verify signature, issuer, audience, time window, workflow/evaluator
binding, provider/model/version approval, evidence/output digests, stub posture, and supportability.
They also own durable replay protection and one-to-one request/run receipt policy at their trust
boundary. A valid signature never supplies missing business evidence or consequence-bearing
approval.

## Validation

Run `make check` for the repository-native gate. Focused evidence is available through:

```powershell
python -m pytest tests/unit/test_workflow_run_attestation_signing.py `
  tests/unit/test_workflow_run_attestation_verification.py `
  tests/unit/test_workflow_run_attestation_issuance.py `
  tests/unit/test_workflow_run_model_risk.py `
  tests/integration/test_workflow_run_attestation_api_contract.py -q
```

The suite covers canonical serialization, claim tampering, key lifecycle, issuer/audience/expiry,
exact model approval, source safety, issuance gates, API errors, and OpenAPI serialization.

## RFC-0002 Idea Explanation Proof

`idea_explanation.pack@v1` has an explicit local-dev proof gate for the Lotus Idea RFC-0002 Slice
09/17 dependency:

```powershell
python scripts/generate_rfc0002_idea_explanation_proof.py
```

The gate executes the Idea explanation workflow pack through the protected HTTP boundary, applies a
reviewer acceptance, verifies source-safe consumer/source-event lineage, and verifies that local
stub execution remains unable to issue:

1. a signed workflow-run attestation, because there is no approved non-stub model-risk decision,
2. a provider-retention confirmation, because there is no live provider execution.

When a downstream handoff artifact is needed, write it under ignored `output/`:

```powershell
python scripts/generate_rfc0002_idea_explanation_proof.py `
  --output output/rfc0002-idea-explanation-proof.json
```

This artifact is intentionally source-safe and partial. It can clear local owner-repo execution,
review, guardrail, and lineage proof, but it must not be used as live-provider certification,
provider-native retention/deletion proof, supported-feature promotion proof, or downstream Idea
consumption proof. Its machine-readable contract is
`contracts/rfc-0002/lotus-ai-idea-explanation-workflow-proof.v1.json`.
