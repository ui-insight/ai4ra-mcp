"""One process, several MCP servers, each at its own path.

    /<server>/mcp       the server's streamable-HTTP endpoint
    /<server>/skills/   its skills folder as static files (catalog.json, components/)
    /                   a JSON index of what is mounted, with one sentence for the whole and, per server, the
                        institution whose own knowledge it needs (`institution`) and which tool arguments
                        name a thing it holds (`given`)
    /README.md          this repository's README, the server's own account of itself

Run every server with `ai4ra-mcp`, a subset with `--only NAME`, or one server
over stdio with `--stdio NAME` for a local MCP client.

A keyed server takes the person's own key from `Authorization: Bearer <key>` on
the request (BearerKeyMiddleware), for that request only; the README's Keys
section says which servers want one and where a key comes from.
"""

from __future__ import annotations

import argparse
import os
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from ai4ra_mcp.common.given import given_of
from ai4ra_mcp.common.http import describe_auth, headers_log, log_headers, log_no_keys, request_key
from ai4ra_mcp.servers.ai4ra.server import mcp as ai4ra
from ai4ra_mcp.servers.bls.server import mcp as bls
from ai4ra_mcp.servers.campusmap.server import mcp as campusmap
from ai4ra_mcp.servers.classes.server import mcp as classes
from ai4ra_mcp.servers.datacite.server import mcp as datacite
from ai4ra_mcp.servers.directory.server import mcp as directory
from ai4ra_mcp.servers.clickup.server import mcp as clickup
from ai4ra_mcp.servers.clinicaltrials.server import mcp as clinicaltrials
from ai4ra_mcp.servers.congress.server import mcp as congress
from ai4ra_mcp.servers.costs.server import mcp as costs
from ai4ra_mcp.servers.crossref.server import mcp as crossref
from ai4ra_mcp.servers.csl.server import mcp as csl
from ai4ra_mcp.servers.ecfr.server import mcp as ecfr
from ai4ra_mcp.servers.events.server import mcp as events
from ai4ra_mcp.servers.fac.server import mcp as fac
from ai4ra_mcp.servers.fedreg.server import mcp as fedreg
from ai4ra_mcp.servers.general.server import mcp as general
from ai4ra_mcp.servers.github.server import mcp as github
from ai4ra_mcp.servers.govinfo.server import mcp as govinfo
from ai4ra_mcp.servers.grants.server import mcp as grants
from ai4ra_mcp.servers.icite.server import mcp as icite
from ai4ra_mcp.servers.idstat.server import mcp as idstat
from ai4ra_mcp.servers.lakehouse import server as lakehouse
from ai4ra_mcp.servers.library.server import mcp as library
from ai4ra_mcp.servers.nih.server import mcp as nih
from ai4ra_mcp.servers.nihdates.server import mcp as nihdates
from ai4ra_mcp.servers.nihgps.server import mcp as nihgps
from ai4ra_mcp.servers.nihguide.server import mcp as nihguide
from ai4ra_mcp.servers.ncura.server import mcp as ncura
from ai4ra_mcp.servers.nsf.server import mcp as nsf
from ai4ra_mcp.servers.oig.server import mcp as oig
from ai4ra_mcp.servers.omb.server import mcp as omb
from ai4ra_mcp.servers.openpayments.server import mcp as openpayments
from ai4ra_mcp.servers.openalex.server import mcp as openalex
from ai4ra_mcp.servers.orcid.server import mcp as orcid
from ai4ra_mcp.servers.osm.server import mcp as osm
from ai4ra_mcp.servers.osti.server import mcp as osti
from ai4ra_mcp.servers.perdiem.server import mcp as perdiem
from ai4ra_mcp.servers.perseus.server import mcp as perseus
from ai4ra_mcp.servers.propublica.server import mcp as propublica
from ai4ra_mcp.servers.pubmed.server import mcp as pubmed
from ai4ra_mcp.servers.re3data.server import mcp as re3data
from ai4ra_mcp.servers.regulations.server import mcp as regulations
from ai4ra_mcp.servers.ror.server import mcp as ror
from ai4ra_mcp.servers.pappg.server import mcp as pappg
from ai4ra_mcp.servers.s2s.server import mcp as s2s
from ai4ra_mcp.servers.sam.server import mcp as sam
from ai4ra_mcp.servers.scorecard.server import mcp as scorecard
from ai4ra_mcp.servers.treasury.server import mcp as treasury
from ai4ra_mcp.servers.udm.server import mcp as udm
from ai4ra_mcp.servers.uidaho.server import mcp as uidaho
from ai4ra_mcp.servers.usaspending.server import mcp as usaspending
from ai4ra_mcp.servers.usda.server import mcp as usda
from ai4ra_mcp.servers.weather.server import mcp as weather
from ai4ra_mcp.servers.wikidata.server import mcp as wikidata
from ai4ra_mcp.servers.wolfram.server import mcp as wolfram

