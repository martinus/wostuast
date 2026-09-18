"""The page, driven in a real browser.

These run only where a browser is available. They exist because the one bug
that mattered here could not be seen any other way: raw HTML was scrubbed
after being written into the document, by which time an `onerror` had already
fired. Nothing short of a browser catches that.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

CHROMIUM = [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
]


def browser_path() -> str | None:
    for candidate in [os.environ.get("WOSTUAST_CHROME", "")] + CHROMIUM:
        if candidate and Path(candidate).exists():
            return candidate
    return None


sync_playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed"
).sync_playwright

pytestmark = pytest.mark.skipif(browser_path() is None, reason="no browser here")


HOSTILE = (
    "Read from a README:\n\n"
    '<img src=x onerror="window.PWNED=1">\n'
    "<script>window.PWNED=2</script>\n"
    "[click me](javascript:window.PWNED=3)\n\n"
    "A fence needing a real `>`:\n\n```python\nif len(hits) > 1:\n    raise Ambiguous\n```\n"
)


@pytest.fixture
def page_at(ws, tmp_path, monkeypatch, transcript_file):
    """A daemon with one session whose transcript holds hostile Markdown."""
    monkeypatch.setattr(ws, "git_facts_many", lambda dirs: {
        d: ws.GitFacts(repo="repo", branch="main") for d in dirs})
    monkeypatch.setattr(ws, "pid_alive", lambda pid: True)

    transcript = transcript_file("s1", [
        {"type": "user", "timestamp": "2026-09-18T14:02:00.000Z",
         "message": {"role": "user", "content": "Do the thing."}},
        {"type": "assistant", "timestamp": "2026-09-18T14:03:00.000Z",
         "message": {"role": "assistant",
                     "content": [{"type": "text", "text": HOSTILE}]}},
        {"type": "assistant", "timestamp": "2026-09-18T14:04:00.000Z",
         "message": {"role": "assistant", "content": [
             {"type": "tool_use", "id": "t1", "name": "Bash",
              "input": {"command": "pytest -q"}}]}},
        {"type": "user", "timestamp": "2026-09-18T14:04:05.000Z",
         "message": {"role": "user", "content": [
             {"type": "tool_result", "tool_use_id": "t1",
              "content": "14 passed in 0.31s\nall good"}]}},
    ])
    ws.append_event({"session_id": "s1", "hook_event_name": "SessionStart",
                     "cwd": str(tmp_path), "pane": "%7", "pid": 1,
                     "ts": time.time(), "transcript_path": str(transcript)})
    ws.write_status("s1", ws.Status(ts=1.0, name="A session", model="Opus 5",
                                    context_pct=41.0))

    daemon = ws.Daemon()
    server = ws.make_server(daemon, 0)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    daemon.store.refresh()
    try:
        yield daemon, f"http://127.0.0.1:{port}/"
    finally:
        daemon.stopping.set()
        server.shutdown()
        server.server_close()


def open_page(play, where, scheme="dark"):
    url = where[1] if isinstance(where, tuple) else where
    browser = play.chromium.launch(executable_path=browser_path(),
                                   args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1440, "height": 900},
                            color_scheme=scheme)
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector(".row", timeout=15000)
    page.wait_for_timeout(600)
    return browser, page


def test_the_page_draws_the_session(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            assert page.locator(".row").count() == 1
            assert "A session" in page.locator(".row .name").inner_text()
            assert page.title() == "wostuast"
            assert "Opus 5" in page.locator("#facts").inner_text()
            assert page.locator(".turn").count() >= 2
        finally:
            browser.close()


def test_hostile_markdown_cannot_run(page_at):
    """An agent that reads a nasty file must not be able to act on this page.
    The page shares an origin with the tmux verbs, so this is the whole game."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            assert page.evaluate("window.PWNED ?? null") is None
            assert page.locator(".prose img").count() == 0
            assert page.locator(".prose script").count() == 0
            hrefs = page.eval_on_selector_all(
                ".prose a", "els => els.map(e => e.getAttribute('href'))")
            assert all(h is None or h.startswith(("http", "#")) for h in hrefs)
        finally:
            browser.close()


