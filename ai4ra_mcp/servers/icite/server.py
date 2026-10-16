"""icite: NIH iCite, the Office of Portfolio Analysis's citation metrics for the papers in PubMed.

Upstream: https://icite.od.nih.gov/api/pubs?pmids=... (JSON, no key; `fl` picks fields; iCite allows up to 1,000
PMIDs a request and asks for a gentle pace). For each paper: its citation count and citations a year, the Relative
Citation Ratio (field- and time-normalised, 1.0 is the median NIH-funded paper), the NIH percentile of that ratio,
the field citation rate and expected citations a year behind it, whether the ratio is provisional (a paper under two
years old or with few citations), the translation measures (the human, animal and molecular/cellular shares of its
MeSH terms and the Approximate Potential to Translate), and the PMIDs that cite it and that it cites. The API answers
a PMID it does not hold by leaving it out, and an overlong number by a different paper, so every record is matched to
the PMIDs asked for and the rest are said to be not found. Data is a monthly snapshot of PubMed and the NIH Open
Citation Collection; a paper indexed this month may not be in it yet.
"""

from __future__ import annotations

import re
from pathlib import Path
from statistics import median

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
API = "https://icite.od.nih.gov/api/pubs"
SITE = "https://icite.od.nih.gov/"
MAX_PMIDS = 100
LIST_CAP = 500
METRIC_FIELDS = ("pmid,doi,title,authors,year,journal,is_research_article,is_clinical,citation_count,citations_per_year,expected_citations_per_year,"
                 "field_citation_rate,relative_citation_ratio,nih_percentile,provisional,human,animal,molecular_cellular,apt,citedByClinicalArticle")
LINK_FIELDS = "pmid,doi,title,year,citation_count,cited_by,references,cited_by_clin"
_cache = TTLCache()

mcp = MCPServer(
    "icite",
    instructions="NIH iCite: citation metrics for PubMed papers by PMID (icite_metrics: Relative Citation Ratio, NIH percentile, citations, translation measures), and the papers citing or cited by one (icite_links). No key. Read icite_index first.",
)


def _ids(text: str) -> list[str]:
    return [s for s in re.split(r"[\s,;]+", text or "") if s]


async def _pubs(pmids: list[str], fields: str) -> list[dict]:
    key = f"pubs:{fields}:{','.join(pmids)}"
    body = await _cache.remember(key, DAY, lambda: get_json(API, {"pmids": ",".join(pmids), "fl": fields}))
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        raise ValueError("iCite did not return its data list")
    return data


def _round(v, places: int = 2):
    return round(v, places) if isinstance(v, (int, float)) and not isinstance(v, bool) else v


def slim_metrics(r: dict) -> dict:
    authors = r.get("authors") or []
    return {
        "pmid": r.get("pmid"), "doi": r.get("doi"), "title": r.get("title"), "year": r.get("year"), "journal": r.get("journal"),
        "first_author": (authors[0] or {}).get("fullName") if authors else None, "author_count": len(authors),
        "is_research_article": r.get("is_research_article"), "is_clinical": r.get("is_clinical"),
        "citation_count": r.get("citation_count"), "citations_per_year": _round(r.get("citations_per_year")),
        "relative_citation_ratio": _round(r.get("relative_citation_ratio")), "nih_percentile": _round(r.get("nih_percentile"), 1), "provisional": r.get("provisional"),
        "expected_citations_per_year": _round(r.get("expected_citations_per_year")), "field_citation_rate": _round(r.get("field_citation_rate")),
        "translation": {"human": _round(r.get("human")), "animal": _round(r.get("animal")), "molecular_cellular": _round(r.get("molecular_cellular")),
                        "apt": _round(r.get("apt")), "cited_by_clinical_article": r.get("citedByClinicalArticle")},
        "link": f"{SITE}analysis/result/?pmids={r.get('pmid')}",
    }


def summarize(papers: list[dict]) -> dict:
    rcrs = [p["relative_citation_ratio"] for p in papers if isinstance(p.get("relative_citation_ratio"), (int, float))]
    out: dict = {"papers": len(papers), "with_rcr": len(rcrs), "citations_total": sum(p.get("citation_count") or 0 for p in papers)}
    if rcrs:
        out.update({"rcr_median": _round(median(rcrs)), "rcr_mean": _round(sum(rcrs) / len(rcrs)), "rcr_at_or_above_1": sum(1 for r in rcrs if r >= 1.0),
                    "provisional": sum(1 for p in papers if p.get("provisional"))})
    return out


