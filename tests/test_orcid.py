"""orcid: the iD checksum, the record's nested groups slimmed, and the Solr query a search builds."""

from ai4ra_mcp.servers.orcid import server as orcid

EMPLOYMENT = {"put-code": 5934190, "department-name": "Office of Research and Economic Development", "role-title": "Director, Northwest Knowledge Network (NKN)",
              "start-date": {"year": {"value": "2010"}, "month": {"value": "10"}, "day": {"value": "15"}}, "end-date": None,
              "organization": {"name": "University of Idaho", "address": {"city": "Moscow", "region": "Idaho", "country": "US"}, "disambiguated-organization": None}, "visibility": "public"}
EDUCATION = {"put-code": 5934185, "department-name": "Bioinformatics and Computational Biology", "role-title": "Ph.D. in Bioinformatics and Computational Biology",
             "start-date": {"year": {"value": "2002"}, "month": {"value": "08"}, "day": None}, "end-date": {"year": {"value": "2008"}, "month": {"value": "12"}, "day": {"value": "15"}},
             "organization": {"name": "University of Idaho", "address": {"city": "Moscow", "region": "Idaho", "country": "US"}}, "visibility": "public"}
FUNDING = {"title": {"title": {"value": "ADVANCE Leadership Award: Women in Science and Engineering"}, "translated-title": None},
           "external-ids": {"external-id": [{"external-id-type": "grant_number", "external-id-value": "0536999", "external-id-url": {"value": "http://www.nsf.gov/awardsearch/showAward?AWD_ID=0536999"}, "external-id-relationship": "self"}]},
           "type": "grant", "start-date": {"year": {"value": "2006"}, "month": {"value": "04"}, "day": {"value": "01"}}, "end-date": {"year": {"value": "2007"}, "month": {"value": "03"}, "day": {"value": "31"}},
           "organization": {"name": "National Science Foundation - Directorate for Education and Human Resources", "address": {"city": "n/a", "region": None, "country": "US"}}, "put-code": 74458}
WORK = {"put-code": 221451839, "title": {"title": {"value": "MindRouter: Open-Source LLM Inference Gateway for Institutional AI Sovereignty"}, "subtitle": None},
        "external-ids": {"external-id": [{"external-id-type": "doi", "external-id-value": "10.1145/3785462.3815861", "external-id-url": {"value": "https://doi.org/10.1145/3785462.3815861"}, "external-id-relationship": "self"}]},
        "url": {"value": "https://doi.org/10.1145/3785462.3815861"}, "type": "conference-paper", "publication-date": {"year": {"value": "2026"}, "month": {"value": "07"}, "day": {"value": "26"}}, "journal-title": None}
RECORD = {"orcid-identifier": {"uri": "https://orcid.org/0000-0001-8781-2041", "path": "0000-0001-8781-2041", "host": "orcid.org"},
          "history": {"creation-method": "DIRECT", "last-modified-date": {"value": 1784717438554}, "claimed": True},
          "person": {"name": {"given-names": {"value": "Lucas"}, "family-name": {"value": "Sheneman"}, "credit-name": None, "visibility": "public"},
                     "other-names": {"other-name": [{"content": "Luke Sheneman"}]}, "biography": {"content": "Director of research computing.", "visibility": "public"},
                     "researcher-urls": {"researcher-url": [{"url-name": "NKN", "url": {"value": "https://www.northwestknowledge.net"}}]},
                     "emails": {"email": [{"email": "sheneman@uidaho.edu", "visibility": "public"}]}, "keywords": {"keyword": [{"content": "bioinformatics"}]}},
          "activities-summary": {"employments": {"affiliation-group": [{"summaries": [{"employment-summary": EMPLOYMENT}]}]},
                                 "educations": {"affiliation-group": [{"summaries": [{"education-summary": EDUCATION}]}]},
                                 "fundings": {"group": [{"funding-summary": [FUNDING]}]},
                                 "works": {"group": [{"work-summary": [WORK, {**WORK, "put-code": 1}]}, {"work-summary": [{**WORK, "put-code": 2, "external-ids": {"external-id": []}}]}]}}}
HIT = {"orcid-id": "0000-0001-8781-2041", "given-names": "Lucas", "family-names": "Sheneman", "credit-name": None, "other-name": [], "email": [], "institution-name": ["University of Idaho"]}


