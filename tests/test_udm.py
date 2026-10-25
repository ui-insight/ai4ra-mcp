"""Offline checks for the udm server: the schema served in portions from a fixture in the published file's
UDM 3 shape (a local file named by AI4RA_MCP_UDM_SCHEMA_FILE), with the core, optional and implementation
tables in one list, the conventions and the modules' own text as sections, a file with no tables refused,
and the conversion guide served as text. tests/test_udm_live.py reads the published file."""

import json

import pytest

from ai4ra_mcp.servers.udm import schema
from ai4ra_mcp.servers.udm import server as udm

FIXTURE = {
    "metadata": {"name": "UDM", "version": "3.0.0", "released": "2026-10-22", "spec_source": "vignettes/udm-system-of-record.md"},
    "types": {"description": "abstract types", "abstract": ["ID", "ShortCode", "Status", "Date"]},
    "conventions": {
        "identifier": {"name": "Identifier convention", "description": "Every table has a primary key named TableName_ID."},
        "lifecycle_stage": {"name": "Lifecycle_Stage discriminator", "tables": {"Budget": ["Proposed", "Actual"]}},
        "audit_columns": {"description": "Every table includes these columns.", "columns": {
            "Created_At": {"type": "Timestamp", "required": True, "description": "Row creation time"},
            "Source_System": {"type": "ShortCode", "required": False, "description": "The originating source system"},
            "Source_Record_ID": {"type": "ID", "required": False, "description": "The originating record's identifier"},
            "Is_Active": {"type": "Boolean", "required": True, "default": True, "description": "Default true"},
        }},
    },
    "modules": {
        "description": "Everything specified is a module.",
        "laws": {"capability_criterion": "x", "encapsulation_rule": "y"},
        "core": {
            "actors": {"name": "Actors", "story": "We track the people", "tables": {
                "Personnel": {"description": "People", "columns": {
                    "Personnel_ID": {"type": "ID", "primary_key": True, "required": True, "description": "PK"},
                    "Last_Name": {"type": "ShortName", "required": True, "pii": True, "description": "Family", "synonyms": "Surname, Family Name"},
                    "Person_Type": {"type": "Status", "required": True, "allowed_values": ["Faculty", "Staff", "Student"], "description": "Class"},
                }}}, "example_views": [{"name": "vw_People"}]},
            "funding_cycle": {"name": "Funding Cycle", "story": "We pursue and manage funded agreements", "tables": {
                "Award": {"description": "Funded agreements", "columns": {
                    "Award_ID": {"type": "ID", "primary_key": True, "required": True, "description": "PK"},
                    "Award_Number": {"type": "ShortCode", "required": True, "description": "Sponsor-issued award number", "synonyms": "Sponsor Award Number, NoA Number, Grant Number"},
                    "Sponsor_Organization_ID": {"type": "ID", "required": True, "references": {"table": "Organization", "column": "Organization_ID"}, "description": "Funder"},
                    "Award_Status": {"type": "Status", "required": True, "allowed_values": ["Pending", "Active", "Closed"], "description": "Status"},
                }, "constraints": [{"rule": "Current_End_Date >= Original_Start_Date"}]}},
                "conventions": [{"name": "Modification vs Previous_Award_ID"}]},
        },
        "optional": {"governance": {"name": "Governance", "story": "Committees.", "requires": {"core": ">=2.3.0", "modules": []}, "notes": "n", "tables": {
            "Committee": {"description": "A standing committee", "columns": {
                "Committee_ID": {"type": "ID", "primary_key": True, "required": True, "description": "PK"},
                "Committee_Name": {"type": "MediumName", "required": True, "description": "Name"}},
                "constraints": [{"rule": "y"}]}}}},
    },
    "implementation_tables": {"description": "z", "tables": {"AllowedValues": {"description": "Vocabularies", "columns": {
        "AllowedValue_ID": {"type": "ID", "primary_key": True, "required": True, "description": "PK"}}}}},
}


@pytest.fixture
def fixture_file(tmp_path, monkeypatch):
    p = tmp_path / "udm.json"
    p.write_text(json.dumps(FIXTURE))
    monkeypatch.setenv(schema.FILE_ENV, str(p))
    return p


