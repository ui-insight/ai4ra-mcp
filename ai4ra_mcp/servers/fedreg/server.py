"""fedreg: the Federal Register, the daily journal where rules, proposed rules and notices are published.

Upstream: https://www.federalregister.gov/api/v1/ (documents.json, documents/{number}.json, agencies.json).
No key. Dates are YYYY-MM-DD both ways; 20 a page by default, at most 1,000; repeated query keys
(conditions[type][], fields[]) are sent as a list of pairs.
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://www.federalregister.gov/api/v1"
TYPES = {"RULE": "Rule", "PRORULE": "Proposed Rule", "NOTICE": "Notice", "PRESDOCU": "Presidential Document"}
# Only what the slim needs: the API returns everything when fields[] is absent, and an abstract per row is plenty.
LIST_FIELDS = ["title", "document_number", "type", "subtype", "publication_date", "agencies", "abstract", "html_url", "pdf_url",
               "comments_close_on", "effective_on", "docket_ids", "regulation_id_numbers", "cfr_references", "action"]
_cache = TTLCache()

mcp = MCPServer(
    "fedreg",
    instructions="The Federal Register: rules, proposed rules and notices by words, agency, CFR part or date; one document by number with its dates and links; agency slugs. Read federal_register_index first.",
)


def _cfr(refs: list | None) -> list[str]:
    return [f"{r.get('title')} CFR {r.get('part')}" for r in refs or [] if r.get("title")]


def _slim(d: dict) -> dict:
    return {
        "document_number": d.get("document_number"), "title": d.get("title"), "type": d.get("type"), "subtype": d.get("subtype"), "action": d.get("action"),
        "publication_date": d.get("publication_date"), "effective_on": d.get("effective_on"), "comments_close_on": d.get("comments_close_on"),
        "agencies": [{"name": a.get("name"), "slug": a.get("slug")} for a in d.get("agencies") or [] if isinstance(a, dict)],
        "abstract": d.get("abstract"), "cfr_references": _cfr(d.get("cfr_references")),
        "docket_ids": d.get("docket_ids") or [], "rins": d.get("regulation_id_numbers") or [],
        "link": d.get("html_url"), "pdf_url": d.get("pdf_url"),
    }


def _slim_document(d: dict) -> dict:
    reg = d.get("regulations_dot_gov_info") or {}
    return {
        **_slim(d), "citation": d.get("citation"), "dates": d.get("dates"), "significant": d.get("significant"), "page_count": d.get("page_length"),
        "body_html_url": d.get("body_html_url"), "full_text_xml_url": d.get("full_text_xml_url"), "raw_text_url": d.get("raw_text_url"),
        "regulations_gov": {"docket_id": reg.get("docket_id"), "document_id": reg.get("document_id"), "comments_count": reg.get("comments_count"),
                            "comment_url": d.get("comment_url")} if reg or d.get("comment_url") else None,
        "topics": d.get("topics") or [],
    }


def _slim_agency(a: dict) -> dict:
    return {"slug": a.get("slug"), "name": a.get("name"), "short_name": a.get("short_name"), "url": a.get("url"), "parent_id": a.get("parent_id")}


def _csv(v: str) -> list[str]:
    return [s.strip() for s in re.split(r"[|,]", v or "") if s.strip()]


@mcp.tool(name="federal_register_index", annotations=_READ_ONLY)
async def federal_register_index() -> dict:
    """How to use the Federal Register tools. READ THIS FIRST: document types, what appears here, the deadline field, what to cite."""
    return {
        "upstream": "https://www.federalregister.gov/api/v1/, no key",
        "workflow": ["federal_register_agencies to find an agency's slug when a search should be limited to one agency",
                     "federal_register_search by words, type, agency, CFR title and part, or publication dates, newest first",
                     "federal_register_document for one document by number, with its dates, CFR parts, links and the regulations.gov docket",
                     "fetch_document on the general server reads the document's link (html_url) when the text itself is needed"],
        "notes": ["A Rule (RULE) is a final regulation with an effective date; a Proposed Rule (PRORULE) asks for comments before a rule is made; a Notice (NOTICE) is anything else an agency publishes: funding opportunities, information collections, meetings, policy statements.",
                  "Changes to 2 CFR 200 (the Uniform Guidance) are OMB rules here (cfr_title 2, cfr_part 200; agency slug management-and-budget-office); agency notices of funding opportunity are Notices whose action reads 'Notice of funding opportunity'.",
                  "comments_close_on is the comment deadline for a proposed rule, or the application deadline some notices carry; effective_on is when a rule takes effect.",
                  "Agency slugs are the Federal Register's own (management-and-budget-office, national-science-foundation, health-and-human-services-department); an unknown slug is a 400. Look them up with federal_register_agencies.",
                  "Dates are YYYY-MM-DD. document_number (2024-07496) is the id everywhere; citation (89 FR 30046) is the page cite.",
                  "Cite the link (html_url) and the publication date. The body is not returned; read it with fetch_document on the general server."],
    }


@mcp.tool(name="federal_register_search", annotations=_READ_ONLY)
async def federal_register_search(
    term: str = "",
    document_types: str = "",
    agencies: str = "",
    cfr_title: str = "",
    cfr_part: str = "",
    date_from: str = "",
    date_to: str = "",
    significant: str = "",
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Search Federal Register documents, newest first.

    Give at least one of term, agencies, cfr_title or date_from. Returns each document with its number, type, action,
    dates, agencies, abstract, CFR parts, docket ids, RINs and a link.

    Args:
        term: Words in the document, e.g. 'uniform guidance' or '"notice of funding opportunity"' (quotes for a phrase).
        document_types: Comma-separated codes: RULE, PRORULE, NOTICE, PRESDOCU. Empty for all.
        agencies: Comma-separated Federal Register agency slugs, e.g. 'management-and-budget-office'; from federal_register_agencies.
        cfr_title: CFR title the document affects, e.g. '2'.
        cfr_part: CFR part within that title, e.g. '200'. Needs cfr_title.
        date_from: Published on or after YYYY-MM-DD.
        date_to: Published on or before YYYY-MM-DD.
        significant: '1' for documents deemed significant under EO 12866, '0' for the rest, empty for all.
        page: Page number, 1-based. Default 1.
        per_page: Documents a page, 1-50. Default 20.
    """
    per_page = max(1, min(int(per_page or 20), 50))
    page = max(1, int(page or 1))
    params: list[tuple[str, str]] = [("order", "newest"), ("per_page", str(per_page)), ("page", str(page))]
    params += [("fields[]", f) for f in LIST_FIELDS]
    if term.strip():
        params.append(("conditions[term]", term.strip()))
    types = [t.upper() for t in _csv(document_types)]
    if any(t not in TYPES for t in types):
        return {"error": "document_types must be from RULE, PRORULE, NOTICE, PRESDOCU"}
    params += [("conditions[type][]", t) for t in types]
    params += [("conditions[agencies][]", a.lower()) for a in _csv(agencies)]
    if cfr_part.strip() and not cfr_title.strip():
        return {"error": "cfr_part needs cfr_title"}
    if cfr_title.strip():
        if not cfr_title.strip().isdigit():
            return {"error": "cfr_title must be a number, e.g. '2'"}
        params.append(("conditions[cfr][title]", cfr_title.strip()))
        if cfr_part.strip():
            params.append(("conditions[cfr][part]", cfr_part.strip()))
    for name, v in (("gte", date_from), ("lte", date_to)):
        if v.strip():
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()):
                return {"error": "dates are YYYY-MM-DD"}
            params.append((f"conditions[publication_date][{name}]", v.strip()))
    if significant.strip():
        if significant.strip() not in ("0", "1"):
            return {"error": "significant is '1', '0' or empty"}
        params.append(("conditions[significant]", significant.strip()))
    if not any(k in ("conditions[term]", "conditions[agencies][]", "conditions[cfr][title]", "conditions[publication_date][gte]") for k, _ in params):
        return {"error": "give at least one of term, agencies, cfr_title or date_from"}
    try:
        body = await _cache.remember("search:" + repr(params), HOUR, lambda: get_json(f"{BASE}/documents.json", params))
    except ValueError as e:
        return {"error": str(e)}
    docs = [_slim(d) for d in body.get("results") or []]
    out = {"page": page, "returned": len(docs), "total": body.get("count"), "total_pages": body.get("total_pages"), "documents": docs}
    if body.get("next_page_url"):
        out["next_page"] = page + 1
    return out


