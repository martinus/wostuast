"""The three tmux verbs, and the converter that makes a capture readable.

tmux itself is not needed here: each verb is one function that takes a command
runner, so the tests pass a fake one and read what it was asked to run.
"""

from __future__ import annotations

from pathlib import Path

import os
import pytest

import conftest

FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: What tmux puts around a paste, for a program that asked for them.
PASTE_START = "\x1b[200~"
PASTE_END = "\x1b[201~"


@pytest.fixture
def asked():
    """A runner that records, and answers as if every command worked."""
    seen = []

    def runner(args, **rest):
        seen.append(conftest.said(args, rest))
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


def test_send_leaves_copy_mode_pastes_the_text_and_then_a_return(ws, asked):
    """`send-keys -l` took the text as an argument, and tmux 3.4 refuses a
    command over 16,341 bytes. `load-buffer -` reads it on stdin instead, and
    `-r` keeps a newline a newline: without it tmux pastes Enter (#328). The
    Enter is a pasted return too, which reaches only the target pane."""
    assert ws.tmux_send("%7", "run the tests", runner=asked) is True
    cancel, load, paste, load_enter, paste_enter = asked.seen
    assert cancel == ["tmux", "send-keys", "-X", "-t", "%7", "cancel"]
    name, enter = load[3], load_enter[3]
    assert load == ["tmux", "load-buffer", "-b", name, "-", "run the tests"]
    assert paste == ["tmux", "paste-buffer", "-p", "-d", "-r", "-b", name,
                     "-t", "%7"]
    assert load_enter == ["tmux", "load-buffer", "-b", enter, "-", "\r"]
    assert paste_enter == ["tmux", "paste-buffer", "-d", "-r", "-b", enter,
                           "-t", "%7"]


def test_each_send_has_a_buffer_of_its_own(ws, asked):
    """Buffers belong to the whole tmux server: another client, or a second
    send, must never paste ours, so the name is ours and never used twice."""
    import os

    ws.tmux_send("%7", "one", runner=asked)
    ws.tmux_send("%8", "two", runner=asked)
    names = [one[3] for one in asked.seen if one[1] == "load-buffer"]
    assert len(set(names)) == 4, names
    assert all(name.startswith(f"wostuast-{os.getpid()}-") for name in names)


def test_send_escapes_nothing_itself(ws, asked):
    """stdin is not a command line: nothing in it is an option, a quote or the
    end of a command, so an escape of our own would arrive as characters."""
    nasty = '-n $(rm -rf /) "quoted" \\backslash\\ ;semicolon;'
    ws.tmux_send("%7", nasty, runner=asked)
    assert conftest.typed(asked.seen) == [nasty]


def test_send_refuses_empty_text(ws, asked):
    """A bare Enter into an agent's prompt is a keystroke nobody asked for."""
    for nothing in ("", "   ", "\n", "\t "):
        assert ws.tmux_send("%7", nothing, runner=asked) is False
    assert asked.seen == []


def test_send_without_a_pane_runs_nothing(ws, asked):
    assert ws.tmux_send("", "hello", runner=asked) is False
    assert asked.seen == []


@pytest.mark.parametrize("fails, ran", [
    (1, ["send-keys", "load-buffer", "delete-buffer"]),
    (2, ["send-keys", "load-buffer", "paste-buffer", "delete-buffer"]),
    (4, ["send-keys", "load-buffer", "paste-buffer", "load-buffer",
         "paste-buffer", "delete-buffer"]),
])
def test_a_paste_that_fails_presses_nothing_and_leaves_no_buffer(ws, fails,
                                                                 ran):
    """Enter on its own would run whatever was already on the line. And tmux
    3.4 keeps a buffer whose paste failed, `-d` or not -- measured, with the
    pane gone -- so it is deleted; a load that ran out of time may have
    filled it too. The text's load, its paste, and the Enter's paste fail
    here in turn, and the cancel fails every time, as it does for a pane in
    no mode: that does not stop a send."""
    seen = []

    def runner(args, **rest):
        seen.append(list(args))
        return None if len(seen) - 1 == fails or "cancel" in args else ""

    assert ws.tmux_send("%7", "hello", runner=runner) is False
    assert [one[1] for one in seen] == ran
    failed = seen[-2]
    name = failed[failed.index("-b") + 1]
    assert seen[-1] == ["tmux", "delete-buffer", "-b", name]


