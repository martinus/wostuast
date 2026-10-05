"""Following a growing file: nothing twice, nothing lost, nothing half-read."""

from __future__ import annotations

import errno
import json
from pathlib import Path


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

    Every event comes once and in the order of the log. `Store.apply` folds
    whatever it is given, so a repeat, or an old event after a new one, would
    set a session back to what it was then.
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
    assert seen == list(range(written)), "an event was lost, repeated or moved"


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
    assert [e["n"] for e in follower.new_events()] == list(range(1, written))


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


def rotate_once(ws, n: int) -> int:
    """Append numbered events until the log has rotated once more, then one
    more into the new live file. Gives the next number to write."""
    before = len(ws.archived_events_paths())
    start = n
    while len(ws.archived_events_paths()) == before:
        ws.append_event({"session_id": "s", "n": n, "pad": "x" * 60})
        n += 1
        assert n - start < 200
    ws.append_event({"session_id": "s", "n": n, "pad": "x" * 60})
    return n + 1


def test_a_rotation_in_the_middle_of_a_pass_is_read_once_and_in_order(
        ws, monkeypatch):
    """At the start the fold reads a year of archives, which takes seconds,
    and a hook can rotate the log meanwhile. The follower listed the
    archives once a pass, so it read the new live file first and the new
    archive after it, a pass later -- and `Store.apply` dropped every event
    in it as old: an open question with no bar. Here the rotation lands
    after the first event a pass gives: once at the start, and once while
    an archive the live tail was handed over to is read."""
    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 900)
    written = rotate_once(ws, 0)
    written = rotate_once(ws, written)
    follower = ws.EventFollower()
    seen: list[int] = []
    for _ in range(2):
        for index, one in enumerate(follower.new_events()):
            seen.append(one["n"])
            if index == 0:
                written = rotate_once(ws, written)
        seen += [e["n"] for e in follower.new_events()]
        # The live file, part read, becomes an archive before the next pass.
        written = rotate_once(ws, written)
    seen += [e["n"] for e in follower.new_events()]
    assert seen == list(range(written)), "an event was lost, repeated or moved"


def test_a_rotation_just_after_the_listing_is_read_in_order(ws, monkeypatch):
    """The narrow case: the log rotates after the archives are listed and
    before the live file is opened. Opened then, the live name is already
    the new file, and the old one's last events come after it, from the top.
    The follower opens the live file first, so what it holds is the file
    the listing was about."""
    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 900)
    follower = ws.EventFollower()
    written = 0
    seen: list[int] = []
    for _ in range(3):
        ws.append_event({"session_id": "s", "n": written, "pad": "x" * 60})
        written += 1
        seen += [e["n"] for e in follower.new_events()]
    listing = ws.archived_events_paths
    rotated: list[int] = []

    def then_rotate():
        found = listing()
        if not rotated:
            rotated.append(1)
            nonlocal written
            written = rotate_once(ws, written)
        return found

    monkeypatch.setattr(ws, "archived_events_paths", then_rotate)
    seen += [e["n"] for e in follower.new_events()]
    seen += [e["n"] for e in follower.new_events()]
    assert rotated
    assert seen == list(range(written)), "an event was lost, repeated or moved"


def refuse_to_open(ws, monkeypatch, refused: Path) -> None:
    """`open` fails for one file, as it does for a daemon out of descriptors."""
    import builtins

    def opener(path, *args, **kwargs):
        if Path(path) == refused:
            raise OSError(errno.EMFILE, "Too many open files", str(path))
        return builtins.open(path, *args, **kwargs)

    monkeypatch.setattr(ws, "open", opener, raising=False)


