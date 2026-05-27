"""Run blocking work off the asyncio event loop (production stability)."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, TypeVar

T = TypeVar("T")


async def run_blocking(func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Execute sync CPU/IO-heavy callables in a worker thread — keeps /healthz responsive."""
    return await asyncio.to_thread(func, *args, **kwargs)
