"""The Files tab: the tree, the window, and syntax highlighting.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations

import os
import re
import time

import pytest

import conftest
from browser import (
    open_file,
    code_text,
    skip_without_browser,
    sync_playwright,
    open_page,
    show_tab,
    numbers,
    open_code,
)

pytestmark = skip_without_browser

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
            assert "print(1)" in code_text(page)
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
            page.wait_for_selector(".goto button")
            names = page.eval_on_selector_all(
                ".goto button .name", "els => els.map(e => e.textContent)")
            assert names == ["NOTES.md"]
            lit = page.eval_on_selector_all(
                ".goto .lit", "els => els.map(e => e.textContent).join('')")
            assert lit.lower() == "nsmd"
            # The letters have to be in order; these are the same four, not.
            page.fill("#find", "dmsn")
            page.wait_for_selector(".goto .nohits")
            assert page.locator(".goto button").count() == 0
        finally:
            browser.close()


def test_the_best_match_comes_first(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.fill("#find", "py")
            page.wait_for_selector(".goto button")
            names = page.eval_on_selector_all(
                ".goto button .name", "els => els.map(e => e.textContent)")
            assert names[0] == "code.py"
        finally:
            browser.close()


def test_a_name_that_matches_nothing_says_so(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.fill("#find", "zzqq")
            page.wait_for_selector(".goto .nohits")
            assert page.locator(".goto button").count() == 0
            # And the tree is untouched behind it.
            assert page.locator(".filelist button").count() > 0
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
            page.eval_on_selector(".filescroll", "el => el.scrollTop = 900")
            (root / "README.md").write_text(long_file + "\n\nand one more\n")
            # Wait for the new line to arrive, not for a poll to have passed.
            page.wait_for_function(
                "document.querySelector('.filebody .prose').innerText"
                ".includes('and one more')", timeout=15000)
            where = page.eval_on_selector(".filescroll", "el => el.scrollTop")
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


def test_the_dot_appears_when_a_quiet_file_is_touched(repo_page):
    """The marker is part of what the list was drawn from. Left out of the
    key, it only ever appeared when the sort order happened to move too."""
    git = conftest.git_in

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


def test_git_failing_does_not_read_as_an_empty_worktree(repo_page):
    """"No files" and "git did not answer" look the same and mean opposite
    things. A two second timeout over fifty thousand files drew the first."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.evaluate("state.files.names = []; state.files.path = null;"
                          " state.files.failed = true; draw()")
            page.wait_for_timeout(200)
            said = page.locator(".filebody .empty").inner_text()
            assert "git did not answer" in said
            assert "holds no file" not in said
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
            page.wait_for_selector(".goto button")
            # The directory it names is a place to go in its own right, and so
            # is the one file under it.
            found = page.eval_on_selector_all(
                ".goto button", "els => els.map(e => e.title)")
            assert "native/shared/libcorrelation/src/Action.h" in found
            assert "native/shared/libcorrelation" in found
        finally:
            browser.close()


