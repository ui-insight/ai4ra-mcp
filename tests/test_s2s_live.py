"""Live checks of the s2s server against a running endpoint, skipped unless S2S_LIVE_ENDPOINT is set.
Against the mock (any copy) this exercises every tool including a submission; against a real
Grants.gov environment set S2S_LIVE_READONLY=1 to stop before submitting.

    S2S_LIVE_ENDPOINT=https://host/s2s-mock/grantsws-applicant/services/v2/ApplicantWebServicesSoapPort \\
    AI4RA_MCP_S2S_CERT_FILE=... AI4RA_MCP_S2S_KEY_FILE=... [AI4RA_MCP_S2S_CA_FILE=...] AI4RA_MCP_S2S_WRITES=1 \\
    S2S_LIVE_OPPORTUNITY=NSF-25-999 uv run pytest tests/test_s2s_live.py -v
"""

import hashlib
import os

import httpx
import pytest

LIVE = os.environ.get("S2S_LIVE_ENDPOINT", "").strip()
pytestmark = pytest.mark.skipif(not LIVE, reason="S2S_LIVE_ENDPOINT not set")
OPP = os.environ.get("S2S_LIVE_OPPORTUNITY", "NSF-25-999")
READONLY = os.environ.get("S2S_LIVE_READONLY", "").strip() == "1"
PDF_URL = "https://a.storyblok.grants.gov/f/21/x/b4573e6e90/applicantcertificaterequestform.pdf"
NS_GRANT = "http://apply.grants.gov/system/MetaGrantApplication"


@pytest.fixture(scope="module")
def s2s(monkeypatch_module):
    monkeypatch_module.setenv("AI4RA_MCP_S2S_ENDPOINT", LIVE)
    from ai4ra_mcp.servers.s2s import server
    monkeypatch_module.setattr(server, "DEFAULT_ENDPOINT", LIVE)
    return server


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


async def test_check_and_opportunity(s2s):
    r = await s2s.s2s_check(opportunity_number=OPP)
    assert r.get("ok"), r
    assert r["wsdl"]["is_applicant_v2"] and r["lookup"]["packages"] >= 1
    o = await s2s.s2s_opportunity(opportunity_number=OPP)
    assert o["count"] >= 1 and o["packages"][0]["package_id"] and o["packages"][0]["forms"], o
    assert (await s2s.s2s_opportunity(opportunity_number="NOPE-000"))["class"] == "not_found"


async def test_submit_and_status(s2s):
    if READONLY or not s2s.WRITES_ON:
        pytest.skip("read-only run or writes off")
    pdf = httpx.get(PDF_URL, follow_redirects=True).content
    import base64
    sha1 = base64.b64encode(hashlib.sha1(pdf).digest()).decode()
    o = await s2s.s2s_opportunity(opportunity_number=OPP)
    pkg = o["packages"][0]["package_id"]
    xml = (f'<grant:GrantApplication xmlns:grant="{NS_GRANT}"><grant:GrantSubmissionHeader><grant:OpportunityID>{OPP}</grant:OpportunityID>'
           f'<grant:PackageID>{pkg}</grant:PackageID><grant:SubmissionTitle>s2s live test</grant:SubmissionTitle></grant:GrantSubmissionHeader><grant:Forms>'
           f'<a:AttachmentForm_1_2 xmlns:a="http://apply.grants.gov/forms/AttachmentForm_1_2-V1.2" xmlns:att="http://apply.grants.gov/system/Attachments-V1.0" xmlns:glob="http://apply.grants.gov/system/Global-V1.0" a:FormVersion="1.2"><a:ATT1><a:ATT1File><att:FileName>cert-form.pdf</att:FileName><att:MimeType>application/pdf</att:MimeType><att:FileLocation att:href="cert-form.pdf"/><glob:HashValue glob:hashAlgorithm="SHA-1">{sha1}</glob:HashValue></a:ATT1File></a:ATT1></a:AttachmentForm_1_2></grant:Forms></grant:GrantApplication>')
    v = await s2s.s2s_validate_package(xml)
    assert v["valid"], v
    env = s2s._environment(LIVE)
    r = await s2s.s2s_submit(xml, [{"content_id": "cert-form.pdf", "url": PDF_URL, "content_type": "application/pdf"}], confirm_environment="wrong")
    assert r["class"] == "configuration"
    r = await s2s.s2s_submit(xml, [{"content_id": "other.pdf", "url": PDF_URL}], confirm_environment=env)
    assert r["class"] == "configuration" and "not referenced" in r["error"]
    r = await s2s.s2s_submit(xml, [{"content_id": "cert-form.pdf", "url": PDF_URL, "content_type": "application/pdf"}], confirm_environment=env)
    assert r.get("tracking_number", "").startswith("GRANT"), r
    assert r["attachments"][0]["sha1_base64"] == sha1 and "warning" not in r["attachments"][0]
    tn = r["tracking_number"]
    info = await s2s.s2s_application_info(tn)
    assert info["status"] in s2s.STATUSES, info
    lst = await s2s.s2s_submissions(tracking_number=tn)
    assert lst["available"] == 1 and lst["submissions"][0]["tracking_number"] == tn
    assert (await s2s.s2s_application_info("GRANT00000000"))["class"] == "not_found"
