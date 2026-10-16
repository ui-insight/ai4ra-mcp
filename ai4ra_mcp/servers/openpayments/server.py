"""openpayments: CMS Open Payments, the payments drug and device companies report making to physicians, other practitioners and teaching hospitals.

Upstream: https://openpaymentsdata.cms.gov/api/1/ (DKAN; no key). The metastore lists one dataset per program year and
kind (General Payment Data, Research Payment Data, Ownership Payment Data, 2019 to 2025) and the Covered Recipient
Profile Supplement; the datastore answers a GET /datastore/query/<dataset>/0 with conditions (property, value, operator
=, like, in ...), limit, offset, sorts and properties, and a POST with the same as JSON plus expressions (sum, count)
and groupings. Conditions are exact and the names are stored upper-case. A query by NPI is indexed and quick; a query by
name takes a few seconds. The data is what manufacturers and group purchasing organisations reported under the Sunshine
Act, published each June for the prior year and refreshed in January; a recipient may dispute a record and the dispute
status rides with it. This is the public record a conflict-of-interest review checks a clinical investigator against.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_json, post_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://openpaymentsdata.cms.gov/api/1"
METASTORE = f"{BASE}/metastore/schemas/dataset/items"
QUERY = f"{BASE}/datastore/query"
SITE = "https://openpaymentsdata.cms.gov/"
KINDS = ("general", "research", "ownership")
ROWS, MAX_ROWS = 50, 500
_TITLE = re.compile(r"^(\d{4}) (General|Research|Ownership) Payment Data$")
PROFILE_TITLE = "Covered Recipient Profile Supplement"
_cache = TTLCache()

mcp = MCPServer(
    "openpayments",
    instructions="CMS Open Payments: a physician or practitioner found by name (openpayments_recipients), the payments companies reported to them in a program year (openpayments_payments), and their totals across years (openpayments_summary). No key. Read openpayments_index first.",
)


async def _datasets() -> dict:
    """{'general': {year: id}, 'research': {...}, 'ownership': {...}, 'profile': id} from the metastore, cached a day."""
    async def make():
        items = await get_json(METASTORE)
        if not isinstance(items, list):
            raise ValueError("the Open Payments metastore did not return its dataset list")
        out: dict = {k: {} for k in KINDS}
        for it in items:
            title = (it.get("title") or "").strip()
            m = _TITLE.match(title)
            if m:
                out[m.group(2).lower()][int(m.group(1))] = it.get("identifier")
            elif title == PROFILE_TITLE:
                out["profile"] = it.get("identifier")
        if not out["general"] or "profile" not in out:
            raise ValueError("the Open Payments metastore lists no payment datasets by year (the site changed)")
        return out
    return await _cache.remember("datasets", DAY, make)


def _conditions(conds: list[tuple[str, str, str]]) -> dict:
    params: dict = {}
    for i, (prop, value, op) in enumerate(conds):
        params[f"conditions[{i}][property]"] = prop
        params[f"conditions[{i}][value]"] = value
        params[f"conditions[{i}][operator]"] = op
    return params


async def _rows(dataset: str, conds: list[tuple[str, str, str]], limit: int, sort: str | None = None, ttl: float = HOUR) -> dict:
    params = {**_conditions(conds), "limit": limit, "schema": "false"}
    if sort:
        params["sorts[0][property]"], params["sorts[0][order]"] = sort, "desc"
    key = f"rows:{dataset}:{repr(sorted(params.items()))}"
    body = await _cache.remember(key, ttl, lambda: get_json(f"{QUERY}/{dataset}/0", params))
    if not isinstance(body, dict) or not isinstance(body.get("results"), list):
        raise ValueError("the Open Payments datastore did not return its results")
    return body


async def _totals(dataset: str, conds: list[tuple[str, str, str]], group_by: str | None = None) -> list[dict]:
    """total_usd and count of the matching payments, by one column when group_by is given, through the datastore's POST query."""
    payload: dict = {"conditions": [{"property": p, "value": v, "operator": o} for p, v, o in conds],
                     "properties": [{"expression": {"operator": "sum", "operands": ["total_amount_of_payment_usdollars"]}, "alias": "total"},
                                    {"expression": {"operator": "count", "operands": ["record_id"]}, "alias": "payments"}],
                     "limit": 100, "schema": False}
    if group_by:
        payload["properties"].insert(0, group_by)
        payload["groupings"] = [group_by]
    key = f"totals:{dataset}:{repr(payload)}"
    body = await _cache.remember(key, HOUR, lambda: post_json(f"{QUERY}/{dataset}/0", payload))
    if not isinstance(body, dict) or not isinstance(body.get("results"), list):
        raise ValueError("the Open Payments datastore did not return its totals")
    rows = []
    for r in body["results"]:
        row = {"total_usd": round(float(r.get("total") or 0), 2), "count": int(r.get("payments") or 0)}
        if group_by:
            row = {"nature": r.get(group_by), **row}
        rows.append(row)
    return sorted(rows, key=lambda r: -r["total_usd"])


