"""re3data: the Registry of Research Data Repositories, where a data management and sharing plan finds the repository its data belongs in.

Upstream: https://www.re3data.org/api/beta/ (XML, no key). The list call, /repositories, takes query and the registry's
own facets as repeated parameters (subjects[], contentTypes[], countries[], dataAccesses[], dataLicenses[], pidSystems[],
certificates[], institutionTypes[]) and returns every matching repository's id, DOI and name, unpaged; the record call,
/repository/<id>, returns the registry's description of one repository in its schema (version 2.2): name, URL,
description, type, subjects (the DFG classification: '2 Life Sciences', '20105 General Genetics'), content types,
keywords, data access and upload terms, data licenses, persistent identifier system, certificates, APIs, the
institutions behind it with their roles and RORs, size, start date, versioning, quality management, citation
guideline, policies and last update. About 3,000 repositories. A search here reads the list and then the first records,
each a request, so a search is as many requests as rows.
"""

from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, TTLCache, get_text
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
API = "https://www.re3data.org/api/beta"
SITE = "https://www.re3data.org/"
NS = {"r3d": "http://www.re3data.org/schema/2-2"}
ROWS, MAX_ROWS = 10, 25
ACCESS = ("open", "restricted", "embargoed", "closed")
_ID = re.compile(r"^r3d\d{9}$")
_cache = TTLCache()

mcp = MCPServer(
    "re3data",
    instructions="re3data, the Registry of Research Data Repositories: repositories by words, subject, content type, country, access terms, identifier system or certificate (re3data_search), and one repository's registry record (re3data_repository). No key. Read re3data_index first.",
)


def _t(el: ET.Element | None, path: str) -> str | None:
    if el is None:
        return None
    found = el.find(path, NS)
    if found is None or found.text is None:
        return None
    t = " ".join(found.text.split())
    return t or None


def _all(el: ET.Element, path: str) -> list[str]:
    return [" ".join(x.text.split()) for x in el.findall(path, NS) if x.text and x.text.strip()]


def parse_list(xml: str) -> list[dict]:
    root = ET.fromstring(xml)
    out = []
    for rep in root.findall("repository"):
        rid = (rep.findtext("id") or "").strip()
        if rid:
            out.append({"id": rid, "name": (rep.findtext("name") or "").strip() or None, "doi": (rep.findtext("doi") or "").strip() or None})
    return out


def parse_repository(xml: str) -> dict:
    root = ET.fromstring(xml)
    rep = root.find("r3d:repository", NS)
    if rep is None:
        raise ValueError("the record carries no repository element (the registry's schema changed)")
    rid = _t(rep, "r3d:re3data.orgIdentifier")
    description = _t(rep, "r3d:description")
    institutions = []
    for inst in rep.findall("r3d:institution", NS):
        institutions.append({"name": _t(inst, "r3d:institutionName"), "country": _t(inst, "r3d:institutionCountry"), "type": _t(inst, "r3d:institutionType"),
                             "responsibility": _all(inst, "r3d:responsibilityType"), "url": _t(inst, "r3d:institutionURL"),
                             "identifiers": _all(inst, "r3d:institutionIdentifier")})
    return {
        "id": rid, "name": _t(rep, "r3d:repositoryName"), "url": _t(rep, "r3d:repositoryURL"),
        "description": description if not description or len(description) <= 600 else description[:600].rsplit(" ", 1)[0] + " …",
        "types": _all(rep, "r3d:type"), "subjects": _all(rep, "r3d:subject"), "content_types": _all(rep, "r3d:contentType"), "keywords": _all(rep, "r3d:keyword"),
        "data_access": _all(rep, "r3d:dataAccess/r3d:dataAccessType"), "data_upload": _all(rep, "r3d:dataUpload/r3d:dataUploadType"),
        "data_licenses": [{"name": _t(lic, "r3d:dataLicenseName"), "url": _t(lic, "r3d:dataLicenseURL")} for lic in rep.findall("r3d:dataLicense", NS)],
        "pid_systems": _all(rep, "r3d:pidSystem"), "certificates": _all(rep, "r3d:certificate"),
        "apis": [{"type": a.get("apiType"), "url": " ".join((a.text or "").split()) or None} for a in rep.findall("r3d:api", NS)],
        "institutions": institutions, "size": _t(rep, "r3d:size"), "start_date": _t(rep, "r3d:startDate"), "end_date": _t(rep, "r3d:endDate"),
        "versioning": _t(rep, "r3d:versioning"), "quality_management": _t(rep, "r3d:qualityManagement"), "enhanced_publication": _t(rep, "r3d:enhancedPublication"),
        "citation_guideline_url": _t(rep, "r3d:citationGuidelineURL"),
        "policies": [{"name": _t(p, "r3d:policyName"), "url": _t(p, "r3d:policyURL")} for p in rep.findall("r3d:policy", NS)],
        "software": _all(rep, "r3d:software/r3d:softwareName"), "last_update": _t(rep, "r3d:lastUpdate"),
        "link": f"{SITE}repository/{rid}" if rid else None,
    }


async def _list(params: list[tuple[str, str]]) -> list[dict]:
    key = "list:" + repr(sorted(params))
    xml = await _cache.remember(key, DAY, lambda: get_text(f"{API}/repositories", params))
    try:
        return parse_list(xml)
    except ET.ParseError as e:
        raise ValueError(f"re3data returned something other than its XML list: {e}") from None


