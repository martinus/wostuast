"""The tmux verbs, the send box, and answering a question.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations


import threading
import time

import pytest

import conftest
from browser import (
    skip_without_browser,
    opened,
    show_tab,
    base_of,
    wait_for_map,
    hold,
    wait_until,
    stub_send,
)

pytestmark = skip_without_browser

def test_jump_puts_the_cursor_in_the_pane(in_pane):
    """The button is an icon at the end of the tab row, outside every tab,
    and a click asks the daemon to jump -- the Enter key's verb."""
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
        assert page.locator("#jump").is_visible()
        assert not [one for one in seen if "select-window" in one], seen
        page.click("#jump")
        deadline = time.time() + 15
        while (["tmux", "select-pane", "-t", "%7"] not in seen
               and time.time() < deadline):
            time.sleep(0.05)
        assert ["tmux", "select-window", "-t", "%7"] in seen
        assert ["tmux", "select-pane", "-t", "%7"] in seen



def test_a_jump_says_it_went_and_a_failed_one_does_not(ws, in_pane, monkeypatch):
    """The jump happens in another window, often on another screen, and the
    page said nothing when it worked: a press that went looked like a key
    that did nothing. The button ticks and the slot names the session. A
    jump tmux refused shows its error and no tick."""
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
        page.click("#jump")
        page.wait_for_selector("#jump.done")
        assert page.get_attribute("#jump", "title") == "jumped"
        assert page.locator("#jump .icon").count() == 1
        name = page.evaluate("rowName(current())")
        assert page.inner_text("#live") == "jumped to " + name
        # And back to itself, with nothing piled up from the press.
        page.wait_for_selector("#jump:not(.done)")
        assert page.get_attribute("#jump", "title").startswith("jump to")
        assert page.locator("#jump .icon").count() == 1

        # tmux refuses: the error stands, and nothing ticks -- not even
        # for a moment, which a look after the error would miss.
        monkeypatch.setattr(ws, "run", lambda args, **rest: None)
        page.evaluate("""() => {
          window.ticked = false;
          new MutationObserver(() => {
            if (document.getElementById('jump').classList.contains('done')) {
              window.ticked = true;
            }
          }).observe(document.getElementById('jump'), { attributes: true });
        }""")
        page.keyboard.press("Enter")
        page.wait_for_function(
            "document.getElementById('live').textContent.includes('tmux')")
        assert page.evaluate("window.ticked") is False

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
    with opened((None, base)) as page:
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


def test_the_map_and_its_grip_run_down_beside_the_send_box(ws, in_pane):
    """The send box and the question bar stand under the transcript, not
    under the whole tab. The grip that sizes the map stopped where they
    began, so it read as a bar that ends for no reason -- and the corner
    under the map was empty space you could not drag."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with opened((None, base)) as page:
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


def drag_edge(page, selector, dx, dy, at=None):
    """Press on an edge, move it by `dx`, `dy` in steps, and let go. `at`
    is the point pressed, from the edge's top left; its middle by default."""
    edge = page.locator(selector).bounding_box()
    x, y = at or (edge["width"] / 2, edge["height"] / 2)
    page.mouse.move(edge["x"] + x, edge["y"] + y)
    page.mouse.down()
    page.mouse.move(edge["x"] + x + dx, edge["y"] + y + dy, steps=4)
    page.mouse.up()


def test_the_maps_edge_draws_no_line_and_drags_from_beside_it(in_pane):
    """A bar of 5 px in the edge colour, heavier than anything on the page
    (#443). Then a line of one pixel, and the reader found the page busy
    with lines: it draws nothing now, and its handle, wider than the
    column, is found with a mouse all the same."""
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
        wait_for_map(page)
        grip = "#content > .grip"
        assert page.locator(grip).bounding_box()["width"] == 1
        assert page.eval_on_selector(
            grip, "el => getComputedStyle(el).backgroundColor") in (
                "rgba(0, 0, 0, 0)", "transparent")
        before = page.locator("#content > .side").bounding_box()["width"]
        drag_edge(page, grip, 40, 0, at=(3, 200))       # 2 px beside the line
        after = page.locator("#content > .side").bounding_box()["width"]
        assert abs(after - before - 40) <= 2, (before, after)


def test_a_line_between_two_grounds_is_not_drawn(in_pane):
    """The reader found the page busy with lines that all looked alike
    (#443). The send bar has a ground of its own, and the find box and the
    count under it are one head with one line under it."""
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
        wait_for_map(page)
        page.wait_for_selector("#sendbar:not([hidden])")
        widths = page.evaluate("""() => [
          getComputedStyle($('sendbar')).borderTopWidth,
          getComputedStyle(document.querySelector('#content > .side > .findslot'))
            .borderBottomWidth,
          getComputedStyle(document.querySelector('#content > .side > .listnote'))
            .borderBottomWidth]""")
        assert widths == ["0px", "0px", "1px"], widths


def test_the_send_box_is_as_tall_as_its_edge_is_dragged(in_pane):
    """The send bar's top edge drags the box's height (#442), empty or
    full, and the box still grows past it as lines are typed (#453); a
    reload keeps it, and a double-click gives the box back to its text."""
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
        page.wait_for_selector("#sendbar:not([hidden]) #say")
        height = lambda: page.locator("#say").bounding_box()["height"]
        assert height() == 32
        drag_edge(page, "#saygrip", 0, -120)
        assert abs(height() - 152) <= 2, height()
        # Still grows as lines are typed past it (#453).
        page.click("#say")
        for _ in range(10):
            page.keyboard.press("Shift+Enter")
        page.keyboard.type("the last line")
        assert height() > 200, height()
        page.fill("#say", "")
        page.evaluate("fitSay()")
        assert abs(height() - 152) <= 2, height()
        page.reload()
        page.wait_for_selector("#sendbar:not([hidden]) #say")
        assert abs(height() - 152) <= 2, height()
        page.dblclick("#saygrip")
        assert height() == 32


def test_a_question_belongs_to_the_transcript_and_no_other_tab(ws, in_pane):
    """It is not the header bar over every tab that was taken away. The row
    still goes amber wherever you are, which is what the row is for; this is
    the answer to "what is it asking", and that is asked here."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with opened((None, base)) as page:
        page.wait_for_selector("#asking:not([hidden]) .askopt")
        for tab in ("files", "diff"):
            show_tab(page, tab)
            assert page.locator("#asking .askopt").count() == 0, tab
            assert page.locator("#asking:not([hidden])").count() == 0, tab
        show_tab(page, "transcript")
        page.wait_for_selector("#asking:not([hidden]) .askopt")
        assert page.locator("#asking .askopt").count() == 5


def option(question, at):
    return (f"#asking .askone:nth-child({question}) "
            f".askopts .askopt:nth-child({at})")


def test_picking_types_nothing_and_can_be_changed(ws, in_pane):
    """A click that went straight into a terminal was a click you could not
    take back, on a page you may have opened on a phone in a pocket."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with opened((None, base)) as page:
        page.wait_for_selector("#asking .askopt")
        page.click(option(1, 2))
        page.wait_for_timeout(300)
        assert page.locator(option(1, 2)).evaluate(
            "one => one.classList.contains('chosen')")
        # Nothing has reached the terminal, and the reader can change
        # their mind as often as they like.
        assert not conftest.into_pane(seen)
        page.click(option(1, 3))
        assert not page.locator(option(1, 2)).evaluate(
            "one => one.classList.contains('chosen')")
        assert page.locator(option(1, 3)).evaluate(
            "one => one.classList.contains('chosen')")
        assert not conftest.into_pane(seen)


def test_submit_waits_until_every_question_is_answered(ws, in_pane):
    """The agent asks them one after the other, so a half-filled submit
    would press a number at a question the reader never looked at."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with opened((None, base)) as page:
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
        # Submit at the right edge, after what it does, as on a permission.
        lefts = page.evaluate("""() => ['.asksays', '.asksend .verb'].map((one) =>
          document.querySelector('#asking ' + one).getBoundingClientRect().left)""")
        assert lefts[0] < lefts[1], lefts


def test_what_you_picked_survives_a_look_at_another_tab(ws, in_pane):
    """The bar is built again when it comes back, and a pick belongs to the
    question it was made for — not to the draw it was made on. Half-answering
    a question, glancing at the diff, and finding the marks gone is a page
    that cannot be trusted with the other half."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with opened((None, base)) as page:
        page.wait_for_selector("#asking .askopt")
        page.click(option(1, 3))
        show_tab(page, "diff")
        assert page.locator("#asking .askopt").count() == 0
        show_tab(page, "transcript")
        page.wait_for_selector("#asking .askopt")
        assert page.locator(option(1, 3)).evaluate(
            "one => one.classList.contains('chosen')")
        assert page.inner_text("#asking .asksays") == "pick an answer to each"


