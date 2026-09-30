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


@pytest.mark.parametrize("text, sent", [
    ("use foo();", "use foo()\\;"),
    (";", "\\;"),
    (";;", ";\\;"),
    ("path\\;", "path\\\\;"),
    ("a;b", "a;b"),
])
def test_a_semicolon_at_the_end_is_sent_as_tmux_reads_it(ws, asked, text, sent):
    """tmux reads an argument that ends in `;` as the end of a command, even
    after `-l --`: "use foo();" arrived as "use foo()". The last `;` goes as
    `\\;`, which tmux turns back into one `;`. On a real tmux, where there
    is one, `test_what_arrives_is_what_was_written` holds the same."""
    assert ws.tmux_send("%7", text, runner=asked) is True
    assert asked.seen[0] == ["tmux", "send-keys", "-t", "%7", "-l", "--", sent]


def test_a_lone_surrogate_never_reaches_a_terminal(ws, asked):
    """JSON can carry one, and `subprocess` hands it to tmux with
    `surrogateescape`: U+DCC2 U+DC9B left as the bytes c2 9b, which is CSI.
    A high one made the encode fail, and the whole send with it."""
    text = "x" + chr(0xDC9B) + "31m" + chr(0xDCC2) + chr(0xDC9B) + "y" + chr(0xD800)
    assert ws.tmux_send("%7", text, runner=asked) is True
    assert asked.seen[0][-1] == "x31my"
    assert ws.tmux_send("%7", chr(0xDC9B) + chr(0xD800), runner=asked) is False


@pytest.fixture
def real_pane(ws, tmp_path, monkeypatch):
    """A pane of a tmux server of this test's own, running a raw `cat` into a
    file, so a test reads the bytes that arrived. Skipped with no tmux."""
    import os
    import shutil
    import subprocess
    import time

    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")
    name = f"wostuast-test-{os.getpid()}-{time.monotonic_ns()}"
    out, ready = tmp_path / "arrived", tmp_path / "ready"

    def tmux(*args):
        return subprocess.run(["tmux", "-L", name, *args], capture_output=True,
                               text=True, timeout=10, check=True).stdout.strip()

    # Raw, or the terminal turns the Enter into a newline on its way to
    # `cat`; and a key sent before `stty` has run is read the cooked way.
    tmux("-f", "/dev/null", "new-session", "-d",
         f"stty raw -echo && : > '{ready}' && exec cat > '{out}'")
    try:
        # `TMUX` names the server a plain `tmux` talks to, so `tmux_send`
        # reaches this one and never the reader's own.
        monkeypatch.setenv("TMUX", tmux("display-message", "-p",
                                         "#{socket_path}") + ",0,0")
        pane = tmux("display-message", "-p", "#{pane_id}")
        deadline = time.monotonic() + 10
        while not ready.exists():
            assert time.monotonic() < deadline, "the pane never went raw"
            time.sleep(0.02)

        def arrived(count):
            deadline = time.monotonic() + 10
            while out.read_bytes().count(b"\r") < count:
                assert time.monotonic() < deadline, out.read_bytes()
                time.sleep(0.02)
            return out.read_bytes()

        yield pane, arrived
    finally:
        subprocess.run(["tmux", "-L", name, "kill-server"], capture_output=True,
                       timeout=10)


def test_what_arrives_is_what_was_written(ws, real_pane):
    """Measured on tmux 3.4 with the bytes read out of a pane: every text
    that ends in `;` lost it, "path\\;" arrived as "path;", and a pair of lone
    surrogates arrived as c2 9b, CSI. What arrives is what was written, or
    what was written without its controls, and nothing else."""
    pane, arrived = real_pane
    texts = ["use foo();", ";", ";;", "a ;", "path\\;", "a\\\\;", "a;b"]
    for text in texts:
        assert ws.tmux_send(pane, text)
    bad = "x" + chr(0xDC9B) + "31m" + chr(0xDCC2) + chr(0xDC9B) + "y"
    assert ws.tmux_send(pane, bad)
    wanted = [one.encode() for one in texts] + [b"x31my"]
    assert arrived(len(wanted)).split(b"\r")[:-1] == wanted


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


def beside(many=False, n=3, preview="if (ok) {\n    parse();\n}\n"):
    """A question with a preview on its first option only, as an agent
    writes one: the rest of the options have none."""
    asked = one(many, n)
    asked["options"][0]["preview"] = preview
    return asked


def test_a_question_beside_a_preview_takes_enter_after_its_digit(ws):
    """Measured against Claude Code 2.1.281 in tmux, with a fake API asking.
    One option with a preview puts the whole question beside a preview box,
    and there a digit only moves the cursor: `3` alone left the reader's
    answer under the cursor and nothing sent. Enter answers and moves on.
    A multiple-choice question is never drawn that way, preview or not."""
    assert ws.ask_keys(ask_of(ws, beside()), [[3]]) == (["3", "Enter"], "")
    assert ws.ask_keys(ask_of(ws, beside(), one(False)), [[2], [3]]) == (
        ["2", "Enter", "3", "Enter"], "")
    assert ws.ask_keys(ask_of(ws, one(False), beside()), [[1], [3]]) == (
        ["1", "3", "Enter", "Enter"], "")
    assert ws.ask_keys(ask_of(ws, beside(many=True)), [[1, 3]]) == (
        ["1", "3", "Tab", "Enter"], "")
    # So its preview is never looked at, and cannot make it unanswerable.
    assert ask_of(ws, beside(many=True, preview="\x1b[1m"))["answerable"]


@_pytest.mark.parametrize("preview, keys", [
    ("", ["2"]),                     # blank: Claude Code draws no box
    (" \n\t ", ["2"]),
    ("x" * 2001, ["2", "Enter"]),    # too long to read, still a box
    ("\U000e0001" * 1001, ["2", "Enter"]),  # 2002 long, as JavaScript counts
    (" " * 1999 + "\u200b", []),       # 2000 is not over it
    ("x\r\ny", ["2", "Enter"]),
    ("\x1b[31mred\x1b[0m", []),      # an escape: its width is a guess
    ("\u200b", []),                  # nothing visible, or is there
    ("\ufffd", []),                  # Claude Code drops this one
    (["not", "text"], []),
])
def test_a_preview_is_read_as_claude_code_reads_it(ws, preview, keys):
    """Claude Code's own test for a preview it can show (`pU`): something
    left once escapes, blanks and U+FFFD are taken out. Where that hangs on
    the width of a character nobody can see, the keys would be a guess, so
    the question is left to the terminal."""
    ask = ask_of(ws, beside(preview=preview))
    assert ws.ask_keys(ask, [[2]])[0] == keys
    assert ask["answerable"] is bool(keys)


def test_a_preview_goes_to_the_page_as_the_dialog_draws_it(ws):
    """The page shows the box Claude Code draws, so it is sent what that box
    holds: the text whole -- `clip` folds every line of a code box into one
    -- or, past `PREVIEW_UNREAD`, only that it was withheld. A preview the
    dialog does not draw is not sent: blank, or on a multiple-choice
    question, which never stands beside a box."""
    code = "if (ok) {\n    parse();\n}\n"
    asked = one(False, n=4)
    for choice, preview in zip(asked["options"], [code, "x" * 2001, " \n "]):
        choice["preview"] = preview
    got = [(o["preview"], o["withheld"])
           for o in ask_of(ws, asked)["questions"][0]["options"]]
    assert got == [(code, False), ("", True), ("", False), ("", False)]
    many = ask_of(ws, beside(many=True, preview=code))["questions"][0]
    assert [o["preview"] for o in many["options"]] == ["", "", ""]


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
