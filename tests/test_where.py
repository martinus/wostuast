"""`tests/where.py`, and the section headers of `wostuast` it reads.

An agent finds its part of the one large file by the section map, and the
rules to read by the brackets at the end of each header. A header that
names a rules file that is gone sends it to read nothing, and a section
that grows to thousands of lines is no longer a place: both are silent,
so these hold them.
"""

from __future__ import annotations

import ast
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


#: Principle 1, data flows one way, as layers of the program's sections,
#: from the bottom up. A section uses names of its own layer and of the
#: layers below it, never of one above: a use upward is a helper in the
#: wrong section, or a part that reaches into the part that drives it.
#: A section is named by its header up to the colon.
LAYERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # What every part may use: limits, the files wostuast keeps, the event
    # log and how it is followed, a path checked, text for a person.
    ("base", ("constants", "state directory", "text log", "event log",
              "following files", "paths from outside", "output helpers")),
    # The shapes the fold fills.
    ("model", ("session model", "one-line summaries", "questions and plans")),
    # Where a file, git or tmux is read or written: the fold does none of
    # it (topics/principles, 1).
    ("edges", ("the hook's Yes", "transcript", "git facts", "worktree files",
               "reading a file", "diffs", "bases", "commits and the build",
               "status line", "our settings.json", "the reader's marks",
               "Claude Code's settings.json", "tmux", "slash commands",
               "install and update")),
    # What an event does to a session. `processes` reads /proc, but folds
    # a death (`_bury`); `search` reads a prompt as the fold does
    # (`prompt_said`, principle 5).
    ("fold", ("processes", "hook handlers", "time", "search")),
    # Every shape the page receives (principle 2).
    ("wire", ("wire",)),
    # `Store.refresh` drives the steps: it follows the log, folds, reads
    # the edges, and renders the rows through the wire.
    ("store", ("the store",)),
    ("serving", ("the daemon", "who connects", "serving", "the verbs",
                 "the page")),
    # Each command runs what is below it, and nothing below runs one.
    ("commands", ("the hook", "the status command", "ls", "transcript shapes",
                  "files and the report", "wait", "doctor", "serve",
                  "command line")),
)

#: Uses of a name a layer up, as (the user, the name used), each with why.
#: May only get shorter (CLAUDE.md, the ratchet). The pull request that
#: added it moved six helpers to the sections of their layers, so it starts
#: empty.
UPWARD_ALREADY: dict[tuple[str, str], str] = {}


def bound_in(function: ast.AST) -> set[str]:
    """Every name a function or a lambda binds, in its body or below."""
    given = function.args
    names = {one.arg for one in (given.posonlyargs + given.args + given.kwonlyargs
                                 + [given.vararg, given.kwarg]) if one is not None}
    for node in ast.walk(function):
        if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names |= {(one.asname or one.name).split(".")[0] for one in node.names}
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
    return names


def global_uses(statement: ast.stmt) -> list[ast.Name]:
    """The names a top-level statement reads from the module: not a local,
    an argument or a comprehension's own name, and not in a type hint,
    which says what a value is and runs nothing (`from __future__ import
    annotations`)."""
    found: list[ast.Name] = []

    def visit(node: ast.AST, scopes: list[set[str]]) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            for outer in [*getattr(node, "decorator_list", []), *node.args.defaults,
                          *[one for one in node.args.kw_defaults if one is not None]]:
                visit(outer, scopes)
            inner = [*scopes, bound_in(node)]
            for one in node.body if isinstance(node.body, list) else [node.body]:
                visit(one, inner)
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            own = {name.id for made in node.generators for name in ast.walk(made.target)
                   if isinstance(name, ast.Name)}
            for child in ast.iter_child_nodes(node):
                visit(child, [*scopes, own])
            return
        if isinstance(node, ast.AnnAssign):
            for child in (node.target, node.value):
                if child is not None:
                    visit(child, scopes)
            return
        if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                and not any(node.id in scope for scope in scopes)):
            found.append(node)
        for child in ast.iter_child_nodes(node):
            visit(child, scopes)

    visit(statement, [])
    return found


def test_no_section_uses_a_layer_above_its_own():
    """Data flows one way (principle 1): events, the fold, rows, the wire,
    the page. `test_the_fold_does_no_io` holds the fold; this holds the
    whole file, by the layers of `LAYERS`. A new section is put into a
    layer, so the table names every section and only those."""
    text = where.PROGRAM.read_text(encoding="utf-8")
    page_at = text[:text.index('PAGE = r"""')].count("\n") + 1
    found = [one for one in where.sections(text) if one.line < page_at]
    found[-1].end = text.count("\n") + 1      # PAGE, and the guard after it
    layer = {name: number for number, (_, names) in enumerate(LAYERS)
             for name in names}
    named = [one.title.split(":")[0] for one in found]
    assert sorted(named) == sorted(layer), (
        f"in no layer: {sorted(set(named) - set(layer))}; "
        f"no such section: {sorted(set(layer) - set(named))}")

    def layer_at(line: int) -> int:
        """The layer of a line; the imports above the first header are
        the bottom."""
        section = where.section_at(found, line)
        return layer[section.title.split(":")[0]] if section else 0

    tree = ast.parse(text)
    home: dict[str, int] = {}
    for statement in tree.body:
        targets = ([statement] if isinstance(
            statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            else statement.targets if isinstance(statement, ast.Assign)
            else [statement.target] if isinstance(statement, ast.AnnAssign) else [])
        for target in targets:
            name = getattr(target, "name", None) or getattr(target, "id", None)
            if name:
                home[name] = layer_at(statement.lineno)
    assert len(home) > 500, "the definitions stopped matching"

    upward: dict[tuple[str, str], str] = {}
    checked = 0
    # The `__main__` guard runs the program, so it stands above every layer.
    # It is the last statement: `tests/test_shape.py` holds that.
    for statement in tree.body[:-1]:
        user = getattr(statement, "name", None) or ast.unparse(
            statement.targets[0] if isinstance(statement, ast.Assign)
            else getattr(statement, "target", statement)).split("\n")[0][:40]
        mine = layer_at(statement.lineno)
        for use in global_uses(statement):
            if use.id not in home:
                continue
            checked += 1
            if home[use.id] > mine:
                upward[(user, use.id)] = (f"{LAYERS[mine][0]} uses "
                                          f"{LAYERS[home[use.id]][0]}")
    assert checked > 1000, "the uses stopped matching"
    new = {key: why for key, why in upward.items() if key not in UPWARD_ALREADY}
    gone = sorted(UPWARD_ALREADY.keys() - upward.keys())
    assert not new, f"a use of a layer above, so move the helper down: {new}"
    assert not gone, f"no longer a use upward, so off UPWARD_ALREADY: {gone}"
