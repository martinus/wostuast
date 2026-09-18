"""The state machine of section 4.3, one test per transition."""

from __future__ import annotations

import pytest


def event(name, **extra):
    base = {
        "session_id": "s1",
        "hook_event_name": name,
        "cwd": "/w/repo/dir",
        "transcript_path": "/t.jsonl",
        "pane": "%1",
        "pid": 4242,
        "ts": extra.pop("ts", 1000.0),
    }
    base.update(extra)
    return base


def fold(ws, *events):
    store = ws.Store()
    for one in events:
        store.apply(one)
    return store.sessions["s1"]


def test_session_start_records_the_facts(ws):
    session = fold(ws, event("SessionStart", source="startup"))
    assert session.state == "starting"
    assert session.cwd == "/w/repo/dir"
    assert session.transcript_path == "/t.jsonl"
    assert session.pane == "%1"
    assert session.pid == 4242
    assert session.last_event == "started (startup)"


def test_prompt_makes_it_working_and_is_kept(ws):
    session = fold(ws, event("SessionStart"), event("UserPromptSubmit", prompt="do it"))
    assert session.state == "working"
    assert session.last_prompt == "do it"


def test_pre_and_post_tool_use_are_working(ws):
    session = fold(
        ws,
        event("PreToolUse", tool_name="Bash", tool_input={"command": "make"}),
    )
    assert session.state == "working"
    assert session.last_tool == "Bash make"
    session = fold(
        ws,
        event("PostToolUse", tool_name="Read", tool_input={"file_path": "/w/repo/dir/a.py"}),
    )
    assert session.state == "working"
    assert session.last_tool == "Read a.py"


def test_permission_notification_needs_you(ws):
    session = fold(
        ws,
        event("PreToolUse", tool_name="Bash", tool_input={"command": "cmake --build build"}),
        event("Notification", notification_type="permission_prompt", ts=1010.0,
              message="Claude needs your permission to use Bash"),
    )
    assert session.state == "needs_you"
    assert session.attention_since == 1010.0
    assert session.reason == "permission: Bash cmake --build build"


def test_idle_notification_needs_you(ws):
    session = fold(
        ws,
        event("Notification", notification_type="idle_prompt",
              message="Claude is waiting for your input"),
    )
    assert session.state == "needs_you"
    assert session.reason == "waiting for input"


def test_notification_without_a_type_is_read_from_the_message(ws):
    session = fold(ws, event("Notification", message="Claude is waiting for your input"))
    assert session.reason == "waiting for input"
    session = fold(ws, event("Notification", message="Claude needs your permission"))
    assert session.state == "needs_you"


def test_auth_notification_does_not_need_you(ws):
    session = fold(
        ws,
        event("UserPromptSubmit", prompt="hi"),
        event("Notification", notification_type="auth_success", message="logged in"),
    )
    assert session.state == "working"


@pytest.mark.parametrize("clearing", ["UserPromptSubmit", "PostToolUse"])
def test_needs_you_clears_on_the_next_prompt_or_tool_result(ws, clearing):
    session = fold(
        ws,
        event("Notification", notification_type="permission_prompt", ts=1010.0),
        event(clearing, ts=1020.0, prompt="go on", tool_name="Bash",
              tool_input={"command": "make"}),
    )
    assert session.state == "working"
    assert session.attention_since == 0.0
    assert session.reason == ""


def test_stop_is_done(ws):
    session = fold(ws, event("UserPromptSubmit", prompt="x"), event("Stop"))
    assert session.state == "done"
    assert session.last_event == "stopped"


def test_subagent_stop_keeps_the_state(ws):
    session = fold(
        ws,
        event("UserPromptSubmit", prompt="x"),
        event("SubagentStop", agent_type="Explore"),
    )
    assert session.state == "working"
    assert session.last_event == "Explore finished"


def test_pre_compact_keeps_the_state_and_counts(ws):
    session = fold(
        ws,
        event("UserPromptSubmit", prompt="x"),
        event("PreCompact", trigger="auto"),
    )
    assert session.state == "working"
    assert session.compactions == 1
    assert "compacted" in session.last_event


def test_session_end_is_ended(ws):
    session = fold(ws, event("Stop"), event("SessionEnd", reason="prompt_input_exit"))
    assert session.state == "ended"
    assert session.end_reason == "prompt_input_exit"


def test_unknown_event_does_not_crash(ws):
    session = fold(ws, event("SomethingNew", weird=1))
    assert session.last_event == "SomethingNew"


def test_event_without_a_session_id_is_ignored(ws):
    store = ws.Store()
    assert store.apply({"hook_event_name": "Stop"}) is None
    assert store.sessions == {}


def test_a_session_whose_process_is_gone_is_dead(ws):
    session = fold(ws, event("UserPromptSubmit", prompt="x"))
    ws.mark_dead(session, alive=lambda pid: False)
    assert session.state == "dead"
    assert session.end_reason == "process gone"


def test_an_ended_session_stays_ended(ws):
    session = fold(ws, event("SessionEnd", reason="clear"))
    ws.mark_dead(session, alive=lambda pid: False)
    assert session.state == "ended"


def test_a_live_process_keeps_its_state(ws):
    session = fold(ws, event("UserPromptSubmit", prompt="x"))
    ws.mark_dead(session, alive=lambda pid: True)
    assert session.state == "working"


def test_recorded_log_gives_the_expected_sessions(ws, recorded_events):
    sessions = ws.build_sessions(recorded_events, now=1758100100.0, alive=lambda pid: True)
    by_id = {s.session_id: s for s in sessions}
    assert len(by_id) == 2
    first = by_id["7f2a1c4e-0000-4000-8000-000000000001"]
    assert first.state == "done"
    assert first.compactions == 1
    assert first.pane == "%7"
    second = by_id["9b3d2f10-0000-4000-8000-000000000002"]
    assert second.state == "ended"
    assert second.end_reason == "prompt_input_exit"


def test_old_sessions_are_dropped(ws, recorded_events):
    later = 1758100000.0 + ws.SESSION_MAX_AGE + 200
    assert ws.build_sessions(recorded_events, now=later, alive=lambda pid: True) == []


def test_sort_puts_the_longest_wait_first(ws):
    def make(state, **kw):
        return ws.Session(session_id=kw.pop("sid"), state=state, cwd="/a/b", **kw)

    rows = [
        make("done", sid="d", last_ts=50.0),
        make("needs_you", sid="n2", attention_since=20.0),
        make("working", sid="w", last_ts=60.0),
        make("ended", sid="e", last_ts=70.0),
        make("needs_you", sid="n1", attention_since=10.0),
        make("starting", sid="s", last_ts=80.0),
    ]
    assert [s.session_id for s in ws.sort_sessions(rows)] == ["n1", "n2", "w", "d", "s", "e"]
