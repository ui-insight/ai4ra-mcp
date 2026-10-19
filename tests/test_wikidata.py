"""wikidata, offline from responses captured 2026-10-19 in tests/fixtures/wikidata/ (a search for Kant, a property search, a search with no
match, Kant's item with 336 properties, an unknown id, a label batch, a SPARQL result): the search, the entity with ids resolved to labels in
batches of fifty, dates at their precision, qualifiers, identifiers left out or kept, the SPARQL rows with ids shortened, the refusals."""

import json
from pathlib import Path

from ai4ra_mcp.servers.wikidata import server as w

FIX = Path(__file__).parent / "fixtures" / "wikidata"
F = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in FIX.glob("*.json")}
REAL_LABELS = {e: ent["labels"]["en"]["value"] for e, ent in F["labels_batch"]["entities"].items()}


def _wikidata(monkeypatch, calls=None, sparql_error=None):
    calls = calls if calls is not None else []

    async def get_json(url, params=None, headers=None):
        calls.append((url, dict(params or {}), dict(headers or {})))
        if url == w.SPARQL:
            if sparql_error:
                raise ValueError(sparql_error)
            return F["sparql_ok"]
        a = params["action"]
        if a == "wbsearchentities":
            return {"item": F["search_kant"], "property": F["search_prop"]}[params["type"]] if "zzq" not in params["search"] else F["search_none"]
        ids = params["ids"].split("|")
        if params["props"] == "labels":
            # Every id gets a label, the real one when the batch fixture has it, so a resolution is checkable.
            # Every id gets a label, the real one when the batch fixture has it; Q18960 (Porifera) only the all-languages one, as Wikidata has it.
            return {"entities": {i: {"id": i, "labels": ({"mul": {"value": "Porifera"}} if i == "Q18960" else {"en": {"value": REAL_LABELS.get(i, f"label of {i}")}})} for i in ids}}
        return F["entity_kant"] if ids == ["Q9312"] else F["entity_bad"]

    monkeypatch.setattr(w, "get_json", get_json)
    w._cache._d.clear()
    return calls


def test_time_and_values():
    assert w._time({"time": "+1724-04-22T00:00:00Z", "precision": 11}) == "1724-04-22"
    assert w._time({"time": "+1740-00-00T00:00:00Z", "precision": 9}) == "1740"
    assert w._time({"time": "+1781-01-00T00:00:00Z", "precision": 10}) == "1781-01"
    assert w._time({"time": "-0384-00-00T00:00:00Z", "precision": 9, "calendarmodel": "http://www.wikidata.org/entity/Q1985786"}) == "-384 (Julian)"
    assert w._time({"time": "+1700-00-00T00:00:00Z", "precision": 7}) == "1700 (century)"
    assert w._value({"snaktype": "novalue"}, {}) == {"value": None, "note": "no value"}
    assert w._value({"snaktype": "value", "datavalue": {"type": "quantity", "value": {"amount": "+1.75", "unit": "http://www.wikidata.org/entity/Q11573"}}}, {"Q11573": "metre"}) == {"amount": "1.75", "unit": {"id": "Q11573", "label": "metre"}}
    assert w._value({"snaktype": "value", "datatype": "commonsMedia", "datavalue": {"type": "string", "value": "Immanuel Kant - Gemaelde 2.jpg"}}, {}) == {"file": "Immanuel Kant - Gemaelde 2.jpg", "url": "https://commons.wikimedia.org/wiki/File:Immanuel_Kant_-_Gemaelde_2.jpg"}
    assert w.shorten({"type": "uri", "value": "http://www.wikidata.org/entity/Q168004"}) == "Q168004" and w.shorten({"type": "literal", "value": "1743-01-25T00:00:00Z"}) == "1743-01-25T00:00:00Z"
    assert w.query_form('PREFIX wd: <http://www.wikidata.org/entity/>\n# a comment\nselect ?p where { ?p wdt:P737 wd:Q9312 }') == "SELECT" and w.query_form("ASK { wd:Q9312 wdt:P31 wd:Q5 }") == "ASK"
    assert w.query_form("DESCRIBE wd:Q9312") is None and w.query_form("INSERT DATA { }") is None and w.query_form("") is None


async def test_search(monkeypatch):
    calls = _wikidata(monkeypatch)
    out = await w.wikidata_search("Immanuel Kant", rows=5)
    assert calls[0][0] == w.API and calls[0][1] == {"action": "wbsearchentities", "search": "Immanuel Kant", "language": "en", "uselang": "en", "type": "item", "limit": 5, "format": "json"}
    assert out["matches"][0]["id"] == "Q9312" and out["matches"][0]["label"] == "Immanuel Kant" and out["matches"][0]["description"] == "German philosopher (1724-1804)" and out["matches"][0]["link"] == "https://www.wikidata.org/wiki/Q9312"
    prop = await w.wikidata_search("influenced by", type="property")
    assert prop["matches"][0]["id"] == "P737" and prop["matches"][0]["datatype"] == "wikibase-item" and prop["matches"][0]["link"] == "https://www.wikidata.org/wiki/Property:P737"
    none = await w.wikidata_search("zzqxvflorpquux")
    assert none["returned"] == 0 and "note" in none
    assert "type must be" in (await w.wikidata_search("x", type="lexeme"))["error"] and "query is required" in (await w.wikidata_search(""))["error"]


