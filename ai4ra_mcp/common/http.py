"""What every upstream call shares: one User-Agent that names this project and a
contact, and a small in-memory cache with a lifetime per entry.

The User-Agent is how an upstream (ecfr.gov, grants.gov, uidaho.edu) knows who
is calling and how to reach us if the volume becomes a problem. The cache is
how we keep that volume down: regulation text for a citation on a date never
changes, and a policy page changes a few times a year.
"""

from __future__ import annotations

import logging
import os
import re
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


# ---- log no keys ----

# A key an upstream wants in the URL (SAM.gov, GSA per diem and PubMed take api_key as a query parameter) would
# land in the process log, because httpx logs every request's full URL at INFO. Nothing a person sent as their
# credential appears in any log line: the httpx and httpcore loggers are held at WARNING, and a filter blanks
# key-like parameters from whatever those loggers, or the root handlers, still emit.
_KEY_PARAMS = re.compile(r"((?:api[_-]?key|key|token|secret|subscription-key|registrationkey|access_token|password)=)[^&\s\"']+", re.I)


class RedactKeys(logging.Filter):
    """Replaces the value of any key-like query parameter in a log record with [redacted]."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        cleaned = _KEY_PARAMS.sub(r"\1[redacted]", msg)
        if cleaned != msg:
            record.msg, record.args = cleaned, ()
        return True


def log_no_keys() -> None:
    """Hold the HTTP client loggers at WARNING and put the redacting filter on them and on the root handlers.
    Called at import and again at startup, since a logging configuration applied later may add handlers."""
    for name in ("httpx", "httpcore"):
        logger = logging.getLogger(name)
        if logger.level < logging.WARNING:
            logger.setLevel(logging.WARNING)
        if not any(isinstance(f, RedactKeys) for f in logger.filters):
            logger.addFilter(RedactKeys())
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, RedactKeys) for f in handler.filters):
            handler.addFilter(RedactKeys())


log_no_keys()


# ---- upstream calls ----

import httpx  # noqa: E402

TIMEOUT_S = 30.0


# A bearer token the client sent with this request, set by the app's middleware for the request's
# scope. A keyed server uses it in place of its own environment key, so a person with their own
# SAM.gov or FAC key can spend their quota rather than the institution's. It is never logged.
request_key: ContextVar[str | None] = ContextVar("request_key", default=None)
# The shape of an Authorization header that arrived but was not accepted (auth_shape below), None when none arrived.
request_auth_shape: ContextVar[str | None] = ContextVar("request_auth_shape", default=None)
_SCHEMES = {"bearer", "basic", "token", "apikey", "api-key"}
_log = logging.getLogger("ai4ra_mcp.keys")
LOG_REFUSALS_ENV = "AI4RA_MCP_LOG_REFUSALS"


def log_refusals() -> bool:
    """Whether a keyed tool's refusal writes its one log line: on when AI4RA_MCP_LOG_REFUSALS is `1`, off otherwise.
    Read at each refusal, so a deployment turns it on to troubleshoot a client and off again after."""
    return os.environ.get(LOG_REFUSALS_ENV, "").strip() == "1"


def auth_shape(value: str) -> str:
    """The shape of an Authorization header the middleware did not accept, carrying none of its characters beyond
    a scheme word: the first word if it is a known scheme (else only its length), how many space-separated parts
    there are, and the length of the last. `scheme=Bearer: parts=2 last_len=40` says a colon crept in,
    `scheme=<40 chars> parts=1` that the key came bare, `parts=3` that a prefix was doubled. A first word that is
    not a known scheme may be the key itself, which is why only its length is kept."""
    parts = value.split()
    first = parts[0] if parts else ""
    scheme = first if first.lower().rstrip(":") in _SCHEMES else f"<{len(first)} chars>"
    return f"scheme={scheme} parts={len(parts)} last_len={len(parts[-1]) if parts else 0}"


def api_key(env_name: str) -> str | None:
    """The key for an upstream: the request's bearer token, which is the person's own key sent by
    their client; else the environment variable, for a deployment that chooses to hold one; else None."""
    sent = request_key.get()
    if sent:
        return sent
    v = os.environ.get(env_name, "").strip()
    return v or None


def missing_key(env_name: str, where: str) -> dict:
    """The answer every tool of a keyed server gives when no key came with the request. It tells the model to
    stop: a refused lookup is not a cue to answer from memory or a web search, which is how a per diem
    question once got invented figures with a made-up source line. It says what the server needs and where a
    key comes from, and nothing about where a client keeps one: that is the client's own help text (the index
    carries the hint a client shows beside its key field).

    With AI4RA_MCP_LOG_REFUSALS=1 (log_refusals), one WARNING line per refusal says whether an Authorization header
    arrived at all and, when one did, its shape (auth_shape), so a deployment can tell a client that sends nothing
    from one that sends the wrong form; it never carries the value. Added 2026-10-15, when Claude.ai dropped a
    `Bearer` header and nothing said so."""
    if log_refusals():
        shape = request_auth_shape.get()
        _log.warning("no API key on this request (%s): authorization header %s", env_name,
                     "absent" if shape is None else f"present but not accepted ({shape})")
    return {"error": f"no API key on this request: send your own key as a bearer token. {where}",
            "do_not": "Do not answer this from memory or from a web search. Tell the person this server needs their key and how to get one, and stop there."}


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
