"""The three tmux verbs, and the converter that makes a capture readable.

tmux itself is not needed here: each verb is one function that takes a command
runner, so the tests pass a fake one and read what it was asked to run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def asked():
    """A runner that records, and answers as if every command worked."""
    seen = []

    def runner(args, **rest):
        seen.append(list(args))
        return ""

    runner.seen = seen
    return runner


@pytest.fixture
def broken():
    def runner(args, **rest):
        return None
    return runner


# --- jump -------------------------------------------------------------------


def test_jump_picks_the_window_then_the_pane(ws, asked):
    assert ws.tmux_jump("%7", runner=asked) is True
    assert asked.seen == [["tmux", "select-window", "-t", "%7"],
                          ["tmux", "select-pane", "-t", "%7"]]


def test_jump_without_a_pane_runs_nothing(ws, asked):
    assert ws.tmux_jump("", runner=asked) is False
    assert asked.seen == []


def test_jump_says_so_when_tmux_refuses(ws, broken):
    assert ws.tmux_jump("%7", runner=broken) is False


def test_jump_runs_the_users_own_focus_command(ws, asked):
    """Raising the terminal window is the window manager's job, and every desk
    does it differently, so the command is the user's to set."""
    ws.tmux_jump("%7", runner=asked, focus="wmctrl -a kitty")
    assert asked.seen[-1] == ["sh", "-c", "wmctrl -a kitty"]


def test_jump_runs_no_focus_command_when_there_is_none(ws, asked, monkeypatch):
    monkeypatch.delenv("WOSTUAST_FOCUS", raising=False)
    ws.tmux_jump("%7", runner=asked)
    assert all(one[0] == "tmux" for one in asked.seen)


def test_the_focus_command_comes_from_the_environment(ws, asked, monkeypatch):
    monkeypatch.setenv("WOSTUAST_FOCUS", "raise-my-terminal")
    ws.tmux_jump("%7", runner=asked)
    assert asked.seen[-1] == ["sh", "-c", "raise-my-terminal"]


# --- send -------------------------------------------------------------------


def test_send_types_the_text_and_then_enter(ws, asked):
    assert ws.tmux_send("%7", "run the tests", runner=asked) is True
    assert asked.seen == [
        ["tmux", "send-keys", "-t", "%7", "-l", "--", "run the tests"],
        ["tmux", "send-keys", "-t", "%7", "Enter"],
    ]


def test_send_escapes_nothing_itself(ws, asked):
    """`-l` sends the text literally, so an escape of our own would arrive as
    characters. `--` is what stops tmux reading a leading dash as an option."""
    nasty = '-n $(rm -rf /) "quoted" \\backslash\\ ;semicolon'
    ws.tmux_send("%7", nasty, runner=asked)
    assert asked.seen[0] == ["tmux", "send-keys", "-t", "%7", "-l", "--", nasty]


def test_send_refuses_empty_text(ws, asked):
    """A bare Enter into an agent's prompt is a keystroke nobody asked for."""
    for nothing in ("", "   ", "\n", "\t "):
        assert ws.tmux_send("%7", nothing, runner=asked) is False
    assert asked.seen == []


def test_send_without_a_pane_runs_nothing(ws, asked):
    assert ws.tmux_send("", "hello", runner=asked) is False
    assert asked.seen == []


def test_send_does_not_press_enter_when_the_text_did_not_arrive(ws):
    """Enter on its own would run whatever was already on the line."""
    seen = []

    def half(args, **rest):
        seen.append(list(args))
        return None if "-l" in args else ""

    assert ws.tmux_send("%7", "hello", runner=half) is False
    assert len(seen) == 1


# --- send -------------------------------------------------------------------


def test_one_line_is_sent_exactly_as_it_always_was(ws, asked):
    """A program that does not understand bracketed paste never sees it."""
    ws.tmux_send("%7", "run the tests", runner=asked)
    assert asked.seen[0] == ["tmux", "send-keys", "-t", "%7", "-l", "--",
                             "run the tests"]


def test_more_than_one_line_arrives_as_a_paste(ws, asked):
    """A newline typed into a terminal is Enter. Measured against a real
    shell: `echo one\\necho two` ran the first line and left the second on the
    prompt. The bracketed paste markers say this arrived as a paste."""
    ws.tmux_send("%7", "first line\nsecond line", runner=asked)
    assert asked.seen[0] == [
        "tmux", "send-keys", "-t", "%7", "-l", "--",
        ws.PASTE_START + "first line\nsecond line" + ws.PASTE_END]
    assert asked.seen[1] == ["tmux", "send-keys", "-t", "%7", "Enter"]


def test_a_carriage_return_counts_as_a_line_too(ws, asked):
    ws.tmux_send("%7", "first\r\nsecond", runner=asked)
    assert asked.seen[0][-1].startswith(ws.PASTE_START)


def test_a_control_character_cannot_end_the_paste_early(ws):
    """A paste ends at ESC [ 2 0 1 ~. Text carrying those bytes would close it
    and leave the rest arriving as keystrokes, with any newline among them as
    Enter. The review is composed from lines an agent wrote, and an escape
    byte is invisible in a preview, so this is taken out at the verb.
    """
    said = []
    ws.tmux_send("%1", "look here\n\x1b[201~rm -rf ~\nand here",
                 runner=lambda cmd: said.append(cmd) or "")
    body = said[0][-1]
    assert "\x1b[201~rm" not in body
    assert body.startswith(ws.PASTE_START) and body.endswith(ws.PASTE_END)
    assert body.count(ws.PASTE_END) == 1
    assert "rm -rf ~" in body           # still shown, just no longer a paste end


def test_a_line_of_only_control_characters_is_not_sent(ws):
    said = []
    assert ws.tmux_send("%1", "\x1b\x07\x00",
                        runner=lambda cmd: said.append(cmd) or "") is False
    assert said == []
