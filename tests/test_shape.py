"""The rules of **Shape** and **Style** in `CLAUDE.md` that the source's
form shows.

No test held these rules; a scan of the source found each one kept.
These are static checks, the weakest kind of test (topics/principles):
code that does the same thing in another form passes. They still turn a
rule nobody checks into a red test the day it breaks.
"""

from __future__ import annotations

import ast
import functools
import re
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parent.parent / "wostuast"


@functools.cache
def program() -> tuple[str, ast.Module]:
    """The program's text and its tree, parsed once for the whole file."""
    text = PROGRAM.read_text(encoding="utf-8")
    return text, ast.parse(text)


def calls(tree: ast.AST) -> list[tuple[ast.Call, str]]:
    """Every call, with what it calls as written: `os.kill`, `run`."""
    return [(node, ast.unparse(node.func)) for node in ast.walk(tree)
            if isinstance(node, ast.Call)]


def test_only_the_standard_library_is_imported():
    """The install curls one file and runs it with the reader's own
    Python, so an import of anything else fails on the reader's machine
    and on no developer's (goal 4, **Shape**)."""
    _, tree = program()
    imported = {alias.name.split(".")[0] for node in ast.walk(tree)
                if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module.split(".")[0] for node in ast.walk(tree)
                 if isinstance(node, ast.ImportFrom) and node.level == 0}
    assert len(imported) > 20, "the imports stopped matching"
    other = sorted(imported - sys.stdlib_module_names)
    assert not other, f"not the standard library: {other}"


def test_the_main_guard_is_the_last_statement():
    """Before the guard was last, a run as a script started the daemon
    with `PAGE` not yet assigned (**Shape**)."""
    _, tree = program()
    last = tree.body[-1]
    assert isinstance(last, ast.If) and ast.unparse(last.test) in (
        "__name__ == '__main__'", "'__main__' == __name__"), (
        f"line {last.lineno} comes after the __main__ guard")
    guards = [node for node in tree.body if isinstance(node, ast.If)
              and "__main__" in ast.unparse(node.test)]
    assert guards == [last], "a second __main__ guard"


#: The tmux commands the four verbs run (**Shape**, #328), and `-V`, the
#: version that `doctor` and the report show, which is no command.
TMUX_WORDS = {"select-window", "select-pane", "send-keys",
              "load-buffer", "paste-buffer", "delete-buffer", "-V"}


def test_tmux_runs_only_the_six_commands():
    """A keystroke into a pane is allowed, and nothing more: a seventh
    command, `kill-pane` or `respawn-pane`, would own the agent (a
    non-goal). A new one is asked for first (**Shape**)."""
    _, tree = program()
    # An argv is a list; a tuple that starts with "tmux" is a label, as
    # the report's `("tmux", version)`.
    argvs = [node for node in ast.walk(tree)
             if isinstance(node, ast.List) and node.elts
             and isinstance(node.elts[0], ast.Constant)
             and node.elts[0].value == "tmux"]
    assert len(argvs) > 6, "the tmux calls stopped matching"
    words = {(node.lineno, ast.unparse(node.elts[1]) if len(node.elts) > 1 else "")
             for node in argvs}
    other = sorted((line, word) for line, word in words
                   if word.strip("'\"") not in TMUX_WORDS)
    assert not other, f"a tmux command beyond the six: {other}"


#: What starts a process. Only `subprocess.run` takes a timeout and waits.
STARTS_A_PROCESS = {"os.system", "os.popen", "os.spawnl", "os.spawnv",
                    "os.spawnlp", "os.spawnvp", "os.fork", "os.forkpty",
                    "subprocess.Popen", "subprocess.call",
                    "subprocess.check_call", "subprocess.check_output",
                    "subprocess.getoutput", "subprocess.getstatusoutput"}


def test_every_process_runs_under_a_timeout():
    """Git and tmux go through `subprocess` with a short timeout, and an
    error there never crashes anything (**Style**): a git that waits for a
    lock, or a tmux that does not answer, would hold the daemon's one
    writer thread for ever. `os.execv` replaces the program and is not a
    child. `from subprocess import run` would hide a call from this test."""
    _, tree = program()
    found = calls(tree)
    runs = [(node, name) for node, name in found if name == "subprocess.run"]
    assert len(runs) >= 3, "the subprocess calls stopped matching"
    bare = [node.lineno for node, _ in runs
            if not any(keyword.arg == "timeout" for keyword in node.keywords)]
    assert not bare, f"subprocess.run with no timeout, at lines {bare}"
    other = sorted((node.lineno, name) for node, name in found
                   if name in STARTS_A_PROCESS)
    assert not other, f"a process started with no timeout: {other}"
    hidden = [node.lineno for node in ast.walk(tree)
              if isinstance(node, ast.ImportFrom) and node.module == "subprocess"]
    assert not hidden, f"from subprocess import, at lines {hidden}"


def test_every_function_has_type_hints():
    """Type hints everywhere (**Style**): a function of this file is read
    far from its callers, and its hints are the first thing that says what
    it takes. `self` and `cls` need none."""
    _, tree = program()
    bare = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        given = node.args
        names = [one for one in (given.posonlyargs + given.args + given.kwonlyargs
                                 + [given.vararg, given.kwarg])
                 if one is not None and one.arg not in ("self", "cls")]
        if node.returns is None or any(one.annotation is None for one in names):
            bare.append((node.lineno, node.name))
    assert not bare, f"functions with an argument or a return not typed: {bare}"


