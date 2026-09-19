"""The session list: state, filter, counts and history.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations

import time

import pytest

import conftest
from browser import (
    skip_without_browser,
    sync_playwright,
    fresh_context,
    open_page,
    two_rows,
)

pytestmark = skip_without_browser

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


def test_a_row_keeps_its_dot_when_the_state_changes(page_at, ws):
    """PLAN.md section 5.2: a row that changes state fades its dot. A fade
    needs the same dot on both sides of the change, and the sidebar used to be
    rebuilt whole, so the one change the fade is for was the one that threw it
    away."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.evaluate("window.__dot = document.querySelector('.row .dot')")
            assert "starting" in page.evaluate("window.__dot.className")
            ws.append_event(conftest.event(
                "PermissionRequest", tool_name="Bash",
                tool_input={"command": "ls ~"}, ts=time.time()))
            daemon.tick()            # fold it, and tell the page
            page.wait_for_function("window.__dot.className.includes('needs_you')")
            assert page.evaluate("window.__dot.isConnected"), "the row was rebuilt"
        finally:
            browser.close()


def test_a_row_shows_its_state_in_more_than_a_dot(page_at):
    """Nine sessions in a list are hard to read from one small dot."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            row = page.locator(".row").first
            edge = page.evaluate(
                "getComputedStyle(document.querySelector('.row')).borderLeftColor")
            face = page.evaluate(
                "getComputedStyle(document.querySelector('.row')).backgroundColor")
            plain = page.evaluate(
                "getComputedStyle(document.querySelector('.sidebar')).backgroundColor")
            assert edge not in ("rgba(0, 0, 0, 0)", "transparent")
            assert face != plain, "the row is not tinted by its state"
        finally:
            browser.close()


def test_the_sidebar_filter_narrows_the_list(pair_at):
    """One story on one page: type letters, type nonsense, press Escape."""
    with sync_playwright() as play:
        browser, page = open_page(play, pair_at)
        try:
            two_rows(page)
            counted = page.locator("#counts").inner_text()

            page.fill("#pick", "wmhr")          # scattered letters, as in Files
            page.wait_for_function("document.querySelectorAll('.row').length === 1")
            assert "warmhare" in page.locator(".row .name").inner_text()
            assert "1 of 2 sessions" in page.locator("#where").inner_text()
            # The counts are the answer to "who needs me". A filter in the box
            # must not hide an agent that is waiting.
            assert page.locator("#counts").inner_text() == counted

            page.fill("#pick", "nowhereatall")
            page.wait_for_selector(".rows .nohits")
            assert page.locator(".row").count() == 0

            page.press("#pick", "Escape")
            two_rows(page)
            assert page.input_value("#pick") == ""
        finally:
            browser.close()


def test_a_hidden_session_still_counts(pair_at, ws):
    """The counts, the title and the icon are about every session. They used to
    be drawn after the guard that asks whether the shown rows had changed, so
    with anything typed in the filter, a session you could not see going amber
    changed nothing anywhere on the page."""
    daemon, path = pair_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            two_rows(page)
            page.fill("#pick", "wmhr")         # hides s1, keeps warmhare
            page.wait_for_function("document.querySelectorAll('.row').length === 1")
            assert "needs you" not in page.locator("#counts").inner_text()

            ws.append_event(conftest.event(
                "PermissionRequest", sid="s1", tool_name="Bash",
                tool_input={"command": "ls ~"}, ts=time.time()))
            daemon.tick()
            page.wait_for_function(
                "document.getElementById('counts').innerText.includes('needs you')")
            assert page.locator(".row").count() == 1, "the filter stopped working"
            assert page.title().startswith("(1)")
        finally:
            browser.close()


def test_f_puts_the_cursor_in_the_session_filter(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.press("body", "f")
            assert page.evaluate("document.activeElement.id") == "pick"
            # And typing in it commands nothing: the tab must not change.
            page.press("#pick", "2")
            assert page.evaluate("state.tab") == "transcript"
        finally:
            browser.close()


def test_the_chosen_row_is_still_obvious(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            assert page.locator(".row.chosen").count() == 1
            ring = page.evaluate(
                "getComputedStyle(document.querySelector('.row.chosen')).outlineStyle")
            assert ring != "none"
        finally:
            browser.close()


def test_the_tab_says_what_is_happening(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            assert page.title() == "wostuast"      # this fixture has one quiet session
            icon = page.evaluate(
                "document.querySelector(\"link[rel='icon']\")?.getAttribute('href') || ''")
            assert icon.startswith("data:image/png"), "no icon was drawn"
        finally:
            browser.close()


def test_the_context_percent_is_a_bar(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            assert page.locator(".ctx .bar").count() == 1
            width = page.evaluate("document.querySelector('.ctx .fill').style.width")
            assert width == "41%"
            assert "41% ctx" in page.locator("#facts").inner_text()
        finally:
            browser.close()


def test_alerts_are_off_until_you_ask(page_at):
    """A page that asked for notification permission on load would be rude, and
    browsers punish it."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            assert page.locator("#bell").inner_text() == "alerts off"
            assert page.evaluate("Notification.permission") != "granted"
        finally:
            browser.close()


