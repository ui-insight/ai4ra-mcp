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

SQL: Marina also speaks v1 of the Trino HTTP statement protocol at /sql/v1/statement, one schema per querying
stream (`client_<client_id>__<stream>`), one view per allowed table, rows filtered and masked inside the views.
lakehouse_sql_catalog surveys the visible schema with Marina's own statistics (GET /query/schema per stream), in
layers small enough to live in a conversation; lakehouse_sql runs one guarded SELECT. Nothing is cached here: the
conversation is the cache. A client is an application identity (everyone using it sees the same views).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
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
SQL_TIMEOUT_S = float(os.environ.get("AI4RA_MCP_LAKEHOUSE_SQL_TIMEOUT_S", "60") or 60)
COUNT_CHUNK = 50          # count(*) branches per UNION ALL statement; Trino fails past 100 stages
LARGEST_TABLES = 25       # ranked across streams in the catalog overview
COLUMNS_INLINE_MAX = 40   # a stream with more tables than this lists them without columns

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
        if not isinstance(a, dict) or not a.get("column"):
            return f"each aggregate is {{fn: one of {', '.join(_AGG_FUNCS)}, column: a column or *, alias: a name}}"
        fn = str(a.get("fn", "")).upper()
        if fn not in _AGG_FUNCS:
            return (f"fn {a.get('fn')!r} is not an aggregate here: the only ones are {', '.join(_AGG_FUNCS)}. "
                    "COUNT on a column counts its non-null rows and COUNT on * counts every row, so a count of "
                    "filled values is COUNT on that column; a count with a condition, or any other function, is one "
                    "lakehouse_sql SELECT.")
    return None




# ---- SQL: the Trino statement protocol through Marina ----

_REFUSED_FIRST_WORDS = ("INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "DROP", "ALTER", "TRUNCATE", "GRANT", "REVOKE", "DENY",
                        "EXPLAIN", "PREPARE", "EXECUTE", "DEALLOCATE", "SET", "RESET", "START", "COMMIT", "ROLLBACK", "USE", "CALL",
                        "ANALYZE", "COMMENT", "REFRESH")
_META_TABLE = re.compile(r'\."_[A-Za-z0-9_]*"|\._[A-Za-z0-9_]+\b')   # a "_stats"-style table: evaluated by the gateway, never wrapped
_TRAILING_LIMIT = re.compile(r"\bLIMIT\s+(?:\d+|ALL)(?:\s+OFFSET\s+\d+)?\s*$", re.IGNORECASE)


def schema_name(client_id: str, stream: str) -> str:
    return f"client_{client_id}__{stream}"


def qualified(client_id: str, stream: str, view: str) -> str:
    return f'lakehouse."{schema_name(client_id, stream)}"."{view}"'


def is_meta_table(name: str) -> bool:
    return str(name or "").startswith("_")


def prepare_sql(sql: str, limit: int) -> str:
    """The statement as it will be sent: one statement, a read, with a LIMIT added when a SELECT has none.
    Raises ValueError with a one-line reason for what is refused here; everything else is Marina's to judge."""
    text = str(sql or "").strip()
    if text.endswith(";"):
        text = text[:-1].rstrip()
    if not text:
        raise ValueError("sql is empty")
    if ";" in text:
        raise ValueError("one statement per call: Marina refuses multi-statement requests, and this one holds a ';'")
    first = re.match(r"[A-Za-z]+", text)
    word = first.group(0).upper() if first else ""
    if word in _REFUSED_FIRST_WORDS:
        raise ValueError(f"{word} is not run from here: the lakehouse is read only (SELECT, WITH, SHOW, DESCRIBE); Marina would refuse it too")
    if word in ("SELECT", "WITH") and not _TRAILING_LIMIT.search(text) and not _META_TABLE.search(text):
        n = max(1, min(int(limit or MAX_ROWS), MAX_ROWS))
        return f"SELECT * FROM ({text}) AS q LIMIT {n}"
    return text


