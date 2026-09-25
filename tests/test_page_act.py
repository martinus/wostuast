"""The tmux verbs, the send box, and answering a question.

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
    wait_for_map,
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
              const pane = document.querySelector('.turnbody')
                .getBoundingClientRect();
              return [pane.bottom, box('asking').top,
                      box('asking').bottom, box('sendbar').top];
            }""")
            assert where[0] <= where[1] + 1, where
            assert where[2] <= where[3] + 1, where
        finally:
            browser.close()


def test_the_map_and_its_grip_run_down_beside_the_send_box(ws, in_pane):
    """The send box and the question bar stand under the transcript, not
    under the whole tab. The grip that sizes the map stopped where they
    began, so it read as a bar that ends for no reason -- and the corner
    under the map was empty space you could not drag."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking:not([hidden]) .askopt")
            wait_for_map(page)
            where = page.evaluate("""() => {
              const box = (one) => one.getBoundingClientRect();
              const content = document.getElementById('content');
              return {grip: box(content.querySelector(':scope > .grip')),
                      side: box(content.querySelector(':scope > .side')),
                      pane: box(content.querySelector('.turnbody')),
                      asking: box(document.getElementById('asking')),
                      send: box(document.getElementById('sendbar'))};
            }""")
            grip, side, send = where["grip"], where["side"], where["send"]
            assert abs(grip["bottom"] - send["bottom"]) <= 1, where
            assert abs(side["bottom"] - send["bottom"]) <= 1, where
            # And neither bar runs under the map or over the transcript.
            assert send["left"] >= grip["right"] - 1, where
            assert where["asking"]["left"] >= grip["right"] - 1, where
            assert where["pane"]["bottom"] <= where["asking"]["top"] + 1, where
            # The box runs down under both bars now, and the way back to the
            # foot of the transcript is measured from the pane, not the box:
            # from the box it would stand behind the send box.
            foot = page.evaluate("""() => {
              const button = document.querySelector('.tofoot');
              button.hidden = false;
              const at = button.getBoundingClientRect();
              button.hidden = true;
              return at;
            }""")
            assert where["pane"]["top"] < foot["top"], (foot, where)
            assert foot["bottom"] <= where["pane"]["bottom"], (foot, where)
            # The grip still drags, and it drags from the part that is new.
            before = side["width"]
            page.mouse.move(grip["left"] + 2, send["top"] + 5)
            page.mouse.down()
            page.mouse.move(grip["left"] + 62, send["top"] + 5, steps=4)
            page.mouse.up()
            after = page.evaluate("""() => document.querySelector(
                '#content > .side').getBoundingClientRect().width""")
            assert abs(after - before - 60) <= 2, (before, after)
            left = page.evaluate(
                "() => document.getElementById('sendbar')"
                ".getBoundingClientRect().left")
            assert abs(left - send["left"] - 60) <= 2, (send, left)
        finally:
            browser.close()


def test_a_question_belongs_to_the_transcript_and_no_other_tab(ws, in_pane):
    """It is not the header bar over every tab that was taken away. The row
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
            assert page.inner_text("#asking .asksays") == \
                "presses 2, then 1, then Enter"
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


def pressed(seen):
    """The keys that reached the pane, in order: a digit, `Tab`, `Enter`."""
    return [one[-1] for one in seen if one[:2] == ["tmux", "send-keys"]]


