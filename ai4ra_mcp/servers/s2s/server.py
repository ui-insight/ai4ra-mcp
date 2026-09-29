"""s2s: the Grants.gov Applicant System-to-System web services, with the person's own certificate.

Upstream: any endpoint that speaks the Applicant S2S V2.0 WSDL over mutual TLS. Grants.gov runs two,
training (trainingws.grants.gov) and production (ws07.grants.gov); a deployment may point the default
at a mock (AI4RA/grants-gov-s2s-mock) so people can practise submitting without a registered
certificate. The endpoint is an argument on every tool, so the same tools reach all three.

The credential is the caller's: a client certificate and private key, sent as the bearer token in
the form credentials.py describes, used for that request and nowhere else. A deployment may hold a
fallback pair in AI4RA_MCP_S2S_CERT_FILE / AI4RA_MCP_S2S_KEY_FILE for clients that cannot send one.

Submitting is a write. It is off unless the deployment sets AI4RA_MCP_S2S_WRITES=1, and the
production endpoint is refused unless AI4RA_MCP_S2S_PRODUCTION=1 as well. Every request is checked
against the WSDL types before it leaves, every GrantApplication against the vendored form schemas,
and every response against the WSDL types as it arrives, so what the model sees is the contract.
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from lxml import etree
from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.fetch import _check_url, _get_following_redirects
from ai4ra_mcp.common.http import HEADERS, request_key
from ai4ra_mcp.common.skills import register_prompts

from . import credentials, soap
from .contract import NS_ACE, NS_GCE, NS_WS, check_element, validate_application

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
_WRITES = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}

SOAP_PATH = "/grantsws-applicant/services/v2/ApplicantWebServicesSoapPort"
TRAINING = "https://trainingws.grants.gov" + SOAP_PATH
PRODUCTION = "https://ws07.grants.gov" + SOAP_PATH
ENDPOINT_ENV = "AI4RA_MCP_S2S_ENDPOINT"
WRITES_ENV = "AI4RA_MCP_S2S_WRITES"
PRODUCTION_ENV = "AI4RA_MCP_S2S_PRODUCTION"
DEFAULT_ENDPOINT = os.environ.get(ENDPOINT_ENV, "").strip() or None
DEFAULT_CA_FILE = os.environ.get(credentials.CA_FILE_ENV, "").strip() or None
WRITES_ON = os.environ.get(WRITES_ENV, "").strip().lower() in ("1", "true", "yes", "on")
PRODUCTION_ON = os.environ.get(PRODUCTION_ENV, "").strip().lower() in ("1", "true", "yes", "on")
KEY_HOW = ("Your S2S credential is the client certificate Grants.gov registered to your organization and its private key, "
           "as a bearer token: run `python -m ai4ra_mcp.servers.s2s.credentials cert.pem key.pem` and paste what it prints. "
           "Against the mock, a certificate minted by the mock's scripts/make-client-cert.sh works the same way.")
MAX_ATTACHMENT_BYTES = 100 * 1024 * 1024
STATUSES = ["Receiving", "Received", "Processing", "Validated", "Rejected with Errors", "Download Preparation", "Received by Agency", "Agency Tracking Number Assigned"]

mcp = MCPServer(
    "s2s",
    instructions="Grants.gov Applicant System-to-System with the person's own certificate: an opportunity's package (competition, package id, forms), a GrantApplication checked against the schemas"
    + (", its submission with attachments" if WRITES_ON else "")
    + ", the list and status of submissions. The endpoint is an argument; the deployment's default"
    + (f" is {DEFAULT_ENDPOINT}" if DEFAULT_ENDPOINT else " is not set, so pass one")
    + ". Read s2s_index first.",
)


# ---- errors ----

class S2SError(Exception):
    """An error with the class OpenERA's transport layer (#1353) distinguishes, so a model reports the right thing."""

    def __init__(self, cls: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.cls, self.message, self.detail = cls, message, detail


def _report(e: Exception) -> dict:
    if isinstance(e, S2SError):
        out = {"error": e.message, "class": e.cls}
        if e.detail:
            out["detail"] = e.detail
    elif isinstance(e, soap.SoapFault):
        low = (e.string + " " + (e.detail or "")).lower()
        if "aor" in low and "authoriz" in low:
            cls = "certificate"
        elif "no submission found" in low or "not found" in low:
            cls = "not_found"
        elif e.code.endswith("Client") or "validat" in low:
            cls = "rejected"
        else:
            cls = "transport" if "mock-armed" in low else "rejected"
        out = {"error": f"Grants.gov returned a SOAP fault: {e.string}", "class": cls, "faultcode": e.code}
        if e.detail:
            out["detail"] = e.detail
    elif isinstance(e, httpx.TimeoutException):
        out = {"error": f"the endpoint did not answer in time: {e}", "class": "transport"}
    elif isinstance(e, httpx.ConnectError):
        s = str(e)
        cls = "certificate" if any(w in s.lower() for w in ("ssl", "tls", "certificate", "handshake")) else "transport"
        out = {"error": f"could not connect: {s}", "class": cls}
    elif (isinstance(e, httpx.RemoteProtocolError) and "disconnected" in str(e).lower()) or (isinstance(e, httpx.ReadError) and not str(e).strip()):
        # Under TLS 1.3 a server that rejects the client certificate does so after the handshake, so
        # the client sees the connection dropped before any response. That is what a refused
        # certificate looks like from here; a server crash mid-request would look the same.
        out = {"error": f"the server dropped the connection without a response ({e}); with mutual TLS this is what a refused client certificate looks like", "class": "certificate"}
    elif isinstance(e, httpx.HTTPError):
        out = {"error": f"transport failure: {e}", "class": "transport"}
    elif isinstance(e, ValueError):
        out = {"error": str(e), "class": "configuration"}
    else:
        out = {"error": f"{type(e).__name__}: {e}", "class": "transport"}
    out["do_not"] = "Do not guess at what Grants.gov would have said. Report the class and the message, and stop there."
    return out


# ---- endpoint and credential ----

def _endpoint(given: str) -> str:
    url = (given or "").strip() or DEFAULT_ENDPOINT
    if not url:
        raise S2SError("configuration", f"no endpoint: pass one, or the deployment sets {ENDPOINT_ENV}. Grants.gov's are {TRAINING} (training) and {PRODUCTION} (production).")
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise S2SError("configuration", "the S2S endpoint must be https: Grants.gov authenticates the certificate in the TLS handshake")
    if url != DEFAULT_ENDPOINT:
        reason = _check_url(url)
        if reason:
            raise S2SError("configuration", f"endpoint refused: {reason}")
    return url


def _is_production(url: str) -> bool:
    return urlsplit(url).hostname == urlsplit(PRODUCTION).hostname


def _environment(url: str) -> str:
    host = urlsplit(url).hostname or ""
    if url == DEFAULT_ENDPOINT and host not in (urlsplit(TRAINING).hostname, urlsplit(PRODUCTION).hostname):
        return "mock"
    return "production" if _is_production(url) else "training" if host == urlsplit(TRAINING).hostname else "other"


def _bundle() -> credentials.Bundle:
    try:
        b = credentials.from_token(request_key.get()) or credentials.from_env()
    except ValueError as e:
        raise S2SError("configuration", str(e)) from e
    if b is None:
        raise S2SError("configuration", f"no S2S credential on this request: send your own as a bearer token (in the Office pane, paste it into this server's i dialog). {KEY_HOW}")
    return b


async def _call(endpoint: str, request: etree._Element, attachments: list[tuple[str, bytes, str]] | None = None, timeout: float = 60.0) -> etree._Element:
    problems = check_element(request)
    if problems:
        raise S2SError("invalid_request", f"{etree.QName(request).localname} does not validate against the WSDL types", "\n".join(problems[:10]))
    env = soap.envelope(request)
    if attachments:
        body, ct = soap.mtom(env, attachments)
    else:
        body, ct = env, "text/xml; charset=UTF-8"
    bundle = _bundle()
    ctx = bundle.ssl_context(DEFAULT_CA_FILE if endpoint == DEFAULT_ENDPOINT else None)
    async with httpx.AsyncClient(verify=ctx, timeout=httpx.Timeout(30.0, read=timeout), headers={**HEADERS, "SOAPAction": '""'}) as client:
        resp = await client.post(endpoint, content=body, headers={"content-type": ct})
    if resp.status_code >= 400 and not resp.headers.get("content-type", "").lower().startswith(("text/xml", "application/soap", "application/xml", "multipart/")):
        raise S2SError("transport", f"HTTP {resp.status_code} from {urlsplit(endpoint).hostname}", resp.text[:300])
    el = soap.parse_response(resp.headers.get("content-type", ""), resp.content)
    problems = check_element(el)
    if problems:
        raise S2SError("transport", f"the response does not match the WSDL types (is {urlsplit(endpoint).hostname} really the Applicant S2S V2.0 service?)", "\n".join(problems[:5]))
    return el


# ---- slimming ----

def _slim_opportunity(d: etree._Element) -> dict:
    return {
        "opportunity_number": soap.text(d, "FundingOpportunityNumber", NS_GCE), "title": soap.text(d, "FundingOpportunityTitle", NS_GCE),
        "competition_id": soap.text(d, "CompetitionID", NS_GCE), "competition_title": soap.text(d, "CompetitionTitle", NS_GCE),
        "package_id": soap.text(d, "PackageID", NS_GCE),
        "cfda": [{"number": c.findtext(f"{{{NS_ACE}}}Number"), "title": c.findtext(f"{{{NS_ACE}}}Title")} for c in d.findall(f"{{{NS_ACE}}}CFDADetails")],
        "opening_date": soap.text(d, "OpeningDate", NS_ACE), "closing_date": soap.text(d, "ClosingDate", NS_ACE),
        "agency": soap.text(d, "OfferingAgency", NS_GCE), "agency_contact": soap.text(d, "AgencyContactInfo", NS_GCE),
        "schema_url": soap.text(d, "SchemaURL", NS_GCE), "instructions_url": soap.text(d, "InstructionsURL", NS_GCE),
        "multi_project": soap.text(d, "IsMultiProject", NS_ACE) == "true",
    }


def _slim_submission(d: etree._Element) -> dict:
    return {
        "tracking_number": soap.text(d, "GrantsGovTrackingNumber", NS_GCE), "agency_tracking_number": soap.text(d, "AgencyTrackingNumber", NS_GCE),
        "status": soap.text(d, "GrantsGovApplicationStatus", NS_GCE), "received_at": soap.text(d, "ReceivedDateTime", NS_ACE),
        "status_at": soap.text(d, "StatusDateTime", NS_ACE), "opportunity_number": soap.text(d, "FundingOpportunityNumber", NS_GCE),
        "title": soap.text(d, "SubmissionTitle", NS_GCE), "package_id": soap.text(d, "PackageID", NS_GCE),
    }


def _write_tool(name: str):
    if WRITES_ON:
        return mcp.tool(name=name, annotations=_WRITES)
    return lambda fn: fn


# ---- tools ----

@mcp.tool(name="s2s_index", annotations=_READ_ONLY)
async def s2s_index() -> dict:
    """What this server offers and how to use it: the tools in order, the endpoints, how the credential travels, the error classes and the status values."""
    return {
        "what": "The Grants.gov Applicant System-to-System (S2S) web services, V2.0, over mutual TLS with the caller's own certificate. Four operations: an opportunity's package, submit an application, list submissions, one submission's status.",
        "workflow": [
            "s2s_check(endpoint, opportunity_number): prove the connection and the certificate before anything else, and learn which error class a failure is.",
            "s2s_opportunity(opportunity_number | cfda | competition_id | package_id): the package facts a submission needs: competition id, package id, the forms and their schema versions, open and close dates.",
            "s2s_validate_package(application_xml): check a GrantApplication against the form schemas offline, and see which attachments it references. No network.",
            ("s2s_submit(application_xml, attachments, endpoint): SubmitApplication with MTOM attachments fetched from the URLs given. Returns the Grants.gov tracking number." if WRITES_ON else "s2s_submit is off in this deployment (AI4RA_MCP_S2S_WRITES is not set)."),
            "s2s_submissions(filters): GetSubmissionList by tracking number, opportunity number, package id, title or status.",
            "s2s_application_info(tracking_number): GetApplicationInfo: the status detail and any agency notes.",
        ],
        "endpoints": {"default": DEFAULT_ENDPOINT or "none set: pass endpoint on every call", "default_environment": _environment(DEFAULT_ENDPOINT) if DEFAULT_ENDPOINT else None,
                      "training": TRAINING, "production": PRODUCTION,
                      "note": "The same tools reach all three; only the endpoint and the credential change. " + ("Production is enabled here." if PRODUCTION_ON else "Production submissions are refused in this deployment (AI4RA_MCP_S2S_PRODUCTION is not set).")},
        "credential": {"how": KEY_HOW, "on_this_request": bool(request_key.get()), "fallback_configured": credentials.from_env() is not None if os.environ.get(credentials.CERT_FILE_ENV) else False},
        "writes": WRITES_ON, "production": PRODUCTION_ON,
        "error_classes": {"configuration": "no endpoint or credential, or a refused URL: fix the setup", "certificate": "the TLS handshake was refused or the AOR is not authorized for this certificate: the registration, not the package",
                          "transport": "timeout, connection failure, or a fault that is not about the package: retry later or report", "rejected": "Grants.gov refused the request or the package, with its own message verbatim: fix the package",
                          "not_found": "no such opportunity package or tracking number", "invalid_request": "the request this server built did not match the WSDL types: a bug or a bad argument"},
        "statuses": STATUSES,
        "citation": "Every figure here comes from the endpoint named in the result, at the time of the call. Say which environment (mock, training, production) it was.",
    }


@mcp.tool(name="s2s_check", annotations=_READ_ONLY)
async def s2s_check(endpoint: str = "", opportunity_number: str = "") -> dict:
    """Connectivity check (Grants.gov test case 2.1): fetch the WSDL, then GetOpportunityList for `opportunity_number` if given. Reports the environment and, on failure, which error class it is."""
    try:
        url = _endpoint(endpoint)
        out = {"endpoint": url, "environment": _environment(url), "credential_source": _bundle().source}
        bundle = _bundle()
        ctx = bundle.ssl_context(DEFAULT_CA_FILE if url == DEFAULT_ENDPOINT else None)
        async with httpx.AsyncClient(verify=ctx, timeout=30.0, headers=HEADERS) as client:
            r = await client.get(url + "?wsdl")
        out["wsdl"] = {"http_status": r.status_code, "is_applicant_v2": "ApplicantWebServices-V2.0" in r.text, "location": (r.text.split('location="', 1)[1].split('"', 1)[0] if 'location="' in r.text else None)}
        if opportunity_number:
            req = soap.el("GetOpportunityListRequest")
            f = soap.sub(req, "OpportunityFilter", ns=NS_ACE)
            soap.sub(f, "FundingOpportunityNumber", opportunity_number, ns=NS_GCE)
            resp = await _call(url, req)
            found = [_slim_opportunity(d) for d in resp.findall(f"{{{NS_ACE}}}OpportunityDetails")]
            out["lookup"] = {"opportunity_number": opportunity_number, "packages": len(found), "packages_found": found}
        out["ok"] = True
        return out
    except Exception as e:  # noqa: BLE001
        return {**_report(e), "endpoint": (endpoint or DEFAULT_ENDPOINT), "ok": False}


@mcp.tool(name="s2s_opportunity", annotations=_READ_ONLY)
async def s2s_opportunity(opportunity_number: str = "", cfda: str = "", competition_id: str = "", package_id: str = "", endpoint: str = "") -> dict:
    """GetOpportunityList: the open packages for an opportunity, by opportunity number, CFDA, competition id or package id (at least one). Each package's competition id, package id, forms with schema versions, and dates."""
    if not any((opportunity_number, cfda, competition_id, package_id)):
        return {"error": "give at least one of opportunity_number, cfda, competition_id or package_id", "class": "configuration"}
    try:
        url = _endpoint(endpoint)
        req = soap.el("GetOpportunityListRequest")
        if package_id:
            soap.sub(req, "PackageID", package_id)
        if any((opportunity_number, cfda, competition_id)):
            f = soap.sub(req, "OpportunityFilter", ns=NS_ACE)
            if opportunity_number:
                soap.sub(f, "FundingOpportunityNumber", opportunity_number, ns=NS_GCE)
            if cfda:
                soap.sub(f, "CFDANumber", cfda, ns=NS_GCE)
            if competition_id:
                soap.sub(f, "CompetitionID", competition_id, ns=NS_GCE)
        resp = await _call(url, req)
        found = [_slim_opportunity(d) for d in resp.findall(f"{{{NS_ACE}}}OpportunityDetails")]
        for o in found:
            o["forms"] = await _forms_from_schema(o.get("schema_url"))
        return {"endpoint": url, "environment": _environment(url), "count": len(found), "packages": found,
                **({} if found else {"note": "no open package matched: for a real opportunity check the number on grants.gov; the mock only knows its seeded ones", "class": "not_found"})}
    except Exception as e:  # noqa: BLE001
        return _report(e)


async def _forms_from_schema(schema_url: str | None) -> list[str] | None:
    """The form names a package accepts, read from its package schema's imports (public URL only)."""
    if not schema_url:
        return None
    try:
        if schema_url.startswith(DEFAULT_ENDPOINT.rsplit(SOAP_PATH, 1)[0] if DEFAULT_ENDPOINT else "\0"):
            bundle = _bundle()
            async with httpx.AsyncClient(verify=bundle.ssl_context(DEFAULT_CA_FILE), timeout=30.0, headers=HEADERS) as client:
                r = await client.get(schema_url)
        else:
            if _check_url(schema_url):
                return None
            r, _ = await _get_following_redirects(schema_url, verify=True)
        if r.status_code != 200:
            return None
        import re
        return re.findall(r'namespace="http://apply.grants.gov/forms/([^"]+)"', r.text) or None
    except Exception:  # noqa: BLE001
        return None


@mcp.tool(name="s2s_validate_package", annotations=_READ_ONLY)
async def s2s_validate_package(application_xml: str) -> dict:
    """Check a GrantApplication XML document offline the way Grants.gov will: the root and header, then each form under grant:Forms against its vendored schema. Returns errors, warnings, the header fields, the forms, and the attachments the forms reference (href and hash). No network."""
    v = validate_application(application_xml)
    v["valid"] = not v["errors"]
    v["note"] = ("Grants.gov will reject this as it stands; fix every error." if v["errors"] else
                 "Schema-valid. Agency business rules are not checked here; Grants.gov applies those after receipt and reports them through the submission's status.")
    return v


@_write_tool("s2s_submit")
async def s2s_submit(application_xml: str, attachments: list[dict] | None = None, endpoint: str = "", confirm_environment: str = "") -> dict:
    """SubmitApplication: send a schema-valid GrantApplication with its attachments. Each attachment is {"content_id": the href the forms use, "url": a public URL to fetch it from} (or "base64" for a small file, and optional "content_type"). `confirm_environment` must equal the endpoint's environment name (mock, training, production) as a guard against submitting to the wrong one. Returns the Grants.gov tracking number and receipt time."""
    try:
        url = _endpoint(endpoint)
        envname = _environment(url)
        if _is_production(url) and not PRODUCTION_ON:
            raise S2SError("configuration", f"production submissions are refused in this deployment ({PRODUCTION_ENV} is not set)")
        if (confirm_environment or "").strip().lower() != envname:
            raise S2SError("configuration", f"this endpoint is the {envname} environment: pass confirm_environment=\"{envname}\" to submit there")
        v = validate_application(application_xml)
        if v["errors"]:
            return {"error": "the package does not validate; nothing was sent", "class": "rejected", "errors": v["errors"][:25], "warnings": v["warnings"]}
        refs = {r["href"]: r for r in v["attachment_refs"] if r.get("href")}
        parts, manifest = [], []
        for a in attachments or []:
            cid = str(a.get("content_id") or "").strip()
            if not soap.CONTENT_ID.match(cid):
                raise S2SError("configuration", f"attachment content_id {cid!r} must be letters, digits, . _ @ - only (it is the MIME Content-ID and the href the forms use)")
            if cid not in refs:
                raise S2SError("configuration", f"attachment {cid!r} is not referenced by any att:FileLocation href in the forms; the forms reference {sorted(refs) or 'nothing'}")
            data = await _attachment_bytes(a)
            mime = str(a.get("content_type") or "application/octet-stream")
            digest = hashlib.sha1(data).digest()
            sha1_b64, sha1_hex = base64.b64encode(digest).decode(), digest.hex()
            note = None
            hv = refs[cid].get("hash_value")
            if hv and hv not in (sha1_b64, sha1_hex, sha1_hex.upper()):
                note = f"the form's glob:HashValue ({hv}) is not the SHA-1 of the fetched bytes (base64 {sha1_b64}); Grants.gov may reject the attachment"
            parts.append((cid, data, mime))
            manifest.append({"content_id": cid, "bytes": len(data), "content_type": mime, "sha1_base64": sha1_b64, "sha1_hex": sha1_hex, **({"warning": note} if note else {})})
        missing = sorted(set(refs) - {p[0] for p in parts})
        if missing:
            raise S2SError("configuration", f"the forms reference attachments that were not supplied: {missing}")
        req = soap.el("SubmitApplicationRequest")
        soap.sub(req, "GrantApplicationXML", application_xml)
        for cid, _, _ in parts:
            att = soap.sub(req, "Attachment", ns=NS_GCE)
            soap.sub(att, "FileContentId", cid, ns=NS_GCE)
            soap.xop_include(soap.sub(att, "FileDataHandler", ns=NS_GCE), cid)
        resp = await _call(url, req, parts, timeout=300.0)
        return {"endpoint": url, "environment": envname, "tracking_number": soap.text(resp, "GrantsGovTrackingNumber", NS_WS), "received_at": soap.text(resp, "ReceivedDateTime", NS_WS),
                "header": v["header"], "forms": v["forms"], "attachments": manifest, "warnings": v["warnings"],
                "next": "Poll s2s_application_info with the tracking number; Received is receipt, not acceptance. Rejected with Errors carries Grants.gov's reasons in the agency notes."}
    except Exception as e:  # noqa: BLE001
        return _report(e)


async def _attachment_bytes(a: dict) -> bytes:
    if a.get("base64"):
        data = base64.b64decode(a["base64"])
    else:
        u = str(a.get("url") or "").strip()
        reason = _check_url(u) if u else "no url or base64"
        if reason:
            raise S2SError("configuration", f"attachment {a.get('content_id')!r}: {reason}")
        r, final = await _get_following_redirects(u, verify=True)
        if r.status_code != 200:
            raise S2SError("configuration", f"attachment {a.get('content_id')!r}: HTTP {r.status_code} from {final}")
        data = r.content
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise S2SError("configuration", f"attachment {a.get('content_id')!r} is {len(data)} bytes; the cap is {MAX_ATTACHMENT_BYTES}")
    if not data:
        raise S2SError("configuration", f"attachment {a.get('content_id')!r} is empty")
    return data


@mcp.tool(name="s2s_submissions", annotations=_READ_ONLY)
async def s2s_submissions(tracking_number: str = "", opportunity_number: str = "", package_id: str = "", title: str = "", status: str = "", endpoint: str = "") -> dict:
    """GetSubmissionList (Grants.gov test case 2.3): the organization's submissions, filtered by any of tracking number, opportunity number, package id, submission title or status (the five filter types the schema allows; filters are ANDed)."""
    try:
        url = _endpoint(endpoint)
        req = soap.el("GetSubmissionListRequest")
        for t, v in (("GrantsGovTrackingNumber", tracking_number), ("FundingOpportunityNumber", opportunity_number), ("PackageID", package_id), ("SubmissionTitle", title), ("Status", status)):
            if v:
                f = soap.sub(req, "SubmissionFilter", ns=NS_ACE)
                soap.sub(f, "Type", t, ns=NS_ACE)
                soap.sub(f, "Value", v, ns=NS_ACE)
        resp = await _call(url, req)
        subs = [_slim_submission(d) for d in resp.findall(f"{{{NS_ACE}}}SubmissionDetails")]
        return {"endpoint": url, "environment": _environment(url), "available": int(soap.text(resp, "AvailableApplicationNumber", NS_WS) or 0), "submissions": subs}
    except Exception as e:  # noqa: BLE001
        return _report(e)


@mcp.tool(name="s2s_application_info", annotations=_READ_ONLY)
async def s2s_application_info(tracking_number: str, endpoint: str = "") -> dict:
    """GetApplicationInfo: one submission's current status detail and any agency notes, by Grants.gov tracking number."""
    try:
        url = _endpoint(endpoint)
        req = soap.el("GetApplicationInfoRequest")
        soap.sub(req, "GrantsGovTrackingNumber", (tracking_number or "").strip())
        resp = await _call(url, req)
        return {"endpoint": url, "environment": _environment(url), "tracking_number": soap.text(resp, "GrantsGovTrackingNumber", NS_WS),
                "status": soap.text(resp, "StatusDetail", NS_WS), "agency_notes": soap.text(resp, "AgencyNotes", NS_WS)}
    except Exception as e:  # noqa: BLE001
        return _report(e)


register_prompts(mcp, Path(__file__).parent / "skills")
