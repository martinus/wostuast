"""`tests/stage.py`, the picture taken first on a report about the Files or
the Review tab.

It is a tool, not a test, so nothing else runs it: without these it could
stop working and the first sign would be the next report about either tab.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import stage
from browser import skip_without_browser

HERE = Path(__file__).resolve().parent


def test_the_tools_write_nothing_outside_their_own_home(tmp_path, monkeypatch):
    """`stage.serve`, `shot.serve` and `tour.make_sessions`, called by a
    script rather than by their `main`, keep to the home they are given: a
    script that called `stage.serve` by itself wrote the command fixtures
    into the real `~/.claude`. The environment is set through `monkeypatch`
    first, so this test leaves it as it found it."""
    import shot
    import tour
    from conftest import wostuast as ws

    real = tmp_path / "real"
    monkeypatch.setattr(ws, "git_facts_many", ws.git_facts_many)
    monkeypatch.setattr(ws, "pid_alive", ws.pid_alive)
    for name, write in (
            ("stage", lambda home: stage.serve(home, commands=True)),
            ("shot", lambda home: shot.serve("", home)),
            ("tour", lambda home: tour.make_sessions(ws, home))):
        # Pointed at "the reader's own" before each tool: the one before it
        # has pointed them at its own home, which would hide this one.
        for key, where in (("WOSTUAST_STATE", "state"), ("WOSTUAST_CONFIG", "config"),
                           ("CLAUDE_CONFIG_DIR", "claude"), ("TMUX", "tmux")):
            monkeypatch.setenv(key, str(real / where))
        (tmp_path / name).mkdir()         # as `mkdtemp` gives each `main` one
        write(tmp_path / name)
        assert not real.exists(), (name, sorted(str(one) for one in real.rglob("*")))
    assert (tmp_path / "stage" / "claude" / "skills" / "notes" / "SKILL.md").is_file()


def test_the_repository_has_what_the_pictures_need(tmp_path):
    repo = tmp_path / "proj"
    stage.make_repo(repo)
    run = lambda *args: subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True,
        check=True).stdout
    # Four commits on the branch, the oldest first as "N / 4" counts them,
    # and the second is the one with Markdown in its message.
    subjects = run("log", "--reverse", "--format=%s", "main..feature").split("\n")[:-1]
    assert subjects == [one.split("\n")[0] for one in stage.MESSAGES]
    assert "**refuses**" in run("log", "-1", "--format=%b", "feature~2")
    # A change not committed, and a document nobody committed.
    assert run("status", "--porcelain").split("\n")[:-1] == [" M ring.c", "?? PLAN.md"]
    # Every comment but the last is on a line the branch added, by number:
    # the hunk headers say which lines are new.
    import re
    added = set()
    for start, count in re.findall(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@",
                                   run("diff", "main...feature", "--unified=0"),
                                   re.M):
        added.update(range(int(start), int(start) + int(count or 1)))
    assert set(stage.LINES[:-1]) <= added, sorted(added)
    assert stage.LINES[-1] not in added


@skip_without_browser
def test_it_draws_a_commit_with_a_review_and_a_click(tmp_path):
    out = tmp_path / "out.png"
    done = subprocess.run(
        [sys.executable, str(HERE / "stage.py"), str(out), "--commit", "2",
         "--review", "--click", ".diffhead .readas button[data-value='true']",
         "--part", ".diffhead.commit"],
        capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@skip_without_browser
def test_it_draws_a_file_on_the_files_tab(tmp_path):
    """Not PLAN.md, which the tab opens by itself."""
    out = tmp_path / "out.png"
    done = subprocess.run(
        [sys.executable, str(HERE / "stage.py"), str(out), "--tab", "files",
         "--open", "ring.c", "--part", ".filebody"],
        capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@skip_without_browser
def test_it_draws_the_settings_menu_from_a_file_and_steps(tmp_path):
    """The settings menu, from a `settings.json` made for it, with a link
    typed in and something drawn by `--eval`: the three things a session
    wrote a script of its own for, three times, and lost with the scratchpad."""
    out = tmp_path / "out.png"
    links = '{"links": [{"match": "OA-(\\\\d+)", "url": "https://t.example/$1"}]}'
    done = subprocess.run(
        [sys.executable, str(HERE / "stage.py"), str(out), "--tab", "transcript",
         "--settings", links, "--click", "#settings",
         "--click", "#setpop .linkadd",
         "--type", "#linklist .linkrow:last-child .linkmatch=BUG-(",
         "--eval", "document.querySelector('#setpop').dataset.staged = 'yes'",
         "--part", "#setpop[data-staged='yes'] #linklist .linkrow:first-child"],
        capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@skip_without_browser
def test_it_draws_the_slash_command_list(tmp_path):
    """`--commands` stages skills and used commands, and `--keys` types into
    the box without the Enter `--type` adds, which would take a command."""
    out = tmp_path / "out.png"
    done = subprocess.run(
        [sys.executable, str(HERE / "stage.py"), str(out), "--tab", "transcript",
         "--commands", "--keys", "#say=/re",
         # The list opens when its fetch answers, after the keys.
         "--eval", "new Promise((done, failed) => { const until = Date.now() + 15000;"
                   " const look = () => !$('slash').hidden ? done()"
                   " : Date.now() > until ? failed(new Error('the list did not open'))"
                   " : setTimeout(look, 20); look(); })",
         "--part", "#slash"],
        capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@skip_without_browser
def test_it_types_into_no_real_tmux(tmp_path):
    """Its session stands in pane `%7`, and a step that sends types into
    it. Run from inside the reader's tmux, that was their own `%7` (#351).
    Here a tmux of its own has a `%7`, `TMUX` names it, and nothing may
    arrive there."""
    import os
    import shutil
    import time

    import pytest

    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")
    name = f"stage-{os.getpid()}-{time.monotonic_ns()}"
    tmux = lambda *args: subprocess.run(
        ["tmux", "-L", name, *args], capture_output=True, text=True,
        timeout=10).stdout.strip()
    tmux("-f", "/dev/null", "new-session", "-d", "cat")
    try:
        for _ in range(7):
            tmux("new-window", "cat")
        assert "%7" in tmux("list-panes", "-a", "-F", "#{pane_id}").split()
        env = dict(os.environ, TMUX=tmux("display-message", "-p",
                                          "#{socket_path}") + ",0,0")
        done = subprocess.run(
            [sys.executable, str(HERE / "stage.py"), str(tmp_path / "out.png"),
             "--tab", "transcript", "--type", "#say=hello from stage"],
            capture_output=True, text=True, timeout=120, env=env)
        assert done.returncode == 0, done.stderr
        time.sleep(0.5)
        assert "hello from stage" not in tmux("capture-pane", "-p", "-t", "%7")
    finally:
        tmux("kill-server")
