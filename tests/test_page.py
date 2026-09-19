"""The page, driven in a real browser.

These run only where a browser is available. They exist because the one bug
that mattered here could not be seen any other way: raw HTML was scrubbed
after being written into the document, by which time an `onerror` had already
fired. Nothing short of a browser catches that.
"""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

import conftest

CHROMIUM = [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
]


def browser_path() -> str | None:
    for candidate in [os.environ.get("WOSTUAST_CHROME", "")] + CHROMIUM:
        if candidate and Path(candidate).exists():
            return candidate
    return None


start_playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed"
).sync_playwright

# One Playwright and one browser for the whole file. Starting Playwright costs
# 0.43 s and launching Chromium 0.15 s, and there are fifty-odd tests here, so
# half a minute of every run went on starting the same two things again and
# again. A context costs 0.03 s and shares nothing — its own storage, its own
# cookies — so each test is still on its own.
_shared: list = []


def shared_browser():
    if not _shared:
        play = start_playwright().start()
        _shared.append(play)
        _shared.append(play.chromium.launch(executable_path=browser_path(),
                                            args=["--no-sandbox"]))
    return _shared[1]


@pytest.fixture(scope="session", autouse=True)
def _close_the_browser():
    yield
    if _shared:
        play, browser = _shared
        browser.close()
        play.stop()
        _shared.clear()


@contextmanager
def sync_playwright():
    """The shared browser, in the shape the tests already ask for it."""
    yield shared_browser()

pytestmark = pytest.mark.skipif(browser_path() is None, reason="no browser here")


HOSTILE = (
    "Read from a README:\n\n"
    '<img src=x onerror="window.PWNED=1">\n'
    "<script>window.PWNED=2</script>\n"
    "[click me](javascript:window.PWNED=3)\n\n"
    "A fence needing a real `>`:\n\n```python\nif len(hits) > 1:\n    raise Ambiguous\n```\n"
)


@pytest.fixture
def page_at(ws, tmp_path, monkeypatch, transcript_file):
    """A daemon with one session whose transcript holds hostile Markdown."""
    monkeypatch.setattr(ws, "git_facts_many", lambda dirs: {
        d: ws.GitFacts(repo="repo", branch="main") for d in dirs})
    monkeypatch.setattr(ws, "pid_alive", lambda pid: True)

    transcript = transcript_file("s1", [
        {"type": "user", "timestamp": "2026-09-18T14:02:00.000Z",
         "message": {"role": "user", "content": "Do the thing."}},
        {"type": "assistant", "timestamp": "2026-09-18T14:03:00.000Z",
         "message": {"role": "assistant",
                     "content": [{"type": "text", "text": HOSTILE}]}},
        {"type": "assistant", "timestamp": "2026-09-18T14:04:00.000Z",
         "message": {"role": "assistant", "content": [
             {"type": "tool_use", "id": "t1", "name": "Bash",
              "input": {"command": "pytest -q"}}]}},
        {"type": "user", "timestamp": "2026-09-18T14:04:05.000Z",
         "message": {"role": "user", "content": [
             {"type": "tool_result", "tool_use_id": "t1",
              "content": "14 passed in 0.31s\nall good"}]}},
    ])
    ws.append_event({"session_id": "s1", "hook_event_name": "SessionStart",
                     "cwd": str(tmp_path), "pane": "%7", "pid": 1,
                     "ts": time.time(), "transcript_path": str(transcript)})
    ws.write_status("s1", ws.Status(ts=1.0, name="A session", model="Opus 5",
                                    context_pct=41.0))

    daemon = ws.Daemon()
    server = ws.make_server(daemon, 0)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    daemon.store.refresh()
    try:
        yield daemon, f"http://127.0.0.1:{port}/"
    finally:
        daemon.stopping.set()
        server.shutdown()
        server.server_close()


MARKED = Path(__file__).resolve().parent / "fixtures" / "marked.min.js"


# What each tab has drawn once its first answer has arrived. Waiting for the
# thing itself beats sleeping for long enough: it is both quicker and surer.
# The transcript shares the box with the two split tabs, so "the box has a
# child" is already true while the file columns are still standing in it. It
# has to have stopped being split as well.
DRAWN = {"transcript": "#content:not(.split) > *", "files": ".filebody > *",
         "diff": ".diffbody > *", "peek": ".peek"}


def fresh_context(play, scheme="dark", with_marked=True):
    """A context of its own, with everything the page fetches answered from
    here, so that no test needs a network.

    marked gets the real bytes, which means the page's `integrity` hash is
    checked for real on every one of these tests. The highlighter is refused,
    which is what being offline looks like; the tests that want one hand the
    page a stand-in instead. The fonts are answered empty: a stylesheet in the
    head holds up the script after it, and no test looks at a typeface.
    """
    context = play.new_context(viewport={"width": 1440, "height": 900},
                               color_scheme=scheme)
    context.route("**/marked.min.js", lambda route: route.fulfill(
        path=str(MARKED), content_type="application/javascript",
        headers={"access-control-allow-origin": "*"})
        if with_marked else route.abort())
    context.route("**/highlight.min.js", lambda route: route.abort())
    context.route("**/fonts.googleapis.com/**", lambda route: route.fulfill(
        status=200, content_type="text/css", body=""))
    return context


def open_page(play, where, scheme="dark", with_marked=True):
    """A fresh context on the shared browser. What comes back is the context,
    so a test that closes `browser` closes its own and nobody else's."""
    url = where[1] if isinstance(where, tuple) else where
    browser = fresh_context(play, scheme, with_marked)
    page = browser.new_page()
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector(".row", timeout=15000)
    # Wait for the first draw rather than for a length of time.
    ready = "document.querySelector('#content > *') !== null"
    if with_marked:
        ready = "!!window.marked && " + ready
    page.wait_for_function(ready, timeout=15000)
    return browser, page


