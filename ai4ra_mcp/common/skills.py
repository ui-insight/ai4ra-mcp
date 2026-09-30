"""A server's skills folder, served three ways from the same files.

`skills/catalog.json` lists components in the shape of AI4RA/prompt-library's
component_catalog.json; each `components/<slug>/prompt.md` has YAML front
matter and a preamble, then the prompt under `## Prompt`. `register_prompts`
puts each one on the server as an MCP prompt named by its slug, and adds one
tool, `<server>_guide`, that lists the components and returns one by name, so
a client that lists tools but not prompts still gets them and a model can fetch
a guide at the moment the job comes up. `app.py` also serves the folder as
static files, so a client that reads catalogs by URL gets the same components
unchanged.

A guide is a component that says what a correct result is in terms that name
no client: no host, no tool names, no cells. What a client does with it is the
client's (decided 2026-09-30).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}


def load_catalog(skills_dir: Path) -> dict:
    path = skills_dir / "catalog.json"
    if not path.exists():
        return {"components": []}
    return json.loads(path.read_text(encoding="utf-8"))


def prompt_text(skills_dir: Path, component: dict) -> str:
    """The prompt.md body without its front matter: the preamble and the prompt."""
    rel = component.get("paths", {}).get("prompt") or f"components/{component['slug']}/prompt.md"
    text = (skills_dir / rel).read_text(encoding="utf-8")
    return _FRONT_MATTER.sub("", text, count=1).strip()


def guide_list(skills_dir: Path) -> list[dict]:
    """Every catalogued component whose prompt file exists: name, summary, version, category."""
    out = []
    for c in load_catalog(skills_dir).get("components", []):
        rel = c.get("paths", {}).get("prompt") or f"components/{c['slug']}/prompt.md"
        if (skills_dir / rel).exists():
            out.append({"name": c["slug"], "summary": c.get("summary", ""), "version": c.get("version"), "category": c.get("category")})
    return out


def guide_get(skills_dir: Path, name: str) -> dict | None:
    """One component's text by slug (case and spacing forgiven), with its version; None when there is none."""
    key = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    for c in load_catalog(skills_dir).get("components", []):
        if re.sub(r"[^a-z0-9]", "", c["slug"].lower()) == key:
            rel = c.get("paths", {}).get("prompt") or f"components/{c['slug']}/prompt.md"
            if not (skills_dir / rel).exists():
                return None
            return {"name": c["slug"], "version": c.get("version"), "category": c.get("category"), "summary": c.get("summary", ""),
                    "guide": prompt_text(skills_dir, c)}
    return None


def register_prompts(server: MCPServer, skills_dir: Path) -> list[str]:
    """Register every catalogued component as an MCP prompt, and the server's `<server>_guide` tool when it has any.
    Returns the slugs registered."""
    names: list[str] = []
    for component in load_catalog(skills_dir).get("components", []):
        slug = component["slug"]
        summary = component.get("summary", "")
        rel = component.get("paths", {}).get("prompt") or f"components/{slug}/prompt.md"
        if not (skills_dir / rel).exists():
            continue

        def make(c=component):
            def prompt() -> str:
                return prompt_text(skills_dir, c)
            prompt.__name__ = c["slug"].replace("-", "_")
            return prompt

        server.prompt(name=slug, description=summary)(make())
        names.append(slug)

    if names:
        tool_name = f"{server.name.replace('-', '_')}_guide"
        listed = ", ".join(names)

        async def guide(name: str = "") -> dict:
            if not (name or "").strip():
                return {"server": server.name, "guides": guide_list(skills_dir),
                        "how": "Call again with name set to the one that covers the job, before doing the job, and follow it. It says what a correct result is; where the result goes is yours."}
            g = guide_get(skills_dir, name)
            if not g:
                return {"error": f"no guide named {name!r} on {server.name}; the guides are {listed}"}
            return {"server": server.name, **g}

        guide.__doc__ = (f"A guide from the {server.name} server: how one job is done, as text to follow, in terms that name no client. "
                         f"Without a name, the list ({listed}); with one, that guide. Fetch the guide that covers the job before doing it.\n\n"
                         "Args:\n    name: The guide's name from the list, e.g. one of the slugs above. Empty for the list.")
        server.tool(name=tool_name, annotations=_READ_ONLY)(guide)
    return names
