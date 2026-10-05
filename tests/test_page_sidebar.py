"""The session list: state, filter, counts and history.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations

import json
from pathlib import Path
from contextlib import contextmanager
import time

import pytest

import conftest
from browser import (
    hold,
    renew_stream,
    pixels,
    kept,
    spy_on_note,
    skip_without_browser,
    opened,
    own_context,
    show_tab,
    two_rows,
    wait_for_watching,
    wait_until,
)

pytestmark = skip_without_browser

def test_a_row_is_not_rebuilt_every_second(page_at, ws, tmp_path):
    """The ages advance once a second. Rebuilding the rows to do it restarted
    the needs-you pulse before it could finish a cycle, and threw away the
    row's colour transition. Only the age text may change."""
    daemon, _ = page_at
    with opened(page_at) as page:
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


def test_a_row_is_kept_when_the_state_changes(page_at, ws):
    """A row that changes state fades into its new colour (CLAUDE.md,
    **Motion**). A fade needs the same row on both sides of the change, and
    the sidebar used to be rebuilt whole, so the one change the fade is for
    was the one that threw it away."""
    daemon, path = page_at
    with opened(path) as page:
        page.evaluate("window.__dot = document.querySelector('.row')")
        assert "done" in page.evaluate("window.__dot.className")
        ws.append_event(conftest.event(
            "PermissionRequest", tool_name="Bash",
            tool_input={"command": "ls ~"}, ts=time.time()))
        daemon.tick()            # fold it, and tell the page
        page.wait_for_function("window.__dot.className.includes('needs_you')")
        assert page.evaluate("window.__dot.isConnected"), "the row was rebuilt"


def test_a_row_shows_its_state_in_its_colour(page_at):
    """The row's edge and tint say the state, and there is no dot and no
    word beside them: nine sessions are hard to read from one small dot."""
    with opened(page_at) as page:
        row = page.locator(".row").first
        edge = page.evaluate(
            "getComputedStyle(document.querySelector('.row')).borderLeftColor")
        # The tint is asked of the row itself: the chosen row wears its
        # state's colour mixed into its fade instead (#396).
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
        if look["chosen"]:
            assert look["image"].startswith("linear-gradient"), look
            assert "rgba(0, 0, 0, 0)" not in look["image"].split(" 55%")[0], look
        else:
            assert look["tint"] in look["face"], "the row is not tinted by its state"


def test_the_sidebar_filter_narrows_the_list(pair_at):
    """One story on one page: type letters, type nonsense, press Escape."""
    with opened(pair_at) as page:
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


def test_a_hidden_session_still_counts(pair_at, ws):
    """The title, the icon and the alerts are about every session. They used to
    be drawn after the guard that asks whether the shown rows had changed, so
    with anything typed in the filter, a session you could not see going amber
    changed nothing anywhere on the page."""
    daemon, path = pair_at
    with opened(path) as page:
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


def test_the_session_list_ends_with_its_rows(page_at):
    """A strip of keys stood under the rows and said, in two cramped lines,
    what ? says in full. The reader found it odd and never needed it, so the
    list ends with its last row."""
    with opened(page_at) as page:
        assert page.evaluate(
            "document.querySelector('.sidebar').lastElementChild.id") == "rows"


def test_f_puts_the_cursor_in_the_session_filter(page_at):
    with opened(page_at) as page:
        page.press("body", "f")
        assert page.evaluate("document.activeElement.id") == "pick"
        # And typing in it commands nothing: the tab must not change.
        page.press("#pick", "2")
        assert page.evaluate("state.tab") == "transcript"


def test_the_chosen_row_is_still_obvious(page_at):
    with opened(page_at) as page:
        assert page.locator(".row.chosen").count() == 1


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
    fade: look.backgroundImage, content: beside,
    line: look.borderTopColor, hue: look.borderLeftColor,
    edgeWidth: look.borderLeftWidth, otherEdge: other.borderLeftWidth,
    otherLine: other.borderTopColor,
    textAt: Math.round(row.querySelector('.name').getBoundingClientRect().left),
    otherTextAt: Math.round(document.querySelector('.row:not(.chosen) .name')
      .getBoundingClientRect().left),
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
    with open_rows(rows_at) as page:
        page.set_viewport_size({"width": 1100, "height": 420})
        page.click('.row[data-id="fresh"]', position={"x": 5, "y": 5})
        page.wait_for_function("state.chosen === 'fresh'")
        # Off the row: its hover draws a line of its own, which stood in
        # for the chosen row's when the chosen one was taken away.
        page.mouse.move(900, 300)
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
        # Its outline is as wide as the other rows' own, so it does not
        # move, and in its state's colour, not the list's: a line in the
        # list's colour could not be seen, and cut the corner of its edge.
        assert [seen["top"], seen["bottom"]] == seen["others"], seen
        # The strongest row in the list (#396): it starts in its state's
        # colour, not in nothing, and a line in that colour runs round it,
        # where the others have none. Its edge is wider, and its text
        # stands where it would have stood.
        assert "transparent" not in seen["fade"]
        assert "rgba(0, 0, 0, 0)" not in seen["fade"].split(" 55%")[0], seen
        assert seen["line"] != seen["otherLine"] == "rgba(0, 0, 0, 0)", seen
        assert seen["edgeWidth"] == "6px" and seen["otherEdge"] == "4px", seen
        assert seen["textAt"] - seen["otherTextAt"] == seen["indent"], seen
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
    with opened(page_at) as page:
        seen = page.evaluate(TAB_ICON_PIXELS, "#e37400")
        amber = [0xe3, 0x74, 0x00, 255]
        assert seen["body"] == amber and seen["chin"] == amber, seen
        assert seen["antenna"] == amber, seen
        # The big eye reaches where the small one's side does not.
        assert seen["big"][3] == 0 and seen["small"][3] == 0, seen
        assert seen["beside"] == amber, seen
        assert seen["mouth"][3] == 0 and seen["corner"][3] == 0, seen
        assert seen["outside"][3] == 0, seen


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
    with opened(path) as page:
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
    with opened(page_at) as page:
        for rows, want in cases:
            said = page.evaluate("""(rows) => tabTitle(rows.map(
              ([id, state, name]) => ({id, state, name, mine: true})))""",
              rows)
            assert said == want, (rows, said)


def test_the_tab_says_what_is_happening(page_at):
    with opened(page_at) as page:
        assert page.title() == "1 ready \u00b7 wostuast"   # one quiet session
        icon = page.evaluate(
            "document.querySelector(\"link[rel='icon']\")?.getAttribute('href') || ''")
        assert icon.startswith("data:image/png"), "no icon was drawn"


def test_alerts_are_off_until_you_ask(page_at):
    """A page that asked for notification permission on load would be rude, and
    browsers punish it."""
    with opened(page_at) as page:
        assert page.get_attribute("#settings", "data-alerts") == "off"
        # Said on the button, as the crossed-out bell used to say it.
        assert page.locator("#settings .offmark").is_visible()
        assert page.evaluate("Notification.permission") != "granted"


def test_the_history_bar_goes_when_the_filter_leaves_nothing_to_fold(past_at):
    """The bar is made once and kept between draws, so a draw with nothing
    under it has to take it away. `barPlaced` started as `!past.length`, which
    is true in exactly the case that needs the removal — so the bar stayed,
    over nothing, still clickable, saying how many sessions it was not
    holding."""
    with opened(past_at) as page:
        page.wait_for_selector(".histhead")
        page.fill("#pick", "session")       # what the live one is called
        page.wait_for_function(
            "document.querySelectorAll('.histhead').length === 0")
        page.press("#pick", "Escape")
        page.wait_for_selector(".histhead")  # and it comes back


def test_finished_sessions_are_folded_away_under_history(past_at):
    with opened(past_at) as page:
        page.wait_for_selector(".histhead")
        assert page.locator(".row").count() == 1, "only the live one is listed"
        assert "2" in page.locator(".histhead").inner_text()
        # It is the last thing in the list, under the live sessions.
        assert page.evaluate(
            "document.getElementById('rows').lastElementChild"
            ".classList.contains('histhead')")
        # And they are still counted: the fold is not a filter.
        assert page.evaluate("state.sessions.length") == 3


def test_history_opens_and_is_remembered(past_at):
    with own_context() as browser:
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


