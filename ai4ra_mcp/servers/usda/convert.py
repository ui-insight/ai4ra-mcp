"""Split a saved terms PDF into its own sections, word for word, and record it in the manifest.

    python -m ai4ra_mcp.servers.usda.convert ID [ID ...]     one or more documents by manifest id
    python -m ai4ra_mcp.servers.usda.convert --all           every document in the manifest

The PDF is data/pdf/<id>.pdf, saved by a person (www.usda.gov refuses automated requests) or fetched (aphis.usda.gov);
its manifest entry (source URL, saved date and by whom, kind, effective date, deviation number, what a deviation
modifies) is written by hand before the conversion. The conversion writes data/sections/<id>.json and fills in the
entry's checksum, size, the PDF's own creation and modification dates, page and section counts, and, for a
deviation, the section numbers its text names. It needs `pdftohtml` and `pdfinfo` (poppler); no model is used.

Sections come from the PDF itself:
  - a document with its own contents list (dotted leaders and page numbers) is split at exactly those entries,
    matched in order; an entry not found in the body is reported, never guessed;
  - otherwise a heading is a short line standing alone after a gap, with no closing punctuation, set wholly in
    bold or in capitals centred on the page (bold is ignored when the PDF marks most of the body bold).
Dropped, and listed in the JSON: the contents list, page numbers, and running headers and footers, which are lines
in the top or bottom band of the page that recur at the same height on at least half the pages. A line that recurs
in the body is kept: "5. Section 10.6 is replaced in full with the following:" recurs in shape on one page of the
0001-F deviation and was once dropped as a header. The check then compares the sections' words with the PDF's, in
order, less the dropped lines; a conversion that fails it, or leaves a contents entry unmatched, exits 1 and writes
nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

DATA = Path(__file__).parent / "data"
MANIFEST = DATA / "manifest.json"
LEADER = re.compile(r"\.{4,}\s*\d+\s*$")
TOC_ENTRY = re.compile(r"^(\d+(?:\.\d+)*)\s+(.*?)\s*(?:\.{4,}|\s)\s*(\d+)\s*$")   # leaders, or a title too long to leave room for them
PAGE_NO = re.compile(r"^\s*(page\s+)?\d+(\s+of\s+\d+)?\s*$", re.I)
NUM = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$")
LIST = re.compile(r"^(\(?[a-z0-9]{1,4}[.)]|[•□▪◦o-])\s", re.I)
NAMED = re.compile(r"Sections?\s+\d+(?:\.\d+)+(?:\s*(?:,\s*and|,\s*or|,|and|or)\s*\d+(?:\.\d+)+)*")
SECTION_NO = re.compile(r"\d+(?:\.\d+)+")
TOP_BAND, BOTTOM_BAND, SAME_HEIGHT = 0.10, 0.88, 6


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def lines_of(pdf):
    with tempfile.TemporaryDirectory() as d:
        base = os.path.join(d, "x")
        subprocess.run(["pdftohtml", "-q", "-xml", "-i", "-nodrm", "-hidden", str(pdf), base], check=True, capture_output=True)
        root = ET.parse(base + ".xml").getroot()
    sizes = {fs.get("id"): int(fs.get("size") or 0) for fs in root.iter("fontspec")}
    out = []
    for page in root.iter("page"):
        pno, height, width = (int(page.get(k) or 0) for k in ("number", "height", "width"))
        frags = []
        for t in page.iter("text"):
            text = "".join(t.itertext())
            if not text.strip():
                continue
            b = t.find(".//b")
            bold = b is not None and "".join(b.itertext()).strip() == text.strip()
            frags.append(dict(top=int(t.get("top") or 0), left=int(t.get("left") or 0), w=int(t.get("width") or 0),
                              h=int(t.get("height") or 0), text=text, bold=bold, size=sizes.get(t.get("font"), 0)))
        frags.sort(key=lambda f: (f["top"], f["left"]))
        rows = []
        for f in frags:   # fragments within 4px vertically share a line
            if rows and abs(rows[-1][0]["top"] - f["top"]) <= 4:
                rows[-1].append(f)
            else:
                rows.append([f])
        for r in rows:
            r.sort(key=lambda f: f["left"])
            text = re.sub(r"\s+", " ", " ".join(f["text"].strip() for f in r)).strip()
            out.append(dict(page=pno, top=r[0]["top"], left=r[0]["left"], w=r[-1]["left"] + r[-1]["w"] - r[0]["left"],
                            h=max(f["h"] for f in r), width=width, height=height, text=text,
                            bold=all(f["bold"] for f in r), size=max(f["size"] for f in r)))
    return out


def in_band(l):
    return l["top"] < l["height"] * TOP_BAND or l["top"] > l["height"] * BOTTOM_BAND


def split_off(lines):
    """Return (kept lines, dropped lines with reasons, contents entries)."""
    pages = len({l["page"] for l in lines})
    shape = lambda s: re.sub(r"\d+", "#", s.lower())
    band = [l for l in lines if in_band(l)]

    def running(l):
        # the same text, digits aside, in the same band at the same height on at least half the pages
        if pages < 3 or not in_band(l):
            return False
        on = {o["page"] for o in band if shape(o["text"]) == shape(l["text"]) and abs(o["top"] - l["top"]) <= SAME_HEIGHT}
        return len(on) >= max(2, pages // 2)

    # the contents list: from the first to the last line with dotted leaders, if they sit together early on
    lead = [i for i, l in enumerate(lines) if LEADER.search(l["text"])]
    toc_span = range(lead[0], lead[-1] + 1) if len(lead) >= 3 and lines[lead[-1]]["page"] <= 5 else range(0)
    toc, pending = [], ""
    kept, dropped = [], []
    for i, l in enumerate(lines):
        if i in toc_span:
            text = (pending + " " + l["text"]).strip() if pending else l["text"]
            m = TOC_ENTRY.match(text)
            if m:
                toc.append(dict(num=m.group(1), title=m.group(2).strip(" ."), page=int(m.group(3))))
                pending = ""
            elif NUM.match(l["text"]) and not LEADER.search(l["text"]):
                pending = l["text"]           # an entry that wraps onto the next line
            elif pending:
                pending = text
            dropped.append((l, "contents list"))
            continue
        if running(l):
            dropped.append((l, "running header or footer")); continue
        if PAGE_NO.match(l["text"]) and (l["top"] > l["height"] * 0.85 or l["top"] < l["height"] * 0.08):
            dropped.append((l, "page number")); continue
        kept.append(l)
    return kept, dropped, toc


def heading_like(l, use_bold):
    t = l["text"]
    if len(t) > 140 or t.endswith((".", ",", ";", ":")) or not re.search(r"[A-Za-z]{3}", t):
        return False
    letters = re.sub(r"[^A-Za-z]", "", t)
    caps = len(letters) >= 4 and letters.isupper()
    centred = abs(l["left"] + l["w"] / 2 - l["width"] / 2) < l["width"] * 0.08 and l["left"] > l["width"] * 0.15
    return (use_bold and l["bold"]) or (caps and centred)


def find_headings(lines, toc):
    """Map line index -> (num, title, number of lines the heading takes). Also returns unmatched entries."""
    heads, missing = {}, []
    if toc:
        pos = 0
        for e in toc:
            want = norm(e["num"] + e["title"])
            hit = None
            for j in range(pos, len(lines)):
                text = norm(lines[j]["text"])
                if not text.startswith(norm(e["num"])):
                    continue
                joined, k = text, j
                while len(joined) < len(want) and k + 1 < len(lines) and k - j < 3:
                    k += 1; joined += norm(lines[k]["text"])
                if joined.startswith(want):
                    hit = (j, k); break
            if hit is None:
                missing.append(e); continue
            j, k = hit
            # a heading line may run on into body text ("1.1 Introduction These General..."): split at the title
            heads[j] = (e["num"], e["title"], k - j + 1)
            pos = k + 1
        return heads, missing
    body = [l for l in lines if l["size"]]
    use_bold = sum(l["bold"] for l in body) < 0.4 * len(body)
    i, prev = 0, None
    while i < len(lines):
        l = lines[i]
        # after a gap, or after a line that introduces it ("5. Section 10.6 is replaced in full with the following:")
        if heading_like(l, use_bold) and (prev is None or l["page"] != prev["page"] or l["top"] - prev["top"] > prev["h"] * 1.5
                                          or prev["text"].endswith(":")):
            k, text = i, l["text"]
            while k + 1 < len(lines) and heading_like(lines[k + 1], use_bold) and lines[k + 1]["page"] == l["page"] \
                    and lines[k + 1]["top"] - lines[k]["top"] <= lines[k]["h"] * 1.6:
                k += 1; text += " " + lines[k]["text"]
            m = NUM.match(text)
            heads[i] = (m.group(1), m.group(2), k - i + 1) if m else ("", text, k - i + 1)
            prev = lines[k]; i = k + 1; continue
        prev = l; i += 1
    return heads, missing


def residue(lines, j, n, num, title):
    """Text on a heading's lines after its number and title (a run-in heading), word for word."""
    words = " ".join(lines[x]["text"] for x in range(j, j + n)).split()
    need = norm(num + title)
    got, cut = "", 0
    for w in words:
        if len(got) >= len(need):
            break
        got += norm(w); cut += 1
    return " ".join(words[cut:])


