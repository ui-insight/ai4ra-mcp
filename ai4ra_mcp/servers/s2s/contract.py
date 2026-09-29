"""The vendored Grants.gov Applicant S2S V2.0 contract, compiled: the WSDL's types for checking
requests before they leave and responses as they arrive, and the form XSDs for checking a
GrantApplication before it is submitted. Everything resolves to contract/ on disk; nothing is
fetched. Copied from AI4RA/grants-gov-s2s-mock, which validates the same way on the other end."""

from __future__ import annotations

import copy
from pathlib import Path

from lxml import etree

CONTRACT = Path(__file__).resolve().parent / "contract"
NS_XS = "http://www.w3.org/2001/XMLSchema"
NS_WS = "http://apply.grants.gov/services/ApplicantWebServices-V2.0"
NS_ACE = "http://apply.grants.gov/system/ApplicantCommonElements-V1.0"
NS_GCE = "http://apply.grants.gov/system/GrantsCommonElements-V1.0"
NS_GRANT = "http://apply.grants.gov/system/MetaGrantApplication"
NS_ATT = "http://apply.grants.gov/system/Attachments-V1.0"
NS_GLOB = "http://apply.grants.gov/system/Global-V1.0"
NS_XOP = "http://www.w3.org/2004/08/xop/include"
REMOTE_PREFIX = "https://apply07.grants.gov/apply/"
_WS_URL = "contract://ApplicantWebServices-V2.0.xsd"
_SYSTEM_IMPORTS = [
    ("http://apply.grants.gov/system/GrantsCommonTypes-V1.0", "GrantsCommonTypes-V1.0.xsd"),
    ("http://apply.grants.gov/system/GrantsCommonElements-V1.0", "GrantsCommonElements-V1.0.xsd"),
    ("http://apply.grants.gov/system/ApplicantCommonElements-V1.0", "ApplicantCommonElements-V1.0.xsd"),
]


class _LocalResolver(etree.Resolver):
    def __init__(self, ws_schema_xml: bytes | None = None):
        self._ws = ws_schema_xml

    def resolve(self, url, pubid, context):
        if url == _WS_URL and self._ws:
            return self.resolve_string(self._ws, context)
        if url and url.startswith(REMOTE_PREFIX):
            kind, _, name = url.removeprefix(REMOTE_PREFIX).partition("/schemas/")
            local = CONTRACT / kind / name
            if local.exists():
                return self.resolve_filename(str(local), context)
        return None


_types: etree.XMLSchema | None = None
_forms: dict[str, etree.XMLSchema] | None = None


def wsdl_types() -> etree.XMLSchema:
    """The ApplicantWebServices-V2.0 schema lifted from the WSDL, with the three system schemas it
    imports, compiled once. Covers every request and response element of the service."""
    global _types
    if _types is None:
        wsdl = etree.parse(str(CONTRACT / "ApplicantWebServices-V2.0.wsdl"))
        ws = next(s for s in wsdl.getroot().iter(f"{{{NS_XS}}}schema") if s.get("targetNamespace") == NS_WS)
        parser = etree.XMLParser()
        parser.resolvers.add(_LocalResolver(etree.tostring(ws)))
        imports = "\n".join(f'<xs:import namespace="{ns}" schemaLocation="{(CONTRACT / "system" / f).as_uri()}"/>' for ns, f in _SYSTEM_IMPORTS)
        wrapper = f'<xs:schema xmlns:xs="{NS_XS}">{imports}<xs:import namespace="{NS_WS}" schemaLocation="{_WS_URL}"/></xs:schema>'
        _types = etree.XMLSchema(etree.fromstring(wrapper.encode(), parser))
    return _types


def check_element(el: etree._Element) -> list[str]:
    """Schema errors for a request or response element, empty when valid. An xop:Include stands
    for resolved binary content and is treated as such."""
    doc = copy.deepcopy(el)
    for inc in list(doc.iter(f"{{{NS_XOP}}}Include")):
        parent = inc.getparent()
        parent.remove(inc)
        parent.text = ""
    schema = wsdl_types()
    if schema.validate(doc):
        return []
    return [f"line {e.line}: {e.message}" for e in schema.error_log]


def form_schemas() -> dict[str, etree.XMLSchema]:
    global _forms
    if _forms is None:
        parser = etree.XMLParser()
        parser.resolvers.add(_LocalResolver())
        found = {}
        for xsd in sorted((CONTRACT / "forms").glob("*.xsd")):
            doc = etree.parse(str(xsd), parser)
            ns = doc.getroot().get("targetNamespace")
            if ns:
                found[ns] = etree.XMLSchema(doc)
        _forms = found
    return _forms


def validate_application(xml: str) -> dict:
    """Check a GrantApplication the way Grants.gov will: the root, the submission header, and each
    form under grant:Forms against its vendored XSD. Returns errors (Grants.gov would reject),
    warnings (a form this copy has no schema for), the header fields, the form names, and every
    attachment reference (href and the HashValue beside it) the forms make."""
    out = {"errors": [], "warnings": [], "header": {}, "forms": [], "attachment_refs": []}
    try:
        root = etree.fromstring(xml.encode() if isinstance(xml, str) else xml)
    except etree.XMLSyntaxError as exc:
        out["errors"].append(f"GrantApplicationXML is not well-formed: {exc}")
        return out
    if etree.QName(root) != etree.QName(NS_GRANT, "GrantApplication"):
        out["errors"].append(f"Root element must be {{{NS_GRANT}}}GrantApplication, got {etree.QName(root).text}")
        return out
    header = root.find(f"{{{NS_GRANT}}}GrantSubmissionHeader")
    if header is None:
        out["errors"].append("GrantApplication has no grant:GrantSubmissionHeader")
    else:
        for k in ("OpportunityID", "PackageID", "SubmissionTitle", "CompetitionID", "CFDANumber", "SchemaVersion"):
            v = header.findtext(f"{{{NS_GRANT}}}{k}")
            if v is not None:
                out["header"][k] = v.strip()
    forms = root.find(f"{{{NS_GRANT}}}Forms")
    if forms is None or len(forms) == 0:
        out["errors"].append("GrantApplication has no grant:Forms")
        return out
    schemas = form_schemas()
    for form in forms:
        q = etree.QName(form)
        out["forms"].append(q.localname)
        schema = schemas.get(q.namespace or "")
        if schema is None:
            out["warnings"].append(f"{q.localname}: no vendored schema for namespace {q.namespace!r}; not validated here (Grants.gov will)")
            continue
        if not schema.validate(form):
            out["errors"].extend(f"{q.localname}: line {e.line}: {e.message}" for e in schema.error_log)
    for loc in root.iter(f"{{{NS_ATT}}}FileLocation"):
        href = loc.get(f"{{{NS_ATT}}}href") or loc.get("href")
        parent = loc.getparent()
        # glob:HashValue is base64Binary (the SHA-1 digest, base64) with a required glob:hashAlgorithm
        hv = parent.find(f"{{{NS_GLOB}}}HashValue") if parent is not None else None
        out["attachment_refs"].append({"href": href, "hash_value": (hv.text or "").strip() if hv is not None else None,
                                       "hash_algorithm": (hv.get(f"{{{NS_GLOB}}}hashAlgorithm") or hv.get("hashAlgorithm")) if hv is not None else None})
    return out
