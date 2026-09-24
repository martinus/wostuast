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


# --- interrupt ----------------------------------------------------------------


def test_interrupt_sends_escape_and_never_ctrl_c(ws, asked):
    """Claude Code's own docs: Escape stops the current response or tool call
    and "Claude keeps the work done so far"; Ctrl-C interrupts a running
    operation, but "if nothing is running, the first press clears the prompt
    input and a second press exits Claude Code".

    A turn can end between deciding to stop a session and the key landing, so
    Ctrl-C on an automatic limit is a race whose losing side is a session that
    quit. Escape on an idle prompt does nothing."""
    assert ws.tmux_interrupt("%7", runner=asked) is True
    assert asked.seen == [["tmux", "send-keys", "-t", "%7", "Escape"]]
    flat = " ".join(asked.seen[0])
    assert "C-c" not in flat and "\x03" not in flat


def test_interrupt_without_a_pane_runs_nothing(ws, asked):
    assert ws.tmux_interrupt("", runner=asked) is False
    assert asked.seen == []


def test_interrupt_says_when_tmux_did_not_take_it(ws):
    assert ws.tmux_interrupt("%7", runner=lambda args, **rest: None) is False


# --- answering a question in the agent's own dialog --------------------------

import pytest as _pytest  # noqa: E402


def ask_of(ws, *questions):
    return ws.read_ask({"tool_name": "AskUserQuestion", "tool_use_id": "q",
                        "tool_input": {"questions": list(questions)}})


def one(many, n=3):
    return {"question": "Q?", "header": "H", "multiSelect": many,
            "options": [{"label": f"o{k}", "description": ""} for k in range(n)]}


def test_the_keys_that_answer_each_shape_of_question(ws):
    """Measured against Claude Code 2.1.281 in tmux, with a fake API asking:
    one single-choice question is answered by its digit and has no review;
    anything else ends on a review that takes Enter; a multiple-choice
    question takes a digit per option and Tab."""
    assert ws.ask_keys(ask_of(ws, one(False)), [[2]]) == (["2"], "")
    assert ws.ask_keys(ask_of(ws, one(True)), [[3, 1]]) == (
        ["1", "3", "Tab", "Enter"], "")
    assert ws.ask_keys(ask_of(ws, one(False), one(True), one(False)),
                       [[2], [2, 3], [1]]) == (
        ["2", "2", "3", "Tab", "1", "Enter"], "")


@_pytest.mark.parametrize("picks", [
    None, [], [[1], [1]], [[]], [["1"]], [[True]], [[0]], [[4]], [[1, 1]],
    [[1, 2]],                   # two answers to a single-choice question
    [[1.0]],
])
def test_picks_that_answer_nothing_are_refused(ws, picks):
    keys, why = ws.ask_keys(ask_of(ws, one(False)), picks)
    assert keys == [] and why, picks


def test_a_question_that_could_not_be_kept_whole_is_not_answered(ws):
    """Keys go by position: a question or an option left out of what the
    page was sent would move every key after it onto the wrong answer."""
    too_many = one(False, n=ws.ASK_MAX + 1)
    ask = ask_of(ws, too_many)
    assert ask["answerable"] is False
    assert ws.ask_keys(ask, [[1]])[0] == []
    broken = ask_of(ws, one(False), "not a question")
    assert broken["answerable"] is False
    assert ask_of(ws, one(False), one(True))["answerable"] is True


def test_keys_go_one_command_each_and_only_the_answer_keys(ws, monkeypatch):
    """`24` in one read is not two ticks, measured: nothing was ticked and
    the dialog moved on without them. And nothing but a digit, Tab or Enter
    is ever pressed through here."""
    monkeypatch.setattr(ws, "KEY_GAP", 0)
    seen = []

    def runner(args, **rest):
        seen.append(list(args))
        return ""

    assert ws.tmux_keys("%3", ["2", "4", "Tab", "Enter"], runner=runner) == 4
    assert seen == [["tmux", "send-keys", "-t", "%3", "-l", "--", "2"],
                    ["tmux", "send-keys", "-t", "%3", "-l", "--", "4"],
                    ["tmux", "send-keys", "-t", "%3", "Tab"],
                    ["tmux", "send-keys", "-t", "%3", "Enter"]]
    seen.clear()
    for bad in (["24"], ["C-c"], ["Escape"], ["-l"], ["2", "x"]):
        assert ws.tmux_keys("%3", bad, runner=runner) == 0
    assert seen == []


def test_a_key_tmux_refused_stops_the_rest(ws, monkeypatch):
    monkeypatch.setattr(ws, "KEY_GAP", 0)
    calls = []

    def runner(args, **rest):
        calls.append(args[-1])
        return None if len(calls) == 2 else ""

    assert ws.tmux_keys("%3", ["1", "2", "Tab", "Enter"], runner=runner) == 1
    assert calls == ["1", "2"]
