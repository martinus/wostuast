"""`tests/claude_pane.py`, the real Claude Code a measurement runs against.

It is a tool, not a test, and Claude Code is not in CI. Its fake Messages
API is the part that can break unseen, so it is held here: a stream that
says "ok", a tool call given once, and every request kept.
"""

from __future__ import annotations

import json
import urllib.request

import pytest

import claude_pane


def asked(api, body):
    request = urllib.request.Request(
        f"http://127.0.0.1:{api.port}/v1/messages", data=json.dumps(body).encode(),
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as answer:
        return answer.read().decode()


@pytest.fixture
def api():
    made = claude_pane.FakeApi()
    yield made
    made.close()


def test_a_turn_is_answered_ok_and_kept(api):
    said = asked(api, {"model": "m", "stream": True, "tools": [{"name": "Bash"}],
                       "messages": [{"role": "user", "content": "hi"}]})
    assert '"text": "ok"' in said and "message_stop" in said
    assert api.requests[-1]["messages"][0]["content"] == "hi"


def test_a_tool_call_is_given_once_and_only_to_a_turn(api):
    """A title request offers no tools: it must not take the call meant for
    the agent's turn."""
    api.next_call = {"id": "toolu_1", "name": "Bash", "input": {"command": "ls"}}
    assert '"ok"' in asked(api, {"model": "m", "stream": True, "messages": []})
    first = asked(api, {"model": "m", "stream": True, "tools": [{}], "messages": []})
    assert '"tool_use"' in first and '\\"command\\": \\"ls\\"' in first
    again = asked(api, {"model": "m", "stream": True, "tools": [{}], "messages": []})
    assert '"tool_use"' not in again


def test_a_request_without_a_stream_gets_json(api):
    said = json.loads(asked(api, {"model": "m", "messages": []}))
    assert said["content"] == [{"type": "text", "text": "ok"}]


def test_it_says_what_it_needs(monkeypatch):
    monkeypatch.setenv("PATH", "/nowhere")
    with pytest.raises(RuntimeError, match="claude and tmux"):
        claude_pane.ClaudePane()
