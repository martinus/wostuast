"""The daemon, driven over real HTTP against a server on a random port."""

from __future__ import annotations

import json
import re
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


def test_the_links_route_carries_both_answers(ws, served):
    """The usable links, and what is wrong with the rest. Both, because the
    page cannot tell "no links" from "your file is broken" on its own -- and
    the difference is the whole of the reader's problem."""
    _, base = served
    ws.links_path().parent.mkdir(parents=True, exist_ok=True)
    ws.links_path().write_text(json.dumps([
        {"match": r"OK-(\d+)", "url": "https://tickets/$1"},
        {"match": "BAD-(", "url": "https://tickets/"},
    ]), encoding="utf-8")
    status, body = get(f"{base}/api/links")
    assert status == 200
    assert body["links"] == [{"match": r"OK-(\d+)", "url": "https://tickets/$1"}]
    assert len(body["trouble"]) == 1 and "link 2" in body["trouble"][0]


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

    blocks, run = daemon.read_transcript("s1")
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

# Every POST here types into a terminal, which is why PLAN.md section 4.4.1
# gives them a token and an Origin check. These tests are that rule.


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


def test_the_token_is_in_the_page_and_is_not_the_mark(served):
    daemon, base = served
    with urllib.request.urlopen(f"{base}/", timeout=5) as answer:
        page = answer.read().decode()
    assert daemon.token in page
    assert ws_token_mark() not in page


def ws_token_mark():
    return "__WOSTUAST_" + "TOKEN__"


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


# --- stopping an agent, and the limit that does it for you --------------------


def test_interrupt_presses_escape(in_tmux):
    daemon, base, seen = in_tmux
    status, body = post(f"{base}/api/session/s1/interrupt", token=daemon.token)
    assert status == 200 and body["done"] is True
    assert seen == [["tmux", "send-keys", "-t", "%7", "Escape"]]


def test_interrupt_needs_the_token_like_every_other_verb(in_tmux):
    """It types into a terminal, so it is behind exactly what `send` is."""
    daemon, base, seen = in_tmux
    status, _ = post(f"{base}/api/session/s1/interrupt")
    assert status == 403
    assert seen == []


def test_a_limit_is_stored_and_read_back(ws, in_tmux):
    daemon, base, seen = in_tmux
    status, body = post(f"{base}/api/session/s1/limit", {"limit": 12.5},
                        token=daemon.token)
    assert status == 200 and body["limit"] == 12.5
    assert ws.read_limits()["s1"]["limit"] == 12.5
    assert seen == []                      # setting one writes no terminal
    status, body = post(f"{base}/api/session/s1/limit", {"limit": 0},
                        token=daemon.token)
    assert status == 200 and ws.read_limits() == {}


def test_a_limit_that_is_not_a_number_is_refused(ws, in_tmux):
    daemon, base, seen = in_tmux
    for bad in ("lots", None, -1, [], float("nan")):
        status, body = post(f"{base}/api/session/s1/limit", {"limit": bad},
                            token=daemon.token)
        assert status == 400, (bad, status)
        assert body["error"]
    status, _ = post(f"{base}/api/session/s1/limit", {"limit": 1e9},
                     token=daemon.token)
    assert status == 400
    assert ws.read_limits() == {}


def test_the_limit_route_needs_the_token_too(ws, in_tmux):
    """It writes no terminal itself, and it is what lets the daemon write one
    later — so it sits behind the same check."""
    daemon, base, seen = in_tmux
    status, _ = post(f"{base}/api/session/s1/limit", {"limit": 5})
    assert status == 403
    assert ws.read_limits() == {}


def test_a_tick_stops_a_session_that_has_gone_over(ws, served, monkeypatch):
    """The one thing this program does to a terminal that nobody pressed a
    button for."""
    daemon, base = served
    seen = []
    monkeypatch.setattr(ws, "run", lambda args, **rest: seen.append(list(args)) or "")
    now = time.time()
    # Every event carries a pane and `apply` takes it, so the second one has
    # to say the same as the first or it moves the session to another pane.
    ws.append_event(event("SessionStart", pane="%7", pid=1, ts=now))
    ws.append_event(event("UserPromptSubmit", pane="%7", prompt="go", ts=now + 1))
    daemon.store.refresh()
    daemon.store.sessions["s1"].status = ws.Status(ts=1.0, cost_usd=30.0)
    daemon.store.set_limit("s1", 10.0)
    assert daemon.store.sessions["s1"].state == "working"

    daemon.tick()
    assert ["tmux", "send-keys", "-t", "%7", "Escape"] in seen
    # And the row says why, so a reader who was not watching finds out.
    said = [one for one in daemon.store.rows if one["id"] == "s1"][0]
    assert said["spend_limit"] == 10.0 and said["limit_fired"]

    seen.clear()
    daemon.tick()
    assert seen == []                      # once, not on every tick