def test_orcid_checksum_iso_7064_mod_11_2():
    assert orcid.valid_orcid("0000-0001-8781-2041") == "0000-0001-8781-2041"
    assert orcid.valid_orcid("https://orcid.org/0000-0001-8388-606X") == "0000-0001-8388-606X"
    assert orcid.valid_orcid(" 0000-0002-1825-0097 ") == "0000-0002-1825-0097" and orcid.valid_orcid("0000-0001-8388-606x") == "0000-0001-8388-606X"
    assert orcid.valid_orcid("0000-0001-8388-6060") == "" and orcid.valid_orcid("0000-0001-8781-2042") == ""
    assert orcid.valid_orcid("0000000187812041") == "" and orcid.valid_orcid("") == "" and orcid.valid_orcid("Sheneman") == ""


def test_slim_record_reads_the_nested_groups():
    r = orcid.slim_record(RECORD)
    assert r["orcid"] == "0000-0001-8781-2041" and r["given_names"] == "Lucas" and r["other_names"] == ["Luke Sheneman"] and r["biography"] == "Director of research computing."
    assert r["emails"] == ["sheneman@uidaho.edu"] and r["keywords"] == ["bioinformatics"] and r["urls"] == [{"name": "NKN", "url": "https://www.northwestknowledge.net"}]
    e = r["employments"][0]
    assert e["organization"] == "University of Idaho" and e["role"].startswith("Director") and e["start"] == "2010-10-15" and e["end"] is None and e["current"] is True
    d = r["educations"][0]
    assert d["role"].startswith("Ph.D.") and d["start"] == "2002-08" and d["end"] == "2008-12-15" and d["current"] is False
    f = r["fundings"][0]
    assert f["title"].startswith("ADVANCE") and f["type"] == "grant" and f["grant_numbers"] == ["0536999"] and f["start"] == "2006-04-01" and f["organization"].startswith("National Science Foundation")
    assert r["works"]["count"] == 2 and len(r["works"]["works"]) == 2
    w = r["works"]["works"][0]
    assert w["doi"] == "10.1145/3785462.3815861" and w["year"] == "2026" and w["type"] == "conference-paper" and w["put_code"] == 221451839
    assert r["works"]["works"][1]["doi"] is None
    assert r["last_modified"] == "2026-07-22" and r["link"] == "https://orcid.org/0000-0001-8781-2041"


def test_slim_hit():
    h = orcid.slim_hit(HIT)
    assert h["orcid"] == "0000-0001-8781-2041" and h["institutions"] == ["University of Idaho"] and h["link"] == "https://orcid.org/0000-0001-8781-2041"


async def test_search_builds_a_solr_query_on_the_expanded_endpoint(monkeypatch):
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen["url"] = url
        seen["headers"] = headers
        seen.update(params or {})
        return {"expanded-result": [HIT], "num-found": 12}

    monkeypatch.setattr(orcid, "get_json", fake_get_json)
    orcid._cache._d.clear()
    out = await orcid.orcid_search(given_names="Lucas", family_name="Sheneman", affiliation="University of Idaho")
    assert seen["url"].endswith("/expanded-search/") and seen["headers"] == {"Accept": "application/json"}
    assert seen["q"] == 'given-names:Lucas AND family-name:Sheneman AND affiliation-org-name:"University of Idaho"' and seen["rows"] == 20 and seen["start"] == 0
    assert out["returned"] == 1 and out["total"] == 12 and out["next_start"] == 1 and out["people"][0]["family_name"] == "Sheneman"
    orcid._cache._d.clear()
    await orcid.orcid_search(query="family-name:Sheneman", rows=500, start=5)
    assert seen["q"] == "family-name:Sheneman" and seen["rows"] == 50 and seen["start"] == 5
    assert "error" in await orcid.orcid_search()


async def test_record_validates_the_id_and_fetches_json(monkeypatch):
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen["url"] = url
        seen["headers"] = headers
        return RECORD

    monkeypatch.setattr(orcid, "get_json", fake_get_json)
    orcid._cache._d.clear()
    out = await orcid.orcid_record("https://orcid.org/0000-0001-8781-2041")
    assert seen["url"].endswith("/0000-0001-8781-2041/record") and seen["headers"] == {"Accept": "application/json"} and out["family_name"] == "Sheneman"
    bad = await orcid.orcid_record("0000-0001-8781-2042")
    assert "check digit" in bad["error"]


async def test_lists_tools():
    assert {t.name for t in await orcid.mcp.list_tools()} == {"orcid_index", "orcid_search", "orcid_record"}
