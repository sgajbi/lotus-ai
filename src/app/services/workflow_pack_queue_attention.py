from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.contracts.workflow_pack_queue_policies import WorkflowPackQueueStatusItemDescriptor
from app.contracts.workflow_packs import (
    WorkflowPackQueueAttentionItemResponse,
    WorkflowPackQueueAttentionSummaryResponse,
    WorkflowPackQueueAttentionType,
)
from app.services.workflow_pack_queue_policy_catalog import (
    build_workflow_pack_queue_status,
    get_workflow_pack_queue_policy_descriptor,
)

WORKFLOW_PACK_QUEUE_ATTENTION_LIMIT = 5


def build_workflow_pack_queue_attention_summary(
    *,
    now_utc: datetime | None = None,
) -> WorkflowPackQueueAttentionSummaryResponse:
    queue_status = build_workflow_pack_queue_status()
    now = now_utc or datetime.now(UTC)
    saturated_items = [
        WorkflowPackQueueAttentionItemResponse(
            attention_type=WorkflowPackQueueAttentionType.LANE_SATURATED,
            policy_id=lane_status.policy_id,
            workflow_pack_id=lane_status.workflow_pack_id,
            workflow_pack_version=lane_status.workflow_pack_version,
            lane=lane_status.lane,
            queue_item_id=None,
            active_count=lane_status.active_count,
            max_concurrent_runs_per_lane=lane_status.max_concurrent_runs_per_lane,
            admitted_at=None,
            attention_reasons=[
                "Workflow-pack queue lane is at or above its saturation attention threshold."
            ],
        )
        for lane_status in queue_status.lane_statuses
        if lane_status.saturation_status.value == "SATURATED"
    ]
    stale_items = _build_stale_queue_attention_items(
        active_items=queue_status.active_items,
        now=now,
    )
    attention_items = saturated_items + stale_items
    status_summary = [
        "Workflow-pack queue heartbeat attention is derived from queue source posture and does not replace run-ledger, review, or task-flow state.",
        "First-wave queue attention covers active-admission saturation and stale active admissions from the current queue source.",
        "Historical timeout, cancellation, and retry-cluster attention requires a durable queue-event source before it can be reported truthfully.",
    ]
    if len(attention_items) > WORKFLOW_PACK_QUEUE_ATTENTION_LIMIT:
        status_summary.append(
            "Returned queue attention items are truncated to the bounded attention limit; use attention_count to measure the full backlog."
        )
    return WorkflowPackQueueAttentionSummaryResponse(
        heartbeat_status="READY" if not attention_items else "ATTENTION_REQUIRED",
        attention_count=len(attention_items),
        saturated_lane_count=len(saturated_items),
        stale_item_count=len(stale_items),
        active_admission_count=queue_status.active_admission_count,
        queue_source_mode=queue_status.queue_source_mode,
        attention_limit=WORKFLOW_PACK_QUEUE_ATTENTION_LIMIT,
        items=attention_items[:WORKFLOW_PACK_QUEUE_ATTENTION_LIMIT],
        status_summary=status_summary,
    )


def _build_stale_queue_attention_items(
    *,
    active_items: list[WorkflowPackQueueStatusItemDescriptor],
    now: datetime,
) -> list[WorkflowPackQueueAttentionItemResponse]:
    items: list[WorkflowPackQueueAttentionItemResponse] = []
    for active_item in active_items:
        policy = get_workflow_pack_queue_policy_descriptor(
            pack_id=active_item.workflow_pack_id,
            version=active_item.workflow_pack_version,
        )
        if policy is None:
            continue
        admitted_at = _parse_utc_timestamp(active_item.admitted_at)
        if admitted_at is None:
            is_stale = True
        else:
            is_stale = now - admitted_at > timedelta(seconds=policy.stale_queue_threshold_seconds)
        if not is_stale:
            continue
        items.append(
            WorkflowPackQueueAttentionItemResponse(
                attention_type=WorkflowPackQueueAttentionType.QUEUE_ITEM_STALE,
                policy_id=active_item.policy_id,
                workflow_pack_id=active_item.workflow_pack_id,
                workflow_pack_version=active_item.workflow_pack_version,
                lane=active_item.lane,
                queue_item_id=active_item.queue_item_id,
                active_count=1,
                max_concurrent_runs_per_lane=policy.max_concurrent_runs_per_lane,
                admitted_at=active_item.admitted_at,
                attention_reasons=[
                    "Workflow-pack queue item has exceeded the policy stale queue threshold."
                ],
            )
        )
    return items


def _parse_utc_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