def pressed(seen):
    """The keys that reached the pane, in order: a digit, `Tab`, `Enter`."""
    return conftest.pressed(seen)


def test_submit_presses_the_numbers_in_the_order_they_were_asked(ws, in_pane):
    """Measured in Claude Code's own dialog: a digit answers a single-choice
    question *and moves on*, so the Enter this used to press after every
    number answered the next question with whatever sat under the cursor --
    and on the review, `2` is Cancel. One Enter, at the end, on "Submit
    answers"."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with opened((None, base)) as page:
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
        # A digit goes as the character, never as a key name, and with no
        # paste markers: a chooser reads keys, and a bracketed paste is text.
        assert ("3", False) in conftest.pastes(seen)
        assert not [one for one in conftest.pastes(seen) if one[1]]


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
    with opened((None, base)) as page:
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
    with opened((None, base)) as page:
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
    with opened((None, base)) as page:
        for asked, picks in cases:
            ask = ws.read_ask({"tool_name": "AskUserQuestion",
                               "tool_input": asked, "tool_use_id": "x"})
            keys, why = ws.ask_keys(ask, picks)
            assert not why, why
            shown = page.evaluate(
                "([ask, picks]) => askKeys(ask, picks.map("
                "(one) => one.map((n) => n - 1))).flat()", [ask, picks])
            assert shown == keys, (asked, picks, shown, keys)


def test_the_question_stays_until_the_daemon_says_it_was_answered(ws, in_pane):
    """Clearing it on the click would take away a question that a missed
    keystroke left standing, and the reader would never know."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with opened((None, base)) as page:
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


SUBMIT = "#asking .asksend .verb"


def test_submit_stays_off_while_its_keys_go_in_and_after(ws, in_pane):
    """The keys go in one at a time, `KEY_GAP` apart. A click on an option in
    that time painted submit back on, and so did a look at another tab; a
    second submit made the pane read 3 1 2 2 Enter Enter. After the keys
    went in, the question stays until its `PostToolUse`, and a second set
    would land on whatever the agent does next."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with opened((None, base)) as page:
        page.wait_for_selector("#asking .askopt")
        page.click(option(1, 3))
        page.click(option(2, 2))
        held = hold(page, "**/answer")
        page.click(SUBMIT)
        wait_until(page, lambda: held)
        page.click(option(1, 1))
        assert page.locator(SUBMIT).is_disabled()
        show_tab(page, "diff")
        show_tab(page, "transcript")
        page.wait_for_selector("#asking .askopt")
        assert page.locator(SUBMIT).is_disabled()
        held[0].continue_()
        wait_until(page, lambda: len(pressed(seen)) >= 3)
        page.wait_for_function(
            "document.querySelector('#asking .asksays').textContent"
            ".startsWith('pressed')")
        page.click(option(1, 2))
        assert page.locator(SUBMIT).is_disabled()
        page.wait_for_timeout(500)        # proving nothing more went in
        assert pressed(seen) == ["3", "2", "Enter"], seen


def test_an_answered_question_stays_answered_after_a_look_at_another(
        ws, in_pane):
    """`state.picked` is one for the whole page. A look at another session
    with a question of its own built it again for that question, and the
    look back built it again with `pressed` off: after a new pick, submit
    was on for a question whose keys had gone in. The answered ids are kept
    apart from the picks, and one is forgotten when its question is gone."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    cwd = daemon.store.sessions["s1"].cwd
    at = time.time()
    ws.append_event(conftest.event("SessionStart", sid="s2", cwd=cwd,
                                   pane="%8", pid=2, ts=at))
    for name in ("PreToolUse", "PermissionRequest"):
        ws.append_event(conftest.event(
            name, sid="s2", cwd=cwd, pane="%8", pid=2, ts=at + 0.1,
            tool_name="AskUserQuestion", tool_input=ASKED,
            **({"tool_use_id": "toolu_q2"} if name == "PreToolUse" else {})))
    daemon.store.refresh()
    with opened((None, base)) as page:
        page.wait_for_function("state.sessions.length === 2")
        page.evaluate("choose('s1')")
        page.wait_for_function(
            "document.getElementById('asking').dataset.ask"
            " === 's1\\ntoolu_q1'")
        page.click(option(1, 3))
        page.click(option(2, 2))
        page.click(SUBMIT)
        wait_until(page, lambda: len(pressed(seen)) >= 3)
        page.wait_for_function(
            "document.querySelector('#asking .asksays').textContent"
            ".startsWith('pressed')")
        for sid, ask in (("s2", "toolu_q2"), ("s1", "toolu_q1")):
            page.evaluate(f"choose('{sid}')")
            page.wait_for_function(
                "document.getElementById('asking').dataset.ask"
                f" === '{sid}\\n{ask}'")
        page.click(option(1, 1))
        page.click(option(2, 1))
        assert page.locator(SUBMIT).is_disabled()
        assert page.inner_text("#asking .asksays").startswith("pressed")

        ws.append_event(conftest.event(
            "PostToolUse", cwd=cwd, pane="%7", pid=1, ts=time.time(),
            tool_name="AskUserQuestion", tool_input=ASKED,
            tool_use_id="toolu_q1"))
        daemon.tick()
        page.wait_for_function("!state.answered.has('toolu_q1')")
        page.wait_for_timeout(300)        # proving nothing more went in
        assert pressed(seen) == ["3", "2", "Enter"], seen


def test_submit_waits_for_a_message_on_its_way_and_comes_back(ws, in_pane):
    """A message from the send box landing between the answer's keys is
    typed into the dialog, so submit is held while one is on its way -- and
    painted back on when it has landed, although nothing else is pushed: an
    agent waiting on a question sends no events."""
    daemon, base, seen = in_pane
    now_asking(ws, daemon)
    with opened((None, base)) as page:
        page.wait_for_selector("#asking .askopt")
        page.click(option(1, 1))
        page.click(option(2, 1))
        assert not page.locator(SUBMIT).is_disabled()
        held = hold(page, "**/send")
        page.fill("#say", "one more thing")
        page.press("#say", "Enter")
        wait_until(page, lambda: held)
        assert page.locator(SUBMIT).is_disabled()
        assert page.inner_text("#asking .asksays") == \
            "waiting for what is on its way to this session"
        held[0].continue_()
        page.wait_for_function(
            f"!document.querySelector('{SUBMIT}').disabled")
        assert page.inner_text("#asking .asksays") == \
            "presses 1, then 1, then Enter"


def test_a_question_with_no_id_does_not_stop_the_page(ws, in_pane):
    """A `PreToolUse` with no `tool_use_id` makes an ask whose id is "",
    which matched the empty picks the page starts with: `paintPicks` read
    a pick list that was not there, threw, and took `drawHeader` with it --
    no jump, no send box. No real payload without the id has been seen;
    the page must not depend on that."""
    daemon, base, seen = in_pane
    ws.append_event({"session_id": "s1", "hook_event_name": "PreToolUse",
                     "tool_name": "AskUserQuestion", "tool_input": ASKED,
                     "ts": time.time()})
    daemon.store.refresh()
    with opened((None, base)) as page:
        page.wait_for_selector("#asking .askopt")
        # Drawn once, and nothing pushed since: the agent is waiting.
        assert page.locator("#jump").is_visible()
        assert page.locator("#sendbar").is_visible()
        blew_up = []
        page.on("pageerror", lambda error: blew_up.append(str(error)))
        page.click(option(1, 2))
        page.wait_for_timeout(300)      # proving nothing threw
        assert not blew_up, blew_up
        assert page.locator(option(1, 2)).evaluate(
            "one => one.classList.contains('chosen')")


