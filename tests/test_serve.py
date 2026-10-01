"""The daemon, driven over real HTTP against a server on a random port."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
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


# --- the rules for the HTTP surface: CLAUDE.md, the Safety section ----------


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


def test_the_settings_route_carries_the_settings_and_the_trouble(ws, served):
    """The usable settings, every link as written with what is wrong with it,
    and where the file is. The trouble too, because the page cannot tell "no
    links" from "your file is broken" on its own -- and the difference is the
    whole of the reader's problem."""
    _, base = served
    ws.config_path().parent.mkdir(parents=True, exist_ok=True)
    ws.config_path().write_text(json.dumps({"colours": "dark", "links": [
        {"match": r"OK-(\d+)", "url": "https://tickets/$1"},
        {"match": "BAD-(", "url": "https://tickets/"},
    ]}), encoding="utf-8")
    status, body = get(f"{base}/api/settings")
    assert status == 200
    assert body["colours"] == "dark"
    assert [one["trouble"] == "" for one in body["links"]] == [True, False]
    assert len(body["trouble"]) == 1 and "link 2" in body["trouble"][0]
    assert body["path"].endswith("settings.json")


def test_the_page_is_served_with_the_settings_in_it(ws, served):
    """So the first paint has the reader's colours: a fetch after the page
    has drawn is a flash of the wrong ones."""
    _, base = served
    ws.save_config({"colours": "light",
                    "links": [{"match": "</script>(\\d+)", "url": "https://t/$1"}]})
    with urllib.request.urlopen(f"{base}/", timeout=5) as response:
        page = response.read().decode("utf-8")
    assert "__WOSTUAST_SETTINGS__" not in page
    held = page.split("var SETTINGS = ", 1)[1].split(";\n", 1)[0]
    assert json.loads(held)["colours"] == "light"
    # The reader's text cannot end the script it stands in.
    assert "</script>(" not in page


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


def test_a_transcript_the_page_holds_whole_is_not_sent_again(
        ws, served, transcript_file):
    """Coming back to the Transcript tab fetched the whole of it every time:
    856 KB for four hundred rounds, five seconds on a slow link, for blocks
    the pushes had already brought. A page that names the reading it holds
    gets `same` and no blocks; one that names anything else gets them all."""
    daemon, base = served
    path = transcript_file("s1", [conftest.record("you", "hello there")])
    ws.append_event(event("SessionStart", transcript_path=str(path)))
    daemon.store.refresh()
    _, first = get(f"{base}/api/session/s1/transcript")
    held = f"{first['run']}.{first['version']}"
    _, again = get(f"{base}/api/session/s1/transcript?have={held}")
    assert again["same"] is True and "blocks" not in again
    assert (again["run"], again["version"]) == (first["run"], first["version"])
    stale = f"{first['run']}.{first['version'] - 1}"
    _, behind = get(f"{base}/api/session/s1/transcript?have={stale}")
    assert "same" not in behind
    assert [b["text"] for b in behind["blocks"]] == ["hello there"]
    # Something new read on the way is news, even to a page that was whole.
    with path.open("a") as out:
        out.write(conftest.records(conftest.record("you", "and again")))
    _, moved = get(f"{base}/api/session/s1/transcript?have={held}")
    assert "same" not in moved
    assert [b["text"] for b in moved["blocks"]] == ["hello there", "and again"]


def fetch_packed(url, accept):
    """The answer's headers and its bytes as they came, before any unpacking."""
    request = urllib.request.Request(url)
    if accept is not None:
        request.add_header("Accept-Encoding", accept)
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.headers, response.read()


def test_text_is_packed_for_a_client_that_takes_gzip(ws, served,
                                                    transcript_file):
    """The page reaches the daemon through an ssh tunnel as often as not,
    and on one at 200 KiB/s the first look at the Files tab of 53,000 files
    took twenty seconds. Text packs to about a twentieth. A client that did
    not ask for gzip, or said `q=0`, gets the bytes as they are."""
    import gzip

    daemon, base = served
    headers, body = fetch_packed(f"{base}/", "gzip, deflate, br")
    assert headers["Content-Encoding"] == "gzip"
    assert "Accept-Encoding" in headers["Vary"]
    assert int(headers["Content-Length"]) == len(body)
    page = gzip.decompress(body)
    assert b"<!doctype html>" in page.lower()
    assert len(body) * 3 < len(page)
    for accept in (None, "identity", "gzip;q=0", "br, gzip; q=0.0"):
        headers, body = fetch_packed(f"{base}/", accept)
        assert headers["Content-Encoding"] is None, accept
        assert b"<!doctype html>" in body.lower()
    headers, _ = fetch_packed(f"{base}/", "*")
    assert headers["Content-Encoding"] == "gzip"
    # JSON too, which is what the Files tab and the transcript are.
    path = transcript_file("s1", [conftest.record("you", "hello there " * 200)])
    ws.append_event(event("SessionStart", transcript_path=str(path)))
    daemon.store.refresh()
    headers, body = fetch_packed(f"{base}/api/session/s1/transcript", "gzip")
    assert headers["Content-Encoding"] == "gzip"
    assert json.loads(gzip.decompress(body))["blocks"][0]["kind"] == "prompt"
    # A small answer is not worth the packing.
    headers, body = fetch_packed(f"{base}/api/session/nope/transcript", "gzip")
    assert headers["Content-Encoding"] is None
    assert json.loads(body)["blocks"] == []


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


def read_events(url, count, timeout=10, then=None):
    """Read `count` server-sent events off the stream.

    `then` runs once the first event is in, and that is the only safe moment
    to make a change the stream should carry. The stream joins the hub before
    it writes its first event, so after that event nothing pushed is lost.
    A change made from a thread after a fixed sleep raced the connection: on
    a loaded runner the stream opened after the push, already showed the new
    state, and the read waited for a second event that never came.
    """
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
                if then and len(got) == 1:
                    then()
    return got


def test_a_stream_too_slow_to_keep_up_is_closed_and_never_given_a_gap(
        ws, served):
    """A stream that cannot take its pushes as fast as they come fills its
    queue, and `Client.put` dropped the oldest one and said nothing. The page
    then took the newer pushes, its `version` passed the lost block, and
    neither a fetch (`?have=` answers `same`) nor a reconnect (its opening is
    not ahead) asked for it again: a block gone for good (#235). Now the
    stream closes at the first push it cannot keep, so what arrived has no
    gap, and the page reconnects behind the daemon and fetches."""
    import socket as sockets
    from urllib.parse import urlparse

    daemon, base = served
    where = urlparse(base)
    sock = sockets.socket()
    # A small window, so the daemon's writer blocks after a few pushes, as
    # it does behind a slow ssh tunnel, and its queue fills.
    sock.setsockopt(sockets.SOL_SOCKET, sockets.SO_RCVBUF, 4096)
    sock.settimeout(10)
    sock.connect((where.hostname, where.port))
    try:
        sock.sendall(b"GET /api/events?watch=s1 HTTP/1.1\r\n"
                     b"Host: localhost\r\n\r\n")
        got = b""
        while b"event: sessions" not in got:       # the stream is in the hub
            got += sock.recv(4096)
        pad = "x" * (256 * 1024)
        for n in range(60):
            daemon.hub.send("transcript", {"id": "s1", "n": n, "pad": pad}, "s1")
        closed = False
        while True:
            try:
                piece = sock.recv(1 << 20)
            except (TimeoutError, OSError):
                break
            if not piece:
                closed = True
                break
            got += piece
    finally:
        sock.close()
    numbers = [int(n) for n in re.findall(rb'"n": (\d+)', got)]
    assert numbers and numbers == list(range(len(numbers))), numbers
    assert len(numbers) < 60
    assert closed, "the stream went on after a push it could not keep"


def test_a_lone_surrogate_in_a_transcript_breaks_nothing(ws, served,
                                                        transcript_file):
    """Claude Code cuts a string between the halves of an emoji and writes
    the escape; json.loads makes it a real lone surrogate, and a strict
    encode refused the whole answer. The transcript answered 500 on every
    request, and a push wrote an HTTP 500 into the middle of the stream.
    Build one with `chr`, never with its escape in source."""
    daemon, base = served
    cut = "cut here: " + chr(0xD83D)
    path = transcript_file("s1", [
        {"type": "user", "timestamp": "2026-09-18T14:02:00.000Z",
         "message": {"role": "user", "content": cut}}])
    ws.append_event(event("SessionStart", transcript_path=str(path)))
    daemon.store.refresh()
    with urllib.request.urlopen(f"{base}/api/session/s1/transcript",
                                timeout=5) as answer:
        assert answer.status == 200
        assert json.loads(answer.read())["blocks"]

    def later():
        with path.open("a") as out:
            out.write(json.dumps(
                {"type": "user", "timestamp": "2026-09-18T14:03:00.000Z",
                 "message": {"role": "user", "content": "again " + chr(0xD83D)}})
                + "\n")
        daemon.tick()

    got = read_events(f"{base}/api/events?watch=s1", 2, then=later)
    kinds = [kind for kind, _ in got]
    assert "transcript" in kinds, got


