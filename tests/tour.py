"""Draw the whole page in every state the sidebar knows, and save a picture
of each view.

    python3 tests/tour.py OUTDIR [--light] [--width 1440] [--height 900]
                          [--view transcript|later|unread|saved|search|permission ...]
                          [--eval JS]

The third of `tests/shot.py` and `tests/stage.py`, for a report or a design
question about the page as a whole: the list, the views over it, and how
they look together. A design review of the sidebar and the views drew this
from nothing in a scratchpad, and used it five times: the pictures before,
the mockup, and the pictures after each of three pull requests.

Six sessions, one in each state a row can be in:

- s1 "Fix the cache race": unread, with tool rows, a plan it asked to
  have approved and a final answer in Markdown; it is chosen.
- s2 "Add substring search": unread, its last answer with a code block.
- s3 "Speed up the table": working, with a `claude -p` and two subagents
  of its Agent tool running under it, and two that ran (#422).
- s4 "Write the release notes": waiting on a permission.
- s5 "Update the README": read, with a reminder 50 minutes out.
- s6 "Try the old allocator": over, in the history (#427).

Two answers and a prompt are saved. Every session has a status line:
model, context, spend.

Each view is one PNG, `OUTDIR/<scheme>-<width>-<n>-<view>.png`, in this
order: `transcript` (s1 chosen), `later` (the remind menu of s2 open),
`unread`, `saved`, `search` (for "cache") and `permission` (s4 chosen).
`--view` draws only the ones named. `--eval JS` runs in the page before
each picture -- a file's path or the code itself -- and **is how a mockup
is drawn**: its CSS and its DOM changes over the real page, as `stage.py`'s
`--eval` does. It must be safe to run again, because it runs once for each
picture.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIEWS = ["transcript", "later", "unread", "saved", "search", "permission"]

PLAN = ("# Fix the race in the cache\n\n## Context\n\n`put` and `get` run on two "
        "threads and share `entries` without a lock.\n\n## Steps\n\n1. Take the "
        "cache's lock in `put`.\n2. Let `get` read a copy.\n3. Add `test_two_writers`.\n")

NAMES = {"s1": ("Fix the cache race", "oans", "fix/cache"),
         "s2": ("Add substring search", "oans", "feature/search"),
         "s3": ("Speed up the table", "unordered_dense", "main"),
         "s4": ("Write the release notes", "wostuast", "notes"),
         "s5": ("Update the README", "wostuast", "docs"),
         "s6": ("Try the old allocator", "unordered_dense", "try/alloc")}

SAID = {
    "s1": "The race is gone. `put` now takes the cache's lock, and `get` reads a copy.\n\n"
          "- **tests**: 214 passed, `test_two_writers` among them\n"
          "- **bench**: 3% slower on one thread, the same on eight\n\n"
          "Shall I open the pull request?",
    "s2": "Substring search works in the find box now:\n\n```\n/cache  matches  cache.py, "
          "src/cache_test.py\n```\n\nTwo questions for you: should it ignore case, and "
          "should it search the folder names too?",
    "s5": "README updated.",
}


def stamp(at: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(at))


def make_sessions(ws, home: Path) -> None:
    """The six sessions, their transcripts, their events, and the marks:
    seen, saved, the reminder."""
    from conftest import isolate, record, records

    isolate(home)

    ws.pid_alive = lambda pid: True
    ws.git_facts_many = lambda dirs: {
        d: ws.GitFacts(repo=NAMES[Path(d).name][1], branch=NAMES[Path(d).name][2],
                       root=d, ahead=1 if Path(d).name == "s1" else 0,
                       dirty=3 if Path(d).name in ("s1", "s2") else 0) for d in dirs}
    folder = ws.settings_path().parent / "projects" / "-w"
    folder.mkdir(parents=True)
    now = time.time()
    t0 = now - 2400
    s1 = records(
        record("you", "The cache test fails now and then on CI. Find out why.", ts=stamp(t0)),
        record("claude", "I'll look at the cache and its test first.", ts=stamp(t0 + 20)),
        record("tool", "src/cache.py", tool="Read", tool_id="t1", ts=stamp(t0 + 25)),
        record("result", "1 import threading\n...", tool_id="t1", ts=stamp(t0 + 26)),
        record("tool", "pytest -q tests/test_cache.py", tool="Bash", tool_id="t2",
               ts=stamp(t0 + 30)),
        record("result", "1 failed, 13 passed", tool_id="t2", ts=stamp(t0 + 40)),
        record("claude", "Found it. `put` and `get` share `entries` with no lock, so a "
               "read during a write sees half an update.\n\nI'll write a plan.",
               ts=stamp(t0 + 60)))
    s1 += json.dumps({"type": "assistant", "timestamp": stamp(t0 + 90), "message": {
        "role": "assistant", "content": [{"type": "tool_use", "id": "p1",
                                          "name": "ExitPlanMode", "input": {"plan": PLAN}}]}}) + "\n"
    s1 += json.dumps({"type": "user", "timestamp": stamp(t0 + 300), "message": {
        "role": "user", "content": [{"type": "tool_result", "tool_use_id": "p1",
                                     "content": "User has approved your plan."}]}}) + "\n"
    s1 += records(
        record("tool", "src/cache.py", tool="Edit", tool_id="t3", ts=stamp(t0 + 320)),
        record("result", "ok", tool_id="t3", ts=stamp(t0 + 321)),
        # A `!` command and a message of the harness: they have a link and
        # a bookmark too (#424).
        record("you", "<bash-input>pytest -q tests/test_cache.py</bash-input>",
               ts=stamp(t0 + 330)),
        record("you", "<bash-stdout>14 passed in 0.41s</bash-stdout><bash-stderr></bash-stderr>",
               ts=stamp(t0 + 335)),
        record("you", "[Request interrupted by user]", ts=stamp(t0 + 340)),
        record("claude", SAID["s1"], ts=stamp(now - 120)))
    for n, sid in enumerate(NAMES):
        cwd = home / "w" / sid
        cwd.mkdir(parents=True)
        path = folder / f"{sid}.jsonl"
        path.write_text(s1 if sid == "s1" else records(
            record("you", NAMES[sid][0], ts=stamp(now - 500)),
            record("claude", "Done.", ts=stamp(now - 400))))
        ws.append_event({"session_id": sid, "hook_event_name": "SessionStart",
                         "cwd": str(cwd), "pane": f"%{n}", "pid": 1,
                         "ts": now - 3000, "transcript_path": str(path)})
        ws.append_event({"session_id": sid, "hook_event_name": "UserPromptSubmit",
                         "cwd": str(cwd), "pane": f"%{n}", "pid": 1,
                         "prompt": NAMES[sid][0], "ts": now - 2500 + n})
        ws.write_status(sid, ws.Status(ts=now, name=NAMES[sid][0], model="Opus 5",
                                       context_pct=41.0, cost_usd=1.83))
    for sid, at in (("s1", now - 120), ("s2", now - 40), ("s5", now - 300)):
        ws.append_event({"session_id": sid, "hook_event_name": "Stop",
                         "cwd": str(home / "w" / sid), "pane": "%1", "pid": 1,
                         "ts": at, "last_assistant_message": SAID[sid]})
    ws.append_event({"session_id": "s4", "hook_event_name": "PermissionRequest",
                     "tool_name": "Bash", "tool_input": {"command": "make release"},
                     # As the hook writes it, and as Claude Code suggests a
                     # rule for a command (measured on 2.1.292).
                     "ask_id": "0123456789abcdef",
                     "permission_suggestions": [
                         {"type": "addRules", "behavior": "allow",
                          "destination": "localSettings",
                          "rules": [{"toolName": "Bash", "ruleContent": "make release *"}]}],
                     "cwd": str(home / "w" / "s4"), "pane": "%4", "pid": 1, "ts": now - 30})
    # One that is over, for the history and its chosen row (#427).
    ws.append_event({"session_id": "s6", "hook_event_name": "SessionEnd", "reason": "logout",
                     "cwd": str(home / "w" / "s6"), "pane": "%5", "pid": 1, "ts": now - 900})
    # The working one has started others (#422): a `claude -p` from its Bash
    # tool still running and one that ended, and two subagents of its Agent
    # tool, one still at work.
    cwd = str(home / "w" / "s3")
    agent = {"session_id": "s3", "cwd": cwd, "pane": "%2", "pid": 4242}
    for n, (what, at) in enumerate((("Compare the two hash maps", now - 400),
                                    ("Profile the insert path", now - 90))):
        ws.append_event({**agent, "hook_event_name": "PreToolUse", "tool_name": "Agent",
                         "tool_input": {"description": what}, "ts": at})
        ws.append_event({**agent, "hook_event_name": "SubagentStart", "agent_id": f"a{n}",
                         "agent_type": "general-purpose", "ts": at + 1})
        ws.append_event({**agent, "hook_event_name": "PreToolUse", "agent_id": f"a{n}",
                         "agent_type": "general-purpose", "tool_name": "Bash",
                         "tool_input": {"command": "perf record ./bench insert"}, "ts": at + 5})
    ws.append_event({**agent, "hook_event_name": "SubagentStop", "agent_id": "a0",
                     "agent_type": "general-purpose", "ts": now - 200})
    for sid, prompt, at, ended in (("c1", "Summarise bench.log in one line", now - 700, True),
                                   ("c2", "Review the diff of table.h", now - 25, False)):
        child = {"session_id": sid, "cwd": cwd, "pane": "", "pid": 5000 + at % 100,
                 "started_by": 4242}
        ws.append_event({**child, "hook_event_name": "SessionStart", "ts": at})
        ws.append_event({**child, "hook_event_name": "UserPromptSubmit", "prompt": prompt,
                         "ts": at + 1})
        ws.append_event({**child, "hook_event_name": "PreToolUse", "tool_name": "Read",
                         "tool_input": {"file_path": f"{cwd}/include/table.h"}, "ts": at + 3})
        if ended:
            ws.append_event({**child, "hook_event_name": "Stop", "ts": at + 9})
            ws.append_event({**child, "hook_event_name": "SessionEnd", "reason": "other",
                             "ts": at + 10})
    state = ws.state_dir()
    state.mkdir(parents=True, exist_ok=True)
    (state / "seen.json").write_text(json.dumps(
        {"floor": now - 9000, "seen": {"s5": now - 200, "s1": t0 + 100}}))
    (state / "reminders.json").write_text(json.dumps({"s5": now + 3000}))
    (state / "saved.json").write_text(json.dumps([
        {"id": "s1", "seq": 6, "ts": int(t0 + 60), "at": now - 100,
         "text": "Found it. `put` and `get` share `entries` with no lock, so a read "
                 "during a write sees half an update."},
        {"id": "s2", "seq": 1, "ts": int(now - 400), "at": now - 900, "text": "Done."},
        {"id": "s1", "seq": 0, "ts": int(t0), "at": now - 1200, "who": "me",
         "text": "The cache test fails now and then on CI. Find out why."},
        {"id": "s1", "seq": 9, "ts": int(t0 + 330), "at": now - 1300, "who": "shell",
         "text": "! pytest -q tests/test_cache.py\n14 passed in 0.41s"},
        {"id": "s1", "seq": 10, "ts": int(t0 + 340), "at": now - 1400, "who": "system",
         "text": "Interrupted."}]))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--light", action="store_true")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--view", action="append", choices=VIEWS)
    parser.add_argument("--eval", dest="code", default="",
                        help="JS to run before each picture, or a file that holds it")
    args = parser.parse_args(argv)
    code = args.code
    # Code longer than a file's name may be is code: asked whether it is a
    # file, the disk answered with an error, and the tour stopped there.
    try:
        if code and Path(code).is_file():
            code = Path(code).read_text()
    except OSError:
        pass
    wanted = args.view or VIEWS

    home = Path(tempfile.mkdtemp(prefix="wostuast-tour-"))
    sys.path.insert(0, str(HERE))
    from conftest import isolate
    isolate(home)          # `make_sessions` does it again, for a script that calls it
    from conftest import wostuast as ws
    from browser import opened

    make_sessions(ws, home)
    daemon = ws.Daemon()
    server = ws.make_server(daemon, 0)
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    daemon.store.refresh()

    # A pass a second, as the real daemon makes: without one, the rows it
    # serves stay as they were at the start, and a session the page read
    # came back unread on the next fetch -- in the pictures, not the page.
    def passes() -> None:
        while True:
            time.sleep(0.5)
            try:
                daemon.tick()
            except Exception:  # a tool: one bad pass must not end the tour
                pass

    threading.Thread(target=passes, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}/"
    scheme = "light" if args.light else "dark"
    args.out.mkdir(parents=True, exist_ok=True)

    with opened(base + "#s3", scheme=scheme) as page:
        page.set_viewport_size({"width": args.width, "height": args.height})
        page.wait_for_selector(".row")

        def shot(view: str) -> None:
            if view not in wanted:
                return
            page.wait_for_timeout(500)
            if code:
                page.evaluate(code)
                page.wait_for_timeout(200)
            path = args.out / f"{scheme}-{args.width}-{VIEWS.index(view) + 1}-{view}.png"
            page.screenshot(path=str(path))
            print(path)

        page.click('.row[data-id="s1"]')
        page.wait_for_selector(".turn.plan")
        shot("transcript")
        page.hover('.row[data-id="s2"]')
        page.click('.row[data-id="s2"] .remindlater')
        page.wait_for_selector('.row[data-id="s2"] .remindmenu:not([hidden])')
        shot("later")
        page.mouse.move(args.width - 10, args.height - 10)
        page.click("#feedlink")
        page.wait_for_selector(".feedentry .prose")
        shot("unread")
        page.click("#savedlink")
        page.wait_for_selector(".feedentry")
        shot("saved")
        page.click("#searchlink")
        page.fill(".searchbox", "cache")
        page.wait_for_selector(".searchresults .feedentry")
        shot("search")
        page.click('.row[data-id="s4"]')
        page.wait_for_selector("#asking:not([hidden])")
        shot("permission")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
