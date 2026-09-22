"""A server's skills folder, served two ways from the same files.

`skills/catalog.json` lists components in the shape of AI4RA/prompt-library's
component_catalog.json; each `components/<slug>/prompt.md` has YAML front
matter and a preamble, then the prompt under `## Prompt`. `register_prompts`
puts each one on the server as an MCP prompt named by its slug, so a client
that speaks MCP gets the skill with the tools. `app.py` also serves the folder
as static files, so a client that reads catalogs by URL (the Office add-in)
gets the same components unchanged.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)


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


def register_prompts(server: MCPServer, skills_dir: Path) -> list[str]:
    """Register every catalogued component as an MCP prompt. Returns the slugs registered."""
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
            prompt.__doc__ = c.get("summary", "")
            return prompt

        server.prompt(name=slug, description=summary)(make())
        names.append(slug)
    return names