def test_a_transcript_push_leaves_under_the_lock(ws, served, transcript_file,
                                                 monkeypatch):
    """A push made after the lock let go could overtake one read before it,
    and the page, which patches by index, then never drew the earlier
    block. Pushed under the lock, the order sent is the order read."""
    daemon, base = served
    path = transcript_file("s1", [
        {"type": "user", "timestamp": "2026-09-18T14:02:00.000Z",
         "message": {"role": "user", "content": "go"}}])
    ws.append_event(event("SessionStart", transcript_path=str(path)))
    daemon.store.refresh()
    held = []
    real = daemon.hub.send

    def spy(kind, data, session_id=""):
        if kind == "transcript":
            held.append(daemon.lock.locked())
        real(kind, data, session_id=session_id)

    monkeypatch.setattr(daemon.hub, "send", spy)
    daemon.read_transcript("s1")
    assert held == [True]


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
        ws.append_event(event("Stop", ts=time.time()))
        daemon.tick()

    got = read_events(f"{base}/api/events", 2, then=later)
    assert [kind for kind, _ in got] == ["sessions", "sessions"]
    assert got[1][1]["sessions"][0]["state"] == "done"


def test_a_transcript_change_reaches_only_its_watcher(ws, served, transcript_file):
    daemon, base = served
    path = transcript_file("s1")
    ws.append_event(event("SessionStart", transcript_path=str(path)))
    daemon.store.refresh()

    def later():
        with open(path, "a") as handle:
            handle.write(json.dumps({
                "type": "assistant", "timestamp": "2026-09-18T14:00:00.000Z",
                "message": {"role": "assistant",
                            "content": [{"type": "text", "text": "a line"}]}}) + "\n")
        daemon.tick()

    got = read_events(f"{base}/api/events?watch=s1", 2, then=later)
    assert got[1][0] == "transcript"
    assert got[1][1]["blocks"][0]["text"] == "a line"


def test_a_stream_decides_its_opening_before_it_says_anything(
        ws, served, transcript_file, monkeypatch):
    """The stream wrote `sessions` and only then asked whether it held a
    transcript to open on. The socket is not buffered, so a reader that saw
    `sessions` made its change -- a tick that starts reading the transcript
    -- inside that gap, and got an opening in front of the block it waited
    for. It failed CI by chance; a slow `transcript_held` is the gap held
    open on purpose."""
    daemon, base = served
    path = transcript_file("s1")
    ws.append_event(event("SessionStart", transcript_path=str(path)))
    daemon.store.refresh()
    asked = daemon.transcript_held

    def slow(session_id):
        time.sleep(0.3)
        return asked(session_id)

    monkeypatch.setattr(daemon, "transcript_held", slow)

    def later():
        with open(path, "a") as handle:
            handle.write(json.dumps(conftest.record("claude", "a line")) + "\n")
        daemon.tick()

    got = read_events(f"{base}/api/events?watch=s1", 2, then=later)
    assert got[1][0] == "transcript" and "opening" not in got[1][1], got[1]
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


def test_a_slow_client_is_closed_rather_than_growing(ws, served):
    """It never grows, and it keeps nothing after a message it lost: the
    stream closes on the wake-up left in the queue."""
    daemon, _ = served
    client = daemon.hub.add()
    for i in range(ws.CLIENT_BACKLOG * 3):
        client.put(f"message {i}")
    assert client.queue.qsize() <= ws.CLIENT_BACKLOG
    assert client.lost
    assert [client.queue.get_nowait() for _ in range(client.queue.qsize())] == [""]


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
        found = daemon.read_transcript("s1")
        seen.append(len(found[0]) if found else 0)

    threads = [threading.Thread(target=fetch) for _ in range(8)]
    for one in threads:
        one.start()
    for one in threads:
        one.join()
    assert set(seen) == {50}, f"got {sorted(set(seen))}"
    assert len(daemon.transcript("s1").blocks) == 50


def test_a_transcript_emptied_under_its_name_reaches_the_watchers(
        ws, served, transcript_file):
    """A rewrite that leaves nothing changes no block, so there was nothing to
    push — and the page went on showing a conversation the file no longer
    holds, until something else happened to be written.

    The run is pushed when it moves, whether or not a block came with it."""
    daemon, _ = served
    path = transcript_file("s1", [
        {"type": "user", "timestamp": "2026-09-18T14:00:00.000Z",
         "message": {"role": "user", "content": "the old conversation"}}])
    ws.append_event(event("SessionStart", transcript_path=str(path)))
    daemon.store.refresh()
    daemon.read_transcript("s1")

    sent = []
    daemon.hub.send = lambda name, body, **rest: sent.append((name, body))
    path.write_text("")                   # same inode, nothing left in it

    blocks, run, _ = daemon.read_transcript("s1")
    assert blocks == []
    assert sent and sent[0][1]["run"] == run
    assert sent[0][1]["blocks"] == []


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


def test_a_diff_the_page_holds_is_not_sent_again(repo_session):
    """The Review tab asks every five seconds, and the answer was the whole
    diff every time: on a slow link the one transfer that never stopped. The
    page sends back the tag of the diff it holds, and a diff that still
    stands is answered with no diff; one that moved comes whole, tag and
    all."""
    root, base = repo_session
    (root / "README.md").write_text("# readme\n\nchanged\n")
    _, first = get(f"{base}/api/session/s1/diff")
    tag = first["tag"]
    assert tag and first["sections"]
    _, again = get(f"{base}/api/session/s1/diff?have={tag}")
    assert again == {"id": "s1", "tag": tag, "same": True}
    (root / "README.md").write_text("# readme\n\nchanged again\n")
    _, moved = get(f"{base}/api/session/s1/diff?have={tag}")
    assert "same" not in moved and moved["tag"] != tag
    assert moved["sections"][1]["files"][0]["path"] == "README.md"


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


def test_a_listing_that_has_not_moved_sends_no_names(repo_session):
    """Fifty thousand names weigh 1.7 MB and change when a file is added or
    removed, which is rare. Which files changed moves every few seconds and is
    a few hundred bytes. So the browser sends back the tag it holds."""
    root, base = repo_session
    status, first = get(f"{base}/api/session/s1/files")
    assert status == 200
    assert first["tag"]
    assert "names" in first

    status, again = get(f"{base}/api/session/s1/files?have={first['tag']}")
    assert status == 200
    assert again["tag"] == first["tag"]
    assert "names" not in again
    assert again["total"] == first["total"]

    # A tag we do not hold gets the names back.
    status, other = get(f"{base}/api/session/s1/files?have=notthisone")
    assert other["names"] == first["names"]


def test_a_new_file_moves_the_tag(repo_session):
    root, base = repo_session
    _, first = get(f"{base}/api/session/s1/files")
    (root / "fresh.txt").write_text("new\n")
    # The listing is held for a few seconds, so wait for it to be read again.
    for _ in range(60):
        time.sleep(0.25)
        _, again = get(f"{base}/api/session/s1/files?have={first['tag']}")
        if again["tag"] != first["tag"]:
            break
    assert again["tag"] != first["tag"]
    assert "fresh.txt" in again["names"].split("\0")


# --- the tmux verbs over HTTP -----------------------------------------------

# Every POST here types into a terminal, which is why each carries a token and
# an Origin check (CLAUDE.md: "Every POST carries a token"). These tests are
# that rule.


def post(url, body=None, token=None, origin=None, timeout=5):
    """A POST, with whatever headers the test wants to get wrong."""
    raw = json.dumps(body or {}).encode()
    ask = urllib.request.Request(url, data=raw, method="POST")
    ask.add_header("Content-Type", "application/json")
    if token is not None:
        ask.add_header("X-Wostuast-Token", token)
    if origin is not None:
        ask.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(ask, timeout=timeout) as answer:
            return answer.status, json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        return refused.status, json.loads(refused.read())


@pytest.fixture
def in_tmux(ws, served, monkeypatch):
    """A session in a pane, with tmux replaced by a runner that records."""
    seen = []

    def runner(args, **rest):
        seen.append(list(args))
        return ""

    monkeypatch.setattr(ws, "run", runner)
    daemon, base = served
    ws.append_event(event("SessionStart", pane="%7", pid=1))
    daemon.store.refresh()
    return daemon, base, seen


def test_a_post_without_the_token_does_nothing(in_tmux):
    """Any site can send this daemon a POST. Only a page that has read the
    token can send one that acts."""
    daemon, base, seen = in_tmux
    status, body = post(f"{base}/api/session/s1/send", {"text": "rm -rf /"})
    assert status == 403
    assert seen == [], "it typed into the terminal without the token"

    status, body = post(f"{base}/api/session/s1/jump", token="not-the-token")
    assert status == 403
    assert seen == []


def test_a_post_from_another_site_does_nothing(in_tmux):
    """Even holding the token, an Origin that is not ours is refused."""
    daemon, base, seen = in_tmux
    status, _ = post(f"{base}/api/session/s1/send", {"text": "hello"},
                     token=daemon.token, origin="https://evil.example")
    assert status == 403
    assert seen == []


def test_a_page_from_an_earlier_serve_is_told_to_reload(in_tmux):
    """The token is made fresh in `Daemon.__init__`, so restarting `serve`
    leaves every open page holding one this daemon never knew. The stream is
    a GET and reconnects, so the sidebar goes on moving and the page looks
    alive while every POST is refused -- in every session at once, because
    the token belongs to the daemon and not to a session.

    "That did not come from this page" is true and useless: it came from the
    page, one `serve` ago. Only the page can say what to do about it, so the
    daemon has to tell it which refusal this is.
    """
    daemon, base, seen = in_tmux
    status, body = post(f"{base}/api/session/s1/send", {"text": "hello"},
                        token="the-token-from-the-last-serve",
                        origin=f"http://127.0.0.1:1234")
    assert status == 403
    assert body["stale"] is True
    assert "restarted" in body["error"] and "Reload" in body["error"]
    assert seen == [], "it typed into the terminal on a refused POST"


def test_a_caller_with_no_token_is_told_nothing_of_the_sort(in_tmux):
    """It never had a token, so it is not a page of ours that went out of
    date -- and a stranger is told nothing it did not already know."""
    daemon, base, seen = in_tmux
    status, body = post(f"{base}/api/session/s1/send", {"text": "rm -rf /"})
    assert status == 403
    assert "stale" not in body
    assert body["error"] == "that did not come from this page"


