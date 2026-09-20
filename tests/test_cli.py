"""The commands: ls, doctor, and the small pieces they print."""

from __future__ import annotations

import argparse
import time

import conftest



def test_tool_summaries(ws):
    cwd = "/w/dir"
    assert ws.tool_summary("Read", {"file_path": "/w/dir/src/table.cpp"}, cwd) == "Read src/table.cpp"
    assert ws.tool_summary("Write", {"file_path": "/w/dir/PLAN.md"}, cwd) == "Write PLAN.md"
    assert ws.tool_summary("Edit", {"file_path": "/other/x.py"}, cwd) == "Edit /other/x.py"
    assert ws.tool_summary("Bash", {"command": "pytest -q"}, cwd) == "Bash pytest -q"
    assert ws.tool_summary("Grep", {"pattern": "resolve_branch"}, cwd) == "Grep resolve_branch"
    assert ws.tool_summary("Glob", {"pattern": "**/*.py"}, cwd) == "Glob **/*.py"
    assert ws.tool_summary("Task", {"description": "look around"}, cwd) == "Task look around"
    assert ws.tool_summary("WebFetch", {"url": "https://x"}, cwd).startswith("WebFetch {")
    assert ws.tool_summary("Mystery", {}, cwd) == "Mystery"
    assert ws.tool_summary("", None, cwd) == "tool"


def test_a_long_command_is_cut(ws):
    summary = ws.tool_summary("Bash", {"command": "x" * 200}, "")
    assert len(summary) == len("Bash ") + 60
    assert summary.endswith("…")


def test_clip_collapses_whitespace(ws):
    assert ws.clip("a\n  b\tc", 10) == "a b c"


def test_ago_reads_in_words(ws):
    assert ws.ago(5) == "5 s"
    assert ws.ago(90) == "1 min"
    assert ws.ago(7200) == "2 h"
    assert ws.ago(200000) == "2 d"
    assert ws.ago(-5) == "0 s"


def test_the_changes_column(ws):
    assert ws.changes_column(ws.GitFacts(branch="main")) == "✓"
    assert ws.changes_column(ws.GitFacts(branch="main", ahead=2, dirty=True,
                                         touched_files=5)) == "↑2 ●5"
    assert ws.changes_column(ws.GitFacts(branch="main", behind=1)) == "↓1 ✓"
    assert ws.changes_column(ws.GitFacts()) == ""


def test_ls_without_sessions_explains_itself(ws, capsys):
    assert ws.cmd_ls(None) == 0
    out = capsys.readouterr().out
    assert "no sessions yet" in out
    assert "doctor" in out


def test_ls_prints_one_row_per_session(ws, written_events, capsys):
    assert ws.cmd_ls(None) == 0
    out = capsys.readouterr().out
    assert "STATE" in out
    assert "oans/warmhare" not in out  # no git repository in the test environment
    assert "warmhare" in out
    assert "calmpuma" in out
    assert "%7" in out
    assert "1 ready · 1 ended" in out


def test_ls_shows_the_name_from_the_status_file(ws, written_events, recorded_status, capsys):
    ws.write_status(recorded_status["session_id"],
                    ws.status_from_payload(recorded_status, now=1.0))
    ws.cmd_ls(None)
    assert "warmhare" in capsys.readouterr().out


def test_doctor_reports_a_missing_install(ws, capsys):
    code = ws.cmd_doctor(None)
    out = capsys.readouterr().out
    assert "wostuast doctor" in out
    assert "hooks missing" in out
    assert code == 1


def test_doctor_is_happy_after_install(ws, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ws, "install_path", lambda: tmp_path / "bin" / "wostuast")
    ws.cmd_install(None)
    capsys.readouterr()
    code = ws.cmd_doctor(None)
    out = capsys.readouterr().out
    assert "all good." in out
    assert code == 0


def test_the_table_pads_every_column_but_the_last(ws):
    rows = [("", ["a", "bbb", "x"]), ("", ["cccc", "d", "y"])]
    assert ws.table(rows, color=False) == "a     bbb  x\ncccc  d    y"


def test_the_table_colours_a_row_by_its_own_state(ws):
    rows = [("", ["head"]), ("needs_you", ["row"])]
    lines = ws.table(rows, color=True).splitlines()
    assert lines[0] == "head"
    assert lines[1].startswith("\033[") and "row" in lines[1]


def test_no_color_when_asked(ws):
    assert ws.paint("x", "needs_you", color=False) == "x"
    assert ws.paint("x", "needs_you", color=True).startswith("\033[")


def test_serve_says_so_when_the_port_is_taken(ws, capsys):
    """It must not crash with a traceback when another wostuast is running."""
    import socket

    held = socket.socket()
    held.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    held.bind((ws.BIND_HOST, 0))
    held.listen(1)
    port = held.getsockname()[1]
    try:
        args = argparse.Namespace(port=port, open=False)
        assert ws.cmd_serve(args) == 1
        assert "cannot listen" in capsys.readouterr().err
    finally:
        held.close()


def test_hook_and_status_skip_the_argument_parser(ws, monkeypatch):
    """They run on every tool call and every redraw, so they must stay cheap."""
    built = False

    def fail_if_built():
        nonlocal built
        built = True
        raise AssertionError("build_parser must not run for hook or status")

    monkeypatch.setattr(ws, "build_parser", fail_if_built)
    monkeypatch.setattr(ws, "cmd_hook", lambda args: 0)
    monkeypatch.setattr(ws, "cmd_status", lambda args: 0)
    monkeypatch.setattr(ws, "FAST_PATH", {"hook": ws.cmd_hook, "status": ws.cmd_status})
    assert ws.main(["hook"]) == 0
    assert ws.main(["status"]) == 0
    assert built is False


def test_every_other_command_still_goes_through_the_parser(ws, capsys):
    assert ws.main([]) == 0
    assert "usage: wostuast" in capsys.readouterr().out


def test_a_notebook_edit_shows_its_path(ws):
    assert ws.tool_summary(
        "NotebookEdit", {"notebook_path": "/w/dir/study.ipynb"}, "/w/dir"
    ) == "NotebookEdit study.ipynb"


def test_the_store_keeps_the_whole_prompt(ws):
    """The sidebar clips for its column. The page wants the full text."""
    store = ws.Store()
    long_prompt = "please " + "x" * 300
    store.apply({"session_id": "s", "hook_event_name": "UserPromptSubmit",
                 "prompt": long_prompt, "ts": 1.0})
    session = store.sessions["s"]
    assert session.last_prompt == long_prompt
    assert long_prompt in session.last_event
    assert len(ws.clip(session.last_event, 60)) == 60


def test_ls_does_not_pass_an_escape_sequence_to_the_terminal(ws, capsys):
    """`session.reason` is a `Notification` message or a summary of a tool
    input: text an agent wrote, which a hostile file or a prompt injection can
    steer. It went to stdout unfiltered — one set the terminal's title and
    turned the rest of the output red, and the column widths went wrong
    besides, because `len` counts the escape bytes.

    The page uses `textContent` for exactly this text and `tmux_send` strips
    it. `ls` is the same data on the same terminal.
    """
    nasty = "\x1b]0;pwned\x07\x1b[31mtook over the terminal"
    ws.append_event(conftest.event("SessionStart", cwd="/w/one", pane="%7",
                                   pid=1, ts=time.time()))
    ws.append_event(conftest.event("Notification", cwd="/w/one",
                                   message=nasty, ts=time.time()))
    assert ws.cmd_ls(None) == 0
    out = capsys.readouterr().out
    assert "took over the terminal" in out
    assert "\x1b" not in out
    assert "\x07" not in out
