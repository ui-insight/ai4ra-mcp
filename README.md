# ai4ra-mcp

One repository, one process, several MCP servers. Each server is mounted at
its own path and is complete on its own, so a client adds only the ones it
wants. The federal servers (eCFR, grants.gov) know nothing about any
institution; the University of Idaho server knows only Idaho. They share a
codebase, a deployment and the plumbing underneath (HTTP client, cache, page
reader), and nothing else.

**Status (2026-09-22):** this README and the layout it describes. The eCFR and
grants.gov code lives in [AI4RA/mcp-ecfr](https://github.com/AI4RA/mcp-ecfr)
and runs on a Hugging Face Space; moving it here is the first piece of work.
The University of Idaho server does not exist yet.

## The servers

| Path | Tools | Upstream | For |
|---|---|---|---|
| `/ecfr/mcp` | `regulatory_index`, `search`, `list_titles`, `list_agencies`, `get_title_versions`, `get_regulation`, `get_title_structure`, `compare_regulations` | ecfr.gov API | Anyone. Federal regulation by citation, topic and date. |
| `/grants/mcp` | `grants_gov_search`, `fetch_document` | grants.gov API; any public web page or PDF | Anyone. Funding announcements and the documents they link to. |
| `/uidaho/mcp` | `guidance_index`, `guidance_search`, `guidance_get` | uidaho.edu policy pages | University of Idaho. The Administrative Procedures Manual (APM), the Faculty Staff Handbook (FSH) and OSP guidance, by policy number, topic and revision date. |

A client's connector URL is the server's path on the host, for example
`https://<host>/ecfr/mcp`. A deployment's list of sources names the paths it
wants: Idaho's names all three; another institution names the first two and
whatever it builds for itself.

Tool names are bare. The server prefix that the Space's Gradio wrapper added
(`ecfr_mcp_server_…`) is gone; clients that namespace tools do it themselves.

### eCFR

The tools and their rules are unchanged from mcp-ecfr: read the index first,
get a valid date from the title's versions before fetching text, give the
title explicitly because part numbers repeat across titles, prefer sections
over parts. The index is memoized for the life of the process. Regulation
text for a citation on a date never changes, so it is cached with a long
lifetime; search results with a short one.

### grants.gov

`grants_gov_search` finds announcements; `fetch_document` reads one, or any
public web page or PDF, in pages. `fetch_document` is a general page reader
and lives here because the grants.gov descriptions tell the model to pass a
hit's link to it. It refuses private addresses and never guesses a path.

### University of Idaho

The policy site is plain HTML with a stable address scheme, which is what
makes a search-and-cite layer cheap:

| Source | Landing page | A policy | Header fields |
|---|---|---|---|
| APM | `uidaho.edu/policies/apm` lists chapters (01 Legal Affairs … 45 Research Office … 95 Public Safety) | `uidaho.edu/policies/apm/45/06` is APM 45.06 | Owner (position, email), `Last updated: <Month D, YYYY>` |
| FSH | `uidaho.edu/policies/fsh` lists chapters 1–6 (5 is Research Policies) | `uidaho.edu/policies/fsh/5/5100` is FSH 5100 | Same layout |
| OSP guidance | to be listed | | |

- `guidance_index` — read first. The sources, their chapters with URLs, starter
  citations for sponsored-projects work (APM 45.06 allowable costs, 45.08 cost
  sharing, 45.10 F&A rate, 45.15 subawards, FSH 5100 general research
  policy), and the usage rules.
- `guidance_search` — full text over the indexed policies. Returns policy
  number, title, chapter, URL and an excerpt.
- `guidance_get` — one policy as clean text by number (`APM 45.06`,
  `FSH 5100`), with its owner and revision date, so a citation can say which
  version was in force when a proposal went in.

The index is built by crawling the chapter pages and cached; a policy's text
is fetched on demand and cached by URL with a lifetime measured in days,
since revisions are rare and the page carries its own date. A page that comes
back as an application shell rather than text is reported as such, and the
policy's PDF is the fallback where one exists.

## Rules

- **Tools act.** A tool does one mechanical thing against one upstream and
  reports what it found. Which policy or regulation applies to a budget line
  is judgment, and judgment lives in a skill on the client side, never in a
  tool.
- **Every server stands alone.** Each can be run by itself over stdio or HTTP
  with nothing else present, and each has its own index tool that tells a
  model how to use it. No server calls another server's tools.
- **Institution-agnostic and institution-specific never mix.** A federal
  server has no Idaho defaults; the Idaho server hard-codes uidaho.edu. Shared
  code is plumbing only.
- **Be a polite upstream client.** One `User-Agent` naming this project and a
  contact address on every request; cache what does not change; on a 429,
  tell the model to wait rather than retrying blindly.

## Layout

```
ai4ra_mcp/
  app.py              builds the Starlette app: one Mount per server, one lifespan
  servers/
    ecfr/             server.py (FastMCP instance and tools), client code, tests
    grants/           server.py, grants_gov client, tests
    uidaho/           server.py, crawler, tests
  common/
    http.py           shared httpx client, User-Agent, TTL cache, 429 handling
    text.py           HTML and PDF to text (from mcp-ecfr's fetch.py)
deploy/
  Caddyfile           a site block that fronts the process
  ai4ra-mcp.service   a systemd unit
  Dockerfile
pyproject.toml
```

`notes/` and `admin/` are ignored by git and are for private working files.

## Running

```
uv sync
uv run ai4ra-mcp                  # all servers on http://127.0.0.1:8000/<name>/mcp
uv run ai4ra-mcp --only ecfr      # one server
uv run ai4ra-mcp --stdio ecfr     # one server over stdio, for local MCP clients
```

Each server is a `FastMCP` instance from the official Python SDK. The
process mounts each one's streamable-HTTP app at its path and runs their
session managers under a single lifespan. Streamable HTTP is the only
network transport; the Space's SSE endpoint is not carried over.

## Hosting

The intended host is a VM behind Caddy with a campus certificate: the same
arrangement the mindrouter-365 demo uses. Caddy terminates TLS and
reverse-proxies `/ecfr/*`, `/grants/*` and `/uidaho/*` to the process on
localhost; a systemd unit keeps the process up.

The Office add-in calls these servers from inside a browser engine, so each
must answer CORS preflight and allow the pane's origin. Public content is
served with `Access-Control-Allow-Origin: *`. A server that must be reachable
only on campus (a future one that reads an internal system) is a Caddy rule
and a firewall, not a code branch.

Why not the Hugging Face Space: it was the fastest public endpoint for a
summit, and Gradio was the way to put stdio tools behind HTTP at the time.
It sleeps when idle, imposes a tool-name prefix, and is one more origin to
trust. The SDK now serves HTTP directly, and the VM already has the
certificate and the proxy. The Space stays up until the VM copy is live and
the clients that name it have moved.

## Connecting

- **Claude.ai:** Settings → Connectors → Add custom connector, with the
  server's URL, for example `https://<host>/ecfr/mcp`. One connector per
  server.
- **Claude Code:** `claude mcp add --transport http ecfr https://<host>/ecfr/mcp`.
- **mindrouter-365:** an entry per server in the deployment's `sources.json`,
  with `url`, `label`, `description` and the Office hosts it applies to.

## Related

- [AI4RA/mcp-ecfr](https://github.com/AI4RA/mcp-ecfr): the eCFR server this
  supersedes, and the Space that serves it today.
- [ui-insight/mindrouter-365](https://github.com/ui-insight/mindrouter-365):
  the Office add-in that is the first client. Its issues 17 (the split into
  pane, servers and deployment) and 23 (the University of Idaho server) are
  the design record for this repository.
