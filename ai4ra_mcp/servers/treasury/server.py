"""treasury: the Treasury Reporting Rates of Exchange, the U.S. government's own exchange rates for converting foreign currency.

Upstream: Fiscal Data, https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/rates_of_exchange
(JSON, no key; filter=field:op:value with eq, lt, lte, gt, gte, in; sort; fields; page[size] and page[number]). The
Bureau of the Fiscal Service publishes one rate per currency per calendar quarter (record_date the quarter's last day,
2026-09-30 the latest on 2026-10-16), as foreign currency units per one U.S. dollar, and an amended rate within a
quarter when a currency moves 10 percent or more; its rule is that a foreign-currency amount is converted at the rate
in effect on the date of the transaction. About 170 currencies a quarter, named 'Country-Currency' ('Canada-Dollar',
'Euro Zone-Euro', 'United Kingdom-Pound'). This is the rate a federal award's foreign subaward, purchase or travel
expense is reported at; it is not a market rate.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
API = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/rates_of_exchange"
SITE = "https://fiscaldata.treasury.gov/datasets/treasury-reporting-rates-exchange/"
FIELDS = "record_date,country,currency,country_currency_desc,exchange_rate,effective_date"
ROWS, MAX_ROWS = 50, 500
_cache = TTLCache()

mcp = MCPServer(
    "treasury",
    instructions="The Treasury Reporting Rates of Exchange from Fiscal Data: the currencies (treasury_currencies), a currency's quarterly rates (treasury_rates), and a foreign amount converted to dollars at the rate in effect on a date (treasury_convert). No key. Read treasury_index first.",
)


async def _rows(params: dict, ttl: float) -> tuple[list[dict], dict]:
    """One page of the dataset: (rows, meta)."""
    key = "rates:" + repr(sorted(params.items()))
    body = await _cache.remember(key, ttl, lambda: get_json(API, params))
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise ValueError("Fiscal Data did not return its data list")
    return body["data"], body.get("meta") or {}


def _date(value: str, label: str) -> str:
    v = value.strip()
    try:
        return date.fromisoformat(v).isoformat()
    except ValueError:
        raise ValueError(f"{label} must be a date, YYYY-MM-DD") from None


def slim(r: dict) -> dict:
    raw = r.get("exchange_rate")
    try:
        rate = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        rate = None
    return {"currency": r.get("country_currency_desc"), "country": r.get("country"), "unit": r.get("currency"), "record_date": r.get("record_date"),
            "effective_date": r.get("effective_date"), "rate": rate}


async def _latest_date() -> str:
    rows, _ = await _rows({"sort": "-record_date", "page[size]": 1, "fields": "record_date"}, HOUR)
    if not rows:
        raise ValueError("Fiscal Data returned no rows")
    return rows[0]["record_date"]


async def _quarter(record_date: str) -> list[dict]:
    rows, _ = await _rows({"filter": f"record_date:eq:{record_date}", "sort": "country_currency_desc", "page[size]": 1000, "fields": FIELDS}, DAY)
    return rows


async def _resolve(currency: str) -> tuple[str | None, list[str]]:
    """The dataset's own 'Country-Currency' name for what a person wrote: exact (case aside), else the one name whose country,
    unit or whole carries the words; several or none leave the first None and the list says which."""
    want = currency.strip().lower()
    names = [r["country_currency_desc"] for r in await _quarter(await _latest_date())]
    exact = [n for n in names if n.lower() == want]
    if exact:
        return exact[0], exact
    words = [w for w in want.replace("-", " ").split() if w]
    partial = [n for n in names if all(w in n.lower() for w in words)]
    return (partial[0] if len(partial) == 1 else None), partial


@mcp.tool(name="treasury_index", annotations=_READ_ONLY)
async def treasury_index() -> dict:
    """How to use the Treasury exchange rate tools. READ THIS FIRST: what the rate is, which rate applies to a transaction, how currencies are named."""
    try:
        latest = await _latest_date()
    except ValueError:
        latest = None
    return {
        "upstream": f"The Treasury Reporting Rates of Exchange from Fiscal Data, {API}; no key; the Bureau of the Fiscal Service's quarterly rates",
        "latest_quarter": latest or "the latest quarter could not be read; see " + SITE,
        "workflow": ["treasury_currencies to find the dataset's name for a currency ('Canada-Dollar', 'Euro Zone-Euro'); a country or unit word is enough when it names one",
                     "treasury_rates for a currency's rates by quarter, or every currency's rate for one quarter",
                     "treasury_convert to turn a foreign amount into dollars at the rate in effect on the transaction's date, with the rate and its quarter shown"],
        "notes": ["The rate is foreign currency units per one U.S. dollar (Canada-Dollar 1.418 means 1.418 Canadian dollars buy one U.S. dollar), so dollars = amount / rate.",
                  "One rate per currency per calendar quarter, dated the quarter's last day (record_date), effective from that date until the next; an amended rate appears within a quarter when a currency moves 10 percent or more, with its own effective_date.",
                  "Treasury's rule: convert at the rate in effect on the date of the transaction (the latest rate whose effective date is on or before it). That is what treasury_convert does; it never averages or uses a market rate.",
                  "This is the rate federal reporting uses (SF-425s, a foreign subrecipient's invoice, foreign travel on an award); it is not a market rate and a bank's rate will differ. Say which quarter's rate was used.",
                  "Cite as 'Treasury Reporting Rates of Exchange, <record_date>' with the dataset link."],
        "link": SITE,
    }


@mcp.tool(name="treasury_currencies", annotations=_READ_ONLY)
async def treasury_currencies(search: str = "") -> dict:
    """The currencies in the latest quarter's table, as the dataset names them ('Country-Currency'), each with its rate; the names treasury_rates and treasury_convert take.

    Args:
        search: Words to match in the country or unit ('canada', 'euro', 'pound'); empty for all.
    """
    try:
        latest = await _latest_date()
        rows = await _quarter(latest)
    except ValueError as e:
        return {"error": str(e), "upstream": API}
    words = [w for w in search.strip().lower().replace("-", " ").split() if w]
    found = [slim(r) for r in rows if all(w in (r.get("country_currency_desc") or "").lower() for w in words)]
    return {"record_date": latest, "total": len(found), "currencies": found, "link": SITE}


@mcp.tool(name="treasury_rates", annotations=_READ_ONLY)
async def treasury_rates(currency: str = "", record_date: str = "", from_date: str = "", to_date: str = "", rows: int = ROWS) -> dict:
    """Treasury exchange rates: one currency's rates by quarter, newest first, or every currency's rate for one quarter.

    Give a currency, a record_date (a quarter's last day), or both; with a currency alone, every quarter the dataset
    holds from the newest. Use it to show the rate behind a conversion or how a currency moved over an award's life.

    Args:
        currency: The dataset's name ('Canada-Dollar') or words that name one ('canada', 'euro zone').
        record_date: One quarter's date, YYYY-MM-DD, as the dataset dates it ('2026-06-30').
        from_date: Earliest record_date, YYYY-MM-DD.
        to_date: Latest record_date, YYYY-MM-DD.
        rows: Rows to return, 1-500. Default 50.
    """
    rows = max(1, min(int(rows or ROWS), MAX_ROWS))
    filters = []
    name = None
    try:
        if currency.strip():
            name, matched = await _resolve(currency)
            if name is None:
                return {"total": 0, "rates": [], "currencies_matched": matched,
                        "error": (f"'{currency}' matches {len(matched)} currencies; pass one name in full" if matched else f"no currency matching '{currency}'; see treasury_currencies")}
            filters.append(f"country_currency_desc:eq:{name}")
        if record_date.strip():
            filters.append(f"record_date:eq:{_date(record_date, 'record_date')}")
        if from_date.strip():
            filters.append(f"record_date:gte:{_date(from_date, 'from_date')}")
        if to_date.strip():
            filters.append(f"record_date:lte:{_date(to_date, 'to_date')}")
    except ValueError as e:
        return {"error": str(e)}
    if not filters:
        return {"error": "give a currency, a record_date, or both"}
    params = {"filter": ",".join(filters), "sort": "-record_date,country_currency_desc", "page[size]": rows, "fields": FIELDS}
    try:
        data, meta = await _rows(params, HOUR)
    except ValueError as e:
        return {"error": str(e), "upstream": API}
    out = {"query": {k: v for k, v in (("currency", name), ("record_date", record_date.strip()), ("from_date", from_date.strip()), ("to_date", to_date.strip())) if v},
           "total": meta.get("total-count", len(data)), "returned": len(data), "rates": [slim(r) for r in data], "link": SITE}
    if isinstance(out["total"], int) and out["total"] > len(data):
        out["note"] = f"{out['total']} rows match; the newest {len(data)} are here. Narrow the dates or raise rows (to {MAX_ROWS})."
    return out


@mcp.tool(name="treasury_convert", annotations=_READ_ONLY)
async def treasury_convert(amount: float, currency: str, transaction_date: str = "") -> dict:
    """A foreign-currency amount in U.S. dollars at the Treasury rate in effect on the transaction's date, with the rate and its quarter.

    Args:
        amount: The amount in the foreign currency, e.g. 12500.
        currency: The dataset's name ('Canada-Dollar') or words that name one ('canada').
        transaction_date: The date of the transaction, YYYY-MM-DD; today when empty.
    """
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        return {"error": "amount must be a number"}
    try:
        when = _date(transaction_date, "transaction_date") if transaction_date.strip() else date.today().isoformat()
        name, matched = await _resolve(currency)
    except ValueError as e:
        return {"error": str(e)}
    if name is None:
        return {"currencies_matched": matched, "error": (f"'{currency}' matches {len(matched)} currencies; pass one name in full" if matched else f"no currency matching '{currency}'; see treasury_currencies")}
    try:
        data, _ = await _rows({"filter": f"country_currency_desc:eq:{name},effective_date:lte:{when}", "sort": "-effective_date", "page[size]": 1, "fields": FIELDS}, HOUR)
    except ValueError as e:
        return {"error": str(e), "upstream": API}
    if not data:
        return {"error": f"no Treasury rate for {name} in effect on or before {when}; the dataset begins in 2001 and a currency may enter it later"}
    r = slim(data[0])
    if not r["rate"]:
        return {"error": f"the rate for {name} on {r['record_date']} is not a number in the dataset", "rate": r}
    usd = amt / r["rate"]
    return {"amount": amt, "currency": name, "transaction_date": when, "rate": r["rate"], "rate_record_date": r["record_date"], "rate_effective_date": r["effective_date"],
            "usd": round(usd, 2), "method": f"{amt:,.2f} {r['unit']} / {r['rate']} {r['unit']} per USD = {usd:,.2f} USD, at the Treasury rate in effect on {when} (the {r['record_date']} quarterly rate, effective {r['effective_date']})",
            "link": SITE}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# A currency the model names waits on the dataset's own list (#40); an amount and a date are the conversation's own.
given(mcp, {"treasury_rates": {"currency": "treasury_currencies"}, "treasury_convert": {"currency": "treasury_currencies"}})
