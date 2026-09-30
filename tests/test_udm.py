"""Offline checks for the udm server: the schema served in portions from a fixture in the published file's
shape (a local file named by AI4RA_MCP_UDM_SCHEMA_FILE), with the synonyms and status taxonomies folded
into a table, the modules folded into the table list, and the conversion guide served as text."""

import json

import pytest

from ai4ra_mcp.servers.udm import schema
from ai4ra_mcp.servers.udm import server as udm

FIXTURE = {
    "metadata": {"name": "UDM", "version": "2.3.0", "released": "2026-08-26", "spec_source": "vignettes/udm-v2-system-of-record.md"},
    "column_synonyms": {"description": "x", "values": {
        "Award.Award_Number": "Sponsor Award Number, NoA Number, Grant Number",
        "Award.Award_Status": "Status, Award State",
        "Personnel.Last_Name": "Surname, Family Name",
    }},
    "universal_patterns": ["identifier convention", "role-named foreign keys"],
    "core_module_membership": {"Actors": ["Personnel"], "Funding Cycle": ["Award"]},
    "audit_columns": {"description": "Every table includes these columns.", "columns": {
        "Created_At": {"type": "DATETIME", "required": True, "description": "Row creation time"},
        "Source_System": {"type": "VARCHAR(50)", "required": False, "description": "The originating source system"},
        "Source_Record_ID": {"type": "VARCHAR(50)", "required": False, "description": "The originating record's identifier"},
        "Is_Active": {"type": "BOOLEAN", "required": True, "default": True, "description": "Default true"},
    }},
    "status_taxonomies": {"Award_Status": ["Pending", "Active", "Closing", "Closed", "Suspended", "Terminated"],
                          "Proposal.Decision_Status": ["Pending", "Funded", "Declined"]},
    "cross_row_constraints": [{"location": "Award", "rule": "Current_End_Date >= Original_Start_Date"}, {"location": "Budget", "rule": "x"}],
    "implementation_tables": ["AllowedValues", "BudgetCategory"],
    "optional_modules": {"description": "y", "modules": {"governance": {"name": "Governance", "story": "Committees.", "requires": [], "tables": {
        "Committee": {"description": "A standing committee", "columns": {
            "Committee_ID": {"type": "VARCHAR(50)", "primary_key": True, "required": True, "description": "PK"},
            "Committee_Name": {"type": "VARCHAR(255)", "required": True, "description": "Name"}}}},
        "cross_row_constraints": [{"location": "Committee", "rule": "y"}]}}},
    "tables": {
        "Award": {"core_module": "Funding Cycle", "description": "Funded agreements", "columns": {
            "Award_ID": {"type": "VARCHAR(50)", "primary_key": True, "required": True, "description": "PK"},
            "Award_Number": {"type": "VARCHAR(50)", "required": True, "description": "Sponsor-issued award number"},
            "Sponsor_Organization_ID": {"type": "VARCHAR(50)", "required": True, "references": {"table": "Organization", "column": "Organization_ID"}, "description": "Funder"},
            "Award_Status": {"type": "VARCHAR(50)", "required": True, "description": "Status"},
            "Original_Start_Date": {"type": "DATE", "required": True, "description": "Start"},
        }},
        "Personnel": {"core_module": "Actors", "description": "People", "columns": {
            "Personnel_ID": {"type": "VARCHAR(50)", "primary_key": True, "required": True, "description": "PK"},
            "Last_Name": {"type": "VARCHAR(100)", "required": True, "pii": True, "description": "Family"},
            "Person_Type": {"type": "VARCHAR(50)", "required": True, "allowed_values": ["Faculty", "Staff", "Student"], "description": "Class"},
        }},
    },
}


@pytest.fixture
def fixture_file(tmp_path, monkeypatch):
    p = tmp_path / "udm.json"
    p.write_text(json.dumps(FIXTURE))
    monkeypatch.setenv(schema.FILE_ENV, str(p))
    return p


