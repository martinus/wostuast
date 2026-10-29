"""Draw any part of the page in a state made for it, and save a picture.

    python3 tests/stage.py OUT.png [--tab review|files|transcript]
                          [--commit N] [--open PATH] [--review]
                          [--settings JSON] [--commands] [--merge] [--elsewhere]
                          [--summary] [--fresh]
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
committed. Folders (`src/util`, `docs`), a binary `logo.bin`, and
`.oa-implement/plan.md` in a folder git ignores, written after the session
began. One session stands in it, with a short transcript.

`--tab` is the tab drawn; `review` is the default. `--commit N` shows the
Nth commit of the branch, counted from the oldest, as "N / 4" does; 0 is
all changes. `--open PATH` opens a file on the Files tab. `--review` writes
a review into the browser first: five comments and a word on the whole.
`--settings JSON` is the reader's `settings.json` before the daemon
starts: the colours, the tab width, the ticket links. `--commands` gives
the send box something to complete: the skills and command files of
`tests/fixtures/commands`, in the repository and in the Claude Code
directory, and a transcript that ran `/clear` and `/compact`; `--keys '#say=/'` after
it opens the list. `--merge` ends the branch in two more commits: one that
renames the size, and a merge of `main`, which renamed it too, settled by
hand (#621); `--commit 6` is the merge. `--elsewhere` is a second
repository, `api`, with one commit and one change, that the agent edited a
file in: the picker beside the tabs names it (#616). Beside it, `notes`, a
folder git knows nothing of, for the reader to add (#624). `--summary` gives
the session four turns that used something, their times, an Explore
subagent and a status line that says what it cost, for the Statistics tab
(#622), and a month of what three more sessions spent, for all of them
(#653). `--fresh` is a session that has only started: no prompt yet, so
no transcript (#651, #654).

Then the steps, once the tab is drawn, in the order they are given:
`--click SELECTOR` clicks, `--type SELECTOR=TEXT` fills a box and presses
Enter, `--keys SELECTOR=TEXT` types into a box key by key and presses
nothing after, `--eval JS` (or a file of it) runs in the page.
`.diffhead .readas` shows a commit message as
text; `--click '#settings' --part '#setpop'` is the settings menu. **A mockup is drawn
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
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABS = {"review": "diff", "files": "files", "transcript": "transcript",
        "summary": "summary", "commands": "commands"}
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


def make_repo(repo: Path, merge: bool = False) -> None:
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
    # A tree with folders in it, a binary file, and a folder git ignores,
    # where an agent writes its plan (`serve` writes it, once the session
    # has begun).
    (repo / "src" / "util").mkdir(parents=True)
    (repo / "src" / "util" / "list.c").write_text("int list_size(void);\n")
    (repo / "docs").mkdir()
    (repo / "docs" / "notes.md").write_text("# Notes\n")
    (repo / "logo.bin").write_bytes(bytes(range(256)) * 3)
    (repo / ".gitignore").write_text(".oa-implement/\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Start the ring")
    git(repo, "checkout", "-qb", "feature")
    for at, message in enumerate(MESSAGES):
        body += (f"\nint ring_f{at}(struct ring *r)\n{{\n\tif (r->size == 0) {{\n"
                 f"\t\treturn -1; /* {WIDE} {WIDE} {WIDE} */\n\t}}\n"
                 f"\treturn {at};\n}}\n")
        (repo / "ring.c").write_text(body)
        git(repo, "commit", "-qam", message)
    if merge:
        body = merge_main(repo, body)
    (repo / "ring.c").write_text(body + "\n/* not committed yet */\n")
    (repo / "PLAN.md").write_text(PLAN)


def merge_main(repo: Path, body: str) -> str:
    """`main` and `feature` each rename the size, and `feature` merges
    `main` and settles the conflict by hand, with a file `main` added
    coming along (#621). Returns `ring.c` as the merge left it."""
    git(repo, "checkout", "-q", "main")
    start = (repo / "ring.c").read_text()
    (repo / "ring.c").write_text(start.replace("r->size;", "r->count;", 1))
    (repo / "CHANGES.md").write_text("# Changes\n\n- the size is a count\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Call the size a count")
    git(repo, "checkout", "-q", "feature")
    (repo / "ring.c").write_text(body.replace("r->size;", "r->len;", 1))
    git(repo, "commit", "-qam", "Call the size a length")
    # It stops on the conflict, as it is meant to.
    subprocess.run(["git", "-C", str(repo), "merge", "-q", "main"], capture_output=True)
    body = body.replace("r->size;", "r->len; /* main calls it the count */", 1)
    (repo / "ring.c").write_text(body)
    git(repo, "add", "ring.c")
    git(repo, "commit", "-qm", "Merge main: keep the length")
    return body


def ran(name: str) -> dict:
    """A transcript record for a slash command that was run."""
    from conftest import record
    return record("you", f"<command-name>/{name}</command-name>"
                         f"<command-message>{name}</command-message>"
                         "<command-args></command-args>")


def make_elsewhere(api: Path) -> None:
    """A second repository the agent worked in (#616)."""
    api.mkdir()
    git(api, "init", "-q", "-b", "main")
    (api / "routes.py").write_text('def health():\n    return "ok"\n')
    (api / "README.md").write_text("# api\n")
    git(api, "add", "-A")
    git(api, "commit", "-q", "-m", "The health route")
    (api / "routes.py").write_text(
        'def health():\n    return "ok"\n\n\ndef ready():\n    return "ready"\n')
    # And a folder git knows nothing of, for the reader to add (#624).
    notes = api.parent / "notes"
    (notes / "meetings").mkdir(parents=True)
    (notes / "ideas.md").write_text("# Ideas\n\n- a ring that grows\n- a ring that warns\n")
    (notes / "meetings" / "monday.md").write_text("# Monday\n\nThe ring is full too often.\n")


#: The turns `--summary` writes (#622): each prompt, its calls, and what its
#: one reply used, as Claude Code writes `usage`.
SPENT = [
    ("Find where the ring is defined.", ["Grep", "Read"],
     dict(input_tokens=30, cache_read_input_tokens=180_000, output_tokens=2_400)),
    ("Refactor the parser to use the ring.", ["Read", "Read", "Edit", "Edit", "Bash"],
     dict(input_tokens=90, cache_creation_input_tokens=60_000,
          cache_read_input_tokens=1_900_000, output_tokens=41_000)),
    ("Run the tests and fix what fails.", ["Bash", "Bash", "Edit", "Bash"],
     dict(input_tokens=60, cache_read_input_tokens=1_200_000, output_tokens=18_000)),
    ("Write the changelog.", ["Read", "Edit"],
     dict(input_tokens=12, cache_read_input_tokens=300_000, output_tokens=3_100)),
]


#: What a call of each tool worked on, and how long it ran, in ms (#663).
TOOK = {
    "Bash": [({"command": "make test"}, 96_400), ({"command": "make -j8"}, 41_200),
             ({"command": "git diff --stat"}, 180)],
    "Read": [({"file_path": "src/ring.c"}, 40), ({"file_path": "src/parse.c"}, 60)],
    "Edit": [({"file_path": "src/parse.c"}, 120), ({"file_path": "CHANGELOG.md"}, 90)],
    "Grep": [({"pattern": "ring_"}, 1_300)],
}


def make_spending(ws, transcript: Path, repo: Path) -> None:
    """Four turns that used something, their times, an Explore subagent
    and a status line that says what it all cost (#622)."""
    from conftest import record, records
    made = []
    for at, (said, tools, used) in enumerate(SPENT):
        made.append(record("you", said))
        for count, tool in enumerate(tools):
            one = record("tool", "src/ring.c", tool=tool, tool_id=f"t{at}{count}")
            one["message"].update(id=f"m{at}", usage=used)
            made += [one, record("result", "ok", tool_id=f"t{at}{count}")]
    with transcript.open("a") as handle:
        handle.write(records(*made))
    began = time.time() - 7_800
    base = {"session_id": "s1", "cwd": str(repo), "pane": "%7"}
    times = [(0, 300), (600, 1_900), (2_400, 3_500), (4_000, 4_200)]
    used = dict.fromkeys(TOOK, 0)
    for turn, ((start, end), (said, tools, _)) in enumerate(zip(times, SPENT)):
        ws.append_event({**base, "hook_event_name": "UserPromptSubmit", "prompt": said,
                         "ts": began + start})
        # Each call's own time, as its `PostToolUse` says it (#663); each
        # tool takes its next example in turn.
        for count, tool in enumerate(tools):
            what, took = TOOK[tool][used[tool] % len(TOOK[tool])]
            used[tool] += 1
            ws.append_event({**base, "hook_event_name": "PostToolUse", "tool_name": tool,
                             "tool_use_id": f"t{turn}{count}", "tool_input": what,
                             "duration_ms": took, "ts": began + start + 20 * (count + 1)})
        ws.append_event({**base, "hook_event_name": "Stop", "ts": began + end})
    agent = {**base, "agent_id": "ag1", "agent_type": "Explore"}
    ws.append_event({**agent, "hook_event_name": "SubagentStart", "ts": began + 700})
    for step in range(3):
        ws.append_event({**agent, "hook_event_name": "PreToolUse", "tool_name": "Grep",
                         "tool_input": {"pattern": "ring"}, "ts": began + 710 + step})
    ws.append_event({**agent, "hook_event_name": "SubagentStop", "ts": began + 860})
    # Its own transcript, where Claude Code writes it (#618).
    own = transcript.with_suffix("") / "subagents" / "agent-ag1.jsonl"
    own.parent.mkdir(parents=True)
    own.write_text(records(
        record("you", "Find every place that reads the ring, and say which ones lock it."),
        record("tool", "ring_", tool="Grep", tool_id="a1"),
        record("result", "src/ring.c\nsrc/parse.c\nsrc/net.c", tool_id="a1"),
        record("tool", "src/parse.c", tool="Read", tool_id="a2"),
        record("result", "…", tool_id="a2"),
        record("claude", "Three files read the ring. **Only `net.c` takes the lock**;"
                         " `parse.c` reads it bare, from the parser thread.")))
    ws.append_event({**base, "hook_event_name": "UserPromptSubmit", "ts": began + 4_300,
                     "prompt": "<task-notification>\n<task-id>ag1</task-id>\n"
                               "<status>completed</status>\n<usage><subagent_tokens>212000"
                               "</subagent_tokens></usage>\n</task-notification>"})
    ws.append_event({**base, "hook_event_name": "Stop", "ts": began + 4_320})
    ws.write_status("s1", ws.Status(ts=time.time(), name="", model="Opus 5",
                                    cost_usd=4.12, wall_ms=7_800_000, api_ms=2_310_000,
                                    lines_added=156, lines_removed=23,
                                    days={ws.local_day(time.time()): 4.12}))
    # The month of three made-up sessions besides, for what all of them
    # spent (#653): a working day dearer than a weekend's, never real.
    today = int(ws.local_day(time.time())[8:])
    for n, rate in enumerate((3.1, 1.7, 0.9)):
        total, days = 0.0, {}
        for day in range(1, today + 1):
            moment = time.time() - (today - day) * 86_400
            weekend = time.localtime(moment).tm_wday >= 5
            total += round(rate * (0.3 if weekend else 1 + (day * (n + 3)) % 7 / 5), 2)
            days[ws.local_day(moment)] = round(total, 2)
        ws.write_status(f"other{n}", ws.Status(ts=time.time(), cost_usd=total, days=days))


def serve(home: Path, commands: bool = False, merge: bool = False,
          elsewhere: bool = False, summary: bool = False,
          fresh: bool = False) -> tuple[str, Path]:
    """A daemon with one session standing in the repository, in `home`."""
    import shutil

    from conftest import FIXTURES, isolate, record, records
    from conftest import wostuast as ws

    isolate(home)

    repo = home / "proj"
    make_repo(repo, merge)
    folder = ws.settings_path().parent / "projects" / "-proj"
    folder.mkdir(parents=True)
    transcript = folder / "s1.jsonl"
    used = [ran("clear"), ran("compact"), ran("clear")] if commands else []
    # Claude Code writes no transcript before the first prompt.
    if not fresh:
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
                     "cwd": str(repo), "pane": "%7", "ts": time.time() - 1,
                     "transcript_path": str(transcript)})
    if summary:
        make_spending(ws, transcript, repo)
    if elsewhere:
        make_elsewhere(home / "api")
        ws.append_event({"session_id": "s1", "hook_event_name": "PreToolUse",
                         "cwd": str(repo), "pane": "%7", "ts": time.time(),
                         "tool_name": "Edit",
                         "tool_input": {"file_path": str(home / "api" / "routes.py")}})
    (repo / ".oa-implement").mkdir()
    (repo / ".oa-implement" / "plan.md").write_text("# The plan\n")
    daemon = ws.Daemon()
    # Ticked by hand, so git is read at once: behind the tick (#550) its
    # facts would wait for a tick that nothing here runs.
    daemon.store.git = ws.GitReader()
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
    ask.add_argument("--merge", action="store_true")
    ask.add_argument("--elsewhere", action="store_true")
    ask.add_argument("--summary", action="store_true")
    ask.add_argument("--fresh", action="store_true")
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
    # state directory or their Claude settings. `serve` does it again, for
    # a script that calls it by itself.
    home = Path(tempfile.mkdtemp(prefix="wostuast-stage-"))
    sys.path.insert(0, str(HERE))
    from conftest import isolate
    isolate(home)
    if said.settings:
        (home / "config").mkdir(parents=True)
        (home / "config" / "settings.json").write_text(
            json.dumps(json.loads(said.settings)), encoding="utf-8")
    sys.path.insert(0, str(HERE))
    url, _ = serve(home, said.commands, said.merge, said.elsewhere, said.summary,
                   said.fresh)

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
            count = 6 if said.merge else 4
            page.wait_for_function("(n) => (state.diff || {}).commits?.length === n",
                                   arg=count, timeout=wait)
            if said.commit:
                sha = page.evaluate("([n, count]) => state.diff.commits[count - n].sha",
                                    [said.commit, count])
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
                # A file of it, as tour.py takes: a mockup that carries a
                # font is longer than a command line may be.
                page.evaluate(Path(value).read_text() if Path(value).is_file()
                              else value)
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
