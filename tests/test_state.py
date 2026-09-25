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


def test_a_compaction_in_the_middle_of_a_turn_does_not_end_it(ws):
    """An auto compaction fires `SessionStart` with `source=compact` and the
    turn goes on. It set "done", so the row moved to ready, the page said the
    agent had finished, and a spend limit could not fire until the next
    tool call."""
    session = fold(
        ws,
        event("UserPromptSubmit", prompt="x"),
        event("PreCompact", trigger="auto", ts=1500.0),
        event("SessionStart", source="compact", ts=1501.0),
    )
    assert session.state == "working"
    # At the prompt, a /compact leaves it ready, as it was.
    session = fold(ws, event("Stop", ts=1400.0),
                   event("SessionStart", source="compact", ts=1501.0))
    assert session.state == "done"


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


def test_sort_is_newest_first_with_the_gone_ones_last(ws):
    """The session you touched last is the one you are looking for. It used
    to be sorted by worktree, so in a list of twenty it was somewhere in the
    middle under `a`."""
    def make(state, sid, where, **kw):
        return ws.Session(session_id=sid, state=state, cwd="/a/" + where, **kw)

    rows = [
        make("done", "d", "Pear", state_since=50.0),
        make("needs_you", "n2", "fig", state_since=20.0),
        make("working", "w", "apple", state_since=60.0),
        make("ended", "e", "acorn", state_since=70.0),
        make("needs_you", "n1", "plum", state_since=10.0),
        make("dead", "x", "aloe", state_since=80.0),
        make("done", "s", "beet", state_since=80.0),
    ]
    order = [s.session_id for s in ws.sort_sessions(rows)]
    # The live ones newest first, then the ended and the dead the same way.
    assert order == ["s", "w", "d", "n2", "n1", "x", "e"]


def test_the_worktree_is_only_the_tiebreaker(ws):
    """Two sessions that last moved at the same instant have to come out in
    some order, and it has to be the same order every time — a name does not
    move, and `label` does: it arrives a second late and `/rename` changes it.
    """
    rows = [
        ws.Session(session_id="p", state="done", cwd="/a/plum", state_since=9.0),
        ws.Session(session_id="a", state="done", cwd="/a/Apple", state_since=9.0),
        ws.Session(session_id="f", state="done", cwd="/a/fig", state_since=9.0),
    ]
    # Apple, fig, plum — case does not split the list.
    assert [s.session_id for s in ws.sort_sessions(rows)] == ["a", "f", "p"]


def test_a_working_session_does_not_move_on_every_tool_call(ws):
    """This is why the order is `settled` and not `since`. A working
    session's last event moves every few seconds, so two busy agents would
    swap places while you read them."""
    store = ws.Store()
    store.apply(event("UserPromptSubmit", prompt="go", ts=100.0))
    began = store.get("s1").settled
    for at, ts in enumerate([101.0, 102.0, 103.0]):
        store.apply(event("PreToolUse", tool_name="Bash",
                          tool_input={"command": f"one {at}"}, ts=ts))
        store.apply(event("PostToolUse", tool_name="Bash",
                          tool_input={"command": f"one {at}"}, ts=ts))
    session = store.get("s1")
    assert session.state == "working"
    assert session.settled == began, "the order would churn"
    assert session.since == 103.0, "the age still counts from the last event"

    # The turn ending is a change, and it does move.
    store.apply(event("Stop", ts=110.0))
    assert store.get("s1").settled == 110.0


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


# --- a question the agent is stopped on ---------------------------------------

#: Two questions in one call, as a real `AskUserQuestion` sends them. The
#: shape was read off a recorded `PreToolUse`, not guessed; the text is
#: invented, because a real one holds somebody's work.
ASKED = {"questions": [
    {"question": "Approve the plan and proceed with implementation?",
     "header": "Plan approval",
     "options": [
         {"label": "Approve", "description": "Start writing the test."},
         {"label": "Changes needed", "description": "Describe what to change."},
         {"label": "Abandon", "description": "Stop without committing."},
     ],
     "multiSelect": False},
    {"question": "Run it on every PR, or only when asked?",
     "header": "On every PR",
     "options": [
         {"label": "On demand (Recommended)", "description": "No annotation."},
         {"label": "Every PR", "description": "One more app start per build."},
     ],
     "multiSelect": False},
]}


