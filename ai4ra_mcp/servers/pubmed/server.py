"""pubmed: NCBI E-utilities for PubMed and the PMC ID converter.

Upstream: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/ (esearch.fcgi, esummary.fcgi, efetch.fcgi) and
https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/. No key needed: 3 requests a second without one,
shared by everyone; an optional NCBI key (AI4RA_MCP_PUBMED_KEY, sent as api_key) allows 10. Dates are YYYY,
YYYY/MM or YYYY/MM/DD; 50 ids a summary call here, 20 an efetch call (the record is the full PubMed XML), 200
an idconv call; idconv takes one id type a call. esummary carries a citation and its ids; the grant list, MeSH
terms and abstract are in the efetch record only.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import CONTACT, DAY, HOUR, TTLCache, api_key, get_json, get_text
from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
KEY_ENV = "AI4RA_MCP_PUBMED_KEY"
KEY_HOW = "Optional: a free NCBI API key comes from the settings page of an NCBI account (https://account.ncbi.nlm.nih.gov/settings/) and lifts the shared 3 requests a second to 10."
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
IDCONV = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
_DATE = re.compile(r"\d{4}(/\d{2}(/\d{2})?)?")
_cache = TTLCache()

mcp = MCPServer(
    "pubmed",
    instructions="PubMed: papers by grant number, author, affiliation or words, each with its PMID, DOI and PMCID for NIH public access compliance; PMID, PMCID and DOI conversion. Read pubmed_index first.",
)


def _params(params: dict) -> dict:
    """The parameters every E-utilities or idconv call carries: identified as this project as NCBI asks, the key when
    there is one, and the contact as email only when it is one (idconv refuses a URL there; E-utilities does not mind)."""
    p = {**params, "tool": "ai4ra-mcp"}
    if "@" in CONTACT and "/" not in CONTACT:
        p["email"] = CONTACT
    key = api_key(KEY_ENV)
    if key:
        p["api_key"] = key
    return p


async def _get(url: str, params: dict) -> dict:
    body = await get_json(url, _params(params))
    return body if isinstance(body, dict) else {}


def _text(el: ET.Element | None) -> str | None:
    """An element's text with its inline markup (italics, sub, sup) flattened, None when empty."""
    if el is None:
        return None
    t = " ".join("".join(el.itertext()).split())
    return t or None


