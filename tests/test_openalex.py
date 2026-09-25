"""openalex: the API's shapes slimmed, the filter string each search builds, and the abstract put back together."""

from ai4ra_mcp.servers.openalex import server as oa

WORK = {"id": "https://openalex.org/W4410975945", "doi": "https://doi.org/10.1093/treephys/tpaf063",
        "title": "Unveiling the integration of above- and below-ground tree carbon-hydraulic traits in Amazonian trees across hydrological niches",
        "publication_year": 2025, "publication_date": "2025-06-02", "type": "article",
        "primary_location": {"is_oa": False, "landing_page_url": "https://doi.org/10.1093/treephys/tpaf063", "source": {"id": "https://openalex.org/S82119156", "display_name": "Tree Physiology"}},
        "open_access": {"is_oa": False, "oa_status": "closed", "oa_url": None},
        "authorships": [{"author_position": "first", "author": {"id": "https://openalex.org/A5089694286", "display_name": "Jason Cham", "orcid": "https://orcid.org/0000-0002-4748-3930"},
                         "institutions": [{"id": "https://openalex.org/I123431417", "display_name": "Scripps Research Institute", "ror": "https://ror.org/02dxx6824"}]},
                        {"author_position": "last", "author": {"id": "https://openalex.org/A5000000001", "display_name": "Another Author", "orcid": None}, "institutions": []}],
        "awards": [{"id": "https://openalex.org/G5081972703", "display_name": "Collaborative Research: Are Amazon forest trees source or sink limited?", "funder_award_id": "1754803",
                    "funder_id": "https://openalex.org/F4320306076", "funder_display_name": "National Science Foundation"}],
        "funders": [{"id": "https://openalex.org/F4320306076", "display_name": "National Science Foundation", "ror": "https://ror.org/021nxhr62"},
                    {"id": "https://openalex.org/F4320332299", "display_name": "National Institute of Food and Agriculture", "ror": "https://ror.org/05qx3fv49"}],
        "cited_by_count": 3, "biblio": {"volume": "45", "issue": "6", "first_page": "tpaf063", "last_page": "tpaf063"}, "referenced_works_count": 88,
        "abstract_inverted_index": {"AIM:": [0], "Healthcare": [1, 4], "workers": [2], "(HCWs)": [3], "were": [5]}}
AUTHOR = {"id": "https://openalex.org/A5052350543", "display_name": "Luke Sheneman", "orcid": "https://orcid.org/0000-0001-8781-2041", "works_count": 27, "cited_by_count": 471,
          "last_known_institutions": [{"id": "https://openalex.org/I155093810", "ror": "https://ror.org/03hbp5t65", "display_name": "University of Idaho", "country_code": "US", "type": "education"}],
          "topics": [{"id": "https://openalex.org/T10015", "display_name": "Genomics and Phylogenetic Studies", "count": 7}, {"id": "https://openalex.org/T10540", "display_name": "Advanced Fluorescence Microscopy Techniques", "count": 5},
                     {"id": "https://openalex.org/T1", "display_name": "Third", "count": 1}, {"id": "https://openalex.org/T2", "display_name": "Fourth", "count": 1}]}
INSTITUTION = {"id": "https://openalex.org/I155093810", "display_name": "University of Idaho", "ror": "https://ror.org/03hbp5t65", "country_code": "US", "type": "education",
               "works_count": 48635, "homepage_url": "https://uidaho.edu", "cited_by_count": 2179951}
FUNDER = {"id": "https://openalex.org/F4320306076", "display_name": "National Science Foundation", "country_code": "US", "awards_count": 12345, "works_count": 1882510,
          "ids": {"openalex": "https://openalex.org/F4320306076", "ror": "https://ror.org/021nxhr62", "wikidata": "https://www.wikidata.org/entity/Q304878", "crossref": "100000001", "doi": "10.13039/100000001"},
          "homepage_url": "https://www.nsf.gov"}


def test_slim_work_carries_grants_authors_and_doi_link():
    w = oa.slim_work(WORK)
    assert w["doi"] == "https://doi.org/10.1093/treephys/tpaf063" and w["year"] == 2025 and w["source"] == "Tree Physiology" and w["pages"] == "tpaf063-tpaf063"
    assert w["grants"] == [{"funder": "National Science Foundation", "funder_id": "https://openalex.org/F4320306076", "award_id": "1754803"}]
    assert w["funders"] == ["National Science Foundation", "National Institute of Food and Agriculture"]
    assert w["authors"][0]["orcid"] == "https://orcid.org/0000-0002-4748-3930" and w["authors"][0]["institutions"] == ["Scripps Research Institute"] and w["author_count"] == 2
    assert w["open_access"]["status"] == "closed" and w["link"] == "https://doi.org/10.1093/treephys/tpaf063"


