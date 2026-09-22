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
from contextvars import ContextVar
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


# ---- upstream calls ----

import httpx  # noqa: E402

TIMEOUT_S = 30.0


# A bearer token the client sent with this request, set by the app's middleware for the request's
# scope. A keyed server uses it in place of its own environment key, so a person with their own
# SAM.gov or FAC key can spend their quota rather than the institution's. It is never logged.
request_key: ContextVar[str | None] = ContextVar("request_key", default=None)


def api_key(env_name: str) -> str | None:
    """The key for an upstream: the request's bearer token, which is the person's own key sent by
    their client; else the environment variable, for a deployment that chooses to hold one; else None."""
    sent = request_key.get()
    if sent:
        return sent
    v = os.environ.get(env_name, "").strip()
    return v or None


def missing_key(env_name: str, where: str) -> dict:
    return {"error": f"no API key on this request: send your own key as a bearer token (in the Office pane, paste it into this server's i dialog). {where}"}


async def get_json(url: str, params: dict | None = None, headers: dict | None = None) -> dict | list:
    """GET JSON with the shared User-Agent. A 429 or 5xx becomes a ValueError the tool reports."""
    async with httpx.AsyncClient(timeout=TIMEOUT_S, headers={**HEADERS, **(headers or {})}, follow_redirects=True) as client:
        resp = await client.get(url, params=params)
    return _body(resp, url)


async def post_json(url: str, payload: dict, headers: dict | None = None) -> dict | list:
    async with httpx.AsyncClient(timeout=TIMEOUT_S, headers={**HEADERS, **(headers or {})}, follow_redirects=True) as client:
        resp = await client.post(url, json=payload)
    return _body(resp, url)


def _body(resp: httpx.Response, url: str) -> dict | list:
    if resp.status_code == 429:
        raise ValueError(f"rate limit exceeded at {resp.request.url.host}; wait before retrying")
    if resp.status_code in (401, 403):
        raise ValueError(f"{resp.status_code} from {resp.request.url.host}: the API key was refused or lacks permission")
    if resp.status_code == 404:
        raise ValueError(f"404 from {url}: nothing at that address")
    if resp.status_code >= 400:
        raise ValueError(f"{resp.status_code} from {resp.request.url.host}: {resp.text[:200]}")
    try:
        return resp.json()
    except ValueError:
        raise ValueError(f"{resp.request.url.host} did not return JSON") from None
