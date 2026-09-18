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
         "diff": ".diffbody > *"}


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
            assert "A session" in page.locator(".row .name").inner_text()
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


def test_a_tab_that_is_not_built_yet_does_nothing(page_at):
    """Peek is milestone 4. Its key must leave the page exactly as it was."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            turns = page.locator(".turn").count()
            page.keyboard.press("4")
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


@pytest.fixture
def big_page(ws, served, tmp_path):
    """A session in a repository with more files than the old list would send."""
    from conftest import git_in as git

    root = tmp_path / "big"
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

    daemon, base = served
    ws.append_event(conftest.event("SessionStart", cwd=str(root), ts=time.time(),
                                   pane="%7", pid=1))
    daemon.store.refresh()
    return root, base


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
            added = page.eval_on_selector_all(
                ".dline.added", "els => els.map(e => e.textContent)")
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
            first = block.locator(".dline.added").first.inner_text()
            assert first == "+# Notes"
            assert block.locator(".dline.removed").count() == 0
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


def test_the_tabs_are_no_longer_disabled(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            for name in ("files", "diff"):
                assert not page.locator(f".tab[data-tab='{name}']").is_disabled()
            assert page.locator(".tab[data-tab='peek']").is_disabled()
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
            names = page.eval_on_selector_all(
                ".filelist button", "els => els.map(e => e.title)")
            assert names == ["native/shared/libcorrelation/src/Action.h"]
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
            assert page.locator(".filebody pre .hljs-keyword").inner_text() == "print"
            assert page.locator(".filebody pre").inner_text() == "print(1)"
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
            body = page.locator(".filebody pre")
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
            assert page.locator(".filebody pre .hljs-title.function_").count() == 1
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
            assert page.locator(".filebody pre").inner_text().strip() == (
                "print(1)\nprint(2)")
            assert page.locator(".filebody pre span").count() == 0
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
            look = page.eval_on_selector(".filebody pre", """el => {
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
            names = page.eval_on_selector_all(
                ".filelist button", "els => els.map(e => e.title)")
            assert names == ["native/shared/libcorrelation/src/Action.h"]
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
