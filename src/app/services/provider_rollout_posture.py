from __future__ import annotations

from dataclasses import dataclass

from app.contracts.providers import ProviderRolloutState
from app.services.provider_live_execution_state import build_provider_live_execution_state
from app.services.provider_configuration_status import (
    build_text_generation_configuration_status,
)


@dataclass(frozen=True)
class ProviderRolloutPosture:
    rollout_state: ProviderRolloutState
    configuration_valid: bool
    live_path_configured: bool
    notes: str


def build_provider_rollout_posture() -> ProviderRolloutPosture:
    configuration = build_text_generation_configuration_status()
    live_execution_state = build_provider_live_execution_state()
    live_path_configured = (
        configuration.configured_live_provider_id is not None
        and configuration.configured_live_model_id is not None
    )

    if not configuration.configuration_valid:
        notes = (
            "Live-provider rollout posture is configured inconsistently and must remain blocked "
            "until allowlisted provider, model, and credential settings are corrected."
        )
    elif configuration.rollout_state == ProviderRolloutState.STUB_DEFAULT:
        notes = (
            "Provider-backed tasks remain on the deterministic stub path because live-provider "
            "rollout has not moved beyond the stub-default posture."
        )
    elif configuration.rollout_state == ProviderRolloutState.ALLOWLISTED_DISABLED:
        notes = (
            "A governed live-provider path is allowlisted, but runtime execution remains "
            "intentionally disabled pending operational approval and rollout review."
        )
    elif configuration.rollout_state == ProviderRolloutState.CANARY_ENABLED:
        notes = (
            "Live-provider rollout is in canary posture. Provider-backed tasks can execute live "
            "only when runtime mode requests the live adapter and the task is allowlisted."
        )
    elif configuration.rollout_state == ProviderRolloutState.ROLLED_OUT:
        notes = (
            "Live-provider rollout posture is marked rolled out, but runtime mode, task "
            "allowlisting, and governance controls still determine whether provider-backed "
            "execution is truly active."
        )
    else:
        notes = "Provider rollout remains documented but not yet allowlisted for live execution."
    if (
        live_execution_state.live_mode_requested
        and live_execution_state.blocking_reason is not None
    ):
        notes = f"{notes} {live_execution_state.blocking_reason}"

    return ProviderRolloutPosture(
        rollout_state=configuration.rollout_state,
        configuration_valid=configuration.configuration_valid,
        live_path_configured=live_path_configured,
        notes=notes,
    )
