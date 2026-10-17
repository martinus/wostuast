"""Which parts of the page script no browser test runs (#439), and how much
of it runs at all.

    python3 tests/page_coverage.py [--from DIR] [--lines] [--check] [pytest args...]

Not a test. It runs the browser tests -- all of them, or the ones named --
with `WOSTUAST_COVERAGE` set, so that `tests/browser.py` records what
Chromium ran of the page script in each page. Then it merges what every
worker wrote and prints the share of the script's lines that ran, and each
named function that never ran, with its line in `wostuast`. `--from DIR`
reads a folder a run wrote before, and runs nothing. `--lines` prints the
lines that never ran too, as ranges. `--check` fails on a named function
that never ran and is not in `UNRUN_ALREADY` (#579), and on one whose lines
that never ran are more than `UNRUN_LINES_ALREADY` allows it (#600): CI's
`browser` job runs it over what the four shards recorded.

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

#: Named page functions no browser test runs, each with why (#579). It
#: was empty when the check was written: the three the first run found
#: (#439) each have a test. A function on it is dead code to delete or a
#: test to write. May only get shorter (CLAUDE.md, the ratchet).
UNRUN_ALREADY: frozenset[str] = frozenset()

#: How many lines of a function no browser test runs, at most (#600). A
#: function that ran is not all run: `drawDiff` ran in every Review tab
#: test while a write in it, behind an `if` no test took, stood unseen
#: (#596). So the lines are counted too, each for the innermost named
#: function that holds it, or for `(top level)`. A function not here may
#: have none. Each entry is the most that three runs of the whole suite
#: left unrun, and says why: a line that runs or not by the timing of the
#: run, never a branch no test was written for. May only get smaller.
#: It was empty when the check was written: once #600's tests were in,
#: three runs of the whole suite left one line unrun, a branch of
#: `drawBell` that has a test now.
UNRUN_LINES_ALREADY: dict[str, int] = {}
TOP_LEVEL = "(top level)"


def merge(folder: Path) -> dict:
    """Every worker's file in `folder`, as one: the script's text, a set of
    the bytes that ran, and the functions with whether any page ran them.
    Each worker served its own page, and the token in it is the same length
    in each, so the texts are one when their lengths are."""
    text = ""
    ran: set[int] = set()
    functions: dict[int, list] = {}
    # Each shard's files are in a folder of their own: a file is named
    # after its process, and two runners can give two processes one number.
    for one in sorted(folder.rglob("*.json")):
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
    if not merged["text"]:
        return ["no page was covered: did any browser test run?"]
    first = first_line(merged, program)
    counted, missed = lines_unrun(merged)
    missed = [first + number + 1 for number in missed]
    out = [f"page script: {counted - len(missed)} of {counted} lines ran "
           f"({100 * (counted - len(missed)) / counted:.1f} %)"]
    never = never_ran(merged, first)
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


def first_line(merged: dict, program: str) -> int:
    """The line of `wostuast` before the script's first. The script's
    lines stand where they stand in `wostuast`: the marks the daemon fills
    in hold no newline."""
    text = merged["text"]
    return (program.split("\n").index("const state = {")
            - text.split("\n").index("const state = {"))


def lines_unrun(merged: dict) -> tuple[int, list[int]]:
    """How many of the script's lines count, and which of them never ran,
    from 0. A line counts when it holds more than space and a `//`
    comment, and it ran when any of its bytes did."""
    ran = merged["ran"]
    counted, missed, at = 0, [], 0
    for number, line in enumerate(merged["text"].split("\n")):
        code = line.strip()
        if code and not code.startswith("//"):
            counted += 1
            if not any(at + column in ran for column, char in enumerate(line)
                       if not char.isspace()):
                missed.append(number)
        at += len(line) + 1
    return counted, missed


def named_functions(merged: dict) -> list[tuple[int, int, str, bool]]:
    """Each named function as its first and last line, from 0, its name,
    and whether any page ran it. Named where it is written: V8 names an
    arrow after what holds it, so each of the three arrows in the
    `PLACE_FIELDS` list was listed as `PLACE_FIELDS`, three times."""
    text = merged["text"]
    return [(text.count("\n", 0, start), text.count("\n", 0, end), name, did)
            for start, (name, end, did) in merged["functions"].items()
            if name and name in text[text.rfind("\n", 0, start) + 1:text.find("\n", start)]]


def unrun_by_function(merged: dict) -> dict[str, list[int]]:
    """The lines no page ran, from 0, by the innermost named function that
    holds each: a handler written inside a function is that function's.
    A line in no named function is `TOP_LEVEL`'s."""
    spans = sorted(named_functions(merged), key=lambda one: one[1] - one[0])
    out: dict[str, list[int]] = {}
    for line in lines_unrun(merged)[1]:
        name = next((name for start, end, name, _did in spans if start <= line <= end),
                    TOP_LEVEL)
        out.setdefault(name, []).append(line)
    return out


def never_ran(merged: dict, first: int) -> list[tuple[int, str, int]]:
    """Each named function no page ran: its line in `wostuast`, counting
    the script's first line as `first`, its name, and how long it is."""
    return sorted((start + first + 1, name, end - start + 1)
                  for start, end, name, did in named_functions(merged) if not did)


def check(merged: dict, program: str = "") -> list[str]:
    """What `--check` fails on, a line each; nothing when the ratchet holds.
    A run that recorded nothing fails too: a shard that uploaded no file
    would otherwise pass with every function unseen. A function that never
    ran is said once, as one, and not again for its lines. With `program`,
    a line is named by its line in it, which is how CI's log says where."""
    if not merged["text"]:
        return ["no page was covered: did any browser test run?"]
    unrun = {name for _line, name, _length in never_ran(merged, 0)}
    out = [f"{name}: no browser test runs it, and it is not in UNRUN_ALREADY"
           for name in sorted(unrun - UNRUN_ALREADY)]
    out += [f"{name}: a test runs it now, so it comes off UNRUN_ALREADY"
            for name in sorted(UNRUN_ALREADY - unrun)]
    first = first_line(merged, program) if program else 0
    for name, lines in sorted(unrun_by_function(merged).items()):
        allowed = UNRUN_LINES_ALREADY.get(name, 0)
        if name not in unrun and len(lines) > allowed:
            where = ", ".join(f"wostuast:{first + line + 1}" for line in lines)
            out.append(f"{name}: {len(lines)} lines no browser test runs, and"
                       f" UNRUN_LINES_ALREADY allows {allowed}: {where}")
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
    parser.add_argument("--check", action="store_true",
                        help="fail on a function no test runs that UNRUN_ALREADY does not hold")
    known, pytest_args = parser.parse_known_args(argv)
    code = 0
    folder = known.source
    if folder is None:
        folder = Path(tempfile.mkdtemp(prefix="wostuast-coverage-"))
        code = collect(folder, pytest_args)
        print(f"coverage kept in {folder} (--from reads it again)")
    merged = merge(folder)
    print("\n".join(report(merged, PROGRAM.read_text(), known.lines)))
    if known.check and (failed := check(merged, PROGRAM.read_text())):
        print("\n".join(failed))
        return 1
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
