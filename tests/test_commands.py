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


def installed(ws, scope="user", project=None, where=None, on=True, settings=None):
    """A plugin `demo` from the marketplace `mk`, with a command and a skill,
    as `claude plugin install` left it on 2.1.289 (#413): the files under
    `plugins/cache/mk/demo/1.0.0`, `installed_plugins.json` (version 2)
    naming that folder, and `enabledPlugins` in a settings file."""
    base = ws.claude_dir() / "plugins"
    folder = where or base / "cache" / "mk" / "demo" / "1.0.0"
    (folder / "commands").mkdir(parents=True)
    (folder / "commands" / "hello.md").write_text("---\ndescription: Say hello\n---\nSay hello.\n")
    (folder / "skills" / "greet").mkdir(parents=True)
    (folder / "skills" / "greet" / "SKILL.md").write_text(
        "---\nname: greet\ndescription: Greet someone\n---\nGreet.\n")
    install = {"scope": scope, "installPath": str(folder), "version": "1.0.0",
               "installedAt": "2026-10-05T06:05:01.928Z"}
    if project:
        install["projectPath"] = str(project)
    base.mkdir(parents=True, exist_ok=True)
    (base / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": {"demo@mk": [install]}}))
    settings = settings or ws.settings_path()
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"enabledPlugins": {"demo@mk": on}}))


def test_a_plugins_commands_are_read_where_claude_code_installed_them(ws, tmp_path):
    """A plugin's command and skill, named `/plugin:name` as Claude Code
    runs them: they were listed as built in, with no file, though they were
    on the disk (#413). Their text is read like any other's, and what the
    transcripts counted of them is theirs."""
    installed(ws)
    found = by_name(ws.Commands().of(str(tmp_path), "", []))
    assert {"demo:hello", "demo:greet"} <= set(found), sorted(found)
    hello = found["demo:hello"]
    assert (hello.came, hello.about) == ("plugin", "Say hello")
    assert hello.file.endswith("plugins/cache/mk/demo/1.0.0/commands/hello.md"), hello.file
    assert found["demo:greet"].about == "Greet someone"
    assert ws.command_text(hello)[0].strip() == "Say hello."
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(records(command_record("demo:hello")))
    counted = by_name(ws.Commands().of(str(tmp_path), "", [transcript]))
    assert (counted["demo:hello"].came, counted["demo:hello"].uses) == ("plugin", 1)


def test_a_plugin_is_read_only_where_it_is_on(ws, tmp_path):
    """Off in the settings, off for a project that turned it off, only in
    its own project when installed for one, and never from a folder
    outside Claude Code's `plugins` (#413)."""
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    names = lambda where: set(by_name(ws.Commands().of(str(where), "", [])))
    installed(ws, on=False)
    assert "demo:hello" not in names(tmp_path)
    shutil.rmtree(ws.claude_dir() / "plugins")
    installed(ws)
    (project / ".claude" / "settings.json").write_text(
        json.dumps({"enabledPlugins": {"demo@mk": False}}))
    assert "demo:hello" in names(tmp_path) and "demo:hello" not in names(project)
    (project / ".claude" / "settings.local.json").write_text(
        json.dumps({"enabledPlugins": {"demo@mk": True}}))
    assert "demo:hello" in names(project)
    shutil.rmtree(ws.claude_dir() / "plugins")
    (project / ".claude" / "settings.json").unlink()
    installed(ws, scope="project", project=project)
    assert "demo:hello" in names(project) and "demo:hello" not in names(tmp_path)
    shutil.rmtree(ws.claude_dir() / "plugins")
    installed(ws, where=tmp_path / "elsewhere")
    assert "demo:hello" not in names(tmp_path)
    (ws.claude_dir() / "plugins" / "installed_plugins.json").write_text("{not json")
    assert "demo:hello" not in names(tmp_path)


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
                                "came": "used", "uses": 1, "file": ""}
    assert named["deploy"]["came"] == "project"



# --- the Commands tab (#367) -----------------------------------------------------


def command_route(base, name):
    from urllib.parse import quote
    try:
        with urllib.request.urlopen(
                f"{base}/api/session/s1/command?name={quote(name)}", timeout=5) as answer:
            return answer.status, json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        return refused.status, json.loads(refused.read())


def a_session_in(ws, daemon, below, transcript_file, *used):
    path = transcript_file("s1", [command_record(one) for one in used])
    ws.append_event(conftest.event("SessionStart", cwd=str(below), ts=time.time(),
                                   transcript_path=str(path)))
    daemon.store.refresh()


def test_a_command_is_read_by_its_name_without_its_frontmatter(ws, served, tmp_path,
                                                               transcript_file):
    """The tab draws what a command says, as Markdown; its frontmatter is
    shown beside it already, and its `---` lines would be rules."""
    daemon, base = served
    project, below = staged(ws, tmp_path)
    a_session_in(ws, daemon, below, transcript_file)
    status, body = command_route(base, "deploy")
    assert status == 200
    assert (body["text"], body["cut"]) == ("Deploy to $ARGUMENTS.\n", False)
    status, body = command_route(base, "notes")      # a skill of your own
    assert status == 200 and body["text"].strip()


