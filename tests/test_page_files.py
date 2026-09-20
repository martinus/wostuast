"""The Files tab: the tree, the window, and syntax highlighting.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations

import os
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
            page.wait_for_selector(".filebody .code .dline")
            got = page.eval_on_selector_all(
                ".filebody .code .dline .ln", "els => els.map(e => e.textContent.trim())")
            assert got == ["1", "2", "3", "4"]
            # The number is beside the line, not part of it, so copying the
            # code does not take it.
            assert code_text(page) == "one\ntwo\nthree\nfour"
            assert page.eval_on_selector(
                ".filebody .code .ln", "el => getComputedStyle(el).userSelect"
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
            # Rows are what carry numbers now, and prose has none of them.
            assert page.locator(".filebody .dline").count() == 0
        finally:
            browser.close()


def test_a_script_with_no_suffix_is_painted_from_its_shebang(ws, served, repo):
    """`wostuast` itself is a Python program with no suffix, and so is most of
    what lives in a bin directory. The name said nothing, so nothing painted."""
    git = conftest.git_in
    (repo / "runme").write_text("#!/usr/bin/env python3\nimport os\n"
                                "def go():\n    return os.getcwd()\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "a script")
    daemon, base = served
    ws.append_event(conftest.event("SessionStart", cwd=str(repo), ts=time.time(),
                                   pane="%7", pid=1))
    daemon.store.refresh()
    with sync_playwright() as play:
        browser, page = open_page(play, (repo, base))
        try:
            show_tab(page, "files")
            # A stand-in highlighter that records what it was asked for.
            page.evaluate("""hljsAsked = Promise.resolve({
              getLanguage: () => true,
              highlight: (text, how) => {
                window.__lang = how.language;
                return { value: "painted" };
              },
            });""")
            page.click(".filelist button:has-text('runme')")
            page.wait_for_function("window.__lang !== undefined")
            assert page.evaluate("window.__lang") == "python"
        finally:
            browser.close()


def test_the_shebang_is_read_without_a_browser(page_at):
    """The cases, in one place, because a shebang has more shapes than a
    suffix does."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            asked = page.evaluate("""() => ({
              plain: languageOf("bin/runme", "#!/bin/sh\\necho hi"),
              env: languageOf("bin/runme", "#!/usr/bin/env python3\\nimport os"),
              versioned: languageOf("x", "#!/usr/bin/python3.12\\nimport os"),
              dashS: languageOf("x", "#!/usr/bin/env -S python3 -u\\nimport os"),
              unknown: languageOf("x", "#!/usr/bin/env frobnicate\\nwhat"),
              none: languageOf("x", "just some text\\n"),
              empty: languageOf("x", ""),
              suffixWins: languageOf("a.rs", "#!/bin/sh\\n"),
            })""")
            assert asked == {
                "plain": "bash", "env": "python", "versioned": "python",
                "dashS": "python", "unknown": None, "none": None,
                "empty": None, "suffixWins": "rust",
            }
        finally:
            browser.close()


def test_the_find_box_searches_the_name_not_the_whole_path(page_at):
    """Reported from a real repository. Searching "MetricsBuilder" returned
    `.../odin/agent/metrics/jmx/MBeanSubscriptionBuilder.java` — the letters
    scattered over 71 characters of path, across four directory names — and
    did not return `.../mintv2/MetricBuilder.h`, which is what was meant, over
    one `s` that is not in it.

    Scattered over a long path a subsequence means nothing. Scattered over a
    name it means what you meant. A directory can still be searched, but only
    when its letters sit together, and a slash says you meant the path.
    """
    junk = ("java-odin/introspection/src/main/java/com/dynatrace/odin/agent"
            "/metrics/jmx/MBeanSubscriptionBuilder.java")
    good = "native/shared/libmintv2/src/main/public/mintv2/MetricBuilder.h"
    deep = "native/shared/libcorrelation/src/Action.h"
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            got = page.evaluate(
                """([junk, good, deep]) => ({
                     junk: !!findPath(junk, "metricsbuilder"),
                     good: !!findPath(good, "metricsbuilder"),
                     exact: !!findPath(good, "metricbuilder"),
                     byDirectory: !!findPath(deep, "libcorrelation"),
                     wrongDirectory: !!findPath(good, "libcorrelation"),
                     withSlash: !!findPath(good, "mintv2/metric"),
                     nothingTyped: !!findPath(good, ""),
                     shortQueryIsStrict: !!findPath(good, "xyz"),
                     nameBeatsDirectory:
                       findPath("src/thing/parser.c", "parser").score >
                       findPath("src/parser/thing.c", "parser").score,
                   })""", [junk, good, deep])
            assert got == {
                "junk": False, "good": True, "exact": True,
                "byDirectory": True, "wrongDirectory": False,
                "withSlash": True, "nothingTyped": True,
                "shortQueryIsStrict": False, "nameBeatsDirectory": True,
            }
        finally:
            browser.close()




def test_a_slow_answer_cannot_land_under_another_file(repo_page):
    """The file is asked for by name, and the name can change while the answer
    is on its way. Only the session was checked when it came back, so picking
    another file quickly left the first one's text under the second one's
    name: the tab showed one file's content labelled as another.

    Found by a test that stopped sleeping for 400 ms and started waiting for
    what the page had drawn.
    """
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            # Hold the next answer for a file, so the switch happens under it.
            page.evaluate("""() => {
              window.__release = null;
              const real = window.fetch;
              window.fetch = (url, opts) => {
                if (String(url).includes("/file?path=")) {
                  window.fetch = real;      // only the one
                  return new Promise((go) => {
                    window.__release = () => go(real(url, opts));
                  });
                }
                return real(url, opts);
              };
            }""")
            # A block body, so Playwright is not handed the promise this test
            # is holding open — awaiting it would hang the call.
            page.evaluate("() => { forgetFile('README.md'); loadFiles(); }")
            page.wait_for_function("window.__release !== null")
            # Another file is picked while the first answer is still in flight.
            page.evaluate("forgetFile('code.py');")
            page.evaluate("window.__release();")
            page.wait_for_timeout(400)
            assert page.evaluate("state.files.path") == "code.py"
            assert "readme" not in page.evaluate("state.files.text").lower(), (
                "one file's text landed under another file's name")
        finally:
            browser.close()


def test_a_row_of_code_is_monospace_in_both_tabs(repo_page):
    """The mono face, size and line height sat on the Diff tab's container, so
    when the Files tab drew the same rows they came out in the proportional
    body face and the gutter's space padding stopped lining up. A row carries
    its own typography."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            faces = {}
            show_tab(page, "files")
            open_file(page)
            faces["files"] = page.eval_on_selector(
                ".filebody .code .dline", "el => getComputedStyle(el).fontFamily")
            show_tab(page, "diff")
            page.wait_for_selector(".diffbody .dline")
            faces["diff"] = page.eval_on_selector(
                ".diffbody .dline", "el => getComputedStyle(el).fontFamily")
            assert "Mono" in faces["files"], faces
            assert faces["files"] == faces["diff"], faces
        finally:
            browser.close()


