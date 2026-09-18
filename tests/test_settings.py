"""install and uninstall must leave every foreign setting untouched."""

from __future__ import annotations

import json


FOREIGN = {
    "model": "opus",
    "hooks": {
        "PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "my-guard.sh"}]}
        ],
        "Stop": [{"hooks": [{"type": "command", "command": "my-stop.sh"}]}],
    },
}


def test_add_hooks_registers_every_event(ws):
    settings = {}
    changes = ws.add_hooks(settings, "/bin/wostuast hook")
    assert len(changes) == len(ws.HOOK_EVENTS)
    for event in ws.HOOK_EVENTS:
        groups = settings["hooks"][event]
        assert any(ws.has_command(group, "/bin/wostuast hook") for group in groups)


def test_only_the_tool_events_get_a_matcher(ws):
    settings = {}
    ws.add_hooks(settings, "cmd")
    for event in ws.HOOK_EVENTS:
        group = settings["hooks"][event][-1]
        assert ("matcher" in group) == (event in ws.MATCHER_EVENTS)


def test_add_hooks_is_idempotent(ws):
    settings = {}
    ws.add_hooks(settings, "cmd")
    first = json.dumps(settings, sort_keys=True)
    assert ws.add_hooks(settings, "cmd") == []
    assert json.dumps(settings, sort_keys=True) == first


def test_round_trip_keeps_foreign_entries(ws):
    settings = json.loads(json.dumps(FOREIGN))
    ws.add_hooks(settings, "cmd")
    ws.remove_hooks(settings, ["cmd"])
    assert settings == FOREIGN


def test_remove_hooks_touches_nothing_of_ours_only(ws):
    settings = json.loads(json.dumps(FOREIGN))
    assert ws.remove_hooks(settings, ["cmd"]) == []
    assert settings == FOREIGN


def test_a_hooks_key_that_is_not_an_object_is_refused(ws):
    import pytest

    with pytest.raises(ValueError):
        ws.add_hooks({"hooks": "nonsense"}, "cmd")
    with pytest.raises(ValueError):
        ws.add_hooks({"hooks": {"Stop": "nonsense"}}, "cmd")


def test_status_line_is_added_only_when_free(ws):
    settings = {}
    assert ws.add_status_line(settings, "cmd status") == ["added status line"]
    assert settings["statusLine"] == {"type": "command", "command": "cmd status"}
    assert ws.add_status_line(settings, "cmd status") == []


def test_an_existing_status_line_is_kept(ws):
    settings = {"statusLine": {"type": "command", "command": "my-line.sh"}}
    notes = ws.add_status_line(settings, "cmd status")
    assert settings["statusLine"]["command"] == "my-line.sh"
    assert notes and "cmd status" in notes[0]


def test_remove_status_line_only_removes_ours(ws):
    settings = {"statusLine": {"type": "command", "command": "my-line.sh"}}
    assert ws.remove_status_line(settings, "cmd status") == []
    assert settings["statusLine"]["command"] == "my-line.sh"
    settings["statusLine"] = {"type": "command", "command": "cmd status"}
    assert ws.remove_status_line(settings, "cmd status") == ["removed status line"]
    assert "statusLine" not in settings


def test_indentation_is_detected(ws):
    assert ws.detect_indent('{\n    "a": 1\n}') == 4
    assert ws.detect_indent('{\n  "a": 1\n}') == 2
    assert ws.detect_indent('{\n\t"a": 1\n}') == "\t"
    assert ws.detect_indent('{"a": 1}') == 2


def test_the_file_keeps_its_indentation_and_last_newline(ws):
    path = ws.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{\n    "model": "opus"\n}\n')
    data, indent, newline = ws.load_settings(path)
    ws.add_hooks(data, "cmd")
    ws.save_settings(path, data, indent, newline)
    text = path.read_text()
    assert text.startswith('{\n    "model": "opus",')
    assert text.endswith("}\n")


def test_a_missing_or_empty_file_reads_as_empty(ws):
    path = ws.settings_path()
    assert ws.load_settings(path) == ({}, 2, True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("   \n")
    assert ws.load_settings(path) == ({}, 2, True)


def test_install_and_uninstall_leave_the_file_as_it_was(ws, tmp_path, monkeypatch):
    path = ws.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    original = json.dumps(FOREIGN, indent=2) + "\n"
    path.write_text(original)
    target = tmp_path / "bin" / "wostuast"
    monkeypatch.setattr(ws, "install_path", lambda: target)

    assert ws.cmd_install(None) == 0
    assert target.exists()
    settings = json.loads(path.read_text())
    assert settings["statusLine"]["command"] == f"{target} status"

    assert ws.cmd_uninstall(None) == 0
    assert path.read_text() == original
