# ai4ra-mcp

One repository, one process, several MCP servers. Each server is one upstream
and one audience, mounted at its own path and complete on its own, so a client
adds only the ones it wants. The federal servers know nothing about any
institution; the University of Idaho server knows only Idaho. They share a
codebase, a deployment and the plumbing underneath (HTTP client, cache, page
reader), and nothing else.

A server carries the tools that act on its upstream and the skills that know
how to use those tools, or, for the `ai4ra` server, skills alone. A client
that speaks MCP gets both together; a client that reads skill catalogs by URL
gets the same files as static content. Everything a client needs that does not
touch its own document lives here: the Office add-in keeps only the tools that
read and write cells, paragraphs and slides.

## The servers

| Path | Upstream | Tools | Skills |
|---|---|---|---|
| `/general/mcp` | the open web | `web_search`, `fetch_document` | `ask`, `remove-ai-tells`, `project-timeline-gantt` (Excel) |
| `/ai4ra/mcp` | none: skills only | none | `rfa-sheet`, `proposal-narrative`, `work-plan`, `budget-outline`, `budget-nsf`, `pi-memo`, and seventeen cost-allowability and budget-justification prompts copied from AI4RA/prompt-library |
| `/ecfr/mcp` | ecfr.gov | `ecfr_regulatory_index`, `ecfr_search`, `ecfr_list_titles`, `ecfr_list_agencies`, `ecfr_get_title_versions`, `ecfr_get_regulation`, `ecfr_get_title_structure`, `ecfr_compare_regulations` | `ecfr-research-admin` |
| `/fedreg/mcp` | Federal Register | `federal_register_index`, `federal_register_search`, `federal_register_document`, `federal_register_agencies` | none |
| `/regulations/mcp` | Regulations.gov (key) | `regulations_gov_index`, `regulations_gov_documents_search`, `regulations_gov_document`, `regulations_gov_docket`, `regulations_gov_comments_search` | none |
| `/grants/mcp` | grants.gov | `grants_gov_search`, `grants_gov_opportunity` | `funding-opportunity-finder` |
| `/nih/mcp` | NIH RePORTER | `nih_index`, `nih_projects_search`, `nih_project`, `nih_publications` | `funding-history` |
| `/nsf/mcp` | NSF Award Search | `nsf_index`, `nsf_awards_search`, `nsf_award`, `nsf_award_outcomes` | none |
| `/usaspending/mcp` | usaspending.gov | `usaspending_index`, `usaspending_recipients`, `usaspending_recipient`, `usaspending_awards_search`, `usaspending_subawards_search`, `usaspending_award` | none |
| `/sam/mcp` | SAM.gov (key) | `sam_index`, `sam_entity`, `sam_exclusions_search`, `sam_assistance_listing`, `sam_assistance_listings_search` | `subrecipient-check` |
| `/fac/mcp` | Federal Audit Clearinghouse (key) | `fac_index`, `fac_audits_search`, `fac_findings`, `fac_federal_awards` | none |
| `/csl/mcp` | trade.gov Consolidated Screening List (key) | `csl_index`, `csl_search`, `csl_sources` | none |
| `/oig/mcp` | HHS OIG LEIE (a CSV download) | `oig_leie_index`, `oig_leie_search`, `oig_leie_status` | none |
| `/propublica/mcp` | ProPublica Nonprofit Explorer | `propublica_nonprofit_index`, `propublica_nonprofit_search`, `propublica_nonprofit_organization` | none |
| `/ror/mcp` | Research Organization Registry | `ror_index`, `ror_search`, `ror_organization` | none |
| `/perdiem/mcp` | GSA per diem rates (key) | `gsa_perdiem_index`, `gsa_perdiem_rates`, `gsa_perdiem_mie_breakdown` | none |
| `/bls/mcp` | Bureau of Labor Statistics (optional key) | `bls_index`, `bls_series`, `bls_common_series` | none |
| `/openalex/mcp` | OpenAlex | `openalex_index`, `openalex_works_search`, `openalex_work`, `openalex_authors_search`, `openalex_institutions_search`, `openalex_funders_search` | none |
| `/pubmed/mcp` | NCBI E-utilities and the PMC ID converter (optional key) | `pubmed_index`, `pubmed_search`, `pubmed_summary`, `pmc_id_convert` | none |
| `/crossref/mcp` | Crossref | `crossref_index`, `crossref_works_search`, `crossref_work`, `crossref_funders_search` | none |
| `/orcid/mcp` | ORCID public API | `orcid_index`, `orcid_search`, `orcid_record` | none |
| `/osti/mcp` | OSTI.GOV | `osti_index`, `osti_search`, `osti_record` | none |
| `/clinicaltrials/mcp` | ClinicalTrials.gov | `clinicaltrials_index`, `clinicaltrials_search`, `clinicaltrials_study` | none |
| `/uidaho/mcp` | uidaho.edu | `uidaho_guidance_index`, `uidaho_guidance_search`, `uidaho_guidance_get`, `uidaho_rates` | `uidaho-lookup`, `uidaho-rates`, `award-facts`, `award-lines`, `award-status`, `award-review`, `pi-awards`, `current-pending`, `current-pending-support`, `proposal-workbook` |
| `/lakehouse/mcp` (one per client) | the University of Idaho lakehouse, Marina (key) | `lakehouse_index`, `lakehouse_streams`, `lakehouse_schema`, `lakehouse_query`, `lakehouse_files`, `lakehouse_file` | `lakehouse-answer` |

The index at `/` lists the servers in this order, which is the order a
client's picker shows them: general first, then the research-administration
skills, then the public upstreams grouped by the job they serve (the rules
and announcements, the awards held, the vetting lists, the budget figures,
the scholarly record), and last the one institution's own servers.

