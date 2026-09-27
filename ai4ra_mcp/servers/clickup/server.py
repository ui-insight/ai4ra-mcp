"""clickup: a person's ClickUp workspaces, lists and tasks, read and written with their own token.

Upstream: https://api.clickup.com/api/v2/. The key is the person's personal API token (Settings, Apps,
Generate API Token; it starts with pk_), which ClickUp takes raw in the Authorization header, not as a
bearer. Their client sends it to this server as a bearer and this server re-sends it the way ClickUp
wants. The tools are mechanical: what a workspace holds, a task by id, tasks in a list, a task created,
commented on, updated or given a file. Which project a piece of mail belongs in is a skill's judgment,
not this server's. ClickUp allows 100 requests a minute per token.

Writes are off unless the deployment sets AI4RA_MCP_CLICKUP_WRITES=1: then the create, update, comment and attach
tools are registered too. Off, the model sees the read tools only and cannot change anything in ClickUp.
"""

from __future__ import annotations

import base64
import datetime as dt
import os
from pathlib import Path

import httpx
from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import HEADERS, HOUR, TIMEOUT_S, TTLCache, _body, api_key, missing_key
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
_WRITES = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}
KEY_ENV = "AI4RA_MCP_CLICKUP_KEY"
KEY_HOW = "Your personal API token comes from ClickUp: click your avatar, Settings, Apps, Generate API Token (it starts with pk_). It acts as you, in every workspace you belong to."
BASE = "https://api.clickup.com/api/v2"
MAX_TASKS = 100          # tasks returned per call (ClickUp pages at 100)
MAX_TEXT = 20000         # characters of description or comment per call
MAX_FILE_BYTES = 5 * 1024 * 1024
WRITES_ENV = "AI4RA_MCP_CLICKUP_WRITES"
WRITES_ON = os.environ.get(WRITES_ENV, "").strip().lower() in ("1", "true", "yes", "on")
_cache = TTLCache()

mcp = MCPServer(
    "clickup",
    instructions="ClickUp with the person's own token: who they are, their workspaces, spaces, folders and lists, tasks across the workspace or in a list or by id" + (", and a task created, updated, commented on or given a file" if WRITES_ON else "; read only in this deployment") + ". Needs a ClickUp personal API token. Read clickup_index first.",
)


async def _request(method: str, url: str, key: str, params: dict | None = None, json: dict | None = None, files: dict | None = None) -> dict | list:
    """One call to ClickUp with the person's token in the header ClickUp expects. Kept separate so tests can replace it."""
    async with httpx.AsyncClient(timeout=TIMEOUT_S, headers={**HEADERS, "Authorization": key}, follow_redirects=True) as client:
        resp = await client.request(method, url, params=params, json=json, files=files)
    return _body(resp, url)


async def _call(method: str, path: str, params: dict | None = None, json: dict | None = None, files: dict | None = None, ttl: float = 0) -> dict | list:
    key = api_key(KEY_ENV)
    if not key:
        raise LookupError(KEY_ENV)
    url = f"{BASE}/{path}"
    if ttl and method == "GET":
        # The cache key carries a fingerprint of the token, since two people's workspaces differ; never the token itself.
        fp = str(abs(hash(key)) % 10**8)
        return await _cache.remember(f"{fp}:{url}?{sorted((params or {}).items())!r}", ttl, lambda: _request(method, url, key, params))
    return await _request(method, url, key, params, json, files)


# ---- shapes ----

