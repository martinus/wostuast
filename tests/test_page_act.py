"""The three tmux verbs, and the send box.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations


import time

import pytest

import conftest
from browser import (
    skip_without_browser,
    sync_playwright,
    open_page,
    show_tab,
    base_of,
)

pytestmark = skip_without_browser

def test_jump_puts_the_cursor_in_the_pane(in_pane):
    """The button lives beside the pane it is about, in the Session tab. It
    used to sit in a bar over every tab, saying nothing the chosen row was not
    already saying."""
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            show_tab(page, "session")
            page.click(".sessionbody .verb")
            page.wait_for_timeout(400)
            assert ["tmux", "select-window", "-t", "%7"] in seen
            assert ["tmux", "select-pane", "-t", "%7"] in seen
        finally:
            browser.close()


# --- a question the agent is stopped on --------------------------------------

#: Two questions in one call, the shape a real `AskUserQuestion` sends.
ASKED = {"questions": [
    {"question": "Approve the plan and proceed?", "header": "Plan approval",
     "options": [
         {"label": "Approve", "description": "Start writing the test."},
         {"label": "Changes needed", "description": "Describe what to change."},
         {"label": "Abandon", "description": "Stop without committing."},
     ], "multiSelect": False},
    {"question": "Run it on every PR?", "header": "On every PR",
     "options": [
         {"label": "On demand", "description": "No annotation."},
         {"label": "Every PR", "description": "One more app start per build."},
     ], "multiSelect": False},
]}


def now_asking(ws, daemon, at=None):
    """The two events a real ask sends, folded into the daemon."""
    at = at or time.time()
    ws.append_event({"session_id": "s1", "hook_event_name": "PreToolUse",
                     "tool_name": "AskUserQuestion", "tool_input": ASKED,
                     "tool_use_id": "toolu_q1", "ts": at})
    ws.append_event({"session_id": "s1", "hook_event_name": "PermissionRequest",
                     "tool_name": "AskUserQuestion", "tool_input": ASKED,
                     "ts": at + 0.1})
    daemon.store.refresh()


def test_an_open_question_is_drawn_over_whatever_tab_you_are_on(ws, in_pane):
    """The row can say "needs you" and the reason line can name the question.
    Neither can hold the question and its answers, and that is what you came
    to the page for."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking:not([hidden]) .askopt")
            seen_text = page.eval_on_selector_all(
                "#asking .askhead", "els => els.map((one) => one.textContent)")
            assert seen_text == ["Plan approval", "On every PR"]
            options = page.eval_on_selector_all(
                "#asking .askone:nth-child(1) .askopt",
                """els => els.map((one) => [
                     one.querySelector('.asknum').textContent,
                     one.querySelector('.asklabel').textContent])""")
            assert options == [["1", "Approve"], ["2", "Changes needed"],
                               ["3", "Abandon"]]
            # And it stands over every tab, not only the one it was drawn on.
            for tab in ("files", "diff", "review", "session"):
                show_tab(page, tab)
                assert page.locator("#asking .askopt").count() == 5, tab
        finally:
            browser.close()


def test_picking_an_option_presses_its_number_in_the_terminal(ws, in_pane):
    """A keystroke, not a paste: `tmux_send` sends one line literally and
    then presses Enter, which is exactly what a finger would do."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking .askopt")
            page.click("#asking .askone:nth-child(1) .askopt:nth-child(2)")
            page.wait_for_timeout(500)
            assert ["tmux", "send-keys", "-t", "%7", "-l", "--", "2"] in seen
            assert ["tmux", "send-keys", "-t", "%7", "Enter"] in seen
            # No paste markers: a chooser reads keys, and a paste is not one.
            assert not [one for one in seen
                        if any("200~" in str(part) for part in one)]
        finally:
            browser.close()


def test_the_question_stays_until_the_daemon_says_it_was_answered(ws, in_pane):
    """Clearing it on the click would take away a question that a missed
    keystroke left standing, and the reader would never know."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking .askopt")
            page.click("#asking .askone:nth-child(1) .askopt:nth-child(1)")
            page.wait_for_timeout(600)
            assert page.locator("#asking .askopt").count() == 5
            # And the button the reader pressed stays pressed. The rows
            # arrive about once a second while an agent works, and a bar
            # rebuilt under the reader hands back an enabled button for a
            # question that has already been answered once.
            picked = "#asking .askone:nth-child(1) .askopt:nth-child(1)"
            assert page.locator(picked).is_disabled()
            daemon.hub.send("sessions", daemon.sessions_payload())
            page.wait_for_timeout(400)
            assert page.locator(picked).is_disabled()

            ws.append_event({"session_id": "s1", "hook_event_name": "PostToolUse",
                             "tool_name": "AskUserQuestion", "tool_input": ASKED,
                             "tool_use_id": "toolu_q1", "ts": time.time()})
            daemon.tick()            # fold it, and tell the page
            # `hidden` is an attribute, not a thing that can be waited for by
            # being visible: an element that is hidden never is.
            page.wait_for_function(
                "document.getElementById('asking').hidden === true",
                timeout=15000)
        finally:
            browser.close()


