"""The commands: ls, doctor, and the small pieces they print."""

from __future__ import annotations

import json
import os
import argparse
import re
import threading
import time

import pytest

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


def test_doctor_says_and_a_start_mends_an_installed_copy_of_another_version(
        ws, tmp_path, monkeypatch, capsys):
    """The hooks and the status line run the installed copy, not the checkout
    `serve` ran from. A reader who pulled and restarted `serve` had a page
    that could show the session's spend and a status line, run by the copy
    from the day before, that never wrote it down -- and nothing said why.
    `doctor` says so; a start writes this version in and says that (#275)."""
    target = tmp_path / "bin" / "wostuast"
    monkeypatch.setattr(ws, "install_path", lambda: target)
    assert ws.install_behind() == ""            # nothing installed, nothing to say
    ws.cmd_install(None)
    assert ws.install_behind() == ""            # the same bytes
    capsys.readouterr()

    target.write_text(target.read_text() + "\n# an older one\n")
    behind = ws.install_behind()
    assert str(target) in behind and "install" in behind
    code = ws.cmd_doctor(None)
    out = capsys.readouterr().out
    assert behind in out
    assert code == 1

    # A start mends it on the way up, and says so where the reader is
    # looking. The server stops at once, the way ctrl-c stops it.
    assert start(ws, monkeypatch) == 0
    out = capsys.readouterr().out
    assert f"\u21bb updated {target}" in out
    assert "restart your Claude Code sessions" in out
    assert ws.install_behind() == ""


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


@pytest.mark.parametrize("port", ["-1", "65536", "70000", "many"])
def test_serve_refuses_a_port_that_is_not_one_without_a_traceback(
        ws, capsys, monkeypatch, port):
    """A port out of range reached `bind`, whose `OverflowError` is not an
    `OSError`, and `serve` died with a traceback (#235). argparse says what
    is wrong, and nothing is started."""
    started = []
    monkeypatch.setattr(ws, "make_server",
                        lambda daemon, port: started.append(port))
    with pytest.raises(SystemExit) as stopped:
        ws.main(["--port", port])
    assert stopped.value.code == 2
    err = capsys.readouterr().err
    assert "--port" in err and "Traceback" not in err
    assert started == []


def test_serve_says_the_port_it_got_when_asked_for_any(ws, capsys,
                                                      monkeypatch):
    """`--port 0` asks the system for a free port, and `serve` printed
    `http://127.0.0.1:0/` and `ssh -N -L 0:127.0.0.1:0`: two lines that
    lead nowhere (#235). It prints the port the socket has."""
    made = ws.make_server
    got = []

    def make(daemon, port):
        server = made(daemon, port)
        got.append(server.server_address[1])

        def stop():
            raise KeyboardInterrupt

        # `shutdown` waits for a loop that never ran: close the socket alone.
        server.serve_forever = stop
        server.shutdown = lambda: None
        return server

    monkeypatch.setattr(ws, "make_server", make)
    monkeypatch.setattr(ws.Daemon, "run", lambda self: None)
    assert ws.main(["--port", "0"]) == 0
    out = capsys.readouterr().out
    port = got[0]
    assert port != 0
    assert f"http://127.0.0.1:{port}/" in out
    assert f"-L {port}:127.0.0.1:{port} " in out
    assert ":0/" not in out and " 0:" not in out


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
    with pytest.raises(SystemExit) as done:
        ws.main(["--help"])
    assert done.value.code == 0
    assert "usage: wostuast" in capsys.readouterr().out


def test_no_command_is_the_start(ws, monkeypatch):
    """A bare `wostuast` checks, brings the hooks up to date and serves
    (#275); it printed the help before, and the help is `--help`."""
    started = []
    monkeypatch.setattr(ws, "cmd_serve", lambda args: started.append(
        (args.port, args.open)) or 0)
    assert ws.main([]) == 0
    assert ws.main(["--port", "0", "--open"]) == 0
    assert started == [(ws.DEFAULT_PORT, False), (0, True)]


def test_serve_is_gone_and_says_what_took_its_place(ws, capsys, monkeypatch):
    """argparse alone would say "invalid choice" and list every command but
    the answer. Nothing is started."""
    monkeypatch.setattr(ws, "cmd_serve", lambda args: pytest.fail("started"))
    assert ws.main(["serve", "--open"]) == 2
    said = capsys.readouterr().err
    assert "`wostuast serve` is now just `wostuast`" in said
    assert "--port and --open" in said


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