def test_another_site_holding_a_wrong_token_is_not_a_stale_page(in_tmux):
    """It fails the Origin check, which no page of ours ever does. Reading
    `stale` off the token alone would have handed that wording to a caller
    that is not a page of ours at all."""
    daemon, base, seen = in_tmux
    status, body = post(f"{base}/api/session/s1/send", {"text": "hello"},
                        token="a-guess", origin="https://evil.example")
    assert status == 403
    assert "stale" not in body
    assert seen == []


def test_a_post_from_this_page_acts(in_tmux):
    daemon, base, seen = in_tmux
    status, body = post(f"{base}/api/session/s1/send", {"text": "run the tests"},
                        token=daemon.token, origin="http://127.0.0.1:1234")
    assert status == 200
    assert body["done"] is True
    assert seen == [
        ["tmux", "send-keys", "-t", "%7", "-l", "--", "run the tests"],
        ["tmux", "send-keys", "-t", "%7", "Enter"],
    ]


def test_jump_picks_the_window_and_the_pane(in_tmux):
    daemon, base, seen = in_tmux
    status, body = post(f"{base}/api/session/s1/jump", token=daemon.token)
    assert status == 200 and body["done"] is True
    assert seen[0] == ["tmux", "select-window", "-t", "%7"]


# --- another user on the same machine (issue #227) ---------------------------
#
# 127.0.0.1 is open to every account on the machine, and `GET /` hands out the
# page with the token in it. So the daemon reads the owner of the other end of
# each connection out of /proc/net/tcp, and answers its own user only.

# Lines as Linux 6.18 wrote them on x86, for a connection from `nobody`
# (uid 65534) at 127.0.0.1:38242 to a daemon run by root at 127.0.0.1:7427.
# The kernel prints each word of an address in the machine's byte order.
LISTENING = ("   4: 0100007F:1D03 00000000:0000 0A 00000000:00000000 00:00000000"
             " 00000000     0        0 494468 1 00000000a3dbac1d 100 0 0 10 0")
THEIR_END = ("   8: 0100007F:9562 0100007F:1D03 01 00000000:00000000 02:0000170C"
             " 00000000 65534        0 496535 2 000000001e7172b0 20 4 28 11 -1")
OUR_END = ("  15: 0100007F:1D03 0100007F:9562 01 00000000:00000000 00:00000000"
           " 00000000     0        0 498793 1 00000000225510a4 20 4 31 12 -1")
# A closed connection with the same two ends: the kernel lists it as uid 0.
CLOSED = ("   9: 0100007F:9562 0100007F:1D03 06 00000000:00000000 03:000011F4"
          " 00000000     0        0 0 3 000000005efeac10")
# The same client port to another server port, owned by somebody else again.
ELSEWHERE = ("  11: 0100007F:9562 0100007F:1D04 01 00000000:00000000 00:00000000"
             " 00000000  1001        0 498800 1 0000000000000000 20 4 31 12 -1")
HEADER = ("  sl  local_address rem_address   st tx_queue rx_queue tr tm->when"
          " retrnsmt   uid  timeout inode")
PEER, OURS = ("127.0.0.1", 0x9562), ("127.0.0.1", 0x1D03)

little_endian = pytest.mark.skipif(
    sys.byteorder != "little", reason="the lines above are as x86 writes them")


def table(*lines):
    return "\n".join((HEADER,) + lines) + "\n"


@little_endian
def test_a_socket_is_found_by_both_of_its_ends(ws):
    """Both ends, or the other connection from the same port would answer,
    and a closed one with the same ends is nobody's and reads as root."""
    text = table(LISTENING, CLOSED, ELSEWHERE, OUR_END, THEIR_END)
    assert ws.table_address("127.0.0.1", 7427) == "0100007F:1D03"
    assert ws.socket_owner(text, PEER, OURS) == 65534
    assert ws.socket_owner(text, OURS, PEER) == 0
    assert ws.socket_owner(text, PEER, ("127.0.0.1", 0x1D04)) == 1001
    assert ws.socket_owner(text, ("127.0.0.1", 1), OURS) is None
    assert ws.socket_owner(table(LISTENING, CLOSED), PEER, OURS) is None


# The same ends after the client sent a request and closed its socket, as
# Linux 6.18 lists them: FIN_WAIT2, uid 0, inode 0 -- no process holds it.
# And after the client only shut down its write half: FIN_WAIT2 too, but
# its own uid and inode, and it can still read the answer.
ORPHANED = ("8974: 0100007F:9562 0100007F:1D03 05 00000000:00000000 03:00001755"
            " 00000000     0        0 0 3 0000000024776677")
HALF_SHUT = ("9083: 0100007F:9562 0100007F:1D03 05 00000000:00000000 00:00000000"
             " 00000000 65534        0 1847845 1 00000000015d2ef5 20 0 0 12 -1")


@little_endian
def test_a_socket_no_process_holds_is_nobodys(ws):
    """Another user connected, sent a request and closed the socket before
    the daemon looked. The kernel then lists it with uid 0, which is root's
    and was let in, and the request was served (#254). A line with no inode
    is skipped, as a `TIME_WAIT` line is. A client that only shut down its
    write half still holds its socket, and is still who it is."""
    assert ws.socket_owner(table(LISTENING, OUR_END, ORPHANED), PEER, OURS) is None
    reads = lambda path: table(LISTENING, OUR_END, ORPHANED)
    assert ws.another_user(PEER, OURS, 1000, reads, ("t",)) is True
    assert ws.another_user(PEER, OURS, 0, reads, ("t",)) is True
    half = table(LISTENING, OUR_END, HALF_SHUT)
    assert ws.socket_owner(half, PEER, OURS) == 65534
    assert ws.another_user(PEER, OURS, 65534, lambda path: half, ("t",)) is False


@little_endian
def test_a_client_on_an_ipv6_socket_is_found_in_tcp6(ws):
    """A dual-stack client reaches 127.0.0.1 as ::ffff:127.0.0.1, and Linux
    lists it in /proc/net/tcp6, in the shape of `tcp6_seq_show`."""
    mapped = "0000000000000000FFFF00000100007F"
    line = (f"   0: {mapped}:9562 {mapped}:1D03 01 00000000:00000000"
            " 00:00000000 00000000  1000        0 12345 1 0000000000000000"
            " 20 4 30 10 -1")
    assert ws.table_address("127.0.0.1", 0x9562, six=True) == f"{mapped}:9562"
    assert ws.socket_owner(table(line), PEER, OURS) == 1000

    reads = {"/proc/net/tcp": table(LISTENING, OUR_END),
             "/proc/net/tcp6": table(line)}
    assert ws.another_user(PEER, OURS, 1000, reads.get) is False
    assert ws.another_user(PEER, OURS, 0, reads.get) is True


@little_endian
def test_only_the_daemons_own_user_is_let_in(ws):
    """Its own user, yes; any other, no; one the table does not list, no --
    the other end is open as long as the connection is, so that is not
    normal. No table at all is a machine without /proc, and stays as it was.
    """
    def reading(text):
        asked = []

        def read(path):
            asked.append(path)
            return text
        return read, asked

    whole = table(LISTENING, OUR_END, THEIR_END)
    assert ws.another_user(PEER, OURS, 65534, reading(whole)[0], ("t",)) is False
    assert ws.another_user(PEER, OURS, 0, reading(whole)[0], ("t",)) is True

    read, asked = reading(table(LISTENING, OUR_END))
    assert ws.another_user(PEER, OURS, 65534, read, ("t",)) is True
    assert len(asked) == ws.PEER_READS, "a line not found was not read again"

    assert ws.another_user(PEER, OURS, 65534, lambda path: None, ("t",)) is False
    # A real table always lists our own listening socket, so an empty one
    # is not a real table: nothing to check against, as with none at all.
    assert ws.another_user(PEER, OURS, 65534, reading(table())[0], ("t",)) is False


@little_endian
def test_root_is_let_in_too(ws):
    """In WSL2's default NAT mode a Windows browser reaches 127.0.0.1 in the
    VM through a relay that runs as root there, so an own-uid-only check
    refused the owner. Root can read the token and every transcript anyway."""
    by_root = THEIR_END.replace(" 65534 ", "     0 ")
    text = table(LISTENING, OUR_END, by_root)
    assert ws.socket_owner(text, PEER, OURS) == 0
    assert ws.another_user(PEER, OURS, 1000, lambda path: text, ("t",)) is False
    assert ws.another_user(PEER, OURS, 1000, lambda path: table(
        LISTENING, OUR_END, THEIR_END), ("t",)) is True


@little_endian
def test_a_line_the_kernel_skipped_once_is_looked_for_again(ws):
    """The kernel writes the table a page at a time and resumes by position,
    so a table that changes during the read can leave a line out."""
    answers = [table(LISTENING), table(LISTENING, OUR_END, THEIR_END)]
    assert ws.another_user(PEER, OURS, 65534, lambda path: answers.pop(0),
                       ("t",)) is False


needs_tables = pytest.mark.skipif(
    not os.path.exists("/proc/net/tcp"),
    reason="no /proc/net/tcp here, so the daemon cannot tell who connects")