def _money(v) -> float | None:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _products(r: dict) -> list[str]:
    out = []
    for i in range(1, 6):
        name = r.get(f"name_of_drug_or_biological_or_device_or_medical_supply_{i}")
        if name:
            out.append(name)
    return out


def slim_general(r: dict) -> dict:
    return {"record_id": r.get("record_id"), "date": r.get("date_of_payment"), "amount_usd": _money(r.get("total_amount_of_payment_usdollars")),
            "payments_in_total": r.get("number_of_payments_included_in_total_amount"), "nature": r.get("nature_of_payment_or_transfer_of_value"),
            "form": r.get("form_of_payment_or_transfer_of_value"), "payer": r.get("applicable_manufacturer_or_applicable_gpo_making_payment_name"),
            "products": _products(r), "third_party": r.get("name_of_third_party_entity_receiving_payment_or_transfer_of_ccfc") or None,
            "context": r.get("contextual_information") or None, "dispute_status": r.get("dispute_status_for_publication"), "program_year": r.get("program_year")}


def slim_research(r: dict) -> dict:
    pi = " ".join(p for p in (r.get("principal_investigator_1_first_name"), r.get("principal_investigator_1_last_name")) if p) or None
    return {"record_id": r.get("record_id"), "date": r.get("date_of_payment"), "amount_usd": _money(r.get("total_amount_of_payment_usdollars")),
            "form": r.get("form_of_payment_or_transfer_of_value"), "payer": r.get("applicable_manufacturer_or_applicable_gpo_making_payment_name"),
            "recipient_type": r.get("covered_recipient_type"), "recipient_entity": r.get("noncovered_recipient_entity_name") or r.get("teaching_hospital_name") or None,
            "principal_investigator": pi, "principal_investigator_npi": r.get("principal_investigator_1_npi") or None,
            "study": r.get("name_of_study") or None, "clinicaltrials_gov": r.get("clinicaltrials_gov_identifier") or None, "preclinical": r.get("preclinical_research_indicator"),
            "products": _products(r), "context": r.get("context_of_research") or None, "dispute_status": r.get("dispute_status_for_publication"), "program_year": r.get("program_year")}


def slim_ownership(r: dict) -> dict:
    return {"record_id": r.get("record_id"), "payer": r.get("applicable_manufacturer_or_applicable_gpo_making_payment_name"),
            "amount_invested_usd": _money(r.get("total_amount_invested_usdollars")), "value_of_interest_usd": _money(r.get("value_of_interest")),
            "terms": r.get("terms_of_interest") or None, "interest_held_by_physician_or_immediate_family": r.get("interest_held_by_physician_or_an_immediate_family_member"),
            "dispute_status": r.get("dispute_status_for_publication"), "program_year": r.get("program_year")}


