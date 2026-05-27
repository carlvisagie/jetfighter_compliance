"""
Acquisition intelligence package.

Import submodules directly (e.g. services.acquisition.orchestration).
This __init__ must not import orchestration, connectors, schedulers, or dashboards
to avoid import cycles and heavy startup side effects.
"""

__all__: list[str] = []