def test_a_session_with_no_question_shows_no_bar(ws, in_pane):
    """It is not the header bar that was taken away. It stands for one thing
    only, and it costs nothing the rest of the time."""
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
        assert page.locator("#asking:not([hidden])").count() == 0
        assert page.locator("#asking .askopt").count() == 0


def test_the_send_box_types_into_the_terminal(in_pane):
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
        page.fill("#say", "run the tests")
        page.press("#say", "Enter")
        # The keys reaching the pane and the send's lock let go, not a
        # number of seconds: a loaded runner takes longer than any.
        wait_until(page, lambda: "run the tests" in conftest.typed(seen))
        page.wait_for_function("sending.size === 0")
        assert conftest.entered(seen) == 1
        # empty, and not put back: the daemon said it went in
        assert page.input_value("#say") == ""


#: An Enter that ends an IME composition, in Chromium's shape
#: (`isComposing`) and in Safari's (`keyCode` 229 once it has ended).
COMPOSED_ENTER = """([box, how]) => {
  const press = new KeyboardEvent('keydown', {key: 'Enter', bubbles: true,
    cancelable: true, isComposing: how === 'composing'});
  if (how === 'safari') Object.defineProperty(press, 'keyCode', {value: 229});
  document.querySelector(box).dispatchEvent(press);
}"""


def test_the_enter_that_ends_a_composition_sends_nothing(in_pane):
    """The Enter that picks a word in an input method is the input
    method's. Taken as the reader's, it sent half a message into the
    terminal."""
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
        page.fill("#say", "\u65e5\u672c")
        for how in ("composing", "safari"):
            page.evaluate(COMPOSED_ENTER, ["#say", how])
        # The box empties the moment a send starts, in the same call as
        # the Enter, so a box still full is the sure sign nothing went.
        assert page.input_value("#say") == "\u65e5\u672c"
        page.wait_for_timeout(500)          # proving nothing was sent
        assert not conftest.into_pane(seen), seen
        page.press("#say", "Enter")
        # Not the box emptying: that is the send starting, not landing.
        # The keys reaching the pane, and the send's lock let go, are.
        wait_until(page, lambda: "\u65e5\u672c" in conftest.typed(seen))
        page.wait_for_function("sending.size === 0")
        assert conftest.entered(seen) == 1
        assert page.input_value("#say") == ""


def test_a_restarted_daemon_says_so_and_keeps_saying_it(ws, in_pane):
    """Restarting `serve` gives the daemon a new token, and an open page
    keeps the one printed into it. The stream is a GET and reconnects, so
    the sidebar goes on moving and the page looks alive while every send is
    refused -- in every session, because the token belongs to the daemon.

    It used to flash "that did not come from this page" for four seconds and
    then read "live" again, over a page where nothing worked.
    """
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
        page.fill("#say", "before the restart")
        page.press("#say", "Enter")
        # The box empties as the text goes, so an empty box is not the
        # answer. The keys reaching the pane, and the send's lock let
        # go, are.
        deadline = time.time() + 15
        while not conftest.typed(seen) and time.time() < deadline:
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


def test_our_own_word_about_what_happened_still_fades(ws, in_pane):
    """"Review sent" is news, and news goes stale. Only a thing you asked
    for and did not get stays."""
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
        said = page.evaluate("""async () => {
          note("review sent");
          return document.getElementById('live').textContent;
        }""")
        assert said == "review sent"
        page.wait_for_function(
            "document.getElementById('live').textContent !== 'review sent'",
            timeout=8000)


def test_the_send_box_keeps_the_text_when_it_did_not_go_in(ws, in_pane,
                                                           monkeypatch):
    """They typed it at a terminal they cannot see. Losing it is not on."""
    daemon, base, seen = in_pane
    monkeypatch.setattr(ws, "run", lambda args, **rest: None)
    with opened((None, base)) as page:
        page.fill("#say", "please work")
        page.press("#say", "Enter")
        page.wait_for_timeout(500)
        assert page.input_value("#say") == "please work"


def test_the_verbs_are_not_there_without_a_pane(no_pane):
    """Nothing to jump to, nothing to type into. Jump is absent, not
    disabled: a button that cannot work is not offered."""
    with opened((None, no_pane[1])) as page:
        page.wait_for_function("state.sessions.length === 1")
        assert page.locator("#sendbar").is_hidden()
        assert page.locator("#jump").is_hidden()


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
    with opened((None, base)) as page:
        page.wait_for_selector("#asking:not([hidden])")
        assert "Which way?" in page.locator("#asking").inner_text()
        page.click("#asking .askopt >> nth=0")     # a complete answer
        page.wait_for_function(
            """() => document.querySelector('#asking .askopt.chosen') !== null""")
        assert page.locator("#asking .asksend .verb").is_disabled()
        assert "not in tmux" in page.locator(".asksays").inner_text()


def test_the_send_box_belongs_to_the_transcript(in_pane):
    with opened((None, base_of(in_pane))) as page:
        assert page.locator("#sendbar").is_visible()
        show_tab(page, "files")
        assert page.locator("#sendbar").is_hidden()
        show_tab(page, "transcript")
        assert page.locator("#sendbar").is_visible()


# --- the send box -----------------------------------------------------------


def test_a_tall_send_box_says_how_much_it_holds(in_pane):
    """A box scrolled to the end of a long log shows its last screenful and
    nothing of how long it is (issue 332). Its lines and bytes stand over
    the send button, once the box is tall enough to leave room there, in
    the sans face and "2.4k" -- the reader said no to "2,400" in a fixed
    face, which took two rows."""
    daemon, base, seen = in_pane
    log = "\n".join(f"06:00 [build] module_{n:04d}.c ok" for n in range(2400))
    with opened((None, base)) as page:
        page.fill("#say", "one line")
        assert page.locator("#saysize").is_hidden()
        # As a paste puts it in: one `input` event. Playwright's `fill` of
        # 60 KB of lines did not end in 60 s; the page's own handler takes
        # 10 ms of it, measured.
        page.evaluate("""(text) => {
          const box = document.getElementById('say');
          box.value = text;
          box.dispatchEvent(new Event('input'));
        }""", log)
        page.wait_for_selector("#saysize:not([hidden])")
        rows = page.locator("#saysize span").all_inner_texts()
        assert rows == ["2.4k lines", f"{round(len(log.encode()) / 1024)} KB"], rows
        out = page.evaluate("""() => {
          const size = document.getElementById('saysize').getBoundingClientRect();
          const box = document.getElementById('say').getBoundingClientRect();
          const send = document.querySelector('#sendbar .sendside .verb')
            .getBoundingClientRect();
          return {clear: size.left >= box.right, above: size.bottom <= send.top,
                  oneRow: size.height < 40, button: send.height,
                  level: Math.abs(send.bottom - box.bottom),
                  face: getComputedStyle(document.getElementById('saysize')).fontFamily};
        }""")
        assert out["clear"] and out["above"] and out["oneRow"], out
        assert out["button"] == 32 and out["level"] <= 1, out
        assert "Mono" not in out["face"], out


def test_the_size_goes_when_the_send_box_empties(in_pane):
    """The box empties the moment a send starts, and its size goes with it:
    a size left standing over an empty box would describe nothing."""
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
        page.fill("#say", "a\nb\nc\nd")
        page.wait_for_selector("#saysize:not([hidden])")
        assert page.locator("#saysize span").first.inner_text() == "4 lines"
        page.press("#say", "Enter")
        page.wait_for_selector("#saysize", state="hidden")


def test_shift_and_enter_writes_a_second_line(in_pane):
    """Enter sends, which is what every chat box does. A prompt with a plan in
    it needs a way to write the second line."""
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
        page.click("#say")
        page.keyboard.type("first line")
        page.keyboard.press("Shift+Enter")
        page.keyboard.type("second line")
        page.wait_for_timeout(300)
        assert page.input_value("#say") == "first line\nsecond line"
        assert seen == [], "shift and enter sent it"

        page.keyboard.press("Enter")
        wait_until(page, lambda: conftest.typed(seen) == [
            "first line\nsecond line"])
        assert page.input_value("#say") == ""