def asked(**extra):
    """The two events a real ask sends, in the order and shape it sends them:
    `PreToolUse` with the `tool_use_id`, then `PermissionRequest` without
    one, ninety milliseconds later."""
    return [
        event("PreToolUse", tool_name="AskUserQuestion", tool_input=ASKED,
              tool_use_id="toolu_q1", ts=1000.0, **extra),
        event("PermissionRequest", tool_name="AskUserQuestion",
              tool_input=ASKED, ts=1000.1, **extra),
    ]


def test_a_session_that_dies_on_its_question_forgets_it(ws):
    """Every change of state clears the attention, and the one made where
    nothing reports it did not: an agent killed at its question kept the
    question, with buttons whose keys went into whatever ran in the pane
    next. `_bury`."""
    store = ws.Store()
    for one in asked():
        store.apply(one)
    store.settle(1010.0, alive=lambda pid: False)
    session = store.sessions["s1"]
    assert session.state == "dead"
    assert session.asking is None
    assert session.reason == ""
    assert session.attention_since == 0.0


def test_one_event_that_cannot_be_folded_costs_only_itself(ws):
    """The follower counts a whole piece of the log as read before it hands
    out a line, so an exception leaving the fold threw away every event
    after it in that piece -- up to a megabyte of sessions -- on every start.
    `Store.fold` catches per event."""
    bad = event("PreToolUse", tool_name="AskUserQuestion", tool_use_id="q",
                tool_input={"questions": [{"question": "q", "options": 3}]})
    store = ws.Store()
    store.apply = (lambda real: lambda one: (_ for _ in ()).throw(
        RuntimeError("boom")) if one is bad else real(one))(store.apply)
    later = [dict(event("SessionStart", ts=1001.0 + n), session_id=f"s{n}")
             for n in range(3)]
    store.fold([bad, *later])
    assert sorted(store.sessions) == ["s0", "s1", "s2"]


@pytest.mark.parametrize("options", [3, {"a": 1}, True, "abc"])
def test_options_that_are_not_a_list_are_not_answered(ws, options):
    """`read_ask` called `len()` and a slice on them, and raised inside the
    fold. A question it cannot read whole is shown and not answered."""
    ask = ws.read_ask({"tool_name": "AskUserQuestion", "tool_use_id": "q",
                       "tool_input": {"questions": [
                           {"question": "q", "options": options},
                           {"question": "r", "options": [{"label": "a"}]}]}})
    assert ask is not None and ask["answerable"] is False


def test_a_question_is_kept_whole_enough_to_answer(ws):
    """The row said `AskUserQuestion {"questions": [{"question": "Approve …`
    -- the catch-all summary, clipped at eighty characters. Everything a
    reader needs to answer was in the payload and none of it reached them."""
    session = fold(ws, *asked())
    assert session.state == "needs_you"
    assert session.asking["id"] == "toolu_q1"
    first = session.asking["questions"][0]
    assert first["header"] == "Plan approval"
    assert first["question"].startswith("Approve the plan")
    assert [one["label"] for one in first["options"]] == [
        "Approve", "Changes needed", "Abandon"]
    assert first["options"][0]["description"] == "Start writing the test."
    assert len(session.asking["questions"]) == 2


def test_the_row_says_what_is_being_asked_not_json(ws):
    """And it does not call it a permission: it is a question with answers
    written out, and "permission" sent you looking for a dialog that asks
    something else."""
    session = fold(ws, *asked())
    assert session.reason == "asks: Plan approval, On every PR"


def test_the_question_goes_when_it_is_answered(ws):
    store = ws.Store()
    for one in asked():
        store.apply(one)
    session = store.sessions["s1"]
    assert session.asking is not None        # or the rest proves nothing
    store.apply(event("PostToolUse", tool_name="AskUserQuestion",
                      tool_input=ASKED, tool_use_id="toolu_q1", ts=1050.0))
    assert session.asking is None
    assert session.state == "working"


def test_another_call_finishing_does_not_take_the_question_away(ws):
    """Claude Code runs two tools at once now and then. The other one
    reporting back is not an answer to this question -- and this one has
    buttons on it, so a stale question is a button that types a number into a
    terminal that has moved on."""
    session = fold(
        ws,
        event("PreToolUse", tool_name="Bash", tool_input={"command": "sleep 30"},
              tool_use_id="b1", ts=999.0),
        *asked(),
        event("PostToolUse", tool_name="Bash", tool_input={"command": "sleep 30"},
              tool_use_id="b1", ts=1001.0),
    )
    assert session.asking is not None
    assert session.state == "needs_you"


