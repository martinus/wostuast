"""`tests/shot.py`, the picture taken first on a report about the page.

It is a tool, not a test, so nothing else runs it: without these it could
stop working and the first sign would be the next layout report.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import shot
from browser import skip_without_browser

HERE = Path(__file__).resolve().parent


def test_the_short_form_reads_as_transcript_records():
    made = shot.parse(
        "you: Do the thing.\n"
        "claude: First the headers.\n"
        "They come before the code.\n"
        "tool: Write /tmp/split.c\n"
        "result: written\n"
        "@ 2026-09-18T14:30:00.000Z\n"
        "think: Now the build.\n"
        "tool: Bash make\n")
    kinds = [(one["type"], one["message"]["content"][0]["type"]
              if isinstance(one["message"]["content"], list) else "prompt")
             for one in made]
    assert kinds == [("user", "prompt"), ("assistant", "text"),
                     ("assistant", "tool_use"), ("user", "tool_result"),
                     ("assistant", "thinking"), ("assistant", "tool_use")]
    # A line with no prefix is the block above it, carried on.
    assert made[1]["message"]["content"][0]["text"] == (
        "First the headers.\nThey come before the code.")
    # A tool's target goes where that tool reads it from.
    write = made[2]["message"]["content"][0]
    assert write["name"] == "Write"
    assert write["input"] == {"file_path": "/tmp/split.c"}
    # A result answers the call above it, and no other.
    assert made[3]["message"]["content"][0]["tool_use_id"] == write["id"]
    assert made[5]["message"]["content"][0]["id"] != write["id"]
    # `@` moves the clock for what comes after it only.
    assert made[3]["timestamp"] != "2026-09-18T14:30:00.000Z"
    assert made[4]["timestamp"] == "2026-09-18T14:30:00.000Z"


@skip_without_browser
def test_it_draws_the_case_and_measures_from_the_text(tmp_path):
    case = tmp_path / "case.txt"
    case.write_text("claude: Now the tests for the split:\n"
                    "tool: Bash ls one\n"
                    "tool: Bash ls two\n"
                    "claude: They pass.\n")
    out = tmp_path / "out.png"
    done = subprocess.run(
        [sys.executable, str(HERE / "shot.py"), str(case), str(out),
         "--measure"],
        capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    rows = [line.split() for line in done.stdout.splitlines()[1:-1]]
    # box, shows, gap, then the block. The reply shows one line and its box
    # is taller, which is the whole reason this measures both.
    words, first, second, reply = rows
    assert int(reply[1]) < int(reply[0]), done.stdout
    # The group sits under the words that announced it.
    assert int(words[2]) < int(second[2]), done.stdout
