"""Guides: every server with catalogued components has a <server>_guide tool that lists them and returns one by
name; a component whose category is guide names no client (no host, no client tool name, no cell address)."""

import re
from pathlib import Path

import pytest

from ai4ra_mcp.app import SERVERS
from ai4ra_mcp.common.skills import guide_get, guide_list, load_catalog, prompt_text

SERVERS_DIR = Path(__file__).parent.parent / "ai4ra_mcp" / "servers"
HOSTS = re.compile(r"\b(Excel|Word|PowerPoint|Outlook|Teams|MindRouter)\b")   # case-sensitive: "word" and "outlook" are ordinary nouns
CLIENT_WORDS = re.compile(r"\b(the pane|add-in|read_range|write_values|write_formulas|add_sheet|format_range|assert_cells|find_cells|get_workbook_overview|add_chart|edit_chart|tracked changes?|yellow)\b", re.I)
CELL = re.compile(r"\b[A-Z]{1,2}\d{2,3}\b|\b[A-Z]{1,2}\d{1,3}:[A-Z]{1,2}\d{1,3}\b")   # B14, G27:K35; not the NSF lines G1 to G6


def guides():
    out = []
    for name in SERVERS:
        skills = SERVERS_DIR / name / "skills"
        for c in load_catalog(skills).get("components", []):
            if c.get("category") == "guide":
                out.append((name, c, skills))
    return out


@pytest.mark.parametrize("name", [n for n in SERVERS if load_catalog(SERVERS_DIR / n / "skills").get("components")])
async def test_every_server_with_components_has_a_guide_tool(name):
    tools = {t.name: t for t in await SERVERS[name].list_tools()}
    tool = f"{name.replace('-', '_')}_guide"
    assert tool in tools and tools[tool].annotations.read_only_hint
    skills = SERVERS_DIR / name / "skills"
    listed = {g["name"] for g in guide_list(skills)}
    assert listed == {c["slug"] for c in load_catalog(skills)["components"]}
    first = next(iter(listed))
    g = guide_get(skills, first.upper().replace("-", " "))
    assert g["name"] == first and g["guide"] == prompt_text(skills, next(c for c in load_catalog(skills)["components"] if c["slug"] == first))
    assert guide_get(skills, "no-such-guide") is None


def test_the_guide_tools_answer_the_list_and_one_guide():
    import asyncio
    from ai4ra_mcp.servers.udm import server as udm
    tools = asyncio.run(udm.mcp.list_tools())
    assert any(t.name == "udm_guide" for t in tools)
    lst = asyncio.run(udm.mcp.call_tool("udm_guide", {}))
    body = lst[1] if isinstance(lst, tuple) else lst
    text = str(body)
    assert "udm-conversion-guide" in text
    one = asyncio.run(udm.mcp.call_tool("udm_guide", {"name": "udm-conversion-guide"}))
    assert "Rename" in str(one)
    missing = asyncio.run(udm.mcp.call_tool("udm_guide", {"name": "nope"}))
    assert "no guide named" in str(missing)


@pytest.mark.parametrize("server,component,skills", [(n, c, s) for n, c, s in guides()], ids=[c["slug"] for _, c, _ in guides()])
def test_a_guide_names_no_client(server, component, skills):
    text = prompt_text(skills, component).replace("Future Outlook", "")   # a heading the tells guide quotes, not the mail client
    hits = sorted({m.group(0) for m in HOSTS.finditer(text)} | {m.group(0) for m in CLIENT_WORDS.finditer(text)})
    assert not hits, f"{server}/{component['slug']} names a client: {hits}"
    cells = sorted({m.group(0) for m in CELL.finditer(text)})
    assert not cells, f"{server}/{component['slug']} names cells: {cells}"
    assert not any(r.startswith(("excel:", "word:", "powerpoint:", "outlook:", "skill_")) for r in component.get("requires", [])), component["requires"]
    for k in ("hosts", "fold", "assertions", "stages"):
        assert k not in component, k
    assert "template" not in component.get("paths", {})


def test_no_skill_on_any_server_names_a_client_or_assumes_an_open_document():
    """The test for any line: would it be wrong if the caller were Claude Desktop? A pull request body said it was
    opened from one client, and three skills read from or guarded "the open message", "the workbook or document"."""
    # the last alternative is a host tool's name (excel:read_range), not a word that stands before a colon
    named = re.compile(r"mindrouter|task ?pane|\bthe pane\b|add-in|\bopen (message|document|workbook)\b|workbook or document|listed with this request|\b(excel|word|powerpoint|outlook):[a-z_]", re.I)
    servers = Path(__file__).parent.parent / "ai4ra_mcp" / "servers"
    for name in SERVERS:
        for c in load_catalog(servers / name / "skills").get("components", []):
            found = named.search(prompt_text(servers / name / "skills", c))
            assert not found, f"{name}/{c['slug']} says {found.group(0)!r}"
            assert not any(r.startswith(("excel:", "word:", "powerpoint:", "outlook:", "skill_")) for r in c.get("requires", [])), c["slug"]
