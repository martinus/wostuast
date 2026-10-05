"""What one agent starts (#422): a `claude -p` it runs from its Bash tool,
which is a session of its own, and the subagents of its Agent tool, which
are not. The page draws both as lines under the agent's row."""

from __future__ import annotations

import json
import subprocess

from conftest import ROOT, as_claude, event


def folded(ws, *events):
    store = ws.Store()
    for one in events:
        store.apply(one)
    return store


def child(sid, by, **extra):
    """An event of a `claude -p`: no pane, a pid of its own, and the pid of
    the agent that ran it, as the hook writes them."""
    return event(extra.pop("name", "SessionStart"), sid=sid, pane="", pid=5000,
                 started_by=by, **extra)


def test_a_session_an_agent_ran_names_that_agent_s_session(ws):
    """Nothing in a `claude -p`'s payload names the agent that ran it; the
    hook finds that agent's pid above it (`claude_from`), and the store the
    session of that pid (`Store.parent_of`)."""
    store = folded(ws, event("SessionStart", sid="parent", pid=4242),
                   child("kid", 4242, ts=1001.0))
    assert store.sessions["kid"].started_by == "parent"
    row = ws.row(store.sessions["kid"])
    assert row["started_by"] == "parent"
    assert row["started_at"] == 1001.0
    assert ws.row(store.sessions["parent"])["started_by"] == ""


def test_a_child_is_linked_only_to_a_session_still_running(ws):
    """A pid is no identity: the numbers come round again. The session that
    had it and ended is not the parent; with two, the one heard from last
    is. Nobody found is no parent, and the child stays a row."""
    store = folded(ws, event("SessionStart", sid="old", pid=4242, ts=900.0),
                   event("SessionEnd", sid="old", pid=4242, ts=950.0),
                   child("kid", 4242, ts=1001.0))
    assert store.sessions["kid"].started_by == ""
    store = folded(ws, event("SessionStart", sid="a", pid=4242, ts=900.0),
                   event("SessionStart", sid="b", pid=4242, ts=990.0),
                   child("kid", 4242, ts=1001.0))
    assert store.sessions["kid"].started_by == "b"
    store = folded(ws, event("SessionStart", sid="a", pid=4242),
                   child("kid", 0), child("kid2", 7777))
    assert store.sessions["kid"].started_by == store.sessions["kid2"].started_by == ""


def test_a_child_s_child_stands_under_the_first_row(ws):
    """The page draws a child as a line, and a line has no lines of its
    own: a grandchild under a child would be drawn nowhere."""
    store = folded(ws, event("SessionStart", sid="top", pid=4242),
                   child("kid", 4242),
                   event("SessionStart", sid="grandkid", pane="", pid=6000,
                         started_by=5000))
    assert store.sessions["grandkid"].started_by == "top"


def test_the_agent_tool_s_subagents_are_kept_on_their_session(ws):
    """Measured on 2.1.289: `SubagentStart`, the subagent's tool calls and
    `SubagentStop` all come under the session that started it, each with
    its `agent_id`. The description is the Agent call's: `SubagentStart`
    carries none. The parent's state is the parent's."""
    store = folded(
        ws,
        event("UserPromptSubmit", prompt="go"),
        event("PreToolUse", tool_name="Agent", ts=1001.0,
              tool_input={"description": "look around", "prompt": "run ls"}),
        event("PreToolUse", tool_name="Agent", ts=1002.0,
              tool_input={"description": "read the docs", "prompt": "read"}),
        event("SubagentStart", agent_id="a1", agent_type="Explore", ts=1003.0),
        event("SubagentStart", agent_id="a2", agent_type="general-purpose", ts=1004.0),
        event("PreToolUse", agent_id="a1", agent_type="Explore", tool_name="Bash",
              tool_input={"command": "ls -la"}, ts=1005.0),
        event("SubagentStop", agent_id="a2", agent_type="general-purpose", ts=1006.0),
        event("SubagentStop", agent_id="a2", agent_type="general-purpose", ts=1007.0),
    )
    session = store.sessions["s1"]
    assert session.state == "working"
    row = ws.row(session)
    assert row["subagents"] == [
        {"id": "a1", "kind": "Explore", "what": "look around", "doing": "Bash ls -la",
         "started": 1003.0, "ended": 0},
        {"id": "a2", "kind": "general-purpose", "what": "read the docs", "doing": "",
         "started": 1004.0, "ended": 1006.0}]
    assert row["agents_ran"] == 1, "a second SubagentStop counted it twice"


