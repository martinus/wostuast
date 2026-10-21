"""Moving between the five tabs.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

import conftest
from browser import (
    skip_without_browser,
    opened,
    DRAWN,
    show_tab,
    wait_for_map,
    stays,
    wait_for_watching,
    write_records,
    own_context,
    load,
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
        stays(page, 200)
        assert page.locator(".tab[data-tab='transcript']").get_attribute(
            "aria-selected") == "true"
        assert page.locator(".turn").count() == turns


def test_a_number_key_picks_a_tab_that_is_built(page_at):
    with opened(page_at) as page:
        page.keyboard.press("2")
        page.wait_for_selector(".filelist.files")       # the Transcript's is .transcript
        assert page.locator(".tab[data-tab='files']").get_attribute(
            "aria-selected") == "true"
        assert page.locator(".filelist").count() == 1
        page.keyboard.press("1")
        page.wait_for_function("document.querySelectorAll('.turn').length >= 2")


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
        stays(page, 400)
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
    with opened(repo_page) as page:
        # The page's own tabs: Commands is a view now, and `DRAWN` still
        # names it for `tests/stage.py` (#411).
        names = page.evaluate("TAB_KEYS")
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
            stays(page, 110)      # quicker than a human, on purpose
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
    names the key. Wide, the numbers are there. Four tabs since #622."""
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
            "Transcript  ·  1", "Files  ·  2", "Review  ·  3", "Summary  ·  4"]
        assert page.evaluate("[...document.querySelectorAll('.tab')].map("
                             "(tab) => getComputedStyle(tab).whiteSpace)") == ["nowrap"] * 4
        # Narrower still, the context bar and the spend step aside, and the
        # names and the buttons at the end still fit.
        assert page.is_visible(".ctxslot .spent")
        page.set_viewport_size({"width": 860, "height": 768})
        page.wait_for_function("getComputedStyle(document.querySelector('.ctxslot .spent')).display === 'none'")
        assert page.evaluate(names) == [1, 1, 1, 1]
        assert page.evaluate(look)[0]["right"] <= 860



# --- folding a column away (#464) ---------------------------------------------

WIDTHS = """() => ({
  sessions: document.querySelector('.sidebar').getBoundingClientRect().width,
  list: document.querySelector('.content.split > .side').getBoundingClientRect().width,
  rows: !!document.querySelector('#rows').getClientRects().length,
  find: !!document.querySelector('#find').getClientRects().length,
  open: document.getElementById('grip').classList.contains('open'),
})"""


def test_each_column_folds_away_and_comes_back(repo_page):
    """On a laptop the session list and the review's list took 615 of 1366
    px (#464). Each folds to a strip that holds only its button, the
    browser keeps it through a reload, and a second click brings it back.
    The chosen row's opening in the grip stands beside its tile, folded."""
    with opened(repo_page, tab="diff") as page:
        page.set_viewport_size({"width": 1366, "height": 768})
        page.wait_for_function("document.getElementById('grip').classList.contains('open')")
        was = page.evaluate(WIDTHS)
        assert was["sessions"] > 200 and was["list"] > 150, was
        pane = page.evaluate("document.querySelector('.content.split > :nth-child(3)').getBoundingClientRect().width")

        page.click("#sessionfold")
        page.click(".side .fold")
        shut = page.evaluate(WIDTHS)
        # The rows stay, as tiles, and the grip opens beside the chosen one.
        assert shut == {"sessions": 34, "list": 34, "rows": True, "find": False,
                        "open": True}, shut
        wider = page.evaluate("document.querySelector('.content.split > :nth-child(3)').getBoundingClientRect().width")
        assert wider > pane + 400, (pane, wider)
        # A folded column's edge drags nothing: a width nobody can see.
        assert page.evaluate("getComputedStyle(document.getElementById('grip')).pointerEvents") == "none"

        page.reload()
        page.wait_for_selector(".side .fold")
        assert page.evaluate(WIDTHS) == shut

        page.click("#sessionfold")
        page.click(".side .fold")
        page.wait_for_function("document.getElementById('grip').classList.contains('open')")
        back = page.evaluate(WIDTHS)
        assert back == was, (was, back)


