"""install and uninstall must leave every foreign setting untouched."""

from __future__ import annotations

import json
import os

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


def test_an_existing_status_line_is_kept_and_a_way_to_have_both_is_given(ws):
    """Claude Code allows one status line, so "add this too" is not a thing the
    user can do. The note has to be a line they can paste."""
    settings = {"statusLine": {"type": "command", "command": "my-line.sh"}}
    notes = ws.add_status_line(settings, "/bin/wostuast status")
    assert settings["statusLine"]["command"] == "my-line.sh"
    joined = "\n".join(notes)
    assert "/bin/wostuast status --then my-line.sh" in joined
    assert "only one" in joined


def test_a_status_line_with_awkward_quoting_is_still_pasteable(ws):
    settings = {"statusLine": {"type": "command",
                               "command": "echo \"it's $PWD\""}}
    notes = ws.add_status_line(settings, "/bin/wostuast status")
    line = [n for n in notes if "--then" in n][0].strip()
    assert line.startswith("/bin/wostuast status --then ")

    # the suggested line must survive a shell
    import shlex
    import subprocess

    parts = shlex.split(line)
    assert parts[:3] == ["/bin/wostuast", "status", "--then"]
    assert subprocess.run(parts[3], shell=True, capture_output=True,
                          text=True).stdout.startswith("it's ")


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
                    "", None, 7]:
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


def test_uninstall_never_deletes_an_empty_key_that_is_not_ours(ws):
    """An empty list the user put there is theirs. Removing nothing must
    change nothing, and must not report a change either."""
    settings = {"model": "opus", "hooks": {"Stop": [], "Other": {}}}
    before = json.dumps(settings, sort_keys=True)
    assert ws.remove_hooks(settings) == []
    assert json.dumps(settings, sort_keys=True) == before


def test_uninstall_leaves_an_empty_hooks_object_alone(ws):
    settings = {"hooks": {}, "model": "x"}
    assert ws.remove_hooks(settings) == []
    assert settings == {"hooks": {}, "model": "x"}


def test_removing_ours_still_tidies_the_key_away(ws):
    settings = {}
    ws.add_hooks(settings, OURS)
    assert ws.remove_hooks(settings)
    assert "hooks" not in settings


def test_uninstall_does_not_create_a_settings_file(ws, capsys):
    """On a machine that never had one, uninstall must not leave `{}` behind."""
    assert not ws.settings_path().exists()
    assert ws.cmd_uninstall(None) == 0
    assert "nothing to change" in capsys.readouterr().out
    assert not ws.settings_path().exists()


def test_uninstall_does_not_rewrite_a_file_it_did_not_change(ws):
    path = ws.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    original = '{"model": "opus", "hooks": {"Stop": [{"hooks": [{"command": "yours.sh"}]}]}}'
    path.write_text(original)
    assert ws.cmd_uninstall(None) == 0
    assert path.read_text() == original      # byte for byte, not even re-indented


def test_an_empty_key_we_added_to_ends_up_removed_not_empty(ws):
    """The one case remove_hooks cannot tell apart, pinned so it stays known.

    Claude Code reads a missing key and an empty list the same way, so this
    costs the user nothing. Any real entry of theirs survives; see the tests
    above.
    """
    settings = {"hooks": {"Stop": []}}
    ws.add_hooks(settings, OURS)
    ws.remove_hooks(settings)
    assert settings.get("hooks", {}).get("Stop") is None


def test_a_real_entry_in_that_same_key_always_survives(ws):
    settings = {"hooks": {"Stop": [{"hooks": [{"command": "mine.sh"}]}]}}
    ws.add_hooks(settings, OURS)
    ws.remove_hooks(settings)
    assert settings["hooks"]["Stop"] == [{"hooks": [{"command": "mine.sh"}]}]


def test_install_does_not_wrap_a_line_it_wrote_itself(ws):
    """Run install, paste the suggested line, run install again: it used to
    offer to wrap its own command in itself."""
    chained = "/home/m/.local/bin/wostuast status --then 'python3 ~/.claude/line.py'"
    settings = {"statusLine": {"type": "command", "command": chained}}
    assert ws.add_status_line(settings, "/home/m/.local/bin/wostuast status") == []
    assert settings["statusLine"]["command"] == chained


def test_a_chained_status_line_is_recognised_as_ours(ws):
    assert ws.is_ours("wostuast status --then 'x'", "status")
    assert ws.is_ours("/home/m/.local/bin/wostuast status --then 'a b c'", "status")
    assert ws.is_ours("wostuast hook", "hook")
    assert not ws.is_ours("wostuast status --then 'x'", "hook")
    assert not ws.is_ours("their-line.sh --then 'x'", "status")


