"""The long-lived Store: fold what is new, refresh on a timer, build rows."""

from __future__ import annotations

import pytest


from conftest import event


@pytest.fixture
def store(ws, stub_git):
    """A Store with git and liveness answered, so tests stay about the Store."""
    return ws.Store()


def test_it_folds_only_what_is_new(ws, store):
    ws.append_event(event("SessionStart"))
    store.refresh(now=1000.0, alive=lambda p: True)
    assert len(store.rows) == 1
    assert store.rows[0]["state"] == "done"

    ws.append_event(event("UserPromptSubmit", prompt="go", ts=1001.0))
    assert store.refresh(now=1001.0, alive=lambda p: True) is True
    assert store.rows[0]["state"] == "working"


def test_refresh_says_when_nothing_changed(ws, store):
    ws.append_event(event("SessionStart"))
    store.refresh(now=1000.0, alive=lambda p: True)
    assert store.refresh(now=1001.0, alive=lambda p: True) is False


def test_time_passing_is_not_a_change(ws, store):
    """A row that aged by itself would look different every second, and the
    page would be sent the whole list for ever. It carries the moment it
    started waiting, and the page counts from there."""
    ws.append_event(event("PermissionRequest", tool_name="Bash",
                          tool_input={"command": "make"}))
    store.refresh(now=1000.0, alive=lambda p: True)
    assert store.rows[0]["since"] == 1000.0
    assert store.refresh(now=1030.0, alive=lambda p: True) is False
    assert store.refresh(now=9999.0, alive=lambda p: True) is False


def test_rows_are_replaced_whole_not_edited(ws, store):
    """Readers take the list without a lock, so it must never change under them."""
    ws.append_event(event("SessionStart"))
    store.refresh(now=1000.0, alive=lambda p: True)
    held = store.rows
    ws.append_event(event("Stop", ts=1002.0))
    store.refresh(now=1002.0, alive=lambda p: True)
    assert held is not store.rows
    assert held[0]["state"] == "done"     # the old list is untouched


def test_git_runs_once_and_then_waits(ws, monkeypatch):
    calls: list[list[str]] = []

    def fake(dirs):
        calls.append(sorted(dirs))
        return {d: ws.GitFacts(repo="repo", branch="main") for d in dirs}

    monkeypatch.setattr(ws, "git_facts_many", fake)
    store = ws.Store()
    ws.append_event(event("SessionStart"))
    store.refresh(now=1000.0, alive=lambda p: True)
    assert calls == [["/w/repo/dir"]]

    # a finished edit asks for git again, but not before the interval is up
    ws.append_event(event("PostToolUse", tool_name="Edit",
                          tool_input={"file_path": "/w/repo/dir/a.py"}, ts=1002.0))
    store.refresh(now=1002.0, alive=lambda p: True)
    assert len(calls) == 1, "git ran again too soon"

    ws.append_event(event("PostToolUse", tool_name="Edit",
                          tool_input={"file_path": "/w/repo/dir/a.py"}, ts=1020.0))
    store.refresh(now=1020.0, alive=lambda p: True)
    assert len(calls) == 2


def test_only_writing_tools_ask_for_git(ws):
    assert ws.touched_the_tree("Stop", {})
    assert ws.touched_the_tree("PostToolUse", {"tool_name": "Edit"})
    assert ws.touched_the_tree("PostToolUse", {"tool_name": "Bash"})
    assert not ws.touched_the_tree("PostToolUse", {"tool_name": "Read"})
    assert not ws.touched_the_tree("PreToolUse", {"tool_name": "Edit"})
    assert not ws.touched_the_tree("Notification", {})


def test_liveness_is_checked_on_a_timer(ws, store):
    looks = []
    ws.append_event(event("UserPromptSubmit", prompt="go"))
    store.refresh(now=1000.0, alive=lambda p: looks.append(p) or True)
    assert len(looks) == 1
    store.refresh(now=1001.0, alive=lambda p: looks.append(p) or True)
    assert len(looks) == 1, "checked again too soon"
    store.refresh(now=1010.0, alive=lambda p: looks.append(p) or True)
    assert len(looks) == 2


def test_the_status_file_is_read_again_only_when_it_changes(ws, store):
    import os

    ws.append_event(event("SessionStart"))
    ws.write_status("s1", ws.Status(ts=1.0, name="First"))
    store.refresh(now=1000.0, alive=lambda p: True)
    assert store.rows[0]["name"] == "First"

    ws.write_status("s1", ws.Status(ts=2.0, name="Second"))
    os.utime(ws.status_path("s1"), (5, 5))
    store.refresh(now=1001.0, alive=lambda p: True)
    assert store.rows[0]["name"] == "Second"


