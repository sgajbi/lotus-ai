from __future__ import annotations

from app.contracts.prompts import (
    PromptDescriptor,
    PromptLifecycleStatus,
    PromptManagementMode,
)

_PROMPTS: list[PromptDescriptor] = [
    PromptDescriptor(
        task_id="explain.v1",
        prompt_version="foundation.explain.v1",
        prompt_kind="system",
        lifecycle_status=PromptLifecycleStatus.ACTIVE,
        management_mode=PromptManagementMode.SEEDED_MEMORY,
        source_reference="app.prompts.registry:_PROMPTS",
        system_instructions=(
            "Explain structured Lotus domain outputs clearly, conservatively, and without "
            "inventing missing business facts."
        ),
        output_contract_notes=(
            "Output must remain explanation-oriented, enterprise-safe, and non-authoritative."
        ),
    ),
    PromptDescriptor(
        task_id="explain.v1",
        prompt_version="foundation.explain.v2",
        prompt_kind="system",
        lifecycle_status=PromptLifecycleStatus.CANDIDATE,
        management_mode=PromptManagementMode.SEEDED_MEMORY,
        source_reference="app.prompts.registry:_PROMPTS",
        system_instructions=(
            "Explain structured Lotus domain outputs clearly, conservatively, and ground the "
            "response in the supplied fields before adding decision-support framing."
        ),
        output_contract_notes=(
            "Output must remain explanation-oriented, enterprise-safe, non-authoritative, "
            "and concise enough for operator review."
        ),
    ),
    PromptDescriptor(
        task_id="summarize.v1",
        prompt_version="foundation.summarize.v1",
        prompt_kind="system",
        lifecycle_status=PromptLifecycleStatus.ACTIVE,
        management_mode=PromptManagementMode.SEEDED_MEMORY,
        source_reference="app.prompts.registry:_PROMPTS",
        system_instructions=(
            "Summarize caller-provided structured inputs into concise, decision-supporting text."
        ),
        output_contract_notes="Output is a draft summary, not business truth.",
    ),
    PromptDescriptor(
        task_id="classify.v1",
        prompt_version="foundation.classify.v1",
        prompt_kind="system",
        lifecycle_status=PromptLifecycleStatus.ACTIVE,
        management_mode=PromptManagementMode.SEEDED_MEMORY,
        source_reference="app.prompts.registry:_PROMPTS",
        system_instructions=(
            "Classify caller-provided structured content into bounded categories only."
        ),
        output_contract_notes="Classification must remain within caller-approved label sets.",
    ),
    PromptDescriptor(
        task_id="extract.v1",
        prompt_version="foundation.extract.v1",
        prompt_kind="system",
        lifecycle_status=PromptLifecycleStatus.ACTIVE,
        management_mode=PromptManagementMode.SEEDED_MEMORY,
        source_reference="app.prompts.registry:_PROMPTS",
        system_instructions="Extract structured fields from curated caller content.",
        output_contract_notes="Extraction output must stay schema-bound and conservative.",
    ),
    PromptDescriptor(
        task_id="generate_structured.v1",
        prompt_version="foundation.generate_structured.v1",
        prompt_kind="system",
        lifecycle_status=PromptLifecycleStatus.ACTIVE,
        management_mode=PromptManagementMode.SEEDED_MEMORY,
        source_reference="app.prompts.registry:_PROMPTS",
        system_instructions=(
            "Generate schema-bound structured output from curated caller context."
        ),
        output_contract_notes="Generated output must remain draft-only and schema-bound.",
    ),
    PromptDescriptor(
        task_id="knowledge_search.v1",
        prompt_version="foundation.knowledge_search.v1",
        prompt_kind="system",
        lifecycle_status=PromptLifecycleStatus.ACTIVE,
        management_mode=PromptManagementMode.SEEDED_MEMORY,
        source_reference="app.prompts.registry:_PROMPTS",
        system_instructions="Search approved Lotus knowledge sources with traceable provenance.",
        output_contract_notes="Citations and source attribution are mandatory when enabled.",
    ),
    PromptDescriptor(
        task_id="knowledge_answer.v1",
        prompt_version="foundation.knowledge_answer.v1",
        prompt_kind="system",
        lifecycle_status=PromptLifecycleStatus.ACTIVE,
        management_mode=PromptManagementMode.SEEDED_MEMORY,
        source_reference="app.prompts.registry:_PROMPTS",
        system_instructions=(
            "Answer questions from approved Lotus knowledge sources with explicit citations."
        ),
        output_contract_notes="Refuse when sources are insufficient or unsupported.",
    ),
    PromptDescriptor(
        task_id="knowledge_answer.v1",
        prompt_version="foundation.knowledge_answer.v2",
        prompt_kind="system",
        lifecycle_status=PromptLifecycleStatus.CANDIDATE,
        management_mode=PromptManagementMode.SEEDED_MEMORY,
        source_reference="app.prompts.registry:_PROMPTS",
        system_instructions=(
            "Answer questions from approved Lotus knowledge sources with explicit citations, "
            "call out weak support plainly, and prefer refusal over unsupported synthesis."
        ),
        output_contract_notes=(
            "Refuse when sources are insufficient or unsupported, and keep the answer "
            "operator-reviewable."
        ),
    ),
]


def get_prompt_by_task_id(task_id: str) -> PromptDescriptor | None:
    for prompt in _PROMPTS:
        if prompt.task_id == task_id and prompt.lifecycle_status == PromptLifecycleStatus.ACTIVE:
            return prompt
    return None


def list_prompts() -> list[PromptDescriptor]:
    return list(_PROMPTS)
