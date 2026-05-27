"""Scheduler hooks — conservative Reddit discovery frequency."""
from __future__ import annotations

import logging

from . import telemetry

logger = logging.getLogger(__name__)


def reddit_discovery_job() -> None:
    from services.runtime_boot import is_safe_mode

    if is_safe_mode():
        return
    try:
        from . import run_reddit_acquisition_cycle

        run_reddit_acquisition_cycle(max_posts=25, min_fit_score=55)
    except Exception as e:
        logger.warning("Reddit discovery job failed: %s", e)
        telemetry.emit("reddit_discovery_failed", metadata={"error": str(e)[:120]})


def reddit_daily_learning_job() -> None:
    from services.runtime_boot import is_safe_mode

    if is_safe_mode():
        return
    try:
        from .learning import run_daily_reddit_learning

        run_daily_reddit_learning()
    except Exception as e:
        logger.warning("Reddit daily learning failed: %s", e)


def register_scheduler_jobs(scheduler) -> None:
    try:
        scheduler.add_job(
            reddit_discovery_job,
            "cron",
            hour="*/6",
            minute=15,
            id="reddit_acquisition_discovery",
            replace_existing=True,
        )
    except Exception:
        pass
    try:
        scheduler.add_job(
            reddit_daily_learning_job,
            "cron",
            hour=6,
            minute=30,
            id="reddit_organism_daily_learning",
            replace_existing=True,
        )
    except Exception:
        pass