# --- a file too long to draw whole -------------------------------------------


def long_rows(page):
    """The line numbers the window is showing, first and last."""
    return page.eval_on_selector_all(
        ".filebody .code .dline .ln",
        "els => [els[0].textContent.trim(), els[els.length - 1].textContent.trim()]")


def test_a_long_file_draws_only_the_rows_on_screen(long_page):
    """A file of 76,000 short lines was 306,000 nodes and about a second to
    build, and the colouring another second and a quarter on top — all of it
    paid again every time the agent saved the file being read."""
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "long.py")
            drawn = page.locator(".filebody .code .dline").count()
            assert 0 < drawn < 300, drawn
            # The scrollbar is still the length of the whole file, so the
            # reader cannot tell the rest is missing except by looking.
            tall = page.eval_on_selector(".filebody", "el => el.scrollHeight")
            assert tall > conftest.LONG_LINES * 20
        finally:
            browser.close()


def test_a_long_file_is_redrawn_in_a_few_milliseconds(long_page):
    """The redraw is what the agent's next save costs the reader."""
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "long.py")
            spent = page.evaluate("""() => {
              const box = document.getElementById("content");
              let worst = 0;
              for (let i = 0; i < 3; i += 1) {
                box.dataset.bodyKey = "";
                const at = performance.now();
                draw();
                worst = Math.max(worst, performance.now() - at);
              }
              return worst;
            }""")
            assert spent < 150, spent
        finally:
            browser.close()


def test_scrolling_a_long_file_brings_the_right_lines(long_page):
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "long.py")
            assert long_rows(page)[0] == "1"
            # Halfway down, by the same arithmetic the page uses.
            page.evaluate("() => { document.querySelector('.filebody')"
                          ".scrollTop = 3000 * 21; }")
            page.wait_for_function(
                "document.querySelector('.filebody .code .dline .ln')"
                ".textContent.trim() !== '1'")
            first, last = long_rows(page)
            assert 2985 <= int(first) <= 3001, first
            assert int(last) > int(first)
            assert f"line{int(first) - 1} = {int(first) - 1}" in code_text(page)
        finally:
            browser.close()