# Index order is picker order: the general fold first, then the research-administration skills, then the public
# upstreams grouped by the job they serve (the rules and announcements, the awards held, the vetting lists, the
# budget figures, the scholarly record, the project trackers), and last the one institution's own servers.
SERVERS: dict[str, MCPServer] = {
    "general": general, "ai4ra": ai4ra, "udm": udm,
    "ecfr": ecfr, "fedreg": fedreg, "regulations": regulations, "idstat": idstat, "govinfo": govinfo, "congress": congress, "grants": grants, "s2s": s2s, "pappg": pappg, "nihgps": nihgps, "nihguide": nihguide, "nihdates": nihdates, "usda": usda, "omb": omb, "ncura": ncura,
    "nih": nih, "nsf": nsf, "usaspending": usaspending,
    "sam": sam, "fac": fac, "csl": csl, "oig": oig, "openpayments": openpayments, "propublica": propublica, "ror": ror, "scorecard": scorecard,
    "perdiem": perdiem, "bls": bls, "treasury": treasury, "osm": osm, "weather": weather, "wolfram": wolfram,
    "openalex": openalex, "pubmed": pubmed, "icite": icite, "crossref": crossref, "datacite": datacite, "re3data": re3data, "orcid": orcid, "osti": osti, "clinicaltrials": clinicaltrials, "wikidata": wikidata, "perseus": perseus,
    "clickup": clickup, "github": github,
    "uidaho": uidaho, "classes": classes, "directory": directory, "events": events, "campusmap": campusmap, "costs": costs, "library": library, **lakehouse.SERVERS,
}
# Mounted and reachable by its path, but left out of the index at `/`, so no client's picker offers it until it is ready
# to share: s2s, held back 2026-10-28.
UNLISTED = {"s2s"}
SERVERS_DIR = Path(__file__).parent / "servers"
WEB = "https://github.com/ui-insight/ai4ra-mcp/blob/main/ai4ra_mcp/servers/"

