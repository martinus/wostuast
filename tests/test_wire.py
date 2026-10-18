"""The wire: every shape the page receives is defined in one place (#540,
CLAUDE.md, **Principles**, 2). These read the program's source as well as
run it, so they hold where a shape is written, not only what it says."""

from __future__ import annotations

import ast
import inspect
import re

import conftest


def page_source(ws) -> str:
    """The page: everything from `PAGE = r\"\"\"` on."""
    text = inspect.getsource(ws)
    return text[text.index('PAGE = r"""'):]


def test_a_block_sends_only_the_fields_it_names(ws):
    """`blocks_json` sent `block.__dict__`, so a field added to `Block` for
    the daemon's own use went to every page. It names its keys now, and
    this list is where a new one is chosen."""
    block = ws.Block(seq=3, kind="tool", result="\n".join(map(str, range(50))))
    block.held_for_the_daemon = "never sent"
    sent = ws.blocks_json([block])[0]
    assert list(sent) == [
        "seq", "kind", "ts", "text", "tool", "target", "added", "removed",
        "result", "patch", "patch_more", "failed", "tool_use_id", "answered"]
    assert sent["result"].endswith("… 10 more lines")


def test_the_page_reads_only_session_fields_the_row_sends(ws):
    """A contract between the two ends: every field the page reads off a
    session is one `row` sends. A field renamed on one side only read as
    `undefined` on the page, which draws as nothing and fails no test.
    The page names a session `s`, `session` or `chosen`; measured when
    this was written, none of those names held anything else."""
    sent = set(ws.row(ws.Session(session_id="x")))
    read = set()
    for name in ("s", "session", "chosen"):
        read |= set(re.findall(rf"\b{name}\.([a-z_]+)\b", page_source(ws)))
    assert read, "the page reads no session field: the pattern is stale"
    assert read - sent == set()


def test_the_page_listens_for_every_event_the_stream_sends(ws):
    """The stream's event names are constants (`EVENTS`), and the page
    listens for exactly those: a name changed on one side lost every push
    of that kind, and the page simply never changed."""
    heard = set(re.findall(r'stream\.addEventListener\("(\w+)"', page_source(ws)))
    assert heard == set(ws.EVENTS)


def test_the_row_and_ls_json_say_the_same_of_a_session(ws):
    """`row` is the page's and `session_json` a promise to scripts, so they
    are two shapes on purpose. What both say -- the worktree, git's facts
    -- comes from one place (`worktree_path`, `git_fields`), and so they
    agree on every key they share."""
    session = ws.Session(session_id="x", cwd="/w/repo/src", home="/w/repo")
    session.git = ws.GitFacts(root="/w/repo", branch="main", ahead=2,
                              behind=1, dirty=True, touched_files=3,
                              doing="rebase", conflicts=1)
    row, json = ws.row(session), ws.session_json(session)
    shared = set(row) & set(json)
    assert {"worktree_path", "branch", "touched_files", "conflicts"} <= shared
    assert {key: row[key] for key in shared} == {key: json[key] for key in shared}


#: Turning a dataclass into JSON outside the wire section, each with why.
#: May only get shorter (CLAUDE.md, **Principles**, the ratchet).
#: #576 emptied it: `write_status` writes its keys one by one.
DATACLASS_TO_JSON_ELSEWHERE: dict[str, int] = {}


def test_only_the_wire_section_turns_a_dataclass_into_json(ws):
    """A dataclass turned whole into JSON sends every field it has, now and
    later. Only the wire section may do it (`wire_fields`, `plain`), for
    the five dataclasses it names as page shapes. Read as calls of `vars`
    and `asdict` and reads of `__dict__`, so a comment that names them is
    not one."""
    text = inspect.getsource(ws)
    lines = text[:text.index('PAGE = r"""')].count("\n")
    head = text.index("# --- wire: every shape the page receives")
    start = text[:head].count("\n")
    end = text[:text.index("\n# --- ", head)].count("\n")
    tree = ast.parse(text)
    functions = [node for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    found: dict[str, int] = {}
    for node in ast.walk(tree):
        called = isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in ("vars", "asdict")
        read = isinstance(node, ast.Attribute) and node.attr == "__dict__"
        if not (called or read) or start < node.lineno <= end or node.lineno > lines:
            continue
        inside = min((one for one in functions
                      if one.lineno <= node.lineno <= one.end_lineno),
                     key=lambda one: one.end_lineno - one.lineno)
        found[inside.name] = found.get(inside.name, 0) + 1
    assert found == DATACLASS_TO_JSON_ELSEWHERE


def test_only_get_json_calls_fetch(ws):
    """One way for the page to ask the daemon (#541): `getJson`. It was
    four, each with its own answer when the daemon went away -- null, an
    `{error}`, a try of its own -- and a fifth would have been a fifth."""
    page = page_source(ws)
    calls = [hit.start() for hit in re.finditer(r"\bfetch\(", page)]
    assert len(calls) == 1
    assert page.rfind("\nasync function getJson(", 0, calls[0]) \
        > page.rfind("\nfunction ", 0, calls[0])


def test_every_field_of_the_pages_state_is_declared(ws):
    """One list names all the state of the page (#542): the `state` literal,
    or a line right after it that sets one field from a helper. Ten fields
    were set first wherever they were first needed, so no one place said
    what the page holds."""
    page = page_source(ws)
    start = page.index("\nconst state = {")
    end = page.index("\n};\n", start)
    declared = set(re.findall(r"^  (\w+):", page[start:end], re.M))
    declared |= set(re.findall(r"^state\.(\w+) = ", page, re.M))
    used = set(re.findall(r"\bstate\.(\w+)", page))
    assert used - declared == set()
