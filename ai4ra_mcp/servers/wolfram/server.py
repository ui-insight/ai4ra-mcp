"""wolfram: Wolfram|Alpha, a computed answer with its interpretation beside it, so a number is checked by a tool and not recalled.

Upstream: two of Wolfram|Alpha's APIs, both keyed by the person's own AppID from https://developer.wolframalpha.com/ (a
free non-commercial account allows 2,000 calls a month; paid tiers above). The LLM API, GET
https://www.wolframalpha.com/api/v1/llm-api?input=..., answers in plain text shaped for a model: labelled sections (the
query, the input interpretation, the result, images, property sections) and a link to the website's result page; it takes
maxchars (6,800 by default), units and an assumption, and answers 501 with a plain-text body when it cannot interpret the
input. Short Answers, GET https://api.wolframalpha.com/v1/result?i=..., is one line of text for the main result and 501 when
no short result exists. Both answer 401 `Invalid appid` as plain text when the key is bad or missing (probed 2026-10-16;
the documentation says 403). The developer portal's Get an AppID form asks for one API; an AppID registered for the LLM
API answered Short Answers too (verified 2026-10-16 with a currency conversion, $506.39 for 450 euros, and a 501 from
each). The AppID goes as `Authorization: Bearer <AppID>`, the form the LLM API documents and Short Answers also accepts,
never in the URL, so it is in no log line; the cache key is the input and its options alone. Answers are cached an hour.
Wolfram Cloud and Wolfram Language evaluation are a different product and are not here.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx
from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import HEADERS, HOUR, TIMEOUT_S, TTLCache, api_key, missing_key
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
KEY_ENV = "AI4RA_MCP_WOLFRAM_KEY"
KEY_HOW = "An AppID comes from https://developer.wolframalpha.com/ : sign in with a Wolfram ID, Get an AppID, choose the LLM API, and copy it (the AppID is the whole credential; there is no separate token). Free for non-commercial use, 2,000 calls a month; paid tiers above that."
LLM = "https://www.wolframalpha.com/api/v1/llm-api"
SHORT = "https://api.wolframalpha.com/v1/result"
PORTAL = "https://developer.wolframalpha.com/"
TERMS = "https://products.wolframalpha.com/api/termsofuse"
MAXCHARS, MAXCHARS_MIN, MAXCHARS_MAX = 6800, 100, 20000
UNITS = ("metric", "imperial")
_cache = TTLCache()

# The LLM API's text is sections, each a heading line ending in a colon and the lines under it to the next blank line or
# heading; the website link's heading quotes the input ("Wolfram|Alpha website result for \"...\":").
_HEADING = re.compile(r"^([^\n:][^\n]*):\s*$")
_WEBSITE = re.compile(r"^Wolfram\|Alpha website result for ", re.I)

mcp = MCPServer(
    "wolfram",
    instructions="Wolfram|Alpha with the person's own AppID: a computed answer with Wolfram's interpretation of the question beside it (wolfram_ask) or one line for the main result (wolfram_answer), for arithmetic, unit and currency conversions, dates and durations, statistics, and scientific facts and formulas, so a number is checked by a tool rather than recalled. Needs the person's AppID. Read wolfram_index first.",
)


def parse_llm_text(text: str) -> dict:
    """The LLM API's plain text as sections: heading to its lines. The interpretation, the result and the website link
    are lifted out by their documented headings; everything else stays under its own heading. The text is kept whole."""
    sections: dict[str, str] = {}
    heading, lines = None, []
    for line in text.splitlines():
        m = _HEADING.match(line)
        if m and not line.startswith(("http://", "https://", "image:")):
            if heading is not None:
                sections[heading] = "\n".join(lines).strip()
            heading, lines = m.group(1).strip(), []
        elif heading is not None:
            lines.append(line)
    if heading is not None:
        sections[heading] = "\n".join(lines).strip()
    link = next((v.strip().splitlines()[0] for k, v in sections.items() if _WEBSITE.match(k) and v.strip()), None)
    query = sections.get("Query")
    return {
        "query": query.strip('"') if query else None,
        "interpretation": sections.get("Input interpretation") or None,
        "result": sections.get("Result") or None,
        "sections": {k: v for k, v in sections.items() if k not in ("Query", "Input interpretation", "Result") and not _WEBSITE.match(k) and v},
        "link": link,
    }


async def _get(url: str, params: dict) -> tuple[int, str]:
    """GET one of Wolfram|Alpha's text endpoints with the person's AppID as the bearer header. The status comes back
    with the body, since a 501 carries Wolfram's own words about an input it could not interpret."""
    key = api_key(KEY_ENV)
    if not key:
        raise LookupError(KEY_ENV)
    async with httpx.AsyncClient(timeout=TIMEOUT_S, headers={**HEADERS, "Authorization": f"Bearer {key}"}, follow_redirects=True) as client:
        resp = await client.get(url, params=params)
    return resp.status_code, resp.text


