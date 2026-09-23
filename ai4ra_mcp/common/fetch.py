"""fetch_document: read a public web page or PDF as plain text.

Lets an MCP client hand the model a funding announcement, a policy page or a
PDF by URL instead of pasting it. Public http(s) only: hostnames that resolve
to private, loopback or link-local addresses are refused, redirects are
re-checked, downloads are capped, and the text comes back in pages so a long
solicitation can be read in several calls.
"""

from __future__ import annotations

import html
import ipaddress
import io
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urlsplit

import httpx

MAX_BYTES = 8 * 1024 * 1024      # refuse bodies larger than this
MAX_CHARS_CAP = 40_000           # hard cap on one page of text
TIMEOUT_S = 30.0
MAX_REDIRECTS = 5
from ai4ra_mcp.common.http import USER_AGENT


def _host_is_public(host: str) -> bool:
    """True when every address the host resolves to is a global unicast address."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            return False
    return True


def _check_url(url: str) -> str | None:
    """A reason the URL is refused, or None."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return "only http and https URLs are fetched"
    if not parts.hostname:
        return "the URL has no host"
    if parts.username or parts.password:
        return "URLs with credentials are refused"
    if not _host_is_public(parts.hostname):
        return f"{parts.hostname} does not resolve to a public address"
    return None


