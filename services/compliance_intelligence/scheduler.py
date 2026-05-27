"""Scheduler hooks — extend existing APScheduler in services.engine."""
from __future__ import annotations

from . import telemetry


def daily_compliance_check() -> None:
    """Cron job: check daily-frequency sources."""
    from services.runtime_boot import is_safe_mode

    if is_safe_mode():
        return
    try:
        from . import run_compliance_cycle

        run_compliance_cycle(polling_filter="daily")
    except Exception as e:
        telemetry.emit("fetch_failed", success=False, severity="warning", message=str(e)[:120])


def weekly_compliance_check() -> None:
    """Cron job: check weekly sources + build digest."""
    from services.runtime_boot import is_safe_mode

    if is_safe_mode():
        return
    try:
        from . import run_compliance_cycle, generate_weekly_digest

        run_compliance_cycle(polling_filter="weekly")
        generate_weekly_digest()
    except Exception as e:
        telemetry.emit("fetch_failed", success=False, severity="warning", message=str(e)[:120])


def register_scheduler_jobs(scheduler) -> None:
    """Register on existing BackgroundScheduler — no separate scheduler island."""
    try:
        scheduler.add_job(
            daily_compliance_check,
            "cron",
            hour=6,
            minute=15,
            id="compliance_intel_daily",
            replace_existing=True,
        )
    except Exception:
        pass
    try:
        scheduler.add_job(
            weekly_compliance_check,
            "cron",
            day_of_week="mon",
            hour=8,
            minute=0,
            id="compliance_intel_weekly",
            replace_existing=True,
        )
    except Exception:
        pass