async def _call(url: str, params: dict) -> tuple[int, str]:
    cache_key = url + "?" + repr(sorted(params.items()))
    return await _cache.remember(cache_key, HOUR, lambda: _get(url, params))


def _refused(status: int, body: str, q: str) -> dict | None:
    """The answer for a status that is not a result; None when the status is 200."""
    if status == 200:
        return None
    said = body.strip()[:2000]
    if status in (401, 403):
        return {"error": f"Wolfram|Alpha refused the AppID ({status}: {said or 'no body'}). Check the key you sent; " + KEY_HOW,
                "do_not": "Do not answer this from memory. Tell the person their AppID was refused and stop there."}
    if status == 501:
        return {"error": "Wolfram|Alpha could not interpret this input (501)", "input": q, "wolfram_said": said or None,
                "do_not": "Do not compute or recall the answer yourself. If Wolfram suggested inputs, offer them to the person or send one as given; otherwise ask the person to rephrase: one line of English keywords, exponents as 6*10^14, one property per call (wolfram_index)."}
    if status == 400:
        return {"error": f"Wolfram|Alpha found no input (400): {said}", "input": q}
    if status == 429:
        return {"error": "Wolfram|Alpha rate limit or monthly quota reached (429); wait before retrying, or check the AppID's allowance on the developer portal", "input": q}
    return {"error": f"{status} from Wolfram|Alpha: {said[:200]}", "input": q}


def _units(units: str) -> str | None:
    u = (units or "").strip().lower()
    if u and u not in UNITS:
        raise ValueError(f"units must be one of {list(UNITS)} or empty")
    return u or None


@mcp.tool(name="wolfram_index", annotations=_READ_ONLY)
async def wolfram_index() -> dict:
    """How to use the Wolfram|Alpha tools. READ THIS FIRST: the key and its terms, how to phrase an input, what each tool returns."""
    return {
        "upstream": f"Wolfram|Alpha's LLM API ({LLM}) and Short Answers API ({SHORT}), keyed by the person's own AppID",
        "key": {"on_this_request": api_key(KEY_ENV) is not None, "per_user": "send your own Wolfram|Alpha AppID as a bearer token; the server holds none unless the deployment set " + KEY_ENV + " as a fallback", "how": KEY_HOW,
                "terms": f"A free AppID is for non-commercial use, 2,000 calls a month; the person is responsible for the terms at {TERMS}. Every call to either tool counts one against the month."},
        "workflow": ["wolfram_ask(input) for an answer worth showing: Wolfram's interpretation of the question, the result and the website link come back together, so the reply can say what Wolfram understood and quote its result",
                     "wolfram_answer(input) for one line to carry on with: a number, a date, a converted amount",
                     "when the interpretation is not what was meant and wolfram_ask's text offers assumptions, call wolfram_ask again with the same input and the assumption string as given; rephrase only when no assumption fits",
                     "cite Wolfram|Alpha with the link wolfram_ask returns, and show the interpretation beside any figure"],
        "phrasing": ["one line of English keywords, not a full sentence: 'France population', '450 euros in US dollars', 'days from 2026-10-01 to 2027-09-30', 'integrate x^2 sin x'",
                     "exponents as 6*10^14, never e notation; single-letter variables; named constants without their values",
                     "a space between compound units ('kg m/s^2'); solve for a variable unit-free first when units are involved",
                     "one property per call: 'tungsten density' then 'tungsten melting point', not both at once",
                     "units='metric' or 'imperial' chooses the measurement system; the default depends on the request's location"],
        "notes": ["A 501 means Wolfram could not interpret the input; its own words come back as wolfram_said, sometimes with inputs to try. The server never changes the question on its own.",
                  "Short Answers (wolfram_answer) fails with 501 when no sufficiently short result exists; wolfram_ask then has the full answer.",
                  f"wolfram_ask's text is capped at maxchars characters, {MAXCHARS} by default; raise it for a long table, lower it for a one-line fact with its interpretation.",
                  "Answers are cached an hour, so repeating the same input within the hour costs no quota; a different input always costs one.",
                  "A table of values is one call, for the formula, not one call per row: ask Wolfram for the derivative, the rate or the expression once, and compute the rows from it. Every call counts against the month.",
                  "Wolfram|Alpha computes; it does not read this institution's rates, policies or budgets. Rates come from their own servers, and Wolfram does the arithmetic on figures the person or a tool supplied."],
    }


