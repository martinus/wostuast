"""The Diff tab.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations


import re
import time

import pytest

import conftest
from browser import (
    kept,
    settings,
    skip_without_browser,
    opened,
    show_tab,
    numbers,
    rgb,
    contrast,
    wait_until,
)

pytestmark = skip_without_browser

def test_the_diff_tab_keeps_the_two_halves_apart(repo_page):
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(".diffhead")
        heads = page.eval_on_selector_all(
            ".diffhead", "els => els.map(e => e.firstChild.textContent)")
        assert heads == ["committed on this branch", "not committed yet"]
        paths = page.eval_on_selector_all(
            ".dfile .path", "els => els.map(e => e.textContent)")
        assert paths == ["code.py", "README.md"]


def test_each_half_of_the_diff_says_what_it_is_a_diff_of(repo_page):
    """The headings were `main...HEAD` and "not committed yet", which is
    precise and only readable if you already know what three dots mean — so
    nobody could tell whether the tab showed the last commit, the branch, the
    worktree, or some of each. #103 opens on exactly that."""
    with opened(repo_page) as page:
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


def test_a_worktree_with_no_default_branch_says_why_there_is_one_half(ws, repo,
                                                                     served,
                                                                     tmp_path):
    """Without a base the committed half is missing altogether, and the tab
    simply showed less — which is the other half of not being able to tell
    what it shows."""
    import subprocess

    # A repository whose branch is not main or master and which has no
    # remote, so `pick_base` finds nothing at all.
    subprocess.run(["git", "-C", str(repo), "branch", "-m", "scratch"],
                   check=True, capture_output=True)
    # A change to a tracked file: the uncommitted half draws a heading only
    # when it has something under it, and a new file is untracked.
    (repo / "README.md").write_text("# readme\n\nhello\n\nand more\n")
    daemon, base = served
    ws.append_event(conftest.event("SessionStart", cwd=str(repo), pane="%7",
                                   pid=1, ts=time.time()))
    daemon.store.refresh()
    with opened(base + "/") as page:
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


def test_a_branch_with_no_commit_in_common_says_so_and_not_that_git_failed(
        ws, repo, served):
    """An orphan branch, or a shallow clone cut above where the branch
    began: `git diff main...HEAD` has no merge base. The tab said "git did
    not answer" under an empty committed half on every poll, for ever."""
    git = conftest.git_in
    git(repo, "checkout", "-q", "--orphan", "pages")
    git(repo, "commit", "-qm", "pages")
    (repo / "README.md").write_text("# readme\n\nhello\n\nand more\n")
    daemon, base = served
    ws.append_event(conftest.event("SessionStart", cwd=str(repo), pane="%7",
                                   pid=1, ts=time.time()))
    daemon.store.refresh()
    with opened(base + "/") as page:
        show_tab(page, "diff")
        page.wait_for_function(
            """() => [...document.querySelectorAll('.diffbody .note')]
                 .some((one) => one.textContent
                   .includes('no commit in common with main'))""")
        notes = page.eval_on_selector_all(
            ".diffbody .note", "els => els.map(e => e.textContent)")
        assert not any("did not answer" in one for one in notes), notes
        heads = page.eval_on_selector_all(
            ".diffhead", "els => els.map(e => e.firstChild.textContent)")
        assert heads == ["not committed yet"], heads
        # With nothing waiting either, it is not "nothing has changed
        # against main": nothing was compared with main. Drawn and read
        # in one call, so a poll cannot land between the two.
        empty = page.evaluate("""() => {
          state.diff = {sections: [], untracked: [], base: 'main',
                        unrelated: true};
          state.diffs.tag += '+';
          draw();
          const one = document.querySelector('.diffbody .empty');
          return one && one.textContent;
        }""")
        assert empty == "Nothing is waiting to be committed.", empty


def test_a_new_or_deleted_file_with_no_lines_says_what_happened(repo_page):
    """git writes no `---`/`+++` for an empty or a binary file, so a new one
    and a deleted one read as "modified", and a new empty file as
    "modified -- The content did not change." """
    root, _ = repo_page
    git = conftest.git_in
    (root / "logo.bin").write_bytes(b"\x89PNG\0old")
    git(root, "add", "logo.bin")
    git(root, "commit", "-qm", "a logo")
    git(root, "rm", "-q", "logo.bin")
    (root / "EMPTY").write_text("")
    (root / "icon.bin").write_bytes(b"\x89PNG\0new")
    git(root, "add", "EMPTY", "icon.bin")
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(
            ".diffhead.uncommitted ~ .dfile:has(.path:text-is('EMPTY'))")
        said = page.evaluate("""() => Object.fromEntries(
          [...document.querySelectorAll('.diffhead.uncommitted ~ .dfile')]
            .map((one) => [one.querySelector('.path').textContent,
                           [one.querySelector('.what').textContent,
                            one.querySelector('.dbody .note')
                              ?.textContent || '']]))""")
        assert said["EMPTY"] == ["added", "A new, empty file."], said
        assert said["icon.bin"][0] == "added", said
        assert said["logo.bin"][0] == "deleted", said
        # The list's icons carry the same word, as a class.
        rows = page.eval_on_selector_all(
            ".filelist.diff button[data-key^='uncommitted']",
            "els => els.map(e => [e.dataset.key.split('\\n')[1],"
            " e.classList.contains('added'), e.classList.contains('deleted')])")
        assert ["EMPTY", True, False] in rows, rows
        assert ["logo.bin", False, True] in rows, rows