def test_only_a_listed_file_is_read(ws, served, tmp_path, transcript_file):
    """A built-in has no file, so it has no text: the page does not ask,
    and the route has nothing to give. A name no file has, or a path, is
    not read."""
    daemon, base = served
    project, below = staged(ws, tmp_path)
    a_session_in(ws, daemon, below, transcript_file, "compact")
    # A real `.md` that no list holds, named by its path: only "listed, by
    # name" keeps it out, as every other name here fails `real_md` too.
    outside = tmp_path / "outside.md"
    outside.write_text("not a command\n")
    for name in ("compact", "../../etc/passwd", "nothing", str(outside)):
        status, body = command_route(base, name)
        assert status == 404 and "text" not in body, name


def test_a_command_that_links_to_a_secret_is_not_read(ws, served, tmp_path,
                                                      transcript_file):
    """An agent can write into its worktree's `.claude/commands` a link named
    `x.md` that points at a key. It is not listed, so the send box and the
    tab agree it is no command, and it is not read."""
    daemon, base = served
    project, below = staged(ws, tmp_path)
    secret = tmp_path / "id_rsa"
    secret.write_text("-----BEGIN PRIVATE KEY-----\n")
    (project / ".claude" / "commands" / "leak.md").symlink_to(secret)
    a_session_in(ws, daemon, below, transcript_file)
    with urllib.request.urlopen(f"{base}/api/session/s1/commands", timeout=5) as answer:
        listed = json.loads(answer.read())["commands"]
    assert "leak" not in [one["name"] for one in listed]
    status, body = command_route(base, "leak")
    assert status == 404 and "PRIVATE" not in json.dumps(body)


def test_a_folder_of_commands_linked_from_elsewhere_is_read(ws, served, tmp_path,
                                                             transcript_file):
    """Your own commands may live in a dotfiles repository, linked into
    place: a file that is a real `.md` is read wherever it lies."""
    daemon, base = served
    project, below = staged(ws, tmp_path)
    dotfiles = tmp_path / "dotfiles" / "commands"
    dotfiles.mkdir(parents=True)
    (dotfiles / "tidy.md").write_text("---\ndescription: Tidy up\n---\nTidy the tests.\n")
    shutil.rmtree(ws.claude_dir() / "commands")
    (ws.claude_dir() / "commands").symlink_to(dotfiles)
    a_session_in(ws, daemon, below, transcript_file)
    status, body = command_route(base, "tidy")
    assert status == 200 and body["text"] == "Tidy the tests.\n"


def test_a_long_command_is_cut_and_says_so(ws, served, tmp_path, transcript_file,
                                           monkeypatch):
    daemon, base = served
    monkeypatch.setattr(ws, "COMMAND_TEXT_MAX", 64)
    project, below = staged(ws, tmp_path)
    (project / ".claude" / "commands" / "long.md").write_text("x" * 500)
    a_session_in(ws, daemon, below, transcript_file)
    status, body = command_route(base, "long")
    assert body["cut"] is True and len(body["text"]) == 64


def test_frontmatter_comes_off_only_when_it_is_there(ws):
    assert ws.after_front("---\na: b\n---\n\nBody\n") == "Body\n"
    assert ws.after_front("No front\n---\n") == "No front\n---\n"
    assert ws.after_front("---\nnever closed\n") == "---\nnever closed\n"



def test_frontmatter_ends_in_the_same_place_for_keys_and_body(ws):
    """`front_matter` split on every line ending and `after_front` on
    newlines alone, so a file with CR endings had its keys read and its
    frontmatter drawn as rules."""
    text = "---\rdescription: Tidy\r---\rTidy the tests.\r"
    assert ws.front_matter(text) == {"description": "Tidy"}
    assert ws.after_front(text) == "Tidy the tests.\r"


def test_a_fifo_named_like_a_skill_is_not_listed(ws, tmp_path):
    """Opened to read its frontmatter, a FIFO held the request thread for
    ever."""
    import os
    import threading
    folder = ws.claude_dir() / "skills" / "stuck"
    folder.mkdir(parents=True)
    fifo = folder / "SKILL.md"
    os.mkfifo(fifo)
    found = {}
    # In a thread, so a listing that opens the FIFO fails here rather than
    # hanging the run, as it hung the request thread.
    reader = threading.Thread(daemon=True, target=lambda: found.update(
        by_name(ws.Commands().of(str(tmp_path), "", []))))
    reader.start()
    reader.join(5)
    try:
        assert not reader.is_alive(), "the listing opened the FIFO and waits on it"
        assert "stuck" not in found
    finally:
        if reader.is_alive():               # a writer lets the reader go
            os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