def test_the_last_line_of_a_long_file_can_be_reached(long_page):
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "long.py")
            page.evaluate("() => { const p = document.querySelector('.filebody');"
                          " p.scrollTop = p.scrollHeight; }")
            page.wait_for_function(
                "(n) => [...document.querySelectorAll('.filebody .code .dline .ln')]"
                ".some((e) => e.textContent.trim() === String(n))",
                arg=conftest.LONG_LINES)
            assert f"line{conftest.LONG_LINES - 1} =" in code_text(page)
        finally:
            browser.close()


def test_a_long_file_says_what_is_different_about_it(long_page):
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "long.py")
            said = page.locator(".filebody .note").inner_text()
            assert str(conftest.LONG_LINES) in said
            assert "no colour" in said and "find" in said
        finally:
            browser.close()


def test_a_short_file_is_still_drawn_whole(long_page):
    """The window starts at a length. Below it nothing changes, so the
    browser's own find still sees the file and a copy is the whole of it."""
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "short.py")
            assert page.locator(".filebody .code .dline").count() == 1
            assert page.locator(".filebody .note").count() == 0
            assert page.locator(".code.windowed").count() == 0
        finally:
            browser.close()


def test_scrolling_sideways_survives_the_window_moving(long_page):
    """The rows are in a new box every time the window moves, so how far along
    a long line the reader had scrolled has to be carried over."""
    root, _ = long_page
    # Wide enough to scroll sideways, and short enough that the whole file
    # stays under the half megabyte the daemon will send.
    root.joinpath("long.py").write_text(
        "".join(f"line{n} = {n}  # {'wide ' * 20}\n"
                for n in range(conftest.LONG_LINES)))
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "long.py")
            page.wait_for_selector(".code.windowed")
            page.wait_for_function(
                "document.querySelector('.filebody .dlines').scrollWidth >"
                " document.querySelector('.filebody .dlines').clientWidth")
            # As far right as this window goes, whatever that turns out to be.
            along = page.eval_on_selector(
                ".filebody .dlines",
                "el => { el.scrollLeft = 4000; return el.scrollLeft; }")
            assert along > 0
            page.evaluate("() => { document.querySelector('.filebody')"
                          ".scrollTop = 900 * 21; }")
            page.wait_for_function(
                "document.querySelector('.filebody .code .dline .ln')"
                ".textContent.trim() !== '1'")
            assert page.eval_on_selector(
                ".filebody .dlines", "el => el.scrollLeft") == along
        finally:
            browser.close()


# --- a document, or the lines it is written in -------------------------------


def test_markdown_can_be_read_as_the_lines_it_is_written_in(repo_page):
    """A rendered document has no line to hang a comment on: the paragraph you
    want to remark on came from a line that is no longer there."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.wait_for_selector(".filebody .prose")   # README.md is first
            assert page.locator(".filebody .prose").count() == 1
            assert page.locator(".filebody .code .dline").count() == 0

            page.click(".filebody .where .link")
            page.wait_for_selector(".filebody .code .dline")
            assert page.locator(".filebody .prose").count() == 0
            assert "# The readme" in code_text(page)
            # And every line now carries the `+` that a comment hangs on.
            assert page.locator(".filebody .code .dline .addnote").count() > 0

            page.click(".filebody .where .link")
            page.wait_for_selector(".filebody .prose")
        finally:
            browser.close()


def test_reading_as_text_holds_across_files(repo_page):
    """Someone reviewing one document usually wants to review the next."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.wait_for_selector(".filebody .prose")
            page.click(".filebody .where .link")
            page.wait_for_selector(".filebody .code .dline")
            page.click(".filelist button:has-text('NOTES.md')")
            page.wait_for_function(
                "document.querySelector('.filebody .where').textContent"
                ".includes('NOTES.md')")
            assert page.locator(".filebody .prose").count() == 0
            assert page.locator(".filebody .code .dline").count() > 0
        finally:
            browser.close()


def test_a_file_that_is_not_a_document_has_no_switch(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            open_file(page, "code.py")
            assert page.locator(".filebody .where .link").count() == 0
        finally:
            browser.close()


# --- finding where a file sits ------------------------------------------------


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
            page.wait_for_selector(".filelist button:has-text('SAMPLING.md')")
            page.click(".filelist button:has-text('SAMPLING.md')")
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
            page.fill("#find", "c.py")
            page.wait_for_selector(".filelist button:has-text('c.py')")
            page.click(".filelist button:has-text('c.py')")
            page.wait_for_function(
                "document.querySelector('.filebody .crumbs')"
                ".textContent === 'a/b/c.py'")
            assert page.eval_on_selector(
                ".filebody .crumbs", "el => el.innerText") == "a/b/c.py"
        finally:
            browser.close()