def test_a_file_that_became_a_link_is_one_row_one_block_and_one_comment(
        repo_page):
    """git writes a type change as a deletion and an addition of one path,
    and the tab drew both: two rows with one `data-key`, marked together; a
    click on either went to the second block; and a comment on the file
    stood on both blocks, because the anchor is the path. #241."""
    root, _ = repo_page
    git = conftest.git_in
    (root / "notes.txt").write_text("one\ntwo\nthree\n")
    git(root, "add", "notes.txt")
    git(root, "commit", "-qm", "notes")
    (root / "notes.txt").unlink()
    (root / "notes.txt").symlink_to("README.md")
    key = "uncommitted\nnotes.txt"
    block = ".diffhead.uncommitted ~ .dfile:has(.path:text-is('notes.txt'))"
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(block)
        said = page.evaluate("""(key) => {
          const rows = [...document.querySelectorAll('.filelist.diff button')]
            .filter((row) => row.dataset.key === key);
          const blocks = [...document.querySelectorAll(
            '.diffhead.uncommitted ~ .dfile')].filter((one) =>
              one.querySelector('.path').textContent === 'notes.txt');
          const scroll = document.querySelector('.diffscroll');
          return {
            rows: rows.map((row) => [row.classList.contains('typechange'),
                                     row.title]),
            blocks: blocks.map((one) => [
              one.querySelector('.what').textContent,
              [...one.querySelectorAll('.dline')].map((line) =>
                line.querySelector('.addnote') ? 'plus' : 'none')]),
            goes: scroll.blocks.get(key) === blocks[0],
            // In the colour of a modified file, the README beside it.
            colours: [
              [blocks[0].querySelector('.what'), document.querySelector(
                '.diffhead.uncommitted ~ .dfile .what.modified')],
              [rows[0].querySelector('.icon'), document.querySelector(
                '.filelist.diff button.modified .icon')],
            ].map(([one, other]) => [getComputedStyle(one).color,
                                     getComputedStyle(other).color]),
          };
        }""", key)
        assert said["rows"] == [
            [True, "notes.txt \u2014 was a file, now a link"]], said
        # The old lines, then the link, and a `+` on the link alone.
        assert said["blocks"] == [
            ["file \u2192 link", ["none", "none", "none", "plus"]]], said
        assert said["goes"], said
        for one, other in said["colours"]:
            assert one == other, said
        # A comment on the whole file stands once in this half. The
        # committed half shows it too, on the file the branch added.
        page.locator(block + " .onFile .addnote").click(force=True)
        page.fill(".commentbox textarea", "why a link?")
        page.click(".commentbox button:text-is('save')")
        page.wait_for_selector(block + " .comment .says")
        shown = page.evaluate("""() => [...document.querySelectorAll(
          '.diffhead.uncommitted ~ .dfile')].filter((one) =>
            one.querySelector('.path').textContent === 'notes.txt')
          .flatMap((one) => [...one.querySelectorAll('.comment .says')])
          .map((one) => one.textContent)""")
        assert shown == ["why a link?"], shown


def test_the_diff_colours_what_changed(repo_page):
    with opened(repo_page) as page:
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


def test_the_diff_tab_carries_its_counts(repo_page):
    with opened(repo_page) as page:
        show_tab(page, "diff")
        # `show_tab` waits for the tab's frame; the badge over the tab is
        # filled when the diff itself lands, which is one fetch later. It
        # read "+0 −0" on a loaded runner.
        page.wait_for_function(
            """() => { const one = document.getElementById('diffcount');
                       return one && one.innerText.startsWith('+2'); }""")
        badge = page.locator("#diffcount").inner_text()
        assert badge.startswith("+2")     # one line in each half


def test_an_untracked_file_is_named(repo_page):
    with opened(repo_page) as page:
        show_tab(page, "diff")
        # The names are listed once, on the left; the note says what they
        # are. Printing them in both places was the same list twice.
        names = page.eval_on_selector_all(
            ".filelist button", "els => els.map(e => e.textContent)")
        assert "NOTES.md" in names
        assert "1 untracked file" in page.locator(".diffbody .note").inner_text()


def test_an_untracked_file_opens_as_one_added_block(repo_page):
    """git has no diff for it, so it was named and left unclickable — the one
    thing on the tab you could not open."""
    with opened(repo_page) as page:
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


def test_the_find_box_narrows_the_file_list(repo_page):
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.fill("#find", "readme")
        page.wait_for_timeout(400)
        paths = page.eval_on_selector_all(
            ".dfile .path", "els => els.map(e => e.textContent)")
        assert paths == ["README.md"]


def test_a_long_file_starts_closed_and_opens_on_click(repo_page):
    root, _ = repo_page
    import subprocess
    (root / "big.txt").write_text("\n".join(f"line {n}" for n in range(60)))
    subprocess.run(["git", "-C", str(root), "add", "big.txt"], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "big"], check=True,
                   capture_output=True)
    (root / "big.txt").write_text("\n".join(f"changed {n}" for n in range(60)))
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_timeout(400)
        # The page owns the cut-off, so the test moves the page's own
        # number rather than pretending the daemon sent a different one.
        page.evaluate("BIG_LINES = 20; state.diffs.tag += '+'; draw()")
        page.wait_for_timeout(200)
        big = page.locator(".dfile:has-text('big.txt')").last
        assert "hidden" in big.locator(".why").inner_text()
        assert big.locator(".dline").count() == 0
        big.locator(".name").click()
        page.wait_for_timeout(200)
        assert big.locator(".dline").count() > 20


def test_a_diff_line_carries_the_number_it_had_on_each_side(repo_page):
    """`@@ -12,7 +14,9 @@` says where the hunk starts on each side, and the
    rest follows from which lines are there. A removed line has no number on
    the new side and an added one has none on the old side."""
    with opened(repo_page) as page:
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


def test_diff_numbers_are_not_copied_with_the_diff(repo_page):
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(".dline .ln")
        assert page.eval_on_selector(
            ".dline .ln", "el => getComputedStyle(el).userSelect") == "none"


def test_picking_an_untracked_file_moves_the_pane_to_it(repo_page):
    """It is built below everything else, and the pane used to scroll straight
    back to where the reader was, so the click looked like it did nothing."""
    root, _ = repo_page
    # A diff long enough that the pane scrolls at all: the untracked block is
    # built after every hunk, so without the jump it is far below the fold.
    (root / "README.md").write_text(
        "# The readme\n\n" + "".join(f"line {n}\n" for n in range(300)))
    with opened(repo_page) as page:
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


