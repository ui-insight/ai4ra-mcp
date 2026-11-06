"""groupsio: the Groups.io mailing lists a person belongs to, read with their own API key.

Upstream: https://groups.io/api/v1/, which Groups.io calls alpha and may change without a new version. The key is
the person's own (https://groups.io/settings/apikeys), sent as a bearer token, and it acts as them: what a call
returns is what that person may see in that group. There is no anonymous reading, even of a public group's archive.

Read only, with no switch to change that: a post reaches everyone on a list. Members are left out too: no roster tool,
and no email address from the upstream's file, event and subscription fields. What a person typed into a message stays as written.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Literal

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.fetch import html_to_text
from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, TTLCache, api_key, get_json, missing_key
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
KEY_ENV = "AI4RA_MCP_GROUPSIO_KEY"
KEY_HOW = "Your API key comes from https://groups.io/settings/apikeys. It acts as you, in every group you belong to."
BASE = "https://groups.io/api/v1"
MAX_LIMIT = 100          # Groups.io's largest page
MAX_TEXT = 20000         # characters of one message, wiki page or event description
_LINK = re.compile(r"""<a\b[^>]*?\bhref=["']([^"']+)["'][^>]*>(.*?)</a>""", re.I | re.S)
_groups = TTLCache()

mcp = MCPServer(
    "groupsio",
    instructions="Groups.io with the person's own API key, read only: their groups, a group's archive by words, topic or message, its wiki, files and calendar. No posting and no member lists. Needs a Groups.io API key. Read groupsio_index first.",
)


async def _call(endpoint: str, params: dict | None = None) -> dict:
    """One GET with the person's key. No key raises LookupError; a refusal, a 429 included, raises ValueError with what Groups.io said."""
    key = api_key(KEY_ENV)
    if not key:
        raise LookupError(KEY_ENV)
    sent = {k: v for k, v in (params or {}).items() if v not in ("", 0, None)}
    return await get_json(f"{BASE}/{endpoint}", sent, {"Authorization": f"Bearer {key}"})


def _next(body: dict) -> str | None:
    """The next page's token as a string: Groups.io's run past 2^53, which a JavaScript client's JSON would round."""
    token = body.get("next_page_token")
    return str(token) if token else None


async def _page(endpoint: str, params: dict, name: str, slim, limit: int, page_token: str) -> dict:
    """One page of a Groups.io list, slimmed, with the token for the next."""
    body = await _call(endpoint, {**params, "limit": min(max(limit, 1), MAX_LIMIT), "page_token": page_token})
    return {"total": body.get("total_count"), "has_more": bool(body.get("has_more")), "next_page_token": _next(body),
            name: [slim(item) for item in body.get("data") or []]}


async def _group(group: str) -> dict:
    """The group's settings, for its id and its address: an enterprise group's is on its own domain, and
    groups.io/g/<name>/<page> drops the page on the way there. The cache key carries a fingerprint of the key, never the key."""
    key = api_key(KEY_ENV) or ""
    return await _groups.remember(f"{abs(hash(key)) % 10**8}:{group}", DAY, lambda: _call("getgroup", {"group_name": group}))


# ---- shapes ----

def _keep_address(link: re.Match) -> str:
    """A link's label with its web address after it, unless the label is the address. A mailto: keeps its label alone."""
    href, label = link.group(1), link.group(2)
    return label if not href.lower().startswith(("http://", "https://")) or href in label else f"{label} ({href})"


def _text(html: str | None) -> str:
    return html_to_text(_LINK.sub(_keep_address, html))[1] if html else ""


def _clip(text: str) -> dict:
    return {"text": text[:MAX_TEXT], "truncated": len(text) > MAX_TEXT}


def _tags(item: dict) -> list[str]:
    return [t.get("name") for t in item.get("hashtags") or [] if t.get("name")]


def _message_link(site: str, msg_num: int | None) -> str | None:
    return f"{site}/message/{msg_num}" if site and msg_num else None


