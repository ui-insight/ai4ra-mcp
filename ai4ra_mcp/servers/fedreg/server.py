"""fedreg: the Federal Register, the daily journal where rules, proposed rules, notices and executive orders are published.

Upstream: https://www.federalregister.gov/api/v1/ (documents.json, documents/{number}.json, agencies.json).
No key. Dates are YYYY-MM-DD both ways; 20 a page by default, at most 1,000; repeated query keys
(conditions[type][], fields[]) are sent as a list of pairs. Presidential documents (PRESDOCU) carry their kind, the
executive order number, the signer, the signing date and the Office of the Federal Register's disposition line; the API
has no condition on the order number, so one order is found by a full-text search for its number with the kind set to
executive_order and the result's executive_order_number compared to what was asked (verified live 2026-10-14, #39).
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_json
from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://www.federalregister.gov/api/v1"
TYPES = {"RULE": "Rule", "PRORULE": "Proposed Rule", "NOTICE": "Notice", "PRESDOCU": "Presidential Document"}
# Only what the slim needs: the API returns everything when fields[] is absent, and an abstract per row is plenty.
LIST_FIELDS = ["title", "document_number", "type", "subtype", "publication_date", "agencies", "abstract", "html_url", "pdf_url",
               "comments_close_on", "effective_on", "docket_ids", "regulation_id_numbers", "cfr_references", "action",
               "executive_order_number", "presidential_document_number", "signing_date", "president", "citation", "disposition_notes", "raw_text_url"]
# The kinds of presidential document the API filters by (conditions[presidential_document_type]); an unknown one is a 400 with no body.
PRESIDENTIAL_TYPES = ("executive_order", "proclamation", "memorandum", "determination", "notice", "other")
# Carried by the slim only when the record has them, so a rule or a notice gains nothing.
_PRESIDENTIAL_FIELDS = ("executive_order_number", "presidential_document_number", "signing_date", "citation", "disposition_notes", "raw_text_url")
_cache = TTLCache()

mcp = MCPServer(
    "fedreg",
    instructions="The Federal Register: rules, proposed rules, notices and executive orders by words, agency, CFR part or date, presidential documents by kind, signer and signing date; one document by number with its dates and links; one executive order by number with its signer, signing date, disposition line and the link to its text; agency slugs. Read federal_register_index first.",
)


def _cfr(refs: list | None) -> list[str]:
    return [f"{r.get('title')} CFR {r.get('part')}" for r in refs or [] if r.get("title")]


def _slim(d: dict) -> dict:
    out = {
        "document_number": d.get("document_number"), "title": d.get("title"), "type": d.get("type"), "subtype": d.get("subtype"), "action": d.get("action"),
        "publication_date": d.get("publication_date"), "effective_on": d.get("effective_on"), "comments_close_on": d.get("comments_close_on"),
        "agencies": [{"name": a.get("name"), "slug": a.get("slug")} for a in d.get("agencies") or [] if isinstance(a, dict)],
        "abstract": d.get("abstract"), "cfr_references": _cfr(d.get("cfr_references")),
        "docket_ids": d.get("docket_ids") or [], "rins": d.get("regulation_id_numbers") or [],
        "link": d.get("html_url"), "pdf_url": d.get("pdf_url"),
    }
    # A presidential document's own fields; disposition_notes verbatim, newlines and all, since it is the Register's prose.
    out.update({k: d[k] for k in _PRESIDENTIAL_FIELDS if d.get(k) is not None})
    if isinstance(d.get("president"), dict):
        out["president"] = {"name": d["president"].get("name"), "identifier": d["president"].get("identifier")}
    return out


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
                     "federal_register_search by words, type, agency, CFR title and part, or publication dates, newest first; presidential documents by kind (presidential_type), signer (president) and signing dates",
                     "federal_register_document for one document by number, with its dates, CFR parts, links and the regulations.gov docket",
                     "federal_register_executive_order for one executive order by number, with who signed it, when, what it revokes and what revoked it, and the link to its text",
                     "fetch_document on the general server reads the document's link (html_url, or raw_text_url for the plain text) when the text itself is needed"],
        "notes": ["A Rule (RULE) is a final regulation with an effective date; a Proposed Rule (PRORULE) asks for comments before a rule is made; a Notice (NOTICE) is anything else an agency publishes: funding opportunities, information collections, meetings, policy statements.",
                  "Changes to 2 CFR 200 (the Uniform Guidance) are OMB rules here (cfr_title 2, cfr_part 200; agency slug management-and-budget-office); agency notices of funding opportunity are Notices whose action reads 'Notice of funding opportunity'.",
                  "comments_close_on is the comment deadline for a proposed rule, or the application deadline some notices carry; effective_on is when a rule takes effect.",
                  "Agency slugs are the Federal Register's own (management-and-budget-office, national-science-foundation, health-and-human-services-department); an unknown slug is a 400. Look them up with federal_register_agencies.",
                  "Dates are YYYY-MM-DD. document_number (2024-07496) is the id everywhere; citation (89 FR 30046) is the page cite.",
                  "Cite the link (html_url) and the publication date. The body is not returned; read it with fetch_document on the general server.",
                  "Executive orders, proclamations, memoranda, determinations and notices from the President are PRESDOCU; presidential_type picks one kind. EO numbers are found by federal_register_executive_order; the API cannot filter by number, so a search by words for an order's subject uses presidential_type=executive_order.",
                  "disposition_notes is the Office of the Federal Register's own line on an order: 'Revoked by:' means it is no longer in force, 'Revokes:' and 'Amends:' name what it did to earlier orders, 'See:' lists related ones. Null means nothing has touched it. Quote it; do not infer an order's status from anything else.",
                  "signing_date is when the President signed; publication_date is when the Register printed it, days later. Cite the EO number, the signing date and the link.",
                  "The body is at raw_text_url as plain text; fetch_document on the general server reads it. The Register's API holds presidential documents from 1994 on."],
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
    presidential_type: str = "",
    president: str = "",
    signing_from: str = "",
    signing_to: str = "",
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Search Federal Register documents, newest first.

    Give at least one of term, agencies, cfr_title, date_from, presidential_type, president or signing_from. Returns each
    document with its number, type, action, dates, agencies, abstract, CFR parts, docket ids, RINs and a link; a
    presidential document also its kind's number (executive_order_number), signer, signing date, citation, disposition
    line and the link to its plain text.

    Args:
        term: Words in the document, e.g. 'uniform guidance' or '"notice of funding opportunity"' (quotes for a phrase).
        document_types: Comma-separated codes: RULE, PRORULE, NOTICE, PRESDOCU. Empty for all.
        agencies: Comma-separated Federal Register agency slugs, e.g. 'management-and-budget-office'; from federal_register_agencies.
        cfr_title: CFR title the document affects, e.g. '2'.
        cfr_part: CFR part within that title, e.g. '200'. Needs cfr_title.
        date_from: Published on or after YYYY-MM-DD.
        date_to: Published on or before YYYY-MM-DD.
        significant: '1' for documents deemed significant under EO 12866, '0' for the rest, empty for all.
        presidential_type: One kind of presidential document: executive_order, proclamation, memorandum, determination, notice, other. Implies document_types PRESDOCU. Empty for all.
        president: The signer's identifier as the Register has it, e.g. 'joe-biden', 'donald-trump'. Empty for any.
        signing_from: Signed on or after YYYY-MM-DD (presidential documents; signing is days before publication).
        signing_to: Signed on or before YYYY-MM-DD.
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
    kind = presidential_type.strip().lower()
    if kind:
        if kind not in PRESIDENTIAL_TYPES:
            return {"error": f"presidential_type must be one of {', '.join(PRESIDENTIAL_TYPES)}"}
        if any(t != "PRESDOCU" for t in types):
            return {"error": "presidential_type is a kind of PRESDOCU; document_types must be PRESDOCU or empty with it"}
        types = ["PRESDOCU"]
        params.append(("conditions[presidential_document_type]", kind))
    params += [("conditions[type][]", t) for t in types]
    if president.strip():
        if not re.fullmatch(r"[a-z-]+", president.strip()):
            return {"error": "president is the Register's identifier, e.g. 'joe-biden'"}
        params.append(("conditions[president]", president.strip()))
    params += [("conditions[agencies][]", a.lower()) for a in _csv(agencies)]
    if cfr_part.strip() and not cfr_title.strip():
        return {"error": "cfr_part needs cfr_title"}
    if cfr_title.strip():
        if not cfr_title.strip().isdigit():
            return {"error": "cfr_title must be a number, e.g. '2'"}
        params.append(("conditions[cfr][title]", cfr_title.strip()))
        if cfr_part.strip():
            params.append(("conditions[cfr][part]", cfr_part.strip()))
    for field, name, v in (("publication_date", "gte", date_from), ("publication_date", "lte", date_to), ("signing_date", "gte", signing_from), ("signing_date", "lte", signing_to)):
        if v.strip():
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()):
                return {"error": "dates are YYYY-MM-DD"}
            params.append((f"conditions[{field}][{name}]", v.strip()))
    if significant.strip():
        if significant.strip() not in ("0", "1"):
            return {"error": "significant is '1', '0' or empty"}
        params.append(("conditions[significant]", significant.strip()))
    if not any(k in ("conditions[term]", "conditions[agencies][]", "conditions[cfr][title]", "conditions[publication_date][gte]",
                     "conditions[presidential_document_type]", "conditions[president]", "conditions[signing_date][gte]") for k, _ in params):
        return {"error": "give at least one of term, agencies, cfr_title, date_from, presidential_type, president or signing_from"}
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


@mcp.tool(name="federal_register_executive_order", annotations=_READ_ONLY)
async def federal_register_executive_order(number: str) -> dict:
    """One executive order by its number: who signed it and when, its citation, the Register's disposition line (what it
    revokes or amends, what revoked it; null when nothing has touched it) and the link to its plain text. Not the body.

    Args:
        number: The executive order's number, digits only, e.g. '14332'.
    """
    num = (number or "").strip()
    if not num.isdigit():
        return {"error": "number is the executive order's number, digits only, e.g. '14332'"}
    # No condition on the number exists, so a full-text search for it among executive orders, checked against each result's number.
    params: list[tuple[str, str]] = [("per_page", "20"), ("conditions[presidential_document_type]", "executive_order"), ("conditions[term]", num)]
    params += [("fields[]", f) for f in LIST_FIELDS]
    try:
        body = await _cache.remember(f"eo:{num}", DAY, lambda: get_json(f"{BASE}/documents.json", params))
    except ValueError as e:
        return {"error": str(e)}
    hits = [d for d in body.get("results") or [] if str(d.get("executive_order_number") or "") == num]
    if not hits:
        return {"error": f"no executive order {num} in the Federal Register; the Register's API holds presidential documents from 1994 on", "number": num}
    if len(hits) > 1:
        return {"number": num, "candidates": [_slim(d) for d in hits], "note": "More than one document carries this executive order number; none is picked."}
    return {**_slim(hits[0]), "note": "The body is at raw_text_url as plain text; fetch_document on the general server reads it."}


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
# The document and executive order numbers a call names come from federal_register_search (#40); one a person cites passes as given.
given(mcp, {"federal_register_document": {"document_number": "federal_register_search"},
            "federal_register_executive_order": {"number": "federal_register_search"}})