The `general` server is what belongs to no single upstream and no one
profession: a web search and the page reader (search for an address you do
not have, then read it; other servers' skills use the reader for attachments
and linked documents) and the skills any office uses with any document. The
`ai4ra` server has no tools: it is the research-administration skills that
work with a client's own document tools. Anything that can be shared lives on
one of these two; the `uidaho` server holds only what is the University of
Idaho's (its policies and rates, the rates as a Rates sheet when asked, the award skills
that read its Banner exports, and the proposal workbook whose steps run
skills from all three).

### general

`web_search` is answered by a SearXNG instance next to this process, a
self-hosted metasearch that merges Google, Bing, DuckDuckGo, Brave, Startpage
and Wikipedia with no key; the compose file runs it as a second container on
the compose network only, with `deploy/searxng/settings.yml` (JSON output on,
limiter off). `AI4RA_MCP_SEARXNG_URL` names it (default
`http://127.0.0.1:8080`). Results carry title, address, snippet and the
engines that found them; an engine that is rate-limiting drops out and the
tool says so. When the backend is down the tool answers with a plain error
that points at `fetch_document` for an address already in hand. Results are
cached for an hour.

Guardrails, all on the server so no client can loosen them: SearXNG runs with
strict safe search (the engines' own filters) and offers only the text
categories general, news, science and it; the tool pins safe search on every
request, refuses a query that contains a blocklisted word, drops any result
whose address, title or snippet matches the blocklist and reports how many
it dropped. The blocklist covers adult, gambling and piracy terms as whole
words or domain fragments; `AI4RA_MCP_SEARCH_BLOCK` adds more, comma
separated.

A client's connector URL is the server's path on the host, for example
`https://<host>/ecfr/mcp`. A client that reads catalogs names the index
instead and gets every server at once; another institution runs the process
with `--only` for the servers it wants, leaves out `uidaho`, and adds
whatever it builds for itself. `GET /` is the index: `{"v": 1, "servers": [...]}`, one
entry per mounted server with its `name`, `label`, `description`, the paths
`mcp`, `skills` (the catalog) and `skills_base` (relative to the index, so
they resolve under whatever prefix a proxy mounts the server at), a `web`
link to the skills
folder on GitHub, `key` (null, or `{"required", "hint"}` when the server
wants the person's own key), and its `tools` and `prompts`. A client that
reads the index adds every server in one step and sees a new one the day it
is deployed; the Office add-in does this from one `indexes` entry in its
sources file.

Tool names carry their upstream (`ecfr_`, `grants_gov_`, `uidaho_`) and
nothing else; a client shows them as they are.

### ai4ra

Skills only. The proposal sheets (`rfa-sheet`, `proposal-narrative`,
`work-plan`, `budget-outline`, `budget-nsf`) and `pi-memo` were written for
the Office add-in and moved here on 2026-09-22; each catalog entry's `source`
says so. `budget-nsf` is institution-agnostic: its template ships no rates,
and the skill reads them from a sheet named Rates when the workbook has one
(seven fixed-label rows: Location, F&A rate, F&A base, Fringe faculty, Fringe
staff, Fringe students, Fringe temporary, and a Source row), writes the
Source row beside the rates as provenance, and estimates a rate the sheet
lacks, filled yellow and marked so. An institution provides the Rates
sheet with a skill of its own; `uidaho-rates` is Idaho's, and writes the sheet only when the request names one (the proposal workbook's Rates step does).

The other seventeen components are copies of AI4RA/prompt-library at commit
`eef6fd3d818037ab51ece87f61806c448d51f40d`, files unchanged, each catalog
entry carrying a `source` with the repository, commit and path. They are not
edited here: a change goes to the prompt library and is copied in again at a
new commit.

### ecfr

The tools and their rules are unchanged from mcp-ecfr: read the index first,
get a valid date from the title's versions before fetching text, give the
title explicitly because part numbers repeat across titles, prefer sections
over parts. The regulatory index, a resource in mcp-ecfr, is a tool here as
well, because most clients never list resources.

### grants

`grants_gov_search` finds announcements; `grants_gov_opportunity` fetches one
record by the id a hit carries, with its synopsis, dates, ceiling, cost
sharing, eligibility and attachment links. An attachment is read with
`fetch_document` on the `general` server.

### uidaho

The policy site is plain HTML with a stable address scheme, which is what
makes a search-and-cite layer cheap:

| Source | Landing page | A policy | Header fields |
|---|---|---|---|
| APM | `uidaho.edu/policies/apm` lists chapters 01–95 (45 is Research Office) | `uidaho.edu/policies/apm/45/06` is APM 45.06 | Owner (position, email), `Last updated: <Month D, YYYY>` |
| FSH | `uidaho.edu/policies/fsh` lists chapters 1–6 (5 is Research Policies) | `uidaho.edu/policies/fsh/5/5100` is FSH 5100 | same |

- `uidaho_guidance_index`: read first. Both sources chapter by chapter with
  URLs, starter citations for sponsored-projects work (APM 45.06 allowable
  costs, 45.08 cost sharing, 45.10 F&A rate, 45.15 subawards, FSH 5100
  general research policy), where the rate documents are, and the usage rules.
- `uidaho_guidance_search`: policies by number or title words, as listed in
  each chapter's index. It does not search policy text; the skill reads a
  likely policy and looks there.
- `uidaho_guidance_get`: one policy as clean text by number (`APM 45.06`,
  `FSH 5100`), with its owner, `Last updated` date and URL, in pages.
- `uidaho_rates`: the F&A rate agreement PDF (`fa`) or the fringe-rate page
  (`fringe`) as text. The agreement is read at the address the F&A page
  links today, so a new agreement is picked up the day it is posted, with
  the last known address as the fallback and the result saying which was
  used; the fringe read returns only the page's fringe section. Every result
  carries the address it was read from.

Chapter lists and policy text are cached for a day: revisions are rare and
the page carries its own date. A number with no page is reported as a 404
with no guessing.

The skills follow the same rule, decided 2026-09-23: nothing from memory.
`uidaho-lookup` answers a policy or rate question from what the tools
return, with the address of every figure and passage, and gives no figure
for a page that could not be read. `uidaho-rates` fetches the F&A and fringe
rates and reports them with their dates and addresses; when the request
names a sheet (the proposal workbook's Rates step does), it writes them
onto it in the layout the budget form reads, and a document that could not
be read leaves its rows without values, marked "not fetched". Neither skill
carries fallback figures.

### lakehouse

The University of Idaho data lakehouse through Marina, its query and file
API at `http://nlayman.nkn.uidaho.edu:7010` (`AI4RA_MCP_LAKEHOUSE_URL`),
reachable on campus, which is why this process reads it and a browser never
does. Every request needs an OAuth 2.0 bearer from `/auth/token`, minted with
HTTP Basic from a client id (`AI4RA_MCP_LAKEHOUSE_CLIENT`, default `mr-365`)
and that client's shared secret. The secret is the key a person pastes into
the pane, sent as the bearer on the MCP call, exchanged here for a Marina
token that is kept in memory until it expires and never logged;
`AI4RA_MCP_LAKEHOUSE_SECRET` is a deployment's fallback. It is one client's
secret, not a personal key, so its rate limits (100 requests a minute, 1,000
an hour) are shared by everyone who uses it.

Marina authorizes a client for streams, and a secret belongs to one client,
so each client is its own server here: its own path, its own fold in the
pane, its own key. `AI4RA_MCP_LAKEHOUSE_CLIENTS` lists the client ids to
mount, comma separated; the first is mounted at `lakehouse`, the rest at
`lakehouse-<id>`, with `AI4RA_MCP_LAKEHOUSE_SECRET_<ID>` as each one's
fallback. Today one client is configured, `mr-365`, against the Marina at
`nlayman.nkn.uidaho.edu`, whose streams the tools discover (`personnel`
is one). A different Marina is `AI4RA_MCP_LAKEHOUSE_URL` in the VM's
`.env`; all instances share the same tools and the same skills folder.

Marina scopes access by stream: a client is authorized for querying streams,
each of which exposes a set of tables through a wrapper view (columns masked,
rows filtered, some filters required) and a set of files by tag, and for
submitting streams that accept records and files. `lakehouse_streams` lists
both; `lakehouse_schema` gives a querying stream's tables and columns;
`lakehouse_query` reads one table with Marina's own filter syntax (equality,
`gte`, `in`, `ilike`, `is_null` and the rest), paging with a total count,
and grouped aggregates (COUNT, SUM, AVG, MIN, MAX); `lakehouse_files` and
`lakehouse_file` read a stream's file catalog and one file as text. Rows are
capped at 500 and 30,000 characters a call. Nothing is written: the
submitting streams are listed but not used, because a remote write would run
behind no confirmation card in the pane. The `lakehouse-answer` skill is the
way a question is answered: streams first, then the schemas, then a filtered
or aggregated query, every figure with its stream, table, filters and date.

### nih

NIH RePORTER, https://api.reporter.nih.gov/ v2, no key, about one request a
second. Projects by PI name, organization, fiscal years, activity codes,
institutes or text; one project by number with its abstract; a project's
publications by core project number, as PubMed ids. RePORTER returns one
record per fiscal year and one per component of a center grant, and the index
tool says how to read that. Searches are cached for an hour, records for a
day.

### nsf

NSF Award Search, https://api.nsf.gov/services/v1/, no key, 25 a page and
3,000 for one query. Awards by keyword, PI, awardee, program or start date;
one award by id with its abstract and program officer; the project outcomes
report. Dates are MM/DD/YYYY both ways.

### sam

SAM.gov, https://api.sam.gov/: entities and exclusions (entity-information
v4) and Assistance Listings (v1). One key covers all three, and it is the
person's own: the client sends it as a bearer token on each call, and the
Office pane keeps it beside the gateway key and sends it to this server only.
**The daily quota is per key:** 10 requests for a personal key without a role
in SAM.gov, 1,000 with a role or a non-federal system account. The index tool
says whether the request carried a key and how many requests this process
has made. An entity by
UEI, CAGE or name with its registration status and dates; active exclusions
by name or UEI; one Assistance Listing by number with its eligibility, the
2 CFR 200 subparts that apply, reporting, audit, matching and contacts;
listings by agency code, status or date. The listings API has no keyword
search. Entities and listings are cached for a day, exclusions for an hour.

