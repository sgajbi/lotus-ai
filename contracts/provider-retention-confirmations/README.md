# Provider Retention Confirmations

This contract family is owned by `lotus-ai` provider operations. It records source-safe provider
storage/deletion posture for completed live Idea explanation runs and signs the result for
`lotus-idea` verification through the existing workflow-attestation public-key discovery path.

It does not contain prompts, generated output, client identifiers, or provider secrets. It does
not grant `lotus-idea` AI infrastructure or provider-deletion authority.

Current status is `not_certified`; see the contract `remaining_blockers` for production closure.
