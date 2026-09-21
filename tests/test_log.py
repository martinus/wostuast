"""The event log: append, read, rotate, and a hook that never fails."""

from __future__ import annotations

import time

import pytest

import json


def test_append_and_read_round_trip(ws):
    ws.append_event({"session_id": "s1", "hook_event_name": "Stop", "ts": 1.0})
    ws.append_event({"session_id": "s1", "hook_event_name": "SessionEnd", "ts": 2.0})
    events = list(ws.read_events())
    assert [e["hook_event_name"] for e in events] == ["Stop", "SessionEnd"]


def test_read_skips_broken_lines(ws):
    path = ws.events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"a": 1}\nnot json\n\n[1,2]\n{"b": 2}\n')
    assert list(ws.read_events()) == [{"a": 1}, {"b": 2}]


def test_read_of_a_missing_file_is_empty(ws):
    assert list(ws.read_events()) == []


def test_the_log_rotates_when_it_grows(ws, monkeypatch):
    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 200)
    for index in range(40):
        ws.append_event({"session_id": "s1", "n": index, "pad": "x" * 40})
    backup = ws.events_path().with_name("events.1.jsonl")
    assert backup.exists()
    assert ws.events_path().stat().st_size <= 2 * ws.EVENTS_MAX_BYTES


def test_the_payload_is_kept_whole(ws):
    payload = {"session_id": "s", "hook_event_name": "PostToolUse",
               "tool_response": {"deep": {"list": [1, 2, 3]}}, "brand_new_field": "keep me"}
    ws.append_event(dict(payload, ts=1.0))
    stored = list(ws.read_events())[0]
    assert stored["brand_new_field"] == "keep me"
    assert stored["tool_response"]["deep"]["list"] == [1, 2, 3]


def test_hook_writes_ts_pane_and_pid(run_cli, tmp_path):
    """The three fields the hook adds to whatever Claude Code sent.

    `pid` is the agent, found by walking up the ancestry, so it is 0 wherever
    there is no Claude Code above us: a CI runner, or a hand-run hook. That is
    the designed answer, not a failure, and a session with pid 0 is simply
    never reported as killed. `shell_pid` is the process that ran us and is
    always there. test_state.py walks a real chain and checks the agent is
    found when there is one.
    """
    payload = {"session_id": "s1", "hook_event_name": "Stop", "cwd": "/w"}
    done = run_cli(["hook"], json.dumps(payload))
    assert done.returncode == 0
    line = json.loads((tmp_path / "state" / "events.jsonl").read_text().strip())
    assert line["session_id"] == "s1"
    assert line["pane"] == "%3"
    assert line["shell_pid"] > 0
    assert line["pid"] >= 0
    assert line["ts"] > 0


def test_hook_exits_zero_on_broken_input(run_cli, tmp_path):
    done = run_cli(["hook"], "this is not json")
    assert done.returncode == 0
    assert not (tmp_path / "state" / "events.jsonl").exists()


def test_hook_exits_zero_on_empty_input(run_cli):
    assert run_cli(["hook"], "").returncode == 0


def test_hook_exits_zero_when_the_state_directory_is_a_file(run_cli, tmp_path):
    (tmp_path / "state").write_text("in the way")
    assert run_cli(["hook"], '{"session_id": "s"}').returncode == 0


def test_counting_does_not_parse(ws):
    path = ws.events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"a": 1}\nnot json at all\n{"b": 2}\n')
    assert ws.count_events() == 3
    assert len(list(ws.read_events())) == 2


def test_counting_a_missing_log_is_zero(ws):
    assert ws.count_events() == 0


def test_broken_utf8_is_skipped_not_fatal(ws):
    path = ws.events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'{"a": 1}\n{"bad": "\xff\xfe"}\n{"b": 2}\n')
    assert [e for e in ws.read_events()] == [{"a": 1}, {"b": 2}]


def test_the_deadline_fires(ws):
    """A hook that waits forever would hold Claude Code. It must not."""
    ws.give_up_after(1)
    try:
        with pytest.raises(TimeoutError):
            time.sleep(3)
    finally:
        ws.stand_down()


def test_standing_down_cancels_the_deadline(ws):
    ws.give_up_after(1)
    ws.stand_down()
    time.sleep(1.2)  # would raise if the deadline were still armed