# What a client's picker shows for each server, whether it wants a key of the person's own, and the institution whose own
# stuff the server is about (`institution`, #38): Idaho's own knowledge on its three, GitHub on the server whose skills
# run over GitHub's own MCP server (so a client folds it with that server, 2026-10-14); a fact the server knows, never a
# label for servers that share a job, which is a client's curation.
UIDAHO = "University of Idaho"
META: dict[str, dict] = {
    "ecfr": {"label": "eCFR", "description": "Federal regulations from the eCFR: search within a title and part, read a section (the current text, or as of a date), compare versions; a report-only check of a passage against 2 CFR 200."},
    "grants": {"label": "grants.gov", "description": "Federal funding opportunities: search, then one opportunity's record with its attachments."},
    "s2s": {"label": "Grants.gov S2S", "description": "The Grants.gov Applicant System-to-System service with the person's own certificate: an opportunity's package, a GrantApplication checked against the schemas, its submission (where the deployment allows), and the status of what was submitted. The deployment's default endpoint is a mock unless configured otherwise.",
            "key": {"required": False, "hint": "Paste your S2S credential bundle: the base64url JSON of your client certificate and key, made with `python -m ai4ra_mcp.servers.s2s.credentials cert.pem key.pem`. Without one the deployment's fallback certificate is used, which only the mock accepts."}},
    "pappg": {"label": "NSF PAPPG", "description": "The NSF Proposal & Award Policies & Procedures Guide (NSF 24-1) as NSF publishes it: the chapters, a chapter's outline, one section's text by label (II.D.2.b), anchor or heading words, and words across the guide. No key."},
    "nihgps": {"label": "NIH Grants Policy Statement", "description": "The NIH Grants Policy Statement, web edition, as NIH publishes it: the table of contents, one section's text and tables by number (7.9.1) or title, and words across a chapter's sections, with the revision each page carries. No key."},
    "nihguide": {"label": "NIH Guide", "description": "The NIH Guide for Grants and Contracts: notices and funding opportunities by words, institute, kind and date from the Guide's own search; one notice's text by number; the week's notices. No key."},
    "nihdates": {"label": "NIH due dates and salary cap", "description": "NIH's standard application due dates by activity code, the three review and award cycles, and the salary cap by fiscal year and award date, from grants.nih.gov's pages with their links. No key."},
    "ncura": {"label": "NCURA calendar", "description": "The National Council of University Research Administrators' meetings, conferences and workshops from its public calendar: upcoming events or the past year by words, one event with dates, registration deadlines, fees, description and venue. No key or membership."},
    "usda": {"label": "USDA and APHIS terms", "description": "The USDA General Terms and Conditions (for Federal Awards and for Mutual Interest Agreements), the 2026 USDA deviations to them, and APHIS's award terms and its New World Screwworm supplement, from the official PDFs saved here and split by section word for word: the documents and their versions, one document's contents, one section's text with the PDF page link and any deviation that names it, words across them, and what was in force on an award's date. No key."},
    "omb": {"label": "OMB memoranda", "description": "OMB's memoranda to agencies (M-26-01, M-24-11) from whitehouse.gov and the archived prior-administration page, 2017 on: by year or title words, one by number with the later memoranda that name it, each with its date and PDF link. No key."},
    "campusmap": {"label": "Campus map", "institution": UIDAHO, "description": "The University of Idaho campus map (Concept3D): buildings and places by name or category with coordinates and building numbers, what is near a point (accessible entrances, restrooms, parking, bike racks, dining), one place with its entrances and parking, the categories. Read with the map page's own client key, no key of the person's; a route between two places is the osm server's."},
    "costs": {"label": "UI costs", "institution": UIDAHO, "description": "What the University of Idaho charges, from its own pages with their links: the tuition and fee schedule by student group, the estimated cost of attendance by student type and program, payment deadlines, late fees and refunds, and the Student Health Insurance Program's premiums and dates."},
    "library": {"label": "UI Library", "institution": UIDAHO, "description": "The University of Idaho Library's catalog (Primo): what the library holds by words, title, author, subject, ISBN or ISSN, where a physical copy sits and whether it is on the shelf, articles with their DOI and full-text status, one record in full with its table of contents; Course Reserves and Special Collections as scopes. No key."},
    "uidaho": {"label": "UI guidance", "institution": UIDAHO, "description": "University policy for sponsored projects (APM, FSH), found by what each policy covers or by number and title; a report-only check of a passage against it; and the F&A and fringe rates from the rate agreement and the fringe-rate page, reported in the Rates contract's order."},
    "classes": {"label": "Class schedule", "institution": UIDAHO, "description": "The University of Idaho class schedule and course catalog: who teaches what, when and where, by term, subject, course number or instructor; one section in full; courses by subject, number or title and one course's catalog record, from the registrar's public Browse Classes and Browse Course Catalog. No key."},
    "directory": {"label": "Campus directory", "institution": UIDAHO, "description": "The University of Idaho campus directory, the employees the university publishes at directory.uidaho.edu: a person by last name, first name, email or department, their university email, phone, title, department and office, and the department list. Employees only, read through the directory's own search form. No key."},
    "events": {"label": "Campus calendar", "institution": UIDAHO, "description": "The University of Idaho campus calendar at uidaho.edu/events, every event the university's calendars publish: lectures and seminars, athletics games, Registrar deadlines, workshops, concerts and closures, by date window, words or calendar, with when, where (campus room or online link), the owning calendar, a line of description and links; the days the university is closed; one event in full; the calendars that feed it. Read from the calendar's public Trumba feed. No key."},
    "general": {"label": "General", "description": "Any office, any document: search the open web, read a page or PDF as text; the guide to AI writing tells."},
    "github": {"label": "GitHub skills", "institution": "GitHub", "description": "Two skills for a GitHub repository through GitHub's own MCP server, whose tools they name: a change as a pull request on an agent branch, and one look at the Actions runs. No tools of its own; no key, since the key is GitHub's server's."},
    "ai4ra": {"label": "AI4RA", "description": "Research-administration guides and prompts: an RFA record, a narrative, a work plan, a budget outline and the NSF budget form (each as a guide any client can follow), the compliance-concerns vocabulary for grouping statements, cost-allowability checks and budget justifications; one tool, ai4ra_guide, that serves them."},
    "udm": {"label": "UDM", "description": "The AI4RA Unified Data Model from its published schema: an overview, one table's columns with types, vocabularies and synonyms, one section, and the guide to converting records to it, served by udm_guide."},
    "nih": {"label": "NIH RePORTER", "description": "NIH-funded projects by PI, organization or topic; one project by number; its publications."},
    "nsf": {"label": "NSF awards", "description": "NSF awards by PI, institution or keyword; one award with its abstract; its outcomes report."},
    "sam": {"label": "SAM.gov", "description": "Entity registrations, exclusions and Assistance Listings.",
            "key": {"required": True, "hint": "Paste your SAM.gov public API key, from the account details page of your SAM.gov account."}},
    "usaspending": {"label": "USAspending", "description": "Federal awards an entity held as the prime and the subawards it received, by name or UEI; one award's record."},
    "fac": {"label": "Federal Audit Clearinghouse", "description": "Single audits, findings and federal awards for subrecipient risk assessment.",
            "key": {"required": True, "hint": "Paste your api.data.gov key for the FAC API (free, from the signup at fac.gov/api)."}},
    "fedreg": {"label": "Federal Register", "description": "Rules, proposed rules and notices in the Federal Register: search by words, agency, CFR part or date; one document with its dates and links; agency slugs."},
    "govinfo": {"label": "GovInfo", "description": "Federal documents from the Government Publishing Office: public laws (the appropriations acts), bills, committee reports, the U.S. Code, CFR, Federal Register, hearings and GAO reports, by words, collection and dates; one document's record and its text in pieces.",
                "key": {"required": True, "hint": "Paste your api.data.gov key, from https://api.data.gov/signup/ (the same key as perdiem, fac and regulations)."}},
    "congress": {"label": "Congress.gov", "description": "A bill's record, status, summary, text versions and actions by Congress, type and number; bills and laws of a Congress by date; a state's members. No word search (use GovInfo).",
                 "key": {"required": True, "hint": "Paste your api.data.gov key, from https://api.congress.gov/sign-up/ (the same key as perdiem, fac and regulations)."}},
    "idstat": {"label": "Idaho Statutes", "description": "The Idaho Code as the Legislature publishes it: the titles, a title's chapters, a chapter's sections, one section's text and history by citation, and the Legislature's full-text search of the code. Current law only, updated each July 1. No key."},
    "regulations": {"label": "Regulations.gov", "description": "Rulemaking dockets, documents and public comments on Regulations.gov: search, one document with its files, one docket, the comments on a document.",
                    "key": {"required": True, "hint": "Paste your api.data.gov key, from https://api.data.gov/signup/ (DEMO_KEY works for a few requests an hour)."}},
    "csl": {"label": "Consolidated Screening List", "description": "Export-control and sanctions screening of a name against the BIS, OFAC and State lists (Entity List, SDN, Denied Persons, ITAR debarred and the rest).",
            "key": {"required": True, "hint": "Paste your trade.gov subscription key, from https://developer.trade.gov/ (subscribe to the Consolidated Screening List API)."}},
    "oig": {"label": "OIG exclusions (LEIE)", "description": "Whether a person or business is excluded from federal health care programs, from the HHS OIG List of Excluded Individuals/Entities, by name or NPI."},
    "openpayments": {"label": "Open Payments", "description": "CMS Open Payments: the payments drug and device companies reported to a physician or practitioner, found by name and state or NPI; the records for a program year (general, research as recipient or principal investigator, ownership) and totals by year, for conflict-of-interest review. No key."},
    "propublica": {"label": "Nonprofit Explorer", "description": "A tax-exempt organization by name or EIN, its IRS status and its Form 990 revenue, expenses, assets and liabilities by year, from ProPublica."},
    "ror": {"label": "Research Organization Registry", "description": "The ROR id, names, location, type, relationships and Crossref Funder, GRID, ISNI and Wikidata ids of a research organization, by name or affiliation string."},
    "scorecard": {"label": "College Scorecard", "description": "The Department of Education's institution facts: institutions by name, state, city, control or degree level; one institution's control, Carnegie and locale codes, accreditor, minority-serving flags, enrollment, Pell rate, cost and outcomes.",
                  "key": {"required": True, "hint": "Paste your api.data.gov key, from https://api.data.gov/signup/ (the same key as perdiem, fac and regulations)."}},
    "perdiem": {"label": "GSA per diem", "description": "Federal lodging and M&IE rates by city, state or zip for a fiscal year, and the M&IE meal breakdown.",
                "key": {"required": True, "hint": "Paste your api.data.gov key, free from https://api.data.gov/signup/ (DEMO_KEY works for a few calls an hour)."}},
    "bls": {"label": "BLS", "description": "Bureau of Labor Statistics CPI and ECI series for budget escalation rates; a key is optional.",
            "key": {"required": False, "hint": "Optional: paste your BLS registration key (free at data.bls.gov/registrationEngine) for 500 queries a day instead of the shared 25."}},
    "treasury": {"label": "Treasury exchange rates", "description": "The Treasury Reporting Rates of Exchange, the government's quarterly rates for converting foreign currency on a federal award: the currencies, a currency's rates by quarter, and a foreign amount in dollars at the rate in effect on the transaction's date. No key."},
    "osm": {"label": "OpenStreetMap", "description": "OpenStreetMap's public services: a place by name with its coordinates (Nominatim) and a walking, cycling or driving route between two points with turn-by-turn steps (the FOSSGIS Valhalla server). No key; one call a second, fair use, attribution required."},
    "weather": {"label": "Weather", "description": "The National Weather Service for a point in the United States: the seven-day forecast by half-day or 48 hours by the hour, the latest observation at the nearest station, and the watches, warnings and advisories in force. No key; a campus point comes from the campusmap server."},
    "wolfram": {"label": "Wolfram|Alpha", "description": "Wolfram|Alpha with the person's own AppID: a computed answer with Wolfram's interpretation of the question beside it, or one line for the main result, for arithmetic, unit and currency conversions, dates and durations, statistics, and scientific facts and formulas, so a number is checked by a tool rather than recalled.",
                "key": {"required": True, "hint": "Paste your Wolfram|Alpha AppID, from https://developer.wolframalpha.com/ (free for non-commercial use, 2,000 calls a month)."}},
    "openalex": {"label": "OpenAlex", "description": "Publications by author, institution, funder or award number, counted by year, funder, institution or topic; one work by DOI with its abstract; what cites a work and what it cites; authors, institutions and funders by name. A key is optional.",
                 "key": {"required": False, "hint": "Optional: paste your OpenAlex API key (free at openalex.org/settings/api) to spend your own $1-a-day budget instead of the $0.10 everyone without a key shares."}},
    "pubmed": {"label": "PubMed", "description": "Papers by grant number, author or affiliation with PMID, DOI and PMCID for NIH public access compliance; one paper's abstract, MeSH terms and grant acknowledgments; PMID/PMCID/DOI conversion.",
               "key": {"required": False, "hint": "Optional: paste an NCBI API key (free from your NCBI account settings) for 10 requests a second instead of the shared 3."}},
    "icite": {"label": "NIH iCite", "description": "Citation metrics for PubMed papers by PMID: citations, the Relative Citation Ratio and its NIH percentile, translation measures, and the papers citing or cited by one. No key."},
    "crossref": {"label": "Crossref", "description": "Publications by words, author or funder with the funding acknowledgments publishers deposited, one work by DOI with its abstract, whether a work has been retracted or corrected (from publishers' notices and the Retraction Watch database), and funders in the Funder Registry."},
    "datacite": {"label": "DataCite", "description": "The DOIs of datasets, software and other research outputs by institution (ROR), funder, award number, type or words, with creators, funding and the paper each supplements; one DOI's record in full. No key."},
    "re3data": {"label": "re3data", "description": "The Registry of Research Data Repositories: repositories by words, subject, content type, country, access terms, identifier system or certificate, each with its registry record, for choosing where a plan's data goes; one repository by id. No key."},
    "orcid": {"label": "ORCID", "description": "A researcher's ORCID iD by name and institution, and their public record: employments, educations, funding with grant numbers, and works with DOIs."},
    "osti": {"label": "OSTI.GOV", "description": "What a DOE award reported: papers, technical reports, data and software in OSTI by contract number, author, institution or words."},
    "clinicaltrials": {"label": "ClinicalTrials.gov", "description": "Clinical studies by condition, intervention, sponsor or status, and one study's registration and results dates, grant ids and design."},
    "wikidata": {"label": "Wikidata", "description": "Wikidata, the structured knowledge base behind Wikipedia: an entity by name, its statements with properties and values resolved to labels (who influenced whom, a school's members, dates, works, positions, places, the identifiers that join to ORCID and ROR), and a read-only SPARQL query for list questions. No key; the query quota is shared."},
    "perseus": {"label": "Perseus", "description": "The Perseus Digital Library's Greek and Latin texts through the Scaife Viewer: the library's authors and corpora, an author's works, a work's versions (the original and its translations) with their tables of contents, a passage by CTS URN as plain text and the same reference in another version, and a search of the library for a word. No key."},
    "clickup": {"label": "ClickUp", "description": "Your ClickUp, with your own token: who you are, your workspaces, spaces, folders and lists, and your tasks across the workspace, in a list or by id. Read only unless the deployment turns writes on.",
                "key": {"required": True, "hint": "Paste your ClickUp personal API token (avatar, Settings, Apps, Generate API Token; it starts with pk_). It acts as you."}},
}


