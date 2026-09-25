"""oig: the HHS Office of Inspector General's List of Excluded Individuals/Entities (LEIE).

Upstream: https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv, the whole list as one CSV (about 15 MB, some
80,000 rows), downloaded once and searched in memory for a day. No key. OIG updates it monthly. Dates are YYYYMMDD
with 00000000 for none; an NPI of 0000000000 is none.
"""

from __future__ import annotations

import asyncio
import csv
import io
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, HEADERS, TTLCache
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
CSV_URL = "https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv"
SEARCH_URL = "https://exclusions.oig.hhs.gov/"
# The exclusion authorities in section 1128 of the Social Security Act, as the EXCLTYPE column codes them.
# 1128(a) exclusions are mandatory (five years at least); 1128(b) are permissive.
EXCLUSION_TYPES = {
    "1128a1": "mandatory: conviction of a program-related crime",
    "1128a2": "mandatory: conviction relating to patient abuse or neglect",
    "1128a3": "mandatory: felony conviction relating to health care fraud",
    "1128a4": "mandatory: felony conviction relating to controlled substances",
    "1128b1": "permissive: misdemeanor conviction relating to health care fraud",
    "1128b2": "permissive: conviction relating to obstruction of an investigation or audit",
    "1128b3": "permissive: misdemeanor conviction relating to controlled substances",
    "1128b4": "permissive: license revocation, suspension or surrender",
    "1128b5": "permissive: exclusion or suspension under another federal or state health care program",
    "1128b6": "permissive: excessive charges, unnecessary services or substandard care",
    "1128b7": "permissive: fraud, kickbacks and other prohibited activities",
    "1128b8": "permissive: entity controlled by a sanctioned individual",
    "1128b9": "permissive: failure to disclose required information",
    "1128b10": "permissive: failure to supply requested information on subcontractors and suppliers",
    "1128b11": "permissive: failure to supply payment information",
    "1128b12": "permissive: failure to grant immediate access",
    "1128b13": "permissive: failure to take corrective action",
    "1128b14": "permissive: default on a health education loan or scholarship obligation",
    "1128b15": "permissive: individual who controls a sanctioned entity",
    "1128b16": "permissive: false statement or misrepresentation of a material fact",
    "1128Aa": "civil monetary penalty: false or fraudulent claims (section 1128A(a))",
    "1156": "peer review: failure to meet obligations to provide medically necessary care of professional quality",
    "1160": "peer review: sanction under former section 1160 (professional standards review, before 1987)",
    "BRCH SA": "breach of a settlement agreement",
    "BRCH CIA": "breach of a corporate integrity agreement",
}
_cache = TTLCache()
_lock = asyncio.Lock()

mcp = MCPServer(
    "oig",
    instructions="HHS OIG List of Excluded Individuals/Entities: whether a person or business is excluded from federal health care programs, by name or NPI. Read oig_leie_index first.",
)


async def download_csv() -> str:
    """The whole LEIE as text. Streamed into memory; a module-level function so a test can replace it."""
    async with httpx.AsyncClient(timeout=120.0, headers=HEADERS, follow_redirects=True) as client:
        async with client.stream("GET", CSV_URL) as resp:
            if resp.status_code >= 400:
                raise ValueError(f"{resp.status_code} from oig.hhs.gov fetching the LEIE")
            chunks = [chunk async for chunk in resp.aiter_bytes()]
    return b"".join(chunks).decode("utf-8", errors="replace")


def parse_csv(text: str) -> list[dict]:
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