def test_the_hook_arms_and_cancels_the_deadline(ws, monkeypatch):
    calls = []
    monkeypatch.setattr(ws, "give_up_after", lambda seconds: calls.append(("arm", seconds)))
    monkeypatch.setattr(ws, "stand_down", lambda: calls.append(("cancel", 0)))
    monkeypatch.setattr(ws, "read_stdin_json", lambda: {"session_id": "s1"})
    assert ws.cmd_hook(None) == 0
    assert calls == [("arm", ws.HOOK_TIMEOUT), ("cancel", 0)]


def test_the_hook_cancels_the_deadline_even_when_it_fails(ws, monkeypatch):
    calls = []
    monkeypatch.setattr(ws, "give_up_after", lambda seconds: calls.append("arm"))
    monkeypatch.setattr(ws, "stand_down", lambda: calls.append("cancel"))

    def explode():
        raise RuntimeError("boom")

    monkeypatch.setattr(ws, "read_stdin_json", explode)
    assert ws.cmd_hook(None) == 0
    assert calls == ["arm", "cancel"]


def fill_until_one_rotation(ws, make_event):
    """Append events until the log rotates exactly once. Returns how many."""
    written = 0
    while not ws.rotated_events_path().exists():
        ws.append_event(make_event(written))
        written += 1
        assert written < 500, "the log never rotated"
    return written


def test_the_rotated_log_is_still_history(ws, monkeypatch):
    """After a rotation a running session must keep its cwd, pane and pid.

    Its SessionStart is in the rotated file, and that is the only place the
    cwd, the pane and the pid are ever recorded.
    """
    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 3000)
    ws.append_event({"session_id": "s1", "hook_event_name": "SessionStart",
                     "cwd": "/w/repo/dir", "pane": "%7", "pid": 1, "ts": 1000.0})
    fill_until_one_rotation(ws, lambda i: {
        "session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": "Bash",
        "tool_input": {"command": "x" * 60}, "pid": 1, "ts": 1001.0 + i})

    sessions = ws.build_sessions(now=1200.0, alive=lambda pid: True)
    assert len(sessions) == 1
    assert sessions[0].cwd == "/w/repo/dir"
    assert sessions[0].pane == "%7"
    assert sessions[0].label == "dir"


def test_both_files_are_read_and_counted(ws, monkeypatch):
    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 500)
    written = fill_until_one_rotation(ws, lambda i: {"session_id": "s1", "n": i,
                                                     "pad": "z" * 40})
    assert ws.count_events() == written
    assert [e["n"] for e in ws.read_events()] == list(range(written))


def test_a_second_rotation_drops_the_oldest_generation(ws, monkeypatch):
    """The log keeps two files, no more. This is by design; it is pinned so a
    reader of `ls` is never surprised by history that quietly reappears."""
    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 400)
    for i in range(60):
        ws.append_event({"session_id": "s1", "n": i, "pad": "z" * 40})
    seen = [e["n"] for e in ws.read_events()]
    assert seen == sorted(seen)          # still oldest first
    assert seen[-1] == 59                # the newest is always there
    assert len(seen) < 60                # but the oldest generation is gone


def test_the_hook_says_nothing_at_all(run_cli):
    """Claude Code reads a hook's stdout as its answer, and for PreToolUse that
    answer can allow or deny a tool. wostuast must never answer."""
    done = run_cli(["hook"], json.dumps(
        {"session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": "Bash",
         "tool_input": {"command": "rm -rf /"}}))
    assert done.returncode == 0
    assert done.stdout == ""
    assert done.stderr == ""


def test_the_hook_stays_silent_even_when_it_fails(run_cli, tmp_path):
    (tmp_path / "state").write_text("in the way")
    done = run_cli(["hook"], json.dumps({"session_id": "s"}))
    assert done.returncode == 0
    assert done.stdout == ""
    assert done.stderr == ""


PROBE_SETUP = (
    "import sys, io, json, importlib.machinery, importlib.util\n"
)

PROBE_RUN = (
    "sys.stdin = io.StringIO(json.dumps({'session_id': 's'}))\n"
    "loader = importlib.machinery.SourceFileLoader('wostuast', 'wostuast')\n"
    "spec = importlib.util.spec_from_loader(loader.name, loader)\n"
    "ws = importlib.util.module_from_spec(spec)\n"
    "sys.modules['wostuast'] = ws\n"
    "loader.exec_module(ws)\n"
    "assert ws.main(['hook']) == 0\n"
)


