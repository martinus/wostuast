"""The session list: state, filter, counts and history.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations

import json
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

def test_a_row_is_not_rebuilt_every_second(page_at, ws, tmp_path):
    """The ages advance once a second. Rebuilding the rows to do it restarted
    the needs-you pulse before it could finish a cycle, and threw away the
    row's colour transition. Only the age text may change."""
    daemon, _ = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            # An age counts seconds only for its first minute, and a loaded
            # CI runner took longer than that to open the page: the fixture's
            # event read "1min" twice. A fresh `Stop` starts the count again
            # and leaves the session where it was, so the row stays in place.
            ws.append_event(conftest.event("Stop", sid="s1", cwd=str(tmp_path),
                                           pane="%7", pid=1, ts=time.time()))
            daemon.tick()
            page.wait_for_function(
                r"/^\d+s$/.test(document.querySelector('.row .age').textContent)")
            page.evaluate("window.__row = document.querySelector('.row .line1')")
            first = page.locator(".row .age").first.inner_text()
            page.wait_for_timeout(2400)
            assert page.evaluate("window.__row.isConnected"), "the row was rebuilt"
            assert page.locator(".row .age").first.inner_text() != first
        finally:
            browser.close()


def test_a_row_is_kept_when_the_state_changes(page_at, ws):
    """A row that changes state fades into its new colour (CLAUDE.md,
    **Motion**). A fade needs the same row on both sides of the change, and
    the sidebar used to be rebuilt whole, so the one change the fade is for
    was the one that threw it away."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.evaluate("window.__dot = document.querySelector('.row')")
            assert "done" in page.evaluate("window.__dot.className")
            ws.append_event(conftest.event(
                "PermissionRequest", tool_name="Bash",
                tool_input={"command": "ls ~"}, ts=time.time()))
            daemon.tick()            # fold it, and tell the page
            page.wait_for_function("window.__dot.className.includes('needs_you')")
            assert page.evaluate("window.__dot.isConnected"), "the row was rebuilt"
        finally:
            browser.close()


def test_a_row_shows_its_state_in_its_colour(page_at):
    """The row's edge and tint say the state, and there is no dot and no
    word beside them: nine sessions are hard to read from one small dot."""
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
            # Named by its row, not counted: `putContext` builds the bar for
            # the strip and for each rate-limit window too, so `.ctx` on its
            # own finds several and none of them is this one.
            seen = page.evaluate("""() => { let key = null;
              for (const one of document.querySelectorAll('.sessionbody dl > *')) {
                if (one.tagName === 'DT') { key = one.innerText; continue; }
                if (key !== 'context used') continue;
                const fill = one.querySelector('.ctx .bar .fill');
                return {bars: one.querySelectorAll('.ctx .bar').length,
                        width: fill && fill.style.width,
                        text: one.innerText};
              }
              return null; }""")
            assert seen, "no context row in the panel"
            assert seen["bars"] == 1, seen
            assert seen["width"] == "41%", seen
            assert "41% ctx" in seen["text"], seen
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


# --- what to be told about ----------------------------------------------------


def alerts_page(play, where):
    """A page whose browser has already allowed alerts, and which records
    every one it is handed. A real `Notification` cannot be read back from
    Playwright, so it is replaced before the page's own script runs."""
    browser = fresh_context(play)
    browser.grant_permissions(["notifications"])
    page = browser.new_page()
    page.add_init_script("""
      window.__told = [];
      window.Notification = function (title, options) {
        window.__told.push([title, (options || {}).body || ""]);
      };
      window.Notification.permission = "granted";
      window.Notification.requestPermission = async () => "granted";
    """)
    page.goto(where, wait_until="domcontentloaded")
    page.wait_for_selector(".row", timeout=15000)
    page.wait_for_function("!!window.marked", timeout=15000)
    return browser, page


def test_the_needs_you_alert_is_on_as_soon_as_alerts_are(page_at):
    """It is the one thing this tool exists to tell you, so it is not a
    second choice on top of allowing alerts at all. The finished one is a
    choice, so it is off until it is asked for."""
    _, path = page_at
    with sync_playwright() as play:
        browser, page = alerts_page(play, path)
        try:
            page.click("#bell")
            page.wait_for_selector("#alerts", state="visible")
            assert page.is_checked("#alertneeds")
            assert not page.is_checked("#alertdone")
            assert "alerts on" in page.locator("#bell").inner_text()
        finally:
            browser.close()