### usaspending

USAspending, https://api.usaspending.gov/api/v2/, no key: the public record
of federal awards and of the subawards primes report under them (FFATA,
$30,000 and up). A recipient's profile carries the former names it is filed
under, which is how an entity renamed since its older awards is found in
the other portals. Awards an entity held as the prime and the subawards it
received, by name or UEI, largest first within the last ten fiscal years
by default, one award-type group per search (grants, other assistance,
contracts); one award's record by its generated id, with its subaward count.
Subawards received are the one public evidence of experience as a
subrecipient, which 2 CFR 200.332(b)(1) asks about. Profiles and records are
cached for a day, searches for an hour.

### fac

The Federal Audit Clearinghouse, https://api.fac.gov, a PostgREST API over
the public single-audit data. A free api.data.gov key, the person's own,
sent by the client as a bearer token and forwarded as `X-Api-Key`. Audits
by auditee name, UEI or EIN, newest first, with the auditor, opinion, the
flags a risk assessment reads (going concern, material weakness, material
noncompliance, low-risk auditee) and total federal expenditure; the findings
of one report with their text; its schedule of federal awards by program. The
`subrecipient-check` skill on the sam server reads both servers.

### fedreg

The Federal Register, https://www.federalregister.gov/api/v1/, no key. The
daily journal where a Rule (a final regulation with an effective date), a
Proposed Rule (asks for comments first) and a Notice (funding opportunities,
information collections, meetings) are published. Documents by words, type,
agency slug, CFR title and part, publication dates and significance, newest
first, 1-50 a page, each with its number, action, dates, agencies, abstract,
CFR parts, docket ids, RINs and links; one document by number with its
citation, page count, the regulations.gov docket it is filed under and the
full-text HTML, XML and text urls, but not the body (`fetch_document` on the
general server reads the link); the agency list with the slug a search needs,
cached a day. Searches are cached an hour, documents a day. The index tells
the model that 2 CFR 200 changes are OMB rules here (slug
`management-and-budget-office`, the Register's own slugs, not the agency's
name), that NOFOs are Notices, that `comments_close_on` is the deadline, that
dates are YYYY-MM-DD, and to cite the link and publication date.

