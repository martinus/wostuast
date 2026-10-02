"""`wostuast files` (#321) and `wostuast report` (#323): what wostuast put on
the disk, and a Markdown report an agent can read to improve it."""

from __future__ import annotations

import argparse
import json
import time

import pytest


def events(ws, *found, at=None):
    """Write these events into the log, stamped now unless they say."""
    now = time.time() if at is None else at
    for one in found:
        ws.append_event({"ts": now, **one})


def installed(ws, tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "install_path", lambda: tmp_path / "bin" / "wostuast")
    ws.cmd_install(None)


def test_the_report_never_holds_the_readers_text(ws, tmp_path, monkeypatch):
    """It is meant to be handed to an agent and pasted into an issue, so it
    holds names and counts only (#323). Every place the reader's text can
    stand -- a prompt, a command, a path, a message, a kind that is not a
    name, a line of the error log -- is written here, and none comes out."""
    events(ws,
           {"session_id": "s1", "hook_event_name": "SessionStart",
            "source": "startup", "cwd": "/home/Secretive/proj"},
           {"session_id": "s1", "hook_event_name": "UserPromptSubmit",
            "prompt": "SECRETIVE prompt"},
           {"session_id": "s1", "hook_event_name": "PreToolUse",
            "tool_name": "Bash", "tool_input": {"command": "rm -rf secretive"}},
           {"session_id": "s1", "hook_event_name": "Notification",
            "notification_type": "a secretive kind", "message": "secretive"},
           {"session_id": "s1", "hook_event_name": "PreToolUse",
            "tool_name": "secretive tool with spaces"})
    ws.log("could not read /home/secretive/file: PermissionError(13, 'denied')")
    said = ws.build_report(7, measure=False)
    assert "secretive" not in said.lower(), said
    assert str(tmp_path) not in said, said
    # Named, not only hidden: an agent can tell which folder a line means.
    assert "<state dir>" in said, said
    # What it may say, it does say.
    assert "PermissionError" in said
    assert "| Bash | 1 |" in said
    assert "startup (1)" in said
    assert "(other)" in said


def test_what_the_review_found_does_not_leak_either(ws, tmp_path, monkeypatch):
    """Each of these reached the report once, in a review before it shipped:
    a log line that names a folder ending in "Error", a line a newline began,
    an MCP server's name, a bad ticket-link pattern quoted back, a folder of
    ours that holds home, a path no swap knows, a nested line that crashed."""
    events(ws, {"session_id": "s1", "hook_event_name": "PreToolUse",
                "tool_name": "mcp__acmecorp-jira__create_issue"})
    with open(ws.events_path(), "a", encoding="utf-8") as handle:
        handle.write("[" * 100000 + "\n")
    ws.log("listing /home/m/AcmeCorpError/src failed: OSError(5, 'io')")
    ws.log("could not answer: AcmecorpWidgetError('x')")
    with open(ws.log_path(), "a", encoding="utf-8") as handle:
        handle.write("acmecorp-continued line\n")
    ws.state_dir_trouble()
    ws.config_path().parent.mkdir(parents=True, exist_ok=True)
    ws.config_path().write_text(json.dumps({"links": [
        {"match": "(?P<acmecorp payroll>x)", "url": "https://x.example/$1"}]}))
    said = ws.build_report(7, measure=False)
    assert "acmecorp" not in said.lower(), said
    assert "| OSError | 1 |" in said, said
    assert "| (other) | 2 |" in said, said
    assert "mcp__\u2026__create_issue" in said, said
    private = ws.private_paths()
    assert private("in /srv/elsewhere/acmecorp/x.txt") == "in <path>"
    assert private("run `~/bin/wostuast install`") == "run `~/bin/wostuast install`"
    monkeypatch.setattr(ws, "settings_path", lambda: ws.Path("/home/claude-cfg.json"))
    monkeypatch.setattr(ws.Path, "home", lambda: ws.Path("/home/alice"))
    assert "alice" not in ws.private_paths()("at /home/alice/.local/x")


def test_a_table_cell_holds_no_newline(ws):
    assert ws.report_table(("A",), [("one\ntwo|three",)])[2] == "| one two\\|three |"


def test_a_new_event_and_a_new_field_are_named(ws):
    """What wostuast does not read yet is what an agent can add. An event
    Claude Code sends that no handler takes is marked new, and every field
    an event carried is listed by name."""
    events(ws, {"session_id": "s1", "hook_event_name": "Stop"},
           {"session_id": "s1", "hook_event_name": "BrandNewEvent", "shiny_field": 1})
    said = ws.build_report(7, measure=False)
    assert "| BrandNewEvent | 1 | **new** |" in said, said
    assert "| Stop | 1 | yes |" in said, said
    assert "shiny_field (1)" in said, said