def _slim_article(art: ET.Element) -> dict:
    """One PubmedArticle of the efetch XML read to what a compliance or review question needs."""
    cit = art.find("MedlineCitation")
    article = cit.find("Article") if cit is not None else None
    if cit is None or article is None:
        return {"error": "a record without a citation"}
    ids = {i.get("IdType"): (i.text or "").strip() for i in art.findall("PubmedData/ArticleIdList/ArticleId")}
    pmid = _text(cit.find("PMID")) or ids.get("pubmed")
    abstract = [(a.get("Label"), _text(a)) for a in article.findall("Abstract/AbstractText")]
    authors = []
    for a in article.findall("AuthorList/Author"):
        name = " ".join(p for p in (_text(a.find("LastName")), _text(a.find("Initials"))) if p) or _text(a.find("CollectiveName"))
        if name:
            authors.append({"name": name, "affiliation": _text(a.find("AffiliationInfo/Affiliation")), "orcid": next((_text(i) for i in a.findall("Identifier") if i.get("Source") == "ORCID"), None)})
    journal = article.find("Journal")
    issue = journal.find("JournalIssue") if journal is not None else None
    date = issue.find("PubDate") if issue is not None else None
    mesh = [{"term": _text(m.find("DescriptorName")), "major": (m.find("DescriptorName").get("MajorTopicYN") == "Y") or any(q.get("MajorTopicYN") == "Y" for q in m.findall("QualifierName")),
             "qualifiers": [_text(q) for q in m.findall("QualifierName")]} for m in cit.findall("MeshHeadingList/MeshHeading") if m.find("DescriptorName") is not None]
    grants = [{"grant_id": _text(g.find("GrantID")), "acronym": _text(g.find("Acronym")), "agency": _text(g.find("Agency")), "country": _text(g.find("Country"))}
              for g in article.findall("GrantList/Grant")]
    return {
        "pmid": pmid, "title": _text(article.find("ArticleTitle")),
        "abstract": " ".join(f"{label}: {text}" if label else text for label, text in abstract if text) or None,
        "authors": authors[:10], "author_count": len(authors),
        "journal": _text(journal.find("ISOAbbreviation")) if journal is not None else None, "full_journal_name": _text(journal.find("Title")) if journal is not None else None,
        "pubdate": " ".join(p for p in (_text(date.find("Year")), _text(date.find("Month")), _text(date.find("Day"))) if p) if date is not None else None,
        "volume": _text(issue.find("Volume")) if issue is not None else None, "issue": _text(issue.find("Issue")) if issue is not None else None,
        "pages": _text(article.find("Pagination/MedlinePgn")),
        "doi": ids.get("doi"), "pmcid": ids.get("pmc"),
        "publication_types": [_text(t) for t in article.findall("PublicationTypeList/PublicationType")],
        "mesh": mesh, "keywords": [_text(k) for k in cit.findall("KeywordList/Keyword") if _text(k)],
        "grants": grants, "grants_listed": bool(grants) or (cit.find("Article/GrantList") is not None),
        "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def parse_articles(xml: str) -> list[dict]:
    """Every PubmedArticle in an efetch response, in the order NCBI returned them."""
    root = ET.fromstring(xml)
    return [_slim_article(a) for a in root.findall("PubmedArticle")]


def _slim_summary(s: dict) -> dict:
    pmid = s.get("uid")
    if s.get("error"):
        return {"pmid": pmid, "error": s.get("error")}
    # articleids carries "pmc" as the bare PMCID and "pmcid" as "pmc-id: PMC...;"; the bare one is the id.
    ids = {i.get("idtype"): i.get("value") for i in s.get("articleids") or []}
    authors = [a.get("name") for a in s.get("authors") or []]
    history = {h.get("pubstatus"): h.get("date") for h in s.get("history") or []}
    return {
        "pmid": pmid, "title": s.get("title"), "authors": authors[:10], "author_count": len(authors),
        "journal": s.get("source"), "full_journal_name": s.get("fulljournalname"), "pubdate": s.get("pubdate"), "epubdate": s.get("epubdate") or None,
        "volume": s.get("volume") or None, "issue": s.get("issue") or None, "pages": s.get("pages") or None,
        "doi": ids.get("doi"), "pmcid": ids.get("pmc"), "pmc_release_date": (history.get("pmc-release") or "")[:10].replace("/", "-") or None,
        "pubtype": s.get("pubtype"), "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def _id_type(v: str) -> str | None:
    if v.isdigit():
        return "pmid"
    if re.fullmatch(r"PMC\d+", v, re.I):
        return "pmcid"
    if re.match(r"10\.\d{4,9}/\S+", v):
        return "doi"
    return None


def _slim_conversion(r: dict) -> dict:
    out = {"requested_id": r.get("requested-id"), "pmid": r.get("pmid"), "pmcid": r.get("pmcid"), "doi": r.get("doi")}
    if r.get("status") == "error" or r.get("errmsg"):
        out["errmsg"] = r.get("errmsg") or "not found"
    return out


def _ids(text: str) -> list[str]:
    return [s for s in re.split(r"[\s,;]+", text or "") if s]


async def _summaries(pmids: list[str]) -> list[dict]:
    body = await _cache.remember("summary:" + ",".join(pmids), DAY, lambda: _get(f"{EUTILS}/esummary.fcgi", {"db": "pubmed", "id": ",".join(pmids), "retmode": "json"}))
    if body.get("error"):
        raise ValueError(f"esummary: {body['error']}")
    result = body.get("result") or {}
    return [_slim_summary(result[u]) for u in result.get("uids") or [] if isinstance(result.get(u), dict)]


@mcp.tool(name="pubmed_index", annotations=_READ_ONLY)
async def pubmed_index() -> dict:
    """How to use the PubMed tools. READ THIS FIRST: the query fields, what a PMCID means for NIH public access, the pace."""
    return {
        "upstream": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/ (esearch, esummary, efetch) and https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/, no key needed",
        "key": {"required": False, "on_this_request": api_key(KEY_ENV) is not None,
                "per_user": "an NCBI key sent as a bearer token is used for this request; without one NCBI allows 3 requests a second shared by every user of this server", "how": KEY_HOW},
        "workflow": ["pubmed_search with a grant number, affiliation, author or words; note each paper's pmid and pmcid",
                     "pubmed_summary for the citations of PMIDs you already hold (from NIH RePORTER's nih_publications, a progress report, a CV)",
                     "pubmed_article for the record behind a citation: abstract, MeSH terms, keywords, publication types and the grants the paper acknowledges, which is how a paper is tied to an award or found to acknowledge none",
                     "pmc_id_convert to turn PMIDs, PMCIDs or DOIs into each other and find which papers have no PMCID"],
        "notes": ["NIH public access policy (NOT-OD-25-047, effective July 1 2025) requires a PMCID for every peer-reviewed paper arising from NIH funding, with no embargo; a paper with a PMID but no PMCID is the one to chase.",
                  "Grant number searches use the [Grant Number] field with the institute code and serial, e.g. 'AI135270[Grant Number]' or 'R01 AI135270[Grant Number]'; the bare RePORTER form 'R01AI135270' finds nothing. An institution's papers: 'University of Idaho[Affiliation]'; NIH-funded ones: add 'AND NIH[Grant Number]'.",
                  "Results are newest first by publication date. pubdate is as the journal gave it ('2023 Jun 30', '2024 Spring'); pmc_release_date is when the PMC copy became public.",
                  "pmcid None on a paper means PMC has no copy: not yet deposited, still in process, or not NIH-funded. pmc_id_convert says 'Identifier not found in PMC' for the same thing.",
                  "grants on an article are what the journal or NIH recorded (grant_id as the agency writes it, 'R01 AI135270'; agency; country). grants_listed false means the record carries no grant list at all, which is not proof the work was unfunded.",
                  "mesh terms are the indexers' subject headings, major true for the paper's main topics; a paper indexed in the last weeks may have none yet.",
                  "Cite the PubMed link (https://pubmed.ncbi.nlm.nih.gov/<pmid>/); a PMCID is also a link, https://pmc.ncbi.nlm.nih.gov/articles/<pmcid>/."],
        "limits": {"search": "1-50 papers a page, retstart for the next page", "summary": "50 PMIDs a call", "article": "20 PMIDs a call", "idconv": "200 ids a call", "pace": "3 requests a second without a key, 10 with"},
    }


@mcp.tool(name="pubmed_search", annotations=_READ_ONLY)
async def pubmed_search(term: str, from_year: str = "", to_year: str = "", retmax: int = 20, retstart: int = 0) -> dict:
    """Search PubMed and return each paper's citation and ids, newest first.

    Use it to list the papers a grant funded, an author's or an institution's papers, or papers on a topic.
    Returns the count, the query as PubMed read it, and for each paper its PMID, DOI, PMCID and link.

    Args:
        term: A PubMed query. Fields in brackets: 'AI135270[Grant Number]', 'University of Idaho[Affiliation]', 'Smith J[Author]'; combine with AND, OR, NOT.
        from_year: Earliest publication date, YYYY, YYYY/MM or YYYY/MM/DD. Empty for no lower bound.
        to_year: Latest publication date, same forms. Empty for no upper bound.
        retmax: Papers to return, 1-50. Default 20.
        retstart: First paper, 0-based, for the next page. Default 0.
    """
    q = (term or "").strip()
    if not q:
        return {"error": "term is required"}
    for label, v in (("from_year", from_year), ("to_year", to_year)):
        if v.strip() and not _DATE.fullmatch(v.strip()):
            return {"error": f"{label} must be YYYY, YYYY/MM or YYYY/MM/DD"}
    params: dict = {"db": "pubmed", "term": q, "retmode": "json", "sort": "pub_date",
                    "retmax": max(1, min(int(retmax or 20), 50)), "retstart": max(0, int(retstart or 0))}
    if from_year.strip() or to_year.strip():
        params.update({"datetype": "pdat", "mindate": from_year.strip() or "1800", "maxdate": to_year.strip() or "3000"})
    try:
        body = await _cache.remember("search:" + repr(sorted(params.items())), HOUR, lambda: _get(f"{EUTILS}/esearch.fcgi", params))
        if body.get("error"):
            return {"error": f"esearch: {body['error']}"}
        res = body.get("esearchresult") or {}
        ids = [str(i) for i in res.get("idlist") or []]
        articles = await _summaries(ids) if ids else []
    except ValueError as e:
        return {"error": str(e)}
    total = int(res.get("count") or 0)
    out = {"term": q, "query_translation": res.get("querytranslation"), "total": total, "retstart": params["retstart"], "returned": len(articles), "articles": articles}
    if params["retstart"] + len(articles) < total:
        out["next_retstart"] = params["retstart"] + len(articles)
    missing = (res.get("errorlist") or {}).get("phrasesnotfound")
    if missing:
        out["phrases_not_found"] = missing
    return out


@mcp.tool(name="pubmed_summary", annotations=_READ_ONLY)
async def pubmed_summary(pmids: str) -> dict:
    """Citations and ids for PubMed ids you already hold: title, authors, journal, date, DOI, PMCID and link for each.

    Args:
        pmids: Comma-separated PubMed ids, up to 50, e.g. '37391585,33744490'.
    """
    ids = _ids(pmids)
    if not ids or not all(i.isdigit() for i in ids):
        return {"error": "pmids must be comma-separated numeric PubMed ids"}
    if len(ids) > 50:
        return {"error": "at most 50 pmids a call"}
    try:
        articles = await _summaries(ids)
    except ValueError as e:
        return {"error": str(e)}
    return {"requested": len(ids), "returned": len(articles), "articles": articles}


@mcp.tool(name="pubmed_article", annotations=_READ_ONLY)
async def pubmed_article(pmids: str) -> dict:
    """The full PubMed record for each PMID: abstract, authors with affiliations, MeSH terms, keywords, publication types and the grants acknowledged.

    Use it to tie a paper to an award (the grants list), to see what a paper is about before citing it in a progress
    report or review, or to check whether a paper acknowledges any funding at all. pubmed_summary is enough for a citation.

    Args:
        pmids: Comma-separated PubMed ids, up to 20, e.g. '37391585,33744490'.
    """
    ids = _ids(pmids)
    if not ids or not all(i.isdigit() for i in ids):
        return {"error": "pmids must be comma-separated numeric PubMed ids"}
    if len(ids) > 20:
        return {"error": "at most 20 pmids a call"}
    try:
        xml = await _cache.remember("article:" + ",".join(ids), DAY, lambda: get_text(f"{EUTILS}/efetch.fcgi", _params({"db": "pubmed", "id": ",".join(ids), "retmode": "xml"})))
        articles = parse_articles(xml)
    except ValueError as e:
        return {"error": str(e)}
    except ET.ParseError as e:
        return {"error": f"efetch returned something other than PubMed XML: {e}"}
    found = {a.get("pmid") for a in articles}
    out = {"requested": len(ids), "returned": len(articles), "articles": articles}
    missing = [i for i in ids if i not in found]
    if missing:
        out["not_found"] = missing
    return out


@mcp.tool(name="pmc_id_convert", annotations=_READ_ONLY)
async def pmc_id_convert(ids: str) -> dict:
    """Convert between PMID, PMCID and DOI, and say which papers have no PMCID.

    Use it on a list of a grant's papers to find the ones NIH public access still needs deposited.

    Args:
        ids: Comma-separated ids, up to 200, any mix of PMIDs ('37391585'), PMCIDs ('PMC10313714') and DOIs ('10.1038/s41598-023-37437-x').
    """
    wanted = _ids(ids)
    if not wanted:
        return {"error": "ids is required"}
    if len(wanted) > 200:
        return {"error": "at most 200 ids a call"}
    groups: dict[str, list[str]] = {}
    records = []
    for v in wanted:
        kind = _id_type(v)
        if kind is None:
            records.append({"requested_id": v, "pmid": None, "pmcid": None, "doi": None, "errmsg": "not a PMID, PMCID or DOI"})
        else:
            groups.setdefault(kind, []).append(v.upper() if kind == "pmcid" else v)
    # idconv takes one id type a call, so a mixed list is one call a type.
    for kind, vals in groups.items():
        params = {"ids": ",".join(vals), "idtype": kind, "format": "json"}
        try:
            body = await _cache.remember("idconv:" + repr(sorted(params.items())), DAY, lambda p=params: _get(IDCONV, p))
        except ValueError as e:
            return {"error": str(e)}
        if body.get("status") == "error":
            msgs = [e.get("message") for e in body.get("errors") or []]
            return {"error": "idconv: " + ("; ".join(m for m in msgs if m) or "request refused")}
        records.extend(_slim_conversion(r) for r in body.get("records") or [])
    have = [r for r in records if r.get("pmcid")]
    lack = [r["requested_id"] for r in records if not r.get("pmcid")]
    return {"requested": len(wanted), "with_pmcid": len(have), "without_pmcid": lack, "records": records,
            "summary": f"{len(have)} of {len(wanted)} have a PMCID; {len(lack)} do not."}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# The ids a call names come from pubmed_search (#40); a PMID, PMCID or DOI a person pastes passes as given.
given(mcp, {"pubmed_summary": {"pmids": "pubmed_search"}, "pubmed_article": {"pmids": "pubmed_search"},
            "pmc_id_convert": {"ids": "pubmed_search"}})
