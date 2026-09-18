"""The daemon, driven over real HTTP against a server on a random port."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

import pytest


@pytest.fixture
def served(ws, monkeypatch):
    """A running daemon on a free port, with git stubbed out."""
    monkeypatch.setattr(ws, "git_facts_many", lambda dirs: {
        d: ws.GitFacts(repo="repo", branch="main") for d in dirs})
    monkeypatch.setattr(ws, "pid_alive", lambda pid: True)
    daemon = ws.Daemon()
    server = ws.make_server(daemon, 0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    daemon.store.refresh()
    try:
        yield daemon, f"http://127.0.0.1:{port}"
    finally:
        daemon.stopping.set()
        server.shutdown()
        server.server_close()


def get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status, json.loads(response.read())


def event(name, sid="s1", **extra):
    base = {"session_id": sid, "hook_event_name": name, "cwd": "/w/repo/dir",
            "pane": "%1", "pid": 4242, "ts": extra.pop("ts", time.time())}
    base.update(extra)
    return base


# --- the rules from PLAN.md section 4.4 and 4.4.1 ---------------------------


def test_it_listens_on_loopback_only(ws, served):
    _, base = served
    assert ws.BIND_HOST == "127.0.0.1"


def test_it_never_allows_another_site_to_read_the_answer(served):
    """No Access-Control-Allow-Origin. A page elsewhere may send a request, but
    the browser will not let it read what comes back."""
    _, base = served
    with urllib.request.urlopen(f"{base}/api/sessions", timeout=5) as response:
        assert response.headers.get("Access-Control-Allow-Origin") is None


def test_an_unknown_path_is_a_clean_404(served):
    _, base = served
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(f"{base}/api/whatever", timeout=5)
    assert caught.value.code == 404


# --- the routes --------------------------------------------------------------


def test_the_page_is_served(served):
    _, base = served
    with urllib.request.urlopen(f"{base}/", timeout=5) as response:
        assert response.status == 200
        assert "text/html" in response.headers["Content-Type"]
        assert b"<!doctype html>" in response.read().lower()


def test_sessions_are_json(ws, served):
    daemon, base = served
    ws.append_event(event("UserPromptSubmit", prompt="do it"))
    daemon.store.refresh()
    status, body = get(f"{base}/api/sessions")
    assert status == 200
    assert body["now"] > 0
    assert len(body["sessions"]) == 1
    assert body["sessions"][0]["state"] == "working"
    assert body["sessions"][0]["branch"] == "main"


def test_a_transcript_is_served(ws, served, tmp_path):
    daemon, base = served
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps({
        "type": "user", "timestamp": "2026-09-18T14:00:00.000Z",
        "message": {"role": "user", "content": "hello there"}}) + "\n")
    ws.append_event(event("SessionStart", transcript_path=str(path)))
    daemon.store.refresh()
    status, body = get(f"{base}/api/session/s1/transcript")
    assert status == 200
    assert body["id"] == "s1"
    assert [b["kind"] for b in body["blocks"]] == ["prompt"]
    assert body["blocks"][0]["text"] == "hello there"


def test_a_session_without_a_transcript_says_so(ws, served):
    daemon, base = served
    ws.append_event(event("SessionStart"))
    daemon.store.refresh()
    status, body = get(f"{base}/api/session/s1/transcript")
    assert body["blocks"] == []
    assert "missing" in body


def test_an_unknown_session_does_not_crash(served):
    _, base = served
    status, body = get(f"{base}/api/session/nope/transcript")
    assert status == 200
    assert body["blocks"] == []


# --- the live stream ---------------------------------------------------------


def read_events(url, count, timeout=10):
    """Read `count` server-sent events off the stream."""
    got = []
    with urllib.request.urlopen(url, timeout=timeout) as response:
        kind, data = "", ""
        deadline = time.time() + timeout
        while len(got) < count and time.time() < deadline:
            line = response.readline().decode("utf-8")
            if line.startswith("event: "):
                kind = line[7:].strip()
            elif line.startswith("data: "):
                data = line[6:].strip()
            elif line.strip() == "" and kind:
                got.append((kind, json.loads(data)))
                kind, data = "", ""
    return got


def test_the_stream_opens_with_the_current_sessions(ws, served):
    daemon, base = served
    ws.append_event(event("UserPromptSubmit", prompt="go"))
    daemon.store.refresh()
    got = read_events(f"{base}/api/events", 1)
    assert got[0][0] == "sessions"
    assert len(got[0][1]["sessions"]) == 1


def test_a_change_is_pushed(ws, served):
    daemon, base = served
    ws.append_event(event("UserPromptSubmit", prompt="go"))
    daemon.store.refresh()

    def later():
        time.sleep(0.3)
        ws.append_event(event("Stop", ts=time.time()))
        daemon.tick()

    threading.Thread(target=later, daemon=True).start()
    got = read_events(f"{base}/api/events", 2)
    assert [kind for kind, _ in got] == ["sessions", "sessions"]
    assert got[1][1]["sessions"][0]["state"] == "done"


def test_a_transcript_change_reaches_only_its_watcher(ws, served, tmp_path):
    daemon, base = served
    path = tmp_path / "t.jsonl"
    path.write_text("")
    ws.append_event(event("SessionStart", transcript_path=str(path)))
    daemon.store.refresh()

    def later():
        time.sleep(0.3)
        with open(path, "a") as handle:
            handle.write(json.dumps({
                "type": "assistant", "timestamp": "2026-09-18T14:00:00.000Z",
                "message": {"role": "assistant",
                            "content": [{"type": "text", "text": "a line"}]}}) + "\n")
        daemon.tick()

    threading.Thread(target=later, daemon=True).start()
    got = read_events(f"{base}/api/events?watch=s1", 2)
    assert got[1][0] == "transcript"
    assert got[1][1]["blocks"][0]["text"] == "a line"


def test_a_client_that_watches_nothing_gets_no_transcript(ws, served, tmp_path):
    daemon, base = served
    ws.append_event(event("SessionStart", transcript_path=str(tmp_path / "t.jsonl")))
    daemon.store.refresh()
    client = daemon.hub.add("")           # watching nothing
    daemon.hub.send("transcript", {"id": "s1"}, session_id="s1")
    assert client.queue.empty()


def test_a_client_is_dropped_when_it_goes(ws, served):
    daemon, _ = served
    client = daemon.hub.add("s1")
    assert daemon.hub.watchers() == {"s1"}
    daemon.hub.drop(client)
    assert daemon.hub.watchers() == set()


def test_a_slow_client_loses_old_messages_rather_than_growing(ws, served):
    daemon, _ = served
    client = daemon.hub.add()
    for i in range(ws.CLIENT_BACKLOG * 3):
        client.put(f"message {i}")
    assert client.queue.qsize() <= ws.CLIENT_BACKLOG


def test_a_broken_tick_does_not_stop_the_daemon(ws, served, monkeypatch):
    daemon, _ = served
    calls = []
    monkeypatch.setattr(daemon.store, "refresh",
                        lambda *a, **k: calls.append(1) or (_ for _ in ()).throw(
                            RuntimeError("boom")))
    daemon.stopping.clear()
    thread = threading.Thread(target=daemon.run, daemon=True)
    thread.start()
    time.sleep(0.2)
    daemon.stopping.set()
    thread.join(timeout=5)
    assert calls, "the tick never ran"


# --- what the page is sent ---------------------------------------------------


def test_a_long_tool_result_is_cut(ws):
    text = "\n".join(f"line {i}" for i in range(200))
    cut = ws.clip_lines(text, 40)
    assert cut.count("\n") == 40
    assert "160 more lines" in cut
    assert ws.clip_lines("short", 40) == "short"
    assert ws.clip_lines("", 40) == ""
