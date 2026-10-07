"""A conversation the agents view moves to the background (`←` on an empty
prompt, measured on Claude Code 2.1.292). It goes on under a new id, in
Claude Code's own daemon, and the session it was gets no end. The page
showed three rows for one conversation: the old one, ready for ever; the
fork, with the same transcript up to the move; and the agents view's own
session, which is asked nothing."""

from __future__ import annotations

import json
import os
import subprocess
import sys

from conftest import FIXTURES, ROOT, event

# What the hook adds to each line of `background_move.jsonl`, as it found
# them: the old session in pane %1, the other two in the daemon, no pane.
OLD, VIEW, FORK = (json.loads(line)["session_id"] for line in
                   (FIXTURES / "background_move.jsonl").read_text().splitlines()[2:])
# The subagent the old session's `Stop` names as running when it moved.
AGENT = json.loads((FIXTURES / "background_move.jsonl").read_text().splitlines()[2]
                   )["background_tasks"][0]["id"]
ADDED = {
    OLD: {"pid": 4242, "pane": "%1"},
    VIEW: {"pid": 5001, "pane": "", "background": True, "moved_from": ""},
    FORK: {"pid": 5002, "pane": "", "background": True, "moved_from": OLD},
}


def recorded(**changes):
    out = []
    for at, line in enumerate((FIXTURES / "background_move.jsonl").read_text().splitlines()):
        one = json.loads(line)
        one.update(ADDED[one["session_id"]], ts=2000.0 + at)
        if one["hook_event_name"] == "SessionStart" and one["session_id"] == OLD:
            one.update(background=False, moved_from="")
        if one["session_id"] in changes:
            one.update(changes[one["session_id"]])
        out.append(one)
    return out


def folded(ws, events):
    store = ws.Store()
    for at, one in enumerate(events):
        store.apply(one)
        if at == 1:
            # A subagent of the old session, running when it moved.
            store.apply(event("SubagentStart", session_id=OLD, agent_id=AGENT,
                              agent_type="Explore", ts=2001.5))
    return store


def test_a_conversation_moved_to_the_background_is_one_row(ws):
    """The old session ends and names the fork, so the page follows it
    (`cleared_into`), as after a `/clear`; its subagents end with it. The
    agents view's own session has no row."""
    store = folded(ws, recorded())
    shown = {one.session_id for one in store.visible(2010.0)}
    assert shown == {OLD, FORK}, "the agents view's session is a row"
    old, fork = store.sessions[OLD], store.sessions[FORK]
    assert (old.state, old.end_reason) == ("ended", "background")
    assert (old.cleared_into, fork.cleared_from) == (FORK, OLD)
    assert ws.row(old)["cleared_into"] == FORK
    assert old.subagents[AGENT].ended == 2004.0, "its subagent ran on"
    assert fork.state == "done"


def test_the_reader_s_name_moves_with_it(ws):
    """Named in the pane before the move, it is the same conversation."""
    store = ws.Store()
    events = recorded()
    store.apply(events[0])
    store.rename(OLD, "the payments work")
    for one in events[1:]:
        store.apply(one)
    assert ws.read_names() == {FORK: "the payments work"}


def test_a_fork_typed_at_a_terminal_ends_nothing(ws):
    """`claude --resume X --fork-session` sends `source: "fork"` too, and
    the old session lives on in its own pane: two conversations, two rows.
    Only a fork in the background is a move, and only the hook can tell."""
    store = folded(ws, recorded(**{FORK: {"background": False, "moved_from": "",
                                          "pane": "%2"}}))
    old = store.sessions[OLD]
    # Working: its `Stop` left a subagent running (#447).
    assert old.state == "working" and old.cleared_into == ""
    assert old.subagents[AGENT].ended == 0
    assert {one.session_id for one in store.visible(2010.0)} == {OLD, FORK}
    assert store.sessions[VIEW].untasked()


def test_the_agents_view_s_session_is_a_row_once_it_has_a_task(ws):
    store = folded(ws, recorded())
    store.apply(event("UserPromptSubmit", session_id=VIEW, prompt="fix the build",
                      ts=2100.0))
    assert VIEW in {one.session_id for one in store.visible(2101.0)}


def test_a_line_from_an_older_hook_hides_nothing(ws):
    """A `SessionStart` with neither key -- the log before this change --
    is a session at a terminal, as it was."""
    events = [{k: v for k, v in one.items() if k not in ("background", "moved_from")}
              for one in recorded()]
    store = folded(ws, events)
    assert {one.session_id for one in store.visible(2010.0)} == {OLD, VIEW, FORK}
    assert store.sessions[OLD].state == "working"


HOST = r"""
import os, subprocess, sys
given = sys.stdin.buffer.read()
if sys.argv[1] == "host":
    # `claude bg-pty-host --bg-pty-host <socket> 200 50 -- <the agent>`
    rest = sys.argv[sys.argv.index("--") + 1:]
    sys.exit(subprocess.run(rest, input=given).returncode)
# The agent: a terminal for its stdin, as the daemon's pty gives it.
_, keys = os.openpty()
os.dup2(keys, 0)
sys.exit(subprocess.run([os.environ["HOOK"]], input=given).returncode)
"""


def test_the_hook_says_which_session_a_background_fork_carries_on(ws, tmp_path):
    """The stand-ins are `claude` processes with the command lines measured
    under Claude Code's daemon. Only `SessionStart` pays for the reads."""
    path = tmp_path / "share" / "wostuast" / "hook.py"
    ws.write_program(path, ws.hook_source((ROOT / "wostuast").read_text(encoding="utf-8")))
    folder = tmp_path / "stand-in"
    folder.mkdir()
    claude = folder / "claude"
    claude.symlink_to(sys.executable)
    (folder / "host.py").write_text(HOST)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "HOOK": str(path),
           "WOSTUAST_STATE": str(tmp_path / "state")}
    log = tmp_path / "state" / "events.jsonl"

    def hook(name, agent, host=True):
        command = [str(claude), str(folder / "host.py"), "agent", *agent]
        if host:
            command = [str(claude), str(folder / "host.py"), "host", "--bg-pty-host",
                       "/tmp/cc-daemon-0/x/pty/new.sock", "200", "50", "--", *command]
        payload = json.dumps({"session_id": "new", "hook_event_name": name,
                              "source": "fork"})
        done = subprocess.run(command, input=payload, capture_output=True, text=True,
                              env=env, timeout=60)
        assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
        line = json.loads(log.read_text().splitlines()[-1])
        return line.get("background"), line.get("moved_from")

    fork = ["--session-id", "new", "--fork-session", "--resume",
            "/home/you/.claude/projects/-w-repo dir/7d1e4b2a-3c9f.jsonl"]
    assert hook("SessionStart", fork) == (True, "7d1e4b2a-3c9f")
    assert hook("SessionStart", ["--fork-session", "--resume=7d1e4b2a"]) == (True, "7d1e4b2a")
    assert hook("SessionStart", ["--agent", "claude"]) == (True, "")
    assert hook("SessionStart", fork, host=False) == (False, ""), "a fork at a terminal"
    assert hook("UserPromptSubmit", fork) == (None, None), "only a start pays"
    assert os.access(path, os.X_OK)
