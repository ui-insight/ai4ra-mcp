#!/usr/bin/env python3
"""
eCFR MCP Server - Access the Electronic Code of Federal Regulations
Provides tools to search, retrieve, and analyze federal regulations from the eCFR API.
Designed for higher education research administration and compliance professionals,
with a primary focus on Uniform Guidance (2 CFR Part 200) and related research regulations.
"""

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from ai4ra_mcp.common import text as _text
from ai4ra_mcp.common.http import HEADERS as _UA_HEADERS
from pydantic import Field
from typing import Annotated, Optional, List, Dict, Any
import asyncio
import difflib
import html
import httpx
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime

# Initialize the MCP server
mcp = MCPServer("ecfr", instructions="Federal regulation from the eCFR. Read the ecfr_regulatory_index tool first; search with ecfr_search limited to a title and part, then read a section with ecfr_get_regulation; omit date for the current text, or give any earlier date for the text in force that day; always give title explicitly.")

# Constants
BASE_URL = "https://www.ecfr.gov/api"
ECFR_SITE = "https://www.ecfr.gov"
TIMEOUT = 30.0
HEADERS = {"Accept": "application/json, application/xml, */*", **_UA_HEADERS}
MAX_RESPONSE_BYTES = 1 * 1024 * 1024  # 1MB hard limit
SOFT_RESPONSE_BYTES = 800_000         # warn at 800KB
DEFAULT_SEARCH_RESULTS = 5
MAX_SEARCH_RESULTS = 25
MAX_DIFF_LINES = 100
DEFAULT_STRUCTURE_DEPTH = 2
CURRENT_TTL = 3600.0                  # seconds the titles list is kept; the eCFR adds a day at most once a day

# =============================================================================
# RESOURCE CACHE — built on first access, memoized for process lifetime
# =============================================================================
_resource_cache: Optional[Dict[str, Any]] = None

# Module-level HTTP client for connection reuse
_http_client: Optional[httpx.AsyncClient] = None

# The eCFR's titles list, which says the latest day it holds: (monotonic time read, the list)
_titles_cache: Optional[tuple] = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True)
    return _http_client


# =============================================================================
# HTTP HELPERS
# =============================================================================

async def api_get(
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    max_retries: int = 2,
) -> dict | str:
    """GET request to the eCFR API with exponential backoff."""
    url = f"{BASE_URL}/{endpoint}"
    client = _get_http_client()
    for attempt in range(1 + max_retries):
        try:
            response = await client.get(url, params=params, headers=HEADERS)
            response.raise_for_status()
            if endpoint.endswith(".xml"):
                return response.text
            return response.json()
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code in (429,) or 500 <= code < 600:
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                if code == 429:
                    raise ToolError("Rate limit exceeded. Wait before retrying.")
                raise ToolError(f"Server error {code} for {endpoint} after {max_retries} retries")
            said = _upstream_reason(e.response)
            if code == 404:
                raise ToolError(f"Not found: {endpoint}. Check that the title, part, section, and date are valid.{said}")
            if code == 406:
                raise ToolError(f"406 Not Acceptable — endpoint must end in .json or .xml: {endpoint}")
            raise ToolError(f"API error {code} for {endpoint}.{said}")
        except httpx.TimeoutException:
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)
                continue
            raise ToolError(f"Request timed out for {endpoint} after {max_retries} retries.")


def _upstream_reason(response: httpx.Response) -> str:
    """What the eCFR said about a refused request (its `error` or `errors`), to end an error message; empty when it said nothing."""
    try:
        body = response.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    reason = body.get("error") or body.get("errors")
    if not reason:
        return ""
    return f" The eCFR said: {reason if isinstance(reason, str) else json.dumps(reason, ensure_ascii=False)}"


def _build_params(**kwargs) -> Dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}


# =============================================================================
# RESPONSE HELPERS
# =============================================================================

def _make_error(message: str, **extra) -> Dict[str, Any]:
    error = {"message": message}
    error.update({k: v for k, v in extra.items() if v is not None})
    return error


def _add_warning(data: Dict[str, Any], message: str) -> None:
    data.setdefault("warnings", []).append(message)


def _make_citation(
    *,
    title: Optional[int] = None,
    part: Optional[str] = None,
    section: Optional[str] = None,
    appendix: Optional[str] = None,
) -> Optional[str]:
    if title is None:
        return None
    if section:
        return f"{title} CFR § {section}"
    if appendix:   # the eCFR names one in full, "Appendix III to Part 200"
        return f"{title} CFR {appendix}" if appendix.lower().startswith("appendix") else f"{title} CFR Appendix {appendix}"
    if part:
        return f"{title} CFR Part {part}"
    return f"{title} CFR"


def _make_source_url(
    *,
    title: Optional[int] = None,
    date: Optional[str] = None,
    part: Optional[str] = None,
    section: Optional[str] = None,
) -> Optional[str]:
    if title is None:
        return None
    if section:
        return f"{ECFR_SITE}/current/title-{title}/section-{section}"
    if part:
        return f"{ECFR_SITE}/current/title-{title}/part-{part}"
    if date:
        return f"{ECFR_SITE}/on/{date}/title-{title}"
    return f"{ECFR_SITE}/current/title-{title}"


def _add_canonical_fields(
    data: Dict[str, Any],
    *,
    title: Optional[int] = None,
    part: Optional[str] = None,
    section: Optional[str] = None,
    appendix: Optional[str] = None,
    date: Optional[str] = None,
) -> Dict[str, Any]:
    data["citation"] = _make_citation(title=title, part=part, section=section, appendix=appendix)
    data["title"] = title
    data["part"] = part
    data["section"] = section
    data["date"] = date
    data["source_url"] = _make_source_url(title=title, date=date, part=part, section=section)
    return data


