"""Scheduled digest jobs for operational alerts."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def daily_digest_job() -> None:
    try:
        from .digest import generate_daily_digest

        generate_daily_digest()
    except Exception as e:
        logger.warning("Daily alert digest failed: %s", e)
        try:
            from .engine import alert_organism_failure

            alert_organism_failure("scheduler_failure", message=f"daily_digest: {e}")
        except Exception:
            pass


def weekly_digest_job() -> None:
    try:
        from .digest import generate_weekly_digest

        generate_weekly_digest()
    except Exception as e:
        logger.warning("Weekly alert digest failed: %s", e)


def register_scheduler_jobs(scheduler) -> None:
    from .paths import load_config

    cfg = load_config()
    try:
        scheduler.add_job(
            daily_digest_job,
            "cron",
            hour=int(cfg.get("digest_daily_hour_utc", 8)),
            minute=5,
            id="operational_alerts_daily_digest",
            replace_existing=True,
        )
    except Exception:
        pass
    try:
        scheduler.add_job(
            weekly_digest_job,
            "cron",
            day_of_week=int(cfg.get("digest_weekly_dow", 0)),
            hour=int(cfg.get("digest_weekly_hour_utc", 9)),
            minute=10,
            id="operational_alerts_weekly_digest",
            replace_existing=True,
        )
    except Exception:
        pass
