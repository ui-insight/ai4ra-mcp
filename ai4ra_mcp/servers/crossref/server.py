"""crossref: the Crossref REST API, the DOI registry's record of works and the Funder Registry.

Upstream: https://api.crossref.org/. No key; a mailto on every call puts us in the polite pool.
20 rows a page by default, 1,000 at most; the offset cannot pass 10,000. Dates are date-parts
arrays ([[2022, 4, 18]]); titles are arrays.
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import CONTACT, DAY, HOUR, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://api.crossref.org"
WORK_FIELDS = "DOI,title,author,container-title,published,type,funder,publisher,volume,issue,page,is-referenced-by-count,URL"
_DOI = re.compile(r"10\.\d{4,9}/\S+")
_TAG = re.compile(r"<[^>]+>")
_cache = TTLCache()

mcp = MCPServer(
    "crossref",
    instructions="Crossref: publications by words, author or funder with their funding acknowledgments; one work by DOI with its abstract; funders in the Funder Registry by name. Read crossref_index first.",
)


async def _get(path: str, params: dict, ttl: float) -> dict:
    params = {**params, "mailto": CONTACT}
    key = path + "?" + repr(sorted(params.items()))
    body = await _cache.remember(key, ttl, lambda: get_json(f"{BASE}/{path}", params))
    return (body.get("message") or {}) if isinstance(body, dict) else {}


def _doi(v: str) -> str:
    v = (v or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:"):
        if v.lower().startswith(prefix):
            v = v[len(prefix):]
    return v if _DOI.fullmatch(v) else ""


def _first(v) -> str | None:
    return v[0] if isinstance(v, list) and v else (v if isinstance(v, str) else None)


def _year(w: dict) -> int | None:
    for k in ("published", "issued", "published-print", "published-online"):
        parts = (w.get(k) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            return parts[0][0]
    return None


def _author(a: dict) -> dict:
    out = {"given": a.get("given"), "family": a.get("family") or a.get("name"), "sequence": a.get("sequence")}
    if a.get("ORCID"):
        out["orcid"] = a["ORCID"]
    affs = [x.get("name") for x in a.get("affiliation") or [] if x.get("name")]
    if affs:
        out["affiliations"] = affs
    return out


def slim_work(w: dict) -> dict:
    doi = w.get("DOI")
    authors = w.get("author") or []
    return {
        "doi": doi, "title": _first(w.get("title")), "authors": [_author(a) for a in authors[:25]], "author_count": len(authors),
        "container": _first(w.get("container-title")), "year": _year(w), "type": w.get("type"), "publisher": w.get("publisher"),
        "volume": w.get("volume"), "issue": w.get("issue"), "page": w.get("page"),
        "funders": [{"name": f.get("name"), "doi": f.get("DOI"), "awards": f.get("award") or []} for f in w.get("funder") or []],
        "cited_by": w.get("is-referenced-by-count"), "link": f"https://doi.org/{doi}" if doi else w.get("URL"),
    }


def slim_funder(f: dict) -> dict:
    fid = f.get("id")
    return {"id": fid, "name": f.get("name"), "alt_names": (f.get("alt-names") or [])[:5], "location": f.get("location"), "uri": f.get("uri"),
            "link": f"https://doi.org/10.13039/{fid}" if fid else None}


@mcp.tool(name="crossref_index", annotations=_READ_ONLY)
async def crossref_index() -> dict:
    """How to use the Crossref tools. READ THIS FIRST: what a DOI lookup gives, the funder id, what to cite."""
    return {
        "upstream": "https://api.crossref.org/, no key; a mailto on every call for the polite pool",
        "workflow": ["crossref_works_search by words, author name or funder id, with years and type; each work carries the funders and award numbers the publisher deposited",
                     "crossref_work for one DOI: the record with abstract, license and reference count; exact and free",
                     "crossref_funders_search for a funder's Funder Registry id, which OpenAlex and ROR share and which crossref_works_search filters on"],
        "notes": ["A work's funders are what the publisher deposited from the acknowledgment; absent funders means none deposited, not none acknowledged.",
                  "A funder's DOI is 10.13039/ followed by its registry id; funder_id here is the registry id (NSF 100000001, NIH 100000002).",
                  "year comes from the published date; Crossref keeps dates as date-parts and titles as lists, which the tools flatten.",
                  "Author matching is by words in the name; an initial or a common surname matches widely, so check the affiliation and ORCID.",
                  "Cite the DOI as https://doi.org/..."],
    }


@mcp.tool(name="crossref_works_search", annotations=_READ_ONLY)
async def crossref_works_search(query: str = "", author: str = "", funder_id: str = "", from_year: str = "", to_year: str = "", type: str = "",
                                rows: int = 20, offset: int = 0) -> dict:
    """Works in Crossref by words, author or funder, most relevant first, with the funders and award numbers deposited on each.

    Give at least one of query, author or funder_id. Use it for the publications a funder supported, or an author's
    papers with their funding acknowledgments.

    Args:
        query: Words in the title, abstract or references, e.g. 'wildfire smoke exposure'.
        author: Author name, e.g. 'Luke Sheneman'.
        funder_id: Funder Registry id, e.g. '100000001' for NSF (from crossref_funders_search).
        from_year: Earliest publication year, e.g. '2020'.
        to_year: Latest publication year.
        type: Work type: journal-article, book-chapter, proceedings-article, dataset, posted-content (preprints). Empty for all.
        rows: Works to return, 1-50. Default 20.
        offset: Record to start from, at most 10,000. Default 0.
    """
    params: dict = {"select": WORK_FIELDS, "rows": max(1, min(int(rows or 20), 50)), "offset": max(0, min(int(offset or 0), 10000))}
    if query.strip():
        params["query"] = query.strip()
    if author.strip():
        params["query.author"] = author.strip()
    filters = []
    if funder_id.strip():
        fid = funder_id.strip().rsplit("/", 1)[-1]
        if not fid.isdigit():
            return {"error": "funder_id must be a Funder Registry id like 100000001"}
        filters.append(f"funder:{fid}")
    for name, v in (("from-pub-date", from_year), ("until-pub-date", to_year)):
        if v.strip():
            if not v.strip().isdigit():
                return {"error": f"{name.split('-')[0]}_year must be a year"}
            filters.append(f"{name}:{v.strip()}")
    if type.strip():
        filters.append(f"type:{type.strip().lower()}")
    if filters:
        params["filter"] = ",".join(filters)
    if not any(k in params for k in ("query", "query.author")) and not funder_id.strip():
        return {"error": "give at least one of query, author or funder_id"}
    try:
        msg = await _get("works", params, HOUR)
    except ValueError as e:
        return {"error": str(e)}
    works = [slim_work(w) for w in msg.get("items") or []]
    total = msg.get("total-results")
    out = {"offset": params["offset"], "returned": len(works), "total": total, "works": works}
    if isinstance(total, int) and params["offset"] + len(works) < total and len(works) == params["rows"]:
        out["next_offset"] = params["offset"] + len(works)
    return out


@mcp.tool(name="crossref_work", annotations=_READ_ONLY)
async def crossref_work(doi: str) -> dict:
    """One work by DOI: the deposited record with abstract, funders, license and reference count.

    Args:
        doi: The DOI, e.g. '10.1371/journal.pone.0266781', with or without https://doi.org/.
    """
    d = _doi(doi)
    if not d:
        return {"error": "doi must look like 10.xxxx/..."}
    try:
        w = await _get(f"works/{d}", {}, DAY)
    except ValueError as e:
        return {"error": str(e)}
    if not w.get("DOI"):
        return {"error": f"no work with DOI {d} in Crossref"}
    abstract = w.get("abstract")
    return {**slim_work(w), "abstract": re.sub(r"\s+", " ", _TAG.sub(" ", abstract)).strip() if abstract else None,
            "licenses": [x.get("URL") for x in w.get("license") or [] if x.get("URL")], "references_count": w.get("references-count"),
            "issn": w.get("ISSN") or []}


@mcp.tool(name="crossref_funders_search", annotations=_READ_ONLY)
async def crossref_funders_search(query: str, rows: int = 20) -> dict:
    """Funders in the Crossref Funder Registry by name, with the registry id that Crossref, OpenAlex and ROR share.

    Args:
        query: The funder's name, e.g. 'National Science Foundation'.
        rows: Funders to return, 1-50. Default 20.
    """
    if not query.strip():
        return {"error": "query is required"}
    params = {"query": query.strip(), "rows": max(1, min(int(rows or 20), 50))}
    try:
        msg = await _get("funders", params, DAY)
    except ValueError as e:
        return {"error": str(e)}
    funders = [slim_funder(f) for f in msg.get("items") or []]
    return {"returned": len(funders), "total": msg.get("total-results"), "funders": funders,
            "note": "id is the Funder Registry id; its DOI is 10.13039/<id>. Pass the id to crossref_works_search as funder_id."}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
