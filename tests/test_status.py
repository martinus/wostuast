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


def test_the_label_shows_the_name_and_the_worktree(ws):
    """With several agents running, the name alone does not say where one is."""
    session = ws.Session(session_id="s", cwd="/home/martin/oans/warmhare")
    session.git = ws.GitFacts(repo="oans")
    assert session.label == "oans/warmhare"
    session.status = ws.Status(name="List files in home")
    assert session.label == "List files in home · oans/warmhare"


def test_a_very_long_title_is_cut(ws):
    session = ws.Session(session_id="s", cwd="/w/dir")
    session.status = ws.Status(name="x" * 200)
    name, _, place = session.label.partition(" · ")
    assert len(name) == 40
    assert place == "dir"


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


def test_the_status_line_can_run_the_one_you_already_had(run_cli, recorded_status):
    """Claude Code allows one status line and the payload can only be read
    once, so chaining is the only way to keep both."""
    done = run_cli(["status", "--then", "cat | wc -c"], json.dumps(recorded_status))
    assert done.returncode == 0
    assert done.stdout.strip().isdigit(), done.stdout
    assert int(done.stdout.strip()) == len(json.dumps(recorded_status))


def test_the_chained_line_still_gets_the_payload(run_cli, recorded_status, tmp_path):
    done = run_cli(["status", "--then",
                    "python3 -c \"import sys,json; print(json.load(sys.stdin)['session_name'])\""],
                   json.dumps(recorded_status))
    assert done.stdout.strip() == "warmhare"


def test_we_still_record_the_session_when_chaining(run_cli, tmp_path, recorded_status):
    run_cli(["status", "--then", "echo mine"], json.dumps(recorded_status))
    stored = json.loads(
        (tmp_path / "state" / "status" / f"{recorded_status['session_id']}.json").read_text())
    assert stored["name"] == "warmhare"
    assert stored["context_pct"] == 41.0


def test_a_chained_line_that_fails_prints_nothing_and_still_exits_zero(run_cli,
                                                                      recorded_status):
    done = run_cli(["status", "--then", "exit 3"], json.dumps(recorded_status))
    assert done.returncode == 0
    assert done.stdout == ""


def test_a_chained_line_that_is_not_a_command_does_not_crash(run_cli, recorded_status):
    done = run_cli(["status", "--then", "definitely-not-here --x"],
                   json.dumps(recorded_status))
    assert done.returncode == 0
