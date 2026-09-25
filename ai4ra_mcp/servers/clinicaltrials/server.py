"""clinicaltrials: ClinicalTrials.gov, the registry of clinical studies and their results.

Upstream: https://clinicaltrials.gov/api/v2/ (studies, studies/{nctId}). No key. Pages by token, 1-50 a page
here; dates are YYYY-MM-DD or YYYY-MM as the sponsor entered them; status values are UPPER_SNAKE.
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://clinicaltrials.gov/api/v2"
FIELDS = ("NCTId,BriefTitle,OfficialTitle,OverallStatus,StartDate,PrimaryCompletionDate,CompletionDate,StudyType,Phase,LeadSponsorName,LeadSponsorClass,"
          "CollaboratorName,Condition,InterventionType,InterventionName,EnrollmentCount,StudyFirstSubmitDate,ResultsFirstSubmitDate,HasResults")
STATUSES = {"ACTIVE_NOT_RECRUITING", "COMPLETED", "ENROLLING_BY_INVITATION", "NOT_YET_RECRUITING", "RECRUITING", "SUSPENDED", "TERMINATED", "WITHDRAWN",
            "AVAILABLE", "NO_LONGER_AVAILABLE", "TEMPORARILY_NOT_AVAILABLE", "APPROVED_FOR_MARKETING", "WITHHELD", "UNKNOWN"}
_NCT = re.compile(r"NCT\d{8}")
_cache = TTLCache()

mcp = MCPServer(
    "clinicaltrials",
    instructions="ClinicalTrials.gov: studies by condition, intervention, sponsor, location, words or status; one study by NCT number with its registration and results dates, sponsor, grant ids and design. Read clinicaltrials_index first.",
)


def _date(struct: dict | None) -> str | None:
    return (struct or {}).get("date")


def _slim_study(s: dict) -> dict:
    p = s.get("protocolSection") or {}
    ident, status = p.get("identificationModule") or {}, p.get("statusModule") or {}
    spons, design = p.get("sponsorCollaboratorsModule") or {}, p.get("designModule") or {}
    nct = ident.get("nctId")
    lead = spons.get("leadSponsor") or {}
    return {
        "nct_id": nct, "title": ident.get("briefTitle"), "official_title": ident.get("officialTitle"), "status": status.get("overallStatus"),
        "start_date": _date(status.get("startDateStruct")), "primary_completion_date": _date(status.get("primaryCompletionDateStruct")),
        "completion_date": _date(status.get("completionDateStruct")),
        "first_submitted": status.get("studyFirstSubmitDate"), "results_first_submitted": status.get("resultsFirstSubmitDate"),
        "study_type": design.get("studyType"), "phases": design.get("phases") or [],
        "lead_sponsor": lead.get("name"), "lead_sponsor_class": lead.get("class"), "collaborators": [c.get("name") for c in spons.get("collaborators") or []],
        "conditions": (p.get("conditionsModule") or {}).get("conditions") or [],
        "interventions": [{"type": i.get("type"), "name": i.get("name")} for i in (p.get("armsInterventionsModule") or {}).get("interventions") or []],
        "enrollment": (design.get("enrollmentInfo") or {}).get("count"), "has_results": s.get("hasResults"),
        "link": f"https://clinicaltrials.gov/study/{nct}",
    }


def _slim_full(s: dict) -> dict:
    p = s.get("protocolSection") or {}
    ident, status, spons = p.get("identificationModule") or {}, p.get("statusModule") or {}, p.get("sponsorCollaboratorsModule") or {}
    design, elig, contacts = p.get("designModule") or {}, p.get("eligibilityModule") or {}, p.get("contactsLocationsModule") or {}
    info, over, ipd, party = design.get("designInfo") or {}, p.get("oversightModule") or {}, p.get("ipdSharingStatementModule") or {}, spons.get("responsibleParty") or {}
    locations = contacts.get("locations") or []
    criteria = elig.get("eligibilityCriteria") or ""
    return {
        **_slim_study(s),
        "org_study_id": (ident.get("orgStudyIdInfo") or {}).get("id"), "organization": (ident.get("organization") or {}).get("fullName"),
        "secondary_ids": [{"id": i.get("id"), "type": i.get("type"), "domain": i.get("domain"), "link": i.get("link")} for i in ident.get("secondaryIdInfos") or []],
        "start_date_type": (status.get("startDateStruct") or {}).get("type"), "primary_completion_date_type": (status.get("primaryCompletionDateStruct") or {}).get("type"),
        "first_posted": _date(status.get("studyFirstPostDateStruct")), "results_first_posted": _date(status.get("resultsFirstPostDateStruct")),
        "last_update_posted": _date(status.get("lastUpdatePostDateStruct")), "status_verified": status.get("statusVerifiedDate"),
        "responsible_party": {"type": party.get("type"), "investigator": party.get("investigatorFullName"), "affiliation": party.get("investigatorAffiliation")},
        "brief_summary": (p.get("descriptionModule") or {}).get("briefSummary"),
        "design": {"allocation": info.get("allocation"), "intervention_model": info.get("interventionModel"), "masking": (info.get("maskingInfo") or {}).get("masking"),
                   "primary_purpose": info.get("primaryPurpose"), "observational_model": info.get("observationalModel")},
        "arms": [{"label": a.get("label"), "type": a.get("type"), "interventions": a.get("interventionNames") or []} for a in (p.get("armsInterventionsModule") or {}).get("armGroups") or []],
        "eligibility": {"sex": elig.get("sex"), "minimum_age": elig.get("minimumAge"), "maximum_age": elig.get("maximumAge"), "healthy_volunteers": elig.get("healthyVolunteers"),
                        "criteria": criteria[:2000] + ("..." if len(criteria) > 2000 else "")},
        "locations_count": len(locations),
        "locations": [{"facility": l.get("facility"), "city": l.get("city"), "state": l.get("state"), "country": l.get("country")} for l in locations[:10]],
        "central_contacts": [{"name": c.get("name"), "role": c.get("role"), "phone": c.get("phone"), "email": c.get("email")} for c in contacts.get("centralContacts") or []],
        "overall_officials": [{"name": o.get("name"), "affiliation": o.get("affiliation"), "role": o.get("role")} for o in contacts.get("overallOfficials") or []],
        "oversight": {"fda_regulated_drug": over.get("isFdaRegulatedDrug"), "fda_regulated_device": over.get("isFdaRegulatedDevice"), "has_dmc": over.get("oversightHasDmc")},
        "ipd_sharing": {"statement": ipd.get("ipdSharing"), "description": ipd.get("ipdSharingDescription")},
        "results_section_present": bool(s.get("resultsSection")),
    }


@mcp.tool(name="clinicaltrials_index", annotations=_READ_ONLY)
async def clinicaltrials_index() -> dict:
    """How to use the ClinicalTrials.gov tools. READ THIS FIRST: the registration and results deadlines, where a grant number appears, status values."""
    return {
        "upstream": "https://clinicaltrials.gov/api/v2/, no key",
        "workflow": ["clinicaltrials_search by sponsor, condition, intervention, location, words or status; note the nct_id",
                     "clinicaltrials_study for one study's registration and results dates, sponsor and collaborators, secondary ids (grant numbers), design, eligibility and sites"],
        "notes": ["NIH-funded clinical trials must be registered at ClinicalTrials.gov within 21 days of enrolling the first participant and have results submitted within one year of the primary completion date (42 CFR 11 for applicable clinical trials; NIH policy NOT-OD-16-149 for every NIH-funded trial). Compare first_submitted with start_date, and results_first_submitted with primary_completion_date.",
                  "An NIH grant number appears in a study's secondary_ids with type NIH (e.g. '2R01HD062744-06'); search for an institution's trials with sponsor (lead sponsor or collaborator) and words in term.",
                  "status values: NOT_YET_RECRUITING, RECRUITING, ENROLLING_BY_INVITATION, ACTIVE_NOT_RECRUITING, SUSPENDED, TERMINATED, COMPLETED, WITHDRAWN, UNKNOWN (not verified in two years); expanded access: AVAILABLE, NO_LONGER_AVAILABLE, TEMPORARILY_NOT_AVAILABLE, APPROVED_FOR_MARKETING.",
                  "Dates are as entered: YYYY-MM-DD or YYYY-MM; a date's type is ACTUAL or ESTIMATED (the study record says which). has_results True means results are posted.",
                  "lead_sponsor_class: NIH, FED, OTHER (universities and hospitals), INDUSTRY, NETWORK, OTHER_GOV, INDIV.",
                  "Cite the study link (https://clinicaltrials.gov/study/<nct_id>)."],
        "limits": {"page_size": "1-50 a page; page_token for the next page"},
    }


@mcp.tool(name="clinicaltrials_search", annotations=_READ_ONLY)
async def clinicaltrials_search(
    condition: str = "",
    intervention: str = "",
    term: str = "",
    sponsor: str = "",
    location: str = "",
    status: str = "",
    page_size: int = 20,
    page_token: str = "",
) -> dict:
    """Search ClinicalTrials.gov studies.

    Give at least one of condition, intervention, term, sponsor or location. Returns each study with its NCT id,
    title, status, dates, sponsor, conditions, interventions, enrollment, whether results are posted, and a link.

    Args:
        condition: Condition or disease, e.g. 'asthma'.
        intervention: Intervention or treatment, e.g. 'remdesivir'.
        term: Words anywhere in the record, e.g. a PI name or a grant number.
        sponsor: Lead sponsor or collaborator name, e.g. 'University of Idaho'.
        location: A city, state, country or facility, e.g. 'Idaho'.
        status: Comma-separated status values, e.g. 'RECRUITING,COMPLETED'. Empty for all.
        page_size: Studies a page, 1-50. Default 20.
        page_token: The next_page_token of the previous page. Empty for the first page.
    """
    params: dict = {"pageSize": max(1, min(int(page_size or 20), 50)), "countTotal": "true", "fields": FIELDS}
    for name, v in (("query.cond", condition), ("query.intr", intervention), ("query.term", term), ("query.spons", sponsor), ("query.locn", location)):
        if v and v.strip():
            params[name] = v.strip()
    if not any(k.startswith("query.") for k in params):
        return {"error": "give at least one of condition, intervention, term, sponsor or location"}
    if status.strip():
        wanted = [s.strip().upper().replace(" ", "_") for s in status.split(",") if s.strip()]
        bad = [s for s in wanted if s not in STATUSES]
        if bad:
            return {"error": f"unknown status {', '.join(bad)}; use " + ", ".join(sorted(STATUSES))}
        params["filter.overallStatus"] = ",".join(wanted)
    if page_token.strip():
        params["pageToken"] = page_token.strip()
    try:
        body = await _cache.remember("search:" + repr(sorted(params.items())), HOUR, lambda: get_json(f"{BASE}/studies", params))
    except ValueError as e:
        return {"error": str(e)}
    studies = [_slim_study(s) for s in body.get("studies") or []]
    out = {"total": body.get("totalCount"), "returned": len(studies), "studies": studies}
    if body.get("nextPageToken"):
        out["next_page_token"] = body["nextPageToken"]
    return out


@mcp.tool(name="clinicaltrials_study", annotations=_READ_ONLY)
async def clinicaltrials_study(nct_id: str) -> dict:
    """One study by NCT number: its registration and results dates, sponsor and collaborators, secondary ids
    (grant numbers), design, arms, eligibility, sites, contacts, oversight and data sharing statement.

    Args:
        nct_id: The NCT number, e.g. 'NCT04280705'.
    """
    nct = (nct_id or "").strip().upper()
    if not _NCT.fullmatch(nct):
        return {"error": "nct_id must be NCT followed by eight digits, e.g. NCT04280705"}
    try:
        body = await _cache.remember(f"study:{nct}", DAY, lambda: get_json(f"{BASE}/studies/{nct}"))
    except ValueError as e:
        return {"error": str(e)}
    if not body.get("protocolSection"):
        return {"error": f"no study {nct}", "nct_id": nct}
    return _slim_full(body)


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
