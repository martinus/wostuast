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