def slim_profile(r: dict) -> dict:
    name = " ".join(p for p in (r.get("covered_recipient_profile_first_name"), r.get("covered_recipient_profile_middle_name"), r.get("covered_recipient_profile_last_name")) if p)
    return {"profile_id": r.get("covered_recipient_profile_id"), "npi": r.get("covered_recipient_npi") or None, "name": name or None, "type": r.get("covered_recipient_profile_type"),
            "specialty": r.get("covered_recipient_profile_primary_specialty") or None, "city": r.get("covered_recipient_profile_city") or None,
            "state": r.get("covered_recipient_profile_state") or None, "license_states": [r.get(f"covered_recipient_profile_license_state_code_{i}") for i in range(1, 6) if r.get(f"covered_recipient_profile_license_state_code_{i}")]}


def _npi_ok(npi: str) -> bool:
    return bool(re.fullmatch(r"\d{10}", npi.strip()))


@mcp.tool(name="openpayments_index", annotations=_READ_ONLY)
async def openpayments_index() -> dict:
    """How to use the Open Payments tools. READ THIS FIRST: who is in the data, what a payment record is and is not, how to go from a name to an NPI."""
    try:
        ds = await _datasets()
        years = sorted(ds["general"])
    except ValueError:
        years = []
    return {
        "upstream": f"CMS Open Payments at {BASE}, the datastore behind {SITE}; no key; one dataset per program year and kind, published each June for the prior year",
        "program_years": years or "the metastore could not be read; see " + SITE,
        "workflow": ["openpayments_recipients with a last name and state (and a first name) to find the person's NPI and profile among the covered recipients; an NPI from NPPES or the OIG check skips this step",
                     "openpayments_summary with the NPI for totals by year and kind: how much, how many payments, in general, research and ownership",
                     "openpayments_payments with the NPI and a program year for the records themselves: date, amount, nature, payer, product, study"],
        "notes": ["Covered recipients are physicians, and since program year 2021 physician assistants, nurse practitioners, clinical nurse specialists, certified nurse anesthetists and midwives, and teaching hospitals. A researcher who is none of these is not here, and absence says nothing about them.",
                  "general payments are consulting fees, speaking, travel, meals, gifts, honoraria, education, royalties and grants outside a study; research payments are tied to a study and name a principal investigator, who may be the covered recipient or a separate physician; ownership records are investment and ownership interests.",
                  "Each record is one transfer of value as the company reported it; a recipient may have disputed it (dispute_status). The data is the company's claim, published after a review window, not an adjudication.",
                  "Names are matched exactly as stored (upper case, legal name); search by last name and state, then narrow by first name, specialty or city. The NPI is the stable key across years.",
                  "For a conflict-of-interest review, the question is usually research payments where the person is principal investigator, and general payments from a sponsor of the person's study; openpayments_summary separates them.",
                  "Cite as 'CMS Open Payments, program year <year>' with the recipient's link."],
        "link": SITE,
    }