def test_another_call_before_the_dialog_does_not_take_the_question_away(ws):
    """The dialog comes about ninety milliseconds after the ask's own
    `PreToolUse`, and another call of the same batch can finish, or start,
    in between. Either wiped the question: the row went amber saying
    "asks: …" with no bar to answer it, and `answer` refused."""
    bash = {"command": "ls"}
    ask, shown = asked()
    finishing = fold(
        ws,
        event("PreToolUse", tool_name="Bash", tool_input=bash,
              tool_use_id="b1", ts=999.0),
        ask,
        event("PostToolUse", tool_name="Bash", tool_input=bash,
              tool_use_id="b1", ts=1000.05),
        shown,
    )
    assert finishing.state == "needs_you"
    assert finishing.asking and finishing.asking["id"] == "toolu_q1"
    starting = fold(
        ws,
        ask,
        event("PreToolUse", tool_name="Read", tool_input={"file_path": "a"},
              tool_use_id="r1", ts=1000.05),
        shown,
    )
    assert starting.asking and starting.asking["id"] == "toolu_q1"
    failing = fold(
        ws,
        ask,
        event("PostToolUseFailure", tool_name="Bash", tool_input=bash,
              tool_use_id="b1", ts=1000.05),
        shown,
    )
    assert failing.asking and failing.asking["id"] == "toolu_q1"


def test_the_question_goes_when_the_agent_moves_on(ws):
    """A call starting says the agent is no longer stopped on anything --
    which is the only sign of a denial, because saying No fires no hook."""
    session = fold(ws, *asked(),
                   event("PreToolUse", tool_name="Bash",
                         tool_input={"command": "ls"}, tool_use_id="b2",
                         ts=1002.0))
    assert session.asking is None


def test_a_question_does_not_survive_a_restart(ws):
    """A session killed at its dialog and resumed came back "ready" with the
    old permission question under it. A question with buttons is the same bug
    with a worse ending."""
    session = fold(ws, *asked(), event("SessionStart", source="resume",
                                       ts=1003.0))
    assert session.asking is None


def test_a_question_with_nothing_to_pick_is_not_one(ws):
    """An ask with no options is nothing a button can answer, and an empty
    bar over every tab is worse than the row alone."""
    session = fold(ws, event("PreToolUse", tool_name="AskUserQuestion",
                             tool_input={"questions": [{"question": "well?"}]},
                             tool_use_id="q", ts=1000.0))
    assert session.asking is None


