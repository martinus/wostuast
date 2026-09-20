"""Reviewing a diff and sending it to the agent (PLAN.md 4.9).

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations

import time

import pytest

import conftest
from browser import (
    comment_on_line,
    open_file,
    open_page,
    code_text,
    skip_without_browser,
    sync_playwright,
    fresh_context,
    show_tab,
    numbers,
    open_diff,
    comment_on_first_line,
)

pytestmark = skip_without_browser

def test_a_diff_line_can_be_commented_on(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            assert page.locator(".comment").count() == 0
            page.locator(".dline .addnote").first.click(force=True)
            page.wait_for_selector(".commentbox textarea")
            page.fill(".commentbox textarea", "use a signed type here")
            page.click(".commentbox .verb")
            page.wait_for_selector(".comment")
            assert "use a signed type here" in page.locator(".comment").inner_text()
            # It is written down, not held in the node it was drawn on.
            assert page.evaluate("state.review.comments.length") == 1
            # path and line, and nothing else: a comment is a place in a file.
            assert page.evaluate("state.review.comments[0].anchor").count("\n") == 1
        finally:
            browser.close()


def test_the_plus_shows_when_you_are_on_the_line(repo_page):
    """It sits over the gutter and stays out of the way until you want it, the
    way a pull request does it — so "can you see it" is the whole feature."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            shown = ("() => getComputedStyle("
                     "document.querySelector('.dline .addnote')).opacity")
            assert page.evaluate(shown) == "0"
            page.locator(".dline").first.hover()
            page.wait_for_function(shown + " === '1'")
            # And it is not part of the diff you copy, like the numbers by it.
            assert page.evaluate("() => getComputedStyle("
                                 "document.querySelector('.dline .addnote'))"
                                 ".userSelect") == "none"
        finally:
            browser.close()


