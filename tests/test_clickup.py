"""clickup: shapes slimmed, dates converted both ways, the create and update payloads, the token sent as ClickUp wants it, and the missing-key answer."""

import datetime as dt

from ai4ra_mcp.servers.clickup import server as c

def ms(iso):
    return int(dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(tzinfo=dt.timezone.utc if "T" not in iso else None).timestamp() * 1000) if "T" not in iso \
        else int(dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)

DAY_MS, MOMENT_MS = ms("2026-10-15"), ms("2026-10-15T17:00:00Z")

TASK = {"id": "86czq1abc", "custom_id": "OSP-12", "name": "NSF budget for Smith", "status": {"status": "in progress", "type": "custom"},
        "priority": {"priority": "high", "id": "2"}, "assignees": [{"id": 123, "username": "nlayman", "email": "nlayman@uidaho.edu"}],
        "tags": [{"name": "pre-award"}], "due_date": "1760572800000", "start_date": None, "date_created": "1758844800000", "date_updated": "1758931200000", "date_closed": None,
        "creator": {"id": 123, "username": "nlayman", "email": "nlayman@uidaho.edu"}, "list": {"id": "901", "name": "Proposals"}, "folder": {"id": "77", "name": "FY26"},
        "space": {"id": "5"}, "parent": None, "url": "https://app.clickup.com/t/86czq1abc", "description": "Budget due Friday. " * 20,
        "markdown_description": "**Budget** due Friday.", "custom_fields": [{"name": "Sponsor", "type": "text", "value": "NSF"}, {"name": "Empty", "type": "text", "value": None}],
        "attachments": [{"id": "a1", "title": "budget.xlsx", "size": 1200, "url": "https://x/budget.xlsx"}], "subtasks": [{"id": "s1", "name": "Fringe", "status": {"status": "to do"}}]}


def test_task_slims_short_and_full():
    t = c.slim_task(TASK)
    assert t["id"] == "86czq1abc" and t["status"] == "in progress" and t["priority"] == "high" and t["tags"] == ["pre-award"]
    assert t["assignees"][0]["email"] == "nlayman@uidaho.edu" and t["list"] == {"id": "901", "name": "Proposals"} and t["link"].endswith("/t/86czq1abc")
    assert t["due_date"].startswith("2025-10-16") and t["start_date"] is None and len(t["description_preview"]) <= 200 and "description" not in t
    f = c.slim_task(TASK, full=True)
    assert f["description"] == "**Budget** due Friday." and f["custom_fields"] == [{"name": "Sponsor", "type": "text", "value": "NSF"}]
    assert f["attachments"][0]["name"] == "budget.xlsx" and f["subtasks"][0]["status"] == "to do"


def test_dates_convert_both_ways():
    assert c._ms("2026-10-15") == DAY_MS and c._ms("2026-10-15T17:00:00Z") == MOMENT_MS and c._ms(str(DAY_MS)) == DAY_MS and c._ms(None) is None
    assert MOMENT_MS - DAY_MS == 17 * 3600 * 1000
    assert c._iso(DAY_MS) == "2026-10-15T00:00:00+00:00" and c._iso(None) is None and c._iso("0") is None


async def test_create_builds_the_payload_and_sends_the_raw_token(monkeypatch):
    monkeypatch.setenv(c.KEY_ENV, "pk_123")
    seen = {}

    async def fake_request(method, url, key, params=None, json=None, files=None):
        seen.update(method=method, url=url, key=key, json=json)
        return {**TASK, "id": "new1"}

    monkeypatch.setattr(c, "_request", fake_request)
    out = await c.clickup_task_create("901", "File the Smith email", description="From Jane", assignees=[123], tags=["mail"], priority=2, due_date="2026-10-15T17:00:00Z", status="to do")
    assert seen["method"] == "POST" and seen["url"].endswith("/list/901/task") and seen["key"] == "pk_123"
    assert seen["json"] == {"name": "File the Smith email", "markdown_description": "From Jane", "assignees": [123], "tags": ["mail"], "priority": 2,
                            "due_date": MOMENT_MS, "due_date_time": True, "status": "to do"}
    assert out["ok"] is True and out["task"]["id"] == "new1"
    bad = await c.clickup_task_create("901", "x", priority=9)
    assert "priority" in bad["error"]


async def test_update_changes_only_what_is_given(monkeypatch):
    monkeypatch.setenv(c.KEY_ENV, "pk_123")
    seen = {}

    async def fake_request(method, url, key, params=None, json=None, files=None):
        seen.update(method=method, url=url, json=json)
        return TASK

    monkeypatch.setattr(c, "_request", fake_request)
    out = await c.clickup_task_update("86czq1abc", status="complete", due_date="none", add_assignees=[5])
    assert seen["method"] == "PUT" and seen["url"].endswith("/task/86czq1abc")
    assert seen["json"] == {"status": "complete", "due_date": None, "due_date_time": False, "assignees": {"add": [5], "rem": []}}
    assert out["changed"] == ["assignees", "due_date", "status"]
    nothing = await c.clickup_task_update("86czq1abc")
    assert "nothing to change" in nothing["error"]


