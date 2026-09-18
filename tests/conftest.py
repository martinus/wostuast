"""Shared fixtures. Every test gets its own state directory."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
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
