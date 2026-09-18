"""The state machine of section 4.3, one test per transition."""

from __future__ import annotations

import pathlib

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


def test_pre_compact_keeps_the_state_and_is_remembered(ws):
    session = fold(
        ws,
        event("UserPromptSubmit", prompt="x"),
        event("PreCompact", trigger="auto", ts=1500.0),
    )
    assert session.state == "working"
    assert session.last_compaction == 1500.0
    assert "compacted" in session.last_event


def test_folding_the_same_events_twice_gives_the_same_answer(ws, recorded_events):
    """Handlers assign, they never accumulate. Milestone 2 folds only the new
    tail of the log, and a re-read of the same bytes must change nothing."""
    once = ws.Store()
    for one in recorded_events:
        once.apply(one)
    twice = ws.Store()
    for one in recorded_events + recorded_events:
        twice.apply(one)
    assert once.sessions == twice.sessions


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
    assert first.last_compaction > 0
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


# --- finding the agent's own process ----------------------------------------


def test_repo_name_for_every_layout(ws):
    assert ws.repo_name("/home/m/oans/.bare") == "oans"          # bare layout
    assert ws.repo_name("/home/m/myrepo/.git") == "myrepo"       # plain clone
    assert ws.repo_name("/home/m/myrepo.git") == "myrepo"        # bare clone
    assert ws.repo_name("/home/m/proj/.bare/") == "proj"         # trailing slash
    assert ws.repo_name("/home/m/p/.git/worktrees/x") == "x"
    assert ws.repo_name("") == ""
    assert ws.repo_name("   ") == ""


def test_reading_a_process_that_is_not_there(ws):
    assert ws.process_name(999999) == ""
    assert ws.process_args(999999) == ""
    assert ws.parent_pid(999999) == 0


def test_reading_our_own_process(ws):
    import os

    assert ws.parent_pid(os.getpid()) == os.getppid()
    assert ws.process_name(os.getpid()) != ""


def test_the_agent_pid_walks_past_the_shell(ws, tmp_path):
    """Claude Code runs a command hook through a shell, so our parent is that
    shell and it dies with us. Taking it for the agent showed every session as
    killed seconds after it started.
    """
    import os
    import subprocess
    import sys

    root = pathlib.Path(__file__).resolve().parents[1]
    (tmp_path / "probe.py").write_text(
        "import importlib.machinery, importlib.util, os, sys\n"
        f"loader = importlib.machinery.SourceFileLoader('w', {str(root / 'wostuast')!r})\n"
        "spec = importlib.util.spec_from_loader(loader.name, loader)\n"
        "m = importlib.util.module_from_spec(spec); sys.modules['w'] = m\n"
        "loader.exec_module(m)\n"
        "print('AGENT', m.agent_pid(), 'SHELL', os.getppid())\n"
    )
    (tmp_path / "outer.py").write_text(
        "import os, subprocess, sys\n"
        "print('CLAUDE', os.getpid(), flush=True)\n"
        "subprocess.run(['sh', '-c', sys.argv[1] + ' ' + sys.argv[2]], env=os.environ)\n"
    )
    claude = tmp_path / "claude"
    claude.symlink_to(sys.executable)

    done = subprocess.run(
        [str(claude), str(tmp_path / "outer.py"), str(claude), str(tmp_path / "probe.py")],
        capture_output=True, text=True, timeout=60,
    )
    found = {}
    for line in done.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] == "CLAUDE":
            found["claude"] = int(parts[1])
        if parts and parts[0] == "AGENT":
            found["agent"] = int(parts[1])
            found["shell"] = int(parts[3])

    assert "agent" in found, done.stdout + done.stderr
    assert found["agent"] == found["claude"], "did not walk past the shell"
    assert found["shell"] != found["claude"], "the shell was not a separate process"


def test_a_session_without_an_agent_pid_is_never_called_killed(ws):
    """Where there is no /proc we cannot find the agent. Saying nothing beats
    saying the session was killed when it is running fine."""
    session = ws.Session(session_id="s", pid=0, state="working")
    ws.mark_dead(session, alive=lambda pid: False)
    assert session.state == "working"


# --- the permission dialog ---------------------------------------------------


def test_a_permission_request_needs_you_at_once(ws):
    session = fold(
        ws,
        event("PreToolUse", tool_name="Bash", tool_input={"command": "ls ~"}, ts=1000.0),
        event("PermissionRequest", tool_name="Bash", tool_input={"command": "ls ~"},
              ts=1000.5),
    )
    assert session.state == "needs_you"
    assert session.attention_since == 1000.5
    assert session.reason == "permission: Bash ls ~"


def test_the_late_notification_does_not_undo_it(ws):
    """Notification says the same thing up to twelve seconds later. It must not
    move the waiting time forward, or the row would show the wrong age."""
    session = fold(
        ws,
        event("PreToolUse", tool_name="Bash", tool_input={"command": "ls ~"}, ts=1000.0),
        event("PermissionRequest", tool_name="Bash", tool_input={"command": "ls ~"},
              ts=1000.5),
        event("Notification", notification_type="permission_prompt",
              message="Claude needs your permission", ts=1012.0),
    )
    assert session.state == "needs_you"
    assert session.reason == "permission: Bash ls ~"


def test_approving_clears_it(ws):
    session = fold(
        ws,
        event("PermissionRequest", tool_name="Bash", tool_input={"command": "ls ~"},
              ts=1000.0),
        event("PostToolUse", tool_name="Bash", tool_input={"command": "ls ~"}, ts=1005.0),
    )
    assert session.state == "working"
    assert session.reason == ""


def test_denying_and_moving_on_clears_it(ws):
    """A denial brings no PostToolUse. The next tool call is what says the
    question was answered, so the row must not keep the old reason."""
    session = fold(
        ws,
        event("PermissionRequest", tool_name="Bash", tool_input={"command": "ls ~"},
              ts=1000.0),
        event("PreToolUse", tool_name="Read", tool_input={"file_path": "/w/repo/dir/a.py"},
              ts=1006.0),
    )
    assert session.state == "working"
    assert session.reason == ""
    assert session.last_event == "Read a.py"


def test_a_permission_request_without_a_tool_still_needs_you(ws):
    session = fold(ws, event("PermissionRequest", ts=1000.0))
    assert session.state == "needs_you"
    assert session.reason == "permission"


def test_a_tool_that_did_not_run_clears_the_waiting(ws):
    session = fold(
        ws,
        event("PermissionRequest", tool_name="Bash", tool_input={"command": "ls ~"},
              ts=1000.0),
        event("PostToolUseFailure", tool_name="Bash", tool_input={"command": "ls ~"},
              error="permission denied", ts=1005.0),
    )
    assert session.state == "working"
    assert session.reason == ""
    assert session.last_event == "Bash ls ~ failed"


def test_an_interrupted_tool_says_so(ws):
    session = fold(
        ws,
        event("PostToolUseFailure", tool_name="Bash", tool_input={"command": "sleep 99"},
              error="interrupted", is_interrupt=True, ts=1005.0),
    )
    assert session.last_event == "Bash sleep 99 interrupted"
