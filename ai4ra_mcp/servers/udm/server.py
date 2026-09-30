"""udm: the AI4RA Unified Data Model, the vendor-neutral schema for research-administration data.

Upstream: the schema JSON the AI4RA-UDM repository publishes on GitHub Pages
(https://ui-insight.github.io/AI4RA-UDM/data/udm_schema_v2.json). No key. Two things a model needs to
convert records to the UDM: the schema, served in portions (an overview, one table, one section), and
the conversion guide, the way the job is done written once as text. The conversion itself is the
model's judgment over the data it can see; nothing here interprets a header or a value.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.skills import register_prompts

from . import schema

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
GUIDE = Path(__file__).parent / "guide.md"
_BIG_SECTIONS = {"tables"}

mcp = MCPServer(
    "udm",
    instructions="The AI4RA Unified Data Model (UDM): the published schema in portions (overview, one table, one section) and the guide to converting records to it. Read udm_index first.",
)


async def _model():
    try:
        return await schema.model(), None
    except (ValueError, OSError) as e:
        return None, {"error": f"the UDM schema could not be read from {schema.source()}: {e}",
                      "do_not": "Do not describe the UDM from memory. Say the schema could not be read and stop there."}


def _link(table: str | None = None) -> str:
    return schema.DASHBOARD + (f"#table={table}" if table else "")


@mcp.tool(name="udm_index", annotations=_READ_ONLY)
async def udm_index() -> dict:
    """How to use the UDM tools, and the overview of the loaded schema. READ THIS FIRST: the version, the modules, every table with a line each, the audit columns, the sections, and the order to call the tools in."""
    m, err = await _model()
    if err:
        return err
    out = m.overview()
    out["workflow"] = ["udm_conversion_guide before converting anything: how the job is done, from looking at the data to the report",
                       "udm_schema with a table name for that table's columns in the spec's order, with types, required flags, references, allowed values, descriptions and synonyms, plus the audit columns and the constraints on it",
                       "udm_schema with a section name (from sections above) for one of the file's other parts verbatim: the universal patterns, the semantic conventions, the status taxonomies, the derived values"]
    out["notes"] = ["The synonyms are examples of what a column has been called elsewhere, not a closed list; read the data.",
                    f"Cite the dashboard, {schema.DASHBOARD}, as the link; a table's page is {_link('Award')}."]
    out["link"] = _link()
    return out


@mcp.tool(name="udm_schema", annotations=_READ_ONLY)
async def udm_schema(table: str = "", section: str = "") -> dict:
    """A portion of the UDM schema JSON: one table (its columns in the spec's order with types, required flags, references, allowed values, descriptions and synonyms; the audit columns; the constraints on it), or one top-level section verbatim.

    Args:
        table: A table's name, e.g. 'Award', 'Personnel', 'Subaward' (case and spacing forgiven). udm_index lists them.
        section: A top-level section of the file instead, e.g. 'universal_patterns', 'semantic_conventions', 'status_taxonomies', 'column_synonyms', 'derived_values'. udm_index lists them. 'tables' is refused: ask for one table.
    """
    m, err = await _model()
    if err:
        return err
    table, section = (table or "").strip(), (section or "").strip()
    if table and section:
        return {"error": "give table or section, not both"}
    if table:
        t = m.table_json(table)
        if not t:
            return {"error": f"no UDM table named {table!r}; udm_index lists them", "udm_version": m.version}
        t["link"] = _link(t["table"])
        return t
    if section:
        if section in _BIG_SECTIONS:
            return {"error": f"'{section}' is the whole table set; ask for one table with table=", "udm_version": m.version}
        body = m.section_json(section)
        if body is None:
            return {"error": f"no section {section!r}; udm_index lists them", "udm_version": m.version}
        return {"udm_version": m.version, "section": section, "content": body, "link": _link()}
    return {"error": "give a table name or a section name; udm_index lists both", "udm_version": m.version}


@mcp.tool(name="udm_conversion_guide", annotations=_READ_ONLY)
async def udm_conversion_guide() -> dict:
    """The guide to converting records to the UDM: look at the data, choose the table, map each column from its name, synonyms, description and values, conform dates, booleans, vocabularies and amounts, fill provenance, ask once, and report. Text for the model to follow."""
    m, err = await _model()
    version = m.version if m else None
    return {"udm_version": version, "guide": GUIDE.read_text(encoding="utf-8"),
            "then": "udm_schema with the table's name, once you know what one row is.", "link": _link()}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
