"""regulations: Regulations.gov, the dockets, documents and public comments of federal rulemaking.

Upstream: https://api.regulations.gov/v4/ (documents, documents/{id}, dockets/{id}, comments). A free api.data.gov key
sent as X-Api-Key, 1,000 requests an hour per key; DEMO_KEY is shared and small. page[size] is 5-250 and
page[number] at most 20; date filters are YYYY-MM-DD; timestamps come back in UTC.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, api_key, get_json, missing_key
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
KEY_ENV = "AI4RA_MCP_REGULATIONS_KEY"
KEY_HOW = "A free key comes from https://api.data.gov/signup/ (an email address is all it asks) and works on api.regulations.gov; DEMO_KEY works for a few requests an hour."
BASE = "https://api.regulations.gov/v4"
DOC_TYPES = {"notice": "Notice", "proposed rule": "Proposed Rule", "rule": "Rule", "supporting & related material": "Supporting & Related Material", "other": "Other"}
SITE = "https://www.regulations.gov"
_cache = TTLCache()

mcp = MCPServer(
    "regulations",
    instructions="Regulations.gov: rulemaking documents by words, type, agency, docket or dates and whether open for comment; one document with its files; one docket; the public comments on a document. Needs a free api.data.gov key. Read regulations_gov_index first.",
)


async def _get(path: str, params: dict, ttl: float) -> dict:
    key = api_key(KEY_ENV)
    if not key:
        raise LookupError(KEY_ENV)
    cache_key = path + "?" + repr(sorted(params.items()))
    body = await _cache.remember(cache_key, ttl, lambda: get_json(f"{BASE}/{path}", params, {"X-Api-Key": key}))
    return body if isinstance(body, dict) else {}


async def _one(path: str) -> dict:
    """One record by path: its JSON:API data row, or the error a tool returns as is."""
    try:
        body = await _get(path, {}, DAY)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e)}
    row = body.get("data")
    return row if isinstance(row, dict) and row.get("id") else {"error": f"nothing at Regulations.gov for {path}"}


def slim_document(row: dict) -> dict:
    a = row.get("attributes") or {}
    did = row.get("id")
    return {
        "document_id": did, "title": a.get("title"), "document_type": a.get("documentType"), "subtype": a.get("subtype"),
        "agency_id": a.get("agencyId"), "docket_id": a.get("docketId"), "posted_date": a.get("postedDate"),
        "comment_start_date": a.get("commentStartDate"), "comment_end_date": a.get("commentEndDate"),
        "open_for_comment": a.get("openForComment"), "withdrawn": a.get("withdrawn"),
        "fr_doc_num": a.get("frDocNum"), "object_id": a.get("objectId"), "link": f"{SITE}/document/{did}",
    }


def slim_document_full(row: dict) -> dict:
    a = row.get("attributes") or {}
    return {
        **slim_document(row), "abstract": a.get("docAbstract"), "cfr_part": a.get("cfrPart"), "rins": a.get("additionalRins") or [],
        "effective_date": a.get("effectiveDate"), "page_count": a.get("pageCount"), "topics": a.get("topics") or [], "subject": a.get("subject"),
        "files": [{"format": f.get("format"), "url": f.get("fileUrl"), "size": f.get("size")} for f in a.get("fileFormats") or []],
        "comment_link": f"{SITE}/commenton/{row.get('id')}" if a.get("openForComment") else None,
    }


def slim_docket(row: dict) -> dict:
    a = row.get("attributes") or {}
    did = row.get("id")
    return {
        "docket_id": did, "title": a.get("title"), "agency_id": a.get("agencyId"), "docket_type": a.get("docketType"), "abstract": a.get("dkAbstract"),
        "rin": a.get("rin"), "program": a.get("program"), "keywords": a.get("keywords"), "effective_date": a.get("effectiveDate"),
        "modified_date": a.get("modifyDate"), "object_id": a.get("objectId"), "link": f"{SITE}/docket/{did}",
    }


def slim_comment(row: dict) -> dict:
    a = row.get("attributes") or {}
    cid = row.get("id")
    return {"comment_id": cid, "title": a.get("title"), "posted_date": a.get("postedDate"), "agency_id": a.get("agencyId"),
            "withdrawn": a.get("withdrawn"), "object_id": a.get("objectId"), "link": f"{SITE}/comment/{cid}"}


def _paging(page: int, page_size: int) -> dict:
    """The API refuses a page under 5 records and serves no page past 20."""
    return {"page[size]": str(max(5, min(int(page_size or 25), 250))), "page[number]": str(page), "sort": "-postedDate"}


def _page_out(body: dict, things: str, rows: list, page: int) -> dict:
    meta = body.get("meta") or {}
    out = {"page": page, "returned": len(rows), "total": meta.get("totalElements"), "total_pages": meta.get("totalPages"), things: rows}
    if meta.get("hasNextPage") and page < 20:
        out["next_page"] = page + 1
    return out


def _date_ok(v: str) -> bool:
    return re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()) is not None


def _id_ok(v: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9_.-]+", v.strip()) is not None


@mcp.tool(name="regulations_gov_index", annotations=_READ_ONLY)
async def regulations_gov_index() -> dict:
    """How to use the Regulations.gov tools. READ THIS FIRST: the key and its limit, the workflow, which id filters comments."""
    return {
        "upstream": "https://api.regulations.gov/v4/ (JSON:API over the public rulemaking dockets)",
        "key": {"on_this_request": api_key(KEY_ENV) is not None,
                "per_user": "send your own api.data.gov key as a bearer token; the server holds none unless the deployment set " + KEY_ENV + " as a fallback",
                "how": KEY_HOW},
        "workflow": ["regulations_gov_documents_search by words, type, agency, docket or posted dates, or only what is open for comment; note the document_id and object_id",
                     "regulations_gov_document for one document: its dates, files (PDF, HTML) and the Federal Register number",
                     "regulations_gov_docket for the docket a document belongs to",
                     "regulations_gov_comments_search for the public comments on a document (by its object_id) or in a docket"],
        "notes": ["The limit is 1,000 requests an hour per key; DEMO_KEY is shared by everyone and allows only a few requests an hour, so get a key for real use.",
                  "Comments on a document are filtered by the document's object_id (commentOnId), not its document_id; take object_id from the search or the document.",
                  "A document's fr_doc_num is its Federal Register document number; the fedreg server's federal_register_document reads that number for the text links.",
                  "Agency ids are Regulations.gov's own short codes (OMB, NSF, HHS, ED, EPA); a docket id is agency-year-number (OMB-2023-0001) and a document id is the docket id plus a suffix.",
                  "Timestamps are UTC; posted_date's date part is the day the document was posted. Date filters are YYYY-MM-DD.",
                  "A page holds 5-250 records and the API serves at most 20 pages of one search; narrow by docket, agency or dates past that.",
                  "Cite the link on each record and its posted date."],
    }


@mcp.tool(name="regulations_gov_documents_search", annotations=_READ_ONLY)
async def regulations_gov_documents_search(
    term: str = "",
    document_type: str = "",
    agency: str = "",
    docket_id: str = "",
    posted_from: str = "",
    posted_to: str = "",
    comment_open_only: bool = False,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    """Search Regulations.gov documents, newest posted first.

    Give at least one of term, agency, docket_id or comment_open_only. Returns each document with its id, type, agency,
    docket, posted and comment dates, whether it is open for comment, its Federal Register number, object_id and a link.

    Args:
        term: Words to search for, e.g. 'indirect cost rate'.
        document_type: One of Notice, Proposed Rule, Rule, Supporting & Related Material, Other. Empty for all.
        agency: Regulations.gov agency id, e.g. 'OMB', 'NSF', 'HHS'.
        docket_id: A docket id, e.g. 'OMB-2023-0001'.
        posted_from: Posted on or after YYYY-MM-DD.
        posted_to: Posted on or before YYYY-MM-DD.
        comment_open_only: True for documents whose comment period has not closed.
        page: Page number, 1-20. Default 1.
        page_size: Documents a page, 5-250. Default 25.
    """
    page = max(1, min(int(page or 1), 20))
    params = _paging(page, page_size)
    if term.strip():
        params["filter[searchTerm]"] = term.strip()
    if document_type.strip():
        dt = DOC_TYPES.get(document_type.strip().lower())
        if not dt:
            return {"error": "document_type must be one of Notice, Proposed Rule, Rule, Supporting & Related Material, Other"}
        params["filter[documentType]"] = dt
    if agency.strip():
        params["filter[agencyId]"] = agency.strip().upper()
    if docket_id.strip():
        if not _id_ok(docket_id):
            return {"error": "docket_id looks like 'OMB-2023-0001'"}
        params["filter[docketId]"] = docket_id.strip()
    for name, v in (("ge", posted_from), ("le", posted_to)):
        if v.strip():
            if not _date_ok(v):
                return {"error": "dates are YYYY-MM-DD"}
            params[f"filter[postedDate][{name}]"] = v.strip()
    if comment_open_only:
        params["filter[commentEndDate][ge]"] = date.today().isoformat()
    if not any(k in params for k in ("filter[searchTerm]", "filter[agencyId]", "filter[docketId]", "filter[commentEndDate][ge]")):
        return {"error": "give at least one of term, agency, docket_id or comment_open_only"}
    try:
        body = await _get("documents", params, HOUR)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e)}
    return _page_out(body, "documents", [slim_document(r) for r in body.get("data") or []], page)


@mcp.tool(name="regulations_gov_document", annotations=_READ_ONLY)
async def regulations_gov_document(document_id: str) -> dict:
    """One Regulations.gov document: its dates, abstract, CFR part, files (PDF, HTML), the Federal Register number
    to read its text by, and its object_id for a comments search.

    Args:
        document_id: The document id, e.g. 'OMB-2023-0001-0001'.
    """
    did = (document_id or "").strip()
    if not did or not _id_ok(did):
        return {"error": "document_id looks like 'OMB-2023-0001-0001'"}
    row = await _one(f"documents/{did}")
    if "error" in row:
        return row
    return {**slim_document_full(row), "note": "fr_doc_num is the Federal Register document number; the fedreg server reads it, and fetch_document on the general server reads a file url."}


@mcp.tool(name="regulations_gov_docket", annotations=_READ_ONLY)
async def regulations_gov_docket(docket_id: str) -> dict:
    """One Regulations.gov docket: its title, agency, type (Rulemaking or Nonrulemaking), abstract, RIN and dates.

    Args:
        docket_id: The docket id, e.g. 'OMB-2023-0001'.
    """
    did = (docket_id or "").strip()
    if not did or not _id_ok(did):
        return {"error": "docket_id looks like 'OMB-2023-0001'"}
    row = await _one(f"dockets/{did}")
    if "error" in row:
        return row
    return {**slim_docket(row), "note": "regulations_gov_documents_search with this docket_id lists the docket's documents."}


@mcp.tool(name="regulations_gov_comments_search", annotations=_READ_ONLY)
async def regulations_gov_comments_search(
    document_object_id: str = "",
    docket_id: str = "",
    term: str = "",
    page: int = 1,
    page_size: int = 25,
) -> dict:
    """Public comments on a document, in a docket, or matching words, newest first.

    Give at least one of document_object_id, docket_id or term. Returns each comment's id, title (usually the
    commenter), posted date, agency and a link; the comment text is on the link.

    Args:
        document_object_id: The document's object_id (e.g. '09000064856107a5'), from the search or the document; not its document_id.
        docket_id: A docket id, e.g. 'OMB-2023-0001'.
        term: Words in the comment.
        page: Page number, 1-20. Default 1.
        page_size: Comments a page, 5-250. Default 25.
    """
    page = max(1, min(int(page or 1), 20))
    params = _paging(page, page_size)
    if document_object_id.strip():
        if not re.fullmatch(r"[0-9a-fA-F]{16}", document_object_id.strip()):
            return {"error": "document_object_id is the 16-character object_id (e.g. '09000064856107a5'), not the document_id"}
        params["filter[commentOnId]"] = document_object_id.strip()
    if docket_id.strip():
        if not _id_ok(docket_id):
            return {"error": "docket_id looks like 'OMB-2023-0001'"}
        params["filter[docketId]"] = docket_id.strip()
    if term.strip():
        params["filter[searchTerm]"] = term.strip()
    if not any(k in params for k in ("filter[commentOnId]", "filter[docketId]", "filter[searchTerm]")):
        return {"error": "give at least one of document_object_id, docket_id or term"}
    try:
        body = await _get("comments", params, HOUR)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e)}
    return _page_out(body, "comments", [slim_comment(r) for r in body.get("data") or []], page)


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