def test_only_what_is_drawn_is_kept(ws):
    """The log keeps every payload whole; a row does not. What goes to every
    browser on every push is named field by field, so a field nobody read
    cannot reach the page."""
    session = fold(ws, event(
        "PreToolUse", tool_name="AskUserQuestion", tool_use_id="q", ts=1000.0,
        tool_input={"questions": [{
            "question": "well?", "header": "H", "multiSelect": True,
            "surprise": "from a newer Claude Code",
            "options": [{"label": "yes", "description": "d",
                         "preview": "also new"}]}]}))
    one = session.asking["questions"][0]
    assert sorted(one) == ["header", "many", "options", "preview", "question"]
    assert sorted(one["options"][0]) == [
        "description", "label", "preview", "withheld"]
    assert one["many"] is True
    # A multiple-choice question is never drawn beside a preview, so its
    # preview is not sent: the page shows what the dialog shows.
    assert one["preview"] is False
    assert one["options"][0]["preview"] == ""


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
    """`auth_success` is not needs-you (CLAUDE.md: "Amber means one thing"). An
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


# --- what a session has done -------------------------------------------------


def test_a_session_keeps_its_own_short_history(ws):
    """The Session tab reads the daemon's own log, folded as the events
    arrived. `events.jsonl` is twenty megabytes at its largest and holds every
    session; walking it per request for one of them is not a trade worth
    making."""
    store = ws.Store()
    store.apply(event("SessionStart", cwd="/w/one", ts=1000.0))
    store.apply(event("UserPromptSubmit", cwd="/w/one", ts=1001.0,
                      prompt="do the thing"))
    store.apply(event("PreToolUse", cwd="/w/one", ts=1002.0, tool_name="Bash",
                      tool_input={"command": "pytest -q"}))
    session = store.sessions["s1"]
    assert [one["name"] for one in session.log] == [
        "SessionStart", "UserPromptSubmit", "PreToolUse"]
    assert session.log[-1]["text"] == "Bash pytest -q"
    assert session.counts == {"SessionStart": 1, "UserPromptSubmit": 1,
                              "PreToolUse": 1}


def test_folding_an_event_twice_does_not_count_it_twice(ws):
    """Everything else here assigns; these two accumulate, which is the one
    thing `CLAUDE.md` says a handler may not do. The rule that makes it safe
    is strictly-newer: `apply` drops what is *older* than the session has
    seen, but an event with the very same `ts` folds again and a rotation
    re-delivers the newest one."""
    store = ws.Store()
    same = event("PreToolUse", cwd="/w/one", ts=1002.0, tool_name="Bash",
                 tool_input={"command": "ls"})
    store.apply(event("SessionStart", cwd="/w/one", ts=1000.0))
    store.apply(same)
    store.apply(same)                  # the rotation delivering it again
    store.apply(dict(same))            # and a copy of it, for good measure
    session = store.sessions["s1"]
    assert session.counts["PreToolUse"] == 1
    assert len(session.log) == 2


def test_the_history_does_not_grow_without_bound(ws):
    """A session that runs all day would otherwise keep every event it ever
    sent, in memory, for a panel nobody is looking at most of the time."""
    store = ws.Store()
    for n in range(ws.SESSION_LOG_MAX + 50):
        store.apply(event("PreToolUse", cwd="/w/one", ts=1000.0 + n,
                          tool_name="Bash", tool_input={"command": f"n{n}"}))
    session = store.sessions["s1"]
    assert len(session.log) == ws.SESSION_LOG_MAX
    # The newest are the ones kept.
    assert session.log[-1]["text"].endswith(f"n{ws.SESSION_LOG_MAX + 49}")
    # And the count is the whole story, not what is left of the log.
    assert session.counts["PreToolUse"] == ws.SESSION_LOG_MAX + 50


def test_the_place_does_not_follow_the_agent_into_a_subdirectory(ws):
    """`cwd` is where the agent is standing, and Claude Code moves it the
    moment the agent changes directory. The row's one irreplaceable fact is
    which worktree this is, and it renamed itself mid-turn."""
    session = fold(
        ws,
        event("SessionStart", cwd="/w/repo/dir"),
        event("PreToolUse", cwd="/w/repo/dir/src/deep", ts=1001.0,
              tool_name="Bash", tool_input={"command": "ls"}),
    )
    assert session.cwd == "/w/repo/dir/src/deep"   # still true, and still used
    assert session.place == "dir"                  # but not what the row says


def test_a_resumed_session_starts_where_it_was_resumed(ws):
    """A session really can be resumed from another directory, and then the
    new one is where it is. `SessionStart` is the one event that may move it."""
    session = fold(
        ws,
        event("SessionStart", cwd="/w/repo/dir"),
        event("PreToolUse", cwd="/w/repo/dir/src", ts=1001.0,
              tool_name="Bash", tool_input={"command": "ls"}),
        event("SessionStart", cwd="/w/repo/other", source="resume", ts=1002.0),
    )
    assert session.place == "other"


# --- a spend limit ------------------------------------------------------------


def working(ws, store, spent, session_id="s1"):
    """A session mid-turn, with the status line's idea of what it has spent."""
    store.apply(dict(event("SessionStart", ts=1000.0), session_id=session_id))
    store.apply(dict(event("UserPromptSubmit", ts=1001.0, prompt="go"),
                     session_id=session_id))
    session = store.sessions[session_id]
    session.pane = "%7"
    session.status = ws.Status(ts=1.0, cost_usd=spent)
    assert session.state == "working"
    return session


def test_a_session_over_its_limit_is_stopped_once(ws):
    """Fired again on every tick, the agent could never be let go: the key
    would land a second later, and a second after that, for ever."""
    store = ws.Store()
    session = working(ws, store, 12.0)
    store.set_limit("s1", 10.0)
    assert store.over_limit(now=50.0) == [("s1", "%7", 50.0)]
    assert "stopped at its $10.00 limit" in session.last_event
    # And not again, however far past it goes.
    session.status = ws.Status(ts=2.0, cost_usd=99.0)
    assert store.over_limit(now=51.0) == []


def test_raising_the_limit_lets_the_session_go_again(ws):
    """Otherwise a stopped session is stuck: the only way on would be to
    delete a file nobody told you about."""
    store = ws.Store()
    working(ws, store, 12.0)
    store.set_limit("s1", 10.0)
    assert store.over_limit(now=50.0) == [("s1", "%7", 50.0)]
    store.set_limit("s1", 20.0)              # clears `fired_at`
    assert store.over_limit(now=51.0) == []  # 12 is under 20
    store.sessions["s1"].status = ws.Status(ts=2.0, cost_usd=25.0)
    assert store.over_limit(now=52.0) == [("s1", "%7", 52.0)]


