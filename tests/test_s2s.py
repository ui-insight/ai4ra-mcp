"""Offline checks for the s2s server: the credential bundle round trip, endpoint rules, the offline
package validator, the request check against the WSDL types, the MTOM message shape, the slimming
of the two detail records, and the error classes."""

import base64
import json
import os

import httpx
import pytest
from lxml import etree

from ai4ra_mcp.common import http as h
from ai4ra_mcp.servers.s2s import credentials, soap
from ai4ra_mcp.servers.s2s import server as s2s
from ai4ra_mcp.servers.s2s.contract import NS_ACE, NS_GCE, NS_GRANT, check_element, validate_application

CERT = "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----"
KEY = "-----BEGIN PRIVATE KEY-----\nMIIE\n-----END PRIVATE KEY-----"
ATTACHMENT_FORM = '<a:AttachmentForm_1_2 xmlns:a="http://apply.grants.gov/forms/AttachmentForm_1_2-V1.2" a:FormVersion="1.2"/>'


def app_xml(forms, opp="NSF-25-999", pkg="PKG00299901"):
    return (f'<grant:GrantApplication xmlns:grant="{NS_GRANT}"><grant:GrantSubmissionHeader><grant:OpportunityID>{opp}</grant:OpportunityID>'
            f'<grant:PackageID>{pkg}</grant:PackageID><grant:SubmissionTitle>t</grant:SubmissionTitle></grant:GrantSubmissionHeader><grant:Forms>{forms}</grant:Forms></grant:GrantApplication>')


def test_bundle_round_trip_base64url_and_plain_json():
    tok = base64.urlsafe_b64encode(json.dumps({"cert": CERT, "key": KEY}).encode()).decode().rstrip("=")
    b = credentials.from_token(tok)
    assert b.cert.startswith("-----BEGIN CERTIFICATE") and b.key.startswith("-----BEGIN PRIVATE KEY") and b.ca is None and b.source == "bearer"
    b2 = credentials.from_token(json.dumps({"cert": CERT, "key": KEY, "ca": CERT}))
    assert b2.ca and credentials.from_token(None) is None
    with pytest.raises(ValueError):
        credentials.from_token("pk_not_a_bundle")
    with pytest.raises(ValueError):
        credentials.from_token(json.dumps({"cert": "nope", "key": KEY}))


def test_bundle_from_env_files(tmp_path, monkeypatch):
    (tmp_path / "c.pem").write_text(CERT)
    (tmp_path / "k.pem").write_text(KEY)
    monkeypatch.setenv(credentials.CERT_FILE_ENV, str(tmp_path / "c.pem"))
    monkeypatch.setenv(credentials.KEY_FILE_ENV, str(tmp_path / "k.pem"))
    assert credentials.from_env().source == "environment"
    assert credentials.make_token(str(tmp_path / "c.pem"), str(tmp_path / "k.pem")) == credentials.make_token(str(tmp_path / "c.pem"), str(tmp_path / "k.pem"))


def test_endpoint_rules(monkeypatch):
    monkeypatch.setattr(s2s, "DEFAULT_ENDPOINT", None)
    with pytest.raises(s2s.S2SError) as e:
        s2s._endpoint("")
    assert e.value.cls == "configuration" and "trainingws" in e.value.message
    with pytest.raises(s2s.S2SError):
        s2s._endpoint("http://ws07.grants.gov" + s2s.SOAP_PATH)
    with pytest.raises(s2s.S2SError):
        s2s._endpoint("https://127.0.0.1:8443" + s2s.SOAP_PATH)   # not public, not the default
    assert s2s._environment(s2s.TRAINING) == "training" and s2s._environment(s2s.PRODUCTION) == "production" and s2s._is_production(s2s.PRODUCTION)
    monkeypatch.setattr(s2s, "DEFAULT_ENDPOINT", "https://grants-gov-s2s-mock:8443" + s2s.SOAP_PATH)
    assert s2s._endpoint("") == s2s.DEFAULT_ENDPOINT and s2s._environment(s2s.DEFAULT_ENDPOINT) == "mock"


