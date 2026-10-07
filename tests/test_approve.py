"""Yes to a permission dialog from the page: through the dialog's own hook,
never through keys.

A dialog has no id, and keys land on whichever dialog is up when they
arrive. The hook of a `PermissionRequest` is called for one dialog, and
Claude Code takes its allow for that dialog only (measured on 2.1.292: the
allow closes the terminal's dialog and the call runs; an answer in the
terminal first stops the hook). So the hook waits for the reader's Yes,
bound to a nonce it wrote into its own line of the log, and says allow
only when the daemon wrote that Yes. Every Yes is the reader's own click.
"""

from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import sys
import threading
import time

import pytest

import conftest
from conftest import ROOT, STAND_IN, event
from test_serve import post

ASK = "0123456789abcdef"


def until(check, seconds=10.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def asking(ws, served, monkeypatch):
    """A session at a permission dialog whose hook waits for a Yes: the real
    `wait_for_yes`, in a thread. A `flock` taken through another open file
    holds against the daemon's look as another process's would. tmux is a
    recorder, which must hear nothing."""
    daemon, base = served
    seen = []
    monkeypatch.setattr(ws, "run", lambda args, **rest: seen.append(list(args)) or "")
    monkeypatch.setattr(ws, "APPROVE_WAIT", 20)
    now = time.time()
    for one in (event("SessionStart", pane="%7", pid=1, ts=now - 10),
                event("PreToolUse", tool_name="Bash", tool_use_id="toolu_p1",
                      tool_input={"command": "make"}, pane="%7", ts=now - 5),
                event("PermissionRequest", tool_name="Bash", ask_id=ASK,
                      tool_input={"command": "make"}, pane="%7", ts=now - 4.9)):
        ws.append_event(one)
    took = []
    hook = threading.Thread(target=lambda: took.append(ws.wait_for_yes(ASK)), daemon=True)
    hook.start()
    assert until(lambda: ws.hook_waits(ASK)), "the hook never took its lock"
    daemon.store.refresh()
    key = daemon.store.sessions["s1"].permission["key"]
    return daemon, base, seen, key, hook, took


def test_a_yes_goes_to_the_dialogs_own_hook_and_never_to_the_pane(ws, asking):
    daemon, base, seen, key, hook, took = asking
    assert ws.row(daemon.store.sessions["s1"])["approvable"] is True
    status, body = post(base + "/api/session/s1/approve", {"key": key},
                        token=daemon.token)
    assert status == 200 and body["done"], body
    hook.join(5)
    assert took == [ASK]
    assert seen == [], "a Yes pressed keys"
    assert not list(ws.approvals_dir().iterdir()), "the Yes was left lying there"
    daemon.store.refresh()
    session = daemon.store.sessions["s1"]
    assert (session.state, session.last_event) == ("working", "allowed from the page")


def test_a_yes_for_another_dialog_or_without_the_token_writes_nothing(ws, asking):
    daemon, base, seen, key, hook, took = asking
    status, body = post(base + "/api/session/s1/approve", {"key": "1.000000"},
                        token=daemon.token)
    assert status == 409 and "no longer waiting" in body["error"]
    status, _ = post(base + "/api/session/s1/approve", {"key": key})
    assert status == 403
    assert not (ws.approvals_dir() / f"{ASK}.yes").exists()
    assert hook.is_alive() and took == []


def test_no_yes_while_a_no_is_on_its_way(ws, asking):
    """One answer to a dialog at a time."""
    daemon, base, seen, key, hook, took = asking
    daemon.declining.add("s1")
    status, body = post(base + "/api/session/s1/approve", {"key": key},
                        token=daemon.token)
    assert status == 409 and "already on its way" in body["error"]
    assert hook.is_alive() and took == []


def test_no_yes_once_the_hook_has_stopped(ws, served):
    """The terminal answered first, and Claude Code stopped the hook: its
    file is there, and nobody holds it. Nothing is written, the page is told
    to answer in the terminal, and the file left behind goes."""
    daemon, base = served
    now = time.time()
    for one in (event("SessionStart", pane="%7", pid=1, ts=now - 10),
                event("PermissionRequest", tool_name="Bash", ask_id=ASK,
                      tool_input={"command": "make"}, pane="%7", ts=now - 4.9)):
        ws.append_event(one)
    left = ws.approvals_dir() / f"{ASK}.wait"
    ws.private_dir(left.parent)
    left.write_text("")
    daemon.store.refresh()
    session = daemon.store.sessions["s1"]
    assert ws.row(session)["approvable"] is False
    assert not left.exists()
    status, body = post(base + "/api/session/s1/approve",
                        {"key": session.permission["key"]}, token=daemon.token)
    assert status == 409 and "cannot be answered Yes from here" in body["error"], body
    assert not (ws.approvals_dir() / f"{ASK}.yes").exists()


SUGGESTED = json.loads((conftest.FIXTURES / "permission_suggestions.json").read_text())


def test_the_choices_are_claude_codes_own_suggestions(ws):
    """Measured on 2.1.292 (`permission_suggestions.json`): each suggestion
    is a "Yes, and ..." of its own, in the CLI's words where they are plain,
    and nothing that asks, denies, removes, or turns every prompt off."""
    def offered(suggestions):
        shown = ws.read_permission(event("PermissionRequest", tool_name="Bash", ask_id=ASK,
                                         permission_suggestions=suggestions), {}, "", 1.0)
        return [(one["at"], one["label"]) for one in shown["always"]]

    assert offered(SUGGESTED["npm test -- --watch=false"]) == [
        (0, "don't ask again for npm test * in this project")]
    assert offered(SUGGESTED["WebFetch https://example.com/doc"]) == [
        (0, "don't ask again for example.com in this project")]
    assert offered(SUGGESTED["Write notes.md"]) == [(0, "accept edits for this session")]
    assert offered(SUGGESTED["rm -rf build"]) == [
        (0, "always allow access to /w/repo/dir for this session"),
        (1, "accept edits for this session")]
    assert offered([
        {"type": "addRules", "behavior": "deny", "destination": "localSettings",
         "rules": [{"toolName": "Bash", "ruleContent": "npm test *"}]},
        {"type": "removeRules", "behavior": "allow", "destination": "localSettings",
         "rules": [{"toolName": "Bash"}]},
        {"type": "setMode", "mode": "bypassPermissions", "destination": "session"},
        "nonsense"]) == []
    # No hook waits to carry one: no choice.
    shown = ws.read_permission(event("PermissionRequest", tool_name="Bash",
                                     permission_suggestions=SUGGESTED["Write notes.md"]),
                               {}, "", 1.0)
    assert shown["always"] == []


@pytest.fixture
def asking_always(ws, served, monkeypatch):
    """`asking`, with a suggestion to keep."""
    daemon, base = served
    monkeypatch.setattr(ws, "APPROVE_WAIT", 20)
    ws.append_event(event("SessionStart", pane="%7", pid=1, ts=time.time() - 10))
    ws.append_event(event("PermissionRequest", tool_name="Bash", ask_id=ASK, pane="%7",
                          tool_input={"command": "npm test -- --watch=false"},
                          permission_suggestions=SUGGESTED["npm test -- --watch=false"],
                          ts=time.time() - 4.9))
    took = []
    hook = threading.Thread(target=lambda: took.append(ws.wait_for_yes(ASK)), daemon=True)
    hook.start()
    assert until(lambda: ws.hook_waits(ASK))
    daemon.store.refresh()
    return daemon, base, daemon.store.sessions["s1"].permission["key"], hook, took


def test_yes_and_dont_ask_again_names_the_choice_by_its_place(ws, asking_always):
    """The page sends which choice, never a rule: the hook takes the rule
    from its own payload (`allow_for`)."""
    daemon, base, key, hook, took = asking_always
    status, body = post(base + "/api/session/s1/approve", {"key": key, "always": 3},
                        token=daemon.token)
    assert status == 400 and "no such choice" in body["error"]
    status, body = post(base + "/api/session/s1/approve",
                        {"key": key, "always": "npm *"}, token=daemon.token)
    assert status == 400
    assert hook.is_alive() and took == []
    status, body = post(base + "/api/session/s1/approve", {"key": key, "always": 0},
                        token=daemon.token)
    assert status == 200 and body["done"], body
    hook.join(5)
    assert took == [f"{ASK}:0"]
    daemon.store.refresh()
    assert daemon.store.sessions["s1"].last_event == \
        "allowed from the page, and don't ask again for npm test * in this project"


def test_a_nonce_of_another_shape_is_no_path(ws):
    """The daemon makes a path of it: nothing but the hook's shape is one."""
    shown = ws.read_permission(event("PermissionRequest", tool_name="Bash",
                                     ask_id="../../daemon"), {}, "", 1.0)
    assert shown["ask"] == ""
    assert not ws.hook_waits("../../daemon.lock")


# --- the hook file itself -----------------------------------------------------


@pytest.fixture
def hook_at(ws, tmp_path):
    """The hook file this checkout makes, run as Claude Code runs it, with a
    daemon's lock held when `daemon` is set."""
    path = tmp_path / "share" / "wostuast" / "hook.py"
    ws.write_program(path, ws.hook_source((ROOT / "wostuast").read_text(encoding="utf-8")))
    folder = tmp_path / "stand-in"
    folder.mkdir()
    (folder / "claude").symlink_to(sys.executable)
    (folder / "stand_in.py").write_text(STAND_IN)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
           "WOSTUAST_STATE": os.environ["WOSTUAST_STATE"]}
    held = []

    def daemon() -> None:
        ws.private_dir(ws.state_dir())
        lock = os.open(ws.daemon_lock_path(), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        held.append(lock)

    def start(tool: str = "Bash", suggestions=None) -> subprocess.Popen:
        payload = json.dumps({"session_id": "s1", "hook_event_name": "PermissionRequest",
                              "tool_name": tool, "tool_input": {"command": "rm -rf build"},
                              "permission_suggestions": suggestions or []})
        child = subprocess.Popen([str(folder / "claude"), str(folder / "stand_in.py"),
                                  "terminal", str(path)], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, env=env, start_new_session=True)
        child.stdin.write(payload)
        child.stdin.close()
        return child

    yield daemon, start
    for lock in held:
        os.close(lock)


def finish(child: subprocess.Popen) -> tuple[int, str, str]:
    """Its exit and what it printed: stdin is closed already, so not
    `communicate`."""
    child.wait(timeout=10)
    return child.returncode, child.stdout.read(), child.stderr.read()


def logged_ask(ws) -> str:
    events = list(ws.read_events())
    return str(events[-1].get("ask_id") or "") if events else ""


def test_the_hook_says_allow_for_its_own_yes_and_nothing_else(ws, hook_at):
    """A Yes written for another nonce, or a file of its name that holds
    something else, is not its Yes: it waits on. Its own is, and allow is
    the one line it prints."""
    daemon, start = hook_at
    daemon()
    child = start()
    assert until(lambda: logged_ask(ws) and ws.hook_waits(logged_ask(ws))), \
        "the hook did not wait"
    ask = logged_ask(ws)
    folder = ws.approvals_dir()
    (folder / "fedcba9876543210.yes").write_text("fedcba9876543210")
    (folder / f"{ask}.yes").write_text("fedcba9876543210")
    time.sleep(0.6)
    assert child.poll() is None, "it took a Yes that was not its own"
    ws.write_atomic(folder / f"{ask}.yes", ask, private=True)
    code, out, err = finish(child)
    assert (code, out, err) == (0, ws.ALLOW, "")
    assert json.loads(out)["hookSpecificOutput"]["decision"] == {"behavior": "allow"}
    assert not (folder / f"{ask}.wait").exists()


def test_the_hook_keeps_the_suggestion_it_was_given_and_no_other(ws, hook_at):
    """`<ask>:0` is an allow with this dialog's own first suggestion, as
    Claude Code sent it -- what the CLI's option 2 does, measured. A choice
    the dialog was not offered -- a deny rule here -- gets no answer."""
    daemon, start = hook_at
    daemon()
    suggestions = SUGGESTED["npm test -- --watch=false"] + [
        {"type": "addRules", "behavior": "deny", "destination": "localSettings",
         "rules": [{"toolName": "Bash", "ruleContent": "*"}]}]
    for pick, expected in ((0, [suggestions[0]]), (1, None)):
        child = start(suggestions=suggestions)
        assert until(lambda: logged_ask(ws) and ws.hook_waits(logged_ask(ws)))
        ask = logged_ask(ws)
        ws.write_atomic(ws.approvals_dir() / f"{ask}.yes", f"{ask}:{pick}", private=True)
        code, out, err = finish(child)
        assert (code, err) == (0, "")
        if expected is None:
            assert out == "", "an allow for a choice nobody was offered"
        else:
            decision = json.loads(out)["hookSpecificOutput"]["decision"]
            assert decision == {"behavior": "allow", "updatedPermissions": expected}


@pytest.mark.parametrize("tool", ["AskUserQuestion", "ExitPlanMode"])
def test_a_question_or_a_plan_is_never_waited_on(ws, hook_at, tool):
    """A question has its own answers, and a plan's options are the
    terminal's: their hooks return at once, silent, with no nonce."""
    daemon, start = hook_at
    daemon()
    child = start(tool)
    assert finish(child) == (0, "", "")
    assert logged_ask(ws) == ""


def test_with_no_daemon_the_hook_does_not_wait(ws, hook_at):
    """Only a daemon can say Yes: with none, the hook returns at once."""
    daemon, start = hook_at
    child = start()
    assert finish(child) == (0, "", "")
    assert not ws.hook_waits(logged_ask(ws))


def test_a_hook_stopped_by_the_terminal_says_nothing(ws, hook_at):
    """The terminal answered: Claude Code stops the hook. It prints nothing,
    and the daemon sees no hook to say Yes to."""
    daemon, start = hook_at
    daemon()
    child = start()
    assert until(lambda: logged_ask(ws) and ws.hook_waits(logged_ask(ws)))
    os.killpg(child.pid, signal.SIGTERM)
    assert finish(child)[1] == ""
    assert not ws.hook_waits(logged_ask(ws))
