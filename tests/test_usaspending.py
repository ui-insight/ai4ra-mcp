"""usaspending: the API's shapes slimmed to what a research administrator needs."""

from ai4ra_mcp.servers.usaspending import server as u

PROFILE = {"name": "CANISIUS UNIVERSITY OF BUFFALO NEW YORK", "alternate_names": ["CANISIUS COLLEGE", "CANISIUS COLLEGE OF BUFFALO"], "uei": "JJWLQMLKBB85",
           "duns": "071486583", "recipient_level": "R", "parent_name": None, "parent_uei": None, "recipient_id": "0ed88279-4fcd-844b-d300-2cc124187429-R",
           "location": {"address_line1": "2001 MAIN ST", "city_name": "BUFFALO", "state_code": "NY", "zip": "14208", "country_code": "USA"},
           "business_types": ["higher_education"], "total_transactions": 46, "total_transaction_amount": 3230276.04}
AWARD_ROW = {"Award ID": "P425F200507", "Recipient Name": "CANISIUS UNIVERSITY OF BUFFALO NEW YORK", "Recipient UEI": "JJWLQMLKBB85", "Award Amount": 6553361.0,
             "Total Outlays": 6553361.0, "Start Date": "2020-05-04", "End Date": "2022-01-16", "Awarding Agency": "Department of Education",
             "Awarding Sub Agency": "Department of Education", "Description": "CARES ACT", "CFDA Number": "84.425", "generated_internal_id": "ASST_NON_P425F200507_091"}
SUB_ROW = {"Sub-Award ID": "SP00013993-02", "Sub-Awardee Name": "CANISIUS UNIVERSITY OF BUFFALO NEW YORK", "Sub-Award Amount": 70301.0, "Sub-Award Date": "2019-09-01",
           "Sub-Award Description": "YEARS 1-2 WORKSCOPES", "Sub-Award Type": "sub-grant", "Prime Award ID": "R01HD...", "Prime Recipient Name": "UNIVERSITY AT BUFFALO",
           "Awarding Agency": "Department of Health and Human Services", "Awarding Sub Agency": "NIH", "prime_award_generated_internal_id": "ASST_NON_R01HD_075"}
RECORD = {"generated_unique_award_id": "ASST_NON_P425F200507_091", "fain": "P425F200507", "type_description": "FORMULA GRANT (A)", "category": "grant",
          "description": "CARES ACT", "total_obligation": 6553361.0, "total_outlay": 6553361.0, "date_signed": "2020-05-04",
          "period_of_performance": {"start_date": "2020-05-04", "end_date": "2022-01-16"},
          "recipient": {"recipient_name": "CANISIUS UNIVERSITY OF BUFFALO NEW YORK", "recipient_uei": "JJWLQMLKBB85", "parent_recipient_name": None},
          "awarding_agency": {"toptier_agency": {"name": "Department of Education"}, "subtier_agency": {"name": "Department of Education"}},
          "funding_agency": {"toptier_agency": {"name": "Department of Education"}},
          "cfda_info": [{"cfda_number": "84.425", "cfda_title": "Education Stabilization Fund"}], "subaward_count": 0, "total_subaward_amount": None}


def test_profile_carries_former_names_and_link():
    p = u._slim_profile(PROFILE)
    assert p["former_names"] == ["CANISIUS COLLEGE", "CANISIUS COLLEGE OF BUFFALO"] and p["uei"] == "JJWLQMLKBB85" and p["parent"] is None
    assert p["link"].endswith("/recipient/0ed88279-4fcd-844b-d300-2cc124187429-R/latest")


def test_award_and_subaward_rows_slim_with_links():
    a = u._slim_award(AWARD_ROW)
    assert a["amount"] == 6553361.0 and a["assistance_listing"] == "84.425" and a["link"].endswith("/award/ASST_NON_P425F200507_091")
    s = u._slim_subaward(SUB_ROW)
    assert s["prime_recipient"] == "UNIVERSITY AT BUFFALO" and s["prime_award_link"].endswith("/award/ASST_NON_R01HD_075")


def test_record_slims():
    r = u._slim_record(RECORD)
    assert r["award_id"] == "P425F200507" and r["period_of_performance"]["end"] == "2022-01-16"
    assert r["assistance_listings"] == [{"number": "84.425", "title": "Education Stabilization Fund"}] and r["awarding_agency"] == "Department of Education"


async def test_search_validates():
    assert "error" in await u.usaspending_awards_search("", "grants")
    assert "error" in await u.usaspending_subawards_search("x", "everything")
    assert "error" in await u.usaspending_recipient("")


def test_window_is_federal_fiscal_years():
    w = u._window(10)
    assert w["start_date"].endswith("-10-01") and w["end_date"].endswith("-09-30")