def test_uninstall_removes_a_chained_status_line(ws):
    settings = {"statusLine": {"type": "command",
                               "command": "wostuast status --then 'mine.sh'"}}
    assert ws.remove_status_line(settings) == ["removed status line"]
    assert "statusLine" not in settings


def test_a_path_with_a_space_is_still_quoted(ws, tmp_path, monkeypatch):
    from pathlib import Path

    monkeypatch.setattr(ws, "install_path", lambda: Path("/home/a b/wostuast"))
    settings = {"statusLine": {"type": "command", "command": "mine.sh"}}
    notes = ws.add_status_line(settings, ws.status_command(ws.install_path()))
    line = [n for n in notes if "--then" in n][0].strip()
    assert ws.words_of(line)[:1] == ["/home/a b/wostuast"]


def test_install_leaves_the_settings_file_at_its_own_permissions(ws, tmp_path,
                                                                 monkeypatch):
    """`settings.json` can hold API keys and environment values. It came back
    0644 from a 0600 file, because a fresh temporary takes the umask — and
    `install` promises to touch nothing but our own hooks."""
    import stat

    path = ws.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(FOREIGN, indent=2) + "\n")
    path.chmod(0o600)
    monkeypatch.setattr(ws, "install_path", lambda: tmp_path / "bin" / "wostuast")

    assert ws.cmd_install(None) == 0
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert ws.cmd_uninstall(None) == 0
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_a_settings_file_that_is_a_link_stays_a_link(ws, tmp_path, monkeypatch):
    """Dotfile managers keep `settings.json` as a link into a repository. The
    rename landed on the link itself: after `install` it was a plain file,
    the repository never had the hooks, and an edit made there no longer
    reached Claude Code."""
    kept = tmp_path / "dotfiles" / "settings.json"
    kept.parent.mkdir()
    kept.write_text(json.dumps(FOREIGN, indent=2) + "\n")
    path = ws.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(kept)
    monkeypatch.setattr(ws, "install_path", lambda: tmp_path / "bin" / "wostuast")

    assert ws.cmd_install(None) == 0
    assert path.is_symlink() and path.resolve() == kept.resolve()
    assert "hooks" in json.loads(kept.read_text())
    assert ws.cmd_uninstall(None) == 0
    assert path.is_symlink()
    assert json.loads(kept.read_text()) == FOREIGN
    assert list(path.parent.glob("*.tmp")) == []


def test_the_settings_are_never_on_disk_where_others_can_read_them(
        ws, tmp_path, monkeypatch):
    """The temporary was written first and made 0600 after, so for a moment a
    0644 copy of a file that can hold API keys stood in `~/.claude`, which is
    not private -- and for good, if `install` died in that moment. The mode
    belongs at creation, the rule `open_private` keeps for the state
    directory."""
    import stat

    path = ws.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(FOREIGN, indent=2) + "\n")
    path.chmod(0o600)
    monkeypatch.setattr(ws, "install_path", lambda: tmp_path / "bin" / "wostuast")
    seen = []
    real = os.fsync

    def look(fd):
        # Every temporary holds its whole text by the time it is synced.
        for one in path.parent.glob("*.tmp"):
            seen.append(stat.S_IMODE(one.stat().st_mode))
        return real(fd)

    monkeypatch.setattr(os, "fsync", look)
    monkeypatch.setattr(type(path), "chmod", lambda self, mode: None)
    was = os.umask(0o022)
    try:
        assert ws.cmd_install(None) == 0
    finally:
        os.umask(was)
    assert seen and all(mode & 0o077 == 0 for mode in seen), [oct(m) for m in seen]


def test_uninstall_keeps_an_empty_group_of_the_users(ws):
    """The rule is that a group we took nothing out of is left exactly as it
    was. A group the user left empty was dropped instead — it looked like one
    we had emptied ourselves, and those two are told apart by what was
    removed, not by what is left."""
    settings = {"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [
            {"type": "command", "command": "/home/m/mine.sh"}]},
        {"matcher": "Edit", "hooks": []},
    ]}}
    ws.add_hooks(settings, OURS)
    ws.remove_hooks(settings)
    assert {"matcher": "Edit", "hooks": []} in settings["hooks"]["PreToolUse"]
    assert {"matcher": "Bash", "hooks": [
        {"type": "command", "command": "/home/m/mine.sh"}]} \
        in settings["hooks"]["PreToolUse"]