# --- the reader's settings, and the ticket links in them --------------------


def write_config(ws, text):
    """The configuration directory is made on demand everywhere else, so a
    test that writes straight into it has to make it too."""
    ws.config_path().parent.mkdir(parents=True, exist_ok=True)
    ws.config_path().write_text(text, encoding="utf-8")


def usable_links(ws):
    return [{"match": one["match"], "url": one["url"]}
            for one in ws.load_config()[1] if not one["trouble"]]


def test_only_a_usable_autolink_reaches_the_page(ws, tmp_path):
    """A broken entry is marked here and named by `doctor`, rather than
    becoming a link that quietly does nothing."""
    write_config(ws, json.dumps({"links": [
        {"match": r"(OA|QSP)-(\d+)", "url": "https://tickets/browse/$1-$2"},
        {"match": "OA-", "url": "javascript:alert(1)"},       # not http
        {"match": "OA-(", "url": "https://tickets/"},          # will not compile
        {"match": "", "url": "https://tickets/"},              # nothing to match
        {"url": "https://tickets/"},                           # no match at all
        "not an object",
        {"match": "x" * 300, "url": "https://tickets/"},       # far too long
        {"match": "(a+)+b", "url": "https://tickets/"},         # backtracks
        {"match": "OA-1", "url": "https://t/", "x": 1},        # not a link's key
    ]}))
    assert usable_links(ws) == [
        {"match": r"(OA|QSP)-(\d+)", "url": "https://tickets/browse/$1-$2"}]
    # Every other one is trouble, the one that is not even an object too.
    # One check for the file and for a POST: a key the POST refuses is
    # refused here too.
    assert len(ws.load_config()[2]) == 8


def test_the_menu_is_handed_a_bad_link_as_written(ws):
    """So it can show it in red and say why, rather than drop it from sight:
    a link that vanished from the menu was a link the reader had to type
    again without knowing what had been wrong with it."""
    write_config(ws, json.dumps({"links": [
        {"match": "BAD-(", "url": "https://tickets/$1"}]}))
    links = ws.config_payload()["links"]
    assert links[0]["match"] == "BAD-("
    assert "not a regular expression" in links[0]["trouble"]


def test_no_settings_file_is_no_settings_and_no_trouble(ws):
    """Most people never change a setting, and a machine that never had the
    file must not be told off for it."""
    assert ws.load_config() == ({}, [], [])


def test_a_settings_file_that_is_not_an_object_is_trouble(ws):
    write_config(ws, '[{"match": "OA-", "url": "https://t/"}]')
    good, links, trouble = ws.load_config()
    assert (good, links) == ({}, [])
    assert "not an object" in trouble[0]


def test_a_setting_outside_its_words_is_left_out_and_said(ws):
    """The page then uses its default."""
    write_config(ws, json.dumps({
        "colours": "dark", "tab_width": 5, "long_lines": "wrap",
        "diff_columns": True, "alerts": {"needs": True, "done": "yes"},
        "mine": "a key we do not know"}))
    good, _, trouble = ws.load_config()
    assert good == {"colours": "dark", "long_lines": "wrap"}
    said = " ".join(trouble)
    assert "tab_width" in said and "diff_columns" in said and "alerts" in said
    assert "mine" not in said          # not ours to judge
    assert ws.config_trouble("tab_width", True)
    assert not ws.config_trouble("tab_width", 8)


def test_the_file_is_in_the_configuration_directory(ws, monkeypatch, tmp_path):
    """Where a person looks for it, and where XDG says it goes."""
    monkeypatch.delenv("WOSTUAST_CONFIG")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert ws.config_path() == tmp_path / "xdg" / "wostuast" / "settings.json"
    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert ws.config_path() == (tmp_path / "home" / ".config" / "wostuast"
                                / "settings.json")
    # And the page is told it with the home as `~`, so it fits the menu.
    assert ws.config_payload()["path"] == "~/.config/wostuast/settings.json"


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
    write_config(ws, json.dumps({"links": [
        {"match": r"OK-(\d+)", "url": "https://tickets/$1"},
        {"match": "BAD-(", "url": "https://tickets/"},
    ]}))
    ws.cmd_doctor(argparse.Namespace())
    said = capsys.readouterr().out
    assert "link 2" in said and "not a regular expression" in said
    # And a broken link is not a reason for the whole check to fail.
    assert "note" in said


