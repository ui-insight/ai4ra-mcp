"""lakehouse: the University of Idaho data lakehouse through Marina, its query and file API.

Upstream: http://nlayman.nkn.uidaho.edu:7010 (AI4RA_MCP_LAKEHOUSE_URL), reachable on campus, so this process
reads it and a browser client never does. Marina authorizes a *client* (an id and a shared secret) for a set
of streams, so each client is its own server here, with its own fold and its own secret in a pane:
AI4RA_MCP_LAKEHOUSE_CLIENTS lists the client ids to mount, comma separated (default mr-365); the first is
mounted as `lakehouse`, the others as `lakehouse-<id>`. Every call needs an OAuth 2.0 bearer from /auth/token,
minted with HTTP Basic (client id, secret): the secret the person's client sends as its bearer token, else
AI4RA_MCP_LAKEHOUSE_SECRET (for the first client) or AI4RA_MCP_LAKEHOUSE_SECRET_<ID> (id upper-cased,
non-alphanumerics as underscores). A token is kept until it expires and never logged. Read only: the querying
streams' tables and files. The submitting streams are listed but not written to here, because a remote write
runs behind no confirmation card.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import httpx
from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common import fetch as _fetch
from ai4ra_mcp.common.http import HEADERS, TIMEOUT_S, api_key, missing_key
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
BASE = os.environ.get("AI4RA_MCP_LAKEHOUSE_URL", "http://nlayman.nkn.uidaho.edu:7010").rstrip("/")
CLIENTS = [c.strip() for c in os.environ.get("AI4RA_MCP_LAKEHOUSE_CLIENTS", "mr-365").split(",") if c.strip()] or ["mr-365"]
MAX_ROWS = 500
MAX_CHARS = 30_000

# Tokens by client id and a hash of the secret they were minted with: (token, expires_at). Never the secret itself.
_tokens: dict[str, tuple[str, float]] = {}


def mount_name(index: int, client_id: str) -> str:
    """The path a client's server is mounted at: the first client is `lakehouse`, the rest `lakehouse-<id>`."""
    return "lakehouse" if index == 0 else "lakehouse-" + re.sub(r"[^a-z0-9]+", "-", client_id.lower()).strip("-")


def key_env(index: int, client_id: str) -> str:
    return "AI4RA_MCP_LAKEHOUSE_SECRET" if index == 0 else "AI4RA_MCP_LAKEHOUSE_SECRET_" + re.sub(r"[^A-Z0-9]+", "_", client_id.upper()).strip("_")


def key_how(client_id: str) -> str:
    return f"The key is the shared secret issued with the lakehouse client id {client_id} by Research Computing and Data Services; it is not a personal key, so ask them for it."


def _hash(client_id: str, secret: str) -> str:
    return hashlib.sha256(f"{client_id}\n{secret}".encode("utf-8")).hexdigest()


async def _token(client_id: str, secret: str) -> str:
    """A bearer for this client and secret, minted at /auth/token with HTTP Basic and kept until it expires."""
    h = _hash(client_id, secret)
    held = _tokens.get(h)
    if held and held[1] > time.time() + 30:
        return held[0]
    async with httpx.AsyncClient(timeout=TIMEOUT_S, headers=HEADERS) as client:
        resp = await client.post(f"{BASE}/auth/token", auth=(client_id, secret), data={"grant_type": "client_credentials"})
    if resp.status_code in (401, 403):
        raise ValueError(f"the lakehouse refused the shared secret for client {client_id}")
    if resp.status_code >= 400:
        raise ValueError(f"{resp.status_code} from the lakehouse token endpoint")
    body = resp.json() if resp.content else {}
    token = body.get("access_token") if isinstance(body, dict) else None
    if not token:
        raise ValueError("the lakehouse token endpoint returned no access_token")
    try:
        expires = float(body.get("expires_in") or 3600)
    except (TypeError, ValueError):
        expires = 3600.0
    _tokens[h] = (token, time.time() + expires)
    return token


async def _call(client: dict, method: str, path: str, params: dict | None = None, payload: dict | None = None, raw: bool = False):
    """One authenticated request for a client. LookupError when no secret is on the request; ValueError for an upstream refusal."""
    secret = api_key(client["key_env"])
    if not secret:
        raise LookupError(client["key_env"])
    for attempt in (1, 2):
        token = await _token(client["id"], secret)
        async with httpx.AsyncClient(timeout=TIMEOUT_S, headers={**HEADERS, "Authorization": f"Bearer {token}"}) as client_http:
            resp = await client_http.request(method, f"{BASE}{path}", params=params, json=payload)
        if resp.status_code == 401 and attempt == 1:
            _tokens.pop(_hash(client["id"], secret), None)   # the token died early: mint another once
            continue
        break
    if resp.status_code in (401, 403):
        raise ValueError(f"{resp.status_code} from the lakehouse: this client is not authorized for that stream, table or file")
    if resp.status_code == 404:
        raise ValueError("404 from the lakehouse: no such stream, table or file")
    if resp.status_code >= 400:
        raise ValueError(f"{resp.status_code} from the lakehouse: {resp.text[:300]}")
    return resp if raw else (resp.json() if resp.content else {})


