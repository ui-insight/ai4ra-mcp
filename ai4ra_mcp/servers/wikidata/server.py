"""wikidata: Wikidata's structured facts, no key: an entity by name, its statements with every id resolved to a label, and a read-only SPARQL query.

Upstream: the Wikibase action API at https://www.wikidata.org/w/api.php (wbsearchentities for entities by name or alias,
wbgetentities for an item's labels, descriptions, aliases, claims and sitelinks, and for resolving up to fifty ids to
labels in one call) and the Wikidata Query Service at https://query.wikidata.org/sparql (SELECT and ASK, JSON results).
No key: Wikimedia asks for a User-Agent that names the caller (this project's does), and the Query Service limits each
client (user agent and address) to 60 seconds of processing a minute, five parallel queries and a 60-second query, with
429 and Retry-After beyond that; those limits are the server's, shared by everyone on it. Data is CC0. An entity is cached a
day, a search an hour, a query result five minutes (the Service's own max-age).
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
API = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"
SITE = "https://www.wikidata.org"
COMMONS = "https://commons.wikimedia.org/wiki/File:"
ENTITY_URI = "http://www.wikidata.org/entity/"
BATCH, MAX_IDS, MAX_ROWS, MAX_QUERY_CHARS = 50, 500, 500, 10000
JULIAN = "Q1985786"
_ID = re.compile(r"^[PQL]\d+$")
_COMMENT = re.compile(r"#[^\n]*")
_PREFIX = re.compile(r"^\s*(?:PREFIX\s+\S+\s+<[^>]*>\s*|BASE\s+<[^>]*>\s*)*", re.I)
_cache = TTLCache()

mcp = MCPServer(
    "wikidata",
    instructions="Wikidata, the structured knowledge base behind Wikipedia: an entity by name (wikidata_search), its statements with properties and values resolved to labels (wikidata_entity), and a read-only SPARQL query for list questions (wikidata_sparql): who influenced whom, a school's members with dates, a person's works, positions and places, with the item ids and links. No key; the query quota is shared. Read wikidata_index first.",
)


def entity_page(eid: str) -> str:
    return f"{SITE}/wiki/{'Property:' if eid.startswith('P') else ''}{eid}"


def _time(v: dict) -> str:
    """Wikidata's time to a date string at the value's own precision: +1724-04-22T00:00:00Z at precision 11 is 1724-04-22,
    +1740-00-00 at precision 9 is 1740; a BCE year keeps its sign; a Julian-calendar value says so."""
    t, p = v.get("time", ""), v.get("precision", 11)
    sign = "-" if t.startswith("-") else ""
    m = re.match(r"[+-]?(\d+)-(\d\d)-(\d\d)", t)
    if not m:
        return t
    y, mo, d = m.groups()
    s = f"{sign}{int(y)}" if p <= 9 else f"{sign}{int(y):04d}-{mo}" if p == 10 else f"{sign}{int(y):04d}-{mo}-{d}"
    if p < 9:
        s += {8: " (decade)", 7: " (century)", 6: " (millennium)"}.get(p, " (approximate)")
    if v.get("calendarmodel", "").endswith(JULIAN):
        s += " (Julian)"
    return s


def _value(snak: dict, labels: dict[str, str]) -> object:
    """One snak's value, readable: an item as id and label, a time as a date, a quantity with its unit's label."""
    if snak.get("snaktype") == "novalue":
        return {"value": None, "note": "no value"}
    if snak.get("snaktype") == "somevalue":
        return {"value": None, "note": "unknown value"}
    dv = snak.get("datavalue") or {}
    v, t = dv.get("value"), dv.get("type")
    if t == "wikibase-entityid":
        return {"id": v["id"], "label": labels.get(v["id"])}
    if t == "time":
        return _time(v)
    if t == "quantity":
        out: dict = {"amount": v.get("amount", "").lstrip("+")}
        unit = (v.get("unit") or "1").rsplit("/", 1)[-1]
        if unit != "1":
            out["unit"] = {"id": unit, "label": labels.get(unit)}
        if v.get("lowerBound") or v.get("upperBound"):
            out["bounds"] = [v.get("lowerBound", "").lstrip("+"), v.get("upperBound", "").lstrip("+")]
        return out
    if t == "monolingualtext":
        return {"text": v.get("text"), "language": v.get("language")}
    if t == "globecoordinate":
        return {"latitude": v.get("latitude"), "longitude": v.get("longitude")}
    if snak.get("datatype") == "commonsMedia":
        return {"file": v, "url": COMMONS + str(v).replace(" ", "_")}
    return v


def _ids_in(snak: dict) -> list[str]:
    dv = snak.get("datavalue") or {}
    if dv.get("type") == "wikibase-entityid":
        return [dv["value"]["id"]]
    if dv.get("type") == "quantity":
        unit = (dv["value"].get("unit") or "1").rsplit("/", 1)[-1]
        return [unit] if unit != "1" else []
    return []


def statements(entity: dict, labels: dict[str, str], identifiers: bool) -> tuple[list[dict], int]:
    """The claims as statements grouped by property, deprecated ones left out, external identifiers left out unless asked."""
    out, skipped = [], 0
    for pid, claims in (entity.get("claims") or {}).items():
        kept = [c for c in claims if c.get("rank") != "deprecated"]
        if not kept:
            continue
        if kept[0]["mainsnak"].get("datatype") == "external-id" and not identifiers:
            skipped += len(kept)
            continue
        values = []
        for c in kept:
            row: dict = {"value": _value(c["mainsnak"], labels), "rank": c.get("rank")}
            if c.get("qualifiers"):
                row["qualifiers"] = {labels.get(q) or q: [_value(s, labels) for s in snaks] for q, snaks in c["qualifiers"].items()}
            if c.get("references"):
                row["references"] = len(c["references"])
            values.append(row)
        out.append({"property": {"id": pid, "label": labels.get(pid)}, "values": values})
    return out, skipped


def ids_to_resolve(entity: dict, identifiers: bool) -> list[str]:
    ids: list[str] = []
    for pid, claims in (entity.get("claims") or {}).items():
        if claims and claims[0]["mainsnak"].get("datatype") == "external-id" and not identifiers:
            continue
        ids.append(pid)
        for c in claims:
            if c.get("rank") == "deprecated":
                continue
            ids.extend(_ids_in(c["mainsnak"]))
            for q, snaks in (c.get("qualifiers") or {}).items():
                ids.append(q)
                for s in snaks:
                    ids.extend(_ids_in(s))
    seen: dict[str, None] = {}
    for i in ids:
        seen.setdefault(i, None)
    return list(seen)[:MAX_IDS]


async def _api(params: dict, ttl: float) -> dict:
    params = {**params, "format": "json"}
    key = "api:" + repr(sorted(params.items()))
    return await _cache.remember(key, ttl, lambda: get_json(API, params))


async def labels_for(ids: list[str], language: str) -> dict[str, str]:
    """Labels for up to MAX_IDS ids, fifty a call (the API's limit), each batch cached a day."""
    out: dict[str, str] = {}
    for i in range(0, len(ids), BATCH):
        batch = ids[i:i + BATCH]
        body = await _api({"action": "wbgetentities", "ids": "|".join(batch), "props": "labels", "languages": language}, DAY)
        for eid, ent in (body.get("entities") or {}).items():
            lab = (ent.get("labels") or {}).get(language, {}).get("value")
            if lab:
                out[eid] = lab
    return out


def shorten(binding: dict) -> object:
    """A SPARQL binding's value: an entity URI as its id, a literal as its value."""
    v = binding.get("value")
    if binding.get("type") == "uri" and isinstance(v, str) and v.startswith(ENTITY_URI):
        return v[len(ENTITY_URI):]
    return v


def query_form(query: str) -> str | None:
    """SELECT or ASK when the query is one (after its prefixes and comments), else None."""
    q = _COMMENT.sub("", query or "")
    q = _PREFIX.sub("", q).lstrip()
    first = q.split(None, 1)[0].upper() if q.split() else ""
    return first if first in ("SELECT", "ASK") else None


@mcp.tool(name="wikidata_index", annotations=_READ_ONLY)
async def wikidata_index() -> dict:
    """How to use the Wikidata tools. READ THIS FIRST: the three tools, how a statement reads, the shared query limits, how to cite."""
    return {
        "upstream": f"Wikidata's action API ({API}: wbsearchentities, wbgetentities) and the Wikidata Query Service ({SPARQL}). No key; data CC0.",
        "workflow": ["wikidata_search a name or alias to get the item id (Q…), or a property name to get its id (P…)",
                     "wikidata_entity the id for its statements: each property with its label and its values resolved to labels, dates and quantities, with qualifiers (start and end times, positions, points in time)",
                     "wikidata_sparql for a list question: members of a school, people influenced by someone, works by decade; write SELECT with the wikibase:label service for labels, and name ids the earlier tools gave",
                     "cite an item by its id and link; a fact's statement may carry references (their count is given), which the item page lists"],
        "reading": ["A statement is property, value, qualifiers, rank; preferred rank is the community's current pick when a property has several values; deprecated statements are left out.",
                    "Dates come at their own precision: 1724-04-22, 1740, or a decade or century marked; a Julian-calendar date says so. Quantities carry a unit's label.",
                    "External identifiers (ORCID, ROR, VIAF, SEP, PhilPapers and three hundred more) are left out unless identifiers=true, since an item like Kant carries hundreds; the count left out is given."],
        "limits": ["The Query Service allows one client 60 seconds of processing a minute, five parallel queries and a 60-second query, and this server is one client for everyone on it: a 429 with its Retry-After is said, and the next query waits.",
                   f"wikidata_entity resolves up to {MAX_IDS} ids to labels, fifty a call; wikidata_sparql returns up to {MAX_ROWS} rows and says when it cut.",
                   "An entity is cached a day, a search an hour, a query result five minutes."],
        "notes": ["Wikidata is crowd-maintained: a statement without references is a claim someone entered, and a date or relation worth relying on is checked on the item page or in a cited source.",
                  "Labels and descriptions come in the language asked for (two-letter code, 'en' by default); an item without a label in that language shows its id alone."],
    }


@mcp.tool(name="wikidata_search", annotations=_READ_ONLY)
async def wikidata_search(query: str, type: str = "item", language: str = "en", rows: int = 10) -> dict:
    """Find Wikidata entities by name or alias.

    Returns each match with its id, label, description, the alias that matched, and its page. Use it to get the Q-id of a person,
    place, work, concept or organisation, or the P-id of a property, before wikidata_entity or a query.

    Args:
        query: A name or alias, e.g. 'Immanuel Kant', 'Vienna Circle', 'influenced by'.
        type: 'item' (default) or 'property'.
        language: Two-letter language code for the search and the labels. Default 'en'.
        rows: Matches to return, 1-50. Default 10.
    """
    q = " ".join((query or "").split())
    if not q:
        return {"error": "query is required"}
    if type not in ("item", "property"):
        return {"error": "type must be 'item' or 'property'"}
    lang = (language or "en").strip().lower()
    try:
        body = await _api({"action": "wbsearchentities", "search": q, "language": lang, "uselang": lang, "type": type, "limit": max(1, min(int(rows or 10), 50))}, HOUR)
    except ValueError as e:
        return {"error": str(e)}
    if body.get("error"):
        return {"error": body["error"].get("info") or body["error"].get("code")}
    matches = [{"id": m["id"], "label": m.get("label"), "description": m.get("description"), "matched": (m.get("match") or {}).get("text"),
                "datatype": m.get("datatype"), "link": entity_page(m["id"])} for m in body.get("search") or []]
    out = {"query": q, "type": type, "language": lang, "returned": len(matches), "matches": matches}
    if not matches:
        out["note"] = "No entity has this name or alias in that language; try another spelling, the native-language name, or a broader term."
    return out


@mcp.tool(name="wikidata_entity", annotations=_READ_ONLY)
async def wikidata_entity(id: str, properties: str = "", language: str = "en", identifiers: bool = False) -> dict:
    """One Wikidata entity: label, description, aliases, Wikipedia article, and its statements with every property and value resolved to a label.

    Args:
        id: The entity id from wikidata_search, e.g. 'Q9312' (an item) or 'P737' (a property).
        properties: Comma-separated P-ids to keep, e.g. 'P737,P800,P69'. Empty for all.
        language: Two-letter language code for labels. Default 'en'.
        identifiers: True includes external identifiers (ORCID, VIAF, SEP and the rest). Default False.
    """
    eid = (id or "").strip().upper()
    if not _ID.match(eid):
        return {"error": "id must be a Wikidata id like Q9312 or P737, from wikidata_search"}
    lang = (language or "en").strip().lower()
    keep = {p.strip().upper() for p in (properties or "").split(",") if p.strip()}
    if any(not _ID.match(p) or not p.startswith("P") for p in keep):
        return {"error": "properties must be P-ids separated by commas, e.g. 'P737,P800'"}
    try:
        body = await _api({"action": "wbgetentities", "ids": eid, "props": "labels|descriptions|aliases|claims|sitelinks", "languages": lang, "sitefilter": f"{lang}wiki"}, DAY)
    except ValueError as e:
        return {"error": str(e)}
    if body.get("error"):
        return {"error": body["error"].get("info") or body["error"].get("code"), "note": "Entity ids come from wikidata_search as given."}
    ent = (body.get("entities") or {}).get(eid) or {}
    if "missing" in ent or not ent:
        return {"error": f"no entity {eid}", "note": "Entity ids come from wikidata_search as given."}
    if keep:
        ent = {**ent, "claims": {p: c for p, c in (ent.get("claims") or {}).items() if p in keep}}
    try:
        labels = await labels_for(ids_to_resolve(ent, identifiers), lang)
    except ValueError as e:
        return {"error": f"the entity was read but its labels were not: {e}"}
    sts, skipped = statements(ent, labels, identifiers)
    sitelink = (ent.get("sitelinks") or {}).get(f"{lang}wiki")
    return {
        "id": eid, "type": ent.get("type"), "label": (ent.get("labels") or {}).get(lang, {}).get("value"),
        "description": (ent.get("descriptions") or {}).get(lang, {}).get("value"),
        "aliases": [a["value"] for a in (ent.get("aliases") or {}).get(lang, [])],
        "wikipedia": {"title": sitelink["title"], "url": f"https://{lang}.wikipedia.org/wiki/{sitelink['title'].replace(' ', '_')}"} if sitelink else None,
        "datatype": ent.get("datatype"), "language": lang, "statements": sts, "statement_count": sum(len(s["values"]) for s in sts),
        "identifiers_left_out": skipped, "modified": ent.get("modified"), "link": entity_page(eid),
    }


@mcp.tool(name="wikidata_sparql", annotations=_READ_ONLY)
async def wikidata_sparql(query: str, rows: int = 50) -> dict:
    """Run a read-only SPARQL query (SELECT or ASK) on the Wikidata Query Service.

    Returns the variables and the rows, entity URIs shortened to ids, literals as their values. Use the wikibase:label service
    for labels: SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } and ?xLabel for each ?x. Name ids the
    earlier tools gave rather than ids from memory.

    Args:
        query: The SPARQL text, e.g. 'SELECT ?p ?pLabel WHERE { ?p wdt:P737 wd:Q9312 . SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } } LIMIT 50'.
        rows: Rows to return at most, 1-500. Default 50.
    """
    q = (query or "").strip()
    if not q:
        return {"error": "query is required"}
    if len(q) > MAX_QUERY_CHARS:
        return {"error": f"query is longer than {MAX_QUERY_CHARS} characters"}
    form = query_form(q)
    if not form:
        return {"error": "only SELECT and ASK queries are run; CONSTRUCT, DESCRIBE and updates are not"}
    n = max(1, min(int(rows or 50), MAX_ROWS))
    key = "sparql:" + q
    try:
        body = await _cache.remember(key, 300, lambda: get_json(SPARQL, {"query": q, "format": "json"}, {"Accept": "application/sparql-results+json"}))
    except ValueError as e:
        msg = str(e)
        if "rate limit" in msg:
            return {"error": "the Query Service is throttling this server (429); wait a minute and try once more. The quota is one client's, shared by everyone on this server.", "upstream": msg}
        return {"error": msg, "note": "A 400 is the Service's own message about the query's syntax; a 500 after a minute is the 60-second query limit."}
    if form == "ASK":
        return {"form": "ASK", "answer": body.get("boolean"), "link": SPARQL}
    vars_ = (body.get("head") or {}).get("vars") or []
    bindings = (body.get("results") or {}).get("bindings") or []
    rows_out = [{v: shorten(b[v]) for v in vars_ if v in b} for b in bindings[:n]]
    out = {"form": "SELECT", "variables": vars_, "returned": len(rows_out), "total_returned_by_service": len(bindings), "rows": rows_out, "truncated": len(bindings) > n,
           "link": f"https://query.wikidata.org/#{q}" if len(q) < 2000 else SPARQL}
    if not bindings:
        out["note"] = "No rows: the pattern matched nothing. Check the ids and properties against wikidata_entity before changing the question."
    return out


given(mcp, {"wikidata_entity": {"id": "wikidata_search"}})
SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
