from __future__ import annotations

from fastapi import APIRouter

from app.contracts.prompts import PromptDescriptor
from app.services.prompt_registry import get_prompt_or_raise, list_registered_prompts

router = APIRouter(prefix="/platform/prompts", tags=["platform"])


@router.get(
    "",
    response_model=list[PromptDescriptor],
    summary="List registered lotus-ai prompts",
    description=(
        "Returns the currently registered prompt definitions known to lotus-ai. "
        "This endpoint is intended for platform transparency and engineering inspection."
    ),
)
async def list_prompts_route() -> list[PromptDescriptor]:
    return list_registered_prompts()


@router.get(
    "/{task_id}",
    response_model=PromptDescriptor,
    summary="Get lotus-ai prompt definition",
    description="Returns the registered prompt definition associated with a task identifier.",
)
async def get_prompt_route(task_id: str) -> PromptDescriptor:
    return get_prompt_or_raise(task_id)
