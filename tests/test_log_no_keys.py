"""Log no keys: nothing a person sent as their credential appears in any log line. The httpx and httpcore
loggers are held at WARNING (their INFO line is the request's full URL), key-like query parameters are
redacted from what they and the root handlers still emit, and the per diem server sends its key as a header."""

import json
import logging

from starlette.testclient import TestClient

from ai4ra_mcp.app import build_app
from ai4ra_mcp.common import http as h
from ai4ra_mcp.servers.perdiem import server as perdiem


def test_http_client_loggers_are_quiet_and_redacting(caplog):
    h.log_no_keys()
    for name in ("httpx", "httpcore"):
        assert logging.getLogger(name).level >= logging.WARNING
        assert any(isinstance(f, h.RedactKeys) for f in logging.getLogger(name).filters)
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("httpx").info('HTTP Request: GET https://api.gsa.gov/x?api_key=SECRET123 "HTTP/1.1 200 OK"')
        logging.getLogger("httpx").warning('HTTP Request: GET https://api.sam.gov/x?q=1&api_key=SECRET456&page=2 "HTTP/1.1 500"')
    assert "SECRET123" not in caplog.text and "SECRET456" not in caplog.text
    assert "api_key=[redacted]&page=2" in caplog.text


def test_redaction_covers_the_key_parameter_names():
    f = h.RedactKeys()
    for line in ("?api_key=A1", "?apikey=A1", "&api-key=A1", "?subscription-key=A1", "?registrationkey=A1", "?token=A1", "?access_token=A1", "?secret=A1", "?key=A1&other=keep"):
        r = logging.LogRecord("x", logging.INFO, "", 0, "url" + line, (), None)
        f.filter(r)
        assert "A1" not in r.getMessage() and "[redacted]" in r.getMessage(), line
        if "other" in line:
            assert "other=keep" in r.getMessage()
    r = logging.LogRecord("x", logging.INFO, "", 0, "plain %s", ("text",), None)
    f.filter(r)
    assert r.getMessage() == "plain text"


async def test_perdiem_sends_its_key_as_a_header(monkeypatch):
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen.update(url=url, params=params, headers=headers)
        return {"rates": []}

    monkeypatch.setattr(perdiem, "get_json", fake_get_json)
    token = h.request_key.set("FAKEKEY_header_test")
    try:
        await perdiem._get("rates/city/Boise/state/ID/year/2099")
    finally:
        h.request_key.reset(token)
    assert seen["headers"] == {"X-Api-Key": "FAKEKEY_header_test"}
    assert "FAKEKEY_header_test" not in seen["url"] and not seen["params"]


def test_redact_auth_keeps_the_form_and_no_character_of_a_token():
    key = "aBYgwiZVVeIdD5y1GuItf5UTqFvb7hAH58LjiULo"
    cases = {
        f"Bearer {key}": "Bearer <token:40>",
        f"bearer {key}": "bearer <token:40>",
        f"Bearer  {key}": "Bearer  <token:40>",
        f"Bearer: {key}": "Bearer: <token:40>",
        key: "<token:40>",
        f"Bearer Bearer {key}": "Bearer Bearer <token:40>",
        f"Bearer{key}": "Bearer<token:40>",
        f"Bearer:{key}": "Bearer:<token:40>",
        f"Basic {key}": "Basic <token:40>",
        f"Bearer {key} extra": "Bearer <token:40> <token:5>",
        f"Bearer\xa0{key}": "Bearer\xa0<token:40>",
        "Bearer": "Bearer",
        "": "",
        "abc": "<token:3>",
    }
    for value, redacted in cases.items():
        assert h.redact_auth(value) == redacted, value
        assert key not in redacted and key[:4] not in redacted and "extra" not in redacted


def test_describe_auth_fields_and_reasons_agree_with_the_middleware():
    key = "aBYgwiZVVeIdD5y1GuItf5UTqFvb7hAH58LjiULo"
    cases = {
        f"Bearer {key}": ("'Bearer <token:40>' len=47 scheme=Bearer sep=U+0020 token_len=40 padded=no", None),
        f"bearer {key}": ("'bearer <token:40>' len=47 scheme=bearer sep=U+0020 token_len=40 padded=no", None),
        f"Bearer  {key}": ("'Bearer  <token:40>' len=48 scheme=Bearer sep=U+0020 U+0020 token_len=40 padded=no", None),
        f" Bearer {key} ": ("' Bearer <token:40> ' len=49 scheme=Bearer sep=U+0020 token_len=40 padded=both", None),
        f"Bearer{key}": ("'Bearer<token:40>' len=46 scheme=Bearer sep=none token_len=40 padded=no", "no space between the scheme and the token"),
        f"Bearer: {key}": ("'Bearer: <token:40>' len=48 scheme=Bearer: sep=U+0020 token_len=40 padded=no", "a colon after the scheme"),
        f"Bearer:{key}": ("'Bearer:<token:40>' len=47 scheme=Bearer: sep=none token_len=40 padded=no", "a colon after the scheme"),
        key: ("'<token:40>' len=40 scheme=none sep=none token_len=40 padded=no", "no scheme word"),
        f"Basic {key}": ("'Basic <token:40>' len=46 scheme=Basic sep=U+0020 token_len=40 padded=no", "scheme is Basic, not Bearer"),
        f"Bearer\xa0{key}": ("'Bearer\\xa0<token:40>' len=47 scheme=Bearer sep=U+00A0 token_len=40 padded=no", "the separator is not a space"),
        "Bearer": ("'Bearer' len=6 scheme=Bearer sep=none token_len=0 padded=no", "no space between the scheme and the token"),
        "Bearer ": ("'Bearer ' len=7 scheme=Bearer sep=U+0020 token_len=0 padded=no", "no token"),
        "": ("'' len=0 scheme=none sep=none token_len=0 padded=no", "empty"),
    }
    for raw, (fields, reason) in cases.items():
        assert h.describe_auth(raw) == (fields, reason), raw
        assert key not in fields and key[:4] not in fields
        # The reason is None exactly when the middleware's own check accepts the value.
        v = raw.strip()
        assert (reason is None) == (v[:7].lower() == "bearer " and bool(v[7:].strip())), raw


