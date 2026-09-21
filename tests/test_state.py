"""The state machine of section 4.3, one test per transition."""

from __future__ import annotations

import pathlib
import time

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
    assert session.state == "done"
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


def test_the_sort_ignores_the_name_claude_code_gave_a_session(ws):
    """The row shows the worktree, so the list is ordered by the worktree. A
    session's name arrives from the status line a second after it starts, and
    `/rename` changes it later, so a list ordered by name jumps under the
    reader for the same reason a list ordered by state did."""
    zed = ws.Session(session_id="z", state="working", cwd="/a/apple")
    zed.status = ws.Status(ts=1.0, name="Zebra work")
    ann = ws.Session(session_id="a", state="working", cwd="/a/pear")
    ann.status = ws.Status(ts=1.0, name="Ant work")
    assert zed.label.startswith("Zebra") and ann.label.startswith("Ant")
    assert [one.session_id for one in ws.sort_sessions([ann, zed])] == ["z", "a"]


def test_idle_notification_does_not_need_you(ws):
    """The agent finished and sits at its prompt. `Stop` already said that, and
    nothing you do clears an idle prompt, so a row that went amber here stayed
    amber for ever. Amber is for an agent that cannot go on without you."""
    session = fold(
        ws,
        event("UserPromptSubmit", prompt="x", ts=1000.0),
        event("Stop", ts=1001.0),
        event("Notification", notification_type="idle_prompt", ts=1061.0,
              message="Claude is waiting for your input"),
    )
    assert session.state == "done"
    assert session.attention_since == 0.0
    assert session.reason == "waiting for input"


def test_an_idle_notification_never_hides_an_open_dialog(ws):
    session = fold(
        ws,
        event("PermissionRequest", tool_name="Bash", tool_input={"command": "ls ~"},
              ts=1000.0),
        event("Notification", notification_type="idle_prompt", ts=1060.0,
              message="Claude is waiting for your input"),
    )
    assert session.state == "needs_you"
    assert session.reason == "permission: Bash ls ~"
    assert session.attention_since == 1000.0


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


def test_sort_is_by_name_with_the_gone_ones_last(ws):
    def make(state, sid, where, **kw):
        return ws.Session(session_id=sid, state=state, cwd="/a/" + where, **kw)

    rows = [
        make("done", "d", "Pear", last_ts=50.0),
        make("needs_you", "n2", "fig", attention_since=20.0),
        make("working", "w", "apple", last_ts=60.0),
        make("ended", "e", "acorn", last_ts=70.0),
        make("needs_you", "n1", "plum", attention_since=10.0),
        make("dead", "x", "aloe", last_ts=80.0),
        make("done", "s", "beet", last_ts=80.0),
    ]
    order = [s.session_id for s in ws.sort_sessions(rows)]
    # apple, beet, fig, Pear, plum — case does not split the list — then the
    # ended and the dead, by name among themselves.
    assert order == ["w", "s", "n2", "d", "n1", "e", "x"]


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


def test_the_late_notification_cannot_raise_it_again(ws):
    """The bug that made "needs you" look like it never cleared. You approve,
    the tool runs, the row goes green — and the notification for the question
    you already answered lands twelve seconds later and turns it amber again,
    with nothing left to come that would clear it."""
    session = fold(
        ws,
        event("PermissionRequest", tool_name="Bash", tool_input={"command": "ls ~"},
              ts=1000.0),
        event("PostToolUse", tool_name="Bash", tool_input={"command": "ls ~"}, ts=1004.0),
        event("Notification", notification_type="permission_prompt",
              message="Claude needs your permission", ts=1012.0),
    )
    assert session.state == "working"
    assert session.attention_since == 0.0
    assert session.reason == ""


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