def test_code_is_painted(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            open_code(page, "'<span class=\"hljs-keyword\">print</span>(1)'")
            assert page.locator(".filebody .code .hljs-keyword").inner_text() == "print"
            # The stub paints the first line; the rest of the file follows it.
            assert code_text(page) == "print(1)\nprint(2)"
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
            body = page.locator(".filebody .code")
            assert page.evaluate("window.pwned") is None
            assert body.locator("img").count() == 0
            assert body.locator(".row").count() == 0
            assert body.locator("[onclick]").count() == 0
            assert body.locator("#n").count() == 0
            # the text survives, only the dressing is gone
            assert body.locator(".hljs-string").inner_text() == "b"
            assert code_text(page) == "ab\nprint(2)"
        finally:
            browser.close()


def test_a_sublanguage_class_survives(repo_page):
    """hljs writes `hljs-title function_` as one span with two classes."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            open_code(page, "'<span class=\"hljs-title function_\">go</span>'")
            assert page.locator(".filebody .code .hljs-title.function_").count() == 1
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
            assert code_text(page).strip() == (
                "print(1)\nprint(2)")
            assert page.locator(".filebody .code .dtext span").count() == 0
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
            look = page.eval_on_selector(".filebody .code", """el => {
              const seen = getComputedStyle(el);
              return [seen.borderTopWidth, seen.backgroundColor];
            }""")
            assert look[0] == "0px"
            assert look[1] in ("rgba(0, 0, 0, 0)", "transparent")
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
            page.wait_for_selector(".goto button")
            found = page.eval_on_selector_all(
                ".goto button", "els => els.map(e => e.title)")
            assert "native/shared/libcorrelation/src/Action.h" in found
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
    git = conftest.git_in
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


def test_typing_leaves_the_tree_exactly_where_it_was(big_page):
    """Typing used to take the tree apart and show only what matched. But
    where a file sits is half of what you know about it, and the tree is the
    answer to that question — hiding it was hiding the answer as a way of
    asking for it. The list of places opens under the box instead."""
    with sync_playwright() as play:
        browser, page = open_page(play, big_page)
        try:
            show_tab(page, "files")
            page.wait_for_selector(".filelist button.dir")
            # Open one by hand first, so that a tree which collapsed under a
            # query would visibly differ from one that did not.
            page.locator(".filelist button.dir").first.click()
            page.wait_for_selector(".filelist button.dir.open")
            before = page.eval_on_selector_all(
                ".filelist button", "els => els.map(e => e.title)")
            assert len(before) > 1

            page.fill("#find", "Action")
            page.wait_for_selector(".goto button")
            after = page.eval_on_selector_all(
                ".filelist button", "els => els.map(e => e.title)")
            assert after == before, "the tree moved"
            assert page.locator(".filelist button.dir.open").count() == 1
        finally:
            browser.close()


def test_a_directory_is_a_place_to_go_too(big_page):
    """"All folders and files with it in the name", so a directory is in the
    list and picking one opens the tree down to it."""
    with sync_playwright() as play:
        browser, page = open_page(play, big_page)
        try:
            show_tab(page, "files")
            page.fill("#find", "libcorrelation")
            page.wait_for_selector(".goto button")
            page.locator(
                ".goto button[title='native/shared/libcorrelation']").click()
            page.wait_for_function(
                """() => [...document.querySelectorAll('.filelist button.dir.open')]
                     .some((e) => e.title === 'native/shared/libcorrelation')""")
            # And the box closed itself on the way.
            assert page.locator(".goto").count() == 0
            assert page.input_value("#find") == ""
        finally:
            browser.close()


def test_picking_a_file_opens_it_and_shows_where_it_sits(big_page):
    with sync_playwright() as play:
        browser, page = open_page(play, big_page)
        try:
            show_tab(page, "files")
            page.fill("#find", "Action.h")
            page.wait_for_selector(".goto button")
            page.locator(".goto button").first.click()
            page.wait_for_function(
                "document.querySelector('.filebody .where').textContent"
                ".includes('Action.h')")
            # Open in the pane, and reachable in the tree behind it.
            assert page.locator(
                ".filelist button.chosen[title$='Action.h']").count() == 1
        finally:
            browser.close()


def test_the_arrows_and_enter_walk_the_list(repo_page):
    """Search on typing, picked without the mouse."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.click("#find")
            # Two names match, so there is somewhere for the arrow to go.
            page.fill("#find", "md")
            page.wait_for_function(
                "document.querySelectorAll('.goto button').length > 1")
            first = page.eval_on_selector(".goto button", "el => el.title")
            page.press("#find", "ArrowDown")
            second = page.eval_on_selector(
                ".goto button.chosen", "el => el.title")
            assert second != first, "the arrow did not move"
            page.press("#find", "Enter")
            page.wait_for_function(
                "(want) => document.querySelector('.filebody .where')"
                ".textContent.includes(want.split('/').pop())", arg=second)
        finally:
            browser.close()


def test_a_part_of_the_path_opens_the_tree_to_it(repo_page):
    """A path in the header is the only place some files are ever named, and
    scrolling fifty thousand rows to find where one sits is not something
    anyone does twice."""
    root, _ = repo_page
    deep = root / "native" / "shared" / "libcorrelation" / "doc"
    deep.mkdir(parents=True)
    (deep / "SAMPLING.md").write_text("# sampling\n")
    conftest.git_in(root, "add", "-A")
    conftest.git_in(root, "commit", "-qm", "deep")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.fill("#find", "SAMPLING")
            page.wait_for_selector(".goto button")
            page.locator(".goto button[title$='SAMPLING.md']").click()
            page.wait_for_function(
                "document.querySelector('.filebody .where').textContent"
                ".includes('SAMPLING.md')")

            # Every part of it is its own way in.
            parts = page.eval_on_selector_all(
                ".filebody .crumb", "els => els.map((e) => e.textContent)")
            assert parts == ["native", "shared", "libcorrelation", "doc",
                             "SAMPLING.md"]

            page.click(".filebody .crumb:has-text('libcorrelation')")
            page.wait_for_function(
                "[...document.querySelectorAll('.filelist button .name')]"
                ".some((e) => e.textContent === 'libcorrelation')")
            # And the filter is gone, because it was hiding the rest of the tree.
            assert page.input_value("#find") == ""
            shown = page.eval_on_selector_all(
                ".filelist button .name", "els => els.map((e) => e.textContent)")
            assert "doc" in shown, shown
        finally:
            browser.close()


def test_the_whole_path_is_still_one_string_to_copy(repo_page):
    """Each part is clickable, so each part is its own element. The separators
    are text nodes and nothing is a block, or a copy would come back with the
    parts on lines of their own."""
    root, _ = repo_page
    deep = root / "a" / "b"
    deep.mkdir(parents=True)
    (deep / "c.py").write_text("print(1)\n")
    conftest.git_in(root, "add", "-A")
    conftest.git_in(root, "commit", "-qm", "deep")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.fill("#find", "a/b/c.py")
            page.wait_for_selector(".goto button")
            page.locator(".goto button[title='a/b/c.py']").click()
            page.wait_for_function(
                "document.querySelector('.filebody .crumbs')"
                ".textContent === 'a/b/c.py'")
            assert page.eval_on_selector(
                ".filebody .crumbs", "el => el.innerText") == "a/b/c.py"
        finally:
            browser.close()


# --- how a file is drawn: the header, and the reader's two choices -----------


def test_a_file_of_a_few_thousand_lines_is_drawn_whole_and_coloured(long_page):
    """Windowing used to start at 2,000 lines, so an ordinary source file lost
    its colour and its browser find. Measured: 2,500 lines cost 144 ms to draw
    whole and paint, which is a price worth paying to read a file."""
    root, _ = long_page
    root.joinpath("mid.py").write_text(
        "".join(f"value_{n} = {n}\n" for n in range(2426)))
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_code(page, "'<span class=\"hljs-keyword\">value_0</span>'",
                      "mid.py")
            assert page.locator(".code.windowed").count() == 0
            assert page.locator(".filebody .note").count() == 0
            page.wait_for_function(
                "document.querySelectorAll('.filebody .code .dline').length === 2426")
            # Drawn whole *and painted*, which is the half the old threshold
            # took away.
            page.wait_for_selector(".filebody .code .hljs-keyword")
        finally:
            browser.close()


def test_the_header_says_what_the_file_is(repo_page):
    """Type, size and when it last changed — all of it already in hand: the
    type the page worked out to paint it, the rest from the one stat the
    daemon does anyway."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            open_file(page, "code.py")
            about = page.locator(".filebody .where .whatis").inner_text()
            # What the page worked out in order to paint it, which is the
            # highlighter's name for the language and not a prettier one.
            assert "py" in about
            assert " B" in about or "KB" in about
            # `21 Sep 07:20`, so a day and a month and a clock.
            assert re.search(r"\d+ [A-Z][a-z]{2} \d\d:\d\d", about), about
        finally:
            browser.close()


def test_the_scrollbar_starts_under_the_header_not_beside_it(long_page):
    """The header carries the path and the two controls, and scrolling away
    from them was scrolling away from the only place that says which file
    this is. It was sticky, which keeps it in view but not out of the
    scrollbar's way: the bar ran the whole height of the pane, beside a line
    that never moves.

    It is outside the scroller now. Put the header back inside `.filescroll`
    and the first measurement stops being nought."""
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "long.py")
            seen = page.evaluate("""() => {
              const pane = document.querySelector('.filebody');
              const view = pane.querySelector('.filescroll');
              const head = pane.querySelector('.where');
              return {inside: view.contains(head),
                      gap: view.getBoundingClientRect().top
                           - head.getBoundingClientRect().bottom,
                      tall: view.scrollHeight > view.clientHeight};
            }""")
            assert seen["inside"] is False, seen
            assert -1 <= seen["gap"] <= 1, seen
            assert seen["tall"] is True, "nothing to scroll, nothing to prove"

            # And the header does not move when the file does.
            before = page.eval_on_selector(
                ".filebody > .where", "el => el.getBoundingClientRect().top")
            page.evaluate("() => { document.querySelector('.filescroll')"
                          ".scrollTop = 4000; }")
            page.wait_for_function(
                "document.querySelector('.filescroll').scrollTop > 1000")
            after = page.eval_on_selector(
                ".filebody > .where", "el => el.getBoundingClientRect().top")
            assert abs(after - before) < 1, (before, after)
        finally:
            browser.close()


def test_the_long_line_scrollbar_is_at_the_bottom_of_the_screen(repo_page):
    """It used to sit under the last line of the file, which in a file of any
    length is somewhere the reader never scrolls to."""
    repo, _ = repo_page
    repo.joinpath("wide.py").write_text(
        "".join(f"value_{n} = '{'x' * 400}'\n" for n in range(400)))
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            open_file(page, "wide.py")
            seen = page.evaluate("""() => {
              const pane = document.querySelector('.filescroll');
              const rows = pane.querySelector('.dlines');
              return {pane: pane.scrollWidth > pane.clientWidth,
                      rows: getComputedStyle(rows).overflowX};
            }""")
            assert seen["pane"] is True, "the pane does not scroll sideways"
            # `visible` is a box with no scrollbar of its own, which is the
            # point: one bar, at the bottom of the screen.
            assert seen["rows"] == "visible", seen
        finally:
            browser.close()


def test_the_tab_width_and_wrap_are_the_readers_and_are_remembered(repo_page):
    """Two choices about reading, not about a session, so they live in this
    browser like the theme does."""
    repo, _ = repo_page
    repo.joinpath("tabs.py").write_text("def a():\n\treturn 1\n")
    wrapped = ("getComputedStyle(document.querySelector('.filebody .dline'))"
               ".whiteSpace")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            open_file(page, "tabs.py")
            assert page.evaluate(
                "getComputedStyle(document.querySelector('.dlines')).tabSize") == "4"
            assert page.evaluate(wrapped) == "pre"

            page.click(".filebody .where .link:text('tab 4')")
            page.wait_for_function(
                "getComputedStyle(document.querySelector('.dlines')).tabSize === '8'")
            page.click(".filebody .where .link:text('wrap')")
            page.wait_for_function(f"{wrapped} === 'pre-wrap'")

            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector(".row")
            open_file(page, "tabs.py")
            page.wait_for_function(f"{wrapped} === 'pre-wrap'")
            assert page.evaluate(
                "getComputedStyle(document.querySelector('.dlines')).tabSize") == "8"
        finally:
            browser.close()


def test_a_windowed_file_says_it_cannot_wrap(long_page):
    """A windowed file's rows are a grid the scrollbar is read against, and a
    wrapped row is not one row tall. A control that quietly did nothing would
    be worse than one that says why."""
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "long.py")
            page.wait_for_selector(".code.windowed")
            assert page.eval_on_selector(
                ".filebody .where .link:text('wrap')", "el => el.disabled") is True
        finally:
            browser.close()


def test_every_row_says_whether_it_is_a_file_or_a_folder(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.wait_for_selector(".filelist button")
            seen = page.eval_on_selector_all(
                ".filelist button",
                """els => els.map((b) => [b.classList.contains('dir'),
                                          b.querySelectorAll('svg.icon').length])""")
            assert seen and all(many == 1 for _, many in seen)
        finally:
            browser.close()


def test_changing_how_a_file_is_drawn_keeps_a_comment_being_written(repo_page):
    """Both controls used to call `redrawCode`, which clears the very key
    `holdingText` guards an open comment box with — so the pane rebuilt under
    the reader and `putCommentBox` re-seeded the box from the saved note,
    which for an unsaved one is the empty string. The header is sticky, so
    those buttons are on screen and clickable the whole time you are typing.

    Neither control rebuilds anything now: both are read from the root by the
    cascade.
    """
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            open_file(page, "code.py")
            page.locator(".filebody .dline .addnote").first.click(force=True)
            page.wait_for_selector(".commentbox textarea")
            page.fill(".commentbox textarea", "half a thought")

            page.click(".filebody .where .link:text('tab 4')")
            page.click(".filebody .where .link:text('wrap')")
            page.wait_for_function(
                "getComputedStyle(document.querySelector('.filebody .dline'))"
                ".whiteSpace === 'pre-wrap'")
            assert page.input_value(".commentbox textarea") == "half a thought"
        finally:
            browser.close()


def test_a_windowed_file_does_not_wrap_even_if_it_is_told_to(long_page):
    """The button being disabled is a courtesy. The rule itself is that a
    windowed file's rows are a grid the scrollbar is read against, and a
    wrapped row is not one row tall — so turning wrap on while a windowed file
    is open must change nothing about its rows."""
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "long.py")
            page.wait_for_selector(".code.windowed")
            page.evaluate("""() => { keepReading({tab: 4, wrap: true}); }""")
            assert page.evaluate("document.documentElement.dataset.wrap") == "yes"
            assert page.evaluate(
                "getComputedStyle(document.querySelector('.filebody .dline'))"
                ".whiteSpace") == "pre"
        finally:
            browser.close()


def test_the_same_query_twice_opens_the_list_again(repo_page):
    """The list is only rebuilt when what it is showing changes. Closing it
    has to forget that too, or typing the same thing again matches the key
    and draws nothing."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.fill("#find", "code")
            page.wait_for_selector(".goto button")
            page.fill("#find", "")
            page.wait_for_function("document.querySelectorAll('.goto').length === 0")
            page.fill("#find", "code")
            page.wait_for_selector(".goto button")
        finally:
            browser.close()


# --- the tree's shape, and where a click lands -------------------------------

def test_a_folder_has_no_triangle_and_its_own_colour(repo_page):
    """The triangle stood where nothing stood on a file row, so a folder's
    name sat right of a file's at the same depth — and a file one level
    deeper lined up exactly with the folder above it, which is the one thing
    a tree must not do. Put `.caret` back and the two names stop agreeing."""
    root, _ = repo_page
    (root / "deep").mkdir()
    (root / "deep" / "inner.py").write_text("x = 1\n")
    conftest.git_in(root, "add", "-A")
    conftest.git_in(root, "commit", "-qm", "deep")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.click(".filelist button.dir:has(.name:text-is('deep'))")
            page.wait_for_selector(".filelist button:has(.name:text-is('inner.py'))")
            assert page.locator(".filelist .caret").count() == 0
            seen = page.evaluate("""() => {
              const left = (name) => [...document.querySelectorAll('.filelist button')]
                .find((one) => one.querySelector('.name').textContent === name)
                .querySelector('.name').getBoundingClientRect().left;
              const icon = (name) => getComputedStyle(
                [...document.querySelectorAll('.filelist button')]
                  .find((one) => one.querySelector('.name').textContent === name)
                  .querySelector('.icon')).color;
              return {dir: left('deep'), inside: left('inner.py'),
                      top: left('README.md'),
                      dirInk: icon('deep'), fileInk: icon('README.md')};
            }""")
            # A folder's name starts where a file's does at the same depth.
            assert abs(seen["dir"] - seen["top"]) < 1, seen
            # And what it holds is a step further in, visibly.
            assert seen["inside"] > seen["dir"] + 8, seen
            # The folder carries a colour of its own.
            assert seen["dirInk"] != seen["fileInk"], seen
        finally:
            browser.close()


def test_an_open_folder_is_drawn_open(repo_page):
    """The triangle said whether a folder stood open. Without it the icon has
    to. Draw the same path for both and this goes red."""
    root, _ = repo_page
    (root / "deep").mkdir()
    (root / "deep" / "inner.py").write_text("x = 1\n")
    conftest.git_in(root, "add", "-A")
    conftest.git_in(root, "commit", "-qm", "deep")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            shut = page.eval_on_selector(
                ".filelist button.dir path", "el => el.getAttribute('d')")
            page.click(".filelist button.dir:has(.name:text-is('deep'))")
            page.wait_for_selector(".filelist button.dir.open")
            wide = page.eval_on_selector(
                ".filelist button.dir path", "el => el.getAttribute('d')")
            assert shut and wide and shut != wide
        finally:
            browser.close()


def test_a_part_of_a_path_already_on_screen_still_answers(repo_page):
    """The click worked and moved nothing, because the folder was already
    open and already in view — so from the reader's seat nothing happened.
    The list marks where you went now, whether or not it had to scroll.

    Drop `state.files.at` from the list's redraw key and the mark stays on
    the file."""
    root, _ = repo_page
    deep = root / "native" / "doc"
    deep.mkdir(parents=True)
    (deep / "SAMPLING.md").write_text("# sampling\n")
    conftest.git_in(root, "add", "-A")
    conftest.git_in(root, "commit", "-qm", "deep")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            # Walk in by hand, so every folder is already open and in view.
            for part in ("native", "doc"):
                page.click(f".filelist button.dir:has(.name:text-is('{part}'))")
                page.wait_for_selector(
                    f".filelist button.dir.open:has(.name:text-is('{part}'))")
            page.click(".filelist button:has(.name:text-is('SAMPLING.md'))")
            page.wait_for_function(
                "document.querySelector('.filebody .where')"
                ".textContent.includes('SAMPLING.md')")
            assert page.eval_on_selector(
                ".filelist button.chosen", "el => el.title").endswith(
                    "SAMPLING.md")

            page.click(".filebody .crumb:has-text('native')")
            page.wait_for_function(
                """() => {
                     const one = document.querySelector('.filelist button.chosen');
                     return one && one.title === 'native';
                   }""")
            # The file is still the one being read; only the mark moved.
            assert page.evaluate("state.files.path").endswith("SAMPLING.md")
        finally:
            browser.close()


def test_a_dotfile_in_the_go_to_list_keeps_its_dot_at_the_front(repo_page):
    """The list clips a long path at its start, which `direction: rtl` buys.
    It costs a bidi trap: a leading dot is a neutral character, and in an RTL
    paragraph a neutral at the edge goes to the other end — so `.gitignore`
    drew as `gitignore.`, a file with a dot invented on it.

    Take `unicode-bidi: plaintext` off and the two measurements swap."""
    root, _ = repo_page
    (root / ".gitignore").write_text("*.pyc\n")
    conftest.git_in(root, "add", "-A")
    conftest.git_in(root, "commit", "-qm", "ignore")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.fill("#find", "gitignor")     # no dot, so the dot is not lit
            page.wait_for_selector(".goto button[title='.gitignore']")
            seen = page.evaluate("""() => {
              const name = document.querySelector(
                ".goto button[title='.gitignore'] .name");
              const walker = document.createTreeWalker(name, NodeFilter.SHOW_TEXT);
              const texts = [];
              while (walker.nextNode()) texts.push(walker.currentNode);
              const edge = (node, from) => {
                const range = document.createRange();
                range.setStart(node, from);
                range.setEnd(node, from + 1);
                return range.getBoundingClientRect().left;
              };
              const last = texts[texts.length - 1];
              return {text: name.textContent,
                      dot: edge(texts[0], 0),
                      end: edge(last, last.nodeValue.length - 1)};
            }""")
            assert seen["text"] == ".gitignore", seen
            assert seen["dot"] < seen["end"], seen
        finally:
            browser.close()


def test_another_file_opens_at_its_top(repo_page):
    """A different file inherited wherever the one before it had been read
    to: open a long file after reading another to its end and it started at
    its end.

    Two things keep it at the top now. `.filescroll` is built with the file,
    so a new one starts at nought; and `forgetFile` puts `state.files.down`
    back to nought, because another file is not a place to go back to. Take
    that line out and the second file opens where the first was left.

    Both files are long, or the browser would clamp the scrollbar to nought
    on its own and the test would pass against the bug."""
    root, _ = repo_page
    for name in ("first.py", "second.py"):
        (root / name).write_text(
            "".join(f"{name[:-3]}_{n} = {n}\n" for n in range(600)))
    conftest.git_in(root, "add", "-A")
    conftest.git_in(root, "commit", "-qm", "two long files")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            open_file(page, "first.py")
            page.evaluate("""() => { const view =
              document.querySelector('.filescroll');
              view.scrollTop = view.scrollHeight; }""")
            page.wait_for_function(
                "document.querySelector('.filescroll').scrollTop > 1000")
            open_file(page, "second.py")
            page.wait_for_function(
                """() => document.querySelector('.filebody .where')
                           .textContent.includes('second.py')""")
            page.wait_for_function(
                "document.querySelector('.filescroll').scrollTop === 0",
                timeout=5000)
            # And it really could have kept a place: this file scrolls too.
            assert page.eval_on_selector(
                ".filescroll", "el => el.scrollHeight > el.clientHeight + 1000")
        finally:
            browser.close()


def test_a_picture_is_shown_rather_than_named(repo_page):
    """"Binary file. There is nothing to show." is true of a compiled object
    and false of a screenshot. The picture really arrives here: the check is
    the width the browser decoded, not that an element was built."""
    root, _ = repo_page
    (root / "logo.png").write_bytes(conftest.tiny_png())
    (root / "blob.bin").write_bytes(b"\0\0\0not a picture\0")
    conftest.git_in(root, "add", "-A")
    conftest.git_in(root, "commit", "-qm", "a picture and a blob")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            # Not `open_file`: it waits for rows, and a picture has none.
            show_tab(page, "files")
            page.click(".filelist button:has-text('logo.png')")
            page.wait_for_selector(".filebody .media img")
            page.wait_for_function(
                "document.querySelector('.filebody .media img').naturalWidth > 0")
            assert page.locator(".filebody .note").count() == 0

            # And a binary that is not a picture still says so.
            page.click(".filelist button:has-text('blob.bin')")
            page.wait_for_function(
                """() => {
                     const note = document.querySelector('.filebody .note');
                     return note && note.textContent.includes('Binary file');
                   }""")
            assert page.locator(".filebody .media").count() == 0
        finally:
            browser.close()


def test_a_picture_too_big_to_show_says_so(ws, repo_page, monkeypatch):
    """The daemon holds the cap, because it is the one that reads the file
    whole. It says so in the same answer, and the page says how big it is
    rather than asking for a file it will be refused."""
    root, _ = repo_page
    monkeypatch.setattr(ws, "SHOWN_MAX_BYTES", 8)   # the picture is 69 bytes
    (root / "logo.png").write_bytes(conftest.tiny_png())
    conftest.git_in(root, "add", "-A")
    conftest.git_in(root, "commit", "-qm", "a picture")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.click(".filelist button:has-text('logo.png')")
            page.wait_for_function(
                """() => {
                     const note = document.querySelector('.filebody .note');
                     return note && note.textContent.includes('too big');
                   }""")
            assert page.locator(".filebody .media").count() == 0
        finally:
            browser.close()


# --- what a session remembers between visits ---------------------------------

def test_a_session_comes_back_to_where_it_was_left(two_repos):
    """A session keeps what the reader chose: the tab, the open file, the
    place in it, and which directories stand open. It keeps none of what the
    daemon sent — the listing, the text and the diff are fetched again,
    because by the time you come back they have moved.

    Drop `usePlace` from `choose` and every one of these comes back blank."""
    repo, _, base = two_repos
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            page.wait_for_function("state.sessions.length === 2")
            page.evaluate("choose('s1')")
            show_tab(page, "files")
            page.click(".filelist button.dir:has(.name:text-is('deep'))")
            page.click(".filelist button:has(.name:text-is('inner.py'))")
            page.wait_for_function(
                """() => document.querySelector('.filebody .where')
                           .textContent.includes('inner.py')""")
            page.evaluate("""() => { const view =
              document.querySelector('.filescroll');
              view.scrollTop = Math.floor(view.scrollHeight / 2); }""")
            page.wait_for_function(
                "document.querySelector('.filescroll').scrollTop > 100")
            was = page.eval_on_selector(".filescroll", "el => el.scrollTop")

            # Away, and back.
            page.evaluate("choose('s2')")
            page.wait_for_function("state.files.path === 'OTHER.md'")
            assert page.evaluate("state.files.dirs.size") == 0
            page.evaluate("choose('s1')")

            page.wait_for_function("state.tab === 'files'")
            page.wait_for_function(
                """() => document.querySelector('.filebody .where')
                           .textContent.includes('inner.py')""")
            page.wait_for_function(
                "(was) => Math.abs(document.querySelector('.filescroll')"
                ".scrollTop - was) < 30", arg=was)
            assert page.evaluate("[...state.files.dirs]") == [["deep", True]]
            # The caches are not kept: this listing came back from the daemon.
            assert page.evaluate("state.files.names.length") > 0
        finally:
            browser.close()


def test_a_session_comes_back_to_the_tab_it_was_left_on(two_repos):
    """The tab is part of where you were. `choose` goes through `showTab` for
    it, which is also what marks the strip and loads the tab — set
    `state.tab` by hand instead and the strip points at the wrong one."""
    _, _, base = two_repos
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            page.wait_for_function("state.sessions.length === 2")
            page.evaluate("choose('s1')")
            show_tab(page, "diff")
            page.evaluate("choose('s2')")
            show_tab(page, "review")
            page.evaluate("choose('s1')")
            # The box, not `state.tab`: `showTab` sets the name and then
            # awaits the load, and until that comes back the box still holds
            # the tab before it.
            page.wait_for_function("$('content').dataset.tab === 'diff'")
            assert page.eval_on_selector(
                ".tab[data-tab='diff']",
                "el => el.getAttribute('aria-selected')") == "true"
        finally:
            browser.close()


def test_a_place_in_a_file_survives_leaving_the_files_tab(two_repos):
    """The pane is on the page only while the Files tab is, so by the time a
    session is left from another tab the scrollbar is long gone. `showTab`
    writes the place down on the way out. Take that line out and the file
    comes back at its top."""
    _, _, base = two_repos
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            page.wait_for_function("state.sessions.length === 2")
            page.evaluate("choose('s1')")
            show_tab(page, "files")
            page.click(".filelist button.dir:has(.name:text-is('deep'))")
            page.click(".filelist button:has(.name:text-is('inner.py'))")
            page.wait_for_function(
                """() => document.querySelector('.filebody .where')
                           .textContent.includes('inner.py')""")
            page.evaluate("""() => { const view =
              document.querySelector('.filescroll');
              view.scrollTop = Math.floor(view.scrollHeight / 2); }""")
            page.wait_for_function(
                "document.querySelector('.filescroll').scrollTop > 100")
            was = page.eval_on_selector(".filescroll", "el => el.scrollTop")

            # Leave by another tab, then leave the session, then come back.
            show_tab(page, "diff")
            assert page.locator(".filescroll").count() == 0
            page.evaluate("choose('s2')")
            # s2 is on the Diff tab too, so its Files tab never loads and
            # there is no open file to wait for; its diff is the signal.
            page.wait_for_function(
                "state.chosen === 's2' && state.diff !== null")
            page.evaluate("choose('s1')")
            page.wait_for_function(
                "state.chosen === 's1' && $('content').dataset.tab === 'diff'")
            show_tab(page, "files")
            page.wait_for_function(
                """() => document.querySelector('.filebody .where')
                           .textContent.includes('inner.py')""")
            page.wait_for_function(
                "(was) => Math.abs(document.querySelector('.filescroll')"
                ".scrollTop - was) < 30", arg=was)
        finally:
            browser.close()


def test_coming_back_does_not_bring_the_last_session_place_with_it(two_repos):
    """`choose` restores the place and then changes the tab. `showTab` used
    to write the scroll position down on its way through, and at that moment
    the pane on the page still belonged to the session being left — so the
    place just restored was overwritten with the other session's.

    The scrollbar is the only writer now. Put a
    `document.querySelector('.filescroll')` write back into `showTab` and
    this goes red."""
    _, _, base = two_repos
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            page.wait_for_function("state.sessions.length === 2")

            # s2: read a long file half way down, then leave by another tab.
            page.evaluate("choose('s2')")
            show_tab(page, "files")
            page.click(".filelist button:has-text('other.py')")
            page.wait_for_function(
                """() => document.querySelector('.filebody .where')
                           .textContent.includes('other.py')""")
            page.evaluate("""() => { const view =
              document.querySelector('.filescroll');
              view.scrollTop = Math.floor(view.scrollHeight / 2); }""")
            page.wait_for_function(
                "document.querySelector('.filescroll').scrollTop > 100")
            two = page.eval_on_selector(".filescroll", "el => el.scrollTop")
            show_tab(page, "diff")

            # s1: a different long file, read to a different place, and left
            # from the Files tab — which is what put a pane on the page for
            # `showTab` to read while coming back to s2.
            page.evaluate("choose('s1')")
            show_tab(page, "files")
            page.click(".filelist button.dir:has(.name:text-is('deep'))")
            page.click(".filelist button:has(.name:text-is('inner.py'))")
            page.wait_for_function(
                """() => document.querySelector('.filebody .where')
                           .textContent.includes('inner.py')""")
            page.evaluate("""() => { const view =
              document.querySelector('.filescroll');
              view.scrollTop = view.scrollHeight; }""")
            page.wait_for_function(
                "document.querySelector('.filescroll').scrollTop > 1000")
            one = page.eval_on_selector(".filescroll", "el => el.scrollTop")
            assert abs(one - two) > 100, (one, two)

            page.evaluate("choose('s2')")
            page.wait_for_function("$('content').dataset.tab === 'diff'")
            assert page.evaluate("state.files.down") == two
            show_tab(page, "files")
            page.wait_for_function(
                """() => document.querySelector('.filebody .where')
                           .textContent.includes('other.py')""")
            page.wait_for_function(
                "(two) => Math.abs(document.querySelector('.filescroll')"
                ".scrollTop - two) < 30", arg=two)
        finally:
            browser.close()


def test_what_a_session_keeps_is_what_comes_back(two_repos):
    """`savePlace` and `usePlace` name their fields by hand. A choice added
    to one and forgotten in the other simply stops coming back, which looks
    like the feature half-working rather than like a bug. Every field one
    writes down, the other has to put back — `tab` excepted, which `choose`
    hands to `showTab`.

    Take a line out of `usePlace` and the two lists stop agreeing."""
    _, _, base = two_repos
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            page.wait_for_function("state.sessions.length === 2")
            seen = page.evaluate("""() => {
              state.tab = 'diff';
              Object.assign(state.files, {path: 'a/b.py', at: 'a',
                                          asText: true, down: 321});
              state.files.dirs = new Map([['a', true]]);
              state.open = new Set([7]);
              state.diffOpen = new Map([['z.py', true]]);
              state.loose = 'loose.txt';
              savePlace('probe');
              const kept = state.visits.get('probe');

              // Blanked the way `choose` blanks it. The tab goes too: it
              // is `choose` that puts that one back, through `showTab`.
              state.tab = 'transcript';
              state.files = blankFiles();
              state.open = new Set();
              state.diffOpen = new Map();
              state.loose = null;
              usePlace('probe');

              const after = {
                tab: state.tab, path: state.files.path, at: state.files.at,
                asText: state.files.asText, down: state.files.down,
                dirs: state.files.dirs, open: state.open,
                diffOpen: state.diffOpen, loose: state.loose,
              };
              const flat = (one) =>
                (one instanceof Map || one instanceof Set)
                  ? JSON.stringify([...one]) : JSON.stringify(one);
              return {
                kept: Object.keys(kept).sort(),
                back: Object.keys(kept)
                        .filter((name) => flat(kept[name]) === flat(after[name]))
                        .sort(),
              };
            }""")
            assert "tab" in seen["kept"], seen
            assert seen["back"] == [one for one in seen["kept"] if one != "tab"], seen
            assert len(seen["kept"]) >= 9, seen
        finally:
            browser.close()