def test_a_finished_row_is_grey(past_at):
    with opened(past_at) as page:
        page.click(".histhead")
        page.wait_for_selector(".row.ended")
        colours = page.evaluate("""() => {
          const live = document.querySelector(".row:not(.ended) .name");
          const past = document.querySelector(".row.ended .name");
          return [getComputedStyle(live).color, getComputedStyle(past).color];
        }""")
        assert colours[0] != colours[1], "a finished session looks live"


def test_the_filter_searches_the_history_too(past_at):
    """A search that cannot see half the sessions gives a wrong answer that
    looks like a right one."""
    with opened(past_at) as page:
        page.wait_for_selector(".histhead")
        page.fill("#pick", "acorn")
        page.wait_for_function("document.querySelectorAll('.row').length === 1")
        assert "acorn" in page.locator(".row .name").inner_text()






def test_the_chosen_row_turns_into_the_content_s_edge(rows_at):
    """Where the chosen row meets the content, its outline turns into the
    content's edge with a round corner and runs on along that edge (#407):
    it stopped square at the end of the list. Read from what the page drew,
    because a gradient's shape is in no computed style. With the row scrolled
    out of the list, and the grip is the list's colour again."""
    with open_rows(rows_at) as page:
        page.set_viewport_size({"width": 1100, "height": 600})
        page.mouse.move(900, 300)
        colours = page.evaluate("""() => {
          const root = getComputedStyle(document.documentElement);
          const meet = getComputedStyle(document.querySelector('.body'))
            .getPropertyValue('--meet');
          return ['--edge', meet].map((value) => {
            const probe = document.createElement('div');
            probe.style.background = value.startsWith('--')
              ? root.getPropertyValue(value) : value;
            document.body.appendChild(probe);
            const said = getComputedStyle(probe).backgroundColor;
            probe.remove();
            return said.match(/\\d+/g).slice(0, 3).map(Number);
          });
        }""")
        edge, meet = (tuple(one) for one in colours)
        assert edge != meet

        def grip():
            at = page.evaluate("""() => {
              const grip = document.getElementById('grip').getBoundingClientRect();
              const row = document.querySelector('.row.chosen');
              const at = row ? row.getBoundingClientRect() : {top: 0, bottom: 0};
              return [grip.left, grip.width, Math.floor(at.top), Math.ceil(at.bottom)];
            }""")
            shot = pixels(page.screenshot(clip={"x": at[0], "y": 0, "width": at[1],
                                                "height": 600}))
            return shot, at[2], at[3]

        def near(one, other):
            return all(abs(a - b) <= 3 for a, b in zip(one, other))

        page.click('.row[data-id="fresh"]', position={"x": 5, "y": 5})
        page.wait_for_function("state.chosen === 'fresh'")
        page.mouse.move(900, 300)
        page.wait_for_function(
            "document.querySelector('.row.chosen').getAnimations().length === 0")
        page.evaluate("new Promise((done) => requestAnimationFrame(() => "
                      "requestAnimationFrame(done)))")
        shot, top, bottom = grip()
        last = len(shot[0]) - 1
        # Open beside the row, as before.
        assert all(near(dot, meet) for dot in shot[(top + bottom) // 2]), shot[(top + bottom) // 2]
        # Just over and under it, the corner: the list's colour at the
        # list's side, the content's ground towards the content.
        for y in (top - 2, bottom + 1):
            assert near(shot[y][0], edge), (y, shot[y])
            assert near(shot[y][last], meet), (y, shot[y])
        # Far over and under it, a line down the content's edge, in
        # neither the list's colour nor the content's.
        for y in (top - 30, bottom + 30):
            assert near(shot[y][0], edge), (y, shot[y])
            assert not near(shot[y][last], edge) and not near(shot[y][last], meet), (y, shot[y])
        # Scrolled out of the list, there is no row to turn, and no line.
        page.set_viewport_size({"width": 1100, "height": 250})
        page.evaluate("document.getElementById('rows').scrollTop = 1e6")
        page.wait_for_function("""() => {
          const row = document.querySelector('.row.chosen').getBoundingClientRect();
          const list = document.getElementById('rows').getBoundingClientRect();
          return row.bottom < list.top || row.top > list.bottom;
        }""")
        page.evaluate("new Promise((done) => requestAnimationFrame(() => "
                      "requestAnimationFrame(done)))")
        shot = pixels(page.screenshot(clip={"x": page.evaluate(
            "document.getElementById('grip').getBoundingClientRect().left"), "y": 60,
            "width": 5, "height": 180}))
        assert all(near(dot, edge) for line in shot for dot in line), "a line with no row"


def test_the_outline_keeps_its_colour_when_another_row_is_chosen(rows_at):
    """The line down the content's edge is the chosen row's colour from the
    moment it is chosen (#416). It was copied from the row's computed
    border while the row was still fading into it, so a click left it all
    but transparent, until the next push drew it again."""
    with open_rows(rows_at) as page:
        page.set_viewport_size({"width": 1100, "height": 600})
        page.click('.row[data-id="fresh"]', position={"x": 5, "y": 5})
        page.wait_for_function("state.chosen === 'fresh'")
        page.mouse.move(900, 300)
        page.wait_for_function(
            "document.querySelector('.row.chosen').getAnimations().length === 0")
        for other in ("idle", "fresh"):
            page.click(f'.row[data-id="{other}"]', position={"x": 5, "y": 5})
            page.mouse.move(900, 300)
            page.wait_for_function(f"state.chosen === '{other}'")
            # Settled, and no push since: the line must be the row's own.
            page.wait_for_function(
                "document.querySelector('.row.chosen').getAnimations().length === 0")
            seen = page.evaluate("""() => {
              const probe = document.createElement('div');
              probe.style.color = getComputedStyle(document.getElementById('grip'))
                .getPropertyValue('--gap-line');
              document.body.appendChild(probe);
              const line = getComputedStyle(probe).color;
              probe.remove();
              return [line, getComputedStyle(document.querySelector('.row.chosen')).borderTopColor];
            }""")
            assert seen[0] == seen[1], (other, seen)


def test_a_drag_on_an_edge_starts_only_by_hand_and_always_stops(page_at):
    """A drag started on any button, held no capture, and stopped only on
    `pointerup`. A right-click on the grip opens the context menu on Linux
    and macOS, and the menu takes the `pointerup`: the sidebar then followed
    the mouse with no button held. A touch the browser cancels did the
    same. A headless browser has no context menu, so the test says what the
    drag does at each step rather than waiting for a menu."""
    with opened(page_at) as page:
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


def test_the_chosen_row_is_tinted_all_the_way_down(page_at):
    """It was an inset shadow with a 40 px spread, which fills inward from each
    edge and leaves a stripe of untinted row down the middle of anything taller
    than 80 px. A row carrying a name, a branch and a reason is taller than
    that, so the selected session had a brighter band through its centre.

    A fill must not depend on how tall the row turns out to be.
    """
    with opened(page_at) as page:
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


def test_the_session_filter_forgives_nothing(past_at):
    """The file matcher forgives one missing letter, because a file name is
    long and one wrong character should not hide it. The session haystack is a
    short line of text, and forgiving a letter there matched half the list —
    "acorn" found a session whose worktree merely contained a, c, o and r."""
    with opened(past_at) as page:
        page.wait_for_selector(".histhead")
        strict = page.evaluate("""() => ({
          exact: !!fuzzy("repo/acorn", "acorn"),
          oneLetterShort: !!fuzzy("repo/acor", "acorn"),
          scattered: !!fuzzy("repo/a-c-o-r", "acorn"),
        })""")
        assert strict == {"exact": True, "oneLetterShort": False,
                          "scattered": False}


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
    with opened(path) as page:
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


def test_a_working_agent_is_listed_above_one_waiting_at_its_prompt(ws, pair_at):
    """An agent still going is something you may want to look in on. One
    sitting at its prompt has finished with you. Ready used to come second,
    on the reading that wanting a prompt is nearer to wanting you -- it is
    not, because nothing about it is waiting."""
    daemon, url = pair_at
    with opened(url) as page:
        page.wait_for_function("state.sessions.length === 2")
        assert bands(page) == ["ready \u00b7 2"]

        ws.append_event(conftest.event(
            "UserPromptSubmit", sid="s2", prompt="go", ts=time.time()))
        daemon.tick()
        page.wait_for_function(
            "() => document.querySelectorAll('.rows .band').length === 2")
        assert bands(page) == ["working \u00b7 1", "ready \u00b7 1"]


def test_a_group_with_nothing_in_it_has_no_heading(page_at):
    with opened(page_at) as page:
        page.wait_for_selector(".rows .band")
        assert bands(page) == ["ready · 1"]


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
    with opened(url) as page:
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


def test_an_age_older_than_an_hour_carries_two_units(pair_at):
    """"2d" covers two days to just short of three, which is not an answer to
    "when did this last do something". Drop the second unit and the row says
    "2d" for a session last seen two and a half days ago."""
    _, url = pair_at
    with opened(url) as page:
        said = page.evaluate("""() => {
          const now = Date.now() / 1000 + state.skew;
          return [40, 90, 2 * 3600, 2 * 3600 + 15 * 60,
                  2 * 86400, 2 * 86400 + 6 * 3600]
                   .map((old) => ago(now - old));
        }""")
        assert said == ["40s", "1min", "2h", "2h 15min", "2d", "2d 6h"]


# --- what to be told about ----------------------------------------------------


@contextmanager
def alerts_page(where):
    """A page whose browser has already allowed alerts, and which records
    every one it is handed. A real `Notification` cannot be read back from
    Playwright, so it is replaced before the page's own script runs."""
    with own_context() as browser:
        browser.grant_permissions(["notifications"])
        page = browser.new_page()
        page.add_init_script("""
          window.__told = [];
          window.Notification = function (title, options) {
            window.__told.push([title, (options || {}).body || "", options || {}]);
          };
          window.Notification.permission = "granted";
          window.Notification.requestPermission = async () => "granted";
        """)
        page.goto(where, wait_until="domcontentloaded")
        page.wait_for_selector(".row", timeout=15000)
        page.wait_for_function("!!window.marked", timeout=15000)
        yield page


def test_the_needs_you_alert_is_on_as_soon_as_alerts_are(page_at):
    """It is the one thing this tool exists to tell you, so it is not a
    second choice on top of allowing alerts at all. The finished one is a
    choice, so it is off until it is asked for."""
    _, path = page_at
    with alerts_page(path) as page:
        page.click("#settings")
        page.wait_for_selector("#setpop", state="visible")
        assert page.is_checked("#alertneeds")
        assert not page.is_checked("#alertdone")
        assert page.get_attribute("#settings", "data-alerts") == "on"
        assert page.locator("#settings .offmark").is_hidden()


def test_an_agent_that_needs_you_is_said_once(ws, page_at):
    daemon, path = page_at
    with alerts_page(path) as page:
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


def test_an_alert_that_needs_you_says_what_and_where_and_stays(ws, page_at):
    """It said "Bash rm -rf build needs you" and nothing of where, with no
    picture, and went away on its own (issue 330). It says the permission
    or the question, then the folder and the branch, wears the tab's robot,
    and stays until clicked: it is what this program is for, and one that
    went while the reader was in another room said nothing to them."""
    daemon, path = page_at
    with alerts_page(path) as page:
        page.wait_for_function("state.sessions.length === 1")
        ws.append_event(conftest.event(
            "PermissionRequest", tool_name="Bash",
            tool_input={"command": "rm -rf build"}, ts=time.time()))
        daemon.tick()
        page.wait_for_function("window.__told.length === 1")
        title, body, options = page.evaluate("window.__told")[0]
        where = page.evaluate(
            "state.sessions[0].place + ' · ' + state.sessions[0].branch")
        assert "needs you" in title
        assert body.split("\n") == ["permission: Bash rm -rf build", where], body
        assert options["icon"].startswith("data:image/png;base64,"), options
        assert options["requireInteraction"] is True


def test_a_question_is_said_as_the_question(ws, page_at):
    """The row says "asks: Way", the question's header; an alert says the
    question itself."""
    daemon, path = page_at
    with alerts_page(path) as page:
        page.wait_for_function("state.sessions.length === 1")
        # The two events a real question sends.
        asked = {"questions": [{"question": "Which way?", "header": "Way",
                                "options": [{"label": "left"}]}]}
        now = time.time()
        ws.append_event(conftest.event(
            "PreToolUse", tool_name="AskUserQuestion", tool_input=asked,
            tool_use_id="toolu_q1", ts=now))
        ws.append_event(conftest.event(
            "PermissionRequest", tool_name="AskUserQuestion",
            tool_input=asked, ts=now + 0.1))
        daemon.tick()
        page.wait_for_function("window.__told.length === 1")
        assert page.evaluate("window.__told")[0][1].startswith("Which way?")


def test_a_finished_agent_says_what_it_finished_and_goes(ws, page_at):
    """"ready for you" said nothing of which turn had ended. It says the
    prompt the agent finished -- cut, its secrets hidden, since an alert can
    stand on a locked screen -- and goes away on its own: nothing waits."""
    daemon, path = page_at
    with alerts_page(path) as page:
        page.wait_for_function("state.sessions.length === 1")
        page.click("#settings")
        page.click("#alertdone")
        page.wait_for_function("document.getElementById('alertdone').checked")
        now = time.time()
        ws.append_event(conftest.event(
            "UserPromptSubmit", prompt="fix the login test with TOKEN=abc123xyz",
            ts=now))
        daemon.tick()
        page.wait_for_function(
            "() => state.sessions.some((one) => one.state === 'working')")
        ws.append_event(conftest.event("Stop", ts=now + 1))
        daemon.tick()
        page.wait_for_function("window.__told.length === 1")
        title, body, options = page.evaluate("window.__told")[0]
        assert "has finished" in title
        first = body.split("\n")[0]
        assert first.startswith("fix the login test"), body
        assert "abc123xyz" not in body
        assert options["requireInteraction"] is False


def test_a_finished_agent_is_said_only_when_it_was_working(ws, page_at):
    """"done" is where a session sits between turns, so the news is the moment
    it gets there. A session already finished when the page opened is not
    news, and neither is one this page has never seen working."""
    daemon, path = page_at
    with alerts_page(path) as page:
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


def test_an_alert_switched_on_mid_turn_still_reports_that_turn(ws, page_at):
    """What each session is doing is written down on every pass, whatever the
    switches say. So ticking the box while an agent is working still tells
    you when it stops — and a session that reached "done" while nobody was
    listening is already at "done" rather than a change waiting to be
    announced, which is what stops a backlog arriving at once.

    Record the states only while the switch is on and the alert goes silent
    for exactly the turn the reader switched it on for."""
    daemon, path = page_at
    with alerts_page(path) as page:
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


def test_an_alert_names_the_session_as_its_row_does(ws, page_at):
    """The row and the tab's title name a session by `rowName`, and so do
    the alerts. They used `label`, which led with Claude Code's title while
    the row showed where the session stood, so the alert named a session the
    list did not. Both are Claude Code's name now (#351)."""
    daemon, path = page_at
    with alerts_page(path) as page:
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
        # The fixture's status line names it, and that is the row's name.
        assert name == "A session"


def test_the_two_switches_are_remembered_apart(page_at, ws):
    _, path = page_at
    with alerts_page(path) as page:
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


def test_two_quick_changes_reach_the_file_in_the_order_they_were_made(
        page_at, ws):
    """Each change was its own POST on its own connection, and the first
    could land after the second: the file kept the older choice, and the
    push put it back on the page. `test_the_two_switches_are_remembered_apart`
    went red that way under load. `keepSetting` sends one at a time now."""
    _, path = page_at
    with alerts_page(path) as page:
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


def test_the_alert_panel_shuts_from_anywhere(page_at):
    """A panel only its own button can close is a panel you have to go back
    to."""
    _, path = page_at
    with alerts_page(path) as page:
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


def test_every_alert_makes_itself_heard(page_at):
    """One tag per session, so a second alert replaces the first -- and with
    `renotify` left false a replacement makes no sound and shows no banner.
    An agent that stopped on a second question was never said."""
    _, path = page_at
    with opened(path) as page:
        got = page.evaluate("""() => {
          let options = null;
          window.Notification = function (title, given) { options = given; };
          tellAbout({ id: 's1', label: 'x' }, 'x needs you', 'why');
          return options;
        }""")
        assert got["tag"] == "wostuast-s1" and got["renotify"] is True, got


def test_turning_needs_you_on_brings_no_backlog(ws, page_at):
    """`waiting` was filled only while alerts were not allowed at all, not
    while this one switch was off -- so ticking it again said every session
    that had gone amber meanwhile, as though it had just happened."""
    daemon, path = page_at
    with alerts_page(path) as page:
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
    # The title Claude Code wrote, which the row shows (#351).
    ws.write_status("fresh", ws.Status(ts=now, name="A generated title"))
    daemon.store.rename("named", "rule work")
    daemon.store.refresh()
    return daemon, url, places


@contextmanager
def open_rows(rows_at):
    daemon, url, _ = rows_at
    with own_context() as context:
        context.add_init_script(
            "localStorage.setItem('wostuast-history', 'open')")
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_function(
            "document.querySelectorAll('.row').length === 4")
        yield page


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
    third and a fourth time, and the dot a fifth. A name not given here is
    the one Claude Code shows (#351): the reader asked for one name in both
    places, and a rename on the page reaches it now, by `/rename`."""
    _, _, places = rows_at
    with open_rows(rows_at) as page:
        rows = page.evaluate(READ_ROWS)
        named, fresh = rows["named"], rows["fresh"]
        assert named["name"] == "rule work"
        assert fresh["name"] == "A generated title"
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


def test_the_git_line_is_one_line_and_its_counts_stand_at_the_right(rows_at):
    """A long branch pushed "✓ clean" onto a second line of its own. Only the
    branch gives way now, with an ellipsis, and what git counts stands at the
    right edge, so the counts of every row read as one column."""
    with open_rows(rows_at) as page:
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


def test_a_row_is_renamed_where_it_stands(rows_at, ws):
    """A double-click or `e` edits the name in the row; Enter keeps it and
    Escape does not. The row is filled again on every push and moves when its
    state changes, and neither may take what is being typed."""
    daemon, _, places = rows_at
    with open_rows(rows_at) as page:
        page.dblclick('.row[data-id="fresh"] .name')
        box = page.locator('.row[data-id="fresh"] input.rowname')
        assert box.input_value() == "A generated title"
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
        # would stop following Claude Code's name for good.
        page.keyboard.press("e")
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)          # proving nothing was sent
        assert "idle" not in daemon.store.names



def test_the_enter_that_ends_a_composition_keeps_no_name(rows_at):
    """The Enter that picks a word in an input method is the input
    method's. Taken as the reader's, it kept half a name."""
    daemon, _, _ = rows_at
    with open_rows(rows_at) as page:
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
    with own_context() as context:
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
    with opened(page_at) as page:
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


def test_a_reader_who_goes_back_to_a_cleared_session_stays_there(
        page_at, ws, tmp_path, transcript_file):
    """Followed once, when the link appears. The old conversation is still
    worth reading, and a page that sent the reader on again on every push
    would make it unreadable. Nor is a link that was there before the page
    opened followed: nobody cleared anything under the reader's eyes."""
    daemon, _ = page_at
    with opened(page_at) as page:
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
    with opened(page_at, wait="frame") as page:
        page.goto(page.url.split("#")[0] + "#s1")
        page.reload()
        page.wait_for_function("state.chosen === 's1' && state.sessions.length === 2")
        page.wait_for_timeout(300)     # proving nothing moves
        assert page.evaluate("state.chosen") == "s1"


def test_the_keys_nobody_pressed_are_gone(pair_at):
    """`j` `k` walked the list, `n` went to the next session that needs
    you, `r` opened the review and `t` showed thinking. The reader used
    none of them, and a line in `?` for each hid the keys they do use.
    Pressed now, they change nothing and say nothing, and `?` lists none
    of them."""
    with opened(pair_at) as page:
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
        # Three tabs, and `4` is the Commands view now (#411).
        assert "s" in listed and "1 – 3" in listed and "4" in listed, listed
        for gone in ("j / k", "n", "r", "t"):
            assert gone not in listed, listed


def test_b_goes_back_to_the_session_before_and_again_returns(pair_at):
    """Two agents on related work are read in turns (#354), and the list
    moves under you, so the other one is never where it was."""
    with opened(pair_at) as page:
        page.wait_for_selector(".row[data-id='s2']")
        page.evaluate("choose('s1')")
        page.click(".row[data-id='s2']")
        assert page.evaluate("state.chosen") == "s2"
        page.press("body", "b")
        assert page.evaluate("state.chosen") == "s1"
        page.press("body", "b")
        assert page.evaluate("state.chosen") == "s2"
        # A reload keeps it: per tab, as the chosen session is.
        page.reload()
        page.wait_for_selector(".row[data-id='s1']")
        page.press("body", "b")
        page.wait_for_function("state.chosen === 's1'")


def test_b_says_why_it_cannot_go_back(pair_at):
    """A session the filter hides is not gone to: the reader would land on
    a row they cannot see. Nothing chosen before says so too."""
    with opened(pair_at) as page:
        page.wait_for_selector(".row[data-id='s2']")
        spy_on_note(page)
        page.evaluate("state.before = ''; try { sessionStorage.clear() } catch (e) {}")
        page.press("body", "b")
        assert page.evaluate("window.__said") == ["no session was chosen before this one"]
        page.evaluate("choose('s1')")
        page.click(".row[data-id='s2']")
        page.fill("#pick", "warmhare")
        page.evaluate("document.activeElement.blur()")   # keys go to the page
        page.press("body", "b")
        assert page.evaluate("state.chosen") == "s2"
        assert page.evaluate("window.__said")[-1] == (
            "the session before this one is hidden by the filter")


# --- a snooze (#355) -----------------------------------------------------------


def test_a_snoozed_session_stops_saying_it_needs_you_until_it_asks_again(ws, page_at):
    """`z` on a session that needs you: it moves to the ready ones, in their
    colour, and the tab's title and the alerts leave it out. Every answer to
    "who needs me" asks `needsYou`, so none of them still shouts. A new
    question ends the snooze by itself, and is said again."""
    daemon, path = page_at
    with alerts_page(path) as page:
        page.wait_for_function("state.sessions.length === 1")
        ws.append_event(conftest.event(
            "PermissionRequest", tool_name="Bash",
            tool_input={"command": "rm -rf build"}, ts=time.time()))
        daemon.tick()
        page.wait_for_function("window.__told.length === 1")
        page.wait_for_function("document.title.includes(' asks ')")
        # A moon on the hover, in the age's place (#389), and nothing
        # until then.
        assert not page.is_visible(".row .snooze")
        page.hover(".row")
        assert page.is_visible(".row .snooze svg")
        assert not page.is_visible(".row .age")
        assert page.get_attribute(".row .snooze", "data-icon") == "moon"
        assert page.get_attribute(".row .snooze", "title").startswith("it waits, but not now")

        page.click(".row")
        page.keyboard.press("z")
        page.wait_for_function("state.sessions[0].snoozed === true")
        page.wait_for_function(
            "[...document.querySelectorAll('.rows .band')]"
            ".some((e) => e.textContent.startsWith('ready'))")
        assert bands(page) == ["ready · 1"]
        assert "snoozed" in page.get_attribute(".row", "class")
        assert page.text_content(".row .line1 .word") == "snoozed"
        assert page.get_attribute(".row .snooze", "data-icon") == "sun"
        page.wait_for_function("!document.title.includes(' asks ')")

        # The same wait, said again late: the row changes, and the alert
        # stays quiet, because the session still waits on what it was
        # snoozed on.
        ws.append_event(conftest.event(
            "Notification", notification_type="elicitation_dialog",
            message="still here", ts=time.time()))
        daemon.tick()
        page.wait_for_function(
            "() => state.sessions[0].last_event === 'still here'")
        assert page.evaluate("state.sessions[0].snoozed") is True
        assert page.evaluate("window.__told.length") == 1

        # A new question wakes it, and is said.
        ws.append_event(conftest.event(
            "PermissionRequest", tool_name="Bash",
            tool_input={"command": "rm -rf dist"}, ts=time.time() + 1))
        daemon.tick()
        page.wait_for_function("window.__told.length === 2")
        assert bands(page) == ["needs you · 1"]
        assert page.get_attribute(".row .snooze", "data-icon") == "moon"


def test_z_on_a_session_that_does_not_need_you_says_why(page_at):
    _, path = page_at
    with opened(path) as page:
        spy_on_note(page)
        page.click(".row")
        page.keyboard.press("z")
        page.wait_for_function("window.__said.length > 0")
        assert "only a session that needs you" in page.evaluate("window.__said")[-1]
        assert not page.is_visible(".row .snooze")


def test_a_rename_that_could_not_reach_claude_code_says_so(rows_at):
    """`named` waits on a dialog, so `/rename` is not typed into it, and the
    name is the page's alone until Claude Code's changes (#351). The reader
    asked for one name in both places, so the page says why there are two."""
    daemon, _, _ = rows_at
    with open_rows(rows_at) as page:
        spy_on_note(page)
        page.dblclick('.row[data-id="named"] .name')
        page.keyboard.press("Control+a")
        page.keyboard.type("dialog work")
        page.keyboard.press("Enter")
        page.wait_for_function("window.__said.length > 0")
        said = page.evaluate("window.__said")[-1]
        assert said.startswith("renamed on this page only: ")
        assert "permission dialog" in said
        assert daemon.store.names.get("named") == "dialog work"



# --- unread (#373) ------------------------------------------------------------


def unread_of(page, sid):
    return page.evaluate(
        f"(state.sessions.find((s) => s.id === '{sid}') || {{}}).unread")


def test_a_turn_that_ends_off_screen_is_unread_until_it_is_opened(ws, pair_at):
    """The session on screen is read as it ends; the other one is marked
    with a dot, named in the tab's title, and read once it is opened."""
    daemon, url = pair_at
    with opened(url) as page:
        two_rows(page)
        page.click('.row[data-id="s1"]')
        page.wait_for_function("state.chosen === 's1'")
        now = time.time()
        ws.append_event(conftest.event("Stop", sid="s1", ts=now + 1))
        ws.append_event(conftest.event("Stop", sid="s2", ts=now + 1))
        daemon.tick()
        page.wait_for_selector('.row.unread[data-id="s2"]')
        assert "unread" not in page.get_attribute('.row[data-id="s1"]', "class")
        page.wait_for_function("document.title.startsWith('1 unread')")
        # The dot is drawn: a class nothing paints is not a mark.
        dot = page.evaluate("""(() => { const it = getComputedStyle(
          document.querySelector('.row[data-id="s2"] .name'), '::before');
          return [it.content, it.width]; })()""")
        assert dot == ['""', "8px"], dot
        # And its name is bold, where a read one is not (#390): s1 is read
        # but chosen, so bold too, until s2 is chosen.
        weight = "(id) => getComputedStyle(document.querySelector(`.row[data-id=\"${id}\"] .name`)).fontWeight"
        assert page.evaluate(weight, "s2") == "600"
        page.click('.row[data-id="s2"]')
        page.wait_for_selector('.row[data-id="s2"]:not(.unread)')
        assert page.evaluate(weight, "s2") == "600"   # chosen
        deadline = time.time() + 10
        while daemon.store.sessions["s2"].unread and time.time() < deadline:
            daemon.store.refresh()
            time.sleep(0.05)
        assert not daemon.store.sessions["s2"].unread
        # A push already on its way may carry the row from before; the next
        # pass sends the one after, and the title follows it.
        daemon.tick()
        page.wait_for_function("!document.title.startsWith('1 unread')")
        # s1 is neither chosen nor unread now, and its name is quiet. Only
        # after that pass: the push on its way could carry s1 unread, from
        # before the page read it, and a look then found it bold under load.
        page.wait_for_function(f"({weight})('s1') === '500'")


def test_u_marks_the_session_on_screen_unread_until_another_is_chosen(ws, pair_at):
    """Marked unread while looking at it, it stays unread -- the point of
    the mark -- and is read when the reader comes back to it."""
    daemon, url = pair_at
    with opened(url) as page:
        two_rows(page)
        page.click('.row[data-id="s1"]')
        page.wait_for_function("state.chosen === 's1'")
        page.keyboard.press("u")
        deadline = time.time() + 10
        while daemon.store.sessions["s1"].seen_at >= 0 and time.time() < deadline:
            time.sleep(0.05)
        daemon.tick()          # the pass that sends the row built after it
        page.wait_for_selector('.row.unread[data-id="s1"]')
        # Pushes come and go while it stays on screen; it stays unread.
        ws.append_event(conftest.event("Notification", sid="s1",
                                       notification_type="idle_prompt",
                                       message="waiting", ts=time.time()))
        daemon.tick()
        page.wait_for_timeout(600)       # proving it did not go
        assert unread_of(page, "s1") is True
        assert daemon.store.sessions["s1"].seen_at < 0
        page.click('.row[data-id="s2"]')
        page.wait_for_function("state.chosen === 's2'")
        assert unread_of(page, "s1") is True
        page.click('.row[data-id="s1"]')
        page.wait_for_selector('.row[data-id="s1"]:not(.unread)')


def test_the_row_offers_unread_on_a_read_row_only(ws, pair_at):
    daemon, url = pair_at
    with opened(url) as page:
        two_rows(page)
        page.click('.row[data-id="s1"]')
        page.wait_for_function("state.chosen === 's1'")
        mark = '.row[data-id="s2"] .markunread'
        # Not there until the hover: invisible, it took the name's room.
        assert page.evaluate(f"document.querySelector('{mark}').offsetWidth") == 0
        # The hover's icons take the age's place, and the row keeps its
        # height and its name's room (#389): as words they cut the name
        # short, and "not now" broke over two lines.
        size = """() => { const row = document.querySelector('.row[data-id="s2"]');
          return [row.offsetHeight, row.querySelector('.name').offsetWidth]; }"""
        before = page.evaluate(size)
        page.hover('.row[data-id="s2"]')
        assert page.locator(mark).is_visible()
        assert page.locator(f"{mark} svg").is_visible()
        assert page.locator('.row[data-id="s2"] .remindlater svg').is_visible()
        assert not page.is_visible('.row[data-id="s2"] .age')
        after = page.evaluate(size)
        assert after[0] == before[0], (before, after)
        # Two icons where "3s" was: a little of the name's room, where the
        # words "later" and "unread" took nearly twice as much.
        assert before[1] - after[1] <= 60, (before, after)
        page.click(mark)
        page.wait_for_selector('.row.unread[data-id="s2"]')
        assert page.locator(mark).is_hidden()
        assert page.evaluate("state.chosen") == "s1"   # not a choice of the row


def test_a_mark_the_daemon_refused_is_taken_back_and_said(ws, pair_at):
    """The row changes at once, before the answer. When the answer is a
    refusal, the dot goes again and the page says why: a dot for a mark
    the file never got was the bug."""
    daemon, url = pair_at
    with opened(url) as page:
        two_rows(page)
        page.click('.row[data-id="s1"]')
        page.wait_for_function("state.chosen === 's1'")
        page.route("**/api/session/s1/seen", lambda route: route.fulfill(
            status=409, content_type="application/json",
            body='{"id": "s1", "error": "refused here"}'))
        page.keyboard.press("u")
        page.wait_for_function("state.trouble === 'refused here'")
        assert unread_of(page, "s1") is False
        assert "unread" not in page.get_attribute('.row[data-id="s1"]', "class")
        assert page.evaluate("state.keptUnread") is None



# --- reminders (#375) ---------------------------------------------------------


def test_a_reminder_puts_a_waiting_session_aside_until_it_comes(ws, page_at):
    """Until its moment, a session that waits stands with the ready ones,
    and says when it comes back; then it needs you again, by the page's own
    clock -- no event comes -- and the alert rings."""
    daemon, path = page_at
    ws.append_event(conftest.event("PermissionRequest", tool_name="Bash",
                                   tool_input={"command": "make"}, ts=time.time()))
    daemon.store.refresh()
    # Far off first: 3 s from now was gone before a loaded machine had
    # drawn the page, and the reminder had come by the first look.
    daemon.store.remind("s1", time.time() + 3600)
    daemon.tick()
    with alerts_page(path) as page:
        page.wait_for_function("state.sessions[0].remind_at > 0")
        assert bands(page) == ["ready · 1"]
        # A clock and the time say it is a reminder (#394), and they stay
        # on the hover: they say when the row comes back.
        assert page.is_visible(".row .age.when svg")
        assert ":" in page.text_content(".row .age")
        page.hover(".row")
        assert page.is_visible(".row .age.when")
        assert page.get_attribute(".row .remindlater", "data-icon") == "clockOff"
        assert "snoozed" in page.get_attribute(".row", "class")
        assert page.evaluate("window.__told.length") == 0
        # Then near: the push sets the page's timer again.
        daemon.store.remind("s1", time.time() + 1)
        daemon.tick()
        page.wait_for_function("window.__told.length === 1", timeout=15000)
        assert bands(page) == ["needs you · 1"]
        assert "snoozed" not in page.get_attribute(".row", "class")


def test_a_reminder_brings_a_ready_session_back_until_it_is_opened(ws, pair_at):
    """A session waiting for nothing comes back too, which a snooze cannot
    do: amber, with the word, and the alert says it is the reminder. Opening
    it ends the reminder."""
    daemon, url = pair_at
    with alerts_page(url) as page:
        two_rows(page)
        page.click('.row[data-id="s1"]')
        page.wait_for_function("state.chosen === 's1'")
        daemon.store.remind("s2", time.time() + 2)
        daemon.tick()
        page.wait_for_selector('.row.reminded[data-id="s2"]', timeout=15000)
        assert page.text_content('.row[data-id="s2"] .line1 .word') == "reminder"
        assert "pill" in page.get_attribute('.row[data-id="s2"] .line1 .word', "class")
        assert bands(page)[0] == "needs you · 1"
        page.wait_for_function("window.__told.length === 1")
        assert page.evaluate("window.__told[0][1]").startswith("the reminder you set")
        page.click('.row[data-id="s2"]')
        deadline = time.time() + 10
        while daemon.store.sessions["s2"].remind_at and time.time() < deadline:
            time.sleep(0.05)
        assert daemon.store.sessions["s2"].remind_at == 0.0
        daemon.tick()
        page.wait_for_selector('.row[data-id="s2"]:not(.reminded)')


def test_later_offers_the_choices_and_keeps_the_one_picked(ws, pair_at):
    daemon, url = pair_at
    with opened(url) as page:
        two_rows(page)
        page.click('.row[data-id="s1"]')
        page.wait_for_function("state.chosen === 's1'")
        row = '.row[data-id="s2"]'
        assert page.evaluate(f"document.querySelector('{row} .remindlater').offsetWidth") == 0
        page.hover(row)
        tall = page.evaluate(f"document.querySelector('{row}').offsetHeight")
        page.click(f"{row} .remindlater")
        # A small menu over the rows below, in whole words (#394): four grey
        # abbreviations in a line of their own were missed.
        words = page.eval_on_selector_all(
            f"{row} .remindmenu button", "els => els.map((e) => e.textContent)")
        # As Slack offers them (#406).
        assert words == ["In 30 minutes", "In 1 hour", "In 3 hours", "Tomorrow at 08:00",
                         "Monday at 08:00", "Custom…"]
        assert page.text_content(f"{row} .remindmenu .menuhead") == "Remind me"
        assert page.evaluate(f"document.querySelector('{row}').offsetHeight") == tall
        # A press between the choices chooses nothing.
        page.click(f"{row} .remindmenu .menuhead")
        assert page.evaluate("state.chosen") == "s1"
        page.click(f"{row} .remindmenu button:text('In 1 hour')")
        page.wait_for_function(
            "state.sessions.find((s) => s.id === 's2').remind_at > 0")
        at = daemon.store.sessions["s2"].remind_at
        assert abs(at - (time.time() + 3600)) < 30, at
        assert page.evaluate("state.chosen") == "s1"     # not a choice of the row
        assert page.is_visible(f"{row} .age.when svg")
        # The mornings, from a clock set to a Monday at 09:00 and to a
        # Sunday at 20:00: tomorrow, and the next Monday that is not today,
        # at eight in the reader's own time. On a Monday that is next
        # week's, more than 7 days on: the daemon takes it.
        mornings = page.evaluate("""() => {
          const kept = state.skew;
          const from = (day, hour) => {
            const at = new Date(2026, 9, day, hour, 0, 0);    // 5 Oct 2026 is a Monday
            state.skew = at.getTime() / 1000 - Date.now() / 1000;
            return ['tomorrow', 'monday'].map((one) => {
              const then = new Date(remindMoment(one) * 1000);
              return [then.getDay(), then.getHours(), then.getMinutes(),
                      Math.round((then - at) / 3600000)];
            });
          };
          const seen = [from(5, 9), from(11, 20)];
          state.skew = kept;
          return seen;
        }""")
        assert mornings == [[[2, 8, 0, 23], [1, 8, 0, 167]],
                            [[1, 8, 0, 12], [1, 8, 0, 12]]], mornings

        # Custom: a day and a time. It stays open when the pointer leaves,
        # a moment past is said, not sent, and Enter sets it.
        page.hover(row)
        page.click(f"{row} .remindlater")       # a set reminder: off again
        page.wait_for_function(
            "state.sessions.find((s) => s.id === 's2').remind_at === 0")
        page.hover(row)
        page.click(f"{row} .remindlater")
        page.click(f"{row} .remindmenu button:text('Custom…')")
        page.wait_for_selector(f"{row} .remindmenu select.remindday")
        # In the page's own words and on a 24-hour clock, whatever the
        # browser's language: its own boxes said "10/05/2026" and "06:00 AM".
        days = page.eval_on_selector_all(f"{row} .remindday option",
                                          "els => els.map((e) => e.textContent)")
        assert days[:2] == ["Today", "Tomorrow"] and len(days) == 31, days
        assert all(len(one.split()) == 3 and one.split()[0] in
                   ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat") for one in days[2:]), days
        assert page.evaluate("document.activeElement.className") == "remindtime"
        shown = page.input_value(f"{row} .remindtime")
        assert len(shown) == 5 and shown.endswith(":00") and 0 <= int(shown[:2]) < 24, shown
        # Over the form first, as a hand goes: the button under the pointer
        # is gone, and a jump from where it stood leaves nothing.
        page.hover(f"{row} .remindset")
        page.mouse.move(900, 500)
        assert page.is_visible(f"{row} .remindtime")
        page.select_option(f"{row} .remindday", "0")
        page.fill(f"{row} .remindtime", "25:00")
        page.click(f"{row} .remindset")
        assert page.text_content(f"{row} .remindwhy") == "Write the time as 22:10."
        page.fill(f"{row} .remindtime", "00:00")
        page.click(f"{row} .remindset")
        assert page.text_content(f"{row} .remindwhy") == "That time has passed."
        assert daemon.store.sessions["s2"].remind_at == 0
        page.select_option(f"{row} .remindday", "3")
        page.fill(f"{row} .remindtime", "1430")
        page.press(f"{row} .remindtime", "Enter")
        page.wait_for_function(
            "state.sessions.find((s) => s.id === 's2').remind_at > 0")
        set_at = page.evaluate("""() => {
            const at = new Date(state.sessions.find((s) => s.id === 's2').remind_at * 1000);
            const want = new Date(serverNow() * 1000);
            want.setDate(want.getDate() + 3);
            return [at.toDateString() === want.toDateString(), at.getHours(), at.getMinutes()]; }""")
        assert set_at == [True, 14, 30], set_at
        assert page.is_hidden(f"{row} .remindmenu")
        assert page.evaluate("state.chosen") == "s1"
        # Escape closes it and sets nothing, and goes no further: over a
        # view, the page's Escape left the view too. A press elsewhere
        # closes it as well.
        page.hover(row)
        page.click(f"{row} .remindlater")
        page.wait_for_function(
            "state.sessions.find((s) => s.id === 's2').remind_at === 0")
        page.click("#savedlink")
        page.wait_for_function("state.feed === 'saved'")
        page.hover(row)
        page.click(f"{row} .remindlater")
        page.click(f"{row} .remindmenu button:text('Custom…')")
        page.press(f"{row} .remindtime", "Escape")
        assert page.is_hidden(f"{row} .remindmenu")
        assert page.evaluate("state.feed") == "saved"
        page.hover(row)
        page.click(f"{row} .remindlater")
        page.click(f"{row} .remindmenu button:text('Custom…')")
        page.mouse.click(900, 500)
        assert page.is_hidden(f"{row} .remindmenu")
        assert daemon.store.sessions["s2"].remind_at == 0




def test_the_four_views_are_one_row_and_always_there(page_at):
    """Unread, Saved, Search and Commands in one row of equal buttons over
    the list (#391, #411), the two counts in badges, a nought grey. Three
    lines in three styles took a hundred pixels, and the first two came and
    went with their counts, which moved the list. **One row at any width
    the list is dragged to**: the icons go first, then the words, and a
    word is never cut to its first letter -- two rows of two were drawn,
    and the reader asked for one."""
    _, path = page_at
    with opened(path) as page:
        page.wait_for_function("document.querySelector('#feedlink .n')")
        look = """() => ['feedlink', 'savedlink', 'searchlink', 'cmdlink'].map((id) => {
          const it = document.getElementById(id);
          const at = it.getBoundingClientRect();
          const n = it.querySelector('.n');
          const word = it.querySelector('.viewname');
          const icon = it.querySelector('svg');
          return {top: Math.round(at.top), width: at.width,
                  word: word.textContent, title: it.title,
                  showsWord: word.offsetWidth > 0 && word.scrollWidth <= word.offsetWidth,
                  showsIcon: !!icon && icon.getBoundingClientRect().width > 0,
                  n: n && n.textContent, none: !!n && n.classList.contains('none'),
                  fits: it.parentNode.scrollWidth <= it.parentNode.clientWidth};
        })"""
        seen = page.evaluate(look)
        assert [one["word"] for one in seen] == ["Unread", "Saved", "Search", "Commands"], seen
        assert [one["n"] for one in seen] == ["0", "0", None, None], seen
        assert seen[0]["none"] and seen[1]["none"], seen
        rows = page.evaluate("document.getElementById('rows').getBoundingClientRect().top")
        assert rows - seen[0]["top"] < 40, (rows, seen)
        shown = {}
        for width in (480, 340, 200):
            page.evaluate(f"document.documentElement.style.setProperty('--sidebar-w', '{width}px')")
            page.wait_for_function(f"document.querySelector('.views').clientWidth < {width}"
                                   f" && document.querySelector('.views').clientWidth > {width - 40}")
            page.wait_for_timeout(100)        # the observer's next frame
            seen = page.evaluate(look)
            assert len({one["top"] for one in seen}) == 1, (width, seen)
            assert max(one["width"] for one in seen) - min(one["width"] for one in seen) < 1, (width, seen)
            assert all(one["fits"] for one in seen), (width, seen)
            # A word is there whole, or not at all; never cut.
            assert len({one["showsWord"] for one in seen}) == 1, (width, seen)
            shown[width] = (seen[0]["showsIcon"], seen[0]["showsWord"])
            # A word that is not shown is in the button's title.
            assert all(one["word"].lower() in one["title"].lower() for one in seen), seen
        assert shown[480] == (True, True), shown
        assert shown[200] == (True, False), shown

# --- all unreads (#376) -------------------------------------------------------


def test_all_unreads_is_one_scroll_through_the_last_answers(ws, pair_at):
    """Coming back from a break: every unread session's last answer, as
    Markdown, newest first, each with "mark read" and "open". Open leaves
    the feed for the session; the tabs come back."""
    daemon, url = pair_at
    with opened(url) as page:
        two_rows(page)
        page.click('.row[data-id="s1"]')
        page.wait_for_function("state.chosen === 's1'")
        now = time.time()
        ws.append_event(conftest.event(
            "Stop", sid="s2", ts=now + 1,
            last_assistant_message="**Done** with the search.\n\n- one\n- two"))
        daemon.tick()
        page.wait_for_function(
            "document.querySelector('#feedlink .n').textContent === '1'")
        assert page.text_content("#feedlink .viewname") == "Unread"
        page.click("#feedlink")
        page.wait_for_selector('.feedentry[data-id="s2"] .prose strong')
        assert page.locator(".feedentry").count() == 1
        assert page.locator('.feedentry[data-id="s2"] .prose li').count() == 2
        assert not page.is_visible(".tabs .tab")
        # The view stands in the tab row (#392): its name, and none of the
        # chosen session's model, context, spend or jump. Shown by force,
        # because a pair with no status line and no pane has none to show.
        assert page.text_content("#viewtitle .viewname") == "All unreads"
        assert page.locator(".feedhead").count() == 0
        assert page.evaluate("""['ctxslot', 'jump'].map((id) => {
          const it = document.getElementById(id); it.hidden = false;
          return getComputedStyle(it).display; })""") == ["none", "none"]
        # A card that reads like its row (#393): the state's colour on its
        # edge, where it stands under its name, and what can be done to it
        # only on its hover.
        card = '.feedentry[data-id="s2"]'
        look = page.evaluate("""(card) => {
          const it = document.querySelector(card);
          const probe = document.createElement('div');
          probe.style.color = 'var(--done)';
          document.body.appendChild(probe);
          const done = getComputedStyle(probe).color;
          probe.remove();
          const s = state.sessions.find((x) => x.id === 's2');
          return {edge: getComputedStyle(it).borderLeftColor, done,
                  where: it.querySelector('.feedwhere').textContent,
                  worktree: s.worktree,
                  open: it.querySelector('.feedtop .link').offsetWidth};
        }""", card)
        assert look["edge"] == look["done"], look
        assert look["worktree"] and look["worktree"] in look["where"], look
        assert look["open"] == 0, look
        page.hover(card)
        assert page.is_visible(f"{card} button:text('open')")
        # Escape leaves it, as the title says, and the tabs come back.
        page.keyboard.press("Escape")
        page.wait_for_function("!state.feed")
        assert page.is_visible(".tabs .tab")
        assert not page.is_visible("#viewtitle")
        page.click("#feedlink")
        page.wait_for_selector(card)
        # Newest first, and a second one comes in while it is open.
        ws.append_event(conftest.event("Stop", sid="s1", ts=now + 2,
                                       last_assistant_message="Second."))
        # s1 is chosen but behind the feed: not read from there.
        daemon.tick()
        page.wait_for_function("document.querySelectorAll('.feedentry').length === 2")
        assert page.eval_on_selector_all(
            ".feedentry", "els => els.map((e) => e.dataset.id)") == ["s1", "s2"]
        page.hover('.feedentry[data-id="s1"]')
        page.click('.feedentry[data-id="s1"] button:text("mark read")')
        page.wait_for_function("document.querySelectorAll('.feedentry').length === 1")
        # A press anywhere on the card opens it, as "open" does.
        page.click('.feedentry[data-id="s2"] .prose li')
        page.wait_for_function("state.chosen === 's2' && !state.feed")
        assert page.is_visible(".tabs .tab")
        page.wait_for_selector('.row[data-id="s2"]:not(.unread)')


def test_what_a_session_started_stands_under_its_row(ws, page_at, tmp_path):
    """A `claude -p` an agent ran, and its Agent tool's subagents, are lines
    under its row (#422), never rows of their own: they came and went in a
    second, and nothing said whose they were. One that ended is folded into
    "1 subagent ran", and counts nowhere -- not in the tab's title, not as
    unread. A child session's line opens its transcript."""
    daemon, url = page_at
    now = time.time()
    by = {"cwd": str(tmp_path), "pane": "", "pid": 5000, "started_by": 1}
    ws.append_event(conftest.event("SessionStart", sid="kid", ts=now, **by))
    ws.append_event(conftest.event("UserPromptSubmit", sid="kid", prompt="Summarise the log",
                                   ts=now, **by))
    for name in ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"):
        ws.append_event(conftest.event(name, sid="over", prompt="Review the diff", ts=now, **by))
    # A subagent runs on after its session's turn has ended (measured).
    agent = {"cwd": str(tmp_path), "pane": "%7", "pid": 1, "ts": now}
    ws.append_event(conftest.event("PreToolUse", tool_name="Agent",
                                   tool_input={"description": "Compare the maps"}, **agent))
    ws.append_event(conftest.event("SubagentStart", agent_id="a1", agent_type="Explore",
                                   **agent))
    ws.append_event(conftest.event("PreToolUse", agent_id="a1", agent_type="Explore",
                                   tool_name="Bash", tool_input={"command": "make bench"},
                                   **agent))
    ws.append_event(conftest.event("Stop", **agent))
    # A child that may need the reader is a row: one waiting on a dialog,
    # and one still working under a parent that is over.
    ws.append_event(conftest.event("SessionStart", sid="asks", ts=now, **by))
    ws.append_event(conftest.event("PermissionRequest", sid="asks", tool_name="Bash",
                                   tool_input={"command": "rm -r build"}, ts=now, **by))
    gone = {"cwd": str(tmp_path), "pane": "", "ts": now}
    ws.append_event(conftest.event("SessionStart", sid="dad", pid=2, **gone))
    ws.append_event(conftest.event("UserPromptSubmit", sid="orphan", prompt="Go on alone",
                                   started_by=2, pid=5001, **gone))
    ws.append_event(conftest.event("SessionEnd", sid="dad", pid=2, **gone))
    daemon.store.refresh()
    with opened(url) as page:
        lines = '.row[data-id="s1"] .kid'
        page.wait_for_function(f"document.querySelectorAll('{lines}.running').length === 2")
        assert sorted(page.evaluate(
            "Array.from(document.querySelectorAll('.row')).map((r) => r.dataset.id)")) \
            == ["asks", "orphan", "s1"]
        running = page.locator(f"{lines}.running").all_inner_texts()
        assert "Summarise the log" in running[0]
        assert "Compare the maps" in running[1] and "make bench" in running[1]
        # The ended child had a turn end, and is unread to the daemon; the
        # page counts it nowhere. s1 is on screen, so it is read.
        assert page.evaluate("state.sessions.find((s) => s.id === 'over').unread")
        assert page.evaluate("unreadSessions().length") == 0
        counted = page.evaluate("""() => { let seen = null; const real = tabTitle;
          tabTitle = (rows) => { seen = rows.map((r) => r.id); return real(rows); };
          drawCounts(); tabTitle = real; return seen; }""")
        assert sorted(counted) == ["asks", "dad", "orphan", "s1"], counted
        fold = page.locator('.row[data-id="s1"] .kidsran')
        assert fold.inner_text() == "▸ 1 subagent ran"
        assert page.locator(lines).count() == 2
        page.locator(f'{lines}[data-kid="kid"]').click()
        page.wait_for_function("state.chosen === 'kid'")
        page.wait_for_selector(f'{lines}.chosen[data-kid="kid"]')
        fold.click()
        page.wait_for_function(f"document.querySelectorAll('{lines}').length === 3")
        assert "Review the diff" in page.locator(lines).nth(2).inner_text()
        assert page.evaluate("state.chosen") == "kid", "the fold chose the row"
        # It ends, and its line goes under the fold. Its parent's row is
        # still by then -- the page's mark that it read s1 has landed and
        # come back -- so a push of the child alone is what draws it again.
        # And pushed once the stream listens to the child: the choice
        # opened a new one.
        wait_for_watching(daemon, "kid")

        def still():
            daemon.tick()
            row = next(one for one in daemon.store.rows if one["id"] == "s1")
            return not row["unread"] and page.evaluate(
                "state.sessions.find((s) => s.id === 's1').seen_at") == row["seen_at"]

        wait_until(page, still)
        ws.append_event(conftest.event("SessionEnd", sid="kid", ts=time.time(), **by))
        daemon.tick()
        page.wait_for_function(f"document.querySelectorAll('{lines}.running').length === 1")
        assert fold.inner_text() == "▾ 2 subagents ran"
        # Folded, the one being read stays in sight: the chosen session is
        # never hidden from the list it is chosen in.
        fold.click()
        page.wait_for_function(f"document.querySelectorAll('{lines}').length === 2")
        assert page.locator(f'{lines}.chosen[data-kid="kid"]').count() == 1


def test_the_views_keep_their_height_when_the_list_scrolls(ws, page_at, tmp_path):
    """A list longer than the window scrolls, and the four view buttons
    above it stay whole (#423). The row of views clips what overflows it,
    and such a flex item may shrink below its content: the column took
    the list's overflow out of it too, and cut its words in half."""
    daemon, url = page_at
    for n in range(40):
        where = tmp_path.parent / f"many{n}"
        where.mkdir(exist_ok=True)
        ws.append_event(conftest.event("SessionStart", sid=f"m{n}", cwd=str(where),
                                       pane="%9", pid=2, ts=time.time()))
    daemon.store.refresh()
    with opened(url) as page:
        page.set_viewport_size({"width": 1200, "height": 500})
        page.wait_for_function("document.querySelectorAll('.row').length === 41")
        size = page.evaluate("""() => { const v = document.querySelector('.views');
          const b = v.querySelector('.feedlink');
          return [v.clientHeight, v.scrollHeight, b.offsetHeight]; }""")
        assert size[0] == size[1] >= size[2] >= 20, size
        # Nor what stands above it: every part of the column but the list.
        for part in page.evaluate("""() => Array.from(
            document.querySelector('.sidebar').children).filter((c) => c.id !== 'rows')
            .map((c) => [c.className, c.clientHeight, c.scrollHeight])"""):
            assert part[1] >= part[2], part


def test_a_chosen_finished_row_is_as_whole_as_any_chosen_row(past_at):
    """A finished row is faded (72 %), and was faded when chosen too: its
    fade into the content then ended on a grey mix of the list's ground,
    and its edge stood out where it meets the content (#427). Chosen, it is
    solid and its name bright, as on any chosen row; the others stay
    faded."""
    with opened(past_at) as page:
        page.click(".histhead")
        page.wait_for_selector('.row[data-id="acorn"]')
        page.click('.row[data-id="acorn"]')
        page.wait_for_function("state.chosen === 'acorn'")
        page.wait_for_selector('.row.chosen[data-id="acorn"]')
        page.wait_for_function("document.getAnimations().length === 0")
        look = page.evaluate("""() => ['acorn', 'beetroot'].map((id) => {
          const row = document.querySelector(`.row[data-id="${id}"]`);
          const name = getComputedStyle(row.querySelector('.name'));
          return [getComputedStyle(row).opacity, name.fontWeight, name.color]; })""")
        bright = page.evaluate("""() => { const probe = document.createElement('div');
          probe.style.color = 'var(--ink-bright)'; document.body.appendChild(probe);
          const said = getComputedStyle(probe).color; probe.remove(); return said; }""")
        assert look[0] == ["1", "600", bright], look
        assert float(look[1][0]) < 1 and look[1][1] == "500", look


def test_a_push_fills_only_the_rows_it_changed(ws, pair_at):
    """A push carries only the rows that changed (#431), and the page fills
    only those: filling all 500 rows took 34 ms on every push. What the page
    holds is still what the daemon holds -- after a push, and after a new
    stream, which opens with every row. A row left alone still ticks its
    age (`data-since`)."""
    daemon, url = pair_at
    with opened(url) as page:
        two_rows(page)
        wait_for_watching(daemon, page.evaluate("state.chosen"))
        page.evaluate("""() => { window.__filled = []; const real = fillRow;
          fillRow = (row, s) => { window.__filled.push(s.id); return real(row, s); }; }""")
        ws.append_event(conftest.event("UserPromptSubmit", sid="s2", prompt="go",
                                       cwd=str(Path(daemon.store.sessions["s2"].cwd)),
                                       pane="%9", pid=2, ts=time.time()))
        daemon.tick()
        page.wait_for_selector('.row.working[data-id="s2"]')
        assert page.evaluate("window.__filled") == ["s2"]
        held = """() => state.sessions.map((s) => [s.id, s.state])"""
        told = [[one["id"], one["state"]] for one in daemon.store.rows]
        assert page.evaluate(held) == told
        since = page.evaluate("""() => document.querySelector(
          '.row[data-id="s1"] .age').dataset.since""")
        assert since and float(since) > 0
        # A choice changes no session, and no push comes for a row that is
        # read: the row chosen before and the one chosen now are filled.
        other = page.evaluate("state.sessions.find((s) => s.id !== state.chosen).id")
        was = page.evaluate("state.chosen")
        page.evaluate("window.__filled = []")
        page.click(f'.row[data-id="{other}"]')
        page.wait_for_selector(f'.row.chosen[data-id="{other}"]')
        assert page.locator(f'.row.chosen[data-id="{was}"]').count() == 0
        assert sorted(page.evaluate("window.__filled")) == sorted([was, other])
        # A session the daemon no longer lists goes from the page.
        wait_for_watching(daemon, other)
        del daemon.store.sessions[was]
        daemon.tick()
        page.wait_for_function(f"!document.querySelector('.row[data-id=\"{was}\"]')")
        told = [[one["id"], one["state"]] for one in daemon.store.rows]
        assert page.evaluate(held) == told
        # A new stream opens with every row, and the page takes all of it:
        # a list spoiled before it is whole again after it.
        renew_stream(page, "state.sessions = state.sessions.slice(1);"
                           " state.stream.close(); state.stream = null; resubscribe()")
        assert page.evaluate(held) == told