def test_an_archive_that_could_not_be_opened_is_read_on_the_next_pass(
        ws, monkeypatch):
    """`Tail.lines` stops quietly when `open` fails, and the follower took
    that for the end of the archive: its events were not read until the
    daemon started again. Nothing after it is read meanwhile, so the log
    still folds in its order."""
    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 900)
    written = rotate_once(ws, 0)
    refuse_to_open(ws, monkeypatch, ws.archived_events_paths()[0])
    follower = ws.EventFollower()
    assert list(follower.new_events()) == []
    monkeypatch.delattr(ws, "open")
    assert [e["n"] for e in follower.new_events()] == list(range(written))


def test_an_archive_that_never_opens_is_given_up_in_the_end(ws, monkeypatch):
    """Waiting on it for ever would stop the log for good. After
    `ARCHIVE_TRIES` passes it is left out, and the rest is read."""
    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 900)
    rotate_once(ws, 0)
    live = [json.loads(line)["n"] for line in
            ws.events_path().read_text().splitlines()]
    refuse_to_open(ws, monkeypatch, ws.archived_events_paths()[0])
    follower = ws.EventFollower()
    for _ in range(ws.ARCHIVE_TRIES - 1):
        assert list(follower.new_events()) == []
    assert [e["n"] for e in follower.new_events()] == live
    assert list(follower.new_events()) == []


def fail_to_list(ws, monkeypatch) -> None:
    """`os.listdir` fails as it does for a daemon out of descriptors."""
    def listdir(path):
        raise OSError(errno.EMFILE, "Too many open files", str(path))

    monkeypatch.setattr(ws.os, "listdir", listdir)


def test_a_listing_that_fails_reads_nothing_until_it_works(ws, monkeypatch):
    """A listing that failed read as "no archives". The live tail then
    started on the new file while the archive of the old one waited unread,
    and the next pass read that archive from its top, after the newer
    events: #253 saw pass 2 give [4] and pass 3 give [0, 1, 2, 3]."""
    follower = ws.EventFollower()
    for n in range(2):
        ws.append_event({"session_id": "s", "n": n})
    assert [e["n"] for e in follower.new_events()] == [0, 1]
    for n in range(2, 4):
        ws.append_event({"session_id": "s", "n": n})
    assert ws.archive_log(ws.events_path())      # a hook rotates
    ws.append_event({"session_id": "s", "n": 4})
    with monkeypatch.context() as short:
        fail_to_list(ws, short)
        assert list(follower.new_events()) == []
    assert [e["n"] for e in follower.new_events()] == [2, 3, 4]
    assert list(follower.new_events()) == []


def cut_short(ws, monkeypatch) -> None:
    """The next `os.unlink` fails, as if the hook stopped between the link
    and the unlink of a rotation: one file, two names."""
    unlink = ws.os.unlink
    calls: list[int] = []

    def once(path, *args, **kwargs):
        if not calls:
            calls.append(1)
            raise OSError(errno.EIO, "cut short", str(path))
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(ws.os, "unlink", once)


def test_a_rotation_cut_short_is_read_once(ws, monkeypatch):
    """The live file stays under its archive name too, and the next rotation
    gives it a third. Read by name, the running follower read it from its
    top once it saw the archive (#253: [3, 0, 1, 2, 3]), and a start read
    it twice over. The event of the hook that stopped is kept, in the file
    it holds."""
    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 900)
    follower = ws.EventFollower()
    seen: list[int] = []
    written = 0
    cut_short(ws, monkeypatch)
    while len(ws.archived_events_paths()) < 3:
        ws.append_event({"session_id": "s", "n": written, "pad": "x" * 60})
        written += 1
        seen += [e["n"] for e in follower.new_events()]
        assert written < 500
    names = ws.archived_events_paths()
    assert names[0].stat().st_ino == names[1].stat().st_ino, "not cut short"
    seen += [e["n"] for e in follower.new_events()]
    assert seen == list(range(written)), "an event was lost, repeated or moved"
    again = ws.EventFollower()
    assert [e["n"] for e in again.new_events()] == list(range(written))
    assert again.files_read()[0] == 3


