"""What one turn changed (#749): the worktree as it was when each turn
began, kept as a tree in wostuast's own git store, and offered on the
Review tab as a base. The diff from a turn's start to the files now is
"since turn N"; the newest start is "this turn".

The reader chose the store: nothing is written into the repository, no
ref, no object, no index. And the daemon, not the hook, takes the
snapshot: the hook stays free of git, and a turn that runs while no daemon
does has none.
"""

from __future__ import annotations

import os
import subprocess
import time

import pytest

from conftest import bare_event, event, git_in
from test_serve import get


def git_state(root):
    """What the repository holds of its own, to show nothing was written:
    its refs, its objects and its index."""
    def out(*args):
        return subprocess.run(["git", "-C", str(root), *args], check=True,
                              capture_output=True, text=True).stdout
    index = (root / ".git" / "index").read_bytes()
    return out("for-each-ref"), out("count-objects", "-v"), index


@pytest.fixture
def turned(ws, served, repo):
    """A session in a real repository whose turn began just now, and the
    tick that keeps its start."""
    daemon, base = served
    now = time.time()
    ws.append_event(event("SessionStart", cwd=str(repo), ts=now - 5))
    ws.append_event(event("UserPromptSubmit", cwd=str(repo), prompt="Fix the cache race",
                          ts=now))
    daemon.store.refresh()
    before = git_state(repo)
    daemon.tick()
    return daemon, base, repo, f"turn:{now:.6f}", before


def test_a_turn_start_is_kept_and_nothing_is_written_into_the_repository(ws, turned):
    daemon, base, repo, key, before = turned
    starts = daemon.store.sessions["s1"].turn_starts
    assert [(one.key, one.n, one.said, one.root) for one in starts] == \
        [(key.removeprefix("turn:"), 1, "Fix the cache race", str(repo))]
    assert ws.TREE_SHAPE.fullmatch(starts[0].tree)
    recorded = [one for one in ws.read_events() if one.get("hook_event_name") == "Snapshot"]
    assert len(recorded) == 1
    assert git_state(repo) == before, "the snapshot wrote into the repository"
    # Seeded from the worktree's index, and reading the repository's own
    # objects: a clean worktree's tree is the commit's, and nothing is copied.
    kept = [one for one in (ws.snapshot_home("s1") / "objects").rglob("*") if one.is_file()]
    assert kept == []
    # One a turn: the next tick takes none again.
    daemon.tick()
    assert len([one for one in ws.read_events()
                if one.get("hook_event_name") == "Snapshot"]) == 1


def test_since_a_turn_shows_what_changed_since_untracked_files_too(ws, turned):
    """One half, to the files on disk now: a changed file and one git does
    not track yet. The picker lists the turn, and the branches beside it."""
    daemon, base, repo, key, _ = turned
    (repo / "README.md").write_text("# readme\n\nhello, again\n")
    (repo / "notes.md").write_text("new\n")
    before = git_state(repo)
    status, body = get(f"{base}/api/session/s1/diff?base={key}")
    assert status == 200
    assert body["turn"] == key and body["base"] == "the start of this turn"
    assert body["turns"] == [{"key": key, "label": "the start of this turn"}]
    assert [one["name"] for one in body["sections"]] == ["turn"]
    assert body["sections"][0]["at_commit"] is False
    files = {one["path"]: one["status"] for one in body["sections"][0]["files"]}
    assert files == {"README.md": "modified", "notes.md": "added"}
    assert git_state(repo) == before, "the diff wrote into the repository"
    # A file the turn found is not in it: it was there when the turn began.
    whole = get(f"{base}/api/session/s1/whole?section=turn&base={key}&path=README.md")[1]
    assert [line["text"] for line in whole["file"]["hunks"][0]["lines"]] == \
        ["# readme", "", "hello", "hello, again"]
    # Without the pick it is the branch's diff, and the turn is still offered.
    _, plain = get(f"{base}/api/session/s1/diff")
    assert plain["turn"] == "" and plain["turns"] == body["turns"]
    assert [one["name"] for one in plain["sections"]] == ["committed", "uncommitted"]


