"""`tests/where.py`, and the section headers of `wostuast` it reads.

An agent finds its part of the one large file by the section map, and the
rules to read by the brackets at the end of each header. A header that
names a rules file that is gone sends it to read nothing, and a section
that grows to thousands of lines is no longer a place: both are silent,
so these hold them.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import where

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

#: A section longer than this is two parts under one header: an agent
#: reading "its" section reads the other too. Split it by job, with a header
#: of its own, as `diffs` was split into bases and commits.
SECTION_MOST = 900


def test_where_finds_each_kind_of_name_and_its_section():
    """A function, a method, a constant, a page function and a CSS rule,
    each with the header of the section it stands in."""
    out = subprocess.run(
        [sys.executable, str(HERE / "where.py"), "cmd_hook", "Store.refresh",
         "HOOK_PARTS", "putFold", ".row", "no_such_name"],
        capture_output=True, text=True, timeout=60)
    said = out.stdout.splitlines()
    assert out.returncode == 1, "a name that is not defined is an error"
    assert any(line.startswith("cmd_hook  wostuast:") and "the hook:" in line
               for line in said)
    assert any(line.startswith("Store.refresh  wostuast:")
               and "the store:" in line for line in said)
    assert any(line.startswith("HOOK_PARTS  wostuast:") for line in said)
    assert any(line.startswith("putFold  wostuast:")
               and "folding a column" in line for line in said)
    assert any(line.startswith(".row  wostuast:") and "rows:" in line
               for line in said)
    assert "no_such_name: not defined in wostuast" in said


def test_where_prints_the_map_without_a_name():
    out = subprocess.run([sys.executable, str(HERE / "where.py")],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0
    lines = out.stdout.splitlines()
    assert len(lines) == len(where.sections(where.PROGRAM.read_text()))
    assert any("the hook: cmd_hook" in line for line in lines)


def test_every_section_names_rules_files_that_exist():
    """The brackets at a header's end name `topics/<name>` files, or a part
    of CLAUDE.md. A name that is not a file sends an agent to read
    nothing before it edits."""
    found = where.sections(where.PROGRAM.read_text(encoding="utf-8"))
    there = {one.stem for one in (ROOT / ".claude" / "topics").glob("*.md")}
    assert len(found) > 50, "the headers stopped matching"
    gone = [(one.line, name) for one in found for name in one.topics
            if name not in there]
    assert not gone, f"headers name rules files that are gone: {gone}"
    odd = [(one.line, cite) for one in found for cite in one.cites
           if not cite.startswith("CLAUDE.md ")]
    assert not odd, f"a header cites neither topics/ nor CLAUDE.md: {odd}"


def test_no_section_grows_past_the_limit():
    """A section past `SECTION_MOST` lines is split by job, with a header of
    its own, before it grows: the map is only useful while a section is a
    part an agent can read whole."""
    found = where.sections(where.PROGRAM.read_text(encoding="utf-8"))
    over = {one.title: one.end - one.line + 1 for one in found
            if one.end - one.line + 1 > SECTION_MOST}
    assert not over, f"past {SECTION_MOST} lines: {over}"