def test_a_session_with_no_question_shows_no_bar(ws, in_pane):
    """It is the bar `PLAN.md` took away. It comes back for one thing only,
    and it costs nothing the rest of the time."""
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            assert page.locator("#asking:not([hidden])").count() == 0
            assert page.locator("#asking .askopt").count() == 0
        finally:
            browser.close()


def test_the_send_box_types_into_the_terminal(in_pane):
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.fill("#say", "run the tests")
            page.press("#say", "Enter")
            page.wait_for_timeout(500)
            assert ["tmux", "send-keys", "-t", "%7", "-l", "--",
                    "run the tests"] in seen
            assert ["tmux", "send-keys", "-t", "%7", "Enter"] in seen
            # cleared only once the daemon said it went in
            assert page.input_value("#say") == ""
        finally:
            browser.close()


def test_the_send_box_keeps_the_text_when_it_did_not_go_in(ws, in_pane,
                                                           monkeypatch):
    """They typed it at a terminal they cannot see. Losing it is not on."""
    daemon, base, seen = in_pane
    monkeypatch.setattr(ws, "run", lambda args, **rest: None)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.fill("#say", "please work")
            page.press("#say", "Enter")
            page.wait_for_timeout(500)
            assert page.input_value("#say") == "please work"
        finally:
            browser.close()


def test_the_verbs_are_not_there_without_a_pane(no_pane):
    """Nothing to jump to, nothing to type into."""
    with sync_playwright() as play:
        browser, page = open_page(play, (None, no_pane[1]))
        try:
            assert page.locator("#sendbar").is_hidden()
            show_tab(page, "session")
            page.wait_for_selector(".sessionbody dl")
            assert "not in tmux" in page.locator(".sessionbody").inner_text()
            assert page.locator(".sessionbody .verb").count() == 0
        finally:
            browser.close()


def test_the_send_box_belongs_to_the_transcript(in_pane):
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base_of(in_pane)))
        try:
            assert page.locator("#sendbar").is_visible()
            show_tab(page, "files")
            assert page.locator("#sendbar").is_hidden()
            show_tab(page, "transcript")
            assert page.locator("#sendbar").is_visible()
        finally:
            browser.close()


# --- the send box -----------------------------------------------------------


def test_shift_and_enter_writes_a_second_line(in_pane):
    """Enter sends, which is what every chat box does. A prompt with a plan in
    it needs a way to write the second line."""
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.click("#say")
            page.keyboard.type("first line")
            page.keyboard.press("Shift+Enter")
            page.keyboard.type("second line")
            page.wait_for_timeout(300)
            assert page.input_value("#say") == "first line\nsecond line"
            assert seen == [], "shift and enter sent it"

            page.keyboard.press("Enter")
            page.wait_for_timeout(500)
            assert seen[0][-1] == ("\x1b[200~first line\nsecond line\x1b[201~")
            assert page.input_value("#say") == ""
        finally:
            browser.close()


def test_the_box_grows_with_what_is_in_it_and_shrinks_back(in_pane):
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            one = page.eval_on_selector("#say", "el => el.clientHeight")
            page.click("#say")
            for _ in range(4):
                page.keyboard.type("a line")
                page.keyboard.press("Shift+Enter")
            page.wait_for_timeout(300)
            many = page.eval_on_selector("#say", "el => el.clientHeight")
            assert many > one + 30, (one, many)
            # it does not grow for ever
            assert many < page.evaluate("window.innerHeight") / 2 + 40

            page.keyboard.press("Enter")
            page.wait_for_timeout(500)
            assert page.eval_on_selector("#say", "el => el.clientHeight") == one
        finally:
            browser.close()


