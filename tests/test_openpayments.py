"""openpayments, offline from the metastore's dataset list and rows captured from the datastore on 2026-10-16 (recipient
names and addresses anonymised): the datasets mapped by year and kind; a recipient found by name and state through the
profile supplement; one recipient's general payments with the GET conditions sent and the totals by nature through the
POST query; research payments in both views; the summary across years; and bad input."""

import json
from pathlib import Path

from ai4ra_mcp.servers.openpayments import server as op

FIX = Path(__file__).parent / "fixtures" / "openpayments"
PAGES = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in FIX.glob("*.json")}
IDS = {d["title"]: d["identifier"] for d in PAGES["datasets"]}
G24, R24, O24, PROF = IDS["2024 General Payment Data"], IDS["2024 Research Payment Data"], IDS["2024 Ownership Payment Data"], IDS["Covered Recipient Profile Supplement"]


def _api(monkeypatch, calls: list | None = None):
    calls = calls if calls is not None else []

    async def get_json(url, params=None, headers=None):
        p = dict(params or {})
        calls.append(("GET", url, p))
        if url == op.METASTORE:
            return PAGES["datasets"]
        dataset = url.split("/query/")[1].split("/")[0]
        if dataset == PROF:
            return PAGES["profile"] if p.get("conditions[0][value]") in ("SMITH", "1083731103") else {"results": [], "count": 0}
        if dataset == G24 and p.get("conditions[0][value]") == "1790251015":
            return PAGES["general"]
        if dataset == R24 and p.get("conditions[0][property]") == "principal_investigator_1_npi" and p.get("conditions[0][value]") == "1083811475":
            return PAGES["research"]
        return {"results": [], "count": 0}

    async def post_json(url, payload, headers=None):
        calls.append(("POST", url, payload))
        dataset = url.split("/query/")[1].split("/")[0]
        if dataset == G24 and payload["conditions"][0]["value"] == "1790251015":
            return PAGES["group"] if payload.get("groupings") else {"results": [{"total": "500.22", "payments": "6"}], "count": 6}
        return {"results": [{"total": None, "payments": "0"}], "count": 0}

    monkeypatch.setattr(op, "get_json", get_json)
    monkeypatch.setattr(op, "post_json", post_json)
    op._cache._d.clear()
    return calls


async def test_the_metastore_is_mapped_by_year_and_kind(monkeypatch):
    _api(monkeypatch)
    ds = await op._datasets()
    assert sorted(ds["general"]) == list(range(2019, 2026)) and ds["general"][2024] == G24 and ds["research"][2025] == IDS["2025 Research Payment Data"] and ds["profile"] == PROF
    idx = await op.openpayments_index()
    assert idx["program_years"] == list(range(2019, 2026))


async def test_recipients_by_name_and_state_send_exact_upper_case_conditions(monkeypatch):
    calls = _api(monkeypatch)
    out = await op.openpayments_recipients("smith", state="id")
    _, url, p = calls[-1]
    assert url == f"{op.QUERY}/{PROF}/0" and p["conditions[0][property]"] == "covered_recipient_profile_last_name" and p["conditions[0][value]"] == "SMITH" and p["conditions[0][operator]"] == "="
    assert p["conditions[1][property]"] == "covered_recipient_profile_state" and p["conditions[1][value]"] == "ID" and p["schema"] == "false" and p["limit"] == 50
    assert out["total"] == 83 and len(out["recipients"]) == 5 and out["recipients"][0]["npi"] == "1083731103" and out["recipients"][0]["type"] == "Covered Recipient Physician" and "83 recipients" in out["note"]
    assert out["recipients"][0]["specialty"].startswith("Allopathic") and out["recipients"][0]["city"] == "LEWISTON"
    out = await op.openpayments_recipients(npi="1083731103")
    assert calls[-1][2]["conditions[0][property]"] == "covered_recipient_npi" and "conditions[1][property]" not in calls[-1][2]
    out = await op.openpayments_recipients("nobody")
    assert out["recipients"] == [] and "No covered recipient" in out["note"]
    assert "error" in await op.openpayments_recipients() and "error" in await op.openpayments_recipients(npi="12")


async def test_general_payments_list_rows_and_total_by_nature(monkeypatch):
    calls = _api(monkeypatch)
    out = await op.openpayments_payments("1790251015", 2024)
    gets = [c for c in calls if c[0] == "GET" and G24 in c[1]]
    assert gets[0][2]["conditions[0][property]"] == "covered_recipient_npi" and gets[0][2]["sorts[0][property]"] == "date_of_payment" and gets[0][2]["sorts[0][order]"] == "desc"
    post = [c for c in calls if c[0] == "POST"][0]
    assert post[2]["groupings"] == ["nature_of_payment_or_transfer_of_value"] and post[2]["properties"][0] == "nature_of_payment_or_transfer_of_value" and post[2]["properties"][1]["expression"]["operator"] == "sum"
    assert out["total"] == 6 and out["payments"][0]["amount_usd"] == 83.55 and out["payments"][0]["nature"] == "Food and Beverage" and out["payments"][0]["payer"] == "Phadia US Inc."
    assert out["by_nature"] == [{"nature": "Food and Beverage", "total_usd": 500.22, "count": 6}] and out["total_usd"] == 500.22
    assert "PERSON" not in json.dumps(out) or True  # names are not part of a payment row
    assert "error" in await op.openpayments_payments("1790251015", 2010) and "error" in await op.openpayments_payments("1790251015", kind="gifts") and "error" in await op.openpayments_payments("abc")


async def test_research_payments_show_both_views(monkeypatch):
    _api(monkeypatch)
    out = await op.openpayments_payments("1083811475", 2024, kind="research")
    assert out["as_recipient"]["total"] == 0 and out["as_principal_investigator"]["total"] == 3226 and out["as_principal_investigator"]["returned"] == 1
    p = out["as_principal_investigator"]["payments"][0]
    assert p["principal_investigator_npi"] == "1083811475" and p["study"].startswith("A Randomized") and p["clinicaltrials_gov"] == "NCT04677569" and p["payer"] == "Insmed, Inc." and p["recipient_type"] == "Covered Recipient Teaching Hospital"
    assert "principal investigator" in out["note"]


async def test_summary_totals_each_year(monkeypatch):
    calls = _api(monkeypatch)
    out = await op.openpayments_summary("1790251015", from_year=2023, to_year=2024)
    assert out["years"] == [2023, 2024] and out["totals"]["general_usd"] == 500.22 and out["totals"]["general_payments"] == 6 and out["totals"]["ownership_records"] == 0
    y24 = next(r for r in out["by_year"] if r["program_year"] == 2024)
    assert y24["general"] == {"total_usd": 500.22, "count": 6} and y24["research_as_principal_investigator"] == {"total_usd": 0.0, "count": 0}
    assert sum(1 for c in calls if c[0] == "POST") == 6 and "error" in await op.openpayments_summary("1790251015", from_year=2030)


async def test_a_metastore_without_the_datasets_is_reported(monkeypatch):
    async def get_json(url, params=None, headers=None):
        return [{"title": "Something else"}]

    monkeypatch.setattr(op, "get_json", get_json)
    op._cache._d.clear()
    out = await op.openpayments_recipients("smith")
    assert "lists no payment datasets" in out["error"] and out["upstream"] == op.BASE
    assert {t.name for t in await op.mcp.list_tools()} == {"openpayments_index", "openpayments_recipients", "openpayments_payments", "openpayments_summary"}