def test_header_log_describes_every_request_and_never_a_value(monkeypatch, caplog):
    """With AI4RA_MCP_LOG_HEADERS=1 the middleware logs one WARNING per request: method, path, whether an
    Authorization header arrived and was accepted (and why not), its fields with the credential redacted, and the
    header names (the happy path and the sad ones alike, so a grep picks either); off, or unset, nothing is logged;
    no credential appears in any record."""
    monkeypatch.delenv("AI4RA_MCP_PERDIEM_KEY", raising=False)
    monkeypatch.setenv(h.LOG_HEADERS_ENV, "1")

    async def fake_get_json(url, params=None, headers=None):
        return {"rates": []}

    monkeypatch.setattr(perdiem, "get_json", fake_get_json)
    perdiem._cache._d.clear()
    rpc = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "gsa_perdiem_rates", "arguments": {"state": "ID", "year": 2026}}}
    hdr = {"Accept": "application/json, text/event-stream"}
    with TestClient(build_app(["perdiem"])) as client, caplog.at_level(logging.DEBUG):
        def call(headers):
            r = client.post("/perdiem/mcp", json=rpc, headers={**hdr, **headers})
            assert r.status_code == 200
            return json.loads(r.json()["result"]["content"][0]["text"])

        def lines():
            return [r.getMessage() for r in caplog.records if r.name == "ai4ra_mcp.headers"]

        caplog.clear()
        assert call({"Authorization": "Bearer SECRET_ACCEPTED_KEY"})["returned"] == 0
        (line,) = lines()
        head, names = line.split("; headers: ")
        assert head == "POST /perdiem/mcp: authorization accepted 'Bearer <token:19>' len=26 scheme=Bearer sep=U+0020 token_len=19 padded=no"
        assert "authorization" in names.split(", ") and "accept" in names.split(", ")
        caplog.clear()
        assert "no API key" in call({})["error"]
        (line,) = lines()
        head, names = line.split("; headers: ")
        assert head == "POST /perdiem/mcp: authorization absent" and "authorization" not in names.split(", ")
        caplog.clear()
        assert "no API key" in call({"Authorization": "Bearer: SECRET_COLON_KEY"})["error"]
        assert lines()[0].startswith("POST /perdiem/mcp: authorization rejected (a colon after the scheme) 'Bearer: <token:16>' len=24 scheme=Bearer: sep=U+0020 token_len=16 padded=no; headers: ")
        caplog.clear()
        assert "no API key" in call({"Authorization": "BearerSECRET_NOSPACE_"})["error"]
        assert lines()[0].startswith("POST /perdiem/mcp: authorization rejected (no space between the scheme and the token) 'Bearer<token:15>' len=21 scheme=Bearer sep=none token_len=15 padded=no; headers: ")
        caplog.clear()
        assert "no API key" in call({"Authorization": "SECRET_BARE_KEY_1"})["error"]
        assert lines()[0].startswith("POST /perdiem/mcp: authorization rejected (no scheme word) '<token:17>' len=17 scheme=none sep=none token_len=17 padded=no; headers: ")
        caplog.clear()
        assert client.get("/").status_code == 200
        assert lines()[0].startswith("GET /: authorization absent; headers: ")
        assert "SECRET" not in "".join(lines()) and "SECRET" not in caplog.text
        assert all(r.levelno == logging.WARNING for r in caplog.records if r.name == "ai4ra_mcp.headers")
        for off in ("", "0", "true", "yes"):
            monkeypatch.setenv(h.LOG_HEADERS_ENV, off)
            caplog.clear()
            assert call({"Authorization": "Bearer SECRET_ACCEPTED_KEY"})["returned"] == 0
            assert "no API key" in call({"Authorization": "Bearer: SECRET_COLON_KEY"})["error"]
            assert "no API key" in call({})["error"]
            assert not lines(), off
        monkeypatch.delenv(h.LOG_HEADERS_ENV)
        caplog.clear()
        assert "no API key" in call({})["error"]
        assert not lines()
        assert "SECRET" not in caplog.text
