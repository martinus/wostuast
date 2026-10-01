"""The session list: state, filter, counts and history.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations

import json
import time

import pytest

import conftest
from browser import (
    hold,
    kept,
    spy_on_note,
    skip_without_browser,
    sync_playwright,
    fresh_context,
    open_page,
    show_tab,
    two_rows,
    wait_until,
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
            # The chosen row wears its tint as a layer under its fade, so
            # the tint is asked of the row itself.
            look = page.evaluate("""() => {
              const row = document.querySelector('.row');
              const probe = document.createElement('div');
              probe.style.background = 'var(--soft)';
              row.appendChild(probe);
              const tint = getComputedStyle(probe).backgroundColor;
              probe.remove();
              const style = getComputedStyle(row);
              return {tint, face: style.backgroundColor, image: style.backgroundImage,
                      chosen: row.classList.contains('chosen'),
                      plain: getComputedStyle(document.querySelector('.sidebar'))
                        .backgroundColor};
            }""")
            assert edge not in ("rgba(0, 0, 0, 0)", "transparent")
            assert look["tint"] not in ("rgba(0, 0, 0, 0)", look["plain"]), look
            worn = look["image"] if look["chosen"] else look["face"]
            assert look["tint"] in worn, "the row is not tinted by its state"
        finally:
            browser.close()


def test_the_sidebar_filter_narrows_the_list(pair_at):
    """One story on one page: type letters, type nonsense, press Escape."""
    with sync_playwright() as play:
        browser, page = open_page(play, pair_at)
        try:
            two_rows(page)
            counted = page.title()

            page.fill("#pick", "wmhr")          # scattered letters, as in Files
            page.wait_for_function("document.querySelectorAll('.row').length === 1")
            assert "warmhare" in page.locator(".row .name").inner_text()
            # The counts are the answer to "who needs me". A filter in the box
            # must not hide an agent that is waiting.
            assert page.title() == counted

            page.fill("#pick", "nowhereatall")
            page.wait_for_selector(".rows .nohits")
            assert page.locator(".row").count() == 0

            page.press("#pick", "Escape")
            two_rows(page)
            assert page.input_value("#pick") == ""
        finally:
            browser.close()


def test_a_hidden_session_still_counts(pair_at, ws):
    """The title, the icon and the alerts are about every session. They used to
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
            assert "needs you" not in page.title()

            ws.append_event(conftest.event(
                "PermissionRequest", sid="s1", tool_name="Bash",
                tool_input={"command": "ls ~"}, ts=time.time()))
            daemon.tick()
            page.wait_for_function("document.title.includes(' asks ')")
            assert page.locator(".row").count() == 1, "the filter stopped working"
            # The row's name, cut as the title cuts it: this one is a long
            # temporary path.
            name = page.evaluate(
                "clip(rowName(state.sessions.find((one) => one.id === 's1')), 30)")
            assert page.title() == name + " asks \u00b7 wostuast"
        finally:
            browser.close()