@mcp.tool(name="wolfram_ask", annotations=_READ_ONLY)
async def wolfram_ask(input: str, maxchars: int = MAXCHARS, units: str = "", assumption: str = "") -> dict:
    """Ask Wolfram|Alpha and get its computed answer with its interpretation of the question beside it (the LLM API).

    Returns Wolfram's plain text whole (text), with the query, the input interpretation, the result, the other sections by
    their headings and the link to the website's result page lifted out. Use it for arithmetic, conversions, dates and
    durations, statistics, and scientific facts and formulas; quote the result and show the interpretation.

    Args:
        input: One line of English keywords, e.g. '450 euros in US dollars', 'days from 2026-10-01 to 2027-09-30', 'tungsten density'.
        maxchars: Cap on the text's length, 100 to 20000. Default 6800.
        units: 'metric' or 'imperial'. Empty for Wolfram's default.
        assumption: An assumption string from an earlier answer's text, to pick that interpretation of the same input. Empty for none.
    """
    q = " ".join((input or "").split())
    if not q:
        return {"error": "input is required: one line of English keywords"}
    try:
        n = int(maxchars or MAXCHARS)
    except (TypeError, ValueError):
        return {"error": f"maxchars must be a whole number between {MAXCHARS_MIN} and {MAXCHARS_MAX}"}
    if not MAXCHARS_MIN <= n <= MAXCHARS_MAX:
        return {"error": f"maxchars must be between {MAXCHARS_MIN} and {MAXCHARS_MAX}"}
    params: dict = {"input": q, "maxchars": n}
    try:
        if u := _units(units):
            params["units"] = u
    except ValueError as e:
        return {"error": str(e)}
    if assumption.strip():
        params["assumption"] = assumption.strip()
    try:
        status, body = await _call(LLM, params)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except httpx.HTTPError as e:
        return {"error": f"Wolfram|Alpha could not be reached: {e.__class__.__name__}", "input": q}
    if refused := _refused(status, body, q):
        return refused
    parsed = parse_llm_text(body)
    return {"input": q, "maxchars": n, "units": params.get("units"), "assumption": params.get("assumption"), **parsed, "text": body.strip(),
            "source": "Wolfram|Alpha", "truncated": len(body) >= n}


@mcp.tool(name="wolfram_answer", annotations=_READ_ONLY)
async def wolfram_answer(input: str, units: str = "") -> dict:
    """One line from Wolfram|Alpha for the main result (the Short Answers API): a number, a date, a converted amount.

    For a figure the model needs to carry on with. When no short result exists Wolfram answers 501 and wolfram_ask has the
    full answer; when the interpretation matters, use wolfram_ask, which shows it.

    Args:
        input: One line of English keywords, e.g. '2.5 percent of 184000', 'weeks between 2026-10-01 and 2027-03-31'.
        units: 'metric' or 'imperial'. Empty for Wolfram's default.
    """
    q = " ".join((input or "").split())
    if not q:
        return {"error": "input is required: one line of English keywords"}
    params: dict = {"i": q}
    try:
        if u := _units(units):
            params["units"] = u
    except ValueError as e:
        return {"error": str(e)}
    try:
        status, body = await _call(SHORT, params)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except httpx.HTTPError as e:
        return {"error": f"Wolfram|Alpha could not be reached: {e.__class__.__name__}", "input": q}
    if refused := _refused(status, body, q):
        if status == 501:
            refused["note"] = "No sufficiently short result, or the input was not understood; wolfram_ask gives the full answer with its interpretation."
        return refused
    return {"input": q, "units": params.get("units"), "answer": body.strip(), "source": "Wolfram|Alpha",
            "note": "The main result as one line, without Wolfram's interpretation of the question; wolfram_ask shows what was understood."}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