def build(lines, toc):
    sizes = Counter(l["size"] for l in lines)
    bsize = sizes.most_common(1)[0][0]
    heads, missing = find_headings(lines, toc)
    centred = lambda l: abs(l["left"] + l["w"] / 2 - l["width"] / 2) < l["width"] * 0.08 and l["left"] > l["width"] * 0.15
    if not toc and 0 in heads and centred(lines[0]) and lines[0]["page"] == 1:
        del heads[0]                                  # a centred block at the very top is the document's title
    first = min(heads) if heads else len(lines)
    title_lines = [l for l in lines[:first] if l["page"] == lines[0]["page"] and (l["bold"] or l["size"] > bsize + 2 or heading_like(l, True))][:6]
    title = " ".join(l["text"] for l in title_lines)
    sections, cur, para, prev = [], None, None, None

    def flush():
        nonlocal para
        if para is not None and cur is not None:
            cur["paras"].append(para)
        para = None

    def add_line(text, l, prev):
        nonlocal para
        small = l["size"] < bsize - 1
        gap = prev is not None and (l["page"] != prev["page"] or l["top"] - prev["top"] > prev["h"] * 1.7)
        carry = prev is not None and l["page"] != prev["page"] and para is not None and not para["text"].rstrip().endswith((".", ":", ";"))
        if para is None or ((gap or LIST.match(text) or small != para["small"]) and not carry):
            flush(); para = dict(text=text, page=l["page"], small=small)
        else:
            t = para["text"]
            para["text"] = t[:-1] + text if re.search(r"[a-z]-$", t) else t + " " + text

    i = 0
    title_set = {id(l) for l in title_lines}
    while i < len(lines):
        l = lines[i]
        if i in heads:
            num, name, n = heads[i]
            flush()
            parts = num.split(".") if num else []
            level = 1 if not num or len(parts) == 1 or parts[1:] == ["0"] else min(len(parts), 3)
            cur = dict(num=num, title=name, level=level, page=l["page"], last=lines[i + n - 1]["page"], paras=[])
            sections.append(cur)
            rest = residue(lines, i, n, num, name) if toc else ""
            if rest:
                add_line(rest, lines[i + n - 1], None)
            prev = lines[i + n - 1]; i += n; continue
        if id(l) in title_set:
            i += 1; continue
        if cur is None:
            cur = dict(num="", title="Preamble", level=1, page=l["page"], last=l["page"], paras=[]); sections.append(cur)
        cur["last"] = l["page"]
        add_line(l["text"], l, prev)
        prev = l; i += 1
    flush()
    return title, title_lines, sections, missing


