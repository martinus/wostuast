"""The Diff tab.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations


import time

import pytest

import conftest
from browser import (
    skip_without_browser,
    sync_playwright,
    open_page,
    show_tab,
    numbers,
)

pytestmark = skip_without_browser

def test_the_diff_tab_keeps_the_two_halves_apart(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(".diffhead")
            heads = page.eval_on_selector_all(
                ".diffhead", "els => els.map(e => e.firstChild.textContent)")
            assert heads == ["committed on this branch", "not committed yet"]
            paths = page.eval_on_selector_all(
                ".dfile .path", "els => els.map(e => e.textContent)")
            assert paths == ["code.py", "README.md"]
        finally:
            browser.close()


def test_each_half_of_the_diff_says_what_it_is_a_diff_of(repo_page):
    """The headings were `main...HEAD` and "not committed yet", which is
    precise and only readable if you already know what three dots mean — so
    nobody could tell whether the tab showed the last commit, the branch, the
    worktree, or some of each. #103 opens on exactly that."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(".diffhead .about")
            said = page.eval_on_selector_all(
                ".diffhead .about", "els => els.map(e => e.textContent)")
            assert len(said) == 2, said
            # The base is named, and so is what it does not include: the
            # three dots are what nobody could read.
            assert "main" in said[0] and "landed on main since" in said[0], said
            assert "last commit" in said[1], said
            # The list on the left says it too, where a heading has no room
            # for a sentence.
            titles = page.eval_on_selector_all(
                ".filelist .head", "els => els.map(e => e.title)")
            assert titles[0] == said[0] and titles[1] == said[1], titles
        finally:
            browser.close()


def test_a_worktree_with_no_default_branch_says_why_there_is_one_half(ws, repo,
                                                                     served,
                                                                     tmp_path):
    """Without a base the committed half is missing altogether, and the tab
    simply showed less — which is the other half of not being able to tell
    what it shows."""
    import subprocess

    # A repository whose branch is not main or master and which has no
    # remote, so `diff_base` finds nothing at all.
    subprocess.run(["git", "-C", str(repo), "branch", "-m", "scratch"],
                   check=True, capture_output=True)
    # A change to a tracked file: the uncommitted half draws a heading only
    # when it has something under it, and a new file is untracked.
    (repo / "README.md").write_text("# readme\n\nhello\n\nand more\n")
    daemon, base = served
    ws.append_event(conftest.event("SessionStart", cwd=str(repo), pane="%7",
                                   pid=1, ts=time.time()))
    daemon.store.refresh()
    with sync_playwright() as play:
        browser, page = open_page(play, base + "/")
        try:
            show_tab(page, "diff")
            page.wait_for_function("() => state.diff !== null")
            assert page.evaluate("state.diff.base") == ""
            page.wait_for_function(
                """() => [...document.querySelectorAll('.diffbody .note')]
                     .some((one) => one.textContent
                       .includes('No default branch to compare against'))""")
            heads = page.eval_on_selector_all(
                ".diffhead", "els => els.map(e => e.firstChild.textContent)")
            assert heads == ["not committed yet"], heads
        finally:
            browser.close()


def test_the_diff_colours_what_changed(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            assert page.locator(".dline.added").count() >= 2
            # `.dtext` is the line itself; the marker beside it is its own
            # span, so what the highlighter is given is exactly the line.
            added = page.eval_on_selector_all(
                ".dline.added .dtext", "els => els.map(e => e.textContent)")
            assert any("second line" in line for line in added)
            marks = page.eval_on_selector_all(
                ".dline.added .sign", "els => els.map(e => e.textContent)")
            assert marks and all(mark == "+" for mark in marks)
            assert len(marks) == len(added)
            # Nothing makes it unselectable, so it is copied with the diff.
            # The numbers are the other way round, and tested as such.
            assert page.eval_on_selector(
                ".dline.added .sign", "el => getComputedStyle(el).userSelect"
            ) != "none"
        finally:
            browser.close()


def test_the_diff_tab_carries_its_counts(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            # `show_tab` waits for the tab's frame; the badge over the tab is
            # filled when the diff itself lands, which is one fetch later. It
            # read "+0 −0" on a loaded runner.
            page.wait_for_function(
                """() => { const one = document.getElementById('diffcount');
                           return one && one.innerText.startsWith('+2'); }""")
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
            row = block.locator(".dline.added").first
            assert row.locator(".sign").inner_text() == "+"
            assert row.locator(".dtext").inner_text() == "# Notes"
            assert block.locator(".dline.removed").count() == 0
            # It is numbered and lined up like every other block. Nothing was
            # removed, so the old side's column stays empty all the way down.
            assert numbers(page, ".dfile:has(.what:text-is('untracked'))"
                           )[:3] == [["", "1"], ["", "2"], ["", "3"]]
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


def test_a_file_that_gained_lines_says_so(repo_page):
    """Three places on the page show how far a file moved, all through
    `putCounts`, and all of them wrote `<span class="plus">`. The review's
    hover button took the same class later and gave it
    `position: absolute; opacity: 0` — so every `+n` on the page went
    invisible while the `−n` beside it stayed, and a file that had gained
    lines read as if it had only lost them."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(".dfile")
            seen = page.evaluate(
                """() => [...document.querySelectorAll('.plus')].map((node) => {
                     const style = getComputedStyle(node);
                     return {text: node.textContent, opacity: style.opacity,
                             position: style.position};
                   })""")
            assert seen, "no line count on the Diff tab at all"
            for one in seen:
                assert one["text"].startswith("+"), one
                assert one["opacity"] == "1", one
                assert one["position"] == "static", one
        finally:
            browser.close()


def test_an_empty_diff_is_inset_like_an_empty_review(repo_page):
    """The Diff tab's body has no padding of its own -- a diff's rows run to
    the edge -- so "Nothing has changed" sat against the left edge while the
    Review tab's "No review yet" sat properly inset. Drop
    `.diffbody > .empty` and the first measurement goes to nought."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(".diffbody > *")
            # The one state this tab is hard to reach with a real worktree:
            # everything committed, nothing untracked.
            page.evaluate("""() => {
              state.diff = {sections: [], untracked: [], base: 'origin/main'};
              state.diffAt += 1;
              draw();
            }""")
            page.wait_for_selector(".diffbody .empty")
            assert "Nothing has changed against origin/main." in \
                page.locator(".diffbody .empty").inner_text()
            diff = page.evaluate("""() => {
              const body = document.querySelector('.diffbody');
              return document.querySelector('.diffbody .empty')
                       .getBoundingClientRect().left
                     - body.getBoundingClientRect().left;
            }""")
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .empty")
            review = page.evaluate("""() => {
              const body = document.querySelector('.reviewbody');
              return document.querySelector('.reviewbody .empty')
                       .getBoundingClientRect().left
                     - body.getBoundingClientRect().left;
            }""")
            assert diff > 10, diff
            assert abs(diff - review) < 1, (diff, review)
        finally:
            browser.close()