async def _sql(client: dict, sql: str, budget_s: float | None = None) -> dict:
    """One statement through Marina's Trino endpoint: HTTP Basic (client id, bearer), text/plain body, nextUri followed
    until the state is terminal or the caps are hit (then the statement is cancelled). Marina's messages come back
    verbatim in the ValueError. LookupError when no secret is on the request."""
    secret = api_key(client["key_env"])
    if not secret:
        raise LookupError(client["key_env"])
    budget = budget_s or SQL_TIMEOUT_S
    for attempt in (1, 2):
        token = await _token(client["id"], secret)
        auth = (client["id"], token)
        started = time.monotonic()
        columns: list = []
        rows: list = []
        chars = 0
        truncated = False
        state = ""
        async with httpx.AsyncClient(timeout=TIMEOUT_S, headers=HEADERS) as http:
            resp = await http.post(f"{BASE}/sql/v1/statement", content=sql.encode("utf-8"), headers={"Content-Type": "text/plain"}, auth=auth)
            if resp.status_code == 401 and attempt == 1:
                _tokens.pop(_hash(client["id"], secret), None)   # the bearer died: mint another and send the statement again, once
                continue
            if resp.status_code >= 400:
                raise ValueError(_marina_message(resp))
            body = resp.json() if resp.content else {}
            while True:
                if body.get("columns") and not columns:
                    columns = [{"name": c.get("name"), "type": c.get("type")} for c in body["columns"] if isinstance(c, dict)]
                for r in body.get("data") or []:
                    if len(rows) >= MAX_ROWS or chars > MAX_CHARS:
                        truncated = True
                        break
                    rows.append(r)
                    chars += len(json.dumps(r, default=str))
                stats = body.get("stats") or {}
                state = str(stats.get("state") or "")
                next_uri = body.get("nextUri")
                if body.get("error"):
                    err = body["error"] if isinstance(body["error"], dict) else {"message": str(body["error"])}
                    raise ValueError(str(err.get("message") or err.get("errorName") or "the statement failed"))
                if not next_uri:
                    if state in ("FAILED", "CANCELED"):
                        raise ValueError(f"the statement ended {state.lower()} without a message from Marina")
                    break
                if truncated or time.monotonic() - started > budget:
                    try:
                        await http.delete(next_uri, auth=auth)
                    except Exception:
                        pass
                    if not truncated:
                        raise ValueError(f"the statement ran past {budget:.0f} seconds and was cancelled; narrow it with a WHERE or ask for less")
                    state = state or "CANCELED"
                    break
                resp = await http.get(next_uri, auth=auth)
                if resp.status_code == 401 and attempt == 1:
                    _tokens.pop(_hash(client["id"], secret), None)
                    body = None
                    break
                if resp.status_code >= 400:
                    raise ValueError(_marina_message(resp))
                body = resp.json() if resp.content else {}
            if body is None:
                continue   # the bearer expired mid-poll: the outer loop re-sends the statement with a fresh one
        return {"columns": [c["name"] for c in columns], "types": [c["type"] for c in columns], "rows": rows, "row_count": len(rows),
                "truncated": truncated, "state": state or "FINISHED", "elapsed_ms": int((time.monotonic() - started) * 1000)}
    raise ValueError("the lakehouse refused the bearer twice")   # unreachable in practice: attempt 2 returns or raises above


def _marina_message(resp) -> str:
    """Marina's own words for a refusal, unchanged: they are written for a model and name the discovery statements."""
    try:
        body = resp.json()
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])
            for k in ("message", "detail", "error"):
                if isinstance(body.get(k), str) and body[k]:
                    return body[k]
    except Exception:
        pass
    text = (resp.text or "").strip()
    return text[:1000] if text else f"{resp.status_code} from the lakehouse SQL endpoint"


def _stream_names(body) -> list[str]:
    """The querying stream names from /streams, whether Marina lists names or objects."""
    out = []
    for q in (body or {}).get("querying") or []:
        if isinstance(q, str):
            out.append(q)
        elif isinstance(q, dict) and (q.get("name") or q.get("stream")):
            out.append(str(q.get("name") or q.get("stream")))
    return out