def test_doctor_says_the_old_links_file_is_no_longer_read(ws, capsys):
    """The reader chose no migration. A file that once made links and now
    does nothing gives no clue why, so `doctor` says where they go now."""
    ws.links_path().parent.mkdir(parents=True, exist_ok=True)
    ws.links_path().write_text("[]", encoding="utf-8")
    ws.cmd_doctor(argparse.Namespace())
    said = capsys.readouterr().out
    assert "no longer read" in said and "settings menu" in said


def test_a_settings_file_that_will_not_parse_says_what_is_wrong(ws):
    """The one people write. `\\d` is not a JSON escape, so the file never
    parses -- and the page showed nothing, which is also what a machine with
    no file looks like. Silence was the bug, not the typo."""
    write_config(ws, '{"links": [{"match": "(OA|QSP)-(\\d+)", "url": "https://t/$1-$2"}]}')
    good, links, trouble = ws.load_config()
    assert (good, links) == ({}, [])
    assert len(trouble) == 1
    assert "not valid JSON" in trouble[0]
    # And it says the thing that fixes it, because the error alone
    # ("Invalid \\escape") does not tell anybody to double a backslash.
    assert "doubled" in trouble[0]


def test_an_entry_that_cannot_be_used_is_trouble_and_the_rest_still_are_links(ws):
    """Dropping a broken entry in silence is the same bug one entry down."""
    write_config(ws, json.dumps({"links": [
        {"match": r"OK-(\d+)", "url": "https://tickets/$1"},
        {"match": "BAD-(", "url": "https://tickets/"},
    ]}))
    assert usable_links(ws) == [{"match": r"OK-(\d+)", "url": "https://tickets/$1"}]
    trouble = ws.load_config()[2]
    assert len(trouble) == 1 and "link 2" in trouble[0]


def test_a_change_is_written_and_keeps_what_it_did_not_touch(ws):
    """The menu sends one setting at a time, and the file is the reader's: a
    key a newer wostuast wrote, or a person, stays."""
    write_config(ws, json.dumps({"colours": "dark", "mine": [1, 2]}))
    assert ws.save_config({"tab_width": 8}) == ("", [])
    held = json.loads(ws.config_path().read_text(encoding="utf-8"))
    assert held == {"colours": "dark", "mine": [1, 2], "tab_width": 8}
    # Written to be read: indented, one key a line.
    assert '\n  "tab_width": 8' in ws.config_path().read_text(encoding="utf-8")


def test_a_bad_change_writes_nothing(ws):
    """One bad key and the whole change is refused, before the file is
    touched -- the page cannot write what the file would refuse to read."""
    write_config(ws, json.dumps({"colours": "dark"}))
    for change in ({"tab_width": 3}, {"colours": "auto", "wrap": "yes"},
                   {"alerts": {"needs": 1}}, {"links": "PROJ-1"}, {}):
        why, _ = ws.save_config(change)
        assert why, change
    assert json.loads(ws.config_path().read_text()) == {"colours": "dark"}


def test_a_link_that_cannot_be_used_is_left_out_and_the_rest_are_kept(ws):
    """The menu shows the refused one in red; a mistake in one pattern must
    not cost the reader the others. Where it stood comes back, so the page
    can put the reason under the right row."""
    why, refused = ws.save_config({"links": [
        {"match": r"OK-(\d+)", "url": "https://tickets/$1"},
        {"match": "(a+)+b", "url": "https://tickets/"},
        {"match": r"NO-(\d+)", "url": "ftp://tickets/$1"},
        {"match": r"X-(\d+)", "url": "https://t/$1", "extra": 1},
    ]})
    assert why == ""
    assert [one["at"] for one in refused] == [1, 2, 3]
    assert "quantifier" in refused[0]["trouble"]
    assert usable_links(ws) == [{"match": r"OK-(\d+)", "url": "https://tickets/$1"}]


def test_a_file_that_cannot_be_read_is_never_written_over(ws):
    """It is the reader's, and they may be halfway through an edit: a default
    written over it would take their work."""
    for held in ('{"links": [{"match": "OA-(\\d+)"', "[1, 2]"):
        write_config(ws, held)
        why, _ = ws.save_config({"tab_width": 2})
        assert "left alone" in why
        assert ws.config_path().read_text(encoding="utf-8") == held


def test_the_settings_file_is_private(ws):
    """The links name where the reader's tickets live, which is nobody
    else's business on a shared machine."""
    ws.save_config({"colours": "light"})
    assert oct(ws.config_path().stat().st_mode)[-3:] == "600"
    assert oct(ws.config_path().parent.stat().st_mode)[-3:] == "700"