def test_the_list_column_folds_on_every_split_tab(repo_page):
    """It is one column for the three tabs, as its width is: folded on the
    Review tab, it is folded on the Files tab and the Transcript tab, whose
    list `split` builds again on every switch."""
    with opened(repo_page, tab="diff") as page:
        page.click(".side .fold")
        for tab in ("files", "transcript"):
            show_tab(page, tab)
            page.wait_for_function(
                "(tab) => document.getElementById('content').dataset.tab === tab", arg=tab)
            assert page.evaluate(WIDTHS)["list"] == 34, tab
            assert page.get_attribute(".side .fold", "aria-expanded") == "false"


def test_a_key_into_a_folded_column_brings_it_back(repo_page):
    """`f` and `/` put the cursor into a column's find box, and nothing can
    be focused in a column that is not drawn: the key did nothing."""
    with opened(repo_page, tab="diff") as page:
        page.click("#sessionfold")
        page.click(".side .fold")
        page.evaluate("document.activeElement.blur()")
        page.keyboard.press("f")
        page.wait_for_function("document.activeElement.id === 'pick'")
        assert page.evaluate(WIDTHS)["sessions"] > 200
        page.keyboard.press("Escape")
        page.evaluate("document.activeElement.blur()")
        page.keyboard.press("/")
        page.wait_for_function("document.activeElement.id === 'find'")
        assert page.evaluate(WIDTHS)["list"] > 150


TILES = """() => [...document.querySelectorAll('#rows .row')]
  .filter((row) => row.getClientRects().length)
  .map((row) => { const box = row.getBoundingClientRect();
    return {id: row.dataset.id, says: getComputedStyle(row, '::before').content,
            title: row.title, chosen: row.classList.contains('chosen'),
            width: Math.round(box.width), height: Math.round(box.height),
            lines: [...row.children].filter((one) => one.getClientRects().length).length}; })"""


def test_a_folded_session_list_is_a_tile_for_each_session(ws, pair_at, tmp_path):
    """Folded, the session list was a strip with one button, and the reader
    could not see who needs them or go to another session without opening
    it again. Each row is a tile now: the first letters of its name, its
    state's colour, the whole row in a card on the hover (#491), and a
    click chooses it. They are the rows themselves, so a push fills them as
    it fills a row."""
    with opened(pair_at) as page:
        page.wait_for_function("document.querySelectorAll('#rows .row').length === 2")
        page.click("#sessionfold")
        tiles = page.evaluate(TILES)
        assert len(tiles) == 2, tiles
        for one in tiles:
            assert one["height"] == 76 and one["lines"] == 0, one
            assert one["says"] not in ("none", "normal", '""'), one
            assert not one["title"], one          # the card says it now
        chosen = [one for one in tiles if one["chosen"]]
        other = [one for one in tiles if not one["chosen"]][0]
        assert len(chosen) == 1 and chosen[0]["width"] > other["width"], tiles
        # The name runs up the tile, turned, and the hover shows the row
        # whole in the tile's own place: one tab opened out, not a second
        # one beside it.
        says = {one["id"]: one["says"] for one in tiles}
        assert says["s1"] == '"A session"', says
        page.hover('#rows .row[data-id="s1"]')
        page.wait_for_selector("#tilecard:not([hidden]) .row .name")
        card = page.evaluate("""() => {
          const card = document.getElementById('tilecard').getBoundingClientRect();
          const tile = document.querySelector('#rows .row[data-id="s1"]').getBoundingClientRect();
          const strip = document.querySelector('.sidebar').getBoundingClientRect();
          return {name: document.querySelector('#tilecard .row .name').textContent,
                  lines: document.querySelectorAll('#tilecard .row > [class^="line"]').length,
                  top: Math.round(card.top - tile.top),
                  left: Math.round(document.querySelector('#tilecard .row')
                                   .getBoundingClientRect().left - tile.left),
                  wide: card.width >= 300};
        }""")
        assert card == {"name": "A session", "lines": card["lines"], "top": 0,
                        "left": 0, "wide": True} and card["lines"] >= 2, card
        page.mouse.move(700, 500)
        page.wait_for_selector("#tilecard", state="hidden")
        turned = page.evaluate("""() => { const css = getComputedStyle(
            document.querySelector('#rows .row'), '::before');
          return [css.writingMode, css.textOverflow, css.maskImage.includes('gradient')]; }""")
        # Turned, and a long name fades at its end rather than "…".
        assert turned == ["vertical-rl", "clip", True], turned
        page.click(f'#rows .row[data-id="{other["id"]}"]')
        page.wait_for_function("(id) => state.chosen === id", arg=other["id"])
        assert [one["id"] for one in page.evaluate(TILES) if one["chosen"]] == [other["id"]]
        # A session that starts while the list is folded comes as a tile,
        # with its card on the hover.
        daemon = pair_at[0]
        ws.append_event(conftest.event("SessionStart", sid="s3", cwd=str(tmp_path),
                                       pane="%8", pid=3, ts=time.time()))
        daemon.tick()
        page.wait_for_function("document.querySelectorAll('#rows .row').length === 3")
        page.hover('#rows .row[data-id="s3"]')
        page.wait_for_selector("#tilecard:not([hidden]) .row[data-id='s3']")
        # Open again, a row is a row: no tile, no title over it, no card.
        page.click("#sessionfold")
        rows = page.evaluate(TILES)
        assert all(one["lines"] >= 2 and not one["title"] for one in rows), rows
        page.hover('#rows .row[data-id="s1"]')
        assert page.locator("#tilecard").is_hidden()



