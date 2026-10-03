"""The line that brings back a session that is over (#352)."""

from __future__ import annotations

import shlex

import pytest

import conftest


def over(ws, **fields):
    session = ws.Session(session_id=fields.pop("sid", "6fd6e34e-45f6-4953-a454-6c0d9ec151dc"),
                         state="ended", **fields)
    return session


def test_it_goes_to_where_the_session_started_not_where_the_agent_walked(ws):
    """`claude --resume` finds a session only from the folder it started in:
    measured, anywhere else it asked to trust the folder and found nothing."""
    session = over(ws, home="/w/my repo", cwd="/w/my repo/src")
    assert shlex.split(ws.resume_command(session)) == [
        "cd", "/w/my repo", "&&", "claude", "--resume", session.session_id]


def test_every_part_is_quoted_and_a_control_character_gives_no_line(ws):
    """The folder and the id came out of an event, and the reader runs the
    line: a quote or a `$(…)` in either is a word, never a command."""
    folder = "/w/it's $(rm -rf ~)"
    line = ws.resume_command(over(ws, home=folder))
    assert shlex.split(line)[:2] == ["cd", folder]
    assert ws.resume_command(over(ws, home="/w/a\nb")) == ""
    assert ws.resume_command(over(ws, home="/w/x", sid="s1; rm -rf ~")) == ""
    assert ws.resume_command(over(ws, home="")) == ""


def test_another_config_folder_is_named_in_front(ws, monkeypatch, tmp_path):
    """A transcript under a second account's config folder: `claude` must be
    told where it is, or it looks in `~/.claude` and finds nothing."""
    monkeypatch.setenv("HOME", str(tmp_path))
    work = tmp_path / "work" / "projects" / "-w-x" / "id.jsonl"
    line = ws.resume_command(over(ws, home="/w/x", transcript_path=str(work)))
    assert shlex.split(line)[3:5] == ["CLAUDE_CONFIG_DIR=" + str(tmp_path / "work"), "claude"]
    usual = tmp_path / ".claude" / "projects" / "-w-x" / "id.jsonl"
    line = ws.resume_command(over(ws, home="/w/x", transcript_path=str(usual)))
    assert "CLAUDE_CONFIG_DIR" not in line


def test_only_a_session_that_is_over_carries_one(ws):
    session = over(ws, home="/w/x")
    assert ws.row(session)["resume"]
    session.state = "done"
    assert ws.row(session)["resume"] == ""
