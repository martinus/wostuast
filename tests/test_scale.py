"""`tests/scale.py`, the numbers of how wostuast scales with its history.

It is a tool, not a test, so nothing else runs it: without this it could
stop working, and the first sign would be the next question about speed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from browser import skip_without_browser

HERE = Path(__file__).resolve().parent


@skip_without_browser
def test_it_prints_every_number_for_a_small_history():
    """One line of JSON with every number, the page's redraw among them.
    A push after one event carries one row, so it is smaller than the
    stream's opening, which carries them all (#431)."""
    done = subprocess.run(
        [sys.executable, str(HERE / "scale.py"), "--sessions", "12", "--turns", "2",
         "--page"], capture_output=True, text=True, timeout=180)
    assert done.returncode == 0, done.stderr
    said = json.loads(done.stdout)
    assert said["sessions"] == 12 and said["events"] > 12 * 2
    for key in ("first_fold_s", "quiet_tick_ms", "event_tick_ms", "push_kb",
                "opening_kb", "redraw_ms"):
        assert said[key] >= 0, key
    assert 0 < said["push_kb"] < said["opening_kb"]
