"""Draw any part of the page in a state made for it, and save a picture.

    python3 tests/stage.py OUT.png [--tab review|files|transcript]
                          [--commit N] [--open PATH] [--review]
                          [--settings JSON] [--commands]
                          [--click SELECTOR | --type SELECTOR=TEXT
                           | --keys SELECTOR=TEXT | --eval JS ...] [--light]
                          [--width 1366] [--height 768] [--part SELECTOR]
                          [--keep]

The twin of `tests/shot.py`, for the two tabs that draw a worktree. A
report about either starts with a picture of it, and every session that
needed one wrote this script again from nothing, in a scratchpad that
stays behind on the machine it was written on.

The repository, made fresh each run: `main` with one commit; `feature` with
four more -- the second has a Markdown message with a trailer, and each adds
a function with a tab-indented body and a line far wider than the pane --
a change not committed yet, and `PLAN.md`, a Markdown document nobody has
committed. One session stands in it, with a short transcript.

`--tab` is the tab drawn; `review` is the default. `--commit N` shows the
Nth commit of the branch, counted from the oldest, as "N / 4" does; 0 is
all changes. `--open PATH` opens a file on the Files tab. `--review` writes
a review into the browser first: five comments and a word on the whole.
`--settings JSON` is the reader's `settings.json` before the daemon
starts: the colours, the tab width, the ticket links. `--commands` gives
the send box something to complete: the skills and command files of
`tests/fixtures/commands`, in the repository and in the Claude Code
directory, and a transcript that ran `/clear` and `/compact`; `--keys '#say=/'` after
it opens the list.

Then the steps, once the tab is drawn, in the order they are given:
`--click SELECTOR` clicks, `--type SELECTOR=TEXT` fills a box and presses
Enter, `--keys SELECTOR=TEXT` types into a box key by key and presses
nothing after, `--eval JS` runs in the page. `.diffhead .readas
button[data-value='true']` shows a commit message as text; `--click
'#settings' --part '#setpop'` is the settings menu. **A mockup is drawn
here too**: `--eval` builds the proposal inside the real page, with its real
CSS, where a copy of the CSS in a file of its own drifts from the page.
`--part` is what the picture is of; the whole window by default. The window
is a notebook's, 1366 x 768, unless it says otherwise.

`--eval` waits for a promise it returns. **A step that opens something the
page fetches -- the slash list after `--keys '#say=/'` -- needs one**: the
next step runs as soon as the keys are in, before the answer, and found
the list still shut. `tests/test_stage.py` has the shape: a promise that
looks every 20 ms and fails after 15 s.

`--keep` keeps the daemon up after the picture and prints its address, for
a script of your own against the same page; Ctrl-C ends it.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABS = {"review": "diff", "files": "files", "transcript": "transcript",
        "commands": "commands"}
WIDE = "x" * 40
MESSAGES = [
    "Add ring_push\n\nPushes one item.",
    "Handle a full ring\n\nThe ring now **refuses** a push when it is full:\n\n"
    "- `ring_push` returns `-1`\n- the caller decides what to do\n\nRefs: OA-12",
    "Add ring_pop",
    "Count drops",
]
PLAN = ("# The plan\n\nThe ring **refuses** a push when it is full.\n\n"
        "- `ring_push` returns `-1`\n- the caller decides\n")
NOTES = ["Return -1 here is fine, but say why in a comment.",
         "This loop reads past the end when the ring is full.\nCheck `r->size` first.",
         "Name this ring_drop, it drops the oldest item.",
         "Please add a test for the full ring.",
         "Why a signed int here?"]


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True)


def make_repo(repo: Path) -> None:
    """`main`, then `feature` four commits on, a change not committed, and a
    document nobody committed. Each commit adds one function, so a picked
    commit is a diff of one hunk and the whole branch is four."""
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    # Its own identity: CI has no global one, and a clone does not carry it.
    git(repo, "config", "user.email", "stage@example.com")
    git(repo, "config", "user.name", "Stage")
    body = "int ring_size(struct ring *r)\n{\n\treturn r->size;\n}\n"
    (repo / "ring.c").write_text(body)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Start the ring")
    git(repo, "checkout", "-qb", "feature")
    for at, message in enumerate(MESSAGES):
        body += (f"\nint ring_f{at}(struct ring *r)\n{{\n\tif (r->size == 0) {{\n"
                 f"\t\treturn -1; /* {WIDE} {WIDE} {WIDE} */\n\t}}\n"
                 f"\treturn {at};\n}}\n")
        (repo / "ring.c").write_text(body)
        git(repo, "commit", "-qam", message)
    (repo / "ring.c").write_text(body + "\n/* not committed yet */\n")
    (repo / "PLAN.md").write_text(PLAN)


def ran(name: str) -> dict:
    """A transcript record for a slash command that was run."""
    from conftest import record
    return record("you", f"<command-name>/{name}</command-name>"
                         f"<command-message>{name}</command-message>"
                         "<command-args></command-args>")


def serve(home: Path, commands: bool = False) -> tuple[str, Path]:
    """A daemon with one session standing in the repository, in `home`."""
    import shutil

    from conftest import FIXTURES, record, records
    from conftest import wostuast as ws

    repo = home / "proj"
    make_repo(repo)
    folder = ws.settings_path().parent / "projects" / "-proj"
    folder.mkdir(parents=True)
    transcript = folder / "s1.jsonl"
    used = [ran("clear"), ran("compact"), ran("clear")] if commands else []
    transcript.write_text(records(
        *used,
        record("you", "Make the ring refuse a push when it is full."),
        record("claude", "Done, in four commits on `feature`.")))
    if commands:
        shutil.copytree(FIXTURES / "commands" / "project" / ".claude",
                        repo / ".claude")
        shutil.copytree(FIXTURES / "commands" / "claude",
                        ws.settings_path().parent, dirs_exist_ok=True)
    ws.append_event({"session_id": "s1", "hook_event_name": "SessionStart",
                     "cwd": str(repo), "pane": "%7", "ts": time.time(),
                     "transcript_path": str(transcript)})
    daemon = ws.Daemon()
    server = ws.make_server(daemon, 0)
    threading.Thread(target=server.serve_forever,
                     kwargs={"poll_interval": 0.05}, daemon=True).start()
    daemon.store.refresh()
    ticking = lambda: [daemon.tick() or time.sleep(0.5) for _ in iter(int, 1)]
    threading.Thread(target=ticking, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}/#s1", repo


#: Each commit's `return -1`, and line 3, which no hunk holds: that one
#: stands under "commented elsewhere", as a comment from the Files tab does.
LINES = [9, 18, 27, 36, 3]


def review() -> str:
    """Five comments and a word on the whole, in the shape `recallReview`
    takes back."""
    return json.dumps({
        "overall": "Fix these and push again.\nThen run the tests.",
        "comments": [{"note": note, "anchor": f"ring.c\n{line}"}
                     for line, note in zip(LINES, NOTES)]})


def main(argv: list[str]) -> int:
    ask = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ask.add_argument("out")
    ask.add_argument("--tab", choices=sorted(TABS), default="review")
    ask.add_argument("--commit", type=int, default=0)
    ask.add_argument("--open")
    ask.add_argument("--review", action="store_true")
    ask.add_argument("--settings")
    ask.add_argument("--commands", action="store_true")
    # One list, so the steps run in the order they were written.
    for flag in ("click", "type", "keys", "eval"):
        ask.add_argument(f"--{flag}", dest="steps", action="append",
                         default=[], type=lambda value, flag=flag: (flag, value))
    ask.add_argument("--light", action="store_true")
    ask.add_argument("--width", type=int, default=1366)
    ask.add_argument("--height", type=int, default=768)
    ask.add_argument("--part", default="body")
    ask.add_argument("--keep", action="store_true")
    said = ask.parse_args(argv)

    # Before anything is imported, so nothing can reach the reader's own
    # state directory or their Claude settings.
    home = Path(tempfile.mkdtemp(prefix="wostuast-stage-"))
    os.environ["WOSTUAST_STATE"] = str(home / "state")
    os.environ["WOSTUAST_CONFIG"] = str(home / "config")
    os.environ["CLAUDE_CONFIG_DIR"] = str(home / "claude")
    # Its session stands in pane `%7`, and a click that sends or renames
    # types into that pane: never the reader's own (#351), as `ws` does.
    os.environ["TMUX"] = f"{home}/no-tmux-here,0,0"
    if said.settings:
        (home / "config").mkdir(parents=True)
        (home / "config" / "settings.json").write_text(
            json.dumps(json.loads(said.settings)), encoding="utf-8")
    sys.path.insert(0, str(HERE))
    url, _ = serve(home, said.commands)

    from browser import DRAWN, WAIT, opened, show_tab
    wait = WAIT or 15000
    with opened(url, scheme="light" if said.light else "dark") as page:
        page.set_viewport_size({"width": said.width, "height": said.height})
        if said.review:
            page.evaluate("(r) => localStorage.setItem('wostuast-review-s1', r)",
                          review())
            page.reload()
            page.wait_for_function("!!window.marked && state.chosen === 's1'",
                                   timeout=wait)
        tab = TABS[said.tab]
        if tab == "commands":           # a view, not a tab (#411)
            page.click("#cmdlink")
        elif tab != "transcript":
            show_tab(page, tab)
        page.wait_for_selector(DRAWN[tab], timeout=wait)
        if tab == "diff":
            page.wait_for_function("(state.diff || {}).commits?.length === 4",
                                   timeout=wait)
            if said.commit:
                sha = page.evaluate("(n) => state.diff.commits[4 - n].sha",
                                    said.commit)
                page.evaluate("(s) => pickDiff(s)", sha)
                page.wait_for_function(
                    "(s) => state.diff && state.diff.of === s", arg=sha,
                    timeout=wait)
            page.wait_for_selector(".diffscroll .dfile", timeout=wait)
        if said.open:
            page.wait_for_function("(p) => state.files.known.has(p)",
                                   arg=said.open, timeout=wait)
            page.evaluate("(p) => goTo(p)", said.open)
            page.wait_for_function(
                "(p) => state.files.read && state.files.path === p",
                arg=said.open, timeout=wait)
        for flag, value in said.steps:
            if flag == "click":
                page.click(value)
            elif flag == "type":
                selector, _, text = value.partition("=")
                page.fill(selector, text)
                page.press(selector, "Enter")
            elif flag == "keys":
                selector, _, text = value.partition("=")
                page.type(selector, text)
            else:
                page.evaluate(value)
        # Only an animation that ends: a row that needs you pulses for ever,
        # and a wait for no animation at all never ended on one.
        page.wait_for_function(
            "() => !document.getAnimations().some("
            "(a) => a.effect && a.effect.getTiming().iterations !== Infinity)",
            timeout=wait)
        page.wait_for_timeout(200)     # a frame for what a click redrew
        page.locator(said.part).first.screenshot(path=said.out)
        print(said.out)
        if said.keep:
            print(url.split("#")[0], flush=True)
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