def test_validate_application_offline():
    v = validate_application(app_xml(ATTACHMENT_FORM))
    assert not v["errors"] and v["header"]["OpportunityID"] == "NSF-25-999" and v["forms"] == ["AttachmentForm_1_2"]
    bad = validate_application(app_xml('<r:RR_SF424_5_0 xmlns:r="http://apply.grants.gov/forms/RR_SF424_5_0-V5.0" r:FormVersion="5.0"/>'))
    assert bad["errors"] and bad["errors"][0].startswith("RR_SF424_5_0:")
    unknown = validate_application(app_xml('<x:Unknown xmlns:x="urn:x"/>'))
    assert not unknown["errors"] and unknown["warnings"]
    assert validate_application("<nope/>")["errors"][0].startswith("Root element must be")
    assert validate_application("not xml")["errors"][0].startswith("GrantApplicationXML is not well-formed")
    with_att = app_xml('<a:AttachmentForm_1_2 xmlns:a="http://apply.grants.gov/forms/AttachmentForm_1_2-V1.2" xmlns:att="http://apply.grants.gov/system/Attachments-V1.0" xmlns:glob="http://apply.grants.gov/system/Global-V1.0" a:FormVersion="1.2"><a:ATT1><a:ATT1File><att:FileName>n.pdf</att:FileName><att:MimeType>application/pdf</att:MimeType><att:FileLocation att:href="n.pdf"/><glob:HashValue glob:hashAlgorithm="SHA-1">q83vAQ==</glob:HashValue></a:ATT1File></a:ATT1></a:AttachmentForm_1_2>')
    v = validate_application(with_att)
    assert not v["errors"], v["errors"]
    assert v["attachment_refs"] == [{"href": "n.pdf", "hash_value": "q83vAQ==", "hash_algorithm": "SHA-1"}]


def test_requests_are_checked_against_wsdl_types():
    req = soap.el("GetOpportunityListRequest")
    f = soap.sub(req, "OpportunityFilter", ns=NS_ACE)
    soap.sub(f, "FundingOpportunityNumber", "NSF-25-999", ns=NS_GCE)
    assert check_element(req) == []
    wrong = soap.el("GetOpportunityListRequest")
    f = soap.sub(wrong, "OpportunityFilter", ns=NS_ACE)
    soap.sub(f, "FundingOpportunityNumber", "NSF-25-999", ns=NS_ACE)
    assert check_element(wrong)
    sub = soap.el("SubmitApplicationRequest")
    soap.sub(sub, "GrantApplicationXML", "<x/>")
    att = soap.sub(sub, "Attachment", ns=NS_GCE)
    soap.sub(att, "FileContentId", "a.pdf", ns=NS_GCE)
    soap.xop_include(soap.sub(att, "FileDataHandler", ns=NS_GCE), "a.pdf")
    assert check_element(sub) == []   # xop:Include stands for resolved binary


def test_mtom_message_round_trips_through_the_parser():
    env = soap.envelope(soap.el("GetOpportunityListRequest"))
    body, ct = soap.mtom(env, [("a.pdf", b"%PDF-1.4 x", "application/pdf"), ("b.pdf", bytes(range(256)), "application/pdf")])
    assert ct.startswith('multipart/related; type="application/xop+xml"') and b"Content-ID: <a.pdf>" in body and bytes(range(256)) in body
    # our own parser reads an MTOM *response* the same way: the root part is the envelope
    el = soap.parse_response(ct, body)
    assert etree.QName(el).localname == "GetOpportunityListRequest"


def test_fault_and_error_classes():
    fault = (b'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><soap:Fault><faultcode>soap:Client</faultcode>'
             b'<faultstring>The AOR is not authorized to submit on behalf of this organization</faultstring><detail><message>armed</message></detail></soap:Fault></soap:Body></soap:Envelope>')
    with pytest.raises(soap.SoapFault) as e:
        soap.parse_response("text/xml", fault)
    assert s2s._report(e.value)["class"] == "certificate" and e.value.detail == "armed"
    assert s2s._report(soap.SoapFault("soap:Server", "Mock-armed SOAP fault", None))["class"] == "transport"
    assert s2s._report(soap.SoapFault("soap:Client", "GrantApplicationXML failed schema validation", "x"))["class"] == "rejected"
    assert s2s._report(soap.SoapFault("soap:Client", "No submission found for Grants.gov tracking number 'x'", None))["class"] == "not_found"
    assert s2s._report(httpx.ConnectError("[SSL: TLSV13_ALERT_CERTIFICATE_REQUIRED] ..."))["class"] == "certificate"
    assert s2s._report(httpx.ReadTimeout("t"))["class"] == "transport"
    # TLS 1.3: a refused client certificate arrives after the handshake as a dropped connection
    assert s2s._report(httpx.ReadError(""))["class"] == "certificate"
    assert s2s._report(httpx.RemoteProtocolError("Server disconnected without sending a response."))["class"] == "certificate"
    assert s2s._report(httpx.ReadError("connection reset by peer"))["class"] == "transport"
    assert s2s._report(s2s.S2SError("configuration", "no endpoint"))["class"] == "configuration"
    assert "do_not" in s2s._report(ValueError("x"))