def test_the_session_list_ends_with_its_rows(page_at):
    """A strip of keys stood under the rows and said, in two cramped lines,
    what ? says in full. The reader found it odd and never needed it, so the
    list ends with its last row."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            assert page.evaluate(
                "document.querySelector('.sidebar').lastElementChild.id") == "rows"
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
        finally:
            browser.close()


READ_TAB = """() => {
  const row = document.querySelector('.row.chosen');
  const grip = document.getElementById('grip');
  const list = document.getElementById('rows').getBoundingClientRect();
  const at = row.getBoundingClientRect();
  const from = grip.getBoundingClientRect().top;
  const look = getComputedStyle(row);
  const other = getComputedStyle(document.querySelector('.row:not(.chosen)'));
  const root = getComputedStyle(document.documentElement);
  const colour = (value) => {
    const probe = document.createElement('div');
    probe.style.background = value;
    document.body.appendChild(probe);
    const said = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return said;
  };
  // What the row meets: the split tab's own list, or the page itself.
  const side = document.querySelector('.content.split > .side');
  const beside = side ? getComputedStyle(side).backgroundColor
                      : colour(root.getPropertyValue('--bg'));
  return {
    fade: look.backgroundImage.split('), linear-gradient')[0] + ')', content: beside,
    ground: look.backgroundColor,
    list: getComputedStyle(document.querySelector('.sidebar')).backgroundColor,
    edge: colour(root.getPropertyValue('--edge')),
    page: colour(root.getPropertyValue('--bg')),
    open: grip.style.getPropertyValue('--gap-top') !== '0px'
      && getComputedStyle(grip).backgroundImage.includes(beside),
    gripWidth: grip.offsetWidth,
    top: look.borderTopWidth, bottom: look.borderBottomWidth,
    right: look.borderRightWidth,
    others: [other.borderTopWidth, other.borderBottomWidth],
    indent: Math.round(at.left - document.querySelector('.row:not(.chosen)')
      .getBoundingClientRect().left),
    behind: Math.round(grip.getBoundingClientRect().left - document
      .querySelector('.row:not(.chosen)').getBoundingClientRect().right),
    reach: Math.round(grip.getBoundingClientRect().left - at.right),
    gap: [parseFloat(grip.style.getPropertyValue('--gap-top')),
          parseFloat(grip.style.getPropertyValue('--gap-bottom'))],
    want: [Math.max(at.top, list.top) - from, Math.min(at.bottom, list.bottom) - from],
  };
}"""


def test_the_chosen_row_is_a_tab_of_the_content_beside_it(rows_at, ws, tmp_path):
    """As in a browser, the chosen row wears the content's ground and runs
    to the line between the list and the content, the line opens where the
    row meets it, and the row's top and bottom are that line turned round
    it. The line stands outside the list that scrolls, so the opening has to
    follow the row when the list moves, and close when the row goes."""
    daemon = rows_at[0]
    with sync_playwright() as play:
        browser, page = open_rows(play, rows_at)
        try:
            page.set_viewport_size({"width": 1100, "height": 420})
            page.click('.row[data-id="fresh"]', position={"x": 5, "y": 5})
            page.wait_for_function("state.chosen === 'fresh'")
            # The row fades into its new ground, and the scroll event lands a
            # frame after the scroll.
            page.wait_for_function(
                "document.querySelector('.row.chosen').getAnimations().length === 0")
            page.evaluate("new Promise((done) => requestAnimationFrame(() => "
                          "requestAnimationFrame(done)))")
            seen = page.evaluate(READ_TAB)
            # The fade ends in the ground of what it meets -- here the map,
            # which stands apart from the page -- and so does the opening.
            assert seen["fade"].startswith("linear-gradient(90deg"), seen
            assert seen["fade"].endswith(seen["content"] + ")"), seen
            assert seen["content"] != seen["page"] and seen["open"], seen
            # The list wears the grip's colour, and the chosen row has no
            # ground of its own: its tint stands on the list's, as its
            # group's rows' do.
            assert seen["list"] == seen["edge"], seen
            assert seen["ground"] == "rgba(0, 0, 0, 0)", seen
            # Its outline is the other rows' own: a line in the list's
            # colour could not be seen, and cut the corner of its edge.
            assert [seen["top"], seen["bottom"]] == seen["others"], seen
            # In from the other rows by the grip's width, as it crosses the
            # grip on the right; and they run to the line as well, as tabs
            # behind it.
            assert seen["indent"] == seen["gripWidth"] > 0, seen
            assert seen["behind"] == 0, seen
            assert seen["right"] == "0px" and seen["reach"] == 0, seen
            assert seen["gap"][1] > seen["gap"][0] > 0, seen
            assert all(abs(a - b) < 0.5
                       for a, b in zip(seen["gap"], seen["want"])), seen

            # A row that arrives above it moves it down, and nothing about
            # the chosen row changes size or scrolls: the draw has to say so.
            # A taller window first, so the row stays in the list's view.
            page.set_viewport_size({"width": 1100, "height": 700})
            page.evaluate("new Promise((done) => requestAnimationFrame(() => "
                          "requestAnimationFrame(done)))")
            seen = page.evaluate(READ_TAB)
            where = tmp_path / "agent" / "newer"
            where.mkdir(parents=True)
            ws.append_event(conftest.event("PreToolUse", sid="newer", cwd=str(where),
                                           tool_name="Bash", tool_use_id="t9",
                                           tool_input={"command": "make"},
                                           ts=time.time()))
            daemon.tick()
            page.wait_for_function("document.querySelectorAll('.row').length === 5")
            page.evaluate("new Promise((done) => requestAnimationFrame(() => "
                          "requestAnimationFrame(done)))")
            moved = page.evaluate(READ_TAB)
            assert moved["want"][0] > seen["want"][0], (seen, moved)
            assert all(abs(a - b) < 0.5
                       for a, b in zip(moved["gap"], moved["want"])), moved

            # Short enough that the list scrolls: it runs to the foot of the
            # page now that no strip of keys stands under it.
            page.set_viewport_size({"width": 1100, "height": 350})

            # The list's bar only while the pointer is on the list: anywhere
            # else it stands between the row and the content.
            bar = "getComputedStyle(document.getElementById('rows')).scrollbarWidth"
            page.mouse.move(900, 300)
            assert page.evaluate(bar) == "none"
            page.hover('.row[data-id="named"]')
            assert page.evaluate(bar) == "thin"
            page.mouse.move(900, 300)

            # Scrolled half out of the list, only what the list shows opens it.
            page.evaluate("""() => {
              const list = document.getElementById('rows');
              const row = document.querySelector('.row.chosen');
              list.scrollTop += row.getBoundingClientRect().top
                - list.getBoundingClientRect().top + row.offsetHeight / 2;
            }""")
            page.wait_for_function("""() => {
              const grip = document.getElementById('grip');
              const list = document.getElementById('rows').getBoundingClientRect();
              return Math.abs(parseFloat(grip.style.getPropertyValue('--gap-top'))
                - (list.top - grip.getBoundingClientRect().top)) < 0.5;
            }""")
            # Scrolled out of it, the line is whole again. A shorter window,
            # so the list can scroll that far -- shorter again since the
            # strip of keys under the list went, and the list got its room.
            page.set_viewport_size({"width": 1100, "height": 250})
            page.evaluate("document.getElementById('rows').scrollTop = 1e6")
            page.wait_for_function("""() => {
              const row = document.querySelector('.row.chosen');
              const list = document.getElementById('rows').getBoundingClientRect();
              return row.getBoundingClientRect().bottom < list.top
                || row.getBoundingClientRect().top > list.bottom;
            }""")
            page.wait_for_function(
                "parseFloat(document.getElementById('grip').style"
                ".getPropertyValue('--gap-bottom')) === 0")
        finally:
            browser.close()


TAB_ICON_PIXELS = """(colour) => {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 32;
  const pen = canvas.getContext('2d');
  paintIcon(pen, colour);
  const at = (x, y) => [...pen.getImageData(x, y, 1, 1).data];
  return {body: at(3, 12), chin: at(16, 29.5), antenna: at(16, 2),
          big: at(13.5, 16.5), small: at(23, 17.5), beside: at(26.5, 17.5),
          mouth: at(16, 26), corner: at(9, 24.5), outside: at(2, 2)};
}"""


def test_the_tab_icon_is_a_robot_in_the_states_colour(page_at):
    """The icon was a dot in the state's colour, and "ready" was the blue of
    the Jira and Bitbucket tabs beside it; then a robot over a status line
    in the state's colour, which was too thin to see in a tab bar. The
    whole robot is the colour now. One eye is big and one small, and a wide
    smile: all three cut out, so the tab bar shows through them."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            seen = page.evaluate(TAB_ICON_PIXELS, "#e37400")
            amber = [0xe3, 0x74, 0x00, 255]
            assert seen["body"] == amber and seen["chin"] == amber, seen
            assert seen["antenna"] == amber, seen
            # The big eye reaches where the small one's side does not.
            assert seen["big"][3] == 0 and seen["small"][3] == 0, seen
            assert seen["beside"] == amber, seen
            assert seen["mouth"][3] == 0 and seen["corner"][3] == 0, seen
            assert seen["outside"][3] == 0, seen
        finally:
            browser.close()


