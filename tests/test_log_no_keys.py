"""Log no keys: nothing a person sent as their credential appears in any log line. The httpx and httpcore
loggers are held at WARNING (their INFO line is the request's full URL), key-like query parameters are
redacted from what they and the root handlers still emit, and the per diem server sends its key as a header."""

import logging

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
