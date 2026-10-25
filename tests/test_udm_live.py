"""The published UDM schema read live: the file is where schema.DEFAULT_URL says and in the shape the server
reads, so the next rename or reshape upstream fails here and not in a person's conversion. Needs the network."""

from ai4ra_mcp.servers.udm import schema


async def test_the_published_schema_loads_with_tables(monkeypatch):
    monkeypatch.delenv(schema.FILE_ENV, raising=False)
    monkeypatch.delenv(schema.URL_ENV, raising=False)
    m = await schema.model()
    assert m.version and m.core_modules and m.audit_columns
    assert {"Award", "Personnel", "AllowedValues"} <= set(m.tables)
    assert m.table_json("Award")["columns"]["Award_Number"]["synonyms"]
    assert "Is_Active" in m.audit_columns
    raw = m.raw
    assert len(m.sections) == len(raw["conventions"]) + 1 + len(raw["modules"]["core"]) + len(raw["modules"]["optional"]) + 2, "two sections share a name"
