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
| `/grants/mcp` | grants.gov | `grants_gov_search`, `grants_gov_opportunity` | `funding-opportunity-finder` |
| `/nih/mcp` | NIH RePORTER | `nih_index`, `nih_projects_search`, `nih_project`, `nih_publications` | `funding-history` |
| `/nsf/mcp` | NSF Award Search | `nsf_index`, `nsf_awards_search`, `nsf_award`, `nsf_award_outcomes` | none |
| `/sam/mcp` | SAM.gov (key) | `sam_index`, `sam_entity`, `sam_exclusions_search`, `sam_assistance_listing`, `sam_assistance_listings_search` | `subrecipient-check` |
| `/usaspending/mcp` | usaspending.gov | `usaspending_index`, `usaspending_recipients`, `usaspending_recipient`, `usaspending_awards_search`, `usaspending_subawards_search`, `usaspending_award` | none |
| `/fac/mcp` | Federal Audit Clearinghouse (key) | `fac_index`, `fac_audits_search`, `fac_findings`, `fac_federal_awards` | none |
| `/uidaho/mcp` | uidaho.edu | `uidaho_guidance_index`, `uidaho_guidance_search`, `uidaho_guidance_get`, `uidaho_rates` | `uidaho-lookup`, `uidaho-rates-sheet`, `award-facts`, `award-lines`, `award-status`, `award-review`, `pi-awards`, `current-pending`, `current-pending-support`, `proposal-workbook` |

The index at `/` lists the servers in this order, which is the order a
client's picker shows them: general first, then the research-administration
skills, the public upstreams, and last the one institution's own server.

The `general` server is what belongs to no single upstream and no one
profession: a web search and the page reader (search for an address you do
not have, then read it; other servers' skills use the reader for attachments
and linked documents) and the skills any office uses with any document. The
`ai4ra` server has no tools: it is the research-administration skills that
work with a client's own document tools. Anything that can be shared lives on
one of these two; the `uidaho` server holds only what is the University of
Idaho's (its policies and rates, a Rates sheet from them, the award skills
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
staff, Fringe students, Fringe temporary, and a Source row) and writes the
Source row beside the rates as provenance. An institution provides the Rates
sheet with a skill of its own; `uidaho-rates-sheet` is Idaho's.

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
  (`fringe`) as text.

Chapter lists and policy text are cached for a day: revisions are rare and
the page carries its own date. A number with no page is reported as a 404
with no guessing.

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
    general/  ai4ra/  grants/  nih/  nsf/  sam/  fac/  usaspending/  uidaho/   same shape (ai4ra has no tools)
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
marks it "estimate", so the highlight means exactly that. `uidaho-rates-sheet`
is Idaho's; another institution writes its own to the same labels.

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

**Keys.** A keyed server (sam, fac) takes its upstream key from its
environment variable. A client may instead send its own key as
`Authorization: Bearer <key>` on the MCP request; for that request it is used
in place of the server's, so a person can spend their own quota rather than
the institution's. The token is held for the request only and never logged.
A request with no key gets a plain "no API key on this request" answer from
every tool of that server, saying to send one; the server still mounts.

Environment: `AI4RA_MCP_SEARXNG_URL`, the web search backend; `AI4RA_MCP_HOST` and `AI4RA_MCP_PORT` (defaults 127.0.0.1 and
8000); `AI4RA_MCP_CONTACT`, the address in the User-Agent; `AI4RA_MCP_SAM_KEY`
and `AI4RA_MCP_FAC_KEY`, optional fallback keys a deployment may hold for
requests that send none (the design is per-user keys sent by the client, so
most deployments set neither); `AI4RA_MCP_HOSTS`,
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
