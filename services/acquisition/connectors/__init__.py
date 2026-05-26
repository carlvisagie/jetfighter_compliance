"""Live acquisition source connectors — lawful public data only."""

from .reddit import run_reddit_acquisition_cycle
from .usaspending_live import (
    CONNECTOR_ID,
    DEFAULT_QUERIES,
    run_usaspending_live_connector,
)

__all__ = [
    "CONNECTOR_ID",
    "DEFAULT_QUERIES",
    "run_usaspending_live_connector",
    "run_reddit_acquisition_cycle",
]
