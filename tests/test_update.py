"""The version a copy carries (#344), and `install` fetching the newest (#345)."""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time

import pytest

import conftest

#: A commit's time, far from today, so a file that kept the day it was
#: written is told apart from one that took the commit's.
WHEN = 1577880000.0  # 2020-01-01 12:00 UTC
SHA = "0123456789abcdef0123456789abcdef01234567"


def program(extra: str = "") -> str:
    """This checkout's program, with a comment added to make another copy."""
    text = (conftest.ROOT / "wostuast").read_text(encoding="utf-8")
    return text + extra


class Answer(io.BytesIO):
    """What `urlopen` gives back, enough for `newest_program`."""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def opener_for(commits, text: str):
    """An opener that answers the commits URL and the file at `SHA`, and
    keeps every URL it was asked."""
    asked = []

    def opener(url):
        asked.append(url)
        if url == conftest.wostuast.COMMITS_URL:
            return Answer(json.dumps(commits).encode())
        return Answer(text.encode())

    return opener, asked


def a_commit(sha: str = SHA) -> list:
    return [{"sha": sha, "commit": {"committer": {"date": "2020-01-01T12:00:00Z"}}}]


def test_version_is_the_day_and_the_start_of_the_hash(ws, run_cli):
    """No number to raise by hand: `--version` says what the page says."""
    done = run_cli(["--version"])
    assert done.returncode == 0, done.stderr
    assert re.fullmatch(r"wostuast \d{4}-\d\d-\d\d · [0-9a-f]{7}\n", done.stdout), done.stdout
    assert done.stdout == f"wostuast {ws.own_version()}\n"


def test_newest_program_fetches_the_file_at_the_commit_it_names(ws):
    opener, asked = opener_for(a_commit(), program())
    text, when = ws.newest_program(opener)
    assert text == program()
    assert when == WHEN
    # At the SHA, never `main`: raw main is cached for five minutes, and the
    # bytes would then be of another commit than the date.
    assert asked == [ws.COMMITS_URL, ws.RAW_AT.format(SHA)]


@pytest.mark.parametrize("commits, text, error", [
    (a_commit(), "<!doctype html><title>404</title>", ValueError),
    (a_commit(), "#!/usr/bin/env python3\ndef half(:\n", SyntaxError),
    (a_commit("../../evil"), program(), ValueError),
    ([], program(), IndexError),
    ({"message": "API rate limit exceeded"}, program(), KeyError),
])
def test_newest_program_refuses_what_is_not_the_program(ws, commits, text, error):
    opener, asked = opener_for(commits, text)
    with pytest.raises(error):
        ws.newest_program(opener)
    assert all("evil" not in url for url in asked)


def install_where(ws, tmp_path, monkeypatch, newest):
    """Make this the installed copy, with `newest` as GitHub, and keep the
    run that `install` hands over to rather than starting it."""
    target = tmp_path / ".local" / "bin" / "wostuast"
    monkeypatch.setattr(ws, "install_path", lambda: target)
    monkeypatch.setattr(ws, "runs_installed", lambda: True)
    monkeypatch.setattr(ws, "newest_program", newest)
    handed = []

    def execv(path, argv):
        # A real one never returns: what follows it in `cmd_install` must
        # not run either.
        handed.append(argv)
        raise Handed()

    monkeypatch.setattr(ws.os, "execv", execv)
    return target, handed


class Handed(Exception):
    """`install` handed over to the copy it fetched."""


def test_the_installed_copy_fetches_the_newest_and_hands_over_to_it(
        ws, tmp_path, monkeypatch, capsys):
    target, handed = install_where(
        ws, tmp_path, monkeypatch, lambda: (program("# newer\n"), WHEN))
    ws.write_program(target, program())
    old = ws.own_version(target)
    with pytest.raises(Handed):
        ws.cmd_install(argparse_args())
    out = capsys.readouterr().out
    assert target.read_text(encoding="utf-8") == program("# newer\n")
    # The day of the commit, not of the fetch.
    assert os.stat(target).st_mtime == WHEN
    assert f"updated {ws.tilde(target)}: {old} → {ws.own_version(target)}" in out, out
    # The new copy builds its own hooks: the old one stops here.
    assert handed == [[sys.executable, str(target), "install", "--fetched"]]