def test_model_reads_the_modules_and_the_sections():
    m = schema.Model(FIXTURE, "fixture")
    assert m.version == "3.0.0" and list(m.tables) == ["Personnel", "Award", "Committee", "AllowedValues"]
    assert m.tables["Award"]["module"] == "Funding Cycle" and m.tables["Award"]["optional_module"] is None
    assert m.tables["Committee"]["optional_module"] == "governance" and m.tables["Committee"]["module"] == "Governance"
    assert m.tables["AllowedValues"]["module"] is None and m.implementation_tables == ["AllowedValues"]
    assert m.table_name("award") == "Award" and m.table_name("allowed values") == "AllowedValues" and m.table_name("Nope") is None
    ov = m.overview()
    assert [t["table"] for t in ov["tables"]] == ["Personnel", "Award", "Committee", "AllowedValues"]
    assert ov["audit_columns"] == ["Created_At", "Source_System", "Source_Record_ID", "Is_Active"]
    assert [(c["key"], c["tables"]) for c in ov["core_modules"]] == [("actors", ["Personnel"]), ("funding_cycle", ["Award"])]
    assert ov["optional_modules"][0]["tables"] == ["Committee"] and ov["optional_modules"][0]["requires"]["core"] == ">=2.3.0"
    assert list(ov["sections"]) == ["identifier", "lifecycle_stage", "audit_columns", "laws", "actors", "funding_cycle", "governance", "types", "metadata"]
    assert m.section_json("funding_cycle") == {"name": "Funding Cycle", "story": "We pursue and manage funded agreements", "conventions": [{"name": "Modification vs Previous_Award_ID"}]}
    t = m.table_json("award")
    assert list(t["columns"]) == ["Award_ID", "Award_Number", "Sponsor_Organization_ID", "Award_Status"]
    assert t["columns"]["Award_Number"]["synonyms"] == "Sponsor Award Number, NoA Number, Grant Number"
    assert t["columns"]["Award_Status"]["allowed_values"] == ["Pending", "Active", "Closed"]
    assert t["columns"]["Sponsor_Organization_ID"]["references"]["table"] == "Organization"
    assert list(t["audit_columns"]) == ["Created_At", "Source_System", "Source_Record_ID", "Is_Active"]
    assert [c["rule"] for c in t["constraints"]] == ["Current_End_Date >= Original_Start_Date"]
    assert [c["rule"] for c in m.table_json("Committee")["constraints"]] == ["y"]


def test_a_file_with_no_tables_is_an_error_not_an_empty_model():
    v2 = {"metadata": {"version": "2.3.0"}, "tables": {"Award": {"columns": {}}}, "audit_columns": {"columns": {}}}
    with pytest.raises(ValueError, match="no tables"):
        schema.Model(v2, "old shape")


async def test_tools_serve_the_schema_in_portions(fixture_file):
    idx = await udm.udm_index()
    assert idx["udm_version"] == "3.0.0" and len(idx["tables"]) == 4 and idx["workflow"][0].startswith("udm_guide")
    t = await udm.udm_schema(table="award")
    assert t["table"] == "Award" and t["columns"]["Award_Status"]["allowed_values"][0] == "Pending" and t["link"].endswith("#table=Award")
    sec = await udm.udm_schema(section="lifecycle_stage")
    assert sec["content"]["tables"] == {"Budget": ["Proposed", "Actual"]}
    assert (await udm.udm_schema(section="governance"))["content"]["notes"] == "n"
    assert (await udm.udm_schema(section="modules"))["error"].startswith("'modules' holds the tables")
    assert (await udm.udm_schema(section="nope"))["error"].startswith("no section")
    assert (await udm.udm_schema(table="Nope"))["error"].startswith("no UDM table")
    assert (await udm.udm_schema())["error"].startswith("give a table")
    assert (await udm.udm_schema(table="Award", section="x"))["error"].startswith("give table or section")


async def test_guide_is_served_as_a_component(fixture_file):
    from ai4ra_mcp.common.skills import guide_get, guide_list
    assert [g["name"] for g in guide_list(udm.SKILLS_DIR)] == ["udm-conversion-guide"]
    g = guide_get(udm.SKILLS_DIR, "UDM conversion guide")
    assert g["version"] == "0.3.0" and g["category"] == "guide"
    text = g["guide"]
    for phrase in ("Rename", "Split", "Combine", "Transform", "Default", "Derive", "Resolve", "Route", "Generate", "Drop", "exactly one row per source row", "Source_System", "Ask once", "not a closed list", "Never invent a value"):
        assert phrase in text, phrase


async def test_unreadable_schema_is_reported_not_invented(tmp_path, monkeypatch):
    monkeypatch.setenv(schema.FILE_ENV, str(tmp_path / "missing.json"))
    r = await udm.udm_index()
    assert r["error"].startswith("the UDM schema could not be read") and "memory" in r["do_not"]


async def test_a_file_in_another_shape_is_reported(tmp_path, monkeypatch):
    p = tmp_path / "v2.json"
    p.write_text(json.dumps({"metadata": {"version": "2.3.0"}, "tables": {"Award": {"columns": {}}}}))
    monkeypatch.setenv(schema.FILE_ENV, str(p))
    r = await udm.udm_index()
    assert r["error"].startswith("the UDM schema could not be read") and "no tables" in r["error"]
