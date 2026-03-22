from __future__ import annotations

from app.config import settings
from app.services.capability_catalog import get_capability_by_task_id


def list_live_text_allowlisted_task_ids() -> list[str]:
    allowlisted = [
        item.strip() for item in settings.live_text_allowed_task_ids.split(",") if item.strip()
    ]
    return sorted(dict.fromkeys(allowlisted))


def list_invalid_live_text_allowlisted_task_ids() -> list[str]:
    return [
        task_id
        for task_id in list_live_text_allowlisted_task_ids()
        if get_capability_by_task_id(task_id) is None or task_id.startswith("knowledge_")
    ]


def is_live_text_task_allowlisted(task_id: str) -> bool:
    return task_id in list_live_text_allowlisted_task_ids()