def test_the_settings_in_the_page_cannot_end_its_script(ws):
    """A link is the reader's text and goes into a `<script>`. Written as it
    is, `</script>` in one ended the script there."""
    text = ws.page_json({"links": [{"match": "</script><b>&",
                                    "url": "\u2028" + chr(0xD800)}]})
    assert "<" not in text and ">" not in text and "&" not in text
    assert text.isascii()
    assert json.loads(text)["links"][0]["match"] == "</script><b>&"


def test_serve_says_what_is_wrong_with_the_settings_file(ws, capsys, monkeypatch):
    """The page says it only in a corner and `doctor` is something you had
    no reason to run, so the restart has to say it."""
    write_config(ws, "not json at all")

    assert start(ws, monkeypatch) == 0
    assert "settings:" in capsys.readouterr().out


def test_serve_says_nothing_about_a_settings_file_it_can_use(ws, capsys,
                                                             monkeypatch):
    """A line every start would be noise, and noise is not read."""
    write_config(ws, json.dumps({"links": [
        {"match": r"OK-(\d+)", "url": "https://t/$1"}]}))

    start(ws, monkeypatch)
    assert "settings:" not in capsys.readouterr().out


def test_serve_writes_no_file_of_its_own(ws, monkeypatch):
    """It left an example `links.json` once. Now the menu writes the file,
    and only when the reader changes something."""
    start(ws, monkeypatch)
    assert not ws.config_path().exists()
    assert not ws.links_path().exists()


def test_doctor_names_a_settings_file_that_will_not_parse(ws, capsys):
    write_config(ws, "not json at all")
    ws.cmd_doctor(argparse.Namespace())
    said = capsys.readouterr().out
    assert "not valid JSON" in said
    assert "note" in said               # still not a reason for the check to fail


def test_serve_says_how_much_history_it_read_and_how_long_it_took(
        ws, capsys, monkeypatch):
    """The log is never thrown away now, so the first read grows for ever,
    and the start is where you find out what that costs. Nothing else says
    it: the page is served before the read ends."""
    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 300)
    for i in range(12):
        ws.append_event({"session_id": "s1", "n": i, "pad": "z" * 40})
    files = len(ws.archived_events_paths()) + 1
    size = sum(path.stat().st_size for path in
               ws.archived_events_paths() + [ws.events_path()])

    start(ws, monkeypatch)
    said = capsys.readouterr().out
    assert f"read 12 events from {files} files ({ws.size_label(size)}) in " in said
    assert re.search(r"\) in (\d+ ms|\d+\.\d s)$", said, re.M)


def test_a_size_is_said_the_way_a_person_reads_it(ws):
    assert ws.size_label(412) == "412 B"
    assert ws.size_label(12 * 1024) == "12 KB"
    assert ws.size_label(45 * 1024 * 1024 + 200 * 1024) == "45.2 MB"
    assert ws.size_label(3 * 1024 ** 3 // 2) == "1.5 GB"


def shaped_transcript(transcript_file):
    """One transcript holding every shape `shapes` sorts: read, left out on
    purpose, not known, and a tag the page leaves showing. The words in it
    are the reader's own, and must never reach the output."""
    note = ("<task-notification>\n<task-id>b1</task-id>\n"
            "<output-file>/tmp/secret-output</output-file>\n"
            "PRIVATE-NOTE-WORDS\n</task-notification>")
    path = transcript_file("shapes", [
        dict(conftest.record("you", "PRIVATE-PROMPT-WORDS"), version="2.1.283"),
        {"type": "mode", "mode": "auto"},
        {"type": "brand-new-record", "content": "PRIVATE-NEW-WORDS"},
        {"type": "attachment", "attachment": {"type": "new_thing",
                                              "text": "PRIVATE-ATTACHED"}},
        {"type": "attachment", "attachment": {"type": "date"}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "image", "source": {"data": "PRIVATE-IMAGE"}}]}},
        {"type": "user", "message": {"role": "user", "content": note}},
        conftest.record("you", "how do I centre a <div> in <my-widget>?"),
        conftest.record("you", "why is a std::vector<uint32_t> slow?"),
        conftest.record("meta", "Run git show <commit-hash> before <next-step>."),
        conftest.record("you", "The page shows <bash-input>ls</bash-input> raw."),
        conftest.record("you", "<shiny-wrapper>Something new</shiny-wrapper>"),
    ])
    # A line separator inside a string is one record, not two halves. Written
    # raw, as Claude Code writes it: `json.dumps` escapes it by default, and
    # an escaped one never broke anything.
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(conftest.record("claude", "one\u2028record"),
                                ensure_ascii=False) + "\n")
    return path