def test_esc_leaves_a_box_and_a_number_then_picks_a_tab(page_at):
    """In a box a number is a letter typed, so `1` `2` `3` did nothing from
    the send box, and the reader asked for another way (#470). Esc leaves
    every box on the bar and the lists -- the send box keeps its text --
    and the number keys work again; the key help says so."""
    with opened(page_at) as page:
        wait_for_map(page)
        for box, tab in (("#say", "files"), ("#find", "diff"), ("#pick", "transcript")):
            page.click(box)
            page.keyboard.type("hello")
            page.keyboard.press("Escape")
            page.keyboard.press(str(["transcript", "files", "diff"].index(tab) + 1))
            page.wait_for_function("(tab) => state.tab === tab", arg=tab)
            assert page.evaluate("document.activeElement === document.body"), box
            if box == "#say":
                assert page.input_value("#say") == "hello"
        assert "1 – 3 work again" in page.text_content("#help")



def test_esc_in_the_find_box_empties_it_and_leaves_it(page_at):
    """On a tab with no list under the box, Escape empties the find, shows
    everything again and leaves the box. The test above reached it only
    when the Files tab's list had not come yet: once it has, the list
    takes Escape, and CI's line check found these lines unrun (#609)."""
    with opened(page_at) as page:
        page.click("#find")
        page.keyboard.type("nothing matches this")
        page.wait_for_function("state.find === 'nothing matches this'")
        page.keyboard.press("Escape")
        page.wait_for_function("state.find === ''")
        assert page.input_value("#find") == ""
        assert page.evaluate("document.activeElement === document.body")


HOLD_FILES = """() => { window.__held = new Promise((done) => { window.__release = done; });
  const real = window.fetch;
  window.fetch = async (url, options) => {
    if (String(url).includes('/files')) await window.__held;
    return real(url, options);
  }; }"""


def test_a_slow_switch_says_it_is_loading_and_a_quick_one_says_nothing(page_at):
    """The last session's or tab's drawing stood in the box until the new
    one was fetched, and over a slow ssh tunnel the reader took it for the
    switch done, until it changed under their eyes. A switch not drawn
    within `SWITCH_SHOWN` dims what stands there and says what is coming;
    one quicker shows nothing, or every switch would flicker."""
    with opened(page_at) as page:
        wait_for_map(page)
        page.evaluate(HOLD_FILES)
        # Not at once, and not within half of `SWITCH_SHOWN` either: a quick
        # switch draws in that time and must never have flickered.
        early = page.evaluate("""async () => { showTab('files');
          const now = document.body.classList.contains('switching');
          await new Promise((done) => setTimeout(done, 60));
          return [now, document.body.classList.contains('switching')]; }""")
        assert early == [False, False], early
        page.wait_for_function("document.body.classList.contains('switching')")
        page.wait_for_function("!document.getAnimations().length")   # the fade ends
        seen = page.evaluate("""() => ({
          says: getComputedStyle(document.getElementById('content'), '::after').content,
          dim: getComputedStyle(document.querySelector('#content > *')).opacity,
          click: getComputedStyle(document.querySelector('#content > *')).pointerEvents })""")
        assert seen["says"] == '"loading A session  ·  Files…"', seen
        assert float(seen["dim"]) < 0.5 and seen["click"] == "none", seen
        page.evaluate("window.__release()")
        page.wait_for_function("!document.body.classList.contains('switching')")
        page.wait_for_function("document.getElementById('content').dataset.tab === 'files'")


