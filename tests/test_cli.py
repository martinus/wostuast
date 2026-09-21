"""The commands: ls, doctor, and the small pieces they print."""

from __future__ import annotations

import json
import argparse
import time

import conftest



def test_tool_summaries(ws):
    cwd = "/w/dir"
    assert ws.tool_summary("Read", {"file_path": "/w/dir/src/table.cpp"}, cwd) == "Read src/table.cpp"
    assert ws.tool_summary("Write", {"file_path": "/w/dir/PLAN.md"}, cwd) == "Write PLAN.md"
    assert ws.tool_summary("Edit", {"file_path": "/other/x.py"}, cwd) == "Edit /other/x.py"
    assert ws.tool_summary("Bash", {"command": "pytest -q"}, cwd) == "Bash pytest -q"
    assert ws.tool_summary("Grep", {"pattern": "resolve_branch"}, cwd) == "Grep resolve_branch"
    assert ws.tool_summary("Glob", {"pattern": "**/*.py"}, cwd) == "Glob **/*.py"
    assert ws.tool_summary("Task", {"description": "look around"}, cwd) == "Task look around"
    assert ws.tool_summary("WebFetch", {"url": "https://x"}, cwd).startswith("WebFetch {")
    assert ws.tool_summary("Mystery", {}, cwd) == "Mystery"
    assert ws.tool_summary("", None, cwd) == "tool"


def test_a_long_command_is_cut(ws):
    summary = ws.tool_summary("Bash", {"command": "x" * 200}, "")
    assert len(summary) == len("Bash ") + 60
    assert summary.endswith("…")


def test_clip_collapses_whitespace(ws):
    assert ws.clip("a\n  b\tc", 10) == "a b c"


def test_ago_reads_in_words(ws):
    assert ws.ago(5) == "5s"
    assert ws.ago(90) == "1min"
    assert ws.ago(-5) == "0s"
    # Two units once the first one is coarse: "2d" covers two days to just
    # short of three, which is not an answer to "when did this last do
    # something".
    assert ws.ago(7200) == "2h"
    assert ws.ago(7200 + 15 * 60) == "2h 15min"
    assert ws.ago(2 * 86400) == "2d"
    assert ws.ago(2 * 86400 + 6 * 3600) == "2d 6h"
    # The second unit is left off when it is nought, so "2d" still means
    # exactly two days rather than two days and something.
    assert ws.ago(2 * 86400 + 59) == "2d"


def test_the_changes_column(ws):
    assert ws.changes_column(ws.GitFacts(branch="main")) == "✓"
    assert ws.changes_column(ws.GitFacts(branch="main", ahead=2, dirty=True,
                                         touched_files=5)) == "↑2 ●5"
    assert ws.changes_column(ws.GitFacts(branch="main", behind=1)) == "↓1 ✓"
    assert ws.changes_column(ws.GitFacts()) == ""


def test_ls_without_sessions_explains_itself(ws, capsys):
    assert ws.cmd_ls(None) == 0
    out = capsys.readouterr().out
    assert "no sessions yet" in out
    assert "doctor" in out


def test_ls_prints_one_row_per_session(ws, written_events, capsys):
    assert ws.cmd_ls(None) == 0
    out = capsys.readouterr().out
    assert "STATE" in out
    assert "oans/warmhare" not in out  # no git repository in the test environment
    assert "warmhare" in out
    assert "calmpuma" in out
    assert "%7" in out
    assert "1 ready · 1 ended" in out


def test_ls_shows_the_name_from_the_status_file(ws, written_events, recorded_status, capsys):
    ws.write_status(recorded_status["session_id"],
                    ws.status_from_payload(recorded_status, now=1.0))
    ws.cmd_ls(None)
    assert "warmhare" in capsys.readouterr().out


def test_doctor_reports_a_missing_install(ws, capsys):
    code = ws.cmd_doctor(None)
    out = capsys.readouterr().out
    assert "wostuast doctor" in out
    assert "hooks missing" in out
    assert code == 1