def test_a_file_that_gained_lines_says_so(repo_page):
    """Three places on the page show how far a file moved, all through
    `putCounts`, and all of them wrote `<span class="plus">`. The review's
    hover button took the same class later and gave it
    `position: absolute; opacity: 0` — so every `+n` on the page went
    invisible while the `−n` beside it stayed, and a file that had gained
    lines read as if it had only lost them."""
    with opened(repo_page) as page:
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


def test_an_empty_diff_is_inset_like_a_heading_of_the_diff(repo_page):
    """The Diff tab's body has no padding of its own -- a diff's rows run to
    the edge -- so "Nothing has changed" sat against the left edge, while
    the Review tab's "No review yet" beside it sat properly inset. That tab
    has gone into this one; the empty state still stands where the words
    of a half's heading start. Drop `.diffscroll > .empty` and it goes to
    nought."""
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(".diffscroll .diffhead")
        head = page.evaluate("""() => {
          const one = document.querySelector('.diffscroll .diffhead');
          return one.getBoundingClientRect().left
                 + parseFloat(getComputedStyle(one).paddingLeft)
                 - document.querySelector('.diffbody')
                     .getBoundingClientRect().left;
        }""")
        # The one state this tab is hard to reach with a real worktree:
        # everything committed, nothing untracked.
        page.evaluate("""() => {
          state.diff = {sections: [], untracked: [], base: 'origin/main'};
          state.diffs.tag += '+';
          draw();
        }""")
        page.wait_for_selector(".diffbody .empty")
        assert "Nothing has changed against origin/main." in \
            page.locator(".diffbody .empty").inner_text()
        empty = page.evaluate("""() => {
          const body = document.querySelector('.diffbody');
          return document.querySelector('.diffbody .empty')
                   .getBoundingClientRect().left
                 - body.getBoundingClientRect().left;
        }""")
        assert empty > 10, empty
        assert abs(empty - head) < 1, (empty, head)


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
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_function("(state.diff || {}).commits?.length === 1")
        options = page.eval_on_selector_all(
            ".pickof option", "els => els.map(e => e.textContent)")
        assert options[:2] == ["all changes (1 commit)", "not committed yet"]
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


def test_only_what_is_not_committed(repo_page):
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(".dfile")
        pick(page, "uncommitted")
        heads = page.eval_on_selector_all(
            ".diffhead", "els => els.map(e => e.firstChild.textContent)")
        assert heads == ["not committed yet"]
        assert "NOTES.md" in page.locator(".filelist").inner_text()


def test_the_older_and_newer_buttons_step_through_the_commits(repo_page):
    root, _ = repo_page
    (root / "code.py").write_text("print(1)\nprint(2)\nprint(3)\n")
    conftest.git_in(root, "commit", "-qam", "third")
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_function("(state.diff || {}).commits?.length === 2")
        older, newer = page.locator(".diffbar .step").all()
        # Nothing to step from while everything is shown.
        assert older.is_disabled() and newer.is_disabled()
        where = page.locator(".diffbar .stepat")
        # Hidden, and not only empty: an empty span still takes a gap.
        assert where.evaluate("e => e.hidden") is True
        pick(page, page.evaluate("state.diff.commits[0].sha"))
        assert page.locator(".diffhead").first.inner_text().startswith("third")
        assert newer.is_disabled() and not older.is_disabled()
        # Which of how many, the oldest first.
        assert where.inner_text() == "2 / 2"
        older.click()
        page.wait_for_function(
            "document.querySelector('.diffhead')?.firstChild.textContent"
            " === 'second'")
        assert older.is_disabled() and not newer.is_disabled()
        assert where.inner_text() == "1 / 2"


def test_another_commit_is_read_from_its_top(repo_page):
    """Stepping to the next commit left the pane where the last one had been
    read to, somewhere in the middle of a diff the reader had not started.
    Another commit starts at its top; the same one, drawn again by a poll,
    keeps the place."""
    root, _ = repo_page
    (root / "code.py").write_text("".join("print(%d)\n" % n for n in range(200)))
    conftest.git_in(root, "commit", "-qam", "third")
    (root / "code.py").write_text("".join("print(%d)\n" % -n for n in range(200)))
    conftest.git_in(root, "commit", "-qam", "fourth")
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_function("(state.diff || {}).commits?.length === 3")
        pick(page, page.evaluate("state.diff.commits[0].sha"))
        page.wait_for_function(
            "document.querySelector('.diffscroll').scrollHeight > 3000")
        page.evaluate("document.querySelector('.diffscroll').scrollTop = 2000")
        # A poll draws the same commit again, and the place stands.
        page.evaluate("() => { state.diffs.tag += '+'; draw(); }")
        page.wait_for_function(
            "document.querySelector('.diffscroll').scrollTop === 2000")
        page.click(".diffbar .step >> nth=0")
        page.wait_for_function(
            "document.querySelector('.diffhead')?.firstChild.textContent"
            " === 'third'")
        page.wait_for_timeout(100)      # past the frame a place is put back in
        assert page.evaluate(
            "document.querySelector('.diffscroll').scrollTop") == 0