def words(s):
    return re.findall(r"[A-Za-z0-9]+", s.lower())


def check(raw, dropped, title_lines, sections):
    """The sections' words must be the PDF's words, in order, less the dropped lines."""
    gone = {id(l) for l, _ in dropped} | {id(l) for l in title_lines}
    pdf = words(" ".join(l["text"] for l in raw if id(l) not in gone))
    out = []
    for s in sections:
        if s["title"] != "Preamble" or s["num"]:
            out += words(s["num"] + " " + s["title"])
        for p in s["paras"]:
            out += words(p["text"])
    # a word broken across lines with a hyphen is one word in the sections and two in the PDF
    a, b = "".join(pdf), "".join(out)
    if a == b:
        return True, "words match the PDF, in order"
    k = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
    return False, f"first difference at character {k}: PDF …{a[max(0, k - 40):k + 40]}… sections …{b[max(0, k - 40):k + 40]}…"


def pdf_info(pdf):
    info = {}
    for line in subprocess.run(["pdfinfo", str(pdf)], check=True, capture_output=True, text=True).stdout.splitlines():
        k, _, v = line.partition(":")
        info[k.strip()] = v.strip()
    return info


def convert(pdf, source):
    """The sections document for one PDF, and a report; None for the document when the check fails."""
    raw = lines_of(pdf)
    kept, dropped, toc = split_off(raw)
    title, title_lines, sections, missing = build(kept, toc)
    ok, msg = check(raw, dropped, title_lines, sections)
    report = {"check": msg if ok else "FAILED: " + msg, "missing": [e["num"] + " " + e["title"] for e in missing], "dropped": len(dropped)}
    if not ok or missing:
        return None, report
    doc = dict(title=title, source=source, pages=max(l["page"] for l in raw), split="contents list" if toc else "layout",
               sections=[dict(num=s["num"], title=s["title"], level=s["level"], page_start=s["page"], page_end=s["last"],
                              text="\n\n".join(p["text"] for p in s["paras"])) for s in sections],
               dropped=[dict(page=l["page"], reason=why, text=l["text"]) for l, why in dropped])
    return doc, report


