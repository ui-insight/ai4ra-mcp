"""lakehouse SQL: the guards on a statement, the Trino protocol client (Basic auth, text/plain, nextUri, caps, cancel,
one re-mint on 401, Marina's messages verbatim), and the three layers of the catalog built on /query/schema."""

import json

import pytest

from ai4ra_mcp.servers.lakehouse import server as lh


# ---- guards ----

def test_prepare_sql_wraps_a_bare_select_and_leaves_the_rest_alone():
    assert lh.prepare_sql("SELECT a FROM t", 200) == "SELECT * FROM (SELECT a FROM t) AS q LIMIT 200"
    assert lh.prepare_sql("select a from t;", 9000) == "SELECT * FROM (select a from t) AS q LIMIT 500"
    assert lh.prepare_sql("WITH x AS (SELECT 1) SELECT * FROM x LIMIT 5", 200) == "WITH x AS (SELECT 1) SELECT * FROM x LIMIT 5"
    assert lh.prepare_sql("SELECT a FROM t LIMIT 10 OFFSET 20", 200) == "SELECT a FROM t LIMIT 10 OFFSET 20"
    assert lh.prepare_sql('SHOW PROFILE IN lakehouse."client_mr-365__subaward"', 200) == 'SHOW PROFILE IN lakehouse."client_mr-365__subaward"'
    assert lh.prepare_sql('DESCRIBE lakehouse."client_mr-365__subaward"."v"', 200).startswith("DESCRIBE")
    meta = 'SELECT * FROM lakehouse."client_mr-365__subaward"."_stats"'
    assert lh.prepare_sql(meta, 200) == meta   # gateway-evaluated: never wrapped


@pytest.mark.parametrize("sql,reason", [
    ("DROP TABLE x", "read only"), ("DELETE FROM lakehouse.s.v", "read only"), ("EXPLAIN SELECT 1", "read only"),
    ("SELECT 1; SELECT 2", "one statement"), ("", "empty"), ("   ;", "empty"),
])
def test_prepare_sql_refuses_with_a_reason(sql, reason):
    with pytest.raises(ValueError) as e:
        lh.prepare_sql(sql, 200)
    assert reason in str(e.value)


def test_names():
    assert lh.schema_name("mr-365", "subaward") == "client_mr-365__subaward"
    assert lh.qualified("mr-365", "subaward", "veras") == 'lakehouse."client_mr-365__subaward"."veras"'
    assert lh.is_meta_table("_stats") and not lh.is_meta_table("stats")


# ---- a fake Marina ----

class Resp:
    def __init__(self, status, body=None, text=""):
        self.status_code, self._body, self.text = status, body, text
        self.content = json.dumps(body).encode() if body is not None else (text.encode() if text else b"")
        self.headers = {}
    def json(self): return self._body


def make_client(monkeypatch, script: dict, calls: list):
    """script: url -> list of Resp popped in order (the last one repeats). Token calls always succeed."""
    minted = {"n": 0}

    class Client:
        def __init__(self, **kw): self.headers = kw.get("headers") or {}
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        def _next(self, url):
            lst = script.get(url)
            assert lst, f"unexpected call to {url}"
            return lst.pop(0) if len(lst) > 1 else lst[0]
        async def post(self, url, auth=None, data=None, content=None, headers=None):
            if url.endswith("/auth/token"):
                minted["n"] += 1
                calls.append(("token", auth)); return Resp(200, {"access_token": f"tok-{minted['n']}", "expires_in": 3600})
            calls.append(("POST", url, auth, (headers or {}).get("Content-Type"), content.decode() if content else None, self.headers.get("Authorization")))
            return self._next(url)
        async def get(self, url, auth=None):
            calls.append(("GET", url, auth)); return self._next(url)
        async def delete(self, url, auth=None):
            calls.append(("DELETE", url, auth)); return Resp(204)
        async def request(self, method, url, params=None, json=None):
            calls.append((method, url, self.headers.get("Authorization"), params)); return self._next(url.split("?")[0])

    monkeypatch.setattr(lh.httpx, "AsyncClient", Client)
    lh._tokens.clear()
    monkeypatch.setenv("AI4RA_MCP_LAKEHOUSE_SECRET", "s3")