def test_a_commit_message_is_markdown_and_its_text_is_one_click_away(repo_page):
    """An agent writes its commit messages in Markdown, and the tab drew the
    source. It is drawn now, and "as text" shows it as it was written; this
    browser keeps the choice. The lines `reflow` keeps are kept in both, and
    the click fills the message again and rebuilds nothing else."""
    root, _ = repo_page
    (root / "code.py").write_text("print(1)\nprint(2)\nprint(3)\n")
    conftest.git_in(root, "commit", "-qam", "print three", "-m",
                    "It **refuses** a push:\n\n- `one`\n- two\n\n"
                    "Reviewed-by: someone\nRefs: OA-12")
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_function("(state.diff || {}).commits?.length === 2")
        pick(page, page.evaluate("state.diff.commits[0].sha"))
        message = page.locator(".diffhead.commit .message")
        assert message.locator("strong").inner_text() == "refuses"
        assert message.locator("li").count() == 2
        assert message.locator("code").inner_text() == "one"
        assert "Reviewed-by: someone\nRefs: OA-12" in message.inner_text()
        pressed = """() => [...document.querySelectorAll(
          '.diffhead .readas button')].map((b) => b.getAttribute('aria-pressed'))"""
        assert page.evaluate(pressed) == ["true", "false"]
        # In the subject's line, at its right end.
        got = page.evaluate("""() => {
          const head = document.querySelector('.diffhead.commit');
          const range = document.createRange();
          range.selectNodeContents(head.firstChild);
          const subject = range.getBoundingClientRect();
          const choice = head.querySelector('.readas').getBoundingClientRect();
          const about = head.querySelector('.about').getBoundingClientRect();
          return [subject.bottom > choice.top && subject.top < choice.bottom,
                  head.getBoundingClientRect().right - choice.right,
                  choice.bottom <= about.top + 1];
        }""")
        assert got[0] and got[1] < 40 and got[2], got
        page.evaluate("document.querySelector('.dfile').dataset.kept = 'yes'")
        page.click(".diffhead .readas button[data-value='true']")
        assert message.evaluate("e => e.textContent") == (
            "It **refuses** a push:\n\n- `one`\n- two\n\n"
            "Reviewed-by: someone\nRefs: OA-12")
        assert page.evaluate(pressed) == ["false", "true"]
        assert page.evaluate("document.querySelector('.dfile').dataset.kept") == "yes"
        # Kept in this browser: the next commit drawn is text too.
        page.reload()
        page.wait_for_function("!!window.marked")
        show_tab(page, "diff")
        page.wait_for_function("(state.diff || {}).commits?.length === 2")
        pick(page, page.evaluate("state.diff.commits[0].sha"))
        assert page.locator(".diffhead.commit .message.astext").count() == 1


def test_a_commit_that_went_away_shows_everything_and_says_so(repo_page):
    """An agent that amends takes the commit out from under the reader. The
    daemon will not hand an unknown sha to git; the tab goes back to all
    changes and says why, rather than showing nothing."""
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(".dfile")
        page.evaluate("pickDiff('" + "0" * 40 + "')")
        page.wait_for_function("state.diffs.gone === true && state.diffs.of === ''")
        page.wait_for_selector(".diffscroll > .note")
        assert "no longer on this branch" in page.locator(
            ".diffscroll > .note").first.inner_text()
        assert page.locator(".diffhead").count() == 2
        assert page.eval_on_selector(".pickof", "el => el.value") == ""


def test_a_comment_in_one_commit_anchors_to_the_file_as_it_is(repo_page):
    """One commit's new side is that commit, not the disk. `print(2)` is line
    2 of `second` and, with fifty lines put above it since, line 52 of the
    file. The daemon sends the map from the commit to the disk; drop `since`
    from `inWorktree` and this says 2."""
    root, _ = repo_page
    code = root / "code.py"
    code.write_text("".join(f"new{n}\n" for n in range(50)) + code.read_text())
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_function("(state.diff || {}).commits?.length === 1")
        pick(page, page.evaluate("state.diff.commits[0].sha"))
        row = page.locator(".dfile .dline.added", has_text="print(2)")
        row.locator(".addnote").click(force=True)
        page.wait_for_selector(".commentbox textarea")
        assert page.evaluate("state.writing") == "code.py\n52"


def test_side_by_side_puts_a_changed_line_beside_what_it_became(repo_page, ws):
    root, _ = repo_page
    (root / "code.py").write_text("print(10)\nprint(2)\n")
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(".dline")
        settings(page, "sides", "split")
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
        kept(ws, "diff_columns", "two")
        # It is the reader's, so a reload keeps it.
        page.reload()
        page.wait_for_selector(".row")
        show_tab(page, "diff")
        page.wait_for_selector(".dline.pair")
        page.click("#settings")
        assert page.get_attribute(
            "#setpop .sides button[data-value='split']",
            "aria-pressed") == "true"


def test_a_side_with_no_line_stays_empty_so_the_columns_stay_level(repo_page, ws):
    """`second` added a line and removed none, so its left side is a gap."""
    ws.save_config({"diff_columns": "two"})
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(".dline.pair")
        row = page.locator(".diffhead.committed ~ .dfile .dline.pair.added").first
        assert row.locator(".half.was.none").count() == 1
        assert row.locator(".half.now .dtext").inner_text() == "print(2)"


def test_the_words_that_changed_are_marked_and_a_rewrite_is_not(repo_page):
    root, _ = repo_page
    (root / "code.py").write_text("print(10)\nprint(2)\n")
    (root / "README.md").write_text("Something else entirely here\n\nfirst line\n")
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(".dline .wd")
        code = ".dfile:has(.path:text-is('code.py'))"
        last = page.locator(".dfile:has(.path:text-is('code.py'))").last
        assert last.locator(".dline.removed .wd").all_inner_texts() == ["1"]
        assert last.locator(".dline.added .wd").all_inner_texts() == ["10"]
        readme = page.locator(".dfile:has(.path:text-is('README.md'))")
        assert readme.locator(".dline.removed").count() == 1, code
        assert readme.locator(".wd").count() == 0


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
    with opened(repo_page) as page:
        page.evaluate(PAINT_EVERY_LINE)
        show_tab(page, "diff")
        page.wait_for_selector(".dline.added .dtext .hljs-keyword")
        last = page.locator(".dfile:has(.path:text-is('code.py'))").last
        added = last.locator(".dline.added .dtext").first
        assert added.inner_text() == "print(10)"
        assert added.locator(".hljs-keyword .wd").all_inner_texts() == ["10"]
        # Every row of both sides, and the context ones too.
        assert page.locator(".dline.context .dtext .hljs-keyword").count() > 0