def test_submit_presses_the_numbers_in_the_order_they_were_asked(ws, in_pane):
    """Measured in Claude Code's own dialog: a digit answers a single-choice
    question *and moves on*, so the Enter this used to press after every
    number answered the next question with whatever sat under the cursor --
    and on the review, `2` is Cancel. One Enter, at the end, on "Submit
    answers"."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking .askopt")
            page.click(option(1, 3))
            page.click(option(2, 2))
            page.click("#asking .asksend .verb")
            page.wait_for_function(
                "() => document.querySelector('#asking .asksend .verb').disabled")
            deadline = time.time() + 15       # as the others: a loaded runner
            while len(pressed(seen)) < 3 and time.time() < deadline:
                time.sleep(0.05)
            assert pressed(seen) == ["3", "2", "Enter"], seen
            # A digit goes as the character, never as a key name.
            assert ["tmux", "send-keys", "-t", "%7", "-l", "--", "3"] in seen
            # No paste markers: a chooser reads keys, and a paste is not one.
            assert not [one for one in seen
                        if any("200~" in str(part) for part in one)]
        finally:
            browser.close()


#: One question that takes more than one answer, as the reader met it.
MANY = {"questions": [
    {"question": "Which of the remaining backport labels apply?",
     "header": "Labels", "multiSelect": True,
     "options": [
         {"label": "HardeningBackport", "description": "If a train is hardening."},
         {"label": "RolloutHotfix", "description": "A hotfix is recommended."},
         {"label": "RolloutBlocker", "description": "Rollout must stop."},
         {"label": "None", "description": "Leave the labels."},
     ]},
]}


def asking_many(ws, daemon, asked=MANY):
    ws.append_event({"session_id": "s1", "hook_event_name": "PreToolUse",
                     "tool_name": "AskUserQuestion", "tool_input": asked,
                     "tool_use_id": "toolu_many", "ts": time.time()})
    daemon.store.refresh()


def test_a_question_that_takes_many_answers_takes_many_and_submits(ws, in_pane):
    """It let you pick one and said to finish in the terminal; its submit
    pressed that one number and Enter, and in a multiple-choice dialog Enter
    ticks whatever is under the cursor -- so it ticked a second option and
    submitted nothing. Measured: a digit per option, Tab, then Enter on
    "Submit answers"."""
    daemon, base, seen = in_pane
    asking_many(ws, daemon)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking .askopt")
            page.click(option(1, 3))
            page.click(option(1, 2))
            page.click(option(1, 4))
            page.click(option(1, 4))            # and untick one again
            chosen = page.eval_on_selector_all(
                "#asking .askopt", "els => els.map(e => e.getAttribute('aria-pressed'))")
            assert chosen == ["false", "true", "true", "false"], chosen
            assert page.inner_text("#asking .asksays") == \
                "presses 2 3 Tab, then Enter"
            assert "finish it in the terminal" not in page.inner_text("#asking")
            page.click("#asking .asksend .verb")
            deadline = time.time() + 15       # as the others: a loaded runner
            while len(pressed(seen)) < 4 and time.time() < deadline:
                time.sleep(0.05)
            assert pressed(seen) == ["2", "3", "Tab", "Enter"], seen
        finally:
            browser.close()


SKETCH = "if (ok) {\n    parse();   // the indentation is the point\n}"
BESIDE = {"questions": [
    {"question": "How should the fix be scoped?", "header": "Scope",
     "multiSelect": False, "options": [
         {"label": "Narrow it", "description": "More state.",
          "preview": SKETCH},
         {"label": "Keep it", "description": "One marker.",
          "preview": "x" * 2001},
         {"label": "Drop it", "description": "Close the PR."},
         {"label": "Fenced", "description": "As an agent writes it.",
          "preview": "```cpp\nint x = 1;\n```"},
         {"label": "Markup", "description": "An agent wrote this.",
          "preview": "<img src=x onerror=\"window.hit=1\">"},
     ]},
    {"question": "Which checks?", "header": "Checks", "multiSelect": True,
     "options": [{"label": "Lint", "description": "", "preview": SKETCH},
                 {"label": "Tests", "description": ""}]},
]}


def test_the_preview_stands_beside_the_options_and_follows_the_pick(
        ws, in_pane):
    """Claude Code draws a box beside the options with the preview of the
    one under its cursor, and the page showed none of it: the reader chose
    without the code the choice was about. The box follows the pick, which
    types nothing, and says what the dialog says when there is nothing to
    show. It is text, never markup, because an agent wrote it."""
    daemon, base, seen = in_pane
    asking_many(ws, daemon, BESIDE)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.set_viewport_size({"width": 1600, "height": 1000})
            page.wait_for_selector("#asking .askpreview")

            def shown():
                return page.evaluate("""() => {
                  const pane = document.querySelector('#asking .askpreview');
                  const body = pane.querySelector('.askprevbody');
                  return [pane.querySelector('.askprevhead').textContent,
                          body.textContent, body.classList.contains('none')];
                }""")

            # Before a pick, the first: where the dialog's cursor starts.
            assert shown() == ["preview of 1. Narrow it", SKETCH, False]
            page.click(option(1, 2))
            assert shown() == [
                "preview of 2. Keep it",
                "(preview cannot be shown in full \u2014 compare the option "
                "labels and descriptions instead)", True]
            page.click(option(1, 3))
            assert shown() == ["preview of 3. Drop it",
                               "No preview available", True]
            page.click(option(1, 4))
            assert shown()[1] == "int x = 1;"
            page.click(option(1, 5))
            assert shown()[1] == BESIDE["questions"][0]["options"][4]["preview"]
            assert page.evaluate(
                "() => !document.querySelector('#asking img') && !window.hit")
            # Beside the options, not under them, where it stood below the
            # bar's fold.
            side = page.evaluate("""() => {
              const opts = document.querySelector('#asking .askbeside .askopts')
                .getBoundingClientRect();
              const pane = document.querySelector('#asking .askpreview')
                .getBoundingClientRect();
              return pane.left >= opts.right && pane.top < opts.bottom;
            }""")
            assert side
            # A multiple-choice question never stands beside a box.
            assert page.locator("#asking .askpreview").count() == 1
            assert page.locator(
                "#asking .askone:nth-child(2) .askpreview").count() == 0
        finally:
            browser.close()


def test_the_page_says_the_keys_the_daemon_presses(ws, in_pane):
    """The keys are worked out twice: on the page, to say them before they
    are pressed, and in the daemon, which presses its own. Change the rule in
    one and not the other and the reader is told one thing while another
    lands in their terminal."""
    daemon, base, seen = in_pane
    mixed = {"questions": [
        {"question": "Colour?", "header": "C", "multiSelect": False,
         "options": [{"label": "Red"}, {"label": "Green"}]},
        MANY["questions"][0],
        {"question": "Size?", "header": "S", "multiSelect": False,
         "options": [{"label": "S"}, {"label": "L"}]},
    ]}
    beside = {"questions": [dict(ASKED["questions"][0], options=[
        dict(ASKED["questions"][0]["options"][0], preview="if (ok) {\n}"),
        *ASKED["questions"][0]["options"][1:]])]}
    cases = [
        (MANY, [[4, 1]]),
        (ASKED, [[2], [1]]),
        ({"questions": [ASKED["questions"][0]]}, [[3]]),
        (mixed, [[2], [2, 4], [1]]),
        (beside, [[3]]),
        ({"questions": [*beside["questions"], *mixed["questions"]]},
         [[1], [2], [1, 2], [2]]),
    ]
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            for asked, picks in cases:
                ask = ws.read_ask({"tool_name": "AskUserQuestion",
                                   "tool_input": asked, "tool_use_id": "x"})
                keys, why = ws.ask_keys(ask, picks)
                assert not why, why
                shown = page.evaluate(
                    "([ask, picks]) => askKeys(ask, picks.map("
                    "(one) => one.map((n) => n - 1))).flat()", [ask, picks])
                assert shown == keys, (asked, picks, shown, keys)
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
    """It is not the header bar that was taken away. It stands for one thing
    only, and it costs nothing the rest of the time."""
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
            # The box empties as the text goes, so an empty box is not the
            # answer. The keys reaching the pane, and the send's lock let
            # go, are.
            deadline = time.time() + 15
            while not any("-l" in one for one in seen) and time.time() < deadline:
                time.sleep(0.05)
            page.wait_for_function("sending.size === 0")

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


def test_a_question_can_be_read_without_tmux_but_not_answered(ws, no_pane):
    """Reading the question is the one thing this page exists to tell you, so
    the bar stays wherever the session runs. Answering it is keystrokes into a
    tmux pane, and there is none — so the button is refused rather than left
    to fail on the press. It used to offer "presses 1" to a terminal that
    could never be typed into."""
    daemon, base = no_pane
    ws.append_event(conftest.event(
        "PreToolUse", pane="", tool_name="AskUserQuestion", tool_use_id="t1",
        ts=time.time(),
        tool_input={"questions": [{"question": "Which way?", "header": "Way",
                                   "multiSelect": False,
                                   "options": [{"label": "Left", "description": "a"},
                                               {"label": "Right", "description": "b"}]}]}))
    daemon.store.refresh()
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking:not([hidden])")
            assert "Which way?" in page.locator("#asking").inner_text()
            page.click("#asking .askopt >> nth=0")     # a complete answer
            page.wait_for_function(
                """() => document.querySelector('#asking .askopt.chosen') !== null""")
            assert page.locator("#asking .asksend .verb").is_disabled()
            assert "not in tmux" in page.locator(".asksays").inner_text()
        finally:
            browser.close()


def test_a_spend_limit_is_not_offered_where_nothing_can_be_pressed(no_pane):
    """jump and stop are simply absent for such a session. The box stays,
    disabled, because the panel is where you go to find out what a session is
    — but it used to take a number and warn only once one had been typed."""
    _, base = no_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            show_tab(page, "session")
            page.wait_for_selector(".limitbox")
            assert page.locator(".limitbox").is_disabled()
            assert "not in tmux" in page.locator(".limitrow").inner_text()
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


def test_enter_twice_sends_once_and_keeps_what_came_after(in_pane):
    """A second Enter before the daemon answered typed the prompt into the
    pane twice, and the answer then cleared whatever had been typed since,
    which had gone nowhere."""
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.evaluate("""() => {
              const real = window.fetch;
              window.fetch = (url, opts) => String(url).endsWith("/send")
                ? new Promise((done) => setTimeout(
                    () => done(real(url, opts)), 3000))
                : real(url, opts);
            }""")
            page.click("#say")
            page.keyboard.type("run the tests")
            page.keyboard.press("Enter")
            page.keyboard.press("Enter")
            # New words and a third Enter while the first send is on its way:
            # two sends at once can interleave their text and Enter commands
            # into one prompt, so this one waits in the box.
            page.keyboard.type(" and then")
            page.keyboard.press("Enter")
            page.wait_for_function(
                "document.getElementById('say').value === ' and then'")

            def typed():
                return [one for one in seen if "-l" in one]

            # Wait for the send to land, then long enough for a second one.
            deadline = time.time() + 15
            while not typed() and time.time() < deadline:
                time.sleep(0.05)
            page.wait_for_timeout(600)
            assert typed() == [["tmux", "send-keys", "-t", "%7", "-l", "--",
                                "run the tests"]], seen
        finally:
            browser.close()


def test_a_refused_send_comes_back_in_front_of_what_was_typed_since(
        ws, in_pane, monkeypatch):
    """The text leaves the box as it goes. When tmux refuses it, it comes
    back, and what was typed while it was on its way stays after it."""
    daemon, base, seen = in_pane
    monkeypatch.setattr(ws, "run", lambda args, **rest: None)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.evaluate("""() => {
              const real = window.fetch;
              window.fetch = (url, opts) => String(url).endsWith("/send")
                ? new Promise((done) => setTimeout(
                    () => done(real(url, opts)), 400))
                : real(url, opts);
            }""")
            page.click("#say")
            page.keyboard.type("please work")
            page.keyboard.press("Enter")
            page.keyboard.type(" and more")
            page.wait_for_function("document.getElementById('say').value"
                                   " === 'please work and more'")
        finally:
            browser.close()


def test_enter_on_a_button_reached_by_keyboard_presses_it(in_pane):
    """Enter jumped to the pane from wherever the focus was, so a keyboard
    could press nothing on the page. After a click it still jumps: the click
    leaves the focus on the button, and Enter then is the jump key."""
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.focus(".tab[data-tab='review']")
            page.keyboard.press("Shift+Tab")
            page.keyboard.press("Tab")
            assert page.evaluate(
                "document.activeElement.matches('.tab[data-tab=review]')")
            page.keyboard.press("Enter")
            page.wait_for_function("state.tab === 'review'")
            page.wait_for_timeout(300)
            assert not [one for one in seen if "select-window" in one], seen

            # A click leaves the focus on the tab it pressed, but not
            # `:focus-visible`: Enter there is still the jump key.
            page.click(".tab[data-tab='files']")
            assert page.evaluate("document.activeElement.matches('.tab')")
            page.keyboard.press("Enter")
            deadline = time.time() + 15
            while (["tmux", "select-window", "-t", "%7"] not in seen
                   and time.time() < deadline):
                time.sleep(0.05)
            assert ["tmux", "select-window", "-t", "%7"] in seen
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


# --- stopping an agent, and the limit that does it for you --------------------


def test_the_stop_button_presses_escape_and_not_ctrl_c(in_pane):
    """Escape stops the turn and keeps the work done so far. Ctrl-C into a
    prompt that has just gone idle is one press away from ending the
    session — see `tmux_interrupt`."""
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            show_tab(page, "session")
            page.wait_for_selector(".sessionbody .verb")
            seen.clear()
            page.click(".sessionbody .verb:text-is('stop')")
            page.wait_for_function(
                "() => document.getElementById('live').innerText"
                ".includes('Escape')")
            assert seen == [["tmux", "send-keys", "-t", "%7", "Escape"]], seen
        finally:
            browser.close()


def test_a_spend_limit_is_set_from_the_panel_and_comes_back(ws, in_pane):
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            show_tab(page, "session")
            page.wait_for_selector(".limitbox")
            assert page.input_value(".limitbox") == ""
            seen.clear()
            # Every limit this page asks for, kept where nothing repaints it.
            # It must be one, for 12 — on `input` rather than `change` the
            # box posts $1 on the way to $12, and a session already past a
            # dollar is stopped by a number the reader was still typing.
            page.evaluate("""() => { window.__asked = [];
              const real = tell;
              tell = (id, what, body) => {
                if (what === 'limit') window.__asked.push(body.limit);
                return real(id, what, body);
              }; }""")
            page.click(".limitbox")
            page.type(".limitbox", "12", delay=40)
            page.keyboard.press("Tab")           # `change`, not every keystroke
            # The daemon has it first. Like a rename, setting one pushes
            # nothing: the rows are built from the map on the next pass, so
            # the browsers hear about it when that pass happens.
            wait_until(lambda: ws.read_limits().get("s1", {}).get("limit") == 12.0)
            assert seen == [], "setting a limit must write no terminal"
            assert page.evaluate("window.__asked") == [12], \
                page.evaluate("window.__asked")
            daemon.tick()
            page.wait_for_function(
                "() => state.sessions[0].spend_limit === 12")
            # And it says what it will *actually* do. This session's status
            # line has sent no spend, so nothing could ever fire, and saying
            # "Escape when the spend passes it" would be a promise this
            # program cannot keep.
            page.wait_for_function(
                """() => document.querySelector('.limitrow')
                     .innerText.includes('does not send the spend')""")

            # With a spend, it promises what it can do.
            daemon.store.sessions["s1"].status = ws.Status(ts=1.0, cost_usd=2.0)
            daemon.tick()
            page.wait_for_function(
                """() => document.querySelector('.limitrow')
                     .innerText.includes('Escape into this pane')""")

            # Emptying it takes the limit away.
            page.fill(".limitbox", "")
            page.keyboard.press("Tab")
            wait_until(lambda: ws.read_limits() == {})
            daemon.tick()
            page.wait_for_function("() => !state.sessions[0].spend_limit")
        finally:
            browser.close()


def test_a_limit_typed_after_another_session_is_chosen_is_that_sessions(
        ws, in_pane, tmp_path):
    """The box kept the focus when an alert or a link chose another session,
    so it was never rebuilt: the panel stood over the old session's box, and
    a number typed to protect the new one set the old one's limit."""
    daemon, base, seen = in_pane
    ws.append_event(conftest.event("SessionStart", sid="s2", cwd=str(tmp_path),
                                   pane="%9", pid=2, ts=time.time()))
    daemon.store.refresh()
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            page.wait_for_function("document.querySelectorAll('.row').length === 2")
            # Both seen on the Session tab, so each comes back to it.
            for one in ("s2", "s1"):
                page.evaluate(f"choose('{one}')")
                show_tab(page, "session")
                page.wait_for_function(
                    "(id) => { const one = document.querySelector('.limitfield');"
                    "          return one && one.dataset.id === id; }", arg=one)
            page.click(".limitbox")
            page.keyboard.type("7")
            # An alert clicked: `choose` runs with the focus where it was.
            page.evaluate("choose('s2')")
            page.wait_for_function(
                "() => { const one = document.querySelector('.limitfield');"
                "        return one && one.dataset.id === 's2'; }")
            page.click(".limitbox")
            page.keyboard.type("9")
            page.keyboard.press("Tab")
            wait_until(lambda: ws.read_limits().get("s2", {}).get("limit") == 9.0)
            # And the 7 half typed in s1's box was never given: no Enter, no
            # Tab, no click away. Stored, it would stop s1 at seven dollars
            # on the way to seventy-five.
            assert "s1" not in ws.read_limits(), ws.read_limits()
        finally:
            browser.close()