def test_the_page_draws_the_session(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            assert page.locator(".row").count() == 1
            # The worktree leads the row; what Claude Code called the session
            # goes under it, because the name is often long and often vague
            # and it used to push the worktree off the end.
            place = page.locator(".row .name").inner_text()
            assert place and "A session" not in place
            assert "A session" in page.locator(".row .called").inner_text()
            assert page.title() == "wostuast"
            assert "Opus 5" in page.locator("#facts").inner_text()
            assert page.locator(".turn").count() >= 2
        finally:
            browser.close()


def test_hostile_markdown_cannot_run(page_at):
    """An agent that reads a nasty file must not be able to act on this page.
    The page shares an origin with the tmux verbs, so this is the whole game."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            assert page.evaluate("window.PWNED ?? null") is None
            assert page.locator(".prose img").count() == 0
            assert page.locator(".prose script").count() == 0
            hrefs = page.eval_on_selector_all(
                ".prose a", "els => els.map(e => e.getAttribute('href'))")
            assert all(h is None or h.startswith(("http", "#")) for h in hrefs)
        finally:
            browser.close()


def test_raw_html_is_shown_rather_than_swallowed(page_at):
    """The reader should see what the agent saw, as text."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            shown = page.locator(".prose").last.inner_text()
            assert "onerror" in shown
            assert "window.PWNED=2" in shown
        finally:
            browser.close()


def test_a_code_fence_keeps_its_angle_bracket(page_at):
    """Escaping the Markdown source instead of the output turned `>` into
    `&gt;` inside fences. This is that regression."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            fence = page.locator(".prose pre").last.inner_text()
            assert "len(hits) > 1" in fence
            assert "&gt;" not in fence
        finally:
            browser.close()


def test_both_themes_are_readable(page_at):
    """PLAN.md section 5.2 asks for a light theme from the start."""
    with sync_playwright() as play:
        seen = {}
        for scheme in ("dark", "light"):
            browser, page = open_page(play, page_at, scheme)
            try:
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


def rgb(text):
    """The three numbers out of a computed `rgb(r, g, b)` or `rgba(...)`."""
    parts = text[text.index("(") + 1:text.index(")")].replace("/", " ").split(",")
    return [float(one.strip().rstrip("%")) for one in parts[:3]]


def contrast(front, back):
    """WCAG 2.1 contrast, so that "is this readable" is a number, not a look."""
    def light(colour):
        channels = []
        for value in rgb(colour):
            part = value / 255
            channels.append(part / 12.92 if part <= 0.03928
                            else ((part + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
    one, two = light(front), light(back)
    high, low = max(one, two), min(one, two)
    return (high + 0.05) / (low + 0.05)


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


def test_only_a_block_that_has_just_arrived_slides_in(page_at):
    """A transcript is rebuilt whenever anything about it changes. Animating
    every block on every rebuild would make the tab shiver each time an agent
    ran a tool, so the slide is for a block nobody has seen before."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            assert page.locator(".fresh").count() == 0, "the history slid in too"
            blocks = daemon.read_transcript("s1")
            one = dict(blocks[-1].__dict__)
            one.update(seq=len(blocks), kind="text", text="and one more thing")
            daemon.hub.send("transcript", {"id": "s1", "blocks": [one]},
                            session_id="s1")
            # In one question, so that a redraw cannot land between asking
            # whether it is there and asking how many there are.
            page.wait_for_function(
                "document.querySelectorAll('.fresh').length === 1")
            moving = ("() => getComputedStyle(document.querySelector('.turn'))"
                      ".animationName")
            assert page.evaluate(moving) == "none", "the whole history animates"
            # Drawing it again is not arriving again.
            page.evaluate("draw()")
            assert page.locator(".fresh").count() == 0
        finally:
            browser.close()


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
            assert "starting" in page.evaluate("window.__dot.className")
            ws.append_event(conftest.event(
                "PermissionRequest", tool_name="Bash",
                tool_input={"command": "ls ~"}, ts=time.time()))
            daemon.tick()            # fold it, and tell the page
            page.wait_for_function("window.__dot.className.includes('needs_you')")
            assert page.evaluate("window.__dot.isConnected"), "the row was rebuilt"
        finally:
            browser.close()


def test_expanding_a_tool_result_leaves_the_rest_alone(page_at):
    """It used to redraw the whole tab, which re-parsed every Markdown block
    and threw the reader to the bottom of the transcript."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.evaluate("document.querySelector('.content').scrollTop = 0")
            page.evaluate("window.__first = document.querySelector('.turn')")
            before = page.evaluate("document.querySelector('.content').scrollTop")
            page.locator(".tool").first.click()
            page.wait_for_timeout(250)
            assert page.locator(".tool-result").count() == 1
            assert page.evaluate("document.querySelector('.content').scrollTop") == before
            assert page.evaluate("window.__first.isConnected"), "everything was redrawn"
        finally:
            browser.close()


def test_a_key_for_a_tab_that_does_not_exist_does_nothing(page_at):
    """`showTab` only takes a name TABS knows, so a fifth key changes nothing.
    Peek answered to `4` from milestone 5; there is no `5`."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            turns = page.locator(".turn").count()
            page.keyboard.press("5")
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


def test_the_session_the_page_picks_for_you_is_watched(page_at, ws):
    """The page auto-selects the first session. It used to set it without
    subscribing, so the stream stayed on watch="" and the transcript of the
    one session actually on screen never updated."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            before = page.locator(".turn").count()
            assert page.locator(".row.chosen").count() == 1

            with open(daemon_transcript(daemon), "a") as handle:
                handle.write(json.dumps({
                    "type": "assistant", "timestamp": "2026-09-18T14:09:00.000Z",
                    "message": {"role": "assistant", "content": [
                        {"type": "text", "text": "A brand new line."}]}}) + "\n")
            daemon.tick()
            page.wait_for_timeout(1200)
            assert page.locator(".turn").count() == before + 1
            assert "A brand new line." in page.locator(".content").inner_text()
        finally:
            browser.close()


def daemon_transcript(daemon):
    return daemon.transcript("s1").tail.path


def test_the_same_blocks_arriving_twice_are_not_shown_twice(page_at):
    """A reconnected stream re-sends the transcript from the beginning, and the
    first fetch and the first push can carry the same block. Each block knows
    its place, so it lands in the same slot either way."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            before = page.locator(".turn").count()
            assert before > 1
            blocks = daemon.read_transcript("s1")
            daemon.hub.send("transcript",
                            {"id": "s1", "blocks": [dict(b.__dict__) for b in blocks]},
                            session_id="s1")
            page.wait_for_timeout(800)
            assert page.locator(".turn").count() == before
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
            assert page.locator("#theme").inner_text() == "auto"

            page.locator("#theme").click()           # auto -> light
            page.wait_for_timeout(150)
            light = page.evaluate("getComputedStyle(document.body).backgroundColor")
            assert light != dark, "light on a dark machine did nothing"
            assert page.locator("#theme").inner_text() == "light"

            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector(".row", timeout=15000)
            assert page.evaluate(
                "getComputedStyle(document.body).backgroundColor") == light
            assert page.locator("#theme").inner_text() == "light"

            page.locator("#theme").click()           # light -> dark
            page.locator("#theme").click()           # dark -> auto
            page.wait_for_timeout(150)
            assert page.locator("#theme").inner_text() == "auto"
            assert page.evaluate(
                "getComputedStyle(document.body).backgroundColor") == dark
        finally:
            browser.close()


def test_typing_finds_text_in_the_transcript(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            everything = page.locator(".turn").count()
            page.locator("#find").fill("pytest")
            page.wait_for_timeout(250)
            assert page.locator(".turn").count() < everything
            assert page.locator("mark").count() >= 1
            assert "pytest" in page.locator("mark").first.inner_text().lower()
            assert " of " in page.locator("#live").inner_text()

            page.locator("#find").fill("")
            page.wait_for_timeout(250)
            assert page.locator(".turn").count() == everything
            assert page.locator("mark").count() == 0
        finally:
            browser.close()


def test_a_search_that_matches_nothing_says_so(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.locator("#find").fill("zzzznotherezzzz")
            page.wait_for_timeout(250)
            assert page.locator(".turn").count() == 0
            assert "Nothing here matches" in page.locator(".content").inner_text()
        finally:
            browser.close()


def test_searching_never_re_parses_what_an_agent_wrote(page_at):
    """Highlighting walks text nodes. A search that looks like markup must not
    become markup."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.locator("#find").fill("<img")
            page.wait_for_timeout(250)
            assert page.evaluate("window.PWNED ?? null") is None
            assert page.locator(".prose img").count() == 0
            assert page.locator("mark").count() >= 1
        finally:
            browser.close()


def test_a_regex_in_the_search_box_is_taken_literally(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.locator("#find").fill("len(hits)")
            page.wait_for_timeout(250)
            assert page.locator("mark").count() >= 1
            assert "len(hits)" in page.locator("mark").first.inner_text()
        finally:
            browser.close()


def test_keys_do_not_fire_while_typing_in_the_search_box(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.locator("#find").focus()
            page.keyboard.type("j")
            page.wait_for_timeout(150)
            assert page.locator("#find").input_value() == "j"
            assert page.evaluate("document.getElementById('help').open") is False
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


@pytest.fixture
def pair_at(ws, page_at, tmp_path):
    """The same daemon with a second session beside the first, so that a filter
    has something to choose between. Two real sessions, not two made up in the
    page: the daemon pushes the list whenever anything changes, and a made-up
    one is gone the moment it does."""
    daemon, url = page_at
    other = tmp_path.parent / "warmhare"
    other.mkdir(exist_ok=True)
    ws.append_event(conftest.event("SessionStart", sid="s2", cwd=str(other),
                                   pane="%9", pid=2, ts=time.time()))
    daemon.store.refresh()
    return daemon, url


def two_rows(page):
    page.wait_for_function("document.querySelectorAll('.row').length === 2")


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
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            assert page.locator(".ctx .bar").count() == 1
            width = page.evaluate("document.querySelector('.ctx .fill').style.width")
            assert width == "41%"
            assert "41% ctx" in page.locator("#facts").inner_text()
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


# --- the Files tab and the Diff tab ------------------------------------------


@pytest.fixture
def repo_page(ws, served, repo):
    """A session in a real repository: one committed change, one not."""
    from conftest import git_in as git

    (repo / "README.md").write_text("# The readme\n\nfirst line\n")
    (repo / "code.py").write_text("print(1)\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "seed")
    git(repo, "checkout", "-qb", "side")
    (repo / "code.py").write_text("print(1)\nprint(2)\n")
    git(repo, "commit", "-qam", "second")
    (repo / "README.md").write_text("# The readme\n\nfirst line\nsecond line\n")
    (repo / "NOTES.md").write_text("# Notes\n\n" + HOSTILE)

    daemon, base = served
    ws.append_event(conftest.event("SessionStart", cwd=str(repo), ts=time.time(),
                                   pane="%7", pid=1))
    daemon.store.refresh()
    return repo, base


@pytest.fixture(scope="session")
def big_repo(tmp_path_factory):
    """A repository with more files than the old list would send.

    Built once for the whole run: writing 5200 files and committing them costs
    about two seconds, and several tests want it. Every one of them only reads,
    so there is nothing to keep apart.
    """
    from conftest import git_in as git

    root = tmp_path_factory.mktemp("big")
    (root / "native" / "shared" / "libcorrelation" / "src").mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    for index in range(5200):
        (root / f"f{index:05d}.txt").write_text("x")
    (root / "native" / "shared" / "libcorrelation" / "src" / "Action.h").write_text(
        "// deep\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "first")
    return root


@pytest.fixture
def big_page(ws, served, big_repo):
    """A session standing in that repository."""
    daemon, base = served
    ws.append_event(conftest.event("SessionStart", cwd=str(big_repo),
                                   ts=time.time(), pane="%7", pid=1))
    daemon.store.refresh()
    return big_repo, base


def show_tab(page, name):
    """Open a tab and wait for its first answer, not for a fixed time."""
    page.click(f".tab[data-tab='{name}']")
    page.wait_for_selector(DRAWN[name], timeout=15000)


def test_the_files_tab_lists_every_file(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            names = page.eval_on_selector_all(
                ".filelist button .name", "els => els.map(e => e.textContent)")
            assert names[0] == "README.md"          # pinned
            assert set(names) == {"README.md", "NOTES.md", "code.py"}
            assert "The readme" in page.locator(".filebody .prose").inner_text()
        finally:
            browser.close()


def test_a_file_that_is_not_markdown_is_shown_as_it_is(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.click(".filelist button:has-text('code.py')")
            page.wait_for_timeout(700)
            assert page.locator(".filebody .prose").count() == 0
            assert "print(1)" in page.locator(".filebody pre.plain").inner_text()
        finally:
            browser.close()


def test_a_changed_file_is_marked(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            touched = page.eval_on_selector_all(
                ".filelist button.touched .name", "els => els.map(e => e.textContent)")
            assert sorted(touched) == ["NOTES.md", "README.md"]
        finally:
            browser.close()


def test_typing_finds_a_file_by_scattered_letters(repo_page):
    """A file picker, not a filter: `nsmd` has to find NOTES.md the way it does
    in an editor. The letters must turn up in that order, but not together,
    and the ones that matched are picked out."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.fill("#find", "nsmd")
            page.wait_for_timeout(400)
            names = page.eval_on_selector_all(
                ".filelist button .name", "els => els.map(e => e.textContent)")
            assert names == ["NOTES.md"]
            lit = page.eval_on_selector_all(
                ".filelist .lit", "els => els.map(e => e.textContent).join('')")
            assert lit.lower() == "nsmd"
            # The letters have to be in order; these are the same four, not.
            page.fill("#find", "dmsn")
            page.wait_for_timeout(400)
            assert page.locator(".filelist button").count() == 0
        finally:
            browser.close()


def test_the_best_match_comes_first(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.fill("#find", "py")
            page.wait_for_timeout(400)
            names = page.eval_on_selector_all(
                ".filelist button .name", "els => els.map(e => e.textContent)")
            assert names[0] == "code.py"
        finally:
            browser.close()


def test_a_name_that_matches_nothing_says_so(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.fill("#find", "zzqq")
            page.wait_for_timeout(400)
            assert page.locator(".filelist button").count() == 0
            assert "no name matches" in page.locator(".listnote").inner_text()
        finally:
            browser.close()


def test_another_file_is_shown_when_it_is_picked(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.click(".filelist button:has-text('NOTES.md')")
            page.wait_for_timeout(700)
            assert "Notes" in page.locator(".filebody .prose").inner_text()
        finally:
            browser.close()


def test_a_hostile_file_cannot_run_either(repo_page):
    """The Files tab renders a file the agent may never have looked at, so the
    scrub matters here at least as much as in the transcript."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.click(".filelist button:has-text('NOTES.md')")
            page.wait_for_timeout(700)
            assert page.evaluate("window.PWNED ?? null") is None
            assert page.locator(".filebody img").count() == 0
            assert page.locator(".filebody script").count() == 0
            assert "onerror" in page.locator(".filebody .prose").inner_text()
        finally:
            browser.close()


def test_an_edited_file_is_read_again_without_losing_the_place(repo_page):
    root, _ = repo_page
    long_file = "# The readme\n\n" + "\n\n".join(f"line {n}" for n in range(400))
    (root / "README.md").write_text(long_file)
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.eval_on_selector(".filebody", "el => el.scrollTop = 900")
            (root / "README.md").write_text(long_file + "\n\nand one more\n")
            # Wait for the new line to arrive, not for a poll to have passed.
            page.wait_for_function(
                "document.querySelector('.filebody .prose').innerText"
                ".includes('and one more')", timeout=15000)
            where = page.eval_on_selector(".filebody", "el => el.scrollTop")
            assert where > 500, "the reader was thrown back to the top"
        finally:
            browser.close()


def test_touching_another_file_leaves_the_open_one_alone(repo_page):
    """The sidebar and the document are redrawn apart. One key over both meant
    that an agent saving any Markdown re-rendered the file you were reading,
    every two seconds, and threw away where you were in it."""
    root, _ = repo_page
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.evaluate(
                "window.__doc = document.querySelector('.filebody .prose')")
            (root / "NOTES.md").write_text("# Notes\n\ntouched again\n")
            page.wait_for_timeout(3000)       # two polls
            assert page.evaluate("window.__doc.isConnected"), \
                "the open document was rebuilt for another file's change"
        finally:
            browser.close()


def test_the_find_box_sits_above_the_file_list(repo_page):
    """One box, moved to where it is used. Two would be two values to keep in
    step, and `/` would have to guess which one it meant."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            assert page.eval_on_selector(
                "#find", "el => el.parentElement.id") == "findhome"
            show_tab(page, "files")
            assert page.eval_on_selector(
                "#find", "el => el.parentElement.className") == "findslot"
            assert page.eval_on_selector(
                "#find", "el => el.closest('.side') !== null")
            # and it goes back when a tab without a list is chosen
            show_tab(page, "transcript")
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


def test_a_tab_comes_back_after_visiting_the_transcript(repo_page):
    """The content box says which tab built it, and `split` rebuilds when that
    is another tab. The transcript emptied the box without saying so, and the
    next Files draw believed its columns were still there."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            for name in ("files", "diff"):
                show_tab(page, name)
                assert page.locator(".filelist button").count() > 0
                show_tab(page, "transcript")
                assert page.locator(".filelist").count() == 0
                show_tab(page, name)
                assert page.locator(".filelist button").count() > 0, name
                assert page.eval_on_selector(
                    "#find", "el => el.parentElement.className") == "findslot"
        finally:
            browser.close()


def test_the_dot_appears_when_a_quiet_file_is_touched(repo_page):
    """The marker is part of what the list was drawn from. Left out of the
    key, it only ever appeared when the sort order happened to move too."""
    from conftest import git_in as git

    root, _ = repo_page
    # A pinned file sits in the same place whether it has changed or not, so
    # the marker is the only thing that can say it did. A file that moves up
    # the list when it changes hides the bug.
    (root / "CLAUDE.md").write_text("# claude\n")
    git(root, "add", "CLAUDE.md")
    git(root, "commit", "-qm", "claude")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.wait_for_selector(".filelist button")
            where = ".filelist button.touched:has-text('CLAUDE.md')"
            assert page.locator(where).count() == 0
            assert page.eval_on_selector_all(
                ".filelist button .name",
                "els => els.map(e => e.textContent)")[0] == "CLAUDE.md"
            (root / "CLAUDE.md").write_text("# claude\n\nedited\n")
            # Wait for the dot, not for long enough that it must have come.
            page.wait_for_selector(where, timeout=15000)
            names = page.eval_on_selector_all(
                ".filelist button .name", "els => els.map(e => e.textContent)")
            assert names[0] == "CLAUDE.md", "it should not have moved"
        finally:
            browser.close()


def test_a_worktree_without_markdown_says_so(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            show_tab(page, "files")
            assert "no file that git knows about" in \
                page.locator(".filebody").inner_text()
        finally:
            browser.close()


def test_the_diff_tab_keeps_the_two_halves_apart(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            heads = page.eval_on_selector_all(
                ".diffhead", "els => els.map(e => e.textContent)")
            assert heads == ["main...HEAD", "not committed yet"]
            paths = page.eval_on_selector_all(
                ".dfile .path", "els => els.map(e => e.textContent)")
            assert paths == ["code.py", "README.md"]
        finally:
            browser.close()


def test_the_diff_colours_what_changed(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            assert page.locator(".dline.added").count() >= 2
            # The numbers come first in the row; `.dtext` is the line itself.
            added = page.eval_on_selector_all(
                ".dline.added .dtext", "els => els.map(e => e.textContent)")
            assert any("second line" in line for line in added)
            assert all(line.startswith("+") for line in added)
        finally:
            browser.close()


def test_the_diff_tab_carries_its_counts(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            badge = page.locator("#diffcount").inner_text()
            assert badge.startswith("+2")     # one line in each half
        finally:
            browser.close()


def test_an_untracked_file_is_named(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            # The names are listed once, on the left; the note says what they
            # are. Printing them in both places was the same list twice.
            names = page.eval_on_selector_all(
                ".filelist button", "els => els.map(e => e.textContent)")
            assert "NOTES.md" in names
            assert "1 untracked file" in page.locator(".diffbody .note").inner_text()
        finally:
            browser.close()


def test_an_untracked_file_opens_as_one_added_block(repo_page):
    """git has no diff for it, so it was named and left unclickable — the one
    thing on the tab you could not open."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.click(".filelist button:has-text('NOTES.md')")
            page.wait_for_timeout(700)
            block = page.locator(".dfile:has(.what:text-is('untracked'))")
            assert block.count() == 1
            assert block.locator(".path").inner_text() == "NOTES.md"
            first = block.locator(".dline.added .dtext").first.inner_text()
            assert first == "+# Notes"
            assert block.locator(".dline.removed").count() == 0
            # It is numbered and lined up like every other block. Nothing was
            # removed, so the old side's column stays empty all the way down.
            assert numbers(page, ".dfile:has(.what:text-is('untracked'))"
                           )[:3] == [["", "1"], ["", "2"], ["", "3"]]
        finally:
            browser.close()


def test_git_failing_does_not_read_as_an_empty_worktree(repo_page):
    """"No files" and "git did not answer" look the same and mean opposite
    things. A two second timeout over fifty thousand files drew the first."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.evaluate("state.names = []; state.file = null;"
                          " state.filesFailed = true; draw()")
            page.wait_for_timeout(200)
            said = page.locator(".filebody .empty").inner_text()
            assert "git did not answer" in said
            assert "holds no file" not in said
        finally:
            browser.close()


def test_the_find_box_narrows_the_file_list(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.fill("#find", "readme")
            page.wait_for_timeout(400)
            paths = page.eval_on_selector_all(
                ".dfile .path", "els => els.map(e => e.textContent)")
            assert paths == ["README.md"]
        finally:
            browser.close()


def test_a_long_file_starts_closed_and_opens_on_click(repo_page):
    root, _ = repo_page
    import subprocess
    (root / "big.txt").write_text("\n".join(f"line {n}" for n in range(60)))
    subprocess.run(["git", "-C", str(root), "add", "big.txt"], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "big"], check=True,
                   capture_output=True)
    (root / "big.txt").write_text("\n".join(f"changed {n}" for n in range(60)))
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_timeout(400)
            # The page owns the cut-off, so the test moves the page's own
            # number rather than pretending the daemon sent a different one.
            page.evaluate("BIG_LINES = 20; state.diffAt += 1; draw()")
            page.wait_for_timeout(200)
            big = page.locator(".dfile:has-text('big.txt')").last
            assert "hidden" in big.locator(".why").inner_text()
            assert big.locator(".dline").count() == 0
            big.locator(".name").click()
            page.wait_for_timeout(200)
            assert big.locator(".dline").count() > 20
        finally:
            browser.close()


def test_every_tab_is_built(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            for name in ("transcript", "files", "diff", "peek"):
                assert not page.locator(f".tab[data-tab='{name}']").is_disabled()
        finally:
            browser.close()


def test_a_directory_that_is_not_a_repository_says_so(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            show_tab(page, "diff")
            assert "no branch to compare" in page.locator(".diffbody").inner_text()
            assert page.locator("#diffcount").is_hidden()
        finally:
            browser.close()


def test_typing_finds_a_file_past_the_first_five_thousand(big_page):
    """The listing stopped at 5000 names sorted by name, so everything under
    `native/` was cut before the matcher saw it. In a 52,799 file repository
    `libcorrelation` found 16 files and missed more than a thousand."""
    with sync_playwright() as play:
        browser, page = open_page(play, big_page)
        try:
            show_tab(page, "files")
            page.fill("#find", "libcorrelation")
            page.wait_for_timeout(600)
            # Typing filters the tree; it does not replace it. The one match
            # is there with the directories that lead to it, and nothing else.
            names = page.eval_on_selector_all(
                ".filelist button", "els => els.map(e => e.title)")
            assert names == ["native", "native/shared",
                             "native/shared/libcorrelation",
                             "native/shared/libcorrelation/src",
                             "native/shared/libcorrelation/src/Action.h"]
            files = page.eval_on_selector_all(
                ".filelist button:not(.dir)", "els => els.map(e => e.title)")
            assert files == ["native/shared/libcorrelation/src/Action.h"]
        finally:
            browser.close()


# --- syntax highlighting ----------------------------------------------------

# The highlighter is fetched, not vendored, so every test here works whether
# or not the machine running it can reach a CDN: the page is handed a stand-in
# and the real download is never started.

STUB = """hljsAsked = Promise.resolve({
  getLanguage: () => true,
  highlight: (text, how) => ({ value: %s }),
});"""


def open_code(page, stub, name="code.py"):
    """Put a stand-in highlighter in place, then open a file that is not
    Markdown."""
    show_tab(page, "files")
    page.evaluate(STUB % stub)
    page.click(f".filelist button:has-text('{name}')")
    page.wait_for_timeout(400)


def test_code_is_painted(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            open_code(page, "'<span class=\"hljs-keyword\">print</span>(1)'")
            assert page.locator(".filebody pre.plain .hljs-keyword").inner_text() == "print"
            assert page.locator(".filebody pre.plain").inner_text() == "print(1)"
        finally:
            browser.close()


def test_the_page_does_not_trust_the_highlighter_either(repo_page):
    """Its output goes through the same inert template the Markdown does. A
    span dressed as our own chrome, an attribute, and an element that is not a
    span all come out as text."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            open_code(page, "'<span class=\"row\" onclick=\"x()\">a</span>'"
                            " + '<img src=x onerror=\"window.pwned=1\">'"
                            " + '<span class=\"hljs-string\" id=\"n\">b</span>'")
            body = page.locator(".filebody pre.plain")
            assert page.evaluate("window.pwned") is None
            assert body.locator("img").count() == 0
            assert body.locator(".row").count() == 0
            assert body.locator("[onclick]").count() == 0
            assert body.locator("#n").count() == 0
            # the text survives, only the dressing is gone
            assert body.locator(".hljs-string").inner_text() == "b"
            assert body.inner_text() == "ab"
        finally:
            browser.close()


def test_a_sublanguage_class_survives(repo_page):
    """hljs writes `hljs-title function_` as one span with two classes."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            open_code(page, "'<span class=\"hljs-title function_\">go</span>'")
            assert page.locator(".filebody pre.plain .hljs-title.function_").count() == 1
        finally:
            browser.close()


def test_no_highlighter_still_shows_the_file(repo_page):
    """Offline, blocked, or bytes that do not match the hash: the code is
    still code, just unpainted."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.evaluate("hljsAsked = Promise.resolve(null);")
            page.click(".filelist button:has-text('code.py')")
            page.wait_for_timeout(400)
            assert page.locator(".filebody pre.plain").inner_text().strip() == (
                "print(1)\nprint(2)")
            assert page.locator(".filebody pre.plain span").count() == 0
        finally:
            browser.close()


def test_the_highlighter_is_pinned_and_asked_for_late(repo_page):
    """Any script on this page can POST to /send, which types into a terminal,
    so a script from someone else's server carries the hash of its bytes. And
    a session that only reads transcripts reaches the network never."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            asked = "document.querySelectorAll('script[src*=highlight]').length"
            assert page.evaluate(asked) == 0      # the transcript asks for nothing
            show_tab(page, "files")
            assert page.evaluate(asked) == 0      # nor does a Markdown file
            page.click(".filelist button:has-text('code.py')")
            page.wait_for_timeout(400)
            tag = page.locator("script[src*='highlight']")
            assert tag.count() == 1
            assert tag.get_attribute("src").startswith("https://")
            assert tag.get_attribute("integrity").startswith("sha384-")
            assert tag.get_attribute("crossorigin") == "anonymous"
        finally:
            browser.close()


def test_a_file_that_is_not_markdown_has_no_box(repo_page):
    """A shell script is the whole page here, not a quotation inside a
    document that does not exist."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.click(".filelist button:has-text('code.py')")
            page.wait_for_timeout(400)
            look = page.eval_on_selector(".filebody pre.plain", """el => {
              const seen = getComputedStyle(el);
              return [seen.borderTopWidth, seen.backgroundColor];
            }""")
            assert look[0] == "0px"
            assert look[1] in ("rgba(0, 0, 0, 0)", "transparent")
        finally:
            browser.close()


def test_without_marked_the_transcript_is_still_readable(page_at):
    """Markdown is written to be read as plain text, so a fetch that never
    arrives costs the rendering and nothing else. The tab is never blank."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at, with_marked=False)
        try:
            page.wait_for_timeout(700)
            assert page.evaluate("!!window.marked") is False
            said = page.locator(".prose").first.inner_text()
            assert said                       # there is text, not an empty box
            assert page.locator(".prose h1, .prose h2, .prose ul").count() == 0
            assert page.locator(".nohits").count() == 0
        finally:
            browser.close()


def test_marked_is_pinned_too(page_at):
    """Both fetched scripts carry the hash of their bytes. The page is served
    the real marked here, so this checks the pin as the browser does."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.wait_for_timeout(700)
            assert page.evaluate("!!window.marked") is True
            tag = page.locator("script[src*='marked']")
            assert tag.count() == 1
            assert tag.get_attribute("src").startswith("https://")
            assert tag.get_attribute("integrity").startswith("sha384-")
            assert tag.get_attribute("crossorigin") == "anonymous"
        finally:
            browser.close()


def test_only_the_rows_on_screen_are_built(big_page):
    """Every row is one height, so two spacers can stand in for the rest. Ten
    thousand matches then cost the same as ten."""
    with sync_playwright() as play:
        browser, page = open_page(play, big_page)
        try:
            show_tab(page, "files")
            # 5201 files, and a screenful of rows.
            assert "5201" in page.locator(".listnote").inner_text()
            built = page.locator(".filelist button").count()
            assert 0 < built <= 120, built

            # The scrollbar still runs the whole length of the list.
            reach = page.eval_on_selector(".filelist", "el => el.scrollHeight")
            assert reach > 5000 * 20, reach

            first = page.eval_on_selector(
                ".filelist button", "el => el.title")
            page.eval_on_selector(".filelist", "el => el.scrollTop = 40000")
            page.wait_for_timeout(250)
            moved = page.eval_on_selector(".filelist button", "el => el.title")
            assert moved != first, "the window did not follow the scrollbar"
            assert page.locator(".filelist button").count() <= 120
        finally:
            browser.close()


def test_a_name_is_still_found_after_scrolling(big_page):
    """The window is where you are in the list, not what the list holds."""
    with sync_playwright() as play:
        browser, page = open_page(play, big_page)
        try:
            show_tab(page, "files")
            page.eval_on_selector(".filelist", "el => el.scrollTop = 40000")
            page.wait_for_timeout(250)
            page.fill("#find", "libcorrelation")
            page.wait_for_timeout(400)
            files = page.eval_on_selector_all(
                ".filelist button:not(.dir)", "els => els.map(e => e.title)")
            assert files == ["native/shared/libcorrelation/src/Action.h"]
        finally:
            browser.close()


def test_the_reader_sees_the_named_files_then_what_changed(repo_page):
    """The daemon sends the names in an order that depends only on which files
    exist, so that the list the page holds stays good while an agent works.
    The three tiers the reader sees are built here, from the changed names and
    their times."""
    root, _ = repo_page
    # Untracked counts as changed, so this one is not quiet: it is the newest
    # change. `code.py` is committed and untouched, and that is the quiet one.
    (root / "a-first-by-name.txt").write_text("new\n")
    os.utime(root / "a-first-by-name.txt", (2_000_000_000, 2_000_000_000))
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.wait_for_selector(".filelist button.touched")
            names = page.eval_on_selector_all(
                ".filelist button", "els => els.map(e => e.title)")
            assert names[0] == "README.md"              # pinned
            assert names[1] == "a-first-by-name.txt"    # the newest change
            assert names[2] == "NOTES.md"               # the older change
            assert names[3] == "code.py"                # quiet, so last
        finally:
            browser.close()


def test_the_newest_change_leads_the_ones_that_changed(repo_page):
    root, _ = repo_page
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.wait_for_selector(".filelist button.touched")
            (root / "code.py").write_text("print(3)\n")
            os.utime(root / "code.py", (2_000_000_000, 2_000_000_000))
            page.wait_for_selector(
                ".filelist button.touched:has-text('code.py')", timeout=15000)
            names = page.eval_on_selector_all(
                ".filelist button", "els => els.map(e => e.title)")
            assert names[0] == "README.md"           # pinned, so it still wins
            assert names[1] == "code.py", names[:4]  # the newest change
        finally:
            browser.close()


# --- the tree ---------------------------------------------------------------


def test_the_list_is_a_tree_that_opens_and_closes(big_page):
    """A closed repository costs its top level and no more."""
    with sync_playwright() as play:
        browser, page = open_page(play, big_page)
        try:
            show_tab(page, "files")
            shut = page.locator(".filelist button.dir:has-text('native')")
            assert shut.count() == 1
            # 5201 files, and only a window of rows exists.
            assert page.locator(".filelist button").count() <= 100
            # Nothing inside the closed directory has been built at all.
            assert page.locator(".filelist button[title^='native/']").count() == 0

            page.click(".filelist button.dir:has-text('native')")
            page.wait_for_selector(".filelist button.dir.open")
            names = page.eval_on_selector_all(
                ".filelist button", "els => els.map(e => e.textContent)")
            assert "shared" in " ".join(names), names

            page.click(".filelist button.dir.open")
            page.wait_for_timeout(200)
            assert page.locator(".filelist button.dir.open").count() == 0
        finally:
            browser.close()


def test_a_directory_holding_a_change_opens_itself(repo_page):
    """A closed tree cannot say what the agent just did, and that is the
    question this tool exists to answer."""
    root, _ = repo_page
    (root / "deep").mkdir()
    (root / "deep" / "quiet.txt").write_text("nothing\n")
    from conftest import git_in as git
    git(root, "add", "deep"), git(root, "commit", "-qm", "deep")
    (root / "src").mkdir()
    (root / "src" / "touched.txt").write_text("the agent wrote this\n")

    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.wait_for_selector(".filelist button.dir.open")
            opened = page.eval_on_selector_all(
                ".filelist button.dir.open", "els => els.map(e => e.title)")
            assert opened == ["src"], opened
            # and the file inside it is on screen, marked
            assert page.locator(
                ".filelist button.touched:has-text('touched.txt')").count() == 1
            # the directory that holds nothing new stays shut, but says so
            shut = page.locator(".filelist button.dir:has-text('deep')")
            assert "open" not in (shut.get_attribute("class") or "")
        finally:
            browser.close()


def test_a_closed_directory_still_says_a_change_is_inside(repo_page):
    root, _ = repo_page
    (root / "src").mkdir()
    (root / "src" / "touched.txt").write_text("the agent wrote this\n")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.wait_for_selector(".filelist button.dir.open")
            page.click(".filelist button.dir.open")          # close it by hand
            page.wait_for_timeout(250)
            shut = page.locator(".filelist button.dir:has-text('src')")
            assert "touched" in (shut.get_attribute("class") or "")
            assert "open" not in (shut.get_attribute("class") or "")
        finally:
            browser.close()


def test_closing_a_directory_by_hand_beats_opening_it_for_you(repo_page):
    """The tree never fights the hand on it."""
    root, _ = repo_page
    (root / "src").mkdir()
    (root / "src" / "touched.txt").write_text("one\n")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.wait_for_selector(".filelist button.dir.open")
            page.click(".filelist button.dir.open")
            page.wait_for_timeout(250)
            # another change lands in the same directory
            (root / "src" / "second.txt").write_text("two\n")
            page.wait_for_timeout(3000)       # two polls
            assert page.locator(".filelist button.dir.open").count() == 0, \
                "it re-opened a directory the reader had closed"
        finally:
            browser.close()


# --- the three tmux verbs ---------------------------------------------------


@pytest.fixture
def in_pane(ws, served, tmp_path, monkeypatch, transcript_file):
    """A session in a pane, with tmux replaced by a runner that records.

    The recording lives on the daemon so a test can read what the page asked
    the terminal to do.
    """
    monkeypatch.setattr(ws, "git_facts_many", lambda dirs: {
        d: ws.GitFacts(repo="repo", branch="main") for d in dirs})
    monkeypatch.setattr(ws, "pid_alive", lambda pid: True)
    seen = []

    def runner(args, **rest):
        seen.append(list(args))
        if "capture-pane" in args:
            return "\x1b[1;32mall good\x1b[0m\nwaiting"
        return ""

    monkeypatch.setattr(ws, "run", runner)
    transcript = transcript_file("s1", [
        {"type": "user", "timestamp": "2026-09-18T14:02:00.000Z",
         "message": {"role": "user", "content": "Do the thing."}},
    ])
    daemon, base = served
    ws.append_event({"session_id": "s1", "hook_event_name": "SessionStart",
                     "cwd": str(tmp_path), "pane": "%7", "pid": 1,
                     "ts": time.time(), "transcript_path": str(transcript)})
    daemon.store.refresh()
    return daemon, base, seen


def test_jump_puts_the_cursor_in_the_pane(in_pane):
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.click("#jump")
            page.wait_for_timeout(400)
            assert ["tmux", "select-window", "-t", "%7"] in seen
            assert ["tmux", "select-pane", "-t", "%7"] in seen
        finally:
            browser.close()


def test_the_send_box_types_into_the_terminal(in_pane):
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.fill("#say", "run the tests")
            page.press("#say", "Enter")
            page.wait_for_timeout(500)
            assert ["tmux", "send-keys", "-t", "%7", "-l", "--",
                    "run the tests"] in seen
            assert ["tmux", "send-keys", "-t", "%7", "Enter"] in seen
            # cleared only once the daemon said it went in
            assert page.input_value("#say") == ""
        finally:
            browser.close()


def test_the_send_box_keeps_the_text_when_it_did_not_go_in(ws, in_pane,
                                                           monkeypatch):
    """They typed it at a terminal they cannot see. Losing it is not on."""
    daemon, base, seen = in_pane
    monkeypatch.setattr(ws, "run", lambda args, **rest: None)
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.fill("#say", "please work")
            page.press("#say", "Enter")
            page.wait_for_timeout(500)
            assert page.input_value("#say") == "please work"
        finally:
            browser.close()


@pytest.fixture
def no_pane(ws, served, tmp_path, monkeypatch):
    """A session that is not running under tmux at all."""
    monkeypatch.setattr(ws, "git_facts_many", lambda dirs: {
        d: ws.GitFacts(repo="repo", branch="main") for d in dirs})
    monkeypatch.setattr(ws, "pid_alive", lambda pid: True)
    daemon, base = served
    ws.append_event({"session_id": "s1", "hook_event_name": "SessionStart",
                     "cwd": str(tmp_path), "pane": "", "pid": 1,
                     "ts": time.time()})
    daemon.store.refresh()
    return daemon, base


def test_the_verbs_are_not_there_without_a_pane(no_pane):
    """Nothing to jump to, nothing to type into."""
    with sync_playwright() as play:
        browser, page = open_page(play, (None, no_pane[1]))
        try:
            assert page.locator("#jump").is_hidden()
            assert page.locator("#sendbar").is_hidden()
            assert "not in tmux" in page.locator("#facts").inner_text()
        finally:
            browser.close()


def test_the_send_box_belongs_to_the_transcript(in_pane):
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base_of(in_pane)))
        try:
            assert page.locator("#sendbar").is_visible()
            show_tab(page, "files")
            assert page.locator("#sendbar").is_hidden()
            show_tab(page, "transcript")
            assert page.locator("#sendbar").is_visible()
        finally:
            browser.close()


def base_of(in_pane):
    return in_pane[1]


def test_peek_shows_the_pane_in_its_colours(in_pane):
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base_of(in_pane)))
        try:
            show_tab(page, "peek")
            page.wait_for_selector(".peek b")
            assert page.locator(".peek").inner_text().startswith("all good")
            green = page.eval_on_selector(".peek b", "el => el.style.color")
            assert "--ansi-2" in green
            assert "waiting" in page.locator(".peek").inner_text()
        finally:
            browser.close()


