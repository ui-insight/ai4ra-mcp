"""perseus, offline from Scaife Viewer responses captured 2026-10-19 in tests/fixtures/perseus/: three groups of the library root
(Plato, Aristotle, Cicero), Plato's works, the Republic's record and its two versions, Republic 1.327a in Greek and English (JSON and text),
a reference the Viewer lacks answered with another passage, a search for 'unexamined'; the URN levels, the listings with labels read from
each record, the passage with another version, the search hits, the refusals."""

import json
from pathlib import Path

from ai4ra_mcp.servers.perseus import server as p

FIX = Path(__file__).parent / "fixtures" / "perseus"
J = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in FIX.glob("*.json")}
T = {f.stem: f.read_text(encoding="utf-8") for f in FIX.glob("*.txt")}
GRC, ENG = "urn:cts:greekLit:tlg0059.tlg030.perseus-grc2", "urn:cts:greekLit:tlg0059.tlg030.perseus-eng2"


def _scaife(monkeypatch, calls=None):
    calls = calls if calls is not None else []
    by_path = {
        "/library/json/": J["root_trimmed"], "/library/urn:cts:greekLit:tlg0059/json/": J["plato"], "/library/urn:cts:greekLit:tlg0059.tlg030/json/": J["republic"],
        f"/library/{GRC}/json/": J["republic_grc2"], f"/library/{ENG}/json/": J["republic_eng2"],
        f"/library/passage/{GRC}:1.327a/json/": J["passage_grc_327a"], f"/library/passage/{ENG}:1.327a/json/": J["passage_eng_327a"],
        f"/library/passage/{GRC}:99.999z/json/": J["passage_bad"],
    }

    async def get_json(url, params=None, headers=None):
        path = url[len(p.BASE):]
        calls.append(path)
        if path.startswith("/search/json/"):
            return J["search_unexamined"]
        if path in by_path:
            return by_path[path]
        if path.startswith("/library/urn:cts:greekLit:tlg0059.tlg0") and path.endswith("/json/"):  # another of Plato's works: a record with a label
            urn = path[len("/library/"):-len("/json/")]
            return {"urn": urn, "label": "Work " + urn.rsplit(".", 1)[-1], "texts": [{"urn": urn + ".perseus-grc2"}, {"urn": urn + ".perseus-eng2"}]}
        raise ValueError(f"404 from {url}: nothing at that address")

    async def get_text(url, params=None, headers=None):
        calls.append(url[len(p.BASE):])
        if "perseus-grc2:1.327a" in url:
            return T["passage_grc_327a"]
        if "perseus-eng2:1.327a" in url:
            return T["passage_eng_327a"]
        return "some text"

    monkeypatch.setattr(p, "get_json", get_json)
    monkeypatch.setattr(p, "get_text", get_text)
    p._cache._d.clear()
    return calls


def test_urn_levels():
    assert p.urn_level("urn:cts:greekLit:tlg0059") == "group" and p.urn_level("urn:cts:greekLit:tlg0059.tlg030") == "work" and p.urn_level(GRC) == "version" and p.urn_level(GRC + ":1.327a") == "passage"
    assert p.urn_level("urn:cts:latinLit:phi0474.phi001.perseus-lat2:1.1") == "passage" and p.urn_level("Plato Republic") is None and p.urn_level("") is None