def _schema_tables(body) -> list[dict]:
    """The tables of a /query/schema answer as [{name, description, row_count, columns: [{name, type, description, stats}]}],
    tolerant of a list or a dict of tables and of columns given either way."""
    raw = body.get("tables") if isinstance(body, dict) else None
    if raw is None and isinstance(body, dict):
        raw = {k: v for k, v in body.items() if isinstance(v, dict) and ("columns" in v or "row_count" in v)}
    items = []
    if isinstance(raw, dict):
        for name, t in raw.items():
            items.append({**(t if isinstance(t, dict) else {}), "name": (t or {}).get("name") or (t or {}).get("table") or name})
    elif isinstance(raw, list):
        for t in raw:
            if isinstance(t, dict):
                items.append({**t, "name": t.get("name") or t.get("table") or ""})
    out = []
    for t in items:
        cols_raw = t.get("columns")
        cols = []
        if isinstance(cols_raw, dict):
            for cname, c in cols_raw.items():
                c = c if isinstance(c, dict) else {"type": c}
                cols.append({"name": cname, **c})
        elif isinstance(cols_raw, list):
            for c in cols_raw:
                if isinstance(c, dict):
                    cols.append(dict(c))
                elif isinstance(c, str):
                    cols.append({"name": c})
        rc = t.get("row_count")
        out.append({"name": str(t["name"]), "description": t.get("description") or "", "row_count": rc if isinstance(rc, (int, float)) else None,
                    "columns": [{"name": c.get("name"), "type": c.get("type"), "description": c.get("description") or "", "stats": c.get("stats") if isinstance(c.get("stats"), dict) else None} for c in cols]})
    return out


def _fit(obj: dict, trim: list[tuple[str, int]]) -> dict:
    """The dict under MAX_CHARS: each (key, keep) in trim shortens that list to `keep` entries in turn until it fits, noting what was cut."""
    for key, keep in trim:
        if len(json.dumps(obj, default=str)) <= MAX_CHARS:
            break
        lst = obj.get(key)
        if isinstance(lst, list) and len(lst) > keep:
            obj[key] = lst[:keep]
            obj.setdefault("left_out", []).append(f"{len(lst) - keep} of {key}")
    return obj