@pytest.mark.parametrize("typed", ["10e", "-5"])
def test_a_limit_the_box_cannot_read_leaves_the_limit_standing(ws, in_pane, typed):
    """A number box reads `10e` as empty, and empty means "no limit": one slip
    of the hand took the limit away and the panel went quiet about it. A
    negative number did the same through `!(asked > 0)`."""
    daemon, base, seen = in_pane
    daemon.store.set_limit("s1", 10.0)
    daemon.tick()
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            show_tab(page, "session")
            page.wait_for_function(
                "() => { const box = document.querySelector('.limitbox');"
                "        return box && box.value === '10'; }")
            page.click(".limitbox", click_count=3)
            page.keyboard.type(typed)
            page.keyboard.press("Tab")
            page.wait_for_function(
                "() => state.trouble.includes('a limit is a number of dollars')")
            assert page.input_value(".limitbox") == "10"
            assert ws.read_limits()["s1"]["limit"] == 10.0
        finally:
            browser.close()


def test_an_escape_tmux_refused_is_not_called_a_stop(ws, in_pane, monkeypatch):
    """The panel said "stopped · raise it to go on" over an agent still
    spending, because the key that would have stopped it never landed."""
    daemon, base, seen = in_pane
    monkeypatch.setattr(ws, "tmux_interrupt", lambda pane: False)
    ws.append_event(conftest.event("UserPromptSubmit", pane="%7",
                                   prompt="go", ts=time.time()))
    daemon.store.refresh()
    daemon.store.sessions["s1"].status = ws.Status(ts=1.0, cost_usd=30.0)
    daemon.store.set_limit("s1", 10.0)
    daemon.tick()
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            show_tab(page, "session")
            page.wait_for_function(
                """() => { const one = document.querySelector('.limitrow');
                           return one && one.innerText.includes('refused'); }""")
            said = page.locator(".limitrow").inner_text()
            assert "stopped" not in said, said
            assert "tried again" in said, said
        finally:
            browser.close()


