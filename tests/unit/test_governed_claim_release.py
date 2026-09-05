"""Governed claim release (issue #340).

Freeze-forever is the intended default for an orphaned claim; this is the
explicit operator path out. Three distinct credentials total, the target's
identity pinned into the approval hash, and the release racing resume on the
SAME claim-instant fence - one winner by construction, never two effects.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.contracts.governed_actions import (
    ClaimReleaseApprovalRequest,
    ClaimReleaseApprovalResponse,
    ClaimReleaseIntentRequest,
    GovernedActionRecord,
    GovernedActionStatus,
    GovernedActionType,
)
from app.http.authenticated_caller import AuthenticatedCaller
from app.services.governed_action_control import (
    approve_and_execute_governed_action,
    submit_governed_action,
)
from app.services.governed_claim_release import (
    approve_claim_release,
    request_claim_release,
)
from app.services.provider_operations_store import get_provider_operations_store
from tests.support.governed_control import GOVERNED_APPROVER, GOVERNED_REQUESTER

RELEASE_REQUESTER = AuthenticatedCaller(
    caller_app="lotus-platform",
    trust_source="verified_service_jwt",
    credential_key_id="ops-key-gamma",
)
RELEASE_APPROVER = AuthenticatedCaller(
    caller_app="lotus-platform",
    trust_source="verified_service_jwt",
    credential_key_id="ops-key-delta",
)

_PAYLOAD: dict[str, str | None] = {
    "action_type": GovernedActionType.PROVIDER_OPERATIONS_RESET.value,
    "target": "live",
}


def _frozen_claim() -> GovernedActionRecord:
    """A CLAIMED action whose holder (GOVERNED_APPROVER) is presumed gone."""

    pending = submit_governed_action(
        caller=GOVERNED_REQUESTER,
        action_type=GovernedActionType.PROVIDER_OPERATIONS_RESET,
        target="live",
        payload=dict(_PAYLOAD),
        attribution=None,
    )

    def _explode(record: object) -> None:
        raise RuntimeError("executor died mid-claim")

    with pytest.raises(RuntimeError):
        approve_and_execute_governed_action(
            caller=GOVERNED_APPROVER,
            action_id=pending.action_id,
            expected_target="live",
            expected_hash=pending.action_hash,
            current_payload_builder=lambda record: dict(record.action_payload),
            attribution=None,
            execute=_explode,
        )
    frozen = get_provider_operations_store().get_governed_action(pending.action_id)
    assert frozen is not None
    assert frozen.status is GovernedActionStatus.CLAIMED
    return frozen


def _release(target_id: str) -> ClaimReleaseApprovalResponse:
    pending = request_claim_release(
        ClaimReleaseIntentRequest(target_action_id=target_id, reason="Credential rotated out."),
        RELEASE_REQUESTER,
    )
    return approve_claim_release(
        ClaimReleaseApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
        ),
        RELEASE_APPROVER,
    )


def test_release_reopens_a_frozen_claim_with_full_evidence() -> None:
    frozen = _frozen_claim()
    response = _release(frozen.action_id)

    released = response.released_action
    assert released.status is GovernedActionStatus.PENDING
    assert released.approver_key_id is None
    assert released.claimed_at is None
    # Requester evidence on the TARGET survives the release.
    assert released.requester_key_id == GOVERNED_REQUESTER.credential_key_id
    # The release action's own chain: three distinct credentials in total.
    release_record = response.governed_action
    assert release_record.status is GovernedActionStatus.EXECUTED
    assert release_record.requester_key_id == RELEASE_REQUESTER.credential_key_id
    assert release_record.approver_key_id == RELEASE_APPROVER.credential_key_id
    assert release_record.result_payload is not None
    assert release_record.result_payload["released_target_action_id"] == frozen.action_id

    # The released action is re-approvable by a distinct credential, and the
    # callback's idempotency-under-action-identity carries convergence.
    performed: set[str] = set()
    executed = approve_and_execute_governed_action(
        caller=GOVERNED_APPROVER,
        action_id=frozen.action_id,
        expected_target="live",
        expected_hash=frozen.action_hash,
        current_payload_builder=lambda record: dict(record.action_payload),
        attribution=None,
        execute=lambda record: performed.add(record.action_id),
    )
    assert executed.status is GovernedActionStatus.EXECUTED
    assert performed == {frozen.action_id}


def test_the_frozen_credential_cannot_request_or_approve_its_own_release() -> None:
    frozen = _frozen_claim()

    with pytest.raises(HTTPException) as request_refusal:
        request_claim_release(
            ClaimReleaseIntentRequest(target_action_id=frozen.action_id, reason="Self-service."),
            GOVERNED_APPROVER,
        )
    assert request_refusal.value.status_code == 403

    pending = request_claim_release(
        ClaimReleaseIntentRequest(target_action_id=frozen.action_id, reason="Legit."),
        RELEASE_REQUESTER,
    )
    with pytest.raises(HTTPException) as approve_refusal:
        approve_claim_release(
            ClaimReleaseApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            GOVERNED_APPROVER,
        )
    assert approve_refusal.value.status_code == 403


def test_release_refuses_targets_that_are_not_claimed() -> None:
    pending = submit_governed_action(
        caller=GOVERNED_REQUESTER,
        action_type=GovernedActionType.PROVIDER_OPERATIONS_RESET,
        target="live",
        payload=dict(_PAYLOAD),
        attribution=None,
    )
    with pytest.raises(HTTPException) as refusal:
        request_claim_release(
            ClaimReleaseIntentRequest(target_action_id=pending.action_id, reason="Not frozen."),
            RELEASE_REQUESTER,
        )
    assert refusal.value.status_code == 409

    with pytest.raises(HTTPException) as missing:
        request_claim_release(
            ClaimReleaseIntentRequest(target_action_id="gact_absent", reason="Missing."),
            RELEASE_REQUESTER,
        )
    assert missing.value.status_code == 404


def test_a_resume_between_request_and_approval_wins_and_the_release_refuses() -> None:
    """Release vs resume: the freshness rebuild pins the claim instant, so a
    claim the owner resumed (rotating the instant) refuses the stale release
    approval - the owner's recovery always beats the operator path."""

    frozen = _frozen_claim()
    pending = request_claim_release(
        ClaimReleaseIntentRequest(target_action_id=frozen.action_id, reason="Frozen."),
        RELEASE_REQUESTER,
    )

    performed: set[str] = set()
    resumed = approve_and_execute_governed_action(
        caller=GOVERNED_APPROVER,
        action_id=frozen.action_id,
        expected_target="live",
        expected_hash=frozen.action_hash,
        current_payload_builder=lambda record: dict(record.action_payload),
        attribution=None,
        execute=lambda record: performed.add(record.action_id),
        resume_interrupted_claim=True,
    )
    assert resumed.status is GovernedActionStatus.EXECUTED

    with pytest.raises(HTTPException) as refusal:
        approve_claim_release(
            ClaimReleaseApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            RELEASE_APPROVER,
        )
    assert refusal.value.status_code == 409
    assert performed == {frozen.action_id}