class _Text(HTMLParser):
    """Visible text of an HTML document: scripts, styles and nav dropped, block boundaries kept."""

    _SKIP = {"script", "style", "noscript", "template", "svg"}   # head keeps only <title>, since meta and link carry no text
    _BLOCK = {"p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article", "header", "footer",
              "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd", "blockquote", "pre", "hr", "nav", "aside", "main"}
    _CELL = {"td", "th"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        elif tag == "title" and not self._skip and not self.title:   # the document's title, not an SVG icon's
            self._in_title = True
        elif tag in self._BLOCK:
            self.parts.append("\n")
        elif tag in self._CELL:
            self.parts.append("\t")
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("#" * int(tag[1]) + " ")

    def handle_endtag(self, tag):
        if tag in self._SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if not self._skip:
            self.parts.append(data)


def html_to_text(raw: str) -> tuple[str, str]:
    """(title, text) for an HTML document."""
    p = _Text()
    p.feed(raw)
    p.close()
    text = "".join(p.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return html.unescape(p.title).strip(), text.strip()


def pdf_to_text(data: bytes) -> str:
    from pypdf import PdfReader  # imported here so the HTML path needs no pypdf

    reader = PdfReader(io.BytesIO(data))
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception:  # a broken page should not lose the rest
            t = ""
        pages.append(f"\n\n[page {i + 1}]\n{t.strip()}")
    return "".join(pages).strip()


# grants.gov opportunity pages are rendered by script, so the page itself carries no text; the same
# record is public through the grants.gov API, which is used instead when the URL names an opportunity.
_GRANTS_GOV_ID = re.compile(r"(?:/search-results-detail/|[?&]oppId=)(\d+)")
GRANTS_GOV_API = "https://api.grants.gov/v1/api/fetchOpportunity"
GRANTS_GOV_ATTACHMENT = "https://apply07.grants.gov/grantsws/rest/opportunity/att/download/{id}"


def _grants_gov_id(url: str) -> str | None:
    parts = urlsplit(url)
    if not parts.hostname or not parts.hostname.lower().endswith("grants.gov"):
        return None
    m = _GRANTS_GOV_ID.search(url)
    return m.group(1) if m else None


def _grants_gov_text(d: dict) -> tuple[str, str]:
    """(title, text) for a fetchOpportunity record: the header facts, the synopsis, then the attachments."""
    syn = d.get("synopsis") or {}
    agency = (syn.get("agencyDetails") or {}).get("agencyName") or d.get("owningAgencyCode") or ""
    top = (syn.get("topAgencyDetails") or {}).get("agencyName") or ""
    title = f"{d.get('opportunityNumber', '')}: {d.get('opportunityTitle', '')}".strip(": ")
    lines = [f"# {title}", ""]

    def fact(label, value):
        if value not in (None, "", [], "none"):
            lines.append(f"- {label}: {value}")

    fact("Agency", " / ".join(x for x in (top, agency) if x and x != top) or top or agency)
    fact("Opportunity number", d.get("opportunityNumber"))
    fact("Posted", syn.get("postingDate"))
    fact("Closes", syn.get("responseDate"))
    fact("Close date note", syn.get("responseDateDesc"))
    fact("Archive date", syn.get("archiveDate"))
    fact("Award ceiling", syn.get("awardCeiling"))
    fact("Award floor", syn.get("awardFloor"))
    fact("Estimated total program funding", syn.get("estimatedFunding"))
    fact("Expected number of awards", syn.get("numberOfAwards") or syn.get("expectedNumberOfAwards"))
    fact("Cost sharing required", "yes" if syn.get("costSharing") else "no")
    fact("Funding instruments", ", ".join(x.get("description", "") for x in syn.get("fundingInstruments") or []))
    fact("Category", ", ".join(x.get("description", "") for x in syn.get("fundingActivityCategories") or []))
    fact("Assistance listings", ", ".join(f"{x.get('cfdaNumber', '')} {x.get('programTitle', '')}".strip() for x in d.get("cfdas") or []))
    fact("Eligible applicants", "; ".join(x.get("description", "") for x in syn.get("applicantTypes") or []))
    fact("Last updated", syn.get("lastUpdatedDate"))
    fact("Latest change", syn.get("modComments"))
    if syn.get("agencyContactEmail"):
        fact("Contact", f"{(syn.get('agencyContactName') or '').replace(chr(10), ', ')} {syn.get('agencyContactEmail')}".strip())

    if syn.get("applicantEligibilityDesc"):
        lines += ["", "## Eligibility", html_to_text(syn["applicantEligibilityDesc"])[1]]
    if syn.get("synopsisDesc"):
        lines += ["", "## Synopsis", html_to_text(syn["synopsisDesc"])[1]]
    if syn.get("fundingDescLinkUrl"):
        lines += ["", f"Full announcement link: {syn['fundingDescLinkUrl']} ({syn.get('fundingDescLinkDesc') or ''})".rstrip(" ()")]

    atts = []
    for folder in d.get("synopsisAttachmentFolders") or []:
        for a in folder.get("synopsisAttachments") or []:
            if a.get("id"):
                atts.append(f"- {a.get('fileName', '')} ({folder.get('folderType', '')}; {a.get('mimeType', '')}): "
                            f"{GRANTS_GOV_ATTACHMENT.format(id=a['id'])}")
    if atts:
        lines += ["", "## Attachments (read the full announcement PDF with the fetch_document tool)"] + atts
    urls = [f"- {u.get('description', '')}: {u.get('docUrl', '')}" for u in d.get("synopsisDocumentURLs") or [] if u.get("docUrl")]
    if urls:
        lines += ["", "## Related links"] + urls
    return title, "\n".join(lines).strip()


async def _fetch_grants_gov(opp_id: str) -> tuple[str, str]:
    async with httpx.AsyncClient(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.post(GRANTS_GOV_API, json={"opportunityId": opp_id})
    resp.raise_for_status()
    body = resp.json()
    data = body.get("data") if isinstance(body, dict) else None
    if not data or body.get("errorcode"):
        raise ValueError(body.get("msg") or "grants.gov returned no opportunity")
    return _grants_gov_text(data)


class _Refused(Exception):
    def __init__(self, message: str, url: str):
        super().__init__(message)
        self.url = url


async def _get_following_redirects(url: str, verify: bool):
    """GET with each redirect target re-checked against the public-address rule. Returns (response, final url)."""
    async with httpx.AsyncClient(follow_redirects=False, timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, verify=verify) as client:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            resp = await client.get(current)
            if resp.is_redirect and resp.headers.get("location"):
                current = str(resp.next_request.url) if resp.next_request else resp.headers["location"]
                reason = _check_url(current)
                if reason:
                    raise _Refused(f"refused after redirect: {reason}", current)
                continue
            return resp, current
        raise _Refused("too many redirects", current)


async def fetch_document(url: str, offset: int = 0, max_chars: int = 12_000) -> dict:
    """Fetch a public web page or PDF and return its text from `offset`, at most `max_chars` characters."""
    url = (url or "").strip()
    reason = _check_url(url)
    if reason:
        return {"error": f"refused: {reason}", "url": url}
    max_chars = max(1_000, min(int(max_chars or 12_000), MAX_CHARS_CAP))
    offset = max(0, int(offset or 0))

    opp_id = _grants_gov_id(url)
    if opp_id:
        try:
            title, text = await _fetch_grants_gov(opp_id)
        except Exception as e:  # noqa: BLE001
            return {"error": f"grants.gov opportunity {opp_id} could not be read: {e}", "url": url}
        return _page(url, "grants.gov", title, text, offset, max_chars)

    current = url
    tls_unverified = False
    try:
        resp, current = await _get_following_redirects(url, verify=True)
    except httpx.ConnectError as e:
        if "CERTIFICATE_VERIFY_FAILED" not in str(e):
            return {"error": f"could not connect: {e}", "url": current}
        # The site's certificate chain does not verify against this server's trust store (a missing
        # intermediate, usually). Read it anyway for this public, read-only fetch, and say so in the result.
        try:
            resp, current = await _get_following_redirects(url, verify=False)
            tls_unverified = True
        except httpx.HTTPError as e2:
            return {"error": f"could not connect: {e2}", "url": current}
    except _Refused as e:
        return {"error": str(e), "url": e.url}
    except httpx.HTTPError as e:
        return {"error": f"could not fetch: {e}", "url": current}

    if resp.status_code == 404:
        return {"error": "HTTP 404: there is no page at that address. Do not guess another path; use an address the user gave or a tool returned, or fetch the site's home page.", "url": current}
    if resp.status_code >= 400:
        return {"error": f"HTTP {resp.status_code}", "url": current}
    body = resp.content
    if len(body) > MAX_BYTES:
        return {"error": f"document is larger than {MAX_BYTES // (1024 * 1024)} MB", "url": current}

    ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
    is_pdf = ctype == "application/pdf" or body[:5] == b"%PDF-" or current.lower().split("?")[0].endswith(".pdf")
    title = ""
    if is_pdf:
        try:
            text = pdf_to_text(body)
        except Exception as e:  # noqa: BLE001
            return {"error": f"the PDF could not be read: {e}", "url": current}
        kind = "pdf"
    elif ctype.startswith("text/html") or ctype in ("application/xhtml+xml", ""):
        title, text = html_to_text(resp.text)
        kind = "html"
    elif ctype.startswith("text/"):
        text = resp.text
        kind = "text"
    else:
        return {"error": f"unsupported content type {ctype or 'unknown'}; only HTML, PDF and plain text are read", "url": current}

    if not text:
        return {"error": "no readable text was found (an image-only PDF or a script-rendered page; for grants.gov, give the opportunity link, for NSF, the solicitation PDF)", "url": current, "kind": kind}
    # An application shell: a page whose HTML is nearly all scripts and holds only a few words (Esploro research
    # portals, many single-page apps). Say so rather than hand back the stub as if it were the page.
    if kind == "html" and len(text) < 300 and resp.text.count("<script") >= 3:
        return {"error": "this page is rendered by scripts in the browser; the fetch returned only its shell (" + text[:120].replace("\n", " ") + "). "
                         "The content cannot be read this way. Ask the user for the information, a PDF or a plain-HTML page, or use it only as a link.",
                "url": current, "kind": "html", "title": title, "script_rendered": True}
    out = _page(current, kind, title, text, offset, max_chars)
    if tls_unverified:
        out["tls_unverified"] = True
        out["note"] = "The site's certificate could not be verified, so this text was read without TLS verification; treat it as unconfirmed."
    return out


def _page(url: str, kind: str, title: str, text: str, offset: int, max_chars: int) -> dict:
    chunk = text[offset:offset + max_chars]
    out = {
        "url": url,
        "kind": kind,
        "title": title,
        "total_chars": len(text),
        "offset": offset,
        "returned_chars": len(chunk),
        "truncated": offset + len(chunk) < len(text),
        "text": chunk,
    }
    if out["truncated"]:
        out["next_offset"] = offset + len(chunk)
    return out


# ---- grants.gov search --------------------------------------------------------

GRANTS_GOV_SEARCH = "https://api.grants.gov/v1/api/search2"
GRANTS_GOV_PAGE = "https://www.grants.gov/search-results-detail/{id}"
_STATUSES = {"posted", "forecasted", "closed", "archived"}


async def grants_gov_search(keyword: str, statuses: str = "posted|forecasted", agencies: str = "",
                            categories: str = "", rows: int = 10, start: int = 0) -> dict:
    """Search grants.gov opportunities. Returns the hit count, the hits, and the agency facet for narrowing."""
    keyword = (keyword or "").strip()
    if not keyword:
        return {"error": "keyword is required"}
    wanted = [s.strip().lower() for s in (statuses or "posted|forecasted").replace(",", "|").split("|") if s.strip()]
    bad = [s for s in wanted if s not in _STATUSES]
    if bad:
        return {"error": f"unknown status {', '.join(bad)}; use posted, forecasted, closed or archived"}
    rows = max(1, min(int(rows or 10), 50))
    start = max(0, int(start or 0))
    payload = {"keyword": keyword, "oppStatuses": "|".join(wanted), "rows": rows, "startRecordNum": start}
    if agencies.strip():
        payload["agencies"] = "|".join(a.strip().upper() for a in agencies.replace(",", "|").split("|") if a.strip())
    if categories.strip():
        payload["fundingCategories"] = "|".join(c.strip().upper() for c in categories.replace(",", "|").split("|") if c.strip())
    async with httpx.AsyncClient(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.post(GRANTS_GOV_SEARCH, json=payload)
    resp.raise_for_status()
    body = resp.json()
    data = body.get("data") if isinstance(body, dict) else None
    if not data or body.get("errorcode"):
        return {"error": (body or {}).get("msg") or "grants.gov returned no data"}
    hits = []
    for h in data.get("oppHits") or []:
        hits.append({
            "id": h.get("id"),
            "number": h.get("number"),
            "title": h.get("title"),
            "agency": h.get("agency") or h.get("agencyCode"),
            "agency_code": h.get("agencyCode"),
            "status": h.get("oppStatus"),
            "open_date": h.get("openDate"),
            "close_date": h.get("closeDate"),
            "assistance_listings": h.get("cfdaList") or [],
            "link": GRANTS_GOV_PAGE.format(id=h.get("id")),
        })
    out = {
        "keyword": keyword,
        "statuses": "|".join(wanted),
        "hit_count": data.get("hitCount"),
        "start": start,
        "returned": len(hits),
        "hits": hits,
        "agencies": [{"code": a.get("value"), "name": a.get("label"), "count": a.get("count")}
                     for a in (data.get("agencies") or [])[:25]],
        "note": "Pass a hit's id to grants_gov_opportunity for the full record, its synopsis and its attachment links; pass an attachment link to fetch_document on the general server to read it.",
    }
    if data.get("suggestion"):
        out["suggestion"] = data["suggestion"]
    if isinstance(data.get("hitCount"), int) and start + len(hits) < data["hitCount"]:
        out["next_start"] = start + len(hits)
    return out