def test_enter_twice_sends_once_and_keeps_what_came_after(in_pane):
    """A second Enter before the daemon answered typed the prompt into the
    pane twice, and the answer then cleared whatever had been typed since,
    which had gone nowhere."""
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
        stub_send(page, delay=3000)
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
            return conftest.typed(seen)

        # Wait for the send to land, then long enough for a second one.
        deadline = time.time() + 15
        while not typed() and time.time() < deadline:
            time.sleep(0.05)
        page.wait_for_timeout(600)
        assert typed() == ["run the tests"], seen


def test_a_refused_send_comes_back_in_front_of_what_was_typed_since(
        ws, in_pane, monkeypatch):
    """The text leaves the box as it goes. When tmux refuses it, it comes
    back, and what was typed while it was on its way stays after it."""
    daemon, base, seen = in_pane
    monkeypatch.setattr(ws, "run", lambda args, **rest: None)
    with opened((None, base)) as page:
        stub_send(page, delay=400)
        page.click("#say")
        page.keyboard.type("please work")
        page.keyboard.press("Enter")
        page.keyboard.type(" and more")
        page.wait_for_function("document.getElementById('say').value"
                               " === 'please work and more'")


def test_enter_on_a_button_reached_by_keyboard_presses_it(in_pane):
    """Enter jumped to the pane from wherever the focus was, so a keyboard
    could press nothing on the page. After a click it still jumps: the click
    leaves the focus on the button, and Enter then is the jump key."""
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
        page.focus(".tab[data-tab='diff']")
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Tab")
        assert page.evaluate(
            "document.activeElement.matches('.tab[data-tab=diff]')")
        page.keyboard.press("Enter")
        page.wait_for_function("state.tab === 'diff'")
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


def test_the_box_grows_with_what_is_in_it_and_shrinks_back(in_pane):
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
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


def test_a_long_line_wraps_rather_than_running_off_the_side(in_pane):
    """A prompt whose start you cannot see is worse than two lines."""
    daemon, base, seen = in_pane
    with opened((None, base)) as page:
        one = page.eval_on_selector("#say", "el => el.clientHeight")
        page.fill("#say", "word " * 120)      # `fill` fires `input` itself
        page.wait_for_timeout(300)
        assert page.eval_on_selector("#say", "el => el.clientHeight") > one
        assert page.eval_on_selector(
            "#say", "el => el.scrollWidth <= el.clientWidth + 1"
        ), "it ran off the side instead of wrapping"


# --- naming a session from the page -------------------------------------------


def test_a_session_can_be_renamed_from_the_page(in_pane):
    """`/rename` in the terminal does not reach here: the name Claude Code
    hands the status line is the one the session started with. A name set here
    is ours and wins."""
    with opened((None, base_of(in_pane))) as page:
        page.dblclick(".row .name")
        page.fill("input.rowname", "the parser")
        page.press("input.rowname", "Enter")
        # The row is where a name is read: there is no second place that
        # says it any more. A name given here leads the row.
        page.wait_for_function(
            "document.querySelector('.row .name').textContent"
            ".includes('the parser')")


def test_escape_leaves_the_name_as_it_was(in_pane):
    with opened((None, base_of(in_pane))) as page:
        was = page.locator(".row .name").inner_text()
        page.dblclick(".row .name")
        page.fill("input.rowname", "not this")
        page.press("input.rowname", "Escape")
        page.wait_for_timeout(300)      # proving it did not go
        assert page.locator(".row .name").inner_text() == was


def test_an_empty_name_gives_the_session_its_place_back(in_pane):
    with opened((None, base_of(in_pane))) as page:
        page.dblclick(".row .name")
        page.fill("input.rowname", "for a moment")
        page.press("input.rowname", "Enter")
        page.wait_for_function(
            "document.querySelector('.row .name').textContent"
            ".includes('for a moment')")
        page.dblclick(".row .name")
        page.fill("input.rowname", "")
        page.press("input.rowname", "Enter")
        page.wait_for_function(
            "!document.querySelector('.row .name').textContent"
            ".includes('for a moment')")


# --- a permission request: read whole, declined from here, approved by its hook --

BUILD = ("cmake --build build -j && "
         + " && ".join(f"ctest -R case{n} --output-on-failure" for n in range(12)))


def now_permission(ws, daemon, calls=("toolu_b1",), pane="%7", ask=""):
    """A real dialog's events: its call starting, then the request 90 ms on.
    Two calls reading the same leave the dialog with no call of its own.
    `ask` is the nonce a hook that waits for a Yes writes."""
    at = time.time()
    shown = {"command": BUILD, "description": "Build and test"}
    cwd = daemon.store.sessions["s1"].cwd
    for call in calls:
        ws.append_event(conftest.event("PreToolUse", tool_name="Bash",
                                       tool_input=shown, pane=pane, cwd=cwd,
                                       tool_use_id=call, ts=at))
    extra = {"ask_id": ask} if ask else {}
    ws.append_event(conftest.event("PermissionRequest", tool_name="Bash",
                                   tool_input=shown, pane=pane, cwd=cwd,
                                   ts=at + 0.09, **extra))
    daemon.store.refresh()


def test_a_permission_is_read_whole_and_declined_with_a_reason(
        ws, in_pane, monkeypatch):
    """The row said the request in one clipped line. Here it stands whole,
    field by field. With no hook waiting there is no Yes: that is the
    terminal's, which the first button opens. No presses Escape; the reason is typed once the
    transcript shows the dialog closed, and the bar goes with the daemon's
    own record of the decline."""
    daemon, base, seen = in_pane
    path = daemon.store.sessions["s1"].transcript_path
    with open(path, "a") as handle:
        handle.write(conftest.records(conftest.record("tool", BUILD, tool_id="toolu_b1")))

    def runner(args, **rest):
        seen.append(conftest.said(args, rest))
        if rest.get("stdin") == b"\x1b":
            with open(path, "a") as handle:
                handle.write(conftest.records(conftest.record(
                    "result", "The user doesn't want to proceed", tool_id="toolu_b1")))
        return ""

    monkeypatch.setattr(ws, "run", runner)
    now_permission(ws, daemon)
    with opened((None, base)) as page:
        page.wait_for_selector("#asking:not([hidden]) .permfield")
        assert page.locator("#asking .askwhat").inner_text() == "May it use Bash?"
        fields = page.eval_on_selector_all(
            "#asking .permfield", """els => els.map((one) => [
              one.querySelector('.askprevhead').textContent,
              one.querySelector('.askprevbody').textContent])""")
        assert fields == [["command", BUILD], ["description", "Build and test"]]
        buttons = page.eval_on_selector_all(
            "#asking button", "els => els.map((one) =>"
            " (one.querySelector('.asklabel') || one).textContent)")
        assert buttons == ["No", "open the terminal", "submit"], buttons
        # The reason is No's alone: it shows once No is picked, inside the
        # one edge that goes round No and its box.
        assert page.locator("#asking .permwhy").is_hidden()
        page.click("#asking .permno")
        assert page.locator("#asking .permnogroup.chosen .permwhy").is_visible()
        # A No waits for what the agent should do instead.
        assert page.locator("#asking .permsubmit").is_disabled()
        assert page.inner_text("#asking .permsend .asksays") == \
            "write what it should do instead"
        page.fill("#asking .permwhy", "Use the ninja build instead")
        assert not page.locator("#asking .permsubmit").is_disabled()
        # Submit at the right edge of the bar, after what it does.
        lefts = page.evaluate("""() => ['.permsend .asksays', '.permsubmit'].map((one) =>
          document.querySelector('#asking ' + one).getBoundingClientRect().left)""")
        assert lefts[0] < lefts[1], lefts
        # What the page says, kept: the slot is repainted on every push.
        page.evaluate("""() => { window.words = []; const was = note;
          note = (word) => { window.words.push(word); was(word); }; }""")
        page.click("#asking .permsubmit")
        page.wait_for_function(
            "window.words.includes('declined, and your reason was typed')")
        deadline = time.time() + 15
        while not conftest.typed(seen) and time.time() < deadline:
            time.sleep(0.05)
        keys = conftest.pressed(seen)
        assert keys[0] == "Escape", keys
        assert conftest.typed(seen) == ["Use the ninja build instead"], seen
        daemon.tick()
        page.wait_for_selector("#asking", state="hidden")


