"""pubmed: esummary, efetch and idconv shapes slimmed, the esearch parameters, the optional key, and bad input."""

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
    assert {t.name for t in await pm.mcp.list_tools()} == {"pubmed_index", "pubmed_search", "pubmed_summary", "pubmed_article", "pmc_id_convert"}


EFETCH = """<?xml version="1.0" ?>
<PubmedArticleSet>
<PubmedArticle>
  <MedlineCitation Status="MEDLINE" Owner="NLM">
    <PMID Version="1">37391585</PMID>
    <Article PubModel="Electronic">
      <Journal><ISOAbbreviation>Sci Rep</ISOAbbreviation><Title>Scientific reports</Title>
        <JournalIssue CitedMedium="Internet"><Volume>13</Volume><Issue>1</Issue><PubDate><Year>2023</Year><Month>Jun</Month><Day>30</Day></PubDate></JournalIssue></Journal>
      <ArticleTitle>Molecular cloning of interferon (IFN)-&#x3c9; of forest <i>musk</i> deer.</ArticleTitle>
      <Pagination><MedlinePgn>10625</MedlinePgn></Pagination>
      <Abstract><AbstractText Label="BACKGROUND">Forest musk deer are threatened.</AbstractText><AbstractText Label="RESULTS">Five sequences were cloned.</AbstractText></Abstract>
      <AuthorList CompleteYN="Y">
        <Author ValidYN="Y"><LastName>Chen</LastName><ForeName>Jia</ForeName><Initials>J</Initials>
          <Identifier Source="ORCID">0000-0001-0000-0001</Identifier>
          <AffiliationInfo><Affiliation>College of Veterinary Medicine, Sichuan Agricultural University, Chengdu, China.</Affiliation></AffiliationInfo></Author>
        <Author ValidYN="Y"><CollectiveName>The Deer Consortium</CollectiveName></Author>
      </AuthorList>
      <GrantList CompleteYN="Y">
        <Grant><GrantID>R01 AI135270</GrantID><Acronym>AI</Acronym><Agency>NIAID NIH HHS</Agency><Country>United States</Country></Grant>
        <Grant><GrantID>2021YFD1800</GrantID><Agency>National Key Research and Development Program of China</Agency><Country>China</Country></Grant>
      </GrantList>
      <PublicationTypeList><PublicationType UI="D016428">Journal Article</PublicationType><PublicationType UI="D013485">Research Support, Non-U.S. Gov't</PublicationType></PublicationTypeList>
    </Article>
    <MeshHeadingList>
      <MeshHeading><DescriptorName UI="D000818" MajorTopicYN="N">Animals</DescriptorName></MeshHeading>
      <MeshHeading><DescriptorName UI="D007372" MajorTopicYN="N">Interferons</DescriptorName><QualifierName UI="Q000235" MajorTopicYN="Y">genetics</QualifierName></MeshHeading>
    </MeshHeadingList>
    <KeywordList Owner="NOTNLM"><Keyword MajorTopicYN="N">musk deer</Keyword></KeywordList>
  </MedlineCitation>
  <PubmedData><ArticleIdList><ArticleId IdType="pubmed">37391585</ArticleId><ArticleId IdType="pmc">PMC10313714</ArticleId><ArticleId IdType="doi">10.1038/s41598-023-37437-x</ArticleId></ArticleIdList></PubmedData>
</PubmedArticle>
<PubmedArticle>
  <MedlineCitation Status="In-Process" Owner="NLM">
    <PMID Version="1">35086793</PMID>
    <Article PubModel="Print"><Journal><ISOAbbreviation>J Virol</ISOAbbreviation><Title>Journal of virology</Title><JournalIssue><Volume>96</Volume><PubDate><Year>2022</Year><Month>Jan</Month></PubDate></JournalIssue></Journal>
      <ArticleTitle>A paper</ArticleTitle><AuthorList><Author><LastName>Lee</LastName><Initials>A</Initials></Author></AuthorList></Article>
  </MedlineCitation>
  <PubmedData><ArticleIdList><ArticleId IdType="pubmed">35086793</ArticleId><ArticleId IdType="doi">10.1128/jvi.01234-21</ArticleId></ArticleIdList></PubmedData>
</PubmedArticle>
</PubmedArticleSet>"""


def test_article_is_read_for_grants_mesh_abstract_and_ids():
    a, b = pm.parse_articles(EFETCH)
    assert a["pmid"] == "37391585" and a["title"] == "Molecular cloning of interferon (IFN)-ω of forest musk deer." and a["doi"] == "10.1038/s41598-023-37437-x" and a["pmcid"] == "PMC10313714"
    assert a["abstract"] == "BACKGROUND: Forest musk deer are threatened. RESULTS: Five sequences were cloned."
    assert a["authors"] == [{"name": "Chen J", "affiliation": "College of Veterinary Medicine, Sichuan Agricultural University, Chengdu, China.", "orcid": "0000-0001-0000-0001"},
                            {"name": "The Deer Consortium", "affiliation": None, "orcid": None}] and a["author_count"] == 2
    assert a["grants"] == [{"grant_id": "R01 AI135270", "acronym": "AI", "agency": "NIAID NIH HHS", "country": "United States"},
                           {"grant_id": "2021YFD1800", "acronym": None, "agency": "National Key Research and Development Program of China", "country": "China"}] and a["grants_listed"]
    assert a["mesh"] == [{"term": "Animals", "major": False, "qualifiers": []}, {"term": "Interferons", "major": True, "qualifiers": ["genetics"]}]
    assert a["keywords"] == ["musk deer"] and a["publication_types"][0] == "Journal Article" and a["pubdate"] == "2023 Jun 30" and a["journal"] == "Sci Rep" and a["pages"] == "10625"
    assert b["pmid"] == "35086793" and b["abstract"] is None and b["grants"] == [] and b["grants_listed"] is False and b["mesh"] == [] and b["pmcid"] is None and b["pubdate"] == "2022 Jan"


async def test_article_fetches_xml_with_the_shared_parameters_and_says_what_was_not_found(monkeypatch):
    calls = []

    async def get_text(url, params=None, headers=None):
        calls.append((url, dict(params or {})))
        return EFETCH

    monkeypatch.setattr(pm, "get_text", get_text)
    monkeypatch.setenv(pm.KEY_ENV, "k123")
    pm._cache._d.clear()
    out = await pm.pubmed_article("37391585, 35086793,1")
    url, p = calls[0]
    assert url.endswith("efetch.fcgi") and p["db"] == "pubmed" and p["id"] == "37391585,35086793,1" and p["retmode"] == "xml" and p["tool"] == "ai4ra-mcp" and p["api_key"] == "k123"
    assert out["requested"] == 3 and out["returned"] == 2 and out["not_found"] == ["1"] and out["articles"][0]["grants"][0]["grant_id"] == "R01 AI135270"
    assert "k123" not in repr(list(pm._cache._d.keys()))
    assert "error" in await pm.pubmed_article("x")
    assert "error" in await pm.pubmed_article(",".join(["1"] * 21))

    async def not_xml(url, params=None, headers=None):
        return "<html>down</html>"

    monkeypatch.setattr(pm, "get_text", not_xml)
    pm._cache._d.clear()
    out = await pm.pubmed_article("37391585")
    assert out == {"requested": 1, "returned": 0, "articles": [], "not_found": ["37391585"]}