@mcp.tool(name="openpayments_recipients", annotations=_READ_ONLY)
async def openpayments_recipients(last_name: str = "", first_name: str = "", state: str = "", npi: str = "", rows: int = ROWS) -> dict:
    """Covered recipients (physicians, practitioners) in Open Payments by name and state, or by NPI: profile id, NPI, name, type, specialty, city, state.

    Args:
        last_name: The last name as licensed (stored upper case; matched exactly), e.g. 'Smith'.
        first_name: The first name, exactly, to narrow.
        state: Two-letter state of the recipient's practice address, e.g. 'ID'.
        npi: A 10-digit National Provider Identifier; with it the names are ignored.
        rows: Recipients to return, 1-500. Default 50.
    """
    rows = max(1, min(int(rows or ROWS), MAX_ROWS))
    conds: list[tuple[str, str, str]] = []
    if npi.strip():
        if not _npi_ok(npi):
            return {"error": "npi must be 10 digits"}
        conds.append(("covered_recipient_npi", npi.strip(), "="))
    else:
        if not last_name.strip():
            return {"error": "give a last_name (with state and first_name to narrow) or an npi"}
        conds.append(("covered_recipient_profile_last_name", last_name.strip().upper(), "="))
        if first_name.strip():
            conds.append(("covered_recipient_profile_first_name", first_name.strip().upper(), "="))
        if state.strip():
            conds.append(("covered_recipient_profile_state", state.strip().upper(), "="))
    try:
        ds = await _datasets()
        body = await _rows(ds["profile"], conds, rows, ttl=DAY)
    except ValueError as e:
        return {"error": str(e), "upstream": BASE}
    found = [slim_profile(r) for r in body["results"]]
    out = {"query": {k: v for k, v in (("last_name", last_name.strip().upper()), ("first_name", first_name.strip().upper()), ("state", state.strip().upper()), ("npi", npi.strip())) if v},
           "total": body.get("count", len(found)), "recipients": found, "link": SITE}
    if out["total"] > len(found):
        out["note"] = f"{out['total']} recipients match; the first {len(found)} are here. Add first_name or state, or raise rows."
    if not found:
        out["note"] = "No covered recipient matches. The name is matched exactly as licensed and stored upper case; try the last name alone, or the person may not be a covered recipient at all."
    return out


@mcp.tool(name="openpayments_payments", annotations=_READ_ONLY)
async def openpayments_payments(npi: str, program_year: int = 0, kind: str = "general", rows: int = ROWS) -> dict:
    """The payments companies reported to one covered recipient in a program year: general, research (as recipient or as principal investigator) or ownership, with totals by nature.

    Args:
        npi: The recipient's 10-digit NPI, from openpayments_recipients.
        program_year: 2019 to the latest published; the latest when 0.
        kind: general (default), research or ownership.
        rows: Records to return, 1-500, newest first. Default 50.
    """
    if not _npi_ok(npi):
        return {"error": "npi must be 10 digits"}
    k = kind.strip().lower()
    if k not in KINDS:
        return {"error": "kind must be general, research or ownership"}
    rows = max(1, min(int(rows or ROWS), MAX_ROWS))
    try:
        ds = await _datasets()
        years = sorted(ds[k])
        year = int(program_year or years[-1])
        if year not in ds[k]:
            return {"error": f"program_year must be one of {', '.join(str(y) for y in years)} for {k} payments"}
        dataset = ds[k][year]
        n = npi.strip()
        if k == "general":
            body = await _rows(dataset, [("covered_recipient_npi", n, "=")], rows, sort="date_of_payment")
            out = {"npi": n, "program_year": year, "kind": k, "total": body.get("count", 0), "returned": len(body["results"]), "payments": [slim_general(r) for r in body["results"]]}
            out["by_nature"] = await _totals(dataset, [("covered_recipient_npi", n, "=")], "nature_of_payment_or_transfer_of_value")
            out["total_usd"] = round(sum(x["total_usd"] for x in out["by_nature"]), 2)
        elif k == "research":
            # The four reads of a year's research table go out together; each takes the datastore a few seconds.
            as_recipient, as_pi, t_recipient, t_pi = await asyncio.gather(
                _rows(dataset, [("covered_recipient_npi", n, "=")], rows, sort="date_of_payment"),
                _rows(dataset, [("principal_investigator_1_npi", n, "=")], rows, sort="date_of_payment"),
                _totals(dataset, [("covered_recipient_npi", n, "=")]), _totals(dataset, [("principal_investigator_1_npi", n, "=")]))
            out = {"npi": n, "program_year": year, "kind": k,
                   "as_recipient": {"total": as_recipient.get("count", 0), "returned": len(as_recipient["results"]), "payments": [slim_research(r) for r in as_recipient["results"]]},
                   "as_principal_investigator": {"total": as_pi.get("count", 0), "returned": len(as_pi["results"]), "payments": [slim_research(r) for r in as_pi["results"]]}}
            out["as_recipient"].update((t_recipient or [{"total_usd": 0.0, "count": 0}])[0])
            out["as_principal_investigator"].update((t_pi or [{"total_usd": 0.0, "count": 0}])[0])
            out["note"] = "A research payment names the study's principal investigator separately from the recipient (often a hospital or entity); both views are here, and a record can appear in both."
        else:
            # The ownership dataset names its columns for the physician, not the covered recipient.
            body = await _rows(dataset, [("physician_npi", n, "=")], rows)
            out = {"npi": n, "program_year": year, "kind": k, "total": body.get("count", 0), "returned": len(body["results"]), "interests": [slim_ownership(r) for r in body["results"]]}
    except ValueError as e:
        return {"error": str(e), "upstream": BASE}
    out["link"] = SITE
    return out


