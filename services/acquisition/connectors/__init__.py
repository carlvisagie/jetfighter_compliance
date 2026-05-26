"""Live acquisition source connectors — lawful public data only."""

from .usaspending_live import (
    CONNECTOR_ID,
    DEFAULT_QUERIES,
    run_usaspending_live_connector,
)

__all__ = [
    "CONNECTOR_ID",
    "DEFAULT_QUERIES",
    "run_usaspending_live_connector",
]
