"""Draw a transcript on the page, save a picture of it, and say what it measured.

    python3 tests/shot.py CASE OUT.png [--width 1500] [--height 900]
                         [--thinking] [--light] [--hover WORDS] [--measure]

This is the first thing to run on a report about how the page looks: build
the case from the reader's screenshot, look at it, change the code, look
again. It takes about two seconds. A spacing fix went round three times
because its tests measured the box around each block, which said 6 px, while
the reader looked at the text, which stood 39 px from what followed it. A
picture of the reader's own case would have shown it the first time.

CASE is a real transcript, `.jsonl`, or a few lines like these:

    you: Do the thing.
    claude: Now the tests for the split:
    think: The headers come first.
    tool: Bash ls /usr/include
    tool: Write /tmp/split.c
    result: 14 passed
    claude: They all pass.
    @ 2026-09-18T14:30:00.000Z

A line with no known prefix goes on the block above it, as a new line. `@`
sets the time of the lines after it; until then it is now, as a live
session's is. `result` answers the call just above it.

`--measure` prints, for each block on screen, the gap from the bottom of
what it shows -- its text, not its box -- to the top of the next block.
`--hover WORDS` puts the pointer on the block holding WORDS first, which is
what shows its copy button.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KINDS = ("you", "claude", "think", "tool", "result")


def parse(text: str) -> list[dict]:
    """The short form above, as transcript records."""
    from conftest import record

    now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    made: list[list] = []   # [kind, text, ts, tool, id]
    calls = 0
    for line in text.splitlines():
        head, _, rest = line.partition(":")
        if line.startswith("@"):
            now = line[1:].strip()
        elif head.strip() in KINDS and _:
            kind, rest = head.strip(), rest.strip()
            tool, tool_id = "Bash", f"t{calls}"
            if kind == "tool":
                calls += 1
                tool_id = f"t{calls}"
                tool, _, rest = rest.partition(" ")
            elif kind == "result":
                tool_id = f"t{calls}"
            made.append([kind, rest, now, tool, tool_id])
        elif made and line.strip():
            made[-1][1] += "\n" + line
    return [record(kind, words, ts=ts, tool=tool, tool_id=tool_id)
            for kind, words, ts, tool, tool_id in made]


def serve(lines: str, home: Path):
    """A daemon with one session holding `lines`, in the throwaway `home`."""
    from conftest import wostuast as ws

    ws.git_facts_many = lambda dirs: {
        d: ws.GitFacts(repo="repo", branch="main") for d in dirs}
    ws.pid_alive = lambda pid: True
    folder = ws.settings_path().parent / "projects" / "-w-repo-dir"
    folder.mkdir(parents=True)
    transcript = folder / "s1.jsonl"
    transcript.write_text(lines)
    ws.append_event({"session_id": "s1", "hook_event_name": "SessionStart",
                     "cwd": str(home), "pane": "%7", "pid": 1,
                     "ts": time.time(), "transcript_path": str(transcript)})
    daemon = ws.Daemon()
    server = ws.make_server(daemon, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    daemon.store.refresh()
    return f"http://127.0.0.1:{server.server_address[1]}/"


MEASURE = """() => {
  const shown = [...document.querySelectorAll('.turnbody .turn')]
    .filter((t) => t.getClientRects().length);
  const box = (one) => one.getBoundingClientRect();
  return shown.map((turn, n) => {
    const what = turn.classList.contains('toolrow') ? turn
                                                    : turn.lastElementChild;
    const next = shown[n + 1];
    return {what: turn.innerText.replace(/\\s+/g, ' ').slice(0, 40),
            box: Math.round(box(turn).height),
            shows: Math.round(box(what).height),
            gap: next ? Math.round(box(next).top - box(what).bottom) : null};
  });
}"""


def main(argv: list[str]) -> int:
    ask = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ask.add_argument("case")
    ask.add_argument("out")
    ask.add_argument("--width", type=int, default=1500)
    ask.add_argument("--height", type=int, default=900)
    ask.add_argument("--thinking", action="store_true")
    ask.add_argument("--light", action="store_true")
    ask.add_argument("--hover")
    ask.add_argument("--measure", action="store_true")
    said = ask.parse_args(argv)

    # Before anything is imported, so nothing can reach the reader's own
    # state directory or their Claude settings.
    home = Path(tempfile.mkdtemp(prefix="wostuast-shot-"))
    os.environ["WOSTUAST_STATE"] = str(home / "state")
    os.environ["CLAUDE_CONFIG_DIR"] = str(home / "claude")
    sys.path.insert(0, str(HERE))
    case = Path(said.case)
    if case.suffix == ".jsonl":
        lines = case.read_text()
    else:
        from conftest import records
        lines = records(*parse(case.read_text()))
    url = serve(lines, home)

    from browser import open_page, sync_playwright, wait_for_map
    with sync_playwright() as play:
        context, page = open_page(play, url,
                                  scheme="light" if said.light else "dark")
        try:
            page.set_viewport_size({"width": said.width,
                                    "height": said.height})
            wait_for_map(page)
            if said.thinking:
                page.evaluate("document.body.classList.add('show-thinking')")
            page.wait_for_function("() => !document.getAnimations().length")
            if said.hover:
                page.locator(".turnbody .turn", has_text=said.hover).hover()
            page.locator(".turnbody").screenshot(path=said.out)
            if said.measure:
                print(f"{'box':>4} {'shows':>5} {'gap':>4}  block")
                for one in page.evaluate(MEASURE):
                    gap = "" if one["gap"] is None else one["gap"]
                    print(f"{one['box']:>4} {one['shows']:>5} {gap:>4}  "
                          f"{one['what']}")
        finally:
            context.close()
    print(said.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
