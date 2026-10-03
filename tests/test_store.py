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


def test_a_resume_outside_tmux_takes_the_old_pane_and_pid_away(ws, store):
    """A session ran in pane %5 and ended. Resumed later in a plain terminal,
    its hook wrote `"pane": ""` -- and only a pane that was there counted, so
    the row kept %5, and jump, send and an answer went to whatever %5 held by
    then: a shell, which runs the text, or another agent. A pid of 0 kept the
    old, dead pid, and `mark_dead` buried the running session as killed.
    The daemon's own `Declined` record carries neither key, and must take
    neither away."""
    ws.append_event(event("SessionStart", pane="%5", pid=4242, ts=1000.0))
    ws.append_event(event("SessionEnd", reason="other", ts=1001.0))
    ws.append_event(event("SessionStart", source="resume", pane="", pid=0,
                          ts=1002.0))
    store.refresh(now=1002.0, alive=lambda pid: False)
    session = store.sessions["s1"]
    assert (session.pane, session.pid) == ("", 0)
    assert store.rows[0]["pane"] == "" and store.rows[0]["state"] == "done"

    ws.append_event(event("SessionStart", source="resume", pane="%9", pid=77,
                          ts=1003.0))
    ws.append_event({"session_id": "s1", "hook_event_name": "Declined",
                     "key": "1.000000", "ts": 1004.0})
    store.refresh(now=1004.0, alive=lambda pid: True)
    assert (session.pane, session.pid) == ("%9", 77)


def recorded_stop_failure(**changes):
    """The `StopFailure` Claude Code 2.1.285 sent, as this test's session."""
    import json
    from conftest import FIXTURES

    line = json.loads((FIXTURES / "stop_failure.jsonl").read_text())
    line.update(session_id="s1", cwd="/w/repo/dir", pane="%1", pid=4242)
    line.update(changes)
    return line


def test_an_api_error_ends_the_turn_and_says_why(ws, store):
    """Claude Code fires `StopFailure` instead of `Stop` when an API error --
    a spend limit, a login, an overload -- ends the turn. It was not
    registered, so the row read "working" over an agent that had stopped,
    and the error was in the transcript and nowhere on the row. The agent
    cannot go on until the reader acts, so it is amber, with Claude Code's
    own sentence as the reason; the next prompt takes it back to work."""
    assert "StopFailure" in ws.HOOK_EVENTS
    ws.append_event(event("UserPromptSubmit", prompt="go", ts=1000.0))
    ws.append_event(recorded_stop_failure(ts=1005.0))
    store.refresh(now=1005.0, alive=lambda p: True)
    row = store.rows[0]
    assert row["state"] == "needs_you", row
    assert row["reason"] == ("stopped: There's an issue with the selected "
                             "model (claude-nonexistent-model-9). It may not "
                             "exist or you may not have access to it."), row
    assert row["since"] == 1005.0

    ws.append_event(event("UserPromptSubmit", prompt="go on", ts=1010.0))
    store.refresh(now=1010.0, alive=lambda p: True)
    assert store.rows[0]["state"] == "working"
    assert "stopped" not in store.rows[0]["reason"]


def test_an_api_error_with_no_words_is_named_by_its_kind(ws, store):
    """`last_assistant_message` is what the recorded payload carried; one
    without it still says what stopped the agent, from `error`."""
    ws.append_event(event("UserPromptSubmit", prompt="go", ts=1000.0))
    ws.append_event(recorded_stop_failure(
        ts=1005.0, error="rate_limit", last_assistant_message=""))
    store.refresh(now=1005.0, alive=lambda p: True)
    assert store.rows[0]["reason"] == "stopped: usage limit reached"


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


def test_a_row_holds_only_plain_values(ws, store):
    """Rows are compared with != to decide what to push, and sent as JSON."""
    import json

    ws.append_event(event("SessionStart"))
    store.refresh(now=1000.0, alive=lambda p: True)
    assert json.loads(json.dumps(store.rows)) == store.rows


