"""`tests/tour.py`, the picture of the whole page in every state the
sidebar knows.

It is a tool, not a test, so nothing else runs it: without this it could
stop working, and the first sign would be the next design question.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from browser import skip_without_browser

HERE = Path(__file__).resolve().parent


@skip_without_browser
def test_it_draws_the_views_it_is_asked_for_with_the_eval_run(tmp_path):
    """Two views of the six, in the light, with a mockup's `--eval` run
    before each: a class it sets is in the page when the picture is taken,
    and only the views named are drawn."""
    done = subprocess.run(
        [sys.executable, str(HERE / "tour.py"), str(tmp_path), "--light",
         "--width", "1200", "--height", "800", "--view", "transcript",
         "--view", "unread", "--eval",
         "if (!document.querySelector('.feedentry, .turn.plan')) throw new Error('not drawn')"],
        capture_output=True, text=True, timeout=180)
    assert done.returncode == 0, done.stderr
    drawn = sorted(path.name for path in tmp_path.iterdir())
    assert drawn == ["light-1200-1-transcript.png", "light-1200-3-unread.png"], drawn
    for name in drawn:
        assert (tmp_path / name).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@skip_without_browser
def test_an_eval_that_throws_stops_the_tour(tmp_path):
    """The eval runs in the page: one that throws is the tour's error. A
    tour that left it out would draw a mockup without the mockup."""
    done = subprocess.run(
        [sys.executable, str(HERE / "tour.py"), str(tmp_path), "--view", "transcript",
         "--eval", "throw new Error('the mockup ran')"],
        capture_output=True, text=True, timeout=180)
    assert done.returncode != 0
    assert "the mockup ran" in done.stderr