async def _repository(rid: str) -> dict:
    xml = await _cache.remember(f"repo:{rid}", DAY, lambda: get_text(f"{API}/repository/{rid}"))
    try:
        return parse_repository(xml)
    except ET.ParseError as e:
        raise ValueError(f"re3data returned something other than a repository record: {e}") from None


@mcp.tool(name="re3data_index", annotations=_READ_ONLY)
async def re3data_index() -> dict:
    """How to use the re3data tools. READ THIS FIRST: what the registry describes, how subjects are named, what the access and identifier fields mean for a data plan."""
    return {
        "upstream": f"re3data at {API}, the Registry of Research Data Repositories, about 3,000 repositories described in its own schema; no key",
        "workflow": ["re3data_search with words and the facets a data plan cares about: subject, content type, country, open access, DOI as the identifier system, a certificate; each result is the repository's record",
                     "re3data_repository for one repository by its r3d id when a plan names it"],
        "notes": ["Subjects are the DFG classification as re3data writes it: a top level ('2 Life Sciences', '3 Natural Sciences', '4 Engineering Sciences', '1 Humanities and Social Sciences') or a finer code and name ('20105 General Genetics', '313 Atmospheric Science, Oceanography and Climate Research'); the subject filter wants the exact string.",
                  "data_access is the registry's reading of who can get the data (open, restricted, embargoed, closed) and data_upload of who can deposit; a plan that promises public data wants open access and a DOI in pid_systems. certificates lists CoreTrustSeal, DINI, WDS and the like when the repository holds one.",
                  "A search reads the registry's list and then the first rows' records, one request each, so ask for the rows you need; the list itself is unpaged and total says how many matched.",
                  "The registry describes repositories as their operators and the editors recorded them (last_update says when); confirm deposit terms, fees and size limits on the repository's own site before naming it in a plan.",
                  "Cite a repository by name with its URL and its re3data link."],
        "limits": {"search": f"1-{MAX_ROWS} records a call"},
        "link": SITE,
    }


@mcp.tool(name="re3data_search", annotations=_READ_ONLY)
async def re3data_search(query: str = "", subject: str = "", content_type: str = "", country: str = "", data_access: str = "", pid_system: str = "",
                         certificate: str = "", rows: int = ROWS) -> dict:
    """Research data repositories in re3data by words and facets, each with its registry record: where a project's data can go.

    Give at least one argument. Use it to find a repository for a data management and sharing plan: open, a DOI for every
    deposit, in the discipline, certified.

    Args:
        query: Words in the name, description or keywords, e.g. 'genomics', 'soil', 'social science survey'.
        subject: A DFG subject as re3data writes it, e.g. '2 Life Sciences', '20105 General Genetics', '34 Geosciences (including Geography)'.
        content_type: e.g. 'Scientific and statistical data formats', 'Images', 'Software applications', 'Audiovisual data', 'Raw data'.
        country: A three-letter code, e.g. 'USA', 'DEU', 'GBR'.
        data_access: open, restricted, embargoed or closed.
        pid_system: e.g. 'DOI', 'hdl', 'ARK', 'URN'.
        certificate: e.g. 'CoreTrustSeal', 'DINI Certificate', 'WDS'.
        rows: Repositories to describe, 1-25. Default 10.
    """
    rows = max(1, min(int(rows or ROWS), MAX_ROWS))
    params: list[tuple[str, str]] = []
    if query.strip():
        params.append(("query", query.strip()))
    for name, value in (("subjects[]", subject), ("contentTypes[]", content_type), ("countries[]", country.upper()), ("dataAccesses[]", data_access.lower()),
                        ("pidSystems[]", pid_system), ("certificates[]", certificate)):
        if value.strip():
            params.append((name, value.strip()))
    if not params:
        return {"error": "give at least one of query, subject, content_type, country, data_access, pid_system or certificate"}
    if data_access.strip() and data_access.strip().lower() not in ACCESS:
        return {"error": f"data_access must be one of {', '.join(ACCESS)}"}
    try:
        found = await _list(params)
        records = list(await asyncio.gather(*(_repository(r["id"]) for r in found[:rows])))
    except ValueError as e:
        return {"error": str(e), "upstream": API}
    by_id = {r["id"]: r for r in found}
    for rec in records:
        if rec.get("id") in by_id and by_id[rec["id"]].get("doi"):
            rec["doi"] = by_id[rec["id"]]["doi"]
    out = {"query": dict(params), "total": len(found), "returned": len(records), "repositories": records, "link": SITE}
    if len(found) > len(records):
        out["note"] = f"{len(found)} repositories match; the first {len(records)} are described here. Add facets to narrow, or raise rows (to {MAX_ROWS}). The rest, by id and name: " + "; ".join(f"{r['id']} {r['name']}" for r in found[rows:rows + 40]) + (" …" if len(found) > rows + 40 else "")
    return out


@mcp.tool(name="re3data_repository", annotations=_READ_ONLY)
async def re3data_repository(id: str) -> dict:
    """One repository's re3data record: description, subjects, content types, access and upload terms, licenses, identifier system, certificates, APIs, institutions, policies.

    Args:
        id: The re3data id, e.g. 'r3d100000044' (Dryad), from re3data_search.
    """
    rid = id.strip()
    if not _ID.match(rid):
        return {"error": "id must be a re3data id like r3d100000044"}
    try:
        return await _repository(rid)
    except ValueError as e:
        if "404" in str(e):
            return {"error": f"no repository {rid} in re3data"}
        return {"error": str(e), "upstream": API}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# A repository id the model names waits on a search that returned it (#40).
given(mcp, {"re3data_repository": {"id": "re3data_search"}})