def test_yes_shows_while_the_hook_waits_and_goes_to_it(ws, in_pane, monkeypatch):
    """Yes is there only while the dialog's own hook waits for it, and it
    goes to that hook, never into the pane: keys could land on another
    dialog. The hook here is the real `wait_for_yes`, in a thread."""
    daemon, base, seen = in_pane
    monkeypatch.setattr(ws, "APPROVE_WAIT", 30)
    ask = "00aa11bb22cc33dd"
    now_permission(ws, daemon, ask=ask)
    with opened((None, base)) as page:
        page.wait_for_selector("#asking:not([hidden]) .permno")
        assert page.locator("#asking .permyes").is_hidden(), "a Yes nothing waits for"
        took = []
        hook = threading.Thread(target=lambda: took.append(ws.wait_for_yes(ask)),
                                daemon=True)
        hook.start()
        wait_until(page, lambda: ws.hook_waits(ask))
        daemon.tick()                    # the pass that sees the hook wait
        page.wait_for_selector("#asking .permyes:not([hidden])")
        page.evaluate("""() => { window.words = []; const was = note;
          note = (word) => { window.words.push(word); was(word); }; }""")
        # A click picks, and says nothing to the dialog: submit does.
        assert page.locator("#asking .permsubmit").is_disabled()
        page.click("#asking .permyes")
        assert page.locator("#asking .permyes.chosen").count() == 1
        page.click("#asking .permno")
        assert page.locator("#asking .askopt.chosen").count() == 1
        assert page.locator("#asking .permwhy").is_visible()
        page.click("#asking .permyes")
        assert page.locator("#asking .permwhy").is_hidden()
        assert page.inner_text("#asking .permsend .asksays") == "allows this one call, once"
        page.wait_for_timeout(300)        # proving nothing was said yet
        assert hook.is_alive() and not took and seen == []
        page.click("#asking .permsubmit")
        page.wait_for_function("window.words.includes('allowed, once')")
        hook.join(10)
        assert took == [ask]
        assert seen == [], "a Yes pressed keys"
        daemon.tick()
        page.wait_for_selector("#asking", state="hidden")


def test_yes_and_dont_ask_again_is_a_choice_of_its_own(ws, in_pane, monkeypatch):
    """The CLI's "Yes, and don't ask again for: npm test *" is a button too,
    in the colour of yes, and it sends which choice it is. No is in another
    colour, so the two answers read apart."""
    daemon, base, seen = in_pane
    monkeypatch.setattr(ws, "APPROVE_WAIT", 30)
    ask = "00aa11bb22cc33ee"
    cwd = daemon.store.sessions["s1"].cwd
    ws.append_event(conftest.event(
        "PermissionRequest", tool_name="Bash", pane="%7", cwd=cwd, ask_id=ask,
        tool_input={"command": "npm test -- --watch=false"},
        permission_suggestions=[{"type": "addRules", "behavior": "allow",
                                 "destination": "localSettings",
                                 "rules": [{"toolName": "Bash", "ruleContent": "npm test *"}]}]))
    took = []
    hook = threading.Thread(target=lambda: took.append(ws.wait_for_yes(ask)), daemon=True)
    hook.start()
    with opened((None, base)) as page:
        wait_until(page, lambda: ws.hook_waits(ask))
        daemon.tick()
        page.wait_for_selector("#asking .permalways:not([hidden])")
        assert page.inner_text("#asking .permalways .asklabel") == \
            "Yes, and don't ask again for npm test * in this project"
        # The CLI's numbers, counting only the options shown.
        assert page.eval_on_selector_all(
            "#asking .permopts .asknum", "els => els.map((one) => one.textContent)") \
            == ["1", "2", "3"]
        colours = page.evaluate("""() => ['.permyes', '.permalways', '.permno'].map((one) =>
          getComputedStyle(document.querySelector('#asking ' + one + ' .asknum')).color)""")
        assert colours[0] == colours[1] != colours[2], colours
        page.click("#asking .permalways")
        page.click("#asking .permsubmit")
        hook.join(10)
        assert took == [ask + ":0"]
        assert seen == [], "a Yes pressed keys"


def test_a_dialog_with_no_call_of_its_own_takes_no_reason(ws, in_pane):
    """Nothing can prove it closed, so no reason is typed for it -- and a box
    that took one and then dropped it would be worse than none."""
    daemon, base, seen = in_pane
    now_permission(ws, daemon, calls=("toolu_b1", "toolu_b2"))
    with opened((None, base)) as page:
        page.wait_for_selector("#asking:not([hidden]) .permfield")
        page.click("#asking .permno")
        assert page.locator("#asking .permwhy").is_disabled()
        assert not page.locator("#asking .permsubmit").is_disabled()
        says = page.locator("#asking .asksays").inner_text()
        assert "cannot be typed" in says
        # A Yes in the terminal fires no hook: the warning holds here too.
        assert "Escape stops the agent" in says


def test_a_permission_can_be_read_without_tmux_but_not_declined(ws, no_pane):
    daemon, base = no_pane
    now_permission(ws, daemon, pane="")
    with opened((None, base)) as page:
        page.wait_for_selector("#asking:not([hidden]) .permfield")
        assert page.locator("#asking .permno").is_disabled()
        assert page.locator("#asking .permsubmit").is_disabled()
        assert "not in tmux" in page.locator("#asking .asksays").inner_text()
        # Nothing to open: absent, like jump everywhere else.
        buttons = page.eval_on_selector_all(
            "#asking button", "els => els.map((one) =>"
            " (one.querySelector('.asklabel') || one).textContent)")
        assert buttons == ["No", "submit"], buttons


def test_a_reason_half_written_survives_a_look_at_another_tab(ws, in_pane):
    """The bar is built again when the Transcript tab comes back, and the
    question bar's scar is half an answer lost that way."""
    daemon, base, seen = in_pane
    now_permission(ws, daemon)
    with opened((None, base)) as page:
        page.wait_for_selector("#asking:not([hidden]) .permno")
        page.click("#asking .permno")
        page.fill("#asking .permwhy", "Use the ninja build")
        show_tab(page, "diff")
        show_tab(page, "transcript")
        # The pick is kept as the reason is, so the box still shows.
        page.wait_for_selector("#asking:not([hidden]) .permno.chosen")
        assert page.locator("#asking .permwhy").is_visible()
        assert page.input_value("#asking .permwhy") == "Use the ninja build"


def test_a_no_waits_for_a_send_already_on_its_way(ws, in_pane):
    """One thing typed into a session at a time: a send landing between the
    Escape and the proof would be typed into a dialog that may be up. No
    looked like it could be pressed then, and a press did nothing and said
    nothing; now it is off, says why, and comes back when the send lands."""
    daemon, base, seen = in_pane
    now_permission(ws, daemon)
    with opened((None, base)) as page:
        page.wait_for_selector("#asking:not([hidden]) .permno")
        page.click("#asking .permno")
        page.fill("#asking .permwhy", "Use the ninja build")
        page.evaluate("startSending(state.chosen)")
        assert page.locator("#asking .permsubmit").is_disabled()
        assert page.inner_text("#asking .permsend .asksays") == \
            "waiting for what is on its way to this session"
        page.click("#asking .permsubmit", force=True)
        page.wait_for_timeout(500)        # proving nothing was pressed
        assert "Escape" not in conftest.pressed(seen), seen
        page.evaluate("doneSending(state.chosen)")
        assert not page.locator("#asking .permsubmit").is_disabled()
        assert page.inner_text("#asking .permsend .asksays") \
            .startswith("presses Escape")
        # Its own No is on its way too, and does not wait for itself.
        held = hold(page, "**/decline")
        page.click("#asking .permsubmit")
        wait_until(page, lambda: held)
        assert page.locator("#asking .permsubmit").is_disabled()
        assert page.inner_text("#asking .permsend .asksays") \
            .startswith("presses Escape")


