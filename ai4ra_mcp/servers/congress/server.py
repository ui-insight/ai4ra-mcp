"""congress: the Congress.gov API, the Library of Congress's record of bills, laws and members.

Upstream: https://api.congress.gov/v3/ (JSON; a free api.data.gov key, sent as the X-Api-Key header, from
https://api.congress.gov/sign-up/). Bills are addressed by Congress, type (hr, s, hjres, sjres, hconres, sconres,
hres, sres) and number: /bill/119/hr/1 with its actions, summaries, text versions, titles, cosponsors, committees and
related bills as sub-resources; /bill/119 and /bill/119/hr list bills by update date in a window; /law/119 the bills
that became law; /member/<state> the state's current members. The API has no word search: words are the govinfo
server's (collection BILLS, BILLSTATUS, CRPT); this one answers what a bill is, where it stands and who carries it.
"""

from __future__ import annotations

import html as _html
import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, api_key, get_json, missing_key
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
KEY_ENV = "AI4RA_MCP_CONGRESS_KEY"
KEY_HOW = "A free key comes from https://api.congress.gov/sign-up/ (api.data.gov, an email address is all it asks); the same api.data.gov key serves the fac, regulations, perdiem, govinfo and scorecard servers."
BASE = "https://api.congress.gov/v3"
SITE = "https://www.congress.gov/"
TYPES = ("hr", "s", "hjres", "sjres", "hconres", "sconres", "hres", "sres")
ROWS, MAX_ROWS = 20, 250
_TAG = re.compile(r"<[^>]+>")
_cache = TTLCache()

mcp = MCPServer(
    "congress",
    instructions="Congress.gov: one bill's record, status, summary and text versions (congress_bill), its actions (congress_bill_actions), bills by Congress, type and dates (congress_bills), the bills that became law (congress_laws), a state's members (congress_members). Needs a free api.data.gov key. Read congress_index first.",
)


def _headers() -> dict:
    key = api_key(KEY_ENV)
    if not key:
        raise LookupError(KEY_ENV)
    return {"X-Api-Key": key}


async def _get(path: str, params: dict | None = None, ttl: float = HOUR) -> dict:
    headers = _headers()
    p = {**(params or {}), "format": "json"}
    body = await _cache.remember(f"get:{path}:{repr(sorted(p.items()))}", ttl, lambda: get_json(f"{BASE}/{path}", p, headers))
    if not isinstance(body, dict):
        raise ValueError("Congress.gov did not return a JSON object")
    return body


def text(fragment: str | None) -> str | None:
    if not fragment:
        return None
    return re.sub(r"\s+", " ", _html.unescape(_TAG.sub(" ", fragment))).strip() or None


def bill_link(congress: int | str, btype: str, number: int | str) -> str:
    names = {"hr": "house-bill", "s": "senate-bill", "hjres": "house-joint-resolution", "sjres": "senate-joint-resolution", "hconres": "house-concurrent-resolution",
             "sconres": "senate-concurrent-resolution", "hres": "house-resolution", "sres": "senate-resolution"}
    return f"{SITE}bill/{congress}th-congress/{names.get(btype.lower(), btype)}/{number}"


def slim_bill_row(b: dict) -> dict:
    la = b.get("latestAction") or {}
    return {"congress": b.get("congress"), "type": b.get("type"), "number": b.get("number"), "title": b.get("title"), "origin_chamber": b.get("originChamber"),
            "introduced": b.get("introducedDate"), "latest_action": {"date": la.get("actionDate"), "text": la.get("text")}, "laws": b.get("laws"),
            "updated": b.get("updateDate"), "link": bill_link(b.get("congress"), str(b.get("type") or ""), b.get("number"))}


def slim_bill(b: dict) -> dict:
    out = slim_bill_row(b)
    out.update({"policy_area": (b.get("policyArea") or {}).get("name"),
                "sponsors": [{"name": s.get("fullName"), "party": s.get("party"), "state": s.get("state"), "district": s.get("district"), "bioguide_id": s.get("bioguideId")} for s in b.get("sponsors") or []],
                "counts": {k: (b.get(k) or {}).get("count") for k in ("actions", "cosponsors", "committees", "committeeReports", "relatedBills", "summaries", "textVersions", "amendments", "titles", "subjects") if isinstance(b.get(k), dict)},
                "cbo_cost_estimates": [{"title": c.get("title"), "date": c.get("pubDate"), "url": c.get("url")} for c in b.get("cboCostEstimates") or []][:5],
                "committee_reports": [c.get("citation") for c in (b.get("committeeReports") or {}).get("item", [])] if isinstance(b.get("committeeReports"), dict) else None})
    return out