def test_a_session_gone_back_to_is_drawn_from_what_the_page_kept(pair_at):
    """Over a slow ssh tunnel every return to a session fetched its whole
    transcript again: 869 KB for 704 blocks, measured. The page keeps the
    last sessions' transcripts (`keepTurns`), draws a kept one at once, and
    asks the daemon only whether it moved -- `have`, answered `same`."""
    with opened(pair_at) as page:
        page.wait_for_function("document.querySelectorAll('#rows .row').length === 2")
        first, other = "s1", "s2"            # s2 has no transcript at all
        page.evaluate("(id) => choose(id)", first)
        page.wait_for_function("(id) => document.querySelector('.turnbody') && "
                               "document.querySelector('.turnbody').dataset.session === id", arg=first)
        # Only a whole reading is kept, and the stream's opening may ask for
        # the transcript again just after the first fetch: wait for it.
        page.wait_for_function("state.turns.whole && state.turns.landed && !state.turns.early")
        page.evaluate("(id) => choose(id)", other)
        page.wait_for_function("(id) => state.heldTurns.has(id)", arg=first)
        page.wait_for_function("(id) => state.chosen === id && state.turns.landed", arg=other)
        # Never another session's transcript under this one's name.
        assert page.evaluate("state.turns.blocks.length") == 0
        page.evaluate("""() => { window.__asked = []; window.__held = new Promise((done) => { window.__release = done; });
          const real = window.fetch;
          window.fetch = async (url, options) => {
            if (String(url).includes('/transcript')) { window.__asked.push(String(url)); await window.__held; }
            return real(url, options);
          }; }""")
        page.evaluate("""() => { window.__draws = 0; const real = TABS.transcript.draw;
          TABS.transcript.draw = (box) => { window.__draws += 1; return real(box); }; }""")
        drawn = page.evaluate("""(id) => { choose(id);
          const pane = document.querySelector('.turnbody');
          return [pane.dataset.session, pane.querySelectorAll('.turn').length]; }""", first)
        assert drawn[0] == first and drawn[1] >= 2, drawn
        asked = page.evaluate("window.__asked")
        assert len(asked) == 1 and "have=" in asked[0], asked
        page.evaluate("window.__release()")
        page.wait_for_function("state.turns.landed")
        assert page.evaluate("state.turns.blocks.length") >= 2
        # The answer was `same`: drawn once, from what was kept, and not
        # built again -- 70 to 90 ms for seven hundred blocks, measured.
        assert page.evaluate("window.__draws") == 1


def test_the_page_keeps_the_last_transcripts_and_no_more(page_at):
    """Eight, the newest: each is up to a megabyte, and a page stays open
    for days."""
    with opened(page_at) as page:
        wait_for_map(page)
        kept = page.evaluate("""() => {
          const ids = Array.from({length: 12}, (_, at) => 'x' + at);
          state.sessions = state.sessions.concat(ids.map((id) => Object.freeze({id})));
          for (const id of ids) {
            state.turns = Object.assign(blankTurns(), {whole: true, blocks: [{seq: 0}]});
            keepTurns(id);
          }
          return [...state.heldTurns.keys()]; }""")
        assert kept == ["x" + str(at) for at in range(4, 12)], kept


