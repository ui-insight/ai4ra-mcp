"""clinicaltrials: the v2 study shapes slimmed, the search parameters, the NCT id check and bad input."""

from ai4ra_mcp.servers.clinicaltrials import server as ct

LISTED = {"protocolSection": {
    "identificationModule": {"nctId": "NCT05109923", "briefTitle": "Onnit Labs New Mood Supplementation in Healthy College Students",
                             "officialTitle": "The Effect of Onnit New Mood Supplementation in Healthy Collegiate Men and Women"},
    "statusModule": {"overallStatus": "COMPLETED", "startDateStruct": {"date": "2018-09-10"}, "primaryCompletionDateStruct": {"date": "2019-05-03"},
                     "completionDateStruct": {"date": "2019-08-02"}, "studyFirstSubmitDate": "2020-12-10"},
    "sponsorCollaboratorsModule": {"leadSponsor": {"name": "University of Idaho", "class": "OTHER"}, "collaborators": [{"name": "Idaho Army National Guard"}]},
    "conditionsModule": {"conditions": ["Mental Health Wellness 1"]},
    "designModule": {"studyType": "INTERVENTIONAL", "phases": ["NA"], "enrollmentInfo": {"count": 56}},
    "armsInterventionsModule": {"interventions": [{"type": "DIETARY_SUPPLEMENT", "name": "Multi-Ingredient Herbal Supplement"}, {"type": "DIETARY_SUPPLEMENT", "name": "Placebo Supplement"}]}},
    "hasResults": False}
SEARCH = {"totalCount": 27, "studies": [LISTED, {"protocolSection": {"identificationModule": {"nctId": "NCT07032636"}}, "hasResults": False}], "nextPageToken": "ZVNj7o2Elu8o3lpwWti8q"}
FULL = {"protocolSection": {
    "identificationModule": {"nctId": "NCT04818073", "orgStudyIdInfo": {"id": "476"},
                             "secondaryIdInfos": [{"id": "2R01HD062744-06", "type": "NIH", "link": "https://reporter.nih.gov/quickSearch/2R01HD062744-06"}],
                             "organization": {"fullName": "University of California, Irvine", "class": "OTHER"},
                             "briefTitle": "Determinants of the Effectiveness of Robot-assisted Hand Movement Training", "officialTitle": "Determinants of ..."},
    "statusModule": {"statusVerifiedDate": "2024-10", "overallStatus": "ACTIVE_NOT_RECRUITING", "startDateStruct": {"date": "2022-05-06", "type": "ACTUAL"},
                     "primaryCompletionDateStruct": {"date": "2025-05-31", "type": "ESTIMATED"}, "completionDateStruct": {"date": "2025-08-31", "type": "ESTIMATED"},
                     "studyFirstSubmitDate": "2021-03-23", "studyFirstPostDateStruct": {"date": "2021-03-26", "type": "ACTUAL"},
                     "resultsFirstSubmitDate": "2026-01-10", "resultsFirstPostDateStruct": {"date": "2026-02-01", "type": "ACTUAL"},
                     "lastUpdateSubmitDate": "2024-10-08", "lastUpdatePostDateStruct": {"date": "2024-10-15", "type": "ACTUAL"}},
    "sponsorCollaboratorsModule": {"responsibleParty": {"type": "PRINCIPAL_INVESTIGATOR", "investigatorFullName": "David Reinkensmeyer", "investigatorTitle": "Professor",
                                                        "investigatorAffiliation": "University of California, Irvine"},
                                   "leadSponsor": {"name": "University of California, Irvine", "class": "OTHER"},
                                   "collaborators": [{"name": "University of Idaho", "class": "OTHER"}, {"name": "Eunice Kennedy Shriver National Institute of Child Health and Human Development (NICHD)", "class": "NIH"}]},
    "oversightModule": {"oversightHasDmc": False, "isFdaRegulatedDrug": False, "isFdaRegulatedDevice": False, "isUsExport": False},
    "descriptionModule": {"briefSummary": "This study tests robot-assisted hand training."},
    "conditionsModule": {"conditions": ["Stroke"]},
    "designModule": {"studyType": "INTERVENTIONAL", "phases": ["NA"], "designInfo": {"allocation": "RANDOMIZED", "interventionModel": "PARALLEL", "primaryPurpose": "TREATMENT",
                                                                                   "maskingInfo": {"masking": "DOUBLE", "whoMasked": ["PARTICIPANT", "INVESTIGATOR"]}},
                     "enrollmentInfo": {"count": 120, "type": "ESTIMATED"}},
    "armsInterventionsModule": {"armGroups": [{"label": "Robot", "type": "EXPERIMENTAL", "description": "...", "interventionNames": ["Device: FINGER robot"]}],
                                "interventions": [{"type": "DEVICE", "name": "FINGER robot", "description": "..."}]},
    "eligibilityModule": {"eligibilityCriteria": "Inclusion Criteria:\n\n" + "x" * 2500, "healthyVolunteers": False, "sex": "ALL", "minimumAge": "18 Years", "maximumAge": "85 Years", "stdAges": ["ADULT", "OLDER_ADULT"]},
    "contactsLocationsModule": {"centralContacts": [{"name": "Study Coordinator", "role": "CONTACT", "phone": "949-000-0000", "email": "coord@uci.edu"}],
                                "overallOfficials": [{"name": "David Reinkensmeyer, Ph.D", "affiliation": "University of California, Irvine", "role": "PRINCIPAL_INVESTIGATOR"}],
                                "locations": [{"facility": f"Site {i}", "city": "Irvine", "state": "California", "zip": "92697", "country": "United States", "geoPoint": {"lat": 33.6, "lon": -117.8}} for i in range(12)]},
    "ipdSharingStatementModule": {"ipdSharing": "NO"}},
    "resultsSection": {"participantFlowModule": {}}, "hasResults": True}


