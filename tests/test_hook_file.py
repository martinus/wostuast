"""The hook file `install` writes (#271): the hook's own functions, copied
out of wostuast, so an event no longer compiles the whole program."""

from __future__ import annotations

import builtins
import json
import os
import subprocess
import symtable

import pytest

from conftest import ROOT, as_claude

SOURCE = (ROOT / "wostuast").read_text(encoding="utf-8")


def written(ws, tmp_path):
    """The hook file for this checkout, where a test can run it."""
    path = tmp_path / "share" / "wostuast" / "hook.py"
    ws.write_program(path, ws.hook_source(SOURCE))
    return path


def run_hook(path, home, payload, keys="terminal"):
    """Run the hook file as Claude Code does: by its own name, through its
    `#!`, in a bare environment, under an agent whose stdin is `keys`."""
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
           "WOSTUAST_STATE": str(home / "state"), "TMUX_PANE": "%3"}
    return as_claude([str(path)], json.dumps(payload), env, home / "stand-in", keys)


@pytest.mark.parametrize("keys, pane", [("terminal", "%3"), ("pipe", "")])
def test_an_agent_that_reads_no_terminal_has_no_pane(ws, tmp_path, keys, pane):
    """A Remote Control session (`claude rc`) and a `claude -p` read a pipe,
    and inherit the pane they were started in: a send went into the rc
    screen, or into another agent's prompt. With no pane, nothing is typed
    into it, and the page says why (`reads_terminal`)."""
    path = written(ws, tmp_path)
    done = run_hook(path, tmp_path, {"session_id": "s1",
                                     "hook_event_name": "UserPromptSubmit"}, keys)
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    line = json.loads((tmp_path / "state" / "events.jsonl").read_text())
    assert line["pid"] > 0, "the stand-in was not taken for the agent"
    assert line["pane"] == pane


def test_reads_terminal_says_yes_unless_it_can_tell_no(ws):
    """A pty, as an interactive session has, is a terminal; a pipe and
    /dev/null are not. Where nothing can be read, the answer is yes, as it
    was before: no pid where there is no /proc, a process that is gone."""
    main, sub = os.openpty()
    try:
        for stdin, reads in ((sub, True), (subprocess.PIPE, False),
                             (subprocess.DEVNULL, False)):
            child = subprocess.Popen(["sleep", "30"], stdin=stdin)
            try:
                assert ws.reads_terminal(child.pid) is reads, stdin
            finally:
                child.kill()
                child.wait()
    finally:
        os.close(main)
        os.close(sub)
    assert ws.reads_terminal(0) is True
    assert ws.reads_terminal(child.pid) is True   # gone now


def test_the_hook_file_defines_every_name_it_uses(ws):
    """A name the copy left behind is a NameError on every event, and the
    hook may say nothing, so it would be caught, logged and never seen. Every
    global a function reads must be defined in the file or be a builtin."""
    text = ws.hook_source(SOURCE)
    table = symtable.symtable(text, "hook.py", "exec")
    defined = set(table.get_identifiers())
    missing = set()

    def walk(scope):
        for child in scope.get_children():
            if child.get_type() == "function":
                missing.update(name for name in child.get_globals()
                               if name not in defined and not hasattr(builtins, name))
            walk(child)

    walk(table)
    assert not missing


def test_the_hook_file_records_an_event_and_says_nothing(ws, tmp_path):
    """The same line `wostuast hook` writes: the payload, the pane, both pids
    and the stamp. And not a byte on stdout, for a permission dialog most of
    all: that is the hook's answer (topics/safety, the first bullet)."""
    path = written(ws, tmp_path)
    for name in ("PreToolUse", "PermissionRequest"):
        done = run_hook(path, tmp_path, {"session_id": "s1", "hook_event_name": name,
                                         "tool_name": "Bash",
                                         "tool_input": {"command": "rm -rf /"}})
        assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    lines = (tmp_path / "state" / "events.jsonl").read_text().splitlines()
    first = json.loads(lines[0])
    assert [json.loads(line)["hook_event_name"] for line in lines] == [
        "PreToolUse", "PermissionRequest"]
    assert first["pane"] == "%3" and first["shell_pid"] > 0
    assert "pid" in first and first["ts"] > 0


