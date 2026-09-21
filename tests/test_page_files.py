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


def test_the_header_stays_in_view_down_a_long_file(long_page):
    """It carries the path and the two controls, and scrolling away from them
    was scrolling away from the only place that says which file this is."""
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "long.py")
            page.evaluate("() => { document.querySelector('.filebody')"
                          ".scrollTop = 4000; }")
            page.wait_for_function(
                "document.querySelector('.filebody').scrollTop > 1000")
            seen = page.evaluate("""() => {
              const pane = document.querySelector('.filebody');
              const head = pane.querySelector('.where');
              return {top: head.getBoundingClientRect().top
                           - pane.getBoundingClientRect().top};
            }""")
            assert -1 <= seen["top"] <= 1, seen
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
              const pane = document.querySelector('.filebody');
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