def _report(client: dict, e: Exception) -> dict:
    if isinstance(e, LookupError):
        return missing_key(client["key_env"], key_how(client["id"]))
    if isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout, OSError)) and not isinstance(e, ValueError):
        return {"error": f"the lakehouse at {BASE} is not reachable from this server ({e}); it answers on campus only"}
    return {"error": str(e)}



def slim_rows(table: str, result: dict, limit: int) -> dict:
    """The rows of one table from a /query response, capped by count and by size."""
    columns = result.get("columns") or []
    rows = result.get("rows") or []
    out, chars = [], 0
    for r in rows[:min(limit, MAX_ROWS)]:
        s = json.dumps(r, default=str)
        if out and chars + len(s) > MAX_CHARS:
            break
        out.append(r)
        chars += len(s)
    return {"table": table, "columns": columns, "rows": out, "returned": len(out),
            "row_count": result.get("rowCount", len(rows)), "truncated": len(out) < len(rows)}


_OPERATORS = ("eq", "neq", "gt", "gte", "lt", "lte", "in", "like", "ilike", "is_null")
_AGG_FUNCS = ("COUNT", "SUM", "AVG", "MIN", "MAX")


def _check_filters(filters) -> str | None:
    if filters is None:
        return None
    if not isinstance(filters, dict):
        return "filters must be an object of column: value or column: {operator: value}"
    for col, v in filters.items():
        if isinstance(v, dict):
            bad = [k for k in v if k not in _OPERATORS]
            if bad:
                return f"unknown filter operator {bad[0]!r} on {col}; use one of {', '.join(_OPERATORS)}"
            if "in" in v and not isinstance(v["in"], list):
                return f"the in operator on {col} takes a list"
    return None


def _check_aggregate(aggregate) -> str | None:
    if aggregate is None:
        return None
    if not isinstance(aggregate, list):
        return "aggregate must be a list of {fn, column, alias}"
    for a in aggregate:
        if not isinstance(a, dict) or str(a.get("fn", "")).upper() not in _AGG_FUNCS or not a.get("column"):
            return f"each aggregate is {{fn: one of {', '.join(_AGG_FUNCS)}, column: a column or *, alias: a name}}"
    return None




