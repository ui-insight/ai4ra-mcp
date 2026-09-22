"""sam: SAM.gov entities, exclusions and Assistance Listings.

Upstream: https://api.sam.gov/ (entity-information v4 and assistance-listings v1). One key covers all
three, and it is the person's own: their client sends it as a bearer token on each call (the Office
pane keeps it beside the gateway key and sends it to this server only). The daily quota is per key:
10 requests for a personal key with no SAM.gov role, 1,000 with a role or a non-federal system
account. A deployment may hold a fallback key in AI4RA_MCP_SAM_KEY, used only when a request sends
none. Requests made by this process are counted so the index can show them.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, api_key, get_json, missing_key
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
KEY_ENV = "AI4RA_MCP_SAM_KEY"
KEY_HOW = "Your personal key comes from the account details page of your SAM.gov account (10 requests a day without a role in SAM.gov, 1,000 with one); a non-federal system account gets 1,000."
ENTITIES = "https://api.sam.gov/entity-information/v4/entities"
EXCLUSIONS = "https://api.sam.gov/entity-information/v4/exclusions"
LISTINGS = "https://api.sam.gov/assistance-listings/v1/search"
_cache = TTLCache()
_requests = {"count": 0}

mcp = MCPServer(
    "sam",
    instructions="SAM.gov: an entity's registration by UEI, CAGE or name; exclusions (debarment and suspension); Assistance Listings by number or agency. Needs a SAM.gov key. Read sam_index first.",
)


async def _get(url: str, params: dict, ttl: float) -> dict:
    key = api_key(KEY_ENV)
    if not key:
        raise LookupError(KEY_ENV)
    cache_key = url + "?" + repr(sorted(params.items()))

    async def make():
        _requests["count"] += 1
        return await get_json(url, {**params, "api_key": key})
    return await _cache.remember(cache_key, ttl, make)


def slim_entity(e: dict) -> dict:
    reg = e.get("entityRegistration") or {}
    core = e.get("coreData") or {}
    info = core.get("entityInformation") or {}
    addr = core.get("physicalAddress") or {}
    gen = core.get("generalInformation") or {}
    types = [t.get("businessTypeDesc") for t in (core.get("businessTypes") or {}).get("businessTypeList") or [] if t.get("businessTypeDesc")]
    uei = reg.get("ueiSAM")
    return {
        "uei": uei, "cage": reg.get("cageCode"), "legal_name": reg.get("legalBusinessName"), "dba_name": reg.get("dbaName"),
        "registration_status": reg.get("registrationStatus"), "registration_date": reg.get("registrationDate"),
        "activation_date": reg.get("activationDate"), "expiration_date": reg.get("expirationDate"),
        "exclusion_status_flag": reg.get("exclusionStatusFlag"), "purpose_of_registration": reg.get("purposeOfRegistrationDesc"),
        "entity_url": info.get("entityURL"), "entity_start_date": info.get("entityStartDate"), "fiscal_year_end": info.get("fiscalYearEndCloseDate"),
        "address": {"line1": addr.get("addressLine1"), "city": addr.get("city"), "state": addr.get("stateOrProvinceCode"), "zip": addr.get("zipCode"), "country": addr.get("countryCode")},
        "entity_structure": gen.get("entityStructureDesc"), "entity_type": gen.get("entityTypeDesc"), "organization_structure": gen.get("organizationStructureDesc"),
        "state_of_incorporation": gen.get("stateOfIncorporationCode"), "business_types": types,
        "link": f"https://sam.gov/entity/{uei}/coreData" if uei else None,
    }


def slim_exclusion(x: dict) -> dict:
    det = x.get("exclusionDetails") or {}
    ident = x.get("exclusionIdentification") or {}
    actions = (x.get("exclusionActions") or {}).get("listOfActions") or []
    act = actions[0] if actions else {}
    addr = x.get("exclusionPrimaryAddress") or x.get("exclusionAddress") or {}
    other = x.get("exclusionOtherInformation") or {}
    name = ident.get("entityName") or ident.get("name") or " ".join(p for p in [ident.get("firstName"), ident.get("middleName"), ident.get("lastName")] if p)
    return {
        "name": name or None, "classification": det.get("classificationType"), "exclusion_type": det.get("exclusionType"),
        "exclusion_program": det.get("exclusionProgram"), "excluding_agency": det.get("excludingAgencyName"), "excluding_agency_code": det.get("excludingAgencyCode"),
        "uei": ident.get("ueiSAM"), "cage": ident.get("cageCode"),
        "activation_date": act.get("activateDate"), "termination_date": act.get("terminationDate"), "termination_type": act.get("terminationType"),
        "record_status": act.get("recordStatus"), "updated": act.get("updateDate"),
        "address": {"city": addr.get("city"), "state": addr.get("stateOrProvinceCode"), "country": addr.get("countryCode")},
        "ct_code": other.get("ctCode"), "comments": other.get("additionalComments"),
        "link": "https://sam.gov/search/?index=ex&sfm[exclusionName]=" + quote(name) if name else "https://sam.gov/search/?index=ex",
    }


def _names(items: list | None) -> list[str]:
    return [t.get("name") for t in items or [] if isinstance(t, dict) and t.get("name")]


def slim_listing(d: dict, full: bool = False) -> dict:
    org = d.get("federalOrganization") or {}
    ov = d.get("overview") or {}
    lid = d.get("assistanceListingId")
    out = {
        "assistance_listing": lid, "title": d.get("title"), "popular_name": d.get("popularShortName") or d.get("popularLongName"),
        "status": d.get("status"), "fiscal_year": d.get("fiscalYear"), "published": d.get("publishedDate"),
        "department": org.get("department"), "agency": org.get("agency"), "office": org.get("office"),
        "objective": ov.get("objective"), "program_web_page": d.get("programWebPage"),
        "link": f"https://sam.gov/fal/{lid}/view" if lid else None,
    }
    if not full:
        return out
    fin = d.get("financialInformation") or {}
    crit = d.get("criteriaForApplying") or {}
    app = d.get("assistanceApplication") or {}
    comp = d.get("compliance") or {}
    fm = comp.get("formulaAndMatching") or {}
    cfr = comp.get("CFR200Requirements") or {}
    out.update({
        "description": ov.get("assistanceListingDescription"),
        "assistance_types": _names([o.get("assistanceType") for o in fin.get("obligations") or []]),
        "funded_current_fy": fin.get("isFundedCurrentFY"),
        "obligations": [{"type": (o.get("assistanceType") or {}).get("name"), "values": o.get("values")} for o in fin.get("obligations") or []],
        "range_and_average": fin.get("rangeAndAverageAssistance"),
        "applicant_types": _names((crit.get("applicant") or {}).get("types")), "applicant_description": (crit.get("applicant") or {}).get("description"),
        "beneficiary_types": _names((crit.get("beneficiary") or {}).get("types")), "beneficiary_description": (crit.get("beneficiary") or {}).get("description"),
        "usage_restrictions": (crit.get("assistanceRestriction") or {}).get("description"),
        "documentation": (crit.get("documentation") or {}).get("description"),
        "deadlines": (app.get("deadlines") or {}).get("description"),
        "application_procedure": (app.get("applicationProcedure") or {}).get("description"),
        "award_procedure": (app.get("awardProcedure") or {}).get("description"),
        "selection_criteria": (app.get("selectionCriteria") or {}).get("description"),
        "cfr_200_subparts_applied": [q.get("code") for q in cfr.get("questions") or [] if q.get("isSelected")],
        "cfr_200_description": cfr.get("description"),
        "reports": [{"code": r.get("code"), "frequency": r.get("frequency"), "description": r.get("description")} for r in comp.get("reports") or []],
        "audit": comp.get("audit"),
        "records": comp.get("records"),
        "matching": {"required": (fm.get("types") or {}).get("matching"), "percent": (fm.get("matching") or {}).get("percent"),
                     "description": (fm.get("matching") or {}).get("description")} if fm else None,
        "contacts": [{"name": c.get("fullName"), "title": c.get("title"), "email": c.get("email"), "phone": c.get("phone")}
                     for c in (d.get("contacts") or {}).get("headquarters") or []],
    })
    return out


@mcp.tool(name="sam_index", annotations=_READ_ONLY)
async def sam_index() -> dict:
    """How to use the SAM.gov tools. READ THIS FIRST: which key is needed, its daily quota, the workflow."""
    return {
        "upstream": "https://api.sam.gov/ entity-information v4 (entities, exclusions) and assistance-listings v1",
        "key": {"on_this_request": api_key(KEY_ENV) is not None, "per_user": "send your own SAM.gov key as a bearer token; the server holds none unless the deployment set " + KEY_ENV + " as a fallback", "how": KEY_HOW,
                "quota_per_day": {"personal key, no SAM.gov role": 10, "personal key with a role": 1000, "non-federal system account": 1000, "federal system account": 10000}},
        "requests_this_process": _requests["count"],
        "workflow": ["sam_entity by UEI, CAGE or legal name: registration status and expiration, address, business types, exclusion flag",
                     "sam_exclusions_search by name or UEI: active exclusions (debarment, suspension, proposed debarment) with agency and dates",
                     "sam_assistance_listing by number (the former CFDA number, e.g. 47.070): objectives, eligibility, compliance, contacts",
                     "sam_assistance_listings_search by agency code or status; there is no keyword search in this API"],
        "notes": ["Every call spends one request of the daily quota; results are cached for a day (entities, listings) or an hour (exclusions).",
                  "An entity's exclusion_status_flag is a quick check; sam_exclusions_search gives the record behind it.",
                  "The exclusions API returns active records only.",
                  "Cite the sam.gov link each record carries, and the date of the check."],
    }


@mcp.tool(name="sam_entity", annotations=_READ_ONLY)
async def sam_entity(uei: str = "", cage: str = "", name: str = "", status: str = "", page: int = 0) -> dict:
    """An entity's SAM.gov registration: status, dates, address, structure, business types and exclusion flag.

    Give one of uei, cage or name. A name matches partially and may return several entities.

    Args:
        uei: The 12-character Unique Entity ID, e.g. 'RV56IG5JM6G9'.
        cage: The 5-character CAGE code.
        name: Legal business name, partial or complete.
        status: 'A' active or 'E' expired registrations; empty for any.
        page: Page of 10 records, from 0. Default 0.
    """
    params: dict = {"includeSections": "entityRegistration,coreData", "page": max(0, int(page or 0))}
    if uei.strip():
        params["ueiSAM"] = uei.strip().upper()
    elif cage.strip():
        params["cageCode"] = cage.strip().upper()
    elif name.strip():
        params["legalBusinessName"] = name.strip()
    else:
        return {"error": "give one of uei, cage or name"}
    if status.strip():
        params["registrationStatus"] = status.strip().upper()[:1]
    try:
        body = await _get(ENTITIES, params, DAY)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e)}
    entities = [slim_entity(e) for e in body.get("entityData") or []]
    out = {"total": body.get("totalRecords"), "page": params["page"], "returned": len(entities), "entities": entities}
    if isinstance(body.get("totalRecords"), int) and (params["page"] + 1) * 10 < body["totalRecords"]:
        out["next_page"] = params["page"] + 1
    return out


@mcp.tool(name="sam_exclusions_search", annotations=_READ_ONLY)
async def sam_exclusions_search(name: str = "", uei: str = "", classification: str = "", agency: str = "", state: str = "", page: int = 0) -> dict:
    """Active exclusions (debarment, suspension, proposed debarment, voluntary exclusion) in SAM.gov.

    Give at least one of name or uei. Returns each exclusion with its type, program, excluding agency, dates and a link.

    Args:
        name: Firm or person name; several words match in any order.
        uei: The entity's Unique Entity ID.
        classification: 'Individual', 'Firm', 'Vessel' or 'Special Entity Designation'; empty for any.
        agency: Excluding agency name, partial.
        state: Two-letter state.
        page: Page of 10 records, from 0. Default 0.
    """
    params: dict = {"page": max(0, min(int(page or 0), 999)), "size": 10}
    if name.strip():
        params["exclusionName"] = name.strip()
    if uei.strip():
        params["ueiSAM"] = uei.strip().upper()
    if not name.strip() and not uei.strip():
        return {"error": "give name or uei"}
    if classification.strip():
        params["classification"] = classification.strip()
    if agency.strip():
        params["excludingAgencyName"] = agency.strip()
    if state.strip():
        params["stateProvince"] = state.strip().upper()
    try:
        body = await _get(EXCLUSIONS, params, HOUR)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e)}
    records = [slim_exclusion(x) for x in body.get("excludedEntity") or []]
    out = {"total": body.get("totalRecords"), "page": params["page"], "returned": len(records), "exclusions": records,
           "note": "Active records only. A total of 0 means no active exclusion matched these terms on the date of the call."}
    if isinstance(body.get("totalRecords"), int) and (params["page"] + 1) * 10 < body["totalRecords"]:
        out["next_page"] = params["page"] + 1
    return out


@mcp.tool(name="sam_assistance_listing", annotations=_READ_ONLY)
async def sam_assistance_listing(number: str) -> dict:
    """One Assistance Listing (the former CFDA program) by its number: objectives, eligibility, application and award
    procedure, the 2 CFR 200 subparts that apply, reporting and audit requirements, matching, and contacts.

    Args:
        number: The listing number, e.g. '47.070' or '93.855'.
    """
    num = (number or "").strip()
    if not num:
        return {"error": "number is required"}
    try:
        body = await _get(LISTINGS, {"assistanceListingId": num, "status": "All", "pageSize": 5}, DAY)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e)}
    data = body.get("assistanceListingsData") or []
    exact = [d for d in data if str(d.get("assistanceListingId")) == num] or data
    if not exact:
        return {"error": f"no Assistance Listing {num}", "number": num}
    return {"number": num, "listing": slim_listing(exact[0], full=True)}


@mcp.tool(name="sam_assistance_listings_search", annotations=_READ_ONLY)
async def sam_assistance_listings_search(organization_codes: str = "", organization_level: str = "", status: str = "Active",
                                         published_from: str = "", published_to: str = "", page: int = 0, page_size: int = 25) -> dict:
    """Assistance Listings by federal organization, status or publication date. The API has no keyword search;
    to find a program by topic, use fetch_document on sam.gov's search page or ask for the number.

    Args:
        organization_codes: Comma-separated FPDS codes for departments or agencies (e.g. '4900' for NSF, '7500' for HHS), or AAC codes for offices.
        organization_level: 'Department', 'Agency' or 'Office'; default Department. Pair it with organization_codes.
        status: 'Active', 'Inactive' or 'All'. Default Active.
        published_from: ISO date, listings published on or after.
        published_to: ISO date, listings published on or before.
        page: Page number from 0. Default 0.
        page_size: Listings a page, 1-1000. Default 25.
    """
    params: dict = {"status": status.strip() or "Active", "pageNumber": max(0, int(page or 0)), "pageSize": max(1, min(int(page_size or 25), 1000))}
    codes = [c.strip() for c in organization_codes.replace("|", ",").split(",") if c.strip()]
    if codes:
        params["organizationCodes"] = ",".join(codes)
        if organization_level.strip():
            params["organizationLevel"] = organization_level.strip()
    if published_from.strip():
        params["publishedDateFrom"] = published_from.strip()
    if published_to.strip():
        params["publishedDateTo"] = published_to.strip()
    try:
        body = await _get(LISTINGS, params, DAY)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e)}
    listings = [slim_listing(d) for d in body.get("assistanceListingsData") or []]
    out = {"total": body.get("totalRecords"), "page": body.get("pageNumber", params["pageNumber"]), "total_pages": body.get("totalPages"),
           "returned": len(listings), "listings": listings}
    if isinstance(body.get("totalPages"), int) and params["pageNumber"] + 1 < body["totalPages"]:
        out["next_page"] = params["pageNumber"] + 1
    return out


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