def test_a_session_stopped_by_its_limit_says_so_where_you_would_look(ws, in_pane):
    """"Why did my agent stop" is asked in front of this panel, not in the
    pane — and raising the box is what lets it go again."""
    daemon, base, seen = in_pane
    ws.append_event(conftest.event("UserPromptSubmit", pane="%7",
                                   prompt="go", ts=time.time()))
    daemon.store.refresh()
    daemon.store.sessions["s1"].status = ws.Status(ts=1.0, cost_usd=30.0)
    daemon.store.set_limit("s1", 10.0)
    daemon.tick()
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            show_tab(page, "session")
            page.wait_for_function(
                """() => { const one = document.querySelector('.limitrow');
                           return one && one.innerText.includes('stopped'); }""")
            said = page.locator(".limitrow").inner_text()
            assert "raise it to go on" in said, said
            assert page.input_value(".limitbox") == "10"
        finally:
            browser.close()


def wait_until(said, seconds=10):
    """Wait for something the daemon knows, rather than for the page to be
    told: a POST that writes no terminal pushes nothing, so the browser only
    hears about it on the next pass."""
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if said():
            return
        time.sleep(0.02)
    raise AssertionError("the daemon never got it")


def test_a_limit_being_typed_survives_the_panel_redrawing(in_pane):
    """`rest` is rebuilt on every four-second poll. A rebuild under the hand
    is worse here than for the name: the node is removed rather than blurred,
    so `change` never fires and the number is not merely lost on screen — it
    is never stored at all."""
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base_of(in_pane)))
        try:
            show_tab(page, "session")
            page.wait_for_selector(".limitbox")
            page.click(".limitbox")
            page.type(".limitbox", "25", delay=20)
            # Whatever the poll brings, and a state change on top of it.
            page.evaluate("""() => {
              state.events = {counts: {Stop: 3}, events: [], at: state.events.at + 1};
              draw();
            }""")
            page.wait_for_function(
                """() => document.querySelector('.sessionbody .counts')
                     .textContent.includes('3')""")
            assert page.input_value(".limitbox") == "25"
            assert page.evaluate(
                "document.activeElement.className") == "limitbox"
        finally:
            browser.close()


