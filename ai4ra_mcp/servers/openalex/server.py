"""openalex: OpenAlex, the open index of scholarly works, authors, institutions and funders.

Upstream: https://api.openalex.org/. No key; a mailto on every call puts us in the polite pool.
Ids are URLs (https://openalex.org/W...); 25 a page by default, 200 at most; dates are YYYY-MM-DD.
About one request a second is polite.
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import CONTACT, DAY, HOUR, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://api.openalex.org"
WORK_FIELDS = "id,doi,title,publication_year,publication_date,type,authorships,primary_location,open_access,awards,funders,cited_by_count,biblio"
_DOI = re.compile(r"10\.\d{4,9}/\S+")
_cache = TTLCache()

mcp = MCPServer(
    "openalex",
    instructions="OpenAlex: publications by author, institution, funder or award number; one work by DOI with its abstract; authors, institutions and funders by name. Read openalex_index first.",
)


async def _get(path: str, params: dict, ttl: float) -> dict:
    params = {**params, "mailto": CONTACT}
    key = path + "?" + repr(sorted(params.items()))
    body = await _cache.remember(key, ttl, lambda: get_json(f"{BASE}/{path}", params))
    return body if isinstance(body, dict) else {}


def _bare(v: str, letter: str) -> str:
    """An OpenAlex id in its short form: 'W123' from 'https://openalex.org/W123' or 'w123'."""
    v = (v or "").strip().rsplit("/", 1)[-1].upper()
    return v if re.fullmatch(rf"{letter}\d+", v) else ""


def _doi(v: str) -> str:
    v = (v or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:"):
        if v.lower().startswith(prefix):
            v = v[len(prefix):]
    return v if _DOI.fullmatch(v) else ""


def abstract_from_inverted_index(index: dict | None) -> str | None:
    """OpenAlex stores an abstract as {word: [positions]}; put the words back in order."""
    if not index:
        return None
    words = sorted((pos, word) for word, positions in index.items() for pos in positions)
    return " ".join(word for _, word in words)


def slim_work(w: dict) -> dict:
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    oa = w.get("open_access") or {}
    authorships = w.get("authorships") or []
    authors = [{"name": (a.get("author") or {}).get("display_name"), "id": (a.get("author") or {}).get("id"), "orcid": (a.get("author") or {}).get("orcid"),
                "institutions": [i.get("display_name") for i in a.get("institutions") or []]} for a in authorships[:10]]
    biblio = w.get("biblio") or {}
    return {
        "id": w.get("id"), "doi": w.get("doi"), "title": w.get("title"), "year": w.get("publication_year"), "date": w.get("publication_date"), "type": w.get("type"),
        "source": src.get("display_name"), "volume": biblio.get("volume"), "issue": biblio.get("issue"),
        "pages": "-".join(p for p in (biblio.get("first_page"), biblio.get("last_page")) if p) or None,
        "authors": authors, "author_count": len(authorships),
        "open_access": {"is_oa": oa.get("is_oa"), "status": oa.get("oa_status"), "oa_url": oa.get("oa_url")},
        "grants": [{"funder": g.get("funder_display_name"), "funder_id": g.get("funder_id"), "award_id": g.get("funder_award_id")} for g in w.get("awards") or []],
        "funders": [f.get("display_name") for f in w.get("funders") or []],
        "cited_by_count": w.get("cited_by_count"), "link": w.get("doi") or w.get("id"),
    }


def slim_author(a: dict) -> dict:
    return {"id": a.get("id"), "display_name": a.get("display_name"), "orcid": a.get("orcid"), "works_count": a.get("works_count"), "cited_by_count": a.get("cited_by_count"),
            "last_known_institutions": [{"name": i.get("display_name"), "id": i.get("id")} for i in a.get("last_known_institutions") or []],
            "topics": [t.get("display_name") for t in (a.get("topics") or [])[:3]], "link": a.get("id")}


def slim_institution(i: dict) -> dict:
    return {"id": i.get("id"), "display_name": i.get("display_name"), "ror": i.get("ror"), "country": i.get("country_code"), "type": i.get("type"),
            "works_count": i.get("works_count"), "homepage": i.get("homepage_url"), "link": i.get("id")}


def slim_funder(f: dict) -> dict:
    ids = f.get("ids") or {}
    return {"id": f.get("id"), "display_name": f.get("display_name"), "country": f.get("country_code"), "grants_count": f.get("awards_count"), "works_count": f.get("works_count"),
            "ids": {"ror": ids.get("ror"), "crossref": ids.get("crossref"), "doi": ids.get("doi")}, "link": f.get("id")}


def _page(body: dict, page: int, per_page: int, name: str, slim) -> dict:
    meta = body.get("meta") or {}
    items = [slim(r) for r in body.get("results") or []]
    out = {"page": page, "returned": len(items), "total": meta.get("count"), name: items}
    if isinstance(meta.get("count"), int) and page * per_page < meta["count"]:
        out["next_page"] = page + 1
    return out


@mcp.tool(name="openalex_index", annotations=_READ_ONLY)
async def openalex_index() -> dict:
    """How to use the OpenAlex tools. READ THIS FIRST: id forms, the award-number filter, what to cite."""
    return {
        "upstream": "https://api.openalex.org/, no key; a mailto on every call for the polite pool; about one request a second",
        "workflow": ["openalex_authors_search or openalex_institutions_search or openalex_funders_search to get an id",
                     "openalex_works_search by author, institution, funder, award number, years or words, newest first",
                     "openalex_work for one work by DOI or OpenAlex id, with its abstract"],
        "notes": ["Ids are URLs (https://openalex.org/W2741809807, A..., I..., F...); the tools accept the URL or the bare id.",
                  "award_id finds the publications an award produced; give the number as the funder writes it in its own records (NSF 1754803, NIH R01AI135270). A prefixed form such as DEB-1754803 is sent both ways.",
                  "Funders are Crossref Funder Registry entries; a funder's ids carry the registry id (crossref) and its 10.13039 DOI.",
                  "grants on a work are what the publisher deposited; a work with no grants may still acknowledge funding in its text.",
                  "authors lists the first ten; author_count is the full count. open_access.oa_url is a free copy when there is one.",
                  "Cite the DOI (https://doi.org/...); fall back to the OpenAlex id only when a work has none."],
    }


@mcp.tool(name="openalex_works_search", annotations=_READ_ONLY)
async def openalex_works_search(search: str = "", author_id: str = "", institution_id: str = "", funder_id: str = "", award_id: str = "",
                                from_year: str = "", to_year: str = "", type: str = "", page: int = 1, per_page: int = 25) -> dict:
    """Publications in OpenAlex, newest first: by author, institution, funder, award number, years or words.

    Give at least one of search, author_id, institution_id, funder_id or award_id. Use it for a biosketch's
    publication list, the papers an award produced, or an institution's output in a period.

    Args:
        search: Words in the title, abstract or full text, e.g. 'wildfire smoke'.
        author_id: OpenAlex author id, 'A5052350543' or its URL.
        institution_id: OpenAlex institution id ('I155093810') or a ROR URL ('https://ror.org/03hbp5t65').
        funder_id: OpenAlex funder id, 'F4320306076'.
        award_id: The funder's award number, e.g. '1754803'.
        from_year: Earliest publication year, e.g. '2020'.
        to_year: Latest publication year.
        type: Work type: article, book-chapter, dataset, preprint, dissertation, review. Empty for all.
        page: Page, 1-based. Default 1.
        per_page: Works a page, 1-50. Default 25.
    """
    filters = []
    if author_id.strip():
        aid = _bare(author_id, "A")
        if not aid:
            return {"error": "author_id must be an OpenAlex author id like A5052350543"}
        filters.append(f"authorships.author.id:{aid}")
    if institution_id.strip():
        inst = institution_id.strip()
        if "ror.org/" in inst:
            filters.append("authorships.institutions.ror:https://ror.org/" + inst.rsplit("/", 1)[-1])
        elif _bare(inst, "I"):
            filters.append(f"authorships.institutions.id:{_bare(inst, 'I')}")
        else:
            return {"error": "institution_id must be an OpenAlex institution id like I155093810 or a ROR URL"}
    if funder_id.strip():
        fid = _bare(funder_id, "F")
        if not fid:
            return {"error": "funder_id must be an OpenAlex funder id like F4320306076"}
        filters.append(f"funders.id:{fid}")
    if award_id.strip():
        num = award_id.strip()
        # OpenAlex keeps the number the funder uses; NSF drops the program prefix, so DEB-1754803 is tried both ways.
        m = re.fullmatch(r"[A-Za-z]+-(\d+)", num)
        filters.append("awards.funder_award_id:" + (f"{num}|{m.group(1)}" if m else num))
    if from_year.strip():
        if not from_year.strip().isdigit():
            return {"error": "from_year must be a year"}
        filters.append(f"from_publication_date:{from_year.strip()}-01-01")
    if to_year.strip():
        if not to_year.strip().isdigit():
            return {"error": "to_year must be a year"}
        filters.append(f"to_publication_date:{to_year.strip()}-12-31")
    if type.strip():
        filters.append(f"type:{type.strip().lower()}")
    if not search.strip() and not any(f.split(":")[0] in ("authorships.author.id", "authorships.institutions.ror", "authorships.institutions.id", "funders.id", "awards.funder_award_id") for f in filters):
        return {"error": "give at least one of search, author_id, institution_id, funder_id or award_id"}
    page = max(1, int(page or 1))
    per_page = max(1, min(int(per_page or 25), 50))
    params: dict = {"sort": "publication_date:desc", "select": WORK_FIELDS, "page": page, "per_page": per_page}
    if search.strip():
        params["search"] = search.strip()
    if filters:
        params["filter"] = ",".join(filters)
    try:
        body = await _get("works", params, HOUR)
    except ValueError as e:
        return {"error": str(e)}
    return _page(body, page, per_page, "works", slim_work)


@mcp.tool(name="openalex_work", annotations=_READ_ONLY)
async def openalex_work(id: str) -> dict:
    """One work by DOI or OpenAlex id, with its abstract, authors, grants and reference count.

    Args:
        id: A DOI ('10.1371/journal.pone.0266781', with or without https://doi.org/ or doi:) or an OpenAlex id ('W4224016882' or its URL).
    """
    wid, doi = _bare(id, "W"), _doi(id)
    if not wid and not doi:
        return {"error": "id must be a DOI or an OpenAlex work id like W4224016882"}
    path = f"works/{wid}" if wid else f"works/doi:{doi}"
    try:
        w = await _get(path, {"select": WORK_FIELDS + ",abstract_inverted_index,referenced_works_count"}, DAY)
    except ValueError as e:
        return {"error": str(e)}
    if not w.get("id"):
        return {"error": f"no work {id.strip()} in OpenAlex"}
    return {**slim_work(w), "abstract": abstract_from_inverted_index(w.get("abstract_inverted_index")), "referenced_works_count": w.get("referenced_works_count")}


@mcp.tool(name="openalex_authors_search", annotations=_READ_ONLY)
async def openalex_authors_search(query: str, institution_id: str = "", page: int = 1) -> dict:
    """Authors by name, with ORCID, counts, last known institutions and top topics. The id is what openalex_works_search takes.

    Args:
        query: The author's name, e.g. 'Luke Sheneman'.
        institution_id: Narrow to an institution: an OpenAlex id ('I155093810', last known institution) or a ROR URL (any affiliation).
        page: Page, 1-based, 25 a page. Default 1.
    """
    if not query.strip():
        return {"error": "query is required"}
    page = max(1, int(page or 1))
    params: dict = {"search": query.strip(), "page": page, "per_page": 25}
    if institution_id.strip():
        inst = institution_id.strip()
        if "ror.org/" in inst:
            params["filter"] = "affiliations.institution.ror:https://ror.org/" + inst.rsplit("/", 1)[-1]
        elif _bare(inst, "I"):
            params["filter"] = f"last_known_institutions.id:{_bare(inst, 'I')}"
        else:
            return {"error": "institution_id must be an OpenAlex institution id like I155093810 or a ROR URL"}
    try:
        body = await _get("authors", params, HOUR)
    except ValueError as e:
        return {"error": str(e)}
    return _page(body, page, 25, "authors", slim_author)


@mcp.tool(name="openalex_institutions_search", annotations=_READ_ONLY)
async def openalex_institutions_search(query: str) -> dict:
    """Institutions by name, with ROR, country, type and works count. The id or ROR is what the other tools take.

    Args:
        query: The institution's name, e.g. 'University of Idaho'.
    """
    if not query.strip():
        return {"error": "query is required"}
    try:
        body = await _get("institutions", {"search": query.strip(), "per_page": 10}, HOUR)
    except ValueError as e:
        return {"error": str(e)}
    return _page(body, 1, 10, "institutions", slim_institution)


@mcp.tool(name="openalex_funders_search", annotations=_READ_ONLY)
async def openalex_funders_search(query: str) -> dict:
    """Funders by name, with the Crossref Funder Registry id and DOI, ROR and counts. The id is what openalex_works_search takes.

    Args:
        query: The funder's name, e.g. 'National Science Foundation'.
    """
    if not query.strip():
        return {"error": "query is required"}
    try:
        body = await _get("funders", {"search": query.strip(), "per_page": 10}, HOUR)
    except ValueError as e:
        return {"error": str(e)}
    return _page(body, 1, 10, "funders", slim_funder)


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