def favicon_pixels(page):
    """The colour of the icon the tab has now, from its body."""
    return page.evaluate("""async () => {
      const image = new Image();
      image.src = document.querySelector("link[rel='icon']").href;
      await image.decode();
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = 32;
      const pen = canvas.getContext('2d');
      pen.drawImage(image, 0, 0);
      const at = (x, y) => [...pen.getImageData(x, y, 1, 1).data].slice(0, 3);
      return {body: at(3, 12)};
    }""")


def test_the_tab_icon_says_the_state_in_the_bar_it_stands_in(ws, pair_at):
    """The bar's own ink while nothing waits, amber when an agent needs
    you. The icon stands in the browser's tab bar, not on the page, so its
    colours follow the browser's light or dark -- a page forced light in a
    dark browser drew a dark robot on a dark bar."""
    daemon, path = pair_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.emulate_media(color_scheme="light")
            page.evaluate("() => { applyTheme('dark'); redrawIcon(); }")
            quiet = favicon_pixels(page)
            assert quiet["body"] == [0x3c, 0x40, 0x43], "a light bar's ink"

            ws.append_event(conftest.event(
                "PermissionRequest", sid="s1", tool_name="Bash",
                tool_input={"command": "ls ~"}, ts=time.time()))
            daemon.tick()
            page.wait_for_function("document.title.includes(' asks ')")
            assert favicon_pixels(page)["body"] == [0xe3, 0x74, 0x00]

            page.emulate_media(color_scheme="dark")
            # A loop in Python, not `wait_for_function`: that took the
            # promise an async check gives back as a yes, at once.
            wait_until(page,
                       lambda: favicon_pixels(page)["body"] == [0xfc, 0xad, 0x4d])
            assert favicon_pixels(page)["body"] == [0xfc, 0xad, 0x4d]
        finally:
            browser.close()