def _ms(value: str | int | None) -> int | None:
    """A date as ClickUp stores it: milliseconds since the epoch. Accepts an ISO date or datetime, or a number already in ms."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if s.isdigit():
        return int(s)
    d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return int(d.timestamp() * 1000)


def _iso(ms: str | int | None) -> str | None:
    if ms in (None, "", 0, "0"):
        return None
    try:
        return dt.datetime.fromtimestamp(int(ms) / 1000, tz=dt.timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def _user(u: dict | None) -> dict | None:
    if not u:
        return None
    return {"id": u.get("id"), "username": u.get("username"), "email": u.get("email")}


def slim_task(t: dict, full: bool = False) -> dict:
    status = t.get("status") or {}
    lst = t.get("list") or {}
    folder = t.get("folder") or {}
    space = t.get("space") or {}
    out = {
        "id": t.get("id"), "custom_id": t.get("custom_id"), "name": t.get("name"),
        "status": status.get("status"), "status_type": status.get("type"),
        "priority": (t.get("priority") or {}).get("priority") if isinstance(t.get("priority"), dict) else t.get("priority"),
        "assignees": [_user(a) for a in t.get("assignees") or []],
        "tags": [g.get("name") for g in t.get("tags") or [] if g.get("name")],
        "due_date": _iso(t.get("due_date")), "start_date": _iso(t.get("start_date")),
        "created": _iso(t.get("date_created")), "updated": _iso(t.get("date_updated")), "closed": _iso(t.get("date_closed")),
        "creator": _user(t.get("creator")),
        "list": {"id": lst.get("id"), "name": lst.get("name")}, "folder": {"id": folder.get("id"), "name": folder.get("name")}, "space": {"id": space.get("id")},
        "parent": t.get("parent"), "link": t.get("url"),
    }
    if full:
        out["description"] = (t.get("markdown_description") or t.get("description") or "")[:MAX_TEXT]
        out["custom_fields"] = [{"name": f.get("name"), "type": f.get("type"), "value": f.get("value")} for f in t.get("custom_fields") or [] if f.get("value") not in (None, "", [])]
        out["attachments"] = [{"id": a.get("id"), "name": a.get("title"), "size": a.get("size"), "link": a.get("url")} for a in t.get("attachments") or []]
        out["time_estimate_ms"] = t.get("time_estimate")
        out["subtasks"] = [{"id": s.get("id"), "name": s.get("name"), "status": (s.get("status") or {}).get("status")} for s in t.get("subtasks") or []]
    else:
        desc = t.get("description") or ""
        out["description_preview"] = desc[:200]
    return out


def slim_list(lst: dict) -> dict:
    folder = lst.get("folder") or {}
    return {"id": lst.get("id"), "name": lst.get("name"), "task_count": lst.get("task_count"),
            "folder": {"id": folder.get("id"), "name": folder.get("name")} if folder.get("id") else None,
            "statuses": [s.get("status") for s in lst.get("statuses") or [] if s.get("status")], "archived": lst.get("archived")}


def slim_comment(c: dict) -> dict:
    return {"id": c.get("id"), "text": (c.get("comment_text") or "")[:MAX_TEXT], "by": _user(c.get("user")), "date": _iso(c.get("date")),
            "resolved": c.get("resolved")}


def _strip(s: str | None, name: str, max_len: int) -> str:
    v = str(s or "").strip()
    if len(v) > max_len:
        raise ValueError(f"{name} is longer than {max_len} characters")
    return v


def _int_list(values: list | None, name: str) -> list[int]:
    out = []
    for v in values or []:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a list of numeric ids (find them with clickup_whoami and clickup_workspace)") from None
    return out


def _refused(e: Exception) -> dict:
    return {"error": str(e)}


def _write_tool(name: str):
    """Registers a write tool only when the deployment turned writes on; otherwise the function stays a plain function."""
    if WRITES_ON:
        return mcp.tool(name=name, annotations=_WRITES)
    return lambda fn: fn


# ---- tools ----

@mcp.tool(name="clickup_index", annotations=_READ_ONLY)
async def clickup_index() -> dict:
    """How to use the ClickUp tools. READ THIS FIRST: the key, the hierarchy, the workflow for reading and filing."""
    return {
        "upstream": "https://api.clickup.com/api/v2/ with the person's own personal API token",
        "key": {"on_this_request": api_key(KEY_ENV) is not None, "per_user": "send your own ClickUp token as a bearer token; the server holds none unless the deployment set " + KEY_ENV + " as a fallback", "how": KEY_HOW},
        "hierarchy": "workspace (ClickUp calls it a team) > space > folder (optional) > list > task > subtask. Tasks live in lists; a list has its own statuses.",
        "workflow": ["Tasks assigned to the person, or anyone, across the whole workspace: ONE call to clickup_tasks_search (assignee 'me' by default; the workspace is found on its own when the person has one). Never walk the lists with clickup_tasks to find them.",
                     "clickup_whoami: who the token is and the workspaces it reaches (members=true for the people and their ids, needed only to assign)",
                     "clickup_workspace by workspace id: every space, folder and list with their ids, in one call, when the question is about where things live or which list to file into",
                     "clickup_tasks by list id for one list's tasks; clickup_task by task id (with description, comments, attachments)",
                     "clickup_task_create in a list; clickup_task_update to change status, name, description, dates or assignees; clickup_task_comment to add a note; clickup_task_attach to put a file on it" if WRITES_ON else
                     "Writes are off in this deployment: nothing in ClickUp can be created, changed, commented on or given a file from here. When the person asks for one, say so and give them the link to do it in ClickUp."],
        "writes": WRITES_ON,
        "notes": ["Ids are strings for lists and tasks and numbers for workspaces and people; use them as the tools return them.",
                  "Dates go in as ISO (2026-10-15 or 2026-10-15T17:00:00Z) and come back as ISO; ClickUp stores milliseconds.",
                  "Descriptions and comments take markdown.",
                  "Which list a piece of work belongs in is a judgment for the person or a skill; these tools only read and write what they are told.",
                  "Every record has a link to open it in ClickUp; cite it."],
    }


async def _me_and_teams() -> tuple[dict, list]:
    me, teams = await _call("GET", "user", ttl=HOUR), await _call("GET", "team", ttl=HOUR)
    return (me or {}).get("user") or {}, (teams or {}).get("teams") or []


async def _workspace_id(given: str) -> str:
    """The workspace to search: the one named, else the person's only one; several without a name is an error."""
    wid = str(given or "").strip()
    if wid:
        return wid
    _, teams = await _me_and_teams()
    if len(teams) == 1:
        return str(teams[0].get("id"))
    if not teams:
        raise ValueError("this token reaches no workspace")
    raise ValueError("workspace_id is required: the token reaches " + ", ".join(f"{t.get('name')} ({t.get('id')})" for t in teams))