def modules_after(code):
    """Which modules a fresh interpreter has loaded after running this code."""
    import subprocess
    import sys

    done = subprocess.run(
        [sys.executable, "-c", code + "print('LOADED:' + ','.join(sorted(sys.modules)))"],
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", "WOSTUAST_STATE": "/tmp/wostuast-probe"},
    )
    assert done.returncode == 0, done.stderr
    marker = [line for line in done.stdout.splitlines() if line.startswith("LOADED:")]
    assert marker, done.stdout
    return set(marker[0][len("LOADED:"):].split(","))


def test_the_hook_does_not_import_what_it_does_not_need():
    """The hook runs on every tool call, so what it loads is what Claude Code
    waits for. This pins the cost: nobody can add a git call, an HTTP client or
    the argument parser to the hot path without a test going red.

    It measures the difference the hook makes, not the total, because the probe
    itself loads `importlib`, and `pathlib` fairly pulls in `urllib.parse`.
    """
    baseline = modules_after(PROBE_SETUP)
    after_hook = modules_after(PROBE_SETUP + PROBE_RUN)
    added = after_hook - baseline

    assert "wostuast" in added, "the probe did not actually run the hook"
    avoidable = {"subprocess", "shutil", "argparse", "socket", "http", "ssl",
                 "email", "concurrent.futures", "urllib.request", "sqlite3"}
    assert not (added & avoidable), f"the hook now loads: {sorted(added & avoidable)}"


def test_the_hook_says_nothing_to_a_permission_request(run_cli):
    """PermissionRequest takes a decision to allow or deny. Our silence is what
    makes it "no opinion", so this is the most important assertion in the suite.
    """
    done = run_cli(["hook"], json.dumps({
        "session_id": "s1", "hook_event_name": "PermissionRequest",
        "tool_name": "Bash", "tool_input": {"command": "rm -rf /"},
    }))
    assert done.returncode == 0
    assert done.stdout == ""
    assert done.stderr == ""


def test_the_hook_records_zero_when_there_is_no_agent_above_it(ws, monkeypatch):
    """A hand-run hook, or a CI runner, has no Claude Code ancestor. The pid is
    then 0, and a session with pid 0 is never reported as killed."""
    monkeypatch.setattr(ws, "looks_like_claude", lambda pid: False)
    assert ws.agent_pid() == 0
    session = ws.Session(session_id="s", pid=0, state="working")
    ws.mark_dead(session, alive=lambda pid: False)
    assert session.state == "working"


# --- what two hooks at once must not do --------------------------------------


def test_a_hook_holding_the_old_log_does_not_replace_the_archive(ws, monkeypatch):
    """A flock is on an inode, not on a name. Hook B opens the log and blocks;
    hook A rotates and releases; B then holds the *archive*, sees a file over
    the limit, and renames the fresh log on top of it — every event ever
    recorded, gone.

    The handle is handed to `append_event` rather than the interleaving being
    raced, because the condition is what matters: this is a hook that is
    holding the wrong inode, however it came to be.
    """
    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 500)
    target = ws.events_path()
    ws.private_dir(target.parent)
    target.write_text("EVERY EVENT EVER RECORDED\n" + "x" * 600 + "\n")

    stale = ws.open_private(target)             # opened before the rotation
    ws.append_event({"session_id": "a"})        # A rotates and appends
    assert "EVERY EVENT" in ws.rotated_events_path().read_text()

    real_open = ws.open_private
    handed = []

    def hand_the_stale_one(path):
        if not handed:
            handed.append(1)
            return stale                        # the inode that is now the archive
        return real_open(path)

    monkeypatch.setattr(ws, "open_private", hand_the_stale_one)
    ws.append_event({"session_id": "b"})

    assert "EVERY EVENT" in ws.rotated_events_path().read_text(), "the archive went"
    assert '"session_id": "b"' in target.read_text(), "and the event still landed"


def test_a_lone_surrogate_does_not_lose_the_event(ws):
    """JS strings are UTF-16 and `JSON.stringify` escapes an unpaired
    surrogate rather than refusing it, so one can arrive in a tool response.
    A strict encoder turned that into a dropped event — and a SessionStart
    lost that way costs the session its cwd, pane and pid for good.

    The surrogate is built with `chr`, never written as an escape in this
    file: that would put a real one in the source, and Python 3.13 cannot
    write a module holding one into a bytecode cache."""
    lonely = "before" + chr(0xD800) + "after"
    ws.append_event({"session_id": "s1", "hook_event_name": "SessionStart",
                     "cwd": "/w/one", "tool_response": lonely})
    events = list(ws.read_events())
    assert len(events) == 1
    assert events[0]["cwd"] == "/w/one"
    assert "before" in events[0]["tool_response"]


