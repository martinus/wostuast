"""Measure how wostuast scales with its history and its sessions, and print
one line of numbers.

    python3 tests/scale.py [--sessions 100] [--turns 40] [--days 6] [--page]

Not a test. It writes a synthetic event log into a throwaway home -- each
session a start, then turns of a prompt, five tool calls with their
results, and a stop; a third of them ended -- and times what grows with
it: the first fold of a start, a quiet tick, a tick after one event, the
size of a stream's opening and of one push. `--page` opens the page in
Chromium and times one push's redraw in the sidebar too.

The numbers behind #430 and #431 were measured with this, written from
nothing in a scratchpad: a start folded every archive, 5.5 s at 240,000
events, and every push sent every row, 562 KB at 500 sessions. Run it
before and after a change that touches the fold, a row, the stream or the
sidebar's draw, and give both lines.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def write_log(ws, sessions: int, turns: int, days: float) -> int:
    """The synthetic history, as the hooks would have written it. Gives the
    number of events."""
    now = time.time()
    path = ws.events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    moment = now - days * 24 * 3600
    with path.open("w") as out:
        def put(record: dict) -> None:
            nonlocal count
            out.write(json.dumps(record) + "\n")
            count += 1
        for n in range(sessions):
            base = {"session_id": f"s{n:05d}", "cwd": f"/w/repo/wt{n % 40}",
                    "pane": f"%{n}", "pid": 1000 + n}
            put({**base, "hook_event_name": "SessionStart", "source": "startup", "ts": moment})
            for turn in range(turns):
                moment += 1
                put({**base, "hook_event_name": "UserPromptSubmit",
                     "prompt": f"do thing {turn} " * 20, "ts": moment})
                for call in range(5):
                    given = {"tool_name": "Bash", "tool_input": {"command": f"make test {call}"},
                             "tool_use_id": f"t{turn}-{call}", "ts": moment}
                    put({**base, "hook_event_name": "PreToolUse", **given})
                    put({**base, "hook_event_name": "PostToolUse", **given,
                         "tool_response": {"stdout": "ok " * 50}})
                put({**base, "hook_event_name": "Stop",
                     "last_assistant_message": "done " * 100, "ts": moment})
            if n % 3 == 0:
                put({**base, "hook_event_name": "SessionEnd", "reason": "logout", "ts": moment})
    return count


def measure(ws, home: Path, sessions: int, turns: int, days: float,
            page: bool) -> dict:
    """Every number, for a history written into `home`, which it keeps to
    (`conftest.isolate`) whoever calls it."""
    from conftest import isolate

    isolate(home)
    ws.pid_alive = lambda pid: True
    ws.git_facts_many = lambda dirs: {d: ws.GitFacts(repo="r", branch="b", root=d)
                                      for d in dirs}
    events = write_log(ws, sessions, turns, days)
    out: dict = {"sessions": sessions, "events": events,
                 "log_mb": round(ws.events_path().stat().st_size / 1e6, 1)}
    daemon = ws.Daemon()
    # As `serve` starts: the catch-up fold, then the first tick builds the
    # rows and pushes them. Only the tick refreshes, as in the daemon: a
    # refresh outside it left `told` behind, and the next push carried
    # every row.
    started = time.perf_counter()
    daemon.catch_up()
    daemon.tick()
    out["first_fold_s"] = round(time.perf_counter() - started, 2)
    started = time.perf_counter()
    daemon.tick()
    out["quiet_tick_ms"] = round((time.perf_counter() - started) * 1000, 1)
    sent: list[str] = []
    daemon.hub.send = lambda kind, data, session_id="": sent.append(json.dumps(data))
    ws.append_event({"session_id": "s00001", "cwd": "/w/repo/wt1", "pane": "%1", "pid": 1001,
                     "hook_event_name": "PreToolUse", "tool_name": "Bash",
                     "tool_input": {"command": "ls"}, "ts": time.time()})
    started = time.perf_counter()
    daemon.tick()
    out["event_tick_ms"] = round((time.perf_counter() - started) * 1000, 1)
    out["push_kb"] = round(len(sent[-1]) / 1e3, 1) if sent else 0
    out["opening_kb"] = round(len(json.dumps(daemon.sessions_payload())) / 1e3, 1)
    if page:
        out["redraw_ms"] = redraw(ws, daemon)
    return out


def redraw(ws, daemon) -> float:
    """One push's redraw in the sidebar, with the layout after it, in ms:
    a row changed, laid over the rows the page holds, drawn."""
    from browser import browser_path
    from playwright.sync_api import sync_playwright

    server = ws.make_server(daemon, 0)
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                     daemon=True).start()
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(executable_path=browser_path())
            try:
                page = browser.new_page(viewport={"width": 1400, "height": 900})
                page.goto(f"http://127.0.0.1:{server.server_address[1]}/")
                page.wait_for_function(f"state.sessions.length === {len(daemon.store.rows)}")
                return round(page.evaluate("""() => {
                  state.history = true; redrawRows(); drawSessions();
                  const t = performance.now();
                  for (let i = 0; i < 10; i++) {
                    const s = state.sessions[Math.min(7, state.sessions.length - 1)];
                    state.sessions = mergeSessions(state.sessions,
                      {changed: [Object.assign({}, s, {last_event: "Bash ls " + i})]});
                    drawSessions(); document.body.offsetHeight;
                  }
                  return (performance.now() - t) / 10; }"""), 1)
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sessions", type=int, default=100)
    parser.add_argument("--turns", type=int, default=40)
    parser.add_argument("--days", type=float, default=6.0,
                        help="how far back the history starts")
    parser.add_argument("--page", action="store_true",
                        help="time one push's redraw in Chromium too")
    args = parser.parse_args(argv)
    # Before anything is imported, so nothing can reach the reader's own
    # state directory, as the other tools do (`conftest.isolate`).
    home = Path(tempfile.mkdtemp(prefix="wostuast-scale-"))
    sys.path.insert(0, str(HERE))
    from conftest import isolate
    isolate(home)
    from conftest import wostuast as ws

    print(json.dumps(measure(ws, home, args.sessions, args.turns, args.days, args.page)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
