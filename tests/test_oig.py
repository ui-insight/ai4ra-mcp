"""oig: the LEIE CSV parsed, rows slimmed, the name and NPI matching, and the download replaced so nothing touches the network."""

import pytest

from ai4ra_mcp.servers.oig import server as oig

CSV = '''LASTNAME,FIRSTNAME,MIDNAME,BUSNAME,GENERAL,SPECIALTY,UPIN,NPI,DOB,ADDRESS,CITY,STATE,ZIP,EXCLTYPE,EXCLDATE,REINDATE,WAIVERDATE,WVRSTATE
"","","","#1 MARKETING SERVICE, INC","OTHER BUSINESS","SOBER HOME","","0000000000","","239 BRIGHTON BEACH AVENUE","BROOKLYN","NY","11235","1128a1","20200319","00000000","00000000",""
"","","","101 FIRST CARE PHARMACY INC","OTHER BUSINESS","PHARMACY","","1972902351","","C/O 609 W 191ST STREET, APT D","NEW YORK","NY","10040","1128b8","20220320","00000000","00000000",""
"SMITH","JOHN","A","","IND- LIC HC SERV PRO","NURSE/NURSES AIDE","","1234567893","19700102","1 MAIN ST","BOISE","ID","83702","1128b4","20190515","00000000","00000000",""
"SMITH","JOHNATHAN","","","IND- LIC HC SERV PRO","PHYSICIAN (MD, DO)","","0000000000","19650304","2 OAK ST","SEATTLE","WA","98101","1128a1","20100101","20180601","00000000",""
"JOHNSON","MARY","","","IND- LIC HC SERV PRO","PHARMACIST","","","","3 ELM ST","BOISE","ID","83702","1128b14","20210707","00000000","20220101","ID"
'''


async def _fake_download():
    return CSV


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    oig._cache._d.clear()
    monkeypatch.setattr(oig, "download_csv", _fake_download)


def test_parse_csv():
    rows = oig.parse_csv(CSV)
    assert len(rows) == 5 and rows[0]["BUSNAME"] == "#1 MARKETING SERVICE, INC" and rows[2]["LASTNAME"] == "SMITH" and rows[2]["NPI"] == "1234567893"


def test_slim_row_business_and_person():
    rows = oig.parse_csv(CSV)
    b = oig.slim_row(rows[0])
    assert b["name"] is None and b["business"] == "#1 MARKETING SERVICE, INC" and b["npi"] is None
    assert b["exclusion_type"] == "1128a1" and b["exclusion_meaning"].startswith("mandatory: conviction of a program-related crime")
    assert b["exclusion_date"] == "2020-03-19" and b["reinstatement_date"] is None and b["waiver_date"] is None
    p = oig.slim_row(rows[2])
    assert p["name"] == "SMITH, JOHN A" and p["business"] is None and p["npi"] == "1234567893" and p["date_of_birth"] == "1970-01-02" and p["state"] == "ID"
    w = oig.slim_row(rows[4])
    assert w["name"] == "JOHNSON, MARY" and w["waiver_date"] == "2022-01-01" and w["waiver_state"] == "ID" and w["npi"] is None
    assert oig.slim_row(rows[3])["reinstatement_date"] == "2018-06-01"


def test_match_rows_by_words_npi_state_and_type():
    rows = oig.parse_csv(CSV)
    assert [r["FIRSTNAME"] for r in oig.match_rows(rows, name="john smith")] == ["JOHN", "JOHNATHAN"]
    assert [r["FIRSTNAME"] for r in oig.match_rows(rows, name="Smith, John A.")] == ["JOHN"]
    assert [r["BUSNAME"] for r in oig.match_rows(rows, name="first care pharmacy")] == ["101 FIRST CARE PHARMACY INC"]
    assert oig.match_rows(rows, name="smith zzz") == []
    assert [r["LASTNAME"] for r in oig.match_rows(rows, npi="1234567893")] == ["SMITH"]
    assert [r["LASTNAME"] for r in oig.match_rows(rows, state="id")] == ["SMITH", "JOHNSON"]
    assert [r["LASTNAME"] for r in oig.match_rows(rows, name="smith", exclusion_type="1128A1")] == ["SMITH"]


async def test_search_downloads_once_and_reports_as_of(monkeypatch):
    calls = []

    async def counting():
        calls.append(1)
        return CSV

    monkeypatch.setattr(oig, "download_csv", counting)
    status = await oig.oig_leie_status()
    assert status["loaded"] is False and status["rows"] == 0
    out = await oig.oig_leie_search(name="smith", limit=1)
    assert out["total"] == 2 and out["returned"] == 1 and out["exclusions"][0]["name"] == "SMITH, JOHN A"
    assert out["link"] == "https://exclusions.oig.hhs.gov/" and out["list_as_of"]
    again = await oig.oig_leie_search(npi="1972902351")
    assert again["exclusions"][0]["business"] == "101 FIRST CARE PHARMACY INC" and len(calls) == 1
    status = await oig.oig_leie_status()
    assert status["loaded"] is True and status["rows"] == 5 and status["list_as_of"] == out["list_as_of"]


async def test_search_validates():
    assert "error" in await oig.oig_leie_search()
    assert "10 digits" in (await oig.oig_leie_search(npi="123"))["error"]


async def test_lists_tools():
    assert {t.name for t in await oig.mcp.list_tools()} == {"oig_leie_index", "oig_leie_search", "oig_leie_status"}
