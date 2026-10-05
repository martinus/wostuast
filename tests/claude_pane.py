#!/usr/bin/env python3
"""Run a real Claude Code in a tmux pane of its own, against a fake Messages
API, and read what it did.

Not a test. A question about what Claude Code does with a key, a paste, a
slash command or a status line is answered by measuring it, never by
guessing (`.claude/topics/payloads.md`). Four issues in one session were
answered this way -- a paste's markers, the keys of a dialog, what `/model`
writes, the status line's `effort` -- and the harness was written from
nothing each time, in a scratchpad that stays behind on the machine.

    python3 tests/claude_pane.py            # starts one, says what it saw

    import claude_pane
    with claude_pane.ClaudePane() as cc:
        cc.ready()
        cc.send("hello")                    # a bracketed paste, then Enter
        cc.wait_for_turns(1)
        cc.turns()                          # what the API was asked, by turn
        cc.statuses()[-1]["effort"]         # what the status line received
        cc.ask("Bash", {"command": "touch x", "description": "x"})
        cc.busy(25)                         # a turn that runs for 25 s
        cc.paste(b"\\x1b")                   # a key, as its bytes
        cc.screen()

    # A plugin, or anything else that must be there before it starts:
    claude_pane.ClaudePane(setup=lambda env: subprocess.run(
        ["claude", "plugin", "install", "demo@mk"], env=env))

It needs `claude` and `tmux` on the PATH, and nothing of yours: a home of
its own, a tmux server of its own (`-L`), a fake API key, the API on
127.0.0.1. The fake API answers "ok" to everything, or, once, the tool call
`ask` gave it. It keeps every request it was sent. `tests/test_claude_pane.py`
keeps the fake API working; Claude Code itself is not in CI.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable


def stream(model: str, block: dict, delta: dict, stop: str):
    """The server-sent events of one answer with one content block."""
    yield "message_start", {"type": "message_start", "message": {
        "id": "msg_fake", "type": "message", "role": "assistant", "model": model,
        "content": [], "stop_reason": None, "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 1}}}
    yield "content_block_start", {"type": "content_block_start", "index": 0,
                                  "content_block": block}
    yield "content_block_delta", {"type": "content_block_delta", "index": 0,
                                  "delta": delta}
    yield "content_block_stop", {"type": "content_block_stop", "index": 0}
    yield "message_delta", {"type": "message_delta", "delta": {
        "stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": 1}}
    yield "message_stop", {"type": "message_stop"}


class FakeApi:
    """A Messages API on 127.0.0.1 that answers "ok", or once a tool call.

    `requests` holds every body it was sent, parsed. Only a request that
    offers tools is the agent's own turn: Claude Code also asks for titles
    and other small things, and those get "ok" too.
    """

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.next_call: dict | None = None
        api = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def do_GET(self) -> None:          # noqa: N802
                self.reply(b"{}")

            def do_POST(self) -> None:          # noqa: N802
                body = self.rfile.read(int(self.headers.get("content-length", 0)))
                try:
                    asked = json.loads(body)
                except ValueError:
                    asked = {}
                api.requests.append(asked)
                if "count_tokens" in self.path:
                    self.reply(json.dumps({"input_tokens": 10}).encode())
                    return
                model = asked.get("model", "claude")
                call = None
                if asked.get("tools") and api.next_call:
                    call, api.next_call = api.next_call, None
                if not asked.get("stream"):
                    self.reply(json.dumps({
                        "id": "msg_fake", "type": "message", "role": "assistant",
                        "model": model, "content": [{"type": "text", "text": "ok"}],
                        "stop_reason": "end_turn", "stop_sequence": None,
                        "usage": {"input_tokens": 10, "output_tokens": 1}}).encode())
                    return
                if call:
                    events = stream(model, {"type": "tool_use", "id": call["id"],
                                            "name": call["name"], "input": {}},
                                    {"type": "input_json_delta",
                                     "partial_json": json.dumps(call["input"])},
                                    "tool_use")
                else:
                    events = stream(model, {"type": "text", "text": ""},
                                    {"type": "text_delta", "text": "ok"}, "end_turn")
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.end_headers()
                for name, data in events:
                    self.wfile.write(f"event: {name}\ndata: {json.dumps(data)}\n\n".encode())
                    self.wfile.flush()

            def reply(self, out: bytes) -> None:
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


class ClaudePane:
    """Claude Code in a tmux pane of its own, talking to a `FakeApi`."""

    def __init__(self, manual: bool = True, width: int = 200,
                 events: tuple[str, ...] = ("UserPromptSubmit", "Stop",
                                            "PermissionRequest"),
                 mode: str = "default",
                 setup: "Callable[[dict[str, str]], None] | None" = None) -> None:
        if not shutil.which("claude") or not shutil.which("tmux"):
            raise RuntimeError("claude_pane needs claude and tmux on the PATH")
        self.home = Path(tempfile.mkdtemp(prefix="claude-pane-"))
        self.work = self.home / "work"
        self.work.mkdir()
        self.api = FakeApi()
        self.name = f"claude-pane-{os.getpid()}-{time.monotonic_ns()}"
        key = "sk-ant-api03-" + "x" * 80
        (self.home / ".claude.json").write_text(json.dumps({
            "hasCompletedOnboarding": True, "theme": "dark",
            "customApiKeyResponses": {"approved": [key[-20:]], "rejected": []},
            "projects": {str(self.work): {"hasTrustDialogAccepted": True,
                                          "hasCompletedProjectOnboarding": True}}}))
        # A status line and hooks that keep what they are handed, so a
        # question about a payload is read off the real one. `events` names
        # the hooks: a question about `PreToolUse` or `Notification` needs
        # them too.
        keep = lambda name: f"cat >> {self.home}/{name}.jsonl; echo >> {self.home}/{name}.jsonl"
        hooks = {event: [{"hooks": [{"type": "command", "command": keep("hooks")}]}]
                 for event in events}
        settings = {"statusLine": {"type": "command",
                                   "command": keep("status") + "; echo ok"},
                    "hooks": hooks}
        if manual:
            # So a tool call asks for permission, rather than auto mode
            # deciding: the dialogs are what most questions are about.
            # `mode="plan"` starts in plan mode, for what a plan's approval
            # looks like.
            settings["permissions"] = {"defaultMode": mode}
        (self.home / ".claude").mkdir()
        (self.home / ".claude" / "settings.json").write_text(json.dumps(settings))
        env = {"HOME": str(self.home), "PATH": os.environ["PATH"],
               "TERM": "xterm-256color", "ANTHROPIC_API_KEY": key,
               "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{self.api.port}",
               "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost",
               "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
               "DISABLE_AUTOUPDATER": "1"}
        # Anything that must be in the home before Claude Code starts -- a
        # plugin installed with `claude plugin install` (#413) -- is done
        # here, with the environment Claude Code will have.
        if setup:
            setup(env)
        given = " ".join(f"{k}='{v}'" for k, v in env.items())
        self.tmux("-f", "/dev/null", "new-session", "-d", "-x", str(width),
                  "-y", "50", "-c", str(self.work), f"env -i {given} claude")
        self.pane = self.tmux("display-message", "-p", "#{pane_id}").strip()

    def __enter__(self) -> "ClaudePane":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        subprocess.run(["tmux", "-L", self.name, "kill-server"],
                       capture_output=True, timeout=10)
        self.api.close()

    def tmux(self, *args: str, stdin: bytes | None = None) -> str:
        done = subprocess.run(["tmux", "-L", self.name, *args], input=stdin,
                              capture_output=True, timeout=60)
        return done.stdout.decode("utf-8", "replace")

    def screen(self) -> str:
        return self.tmux("capture-pane", "-p", "-t", self.pane)

    def wait_for(self, words: str, seconds: float = 40) -> bool:
        """True once `words` are on the screen, False at the deadline."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if words in self.screen():
                return True
            time.sleep(0.3)
        return False

    def ready(self) -> None:
        """Past the start: the prompt is up. The question about auto mode
        that a manual start asks is answered No, with ordinary keys."""
        end = time.monotonic() + 60
        settled = None
        while time.monotonic() < end:
            shown = self.screen()
            if "Make auto mode" in shown:
                self.tmux("send-keys", "-t", self.pane, "Down")
                time.sleep(0.3)
                self.tmux("send-keys", "-t", self.pane, "Enter")
                settled = None
            elif "mode on" in shown or "for shortcuts" in shown:
                # The prompt is drawn before the question about auto mode
                # comes up over it, and a prompt sent then answered that
                # question: so the prompt has to stand for a while first.
                settled = settled or time.monotonic()
                if time.monotonic() - settled > 3:
                    return
            time.sleep(0.3)
        raise TimeoutError("Claude Code never showed its prompt:\n" + self.screen())

    def paste(self, data: bytes, bracket: bool = False) -> None:
        """Paste bytes into the pane, as wostuast's `tmux_paste` does."""
        self.tmux("load-buffer", "-b", "cp", "-", stdin=data)
        self.tmux("paste-buffer", *(["-p"] if bracket else []), "-d", "-r",
                  "-b", "cp", "-t", self.pane)

    def send(self, text: str) -> None:
        """Type a prompt and submit it, as wostuast's `tmux_send` does."""
        self.paste(text.encode(), bracket=True)
        time.sleep(0.15)
        self.paste(b"\r")

    def ask(self, tool: str, given: dict, prompt: str = "go") -> None:
        """Make the agent call `tool` with `given`: its next turn answers
        with that call. Then `paste` the keys of its dialog."""
        self.api.next_call = {"id": f"toolu_{time.monotonic_ns()}",
                              "name": tool, "input": given}
        self.send(prompt)

    def busy(self, seconds: int = 25, prompt: str = "go") -> None:
        """Start a turn that is still running when this returns: its answer
        is `sleep <seconds>` in Bash, for "what does X do while a turn
        runs" (#351). `sleep` needs no dialog, even in manual mode (2.1.288),
        so waiting for one let the turn end first. And not
        `wait_for_turns(2)`: the second request is the one after the tool's
        result, when the turn is all but over."""
        self.ask("Bash", {"command": f"sleep {seconds}", "description": "wait"},
                 prompt)
        if not self.wait_for(f"sleep {seconds}", 30):
            raise TimeoutError("the turn never started:\n" + self.screen())

    def turns(self) -> list[dict]:
        """The agent's own requests, in order: those that offer tools."""
        return [one for one in self.api.requests if one.get("tools")]

    def wait_for_turns(self, count: int, seconds: float = 60) -> bool:
        end = time.monotonic() + seconds
        while len(self.turns()) < count and time.monotonic() < end:
            time.sleep(0.2)
        return len(self.turns()) >= count

    def prompt_of(self, turn: dict) -> str:
        """The text the user sent in a turn, without system reminders."""
        users = [one for one in turn.get("messages") or [] if one.get("role") == "user"]
        said = users[-1]["content"] if users else ""
        if isinstance(said, list):
            said = "".join(part.get("text", "") for part in said
                           if part.get("type") == "text"
                           and not part.get("text", "").startswith("<system-reminder>"))
        return said

    def _kept(self, name: str) -> list[dict]:
        path = self.home / f"{name}.jsonl"
        if not path.exists():
            return []
        out = []
        for line in path.read_text().splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
        return out

    def statuses(self) -> list[dict]:
        """Every status line payload Claude Code handed over, in order."""
        return self._kept("status")

    def hooks(self) -> list[dict]:
        """Every hook payload of the `events` it was started with."""
        return self._kept("hooks")

    def settings(self) -> dict:
        """Claude Code's own settings file, as it is now: what `/model` and
        `/effort` write, measured."""
        return json.loads((self.home / ".claude" / "settings.json").read_text())


def main() -> int:
    with ClaudePane() as cc:
        cc.ready()
        cc.send("hello")
        if not cc.wait_for_turns(1):
            print(cc.screen())
            return 1
        time.sleep(2)
        print("the prompt arrived as:", repr(cc.prompt_of(cc.turns()[-1])))
        last = (cc.statuses() or [{}])[-1]
        print("status line keys:", sorted(last))
        print("hook events:", [one.get("hook_event_name") for one in cc.hooks()])
    return 0


if __name__ == "__main__":
    sys.exit(main())