def test_doctor_is_happy_after_install(ws, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ws, "install_path", lambda: tmp_path / "bin" / "wostuast")
    ws.cmd_install(None)
    capsys.readouterr()
    code = ws.cmd_doctor(None)
    out = capsys.readouterr().out
    assert "all good." in out
    assert code == 0


def test_the_table_pads_every_column_but_the_last(ws):
    rows = [("", ["a", "bbb", "x"]), ("", ["cccc", "d", "y"])]
    assert ws.table(rows, color=False) == "a     bbb  x\ncccc  d    y"


def test_the_table_colours_a_row_by_its_own_state(ws):
    rows = [("", ["head"]), ("needs_you", ["row"])]
    lines = ws.table(rows, color=True).splitlines()
    assert lines[0] == "head"
    assert lines[1].startswith("\033[") and "row" in lines[1]


def test_no_color_when_asked(ws):
    assert ws.paint("x", "needs_you", color=False) == "x"
    assert ws.paint("x", "needs_you", color=True).startswith("\033[")


def test_serve_says_so_when_the_port_is_taken(ws, capsys):
    """It must not crash with a traceback when another wostuast is running."""
    import socket

    held = socket.socket()
    held.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    held.bind((ws.BIND_HOST, 0))
    held.listen(1)
    port = held.getsockname()[1]
    try:
        args = argparse.Namespace(port=port, open=False)
        assert ws.cmd_serve(args) == 1
        assert "cannot listen" in capsys.readouterr().err
    finally:
        held.close()


def test_hook_and_status_skip_the_argument_parser(ws, monkeypatch):
    """They run on every tool call and every redraw, so they must stay cheap."""
    built = False

    def fail_if_built():
        nonlocal built
        built = True
        raise AssertionError("build_parser must not run for hook or status")

    monkeypatch.setattr(ws, "build_parser", fail_if_built)
    monkeypatch.setattr(ws, "cmd_hook", lambda args: 0)
    monkeypatch.setattr(ws, "cmd_status", lambda args: 0)
    monkeypatch.setattr(ws, "FAST_PATH", {"hook": ws.cmd_hook, "status": ws.cmd_status})
    assert ws.main(["hook"]) == 0
    assert ws.main(["status"]) == 0
    assert built is False


def test_every_other_command_still_goes_through_the_parser(ws, capsys):
    assert ws.main([]) == 0
    assert "usage: wostuast" in capsys.readouterr().out


def test_a_notebook_edit_shows_its_path(ws):
    assert ws.tool_summary(
        "NotebookEdit", {"notebook_path": "/w/dir/study.ipynb"}, "/w/dir"
    ) == "NotebookEdit study.ipynb"


def test_the_store_keeps_the_whole_prompt(ws):
    """The sidebar clips for its column. The page wants the full text."""
    store = ws.Store()
    long_prompt = "please " + "x" * 300
    store.apply({"session_id": "s", "hook_event_name": "UserPromptSubmit",
                 "prompt": long_prompt, "ts": 1.0})
    session = store.sessions["s"]
    assert session.last_prompt == long_prompt
    assert long_prompt in session.last_event
    assert len(ws.clip(session.last_event, 60)) == 60


def test_ls_does_not_pass_an_escape_sequence_to_the_terminal(ws, capsys):
    """`session.reason` is a `Notification` message or a summary of a tool
    input: text an agent wrote, which a hostile file or a prompt injection can
    steer. It went to stdout unfiltered — one set the terminal's title and
    turned the rest of the output red, and the column widths went wrong
    besides, because `len` counts the escape bytes.

    The page uses `textContent` for exactly this text and `tmux_send` strips
    it. `ls` is the same data on the same terminal.
    """
    nasty = "\x1b]0;pwned\x07\x1b[31mtook over the terminal"
    ws.append_event(conftest.event("SessionStart", cwd="/w/one", pane="%7",
                                   pid=1, ts=time.time()))
    ws.append_event(conftest.event("Notification", cwd="/w/one",
                                   message=nasty, ts=time.time()))
    assert ws.cmd_ls(None) == 0
    out = capsys.readouterr().out
    assert "took over the terminal" in out
    assert "\x1b" not in out
    assert "\x07" not in out