def test_a_subagent_is_named_by_its_call_s_result_and_found_without_its_start(ws):
    """Hooks installed before `SubagentStart` was one of ours send none: the
    subagent is found by its first tool call. A background call's result
    names its `agentId` and description, which is surer than the order."""
    store = folded(
        ws,
        event("PreToolUse", agent_id="a9", agent_type="Explore", tool_name="Read",
              tool_input={"file_path": "/w/repo/dir/a.py"}, ts=1001.0),
        event("PostToolUse", tool_name="Agent", ts=1002.0,
              tool_input={"description": "ignored"},
              tool_response={"isAsync": True, "agentId": "a9",
                             "description": "find the cache"}),
    )
    one = store.sessions["s1"].subagents["a9"]
    assert (one.kind, one.what, one.started) == ("Explore", "find the cache", 1001.0)
    assert one.doing.startswith("Read")


def test_a_session_keeps_only_the_last_subagents_and_counts_them_all(ws, monkeypatch):
    """An agent can start hundreds in a day, and the row goes out on every
    change: the ended ones go first, the running ones stay."""
    monkeypatch.setattr(ws, "SUBAGENTS_HELD", 3)
    events = [event("SubagentStart", agent_id="run", ts=1000.0)]
    for n in range(5):
        events += [event("SubagentStart", agent_id=f"a{n}", ts=1001.0 + n),
                   event("SubagentStop", agent_id=f"a{n}", ts=1001.5 + n)]
    session = folded(ws, *events).sessions["s1"]
    assert list(session.subagents) == ["run", "a3", "a4"]
    assert session.agents_ran == 5


def test_a_session_that_is_over_has_no_subagent_running(ws):
    """One gone before its `SubagentStop` would run on the page for ever:
    a `SessionEnd`, or a process found dead (`_bury`), ends them."""
    session = folded(ws, event("SubagentStart", agent_id="a1"),
                     event("SessionEnd", ts=1100.0)).sessions["s1"]
    assert (session.subagents["a1"].ended, session.agents_ran) == (1100.0, 1)
    session = folded(ws, event("SubagentStart", agent_id="a1")).sessions["s1"]
    ws.mark_dead(session, alive=lambda pid: False, now=1200.0)
    assert (session.subagents["a1"].ended, session.agents_ran) == (1200.0, 1)


def test_the_hook_names_the_agent_that_ran_a_claude_p(ws, tmp_path):
    """The hook of a `claude -p` an agent ran walks on past it to that
    agent (`claude_from`), and only for an agent with no terminal: one at a
    terminal pays nothing for it. The stand-ins are `claude` processes, an
    agent at a terminal running one with a pipe for its stdin, which runs
    the hook."""
    path = tmp_path / "share" / "wostuast" / "hook.py"
    ws.write_program(path, ws.hook_source((ROOT / "wostuast").read_text(encoding="utf-8")))
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
           "WOSTUAST_STATE": str(tmp_path / "state"), "TMUX_PANE": "%3"}
    folder = tmp_path / "stand-in"
    payload = json.dumps({"session_id": "s1", "hook_event_name": "SessionStart"})
    done = as_claude([str(path)], payload, env, folder, "terminal")
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    log = tmp_path / "state" / "events.jsonl"
    alone = json.loads(log.read_text())
    assert alone["started_by"] == 0, "an agent at a terminal was taken for a child"
    log.unlink()
    claude, script = str(folder / "claude"), str(folder / "stand_in.py")
    outer = subprocess.Popen([claude, script, "terminal", claude, script, "pipe", str(path)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=env)
    out, err = outer.communicate(payload, timeout=60)
    assert (outer.returncode, out, err) == (0, "", "")
    line = json.loads(log.read_text())
    assert line["pid"] > 0 and line["pid"] != outer.pid
    assert line["pane"] == ""
    assert line["started_by"] == outer.pid