def test_the_hook_file_survives_what_breaks_it(ws, tmp_path):
    """Not JSON, and a state directory that cannot be made: exit 0, nothing
    printed, as the program's own hook does."""
    path = written(ws, tmp_path)
    done = subprocess.run([str(path)], input="not json", capture_output=True,
                          text=True, timeout=30,
                          env={"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path),
                               "WOSTUAST_STATE": "/proc/no/such/place"})
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")


def test_the_hook_file_loads_little(ws, tmp_path):
    """What it imports is what every tool call waits for. The program's
    `test_the_hook_does_not_import_what_it_does_not_need` holds the same
    line for `wostuast hook`."""
    path = written(ws, tmp_path)
    done = subprocess.run(
        [os.environ.get("PYTHON", "python3"), "-X", "importtime", str(path)],
        input="{}", capture_output=True, text=True, timeout=30,
        env={"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path),
             "WOSTUAST_STATE": str(tmp_path / "state")})
    loaded = {line.rsplit("|", 1)[-1].strip() for line in done.stderr.splitlines()
              if line.startswith("import time:")}
    avoidable = {"argparse", "subprocess", "dataclasses", "ast", "inspect",
                 "http", "urllib.request", "socket", "shlex", "sqlite3"}
    assert loaded and not (loaded & avoidable), sorted(loaded & avoidable)


def test_install_writes_the_hook_file_and_points_every_hook_at_it(
        ws, tmp_path, monkeypatch):
    target = tmp_path / "bin" / "wostuast"
    monkeypatch.setattr(ws, "install_path", lambda: target)
    assert ws.cmd_install(None) == 0
    hook = ws.hook_path()
    assert hook == tmp_path / "share" / "wostuast" / "hook.py"
    assert hook.read_text() == ws.hook_source(target.read_text())
    assert os.access(hook, os.X_OK)
    settings = json.loads(ws.settings_path().read_text())
    commands = {entry["command"] for event in ws.HOOK_EVENTS
                for group in settings["hooks"][event] for entry in group["hooks"]}
    assert commands == {ws.hook_command(hook)}
    assert ws.install_behind() == ""


def test_an_old_install_is_moved_to_the_hook_file_in_place(ws):
    """An install from before the file ran the whole program on every event.
    Its entry becomes the file where it stands, so the order of the user's
    hooks stays; their own entry is not touched."""
    old = "/home/m/.local/bin/wostuast hook"
    new = "/home/m/.local/share/wostuast/hook.py"
    settings = {"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": "my-stop.sh"},
        {"type": "command", "command": old}]}]}}
    ws.add_hooks(settings, new)
    assert [entry["command"] for entry in settings["hooks"]["Stop"][0]["hooks"]] == [
        "my-stop.sh", new]
    assert len(settings["hooks"]["Stop"]) == 1
    assert ws.add_hooks(settings, new) == []


def test_the_hook_file_is_ours_and_nothing_like_it_is(ws):
    assert ws.is_ours("/home/m/.local/share/wostuast/hook.py", "hook")
    assert ws.is_ours("'/home/a b/.local/share/wostuast/hook.py'", "hook")
    for command in ["/x/hook.py", "/x/wostuast/hook.py --other", "hook.py"]:
        assert not ws.is_ours(command, "hook")
    assert not ws.is_ours("/home/m/.local/share/wostuast/hook.py", "status")


def test_uninstall_removes_the_hook_file(ws, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ws, "install_path", lambda: tmp_path / "bin" / "wostuast")
    ws.cmd_install(None)
    assert ws.hook_path().exists()
    assert ws.cmd_uninstall(None) == 0
    assert not ws.hook_path().exists()
    assert f"removed {ws.hook_path()}" in capsys.readouterr().out


def test_doctor_says_when_the_hook_file_is_not_this_versions(
        ws, tmp_path, monkeypatch, capsys):
    """An install of an older copy, or a hand that edited it: the hooks run
    it, so what this version records is not recorded."""
    monkeypatch.setattr(ws, "install_path", lambda: tmp_path / "bin" / "wostuast")
    ws.cmd_install(None)
    capsys.readouterr()
    ws.hook_path().write_text(ws.hook_path().read_text() + "\n# edited\n")
    behind = ws.install_behind()
    assert str(ws.hook_path()) in behind and "install" in behind
    assert ws.cmd_doctor(None) == 1
    assert behind in capsys.readouterr().out


