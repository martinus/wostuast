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


# --- peek -------------------------------------------------------------------


def test_peek_asks_for_the_pane_with_its_colours(ws, asked):
    ws.tmux_peek("%7", runner=asked)
    assert asked.seen == [["tmux", "capture-pane", "-p", "-e", "-t", "%7"]]


def test_peek_without_a_pane_asks_nothing(ws, asked):
    assert ws.tmux_peek("", runner=asked) is None
    assert asked.seen == []


# --- the converter ----------------------------------------------------------


def runs_of(ws, text):
    return [(one.text, one.fg, one.bold) for one in ws.ansi_runs(text)]


def test_a_recorded_capture_keeps_its_colours(ws):
    """The real thing, out of a real tmux."""
    runs = ws.ansi_runs((FIXTURES / "peek.txt").read_text())
    said = {one.text.strip(): one for one in runs}
    assert said["✓ 14 passed"].fg == "var(--ansi-2)"
    assert said["✓ 14 passed"].bold is True
    assert said["0.31s"].fg == "var(--ansi-3)"
    assert said["FAILED"].fg == "var(--ansi-1)"
    assert said["256-colour"].fg == "#ff8700"      # xterm 208
    assert said["truecolor"].fg == "#6495ed"       # 100, 149, 237
    assert said["underlined bold"].under is True
    assert said["underlined bold"].bold is True
    # Every character of the capture survives, colours aside.
    assert "".join(one.text for one in runs).count("14 passed") == 1


def test_the_first_sixteen_colours_are_named_not_fixed(ws):
    """The page gives them values, so they follow the theme."""
    assert ws.ansi_runs("\x1b[31mred")[0].fg == "var(--ansi-1)"
    assert ws.ansi_runs("\x1b[91mbright")[0].fg == "var(--ansi-9)"
    assert ws.ansi_runs("\x1b[44mon blue")[0].bg == "var(--ansi-4)"
    assert ws.ansi_runs("\x1b[104mon bright")[0].bg == "var(--ansi-12)"


def test_reset_puts_everything_back(ws):
    runs = ws.ansi_runs("\x1b[1;4;31mloud\x1b[0mquiet")
    assert (runs[0].bold, runs[0].under, runs[0].fg) == (True, True, "var(--ansi-1)")
    assert (runs[1].bold, runs[1].under, runs[1].fg) == (False, False, "")


def test_one_thing_at_a_time_can_be_turned_off(ws):
    runs = ws.ansi_runs("\x1b[1;31mboth\x1b[22mjust red\x1b[39mplain")
    assert (runs[0].bold, runs[0].fg) == (True, "var(--ansi-1)")
    assert (runs[1].bold, runs[1].fg) == (False, "var(--ansi-1)")
    assert runs[2].fg == ""


def test_a_sequence_that_is_not_a_colour_is_dropped_not_shown(ws):
    """A cursor movement printed as text is worse than one lost."""
    for noise in ("\x1b[2J", "\x1b[H", "\x1b[?25l", "\x1b]0;a title\x07", "\x1bM"):
        assert runs_of(ws, noise + "after") == [("after", "", False)], noise


def test_a_code_we_do_not_know_does_not_lose_its_neighbours(ws):
    """Terminals skip what they do not know and read the rest."""
    assert ws.ansi_runs("\x1b[53;31mred anyway")[0].fg == "var(--ansi-1)"


def test_text_that_looks_the_same_is_one_run(ws):
    runs = ws.ansi_runs("\x1b[31mone\x1b[31m two\x1b[31m three")
    assert len(runs) == 1
    assert runs[0].text == "one two three"


def test_control_characters_never_reach_the_page(ws):
    runs = ws.ansi_runs("before\x00\x07\x08after\r\nnext\tcolumn")
    assert runs[0].text == "beforeafter\nnext\tcolumn"


def test_a_capture_that_changes_colour_for_ever_is_cut(ws):
    """A pane nobody is reading must not become a node per character."""
    loud = "".join(f"\x1b[3{n % 8}m{n}" for n in range(3000))
    assert len(ws.ansi_runs(loud, limit=50)) == 50


def test_nothing_captured_is_no_runs(ws):
    assert ws.ansi_runs("") == []


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
        "\x1b[200~first line\nsecond line\x1b[201~"]
    assert asked.seen[1] == ["tmux", "send-keys", "-t", "%7", "Enter"]


def test_a_carriage_return_counts_as_a_line_too(ws, asked):
    ws.tmux_send("%7", "first\r\nsecond", runner=asked)
    assert asked.seen[0][-1].startswith("\x1b[200~")