def make_server(name: str, client_id: str, key_env_name: str) -> tuple[MCPServer, dict]:
    """One MCP server for one lakehouse client: the same tools, closed over the client id and the name of its
    fallback secret variable. Mounted under `name`."""
    client = {"id": client_id, "key_env": key_env_name}
    mcp = MCPServer(
        name,
        instructions=f"The University of Idaho data lakehouse (Marina) as client {client_id}: the streams it may query, each stream's tables and columns, rows from a table, and the files a stream may read. Needs this client's shared secret. Read lakehouse_index first, then lakehouse_streams.",
    )

    @mcp.tool(name="lakehouse_index", annotations=_READ_ONLY)
    async def lakehouse_index() -> dict:
        """What the lakehouse server offers and how to use it: the client, the streams model, the tools in order, the rules. Read this first."""
        return {
            "upstream": f"{BASE} (Marina, the University of Idaho lakehouse API; campus only, reached by this server)",
            "client": client["id"],
            "key": {"on_this_request": bool(api_key(client["key_env"])), "per_user": "send this client's shared secret as a bearer token; the server holds none unless the deployment set " + client["key_env"],
                        "how": key_how(client["id"])},
            "model": "A client is authorized for streams. A querying stream reads a set of tables through a wrapper view (columns masked and rows filtered as the stream allows) and a set of files by tag. A submitting stream accepts records and files; those are listed here but not written to.",
            "workflow": ["lakehouse_streams: the querying and submitting streams this client may use",
                         "lakehouse_schema(stream): the tables and columns a querying stream can read",
                         "lakehouse_query(stream, table, limit, filters, offset, group_by, aggregate): rows from one table, filtered and paged, or grouped and aggregated (COUNT, SUM, AVG, MIN, MAX)",
                         "lakehouse_files(stream): the files a stream may read, with their hashes",
                         "lakehouse_file(stream, hash): one file as text, in pages"],
            "notes": [f"Rows are capped at {MAX_ROWS} a call and {MAX_CHARS:,} characters: filter, page with offset, or aggregate rather than scanning.",
                      "A stream may require certain filters; a 400 names them. A column not in the stream's row_params is filtered as text.",
                      "Rate limits: 100 requests a minute and 1,000 an hour for this client, shared by everyone using it.",
                      "Every result names the stream and table it came from; cite them with the date of the call.",
                      "Nothing is written to the lakehouse from here."],
        }


    @mcp.tool(name="lakehouse_streams", annotations=_READ_ONLY)
    async def lakehouse_streams() -> dict:
        """The streams this client is authorized to use: querying (readable here) and submitting (listed, not written to).

        Returns: client_id, querying (stream names), submitting (stream names).
        """
        try:
            body = await _call(client, "GET", "/streams")
        except Exception as e:
            return _report(client, e)
        return {"client_id": body.get("client_id"), "querying": body.get("querying") or [], "submitting": body.get("submitting") or [],
                "note": "Call lakehouse_schema with a querying stream to see its tables; submitting streams are not written to from here."}


    @mcp.tool(name="lakehouse_schema", annotations=_READ_ONLY)
    async def lakehouse_schema(stream: str) -> dict:
        """The tables a querying stream can read, with their columns and types, as the stream's wrapper view exposes them.

        Args:
            stream: A querying stream name from lakehouse_streams.
        """
        stream = (stream or "").strip()
        if not stream:
            return {"error": "stream is required: a querying stream name from lakehouse_streams"}
        try:
            body = await _call(client, "GET", "/query/schema", params={"stream": stream})
        except Exception as e:
            return _report(client, e)
        return {"stream": stream, "schema": body}


    @mcp.tool(name="lakehouse_query", annotations=_READ_ONLY)
    async def lakehouse_query(stream: str, table: str, limit: int = 100, filters: dict | None = None, offset: int | None = None,
                              group_by: list[str] | None = None, aggregate: list[dict] | None = None) -> dict:
        """Rows from one table of a querying stream, as the stream's view exposes them: filtered, paged, or grouped and aggregated.

        Filter before you page and aggregate before you scan: a wide table is best asked for its distinct values
        (group_by alone) or its counts and sums (group_by with aggregate) rather than its rows. The stream may require
        certain filters (a 400 names them) and caps the rows.

        Args:
            stream: A querying stream name from lakehouse_streams.
            table: A table name from lakehouse_schema.
            limit: Rows to return, 1-500. Default 100.
            filters: Column filters combined with AND. A bare value is equality: {"fiscal_year": 2024, "status": "Active"}. An object is operators: {"amount": {"gte": 50000, "lte": 200000}, "status": {"in": ["Active", "Pending"]}, "title": {"ilike": "%climate%"}, "ended": {"is_null": true}}; operators eq, neq, gt, gte, lt, lte, in (a list, at most 1000), like, ilike, is_null.
            offset: Row offset for paging, 0-based; when given, the result carries total_count, the matching rows before paging.
            group_by: Column names to group by. Alone, it returns the distinct combinations; with aggregate, the computed values, ordered by the first aggregate descending.
            aggregate: With group_by: [{"fn": "COUNT", "column": "*", "alias": "cnt"}, {"fn": "SUM", "column": "amount", "alias": "total"}]; fn is COUNT, SUM, AVG, MIN or MAX.
        Returns: stream, table, columns, rows, returned, row_count, total_count (when offset was given), truncated.
        """
        stream, table = (stream or "").strip(), (table or "").strip()
        if not stream or not table:
            return {"error": "stream and table are required: see lakehouse_streams and lakehouse_schema"}
        limit = max(1, min(int(limit or 100), MAX_ROWS))
        problem = _check_filters(filters) or _check_aggregate(aggregate)
        if problem:
            return {"error": problem}
        if aggregate and not group_by:
            return {"error": "aggregate needs group_by (group by a column to aggregate over it)"}
        req: dict = {"table": table, "limit": limit}
        if filters:
            req["filters"] = filters
        if offset is not None:
            req["offset"] = max(0, int(offset))
        if group_by:
            req["group_by"] = [str(c) for c in group_by]
        if aggregate:
            req["aggregate"] = [{"fn": str(a["fn"]).upper(), "column": str(a["column"]), **({"alias": str(a["alias"])} if a.get("alias") else {})} for a in aggregate]
        try:
            body = await _call(client, "POST", "/query", payload={"stream": stream, "tables": [req]})
        except Exception as e:
            return _report(client, e)
        result = body.get(table) if isinstance(body, dict) else None
        if not isinstance(result, dict):
            return {"error": f"the lakehouse answered without a '{table}' entry", "keys": list(body.keys()) if isinstance(body, dict) else None}
        out = {"stream": stream, **slim_rows(table, result, limit)}
        if "totalCount" in result:
            out["total_count"] = result["totalCount"]
        return out


    @mcp.tool(name="lakehouse_files", annotations=_READ_ONLY)
    async def lakehouse_files(stream: str) -> dict:
        """The files a querying stream may read: the catalog of files whose tags the stream is allowed, with each file's hash for lakehouse_file.

        Args:
            stream: A querying stream name from lakehouse_streams.
        """
        stream = (stream or "").strip()
        if not stream:
            return {"error": "stream is required: a querying stream name from lakehouse_streams"}
        try:
            body = await _call(client, "GET", "/files/catalog", params={"stream": stream})
        except Exception as e:
            return _report(client, e)
        return {"stream": stream, "catalog": body, "note": "Pass a file's hash to lakehouse_file to read it as text."}


    @mcp.tool(name="lakehouse_file", annotations=_READ_ONLY)
    async def lakehouse_file(stream: str, hash: str, offset: int = 0, max_chars: int = 12000) -> dict:
        """One file a stream may read, as text: a PDF or HTML file is converted, a text file decoded, anything else described. In pages.

        Args:
            stream: A querying stream name from lakehouse_streams.
            hash: The file's hash from lakehouse_files.
            offset: Character position to start from. Default 0.
            max_chars: Characters to return, 1000-40000. Default 12000.
        """
        stream, hash = (stream or "").strip(), (hash or "").strip()
        if not stream or not hash:
            return {"error": "stream and hash are required: see lakehouse_files"}
        try:
            resp = await _call(client, "GET", "/files", params={"stream": stream, "hash": hash}, raw=True)
        except Exception as e:
            return _report(client, e)
        ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
        data = resp.content
        title = ""
        if ctype == "application/pdf" or data[:5] == b"%PDF-":
            kind, text = "pdf", _fetch.pdf_to_text(data)
        elif ctype in ("text/html", "application/xhtml+xml"):
            kind = "html"
            title, text = _fetch.html_to_text(data.decode("utf-8", "replace"))
        elif ctype.startswith("text/") or ctype in ("application/json", "application/csv"):
            kind, text = "text", data.decode("utf-8", "replace")
        else:
            return {"stream": stream, "hash": hash, "kind": ctype or "unknown", "bytes": len(data),
                    "error": "this file is not text, HTML or PDF, so it cannot be read here"}
        max_chars = max(1000, min(int(max_chars or 12000), 40000))
        page = _fetch._page(f"{BASE}/files?stream={stream}&hash={hash}", kind, title, text, max(0, int(offset or 0)), max_chars)
        return {"stream": stream, "hash": hash, "content_type": ctype, **page}


    register_prompts(mcp, Path(__file__).parent / "skills")
    return mcp, {"lakehouse_index": lakehouse_index, "lakehouse_streams": lakehouse_streams, "lakehouse_schema": lakehouse_schema,
                 "lakehouse_query": lakehouse_query, "lakehouse_files": lakehouse_files, "lakehouse_file": lakehouse_file}


# The configured clients, the first one at `lakehouse`; each is its own server, fold and secret.
_built = {mount_name(i, c): make_server(mount_name(i, c), c, key_env(i, c)) for i, c in enumerate(CLIENTS)}
SERVERS: dict[str, MCPServer] = {n: m for n, (m, _t) in _built.items()}
CLIENT_OF: dict[str, str] = {mount_name(i, c): c for i, c in enumerate(CLIENTS)}
KEY_ENV_OF: dict[str, str] = {mount_name(i, c): key_env(i, c) for i, c in enumerate(CLIENTS)}
# The first client's server and tools by plain names, for a stdio run and the tests.
mcp = SERVERS["lakehouse"]
CLIENT_ID = CLIENTS[0]
KEY_ENV = KEY_ENV_OF["lakehouse"]
_default_tools = _built["lakehouse"][1]
lakehouse_index, lakehouse_streams, lakehouse_schema = _default_tools["lakehouse_index"], _default_tools["lakehouse_streams"], _default_tools["lakehouse_schema"]
lakehouse_query, lakehouse_files, lakehouse_file = _default_tools["lakehouse_query"], _default_tools["lakehouse_files"], _default_tools["lakehouse_file"]