def test_listed_study_slims():
    s = ct._slim_study(LISTED)
    assert s["nct_id"] == "NCT05109923" and s["status"] == "COMPLETED" and s["start_date"] == "2018-09-10" and s["primary_completion_date"] == "2019-05-03"
    assert s["first_submitted"] == "2020-12-10" and s["results_first_submitted"] is None and s["has_results"] is False
    assert s["lead_sponsor"] == "University of Idaho" and s["lead_sponsor_class"] == "OTHER" and s["collaborators"] == ["Idaho Army National Guard"]
    assert s["interventions"] == [{"type": "DIETARY_SUPPLEMENT", "name": "Multi-Ingredient Herbal Supplement"}, {"type": "DIETARY_SUPPLEMENT", "name": "Placebo Supplement"}]
    assert s["enrollment"] == 56 and s["phases"] == ["NA"] and s["link"] == "https://clinicaltrials.gov/study/NCT05109923"
    bare = ct._slim_study({"protocolSection": {"identificationModule": {"nctId": "NCT07032636"}}, "hasResults": False})
    assert bare["nct_id"] == "NCT07032636" and bare["collaborators"] == [] and bare["start_date"] is None


def test_full_study_slims_ids_dates_design_and_truncates():
    f = ct._slim_full(FULL)
    assert f["secondary_ids"] == [{"id": "2R01HD062744-06", "type": "NIH", "domain": None, "link": "https://reporter.nih.gov/quickSearch/2R01HD062744-06"}]
    assert f["org_study_id"] == "476" and f["organization"] == "University of California, Irvine"
    assert f["first_posted"] == "2021-03-26" and f["results_first_submitted"] == "2026-01-10" and f["results_first_posted"] == "2026-02-01"
    assert f["primary_completion_date_type"] == "ESTIMATED" and f["start_date_type"] == "ACTUAL"
    assert f["responsible_party"] == {"type": "PRINCIPAL_INVESTIGATOR", "investigator": "David Reinkensmeyer", "affiliation": "University of California, Irvine"}
    assert f["collaborators"][0] == "University of Idaho" and f["design"]["allocation"] == "RANDOMIZED" and f["design"]["masking"] == "DOUBLE"
    assert f["arms"] == [{"label": "Robot", "type": "EXPERIMENTAL", "interventions": ["Device: FINGER robot"]}]
    assert f["eligibility"]["sex"] == "ALL" and f["eligibility"]["minimum_age"] == "18 Years" and len(f["eligibility"]["criteria"]) == 2003 and f["eligibility"]["criteria"].endswith("...")
    assert f["locations_count"] == 12 and len(f["locations"]) == 10 and f["locations"][0] == {"facility": "Site 0", "city": "Irvine", "state": "California", "country": "United States"}
    assert f["central_contacts"] == [{"name": "Study Coordinator", "role": "CONTACT", "phone": "949-000-0000", "email": "coord@uci.edu"}]
    assert f["oversight"] == {"fda_regulated_drug": False, "fda_regulated_device": False, "has_dmc": False}
    assert f["ipd_sharing"] == {"statement": "NO", "description": None} and f["has_results"] is True and f["results_section_present"] is True


async def test_search_sends_v2_params(monkeypatch):
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen["url"], seen["params"] = url, dict(params or {})
        return SEARCH

    monkeypatch.setattr(ct, "get_json", fake_get_json)
    ct._cache._d.clear()
    out = await ct.clinicaltrials_search(condition="asthma", sponsor="University of Idaho", status="recruiting, Completed", page_size=500, page_token="abc")
    assert seen["url"] == "https://clinicaltrials.gov/api/v2/studies"
    assert seen["params"] == {"pageSize": 50, "countTotal": "true", "fields": ct.FIELDS, "query.cond": "asthma", "query.spons": "University of Idaho",
                              "filter.overallStatus": "RECRUITING,COMPLETED", "pageToken": "abc"}
    assert out["total"] == 27 and out["returned"] == 2 and out["next_page_token"] == "ZVNj7o2Elu8o3lpwWti8q" and out["studies"][0]["nct_id"] == "NCT05109923"


async def test_study_fetches_by_nct_id(monkeypatch):
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen["url"] = url
        return FULL

    monkeypatch.setattr(ct, "get_json", fake_get_json)
    ct._cache._d.clear()
    out = await ct.clinicaltrials_study(" nct04818073 ")
    assert seen["url"] == "https://clinicaltrials.gov/api/v2/studies/NCT04818073" and out["nct_id"] == "NCT04818073"


async def test_bad_input():
    assert "error" in await ct.clinicaltrials_search()
    assert "error" in await ct.clinicaltrials_search(status="RECRUITING")
    assert "unknown status BOGUS" in (await ct.clinicaltrials_search(condition="asthma", status="BOGUS"))["error"]
    assert "eight digits" in (await ct.clinicaltrials_study("NCT123"))["error"]
    assert "error" in await ct.clinicaltrials_study("")


async def test_lists_tools():
    assert {t.name for t in await ct.mcp.list_tools()} == {"clinicaltrials_index", "clinicaltrials_search", "clinicaltrials_study"}
