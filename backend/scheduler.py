"""Background Job Scheduler for SignalForge AI using APScheduler.

Configures and manages in-process recurring asynchronous tasks:
- Hourly follow-up checking (drafting messages, quiet hours deferral, task creation).
- Periodic stale job recovery (discovering and auditing jobs stuck > 15 minutes).
- Automatic task un-snoozing when snoozed_until timestamp has passed.

Per docs/decisions.md Section 9:
- Runs inside a single uvicorn worker process.
- Job execution state lives in the database, never solely in memory.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.database import get_supabase_client

logger = logging.getLogger("signalforge.scheduler")

# Module-level singleton
_scheduler: Optional[AsyncIOScheduler] = None


async def run_followup_check_job(db_client: Any = None) -> Dict[str, Any]:
    """Evaluate due followups, generate drafts, and create approval tasks."""
    logger.info("Executing scheduled job: check_pending_followups")
    try:
        from backend.services.followup import FollowupService

        svc = FollowupService(db_client=db_client)
        result = await svc.check_pending_followups()
        logger.info(
            f"Follow-up check completed: {result.get('checked', 0)} checked, "
            f"{result.get('drafted', 0)} drafted, {result.get('deferred', 0)} deferred, "
            f"{result.get('cancelled', 0)} cancelled"
        )
        return result
    except Exception as exc:
        logger.error(f"Error in scheduled follow-up check job: {exc}", exc_info=True)
        return {"error": str(exc)}


async def run_stale_jobs_recovery_job(db_client: Any = None) -> Dict[str, int]:
    """Reset stale discovering campaigns and running audits per decisions.md §9."""
    logger.info("Executing scheduled job: recover_stale_jobs")
    try:
        from backend.main import recover_stale_discovery_jobs, recover_stale_audit_jobs

        recovered_disc = await recover_stale_discovery_jobs()
        recovered_audit = await recover_stale_audit_jobs()
        logger.info(
            f"Stale job recovery completed: {recovered_disc} discovery jobs, {recovered_audit} audit jobs"
        )
        return {"discovery_recovered": recovered_disc, "audit_recovered": recovered_audit}
    except Exception as exc:
        logger.error(f"Error in scheduled stale job recovery: {exc}", exc_info=True)
        return {"error": 1}


async def run_unsnooze_tasks_job(db_client: Any = None, user_id: Optional[str] = None) -> int:
    """Reset snoozed tasks whose snoozed_until timestamp has elapsed back to pending.

    Args:
        db_client: Optional injected database client.
        user_id: Optional UUID to scope task unsnoozing to a single tenant.

    Returns:
        Number of unsnoozed tasks.
    """
    logger.info(f"Executing scheduled job: unsnooze_expired_tasks (user_id={user_id or 'all'})")
    try:
        db = db_client or get_supabase_client()
        now_iso = datetime.now(timezone.utc).isoformat()

        query = (
            db.table("tasks")
            .select("id")
            .eq("status", "snoozed")
            .lte("snoozed_until", now_iso)
        )
        if user_id:
            query = query.eq("user_id", user_id)

        res = query.execute()
        tasks_to_unsnooze = res.data or []
        if not tasks_to_unsnooze:
            return 0

        task_ids = [t["id"] for t in tasks_to_unsnooze]
        update_query = (
            db.table("tasks")
            .update({
                "status": "pending",
                "snoozed_until": None,
                "updated_at": now_iso,
            })
            .in_("id", task_ids)
        )
        if user_id:
            update_query = update_query.eq("user_id", user_id)

        update_query.execute()

        logger.info(f"Unsnoozed {len(task_ids)} task(s) whose snooze period expired")
        return len(task_ids)
    except Exception as exc:
        logger.error(f"Error in unsnooze tasks job: {exc}", exc_info=True)
        return 0


def get_scheduler() -> AsyncIOScheduler:
    """Return the global AsyncIOScheduler singleton, initializing if needed."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


def start_scheduler(
    followup_interval_hours: int = 1,
    recovery_interval_minutes: int = 15,
    unsnooze_interval_minutes: int = 30,
) -> AsyncIOScheduler:
    """Start the APScheduler background worker and register recurring jobs."""
    scheduler = get_scheduler()

    # 1. Hourly follow-up evaluation job
    if not scheduler.get_job("job_check_followups"):
        scheduler.add_job(
            run_followup_check_job,
            trigger=IntervalTrigger(hours=followup_interval_hours),
            id="job_check_followups",
            name="Check pending outreach follow-ups",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

    # 2. Periodic stale jobs recovery (every 15 mins)
    if not scheduler.get_job("job_stale_recovery"):
        scheduler.add_job(
            run_stale_jobs_recovery_job,
            trigger=IntervalTrigger(minutes=recovery_interval_minutes),
            id="job_stale_recovery",
            name="Recover stale discovering/auditing jobs",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

    # 3. Un-snooze expired tasks (every 30 mins)
    if not scheduler.get_job("job_unsnooze_tasks"):
        scheduler.add_job(
            run_unsnooze_tasks_job,
            trigger=IntervalTrigger(minutes=unsnooze_interval_minutes),
            id="job_unsnooze_tasks",
            name="Un-snooze expired tasks",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

    # Check for active running event loop before starting scheduler
    try:
        import asyncio
        asyncio.get_running_loop()
        has_loop = True
    except RuntimeError:
        has_loop = False

    if has_loop and not scheduler.running:
        scheduler.start()
        logger.info("SignalForge AI APScheduler started with 3 background jobs")
    elif not has_loop:
        logger.info("APScheduler initialized; start deferred until active event loop is available")

    return scheduler


def stop_scheduler() -> None:
    """Gracefully stop the APScheduler background worker."""
    global _scheduler
    if _scheduler is not None:
        try:
            if _scheduler.running:
                _scheduler.shutdown(wait=False)
                logger.info("SignalForge AI APScheduler stopped")
        except Exception as exc:
            logger.warning(f"Notice during scheduler shutdown: {exc}")
        finally:
            _scheduler = None