def test_an_agent_that_needs_you_is_said_once(ws, page_at):
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = alerts_page(play, path)
        try:
            page.wait_for_function("state.sessions.length === 1")
            ws.append_event(conftest.event(
                "PermissionRequest", tool_name="Bash",
                tool_input={"command": "rm -rf build"}, ts=time.time()))
            daemon.tick()
            page.wait_for_function("window.__told.length === 1")
            told = page.evaluate("window.__told")
            assert "needs you" in told[0][0], told

            # A second pass over the same amber row says nothing more. It has
            # to be a pass that really happens: the daemon pushes only when a
            # row differs, so a tick that changes nothing never reaches
            # `notifyAbout` at all and would prove nothing. A second dialog
            # about another command moves `reason`, and leaves it amber.
            ws.append_event(conftest.event(
                "PermissionRequest", tool_name="Bash",
                tool_input={"command": "rm -rf dist"}, ts=time.time() + 1))
            daemon.tick()
            page.wait_for_function(
                "() => state.sessions[0].reason.includes('dist')")
            assert page.evaluate("window.__told.length") == 1
        finally:
            browser.close()


def test_a_finished_agent_is_said_only_when_it_was_working(ws, page_at):
    """"done" is where a session sits between turns, so the news is the moment
    it gets there. A session already finished when the page opened is not
    news, and neither is one this page has never seen working."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = alerts_page(play, path)
        try:
            page.wait_for_function("state.sessions.length === 1")
            page.click("#bell")
            page.click("#alertdone")
            page.wait_for_function("document.getElementById('alertdone').checked")
            # A real second pass over sessions that are sitting at "done".
            # It has to be a pass that really happens: the daemon pushes only
            # when a row differs, so a tick that changes nothing never reaches
            # `notifyAbout` and would prove nothing. A second session starting
            # changes the list, and neither of them has been seen working.
            now = time.time()
            ws.append_event(conftest.event(
                "SessionStart", sid="s2", ts=now, pane="%9"))
            daemon.tick()
            page.wait_for_function("state.sessions.length === 2")
            assert page.evaluate("window.__told.length") == 0

            ws.append_event(conftest.event(
                "UserPromptSubmit", prompt="go", ts=now + 1))
            daemon.tick()
            page.wait_for_function(
                "() => state.sessions.some((one) => one.state === 'working')")
            assert page.evaluate("window.__told.length") == 0

            ws.append_event(conftest.event("Stop", ts=now + 2))
            daemon.tick()
            page.wait_for_function("window.__told.length === 1")
            assert "has finished" in page.evaluate("window.__told")[0][0]
        finally:
            browser.close()


def test_an_alert_switched_on_mid_turn_still_reports_that_turn(ws, page_at):
    """What each session is doing is written down on every pass, whatever the
    switches say. So ticking the box while an agent is working still tells
    you when it stops — and a session that reached "done" while nobody was
    listening is already at "done" rather than a change waiting to be
    announced, which is what stops a backlog arriving at once.

    Record the states only while the switch is on and the alert goes silent
    for exactly the turn the reader switched it on for."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = alerts_page(play, path)
        try:
            page.wait_for_function("state.sessions.length === 1")
            now = time.time()
            ws.append_event(conftest.event(
                "UserPromptSubmit", prompt="go", ts=now))
            daemon.tick()
            page.wait_for_function("state.sessions[0].state === 'working'")
            assert page.evaluate("window.__told.length") == 0

            # On, with the turn already running.
            page.click("#bell")
            page.click("#alertdone")
            page.wait_for_function("document.getElementById('alertdone').checked")

            ws.append_event(conftest.event("Stop", ts=now + 1))
            daemon.tick()
            page.wait_for_function("window.__told.length === 1")
            assert "has finished" in page.evaluate("window.__told")[0][0]
        finally:
            browser.close()


def test_the_two_switches_are_remembered_apart(page_at):
    _, path = page_at
    with sync_playwright() as play:
        browser, page = alerts_page(play, path)
        try:
            page.click("#bell")
            page.click("#alertneeds")      # off, from its default on
            page.click("#alertdone")       # on
            page.wait_for_function(
                """() => !document.getElementById('alertneeds').checked
                      && document.getElementById('alertdone').checked""")
            kept = page.evaluate("localStorage.getItem('wostuast-alerts')")
            assert json.loads(kept) == {"needs": False, "done": True}, kept
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector(".row")
            page.click("#bell")
            page.wait_for_selector("#alerts", state="visible")
            assert not page.is_checked("#alertneeds")
            assert page.is_checked("#alertdone")
        finally:
            browser.close()


