"""`wostuast wait`: return when a session reaches a state (#356)."""

from __future__ import annotations

import json
import time

import pytest

from conftest import event


@pytest.fixture
def live(ws, monkeypatch):
    """The module with every agent alive, and a way to write events now."""
    monkeypatch.setattr(ws, "pid_alive", lambda pid: True)
    monkeypatch.setattr(ws, "WAIT_STEP", 0.01)

    def write(name, sid="s1", **extra):
        ws.append_event(event(name, sid=sid, ts=time.time(), **extra))

    return write


def wait(ws, *argv):
    return ws.cmd_wait(ws.build_parser().parse_args(["wait", *argv]))


def test_a_session_already_there_returns_at_once(ws, live, capsys):
    live("SessionStart", cwd="/w/repo/alpha")
    live("Stop")
    assert wait(ws, "s1", "--until", "done") == 0
    assert capsys.readouterr().out == "s1 alpha: ready\n"


def test_it_waits_for_the_state_to_come(ws, live, monkeypatch, capsys):
    """The log is followed: what is appended while it waits is read."""
    live("SessionStart")
    live("UserPromptSubmit", prompt="go")
    steps = []

    def step(seconds):
        steps.append(seconds)
        if len(steps) == 2:
            live("Stop")
        # A wait that never reads the Stop fails here rather than for ever.
        assert len(steps) < 20, "the Stop written while it waited was never read"

    monkeypatch.setattr(ws.time, "sleep", step)
    assert wait(ws, "s1", "--until", "ready") == 0
    assert len(steps) == 2
    assert capsys.readouterr().out.endswith(": ready\n")


def test_the_words_ls_prints_and_over_are_states(ws):
    assert ws.wait_states("needs you") == {"needs_you"}
    assert ws.wait_states("needs-you") == {"needs_you"}
    assert ws.wait_states("ready") == {"done"}
    assert ws.wait_states("killed") == {"dead"}
    assert ws.wait_states("over") == {"ended", "dead"}
    with pytest.raises(Exception):
        ws.wait_states("finished")


def test_a_session_that_ended_otherwise_is_exit_1(ws, live, capsys):
    live("SessionStart")
    live("SessionEnd", reason="exit")
    assert wait(ws, "s1", "--until", "needs_you") == 1
    assert "without becoming needs_you" in capsys.readouterr().err
    assert wait(ws, "s1", "--until", "over") == 0


def test_a_session_is_named_by_its_id_its_start_or_its_name(ws, live, capsys):
    live("SessionStart", sid="abc12345", cwd="/w/repo/alpha")
    live("Stop", sid="abc12345", cwd="/w/repo/alpha")
    live("SessionStart", sid="def67890", cwd="/w/repo/beta")
    live("Stop", sid="def67890", cwd="/w/repo/beta")
    assert wait(ws, "abc", "--until", "done") == 0
    assert capsys.readouterr().out.startswith("abc12345 ")
    assert wait(ws, "beta", "--until", "done") == 0
    assert capsys.readouterr().out.startswith("def67890 ")


def test_a_name_two_sessions_fit_is_refused_and_both_are_named(ws, live, capsys):
    live("SessionStart", sid="abc12345", cwd="/w/repo/same")
    live("SessionStart", sid="abc99999", cwd="/w/repo/same")
    assert wait(ws, "abc", "--until", "done") == 1
    err = capsys.readouterr().err
    assert "fits 2 sessions" in err and "abc12345" in err and "abc99999" in err
    assert wait(ws, "nobody", "--until", "done") == 1
    assert "no session is called 'nobody'" in capsys.readouterr().err


def test_without_a_session_any_one_will_do(ws, live, capsys):
    live("SessionStart", sid="a1")
    live("SessionStart", sid="b2")
    live("Notification", sid="b2", notification_type="permission_prompt",
         message="Claude needs your permission to use Bash")
    assert wait(ws, "--until", "needs_you") == 0
    assert capsys.readouterr().out.startswith("b2 ")


def test_the_timeout_is_exit_124(ws, live, capsys):
    live("SessionStart")
    live("UserPromptSubmit", prompt="go")
    started = time.monotonic()
    assert wait(ws, "s1", "--until", "done", "--timeout", "0.2") == 124
    assert time.monotonic() - started < 5
    assert capsys.readouterr().err == "timed out\n"


def test_a_clear_is_followed_into_the_session_it_became(ws, live, capsys):
    """`/clear` ends the session and goes on in a new one in the same pane,
    a tenth of a second apart; the wait goes with it, as the page does."""
    live("SessionStart", sid="old")
    live("UserPromptSubmit", sid="old", prompt="go")
    live("SessionEnd", sid="old", reason="clear")
    live("SessionStart", sid="new", source="clear")
    live("Stop", sid="new")
    assert wait(ws, "old", "--until", "done") == 0
    assert capsys.readouterr().out.startswith("new ")


def test_json_is_the_shape_ls_prints(ws, live, capsys):
    live("SessionStart")
    live("Stop")
    assert wait(ws, "s1", "--until", "done", "--json") == 0
    found = json.loads(capsys.readouterr().out)
    assert found["version"] == 1
    assert [one["id"] for one in found["sessions"]] == ["s1"]
    assert found["sessions"][0]["state"] == "done"
