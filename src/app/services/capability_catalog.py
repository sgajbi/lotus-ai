from __future__ import annotations

from app.config import settings
from app.contracts.tasks import (
    CapabilityCatalogResponse,
    CapabilityDescriptor,
    OutputLabel,
    TaskCategory,
)


def build_capability_catalog() -> CapabilityCatalogResponse:
    return CapabilityCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        tasks=[
            CapabilityDescriptor(
                task_id="explain.v1",
                category=TaskCategory.EXPLAIN,
                enabled=True,
                output_label=OutputLabel.EXPLANATION_ONLY,
                description="Explain structured Lotus domain outputs in plain English.",
            ),
            CapabilityDescriptor(
                task_id="summarize.v1",
                category=TaskCategory.SUMMARIZE,
                enabled=True,
                output_label=OutputLabel.DRAFT,
                description="Summarize structured inputs into concise, governed narrative output.",
            ),
            CapabilityDescriptor(
                task_id="classify.v1",
                category=TaskCategory.CLASSIFY,
                enabled=True,
                output_label=OutputLabel.CLASSIFICATION,
                description="Classify structured content into bounded output categories.",
            ),
            CapabilityDescriptor(
                task_id="extract.v1",
                category=TaskCategory.EXTRACT,
                enabled=True,
                output_label=OutputLabel.DRAFT,
                description="Extract structured fields from caller-provided content.",
            ),
            CapabilityDescriptor(
                task_id="generate_structured.v1",
                category=TaskCategory.GENERATE_STRUCTURED,
                enabled=True,
                output_label=OutputLabel.DRAFT,
                description="Generate schema-bound structured output from curated context.",
            ),
            CapabilityDescriptor(
                task_id="knowledge_search.v1",
                category=TaskCategory.KNOWLEDGE_SEARCH,
                enabled=False,
                output_label=OutputLabel.RETRIEVAL_ANSWER,
                description="Search approved Lotus knowledge sources with source attribution.",
            ),
            CapabilityDescriptor(
                task_id="knowledge_answer.v1",
                category=TaskCategory.KNOWLEDGE_ANSWER,
                enabled=False,
                output_label=OutputLabel.RETRIEVAL_ANSWER,
                description="Answer questions from approved Lotus knowledge sources with citations.",
            ),
        ],
    )