def make_server(name: str, client_id: str, key_env_name: str) -> tuple[MCPServer, dict]:
    """One MCP server for one lakehouse client: the same tools, closed over the client id and the name of its
    fallback secret variable. Mounted under `name`."""
    client = {"id": client_id, "key_env": key_env_name}
    mcp = MCPServer(
        name,
        instructions=f"The University of Idaho data lakehouse (Marina) as client {client_id}: the streams it may query, each stream's tables and columns with Marina's statistics, rows from a table by filter or by one guarded SQL SELECT, and the files a stream may read. Needs this client's shared secret. Read lakehouse_index first, then lakehouse_sql_catalog.",
    )

    @mcp.tool(name="lakehouse_index", annotations=_READ_ONLY)
    async def lakehouse_index() -> dict:
        """What the lakehouse server offers and how to use it: the client, the streams model, the tools in order, the rules. Read this first."""
        return {
            "upstream": f"{BASE} (Marina, the University of Idaho lakehouse API; campus only, reached by this server)",
            "client": client["id"],
            "key": {"on_this_request": bool(api_key(client["key_env"])), "per_user": "send this client's shared secret as a bearer token; the server holds none unless the deployment set " + client["key_env"],
                        "how": key_how(client["id"])},
            "model": "A client is an application identity authorized for streams; everyone using it sees the same views. A querying stream reads a set of tables through a wrapper view (columns masked and rows filtered as the admin set on the stream) and a set of files by tag. A submitting stream accepts records and files; those are listed here but not written to. In SQL, a stream is the schema lakehouse.\"client_" + client["id"] + "__<stream>\" and each table a view in it.",
            "workflow": ["lakehouse_sql_catalog(): the streams this client sees with their sizes and the largest tables across them; (stream): that stream's tables by row count; (stream, table): every column with Marina's statistics (null_count, distinct_count, min, max, mean, true_count, rows_by_year and the rest, where measured). Read this before writing SQL; the conversation keeps it. counts=true scans only the tables Marina has not measured yet.",
                         "lakehouse_sql(sql, limit): one SELECT or WITH over one stream's views, fully qualified as lakehouse.\"client_" + client["id"] + "__<stream>\".\"<view>\"; any Trino function; SHOW PROFILE IN a schema and SELECT * FROM its _stats give statistics; a LIMIT is added when missing. Marina refuses DML, DDL, EXPLAIN and multi-statement requests, and its message says what to do.",
                         "lakehouse_query(stream, table, limit, filters, offset, group_by, aggregate): a simple filtered read of one table without SQL, or grouped aggregates (exactly COUNT, SUM, AVG, MIN, MAX; COUNT on a column is its non-null count). Anything else is lakehouse_sql.",
                         "lakehouse_streams and lakehouse_schema(stream): the plain lists behind the catalog",
                         "lakehouse_files(stream): the files a stream may read, with their hashes",
                         "lakehouse_file(stream, hash): one file as text, in pages"],
            "notes": [f"Rows are capped at {MAX_ROWS} a call and {MAX_CHARS:,} characters: filter, page with offset, or aggregate rather than scanning.",
                      "One stream per SQL statement. Tables whose names start with _ are metadata (_stats), read by the gateway, not data tables.",
                      "Nothing is cached on this server: a catalog result is fresh each call, so call it once and refer back to it.",
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
            aggregate: With group_by: [{"fn": "COUNT", "column": "*", "alias": "cnt"}, {"fn": "SUM", "column": "amount", "alias": "total"}]. fn is exactly one of COUNT, SUM, AVG, MIN, MAX; nothing else exists. COUNT on * counts every row of the group and COUNT on a column counts its non-null rows (SQL semantics), so "how many have a file" is COUNT on the file column. A count with a condition, a distinct count or any other function is a lakehouse_sql SELECT instead.
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


    async def _stream_schema(stream: str) -> list[dict]:
        body = await _call(client, "GET", "/query/schema", params={"stream": stream})
        return _schema_tables(body)

    async def _count_unmeasured(stream: str, tables: list[dict]) -> dict:
        """Row counts for the data tables Marina has not measured, one UNION ALL statement per chunk of COUNT_CHUNK views."""
        names = [t["name"] for t in tables if t["row_count"] is None and not is_meta_table(t["name"])]
        counts: dict = {}
        for i in range(0, len(names), COUNT_CHUNK):
            chunk = names[i:i + COUNT_CHUNK]
            sql = " UNION ALL ".join(f"SELECT '{v}' AS view, count(*) AS n FROM {qualified(client['id'], stream, v)}" for v in chunk)
            res = await _sql(client, sql)
            for row in res["rows"]:
                if isinstance(row, (list, tuple)) and len(row) >= 2:
                    counts[str(row[0])] = row[1]
        return counts

    @mcp.tool(name="lakehouse_sql_catalog", annotations=_READ_ONLY)
    async def lakehouse_sql_catalog(stream: str = "", table: str = "", counts: bool = False) -> dict:
        """The visible schema with Marina's statistics, in three layers so any answer fits a conversation. No arguments: every querying stream with its table count and total rows, and the largest tables across all streams. stream: that stream's tables by row count (columns inline when the stream has 40 tables or fewer). stream and table: every column with type, description and statistics where measured (null_count, distinct_count, min, max, mean, stddev, sum, min_length, max_length, empty_count, true_count, rows_by_year).

        Read this before writing SQL: it gives the fully qualified names. Nothing is cached here, so call it once and refer back.

        Args:
            stream: A querying stream name; empty for the overview.
            table: A table (view) name in that stream, for its columns and statistics.
            counts: true = for tables Marina has not measured yet, count rows now with count(*) statements (one per 50 tables). Needs stream. Off by default because it scans.
        """
        stream, table = (stream or "").strip(), (table or "").strip()
        try:
            if not stream:
                names = _stream_names(await _call(client, "GET", "/streams"))
                streams, largest, meta = [], [], 0
                for st in names:
                    tables = await _stream_schema(st)
                    data = [t for t in tables if not is_meta_table(t["name"])]
                    meta += len(tables) - len(data)
                    streams.append({"stream": st, "schema": schema_name(client["id"], st), "tables": len(data),
                                    "rows": sum(t["row_count"] for t in data if isinstance(t["row_count"], (int, float))),
                                    "unmeasured": sum(1 for t in data if t["row_count"] is None), "stats_table": qualified(client["id"], st, "_stats")})
                    largest.extend({"table": qualified(client["id"], st, t["name"]), "rows": t["row_count"]} for t in data if isinstance(t["row_count"], (int, float)))
                largest.sort(key=lambda x: -x["rows"])
                out = {"client": client["id"], "streams": streams, "largest_tables": largest[:LARGEST_TABLES], "metadata_tables": meta,
                       "stats_source": "marina", "next": "lakehouse_sql_catalog(stream) for one stream's tables; (stream, table) for a table's columns and statistics."}
                if counts:
                    out["note"] = "counts=true needs a stream; the overview shows Marina's counts only."
                return _fit(out, [("largest_tables", 10), ("streams", 20)])
            tables = await _stream_schema(stream)
            if table:
                hit = next((t for t in tables if t["name"] == table), None) or next((t for t in tables if t["name"].lower() == table.lower()), None)
                if not hit:
                    return {"error": f"no table '{table}' in stream {stream}", "tables": [t["name"] for t in tables if not is_meta_table(t["name"])][:200]}
                cols = []
                for c in hit["columns"]:
                    col = {"name": c["name"], "type": c["type"]}
                    if c["description"]:
                        col["description"] = c["description"]
                    if c["stats"]:
                        col.update({k: v for k, v in c["stats"].items() if v is not None})
                    cols.append(col)
                out = {"client": client["id"], "stream": stream, "table": hit["name"], "qualified": qualified(client["id"], stream, hit["name"]),
                       "description": hit["description"], "row_count": hit["row_count"], "columns": cols, "stats_source": "marina" if any(c["stats"] for c in hit["columns"]) else None}
                return _fit(out, [("columns", 80)])
            data = [t for t in tables if not is_meta_table(t["name"])]
            counted = await _count_unmeasured(stream, data) if counts else {}
            for t in data:
                if t["row_count"] is None and t["name"] in counted:
                    t["row_count"] = counted[t["name"]]
                    t["counted_now"] = True
            data.sort(key=lambda t: (t["row_count"] is None, -(t["row_count"] or 0)))
            inline = len(data) <= COLUMNS_INLINE_MAX
            rows = []
            for t in data:
                r = {"table": t["name"], "qualified": qualified(client["id"], stream, t["name"]), "rows": t["row_count"], "columns": len(t["columns"])}
                if t["description"]:
                    r["description"] = t["description"]
                if t.get("counted_now"):
                    r["counted_now"] = True
                if inline:
                    r["column_list"] = [f"{c['name']} {c['type']}".strip() for c in t["columns"]]
                rows.append(r)
            out = {"client": client["id"], "stream": stream, "schema": schema_name(client["id"], stream), "tables": rows, "table_count": len(rows),
                   "unmeasured": sum(1 for t in data if t["row_count"] is None), "stats_source": "marina" if any(t["row_count"] is not None and not t.get("counted_now") for t in data) else None,
                   "metadata_tables": [t["name"] for t in tables if is_meta_table(t["name"])],
                   "next": "lakehouse_sql_catalog(stream, table) for a table's columns and statistics" + ("" if inline else "; columns are not inline because the stream has more than 40 tables")}
            if not counts and out["unmeasured"]:
                out["note"] = f"{out['unmeasured']} tables have no row_count from Marina yet; counts=true counts them now (a scan)."
            return _fit(out, [("tables", 150), ("tables", 60)])
        except Exception as e:
            return _report(client, e)

    @mcp.tool(name="lakehouse_sql", annotations=_READ_ONLY)
    async def lakehouse_sql(sql: str, limit: int = 200) -> dict:
        """One SQL statement over the lakehouse through Marina: a SELECT or WITH over one stream's views, or SHOW SCHEMAS, SHOW TABLES IN a schema, SHOW COLUMNS, SHOW PROFILE IN a schema, DESCRIBE a view. Any Trino built-in function. Views are fully qualified as lakehouse."client_<id>__<stream>"."<view>" (lakehouse_sql_catalog gives the names). A LIMIT is added when a SELECT has none. Read only: Marina refuses anything else and says why.

        Args:
            sql: The statement, one only, no trailing statements.
            limit: Rows to return when the statement has no LIMIT, 1-500. Default 200.
        Returns: columns, types, rows (as lists in column order), returned, row_count, truncated, state, elapsed_ms, sql_run (the statement actually sent).
        """
        try:
            sql_run = prepare_sql(sql, limit)
        except ValueError as e:
            return {"error": str(e)}
        try:
            res = await _sql(client, sql_run)
        except Exception as e:
            return _report(client, e)
        out = slim_rows("sql", res, max(1, min(int(limit or 200), MAX_ROWS)))
        out.update({"types": res["types"], "state": res["state"], "elapsed_ms": res["elapsed_ms"], "sql_run": sql_run})
        out["truncated"] = out["truncated"] or res["truncated"]
        return out

    register_prompts(mcp, Path(__file__).parent / "skills")
    return mcp, {"lakehouse_index": lakehouse_index, "lakehouse_streams": lakehouse_streams, "lakehouse_schema": lakehouse_schema,
                 "lakehouse_query": lakehouse_query, "lakehouse_files": lakehouse_files, "lakehouse_file": lakehouse_file,
                 "lakehouse_sql_catalog": lakehouse_sql_catalog, "lakehouse_sql": lakehouse_sql}


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
lakehouse_sql_catalog, lakehouse_sql = _default_tools["lakehouse_sql_catalog"], _default_tools["lakehouse_sql"]