@needs_tables
def test_a_connection_from_another_user_gets_nothing(ws, in_tmux,
                                                    monkeypatch):
    """The page, the stream, the JSON and every POST -- the token included.
    The daemon is told it runs as another user, so this runs as anybody."""
    daemon, base, seen = in_tmux
    with urllib.request.urlopen(f"{base}/", timeout=5) as answer:
        assert daemon.token.encode() in answer.read(), "the owner is refused"

    daemon.uid = os.getuid() + 1
    # Root is let in as well, and this suite may run as root.
    monkeypatch.setattr(ws, "ROOT_UID", -1)
    for path in ("/", "/api/events", "/api/sessions",
                 "/api/session/s1/transcript"):
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(f"{base}{path}", timeout=5)
        assert caught.value.code == 403, path
        said = caught.value.read()
        assert daemon.token.encode() not in said, path
        assert json.loads(said)["error"] == ws.STRANGER, path
    status, body = post(f"{base}/api/session/s1/send", {"text": "!id"},
                        token=daemon.token, origin="http://127.0.0.1:1234")
    assert (status, body["error"]) == (403, ws.STRANGER)
    assert seen == [], "another user typed into the terminal"


@needs_tables
def test_a_table_that_cannot_be_read_refuses(ws, served, monkeypatch,
                                             tmp_path):
    """Running out of files is something another user can cause, so a table
    that is there and cannot be read is a no, never the way it was before.
    Only a table that is not there at all is a machine without one."""
    _, base = served
    assert ws.read_table(str(tmp_path / "no-such-table")) is None
    with pytest.raises(OSError):
        ws.read_table(str(tmp_path))  # there, and not a file one can read

    def cannot(path):
        raise OSError(24, "Too many open files")
    monkeypatch.setattr(ws, "read_table", cannot)
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(f"{base}/api/sessions", timeout=5)
    assert caught.value.code == 403


@needs_tables
@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="only root can run a request as another user")
@pytest.mark.skipif(shutil.which("setpriv") is None, reason="needs setpriv")
def test_a_real_request_from_another_user_is_refused(ws, served):
    """Not a daemon told it is somebody else: a request made as `nobody`."""
    daemon, base = served
    ask = ("import urllib.request, urllib.error, sys\n"
           "try:\n"
           f"    urllib.request.urlopen('{base}/', timeout=5)\n"
           "    print(200)\n"
           "except urllib.error.HTTPError as e:\n"
           "    print(e.code, e.read().decode())\n")
    done = subprocess.run(
        ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups",
         sys.executable, "-c", ask],
        capture_output=True, text=True, timeout=30)
    assert done.stdout.startswith("403"), done.stdout + done.stderr
    assert daemon.token not in done.stdout


@needs_tables
@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="only root can run a request as another user")
@pytest.mark.skipif(shutil.which("setpriv") is None, reason="needs setpriv")
def test_a_request_from_another_user_that_closed_first_is_refused(
        ws, served, monkeypatch):
    """As `nobody`: connect, send a request, close. Under load the daemon
    reads the table after the close, and the line then says uid 0 (#254).
    The read is made late here, so it comes after the close every time.
    The daemon is told it runs as another user than root, as the owner of
    a real machine is, and root stays let in."""
    daemon, base = served
    daemon.uid = 12345
    assert ws.ROOT_UID == 0
    real_read, said = ws.read_table, []

    def late(path):
        time.sleep(0.5)
        return real_read(path)

    def recorded(*args, **rest):
        said.append(ws_another_user(*args, **rest))
        return said[-1]

    ws_another_user = ws.another_user
    monkeypatch.setattr(ws, "read_table", late)
    monkeypatch.setattr(ws, "another_user", recorded)
    port = base.rsplit(":", 1)[1]
    ask = ("import socket\n"
           f"s = socket.create_connection(('127.0.0.1', {port}))\n"
           "s.sendall(b'GET /api/sessions HTTP/1.1\\r\\nHost: localhost\\r\\n\\r\\n')\n"
           "s.close()\n")
    subprocess.run(["setpriv", "--reuid=65534", "--regid=65534",
                    "--clear-groups", sys.executable, "-c", ask],
                   check=True, capture_output=True, timeout=30)
    deadline = time.monotonic() + 15
    while not said and time.monotonic() < deadline:
        time.sleep(0.05)
    assert said == [True], "a closed socket of another user was let in"


def test_the_token_is_in_the_page_and_is_not_the_mark(served):
    daemon, base = served
    with urllib.request.urlopen(f"{base}/", timeout=5) as answer:
        page = answer.read().decode()
    assert daemon.token in page
    assert ws_token_mark() not in page


def ws_token_mark():
    return "__WOSTUAST_" + "TOKEN__"


def test_the_page_says_which_copy_is_running(served, ws):
    """The name at the top of the session list carries a version: the day
    the running file was written and the start of the SHA-256 of its bytes.
    Nothing to raise by hand, and two copies that say the same are the same
    bytes, which is what `install_behind` compares."""
    import hashlib
    import re
    from pathlib import Path
    daemon, base = served
    said = ws.own_version()
    day, _, digest = said.partition(" \u00b7 ")
    assert re.fullmatch(r"\d{4}-\d\d-\d\d", day)
    here = Path(ws.__file__).read_bytes()
    assert digest == hashlib.sha256(here).hexdigest()[:7]
    with urllib.request.urlopen(f"{base}/", timeout=5) as answer:
        page = answer.read().decode()
    assert said in page
    assert "__WOSTUAST_" + "VERSION__" not in page


def test_two_daemons_do_not_share_a_token(ws):
    assert ws.Daemon().token != ws.Daemon().token
    assert len(ws.Daemon().token) >= 32


def test_sending_nothing_is_refused(in_tmux):
    daemon, base, seen = in_tmux
    for nothing in ("", "   ", "\n"):
        status, body = post(f"{base}/api/session/s1/send", {"text": nothing},
                            token=daemon.token)
        assert status == 400, nothing
    assert seen == []


def test_a_send_of_nothing_but_controls_is_nothing(in_tmux):
    """`tmux_send` takes the controls out, so text made of nothing else is
    nothing to send. It was refused as "tmux did not answer ... the text may
    be on the prompt", which sent the reader to look for text that was never
    typed, from a tmux that was never asked."""
    daemon, base, seen = in_tmux
    status, body = post(f"{base}/api/session/s1/send",
                        {"text": "\x1b\x07\x1b"}, token=daemon.token)
    assert (status, body["error"]) == (400, "there is nothing to send")
    assert seen == []


def test_no_answer_goes_to_a_session_that_is_over(ws, in_tmux):
    """A session that is over has a pane that has moved on. Even a row that
    still carries the question must not press its keys there."""
    daemon, base, seen = in_tmux
    ws.append_event(event("PreToolUse", tool_name="AskUserQuestion",
                          tool_use_id="toolu_q", tool_input={"questions": [
                              {"question": "Which?", "header": "H",
                               "multiSelect": False,
                               "options": [{"label": "a"}, {"label": "b"}]}]}))
    daemon.store.refresh()
    session = daemon.store.sessions["s1"]
    assert session.asking
    session.state = "dead"          # the row, as a burial that kept it
    status, body = post(f"{base}/api/session/s1/answer",
                        {"ask": "toolu_q", "picks": [[1]]}, token=daemon.token)
    assert (status, body["error"]) == (409, "this session is over")
    assert seen == []


def test_the_page_cannot_be_framed(served):
    """Framed by another origin, the page is still ours and holds the token,
    so its POSTs pass every check -- and two clicks on a decoy over an
    invisible frame sent Escape into a pane. Only a header stops a frame."""
    _, base = served
    with urllib.request.urlopen(f"{base}/", timeout=5) as response:
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "frame-ancestors 'none'" in response.headers[
            "Content-Security-Policy"]


def test_sending_more_than_fits_is_refused_not_cut(ws, in_tmux):
    """What arrives in the terminal must be what the user wrote, or nothing.

    Over `SEND_MAX` and under `POST_MAX`, so it is this cap that refuses it:
    it used to send 99,999 characters, which the body limit dropped one floor
    earlier, and so this never reached the cap it is named after."""
    daemon, base, seen = in_tmux
    assert ws.SEND_MAX * 2 < ws.POST_MAX
    status, body = post(f"{base}/api/session/s1/send",
                        {"text": "x" * (ws.SEND_MAX * 2)}, token=daemon.token)
    assert status == 400, (status, body)
    assert str(ws.SEND_MAX) in body["error"]
    assert seen == []



def test_a_long_paste_goes_in(in_tmux):
    """4,400 characters was refused by a cap of 4,000, which is less than one
    long paste. Measured against tmux 3.4, the terminal takes four times
    that."""
    daemon, base, seen = in_tmux
    status, body = post(f"{base}/api/session/s1/send",
                        {"text": "x" * 4400}, token=daemon.token)
    assert status == 200 and body["done"] is True
    assert len(seen) == 2


