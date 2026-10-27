"""Offline checks on the usda server: the stored copies are the ones the manifest names, sections are found by number
and title, long sections come whole in pieces, deviations attach to the sections they name, and the version for an
award's date is the held one in force then. With poppler installed, every PDF is converted again and must give the
stored sections exactly."""

import hashlib
import json
import shutil

import pytest

from ai4ra_mcp.servers.usda import convert
from ai4ra_mcp.servers.usda import server as usda
from ai4ra_mcp.servers.usda import process

FEDERAL = "usda-general-terms-conditions-2025"
APHIS = "tcs-for-award-feb14-2026-until-amended_0"


@pytest.mark.parametrize("doc_id", list(usda.DOCS))
def test_stored_copy_is_the_manifests(doc_id):
    e = usda.DOCS[doc_id]
    raw = (usda.DATA / "pdf" / f"{doc_id}.pdf").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == e["sha256"] and len(raw) == e["bytes"]
    assert len(usda.SECTIONS[doc_id]["sections"]) == e["sections"]
    assert e["source_url"].startswith(("https://www.usda.gov/", "https://www.aphis.usda.gov/"))
    assert usda._source(e)["copy"] == f"{usda.COPY_BASE}{doc_id}.pdf"


def test_deviations_name_their_sections():
    names = {e["deviation"]: e["names_sections"] for e in usda.DOCS.values() if e["deviation"]}
    assert names["2026-USDA-0001-F"] == ["10.0", "10.6", "10.7", "10.8", "10.9"]
    assert names["2026-USDA-0001-M"] == ["9.0", "9.6", "9.7", "9.8", "9.9"]
    assert names["2026-USDA-0002-F"] == ["12.2", "13.6", "12.2.2", "13.5"]
    assert names["2026-USDA-0002-M"] == ["11.2", "12.7", "11.2.2", "12.6"]


async def test_section_by_number_carries_its_source_and_deviations():
    r = await usda.usda_terms_section(FEDERAL, "13.5")
    assert r["title"] and r["link"].startswith(usda.DOCS[FEDERAL]["source_url"] + "#page=")
    assert r["saved"] == "2026-10-27" and r["status"] == "current"
    assert [d["deviation"] for d in r["deviations"]] == ["2026-USDA-0002-F"]
    r = await usda.usda_terms_section(FEDERAL, "10.7")
    assert [d["deviation"] for d in r["deviations"]] == ["2026-USDA-0001-F"]


async def test_section_by_title_and_by_deviation_number():
    r = await usda.usda_terms_section(APHIS, "patents and inventions")
    assert r["title"] == "PATENTS AND INVENTIONS" and r["number"] is None
    r = await usda.usda_terms_section("2026-USDA-0001-F", "10.6")
    assert r["title"] == "Research Security Training" and r["modifies"] == FEDERAL


async def test_long_section_comes_whole_in_pieces():
    whole = next(s for s in usda.SECTIONS[FEDERAL]["sections"] if s["num"] == "3.0")["text"]
    assert len(whole) > usda.PIECE
    got, offset = "", 0
    while True:
        r = await usda.usda_terms_section(FEDERAL, "3.0", offset)
        got += r["text"]
        if "next_offset" not in r:
            break
        assert r["total_chars"] == len(whole)
        offset = r["next_offset"]
    assert got == whole


async def test_unknowns_are_refused():
    assert "error" in await usda.usda_terms_contents("nifa-terms")
    assert "error" in await usda.usda_terms_section(FEDERAL, "99.9")
    assert "error" in await usda.usda_terms_for_award("July 10")


async def test_search_puts_titles_first():
    r = await usda.usda_terms_search("prior approval", FEDERAL)
    assert r["sections"][0]["section"] == "1.15" and r["sections"][0]["in_title"]
    assert all(h["id"] == FEDERAL for h in r["sections"])


async def test_for_award_gives_the_held_version_in_force():
    r = await usda.usda_terms_for_award("2026-07-10")
    assert {x["id"] for x in r["in_force"]} == {FEDERAL, "usda-mia-general-terms-conditions-2025", APHIS}
    assert {d["deviation"] for d in r["deviations_available"]} == {"2026-USDA-0001-F", "2026-USDA-0001-M", "2026-USDA-0002-F", "2026-USDA-0002-M"}
    r = await usda.usda_terms_for_award("2026-06-10")
    assert {d["deviation"] for d in r["deviations_available"]} == {"2026-USDA-0001-F", "2026-USDA-0001-M"}
    # APHIS's own example: an award effective 2025-09-25 is under the March 2025 terms, which are not held here
    r = await usda.usda_terms_for_award("2025-09-25")
    assert r["in_force"] == [] and any(x["agency"] == "APHIS" and x["earliest_held"] == "2026-02-14" for x in r["not_held"])


