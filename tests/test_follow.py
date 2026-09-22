"""Following a growing file: nothing twice, nothing lost, nothing half-read."""

from __future__ import annotations

import json


def test_it_reads_each_line_once(ws, tmp_path):
    path = tmp_path / "f.jsonl"
    path.write_text("a\nb\n")
    tail = ws.Tail(path)
    assert tail.read_new() == [b"a", b"b"]
    assert tail.read_new() == []
    with open(path, "a") as handle:
        handle.write("c\n")
    assert tail.read_new() == [b"c"]


def test_a_missing_file_is_quiet(ws, tmp_path):
    assert ws.Tail(tmp_path / "nothing").read_new() == []


def test_a_half_written_line_waits_for_its_newline(ws, tmp_path):
    path = tmp_path / "f.jsonl"
    path.write_text('{"a": 1}\n{"b": ')
    tail = ws.Tail(path)
    assert tail.read_new() == [b'{"a": 1}']
    assert tail.partial == b'{"b": '
    with open(path, "a") as handle:
        handle.write("2}\n")
    assert tail.read_new() == [b'{"b": 2}']


def test_a_line_split_across_three_reads(ws, tmp_path):
    path = tmp_path / "f.jsonl"
    path.write_text("")
    tail = ws.Tail(path)
    for piece in ("he", "ll", "o"):
        with open(path, "a") as handle:
            handle.write(piece)
        assert tail.read_new() == []
    with open(path, "a") as handle:
        handle.write("\n")
    assert tail.read_new() == [b"hello"]


def test_a_file_replaced_under_the_same_name_starts_again(ws, tmp_path):
    """The trap this guards: seeking past the end of a smaller new file and
    then going quiet for ever."""
    path = tmp_path / "f.jsonl"
    path.write_text("one\ntwo\nthree\nfour\n")
    tail = ws.Tail(path)
    assert len(tail.read_new()) == 4
    (tmp_path / "other").write_text("new\n")
    (tmp_path / "other").replace(path)
    assert tail.read_new() == [b"new"]


def test_a_file_rewritten_shorter_in_place_starts_again(ws, tmp_path):
    path = tmp_path / "f.jsonl"
    path.write_text("one\ntwo\nthree\n")
    tail = ws.Tail(path)
    assert len(tail.read_new()) == 3
    path.write_text("x\n")          # same inode, less content
    assert tail.read_new() == [b"x"]


def test_blank_lines_are_skipped(ws, tmp_path):
    path = tmp_path / "f.jsonl"
    path.write_text("a\n\n   \nb\n")
    assert ws.Tail(path).read_new() == [b"a", b"b"]


# --- the event log, which the hook rotates under us -------------------------


def test_the_follower_reads_new_events(ws):
    follower = ws.EventFollower()
    assert list(follower.new_events()) == []
    ws.append_event({"session_id": "s", "n": 1})
    assert [e["n"] for e in follower.new_events()] == [1]
    ws.append_event({"session_id": "s", "n": 2})
    ws.append_event({"session_id": "s", "n": 3})
    assert [e["n"] for e in follower.new_events()] == [2, 3]
    assert list(follower.new_events()) == []


def test_nothing_is_lost_when_the_log_rotates_under_the_follower(ws, monkeypatch):
    """The hook rotates, not the daemon, so this happens without warning.

    A rotation makes the archive tail read a file it has already read, so some
    events arrive a second time. Losing one is the failure; repeating one is
    not, and `Store.apply` ignores an event older than the session has seen.
    """
    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 900)
    follower = ws.EventFollower()
    seen: list[int] = []
    written = 0
    while not ws.archived_events_paths():
        ws.append_event({"session_id": "s", "n": written, "pad": "x" * 60})
        written += 1
        seen += [e["n"] for e in follower.new_events()]
        assert written < 200
    seen += [e["n"] for e in follower.new_events()]
    assert set(seen) == set(range(written)), "an event went missing"


def test_events_written_between_polls_survive_a_rotation(ws, monkeypatch):
    """The harder case: the follower is not watching when the log turns over."""
    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 900)
    follower = ws.EventFollower()
    ws.append_event({"session_id": "s", "n": 0, "pad": "x" * 60})
    assert [e["n"] for e in follower.new_events()] == [0]
    written = 1
    while not ws.archived_events_paths():
        ws.append_event({"session_id": "s", "n": written, "pad": "x" * 60})
        written += 1
        assert written < 200
    assert set(e["n"] for e in follower.new_events()) >= set(range(1, written))


