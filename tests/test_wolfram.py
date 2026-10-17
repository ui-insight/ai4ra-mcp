"""wolfram, offline from responses captured live on 2026-10-16 in tests/fixtures/wolfram/ (the LLM API's text for a currency
conversion and a duration, its 501 body with a suggested input, Short Answers' line and its 501 body): the LLM API's text read
into its sections, each status Wolfram answers with, the missing-key answer, the AppID as the bearer header and never in the
URL or the cache key, the argument checks."""

from pathlib import Path

import httpx

from ai4ra_mcp.common import http as h
from ai4ra_mcp.servers.wolfram import server as w

FIX = Path(__file__).parent / "fixtures" / "wolfram"
F = {p.stem: p.read_text(encoding="utf-8") for p in FIX.glob("*.txt")}
SAMPLE = F["llm_euros"]


def _wolfram(monkeypatch, status=200, body=SAMPLE, calls=None, raise_exc=None):
    calls = calls if calls is not None else []

    class Resp:
        def __init__(self, url):
            self.status_code, self.text, self.url = status, body, url

    class Client:
        def __init__(self, **kw):
            self.headers = kw.get("headers") or {}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            calls.append((url, dict(params or {}), dict(self.headers)))
            if raise_exc:
                raise raise_exc
            return Resp(url)

    monkeypatch.setattr(w.httpx, "AsyncClient", Client)
    w._cache._d.clear()
    return calls


def test_parse_llm_text():
    p = w.parse_llm_text(SAMPLE)
    assert p["query"] == "450 euros in US dollars" and p["interpretation"] == "convert €450 (euros) to US dollars" and p["result"] == "$506.39 (US dollars) (October 16, 2026)"
    assert set(p["sections"]) == {"Exchange history for €450 (euros)", "Additional currency conversions for €450 (euros)"}
    assert p["sections"]["Exchange history for €450 (euros)"].startswith("1-year minimum | $502.96") and "GBP | £379.73 (British pounds)" in p["sections"]["Additional currency conversions for €450 (euros)"]
    assert p["link"] == "https://www.wolframalpha.com/input?i=450+euros+in+US+dollars"
    d = w.parse_llm_text(F["llm_days"])
    assert d["result"] == "364 days" and d["interpretation"].startswith("days from | Thursday, October 1, 2026") and d["link"].startswith("https://www.wolframalpha.com/input?i=days")
    # An assumption Wolfram offers stays under its own heading, with the string to resend as the assumption argument.
    assert d["sections"]["Assumption"] == 'Assuming "2026-10-01" is a date\nTo use as a year set assumption=*MC.2026!-10!-01-_*PseudoTokenYear-' and "52 weeks" in d["sections"]["Time span"]
    # A heading-less body, and a line that only looks like a heading (a URL, an image line), parse without error.
    assert w.parse_llm_text("just words") == {"query": None, "interpretation": None, "result": None, "sections": {}, "link": None}
    assert w.parse_llm_text("Result:\nimage: https://x/y.png\nhttps://x/z:\n")["result"] == "image: https://x/y.png\nhttps://x/z:"


async def test_ask_sends_the_key_as_the_bearer_header_and_not_in_the_url(monkeypatch):
    monkeypatch.delenv(w.KEY_ENV, raising=False)
    calls = _wolfram(monkeypatch)
    token = h.request_key.set("SECRET_APPID_1")
    try:
        out = await w.wolfram_ask("450 euros in US dollars", units="metric", assumption="DateOrder_**Day.Month.Year--")
    finally:
        h.request_key.reset(token)
    url, params, headers = calls[0]
    assert url == w.LLM and params == {"input": "450 euros in US dollars", "maxchars": 6800, "units": "metric", "assumption": "DateOrder_**Day.Month.Year--"}
    assert headers["Authorization"] == "Bearer SECRET_APPID_1" and headers["User-Agent"].startswith("ai4ra-mcp/") and "SECRET" not in url + repr(params)
    assert all("SECRET" not in k for k in w._cache._d)
    assert out["result"] == "$506.39 (US dollars) (October 16, 2026)" and out["interpretation"].startswith("convert") and out["link"].startswith("https://") and out["text"] == SAMPLE.strip()
    assert out["source"] == "Wolfram|Alpha" and out["truncated"] is False and out["units"] == "metric"
    # The same call within the hour is answered from the cache: one request upstream.
    token = h.request_key.set("SECRET_APPID_2")
    try:
        await w.wolfram_ask("450  euros in US dollars", units="METRIC", assumption="DateOrder_**Day.Month.Year--")
    finally:
        h.request_key.reset(token)
    assert len(calls) == 1