### regulations

Regulations.gov, https://api.regulations.gov/v4/, a JSON:API over the public
rulemaking dockets. A free api.data.gov key, the person's own, sent by the
client as a bearer token and forwarded as `X-Api-Key`; `AI4RA_MCP_REGULATIONS_KEY`
is a deployment's fallback. **The limit is 1,000 requests an hour per key**,
and DEMO_KEY is shared by everyone and good for a handful. Documents by words,
type (Notice, Proposed Rule, Rule, Supporting & Related Material, Other),
agency id, docket, posted dates or only those open for comment, newest first,
5-250 a page and at most 20 pages of one search; one document with its dates,
files (PDF, HTML), CFR part and the Federal Register number the fedreg server
reads for the text; one docket with its type, abstract and RIN; the public
comments on a document or in a docket. Searches are cached an hour, records a
day. The index tells the model that comments are filtered by the document's
`object_id`, not its document id, that timestamps are UTC and date filters
YYYY-MM-DD, and to cite the link on each record.

csl: META "csl": {"label": "Consolidated Screening List", "description": "Export-control and sanctions screening of a name against the BIS, OFAC and State lists (Entity List, SDN, Denied Persons, ITAR debarred and the rest).", "key": {"required": True, "hint": "Paste your trade.gov subscription key, from https://developer.trade.gov/ (subscribe to the Consolidated Screening List API)."}}
tools: csl_index, csl_search, csl_sources
row: | `/csl/mcp` | trade.gov Consolidated Screening List (key) | `csl_index`, `csl_search`, `csl_sources` | none |
env: AI4RA_MCP_CSL_KEY

oig: META "oig": {"label": "OIG exclusions (LEIE)", "description": "Whether a person or business is excluded from federal health care programs, from the HHS OIG List of Excluded Individuals/Entities, by name or NPI."}
tools: oig_leie_index, oig_leie_search, oig_leie_status
row: | `/oig/mcp` | HHS OIG LEIE (a CSV download) | `oig_leie_index`, `oig_leie_search`, `oig_leie_status` | none |

propublica: META "propublica": {"label": "Nonprofit Explorer", "description": "A tax-exempt organization by name or EIN, its IRS status and its Form 990 revenue, expenses, assets and liabilities by year, from ProPublica."}
tools: propublica_nonprofit_index, propublica_nonprofit_search, propublica_nonprofit_organization
row: | `/propublica/mcp` | ProPublica Nonprofit Explorer | `propublica_nonprofit_index`, `propublica_nonprofit_search`, `propublica_nonprofit_organization` | none |

ror: META "ror": {"label": "Research Organization Registry", "description": "The ROR id, names, location, type, relationships and Crossref Funder, GRID, ISNI and Wikidata ids of a research organization, by name or affiliation string."}
tools: ror_index, ror_search, ror_organization
row: | `/ror/mcp` | Research Organization Registry | `ror_index`, `ror_search`, `ror_organization` | none |

### csl

The Consolidated Screening List at
https://data.trade.gov/consolidated_screening_list/v1/search, trade.gov's
merge of the thirteen export-control and sanctions lists of Commerce (Entity
List, Denied Persons, Unverified, Military End User), Treasury (SDN, SSI, FSE,
CMIC, NS-MBS, PLC, Capta) and State (ITAR debarred, nonproliferation),
refreshed hourly. A free subscription key from developer.trade.gov, sent as
the `subscription-key` header; the person's own as a bearer token, or
`AI4RA_MCP_CSL_KEY` as a deployment's fallback. `csl_search` screens a name,
fuzzy by default, narrowed by list codes, countries or type (Individual,
Entity, Vessel, Aircraft), 50 a page by offset; each hit carries its list
code, programs, addresses, ids, dates, license terms and the source's own
page as the link. `csl_sources` is the static table of the thirteen lists,
their agencies and what a listing means. Searches are cached an hour. The
index says this is separate from SAM.gov exclusions and the OIG LEIE, that a
fuzzy hit is a lead to verify against addresses and ids rather than a
verdict, to search the exact name and every alias one at a time, and to cite
the list, the OFAC entity_number (or the CSL id on BIS and State records) and
the source_list_url.

### oig

The HHS Office of Inspector General's List of Excluded Individuals/Entities,
which has no API: the server downloads the whole list from
https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv (15 MB, about
84,000 rows) on the first search of the day, streams it into memory behind
one lock so concurrent first calls download once, and searches it there for
a day. No key. `oig_leie_search` matches every word of a name, in any order,
against the business name or the person's last, first and middle names, or
an NPI exactly, narrowed by state or exclusion authority; each row comes
back with the name, specialty, NPI, city, state, the section 1128 code and
its meaning (1128(a) mandatory, 1128(b) permissive, plus 1128A(a), 1156,
1160 and the breach codes), the exclusion, reinstatement and waiver dates as
YYYY-MM-DD, when this copy was downloaded, and a link to OIG's online search.
`oig_leie_status` says whether the list is loaded, its row count and its
download time. The index says the LEIE check is required of anyone paid with
HHS funds and of their contractors and subrecipients (42 CFR 1001.1901), that
a name match is a lead to confirm by NPI and on OIG's online search, and that
OIG updates the list monthly while this copy is refreshed daily.

### propublica