@mcp.tool(name="openpayments_summary", annotations=_READ_ONLY)
async def openpayments_summary(npi: str, from_year: int = 0, to_year: int = 0) -> dict:
    """One covered recipient's totals by program year: general payments (amount and count), research payments as recipient and as principal investigator, ownership records.

    Args:
        npi: The recipient's 10-digit NPI, from openpayments_recipients.
        from_year: First program year; the latest three years when 0 (each year is several queries, a few seconds each).
        to_year: Last program year; the latest when 0.
    """
    if not _npi_ok(npi):
        return {"error": "npi must be 10 digits"}
    n = npi.strip()
    try:
        ds = await _datasets()
        latest = max(ds["general"])
        first = int(from_year) if from_year else latest - 2
        years = [y for y in sorted(ds["general"]) if y >= first and (not to_year or y <= int(to_year))]
        if not years:
            return {"error": f"no program years between {from_year} and {to_year}; published years are {min(ds['general'])} to {max(ds['general'])}"}
        async def year_row(y: int) -> dict:
            # A year's reads go out together, one year after another, so the datastore sees at most four requests at once.
            none = [{"total_usd": 0.0, "count": 0}]
            jobs = [_totals(ds["general"][y], [("covered_recipient_npi", n, "=")])]
            if y in ds["research"]:
                jobs += [_totals(ds["research"][y], [("covered_recipient_npi", n, "=")]), _totals(ds["research"][y], [("principal_investigator_1_npi", n, "=")])]
            if y in ds["ownership"]:
                jobs.append(_rows(ds["ownership"][y], [("physician_npi", n, "=")], 1))
            got = list(await asyncio.gather(*jobs))
            row: dict = {"program_year": y, "general": (got.pop(0) or none)[0]}
            if y in ds["research"]:
                row["research_as_recipient"] = (got.pop(0) or none)[0]
                row["research_as_principal_investigator"] = (got.pop(0) or none)[0]
            if y in ds["ownership"]:
                row["ownership_records"] = got.pop(0).get("count", 0)
            return row

        by_year = [await year_row(y) for y in years]
    except ValueError as e:
        return {"error": str(e), "upstream": BASE}
    totals = {"general_usd": round(sum(r["general"]["total_usd"] for r in by_year), 2), "general_payments": sum(r["general"]["count"] for r in by_year),
              "research_as_recipient_usd": round(sum(r.get("research_as_recipient", {}).get("total_usd", 0) for r in by_year), 2),
              "research_as_principal_investigator_usd": round(sum(r.get("research_as_principal_investigator", {}).get("total_usd", 0) for r in by_year), 2),
              "ownership_records": sum(r.get("ownership_records", 0) for r in by_year)}
    return {"npi": n, "years": years, "totals": totals, "by_year": by_year, "link": SITE,
            "note": "Totals are the companies' reports as published, disputed records included; see openpayments_payments for the records and their dispute status."}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# An NPI the model names waits on a recipient search that returned it (#40); one a person gives passes as given.
given(mcp, {"openpayments_payments": {"npi": "openpayments_recipients"}, "openpayments_summary": {"npi": "openpayments_recipients"}})