STMT = f"{lh.BASE}/sql/v1/statement"
NEXT1, NEXT2 = f"{lh.BASE}/sql/v1/statement/q1/1", f"{lh.BASE}/sql/v1/statement/q1/2"


async def test_sql_uses_basic_auth_text_plain_and_follows_next_uri(monkeypatch):
    calls = []
    make_client(monkeypatch, {
        STMT: [Resp(200, {"id": "q1", "nextUri": NEXT1, "stats": {"state": "QUEUED"}})],
        NEXT1: [Resp(200, {"id": "q1", "nextUri": NEXT2, "columns": [{"name": "state", "type": "varchar"}, {"name": "n", "type": "bigint"}], "data": [["ID", 3]], "stats": {"state": "RUNNING"}})],
        NEXT2: [Resp(200, {"id": "q1", "data": [["WA", 2]], "stats": {"state": "FINISHED"}})],
    }, calls)
    out = await lh.lakehouse_sql('SELECT state, count(*) AS n FROM lakehouse."client_mr-365__subaward"."v" GROUP BY state')
    post = next(c for c in calls if c[0] == "POST")
    assert post[2] == (lh.CLIENT_ID, "tok-1") and post[3] == "text/plain" and post[5] is None   # Basic, not a Bearer header
    assert post[4].startswith("SELECT * FROM (SELECT state") and post[4].endswith("LIMIT 200")
    assert out["columns"] == ["state", "n"] and out["types"] == ["varchar", "bigint"] and out["rows"] == [["ID", 3], ["WA", 2]]
    assert out["state"] == "FINISHED" and out["truncated"] is False and out["sql_run"] == post[4] and out["returned"] == 2
    assert [c[0] for c in calls] == ["token", "POST", "GET", "GET"]


async def test_sql_passes_marina_failure_message_verbatim(monkeypatch):
    calls = []
    msg = 'Table not found. Use SHOW TABLES IN lakehouse."client_mr-365__subaward" to list the views you may query.'
    make_client(monkeypatch, {STMT: [Resp(200, {"id": "q1", "stats": {"state": "FAILED"}, "error": {"message": msg, "errorName": "TABLE_NOT_FOUND"}})]}, calls)
    out = await lh.lakehouse_sql('SELECT * FROM lakehouse."client_mr-365__subaward"."nope"')
    assert out == {"error": msg}
    make_client(monkeypatch, {STMT: [Resp(400, {"error": {"message": "Only SELECT, WITH, SHOW and DESCRIBE are accepted."}})]}, calls)
    out = await lh.lakehouse_sql("SHOW SESSION")
    assert out == {"error": "Only SELECT, WITH, SHOW and DESCRIBE are accepted."}


async def test_sql_mints_again_once_on_401_mid_poll(monkeypatch):
    calls = []
    make_client(monkeypatch, {
        STMT: [Resp(200, {"id": "q1", "nextUri": NEXT1, "stats": {"state": "QUEUED"}}), Resp(200, {"id": "q2", "data": [[1]], "columns": [{"name": "x", "type": "integer"}], "stats": {"state": "FINISHED"}})],
        NEXT1: [Resp(401)],
    }, calls)
    out = await lh.lakehouse_sql("SELECT 1 AS x LIMIT 1")
    assert out["rows"] == [[1]]
    assert sum(1 for c in calls if c[0] == "token") == 2
    posts = [c for c in calls if c[0] == "POST"]
    assert len(posts) == 2 and posts[0][2] == (lh.CLIENT_ID, "tok-1") and posts[1][2] == (lh.CLIENT_ID, "tok-2")