ProPublica's Nonprofit Explorer API v2 at
https://projects.propublica.org/nonprofits/api/v2/, the IRS Business Master
File and Form 990 extracts for every tax-exempt organization. No key.
`propublica_nonprofit_search` finds organizations by name, narrowed by state,
NTEE category (1-10) or IRS subsection (3 for 501(c)(3)), 25 a page from page
0, each with EIN, city, state, NTEE code, the subsection spelled out and a
link to its page. `propublica_nonprofit_organization` takes an EIN with or
without the hyphen and returns the IRS record (address, subsection, ruling
date, latest tax period) and up to ten filings newest first, each with the
year, form, total revenue, expenses, assets, liabilities, net assets,
contributions and the PDF, plus the years of filings without extracted data.
Searches are cached an hour, records a day. The index says this is Form 990
data, so a public university or government unit may not appear and absence
is not a finding; that revenue and expenses are the organization's whole
year; and that the single-audit threshold in 2 CFR 200.501 is federal
expenditure, not revenue, so this is context and the audit check is the fac
server.

### ror

The Research Organization Registry API v2 at
https://api.ror.org/v2/organizations, the persistent identifiers ORCID,
OpenAlex, Crossref and DataCite use for institutions. No key. `ror_search`
finds organizations by name, narrowed by country code and type, 20 a page
from page 1; with `affiliation=True` it instead matches a whole affiliation
line as written on a paper or CV and returns the candidates scored, with
`chosen` on the one ROR is confident of. Each organization carries its ROR
id, display name, aliases, acronyms and other-language labels, types, status,
country, region and city, founding year, domains, website, its ids in other
registries grouped by type (fundref is the Crossref Funder Registry id, plus
grid, isni, wikidata) and its parent, child and related organizations.
`ror_organization` takes the full https://ror.org/xxxx or the bare id.
Searches are cached an hour, records a day. The index says departments and
labs have no ROR id (the university does), that a subaward goes to the legal
entity which may be the parent, and that an inactive record names its
successor in its relationships.

perdiem: META "perdiem": {"label": "GSA per diem", "description": "Federal lodging and M&IE rates by city, state or zip for a fiscal year, and the M&IE meal breakdown.", "key": {"required": True, "hint": "Paste your api.data.gov key, free from https://api.data.gov/signup/ (DEMO_KEY works for a few calls an hour)."}}
tools: gsa_perdiem_index, gsa_perdiem_rates, gsa_perdiem_mie_breakdown
row: | `/perdiem/mcp` | GSA per diem rates (key) | `gsa_perdiem_index`, `gsa_perdiem_rates`, `gsa_perdiem_mie_breakdown` | none |
env: AI4RA_MCP_PERDIEM_KEY

bls: META "bls": {"label": "BLS", "description": "Bureau of Labor Statistics CPI and ECI series for budget escalation rates; a key is optional.", "key": {"required": False, "hint": "Optional: paste your BLS registration key (free at data.bls.gov/registrationEngine) for 500 queries a day instead of the shared 25."}}
tools: bls_index, bls_series, bls_common_series
row: | `/bls/mcp` | Bureau of Labor Statistics (optional key) | `bls_index`, `bls_series`, `bls_common_series` | none |
env: AI4RA_MCP_BLS_KEY (optional)

### perdiem

GSA per diem rates, https://api.gsa.gov/travel/perdiem/v2/, the lodging and
M&IE ceilings for travel within the continental US. A free api.data.gov key,
the person's own, sent by the client as a bearer token and forwarded as the
`api_key` query param. Rates for a city and state, a whole state (every
listed location plus the standard rate) or a zip, for a federal fiscal year:
lodging per night by month with its low and high, M&IE per day, and a
standard-rate flag; the year's M&IE tiers with breakfast, lunch, dinner,
incidentals and the first-and-last-day (75 percent) amount. A city GSA does
not list comes back as the standard-rate row with a note saying so. Answers
are cached a day. The index tells the model that years are fiscal years
(October to September), that only CONUS is here, and to cite year and
location with the GSA per diem page.

### bls

The Bureau of Labor Statistics Public Data API, https://api.bls.gov/publicAPI/,
the CPI and ECI series an escalation rate rests on. No key is needed: v1
allows 25 queries a day per IP, shared by everyone on the server, 10 years
and 25 series a query. A free registration key, sent as a bearer token, moves
the server to v2 with 500 a day, 20 years, 50 series and series titles; the
index says which is in use. `bls_series` takes ids and a span of years and
returns each series' points newest first (year, period, value, latest flag)
with BLS's message list, where it reports a missing series or a reached
threshold. `bls_common_series` is the table of ids a budget justification
uses: CPI-U all items (national, seasonally adjusted, West region), CPI
medical care, CPI college tuition, and the ECI 12-month changes for total
compensation and wages. Answers are cached a day to spare the quota. The
index tells the model the rate is 100 * (new - old) / old from two points a
year apart, that ECI 'A' series are already percent changes, and to say
which series and periods it used.

openalex: META "openalex": {"label": "OpenAlex", "description": "Publications by author, institution, funder or award number, one work by DOI with its abstract, and authors, institutions and funders by name."}
tools: openalex_index, openalex_works_search, openalex_work, openalex_authors_search, openalex_institutions_search, openalex_funders_search
row: | `/openalex/mcp` | OpenAlex | `openalex_index`, `openalex_works_search`, `openalex_work`, `openalex_authors_search`, `openalex_institutions_search`, `openalex_funders_search` | none |

crossref: META "crossref": {"label": "Crossref", "description": "Publications by words, author or funder with the funding acknowledgments publishers deposited, one work by DOI with its abstract, and funders in the Funder Registry."}
tools: crossref_index, crossref_works_search, crossref_work, crossref_funders_search
row: | `/crossref/mcp` | Crossref | `crossref_index`, `crossref_works_search`, `crossref_work`, `crossref_funders_search` | none |

orcid: META "orcid": {"label": "ORCID", "description": "A researcher's ORCID iD by name and institution, and their public record: employments, educations, funding with grant numbers, and works with DOIs."}
tools: orcid_index, orcid_search, orcid_record
row: | `/orcid/mcp` | ORCID public API | `orcid_index`, `orcid_search`, `orcid_record` | none |

### openalex

