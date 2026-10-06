"""Light and dark, contrast, and motion.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations

import json


import pytest

import conftest
from browser import (
    kept,
    settings,
    skip_without_browser,
    opened,
    own_context,
    contrast,
    rgb,
    wait_for_map,
)

pytestmark = skip_without_browser

def test_both_themes_are_readable(page_at):
    """Both themes are the same variables on another ground, and both read."""
    seen = {}
    for scheme in ("dark", "light"):
        with opened(page_at, scheme) as page:
            # `open_page` returns on the first draw, and the first draw is
            # the tab's frame -- the transcript, and so the code block
            # this reads, arrives one fetch later. Asking straight away
            # threw on a null element, on a loaded runner and nowhere else.
            page.wait_for_selector(".prose pre code")
            seen[scheme] = (
                page.evaluate("getComputedStyle(document.body).backgroundColor"),
                page.evaluate(
                    "getComputedStyle(document.querySelector('.prose pre code'))"
                    ".color"),
            )
    assert seen["dark"][0] != seen["light"][0], "the light theme did not apply"
    assert seen["dark"][1] != seen["light"][1], "code would be unreadable"


def test_the_scrollbars_belong_to_the_theme(page_at):
    """A scrollbar is painted by the browser, not by this stylesheet, so
    without being told which way round the page is it stays at the system's —
    and a dark page carried a bright bar down every column. Measured before
    the fix: `color-scheme: normal` and `scrollbar-color: auto`, in both.

    Take either declaration out and one of these two goes back to what the
    machine happens to be set to."""
    seen = {}
    for scheme in ("dark", "light"):
        with opened(page_at, scheme) as page:
            # `open_page` waits for the frame, not the transcript: on a
            # loaded machine `.turnbody` was not there yet and the read
            # below threw on null.
            wait_for_map(page)
            seen[scheme] = page.evaluate("""() => {
              const root = getComputedStyle(document.documentElement);
              // Inherited, so a pane deep in the page has to have it too.
              const pane = getComputedStyle(
                document.querySelector('.turnbody'));
              // Through an element, so the variable comes back as the
              // browser resolves it rather than as the hex it is written.
              const probe = document.createElement('span');
              probe.style.color = 'var(--edge-bright)';
              document.body.appendChild(probe);
              const edge = getComputedStyle(probe).color;
              probe.remove();
              return {scheme: root.colorScheme, bar: pane.scrollbarColor,
                      edge: edge};
            }""")
    assert seen["dark"]["scheme"] == "dark", seen
    assert seen["light"]["scheme"] == "light", seen
    # The thumb is the page's own line colour, not the system's grey, and
    # it is a different one in each theme.
    for scheme, one in seen.items():
        assert one["bar"] != "auto", (scheme, one)
        thumb = one["bar"].split(") ")[0] + ")"
        assert rgb(thumb) == rgb(one["edge"]), (scheme, one)
    assert seen["dark"]["bar"] != seen["light"]["bar"], seen


def test_a_search_hit_can_be_read_in_both_themes(page_at):
    """The mark sat on the amber with near-black text. In the light theme the
    amber is a dark brown, so near-black on it could not be read at all."""
    for scheme in ("dark", "light"):
        with opened(page_at, scheme) as page:
            page.locator("#find").fill("pytest")
            page.wait_for_selector("mark")
            seen = page.evaluate(
                "() => { const s = getComputedStyle(document.querySelector('mark'));"
                " return [s.color, s.backgroundColor]; }")
            assert contrast(*seen) >= 4.5, f"{scheme}: {seen} is {contrast(*seen):.1f}:1"


def test_less_motion_stops_everything_moving(page_at):
    """One switch, so a reader who asked their system for less motion does not
    have to be told about each thing on this page that moves."""
    with opened(page_at) as page:
        # In seconds, whatever unit the browser reports them in.
        moving = ("() => getComputedStyle(document.querySelector('.row'))"
                  ".transitionDuration.split(', ').map((one) => parseFloat(one))")
        assert max(page.evaluate(moving)) > 0.05
        page.emulate_media(reduced_motion="reduce")
        assert max(page.evaluate(moving)) < 0.01


def test_the_colours_can_be_switched_and_are_remembered(page_at):
    """The light values used to live inside a media query, so choosing light on
    a dark machine could not work at all."""
    daemon, path = page_at
    with own_context() as browser:
        page = browser.new_page()
        page.goto(path, wait_until="domcontentloaded")
        page.wait_for_selector(".row", timeout=15000)
        dark = page.evaluate("getComputedStyle(document.body).backgroundColor")
        chosen = "document.documentElement.dataset.themeChoice"
        assert page.evaluate(chosen) == "system"

        settings(page, "colours", "light")
        page.wait_for_timeout(150)
        light = page.evaluate("getComputedStyle(document.body).backgroundColor")
        assert light != dark, "light on a dark machine did nothing"
        assert page.evaluate(chosen) == "light"
        assert page.get_attribute(
            "#setpop .colours button[data-value='light']", "aria-pressed") == "true"

        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector(".row", timeout=15000)
        assert page.evaluate(
            "getComputedStyle(document.body).backgroundColor") == light
        assert page.evaluate(chosen) == "light"

        settings(page, "colours", "dark")
        settings(page, "colours", "system")
        page.wait_for_timeout(150)
        assert page.evaluate(chosen) == "system"
        assert page.evaluate(
            "getComputedStyle(document.body).backgroundColor") == dark


def test_the_tab_icon_follows_the_browser_and_not_the_page(page_at):
    """The icon stands in the browser's tab bar, so it follows the browser's
    light or dark. It was painted out of the page's palette, and a page
    switched to light in a dark browser put a dark-ink icon on a dark bar.
    So the page's theme leaves it alone, and the browser's scheme redraws
    it."""
    with opened(page_at) as page:
        page.emulate_media(color_scheme="light")
        page.evaluate("redrawIcon()")
        href = "document.querySelector(\"link[rel='icon']\").href"
        before = page.evaluate(href)
        assert before.startswith("data:image/png")

        settings(page, "colours", "dark")
        settings(page, "colours", "light")
        assert page.evaluate(href) == before, "the page's theme moved it"

        page.emulate_media(color_scheme="dark")
        page.wait_for_function(f"{href} !== {json.dumps(before)}")


def test_no_state_on_the_body_can_make_the_page_vanish(page_at):
    """`stream.onerror` does `classList.add("lost")`, and the rule that hid
    the bar until it was wanted was `.lost { display: none }` — which the
    body then matched itself. The whole page went to `display: none` the
    moment the stream hiccupped, and came back when it reconnected or when
    the reader pressed F5. From the outside it read as a page that had
    simply stopped working.

    So the rule is not "do not call it `lost`" but this: whatever the page
    puts on `body`, the page is still there. Every class it sets is named
    here, and a new one belongs in this list.
    """
    states = ["offline", "outdated", "dragging"]
    with opened(page_at) as page:
        seen = page.evaluate("""(states) => {
          const look = () => [
            getComputedStyle(document.body).display,
            Math.round(document.querySelector(".app")
                         .getBoundingClientRect().height),
            document.querySelectorAll(".row").length];
          const out = {before: look()};
          for (const one of states) {
            document.body.classList.add(one);
            out[one] = look();
            document.body.classList.remove(one);
          }
          // And all of them at once, which is a real Tuesday.
          document.body.classList.add(...states);
          out.together = look();
          return out;
        }""", states)
        tall = seen["before"][1]
        assert tall > 100, seen
        for where, found in seen.items():
            assert found[0] != "none", (where, found)
            assert found[1] == tall, (where, found)
            assert found[2] == seen["before"][2], (where, found)


def test_every_icon_fits_inside_its_box(page_at):
    """An `svg` clips to its own viewport, and a stroke reaches half its
    width past the line it is drawn on. The page icon's bottom edge sat at
    13.5 with a 1.2 stroke, so the last tenth of it was cut away — and the
    next icon anybody draws would have gone the same way.

    Measured with the page's own `putIcon` and the page's own CSS, so this is
    the width that really ships and not a number copied into a test.
    """
    with opened(page_at) as page:
        out = page.evaluate("""() => {
          const where = "http://www.w3.org/2000/svg";
          // Inside a `.filelist`, because that is where `.icon` is
          // styled and the stroke width is the thing being measured.
          const host = document.createElement("div");
          host.className = "filelist";
          host.style.position = "absolute";
          host.style.visibility = "hidden";
          document.body.appendChild(host);
          putIcon(host, "dir");
          const wide = parseFloat(
            getComputedStyle(host.querySelector(".icon")).strokeWidth);
          const svg = host.querySelector("svg");
          const path = svg.querySelector("path");
          const found = {};
          for (const [name, d] of Object.entries(ICONS)) {
            path.setAttribute("d", d);
            const box = path.getBBox();
            const half = wide / 2;
            found[name] = [box.x - half, box.y - half,
                           box.x + box.width + half,
                           box.y + box.height + half];
          }
          host.remove();
          return {wide, found};
        }""")
        assert out["wide"] > 0, out
        for name, edge in out["found"].items():
            assert all(-0.001 <= one <= 14.001 for one in edge), (name, edge)


def test_the_tabs_start_at_the_top_and_the_name_heads_the_session_list(page_at):
    """A bar across the whole page held the name, a count of sessions, the
    counts by state, the alerts and the colours. The reader asked for the
    room back: the counts are the sidebar's groups again, the name and the
    version head the session list, and the two buttons are icons at the end
    of the tab row -- which now starts at the top of the window, level with
    the head of the list beside it."""
    with opened(page_at) as page:
        out = page.evaluate("""() => {
          const box = (sel) => document.querySelector(sel).getBoundingClientRect();
          const head = document.querySelector('.sidebar-head');
          return {topbar: document.querySelectorAll('.topbar, #counts, #where').length,
                  tabsTop: box('.tabs').top, tabsBottom: box('.tabs').bottom,
                  headBottom: box('.sidebar-head').bottom,
                  brand: head.querySelector('.brand').textContent,
                  version: head.querySelector('.version').textContent,
                  settings: !!document.querySelector('.tabs #settings svg'),
                  words: document.querySelector('.tabs #settings').textContent};
        }""")
        assert out["topbar"] == 0
        assert out["tabsTop"] == 0
        assert abs(out["tabsBottom"] - out["headBottom"]) <= 1, out
        assert out["brand"] == "wostuast"
        assert " · " in out["version"] and "__" not in out["version"]
        assert out["settings"] and out["words"] == ""


def test_the_name_links_to_the_project(page_at):
    """The reader asked for the name at the top of the list to lead to the
    project (#333). In a tab of its own, so the page that watches the agents
    stays open, and with no opener, so the project's page cannot reach back
    into this one, which holds the token."""
    with opened(page_at) as page:
        brand = page.locator(".sidebar-head a.brand")
        assert brand.text_content() == "wostuast"
        assert brand.get_attribute("href") == "https://github.com/martinus/wostuast"
        assert brand.get_attribute("target") == "_blank"
        assert set(brand.get_attribute("rel").split()) >= {"noopener", "noreferrer"}


def test_every_settings_label_stands_level_with_what_it_names(page_at):
    """A label is read along the line it stands on. With a padding to line
    it up with a button, "alerts" stood 5 px under its first checkbox, and
    the reader saw it. Measured from the text, not the boxes: a checkbox
    row and a button row are not the same height."""
    with opened(page_at) as page:
        page.click("#settings")
        page.wait_for_selector("#setpop:not([hidden]) .setlabel")
        gaps = page.evaluate("""() => {
          const mid = (node) => {
            const walk = document.createTreeWalker(node, NodeFilter.SHOW_TEXT,
              { acceptNode: (t) => t.data.trim() ? 1 : 3 });
            const range = document.createRange();
            range.selectNodeContents(walk.nextNode());
            const box = range.getClientRects()[0];
            return box.top + box.height / 2;
          };
          return [...document.querySelectorAll("#setpop .setlabel")].map(
            (label) => [label.textContent.trim(),
                        mid(label.nextElementSibling) - mid(label)]);
        }""")
        assert len(gaps) == 8, gaps
        assert all(abs(gap) <= 1 for _, gap in gaps), gaps


# --- the settings, kept in one file -------------------------------------------


def test_a_setting_reaches_every_open_page_and_survives_a_reload(ws, page_at):
    """The reader asked for one file in place of each browser's own memory:
    a choice made in one page is kept in `settings.json`, and every other
    open page takes it from the push, without a reload."""
    daemon, url = page_at
    with own_context() as browser:
        one = browser.new_page()
        two = browser.new_page()
        for page in (one, two):
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector(".row")
            page.wait_for_function("state.live === 'live'")
        settings(one, "tabwidth", "8")
        settings(one, "colours", "light")
        settings(one, "wrapping", "true")
        kept(ws, "tab_width", 8)
        kept(ws, "colours", "light")
        kept(ws, "long_lines", "wrap")
        two.wait_for_function("""() => {
          const root = document.documentElement;
          return root.style.getPropertyValue('--tab-w') === '8'
            && root.dataset.theme === 'light' && root.dataset.wrap === 'yes';
        }""")
        # And a file changed by hand reaches the page the same way: the
        # tick sees it. No fixture runs a ticker, so the test ticks.
        ws.config_path().write_text(json.dumps({"colours": "dark"}),
                                    encoding="utf-8")
        daemon.tell_config()
        two.wait_for_function("""() => {
          const root = document.documentElement;
          return root.dataset.theme === 'dark'
            && root.style.getPropertyValue('--tab-w') === '4';
        }""")


def test_the_page_starts_in_the_colours_of_the_file(ws, page_at):
    """They are in the page as it is served, so the first paint is right: a
    fetch after it would be a flash of the wrong colours."""
    ws.save_config({"colours": "light", "tab_width": 2, "diff_columns": "two"})
    _, url = page_at
    with own_context(scheme="dark") as browser:
        page = browser.new_page()
        # Read the moment the body is made: the head's script has run
        # and the page's own, at the end of the body, has not. The
        # colours the first paint has.
        # The whole document is watched: this runs before `<html>` is
        # there, and observing the element that is not yet made threw.
        page.add_init_script("""new MutationObserver((seen, watch) => {
          if (!document.body) return;
          window.firstTheme = document.documentElement.dataset.theme;
          watch.disconnect();
        }).observe(document, { childList: true, subtree: true });""")
        page.goto(url, wait_until="domcontentloaded")
        seen = [page.evaluate("window.firstTheme")]
        assert seen == ["light"], seen
        page.wait_for_selector(".row")
        page.click("#settings")
        assert page.get_attribute(
            "#setpop .tabwidth button[data-value='2']", "aria-pressed") == "true"
        assert page.get_attribute(
            "#setpop .sides button[data-value='split']", "aria-pressed") == "true"
        assert page.inner_text("#settingspath").endswith("settings.json")


def test_the_whole_settings_menu_is_in_the_proportional_face(page_at):
    """The reader asked for it: in the fixed face a long url made the menu as
    wide as the link."""
    with opened(page_at) as page:
        page.click("#settings")
        page.click("#setpop .linkadd")
        faces = page.eval_on_selector_all(
            "#setpop .setlabel, #setpop .verb, #setpop input, #setpop .where",
            "els => [...new Set(els.map((one) => getComputedStyle(one).fontFamily))]")
        assert faces and all("Mono" not in one and "monospace" not in one
                             for one in faces), faces
        # And a long url does not make it wider.
        wide = page.evaluate("document.getElementById('setpop').offsetWidth")
        page.fill("#linklist .linkurl", "https://t.example/" + "x" * 400)
        assert page.evaluate("document.getElementById('setpop').offsetWidth") == wide



def test_the_c_key_steps_through_the_colours(page_at):
    """`c` takes the next of auto, light and dark, and after dark auto
    again. No test pressed it until the page script's coverage said that
    `nextTheme` never ran (#439).

    Each press waits for its own push before the next: a choice is shown
    at once and made so by the push, and the push of an earlier press came
    after a later one, put "dark" back over "auto", and the next press
    started from there. It went red once in four runs under load."""
    with opened(page_at) as page:
        page.evaluate("""() => {
          window.__took = [];
          const take = takeSettings;
          takeSettings = (body, first) => { window.__took.push(body.colours); take(body, first); };
          document.activeElement && document.activeElement.blur();
        }""")
        seen = [page.evaluate("themeChoice()")]
        for word in ("light", "dark", "auto"):
            page.keyboard.press("c")
            page.wait_for_function("w => window.__took.at(-1) === w", arg=word)
            seen.append(page.evaluate("themeChoice()"))
    assert seen == ["system", "light", "dark", "system"]




def faces(page, selectors):
    """Each selector's face, or 'missing' when nothing matches it."""
    return page.evaluate("""(selectors) => selectors.map((sel) => {
      const one = document.querySelector(sel);
      return [sel, one ? getComputedStyle(one).fontFamily : 'missing'];
    })""", selectors)


def fixed_only_for(seen, machine):
    for sel, face in seen:
        assert face != "missing", (sel, seen)
        fixed = "Mono" in face or "monospace" in face
        assert fixed == (sel in machine), (sel, face)


def test_the_fixed_face_is_for_machine_text_only(page_at):
    """Which face says what was random (#448). The fixed face is for text a
    machine reads or the reader types; a time, a count, a name and a tab's
    title are words. The reader named six places it was wrong: the time of
    a session and of a turn, "claude", the tabs among them."""
    with opened(page_at) as page:
        wait_for_map(page)
        page.wait_for_selector(".who")
        machine = ["#say"]
        fixed_only_for(faces(page, [".row .age", ".who", ".tabs .tab", ".listnote",
                                    ".band", "#sendbar .verb"] + machine), machine)


def test_the_review_bar_reads_in_words(repo_page):
    """"against", "older", "newer" and "3 / 3" are words, and the diff is
    code (#448)."""
    with opened(repo_page, tab="diff") as page:
        page.wait_for_selector(".diffbar .baseword")
        machine = [".dlines", ".hunk"]
        fixed_only_for(faces(page, [".diffbar .baseword", ".diffbar .stepat",
                                    ".diffbar .pickof"] + machine), machine)
