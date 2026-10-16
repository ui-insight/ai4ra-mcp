"""datacite: DataCite, the registry of DOIs for datasets, software, preprints, reports and other research outputs.

Upstream: https://api.datacite.org/dois (JSON:API, no key; filters affiliation-id (a ROR), funder-id (a Crossref Funder
Registry DOI), resource-type-id (dataset, software, text, image, ...), published (a year or 'from,to'); query in
Elasticsearch syntax over the metadata, so an award is fundingReferences.awardNumber:"1754803"; page[size] and
page[number]; sort). Every DOI a repository registers through DataCite is here with the metadata the repository
deposited: creators with affiliations and ORCIDs, publisher, year, type, description, subjects, funding references
with award numbers, related identifiers (the paper a dataset supplements), license, sizes and formats, and DataCite's
own citation, view and download counts. The University of Idaho's own DOIs (prefix 10.60841) are minted through VERSO
and resolve to it. This is the register for a data management and sharing plan's outputs and for an institution's or
award's datasets; a DOI minted through Crossref (most journal articles) is in the crossref server, not here.
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
API = "https://api.datacite.org/dois"
SITE = "https://commons.datacite.org/"
ROWS, MAX_ROWS = 25, 100
TYPES = ("dataset", "software", "text", "image", "audiovisual", "collection", "model", "physical-object", "report", "preprint", "dissertation", "journal-article",
         "book", "book-chapter", "conference-paper", "other")
_DOI = re.compile(r"10\.\d{4,9}/\S+")
_cache = TTLCache()

mcp = MCPServer(
    "datacite",
    instructions="DataCite: the DOIs of datasets, software and other research outputs by institution (ROR), funder, award number, type or words (datacite_search), and one DOI's record (datacite_doi). No key. Read datacite_index first.",
)


def _doi(v: str) -> str:
    v = (v or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:"):
        if v.lower().startswith(prefix):
            v = v[len(prefix):]
    return v if _DOI.fullmatch(v) else ""


def _person(p: dict) -> dict:
    orcid = next((i.get("nameIdentifier") for i in p.get("nameIdentifiers") or [] if (i.get("nameIdentifierScheme") or "").upper() == "ORCID"), None)
    # An affiliation is an object in the current schema and a bare name in older deposits.
    affiliations = [a.get("name") if isinstance(a, dict) else a for a in p.get("affiliation") or []]
    return {"name": p.get("name"), "orcid": orcid, "affiliations": [a for a in affiliations if a]}


def slim(rec: dict, full: bool = False) -> dict:
    a = rec.get("attributes") or {}
    types = a.get("types") or {}
    titles = a.get("titles") or []
    descs = [d.get("description") for d in a.get("descriptions") or [] if d.get("description")]
    description = " ".join(" ".join(descs).split()) or None
    creators = a.get("creators") or []
    rights = [r.get("rightsIdentifier") or r.get("rights") for r in a.get("rightsList") or [] if r.get("rightsIdentifier") or r.get("rights")]
    out = {
        "doi": a.get("doi"), "title": titles[0].get("title") if titles else None, "year": a.get("publicationYear"), "publisher": a.get("publisher"),
        "resource_type": types.get("resourceTypeGeneral"), "resource_type_detail": types.get("resourceType") or None,
        "creators": [_person(p) for p in creators[:10]], "creator_count": len(creators),
        "description": description if full or not description or len(description) <= 400 else description[:400].rsplit(" ", 1)[0] + " …",
        "funding": [{"funder": f.get("funderName"), "funder_id": f.get("funderIdentifier"), "award_number": f.get("awardNumber"), "award_title": " ".join((f.get("awardTitle") or "").split()) or None}
                    for f in a.get("fundingReferences") or []],
        "related": [{"relation": r.get("relationType"), "id": r.get("relatedIdentifier"), "type": r.get("relatedIdentifierType")} for r in (a.get("relatedIdentifiers") or [])[:10]],
        "rights": rights, "url": a.get("url"), "state": a.get("state"),
        "counts": {"citations": a.get("citationCount"), "views": a.get("viewCount"), "downloads": a.get("downloadCount")},
        "link": f"https://doi.org/{a.get('doi')}" if a.get("doi") else None,
    }
    if full:
        out.update({"subjects": [s.get("subject") for s in a.get("subjects") or [] if s.get("subject")], "sizes": a.get("sizes") or [], "formats": a.get("formats") or [],
                    "language": a.get("language"), "version": a.get("version"), "contributors": [_person(p) for p in (a.get("contributors") or [])[:10]],
                    "geolocations": [g.get("geoLocationPlace") for g in a.get("geoLocations") or [] if g.get("geoLocationPlace")],
                    "dates": [{"type": d.get("dateType"), "date": d.get("date")} for d in a.get("dates") or []], "registered": a.get("registered"), "updated": a.get("updated")})
    return out


@mcp.tool(name="datacite_index", annotations=_READ_ONLY)
async def datacite_index() -> dict:
    """How to use the DataCite tools. READ THIS FIRST: what DataCite holds and does not, how to find an institution's or an award's datasets, what the counts mean."""
    return {
        "upstream": f"DataCite at {API}, the registry of DOIs for datasets, software and other research outputs with the metadata each repository deposited; no key",
        "workflow": ["ror_search (the ror server) or openalex_institutions_search for the institution's ROR; crossref_funders_search for a funder's 10.13039 id",
                     "datacite_search by affiliation (ROR), funder, award number, resource type, years or words: the outputs with creators, type, funding and the paper each supplements",
                     "datacite_doi for one record in full: subjects, sizes, formats, related identifiers, counts"],
        "notes": ["DataCite holds what repositories registered through it (Dryad, Zenodo, Figshare, ICPSR, OSF, institutional repositories; the University of Idaho's own DOIs, prefix 10.60841, come from VERSO). Journal articles mostly carry Crossref DOIs and are in the crossref server; a dataset in a repository that mints its own DOIs elsewhere is not here.",
                  "affiliation matches the ROR a creator's affiliation carries; a repository that deposited no ROR leaves its records out, so an institution's count is a floor, not a census. funder and award_number match fundingReferences the depositor filled in, likewise.",
                  "resource_type is DataCite's general type (Dataset, Software, Text, Image, Other ...); resource_type_detail is the depositor's own word for it.",
                  "related shows the DOIs a record points at and how (IsSupplementTo the paper it supports, IsVersionOf, Cites); counts are DataCite's own, from repositories that report usage and from DOI-to-DOI citations, and are low or zero for most records.",
                  "For a data management and sharing plan: search by award_number for what an award has deposited, or by affiliation and resource_type dataset for an institution's datasets in a period.",
                  "Cite the DOI (https://doi.org/...)."],
        "limits": {"search": f"1-{MAX_ROWS} a page, page for the next"},
        "link": SITE,
    }


@mcp.tool(name="datacite_search", annotations=_READ_ONLY)
async def datacite_search(query: str = "", affiliation_ror: str = "", funder_id: str = "", award_number: str = "", resource_type: str = "",
                          from_year: str = "", to_year: str = "", page: int = 1, per_page: int = ROWS) -> dict:
    """Research outputs with DataCite DOIs: datasets, software, reports and more, by institution, funder, award number, type, years or words.

    Give at least one of query, affiliation_ror, funder_id or award_number. Use it for an institution's datasets in a
    period, what an award deposited, or datasets on a topic.

    Args:
        query: Words in the title, description or subjects, e.g. 'wildfire smoke'.
        affiliation_ror: The institution's ROR, 'https://ror.org/03hbp5t65' or '03hbp5t65', matched on creators' affiliations.
        funder_id: The funder's Crossref Funder Registry DOI, '10.13039/100000001' (NSF), with or without https://doi.org/.
        award_number: The award number as the depositor wrote it, e.g. '1754803' or 'R01AI135270'.
        resource_type: dataset, software, text, image, audiovisual, collection, model, physical-object, report, preprint, dissertation, other. Empty for all.
        from_year: Earliest publication year.
        to_year: Latest publication year.
        page: Page, 1-based. Default 1.
        per_page: Records a page, 1-100. Default 25.
    """
    params: dict = {}
    parts = []
    if query.strip():
        parts.append(f"({query.strip()})")
    if award_number.strip():
        num = award_number.strip().replace('"', "")
        parts.append(f'fundingReferences.awardNumber:"{num}"')
    if affiliation_ror.strip():
        ror = affiliation_ror.strip().rsplit("/", 1)[-1]
        if not re.fullmatch(r"0[a-z0-9]{8}", ror):
            return {"error": "affiliation_ror must be a ROR id like https://ror.org/03hbp5t65"}
        params["affiliation-id"] = f"https://ror.org/{ror}"
        params["affiliation"] = "true"
    if funder_id.strip():
        fid = _doi(funder_id)
        if not fid or not fid.startswith("10.13039/"):
            return {"error": "funder_id must be a Crossref Funder Registry DOI like 10.13039/100000001"}
        params["funder-id"] = fid
    if resource_type.strip():
        rt = resource_type.strip().lower().replace(" ", "-").replace("_", "-")
        if rt not in TYPES:
            return {"error": f"resource_type must be one of {', '.join(TYPES)}"}
        params["resource-type-id"] = rt
    years = [from_year.strip(), to_year.strip()]
    if any(years):
        if not all(y.isdigit() for y in years if y):
            return {"error": "from_year and to_year must be years"}
        params["published"] = f"{years[0] or '1900'},{years[1] or '2100'}"
    if not parts and not params.get("affiliation-id") and not params.get("funder-id"):
        return {"error": "give at least one of query, affiliation_ror, funder_id or award_number"}
    page = max(1, int(page or 1))
    per_page = max(1, min(int(per_page or ROWS), MAX_ROWS))
    if parts:
        params["query"] = " AND ".join(parts)
    else:
        params["sort"] = "-created"
    params.update({"page[size]": per_page, "page[number]": page})
    key = "search:" + repr(sorted(params.items()))
    try:
        body = await _cache.remember(key, HOUR, lambda: get_json(API, params))
    except ValueError as e:
        return {"error": str(e), "upstream": API}
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        return {"error": "DataCite did not return its data list", "upstream": API}
    meta = body.get("meta") or {}
    total = meta.get("total")
    out = {"query": {k: v for k, v in (("query", query.strip()), ("affiliation_ror", params.get("affiliation-id")), ("funder_id", params.get("funder-id")),
                                        ("award_number", award_number.strip()), ("resource_type", params.get("resource-type-id")), ("years", params.get("published"))) if v},
           "page": page, "returned": len(data), "total": total, "records": [slim(r) for r in data], "link": SITE}
    if isinstance(total, int) and page * per_page < total:
        out["next_page"] = page + 1
    return out


@mcp.tool(name="datacite_doi", annotations=_READ_ONLY)
async def datacite_doi(doi: str) -> dict:
    """One DataCite DOI's record in full: creators with affiliations and ORCIDs, type, description, subjects, funding, related identifiers, license, sizes, formats, counts.

    Args:
        doi: The DOI, '10.3886/e249735v1', with or without https://doi.org/ or doi:.
    """
    d = _doi(doi)
    if not d:
        return {"error": "doi must be a DOI like 10.3886/e249735v1"}
    try:
        body = await _cache.remember(f"doi:{d.lower()}", DAY, lambda: get_json(f"{API}/{d}"))
    except ValueError as e:
        if "404" in str(e):
            return {"error": f"no DataCite record for {d}: a Crossref DOI (see the crossref server), a typo, or a DOI not yet registered"}
        return {"error": str(e), "upstream": API}
    rec = body.get("data") if isinstance(body, dict) else None
    if not isinstance(rec, dict):
        return {"error": "DataCite did not return a record", "upstream": API}
    return slim(rec, full=True)


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# A ROR, a funder id or a DOI comes from the person or from ror, crossref and openalex; no tool here lists them, so nothing is stated (#40).