def test_no_source_file_holds_a_lone_surrogate(ws):
    """Writing the escape in a docstring, to say what the fix is about, puts a
    real lone surrogate in the source. Python 3.10 to 3.12 marshal one into a
    bytecode cache without complaint; **3.13 refuses**, and the import fails
    before a single test runs. So the suite was green on four versions and the
    build was red on one, over a comment.

    Build such a character with `chr(0xD800)` instead. This test reads every
    source file the same way on every version, so the rule does not depend on
    which Python is running it.
    """
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    files = [root / "wostuast"] + sorted(root.glob("tests/*.py"))
    guilty = []
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(), str(path))):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            try:
                node.value.encode("utf-8")
            except UnicodeEncodeError:
                guilty.append(f"{path.name}:{node.lineno}")
    assert not guilty, f"use chr(0xD800) rather than the escape: {guilty}"


def test_the_log_is_ours_from_the_moment_it_exists(ws):
    """Not after the first write. The window does not close if the process
    dies inside it, and by then the file already holds a prompt."""
    import stat

    target = ws.events_path()
    ws.private_dir(target.parent)
    assert not target.exists()
    ws.append_event({"session_id": "s1", "prompt": "something private"})
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_the_hook_logs_under_its_own_deadline(ws, monkeypatch):
    """`log` opens and writes a file, and the failure being logged may be that
    the filesystem is not answering. Cancelling the alarm and then writing is
    how a hook holds Claude Code for ever."""
    import signal

    seen = []
    monkeypatch.setattr(ws, "read_stdin_json",
                        lambda: (_ for _ in ()).throw(RuntimeError("no stdin")))
    real_log = ws.log
    monkeypatch.setattr(ws, "log", lambda message: (
        seen.append(signal.getitimer(signal.ITIMER_REAL)[0]), real_log(message)))
    assert ws.cmd_hook(None) == 0
    assert seen and seen[0] > 0, "the deadline was cancelled before the logging"


def test_a_pane_id_with_a_newline_is_not_a_pane_id(ws):
    """`$` matches before a final newline; `\\Z` does not."""
    assert ws.PANE_PATTERN.match("%7")
    assert not ws.PANE_PATTERN.match("%7\n")


def test_two_threads_writing_one_file_do_not_unlink_each_other(ws, tmp_path):
    """The temporary name carried the pid alone, which is the same for both —
    so one thread renamed or unlinked the other's half-written file, and the
    loser raised `FileNotFoundError` out of `write_atomic`. Two processes were
    thought of; two threads of one process were not, and the daemon answers
    every browser in a thread of its own.
    """
    import threading

    target = tmp_path / "shared.json"
    trouble = []

    def write(text):
        try:
            for _ in range(20):
                ws.write_atomic(target, text)
        except Exception as error:      # noqa: BLE001 - the point of the test
            trouble.append(error)

    threads = [threading.Thread(target=write, args=(text,))
               for text in ("one", "two")]
    for one in threads:
        one.start()
    for one in threads:
        one.join()
    assert trouble == []
    assert target.read_text() in ("one", "two")


def test_the_map_in_claude_md_points_at_real_symbols():
    """`CLAUDE.md` opens with a table routing "about to touch X" to the
    section that holds the rules for it. A router that names a symbol the
    program no longer has sends an agent grepping for nothing, and a wrong
    map is worse than none: it is believed.

    Three numbers in that file went stale by 40% before anybody noticed. The
    table is the part most likely to go the same way, because it is the part
    that names code.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent.parent
    doc = (root / "CLAUDE.md").read_text(encoding="utf-8")
    program = (root / "wostuast").read_text(encoding="utf-8")
    start = doc.index("## Where to look")
    table = doc[start:doc.index("\n## ", start + 4)]
    named = sorted(set(re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", table)))
    assert len(named) > 20, "the table stopped naming symbols"
    missing = [one for one in named if one not in program]
    assert not missing, f"CLAUDE.md routes to symbols that are gone: {missing}"

