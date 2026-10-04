"""Moving between the five tabs.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations


import time

import pytest

import conftest
from browser import (
    skip_without_browser,
    opened,
    DRAWN,
    show_tab,
    wait_for_map,
)

pytestmark = skip_without_browser

def test_a_key_for_a_tab_that_does_not_exist_does_nothing(page_at):
    """A number key picks the tab in that place in `TAB_KEYS`, so a key past
    the last one changes nothing. There are four; there is no `6`."""
    with opened(page_at) as page:
        # Both counts have to be of the same transcript. Taking the first
        # before it had arrived made the second one larger, and the key
        # got the blame for a block the stream had delivered.
        wait_for_map(page)
        turns = page.locator(".turn").count()
        page.keyboard.press("6")
        page.wait_for_timeout(200)
        assert page.locator(".tab[data-tab='transcript']").get_attribute(
            "aria-selected") == "true"
        assert page.locator(".turn").count() == turns


def test_a_number_key_picks_a_tab_that_is_built(page_at):
    with opened(page_at) as page:
        page.keyboard.press("2")
        page.wait_for_timeout(500)
        assert page.locator(".tab[data-tab='files']").get_attribute(
            "aria-selected") == "true"
        assert page.locator(".filelist").count() == 1
        page.keyboard.press("1")
        page.wait_for_timeout(500)
        assert page.locator(".turn").count() >= 2


def test_the_find_box_sits_above_the_list_it_narrows(repo_page):
    """One box, moved to where it is used. Two would be two values to keep in
    step, and `/` would have to guess which one it meant. Every tab has a
    list, and keeps it in that list's slot.

    And each says what it is for: a tab used to offer "find a file" for a
    list it did not have, from a ternary that named three tabs and gave the
    rest whatever its last arm said. `finds` in `TABS` is one entry a tab."""
    with opened(repo_page) as page:
        hints = []
        for name in ("transcript", "files", "diff"):
            show_tab(page, name)
            assert page.eval_on_selector(
                "#find", "el => el.parentElement.className") == "findslot", name
            assert page.eval_on_selector(
                "#find", "el => el.closest('.side') !== null"), name
            hints.append(page.eval_on_selector("#find", "el => el.placeholder"))
        assert len(set(hints)) == 3, hints


def test_the_find_box_keeps_focus_while_you_type(repo_page):
    """It is moved only when its parent is wrong. Re-homing it on every draw
    would detach it mid-keystroke and drop the caret."""
    with opened(repo_page) as page:
        show_tab(page, "files")
        page.click("#find")
        page.keyboard.type("note", delay=60)
        page.wait_for_timeout(400)
        assert page.evaluate("document.activeElement.id") == "find"
        assert page.input_value("#find") == "note"


def test_the_diff_tab_gets_the_box_too(repo_page):
    with opened(repo_page) as page:
        show_tab(page, "diff")
        assert page.eval_on_selector(
            "#find", "el => el.parentElement.className") == "findslot"


def test_a_tab_comes_back_after_visiting_another(repo_page):
    """The content box says which tab built it, and `split` rebuilds when that
    is another tab. A tab that emptied the box without saying so left the next
    draw believing its columns were still there."""
    with opened(repo_page) as page:
        for name in ("files", "diff"):
            show_tab(page, name)
            assert page.locator(f".filelist.{name} button").count() > 0
            show_tab(page, "transcript")
            assert page.locator(f".filelist.{name}").count() == 0
            show_tab(page, name)
            assert page.locator(f".filelist.{name} button").count() > 0, name
            assert page.eval_on_selector(
                "#find", "el => el.parentElement.className") == "findslot"


def test_every_tab_is_built(page_at):
    with opened(page_at) as page:
        for name in ("transcript", "files", "diff"):
            assert not page.locator(f".tab[data-tab='{name}']").is_disabled()


def test_every_tab_has_a_number_key_and_it_is_the_one_it_is_drawn_under(page_at):
    """The keys used to be spelled out one `case` each and stopped at four,
    so the fifth tab shipped with no key. Take an entry off the end of
    `TAB_KEYS` and the tab it names stops answering."""
    with opened(page_at) as page:
        names = page.evaluate("TAB_KEYS")
        drawn = page.eval_on_selector_all(
            ".tab", "els => els.map((one) => one.dataset.tab)")
        assert names == drawn, (names, drawn)
        for at, name in enumerate(names):
            page.keyboard.press(str(at + 1))
            page.wait_for_function(
                "(name) => $('content').dataset.tab === name", arg=name)


# --- moving between tabs ----------------------------------------------------

def test_every_way_from_one_tab_to_another_works(repo_page):
    """There is one find box and it lives inside the content box on a split
    tab. A tab that empties that box without giving it back destroys it, and
    then `showTab` throws on the next `$("find")` — before it reaches `load`,
    so the tab never loads, and every switch after it throws as well. The page
    stayed broken until a reload. The Peek tab did exactly this before it
    was removed, and this test is what it left behind.
    """
    names = list(DRAWN)
    with opened(repo_page) as page:
        blew_up = []
        page.on("pageerror", lambda error: blew_up.append(str(error)))
        for one in names:
            for other in names:
                if one == other:
                    continue
                show_tab(page, one)
                show_tab(page, other)
                assert page.locator(DRAWN[other]).count() > 0, \
                    f"{one} to {other} drew nothing"
                assert not blew_up, blew_up
        # and the find box is still there, still working. On the Files
        # tab that means the list of places opens under it; the tree
        # behind it is not what answers.
        show_tab(page, "files")
        page.fill("#find", "code")
        page.wait_for_selector(".goto button")
        assert page.eval_on_selector_all(
            ".goto button", "els => els.map(e => e.title)") == ["code.py"]
        assert not blew_up, blew_up


def test_switching_tabs_faster_than_they_load_still_lands(repo_page):
    """Each tab asks the daemon and draws when the answer comes. Clicking
    through them faster than that must still leave the last one drawn."""
    with opened(repo_page) as page:
        blew_up = []
        page.on("pageerror", lambda error: blew_up.append(str(error)))
        for name in ["files", "diff", "transcript", "files", "transcript",
                     "diff", "transcript", "diff", "files", "files"]:
            page.click(f".tab[data-tab='{name}']")
            page.wait_for_timeout(110)      # quicker than a human, on purpose
        page.wait_for_selector(DRAWN["files"], timeout=15000)
        assert page.evaluate("$('content').dataset.tab") == "files"
        assert not blew_up, blew_up


def test_a_transcript_push_during_a_tab_switch_stays_out_of_the_other_tab(
        repo_page):
    """`showTab` sets `state.tab` and then awaits `load()`. During that await
    the box still belongs to the tab before it, and the push's guard read
    `state.tab` — so a turn was appended as a fourth column of the Files tab.

    `draw()` already asks the box which tab owns it. This does too."""
    with opened(repo_page) as page:
        show_tab(page, "files")
        page.wait_for_selector(".filebody")
        before = page.evaluate(
            """() => [...document.getElementById('content').children]
                       .map((node) => node.className)""")

        # The exact pair an arriving transcript performs, in the window
        # where the tab has been picked and its body has not been drawn.
        page.evaluate("""() => {
          state.tab = 'transcript';
          patchTranscript([state.turns.blocks.length]);
          state.tab = 'files';
        }""")
        after = page.evaluate(
            """() => [...document.getElementById('content').children]
                       .map((node) => node.className)""")
        assert after == before


# --- how full the window is ---------------------------------------------------


def test_the_model_stands_left_of_the_context_bar(page_at):
    """The percentage is a percentage of this model's window, and `/model`
    changes it mid-session, so the name stands beside the bar it fills."""
    _, path = page_at
    with opened(path) as page:
        page.wait_for_selector("#ctxslot .model")
        seen = page.evaluate("""() => {
          const box = (sel) => document.querySelector(sel)
            .getBoundingClientRect();
          return {text: document.querySelector('#ctxslot .model').textContent,
                  left: box('#ctxslot .model').right <= box('#ctxslot .ctx').left};
        }""")
        assert seen == {"text": "Opus 5", "left": True}, seen


def test_the_context_bar_stands_at_the_end_of_the_tab_row(page_at):
    """It is the one fact about a session you want to notice rather than look
    up, so it is on every tab — which is the whole of what #101 asked for
    that wostuast can actually know."""
    _, path = page_at
    with opened(path) as page:
        page.wait_for_selector("#ctxslot .ctx")
        for tab in ("transcript", "files", "diff"):
            show_tab(page, tab)
            seen = page.evaluate("""() => {
              const slot = document.getElementById('ctxslot');
              const bar = slot.querySelector('.bar .fill');
              const live = document.getElementById('live')
                .getBoundingClientRect();
              return {text: slot.innerText, hidden: slot.hidden,
                      fill: bar && bar.style.width,
                      leftOfLive: slot.getBoundingClientRect().right
                                  <= live.left + 1};
            }""")
            assert seen["hidden"] is False, tab
            assert "41% ctx" in seen["text"], (tab, seen)
            assert seen["fill"] == "41%", (tab, seen)
            assert seen["leftOfLive"], (tab, seen)


def test_a_session_whose_status_line_is_quiet_has_no_context_bar(ws, served):
    """`context_pct` is the one number only the status line carries, so a
    session without one has nothing to draw and draws nothing — rather than a
    bar at nought, which would read as an empty window."""
    daemon, base = served
    ws.append_event(conftest.event(
        "SessionStart", pane="%7", pid=1, ts=time.time()))
    daemon.store.refresh()
    with opened(base + "/") as page:
        page.wait_for_function("state.sessions.length === 1")
        assert page.evaluate("state.sessions[0].context_pct") is None
        assert page.is_hidden("#ctxslot")
        assert page.evaluate(
            "document.getElementById('ctxslot').innerText") == ""


def test_the_context_bar_does_not_touch_the_live_slot(page_at):
    """`paintLive` is the one writer of that slot and three things already
    want it. A fourth would be the race that rule was written after."""
    _, path = page_at
    with opened(path) as page:
        page.wait_for_selector("#ctxslot .ctx")
        page.wait_for_function(
            "state.live === 'live' && document.getElementById('live').textContent === ''")
        page.evaluate("said({error: 'no pane for this session'})")
        page.wait_for_function(
            """() => document.getElementById('live').innerText
                      .includes('no pane')""")
        # The failure is in the slot, and the bar is still beside it.
        assert "41% ctx" in page.locator("#ctxslot").inner_text()


def test_the_strip_carries_what_this_session_has_spent(page_at):
    """The status line has carried `cost.total_cost_usd` all along. This
    repository said it did not, wrote that into its design brief, and closed
    #101 down to one line on the strength of it — see
    `tests/fixtures/README.md`."""
    _, path = page_at
    with opened(path) as page:
        page.wait_for_selector("#ctxslot .spent")
        for tab in ("transcript", "files", "diff"):
            show_tab(page, tab)
            seen = page.evaluate("""() => {
              const slot = document.getElementById('ctxslot');
              const spent = slot.querySelector('.spent');
              return {text: slot.innerText.replace(/\\s+/g, ' '),
                      caveat: spent && spent.title};
            }""")
            assert "41% ctx" in seen["text"], (tab, seen)
            assert "$1.83" in seen["text"], (tab, seen)
            # An estimate at list price. Said on the number, because it is
            # read once and the strip has no width for a sentence.
            assert "estimate" in seen["caveat"], (tab, seen)
            assert "/clear" in seen["caveat"], (tab, seen)


def test_a_session_that_was_told_no_cost_shows_none(ws, served):
    """`None` is "the status line did not say" and 0 is "it spent nothing".
    A session on an API key gets no `cost` at all, and $0.00 for it would be a
    number nobody measured."""
    daemon, base = served
    ws.append_event(conftest.event(
        "SessionStart", pane="%7", pid=1, ts=time.time()))
    ws.write_status("s1", ws.Status(ts=1.0, name="A session", context_pct=12.0))
    daemon.store.refresh()
    with opened(base + "/") as page:
        page.wait_for_function("state.sessions.length === 1")
        assert page.evaluate("state.sessions[0].cost_usd") is None
        page.wait_for_selector("#ctxslot .ctx")      # context still shows
        assert page.locator("#ctxslot .spent").count() == 0


def test_a_key_leaves_no_ring_on_a_tab_that_was_clicked(page_at):
    """A click leaves the focus on its button, and a key pressed after it
    turns `:focus-visible` on: clicking a tab and pressing 1 drew the
    browser's dark ring round the tab just left. A shortcut that
    acts takes the focus off a button the pointer pressed. One reached by
    Tab keeps it, because that is where a keyboard reader is."""
    ringed = """() => [...document.querySelectorAll('.tab')]
      .filter((one) => one.matches(':focus-visible')).map((one) => one.dataset.tab)"""
    with opened(page_at) as page:
        page.click(".tab[data-tab='diff']")
        page.keyboard.press("1")
        page.wait_for_function("state.tab === 'transcript'")
        assert page.evaluate(ringed) == []

        for _ in range(60):             # to a tab, by keyboard
            page.keyboard.press("Tab")
            if page.evaluate("document.activeElement.classList.contains('tab')"):
                break
        reached = page.evaluate("document.activeElement.dataset.tab")
        assert reached, "Tab never reached a tab"
        page.keyboard.press("2")
        page.wait_for_function("state.tab === 'files'")
        assert page.evaluate(ringed) == [reached]


def test_the_tab_names_stay_on_one_line_in_a_narrow_window(page_at):
    """At 1024 px "1 Transcript" broke over two lines (#397). A name never
    wraps; short of room the key's number goes, and the tab's title still
    names the key. Wide, the numbers are there."""
    with opened(page_at) as page:
        look = """() => [...document.querySelectorAll('.tab')].map((tab) => ({
          lines: Math.round(tab.getBoundingClientRect().height),
          key: getComputedStyle(tab.querySelector('.tabkey')).display,
          right: Math.round(document.querySelector('#settings').getBoundingClientRect().right),
          title: tab.title}))"""
        page.set_viewport_size({"width": 1440, "height": 800})
        wide = page.evaluate(look)
        assert all(one["key"] != "none" for one in wide), wide
        page.set_viewport_size({"width": 1024, "height": 768})
        page.wait_for_function("getComputedStyle(document.querySelector('.tabkey')).display === 'none'")
        narrow = page.evaluate(look)
        # One line: every tab as tall as the row, none taller.
        assert len({one["lines"] for one in narrow}) == 1, narrow
        # Each name is one box of text: two would be a name on two lines.
        names = """[...document.querySelectorAll('.tab')].map((tab) => {
          const text = [...tab.childNodes].find((n) => n.nodeType === 3 && n.textContent.trim());
          const range = document.createRange(); range.selectNodeContents(text);
          return range.getClientRects().length; })"""
        assert page.evaluate(names) == [1, 1, 1, 1]
        # The settings button is still on screen, at the row's right.
        assert narrow[0]["right"] <= 1024, narrow
        assert [one["title"] for one in narrow] == [
            "Transcript  ·  1", "Files  ·  2", "Review  ·  3", "Commands  ·  4"]
        assert page.evaluate("[...document.querySelectorAll('.tab')].map("
                             "(tab) => getComputedStyle(tab).whiteSpace)") == ["nowrap"] * 4
        # Narrower still, the context bar and the spend step aside, and the
        # names and the buttons at the end still fit.
        assert page.is_visible(".ctxslot .spent")
        page.set_viewport_size({"width": 860, "height": 768})
        page.wait_for_function("getComputedStyle(document.querySelector('.ctxslot .spent')).display === 'none'")
        assert page.evaluate(names) == [1, 1, 1, 1]
        assert page.evaluate(look)[0]["right"] <= 860