def test_the_transcript_stands_beside_the_review_and_follows_the_agent(page_at):
    """The reader chats with an agent while reading its review (#625): `t`
    puts the transcript in a column on the right, with the send box under
    it, as the reader chose from pictures. It is the live transcript, `t`
    puts it away, and this browser keeps the choice. The session list stays
    as the reader left it (#641)."""
    daemon, path = page_at
    with opened(path) as page:
        wait_for_map(page)
        wait_for_watching(daemon)
        turns = page.evaluate("document.querySelectorAll('#content .turnbody > .turn').length")
        assert turns >= 2
        page.keyboard.press("t")
        page.wait_for_function("document.body.classList.contains('sidechat')")
        assert page.evaluate("state.tab") == "diff"
        page.wait_for_function(
            f"document.querySelectorAll('#chat .turnbody > .turn').length === {turns}")
        place = page.evaluate("""() => {
          const at = (id) => document.getElementById(id).getBoundingClientRect();
          return {chatLeft: Math.round(at('chat').left),
                  contentRight: Math.round(at('content').right),
                  send: document.getElementById('sendbar').parentNode.id,
                  sendShown: !document.getElementById('sendbar').hidden,
                  folded: document.body.classList.contains('foldsessions'),
                  pressed: document.getElementById('chatbtn').getAttribute('aria-pressed')};
        }""")
        assert place["chatLeft"] >= place["contentRight"] - 1, place
        assert place["send"] == "chat" and place["sendShown"], place
        assert not place["folded"] and place["pressed"] == "true", place
        # A push lands in the column, as it lands in the tab.
        write_records(daemon, conftest.record(
            "claude", "A reply beside the diff.", ts="2026-09-18T15:00:00.000Z"))
        daemon.tick()
        page.wait_for_function("""[...document.querySelectorAll('#chat .turnbody > .turn')]
          .some((one) => one.textContent.includes('A reply beside the diff.'))""")
        # Kept by this browser: a page opened later puts it beside a tab
        # again, as `test_the_transcript_is_never_beside_itself` shows. Not
        # by a reload here: what the page ran before one may not count for
        # the page's coverage (topics/testing).
        assert page.evaluate("localStorage.getItem('wostuast-chat')") == "1"
        # `t` puts it away and unfolds the list it folded.
        page.keyboard.press("t")
        page.wait_for_function("!document.body.classList.contains('sidechat')")
        gone = page.evaluate("""() => ({
          chat: document.getElementById('chat').hidden,
          send: document.getElementById('sendbar').parentNode.className,
          folded: document.body.classList.contains('foldsessions'),
          kept: localStorage.getItem('wostuast-chat')})""")
        assert gone == {"chat": True, "send": "main", "folded": False, "kept": None}, gone

def test_the_transcript_is_never_beside_itself(page_at):
    """On the Transcript tab the column would be the tab twice: wanted or
    not, it stands only beside Files and Review."""
    daemon, path = page_at
    with own_context() as context:
        context.add_init_script("localStorage.setItem('wostuast-chat', '1')")
        page = context.new_page()
        load(page, path)
        show_tab(page, "files")
        page.wait_for_function("document.body.classList.contains('sidechat')")
        show_tab(page, "transcript")
        page.wait_for_function("!document.body.classList.contains('sidechat')")
        assert page.evaluate("document.getElementById('sendbar').parentNode.className") == "main"


def test_the_transcript_column_s_head_lines_up_with_the_bars_beside_it(repo_page):
    """The rule under the column's head stood a few pixels above the rule
    under the commit picker beside it (#625). It lines up with the bar of
    the tab beside it, on Review and on Files, whose bars differ."""
    with own_context() as context:
        context.add_init_script("localStorage.setItem('wostuast-chat', '1')")
        page = context.new_page()
        load(page, repo_page)
        for tab, bar in (("diff", ".diffbar"), ("files", ".where")):
            show_tab(page, tab)
            page.wait_for_selector(f"#chat .chathead")
            page.wait_for_selector(f"#content {bar}")
            lines = page.evaluate("""(bar) => {
              const low = (one) => Math.round(document.querySelector(one).getBoundingClientRect().bottom);
              return [low('#chat .chathead'), low('#content ' + bar)];
            }""", bar)
            assert lines[0] == lines[1], (tab, lines)