def test_the_send_box_is_away_while_a_permission_dialog_is_up(ws, in_pane):
    """The dialog's cursor starts on "1. Yes", so the Enter after a message
    approves, and a message that starts with a digit picks that option. The
    box goes, the dialog's bar says why where it stood, and it comes back
    when the dialog closes."""
    daemon, base, seen = in_pane
    now_permission(ws, daemon)
    with opened((None, base)) as page:
        page.wait_for_selector("#asking:not([hidden]) .permfield")
        assert page.locator("#sendbar").is_hidden()
        assert "send box is back when this dialog closes" in \
            page.locator("#asking .askone").inner_text()
        # A Yes in the terminal: the call runs and reports back.
        ws.append_event(conftest.event(
            "PostToolUse", tool_name="Bash", tool_use_id="toolu_b1",
            tool_input={"command": BUILD}, pane="%7",
            cwd=daemon.store.sessions["s1"].cwd, ts=time.time()))
        daemon.tick()
        page.wait_for_selector("#sendbar:not([hidden])", timeout=15000)


def test_the_review_is_not_sent_into_a_permission_dialog(ws, in_pane):
    """The review goes through `send` too, and ends in the same Enter. Its
    button is off while the dialog is up, and says why where it stands."""
    daemon, base, seen = in_pane
    now_permission(ws, daemon)
    with opened((None, base)) as page:
        show_tab(page, "diff")
        page.evaluate("""([one]) => { state.review.comments.push(one);
          keepReview(); }""",
          [{"anchor": "code.py\n1", "quoted": "x", "note": "later"}])
        page.wait_for_selector("#reviewbar:not([hidden]) #sendreview")
        assert page.locator("#sendreview").is_disabled()
        assert "permission dialog" in page.get_attribute(
            "#sendreview", "title")


def test_the_review_is_not_offered_to_a_session_that_is_over(ws, in_pane):
    """Its button checked the pane and the dialog, not whether the session
    had ended, so it offered a send the daemon refuses with "this session
    is over". One test for every control now, `whyNotTyped` (#287)."""
    daemon, base, seen = in_pane
    cwd = daemon.store.sessions["s1"].cwd
    ws.append_event(conftest.event("SessionEnd", reason="prompt_input_exit",
                                   pane="%7", pid=1, cwd=cwd, ts=time.time()))
    daemon.store.refresh()
    assert daemon.store.sessions["s1"].state == "ended"
    with opened((None, base)) as page:
        page.evaluate("choose('s1')")
        show_tab(page, "diff")
        page.evaluate("""([one]) => { state.review.comments.push(one);
          keepReview(); }""",
          [{"anchor": "code.py\n1", "quoted": "x", "note": "too late"}])
        page.wait_for_selector("#reviewbar:not([hidden]) #sendreview")
        assert page.locator("#sendreview").is_disabled()
        assert "over" in page.get_attribute("#sendreview", "title")


def test_a_question_is_not_answered_into_a_permission_dialog(ws, in_pane):
    """One batch of calls can hold a question and a command that asks for
    permission, and the daemon refuses the answer then (#254). The submit
    button offered it anyway, and said "presses 1"."""
    daemon, base, seen = in_pane
    # One batch: the calls start together, so the question is still open
    # when the command's dialog comes up.
    at = time.time()
    cwd = daemon.store.sessions["s1"].cwd
    for one in (conftest.event("PreToolUse", tool_name="AskUserQuestion",
                               tool_input=ASKED, tool_use_id="toolu_q1"),
                conftest.event("PreToolUse", tool_name="Bash",
                               tool_input={"command": BUILD},
                               tool_use_id="toolu_b1"),
                conftest.event("PermissionRequest", tool_name="Bash",
                               tool_input={"command": BUILD})):
        one.update(pane="%7", pid=1, cwd=cwd, ts=at)
        ws.append_event(one)
    daemon.store.refresh()
    held = daemon.store.sessions["s1"]
    assert held.asking and held.dialog
    with opened((None, base)) as page:
        page.wait_for_selector("#asking:not([hidden]) .askopt")
        page.click(option(1, 1))
        page.click(option(2, 1))
        page.wait_for_function(
            "document.querySelectorAll('#asking .askopt.chosen').length === 2")
        assert page.locator(SUBMIT).is_disabled()
        assert "permission dialog" in page.locator(
            "#asking .asksays").inner_text()
    assert seen == []


def test_the_reason_box_shows_its_placeholder_and_what_is_typed_whole(ws, in_pane):
    """The reason for a No is a box one row high. Its placeholder was wider
    than the box at 1,100 px, and wrapped onto a second row that did not
    show: "(optional)" stood cut in half under the first. And a long reason
    wrapped onto rows nobody could see, because the box did not grow as the
    send box does. The placeholder, typed in, needs no second row, and a
    long reason makes the box as tall as it is."""
    daemon, base, seen = in_pane
    path = daemon.store.sessions["s1"].transcript_path
    with open(path, "a") as handle:
        handle.write(conftest.records(conftest.record("tool", BUILD, tool_id="toolu_b1")))
    now_permission(ws, daemon)
    rows = """() => { const box = document.querySelector('#asking .permwhy');
      return [box.clientHeight, box.scrollHeight]; }"""
    with opened((None, base)) as page:
        page.set_viewport_size({"width": 1100, "height": 700})
        page.wait_for_selector("#asking:not([hidden]) .permno")
        page.click("#asking .permno")
        page.evaluate("""() => { const box = document.querySelector('#asking .permwhy');
          box.value = box.placeholder; }""")
        shown, needed = page.evaluate(rows)
        assert needed <= shown, "the placeholder wraps onto a hidden row"

        page.fill("#asking .permwhy", "do not delete the folder; move it to "
                  "the archive and tell me what is in it first")
        shown, needed = page.evaluate(rows)
        assert shown > 40, "a long reason did not grow the box"
        assert needed <= shown, "a long reason wraps onto a hidden row"


def test_ctrl_enter_sends_and_says_no_and_the_buttons_stand_level(ws, in_pane):
    """Ctrl+Enter presses the box's own button: the send box left it out on
    purpose and sent nothing, and the reason for a No had only its button.
    And the send button beside its box is as tall as its first line -- it
    was 26 px beside a box of 32, bottoms aligned, and the tops read as a
    mistake. The reason for a No stands under the answers, with no button
    beside it, so only its Ctrl+Enter is asked of it."""
    daemon, base, seen = in_pane
    # A dialog whose call the page can name, or it offers no reason.
    path = daemon.store.sessions["s1"].transcript_path
    with open(path, "a") as handle:
        handle.write(conftest.records(conftest.record("tool", BUILD, tool_id="toolu_b1")))
    level = """(sel) => { const box = document.querySelector(sel);
      const a = box.getBoundingClientRect();
      const b = box.nextElementSibling.getBoundingClientRect();
      return [Math.abs(a.top - b.top), Math.abs(a.bottom - b.bottom)]; }"""

    def pressed(check):
        deadline = time.time() + 15
        while not check() and time.time() < deadline:
            time.sleep(0.05)
        return check()

    with opened((None, base)) as page:
        page.wait_for_selector("#sendbar:not([hidden])")
        assert max(page.evaluate(level, "#say")) < 1
        page.click("#say")
        page.keyboard.type("hello there")
        page.keyboard.press("Control+Enter")
        assert pressed(lambda: "hello there" in conftest.typed(seen)), seen

        # The dialog after the send: while it is up there is no send
        # box. `now_permission` folds the events itself, so no tick
        # after it has anything new to push; this pushes the rows.
        now_permission(ws, daemon)
        daemon.hub.send("sessions", daemon.sessions_payload())
        page.wait_for_selector("#asking:not([hidden]) .permno")
        page.click("#asking .permno")
        page.fill("#asking .permwhy", "no thanks")
        page.press("#asking .permwhy", "Control+Enter")
        assert pressed(lambda: "Escape" in conftest.pressed(seen)), seen


# --- completing a slash command (#268) ----------------------------------------


def skill(base, name, about):
    """A skill under a `.claude` directory, in the shape `tests/fixtures/commands`
    records."""
    folder = base / "skills" / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {about}\nargument-hint: [number]\n---\n")


def ran(daemon, name):
    """The session's transcript says `/name` was run."""
    path = daemon.store.sessions["s1"].transcript_path
    with open(path, "a") as handle:
        handle.write(conftest.records(conftest.record(
            "you", f"<command-name>/{name}</command-name>"
                   f"<command-message>{name}</command-message>"
                   "<command-args></command-args>")))


SLASH_ROWS = "() => [...document.querySelectorAll('#slash button .name')].map((n) => n.textContent)"