def slim_group(sub: dict) -> dict:
    """A subscription as the group it is: never the member's email, name or settings the upstream object also carries."""
    return {"group": sub.get("group_name"), "group_id": sub.get("group_id"), "members": sub.get("subs_count"), "most_recent_message": sub.get("most_recent_message")}


def slim_topic(t: dict) -> dict:
    return {"topic_id": t.get("id"), "subject": t.get("subject"), "started_by": t.get("name"), "messages": t.get("num_messages"), "created": t.get("created"),
            "most_recent_message": t.get("most_recent_message"), "summary": _text(t.get("summary")), "hashtags": _tags(t),
            "has_attachments": t.get("has_attachments"), "closed": t.get("is_closed")}


def slim_message(m: dict, site: str) -> dict:
    return {"msg_num": m.get("msg_num"), "topic_id": m.get("topic_id"), "subject": m.get("subject"), "from": m.get("name"), "user_id": m.get("user_id"),
            "created": m.get("created"), "is_reply": m.get("is_reply"), "hashtags": _tags(m),
            **_clip(m.get("body") or "" if m.get("is_plain_text") else _text(m.get("body"))),
            "attachments": [{"filename": a.get("filename"), "media_type": a.get("media_type"), "download_url": a.get("download_url")} for a in m.get("attachments") or []],
            "link": _message_link(site, m.get("msg_num"))}


def slim_result(r: dict, site: str) -> dict:
    return {"msg_num": r.get("msg_num"), "topic_id": r.get("topic_id"), "subject": r.get("subject"), "from": r.get("name"), "user_id": r.get("user_id"),
            "created": r.get("created"), "messages_in_topic": r.get("num_msgs_in_topic"), "summary": _text(r.get("summary")), "hashtags": _tags(r),
            "has_attachments": r.get("has_attachments"), "link": _message_link(site, r.get("msg_num"))}


def slim_wiki(w: dict) -> dict:
    return {"page_id": w.get("id"), "title": w.get("title"), "path": w.get("path"), "updated": w.get("updated"), "revisions": w.get("rev_count")}


def slim_wiki_result(w: dict) -> dict:
    return {"page_id": w.get("id"), "title": w.get("title"), "updated": w.get("updated"), "revisions": w.get("rev_count"), "snippet": _text(w.get("snippet"))}


def slim_file(f: dict) -> dict:
    """A file, folder or link, `type` as Groups.io gives it: never the uploader's email the upstream object carries."""
    return {"name": f.get("name"), "description": f.get("desc"), "type": f.get("type"), "path": f.get("path"), "size": f.get("size"), "items": f.get("count"),
            "media_type": f.get("media_type"), "created": f.get("created"), "updated": f.get("updated"), "uploaded_by": f.get("display_name"),
            "download_url": f.get("download_url"), "url": f.get("url")}


def slim_event(e: dict, site: str) -> dict:
    """An event: never the organizer's email or phone the upstream object carries."""
    return {"event_id": e.get("id"), "name": e.get("name"), "group": e.get("group_name"), "start": e.get("start_time"), "end": e.get("end_time"), "timezone": e.get("timezone"),
            "all_day": e.get("all_day"), "location": e.get("location"), "organizer": e.get("organizer_name"), "rsvp": e.get("rsvp"),
            "description": _clip(_text(e.get("description"))), "calendar": f"{site}/calendar" if site else None}


def _refused(e: Exception) -> dict:
    return {"error": str(e), "do_not": "Do not answer this from memory. Tell the person what Groups.io said."}


# ---- tools ----