def test_a_whole_file_can_be_commented_on(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.locator(".onFile .addnote").first.click()
            page.wait_for_selector(".commentbox textarea")
            page.fill(".commentbox textarea", "keep the heading order")
            page.click(".commentbox .verb")
            page.wait_for_selector(".onFile .comment")
            assert page.evaluate("state.review.comments[0].anchor").endswith("\n0")
        finally:
            browser.close()


def test_a_comment_survives_the_diff_being_read_again(repo_page):
    """The poll replaces the whole answer every couple of seconds. A comment
    is anchored to the line, not to the node the line was drawn on."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.locator(".dline .addnote").first.click(force=True)
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
            page.locator(".dline .addnote").first.click(force=True)
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
            page.locator(".dline .addnote").first.click(force=True)
            page.fill(".commentbox textarea", "first thought")
            page.click(".commentbox .verb")
            page.wait_for_selector(".comment")

            page.click(".comment .link")            # edit
            page.wait_for_selector(".commentbox textarea")
            assert page.input_value(".commentbox textarea") == "first thought"
            page.fill(".commentbox textarea", "second thought")
            page.click(".commentbox .verb")
            page.wait_for_function("state.review.comments[0].note === 'second thought'")

            # Clearing the box and saving is how a comment goes away, so there
            # is no second thing to find and press.
            page.click(".comment .link")
            page.fill(".commentbox textarea", "   ")
            page.click(".commentbox .verb")
            page.wait_for_function("state.review.comments.length === 0")
            assert page.locator(".comment").count() == 0
        finally:
            browser.close()


def test_cancel_leaves_the_comment_as_it_was(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.locator(".dline .addnote").first.click(force=True)
            page.fill(".commentbox textarea", "kept")
            page.click(".commentbox .verb")
            page.wait_for_selector(".comment")
            page.click(".comment .link")
            page.fill(".commentbox textarea", "thrown away")
            page.click(".commentbox .link")         # cancel
            page.wait_for_selector(".comment")
            assert "kept" in page.locator(".comment").inner_text()
            assert page.evaluate("state.review.comments.length") == 1
        finally:
            browser.close()


def test_the_review_belongs_to_the_session_it_is_about(ws, served, repo_page,
                                                      tmp_path):
    """The one chosen is a real second session. It used to be a made-up id,
    and the page does not keep one: the next push of the session list finds
    nothing under it, picks the first session again, and brings its review
    back with it. Correct, and it made the test fail about one run in five."""
    daemon, _ = served
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            # Through the shared helper, which waits for the box to open and
            # for the comment to land. This test hand-rolled the sequence and
            # skipped both waits — it predates the helper.
            comment_on_first_line(page, "about this session")
            page.wait_for_function("state.review.comments.length === 1")

            # The second session arrives now, rather than before the page
            # opened: the page picks the first session it is given, and this
            # one has no repository behind it to draw a diff from.
            other = tmp_path / "elsewhere"
            other.mkdir(exist_ok=True)
            ws.append_event(conftest.event("SessionStart", sid="s2",
                                           cwd=str(other), pane="%9", pid=2,
                                           ts=time.time()))
            daemon.tick()          # nothing polls in a test; this pushes the list
            page.wait_for_function("document.querySelectorAll('.row').length === 2")
            page.evaluate("choose('s2')")
            seen = page.evaluate(
                """() => ({n: state.review.comments.length, chosen: state.chosen})""")
            assert seen == {"n": 0, "chosen": "s2"}

            # And it is still the first session's when you go back to it.
            page.evaluate("choose('s1')")
            page.wait_for_function("state.review.comments.length === 1")
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
            page.locator(".dline .addnote").first.click(force=True)
            page.fill(".commentbox textarea", "do not send me")
            page.click(".commentbox .verb")
            page.wait_for_selector(".comment")
            sent = page.evaluate("window.__posts.filter((u) => u.includes('/send'))")
            assert sent == []
        finally:
            browser.close()


def test_the_review_tab_says_how_many_are_waiting(repo_page):
    """The submit button used to live on the Diff tab, so "is there a review"
    was answered by whether it was there. The tab's own badge answers it now,
    from wherever you are."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            assert page.locator("#reviewcount").is_hidden()
            comment_on_first_line(page, "one thing")
            page.wait_for_selector("#reviewcount:not([hidden])")
            assert page.locator("#reviewcount").inner_text() == "1"
            # And it is not on the Diff tab any more.
            assert page.locator(".diffbody .verb.submit").count() == 0
        finally:
            browser.close()


def test_the_message_is_on_the_tab_and_is_what_would_be_sent(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "use a signed type here")
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .reviewtext")
            shown = page.locator(".reviewbody .reviewtext").inner_text()
            assert shown.startswith("# Task: ")
            assert "use a signed type here" in shown
            assert "\n> " in shown, "the line it is about is quoted"
            # What is shown is what would be sent, byte for byte.
            assert shown.rstrip("\n") == page.evaluate("reviewText()").rstrip("\n")
        finally:
            browser.close()


def test_the_task_and_the_note_go_into_the_message_as_you_type(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "a line note")
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .reviewtext")
            page.fill(".about .field:nth-of-type(1) textarea", "cleanup")
            page.fill(".about .field:nth-of-type(2) textarea",
                      "mostly good, two things")
            page.wait_for_function(
                "document.querySelector('.reviewbody .reviewtext')"
                ".textContent.includes('mostly good, two things')")
            shown = page.locator(".reviewbody .reviewtext").inner_text()
            assert shown.startswith("# Task: cleanup")
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
              state.review.comments = [
                {anchor: "b.py\\n9", quoted: "nine", note: "at nine"},
                {anchor: "b.py\\n0", quoted: "", note: "about the file"},
                {anchor: "a.py\\n2", quoted: "two", note: "at two"},
              ];
            }""")
            shown = page.evaluate("reviewText()")
            assert (shown.index("at two") < shown.index("about the file")
                    < shown.index("at nine"))
            assert "## a.py:2" in shown and "## b.py:9" in shown
            assert "## b.py\n\nabout the file" in shown, \
                "a file comment has no line"
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
            show_tab(page, "review")
            page.click(".reviewbody .verb.submit")
            page.wait_for_function("window.__sent.length === 1")
            assert "change this please" in page.evaluate("window.__sent[0]")
            # It went, so it is gone from here: no sending the same twice.
            page.wait_for_function("state.review.comments.length === 0")
            assert page.locator("#reviewcount").is_hidden()
        finally:
            browser.close()


def test_leaving_the_tab_keeps_what_was_typed(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "still here")
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .reviewtext")
            page.fill(".about .field:nth-of-type(2) textarea", "typed and kept")
            show_tab(page, "diff")
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .reviewtext")
            assert page.evaluate("state.review.comments.length") == 1
            assert page.input_value(
                ".about .field:nth-of-type(2) textarea") == "typed and kept"
        finally:
            browser.close()


def test_a_session_without_a_pane_cannot_be_sent_to(ws, served, repo):
    """The same rule the other verbs already follow: it can be written, it
    just has nowhere to go."""
    git = conftest.git_in

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
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .verb.submit")
            assert page.locator(".reviewbody .verb.submit").is_disabled()
            assert "not running in tmux" in page.locator(
                ".reviewbody .why").inner_text()
        finally:
            browser.close()


def test_r_goes_to_the_review(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.press("body", "r")
            page.wait_for_function("state.tab === 'review'")
            # Nothing written yet, and the tab says so rather than being empty.
            assert "No review yet" in page.locator(".reviewbody .empty").inner_text()
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
            page.locator(".dfile:has(.what:text('untracked')) .dline .addnote").first.click(
                force=True)
            page.wait_for_selector(".commentbox textarea")
            page.fill(".commentbox textarea", "about the notes")
            page.click(".commentbox .verb")
            page.wait_for_function("state.review.comments.length === 1")
            assert page.evaluate("state.review.comments[0].anchor").startswith("NOTES.md\n")
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

            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .reviewtext")
            page.fill(".about .field:nth-of-type(2) textarea", "and so is this")
            page.wait_for_function(
                "document.querySelector('.reviewbody .reviewtext')"
                ".textContent.includes('and so is this')")

            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector(".row")
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .reviewtext")
            assert page.input_value(
                ".about .field:nth-of-type(2) textarea") == "and so is this"
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
            page.wait_for_function("state.review.comments.length === 0")
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
                {task: "fine", overall: 7, comments: [
                  {anchor: "a.py\\n1", quoted: "x", note: "a real one"},
                  {anchor: "a.py\\nnew\\n1", note: "an older anchor shape"},
                  {note: "no anchor"},
                  "not even an object",
                  null,
                ]}));
              recallReview(state.chosen);
            }""")
            assert page.evaluate("state.review.comments.length") == 1
            assert page.evaluate("state.review.task") == "fine"
            assert page.evaluate("state.review.comments[0].note") == "a real one"
            assert page.evaluate("state.review.overall") == "", \
                "a number is not a note"
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