OpenAlex, https://api.openalex.org/, no key; a `mailto` on every call puts
the server in the polite pool, about one request a second. Works newest
first by author, institution (OpenAlex id or ROR), funder, award number,
years, type or words, with the first ten authors, journal, open-access copy,
the funders and award numbers the publisher deposited, and citation count;
one work by DOI or OpenAlex id with its abstract put back together from the
inverted index and its reference count; authors by name with ORCID, counts,
last known institutions and top topics; institutions and funders by name,
a funder with its Crossref Funder Registry id and 10.13039 DOI. Ids are URLs
and the tools take either form. The index tells the model that the award
filter takes the number as the funder writes it (NSF 1754803) and that a
prefixed form is tried both ways, that missing grants mean none deposited,
and to cite the DOI. Searches are cached for an hour, works for a day; 50
a page at most.

### pubmed

NCBI's E-utilities for PubMed (`esearch`, `esummary` at
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/) and the PMC ID converter
(https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/). No key is
needed: NCBI allows 3 requests a second to everyone without one, and an
optional NCBI key (`AI4RA_MCP_PUBMED_KEY`, or the person's own as a bearer
token) is sent as `api_key` for 10. `pubmed_search` takes a PubMed query
with its fields (`AI135270[Grant Number]`, `University of Idaho[Affiliation]`,
`Smith J[Author]`) and an optional publication date range, and returns each
paper's citation, PMID, DOI, PMCID and PubMed link, newest first, 1-50 a page.
`pubmed_summary` gives the same for PMIDs already in hand (up to 50), such as
the ids NIH RePORTER's `nih_publications` returns. `pmc_id_convert` takes up
to 200 PMIDs, PMCIDs and DOIs in any mix, converts among them (one idconv call
per id type, since the API takes one type a call) and says which have no
PMCID. Every call carries `tool=ai4ra-mcp` and, when `AI4RA_MCP_CONTACT` is an
email address, `email=` that address (idconv rejects a URL there). Searches
are cached an hour, summaries and conversions a day. The index tells the model
that NIH public access (NOT-OD-25-047, effective July 1 2025) needs a PMCID
for every peer-reviewed paper arising from NIH funding, so a paper with a PMID
and no PMCID is the one to chase; that grant searches use the institute code
and serial (`AI135270[Grant Number]`; the RePORTER form `R01AI135270` finds
nothing); and to cite the PubMed link.

### crossref

The Crossref REST API, https://api.crossref.org/, no key; a `mailto` on
every call puts the server in the polite pool. Works by words, author name
or Funder Registry id, with years and type, most relevant first: DOI, title,
authors (ORCID and affiliations when deposited), journal, year, publisher,
volume, issue, pages, the funders with their award numbers, and citation
count; one work by DOI, exact and free, with its abstract (JATS stripped),
license URLs, ISSN and reference count; funders by name with the registry
id, its alternate names and location. The registry id is the one Crossref,
OpenAlex and ROR share, and its DOI is 10.13039/<id>. Crossref keeps titles
as lists and dates as date-parts; the tools flatten both. The index tells
the model that a work's funders are what the publisher deposited, that
author matching is by words, and to cite https://doi.org/<DOI>. Searches
are cached for an hour, records and funders for a day; 50 rows a page,
offset at most 10,000.

### orcid

The ORCID public API v3.0, https://pub.orcid.org/v3.0/, no key for public
reads. Researchers by given names, family name and affiliation (a Solr query
built from the parts, or a raw one), through the expanded search that gives
each hit's names, institutions and public emails in one call, so finding an
iD costs one request; one record by iD, the public parts only: names, other
names, biography, emails, keywords, URLs, employments and educations with
organization, department, role and dates (no end date means current),
fundings with type, organization, dates and grant numbers, and the works
(count, and the first 25 with title, type, year, journal and DOI). The iD is
checked for shape and its ISO 7064 MOD 11-2 check digit before any call.
The index tells the model that an empty section means unpublished, not
none; that given names match the registered form (Lucas, not Luke); that
the record is self-asserted unless a source such as Crossref added the
entry; and to cite https://orcid.org/<iD>. Searches are cached for an hour,
records for a day; 50 hits a page.

### osti

