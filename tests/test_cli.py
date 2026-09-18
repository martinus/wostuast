"""The commands: ls, doctor, and the small pieces they print."""

from __future__ import annotations

import json


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


def test_ls_prints_one_row_per_session(ws, recorded_events, capsys, monkeypatch):
    path = ws.events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in recorded_events))
    monkeypatch.setattr(ws, "SESSION_MAX_AGE", 10**12)
    monkeypatch.setattr(ws, "pid_alive", lambda pid: True)
    assert ws.cmd_ls(None) == 0
    out = capsys.readouterr().out
    assert "STATE" in out
    assert "oans/warmhare" not in out  # no git repository in the test environment
    assert "warmhare" in out
    assert "calmpuma" in out
    assert "%7" in out
    assert "1 done · 1 ended" in out


def test_ls_shows_the_name_from_the_status_file(ws, recorded_events, recorded_status,
                                                capsys, monkeypatch):
    path = ws.events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in recorded_events))
    ws.write_status(recorded_status["session_id"],
                    ws.status_from_payload(recorded_status, now=1.0))
    monkeypatch.setattr(ws, "SESSION_MAX_AGE", 10**12)
    monkeypatch.setattr(ws, "pid_alive", lambda pid: True)
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
    rows = [["a", "bbb", "x"], ["cccc", "d", "y"]]
    assert ws.table(rows, ["", ""], color=False) == "a     bbb  x\ncccc  d    y"


def test_no_color_when_asked(ws):
    assert ws.paint("x", "needs_you", color=False) == "x"
    assert ws.paint("x", "needs_you", color=True).startswith("\033[")


def test_serve_says_it_is_not_here_yet(ws, capsys):
    assert ws.cmd_serve(None) == 1
    assert "milestone 2" in capsys.readouterr().err
