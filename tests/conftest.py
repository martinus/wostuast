"""Shared fixtures. Every test gets its own state directory."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
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