def test_a_turn_nobody_kept_is_no_base(ws, turned):
    """The page's word is a key to look up, never a tree: another key is a
    branch nobody has, and the branch's diff comes."""
    daemon, base, repo, key, _ = turned
    _, body = get(f"{base}/api/session/s1/diff?base=turn:1.000000")
    assert body["turn"] == ""
    assert [one["name"] for one in body["sections"]] == ["committed", "uncommitted"]


def test_a_turn_that_began_long_ago_gets_no_snapshot(ws, served, repo):
    """A daemon that starts later folds old turns, and the worktree has
    moved on since: a snapshot then would be of another moment."""
    daemon, base = served
    then = time.time() - ws.SNAPSHOT_LATE - 5
    ws.append_event(event("SessionStart", cwd=str(repo), ts=then - 5))
    ws.append_event(event("UserPromptSubmit", cwd=str(repo), prompt="go", ts=then))
    daemon.tick()
    assert daemon.store.sessions["s1"].turn_starts == []


def test_a_snapshot_is_kept_only_for_the_turn_it_names(ws):
    """Written late, for a turn another has followed, it is of another
    moment, and the newer turn is not given it."""
    tree = "a" * 40
    events = [event("SessionStart", ts=1.0),
              event("UserPromptSubmit", prompt="first", ts=2.0),
              event("UserPromptSubmit", prompt="second", ts=3.0),
              # The daemon's own record, as `take_snapshots` writes it: no pane.
              bare_event("Snapshot", ts=4.0, turn="2.000000", tree=tree, root="/w"),
              bare_event("Snapshot", ts=4.5, turn="3.000000", tree="not a tree", root="/w")]
    assert ws.build_sessions(events, now=5)[0].turn_starts == []
    events.append(bare_event("Snapshot", ts=5.0, turn="3.000000", tree=tree, root="/w"))
    started = ws.build_sessions(events, now=6)[0].turn_starts
    assert [(one.n, one.said) for one in started] == [(2, "second")]


def test_an_older_turn_is_named_by_its_number_and_its_prompt(ws):
    session = ws.Session(session_id="s1", state="done", turn_key="2.000000")
    first = ws.TurnStart(key="1.000000", n=1, said="Add search", tree="a" * 40, root="/w")
    last = ws.TurnStart(key="2.000000", n=2, said="Fix it", tree="b" * 40, root="/w")
    session.turn_starts = [first, last]
    assert ws.turn_bases(session, "/w") == [
        {"key": "turn:2.000000", "label": "the start of the last turn"},
        {"key": "turn:1.000000", "label": "the start of turn 1 · Add search"}]
    assert ws.turn_bases(session, "/elsewhere") == []


def test_a_snapshot_folder_nothing_wrote_for_two_weeks_goes(ws):
    old, new = ws.snapshots_dir() / "old", ws.snapshots_dir() / "new"
    for one in (old, new):
        one.mkdir(parents=True)
    then = time.time() - ws.SNAPSHOT_KEPT - 60
    os.utime(old, (then, then))
    ws.prune_snapshots(time.time())
    assert not old.exists() and new.exists()


def test_a_snapshot_survives_a_blob_the_repository_dropped(ws, repo):
    """The kept index names blobs by their stat data, and the repository's gc
    may drop one no commit holds: `write-tree` then fails, and the index is
    made again from nothing, once."""
    (repo / "loose.txt").write_text("staged once\n")
    # An hour old, so its index entry is trusted on its stat alone: written
    # in the same second as the index, git hashes it again ("racily clean"),
    # and the dropped blob is written anew without any second try.
    then = time.time() - 3600
    os.utime(repo / "loose.txt", (then, then))
    git_in(repo, "add", "loose.txt")
    assert ws.take_snapshot(str(repo), "s1")
    git_in(repo, "rm", "-q", "--cached", "loose.txt")
    git_in(repo, "prune", "--expire=now")
    again = ws.take_snapshot(str(repo), "s1")
    assert again and ws.TREE_SHAPE.fullmatch(again)
    env = ws.snapshot_env(str(repo), ws.snapshot_home("s1"), ws.run)
    listed = ws.run(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", again], env=env)
    assert listed.split() == ["README.md", "loose.txt"]