def test_a_slash_offers_the_commands_and_tab_takes_one(ws, in_pane, tmp_path):
    """The list opens on `/` with the most used first, narrows as letters are
    typed, and Tab puts the command in the box with a space after it, ready
    for what it is given. Taking one sends nothing."""
    daemon, base, seen = in_pane
    skill(tmp_path / ".claude", "review-pr", "Review a pull request")
    ran(daemon, "clear")
    with opened((None, base)) as page:
        page.click("#say")
        page.keyboard.type("/")
        page.wait_for_function("!$('slash').hidden")
        assert page.evaluate(SLASH_ROWS) == ["/clear", "/review-pr"]
        page.keyboard.type("rev")
        page.wait_for_function("document.querySelectorAll('#slash button').length === 1")
        assert page.text_content("#slash button .hint") == "[number]"
        assert page.text_content("#slash button .came") == "this project"
        page.keyboard.press("Tab")
        assert page.input_value("#say") == "/review-pr "
        assert page.evaluate("$('slash').hidden")
        assert page.evaluate("document.activeElement.id") == "say"
        assert not conftest.into_pane(seen)
        page.keyboard.type("12")
        page.keyboard.press("Enter")
        wait_until(page, lambda: "/review-pr 12" in conftest.typed(seen))


def test_enter_takes_a_command_and_escape_keeps_the_list_shut(ws, in_pane, tmp_path):
    """Enter on an open list takes the row, it does not send. Escape shuts the
    list and leaves the box focused, and the list stays shut while the same
    word is typed on; a new word opens it again. The arrows move the row."""
    daemon, base, seen = in_pane
    skill(tmp_path / ".claude", "review-pr", "Review a pull request")
    ran(daemon, "clear")
    with opened((None, base)) as page:
        page.click("#say")
        page.keyboard.type("/")
        page.wait_for_function("document.querySelectorAll('#slash button').length === 2")
        page.keyboard.press("ArrowDown")
        assert page.text_content("#slash button.chosen .name") == "/review-pr"
        page.keyboard.press("Enter")
        assert page.input_value("#say") == "/review-pr "
        assert not conftest.into_pane(seen)

        page.fill("#say", "")
        page.keyboard.type("/")
        page.wait_for_function("!$('slash').hidden")
        page.keyboard.press("Escape")
        assert page.evaluate("$('slash').hidden")
        assert page.evaluate("document.activeElement.id") == "say"
        page.keyboard.type("c")
        page.wait_for_timeout(300)          # proving the list did *not* open
        assert page.evaluate("$('slash').hidden")

        page.keyboard.press("Backspace")
        page.keyboard.press("Backspace")
        page.keyboard.type("/c")
        page.wait_for_function("!$('slash').hidden")
        assert page.evaluate(SLASH_ROWS) == ["/clear"]


def test_enter_sends_what_was_typed_unless_a_row_was_chosen(ws, in_pane, tmp_path):
    """Enter takes a row only when the reader chose it: an arrow, or a word
    that starts the name. A scattered match is a guess, and a whole name is
    done: both go to the terminal as typed, with one Enter. And an Escape
    does not outlive the word it shut the list on: after a send, `/` opens
    the list again."""
    daemon, base, seen = in_pane
    skill(tmp_path / ".claude", "review-pr", "Review a pull request")
    ran(daemon, "clear")

    def sent(text):
        wait_until(page, lambda: text in conftest.typed(seen))
        page.wait_for_function("sending.size === 0")

    with opened((None, base)) as page:
        page.click("#say")
        page.keyboard.type("/rp")                 # review-pr, scattered
        page.wait_for_function("!$('slash').hidden")
        page.keyboard.press("Enter")
        sent("/rp")
        page.keyboard.type("/rp")                 # the same, but chosen
        page.wait_for_function("!$('slash').hidden")
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        assert page.input_value("#say") == "/review-pr "
        page.fill("#say", "")
        page.keyboard.type("/clear")              # the whole name
        page.wait_for_function("!$('slash').hidden")
        page.keyboard.press("Enter")
        sent("/clear")

        page.keyboard.type("/")
        page.wait_for_function("!$('slash').hidden")
        page.keyboard.press("Escape")
        page.keyboard.type("x")
        page.keyboard.press("Enter")
        sent("/x")
        page.keyboard.type("/")
        page.wait_for_function("!$('slash').hidden")


def test_an_answer_for_a_box_that_was_left_opens_nothing(ws, in_pane, tmp_path):
    """The list is asked for when `/` is typed. A reader who leaves the box
    before the answer comes has moved on, and the list must not open over
    the transcript with nothing to type into."""
    daemon, base, seen = in_pane
    skill(tmp_path / ".claude", "review-pr", "Review a pull request")
    held = []
    with opened((None, base)) as page:
        page.route("**/commands", lambda route: held.append(route))
        page.click("#say")
        page.keyboard.type("/")
        wait_until(page, lambda: held)
        page.evaluate("$('say').blur()")
        with page.expect_response("**/commands"):
            held[0].continue_()
        page.wait_for_timeout(300)          # proving the list did *not* open
        assert page.evaluate("$('slash').hidden")


def test_the_list_is_asked_for_each_time_it_opens(ws, in_pane, tmp_path):
    """A skill written while the page is open is in the next list: the
    commands are not kept from one opening to the next."""
    daemon, base, seen = in_pane
    skill(tmp_path / ".claude", "review-pr", "Review a pull request")
    with opened((None, base)) as page:
        page.click("#say")
        page.keyboard.type("/")
        page.wait_for_function("document.querySelectorAll('#slash button').length === 1")
        page.keyboard.press("Backspace")
        page.wait_for_function("$('slash').hidden")
        skill(ws.claude_dir(), "notes", "Write today's notes")
        page.keyboard.type("/")
        page.wait_for_function("document.querySelectorAll('#slash button').length === 2")
        assert page.evaluate(SLASH_ROWS) == ["/notes", "/review-pr"]


# --- the model and its effort -------------------------------------------------


def with_model(ws, daemon, model="Opus 5.5", model_id="claude-opus-5-5",
               effort="high"):
    ws.write_status("s1", ws.Status(ts=1.0, model=model, model_id=model_id,
                                    effort=effort, context_pct=10.0))
    daemon.store.refresh()


def test_the_model_says_its_effort_and_a_pick_types_the_command(ws, in_pane):
    """The model and how hard it thinks stand beside the context bar (issue
    337), and a click on them opens a menu that types `/model` or `/effort`
    into the pane through `send` (issue 338). The menu says that Claude Code
    makes the choice the default for new sessions too -- measured on
    2.1.287, a typed one writes its settings file."""
    daemon, base, seen = in_pane
    with_model(ws, daemon)
    with opened((None, base)) as page:
        page.wait_for_selector("#ctxslot .model")
        assert page.locator("#ctxslot .model").inner_text() == "Opus 5.5 · high"
        page.click("#ctxslot .model")
        page.wait_for_selector("#modelpop:not([hidden])")
        assert "default for new sessions" in page.locator("#modelpop").inner_text()
        pressed = page.eval_on_selector_all(
            "#modelpop [aria-pressed='true']", "els => els.map((e) => e.textContent)")
        assert pressed == ["claude-opus-5-5", "high"], pressed
        page.click("#modelpop .models button[data-value='sonnet']")
        page.wait_for_selector("#modelpop", state="hidden")
        wait_until(page, lambda: conftest.typed(seen) == ["/model sonnet"])
        page.wait_for_function("sending.size === 0")
        page.click("#ctxslot .model")
        page.click("#modelpop .efforts button[data-value='max']")
        wait_until(page, lambda: conftest.typed(seen)[-1:] == ["/effort max"])


def test_an_older_model_is_offered_by_its_full_id(ws, in_pane):
    """An alias names the newest of its family; `/model claude-opus-5` gave
    "Opus 5", measured. The full ids the sessions ran are offered, from the
    rows, so nothing is a list kept by hand."""
    daemon, base, seen = in_pane
    with_model(ws, daemon, model="Opus 5", model_id="claude-opus-5")
    ws.append_event(conftest.event("SessionStart", sid="s2", pane="%9", pid=2,
                                   model="claude-sonnet-4-5", ts=time.time()))
    daemon.store.refresh()
    with opened((None, base)) as page:
        page.wait_for_function("state.sessions.length === 2")
        page.evaluate("choose('s1')")       # the newer one has no status line
        page.click("#ctxslot .model")
        used = page.eval_on_selector_all(
            "#modelpop .usedmodels button", "els => els.map((e) => e.textContent)")
        assert used == ["claude-opus-5", "claude-sonnet-4-5"], used
        page.click("#modelpop .usedmodels button[data-value='claude-sonnet-4-5']")
        wait_until(page, lambda: conftest.typed(seen) == ["/model claude-sonnet-4-5"])