def test_the_copy_install_hands_over_to_installs_and_never_fetches(tmp_path):
    """What `install` hands over to, run as it is run: the installed copy,
    with `--fetched`. It must exist as an option and stop a second fetch --
    any fetch here fails, through a proxy that is not there."""
    target = tmp_path / ".local" / "bin" / "wostuast"
    conftest.wostuast.write_program(target, program())
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "NO_COLOR": "1",
           "WOSTUAST_STATE": str(tmp_path / "state"),
           "WOSTUAST_CONFIG": str(tmp_path / "config"),
           "CLAUDE_CONFIG_DIR": str(tmp_path / "claude"),
           "https_proxy": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9"}
    done = subprocess.run([sys.executable, str(target), "install", "--fetched"],
                          capture_output=True, text=True, env=env, timeout=60)
    assert done.returncode == 0, done.stderr
    assert "GitHub" not in done.stdout and "newest" not in done.stdout, done.stdout
    settings = json.loads((tmp_path / "claude" / "settings.json").read_text())
    assert settings["hooks"] and settings["statusLine"]


def test_the_newest_already_takes_only_the_commits_day(ws, tmp_path, monkeypatch, capsys):
    target, handed = install_where(ws, tmp_path, monkeypatch, lambda: (program(), WHEN))
    ws.write_program(target, program())
    ws.cmd_install(argparse_args())
    out = capsys.readouterr().out
    assert f"already the newest wostuast: {ws.own_version(target)}" in out, out
    assert ws.own_version(target).startswith("2020-01-0")
    assert handed == []


def test_a_fetch_that_fails_says_why_and_installs_this_copy(
        ws, tmp_path, monkeypatch, capsys):
    def offline():
        raise OSError("<urlopen error [Errno -3]\n Temporary failure in name resolution>")

    target, handed = install_where(ws, tmp_path, monkeypatch, offline)
    assert ws.cmd_install(argparse_args()) == 0
    out = capsys.readouterr().out
    assert ("could not check GitHub for a newer wostuast (<urlopen error [Errno -3]"
            " Temporary failure in name resolution>); installing this one") in out, out
    assert handed == []
    assert target.exists()
    assert ws.hook_path().exists()


def test_a_checkout_installs_itself_and_never_fetches(ws, tmp_path, monkeypatch, capsys):
    """`./wostuast install` in a checkout installs the checkout: a branch
    being tried is not replaced by main."""
    def never():
        raise AssertionError("a checkout fetched")

    monkeypatch.setattr(ws, "newest_program", never)
    assert not ws.runs_installed()
    assert ws.cmd_install(argparse_args()) == 0
    assert "GitHub" not in capsys.readouterr().out
    assert ws.install_path().read_text(encoding="utf-8") == program()


def test_a_link_to_a_checkout_is_not_the_installed_copy(ws, tmp_path, monkeypatch):
    """A link resolves to the checkout, which is this file: the rename
    would put main in the link's place."""
    target = tmp_path / ".local" / "bin" / "wostuast"
    target.parent.mkdir(parents=True)
    target.symlink_to(conftest.ROOT / "wostuast")
    monkeypatch.setattr(ws, "install_path", lambda: target)
    assert not ws.runs_installed()
    target.unlink()
    ws.write_program(target, program())
    monkeypatch.setattr(ws, "__file__", str(target))
    assert ws.runs_installed()


def test_the_one_line_install_hands_over_even_to_the_same_copy(
        ws, tmp_path, monkeypatch, capsys):
    """`python3 -c "$(curl …)" install` has no file: what follows would
    take raw main, cached and maybe older than what was just fetched."""
    target, handed = install_where(ws, tmp_path, monkeypatch, lambda: (program(), WHEN))
    ws.write_program(target, program())
    monkeypatch.delattr(ws, "__file__")
    with pytest.raises(Handed):
        ws.cmd_install(argparse_args())
    assert "already the newest" in capsys.readouterr().out
    assert handed == [[sys.executable, str(target), "install", "--fetched"]]


def argparse_args():
    return conftest.wostuast.build_parser().parse_args(["install"])


def test_the_day_is_the_same_in_every_time_zone(ws, tmp_path, monkeypatch):
    """A commit at 23:30 UTC was the next day in Tokyo, and one copy had
    two versions."""
    late = 1577921400.0  # 2020-01-01 23:30 UTC
    target = tmp_path / "wostuast"
    target.write_text("x")
    os.utime(target, (late, late))
    monkeypatch.setenv("TZ", "Asia/Tokyo")
    time.tzset()
    try:
        assert ws.own_version(target).startswith("2020-01-01 ")
    finally:
        monkeypatch.undo()
        time.tzset()