@mcp.tool(name="icite_index", annotations=_READ_ONLY)
async def icite_index() -> dict:
    """How to use the iCite tools. READ THIS FIRST: what the Relative Citation Ratio is, what the percentile compares to, when a value is provisional."""
    return {
        "upstream": f"NIH iCite at {API}, the Office of Portfolio Analysis's metrics over PubMed and the NIH Open Citation Collection; no key; a monthly snapshot",
        "workflow": ["pubmed_search or pubmed_summary (the pubmed server) or nih_publications (the nih server) for the PMIDs of the papers in question",
                     "icite_metrics with those PMIDs, up to 100 a call: each paper's citations, Relative Citation Ratio, NIH percentile and translation measures, with a summary across the set",
                     "icite_links for one paper's citing papers and references as PMIDs, which pubmed_summary turns into citations"],
        "notes": ["relative_citation_ratio (RCR) is the paper's citations a year divided by the expected rate for its field (field_citation_rate, from the papers co-cited with it), normalised so 1.0 is the median NIH-funded paper of its year; 2.0 is twice that. It is iCite's answer to comparing papers across fields and ages.",
                  "nih_percentile places the RCR among NIH-funded papers of the same year: 80.2 means it outscores 80 percent of them. It is null when iCite has no RCR for the paper.",
                  "provisional true means the RCR rests on little: the paper is under two years old or has few citations, and the value will move. Say so when quoting it.",
                  "translation: human, animal and molecular_cellular are the shares of the paper's MeSH terms in each area (they sum to about 1); apt, the Approximate Potential to Translate, is iCite's estimate of the chance the paper is cited by a clinical article; cited_by_clinical_article says whether one already has.",
                  "citation_count is from the NIH Open Citation Collection, PubMed-to-PubMed only; a book, a report or a paper outside PubMed is not counted, so the count can sit below Google Scholar's.",
                  "A PMID iCite does not hold comes back as not_found: a paper indexed this month, or one outside PubMed. iCite does not take DOIs; convert with pmc_id_convert first.",
                  "Cite as 'NIH iCite, <month>' with the paper's PMID; a biosketch or progress report quotes the RCR and percentile with the provisional flag."],
        "limits": {"metrics": f"{MAX_PMIDS} PMIDs a call", "links": f"citing and cited PMIDs listed to {LIST_CAP} each, with the full counts"},
        "link": SITE,
    }


@mcp.tool(name="icite_metrics", annotations=_READ_ONLY)
async def icite_metrics(pmids: str) -> dict:
    """Citation metrics for PubMed papers: citations, Relative Citation Ratio, NIH percentile, translation measures, and a summary across the set.

    Use it for the publication list in a biosketch, a progress report or a renewal: which papers are cited above the
    field's norm and which are too new to say.

    Args:
        pmids: Comma-separated PubMed ids, up to 100, e.g. '33744490,37391585'.
    """
    ids = _ids(pmids)
    if not ids or not all(i.isdigit() for i in ids):
        return {"error": "pmids must be comma-separated numeric PubMed ids"}
    if len(ids) > MAX_PMIDS:
        return {"error": f"at most {MAX_PMIDS} pmids a call"}
    try:
        data = await _pubs(ids, METRIC_FIELDS)
    except ValueError as e:
        return {"error": str(e), "upstream": API}
    by_pmid = {str(r.get("pmid")): r for r in data}
    papers = [slim_metrics(by_pmid[i]) for i in ids if i in by_pmid]
    out = {"requested": len(ids), "returned": len(papers), "summary": summarize(papers), "papers": papers, "link": f"{SITE}analysis/result/?pmids={','.join(ids)}"}
    missing = [i for i in ids if i not in by_pmid]
    if missing:
        out["not_found"] = missing
    return out


@mcp.tool(name="icite_links", annotations=_READ_ONLY)
async def icite_links(pmid: str) -> dict:
    """The papers citing one PubMed paper and the papers it cites, as PMIDs, with the clinical articles among the citers.

    Use it to see who built on a paper or to assemble its reference list; pubmed_summary turns the PMIDs into citations.

    Args:
        pmid: One PubMed id, e.g. '33744490'.
    """
    pid = (pmid or "").strip()
    if not pid.isdigit():
        return {"error": "pmid must be one numeric PubMed id"}
    try:
        data = await _pubs([pid], LINK_FIELDS)
    except ValueError as e:
        return {"error": str(e), "upstream": API}
    rec = next((r for r in data if str(r.get("pmid")) == pid), None)
    if rec is None:
        return {"pmid": pid, "error": "iCite does not hold this PMID: a paper indexed this month, or one outside PubMed"}
    cited_by = [str(p) for p in rec.get("cited_by") or []]
    refs = [str(p) for p in rec.get("references") or []]
    clin = [str(p) for p in rec.get("cited_by_clin") or []]
    out = {"pmid": pid, "doi": rec.get("doi"), "title": rec.get("title"), "year": rec.get("year"),
           "cited_by_count": len(cited_by), "cited_by": cited_by[:LIST_CAP], "references_count": len(refs), "references": refs[:LIST_CAP],
           "cited_by_clinical_count": len(clin), "cited_by_clinical": clin[:LIST_CAP], "link": f"{SITE}analysis/result/?pmids={pid}"}
    if len(cited_by) > LIST_CAP or len(refs) > LIST_CAP:
        out["note"] = f"Lists are cut at {LIST_CAP}; the counts are the full ones."
    return out


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# A PMID comes from the person or from another server's result (pubmed, nih); no tool here lists them, so nothing is stated (#40).