def test_a_daemon_started_after_a_rotation_still_sees_the_history(ws, monkeypatch):
    """It used to tail only the live file, so every session that started before
    the rotation lost its cwd, its pane and its pid."""
    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 900)
    ws.append_event({"session_id": "s", "hook_event_name": "SessionStart",
                     "cwd": "/w/repo/dir", "pane": "%7", "pid": 1, "ts": 1000.0})
    n = 0
    while not ws.archived_events_paths():
        ws.append_event({"session_id": "s", "hook_event_name": "PreToolUse",
                         "tool_name": "Bash", "tool_input": {"command": "x" * 60},
                         "pid": 1, "ts": 1001.0 + n})
        n += 1
        assert n < 200

    store = ws.Store()                      # as if the daemon had just started
    store.follow()
    session = store.sessions["s"]
    assert session.cwd == "/w/repo/dir"
    assert session.pane == "%7"


def test_an_event_delivered_twice_does_not_rewind_a_session(ws):
    """A rotation re-reads the archive, so old events arrive after new ones."""
    store = ws.Store()
    start = {"session_id": "s", "hook_event_name": "SessionStart",
             "cwd": "/w/repo/dir", "pid": 1, "ts": 1000.0}
    store.apply(start)
    store.apply({"session_id": "s", "hook_event_name": "Stop", "ts": 1005.0})
    assert store.sessions["s"].state == "done"

    store.apply(start)                      # the archive, read again
    assert store.sessions["s"].state == "done"
    assert store.sessions["s"].cwd == "/w/repo/dir"


def test_broken_lines_do_not_stop_the_follower(ws):
    path = ws.events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"n": 1}\nrubbish\n[1,2]\n{"n": 2}\n')
    assert [e["n"] for e in ws.EventFollower().new_events()] == [1, 2]


# --- a log that is never thrown away has to be read a piece at a time -------


def held_at_most(read) -> tuple[int, int]:
    """Run `read`, and say how many items it gave and the most memory it held
    at any one moment. `tracemalloc` sees every bytes object `read()` makes."""
    import tracemalloc

    tracemalloc.start()
    try:
        count = sum(1 for _ in read())
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return count, peak


def test_a_big_log_is_read_a_piece_at_a_time(ws, monkeypatch):
    """`Tail` read the whole rest of a file in one `read()`, then split it and
    kept both. Measured on a synthetic 400 MB log: 821 MB resident, for a
    daemon that holds a few kilobytes per session. The log was capped at two
    files of 20 MB, so nobody met it; keeping every archive is what makes it
    a real bill, so the read is capped rather than the history."""
    monkeypatch.setattr(ws, "TAIL_CHUNK", 64 * 1024, raising=False)
    path = ws.events_path()
    ws.private_dir(path.parent)
    line = json.dumps({"session_id": "s", "pad": "x" * 500}) + "\n"
    path.write_text(line * 8000)                 # about 4 MB

    count, peak = held_at_most(ws.EventFollower().new_events)
    assert count == 8000
    assert peak < 1024 * 1024, f"held {peak:,} bytes at once for a 4 MB log"


def test_a_line_longer_than_a_piece_is_still_read_whole(ws, tmp_path,
                                                        monkeypatch):
    """A piece that holds no newline gives no line, and an empty answer is
    not the end of the file. Stopping there would leave a Write of a big file
    unread until the next event came along to push it through."""
    monkeypatch.setattr(ws, "TAIL_CHUNK", 1024, raising=False)
    path = tmp_path / "f.jsonl"
    long = b"y" * 5000
    path.write_bytes(b"a\n" + long + b"\nb\n")
    assert ws.Tail(path).read_new() == [b"a", long, b"b"]


def test_a_rotation_between_two_reads_does_not_read_the_archive_again(
        ws, monkeypatch):
    """The live file becomes an archive under a new name, and a tail that
    only knew names read all of it again: 20 MB parsed a second time on every
    rotation. The follower knows the file by its inode and carries on."""
    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 900)
    follower = ws.EventFollower()
    seen: list[int] = []
    written = 0
    while len(ws.archived_events_paths()) < 3:
        ws.append_event({"session_id": "s", "n": written, "pad": "x" * 60})
        written += 1
        seen += [e["n"] for e in follower.new_events()]
        assert written < 500
    assert seen == list(range(written)), "an event was lost or read twice"