def test_no_signal_reaches_another_process():
    """Owning the agent process is a non-goal: a keystroke into a pane is
    allowed, a signal is not. `os.kill(pid, 0)` sends nothing; it asks
    whether the process lives. The hook's own alarm (`signal.alarm`) is
    the hook's, and reaches nobody else."""
    _, tree = program()
    found = calls(tree)
    kills = [node for node, name in found if name == "os.kill"]
    assert kills, "the liveness check stopped matching"
    sent = [node.lineno for node in kills
            if not (len(node.args) == 2 and isinstance(node.args[1], ast.Constant)
                    and node.args[1].value == 0)]
    assert not sent, f"os.kill sends a signal, at lines {sent}"
    other = sorted((node.lineno, name) for node, name in found
                   if name in ("os.killpg", "signal.pthread_kill",
                               "os.pidfd_send_signal"))
    assert not other, f"a signal to another process: {other}"
    argvs = [node.lineno for node in ast.walk(tree)
             if isinstance(node, (ast.List, ast.Tuple)) and node.elts
             and isinstance(node.elts[0], ast.Constant)
             and node.elts[0].value in ("kill", "pkill", "killall")]
    assert not argvs, f"a kill command, at lines {argvs}"


#: Calls that change a list, a dict or a set in place.
CHANGES_IN_PLACE = {"append", "extend", "insert", "remove", "pop", "clear",
                    "sort", "reverse", "add", "discard", "update",
                    "setdefault", "popitem"}


def test_no_function_changes_a_module_level_name():
    """No module-level mutable state (**Shape**): the daemon owns a `Store`
    and a `Hub`, and the readers take `rows` without a lock because one
    thread writes. A table at module level (`_HANDLERS`, `ROUTES`) is
    built once, as the module loads; a function that changed one would be
    a second writer that no lock guards, and a test's change would leak
    into the next test."""
    _, tree = program()
    names = {target.id for node in tree.body
             for target in (node.targets if isinstance(node, ast.Assign)
                            else [node.target] if isinstance(node, ast.AnnAssign)
                            else [])
             if isinstance(target, ast.Name)}
    assert len(names) > 50, "the module-level names stopped matching"

    def base(node: ast.AST) -> ast.AST:
        while isinstance(node, (ast.Subscript, ast.Attribute)):
            node = node.value
        return node

    changed = set()
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(function):
            if isinstance(node, ast.Global):
                changed |= {(node.lineno, name) for name in node.names}
            targets = (node.targets if isinstance(node, (ast.Assign, ast.Delete))
                       else [node.target] if isinstance(node, (ast.AugAssign, ast.AnnAssign))
                       else [])
            for target in targets:
                under = base(target)
                if (under is not target and isinstance(under, ast.Name)
                        and under.id in names):
                    changed.add((node.lineno, under.id))
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in CHANGES_IN_PLACE
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in names):
                changed.add((node.lineno, node.func.value.id))
    assert not changed, f"a function changes a module-level name: {sorted(changed)}"


#: Every address outside localhost that the page's text holds, outside a
#: comment, each with why it may be there.
PAGE_ADDRESSES: dict[str, str] = {
    "https://fonts.googleapis.com":
        "the fonts' stylesheet (topics/decisions, the look): CSS runs no script",
    "https://cdnjs.cloudflare.com/ajax/libs/":
        "marked and highlight.js, each a `_SRC` fetched with its `_HASH`",
    "http://www.w3.org/2000/svg":
        "the name of SVG's namespace, which nothing fetches",
    "https://github.com/martinus/wostuast":
        "the brand's link, which only the reader's click opens",
    "https://tickets.example.com/":
        "the example a ticket link's field shows, which nothing opens",
}


def page_text() -> str:
    """The text of `PAGE`, as the daemon serves it."""
    _, tree = program()
    assigned = [node.value for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(one, ast.Name) and one.id == "PAGE"
                        for one in node.targets)]
    assert len(assigned) == 1 and isinstance(assigned[0], ast.Constant), (
        "PAGE is no longer one string")
    return assigned[0].value


def test_the_page_loads_scripts_only_pinned_by_their_hash():
    """Any script on the page can POST to `/send`, which types into the
    reader's terminal (topics/safety), and no JavaScript library is
    vendored (topics/daemon-and-page). So a script from outside comes only
    through `fetchScript`, with the hash of its exact bytes, and any other
    outside address the page names is one of `PAGE_ADDRESSES`."""
    page = page_text()
    lines = [line for line in page.split("\n")
             if not line.lstrip().startswith(("//", "/*", "*"))]
    named = set(re.findall(r"""["'`(](https?://[^"'`)\s]*)""", "\n".join(lines)))
    assert len(named) >= 4, "the addresses stopped matching"
    other = sorted(one for one in named
                   if not any(one.startswith(allowed) for allowed in PAGE_ADDRESSES))
    assert not other, f"the page names an address not in PAGE_ADDRESSES: {other}"
    assert not re.search(r"<script[^>]*\bsrc\s*=", page), "a <script src>, with no hash"
    assert not re.search(r"@import|url\(\s*['\"]?https?:", page), "CSS from outside"
    fetched = re.findall(r"fetchScript\((\w+), (\w+)\)", page)
    sources = re.findall(r'^const (\w+) =\s*"(https://cdnjs[^"]*)";', page, re.M)
    assert sources, "the pinned scripts stopped matching"
    for name, address in sources:
        hashed = [held for given, held in fetched if given == name]
        assert hashed, f"{name} ({address}) is not fetched by fetchScript"
        assert all(re.search(rf'^const {held} =\s*"sha384-[A-Za-z0-9+/=]{{64}}";',
                             page, re.M) for held in hashed), (
            f"{name} is fetched without the hash of its bytes")
    in_text = [one for one in named if one.startswith("https://cdnjs")]
    assert sorted(in_text) == sorted(address for _, address in sources), (
        "a script address from outside that is not a pinned `_SRC`")