def test_the_summary_tab_says_where_the_tokens_went(ws, page_at):
    """The fourth tab (#622): what was spent, the costliest turns with
    their share, the calls by tool; a turn is a link to it in the
    transcript. Key 4, as the reader chose; the
    Commands view moved to 5."""
    daemon, path = page_at

    def reply(made, mid, **used):
        made["message"]["id"] = mid
        made["message"]["usage"] = used
        return made

    write_records(daemon,
                  conftest.record("you", "Rename the parser."),
                  reply(conftest.record("tool", "grep -r parse", tool_id="g1"), "m9",
                        input_tokens=40, output_tokens=9000, cache_read_input_tokens=50000),
                  conftest.record("result", "src/parse.py", tool_id="g1"),
                  # Turns after it, so the tab's own landing, at the foot,
                  # shows it nowhere: only the link can.
                  *[conftest.record(*one) for at in range(30) for one in (
                      ("you", f"Next step {at}."), ("claude", "Done.\n\n" * 6))])
    # A subagent that ran, and the lines the status line counts.
    now = time.time()
    for name, at in (("SubagentStart", now), ("PreToolUse", now + 1), ("SubagentStop", now + 2)):
        ws.append_event(conftest.event(name, ts=at, pane="%7", pid=1, agent_id="ag1",
                                       agent_type="Explore", tool_name="Grep",
                                       tool_input={"pattern": "parse"}))
    ws.write_status("s1", ws.Status(ts=1.0, name="A session", model="Opus 5",
                                    cost_usd=1.8342, lines_added=12, lines_removed=3))
    daemon.store.refresh()
    with opened(path) as page:
        wait_for_map(page)
        page.keyboard.press("4")
        page.wait_for_selector(".summary > .sumhead")
        assert page.evaluate("state.tab") == "summary"
        head = page.locator(".sumhead").inner_text()
        assert "$1.83" in head and "spent" in head and "+12 \u22123" in head, head
        lines = page.locator(".sumline.turnlink").all_inner_texts()
        assert "Rename the parser." in lines[0] and "\u2248$" in lines[0], lines
        assert "Bash" in page.locator(".summary").inner_text()
        agents = page.locator(".sumline", has_text="Explore").inner_text()
        assert "\u00d71" in agents and "1 call" in agents, agents
        # No place to pick: that is the Files and Review tabs'.
        assert page.locator("#placepick").is_hidden()
        page.locator(".sumline.turnlink", has_text="Rename the parser.").click()
        page.wait_for_function("state.tab === 'transcript'")
        page.wait_for_function("""() => {
          const box = document.getElementById('content').getBoundingClientRect();
          return [...document.querySelectorAll('#content .turn')].some((one) => {
            const at = one.getBoundingClientRect();
            return one.textContent.includes('Rename the parser.')
              && at.top >= box.top - 1 && at.top < box.bottom;
          });
        }""")
        page.keyboard.press("Escape")
        page.keyboard.press("5")
        page.wait_for_function("state.feed === 'commands'")


def test_a_subagent_s_line_opens_its_own_transcript_read_only(ws, page_at):
    """A subagent's line under its row opens its own transcript in the
    Transcript tab (#618): a bar names it and goes back. Its turns are the
    tab's while it is open, so a call opens as any does -- in its view, not
    the session's -- but they have no buttons, its first prompt is its
    task, and the send box is away, as nothing is sent to a subagent.
    Another tab, or back, is the session's transcript and its send box; a
    view open is closed."""
    daemon, path = page_at
    own = Path(daemon.store.sessions["s1"].transcript_path)
    agent = own.with_suffix("") / "subagents" / "agent-ag1.jsonl"
    agent.parent.mkdir(parents=True)
    agent.write_text(conftest.records(
        conftest.record("you", "look around"),
        conftest.record("tool", "ls -la", tool_id="a1"),
        conftest.record("result", "three files here", tool_id="a1"),
        conftest.record("claude", "Found three files.")))
    now = time.time()
    ws.append_event(conftest.event("SubagentStart", cwd=str(own.parent), pane="%7", pid=1,
                                   ts=now, agent_id="ag1", agent_type="Explore"))
    ws.append_event(conftest.event("SubagentStop", cwd=str(own.parent), pane="%7", pid=1,
                                   ts=now + 1, agent_id="ag1", agent_type="Explore",
                                   agent_transcript_path=str(agent)))
    daemon.store.refresh()
    in_view = "document.querySelector('.agentview .turnbody')?.textContent.includes"
    with opened(path) as page:
        wait_for_map(page)
        wait_for_watching(daemon)
        page.wait_for_selector("#sendbar", state="visible")
        # A call the reader opened in the session's own, kept for the way back.
        page.locator("#content .tool", has_text="pytest").click()
        page.wait_for_function(
            "document.querySelector('#content .turnbody').textContent.includes('all good')")
        page.click(".row[data-id='s1'] .kidsran")
        page.click("#feedlink")                    # a view, which it closes
        page.wait_for_function("state.feed")
        page.click(".row[data-id='s1'] .kid.opens")
        page.wait_for_function(f"{in_view}('Found three files.')")
        assert page.evaluate("state.feed") is False
        page.wait_for_function(
            "document.querySelector('.agenthead').textContent.startsWith('\\u21b3Explore')")
        assert page.locator(".agentview .who .self").first.inner_text() == "task"
        assert page.locator(".agentview .who .self[href]").count() == 0
        assert page.locator("#sendbar").is_hidden()
        assert all(not one.is_visible() for one in page.locator(".agentview .turnacts").all())
        # A call opens in its view, and the session's own turns are untouched.
        page.locator(".agentview .tool", has_text="ls -la").click()
        page.wait_for_function(f"{in_view}('three files here')")
        assert page.evaluate("[...state.agent.held.open]") == [2]
        # What the session says meanwhile is not the subagent's; back is.
        write_records(daemon, conftest.record("claude", "A reply while you were away."))
        daemon.tick()
        stays(page, 600)
        assert "while you were away" not in page.locator("#content").inner_text()
        # Another tab leaves it, as "back" does.
        page.keyboard.press("2")
        page.keyboard.press("1")
        page.wait_for_function(
            "document.querySelector('#content .turnbody')?.textContent.includes('Do the thing.')")
        page.click(".row[data-id='s1'] .kid.opens")
        page.wait_for_selector(".agenthead")
        page.click(".agentback")
        page.wait_for_function(
            "document.querySelector('#content .turnbody')?.textContent.includes("
            "'A reply while you were away.') && !document.querySelector('.agenthead')")
        page.wait_for_selector("#sendbar", state="visible")
        # Its second line: the first stands on the call's line when shut.
        assert "all good" in page.locator("#content .turnbody").inner_text(), "the call shut"
        # A link to a turn of the session leaves a subagent open, too.
        page.click(".row[data-id='s1'] .kid.opens")
        page.wait_for_selector(".agenthead")
        page.evaluate("() => { location.hash = blockHref(0); }")
        page.wait_for_function(
            "!document.querySelector('.agenthead')"
            " && document.querySelector('#content .turnbody')?.textContent.includes('Do the thing.')")