# --- reviewing from the Files tab --------------------------------------------

#: One highlighter span that opens on line 2 and closes on line 4, as a real
#: one returns for a triple-quoted string. The point of painting the file whole.
QUOTE = "'''"
PAINTED = ("a = 1\n"
           '<span class="hljs-string">' + QUOTE + "\n"
           "still inside\n"
           + QUOTE + "</span>\n"
           "b = 2")


def test_any_line_of_any_file_can_be_commented_on(repo_page):
    """Not only a line that happens to be in the diff."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            open_file(page)
            assert page.locator(".filebody .code .dline").count() >= 2
            comment_on_line(page, 1, "the second line, from the file")
            # Anchored to the line, on the side a diff comment would use.
            anchor = page.evaluate("state.review.comments[0].anchor")
            assert anchor.startswith("code.py\n")
            assert anchor.endswith("\n2")
        finally:
            browser.close()


def test_a_comment_made_on_the_diff_shows_in_the_file(repo_page):
    """One anchor, so the two tabs are two views of the same review."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.evaluate(
                "([one]) => { state.review.comments = [one]; }",
                [{"anchor": "code.py\n2", "quoted": "print(2)",
                  "note": "written on the diff tab"}])
            open_file(page)
            page.wait_for_selector(".filebody .comment")
            assert "written on the diff tab" in page.locator(
                ".filebody .comment").inner_text()
        finally:
            browser.close()


