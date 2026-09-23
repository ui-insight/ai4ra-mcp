"""usaspending: USAspending.gov, the public record of federal awards and the subawards reported under them.

Upstream: https://api.usaspending.gov/api/v2/. No key. The award search takes the award types of one group
at a time (assistance or contracts), a recipient's name or UEI, and a time window; with subawards on it
returns the subawards a recipient received, which no other public source lists.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_json, post_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://api.usaspending.gov/api/v2"
SITE = "https://www.usaspending.gov"
KINDS = {
    "grants": ["02", "03", "04", "05"],
    "other_assistance": ["06", "07", "08", "09", "10", "11"],
    "contracts": ["A", "B", "C", "D"],
}
AWARD_FIELDS = ["Award ID", "Recipient Name", "Recipient UEI", "Award Amount", "Total Outlays", "Start Date", "End Date",
                "Awarding Agency", "Awarding Sub Agency", "Description", "CFDA Number", "generated_internal_id"]
SUBAWARD_FIELDS = ["Sub-Award ID", "Sub-Awardee Name", "Sub-Award Amount", "Sub-Award Date", "Sub-Award Description", "Sub-Award Type",
                   "Prime Award ID", "Prime Recipient Name", "Awarding Agency", "Awarding Sub Agency", "prime_award_generated_internal_id"]
_cache = TTLCache()

mcp = MCPServer(
    "usaspending",
    instructions="USAspending: a recipient's federal awards as a prime and the subawards it received, by name or UEI; one award's record. Read usaspending_index first.",
)


def _window(years: int) -> dict:
    today = _dt.date.today()
    fy_end = today.year + (1 if today.month >= 10 else 0)
    return {"start_date": f"{fy_end - years}-10-01", "end_date": f"{fy_end}-09-30"}


def _slim_award(a: dict) -> dict:
    gid = a.get("generated_internal_id")
    return {"award_id": a.get("Award ID"), "recipient": a.get("Recipient Name"), "recipient_uei": a.get("Recipient UEI"),
            "amount": a.get("Award Amount"), "outlays": a.get("Total Outlays"), "start_date": a.get("Start Date"), "end_date": a.get("End Date"),
            "awarding_agency": a.get("Awarding Agency"), "awarding_sub_agency": a.get("Awarding Sub Agency"),
            "description": (a.get("Description") or "")[:300] or None, "assistance_listing": a.get("CFDA Number"),
            "generated_internal_id": gid, "link": f"{SITE}/award/{gid}" if gid else None}


def _slim_subaward(s: dict) -> dict:
    gid = s.get("prime_award_generated_internal_id")
    return {"subaward_id": s.get("Sub-Award ID"), "subawardee": s.get("Sub-Awardee Name"), "amount": s.get("Sub-Award Amount"),
            "date": s.get("Sub-Award Date"), "type": s.get("Sub-Award Type"), "description": (s.get("Sub-Award Description") or "")[:300] or None,
            "prime_award_id": s.get("Prime Award ID"), "prime_recipient": s.get("Prime Recipient Name"),
            "awarding_agency": s.get("Awarding Agency"), "awarding_sub_agency": s.get("Awarding Sub Agency"),
            "prime_award_link": f"{SITE}/award/{gid}" if gid else None}


def _slim_record(d: dict) -> dict:
    pop = d.get("period_of_performance") or {}
    rec = d.get("recipient") or {}
    aa = d.get("awarding_agency") or {}
    fa = d.get("funding_agency") or {}
    gid = d.get("generated_unique_award_id")
    return {"award_id": d.get("fain") or d.get("piid") or d.get("uri"), "generated_internal_id": gid, "type": d.get("type_description"),
            "category": d.get("category"), "description": d.get("description"), "total_obligation": d.get("total_obligation"),
            "total_outlay": d.get("total_outlay"), "date_signed": d.get("date_signed"),
            "period_of_performance": {"start": pop.get("start_date"), "end": pop.get("end_date")},
            "recipient": {"name": rec.get("recipient_name"), "uei": rec.get("recipient_uei"), "parent": rec.get("parent_recipient_name")},
            "awarding_agency": (aa.get("toptier_agency") or {}).get("name"), "awarding_sub_agency": (aa.get("subtier_agency") or {}).get("name"),
            "funding_agency": (fa.get("toptier_agency") or {}).get("name"),
            "assistance_listings": [{"number": c.get("cfda_number"), "title": c.get("cfda_title")} for c in d.get("cfda_info") or []],
            "subaward_count": d.get("subaward_count"), "total_subaward_amount": d.get("total_subaward_amount"),
            "link": f"{SITE}/award/{gid}" if gid else None}


@mcp.tool(name="usaspending_index", annotations=_READ_ONLY)
async def usaspending_index() -> dict:
    """How to use the USAspending tools. READ THIS FIRST."""
    return {
        "upstream": "https://api.usaspending.gov/api/v2/, no key",
        "workflow": ["usaspending_recipients to resolve a name to its recipient records and UEI",
                     "usaspending_recipient for one recipient's profile, with the former names it is filed under (search other portals by each)",
                     "usaspending_awards_search for the awards an entity held as the prime (grants by default; contracts or other assistance by kind)",
                     "usaspending_subawards_search for the subawards an entity received under other primes' awards, the one public record of that",
                     "usaspending_award for one award's record by its generated id"],
        "notes": ["Searches match the recipient's name or UEI; a former name (a college that became a university) may hold older records, search both.",
                  "Award types come in groups: grants (02-05), other assistance (06-11), contracts (A-D); one group per search.",
                  "The time window is the last ten federal fiscal years unless years is given; amounts are obligations, outlays are what has been paid.",
                  "Subawards are reported by primes under FFATA for subawards of $30,000 or more; small ones are not here.",
                  "Every record carries a usaspending.gov link; cite it and the date of the check."],
    }


@mcp.tool(name="usaspending_recipients", annotations=_READ_ONLY)
async def usaspending_recipients(keyword: str, limit: int = 10) -> dict:
    """Find recipients by name or UEI: each with its UEI, DUNS, level (R a recipient on its own, P a parent, C a child of a parent) and total amount.

    Args:
        keyword: Part of a name, or a UEI, e.g. 'Canisius' or 'JJWLQMLKBB85'.
        limit: Records to return, 1-50. Default 10.
    """
    kw = (keyword or "").strip()
    if not kw:
        return {"error": "keyword is required"}
    limit = max(1, min(int(limit or 10), 50))
    try:
        body = await _cache.remember(f"recipients:{kw.lower()}:{limit}", DAY, lambda: post_json(f"{BASE}/recipient/", {"keyword": kw, "award_type": "all", "limit": limit, "page": 1}))
    except ValueError as e:
        return {"error": str(e)}
    meta = body.get("page_metadata") or {}
    out = [{"name": r.get("name"), "uei": r.get("uei"), "duns": r.get("duns"), "level": r.get("recipient_level"), "amount": r.get("amount"),
            "recipient_id": r.get("id"), "link": f"{SITE}/recipient/{r.get('id')}/latest" if r.get("id") else None} for r in body.get("results") or []]
    return {"keyword": kw, "total": meta.get("total"), "returned": len(out), "recipients": out,
            "note": "level R is the entity itself; P and C are parent and child views of the same UEI"}


def _slim_profile(d: dict) -> dict:
    loc = d.get("location") or {}
    rid = d.get("recipient_id")
    return {"name": d.get("name"), "former_names": d.get("alternate_names") or [], "uei": d.get("uei"), "duns": d.get("duns"),
            "level": d.get("recipient_level"), "parent": {"name": d.get("parent_name"), "uei": d.get("parent_uei")} if d.get("parent_name") else None,
            "location": {"line1": loc.get("address_line1"), "city": loc.get("city_name"), "state": loc.get("state_code"), "zip": loc.get("zip"), "country": loc.get("country_code")},
            "business_types": d.get("business_types") or [],
            "total_transactions": d.get("total_transactions"), "total_transaction_amount": d.get("total_transaction_amount"),
            "recipient_id": rid, "link": f"{SITE}/recipient/{rid}/latest" if rid else None}


@mcp.tool(name="usaspending_recipient", annotations=_READ_ONLY)
async def usaspending_recipient(recipient: str) -> dict:
    """One recipient's profile: its current name and the former names USAspending knows it by, UEI and DUNS, parent, location,
    business types and totals. Read this first for an entity's name history, then search the other portals under every name.

    Args:
        recipient: A recipient_id from usaspending_recipients, or a UEI (the level-R record is used), or a name (the first level-R match).
    """
    key = (recipient or "").strip()
    if not key:
        return {"error": "recipient is required"}
    rid = key if key.count("-") >= 5 else None
    try:
        if not rid:
            found = await _cache.remember(f"recipients:{key.lower()}:25", DAY, lambda: post_json(f"{BASE}/recipient/", {"keyword": key, "award_type": "all", "limit": 25, "page": 1}))
            rows = found.get("results") or []
            pick = next((r for r in rows if r.get("recipient_level") == "R"), None) or next((r for r in rows if r.get("recipient_level") == "P"), None) or (rows[0] if rows else None)
            if not pick:
                return {"error": f"no recipient matches {key}", "recipient": key}
            rid = pick.get("id")
        body = await _cache.remember(f"profile:{rid}", DAY, lambda: get_json(f"{BASE}/recipient/{rid}/"))
    except ValueError as e:
        return {"error": str(e)}
    return _slim_profile(body)


async def _search(recipient: str, kind: str, years: int, limit: int, page: int, subawards: bool) -> dict:
    codes = KINDS.get(kind)
    filters = {"recipient_search_text": [recipient], "award_type_codes": codes, "time_period": [_window(years)]}
    payload = {"filters": filters, "fields": SUBAWARD_FIELDS if subawards else AWARD_FIELDS, "limit": limit, "page": page,
               "sort": "Sub-Award Amount" if subawards else "Award Amount", "order": "desc"}
    if subawards:
        payload["subawards"] = True
    key = f"search:{subawards}:{kind}:{years}:{limit}:{page}:{recipient.lower()}"
    return await _cache.remember(key, HOUR, lambda: post_json(f"{BASE}/search/spending_by_award/", payload))


@mcp.tool(name="usaspending_awards_search", annotations=_READ_ONLY)
async def usaspending_awards_search(recipient: str, kind: str = "grants", years: int = 10, limit: int = 25, page: int = 1) -> dict:
    """The federal awards an entity held as the prime recipient, largest first.

    Args:
        recipient: The recipient's name or UEI, e.g. 'Canisius University' or 'JJWLQMLKBB85'.
        kind: grants (default), other_assistance or contracts; one group per search.
        years: Fiscal years back from the current one to cover, 1-30. Default 10.
        limit: Records per page, 1-100. Default 25.
        page: Page number, from 1.
    """
    rec = (recipient or "").strip()
    if not rec:
        return {"error": "recipient is required"}
    if kind not in KINDS:
        return {"error": f"kind must be one of {', '.join(KINDS)}"}
    years = max(1, min(int(years or 10), 30)); limit = max(1, min(int(limit or 25), 100)); page = max(1, int(page or 1))
    try:
        body = await _search(rec, kind, years, limit, page, False)
    except ValueError as e:
        return {"error": str(e)}
    awards = [_slim_award(a) for a in body.get("results") or []]
    meta = body.get("page_metadata") or {}
    out = {"recipient": rec, "kind": kind, "window": _window(years), "page": page, "returned": len(awards), "awards": awards}
    if meta.get("hasNext"):
        out["next_page"] = page + 1
    return out


@mcp.tool(name="usaspending_subawards_search", annotations=_READ_ONLY)
async def usaspending_subawards_search(recipient: str, kind: str = "grants", years: int = 10, limit: int = 25, page: int = 1) -> dict:
    """The subawards an entity received under other recipients' federal awards, largest first: the public evidence of
    experience as a subrecipient. Each carries the prime award, the prime recipient and the awarding agency.

    Args:
        recipient: The subawardee's name or UEI.
        kind: grants (default), other_assistance or contracts, the type of the prime awards; one group per search.
        years: Fiscal years back from the current one to cover, 1-30. Default 10.
        limit: Records per page, 1-100. Default 25.
        page: Page number, from 1.
    """
    rec = (recipient or "").strip()
    if not rec:
        return {"error": "recipient is required"}
    if kind not in KINDS:
        return {"error": f"kind must be one of {', '.join(KINDS)}"}
    years = max(1, min(int(years or 10), 30)); limit = max(1, min(int(limit or 25), 100)); page = max(1, int(page or 1))
    try:
        body = await _search(rec, kind, years, limit, page, True)
    except ValueError as e:
        return {"error": str(e)}
    subs = [_slim_subaward(s) for s in body.get("results") or []]
    meta = body.get("page_metadata") or {}
    out = {"recipient": rec, "kind": kind, "window": _window(years), "page": page, "returned": len(subs), "subawards": subs,
           "note": "Primes report subawards of $30,000 or more under FFATA; smaller ones are not here."}
    if meta.get("hasNext"):
        out["next_page"] = page + 1
    return out


@mcp.tool(name="usaspending_award", annotations=_READ_ONLY)
async def usaspending_award(generated_internal_id: str) -> dict:
    """One award's record by the generated id a search returned (e.g. 'ASST_NON_P425F200507_091'): description, obligation and
    outlay, period of performance, recipient, agencies, assistance listings, and its subaward count and total.

    Args:
        generated_internal_id: The generated_internal_id from a search result.
    """
    gid = (generated_internal_id or "").strip()
    if not gid:
        return {"error": "generated_internal_id is required"}
    try:
        body = await _cache.remember(f"award:{gid}", DAY, lambda: get_json(f"{BASE}/awards/{gid}/"))
    except ValueError as e:
        return {"error": str(e)}
    return _slim_record(body)


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