def test_the_tab_title_names_who_needs_you(page_at):
    """A tab cuts the end of its title off, so it leads with what matters:
    who needs you, by the name on the row; else how many work; else how
    many are ready. It said "(1) needs you" and left you to look for whom,
    and "wostuast" alone while four agents sat ready."""
    cases = [
        ([["a", "needs_you", "fix-login"]], "fix-login asks \u00b7 wostuast"),
        ([["a", "needs_you", "fix-login"], ["b", "needs_you", "api-retry"],
          ["c", "working", "other"]],
         "fix-login, api-retry need you \u00b7 wostuast"),
        ([["a", "needs_you", "one"], ["b", "needs_you", "two"],
          ["c", "needs_you", "three"], ["d", "needs_you", "four"]],
         "one, two +2 need you \u00b7 wostuast"),
        ([["a", "working", "x"], ["b", "working", "y"], ["c", "done", "z"]],
         "2 working \u00b7 wostuast"),
        ([["a", "done", "x"], ["b", "done", "y"], ["c", "ended", "z"]],
         "2 ready \u00b7 wostuast"),
        ([["a", "ended", "x"]], "wostuast"),
        ([], "wostuast"),
        ([["a", "needs_you", "a name that is far too long for any tab"]],
         "a name that is far too long f\u2026 asks \u00b7 wostuast"),
    ]
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            for rows, want in cases:
                said = page.evaluate("""(rows) => tabTitle(rows.map(
                  ([id, state, name]) => ({id, state, name, mine: true})))""",
                  rows)
                assert said == want, (rows, said)
        finally:
            browser.close()


