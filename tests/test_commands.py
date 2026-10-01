"""What the send box can complete: the skills and command files a session
can see, and the commands its transcripts say were run (#268)."""

from __future__ import annotations

import json
import shutil
import time
import urllib.request

import conftest
from conftest import FIXTURES, git_in, record, records


def command_record(name, args=""):
    """A `user` record for a slash command, the way Claude Code writes one."""
    return record("you", f"<command-name>/{name}</command-name>\n"
                         f"            <command-message>{name}</command-message>\n"
                         f"            <command-args>{args}</command-args>")


def local_command(name):
    """The other shape a command is written in: a `system` record
    (`tests/fixtures/local_command.jsonl`)."""
    return {"type": "system", "subtype": "local_command",
            "content": f"<command-name>/{name}</command-name>\n"
                       f"            <command-message>{name}</command-message>\n"
                       f"            <command-args></command-args>",
            "timestamp": "2026-09-26T04:09:51.639Z", "isMeta": False}


def staged(ws, tmp_path):
    """The fixture's project as a repository, and its `claude` folder as the
    Claude Code directory. Returns the project and the folder below it."""
    project = tmp_path / "project"
    shutil.copytree(FIXTURES / "commands" / "project", project)
    shutil.copytree(FIXTURES / "commands" / "claude", ws.claude_dir())
    git_in(project, "init", "-q", "-b", "main")
    return project, project / "sub"


def by_name(found):
    return {one.name: one for one in found}


def test_the_project_and_your_own_commands_are_read(ws, tmp_path):
    """Skills by their `name` or their folder, command files by their file
    name; nearest first, so the project's `review-pr` wins over yours; and
    nothing that is not a command: `user-invocable: false`, and a file in a
    subdirectory of `commands`, whose name is not known."""
    project, below = staged(ws, tmp_path)
    found = by_name(ws.Commands().of(str(below), str(project), []))
    assert sorted(found) == ["deploy", "notes", "review-pr", "standup"]
    assert found["review-pr"].came == "project"
    assert found["review-pr"].about.startswith("Review a pull request")
    assert found["review-pr"].hint == "[pull request number]"
    assert (found["deploy"].came, found["deploy"].hint) == ("project", "<environment>")
    assert found["notes"].came == "yours"
    assert found["notes"].about == "Write today's notes from the session, in the house style."
    assert (found["standup"].came, found["standup"].about) == ("yours", "")


def test_a_session_outside_a_repository_reads_only_its_own_directory(ws, tmp_path):
    project, below = staged(ws, tmp_path)
    assert "deploy" not in by_name(ws.Commands().of(str(below), "", []))
    assert "deploy" in by_name(ws.Commands().of(str(project), "", []))


def test_a_name_that_is_not_a_command_is_left_out(ws, tmp_path):
    """The name is what the box gets, and from there a terminal, so a skill
    that names itself something no command is called is not offered."""
    skills = ws.claude_dir() / "skills"
    for folder, name in [("a", "../../etc"), ("b", "two words"), ("c", "ok-name")]:
        (skills / folder).mkdir(parents=True)
        (skills / folder / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    assert sorted(by_name(ws.Commands().of(str(tmp_path), "", []))) == ["ok-name"]


def test_what_the_transcripts_say_was_run_is_counted(ws, tmp_path):
    """Built-in commands are in no file, so they come from the transcripts.
    A prompt that only mentions a command, and Claude Code's own words, are
    not a use of one."""
    project, below = staged(ws, tmp_path)
    one, two = tmp_path / "one.jsonl", tmp_path / "two.jsonl"
    one.write_text(records(command_record("clear"), command_record("deploy", "prod"),
                           record("you", "what does <command-name>/clear</command-name> do?"),
                           record("meta", "<command-name>/clear</command-name>")))
    two.write_text(records(command_record("clear"), local_command("context")))
    found = ws.Commands().of(str(below), str(project), [one, two])
    named = by_name(found)
    assert (named["clear"].uses, named["clear"].came) == (2, "used")
    assert (named["deploy"].uses, named["deploy"].came) == (1, "project")
    assert named["context"].uses == 1
    assert [one.name for one in found][:3] == ["clear", "context", "deploy"]


def test_a_transcript_is_read_on_from_where_it_stopped(ws, tmp_path):
    """Asking again costs only what was written since; a transcript written
    again from nothing counts again from nothing."""
    path = tmp_path / "t.jsonl"
    path.write_text(records(command_record("clear")))
    held = ws.Commands()
    assert held.used([path])["clear"] == 1
    with path.open("a") as handle:
        handle.write(records(command_record("clear")))
    assert held.used([path])["clear"] == 2
    path.write_text(records(command_record("model")))
    assert dict(held.used([path])) == {"model": 1}


def test_the_daemon_answers_with_the_commands(ws, served, tmp_path, transcript_file):
    daemon, base = served
    project, below = staged(ws, tmp_path)
    path = transcript_file("s1", [command_record("compact")])
    ws.append_event(conftest.event("SessionStart", cwd=str(below), ts=time.time(),
                                   transcript_path=str(path)))
    daemon.store.refresh()
    with urllib.request.urlopen(f"{base}/api/session/s1/commands", timeout=5) as answer:
        body = json.loads(answer.read())
    named = {one["name"]: one for one in body["commands"]}
    assert named["compact"] == {"name": "compact", "about": "", "hint": "",
                                "came": "used", "uses": 1}
    assert named["deploy"]["came"] == "project"