def test_the_whole_file_is_highlighted_then_cut_into_lines(repo_page):
    """The point of doing it this way. A block comment or a long string only
    makes sense whole, so the highlighter is given the whole file and its
    answer is cut up afterwards: a span that crosses a newline is closed at
    the end of the line and opened again on the next."""
    root, _ = repo_page
    (root / "code.py").write_text(
        "a = 1\n" + QUOTE + "\nstill inside\n" + QUOTE + "\nb = 2\n")
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.evaluate(
                "([value]) => { hljsAsked = Promise.resolve("
                "{ getLanguage: () => true, highlight: () => ({ value }) }); }",
                [PAINTED])
            open_file(page)
            page.wait_for_selector(".filebody .code .hljs-string")
            # One span per line it covers, not one span swallowing the rows.
            spans = page.eval_on_selector_all(
                ".filebody .code .dline .hljs-string",
                "els => els.map(e => e.textContent)")
            assert spans == [QUOTE, "still inside", QUOTE]
            assert code_text(page) == (
                "a = 1\n" + QUOTE + "\nstill inside\n" + QUOTE + "\nb = 2")
        finally:
            browser.close()


# --- reviewing a file too long to draw whole ---------------------------------


def scroll_to(page, line):
    """Put the window over `line`, and wait for it to arrive."""
    page.evaluate("(n) => { document.querySelector('.filebody')"
                  ".scrollTop = n * 21; }", line)
    page.wait_for_function(
        "(n) => [...document.querySelectorAll('.filebody .code .dline .ln')]"
        ".some((e) => e.textContent.trim() === String(n))", arg=line)


def row_for(page, line):
    """The row drawn for that line number. `long.py` says its own number on
    every line, so the row is found by what it says."""
    return page.locator(".filebody .code .dline").filter(
        has_text=f"line{line - 1} = {line - 1}").first


def test_a_line_of_a_long_file_is_numbered_from_the_file_not_the_window(long_page):
    """Only a slice of the file is drawn, and a slice that thought it started
    at line one would anchor every comment in it to the wrong place."""
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "long.py")
            scroll_to(page, 3000)
            row_for(page, 3000).locator(".addnote").click(force=True)
            page.wait_for_selector(".commentbox textarea")
            page.fill(".commentbox textarea", "about line three thousand")
            page.click(".commentbox .verb")
            page.wait_for_selector(".comment")
            assert page.evaluate("state.review.comments[0].anchor") == "long.py\n3000"
            assert page.evaluate("state.review.comments[0].quoted") == "line2999 = 2999"
        finally:
            browser.close()


def test_a_comment_in_a_long_file_survives_the_file_being_read_again(long_page):
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "long.py")
            scroll_to(page, 3000)
            row_for(page, 3000).locator(".addnote").click(force=True)
            page.wait_for_selector(".commentbox textarea")
            page.fill(".commentbox textarea", "still here")
            page.click(".commentbox .verb")
            page.wait_for_selector(".comment")
            page.evaluate("state.files.mtime += 1; draw()")
            page.wait_for_selector(".comment")
            assert "still here" in page.locator(".comment").inner_text()
            # And the file is still as long as it was: a taller row is counted
            # rather than ignored, so the last line is still reachable.
            page.evaluate("() => { const p = document.querySelector('.filebody');"
                          " p.scrollTop = p.scrollHeight; }")
            page.wait_for_function(
                "(n) => [...document.querySelectorAll('.filebody .code .dline .ln')]"
                ".some((e) => e.textContent.trim() === String(n))",
                arg=conftest.LONG_LINES)
        finally:
            browser.close()


def test_the_window_stands_still_while_a_comment_is_written(long_page):
    """Moving it would throw away what is being typed, which is the rule the
    diff already keeps."""
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "long.py")
            scroll_to(page, 3000)
            row_for(page, 3000).locator(".addnote").click(force=True)
            page.wait_for_selector(".commentbox textarea")
            page.fill(".commentbox textarea", "half a thought")
            page.evaluate("() => { document.querySelector('.filebody')"
                          ".scrollTop = 200 * 21; }")
            page.wait_for_timeout(300)      # proving it did not move
            assert page.input_value(".commentbox textarea") == "half a thought"
        finally:
            browser.close()



# --- the Review tab ----------------------------------------------------------