def test_a_running_subagent_s_transcript_follows_it(ws, page_at):
    """A subagent that still runs has no `SubagentStop` to name its
    transcript: the page reads the one beside the session's (measured on
    2.1.306), and again while it runs, so what it does next shows (#618)."""
    daemon, path = page_at
    own = Path(daemon.store.sessions["s1"].transcript_path)
    agent = own.with_suffix("") / "subagents" / "agent-ag2.jsonl"
    agent.parent.mkdir(parents=True)
    agent.write_text(conftest.records(conftest.record("you", "read the tests")))
    ws.append_event(conftest.event("SubagentStart", cwd=str(own.parent), pane="%7", pid=1,
                                   ts=time.time(), agent_id="ag2", agent_type="Plan"))
    daemon.store.refresh()
    in_view = "document.querySelector('.agentview .turnbody')?.textContent.includes"
    with opened(path) as page:
        wait_for_map(page)
        page.click(".row[data-id='s1'] .kid.running.opens")
        page.wait_for_function(f"{in_view}('read the tests')")
        assert "running" in page.locator(".agenthead").inner_text()
        with agent.open("a") as handle:
            handle.write(conftest.records(conftest.record("claude", "Two tests fail.")))
        page.wait_for_function(f"{in_view}('Two tests fail.')")


def test_the_transcript_column_is_as_wide_as_its_edge_is_dragged(page_at):
    """The transcript beside a tab takes a drag of its left edge (#641), as
    the session column does: left, it grows, and this browser keeps the
    width; a double click forgets it. It never folds the session list."""
    daemon, path = page_at
    with opened(path) as page:
        page.set_viewport_size({"width": 1440, "height": 800})
        wait_for_map(page)
        page.keyboard.press("t")
        page.wait_for_function("document.body.classList.contains('sidechat')")
        width = "() => Math.round(document.getElementById('chat').getBoundingClientRect().width)"
        before = page.evaluate(width)
        grip = page.locator("#chat > .chatgrip").bounding_box()
        x, y = grip["x"] + grip["width"] / 2, grip["y"] + 200
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x - 120, y, steps=6)
        page.mouse.up()
        assert abs(page.evaluate(width) - (before + 120)) <= 2, (before, page.evaluate(width))
        assert page.evaluate("localStorage.getItem('wostuast--chat-w')") == str(before + 120)
        assert not page.evaluate("document.body.classList.contains('foldsessions')")
        page.locator("#chat > .chatgrip").dblclick()
        assert abs(page.evaluate(width) - before) <= 2