async def test_answer_is_one_line(monkeypatch):
    monkeypatch.setenv(w.KEY_ENV, "ENV_APPID")
    calls = _wolfram(monkeypatch, body=F["short_euros"])
    out = await w.wolfram_answer("450 euros in US dollars")
    assert out["answer"] == "$506.39  (US dollars)" and calls[0][0] == w.SHORT and calls[0][1] == {"i": "450 euros in US dollars"} and calls[0][2]["Authorization"] == "Bearer ENV_APPID"


async def test_without_a_key_both_tools_say_so(monkeypatch):
    monkeypatch.delenv(w.KEY_ENV, raising=False)
    calls = _wolfram(monkeypatch)
    for out in (await w.wolfram_ask("2+2"), await w.wolfram_answer("2+2")):
        assert "no API key" in out["error"] and "developer.wolframalpha.com" in out["error"] and out["do_not"].startswith("Do not answer")
    assert calls == []
    idx = await w.wolfram_index()
    assert idx["key"]["on_this_request"] is False and "2,000 calls a month" in idx["key"]["terms"] and any("6*10^14" in p for p in idx["phrasing"])


async def test_statuses_are_said_in_wolframs_words(monkeypatch):
    monkeypatch.setenv(w.KEY_ENV, "ENV_APPID")
    _wolfram(monkeypatch, status=501, body=F["llm_501"])
    out = await w.wolfram_ask("florp zzqx")
    assert out["error"].startswith("Wolfram|Alpha could not interpret") and out["wolfram_said"] == "Wolfram|Alpha could not understand: florp zzqx. \nYou could instead try: florp" and out["input"] == "florp zzqx"
    assert "Do not compute" in out["do_not"]
    _wolfram(monkeypatch, status=501, body=F["short_501"])
    short = await w.wolfram_answer("florp zzqx")
    assert short["error"].startswith("Wolfram|Alpha could not interpret") and short["wolfram_said"] == '"Wolfram|Alpha did not understand your input"' and "wolfram_ask" in short["note"]
    _wolfram(monkeypatch, status=401, body="Invalid appid")
    out = await w.wolfram_ask("2+2")
    assert "refused the AppID (401: Invalid appid)" in out["error"] and "Do not answer" in out["do_not"]
    _wolfram(monkeypatch, status=400, body="No input.")
    assert (await w.wolfram_ask("2+2"))["error"].startswith("Wolfram|Alpha found no input (400): No input.")
    _wolfram(monkeypatch, status=429, body="")
    assert "quota" in (await w.wolfram_answer("2+2"))["error"]
    _wolfram(monkeypatch, status=503, body="<html>down</html>")
    assert (await w.wolfram_ask("2+2"))["error"].startswith("503 from Wolfram|Alpha")
    _wolfram(monkeypatch, raise_exc=httpx.ConnectTimeout("slow"))
    assert (await w.wolfram_ask("2+2"))["error"] == "Wolfram|Alpha could not be reached: ConnectTimeout"


async def test_argument_checks(monkeypatch):
    monkeypatch.setenv(w.KEY_ENV, "ENV_APPID")
    calls = _wolfram(monkeypatch)
    assert "input is required" in (await w.wolfram_ask("  "))["error"] and "input is required" in (await w.wolfram_answer(""))["error"]
    assert "maxchars must be between" in (await w.wolfram_ask("2+2", maxchars=50))["error"] and "maxchars must be between" in (await w.wolfram_ask("2+2", maxchars=10**6))["error"]
    assert "units must be one of" in (await w.wolfram_ask("2+2", units="furlongs"))["error"] and "units must be one of" in (await w.wolfram_answer("2+2", units="si"))["error"]
    assert calls == []
    out = await w.wolfram_ask("2+2", maxchars=500)
    assert calls[0][1] == {"input": "2+2", "maxchars": 500} and out["maxchars"] == 500 and out["assumption"] is None