def test_only_the_days_asked_for_are_counted(ws):
    old = time.time() - 10 * 86400
    events(ws, {"session_id": "s1", "hook_event_name": "Stop"}, at=old)
    events(ws, {"session_id": "s2", "hook_event_name": "SessionEnd", "reason": "clear"})
    said = ws.build_report(7, measure=False)
    assert "| SessionEnd | 1 | yes |" in said
    assert "| Stop |" not in said
    assert "SessionEnd.reason | clear (1)" in said


def test_the_report_is_markdown_an_agent_can_read(ws):
    """One heading a section, tables with a head, and a preamble that says
    what wostuast is and what the report may hold."""
    said = ws.build_report(7, measure=False)
    assert said.startswith("# wostuast report\n")
    for section in ("## Versions", "## Setup", "## Files", "## Hook events",
                    "## Transcripts", "## Errors", "## Cost"):
        assert f"\n{section}" in said, section
    assert "names, counts, sizes and timings only" in said
    for line in said.splitlines():
        if line.startswith("|"):
            assert line.endswith("|"), line


def test_the_cost_is_measured_on_the_installed_files(ws, tmp_path, monkeypatch):
    """The hook and the status file, run as Claude Code runs them. Not
    installed, they did not run, and the report says so rather than 0 ms."""
    said = ws.build_report(7)
    assert "| hook.py, one event | did not run |" in said
    installed(ws, tmp_path, monkeypatch)
    said = ws.build_report(7)
    took = [line for line in said.splitlines() if line.startswith("| hook.py")]
    assert took and took[0].endswith(" ms |"), took


def test_files_lists_what_is_there_and_what_uninstall_does(ws, tmp_path,
                                                           monkeypatch, capsys):
    installed(ws, tmp_path, monkeypatch)
    events(ws, {"session_id": "s1", "hook_event_name": "Stop"})
    capsys.readouterr()
    assert ws.cmd_files(argparse.Namespace()) == 0
    said = capsys.readouterr().out
    assert "Run by Claude Code (uninstall removes these)" in said
    assert "History (uninstall keeps it: it is yours)" in said
    hook = [line for line in said.splitlines() if "hook.py" in line]
    assert hook and "(not there)" not in hook[0], said
    names = [line for line in said.splitlines() if "names.json" in line]
    assert names and "(not there)" in names[0], said
    # The old links file is listed only when it is there, to be deleted.
    assert "links.json" not in said


def test_archives_and_status_files_are_counted(ws):
    rows = {row.path.name: row for row in ws.installed_files()}
    assert rows["events.N.jsonl"].count == 0
    ws.state_dir_trouble()
    for n in (1, 2):
        ws.state_dir().joinpath(f"events.{n}.jsonl").write_text("{}\n")
    ws.status_dir().mkdir(parents=True)
    for sid in ("a", "b", "c"):
        ws.status_path(sid).write_text("{}")
    rows = {row.path.name: row for row in ws.installed_files()}
    assert rows["events.N.jsonl"].count == 2 and rows["events.N.jsonl"].there
    assert rows["status"].count == 3


def test_every_file_wostuast_writes_is_listed(ws):
    """`installed_files` is the one list, for `files` and the report. A new
    file on the disk was easy to leave out of it, so every path function of
    the program has to be on it -- or named here as not a file of ours."""
    not_files = {"state_dir", "claude_dir"}
    listed = {row.path for row in ws.installed_files()}
    listed.add(ws.links_path())            # listed only while it is there
    for name in dir(ws):
        if not (name.endswith("_path") or name.endswith("_dir")) or name in not_files:
            continue
        made = getattr(ws, name)
        try:
            path = made()
        except TypeError:
            continue                       # takes an argument: one of many
        assert path in listed, f"{name}() is not in installed_files"


def test_shapes_is_now_part_of_the_report(ws, capsys, monkeypatch):
    assert ws.main(["shapes"]) == 1
    assert "`wostuast report`" in capsys.readouterr().err


def test_report_is_a_command(ws, capsys):
    assert ws.main(["report", "--days", "1"]) == 0
    assert capsys.readouterr().out.startswith("# wostuast report\n")


@pytest.mark.parametrize("value, shown", [
    ("startup", "startup"), ("permission_prompt", "permission_prompt"),
    ("mcp__github__create_pull_request", "mcp__github__create_pull_request"),
    ("has a space", "(other)"), ("/home/m/x", "(other)"), (7, "(other)"),
    ("x" * 65, "(other)"),
])
def test_a_value_is_shown_only_when_it_is_a_name(ws, value, shown):
    assert ws.named(value) == shown


def test_the_report_reads_the_log_it_writes(ws):
    """The report and the hook agree on the shape of a line."""
    events(ws, {"session_id": "s1", "hook_event_name": "Stop"})
    assert [e["hook_event_name"] for e in ws.recent_events(1)] == ["Stop"]
    assert json.loads(ws.events_path().read_text().splitlines()[0])["session_id"] == "s1"