def test_the_review_tab_shows_every_comment_in_one_place(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "the first thing")
            page.evaluate("""([one]) => { state.review.comments.push(one);
              keepReview(); }""",
              [{"anchor": "other.py\n7", "quoted": "a line",
                "note": "the second thing"}])
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .spot")
            shown = page.locator(".reviewbody").inner_text()
            assert "the first thing" in shown and "the second thing" in shown
            assert "other.py:7" in shown
            # And the left column lists them, the way the other tabs do.
            assert page.locator(".side button").count() == 2
        finally:
            browser.close()


def test_a_comment_can_be_deleted_from_the_review_tab(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "goes away")
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .spot")
            page.click(".reviewbody .comment .link:text('delete')")
            page.wait_for_function("state.review.comments.length === 0")
            assert "No review yet" in page.locator(".reviewbody .empty").inner_text()
        finally:
            browser.close()


def test_the_whole_review_is_deleted_only_on_the_second_press(repo_page):
    """There is no undo, and a review is half an hour of someone's reading."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "careful now")
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .spot")
            page.click(".reviewbody .link:text('delete this review')")
            page.wait_for_selector(".reviewbody .link:text('really delete it?')")
            assert page.evaluate("state.review.comments.length") == 1
            page.click(".reviewbody .link:text('really delete it?')")
            page.wait_for_function("state.review.comments.length === 0")
            assert page.evaluate(
                "Object.keys(localStorage)"
                ".filter((k) => k.startsWith('wostuast-review-')).length") == 0
        finally:
            browser.close()


def test_a_comment_leads_back_to_the_file_it_is_about(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "about this")
            path = page.evaluate("state.review.comments[0].anchor.split('\\n')[0]")
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .spot .crumb")
            page.click(".reviewbody .spot .crumb")
            page.wait_for_function("state.tab === 'files'")
            assert page.evaluate("state.files.path") == path
        finally:
            browser.close()


def test_the_message_is_a_task_with_one_section_per_place(repo_page):
    """The shape the agent gets: a heading it can read at a glance, what to do,
    what to hand back, then `path:line` with the line quoted under it."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.evaluate("""([one]) => {
              state.review.task = "cleanup";
              state.review.overall = "tidy these up";
              state.review.comments = [one];
            }""", [{"anchor": "a.py\n4", "quoted": "x = 1",
                    "note": "use a better name"}])
            shown = page.evaluate("reviewText()")
            assert shown.startswith("# Task: cleanup\n\ntidy these up\n\n")
            assert "write one short entry per location" in shown
            assert "search for the quoted line" in shown
            assert "## a.py:4\n\n> x = 1\n\nuse a better name\n" in shown
            # Nothing about the diff: a comment is a place in a file.
            assert "no longer in the diff" not in shown
        finally:
            browser.close()


def test_a_review_without_a_task_name_still_has_a_heading(repo_page):
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "unnamed")
            assert page.evaluate("reviewText()").startswith("# Task: review\n")
        finally:
            browser.close()


def test_a_removed_line_is_not_offered_a_comment(repo_page):
    """A comment is a place in the file as it is now, and a removed line has
    no such place. It used to anchor to the old side — which the Files tab,
    where every line is a line of the file as it is, could never draw. Once
    the diff moved past it the comment was on no page at all, and was still
    sent."""
    root, _ = repo_page
    root.joinpath("code.py").write_text("print(2)\n")   # the line went away
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.wait_for_selector(".dline.removed")
            assert page.locator(".dline.removed .addnote").count() == 0
            assert page.locator(".dline.added .addnote").count() > 0
            # And every anchor the page can make is a line of the file as it is.
            assert page.evaluate(
                "[...document.querySelectorAll('.dline .addnote')].length > 0")
        finally:
            browser.close()


def test_two_places_in_one_file_cannot_collide(repo_page):
    """`path:40` meant either side of the diff, so a comment on the old line 40
    and one on the new line 40 both printed as `## path:40`."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            anchors = page.evaluate("""() => {
              const seen = new Set();
              for (const row of document.querySelectorAll(".dline")) {
                const plus = row.querySelector(".addnote");
                if (plus) seen.add(plus.title);
              }
              return [...seen];
            }""")
            assert anchors, "there is something to comment on"
            # One anchor per drawn line, and each is `path\nline`.
            made = page.evaluate("anchorOf('a.py', 40)")
            assert made == "a.py\n40" and made.count("\n") == 1
            assert page.evaluate("placeOf('a.py\\n40')") == "a.py:40"
            assert page.evaluate("placeOf('a.py\\n0')") == "a.py"
        finally:
            browser.close()


def test_a_comment_leads_to_its_line_in_a_long_file(long_page):
    """The heading says `path:3000`. Landing at the top of a 6,000-line file
    is telling the reader where to go and then not going there."""
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "long.py")
            page.evaluate("""([one]) => { state.review.comments = [one];
              keepReview(); }""",
              [{"anchor": "long.py\n3000", "quoted": "line2999 = 2999",
                "note": "about this"}])
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .spot .crumb")
            page.click(".reviewbody .spot .crumb")
            page.wait_for_function("state.tab === 'files'")
            page.wait_for_function(
                "[...document.querySelectorAll('.filebody .code .dline .dtext')]"
                ".some((e) => e.textContent === 'line2999 = 2999')")
        finally:
            browser.close()


def test_a_comment_leads_to_its_line_in_a_file_drawn_whole(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            root = repo_page[0]
            root.joinpath("code.py").write_text(
                "".join(f"x{n} = {n}\n" for n in range(400)))
            open_file(page, "code.py")
            page.wait_for_function(
                "document.querySelectorAll('.filebody .code .dline').length > 300")
            page.evaluate("""([one]) => { state.review.comments = [one];
              keepReview(); }""",
              [{"anchor": "code.py\n350", "quoted": "x349 = 349",
                "note": "about this"}])
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .spot .crumb")
            page.click(".reviewbody .spot .crumb")
            page.wait_for_function("state.tab === 'files'")
            page.wait_for_selector(".filebody .code .dline")
            page.wait_for_function(
                "document.querySelector('.filebody').scrollTop > 200")
        finally:
            browser.close()


def test_a_comment_on_a_document_opens_it_as_lines(repo_page):
    """A rendered document has no line 4 to go to, so being asked for one is
    being asked for the lines it is written in."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.wait_for_selector(".filebody .prose")
            page.evaluate("""([one]) => { state.review.comments = [one];
              keepReview(); }""",
              [{"anchor": "README.md\n3", "quoted": "first line",
                "note": "about this"}])
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .spot .crumb")
            page.click(".reviewbody .spot .crumb")
            page.wait_for_function("state.tab === 'files'")
            page.wait_for_selector(".filebody .code .dline")
            assert page.locator(".filebody .prose").count() == 0
            assert page.evaluate("state.files.asText") is True
        finally:
            browser.close()


