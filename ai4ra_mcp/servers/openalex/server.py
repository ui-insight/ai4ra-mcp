"""openalex: OpenAlex, the open index of scholarly works, authors, institutions and funders.

Upstream: https://api.openalex.org/. Since February 2026 OpenAlex meters the API by a daily budget: a call with
no key shares $0.10 a day with everyone on the caller's network address; a free key of the person's own
(https://openalex.org/settings/api) has its own $1 a day, enough for a few thousand searches. The key is
optional here, the person's own as a bearer token or AI4RA_MCP_OPENALEX_KEY, sent as api_key; a mailto rides
on every call as the contact OpenAlex asks for. Ids are URLs (https://openalex.org/W...); 25 a page by
default, 200 at most; dates are YYYY-MM-DD.
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import CONTACT, DAY, HOUR, TTLCache, api_key, get_json
from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://api.openalex.org"
KEY_ENV = "AI4RA_MCP_OPENALEX_KEY"
KEY_HOW = "Optional: a free OpenAlex key from https://openalex.org/settings/api has its own $1 a day of OpenAlex's usage budget; without one every caller on this server's network shares $0.10 a day."
WORK_FIELDS = "id,doi,title,publication_year,publication_date,type,authorships,primary_location,open_access,awards,funders,cited_by_count,biblio"
# What works can be counted by, as a person says it and as OpenAlex's group_by names it.
GROUPS = {"year": "publication_year", "type": "type", "funder": "funders.id", "award": "awards.funder_award_id", "institution": "authorships.institutions.id",
          "country": "authorships.institutions.country_code", "oa_status": "open_access.oa_status", "topic": "primary_topic.id", "field": "primary_topic.field.id",
          "source": "primary_location.source.id"}
_DOI = re.compile(r"10\.\d{4,9}/\S+")
_cache = TTLCache()

mcp = MCPServer(
    "openalex",
    instructions="OpenAlex: publications by author, institution, funder or award number; one work by DOI with its abstract; works counted by year, funder, institution or topic; what cites a work and what it cites; authors, institutions and funders by name. Read openalex_index first.",
)


async def _get(path: str, params: dict, ttl: float) -> dict:
    """One call, cached by path and parameters. The key is added after the cache key is made, so no key is in the cache or its keys."""
    key = path + "?" + repr(sorted(params.items()))
    params = {**params, "mailto": CONTACT}
    sent = api_key(KEY_ENV)
    if sent:
        params["api_key"] = sent
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


def _work_filters(search: str, author_id: str, institution_id: str, funder_id: str, award_id: str, from_year: str, to_year: str, type: str) -> tuple[list[str], dict | None]:
    """The filter clauses a works call sends for these arguments, or the error that stops it. At least one of search,
    author, institution, funder or award must be given, since years and type alone are the whole index."""
    filters: list[str] = []
    if author_id.strip():
        aid = _bare(author_id, "A")
        if not aid:
            return [], {"error": "author_id must be an OpenAlex author id like A5052350543"}
        filters.append(f"authorships.author.id:{aid}")
    if institution_id.strip():
        inst = institution_id.strip()
        if "ror.org/" in inst:
            filters.append("authorships.institutions.ror:https://ror.org/" + inst.rsplit("/", 1)[-1])
        elif _bare(inst, "I"):
            filters.append(f"authorships.institutions.id:{_bare(inst, 'I')}")
        else:
            return [], {"error": "institution_id must be an OpenAlex institution id like I155093810 or a ROR URL"}
    if funder_id.strip():
        fid = _bare(funder_id, "F")
        if not fid:
            return [], {"error": "funder_id must be an OpenAlex funder id like F4320306076"}
        filters.append(f"funders.id:{fid}")
    if award_id.strip():
        num = award_id.strip()
        # OpenAlex keeps the number the funder uses; NSF drops the program prefix, so DEB-1754803 is tried both ways.
        m = re.fullmatch(r"[A-Za-z]+-(\d+)", num)
        filters.append("awards.funder_award_id:" + (f"{num}|{m.group(1)}" if m else num))
    if from_year.strip():
        if not from_year.strip().isdigit():
            return [], {"error": "from_year must be a year"}
        filters.append(f"from_publication_date:{from_year.strip()}-01-01")
    if to_year.strip():
        if not to_year.strip().isdigit():
            return [], {"error": "to_year must be a year"}
        filters.append(f"to_publication_date:{to_year.strip()}-12-31")
    if type.strip():
        filters.append(f"type:{type.strip().lower()}")
    if not search.strip() and not any(f.split(":")[0] in ("authorships.author.id", "authorships.institutions.ror", "authorships.institutions.id", "funders.id", "awards.funder_award_id") for f in filters):
        return [], {"error": "give at least one of search, author_id, institution_id, funder_id or award_id"}
    return filters, None


async def _work_id(id: str) -> tuple[str, dict | None]:
    """The W id for a DOI or an OpenAlex id, one cached lookup for a DOI; or the error."""
    wid, doi = _bare(id, "W"), _doi(id)
    if wid:
        return wid, None
    if not doi:
        return "", {"error": "id must be a DOI or an OpenAlex work id like W4224016882"}
    try:
        w = await _get(f"works/doi:{doi}", {"select": "id"}, DAY)
    except ValueError as e:
        return "", {"error": str(e)}
    wid = _bare(w.get("id") or "", "W")
    return wid, (None if wid else {"error": f"no work {id.strip()} in OpenAlex"})


@mcp.tool(name="openalex_index", annotations=_READ_ONLY)
async def openalex_index() -> dict:
    """How to use the OpenAlex tools. READ THIS FIRST: id forms, the award-number filter, the usage budget, what to cite."""
    return {
        "upstream": "https://api.openalex.org/; metered by a daily budget rather than a rate: a call with no key shares $0.10 a day with everyone on this server's network address, a free key has its own $1 a day; a mailto on every call",
        "key": {"required": False, "on_this_request": api_key(KEY_ENV) is not None,
                "per_user": "an OpenAlex key sent as a bearer token is used for this request and spends that person's own daily budget; without one the call spends the budget everyone without a key shares", "how": KEY_HOW},
        "workflow": ["openalex_authors_search or openalex_institutions_search or openalex_funders_search to get an id",
                     "openalex_works_search by author, institution, funder, award number, years or words, newest first",
                     "openalex_works_group for the same works counted by year, type, funder, award, institution, country, open-access status, topic, field or journal, one call in place of paging",
                     "openalex_work for one work by DOI or OpenAlex id, with its abstract",
                     "openalex_citations for the works that cite a work (cited_by) or the works it cites (references)"],
        "notes": ["Ids are URLs (https://openalex.org/W2741809807, A..., I..., F...); the tools accept the URL or the bare id.",
                  "award_id finds the publications an award produced; give the number as the funder writes it in its own records (NSF 1754803, NIH R01AI135270). A prefixed form such as DEB-1754803 is sent both ways.",
                  "Funders are Crossref Funder Registry entries; a funder's ids carry the registry id (crossref) and its 10.13039 DOI.",
                  "grants on a work are what the publisher deposited; a work with no grants may still acknowledge funding in its text. A count by funder or award counts only deposited acknowledgments.",
                  "authors lists the first ten; author_count is the full count. open_access.oa_url is a free copy when there is one.",
                  "A list call costs OpenAlex $0.0001 and a text search $0.001 of the budget; one record by id costs nothing. A 429 means the day's budget is spent; it resets at midnight UTC.",
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
    filters, err = _work_filters(search, author_id, institution_id, funder_id, award_id, from_year, to_year, type)
    if err:
        return err
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


@mcp.tool(name="openalex_works_group", annotations=_READ_ONLY)
async def openalex_works_group(group_by: str, search: str = "", author_id: str = "", institution_id: str = "", funder_id: str = "", award_id: str = "",
                               from_year: str = "", to_year: str = "", type: str = "") -> dict:
    """The works openalex_works_search would list, counted by one dimension in one call: how many a year, by funder, by institution, by topic.

    Same filters as openalex_works_search, at least one of search, author_id, institution_id, funder_id or award_id. Use it for
    "how many University of Idaho papers acknowledged NSF each year", "which funders appear on an author's papers", "what share is
    open access". Counts are of deposited metadata: a paper whose publisher deposited no funder is counted under none.

    Args:
        group_by: year, type, funder, award, institution, country, oa_status, topic, field or source (the journal).
        search: Words in the title, abstract or full text.
        author_id: OpenAlex author id, 'A5052350543' or its URL.
        institution_id: OpenAlex institution id ('I155093810') or a ROR URL ('https://ror.org/03hbp5t65').
        funder_id: OpenAlex funder id, 'F4320306076'.
        award_id: The funder's award number, e.g. '1754803'.
        from_year: Earliest publication year, e.g. '2020'.
        to_year: Latest publication year.
        type: Work type: article, book-chapter, dataset, preprint, dissertation, review. Empty for all.
    """
    dim = group_by.strip().lower()
    if dim not in GROUPS:
        return {"error": f"group_by must be one of {', '.join(GROUPS)}"}
    filters, err = _work_filters(search, author_id, institution_id, funder_id, award_id, from_year, to_year, type)
    if err:
        return err
    params: dict = {"group_by": GROUPS[dim], "per_page": 200}
    if search.strip():
        params["search"] = search.strip()
    if filters:
        params["filter"] = ",".join(filters)
    try:
        body = await _get("works", params, HOUR)
    except ValueError as e:
        return {"error": str(e)}
    meta = body.get("meta") or {}
    groups = [{"key": g.get("key"), "name": g.get("key_display_name"), "count": g.get("count")} for g in body.get("group_by") or []]
    if dim == "year":
        groups.sort(key=lambda g: str(g["key"]), reverse=True)
    return {"group_by": dim, "total": meta.get("count"), "groups_count": meta.get("groups_count", len(groups)), "groups": groups,
            "note": "total is the works matched; a work with two funders or two institutions is counted under each, so counts can sum past it. At most 200 groups are returned."}


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


@mcp.tool(name="openalex_citations", annotations=_READ_ONLY)
async def openalex_citations(id: str, direction: str = "cited_by", page: int = 1, per_page: int = 25) -> dict:
    """The works that cite a work (cited_by, newest first) or the works it cites (references), each as openalex_works_search lists them.

    Use it to see who built on a paper, to check what a manuscript under review cites, or to follow a finding back to its sources.

    Args:
        id: A DOI or an OpenAlex work id ('W2741809807' or its URL).
        direction: 'cited_by' for works citing this one (default), 'references' for the works this one cites.
        page: Page, 1-based. Default 1.
        per_page: Works a page, 1-50. Default 25.
    """
    which = direction.strip().lower()
    if which not in ("cited_by", "references"):
        return {"error": "direction must be cited_by or references"}
    wid, err = await _work_id(id)
    if err:
        return err
    page = max(1, int(page or 1))
    per_page = max(1, min(int(per_page or 25), 50))
    try:
        if which == "cited_by":
            body = await _get("works", {"filter": f"cites:{wid}", "sort": "publication_date:desc", "select": WORK_FIELDS, "page": page, "per_page": per_page}, HOUR)
            out = _page(body, page, per_page, "works", slim_work)
        else:
            w = await _get(f"works/{wid}", {"select": "id,referenced_works"}, DAY)
            refs = [_bare(r, "W") for r in w.get("referenced_works") or []]
            chunk = refs[(page - 1) * per_page: page * per_page]
            works = []
            if chunk:
                body = await _get("works", {"filter": "openalex_id:" + "|".join(chunk), "select": WORK_FIELDS, "per_page": len(chunk)}, DAY)
                works = [slim_work(r) for r in body.get("results") or []]
            out = {"page": page, "returned": len(works), "total": len(refs), "works": works}
            if page * per_page < len(refs):
                out["next_page"] = page + 1
    except ValueError as e:
        return {"error": str(e)}
    return {"work": f"https://openalex.org/{wid}", "direction": which, **out}


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
# The OpenAlex ids a call names and the tool that lists them (#40): authors, institutions and funders from their
# searches, a work from openalex_works_search; a DOI or id a person pastes passes as given.
_IDS = {"author_id": "openalex_authors_search", "institution_id": "openalex_institutions_search", "funder_id": "openalex_funders_search"}
given(mcp, {"openalex_works_search": _IDS, "openalex_works_group": _IDS,
            "openalex_work": {"id": "openalex_works_search"}, "openalex_citations": {"id": "openalex_works_search"},
            "openalex_authors_search": {"institution_id": "openalex_institutions_search"}})
