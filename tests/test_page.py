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


sync_playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed"
).sync_playwright

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


def open_page(play, where, scheme="dark"):
    url = where[1] if isinstance(where, tuple) else where
    browser = play.chromium.launch(executable_path=browser_path(),
                                   args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1440, "height": 900},
                            color_scheme=scheme)
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector(".row", timeout=15000)
    page.wait_for_timeout(600)
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
        browser = play.chromium.launch(executable_path=browser_path(),
                                       args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900},
                                    color_scheme="dark")
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


def show_tab(page, name):
    page.click(f".tab[data-tab='{name}']")
    page.wait_for_timeout(700)


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
            assert "no name matches" in page.locator(".filelist").inner_text()
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
            page.wait_for_timeout(400)
            (root / "README.md").write_text(long_file + "\n\nand one more\n")
            page.wait_for_timeout(3000)       # one poll, and then some
            assert "and one more" in page.locator(".filebody .prose").inner_text()
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
                ".filelist .plain", "els => els.map(e => e.textContent)")
            assert names == ["NOTES.md"]
            assert "1 untracked file" in page.locator(".diffbody .note").inner_text()
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