def test_the_alert_panel_shuts_from_anywhere(page_at):
    """A panel only its own button can close is a panel you have to go back
    to."""
    _, path = page_at
    with sync_playwright() as play:
        browser, page = alerts_page(play, path)
        try:
            for shut in ("body click", "escape", "the bell"):
                page.click("#bell")
                page.wait_for_selector("#alerts", state="visible")
                if shut == "body click":
                    page.mouse.click(700, 500)
                elif shut == "escape":
                    page.keyboard.press("Escape")
                else:
                    page.click("#bell")
                page.wait_for_selector("#alerts", state="hidden")
                assert page.get_attribute("#bell", "aria-expanded") == "false", shut
        finally:
            browser.close()


def test_the_session_panel_names_each_rate_limit_window(page_at):
    """They appear only for a claude.ai Pro or Max subscription, or behind a
    gateway, and only after the first API response — and Claude Code drops a
    window once its reset has passed. So each is drawn only when it was sent,
    never as a nought."""
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            show_tab(page, "session")
            page.wait_for_selector(".sessionbody dl")
            rows = page.evaluate(
                """() => { const out = {}; let key = null;
                     for (const one of document.querySelectorAll('.sessionbody dl > *')) {
                       if (one.tagName === 'DT') key = one.innerText;
                       else out[key] = one.innerText.replace(/\\s+/g, ' ');
                     }
                     return out; }""")
            assert "$1.83" in rows["spent"], rows
            assert "list price" in rows["spent"], rows
            # Named in words, not as the payload spells them.
            assert "24% used" in rows["5-hour limit"], rows
            assert "resets" in rows["5-hour limit"], rows
            assert "41% used" in rows["weekly limit"], rows
        finally:
            browser.close()


def test_a_session_with_no_rate_limits_gets_no_rows_for_them(ws, served):
    daemon, base = served
    ws.append_event(conftest.event(
        "SessionStart", pane="%7", pid=1, ts=time.time()))
    ws.write_status("s1", ws.Status(ts=1.0, name="A session"))
    daemon.store.refresh()
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            page.wait_for_function("state.sessions.length === 1")
            show_tab(page, "session")
            page.wait_for_selector(".sessionbody dl")
            said = page.locator(".sessionbody dl").inner_text()
            assert "limit" not in said, said
            assert "spent" not in said, said
        finally:
            browser.close()


def test_every_alert_makes_itself_heard(page_at):
    """One tag per session, so a second alert replaces the first -- and with
    `renotify` left false a replacement makes no sound and shows no banner.
    An agent that stopped on a second question was never said."""
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            got = page.evaluate("""() => {
              let options = null;
              window.Notification = function (title, given) { options = given; };
              tellAbout({ id: 's1', label: 'x' }, 'x needs you', 'why');
              return options;
            }""")
            assert got["tag"] == "wostuast-s1" and got["renotify"] is True, got
        finally:
            browser.close()