async def _list() -> dict:
    # One lock so concurrent first calls download once; the cache then answers for a day.
    async with _lock:
        async def load() -> dict:
            rows = parse_csv(await download_csv())
            return {"rows": rows, "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        return await _cache.remember("leie", DAY, load)


def _date(v: str | None) -> str | None:
    v = (v or "").strip()
    return f"{v[:4]}-{v[4:6]}-{v[6:8]}" if len(v) == 8 and v.isdigit() and v != "00000000" else None


def _words(s: str) -> list[str]:
    return re.sub(r"[^A-Z0-9 ]", " ", (s or "").upper()).split()


def _person_name(row: dict) -> str | None:
    last, first, mid = (row.get("LASTNAME") or "").strip(), (row.get("FIRSTNAME") or "").strip(), (row.get("MIDNAME") or "").strip()
    if not last and not first:
        return None
    return f"{last}, {first} {mid}".strip().rstrip(",")


def slim_row(row: dict) -> dict:
    npi = (row.get("NPI") or "").strip()
    code = (row.get("EXCLTYPE") or "").strip()
    return {
        "name": _person_name(row), "business": (row.get("BUSNAME") or "").strip() or None,
        "general": row.get("GENERAL") or None, "specialty": row.get("SPECIALTY") or None,
        "npi": npi if npi and npi != "0000000000" else None, "date_of_birth": _date(row.get("DOB")),
        "city": row.get("CITY") or None, "state": row.get("STATE") or None, "zip": row.get("ZIP") or None,
        "exclusion_type": code, "exclusion_meaning": EXCLUSION_TYPES.get(code, "see the OIG exclusion authorities table"),
        "exclusion_date": _date(row.get("EXCLDATE")), "reinstatement_date": _date(row.get("REINDATE")),
        "waiver_date": _date(row.get("WAIVERDATE")), "waiver_state": row.get("WVRSTATE") or None,
    }


def match_rows(rows: list[dict], name: str = "", npi: str = "", state: str = "", exclusion_type: str = "") -> list[dict]:
    """The rows a search matches. Every word of name must begin a word of the business name or of the person's
    last, first and middle names, in any order, so 'smith john' and 'john smith' find the same person."""
    want = _words(name)
    npi, state, etype = npi.strip(), state.strip().upper(), exclusion_type.strip().lower()
    out = []
    for row in rows:
        if npi and (row.get("NPI") or "").strip() != npi:
            continue
        if state and (row.get("STATE") or "").strip().upper() != state:
            continue
        if etype and (row.get("EXCLTYPE") or "").strip().lower() != etype:
            continue
        if want:
            hay = _words(row.get("BUSNAME") or "") or _words(" ".join((row.get("LASTNAME") or "", row.get("FIRSTNAME") or "", row.get("MIDNAME") or "")))
            if not all(any(h.startswith(w) for h in hay) for w in want):
                continue
        out.append(row)
    return out


@mcp.tool(name="oig_leie_index", annotations=_READ_ONLY)
async def oig_leie_index() -> dict:
    """How to use the OIG exclusion list tools. READ THIS FIRST: what the list is, when it is required, how to read a hit."""
    return {
        "upstream": CSV_URL + ", the whole list, refreshed here daily; no key",
        "workflow": ["oig_leie_search by the person's or business's name, then by NPI when one is known",
                     "oig_leie_status to say when this copy of the list was downloaded",
                     "for a hit, cite the exclusion type and date, and confirm on " + SEARCH_URL + " before acting"],
        "notes": ["The LEIE is the HHS check: anyone paid with HHS funds (NIH, HRSA, CDC, ...) must not be excluded, and a recipient must screen employees, contractors and subrecipients (42 CFR 1001.1901). It is separate from SAM.gov exclusions and from the export-control screening on the csl server.",
                  "A match is by name, so a common name is a lead, not a finding: compare the NPI, specialty, city and state, and verify on the online search, which OIG treats as the record.",
                  "exclusion_type is the section 1128 authority; 1128(a) exclusions are mandatory and last at least five years, 1128(b) are permissive. reinstatement_date set means the exclusion has ended.",
                  "A waiver (waiver_date, waiver_state) lets the person be paid under a program in that state only.",
                  "OIG updates the list monthly; list_as_of is when this copy was downloaded. Dates are YYYY-MM-DD.",
                  "The first search of the day downloads 15 MB and takes a few seconds."],
    }


@mcp.tool(name="oig_leie_search", annotations=_READ_ONLY)
async def oig_leie_search(name: str = "", npi: str = "", state: str = "", exclusion_type: str = "", limit: int = 25) -> dict:
    """People and businesses on the OIG exclusion list matching a name or NPI.

    Give name or npi. Returns each exclusion with the name, specialty, NPI, city, state, the exclusion type and its
    meaning, the dates, and a link to OIG's own search for verification.

    Args:
        name: Words of the name in any order, e.g. 'John Smith' or 'Acme Home Health'. Every word must appear.
        npi: The 10-digit National Provider Identifier; an exact match.
        state: Two-letter state to narrow, e.g. 'ID'.
        exclusion_type: One authority code to narrow, e.g. '1128a1'.
        limit: Rows to return, 1-100. Default 25.
    """
    if not name.strip() and not npi.strip():
        return {"error": "give name or npi"}
    if npi.strip() and not re.fullmatch(r"\d{10}", npi.strip()):
        return {"error": "npi must be 10 digits"}
    try:
        data = await _list()
    except (ValueError, httpx.HTTPError) as e:
        return {"error": f"could not fetch the LEIE: {e}"}
    matched = match_rows(data["rows"], name, npi, state, exclusion_type)
    limit = max(1, min(int(limit or 25), 100))
    return {"returned": min(len(matched), limit), "total": len(matched), "exclusions": [slim_row(r) for r in matched[:limit]],
            "list_as_of": data["as_of"], "link": SEARCH_URL,
            "note": "No row matches; confirm with the online search before recording a clear result." if not matched else "A name match is a lead; verify NPI, location and specialty, and confirm at the link."}


@mcp.tool(name="oig_leie_status", annotations=_READ_ONLY)
async def oig_leie_status() -> dict:
    """Whether the exclusion list is loaded on this server, how many rows it has and when it was downloaded."""
    data = _cache.get("leie")
    if not data:
        return {"loaded": False, "rows": 0, "list_as_of": None, "source": CSV_URL, "note": "The first search downloads the list; it is then held for a day."}
    return {"loaded": True, "rows": len(data["rows"]), "list_as_of": data["as_of"], "source": CSV_URL, "refresh": "daily"}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
