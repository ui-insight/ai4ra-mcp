"""Reprocess every stored PDF whose checksum no longer matches the manifest.

    python -m ai4ra_mcp.servers.usda.process [--report FILE]

New versions arrive by hand: a person saves a PDF from the publisher in a browser (www.usda.gov refuses automated
requests) and commits it to data/pdf/. Nothing here goes online. For each PDF in data/pdf/, its sha256 is compared
with its manifest entry's:
  - the same: nothing to do;
  - different: the PDF is converted again (convert.rebuild); one that passes the word check gets new sections, its
    manifest entry is refilled (checksum, PDF dates, pages, sections, the sections a deviation names), saved is set
    to the day and stale_since is cleared; one that fails keeps its old sections and gets stale_since, so every
    answer says a newer version may exist until the conversion is fixed;
  - no entry: reported, since the entry's facts (title, agency, kind, who it applies to, effective date, deviation
    number, what it modifies, source URL, listing page) are a person's to write; add the entry and run again.
A manifest entry with no PDF is reported too.

Prints one line a document, writes the same as JSON to --report, and exits 1 when anything needs a person.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from ai4ra_mcp.servers.usda.convert import DATA, load_manifest, rebuild, save_manifest

ENTRY = {"id": "<file name without .pdf>", "agency": "usda | aphis", "kind": "general_terms | deviation | agency_terms | supplement",
         "applies_to": "", "effective": "YYYY-MM-DD", "deviation": None, "modifies": None, "title": "", "source_url": "", "listed_on": "",
         "saved": "YYYY-MM-DD", "saved_how": "by hand in a browser", "note": None, "stale_since": None, "sha256": ""}


def process(today: str) -> list[dict]:
    manifest = load_manifest()
    entries = {e["id"]: e for e in manifest["documents"]}
    pdfs = {p.stem: p for p in sorted((DATA / "pdf").glob("*.pdf"))}
    results = []
    for doc_id, pdf in pdfs.items():
        e = entries.get(doc_id)
        if e is None:
            results.append({"id": doc_id, "result": "no manifest entry: add one (the fields of `entry`) and run again", "entry": {**ENTRY, "id": doc_id}})
            continue
        if hashlib.sha256(pdf.read_bytes()).hexdigest() == e["sha256"]:
            results.append({"id": doc_id, "result": "unchanged"})
            continue
        try:
            ok, line = rebuild(e)
        except (subprocess.CalledProcessError, ET.ParseError) as err:   # a file poppler cannot read
            ok, line = False, f"{doc_id}: {type(err).__name__}"
        if ok:
            e.update(saved=today, stale_since=None)
            results.append({"id": doc_id, "result": "rebuilt", "detail": line})
        else:
            e["stale_since"] = e.get("stale_since") or today
            results.append({"id": doc_id, "result": "changed, conversion failed: marked stale", "detail": line})
    for doc_id in entries.keys() - pdfs.keys():
        results.append({"id": doc_id, "result": "manifest entry with no PDF"})
    save_manifest(manifest)
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", type=Path)
    a = ap.parse_args()
    results = process(_dt.date.today().isoformat())
    for r in results:
        print(f"{r['id']}: {r['result']}" + (f"\n  {r['detail']}" if r.get("detail") else "") + (f"\n  {json.dumps(r['entry'])}" if r.get("entry") else ""))
    if a.report:
        a.report.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    if any(r["result"] not in ("unchanged", "rebuilt") for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