@mcp.tool(name="congress_index", annotations=_READ_ONLY)
async def congress_index() -> dict:
    """How to use the Congress.gov tools. READ THIS FIRST: the key, how bills are addressed, what this API does not do."""
    return {
        "upstream": f"Congress.gov at {BASE}, the Library of Congress's legislative record; a free api.data.gov key",
        "key": {"required": True, "on_this_request": api_key(KEY_ENV) is not None, "per_user": "send your own api.data.gov key as a bearer token; the server holds none unless the deployment set " + KEY_ENV + " as a fallback", "how": KEY_HOW},
        "workflow": ["congress_bill with the Congress, type and number (119, hr, 1) for what a bill is and where it stands: title, sponsors, latest action, the laws it became, summary, text versions",
                     "congress_bill_actions for the full chronology",
                     "congress_bills for the bills of a Congress or a type updated in a window, newest first; congress_laws for the bills that became law",
                     "congress_members for a state's current delegation"],
        "notes": ["A bill is addressed by Congress (119 is 2025-2026), type (hr House bill, s Senate bill, hjres and sjres joint resolutions, hconres and sconres concurrent, hres and sres simple) and number. An appropriations act is a bill that became a public law; its law number is on the record (119-75).",
                  "This API has no word search. To find bills by words use govinfo_search with collections BILLS or BILLSTATUS, or for the enacted text PLAW, then read the bill here by its number.",
                  "summary is the Congressional Research Service's latest; text_versions name each version (Introduced, Engrossed, Enrolled) with its formats and the Congress.gov URL of the text. Committee reports (H. Rept. 119-xx) carry the directive language behind an appropriation; GovInfo's CRPT collection has their text.",
                  "Cite a bill by its number and Congress (H.R. 1, 119th Congress) with its Congress.gov link, and a law by its public law number."],
        "link": SITE,
    }


def _check(congress: int, bill_type: str, number: int) -> tuple[int, str, int] | dict:
    c, t, n = int(congress or 0), bill_type.strip().lower(), int(number or 0)
    if c < 93 or c > 150:
        return {"error": "congress must be a Congress number, 93 (1973) or later; 119 is 2025-2026"}
    if t not in TYPES:
        return {"error": f"bill_type must be one of {', '.join(TYPES)}"}
    if n <= 0:
        return {"error": "number must be the bill's number"}
    return c, t, n


@mcp.tool(name="congress_bill", annotations=_READ_ONLY)
async def congress_bill(congress: int, bill_type: str, number: int) -> dict:
    """One bill or resolution: title, sponsors, policy area, latest action, the laws it became, the CRS summary, text versions and counts of its actions, cosponsors, committees and reports.

    Args:
        congress: The Congress, e.g. 119.
        bill_type: hr, s, hjres, sjres, hconres, sconres, hres or sres.
        number: The bill's number, e.g. 1.
    """
    checked = _check(congress, bill_type, number)
    if isinstance(checked, dict):
        return checked
    c, t, n = checked
    try:
        body = await _get(f"bill/{c}/{t}/{n}")
        bill = body.get("bill") or {}
        out = slim_bill(bill)
        if (bill.get("summaries") or {}).get("count"):
            s = await _get(f"bill/{c}/{t}/{n}/summaries", {"limit": 5})
            latest = (s.get("summaries") or [])[-1:] or [{}]
            out["summary"] = {"as_of": latest[0].get("actionDate"), "stage": latest[0].get("actionDesc"), "text": text(latest[0].get("text"))}
        if (bill.get("textVersions") or {}).get("count"):
            tv = await _get(f"bill/{c}/{t}/{n}/text", {"limit": 20})
            out["text_versions"] = [{"version": v.get("type"), "date": (v.get("date") or "")[:10] or None,
                                     "formats": {f.get("type"): f.get("url") for f in v.get("formats") or []}} for v in tv.get("textVersions") or []]
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        if "404" in str(e):
            return {"error": f"no bill {t.upper()} {n} in the {c}th Congress"}
        return {"error": str(e), "upstream": BASE}
    return out


@mcp.tool(name="congress_bill_actions", annotations=_READ_ONLY)
async def congress_bill_actions(congress: int, bill_type: str, number: int, rows: int = 50, offset: int = 0) -> dict:
    """A bill's actions in order, newest first: introduced, referred, reported, passed, signed, became law.

    Args:
        congress: The Congress, e.g. 119.
        bill_type: hr, s, hjres, sjres, hconres, sconres, hres or sres.
        number: The bill's number.
        rows: Actions a page, 1-250. Default 50.
        offset: Offset of the first action. Default 0.
    """
    checked = _check(congress, bill_type, number)
    if isinstance(checked, dict):
        return checked
    c, t, n = checked
    rows, offset = max(1, min(int(rows or 50), MAX_ROWS)), max(0, int(offset or 0))
    try:
        body = await _get(f"bill/{c}/{t}/{n}/actions", {"limit": rows, "offset": offset})
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e), "upstream": BASE}
    actions = [{"date": a.get("actionDate"), "text": a.get("text"), "type": a.get("type"), "chamber": (a.get("sourceSystem") or {}).get("name"),
                "committees": [x.get("name") for x in a.get("committees") or []] or None} for a in body.get("actions") or []]
    total = (body.get("pagination") or {}).get("count")
    out = {"bill": f"{t.upper()} {n}, {c}th Congress", "total": total, "offset": offset, "returned": len(actions), "actions": actions, "link": bill_link(c, t, n) + "/all-actions"}
    if isinstance(total, int) and offset + len(actions) < total:
        out["next_offset"] = offset + len(actions)
    return out


