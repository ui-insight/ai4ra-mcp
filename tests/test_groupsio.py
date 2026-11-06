"""groupsio: the key as a bearer, what each tool sends, shapes slimmed to text with no email address, and refusals reported."""

import json

import pytest

from ai4ra_mcp.common import http as h
from ai4ra_mcp.common.http import TTLCache
from ai4ra_mcp.servers.groupsio import server as g

SITE = "https://lists.example.edu/g/main"   # an enterprise group's address, from getgroup
FILE = {"id": 1, "object": "file", "name": "budget.pdf", "desc": "FY27", "size": 12, "path": "plans", "type": "file_type_file", "media_type": "application/pdf",
        "download_url": "https://s3/x", "display_name": "Jo", "user_name": "jo1", "email": "jo@example.org"}
SUB = {"id": 9, "group_id": 7, "group_name": "nih-admins", "nice_group_name": "NIH Admins", "subs_count": 40, "email": "me@example.org", "full_name": "Me", "signature": "Me, OSP"}
EVENT = {"id": 5, "name": "Office hours", "group_name": "nih-admins", "start_time": "2026-11-10T15:00:00-08:00", "description": "<p>Bring <b>questions</b></p>",
         "organizer_name": "Jo", "organizer_email": "jo@example.org", "organizer_phone": "555-0100"}
HTML_MSG = {"msg_num": 87, "topic_id": 3, "subject": "F&A", "name": "Jo", "user_id": 22, "is_plain_text": False, "body": "<div>Rate is <b>52%</b></div>", "quoted": "<div>old</div>",
            "raw_message": "MIME", "hashtags": [{"name": "rates"}], "attachments": [{"filename": "a.pdf", "media_type": "application/pdf", "download_url": "https://s3/a", "id": 4}]}


def _list(*items, **more):
    return {"object": "list", "total_count": len(items), "has_more": False, "next_page_token": 0, "data": list(items), **more}


@pytest.fixture
def upstream(monkeypatch):
    """Replaces the GET with canned bodies by endpoint, recording every call."""
    monkeypatch.setenv(g.KEY_ENV, "gio-key")
    calls, bodies = [], {}

    async def fake(url, params=None, headers=None):
        endpoint = url.rsplit("/", 1)[1]
        calls.append({"endpoint": endpoint, "params": params, "headers": headers})
        return bodies[endpoint]

    monkeypatch.setattr(g, "get_json", fake)
    monkeypatch.setattr(g, "_groups", TTLCache())
    bodies["getgroup"] = {"id": 7, "name": "nih-admins", "group_url": SITE}
    return calls, bodies


@pytest.mark.parametrize("tool,args", [
    (g.groupsio_groups, {}), (g.groupsio_search, {"group": "x", "q": "y"}), (g.groupsio_topics, {"group": "x"}), (g.groupsio_topic, {"group": "x", "topic_id": 1}),
    (g.groupsio_message, {"group": "x", "msg_num": 1}), (g.groupsio_wiki, {"group": "x"}), (g.groupsio_files, {"group": "x"}), (g.groupsio_events, {"group": "x"}),
])
async def test_without_a_key_every_tool_says_so(monkeypatch, tool, args):
    monkeypatch.delenv(g.KEY_ENV, raising=False)
    assert "no API key" in (await tool(**args))["error"]


async def test_the_person_s_key_goes_as_a_bearer_and_nothing_empty_is_sent(upstream):
    calls, bodies = upstream
    bodies["getsubs"] = _list(SUB)
    token = h.request_key.set("their-key")
    try:
        out = await g.groupsio_groups()
    finally:
        h.request_key.reset(token)
    assert calls[0]["headers"] == {"Authorization": "Bearer their-key"} and calls[0]["params"] == {"limit": 100}
    assert out["groups"] == [{"group": "nih-admins", "group_id": 7, "members": 40, "most_recent_message": None}]
    assert out["next_page_token"] is None


async def test_search_sends_its_filters_and_links_each_match(upstream):
    calls, bodies = upstream
    bodies["searcharchives"] = _list({"msg_num": 12, "topic_id": 3, "subject": "Rates", "name": "Jo", "summary": "the <b>rate</b> is", "body": "x" * 500})
    out = await g.groupsio_search("nih-admins", "rate #fa", preset_date_range="past_year", sort="created", limit=500)
    assert calls[1]["params"] == {"group_name": "nih-admins", "q": "rate #fa", "preset_date_range": "past_year", "sort_field": "created", "sort_dir": "desc", "exclude_sigs": "true", "limit": 100}
    hit = out["results"][0]
    assert hit["summary"] == "the rate is" and hit["link"] == f"{SITE}/message/12" and "body" not in hit


async def test_topic_reads_html_as_text_in_order_and_leaves_the_raw_message_out(upstream):
    calls, bodies = upstream
    bodies["gettopic"] = _list(HTML_MSG, {**HTML_MSG, "msg_num": 88, "is_plain_text": True, "body": "<not> html"})
    out = await g.groupsio_topic("nih-admins", 3)
    assert calls[-1]["params"]["sort_dir"] == "asc" and calls[-1]["params"]["topic_id"] == 3
    first, second = out["messages"]
    assert first["text"] == "Rate is 52%" and first["truncated"] is False and first["hashtags"] == ["rates"]
    assert first["attachments"] == [{"filename": "a.pdf", "media_type": "application/pdf", "download_url": "https://s3/a"}]
    assert first["link"] == f"{SITE}/message/87" and second["text"] == "<not> html"
    assert "MIME" not in json.dumps(out) and "old" not in json.dumps(out)


