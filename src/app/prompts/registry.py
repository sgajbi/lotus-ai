from __future__ import annotations

from app.contracts.prompts import PromptDescriptor

_PROMPTS: dict[str, PromptDescriptor] = {
    "explain.v1": PromptDescriptor(
        task_id="explain.v1",
        prompt_version="foundation.explain.v1",
        prompt_kind="system",
        system_instructions=(
            "Explain structured Lotus domain outputs clearly, conservatively, and without "
            "inventing missing business facts."
        ),
        output_contract_notes=(
            "Output must remain explanation-oriented, enterprise-safe, and non-authoritative."
        ),
    ),
    "summarize.v1": PromptDescriptor(
        task_id="summarize.v1",
        prompt_version="foundation.summarize.v1",
        prompt_kind="system",
        system_instructions=(
            "Summarize caller-provided structured inputs into concise, decision-supporting text."
        ),
        output_contract_notes="Output is a draft summary, not business truth.",
    ),
    "classify.v1": PromptDescriptor(
        task_id="classify.v1",
        prompt_version="foundation.classify.v1",
        prompt_kind="system",
        system_instructions=(
            "Classify caller-provided structured content into bounded categories only."
        ),
        output_contract_notes="Classification must remain within caller-approved label sets.",
    ),
    "extract.v1": PromptDescriptor(
        task_id="extract.v1",
        prompt_version="foundation.extract.v1",
        prompt_kind="system",
        system_instructions="Extract structured fields from curated caller content.",
        output_contract_notes="Extraction output must stay schema-bound and conservative.",
    ),
    "generate_structured.v1": PromptDescriptor(
        task_id="generate_structured.v1",
        prompt_version="foundation.generate_structured.v1",
        prompt_kind="system",
        system_instructions=(
            "Generate schema-bound structured output from curated caller context."
        ),
        output_contract_notes="Generated output must remain draft-only and schema-bound.",
    ),
    "knowledge_search.v1": PromptDescriptor(
        task_id="knowledge_search.v1",
        prompt_version="foundation.knowledge_search.v1",
        prompt_kind="system",
        system_instructions="Search approved Lotus knowledge sources with traceable provenance.",
        output_contract_notes="Citations and source attribution are mandatory when enabled.",
    ),
    "knowledge_answer.v1": PromptDescriptor(
        task_id="knowledge_answer.v1",
        prompt_version="foundation.knowledge_answer.v1",
        prompt_kind="system",
        system_instructions=(
            "Answer questions from approved Lotus knowledge sources with explicit citations."
        ),
        output_contract_notes="Refuse when sources are insufficient or unsupported.",
    ),
}


def get_prompt_by_task_id(task_id: str) -> PromptDescriptor | None:
    return _PROMPTS.get(task_id)


def list_prompts() -> list[PromptDescriptor]:
    return list(_PROMPTS.values())