def test_the_text_goes_as_it_is_and_tmux_brackets_the_paste(ws, asked):
    """A newline typed into a terminal is Enter: measured against a real
    shell, `echo one\\necho two` ran the first line. So the paste is `-p`,
    which brackets it for a program that asked, and the text goes as it is,
    one line or many -- our own markers were put on many lines only, and
    100 KB on one line then arrived in Claude Code as pieces with the Enter
    inside the last one."""
    for text in ("run the tests", "first line\nsecond line"):
        asked.seen.clear()
        ws.tmux_send("%7", text, runner=asked)
        assert conftest.typed(asked.seen) == [text]
        text_paste, enter_paste = [one for one in asked.seen
                                   if one[1] == "paste-buffer"]
        assert "-p" in text_paste and "-r" in text_paste
        assert "-p" not in enter_paste, "a return inside a paste is no Enter"


def test_a_control_character_cannot_end_the_paste_early(ws, asked):
    """A paste ends at ESC [ 2 0 1 ~. Text carrying those bytes would close it
    and leave the rest arriving as keystrokes, with any newline among them as
    Enter. The review is composed from lines an agent wrote, and an escape
    byte is invisible in a preview, so this is taken out at the verb.
    `test_what_arrives_is_what_was_written` holds it in a real pane.
    """
    ws.tmux_send("%1", "look here\n\x1b[201~rm -rf ~\nand here", runner=asked)
    body = conftest.typed(asked.seen)[0]
    assert "\x1b" not in body
    assert "rm -rf ~" in body           # still shown, just no longer a paste end


def test_a_line_of_only_control_characters_is_not_sent(ws, asked):
    assert ws.tmux_send("%1", "\x1b\x07\x00", runner=asked) is False
    assert asked.seen == []


@pytest.mark.parametrize("text", ["use foo();", ";", ";;", "path\\;", "a;b"])
def test_a_semicolon_at_the_end_needs_no_escape(ws, asked, text):
    """`send-keys` read an argument that ends in `;` as the end of a command,
    even after `-l --`: "use foo();" arrived as "use foo()", and the last `;`
    had to go as `\\;`. stdin is not a command line, so it goes as it is. On a
    real tmux, where there is one, `test_what_arrives_is_what_was_written`
    holds the same."""
    assert ws.tmux_send("%7", text, runner=asked) is True
    assert conftest.typed(asked.seen) == [text]


def test_a_lone_surrogate_never_reaches_a_terminal(ws, asked):
    """JSON can carry one, and `subprocess` handed an argument to tmux with
    `surrogateescape`: U+DCC2 U+DC9B left as the bytes c2 9b, which is CSI.
    A high one made the encode fail, and the whole send with it."""
    text = "x" + chr(0xDC9B) + "31m" + chr(0xDCC2) + chr(0xDC9B) + "y" + chr(0xD800)
    assert ws.tmux_send("%7", text, runner=asked) is True
    assert conftest.typed(asked.seen) == ["x31my"]
    assert ws.tmux_send("%7", chr(0xDC9B) + chr(0xD800), runner=asked) is False


def a_pane(tmp_path, monkeypatch, asks):
    """A pane of a tmux server of this test's own, running a raw `cat` into a
    file, so a test reads the bytes that arrived. `asks` is whether the
    program asked for bracketed paste, as Claude Code does. Skipped with no
    tmux."""
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
    # `ESC [ ? 2004 h` is how a program asks for the paste markers.
    ask = "printf '\\033[?2004h' && " if asks else ""
    tmux("-f", "/dev/null", "new-session", "-d",
         f"stty raw -echo && {ask}: > '{ready}' && exec cat > '{out}'")
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


@pytest.fixture
def real_pane(ws, tmp_path, monkeypatch):
    """A raw pane whose program asked for the paste markers."""
    yield from a_pane(tmp_path, monkeypatch, asks=True)


@pytest.fixture
def plain_pane(ws, tmp_path, monkeypatch):
    """A raw pane whose program did not ask for the paste markers."""
    yield from a_pane(tmp_path, monkeypatch, asks=False)


def pasted(text):
    """What a pane that asked for the markers reads for one send."""
    return (PASTE_START + text + PASTE_END).encode()


