"""fetch_document: a page's embedded frames are reported, since a calendar or a schedule is often another page shown
inside the one the user names and the fetch sees only its fallback text. Fixture: NCURA's calendar page, whose
content is one iframe onto the association-management system's event list (captured 2026-10-19, nav trimmed)."""

from pathlib import Path

from ai4ra_mcp.common import fetch as f

FIX = Path(__file__).parent / "fixtures" / "general"
PAGE = "https://www.ncura.edu/education/calendar.aspx"
LIST = "https://www.ncura.edu/cvweb/cgi-bin/Eventsdll.dll/EventList?sessionbegdate=%3egetdate()-1&Range=1%2f10&ONWEBFLG=Y&REGONLINE=Y&SORT=TOPRINTFLG+DESC%2cSESSIONBEGDATE"


def test_html_page_lists_the_frames_in_order_and_marks_them_in_the_text():
    title, text, frames = f.html_page((FIX / "calendar_iframe.html").read_text(), PAGE)
    assert title == "Calendar"
    # The calendar's frame, then the relative one resolved against the page; about:blank, javascript: and the
    # tracking frame inside <noscript> are not frames a reader can follow.
    assert frames == [LIST, "https://www.ncura.edu/Education/Relative.aspx"]
    assert f"[frame: {LIST}]" in text and "[frame: https://www.ncura.edu/Education/Relative.aspx]" in text
    assert text.index("# Events Calendar") < text.index(f"[frame: {LIST}]") < text.index("Your browser does not support inline frames")
    assert "googletagmanager" not in text and "about:blank" not in text and "javascript:" not in text
    # html_to_text keeps its shape for the servers that read pages through it (the title is also the first line).
    assert f.html_to_text("<title>t</title><p>a</p>") == ("t", "t\na")


def test_html_page_without_frames():
    assert f.html_page("<html><head><title>Plain</title></head><body><p>Just text.</p></body></html>") == ("Plain", "Plain\nJust text.", [])
    # The same frame twice is one address.
    _, _, frames = f.html_page('<iframe src="https://x.example/a"></iframe><iframe src="https://x.example/a"></iframe>')
    assert frames == ["https://x.example/a"]


class _Resp:
    def __init__(self, body: str, status=200, ctype="text/html; charset=utf-8"):
        self.status_code, self.text, self.headers = status, body, {"content-type": ctype}
        self.content = body.encode()


async def test_fetch_document_reports_the_frames_with_a_note(monkeypatch):
    raw = (FIX / "calendar_iframe.html").read_text()

    async def fake_get(url, verify):
        assert url == PAGE and verify
        return _Resp(raw), url

    monkeypatch.setattr(f, "_host_is_public", lambda host: True)
    monkeypatch.setattr(f, "_get_following_redirects", fake_get)
    out = await f.fetch_document(PAGE)
    assert "error" not in out and out["kind"] == "html" and out["title"] == "Calendar"
    assert out["frames"] == [LIST, "https://www.ncura.edu/Education/Relative.aspx"]
    assert out["note"].startswith("The page embeds 2 frames") and "fetch_document" in out["note"]
    assert f"[frame: {LIST}]" in out["text"]
    # A page with no frames carries neither key.
    monkeypatch.setattr(f, "_get_following_redirects", lambda url, verify: _plain(url))
    out = await f.fetch_document(PAGE)
    assert "frames" not in out and "note" not in out and out["text"] == "Plain\nJust text."


async def _plain(url):
    return _Resp("<html><head><title>Plain</title></head><body><p>Just text.</p></body></html>"), url


async def test_a_script_shell_whose_content_is_a_frame_is_not_called_unreadable(monkeypatch):
    shell = ('<html><head><title>Shell</title><script></script><script></script><script></script></head>'
             '<body><iframe src="https://host.example/app"></iframe></body></html>')

    async def fake_get(url, verify):
        return _Resp(shell), url

    monkeypatch.setattr(f, "_host_is_public", lambda host: True)
    monkeypatch.setattr(f, "_get_following_redirects", fake_get)
    out = await f.fetch_document("https://host.example/page")
    assert "error" not in out and out["frames"] == ["https://host.example/app"]
    # Without the frame, the same shell is reported as script-rendered.
    bare = shell.replace('<iframe src="https://host.example/app"></iframe>', "<p>loading</p>")

    async def fake_bare(url, verify):
        return _Resp(bare), url

    monkeypatch.setattr(f, "_get_following_redirects", fake_bare)
    out = await f.fetch_document("https://host.example/page")
    assert out.get("script_rendered") and "frames" not in out