def test_finished_sessions_are_folded_away_under_history(past_at):
    with sync_playwright() as play:
        browser, page = open_page(play, past_at)
        try:
            page.wait_for_selector(".histhead")
            assert page.locator(".row").count() == 1, "only the live one is listed"
            assert "2" in page.locator(".histhead").inner_text()
            # It is the last thing in the list, under the live sessions.
            assert page.evaluate(
                "document.getElementById('rows').lastElementChild"
                ".classList.contains('histhead')")
            # And they are still counted: the fold is not a filter.
            assert "2 ended" in page.locator("#counts").inner_text()
            assert page.locator("#where").inner_text() == "3 sessions"
        finally:
            browser.close()


def test_history_opens_and_is_remembered(past_at):
    with sync_playwright() as play:
        browser = fresh_context(play)
        try:
            page = browser.new_page()
            page.goto(past_at[1], wait_until="domcontentloaded")
            page.wait_for_selector(".histhead")
            page.click(".histhead")
            page.wait_for_function("document.querySelectorAll('.row').length === 3")
            # The bar moves above the rows it opened.
            assert page.evaluate(
                "[...document.getElementById('rows').children]"
                ".findIndex((n) => n.classList.contains('histhead'))") == 1

            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector(".histhead")
            page.wait_for_function("document.querySelectorAll('.row').length === 3")
        finally:
            browser.close()


def test_a_finished_row_is_grey(past_at):
    with sync_playwright() as play:
        browser, page = open_page(play, past_at)
        try:
            page.click(".histhead")
            page.wait_for_selector(".row.ended")
            colours = page.evaluate("""() => {
              const live = document.querySelector(".row:not(.ended) .name");
              const past = document.querySelector(".row.ended .name");
              return [getComputedStyle(live).color, getComputedStyle(past).color];
            }""")
            assert colours[0] != colours[1], "a finished session looks live"
        finally:
            browser.close()


def test_the_filter_searches_the_history_too(past_at):
    """A search that cannot see half the sessions gives a wrong answer that
    looks like a right one."""
    with sync_playwright() as play:
        browser, page = open_page(play, past_at)
        try:
            page.wait_for_selector(".histhead")
            page.fill("#pick", "acorn")
            page.wait_for_function("document.querySelectorAll('.row').length === 1")
            assert "acorn" in page.locator(".row .name").inner_text()
        finally:
            browser.close()


def test_j_and_k_do_not_walk_into_a_folded_history(past_at):
    with sync_playwright() as play:
        browser, page = open_page(play, past_at)
        try:
            page.wait_for_selector(".histhead")
            for _ in range(5):
                page.press("body", "j")
            assert page.locator(".row.chosen").count() == 1
            assert page.evaluate("state.chosen") == "s1"
        finally:
            browser.close()