def test_shapes_lists_what_the_page_cannot_show_and_never_the_text(
        ws, transcript_file, capsys):
    """Every bug of one kind lately -- `!git up`, `/clear`, `/model`, paste
    tags on the row -- was a shape Claude Code wrote and the page did not
    know, found by the reader as tags on the screen. `shapes` reads recent
    transcripts with the page's own reader and lists what it leaves out or
    leaves tagged: names and counts, so it can go into a public report."""
    shaped_transcript(transcript_file)
    assert ws.main(["shapes"]) == 0
    out = capsys.readouterr().out
    assert "brand-new-record" in out
    assert "attachment/new_thing" in out
    assert "user piece: image" in out
    assert "<task-id> in a note" in out
    assert "2.1.283 (1)" in out
    # Left out on purpose: bookkeeping, and the harness talking to the agent.
    assert "mode" not in out.split("does not show:")[1].split("tags")[0]
    assert "attachment/date" not in out
    # HTML a person types is not Claude Code's: no hyphen, no underscore.
    assert "<div>" not in out
    # A tag Claude Code writes is closed; an open one is C++ or a placeholder.
    assert "<uint32_t>" not in out and "<my-widget>" not in out
    assert "<commit-hash>" not in out and "<next-step>" not in out
    # A prompt that quotes a tag after its own words is a person's report; a
    # prompt that opens with a closed tag is a wrapper nobody knows yet.
    assert "<bash-input>" not in out
    assert "<shiny-wrapper> in a prompt" in out
    # The U+2028 record was read whole.
    assert "not a JSON object" not in out
    assert "PRIVATE" not in out and "secret-output" not in out


def test_shapes_reads_only_the_days_asked_for(ws, transcript_file, capsys):
    import os
    old = shaped_transcript(transcript_file)
    week_ago = time.time() - 8 * 86400
    os.utime(old, (week_ago, week_ago))
    ws.main(["shapes"])
    assert "Read 0 records in 0 transcripts" in capsys.readouterr().out
    ws.main(["shapes", "--days", "9"])
    assert "brand-new-record" in capsys.readouterr().out


def test_shapes_says_so_when_it_knows_everything(ws, transcript_file, capsys):
    transcript_file("plain", [conftest.record("you", "hello"),
                              conftest.record("claude", "hi")])
    ws.main(["shapes"])
    assert "Nothing the page does not know." in capsys.readouterr().out


# --- the start: a bare `wostuast` (#275) ---------------------------------------


class StopsAtOnce:
    """A server that stops the way ctrl-c stops it, before it serves."""

    server_address = ("127.0.0.1", 7331)

    def serve_forever(self):
        raise KeyboardInterrupt

    def shutdown(self):
        pass

    def server_close(self):
        pass


def start(ws, monkeypatch, made=None):
    """Run the start against a server that stops at once."""
    def make(daemon, port):
        if made is not None:
            made.append(port)
        return StopsAtOnce()

    monkeypatch.setattr(ws, "make_server", make)
    monkeypatch.setattr(ws.Daemon, "run", lambda self: None)
    code = ws.cmd_serve(argparse.Namespace(port=0, open=False))
    # The first read prints its line from a thread of its own, and would
    # print it into the next test's output.
    for worker in threading.enumerate():
        if worker.name == "wostuast-refresh":
            worker.join(10)
    return code


def test_a_start_brings_everything_up_to_date_and_says_so_in_a_line(
        ws, monkeypatch, capsys):
    assert start(ws, monkeypatch) == 0
    out = capsys.readouterr().out
    updated = [line for line in out.splitlines() if "↻ updated" in line]
    assert len(updated) == 1
    for part in (str(ws.install_path()), str(ws.hook_path()),
                 f"{len(ws.HOOK_EVENTS)} hooks", "status line"):
        assert part in updated[0]
    assert "restart your Claude Code sessions" in out
    settings = json.loads(ws.settings_path().read_text())
    assert all(event in settings["hooks"] for event in ws.HOOK_EVENTS)


def test_a_start_with_nothing_behind_writes_nothing(ws, monkeypatch, capsys):
    """Claude Code's `settings.json` is the user's file: a start that has
    nothing to fix leaves it alone, its time included."""
    start(ws, monkeypatch)
    files = [ws.settings_path(), ws.install_path(), ws.hook_path()]
    before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in files]
    capsys.readouterr()
    assert start(ws, monkeypatch) == 0
    assert [(path.read_bytes(), path.stat().st_mtime_ns) for path in files] == before
    out = capsys.readouterr().out
    assert "↻" not in out
    assert f"✓ {len(ws.HOOK_EVENTS)} hooks → " in out


