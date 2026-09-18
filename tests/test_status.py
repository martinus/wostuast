"""The status line: the only place that carries the session name and context."""

from __future__ import annotations

import json


def test_the_recorded_payload_gives_name_model_and_context(ws, recorded_status):
    status = ws.status_from_payload(recorded_status, now=5.0)
    assert status.name == "warmhare"
    assert status.model == "Opus 5"
    assert status.context_pct == 41.0
    assert status.version == "2.1.276"
    assert status.ts == 5.0


def test_a_payload_without_context_gives_none(ws):
    status = ws.status_from_payload({"session_id": "s"}, now=1.0)
    assert status.context_pct is None
    assert status.name == ""


def test_a_payload_with_odd_types_does_not_crash(ws):
    status = ws.status_from_payload({"model": "a string", "context_window": 7}, now=1.0)
    assert status.model == ""
    assert status.context_pct is None


def test_the_agent_name_is_kept(ws):
    status = ws.status_from_payload({"agent": {"name": "code-architect"}}, now=1.0)
    assert status.agent == "code-architect"


def test_write_and_read_round_trip(ws, recorded_status):
    status = ws.status_from_payload(recorded_status, now=5.0)
    ws.write_status("s1", status)
    assert ws.read_status("s1") == status


def test_reading_a_missing_status_gives_an_empty_one(ws):
    assert ws.read_status("nobody") == ws.Status()


def test_a_session_id_never_escapes_the_status_directory(ws):
    ws.write_status("../../evil", ws.Status(ts=1.0, name="x"))
    written = list(ws.status_dir().glob("*.json"))
    assert len(written) == 1
    assert written[0].name == ".._.._evil.json"
    assert "/" not in written[0].name


def test_the_printed_line_is_short_and_plain(ws, recorded_status):
    status = ws.status_from_payload(recorded_status, now=5.0)
    assert ws.status_line(status, "/home/martin/oans/warmhare") == "warmhare · Opus 5 · 41% ctx"


def test_without_a_name_the_line_falls_back_to_the_directory(ws):
    assert ws.status_line(ws.Status(), "/home/martin/oans/warmhare") == "warmhare"


def test_old_status_files_are_dropped(ws):
    ws.write_status("old", ws.Status(ts=1.0))
    ws.write_status("new", ws.Status(ts=1.0))
    target = ws.status_dir() / "old.json"
    import os

    os.utime(target, (0, 0))
    ws.drop_old_status(now=ws.SESSION_MAX_AGE * 2)
    assert not target.exists()
    assert (ws.status_dir() / "new.json").exists()


def test_the_name_becomes_the_session_label(ws):
    session = ws.Session(session_id="s", cwd="/home/martin/oans/warmhare")
    session.git = ws.GitFacts(repo="oans")
    assert session.label == "oans/warmhare"
    session.status = ws.Status(name="warmhare")
    assert session.label == "warmhare"


def test_status_command_stores_the_payload_and_prints_one_line(run_cli, tmp_path,
                                                               recorded_status):
    done = run_cli(["status"], json.dumps(recorded_status))
    assert done.returncode == 0
    assert done.stdout.strip() == "warmhare · Opus 5 · 41% ctx"
    stored = json.loads(
        (tmp_path / "state" / "status" / f"{recorded_status['session_id']}.json").read_text()
    )
    assert stored["context_pct"] == 41.0


def test_status_command_survives_broken_input(run_cli):
    assert run_cli(["status"], "not json").returncode == 0