def test_the_filter_narrows_what_is_shown_and_not_what_is_sent(repo_page):
    """The find box is shared with the other tabs, so a filter left over from
    finding a file is enough. It used to narrow the preview as well, so the
    message said one comment and the send carried two — quoted source the
    reader never saw, on its way into their terminal."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "about the code")
            page.evaluate("""([one]) => { state.review.comments.push(one);
              keepReview(); }""",
              [{"anchor": "elsewhere.md\n9", "quoted": "a line never seen",
                "note": "a note never read"}])
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody .reviewtext")
            page.fill("#find", "code")
            page.wait_for_function(
                "document.querySelectorAll('.reviewbody .spot').length === 1")

            shown = page.locator(".reviewbody .reviewtext").inner_text()
            assert "elsewhere.md" in shown, "the preview is the whole review"
            assert shown.rstrip("\n") == page.evaluate("reviewText()").rstrip("\n")
            # And the strip says the list is narrowed, rather than lying about
            # how many comments there are.
            assert "1 of 2 comments" in page.locator(".listnote").inner_text()
        finally:
            browser.close()


# --- the committed section is HEAD, not the file on disk ---------------------


CLICK_COMMITTED = """(want) => {
  const pane = document.querySelector('.diffbody');
  let committed = false;
  for (const node of pane.children) {
    if (node.classList.contains('diffhead')) {
      committed = node.classList.contains('committed');
      continue;
    }
    if (!committed || !node.classList.contains('dfile')) continue;
    for (const row of node.querySelectorAll('.dline')) {
      if (!row.textContent.includes(want)) continue;
      const plus = row.querySelector('.addnote');
      if (!plus) return 'no + on that line';
      plus.click();
      return 'clicked';
    }
  }
  return 'no such line in the committed section';
}"""


def test_a_committed_line_anchors_to_where_it_is_in_the_worktree(repo_page, ws):
    """The committed section is `base...HEAD`, so its new side is HEAD — not
    the file on disk. A comment belongs to a line of the file as it is, and
    this one was anchored to HEAD's number: with fifty uncommitted lines above
    it, the comment was drawn on the Files tab over a line nobody commented
    on, and the message told the agent the wrong place. Wrong at the moment of
    writing, not because the file moved afterwards."""
    repo, _ = repo_page
    code = repo / "code.py"
    code.write_text("".join(f"new{n}\n" for n in range(50)) + code.read_text())
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.wait_for_function(
                "document.querySelectorAll('.diffhead.committed').length === 1")
            assert page.evaluate(CLICK_COMMITTED, "print(2)") == "clicked"
            page.wait_for_selector(".commentbox textarea")
            # print(2) is line 2 of HEAD and line 52 of the worktree.
            assert page.evaluate("state.writing") == "code.py\n52"
        finally:
            browser.close()


def test_one_line_in_both_sections_opens_one_comment_box(repo_page):
    """A file changed in both sections has the same worktree line twice, and
    two boxes were drawn for it. The later `focus()` won, so the keystrokes
    went to the box off screen — and saving the one the reader could see
    passed an empty note, which means delete. The comment was lost without a
    word."""
    repo, _ = repo_page
    code = repo / "code.py"
    code.write_text(code.read_text() + "print(3)\n")   # uncommitted, after it
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.wait_for_function(
                "document.querySelectorAll('.diffhead.committed').length === 1")
            assert page.evaluate(CLICK_COMMITTED, "print(2)") == "clicked"
            page.wait_for_selector(".commentbox textarea")
            assert page.locator(".commentbox").count() == 1
            assert page.evaluate("state.writing") == "code.py\n2"

            page.fill(".commentbox textarea", "this is the note I typed")
            page.click(".commentbox .verb")
            page.wait_for_selector(".comment")
            notes = page.evaluate(
                "state.review.comments.map((one) => one.note)")
            assert notes == ["this is the note I typed"]
        finally:
            browser.close()


def test_sending_a_review_leaves_the_next_session_alone(ws, served, repo_page,
                                                        tmp_path):
    """`tmux send-keys` takes long enough to press `j` in. Everything after the
    answer worked on whatever was current by then, so it blanked the **new**
    session's draft and removed its key from storage."""
    daemon, _ = served
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            comment_on_first_line(page, "about the first session")
            page.wait_for_function("state.review.comments.length === 1")

            other = tmp_path / "elsewhere"
            other.mkdir(exist_ok=True)
            ws.append_event(conftest.event("SessionStart", sid="s2",
                                           cwd=str(other), pane="%9", pid=2,
                                           ts=time.time()))
            daemon.tick()
            page.wait_for_function(
                "document.querySelectorAll('.row').length === 2")

            # Hold the answer open, the way a slow `tmux send-keys` does.
            page.evaluate("""() => {
              window.__answer = null;
              window.__realTell = tell;
              tell = () => new Promise((done) => { window.__answer = done; });
              submitReview();
            }""")
            page.wait_for_function("window.__answer !== null")

            page.evaluate("choose('s2')")
            page.evaluate("""() => {
              state.review.comments.push(
                {anchor: 'other.py\\n1', note: 'the second session', quoted: ''});
              keepReview();
            }""")
            page.evaluate("window.__answer({ok: true})")
            page.wait_for_function(
                "localStorage.getItem('wostuast-review-s1') === null")

            seen = page.evaluate("""() => ({
              held: state.review.comments.map((one) => one.note),
              stored: localStorage.getItem('wostuast-review-s2'),
            })""")
            assert seen["held"] == ["the second session"]
            assert seen["stored"] and "the second session" in seen["stored"]
        finally:
            browser.close()


