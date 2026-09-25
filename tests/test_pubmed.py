"""pubmed: esummary and idconv shapes slimmed, the esearch parameters, the optional key, and bad input."""

from ai4ra_mcp.servers.pubmed import server as pm

SUMMARY = {"uid": "37391585", "pubdate": "2023 Jun 30", "epubdate": "2023 Jun 30", "source": "Sci Rep",
           "authors": [{"name": f"Author {i}", "authtype": "Author", "clusterid": ""} for i in range(16)], "lastauthor": "Chen JN",
           "title": "Molecular cloning, prokaryotic expression and its application potential evaluation of interferon (IFN)-ω of forest musk deer.",
           "volume": "13", "issue": "1", "pages": "10625", "pubtype": ["Journal Article", "Research Support, Non-U.S. Gov't"],
           "articleids": [{"idtype": "pubmed", "idtypen": 1, "value": "37391585"}, {"idtype": "pmc", "idtypen": 8, "value": "PMC10313714"},
                          {"idtype": "pmcid", "idtypen": 5, "value": "pmc-id: PMC10313714;"}, {"idtype": "doi", "idtypen": 3, "value": "10.1038/s41598-023-37437-x"},
                          {"idtype": "pii", "idtypen": 4, "value": "10.1038/s41598-023-37437-x"}],
           "history": [{"pubstatus": "received", "date": "2022/12/12 00:00"}, {"pubstatus": "pmc-release", "date": "2023/06/30 00:00"}],
           "fulljournalname": "Scientific reports", "elocationid": "doi: 10.1038/s41598-023-37437-x", "sortpubdate": "2023/06/30 00:00"}
NO_PMC = {"uid": "35086793", "pubdate": "2022 Jan", "source": "J Virol", "authors": [{"name": "Lee A"}], "title": "A paper", "volume": "96", "issue": "3", "pages": "",
          "pubtype": ["Journal Article"], "articleids": [{"idtype": "pubmed", "value": "35086793"}, {"idtype": "doi", "value": "10.1128/jvi.01234-21"}], "history": []}
ESEARCH = {"header": {"type": "esearch", "version": "0.3"},
           "esearchresult": {"count": "7", "retmax": "2", "retstart": "0", "idlist": ["35086793", "37391585"], "translationset": [],
                             "querytranslation": "\"AI135270\"[Grants and Funding] AND 2018/01/01:2025/12/31[Date - Publication]"}}
ESUMMARY = {"header": {"type": "esummary", "version": "0.3"},
            "result": {"uids": ["35086793", "37391585", "1"], "35086793": NO_PMC, "37391585": SUMMARY, "1": {"uid": "1", "error": "cannot get document summary"}}}
IDCONV_PMID = {"status": "ok", "request": {"idtype": "pmid"},
               "records": [{"doi": "10.1038/s41598-023-37437-x", "pmcid": "PMC10313714", "pmid": 37391585, "requested-id": "37391585"},
                           {"pmid": 99999999999, "requested-id": "99999999999", "status": "error", "errmsg": "Identifier not found in PMC"}]}
IDCONV_DOI = {"status": "ok", "records": [{"doi": "10.1093/nar/gks1195", "pmcid": "PMC3531190", "pmid": 23193287, "requested-id": "10.1093/nar/gks1195"}]}
IDCONV_PMCID = {"status": "ok", "records": [{"doi": "10.1093/nar/gks1195", "pmcid": "PMC3531190", "pmid": 23193287, "requested-id": "PMC3531190"}]}


def fake(calls):
    async def get_json(url, params=None, headers=None):
        calls.append((url, dict(params or {})))
        if url.endswith("esearch.fcgi"):
            return ESEARCH
        if url.endswith("esummary.fcgi"):
            return ESUMMARY
        return {"pmid": IDCONV_PMID, "doi": IDCONV_DOI, "pmcid": IDCONV_PMCID}[params["idtype"]]
    return get_json


