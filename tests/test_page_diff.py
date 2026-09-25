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
    rgb,
    contrast,
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
                ".diffscroll", "el => el.scrollHeight > el.clientHeight + 400"
            ), "the pane does not scroll, so this proves nothing"
            page.click(".filelist button:has-text('NOTES.md')")
            page.wait_for_selector(".dfile .what:text-is('untracked')")
            page.wait_for_timeout(600)
            where = page.eval_on_selector_all(
                ".diffscroll, .dfile:has(.what:text-is('untracked'))", """els => {
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
    `.diffscroll > .empty` and the first measurement goes to nought."""
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


# --- one commit, one column or two, the tree -------------------------------


def pick(page, value):
    """Pick what the tab shows, through the control a reader uses, and wait
    for the answer to be drawn."""
    page.select_option(".pickof", value)
    page.wait_for_function(
        "v => state.diff && (state.diff.of || '') === v && "
        "document.querySelector('.diffscroll > *') !== null", arg=value)


def test_one_commit_is_shown_on_its_own(repo_page):
    """The branch holds one commit, `second`, which added `print(2)`. Picked,
    the tab shows that and nothing else: not the README the agent has not
    committed, and not the untracked file."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_function("(state.diff || {}).commits?.length === 1")
            options = page.eval_on_selector_all(
                ".pickof option", "els => els.map(e => e.textContent)")
            assert options[:2] == ["all changes", "not committed yet"]
            assert options[2].endswith("second"), options
            sha = page.evaluate("state.diff.commits[0].sha")
            pick(page, sha)
            heads = page.eval_on_selector_all(
                ".diffhead", "els => els.map(e => e.firstChild.textContent)")
            assert heads == ["second"]
            assert page.eval_on_selector_all(
                ".dfile .path", "els => els.map(e => e.textContent)") == ["code.py"]
            assert "NOTES.md" not in page.locator(".filelist").inner_text()
            # It is remembered as a choice, and the way back is the same box.
            pick(page, "")
            assert page.locator(".diffhead").count() == 2
        finally:
            browser.close()


def test_only_what_is_not_committed(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(".dfile")
            pick(page, "uncommitted")
            heads = page.eval_on_selector_all(
                ".diffhead", "els => els.map(e => e.firstChild.textContent)")
            assert heads == ["not committed yet"]
            assert "NOTES.md" in page.locator(".filelist").inner_text()
        finally:
            browser.close()


def test_the_older_and_newer_buttons_step_through_the_commits(repo_page):
    root, _ = repo_page
    (root / "code.py").write_text("print(1)\nprint(2)\nprint(3)\n")
    conftest.git_in(root, "commit", "-qam", "third")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_function("(state.diff || {}).commits?.length === 2")
            older, newer = page.locator(".diffbar .step").all()
            # Nothing to step from while everything is shown.
            assert older.is_disabled() and newer.is_disabled()
            pick(page, page.evaluate("state.diff.commits[0].sha"))
            assert page.locator(".diffhead").first.inner_text().startswith("third")
            assert newer.is_disabled() and not older.is_disabled()
            older.click()
            page.wait_for_function(
                "document.querySelector('.diffhead')?.firstChild.textContent"
                " === 'second'")
            assert older.is_disabled() and not newer.is_disabled()
        finally:
            browser.close()


def test_a_commit_that_went_away_shows_everything_and_says_so(repo_page):
    """An agent that amends takes the commit out from under the reader. The
    daemon will not hand an unknown sha to git; the tab goes back to all
    changes and says why, rather than showing nothing."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(".dfile")
            page.evaluate("pickDiff('" + "0" * 40 + "')")
            page.wait_for_function("state.diffGone === true && state.diffOf === ''")
            page.wait_for_selector(".diffscroll > .note")
            assert "no longer on this branch" in page.locator(
                ".diffscroll > .note").first.inner_text()
            assert page.locator(".diffhead").count() == 2
            assert page.eval_on_selector(".pickof", "el => el.value") == ""
        finally:
            browser.close()


def test_a_comment_in_one_commit_anchors_to_the_file_as_it_is(repo_page):
    """One commit's new side is that commit, not the disk. `print(2)` is line
    2 of `second` and, with fifty lines put above it since, line 52 of the
    file. The daemon sends the map from the commit to the disk; drop `since`
    from `inWorktree` and this says 2."""
    root, _ = repo_page
    code = root / "code.py"
    code.write_text("".join(f"new{n}\n" for n in range(50)) + code.read_text())
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_function("(state.diff || {}).commits?.length === 1")
            pick(page, page.evaluate("state.diff.commits[0].sha"))
            row = page.locator(".dfile .dline.added", has_text="print(2)")
            row.locator(".addnote").click(force=True)
            page.wait_for_selector(".commentbox textarea")
            assert page.evaluate("state.writing") == "code.py\n52"
        finally:
            browser.close()


def test_side_by_side_puts_a_changed_line_beside_what_it_became(repo_page):
    root, _ = repo_page
    (root / "code.py").write_text("print(10)\nprint(2)\n")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(".dline")
            page.click(".diffbar .sides button[data-sides='split']")
            page.wait_for_selector(".dline.pair")
            pairs = page.eval_on_selector_all(
                ".diffhead.uncommitted ~ .dfile .dline.pair", """els => els.map(
                  (e) => [...e.querySelectorAll('.half')].map(
                    (h) => [h.className, h.querySelector('.ln').textContent,
                            h.querySelector('.dtext').textContent]))""")
            assert [["half was removed", "1", "print(1)"],
                    ["half now added", "1", "print(10)"]] in pairs, pairs
            # The `+` is on the side that is the file as it is, and only there.
            changed = page.locator(".dline.pair.changed").first
            assert changed.locator(".half.now .addnote").count() == 1
            assert changed.locator(".half.was .addnote").count() == 0
            assert page.evaluate(
                "localStorage.getItem('wostuast-diff-sides')") == "split"
            # It is about this screen, so a reload keeps it.
            page.reload()
            page.wait_for_selector(".row")
            show_tab(page, "diff")
            page.wait_for_selector(".dline.pair")
            assert page.get_attribute(
                ".diffbar .sides button[data-sides='split']",
                "aria-pressed") == "true"
        finally:
            browser.close()


def test_a_side_with_no_line_stays_empty_so_the_columns_stay_level(repo_page):
    """`second` added a line and removed none, so its left side is a gap."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            page.evaluate("localStorage.setItem('wostuast-diff-sides', 'split')")
            page.reload()
            page.wait_for_selector(".row")
            show_tab(page, "diff")
            page.wait_for_selector(".dline.pair")
            row = page.locator(".diffhead.committed ~ .dfile .dline.pair.added").first
            assert row.locator(".half.was.none").count() == 1
            assert row.locator(".half.now .dtext").inner_text() == "print(2)"
        finally:
            browser.close()


def test_the_words_that_changed_are_marked_and_a_rewrite_is_not(repo_page):
    root, _ = repo_page
    (root / "code.py").write_text("print(10)\nprint(2)\n")
    (root / "README.md").write_text("Something else entirely here\n\nfirst line\n")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(".dline .wd")
            code = ".dfile:has(.path:text-is('code.py'))"
            last = page.locator(".dfile:has(.path:text-is('code.py'))").last
            assert last.locator(".dline.removed .wd").all_inner_texts() == ["1"]
            assert last.locator(".dline.added .wd").all_inner_texts() == ["10"]
            readme = page.locator(".dfile:has(.path:text-is('README.md'))")
            assert readme.locator(".dline.removed").count() == 1, code
            assert readme.locator(".wd").count() == 0
        finally:
            browser.close()


# A highlighter that wraps every line it is given in a keyword span, so the
# test can tell painted from plain and count the lines it handed back.
PAINT_EVERY_LINE = """hljsAsked = Promise.resolve({
  getLanguage: () => true,
  highlight: (text) => ({ value: text.split("\\n").map((line) =>
    '<span class="hljs-keyword">' + line.replace(/&/g, '&amp;')
      .replace(/</g, '&lt;') + '</span>').join("\\n") }),
});"""


def test_the_diff_is_painted_and_keeps_its_word_marks(repo_page):
    """Painting replaces what a cell holds, so the marks on the changed words
    have to be put back on top. Take `markWords` out of `paintDiff` and the
    marks go the moment the colour arrives."""
    root, _ = repo_page
    (root / "code.py").write_text("print(10)\nprint(2)\n")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            page.evaluate(PAINT_EVERY_LINE)
            show_tab(page, "diff")
            page.wait_for_selector(".dline.added .dtext .hljs-keyword")
            last = page.locator(".dfile:has(.path:text-is('code.py'))").last
            added = last.locator(".dline.added .dtext").first
            assert added.inner_text() == "print(10)"
            assert added.locator(".hljs-keyword .wd").all_inner_texts() == ["10"]
            # Every row of both sides, and the context ones too.
            assert page.locator(".dline.context .dtext .hljs-keyword").count() > 0
        finally:
            browser.close()


def test_the_list_is_a_tree_and_the_pane_reads_in_its_order(repo_page):
    """Folders first, then files, at every level -- and the pane beside it in
    the same order, so the two read the same way down. A folder holding only
    a folder is one row."""
    root, _ = repo_page
    (root / "src" / "deep").mkdir(parents=True)
    (root / "src" / "deep" / "a.py").write_text("a = 1\n")
    (root / "zz.txt").write_text("z\n")
    conftest.git_in(root, "add", "src", "zz.txt")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(".filelist.diff button.dir")
            rows = page.eval_on_selector_all(
                ".filelist.diff > *", """els => els.map((e) =>
                  (e.classList.contains('head') ? 'head ' : '')
                  + (e.classList.contains('dir') ? 'dir ' : '')
                  + e.textContent)""")
            at = rows.index("head not committed yet")
            assert rows[at + 1:at + 5] == [
                "dir src/deep", "a.py+1", "README.md+1", "zz.txt+1"], rows
            paths = page.eval_on_selector_all(
                ".diffhead.uncommitted ~ .dfile .path",
                "els => els.map(e => e.textContent)")
            assert paths == ["src/deep/a.py", "README.md", "zz.txt"], paths
            # Shutting the folder hides what is in it and moves nothing else.
            page.click(".filelist.diff button.dir:has-text('src/deep')")
            page.wait_for_function(
                "!document.querySelector('.filelist.diff button[data-key$=\"a.py\"]')")
            assert page.locator(".dfile .path:text-is('src/deep/a.py')").count() == 1
            # A file in the tree takes the pane to it, and the tree marks it.
            page.click(".filelist.diff button[data-key$='zz.txt']")
            page.wait_for_selector(".filelist.diff button.chosen[data-key$='zz.txt']")
        finally:
            browser.close()


def test_one_column_shows_a_runs_removed_lines_before_its_added_ones(repo_page):
    """git's own order, and every diff reader's. Pairing lines for the word
    marks once drew them old, new, old, new -- the picture showed it at a
    glance, and no test did."""
    root, _ = repo_page
    (root / "code.py").write_text("print(10)\nprint(20)\n")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(".diffhead.uncommitted ~ .dfile .dline")
            kinds = page.eval_on_selector_all(
                ".diffhead.uncommitted ~ .dfile:has(.path:text-is('code.py')) .dline",
                "els => els.map(e => e.className.replace('dline ', ''))")
            assert kinds == ["removed", "removed", "added", "added"], kinds
        finally:
            browser.close()


def test_one_commit_shows_its_whole_message(repo_page):
    root, _ = repo_page
    (root / "code.py").write_text("print(1)\nprint(2)\nprint(3)\n")
    conftest.git_in(root, "commit", "-qam", "Print three",
                    "-m", "Two was not enough.\n\n- one\n- two")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_function("(state.diff || {}).commits?.length === 2")
            pick(page, page.evaluate("state.diff.commits[0].sha"))
            head = page.locator(".diffhead.commit")
            assert head.evaluate("e => e.firstChild.textContent") == "Print three"
            # As it was written: the lines and the blank line between them.
            assert head.locator(".message").evaluate("e => e.textContent") == \
                "Two was not enough.\n\n- one\n- two"
            assert head.locator(".message").evaluate(
                "e => getComputedStyle(e).whiteSpace") == "pre-wrap"
            # And not over all changes, which is no one commit.
            pick(page, "")
            assert page.locator(".diffhead .message").count() == 0
        finally:
            browser.close()


def test_a_diff_in_the_light_is_on_white_and_reads(repo_page):
    """On the code ground, #eceae3, an unchanged line stood at 4.29 against
    its background: under the 4.5 body text needs, and a brown box darker
    than the page it sat on. The card is white in the light now."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page, scheme="light")
        try:
            show_tab(page, "diff")
            page.wait_for_selector(".dfile .dline.context")
            seen = page.evaluate("""() => {
              const card = document.querySelector('.dfile');
              const line = document.querySelector('.dfile .dline.context');
              return { card: getComputedStyle(card).backgroundColor,
                       ink: getComputedStyle(line).color,
                       page: getComputedStyle(document.body).backgroundColor };
            }""")
            assert rgb(seen["card"]) == [255, 255, 255], seen
            assert contrast(seen["ink"], seen["card"]) >= 4.5, seen
        finally:
            browser.close()


# --- more of a file, between its changes ------------------------------------


def long_change(root):
    """A 120-line file, committed, then changed on disk at 30 and 90."""
    rows = [f"line {n}" for n in range(1, 121)]
    (root / "long.txt").write_text("\n".join(rows) + "\n")
    conftest.git_in(root, "add", "long.txt")
    conftest.git_in(root, "commit", "-qm", "long")
    rows[29] = "changed 30"
    rows[89] = "changed 90"
    (root / "long.txt").write_text("\n".join(rows) + "\n")


LONG = ".diffhead.uncommitted ~ .dfile:has(.path:text-is('long.txt'))"


def shown_numbers(page):
    """The new-side numbers of every row of the long file, in order."""
    return page.eval_on_selector_all(
        LONG + " .dline", """els => els.map(
          (e) => e.querySelector('.ln').textContent.slice(5, 11).trim())
          .filter(Boolean).map(Number)""")


def test_a_band_says_how_many_lines_are_hidden_and_shows_them(repo_page):
    """Bitbucket's way: a band where lines are hidden, twenty more from
    either end, or all of them."""
    root, _ = repo_page
    long_change(root)
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(LONG + " .hunk")
            said = page.eval_on_selector_all(
                LONG + " .hunk .hidden", "els => els.map(e => e.textContent)")
            # 1-26 above the first change, 34-86 between, and whatever is
            # after 93: git showed three lines, so nobody knows yet.
            assert said == ["26 lines hidden", "53 lines hidden",
                            "more of the file below"], said
            assert shown_numbers(page)[:1] == [27]
            # Up from the first change: the twenty lines just above it.
            page.locator(LONG + " .hunk").first.locator(".grow").click()
            page.wait_for_selector(LONG + " .dtext:text-is('line 7')")
            numbers = shown_numbers(page)
            assert numbers[:21] == list(range(7, 28)), numbers
            # All of the middle: the two changes are one hunk now.
            page.locator(LONG + " .hunk", has_text="53 lines hidden") \
                .locator(".link").click()
            page.wait_for_selector(LONG + " .dtext:text-is('line 60')")
            numbers = shown_numbers(page)
            assert numbers == list(range(7, 94)), numbers
            # The whole file has arrived, so the end is known now.
            tail = page.locator(LONG + " .hunk.tail .hidden").inner_text()
            assert tail == "27 lines hidden", tail
        finally:
            browser.close()


def test_a_shown_line_takes_a_comment_where_it_stands(repo_page):
    root, _ = repo_page
    long_change(root)
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(LONG + " .hunk")
            page.locator(LONG + " .hunk").first.locator(".grow").click()
            row = page.locator(LONG + " .dline", has_text="line 10").first
            row.wait_for()
            row.locator(".addnote").click(force=True)
            page.wait_for_selector(".commentbox textarea")
            assert page.evaluate("state.writing") == "long.txt\n10"
        finally:
            browser.close()


def test_shown_lines_come_again_from_the_file_as_it_now_is(repo_page):
    """The whole file is kept against the hunks it came with. The agent
    saves; lines kept from before would put old text between new changes."""
    root, _ = repo_page
    long_change(root)
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(LONG + " .hunk")
            page.locator(LONG + " .hunk").first.locator(".grow").click()
            page.wait_for_selector(LONG + " .dtext:text-is('line 10')")
            rows = (root / "long.txt").read_text().splitlines()
            rows[11] = "twelve, changed while you read"
            (root / "long.txt").write_text("\n".join(rows) + "\n")
            page.evaluate("loadDiff()")
            page.wait_for_selector(
                LONG + " .dline.added .dtext:text-is('twelve, changed while you read')")
            # Still shown, from the new whole file.
            assert page.locator(LONG + " .dtext:text-is('line 10')").count() == 1
        finally:
            browser.close()


def test_the_file_header_stands_on_the_diffs_own_ground(repo_page):
    """It had a colour of its own, darker than the code under it, and read
    as a bar rather than as the top of the file."""
    for scheme in ("light", "dark"):
        with sync_playwright() as play:
            browser, page = open_page(play, repo_page, scheme=scheme)
            try:
                show_tab(page, "diff")
                page.wait_for_selector(".dfile > .name")
                card, head = page.evaluate("""() => [
                  getComputedStyle(document.querySelector('.dfile')).backgroundColor,
                  getComputedStyle(document.querySelector('.dfile > .name')).backgroundColor]""")
                assert head == card, (scheme, head, card)
            finally:
                browser.close()


# --- a failure, or a choice, that outlived what it was about -----------------


def untracked_block(page):
    return page.locator(".dfile:has(.what:text-is('untracked'))")


def test_an_untracked_file_is_read_again_when_its_session_comes_back(
        repo_page, served, ws):
    """The pick came back with the session and the text did not, and
    nothing asked for it: "reading…" for ever, and a click on the name did
    nothing, because it was the name already picked."""
    repo, path = repo_page
    daemon, _ = served
    ws.append_event(conftest.event("SessionStart", sid="s2", cwd=str(repo),
                                   ts=time.time()))
    daemon.store.refresh()
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function("state.sessions.length === 2")
            page.evaluate("choose('s1')")
            show_tab(page, "diff")
            page.click(".filelist button:has-text('NOTES.md')")
            page.wait_for_selector(".dfile .dtext:text-is('# Notes')")
            page.evaluate("choose('s2')")
            page.evaluate("choose('s1')")
            page.wait_for_selector(".dfile .dtext:text-is('# Notes')")
        finally:
            browser.close()


def test_an_untracked_file_that_could_not_be_read_says_so(repo_page):
    """A failed fetch was drawn as "This file is empty.", and it was kept:
    the failure stayed on screen as the file's content."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.route("**/file?*", lambda route: route.abort())
            page.click(".filelist button:has-text('NOTES.md')")
            page.wait_for_function(
                """() => [...document.querySelectorAll('.dfile')].some(
                     one => one.innerText.includes('could not be read'))""")
            assert "empty" not in untracked_block(page).inner_text()
            page.unroute("**/file?*")
            # The next poll asks again.
            page.wait_for_selector(".dfile .dtext:text-is('# Notes')")
        finally:
            browser.close()


def test_a_whole_file_that_failed_is_asked_for_again_on_a_click(repo_page):
    """The failure was kept so a draw would not ask git again -- and so every
    later click on the band added a range, drew, and showed nothing."""
    root, _ = repo_page
    long_change(root)
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(LONG + " .hunk")
            page.route("**/whole?*", lambda route: route.abort())
            page.locator(LONG + " .hunk").first.locator(".grow").click()
            page.wait_for_function(
                "[...state.diffWhole.values()].some(w => !w.asking && !w.file)")
            page.unroute("**/whole?*")
            page.locator(LONG + " .hunk").first.locator(".grow").click()
            page.wait_for_selector(LONG + " .dtext:text-is('line 7')")
        finally:
            browser.close()


def test_a_file_shut_in_one_half_stays_open_in_the_other(repo_page):
    """The choice was kept by the path alone, so shutting a file in the
    committed half shut it in the uncommitted half too, on the next save."""
    root, _ = repo_page
    (root / "code.py").write_text("print(1)\nprint(2)\nprint(3)\n")
    committed = ".diffhead.committed ~ .dfile:has(.path:text-is('code.py'))"
    loose = ".diffhead.uncommitted ~ .dfile:has(.path:text-is('code.py'))"
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(loose + " .dline")
            page.locator(committed).first.locator(".name").click()
            page.evaluate("state.diffAt += 1; draw()")    # the agent saved
            page.wait_for_selector(loose + " .dline")
            assert page.locator(committed).first.locator(".dline").count() == 0
        finally:
            browser.close()


def test_an_untracked_file_git_would_not_list_is_not_its_one_line(
        repo_page, ws, monkeypatch):
    """`is_listed` timing out makes the route answer `missing`, and the page
    drew that sentence as the file's one added line, with a `+` on it."""
    monkeypatch.setattr(ws, "is_listed", lambda *a, **k: False)
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.click(".filelist button:has-text('NOTES.md')")
            page.wait_for_function(
                """() => [...document.querySelectorAll('.dfile')].some(
                     one => one.innerText.includes('could not be read'))""")
            assert untracked_block(page).locator(".dline").count() == 0
        finally:
            browser.close()


def backport_on_page(repo_page, served, ws, monkeypatch):
    """The fixture's repository as a backport: `release` cut from main with
    a commit of its own, and `fix` cut from it. The daemon finds `release`;
    against `main`, the release's own commit shows as the branch's."""
    root, _ = repo_page
    daemon, _ = served
    # The fixture's git gives no worktree root; a real one does.
    monkeypatch.setattr(ws, "git_facts_many", lambda dirs: {
        d: ws.GitFacts(repo="repo", branch="fix", root=str(root)) for d in dirs})
    daemon.store.git_read.clear()
    daemon.tick()
    git = conftest.git_in
    git(root, "stash", "-q", "-u")
    git(root, "checkout", "-qb", "release", "main")
    (root / "hotfix.txt").write_text("only on the release branch\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "release hotfix")
    git(root, "checkout", "-qb", "fix")
    (root / "fix.txt").write_text("the fix\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "the fix")
    return daemon


def test_the_base_can_be_picked_and_is_kept_for_the_worktree(repo_page, served,
                                                            ws, monkeypatch):
    """The daemon finds the branch a worktree was cut from; the reader can
    say otherwise, and that stays with this checkout in this browser."""
    root, path = repo_page
    daemon = backport_on_page(repo_page, served, ws, monkeypatch)
    committed = ".diffhead.committed ~ .dfile .path"
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            show_tab(page, "diff")
            page.wait_for_function(
                """() => { const one = document.querySelector('.pickbase');
                           return one && one.options[0].textContent.includes('release'); }""")
            assert page.locator(committed).all_inner_texts() == ["fix.txt"]
            page.select_option(".pickbase", "main")
            page.wait_for_function(
                "() => [...document.querySelectorAll('.diffhead.committed ~ .dfile .path')]"
                ".some((one) => one.textContent === 'hotfix.txt')")
            page.reload()
            show_tab(page, "diff")
            page.wait_for_function(
                "() => document.querySelector('.pickbase').value === 'main'")
            # Kept for the worktree, not for the directory the agent is in:
            # a `cd src` made a pick keyed on `cwd` look as if never made.
            (root / "src").mkdir()
            ws.append_event(conftest.event(
                "PreToolUse", cwd=str(root / "src"), tool_name="Bash",
                tool_input={"command": "ls"}, ts=time.time()))
            daemon.tick()
            page.wait_for_function(
                "() => state.sessions[0].cwd.endsWith('/src')")
            page.reload()
            show_tab(page, "diff")
            page.wait_for_function(
                "() => document.querySelector('.pickbase').value === 'main'")
        finally:
            browser.close()


def test_a_diff_asked_for_before_the_base_was_picked_does_not_land(
        repo_page, served, ws, monkeypatch):
    """A poll asks for the diff with the base found; the reader picks
    another while it is out, and that pick's answer comes first. The late
    answer is for a base nobody wants now, and drawn it put the release's
    diff under a picker that says `main`."""
    root, path = repo_page
    backport_on_page(repo_page, served, ws, monkeypatch)
    committed = ".diffhead.committed ~ .dfile .path"
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            show_tab(page, "diff")
            page.wait_for_function(
                """() => { const one = document.querySelector('.pickbase');
                           return one && one.options[0].textContent.includes('release'); }""")
            held = []
            page.route("**/diff*", lambda route: held.append(route)
                       if "base=" not in route.request.url and not held
                       else route.continue_())
            # A poll, with no pick. Not awaited: its promise waits on the
            # request held here, and `evaluate` would wait with it.
            page.evaluate("() => { load(); }")
            for _ in range(300):
                if held:
                    break
                page.wait_for_timeout(20)
            page.select_option(".pickbase", "main")
            page.wait_for_function(
                f"() => [...document.querySelectorAll('{committed}')]"
                ".some((one) => one.textContent === 'hotfix.txt')")
            held[0].continue_()
            page.wait_for_timeout(700)       # proving the late answer did not land
            assert page.evaluate("state.diff.base") == "main"
            assert "hotfix.txt" in page.locator(committed).all_inner_texts()
        finally:
            browser.close()


def test_a_whole_file_is_asked_for_against_the_base_the_diff_was_drawn_on(
        repo_page):
    """With nothing picked the page sent no base, and the daemon found one
    again for the whole file; a different answer drew another base's lines
    between these hunks."""
    root, _ = repo_page
    long_change(root)
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_selector(LONG + " .hunk")
            asked = []
            page.on("request", lambda one: asked.append(one.url)
                    if "/whole?" in one.url else None)
            page.locator(LONG + " .hunk").first.locator(".grow").click()
            page.wait_for_selector(LONG + " .dtext:text-is('line 7')")
            base = page.evaluate("state.diff.base")
            assert base and any("base=" + base in url for url in asked), asked
        finally:
            browser.close()


def test_a_commit_message_wraps_at_the_window_and_links_its_tickets(repo_page, ws):
    """git wraps a message by hand at about 72 columns, and the tab drew it
    as it stood in a box 80 characters wide: lines cut short whatever the
    window. A paragraph's lines are joined now, so the window wraps them; a
    list item and a trailer keep their own lines. And the reader's ticket
    links reach the subject and the message, as they reach the transcript."""
    import json
    root, _ = repo_page
    ws.links_path().parent.mkdir(parents=True, exist_ok=True)
    ws.links_path().write_text(json.dumps(
        [{"match": "OA-(\\d+)", "url": "https://tickets.example.com/OA-$1"}]))
    (root / "code.py").write_text("print(1)\nprint(2)\nprint(3)\n")
    conftest.git_in(root, "commit", "-qam", "OA-12: print three", "-m",
                    "Two was not enough, and the reader asked for a third\n"
                    "one, which OA-13 needs as well.\n\n- one\n- two\n\n"
                    "Reviewed-by: someone\nRefs: OA-12")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            page.wait_for_function("(state.diff || {}).commits?.length === 2")
            page.wait_for_function("state.links.length === 1")
            pick(page, page.evaluate("state.diff.commits[0].sha"))
            head = page.locator(".diffhead.commit")
            message = head.locator(".message")
            assert message.evaluate("e => e.textContent") == (
                "Two was not enough, and the reader asked for a third one,"
                " which OA-13 needs as well.\n\n- one\n- two\n\n"
                "Reviewed-by: someone\nRefs: OA-12")
            assert message.evaluate("e => getComputedStyle(e).maxWidth") == "none"
            links = head.locator("a").evaluate_all(
                "els => els.map((a) => [a.textContent, a.href])")
            assert links == [
                ["OA-12", "https://tickets.example.com/OA-12"],
                ["OA-13", "https://tickets.example.com/OA-13"],
                ["OA-12", "https://tickets.example.com/OA-12"]], links
        finally:
            browser.close()


def test_the_pickers_say_how_many_commits_and_stand_apart_from_against(repo_page):
    """"all changes" said nothing of what it held, and "against" stood inside
    the branch picker and took its room: "against main" was cut to
    "against ma". The count is the branch's own commits; the word stands
    beside the picker; both wear the narrow face, as file names do."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            # Narrow enough that the bar cannot hold both pickers whole.
            page.set_viewport_size({"width": 900, "height": 700})
            show_tab(page, "diff")
            page.wait_for_function("(state.diff || {}).commits?.length === 1")
            page.wait_for_function(
                "document.querySelector('.pickbase').options.length > 0")
            out = page.evaluate("""() => {
              const bar = document.querySelector('.diffbar');
              const word = bar.querySelector('.baseword');
              const base = bar.querySelector('.pickbase');
              const narrow = getComputedStyle(document.documentElement)
                .getPropertyValue('--narrow').trim();
              // As wide as its own content: the branch name is read whole,
              // and the commit picker gives way instead.
              const clone = base.cloneNode(true);
              clone.style.cssText = 'position: absolute; visibility: hidden';
              bar.appendChild(clone);
              const whole = clone.getBoundingClientRect().width;
              clone.remove();
              return {all: bar.querySelector('.pickof').options[0].textContent,
                      cut: whole - base.getBoundingClientRect().width,
                      word: word.textContent, shown: !word.hidden,
                      before: word.nextElementSibling === base,
                      names: [...base.options].map((one) => one.textContent),
                      font: [getComputedStyle(base).fontFamily,
                             getComputedStyle(bar.querySelector('.pickof')).fontFamily],
                      narrow};
            }""")
            assert out["all"] == "all changes (1 commit)", out
            assert out["cut"] < 1, out
            assert out["word"] == "against" and out["shown"] and out["before"], out
            assert out["names"] and not any(
                one.startswith("against") for one in out["names"]), out
            same = [one.replace('"', "'") for one in [*out["font"], out["narrow"]]]
            assert same[0] == same[1] == same[2], out
        finally:
            browser.close()
