"""install and uninstall must leave every foreign setting untouched."""

from __future__ import annotations

import json

import pytest

OURS = "/home/m/.local/bin/wostuast hook"


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
    changes = ws.add_hooks(settings, OURS)
    assert len(changes) == len(ws.HOOK_EVENTS)
    for event in ws.HOOK_EVENTS:
        assert any(ws.has_verb(group, "hook") for group in settings["hooks"][event])


def test_only_the_tool_events_get_a_matcher(ws):
    settings = {}
    ws.add_hooks(settings, OURS)
    for event in ws.HOOK_EVENTS:
        group = settings["hooks"][event][-1]
        assert ("matcher" in group) == (event in ws.MATCHER_EVENTS)


def test_add_hooks_is_idempotent(ws):
    settings = {}
    ws.add_hooks(settings, OURS)
    first = json.dumps(settings, sort_keys=True)
    assert ws.add_hooks(settings, OURS) == []
    assert json.dumps(settings, sort_keys=True) == first


def test_round_trip_keeps_foreign_entries(ws):
    settings = json.loads(json.dumps(FOREIGN))
    ws.add_hooks(settings, OURS)
    ws.remove_hooks(settings)
    assert settings == FOREIGN


def test_remove_hooks_touches_nothing_of_ours_only(ws):
    settings = json.loads(json.dumps(FOREIGN))
    assert ws.remove_hooks(settings) == []
    assert settings == FOREIGN


def test_a_hooks_key_that_is_not_an_object_is_refused(ws):
    with pytest.raises(ValueError):
        ws.add_hooks({"hooks": "nonsense"}, OURS)
    with pytest.raises(ValueError):
        ws.add_hooks({"hooks": {"Stop": "nonsense"}}, OURS)


def test_status_line_is_added_only_when_free(ws):
    settings = {}
    assert ws.add_status_line(settings, "/bin/wostuast status") == ["added status line"]
    assert settings["statusLine"] == {"type": "command", "command": "/bin/wostuast status"}
    assert ws.add_status_line(settings, "/bin/wostuast status") == []


def test_an_existing_status_line_is_kept(ws):
    settings = {"statusLine": {"type": "command", "command": "my-line.sh"}}
    notes = ws.add_status_line(settings, "/bin/wostuast status")
    assert settings["statusLine"]["command"] == "my-line.sh"
    assert notes and "/bin/wostuast status" in notes[0]


def test_remove_status_line_only_removes_ours(ws):
    settings = {"statusLine": {"type": "command", "command": "my-line.sh"}}
    assert ws.remove_status_line(settings) == []
    assert settings["statusLine"]["command"] == "my-line.sh"
    settings["statusLine"] = {"type": "command", "command": "/bin/wostuast status"}
    assert ws.remove_status_line(settings) == ["removed status line"]
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


def test_our_commands_are_matched_by_shape_not_by_string(ws):
    for command in ["wostuast hook", "/home/m/.local/bin/wostuast hook", "./wostuast hook"]:
        assert ws.is_ours(command, "hook")
    assert ws.is_ours("/opt/wostuast status", "status")


def test_nothing_else_is_ours(ws):
    for command in ["my-guard.sh", "wostuast", "wostuast serve", "not-wostuast hook",
                    "wostuast hook --extra", "", None, 7]:
        assert not ws.is_ours(command, "hook")


def test_an_install_from_another_path_is_still_recognised(ws):
    """doctor and uninstall used to miss a checkout install. They must not."""
    settings = {}
    ws.add_hooks(settings, "/home/m/src/wostuast/wostuast hook")
    assert ws.add_hooks(settings, "/home/m/.local/bin/wostuast hook") == []
    assert len(ws.remove_hooks(settings)) == len(ws.HOOK_EVENTS)
    assert "hooks" not in settings


def test_a_compact_file_comes_back_re_indented_but_unchanged(ws):
    """We keep the indent width, not the layout. Inline objects get expanded.

    This is the one way the file is not byte-identical after a round trip, so
    it is pinned here rather than left as a surprise.
    """
    path = ws.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    original = '{\n    "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "mine.sh"}]}]}\n}\n'
    path.write_text(original)

    data, indent, newline = ws.load_settings(path)
    ws.add_hooks(data, OURS)
    ws.remove_hooks(data)
    ws.save_settings(path, data, indent, newline)

    text = path.read_text()
    assert text != original                       # re-indented
    assert json.loads(text) == json.loads(original)  # but nothing was lost
    assert "\n    " in text and "\n  " not in text.replace("\n    ", "")  # 4 spaces kept
