"""The daemon, driven over real HTTP against a server on a random port."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

import pytest


import conftest


def event(name, **extra):
    """A hook event stamped now, because these tests run against a live clock."""
    extra.setdefault("ts", time.time())
    return conftest.event(name, **extra)


def get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status, json.loads(response.read())


# --- the rules from PLAN.md section 4.4 and 4.4.1 ---------------------------


def test_it_listens_on_loopback_only(ws):
    """Not the constant: the socket. The page can reach the tmux verbs, so this
    port must never be offered to the network."""
    daemon = ws.Daemon()
    server = ws.make_server(daemon, 0)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()


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


def test_a_transcript_is_served(ws, served, transcript_file):
    daemon, base = served
    path = transcript_file("s1", [{
        "type": "user", "timestamp": "2026-09-18T14:00:00.000Z",
        "message": {"role": "user", "content": "hello there"}}])
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


def test_a_transcript_change_reaches_only_its_watcher(ws, served, transcript_file):
    daemon, base = served
    path = transcript_file("s1")
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


def test_a_client_that_watches_nothing_gets_no_transcript(ws, served, transcript_file):
    daemon, base = served
    ws.append_event(event("SessionStart", transcript_path=str(transcript_file("s1"))))
    daemon.store.refresh()
    client = daemon.hub.add("")           # watching nothing
    daemon.hub.send("transcript", {"id": "s1"}, session_id="s1")
    assert client.queue.empty()


def test_a_client_is_dropped_when_it_goes(served):
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


def test_a_broken_tick_does_not_stop_the_daemon(served, monkeypatch):
    daemon, _ = served
    calls = []

    def boom(*args, **kw):
        calls.append(1)
        raise RuntimeError("boom")

    monkeypatch.setattr(daemon.store, "refresh", boom)
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


def test_a_deeper_path_is_not_mistaken_for_a_session(served):
    """`startswith` plus `endswith` matched /api/session/a/b/transcript and
    took `a` for the session. The path is parsed by segment now."""
    _, base = served
    for bad in ("/api/session/a/b/transcript", "/api/session//transcript",
                "/api/session/s1", "/api/session/s1/nonsense"):
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(base + bad, timeout=5)
        assert caught.value.code == 404, bad


def test_readers_are_dropped_when_their_session_goes(ws, served, transcript_file):
    """A reader holds a whole transcript. They must not pile up."""
    daemon, _ = served
    ws.append_event(event("SessionStart",
                          transcript_path=str(transcript_file("s1"))))
    daemon.store.refresh()
    assert daemon.transcript("s1") is not None
    assert "s1" in daemon.transcripts

    # A session too old to show is forgotten, and its reader goes with it.
    daemon.store.visible(time.time() + ws.SESSION_MAX_AGE + 10)
    daemon.forget_gone()
    assert daemon.transcripts == {}


def test_a_transcript_outside_the_claude_directory_is_refused(ws, served, tmp_path):
    """The path comes out of the log, so it is input, not fact."""
    daemon, base = served
    sneaky = tmp_path / "secrets.jsonl"
    sneaky.write_text("{}\n")
    ws.append_event(event("SessionStart", transcript_path=str(sneaky)))
    daemon.store.refresh()
    assert daemon.transcript("s1") is None
    status, body = get(f"{base}/api/session/s1/transcript")
    assert body["blocks"] == []
    assert "missing" in body


def test_a_transcript_must_end_in_jsonl(ws, served, transcript_file):
    daemon, _ = served
    path = transcript_file("s1")
    other = path.with_suffix(".txt")
    other.write_text("{}\n")
    ws.append_event(event("SessionStart", transcript_path=str(other)))
    daemon.store.refresh()
    assert daemon.transcript("s1") is None


def test_a_request_for_another_host_is_refused(served):
    """Binding to loopback does not stop a site pointing its own name here."""
    daemon, base = served
    ask = urllib.request.Request(f"{base}/api/sessions",
                                 headers={"Host": "evil.example.com"})
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(ask, timeout=5)
    assert caught.value.code == 403


def test_the_reader_is_only_advanced_in_one_place(ws, served, transcript_file):
    """Two threads calling read_new at once moved the offset twice, which then
    looked like a shrinking file and re-read the whole transcript."""
    daemon, base = served
    lines = [{"type": "user", "timestamp": "2026-09-18T14:00:00.000Z",
              "message": {"role": "user", "content": f"line {i}"}} for i in range(50)]
    path = transcript_file("s1", lines)
    ws.append_event(event("SessionStart", transcript_path=str(path)))
    daemon.store.refresh()

    seen = []

    def fetch():
        seen.append(len(daemon.read_transcript("s1") or []))

    threads = [threading.Thread(target=fetch) for _ in range(8)]
    for one in threads:
        one.start()
    for one in threads:
        one.join()
    assert set(seen) == {50}, f"got {sorted(set(seen))}"
    assert len(daemon.transcript("s1").blocks) == 50


# --- the Files tab and the Diff tab ------------------------------------------


@pytest.fixture
def repo_session(ws, served, repo):
    """A session whose cwd is a real repository with one commit."""
    daemon, base = served
    ws.append_event(event("SessionStart", cwd=str(repo)))
    daemon.store.refresh()
    return repo, base


def test_the_file_listing_is_served(repo_session):
    root, base = repo_session
    status, body = get(f"{base}/api/session/s1/files")
    assert status == 200
    assert body["root"] == str(root)
    assert body["names"].split("\0") == ["README.md"]
    assert body["total"] == 1
    assert body["cut"] is False
    assert body["failed"] is False


def test_every_name_is_served_and_the_changed_ones_are_named(repo_session):
    """The names go as one string because fifty thousand objects cost
    megabytes a poll. The changed ones are a short list of their own."""
    root, base = repo_session
    (root / "notes.md").write_text("# notes\n")
    (root / "deep").mkdir()
    (root / "deep" / "code.py").write_text("print(1)\n")
    status, body = get(f"{base}/api/session/s1/files")
    assert status == 200
    assert sorted(body["names"].split("\0")) == ["README.md", "deep/code.py",
                                                 "notes.md"]
    assert sorted(body["changed"]) == ["deep/code.py", "notes.md"]


def test_one_file_is_served(repo_session):
    _, base = repo_session
    status, body = get(f"{base}/api/session/s1/file?path=README.md")
    assert status == 200
    assert body["text"] == "# readme\n\nhello\n"


def test_a_file_the_listing_does_not_offer_is_a_404(repo_session):
    _, base = repo_session
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(f"{base}/api/session/s1/file?path=../../etc/passwd",
                               timeout=5)
    assert caught.value.code == 404


def test_the_diff_is_served(repo_session):
    root, base = repo_session
    (root / "README.md").write_text("# readme\n\nchanged\n")
    status, body = get(f"{base}/api/session/s1/diff")
    assert status == 200
    assert body["base"] == "main"
    names = [section["name"] for section in body["sections"]]
    assert names == ["committed", "uncommitted"]
    changed = body["sections"][1]["files"]
    assert [one["path"] for one in changed] == ["README.md"]
    assert changed[0]["hunks"][0]["lines"][-1]["kind"] == "added"


def test_a_session_that_is_gone_is_a_404_on_every_new_route(served):
    _, base = served
    for verb in ("files", "file", "diff"):
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(f"{base}/api/session/nobody/{verb}", timeout=5)
        assert caught.value.code == 404


# --- the page's one external dependency -------------------------------------


def fetched_scripts(page):
    """Every script the page fetches, as (name, url, hash)."""
    import re

    found = []
    for name in ("MARKED", "HLJS"):
        where = re.search(name + r'_SRC =\n  "([^"]+)"', page)
        pinned = re.search(name + r'_HASH =\n  "([^"]+)"', page)
        assert where and pinned, name
        found.append((name, where.group(1), pinned.group(1)))
    return found


def test_every_fetched_script_is_pinned(ws):
    """Any script on this page can POST to /send, which types into a terminal.
    So each one carries the hash of its exact bytes, over https, and the
    browser refuses anything else."""
    for name, where, pinned in fetched_scripts(ws.PAGE):
        assert where.startswith("https://"), name
        assert pinned.startswith("sha384-"), name
    assert "tag.integrity = hash;" in ws.PAGE
    assert 'tag.crossOrigin = "anonymous";' in ws.PAGE
    # One fetcher, so there is one place where a hash could be dropped.
    assert ws.PAGE.count("document.head.appendChild(tag)") == 1


def test_the_pins_still_match_what_the_cdn_serves(ws):
    """A hash that has drifted from the file it names means the script is
    refused for everyone, and nothing else would say so. Skipped offline."""
    import base64
    import hashlib

    for name, where, pinned in fetched_scripts(ws.PAGE):
        try:
            raw = urllib.request.urlopen(where, timeout=30).read()
        except (urllib.error.URLError, OSError) as error:   # offline, blocked
            pytest.skip(f"cannot reach {where}: {error}")
        got = "sha384-" + base64.b64encode(hashlib.sha384(raw).digest()).decode()
        assert got == pinned, name


def test_the_marked_fixture_is_the_pinned_one(ws):
    """The page tests serve marked from tests/fixtures, and the browser checks
    the page's own hash against it. If the two drift apart every page test
    fails at once, so they are compared here where the reason is plain."""
    import base64
    import hashlib
    from pathlib import Path

    raw = (Path(__file__).resolve().parent / "fixtures" / "marked.min.js"
           ).read_bytes()
    got = "sha384-" + base64.b64encode(hashlib.sha384(raw).digest()).decode()
    pinned = dict((name, hash_) for name, _, hash_ in fetched_scripts(ws.PAGE))
    assert got == pinned["MARKED"]