def test_a_long_prompt_is_cut_before_it_reaches_the_page(ws, store):
    ws.append_event(event("UserPromptSubmit", prompt="y" * 5000))
    store.refresh(now=1000.0, alive=lambda p: True)
    # The prompt reaches the page inside `last_event`, and only cut.
    assert store.rows[0]["last_event"] == "prompt: " + ws.clip("y" * 5000,
                                                             ws.PROMPT_WIDTH)
    assert len(store.rows[0]["last_event"]) <= len("prompt: ") + ws.PROMPT_WIDTH


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


# --- a snooze (#355) -----------------------------------------------------------


def asks(ws, sid="s1", ts=1000.0, command="make"):
    ws.append_event(event("PermissionRequest", sid=sid, ts=ts, tool_name="Bash",
                          tool_input={"command": command}))


def test_a_snooze_holds_while_the_session_waits_on_the_same_thing(ws, store):
    asks(ws)
    store.refresh(now=1000.0, alive=lambda p: True)
    assert store.snooze("s1", True) is True
    store.refresh(now=1050.0, alive=lambda p: True)
    assert store.rows[0]["snoozed"] is True
    assert store.rows[0]["state"] == "needs_you"     # it still waits
    assert ws.read_snoozed() == {"s1": 1000.0}


def test_a_snooze_ends_when_the_session_moves_on(ws, store):
    """No timer and no setting: the next thing that happens wakes it. An
    answer and a new question are both that."""
    asks(ws)
    store.refresh(now=1000.0, alive=lambda p: True)
    store.snooze("s1", True)
    ws.append_event(event("PostToolUse", ts=1010.0, tool_name="Bash"))
    ws.append_event(event("Stop", ts=1020.0))
    asks(ws, ts=1030.0, command="make install")
    store.refresh(now=1030.0, alive=lambda p: True)
    assert store.rows[0]["state"] == "needs_you"
    assert store.rows[0]["snoozed"] is False


def test_a_second_question_in_the_same_wait_wakes_it_too(ws, store):
    """Two questions in a row, with no turn between: the session was in the
    one state all along, so the moment it became so did not move, and the
    snooze held over a question the reader never saw."""
    asks(ws)
    store.refresh(now=1000.0, alive=lambda p: True)
    store.snooze("s1", True)
    asks(ws, ts=1030.0, command="rm -rf build")
    store.refresh(now=1030.0, alive=lambda p: True)
    assert store.rows[0]["snoozed"] is False


def test_only_a_session_that_needs_you_is_snoozed(ws, store):
    ws.append_event(event("SessionStart"))
    store.refresh(now=1000.0, alive=lambda p: True)
    assert store.snooze("s1", True) is False
    assert store.snooze("nope", True) is False
    assert ws.read_snoozed() == {}


def test_a_snooze_outlives_the_daemon_and_wakes_by_hand(ws, stub_git):
    asks(ws)
    first = ws.Store()
    first.refresh(now=1000.0, alive=lambda p: True)
    first.snooze("s1", True)
    again = ws.Store()
    again.refresh(now=1001.0, alive=lambda p: True)
    assert again.rows[0]["snoozed"] is True
    assert again.snooze("s1", False) is False
    again.refresh(now=1002.0, alive=lambda p: True)
    assert again.rows[0]["snoozed"] is False
    assert ws.read_snoozed() == {}


def test_a_snooze_that_no_longer_holds_leaves_the_file(ws, store):
    """The file is pruned on the next write, so it does not grow by one entry
    a question for ever."""
    asks(ws, sid="a")
    asks(ws, sid="b")
    store.refresh(now=1000.0, alive=lambda p: True)
    store.snooze("a", True)
    ws.append_event(event("Stop", sid="a", ts=1010.0))
    store.refresh(now=1010.0, alive=lambda p: True)
    store.snooze("b", True)
    assert set(ws.read_snoozed()) == {"b"}


def test_a_snooze_file_that_is_not_ours_is_read_as_none(ws):
    ws.snoozed_path().parent.mkdir(parents=True, exist_ok=True)
    ws.snoozed_path().write_text('{"a": "x", "b": true, "c": 5}')
    assert ws.read_snoozed() == {"c": 5.0}
    ws.snoozed_path().write_text("[1]")
    assert ws.read_snoozed() == {}