async def test_library_levels(monkeypatch):
    calls = _scaife(monkeypatch)
    root = await p.perseus_library()
    assert root["level"] == "groups" and root["returned"] == 3 and {"urn": "urn:cts:greekLit:tlg0059", "label": "Plato", "works": 37} in root["groups"]
    assert (await p.perseus_library(query="cicero"))["groups"][0]["label"] == "Cicero, Marcus Tullius" and "note" in await p.perseus_library(query="Hemingway") and calls.count("/library/json/") == 1
    plato = await p.perseus_library("urn:cts:greekLit:tlg0059")
    assert plato["level"] == "author" and plato["label"] == "Plato" and plato["returned"] == 37
    rep = next(w for w in plato["works"] if w["urn"] == "urn:cts:greekLit:tlg0059.tlg030")
    assert rep["label"] == "Republic" and rep["versions"] == [GRC, ENG] and all(w["label"] for w in plato["works"])
    work = await p.perseus_library("urn:cts:greekLit:tlg0059.tlg030")
    assert work["level"] == "work" and work["label"] == "Republic" and work["author"] == "Plato" and [v["urn"] for v in work["versions"]] == [GRC, ENG]
    eng = work["versions"][1]
    assert eng["language"] == "eng" and eng["language_name"] == "English" and eng["kind"] == "translation" and eng["description"].startswith("Plato in Twelve Volumes") and eng["first_passage"] == ENG + ":1.327-1.331"
    assert eng["contents"][0] == {"urn": ENG + ":1.327-1.331", "label": "Book 1"} and len(eng["contents"]) == 10 and eng["reader"].startswith("https://scaife.perseus.org/")
    grc = await p.perseus_library(GRC)
    assert grc["level"] == "version" and grc["label"] == "Πολιτεία" and grc["language"] == "grc" and grc["kind"] == "edition" and grc["work"] == "Republic" and grc["author"] == "Plato"
    assert "urn must be" in (await p.perseus_library(GRC + ":1.327a"))["error"] and "urn must be" in (await p.perseus_library("Plato"))["error"]
    bad = await p.perseus_library("urn:cts:greekLit:tlg9999")
    assert bad["error"].startswith("404 from") and "perseus_library" in bad["error"]


async def test_passage(monkeypatch):
    calls = _scaife(monkeypatch)
    out = await p.perseus_passage(GRC + ":1.327a", with_version=ENG)
    assert out["urn"] == GRC + ":1.327" and out["urn_requested"] == GRC + ":1.327a" and "note" not in out and out["reference"] == "Book 1 Section 327"
    assert out["author"] == "Plato" and out["work"] == "Republic" and out["version"] == {"urn": GRC, "label": "Πολιτεία", "language": "grc", "language_name": "Greek", "kind": "edition"}
    assert out["text"].startswith("κατέβην χθὲς εἰς Πειραιᾶ") and out["truncated"] is False and out["words"] == 201 and out["reader"] == "https://scaife.perseus.org/reader/" + GRC + ":1.327/"
    wv = out["with_version"]
    assert wv["urn_requested"] == ENG + ":1.327a" and wv["version"]["kind"] == "translation" and "Piraeus" in wv["text"] or wv["text"].startswith("I Socrates")
    assert f"/library/passage/{GRC}:1.327a/json/" in calls and f"/library/passage/{GRC}:1.327a/text/" in calls and f"/library/passage/{ENG}:1.327a/text/" in calls
    bad = await p.perseus_passage(GRC + ":99.999z")
    assert bad["urn"] == GRC + ":10.621" and bad["note"].startswith("The Viewer answered for " + GRC + ":10.621")
    assert "urn must be a passage" in (await p.perseus_passage(GRC))["error"]
    assert (await p.perseus_passage(GRC + ":1.327a", with_version="Shorey"))["with_version"]["error"].startswith("with_version must be")
    missing = await p.perseus_passage("urn:cts:greekLit:tlg9999.tlg001.perseus-grc1:1")
    assert missing["error"].startswith("404 from") and "perseus_search" in missing["error"]


async def test_search(monkeypatch):
    calls = _scaife(monkeypatch)
    out = await p.perseus_search("unexamined", rows=3)
    assert calls[0] == "/search/json/?q=unexamined&type=library&kind=form&page=1" and out["total"] == J["search_unexamined"]["total_count"] and out["returned"] == 3
    hit = out["hits"][0]
    assert hit["urn"] == "urn:cts:greekLit:tlg0010.tlg015.perseus-eng2:42" and hit["author"] == "Isocrates" and hit["work"] == "Evagoras" and hit["version"]["language"] == "eng"
    assert "<em>unexamined</em>" in hit["snippets"][0] and hit["reader"] == "https://scaife.perseus.org/reader/urn:cts:greekLit:tlg0010.tlg015.perseus-eng2:42/"
    assert out["link"] == "https://scaife.perseus.org/search/?q=unexamined&type=library&kind=form"
    assert "kind must be" in (await p.perseus_search("x", kind="stem"))["error"] and "query is required" in (await p.perseus_search(""))["error"]
    idx = await p.perseus_index()
    assert idx["urns"][0].startswith("A CTS URN") and "perseus_library" in idx["workflow"][0]