def test_the_tab_says_what_is_happening(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            assert page.title() == "1 ready \u00b7 wostuast"   # one quiet session
            icon = page.evaluate(
                "document.querySelector(\"link[rel='icon']\")?.getAttribute('href') || ''")
            assert icon.startswith("data:image/png"), "no icon was drawn"
        finally:
            browser.close()


def test_alerts_are_off_until_you_ask(page_at):
    """A page that asked for notification permission on load would be rude, and
    browsers punish it."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            assert page.get_attribute("#settings", "data-alerts") == "off"
            # Said on the button, as the crossed-out bell used to say it.
            assert page.locator("#settings .offmark").is_visible()
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
            assert page.evaluate("state.sessions.length") == 3
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






def test_a_drag_on_an_edge_starts_only_by_hand_and_always_stops(page_at):
    """A drag started on any button, held no capture, and stopped only on
    `pointerup`. A right-click on the grip opens the context menu on Linux
    and macOS, and the menu takes the `pointerup`: the sidebar then followed
    the mouse with no button held. A touch the browser cancels did the
    same. A headless browser has no context menu, so the test says what the
    drag does at each step rather than waiting for a menu."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            grip = page.locator("#grip").bounding_box()
            x, y = grip["x"] + grip["width"] / 2, grip["y"] + 200
            width = "getComputedStyle(document.documentElement)" \
                    ".getPropertyValue('--sidebar-w')"
            dragging = "document.body.classList.contains('dragging')"
            page.evaluate("""() => document.getElementById('grip')
              .addEventListener('pointerdown', (at) => { window.__id = at.pointerId; })""")
            held = "document.getElementById('grip').hasPointerCapture(window.__id)"
            page.mouse.move(x, y)
            page.mouse.down(button="right")
            assert not page.evaluate(dragging), "a right press started a drag"
            page.mouse.up(button="right")

            for stop in ("pointercancel", "lostpointercapture"):
                page.mouse.move(x, y)
                page.mouse.down()
                assert page.evaluate(dragging)
                assert page.evaluate(held), "the grip did not capture the pointer"
                before = page.evaluate(width)
                # Sent by hand: this Chromium, driven from here, sends
                # neither a cancel nor a lost capture of its own.
                page.evaluate("""(name) => document.getElementById('grip')
                  .dispatchEvent(new PointerEvent(name,
                                 {bubbles: true, pointerId: window.__id}))""", stop)
                page.mouse.move(x + 80, y, steps=4)
                assert not page.evaluate(dragging), stop
                assert page.evaluate(width) == before, stop
                page.mouse.up()
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
            page.click("#settings")
            page.wait_for_selector("#setpop", state="visible")
            assert page.is_checked("#alertneeds")
            assert not page.is_checked("#alertdone")
            assert page.get_attribute("#settings", "data-alerts") == "on"
            assert page.locator("#settings .offmark").is_hidden()
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
            page.click("#settings")
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
            page.click("#settings")
            page.click("#alertdone")
            page.wait_for_function("document.getElementById('alertdone').checked")

            ws.append_event(conftest.event("Stop", ts=now + 1))
            daemon.tick()
            page.wait_for_function("window.__told.length === 1")
            assert "has finished" in page.evaluate("window.__told")[0][0]
        finally:
            browser.close()


def test_an_alert_names_the_session_as_its_row_does(ws, page_at):
    """The row and the tab's title name a session by `rowName`: the reader's
    name, or else where it stands. The alerts used `label`, which leads with
    the title Claude Code writes from the first prompt -- a title `/rename`
    never reaches -- so the alert named a session the list did not."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = alerts_page(play, path)
        try:
            page.wait_for_function("state.sessions.length === 1")
            page.click("#settings")
            page.click("#alertdone")
            page.wait_for_function("document.getElementById('alertdone').checked")
            now = time.time()
            ws.append_event(conftest.event("UserPromptSubmit", prompt="go", ts=now))
            daemon.tick()
            page.wait_for_function("state.sessions[0].state === 'working'")
            ws.append_event(conftest.event("Stop", ts=now + 1))
            daemon.tick()
            page.wait_for_function("window.__told.length === 1")
            ws.append_event(conftest.event(
                "PermissionRequest", tool_name="Bash",
                tool_input={"command": "rm -rf build"}, ts=now + 2))
            daemon.tick()
            page.wait_for_function("window.__told.length === 2")
            name = page.evaluate("rowName(state.sessions[0])")
            titles = [one[0] for one in page.evaluate("window.__told")]
            assert titles == [name + " has finished", name + " needs you"], titles
            # The fixture's status line names it; that name is not the row's.
            assert not any("A session" in one for one in titles), titles
        finally:
            browser.close()


def test_the_two_switches_are_remembered_apart(page_at, ws):
    _, path = page_at
    with sync_playwright() as play:
        browser, page = alerts_page(play, path)
        try:
            page.click("#settings")
            page.click("#alertneeds")      # off, from its default on
            page.click("#alertdone")       # on
            page.wait_for_function(
                """() => !document.getElementById('alertneeds').checked
                      && document.getElementById('alertdone').checked""")
            kept(ws, "alerts", {"needs": False, "done": True})
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector(".row")
            page.click("#settings")
            page.wait_for_selector("#setpop", state="visible")
            assert not page.is_checked("#alertneeds")
            assert page.is_checked("#alertdone")
        finally:
            browser.close()


def test_two_quick_changes_reach_the_file_in_the_order_they_were_made(
        page_at, ws):
    """Each change was its own POST on its own connection, and the first
    could land after the second: the file kept the older choice, and the
    push put it back on the page. `test_the_two_switches_are_remembered_apart`
    went red that way under load. `keepSetting` sends one at a time now."""
    _, path = page_at
    with sync_playwright() as play:
        browser, page = alerts_page(play, path)
        try:
            sent = []
            page.on("request", lambda one: sent.append(one.post_data)
                    if one.url.endswith("/api/settings") else None)
            held = hold(page, "**/api/settings")
            page.click("#settings")
            page.click("#alertneeds")      # off, from its default on
            page.click("#alertdone")       # on
            wait_until(page, lambda: held)
            page.wait_for_timeout(300)     # proving the second did not go
            assert len(sent) == 1, sent
            # Through Playwright, which lets the route pass the second on:
            # `kept` polls the file from Python, and nothing routes then.
            with page.expect_response(
                    lambda answer: answer.url.endswith("/api/settings")
                    and '"done":true' in (answer.request.post_data or "")):
                held[0].continue_()
            assert len(sent) == 2, sent
            kept(ws, "alerts", {"needs": False, "done": True})
        finally:
            browser.close()


def test_the_alert_panel_shuts_from_anywhere(page_at):
    """A panel only its own button can close is a panel you have to go back
    to."""
    _, path = page_at
    with sync_playwright() as play:
        browser, page = alerts_page(play, path)
        try:
            for shut in ("body click", "escape", "the button"):
                page.click("#settings")
                page.wait_for_selector("#setpop", state="visible")
                if shut == "body click":
                    page.mouse.click(700, 500)
                elif shut == "escape":
                    page.keyboard.press("Escape")
                else:
                    page.click("#settings")
                page.wait_for_selector("#setpop", state="hidden")
                assert page.get_attribute("#settings", "aria-expanded") == "false", shut
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
            page.click("#settings")
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
            # No more than the daemon keeps: a longer paste reached it (#235).
            assert box.evaluate("b => b.maxLength") == ws.NAME_MAX
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



def test_the_enter_that_ends_a_composition_keeps_no_name(rows_at):
    """The Enter that picks a word in an input method is the input
    method's. Taken as the reader's, it kept half a name."""
    daemon, _, _ = rows_at
    with sync_playwright() as play:
        browser, page = open_rows(play, rows_at)
        try:
            page.dblclick('.row[data-id="fresh"] .name')
            page.fill('.row[data-id="fresh"] input.rowname', "\u65e5\u672c")
            for how in ("composing", "safari"):
                page.evaluate("""([box, how]) => {
                  const press = new KeyboardEvent('keydown', {key: 'Enter',
                    bubbles: true, cancelable: true,
                    isComposing: how === 'composing'});
                  if (how === 'safari') {
                    Object.defineProperty(press, 'keyCode', {value: 229});
                  }
                  document.querySelector(box).dispatchEvent(press);
                }""", ['.row[data-id="fresh"] input.rowname', how])
            page.wait_for_timeout(300)          # proving nothing was kept
            assert "fresh" not in daemon.store.names
            assert page.locator('.row[data-id="fresh"] input.rowname').count() == 1
            page.keyboard.press("Enter")
            page.wait_for_function(
                """document.querySelector('.row[data-id="fresh"] .name')
                   .textContent === '\u65e5\u672c'""")
        finally:
            browser.close()


def test_a_ticket_in_a_rows_name_or_branch_is_a_link(rows_at, ws):
    """A branch is most often named after its ticket, and so is a session
    reviewing a pull request. The ticket links make both links, as they do
    in the transcript. The row is filled again on every push, so a link must
    outlive a push that does not change it -- one rebuilt between the press
    and the release is a click that never happens -- and a click on it
    opens the ticket and chooses nothing."""
    daemon, url, places = rows_at
    daemon.store.rename("named", "review PR #58")
    daemon.store.refresh()
    with sync_playwright() as play:
        context = fresh_context(play)
        context.add_init_script("localStorage.setItem('wostuast-history', 'open')")
        # The links arrive after the last push -- the reader adds one in the
        # menu -- so the rows have to be filled again when they come, and no
        # push of the sessions will do it. The last push is the one a stream
        # opens with once a session is chosen.
        context.add_init_script("""
          const add = EventSource.prototype.addEventListener;
          EventSource.prototype.addEventListener = function (name, fn, ...rest) {
            if (name !== 'sessions' || !this.url.includes('watch=')) {
              return add.call(this, name, fn, ...rest);
            }
            return add.call(this, name, (message) => {
              fn(message);
              window.watchedPush = true;
            }, ...rest);
          };""")
        context.route("https://*.example/**", lambda route: route.abort())
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_function(
                "document.querySelectorAll('.row').length === 4")
            page.wait_for_function("window.watchedPush === true")
            ws.save_config({"links": [
                {"match": r"(OA)-(\d+)",
                 "url": "https://tickets.example/browse/$1-$2"},
                {"match": r"PR #(\d+)", "url": "https://code.example/pull/$1"},
            ]})
            daemon.tell_config()
            named = '.row[data-id="named"]'
            page.wait_for_selector(named + " .branch a.ticket")
            seen = page.eval_on_selector_all(
                named + " a.ticket",
                "els => els.map((one) => [one.textContent, one.href, one.target])")
            assert seen == [
                ["PR #58", "https://code.example/pull/58", "_blank"],
                ["OA-74380", "https://tickets.example/browse/OA-74380", "_blank"],
            ], seen
            assert page.inner_text(named + " .line1 .name") == "review PR #58"
            assert page.inner_text(named + " .branch") == LONG_BRANCH

            # A push that fills the row again leaves both links where they
            # stand.
            page.evaluate(f"""() => {{
              window.links = [...document.querySelectorAll(
                '{named} a.ticket')];
            }}""")
            ws.append_event(conftest.event(
                "PermissionRequest", sid="named", cwd=str(places["named"]),
                tool_name="Bash", tool_input={"command": "make check"},
                ts=time.time()))
            daemon.tick()
            page.wait_for_function(
                f"""document.querySelector('{named} .said')
                   .textContent.includes('make check')""")
            assert page.evaluate(
                "window.links.map((one) => one.isConnected)") == [True, True]

            # A click on a link opens the ticket and chooses nothing.
            page.click('.row[data-id="fresh"]')
            page.wait_for_function("state.chosen === 'fresh'")
            with context.expect_page():
                page.click(named + " .branch a.ticket")
            page.wait_for_timeout(300)          # proving nothing was chosen
            assert page.evaluate("state.chosen") == "fresh"

            # A rename edits the name as text, and the link comes back after.
            page.bring_to_front()
            page.click(named, position={"x": 5, "y": 5})
            page.wait_for_function("state.chosen === 'named'")
            page.keyboard.press("e")
            box = page.locator(named + " input.rowname")
            assert box.input_value() == "review PR #58"
            page.keyboard.press("Escape")
            page.wait_for_selector(named + " .line1 .name a.ticket")
            assert page.inner_text(named + " .line1 .name") == "review PR #58"

            # A link changed in the menu, as many links as before: the rows
            # follow it. Keyed on the count, they kept the old address.
            ws.save_config({"links": [
                {"match": r"(OA)-(\d+)",
                 "url": "https://tickets.example/browse/$1-$2"},
                {"match": r"PR #(\d+)", "url": "https://code.example/pr/$1"},
            ]})
            daemon.tell_config()
            page.wait_for_function(f"""document.querySelector(
              '{named} .line1 .name a.ticket').href
              === 'https://code.example/pr/58'""")
        finally:
            context.close()


def clear_into_s2(ws, daemon, tmp_path, transcript_file):
    """What a `/clear` in s1's pane writes: s1 ends, s2 starts with a
    transcript of its own, in the same pane and the same process."""
    path = transcript_file("s2", [conftest.record("you", "after the clear")])
    now = time.time()
    ws.append_event(conftest.event("SessionEnd", sid="s1", cwd=str(tmp_path),
                                   pane="%7", pid=1, reason="clear", ts=now))
    ws.append_event(conftest.event("SessionStart", sid="s2", cwd=str(tmp_path),
                                   pane="%7", pid=1, source="clear",
                                   transcript_path=str(path), ts=now + 0.1))
    daemon.tick()


def test_a_clear_is_followed_and_a_reload_stays_on_it(page_at, ws, tmp_path,
                                                      transcript_file):
    """The reader typed `/clear` and the page stayed on the session it had
    ended, with the old transcript; a reload then opened on the first row,
    the new one, and the old conversation seemed gone. The page follows the
    `/clear` into the new session, and the address names the session on
    screen, so a reload comes back to it."""
    daemon, _ = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            assert page.evaluate("location.hash") == "#s1"
            clear_into_s2(ws, daemon, tmp_path, transcript_file)
            page.wait_for_function("state.chosen === 's2'")
            page.wait_for_function(
                "document.querySelector('.turnbody')?.innerText"
                ".includes('after the clear')")
            assert page.evaluate("location.hash") == "#s2"
            page.reload()
            page.wait_for_function("state.chosen === 's2' && state.turns.landed")
            assert "after the clear" in page.locator(".turnbody").inner_text()
        finally:
            browser.close()


def test_a_reader_who_goes_back_to_a_cleared_session_stays_there(
        page_at, ws, tmp_path, transcript_file):
    """Followed once, when the link appears. The old conversation is still
    worth reading, and a page that sent the reader on again on every push
    would make it unreadable. Nor is a link that was there before the page
    opened followed: nobody cleared anything under the reader's eyes."""
    daemon, _ = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            clear_into_s2(ws, daemon, tmp_path, transcript_file)
            page.wait_for_function("state.chosen === 's2'")
            page.evaluate("choose('s1')")
            ws.append_event(conftest.event("UserPromptSubmit", sid="s2",
                                           cwd=str(tmp_path), pane="%7", pid=1,
                                           prompt="more", ts=time.time() + 1))
            daemon.tick()
            page.wait_for_function(
                "state.sessions.find(s => s.id === 's2').state === 'working'")
            assert page.evaluate("state.chosen") == "s1"
        finally:
            browser.close()
        browser, page = open_page(play, page_at, wait="frame")
        try:
            page.goto(page.url.split("#")[0] + "#s1")
            page.reload()
            page.wait_for_function("state.chosen === 's1' && state.sessions.length === 2")
            page.wait_for_timeout(300)     # proving nothing moves
            assert page.evaluate("state.chosen") == "s1"
        finally:
            browser.close()


def test_the_keys_nobody_pressed_are_gone(pair_at):
    """`j` `k` walked the list, `n` went to the next session that needs
    you, `r` opened the review and `t` showed thinking. The reader used
    none of them, and a line in `?` for each hid the keys they do use.
    Pressed now, they change nothing and say nothing, and `?` lists none
    of them."""
    with sync_playwright() as play:
        browser, page = open_page(play, pair_at)
        try:
            two_rows(page)
            spy_on_note(page)
            before = page.evaluate("[state.chosen, state.tab]")
            for key in ("j", "k", "n", "r", "t", "j"):
                page.press("body", key)
            assert page.evaluate("[state.chosen, state.tab]") == before
            assert page.evaluate("window.__said") == []
            page.press("body", "?")
            listed = page.eval_on_selector_all(
                "#help dt", "els => els.map((one) => one.textContent.trim())")
            assert "s" in listed and "1 – 3" in listed, listed
            for gone in ("j / k", "n", "r", "t"):
                assert gone not in listed, listed
        finally:
            browser.close()