def test_model_folds_modules_taxonomies_and_synonyms():
    m = schema.Model(FIXTURE, "fixture")
    assert m.version == "2.3.0" and set(m.tables) == {"Award", "Personnel", "Committee"}
    assert m.tables["Committee"]["optional_module"] == "governance" and m.tables["Committee"]["module"] == "Governance"
    assert m.taxonomies["Award"]["Award_Status"][1] == "Active" and m.taxonomies["Proposal"]["Decision_Status"] == ["Pending", "Funded", "Declined"]
    assert m.table_name("award") == "Award" and m.table_name("Nope") is None
    ov = m.overview()
    assert [t["table"] for t in ov["tables"]] == ["Award", "Personnel", "Committee"] and ov["audit_columns"] == ["Created_At", "Source_System", "Source_Record_ID", "Is_Active"]
    assert ov["optional_modules"][0]["tables"] == ["Committee"] and ov["implementation_tables"] == ["AllowedValues", "BudgetCategory"]
    assert "tables" not in ov["sections"] and ov["sections"]["universal_patterns"] == "list of 2"
    t = m.table_json("award")
    assert list(t["columns"]) == ["Award_ID", "Award_Number", "Sponsor_Organization_ID", "Award_Status", "Original_Start_Date"]
    assert t["columns"]["Award_Number"]["synonyms"] == "Sponsor Award Number, NoA Number, Grant Number"
    assert t["columns"]["Award_Status"]["allowed_values"] == FIXTURE["status_taxonomies"]["Award_Status"]
    assert t["columns"]["Sponsor_Organization_ID"]["references"]["table"] == "Organization"
    assert list(t["audit_columns"]) == ["Created_At", "Source_System", "Source_Record_ID", "Is_Active"]
    assert [c["rule"] for c in t["cross_row_constraints"]] == ["Current_End_Date >= Original_Start_Date"]
    assert [c["rule"] for c in m.table_json("Committee")["cross_row_constraints"]] == ["y"]
    assert m.table_json("Personnel")["columns"]["Person_Type"]["allowed_values"] == ["Faculty", "Staff", "Student"]


async def test_tools_serve_the_schema_in_portions(fixture_file):
    idx = await udm.udm_index()
    assert idx["udm_version"] == "2.3.0" and len(idx["tables"]) == 3 and idx["workflow"][0].startswith("udm_conversion_guide")
    t = await udm.udm_schema(table="award")
    assert t["table"] == "Award" and t["columns"]["Award_Status"]["allowed_values"][0] == "Pending" and t["link"].endswith("#table=Award")
    sec = await udm.udm_schema(section="universal_patterns")
    assert sec["content"] == ["identifier convention", "role-named foreign keys"]
    assert (await udm.udm_schema(section="tables"))["error"].startswith("'tables' is the whole")
    assert (await udm.udm_schema(section="nope"))["error"].startswith("no section")
    assert (await udm.udm_schema(table="Nope"))["error"].startswith("no UDM table")
    assert (await udm.udm_schema())["error"].startswith("give a table")
    assert (await udm.udm_schema(table="Award", section="x"))["error"].startswith("give table or section")


async def test_guide_is_served_as_text(fixture_file):
    g = await udm.udm_conversion_guide()
    assert g["udm_version"] == "2.3.0" and g["then"].startswith("udm_schema")
    text = g["guide"]
    for phrase in ("Rename", "Split", "Combine", "Transform", "Default", "Derive", "Resolve", "Route", "Generate", "Drop", "exactly one row per source row", "Source_System", "Ask once", "not a closed list", "Never invent a value"):
        assert phrase in text, phrase


async def test_unreadable_schema_is_reported_not_invented(tmp_path, monkeypatch):
    monkeypatch.setenv(schema.FILE_ENV, str(tmp_path / "missing.json"))
    r = await udm.udm_index()
    assert r["error"].startswith("the UDM schema could not be read") and "memory" in r["do_not"]
    g = await udm.udm_conversion_guide()
    assert g["udm_version"] is None and "Rename" in g["guide"]