async def test_tasks_filters_by_name_on_the_page(monkeypatch):
    monkeypatch.setenv(c.KEY_ENV, "pk_123")

    async def fake_request(method, url, key, params=None, json=None, files=None):
        assert params["include_closed"] == "true" and params["statuses[]"] == "to do"
        return {"tasks": [TASK, {**TASK, "id": "other", "name": "Unrelated"}]}

    monkeypatch.setattr(c, "_request", fake_request)
    out = await c.clickup_tasks("901", contains="smith", status="to do", open_only=False)
    assert out["returned"] == 1 and out["tasks"][0]["id"] == "86czq1abc" and out["more"] is False


async def test_attach_rejects_bad_base64_and_sends_a_file(monkeypatch):
    monkeypatch.setenv(c.KEY_ENV, "pk_123")
    seen = {}

    async def fake_request(method, url, key, params=None, json=None, files=None):
        seen.update(files=files)
        return {"id": "att9", "title": "note.txt", "url": "https://x/note.txt"}

    monkeypatch.setattr(c, "_request", fake_request)
    assert "base64" in (await c.clickup_task_attach("t1", "note.txt", "not base64!"))["error"]
    out = await c.clickup_task_attach("t1", "note.txt", "aGVsbG8=")
    assert seen["files"]["attachment"] == ("note.txt", b"hello") and out["attachment"]["id"] == "att9" and out["attachment"]["size"] == 5


async def test_missing_key_tells_the_model_to_stop(monkeypatch):
    monkeypatch.delenv(c.KEY_ENV, raising=False)
    out = await c.clickup_whoami()
    assert "no API key" in out["error"] and "pk_" in out["error"] and out["do_not"].startswith("Do not answer")


async def test_search_finds_the_workspace_and_filters_by_me(monkeypatch):
    monkeypatch.setenv(c.KEY_ENV, "pk_123")
    seen = []

    async def fake_request(method, url, key, params=None, json=None, files=None):
        seen.append((url.split("/api/v2/")[1], params))
        if url.endswith("/user"):
            return {"user": {"id": 95185155, "username": "Nathan Layman", "email": "nlayman@uidaho.edu"}}
        if url.endswith("/team"):
            return {"teams": [{"id": "9017952524", "name": "University of Idaho", "members": [{"user": {"id": 1}}, {"user": {"id": 2}}]}]}
        return {"tasks": [TASK, {**TASK, "id": "t2", "name": "Other"}]}

    monkeypatch.setattr(c, "_request", fake_request)
    c._cache._d.clear()
    out = await c.clickup_tasks_search(contains="smith", statuses=["in progress"], updated_since="2026-09-01")
    path, params = seen[-1]
    assert path == "team/9017952524/task" and params["assignees[]"] == ["95185155"] and params["statuses[]"] == ["in progress"]
    assert params["date_updated_gt"] == c._ms("2026-09-01") and "include_closed" not in params
    assert out["workspace_id"] == "9017952524" and out["assignee"] == "me" and out["returned"] == 1 and out["tasks"][0]["id"] == "86czq1abc"
    c._cache._d.clear()
    out = await c.clickup_tasks_search(assignee="any", include_closed=True, space_ids=["5"])
    path, params = seen[-1]
    assert "assignees[]" not in params and params["include_closed"] == "true" and params["space_ids[]"] == ["5"] and out["returned"] == 2


async def test_whoami_leaves_members_out_unless_asked(monkeypatch):
    monkeypatch.setenv(c.KEY_ENV, "pk_123")

    async def fake_request(method, url, key, params=None, json=None, files=None):
        if url.endswith("/user"):
            return {"user": {"id": 95185155, "username": "Nathan Layman", "email": "nlayman@uidaho.edu"}}
        return {"teams": [{"id": "9017952524", "name": "University of Idaho", "members": [{"user": {"id": 1, "username": "A", "email": "a@x"}}, {"user": {"id": 2, "username": "B", "email": "b@x"}}]}]}

    monkeypatch.setattr(c, "_request", fake_request)
    c._cache._d.clear()
    out = await c.clickup_whoami()
    assert out["workspaces"][0]["member_count"] == 2 and "members" not in out["workspaces"][0] and "members=true" in out["note"]
    out = await c.clickup_whoami(members=True)
    assert [m["id"] for m in out["workspaces"][0]["members"]] == [1, 2]


async def test_workspace_reads_live_spaces_and_adds_archived_only_on_request(monkeypatch):
    monkeypatch.setenv(c.KEY_ENV, "pk_123")
    calls = []

    async def fake_request(method, url, key, params=None, json=None, files=None):
        calls.append((url.split("/api/v2/")[1], params["archived"]))
        if url.endswith("/space"):
            return {"spaces": [{"id": "s1", "name": "Live" if params["archived"] == "false" else "Old", "statuses": []}]}
        if url.endswith("/folder"):
            return {"folders": []}
        return {"lists": [{"id": "l1", "name": "L", "task_count": 1, "statuses": []}]} if params["archived"] == "false" else {"lists": []}

    monkeypatch.setattr(c, "_request", fake_request)
    c._cache._d.clear()
    out = await c.clickup_workspace("9017952524")
    assert [sp["name"] for sp in out["spaces"]] == ["Live"] and out["spaces"][0]["archived"] is False and all(a == "false" for _, a in calls)
    c._cache._d.clear(); calls.clear()
    out = await c.clickup_workspace("9017952524", include_archived=True)
    assert [sp["name"] for sp in out["spaces"]] == ["Live", "Old"] and out["spaces"][1]["archived"] is True and ("team/9017952524/space", "true") in calls