@mcp.tool(name="clickup_whoami", annotations=_READ_ONLY)
async def clickup_whoami(members: bool = False) -> dict:
    """Who the token belongs to (id, username, email) and the workspaces it can reach, each with its id and member count. members=true lists the people with their ids, which assigning a task needs.

    Args:
        members: Include each workspace's members (id, username, email). Off by default; a workspace can have hundreds.
    """
    try:
        user, teams = await _me_and_teams()
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)
    out = {"user": _user(user), "workspaces": []}
    for t in teams:
        ws = {"id": t.get("id"), "name": t.get("name"), "member_count": len(t.get("members") or [])}
        if members:
            ws["members"] = [_user((m or {}).get("user")) for m in t.get("members") or []][:500]
        out["workspaces"].append(ws)
    if not members:
        out["note"] = "Call with members=true for the people and their ids when you need to assign."
    return out


@mcp.tool(name="clickup_tasks_search", annotations=_READ_ONLY)
async def clickup_tasks_search(workspace_id: str = "", assignee: str = "me", statuses: list[str] | None = None, space_ids: list[str] | None = None,
                               list_ids: list[str] | None = None, include_closed: bool = False, contains: str = "", updated_since: str = "", page: int = 0) -> dict:
    """Tasks across a whole workspace in one call, filtered by assignee (the person by default), status, space or list: id, name, status, priority, assignees, tags, dates, list and folder, link. Use this for "my tasks", "what is assigned to X", "everything open in space Y".

    Args:
        workspace_id: The workspace (team) id; left empty, the person's only workspace is used.
        assignee: 'me' (default) for the token's own user, a numeric user id, several ids separated by commas, or 'any' for no assignee filter.
        statuses: Keep only these statuses, as the lists name them.
        space_ids: Keep only tasks in these spaces.
        list_ids: Keep only tasks in these lists.
        include_closed: Include closed and done tasks (default false).
        contains: Keep only tasks whose name contains this text (applied to the page fetched).
        updated_since: ISO date or datetime; only tasks updated after it.
        page: Page number, 0 first; 100 tasks a page, more says whether another page exists.
    """
    try:
        wid = await _workspace_id(workspace_id)
        params: dict = {"page": max(0, int(page or 0)), "subtasks": "true", "order_by": "updated", "reverse": "true"}
        who = str(assignee or "me").strip().lower()
        if who == "me":
            user, _ = await _me_and_teams()
            if not user.get("id"):
                raise ValueError("could not read the token's user id")
            params["assignees[]"] = [str(user["id"])]
        elif who and who != "any":
            params["assignees[]"] = [a.strip() for a in who.split(",") if a.strip()]
        if include_closed:
            params["include_closed"] = "true"
        if statuses:
            params["statuses[]"] = [str(x).strip() for x in statuses if str(x).strip()]
        if space_ids:
            params["space_ids[]"] = [str(x).strip() for x in space_ids if str(x).strip()]
        if list_ids:
            params["list_ids[]"] = [str(x).strip() for x in list_ids if str(x).strip()]
        if str(updated_since or "").strip():
            params["date_updated_gt"] = _ms(updated_since)
        body = await _call("GET", f"team/{wid}/task", params)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)
    tasks = [slim_task(t) for t in (body or {}).get("tasks") or []]
    if contains.strip():
        needle = contains.strip().lower()
        tasks = [t for t in tasks if needle in (t["name"] or "").lower()]
    return {"workspace_id": wid, "assignee": who, "page": params["page"], "returned": len(tasks), "tasks": tasks[:MAX_TASKS],
            "more": len((body or {}).get("tasks") or []) >= MAX_TASKS,
            "note": "Closed tasks are left out unless include_closed is true." if not include_closed else None}