def test_a_refused_escape_waits_and_is_tried_again_across_a_restart(ws):
    """A key tmux refused stopped nothing. Kept as a stop, the agent ran on
    behind a page that said it had been stopped; tried on every tick, a
    refusing tmux would be asked once a second for ever. `refused_at` is
    kept in the file, or a restart forgets the wait."""
    store = ws.Store()
    working(ws, store, 12.0)
    store.set_limit("s1", 10.0)
    assert store.over_limit(now=50.0) == [("s1", "%7", 50.0)]
    store.limit_refused("s1", 50.0, now=50.0)
    assert ws.read_limits()["s1"] == {"limit": 10.0, "fired_at": 0.0,
                                      "refused_at": 50.0, "refused_spend": 12.0}
    assert "could not stop" in store.sessions["s1"].last_event
    again = ws.Store()
    session = working(ws, again, 13.0)
    assert again.over_limit(now=50.0 + ws.LIMIT_RETRY - 1) == []
    assert again.over_limit(now=50.0 + ws.LIMIT_RETRY) == [
        ("s1", "%7", 50.0 + ws.LIMIT_RETRY)]
    assert session.last_event.startswith("stopped")


def test_a_refused_escape_is_not_pressed_again_into_an_agent_it_stopped(ws):
    """`run` gives None for a `send-keys` that timed out, and the key may
    have landed all the same. An agent stopped by an Escape fires no hook
    that says so, so the row still reads "working" -- and a second Escape
    after `LIMIT_RETRY` went into a prompt nobody was at. A stopped agent
    spends nothing: only a spend that has grown is tried again."""
    store = ws.Store()
    session = working(ws, store, 12.0)
    store.set_limit("s1", 10.0)
    assert store.over_limit(now=50.0) == [("s1", "%7", 50.0)]
    store.limit_refused("s1", 50.0, now=50.0)
    assert store.over_limit(now=50.0 + ws.LIMIT_RETRY * 10) == []
    session.status = ws.Status(ts=2.0, cost_usd=12.5)
    assert store.over_limit(now=50.0 + ws.LIMIT_RETRY * 10) == [
        ("s1", "%7", 50.0 + ws.LIMIT_RETRY * 10)]


def test_a_refusal_after_the_limit_was_raised_is_not_written_over_it(ws):
    """The key goes out of the lock, so a raise can land between the stop and
    its refusal. Written over it, the panel said "could not stop at its
    $20.00 limit" with the spend at 12, and the next real stop waited."""
    store = ws.Store()
    session = working(ws, store, 12.0)
    store.set_limit("s1", 10.0)
    assert store.over_limit(now=50.0) == [("s1", "%7", 50.0)]
    store.set_limit("s1", 20.0)
    store.limit_refused("s1", 50.0, now=51.0)
    assert store.limits["s1"] == {"limit": 20.0, "fired_at": 0.0}
    assert "could not stop" not in session.last_event
    session.status = ws.Status(ts=2.0, cost_usd=25.0)
    assert store.over_limit(now=52.0) == [("s1", "%7", 52.0)]


def test_a_refusal_is_forgotten_when_the_spend_drops_below_the_limit(ws):
    """`/clear` puts the spend back to nought. The refusal stayed, and the
    panel said "tmux refused the Escape" for ever over a session under its
    limit."""
    store = ws.Store()
    session = working(ws, store, 12.0)
    store.set_limit("s1", 10.0)
    store.over_limit(now=50.0)
    store.limit_refused("s1", 50.0, now=50.0)
    session.status = ws.Status(ts=2.0, cost_usd=0.0)
    assert store.over_limit(now=51.0) == []
    assert store.limits["s1"] == {"limit": 10.0, "fired_at": 0.0}


def test_only_a_working_session_is_stopped(ws):
    """Escape into an idle prompt is a keystroke nobody asked for, and Escape
    while a permission dialog is up declines it — which is a decision, and not
    this one's to make."""
    store = ws.Store()
    session = working(ws, store, 12.0)
    store.set_limit("s1", 10.0)
    store.apply(event("Stop", ts=1002.0))
    assert session.state == "done"
    assert store.over_limit(now=50.0) == []


def test_a_session_whose_spend_nobody_sent_is_not_stopped(ws):
    """`None` is "the status line did not say". Stopping an agent over a
    number nobody sent is the worst way this could go wrong."""
    store = ws.Store()
    working(ws, store, None)
    store.set_limit("s1", 10.0)
    assert store.over_limit(now=50.0) == []


def test_a_session_with_no_pane_is_not_stopped(ws):
    store = ws.Store()
    session = working(ws, store, 12.0)
    session.pane = ""
    store.set_limit("s1", 10.0)
    assert store.over_limit(now=50.0) == []