def test_a_model_with_no_effort_offers_none(ws, in_pane):
    """Haiku has no effort: the status line says none, so there is nothing
    to show beside the model and nothing to set."""
    daemon, base, seen = in_pane
    with_model(ws, daemon, model="Haiku 4.5", model_id="claude-haiku-4-5",
               effort="")
    with opened((None, base)) as page:
        page.wait_for_selector("#ctxslot .model")
        assert page.locator("#ctxslot .model").inner_text() == "Haiku 4.5"
        page.click("#ctxslot .model")
        page.wait_for_selector("#modelpop:not([hidden])")
        assert page.locator("#modelpop .efforts").count() == 0


def test_the_model_menu_shuts_and_types_nothing_it_cannot(ws, served):
    """Escape and a click elsewhere shut it, as they shut the settings. A
    session outside tmux cannot be typed into, so its menu says why, and
    every choice in it is off."""
    daemon, base = served
    ws.append_event(conftest.event("SessionStart", pane="", pid=1, ts=time.time()))
    ws.write_status("s1", ws.Status(ts=1.0, model="Opus 5.5", effort="high",
                                    context_pct=10.0))
    daemon.store.refresh()
    with opened((None, base)) as page:
        page.wait_for_selector("#ctxslot .model")
        page.click("#ctxslot .model")
        page.wait_for_selector("#modelpop:not([hidden])")
        assert "cannot be changed from here" in page.locator("#modelpop").inner_text()
        assert page.evaluate("[...document.querySelectorAll('#modelpop .choice button')]"
                             ".every((one) => one.disabled)")
        page.keyboard.press("Escape")
        page.wait_for_selector("#modelpop", state="hidden")
        page.click("#ctxslot .model")
        page.wait_for_selector("#modelpop:not([hidden])")
        page.click(".turnbody")
        page.wait_for_selector("#modelpop", state="hidden")


def test_a_session_that_is_over_offers_the_line_that_brings_it_back(ws, page_at):
    """Where the send box stood, the command to bring it back, to read and
    copy (#352). The page runs nothing: the reader does, where they want."""
    import shlex

    daemon, _ = page_at
    home = daemon.store.sessions["s1"].home
    with opened(page_at) as page:
        page.wait_for_selector("#sendbar:not([hidden])")
        assert page.locator("#resumebar").is_hidden()
        ws.append_event(conftest.event("SessionEnd", reason="prompt_input_exit",
                                       pane="%7", pid=1, cwd=home, ts=time.time()))
        daemon.tick()                   # what pushes the change to the page
        page.wait_for_selector("#resumebar:not([hidden]) .resumeline")
        assert page.locator("#sendbar").is_hidden()
        line = page.inner_text("#resumebar .resumeline")
        # The test's transcript is under its own config folder, not
        # `~/.claude`, so the line names it.
        words = shlex.split(line)
        assert words[:3] == ["cd", home, "&&"]
        assert words[3].startswith("CLAUDE_CONFIG_DIR=")
        assert words[4:] == ["claude", "--resume", "s1"]
        page.evaluate("""() => { window.copied = null;
          copyToClipboard = async (text) => { window.copied = text; return true; }; }""")
        page.click("#resumebar button")
        assert page.evaluate("window.copied") == line
        page.wait_for_selector("#resumebar button:text-is('copied')")


def test_a_slash_in_the_middle_of_a_message_completes_too(ws, in_pane, tmp_path):
    """After a space, a `/` opens the list as it does at the start (#368).
    Claude Code names a skill or a command file in a message to the model,
    so those are offered; a built-in works only at the start, so it is not.
    Taking one replaces the word being typed and keeps the rest."""
    daemon, base, seen = in_pane
    skill(tmp_path / ".claude", "review-pr", "Review a pull request")
    ran(daemon, "clear")
    with opened((None, base)) as page:
        page.click("#say")
        page.keyboard.type("please /")
        page.wait_for_function("!$('slash').hidden")
        assert page.evaluate(SLASH_ROWS) == ["/review-pr"]
        page.keyboard.type("rev")
        page.keyboard.press("Tab")
        assert page.input_value("#say") == "please /review-pr "
        page.keyboard.type("12 and then stop")
        # A `/` at the start, before all of it: the built-in is offered
        # there, and taking a row keeps everything after it.
        page.evaluate("""() => { const box = $('say');
          box.setRangeText('/ ', 0, 0, 'end');
          box.setSelectionRange(1, 1);
          box.dispatchEvent(new Event('input')); }""")
        page.wait_for_function("!$('slash').hidden")
        assert page.evaluate(SLASH_ROWS) == ["/clear", "/review-pr"]
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Tab")
        assert page.input_value("#say") == "/review-pr please /review-pr 12 and then stop"
        assert not conftest.into_pane(seen)


def test_a_slash_inside_a_word_opens_nothing(ws, in_pane, tmp_path):
    """`src/main.py` and `and/or` are not commands."""
    daemon, base, _ = in_pane
    skill(tmp_path / ".claude", "review-pr", "Review a pull request")
    with opened((None, base)) as page:
        page.click("#say")
        page.keyboard.type("look at src/")
        page.wait_for_timeout(300)          # proving nothing opens
        assert page.evaluate("$('slash').hidden")



# --- a plan waiting for approval (#372) -------------------------------------


def test_a_plan_is_read_as_markdown_and_the_dialog_points_at_it(ws, in_pane):
    """The plan was one row of JSON in the transcript and its raw source in
    the panel. It is a document now, drawn as Markdown, and the panel says
    what is asked and scrolls to it; it still offers no Yes."""
    import json

    daemon, base, seen = in_pane
    path = daemon.store.sessions["s1"].transcript_path
    with open(path, "a") as handle:
        for line in (conftest.FIXTURES / "plan_transcript.jsonl").read_text().splitlines():
            record = json.loads(line)
            # Up to the call: its rejection has not come yet.
            if record.get("toolUseResult") == "User rejected tool use":
                break
            handle.write(line + "\n")
    cwd = daemon.store.sessions["s1"].cwd
    for at, line in enumerate((conftest.FIXTURES / "plan_events.jsonl").read_text().splitlines()):
        one = json.loads(line)
        one.update(session_id="s1", cwd=cwd, pane="%7", pid=1, ts=time.time() + at / 10)
        one.pop("transcript_path")
        ws.append_event(one)
    daemon.store.refresh()
    with opened((None, base)) as page:
        page.set_viewport_size({"width": 1200, "height": 500})
        page.wait_for_selector(".turn.plan .prose h1")
        assert page.locator(".turn.plan .prose h1").inner_text() == "Fix the race in the cache"
        assert page.locator(".turn.plan .prose table").count() == 1
        assert "#" not in page.locator(".turn.plan .prose").inner_text()
        assert page.locator(".turn.plan .who .self").inner_text() == "plan"
        page.wait_for_selector("#asking:not([hidden]) .askwhat")
        assert page.locator("#asking .askhead").inner_text().lower() == "plan"
        assert page.locator("#asking .permfield").count() == 0
        buttons = page.eval_on_selector_all(
            "#asking button", "els => els.map((one) =>"
            " (one.querySelector('.asklabel') || one).textContent)")
        assert buttons == ["read the plan", "No", "open the terminal", "submit"], buttons
        # Its top away from the top of the pane first -- at the head of the
        # transcript -- so the click is what brings it there.
        top = """() => document.querySelector('.turn.plan').getBoundingClientRect().top
          - document.querySelector('.turnbody').getBoundingClientRect().top"""
        page.evaluate("document.querySelector('.turnbody').scrollTop = 0")
        assert page.evaluate(top) > 100
        page.click("#asking button:text('read the plan')")
        page.wait_for_function(f"({top})() < 30")