async def test_sql_stops_at_the_row_cap_and_cancels(monkeypatch):
    calls = []
    big = [[i] for i in range(lh.MAX_ROWS + 50)]
    make_client(monkeypatch, {
        STMT: [Resp(200, {"id": "q1", "nextUri": NEXT1, "columns": [{"name": "i", "type": "integer"}], "data": big, "stats": {"state": "RUNNING"}})],
        NEXT1: [Resp(200, {"id": "q1", "data": [[9]], "stats": {"state": "FINISHED"}})],
    }, calls)
    out = await lh.lakehouse_sql("SELECT i FROM lakehouse.\"client_mr-365__s\".\"v\" LIMIT 1000", limit=500)
    assert out["truncated"] is True and out["returned"] == lh.MAX_ROWS
    assert ("DELETE", NEXT1, (lh.CLIENT_ID, "tok-1")) in calls and not any(c[0] == "GET" for c in calls)


async def test_sql_without_a_secret_says_so(monkeypatch):
    monkeypatch.delenv("AI4RA_MCP_LAKEHOUSE_SECRET", raising=False)
    out = await lh.lakehouse_sql("SELECT 1")
    assert "no API key" in out["error"]


# ---- the catalog ----

def schema_body(tables):
    return {"stream": "x", "tables": tables, "stats": {"table": "_stats"}}


def table(name, rows, cols=2, stats=None, desc=""):
    return {"name": name, "description": desc, "row_count": rows,
            "columns": [{"name": f"c{i}", "type": "varchar", "description": "", "stats": stats} for i in range(cols)]}


STREAMS = f"{lh.BASE}/streams"
SCHEMA = f"{lh.BASE}/query/schema"


async def test_catalog_overview_ranks_largest_tables_across_streams_and_skips_metadata(monkeypatch):
    calls = []
    make_client(monkeypatch, {
        STREAMS: [Resp(200, {"client_id": "mr-365", "querying": [{"name": "subaward", "stats_table": "_stats"}, "personnel"], "submitting": ["intake"]})],
        SCHEMA: [Resp(200, schema_body([table("awards", 5000), table("_stats", 12), table("subs", None)])),
                 Resp(200, schema_body([table("people", 90000), table("depts", 40)]))],
    }, calls)
    out = await lh.lakehouse_sql_catalog()
    assert [s["stream"] for s in out["streams"]] == ["subaward", "personnel"]
    assert out["streams"][0] == {"stream": "subaward", "schema": "client_mr-365__subaward", "tables": 2, "rows": 5000, "unmeasured": 1, "stats_table": 'lakehouse."client_mr-365__subaward"."_stats"'}
    assert [t["rows"] for t in out["largest_tables"]] == [90000, 5000, 40] and out["largest_tables"][0]["table"] == 'lakehouse."client_mr-365__personnel"."people"'
    assert out["metadata_tables"] == 1 and out["stats_source"] == "marina"
    assert [c for c in calls if c[0] == "GET" and "/query/schema" in c[1]][0][3] == {"stream": "subaward"}
    assert not any(c[0] == "POST" for c in calls)   # REST only: no SQL for the overview


async def test_catalog_stream_layer_lists_tables_by_size_with_columns_inline_for_small_streams(monkeypatch):
    calls = []
    make_client(monkeypatch, {SCHEMA: [Resp(200, schema_body([table("small", 10, cols=1), table("big", 700, cols=3, desc="the big one"), table("_stats", 2), table("new", None)]))]}, calls)
    out = await lh.lakehouse_sql_catalog(stream="subaward")
    assert [t["table"] for t in out["tables"]] == ["big", "small", "new"] and out["tables"][0]["column_list"] == ["c0 varchar", "c1 varchar", "c2 varchar"]
    assert out["tables"][0]["description"] == "the big one" and out["tables"][2]["rows"] is None and out["unmeasured"] == 1
    assert out["metadata_tables"] == ["_stats"] and "counts=true" in out["note"] and out["schema"] == "client_mr-365__subaward"
    many = [table(f"t{i}", i) for i in range(50)]
    make_client(monkeypatch, {SCHEMA: [Resp(200, schema_body(many))]}, calls)
    out = await lh.lakehouse_sql_catalog(stream="subaward")
    assert "column_list" not in out["tables"][0] and "more than 40 tables" in out["next"] and out["table_count"] == 50