def named_sections(doc):
    """The section numbers a deviation's text names ("Sections 12.2 and 13.6", "Section 10.6 is replaced"), in order."""
    seen = []
    for s in doc["sections"]:
        for span in NAMED.findall(s["text"]):
            for n in SECTION_NO.findall(span):
                if n not in seen:
                    seen.append(n)
    return seen


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = {d["id"]: d for d in manifest["documents"]}
    ids = list(entries) if a.all else a.ids
    unknown = [i for i in ids if i not in entries]
    if not ids or unknown:
        raise SystemExit(f"name documents by manifest id, or --all; unknown: {unknown}" if unknown else "name documents by manifest id, or --all")
    failed = False
    for i in ids:
        e, pdf = entries[i], DATA / "pdf" / f"{i}.pdf"
        doc, report = convert(pdf, e["source_url"])
        print(f"{i}: {report['check']}; {report['dropped']} lines dropped" + "".join(f"\n  MISSING {m}" for m in report["missing"]))
        if doc is None:
            failed = True
            continue
        (DATA / "sections" / f"{i}.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        info, raw = pdf_info(pdf), pdf.read_bytes()
        e.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), pdf_created=info.get("CreationDate"), pdf_modified=info.get("ModDate"),
                 pages=doc["pages"], sections=len(doc["sections"]), split=doc["split"])
        if e["kind"] == "deviation":
            e["names_sections"] = named_sections(doc)
    MANIFEST.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