def test_peek_never_reads_what_a_terminal_printed_as_markup(ws, in_pane,
                                                            monkeypatch):
    """A pane can hold anything an agent ran. Every run is set with
    textContent, so it is shown, never obeyed."""
    monkeypatch.setattr(ws, "run", lambda args, **rest:
                        "<img src=x onerror=\"window.pwned=1\">"
                        "<script>window.pwned=1</script>done")
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base_of(in_pane)))
        try:
            show_tab(page, "peek")
            page.wait_for_timeout(600)
            assert page.evaluate("window.pwned") is None
            assert page.locator(".peek img, .peek script").count() == 0
            assert "onerror" in page.locator(".peek").inner_text()
        finally:
            browser.close()


def test_peek_says_so_when_there_is_no_pane(no_pane):
    with sync_playwright() as play:
        browser, page = open_page(play, (None, no_pane[1]))
        try:
            show_tab(page, "peek")
            page.wait_for_timeout(500)
            assert "not in tmux" in page.locator(".peek").inner_text()
        finally:
            browser.close()


# --- moving between tabs ----------------------------------------------------

def test_every_way_from_one_tab_to_another_works(repo_page):
    """There is one find box and it lives inside the content box on a split
    tab. A tab that empties that box without giving it back destroys it, and
    then `showTab` throws on the next `$("find")` — before it reaches `load`,
    so the tab never loads, and every switch after it throws as well. The page
    stayed broken until a reload. Peek did exactly this.
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
            # and the find box is still there, still working
            show_tab(page, "files")
            page.fill("#find", "code")
            page.wait_for_timeout(400)
            assert page.locator(".filelist button").count() == 1
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
            for name in ["files", "diff", "peek", "transcript", "peek", "files",
                         "transcript", "diff", "peek", "files"]:
                page.click(f".tab[data-tab='{name}']")
                page.wait_for_timeout(110)      # quicker than a human, on purpose
            page.wait_for_selector(DRAWN["files"], timeout=15000)
            assert page.evaluate("$('content').dataset.tab") == "files"
            assert not blew_up, blew_up
        finally:
            browser.close()


def test_typing_filters_the_tree_rather_than_flattening_it(big_page):
    """Where a file sits is half of what you know about it, and a flat list of
    matches throws that away."""
    with sync_playwright() as play:
        browser, page = open_page(play, big_page)
        try:
            show_tab(page, "files")
            page.fill("#find", "Action")
            page.wait_for_timeout(600)
            rows = page.eval_on_selector_all(".filelist button", """els => els.map(
              (e) => [e.title, e.className.includes("dir"),
                      parseInt(e.style.paddingLeft)])""")
            # the directories that lead to it are there, and they step in
            assert [one[0] for one in rows if one[1]] == [
                "native", "native/shared", "native/shared/libcorrelation",
                "native/shared/libcorrelation/src"]
            assert [one[2] for one in rows] == [14, 27, 40, 53, 66]
            # a row shows its own name, not the whole path
            assert page.eval_on_selector_all(
                ".filelist button", "els => els.map(e => e.textContent)"
            )[-1] == "Action.h"
            # The letters that matched are picked out on the rows that own
            # them, wherever in the path they fell. `action` finds its `a` in
            # `native`, so that is where it is shown.
            lit = page.eval_on_selector_all(
                ".filelist .lit", "els => els.map(e => e.textContent).join('')")
            assert lit.lower() == "action"
        finally:
            browser.close()


def test_clearing_the_box_puts_the_whole_tree_back(big_page):
    with sync_playwright() as play:
        browser, page = open_page(play, big_page)
        try:
            show_tab(page, "files")
            page.fill("#find", "Action")
            page.wait_for_timeout(500)
            assert page.locator(".filelist button:not(.dir)").count() == 1
            page.fill("#find", "")
            page.wait_for_timeout(500)
            assert page.locator(".filelist button:not(.dir)").count() > 50
            # closed again, as it was
            assert page.locator(".filelist button.dir.open").count() == 0
        finally:
            browser.close()


# --- line numbers -----------------------------------------------------------


def numbers(page, under):
    """The two line numbers of every row under a selector.

    They share one element, lined up with spaces: a diff row is monospace and
    already `white-space: pre`, so a flex box and an element per column would
    be three more nodes a line for nothing.
    """
    return page.eval_on_selector_all(
        under + " .dline .ln",
        """els => els.map((e) => [e.textContent.slice(0, 5).trim(),
                                  e.textContent.slice(5, 11).trim()])""")


def test_a_file_is_numbered_beside_the_code_not_inside_it(repo_page):
    """The numbers are not the file, so copying the code does not take them,
    and the highlighter can rewrite everything to their right."""
    root, _ = repo_page
    (root / "code.py").write_text("one\ntwo\nthree\nfour\n")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.click(".filelist button:has-text('code.py')")
            page.wait_for_selector(".filebody .code .nums")
            assert page.locator(".filebody .nums").inner_text() == "1\n2\n3\n4"
            assert page.locator(".filebody pre.plain .ln").count() == 0
            # both columns share a line height, so they stay level
            look = page.eval_on_selector_all(
                ".filebody .code pre",
                "els => els.map(e => getComputedStyle(e).lineHeight)")
            assert look[0] == look[1]
            assert page.eval_on_selector(
                ".filebody .nums", "el => getComputedStyle(el).userSelect"
            ) == "none"
        finally:
            browser.close()


def test_markdown_has_no_line_numbers(repo_page):
    """It is prose, not code."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.wait_for_selector(".filebody .prose")
            assert page.locator(".filebody .nums").count() == 0
        finally:
            browser.close()