async def test_message_finds_the_group_s_id_by_name(upstream):
    calls, bodies = upstream
    bodies["getmessage"] = HTML_MSG
    out = await g.groupsio_message("nih-admins", 87)
    assert [c["endpoint"] for c in calls] == ["getgroup", "getmessage"] and calls[1]["params"] == {"group_id": 7, "msg_num": 87}
    assert out["text"] == "Rate is 52%" and out["link"] == f"{SITE}/message/87"


async def test_a_group_s_address_is_looked_up_once_per_key(upstream):
    calls, bodies = upstream
    bodies["searcharchives"] = _list()
    await g.groupsio_search("g", "a")
    await g.groupsio_search("g", "b")
    assert [c["endpoint"] for c in calls].count("getgroup") == 1
    token = h.request_key.set("another-key")
    try:
        await g.groupsio_search("g", "c")
    finally:
        h.request_key.reset(token)
    assert [c["endpoint"] for c in calls].count("getgroup") == 2


async def test_a_page_token_too_big_for_javascript_goes_out_and_back_as_a_string(upstream):
    calls, bodies = upstream
    bodies["gettopics"] = _list({"id": 1}, next_page_token=1793295515523381988)
    out = await g.groupsio_topics("g")
    assert out["next_page_token"] == "1793295515523381988"
    await g.groupsio_topics("g", page_token=out["next_page_token"])
    assert calls[-1]["params"]["page_token"] == "1793295515523381988"


def test_a_link_s_address_survives_as_text():
    out = g._text('<p>Check the source (<a href="https://x.gov/a?b=1&amp;c=2" rel="nofollow">available here</a>). Try <a href="https://y.org/">https://y.org/</a>. '
                  'Ask <a href="mailto:jo@example.org">Jo</a>.</p>')
    assert out == "Check the source (available here (https://x.gov/a?b=1&c=2)). Try https://y.org/. Ask Jo."


async def test_a_long_message_is_cut_and_says_so():
    out = g.slim_message({"msg_num": 1, "is_plain_text": True, "body": "x" * (g.MAX_TEXT + 1)}, SITE)
    assert len(out["text"]) == g.MAX_TEXT and out["truncated"] is True


async def test_wiki_chooses_page_search_or_list(upstream):
    calls, bodies = upstream
    bodies["getwikipageset"] = {"page": {"id": 2, "title": "Home", "path": "Home", "rev_count": 3}, "data": {"body": "<p>Welcome</p>"}}
    bodies["searchwikis"] = _list({"id": 2, "title": "Home", "snippet": "<b>Wel</b>come", "body": "whole page"})
    bodies["getwikipages"] = _list({"id": 2, "title": "Home", "path": "Home"})
    page = await g.groupsio_wiki("g", path="Home")
    assert page["text"] == "Welcome" and page["title"] == "Home" and calls[-1]["params"] == {"group_name": "g", "path": "Home"}
    assert (await g.groupsio_wiki("g", q="wel"))["pages"][0]["snippet"] == "Welcome" and calls[-1]["endpoint"] == "searchwikis"
    assert (await g.groupsio_wiki("g"))["pages"][0]["path"] == "Home" and calls[-1]["endpoint"] == "getwikipages"


async def test_files_chooses_search_or_folder(upstream):
    calls, bodies = upstream
    bodies["searchfiles"] = bodies["getfiledirectory"] = _list(FILE, {"name": "plans", "count": 2})
    assert (await g.groupsio_files("g", q="budget"))["files"][0]["download_url"] == "https://s3/x" and calls[-1]["endpoint"] == "searchfiles"
    out = await g.groupsio_files("g", path="plans")
    assert calls[-1]["endpoint"] == "getfiledirectory" and calls[-1]["params"]["path"] == "plans"
    assert out["files"][0]["type"] == "file_type_file" and out["files"][1]["items"] == 2


async def test_events_need_a_group_or_an_id_and_start_today_by_default(upstream):
    calls, bodies = upstream
    bodies["getevents"], bodies["getevent"] = _list(EVENT), EVENT
    assert "group" in (await g.groupsio_events())["error"] and not calls
    out = await g.groupsio_events("nih-admins")
    assert calls[-1]["params"]["start"] == g.dt.date.today().isoformat()
    assert out["events"][0]["description"]["text"] == "Bring questions" and out["events"][0]["calendar"] == f"{SITE}/calendar"
    one = await g.groupsio_events(event_id=5)
    assert one["event_id"] == 5 and one["calendar"] == f"{SITE}/calendar"


async def test_no_answer_carries_an_email_address_or_a_phone(upstream):
    _, bodies = upstream
    bodies["getsubs"], bodies["getfiledirectory"], bodies["getevents"] = _list(SUB), _list(FILE), _list(EVENT)
    out = json.dumps([await g.groupsio_groups(), await g.groupsio_files("g"), await g.groupsio_events("g")])
    assert "@example.org" not in out and "555-0100" not in out and "OSP" not in out


async def test_a_refusal_is_reported_not_raised(upstream, monkeypatch):
    async def refused(url, params=None, headers=None):
        raise ValueError('400 from groups.io: {"object":"error","type":"inadequate_permissions","extra":""}')

    monkeypatch.setattr(g, "get_json", refused)
    out = await g.groupsio_wiki("g")
    assert "inadequate_permissions" in out["error"] and "memory" in out["do_not"]


async def test_only_read_tools_are_registered():
    tools = await g.mcp.list_tools()
    assert all(t.annotations.read_only_hint for t in tools)