def test_slimming():
    d = etree.fromstring(f'<ns2:OpportunityDetails xmlns:ns2="{NS_ACE}" xmlns:ns1="{NS_GCE}"><ns1:FundingOpportunityNumber>NSF-25-999</ns1:FundingOpportunityNumber>'
                         f'<ns1:CompetitionID>C1</ns1:CompetitionID><ns1:PackageID>P1</ns1:PackageID><ns2:CFDADetails><ns2:Number>47.070</ns2:Number><ns2:Title>CISE</ns2:Title></ns2:CFDADetails>'
                         f'<ns2:OpeningDate>2026-01-15</ns2:OpeningDate><ns2:ClosingDate>2026-12-31</ns2:ClosingDate><ns1:SchemaURL>https://x/y.xsd</ns1:SchemaURL><ns2:IsMultiProject>false</ns2:IsMultiProject></ns2:OpportunityDetails>')
    o = s2s._slim_opportunity(d)
    assert o["opportunity_number"] == "NSF-25-999" and o["package_id"] == "P1" and o["cfda"] == [{"number": "47.070", "title": "CISE"}] and o["multi_project"] is False
    s = etree.fromstring(f'<ns2:SubmissionDetails xmlns:ns2="{NS_ACE}" xmlns:ns1="{NS_GCE}"><ns1:GrantsGovTrackingNumber>GRANT12345678</ns1:GrantsGovTrackingNumber>'
                         f'<ns1:AgencyTrackingNumber>AGY-1</ns1:AgencyTrackingNumber><ns1:GrantsGovApplicationStatus>Validated</ns1:GrantsGovApplicationStatus>'
                         f'<ns2:ReceivedDateTime>2026-09-28T00:00:00+00:00</ns2:ReceivedDateTime></ns2:SubmissionDetails>')
    assert s2s._slim_submission(s)["status"] == "Validated" and s2s._slim_submission(s)["agency_tracking_number"] == "AGY-1"


async def test_tools_refuse_without_credential_or_endpoint(monkeypatch):
    monkeypatch.setattr(s2s, "DEFAULT_ENDPOINT", None)
    monkeypatch.delenv(credentials.CERT_FILE_ENV, raising=False)
    r = await s2s.s2s_application_info("GRANT1")
    assert r["class"] == "configuration" and "endpoint" in r["error"]
    r = await s2s.s2s_check(endpoint=s2s.TRAINING)
    assert r["ok"] is False and r["class"] == "configuration" and "credential" in r["error"]
    r = await s2s.s2s_opportunity()
    assert r["class"] == "configuration"
    v = await s2s.s2s_validate_package(app_xml(ATTACHMENT_FORM))
    assert v["valid"] is True


def test_index_says_what_is_on():
    import asyncio
    idx = asyncio.run(s2s.s2s_index())
    assert idx["writes"] == s2s.WRITES_ON and "s2s_check" in idx["workflow"][0] and idx["endpoints"]["training"] == s2s.TRAINING


def _self_signed(issuer_cn: str, issuer_o: str, client_auth: bool = True):
    from datetime import datetime, timedelta, timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(x509.oid.NameOID.COUNTRY_NAME, "US"), x509.NameAttribute(x509.oid.NameOID.ORGANIZATION_NAME, issuer_o), x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, issuer_cn)])
    now = datetime.now(timezone.utc)
    b = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(0xABC123)
         .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=100)))
    if client_auth:
        b = b.add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
    return b.sign(key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM).decode()


def test_describe_certificate_and_issuer_acceptance():
    pem = _self_signed("InCommon RSA Server CA 2", "Internet2")
    d = credentials.describe(pem)
    assert d["issuer"]["CN"] == "InCommon RSA Server CA 2" and d["serial_hex"] == "ABC123" and d["key"] == "RSA 2048" and d["client_auth_eku"] is True
    assert d["meets_grants_gov_minimums"] and 98 <= d["days_left"] <= 100 and not d["expired"]
    assert s2s.issuer_accepted(d["issuer"], s2s.TRAINING) is True and s2s.issuer_accepted(d["issuer"], s2s.PRODUCTION) is True
    assert s2s.issuer_accepted({"CN": "grants-gov-s2s-mock CA"}, s2s.TRAINING) is False
    assert s2s.issuer_accepted(d["issuer"], "https://grants-gov-s2s-mock:8443/x") is None
    v = s2s.certificate_verdict(pem, s2s.TRAINING)
    assert v["issuer_accepted_by_endpoint"] is True and "not registered" in v["issuer_note"]
    v = s2s.certificate_verdict(_self_signed("Some Corporate CA", "Acme", client_auth=False), s2s.PRODUCTION)
    assert v["issuer_accepted_by_endpoint"] is False and "NOT on the CA list" in v["issuer_note"] and v["client_auth_eku"] is None
    both = s2s.accepted_issuers(s2s.TRAINING), s2s.accepted_issuers(s2s.PRODUCTION)
    assert all(len(x) > 150 for x in both) and any(a.get("CN") == "InCommon RSA Server CA" for a in both[0])