def test_a_comment_box_on_one_tab_does_not_freeze_another(repo_page):
    """`holdingText` asked only whether a box was open somewhere. One left on
    the Diff tab froze the Files tab, which had no box on screen to close: the
    pane kept drawing the file the reader had already left."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            page.locator(".dline .addnote").first.click(force=True)
            page.wait_for_selector(".commentbox textarea")

            # The Review tab opens no file, so nothing else can clear it:
            # leaving the tab the box was on is what has to.
            show_tab(page, "review")
            page.wait_for_selector(".reviewbody")
            assert page.evaluate("state.writing") is None, \
                "the box was on the tab you left"

            show_tab(page, "files")
            page.wait_for_selector(".filebody")

            # And the same within one tab: the box belongs to the file it is
            # on, and picking another file takes it away.
            page.click(".filelist button:has-text('code.py')")
            page.wait_for_selector(".filebody .code .dline")
            page.locator(".filebody .dline .addnote").first.click(force=True)
            page.wait_for_selector(".commentbox textarea")
            page.click(".filelist button:has-text('NOTES.md')")
            page.wait_for_function("state.files.path === 'NOTES.md'")
            page.wait_for_function(
                """() => !document.querySelector('.filebody')
                           .textContent.includes('print(1)')""")
            assert page.evaluate("state.writing") is None
        finally:
            browser.close()


def test_a_big_diff_file_stays_open_when_the_agent_saves(repo_page):
    """`open` was a local on the node `drawDiffFile` built, and `drawDiff`
    rebuilds the pane whenever anything is saved — so a file the reader
    expanded snapped shut on the next poll."""
    with sync_playwright() as play:
        browser, page = open_diff(play, repo_page)
        try:
            # Two lines is "big" here, so a small file behaves like a long
            # one and the test does not need a file of ten thousand.
            page.evaluate("BIG_LINES = 2; state.diffAt += 1; draw();")
            shown = """() => {
              const node = [...document.querySelectorAll('.dfile')].find(
                (one) => one.querySelector('.path').textContent === 'README.md');
              return node ? node.querySelectorAll('.dline').length : -1;
            }"""
            page.wait_for_function(
                f"() => ({shown})() === 0")      # over BIG_LINES, so shut
            page.locator(".dfile:has(.path:text-is('README.md')) .name").click()
            page.wait_for_function(f"() => ({shown})() > 0")
            many = page.evaluate(shown)

            page.evaluate("state.diffAt += 1; draw();")   # as a save does
            assert page.evaluate(shown) == many
        finally:
            browser.close()


def test_going_to_a_comment_puts_its_line_on_screen(long_page):
    """`lineTop` assumed every row is `CODE_H` tall. A commented line is
    taller than that, and `fillCode` lays the file out knowing it — so with
    fifteen comments above the target the pane landed 1600 px short of a
    760 px pane, and the line the reader asked for was nowhere on it. Even one
    comment above it threw the landing off by about five rows."""
    with sync_playwright() as play:
        browser, page = open_page(play, long_page)
        try:
            open_file(page, "long.py")
            page.evaluate("""() => {
              for (let n = 10; n <= 150; n += 10) {
                state.review.comments.push({
                  anchor: "long.py\\n" + n, note: "note " + n, quoted: ""});
              }
              state.review.comments.push(
                {anchor: "long.py\\n3000", note: "the one to go to", quoted: ""});
              keepReview();
            }""")
            # Through the Review tab, the way a reader gets there: the button
            # under each comment says where it is.
            show_tab(page, "review")
            page.click(".spot .crumb:text-is('long.py:3000')")
            page.wait_for_function(
                """() => [...document.querySelectorAll('.filebody .code .dline .ln')]
                     .some((e) => e.textContent.trim() === '3000')""")
            seen = page.evaluate("""() => {
              const pane = document.querySelector('.filebody');
              const row = [...pane.querySelectorAll('.dline')].find(
                (one) => one.querySelector('.ln').textContent.trim() === '3000');
              const box = row.getBoundingClientRect();
              const on = pane.getBoundingClientRect();
              return {top: box.top - on.top, height: on.height};
            }""")
            assert 0 <= seen["top"] < seen["height"], seen
        finally:
            browser.close()