def test_raw_html_is_shown_rather_than_swallowed(page_at):
    """The reader should see what the agent saw, as text."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            shown = page.locator(".prose").last.inner_text()
            assert "onerror" in shown
            assert "window.PWNED=2" in shown
        finally:
            browser.close()


def test_a_code_fence_keeps_its_angle_bracket(page_at):
    """Escaping the Markdown source instead of the output turned `>` into
    `&gt;` inside fences. This is that regression."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            fence = page.locator(".prose pre").last.inner_text()
            assert "len(hits) > 1" in fence
            assert "&gt;" not in fence
        finally:
            browser.close()


def test_both_themes_are_readable(page_at):
    """PLAN.md section 5.2 asks for a light theme from the start."""
    with sync_playwright() as play:
        seen = {}
        for scheme in ("dark", "light"):
            browser, page = open_page(play, page_at, scheme)
            try:
                seen[scheme] = (
                    page.evaluate("getComputedStyle(document.body).backgroundColor"),
                    page.evaluate(
                        "getComputedStyle(document.querySelector('.prose pre code'))"
                        ".color"),
                )
            finally:
                browser.close()
        assert seen["dark"][0] != seen["light"][0], "the light theme did not apply"
        assert seen["dark"][1] != seen["light"][1], "code would be unreadable"


def test_a_row_is_not_rebuilt_every_second(page_at):
    """The ages advance once a second. Rebuilding the rows to do it restarted
    the needs-you pulse before it could finish a cycle, and threw away the
    dot's colour transition. Only the age text may change."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.evaluate("window.__dot = document.querySelector('.row .dot')")
            first = page.locator(".row .age").first.inner_text()
            page.wait_for_timeout(2400)
            assert page.evaluate("window.__dot.isConnected"), "the row was rebuilt"
            assert page.locator(".row .age").first.inner_text() != first
        finally:
            browser.close()


def test_expanding_a_tool_result_leaves_the_rest_alone(page_at):
    """It used to redraw the whole tab, which re-parsed every Markdown block
    and threw the reader to the bottom of the transcript."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.evaluate("document.querySelector('.content').scrollTop = 0")
            page.evaluate("window.__first = document.querySelector('.turn')")
            before = page.evaluate("document.querySelector('.content').scrollTop")
            page.locator(".tool").first.click()
            page.wait_for_timeout(250)
            assert page.locator(".tool-result").count() == 1
            assert page.evaluate("document.querySelector('.content').scrollTop") == before
            assert page.evaluate("window.__first.isConnected"), "everything was redrawn"
        finally:
            browser.close()


def test_a_tab_that_is_not_built_yet_does_nothing(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            turns = page.locator(".turn").count()
            page.keyboard.press("2")
            page.wait_for_timeout(200)
            assert page.locator(".tab[data-tab='transcript']").get_attribute(
                "aria-selected") == "true"
            assert page.locator(".turn").count() == turns
        finally:
            browser.close()


def test_the_session_the_page_picks_for_you_is_watched(page_at, ws):
    """The page auto-selects the first session. It used to set it without
    subscribing, so the stream stayed on watch="" and the transcript of the
    one session actually on screen never updated."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            before = page.locator(".turn").count()
            assert page.locator(".row.chosen").count() == 1

            with open(daemon_transcript(daemon), "a") as handle:
                handle.write(json.dumps({
                    "type": "assistant", "timestamp": "2026-09-18T14:09:00.000Z",
                    "message": {"role": "assistant", "content": [
                        {"type": "text", "text": "A brand new line."}]}}) + "\n")
            daemon.tick()
            page.wait_for_timeout(1200)
            assert page.locator(".turn").count() == before + 1
            assert "A brand new line." in page.locator(".content").inner_text()
        finally:
            browser.close()


def daemon_transcript(daemon):
    return daemon.transcript("s1").tail.path


def test_the_same_blocks_arriving_twice_are_not_shown_twice(page_at):
    """A reconnected stream re-sends the transcript from the beginning, and the
    first fetch and the first push can carry the same block. Each block knows
    its place, so it lands in the same slot either way."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            before = page.locator(".turn").count()
            assert before > 1
            blocks = daemon.read_transcript("s1")
            daemon.hub.send("transcript",
                            {"id": "s1", "blocks": [dict(b.__dict__) for b in blocks]},
                            session_id="s1")
            page.wait_for_timeout(800)
            assert page.locator(".turn").count() == before
        finally:
            browser.close()
