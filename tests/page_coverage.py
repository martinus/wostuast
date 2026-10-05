"""Which parts of the page script no browser test runs (#439), and how much
of it runs at all.

    python3 tests/page_coverage.py [--from DIR] [--lines] [pytest args...]

Not a test. It runs the browser tests -- all of them, or the ones named --
with `WOSTUAST_COVERAGE` set, so that `tests/browser.py` records what
Chromium ran of the page script in each page. Then it merges what every
worker wrote and prints the share of the script's lines that ran, and each
named function that never ran, with its line in `wostuast`. `--from DIR`
reads a folder a run wrote before, and runs nothing. `--lines` prints the
lines that never ran too, as ranges.

Not named `coverage.py`: pytest puts `tests/` on the path, and a file of
that name would stand in for the coverage package for anything that
imports it.

A function on the list is one of two things. Code that nothing calls any
more is dead, and goes: in #431 a break of the `gone` list left every test
green, because nothing used it, and only a perturbation run found that. Code
the program does call is a test nobody wrote.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parent / "wostuast"


def merge(folder: Path) -> dict:
    """Every worker's file in `folder`, as one: the script's text, a set of
    the bytes that ran, and the functions with whether any page ran them.
    Each worker served its own page, and the token in it is the same length
    in each, so the texts are one when their lengths are."""
    text = ""
    ran: set[int] = set()
    functions: dict[int, list] = {}
    for one in sorted(folder.glob("*.json")):
        for held in json.loads(one.read_text()):
            if text and len(held["text"]) != len(text):
                raise SystemExit(f"{one.name}: a page script of another length")
            text = held["text"]
            for start, end in held["ran"]:
                ran.update(range(start, end))
            for start, name, end, did in held["functions"]:
                known = functions.setdefault(start, [name, end, False])
                known[2] = known[2] or did
    return {"text": text, "ran": ran, "functions": functions}


def report(merged: dict, program: str, lines: bool = False) -> list[str]:
    """What `main` prints: the share of the script's lines that ran, each
    named function that never ran with its line in `program`, and with
    `lines` the runs of lines that never ran. A line counts when it holds
    more than space and a `//` comment, and it ran when any of its bytes
    did."""
    text, ran = merged["text"], merged["ran"]
    if not text:
        return ["no page was covered: did any browser test run?"]
    # The script's lines stand where they stand in `wostuast`: the marks
    # the daemon fills in hold no newline.
    first = program.split("\n").index("const state = {") - text.split("\n").index("const state = {")
    counted, missed, at = 0, [], 0
    for number, line in enumerate(text.split("\n")):
        code = line.strip()
        if code and not code.startswith("//"):
            counted += 1
            if not any(at + column in ran for column, char in enumerate(line)
                       if not char.isspace()):
                missed.append(first + number + 1)
        at += len(line) + 1
    out = [f"page script: {counted - len(missed)} of {counted} lines ran "
           f"({100 * (counted - len(missed)) / counted:.1f} %)"]
    # Named where it is written: V8 names an arrow after what holds it, so
    # each of the three arrows in the `PLACE_FIELDS` list was listed as
    # `PLACE_FIELDS`, three times.
    never = sorted((text.count("\n", 0, start) + first + 1, name, text.count("\n", start, end) + 1)
                   for start, (name, end, did) in merged["functions"].items()
                   if name and not did and name in text[text.rfind("\n", 0, start) + 1:
                                                       text.find("\n", start)])
    out.append(f"{len(never)} named functions never ran:")
    out += [f"  wostuast:{line}  {name}  ({length} lines)" for line, name, length in never]
    if lines:
        out.append("lines that never ran:")
        start = None
        for one, after in zip(missed, missed[1:] + [None]):
            start = start or one
            if after != one + 1:
                out.append(f"  wostuast:{start}" + (f"-{one}" if one != start else ""))
                start = None
    return out


def collect(folder: Path, pytest_args: list[str]) -> int:
    """Run the browser tests with coverage recorded into `folder`. Gives
    pytest's exit code: a red test is said, but the report still prints,
    because what the others ran is still true."""
    args = pytest_args or [str(path) for path in sorted(HERE.glob("test_page_*.py"))]
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-n", "auto", "-p", "no:cacheprovider", *args],
        cwd=HERE.parent, env={**os.environ, "WOSTUAST_COVERAGE": str(folder)}).returncode


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--from", dest="source", type=Path,
                        help="read a folder a run wrote before, and run nothing")
    parser.add_argument("--lines", action="store_true",
                        help="print the lines that never ran too")
    known, pytest_args = parser.parse_known_args(argv)
    code = 0
    folder = known.source
    if folder is None:
        folder = Path(tempfile.mkdtemp(prefix="wostuast-coverage-"))
        code = collect(folder, pytest_args)
        print(f"coverage kept in {folder} (--from reads it again)")
    print("\n".join(report(merge(folder), PROGRAM.read_text(), known.lines)))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