def test_a_start_stops_on_a_settings_file_it_cannot_read(
        ws, monkeypatch, capsys, tmp_path):
    """Red, on stderr, and nothing served: the hooks cannot be checked. One
    short line: the path as a person writes it, and only where the JSON
    breaks. The parser's own words ran past the edge of the terminal and
    named the place twice."""
    monkeypatch.setenv("HOME", str(tmp_path))
    ws.settings_path().parent.mkdir(parents=True, exist_ok=True)
    ws.settings_path().write_text("{not json")
    made = []
    assert start(ws, monkeypatch, made) == 1
    assert made == []
    assert capsys.readouterr().err.splitlines() == [
        "  ✗ cannot read ~/claude/settings.json: not valid JSON at line 1, column 2"]
    assert ws.settings_path().read_text() == "{not json"


def test_a_settings_file_that_holds_no_object_is_said_once(ws, monkeypatch,
                                                           capsys, tmp_path):
    """The path is in the line once, not twice."""
    monkeypatch.setenv("HOME", str(tmp_path))
    ws.settings_path().parent.mkdir(parents=True, exist_ok=True)
    ws.settings_path().write_text("[1, 2]")
    assert ws.cmd_install(None) == 1
    assert capsys.readouterr().err == (
        "cannot read ~/claude/settings.json: it holds no JSON object\n")


def test_a_start_says_when_the_status_line_is_your_own(ws, monkeypatch, capsys):
    ws.settings_path().parent.mkdir(parents=True, exist_ok=True)
    ws.settings_path().write_text(json.dumps(
        {"statusLine": {"type": "command", "command": "mine.sh"}}))
    start(ws, monkeypatch)
    out = capsys.readouterr().out
    assert "your own status line runs" in out
    assert json.loads(ws.settings_path().read_text())["statusLine"]["command"] == "mine.sh"


def test_the_start_is_coloured_only_on_a_terminal(ws, monkeypatch, capsys):
    """Green for what is right, yellow for what changed; plain text where
    nobody sees colour (`use_color`: a pipe, or NO_COLOR)."""
    monkeypatch.setattr(ws, "use_color", lambda: True)
    start(ws, monkeypatch)
    out = capsys.readouterr().out
    assert "\033[33m↻\033[0m updated" in out
    assert "\033[32m✓\033[0m python" in out
    monkeypatch.setattr(ws, "use_color", lambda: False)
    start(ws, monkeypatch)
    assert "\033[" not in capsys.readouterr().out


# --- install and start share their helpers (#285) ------------------------------


def test_doctor_makes_the_state_directory_private(ws, capsys):
    """`doctor` made it with `mkdir` alone, so on a new machine it stood at
    the umask, 0755, holding every prompt, until a hook ran."""
    old = os.umask(0o022)
    try:
        ws.cmd_doctor(argparse.Namespace())
    finally:
        os.umask(old)
    capsys.readouterr()
    assert ws.state_dir().stat().st_mode & 0o777 == 0o700


def test_a_home_of_root_is_not_written_as_a_tilde(ws, monkeypatch):
    """`config_payload` guarded against it and `tilde` did not; one owns it."""
    monkeypatch.setattr(ws.Path, "home", classmethod(lambda cls: ws.Path("/")))
    assert ws.tilde("/etc/wostuast/settings.json") == "/etc/wostuast/settings.json"
    assert ws.config_payload()["path"] == str(ws.config_path())


def test_a_start_builds_the_hook_once(ws, monkeypatch):
    """It parses the whole program: once to write the hook file, and it was
    once more to compare it."""
    made = []
    real = ws.hook_source
    monkeypatch.setattr(ws, "hook_source",
                        lambda source: made.append(1) or real(source))
    assert start(ws, monkeypatch) == 0
    assert len(made) == 1


def test_the_program_is_written_executable_and_whole(ws, tmp_path):
    target = tmp_path / "bin" / "wostuast"
    assert ws.write_program(target, "#!/bin/sh\n") is True
    assert target.stat().st_mode & 0o777 == 0o755
    assert ws.write_program(target, "#!/bin/sh\n") is False
    assert sorted(p.name for p in target.parent.iterdir()) == ["wostuast"]