@mcp.tool(name="groupsio_index", annotations=_READ_ONLY)
async def groupsio_index() -> dict:
    """How to use the Groups.io tools. READ THIS FIRST: the key, what each tool reads, what is left out."""
    return {
        "upstream": f"{BASE}/ with the person's own API key; Groups.io calls this API alpha",
        "key": {"on_this_request": api_key(KEY_ENV) is not None, "per_user": "send your own Groups.io API key as a bearer token", "how": KEY_HOW},
        "workflow": ["groupsio_groups: the groups the person belongs to, with the name every other tool takes",
                     "groupsio_search: a group's messages by words; groupsio_topics: its threads, newest activity first",
                     "groupsio_topic by group and topic_id: a thread's messages in order; groupsio_message by group and msg_num: one message",
                     "groupsio_wiki, groupsio_files and groupsio_events: a group's wiki, files and calendar"],
        "left_out": "Posting, moderating, RSVPs and votes (read only, always), member lists and email addresses, chats, photos, polls and databases. When the person asks for one, say so.",
        "notes": ["What a call returns is what this person may see; a group that hides a section refuses it, and that refusal is the answer.",
                  "A message's text has any quoted reply removed, as Groups.io separates it.",
                  "On a rate limit, wait before trying again. Groups.io does not publish its limits.",
                  "Lists page: pass next_page_token back as page_token. Cite each message's link."],
    }


@mcp.tool(name="groupsio_groups", annotations=_READ_ONLY)
async def groupsio_groups(limit: int = 100, page_token: str = "") -> dict:
    """The groups the person belongs to, each with the name the other tools take.

    Args:
        limit: Groups per page, 1 to 100.
        page_token: next_page_token from the previous page.
    """
    try:
        return await _page("getsubs", {}, "groups", slim_group, limit, page_token)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)


@mcp.tool(name="groupsio_search", annotations=_READ_ONLY)
async def groupsio_search(group: str, q: str, start_date: str = "", end_date: str = "",
                          preset_date_range: Literal["", "past_hour", "past_24_hours", "past_week", "past_month", "past_year"] = "",
                          sort: Literal["relevance", "created"] = "relevance", newest_first: bool = True,
                          limit: int = 20, page_token: str = "") -> dict:
    """Search one group's message archive. Returns each match's summary and link; read it in full with groupsio_topic or groupsio_message.

    Args:
        group: The group's name, from groupsio_groups.
        q: Words to find. `#name` limits to a hashtag and `posterid:ID` to one person's messages (their user_id).
        start_date: Earliest date, as 2026-10-15T00:00:00-07:00, in the key owner's timezone.
        end_date: Latest date, in the same form.
        preset_date_range: A preset window, used only when neither date is given.
        sort: By relevance or by date.
        newest_first: Descending order; false for ascending.
        limit: Results per page, 1 to 100.
        page_token: next_page_token from the previous page.
    """
    try:
        site = (await _group(group)).get("group_url") or ""
        return await _page("searcharchives", {"group_name": group, "q": q, "start_date": start_date, "end_date": end_date, "preset_date_range": preset_date_range,
                                              "sort_field": sort, "sort_dir": "desc" if newest_first else "asc", "exclude_sigs": "true"},
                           "results", lambda r: slim_result(r, site), limit, page_token)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)


@mcp.tool(name="groupsio_topics", annotations=_READ_ONLY)
async def groupsio_topics(group: str, limit: int = 20, page_token: str = "") -> dict:
    """One group's threads, most recent activity first, with who started each and how many messages it holds.

    Args:
        group: The group's name, from groupsio_groups.
        limit: Topics per page, 1 to 100.
        page_token: next_page_token from the previous page.
    """
    try:
        return await _page("gettopics", {"group_name": group}, "topics", slim_topic, limit, page_token)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)


@mcp.tool(name="groupsio_topic", annotations=_READ_ONLY)
async def groupsio_topic(group: str, topic_id: int, limit: int = 50, page_token: str = "") -> dict:
    """One thread's messages in the order they were sent, with their text, attachments and links.

    Args:
        group: The group's name, from groupsio_groups.
        topic_id: The topic's id, from groupsio_topics or groupsio_search.
        limit: Messages per page, 1 to 100.
        page_token: next_page_token from the previous page.
    """
    try:
        site = (await _group(group)).get("group_url") or ""
        body = await _call("gettopic", {"topic_id": topic_id, "sort_field": "Created", "sort_dir": "asc", "limit": min(max(limit, 1), MAX_LIMIT), "page_token": page_token})
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)
    return {"total": body.get("total_count"), "has_more": bool(body.get("has_more")), "next_page_token": _next(body),
            "messages": [slim_message(m, site) for m in body.get("data") or []]}