def test_a_save_to_another_file_leaves_the_one_being_read_alone(repo_page):
    """The agent saves a file, the diff comes again, and every file was built
    again from nothing: as plain text, then painted a file at a time behind
    the highlighter and a timer. The file being read lost its colour and its
    word marks and got them back -- the reader saw the text jump. A file
    whose diff did not change keeps its element, and nothing in it is
    touched."""
    root, _ = repo_page
    (root / "other.py").write_text("first()\n")
    conftest.git_in(root, "add", "other.py")
    with opened(repo_page) as page:
        page.evaluate(PAINT_EVERY_LINE)
        show_tab(page, "diff")
        # Painted, so the text is in a span of the highlighter's: `:text-is`
        # matches that span, not the row's text cell.
        added = """(text) => [...document.querySelectorAll('.dline.added .dtext')]
          .some((cell) => cell.textContent === text && cell.querySelector('.hljs-keyword'))"""
        page.wait_for_function(added, arg="first()")
        page.wait_for_function(added, arg="print(2)")
        page.evaluate("""() => {
          window.codeFile = () => [...document.querySelectorAll('.dfile')].find(
            (one) => one.querySelector('.path').textContent === 'code.py');
          window.kept = window.codeFile();
          window.touched = 0;
          new MutationObserver((seen) => { window.touched += seen.length; })
            .observe(window.kept, { childList: true, subtree: true,
                                    characterData: true });
          // Taken out and put back is the same node, and not the same
          // block: it lost its sideways scroll and was laid out again.
          window.out = [];
          new MutationObserver((seen) => seen.forEach(
            (one) => window.out.push(...one.removedNodes)))
            .observe(window.kept.parentNode, { childList: true });
        }""")
        (root / "other.py").write_text("first()\nsecond()\n")
        page.evaluate("loadDiff()")
        page.wait_for_function(added, arg="second()")
        assert page.evaluate("window.codeFile() === window.kept"), \
            "the file being read was built again"
        assert page.evaluate("window.touched") == 0
        assert page.evaluate("window.out.includes(window.kept)") is False


def test_a_file_that_grows_above_leaves_the_reader_where_they_were(repo_page):
    """The reader is in README.md, and the agent adds lines to other.py,
    which stands above it. The pane kept its number, so README.md slid down
    under the reader by as many rows as other.py gained. The block on screen
    stays where it stood."""
    root, _ = repo_page
    (root / "other.py").write_text("first()\n")
    conftest.git_in(root, "add", "other.py")
    (root / "README.md").write_text(
        "# The readme\n\nfirst line\n"
        + "".join(f"added line {n}\n" for n in range(120)))
    with opened(repo_page) as page:
        show_tab(page, "diff")
        shows = """(text) => [...document.querySelectorAll('.dtext')]
          .some((cell) => cell.textContent === text)"""
        page.wait_for_function(shows, arg="added line 119")
        where = """() => {
          const scroll = document.querySelector('.diffbody .dfile').parentNode;
          const readme = [...scroll.querySelectorAll('.dfile')].find(
            (one) => one.querySelector('.path').textContent === 'README.md');
          return readme.getBoundingClientRect().top
            - scroll.getBoundingClientRect().top;
        }"""
        page.evaluate(f"""() => {{
          const scroll = document.querySelector('.diffbody .dfile').parentNode;
          scroll.scrollTop += ({where})() + 200;
        }}""")
        before = page.evaluate(where)
        assert before < -150, "README.md is not where the reader is"
        (root / "other.py").write_text(
            "".join(f"call_{n}()\n" for n in range(30)))
        page.evaluate("loadDiff()")
        page.wait_for_function(shows, arg="call_29()")
        page.wait_for_timeout(100)      # past any frame that sets the place
        assert abs(page.evaluate(where) - before) <= 1


def test_a_diff_of_a_file_with_windows_line_ends_is_painted(repo_page):
    """A CRLF file's diff lines end in CR, and the HTML parser in
    `paintedInto` reads that as one more line break: each side of a hunk
    came back with more lines than it has rows, and none was painted."""
    root, _ = repo_page
    (root / "code.py").write_bytes(b"print(10)\r\nprint(2)\r\n")
    with opened(repo_page) as page:
        page.evaluate(PAINT_EVERY_LINE)
        show_tab(page, "diff")
        last = page.locator(".dfile:has(.path:text-is('code.py'))").last
        last.locator(".dline.added .dtext .hljs-keyword").first.wait_for()
        assert last.locator(".dline.added .dtext").all_inner_texts() == [
            "print(10)", "print(2)"]


def test_a_lone_carriage_return_keeps_the_word_marks_in_place(repo_page):
    """A CR inside a line, as progress output in a log has, was taken out
    before the highlighter. The coloured line was one character short, and
    every word mark after the CR stood one place late: on `0)`, not `10`.
    It becomes a space, as the plain row draws it."""
    root, _ = repo_page
    (root / "code.py").write_bytes(b"a\rprint(10)\nprint(2)\n")
    with opened(repo_page) as page:
        page.evaluate(PAINT_EVERY_LINE)
        show_tab(page, "diff")
        last = page.locator(".dfile:has(.path:text-is('code.py'))").last
        added = last.locator(".dline.added .dtext").first
        added.locator(".hljs-keyword").first.wait_for()
        assert added.text_content() == "a print(10)"
        assert added.locator(".hljs-keyword .wd").all_text_contents() == [
            "a ", "10"]


def test_the_list_is_a_tree_and_the_pane_reads_in_its_order(repo_page):
    """Folders first, then files, at every level -- and the pane beside it in
    the same order, so the two read the same way down. A folder holding only
    a folder is one row."""
    root, _ = repo_page
    (root / "src" / "deep").mkdir(parents=True)
    (root / "src" / "deep" / "a.py").write_text("a = 1\n")
    (root / "zz.txt").write_text("z\n")
    conftest.git_in(root, "add", "src", "zz.txt")
    with opened(repo_page) as page:
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


