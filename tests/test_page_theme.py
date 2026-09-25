"""Light and dark, contrast, and motion.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations


import pytest

import conftest
from browser import (
    skip_without_browser,
    sync_playwright,
    fresh_context,
    open_page,
    contrast,
    rgb,
    wait_for_map,
)

pytestmark = skip_without_browser

def test_both_themes_are_readable(page_at):
    """Both themes are the same variables on another ground, and both read."""
    with sync_playwright() as play:
        seen = {}
        for scheme in ("dark", "light"):
            browser, page = open_page(play, page_at, scheme)
            try:
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
            finally:
                browser.close()
        assert seen["dark"][0] != seen["light"][0], "the light theme did not apply"
        assert seen["dark"][1] != seen["light"][1], "code would be unreadable"


def test_the_scrollbars_belong_to_the_theme(page_at):
    """A scrollbar is painted by the browser, not by this stylesheet, so
    without being told which way round the page is it stays at the system's —
    and a dark page carried a bright bar down every column. Measured before
    the fix: `color-scheme: normal` and `scrollbar-color: auto`, in both.

    Take either declaration out and one of these two goes back to what the
    machine happens to be set to."""
    with sync_playwright() as play:
        seen = {}
        for scheme in ("dark", "light"):
            browser, page = open_page(play, page_at, scheme)
            try:
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
            finally:
                browser.close()
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
    with sync_playwright() as play:
        for scheme in ("dark", "light"):
            browser, page = open_page(play, page_at, scheme)
            try:
                page.locator("#find").fill("pytest")
                page.wait_for_selector("mark")
                seen = page.evaluate(
                    "() => { const s = getComputedStyle(document.querySelector('mark'));"
                    " return [s.color, s.backgroundColor]; }")
                assert contrast(*seen) >= 4.5, f"{scheme}: {seen} is {contrast(*seen):.1f}:1"
            finally:
                browser.close()


def test_less_motion_stops_everything_moving(page_at):
    """One switch, so a reader who asked their system for less motion does not
    have to be told about each thing on this page that moves."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            # In seconds, whatever unit the browser reports them in.
            moving = ("() => getComputedStyle(document.querySelector('.row'))"
                      ".transitionDuration.split(', ').map((one) => parseFloat(one))")
            assert max(page.evaluate(moving)) > 0.05
            page.emulate_media(reduced_motion="reduce")
            assert max(page.evaluate(moving)) < 0.01
        finally:
            browser.close()


def test_the_colours_can_be_switched_and_are_remembered(page_at):
    """The light values used to live inside a media query, so choosing light on
    a dark machine could not work at all."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser = fresh_context(play)
        try:
            page = browser.new_page()
            page.goto(path, wait_until="domcontentloaded")
            page.wait_for_selector(".row", timeout=15000)
            dark = page.evaluate("getComputedStyle(document.body).backgroundColor")
            assert page.get_attribute("#theme", "data-choice") == "auto"

            page.locator("#theme").click()           # auto -> light
            page.wait_for_timeout(150)
            light = page.evaluate("getComputedStyle(document.body).backgroundColor")
            assert light != dark, "light on a dark machine did nothing"
            assert page.get_attribute("#theme", "data-choice") == "light"

            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector(".row", timeout=15000)
            assert page.evaluate(
                "getComputedStyle(document.body).backgroundColor") == light
            assert page.get_attribute("#theme", "data-choice") == "light"

            page.locator("#theme").click()           # light -> dark
            page.locator("#theme").click()           # dark -> auto
            page.wait_for_timeout(150)
            assert page.get_attribute("#theme", "data-choice") == "auto"
            assert page.evaluate(
                "getComputedStyle(document.body).backgroundColor") == dark
        finally:
            browser.close()


def test_the_tab_icon_follows_a_theme_change(page_at):
    """The icon is a dot painted out of the palette, and the section is placed
    beside the colours so that it follows them. It did not: `drawIcon` returns
    early when the state it shows has not changed, and the state does not
    change with the theme — so a dark-theme dot sat on a light page."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.wait_for_function(
                "document.querySelector(\"link[rel='icon']\") !== null")
            before = page.evaluate(
                "document.querySelector(\"link[rel='icon']\").href")
            assert before.startswith("data:image/png")

            page.locator("#theme").click()          # whatever it was, not that
            page.wait_for_function(
                """(was) => document.querySelector("link[rel='icon']").href !== was""",
                arg=before)
        finally:
            browser.close()


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
    states = ["offline", "outdated", "show-thinking", "dragging"]
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
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
        finally:
            browser.close()


def test_every_icon_fits_inside_its_box(page_at):
    """An `svg` clips to its own viewport, and a stroke reaches half its
    width past the line it is drawn on. The page icon's bottom edge sat at
    13.5 with a 1.2 stroke, so the last tenth of it was cut away — and the
    next icon anybody draws would have gone the same way.

    Measured with the page's own `putIcon` and the page's own CSS, so this is
    the width that really ships and not a number copied into a test.
    """
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
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
        finally:
            browser.close()


def test_the_tabs_start_at_the_top_and_the_name_heads_the_session_list(page_at):
    """A bar across the whole page held the name, a count of sessions, the
    counts by state, the alerts and the colours. The reader asked for the
    room back: the counts are the sidebar's groups again, the name and the
    version head the session list, and the two buttons are icons at the end
    of the tab row -- which now starts at the top of the window, level with
    the head of the list beside it."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            out = page.evaluate("""() => {
              const box = (sel) => document.querySelector(sel).getBoundingClientRect();
              const head = document.querySelector('.sidebar-head');
              return {topbar: document.querySelectorAll('.topbar, #counts, #where').length,
                      tabsTop: box('.tabs').top, tabsBottom: box('.tabs').bottom,
                      headBottom: box('.sidebar-head').bottom,
                      brand: head.querySelector('.brand').textContent,
                      version: head.querySelector('.version').textContent,
                      bell: !!document.querySelector('.tabs #bell svg'),
                      theme: !!document.querySelector('.tabs #theme svg'),
                      words: document.querySelector('.tabs #bell').textContent
                        + document.querySelector('.tabs #theme').textContent};
            }""")
            assert out["topbar"] == 0
            assert out["tabsTop"] == 0
            assert abs(out["tabsBottom"] - out["headBottom"]) <= 1, out
            assert out["brand"] == "wostuast"
            assert " · " in out["version"] and "__" not in out["version"]
            assert out["bell"] and out["theme"] and out["words"] == ""
        finally:
            browser.close()
