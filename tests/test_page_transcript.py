"""The Transcript tab: what an agent said, and what it may not do to this page.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations

import json

import pytest

import conftest
from browser import (
    skip_without_browser,
    sync_playwright,
    open_page,
    daemon_transcript,
)

pytestmark = skip_without_browser

def test_the_page_draws_the_session(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            assert page.locator(".row").count() == 1
            # The worktree leads the row; what Claude Code called the session
            # goes under it, because the name is often long and often vague
            # and it used to push the worktree off the end.
            place = page.locator(".row .name").inner_text()
            assert place and "A session" not in place
            assert "A session" in page.locator(".row .called").inner_text()
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


def test_only_a_block_that_has_just_arrived_slides_in(page_at):
    """A transcript is rebuilt whenever anything about it changes. Animating
    every block on every rebuild would make the tab shiver each time an agent
    ran a tool, so the slide is for a block nobody has seen before."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            assert page.locator(".fresh").count() == 0, "the history slid in too"
            blocks = daemon.read_transcript("s1")
            one = dict(blocks[-1].__dict__)
            one.update(seq=len(blocks), kind="text", text="and one more thing")
            daemon.hub.send("transcript", {"id": "s1", "blocks": [one]},
                            session_id="s1")
            # In one question, so that a redraw cannot land between asking
            # whether it is there and asking how many there are.
            page.wait_for_function(
                "document.querySelectorAll('.fresh').length === 1")
            moving = ("() => getComputedStyle(document.querySelector('.turn'))"
                      ".animationName")
            assert page.evaluate(moving) == "none", "the whole history animates"
            # Drawing it again is not arriving again.
            page.evaluate("draw()")
            assert page.locator(".fresh").count() == 0
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


def test_typing_finds_text_in_the_transcript(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            everything = page.locator(".turn").count()
            page.locator("#find").fill("pytest")
            page.wait_for_timeout(250)
            assert page.locator(".turn").count() < everything
            assert page.locator("mark").count() >= 1
            assert "pytest" in page.locator("mark").first.inner_text().lower()
            assert " of " in page.locator("#live").inner_text()

            page.locator("#find").fill("")
            page.wait_for_timeout(250)
            assert page.locator(".turn").count() == everything
            assert page.locator("mark").count() == 0
        finally:
            browser.close()


def test_a_search_that_matches_nothing_says_so(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.locator("#find").fill("zzzznotherezzzz")
            page.wait_for_timeout(250)
            assert page.locator(".turn").count() == 0
            assert "Nothing here matches" in page.locator(".content").inner_text()
        finally:
            browser.close()


def test_searching_never_re_parses_what_an_agent_wrote(page_at):
    """Highlighting walks text nodes. A search that looks like markup must not
    become markup."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.locator("#find").fill("<img")
            page.wait_for_timeout(250)
            assert page.evaluate("window.PWNED ?? null") is None
            assert page.locator(".prose img").count() == 0
            assert page.locator("mark").count() >= 1
        finally:
            browser.close()


def test_a_regex_in_the_search_box_is_taken_literally(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.locator("#find").fill("len(hits)")
            page.wait_for_timeout(250)
            assert page.locator("mark").count() >= 1
            assert "len(hits)" in page.locator("mark").first.inner_text()
        finally:
            browser.close()


def test_keys_do_not_fire_while_typing_in_the_search_box(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.locator("#find").focus()
            page.keyboard.type("j")
            page.wait_for_timeout(150)
            assert page.locator("#find").input_value() == "j"
            assert page.evaluate("document.getElementById('help').open") is False
        finally:
            browser.close()


def test_without_marked_the_transcript_is_still_readable(page_at):
    """Markdown is written to be read as plain text, so a fetch that never
    arrives costs the rendering and nothing else. The tab is never blank."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at, with_marked=False)
        try:
            page.wait_for_timeout(700)
            assert page.evaluate("!!window.marked") is False
            said = page.locator(".prose").first.inner_text()
            assert said                       # there is text, not an empty box
            assert page.locator(".prose h1, .prose h2, .prose ul").count() == 0
            assert page.locator(".nohits").count() == 0
        finally:
            browser.close()


def test_marked_is_pinned_too(page_at):
    """Both fetched scripts carry the hash of their bytes. The page is served
    the real marked here, so this checks the pin as the browser does."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.wait_for_timeout(700)
            assert page.evaluate("!!window.marked") is True
            tag = page.locator("script[src*='marked']")
            assert tag.count() == 1
            assert tag.get_attribute("src").startswith("https://")
            assert tag.get_attribute("integrity").startswith("sha384-")
            assert tag.get_attribute("crossorigin") == "anonymous"
        finally:
            browser.close()