def test_one_column_shows_a_runs_removed_lines_before_its_added_ones(repo_page):
    """git's own order, and every diff reader's. Pairing lines for the word
    marks once drew them old, new, old, new -- the picture showed it at a
    glance, and no test did."""
    root, _ = repo_page
    (root / "code.py").write_text("print(10)\nprint(20)\n")
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(".diffhead.uncommitted ~ .dfile .dline")
        kinds = page.eval_on_selector_all(
            ".diffhead.uncommitted ~ .dfile:has(.path:text-is('code.py')) .dline",
            "els => els.map(e => e.className.replace('dline ', ''))")
        assert kinds == ["removed", "removed", "added", "added"], kinds


def test_one_commit_shows_its_whole_message(repo_page):
    root, _ = repo_page
    (root / "code.py").write_text("print(1)\nprint(2)\nprint(3)\n")
    conftest.git_in(root, "commit", "-qam", "Print three",
                    "-m", "Two was not enough.\n\n- one\n- two")
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_function("(state.diff || {}).commits?.length === 2")
        pick(page, page.evaluate("state.diff.commits[0].sha"))
        head = page.locator(".diffhead.commit")
        assert head.evaluate("e => e.firstChild.textContent") == "Print three"
        # As it was written, a click away: the lines and the blank line
        # between them.
        page.click(".diffhead .readas button[data-value='true']")
        assert head.locator(".message").evaluate("e => e.textContent") == \
            "Two was not enough.\n\n- one\n- two"
        assert head.locator(".message").evaluate(
            "e => getComputedStyle(e).whiteSpace") == "pre-wrap"
        # And not over all changes, which is no one commit.
        pick(page, "")
        assert page.locator(".diffhead .message").count() == 0


def test_a_diff_in_the_light_is_on_white_and_reads(repo_page):
    """On the code ground, #eceae3, an unchanged line stood at 4.29 against
    its background: under the 4.5 body text needs, and a brown box darker
    than the page it sat on. The card is white in the light now."""
    with opened(repo_page, scheme="light") as page:
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
    with opened(repo_page) as page:
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


def test_a_shown_line_takes_a_comment_where_it_stands(repo_page):
    root, _ = repo_page
    long_change(root)
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(LONG + " .hunk")
        page.locator(LONG + " .hunk").first.locator(".grow").click()
        row = page.locator(LONG + " .dline", has_text="line 10").first
        row.wait_for()
        row.locator(".addnote").click(force=True)
        page.wait_for_selector(".commentbox textarea")
        assert page.evaluate("state.writing") == "long.txt\n10"


def test_shown_lines_come_again_from_the_file_as_it_now_is(repo_page):
    """The whole file is kept against the hunks it came with. The agent
    saves; lines kept from before would put old text between new changes."""
    root, _ = repo_page
    long_change(root)
    with opened(repo_page) as page:
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


def test_the_file_header_stands_on_the_diffs_own_ground(repo_page):
    """It had a colour of its own, darker than the code under it, and read
    as a bar rather than as the top of the file."""
    for scheme in ("light", "dark"):
        with opened(repo_page, scheme=scheme) as page:
            show_tab(page, "diff")
            page.wait_for_selector(".dfile > .name")
            card, head = page.evaluate("""() => [
              getComputedStyle(document.querySelector('.dfile')).backgroundColor,
              getComputedStyle(document.querySelector('.dfile > .name')).backgroundColor]""")
            assert head == card, (scheme, head, card)


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
    with opened(path) as page:
        page.wait_for_function("state.sessions.length === 2")
        page.evaluate("choose('s1')")
        show_tab(page, "diff")
        page.click(".filelist button:has-text('NOTES.md')")
        page.wait_for_selector(".dfile .dtext:text-is('# Notes')")
        page.evaluate("choose('s2')")
        page.evaluate("choose('s1')")
        page.wait_for_selector(".dfile .dtext:text-is('# Notes')")


def test_an_untracked_file_that_could_not_be_read_says_so(repo_page):
    """A failed fetch was drawn as "This file is empty.", and it was kept:
    the failure stayed on screen as the file's content."""
    with opened(repo_page) as page:
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


def test_a_whole_file_that_failed_is_asked_for_again_on_a_click(repo_page):
    """The failure was kept so a draw would not ask git again -- and so every
    later click on the band added a range, drew, and showed nothing."""
    root, _ = repo_page
    long_change(root)
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(LONG + " .hunk")
        page.route("**/whole?*", lambda route: route.abort())
        page.locator(LONG + " .hunk").first.locator(".grow").click()
        page.wait_for_function(
            "[...state.diffs.whole.values()].some(w => !w.asking && !w.file)")
        page.unroute("**/whole?*")
        page.locator(LONG + " .hunk").first.locator(".grow").click()
        page.wait_for_selector(LONG + " .dtext:text-is('line 7')")


def test_a_file_shut_in_one_half_stays_open_in_the_other(repo_page):
    """The choice was kept by the path alone, so shutting a file in the
    committed half shut it in the uncommitted half too, on the next save."""
    root, _ = repo_page
    (root / "code.py").write_text("print(1)\nprint(2)\nprint(3)\n")
    committed = ".diffhead.committed ~ .dfile:has(.path:text-is('code.py'))"
    loose = ".diffhead.uncommitted ~ .dfile:has(.path:text-is('code.py'))"
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(loose + " .dline")
        page.locator(committed).first.locator(".name").click()
        page.evaluate("state.diffs.tag += '+'; draw()")    # the agent saved
        page.wait_for_selector(loose + " .dline")
        assert page.locator(committed).first.locator(".dline").count() == 0


