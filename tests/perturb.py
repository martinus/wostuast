#!/usr/bin/env python3
"""Break the code on purpose, one break at a time, and say which tests saw it.

Not a test. A test is proven by the change that should make it fail, and
the tests it is about are the only ones worth running for that: the whole
file took 7 to 40 seconds a break, and a fix with nine breaks spent more
time here than on the fix.

    python3 tests/perturb.py breaks.json

`breaks.json` is a list. Each entry is one break:

    {"name": "no lock round the push",          # what the line says
     "file": "wostuast",                        # optional, this is the default
     "old": "exact text, once in the file",
     "new": "what it becomes",
     "tests": ["tests/test_serve.py::test_a_transcript_push_leaves_under_the_lock"]}

`tests` is what pytest is handed: node ids, files, or `-k` and its
expression. Every break is put back before the next one, and on Ctrl-C.
A break is proven when at least one selected test failed. It is not when
all passed, when nothing was selected, or when the old text is not in the
file exactly once. The exit status is 0 only when every break was proven.

`WOSTUAST_WAIT` is 5000 unless it is set already, so a break that makes the
page wait for something that never comes fails in five seconds, not thirty.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def counts(output: str) -> tuple[int, int]:
    """How many failed and how many passed, from pytest's summary line.

    Only that line: a test that prints "3 passed" must not be counted.
    """
    summary = [line for line in output.splitlines()
               if re.search(r"\d+ (passed|failed|errors?)\b.* in [\d.]+s", line)]
    if not summary:
        return 0, 0
    last = summary[-1]
    failed = sum(int(n) for n in re.findall(r"(\d+) (?:failed|errors?)\b", last))
    passed = sum(int(n) for n in re.findall(r"(\d+) passed", last))
    return failed, passed


def one(entry: dict, env: dict) -> tuple[bool, str]:
    """Apply one break, run its tests, put the file back. (proven, line)."""
    path = Path(entry.get("file", "wostuast"))
    was = path.read_bytes()
    text = was.decode("utf-8")
    found = text.count(entry["old"])
    if found != 1:
        return False, f"old text is in {path} {found} times, not once"
    try:
        path.write_bytes(text.replace(entry["old"], entry["new"]).encode("utf-8"))
        ran = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             *entry["tests"]],
            capture_output=True, text=True, env=env)
    finally:
        path.write_bytes(was)
    failed, passed = counts(ran.stdout + ran.stderr)
    if failed:
        return True, f"red    {failed} failed, {passed} passed"
    if not passed:
        return False, "nothing ran: the selection matched no test"
    return False, f"GREEN  {passed} passed -- no test saw this break"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    breaks = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    env = dict(os.environ)
    env.setdefault("WOSTUAST_WAIT", "5000")
    proven = 0
    for index, entry in enumerate(breaks):
        ok, line = one(entry, env)
        proven += ok
        print(f"{index:>2} {entry.get('name', '')[:40]:<40} {line}", flush=True)
    print(f"{proven} of {len(breaks)} breaks proven")
    return 0 if proven == len(breaks) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