def test_a_diff_line_carries_the_number_it_had_on_each_side(repo_page):
    """`@@ -12,7 +14,9 @@` says where the hunk starts on each side, and the
    rest follows from which lines are there. A removed line has no number on
    the new side and an added one has none on the old side."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(".dline")
            rows = page.eval_on_selector_all(".dfile .dline", """els => els.map(
              (e) => [e.className.replace("dline ", ""),
                      e.children[0].textContent.slice(0, 5).trim(),
                      e.children[0].textContent.slice(5, 11).trim(),
                      e.children[1].textContent])""")
            assert rows, "no diff lines at all"
            for kind, old, now, text in rows:
                if kind == "added":
                    assert old == "" and now != "", (kind, old, now)
                elif kind == "removed":
                    assert now == "" and old != "", (kind, old, now)
                else:
                    assert old != "" and now != "", (kind, old, now)
            # a context line before an added one keeps its own number
            context = [one for one in rows if one[0] == "context"]
            assert context and context[0][1] == context[0][2]
        finally:
            browser.close()


def test_diff_numbers_are_not_copied_with_the_diff(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(".dline .ln")
            assert page.eval_on_selector(
                ".dline .ln", "el => getComputedStyle(el).userSelect") == "none"
        finally:
            browser.close()


def test_picking_an_untracked_file_moves_the_pane_to_it(repo_page):
    """It is built below everything else, and the pane used to scroll straight
    back to where the reader was, so the click looked like it did nothing."""
    root, _ = repo_page
    # A diff long enough that the pane scrolls at all: the untracked block is
    # built after every hunk, so without the jump it is far below the fold.
    (root / "README.md").write_text(
        "# The readme\n\n" + "".join(f"line {n}\n" for n in range(300)))
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(".dline")
            assert page.eval_on_selector(
                ".diffbody", "el => el.scrollHeight > el.clientHeight + 400"
            ), "the pane does not scroll, so this proves nothing"
            page.click(".filelist button:has-text('NOTES.md')")
            page.wait_for_selector(".dfile .what:text-is('untracked')")
            page.wait_for_timeout(600)
            where = page.eval_on_selector_all(
                ".diffbody, .dfile:has(.what:text-is('untracked'))", """els => {
                  const pane = els[0].getBoundingClientRect();
                  const block = els[1].getBoundingClientRect();
                  return { above: block.top - pane.top, tall: pane.height,
                           went: els[0].scrollTop };
                }""")
            # The pane moved, and the block is on screen rather than far below
            # it. The block is the last thing in the pane, so it can only come
            # as far up as the end of the scroll allows.
            assert where["went"] > 0, "the pane did not move at all"
            assert 0 <= where["above"] < where["tall"], where
        finally:
            browser.close()


# --- the send box -----------------------------------------------------------


def test_shift_and_enter_writes_a_second_line(in_pane):
    """Enter sends, which is what every chat box does. A prompt with a plan in
    it needs a way to write the second line."""
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            page.click("#say")
            page.keyboard.type("first line")
            page.keyboard.press("Shift+Enter")
            page.keyboard.type("second line")
            page.wait_for_timeout(300)
            assert page.input_value("#say") == "first line\nsecond line"
            assert seen == [], "shift and enter sent it"

            page.keyboard.press("Enter")
            page.wait_for_timeout(500)
            assert seen[0][-1] == ("\x1b[200~first line\nsecond line\x1b[201~")
            assert page.input_value("#say") == ""
        finally:
            browser.close()


def test_the_box_grows_with_what_is_in_it_and_shrinks_back(in_pane):
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
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
        finally:
            browser.close()


def test_a_long_line_wraps_rather_than_running_off_the_side(in_pane):
    """A prompt whose start you cannot see is worse than two lines."""
    daemon, base, seen = in_pane
    with sync_playwright() as play:
        browser, page = open_page(play, (None, base))
        try:
            one = page.eval_on_selector("#say", "el => el.clientHeight")
            page.fill("#say", "word " * 120)      # `fill` fires `input` itself
            page.wait_for_timeout(300)
            assert page.eval_on_selector("#say", "el => el.clientHeight") > one
            assert page.eval_on_selector(
                "#say", "el => el.scrollWidth <= el.clientWidth + 1"
            ), "it ran off the side instead of wrapping"
        finally:
            browser.close()


# --- the review: milestone 7 stage 1 -----------------------------------------


def open_diff(play, where):
    """The Diff tab of a real repository, drawn."""
    browser, page = open_page(play, where)
    show_tab(page, "diff")
    page.wait_for_selector(".dline")
    return browser, page


def test_a_diff_line_can_be_commented_on(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            assert page.locator(".comment").count() == 0
            page.locator(".dline .plus").first.click(force=True)
            page.wait_for_selector(".commentbox textarea")
            page.fill(".commentbox textarea", "use a signed type here")
            page.click(".commentbox .verb")
            page.wait_for_selector(".comment")
            assert "use a signed type here" in page.locator(".comment").inner_text()
            # It is written down, not held in the node it was drawn on.
            assert page.evaluate("state.review.length") == 1
            assert page.evaluate("state.review[0].anchor").count("\n") == 2
        finally:
            browser.close()


def test_the_plus_shows_when_you_are_on_the_line(repo_page):
    """It sits over the gutter and stays out of the way until you want it, the
    way a pull request does it — so "can you see it" is the whole feature."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            shown = ("() => getComputedStyle("
                     "document.querySelector('.dline .plus')).opacity")
            assert page.evaluate(shown) == "0"
            page.locator(".dline").first.hover()
            page.wait_for_function(shown + " === '1'")
            # And it is not part of the diff you copy, like the numbers by it.
            assert page.evaluate("() => getComputedStyle("
                                 "document.querySelector('.dline .plus'))"
                                 ".userSelect") == "none"
        finally:
            browser.close()