def test_summary_slims_ids_authors_and_release():
    a = pm._slim_summary(SUMMARY)
    assert a["pmid"] == "37391585" and a["pmcid"] == "PMC10313714" and a["doi"] == "10.1038/s41598-023-37437-x"
    assert len(a["authors"]) == 10 and a["author_count"] == 16 and a["journal"] == "Sci Rep" and a["full_journal_name"] == "Scientific reports"
    assert a["volume"] == "13" and a["pages"] == "10625" and a["pmc_release_date"] == "2023-06-30" and a["link"] == "https://pubmed.ncbi.nlm.nih.gov/37391585/"
    b = pm._slim_summary(NO_PMC)
    assert b["pmcid"] is None and b["pages"] is None and b["pmc_release_date"] is None
    assert pm._slim_summary({"uid": "1", "error": "cannot get document summary"}) == {"pmid": "1", "error": "cannot get document summary"}


async def test_search_sends_dates_tool_and_email_then_summarises(monkeypatch):
    calls = []
    monkeypatch.setattr(pm, "get_json", fake(calls))
    monkeypatch.delenv(pm.KEY_ENV, raising=False)
    pm._cache._d.clear()
    out = await pm.pubmed_search("AI135270[Grant Number]", from_year="2018", retmax=500)
    url, p = calls[0]
    assert url.endswith("esearch.fcgi") and p["term"] == "AI135270[Grant Number]" and p["retmax"] == 50 and p["sort"] == "pub_date"
    assert p["datetype"] == "pdat" and p["mindate"] == "2018" and p["maxdate"] == "3000" and p["tool"] == "ai4ra-mcp"
    assert "api_key" not in p
    assert calls[1][0].endswith("esummary.fcgi") and calls[1][1]["id"] == "35086793,37391585"
    assert out["total"] == 7 and out["returned"] == 3 and out["next_retstart"] == 3 and out["query_translation"].startswith('"AI135270"')
    assert out["articles"][1]["pmcid"] == "PMC10313714" and out["articles"][0]["pmcid"] is None


async def test_key_is_sent_when_set_and_email_only_when_the_contact_is_one(monkeypatch):
    calls = []
    monkeypatch.setattr(pm, "get_json", fake(calls))
    monkeypatch.setenv(pm.KEY_ENV, "k123")
    monkeypatch.setattr(pm, "CONTACT", "https://github.com/ui-insight/ai4ra-mcp")
    pm._cache._d.clear()
    await pm.pubmed_summary("37391585, 35086793")
    assert calls[0][1]["api_key"] == "k123" and calls[0][1]["id"] == "37391585,35086793" and "email" not in calls[0][1]
    monkeypatch.setattr(pm, "CONTACT", "osp@uidaho.edu")
    pm._cache._d.clear()
    await pm.pubmed_summary("37391585")
    assert calls[1][1]["email"] == "osp@uidaho.edu"


async def test_id_convert_groups_by_type_and_counts(monkeypatch):
    calls = []
    monkeypatch.setattr(pm, "get_json", fake(calls))
    monkeypatch.delenv(pm.KEY_ENV, raising=False)
    pm._cache._d.clear()
    out = await pm.pmc_id_convert("37391585,99999999999 pmc3531190, 10.1093/nar/gks1195, junk")
    sent = {p["idtype"]: p["ids"] for _, p in calls}
    assert sent == {"pmid": "37391585,99999999999", "pmcid": "PMC3531190", "doi": "10.1093/nar/gks1195"}
    assert all(url == pm.IDCONV and p["format"] == "json" for url, p in calls)
    assert out["requested"] == 5 and out["with_pmcid"] == 3 and out["without_pmcid"] == ["junk", "99999999999"]
    assert out["summary"] == "3 of 5 have a PMCID; 2 do not."
    missing = [r for r in out["records"] if r["requested_id"] == "99999999999"][0]
    assert missing["errmsg"] == "Identifier not found in PMC" and missing["pmcid"] is None


async def test_bad_input():
    assert "error" in await pm.pubmed_search("")
    assert "YYYY" in (await pm.pubmed_search("x", from_year="Jan 2020"))["error"]
    assert "error" in await pm.pubmed_summary("PMC123")
    assert "error" in await pm.pubmed_summary(",".join(["1"] * 51))
    assert "error" in await pm.pmc_id_convert("")


async def test_lists_tools():
    assert {t.name for t in await pm.mcp.list_tools()} == {"pubmed_index", "pubmed_search", "pubmed_summary", "pmc_id_convert"}