# --- the reader's own autolinks ----------------------------------------------


def write_links(ws, text):
    """The state directory is made on demand everywhere else, so a test that
    writes straight into it has to make it too."""
    ws.links_path().parent.mkdir(parents=True, exist_ok=True)
    ws.links_path().write_text(text, encoding="utf-8")


def test_only_a_usable_autolink_reaches_the_page(ws, tmp_path):
    """A broken entry is dropped here and named by `doctor`, rather than
    becoming a link that quietly does nothing."""
    write_links(ws, json.dumps([
        {"match": r"(OA|QSP)-(\d+)", "url": "https://tickets/browse/$1-$2"},
        {"match": "OA-", "url": "javascript:alert(1)"},       # not http
        {"match": "OA-(", "url": "https://tickets/"},          # will not compile
        {"match": "", "url": "https://tickets/"},              # nothing to match
        {"url": "https://tickets/"},                           # no match at all
        "not an object",
        {"match": "x" * 300, "url": "https://tickets/"},       # far too long
        {"match": "(a+)+b", "url": "https://tickets/"},         # backtracks
    ]))
    assert ws.read_links() == [
        {"match": r"(OA|QSP)-(\d+)", "url": "https://tickets/browse/$1-$2"}]


def test_no_links_file_is_no_links(ws):
    assert ws.read_links() == []


def test_a_links_file_that_is_not_a_list_is_no_links(ws):
    write_links(ws, '{"match": "OA-", "url": "https://t/"}')
    assert ws.read_links() == []


def test_a_quantifier_inside_a_quantified_group_is_refused(ws):
    """`(a+)+b` is the shape that backtracks catastrophically, and nothing on
    the page can time a regular expression out. Spotting it is a heuristic
    and says so; it is the one shape worth spotting."""
    assert ws.risky_pattern("(a+)+") is True
    assert ws.risky_pattern("(x*)*y") is True
    assert ws.risky_pattern(r"([a-z]+\d*)+") is True
    assert ws.risky_pattern(r"(OA|QSP)-(\d+)") is False
    assert ws.risky_pattern(r"\bTICKET-\d+\b") is False
    assert ws.risky_pattern("(abc)+") is False


def test_doctor_names_a_broken_autolink(ws, capsys):
    write_links(ws, json.dumps([
        {"match": r"OK-(\d+)", "url": "https://tickets/$1"},
        {"match": "BAD-(", "url": "https://tickets/"},
    ]))
    ws.cmd_doctor(argparse.Namespace())
    said = capsys.readouterr().out
    assert "link 2" in said and "not a regular expression" in said
    # And a broken link is not a reason for the whole check to fail.
    assert "note" in said


def test_a_links_file_that_will_not_parse_says_what_is_wrong(ws):
    """The one people write. `\\d` is not a JSON escape, so the file never
    parses -- and the page showed nothing, which is also what a machine with
    no links file looks like. Silence was the bug, not the typo."""
    write_links(ws, '[{"match": "(OA|QSP)-(\\d+)", "url": "https://t/$1-$2"}]')
    usable, trouble = ws.load_links()
    assert usable == []
    assert len(trouble) == 1
    assert "not valid JSON" in trouble[0]
    # And it says the thing that fixes it, because the error alone
    # ("Invalid \\escape") does not tell anybody to double a backslash.
    assert "doubled" in trouble[0]


def test_an_entry_that_cannot_be_used_is_trouble_and_the_rest_still_are_links(ws):
    """Dropping a broken entry in silence is the same bug one entry down."""
    write_links(ws, json.dumps([
        {"match": r"OK-(\d+)", "url": "https://tickets/$1"},
        {"match": "BAD-(", "url": "https://tickets/"},
    ]))
    usable, trouble = ws.load_links()
    assert usable == [{"match": r"OK-(\d+)", "url": "https://tickets/$1"}]
    assert len(trouble) == 1 and "link 2" in trouble[0]


