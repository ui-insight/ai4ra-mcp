# ai4ra-mcp

One repository, one process, twenty-five MCP servers. Each server is one
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
- [Status](#status), [Related](#related)

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
| `/general/mcp` | the open web, through a SearXNG beside the process | none | `web_search`, `fetch_document`, `general_guide` | `ask`, `remove-ai-tells`, `ai-tells-guide` (the guide), `project-timeline-gantt` (Excel only), `code-change` and `actions-check` (use GitHub's own MCP server, reached by the Office pane through its host's proxy; see mindrouter-365's README, "GitHub through the proxy") |
| `/ai4ra/mcp` | none: skills and guides | none | `ai4ra_guide` | `rfa-sheet`, `proposal-narrative`, `work-plan`, `budget-outline`, `budget-nsf`, `udm-sheet` (a workbook's sheet as a UDM table; calls the udm server's tools), the guides `rfa-guide`, `narrative-guide`, `work-plan-guide`, `budget-outline-guide`, `nsf-budget-guide`, and seventeen cost-allowability, extraction and budget-justification prompts copied from AI4RA/prompt-library |
| `/udm/mcp` | the AI4RA Unified Data Model's published schema (ui-insight.github.io/AI4RA-UDM) | none | `udm_index`, `udm_schema`, `udm_guide` | `udm-conversion-guide` (the guide; `udm-sheet` is on `ai4ra`) |

**Rules and announcements**

| Path | Upstream | Key | Tools | Skills |
|---|---|---|---|---|
| `/ecfr/mcp` | ecfr.gov | none | `ecfr_guide`, `ecfr_regulatory_index`, `ecfr_search`, `ecfr_list_titles`, `ecfr_list_agencies`, `ecfr_get_title_versions`, `ecfr_get_regulation`, `ecfr_get_title_structure`, `ecfr_compare_regulations` | `ecfr-research-admin` |
| `/fedreg/mcp` | Federal Register | none | `federal_register_index`, `federal_register_search`, `federal_register_document`, `federal_register_agencies` | none |
| `/regulations/mcp` | Regulations.gov | **required** (api.data.gov) | `regulations_gov_index`, `regulations_gov_documents_search`, `regulations_gov_document`, `regulations_gov_docket`, `regulations_gov_comments_search` | none |
| `/grants/mcp` | grants.gov | none | `grants_gov_search`, `grants_gov_opportunity`, `grants_guide` | `funding-opportunity-finder` |
| `/s2s/mcp` | the Grants.gov Applicant System-to-System (S2S) SOAP service, at any endpoint: training, production, or the deployment's default (a mock) | optional (the person's own S2S certificate and key as a bearer bundle; a deployment may hold a fallback that only the mock accepts) | `s2s_index`, `s2s_check`, `s2s_opportunity`, `s2s_validate_package`, `s2s_submissions`, `s2s_application_info`; with `AI4RA_MCP_S2S_WRITES=1` also `s2s_submit` (off by default) | none yet |

**Awards held**

| Path | Upstream | Key | Tools | Skills |
|---|---|---|---|---|
| `/nih/mcp` | NIH RePORTER | none | `nih_guide`, `nih_index`, `nih_projects_search`, `nih_project`, `nih_publications` | `funding-history` |
| `/nsf/mcp` | NSF Award Search | none | `nsf_index`, `nsf_awards_search`, `nsf_award`, `nsf_award_outcomes` | none |
| `/usaspending/mcp` | USAspending | none | `usaspending_index`, `usaspending_recipients`, `usaspending_recipient`, `usaspending_awards_search`, `usaspending_subawards_search`, `usaspending_award` | none |

**Vetting a partner**

| Path | Upstream | Key | Tools | Skills |
|---|---|---|---|---|
| `/sam/mcp` | SAM.gov | **required** (SAM.gov personal key) | `sam_guide`, `sam_index`, `sam_entity`, `sam_exclusions_search`, `sam_assistance_listing`, `sam_assistance_listings_search` | `subrecipient-check` |
| `/fac/mcp` | Federal Audit Clearinghouse | **required** (api.data.gov) | `fac_index`, `fac_audits_search`, `fac_findings`, `fac_federal_awards` | none |
| `/csl/mcp` | trade.gov Consolidated Screening List | **required** (trade.gov subscription key) | `csl_index`, `csl_search`, `csl_sources` | none |
| `/oig/mcp` | HHS OIG LEIE, from its daily CSV | none | `oig_leie_index`, `oig_leie_search`, `oig_leie_status` | none |
| `/propublica/mcp` | ProPublica Nonprofit Explorer | none | `propublica_nonprofit_index`, `propublica_nonprofit_search`, `propublica_nonprofit_organization` | none |
| `/ror/mcp` | Research Organization Registry | none | `ror_index`, `ror_search`, `ror_organization` | none |

**Budget figures**

| Path | Upstream | Key | Tools | Skills |
|---|---|---|---|---|
| `/perdiem/mcp` | GSA per diem | **required** (api.data.gov) | `gsa_perdiem_index`, `gsa_perdiem_rates`, `gsa_perdiem_mie_breakdown` | none |
| `/bls/mcp` | Bureau of Labor Statistics | optional (BLS registration key) | `bls_index`, `bls_series`, `bls_common_series` | none |

**The scholarly record**

| Path | Upstream | Key | Tools | Skills |
|---|---|---|---|---|
| `/openalex/mcp` | OpenAlex | none | `openalex_index`, `openalex_works_search`, `openalex_work`, `openalex_authors_search`, `openalex_institutions_search`, `openalex_funders_search` | none |
| `/pubmed/mcp` | NCBI E-utilities and the PMC ID converter | optional (NCBI key) | `pubmed_index`, `pubmed_search`, `pubmed_summary`, `pmc_id_convert` | none |
| `/crossref/mcp` | Crossref | none | `crossref_index`, `crossref_works_search`, `crossref_work`, `crossref_funders_search` | none |
| `/orcid/mcp` | ORCID public API | none | `orcid_index`, `orcid_search`, `orcid_record` | none |
| `/osti/mcp` | OSTI.GOV | none | `osti_index`, `osti_search`, `osti_record` | none |
| `/clinicaltrials/mcp` | ClinicalTrials.gov | none | `clinicaltrials_index`, `clinicaltrials_search`, `clinicaltrials_study` | none |

**Project trackers**

| Path | Upstream | Key | Tools | Skills |
|---|---|---|---|---|
| `/clickup/mcp` | ClickUp, as the person | **required** (ClickUp personal API token) | `clickup_index`, `clickup_whoami`, `clickup_tasks_search` (the whole workspace in one call: by assignee, status, space or list), `clickup_workspace`, `clickup_tasks`, `clickup_task`; with `AI4RA_MCP_CLICKUP_WRITES=1` also `clickup_task_create`, `clickup_task_update`, `clickup_task_comment`, `clickup_task_attach` (off by default: read only) | none yet (the skill that files a piece of mail into a project goes here) |

GitHub is not a server here: GitHub's own remote MCP server takes a personal
access token as a bearer, so the Office pane reaches it through a proxy block
on the pane's host (see mindrouter-365's README, "GitHub through the proxy"),
with its `context`, `issues` and `repos` toolsets and its `get_me` whoami.
ClickUp's hosted MCP server is OAuth only, which the pane cannot do
(mindrouter-365 issue #27), hence a keyed server of our own over ClickUp's
REST API.

**University of Idaho**

| Path | Upstream | Key | Tools | Skills |
|---|---|---|---|---|
| `/uidaho/mcp` | uidaho.edu policy pages and rate documents | none | `uidaho_guide`, `uidaho_guidance_index`, `uidaho_guidance_search`, `uidaho_guidance_get`, `uidaho_rates` | `uidaho-lookup`, `uidaho-rates`, `proposal-workbook` |
| `/lakehouse/mcp` (one per configured client; the others at `/lakehouse-<id>/mcp`) | the University of Idaho data lakehouse, through Marina | **required** (the client's shared secret) | `lakehouse_guide`, `lakehouse_index`, `lakehouse_sql_catalog`, `lakehouse_sql`, `lakehouse_streams`, `lakehouse_schema`, `lakehouse_query`, `lakehouse_files`, `lakehouse_file` | `lakehouse-answer` |

Tool names carry their upstream (`ecfr_`, `grants_gov_`, `uidaho_`) and
nothing else; a client shows them as they are. Every server with skills
has a `<server>_guide` tool that lists them and returns one by name (see
[Skills](#skills)). Every server except `ai4ra`
has an index tool (`<upstream>_index`, or `ecfr_regulatory_index`) that a
model reads first: what the server offers, the tools in the order to use
them, the upstream's limits, the date formats and the citation rule. A
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

`GET /` returns `{"v": 1, "servers": [...]}`, one entry per mounted server:

```json
{
  "name": "perdiem",
  "label": "GSA per diem",
  "description": "Federal lodging and M&IE rates by city, state or zip for a fiscal year, and the M&IE meal breakdown.",
  "mcp": "perdiem/mcp",
  "skills": "perdiem/skills/catalog.json",
  "skills_base": "perdiem/skills/",
  "web": "https://github.com/ui-insight/ai4ra-mcp/blob/main/ai4ra_mcp/servers/perdiem/skills/",
  "key": {"required": true, "hint": "Paste your api.data.gov key, free from https://api.data.gov/signup/ (DEMO_KEY works for a few calls an hour)."},
  "tools": ["gsa_perdiem_index", "gsa_perdiem_rates", "gsa_perdiem_mie_breakdown"],
  "prompts": []
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
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ecfr_get_regulation","arguments":{"title":2,"section":"200.403","date":"2025-01-01"}}}'

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

Eight servers talk to an upstream that wants a key, and one more wants a
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
| `csl` | required | https://developer.trade.gov/ : sign up, subscribe to the Consolidated Screening List API, copy the subscription key | trade.gov's per-subscription limit | `subscription-key` header |
| `bls` | optional | https://data.bls.gov/registrationEngine/ (free) | 25 queries a day per IP without one (v1, shared by everyone on the server), 500 with one (v2), plus longer spans and series titles | `registrationkey` in the POST body |
| `pubmed` | optional | The settings page of an NCBI account, https://account.ncbi.nlm.nih.gov/settings/ (free) | 3 requests a second without one, shared; 10 with one | `api_key` query parameter |
| `clickup` | required | ClickUp: click your avatar, Settings, Apps, Generate API Token (starts with `pk_`). It acts as you in every workspace you belong to, so a task it creates is created by you | 100 requests a minute per token | Raw in the `Authorization` header, the way ClickUp wants it (the server takes the bearer the client sent and re-sends it that way) |
| `lakehouse` | required | The shared secret issued with the lakehouse client id (today `mr-365`) by Research Computing and Data Services. It is one client's secret, not a personal key, so its limits (100 requests a minute, 1,000 an hour) are shared by everyone who uses it | per client | Exchanged at Marina's `/auth/token` for an OAuth bearer, kept in memory until it expires |

One api.data.gov key works for `fac`, `regulations` and `perdiem` alike; a
person pastes the same key into each of those three servers.

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
  header `Authorization` whose value is `Bearer <key>` (the scheme typed in,
  since Claude.ai sends the value as entered); the key is then shared by the
  organization on a Team or Enterprise plan, and the person's own on a
  Free, Pro or Max plan. The headers cannot be edited after the connector
  is added, only removed and re-added. Without that beta, a keyed server
  used from Claude.ai needs the deployment fallback below. The steps are
  under [Adding a keyed server to Claude.ai](#adding-a-keyed-server-to-claudeai).
- **A client that cannot add a header** (a stdio run has no HTTP at all;
  Claude.ai without the request-headers beta): the deployment holds a
  fallback key in the server's environment variable (`AI4RA_MCP_SAM_KEY`,
  `AI4RA_MCP_FAC_KEY`, `AI4RA_MCP_REGULATIONS_KEY`, `AI4RA_MCP_PERDIEM_KEY`,
  `AI4RA_MCP_CSL_KEY`, `AI4RA_MCP_BLS_KEY`, `AI4RA_MCP_PUBMED_KEY`,
  `AI4RA_MCP_LAKEHOUSE_SECRET`), used only for a request that sends no
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
judgment of the matching sheet skill with the placement taken out; the sheet
skills stay beside them until their placement halves move to the client
(mindrouter-365 #36), and are then removed. The proposal sheets (`rfa-sheet`, `proposal-narrative`,
`work-plan`, `budget-outline`, `budget-nsf`) were written for the Office
add-in and moved here on 2026-09-22; each catalog entry's `source`
says so. `budget-nsf` is institution-agnostic: its template ships no rates,
and the skill reads them from a sheet named Rates when the workbook has one
(seven fixed-label rows: Location, F&A rate, F&A base, Fringe faculty, Fringe
staff, Fringe students, Fringe temporary, and a Source row), writes the
Source row beside the rates as provenance, and estimates a rate the sheet
lacks, filled yellow and marked so. An institution provides the Rates
sheet with a skill of its own; `uidaho-rates` is Idaho's, and writes the
sheet only when the request names one (the proposal workbook's Rates step
does).

`udm-sheet` lays a sheet of records out as one Unified Data
Model table on a new sheet, by formula, after one round of confirmed
decisions; the schema and the conversion guide come from the `udm`
server's tools, and its description is under [udm](#udm).

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

Any MCP client can convert with these two tools alone. `udm-sheet`, on the
`ai4ra` server with the other research-administration skills, is the
workbook side: it reads the records, follows the guide, asks once, and
lays the sheet out as one UDM table on a new sheet named `UDM <Table>`,
every column of the table in the spec's order and the audit columns, each
data cell a formula on the source cell (a reference, a split, a join, a
parsed date, a `SWITCH` over the vocabulary, a generated key when the
source has no identifier), `_Date` and `_Amount` columns formatted, and
the header of a required column with no source filled light yellow. Before
it reports, it tests the row count with `assert_cells` (the key column
nonblank on every source row, and the row below empty), since a catalog
assertion cannot name a count only known at run time; the catalog's own
assertions hold the header and the first key. One
table a run: the leftover headers are named with the table each belongs
to, and a second run naming that table writes the next. Where that
placement skill finally lives is open: the base client is the plan's answer
(mindrouter-365 #37), but the data model it targets is one consortium's, and
an institution with a data model of its own may want the conversion skill in
its own client instead; noted in the plan and mindrouter-365 #43, not a
change.

### ecfr

The eCFR API, https://www.ecfr.gov/api, no key. The tools and their rules
are unchanged from mcp-ecfr: read the index first, get a valid date from the
title's versions before fetching text, give the title explicitly because
part numbers repeat across titles, prefer sections over parts. The
regulatory index, a resource in mcp-ecfr, is a tool here as well, because
most clients never list resources. `ecfr_compare_regulations` diffs a
section between two dates.

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
optional NCBI key (the person's own as a bearer token, or
`AI4RA_MCP_PUBMED_KEY`) is sent as `api_key` for 10. `pubmed_search` takes a
PubMed query with its fields (`AI135270[Grant Number]`,
`University of Idaho[Affiliation]`, `Smith J[Author]`) and an optional
publication date range, and returns each paper's citation, PMID, DOI, PMCID
and PubMed link, newest first, 1-50 a page. `pubmed_summary` gives the same
for PMIDs already in hand (up to 50), such as the ids NIH RePORTER's
`nih_publications` returns. `pmc_id_convert` takes up to 200 PMIDs, PMCIDs
and DOIs in any mix, converts among them (one idconv call per id type, since
the API takes one type a call) and says which have no PMCID. Every call
carries `tool=ai4ra-mcp` and, when `AI4RA_MCP_CONTACT` is an email address,
`email=` that address (idconv rejects a URL there). Searches are cached an
hour, summaries and conversions a day. The index tells the model that NIH
public access (NOT-OD-25-047, effective July 1 2025) needs a PMCID for every
peer-reviewed paper arising from NIH funding, so a paper with a PMID and no
PMCID is the one to chase; that grant searches use the institute code and
serial (`AI135270[Grant Number]`; the RePORTER form `R01AI135270` finds
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
carries fallback figures. `proposal-workbook` is the eight-step workflow
that runs skills from the general, ai4ra and uidaho servers in order. The
award skills that read Banner exports (award-facts, award-lines,
award-status, award-review, pi-awards, current-pending,
current-pending-support, and pi-memo on ai4ra) were removed on 2026-09-30
(#12): none of them worked, and all were Excel-bound, which under the
server-and-client rule is client code; they are in git history.

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
`/sql/v1/statement`: one schema per querying stream, named
`client_<client_id>__<stream>`, one view per allowed table, so a table is
`lakehouse."client_mr-365__subaward"."<view>"`; rows are filtered and masked
inside the views, and a statement may reference one stream's views only. The
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
(`udm_guide`), the five proposal guides on `ai4ra` (`ai4ra_guide`) and the
AI-tells guide on `general` (`general_guide`) are the guides so far.

A skill is a prompt with a contract: what it needs, what it produces, which
tools it calls. Each lives in its server's `skills/components/<slug>/` as
`prompt.md` (YAML front matter, a preamble with **Purpose**, **Expected
input** and **Expected output**, then the prompt under `## Prompt`),
`README.md`, `CHANGELOG.md` and `evals/`, with an entry in that server's
`catalog.json`. The server serves it as an MCP prompt named by its slug and
as static files under `/<server>/skills/`.

The catalog entry follows AI4RA/prompt-library's shape (`slug`, `summary`,
`version`, `category`, `status`, `paths`, `contracts.output.format`,
`evaluation`) and adds the fields a client acts on:

| Field | What it says |
|---|---|
| `requires` | The tools the skill calls: a tool name here (`uidaho_rates`), `<host>:<name>` for a client's own tool (`excel:write_values`), or `skill_<slug>` for another skill a workflow runs |
| `triggers` | Words in a request that point at the skill |
| `hosts` | The clients the skill is offered in (`["excel"]`); absent means all |
| `fold` | `"host"` lists the skill beside that client's own tools instead of in this server's fold (the Gantt chart, in Excel) |
| `paths.template` | A `template.json` the client lays down before the skill runs: a sheet of values, formats, `locked` ranges and `from_context` cells |
| `assertions` | The skill's definition of done, tested by the client on its output sheet: `[{address, rule, min, max, value, of, sheet, label}]` |
| `stages` | For a workflow, the table of steps: `[{name, skill, context, sources, required_tools}]`; a step's skill may live on any server |
| `source` | Where a copied or moved component came from: repository, commit, path |

A client caches the prompt text by version, so a change to a skill bumps
the version in the front matter and the catalog together.

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

Python 3.12 or later. Each server is an `MCPServer` from the official Python
SDK (mcp 2.x). The process mounts each one's streamable-HTTP app at its
path, stateless and answering in JSON, and runs their session managers under
one lifespan. Streamable HTTP is the only network transport.

The tests are offline: every server mounts and lists the tools it promises,
the index answers, CORS answers, the University of Idaho parsers read the
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
| `AI4RA_MCP_SAM_KEY`, `AI4RA_MCP_FAC_KEY`, `AI4RA_MCP_REGULATIONS_KEY`, `AI4RA_MCP_PERDIEM_KEY`, `AI4RA_MCP_CSL_KEY` | Fallback keys for the required-key servers, used only for a request that sends no bearer token (see [Keys](#keys)) | unset |
| `AI4RA_MCP_BLS_KEY`, `AI4RA_MCP_PUBMED_KEY` | Fallback keys for the optional-key servers, likewise | unset |
| `AI4RA_MCP_LAKEHOUSE_URL` | The Marina the lakehouse servers read | `http://nlayman.nkn.uidaho.edu:7010` |
| `AI4RA_MCP_LAKEHOUSE_CLIENTS` | The lakehouse client ids to mount, comma separated; the first at `/lakehouse`, the rest at `/lakehouse-<id>` | `mr-365` |
| `AI4RA_MCP_LAKEHOUSE_SECRET`, `AI4RA_MCP_LAKEHOUSE_SECRET_<ID>` | Fallback shared secrets, the first client's and each other client's | unset |
| `AI4RA_MCP_LAKEHOUSE_SQL_TIMEOUT_S` | Seconds a `lakehouse_sql` statement may run before it is cancelled | `60` |
| `AI4RA_MCP_S2S_ENDPOINT` | The s2s server's default endpoint, used when a call passes none. The compose file sets it to the mock's mutual-TLS port on the compose network | unset: every call must pass one |
| `AI4RA_MCP_S2S_CA_FILE` | The CA that signs the default endpoint's server certificate (the mock's `ca.crt`); other endpoints use the system trust store or the bundle's own `ca` | unset |
| `AI4RA_MCP_S2S_CERT_FILE`, `AI4RA_MCP_S2S_KEY_FILE` | Fallback client certificate and key for a request that sends no bearer bundle; the compose file points them at a mock-minted pair | unset |
| `AI4RA_MCP_S2S_WRITES` | `1` registers `s2s_submit` | unset: read only |
| `AI4RA_MCP_S2S_PRODUCTION` | `1` lets `s2s_submit` reach `ws07.grants.gov`; otherwise production is refused | unset |
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
  keyed server. Its skills appear as prompts (`/mcp__ecfr__ecfr-research-admin`).
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
   Value: `Bearer ` and then your key, with the space. Claude.ai sends the
   value exactly as typed, so without the `Bearer ` prefix the server
   ignores it. Mark the header Required.
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
  found in the demo host's container log.
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
  uses; a skill that uses only a client's own document tools lives on `ai4ra`
  (research administration) or `general` (any office). A skill that needs
  one client only says so with `hosts` in its catalog entry, and `fold:
  "host"` when that client should list it beside its own tools (the Gantt
  chart, in Excel).
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
  servers/
    ecfr/
      server.py               MCPServer("ecfr"): tools with read-only annotations, the index tool, prompts
      skills/
        catalog.json          the components, in AI4RA/prompt-library's catalog shape
        components/<slug>/    prompt.md, README.md, CHANGELOG.md, evals/, template.json where the skill has one
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
an empty `components` list is enough). Add it to `SERVERS` in `app.py` in
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

2026-09-30: the server-and-client rule; log no keys; the Banner family removed; guides as catalogued components with a `<server>_guide` tool per server (the UDM guide, five proposal guides, the AI-tells guide). 2026-09-29: twenty-six servers; the `udm` server and the `udm-sheet` skill on `ai4ra` were added that day, offline-tested against a fixture in the published schema's shape and tried against the real schema. 2026-09-25: twenty-five servers. The eCFR and grants.gov code moved in from
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
