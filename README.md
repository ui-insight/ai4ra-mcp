# ai4ra-mcp

One repository, one process, several MCP servers. Each server is one upstream
and one audience, mounted at its own path and complete on its own, so a client
adds only the ones it wants. The federal servers know nothing about any
institution; the University of Idaho server knows only Idaho. They share a
codebase, a deployment and the plumbing underneath (HTTP client, cache, page
reader), and nothing else.

A server carries the tools that act on its upstream and the skills that know
how to use those tools. A client that speaks MCP gets both together; a client
that reads skill catalogs by URL gets the same files as static content.

## The servers

| Path | Upstream | Tools | Skills |
|---|---|---|---|
| `/ecfr/mcp` | ecfr.gov | `ecfr_regulatory_index`, `ecfr_search`, `ecfr_list_titles`, `ecfr_list_agencies`, `ecfr_get_title_versions`, `ecfr_get_regulation`, `ecfr_get_title_structure`, `ecfr_compare_regulations` | `ecfr-research-admin` |
| `/grants/mcp` | grants.gov | `grants_gov_search`, `grants_gov_opportunity` | `funding-opportunity-finder` |
| `/uidaho/mcp` | uidaho.edu | `uidaho_guidance_index`, `uidaho_guidance_search`, `uidaho_guidance_get`, `uidaho_rates` | `uidaho-lookup` |
| `/ai4ra/mcp` | the open web | `fetch_document` | none |

The `ai4ra` server is the catch-all: whatever AI4RA provides that is tied to
no single upstream. Today that is the page reader, which other servers' skills
use for attachments and linked documents.

A client's connector URL is the server's path on the host, for example
`https://<host>/ecfr/mcp`. A deployment's list of sources names the paths it
wants: Idaho's names all four; another institution names three and whatever
it builds for itself. `GET /` lists what is mounted, with each server's tools
and prompts.

Tool names carry their upstream (`ecfr_`, `grants_gov_`, `uidaho_`) and are
otherwise unchanged from mcp-ecfr. The extra prefix the Hugging Face Space's
Gradio wrapper added (`ecfr_mcp_server_…`) is gone.

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
`fetch_document` on the `ai4ra` server.

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

## Rules

- **Tools act.** A tool does one mechanical thing against one upstream and
  reports what it found. Which policy or regulation applies to a budget line
  is judgment, and judgment lives in a skill, never in a tool.
- **One server, one upstream, one audience.** Everything that reads ecfr.gov
  is one server; everything that reads uidaho.edu is another. A federal
  server has no Idaho defaults; the Idaho server hard-codes uidaho.edu.
  Shared code is plumbing only. The `ai4ra` server is the one exception, by
  design: the place for what belongs to no upstream.
- **Every server stands alone.** Each runs by itself over stdio or HTTP with
  nothing else present, and each has an index tool that tells a model how to
  use it. No server calls another server's tools; a skill may name another
  server's tool when the job needs it.
- **Skills stay with their tools.** A skill lives in the server whose tools it
  uses. Skills that need a client's own tools (an Office add-in's cells and
  paragraphs) belong to that client, not here.
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
    grants/  uidaho/  ai4ra/  same shape
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
`CHANGELOG.md` and `evals/`, and an entry in that server's `catalog.json`
whose `requires` lists the tools it calls. The server serves it as an MCP
prompt named by its slug and as static files under `/<server>/skills/`.

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
Streamable HTTP is the only network transport; the Space's SSE endpoint is
not carried over.

Environment: `AI4RA_MCP_HOST` and `AI4RA_MCP_PORT` (defaults 127.0.0.1 and
8000); `AI4RA_MCP_CONTACT`, the address in the User-Agent; `AI4RA_MCP_HOSTS`,
a comma-separated list of public hostnames to allow, which turns the SDK's
DNS-rebinding protection on (off by default, since a reverse proxy in front
sets the Host header to the public name).

## Hosting

The intended host is a VM behind Caddy with a campus certificate, the same
arrangement the mindrouter-365 demo uses. Caddy terminates TLS and
reverse-proxies the server paths to the process on localhost; the systemd
unit in `deploy/` keeps the process up. The Dockerfile is for anyone who
would rather run it elsewhere.

Clients such as the Office add-in call these servers from inside a browser
engine, so the process answers CORS itself: any origin, any method, and the
`Mcp-Session-Id` header exposed. Public content needs nothing narrower. A
server that must be reachable only on campus (a future one that reads an
internal system) is a Caddy rule and a firewall, not a code branch.

Why not the Hugging Face Space: it was the fastest public endpoint for a
summit, and Gradio was the way to put stdio tools behind HTTP at the time.
It sleeps when idle, imposes a tool-name prefix, and is one more origin to
trust. The SDK now serves HTTP directly, and the VM already has the
certificate and the proxy. The Space stays up until the VM copy is live and
the clients that name it have moved.

## Connecting

- **Claude.ai:** Settings → Connectors → Add custom connector, with the
  server's URL, for example `https://<host>/ecfr/mcp`. One connector per
  server; its skills appear as prompts.
- **Claude Code:** `claude mcp add --transport http ecfr https://<host>/ecfr/mcp`.
- **mindrouter-365:** a `servers` entry per server in the deployment's
  `sources.json` with its `/mcp` URL, and a `libraries` entry per server
  whose `catalog` is `https://<host>/<server>/skills/catalog.json` and whose
  `base` is `https://<host>/<server>/skills/`.

## Status

2026-09-22: all four servers run, with the eCFR and grants.gov code moved in
from mcp-ecfr and the University of Idaho server new. Not yet done: the VM
deployment, evals for the three skills, and pointing mindrouter-365's
`sources.json` here instead of at the Space.

## Related

- [AI4RA/mcp-ecfr](https://github.com/AI4RA/mcp-ecfr): the eCFR server this
  supersedes, and the Space that serves it today.
- [ui-insight/mindrouter-365](https://github.com/ui-insight/mindrouter-365):
  the Office add-in that is the first client. Its issues 17 (the split into
  pane, servers and deployment) and 23 (the University of Idaho server) are
  the design record for this repository.
- [AI4RA/prompt-library](https://github.com/AI4RA/prompt-library): the
  component and catalog shape the skills folders follow.