def test_the_cap_on_a_send_is_in_bytes(ws, in_tmux):
    """It is what tmux counts: bisected against tmux 3.4, `send-keys -l`
    takes 16,341 bytes of ASCII and 8,170 two-byte characters. A cap on
    `len()` would let three times the bytes through in Japanese, and tmux
    would refuse the lot -- silently, as far as the reader could see."""
    daemon, base, seen = in_tmux
    wide = "\u3042" * (ws.SEND_MAX // 3 + 1)         # 3 bytes each in UTF-8
    assert len(wide) < ws.SEND_MAX                   # under a cap on len()
    status, body = post(f"{base}/api/session/s1/send", {"text": wide},
                        token=daemon.token)
    assert status == 400, body
    assert "bytes" in body["error"]
    assert seen == []


def test_a_message_too_large_to_read_says_that(in_tmux):
    """A body over `POST_MAX` is never read, so the route sees an empty one --
    and refused it as "there is nothing to send", which is the opposite of
    what happened."""
    daemon, base, seen = in_tmux
    status, body = post(f"{base}/api/session/s1/send",
                        {"text": "x" * (64 * 1024)}, token=daemon.token)
    assert status == 413, (status, body)
    assert "large" in body["error"]
    assert seen == []


def test_a_jump_tmux_refuses_says_so(ws, served, monkeypatch):
    """The same silence `send` had: `done: false` carries no `error`, so the
    page cleared the slot and the jump failed with nothing on screen."""
    daemon, base = served
    monkeypatch.setattr(ws, "run", lambda args, **rest: None)
    ws.append_event(event("SessionStart", pane="%7", pid=1))
    daemon.store.refresh()
    status, body = post(f"{base}/api/session/s1/jump", token=daemon.token)
    assert status == 502
    assert body["error"]


def test_a_send_tmux_refuses_says_so(ws, served, monkeypatch):
    """`done: false` carries no `error`, so the page cleared the slot and
    wrote nothing into it: the reader asked for something, did not get it,
    and was told nothing at all."""
    daemon, base = served
    monkeypatch.setattr(ws, "run", lambda args, **rest: None)
    ws.append_event(event("SessionStart", pane="%7", pid=1))
    daemon.store.refresh()
    status, body = post(f"{base}/api/session/s1/send", {"text": "hello"},
                        token=daemon.token)
    assert status == 502
    assert body["error"]


def test_a_session_that_is_over_is_not_sent_to(in_tmux):
    daemon, base, seen = in_tmux
    ws_append_end(daemon)
    status, body = post(f"{base}/api/session/s1/send", {"text": "hello"},
                        token=daemon.token)
    assert status == 409
    assert seen == []


def ws_append_end(daemon):
    import conftest as c
    c.wostuast.append_event(event("SessionEnd"))
    daemon.store.refresh()


def test_a_session_outside_tmux_has_no_verbs(ws, served, monkeypatch):
    seen = []
    monkeypatch.setattr(ws, "run", lambda args, **rest: seen.append(list(args)))
    daemon, base = served
    ws.append_event(event("SessionStart", pane="", pid=1))
    daemon.store.refresh()
    status, body = post(f"{base}/api/session/s1/jump", token=daemon.token)
    assert status == 409
    assert "not in tmux" in body["error"]
    assert seen == []


# --- the palette -------------------------------------------------------------

#: A colour written out rather than named. `#bell` and the like do not match:
#: a hex colour is three, four, six or eight hex digits and then a word end.
COLOUR = re.compile(
    r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b"
    r"|\b(?:rgba?|hsla?)\s*\("
)


def stylesheet(page: str) -> str:
    """The page's CSS with the palette blocks taken out.

    Every `:root` block is a palette, and a palette is where a colour is
    allowed to be a number. Everything after them names one instead.
    """
    css = page[page.index("<style>"):page.index("</style>")]
    out = []
    at = 0
    for start in [m.start() for m in re.finditer(r"^:root[^{]*\{", css, re.M)]:
        out.append(css[at:start])
        at = css.index("}", start) + 1
    out.append(css[at:])
    return "".join(out)


def test_every_colour_outside_the_palette_is_named(ws):
    """A colour written into a rule is right in one theme and wrong in the
    other. The search hit was near-black on amber, which in the light theme is
    near-black on dark brown, and nobody saw it until someone searched. This
    is the rule that catches the next one, rather than a reader who cannot
    read something.
    """
    loose = sorted(set(COLOUR.findall(stylesheet(ws.PAGE))))
    assert not loose, f"write these as a variable in the palette: {loose}"


def test_the_palette_check_would_notice(ws):
    """The test above passes trivially if `stylesheet` cuts too much."""
    css = stylesheet(ws.PAGE)
    assert "var(--needs)" in css and len(css) > 10000
    assert COLOUR.search("a { color: #e0a642; }")
    assert COLOUR.search("a { color: rgba(0,0,0,.5); }")
    assert not COLOUR.search("#bell { margin-left: 14px; }")


# --- naming a session --------------------------------------------------------


def test_a_session_can_be_named_over_http(ws, served):
    daemon, base = served
    ws.append_event(event("SessionStart", sid="s1", cwd="/w/one", pane="%7", pid=1))
    daemon.store.refresh()
    status, body = post(f"{base}/api/session/s1/name", {"name": "the parser"},
                        token=daemon.token)
    assert status == 200 and body["name"] == "the parser"
    daemon.store.refresh()
    assert daemon.store.rows[0]["name"] == "the parser"
    assert daemon.store.rows[0]["mine"] is True
    assert daemon.store.rows[0]["label"].startswith("the parser")


def test_naming_a_session_that_is_not_there_is_a_404(ws, served):
    daemon, base = served
    status, _ = post(f"{base}/api/session/nope/name", {"name": "x"},
                     token=daemon.token)
    assert status == 404


def test_a_name_needs_the_token_like_every_other_post(ws, served):
    """It writes no terminal, but it arrives the same way and is checked the
    same way: another site must not be able to rename what it can reach."""
    daemon, base = served
    ws.append_event(event("SessionStart", sid="s1", cwd="/w/one", pane="%7", pid=1))
    daemon.store.refresh()
    status, _ = post(f"{base}/api/session/s1/name", {"name": "theirs"}, token="wrong")
    assert status == 403
    assert ws.read_names() == {}


def test_a_name_too_large_to_read_keeps_the_name_there_was(ws, served):
    """`asked()` does not read a body over `POST_MAX` and hands the route
    `{}`, and `name` read that as "take the name away": a paste of 70,000
    characters into the rename box answered `{"name": "", "done": true}`
    and emptied `names.json` (#235). It is refused, as `send` and
    `decline` refuse theirs."""
    daemon, base = served
    ws.append_event(event("SessionStart", sid="s1", cwd="/w/one", pane="%7", pid=1))
    daemon.store.refresh()
    post(f"{base}/api/session/s1/name", {"name": "kept"}, token=daemon.token)
    status, body = post(f"{base}/api/session/s1/name", {"name": "x" * 70000},
                        token=daemon.token)
    assert status == 413, (status, body)
    assert "large" in body["error"]
    assert ws.read_names() == {"s1": "kept"}


def test_a_session_with_no_pane_can_still_be_named(ws, served):
    """Unlike the tmux verbs: naming touches no terminal, and naming a session
    that has ended is the point of naming one at all."""
    daemon, base = served
    ws.append_event(event("SessionStart", sid="s1", cwd="/w/one", pane="", pid=1))
    daemon.store.refresh()
    status, body = post(f"{base}/api/session/s1/name", {"name": "over"},
                        token=daemon.token)
    assert status == 200 and body["name"] == "over"


# --- the socket itself, where urllib will not go -----------------------------


def raw_exchange(base, request, wait=5.0, reads=3):
    """Send bytes at the daemon and read what comes back on that one socket.

    `urllib` writes a well-formed request and reads one answer, so none of
    this area can be tested through it.
    """
    import socket as sockets
    from urllib.parse import urlparse

    where = urlparse(base)
    sock = sockets.create_connection((where.hostname, where.port), timeout=wait)
    try:
        sock.sendall(request)
        sock.settimeout(wait)
        out = b""
        for _ in range(reads):
            try:
                piece = sock.recv(65536)
            except (TimeoutError, OSError):
                break
            if not piece:
                break
            out += piece
        return out
    finally:
        sock.close()


def test_a_body_too_large_to_read_does_not_frame_the_next_request(in_tmux):
    """`asked()` refuses to read a body over `POST_MAX`, and the connection
    used to stay open under it — so the rest of the body was parsed as the
    next request on that socket. A cross-origin page can send this POST with
    no preflight, and the daemon answered the GET written inside it.

    Not a way past the token: every POST verb still demands it. A way to put
    a request of someone else's framing through the router, and to leave the
    answers on that socket out of step with the questions.
    """
    daemon, base, seen = in_tmux
    smuggled = (b"GET /api/sessions HTTP/1.1\r\nHost: localhost\r\n\r\n"
                + b"x" * 70000)
    request = (b"POST /api/session/s1/send HTTP/1.1\r\n"
               b"Host: localhost\r\n"
               b"Content-Type: text/plain\r\n"
               b"Content-Length: " + str(len(smuggled)).encode() + b"\r\n"
               b"\r\n" + smuggled)
    out = raw_exchange(base, request)
    assert out.count(b"HTTP/1.") == 1, out[:400]
    assert b"403" in out.split(b"\r\n")[0]
    assert b'"sessions"' not in out
    assert seen == []


HIDDEN = b"GET /api/nothing HTTP/1.1\r\nHost: localhost\r\n\r\n"


@pytest.mark.parametrize("head, body", [
    # The body's end is not in a Content-Length, and http.server reads none.
    (b"POST /api/session/s1/send HTTP/1.1\r\nTransfer-Encoding: chunked\r\n",
     b"%x\r\n" % len(HIDDEN) + HIDDEN + b"\r\n0\r\n\r\n"),
    (b"POST /api/session/s1/send HTTP/1.1\r\nContent-Length: many\r\n", HIDDEN),
    (b"POST /api/session/s1/send HTTP/1.1\r\nContent-Length: -5\r\n", HIDDEN),
    (b"POST /api/session/s1/send HTTP/1.1\r\nContent-Length: 0\r\n"
     b"Content-Length: 50\r\n", HIDDEN),
    # A GET's body is never read at all.
    (b"GET /api/settings HTTP/1.1\r\nContent-Length: %d\r\n" % len(HIDDEN), HIDDEN),
    (b"GET /api/settings HTTP/1.1\r\nTransfer-Encoding: chunked\r\n",
     b"%x\r\n" % len(HIDDEN) + HIDDEN + b"\r\n0\r\n\r\n"),
], ids=["chunked", "a-length-that-is-not-a-number", "a-negative-length",
        "two-lengths", "a-get-with-a-body", "a-chunked-get"])
def test_a_body_that_is_not_read_does_not_frame_the_next_request(in_tmux, head,
                                                                 body):
    """The rule above, for every body `asked()` does not read (#235). A
    chunked POST read as length 0, and the request inside its body was
    answered as the next one on that socket: one request, two answers. A
    body on a GET, and a length that does not parse, did the same. Not
    reading such a body is fine; keeping the connection open under it is
    not."""
    daemon, base, seen = in_tmux
    out = raw_exchange(base, head + b"Host: localhost\r\n\r\n" + body)
    assert only_one_answer(out)
    assert seen == []


@pytest.mark.parametrize("head, first", [
    (b"POST /api/session/s1/send HTTP/1.1\r\n", b" 403 "),
    (b"GET /api/settings HTTP/1.1\r\n", b" 200 "),
], ids=["a-post", "a-get"])
def test_a_length_too_long_to_be_a_number_is_not_read(in_tmux, head, first):
    """`isdigit()` took 5,000 digits and `int()` refused them: Python reads
    no number of more than 4,300 digits. The daemon answered 500 and kept
    the connection, and the bytes after the headers were answered as the
    next request (#254). Now such a body is one whose end is not known:
    the answer the request would get anyway, and the connection closed."""
    daemon, base, seen = in_tmux
    out = raw_exchange(base, head + b"Host: localhost\r\nContent-Length: "
                       + b"9" * 5000 + b"\r\n\r\n" + HIDDEN)
    assert only_one_answer(out)
    assert first in out.split(b"\r\n")[0], out[:200]
    assert seen == []


def test_a_request_that_fails_closes_its_connection(in_tmux, monkeypatch):
    """A request that fails half way may leave its body in the socket, so
    the 500 closes the connection: what follows is never read as a request
    of its own (#254)."""
    daemon, base, seen = in_tmux

    def broken():
        raise RuntimeError("nobody thought of this")
    monkeypatch.setattr(daemon, "sessions_payload", broken)
    out = raw_exchange(base, b"GET /api/sessions HTTP/1.1\r\nHost: localhost"
                       b"\r\n\r\n" + HIDDEN)
    assert only_one_answer(out)
    assert b" 500 " in out.split(b"\r\n")[0], out[:200]


def only_one_answer(out):
    """True when the socket carried one answer and nothing after it.

    Counting status lines is not enough: a chunk's size line, read as the
    next request, is answered as HTTP/0.9, which has no status line.
    """
    head, _, rest = out.partition(b"\r\n\r\n")
    length = re.search(rb"(?im)^content-length: *(\d+)", head)
    assert head.startswith(b"HTTP/1.") and length, out[:600]
    assert rest[int(length.group(1)):] == b"", out[:600]
    return True


def test_a_body_that_is_not_read_is_not_taken_for_an_empty_one(ws, in_tmux):
    """The route sees `{}` for a body it never read, and `name` reads `{}`
    as "take the name away". So a POST whose body was not read is refused,
    token or no token, and nothing is changed."""
    daemon, base, seen = in_tmux
    daemon.store.rename("s1", "kept")
    body = b'{"name": ""}'
    request = (b"POST /api/session/s1/name HTTP/1.1\r\n"
               b"Host: localhost\r\n"
               b"X-Wostuast-Token: " + daemon.token.encode() + b"\r\n"
               b"Transfer-Encoding: chunked\r\n\r\n"
               + b"%x\r\n" % len(body) + body + b"\r\n0\r\n\r\n")
    out = raw_exchange(base, request)
    assert only_one_answer(out)
    assert b" 400 " in out.split(b"\r\n")[0], out[:200]
    assert ws.read_names() == {"s1": "kept"}


def test_an_origin_that_will_not_parse_is_refused_quietly(in_tmux):
    """`urlparse("http://[::1")` raises. The checks used to run in front of
    the `try`, so an unauthenticated request could kill the thread: no status
    line at all, and a traceback in the terminal running `serve`."""
    daemon, base, seen = in_tmux
    request = (b"POST /api/session/s1/jump HTTP/1.1\r\n"
               b"Host: localhost\r\n"
               b"Origin: http://[::1\r\n"
               b"X-Wostuast-Token: " + daemon.token.encode() + b"\r\n"
               b"Content-Length: 0\r\n\r\n")
    out = raw_exchange(base, request)
    assert out.startswith(b"HTTP/1."), out[:200]
    assert b"403" in out.split(b"\r\n")[0]
    assert seen == []


def test_a_token_header_that_is_not_ascii_is_refused_quietly(in_tmux):
    """Headers decode as latin-1, and `hmac.compare_digest` raises on a
    string that is not ASCII."""
    daemon, base, seen = in_tmux
    request = (b"POST /api/session/s1/jump HTTP/1.1\r\n"
               b"Host: localhost\r\n"
               b"X-Wostuast-Token: \xe9\r\n"
               b"Content-Length: 0\r\n\r\n")
    out = raw_exchange(base, request)
    assert out.startswith(b"HTTP/1."), out[:200]
    assert b"403" in out.split(b"\r\n")[0]
    assert seen == []


def test_a_request_with_no_host_is_not_ours(served):
    """The check exists because a site can point its own name at 127.0.0.1.
    An empty Host used to satisfy it, which made it skippable."""
    daemon, base = served
    out = raw_exchange(base, b"GET /api/sessions HTTP/1.0\r\n\r\n")
    assert b"403" in out.split(b"\r\n")[0], out[:200]
    assert b'"sessions"' not in out


def test_the_c1_controls_do_not_reach_a_terminal(ws):
    """NEL and CSI are controls a terminal may act on, and they are in text an
    agent wrote. U+2028 is a line break that `"\\n" in text` does not see."""
    sent = []
    ws.tmux_send("%1", "before\u009bafter\u0085and more",
                 runner=lambda args, **rest: sent.append(args) or "")
    text = sent[0][-1]
    assert text == "beforeafterandmore"
    assert "\u009b" not in text and "\u0085" not in text and " " not in text


def test_a_path_that_will_not_parse_answers_rather_than_dying(served):
    """`urlparse(self.path)` used to run in front of the `try` on the GET side
    too, so a request line holding an unterminated IPv6 host killed the thread
    with no status line sent. Every part of a request is inside the guard."""
    daemon, base = served
    out = raw_exchange(base, b"GET http://[::1 HTTP/1.1\r\nHost: localhost\r\n\r\n")
    assert out.startswith(b"HTTP/1."), out[:200]
    assert b"500" in out.split(b"\r\n")[0] or b"404" in out.split(b"\r\n")[0]


# --- a file served as its own bytes ------------------------------------------


def test_a_picture_is_served_with_the_type_its_name_says(repo_session):
    root, base = repo_session
    raw = conftest.tiny_png()
    (root / "logo.png").write_bytes(raw)
    conftest.git_in(root, "add", "-A")
    conftest.git_in(root, "commit", "-qm", "logo")
    with urllib.request.urlopen(f"{base}/api/session/s1/raw?path=logo.png",
                                timeout=5) as answer:
        assert answer.status == 200
        assert answer.headers["Content-Type"] == "image/png"
        # Never let the browser read the bytes and pick its own type: this
        # origin holds the token the page POSTs with.
        assert answer.headers["X-Content-Type-Options"] == "nosniff"
        assert answer.headers.get("Access-Control-Allow-Origin") is None
        assert answer.read() == raw


def test_a_picture_is_never_packed(repo_session):
    """Only text is packed. A picture or a video is packed already, and
    gzip over it costs time and saves nothing."""
    root, base = repo_session
    raw = conftest.tiny_png() + bytes(8192)
    (root / "big.png").write_bytes(raw)
    conftest.git_in(root, "add", "-A")
    conftest.git_in(root, "commit", "-qm", "big")
    headers, body = fetch_packed(f"{base}/api/session/s1/raw?path=big.png",
                                 "gzip")
    assert headers["Content-Type"] == "image/png"
    assert headers["Content-Encoding"] is None
    assert body == raw


def test_the_raw_route_serves_nothing_that_could_be_a_document(repo_session):
    """An SVG or an HTML file served from here would be a page an agent wrote,
    on the origin that holds the token, with a script in it able to read
    both. The list of types is the whole of what this route will serve."""
    root, base = repo_session
    for name, body in (("page.html", b"<b>hi</b>"), ("draw.svg", b"<svg/>"),
                       ("notes.txt", b"words")):
        (root / name).write_bytes(body)
    conftest.git_in(root, "add", "-A")
    conftest.git_in(root, "commit", "-qm", "sundry")
    for name in ("page.html", "draw.svg", "notes.txt", "../../etc/hosts"):
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(
                f"{base}/api/session/s1/raw?path={name}", timeout=5)
        assert caught.value.code == 404, name


# --- answering a question -----------------------------------------------------

TWO = {"questions": [
    {"question": "Colour?", "header": "C", "multiSelect": False,
     "options": [{"label": "Red"}, {"label": "Green"}]},
    {"question": "Labels?", "header": "L", "multiSelect": True,
     "options": [{"label": "A"}, {"label": "B"}, {"label": "C"}]},
]}


def asking(ws, daemon, tool_use_id="toolu_two"):
    ws.append_event(event("PreToolUse", tool_name="AskUserQuestion",
                          tool_input=TWO, tool_use_id=tool_use_id, pane="%7"))
    daemon.store.refresh()


def test_an_answer_presses_the_keys_the_question_takes(ws, in_tmux, monkeypatch):
    monkeypatch.setattr(ws, "KEY_GAP", 0)
    daemon, base, seen = in_tmux
    asking(ws, daemon)
    status, body = post(base + "/api/session/s1/answer",
                        {"ask": "toolu_two", "picks": [[2], [3, 1]]},
                        token=daemon.token)
    assert status == 200 and body["keys"] == ["2", "1", "3", "Tab", "Enter"], body
    assert [one[-1] for one in seen] == ["2", "1", "3", "Tab", "Enter"]


def test_an_answer_for_a_question_no_longer_waiting_presses_nothing(
        ws, in_tmux, monkeypatch):
    """Its numbers would land on a question nobody read -- or on the agent's
    prompt, once the question has been answered in the terminal."""
    monkeypatch.setattr(ws, "KEY_GAP", 0)
    daemon, base, seen = in_tmux
    asking(ws, daemon)
    status, body = post(base + "/api/session/s1/answer",
                        {"ask": "toolu_old", "picks": [[1], [1]]},
                        token=daemon.token)
    assert status == 409 and "no longer waiting" in body["error"]
    status, body = post(base + "/api/session/s1/answer",
                        {"ask": "toolu_two", "picks": [[1], [9]]},
                        token=daemon.token)
    assert status == 400 and body["error"]
    # And like every verb that types, it wants the token.
    status, _ = post(base + "/api/session/s1/answer",
                     {"ask": "toolu_two", "picks": [[1], [1]]})
    assert status == 403
    assert seen == []


def test_an_answer_too_large_to_read_says_that(ws, in_tmux):
    """A body over `POST_MAX` is not read, and the route sees `{}`, which
    has no `ask`: it was refused as "that question is no longer waiting",
    and the question was waiting (#254)."""
    daemon, base, seen = in_tmux
    asking(ws, daemon)
    status, body = post(base + "/api/session/s1/answer",
                        {"ask": "toolu_two", "picks": [[1], [1]],
                         "pad": "x" * ws.POST_MAX}, token=daemon.token)
    assert status == 413 and "large" in body["error"], (status, body)
    assert seen == []


def test_an_answer_never_goes_into_a_permission_dialog(ws, in_tmux, monkeypatch):
    """One batch of calls can hold a question and a command that asks for
    permission. The answer's keys are digits and Enter, and the dialog's
    cursor starts on "1. Yes", so they could approve the command. The
    answer is refused while the row shows a dialog, as `send` is (#254)."""
    monkeypatch.setattr(ws, "KEY_GAP", 0)
    daemon, base, seen = in_tmux
    asking(ws, daemon)
    for one in (event("PreToolUse", tool_name="Bash", tool_use_id="toolu_b1",
                      tool_input={"command": "rm -rf build"}, pane="%7"),
                event("PermissionRequest", tool_name="Bash",
                      tool_input={"command": "rm -rf build"}, pane="%7")):
        ws.append_event(one)
    daemon.store.refresh()
    held = daemon.store.sessions["s1"]
    assert held.asking and held.permission and held.state == "needs_you"
    status, body = post(base + "/api/session/s1/answer",
                        {"ask": "toolu_two", "picks": [[1], [1]]},
                        token=daemon.token)
    assert status == 409 and "permission dialog" in body["error"], body
    assert seen == []


def test_an_answer_tmux_cut_short_says_how_far_it_got(ws, served, monkeypatch):
    """Some keys may have landed. "Nothing went in" would send the reader
    back to answer again, on top of half an answer."""
    monkeypatch.setattr(ws, "KEY_GAP", 0)
    calls = []

    def runner(args, **rest):
        calls.append(args)
        return None if len(calls) == 3 else ""

    monkeypatch.setattr(ws, "run", runner)
    daemon, base = served
    ws.append_event(event("SessionStart", pane="%7", pid=1))
    asking(ws, daemon)
    status, body = post(base + "/api/session/s1/answer",
                        {"ask": "toolu_two", "picks": [[1], [1, 2]]},
                        token=daemon.token)
    assert status == 502 and "2 of 5" in body["error"], body


# --- declining a permission request -----------------------------------------

REJECTED = ("The user doesn't want to proceed with this tool use. The tool use"
            " was rejected (eg. if it was a file edit, the new_string was NOT"
            " written to the file).")


@pytest.fixture
def declining(ws, served, transcript_file, monkeypatch):
    """A session at a permission dialog, in a pane, with its transcript.

    tmux is a recorder, and `closes` says whether the Escape closes the
    dialog: when it does, the rejection is written to the transcript as the
    call's result, as 2.1.282 writes it a few milliseconds after the key.
    """
    daemon, base = served
    path = transcript_file("s1", [conftest.record("tool", "make", tool_id="toolu_p1")])
    seen, closes = [], [True]

    def runner(args, **rest):
        seen.append(list(args))
        if args[-1] == "Escape" and closes[0]:
            with open(path, "a") as handle:
                handle.write(conftest.records(conftest.record(
                    "result", REJECTED, tool_id="toolu_p1")))
        return ""

    monkeypatch.setattr(ws, "run", runner)
    monkeypatch.setattr(ws, "DECLINE_WAIT", 0.5)
    now = time.time()
    for one in (event("SessionStart", pane="%7", pid=1, transcript_path=str(path),
                      ts=now - 10),
                event("PreToolUse", tool_name="Bash", tool_use_id="toolu_p1",
                      tool_input={"command": "make"}, pane="%7", ts=now - 5),
                event("PermissionRequest", tool_name="Bash",
                      tool_input={"command": "make"}, pane="%7", ts=now - 4.9)):
        ws.append_event(one)
    daemon.store.refresh()
    key = daemon.store.sessions["s1"].permission["key"]
    return daemon, base, seen, closes, key, path


def typed(seen):
    return [one[-1] for one in seen if "-l" in one]


def test_a_decline_is_escape_then_the_reason_once_the_dialog_closed(
        ws, declining):
    """Escape declines every dialog -- measured on 2.1.282, where the number
    of "No" is 4 on a command and 3 on a file -- and the reason is a prompt
    typed after it. The daemon records the decline, so the row leaves amber:
    no hook says No was said."""
    daemon, base, seen, closes, key, _ = declining
    status, body = post(base + "/api/session/s1/decline",
                        {"key": key, "reason": "Use the ninja build instead"},
                        token=daemon.token)
    assert status == 200 and body["sent"] and body["seen"], body
    assert seen[0][-1] == "Escape"
    assert typed(seen) == ["Use the ninja build instead"]
    daemon.store.refresh()
    session = daemon.store.sessions["s1"]
    assert session.state == "done" and session.permission is None


def test_a_reason_is_never_typed_into_a_dialog_not_seen_to_close(ws, declining):
    """The cursor starts on "1. Yes" and a digit picks an option, so a
    reason typed into a dialog still up can approve what was declined. An
    Escape read in one burst with the letters after it is an Alt key --
    measured, the dialog stayed up. Without the call's result in the
    transcript, nothing but the Escape is pressed."""
    daemon, base, seen, closes, key, _ = declining
    closes[0] = False
    status, body = post(base + "/api/session/s1/decline",
                        {"key": key, "reason": "Use port 1234"},
                        token=daemon.token)
    assert status == 200 and not body["seen"] and "not typed" in body["error"]
    assert [one[-1] for one in seen] == ["Escape"]
    daemon.store.refresh()
    assert daemon.store.sessions["s1"].state == "needs_you"


def test_a_request_with_no_call_gets_escape_and_no_reason(ws, declining):
    """Two open calls reading the same leave the dialog with no call, and
    then nothing can prove it closed."""
    daemon, base, seen, closes, key, _ = declining
    daemon.store.sessions["s1"].permission["call"] = ""
    status, body = post(base + "/api/session/s1/decline",
                        {"key": key, "reason": "no"}, token=daemon.token)
    assert status == 200 and not body["seen"] and "not typed" in body["error"]
    assert [one[-1] for one in seen] == ["Escape"]


def test_a_request_answered_in_the_terminal_is_not_declined(ws, declining):
    """The row is amber until a hook says otherwise, and none says Yes was
    pressed. If the call has its result, the dialog is over, and an Escape
    now would stop whatever the agent went on to do."""
    daemon, base, seen, closes, key, path = declining
    with open(path, "a") as handle:
        handle.write(conftest.records(conftest.record(
            "result", "built", tool_id="toolu_p1")))
    status, body = post(base + "/api/session/s1/decline", {"key": key},
                        token=daemon.token)
    assert status == 409 and "answered in the terminal" in body["error"]
    assert seen == []


def test_a_decline_for_another_dialog_presses_nothing(ws, declining):
    daemon, base, seen, closes, key, _ = declining
    status, body = post(base + "/api/session/s1/decline", {"key": "1.000000"},
                        token=daemon.token)
    assert status == 409 and "no longer waiting" in body["error"]
    status, _ = post(base + "/api/session/s1/decline", {"key": key})
    assert status == 403
    assert seen == []


def test_a_decline_not_seen_to_close_does_not_say_declined(ws, declining):
    """With no reason too: "declined" would be a claim nothing proved, and
    the row stays amber."""
    daemon, base, seen, closes, key, _ = declining
    closes[0] = False
    status, body = post(base + "/api/session/s1/decline", {"key": key},
                        token=daemon.token)
    assert status == 200 and not body["seen"]
    assert "not seen to close" in body["error"]


def test_one_decline_at_a_time_per_session(ws, declining):
    """A decline waits between its Escape and its reason, and a second one
    from another tab would press another Escape into what came next."""
    daemon, base, seen, closes, key, _ = declining
    daemon.declining.add("s1")
    status, body = post(base + "/api/session/s1/decline", {"key": key},
                        token=daemon.token)
    assert status == 409 and "already on its way" in body["error"]
    assert seen == []


def test_a_send_never_answers_a_permission_dialog(ws, declining):
    """The dialog's cursor starts on "1. Yes", and a digit picks an option:
    the send typed "1" and pressed Enter into it, which approves -- the one
    thing this page may never do. `decline` waits for proof that the dialog
    closed; a send has none, so it is refused while the row is amber for a
    dialog, and while a No is on its way."""
    daemon, base, seen, closes, key, _ = declining
    status, body = post(base + "/api/session/s1/send", {"text": "1"},
                        token=daemon.token)
    assert status == 409 and "permission dialog" in body["error"], body
    assert seen == []


def test_no_send_goes_in_while_a_no_is_on_its_way(ws, in_tmux):
    daemon, base, seen = in_tmux
    daemon.declining.add("s1")
    status, body = post(base + "/api/session/s1/send", {"text": "go on"},
                        token=daemon.token)
    assert status == 409 and "No is already on its way" in body["error"], body
    assert seen == []


def test_two_sends_at_once_do_not_mix_in_the_pane(ws, served, monkeypatch):
    """The page's `sending` guard is per browser tab. Two tabs, or a tab and
    a script, ran two HTTP threads, and with a tmux that takes a moment the
    pane got "first", "second", Enter, Enter: one prompt of both. One goes
    in, and the other is refused, whole."""
    import threading

    seen = []

    def runner(args, **rest):
        seen.append(list(args))
        time.sleep(0.2)
        return ""

    monkeypatch.setattr(ws, "run", runner)
    daemon, base = served
    ws.append_event(event("SessionStart", pane="%7", pid=1))
    daemon.store.refresh()
    answers = []
    start = threading.Barrier(2)

    def send(text):
        start.wait()
        answers.append(post(base + "/api/session/s1/send", {"text": text},
                            token=daemon.token))

    both = [threading.Thread(target=send, args=(text,))
            for text in ("first message", "second message")]
    for one in both:
        one.start()
    for one in both:
        one.join()
    assert sorted(status for status, _ in answers) == [200, 409], answers
    refused = [body for status, body in answers if status == 409][0]
    assert "already being typed" in refused["error"]
    typed_now = [one[-1] for one in seen]
    assert len(typed_now) == 2 and typed_now[1] == "Enter", typed_now
    # And the session is given back: the next send goes in.
    status, _ = post(base + "/api/session/s1/send", {"text": "third"},
                     token=daemon.token)
    assert status == 200


def test_nothing_else_is_typed_while_an_answer_or_a_no_goes_in(
        ws, declining, monkeypatch):
    """An answer is keys `KEY_GAP` apart, and a No waits up to
    `DECLINE_WAIT` between its Escape and its reason: a send, a second
    answer or a No landing in between mixed its keys with theirs."""
    monkeypatch.setattr(ws, "KEY_GAP", 0)
    daemon, base, seen, closes, key, _ = declining
    assert daemon.claim("s1") == ""            # a send, on its way
    status, body = post(base + "/api/session/s1/decline", {"key": key},
                        token=daemon.token)
    assert status == 409 and "already being typed" in body["error"], body
    asking(ws, daemon)
    status, body = post(base + "/api/session/s1/answer",
                        {"ask": "toolu_two", "picks": [[1], [1]]},
                        token=daemon.token)
    assert status == 409 and "already being typed" in body["error"], body
    assert seen == []
    daemon.release("s1")
    status, body = post(base + "/api/session/s1/answer",
                        {"ask": "toolu_two", "picks": [[1], [1]]},
                        token=daemon.token)
    assert status == 200, body
    assert daemon.typing == set() and daemon.declining == set()


def test_a_no_given_in_the_terminal_ends_the_wait(ws, declining):
    """Saying No fires no hook, and only the page's own No had the daemon
    watch for it: a No typed in the terminal left the row amber, over an
    agent back at its prompt, until the next prompt. The tick now looks for
    the rejection as the call's result, for every dialog up. A Yes is not a
    No, and a No the page is pressing is the page's to record."""
    daemon, _, _, _, _, path = declining

    def write(text):
        with open(path, "a") as handle:
            handle.write(conftest.records(conftest.record(
                "result", text, tool_id="toolu_p1")))

    # While the page presses its own No, the tick leaves the dialog alone.
    daemon.declining.add("s1")
    write(REJECTED)
    daemon.tick()
    assert daemon.store.sessions["s1"].state == "needs_you"
    daemon.declining.discard("s1")

    daemon.tick()
    session = daemon.store.sessions["s1"]
    assert session.state == "done" and session.permission is None
    assert session.last_event == "declined in the terminal"
    # The daemon's own record, in the log, says where the No came from.
    with open(ws.events_path(), encoding="utf-8") as handle:
        written = [json.loads(line) for line in handle if line.strip()]
    declined = [one for one in written if one.get("hook_event_name") == "Declined"]
    assert [one.get("where") for one in declined] == ["terminal"], declined
    assert daemon.store.rows[0]["state"] == "done"


def test_a_yes_in_the_terminal_is_not_taken_for_a_no(ws, declining):
    """A call that ran has a result too, and its `PostToolUse` is what says
    so. Read as a No, the row said "declined" over a build that went on."""
    daemon, _, _, _, _, path = declining
    with open(path, "a") as handle:
        handle.write(conftest.records(conftest.record(
            "result", "14 passed in 0.31s", tool_id="toolu_p1")))
    daemon.tick()
    assert daemon.store.sessions["s1"].state == "needs_you"


# --- the settings, written from the page --------------------------------------


def settings_pushed(client):
    """The `settings` messages a stream client was sent, as data."""
    out = []
    while not client.queue.empty():
        message = client.queue.get_nowait()
        if message.startswith("event: settings\n"):
            out.append(json.loads(message.split("data: ", 1)[1]))
    return out


def test_a_setting_needs_the_token(ws, served):
    """It writes no terminal, but it writes a file of the reader's, and any
    site can POST to a loopback port. Checked like the verbs."""
    daemon, base = served
    status, _ = post(f"{base}/api/settings", {"colours": "dark"})
    assert status == 403
    status, _ = post(f"{base}/api/settings", {"colours": "dark"}, token="wrong")
    assert status == 403
    assert not ws.config_path().exists()


def test_a_setting_is_written_and_every_page_hears_of_it(ws, served):
    """One reader, many tabs: a change in one is a change in all of them,
    the one that made it too, and the push is how."""
    daemon, base = served
    client = daemon.hub.add()
    status, body = post(f"{base}/api/settings", {"tab_width": 8},
                        token=daemon.token)
    assert status == 200 and body["done"] is True, body
    assert body["tab_width"] == 8
    assert json.loads(ws.config_path().read_text()) == {"tab_width": 8}
    pushed = settings_pushed(client)
    assert [one["tab_width"] for one in pushed] == [8]
    # The answer is the push, number and all, so the page can drop a push
    # older than it. The next one is numbered after it.
    assert (body["serial"], body["run"]) == (pushed[0]["serial"], pushed[0]["run"])
    # And the tick that follows does not say it twice.
    daemon.tell_config()
    assert settings_pushed(client) == []
    status, body = post(f"{base}/api/settings", {"tab_width": 2},
                        token=daemon.token)
    assert body["serial"] == pushed[0]["serial"] + 1


def test_a_file_changed_by_hand_reaches_the_page(ws, served):
    """The reader may open the file in an editor. The tick looks at it -- a
    stat, not a read -- and a change goes out without a reload."""
    daemon, _ = served
    client = daemon.hub.add()
    daemon.tell_config()
    assert settings_pushed(client) == []
    ws.config_path().parent.mkdir(parents=True, exist_ok=True)
    ws.config_path().write_text('{"colours": "dark"}', encoding="utf-8")
    daemon.tick()
    assert [one["colours"] for one in settings_pushed(client)] == ["dark"]


def test_a_bad_setting_is_refused_and_says_why(ws, served):
    daemon, base = served
    status, body = post(f"{base}/api/settings", {"tab_width": 3},
                        token=daemon.token)
    assert status == 400 and "tab_width" in body["error"], body
    assert not ws.config_path().exists()


def test_a_refused_link_is_named_in_the_answer(ws, served):
    """So the menu can put the reason under the right row; the rest are
    kept."""
    daemon, base = served
    status, body = post(f"{base}/api/settings", {"links": [
        {"match": "(a+)+", "url": "https://t/"},
        {"match": r"OK-(\d+)", "url": "https://t/$1"}]}, token=daemon.token)
    assert status == 200, body
    assert [one["at"] for one in body["refused"]] == [0]
    assert [one["match"] for one in body["links"]] == [r"OK-(\d+)"]


def test_a_setting_too_large_to_read_says_that(ws, served):
    """`asked()` hands over `{}` for a body it did not read, which is a
    change of nothing, and must not answer as if it were done."""
    daemon, base = served
    status, body = post(f"{base}/api/settings",
                        {"links": [{"match": "x", "url": "https://t/" + "x" * 70000}]},
                        token=daemon.token)
    assert status == 413 and "large" in body["error"], (status, body)
    assert not ws.config_path().exists()


def test_a_settings_file_that_cannot_be_written_says_so(ws, served, monkeypatch):
    """A read-only home must not answer 500, or "done"."""
    daemon, base = served

    def refuse(*args, **kwargs):
        raise OSError("read-only file system")

    monkeypatch.setattr(ws, "write_atomic", refuse)
    status, body = post(f"{base}/api/settings", {"colours": "dark"},
                        token=daemon.token)
    assert status == 400 and "read-only" in body["error"], (status, body)