def test_a_limit_survives_a_restart_and_nought_takes_it_away(ws):
    store = ws.Store()
    store.set_limit("s1", 7.5)
    assert ws.read_limits() == {"s1": {"limit": 7.5, "fired_at": 0.0}}
    assert ws.Store().limits == {"s1": {"limit": 7.5, "fired_at": 0.0}}
    store.set_limit("s1", 0)
    assert ws.read_limits() == {}


def test_a_limits_file_with_rubbish_in_it_is_not_trusted(ws):
    """Ours, but it outlives the version that wrote it."""
    ws.limits_path().parent.mkdir(parents=True, exist_ok=True)
    ws.limits_path().write_text(
        '{"a": {"limit": "lots"}, "b": 3, "c": {"limit": -1},'
        ' "d": {"limit": 5, "fired_at": "soon"}}', encoding="utf-8")
    assert ws.read_limits() == {"d": {"limit": 5.0, "fired_at": 0.0}}
    ws.limits_path().write_text("not json", encoding="utf-8")
    assert ws.read_limits() == {}


def test_a_stopped_session_is_armed_again_when_the_spend_drops(ws):
    """`/clear` puts `cost.total_cost_usd` back to nought. Without re-arming,
    one stop disarms the limit for the rest of the session and the agent runs
    without bound behind a box still showing a number."""
    store = ws.Store()
    session = working(ws, store, 12.0)
    store.set_limit("s1", 10.0)
    assert store.over_limit(now=50.0) == [("s1", "%7", 50.0)]
    assert store.limits["s1"]["fired_at"]

    session.status = ws.Status(ts=2.0, cost_usd=0.0)      # /clear
    assert store.over_limit(now=51.0) == []               # armed, not fired
    assert store.limits["s1"]["fired_at"] == 0.0
    session.status = ws.Status(ts=3.0, cost_usd=11.0)
    assert store.over_limit(now=52.0) == [("s1", "%7", 52.0)]


def test_a_limit_raised_while_a_stop_is_being_decided_is_not_clobbered(ws):
    """`over_limit` used to read the map outside the lock and merge under it,
    so a raise that landed in between was overwritten with the old number and
    a fresh `fired_at` — the reader's release undone at the moment they made
    it. Both sides take `naming` now, so one waits for the other."""
    import threading

    store = ws.Store()
    working(ws, store, 12.0)
    store.set_limit("s1", 10.0)
    held = threading.Event()
    go = threading.Event()
    real = ws.write_limits

    def slow(limits):
        real(limits)
        if not held.is_set():
            held.set()
            go.wait(5)               # still inside `over_limit`'s lock

    ws.write_limits = slow
    try:
        worker = threading.Thread(target=store.over_limit, args=(50.0,))
        worker.start()
        held.wait(5)
        raiser = threading.Thread(target=store.set_limit, args=("s1", 50.0))
        raiser.start()
        raiser.join(0.3)
        assert raiser.is_alive(), "the raise got in while the stop was writing"
        go.set()
        worker.join(5)
        raiser.join(5)
    finally:
        ws.write_limits = real
    # The raise is what stands, and it cleared the firing.
    assert store.limits["s1"] == {"limit": 50.0, "fired_at": 0.0}


# --- a history that is never thrown away ------------------------------------

DAY = 86400.0


def a_year_of_sessions():
    """One short session a day for 400 days, and one that ran all of them."""
    for n in range(400):
        yield event("SessionStart", session_id=f"s{n}", cwd=f"/w/tree{n}", ts=n * DAY)
        yield event("PostToolUse", session_id=f"s{n}", cwd=f"/w/tree{n}", tool_name="Edit",
                    tool_input={"file_path": "a.py"}, ts=n * DAY + 30)
        yield event("Stop", session_id=f"s{n}", cwd=f"/w/tree{n}", ts=n * DAY + 60)
        if n == 0:
            yield event("SessionStart", session_id="long", cwd="/w/long", ts=1.0)
        # It moved into a subdirectory after it started, so only the kept
        # SessionStart can still say where it began.
        yield event("UserPromptSubmit", session_id="long", cwd="/w/long/src",
                    prompt="and again", ts=n * DAY + 90)


