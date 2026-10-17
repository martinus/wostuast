"""The fold does no I/O (#546, CLAUDE.md, **Principles**, 1).

`Store.apply` turns one hook event into a change of a session. It ran
`write_names` when a `/clear` or a move to the background took the reader's
name along, the replay at every start included. These fold every kind of
event there is with file, process, subprocess and clock calls made to fail.
A guard sees only the paths it is given, so the second test holds that every
handler and both link paths are among them.
"""

from __future__ import annotations

import builtins
import io as iomodule
import json
import os
import subprocess
import time
from pathlib import Path

from conftest import event
from test_background import FORK, OLD, recorded
from test_state import clear_events

FIXTURES = Path(__file__).parent / "fixtures"


def every_kind_of_event(ws) -> list[dict]:
    """The recorded logs, a `/clear`, a move to the background, and one
    event for each handler in `_HANDLERS`, so a new handler is folded here
    without anyone adding it."""
    events = []
    for path in sorted(FIXTURES.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            try:
                one = json.loads(line)
            except ValueError:
                continue
            if isinstance(one, dict) and one.get("hook_event_name"):
                events.append(one)
    events.append(event("SessionStart", source="startup", ts=1000.0))
    events.extend(clear_events())
    events.extend(recorded())
    events.extend(event(name, sid="every", ts=3000.0) for name in ws._HANDLERS)
    return events


def refuse(name):
    def call(*args, **kwargs):
        raise AssertionError(f"the fold did I/O: {name}{args[:1]}")
    return call


def test_the_fold_does_no_io(ws, monkeypatch):
    """Every event folded with file, process, subprocess and clock calls
    made to fail; the names a `/clear` and a move took along are written
    once the fold is done (`save_names`), and not inside it."""
    events = every_kind_of_event(ws)
    store = ws.Store()
    store.marks.names = {"s1": "the payments work", OLD: "the moved one"}
    # Its own context, so that leaving it undoes only these: a plain
    # `monkeypatch.undo()` undid the `ws` fixture's throwaway home too, and
    # the names were then written into the real state directory.
    with monkeypatch.context() as io:
        # `Path.read_text` opens through `io.open`, which patching
        # `builtins.open` does not reach (#547): `Path` is refused too.
        for owner, name in [(builtins, "open"), (os, "open"), (iomodule, "open"),
                            (Path, "open"), (Path, "read_text"),
                            (Path, "read_bytes"), (os, "replace"),
                            (os, "rename"), (os, "stat"), (os, "kill"),
                            (os, "listdir"), (os, "scandir"), (subprocess, "run"),
                            (subprocess, "Popen"), (time, "time")]:
            io.setattr(owner, name, refuse(name))
        for one in events:
            store.apply(one)
    assert store.marks.names_moved
    assert ws.read_names() == {}, "the fold wrote the names itself"
    store.save_names()
    assert ws.read_names() == {"s2": "the payments work",
                               FORK: "the moved one"}


def test_a_moved_name_that_could_not_be_written_is_written_later(ws, monkeypatch):
    """The fold moves a name in memory and `save_names` writes it after
    (#593). A write that failed -- a full disk -- is tried again by the
    next save, or memory and the file disagree until some other rename,
    and a restart puts the name back where it was."""
    store = ws.Store()
    store.marks.names = {"s2": "the payments work"}
    store.marks.names_moved = True
    real, tries = ws.write_names, []

    def full_once(*args):
        tries.append(args)
        if len(tries) == 1:
            raise OSError("no space left on device")
        real(*args)

    monkeypatch.setattr(ws, "write_names", full_once)
    store.save_names()
    assert ws.read_names() == {}
    store.save_names()
    assert ws.read_names() == {"s2": "the payments work"}
    assert not store.marks.names_moved


def test_the_guard_folds_every_handler_and_both_links(ws):
    """A guard proves nothing about a path it never runs: the fold was clean
    on the recorded logs while the `/clear` that writes was not among them."""
    events = every_kind_of_event(ws)
    assert set(ws._HANDLERS) <= {one["hook_event_name"] for one in events}
    store = ws.Store()
    store.fold(events)
    assert store.sessions["s1"].cleared_into == "s2", "no /clear was joined"
    assert store.sessions[OLD].cleared_into == FORK, "no move was joined"
