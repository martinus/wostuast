"""The event log: append, read, rotate, and a hook that never fails."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    assert ws.events_path().stat().st_size <= 200 + 200


def test_the_payload_is_kept_whole(ws):
    payload = {"session_id": "s", "hook_event_name": "PostToolUse",
               "tool_response": {"deep": {"list": [1, 2, 3]}}, "brand_new_field": "keep me"}
    ws.append_event(dict(payload, ts=1.0))
    stored = list(ws.read_events())[0]
    assert stored["brand_new_field"] == "keep me"
    assert stored["tool_response"]["deep"]["list"] == [1, 2, 3]


def run_cli(args, stdin, env_dir):
    env = {"PATH": "/usr/bin:/bin", "HOME": str(env_dir),
           "WOSTUAST_STATE": str(env_dir / "state"), "TMUX_PANE": "%3", "NO_COLOR": "1"}
    return subprocess.run([sys.executable, str(ROOT / "wostuast"), *args],
                          input=stdin, capture_output=True, text=True, env=env)


def test_hook_writes_ts_pane_and_pid(tmp_path):
    payload = {"session_id": "s1", "hook_event_name": "Stop", "cwd": "/w"}
    done = run_cli(["hook"], json.dumps(payload), tmp_path)
    assert done.returncode == 0
    line = json.loads((tmp_path / "state" / "events.jsonl").read_text().strip())
    assert line["session_id"] == "s1"
    assert line["pane"] == "%3"
    assert line["pid"] > 0
    assert line["ts"] > 0


def test_hook_exits_zero_on_broken_input(tmp_path):
    done = run_cli(["hook"], "this is not json", tmp_path)
    assert done.returncode == 0
    assert not (tmp_path / "state" / "events.jsonl").exists()


def test_hook_exits_zero_on_empty_input(tmp_path):
    assert run_cli(["hook"], "", tmp_path).returncode == 0


def test_hook_exits_zero_when_the_state_directory_is_a_file(tmp_path):
    (tmp_path / "state").write_text("in the way")
    assert run_cli(["hook"], '{"session_id": "s"}', tmp_path).returncode == 0
