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
    show_tab,
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
            assert "done" in page.evaluate("window.__dot.className")
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
    """How full a context window is reads at a glance and does not at a
    count. It lives in the Session tab, which is where everything the chosen
    row does not already say now lives."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            show_tab(page, "session")
            page.wait_for_selector(".sessionbody .ctx .bar")
            assert page.locator(".ctx .bar").count() == 1
            width = page.evaluate("document.querySelector('.ctx .fill').style.width")
            assert width == "41%"
            assert "41% ctx" in page.locator(".sessionbody").inner_text()
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


def test_the_history_bar_goes_when_the_filter_leaves_nothing_to_fold(past_at):
    """The bar is made once and kept between draws, so a draw with nothing
    under it has to take it away. `barPlaced` started as `!past.length`, which
    is true in exactly the case that needs the removal — so the bar stayed,
    over nothing, still clickable, saying how many sessions it was not
    holding."""
    with sync_playwright() as play:
        browser, page = open_page(play, past_at)
        try:
            page.wait_for_selector(".histhead")
            page.fill("#pick", "session")       # what the live one is called
            page.wait_for_function(
                "document.querySelectorAll('.histhead').length === 0")
            page.press("#pick", "Escape")
            page.wait_for_selector(".histhead")  # and it comes back
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
            # The bar stands above the rows it opened, and below the live
            # ones. Not at a fixed index: each group of live rows has a head
            # of its own now.
            assert page.evaluate("""() => {
              const kids = [...document.getElementById("rows").children];
              const bar = kids.findIndex((n) => n.classList.contains("histhead"));
              const gone = kids.findIndex((n) => n.classList.contains("ended"));
              const live = kids.findIndex(
                (n) => n.classList.contains("row") && !n.classList.contains("ended"));
              return live < bar && bar < gone;
            }""")

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


def test_the_chosen_row_is_tinted_all_the_way_down(page_at):
    """It was an inset shadow with a 40 px spread, which fills inward from each
    edge and leaves a stripe of untinted row down the middle of anything taller
    than 80 px. A row carrying a name, a branch and a reason is taller than
    that, so the selected session had a brighter band through its centre.

    A fill must not depend on how tall the row turns out to be.
    """
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            row = page.locator(".row.chosen")
            assert row.count() == 1
            seen = page.evaluate("""() => {
              const node = document.querySelector(".row.chosen");
              const style = getComputedStyle(node);
              return {shadow: style.boxShadow,
                      image: style.backgroundImage,
                      height: node.getBoundingClientRect().height};
            }""")
            assert seen["shadow"] == "none", "a shadow cannot fill an unknown height"
            assert "gradient" in seen["image"], "the chosen row has lost its tint"
            # And the row really is taller than the old spread covered.
            assert seen["height"] > 40
        finally:
            browser.close()


def test_the_session_filter_forgives_nothing(past_at):
    """The file matcher forgives one missing letter, because a file name is
    long and one wrong character should not hide it. The session haystack is a
    short line of text, and forgiving a letter there matched half the list —
    "acorn" found a session whose worktree merely contained a, c, o and r."""
    with sync_playwright() as play:
        browser, page = open_page(play, past_at)
        try:
            page.wait_for_selector(".histhead")
            strict = page.evaluate("""() => ({
              exact: !!fuzzy("repo/acorn", "acorn"),
              oneLetterShort: !!fuzzy("repo/acor", "acorn"),
              scattered: !!fuzzy("repo/a-c-o-r", "acorn"),
            })""")
            assert strict == {"exact": True, "oneLetterShort": False,
                              "scattered": False}
        finally:
            browser.close()


# --- the four groups ----------------------------------------------------------


def bands(page):
    """The section heads on screen, in order, with their counts."""
    return page.eval_on_selector_all(
        ".rows .band, .rows .histhead", "els => els.map((e) => e.textContent)")


def test_the_list_is_grouped_by_what_each_session_needs(past_at, ws):
    """Most urgent first. "who needs me" is the question this tool exists to
    answer, so the answer is a group with its own heading, not a colour you
    have to find in a list."""
    daemon, path = past_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_selector(".rows .band")
            # One live session, ready, and two finished ones folded away.
            assert bands(page) == ["ready · 1", "▸ history · 2"]

            ws.append_event(conftest.event(
                "PermissionRequest", tool_name="Bash",
                tool_input={"command": "ls ~"}, ts=time.time()))
            daemon.tick()
            page.wait_for_function(
                "[...document.querySelectorAll('.rows .band')]"
                ".some((e) => e.textContent.startsWith('needs you'))")
            # It moved out of "ready" and into "needs you", which is the whole
            # point of the grouping.
            assert bands(page) == ["needs you · 1", "▸ history · 2"]
        finally:
            browser.close()


def test_a_working_agent_is_listed_above_one_waiting_at_its_prompt(ws, pair_at):
    """An agent still going is something you may want to look in on. One
    sitting at its prompt has finished with you. Ready used to come second,
    on the reading that wanting a prompt is nearer to wanting you -- it is
    not, because nothing about it is waiting."""
    daemon, url = pair_at
    with sync_playwright() as play:
        browser, page = open_page(play, url)
        try:
            page.wait_for_function("state.sessions.length === 2")
            assert bands(page) == ["ready \u00b7 2"]

            ws.append_event(conftest.event(
                "UserPromptSubmit", sid="s2", prompt="go", ts=time.time()))
            daemon.tick()
            page.wait_for_function(
                "() => document.querySelectorAll('.rows .band').length === 2")
            assert bands(page) == ["working \u00b7 1", "ready \u00b7 1"]
        finally:
            browser.close()


def test_a_group_with_nothing_in_it_has_no_heading(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.wait_for_selector(".rows .band")
            assert bands(page) == ["ready · 1"]
        finally:
            browser.close()


def test_a_session_that_has_just_started_is_ready(ws, served):
    """It is waiting at its prompt, which is what ready means. It used to say
    "starting" and settle after five minutes — a word that was true for a
    moment and wrong for a day, because SessionStart is often the only event a
    session ever sends."""
    daemon, base = served
    ws.append_event(conftest.event("SessionStart", cwd="/w/one",
                                   ts=time.time(), pane="%7", pid=1))
    daemon.store.refresh()
    assert daemon.store.rows[0]["state"] == "done"
    assert daemon.store.rows[0]["state_word"] == "ready"


def test_the_list_is_newest_first_inside_a_band(ws, pair_at):
    """The session you touched last is the one you came for. It used to be
    sorted by worktree, so in a list of twenty it was somewhere in the middle
    under `a`. Sort `sort_sessions` by name again and the order flips."""
    daemon, url = pair_at
    with sync_playwright() as play:
        browser, page = open_page(play, url)
        try:
            page.wait_for_function("state.sessions.length === 2")
            first = page.eval_on_selector_all(
                ".row", "els => els.map((one) => one.dataset.id)")
            # The one that spoke last leads. `pair_at` starts s2 after s1.
            assert first == ["s2", "s1"], first

            # And it follows what happens, not what the rows are called.
            # A whole turn, so s1 ends back under "ready" beside s2 rather
            # than in the band below it: the order inside a band is what this
            # is about.
            now = time.time()
            ws.append_event(conftest.event(
                "UserPromptSubmit", sid="s1", prompt="go", ts=now + 5))
            ws.append_event(conftest.event("Stop", sid="s1", ts=now + 6))
            daemon.tick()            # fold it, and tell the page
            page.wait_for_function(
                """() => [...document.querySelectorAll('.row')]
                           .map((one) => one.dataset.id)[0] === 's1'""")
        finally:
            browser.close()


def test_an_age_older_than_an_hour_carries_two_units(pair_at):
    """"2d" covers two days to just short of three, which is not an answer to
    "when did this last do something". Drop the second unit and the row says
    "2d" for a session last seen two and a half days ago."""
    _, url = pair_at
    with sync_playwright() as play:
        browser, page = open_page(play, url)
        try:
            said = page.evaluate("""() => {
              const now = Date.now() / 1000 + state.skew;
              return [40, 90, 2 * 3600, 2 * 3600 + 15 * 60,
                      2 * 86400, 2 * 86400 + 6 * 3600]
                       .map((old) => ago(now - old));
            }""")
            assert said == ["40s", "1min", "2h", "2h 15min", "2d", "2d 6h"]
        finally:
            browser.close()