# One lakehouse server per configured client (AI4RA_MCP_LAKEHOUSE_CLIENTS): each its own fold and its own secret.
for _name, _client in lakehouse.CLIENT_OF.items():
    META[_name] = {"label": "Lakehouse" if len(lakehouse.CLIENT_OF) == 1 else f"Lakehouse ({_client})", "institution": UIDAHO,
                   "description": f"The University of Idaho data lakehouse (Marina) as client {_client}: the streams it may query, their tables and columns, rows filtered or aggregated, and the files a stream may read. Read only.",
                   "key": {"required": True, "hint": f"Paste the shared secret issued with the lakehouse client id {_client} by Research Computing and Data Services; or, to run as another client, its id, a colon and its secret (other-client:its-secret)."}}


class BearerKeyMiddleware:
    """Reads `Authorization: Bearer <token>` and makes it this request's upstream key (see
    common.http.request_key). The token is held for the request only and never logged. With AI4RA_MCP_LOG_HEADERS=1
    (the one logging switch) every request is one WARNING line: method, path, whether an Authorization header
    arrived and was accepted (and why not), its fields as received with the credential redacted
    (common.http.describe_auth) and the names of the headers present, so a deployment can set a call that worked beside one that did not; no credential and
    no other header's value is ever written."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        token = None
        if scope["type"] == "http":
            headers = scope.get("headers") or []
            auth = "absent"
            for name, value in headers:
                if name == b"authorization":
                    raw = value.decode("latin-1")
                    v = raw.strip()
                    if v[:7].lower() == "bearer " and v[7:].strip():
                        token = v[7:].strip()
                    if log_headers():
                        fields, reason = describe_auth(raw)
                        auth = f"accepted {fields}" if token else f"rejected ({reason}) {fields}"
                    break
            if log_headers():
                headers_log.warning("%s %s: authorization %s; headers: %s", scope.get("method"), scope.get("path"), auth,
                                    ", ".join(n.decode("latin-1") for n, _ in headers) or "none")
        reset = request_key.set(token)
        try:
            await self.app(scope, receive, send)
        finally:
            request_key.reset(reset)


def _transport_security() -> TransportSecuritySettings:
    """Behind a reverse proxy the Host header is the public name, so DNS-rebinding
    protection is off unless AI4RA_MCP_HOSTS lists the names to allow."""
    hosts = [h.strip() for h in os.environ.get("AI4RA_MCP_HOSTS", "").split(",") if h.strip()]
    if hosts:
        return TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=["*"])
    return TransportSecuritySettings(enable_dns_rebinding_protection=False)


README = Path(__file__).parent.parent / "README.md"
# What the whole is, for a model reading the index for the first time; the search first, since a model that searches the web
# for "MindRouter" finds an unrelated inference gateway and its single-provider search (#33).
ABOUT = ("ai4ra-mcp: one process of MCP servers for research administration, each over one public upstream or one institution's own (the eCFR, grants.gov, NIH, NSF, SAM.gov, the University of Idaho's policies, class schedule and lakehouse, the person's ClickUp), with guides and skills a model follows and no client's document tools. Its web_search is a SearXNG metasearch beside the process that merges Google, Bing, DuckDuckGo, Brave, Startpage and more under strict safe search and a server-side blocklist: not a single provider's search. The whole account is README.md at this index's root.")


def build_app(only: list[str] | None = None) -> Starlette:
    names = only or list(SERVERS)
    unknown = [n for n in names if n not in SERVERS]
    if unknown:
        raise SystemExit(f"unknown server {', '.join(unknown)}; choose from {', '.join(SERVERS)}")
    log_no_keys()
    security = _transport_security()
    routes, mounted = [], []
    for name in names:
        server = SERVERS[name]
        skills = SERVERS_DIR / name / "skills"
        if skills.is_dir():
            routes.append(Mount(f"/{name}/skills", app=StaticFiles(directory=str(skills)), name=f"{name}-skills"))
        routes.append(Mount(f"/{name}", app=server.streamable_http_app(json_response=True, stateless_http=True, transport_security=security)))
        mounted.append(name)

    async def index(_request):
        out = []
        for name in (n for n in mounted if n not in UNLISTED):
            tools = await SERVERS[name].list_tools()
            prompts = await SERVERS[name].list_prompts()
            meta = META.get(name, {})
            out.append({"name": name, "label": meta.get("label", name), "institution": meta.get("institution"), "description": meta.get("description", ""),
                        # Relative to this index, so they resolve under whatever prefix a proxy mounts the server at.
                        "mcp": f"{name}/mcp", "skills": f"{name}/skills/catalog.json", "skills_base": f"{name}/skills/",
                        "web": f"{WEB}{name}/skills/", "key": meta.get("key"),
                        "tools": [t.name for t in tools], "prompts": [p.name for p in prompts],
                        # Which arguments name a thing the server holds and which tool lists the values (common.given, #40).
                        "given": given_of(SERVERS[name])})
        return JSONResponse({"v": 1, "description": ABOUT, "readme": "README.md", "servers": out})

    async def readme(_request):
        return FileResponse(README, media_type="text/markdown; charset=utf-8")

    routes.append(Route("/", index))
    routes.append(Route("/README.md", readme))

    @asynccontextmanager
    async def lifespan(_app):
        async with AsyncExitStack() as stack:
            for name in mounted:
                await stack.enter_async_context(SERVERS[name].session_manager.run())
            yield

    middleware = [Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], expose_headers=["Mcp-Session-Id"]),
                  Middleware(BearerKeyMiddleware)]
    return Starlette(routes=routes, lifespan=lifespan, middleware=middleware)


def main() -> None:
    parser = argparse.ArgumentParser(prog="ai4ra-mcp", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default=os.environ.get("AI4RA_MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AI4RA_MCP_PORT", "8000")))
    parser.add_argument("--only", action="append", metavar="NAME", help="mount only this server (repeatable)")
    parser.add_argument("--stdio", metavar="NAME", help="run one server over stdio instead of HTTP")
    args = parser.parse_args()
    log_no_keys()
    if args.stdio:
        if args.stdio not in SERVERS:
            raise SystemExit(f"unknown server {args.stdio}; choose from {', '.join(SERVERS)}")
        SERVERS[args.stdio].run("stdio")
        return
    import uvicorn

    uvicorn.run(build_app(args.only), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
