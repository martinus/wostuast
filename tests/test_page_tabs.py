"""Moving between the five tabs.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations


import time

import pytest

import conftest
from browser import (
    skip_without_browser,
    sync_playwright,
    DRAWN,
    open_page,
    show_tab,
    wait_for_map,
)

pytestmark = skip_without_browser

def test_a_key_for_a_tab_that_does_not_exist_does_nothing(page_at):
    """A number key picks the tab in that place in `TAB_KEYS`, so a key past
    the last one changes nothing. There are five; there is no `6`."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
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
        finally:
            browser.close()


def test_a_number_key_picks_a_tab_that_is_built(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.keyboard.press("2")
            page.wait_for_timeout(500)
            assert page.locator(".tab[data-tab='files']").get_attribute(
                "aria-selected") == "true"
            assert page.locator(".filelist").count() == 1
            page.keyboard.press("1")
            page.wait_for_timeout(500)
            assert page.locator(".turn").count() >= 2
        finally:
            browser.close()


def test_the_find_box_sits_above_the_list_it_narrows(repo_page):
    """One box, moved to where it is used. Two would be two values to keep in
    step, and `/` would have to guess which one it meant. Every tab with a
    list keeps it in that list's slot; the Session tab has none, so there the
    box goes home."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            for name in ("transcript", "files", "diff"):
                show_tab(page, name)
                assert page.eval_on_selector(
                    "#find", "el => el.parentElement.className") == "findslot", name
                assert page.eval_on_selector(
                    "#find", "el => el.closest('.side') !== null"), name
            # and it goes home when a tab without a list is chosen
            show_tab(page, "session")
            assert page.eval_on_selector(
                "#find", "el => el.parentElement.id") == "findhome"
        finally:
            browser.close()


def test_the_find_box_keeps_focus_while_you_type(repo_page):
    """It is moved only when its parent is wrong. Re-homing it on every draw
    would detach it mid-keystroke and drop the caret."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.click("#find")
            page.keyboard.type("note", delay=60)
            page.wait_for_timeout(400)
            assert page.evaluate("document.activeElement.id") == "find"
            assert page.input_value("#find") == "note"
        finally:
            browser.close()


def test_the_diff_tab_gets_the_box_too(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            assert page.eval_on_selector(
                "#find", "el => el.parentElement.className") == "findslot"
        finally:
            browser.close()


def test_a_tab_comes_back_after_visiting_another(repo_page):
    """The content box says which tab built it, and `split` rebuilds when that
    is another tab. A tab that emptied the box without saying so left the next
    draw believing its columns were still there."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            for name in ("files", "diff"):
                show_tab(page, name)
                assert page.locator(f".filelist.{name} button").count() > 0
                show_tab(page, "session")
                assert page.locator(".filelist").count() == 0
                show_tab(page, name)
                assert page.locator(f".filelist.{name} button").count() > 0, name
                assert page.eval_on_selector(
                    "#find", "el => el.parentElement.className") == "findslot"
        finally:
            browser.close()


def test_every_tab_is_built(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            for name in ("transcript", "files", "diff", "review", "session"):
                assert not page.locator(f".tab[data-tab='{name}']").is_disabled()
        finally:
            browser.close()


def test_every_tab_has_a_number_key_and_it_is_the_one_it_is_drawn_under(page_at):
    """The keys used to be spelled out one `case` each and stopped at four,
    so the fifth tab shipped with no key. Take an entry off the end of
    `TAB_KEYS` and the tab it names stops answering."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            names = page.evaluate("TAB_KEYS")
            drawn = page.eval_on_selector_all(
                ".tab", "els => els.map((one) => one.dataset.tab)")
            assert names == drawn, (names, drawn)
            for at, name in enumerate(names):
                page.keyboard.press(str(at + 1))
                page.wait_for_function(
                    "(name) => $('content').dataset.tab === name", arg=name)
        finally:
            browser.close()


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
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
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
        finally:
            browser.close()


def test_switching_tabs_faster_than_they_load_still_lands(repo_page):
    """Each tab asks the daemon and draws when the answer comes. Clicking
    through them faster than that must still leave the last one drawn."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            blew_up = []
            page.on("pageerror", lambda error: blew_up.append(str(error)))
            for name in ["files", "diff", "review", "transcript", "review",
                         "files", "transcript", "diff", "review", "files"]:
                page.click(f".tab[data-tab='{name}']")
                page.wait_for_timeout(110)      # quicker than a human, on purpose
            page.wait_for_selector(DRAWN["files"], timeout=15000)
            assert page.evaluate("$('content').dataset.tab") == "files"
            assert not blew_up, blew_up
        finally:
            browser.close()


def test_a_transcript_push_during_a_tab_switch_stays_out_of_the_other_tab(
        repo_page):
    """`showTab` sets `state.tab` and then awaits `load()`. During that await
    the box still belongs to the tab before it, and the push's guard read
    `state.tab` — so a turn was appended as a fourth column of the Files tab.

    `draw()` already asks the box which tab owns it. This does too."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
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
        finally:
            browser.close()


def test_a_tab_with_nothing_to_narrow_offers_no_find_box(page_at):
    """The Session tab is about one session and has no list to narrow, and it
    was offering "find a file" — a promise about a tab one over. `finds` in
    `TABS` says what the box is for, or `null`, so a new tab is one entry
    rather than another arm of a ternary that names three tabs and gives the
    rest whatever the last arm said."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            seen = {}
            for tab in ("transcript", "files", "diff", "review", "session"):
                show_tab(page, tab)
                seen[tab] = page.evaluate("""() => {
                  const box = document.getElementById('find');
                  return {shown: !!box.offsetParent, hint: box.placeholder};
                }""")
            assert seen["session"]["shown"] is False, seen
            for tab in ("transcript", "files", "diff", "review"):
                assert seen[tab]["shown"] is True, (tab, seen)
            # And each says what it is for, rather than three of them saying
            # the same thing because a ternary ran out of arms.
            hints = [seen[one]["hint"]
                     for one in ("transcript", "files", "diff", "review")]
            assert len(set(hints)) == 4, hints
        finally:
            browser.close()


def test_the_live_slot_keeps_the_far_end_when_the_find_box_goes(page_at):
    """`margin-left: auto` on the find box is what pushed both it and the
    live slot to the end of the tab bar. With the box gone the slot came to
    rest against the last tab."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            show_tab(page, "session")
            seen = page.evaluate("""() => {
              const bar = document.querySelector('.tabs').getBoundingClientRect();
              const live = document.getElementById('live').getBoundingClientRect();
              const last = [...document.querySelectorAll('.tab')]
                .pop().getBoundingClientRect();
              return {gap: bar.right - live.right, fromTab: live.left - last.right};
            }""")
            assert seen["gap"] < 40, seen         # still at the far end
            assert seen["fromTab"] > 100, seen    # not up against the tabs
        finally:
            browser.close()



# --- how full the window is ---------------------------------------------------


def test_the_context_bar_stands_at_the_end_of_the_tab_row(page_at):
    """It is in the Session tab too, in a panel you have to go to. This is the
    one fact in that panel you want to notice rather than look up, so it is on
    every tab — which is the whole of what #101 asked for that wostuast can
    actually know."""
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_selector("#ctxslot .ctx")
            for tab in ("transcript", "files", "diff", "review", "session"):
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
        finally:
            browser.close()


def test_a_session_whose_status_line_is_quiet_has_no_context_bar(ws, served):
    """`context_pct` is the one number only the status line carries, so a
    session without one has nothing to draw and draws nothing — rather than a
    bar at nought, which would read as an empty window."""
    daemon, base = served
    ws.append_event(conftest.event(
        "SessionStart", pane="%7", pid=1, ts=time.time()))
    daemon.store.refresh()
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            page.wait_for_function("state.sessions.length === 1")
            assert page.evaluate("state.sessions[0].context_pct") is None
            assert page.is_hidden("#ctxslot")
            assert page.evaluate(
                "document.getElementById('ctxslot').innerText") == ""
        finally:
            browser.close()


def test_the_context_bar_does_not_touch_the_live_slot(page_at):
    """`paintLive` is the one writer of that slot and three things already
    want it. A fourth would be the race that rule was written after."""
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_selector("#ctxslot .ctx")
            page.wait_for_function(
                "document.getElementById('live').textContent === 'live'")
            page.evaluate("said({error: 'no pane for this session'})")
            page.wait_for_function(
                """() => document.getElementById('live').innerText
                          .includes('no pane')""")
            # The failure is in the slot, and the bar is still beside it.
            assert "41% ctx" in page.locator("#ctxslot").inner_text()
        finally:
            browser.close()


def test_the_strip_carries_what_this_session_has_spent(page_at):
    """The status line has carried `cost.total_cost_usd` all along. This
    repository said it did not, wrote that into PLAN.md section 12, and closed
    #101 down to one line on the strength of it — see
    `tests/fixtures/README.md`."""
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_selector("#ctxslot .spent")
            for tab in ("transcript", "files", "diff", "review", "session"):
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
        finally:
            browser.close()


def test_a_session_that_was_told_no_cost_shows_none(ws, served):
    """`None` is "the status line did not say" and 0 is "it spent nothing".
    A session on an API key gets no `cost` at all, and $0.00 for it would be a
    number nobody measured."""
    daemon, base = served
    ws.append_event(conftest.event(
        "SessionStart", pane="%7", pid=1, ts=time.time()))
    ws.write_status("s1", ws.Status(ts=1.0, name="A session", context_pct=12.0))
    daemon.store.refresh()
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            page.wait_for_function("state.sessions.length === 1")
            assert page.evaluate("state.sessions[0].cost_usd") is None
            page.wait_for_selector("#ctxslot .ctx")      # context still shows
            assert page.locator("#ctxslot .spent").count() == 0
        finally:
            browser.close()