def test_doctor_says_when_the_hook_file_is_gone(ws, tmp_path, monkeypatch, capsys):
    """The settings still name it, so every hook looks registered, and every
    event is lost. Before the file the command was the program, and
    "installed at" caught it."""
    monkeypatch.setattr(ws, "install_path", lambda: tmp_path / "bin" / "wostuast")
    ws.cmd_install(None)
    capsys.readouterr()
    ws.hook_path().unlink()
    behind = ws.install_behind()
    assert str(ws.hook_path()) in behind and "install" in behind
    assert ws.cmd_doctor(None) == 1
    assert behind in capsys.readouterr().out


# --- the status file (#286) ------------------------------------------------------


def written_status(ws, tmp_path):
    path = tmp_path / "share" / "wostuast" / "status.py"
    ws.write_program(path, ws.status_source(SOURCE))
    return path


def run_status(path, home, payload, *args):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
           "WOSTUAST_STATE": str(home / "state")}
    return subprocess.run([str(path), *args], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=30)


def test_the_status_file_defines_every_name_it_uses(ws):
    """The hook file's test, for the status file: a name left behind is a
    status line that prints nothing, and says why only in the log."""
    text = ws.status_source(SOURCE)
    table = symtable.symtable(text, "status.py", "exec")
    defined = set(table.get_identifiers())
    missing = set()

    def walk(scope):
        for child in scope.get_children():
            # A class body too: `StatusArgs` reads `then_in` and `sys`
            # there, and a class scope has no `get_globals`.
            read = (child.get_globals() if child.get_type() == "function" else
                    {one.get_name() for one in child.get_symbols()
                     if one.is_referenced() and not one.is_assigned()})
            missing.update(name for name in read
                           if name not in defined and not hasattr(builtins, name))
            walk(child)

    walk(table)
    assert not missing


def test_the_status_file_keeps_the_session_and_prints_its_line(ws, tmp_path):
    """What `wostuast status` does: the name and the context kept for the
    page, one line printed -- or the user's own line, run with the same
    payload, after `--then`. `Status` came out of the first build with no
    `@dataclass` above it, and took no arguments."""
    path = written_status(ws, tmp_path)
    payload = {"session_id": "s9", "session_name": "warm", "cwd": "/tmp",
               "model": {"display_name": "Opus 5"},
               "context_window": {"used_percentage": 41}}
    done = run_status(path, tmp_path, payload)
    assert (done.returncode, done.stderr) == (0, "")
    assert "warm" in done.stdout and "41%" in done.stdout
    kept = json.loads((tmp_path / "state" / "status" / "s9.json").read_text())
    assert kept["name"] == "warm" and kept["context_pct"] == 41.0
    done = run_status(path, tmp_path, payload, "--then", "cat")
    assert json.loads(done.stdout)["session_id"] == "s9"


def test_the_status_file_loads_little(ws, tmp_path):
    """It runs on every redraw. `dataclasses` it needs, and `ast` comes with
    it through `inspect`; the rest of what the program imports it must not."""
    path = written_status(ws, tmp_path)
    done = subprocess.run(
        [os.environ.get("PYTHON", "python3"), "-X", "importtime", str(path)],
        input="{}", capture_output=True, text=True, timeout=30,
        env={"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path),
             "WOSTUAST_STATE": str(tmp_path / "state")})
    loaded = {line.rsplit("|", 1)[-1].strip() for line in done.stderr.splitlines()
              if line.startswith("import time:")}
    avoidable = {"argparse", "http", "urllib.request", "socket", "shlex",
                 "sqlite3", "subprocess"}
    assert loaded and not (loaded & avoidable), sorted(loaded & avoidable)


def test_install_points_the_status_line_at_the_status_file(
        ws, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ws, "install_path", lambda: tmp_path / "bin" / "wostuast")
    assert ws.cmd_install(None) == 0
    status = ws.status_program_path()
    assert status == tmp_path / "share" / "wostuast" / "status.py"
    assert os.access(status, os.X_OK)
    settings = json.loads(ws.settings_path().read_text())
    assert settings["statusLine"]["command"] == ws.status_command(status)
    assert ws.install_behind() == ""
    status.write_text(status.read_text() + "\n# edited\n")
    behind = ws.install_behind()
    assert str(status) in behind and "install" in behind
    status.unlink()
    behind = ws.install_behind()
    assert str(status) in behind and "install" in behind
    assert ws.cmd_install(None) == 0
    assert status.exists()
    capsys.readouterr()
    assert ws.cmd_uninstall(None) == 0
    assert "statusLine" not in json.loads(ws.settings_path().read_text())
    assert not status.exists()
    assert f"removed {status}" in capsys.readouterr().out
