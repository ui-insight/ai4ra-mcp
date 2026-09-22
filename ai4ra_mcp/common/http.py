"""What every upstream call shares: one User-Agent that names this project and a
contact, and a small in-memory cache with a lifetime per entry.

The User-Agent is how an upstream (ecfr.gov, grants.gov, uidaho.edu) knows who
is calling and how to reach us if the volume becomes a problem. The cache is
how we keep that volume down: regulation text for a citation on a date never
changes, and a policy page changes a few times a year.
"""

from __future__ import annotations

import os
import time
from typing import Any, Awaitable, Callable

CONTACT = os.environ.get("AI4RA_MCP_CONTACT", "https://github.com/ui-insight/ai4ra-mcp")
USER_AGENT = f"ai4ra-mcp/0.1 (+{CONTACT})"
HEADERS = {"User-Agent": USER_AGENT}

HOUR = 3600
DAY = 24 * HOUR


class TTLCache:
    """A dict whose entries expire. One per server module; not shared across processes."""

    def __init__(self, max_entries: int = 2000):
        self._d: dict[str, tuple[float, Any]] = {}
        self._max = max_entries

    def get(self, key: str) -> Any | None:
        hit = self._d.get(key)
        if hit is None:
            return None
        expires, value = hit
        if expires < time.monotonic():
            self._d.pop(key, None)
            return None
        return value

    def put(self, key: str, value: Any, ttl: float) -> Any:
        if len(self._d) >= self._max:
            oldest = min(self._d, key=lambda k: self._d[k][0])
            self._d.pop(oldest, None)
        self._d[key] = (time.monotonic() + ttl, value)
        return value

    async def remember(self, key: str, ttl: float, make: Callable[[], Awaitable[Any]]) -> Any:
        value = self.get(key)
        if value is None:
            value = self.put(key, await make(), ttl)
        return value