def test_what_arrives_is_what_was_written(ws, real_pane):
    """Measured on tmux 3.4 with the bytes read out of a pane: through
    `send-keys`, every text that ends in `;` lost it, "path\\;" arrived as
    "path;", and a pair of lone surrogates arrived as c2 9b, CSI. What
    arrives is what was written, or what was written without its controls,
    as one paste, and nothing else -- an end marker in the text included."""
    pane, arrived = real_pane
    texts = ["use foo();", ";", ";;", "a ;", "path\\;", "a\\\\;", "a;b",
             "two\nlines"]
    for text in texts:
        assert ws.tmux_send(pane, text)
    bad = "x" + chr(0xDC9B) + "31m" + chr(0xDCC2) + chr(0xDC9B) + "y"
    assert ws.tmux_send(pane, bad)
    assert ws.tmux_send(pane, "look\x1b[201~here")
    wanted = [pasted(one) for one in texts] + [pasted("x31my"),
                                               pasted("look[201~here")]
    assert arrived(len(wanted)).split(b"\r")[:-1] == wanted


def test_a_long_text_arrives_whole_as_one_paste(ws, real_pane):
    """`send-keys -l` stopped at 16,341 bytes on tmux 3.4, and a long log
    could not be sent (#328). Through the buffer, a text of `SEND_MAX`
    bytes -- tabs, `ä`, a `;` at the end -- arrives every byte, between the
    paste markers, and then the one Enter."""
    pane, arrived = real_pane
    line = "\tlog line ä;\n"
    text = (line * (ws.SEND_MAX // len(line.encode())))[:-1]
    assert 16341 < len(text.encode()) <= ws.SEND_MAX
    assert ws.tmux_send(pane, text)
    assert arrived(1) == pasted(text) + b"\r"


def test_a_program_that_did_not_ask_sees_no_markers(ws, plain_pane):
    """It cannot read them, so they would arrive as characters. A newline
    still arrives as a newline, not as the carriage return that is Enter:
    that is `-r`, and without it tmux pastes one -- measured."""
    pane, arrived = plain_pane
    assert ws.tmux_send(pane, "one line")
    assert ws.tmux_send(pane, "two\nlines")
    assert arrived(2) == b"one line\rtwo\nlines\r"


def test_a_pane_in_copy_mode_still_gets_one_paste(ws, real_pane):
    """A pane scrolled back with the mouse wheel is in copy mode, and there a
    paste reached the program without the markers and the Enter was eaten
    by the mode: a real bash ran the first line of two, and the page said
    done. The send leaves the mode first."""
    pane, arrived = real_pane
    assert ws.run(["tmux", "copy-mode", "-t", pane]) is not None
    assert ws.tmux_send(pane, "two\nlines")
    assert arrived(1) == pasted("two\nlines") + b"\r"


def a_synchronized_pane_beside(ws, pane, tmp_path):
    """A second raw pane in the window of `pane`, with `synchronize-panes`
    on: the file it writes what it reads to."""
    import time

    other, ready = tmp_path / "other", tmp_path / "other-ready"
    assert ws.run(["tmux", "split-window", "-t", pane,
                   f"stty raw -echo && : > '{ready}' && exec cat > '{other}'"]
                  ) is not None
    deadline = time.monotonic() + 10
    while not ready.exists():
        assert time.monotonic() < deadline, "the other pane never went raw"
        time.sleep(0.02)
    assert ws.run(["tmux", "set-option", "-w", "-t", pane,
                   "synchronize-panes", "on"]) is not None
    return other


def test_synchronized_panes_get_no_enter_of_ours(ws, real_pane, tmp_path):
    """Under `synchronize-panes` a key goes to every pane of the window and a
    paste only to its target, so `send-keys Enter` after the paste gave the
    other panes a bare Enter, which runs whatever is on their prompt."""
    import time

    pane, arrived = real_pane
    other = a_synchronized_pane_beside(ws, pane, tmp_path)
    assert ws.tmux_send(pane, "only here")
    assert arrived(1) == pasted("only here") + b"\r"
    time.sleep(0.5)                     # proving nothing reached the other
    assert other.read_bytes() == b""


def test_synchronized_panes_get_no_answer_and_no_escape_of_ours(
        ws, real_pane, tmp_path, monkeypatch):
    """The same for the answer keys and the No's Escape (#331): `send-keys`
    pressed them in every pane of the window, and a digit and an Enter on
    another agent's prompt can answer or approve something there. They are
    pasted as their bytes, and reach the target alone, as `send-keys` sent
    them."""
    import time

    monkeypatch.setattr(ws, "KEY_GAP", 0)
    pane, arrived = real_pane
    other = a_synchronized_pane_beside(ws, pane, tmp_path)
    assert ws.tmux_interrupt(pane)
    assert ws.tmux_keys(pane, ["2", "Tab", "Enter"]) == 3
    assert arrived(1) == b"\x1b2\t\r"
    time.sleep(0.5)                     # proving nothing reached the other
    assert other.read_bytes() == b""


def test_no_buffer_is_left_behind(ws, real_pane):
    """tmux keeps a buffer whose paste failed, `-d` or not, and buffers
    belong to the whole server -- the reader's own paste key lists them.
    Measured with a pane that is gone."""
    pane, arrived = real_pane
    assert ws.tmux_send(pane, "kept")
    assert not ws.tmux_send("%999", "to a pane that is gone")
    arrived(1)
    assert ws.run(["tmux", "list-buffers", "-F", "#{buffer_name}"]) == ""


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
    assert conftest.pressed(asked.seen) == ["Escape"]
    flat = " ".join(" ".join(one) for one in asked.seen)
    assert "C-c" not in flat and "\x03" not in flat
    # Pasted, not pressed: a key goes to every synchronized pane (#331).
    # The one `send-keys` leaves copy mode, and presses nothing.
    assert [one for one in asked.seen if one[1] == "send-keys"] == [
        ["tmux", "send-keys", "-X", "-t", "%7", "cancel"]]
    # `-S`, or tmux 3.7 runs the paste through vis(3) and types `^[`.
    assert "-S" in [one for one in asked.seen if one[1] == "paste-buffer"][0]


def test_a_tmux_that_refuses_dash_s_still_gets_one_escape(ws):
    """tmux 3.4 says "unknown flag -S" and pastes nothing; the Escape then
    goes without it, which is exact there. One Escape, never two."""
    seen = []

    def runner(args, **rest):
        seen.append(conftest.said(args, rest))
        return None if args[1] == "paste-buffer" and "-S" in args else ""

    assert ws.tmux_interrupt("%7", runner=runner) is True
    tried = [one for one in seen if one[1] == "paste-buffer"]
    assert ["-S" in one for one in tried] == [True, False]
    assert [text for text, _ in conftest.pastes(seen)] == ["\x1b", "\x1b"]


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


def test_keys_go_one_paste_each_and_only_the_answer_keys(ws, asked, monkeypatch):
    """`24` in one read is not two ticks, measured: nothing was ticked and
    the dialog moved on without them. So one paste a key, unbracketed: a
    key as its bytes, and never `send-keys`, which under synchronize-panes
    pressed it in every pane of the window (#331). And nothing but a digit,
    Tab or Enter is ever pressed through here."""
    monkeypatch.setattr(ws, "KEY_GAP", 0)
    assert ws.tmux_keys("%3", ["2", "4", "Tab", "Enter"], runner=asked) == 4
    assert conftest.pastes(asked.seen) == [
        ("2", False), ("4", False), ("\t", False), ("\r", False)]
    assert [one for one in asked.seen if one[1] == "send-keys"] == [
        ["tmux", "send-keys", "-X", "-t", "%3", "cancel"]]
    asked.seen.clear()
    for bad in (["24"], ["C-c"], ["Escape"], ["-l"], ["2", "x"]):
        assert ws.tmux_keys("%3", bad, runner=asked) == 0
    assert asked.seen == []


def test_a_key_tmux_refused_stops_the_rest(ws, monkeypatch):
    monkeypatch.setattr(ws, "KEY_GAP", 0)
    seen = []

    def runner(args, **rest):
        seen.append(conftest.said(args, rest))
        pasted = [one for one in seen if one[1] == "paste-buffer"]
        return None if args[1] == "paste-buffer" and len(pasted) == 2 else ""

    assert ws.tmux_keys("%3", ["1", "2", "Tab", "Enter"], runner=runner) == 1
    assert [text for text, _ in conftest.pastes(seen)] == ["1", "2"]
    assert seen[-1][1] == "delete-buffer"


@pytest.fixture
def inside_tmux(monkeypatch):
    """The suite run from inside a tmux, as the reader runs it. Asked for
    before `ws`, so `ws` finds it set."""
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1234,0")


def test_no_test_reaches_the_tmux_it_runs_under(inside_tmux, ws, tmp_path):
    """A rename types `/rename` into its session's pane (#351), and a page
    test that renamed a session in `%1` typed it into the reader's own pane
    when the suite ran inside tmux. `ws` points `TMUX` at a socket in the
    test's own folder, where no server runs."""
    assert os.environ["TMUX"].startswith(str(tmp_path))
    assert not ws.tmux_send("%1", "/rename x")