async def test_catalog_table_layer_passes_marina_stats_keys_through(monkeypatch):
    calls = []
    stats = {"null_count": 3, "distinct_count": 40, "min": "2019-01-01", "max": "2026-09-01", "true_count": None, "rows_by_year": {"2025": 10}}
    make_client(monkeypatch, {SCHEMA: [Resp(200, schema_body([table("awards", 5000, cols=1, stats=stats, desc="Awards")]))]}, calls)
    out = await lh.lakehouse_sql_catalog(stream="subaward", table="AWARDS")
    assert out["qualified"] == 'lakehouse."client_mr-365__subaward"."awards"' and out["row_count"] == 5000 and out["description"] == "Awards"
    col = out["columns"][0]
    assert col == {"name": "c0", "type": "varchar", "null_count": 3, "distinct_count": 40, "min": "2019-01-01", "max": "2026-09-01", "rows_by_year": {"2025": 10}}
    assert out["stats_source"] == "marina"
    missing = await lh.lakehouse_sql_catalog(stream="subaward", table="nope")
    assert "no table 'nope'" in missing["error"] and missing["tables"] == ["awards"]


async def test_catalog_counts_only_unmeasured_tables_in_chunks_of_fifty(monkeypatch):
    calls = []
    tables = [table("measured", 10)] + [table(f"u{i}", None) for i in range(60)]
    rows1 = [[f"u{i}", i] for i in range(50)]
    rows2 = [[f"u{i}", i] for i in range(50, 60)]
    make_client(monkeypatch, {
        SCHEMA: [Resp(200, schema_body(tables))],
        STMT: [Resp(200, {"id": "c1", "columns": [{"name": "view", "type": "varchar"}, {"name": "n", "type": "bigint"}], "data": rows1, "stats": {"state": "FINISHED"}}),
               Resp(200, {"id": "c2", "columns": [{"name": "view", "type": "varchar"}, {"name": "n", "type": "bigint"}], "data": rows2, "stats": {"state": "FINISHED"}})],
    }, calls)
    out = await lh.lakehouse_sql_catalog(stream="subaward", counts=True)
    posts = [c for c in calls if c[0] == "POST"]
    assert len(posts) == 2 and posts[0][4].count("UNION ALL") == 49 and posts[1][4].count("UNION ALL") == 9
    assert "measured" not in posts[0][4] and posts[0][4].startswith("SELECT 'u0' AS view, count(*) AS n FROM lakehouse.\"client_mr-365__subaward\".\"u0\"")
    by = {t["table"]: t for t in out["tables"]}
    assert by["u59"]["rows"] == 59 and by["u59"]["counted_now"] is True and "counted_now" not in by["measured"] and out["unmeasured"] == 0


def test_fit_trims_lists_and_says_so():
    obj = {"largest_tables": [{"table": "x" * 200, "rows": i} for i in range(400)], "streams": [1, 2, 3]}
    out = lh._fit(obj, [("largest_tables", 10), ("streams", 20)])
    assert len(out["largest_tables"]) == 10 and out["left_out"] == ["390 of largest_tables"] and len(json.dumps(out)) <= lh.MAX_CHARS


async def test_index_names_the_sql_tools():
    idx = await lh.lakehouse_index()
    assert any("lakehouse_sql_catalog" in w for w in idx["workflow"]) and any("lakehouse_sql(" in w for w in idx["workflow"])
    names = {t.name for t in await lh.mcp.list_tools()}
    assert {"lakehouse_sql_catalog", "lakehouse_sql"} <= names
