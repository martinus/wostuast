"""Draw the Files or the Review tab over a repository made for it, and save a picture.

    python3 tests/stage.py OUT.png [--tab review|files|transcript]
                          [--commit N] [--open PATH] [--review]
                          [--click SELECTOR ...] [--light]
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
`--click` clicks a selector once the tab is drawn, in order, for a toggle
or a menu: `.diffhead .readas button[data-value='true']` shows a commit
message as text. `--part` is what the picture is of; the whole window by
default. The window is a notebook's, 1366 x 768, unless it says otherwise.

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
TABS = {"review": "diff", "files": "files", "transcript": "transcript"}
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


def serve(home: Path) -> tuple[str, Path]:
    """A daemon with one session standing in the repository, in `home`."""
    from conftest import record, records
    from conftest import wostuast as ws

    repo = home / "proj"
    make_repo(repo)
    folder = ws.settings_path().parent / "projects" / "-proj"
    folder.mkdir(parents=True)
    transcript = folder / "s1.jsonl"
    transcript.write_text(records(
        record("you", "Make the ring refuse a push when it is full."),
        record("claude", "Done, in four commits on `feature`.")))
    ws.append_event({"session_id": "s1", "hook_event_name": "SessionStart",
                     "cwd": str(repo), "pane": "%7", "ts": time.time(),
                     "transcript_path": str(transcript)})
    daemon = ws.Daemon()
    server = ws.make_server(daemon, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
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
    ask.add_argument("--click", action="append", default=[])
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
    os.environ["CLAUDE_CONFIG_DIR"] = str(home / "claude")
    sys.path.insert(0, str(HERE))
    url, _ = serve(home)

    from browser import DRAWN, WAIT, open_page, show_tab, sync_playwright
    wait = WAIT or 15000
    with sync_playwright() as play:
        context, page = open_page(play, url,
                                  scheme="light" if said.light else "dark")
        try:
            page.set_viewport_size({"width": said.width, "height": said.height})
            if said.review:
                page.evaluate("(r) => localStorage.setItem('wostuast-review-s1', r)",
                              review())
                page.reload()
                page.wait_for_function("!!window.marked && state.chosen === 's1'",
                                       timeout=wait)
            tab = TABS[said.tab]
            if tab != "transcript":
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
            for selector in said.click:
                page.click(selector)
            page.wait_for_function("() => !document.getAnimations().length",
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
        finally:
            context.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
