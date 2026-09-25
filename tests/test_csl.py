"""csl: the Consolidated Screening List record shape slimmed, the search's parameters, and the missing-key answer.
Built from the public downloadable list (which needs no key), not the keyed search endpoint."""

import pytest

from ai4ra_mcp.servers.csl import server as csl

SDN = {"addresses": [{"city": "London", "country": "GB", "address": "4th Floor, 189 Marsh Wall", "state": None, "postal_code": "E14 9SH"},
                     {"city": "Havana", "country": "CU", "address": "Edificio Atlantic, Oficina 4 H", "state": None, "postal_code": "10400"}],
       "alt_names": ["HAVANA INTERNATIONAL BANK, LTD"], "citizenships": [], "dates_of_birth": [], "end_date": None, "entity_number": "906",
       "federal_register_notice": None, "id": "906",
       "ids": [{"type": "Company Number", "number": "01074897", "country": "GB", "issue_date": None, "expiration_date": None},
               {"type": "SWIFT/BIC", "number": "HAVIGB2L", "issue_date": None, "expiration_date": None}],
       "license_policy": None, "license_requirement": None, "name": "HAVIN BANK LIMITED", "nationalities": [], "places_of_birth": [],
       "programs": ["CUBA"], "remarks": None, "source": "Specially Designated Nationals (SDN) - Treasury Department",
       "source_information_url": "https://home.treasury.gov/policy-issues/financial-sanctions/specially-designated-nationals-and-blocked-persons-list-sdn-human-readable-lists",
       "source_list_url": "https://sanctionslist.ofac.treas.gov/Home/SdnList", "title": None, "type": "Entity"}
EL = {"source": "Entity List (EL) - Bureau of Industry and Security", "name": "Abdul Satar Ghoura",
      "addresses": [{"address": "501, 5th Floor, Amanullah Sancharaki Market", "city": "Kabul", "state": "", "postal_code": "", "country": "AF"}],
      "federal_register_notice": "76 FR 71867", "start_date": "2011-11-21", "standard_order": None, "license_policy": "Presumption of denial.",
      "license_requirement": "For all items subject to the EAR. (See §744.11 of the EAR).", "remarks": "",
      "source_list_url": "https://www.bis.gov/regulations/ear/744#supplement-4-744", "alt_names": None,
      "source_information_url": "https://www.bis.gov/licensing/guidance-on-end-user-and-end-use-controls-and-us-person-controls",
      "id": "b6e959b59898e975daaae8fae3a8da1ec522f9f888cafc0e6401a16d", "title": None}
ISN = {"source": "Nonproliferation Sanctions (ISN) - State Department", "programs": ["Chemical and Biological Weapons Act"], "name": "SPC Supachoke ",
       "federal_register_notice": "Vol. 59, No. 44, 03/07/1994", "start_date": "1994-02-08", "alt_names": ["Super Trade"], "country": "TH",
       "source_list_url": "https://www.state.gov/bureau-of-arms-control-and-nonproliferation/nonproliferation-sanctions",
       "source_information_url": "https://www.state.gov/bureau-of-arms-control-and-nonproliferation/nonproliferation-sanctions", "id": "2446250b"}
RESPONSE = {"total": 1, "offset": 0, "results": [SDN], "search_performed_at": "2026-09-25T04:15:00+00:00",
            "sources_used": [{"source": "Specially Designated Nationals (SDN) - Treasury Department", "source_last_updated": "2026-09-23T14:07:33+00:00", "import_rate": "Hourly"},
                             {"source": "Non-SDN Menu-Based Sanctions List (NS-MBS List) - Treasury Department", "source_last_updated": "2026-09-23T14:07:35+00:00"}]}


def test_slim_sdn_entity():
    r = csl.slim_result(SDN)
    assert r["source"] == "SDN" and r["entity_number"] == "906" and r["programs"] == ["CUBA"] and r["type"] == "Entity"
    assert r["alt_names"] == ["HAVANA INTERNATIONAL BANK, LTD"] and r["addresses"][1]["country"] == "CU"
    assert r["ids"][1] == {"type": "SWIFT/BIC", "number": "HAVIGB2L", "country": None, "issue_date": None, "expiration_date": None}
    assert r["link"].startswith("https://home.treasury.gov/") and r["source_list_url"].endswith("/SdnList")
    assert "dates_of_birth" not in r and "title" not in r


def test_slim_bis_and_state_records():
    e = csl.slim_result(EL)
    assert e["source"] == "EL" and e["entity_number"] is None and e["alt_names"] == [] and e["remarks"] is None
    assert e["license_policy"] == "Presumption of denial." and e["federal_register_notice"] == "76 FR 71867"
    i = csl.slim_result(ISN)
    assert i["source"] == "ISN" and i["country"] == "TH" and i["programs"] == ["Chemical and Biological Weapons Act"]
    assert csl._source_code("Non-SDN Menu-Based Sanctions List (NS-MBS List) - Treasury Department") == "NS-MBS"
    assert csl._source_code("Military End User (MEU) List - Bureau of Industry and Security") == "MEU"


async def test_search_sends_key_header_and_params(monkeypatch):
    monkeypatch.setenv(csl.KEY_ENV, "k123")
    csl._cache._d.clear()
    sent = {}

    async def fake_get(url, params=None, headers=None):
        sent.update(url=url, params=params, headers=headers)
        return RESPONSE

    monkeypatch.setattr(csl, "get_json", fake_get)
    out = await csl.csl_search("Havin Bank", fuzzy=False, sources="sdn, el", countries="gb,cu", type="entity", size=99)
    assert sent["url"] == csl.BASE and sent["headers"] == {"subscription-key": "k123"}
    assert sent["params"] == {"name": "Havin Bank", "fuzzy_name": "false", "offset": 0, "size": 50, "sources": "SDN,EL", "countries": "GB,CU", "type": "Entity"}
    assert out["returned"] == 1 and out["total"] == 1 and out["results"][0]["name"] == "HAVIN BANK LIMITED" and "next_offset" not in out
    assert out["sources_used"][1]["source"] == "NS-MBS"


async def test_search_validates(monkeypatch):
    monkeypatch.setenv(csl.KEY_ENV, "k123")
    assert "error" in await csl.csl_search("")
    assert "unknown source" in (await csl.csl_search("x", sources="SDN,BOGUS"))["error"]
    assert "type must" in (await csl.csl_search("x", type="Company"))["error"]


async def test_search_without_key(monkeypatch):
    monkeypatch.delenv(csl.KEY_ENV, raising=False)
    out = await csl.csl_search("Havin Bank")
    assert "no API key" in out["error"] and "developer.trade.gov" in out["error"]


async def test_sources_is_the_documented_thirteen():
    out = await csl.csl_sources()
    codes = {s["code"] for s in out["sources"]}
    assert codes == {"CAP", "CMIC", "DPL", "DTC", "EL", "FSE", "ISN", "MEU", "NS-MBS", "PLC", "SDN", "SSI", "UVL"}
    assert all(s["name"] and s["agency"] and s["what"] for s in out["sources"])


async def test_lists_tools():
    assert {t.name for t in await csl.mcp.list_tools()} == {"csl_index", "csl_search", "csl_sources"}