def test_old_sessions_leave_the_rows(ws, store):
    ws.append_event(event("Stop"))
    store.refresh(now=1000.0, alive=lambda p: True)
    assert len(store.rows) == 1
    store.refresh(now=1000.0 + ws.SESSION_MAX_AGE + 10, alive=lambda p: True)
    assert store.rows == []


def test_a_row_carries_what_the_page_needs(ws, store):
    ws.append_event(event("PermissionRequest", tool_name="Bash",
                          tool_input={"command": "cmake --build build"},
                          transcript_path="/t.jsonl"))
    ws.write_status("s1", ws.Status(ts=1.0, name="Build it", model="Opus 5",
                                    context_pct=41.0))
    store.refresh(now=1000.0, alive=lambda p: True)
    got = store.rows[0]
    assert got["id"] == "s1"
    assert got["label"] == "Build it · repo/dir"
    assert got["state"] == "needs_you"
    assert got["state_word"] == "needs you"
    assert got["reason"] == "permission: Bash cmake --build build"
    assert got["branch"] == "main"
    assert got["pane"] == "%1"
    assert got["model"] == "Opus 5"
    assert got["context_pct"] == 41.0
    assert got["has_transcript"] is True


def test_a_row_holds_only_plain_values(ws, store):
    """Rows are compared with != to decide what to push, and sent as JSON."""
    import json

    ws.append_event(event("SessionStart"))
    store.refresh(now=1000.0, alive=lambda p: True)
    assert json.loads(json.dumps(store.rows)) == store.rows


def test_a_long_prompt_is_cut_before_it_reaches_the_page(ws, store):
    ws.append_event(event("UserPromptSubmit", prompt="y" * 5000))
    store.refresh(now=1000.0, alive=lambda p: True)
    assert len(store.rows[0]["last_prompt"]) == ws.PROMPT_WIDTH


def test_rows_come_out_newest_first_whatever_their_names(ws, store):
    """The one you touched last is at the top, and a finished one is at the
    bottom however lately it finished."""
    ws.append_event(event("Stop", sid="d", cwd="/w/repo/pear", ts=1005.0))
    ws.append_event(event("PermissionRequest", sid="c", cwd="/w/repo/fig",
                          tool_name="Bash", tool_input={"command": "b"}, ts=1004.0))
    ws.append_event(event("PermissionRequest", sid="b", cwd="/w/repo/apple",
                          tool_name="Bash", tool_input={"command": "a"}, ts=1001.0))
    ws.append_event(event("SessionEnd", sid="a", cwd="/w/repo/beet", ts=1006.0))
    store.refresh(now=1010.0, alive=lambda p: True)
    assert [r["id"] for r in store.rows] == ["d", "c", "b", "a"]


def test_a_refresh_asked_for_during_the_cool_down_is_not_lost(ws, monkeypatch):
    """It used to be dropped rather than deferred, so a write landing just
    after a git run left the row stale until something else asked again."""
    calls = []

    def fake(dirs):
        calls.append(sorted(dirs))
        return {d: ws.GitFacts(repo="repo", branch="main") for d in dirs}

    monkeypatch.setattr(ws, "git_facts_many", fake)
    store = ws.Store()
    ws.append_event(event("SessionStart"))
    store.refresh(now=1000.0, alive=lambda p: True)
    assert len(calls) == 1

    # an edit two seconds later, well inside the interval
    ws.append_event(event("PostToolUse", tool_name="Edit",
                          tool_input={"file_path": "/w/repo/dir/a.py"}, ts=1002.0))
    store.refresh(now=1002.0, alive=lambda p: True)
    assert len(calls) == 1, "git ran too soon"

    # and then nothing else happens at all. The ask must still be waiting.
    store.refresh(now=1003.0, alive=lambda p: True)
    assert len(calls) == 1
    store.refresh(now=1015.0, alive=lambda p: True)
    assert len(calls) == 2, "the request was dropped instead of deferred"


def test_a_session_too_old_is_forgotten_not_merely_hidden(ws, store):
    """Everything hung off a session id is kept with it, so the daemon must
    let go of the id itself."""
    ws.append_event(event("Stop"))
    store.refresh(now=1000.0, alive=lambda p: True)
    assert "s1" in store.sessions
    store.refresh(now=1000.0 + ws.SESSION_MAX_AGE + 10, alive=lambda p: True)
    assert store.sessions == {}