@mcp.tool(name="congress_bills", annotations=_READ_ONLY)
async def congress_bills(congress: int = 119, bill_type: str = "", from_date: str = "", to_date: str = "", rows: int = ROWS, offset: int = 0) -> dict:
    """Bills of a Congress, optionally of one type, updated in a window, most recently updated first.

    Args:
        congress: The Congress, e.g. 119.
        bill_type: hr, s, hjres, sjres, hconres, sconres, hres, sres; empty for all.
        from_date: Earliest update, YYYY-MM-DD.
        to_date: Latest update, YYYY-MM-DD.
        rows: Bills a page, 1-250. Default 20.
        offset: Offset of the first bill. Default 0.
    """
    c, t = int(congress or 119), bill_type.strip().lower()
    if t and t not in TYPES:
        return {"error": f"bill_type must be one of {', '.join(TYPES)} or empty"}
    params: dict = {"limit": max(1, min(int(rows or ROWS), MAX_ROWS)), "offset": max(0, int(offset or 0)), "sort": "updateDate desc"}
    for label, v, key in (("from_date", from_date, "fromDateTime"), ("to_date", to_date, "toDateTime")):
        if v.strip():
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()):
                return {"error": f"{label} must be YYYY-MM-DD"}
            params[key] = v.strip() + ("T00:00:00Z" if key == "fromDateTime" else "T23:59:59Z")
    try:
        body = await _get(f"bill/{c}" + (f"/{t}" if t else ""), params)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e), "upstream": BASE}
    bills = [slim_bill_row(b) for b in body.get("bills") or []]
    total = (body.get("pagination") or {}).get("count")
    out = {"congress": c, "type": t or None, "total": total, "offset": params["offset"], "returned": len(bills), "bills": bills, "link": SITE}
    if isinstance(total, int) and params["offset"] + len(bills) < total:
        out["next_offset"] = params["offset"] + len(bills)
    return out


@mcp.tool(name="congress_laws", annotations=_READ_ONLY)
async def congress_laws(congress: int = 119, rows: int = ROWS, offset: int = 0) -> dict:
    """The bills of a Congress that became law, with their public law numbers, most recently updated first.

    Args:
        congress: The Congress, e.g. 119.
        rows: Laws a page, 1-250. Default 20.
        offset: Offset of the first. Default 0.
    """
    c = int(congress or 119)
    params = {"limit": max(1, min(int(rows or ROWS), MAX_ROWS)), "offset": max(0, int(offset or 0))}
    try:
        body = await _get(f"law/{c}", params)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e), "upstream": BASE}
    laws = [slim_bill_row(b) for b in body.get("bills") or []]
    total = (body.get("pagination") or {}).get("count")
    out = {"congress": c, "total": total, "offset": params["offset"], "returned": len(laws), "laws": laws, "link": SITE}
    if isinstance(total, int) and params["offset"] + len(laws) < total:
        out["next_offset"] = params["offset"] + len(laws)
    return out


@mcp.tool(name="congress_members", annotations=_READ_ONLY)
async def congress_members(state: str) -> dict:
    """A state's current members of Congress: name, party, chamber, district, with their Congress.gov pages.

    Args:
        state: Two-letter state code, e.g. 'ID'.
    """
    st = state.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", st):
        return {"error": "state must be a two-letter code, e.g. 'ID'"}
    try:
        body = await _get(f"member/{st}", {"currentMember": "true", "limit": 100}, ttl=DAY)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e), "upstream": BASE}
    members = []
    for m in body.get("members") or []:
        terms = ((m.get("terms") or {}).get("item") or [])
        last = terms[-1] if terms else {}
        members.append({"name": m.get("name"), "party": m.get("partyName"), "state": m.get("state"), "district": m.get("district"), "chamber": last.get("chamber"),
                        "since": last.get("startYear"), "bioguide_id": m.get("bioguideId"), "link": m.get("url", "").replace("api.congress.gov/v3/member/", "www.congress.gov/member/").split("?")[0] or None})
    return {"state": st, "total": len(members), "members": members, "link": f"{SITE}members?q=%7B%22member-state%22%3A%22{st}%22%7D"}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# A bill's Congress, type and number come from the person or from govinfo_search and congress_bills (#40).
given(mcp, {"congress_bill_actions": {"number": "congress_bills"}})