def test_a_whole_file_can_be_commented_on(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.locator(".onFile .plus").first.click()
            page.wait_for_selector(".commentbox textarea")
            page.fill(".commentbox textarea", "keep the heading order")
            page.click(".commentbox .verb")
            page.wait_for_selector(".onFile .comment")
            assert page.evaluate("state.review[0].anchor").endswith("\nfile\n0")
        finally:
            browser.close()


def test_a_comment_survives_the_diff_being_read_again(repo_page):
    """The poll replaces the whole answer every couple of seconds. A comment
    is anchored to the line, not to the node the line was drawn on."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.locator(".dline .plus").first.click(force=True)
            page.fill(".commentbox textarea", "look again")
            page.click(".commentbox .verb")
            page.wait_for_selector(".comment")
            page.evaluate("state.diffAt += 1; draw()")
            assert page.locator(".comment").count() == 1
            assert "look again" in page.locator(".comment").inner_text()
        finally:
            browser.close()


def test_an_open_box_is_not_swept_away_by_the_poll(repo_page):
    """An agent saving a file rebuilds the diff. Doing that under an open box
    would take what is being typed with it, and would move the code the
    comment is about while it is being written."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.locator(".dline .plus").first.click(force=True)
            page.wait_for_selector(".commentbox textarea")
            page.fill(".commentbox textarea", "half a thought")
            page.evaluate("state.diffAt += 1; draw()")
            assert page.input_value(".commentbox textarea") == "half a thought"
        finally:
            browser.close()


def test_a_comment_can_be_edited_and_emptied_away(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.locator(".dline .plus").first.click(force=True)
            page.fill(".commentbox textarea", "first thought")
            page.click(".commentbox .verb")
            page.wait_for_selector(".comment")

            page.click(".comment .link")            # edit
            page.wait_for_selector(".commentbox textarea")
            assert page.input_value(".commentbox textarea") == "first thought"
            page.fill(".commentbox textarea", "second thought")
            page.click(".commentbox .verb")
            page.wait_for_function("state.review[0].note === 'second thought'")

            # Clearing the box and saving is how a comment goes away, so there
            # is no second thing to find and press.
            page.click(".comment .link")
            page.fill(".commentbox textarea", "   ")
            page.click(".commentbox .verb")
            page.wait_for_function("state.review.length === 0")
            assert page.locator(".comment").count() == 0
        finally:
            browser.close()


def test_cancel_leaves_the_comment_as_it_was(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.locator(".dline .plus").first.click(force=True)
            page.fill(".commentbox textarea", "kept")
            page.click(".commentbox .verb")
            page.wait_for_selector(".comment")
            page.click(".comment .link")
            page.fill(".commentbox textarea", "thrown away")
            page.click(".commentbox .link")         # cancel
            page.wait_for_selector(".comment")
            assert "kept" in page.locator(".comment").inner_text()
            assert page.evaluate("state.review.length") == 1
        finally:
            browser.close()


def test_the_review_belongs_to_the_session_it_is_about(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.locator(".dline .plus").first.click(force=True)
            page.fill(".commentbox textarea", "about this session")
            page.click(".commentbox .verb")
            page.wait_for_function("state.review.length === 1")
            page.evaluate("choose('someone-else')")
            assert page.evaluate("state.review.length") == 0
        finally:
            browser.close()


def test_nothing_is_sent_yet(repo_page):
    """Stage 1 of milestone 7 draws and keeps a review. Sending it is stage 2,
    and until then nothing here may reach the terminal."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.evaluate("window.__posts = []; const real = window.fetch;"
                          " window.fetch = (u, o) => { window.__posts.push(String(u));"
                          " return real(u, o); };")
            page.locator(".dline .plus").first.click(force=True)
            page.fill(".commentbox textarea", "do not send me")
            page.click(".commentbox .verb")
            page.wait_for_selector(".comment")
            sent = page.evaluate("window.__posts.filter((u) => u.includes('/send'))")
            assert sent == []
        finally:
            browser.close()


# --- the review: milestone 7 stage 2 -----------------------------------------


def comment_on_first_line(page, note):
    page.locator(".dline .plus").first.click(force=True)
    page.wait_for_selector(".commentbox textarea")
    page.fill(".commentbox textarea", note)
    page.click(".commentbox .verb")
    page.wait_for_selector(".comment")


def test_there_is_no_submit_until_there_is_a_comment(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            assert page.locator(".verb.submit").count() == 0
            comment_on_first_line(page, "one thing")
            page.wait_for_selector(".verb.submit")
            assert "1" in page.locator(".verb.submit").inner_text()
        finally:
            browser.close()


def test_the_preview_is_the_message_itself(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "use a signed type here")
            page.click(".verb.submit")
            page.wait_for_selector("#review[open]")
            shown = page.locator("#reviewtext").inner_text()
            assert shown.startswith("Review: 1 comment on 1 file.")
            assert "use a signed type here" in shown
            assert "\n> " in shown, "the line it is about is quoted"
            # What is shown is what would be sent, byte for byte.
            assert shown.rstrip("\n") == page.evaluate("reviewText()").rstrip("\n")
        finally:
            browser.close()


def test_the_overall_note_goes_into_the_message_as_you_type(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "a line note")
            page.click(".verb.submit")
            page.wait_for_selector("#review[open]")
            page.fill("#overall", "mostly good, two things")
            page.wait_for_function(
                "document.getElementById('reviewtext')"
                ".textContent.includes('mostly good, two things')")
            shown = page.locator("#reviewtext").inner_text()
            # The note comes before the comments, as its own paragraph.
            assert shown.index("mostly good") < shown.index("a line note")
        finally:
            browser.close()


def test_the_message_is_ordered_by_file_and_line(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            # Written out of order on purpose: line 9, then the file, then 2.
            page.evaluate("""() => {
              state.review = [
                {anchor: "b.py\\nnew\\n9", quoted: "nine", note: "at nine"},
                {anchor: "b.py\\nfile\\n0", quoted: "", note: "about the file"},
                {anchor: "a.py\\nnew\\n2", quoted: "two", note: "at two"},
              ];
            }""")
            shown = page.evaluate("reviewText()")
            assert shown.startswith("Review: 3 comments on 2 files.")
            assert (shown.index("at two") < shown.index("about the file")
                    < shown.index("at nine"))
            assert "a.py:2" in shown and "b.py:9" in shown
            assert "b.py\nabout the file" in shown, "a file comment has no line"
        finally:
            browser.close()


def test_submitting_sends_it_and_empties_the_review(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "change this please")
            page.evaluate("""() => {
              window.__sent = [];
              const real = window.fetch;
              window.fetch = (url, opts) => {
                if (String(url).endsWith("/send")) {
                  window.__sent.push(JSON.parse(opts.body).text);
                  return Promise.resolve(new Response('{"done": true}'));
                }
                return real(url, opts);
              };
            }""")
            page.click(".verb.submit")
            page.wait_for_selector("#review[open]")
            page.click("#reviewsend")
            page.wait_for_function("window.__sent.length === 1")
            assert "change this please" in page.evaluate("window.__sent[0]")
            # It went, so it is gone from here: no sending the same twice.
            page.wait_for_function("state.review.length === 0")
            assert page.locator(".verb.submit").count() == 0
            assert page.evaluate("document.getElementById('review').open") is False
        finally:
            browser.close()


def test_cancel_keeps_the_review(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "still here")
            page.click(".verb.submit")
            page.wait_for_selector("#review[open]")
            page.fill("#overall", "typed and kept")
            page.click("#reviewstop")
            page.wait_for_function(
                "document.getElementById('review').open === false")
            assert page.evaluate("state.review.length") == 1
            page.click(".verb.submit")
            page.wait_for_selector("#review[open]")
            assert page.input_value("#overall") == "typed and kept"
        finally:
            browser.close()


def test_a_session_without_a_pane_cannot_be_sent_to(ws, served, repo):
    """The same rule the other verbs already follow: it can be written, it
    just has nowhere to go."""
    from conftest import git_in as git

    (repo / "code.py").write_text("print(1)\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "seed")
    (repo / "code.py").write_text("print(1)\nprint(2)\n")
    daemon, base = served
    ws.append_event(conftest.event("SessionStart", cwd=str(repo), pane="",
                                   ts=time.time(), pid=1))
    daemon.store.refresh()
    with sync_playwright() as play:
        browser, page = open_diff(play, (repo, base))
        try:
            comment_on_first_line(page, "nowhere to go")
            page.click(".verb.submit")
            page.wait_for_selector("#review[open]")
            assert page.locator("#reviewsend").is_disabled()
            assert "not running in tmux" in page.locator("#reviewwhy").inner_text()
        finally:
            browser.close()


def test_r_opens_the_review_and_escape_closes_it(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.press("body", "r")
            page.wait_for_timeout(100)
            assert page.evaluate("document.getElementById('review').open") is False, \
                "there is nothing to submit yet"
            comment_on_first_line(page, "something")
            page.press("body", "r")
            page.wait_for_selector("#review[open]")
            page.press("body", "Escape")
            page.wait_for_function(
                "document.getElementById('review').open === false")
        finally:
            browser.close()


# --- history: the sessions nobody can talk to any more ------------------------


@pytest.fixture
def past_at(ws, page_at, tmp_path):
    """The one-session page, with two finished sessions beside it."""
    daemon, url = page_at
    for name, reason in (("acorn", "clear"), ("beetroot", "logout")):
        where = tmp_path.parent / name
        where.mkdir(exist_ok=True)
        ws.append_event(conftest.event("SessionStart", sid=name, cwd=str(where),
                                       pane="%9", pid=2, ts=time.time()))
        ws.append_event(conftest.event("SessionEnd", sid=name, cwd=str(where),
                                       reason=reason, ts=time.time()))
    daemon.store.refresh()
    return daemon, url


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
            # The bar moves above the rows it opened.
            assert page.evaluate(
                "[...document.getElementById('rows').children]"
                ".findIndex((n) => n.classList.contains('histhead'))") == 1

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


def test_an_untracked_file_anchors_its_comments_to_itself(repo_page):
    """git has no diff for an untracked file, so it is drawn from a synthetic
    one. That object carried no path, so every untracked file's comments were
    anchored to `undefined` — and a comment on line 3 of one turned up on line
    3 of every other."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.click(".side button[title='NOTES.md']")
            page.wait_for_selector(".dfile .what:text('untracked')")
            page.wait_for_selector(".dline")
            page.locator(".dfile:has(.what:text('untracked')) .dline .plus").first.click(
                force=True)
            page.wait_for_selector(".commentbox textarea")
            page.fill(".commentbox textarea", "about the notes")
            page.click(".commentbox .verb")
            page.wait_for_function("state.review.length === 1")
            assert page.evaluate("state.review[0].anchor").startswith("NOTES.md\n")
            assert "NOTES.md:" in page.evaluate("reviewText()")
        finally:
            browser.close()


# --- the review: milestone 7 stage 3 -----------------------------------------


def test_a_review_survives_a_reload(repo_page):
    """A review is written over ten minutes. Losing it to an F5 is losing the
    work, so it is kept in this browser — and nowhere else."""
    with sync_playwright() as play:
        browser = fresh_context(play)
        try:
            page = browser.new_page()
            page.goto(repo_page[1], wait_until="domcontentloaded")
            page.wait_for_selector(".row")
            show_tab(page, "diff")
            page.wait_for_selector(".dline")
            comment_on_first_line(page, "still here after F5")

            # Reload on the comment alone, before anything else has had a
            # chance to save it: writing a comment is what has to keep it.
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector(".row")
            show_tab(page, "diff")
            page.wait_for_selector(".comment")
            assert "still here after F5" in page.locator(".comment").inner_text()

            page.click(".verb.submit")
            page.wait_for_selector("#review[open]")
            page.fill("#overall", "and so is this")
            page.wait_for_function(
                "document.getElementById('reviewtext')"
                ".textContent.includes('and so is this')")
            page.click("#reviewstop")

            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector(".row")
            show_tab(page, "diff")
            page.wait_for_selector(".comment")
            page.click(".verb.submit")
            page.wait_for_selector("#review[open]")
            assert page.input_value("#overall") == "and so is this"
        finally:
            browser.close()


def test_a_review_that_went_is_not_kept(repo_page):
    with sync_playwright() as play:
        browser = fresh_context(play)
        try:
            page = browser.new_page()
            page.goto(repo_page[1], wait_until="domcontentloaded")
            page.wait_for_selector(".row")
            show_tab(page, "diff")
            page.wait_for_selector(".dline")
            comment_on_first_line(page, "goes away")
            page.click(".comment .link")
            page.fill(".commentbox textarea", "")
            page.click(".commentbox .verb")
            page.wait_for_function("state.review.length === 0")
            assert page.evaluate(
                "Object.keys(localStorage)"
                ".filter((k) => k.startsWith('wostuast-review-')).length") == 0
        finally:
            browser.close()


def test_storage_that_is_not_a_review_is_left_out(repo_page):
    """What comes back was written by this page, but a browser's storage is
    not a place to trust blindly."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.evaluate("""() => {
              localStorage.setItem("wostuast-review-" + state.chosen, JSON.stringify(
                {overall: 7, comments: [
                  {anchor: "a.py\\nnew\\n1", quoted: "x", note: "a real one"},
                  {note: "no anchor"},
                  "not even an object",
                  null,
                ]}));
              recallReview(state.chosen);
            }""")
            assert page.evaluate("state.review.length") == 1
            assert page.evaluate("state.review[0].note") == "a real one"
            assert page.evaluate("state.overall") == ""
        finally:
            browser.close()


def test_a_comment_whose_line_changed_says_so(repo_page):
    """The agent keeps working while you read. Moving the comment to whatever
    is at that line number now would point it at different code; dropping it
    would lose the work. It says so instead, and keeps the line it quoted."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "about the old line")
            assert page.locator(".comment.stale").count() == 0
            # The same line number, different text: the agent edited it.
            page.evaluate("""() => {
              for (const section of state.diff.sections) {
                for (const file of section.files) {
                  for (const hunk of file.hunks) {
                    for (const line of hunk.lines) line.text = "something else";
                  }
                }
              }
              state.diffAt += 1;
              redrawDiff();
            }""")
            page.wait_for_selector(".comment.stale")
            shown = page.locator(".comment.stale").inner_text()
            assert "the line has changed" in shown
            assert "about the old line" in shown, "the note is kept"
            assert "the line has changed" in page.evaluate("reviewText()")
        finally:
            browser.close()


def test_a_comment_with_nowhere_left_to_sit_is_still_shown(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "the file went away")
            page.evaluate("""() => {
              for (const section of state.diff.sections) section.files = [];
              state.diff.untracked = [];
              state.diffAt += 1;
              redrawDiff();
            }""")
            page.wait_for_selector(".diffhead.gone")
            assert page.locator(".comment.stale").count() == 1
            assert "the file went away" in page.locator(".comment").inner_text()
            assert "no longer in the diff" in page.evaluate("reviewText()")
            assert page.evaluate("state.review.length") == 1, "nothing is dropped"
        finally:
            browser.close()


def test_a_review_for_a_session_that_is_gone_is_swept_up(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "mine")
            page.evaluate("""() => {
              localStorage.setItem("wostuast-review-someone-else", JSON.stringify(
                {overall: "", comments: [{anchor: "a\\nnew\\n1", note: "theirs"}]}));
              state.pruned = false;
              drawSessions();
            }""")
            kept = page.evaluate(
                "Object.keys(localStorage)"
                ".filter((k) => k.startsWith('wostuast-review-'))")
            assert len(kept) == 1
            assert "someone-else" not in kept[0]
        finally:
            browser.close()
