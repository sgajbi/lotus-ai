from __future__ import annotations

from dataclasses import dataclass

from app.contracts.access_control import AuthorizationDecision
from app.contracts.prompts import PromptDescriptor, PromptSelectionTraceDescriptor
from app.contracts.providers import ProviderExecutionResponse
from app.contracts.safety import SafetyExecutionOutcome
from app.contracts.tasks import CapabilityDescriptor, TaskExecutionRequest


@dataclass(frozen=True)
class TaskExecutionContext:
    request: TaskExecutionRequest
    capability: CapabilityDescriptor
    authorization: AuthorizationDecision
    prompt: PromptDescriptor
    prompt_selection: PromptSelectionTraceDescriptor
    safety_outcome: SafetyExecutionOutcome
    request_id: str
    generated_at: str


@dataclass(frozen=True)
class ResolvedTaskExecution:
    context: TaskExecutionContext
    provider_execution: ProviderExecutionResponse
    safety_outcome: SafetyExecutionOutcome