@mcp.tool(name="groupsio_message", annotations=_READ_ONLY)
async def groupsio_message(group: str, msg_num: int) -> dict:
    """One message by its number within a group, with its text, attachments and link.

    Args:
        group: The group's name, from groupsio_groups.
        msg_num: The message's number in that group, from groupsio_search or groupsio_topic.
    """
    try:
        found = await _group(group)  # getmessage takes only a group's id
        return slim_message(await _call("getmessage", {"group_id": found.get("id"), "msg_num": msg_num}), found.get("group_url") or "")
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)


@mcp.tool(name="groupsio_wiki", annotations=_READ_ONLY)
async def groupsio_wiki(group: str, q: str = "", page_id: int = 0, path: str = "", limit: int = 50, page_token: str = "") -> dict:
    """One group's wiki: one page's text by page_id or path, pages matching q, or else the list of pages.

    Args:
        group: The group's name, from groupsio_groups.
        q: Words to find across the wiki.
        page_id: Read this page, from this tool's results.
        path: Read the page at this path, from this tool's list.
        limit: Pages per page of results, 1 to 100.
        page_token: next_page_token from the previous page.
    """
    try:
        if page_id or path:
            body = await _call("getwikipageset", {"group_name": group, "id": page_id, "path": path})
            return {**slim_wiki(body.get("page") or {}), **_clip(_text((body.get("data") or {}).get("body")))}
        if q:
            return await _page("searchwikis", {"group_name": group, "q": q}, "pages", slim_wiki_result, limit, page_token)
        return await _page("getwikipages", {"group_name": group}, "pages", slim_wiki, limit, page_token)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)


@mcp.tool(name="groupsio_files", annotations=_READ_ONLY)
async def groupsio_files(group: str, q: str = "", path: str = "", limit: int = 50, page_token: str = "") -> dict:
    """One group's files: those matching q, or else what is in a folder, each with a download link. The file itself is not read here.

    Args:
        group: The group's name, from groupsio_groups.
        q: Words to find across the group's files.
        path: The folder to list; empty for the top.
        limit: Files per page, 1 to 100.
        page_token: next_page_token from the previous page.
    """
    try:
        if q:
            return await _page("searchfiles", {"group_name": group, "q": q}, "files", slim_file, limit, page_token)
        return await _page("getfiledirectory", {"group_name": group, "path": path}, "files", slim_file, limit, page_token)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)


@mcp.tool(name="groupsio_events", annotations=_READ_ONLY)
async def groupsio_events(group: str = "", start: str = "", end: str = "", event_id: int = 0, limit: int = 50, page_token: str = "") -> dict:
    """One group's calendar from a date forward, or one event by event_id.

    Args:
        group: The group's name, from groupsio_groups. Required unless event_id is given.
        start: Earliest date, YYYY-MM-DD; today when empty.
        end: Latest date, YYYY-MM-DD.
        event_id: Read this one event instead, from this tool's results.
        limit: Events per page, 1 to 100.
        page_token: next_page_token from the previous page.
    """
    if not (event_id or group.strip()):
        return {"error": "name a group, or an event_id"}
    try:
        if event_id:
            event = await _call("getevent", {"event_id": event_id})
            return slim_event(event, (await _group(event.get("group_name"))).get("group_url") or "")
        site = (await _group(group)).get("group_url") or ""
        return await _page("getevents", {"group_name": group, "start": start or dt.date.today().isoformat(), "end": end}, "events", lambda e: slim_event(e, site), limit, page_token)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)


given(mcp, {
    "groupsio_search": {"group": "groupsio_groups"},
    "groupsio_topics": {"group": "groupsio_groups"},
    "groupsio_topic": {"group": "groupsio_groups", "topic_id": "groupsio_topics"},
    "groupsio_message": {"group": "groupsio_groups", "msg_num": "groupsio_search"},
    "groupsio_wiki": {"group": "groupsio_groups"},
    "groupsio_files": {"group": "groupsio_groups"},
    "groupsio_events": {"group": "groupsio_groups"},
})

register_prompts(mcp, Path(__file__).parent / "skills")