def test_no_links_file_is_not_trouble(ws):
    """Most people want no autolinks, and a machine that never had the file
    must not be told off for it."""
    assert ws.load_links() == ([], [])


def test_serve_says_what_is_wrong_with_the_links_file(ws, capsys, monkeypatch):
    """The page cannot make you look at it and `doctor` is something you had
    no reason to run, so the restart has to say it."""
    write_links(ws, "not json at all")

    class Fake:
        def serve_forever(self):
            raise KeyboardInterrupt

        def shutdown(self):
            pass

        def server_close(self):
            pass

    monkeypatch.setattr(ws, "make_server", lambda daemon, port: Fake())
    monkeypatch.setattr(ws.Daemon, "run", lambda self: None)
    assert ws.cmd_serve(argparse.Namespace(port=0, open=False)) == 0
    assert "links:" in capsys.readouterr().err


def test_serve_says_nothing_about_a_links_file_it_can_use(ws, capsys,
                                                          monkeypatch):
    """A line every start would be noise, and noise is not read."""
    write_links(ws, json.dumps([{"match": r"OK-(\d+)", "url": "https://t/$1"}]))

    class Fake:
        def serve_forever(self):
            raise KeyboardInterrupt

        def shutdown(self):
            pass

        def server_close(self):
            pass

    monkeypatch.setattr(ws, "make_server", lambda daemon, port: Fake())
    monkeypatch.setattr(ws.Daemon, "run", lambda self: None)
    ws.cmd_serve(argparse.Namespace(port=0, open=False))
    assert "links:" not in capsys.readouterr().err


def test_doctor_names_a_links_file_that_will_not_parse(ws, capsys):
    write_links(ws, "not json at all")
    ws.cmd_doctor(argparse.Namespace())
    said = capsys.readouterr().out
    assert "not valid JSON" in said
    assert "note" in said               # still not a reason for the check to fail


def test_serve_leaves_an_example_when_there_is_no_links_file(ws):
    """Finding out how to write one should be opening it, not reading a
    README. JSON has no comments, so the example has to be a working entry."""
    assert ws.write_example_links() is True
    assert ws.links_path().exists()
    # It is a file `doctor` is happy with and the page can use.
    assert ws.read_links() == ws.EXAMPLE_LINKS
    for one in ws.EXAMPLE_LINKS:
        assert ws.link_trouble(one) == "", one


def test_the_example_links_nothing(ws):
    """Nobody's work has a ticket called `EXAMPLE-1`, so the example matches
    nothing until it is edited. An example that made real links would be a
    program doing something nobody asked for."""
    import re
    for one in ws.EXAMPLE_LINKS:
        pattern = re.compile(one["match"])
        for text in ("Fixed OA-73219 and QSP-52811.",
                     "see ticket 4242, and PROJ-7",
                     "an example of what to do"):
            assert pattern.search(text) is None, (one, text)


def test_an_existing_links_file_is_never_written_over(ws):
    """A file somebody wrote and got wrong is still theirs; `doctor` says
    what is wrong with it. Drop the `exists` check and this one is lost."""
    ws.links_path().parent.mkdir(parents=True, exist_ok=True)
    for held in ('[{"match": "OA-(\\\\d+)", "url": "https://mine/$1"}]',
                 "not json at all",
                 ""):
        ws.links_path().write_text(held, encoding="utf-8")
        assert ws.write_example_links() is False
        assert ws.links_path().read_text(encoding="utf-8") == held


def test_the_example_is_private_at_creation(ws):
    """Everything in the state directory is, and this one is written by the
    same helper for the same reason."""
    ws.write_example_links()
    assert oct(ws.links_path().stat().st_mode)[-3:] == "600"
    assert oct(ws.links_path().parent.stat().st_mode)[-3:] == "700"


def test_a_state_directory_that_cannot_be_written_does_not_stop_serve(ws,
                                                                     monkeypatch):
    """It is a convenience. `serve` starts with it or without it."""
    def refuse(*args, **kwargs):
        raise OSError("read-only file system")

    monkeypatch.setattr(ws, "write_atomic", refuse)
    assert ws.write_example_links() is False