@mcp.tool(name="clickup_workspace", annotations=_READ_ONLY)
async def clickup_workspace(workspace_id: str, include_archived: bool = False) -> dict:
    """Everything in a workspace that can hold tasks: its spaces, each space's folders with their lists, and the lists outside any folder, with ids, names and task counts.

    Args:
        workspace_id: The workspace (team) id from clickup_whoami.
        include_archived: Include archived spaces, folders and lists.
    """
    wid = str(workspace_id or "").strip()
    if not wid:
        return {"error": "workspace_id is required (see clickup_whoami)"}
    # ClickUp's archived=true means "archived only", so the live set is always read and the archived set is added to it on request.
    async def both(path: str, key: str) -> list:
        live = ((await _call("GET", path, {"archived": "false"}, ttl=HOUR)) or {}).get(key) or []
        if not include_archived:
            return live
        gone = ((await _call("GET", path, {"archived": "true"}, ttl=HOUR)) or {}).get(key) or []
        for g in gone:
            g["archived"] = True
        return live + gone
    try:
        out_spaces = []
        for sp in await both(f"team/{wid}/space", "spaces"):
            sid = sp.get("id")
            folders = {"folders": await both(f"space/{sid}/folder", "folders")}
            loose = {"lists": await both(f"space/{sid}/list", "lists")}
            out_spaces.append({
                "id": sid, "name": sp.get("name"), "private": sp.get("private"), "archived": bool(sp.get("archived")),
                "statuses": [s.get("status") for s in sp.get("statuses") or [] if s.get("status")],
                "folders": [{"id": f.get("id"), "name": f.get("name"), "lists": [slim_list(l) for l in f.get("lists") or []]} for f in (folders or {}).get("folders") or []],
                "lists": [slim_list(l) for l in (loose or {}).get("lists") or []],
            })
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)
    return {"workspace_id": wid, "spaces": out_spaces, "link": f"https://app.clickup.com/{wid}/home"}


@mcp.tool(name="clickup_tasks", annotations=_READ_ONLY)
async def clickup_tasks(list_id: str, contains: str = "", status: str = "", open_only: bool = True, include_closed: bool = False, page: int = 0) -> dict:
    """Tasks in a list, newest first, up to 100 a page: id, name, status, priority, assignees, tags, dates and a link. Filter by a word in the name or by status.

    Args:
        list_id: The list id from clickup_workspace.
        contains: Keep only tasks whose name contains this text (case-insensitive); ClickUp has no text search, so this is applied to the page fetched.
        status: Keep only tasks in this status (as the list names it).
        open_only: Leave out closed tasks (default). Set false, or include_closed true, to see them.
        include_closed: Same as open_only false.
        page: Page number, 0 first.
    """
    lid = str(list_id or "").strip()
    if not lid:
        return {"error": "list_id is required (see clickup_workspace)"}
    params: dict = {"page": max(0, int(page or 0)), "subtasks": "true", "order_by": "updated", "reverse": "true"}
    if include_closed or not open_only:
        params["include_closed"] = "true"
    if status.strip():
        params["statuses[]"] = status.strip()
    try:
        body = await _call("GET", f"list/{lid}/task", params)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)
    tasks = [slim_task(t) for t in (body or {}).get("tasks") or []]
    if contains.strip():
        needle = contains.strip().lower()
        tasks = [t for t in tasks if needle in (t["name"] or "").lower()]
    return {"list_id": lid, "page": params["page"], "returned": len(tasks), "tasks": tasks[:MAX_TASKS],
            "more": len((body or {}).get("tasks") or []) >= MAX_TASKS}


