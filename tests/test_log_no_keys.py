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


def test_auth_shape_carries_no_character_of_a_token():
    key = "aBYgwiZVVeIdD5y1GuItf5UTqFvb7hAH58LjiULo"
    cases = {
        f"Bearer: {key}": "scheme=Bearer: parts=2 last_len=40",
        key: "scheme=<40 chars> parts=1 last_len=40",
        f"Bearer Bearer {key}": "scheme=Bearer parts=3 last_len=40",
        f"Bearer:{key}": "scheme=<47 chars> parts=1 last_len=47",
        f"Basic {key}": "scheme=Basic parts=2 last_len=40",
        "Bearer": "scheme=Bearer parts=1 last_len=6",
        "": "scheme=<0 chars> parts=0 last_len=0",
    }
    for value, shape in cases.items():
        assert h.auth_shape(value) == shape, value
        assert key not in shape and key[:8] not in shape


def test_refusal_logs_the_header_shape_and_never_the_token(monkeypatch, caplog):
    """A keyed tool's refusal logs one WARNING saying whether an Authorization header arrived and, when one did,
    its shape; an accepted key logs nothing; the token's characters appear in no record either way. The line is
    written only with AI4RA_MCP_LOG_REFUSALS=1, the switch a deployment turns on to troubleshoot a client."""
    monkeypatch.delenv("AI4RA_MCP_PERDIEM_KEY", raising=False)
    monkeypatch.setenv(h.LOG_REFUSALS_ENV, "1")

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

        caplog.clear()
        assert call({"Authorization": "Bearer SECRET_ACCEPTED_KEY"})["returned"] == 0
        assert "no API key" not in caplog.text
        caplog.clear()
        assert "no API key" in call({})["error"]
        assert "no API key on this request (AI4RA_MCP_PERDIEM_KEY): authorization header absent" in caplog.text
        caplog.clear()
        assert "no API key" in call({"Authorization": "Bearer: SECRET_COLON_KEY"})["error"]
        assert "authorization header present but not accepted (scheme=Bearer: parts=2 last_len=16)" in caplog.text
        caplog.clear()
        assert "no API key" in call({"Authorization": "SECRET_BARE_KEY_1"})["error"]
        assert "present but not accepted (scheme=<17 chars> parts=1 last_len=17)" in caplog.text
        assert "SECRET" not in caplog.text
        assert all(r.levelno == logging.WARNING for r in caplog.records if r.name == "ai4ra_mcp.keys")
        for off in ("", "0", "true", "yes"):
            monkeypatch.setenv(h.LOG_REFUSALS_ENV, off)
            caplog.clear()
            assert "no API key" in call({"Authorization": "Bearer: SECRET_COLON_KEY"})["error"]
            assert not [r for r in caplog.records if r.name == "ai4ra_mcp.keys"], off
        monkeypatch.delenv(h.LOG_REFUSALS_ENV)
        caplog.clear()
        assert "no API key" in call({})["error"]
        assert not [r for r in caplog.records if r.name == "ai4ra_mcp.keys"]
        assert "SECRET" not in caplog.text