@mcp.tool(name="federal_register_document", annotations=_READ_ONLY)
async def federal_register_document(document_number: str) -> dict:
    """One Federal Register document by number: its dates, agencies, abstract, CFR parts, docket and RINs, page count,
    the regulations.gov docket it is filed under, and links to the page, the PDF and the full text. Not the body.

    Args:
        document_number: The document number, e.g. '2024-07496'.
    """
    num = (document_number or "").strip()
    if not re.fullmatch(r"[\w-]+", num) or not num[0].isdigit():
        return {"error": "document_number looks like '2024-07496'"}
    try:
        body = await _cache.remember(f"document:{num}", DAY, lambda: get_json(f"{BASE}/documents/{num}.json"))
    except ValueError as e:
        return {"error": str(e)}
    if not isinstance(body, dict) or not body.get("document_number"):
        return {"error": f"no Federal Register document {num}", "document_number": num}
    return {**_slim_document(body), "note": "The body is not returned; fetch_document on the general server reads the link."}


@mcp.tool(name="federal_register_agencies", annotations=_READ_ONLY)
async def federal_register_agencies(query: str = "") -> dict:
    """Federal Register agencies with the slug a search needs. Give a word of the name to narrow.

    Args:
        query: A word of the agency's name or its short name, e.g. 'budget' or 'NSF'. Empty for the whole list.
    """
    try:
        rows = await _cache.remember("agencies", DAY, lambda: get_json(f"{BASE}/agencies.json"))
    except ValueError as e:
        return {"error": str(e)}
    q = query.strip().lower()
    agencies = [_slim_agency(a) for a in rows or [] if isinstance(a, dict)]
    if q:
        agencies = [a for a in agencies if q in (a["name"] or "").lower() or q == (a["short_name"] or "").lower() or q in (a["slug"] or "")]
    return {"query": query.strip(), "returned": len(agencies), "agencies": agencies}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