def test_abstract_is_rebuilt_from_the_inverted_index():
    assert oa.abstract_from_inverted_index(WORK["abstract_inverted_index"]) == "AIM: Healthcare workers (HCWs) Healthcare were"
    assert oa.abstract_from_inverted_index(None) is None and oa.abstract_from_inverted_index({}) is None


def test_slim_author_institution_funder():
    a = oa.slim_author(AUTHOR)
    assert a["orcid"].endswith("8781-2041") and a["last_known_institutions"] == [{"name": "University of Idaho", "id": "https://openalex.org/I155093810"}]
    assert a["topics"] == ["Genomics and Phylogenetic Studies", "Advanced Fluorescence Microscopy Techniques", "Third"] and a["link"] == AUTHOR["id"]
    i = oa.slim_institution(INSTITUTION)
    assert i["ror"] == "https://ror.org/03hbp5t65" and i["type"] == "education" and i["homepage"] == "https://uidaho.edu"
    f = oa.slim_funder(FUNDER)
    assert f["ids"] == {"ror": "https://ror.org/021nxhr62", "crossref": "100000001", "doi": "10.13039/100000001"} and f["grants_count"] == 12345


def test_ids_accept_url_or_bare_form():
    assert oa._bare("https://openalex.org/W4224016882", "W") == "W4224016882" and oa._bare("w4224016882", "W") == "W4224016882" and oa._bare("A1", "W") == ""
    assert oa._doi("https://doi.org/10.1371/journal.pone.0266781") == "10.1371/journal.pone.0266781" and oa._doi("doi:10.1000/x") == "10.1000/x" and oa._doi("W1") == ""


async def test_works_search_builds_the_filter(monkeypatch):
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen["url"] = url
        seen.update(params or {})
        return {"meta": {"count": 60, "page": 1, "per_page": 25}, "results": [WORK] * 25}

    monkeypatch.setattr(oa, "get_json", fake_get_json)
    oa._cache._d.clear()
    out = await oa.openalex_works_search(search="wildfire smoke", author_id="https://openalex.org/A5052350543", institution_id="https://ror.org/03hbp5t65",
                                         funder_id="F4320306076", award_id="DEB-1754803", from_year="2020", to_year="2024", type="Article")
    assert seen["url"].endswith("/works") and seen["search"] == "wildfire smoke" and seen["mailto"] and seen["sort"] == "publication_date:desc"
    assert seen["filter"] == ("authorships.author.id:A5052350543,authorships.institutions.ror:https://ror.org/03hbp5t65,funders.id:F4320306076,"
                              "awards.funder_award_id:DEB-1754803|1754803,from_publication_date:2020-01-01,to_publication_date:2024-12-31,type:article")
    assert "grants" not in seen["select"] and "awards" in seen["select"]
    assert out["returned"] == 25 and out["total"] == 60 and out["next_page"] == 2
    oa._cache._d.clear()
    seen.clear()
    await oa.openalex_works_search(institution_id="I155093810")
    assert seen["filter"] == "authorships.institutions.id:I155093810" and "search" not in seen


async def test_work_by_doi_or_id_and_bad_input(monkeypatch):
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen["url"] = url
        return WORK

    monkeypatch.setattr(oa, "get_json", fake_get_json)
    oa._cache._d.clear()
    out = await oa.openalex_work("https://doi.org/10.1093/treephys/tpaf063")
    assert seen["url"].endswith("/works/doi:10.1093/treephys/tpaf063") and out["abstract"].startswith("AIM:") and out["referenced_works_count"] == 88
    await oa.openalex_work("W4410975945")
    assert seen["url"].endswith("/works/W4410975945")
    assert "error" in await oa.openalex_work("not-an-id")
    assert "error" in await oa.openalex_works_search(from_year="2020")
    assert "error" in await oa.openalex_works_search(author_id="I155093810")
    assert "error" in await oa.openalex_authors_search("")


async def test_authors_search_filters_by_institution(monkeypatch):
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen.update(params or {})
        return {"meta": {"count": 1}, "results": [AUTHOR]}

    monkeypatch.setattr(oa, "get_json", fake_get_json)
    oa._cache._d.clear()
    out = await oa.openalex_authors_search("Sheneman", institution_id="I155093810")
    assert seen["filter"] == "last_known_institutions.id:I155093810" and out["authors"][0]["display_name"] == "Luke Sheneman" and "next_page" not in out
    oa._cache._d.clear()
    await oa.openalex_authors_search("Sheneman", institution_id="https://ror.org/03hbp5t65")
    assert seen["filter"] == "affiliations.institution.ror:https://ror.org/03hbp5t65"


async def test_lists_tools():
    assert {t.name for t in await oa.mcp.list_tools()} == {"openalex_index", "openalex_works_search", "openalex_work", "openalex_authors_search",
                                                            "openalex_institutions_search", "openalex_funders_search"}
