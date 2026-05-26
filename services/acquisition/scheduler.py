"""Scheduler hooks for autonomous acquisition cycles."""
from __future__ import annotations

import logging

from . import telemetry

logger = logging.getLogger(__name__)


def daily_acquisition_cycle() -> None:
    try:
        from .connectors.usaspending_live import run_usaspending_live_connector

        run_usaspending_live_connector(campaign_id="upload-first-daily", message_variant="A")
    except Exception as e:
        logger.warning("Daily acquisition cycle failed: %s", e)
        telemetry.emit("acquisition_failure", success=False, message=str(e)[:120], severity="warning")


def daily_acquisition_learning() -> None:
    try:
        from .learning import run_learning_cycle

        run_learning_cycle()
    except Exception as e:
        logger.warning("Acquisition learning cycle failed: %s", e)


def register_scheduler_jobs(scheduler) -> None:
    try:
        scheduler.add_job(
            daily_acquisition_cycle,
            "cron",
            hour=7,
            minute=0,
            id="acquisition_organism_daily",
            replace_existing=True,
        )
    except Exception:
        pass
    try:
        scheduler.add_job(
            daily_acquisition_learning,
            "cron",
            hour=7,
            minute=30,
            id="acquisition_organism_learning",
            replace_existing=True,
        )
    except Exception:
        pass
    try:
        from .connectors.reddit.scheduler import register_scheduler_jobs as register_reddit_jobs

        register_reddit_jobs(scheduler)
    except Exception:
        pass
