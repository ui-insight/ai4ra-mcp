"""The AI4RA Unified Data Model (UDM) schema, read from where it is published and served in portions.

Upstream: the JSON the AI4RA-UDM repository publishes on GitHub Pages
(https://ui-insight.github.io/AI4RA-UDM/data/udm_schema.json, UDM 3), the machine-readable half of the
spec. AI4RA_MCP_UDM_SCHEMA_URL points at another copy; AI4RA_MCP_UDM_SCHEMA_FILE reads a local file
instead (a checkout of the repository, or a test fixture). Cached a day.

The whole file is a few hundred kilobytes, so it is served as an overview, one table at a time (from a
core module, an optional module or the implementation tables), or one named section at a time (a
convention, a module's text without its tables, the laws, the types). A file with no tables where UDM 3
keeps them is an error, not an empty model. Nothing here interprets the schema.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ai4ra_mcp.common.http import DAY, TTLCache, get_json

DEFAULT_URL = "https://ui-insight.github.io/AI4RA-UDM/data/udm_schema.json"
URL_ENV = "AI4RA_MCP_UDM_SCHEMA_URL"
FILE_ENV = "AI4RA_MCP_UDM_SCHEMA_FILE"
DASHBOARD = "https://ui-insight.github.io/AI4RA-UDM/"
_cache = TTLCache()


def source() -> str:
    path = os.environ.get(FILE_ENV, "").strip()
    return path or (os.environ.get(URL_ENV, "").strip() or DEFAULT_URL)


async def load_raw() -> dict:
    """The schema JSON as published: a local file when AI4RA_MCP_UDM_SCHEMA_FILE names one, else the URL, cached a day."""
    src = source()
    if not src.startswith(("http://", "https://")):
        return json.loads(Path(src).read_text(encoding="utf-8"))
    return await _cache.remember("raw:" + src, DAY, lambda: get_json(src))


def _norm(s: str) -> str:
    return "".join(ch for ch in str(s or "").lower() if ch.isalnum())


class Model:
    """The schema with its tables in one place: each core module's, each optional module's and the implementation
    tables, each knowing its module; the audit columns; and the named sections, every convention, every module's
    own text without its tables, the laws, the types and the metadata. A column carries its own synonyms and
    allowed values and a table its own constraints in the file, so nothing is folded in."""

    def __init__(self, raw: dict, src: str):
        self.raw = raw
        meta = raw.get("metadata") or {}
        self.version = meta.get("version")
        self.released = meta.get("released")
        self.source = src
        self.spec_source = meta.get("spec_source")
        modules = raw.get("modules") or {}
        conventions = raw.get("conventions") or {}
        self.tables: dict[str, dict] = {}
        self.core_modules: dict[str, dict] = {}
        self.modules: dict[str, dict] = {}
        self.sections: dict = dict(conventions)
        if "laws" in modules:
            self.sections["laws"] = modules["laws"]
        for group, into in (("core", self.core_modules), ("optional", self.modules)):
            for key, mod in (modules.get(group) or {}).items():
                name = mod.get("name", key)
                tables = mod.get("tables") or {}
                into[key] = {"key": key, "name": name, "story": mod.get("story", ""), "requires": mod.get("requires"), "tables": list(tables)}
                for t, spec in tables.items():
                    self.tables.setdefault(t, {"spec": spec, "module": name, "optional_module": key if group == "optional" else None})
                self.sections[key] = {k: v for k, v in mod.items() if k != "tables"}
        impl = (raw.get("implementation_tables") or {}).get("tables") or {}
        for t, spec in impl.items():
            self.tables.setdefault(t, {"spec": spec, "module": None, "optional_module": None})
        self.implementation_tables: list[str] = list(impl)
        for key in ("types", "metadata"):
            if key in raw:
                self.sections[key] = raw[key]
        if not self.tables:
            raise ValueError("the file holds no tables under modules.core, modules.optional or implementation_tables, "
                             "where UDM 3 keeps them; its shape has changed and this server must be updated to read it")
        self.audit_columns: dict = (conventions.get("audit_columns") or {}).get("columns") or {}

    def table_name(self, name: str) -> str | None:
        if name in self.tables:
            return name
        key = _norm(name)
        return next((t for t in self.tables if _norm(t) == key), None)

    def overview(self) -> dict:
        """What the file holds: the version, the modules and their tables, every table with a line, the audit columns, the sections."""
        tables = []
        for name, entry in self.tables.items():
            spec = entry["spec"]
            tables.append({"table": name, "module": entry["module"], "optional_module": entry["optional_module"],
                           "columns": len(spec.get("columns") or {}), "description": str(spec.get("description", ""))[:240]})
        sections = {k: (v[:200] if isinstance(v, str) else (f"{type(v).__name__} of {len(v)}" if hasattr(v, "__len__") else type(v).__name__))
                    for k, v in self.sections.items()}
        return {"udm_version": self.version, "released": self.released, "source": self.source, "spec_source": self.spec_source,
                "core_modules": [{"key": k, "name": v["name"], "tables": v["tables"], "story": str(v["story"])[:300]} for k, v in self.core_modules.items()],
                "optional_modules": [{"key": k, "name": v["name"], "requires": v["requires"], "tables": v["tables"], "story": str(v["story"])[:300]} for k, v in self.modules.items()],
                "implementation_tables": self.implementation_tables,
                "tables": tables, "audit_columns": list(self.audit_columns.keys()), "sections": sections}

    def table_json(self, name: str) -> dict | None:
        """One table as the file has it, its columns in the spec's order with their synonyms and allowed values, its
        constraints, and the audit columns every table carries."""
        real = self.table_name(name)
        if not real:
            return None
        entry = self.tables[real]
        spec = entry["spec"]
        return {"udm_version": self.version, "table": real, "module": entry["module"], "optional_module": entry["optional_module"],
                "description": spec.get("description", ""), "columns": spec.get("columns") or {},
                "audit_columns": self.audit_columns,
                **{k: v for k, v in spec.items() if k not in ("columns", "description")}}

    def section_json(self, key: str):
        return self.sections.get(key)


async def model() -> Model:
    src = source()
    if not src.startswith(("http://", "https://")):
        return Model(await load_raw(), src)
    return await _cache.remember("model:" + src, DAY, _build)


async def _build() -> Model:
    return Model(await load_raw(), source())
