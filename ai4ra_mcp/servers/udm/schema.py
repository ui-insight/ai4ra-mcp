"""The AI4RA Unified Data Model (UDM) v2 schema, read from where it is published and served in portions.

Upstream: the JSON the AI4RA-UDM repository publishes on GitHub Pages
(https://ui-insight.github.io/AI4RA-UDM/data/udm_schema_v2.json), the machine-readable half of the
spec. AI4RA_MCP_UDM_SCHEMA_URL points at another copy; AI4RA_MCP_UDM_SCHEMA_FILE reads a local file
instead (a checkout of the repository, or a test fixture). Cached a day.

The whole file is a few hundred kilobytes, so it is served as an overview, one table at a time (with
the synonyms and the status taxonomy the file keeps apart from the table folded in), or one top-level
section at a time. Nothing here interprets the schema.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ai4ra_mcp.common.http import DAY, TTLCache, get_json

DEFAULT_URL = "https://ui-insight.github.io/AI4RA-UDM/data/udm_schema_v2.json"
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
    """The schema with its tables in one place: the core tables and the optional modules' tables, each
    knowing its module; the synonyms and status taxonomies keyed by table; the audit columns; the constraints."""

    def __init__(self, raw: dict, src: str):
        self.raw = raw
        meta = raw.get("metadata") or {}
        self.version = meta.get("version")
        self.released = meta.get("released")
        self.source = src
        self.spec_source = meta.get("spec_source")
        self.synonyms: dict[str, str] = ((raw.get("column_synonyms") or {}).get("values")) or {}
        self.tables: dict[str, dict] = {}
        for name, spec in (raw.get("tables") or {}).items():
            self.tables[name] = {"spec": spec, "module": spec.get("core_module") or "", "optional_module": None}
        self.modules: dict[str, dict] = {}
        for key, mod in ((raw.get("optional_modules") or {}).get("modules") or {}).items():
            self.modules[key] = {"key": key, "name": mod.get("name", key), "story": mod.get("story", ""), "requires": mod.get("requires") or [],
                                 "tables": list((mod.get("tables") or {}).keys())}
            for name, spec in (mod.get("tables") or {}).items():
                self.tables.setdefault(name, {"spec": spec, "module": mod.get("name", key), "optional_module": key})
        self.audit_columns: dict = ((raw.get("audit_columns") or {}).get("columns")) or {}
        self.taxonomies: dict[str, dict[str, list]] = {}
        for key, values in (raw.get("status_taxonomies") or {}).items():
            if not isinstance(values, list):
                continue
            if "." in key:
                t, c = key.split(".", 1)
                self.taxonomies.setdefault(t, {})[c] = values
            else:
                for t, entry in self.tables.items():
                    if key in (entry["spec"].get("columns") or {}):
                        self.taxonomies.setdefault(t, {})[key] = values
        self.constraints: list[dict] = [c for c in (raw.get("cross_row_constraints") or []) if isinstance(c, dict)]
        for mod in ((raw.get("optional_modules") or {}).get("modules") or {}).values():
            self.constraints += [c for c in (mod.get("cross_row_constraints") or []) if isinstance(c, dict)]
        self.core_modules: dict[str, list[str]] = raw.get("core_module_membership") or {}
        it = raw.get("implementation_tables")
        self.implementation_tables: list[str] = [t for t in it if isinstance(t, str)] if isinstance(it, list) else []

    def table_name(self, name: str) -> str | None:
        if name in self.tables:
            return name
        key = _norm(name)
        return next((t for t in self.tables if _norm(t) == key), None)

    def overview(self) -> dict:
        """What the file holds: the version, the modules and their tables with a line each, the audit columns, the sections."""
        tables = []
        for name, entry in self.tables.items():
            spec = entry["spec"]
            tables.append({"table": name, "module": entry["module"], "optional_module": entry["optional_module"],
                           "columns": len(spec.get("columns") or {}), "description": str(spec.get("description", ""))[:240]})
        sections = {k: (v[:200] if isinstance(v, str) else (f"{type(v).__name__} of {len(v)}" if hasattr(v, "__len__") else type(v).__name__))
                    for k, v in self.raw.items() if k != "tables"}
        return {"udm_version": self.version, "released": self.released, "source": self.source, "spec_source": self.spec_source,
                "core_modules": [{"module": m, "tables": ts} for m, ts in self.core_modules.items()],
                "implementation_tables": self.implementation_tables,
                "optional_modules": [{"key": k, "name": v["name"], "requires": v["requires"], "tables": v["tables"], "story": str(v["story"])[:300]} for k, v in self.modules.values() and self.modules.items()],
                "tables": tables, "audit_columns": list(self.audit_columns.keys()), "sections": sections}

    def table_json(self, name: str) -> dict | None:
        """One table as the file has it, with each column's synonyms and, where the file keeps the vocabulary in
        status_taxonomies rather than on the column, its allowed values; then the audit columns and the constraints."""
        real = self.table_name(name)
        if not real:
            return None
        entry = self.tables[real]
        spec = entry["spec"]
        tax = self.taxonomies.get(real, {})
        columns = {}
        for col, cs in (spec.get("columns") or {}).items():
            c = dict(cs)
            syn = self.synonyms.get(f"{real}.{col}")
            if syn:
                c["synonyms"] = syn
            if "allowed_values" not in c and col in tax:
                c["allowed_values"] = tax[col]
            columns[col] = c
        return {"udm_version": self.version, "table": real, "module": entry["module"], "optional_module": entry["optional_module"],
                "description": spec.get("description", ""), "columns": columns,
                "audit_columns": self.audit_columns,
                "cross_row_constraints": [c for c in self.constraints if str(c.get("location", "")).split(".")[0].split(" ")[0] == real],
                **{k: v for k, v in spec.items() if k not in ("columns", "description", "core_module")}}

    def section_json(self, key: str):
        return self.raw.get(key)


async def model() -> Model:
    src = source()
    if not src.startswith(("http://", "https://")):
        return Model(await load_raw(), src)
    return await _cache.remember("model:" + src, DAY, _build)


async def _build() -> Model:
    return Model(await load_raw(), source())