@mcp.tool(name="clickup_task", annotations=_READ_ONLY)
async def clickup_task(task_id: str, comments: bool = True) -> dict:
    """One task by id: everything clickup_tasks shows plus the description (markdown), custom fields, attachments, subtasks and, by default, its comments.

    Args:
        task_id: The task id (the string in its ClickUp link, e.g. 86czq1abc), or a custom id with the workspace's prefix.
        comments: Include the task's comments (default true).
    """
    tid = str(task_id or "").strip().lstrip("#")
    if not tid:
        return {"error": "task_id is required"}
    try:
        t = await _call("GET", f"task/{tid}", {"include_subtasks": "true", "include_markdown_description": "true"})
        out = slim_task(t or {}, full=True)
        if comments:
            c = await _call("GET", f"task/{tid}/comment")
            out["comments"] = [slim_comment(x) for x in (c or {}).get("comments") or []]
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)
    return out


@_write_tool(name="clickup_task_create")
async def clickup_task_create(list_id: str, name: str, description: str = "", assignees: list[int] | None = None, tags: list[str] | None = None,
                              priority: int = 0, due_date: str = "", start_date: str = "", status: str = "", parent: str = "") -> dict:
    """Create a task in a list. Returns the new task with its id and link. Nothing else in the list changes.

    Args:
        list_id: The list to create it in, from clickup_workspace.
        name: The task name, up to 500 characters.
        description: Markdown for the task's description, up to 20,000 characters.
        assignees: Numeric user ids from clickup_whoami's members.
        tags: Tag names; a tag that does not exist in the space is created.
        priority: 1 urgent, 2 high, 3 normal, 4 low; 0 leaves it unset.
        due_date: ISO date or datetime (2026-10-15 or 2026-10-15T17:00:00Z).
        start_date: ISO date or datetime.
        status: A status the list has (see clickup_workspace); the list's default when empty.
        parent: A task id to make this a subtask of.
    """
    lid = str(list_id or "").strip()
    try:
        if not lid:
            raise ValueError("list_id is required (see clickup_workspace)")
        nm = _strip(name, "name", 500)
        if not nm:
            raise ValueError("name is required")
        payload: dict = {"name": nm}
        desc = _strip(description, "description", MAX_TEXT)
        if desc:
            payload["markdown_description"] = desc
        if assignees:
            payload["assignees"] = _int_list(assignees, "assignees")
        if tags:
            payload["tags"] = [str(t).strip() for t in tags if str(t).strip()][:20]
        if priority:
            if int(priority) not in (1, 2, 3, 4):
                raise ValueError("priority must be 1 (urgent), 2 (high), 3 (normal) or 4 (low)")
            payload["priority"] = int(priority)
        if due_date:
            payload["due_date"] = _ms(due_date)
            payload["due_date_time"] = "T" in str(due_date)
        if start_date:
            payload["start_date"] = _ms(start_date)
            payload["start_date_time"] = "T" in str(start_date)
        if status.strip():
            payload["status"] = status.strip()
        if str(parent or "").strip():
            payload["parent"] = str(parent).strip()
        t = await _call("POST", f"list/{lid}/task", json=payload)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)
    return {"ok": True, "task": slim_task(t or {}, full=False), "created_in_list": lid}


