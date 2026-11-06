"""Tasks management endpoints for sales workflow and daily action items (Stage 6 Task 4)."""

from datetime import datetime, time, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.database import get_supabase_client
from backend.dependencies import get_current_user, get_owned_task
from backend.models.task import (
    SnoozePreset,
    TaskGroupCounts,
    TaskListResponse,
    TaskPriority,
    TaskResponse,
    TaskStatus,
    TaskType,
    UpdateTaskRequest,
)

logger = logging.getLogger("signalforge.tasks")

router = APIRouter(tags=["tasks"])

IST = timezone(timedelta(hours=5, minutes=30))

ALLOWED_TASK_STATUSES = {s.value for s in TaskStatus}
ALLOWED_TASK_PRIORITIES = {p.value for p in TaskPriority}
ALLOWED_SNOOZE_PRESETS = {p.value for p in SnoozePreset}

PRIORITY_WEIGHTS = {
    "urgent": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


def _enrich_tasks_with_names(
    db: Any,
    tasks: List[Dict[str, Any]],
) -> List[TaskResponse]:
    """Batch-lookup lead business names and campaign names to enrich task objects."""
    if not tasks:
        return []

    lead_ids = list({t["lead_id"] for t in tasks if t.get("lead_id")})
    campaign_ids = list({t["campaign_id"] for t in tasks if t.get("campaign_id")})

    lead_map: Dict[str, str] = {}
    if lead_ids:
        try:
            leads_res = db.table("leads").select("id, business_name").in_("id", lead_ids).execute()
            for l in (leads_res.data or []):
                lead_map[l["id"]] = l.get("business_name") or "Unnamed Lead"
        except Exception as exc:
            logger.warning(f"Error resolving lead names for tasks: {exc}")

    campaign_map: Dict[str, str] = {}
    if campaign_ids:
        try:
            camps_res = db.table("campaigns").select("id, name").in_("id", campaign_ids).execute()
            for c in (camps_res.data or []):
                campaign_map[c["id"]] = c.get("name") or "Unnamed Campaign"
        except Exception as exc:
            logger.warning(f"Error resolving campaign names for tasks: {exc}")

    enriched: List[TaskResponse] = []
    for t in tasks:
        enriched.append(
            TaskResponse(
                id=t["id"],
                lead_id=t.get("lead_id"),
                lead_name=lead_map.get(t.get("lead_id")),
                campaign_id=t.get("campaign_id"),
                campaign_name=campaign_map.get(t.get("campaign_id")),
                user_id=t["user_id"],
                task_type=t["task_type"],
                title=t["title"],
                description=t.get("description") or "",
                status=t["status"],
                priority=t["priority"],
                due_date=t.get("due_date"),
                snoozed_until=t.get("snoozed_until"),
                completed_at=t.get("completed_at"),
                created_at=t.get("created_at"),
                updated_at=t.get("updated_at"),
            )
        )
    return enriched


def _compute_snooze_time(preset: str) -> datetime:
    """Calculate target UTC datetime for given snooze preset in IST context."""
    now_ist = datetime.now(IST)
    if preset == SnoozePreset.LATER_TODAY.value:
        target_ist = now_ist + timedelta(hours=4)
    elif preset == SnoozePreset.TOMORROW.value:
        next_day = now_ist.date() + timedelta(days=1)
        target_ist = datetime.combine(next_day, time(9, 0), tzinfo=IST)
    elif preset == SnoozePreset.NEXT_WEEK.value:
        next_week = now_ist.date() + timedelta(days=7)
        target_ist = datetime.combine(next_week, time(9, 0), tzinfo=IST)
    else:
        target_ist = now_ist + timedelta(days=1)
    return target_ist.astimezone(timezone.utc)


@router.get(
    "/tasks",
    summary="Get User Tasks",
    description="Returns user's sales tasks with optional filters and timeframe grouping counters.",
    status_code=status.HTTP_200_OK,
)
async def list_tasks(
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by task status ('pending', 'in_progress', 'completed', 'snoozed', 'cancelled')",
    ),
    priority_filter: Optional[str] = Query(
        default=None,
        alias="priority",
        description="Filter by priority ('urgent', 'high', 'medium', 'low')",
    ),
    lead_id: Optional[str] = Query(default=None, description="Filter by lead ID"),
    campaign_id: Optional[str] = Query(default=None, description="Filter by campaign ID"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve filtered tasks for the current user and timeframe counts."""
    db = get_supabase_client()
    user_id = user["id"]

    # Validate UUID formats and user ownership if provided
    for param_name, param_val in [("lead_id", lead_id), ("campaign_id", campaign_id)]:
        if param_val:
            try:
                UUID(param_val.strip())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Resource with ID '{param_val}' not found",
                )

    if campaign_id:
        camp_res = (
            db.table("campaigns")
            .select("id")
            .eq("id", campaign_id.strip())
            .eq("user_id", user_id)
            .execute()
        )
        if not camp_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign with ID '{campaign_id}' not found",
            )

    if lead_id:
        # Check that lead belongs to one of user's campaigns
        user_camps_res = db.table("campaigns").select("id").eq("user_id", user_id).execute()
        user_camp_ids = [c["id"] for c in (user_camps_res.data or [])]
        lead_res = (
            db.table("leads")
            .select("id")
            .eq("id", lead_id.strip())
            .in_("campaign_id", user_camp_ids)
            .execute()
        )
        if not lead_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead with ID '{lead_id}' not found",
            )

    if status_filter and status_filter not in ALLOWED_TASK_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid task status '{status_filter}'. Permitted values: {', '.join(sorted(ALLOWED_TASK_STATUSES))}",
        )

    if priority_filter and priority_filter not in ALLOWED_TASK_PRIORITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid task priority '{priority_filter}'. Permitted values: {', '.join(sorted(ALLOWED_TASK_PRIORITIES))}",
        )

    # 1. Fetch all user tasks for counter calculation
    try:
        all_user_tasks_res = (
            db.table("tasks")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        all_user_tasks = all_user_tasks_res.data or []
    except Exception as exc:
        logger.error(f"Error querying tasks for user {user_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tasks",
        ) from exc

    # 2. Compute group counts according to UI-UX.md §6.9 (Overdue, Today, Upcoming, Completed)
    now_utc = datetime.now(timezone.utc)
    now_ist = datetime.now(IST)
    today_start_ist = datetime.combine(now_ist.date(), time.min, tzinfo=IST).astimezone(timezone.utc)
    today_end_ist = datetime.combine(now_ist.date(), time.max, tzinfo=IST).astimezone(timezone.utc)

    overdue_cnt = 0
    today_cnt = 0
    upcoming_cnt = 0
    completed_cnt = 0

    for t in all_user_tasks:
        t_status = t.get("status")
        if t_status == TaskStatus.COMPLETED.value:
            completed_cnt += 1
            continue

        if t_status in (TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value):
            raw_due = t.get("due_date")
            if raw_due:
                try:
                    due_dt = datetime.fromisoformat(str(raw_due).replace("Z", "+00:00"))
                    if due_dt.tzinfo is None:
                        due_dt = due_dt.replace(tzinfo=timezone.utc)
                    if due_dt < today_start_ist:
                        overdue_cnt += 1
                    elif today_start_ist <= due_dt <= today_end_ist:
                        today_cnt += 1
                    else:
                        upcoming_cnt += 1
                except Exception:
                    upcoming_cnt += 1
            else:
                upcoming_cnt += 1

    counts = TaskGroupCounts(
        overdue=overdue_cnt,
        today=today_cnt,
        upcoming=upcoming_cnt,
        completed=completed_cnt,
        total=len(all_user_tasks),
    )

    # 3. Filter and paginate tasks for the response list
    filtered_tasks = all_user_tasks
    if status_filter:
        filtered_tasks = [t for t in filtered_tasks if t.get("status") == status_filter]
    if priority_filter:
        filtered_tasks = [t for t in filtered_tasks if t.get("priority") == priority_filter]
    if lead_id:
        filtered_tasks = [t for t in filtered_tasks if t.get("lead_id") == lead_id.strip()]
    if campaign_id:
        filtered_tasks = [t for t in filtered_tasks if t.get("campaign_id") == campaign_id.strip()]

    # Sort tasks: open tasks first, due_date ascending (None last), created_at desc
    def _sort_key(item: Dict[str, Any]):
        p_val = PRIORITY_WEIGHTS.get(item.get("priority", "medium"), 2)
        raw_due = item.get("due_date")
        has_due = 0 if raw_due else 1
        due_str = raw_due or "9999-12-31T23:59:59Z"
        created_str = item.get("created_at") or ""
        ts = 0.0
        if created_str:
            try:
                ts = datetime.fromisoformat(str(created_str).replace("Z", "+00:00")).timestamp()
            except Exception:
                ts = 0.0
        return (has_due, due_str, p_val, -ts)

    filtered_tasks.sort(key=_sort_key)
    paginated_tasks = filtered_tasks[offset : offset + limit]

    enriched = _enrich_tasks_with_names(db, paginated_tasks)

    return {
        "data": TaskListResponse(
            tasks=enriched,
            counts=counts,
        ).model_dump(mode="json"),
        "message": "Tasks retrieved successfully",
    }


@router.get(
    "/tasks/upcoming",
    summary="Get Upcoming Tasks Work Queue",
    description="Returns open (pending/in_progress) tasks ordered by due date and priority for Today view.",
    status_code=status.HTTP_200_OK,
)
async def get_upcoming_tasks(
    limit: int = Query(default=10, ge=1, le=50),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve actionable open tasks for the Today action center."""
    db = get_supabase_client()
    user_id = user["id"]

    try:
        res = (
            db.table("tasks")
            .select("*")
            .eq("user_id", user_id)
            .in_("status", [TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value])
            .execute()
        )
        tasks = res.data or []
    except Exception as exc:
        logger.error(f"Error querying upcoming tasks for user {user_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve upcoming tasks",
        ) from exc

    def _upcoming_sort_key(item: Dict[str, Any]):
        raw_due = item.get("due_date")
        has_due = 0 if raw_due else 1
        due_str = raw_due or "9999-12-31T23:59:59Z"
        p_val = PRIORITY_WEIGHTS.get(item.get("priority", "medium"), 2)
        return (has_due, due_str, p_val)

    tasks.sort(key=_upcoming_sort_key)
    enriched = _enrich_tasks_with_names(db, tasks[:limit])

    return {
        "data": [t.model_dump(mode="json") for t in enriched],
        "message": "Upcoming tasks retrieved successfully",
    }


@router.put(
    "/tasks/{id}",
    summary="Update Task",
    description="Update task status (complete, snooze, reopen), priority, due date, or notes.",
    status_code=status.HTTP_200_OK,
)
async def update_task(
    id: str,
    payload: UpdateTaskRequest,
    task: Dict[str, Any] = Depends(get_owned_task),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update task attributes, managing completion and snooze transitions."""
    db = get_supabase_client()
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()

    update_data: Dict[str, Any] = {
        "updated_at": now_iso,
    }

    # 1. Status transition & completion handling
    target_status = payload.status
    if target_status is not None:
        if target_status not in ALLOWED_TASK_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid task status '{target_status}'. Permitted values: {', '.join(sorted(ALLOWED_TASK_STATUSES))}",
            )
        update_data["status"] = target_status

        if target_status == TaskStatus.COMPLETED.value:
            update_data["completed_at"] = now_iso
            update_data["snoozed_until"] = None
        elif target_status in (TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value):
            update_data["completed_at"] = None
            update_data["snoozed_until"] = None

    # 2. Snooze handling (via preset or custom timestamp)
    if payload.snooze_preset is not None:
        if payload.snooze_preset not in ALLOWED_SNOOZE_PRESETS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid snooze preset '{payload.snooze_preset}'. Permitted values: {', '.join(sorted(ALLOWED_SNOOZE_PRESETS))}",
            )
        snooze_dt = _compute_snooze_time(payload.snooze_preset)
        update_data["status"] = TaskStatus.SNOOZED.value
        update_data["snoozed_until"] = snooze_dt.isoformat()
        update_data["completed_at"] = None
    elif payload.snoozed_until is not None:
        target_snooze = payload.snoozed_until
        if target_snooze.tzinfo is None:
            target_snooze = target_snooze.replace(tzinfo=timezone.utc)
        if target_snooze <= now_utc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Snooze time must be in the future",
            )
        update_data["status"] = TaskStatus.SNOOZED.value
        update_data["snoozed_until"] = target_snooze.isoformat()
        update_data["completed_at"] = None
    elif target_status == TaskStatus.SNOOZED.value and not task.get("snoozed_until"):
        # Default snooze if none specified is tomorrow 09:00 IST
        snooze_dt = _compute_snooze_time(SnoozePreset.TOMORROW.value)
        update_data["snoozed_until"] = snooze_dt.isoformat()
        update_data["completed_at"] = None

    # 3. Priority update
    if payload.priority is not None:
        if payload.priority not in ALLOWED_TASK_PRIORITIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid task priority '{payload.priority}'. Permitted values: {', '.join(sorted(ALLOWED_TASK_PRIORITIES))}",
            )
        update_data["priority"] = payload.priority

    # 4. Content and date updates
    if payload.title is not None:
        title_stripped = payload.title.strip()
        if not title_stripped:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task title cannot be empty",
            )
        update_data["title"] = title_stripped

    if payload.description is not None:
        update_data["description"] = payload.description.strip()

    if payload.due_date is not None:
        update_data["due_date"] = payload.due_date.isoformat()

    # 5. Persist updates to database
    try:
        upd_res = (
            db.table("tasks")
            .update(update_data)
            .eq("id", id)
            .eq("user_id", user["id"])
            .execute()
        )
        updated_row = upd_res.data[0] if upd_res.data else {**task, **update_data}
    except Exception as exc:
        logger.error(f"Error updating task {id} for user {user['id']}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update task",
        ) from exc

    enriched_list = _enrich_tasks_with_names(db, [updated_row])
    result_model = enriched_list[0] if enriched_list else TaskResponse(**updated_row)

    logger.info(f"Task {id} updated by user {user['id']} (status: {result_model.status})")
    return {
        "data": result_model.model_dump(mode="json"),
        "message": "Task updated successfully",
    }