def test_a_limit_being_typed_survives_its_own_news(ws, in_pane):
    """The narrow key keeps the poll's churn out, but the limit field has
    news of its own — a status line that starts reporting a spend, or a limit
    that has just fired. Without the focus guard that news rebuilds the box
    under the hand, and the node is removed rather than blurred, so `change`
    never fires and the number is gone."""
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            show_tab(page, "session")
            page.wait_for_selector(".limitbox")
            page.click(".limitbox")
            page.type(".limitbox", "25", delay=20)
            # Exactly what `limitKey` watches, arriving mid-word.
            page.evaluate("""() => { state.sessions[0].cost_usd = 3.5;
                                     draw(); }""")
            page.wait_for_timeout(200)   # proving something did not happen
            assert page.input_value(".limitbox") == "25"
            assert page.evaluate(
                "document.activeElement.className") == "limitbox"
        finally:
            browser.close()


# --- a permission request: read whole, declined from here, never approved ----

BUILD = ("cmake --build build -j && "
         + " && ".join(f"ctest -R case{n} --output-on-failure" for n in range(12)))


def now_permission(ws, daemon, calls=("toolu_b1",), pane="%7"):
    """A real dialog's events: its call starting, then the request 90 ms on.
    Two calls reading the same leave the dialog with no call of its own."""
    at = time.time()
    shown = {"command": BUILD, "description": "Build and test"}
    cwd = daemon.store.sessions["s1"].cwd
    for call in calls:
        ws.append_event(conftest.event("PreToolUse", tool_name="Bash",
                                       tool_input=shown, pane=pane, cwd=cwd,
                                       tool_use_id=call, ts=at))
    ws.append_event(conftest.event("PermissionRequest", tool_name="Bash",
                                   tool_input=shown, pane=pane, cwd=cwd,
                                   ts=at + 0.09))
    daemon.store.refresh()