OSTI.GOV, the Department of Energy's record of the research results its
awards reported (https://www.osti.gov/api/v1/records). No key; every request
sends `Accept: application/json`, since the default answer is XML.
`osti_search` takes words, an author, a DOE contract number (`SC0019327`; a
leading `DE-` is dropped), a research organization, a sponsoring office, a
publication date range (MM/DD/YYYY) and a product type (Journal Article,
Technical Report, Dataset, Conference, ...), 1-50 rows a page, and returns each
record's OSTI id, title, authors, date, product and article type, journal,
DOI, DOE and other contract numbers, research and sponsor organizations,
report number, the citation and full-text links and the biblio link; the total
comes from the `X-Total-Count` response header, so the server has a small
local `_get` on httpx that returns body and headers. `osti_record` is one
record with its abstract, subjects and availability. OSTI rate-limits
aggressively (a 429, or a dropped connection, on a second quick request), so
the server sends one request at a time behind a lock, caches searches an hour
and records a day, and turns a dropped connection into a plain "wait a
minute" answer. The index tells the model that DOE award terms require
accepted manuscripts, reports and data to be in OSTI under the award's
contract number, so `doe_contract` is the search for "what did this award
report"; the product types; the date formats; the pace; and to cite the OSTI
link and the DOI.

### clinicaltrials

ClinicalTrials.gov's API v2 (https://clinicaltrials.gov/api/v2/). No key.
`clinicaltrials_search` takes a condition, intervention, free words, sponsor
(lead or collaborator), location and a comma list of statuses (validated
against the registry's values), 1-50 a page with a page token for the next,
asks for a compact field list and returns each study's NCT id, titles, status,
start, primary completion and completion dates, first-submitted and
results-first-submitted dates, study type, phases, lead sponsor and class,
collaborators, conditions, interventions, enrollment, whether results are
posted, and the study link, with the total count. `clinicaltrials_study`
takes an NCT number (NCT plus eight digits) and slims the whole protocol
section: secondary ids (an NIH grant number appears here with type NIH),
posting dates and whether each date is actual or estimated, responsible party,
brief summary, design, arms, eligibility (criteria cut at 2,000 characters),
site count and first ten sites, contacts, oversight (FDA-regulated drug or
device, DMC), the IPD sharing statement, and whether a results section is
present. Searches are cached an hour, studies a day. The index tells the model
that NIH-funded trials must be registered within 21 days of first enrollment
and have results submitted within a year of primary completion (42 CFR 11,
NOT-OD-16-149), which dates to compare, the status values, the sponsor
classes, and to cite the study link.


## Rules

- **Tools act.** A tool does one mechanical thing against one upstream and
  reports what it found. Which policy or regulation applies to a budget line
  is judgment, and judgment lives in a skill, never in a tool.
- **One server, one upstream, one audience.** Everything that reads ecfr.gov
  is one server; everything that reads uidaho.edu is another. A federal
  server has no Idaho defaults; the Idaho server hard-codes uidaho.edu.
  Shared code is plumbing only. Two servers are the exceptions, by design:
  `general` is the place for what belongs to no upstream, and `ai4ra` is
  the research-administration skills that have no upstream at all.
- **Every server stands alone.** Each runs by itself over stdio or HTTP with
  nothing else present, and each has an index tool that tells a model how to
  use it. No server calls another server's tools; a skill may name another
  server's tool when the job needs it.
- **Skills stay with their tools.** A skill lives in the server whose tools it
  uses; a skill that uses only a client's own document tools lives on `ai4ra`
  (research administration) or `general` (any office). A skill that needs
  one client only says so with `hosts` in its catalog entry, and `fold:
  "host"` when that client should list it beside its own tools (the Gantt
  chart, in Excel).
- **Be a polite upstream client.** One `User-Agent` naming this project and a
  contact on every request; cache what does not change; on a 429, tell the
  model to wait rather than retrying blindly.

## Layout

```
ai4ra_mcp/
  app.py                      mounts /<server>/mcp and /<server>/skills/ for each; GET / lists them
  common/
    http.py                   User-Agent and contact, TTL cache
    fetch.py                  the page reader and grants.gov client (from mcp-ecfr)
    skills.py                 a skills folder as MCP prompts
  servers/
    ecfr/
      server.py               MCPServer("ecfr"): tools, the index resource, prompts
      skills/
        catalog.json          the components, in AI4RA/prompt-library's catalog shape
        components/<slug>/    prompt.md, README.md, CHANGELOG.md, evals/
    general/  ai4ra/  grants/  nih/  nsf/  sam/  fac/  usaspending/  uidaho/  lakehouse/   same shape (ai4ra has no tools)
    fedreg/  regulations/  csl/  oig/  propublica/  ror/  perdiem/  bls/          same shape, no skills yet
    openalex/  pubmed/  crossref/  orcid/  osti/  clinicaltrials/
deploy/
  Caddyfile                   a site block that fronts the process
  ai4ra-mcp.service           a systemd unit
  Dockerfile
tests/                        offline: every server lists its tools and prompts, the app mounts, CORS answers, the Idaho parsers
```

`notes/` and `admin/` are ignored by git and are for private working files.

### Adding a server

A folder under `ai4ra_mcp/servers/<name>/` with a `server.py` that builds one
`MCPServer` named `<name>`, registers its tools with read-only annotations,
and ends by calling `register_prompts` on its `skills/` folder. Add it to
`SERVERS` in `app.py` and to the expected tools in the tests. Its README
section above says what upstream it reads and what its index tool tells the
model.

### Adding a skill

A folder under the server's `skills/components/<slug>/` with `prompt.md`
(YAML front matter, a preamble with **Purpose**, **Expected input** and
**Expected output**, the prompt under `## Prompt`), `README.md`,
`CHANGELOG.md` and `evals/`, and an entry in that server's `catalog.json`.
The server serves it as an MCP prompt named by its slug and as static files
under `/<server>/skills/`. A skill goes on the server whose tools it uses;
one that uses only a client's document tools goes on `ai4ra` (research
administration) or `general` (any office); one that is one institution's
goes on that institution's server. Bump the version in the front matter and
the catalog together: a client caches the prompt text by version.

The catalog entry follows AI4RA/prompt-library's shape (`slug`, `summary`,
`version`, `category`, `status`, `paths`, `contracts.output.format`,
`evaluation`) and adds the fields a client acts on:

| Field | What it says |
|---|---|
| `requires` | The tools the skill calls: a tool name here (`uidaho_rates`), or `<host>:<name>` for a client's own tool (`excel:write_values`) |
| `triggers` | Words in a request that point at the skill |
| `hosts` | The clients the skill is offered in (`["excel"]`); absent means all |
| `fold` | `"host"` lists the skill beside that client's own tools instead of in this server's fold (the Gantt chart, in Excel) |
| `paths.template` | A `template.json` the client lays down before the skill runs: a sheet of values, formats, `locked` ranges and `from_context` cells |
| `assertions` | The skill's definition of done, tested by the client on its output sheet: `[{address, rule, min, max, value, of, sheet, label}]` |
| `stages` | For a workflow, the table of steps: `[{name, skill, context, sources, required_tools}]`; a step's skill may live on any server |
| `source` | Where a copied or moved component came from: repository, commit, path |

**The Rates sheet contract.** A budget form skill is institution-agnostic:
it takes its rates from a sheet named Rates when the workbook has one. An
institution's rates skill writes that sheet with a header row (Item, Value,
Basis, Effective, Source, Link), then seven rows with these labels in column
A: Location, F&A rate, F&A base, Fringe faculty, Fringe staff, Fringe
students, Fringe temporary, values as fractions, each with the address it
was read from; reference rows after them; and a last row labelled Source,
one line naming the documents, their periods and their addresses, which the
form copies beside its rates as provenance. A rate the skill could not read
is a row with its label and no value, marked "not fetched", never a figure
from memory. The form estimates a rate the sheet lacks, fills it yellow and
marks it "estimate", so the highlight means exactly that. `uidaho-rates`
is Idaho's: it fetches and reports the rates, and writes the sheet when the
request names one; another institution writes its own to the same labels.

