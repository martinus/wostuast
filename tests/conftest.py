"""Shared fixtures. Every test gets its own state directory."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load_module():
    """Import the `wostuast` script, which has no .py suffix."""
    loader = importlib.machinery.SourceFileLoader("wostuast", str(ROOT / "wostuast"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


wostuast = _load_module()


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """The module, with its state directory pointed at a temporary path."""
    monkeypatch.setenv("WOSTUAST_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    monkeypatch.setenv("NO_COLOR", "1")
    return wostuast


@pytest.fixture
def recorded_events():
    """The recorded event log, as a list of dicts."""
    lines = (FIXTURES / "events.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@pytest.fixture
def recorded_status():
    return json.loads((FIXTURES / "status.json").read_text())


@pytest.fixture
def run_cli(tmp_path):
    """Run the program as Claude Code would: a fresh process, a bare environment."""

    def run(args, stdin="", home=None):
        root = home or tmp_path
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(root),
            "WOSTUAST_STATE": str(root / "state"),
            "CLAUDE_CONFIG_DIR": str(root / "claude"),
            "TMUX_PANE": "%3",
            "NO_COLOR": "1",
        }
        return subprocess.run(
            [sys.executable, str(ROOT / "wostuast"), *args],
            input=stdin, capture_output=True, text=True, env=env,
        )

    return run


@pytest.fixture
def written_events(ws, recorded_events, monkeypatch):
    """The recorded log on disk, with time and liveness frozen."""
    for event in recorded_events:
        ws.append_event(event)
    monkeypatch.setattr(ws, "SESSION_MAX_AGE", 10**12)
    monkeypatch.setattr(ws, "pid_alive", lambda pid: True)
    return recorded_events


def event(name, sid="s1", **extra):
    """One hook event, with the fields every event carries already filled in."""
    base = {
        "session_id": sid,
        "hook_event_name": name,
        "cwd": extra.pop("cwd", "/w/repo/dir"),
        "pane": "%1",
        "pid": 4242,
        "ts": extra.pop("ts", 1000.0),
    }
    base.update(extra)
    return base


@pytest.fixture
def stub_git(ws, monkeypatch):
    """Answer for git and for liveness, so a test stays about its own subject."""
    monkeypatch.setattr(ws, "git_facts_many", lambda dirs: {
        d: ws.GitFacts(repo="repo", branch="main") for d in dirs})
    monkeypatch.setattr(ws, "pid_alive", lambda pid: True)


@pytest.fixture
def served(ws, stub_git):
    """A daemon on a free port. Yields (daemon, base url)."""
    import threading

    daemon = ws.Daemon()
    server = ws.make_server(daemon, 0)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    daemon.store.refresh()
    try:
        yield daemon, f"http://127.0.0.1:{port}"
    finally:
        daemon.stopping.set()
        server.shutdown()
        server.server_close()


def git_in(cwd, *args):
    """Run one git command in a test repository, and fail loudly if it fails."""
    subprocess.run(["git", "-C", str(cwd), *args], check=True,
                   capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """A repository with one commit on main.

    Several test files need one, so it lives here: git's own facts, the file
    listing, the diff, and the page. Each of them seeds whatever else it needs
    on top.
    """
    root = tmp_path / "myrepo"
    root.mkdir()
    git_in(root, "init", "-q", "-b", "main")
    git_in(root, "config", "user.email", "t@example.com")
    git_in(root, "config", "user.name", "T")
    (root / "README.md").write_text("# readme\n\nhello\n")
    git_in(root, "add", ".")
    git_in(root, "commit", "-qm", "first")
    return root


@pytest.fixture
def transcript_file(ws, tmp_path):
    """A path where a real transcript would be: under the Claude config dir.

    `safe_transcript` refuses anything else, so a test that writes one somewhere
    convenient would be testing a path the daemon will not open.
    """

    def make(name="s1", lines=()):
        folder = ws.settings_path().parent / "projects" / "-w-repo-dir"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{name}.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in lines))
        return path

    return make


# --- the page tests: one browser, and the daemons they drive ------------------
#
# These live here so every page test file gets them. The helpers they are used
# with are in `browser.py`; only the fixtures have to be here.

from browser import HOSTILE, _shared  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _close_the_browser():
    yield
    if _shared:
        play, browser = _shared
        browser.close()
        play.stop()
        _shared.clear()


@pytest.fixture
def page_at(ws, tmp_path, monkeypatch, transcript_file):
    """A daemon with one session whose transcript holds hostile Markdown."""
    monkeypatch.setattr(ws, "git_facts_many", lambda dirs: {
        d: ws.GitFacts(repo="repo", branch="main") for d in dirs})
    monkeypatch.setattr(ws, "pid_alive", lambda pid: True)

    transcript = transcript_file("s1", [
        {"type": "user", "timestamp": "2026-09-18T14:02:00.000Z",
         "message": {"role": "user", "content": "Do the thing."}},
        {"type": "assistant", "timestamp": "2026-09-18T14:03:00.000Z",
         "message": {"role": "assistant",
                     "content": [{"type": "text", "text": HOSTILE}]}},
        {"type": "assistant", "timestamp": "2026-09-18T14:04:00.000Z",
         "message": {"role": "assistant", "content": [
             {"type": "tool_use", "id": "t1", "name": "Bash",
              "input": {"command": "pytest -q"}}]}},
        {"type": "user", "timestamp": "2026-09-18T14:04:05.000Z",
         "message": {"role": "user", "content": [
             {"type": "tool_result", "tool_use_id": "t1",
              "content": "14 passed in 0.31s\nall good"}]}},
    ])
    ws.append_event({"session_id": "s1", "hook_event_name": "SessionStart",
                     "cwd": str(tmp_path), "pane": "%7", "pid": 1,
                     "ts": time.time(), "transcript_path": str(transcript)})
    ws.write_status("s1", ws.Status(ts=1.0, name="A session", model="Opus 5",
                                    context_pct=41.0))

    daemon = ws.Daemon()
    server = ws.make_server(daemon, 0)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    daemon.store.refresh()
    try:
        yield daemon, f"http://127.0.0.1:{port}/"
    finally:
        daemon.stopping.set()
        server.shutdown()
        server.server_close()


@pytest.fixture
def pair_at(ws, page_at, tmp_path):
    """The same daemon with a second session beside the first, so that a filter
    has something to choose between. Two real sessions, not two made up in the
    page: the daemon pushes the list whenever anything changes, and a made-up
    one is gone the moment it does."""
    daemon, url = page_at
    other = tmp_path.parent / "warmhare"
    other.mkdir(exist_ok=True)
    ws.append_event(event("SessionStart", sid="s2", cwd=str(other),
                                   pane="%9", pid=2, ts=time.time()))
    daemon.store.refresh()
    return daemon, url

# --- history: the sessions nobody can talk to any more ------------------------



@pytest.fixture
def past_at(ws, page_at, tmp_path):
    """The one-session page, with two finished sessions beside it."""
    daemon, url = page_at
    for name, reason in (("acorn", "clear"), ("beetroot", "logout")):
        where = tmp_path.parent / name
        where.mkdir(exist_ok=True)
        ws.append_event(event("SessionStart", sid=name, cwd=str(where),
                                       pane="%9", pid=2, ts=time.time()))
        ws.append_event(event("SessionEnd", sid=name, cwd=str(where),
                                       reason=reason, ts=time.time()))
    daemon.store.refresh()
    return daemon, url

# --- the Files tab and the Diff tab ------------------------------------------



@pytest.fixture
def repo_page(ws, served, repo):
    """A session in a real repository: one committed change, one not."""
    git = git_in

    (repo / "README.md").write_text("# The readme\n\nfirst line\n")
    (repo / "code.py").write_text("print(1)\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "seed")
    git(repo, "checkout", "-qb", "side")
    (repo / "code.py").write_text("print(1)\nprint(2)\n")
    git(repo, "commit", "-qam", "second")
    (repo / "README.md").write_text("# The readme\n\nfirst line\nsecond line\n")
    (repo / "NOTES.md").write_text("# Notes\n\n" + HOSTILE)

    daemon, base = served
    ws.append_event(event("SessionStart", cwd=str(repo), ts=time.time(),
                                   pane="%7", pid=1))
    daemon.store.refresh()
    return repo, base


@pytest.fixture(scope="session")
def big_repo(tmp_path_factory):
    """A repository with more files than the old list would send.

    Built once for the whole run: writing 5200 files and committing them costs
    about two seconds, and several tests want it. Every one of them only reads,
    so there is nothing to keep apart.
    """
    git = git_in

    root = tmp_path_factory.mktemp("big")
    (root / "native" / "shared" / "libcorrelation" / "src").mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    for index in range(5200):
        (root / f"f{index:05d}.txt").write_text("x")
    (root / "native" / "shared" / "libcorrelation" / "src" / "Action.h").write_text(
        "// deep\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "first")
    return root


@pytest.fixture
def big_page(ws, served, big_repo):
    """A session standing in that repository."""
    daemon, base = served
    ws.append_event(event("SessionStart", cwd=str(big_repo),
                                   ts=time.time(), pane="%7", pid=1))
    daemon.store.refresh()
    return big_repo, base

# --- the three tmux verbs ---------------------------------------------------



@pytest.fixture
def in_pane(ws, served, tmp_path, monkeypatch, transcript_file):
    """A session in a pane, with tmux replaced by a runner that records.

    The recording lives on the daemon so a test can read what the page asked
    the terminal to do.
    """
    monkeypatch.setattr(ws, "git_facts_many", lambda dirs: {
        d: ws.GitFacts(repo="repo", branch="main") for d in dirs})
    monkeypatch.setattr(ws, "pid_alive", lambda pid: True)
    seen = []

    def runner(args, **rest):
        seen.append(list(args))
        if "capture-pane" in args:
            return "\x1b[1;32mall good\x1b[0m\nwaiting"
        return ""

    monkeypatch.setattr(ws, "run", runner)
    transcript = transcript_file("s1", [
        {"type": "user", "timestamp": "2026-09-18T14:02:00.000Z",
         "message": {"role": "user", "content": "Do the thing."}},
    ])
    daemon, base = served
    ws.append_event({"session_id": "s1", "hook_event_name": "SessionStart",
                     "cwd": str(tmp_path), "pane": "%7", "pid": 1,
                     "ts": time.time(), "transcript_path": str(transcript)})
    daemon.store.refresh()
    return daemon, base, seen


@pytest.fixture
def no_pane(ws, served, tmp_path, monkeypatch):
    """A session that is not running under tmux at all."""
    monkeypatch.setattr(ws, "git_facts_many", lambda dirs: {
        d: ws.GitFacts(repo="repo", branch="main") for d in dirs})
    monkeypatch.setattr(ws, "pid_alive", lambda pid: True)
    daemon, base = served
    ws.append_event({"session_id": "s1", "hook_event_name": "SessionStart",
                     "cwd": str(tmp_path), "pane": "", "pid": 1,
                     "ts": time.time()})
    daemon.store.refresh()
    return daemon, base