def test_a_tool_that_failed_clears_the_waiting(ws):
    session = fold(
        ws,
        event("PermissionRequest", tool_name="Bash", tool_input={"command": "ls ~"},
              ts=1000.0),
        event("PostToolUseFailure", tool_name="Bash", tool_input={"command": "ls ~"},
              error="command not found", ts=1005.0),
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


def test_a_denied_permission_sends_no_event_at_all(ws):
    """Measured against a real session: saying No to the dialog fires no hook.
    The log ends at the Notification. So the session keeps waiting, which is
    still true, and nothing here may pretend otherwise.
    """
    session = fold(
        ws,
        event("PreToolUse", tool_name="Bash", tool_input={"command": "ls ~"}, ts=1000.0),
        event("Notification", notification_type="permission_prompt",
              message="Claude needs your permission", ts=1012.0),
    )
    assert session.state == "needs_you"
    assert session.attention_since == 1012.0


def test_a_session_with_no_pid_goes_quiet_rather_than_living_for_ever(ws):
    """`agent_pid` returns 0 where there is no /proc to walk — on macOS, for
    every session. Such a session cannot be checked, so it stayed in the list
    as though it were running until the log forgot it, a week later."""
    session = ws.Session(session_id="s", state="working", cwd="/a/b", last_ts=1000.0)
    ws.mark_dead(session, alive=lambda pid: True, now=1000.0 + ws.QUIET_MAX - 1)
    assert session.state == "working"
    ws.mark_dead(session, alive=lambda pid: True, now=1000.0 + ws.QUIET_MAX + 1)
    assert session.state == "dead"
    assert session.end_reason == "no sign of it"


def test_a_session_we_can_check_is_not_buried_for_being_quiet(ws):
    """An agent left waiting overnight has a pid, and the pid is the answer."""
    session = ws.Session(session_id="s", state="needs_you", cwd="/a/b",
                         pid=4242, last_ts=1000.0)
    ws.mark_dead(session, alive=lambda pid: True, now=1000.0 + ws.QUIET_MAX * 3)
    assert session.state == "needs_you"


def test_an_idle_prompt_says_why_a_session_is_quiet(ws):
    """It is already ready; this says what it is waiting for."""
    session = fold(
        ws,
        event("SessionStart", source="resume", ts=1000.0),
        event("Notification", notification_type="idle_prompt", ts=1060.0,
              message="Claude is waiting for your input"),
    )
    assert session.state == "done"
    assert session.reason == "waiting for input"


def test_a_pid_that_belongs_to_something_else_now_is_not_alive(ws, monkeypatch):
    """The numbers wrap. A session that ended in the morning had its pid taken
    by something else by the evening, so `kill -0` said yes and the row sat
    there all day saying "done" for an agent that was gone."""
    monkeypatch.setattr(ws.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(ws, "looks_like_claude", lambda pid: False)
    assert ws.pid_alive(4242) is False
    monkeypatch.setattr(ws, "looks_like_claude", lambda pid: True)
    assert ws.pid_alive(4242) is True


def test_a_session_whose_pid_was_reused_goes_to_the_history(ws, monkeypatch):
    monkeypatch.setattr(ws.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(ws, "looks_like_claude", lambda pid: False)
    session = ws.Session(session_id="s", state="done", cwd="/a/b", pid=4242,
                         last_ts=1000.0)
    ws.mark_dead(session, now=1000.0)
    assert session.state == "dead"
    assert session.end_reason == "process gone"


# --- a name the reader gave ---------------------------------------------------


def test_a_name_set_here_wins_over_the_one_claude_code_sent(ws):
    session = ws.Session(session_id="s", cwd="/a/b",
                         status=ws.Status(name="from-claude"))
    assert session.label.startswith("from-claude")
    session.mine = "mine"
    assert session.label.startswith("mine")


def test_renaming_keeps_it_and_taking_it_away_forgets_it(ws):
    store = ws.Store()
    assert store.rename("s", "  a  long   name  ") == "a long name"
    assert ws.read_names() == {"s": "a long name"}
    # A fresh store reads what the last one wrote: this is the half that
    # survives a restart of the daemon.
    assert ws.Store().names == {"s": "a long name"}
    assert store.rename("s", "   ") == ""
    assert ws.read_names() == {}


def test_a_name_is_clipped_rather_than_refused(ws):
    store = ws.Store()
    given = store.rename("s", "x" * (ws.NAME_MAX + 50))
    assert len(given) == ws.NAME_MAX


def test_names_that_are_not_names_are_left_out(ws):
    """The file is ours, but it is on disk and a browser is not the only thing
    that can write there."""
    ws.write_atomic(ws.names_path(), '{"good": "keep", "bad": 7, "empty": " "}')
    assert ws.read_names() == {"good": "keep"}
    ws.write_atomic(ws.names_path(), "[1, 2]")
    assert ws.read_names() == {}


def test_a_new_name_from_the_status_line_reaches_the_row(ws):
    """Our own path is live: a status file that changes is read again on the
    next pass. A rename in the terminal does not show because the name Claude
    Code hands the status line is the one the session started with, not
    because anything here holds on to the old one."""
    import time as clock

    ws.append_event(event("SessionStart", sid="s1", cwd="/w/one",
                          ts=clock.time(), pane="%7", pid=1))
    store = ws.Store()
    ws.write_status("s1", ws.Status(ts=clock.time(), name="first"))
    store.refresh()
    assert store.rows[0]["name"] == "first"
    clock.sleep(0.02)                      # a different mtime, not a new file
    ws.write_status("s1", ws.Status(ts=clock.time(), name="second"))
    store.refresh()
    assert store.rows[0]["name"] == "second"


# --- five ways a row said the wrong thing ------------------------------------


def test_an_auth_notification_does_not_strand_the_row_amber(ws):
    """`PLAN.md` 4.3 says plainly that `auth_success` is not needs-you. An
    older Claude Code sends no `notification_type`, and the fallback took
    anything that was not the idle message for a permission prompt.

    Nothing clears it: no tool call and no prompt follows an auth
    notification, so the row sat amber with "Logged in as martin" as its
    reason until someone typed into that session."""
    store = ws.Store()
    store.apply(event("SessionStart", cwd="/w/one", ts=1000.0))
    store.apply(event("Notification", cwd="/w/one", ts=1001.0,
                      message="Logged in as martin"))
    session = store.sessions["s1"]
    assert session.state != "needs_you"
    assert session.reason == ""
    assert session.last_event == "Logged in as martin"


def test_an_untyped_permission_message_is_still_read(ws):
    """The other half: the fallback has to recognise one, not assume it."""
    store = ws.Store()
    store.apply(event("SessionStart", cwd="/w/one", ts=1000.0))
    store.apply(event("Notification", cwd="/w/one", ts=1001.0,
                      message="Claude needs your permission to use Bash"))
    assert store.sessions["s1"].state == "needs_you"


def test_a_stale_permission_notification_leaves_the_text_alone_too(ws):
    """Only the state change was dropped. The row read "ready" in blue with a
    permission question as its only line of text, and stayed that way until
    someone typed."""
    store = ws.Store()
    store.apply(event("SessionStart", cwd="/w/one", ts=1000.0))
    store.apply(event("PermissionRequest", cwd="/w/one", ts=1000.0,
                      tool_name="Bash", tool_input={"command": "ls"}))
    store.apply(event("PostToolUse", cwd="/w/one", ts=1004.0, tool_name="Bash"))
    store.apply(event("Stop", cwd="/w/one", ts=1006.0))
    store.apply(event("Notification", cwd="/w/one", ts=1012.0,
                      notification_type="permission_prompt",
                      message="Claude needs your permission to use Bash"))
    session = store.sessions["s1"]
    assert session.state == "done"
    assert session.reason == ""
    assert session.last_event == "stopped"


def test_a_resumed_session_is_not_still_waiting(ws):
    """Every handler that sets a state clears the attention with it. This one
    did not, so a session killed at its dialog and resumed came back reading
    "ready" with "permission: Bash rm -rf ~" under it — and a wait that had
    started before the agent died."""
    store = ws.Store()
    store.apply(event("PermissionRequest", cwd="/w/one", ts=1000.0,
                      tool_name="Bash", tool_input={"command": "rm -rf ~"}))
    assert store.sessions["s1"].state == "needs_you"
    store.apply(event("SessionStart", cwd="/w/one", ts=2000.0, source="resume"))
    session = store.sessions["s1"]
    assert session.state == "done"
    assert session.reason == ""
    assert session.attention_since == 0.0


def test_a_second_notification_does_not_restart_the_wait(ws):
    """A Claude Code that sends no `PermissionRequest` notifies again while
    the same dialog is up. The clock is how long you have been needed, and
    moving it made a row that had waited a minute say it had waited none."""
    store = ws.Store()
    store.apply(event("SessionStart", cwd="/w/one", ts=900.0))
    store.apply(event("Notification", cwd="/w/one", ts=1000.0,
                      notification_type="elicitation_dialog",
                      message="Claude is asking"))
    assert store.sessions["s1"].attention_since == 1000.0
    store.apply(event("Notification", cwd="/w/one", ts=1060.0,
                      notification_type="elicitation_dialog",
                      message="Claude is asking"))
    assert store.sessions["s1"].attention_since == 1000.0
    assert store.sessions["s1"].state == "needs_you"


def test_two_renames_at_once_keep_both_names(ws):
    """`ThreadingHTTPServer` runs two `POST /name` requests at once in one
    process. Both built the new map from the same snapshot, so one name was
    lost — and memory and the file disagreed about which, so a restart
    silently swapped them. The temporary file was named by pid alone, so one
    thread also unlinked the other's, which came back as a
    `FileNotFoundError` into a browser's request.
    """
    import threading

    store = ws.Store()
    real = ws.write_names

    def slow(names):
        time.sleep(0.05)
        real(names)

    ws.write_names = slow
    try:
        threads = [threading.Thread(target=store.rename, args=(who, f"name-{who}"))
                   for who in ("a", "b")]
        for one in threads:
            one.start()
        for one in threads:
            one.join()
    finally:
        ws.write_names = real

    assert store.names == {"a": "name-a", "b": "name-b"}
    assert ws.read_names() == store.names


# --- two tools at once, and a dialog on one of them --------------------------


def test_a_result_for_another_call_does_not_clear_an_open_dialog(ws):
    """Claude Code runs two tools at once now and then — measured over 233
    calls on a real machine, one started while another was still open, and
    both were `Bash`. Both `PreToolUse` events come before the dialog, so the
    other call reports back while the dialog is still on screen.

    Clearing the amber on that turned the row green while the agent sat
    blocked: the one thing this program exists to say, said backwards.
    """
    session = fold(
        ws,
        event("PreToolUse", tool_name="Bash", tool_input={"command": "pytest -q"},
              ts=1000.0),
        event("PreToolUse", tool_name="Bash", tool_input={"command": "rm -rf build"},
              ts=1000.7),
        event("PermissionRequest", tool_name="Bash",
              tool_input={"command": "rm -rf build"}, ts=1001.0),
        event("PostToolUse", tool_name="Bash", tool_input={"command": "pytest -q"},
              ts=1003.0),
    )
    assert session.state == "needs_you"
    assert session.reason == "permission: Bash rm -rf build"
    assert session.attention_since == 1001.0


def test_the_result_the_dialog_was_about_does_clear_it(ws):
    """The other half. Say yes, the call runs, and the row goes back to work."""
    session = fold(
        ws,
        event("PreToolUse", tool_name="Bash", tool_input={"command": "pytest -q"},
              ts=1000.0),
        event("PermissionRequest", tool_name="Bash",
              tool_input={"command": "pytest -q"}, ts=1001.0),
        event("PostToolUse", tool_name="Bash", tool_input={"command": "pytest -q"},
              ts=1003.0),
    )
    assert session.state == "working"
    assert session.reason == ""


def test_a_failure_of_another_call_does_not_clear_it_either(ws):
    """A failure is a call finishing, so it is paired the same way."""
    session = fold(
        ws,
        event("PermissionRequest", tool_name="Bash",
              tool_input={"command": "rm -rf build"}, ts=1001.0),
        event("PostToolUseFailure", tool_name="Bash",
              tool_input={"command": "pytest -q"}, ts=1003.0),
    )
    assert session.state == "needs_you"
    assert session.reason == "permission: Bash rm -rf build"


def test_a_dialog_with_no_tool_named_is_cleared_by_anything(ws):
    """A `Notification` raises the alarm without naming a tool, and so can a
    `PermissionRequest`. With nothing to pair against, the old rule stands —
    the first thing that happens answers it. Guessing a pairing would be
    worse: it could leave a row amber for ever."""
    session = fold(
        ws,
        event("PermissionRequest", ts=1000.0),
        event("PostToolUse", tool_name="Read",
              tool_input={"file_path": "/w/repo/a.py"}, ts=1003.0),
    )
    assert session.state == "working"
    assert session.reason == ""