## Running

```
uv sync
uv run ai4ra-mcp                   # every server on http://127.0.0.1:8000/<name>/mcp
uv run ai4ra-mcp --only uidaho     # a subset (repeatable)
uv run ai4ra-mcp --stdio ecfr      # one server over stdio, for a local MCP client
uv run pytest                      # offline tests
```

Each server is an `MCPServer` from the official Python SDK (mcp 2.x). The
process mounts each one's streamable-HTTP app at its path, stateless and
answering in JSON, and runs their session managers under one lifespan.
Streamable HTTP is the only network transport.

**Keys.** A keyed server (sam, fac, regulations, csl, perdiem) takes its
upstream key from its environment variable; bls and pubmed take an optional
one that raises their quota. A client may instead send its own key as
`Authorization: Bearer <key>` on the MCP request; for that request it is used
in place of the server's, so a person can spend their own quota rather than
the institution's. The token is held for the request only and never logged.
A request with no key gets a plain "no API key on this request" answer from
every tool of that server, saying to send one and telling the model to stop
there rather than answer from memory or a web search (a per diem question
once got invented figures that way); the server still mounts.

Environment: `AI4RA_MCP_SEARXNG_URL`, the web search backend; `AI4RA_MCP_HOST` and `AI4RA_MCP_PORT` (defaults 127.0.0.1 and
8000); `AI4RA_MCP_CONTACT`, the address in the User-Agent and the `mailto` that
OpenAlex, Crossref and NCBI ask for (set it to an email address: a URL earns
no polite pool and idconv rejects it); `AI4RA_MCP_SAM_KEY`, `AI4RA_MCP_FAC_KEY`,
`AI4RA_MCP_REGULATIONS_KEY`, `AI4RA_MCP_CSL_KEY`, `AI4RA_MCP_PERDIEM_KEY`,
`AI4RA_MCP_BLS_KEY` and `AI4RA_MCP_PUBMED_KEY`, optional fallback keys a
deployment may hold for requests that send none (the design is per-user keys
sent by the client, so most deployments set none); `AI4RA_MCP_HOSTS`,
a comma-separated list of public hostnames to allow, which turns the SDK's
DNS-rebinding protection on (off by default, since a reverse proxy in front
sets the Host header to the public name).

## Hosting

The intended host is a VM behind Caddy with a campus certificate, the same
arrangement the mindrouter-365 demo uses. Caddy terminates TLS and
reverse-proxies the server paths to the process on localhost. On a host
that already runs its services as containers, `docker compose up -d --build`
at the repo root does the same for this one, bound to localhost with restart
unless-stopped, and brings up SearXNG beside it (set `SEARXNG_SECRET` in a
`.env` file next to the compose file); otherwise a systemd unit keeps the
process up and SearXNG is yours to run. `deploy/ai4ra-mcp.user.service` runs it as a user
service with no sudo, under the account that cloned the repo (lingering
enabled once so it survives logout); `deploy/ai4ra-mcp.service` is the
system-wide form for an administrator to install. The Dockerfile is for anyone who
would rather run it elsewhere.

Clients such as the Office add-in call these servers from inside a browser
engine, so the process answers CORS itself: any origin, any method, and the
`Mcp-Session-Id` header exposed. Public content needs nothing narrower. A
server that must be reachable only on campus (a future one that reads an
internal system) is a Caddy rule and a firewall, not a code branch.

The demo deployment: the repository cloned on the VM, `docker compose up -d
--build` for the process and SearXNG, and a `handle_path /mcp/*` block in
Caddy that forwards to port 8000, so the index is at `https://<host>/mcp/`
and each server at `https://<host>/mcp/<name>/mcp`. Shipping a change is a
commit, a pull on the VM and the same compose command; a client's Refresh
then re-reads the server's tools and skills. The eCFR server's earlier home,
a Hugging Face Space behind Gradio, is retired: it slept when idle, prefixed
every tool name, and was one more origin to trust.

## Connecting

- **Claude.ai:** Settings → Connectors → Add custom connector, with the
  server's URL, for example `https://<host>/ecfr/mcp`. One connector per
  server; its skills appear as prompts.
- **Claude Code:** `claude mcp add --transport http ecfr https://<host>/ecfr/mcp`.
- **mindrouter-365:** one `indexes` entry in the deployment's `sources.json`
  with the URL of `/`; the pane reads the index and lists every server as one
  fold holding its tools, skills and workflows, each with a Refresh that
  re-reads all three. A keyed server's index entry carries
  `"key": {"required": true, "hint": "..."}`; each person pastes their own
  key into that server's i dialog in the pane, which sends it as the bearer
  token on that server's calls and nowhere else.

## Status

2026-09-22: ten servers, deployed on the demo VM behind Caddy with SearXNG
beside it. The eCFR and grants.gov code moved in from mcp-ecfr; the NIH, NSF,
SAM.gov, USAspending and Federal Audit Clearinghouse servers are verified
against the live APIs (SAM.gov and FAC with a person's own key). The Office
add-in's skills moved here the same day: everything that does not touch the
document is served from this process. Not yet done: evals for the moved
skills, the SAM.gov integrity section, an FDP Clearinghouse reader.

## Related

- [AI4RA/mcp-ecfr](https://github.com/AI4RA/mcp-ecfr): the eCFR server this
  supersedes.
- [ui-insight/mindrouter-365](https://github.com/ui-insight/mindrouter-365):
  the Office add-in that is the first client. Its issues 17 (the split into
  pane, servers and deployment) and 23 (the University of Idaho server) are
  the design record for this repository.
- [AI4RA/prompt-library](https://github.com/AI4RA/prompt-library): the
  component and catalog shape the skills folders follow.