def test_a_permission_is_read_whole_and_declined_with_a_reason(
        ws, in_pane, monkeypatch):
    """The row said the request in one clipped line. Here it stands whole,
    field by field, with no way to approve it: that is the terminal's, which
    the first button opens. No presses Escape; the reason is typed once the
    transcript shows the dialog closed, and the bar goes with the daemon's
    own record of the decline."""
    daemon, base, seen = in_pane
    path = daemon.store.sessions["s1"].transcript_path
    with open(path, "a") as handle:
        handle.write(conftest.records(conftest.record("tool", BUILD, tool_id="toolu_b1")))

    def runner(args, **rest):
        seen.append(list(args))
        if args[-1] == "Escape":
            with open(path, "a") as handle:
                handle.write(conftest.records(conftest.record(
                    "result", "The user doesn't want to proceed", tool_id="toolu_b1")))
        return ""

    monkeypatch.setattr(ws, "run", runner)
    now_permission(ws, daemon)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking:not([hidden]) .permfield")
            assert page.locator("#asking .askwhat").inner_text() == "May it use Bash?"
            fields = page.eval_on_selector_all(
                "#asking .permfield", """els => els.map((one) => [
                  one.querySelector('.askprevhead').textContent,
                  one.querySelector('.askprevbody').textContent])""")
            assert fields == [["command", BUILD], ["description", "Build and test"]]
            buttons = page.eval_on_selector_all(
                "#asking button", "els => els.map((one) => one.textContent)")
            assert buttons == ["open the terminal", "no"], buttons
            page.fill("#asking .permwhy", "Use the ninja build instead")
            # What the page says, kept: the slot is repainted on every push.
            page.evaluate("""() => { window.words = []; const was = note;
              note = (word) => { window.words.push(word); was(word); }; }""")
            page.click("#asking .permno")
            page.wait_for_function(
                "window.words.includes('declined, and your reason was typed')")
            deadline = time.time() + 15
            while not any("-l" in one for one in seen) and time.time() < deadline:
                time.sleep(0.05)
            keys = [one[-1] for one in seen if one[:2] == ["tmux", "send-keys"]]
            assert keys[0] == "Escape", keys
            assert "Use the ninja build instead" in keys, keys
            daemon.tick()
            page.wait_for_selector("#asking", state="hidden")
        finally:
            browser.close()