def test_the_first_read_holds_a_week_of_sessions_not_all_of_them(ws):
    """The log is never thrown away now, and the first read folds all of it.
    `visible()` forgets a session a week quiet, but only once the fold is
    over -- measured on a year-shaped log, 1,873 sessions at about 80 KB each
    sat in memory until then. The fold forgets as it goes, by the time the
    log itself has reached, never the clock: a test's events are from 1970."""
    store = ws.Store()
    most = 0
    for one in a_year_of_sessions():
        store.fold([one])
        most = max(most, len(store.sessions))
    assert most <= 10, f"{most} sessions held at once"
    # Forgetting goes by the last event, never the first: a session that
    # started a year ago and is still going keeps where it started.
    assert store.sessions["long"].home == "/w/long"


def test_git_is_asked_about_the_sessions_shown_and_no_others(ws, monkeypatch):
    """Every tree-touching event puts its directory on `git_wanted`, and only
    a git run took one off. After a year of history the first refresh ran git
    on every worktree touched that year, deleted ones included."""
    asked: list[str] = []

    def git(dirs):
        asked.extend(dirs)
        return {d: ws.GitFacts(repo="repo", branch="main") for d in dirs}

    monkeypatch.setattr(ws, "git_facts_many", git)
    monkeypatch.setattr(ws, "pid_alive", lambda pid: True)
    store = ws.Store()
    store.fold(a_year_of_sessions())
    store.refresh(now=400 * DAY)
    shown = {s.cwd for s in store.visible(400 * DAY)}
    assert set(asked) <= shown, f"git ran on {len(set(asked) - shown)} hidden worktrees"
    assert set(asked) == shown


def test_one_event_from_a_wrong_clock_does_not_forget_everything(ws):
    """The fold goes by the log's own clock, and `ts` is whatever the machine
    said when a hook ran. One event stamped a year ahead would make every
    start forget every session a week older than that -- which is all of them.
    `visible()` goes by the real time and cannot do that, so the fold never
    forgets more than `visible()` would."""
    now = time.time()
    store = ws.Store()
    store.fold([event("SessionStart", session_id="today", ts=now - 60),
                event("SessionStart", session_id="ahead", ts=now + 365 * DAY),
                event("Stop", session_id="ahead", ts=now + 365 * DAY + 1)])
    assert "today" in store.sessions


def test_a_session_that_never_changed_state_keeps_its_place(ws):
    """`settled` fell back to the last event while nothing had stamped
    `state_since`, and `SessionStart` is done to done, which stamps nothing.
    So an idle notification moved a row that had not changed at all."""
    store = ws.Store()
    store.apply(dict(event("SessionStart", ts=1.0), session_id="a"))
    store.apply(dict(event("SessionStart", ts=10.0), session_id="b"))
    order = lambda: [one.session_id for one in ws.sort_sessions(
        list(store.sessions.values()))]
    assert order() == ["b", "a"]
    store.apply(dict(event("Notification", ts=61.0,
                           notification_type="idle_prompt",
                           message="Claude is waiting for your input"),
                     session_id="a"))
    assert order() == ["b", "a"]
    assert store.sessions["a"].settled == 1.0


def test_started_is_when_the_session_began(ws):
    """The Session tab's "started" row read `since`, the last event -- so it
    said "0s ago" for a session two hours old that had just been sent a
    prompt."""
    session = fold(ws, event("SessionStart", ts=1000.0),
                   event("UserPromptSubmit", prompt="go", ts=8200.0))
    assert ws.row(session)["started"] == 1000.0


# --- a permission request, whole, and declining it from the page -------------

LONG = "cmake --build build -j && " + " && ".join(f"ctest -R case{n}" for n in range(30))


def asking_permission(ws, *before, command=LONG, call="toolu_p1", ts=1010.0):
    return fold(ws, event("SessionStart", ts=1000.0), *before,
                event("PreToolUse", tool_name="Bash", tool_use_id=call,
                      tool_input={"command": command, "description": "Build"},
                      ts=ts),
                event("PermissionRequest", tool_name="Bash",
                      tool_input={"command": command, "description": "Build"},
                      ts=ts + 0.09))


def test_a_permission_request_reaches_the_page_whole(ws):
    """The row said the request clipped to one line. A request is judged on
    all of it, so the page gets every field of the input, whole, and the
    call it is about -- which `PermissionRequest` does not carry, and which
    is found among the calls that started and have not finished."""
    session = asking_permission(ws)
    shown = ws.row(session)["permission"]
    assert shown["tool"] == "Bash" and shown["call"] == "toolu_p1"
    assert shown["fields"] == [["command", LONG], ["description", "Build"]]
    assert not shown["withheld"] and shown["key"] == "1010.090000"
    assert len(session.reason) < len(LONG)          # the row's line is clipped


