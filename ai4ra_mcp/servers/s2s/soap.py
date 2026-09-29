"""SOAP 1.1 over HTTP for the Applicant S2S service, from the client side: build an envelope, wrap
it and its attachments as MTOM/XOP, read a plain or MTOM response, and turn a soap:Fault into an
exception that carries what Grants.gov said."""

from __future__ import annotations

import re
import uuid
from email.parser import BytesParser
from email.policy import default as email_policy

from lxml import etree

from .contract import NS_ACE, NS_GCE, NS_WS, NS_XOP

NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NSMAP = {"soap": NS_SOAP, "ns": NS_WS, "ns2": NS_ACE, "ns1": NS_GCE, "xop": NS_XOP}
CONTENT_ID = re.compile(r"^[A-Za-z0-9._@-]+$")


class SoapFault(Exception):
    def __init__(self, code: str, string: str, detail: str | None):
        super().__init__(string)
        self.code, self.string, self.detail = code, string, detail


def el(tag: str, text: str | None = None, ns: str = NS_WS) -> etree._Element:
    e = etree.Element(f"{{{ns}}}{tag}", nsmap=NSMAP)
    if text is not None:
        e.text = str(text)
    return e


def sub(parent: etree._Element, tag: str, text=None, ns: str = NS_WS) -> etree._Element:
    e = etree.SubElement(parent, f"{{{ns}}}{tag}")
    if text is not None:
        e.text = str(text)
    return e


def envelope(body_child: etree._Element) -> bytes:
    env = etree.Element(f"{{{NS_SOAP}}}Envelope", nsmap=NSMAP)
    etree.SubElement(env, f"{{{NS_SOAP}}}Body").append(body_child)
    return etree.tostring(env, xml_declaration=True, encoding="UTF-8")


def mtom(envelope_bytes: bytes, attachments: list[tuple[str, bytes, str]]) -> tuple[bytes, str]:
    """(body, content-type) for a multipart/related MTOM message: the envelope as the root part and
    each (content_id, data, mime_type) as a binary part the envelope refers to with cid:."""
    boundary = "MIMEBoundary_" + uuid.uuid4().hex
    parts = [
        f"--{boundary}\r\nContent-Type: application/xop+xml; charset=UTF-8; type=\"text/xml\"\r\n"
        f"Content-Transfer-Encoding: binary\r\nContent-ID: <root.message@ai4ra-mcp>\r\n\r\n".encode() + envelope_bytes
    ]
    for cid, data, mime in attachments:
        parts.append(f"\r\n--{boundary}\r\nContent-Type: {mime}\r\nContent-Transfer-Encoding: binary\r\nContent-ID: <{cid}>\r\n\r\n".encode() + data)
    body = b"".join(parts) + f"\r\n--{boundary}--\r\n".encode()
    ct = f'multipart/related; type="application/xop+xml"; start="<root.message@ai4ra-mcp>"; start-info="text/xml"; boundary="{boundary}"'
    return body, ct


def xop_include(parent: etree._Element, cid: str) -> None:
    etree.SubElement(parent, f"{{{NS_XOP}}}Include").set("href", f"cid:{cid}")


def parse_response(content_type: str, body: bytes) -> etree._Element:
    """The first child of soap:Body, or a SoapFault. MTOM responses are unwrapped to their root part."""
    xml = body
    if content_type.lower().startswith("multipart/"):
        msg = BytesParser(policy=email_policy).parsebytes(b"Content-Type: " + content_type.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
        parts = list(msg.iter_parts())
        if not parts:
            raise ValueError("MTOM response has no parts")
        start = (msg.get_param("start") or "").strip("<>")
        root = next((p for p in parts if (p.get("Content-ID") or "").strip("<>") == start), parts[0])
        xml = root.get_payload(decode=True) or b""
    try:
        env = etree.fromstring(xml)
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"response is not a SOAP envelope: {exc}; first bytes: {body[:120]!r}") from exc
    fault = env.find(f".//{{{NS_SOAP}}}Fault")
    if fault is not None:
        d = fault.find("detail")
        detail = None
        if d is not None:
            detail = "".join(d.itertext()).strip() or None
        raise SoapFault(fault.findtext("faultcode") or "", fault.findtext("faultstring") or "", detail)
    b = env.find(f"{{{NS_SOAP}}}Body")
    if b is None or len(b) == 0:
        raise ValueError("SOAP response has an empty Body")
    return b[0]


def text(parent: etree._Element, local: str, ns: str | None = None) -> str | None:
    """Text of the first descendant named `local` (in `ns`, or any namespace), stripped."""
    for child in parent.iter():
        if child is parent:
            continue
        q = etree.QName(child)
        if q.localname == local and (ns is None or q.namespace == ns):
            return (child.text or "").strip()
    return None