def test_turning_needs_you_on_brings_no_backlog(ws, page_at):
    """`waiting` was filled only while alerts were not allowed at all, not
    while this one switch was off -- so ticking it again said every session
    that had gone amber meanwhile, as though it had just happened."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = alerts_page(play, path)
        try:
            page.wait_for_function("state.sessions.length === 1")
            page.click("#bell")
            page.click("#alertneeds")
            page.wait_for_function("!document.getElementById('alertneeds').checked")
            now = time.time()
            ws.append_event(conftest.event(
                "PermissionRequest", tool_name="Bash",
                tool_input={"command": "rm -rf build"}, ts=now))
            daemon.tick()
            page.wait_for_function(
                "() => state.sessions[0].state === 'needs_you'")
            page.click("#alertneeds")
            page.wait_for_function("document.getElementById('alertneeds').checked")
            # A pass that really happens: a second session changes the list.
            ws.append_event(conftest.event("SessionStart", sid="s2", ts=now + 1,
                                           pane="%9"))
            daemon.tick()
            page.wait_for_function("state.sessions.length === 2")
            assert page.evaluate("window.__told.length") == 0
        finally:
            browser.close()


def test_the_session_tab_does_not_say_what_git_has_not_said(page_at):
    """Before git answered, "not in a repository" and "changed files: none"
    were drawn as facts."""
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function("state.sessions.length === 1")
            said = page.evaluate("""() => {
              const box = document.createElement('div');
              putFacts(box, { ...state.sessions[0], git_known: false,
                              branch: '', dirty: false, repo: '' });
              return box.innerText;
            }""")
            assert "not in a repository" not in said, said
            assert "none" not in said, said
            assert "git has not answered" in said, said
        finally:
            browser.close()

# --- what a row says ---------------------------------------------------------

LONG_BRANCH = "backport/341/OA-74380-rulemetadata-for-the-new-ingest-path"


@pytest.fixture
def rows_at(ws, served, monkeypatch, tmp_path):
    """Four sessions, one in each group, with git facts a real row carries.

    `named` was given a name on the page and waits on a dialog; `fresh` has
    none and is working; `idle` is ready, with the notification that used to
    say "waiting for input" under it; `old` has ended."""
    daemon, url = served
    agent = tmp_path / "agent"
    places = {sid: agent / tree for sid, tree in
              (("named", "richpalm"), ("fresh", "bluefox"),
               ("idle", "oakleaf"), ("old", "oldtree"))}
    facts = {
        "named": ws.GitFacts(repo="agent", branch=LONG_BRANCH, ahead=1,
                             root=str(places["named"]),
                             remote="https://example.com/team/agent.git"),
        "fresh": ws.GitFacts(repo="agent", branch="feature/retry", dirty=True,
                             touched_files=3, root=str(places["fresh"])),
    }
    by_dir = {str(places[sid]): one for sid, one in facts.items()}
    monkeypatch.setattr(ws, "git_facts_many", lambda dirs: {
        d: by_dir.get(d, ws.GitFacts(repo="agent", branch="main")) for d in dirs})
    now = time.time()
    for sid, where in places.items():
        where.mkdir(parents=True)
        ws.append_event(conftest.event("SessionStart", sid=sid, cwd=str(where),
                                       pid=1, ts=now - 60))
    ws.append_event(conftest.event("PermissionRequest", sid="named",
                                   cwd=str(places["named"]), tool_name="Bash",
                                   tool_input={"command": "curl -s example.com"},
                                   ts=now - 5))
    ws.append_event(conftest.event("PreToolUse", sid="fresh",
                                   cwd=str(places["fresh"]), tool_name="Bash",
                                   tool_use_id="t1",
                                   tool_input={"command": "pytest -q"}, ts=now - 5))
    ws.append_event(conftest.event("Notification", sid="idle",
                                   cwd=str(places["idle"]),
                                   notification_type="idle_prompt",
                                   message="Claude is waiting for your input",
                                   ts=now - 5))
    ws.append_event(conftest.event("SessionEnd", sid="old",
                                   cwd=str(places["old"]), reason="logout",
                                   ts=now - 5))
    # The title Claude Code writes from the first prompt. It is not the row's.
    ws.write_status("fresh", ws.Status(ts=now, name="A generated title"))
    daemon.store.rename("named", "rule work")
    daemon.store.refresh()
    return daemon, url, places


def open_rows(play, rows_at):
    daemon, url, _ = rows_at
    context = fresh_context(play)
    context.add_init_script("localStorage.setItem('wostuast-history', 'open')")
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_function("document.querySelectorAll('.row').length === 4")
    return context, page


READ_ROWS = """() => Object.fromEntries([...document.querySelectorAll('.row')].map(
  (row) => {
    const shown = (sel) => {
      const node = row.querySelector(sel);
      return node && node.getClientRects().length ? node.innerText : null;
    };
    const title = (sel) => (row.querySelector(sel) || {}).title;
    return [row.dataset.id, {
      name: shown('.line1 .name'), word: shown('.word'),
      age: shown('.line1 .age'), repo: shown('.repo'), repoTitle: title('.repo'),
      tree: shown('.worktree'), treeTitle: title('.worktree'),
      branch: shown('.branch'), git: shown('.gitstate'), said: shown('.said'),
      dots: row.querySelectorAll('.dot').length, text: row.innerText}];
  }))"""


def test_a_row_says_its_name_where_it_is_its_branch_and_when(rows_at):
    """The name, the repository and the worktree, the branch and what git
    counts, and the time -- and the state nowhere but the colour and the
    group: a word at the top and "waiting for input" at the foot said it a
    third and a fourth time, and the dot a fifth. A name not given is where
    the session stands, never the title Claude Code wrote, which `/rename`
    does not reach and which went stale beside the branch."""
    _, _, places = rows_at
    with sync_playwright() as play:
        browser, page = open_rows(play, rows_at)
        try:
            rows = page.evaluate(READ_ROWS)
            named, fresh = rows["named"], rows["fresh"]
            assert named["name"] == "rule work"
            assert fresh["name"] == "agent/bluefox"
            assert "A generated title" not in fresh["text"]
            # Every row, named or not, says its repository and worktree, and
            # a hover says where each one is.
            assert (named["repo"], named["tree"]) == ("agent", "richpalm")
            assert (fresh["repo"], fresh["tree"]) == ("agent", "bluefox")
            assert named["repoTitle"] == "https://example.com/team/agent.git"
            assert fresh["repoTitle"] == "no remote"
            assert named["treeTitle"] == str(places["named"])
            assert named["branch"] == LONG_BRANCH     # the ellipsis is drawn
            assert "↑1" in named["git"] and "clean" in named["git"]
            assert "3 files" in fresh["git"]
            for one in rows.values():
                assert one["dots"] == 0
                assert one["age"], "the time stands beside the name"
            # The state is said by the colour and the group, and only a
            # finished row, whose group holds two states, says it in words.
            assert named["word"] is None and fresh["word"] is None
            assert rows["idle"]["word"] is None
            assert rows["old"]["word"] == "ended"
            # What it is doing or asks, while it is doing or asking.
            assert "permission" in named["said"]
            assert "pytest" in fresh["said"]
            assert rows["idle"]["said"] is None
            assert "waiting for input" not in rows["idle"]["text"]
            assert rows["old"]["said"] is None
            assert "ended (" not in rows["old"]["text"]
        finally:
            browser.close()


def test_the_git_line_is_one_line_and_its_counts_stand_at_the_right(rows_at):
    """A long branch pushed "✓ clean" onto a second line of its own. Only the
    branch gives way now, with an ellipsis, and what git counts stands at the
    right edge, so the counts of every row read as one column."""
    with sync_playwright() as play:
        browser, page = open_rows(play, rows_at)
        try:
            measure = """(id) => {
              const line = document.querySelector(`.row[data-id="${id}"] .branch`)
                .parentElement;
              const high = parseFloat(getComputedStyle(line).lineHeight)
                || parseFloat(getComputedStyle(line).fontSize) * 1.6;
              const text = line.querySelector('.branch .text');
              return {tall: line.getBoundingClientRect().height, high,
                      cut: text.scrollWidth > text.clientWidth,
                      counts: line.querySelector('.gitstate').getBoundingClientRect().right,
                      edge: line.getBoundingClientRect().right,
                      parts: [...line.querySelectorAll('.gitstate > *')]
                        .map((one) => one.getBoundingClientRect().height)};
            }"""
            out = page.evaluate(measure, "named")
            assert out["cut"], "the branch is long enough to be cut"
            assert out["tall"] < 1.5 * out["high"], out
            assert all(h < 1.5 * out["high"] for h in out["parts"]), out
            assert abs(out["counts"] - out["edge"]) < 1, out
            # A short branch leaves room, and the counts still stand at the
            # edge rather than after the branch.
            out = page.evaluate(measure, "fresh")
            assert not out["cut"]
            assert abs(out["counts"] - out["edge"]) < 1, out
        finally:
            browser.close()


def test_a_row_is_renamed_where_it_stands(rows_at, ws):
    """A double-click or `e` edits the name in the row; Enter keeps it and
    Escape does not. The row is filled again on every push and moves when its
    state changes, and neither may take what is being typed."""
    daemon, _, places = rows_at
    with sync_playwright() as play:
        browser, page = open_rows(play, rows_at)
        try:
            page.dblclick('.row[data-id="fresh"] .name')
            box = page.locator('.row[data-id="fresh"] input.rowname')
            assert box.input_value() == "agent/bluefox"
            page.keyboard.type("retry work")
            # A push that fills the row again and moves it to the top, as a
            # dialog coming up does, with the box still open.
            ws.append_event(conftest.event(
                "PermissionRequest", sid="fresh", cwd=str(places["fresh"]),
                tool_name="Bash", tool_input={"command": "rm -r build"},
                ts=time.time()))
            daemon.tick()
            page.wait_for_function(
                "document.querySelector('.row').dataset.id === 'fresh'")
            page.keyboard.type("!")
            assert box.input_value() == "retry work!"
            page.keyboard.press("Enter")
            page.wait_for_function(
                """document.querySelector('.row[data-id="fresh"] .name')
                   .textContent === 'retry work!'""")
            assert daemon.store.names.get("fresh") == "retry work!"

            # `e` on the chosen row, and Escape: nothing is kept.
            page.click('.row[data-id="idle"]')
            page.keyboard.press("e")
            page.keyboard.type("not this")
            page.keyboard.press("Escape")
            page.wait_for_function(
                "!document.querySelector('input.rowname')")
            assert page.locator('.row[data-id="idle"] .name').inner_text() \
                == "agent/oakleaf"
            # Enter on the name it came with is not a name chosen: kept, it
            # would stop following the worktree for good.
            page.keyboard.press("e")
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)          # proving nothing was sent
            assert "idle" not in daemon.store.names
        finally:
            browser.close()
