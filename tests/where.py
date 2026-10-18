#!/usr/bin/env python3
"""Where a name of `wostuast` is defined, the section it stands in, and the
rules to read before changing it.

Not a test. The program is one file of five figures of lines, cut into
sections by header lines: `# --- ` in the Python, `/* --- ` in the page's
CSS, `// --- ` in its script. A header says what its section holds and, in
brackets at its end, the rules files of that part:

    # --- the hook: cmd_hook runs on every event ... [topics/safety]

    python3 tests/where.py                 # the map: every section, its line and length
    python3 tests/where.py cmd_hook putFold # where each name is defined, and what to read

A name is found where it is defined: a Python `def`, `class` or assignment
at the start of a line, a method (`refresh`, or `Store.refresh`), or a page
`function`, `const` or `let`. A CSS rule is found by its first selector,
`.row`.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROGRAM = Path(__file__).resolve().parent.parent / "wostuast"

#: A section's header, in any of the three languages of the file.
HEADER = re.compile(r"^(?:# |// |/\* )--- (.*?)(?: \*/)?$")
#: The rules files a header names, in brackets at its end.
TOPICS = re.compile(r"\[([^\]]*)\]$")


@dataclass
class Section:
    """One section of the program: its header and its lines."""

    line: int                     # the header's line, counted from 1
    end: int                      # the last line of the section
    title: str                    # the header, without its marks
    topics: list[str] = field(default_factory=list)  # "safety", ...
    cites: list[str] = field(default_factory=list)   # the rest: CLAUDE.md ...


def sections(text: str) -> list[Section]:
    """Every section of the program, in order."""
    lines = text.split("\n")
    found: list[Section] = []
    for number, line in enumerate(lines, 1):
        header = HEADER.match(line)
        if not header:
            continue
        if found:
            found[-1].end = number - 1
        title = header.group(1)
        named = TOPICS.search(title)
        topics: list[str] = []
        cites: list[str] = []
        if named:
            for one in named.group(1).split(","):
                one = one.strip()
                if one.startswith("topics/"):
                    topics.append(one[len("topics/"):])
                else:
                    cites.append(one)
        found.append(Section(number, number, title, topics, cites))
    if found:
        found[-1].end = len(lines)
    return found


def definitions(text: str, name: str) -> list[int]:
    """The lines that define `name`, counted from 1."""
    if "." in name[1:] and not name.startswith("."):
        owner, method = name.split(".", 1)
        return [line for line in definitions(text, method)
                if text.split("\n")[line - 1].startswith("    ")
                and owner_of(text, line) == owner]
    word = re.escape(name)
    if name.startswith("."):
        pattern = re.compile(rf"^{word}\s*[,{{]")
    else:
        pattern = re.compile(
            rf"^(?:(?:async )?def |class |(?:async )?function\*? |const |let )"
            rf"{word}\b|^{word}(?: *[:=])|^    (?:async )?def {word}\(")
    return [number for number, line in enumerate(text.split("\n"), 1)
            if pattern.match(line)]


def owner_of(text: str, line: int) -> str:
    """The class a method on this line belongs to, or ""."""
    for above in reversed(text.split("\n")[:line - 1]):
        named = re.match(r"^class (\w+)", above)
        if named:
            return named.group(1)
        if re.match(r"^(?:async )?def ", above):
            return ""
    return ""


def section_at(found: list[Section], line: int) -> Section | None:
    """The section that holds this line, or None above the first."""
    return next((one for one in found if one.line <= line <= one.end), None)


def main(argv: list[str]) -> int:
    text = PROGRAM.read_text(encoding="utf-8")
    found = sections(text)
    if not argv:
        for one in found:
            print(f"{one.line:>6} {one.end - one.line + 1:>5}  {one.title}")
        return 0
    missing = 0
    for name in argv:
        lines = definitions(text, name)
        if not lines:
            print(f"{name}: not defined in wostuast")
            missing += 1
        for line in lines:
            where = section_at(found, line)
            title = where.title if where else "(above the first section)"
            print(f"{name}  wostuast:{line}  {title}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