def test_a_long_line_wraps_rather_than_running_off_the_side(in_pane):
    """A prompt whose start you cannot see is worse than two lines."""
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            one = page.eval_on_selector("#say", "el => el.clientHeight")
            page.fill("#say", "word " * 120)      # `fill` fires `input` itself
            page.wait_for_timeout(300)
            assert page.eval_on_selector("#say", "el => el.clientHeight") > one
            assert page.eval_on_selector(
                "#say", "el => el.scrollWidth <= el.clientWidth + 1"
            ), "it ran off the side instead of wrapping"
        finally:
            browser.close()


# --- naming a session from the page -------------------------------------------


def test_a_session_can_be_renamed_from_the_page(in_pane):
    """`/rename` in the terminal does not reach here: the name Claude Code
    hands the status line is the one the session started with. A name set here
    is ours and wins."""
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base_of(in_pane)))
        try:
            show_tab(page, "session")
            page.fill(".sessionbody .rename", "the parser")
            page.press(".sessionbody .rename", "Enter")
            # The row is where a name is read: there is no second place that
            # says it any more. The row puts the worktree in `.name` and the
            # session's own name in `.called`, which is what a rename changes.
            page.wait_for_function(
                "document.querySelector('.row .called').textContent"
                ".includes('the parser')")
        finally:
            browser.close()


def test_escape_leaves_the_name_as_it_was(in_pane):
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base_of(in_pane)))
        try:
            show_tab(page, "session")
            was = page.locator(".row .called").inner_text()
            page.fill(".sessionbody .rename", "not this")
            page.press(".sessionbody .rename", "Escape")
            page.wait_for_timeout(300)      # proving it did not go
            assert page.locator(".row .called").inner_text() == was
        finally:
            browser.close()


def test_an_empty_name_gives_the_session_its_place_back(in_pane):
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base_of(in_pane)))
        try:
            show_tab(page, "session")
            page.fill(".sessionbody .rename", "for a moment")
            page.press(".sessionbody .rename", "Enter")
            page.wait_for_function(
                "document.querySelector('.row .called').textContent"
                ".includes('for a moment')")
            page.fill(".sessionbody .rename", "")
            page.press(".sessionbody .rename", "Enter")
            page.wait_for_function(
                "!document.querySelector('.row .called').textContent"
                ".includes('for a moment')")
        finally:
            browser.close()


# --- the Session tab ---------------------------------------------------------


def test_the_session_tab_says_what_the_row_cannot(in_pane):
    """The bar that used to stand over every tab said the branch, the pane,
    the model and the state. Three of those the chosen row says already, one
    column to the left — and it cost 56 pixels of every tab to repeat them.
    What it said that the row does not say is here, with the rest."""
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base_of(in_pane)))
        try:
            assert page.locator(".session-head").count() == 0
            show_tab(page, "session")
            page.wait_for_selector(".sessionbody dl")
            said = page.locator(".sessionbody").inner_text()
            assert "%7" in said                      # the pane
            assert "/w/one" in said or "one" in said  # the whole path
            assert "session id" in said
        finally:
            browser.close()


def test_the_session_tab_counts_what_the_session_did(in_pane, ws):
    daemon, base, seen = in_pane
    ws.append_event(conftest.event("UserPromptSubmit", cwd="/w/one",
                                   ts=time.time(), prompt="do the thing"))
    daemon.store.refresh()
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            show_tab(page, "session")
            page.wait_for_selector(".sessionbody .counts")
            page.wait_for_function(
                """() => document.querySelector('.sessionbody .counts')
                     .textContent.includes('prompts')""")
            # And the log says the same thing in the order it happened.
            page.wait_for_function(
                """() => [...document.querySelectorAll('.sessionlog .said')]
                     .some((e) => e.textContent.includes('do the thing'))""")
        finally:
            browser.close()


def test_a_name_being_typed_survives_the_tab_redrawing(in_pane):
    """The panel is polled, and the name box is typed into. Rebuilding it
    under the reader would take the name with it — the rule the review keeps
    for its comments."""
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base_of(in_pane)))
        try:
            show_tab(page, "session")
            page.wait_for_selector(".sessionbody .rename")
            page.click(".sessionbody .rename")
            page.fill(".sessionbody .rename", "half a name")
            # Whatever the poll brings, and a state change on top of it.
            page.evaluate("""() => {
              state.events = {counts: {Stop: 3}, events: [], at: state.events.at + 1};
              draw();
            }""")
            page.wait_for_function(
                """() => document.querySelector('.sessionbody .counts')
                     .textContent.includes('3')""")
            assert page.input_value(".sessionbody .rename") == "half a name"
        finally:
            browser.close()