def test_a_request_two_open_calls_could_be_has_no_call(ws):
    """Two calls reading the same cannot be told apart, and a guessed call
    would let a reason be typed on the strength of the wrong result."""
    session = asking_permission(ws, event(
        "PreToolUse", tool_name="Bash", tool_use_id="toolu_p0",
        tool_input={"command": LONG, "description": "Build"}, ts=1005.0))
    assert session.permission["call"] == ""
    # A call that has reported back is not open, and not a second match.
    session = asking_permission(ws, event(
        "PreToolUse", tool_name="Bash", tool_use_id="toolu_p0",
        tool_input={"command": LONG, "description": "Build"}, ts=1005.0),
        event("PostToolUse", tool_name="Bash", tool_use_id="toolu_p0",
              tool_input={"command": LONG, "description": "Build"}, ts=1006.0))
    assert session.permission["call"] == "toolu_p1"
    # Nor is one left from a turn that is over: declined in the terminal,
    # it never reports back.
    session = asking_permission(ws, event(
        "PreToolUse", tool_name="Bash", tool_use_id="toolu_p0",
        tool_input={"command": LONG, "description": "Build"}, ts=1005.0),
        event("UserPromptSubmit", prompt="try again", ts=1006.0))
    assert session.permission["call"] == "toolu_p1"


def test_a_request_too_long_to_send_is_withheld(ws, monkeypatch):
    monkeypatch.setattr(ws, "PERMISSION_SHOWN", 100)
    shown = asking_permission(ws).permission
    assert shown["withheld"] and shown["fields"] == []


def test_the_permission_goes_with_the_attention(ws):
    """It is on the row only while the row is amber, and a question is not
    a permission: it has its own bar."""
    session = asking_permission(ws)
    later = fold(ws, event("SessionStart", ts=1000.0),
                 event("PreToolUse", tool_name="Bash", tool_use_id="toolu_p1",
                       tool_input={"command": "ls"}, ts=1010.0),
                 event("PermissionRequest", tool_name="Bash",
                       tool_input={"command": "ls"}, ts=1010.1),
                 event("PostToolUse", tool_name="Bash", tool_use_id="toolu_p1",
                       tool_input={"command": "ls"}, ts=1020.0))
    assert session.permission and later.permission is None
    assert ws.row(later)["permission"] is None
    asked = fold(ws, event("SessionStart", ts=1000.0),
                 event("PermissionRequest", tool_name="AskUserQuestion",
                       tool_input={"questions": []}, ts=1010.0))
    assert asked.permission is None


def test_a_decline_seen_in_the_transcript_ends_the_wait(ws):
    """Saying No fires no hook, so the row stayed amber over an agent back
    at its prompt. The daemon's own `Declined` record ends it -- for the
    dialog it names, and no other."""
    key = asking_permission(ws).permission["key"]
    declined = asking_permission(ws, ts=1010.0)
    ws_store = ws.Store()
    for one in (event("SessionStart", ts=1000.0),
                event("PreToolUse", tool_name="Bash", tool_use_id="toolu_p1",
                      tool_input={"command": LONG, "description": "Build"},
                      ts=1010.0),
                event("PermissionRequest", tool_name="Bash",
                      tool_input={"command": LONG, "description": "Build"},
                      ts=1010.09)):
        ws_store.apply(one)
    ws_store.apply(event("Declined", key="999.000000", ts=1011.0))
    other = ws_store.sessions["s1"]
    assert other.state == "needs_you" and other.permission   # not its dialog
    ws_store.apply(event("Declined", key=key, tool_use_id="toolu_p1", ts=1012.0))
    assert other.state == "done" and other.permission is None
    assert other.reason == "" and other.calls == {}
    assert other.last_event == "declined from the page"
    assert declined.state == "needs_you"         # nothing but the record does it


def test_a_row_names_the_worktree_by_its_top_not_where_it_started(ws):
    """The row's second line is the repository and the worktree. A session
    started in `src` is still in `richpalm`: once git has said where the
    worktree begins, that is the folder named, and its whole path is the
    hover. Before git has answered, it is where the session started."""
    session = fold(ws, event("SessionStart", cwd="/w/agent/richpalm/src"))
    assert ws.row(session)["worktree"] == "src"
    session.git = ws.GitFacts(repo="agent", root="/w/agent/richpalm",
                              remote="https://example.com/agent.git")
    shown = ws.row(session)
    assert shown["worktree"] == "richpalm"
    assert shown["worktree_path"] == "/w/agent/richpalm"
    assert shown["remote"] == "https://example.com/agent.git"