async def test_entity_resolves_labels_in_batches(monkeypatch):
    calls = _wikidata(monkeypatch)
    out = await w.wikidata_entity("Q9312")
    first = calls[0][1]
    assert first["action"] == "wbgetentities" and first["ids"] == "Q9312" and first["props"] == "labels|descriptions|aliases|claims|sitelinks" and first["sitefilter"] == "enwiki" and first["languages"] == "en|mul"
    label_calls = [c for c in calls[1:] if c[1]["props"] == "labels"]
    assert label_calls and all(len(c[1]["ids"].split("|")) <= 50 and c[1]["languages"] == "en|mul" for c in label_calls) and sum(len(c[1]["ids"].split("|")) for c in label_calls) <= w.MAX_IDS
    assert (await w.labels_for(["Q18960", "Q37160"], "en")) == {"Q18960": "Porifera", "Q37160": "David Hume"}
    assert w.term({"labels": {"mul": {"value": "Porifera"}}}, "labels", "en") == "Porifera" and w.term({"labels": {}}, "labels", "en") is None
    assert out["label"] == "Immanuel Kant" and out["description"] == "German philosopher (1724-1804)" and out["wikipedia"] == {"title": "Immanuel Kant", "url": "https://en.wikipedia.org/wiki/Immanuel_Kant"}
    by = {s["property"]["id"]: s for s in out["statements"]}
    assert "P569" in by and by["P569"]["property"]["label"] == "date of birth" and by["P569"]["values"][0]["value"] == "1724-04-22" and by["P569"]["values"][0]["references"] == 9
    assert {"id": "Q37160", "label": "David Hume"} in [v["value"] for v in by["P737"]["values"]] and by["P737"]["property"]["label"] == "influenced by"
    assert by["P69"]["values"][0]["qualifiers"]["label of P580"] == ["1740"] and by["P69"]["values"][0]["value"]["id"] == "Q672420"
    assert out["identifiers_left_out"] == 318 and "P214" not in by and out["statement_count"] == sum(len(s["values"]) for s in out["statements"]) and out["link"] == "https://www.wikidata.org/wiki/Q9312"
    # Narrowed to two properties, and with identifiers kept.
    narrow = await w.wikidata_entity("Q9312", properties="P737,P569")
    assert [s["property"]["id"] for s in narrow["statements"]] == ["P737", "P569"] or set(s["property"]["id"] for s in narrow["statements"]) == {"P737", "P569"}
    full = await w.wikidata_entity("Q9312", identifiers=True)
    assert full["identifiers_left_out"] == 0 and any(s["property"]["id"] == "P214" for s in full["statements"])
    assert (await w.wikidata_entity("Q999999999999"))["error"].startswith("Could not find an entity")
    assert "id must be" in (await w.wikidata_entity("kant"))["error"] and "properties must be" in (await w.wikidata_entity("Q9312", properties="Q1"))["error"]


async def test_sparql(monkeypatch):
    calls = _wikidata(monkeypatch)
    q = 'SELECT ?p ?pLabel ?born WHERE {?p wdt:P737 wd:Q9312; wdt:P106 wd:Q4964182; wdt:P569 ?born. SERVICE wikibase:label {bd:serviceParam wikibase:language "en"}} ORDER BY ?born LIMIT 5'
    out = await w.wikidata_sparql(q, rows=3)
    assert calls[0][0] == w.SPARQL and calls[0][1] == {"query": q, "format": "json"} and calls[0][2]["Accept"] == "application/sparql-results+json"
    assert out["variables"] == ["p", "pLabel", "born"] and out["returned"] == 3 and out["total_returned_by_service"] == 5 and out["truncated"] is True
    assert out["rows"][0] == {"p": "Q168004", "born": "1743-01-25T00:00:00Z", "pLabel": "Friedrich Heinrich Jacobi"} and out["link"].startswith("https://query.wikidata.org/#SELECT")
    await w.wikidata_sparql(q, rows=3)
    assert len(calls) == 1
    assert "only SELECT and ASK" in (await w.wikidata_sparql("DESCRIBE wd:Q9312"))["error"] and "query is required" in (await w.wikidata_sparql(" "))["error"]
    _wikidata(monkeypatch, sparql_error="rate limit exceeded at query.wikidata.org; wait before retrying")
    assert "throttling" in (await w.wikidata_sparql(q))["error"]
    _wikidata(monkeypatch, sparql_error="400 from query.wikidata.org: SPARQL-QUERY: queryStr=SELECT ?p WHERE { ?p wdt:P737 \njava.util.concurrent.ExecutionException: org.openrdf.query.MalformedQueryException: Encountered \"<EOF>\"")
    bad = await w.wikidata_sparql("SELECT ?p WHERE { ?p wdt:P737 ")
    assert bad["error"].startswith("400 from") and "MalformedQueryException" in bad["error"]
    idx = await w.wikidata_index()
    assert "one client for everyone" in idx["limits"][0] and idx["workflow"][0].startswith("wikidata_search")