def test_a_start_on_a_rotation_cut_short_reads_the_live_file_once(
        ws, monkeypatch):
    """Before the next rotation the one file is the live log and the newest
    archive at once, and the hooks still write to it."""
    for n in range(3):
        ws.append_event({"session_id": "s", "n": n})
    cut_short(ws, monkeypatch)
    assert not ws.archive_log(ws.events_path())
    assert ws.archived_events_paths()
    follower = ws.EventFollower()
    assert [e["n"] for e in follower.new_events()] == [0, 1, 2]
    ws.append_event({"session_id": "s", "n": 3})
    assert [e["n"] for e in follower.new_events()] == [3]
    assert ws.archive_log(ws.events_path())
    ws.append_event({"session_id": "s", "n": 4})
    assert [e["n"] for e in follower.new_events()] == [4]
    assert list(follower.new_events()) == []


def test_an_archive_that_moves_is_not_given_up(ws, monkeypatch):
    """`ARCHIVE_TRIES` counts passes that read nothing. An archive on a slow
    disk that gives a piece and then fails, pass after pass, is moving, and
    it was given up after ten passes all the same, with the rest unread."""
    import builtins

    monkeypatch.setattr(ws, "TAIL_CHUNK", 64, raising=False)
    for n in range(40):
        ws.append_event({"session_id": "s", "n": n, "pad": "x" * 40})
    assert ws.archive_log(ws.events_path())
    ws.append_event({"session_id": "s", "n": 40})
    slow = ws.archived_events_paths()[0]

    class OnePiece:
        """A file that gives one piece a read and fails on the next."""
        def __init__(self, handle):
            self.handle, self.given = handle, False

        def read(self, size):
            if self.given:
                raise OSError(errno.EIO, "slow disk")
            self.given = True
            return self.handle.read(size)

        def __getattr__(self, name):
            return getattr(self.handle, name)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.handle.close()

    def opener(path, *args, **kwargs):
        handle = builtins.open(path, *args, **kwargs)
        return OnePiece(handle) if Path(path) == slow else handle

    monkeypatch.setattr(ws, "open", opener, raising=False)
    follower = ws.EventFollower()
    seen: list[int] = []
    for _ in range(200):
        seen += [e["n"] for e in follower.new_events()]
        if seen and seen[-1] == 40:
            break
    assert seen == list(range(41)), "an archive that moved was given up"


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


def test_a_start_leaves_out_the_archives_older_than_the_window(ws, monkeypatch):
    """Every start folded every archive, because the log is never thrown
    away, so a start grew with the whole history (#430). An archive last
    written before `HISTORY_FOLDED` is left out, by its file's time: by the
    daemon's follower, by `ls` (`read_events`), and said at the start. It
    stays on disk: `measure_log` still counts it, and search still reads
    it. A newer archive and the live file are read, in order."""
    import os
    import time

    monkeypatch.setattr(ws, "EVENTS_MAX_BYTES", 900)
    n = rotate_once(ws, 0)
    n = rotate_once(ws, n)
    old, new = ws.archived_events_paths()
    long_ago = time.time() - ws.HISTORY_FOLDED - 3600
    os.utime(old, (long_ago, long_ago))
    in_old = {json.loads(line)["n"] for line in old.read_text().splitlines()}
    kept = [one["n"] for one in ws.EventFollower().new_events()]
    assert kept == sorted(kept) and kept[-1] == n - 1
    assert not in_old & set(kept) and set(range(n)) - in_old == set(kept)
    assert [one["n"] for one in ws.read_events()] == kept
    assert ws.measure_log()[0] == n
    daemon = ws.Daemon()
    said = daemon.catch_up()
    assert said.endswith(f"left out 1 archive older than {ws.HISTORY_FOLDED // 86400} days"), said
    assert daemon.store.follower.files_read()[0] == 2
    # A day younger than the window, it is read again.
    recent = time.time() - ws.HISTORY_FOLDED + 86400
    os.utime(old, (recent, recent))
    assert [one["n"] for one in ws.EventFollower().new_events()] == list(range(n))
