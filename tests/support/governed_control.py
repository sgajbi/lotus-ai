"""Two-step governed-action helpers for tests (issue #157).

Prompt promotion requires a verified requester and a distinct verified
approver. Tests that need an active prompt as *setup* use
``promote_prompt_for_test`` so the two-step flow lives in one place instead of
being copied into every file; tests about the flow itself call the service
functions directly.
"""

from __future__ import annotations

from app.contracts.prompts import (
    PromptPromotionApprovalRequest,
    PromptPromotionApprovalResponse,
    PromptPromotionIntentRequest,
)
from app.http.authenticated_caller import AuthenticatedCaller
from app.services.prompt_rollout_control import (
    approve_prompt_promotion,
    request_prompt_promotion,
)

GOVERNED_REQUESTER = AuthenticatedCaller(
    caller_app="lotus-platform",
    trust_source="verified_service_jwt",
    credential_key_id="ops-key-alpha",
)
GOVERNED_APPROVER = AuthenticatedCaller(
    caller_app="lotus-platform",
    trust_source="verified_service_jwt",
    credential_key_id="ops-key-beta",
)


def promote_prompt_for_test(
    *,
    task_id: str,
    candidate_prompt_version: str,
    reason: str = "Governed promotion for test setup.",
    requested_by: str = "alice@lotus.test",
    approved_by: str = "bob@lotus.test",
) -> PromptPromotionApprovalResponse:
    pending = request_prompt_promotion(
        PromptPromotionIntentRequest(
            task_id=task_id,
            candidate_prompt_version=candidate_prompt_version,
            reason=reason,
            requested_by=requested_by,
        ),
        GOVERNED_REQUESTER,
    )
    return approve_prompt_promotion(
        PromptPromotionApprovalRequest(
            task_id=task_id,
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
            approved_by=approved_by,
        ),
        GOVERNED_APPROVER,
    )