def test_a_dialog_with_no_call_of_its_own_takes_no_reason(ws, in_pane):
    """Nothing can prove it closed, so no reason is typed for it -- and a box
    that took one and then dropped it would be worse than none."""
    daemon, base, seen = in_pane
    now_permission(ws, daemon, calls=("toolu_b1", "toolu_b2"))
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking:not([hidden]) .permfield")
            assert page.locator("#asking .permwhy").is_disabled()
            assert not page.locator("#asking .permno").is_disabled()
            says = page.locator("#asking .asksays").inner_text()
            assert "cannot be typed" in says
            # A Yes in the terminal fires no hook: the warning holds here too.
            assert "Escape stops the agent" in says
        finally:
            browser.close()


def test_a_permission_can_be_read_without_tmux_but_not_declined(ws, no_pane):
    daemon, base = no_pane
    now_permission(ws, daemon, pane="")
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking:not([hidden]) .permfield")
            assert page.locator("#asking .permno").is_disabled()
            assert "not in tmux" in page.locator("#asking .asksays").inner_text()
            # Nothing to open: absent, like jump everywhere else.
            buttons = page.eval_on_selector_all(
                "#asking button", "els => els.map((one) => one.textContent)")
            assert buttons == ["no"], buttons
        finally:
            browser.close()


def test_a_reason_half_written_survives_a_look_at_another_tab(ws, in_pane):
    """The bar is built again when the Transcript tab comes back, and the
    question bar's scar is half an answer lost that way."""
    daemon, base, seen = in_pane
    now_permission(ws, daemon)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking:not([hidden]) .permwhy")
            page.fill("#asking .permwhy", "Use the ninja build")
            show_tab(page, "diff")
            show_tab(page, "transcript")
            page.wait_for_selector("#asking:not([hidden]) .permwhy")
            assert page.input_value("#asking .permwhy") == "Use the ninja build"
        finally:
            browser.close()


def test_a_no_waits_for_a_send_already_on_its_way(ws, in_pane):
    """One thing typed into a session at a time: a send landing between the
    Escape and the proof would be typed into a dialog that may be up."""
    daemon, base, seen = in_pane
    now_permission(ws, daemon)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.wait_for_selector("#asking:not([hidden]) .permno")
            page.evaluate("sending.add(state.chosen)")
            page.click("#asking .permno")
            page.wait_for_timeout(500)        # proving nothing was pressed
            assert not [one for one in seen if one[-1] == "Escape"], seen
        finally:
            browser.close()
