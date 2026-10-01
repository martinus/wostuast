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
