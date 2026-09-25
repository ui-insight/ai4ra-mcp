"""orcid: the ORCID public API, a researcher's own record of names, affiliations, funding and works.

Upstream: https://pub.orcid.org/v3.0/. No key for public reads with Accept: application/json.
Search returns 1,000 at most, 200 a page (the expanded search also gives names and institutions);
dates are {year: {value}, month: {value}, day: {value}}; only what the person made public is returned.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://pub.orcid.org/v3.0"
JSON = {"Accept": "application/json"}
_ID = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")
_cache = TTLCache()

mcp = MCPServer(
    "orcid",
    instructions="ORCID: find a researcher's iD by name and institution, and read their public record: employments, educations, funding and works. Read orcid_index first.",
)


def valid_orcid(v: str) -> str:
    """The bare iD (0000-0001-8781-2041) when v is a well-formed ORCID iD with a good ISO 7064 MOD 11-2 check digit; else ''."""
    s = (v or "").strip().rsplit("/", 1)[-1].upper()
    if not _ID.fullmatch(s):
        return ""
    total = 0
    for ch in s.replace("-", "")[:15]:
        total = (total + int(ch)) * 2
    check = (12 - total % 11) % 11
    return s if s[-1] == ("X" if check == 10 else str(check)) else ""


def _v(d: dict | None, key: str):
    return ((d or {}).get(key) or {}).get("value")


def _date(d: dict | None) -> str | None:
    if not d:
        return None
    parts = [_v(d, "year"), _v(d, "month"), _v(d, "day")]
    return "-".join(p for p in parts if p) or None


def _ms(d: dict | None) -> str | None:
    ms = (d or {}).get("value")
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d") if isinstance(ms, (int, float)) else None


def _affiliation(s: dict) -> dict:
    org = s.get("organization") or {}
    addr = org.get("address") or {}
    return {"organization": org.get("name"), "city": addr.get("city"), "region": addr.get("region"), "country": addr.get("country"),
            "department": s.get("department-name"), "role": s.get("role-title"),
            "start": _date(s.get("start-date")), "end": _date(s.get("end-date")), "current": s.get("end-date") is None}


def _affiliations(section: dict | None, kind: str) -> list[dict]:
    """The summaries of an affiliation section: employments.affiliation-group[].summaries[].employment-summary."""
    out = []
    for group in (section or {}).get("affiliation-group") or []:
        for s in group.get("summaries") or []:
            summary = s.get(f"{kind}-summary")
            if summary:
                out.append(_affiliation(summary))
    return out


def _external_ids(holder: dict | None) -> list[dict]:
    return [{"type": x.get("external-id-type"), "value": x.get("external-id-value"), "url": _v(x, "external-id-url")} for x in (holder or {}).get("external-id") or []]


def _funding(s: dict) -> dict:
    org = s.get("organization") or {}
    ids = _external_ids(s.get("external-ids"))
    return {"title": _v(s.get("title"), "title"), "type": s.get("type"), "organization": org.get("name"),
            "start": _date(s.get("start-date")), "end": _date(s.get("end-date")),
            "grant_numbers": list(dict.fromkeys(x["value"] for x in ids if x.get("type") == "grant_number" and x.get("value"))), "external_ids": ids, "put_code": s.get("put-code")}


def _work(s: dict) -> dict:
    ids = _external_ids(s.get("external-ids"))
    return {"title": _v(s.get("title"), "title"), "type": s.get("type"), "year": _v(s.get("publication-date"), "year"),
            "journal": _v(s, "journal-title"), "doi": next((x["value"] for x in ids if x.get("type") == "doi"), None),
            "url": _v(s, "url"), "put_code": s.get("put-code")}


def slim_record(r: dict) -> dict:
    """One ORCID record, public parts only, in the order a biosketch or current-and-pending draft reads it."""
    oid = (r.get("orcid-identifier") or {}).get("path")
    person = r.get("person") or {}
    name = person.get("name") or {}
    acts = r.get("activities-summary") or {}
    fundings = [_funding(s) for g in (acts.get("fundings") or {}).get("group") or [] for s in g.get("funding-summary") or []]
    groups = (acts.get("works") or {}).get("group") or []
    works = [_work(g["work-summary"][0]) for g in groups if g.get("work-summary")]
    return {
        "orcid": oid, "given_names": _v(name, "given-names"), "family_name": _v(name, "family-name"), "credit_name": _v(name, "credit-name"),
        "other_names": [x.get("content") for x in (person.get("other-names") or {}).get("other-name") or []],
        "biography": (person.get("biography") or {}).get("content"),
        "emails": [e.get("email") for e in (person.get("emails") or {}).get("email") or []],
        "keywords": [k.get("content") for k in (person.get("keywords") or {}).get("keyword") or []],
        "urls": [{"name": u.get("url-name"), "url": _v(u, "url")} for u in (person.get("researcher-urls") or {}).get("researcher-url") or []],
        "employments": _affiliations(acts.get("employments"), "employment"), "educations": _affiliations(acts.get("educations"), "education"),
        "fundings": fundings, "works": {"count": len(groups), "works": works[:25]},
        "last_modified": _ms((r.get("history") or {}).get("last-modified-date")), "link": f"https://orcid.org/{oid}" if oid else None,
    }


def slim_hit(h: dict) -> dict:
    oid = h.get("orcid-id")
    return {"orcid": oid, "given_names": h.get("given-names"), "family_name": h.get("family-names"), "credit_name": h.get("credit-name"),
            "other_names": h.get("other-name") or [], "institutions": h.get("institution-name") or [], "emails": h.get("email") or [],
            "link": f"https://orcid.org/{oid}" if oid else None}


def _term(field: str, value: str) -> str:
    v = value.strip().replace('"', "")
    return f'{field}:"{v}"' if " " in v else f"{field}:{v}"


@mcp.tool(name="orcid_index", annotations=_READ_ONLY)
async def orcid_index() -> dict:
    """How to use the ORCID tools. READ THIS FIRST: what a record holds, what is public, what to cite."""
    return {
        "upstream": "https://pub.orcid.org/v3.0/, no key for public reads",
        "workflow": ["orcid_search by family name, given names and institution to find the iD; several people share a name, so read the institutions",
                     "orcid_record for the person's record: employments, educations, funding with grant numbers, and works with DOIs"],
        "notes": ["Only what the person made public is returned; an empty section means unpublished or unfilled, not none.",
                  "A biosketch or current-and-pending draft starts from the record and is checked against the person; ORCID is self-asserted unless a source such as Crossref or a funder added it.",
                  "given_names in a search matches the registered form ('Lucas', not 'Luke'); search by family name alone and read the hits when unsure.",
                  "works.count is the number of distinct works; works lists the first 25 with DOI, type and year. A work's DOI is the citation to fetch from Crossref or OpenAlex.",
                  "A funding entry's grant_numbers are the funder's award numbers as entered, which the NSF and NIH servers look up.",
                  "Dates may be a year alone. An employment with no end date is current.",
                  "Cite https://orcid.org/<iD>."],
    }


@mcp.tool(name="orcid_search", annotations=_READ_ONLY)
async def orcid_search(query: str = "", given_names: str = "", family_name: str = "", affiliation: str = "", rows: int = 20, start: int = 0) -> dict:
    """Find researchers' ORCID iDs by name and institution, with each hit's names, institutions and public emails.

    Give family_name (with given_names or affiliation to narrow), or a raw Solr query.

    Args:
        query: A raw Solr query, e.g. 'family-name:Sheneman AND affiliation-org-name:"University of Idaho"'; used as is when given.
        given_names: Given names as registered, e.g. 'Lucas'.
        family_name: Family name, e.g. 'Sheneman'.
        affiliation: An organization name in the person's affiliations, e.g. 'University of Idaho'.
        rows: Hits to return, 1-50. Default 20.
        start: Hit to start from. Default 0.
    """
    if query.strip():
        q = query.strip()
    else:
        terms = [_term(f, v) for f, v in (("given-names", given_names), ("family-name", family_name), ("affiliation-org-name", affiliation)) if v.strip()]
        if not terms:
            return {"error": "give family_name, given_names, affiliation or a raw query"}
        q = " AND ".join(terms)
    params = {"q": q, "rows": max(1, min(int(rows or 20), 50)), "start": max(0, int(start or 0))}
    try:
        body = await _cache.remember("search:" + repr(sorted(params.items())), HOUR, lambda: get_json(f"{BASE}/expanded-search/", params, JSON))
    except ValueError as e:
        return {"error": str(e)}
    hits = [slim_hit(h) for h in (body.get("expanded-result") if isinstance(body, dict) else None) or []]
    total = body.get("num-found") if isinstance(body, dict) else None
    out = {"query": q, "start": params["start"], "returned": len(hits), "total": total, "people": hits}
    if isinstance(total, int) and params["start"] + len(hits) < total and hits:
        out["next_start"] = params["start"] + len(hits)
    return out


@mcp.tool(name="orcid_record", annotations=_READ_ONLY)
async def orcid_record(orcid_id: str) -> dict:
    """A researcher's public ORCID record: names, biography, employments, educations, funding and works.

    Args:
        orcid_id: The iD, e.g. '0000-0001-8781-2041' or its https://orcid.org/ URL.
    """
    oid = valid_orcid(orcid_id)
    if not oid:
        return {"error": "orcid_id must be a valid ORCID iD like 0000-0001-8781-2041 (the last character is a check digit)"}
    try:
        body = await _cache.remember(f"record:{oid}", DAY, lambda: get_json(f"{BASE}/{oid}/record", None, JSON))
    except ValueError as e:
        return {"error": str(e)}
    if not isinstance(body, dict) or not body.get("orcid-identifier"):
        return {"error": f"no public record for {oid}"}
    return slim_record(body)


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
