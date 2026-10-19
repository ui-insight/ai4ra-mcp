# ai4ra-mcp

One repository, one process, twenty-nine MCP servers. Each server is one
upstream and one audience, mounted at its own path and complete on its own,
so a client adds only the ones it wants. The federal and scholarly servers
know nothing about any institution; the University of Idaho servers know only
Idaho. They share a codebase, a deployment and the plumbing underneath (HTTP
client, cache, page reader, key handling), and nothing else.

A server carries the tools that act on its upstream and the skills that know
how to use those tools, or, for the `ai4ra` server, skills alone. A client
that speaks MCP gets both together; a client that reads skill catalogs by URL
gets the same files as static content. Everything a client needs that does not
touch its own document lives here: the Office add-in keeps only the tools that
read and write cells, paragraphs and slides.

Every tool is read-only. Nothing here writes to an upstream.

**Contents**

- [The servers](#the-servers): every server, its path, its upstream, whether it needs a key, its tools and skills
- [How the API works](#how-the-api-works): the index, the MCP endpoints, the skills files, a worked session
- [Keys](#keys): which servers need one, where to get it, how a person submits it from each client, what a request without one gets
- [Server reference](#server-reference): what each server reads, what its tools return, what its index tool tells the model
- [Skills](#skills): the catalog shape, the fields a client acts on, the Rates sheet contract
- [Running](#running), [Environment](#environment), [Hosting](#hosting), [Connecting a client](#connecting-a-client)
- [Rules](#rules), [Layout](#layout), [Adding a server](#adding-a-server), [Adding a skill](#adding-a-skill)
- [Status](#status), [Related](#related), [Contributing](#contributing), [License](#license), [Acknowledgments](#acknowledgments)

## The servers

The index at `/` lists the servers in this order, which is the order a
client's picker shows them: general first, then the research-administration
skills, then the public upstreams grouped by the job they serve, and last the
one institution's own servers. A **Key** of *required* means every tool of
that server answers "no API key on this request" until the person's own key
arrives as a bearer token (see [Keys](#keys)); *optional* means the server
works without one and a key raises its quota.

**General and skills**

| Path | Upstream | Key | Tools | Skills |
|---|---|---|---|---|
| `/general/mcp` | the open web, through a SearXNG beside the process | none | `web_search`, `fetch_document`, `general_guide` | `ai-tells-guide` (the guide) |
| `/ai4ra/mcp` | none: guides and prompts | none | `ai4ra_guide` | the guides `rfa-guide`, `narrative-guide`, `work-plan-guide`, `budget-outline-guide`, `nsf-budget-guide`, `compliance-concerns-guide`, and seventeen cost-allowability, extraction and budget-justification prompts copied from AI4RA/prompt-library |
| `/udm/mcp` | the AI4RA Unified Data Model's published schema (ui-insight.github.io/AI4RA-UDM) | none | `udm_index`, `udm_schema`, `udm_guide` | `udm-conversion-guide` (the guide) |

**Rules and announcements**

| Path | Upstream | Key | Tools | Skills |
|---|---|---|---|---|
| `/ecfr/mcp` | ecfr.gov | none | `ecfr_guide`, `ecfr_regulatory_index`, `ecfr_search`, `ecfr_list_titles`, `ecfr_list_agencies`, `ecfr_get_title_versions`, `ecfr_get_regulation`, `ecfr_get_title_structure`, `ecfr_compare_regulations` | `cfr-check` |
| `/fedreg/mcp` | Federal Register | none | `federal_register_index`, `federal_register_search`, `federal_register_document`, `federal_register_executive_order`, `federal_register_agencies` | none |
| `/regulations/mcp` | Regulations.gov | **required** (api.data.gov) | `regulations_gov_index`, `regulations_gov_documents_search`, `regulations_gov_document`, `regulations_gov_docket`, `regulations_gov_comments_search` | none |
| `/idstat/mcp` | the Idaho Statutes at legislature.idaho.gov and the Legislature's search of them | none | `idstat_index`, `idstat_titles`, `idstat_chapters`, `idstat_sections`, `idstat_section`, `idstat_search` | none |
| `/govinfo/mcp` | GovInfo (Government Publishing Office) | **required** (api.data.gov) | `govinfo_index`, `govinfo_collections`, `govinfo_search`, `govinfo_package`, `govinfo_text` | none |
| `/congress/mcp` | Congress.gov | **required** (api.data.gov) | `congress_index`, `congress_bill`, `congress_bill_actions`, `congress_bills`, `congress_laws`, `congress_members` | none |
| `/grants/mcp` | grants.gov | none | `grants_gov_search`, `grants_gov_opportunity`, `grants_guide` | `funding-opportunity-finder` |
| `/s2s/mcp` | the Grants.gov Applicant System-to-System (S2S) SOAP service, at any endpoint: training, production, or the deployment's default (a mock) | optional (the person's own S2S certificate and key as a bearer bundle; a deployment may hold a fallback that only the mock accepts) | `s2s_index`, `s2s_check`, `s2s_opportunity`, `s2s_validate_package`, `s2s_submissions`, `s2s_application_info`; with `AI4RA_MCP_S2S_WRITES=1` also `s2s_submit` (off by default) | none yet |

**Awards held**

| Path | Upstream | Key | Tools | Skills |
|---|---|---|---|---|
| `/pappg/mcp` | the NSF PAPPG (NSF 24-1) at nsf.gov/policies/pappg | none | `pappg_index`, `pappg_chapters`, `pappg_outline`, `pappg_section`, `pappg_search` | none |
| `/nihgps/mcp` | the NIH Grants Policy Statement, web edition at grants.nih.gov | none | `nihgps_index`, `nihgps_toc`, `nihgps_section`, `nihgps_search` | none |
| `/nihguide/mcp` | the NIH Guide for Grants and Contracts: its search service, notice pages and weekly index | none | `nihguide_index`, `nihguide_search`, `nihguide_notice`, `nihguide_weekly` | none |
| `/nihdates/mcp` | grants.nih.gov's standard due dates and salary cap pages | none | `nihdates_index`, `nihdates_due`, `nihdates_cycles`, `nihdates_salary_cap` | none |
| `/omb/mcp` | OMB's memoranda page on whitehouse.gov and the archived prior-administration page | none | `omb_index`, `omb_memoranda`, `omb_memorandum` | none |
| `/ncura/mcp` | NCURA's public event listing (cvweb) behind its calendar page | none | `ncura_index`, `ncura_events`, `ncura_event` | none |
| `/nih/mcp` | NIH RePORTER | none | `nih_guide`, `nih_index`, `nih_projects_search`, `nih_project`, `nih_publications` | `funding-history` |
| `/nsf/mcp` | NSF Award Search | none | `nsf_index`, `nsf_awards_search`, `nsf_award`, `nsf_award_outcomes` | none |
| `/usaspending/mcp` | USAspending | none | `usaspending_index`, `usaspending_recipients`, `usaspending_recipient`, `usaspending_awards_search`, `usaspending_subawards_search`, `usaspending_award` | none |

**Vetting a partner**

| Path | Upstream | Key | Tools | Skills |
|---|---|---|---|---|
| `/sam/mcp` | SAM.gov | **required** (SAM.gov personal key) | `sam_guide`, `sam_index`, `sam_entity`, `sam_exclusions_search`, `sam_assistance_listing`, `sam_assistance_listings_search` | `subrecipient-check` |
| `/fac/mcp` | Federal Audit Clearinghouse | **required** (api.data.gov) | `fac_index`, `fac_audits_search`, `fac_findings`, `fac_federal_awards` | none |
| `/csl/mcp` | trade.gov Consolidated Screening List | **required** (trade.gov subscription key) | `csl_index`, `csl_search`, `csl_sources` | none |
| `/openpayments/mcp` | CMS Open Payments (DKAN datastore) | none | `openpayments_index`, `openpayments_recipients`, `openpayments_payments`, `openpayments_summary` | none |
| `/oig/mcp` | HHS OIG LEIE, from its daily CSV | none | `oig_leie_index`, `oig_leie_search`, `oig_leie_status` | none |
| `/propublica/mcp` | ProPublica Nonprofit Explorer | none | `propublica_nonprofit_index`, `propublica_nonprofit_search`, `propublica_nonprofit_organization` | none |
| `/scorecard/mcp` | College Scorecard (Department of Education) | **required** (api.data.gov) | `scorecard_index`, `scorecard_search`, `scorecard_school` | none |
| `/ror/mcp` | Research Organization Registry | none | `ror_index`, `ror_search`, `ror_organization` | none |

**Budget figures**

| Path | Upstream | Key | Tools | Skills |
|---|---|---|---|---|
| `/perdiem/mcp` | GSA per diem | **required** (api.data.gov) | `gsa_perdiem_index`, `gsa_perdiem_rates`, `gsa_perdiem_mie_breakdown` | none |
| `/bls/mcp` | Bureau of Labor Statistics | optional (BLS registration key) | `bls_index`, `bls_series`, `bls_common_series` | none |

**The scholarly record**

| Path | Upstream | Key | Tools | Skills |
|---|---|---|---|---|
| `/treasury/mcp` | Treasury Reporting Rates of Exchange (Fiscal Data) | none | `treasury_index`, `treasury_currencies`, `treasury_rates`, `treasury_convert` | none |
| `/osm/mcp` | OpenStreetMap's Nominatim and the FOSSGIS Valhalla router | none (fair use, one call a second) | `osm_index`, `osm_geocode`, `osm_route` | none |
| `/weather/mcp` | The National Weather Service API | none | `weather_index`, `weather_forecast`, `weather_now`, `weather_alerts`, `weather_office` | none |
| `/wolfram/mcp` | Wolfram\|Alpha's LLM API and Short Answers API | **required** (the person's Wolfram\|Alpha AppID) | `wolfram_index`, `wolfram_ask`, `wolfram_answer` | none |
| `/openalex/mcp` | OpenAlex | optional (OpenAlex key) | `openalex_index`, `openalex_works_search`, `openalex_works_group`, `openalex_work`, `openalex_citations`, `openalex_authors_search`, `openalex_institutions_search`, `openalex_funders_search` | none |
| `/pubmed/mcp` | NCBI E-utilities and the PMC ID converter | optional (NCBI key) | `pubmed_index`, `pubmed_search`, `pubmed_summary`, `pubmed_article`, `pmc_id_convert` | none |
| `/icite/mcp` | NIH iCite | none | `icite_index`, `icite_metrics`, `icite_links` | none |
| `/crossref/mcp` | Crossref | none | `crossref_index`, `crossref_works_search`, `crossref_work`, `crossref_updates`, `crossref_funders_search` | none |
| `/datacite/mcp` | DataCite | none | `datacite_index`, `datacite_search`, `datacite_doi` | none |
| `/re3data/mcp` | re3data, the Registry of Research Data Repositories | none | `re3data_index`, `re3data_search`, `re3data_repository` | none |
| `/orcid/mcp` | ORCID public API | none | `orcid_index`, `orcid_search`, `orcid_record` | none |
| `/osti/mcp` | OSTI.GOV | none | `osti_index`, `osti_search`, `osti_record` | none |
| `/clinicaltrials/mcp` | ClinicalTrials.gov | none | `clinicaltrials_index`, `clinicaltrials_search`, `clinicaltrials_study` | none |

**Project trackers**

| Path | Upstream | Key | Tools | Skills |
|---|---|---|---|---|
| `/clickup/mcp` | ClickUp, as the person | **required** (ClickUp personal API token) | `clickup_index`, `clickup_whoami`, `clickup_tasks_search` (the whole workspace in one call: by assignee, status, space, list or tag), `clickup_workspace`, `clickup_tasks`, `clickup_task`, `clickup_list_fields` (a list's custom fields with a drop-down's options); with `AI4RA_MCP_CLICKUP_WRITES=1` also `clickup_task_create`, `clickup_task_update`, `clickup_task_comment`, `clickup_task_attach`, `clickup_task_field_set` (off by default: read only) | none yet (the skill that files a piece of mail into a project goes here; `feature-prd-interview` on `uidaho` writes through these tools) |

| `/github/mcp` | none: GitHub's own remote MCP server holds the tools | none (the key is GitHub's server's) | `github_guide` | `code-change` (a described change as a pull request on an agent branch), `actions-check` (one look at the Actions runs); both name GitHub's tools in `requires` |

GitHub's tools are not served here: GitHub's own remote MCP server takes a
personal access token as a bearer, so the Office pane reaches it through a
proxy block on the pane's host (see mindrouter-365's README, "GitHub through
the proxy"), with its `context`, `issues` and `repos` toolsets and its
`get_me` whoami. The `github` server here holds only the two skills that
run over those tools, and its index entry carries `institution: "GitHub"`,
the value a client gives GitHub's own server, so the two fold together and
the skills stand beside the tools they call rather than under `general`
(2026-10-14; #42 holds the other shape, a keyed server over the REST API
with tools of its own). ClickUp's hosted MCP server is OAuth only, which the
pane cannot do (mindrouter-365 issue #27), hence a keyed server of our own
over ClickUp's REST API.

**University of Idaho**

| Path | Upstream | Key | Tools | Skills |
|---|---|---|---|---|
| `/uidaho/mcp` | uidaho.edu policy pages and rate documents | none | `uidaho_guide`, `uidaho_guidance_index`, `uidaho_guidance_search`, `uidaho_guidance_get`, `uidaho_rates`, `uidaho_salaries` | `uidaho-lookup`, `uidaho-rates`, `policy-check`, `feature-prd-interview` (with the `openera-feature-guide` guide; its writes go through the `clickup` server) |
| `/classes/mcp` | the registrar's public class schedule and course catalog (Browse Classes and Browse Course Catalog in Banner) | none | `classes_index`, `classes_terms`, `classes_search`, `classes_section`, `classes_catalog`, `classes_course` | none yet |
| `/directory/mcp` | the campus directory at directory.uidaho.edu, the employees the university publishes | none | `directory_index`, `directory_search`, `directory_person`, `directory_departments` | none yet |
| `/events/mcp` | the campus calendar at uidaho.edu/events, through its public Trumba feed | none | `events_index`, `events_search`, `events_closures`, `events_event`, `events_calendars` | none yet |
| `/campusmap/mcp` | the campus map, Concept3D map 2155, through its locations and categories API | none of the person's (the map page's own client key) | `campusmap_index`, `campusmap_categories`, `campusmap_search`, `campusmap_near`, `campusmap_place` | none yet |
| `/costs/mcp` | www.uidaho.edu's student billing, account payments, cost of attendance and SHIP pages | none | `costs_index`, `costs_tuition`, `costs_attendance`, `costs_deadlines`, `costs_insurance` | none |
| `/library/mcp` | the University of Idaho Library's catalog, Primo VE on the Orbis Cascade Alliance host, through the public search endpoint its own page uses | none | `library_index`, `library_search`, `library_record` | none |
| `/lakehouse/mcp` (one per configured client; the others at `/lakehouse-<id>/mcp`) | the University of Idaho data lakehouse, through Marina | **required** (the client's shared secret) | `lakehouse_guide`, `lakehouse_index`, `lakehouse_sql_catalog`, `lakehouse_sql`, `lakehouse_streams`, `lakehouse_schema`, `lakehouse_query`, `lakehouse_files`, `lakehouse_file` | `lakehouse-answer` |

Tool names carry their upstream (`ecfr_`, `grants_gov_`, `uidaho_`) and
nothing else; a client shows them as they are. Every server with skills
has a `<server>_guide` tool that lists them and returns one by name (see
[Skills](#skills)). Every server except `ai4ra`
has an index tool (`<upstream>_index`, or `ecfr_regulatory_index`) that a
model reads first: what the server offers, the tools in the order to use
them, the upstream's limits, the date formats and the citation rule. On
`ecfr` the index is reference, read when wanted: a question there starts
with a search (#28). A
server's `instructions` string, sent on `initialize`, says the same in a
sentence.

The `general` server is what belongs to no single upstream and no one
profession: a web search and the page reader (search for an address you do
not have, then read it; other servers' skills use the reader for attachments
and linked documents) and the skills any office uses with any document. The
`ai4ra` server has no tools: it is the research-administration skills that
work with a client's own document tools. Anything that can be shared lives on
one of these two; the `uidaho` and `lakehouse` servers hold only what is the
University of Idaho's.

## How the API works

One process serves every mounted server. There are three kinds of address:

| Address | What answers |
|---|---|
| `GET /` | The index: a JSON list of the mounted servers, for a client that adds them all at once |
| `POST /<name>/mcp` | The server's MCP endpoint, streamable HTTP, JSON-RPC 2.0 |
| `GET /<name>/skills/...` | The server's skills folder as static files: `catalog.json` and `components/<slug>/prompt.md`, `README.md`, `CHANGELOG.md`, `template.json` |

Behind a reverse proxy that mounts the process under a prefix, every address
carries the prefix: the demo deployment has the index at
`https://<host>/mcp/` and the eCFR server at `https://<host>/mcp/ecfr/mcp`.

### The index

`GET /` returns `{"v": 1, "description": "...", "readme": "README.md",
"servers": [...]}`. `description` is one paragraph for the whole: what
ai4ra-mcp is, and first that its search is a SearXNG metasearch and not a
single provider's, since a model that searched the web for "MindRouter"
found an unrelated inference gateway and drew that system (#33, 2026-10-07).
`readme` is the relative address of this file, served as `text/markdown` at
`/README.md`, so a client that reads pages by URL gets the server's own
account of itself and a model asked what the server is answers from it. Then
one entry per mounted server:

```json
{
  "name": "perdiem",
  "label": "GSA per diem",
  "institution": null,
  "description": "Federal lodging and M&IE rates by city, state or zip for a fiscal year, and the M&IE meal breakdown.",
  "mcp": "perdiem/mcp",
  "skills": "perdiem/skills/catalog.json",
  "skills_base": "perdiem/skills/",
  "web": "https://github.com/ui-insight/ai4ra-mcp/blob/main/ai4ra_mcp/servers/perdiem/skills/",
  "key": {"required": true, "hint": "Paste your api.data.gov key, free from https://api.data.gov/signup/ (DEMO_KEY works for a few calls an hour)."},
  "tools": ["gsa_perdiem_index", "gsa_perdiem_rates", "gsa_perdiem_mie_breakdown"],
  "prompts": [],
  "given": {}
}
```

The paths `mcp`, `skills` and `skills_base` are relative to the index, so
they resolve under whatever prefix a proxy mounts the process at. `key` is
`null` for a server that needs none, or `{"required", "hint"}`: `required`
true means the server refuses every tool call without one, false means a key
is optional and raises the quota; `hint` is the sentence a client shows
beside its key field. `tools` and `prompts` are the names the server lists.
A client that reads the index adds every server in one step and sees a new
server the day it is deployed; the Office add-in does this from one `indexes`
entry in its sources file.

`institution` is the source the server is about, when that source is one
organisation's own: `"University of Idaho"` on `uidaho`, `classes`, `directory`, `events`, `campusmap` and every
lakehouse server, whose upstreams are Idaho's own and which need Idaho's own
knowledge (the placement table's question); `"GitHub"` on `github`, whose
skills run over GitHub's own MCP server, so a client that gives that server
the same value folds the two together; `null` on every other server (#38,
widened 2026-10-14). It is a fact the server knows, so a client can gather
one source's servers under one heading, each still its own server with its
own key, tools and skills, and a server without it stands as it does today.
It is never a label for servers that share a job: "Screening lists" over
`sam`, `csl` and `oig` is a client's curation and no value of this field,
and "federal" over the public upstreams would be the same.

`given` is a fact about the shape of a correct call: for each tool whose
arguments name a thing the server holds, which arguments those are and
which tool on the same server lists their values. The class schedule's
entry says

```json
"given": {
  "classes_search": {"term": "classes_terms"},
  "classes_section": {"term": "classes_terms", "crn": "classes_search"},
  "classes_catalog": {"term": "classes_terms"},
  "classes_course": {"term": "classes_terms"}
}
```

A client that checks calls can hold one whose identifier neither the person
nor an earlier tool result gave until the listing tool has run (mindrouter-365
#72: asked for full details on two sections it had searched, a model called
`classes_section` with a CRN that appeared nowhere in the conversation, and
the server, which cannot know what the model should have read, answered for
that section). A value the person typed passes as typed: a term named "Fall
2026" resolves, a UEI or a DOI pasted from a letter is given. Left out is
anything a person expects a model to infer, a subject code from "biology" or
a CFR citation from a rule's name. The field is empty for a server with no
such argument; it names no client and says nothing about the order of work.
Each server states its table beside its tools with `given` from
`common/given.py`, and `tests/test_servers.py` holds every entry to a tool
and argument the server lists and a listing tool on the same server (#40).

### The MCP endpoint

Each `/<name>/mcp` is a streamable-HTTP MCP server from the official Python
SDK (mcp 2.x), mounted stateless and answering in plain JSON rather than an
event stream, so a client needs no session and a proxy needs no special
handling. The protocol is JSON-RPC 2.0 over POST; the methods a client uses
are `initialize`, `tools/list`, `tools/call`, `prompts/list` and
`prompts/get`. Every tool is annotated read-only (`readOnlyHint` true,
`destructiveHint` false).

A session with curl, against a local process:

```sh
# What the server is and how to use it
curl -s http://127.0.0.1:8000/ecfr/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'

# The tools, with their descriptions and input schemas
curl -s http://127.0.0.1:8000/ecfr/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

# One call
curl -s http://127.0.0.1:8000/ecfr/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ecfr_get_regulation","arguments":{"title":2,"part":"200","section":"200.403"}}}'

# A keyed server: the person's key rides as a bearer token
curl -s http://127.0.0.1:8000/perdiem/mcp \
  -H 'Authorization: Bearer YOUR_API_DATA_GOV_KEY' \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"gsa_perdiem_rates","arguments":{"city":"Boise","state":"ID","year":2026}}}'
```

A tool's answer is one text content block holding JSON. A successful answer
is the slimmed record with a `link` on every item, so the model can cite it.
A problem the tool can name (bad input, an upstream 404, a rate limit, no
key) comes back as `{"error": "..."}` in that same block with `isError`
false: the call worked, the answer is a refusal the model can read and act
on. An unknown tool, arguments that fail the tool's schema, or an exception
a tool did not catch come back from the SDK as a result with `isError` true
and the message as text.

The process answers CORS itself, since the Office add-in calls it from
inside a browser engine: any origin, any method, any header, with
`Mcp-Session-Id` exposed. Public content needs nothing narrower.

### The skills files

`/<name>/skills/catalog.json` lists the server's components in the shape of
AI4RA/prompt-library's `component_catalog.json`; each component's files are
under `/<name>/skills/components/<slug>/`. The same components are also
registered on the MCP server as prompts named by their slug, so a client that
speaks MCP gets `prompts/list` and `prompts/get` with the prompt text (the
`prompt.md` body without its front matter), and a client that reads catalogs
by URL gets the same files unchanged. See [Skills](#skills) for the catalog
fields.

### stdio

`ai4ra-mcp --stdio <name>` runs one server over stdio for a local MCP client
(Claude Desktop, Claude Code) with no network. The bearer-token path does not
exist there; a keyed server takes its key from the environment variable
instead.

## Keys

Thirteen servers talk to an upstream that wants a key, and one more wants a
shared secret. **The key is the person's own**, sent by their client as
`Authorization: Bearer <key>` on each MCP request, and it is used for that
request only: held in a request-scoped variable, never logged, never stored.
Quotas are per key at every one of these upstreams, so this is how a person
spends their own allowance rather than the institution's, and how a
deployment holds no secrets at all.

| Server | Key | Where a person gets one | Quota | Sent upstream as |
|---|---|---|---|---|
| `sam` | required | The account details page of their own SAM.gov account (a personal API key) | 10 requests a day with no role in SAM.gov; 1,000 with a role or a non-federal system account | `api_key` query parameter |
| `fac` | required | api.data.gov, through the FAC API signup at https://www.fac.gov/api/ (free; an email address is all it asks) | api.data.gov's default, 1,000 an hour | `X-Api-Key` header |
| `regulations` | required | https://api.data.gov/signup/ (free); `DEMO_KEY` works for a handful of requests an hour and is shared by everyone | 1,000 requests an hour per key | `X-Api-Key` header |
| `perdiem` | required | https://api.data.gov/signup/ (free); `DEMO_KEY` works for a few calls an hour | api.data.gov's default, 1,000 an hour | `api_key` query parameter |
| `govinfo` | required | https://api.data.gov/signup/ (free), the same key | api.data.gov's default, 1,000 an hour | `X-Api-Key` header |
| `congress` | required | https://api.congress.gov/sign-up/ (free, an api.data.gov key) | api.data.gov's default, 1,000 an hour (Congress.gov says 5,000 a day) | `X-Api-Key` header |
| `scorecard` | required | https://api.data.gov/signup/ (free), the same key | api.data.gov's default, 1,000 an hour | `X-Api-Key` header |
| `csl` | required | https://developer.trade.gov/ : sign up, subscribe to the Consolidated Screening List API, copy the subscription key | trade.gov's per-subscription limit | `subscription-key` header |
| `wolfram` | required | https://developer.wolframalpha.com/ : sign in with a Wolfram ID, Get an AppID, choose the LLM API, copy it (the AppID is the whole credential). Free for non-commercial use; the terms are the person's to meet | 2,000 calls a month on a free AppID (every call to either tool is one); paid tiers above | `Authorization: Bearer <AppID>` header, the form the LLM API documents; Short Answers accepts it too, and the one AppID answers both |
| `bls` | optional | https://data.bls.gov/registrationEngine/ (free) | 25 queries a day per IP without one (v1, shared by everyone on the server), 500 with one (v2), plus longer spans and series titles | `registrationkey` in the POST body |
| `pubmed` | optional | The settings page of an NCBI account, https://account.ncbi.nlm.nih.gov/settings/ (free) | 3 requests a second without one, shared; 10 with one | `api_key` query parameter |
| `openalex` | optional | https://openalex.org/settings/api (free) | OpenAlex meters by a daily budget rather than a rate (since February 2026): $0.10 a day shared by everyone on the server's network address without one, $1 a day of the person's own with one; a list call costs $0.0001, a text search $0.001, one record by id nothing | `api_key` query parameter |
| `clickup` | required | ClickUp: click your avatar, Settings, Apps, Generate API Token (starts with `pk_`). It acts as you in every workspace you belong to, so a task it creates is created by you | 100 requests a minute per token | Raw in the `Authorization` header, the way ClickUp wants it (the server takes the bearer the client sent and re-sends it that way) |
| `lakehouse` | required | The shared secret issued with the lakehouse client id (today `mr-365`) by Research Computing and Data Services; or another client's id, a colon and its secret (`other-client:its-secret`) to run as that client. It is one client's secret, not a personal key, so its limits (100 requests a minute, 1,000 an hour) are shared by everyone who uses it | per client | Exchanged at Marina's `/auth/token` for an OAuth bearer, kept in memory until it expires |

One api.data.gov key works for `fac`, `regulations`, `perdiem`, `govinfo`,
`congress` and `scorecard` alike; a person pastes the same key into each of
those six servers.

### How a person submits a key, by client

- **The Office add-in (mindrouter-365).** The pane reads the index and shows
  each keyed server with an *i* dialog holding a key field and the server's
  `hint`. The person pastes their key there once; the pane keeps it beside
  the gateway key in the add-in's own storage and sends it as the bearer
  token on that server's calls and nowhere else. Each person's key is their
  own; the deployment holds none.
- **Claude Code.** Add the header when adding the server:
  `claude mcp add --transport http perdiem https://<host>/perdiem/mcp --header "Authorization: Bearer <key>"`.
- **curl, a script, any HTTP client.** Set the `Authorization: Bearer <key>`
  header on the POST, as in the session above.
- **Claude.ai.** A custom connector has no per-user key field: its own
  key mechanisms are OAuth (each person signs in) and, in beta for a limited
  set of organizations, *Request headers*, where whoever adds the connector
  enters a fixed header once and Claude.ai sends it on every request for
  everyone in the organization. For a keyed server here, that is one
  connector per server with authentication *No sign-in* and a request
  header `authorization` whose value is `Bearer`, two spaces, then the
  key: a single space typed into Claude.ai's value field is removed, so
  that value arrives as `Bearer<key>` in one word and the server sees no
  scheme (seen 2026-10-15 by the request log, the header's form
  `'Bearer<token:40>'`; reported to Anthropic the same day), while two
  typed spaces both arrive and the server strips them; the key is then shared by the
  organization on a Team or Enterprise plan, and the person's own on a
  Free, Pro or Max plan. The headers cannot be edited after the connector
  is added, only removed and re-added. Without that beta, a keyed server
  used from Claude.ai needs the deployment fallback below. The steps are
  under [Adding a keyed server to Claude.ai](#adding-a-keyed-server-to-claudeai).
- **A client that cannot add a header** (a stdio run has no HTTP at all;
  Claude.ai without the request-headers beta): the deployment holds a
  fallback key in the server's environment variable (`AI4RA_MCP_SAM_KEY`,
  `AI4RA_MCP_FAC_KEY`, `AI4RA_MCP_REGULATIONS_KEY`, `AI4RA_MCP_PERDIEM_KEY`,
  `AI4RA_MCP_CSL_KEY`, `AI4RA_MCP_GOVINFO_KEY`, `AI4RA_MCP_CONGRESS_KEY`,
  `AI4RA_MCP_SCORECARD_KEY`, `AI4RA_MCP_BLS_KEY`, `AI4RA_MCP_PUBMED_KEY`,
  `AI4RA_MCP_OPENALEX_KEY`, `AI4RA_MCP_LAKEHOUSE_SECRET`), used only for a request that sends no
  token. That is a deployment's choice, not the design: everyone through
  that deployment then shares one quota, and most deployments set none.

### What a request without a key gets

The server still mounts and still lists its tools, so a client sees what it
would get. Its index tool answers with a `key` block saying whether this
request carried one (`on_this_request`), that the key is per user, and how
to get one. Every other tool answers:

```json
{
  "error": "no API key on this request: send your own key as a bearer token. A free key comes from https://api.data.gov/signup/ (an email address is all it asks); DEMO_KEY works for a few calls an hour.",
  "do_not": "Do not answer this from memory or from a web search. Tell the person this server needs their key and how to get one, and stop there."
}
```

With `AI4RA_MCP_LOG_HEADERS=1` in the environment, the one logging switch,
the process logs one WARNING line per request on any path: method, path,
whether an `Authorization` header arrived and whether the middleware
accepted it (and why not), the header's fields as received with its
credential redacted, and the names of the headers present. The fields are
the header's form (every word that is not a scheme word is `<token:N>` with
N its length, a word that begins with a scheme word keeps only that prefix,
whitespace kept as sent and quoted), the whole value's length, the scheme
word exactly as sent (`none` when the first word is not one, since it may be
the key), the separator between scheme and token as code points (`U+0020` a
space, `U+00A0` a non-breaking one, `none` when the token is glued to the
scheme), the token's length, and whether whitespace pads either end. No
character of a credential and no other header's value is written. A call
that worked and one that did not sit side by side, and a grep on `rejected`
or `absent` keeps the failures:

```
POST /perdiem/mcp: authorization accepted 'Bearer <token:40>' len=47 scheme=Bearer sep=U+0020 token_len=40 padded=no; headers: host, user-agent, accept, content-type, authorization
POST /perdiem/mcp: authorization rejected (no space between the scheme and the token) 'Bearer<token:40>' len=46 scheme=Bearer sep=none token_len=40 padded=no; headers: host, user-agent, accept, content-type, authorization
POST /perdiem/mcp: authorization rejected (a colon after the scheme) 'Bearer: <token:40>' len=48 scheme=Bearer: sep=U+0020 token_len=40 padded=no; headers: host, user-agent, accept, content-type, authorization
POST /perdiem/mcp: authorization absent; headers: host, user-agent, accept, content-type
```

The first is the accepted form. The second is the key glued to `Bearer`
with the space between them lost, what Claude.ai's header field did to a
typed space (2026-10-15, the first thing this line found); the third a colon
that crept in. The other reasons are `no scheme word` (a key pasted bare),
`scheme is Basic, not Bearer`, `the separator is not a space`, `no token`
and `empty`. The switch is read on each request and is off unless set, so a
deployment turns it on to troubleshoot a client (on the demo VM, the line
in the `.env` beside the compose file and `docker compose up -d`) and off
again after.

The second line is there because a refused lookup once became an invented
answer: a per diem question got made-up figures with a made-up source line
after the tool asked for a key. The answer now tells the model to stop, and
the `bls` and `pubmed` servers, whose key is optional, carry on without one
at the shared rate. A key an upstream refuses comes back as
`401 from <host>: the API key was refused or lacks permission`; a rate limit
as `rate limit exceeded at <host>; wait before retrying`, which the model
is told to report rather than retry.

## Server reference

One section per server, in index order: what it reads, what its tools
return, how long answers are cached, and what its index tool tells the
model. Caches are in memory, one per server, and do not survive a restart.

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

`fetch_document` reads a public web page or PDF as plain text, in pages
(`offset`, `max_chars` up to 40,000), so a long solicitation is read in
several calls. Public http(s) only: a host that resolves to a private,
loopback or link-local address is refused, every redirect is re-checked,
bodies over 8 MB are refused, and only HTML, PDF and plain text are read. A
grants.gov opportunity link is answered from the grants.gov API instead,
since the page itself is rendered by script; any other script-rendered
shell is reported as such rather than handed back as if it were the page. A
site whose certificate chain does not verify is read anyway and the result
says so (`tls_unverified`).

### ai4ra

Skills and guides, and one tool, `ai4ra_guide`, that lists the components
and returns one by name. Five guides say what a correct result is with no
client named: `rfa-guide` (a funding opportunity's facts and requirements,
the ceiling as a number), `narrative-guide` (the sections of a proposal
narrative), `work-plan-guide` (activities with lead, start and duration),
`budget-outline-guide` (eleven categories, the split, the estimates, the
loaded share of the ceiling) and `nsf-budget-guide` (lines A to M, the
inputs and their origin, the Rates contract, the checks). Each is the
judgment of a sheet skill with the placement taken out. The sheet skills
themselves (rfa-sheet, proposal-narrative, work-plan, budget-outline,
budget-nsf, and udm-sheet) were the pane's from the start, moved here on
2026-09-22 and moved back on 2026-09-30 once the pane served its own
(mindrouter-365 #36, #37); they are in git history. `nsf-budget-guide`
carries the Rates contract a budget form reads: seven labelled items in a
fixed order (Location, F&A rate, F&A base, Fringe faculty, Fringe staff,
Fringe students, Fringe temporary) and a Source line of provenance; an
institution's rates skill reports in that form (`uidaho-rates` is Idaho's)
and a client lays it down.

A sixth guide is a vocabulary: `compliance-concerns-guide` holds twenty
concerns a statement about a sponsored project can raise (allowability,
indirect costs, effort, cost sharing, subawards and the rest), each a name
and a description of what it covers and where it stops, so that statements
about the same thing can be grouped under one name. The list is closed and
cites nothing: which regulation or policy governs a statement is found from
the statement with the server that holds that source (`ecfr_search`
limited to a title and part on `ecfr`, the `uidaho-lookup` skill on
`uidaho`), not from a map kept here. Draft
0.1; the categories are the research office's to own and have not been
reviewed by it (#15).

The other seventeen components are copies of AI4RA/prompt-library at commit
`eef6fd3d818037ab51ece87f61806c448d51f40d`, files unchanged, each catalog
entry carrying a `source` with the repository, commit and path. They are not
edited here: a change goes to the prompt library and is copied in again at a
new commit.

### udm

The AI4RA Unified Data Model, the vendor-neutral specification for
research-administration data, read from the schema JSON its repository
publishes on GitHub Pages
(https://ui-insight.github.io/AI4RA-UDM/data/udm_schema_v2.json; the prose
spec is in the AI4RA-UDM repository). No key. `AI4RA_MCP_UDM_SCHEMA_URL`
points at another copy and `AI4RA_MCP_UDM_SCHEMA_FILE` reads a local file
instead, which is how a checkout ahead of the published release is served;
the published copy is cached a day, and every answer carries the version it
came from.

Two things a model needs to convert records to the UDM, and nothing that
interprets the records for it. **The schema, in portions**, since the file
is a few hundred kilobytes: `udm_index` is the overview (the version, the
47 core tables in their six modules, the two implementation tables, the
optional modules' tables each marked with its module, every table with a
line, the audit columns, and the file's other sections by name);
`udm_schema` with a table name is that table as the file has it, its
columns in the spec's order with type, required flag, primary-key flag,
references, allowed values (the column's own, or the status taxonomy the
file keeps apart), description and synonyms, then the audit columns every
table carries and the cross-row constraints on it; `udm_schema` with a
section name is one top-level section verbatim (`universal_patterns`,
`semantic_conventions`, `status_taxonomies`, `derived_values`). **The
conversion guide**: `udm_guide` with the name `udm-conversion-guide` (a
catalogued component, also an MCP prompt) returns the way the job is done
written once as text: look at the data before the schema and
say what one row is; fetch the table; decide each source column's one
operation (rename, split or extract, combine or coalesce, transform,
recode or blank, default, derive, resolve, route, generate, drop, or keep
flagged) from its name, the synonyms, the description and above all the
values, with the patterns that
recur (the key, sponsor versus internal numbers, references held as names,
original versus current, lifecycle stages, two-way attachment, columns the
source lacks or the table lacks); conform dates, booleans, vocabularies,
amounts and text; fill provenance; ask once with the decisions laid out and
at most three questions; report. And what it never does: the output has
exactly one row per source row in the source's order, never filtered,
deduplicated, aggregated, sorted, pivoted or split; a grain that is not
the table's means another table or a reshape first, not fewer or more
rows. The synonyms are examples of what a
column has been called elsewhere, not a closed list, and the guide says so:
an institution's data has names the schema never heard of, which is why the
mapping is the model's judgment over the data it can see and not a match
the server computes.

Any MCP client can convert with these two tools alone. The workbook side,
a placement skill that reads the records, follows the guide, asks once, and
lays the sheet out as one UDM table by formula, is the pane's own skill
(mindrouter-365 #37); it was served from here until 2026-09-30 and is in
git history. Where it finally lives is open: the base client is the plan's
answer, but the data model it targets is one consortium's, and an
institution with a data model of its own may want the conversion skill in
its own mindrouter-365-aware server instead (mindrouter-365 #43).

### ecfr

The eCFR API, https://www.ecfr.gov/api, no key. The tools came from
mcp-ecfr: give the title explicitly because part
numbers repeat across titles, prefer sections over parts. The regulatory
index, a resource in mcp-ecfr, is a tool here as well, because most clients
never list resources. It is reference for a caller that does not know where
to start (agency slugs, starter citations, the day the eCFR is current to)
and not a first call: the server's `instructions`, the index's own
description and `ecfr_search`'s "START HERE" now tell one story, search
within a title and part and read what the search returns. Until 2026-10-01
the instructions and the index each said to read the index first while the
search said to start there and `cfr-check` never called the index, so a
client that honoured the instructions made an index call before every
check (#28). `ecfr_compare_regulations` diffs a section between two
dates.

**No date is needed for the current text.** `ecfr_search`,
`ecfr_get_regulation` and `ecfr_get_title_structure` take `date` as
optional, and `ecfr_compare_regulations` its `date_2`: left out, it is the
latest day the eCFR holds, read from the eCFR's own
titles list (the title's `up_to_date_as_of`) and kept for an hour, never
taken from the clock. The eCFR runs behind the calendar (on 2026-10-01 it
held 2026-09-29) and refuses a later date, so "today" and often "yesterday"
fail. The result's `date` says which day was read, and the index reports it
as `current_as_of`. Any earlier
date returns the text in force that day, so no version lookup comes before
a fetch; `ecfr_get_title_versions` is for history. A date past the latest
day is refused with that day named, and the server's refusals (a bad date,
a section the eCFR does not have, with the eCFR's own words) now reach the
client as the error's text instead of a bare "Error executing tool" (#16,
items 2, 4, 5 and part of 8). A search of every version, superseded ones
included, is `date="all"`.

**A long section comes back as its outline.** A section is the smallest
thing the eCFR serves, and some are far longer than what a caller needs
from them: 200.1 (Definitions) is 47,153 characters and the definition of
modified total direct cost is 659 of them. `ecfr_get_regulation` returns a
short text whole. One over 6,000 characters that has subheadings comes back
as an `outline`, the text's own subheadings each with the character offset it
starts at and the size of its part (`"30650: Modified Total Direct Cost
(MTDC) (661 chars)"`), and only the lines before the first of them; the caller chooses a part and calls again
with its `offset`, one number copied from the outline, and the part is read
to its end: where the next subheading of the same level begins, so "(g)"
comes with the paragraphs under it and a definition with its numbered
items. A part read also returns its `pinpoint`, the citation down to that
paragraph (`2 CFR 200.430(i)(5)`, `2 CFR 200.1 Equipment`, `2 CFR Appendix
III to Part 200, B.1`), built from the labels of the headings it sits
under, so a finding cites the paragraph it quotes and not a neighbour
(#23). Levels are read from the text too (an appendix's heading ranks, a
paragraph's own label: (a), (1), (i), (A)). The subheadings are the ones
the regulation carries: a paragraph's italic lead-in (the 109 defined terms
of 200.1, "(a) General." in 200.430), an appendix's headings, each
section's head when a subpart is fetched. They are read from the text
fetched, so an earlier version's outline is that version's, and the server
keeps no map of the regulation. An offset that is no heading's reads the part it
falls in, from that part's heading, so a number carried over from another
section's outline returns a whole paragraph with its true pinpoint and not
a page that starts mid-sentence (a run asked for 200.430 at 2000, the
offset of "(c)" in 200.431, and was given 11,161 characters). A text that
came whole has no part and no page to ask for: an offset sent for one
returns it whole again with a `note` that says so (a check asked for a
2,111-character section at 1300, 600 and 470 and was given three pieces
from mid-sentence, #25). A long text
with no subheadings is paged instead: `truncated`, `next_offset`. Every result carries `total_chars`,
`offset` and `returned_chars`; `truncated` means the read was cut short of
what was asked for, so a part read to its end is not truncated though the
text goes on (#16 item 3).

The size is the server's and a caller cannot set it: there is no
`max_chars`. Two numbers in `common/text.py` hold for a regulation's
sections and a policy's alike. A text that has an outline comes back whole
up to 6,000 characters (`WHOLE_CHARS`) and as its outline past that; a text
with no outline has nothing to choose from, so it comes back whole up to
12,000 (`PAGE_CHARS`) and a page of that size at a time past it, and a part
read by its offset is never cut below that. The line has moved with the
runs. At 12,000, before a part could be read to its end by its offset, a
check read 200.430 (17,638 characters) in twelve pieces (#19), and it went
to 20,000; at 20,000 a check read 200.431 (15,647) whole for nothing (#22);
and at 12,000 the first whole-document check read five policies of 6,900 to
9,400 characters whole for a clause each, 43,000 of a step's 60,000, with
half its rounds of calls unused. What a step runs out of is characters, so
the line sits where a part read saves them. A model that asked for 3,000
turned 200.413 (3,777) into an outline, then was refused for asking for
400; no caller sets a size now. Change the constants if a run shows the
line is in the wrong place.

`ecfr_search` can be limited to a title, part, subpart or section (`title`,
`part`, `subpart`, `section`, the eCFR's hierarchy filter), so a Uniform
Guidance search is only 2 CFR 200: `title=2, part="200"`. A part, subpart or
section needs the title, and a subpart needs its part. Three things make a
search find the governing sections: the words, the limit to the title and
part, and the date, which is the current text unless one is given. The
words are few, two or three: a section matches only when it has every one,
and a search that finds nothing with more says so. A hit is its citation, the heading of the section or appendix, the
title, part and section to pass to `ecfr_get_regulation`, and its link:
about 350 characters where the eCFR's own record, which repeats the title,
chapter and part headings in every hit, came to about 780 (#16 item 7).
The agency filter (`agency_slugs`) takes in every
part an agency owns and is no longer the way to reach Part 200; the eCFR's
slug for OMB is `management-and-budget-office`. The result's
`meta.description` says what was searched ("in Title 2 :: Part 200") (#17).

One skill, `cfr-check`, report-only: it checks a passage of a document,
however the client supplies it, against 2 CFR 200 as fetched (the current
rules unless the request names a date) and reports a finding for each
sentence that disagrees: the word `finding.` with the pinpoint, the sentence's
words, one clause quoted with its link, and a fix (no verdict: it surfaces
what a person should look at and does not rule, #26); then the date read, the
sections fetched and each sentence not checked. Nothing comes from memory.
It names no client, so it runs the same in Claude Desktop, Claude Code or
the pane; putting each finding on the document (a comment on its sentence)
is a client's placement skill, as with the rates. `ecfr_guide` serves it.
`ecfr-research-admin`, the prompt that came with mcp-ecfr, was removed on
2026-10-01: it restated what the tool descriptions, the server's
instructions and the index already say.

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

Executive orders are first-class on the same server, since the Register
publishes every one as a presidential document and its API carries the
order's number, signer, signing date, citation, plain-text body and the
Office of the Federal Register's disposition line (#39, verified live
2026-10-14). A search takes `presidential_type` (one of `executive_order`,
`proclamation`, `memorandum`, `determination`, `notice`, `other`, which
implies PRESDOCU), `president` (the Register's identifier, `joe-biden`) and
`signing_from`/`signing_to`, each enough on its own; a presidential
document's row and record carry `executive_order_number`,
`presidential_document_number`, `signing_date`, `president` (name and
identifier), `citation`, `disposition_notes` and `raw_text_url`, and a rule
or notice gains none of them. `federal_register_executive_order` finds one
order by number: the API has no condition on the number, so it is a
full-text search for the number among executive orders with each result's
`executive_order_number` checked against what was asked; none is an error
that says the API holds presidential documents from 1994 on, more than one
comes back as `candidates` with no pick. The disposition line is the
Register's, passed through as written: `Revoked by:` means no longer in
force, `Revokes:` and `Amends:` what it did to earlier orders, `See:`
related ones, null that nothing has touched it; the index tells the model
to quote it and infer an order's status from nothing else, that signing is
days before publication, and to read the body from `raw_text_url` with
`fetch_document`.

### regulations

Regulations.gov, https://api.regulations.gov/v4/, a JSON:API over the public
rulemaking dockets. A free api.data.gov key, the person's own, sent by the
client as a bearer token and forwarded as `X-Api-Key`;
`AI4RA_MCP_REGULATIONS_KEY` is a deployment's fallback. **The limit is 1,000
requests an hour per key**, and DEMO_KEY is shared by everyone and good for
a handful. Documents by words, type (Notice, Proposed Rule, Rule, Supporting
& Related Material, Other), agency id, docket, posted dates or only those
open for comment, newest first, 5-250 a page and at most 20 pages of one
search; one document with its dates, files (PDF, HTML), CFR part and the
Federal Register number the fedreg server reads for the text; one docket
with its type, abstract and RIN; the public comments on a document or in a
docket. Searches are cached an hour, records a day. The index tells the
model that comments are filtered by the document's `object_id`, not its
document id, that timestamps are UTC and date filters YYYY-MM-DD, and to
cite the link on each record.

### idstat

The Idaho Statutes, the codified law of the State of Idaho, as the
Legislative Services Office publishes them at
`https://legislature.idaho.gov/statutesrules/idstat/`: one HTML page per
title (74), chapter and section, a PDF of each chapter beside them, the
current law only, updated to the web each July 1 after the session. The
site is WordPress and the statute text inside each page is the office's
Arbortext export (a `pgbrk` block: title and chapter lines, the section's
number, heading and text, then its History line); the site's WordPress REST
API does not answer, and there is no other API or bulk download (checked
2026-10-16), so the pages are read as published, anchored on the outline
tables and that block. No login, no key; cell 4, since the state's law is
no one institution's own knowledge.

Full-text search is the Legislature's own ISYS engine at
`https://legislature.search.idaho.gov/search`, a GET with
`IW_FIELD_WEB_STYLE` (web-style words, a quoted phrase, AND and OR),
`IW_DATABASE=Idaho Statutes` and `IW_BATCHSIZE` for the results a page
(tested to 50). Its results page lists each matching page with a hit count,
a snippet with the matches marked and the page's URL; the matches are
section pages and, now and then, a chapter or title outline, which the
result's `kind` says. Later pages of a result set live under a query id the
engine mints per search, so the server asks for the rows it wants in one
batch and pages no further. The engine answers nothing (200, an empty body)
to a User-Agent that does not begin `Mozilla/5.0`, and to one that nests
parentheses, so the search alone is sent as
`Mozilla/5.0 (compatible; ai4ra-mcp/0.1; +<AI4RA_MCP_CONTACT>)`, the
convention for an identified robot, which still names this project and its
contact; the statute pages take the plain agent string.

- `idstat_titles()`: every title with its name and link.
- `idstat_chapters(title)`: a title's chapters with name, link and chapter
  PDF.
- `idstat_sections(title, chapter)`: a chapter's sections with citation and
  heading, the title and chapter headings and the PDF.
- `idstat_section(citation)`: one section by citation (`33-2901`,
  `67-5309A`): the title and chapter headings, number, heading, text as
  paragraphs in the code's order, and History. A citation is TT-CCSS, title,
  hyphen, chapter and a two-digit section, so the chapter is read from the
  citation and a citation alone finds its page; a section that is not there
  returns the 404 and the page it tried.
- `idstat_search(query, rows)`: the engine's results, `sections_matched`,
  `hits`, and for each result its kind, section, page, hit count, snippet
  (matches as `**word**`) and link, 1-50 a call, with a note when more
  matched.

The index reports the office's own statement of how current the text is,
read from its "How current is this law?" page (`current through the 2026
Legislative Session` on 2026-10-16), and tells the model which titles
research administration reaches for (33 Education, 67 State Government and
State Affairs, 74 Transparent and Ethical Government with the Public Records
Act and Ethics in Government), to read a section
before quoting it, and to cite Idaho Code § TT-CCSS with the link. Pages are
cached a day, searches an hour. Offline tests run on pages captured in
`tests/fixtures/idstat/` with the WordPress chrome cut; the live site is the
only test of the routes and the engine themselves. The Idaho Administrative
Code (IDAPA) is published only as PDFs and is not here.

### govinfo

GovInfo, https://api.govinfo.gov/, the Government Publishing Office's
federal documents; a free api.data.gov key, the person's own as a bearer
token and forwarded as `X-Api-Key`, `AI4RA_MCP_GOVINFO_KEY` a deployment's
fallback. The search is a `POST /search` in GovInfo's syntax: the server
builds `collection:(PLAW BILLS ...)`, the words as given (a quoted phrase, OR,
`title:(...)`), `congress:119` and `publishdate:range(from,to)` from its
arguments, newest first, 1-100 a page with an `offsetMark` cursor the answer
returns. Each result is a package (a public law, one version of a bill, a
committee report, a Code title) or a granule within one (a Code section),
with its collection, date, formats and GovInfo link. `govinfo_package(id)`
reads `/packages/<id>/summary`: titles, Congress, document type, pages,
whether it is an appropriation, the laws and Code sections it references,
formats. `govinfo_text(id, granule_id, offset, max_chars)` reads
`/packages/<id>/htm` (or the granule's) as plain text in pieces of up to
60,000 characters with a `next_offset`, since an appropriations act runs to
hundreds of pages. `govinfo_collections()` lists the collections with counts.
Searches are cached an hour, records and text a day. The index explains the
collections that matter here (PLAW for the appropriations acts, CRPT for the
report language, USCODE, CFR, FR, CHRG, GAOREPORTS, BUDGET, COMPS), the
query syntax, and that the regulations themselves are the ecfr and fedreg
servers' job. Offline tests run on answers captured in
`tests/fixtures/govinfo/`.

### congress

Congress.gov, https://api.congress.gov/v3/, the Library of Congress's
legislative record; a free api.data.gov key (sign-up at api.congress.gov),
forwarded as `X-Api-Key`, `AI4RA_MCP_CONGRESS_KEY` the fallback. A bill is
addressed by Congress, type (hr, s, hjres, sjres, hconres, sconres, hres,
sres) and number. `congress_bill` assembles one bill from its record, its
latest CRS summary and its text versions (three calls): title, sponsors,
policy area, latest action, the laws it became, counts of actions,
cosponsors, committees and reports, CBO estimates, committee report
citations, the summary as text, and each text version's formats and URLs.
`congress_bill_actions` pages the chronology; `congress_bills` lists a
Congress's bills, or one type's, updated in a window, most recently updated
first; `congress_laws` the bills that became law with their public law
numbers; `congress_members` a state's current delegation. Lists are cached an
hour, members a day. The API has no word search, which the index says: words
are govinfo's (collections BILLS, BILLSTATUS, CRPT, PLAW), and this server
answers what a bill is, where it stands and who carries it. Offline tests
run on answers captured in `tests/fixtures/congress/`.

### grants

grants.gov's public API, https://api.grants.gov/v1/api/, no key.
`grants_gov_search` finds announcements by keyword, status (posted,
forecasted, closed, archived), agency and category, with the agency facet
for narrowing; `grants_gov_opportunity` fetches one record by the id a hit
carries, with its synopsis, dates, ceiling, cost sharing, eligibility and
attachment links. An attachment is read with `fetch_document` on the
`general` server. The `funding-opportunity-finder` skill runs that sequence.

### s2s

The Grants.gov Applicant System-to-System web services, V2.0: SOAP over
mutual TLS, the contract Grants.gov publishes as a WSDL and form XSDs (vendored
under `servers/s2s/contract/`, copied from
[AI4RA/grants-gov-s2s-mock](https://github.com/AI4RA/grants-gov-s2s-mock)).
Grants.gov runs it at `trainingws.grants.gov` and `ws07.grants.gov`; every tool
takes an `endpoint`, and the deployment's default (`AI4RA_MCP_S2S_ENDPOINT`) is
the mock on the compose network, so the same tools reach all three and the
switch to the real service is a URL and a certificate, not code. The
credential is the person's: their client certificate and private key as the
bearer token, base64url of `{"cert": PEM, "key": PEM, "ca": PEM?}` (printed by
`python -m ai4ra_mcp.servers.s2s.credentials cert.pem key.pem`), held for the
request only; the key never appears in a tool argument. A deployment may hold
a fallback pair in `AI4RA_MCP_S2S_CERT_FILE` and `AI4RA_MCP_S2S_KEY_FILE`.

`s2s_check` proves the connection (the WSDL, then a package lookup) and names
which of the error classes a failure is: configuration, certificate,
transport, rejected, not_found. It also describes the caller's certificate
(subject, issuer, serial, validity, key, Client Authentication EKU) and, for
training and production, whether its issuer is on the CA list that endpoint
announced in its TLS handshake when we probed it on 2026-09-28
(`contract/acceptable-client-cas.<host>.txt`, about 180 names each, InCommon
and Sectigo among them), so a certificate failure is reported as either an
unaccepted issuer or an accepted one that is not yet registered. `s2s_opportunity` is GetOpportunityList by
opportunity number, CFDA, competition id or package id, with each package's
forms read from its package schema. `s2s_validate_package` checks a
GrantApplication offline against the form schemas and lists the attachments it
references. `s2s_submit` (writes on only; production only with
`AI4RA_MCP_S2S_PRODUCTION=1`) validates the package, fetches each attachment
from a public URL, checks its SHA-1 against the form's HashValue, sends
SubmitApplication as MTOM and returns the tracking number; it requires
`confirm_environment` to equal the endpoint's environment name.
`s2s_submissions` is GetSubmissionList by the five filter types the schema
allows; `s2s_application_info` is GetApplicationInfo. Every request is
checked against the WSDL types before it leaves and every response as it
arrives; the index tool lists the status values and the error classes.
`tests/test_s2s_live.py` runs the whole sequence, including a submission,
against any endpoint named in `S2S_LIVE_ENDPOINT`.

### pappg

The NSF Proposal & Award Policies & Procedures Guide as NSF publishes it,
`https://www.nsf.gov/policies/pappg/24-1/`, one HTML page per chapter
(`ch-1-pre-submission` to `ch-12-disputes-misconduct`), a table of contents
whose links carry the anchor of every section, a summary of changes, a
subject index and a PDF; no key. The version is pinned (NSF 24-1, effective
for proposals due on or after 2024-05-20) and the landing page's version
line is read each day so the index can say when NSF has moved on. A chapter
page is Drupal: the text sits in `text__content` blocks under h2 (a lettered
section, whose page id is a slug), h3 (a numbered subsection, id `ch2D2`)
and h4 (a lettered paragraph, `ch2D2b`); the table of contents links a
lettered section by its slug, so each section carries a canonical anchor
(`ch2A`, made from the heading's letter, or its place among the chapter's
lettered sections) beside the id the page uses, and links go to the page's
id. `pappg_chapters()` lists the twelve chapters; `pappg_outline(chapter)` a
chapter's sections with labels (`D.2.b`) and anchors; `pappg_section(chapter,
section)` one section by label, anchor or heading words, with its paragraphs
and the subsections under it and a citation (`PAPPG Chapter II.D.2.b`);
`pappg_search(query, chapter, rows)` the sections across the guide, or in
one chapter, whose heading or text carries every word, heading matches
first, with a snippet. Chapters are cached a day. The index tells the model
how to cite, that a solicitation may deviate from the guide, which chapters
hold what, and that tables and footnotes come through as text. Offline tests
run on the table of contents, two chapters and the landing page's version
line captured in `tests/fixtures/pappg/`.

### nihgps

The NIH Grants Policy Statement, the terms and conditions of NIH awards, in
the web edition NIH publishes at
`https://grants.nih.gov/grants/policy/nihgps/HTML5/` (MadCap Flare), one
page per section; no key. The edition's table of contents is its data file
`Data/Tocs/TOC_Web.js`, which names chunk files mapping each page to its
entries (a page can hold several: 7.9 and 7.9.1 share one, the second at an
anchor), read once a day for the outline (about 280 sections) and to resolve
a section number or title to its page. A section page is read from its
heading: paragraphs, tables as rows (Exhibit 5 in 7.9.1, the selected items
of cost, is a table of items and NIH's rule for each), subheadings, and the
revision line every page carries (`REVISED MARCH 2026`, read live
2026-10-16); glossary popups, which are inline definitions, are dropped so
a sentence reads once; a chapter's own page is a placeholder and is answered
from the table of contents. `nihgps_toc(query, chapter)` lists the table, the
sections whose titles carry words, or one chapter's sections;
`nihgps_section(section)` one section by number (`7.9`, `8.1.2.3`) or title
with its subsections and a citation (`NIH GPS 7.9`); `nihgps_search(query,
chapter, rows)` the sections of one chapter that carry every word, reading
the chapter's pages (cached a day), title matches first, with a snippet. The
index reports the revision, explains the parts and chapters, how to cite,
that the GPS incorporates 2 CFR 200 (the ecfr server), and that a Guide
notice newer than the revision governs (the nihguide server). Offline tests
run on the table-of-contents files and three pages captured in
`tests/fixtures/nihgps/`.

### nihguide

The NIH Guide for Grants and Contracts, NIH's publication of record for
notices and funding opportunities, at `https://grants.nih.gov/grants/guide/`;
no key. Its search page is an app that reads a JSON service, found in the
app's bundle on 2026-10-16: `GET <service>/data?perpage=&from=&sort=&type=
&query=&primaryic=&daterange=MMDDYYYY-MMDDYYYY&...`, an Elasticsearch result
whose hits carry the document number, title, type, document type, release
and expiration dates, issuing institute, notice subject, activity codes and
a line of purpose. `type` is `notices` for the Guide's notices (NOT-; 16,800
on 2026-10-16) and `active`, `activenosis`, `expired`, `expirednosis` for
notices of funding opportunity (RFA, PA, PAR, PAS) and notices of special
interest, the four together being every NOFO the Guide has carried. The
service is the page's own and undocumented, which the index says; a change
to it is a change to this server and the page is the fallback.
`nihguide_search(query, kind, institute, from_date, to_date, rows, start)`
maps kind (notices, opportunities, open, all) to type, the institute code to
`primaryic`, dates to the service's form, sorts by relevance when words are
given and by release date otherwise, 1-100 a page with `next_start`, and
links each result to its Guide page (`notice-files`, `rfa-files`,
`pa-files`). `nihguide_notice(number)` reads a notice's page for its number,
title, release and expiration dates, related announcements, issuing
organisations, purpose and inquiries (email addresses are hidden by the
site's protection and are not read). `nihguide_weekly(week_ending)` reads
the weekly index (`WeeklyIndexMobile.cfm`, `WeekEnding=MM-DD-YYYY` for an
earlier week) to its groups of notices. Searches and the weekly index are
cached an hour, notice pages a day. The index explains the numbering, that
new NOFOs are posted on Grants.gov as of fiscal 2026 (the grants server has
the packages) while the Guide still lists them, and that a notice newer than
the Grants Policy Statement's revision governs. Offline tests run on the
service's answers, a notice page and the weekly index captured in
`tests/fixtures/nihguide/`.

### nihdates

Two pages on grants.nih.gov, read as HTML and cached a day, no key: the
standard due dates page, `https://grants.nih.gov/grants-process/submit/submission-policies/standard-due-dates`,
and the salary cap summary,
`https://grants.nih.gov/policy-and-compliance/policy-topics/nih-fiscal-policies/salary-cap-summary`.
`nihdates_due(activity_code)` returns the due dates table's rows for a code
(R01, R21, K08, F31, a series such as 'K series'), each with the activity
codes, which applications the row is for (new; renewal, resubmission,
revision), the program and the Cycle I, II and III dates, and the page's
note that AIDS applications no longer have their own dates (NOT-OD-26-029);
`nihdates_cycles` the table of what follows a due date in each cycle (merit
review, council, earliest start); `nihdates_salary_cap(fiscal_year)` the
Executive Level II cap for each period of award issue dates since FY 1990
with the Guide notice that set it, the cap in force today when a period
covers it and the latest posted when none does (the page had no FY 2027
period on 2026-10-16). Every answer carries the page URL and the date the
page says it was last updated. Offline tests run on both pages' main content
captured in `tests/fixtures/nihdates/`.

### omb

OMB's memoranda to agencies (M-26-01, M-24-11), from the memoranda page on
whitehouse.gov, `https://www.whitehouse.gov/omb/information-resources/guidance/memoranda/`
(the current administration's), and the same page as the National Archives
preserved it for the prior administration,
`https://bidenwhitehouse.archives.gov/omb/information-for-agencies/memoranda/`
(late 1990s to January 2025); together 691 memoranda, 1999 to 2026, when
read 2026-10-16. Both are read as HTML with a browser-like User-Agent
(whitehouse.gov's edge refuses the generic one), cached a day, no key. Each
entry is the number, title, date, year heading, PDF link and page count when
the list gives it; a number on both lists is kept from whitehouse.gov; and
each entry's `referenced_by` is the later memoranda whose titles name its
number (M-25-14 'Rescission of M-25-13'), since the list says nothing else
about whether a memorandum is in force. `omb_memoranda(year, query, rows)`
searches by year heading and title words newest first; `omb_memorandum(number)`
takes 'M-24-11', 'M 24 11' or '24-11'. The PDF itself is read with the
ai4ra server's fetch tools. Offline tests run on the current page and the
2025 and 2024 sections of the archive captured in `tests/fixtures/omb/`.

### ncura

The National Council of University Research Administrators' calendar of
meetings, conferences and workshops, from the public event listing behind
`https://www.ncura.edu/Education/Calendar.aspx`: the calendar page is an
iframe onto NCURA's association-management system (cvweb, `Eventsdll.dll`),
whose `EventList` returns the events shown on the web from a start date as
an HTML table and whose `EventInfo?sessionaltcd=<code>` returns one event.
Neither needs a login; the member side (Collaborate, NCURA Magazine, the
member directory, the Career Center) is behind one and is not read. Read with
a browser-like User-Agent, the list cached an hour and an event a day, no key.
`ncura_events(query, when, rows)` is the events soonest first with code,
title, subtitle, dates, NCURA's type code (ANNUAL, FRA, PRA, FUND, DRA,
REGSPRING), whether registration is open (the list's own flag), the check
registration form and the event's page; `when` is 'upcoming' (from
yesterday, as the site shows: nine events on 2026-10-16) or 'year' (the past
400 days too: 46). `ncura_event(code)` is one event with its dates, early-bird
and registration deadlines, the fee table as printed (member and non-member,
early and regular), the description, the venue and address and the hotel
link. The code is NCURA's handle and is read from `ncura_events`, never
guessed. Offline tests run on the two lists and two events (a regional
meeting and a virtual workshop) captured in `tests/fixtures/ncura/`.

### nih

NIH RePORTER, https://api.reporter.nih.gov/ v2, no key, about one request a
second. Projects by PI name, organization, fiscal years, activity codes,
institutes or text; one project by number with its abstract; a project's
publications by core project number, as PubMed ids. RePORTER returns one
record per fiscal year and one per component of a center grant, and the index
tool says how to read that. Searches are cached for an hour, records for a
day. The `funding-history` skill reads this server and the nsf server for a
PI's or an institution's federal award history.

### nsf

NSF Award Search, https://api.nsf.gov/services/v1/, no key, 25 a page and
3,000 for one query. Awards by keyword, PI, awardee, program or start date;
one award by id with its abstract and program officer; the project outcomes
report. Dates are MM/DD/YYYY both ways. A multi-word awardee is sent as a
quoted phrase, since the API matches an unquoted name on any word; a PI name
stays unquoted, where any-word is what finds a middle initial.

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

### sam

SAM.gov, https://api.sam.gov/: entities and exclusions (entity-information
v4) and Assistance Listings (v1). One key covers all three, and it is the
person's own: the client sends it as a bearer token on each call.
**The daily quota is per key:** 10 requests for a personal key without a role
in SAM.gov, 1,000 with a role or a non-federal system account. The index tool
says whether the request carried a key and how many requests this process
has made. An entity by UEI, CAGE or name with its registration status and
dates; active exclusions by name or UEI; one Assistance Listing by number
with its eligibility, the 2 CFR 200 subparts that apply, reporting, audit,
matching and contacts; listings by agency code, status or date. The listings
API has no keyword search. Entities and listings are cached for a day,
exclusions for an hour.

The `subrecipient-check` skill lives here and reads five servers: the
entity's SAM.gov registration and exclusions, its USAspending name history,
prime awards and subawards received, its FAC single audits and findings, and
its NSF and NIH award history, each under every name it has been filed
under. A name seen in results but on neither list is reported as a possible
synonym to confirm, never searched on the model's own initiative.

### fac

The Federal Audit Clearinghouse, https://api.fac.gov, a PostgREST API over
the public single-audit data. A free api.data.gov key, the person's own,
sent by the client as a bearer token and forwarded as `X-Api-Key`;
`AI4RA_MCP_FAC_KEY` is a deployment's fallback. Audits by auditee name, UEI
or EIN, newest first, with the auditor, opinion, the flags a risk assessment
reads (going concern, material weakness, material noncompliance, low-risk
auditee) and total federal expenditure; the findings of one report with
their text; its schedule of federal awards by program (the SEFA: spending by
program in the audited year, not a list of grants).

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

### openpayments

CMS Open Payments, https://openpaymentsdata.cms.gov/api/1/, the DKAN
datastore behind the Open Payments site, no key: the payments drug and
device manufacturers and group purchasing organisations reported making to
physicians, other practitioners (since program year 2021: physician
assistants, nurse practitioners, clinical nurse specialists, nurse
anesthetists, midwives) and teaching hospitals under the Sunshine Act,
published each June for the prior year. The metastore lists one dataset per
program year and kind (General, Research and Ownership Payment Data, 2019 to
2025 on 2026-10-16) and the Covered Recipient Profile Supplement, read once a
day and mapped by year and kind; the datastore answers `GET
/datastore/query/<dataset>/0` with `conditions[i][property|value|operator]`,
`limit`, `sorts` and `schema=false`, and a `POST` of the same as JSON with
`sum` and `count` expressions and `groupings`. Conditions are exact and names
are stored upper case; a query by NPI is indexed and answers in a second or
two, a query by name in a few. `openpayments_recipients(last_name,
first_name, state, npi)` finds a person in the profile supplement (profile
id, NPI, name, type, specialty, city, state, license states);
`openpayments_payments(npi, program_year, kind, rows)` lists one year's
records newest first, general ones with the totals by nature from the POST
query, research ones in two views (as the covered recipient and as the
study's principal investigator, with the study, its ClinicalTrials.gov id,
the payer and the products), ownership ones as interests;
`openpayments_summary(npi, from_year, to_year)` totals each year's general
payments, research payments in both views and ownership records, with grand
totals. Rows are cached an hour, the profile lookup and the dataset list a
day. The index tells the model who is a covered recipient and that absence
says nothing about anyone else, that a record is the company's report and
may be disputed, how to go from a name to an NPI, and which view a
conflict-of-interest review wants. Offline tests run on rows captured in
`tests/fixtures/openpayments/` with recipient names and addresses
anonymised.

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

### scorecard

The College Scorecard, https://api.data.gov/ed/collegescorecard/v1/schools,
the Department of Education's institution data from IPEDS and federal aid
records; a free api.data.gov key forwarded as `X-Api-Key`,
`AI4RA_MCP_SCORECARD_KEY` the fallback. One record per institution (IPEDS
unit id), filtered by name (contains), state, city, control and predominant
degree, with the fields named on the call. `scorecard_search` lists
institutions (id, name, place, control, degree levels, Carnegie basic code,
enrollment); `scorecard_school(id)` one record: control, Carnegie and locale
codes, accreditor, OPE ids, the minority-serving flags, enrollment and
graduate students, race and ethnicity shares, Pell grant and federal loan
rates, admission rate, tuition and net price, completion and retention,
median earnings ten years after entry, with codes named where the meaning is
fixed (control, degree level) and left numeric where the Carnegie and locale
code lists are long (the data dictionary is linked). Cached a day. The index
says which flags are reported (historically black, tribal) and that the
Hispanic-serving and other flags are null for every institution in the
current release, so an HSI or AANAPISI check needs the Department's
eligibility matrix; that Pell rate is the low-income measure eligibility
criteria often name; and that a research profile is the NSF, NIH and
USAspending servers' job. Offline tests run on the University of Idaho's
record and an Idaho search captured in `tests/fixtures/scorecard/`.

### perdiem

GSA per diem rates, https://api.gsa.gov/travel/perdiem/v2/, the lodging and
M&IE ceilings for travel within the continental US. A free api.data.gov key,
the person's own, sent by the client as a bearer token and forwarded as the
`api_key` query parameter; `AI4RA_MCP_PERDIEM_KEY` is a deployment's
fallback. Rates for a city and state, a whole state (every listed location
plus the standard rate) or a zip, for a federal fiscal year: lodging per
night by month with its low and high, M&IE per day, and a standard-rate
flag; the year's M&IE tiers with breakfast, lunch, dinner, incidentals and
the first-and-last-day (75 percent) amount. A city GSA does not list comes
back as the standard-rate row with a note saying so. Answers are cached a
day. The index tells the model that years are fiscal years (October to
September), that only CONUS is here, and to cite year and location with the
GSA per diem page.

### bls

The Bureau of Labor Statistics Public Data API, https://api.bls.gov/publicAPI/,
the CPI and ECI series an escalation rate rests on. No key is needed: v1
allows 25 queries a day per IP, shared by everyone on the server, 10 years
and 25 series a query. A free registration key, sent as a bearer token (or
`AI4RA_MCP_BLS_KEY`) and forwarded as `registrationkey` in the POST body,
moves the server to v2 with 500 a day, 20 years, 50 series and series
titles; the index says which is in use. `bls_series` takes ids and a span of
years and returns each series' points newest first (year, period, value,
latest flag) with BLS's message list, where it reports a missing series or a
reached threshold. `bls_common_series` is the table of ids a budget
justification uses: CPI-U all items (national, seasonally adjusted, West
region), CPI medical care, CPI college tuition, and the ECI 12-month changes
for total compensation and wages, verified live on 2026-09-24. Answers are
cached a day to spare the quota. The index tells the model the rate is
100 * (new - old) / old from two points a year apart, that ECI 'A' series
are already percent changes, and to say which series and periods it used.

### treasury

The Treasury Reporting Rates of Exchange from Fiscal Data,
`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/rates_of_exchange`,
a JSON API with `filter=field:op:value` (eq, lt, lte, gt, gte, in), `sort`,
`fields` and `page[size]`, no key. The Bureau of the Fiscal Service
publishes one rate per currency per calendar quarter, dated the quarter's
last day (2026-09-30 the latest on 2026-10-16, about 170 currencies named
`Country-Currency`: `Canada-Dollar`, `Euro Zone-Euro`), as foreign units per
one U.S. dollar, with an amended rate inside a quarter when a currency moves
10 percent or more; its rule is that a foreign-currency amount is converted
at the rate in effect on the date of the transaction. It is the rate a
federal award's foreign subaward invoice, purchase or travel is reported at,
not a market rate. `treasury_currencies(search)` lists the latest quarter's
table, matched by words in the country or unit, the names the other tools
take; `treasury_rates(currency, record_date, from_date, to_date, rows)`
gives one currency's rates by quarter, newest first, or every currency's for
one quarter, a currency resolved against the table (exact, one partial, or
the matches returned as `currencies_matched`); `treasury_convert(amount,
currency, transaction_date)` divides the amount by the latest rate whose
effective date is on or before the transaction date and shows the rate, its
quarter and the arithmetic. The latest quarter is cached an hour, a quarter's
table a day, other reads an hour. The index tells the model the rate's
direction (dollars = amount / rate), Treasury's rule, that a bank's rate will
differ, and to say which quarter's rate was used. Offline tests run on the
2026-09-30 table and two currencies' series captured in
`tests/fixtures/treasury/`.

### osm

OpenStreetMap's public services, no key: Nominatim,
`https://nominatim.openstreetmap.org/search`, for a place by name, and the
FOSSGIS Valhalla server, `https://valhalla1.openstreetmap.de/route`, for a
route between two points on foot, by bicycle or by car with turn-by-turn
steps that name campus walkways ("Bear right onto Hello Walk"). Both are the
OSM community's servers under fair-use policies (one request a second, an
identifying User-Agent, results cached, no autocomplete, no bulk or periodic
work, attribution under the ODbL), so calls here are paced to one a second
to each and cached (places a day, routes an hour), every answer carries the
attribution line, and the index says a heavy or scheduled need means hosting
Nominatim or Valhalla oneself. Tested on the University of Idaho campus on
2026-10-16: Nominatim resolved six of ten campus buildings by name, in OSM's
own spellings, so a campus place is taken from the campusmap server and only
the route asked here; Valhalla walked Albertson to the Kibbie Dome in 0.42
miles and eight minutes along the walkways, cycled and drove the same
points, and reached the Pullman-Moscow airport. `osm_geocode(query,
near_campus, rows)` biases results to a Moscow and Pullman viewbox unless
told otherwise and returns name, kind, coordinates, address and OSM link;
`osm_route(from_lat, from_lon, to_lat, to_lon, mode)` returns miles, minutes
and steps with the streets OSM names, and a link that opens the same route
on openstreetmap.org. Offline tests run on a geocode and a route captured
in `tests/fixtures/osm/`.

### weather

The National Weather Service API, `https://api.weather.gov/`, no key, an
identifying User-Agent on every call; the United States and its territories
and nothing else. A point (`/points/{lat},{lon}`) names its forecast office
and grid and links the forecasts (the office's own record gives its name,
Spokane, WA for OTX, so an answer names the office rather than leaving a
three-letter id to be guessed at), so `weather_forecast(lat, lon, hourly)`
returns seven days in the Service's half-day periods ("This Afternoon",
"Tonight", "Friday") with temperature, chance of precipitation, wind and the
forecaster's wording, or 48 hours by the hour; `weather_now(lat, lon)` the
latest observation at the nearest reporting station (for campus, the
Pullman-Moscow airport, KPUW) with the Service's Celsius, km/h, metres and
pascals also given in Fahrenheit, miles an hour, miles and inches of
mercury; `weather_alerts(lat, lon)` the watches, warnings and advisories in
force at the point, most severe first, an empty list when none;
`weather_office(office)` the office an answer names, by id, with its name,
address, telephone, region and the counties it is responsible for (the
county zones named in one `/zones` call), read from the Service rather than
held here. A point is a
latitude and longitude from the person, from `campusmap_search` for a
university building or from `osm_geocode` for an address; nothing here
names one. Points are cached a day, forecasts half an hour, observations
ten minutes, alerts five. Offline tests run on the campus point, its
forecast, stations, an observation, the office, its county zones and an
alert list captured in `tests/fixtures/weather/`.

### wolfram

Wolfram|Alpha, two of its APIs over one AppID: the LLM API,
`https://www.wolframalpha.com/api/v1/llm-api`, and Short Answers,
`https://api.wolframalpha.com/v1/result`. The AppID is the person's own, from
https://developer.wolframalpha.com/ (a free non-commercial account allows
2,000 calls a month, paid tiers above), sent by the client as a bearer token
and forwarded as `Authorization: Bearer <AppID>`, the form the LLM API
documents, never in the URL; `AI4RA_MCP_WOLFRAM_KEY` is a deployment's
fallback. `wolfram_ask(input, maxchars, units, assumption)` is the LLM API's
plain text whole, with the query, Wolfram's input interpretation, the result,
the other sections under their own headings and the link to the website's
result page lifted out, so a reply can say what Wolfram understood the
question to be and quote its result; `maxchars` caps the text (6,800 by
default), `units` is metric or imperial, and `assumption` resends the same
input under an assumption an earlier answer offered. `wolfram_answer(input,
units)` is Short Answers' one line for the main result, for a figure to carry
on with. A 501 (the input not interpreted, or no short result) comes back
with Wolfram's own words as `wolfram_said`, and the server never changes the
question on its own; a refused AppID is said (Wolfram answers 401 `Invalid
appid` in plain text, probed 2026-10-16, where its documentation says 403).
Answers are cached an hour, keyed by the input and its options alone. The
index tells the model how Wolfram wants an input phrased (one line of English
keywords, exponents as `6*10^14`, one property per call, an assumption before
a rephrase), that each call counts against the month so a table of values
is one call for the formula and not one per row, and that Wolfram
computes on figures the person or another tool supplied and reads none of the
institution's own. The portal's Get an AppID form asks for one API; an AppID
registered for the LLM API answered Short Answers too (verified 2026-10-16).
Offline tests run on responses captured that day in `tests/fixtures/wolfram/`:
a currency conversion and a duration from the LLM API, Short Answers' line,
and each endpoint's 501 body.

### openalex

OpenAlex, https://api.openalex.org/. Since February 2026 OpenAlex meters
its API by a daily budget rather than a rate: a call with no key shares
$0.10 a day with everyone on the caller's network address, and a free key
of the person's own (https://openalex.org/settings/api) has its own $1 a
day, a few thousand searches. The key is optional here, the person's own as
a bearer token or `AI4RA_MCP_OPENALEX_KEY`, sent as `api_key` and added
after the cache key is made, so no key reaches the cache or a log; a
`mailto` rides on every call as the contact OpenAlex asks for, and the index
reports whether a key is on the request and what a call costs. Works newest
first by author, institution (OpenAlex id or ROR), funder, award number,
years, type or words, with the first ten authors, journal, open-access copy,
the funders and award numbers the publisher deposited, and citation count;
the same works counted by one dimension in one call (`openalex_works_group`:
year, type, funder, award, institution, country, open-access status, topic,
field or journal, up to 200 groups, so "how many University of Idaho papers
acknowledged NSF each year" is one call rather than a paging loop, with the
caveat that a work with two funders is counted under each); one work by DOI
or OpenAlex id with its abstract put back together from the inverted index
and its reference count; the works that cite a work, newest first, or the
works it cites, paged (`openalex_citations`, through the `cites` filter and
the work's `referenced_works` list fetched in pages of ids); authors by name
with ORCID, counts, last known institutions and top topics; institutions
and funders by name, a funder with its Crossref Funder Registry id and
10.13039 DOI. Ids are URLs and the tools take either form. The index tells
the model that the award filter takes the number as the funder writes it
(NSF 1754803) and that a prefixed form is tried both ways, that missing
grants mean none deposited and a count by funder counts only deposits, that
a 429 is the day's budget spent, and to cite the DOI. Searches and counts
are cached for an hour, works and reference lists for a day; 50 a page at
most.

### pubmed

NCBI's E-utilities for PubMed (`esearch`, `esummary`, `efetch` at
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/) and the PMC ID converter
(https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/). No key is
needed: NCBI allows 3 requests a second to everyone without one, and an
optional NCBI key (the person's own as a bearer token, or
`AI4RA_MCP_PUBMED_KEY`) is sent as `api_key` for 10. `pubmed_search` takes a
PubMed query with its fields (`AI135270[Grant Number]`,
`University of Idaho[Affiliation]`, `Smith J[Author]`) and an optional
publication date range, and returns each paper's citation, PMID, DOI, PMCID
and PubMed link, newest first, 1-50 a page. `pubmed_summary` gives the same
for PMIDs already in hand (up to 50), such as the ids NIH RePORTER's
`nih_publications` returns. `pubmed_article` reads the full PubMed XML
record for up to 20 PMIDs: the abstract with its section labels, authors
with affiliation and ORCID, journal and date, MeSH headings with their
qualifiers and major-topic flag, keywords, publication types, and the
grants the paper acknowledges as the journal or NIH recorded them (grant id
as the agency writes it, acronym, agency, country), which `esummary` does
not carry and which is how a paper is tied to an award or found to
acknowledge none (`grants_listed` false means the record has no grant list
at all, not that the work was unfunded); PMIDs the response does not carry
come back as `not_found`. `pmc_id_convert` takes up to 200 PMIDs, PMCIDs
and DOIs in any mix, converts among them (one idconv call per id type, since
the API takes one type a call) and says which have no PMCID. Every call
carries `tool=ai4ra-mcp` and, when `AI4RA_MCP_CONTACT` is an email address,
`email=` that address (idconv rejects a URL there). Searches are cached an
hour, summaries, records and conversions a day. The index tells the model that NIH
public access (NOT-OD-25-047, effective July 1 2025) needs a PMCID for every
peer-reviewed paper arising from NIH funding, so a paper with a PMID and no
PMCID is the one to chase; that grant searches use the institute code and
serial (`AI135270[Grant Number]`; the RePORTER form `R01AI135270` finds
nothing); and to cite the PubMed link.

### icite

NIH iCite, https://icite.od.nih.gov/api/pubs, the Office of Portfolio
Analysis's citation metrics over PubMed and the NIH Open Citation Collection,
a monthly snapshot, no key; `fl` picks the fields so a call for metrics does
not carry every citing PMID. `icite_metrics` takes up to 100 PMIDs and
returns, for each, the citation count and citations a year, the Relative
Citation Ratio (citations a year against the field citation rate of the
papers co-cited with it, normalised so 1.0 is the median NIH-funded paper of
its year), the NIH percentile of that ratio, whether the ratio is
provisional (under two years old or few citations), the expected citations a
year and field citation rate behind it, the translation measures (the human,
animal and molecular/cellular shares of its MeSH terms, the Approximate
Potential to Translate, and whether a clinical article has cited it), the
first author and author count, and a summary across the set (papers, with an
RCR, citations in total, median and mean RCR, how many at or above 1.0, how
many provisional). `icite_links` gives one paper's citing PMIDs, its
references and the clinical articles among its citers, with full counts and
the lists cut at 500. The API answers a PMID it does not hold by leaving it
out, and an overlong number with a different paper, so every record is
matched to the PMIDs asked for and the rest come back as `not_found`.
Records are cached a day. The index explains the ratio and the percentile,
says to quote the provisional flag with a value, that citation counts are
PubMed-to-PubMed only, and that iCite takes no DOIs (`pmc_id_convert`
first). Offline tests run on three records captured in
`tests/fixtures/icite/`.

### crossref

The Crossref REST API, https://api.crossref.org/, no key; a `mailto` on
every call puts the server in the polite pool. Works by words, author name
or Funder Registry id, with years and type, most relevant first: DOI, title,
authors (ORCID and affiliations when deposited), journal, year, publisher,
volume, issue, pages, the funders with their award numbers, and citation
count; one work by DOI, exact and free, with its abstract (JATS stripped),
license URLs, ISSN and reference count, and whether it has been retracted;
`crossref_updates(doi)` for whether a work has been retracted, corrected or
given an expression of concern, each notice with its type, date and DOI,
read from the work's `updated-by` (which Crossref fills from publishers'
deposits and the Retraction Watch database, open since 2023) joined with the
notices that name the work (`filter=updates:<DOI>`), and for a notice the
work it updates; the answer says no record is not a clean bill. Tested on
the Wakefield paper: a 2004 correction and the 2010 retraction, both from
Retraction Watch. Funders by name with the registry
id, its alternate names and location. The registry id is the one Crossref,
OpenAlex and ROR share, and its DOI is 10.13039/<id>. Crossref keeps titles
as lists and dates as date-parts; the tools flatten both. The index tells
the model that a work's funders are what the publisher deposited, that
author matching is by words, and to cite https://doi.org/<DOI>. Searches
are cached for an hour, records and funders for a day; 50 rows a page,
offset at most 10,000.

### datacite

DataCite, https://api.datacite.org/dois, the registry of DOIs for datasets,
software, preprints, reports and other research outputs, a JSON:API with no
key: filters `affiliation-id` (a ROR, matched on creators' affiliations, with
`affiliation=true` so the names come back), `funder-id` (a Crossref Funder
Registry DOI), `resource-type-id` (dataset, software, text, image, ...),
`published` (a year range), and `query` in Elasticsearch syntax over the
metadata, which is how an award is found
(`fundingReferences.awardNumber:"1754803"`); `sort=-created` when no words
are given, relevance when they are. Every record carries what the
repository deposited: creators with affiliations and ORCIDs, publisher,
year, DataCite's general type and the depositor's own, description,
subjects, funding references with award numbers, related identifiers (the
paper a dataset supplements), license, sizes and formats, and DataCite's
citation, view and download counts. The University of Idaho's own DOIs
(prefix 10.60841, 933 records with its ROR on 2026-10-16) are minted
through VERSO and resolve to it. `datacite_search(query, affiliation_ror,
funder_id, award_number, resource_type, from_year, to_year, page,
per_page)` lists records 1-100 a page with `next_page`; `datacite_doi(doi)`
gives one in full, and says of a DOI DataCite does not hold that it is
likely a Crossref DOI (the crossref server). Searches are cached an hour,
records a day. The index tells the model what DataCite holds and does not,
that an institution's count is a floor since a repository that deposited no
ROR leaves its records out, what the counts mean, and how a data management
and sharing plan's outputs are found (by award number, or by affiliation and
type dataset in a period). Offline tests run on records captured in
`tests/fixtures/datacite/`.

### re3data

re3data, the Registry of Research Data Repositories,
https://www.re3data.org/api/beta/, XML, no key: about 3,000 repositories
described in the registry's own schema (version 2.2). The list call,
`/repositories`, takes `query` and the registry's facets as repeated
parameters (`subjects[]`, `contentTypes[]`, `countries[]`, `dataAccesses[]`,
`pidSystems[]`, `certificates[]`) and returns every match's id, DOI and name,
unpaged; the record call, `/repository/<id>`, returns one repository: name,
URL, description, type, subjects in the DFG classification as the registry
writes it (`2 Life Sciences`, `20105 General Genetics`), content types,
keywords, data access and upload terms (open, restricted, embargoed,
closed), data licenses, persistent identifier system, certificates
(CoreTrustSeal and the like), APIs, the institutions behind it with their
roles and RORs, size, start date, versioning, quality management, citation
guideline, policies and last update. `re3data_search(query, subject,
content_type, country, data_access, pid_system, certificate, rows)` reads
the list and then the first rows' records together, 1-25 a call, with the
total and the rest named by id in a note; `re3data_repository(id)` reads one.
Both cached a day. The index tells the model how subjects are named, what the
access and identifier fields mean for a data management and sharing plan
(open access and a DOI), that a search is as many requests as rows, and to
confirm deposit terms on the repository's own site. Offline tests run on a
list and two records captured in `tests/fixtures/re3data/`.

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
comes from the `X-Total-Count` response header. `osti_record` is one record
with its abstract, subjects and availability. OSTI rate-limits aggressively
(a 429, or a dropped connection, on a second quick request), so the server
sends one request at a time behind a lock, caches searches an hour and
records a day, and turns a dropped connection into a plain "wait a minute"
answer. The index tells the model that DOE award terms require accepted
manuscripts, reports and data to be in OSTI under the award's contract
number, so `doe_contract` is the search for "what did this award report";
the product types; the date formats; the pace; and to cite the OSTI link and
the DOI.

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

### github

No upstream of its own: GitHub's remote MCP server holds the tools, and a
browser client reaches it through a proxy on its own host. This server is
the two skills that run over those tools, served as prompts and through
`github_guide`, so that a client lists them beside GitHub's tools rather than
under `general`. `code-change` makes a described change to a repository as a
pull request: it reads the files first, commits the whole changed files to a
new `agent/<login>/<slug>` branch, opens the pull request against the default
branch, starts the checks or a named workflow and reports the links; it never
writes to the default branch, never merges, never waits for checks and never
commits a secret, and the person reviews and merges. `actions-check` is one
look at a repository's Actions: the latest runs on a branch, pull request or
workflow with status, conclusion and links, and for each failure the job, the
step and the first real error from the failed jobs' logs; a snapshot, never a
wait, with reruns or cancellations only when asked by name. Both declare
their short inputs as prompt arguments. Their `requires` name GitHub's tools
(`get_me`, `get_file_contents`, `search_code`, `create_branch`, `push_files`,
`create_pull_request`, `actions_list`, `actions_get`, `get_job_logs`,
`actions_run_trigger`), which GitHub has renamed before; a rename breaks the
skills until the names are updated here. A keyed server over the REST API
with tools of its own is #42, not decided.

### uidaho

The policy site is plain HTML with a stable address scheme, which is what
makes a search-and-cite layer cheap:

| Source | Landing page | A policy | Header fields |
|---|---|---|---|
| APM | `uidaho.edu/policies/apm` lists chapters 01–95 (45 is Research Office) | `uidaho.edu/policies/apm/45/06` is APM 45.06 | Owner (position, email), `Last updated: <Month D, YYYY>` |
| FSH | `uidaho.edu/policies/fsh` lists chapters 1–6 (5 is Research Policies) | `uidaho.edu/policies/fsh/5/5100` is FSH 5100 | same |

- `uidaho_guidance_index`: where a policy question starts, with a chapter
  (`APM 45` is sponsored projects); the tool, its usage notes and the
  server's instructions all say so, since "read the index first" had a
  check make a call with no chapter before the one it needed (#21). With no
  chapter: both sources chapter by chapter with URLs, where the rate
  documents are, and the usage rules. With `chapter`
  (`APM 45`, `FSH 5`, any chapter listed) it is that chapter's index: every
  policy with what it covers and its `Last updated` date. What a policy
  covers is the opening sentence of its own text, without the label the
  page gives it (a Purpose, a Preamble, an Introduction; a contents list is
  passed over), cut at 200 characters. One sentence and no address, because
  every check reads the listing whole: APM 45 was 9,736 characters with a
  paragraph and a URL for each policy and is 7,253 now; a policy's address
  comes with its text when it is read. This is how the policy
  that governs a statement is found: a model reads the index and chooses by
  what each policy covers, which matches on meaning with no embedding model
  and no list kept by hand. The index is built from the policy pages when
  asked for (APM 45 is 24 policies, under three seconds cold) and the pages are cached for a day; a page that cannot be
  read is listed under `unread`, not left out. A page with no opening prose
  (two of 354: a pointer to another page, a link to a chart) gives the first
  line it has. The starter citations, ten policies listed by hand, are gone
  (#18).
- `uidaho_guidance_search`: policies by number or title words, as listed in
  each chapter's index. It does not search policy text; the skill reads a
  likely policy and looks there.
- `uidaho_guidance_get`: one policy as clean text by number (`APM 45.06`,
  `FSH 5100`), with its owner, `Last updated` date and URL. A short policy
  comes back whole; one over 6,000 characters as an outline
  of its own sections, the lettered ones and the numbered ones under them
  (`"9830: E-1. Salaries"`), read from the text; a section is then read to
  its end by its offset, as a long section of the eCFR is, and returns its
  `pinpoint` (`APM 45.06 E-1`). APM 45.06 is
  17,377 characters, its first call about 1,500, and E-1 reads as 1,286. A
  contents list at the top and a lettered list inside a section are passed
  over, since sections come in order. The first two-source check read about
  77,000 characters of policy for three sentences, most of it whole
  policies for one clause each (#21). The reader is shared with the ecfr
  server (`common/text.py`).
- `uidaho_salaries`: the Budget and Planning Office's salary book, the
  published PDF of every filled position's salary for the newest fiscal year
  that has one (FY2026, as of May 14, 2025, when added 2026-10-16), linked from
  the budget-planning page's budget books and read whole once a day: lines
  matching a name, title or department, each with name, title and rank, FY or
  AY basis, the annual salary, whether an administrative stipend is paid, and
  the division, unit and department lines above it, with the book's fiscal
  year, as-of date and link. For a budget's salary line (a named
  co-investigator's institutional base salary, what a title is paid), never a
  listing by itself.
- `uidaho_rates`: the F&A rate agreement PDF (`fa`) or the fringe-rate page
  (`fringe`) as text. The agreement comes as its Sections I and II (the
  rates by type and location, the base, the fringe rates, the special
  remarks on off-campus work and equipment), 5,422 characters; Section III,
  general terms and signatures, a third of the text, is left out, and the
  result says so in `trimmed_to`. The agreement is read at the address the F&A page
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
rates and reports them in the Rates contract's order with their dates and
addresses; a document that could not be read leaves its items without
values, marked "not fetched". Neither skill carries fallback figures.
`policy-check` checks a passage of a document against the APM and the FSH
as fetched and reports a finding for each sentence that disagrees with a
policy, in the findings contract's form: it finds the
policy from the chapter's index, reads it, and quotes the clause. A
sentence that states an F&A or fringe rate is compared with the rate
agreement or the fringe-rate page by `uidaho_rates` inside the same check
(0.2.0), so a client runs no rates skill first. It is
the university's sibling of `cfr-check` on `ecfr`; a client that runs both
on one passage can put the two findings for a sentence in one place.
Writing the rates onto a sheet, and the eight-step proposal workbook that
ran skills from the general, ai4ra and uidaho servers in order, are Idaho's
mindrouter-365-aware server's (cell 2 of the grid; mindrouter-365 #39) and
left here on 2026-09-30. The
award skills that read Banner exports (award-facts, award-lines,
award-status, award-review, pi-awards, current-pending,
current-pending-support, and pi-memo on ai4ra) were removed on 2026-09-30
(#12): none of them worked, and all were Excel-bound, which under the
server-and-client rule is client code; they are in git history.

`feature-prd-interview` (#32, 2026-10-07) interviews a subject matter
expert about one OpenERA feature and writes the definition into the
feature's ClickUp task: thirteen headings, acceptance criteria in Gherkin
read back in plain English, the AI first pass taken apart section by
section, a blind second reviewer compared and reconciled when a feature has
two assignees, and the finished criteria fingerprinted against the index
task rather than against other features' documents. It never takes an
attachment or the contents of a real record. It is cell 3 of the grid: no
host tools, Idaho's own knowledge. Every fact of the work (the OpenERA
list, the `feature` tag, the subtask names, the thirteen headings, the
Basis tags, the index task, the Data Sensitivity field) is in the
`openera-feature-guide` guide beside it, fetched first through
`uidaho_guide`, so the skill's text names none of them and the guide is the
one file that changes when the list or the index moves. Its ClickUp work is
the `clickup` server's tools, named fully qualified
(`clickup:clickup_task`), so a client needs both servers connected and the
`clickup` deployment's writes on. It was converted from a `.skill` package
written for claude.ai; its two reference files were methods, so they are
sections of the prompt, since a guide is never a method.

### classes

The University of Idaho class schedule and course catalog: who teaches
what, when and where, and what a course is. The upstream is Banner Student
Registration Self-Service at `banner.uidaho.edu/StudentRegistrationSsb`,
whose two open modes, Browse Classes and Browse Course Catalog, need no
login and are read through the pages' own interface (routes confirmed
without a login on 2026-10-13 and 14):

| Route | What it returns |
|---|---|
| `classSearch/getTerms` | the terms, newest first; one closed to registration says `(View Only)` |
| `term/termSelection?mode=<search or courseSearch>`, then `term/search` with the term | a session cookie with the term bound to it, in the schedule's mode or the catalog's |
| `classSearch/get_instructor?searchTerm=<one word>` | the instructors whose name matches, each with an id numbered within the session |
| `searchResults/searchResults` by subject, course number and instructor id | `totalCount` and the sections, each with its instructors (name, email, primary), meetings, credits and enrollment |
| `courseSearchResults/courseSearchResults` by subject, course number and keyword | `totalCount` and the catalog's courses, each with its college, department, credits and effective terms; the keyword matches a word of the title or the description, and the title field only a whole title |
| `classSearch/resetDataForm` | clears the schedule's search; without it a second search on the session answers with the first's results. In the catalog's mode it does nothing, so a session there serves one search |
| `searchResults/get…` by term and CRN, twelve panels: description, class details, prerequisites, corequisites, restrictions, cross-listed sections, linked sections, attributes, fees, bookstore, enrollment (HTML) and meeting times (JSON) | one section's panels |
| `courseSearchResults/get…` by term, subject and course number, six panels: description, prerequisites, corequisites, restrictions, attributes, fees (HTML) | one course's panels |

Because the instructor ids are the session's and the form holds the last
search, every call opens its own session in the mode it needs, selects the
term, does its lookup and its search there, resets the form and closes.
Results are cached ten minutes on their arguments, the term list an hour.
No key is taken and nothing about the caller is sent. Canvas was looked at
and set aside for this question: its tokens are the person's whole account.
Course materials are not here: Banner's bookstore panel carries no
materials, only a link to the Day One Access list, and the VandalStore's
storefront sits behind a bot check; a materials tool waits on a feed from
the bookstore (#36).

- `classes_index`: the upstream, the five tools, the current term (the
  newest open to registration) and the caveats: this is a page's internal
  interface, not a published API, so a Banner upgrade can change a route
  and a tool whose route stops answering returns the status and the route;
  instructors are matched by name and never guessed; the schedule knows
  sections and the catalog knows courses, neither degree requirements or
  anyone's enrollments; the two disagree at the edges (a course with no
  sections this term, a section whose catalog entry has ended), so every
  result says which it read in `read_from`.
- `classes_terms`: every term the schedule has, newest first, with code,
  name and `view_only`, and `total`; the whole list, paged out of Banner
  until a short page and cached an hour, so how far back the schedule
  reaches is read from it and a term a person names resolves however old
  (#43: the newest ten by default had a model say the schedule began at
  Fall 2024). The same list resolves a term for every other tool.
- `classes_search`: sections by `subject`, `course_number` or `instructor`
  (at least one), for a `term` by code or name, or the newest open term
  when empty; `rows` up to 100 a page with `next_start`. Each section is
  CRN, subject, number, title, section, credits (Banner's fixed hours or
  its low-high range), campus, schedule type, method, instructors with
  email, a `meets` line (`MWF 10:30-11:20 RENFREW HALL 111`, `TBA` when
  unscheduled), enrollment, capacity, seats, waitlist, part of term. An
  instructor is looked up by one word (a `Last, First` name's surname, or
  the last word) and chosen from Banner's list: one match is searched; a
  full name among several is searched; several otherwise come back as
  `instructors_matched` with an error saying to pass one in full, and no
  match is said. Nothing is guessed.
- `classes_section`: one CRN's catalog description, details (campus,
  schedule type, method, section, credits, grade mode), meetings (days,
  times, building, room, dates, instructors), prerequisites as one line
  with Banner's And/Or and parentheses, corequisites, restrictions as the
  registrar publishes them (one string a rule, the majors, colleges,
  levels, cohorts or campuses named), cross-listed and linked sections as
  CRN, subject, number, title and section, attributes, fees as description
  and amount, the Day One Access link, and enrollment counts, the HTML
  panels read down to fields.
- `classes_catalog`: courses by `subject`, `course_number` or `keyword`
  (a word of the title or the catalog description; at least one), for a
  term, paged like the search: subject,
  number, title, credits, college, department, levels, schedule types,
  grade modes, attributes, whether the course has sections this term, and
  its effective terms. The catalog's answer when a person names a topic
  rather than a section.
- `classes_course`: one course by term, subject and number: the catalog's
  record (title, credits, college, department) with its description,
  prerequisites, corequisites, restrictions, attributes and fees. A course
  the catalog does not list for the term is said.

Offline tests run on the responses captured in `tests/fixtures/classes/`;
the live site is the only test of the routes themselves.

### directory

The University of Idaho campus directory: who a person is at the
university and how to reach them at work. The upstream is the directory at
`directory.uidaho.edu`, whose advanced search form needs no login for
employees and is read through the form's own parameters (confirmed without
a login on 2026-10-15):

| Route | What it returns |
|---|---|
| `advanced` | the form, whose department list is every department the directory knows |
| `search?tab=advanced&pt=emp` with `LastName`, `FirstName`, `email`, `dept`, `SoundsLike`, `depth` (10, 20 or 30) and `offset` | `N matches were found` and a table of people (name, university email, phone, department, status), or, when exactly one person matches, that person's details (phone, email, title, department, office, campus zip) in place of the table |

Each name field matches as a prefix (`Lay` finds Layman); `email` matches
the address or its start; `dept` is one of the form's own names or `All`;
`SoundsLike` matches a last name by its sound. `pt` is always `emp`: the
page shows students only after the university's login, which this process
never has, so students and student employees are not here. Results are
cached ten minutes on their arguments, the department list a day. No key
is taken and nothing about the caller is sent.

The page also carries an internal identifier for each person (Banner's
PIDM) in its popup attributes, its detail links and its autocomplete
JSON. Nothing here reads, keeps, follows or returns it: the detail route
and the autocomplete are not used, the table is read for its visible
cells, the test fixtures carry it zeroed, and a test holds every result and
every cache key to carrying none of it. Its presence was reported to the
university as a defect on 2026-10-15 and is not assumed either way: the
server reads only what a visitor sees, which a fix would leave.

- `directory_index`: the upstream, the three tools, the caveats: a page's
  own form, not a published API, so a change to the site can alter a route
  and a tool whose route stops answering returns the status and the route;
  employees only, so a student is not here and is not said to be absent
  from the university; the fields are the page's own and nothing more;
  several matches come back as a list, never a guess.
- `directory_search`: people by `last_name`, `first_name`, `email` or
  `department` (at least one), with `sounds_like`; `rows` 10, 20 or 30 a
  page (another number rounds up) with `next_start`. A department is
  matched against the directory's list: an exact name, or one name the
  fragment appears in; several come back as `departments_matched` with an
  error saying to pass one in full, none is said. One match returns the
  person's details in place of a row, with a note saying so.
- `directory_person`: one person by enough of a name, an email or a name
  with a department: name, university email, phone (null when unlisted),
  title, department, office and campus zip. Several matches come back as
  the list to narrow from; none is said. The directory shows only the
  first 30 characters of a title ("Director, Office of Sponsored", seen
  2026-10-16), so such a title comes with `title_truncated` true and the
  index says to quote it as shown and never complete it.
- `directory_departments`: every department the form lists, as it names
  them, with `total`.

Offline tests run on the pages captured in `tests/fixtures/directory/`,
with the result rows anonymised; the live site is the only test of the
routes themselves.

### events

The University of Idaho campus calendar: what is happening on campus and
when. The upstream is the calendar at `uidaho.edu/events`, a Trumba
calendar whose public JSON feed,
`https://www.trumba.com/calendars/university-of-idaho.json`, carries every
event the university's calendars publish (the main calendar, Registrar,
College of Graduate Studies, Alumni Relations, the colleges, Student
Affairs and the rest), each with its title, start and end in campus local
time with the UTC offset, all-day flag, location type (In-Person, Online,
Hybrid) and location, the campus room and online link as custom fields,
the owning calendar, the description, the event's own link, registration
flags and, for a repeating event, the rule and a series id. No login, no
key. The feed's parameters, confirmed 2026-10-16: `startdate` and
`enddate` as YYYYMMDD, or `days` or `months` from today; `search` for
words anywhere in an event's text (a quoted phrase matches nothing);
`eventid` for one event; `events` for the most to return, 200 when not
given, so this server asks for 500 and says when a window reached it. The
feed has no calendar parameter, so a calendar filter is applied here on
the `categoryCalendar` each event carries.

- `events_search(search, start, end, days, calendar, rows)`: the events in
  a window, soonest first. With nothing given, the next 30 days; `start`
  with `end`, or `start` with `days`, or `end` from today; dates are
  YYYY-MM-DD. Each event is a short row (a month of the whole campus is
  some three hundred events, seen in the first live test on 2026-10-16):
  id, title, start, end, all_day, canceled, location_type, location (the
  campus room when the calendar gave one, else the location line),
  online_link, calendar, a description cut at 160 characters, the event's
  own web_link (for a game, its schedule and ticket page) and its calendar
  link; repeats and series_id on a recurring one; contact and registration
  when the event carries them. `rows` 1-200, default 50, with a note when
  the window held more. Athletics is in the feed: the sport's name as the
  words lists the games (a home game is often posted all-day, with the time
  only on the athletics page).
- `events_closures(start, end, days)`: the days the university is closed in
  a window, the next 120 days by default. A holiday question through the
  pane first went by way of a guessed calendar name ("Campus Closed",
  refused by the client's guard, then "University Closures" from the list;
  2026-10-16), and a calendar's name is the owner's to change or misspell,
  so this tool searches the feed for the words closed, closure and holiday
  and keeps the events whose title or calendar says closed or closure, or
  whose calendar is named for holidays or closures; a holiday concert or a
  holiday trip is not one. One call, no name to know.
- `events_event(id)`: one event in full: the whole description, when as the
  calendar words it, the timezone offset, campus_location, image.
- `events_calendars(months)`: the calendars that feed the university's,
  each with its event count over the coming months (default three), the
  names a `calendar` argument is matched against.

HTML in the feed (links, entities, italics) is read to plain text and the
first `href` where a link is the value. A window is cached ten minutes, the
calendar list an hour. The index tells the model that times are campus
local, Pacific (an earlier caveat said Mountain; the feed's own labels read
PDT, corrected 2026-10-16), that a window with no filter is the whole campus, that the flags
say nothing about who may attend, and to cite an event by title and date
with its link. Offline tests run on nine events captured in
`tests/fixtures/events/feed.json` with contacts anonymised; the live feed
is the only test of the parameters themselves.

### campusmap

The University of Idaho campus map: where a place is. The university's map
is Concept3D map 2155 (`map.concept3d.com/?id=2155`, embedded at
uidaho.edu), and Concept3D's JSON API,
`api.concept3d.com/locations?map=2155` and `/categories?map=2155`, answers
with the key the map page itself sends from its public script, a client key
served to every visitor and good for reading the map's points. It is
Concept3D's, not the person's, and is held here as the map page holds it;
the decision to use it is recorded on #45 (2026-10-16), and when Concept3D
rotates it the osm server's geocoding stands in, which the error says. The
map has about 3,600 points in 130 categories: 323 buildings in the
alphabetical categories (A, B - D ... T - Z) each with the university's
building number, building addresses, departments and colleges, accessible
entrances and automatic doors, restrooms, elevators and nursing rooms,
parking by kind, bike racks, EV charging and transit stops, dining,
athletics, health, study spots, memorials and trees; the editors' working
categories (QC, drafts, labels, traces, edits) are hidden. The map has no
routing of its own (its directions run on Mapbox under Concept3D's keys), so
a route between two places is the osm server's `osm_route` with the points
from here. `campusmap_search(query, category, rows)` matches words of a name
and a category; `campusmap_near(lat, lng, category, radius_m, rows)` lists
what is within a straight-line radius of a point, nearest first;
`campusmap_place(id)` gives one place with its nearest accessible entrances,
parking and restrooms; `campusmap_categories()` the categories with counts.
The two lists are read once a day. The index says how the map names a
building (surname first, the given name in parentheses: `Albertson (J.A.)`,
`Pitman Center (Bruce M.)`), that distances here are straight-line, and to
cite a place by its map name and link. Offline tests run on the categories
and a cut of the locations captured in `tests/fixtures/campusmap/`.

### costs

What the University of Idaho charges, from five pages on www.uidaho.edu
read as HTML and cached a day, no key: Student Accounts' student billing
page (the per-semester tuition and fee schedule by student group, the
summer and winter per-credit rates, the prior year's schedule, the late fee
schedule by term and the refund schedule), its account payments page (the
payment plan rules), Financial Aid's cost of attendance page (the estimated
annual cost tables by student type and program) and Student Health
Services' SHIP page and insurance requirement page. The pages are the
university's content management system, so the server reads each into its
headings, accordion labels, paragraphs, lists and tables (`blocks`,
`sections`) and returns a section's lists as labelled items ('Full-time
(9-20 credits)': '$5,898') and its tables by column, under the page's own
headings. `costs_tuition(schedule, students)` is the schedule for the
semester (by student group; the insurance fee group, a sentence on that
page rather than a rate list, carries its text and names `costs_insurance`),
summer, winter or the prior year; `costs_attendance(students)` the cost of attendance tables, filtered by
words with punctuation ignored ('MBA' finds 'M.B.A.'); `costs_deadlines`
the late fee dates by term, the due sentences, the refund schedule and the
payment plan rules; `costs_insurance` the SHIP premiums by period, coverage
dates, dependent rates and the requirement. Every answer carries the page
URL, the heading it was read from and the day it was read, so a figure is
checked against the page when the university changes it; a page down or a
heading gone is said with the link. Fringe and F&A rates for budgets are
the uidaho server's. Offline tests run on the five pages' main content
captured in `tests/fixtures/costs/`.

### library

The University of Idaho Library's catalog: Primo VE on the Orbis Cascade
Alliance's Ex Libris host, `alliance-uidaho.primo.exlibrisgroup.com`, read
through the public REST endpoint the discovery page itself calls
(`/primaws/rest/pub/pnxs`), no token or key. `library_search(query, field,
type, available, scope, sort, offset, rows)` is the catalog's hits by words,
title, author, subject, ISBN or ISSN, narrowed to a resource type (books,
articles and the rest of Primo's facet) or to physical copies on the shelf
here, in the Everything scope (the local catalog and the central index
together), Course Reserves or Special Collections and Archives; each hit
with id, title, creators, type, publisher, year, format, ISBN or ISSN, DOI,
the journal citation for an article, subjects, Primo's availability code
with what it means in the catalog's own terms (on the shelf here at a
library, location and call number; no copy held here; online through the
link resolver), the best physical copy's location, the link resolver and
the record's catalog page; totals for the local catalog and the central
index separately. `library_record(id, context)` is one record in full with
its summary, table of contents, subjects and every holding, by the id
`library_search` gave (`alma…` local, `cdi_…` the central index), stated as
given. Verso, interlibrary loan and a person's account are not here, which
the index says. Searches and records are cached an hour, since availability
changes. Offline tests run on searches (physical items with locations, a
local-and-central mix, shelf-available, articles, no hits) and records
captured 2026-10-19 in `tests/fixtures/library/`.

### lakehouse

The University of Idaho data lakehouse through Marina, its query and file
API at `http://nlayman.nkn.uidaho.edu:7010` (`AI4RA_MCP_LAKEHOUSE_URL`),
reachable on campus, which is why this process reads it and a browser never
does. Every request needs an OAuth 2.0 bearer from `/auth/token`, minted with
HTTP Basic from a client id and that client's shared secret. The secret is
the key a person pastes into the pane, sent as the bearer on the MCP call,
exchanged here for a Marina token that is kept in memory until it expires
and never logged; `AI4RA_MCP_LAKEHOUSE_SECRET` is a deployment's fallback. It
is one client's secret, not a personal key, so its rate limits (100 requests
a minute, 1,000 an hour) are shared by everyone who uses it.

The key may also name the client (2026-10-02). A bearer of the form
`<client id>:<secret>` runs the request as that client of Marina's, with
that secret, so a person authorized for another client uses the same fold
with no deployment change; a bearer with no such prefix is the mounted
client's secret, and a request with no bearer falls back to the deployment's
secret for the mounted client, as before. The part before the first colon
is taken as a client id only when it has the shape of one (letters, digits,
dots, hyphens and underscores, up to 64), so a secret that happens to hold a
colon is still read whole. Marina decides whether the pair is good; a wrong
pair gets its refusal. `lakehouse_index` reports the client the request ran
as, and so does every catalog answer.

Marina authorizes a client for streams, and a secret belongs to one client,
so each client is its own server here: its own path, its own fold in the
pane, its own key. `AI4RA_MCP_LAKEHOUSE_CLIENTS` lists the client ids to
mount, comma separated (default `mr-365`); the first is mounted at
`lakehouse`, the rest at `lakehouse-<id>` (the id lower-cased, runs of other
characters as one hyphen), with `AI4RA_MCP_LAKEHOUSE_SECRET_<ID>` (the id
upper-cased, runs of other characters as one underscore) as each one's
fallback. Today one client is configured, `mr-365`, whose streams the tools
discover (`personnel` is one). A different Marina is `AI4RA_MCP_LAKEHOUSE_URL`
in the VM's `.env`; all instances share the same tools and the same skills
folder.

Marina scopes access by stream: a client is authorized for querying streams,
each of which exposes a set of tables through a wrapper view (columns masked,
rows filtered, some filters required) and a set of files by tag, and for
submitting streams that accept records and files. `lakehouse_streams` lists
both; `lakehouse_schema` gives a querying stream's tables and columns;
`lakehouse_query` reads one table with Marina's own filter syntax (equality,
`gte`, `in`, `ilike`, `is_null` and the rest), paging with a total count,
and aggregates (COUNT, SUM, AVG, MIN, MAX) per group, or as one row of
totals when no `group_by` is given, which the tool runs as one SELECT through
the SQL gateway; `lakehouse_files` and
`lakehouse_file` read a stream's file catalog and one file as text. Rows are
capped at 500 and 30,000 characters a call. Nothing is written: the
submitting streams are listed but not used, because a remote write would run
behind no confirmation card in the pane. The `lakehouse-answer` skill is the
way a question is answered: the catalog's layers first (streams, one
stream's tables, one table's columns), then a filtered or aggregated query,
every figure with its stream, table, filters and date. An aggregate is typed
in the tool's schema: `fn` (exactly COUNT, SUM, AVG, MIN or MAX), `column`
and `alias`, so a model fills the keys from the schema rather than the prose.

**SQL.** Marina also speaks v1 of the Trino HTTP statement protocol at
`/sql/v1/statement`: one schema per querying stream, named for the stream
(since Marina's PR #382 of 2026-09-29; the earlier `client_<id>__<stream>`
form is refused), one table per allowed source table under its own name, so
a table is `lakehouse."subaward"."<table>"`, both parts quoted since a
stream name may carry a hyphen; rows are filtered and columns masked by a
policy Marina inlines at query time, and a statement may reference one
stream's tables only. Marina's keyword guard is textual, so INSERT, SET,
USE, CALL, ROLE and the rest are refused even inside a string literal or as
an alias. The stats table, `lakehouse."<stream>"."_stats"`, is evaluated by
the gateway itself and takes SELECT with WHERE, GROUP BY, ORDER BY, LIMIT
and the simple aggregates over itself, no Trino-only function and never a
data table in the same statement (#13). The
endpoint takes HTTP Basic with the client id as the user and the Marina
bearer as the password (a Bearer header is refused), a `text/plain` body, and
answers page by page through `nextUri`. Two tools sit on it:

- `lakehouse_sql_catalog` is the survey, in three layers so any answer fits a
  conversation: with no arguments, every querying stream with its table count
  and total rows (`rows` is null and `rows_measured` given while Marina has
  tables it has not measured, since a partial sum is not a size) and the
  largest tables across all streams; with `stream`, that
  stream's tables by row count (column names inline when it has 40 tables or
  fewer), and with `like` as well only the tables whose names match a SQL LIKE
  pattern, since the listing keeps 150 of a stream's tables and the subaward
  stream has 1,656; with `stream` and `table`, every column with its type, description
  and Marina's statistics under Marina's own keys (`null_count`,
  `distinct_count`, `min`, `max`, `mean`, `stddev`, `sum`, `min_length`,
  `max_length`, `empty_count`, `true_count`, `rows_by_year`, each present only
  where measured). A table Marina has counted but not profiled comes back from
  `/query/schema` with no columns at all, so the table layer then reads one row
  through `/query` and names the columns from it, saying so. It is built on `GET /query/schema?stream=` (one call per
  stream, Marina's counts and statistics since its PR #357), never on `SHOW
  TABLES` and `DESCRIBE` per view, which would be thousands of SQL calls on a
  large client. `counts=true` counts only the tables Marina has not measured
  yet, with `count(*)` statements of at most fifty views each (Trino fails
  past a hundred UNION branches); a chunk that fails is reported under
  `count_problems` with Marina's message and the others still count. Tables whose names start with `_` (`_stats`)
  are metadata, read by the gateway, and are never listed as data.
- `lakehouse_sql` runs one statement: a `SELECT` or `WITH`, or `SHOW SCHEMAS`,
  `SHOW TABLES IN`, `SHOW COLUMNS`, `SHOW PROFILE IN`, `DESCRIBE`. One
  statement per call (a second `;` is refused here), DML, DDL, `EXPLAIN` and
  `PREPARE` are refused before sending, and a `SELECT` without a `LIMIT` is
  wrapped in one (never a statement on a `_` table, which the gateway
  evaluates). Rows are capped at 500 and 30,000 characters; a statement that
  passes the cap or `AI4RA_MCP_LAKEHOUSE_SQL_TIMEOUT_S` (60 seconds) is
  cancelled with `DELETE`; each HTTP exchange with the gateway is allowed that
  budget too, since Marina may run the whole statement before its first
  answer. Marina's refusals come back word for word: they are written for a
  model and name the discovery statements. Every failure has a message: the
  REST endpoints' `{"error": "…"}` and the gateway's Trino error (`message`,
  `errorName` or `failureInfo.message`) are passed through, an httpx timeout
  (which stringifies to nothing) is named with the seconds allowed, and a
  status without a message is given a fixed reading. Row counts of many
  tables are one statement, which the tool descriptions and the skill say:
  `SELECT DISTINCT table_name, row_count FROM …"_stats" WHERE table_name LIKE`
  for what Marina has measured, one `UNION ALL` of `count(*)` branches for the
  rest.

Nothing is cached on this server. The conversation is the cache: a catalog
result stays in the transcript and the model refers back to it, so each
result is kept compact rather than remembered. A client is an application
identity: filters and masks are set per stream by the admin and everyone
using the client sees the same views; a person-level scope is a separate
client or stream.

## Skills

A **guide** is a component that says what a correct result is in terms
that name no client: no host, no tool names, no cells, no fills. What a
client does with it, which sheet, which tools, what is confirmed, is the
client's (the server-and-client rule, decided 2026-09-30: anything that
depends on knowledge of the client lives in the client). Its category is
`guide`, and `tests/test_guides.py` holds every guide to that. A guide
reaches a model two ways from the same file: as an MCP prompt named by its
slug, and through the server's `<server>_guide` tool, which lists the
server's components without a name and returns one with a name, so a
client that lists tools but not prompts still gets it and the model can
fetch the guide at the moment the job comes up. The UDM conversion guide
(`udm_guide`), the five proposal guides, the compliance-concerns
vocabulary on `ai4ra` (`ai4ra_guide`), the AI-tells guide on `general`
(`general_guide`) and the OpenERA feature guide on `uidaho` (`uidaho_guide`)
are the guides so far.

A skill is a prompt with a contract: what it needs, what it produces, which
tools it calls. Each lives in its server's `skills/components/<slug>/` as
`prompt.md` (YAML front matter, a preamble with **Purpose**, **Expected
input** and **Expected output**, then the prompt under `## Prompt`),
`README.md`, `CHANGELOG.md` and `evals/`, with an entry in that server's
`catalog.json`. The server serves it as an MCP prompt named by its slug and
as static files under `/<server>/skills/`.

A skill that takes something short from its caller declares it in
`contracts.input.arguments`, each with a `name`, a `description` and
`required`. They are the MCP prompt's arguments, so a client that shows a
prompt as a form (Claude Desktop, Claude Code) asks for them, and a value
given is appended to the prompt's text under its name ("The passage:").
Only the prompt route takes them. `<server>_guide` and the static file serve
the skill's text as it is, for a client that supplies the input in its own
message; a prompt fetched with no arguments is the same text (#28).

Twelve skills declare arguments (#29): the two checks (`passage`, and
`date` on `cfr-check`), `funding-history` (`person`, `institution`, `years`,
`sponsor`), `subrecipient-check` (`entity`, `award`),
`funding-opportunity-finder` (`topic`, `constraints`), `lakehouse-answer`
(`question`), `uidaho-lookup` (`question`, `location`), `uidaho-rates`
(`location`, `type`), `actions-check` (`repository`, `branch`,
`pull_request`, `workflow`, `run`), `code-change` (`repository`, `change`),
`sponsor-doc-defaults-udm` (`sponsor`, `division`) and
`feature-prd-interview` (`feature`). Three rules:

- **Every argument is optional.** A prompt fetched with none is refused by
  no client and returns the text it always did; each skill already says
  what to do when its input is missing (ask, or use a default).
- **A skill whose input is a document or a record takes none**: the cost
  checks, the extraction skills and the budget-justification skills on
  `ai4ra`. An attachment cannot travel in an argument and a structured
  record is too long for a form, so the person supplies the material beside
  the prompt, as those skills' texts expect.
- **A guide takes none**: it is reference a caller reads as data.

A declaration is in this repository's catalog and not in the prompt's text,
so it changes no skill's version and forks no component copied from
AI4RA/prompt-library. `tests/test_servers.py` holds every prompt's listed
arguments to its catalog entry and its text with no arguments to the guide
tool's.

The catalog entry follows AI4RA/prompt-library's shape (`slug`, `summary`,
`version`, `category`, `status`, `paths`, `contracts.output.format`,
`evaluation`) and adds three fields:

| Field | What it says |
|---|---|
| `requires` | The server tools the skill calls, by name (`uidaho_rates`, `udm_schema`); a guide may name another server's tool. Never a client's tool name |
| `triggers` | Words in a request that point at the skill |
| `source` | Where a copied or moved component came from: repository, commit, path |

A client caches the prompt text by version, so a change to a skill bumps
the version in the front matter and the catalog together. The fields a
client acts on for its own skills (`hosts`, `fold`, `template`,
`assertions`, `stages`, `from_context`, `locked`, `excel:` and `skill_`
requirements) are not carried here: a catalog served by an institution's
mindrouter-365-aware server may carry them, and this one never does, which
`tests/test_guides.py` checks for every guide (ai4ra-mcp #10).

**The findings contract.** A check of a document against a source (`cfr-check`
on `ecfr`, `policy-check` on `uidaho`) replies with findings in one fixed
form, so a client can put each on its sentence and join the findings of two
checks without a model. Its catalog entry says `contracts.output.format:
"findings"`. One finding per sentence, a blank line between findings, each
these lines in this order:

```
finding. 2 CFR 200.<section>(<paragraph>)
Statement: "<the sentence's words, copied exactly from the passage>"
"<one clause, copied word for word from the fetched text>" <the address it was read from>
Suggested Fix: <Add | Change | Remove> <what, in the document>
```

The first line is the word `finding.`, the same for every finding, then the
pinpoint in the source's own citation: `2 CFR 200.313(a)`, `APM 45.09 D-4`,
`FSH 5100 B-2` (an FSH policy number has no dot). There is no verdict: a
check surfaces candidate findings, with the evidence beside them, for a
person to verify, and does not rule; `violates.` and `unclear.` stood here
until 2026-10-01 and the split between them held in no run (#26). A
sentence draws a finding when it states something the quoted clause
forbids, or when the clause conditions or requires something the passage
does not show; the clause must itself forbid, require or condition
something, and a finding never rests on a fact the sentence does not state
(#25). The source line is the quotation and its link with nothing before
it, since the pinpoint above it names the source; a client may take any
line of a finding that holds a quotation and is not `Statement:` or
`Suggested Fix:` for a source line. One line for each rule the finding rests on. A finding
holds one sentence to the source: two sentences of the document that
disagree with each other are not a finding, since it would rest on nothing
fetched, and no check reports one (#24). The last line is a suggestion to
the person who verifies the finding and is labelled as one, `Suggested
Fix:` (`Fix:` until 2026-10-01, #27). It opens with
Add (the passage does not show something the clause requires), Change or
Remove (the sentence states something the clause does not allow) and ends
at the change: it gives no
reason and states no rule, since it is the one line nothing can test (#22,
#23). An Add names what the passage is to show and never says that it
exists or was done, since a check knows only that the passage does not
show it, not whether it exists or can be had. So an Add gives the two
other ways out in the same line, in fixed words, and leaves the choice to
the person: "Add the prior approval for the purchase, check with the
Office of Sponsored Programs, or Remove the sentence", never "Add a
statement that prior approval was obtained". The office is the
institution's own on its server (`policy-check`) and "your sponsored
programs office" on a general one (`cfr-check`). A Change or a Remove is
one clause. A closing follows the findings: what was read and as of when, and one
line for each sentence not checked, `not checked: "<the sentence's words,
copied exactly>"` with nothing after it, so a client can match the line to
a sentence and see that none of them also has a finding. Every quotation
is text the check fetched in that turn, and the closing says nothing of
what governs a sentence that was not fetched either (#20). The pinpoint is
not left to be worked out where the server knows it: a part read by its
offset returns `pinpoint` (`2 CFR 200.430(i)(5)`, `APM 45.06 E-1`), which
the check copies and a client can hold the first line to.
`tests/test_findings.py` holds each such skill's prompt to the form, and a
change to it is a MAJOR version of the skill.

**The Rates contract.** A budget form is institution-agnostic: it takes its
rates in one fixed form, wherever a client keeps them. An institution's
rates skill reports seven labelled items in this order, Location, F&A rate,
F&A base, Fringe faculty, Fringe staff, Fringe students, Fringe temporary,
values as fractions, each with the document, the period and the address it
was read from; reference items after them; and a last item labelled Source,
one line naming the documents, their periods and their addresses, which the
form copies beside its rates as provenance. A rate the skill could not read
is present with its label and no value, marked "not fetched", never a figure
from memory. `nsf-budget-guide` says how the form uses it and what it
estimates when an item is missing; `uidaho-rates` is Idaho's reporter;
laying the items onto a sheet is a client's skill.

## Running

```
uv sync
uv run ai4ra-mcp                   # every server on http://127.0.0.1:8000/<name>/mcp
uv run ai4ra-mcp --only uidaho     # a subset (repeatable)
uv run ai4ra-mcp --stdio ecfr      # one server over stdio, for a local MCP client
uv run pytest                      # offline tests
```

Python 3.12 or later. Each server is an `MCPServer` from the official Python
SDK (mcp 2.x). The process mounts each one's streamable-HTTP app at its
path, stateless and answering in JSON, and runs their session managers under
one lifespan. Streamable HTTP is the only network transport.

The tests are offline: every server mounts and lists the tools it promises,
its `given` table names only its own tools and their arguments, the index
answers, CORS answers, the University of Idaho parsers read the
page shapes they were written for, each upstream's record shape is slimmed
as expected from a captured example, a keyed server refuses a request
without a key and takes a bearer token over the environment, the LEIE CSV is
parsed with the download replaced, and the SearXNG answer is slimmed with a
clear error when the backend is down. Nothing in the suite touches the
network.

## Environment

Every variable is optional; the defaults run the process on localhost with
no keys.

| Variable | What it sets | Default |
|---|---|---|
| `AI4RA_MCP_HOST`, `AI4RA_MCP_PORT` | The listening address | `127.0.0.1`, `8000` |
| `AI4RA_MCP_CONTACT` | The contact in the `User-Agent` and the `mailto` that OpenAlex, Crossref and NCBI ask for. Set it to an email address: a URL earns no polite pool and idconv rejects it | the repository URL |
| `AI4RA_MCP_HOSTS` | Comma-separated public hostnames to allow, which turns the SDK's DNS-rebinding protection on. Off by default, since a reverse proxy in front sets the Host header to the public name | unset |
| `AI4RA_MCP_SEARXNG_URL` | The SearXNG that answers `web_search` | `http://127.0.0.1:8080` |
| `AI4RA_MCP_SEARCH_BLOCK` | More comma-separated words or domain fragments for the `web_search` blocklist | unset |
| `AI4RA_MCP_SAM_KEY`, `AI4RA_MCP_FAC_KEY`, `AI4RA_MCP_REGULATIONS_KEY`, `AI4RA_MCP_PERDIEM_KEY`, `AI4RA_MCP_CSL_KEY`, `AI4RA_MCP_GOVINFO_KEY`, `AI4RA_MCP_CONGRESS_KEY`, `AI4RA_MCP_SCORECARD_KEY` | Fallback keys for the required-key servers, used only for a request that sends no bearer token (see [Keys](#keys)) | unset |
| `AI4RA_MCP_BLS_KEY`, `AI4RA_MCP_PUBMED_KEY`, `AI4RA_MCP_OPENALEX_KEY` | Fallback keys for the optional-key servers, likewise | unset |
| `AI4RA_MCP_LAKEHOUSE_URL` | The Marina the lakehouse servers read | `http://nlayman.nkn.uidaho.edu:7010` |
| `AI4RA_MCP_LAKEHOUSE_CLIENTS` | The lakehouse client ids to mount, comma separated; the first at `/lakehouse`, the rest at `/lakehouse-<id>` | `mr-365` |
| `AI4RA_MCP_LAKEHOUSE_SECRET`, `AI4RA_MCP_LAKEHOUSE_SECRET_<ID>` | Fallback shared secrets, the first client's and each other client's | unset |
| `AI4RA_MCP_LAKEHOUSE_SQL_TIMEOUT_S` | Seconds a `lakehouse_sql` statement may run before it is cancelled | `60` |
| `AI4RA_MCP_S2S_ENDPOINT` | The s2s server's default endpoint, used when a call passes none. The compose file sets it to the mock's mutual-TLS port on the compose network | unset: every call must pass one |
| `AI4RA_MCP_S2S_CA_FILE` | The CA that signs the default endpoint's server certificate (the mock's `ca.crt`); other endpoints use the system trust store or the bundle's own `ca` | unset |
| `AI4RA_MCP_S2S_CERT_FILE`, `AI4RA_MCP_S2S_KEY_FILE` | Fallback client certificate and key for a request that sends no bearer bundle; the compose file points them at a mock-minted pair | unset |
| `AI4RA_MCP_S2S_WRITES` | `1` registers `s2s_submit` | unset: read only |
| `AI4RA_MCP_S2S_PRODUCTION` | `1` lets `s2s_submit` reach `ws07.grants.gov`; otherwise production is refused | unset |
| `AI4RA_MCP_LOG_HEADERS` | `1` logs one line per request: method, path, whether an `Authorization` header arrived and was accepted and why not, its fields (form, length, scheme, separator code points, token length, padding) with the credential redacted, the header names, never a credential (see [What a request without a key gets](#what-a-request-without-a-key-gets)); the compose file passes it through from `.env` | unset: nothing logged |
| `SEARXNG_SECRET` | SearXNG's own secret, read by the compose file from the environment or a `.env` file beside it | a placeholder that should be changed |

## Hosting

The intended host is a VM behind Caddy with a campus certificate, the same
arrangement the mindrouter-365 demo uses. Caddy terminates TLS and
reverse-proxies the process on localhost. On a host that already runs its
services as containers, `docker compose up -d --build` at the repo root does
the same for this one, bound to localhost with restart unless-stopped, and
brings up SearXNG beside it (set `SEARXNG_SECRET` in a `.env` file next to
the compose file); otherwise a systemd unit keeps the process up and SearXNG
is yours to run. `deploy/ai4ra-mcp.user.service` runs it as a user service
with no sudo, under the account that cloned the repo (lingering enabled once
so it survives logout); `deploy/ai4ra-mcp.service` is the system-wide form
for an administrator to install. `deploy/Caddyfile` is the site block, in
both forms: the process at the root of its own hostname, or under `/mcp/` on
a host that serves other things. The Dockerfile is for anyone who would
rather run it elsewhere.

The demo deployment: the repository cloned on the VM, `docker compose up -d
--build` for the process and SearXNG, and a `handle_path /mcp/*` block in
Caddy that forwards to port 8000, so the index is at `https://<host>/mcp/`
and each server at `https://<host>/mcp/<name>/mcp`. Shipping a change is a
commit, a pull on the VM and the same compose command; a client's Refresh
then re-reads the server's tools and skills. No upstream key has to be
deployed: each person's client sends their own. The eCFR server's earlier
home, a Hugging
Face Space behind Gradio, is retired: it slept when idle, prefixed every
tool name, and was one more origin to trust.

One thing on the same host is not an MCP server: **grants-gov-s2s-mock**
([AI4RA/grants-gov-s2s-mock](https://github.com/AI4RA/grants-gov-s2s-mock)),
the throwaway Grants.gov Applicant S2S mock that OpenERA's submission code is
built against and that the `s2s` server here talks to by default. It is cloned
beside this repo and runs as one more compose service with two listeners from
one process: plain HTTP on localhost:8081, which Caddy serves under
`/s2s-mock/` with the campus certificate (`deploy/Caddyfile`; no new hostname,
certificate or port), and mutual TLS on port 8443 of the compose network,
which the `s2s` server uses so that a caller without a mock-issued certificate
is refused as Grants.gov would refuse one. The mock mints its own CA and
certificates into `../grants-gov-s2s-mock/certs` on first start; this process
mounts that folder read-only for the CA and its fallback client pair. Set
`S2S_MOCK_PUBLIC_URL` in the `.env` to the public base
(`https://<host>/s2s-mock`) so the WSDL it hands out points back at itself.
Its control API has no auth and is limited to campus addresses by a Caddy
matcher. It is retired, and its blocks and the `AI4RA_MCP_S2S_*` defaults
repointed at training, the day the university's real certificate works
against training.grants.gov.

Clients such as the Office add-in call these servers from inside a browser
engine, so the process answers CORS itself: any origin, any method, and the
`Mcp-Session-Id` header exposed. Public content needs nothing narrower. A
server that must be reachable only on campus is a Caddy rule and a firewall,
not a code branch; the lakehouse servers are reachable wherever the process
is, and it is the Marina behind them that answers on campus only.

## Connecting a client

Three kinds of client read these servers, and the servers tell them apart
in no way: **mindrouter-365**, the base Office client (cell 1 of the grid
under [Rules](#rules)); **an institution's mindrouter-365-aware server**,
built on the pane and adding that institution's own document skills (cell
2; Idaho's does not exist yet); and **any other MCP client**. A skill that
needs only a host's document tools and a server's guide is cell 1; one that
needs an institution's own sources or vocabularies as well is cell 2; what a
correct result is belongs here, as a guide, in cell 3 or 4.

- **The Office add-in (mindrouter-365):** one `indexes` entry in the
  deployment's `sources.json` with the URL of `/`; the pane reads the index
  and lists every server as one fold holding its tools, skills and
  workflows, each with a Refresh that re-reads all three. A keyed server's
  fold carries an *i* dialog where each person pastes their own key; the
  pane sends it as the bearer token on that server's calls and nowhere else.
- **Claude Code:** `claude mcp add --transport http ecfr https://<host>/ecfr/mcp`,
  one server per command; add `--header "Authorization: Bearer <key>"` for a
  keyed server. A server's skills appear as prompts (`/mcp__uidaho__uidaho-lookup`).
- **Claude.ai:** one custom connector per server, added under Customize,
  Connectors (on Team and Enterprise plans an owner adds it under
  Organization settings and members then connect). The walkthrough below
  adds a keyed server; an unkeyed one is the same with no header.

### Adding a keyed server to Claude.ai

Per diem as the example, on the demo deployment, with a personal account.
You need the server's URL and your own api.data.gov key.

1. Open Customize, Connectors, and click **Add custom connector**.
2. Name it (`per diem`) and enter the URL
   `https://<host>/mcp/perdiem/mcp`. Click Continue. Claude.ai probes the
   URL and marks **No sign-in** as *Detected*: these servers run no OAuth.
3. Leave No sign-in selected. The yellow notice that anyone with the URL can
   use the connector is generic to that choice; your key is not part of it.
4. Under **Request headers**, click Add header. Name: `authorization`.
   Value: `Bearer`, then two spaces, then your key. One typed space is
   dropped by that field, so `Bearer <key>` typed with one space reaches
   the server as `Bearer<key>` in one word and the server answers "no API
   key on this request" (seen 2026-10-15, when the request log showed the
   header as `'Bearer<token:40>'`, the key glued to the scheme; reported
   to Anthropic the same day). Two typed spaces both arrive, as
   `'Bearer  <token:40>'`, and the server strips them. The scheme's case
   does not matter to the server. Without the scheme the server ignores
   the value. Mark the header Required.
5. Click **Add**. In a chat, turn the connector on from the + menu and ask
   for a rate (Boise, Idaho, fiscal year 2026). The `gsa_perdiem_index` tool
   reports `on_this_request: true` when the key arrived; a refused key comes
   back as a 401 from api.gsa.gov, which usually means the value lost its
   scheme.

The header value is stored and never shown again, and it cannot be edited:
to change a key, remove the connector and add it again. The Request headers
section is a beta that Anthropic is rolling out gradually; if the dialog is
one screen with only a URL and Advanced settings, the account does not have
it yet, and a keyed server there needs a deployment that holds the fallback
key. On a personal plan the header is your own key; on a Team or Enterprise
plan it is the organization's, shared by everyone who connects.
- **Claude Desktop or another stdio client:** `uv run ai4ra-mcp --stdio <name>`
  as the command, with a keyed server's key in its environment variable.
- **Anything else that speaks MCP over streamable HTTP:** the URL
  `https://<host>/<name>/mcp`, and the `Authorization: Bearer` header for a
  key. A client that reads catalogs by URL takes `https://<host>/` and finds
  every server, catalog and prompt file from there.

## Rules

- **Tools act.** A tool does one mechanical thing against one upstream and
  reports what it found. Which policy or regulation applies to a budget line
  is judgment, and judgment lives in a skill, never in a tool.
- **Tools read.** Every tool is read-only and annotated so. Nothing here
  writes to an upstream, including the lakehouse's submitting streams, which
  are listed and left alone. Two exceptions, each off unless the deployment
  turns it on and each annotated as a write: ClickUp's task writes, and the
  s2s server's `s2s_submit`, which is the one thing that service is for.
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
- **Keys are the person's.** A keyed upstream is called with the key the
  client sent, for that request only. The environment fallback exists for a
  client that cannot send one, and a deployment may leave it unset.
- **Log no keys.** Nothing a person sent as their credential appears in
  any log line at any level. The `httpx` and `httpcore` loggers are held at
  WARNING, since their INFO line is the request's full URL, and a filter
  blanks key-like query parameters from whatever they or the root handlers
  still emit (`log_no_keys` in `common/http.py`, applied at import and at
  startup, with a test in `tests/test_log_no_keys.py`). An upstream that
  accepts a header gets the key there (api.data.gov's `X-Api-Key` for per
  diem); SAM.gov and PubMed want it in the URL, so the filter is what
  keeps it out of the log. Decided 2026-09-30, after the per diem key was
  found in the demo host's container log. The line per request that
  `AI4RA_MCP_LOG_HEADERS` turns on (under *What a request without a key
  gets*) carries header names and the Authorization header's fields with
  every word that is not a scheme word replaced by its length, since any
  such word may be the key; no credential reaches the line whatever a
  client did to it, and no masked or hashed part of one either, since a
  part of a credential is still the credential.
- **Nothing from memory.** A tool that cannot reach its upstream, or has no
  key for it, says so and tells the model to stop there. A skill reports
  only what the tools returned, with the address of every figure.
- **Where a thing lives is decided by two questions.** Does it call a host's
  document tools, and does it need one institution's own knowledge? Decided
  2026-09-30 (mindrouter-365 #33 and #43, #10 here), not to be drifted from:

  |                       | Needs the institution's own knowledge: no | Needs the institution's own knowledge: yes |
  |-----------------------|-------------------------------------------|--------------------------------------------|
  | Calls host tools: yes | 1. The base client (mindrouter-365)       | 2. The institution's mindrouter-365-aware server (Idaho's) |
  | Calls host tools: no  | 4. ai4ra-mcp, a general server            | 3. ai4ra-mcp, the institution's server (`uidaho`, `lakehouse`) |

  This repository is cells 3 and 4: tools over one upstream each, and
  guides that say what a correct result is in terms that name no client.
  The servers tell clients apart in no way: the base pane, an institution's
  mindrouter-365-aware server (from here a client in its own right, since it
  only ever calls in), and any other MCP client all get the same answers.
  The test for any line: would it be wrong if the caller were Claude
  Desktop? Then it is row 1 or 2 and moves. Dependence runs one way: a
  change in a client never requires a change here.
- **Skills stay with their tools.** A skill lives in the server whose tools it
  uses; a guide with no tool of its own lives on `ai4ra` (research
  administration) or `general` (any office). No catalog entry here says
  where a client should list it or which client may run it: `hosts`, `fold`,
  `template`, `assertions`, `stages` and `from_context` are a client's
  fields, and `requires` names only server tools.
- **Be a polite upstream client.** One `User-Agent` naming this project and a
  contact on every request; cache what does not change; on a 429, tell the
  model to wait rather than retrying blindly; one request at a time where
  the upstream asks (OSTI).

## Layout

```
ai4ra_mcp/
  app.py                      mounts /<server>/mcp and /<server>/skills/ for each; GET / is the index;
                              the bearer-token middleware; the picker metadata (label, description, key hint)
  common/
    http.py                   User-Agent and contact, TTL cache, get_json/post_json, the request key and the no-key answer
    fetch.py                  the page reader and grants.gov client
    skills.py                 a skills folder as MCP prompts and as the server's <server>_guide tool
    text.py                   a long text read whole, as an outline of its own headings, or a page at a time; where a part ends
  servers/
    ecfr/
      server.py               MCPServer("ecfr"): tools with read-only annotations, the index tool, prompts
      skills/
        catalog.json          the components, in AI4RA/prompt-library's catalog shape
        components/<slug>/    prompt.md, README.md, CHANGELOG.md, evals/
    general/  ai4ra/  grants/  nih/  sam/  uidaho/  lakehouse/       same shape, with skills (ai4ra has no tools)
    udm/                      schema.py serves the published UDM schema in portions; skills/ holds the conversion guide
    fedreg/  regulations/  nsf/  usaspending/  fac/  csl/  oig/
    propublica/  ror/  perdiem/  bls/  openalex/  pubmed/  crossref/
    orcid/  osti/  clinicaltrials/                                   same shape, an empty catalog
deploy/
  Caddyfile                   the site block, at a hostname's root or under /mcp/
  ai4ra-mcp.service           a system-wide systemd unit
  ai4ra-mcp.user.service      a user-level systemd unit, no sudo
  Dockerfile
  searxng/settings.yml        SearXNG for web_search
docker-compose.yml            the process and SearXNG as two containers
tests/                        offline, one file per server plus the app
```

`notes/` and `admin/` are ignored by git and are for private working files.

### Adding a server

A folder under `ai4ra_mcp/servers/<name>/` with a `server.py` that builds one
`MCPServer` named `<name>` with an `instructions` sentence, registers its
tools with read-only annotations (an `<upstream>_index` tool first), and ends
by calling `register_prompts` on its `skills/` folder (a `catalog.json` with
an empty `components` list is enough) and, when a tool takes an identifier
another of its tools lists, `given` with that table (the index's `given`
field). Add it to `SERVERS` in `app.py` in
the group it belongs to, give it a `META` entry (label, description, and a
`key` block if the upstream wants one), and add its tools to
`EXPECTED_TOOLS` in `tests/test_servers.py` with a test file of its own for
its slimming. A keyed server reads its key with `api_key(KEY_ENV)` and
answers `missing_key(KEY_ENV, KEY_HOW)` from every tool when there is none,
so the bearer-token path works without further code. Its section under
[Server reference](#server-reference) says what upstream it reads and what
its index tool tells the model.

### Adding a skill

A folder under the server's `skills/components/<slug>/` with `prompt.md`,
`README.md`, `CHANGELOG.md` and `evals/`, and an entry in that server's
`catalog.json` with the fields under [Skills](#skills). A skill goes on the
server whose tools it uses; one that uses only a client's document tools
goes on `ai4ra` (research administration) or `general` (any office); one
that is one institution's goes on that institution's server. Bump the
version in the front matter and the catalog together.

## Status

2026-10-15: `directory`, a server over the University of Idaho campus directory at directory.uidaho.edu, the employees the university publishes: people by last name, first name, email or department, one person's details, the department list; employees only, no key, read through the directory's advanced search form; built without reading, keeping or returning the internal identifier (Banner's PIDM) the page carries in its popup attributes, detail links and autocomplete, which was reported to the university the same day, so a fix leaves the server untouched. The same day, keys: a client's `Authorization` header can be logged as its fields with the credential redacted, behind the one switch `AI4RA_MCP_LOG_HEADERS=1`, after Claude.ai's request-header field was found to drop a typed space (the key arrived glued to `Bearer`); the README's Claude.ai steps say to type two spaces. The same day: a list says what it holds (#43): `classes_terms` returns every term, with `total` and no `max`, and the same whole list resolves a term a person names for every other tool, since the newest ten by default had a model report the schedule began at Fall 2024 and a term older than ten fail to resolve by name; `fac_audits_search` takes `offset` and says `next_offset` when more audits exist, the one other list that cut silently. The convention everywhere else stood: `returned`, `total` when the upstream states one, and a next pointer only when more exists. 2026-10-14: the two GitHub skills move from `general` to a `github` server of their own with no tools beyond `github_guide`, whose index entry carries `institution: "GitHub"` so a client folds it with GitHub's own MCP server (the pane's proxy fold takes the same value: mindrouter-365 #77) and the skills stand beside the tools they call; `institution` widened from an institution's own knowledge to the source a server is about, when it is one organisation's own; the `uidaho` server's label is "UI guidance", since inside a University of Idaho fold the server is the guidance one. The same day: `institution` on each server's index entry, the institution whose own knowledge the server needs: "University of Idaho" on `uidaho`, `classes` and every lakehouse server, null on the rest by definition, so a client can gather one institution's servers; never a label for servers that share a job (#38; the pane side is mindrouter-365 #74). The same day: executive orders first-class on `fedreg` (#39): `federal_register_search` takes `presidential_type`, `president`, `signing_from` and `signing_to`, a presidential document's row and record carry its number, signer, signing date, citation, disposition line and plain-text link, and `federal_register_executive_order` finds one order by number (a full-text search for the number among executive orders, checked against each result's number, since the API has no condition on it), with the Register's disposition line passed through as written. The same day: `given` on each server's index entry, a sibling of `tools`: for each tool whose arguments name a thing the server holds, which arguments those are and which tool on the same server lists their values (`classes_section`: `term` from `classes_terms`, `crn` from `classes_search`), so a client can hold a call whose identifier the conversation never gave (mindrouter-365 #72, where a model invented a CRN for a third section; #40). The first wave is the class schedule's terms and CRNs; the same shape on the same day for ClickUp's workspace, space, list and task ids, the record ids on NIH, NSF, USAspending, SAM.gov, FAC, ROR, grants.gov, the Federal Register, Regulations.gov and Nonprofit Explorer, the scholarly servers' identifiers, BLS series ids, Idaho's policy numbers and the lakehouse's streams, tables and file hashes; subject codes and CFR citations left out as inference a person expects. The same day: `classes`, a server over the registrar's public class schedule and course catalog (Browse Classes and Browse Course Catalog in Banner): terms, sections by term, subject, course number or instructor, one section in full (its twelve panels: description, details, meetings, prerequisites, corequisites, restrictions, cross-listed and linked sections, attributes, fees, the Day One Access link, enrollment), courses by subject, number or keyword, and one course's catalog record; no key, every tool a read, each call its own Banner session since the instructor ids are the session's and the form holds the last search; course materials wait on a feed from the bookstore (#36). It answers the pane's "can you help with my course" with one search by the person's name for the current term. 2026-10-07: a client can read what this server is from the server: the index carries one paragraph for the whole, with the search first as a SearXNG metasearch and not a single provider's, and `README.md` is served at the root as `text/markdown`; the `general` server's instructions say the same (#33; the per-server about pages and an `about` entry on the guide tools were dropped, since every server's `instructions` and `<server>_index` tool are already its account). The same day: `feature-prd-interview` 0.1.0 on `uidaho`, converted from a `.skill` package written for claude.ai, with every fact in `openera-feature-guide` 0.1.0 and its ClickUp work through three additions to `clickup` (a `tags` filter on the search, `clickup_list_fields`, `clickup_task_field_set`) (#32); `lakehouse-answer` 0.4.0 (nothing invented, rows as rows, a head is a small query) and the server's trailing-LIMIT pattern in Trino's order, OFFSET then LIMIT. #31, the skills in Anthropic's `SKILL.md` shape, stands not decided: on its own the reformat is churn, and it pays off only together with a download that works in Claude, the two done together or not at all. 2026-10-05: from a review of the `Suggested Fix:` line, an Add names what the passage is to show and never says that it exists or was done, and gives the two other ways out in the same line (`Add …, check with <the sponsored programs office>, or Remove the sentence`), since a check knows only that the passage does not show it, not whether it exists or can be had (`cfr-check` 0.13.0, `policy-check` 0.13.0); the four lines of a finding, the label and the opening word are unchanged. 2026-10-02: nine more skills declare their short inputs as optional prompt arguments, eleven in all; a skill that takes a document or a record, and a guide, take none (#29). A sweep of all 35 skills for anything that names a client found three and fixed them (`code-change` 0.2.0 no longer signs a pull request "Opened from MindRouter 365" or reads from "the open message, document or selection"; `actions-check` 0.1.1; `uidaho-lookup` 0.5.2 drops its guard against writing into a workbook), and `tests/test_guides.py` now holds every prompt on every server to naming no client. For clients other than the pane (#28), the two checks declare their inputs as prompt arguments (`passage`, and `date` on `cfr-check`), their text no longer describes one client's limits on calls, and the `ecfr` server tells one story about the first call: a search, with the index as reference. 2026-10-01: a check surfaces candidate findings for a person to verify and does not rule, so a finding's first line is the one word `finding.` in place of `violates.` and `unclear.`, its last line is labelled `Suggested Fix:` in place of `Fix:` (#27; a client that reads the line by its label is updated first), and its source line is the quotation and its link with no label (#26; a client that read the source line by its label must be updated first, mindrouter-365 at `068ca71` or later); after the first whole-document run on 1,500-character passages (#25) the quoted clause must itself forbid, require or condition something, no finding rests on a fact the sentence does not state, the reading still owed before a report is one further round, a sentence that states a rate or its base is never listed as not checked once the rate document is read, and an offset sent for a text that came whole returns it whole with a note. Earlier the same day: a finding holds one sentence to the fetched rule and never to another sentence of the document, so the `Conflicts with:` line is out of the findings form (#24). A text with an outline comes back whole only up to 6,000 characters, a chapter's listing carries one sentence a policy, and the rate agreement comes without its general terms, since a step runs out of characters before it runs out of rounds. After the first whole-document run, an outline shows each part's size, an offset that is no heading's reads the part it falls in, and the checks name the read's arguments, never read a heading and the one above it, and list as not checked only a numbered sentence. After the next run (#23), with both steps light (14,505 and 23,283 characters), the checks number the sentences and work by the numbers, a part read returns its `pinpoint`, the Fix line has a form (Add, Change or Remove, ending at the change), a rate the page contradicts is a finding and never "not checked", and a not-checked line quotes its sentence. After the run that followed (#22) the size of a read is the server's alone (no `max_chars`; 12,000 for both sources), search hits are compact, and both checks keep the Fix line to what to change in the document and test each finding's clause against the sentence before reporting. After the first two-source run (#21) a long policy comes back as an outline of its sections and is read one section at a time, a policy question starts with a chapter's listing, and both checks quote the clause on the sentence's own subject and take no general principle as grounds for a finding. After the second run (#20) the checks label a source line with the server's name (`eCFR:`, `University of Idaho:`), search for every sentence that asserts something and fetch the section the search returned for it before calling it unchecked, name what was not checked by its own words only, and keep violates and unclear apart. After the first real run of `cfr-check` took 16 model calls for one passage (#19), a section up to 20,000 characters comes back whole, a part is read to its end by its offset alone, and both checks search once, read once and stop. The `uidaho` chapter index, each policy with what it covers in its own opening words (#18); `policy-check` on `uidaho`, the university's sibling of `cfr-check`; the findings contract both report in. `ecfr_search` limited to a title and part (#17); no date needed for the current text on any ecfr tool, the latest day read from the eCFR and not the clock, and the server's refusals readable by a client (#16 items 2, 4, 5, part of 8); `ecfr-research-admin` removed; a report-only `cfr-check` on `ecfr`, so a client keeps only the placement of findings. a long section returned as its outline, a part read by its offsets (#16 item 3). Open on #16: the index's size (6), compact search results (7). 2026-09-30: the server-and-client rule and the grid; log no keys; the Banner family removed; guides as catalogued components with a `<server>_guide` tool per server (the UDM guide, five proposal guides, the AI-tells guide, and the compliance-concerns vocabulary as draft 0.1, #15); once the pane served its own placement skills (mindrouter-365 #34 to #39), the ten it had been carrying here (Gantt, ask, remove-ai-tells, the five proposal sheets, udm-sheet, proposal-workbook) were removed and the rates skill became report-only, so no catalog here carries a client's fields. 2026-09-29: twenty-six servers; the `udm` server and the `udm-sheet` skill on `ai4ra` were added that day, offline-tested against a fixture in the published schema's shape and tried against the real schema. 2026-09-25: twenty-five servers. The eCFR and grants.gov code moved in from
mcp-ecfr on 2026-09-22 with the Office add-in's skills, and the NIH, NSF,
SAM.gov, USAspending and Federal Audit Clearinghouse servers were verified
against the live APIs that day (SAM.gov and FAC with a person's own key).
The lakehouse server followed on 2026-09-23 and the fourteen servers for the
Federal Register, Regulations.gov, the screening lists, the budget figures
and the scholarly record on 2026-09-24, each written against its upstream's
documented shapes and tested offline from captured examples; BLS's common
series were verified live, and the others are verified as they are used.
The demo deployment runs on the VM behind Caddy with SearXNG beside it.

Not yet done: evals for the moved skills; skills for the fourteen newer
servers (a screening workflow across `csl`, `oig` and `sam`, a public-access
check across `nih` and `pubmed`, an escalation-rate note from `bls`); the
SAM.gov integrity section; an FDP Clearinghouse reader. SBIR.gov is left out
because its API refuses every caller.

## Related

- [AI4RA/mcp-ecfr](https://github.com/AI4RA/mcp-ecfr): the eCFR server this
  supersedes.
- [ui-insight/mindrouter-365](https://github.com/ui-insight/mindrouter-365):
  the Office add-in that is the first client. Its issues 17 (the split into
  pane, servers and deployment) and 23 (the University of Idaho server) are
  the design record for this repository.
- [AI4RA/prompt-library](https://github.com/AI4RA/prompt-library): the
  component and catalog shape the skills folders follow.
- [AI4RA/grants-gov-s2s-mock](https://github.com/AI4RA/grants-gov-s2s-mock):
  the Grants.gov S2S test surface hosted beside this process (see Hosting).
  OpenERA #1418.

## Contributing

Contributions are welcome by pull request. By submitting a contribution you agree that it will be licensed under the [Apache License, Version 2.0](LICENSE), the same license as the project, and you represent that you have the right to license it under those terms. Contributions keep the attribution in [NOTICE](NOTICE) intact.

## License

Apache License 2.0, copyright 2026 Nathan Layman. See [LICENSE](LICENSE) for the terms and [NOTICE](NOTICE) for the attributions a redistribution keeps under Section 4(d): Nathan Layman as the author, the University of Idaho, the AI4RA project, and the National Science Foundation award that funded the work. To cite the project, use [CITATION.cff](CITATION.cff).

## Acknowledgments

<img src="https://github.com/user-attachments/assets/d2b43c22-84f6-4912-91dc-8b081d9e2c6f" alt="NSF Logo" width="157">

ai4ra-mcp is a project of [AI4RA](https://github.com/AI4RA) at the University of Idaho, developed with support from the National Science Foundation under the GRANTED program ([NSF Award #2427549](https://www.nsf.gov/awardsearch/show-award?AWD_ID=2427549), "Crossing the Innovation Valley of Death: Democratizing Data and Artificial Intelligence for Research Administration"). Any opinions, findings, conclusions or recommendations expressed in this material are those of the author and do not necessarily reflect the views of the National Science Foundation.