def test_an_untracked_file_git_would_not_list_is_not_its_one_line(
        repo_page, ws, monkeypatch):
    """`is_listed` timing out makes the route answer `missing`, and the page
    drew that sentence as the file's one added line, with a `+` on it."""
    monkeypatch.setattr(ws, "is_listed", lambda *a, **k: False)
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.click(".filelist button:has-text('NOTES.md')")
        page.wait_for_function(
            """() => [...document.querySelectorAll('.dfile')].some(
                 one => one.innerText.includes('could not be read'))""")
        assert untracked_block(page).locator(".dline").count() == 0


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
    with opened(path) as page:
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


def test_a_diff_asked_for_before_the_base_was_picked_does_not_land(
        repo_page, served, ws, monkeypatch):
    """A poll asks for the diff with the base found; the reader picks
    another while it is out, and that pick's answer comes first. The late
    answer is for a base nobody wants now, and drawn it put the release's
    diff under a picker that says `main`."""
    root, path = repo_page
    backport_on_page(repo_page, served, ws, monkeypatch)
    committed = ".diffhead.committed ~ .dfile .path"
    with opened(path) as page:
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
        wait_until(page, lambda: held)
        page.select_option(".pickbase", "main")
        page.wait_for_function(
            f"() => [...document.querySelectorAll('{committed}')]"
            ".some((one) => one.textContent === 'hotfix.txt')")
        held[0].continue_()
        page.wait_for_timeout(700)       # proving the late answer did not land
        assert page.evaluate("state.diff.base") == "main"
        assert "hotfix.txt" in page.locator(committed).all_inner_texts()


def test_a_whole_file_is_asked_for_against_the_base_the_diff_was_drawn_on(
        repo_page):
    """With nothing picked the page sent no base, and the daemon found one
    again for the whole file; a different answer drew another base's lines
    between these hunks."""
    root, _ = repo_page
    long_change(root)
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(LONG + " .hunk")
        asked = []
        page.on("request", lambda one: asked.append(one.url)
                if "/whole?" in one.url else None)
        page.locator(LONG + " .hunk").first.locator(".grow").click()
        page.wait_for_selector(LONG + " .dtext:text-is('line 7')")
        base = page.evaluate("state.diff.base")
        assert base and any("base=" + base in url for url in asked), asked


def test_a_commit_message_wraps_at_the_window_and_links_its_tickets(repo_page, ws):
    """git wraps a message by hand at about 72 columns, and the tab drew it
    as it stood in a box 80 characters wide: lines cut short whatever the
    window. A paragraph's lines are joined now, so the window wraps them; a
    list item and a trailer keep their own lines. And the reader's ticket
    links reach the subject and the message, as they reach the transcript."""
    import json
    root, _ = repo_page
    ws.save_config({"links": [
        {"match": "OA-(\\d+)", "url": "https://tickets.example.com/OA-$1"}]})
    (root / "code.py").write_text("print(1)\nprint(2)\nprint(3)\n")
    conftest.git_in(root, "commit", "-qam", "OA-12: print three", "-m",
                    "Two was not enough, and the reader asked for a third\n"
                    "one, which OA-13 needs as well.\n\n- one\n- two\n\n"
                    "Reviewed-by: someone\nRefs: OA-12")
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_function("(state.diff || {}).commits?.length === 2")
        page.wait_for_function("state.links.length === 1")
        pick(page, page.evaluate("state.diff.commits[0].sha"))
        head = page.locator(".diffhead.commit")
        # The lines as they were joined, which the text shows.
        page.click(".diffhead .readas button[data-value='true']")
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


def test_the_pickers_say_how_many_commits_and_stand_apart_from_against(repo_page):
    """"all changes" said nothing of what it held, and "against" stood inside
    the branch picker and took its room: "against main" was cut to
    "against ma". The count is the branch's own commits; the word stands
    beside the picker; both wear the narrow face, as file names do."""
    with opened(repo_page) as page:
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


def test_a_poll_of_a_diff_that_stands_is_answered_short(repo_page):
    """The Review tab asks every five seconds, and the whole diff came back
    every time, changed or not: on a slow link the one transfer that never
    stopped. The page sends back the tag of the diff it holds and gets
    `same`; a diff that moved comes whole and is drawn."""
    repo, _ = repo_page
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(".dline")
        page.wait_for_function("state.diffs.tag !== ''")
        drawn = page.evaluate("state.diffs.tag")
        with page.expect_response(re.compile(r"/diff\?")) as came:
            page.evaluate("() => { load(); }")
        assert "have=" in came.value.url, came.value.url
        assert came.value.json().get("same") is True
        assert page.evaluate("state.diffs.tag") == drawn
        assert page.locator(".dline").count() > 0

        (repo / "code.py").write_text("print(1)\nprint(2)\nprint(3)\n")
        page.evaluate("() => { load(); }")
        page.wait_for_function("t => state.diffs.tag !== t", arg=drawn)
        page.wait_for_function(
            "[...document.querySelectorAll('.dline')].some("
            "l => l.textContent.includes('print(3)'))")


def tabbed_change(root):
    """A change indented by tabs, with one line too long for the pane."""
    (root / "code.py").write_text(
        "print(1)\nprint(2)\nif x:\n\ty = 1\n\t\tz = 2\n"
        "long = '" + "x" * 400 + "'\n")


def lead(page, text):
    """How far the line holding `text` stands in from the start of its text,
    in widths of one character: what its leading tabs drew as."""
    return page.evaluate("""(text) => {
      const cell = [...document.querySelectorAll('.dline .dtext')]
        .find((one) => one.textContent.trim() === text.trim()
                       && one.textContent.startsWith('\\t'));
      const node = cell.firstChild.nodeType === 3 ? cell.firstChild
        : document.createTreeWalker(cell, NodeFilter.SHOW_TEXT).nextNode();
      const at = node.textContent.search(/[^\\t]/);
      const range = document.createRange();
      range.setStart(node, at); range.setEnd(node, at + 1);
      const ch = range.getBoundingClientRect().width;
      return (range.getBoundingClientRect().left
              - cell.getBoundingClientRect().left) / ch;
    }""", text)