@_write_tool(name="clickup_task_update")
async def clickup_task_update(task_id: str, name: str = "", description: str = "", status: str = "", priority: int = 0,
                              due_date: str = "", start_date: str = "", add_assignees: list[int] | None = None, remove_assignees: list[int] | None = None) -> dict:
    """Change a task's name, description, status, priority, dates or assignees. Only the fields given change; the description given replaces the old one.

    Args:
        task_id: The task id.
        name: New name.
        description: New description in markdown; replaces the current one.
        status: A status the task's list has.
        priority: 1 urgent, 2 high, 3 normal, 4 low.
        due_date: ISO date or datetime; 'none' clears it.
        start_date: ISO date or datetime; 'none' clears it.
        add_assignees: Numeric user ids to add.
        remove_assignees: Numeric user ids to remove.
    """
    tid = str(task_id or "").strip().lstrip("#")
    try:
        if not tid:
            raise ValueError("task_id is required")
        payload: dict = {}
        if name.strip():
            payload["name"] = _strip(name, "name", 500)
        if description.strip():
            payload["markdown_description"] = _strip(description, "description", MAX_TEXT)
        if status.strip():
            payload["status"] = status.strip()
        if priority:
            if int(priority) not in (1, 2, 3, 4):
                raise ValueError("priority must be 1 (urgent), 2 (high), 3 (normal) or 4 (low)")
            payload["priority"] = int(priority)
        for field, val in (("due_date", due_date), ("start_date", start_date)):
            if str(val).strip():
                payload[field] = None if str(val).strip().lower() == "none" else _ms(val)
                payload[field + "_time"] = "T" in str(val)
        if add_assignees or remove_assignees:
            payload["assignees"] = {"add": _int_list(add_assignees, "add_assignees"), "rem": _int_list(remove_assignees, "remove_assignees")}
        if not payload:
            raise ValueError("nothing to change: give name, description, status, priority, due_date, start_date or assignees")
        t = await _call("PUT", f"task/{tid}", json=payload)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)
    return {"ok": True, "changed": sorted(k for k in payload if not k.endswith("_time")), "task": slim_task(t or {}, full=False)}


@_write_tool(name="clickup_task_comment")
async def clickup_task_comment(task_id: str, text: str, notify_all: bool = False) -> dict:
    """Add a comment to a task. Markdown is fine. Returns the comment id.

    Args:
        task_id: The task id.
        text: The comment, up to 20,000 characters.
        notify_all: Notify everyone on the task (default false).
    """
    tid = str(task_id or "").strip().lstrip("#")
    try:
        if not tid:
            raise ValueError("task_id is required")
        body = _strip(text, "text", MAX_TEXT)
        if not body:
            raise ValueError("text is empty")
        c = await _call("POST", f"task/{tid}/comment", json={"comment_text": body, "notify_all": bool(notify_all)})
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)
    return {"ok": True, "comment_id": (c or {}).get("id"), "task_id": tid, "link": f"https://app.clickup.com/t/{tid}"}


@_write_tool(name="clickup_task_attach")
async def clickup_task_attach(task_id: str, filename: str, content_base64: str) -> dict:
    """Attach a file to a task from its base64 content (up to 5 MB). Returns the attachment's id and link.

    Args:
        task_id: The task id.
        filename: The name the file will have in ClickUp, with its extension.
        content_base64: The file's bytes as base64.
    """
    tid = str(task_id or "").strip().lstrip("#")
    try:
        if not tid:
            raise ValueError("task_id is required")
        fn = _strip(filename, "filename", 255)
        if not fn or "/" in fn or "\\" in fn:
            raise ValueError("filename must be a plain file name with its extension")
        try:
            data = base64.b64decode(str(content_base64 or "").strip(), validate=True)
        except (ValueError, TypeError):
            raise ValueError("content_base64 is not valid base64") from None
        if not data:
            raise ValueError("the file is empty")
        if len(data) > MAX_FILE_BYTES:
            raise ValueError(f"the file is larger than {MAX_FILE_BYTES // 1048576} MB")
        a = await _call("POST", f"task/{tid}/attachment", files={"attachment": (fn, data)})
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return _refused(e)
    return {"ok": True, "attachment": {"id": (a or {}).get("id"), "name": (a or {}).get("title") or fn, "size": len(data), "link": (a or {}).get("url")}, "task_id": tid}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
