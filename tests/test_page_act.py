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


def test_an_open_question_stands_at_the_foot_of_the_transcript(ws, in_pane):
    """The row can say "needs you" and the reason line can name the question.
    Neither can hold the question and its answers, and that is what you came
    to the page for. It is the last thing in the conversation because it is
    the last thing in the conversation."""
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
            # Under the transcript and over the send box, on the screen and
            # not only in the markup: answering is sending, so the two belong
            # together and the question is the thing you read last.
            where = page.evaluate("""() => {
              const box = (id) =>
                document.getElementById(id).getBoundingClientRect();
              return [box('content').bottom, box('asking').top,
                      box('asking').bottom, box('sendbar').top];
            }""")
            assert where[0] <= where[1] + 1, where
            assert where[2] <= where[3] + 1, where
        finally:
            browser.close()


def test_a_question_belongs_to_the_transcript_and_no_other_tab(ws, in_pane):
    """It is not the bar over every tab that `PLAN.md` took away. The row
    still goes amber wherever you are, which is what the row is for; this is
    the answer to "what is it asking", and that is asked here."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking:not([hidden]) .askopt")
            for tab in ("files", "diff", "review", "session"):
                show_tab(page, tab)
                assert page.locator("#asking .askopt").count() == 0, tab
                assert page.locator("#asking:not([hidden])").count() == 0, tab
            show_tab(page, "transcript")
            page.wait_for_selector("#asking:not([hidden]) .askopt")
            assert page.locator("#asking .askopt").count() == 5
        finally:
            browser.close()


def option(question, at):
    return (f"#asking .askone:nth-child({question}) "
            f".askopts .askopt:nth-child({at})")


def test_picking_types_nothing_and_can_be_changed(ws, in_pane):
    """A click that went straight into a terminal was a click you could not
    take back, on a page you may have opened on a phone in a pocket."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking .askopt")
            page.click(option(1, 2))
            page.wait_for_timeout(300)
            assert page.locator(option(1, 2)).evaluate(
                "one => one.classList.contains('chosen')")
            # Nothing has reached the terminal, and the reader can change
            # their mind as often as they like.
            assert not [one for one in seen if "send-keys" in one]
            page.click(option(1, 3))
            assert not page.locator(option(1, 2)).evaluate(
                "one => one.classList.contains('chosen')")
            assert page.locator(option(1, 3)).evaluate(
                "one => one.classList.contains('chosen')")
            assert not [one for one in seen if "send-keys" in one]
        finally:
            browser.close()


def test_submit_waits_until_every_question_is_answered(ws, in_pane):
    """The agent asks them one after the other, so a half-filled submit
    would press a number at a question the reader never looked at."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking .asksend .verb")
            assert page.locator("#asking .asksend .verb").is_disabled()
            assert page.inner_text("#asking .asksays") == "pick an answer to each"
            page.click(option(1, 2))
            assert page.locator("#asking .asksend .verb").is_disabled()
            page.click(option(2, 1))
            assert not page.locator("#asking .asksend .verb").is_disabled()
            # And it says what it will do before it is pressed. These are
            # keystrokes into a live terminal.
            assert page.inner_text("#asking .asksays") == "presses 2, then 1"
        finally:
            browser.close()


def test_what_you_picked_survives_a_look_at_another_tab(ws, in_pane):
    """The bar is built again when it comes back, and a pick belongs to the
    question it was made for — not to the draw it was made on. Half-answering
    a question, glancing at the diff, and finding the marks gone is a page
    that cannot be trusted with the other half."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking .askopt")
            page.click(option(1, 3))
            show_tab(page, "diff")
            assert page.locator("#asking .askopt").count() == 0
            show_tab(page, "transcript")
            page.wait_for_selector("#asking .askopt")
            assert page.locator(option(1, 3)).evaluate(
                "one => one.classList.contains('chosen')")
            assert page.inner_text("#asking .asksays") == "pick an answer to each"
        finally:
            browser.close()


def test_submit_presses_the_numbers_in_the_order_they_were_asked(ws, in_pane):
    """A keystroke, not a paste: `tmux_send` sends one line literally and
    then presses Enter, which is exactly what a finger would do."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking .askopt")
            page.click(option(1, 3))
            page.click(option(2, 2))
            page.click("#asking .asksend .verb")
            page.wait_for_timeout(700)
            typed = [one[-1] for one in seen
                     if "send-keys" in one and "-l" in one]
            assert typed == ["3", "2"], seen
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
            page.click(option(1, 1))
            page.click(option(2, 1))
            page.click("#asking .asksend .verb")
            page.wait_for_timeout(600)
            assert page.locator("#asking .askopt").count() == 5
            # And what the reader picked stays picked. The rows arrive about
            # once a second while an agent works, and a bar rebuilt under the
            # reader would clear the marks and hand back a live submit for a
            # question already answered.
            assert page.locator(option(1, 1)).evaluate(
                "one => one.classList.contains('chosen')")
            assert page.locator("#asking .asksend .verb").is_disabled()
            daemon.hub.send("sessions", daemon.sessions_payload())
            page.wait_for_timeout(400)
            assert page.locator(option(1, 1)).evaluate(
                "one => one.classList.contains('chosen')")
            assert page.locator("#asking .asksend .verb").is_disabled()

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


def test_a_restarted_daemon_says_so_and_keeps_saying_it(ws, in_pane):
    """Restarting `serve` gives the daemon a new token, and an open page
    keeps the one printed into it. The stream is a GET and reconnects, so
    the sidebar goes on moving and the page looks alive while every send is
    refused -- in every session, because the token belongs to the daemon.

    It used to flash "that did not come from this page" for four seconds and
    then read "live" again, over a page where nothing worked.
    """
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.fill("#say", "before the restart")
            page.press("#say", "Enter")
            page.wait_for_function("document.getElementById('say').value === ''")

            daemon.token = "the token a restarted serve would make"

            page.fill("#say", "after the restart")
            page.press("#say", "Enter")
            # A bar over the whole page, because no strip this small can
            # carry "nothing you do here will work".
            page.wait_for_selector("body.outdated .stale")
            said = page.inner_text(".stale")
            assert "restarted" in said and "Reload" in said

            # The text is still there: they typed it at a terminal they
            # cannot see, and it never went in.
            assert page.input_value("#say") == "after the restart"
            # And the strip still says why, four seconds on.
            page.wait_for_timeout(4500)
            assert "restarted" in page.inner_text("#live")
        finally:
            browser.close()


def test_our_own_word_about_what_happened_still_fades(ws, in_pane):
    """"Review sent" is news, and news goes stale. Only a thing you asked
    for and did not get stays."""
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            said = page.evaluate("""async () => {
              note("review sent");
              return document.getElementById('live').textContent;
            }""")
            assert said == "review sent"
            page.wait_for_function(
                "document.getElementById('live').textContent !== 'review sent'",
                timeout=8000)
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