def test_release_cas_loses_to_a_concurrent_resume_between_claim_and_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The narrow window after the release approval's freshness rebuild: the
    owner's resume rotates the claim instant, so the release's fenced CAS
    (pinned to the stale instant) loses - one winner, never two outcomes."""

    frozen = _frozen_claim()
    pending = request_claim_release(
        ClaimReleaseIntentRequest(target_action_id=frozen.action_id, reason="Frozen."),
        RELEASE_REQUESTER,
    )

    store = get_provider_operations_store()
    real_transition = store.transition_governed_action

    def resume_wins_first(
        *,
        action_id: str,
        expected_status: str,
        record: GovernedActionRecord,
        expected_claimed_at: str | None = None,
    ) -> bool:
        if action_id == frozen.action_id and expected_claimed_at == frozen.claimed_at:
            # The owner resumed a moment earlier: rotate the live claim
            # instant so the release's pinned fence no longer matches.
            rotated = frozen.model_copy(update={"claimed_at": "2099-01-01T00:00:00+00:00"})
            real_transition(
                action_id=frozen.action_id,
                expected_status=GovernedActionStatus.CLAIMED.value,
                record=rotated,
                expected_claimed_at=frozen.claimed_at,
            )
        return real_transition(
            action_id=action_id,
            expected_status=expected_status,
            record=record,
            expected_claimed_at=expected_claimed_at,
        )

    monkeypatch.setattr(store, "transition_governed_action", resume_wins_first)
    with pytest.raises(HTTPException) as refusal:
        approve_claim_release(
            ClaimReleaseApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            RELEASE_APPROVER,
        )
    assert refusal.value.status_code == 409
    target = store.get_governed_action(frozen.action_id)
    assert target is not None
    assert target.status is GovernedActionStatus.CLAIMED
    assert target.claimed_at == "2099-01-01T00:00:00+00:00"


def test_a_replayed_release_approval_converges_on_the_recorded_outcome() -> None:
    frozen = _frozen_claim()
    pending = request_claim_release(
        ClaimReleaseIntentRequest(target_action_id=frozen.action_id, reason="Frozen."),
        RELEASE_REQUESTER,
    )
    first = approve_claim_release(
        ClaimReleaseApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
        ),
        RELEASE_APPROVER,
    )
    replay = approve_claim_release(
        ClaimReleaseApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
        ),
        RELEASE_APPROVER,
    )
    assert replay.governed_action.action_id == first.governed_action.action_id
    assert replay.released_action.action_id == frozen.action_id


def test_approving_an_unknown_release_action_is_not_found() -> None:
    with pytest.raises(HTTPException) as missing:
        approve_claim_release(
            ClaimReleaseApprovalRequest(action_id="gact_absent", action_hash="0" * 64),
            RELEASE_APPROVER,
        )
    assert missing.value.status_code == 404


def test_replay_refuses_when_the_released_target_vanished(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A replayed approval reconstructs the outcome from the durable result;
    a released target that no longer exists is a bounded 409, never an
    invented record."""

    frozen = _frozen_claim()
    pending = request_claim_release(
        ClaimReleaseIntentRequest(target_action_id=frozen.action_id, reason="Frozen."),
        RELEASE_REQUESTER,
    )
    approve_claim_release(
        ClaimReleaseApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
        ),
        RELEASE_APPROVER,
    )

    store = get_provider_operations_store()
    real_get = store.get_governed_action

    def _target_vanished(action_id: str) -> GovernedActionRecord | None:
        if action_id == frozen.action_id:
            return None
        return real_get(action_id)

    monkeypatch.setattr(store, "get_governed_action", _target_vanished)
    with pytest.raises(HTTPException) as refusal:
        approve_claim_release(
            ClaimReleaseApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            RELEASE_APPROVER,
        )
    assert refusal.value.status_code == 409


def test_execute_refuses_when_the_target_left_claimed_after_freshness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The defensive execute-time recheck: the freshness rebuild passed, but
    the target left CLAIMED before the release's CAS ran - bounded 409,
    nothing changed."""

    frozen = _frozen_claim()
    pending = request_claim_release(
        ClaimReleaseIntentRequest(target_action_id=frozen.action_id, reason="Frozen."),
        RELEASE_REQUESTER,
    )

    store = get_provider_operations_store()
    real_get = store.get_governed_action
    calls = {"count": 0}

    def _flips_after_freshness(action_id: str) -> GovernedActionRecord | None:
        record = real_get(action_id)
        if action_id == frozen.action_id and record is not None:
            calls["count"] += 1
            if calls["count"] >= 2:
                # By the execute-time recheck the claim has finalized.
                return record.model_copy(update={"status": GovernedActionStatus.EXECUTED})
        return record

    monkeypatch.setattr(store, "get_governed_action", _flips_after_freshness)
    with pytest.raises(HTTPException) as refusal:
        approve_claim_release(
            ClaimReleaseApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            RELEASE_APPROVER,
        )
    assert refusal.value.status_code == 409
