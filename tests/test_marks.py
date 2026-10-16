"""The reader's marks, in one store (#547): names, snoozes, what was seen,
reminders, saved turns. Each test walks every kind, so a sixth mark that
`Marks.load` reads is tested by them as well."""

from __future__ import annotations

import builtins
import io as iomodule
import os
from pathlib import Path

import pytest

from conftest import event

#: Each kind: its file, a way to set it through the store, and how to read
#: it back from a store that was just made, as after a restart.
KINDS = {
    "names": ("names_path",
              lambda store: store.rename("s1", "the payments work"),
              lambda marks: marks.names == {"s1": "the payments work"}),
    "snoozes": ("snoozed_path",
                lambda store: store.snooze("s1", True),
                lambda marks: set(marks.snoozes) == {"s1"}),
    "seen": ("seen_path",
             lambda store: store.see("s1", True),
             lambda marks: set(marks.seen) == {"s1"}),
    "reminders": ("reminders_path",
                  lambda store: store.remind("s1", 5000.0),
                  lambda marks: marks.reminders == {"s1": 5000.0}),
    "saved": ("saved_path",
              lambda store: store.save({"id": "s1", "seq": 2, "ts": 1001.0,
                                        "text": "kept", "at": 1002.0}, True),
              lambda marks: [one["id"] for one in marks.saved] == ["s1"]),
}


def waiting(ws):
    """A store with one session that needs the reader."""
    store = ws.Store()
    store.fold([event("SessionStart", ts=1000.0),
                event("Notification", ts=1001.0,
                      message="Claude needs your permission to use Bash")])
    return store


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_each_mark_survives_a_restart(ws, kind):
    """Set through the store, read back by a new one: the half of each
    mark that a restart of the daemon keeps."""
    _, put, kept = KINDS[kind]
    put(waiting(ws))
    assert kept(ws.Marks.load()), kind


@pytest.mark.parametrize("kind", sorted(KINDS))
@pytest.mark.parametrize("broken", ["{not json", "[1, 2]", '{"x": true}', ""])
def test_a_broken_file_of_each_kind_is_no_marks(ws, kind, broken):
    """A file of ours that is not what it should be is read as none of
    that kind, never raised: the page must come up whatever is on the
    disk."""
    path = getattr(ws, KINDS[kind][0])()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(broken)
    marks = ws.Marks.load()
    assert not getattr(marks, kind), (kind, broken)


def test_a_store_can_be_built_with_no_files(ws, monkeypatch):
    """`Marks()` holds none and reads nothing, so a store made with it
    folds events with no file opened at all (#546, #547)."""
    def refuse(*args, **kwargs):
        raise AssertionError(f"a file was opened: {args[:1]}")
    with monkeypatch.context() as io:
        # `Path.read_text` opens through `io.open`, which patching
        # `builtins.open` does not reach: a read there went unseen.
        for owner, name in [(builtins, "open"), (os, "open"),
                            (iomodule, "open"), (Path, "open"),
                            (Path, "read_text"), (Path, "read_bytes")]:
            io.setattr(owner, name, refuse)
        store = ws.Store(follower=object(), marks=ws.Marks())
        for one in (event("SessionStart", ts=1000.0), event("Stop", ts=1001.0)):
            store.apply(one)
    assert store.sessions["s1"].state == "done"