@pytest.mark.skipif(not (shutil.which("pdftohtml") and shutil.which("pdfinfo")), reason="needs poppler")
@pytest.mark.parametrize("doc_id", list(usda.DOCS))
def test_conversion_reproduces_the_stored_sections(doc_id):
    doc, report = convert.convert(usda.DATA / "pdf" / f"{doc_id}.pdf", usda.DOCS[doc_id]["source_url"])
    assert doc is not None, report
    assert doc == json.loads((usda.DATA / "sections" / f"{doc_id}.json").read_text(encoding="utf-8"))


def test_body_lines_that_recur_are_kept():
    # once dropped as running headers: they recur in shape, but in the body, not at the same height in a page's margin
    text = lambda i: " ".join(s["text"] for s in usda.SECTIONS[i]["sections"])
    assert "5. Section 10.6 is replaced in full with the following:" in text("2026-usda-0001-f-deviation")
    assert "8. Section 9.9 is replaced in full with the following:" in text("2026-usda-0001-m-deviation")
    inventions = next(s for s in usda.SECTIONS["nwsgc-supplemental"]["sections"] if s["title"] == "Inventions")["text"]
    assert inventions.endswith("your program manager and NWS.Grand.Challenge@usda.gov . Include in the subject line of the email\n\n(1) APP ID # and FAIN agreement number and (2) “INVENTION”.")
    assert all(d["reason"] != "running header or footer" or d["text"].isdigit() for i in usda.DOCS for d in usda.SECTIONS[i]["dropped"]
               if i.startswith("2026-usda-0001"))



@pytest.fixture
def scratch(tmp_path, monkeypatch):
    """A copy of the data folder for the processing to change, never the repository's."""
    data = tmp_path / "data"
    shutil.copytree(usda.DATA, data)
    monkeypatch.setattr(convert, "DATA", data)
    monkeypatch.setattr(convert, "MANIFEST", data / "manifest.json")
    monkeypatch.setattr(process, "DATA", data)
    return data


def _entry(data, doc_id):
    return next(e for e in json.loads((data / "manifest.json").read_text())["documents"] if e["id"] == doc_id)


def test_process_leaves_unchanged_pdfs_alone(scratch):
    before = (scratch / "manifest.json").read_text()
    assert {r["result"] for r in process.process("2026-11-01")} == {"unchanged"}
    assert (scratch / "manifest.json").read_text() == before


@pytest.mark.skipif(not (shutil.which("pdftohtml") and shutil.which("pdfinfo")), reason="needs poppler")
def test_process_rebuilds_a_replaced_pdf(scratch):
    # a stand-in for a new version saved over the old file: another document's PDF under this one's name
    new = (scratch / "pdf" / "2026-usda-0002-m.pdf").read_bytes()
    (scratch / "pdf" / "2026-usda-0002-f.pdf").write_bytes(new)
    results = {r["id"]: r["result"] for r in process.process("2026-11-01")}
    assert results["2026-usda-0002-f"] == "rebuilt" and results[FEDERAL] == "unchanged"
    e = _entry(scratch, "2026-usda-0002-f")
    assert e["sha256"] == hashlib.sha256(new).hexdigest() and e["saved"] == "2026-11-01" and e["stale_since"] is None
    assert e["names_sections"] == ["11.2", "12.7", "11.2.2", "12.6"]


@pytest.mark.skipif(not (shutil.which("pdftohtml") and shutil.which("pdfinfo")), reason="needs poppler")
def test_process_marks_stale_and_keeps_the_sections_when_a_pdf_fails(scratch):
    sections = (scratch / "sections" / f"{APHIS}.json").read_text()
    (scratch / "pdf" / f"{APHIS}.pdf").write_bytes(b"%PDF-1.4 not really a pdf")
    results = {r["id"]: r["result"] for r in process.process("2026-11-01")}
    assert results[APHIS].startswith("changed, conversion failed")
    e = _entry(scratch, APHIS)
    assert e["stale_since"] == "2026-11-01" and e["sha256"] == usda.DOCS[APHIS]["sha256"]
    assert (scratch / "sections" / f"{APHIS}.json").read_text() == sections


def test_process_reports_a_pdf_without_an_entry(scratch):
    shutil.copy(scratch / "pdf" / f"{APHIS}.pdf", scratch / "pdf" / "tcs-for-award-2027.pdf")
    results = {r["id"]: r for r in process.process("2026-11-01")}
    assert results["tcs-for-award-2027"]["result"].startswith("no manifest entry") and results["tcs-for-award-2027"]["entry"]["id"] == "tcs-for-award-2027"