def test_a_tab_in_a_diff_line_is_a_whole_tab_from_where_the_text_starts(
        repo_page):
    """The numbers, the sign and the text stood in one row, so a tab ran from
    the start of the row: a line indented by one tab stood one space in,
    after the `+`, and the reader read it as a single space."""
    root, _ = repo_page
    tabbed_change(root)
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(".dline .dtext:has-text('z = 2')")
        assert abs(lead(page, "\ty = 1") - 4) < 0.2
        assert abs(lead(page, "\t\tz = 2") - 8) < 0.2
        settings(page, "tabwidth", "8")
        assert page.evaluate(
            "document.documentElement.style.getPropertyValue('--tab-w')") == "8"
        assert abs(lead(page, "\ty = 1") - 8) < 0.2


def test_scrolled_sideways_every_line_keeps_its_colour(repo_page):
    """A row was only as wide as the pane unless its own text was longer, so
    scrolled sideways a short added line's green stopped at the pane's edge
    and only the long one went on. Every row of one column is as wide as the
    widest."""
    root, _ = repo_page
    tabbed_change(root)
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(".dline .dtext:has-text('z = 2')")
        widths = page.evaluate("""() => {
          const block = [...document.querySelectorAll('.dlines')].find(
            (one) => one.textContent.includes('z = 2'));
          return [block.scrollWidth, block.clientWidth,
                  [...block.querySelectorAll('.dline')].map(
                    (row) => row.getBoundingClientRect().width)];
        }""")
        wide, pane, rows = widths
        assert wide > pane + 100, widths    # it does scroll sideways
        assert min(rows) >= wide - 1, widths


def test_a_long_line_wraps_under_its_own_text_in_one_column(repo_page):
    """Wrap was the Files tab's alone, and one column only scrolled. Wrapped,
    the rest of the line stands under the text, not under the numbers."""
    root, _ = repo_page
    tabbed_change(root)
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(".dline .dtext:has-text('z = 2')")
        settings(page, "wrapping", "true")
        got = page.evaluate("""() => {
          const cell = [...document.querySelectorAll('.dline .dtext')]
            .find((one) => one.textContent.startsWith("long = '"));
          const block = cell.closest('.dlines');
          const rects = [...cell.getClientRects()];
          const range = document.createRange();
          range.selectNodeContents(cell);
          const lines = [...range.getClientRects()];
          return [block.scrollWidth - block.clientWidth, lines.length,
                  Math.min(...lines.map((r) => r.left)),
                  cell.getBoundingClientRect().left];
        }""")
        spill, lines, left, start = got
        assert spill <= 1, got
        assert lines > 1, got
        assert left >= start - 1, got     # never under the numbers


def test_the_settings_say_what_is_chosen_and_change_it_in_place(repo_page):
    """Everything about this screen is one menu at the end of the tab row:
    it was a bell, a colours button, a menu on the Review bar and two links
    over every file. It says what is chosen, and a choice changes the page
    without rebuilding what is being read."""
    with opened(repo_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(".dline")
        assert page.locator(".diffbar .viewmenu, .filebody .reading").count() == 0
        page.click("#settings")
        pressed = """() => [...document.querySelectorAll(
          '#setpop button[aria-pressed="true"]')].map((b) => b.dataset.value)"""
        assert page.evaluate(pressed) == ["system", "4", "false", "unified"]
        drawn = page.evaluate("state.diffs.tag")
        settings(page, "tabwidth", "2")
        settings(page, "sides", "split")
        page.wait_for_selector(".dline.pair")
        assert page.evaluate(pressed) == ["system", "2", "false", "split"]
        assert page.evaluate("state.diffs.tag") == drawn


def test_another_sessions_diff_is_read_from_its_top(two_repos):
    """`drawDiff` kept the place when `scroll.dataset.of` matched, and it
    held only what the diff was of: "" for everything, in any session. So
    the next session's diff opened 2,000 px down, where the last one had
    been read to."""
    repo, other, base = two_repos
    for where, name in ((repo, "deep/inner.py"), (other, "other.py")):
        with (where / name).open("a") as out:
            out.write("".join(f"more_{n} = {n}\n" for n in range(300)))
    top = "document.querySelector('.diffscroll').scrollTop"
    with opened(base + "/") as page:
        page.wait_for_function("state.sessions.length === 2")
        # Each session was last left on this tab, so a choice keeps the
        # pane, as `j` does between two sessions under review.
        # Its own file, not the pane the last session left: that one
        # is as tall, and a scroll into it was put back to the top when
        # this diff came -- red under load.
        shows = ("(name) => [...document.querySelectorAll("
                 "'.diffscroll .dfile .path')]"
                 ".some((one) => one.textContent === name)")
        for sid, name in (("s2", "other.py"), ("s1", "deep/inner.py")):
            page.evaluate(f"choose('{sid}')")
            show_tab(page, "diff")
            page.wait_for_function(shows, arg=name)
        page.wait_for_function(
            "document.querySelector('.diffscroll').scrollHeight > 3000")
        page.evaluate(f"{top} = 2000")
        page.wait_for_function(f"{top} === 2000")
        page.evaluate("choose('s2')")
        page.wait_for_function(shows, arg="other.py")
        # Past the frame a place is put back in.
        page.evaluate("""() => new Promise((done) =>
          requestAnimationFrame(() => requestAnimationFrame(done)))""")
        assert page.evaluate(top) == 0


def test_an_emoji_that_changed_is_marked_whole(repo_page):
    """`WORD` had no `u` flag, so an emoji was two halves of a pair, and
    for one face changed to another the mark took the second half only:
    the line then drew two broken glyphs where the face had been."""
    with opened(repo_page) as page:
        runs = page.evaluate("wordDiff('face = \"\\u{1F600}\"', "
                             "'face = \"\\u{1F603}\"')")
        assert runs == [[[8, 10]], [[8, 10]]], runs