def _finalize_response(data: Dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    if len(payload.encode("utf-8")) <= MAX_RESPONSE_BYTES:
        return payload
    fallback = {
        "error": _make_error("Response exceeds 1MB limit."),
        "hint": "Narrow the request: add section=, subpart=, or lower depth/per_page.",
    }
    return json.dumps(fallback, ensure_ascii=False, indent=2)


def _validate_date_str(value: Optional[str], field_name: str) -> None:
    if value is None:
        return
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as e:
        raise ToolError(f"{field_name} must be YYYY-MM-DD") from e


# =============================================================================
# THE CURRENT DATE — the latest day the eCFR holds, read from the eCFR
# =============================================================================

async def _current_date(title: Optional[int] = None) -> str:
    """The latest day the eCFR holds: the title's up_to_date_as_of, or the whole eCFR's (meta.date) with no title.
    The eCFR runs a day or more behind the calendar and refuses a later date, so this is read from its titles
    list, never taken from the clock."""
    global _titles_cache
    now = time.monotonic()
    if _titles_cache is None or now - _titles_cache[0] > CURRENT_TTL:
        _titles_cache = (now, await api_get("versioner/v1/titles.json"))
    data = _titles_cache[1]
    latest = (data.get("meta") or {}).get("date")
    if title is not None:
        for t in data.get("titles", []):
            if t.get("number") == title and t.get("up_to_date_as_of"):
                latest = t["up_to_date_as_of"]
    if not latest:
        raise ToolError("The eCFR's titles list did not say the latest day it holds; give date explicitly.")
    return latest


async def _resolve_date(value: Optional[str], field_name: str, title: Optional[int] = None) -> str:
    """The date to send: the latest day the eCFR holds when none is given, else the given date once it is well
    formed and not past that day."""
    latest = await _current_date(title)
    if not value:
        return latest
    _validate_date_str(value, field_name)
    if value > latest:
        where = f" for Title {title}" if title is not None else ""
        raise ToolError(f"{field_name} {value} is past the latest day the eCFR holds{where} ({latest}). "
                        f"Omit {field_name} for the current text, or give {latest} or an earlier date.")
    return value


# =============================================================================
# TITLE AUTO-RESOLUTION
# =============================================================================

async def _resolve_title(section: str = None, part: str = None) -> dict | list | None:
    query = section or part
    if not query:
        return None
    try:
        data = await api_get("search/v1/results.json", {"query": query, "per_page": 10})
        results = data.get("results", [])
    except Exception:
        return None

    seen_titles: Dict[int, dict] = {}
    for result in results:
        hierarchy = result.get("hierarchy", {})
        try:
            title_number = int(hierarchy.get("title"))
        except (TypeError, ValueError):
            continue
        h_section = (hierarchy.get("section") or "").strip()
        h_part = (hierarchy.get("part") or "").strip()
        if section and h_section == section:
            seen_titles.setdefault(title_number, hierarchy)
        elif part and h_part == part:
            seen_titles.setdefault(title_number, hierarchy)

    if not seen_titles:
        return None
    if len(seen_titles) == 1:
        return next(iter(seen_titles.values()))
    return list(seen_titles.values())


# =============================================================================
# XML → PLAIN TEXT
# =============================================================================

_LABELS = re.compile(r"(\([A-Za-z0-9]+\)\s*)+")   # a paragraph's own label or labels: (a), (1), (a)(1)
_ROMAN = re.compile(r"m{0,3}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})")


def _xml_to_text(xml_str: str) -> str:
    return _xml_to_text_and_outline(xml_str)[0]


def _xml_to_text_and_outline(xml_str: str) -> tuple[str, List[tuple]]:
    """The eCFR's XML as plain text, and the text's own outline: each subheading as (offset, heading, end), the
    character offset it starts at and the offset its part ends at, which is where the next subheading of the
    same level or a higher one begins. The subheadings are the ones the regulation carries: a paragraph's italic
    lead-in, an appendix's headings, each section's head when there are several. A text with none has no
    outline. It is read from the text fetched, so the outline of an earlier version is that version's."""
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return xml_str, []

    parts: List[str] = []
    marks: List[tuple] = []   # (index in parts, level, heading, label): a section's head 0, an appendix's headings 1 to 3, a paragraph 4 and deeper
    last_letter = [""]        # the last (a), (b), ... seen, to tell the letter (i) that follows (h) from the numeral (i)

    def _depth(text: str) -> int:
        """How deep a paragraph sits by its own label, as the CFR nests them: (a) 1, (1) 2, (i) 3, (A) 4; none 0."""
        m = _LABELS.match(text)
        depth = 0
        for label in re.findall(r"\(([A-Za-z0-9]+)\)", m.group(0)) if m else []:
            if label.isdigit():
                depth = 2
            elif label.isupper():
                depth = 4
            elif len(label) == 1 and (label == "a" or (last_letter[0] and ord(label) == ord(last_letter[0]) + 1)):
                depth, last_letter[0] = 1, label
            elif _ROMAN.fullmatch(label):
                depth = 3
            else:
                depth, last_letter[0] = 1, label
        return depth

    def _inner_text(elem: ET.Element) -> str:
        return re.sub(r"\s+", " ", "".join(elem.itertext())).strip()

    def _paragraph_prefix(elem: ET.Element) -> str:
        for key in ("N", "n", "label"):
            value = elem.attrib.get(key)
            if value:
                return value.strip()
        for child in elem:
            if child.tag in ("E", "ENUM"):
                text = _inner_text(child)
                if text:
                    return text.strip()
        return ""

    def _lead_in(elem: ET.Element) -> str:
        """A paragraph's italic lead-in with its label, "(a) General." or "Modified Total Direct Cost (MTDC)": the
        paragraph opens with it, nothing before it but the label."""
        children = list(elem)
        if not children or children[0].tag != "I":
            return ""
        before = (elem.text or "").strip()
        if before and not _LABELS.fullmatch(before):
            return ""
        lead = _inner_text(children[0])
        return f"{before} {lead}".strip() if 1 < len(lead) <= 120 else ""

    def _process_table(table_elem: ET.Element) -> str:
        rows = []
        for row in table_elem.iter():
            if row.tag in ("ROW", "TR"):
                cells = [_inner_text(c) for c in row if c.tag in ("ENT", "TD", "TH")]
                if cells:
                    rows.append("| " + " | ".join(cells) + " |")
        if rows:
            if len(rows) > 1:
                col_count = rows[0].count("|") - 1
                rows.insert(1, "| " + " | ".join(["---"] * col_count) + " |")
            return "\n".join(rows)
        return ""

    def _walk(elem: ET.Element):
        tag = elem.tag
        if tag == "SECTNO":
            text = _inner_text(elem)
            if text:
                parts.append(f"\n{'=' * 60}")
                parts.append(f"§ {text}")
            return
        if tag in ("SUBJECT", "HEAD"):
            text = _inner_text(elem)
            if text:
                marks.append((len(parts), 0, text, ""))
                parts.append(text)
                parts.append("=" * 60)
            return
        if tag == "HD" or re.fullmatch(r"HD\d", tag):
            text = _inner_text(elem)
            if text:
                number = re.match(r"([A-Za-z0-9]+)\.(?= |$)", text)   # "B." of "B. Identification ...", "1." under it
                marks.append((len(parts), int(tag[2:] or 1), text, f".{number.group(1)}" if number else f" {text}"))
                parts.append(f"\n--- {text} ---")
            return
        if tag in ("TABLE", "GPOTABLE"):
            table_text = _process_table(elem)
            if table_text:
                parts.append(f"\n{table_text}\n")
            return
        if tag in ("P", "FP"):
            text = _inner_text(elem)
            if text:
                depth = _depth(text)
                lead = _lead_in(elem)
                if lead:
                    own = _LABELS.match(lead)   # "(a)" of "(a) General."; a defined term has none and is cited by name
                    marks.append((len(parts), 4 + depth, lead, re.sub(r"\s+", "", own.group(0)) if own else f" {lead.rstrip('.')}"))
                prefix = _paragraph_prefix(elem)
                parts.append(f"{prefix} {text}" if prefix and not text.startswith(prefix) else text)
            return
        if tag in ("AUTH", "SOURCE"):
            text = _inner_text(elem)
            if text:
                parts.append(f"[{tag}] {text}")
            return
        if elem.text and elem.text.strip():
            parts.append(re.sub(r"\s+", " ", elem.text).strip())
        for child in elem:
            _walk(child)
            if child.tail and child.tail.strip():
                parts.append(re.sub(r"\s+", " ", child.tail).strip())

    _walk(root)

    cleaned: List[str] = []
    starts: Dict[int, int] = {}   # index in parts -> the character offset its text starts at
    length = 0
    seen_blank = False
    for i, p in enumerate(parts):
        v = p.strip()
        if not v:
            if not seen_blank:
                cleaned.append("")
                length += 2 if len(cleaned) > 1 else 0
                seen_blank = True
        else:
            length += 2 if cleaned else 0
            starts[i] = length
            cleaned.append(v)
            length += len(v)
            seen_blank = False

    text = "\n\n".join(cleaned)
    heads = [m for m in marks if m[1] == 0]
    entries = [m for m in marks if m[1] > 0]
    if len(heads) > 1:
        entries = sorted(entries + heads)
    return text, _text.with_ends([(starts[i], level, heading, label) for i, level, heading, label in entries], len(text))


# =============================================================================
# MISC HELPERS
# =============================================================================

def _prune_tree(node: dict, max_depth: int, current_depth: int = 1) -> dict:
    if not isinstance(node, dict):
        return node
    result = {k: v for k, v in node.items() if k != "children"}
    children = node.get("children", [])
    if children:
        result["child_count"] = len(children)
        if current_depth >= max_depth:
            result["truncated_children_count"] = len(children)
        else:
            result["children"] = [
                _prune_tree(child, max_depth, current_depth + 1) for child in children
            ]
    return result


def _plain(marked: Optional[str]) -> str:
    """The eCFR's search text without its highlight markup and entities."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", marked or "")).split())


def _slim_search_result(result: dict, include_excerpts: bool, versions: bool = False) -> dict:
    """One hit as what a caller needs to choose it and read it: the citation, the heading of the section or
    appendix, what to pass to ecfr_get_regulation, and the link. The eCFR's own record repeats the title, chapter
    and part headings in every hit and came to about 780 characters; this is about a fifth of that (#16, #22)."""
    hierarchy = result.get("hierarchy", {})
    headings = result.get("headings", {})
    title = int(hierarchy["title"]) if hierarchy.get("title") not in (None, "") else None
    part, section, appendix = hierarchy.get("part"), hierarchy.get("section"), hierarchy.get("appendix")
    slim = {
        "citation": _make_citation(title=title, part=part, section=section, appendix=appendix),
        "heading": _plain(headings.get("section") or headings.get("appendix") or headings.get("subpart") or headings.get("part")),
        "title": title,
        "part": part,
    }
    if section:
        slim["section"] = section
    elif appendix:
        slim["appendix"] = appendix
    elif hierarchy.get("subpart"):
        slim["subpart"] = hierarchy["subpart"]
    slim["source_url"] = _make_source_url(title=title, part=part, section=section)
    if versions:   # a search of every version: which one this is
        slim["starts_on"], slim["ends_on"] = result.get("starts_on"), result.get("ends_on")
    if include_excerpts:
        slim["full_text_excerpt"] = _plain(result.get("full_text_excerpt"))
    return slim


# =============================================================================
# STARTUP RESOURCE
# =============================================================================

async def _build_resource() -> Dict[str, Any]:
    grants_titles = {2, 7, 20, 29, 34, 42, 45, 49}
    title_2_versions = await api_get("versioner/v1/versions/title-2.json", params={"part": "200"})
    agencies_data = await api_get("admin/v1/agencies.json")

    agencies = []
    for agency in agencies_data.get("agencies", []):
        refs = agency.get("cfr_references", [])
        if {ref.get("title") for ref in refs} & grants_titles:
            agencies.append({
                "slug": agency.get("slug"),
                "name": agency.get("name"),
                "short_name": agency.get("short_name"),
                "cfr_references": refs,
            })
        for child in agency.get("children", []):
            child_refs = child.get("cfr_references", [])
            if {ref.get("title") for ref in child_refs} & grants_titles:
                agencies.append({
                    "slug": child.get("slug"),
                    "name": child.get("name"),
                    "short_name": child.get("short_name"),
                    "parent_slug": agency.get("slug"),
                    "cfr_references": child_refs,
                })

    meta = title_2_versions.get("meta", {})
    content_versions = title_2_versions.get("content_versions", [])
    starter_citations = []
    for item in content_versions:
        if not item.get("identifier") or item.get("type") != "section":
            continue
        starter_citations.append({
            "citation": f"2 CFR § {item['identifier']}",
            "identifier": item["identifier"],
            "name": item.get("name"),
            "part": item.get("part"),
            "subpart": item.get("subpart"),
            "date": item.get("date"),
            "source_url": _make_source_url(title=2, part=item.get("part"), section=item["identifier"]),
        })
        if len(starter_citations) >= 15:
            break

    latest_date = meta.get("latest_amendment_date") or meta.get("latest_issue_date")
    return {
        "generated_from": "live ecfr api",
        "uniform_guidance": {
            "citation": "2 CFR Part 200",
            "title": 2,
            "part": "200",
            "latest_amendment_date": latest_date,
            "source_url": _make_source_url(title=2, part="200"),
            "starter_citations": starter_citations,
        },
        "grants_relevant_agencies": agencies,
        "usage_notes": [
            "Omit date for the current text: every tool that takes a date uses the latest day the eCFR holds (current_as_of) when none is given.",
            "Any date on or before current_as_of returns the text in force that day. The calendar's today is usually a day or more past current_as_of and is refused.",
            "ecfr_get_title_versions is for history (when a section changed, and the dates of its versions). It is not needed before a fetch.",
            "Use ecfr_search for topic/concept discovery, limited to a title and part (Uniform Guidance: title=2, part='200'). Results include title+part+section for follow-up calls.",
            "Always provide title= explicitly; part numbers are NOT unique across titles (e.g. Part 46 exists in Title 45 AND other titles).",
            "Prefer section-level over part-level requests — part-level fetches can be very large.",
            f"latest_amendment_date ({latest_date}) is when Title 2 Part 200 last changed, not a date a fetch needs.",
        ],
    }


async def _get_resource() -> Dict[str, Any]:
    global _resource_cache
    if _resource_cache is None:
        _resource_cache = await _build_resource()
    return _resource_cache


# =============================================================================
# MCP RESOURCE
# =============================================================================

@mcp.resource("ecfr://regulatory-index")
async def regulatory_index() -> str:
    """Compact API-derived metadata for Uniform Guidance and research administration."""
    return await ecfr_regulatory_index()


@mcp.tool(name="ecfr_regulatory_index", annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
async def ecfr_regulatory_index() -> str:
    """
    Compact API-derived metadata for Uniform Guidance and research administration.
    READ THIS BEFORE CALLING TOOLS. Contains:
      uniform_guidance — live Title 2 Part 200 metadata and latest_amendment_date
      starter_citations — section-level starting points for 2 CFR Part 200
      grants_relevant_agencies — agency slugs for search filtering
      usage_notes — key rules for valid tool calls
      current_as_of — the latest day the eCFR holds, which a tool uses when no date is given
    """
    data = {**await _get_resource(), "current_as_of": await _current_date()}
    return _finalize_response(data)


# =============================================================================
# MCP TOOLS — parameters are flat/unwrapped so agents see the full schema
# =============================================================================

_READ_ONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


@mcp.tool(name="ecfr_get_title_versions", annotations=_READ_ONLY_ANNOTATIONS)
async def ecfr_get_title_versions(
    title: Annotated[int, Field(description="CFR title number (1–50)", ge=1, le=50)],
    part: Annotated[Optional[str], Field(default=None, description="Narrow to a specific part (e.g. '200' for Uniform Guidance, '46' for Common Rule)")] = None,
    section: Annotated[Optional[str], Field(default=None, description="Narrow to a specific section (e.g. '200.474'). Requires part.")] = None,
    limit: Annotated[int, Field(default=25, description="Max versions to return. Default 25 is sufficient for most use cases.", ge=1, le=200)] = 25,
    issue_date_on: Annotated[Optional[str], Field(default=None, description="Content added on this date (YYYY-MM-DD)")] = None,
    issue_date_lte: Annotated[Optional[str], Field(default=None, description="Content added on or before (YYYY-MM-DD)")] = None,
    issue_date_gte: Annotated[Optional[str], Field(default=None, description="Content added on or after (YYYY-MM-DD)")] = None,
    subtitle: Annotated[Optional[str], Field(default=None, description="Uppercase letter, e.g. 'A'")] = None,
    chapter: Annotated[Optional[str], Field(default=None, description="Roman numeral, e.g. 'I'")] = None,
    subchapter: Annotated[Optional[str], Field(default=None, description="Requires chapter. Uppercase letter.")] = None,
    subpart: Annotated[Optional[str], Field(default=None, description="Requires part. Uppercase letter.")] = None,
    appendix: Annotated[Optional[str], Field(default=None, description="Requires subtitle, chapter, or part.")] = None,
) -> str:
    """Get the amendment/version history for a CFR title: when a part or section changed.

    For history, not a step before a fetch: ecfr_get_regulation with no date returns the current text.
    Use part= and section= filters to narrow to a specific regulation.
    Each returned version has a "date" field, the day that version began. To read a version, pass its
    date (or any later day before the next version began) as date= to ecfr_get_regulation; to compare
    two, pass their dates to ecfr_compare_regulations.

    Example: ecfr_get_title_versions(title=2, part="200", section="200.474")
    """
    _validate_date_str(issue_date_on, "issue_date_on")
    _validate_date_str(issue_date_lte, "issue_date_lte")
    _validate_date_str(issue_date_gte, "issue_date_gte")
    if subchapter and not chapter:
        return _finalize_response({"error": _make_error("subchapter requires chapter")})
    if subpart and not part:
        return _finalize_response({"error": _make_error("subpart requires part")})
    if section and not part:
        return _finalize_response({"error": _make_error("section requires part")})
    if appendix and not (subtitle or chapter or part):
        return _finalize_response({"error": _make_error("appendix requires subtitle, chapter, or part")})

    query_params = _build_params(
        subtitle=subtitle,
        chapter=chapter,
        subchapter=subchapter,
        part=part,
        subpart=subpart,
        section=section,
        appendix=appendix,
    )
    if issue_date_on:
        query_params["issue_date[on]"] = issue_date_on
    if issue_date_lte:
        query_params["issue_date[lte]"] = issue_date_lte
    if issue_date_gte:
        query_params["issue_date[gte]"] = issue_date_gte
    data = await api_get(
        f"versioner/v1/versions/title-{title}.json",
        params=query_params or None,
    )
    versions = data.get("content_versions", [])
    total = len(versions)
    data["content_versions"] = versions[:limit]
    _add_canonical_fields(data, title=title, part=part, section=section, appendix=appendix,
                          date=issue_date_on or issue_date_lte or issue_date_gte)
    if total > limit:
        _add_warning(data, f"Truncated: {total} versions available, returned {limit}. "
                           f"Use date or hierarchy filters to narrow results.")
    return _finalize_response(data)


@mcp.tool(name="ecfr_get_regulation", annotations=_READ_ONLY_ANNOTATIONS)
async def ecfr_get_regulation(
    date: Annotated[Optional[str], Field(default=None, description="The day whose text is wanted (YYYY-MM-DD). Omit for the current text: the latest day the eCFR holds. Any earlier date returns the text in force that day; no version lookup is needed first. A date past the latest day the eCFR holds, which is usually a day or more behind the calendar, is refused.")] = None,
    title: Annotated[Optional[int], Field(default=None, description="CFR title number (1–50). Provide explicitly for unambiguous results. If omitted, resolved from section/part via search — but ambiguous parts (e.g. Part 46, Part 50) will return an error requiring you to specify title.", ge=1, le=50)] = None,
    part: Annotated[Optional[str], Field(default=None, description="Part number, e.g. '200', '46'")] = None,
    section: Annotated[Optional[str], Field(default=None, description="Section number, e.g. '200.474', '46.116'. Requires part. Prefer this over part-only.")] = None,
    subpart: Annotated[Optional[str], Field(default=None, description="Requires part. E.g. 'A', 'B'")] = None,
    subtitle: Annotated[Optional[str], Field(default=None, description="Uppercase letter")] = None,
    chapter: Annotated[Optional[str], Field(default=None, description="Roman numeral, e.g. 'I'")] = None,
    subchapter: Annotated[Optional[str], Field(default=None, description="Requires chapter.")] = None,
    appendix: Annotated[Optional[str], Field(default=None, description="Requires subtitle, chapter, or part.")] = None,
    text_only: Annotated[bool, Field(default=True, description="True (default): returns clean paragraph text — sufficient for policy analysis. False: returns raw XML, whole — only needed for structural parsing.")] = True,
    offset: Annotated[int, Field(default=0, description="Character position to start reading from: a heading's offset from the outline, which reads that part to its end, or next_offset.", ge=0)] = 0,
) -> str:
    """Retrieve regulatory text for a specific section or part: the current text, or the text in force on a given date.

    Omit date= for the current text; the result's date says which day was read.
    A text up to 12,000 characters comes back whole; there is no size to set. A longer one comes
    back as an outline: its own subheadings, each as "offset: heading", with only the lines before the
    first of them. Choose the part you need and call again with offset= that heading's offset: the part
    is read to its end, which is where the next subheading of its level begins, so "(g)" comes with the
    paragraphs under it, and the result's pinpoint cites it ("2 CFR 200.430(i)(5)"). Ask for several parts
    in one round of calls. A long text with no subheadings
    comes back a page at a time instead: when truncated, call again with offset = next_offset.
    Provide section= whenever possible — part-only requests return very large responses and will be blocked unless subpart= is also specified.
    Always provide title= explicitly for Parts 46 and 50, which exist in multiple titles.

    Examples:
      ecfr_get_regulation(title=2, part="200", section="200.474")
      ecfr_get_regulation(title=45, part="46", section="46.116", date="2018-07-18")
    """
    if subchapter and not chapter:
        return _finalize_response({"error": _make_error("subchapter requires chapter")})
    if subpart and not part:
        return _finalize_response({"error": _make_error("subpart requires part")})
    if section and not part:
        return _finalize_response({"error": _make_error("section requires part")})
    if appendix and not (subtitle or chapter or part):
        return _finalize_response({"error": _make_error("appendix requires subtitle, chapter, or part")})

    if not section and not part and not appendix:
        return _finalize_response({"error": _make_error(
            "Must provide at least part= or section=. Fetching an entire title is too large. "
            "Use ecfr_get_title_structure to find valid identifiers."
        )})
    if part and not section and not subpart and not appendix:
        return _finalize_response({"error": _make_error(
            f"Part {part} without section= or subpart= would return a very large response. "
            f"Add section= to narrow the request. "
            f"Use ecfr_get_title_structure(title=<N>, date=...) to find valid section identifiers."
        )})

    resolved_title = title
    if resolved_title is None:
        resolved = await _resolve_title(section=section, part=part)
        if resolved is None:
            return _finalize_response({"error": _make_error(
                "Could not resolve title from section/part. Provide title= explicitly."
            )})
        if isinstance(resolved, list):
            return _finalize_response({"error": _make_error(
                "Ambiguous: this part/section exists in multiple titles. Provide title= explicitly.",
                candidates=[{
                    "title": h.get("title"),
                    "part": h.get("part"),
                    "section": h.get("section"),
                    "chapter": h.get("chapter"),
                } for h in resolved],
                hint="Re-call with title= set to the correct title number.",
            )})
        try:
            resolved_title = int(resolved.get("title"))
        except (TypeError, ValueError):
            return _finalize_response({"error": _make_error("Title resolution returned non-numeric value.", resolved=resolved)})

    query_params = _build_params(
        subtitle=subtitle,
        chapter=chapter,
        subchapter=subchapter,
        part=part,
        subpart=subpart,
        section=section,
        appendix=appendix,
    )
    used_date = await _resolve_date(date, "date", resolved_title)
    xml_text = await api_get(
        f"versioner/v1/full/{used_date}/title-{resolved_title}.xml",
        params=query_params or None,
    )
    pin = ""
    if text_only:
        result = _text.read(*_xml_to_text_and_outline(xml_text), offset)
        pin = result.pop("pin", "")
    else:
        result = {"xml": xml_text}
        content_bytes = len(xml_text.encode("utf-8"))
        if content_bytes > SOFT_RESPONSE_BYTES:
            _add_warning(result, f"Response is {content_bytes:,} bytes (soft limit: 800KB). "
                                 f"Narrow to section= if you only need a specific provision.")
    _add_canonical_fields(result, title=resolved_title, part=part, section=section, appendix=appendix, date=used_date)
    if pin and (section or appendix):
        # the part read, as a finding cites it: "2 CFR 200.430(i)(5)", "2 CFR 200.1 Equipment", "2 CFR Appendix III to Part 200, B.1"
        result["pinpoint"] = f"{resolved_title} CFR {section}{pin}" if section else f"{resolved_title} CFR {appendix}, {pin.lstrip('. ')}"
    if title is None:
        result["resolved_from"] = "search"
    return _finalize_response(result)


@mcp.tool(name="ecfr_search", annotations=_READ_ONLY_ANNOTATIONS)
async def ecfr_search(
    query: Annotated[str, Field(description="Two or three words: every word must be in a section for it to match, so a long query finds nothing. Examples: 'indirect costs', 'subaward monitoring', 'conflict of interest', 'prior approval', 'procurement standards'.", min_length=1, max_length=500)],
    title: Annotated[Optional[int], Field(default=None, description="Limit the search to this CFR title (1–50). Uniform Guidance: title=2 with part='200'.", ge=1, le=50)] = None,
    part: Annotated[Optional[str], Field(default=None, description="Limit the search to this part, e.g. '200', '46'. Requires title, because part numbers repeat across titles.")] = None,
    subpart: Annotated[Optional[str], Field(default=None, description="Limit the search to this subpart, e.g. 'E'. Requires title and part.")] = None,
    section: Annotated[Optional[str], Field(default=None, description="Limit the search to this section, e.g. '200.430'. Requires title.")] = None,
    page: Annotated[int, Field(default=1, description="Page of results (max 20)", ge=1, le=20)] = 1,
    per_page: Annotated[int, Field(default=DEFAULT_SEARCH_RESULTS, description="Results per page (default 5). Increase to 10-15 only when broader coverage needed.", ge=1, le=MAX_SEARCH_RESULTS)] = DEFAULT_SEARCH_RESULTS,
    include_excerpts: Annotated[bool, Field(default=False, description="Include full_text_excerpt snippets. Useful to confirm relevance before fetching full text.")] = False,
    order: Annotated[Optional[str], Field(default="relevance", description="Sort order: 'relevance' (default), 'newest_first', 'oldest_first', 'hierarchy'")] = "relevance",
    date: Annotated[Optional[str], Field(default=None, description="Limit to the text in force on this date (YYYY-MM-DD). Omit for the current text: the latest day the eCFR holds. 'all' searches every version, superseded ones included, which often rank first.")] = None,
    last_modified_after: Annotated[Optional[str], Field(default=None, description="Modified after this date (YYYY-MM-DD)")] = None,
    last_modified_on_or_after: Annotated[Optional[str], Field(default=None, description="Modified on or after (YYYY-MM-DD)")] = None,
    last_modified_before: Annotated[Optional[str], Field(default=None, description="Modified before (YYYY-MM-DD)")] = None,
    last_modified_on_or_before: Annotated[Optional[str], Field(default=None, description="Modified on or before (YYYY-MM-DD)")] = None,
    agency_slugs: Annotated[Optional[List[str]], Field(default=None, description="Filter by agency slug(s) from ecfr_list_agencies. An agency filter takes in every part the agency owns; to search one part, use title and part instead.")] = None,
) -> str:
    """Full-text search of the Code of Federal Regulations: all of it, or one title, part, subpart or section.

    START HERE for topic or concept questions where you don't have a specific citation.
    Returns sections ranked by relevance, each as its citation, its heading, the title, part and section
    (or appendix) to pass to ecfr_get_regulation, and its link.
    Three things make a search find the governing sections: the words, the limit to a title and part,
    and the date. Keep the words few, two or three: a section matches only when it has every one of them. With no date= the search is of the current text (the result's date says which day);
    give a date for the rule in force that day, or date="all" for every version, superseded ones included.
    For Uniform Guidance topics, search only 2 CFR 200: title=2, part="200".
    meta.description says what was searched, e.g. "... in Title 2 :: Part 200".

    Example: ecfr_search(query="compensation", title=2, part="200")

    NEXT STEP: Take the title/part/section from a result → ecfr_get_regulation with the same date
    (or none, for the current text) to fetch the full text.
    """
    if (part or subpart or section) and title is None:
        return _finalize_response({"error": _make_error("part, subpart and section require title")})
    if subpart and not part:
        return _finalize_response({"error": _make_error("subpart requires part")})
    every_version = (date or "").strip().lower() == "all"
    used_date = None if every_version else await _resolve_date(date, "date", title)
    for field_name, field_val in [
        ("last_modified_after", last_modified_after),
        ("last_modified_on_or_after", last_modified_on_or_after),
        ("last_modified_before", last_modified_before),
        ("last_modified_on_or_before", last_modified_on_or_before),
    ]:
        _validate_date_str(field_val, field_name)

    query_params = _build_params(
        query=query,
        page=page,
        per_page=per_page,
        paginate_by="results",
        order=order,
        date=used_date,
        last_modified_after=last_modified_after,
        last_modified_on_or_after=last_modified_on_or_after,
        last_modified_before=last_modified_before,
        last_modified_on_or_before=last_modified_on_or_before,
    )
    if agency_slugs:
        query_params["agency_slugs[]"] = agency_slugs
    for level, value in [("title", title), ("part", part), ("subpart", subpart), ("section", section)]:
        if value is not None:
            query_params[f"hierarchy[{level}]"] = value

    data = await api_get("search/v1/results.json", params=query_params)
    results = data.get("results", [])
    meta = data.get("meta", {})
    response = {
        "results": [_slim_search_result(r, include_excerpts, every_version) for r in results],
        "meta": meta,
        "date": used_date or "all",
        "source_url": f"{ECFR_SITE}/search?query={query}",
    }
    total_pages = meta.get("total_pages", 0)
    total_count = meta.get("total_count", 0)
    current_page = meta.get("current_page", 1)
    if not results and len(query.split()) > 3:
        _add_warning(response, "No section has every word of this query. Search again with two or three of them.")
    if total_pages > 20:
        _add_warning(response, f"{total_count} total results across {total_pages} pages; only pages 1–20 accessible. "
                               f"Narrow with title and part, date, agency_slugs, or last_modified_* filters.")
    if current_page >= 20 and total_pages > 20:
        _add_warning(response, f"Reached last accessible page (20/{total_pages}). Refine the query to find more specific results.")
    return _finalize_response(response)


@mcp.tool(name="ecfr_get_title_structure", annotations=_READ_ONLY_ANNOTATIONS)
async def ecfr_get_title_structure(
    title: Annotated[int, Field(description="CFR title number (1–50)", ge=1, le=50)],
    date: Annotated[Optional[str], Field(default=None, description="The day whose table of contents is wanted (YYYY-MM-DD). Omit for the current one: the latest day the eCFR holds.")] = None,
    depth: Annotated[int, Field(default=DEFAULT_STRUCTURE_DEPTH, description="Hierarchy depth: 1=title, 2=subtitle/chapter, 3=parts, 4=sections. Depth 4 on broad titles (2, 42, 45) is blocked — use depth 3 then narrow.", ge=1, le=4)] = DEFAULT_STRUCTURE_DEPTH,
) -> str:
    """Get the hierarchical table of contents for a CFR title: the current one, or as it stood on a given date.

    Use this to discover valid part and section identifiers before calling ecfr_get_regulation.
    Start with depth=2 or depth=3; depth=4 on broad titles (2, 42, 45) is blocked due to response size.
    """
    if depth == 4 and title in {2, 42, 45}:
        return _finalize_response({"error": _make_error(
            f"Depth 4 for Title {title} exceeds the 1MB response limit. "
            f"Use depth=3 to find parts, then call ecfr_get_regulation with a specific part or section."
        )})
    used_date = await _resolve_date(date, "date", title)
    data = await api_get(f"versioner/v1/structure/{used_date}/title-{title}.json")
    pruned = _prune_tree(data, max_depth=depth)
    _add_canonical_fields(pruned, title=title, date=used_date)
    if len(json.dumps(pruned, ensure_ascii=False).encode("utf-8")) > SOFT_RESPONSE_BYTES:
        _add_warning(pruned, "Structure response is large (>800KB). Lower depth or use ecfr_search to find a specific section first.")
    return _finalize_response(pruned)


@mcp.tool(name="ecfr_compare_regulations", annotations=_READ_ONLY_ANNOTATIONS)
async def ecfr_compare_regulations(
    date_1: Annotated[str, Field(description="Earlier date (YYYY-MM-DD): any day the earlier text was in force. ecfr_get_title_versions gives the days a section changed.")],
    date_2: Annotated[Optional[str], Field(default=None, description="Later date (YYYY-MM-DD). Omit to compare with the current text: the latest day the eCFR holds.")] = None,
    title: Annotated[Optional[int], Field(default=None, description="CFR title number. Provide explicitly to avoid ambiguity. See ecfr_get_regulation notes on ambiguous parts.", ge=1, le=50)] = None,
    part: Annotated[Optional[str], Field(default=None, description="Part number, e.g. '200'")] = None,
    section: Annotated[Optional[str], Field(default=None, description="Section number. Requires part.")] = None,
    subpart: Annotated[Optional[str], Field(default=None, description="Requires part.")] = None,
    subtitle: Annotated[Optional[str], Field(default=None, description="Uppercase letter")] = None,
    chapter: Annotated[Optional[str], Field(default=None, description="Roman numeral")] = None,
    subchapter: Annotated[Optional[str], Field(default=None, description="Requires chapter.")] = None,
    appendix: Annotated[Optional[str], Field(default=None, description="Requires subtitle, chapter, or part.")] = None,
    include_full_text: Annotated[bool, Field(default=False, description="Include full plain text of both versions alongside the diff. Default False.")] = False,
) -> str:
    """Compare regulatory text between two dates to identify changes.

    Give date_1 and leave date_2 out to compare an earlier text with the current one. To compare two
    versions, ecfr_get_title_versions gives the days a section changed: a day before a change and a day
    on or after it. Returns a structured diff of added/removed paragraphs.
    Set include_full_text=True to also receive the full text of both versions.
    """
    if subchapter and not chapter:
        return _finalize_response({"error": _make_error("subchapter requires chapter")})
    if subpart and not part:
        return _finalize_response({"error": _make_error("subpart requires part")})
    if section and not part:
        return _finalize_response({"error": _make_error("section requires part")})
    if appendix and not (subtitle or chapter or part):
        return _finalize_response({"error": _make_error("appendix requires subtitle, chapter, or part")})

    resolved_title = title
    if resolved_title is None:
        resolved = await _resolve_title(section=section, part=part)
        if resolved is None:
            return _finalize_response({"error": _make_error(
                "Could not resolve title. Provide title= explicitly."
            )})
        if isinstance(resolved, list):
            return _finalize_response({"error": _make_error(
                "Ambiguous: part/section exists in multiple titles. Provide title= explicitly.",
                candidates=[{"title": h.get("title"), "part": h.get("part"), "section": h.get("section")} for h in resolved],
                hint="Re-call with title= specified.",
            )})
        try:
            resolved_title = int(resolved.get("title"))
        except (TypeError, ValueError):
            return _finalize_response({"error": _make_error("Non-numeric title resolved.", resolved=resolved)})

    hierarchy = _build_params(
        subtitle=subtitle,
        chapter=chapter,
        subchapter=subchapter,
        part=part,
        subpart=subpart,
        section=section,
        appendix=appendix,
    )
    date_1 = await _resolve_date(date_1, "date_1", resolved_title)
    date_2 = await _resolve_date(date_2, "date_2", resolved_title)
    xml_1 = await api_get(f"versioner/v1/full/{date_1}/title-{resolved_title}.xml", params=hierarchy)
    xml_2 = await api_get(f"versioner/v1/full/{date_2}/title-{resolved_title}.xml", params=hierarchy)
    text_1 = _xml_to_text(xml_1)
    text_2 = _xml_to_text(xml_2)
    identical = text_1 == text_2

    result: Dict[str, Any] = {
        "date_1": date_1,
        "date_2": date_2,
        "identical": identical,
        "length_1": len(text_1),
        "length_2": len(text_2),
    }
    _add_canonical_fields(result, title=resolved_title, part=part, section=section, appendix=appendix, date=date_2)
    if title is None:
        result["resolved_from"] = "search"

    if identical:
        result["diff"] = {"summary": "No changes detected.", "added_lines": [], "removed_lines": []}
    else:
        lines_1 = text_1.splitlines()
        lines_2 = text_2.splitlines()
        differ = difflib.unified_diff(
            lines_1, lines_2,
            fromfile=f"Date: {date_1}",
            tofile=f"Date: {date_2}",
            lineterm="",
        )
        added, removed = [], []
        for line in differ:
            if line.startswith("+") and not line.startswith("+++"):
                added.append(line[1:].strip())
            elif line.startswith("-") and not line.startswith("---"):
                removed.append(line[1:].strip())
        added = [l for l in added if l]
        removed = [l for l in removed if l]

        t_added, omit_added = added[:MAX_DIFF_LINES], max(0, len(added) - MAX_DIFF_LINES)
        t_removed, omit_removed = removed[:MAX_DIFF_LINES], max(0, len(removed) - MAX_DIFF_LINES)
        result["diff"] = {
            "summary": f"{len(added)} paragraph(s) added, {len(removed)} paragraph(s) removed",
            "added_lines": t_added,
            "removed_lines": t_removed,
        }
        if omit_added or omit_removed:
            _add_warning(result, f"Diff truncated to {MAX_DIFF_LINES} lines each. "
                                 f"Omitted {omit_added} added and {omit_removed} removed lines.")

    if include_full_text:
        result["text_1"] = text_1
        if not identical:
            result["text_2"] = text_2
        else:
            result["note"] = "Texts identical — only text_1 included."

    return _finalize_response(result)


@mcp.tool(name="ecfr_list_agencies", annotations=_READ_ONLY_ANNOTATIONS)
async def ecfr_list_agencies(
    name_filter: Annotated[Optional[str], Field(default=None, description="Case-insensitive substring filter on agency name or slug. E.g. 'health', 'nsf', 'education'.")] = None,
    include_children: Annotated[bool, Field(default=False, description="Include sub-agency children arrays. Default False keeps response compact.")] = False,
) -> str:
    """List federal agencies with slugs and CFR references.

    Use name_filter to find a specific agency quickly (e.g. 'health', 'nsf').
    Slugs can be passed to ecfr_search via agency_slugs= to scope results to everything an agency owns.
    Common slugs: 'management-and-budget-office', 'national-science-foundation',
    'national-institutes-of-health'.
    To search the Uniform Guidance alone, use ecfr_search(title=2, part="200") rather than an agency slug.
    """
    data = await api_get("admin/v1/agencies.json")
    agencies = data.get("agencies", [])
    if name_filter:
        needle = name_filter.lower()
        agencies = [
            a for a in agencies
            if needle in (a.get("name") or "").lower()
            or needle in (a.get("slug") or "").lower()
            or needle in (a.get("short_name") or "").lower()
        ]

    def _slim(agency: dict) -> dict:
        r = {
            "name": agency.get("name"),
            "short_name": agency.get("short_name"),
            "slug": agency.get("slug"),
            "cfr_references": agency.get("cfr_references", []),
        }
        if include_children:
            r["children"] = [_slim(c) for c in agency.get("children", [])]
        return r

    return _finalize_response({"agencies": [_slim(a) for a in agencies]})


@mcp.tool(name="ecfr_list_titles", annotations=_READ_ONLY_ANNOTATIONS)
async def ecfr_list_titles(
    summary_only: Annotated[bool, Field(default=True, description="True (default): returns number, name, latest_amended_on, source_url only — sufficient for navigation and well within the 1MB limit. False: full API response including reserved/up_to_date_as_of fields.")] = True,
) -> str:
    """List all 50 CFR titles with names and latest amendment dates.

    Use summary_only=True (default) to get a compact list sufficient for identifying
    which title number covers a given topic area.
    """
    data = await api_get("versioner/v1/titles.json")
    if summary_only:
        data = {"titles": [
            {
                "citation": f"{t['number']} CFR",
                "title": t["number"],
                "name": t["name"],
                "latest_amended_on": t.get("latest_amended_on"),
                "source_url": _make_source_url(title=t["number"]),
            }
            for t in data.get("titles", [])
        ]}
    return _finalize_response(data)


# =============================================================================
# ENTRY POINT
# =============================================================================


# =============================================================================
# SKILLS — catalogued components served as MCP prompts and as static files
# =============================================================================

from pathlib import Path as _Path  # noqa: E402

from ai4ra_mcp.common.skills import register_prompts as _register_prompts  # noqa: E402

SKILLS_DIR = _Path(__file__).parent / "skills"
_register_prompts(mcp, SKILLS_DIR)
