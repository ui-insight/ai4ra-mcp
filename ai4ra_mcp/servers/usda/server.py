"""usda: the USDA General Terms and Conditions, the USDA deviations to them, and APHIS's own award terms, served by section.

Upstream: the official PDFs, saved and stored here (data/pdf), never read at request time. www.usda.gov refuses
automated requests, so the USDA documents were saved by a person in a browser; the APHIS ones were fetched from
www.aphis.usda.gov. Each was split at its own headings by convert.py, word for word (data/sections), and its
manifest entry (data/manifest.json) carries the source URL, the date saved, the version (effective date, or the
deviation number), the PDF's checksum and its own creation date, and for a deviation the document it modifies and
the section numbers its text names. A question costs the contents list and a few sections, not a 48-page document,
with no embeddings, so any model can use it. Every answer that carries text names the publisher's PDF with a page
anchor and the date the copy was saved; a copy marked stale in the manifest says so in every answer.

These are works of the U.S. Government, not subject to copyright in the United States (17 U.S.C. 105(a)).
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
DATA = Path(__file__).parent / "data"
PIECE = 6000   # characters of one section per call; the largest section (3.0 of the Federal Awards terms) is 8,192
APHIS_PAGE = "https://www.aphis.usda.gov/organization/business-services/asc/terms-conditions"
# The stored PDFs as this repository publishes them: a download of the copy exactly as saved, beside the publisher's link.
COPY_BASE = "https://github.com/ui-insight/ai4ra-mcp/raw/main/ai4ra_mcp/servers/usda/data/pdf/"
USDA_PAGE = "https://www.usda.gov/about-usda/general-information/staff-offices/office-chief-financial-officer/federal-financial-assistance-policy/usda-general-terms-and-conditions"

MANIFEST = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
DOCS: dict[str, dict] = {d["id"]: d for d in MANIFEST["documents"]}
SECTIONS: dict[str, dict] = {i: json.loads((DATA / "sections" / f"{i}.json").read_text(encoding="utf-8")) for i in DOCS}

mcp = MCPServer(
    "usda",
    instructions="The USDA General Terms and Conditions (for Federal Awards and for Mutual Interest Agreements), the USDA deviations to them, and APHIS's award terms, from the official PDFs saved here and split by section: the documents and their versions (usda_terms_documents), one document's contents (usda_terms_contents), one section's text (usda_terms_section), words across them (usda_terms_search), what was in force on an award's date (usda_terms_for_award). No key. Read usda_index first.",
)


def _status(e: dict) -> str:
    if e.get("stale_since"):
        return "stale"
    if e["kind"] != "deviation" and any(o["kind"] == e["kind"] and o["agency"] == e["agency"] and o["applies_to"] == e["applies_to"]
                                        and o["effective"] > e["effective"] for o in DOCS.values()):
        return "superseded"
    return "current"


def _stale(e: dict) -> str | None:
    return f"A newer version may exist (seen {e['stale_since']}); this copy was saved {e['saved']}. Check {e['listed_on']}." if e.get("stale_since") else None


def _ref(s: dict) -> str:
    """How a section is named back to the server: its number, or its title when it has none."""
    return s["num"] or s["title"]


def _pages(s: dict) -> str:
    return str(s["page_start"]) if s["page_start"] == s["page_end"] else f"{s['page_start']}-{s['page_end']}"


def _version(e: dict) -> str:
    return e["deviation"] + f" (effective {e['effective']})" if e["deviation"] else f"effective {e['effective']}"


def _source(e: dict, s: dict | None = None) -> dict:
    """Where a result's text comes from: the publisher's PDF at the section's page, and the copy's date."""
    out = {"document": e["title"], "version": _version(e)}
    if s is not None:
        out |= {"section": _ref(s), "pdf_pages": _pages(s), "link": f"{e['source_url']}#page={s['page_start']}"}
    else:
        out["link"] = e["source_url"]
    out |= {"copy": f"{COPY_BASE}{e['id']}.pdf", "saved": e["saved"]}
    if e.get("stale_since"):
        out["stale"] = _stale(e)
    return out


def _document(want: str) -> dict | None:
    """A document by its id or, for a deviation, its number ('2026-USDA-0002-F')."""
    w = want.strip().lower()
    return next((e for e in DOCS.values() if e["id"].lower() == w or (e["deviation"] or "").lower() == w), None)


def _no_document(want: str) -> dict:
    return {"error": f"no document {want!r}; name one by id or deviation number", "documents": [{"id": e["id"], "deviation": e["deviation"], "title": e["title"]} for e in DOCS.values()]}


def _match(sections: list[dict], want: str) -> list[dict]:
    """The sections a name picks: an exact number, else an exact title, else every title carrying all the words."""
    w = want.strip().rstrip(".")
    exact = [s for s in sections if s["num"] and s["num"] == w]
    if exact:
        return exact
    titled = [s for s in sections if s["title"].lower() == w.lower()]
    if titled:
        return titled
    words = w.lower().split()
    return [s for s in sections if words and all(x in s["title"].lower() for x in words)]


def _deviations_on(e: dict, s: dict) -> list[dict]:
    """The deviations that name this section of this document (or a section it sits in)."""
    if not s["num"]:
        return []
    out = []
    for d in DOCS.values():
        if d.get("modifies") == e["id"] and any(s["num"] == n or s["num"].startswith(n + ".") for n in d.get("names_sections") or []):
            out.append({"deviation": d["deviation"], "id": d["id"], "effective": d["effective"], "names": d["names_sections"], "applies": d.get("note"), "link": d["source_url"]})
    return out


def _excerpt(text: str, words: list[str]) -> str:
    low = text.lower()
    k = min((low.find(w) for w in words if w in low), default=-1)
    if len(text) <= 300:
        return text
    return (("… " if k > 120 else "") + text[max(0, k - 120):k + 180].strip() + " …") if k >= 0 else text[:300] + " …"


@mcp.tool(name="usda_index", annotations=_READ_ONLY)
async def usda_index() -> dict:
    """How to use the USDA and APHIS terms tools. READ THIS FIRST: which documents are held, how versions and deviations work, how to cite."""
    return {
        "upstream": "The official PDFs from www.usda.gov and www.aphis.usda.gov, saved here and split at their own headings word for word; read from storage, never at request time; no key",
        "documents": len(DOCS),
        "stale": [e["id"] for e in DOCS.values() if e.get("stale_since")],
        "workflow": ["usda_terms_for_award with the award's date when the question is which terms govern an award",
                     "usda_terms_contents with a document for its sections, their PDF pages and sizes; the first call for a question about what a document says",
                     "usda_terms_section with the document and a section number ('10.7') or title ('PATENTS AND INVENTIONS') for its text",
                     "usda_terms_search with words when the section is not known from the contents"],
        "notes": ["The USDA General Terms and Conditions come in two editions, for Federal Awards and for Mutual Interest Agreements (MIA), numbered differently (Federal Awards 10.7 is MIA 9.7). Both are effective 2025-12-31.",
                  "A deviation (2026-USDA-NNNN-F for Federal Awards, -M for MIA) modifies one edition. It applies to an award only when the award incorporates it, so a deviation in force on a date was available, not necessarily applied. 0001 (research security, FOCI, disclosures, malign foreign talent recruitment) is optional for awarding agencies; 0002 applies only to the Seattle Plaintiffs named in it.",
                  "APHIS's terms incorporate the USDA General Terms for Federal Awards by reference. APHIS's page says the version in force when the award was signed applies, and a substantial amendment moves an award to the current version.",
                  "A section is named by its number, or by its title where the document numbers none (the APHIS terms and the NWS supplement). usda_terms_section returns a long section in pieces with next_offset; it is never cut silently.",
                  "Cite the document, its version, the section and the PDF page, with the link given (the publisher's PDF with #page=). Every answer also carries the date the copy was saved.",
                  "copy is a download of the stored PDF exactly as saved (its sha256 is in usda_terms_documents), for a person who wants the file: www.usda.gov refuses some automated requests, and USDA has replaced a PDF at the same address without changing its date, so the copy is the version these answers quote."],
        "caveats": ["Only the versions listed by usda_terms_documents are held. An award signed before a held version's effective date was governed by an earlier one: say it is not held here and give the listing page (" + APHIS_PAGE + " or " + USDA_PAGE + ").",
                    "A copy marked stale may have been replaced by a newer version; every answer from it says so. USDA has replaced a PDF without changing its effective date, so a version is told apart by its checksum and the PDF's creation date (usda_terms_documents gives both).",
                    "The award document itself governs: its terms, the deviations it incorporates and any special conditions. These tools give the standard terms, not one award's."],
        "links": {"usda": USDA_PAGE, "aphis": APHIS_PAGE},
    }


@mcp.tool(name="usda_terms_documents", annotations=_READ_ONLY)
async def usda_terms_documents() -> dict:
    """Every document held: id, title, agency, kind, who it applies to, version, status (current, superseded or stale), what a deviation modifies and which sections it names, the source PDF and the date the copy was saved."""
    docs = [{"id": e["id"], "title": e["title"], "agency": e["agency"].upper(), "kind": e["kind"], "applies_to": e["applies_to"], "effective": e["effective"],
             "deviation": e["deviation"], "modifies": e.get("modifies"), "names_sections": e.get("names_sections"), "status": _status(e), "stale": _stale(e),
             "note": e.get("note"), "pages": e["pages"], "sections": e["sections"], "source_url": e["source_url"], "copy": f"{COPY_BASE}{e['id']}.pdf", "listed_on": e["listed_on"],
             "saved": e["saved"], "saved_how": e["saved_how"], "sha256": e["sha256"], "pdf_created": e["pdf_created"]} for e in DOCS.values()]
    return {"total": len(docs), "documents": docs, "license": MANIFEST["license"]}


@mcp.tool(name="usda_terms_contents", annotations=_READ_ONLY)
async def usda_terms_contents(document: str) -> dict:
    """One document's sections in order: the name to ask for each by, number, title, level, PDF pages and size in characters.

    Args:
        document: The document's id from usda_terms_documents, or a deviation number ('2026-USDA-0001-F').
    """
    e = _document(document)
    if e is None:
        return _no_document(document)
    secs = SECTIONS[e["id"]]["sections"]
    return {"id": e["id"], **_source(e), "status": _status(e), "total": len(secs),
            "sections": [{"section": _ref(s), "number": s["num"] or None, "title": s["title"], "level": s["level"], "pdf_pages": _pages(s), "chars": len(s["text"])} for s in secs]}


@mcp.tool(name="usda_terms_section", annotations=_READ_ONLY)
async def usda_terms_section(document: str, section: str, offset: int = 0) -> dict:
    """One section's text, word for word from the PDF, with its source link at the page and any deviation that names it.

    A section longer than 6,000 characters comes in pieces: next_offset is set while more remains.

    Args:
        document: The document's id from usda_terms_documents, or a deviation number ('2026-USDA-0002-F').
        section: The section's number ('10.7', '12.2.2') or title ('Prior Approval', 'RECIPIENT RESPONSIBILITIES'), as usda_terms_contents lists it.
        offset: Where to start in the section's text, from a previous call's next_offset. Default 0.
    """
    e = _document(document)
    if e is None:
        return _no_document(document)
    if not section.strip():
        return {"error": "section is required; see usda_terms_contents"}
    hits = _match(SECTIONS[e["id"]]["sections"], section)
    if not hits:
        return {"error": f"no section {section!r} in {e['id']}; see usda_terms_contents"}
    if len(hits) > 1:
        return {"error": f"{len(hits)} sections carry those words; name one", "sections": [{"section": _ref(s), "title": s["title"]} for s in hits[:30]]}
    s = hits[0]
    text, start = s["text"], max(0, int(offset or 0))
    end = len(text) if len(text) - start <= PIECE else (text.rfind("\n\n", start, start + PIECE) if text.rfind("\n\n", start, start + PIECE) > start else start + PIECE)
    out = {"section": _ref(s), "number": s["num"] or None, "title": s["title"], "text": text[start:end], **_source(e, s), "status": _status(e)}
    if end < len(text):
        out |= {"next_offset": end, "total_chars": len(text)}
    elif start:
        out["total_chars"] = len(text)
    if not s["text"]:
        out["note"] = "This is a part heading with no text of its own; its numbered sections follow it in usda_terms_contents."
    devs = _deviations_on(e, s)
    if devs:
        out["deviations"] = devs
        out["deviation_note"] = "A deviation names this section. It changes the section only for an award that incorporates it; read it with usda_terms_section on the deviation's id."
    if e.get("modifies"):
        out["modifies"] = e["modifies"]
    return out


@mcp.tool(name="usda_terms_search", annotations=_READ_ONLY)
async def usda_terms_search(words: str, document: str = "", rows: int = 20) -> dict:
    """The sections that carry every word given, section titles first, each with an excerpt and its source link.

    Args:
        words: Words to find, e.g. 'prior approval', 'program income', 'foreign travel'.
        document: A document's id or deviation number to search only that one. Empty for all.
        rows: Sections to return, 1-50. Default 20.
    """
    want = [w for w in words.lower().split() if w]
    if not want:
        return {"error": "words is required"}
    docs = list(DOCS.values())
    if document.strip():
        e = _document(document)
        if e is None:
            return _no_document(document)
        docs = [e]
    rows = max(1, min(int(rows or 20), 50))
    hits = []
    for e in docs:
        for s in SECTIONS[e["id"]]["sections"]:
            title = s["title"].lower()
            if all(w in (title + " " + s["text"].lower()) for w in want):
                hits.append({"id": e["id"], "section": _ref(s), "title": s["title"], "in_title": all(w in title for w in want),
                             "excerpt": _excerpt(s["text"], want), **_source(e, s), "status": _status(e)})
    hits.sort(key=lambda h: not h["in_title"])
    out = {"words": words.strip(), "total": len(hits), "returned": min(rows, len(hits)), "sections": hits[:rows]}
    if len(hits) > rows:
        out["note"] = f"{len(hits)} sections match; the first {rows} are here (title matches first). Name a document or add a word to narrow."
    return out


@mcp.tool(name="usda_terms_for_award", annotations=_READ_ONLY)
async def usda_terms_for_award(date: str) -> dict:
    """The held versions in force on an award's date, and the deviations available then, with what each applies to.

    Args:
        date: The date the award was signed (or substantially amended), YYYY-MM-DD.
    """
    try:
        day = _dt.date.fromisoformat(date.strip()).isoformat()
    except ValueError:
        return {"error": f"date must be YYYY-MM-DD, got {date!r}"}
    groups: dict[tuple, list[dict]] = {}
    for e in DOCS.values():
        if e["kind"] != "deviation":
            groups.setdefault((e["agency"], e["kind"], e["applies_to"]), []).append(e)
    in_force, not_held = [], []
    for (agency, kind, applies_to), versions in groups.items():
        held = sorted((v for v in versions if v["effective"] <= day), key=lambda v: v["effective"])
        if held:
            v = held[-1]
            in_force.append({"id": v["id"], "title": v["title"], "agency": agency.upper(), "kind": kind, "applies_to": applies_to, "effective": v["effective"],
                             "note": v.get("note"), **_source(v), "status": _status(v)})
        else:
            first = min(v["effective"] for v in versions)
            not_held.append({"agency": agency.upper(), "kind": kind, "applies_to": applies_to, "earliest_held": first,
                             "note": f"No version held here was in force on {day}; the earliest held is effective {first}. Any earlier version is on the listing page.", "listed_on": versions[0]["listed_on"]})
    current = {x["id"] for x in in_force}
    deviations = [{"deviation": d["deviation"], "id": d["id"], "effective": d["effective"], "modifies": d["modifies"], "names_sections": d.get("names_sections"),
                   "applies": d.get("note"), **_source(d), "status": _status(d)}
                  for d in DOCS.values() if d["kind"] == "deviation" and d["effective"] <= day and d.get("modifies") in current]
    return {"date": day, "in_force": in_force, "deviations_available": deviations, "not_held": not_held,
            "notes": ["A deviation applies to an award only when the award incorporates it; this lists what was available on the date.",
                      "APHIS's terms incorporate the USDA General Terms for Federal Awards; a supplement applies only to its own program.",
                      "The award's own document governs; a substantial amendment moves an award to the version current then."]}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# A document id or section a model names waits on the listing that carries it (#40); one a person gives passes as given.
given(mcp, {"usda_terms_contents": {"document": "usda_terms_documents"},
            "usda_terms_section": {"document": "usda_terms_documents", "section": "usda_terms_contents"},
            "usda_terms_search": {"document": "usda_terms_documents"}})
