"""Reviewing a diff and sending it to the agent (CLAUDE.md, **The review**).

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations

import time

import pytest

import conftest
from browser import (
    comment_on_line,
    open_file,
    code_text,
    skip_without_browser,
    opened,
    own_context,
    show_tab,
    numbers,
    comment_on_first_line,
    spy_on_note,
    stub_send,
)

pytestmark = skip_without_browser

def test_a_diff_line_can_be_commented_on(repo_page):
    with opened(repo_page, tab="diff") as page:
        assert page.locator(".comment").count() == 0
        comment_on_first_line(page, "use a signed type here")
        assert "use a signed type here" in page.locator(".comment").inner_text()
        # It is written down, not held in the node it was drawn on.
        assert page.evaluate("state.review.comments.length") == 1
        # path and line, and nothing else: a comment is a place in a file.
        assert page.evaluate("state.review.comments[0].anchor").count("\n") == 1


def test_the_plus_shows_when_you_are_on_the_line(repo_page):
    """It sits over the gutter and stays out of the way until you want it, the
    way a pull request does it — so "can you see it" is the whole feature."""
    with opened(repo_page, tab="diff") as page:
        shown = ("() => getComputedStyle("
                 "document.querySelector('.dline .addnote')).opacity")
        assert page.evaluate(shown) == "0"
        page.locator(".dline").first.hover()
        page.wait_for_function(shown + " === '1'")
        # And it is not part of the diff you copy, like the numbers by it.
        assert page.evaluate("() => getComputedStyle("
                             "document.querySelector('.dline .addnote'))"
                             ".userSelect") == "none"


def test_a_whole_file_can_be_commented_on(repo_page):
    with opened(repo_page, tab="diff") as page:
        page.locator(".onFile .addnote").first.click()
        page.wait_for_selector(".commentbox textarea")
        page.fill(".commentbox textarea", "keep the heading order")
        page.click(".commentbox button:text-is('save')")
        page.wait_for_selector(".onFile .comment")
        assert page.evaluate("state.review.comments[0].anchor").endswith("\n0")


def test_a_comment_survives_the_diff_being_read_again(repo_page):
    """The poll replaces the whole answer every couple of seconds. A comment
    is anchored to the line, not to the node the line was drawn on."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "look again")
        page.evaluate("state.diffs.tag += '+'; draw()")
        assert page.locator(".comment").count() == 1
        assert "look again" in page.locator(".comment").inner_text()


def test_an_open_box_is_not_swept_away_by_the_poll(repo_page):
    """An agent saving a file rebuilds the diff. Doing that under an open box
    would take what is being typed with it, and would move the code the
    comment is about while it is being written."""
    with opened(repo_page, tab="diff") as page:
        page.locator(".dline .addnote").first.click(force=True)
        page.wait_for_selector(".commentbox textarea")
        page.fill(".commentbox textarea", "half a thought")
        page.evaluate("state.diffs.tag += '+'; draw()")
        assert page.input_value(".commentbox textarea") == "half a thought"


def test_a_comment_can_be_edited_and_emptied_away(repo_page):
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "first thought")

        page.click(".comment button:text-is('edit')")            # edit
        page.wait_for_selector(".commentbox textarea")
        assert page.input_value(".commentbox textarea") == "first thought"
        page.fill(".commentbox textarea", "second thought")
        page.click(".commentbox button:text-is('save')")
        page.wait_for_function("state.review.comments[0].note === 'second thought'")

        # Clearing the box and saving is how a comment goes away, so there
        # is no second thing to find and press.
        page.click(".comment button:text-is('edit')")
        page.fill(".commentbox textarea", "   ")
        page.click(".commentbox button:text-is('save')")
        page.wait_for_function("state.review.comments.length === 0")
        assert page.locator(".comment").count() == 0


def test_cancel_leaves_the_comment_as_it_was(repo_page):
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "kept")
        page.click(".comment button:text-is('edit')")
        page.fill(".commentbox textarea", "thrown away")
        page.click(".commentbox button:text-is('cancel')")         # cancel
        page.wait_for_selector(".comment")
        assert "kept" in page.locator(".comment").inner_text()
        assert page.evaluate("state.review.comments.length") == 1


def test_the_review_belongs_to_the_session_it_is_about(ws, served, repo_page,
                                                      tmp_path):
    """The one chosen is a real second session. It used to be a made-up id,
    and the page does not keep one: the next push of the session list finds
    nothing under it, picks the first session again, and brings its review
    back with it. Correct, and it made the test fail about one run in five."""
    daemon, _ = served
    with opened(repo_page, tab="diff") as page:
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


def test_nothing_is_sent_yet(repo_page):
    """Stage 1 of milestone 7 draws and keeps a review. Sending it is stage 2,
    and until then nothing here may reach the terminal."""
    with opened(repo_page, tab="diff") as page:
        page.evaluate("window.__posts = []; const real = window.fetch;"
                      " window.fetch = (u, o) => { window.__posts.push(String(u));"
                      " return real(u, o); };")
        comment_on_first_line(page, "do not send me")
        sent = page.evaluate("window.__posts.filter((u) => u.includes('/send'))")
        assert sent == []


def test_the_review_tab_says_how_many_are_waiting(repo_page):
    """The submit button used to live on the Diff tab, so "is there a review"
    was answered by whether it was there. The tab's own badge answers it now,
    from wherever you are -- and it says what it counts, beside the diff's
    own "+3 -1" on the same tab."""
    with opened(repo_page, tab="diff") as page:
        assert page.locator("#reviewcount").is_hidden()
        comment_on_first_line(page, "one thing")
        page.wait_for_selector("#reviewcount:not([hidden])")
        assert page.locator("#reviewcount").inner_text() == "1 comment"
        assert page.evaluate(
            "$('reviewcount').closest('.tab').dataset.tab") == "diff"
        page.evaluate("""([one]) => { state.review.comments.push(one);
          keepReview(); }""",
          [{"anchor": "other.py\n7", "quoted": "a line", "note": "two"}])
        page.wait_for_function(
            "$('reviewcount').textContent === '2 comments'")


def test_the_message_is_on_the_tab_and_is_what_would_be_sent(repo_page):
    """It stands in the send bar under the diff, beside the button: what
    goes is in view when it is sent."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "use a signed type here")
        page.wait_for_selector("#reviewbar:not([hidden]) #reviewsay")
        shown = page.input_value("#reviewsay")
        assert not shown.startswith("#"), "no heading any more"
        assert "use a signed type here" in shown
        assert "\n> " in shown, "the line it is about is quoted"
        # With nothing said about the whole review, what is shown is
        # what would be sent, byte for byte.
        assert shown.rstrip("\n") == page.evaluate("reviewText()").rstrip("\n")


def test_the_comment_on_the_whole_review_goes_on_top_as_you_type(repo_page):
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "a line note")
        page.wait_for_selector("#reviewbar:not([hidden]) #overall")
        page.fill("#overall", "mostly good, two things")
        page.wait_for_function(
            "state.review.overall === 'mostly good, two things'")
        shown = page.evaluate("reviewText()")
        assert shown.startswith("mostly good, two things\n\n")
        # It comes before the comments, as its own paragraph.
        assert shown.index("mostly good") < shown.index("a line note")
        # And the box under it is the rest of the message, without it.
        assert "mostly good" not in page.input_value("#reviewsay")


def test_the_message_is_ordered_by_file_and_line(repo_page):
    with opened(repo_page, tab="diff") as page:
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


def test_submitting_sends_it_and_empties_the_review(repo_page):
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "change this please")
        stub_send(page, [{"done": True}])
        page.click("#sendreview")
        page.wait_for_function("window.__sent.length === 1")
        assert "change this please" in page.evaluate("window.__sent[0]")
        # It went, so it is gone from here: no sending the same twice.
        page.wait_for_function("state.review.comments.length === 0")
        assert page.locator("#reviewcount").is_hidden()
        assert page.locator("#reviewbar").is_hidden()


def test_a_double_click_sends_a_review_once(repo_page):
    """`tmux send-keys` takes long enough to click twice in, and the second
    click typed the whole review into the pane a second time."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "change this please")
        stub_send(page, [{"done": True}], delay=400)
        page.dblclick("#sendreview")
        page.wait_for_function("state.review.comments.length === 0")
        page.wait_for_timeout(300)
        assert page.evaluate("window.__sent.length") == 1


def test_a_review_that_goes_through_clears_an_earlier_refusal(repo_page):
    """The success only borrowed the slot for four seconds, so the refusal
    before it came back over a review that had been sent."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "change this please")
        stub_send(page, [{"error": "that is too many bytes"}, {"done": True}])
        page.click("#sendreview")
        page.wait_for_function("state.trouble === 'that is too many bytes'")
        page.click("#sendreview")
        page.wait_for_function("state.review.comments.length === 0")
        assert page.evaluate("state.trouble") == ""


def test_leaving_the_tab_keeps_what_was_typed(repo_page):
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "still here")
        page.wait_for_selector("#reviewbar:not([hidden]) #overall")
        page.fill("#overall", "typed and kept")
        show_tab(page, "files")
        show_tab(page, "diff")
        page.wait_for_selector("#reviewbar:not([hidden]) #overall")
        assert page.evaluate("state.review.comments.length") == 1
        assert page.input_value("#overall") == "typed and kept"


def test_a_session_without_a_pane_cannot_be_sent_to(no_pane):
    """The same rule the other verbs already follow: it can be written, it
    just has nowhere to go -- and the button says why where it stands."""
    _, base = no_pane
    with opened(base + "/") as page:
        show_tab(page, "diff")
        page.evaluate("""([one]) => { state.review.comments.push(one);
          keepReview(); }""",
          [{"anchor": "code.py\n1", "quoted": "x", "note": "nowhere to go"}])
        page.wait_for_selector("#reviewbar:not([hidden]) #sendreview")
        assert page.locator("#sendreview").is_disabled()
        assert "not in tmux" in page.get_attribute(
            "#sendreview", "title")


def test_3_goes_to_the_review(repo_page):
    """The Review tab is the diff, under the name of what it is for now."""
    with opened(repo_page) as page:
        page.press("body", "3")
        page.wait_for_function("$('content').dataset.tab === 'diff'")
        assert page.text_content(".tab[data-tab='diff'] .tabkey") == "3"
        assert page.inner_text(".tab[data-tab='diff']").replace("\n", "").startswith("3Review")
        # Nothing written yet, so there is nothing to send.
        assert page.locator("#reviewbar").is_hidden()


def test_an_untracked_file_anchors_its_comments_to_itself(repo_page):
    """git has no diff for an untracked file, so it is drawn from a synthetic
    one. That object carried no path, so every untracked file's comments were
    anchored to `undefined` — and a comment on line 3 of one turned up on line
    3 of every other."""
    with opened(repo_page, tab="diff") as page:
        page.click(".side button[title='NOTES.md']")
        page.wait_for_selector(".dfile .what:text('untracked')")
        page.wait_for_selector(".dline")
        page.locator(".dfile:has(.what:text('untracked')) .dline .addnote").first.click(
            force=True)
        page.wait_for_selector(".commentbox textarea")
        page.fill(".commentbox textarea", "about the notes")
        page.click(".commentbox button:text-is('save')")
        page.wait_for_function("state.review.comments.length === 1")
        assert page.evaluate("state.review.comments[0].anchor").startswith("NOTES.md\n")
        assert "NOTES.md:" in page.evaluate("reviewText()")


# --- the review: milestone 7 stage 3 -----------------------------------------


def test_a_review_survives_a_reload(repo_page):
    """A review is written over ten minutes. Losing it to an F5 is losing the
    work, so it is kept in this browser — and nowhere else."""
    with own_context() as browser:
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

        page.wait_for_selector("#reviewbar:not([hidden]) #overall")
        page.fill("#overall", "and so is this")
        page.wait_for_function("state.review.overall === 'and so is this'")

        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector(".row")
        show_tab(page, "diff")
        page.wait_for_selector("#reviewbar:not([hidden]) #overall")
        assert page.input_value("#overall") == "and so is this"


def test_a_review_that_went_is_not_kept(repo_page):
    with own_context() as browser:
        page = browser.new_page()
        page.goto(repo_page[1], wait_until="domcontentloaded")
        page.wait_for_selector(".row")
        show_tab(page, "diff")
        page.wait_for_selector(".dline")
        comment_on_first_line(page, "goes away")
        page.click(".comment button:text-is('edit')")
        page.fill(".commentbox textarea", "")
        page.click(".commentbox button:text-is('save')")
        page.wait_for_function("state.review.comments.length === 0")
        assert page.evaluate(
            "Object.keys(localStorage)"
            ".filter((k) => k.startsWith('wostuast-review-')).length") == 0


def test_storage_that_is_not_a_review_is_left_out(repo_page):
    """What comes back was written by this page, but a browser's storage is
    not a place to trust blindly."""
    with opened(repo_page, tab="diff") as page:
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
        # A task name from an older page is not a field any more.
        assert page.evaluate("'task' in state.review") is False
        assert page.evaluate("state.review.comments[0].note") == "a real one"
        assert page.evaluate("state.review.overall") == "", \
            "a number is not a note"


def test_a_review_for_a_session_that_is_gone_is_swept_up(repo_page):
    with opened(repo_page, tab="diff") as page:
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
    with opened(repo_page) as page:
        open_file(page)
        assert page.locator(".filebody .code .dline").count() >= 2
        comment_on_line(page, 1, "the second line, from the file")
        # Anchored to the line, on the side a diff comment would use.
        anchor = page.evaluate("state.review.comments[0].anchor")
        assert anchor.startswith("code.py\n")
        assert anchor.endswith("\n2")


def test_a_comment_made_on_the_diff_shows_in_the_file(repo_page):
    """One anchor, so the two tabs are two views of the same review."""
    with opened(repo_page, tab="diff") as page:
        page.evaluate(
            "([one]) => { state.review.comments = [one]; }",
            [{"anchor": "code.py\n2", "quoted": "print(2)",
              "note": "written on the diff tab"}])
        open_file(page)
        page.wait_for_selector(".filebody .comment")
        assert "written on the diff tab" in page.locator(
            ".filebody .comment").inner_text()


def test_the_whole_file_is_highlighted_then_cut_into_lines(repo_page):
    """The point of doing it this way. A block comment or a long string only
    makes sense whole, so the highlighter is given the whole file and its
    answer is cut up afterwards: a span that crosses a newline is closed at
    the end of the line and opened again on the next."""
    root, _ = repo_page
    (root / "code.py").write_text(
        "a = 1\n" + QUOTE + "\nstill inside\n" + QUOTE + "\nb = 2\n")
    with opened(repo_page) as page:
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


# --- reviewing a file too long to draw whole ---------------------------------


def scroll_to(page, line):
    """Put the window over `line`, and wait for it to arrive."""
    page.evaluate("(n) => { document.querySelector('.filescroll')"
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
    with opened(long_page) as page:
        open_file(page, "long.py")
        scroll_to(page, 3000)
        row_for(page, 3000).locator(".addnote").click(force=True)
        page.wait_for_selector(".commentbox textarea")
        page.fill(".commentbox textarea", "about line three thousand")
        page.click(".commentbox button:text-is('save')")
        page.wait_for_selector(".comment")
        assert page.evaluate("state.review.comments[0].anchor") == "long.py\n3000"
        assert page.evaluate("state.review.comments[0].quoted") == "line2999 = 2999"


def test_a_comment_in_a_long_file_survives_the_file_being_read_again(long_page):
    with opened(long_page) as page:
        open_file(page, "long.py")
        scroll_to(page, 3000)
        row_for(page, 3000).locator(".addnote").click(force=True)
        page.wait_for_selector(".commentbox textarea")
        page.fill(".commentbox textarea", "still here")
        page.click(".commentbox button:text-is('save')")
        page.wait_for_selector(".comment")
        page.evaluate("state.files.mtime += 1; draw()")
        page.wait_for_selector(".comment")
        assert "still here" in page.locator(".comment").inner_text()
        # And the file is still as long as it was: a taller row is counted
        # rather than ignored, so the last line is still reachable.
        page.evaluate("() => { const p = document.querySelector('.filescroll');"
                      " p.scrollTop = p.scrollHeight; }")
        page.wait_for_function(
            "(n) => [...document.querySelectorAll('.filebody .code .dline .ln')]"
            ".some((e) => e.textContent.trim() === String(n))",
            arg=conftest.LONG_LINES)


def test_the_window_stands_still_while_a_comment_is_written(long_page):
    """Moving it would throw away what is being typed, which is the rule the
    diff already keeps."""
    with opened(long_page) as page:
        open_file(page, "long.py")
        scroll_to(page, 3000)
        row_for(page, 3000).locator(".addnote").click(force=True)
        page.wait_for_selector(".commentbox textarea")
        page.fill(".commentbox textarea", "half a thought")
        page.evaluate("() => { document.querySelector('.filescroll')"
                      ".scrollTop = 200 * 21; }")
        page.wait_for_timeout(300)      # proving it did not move
        assert page.input_value(".commentbox textarea") == "half a thought"



# --- the review on the Review tab ---------------------------------------------
#
# The Diff tab is where a review is written, read back and sent. What the
# Review tab of its own held is here: every comment listed in the tree, the
# ones no diff shows at the foot of the pane, and the send bar under it.

#: Every comment row in the tree, as the reader sees it.
SAID_ROWS = """() => [...document.querySelectorAll('.filelist.diff button.said')]
  .map((one) => ({name: one.querySelector('.name').textContent,
                  where: one.querySelector('.where').textContent}))"""


def add_comment(page, anchor, note, quoted=""):
    """A comment put straight into the review, and the tab drawn for it."""
    page.evaluate("""([one]) => { state.review.comments.push(one);
      keepReview(); redrawCode(); }""",
      [{"anchor": anchor, "quoted": quoted, "note": note}])


def test_the_tree_lists_every_comment_under_the_files(repo_page):
    """Every comment in one place, which is what the Review tab of its own
    was for: under the files, after a heading of its own, the note's first
    line and where it is. One on a file the diff does not show is listed
    too, and stands at the foot of the pane with the line it quoted."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "the first thing")
        add_comment(page, "other.py\n7", "the second thing\nand more",
                    quoted="a line")
        page.wait_for_function(
            "document.querySelectorAll('.filelist.diff button.said')"
            ".length === 2")
        rows = page.evaluate(SAID_ROWS)
        names = sorted(one["name"] for one in rows)
        assert names == ["the first thing", "the second thing"], rows
        assert "other.py:7" in [one["where"] for one in rows], rows
        # After the files, under its own heading.
        seen = page.evaluate("""() => {
          const list = document.querySelector('.filelist.diff');
          const heads = [...list.querySelectorAll('.head')];
          const last = heads[heads.length - 1];
          const files = [...list.querySelectorAll('button[data-key]')];
          const after = (one, two) => !!(one.compareDocumentPosition(two)
            & Node.DOCUMENT_POSITION_FOLLOWING);
          return {head: last.classList.contains('said')
                          && last.textContent.startsWith('comments'),
                  files: files.length > 0
                         && files.every((one) => after(one, last))};
        }""")
        assert seen == {"head": True, "files": True}, seen
        # other.py is in no diff, so its comment stands at the foot.
        page.wait_for_selector(".diffscroll .diffhead.elsewhere")
        far = page.locator(".diffscroll .comment").filter(
            has_text="the second thing")
        assert far.locator(".quoted").inner_text() == "a line"


def test_a_comment_can_be_deleted_where_it_stands(repo_page):
    """Delete was on the Review tab's copy of a comment only. Every comment
    carries it now, in the diff and at the foot alike."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "goes away")
        add_comment(page, "other.py\n7", "the far one", quoted="a line")
        far = page.locator(".diffscroll .comment").filter(has_text="the far one")
        far.wait_for()
        far.locator("button:text-is('delete')").click()
        page.wait_for_function("state.review.comments.length === 1")
        assert page.locator(".diffhead.elsewhere").count() == 0
        page.click(".diffscroll .comment button:text-is('delete')")
        page.wait_for_function("state.review.comments.length === 0")
        assert page.locator(".comment").count() == 0
        assert page.locator(".filelist.diff .head.said").count() == 0
        assert page.locator("#reviewbar").is_hidden()


def test_the_whole_review_is_deleted_only_on_the_second_press(repo_page):
    """There is no undo, and a review is half an hour of someone's reading."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "careful now")
        head = ".filelist.diff .head.said"
        page.click(f"{head} button:text-is('delete review')")
        page.wait_for_selector(f"{head} button:text-is('really delete it?')")
        assert page.evaluate("state.review.comments.length") == 1
        page.click(f"{head} button:text-is('really delete it?')")
        page.wait_for_function("state.review.comments.length === 0")
        assert page.evaluate(
            "Object.keys(localStorage)"
            ".filter((k) => k.startsWith('wostuast-review-')).length") == 0


def test_a_row_in_the_comments_goes_to_its_comment(repo_page):
    """A comment two hundred lines down a diff is a comment nobody finds by
    scrolling. Its row in the tree puts it on screen."""
    root, _ = repo_page
    root.joinpath("code.py").write_text(
        "".join(f"x{n} = {n}\n" for n in range(200)))
    in_view = """() => {
      const scroll = document.querySelector('.diffscroll');
      const one = [...scroll.querySelectorAll('.comment')].find(
        (node) => node.dataset.anchor === 'code.py\\n190');
      if (!one) return false;
      const at = one.getBoundingClientRect();
      const on = scroll.getBoundingClientRect();
      return at.top >= on.top && at.bottom <= on.bottom;
    }"""
    with opened(repo_page, tab="diff") as page:
        add_comment(page, "code.py\n190", "far down the file",
                    quoted="x189 = 189")
        page.wait_for_selector(".diffscroll .comment")
        page.evaluate("document.querySelector('.diffscroll').scrollTop = 0")
        assert page.evaluate(in_view) is False, "it starts off screen"
        page.click(".filelist.diff button.said")
        page.wait_for_function(in_view)


def test_a_comment_on_a_file_the_diff_does_not_show_stands_under_it(long_page):
    """A comment written on the Files tab, on a file nobody changed, is sent
    with the rest -- so it has to be on the tab it is sent from, and with
    the lines round it, not only the one it quoted."""
    with opened(long_page) as page:
        open_file(page, "long.py")
        row_for(page, 12).locator(".addnote").click(force=True)
        page.wait_for_selector(".commentbox textarea")
        page.fill(".commentbox textarea", "about line twelve")
        page.click(".commentbox button:text-is('save')")
        page.wait_for_selector(".comment")

        show_tab(page, "diff")
        page.wait_for_selector(".diffscroll .diffhead.elsewhere")
        card = ".diffscroll .dfile:has(.path:text-is('long.py'))"
        page.wait_for_selector(f"{card} .dline")
        texts = page.eval_on_selector_all(
            f"{card} .dline .dtext", "els => els.map((e) => e.textContent)")
        # Two lines before it and one after, as the file stands.
        assert texts == ["line9 = 9", "line10 = 10",
                         "line11 = 11", "line12 = 12"], texts
        seen = page.evaluate("""() => {
          const node = [...document.querySelectorAll('.diffscroll .dfile')]
            .find((one) => one.querySelector('.path').textContent === 'long.py');
          const rows = [...node.querySelectorAll('.dline')];
          const said = node.querySelector('.comment');
          return {note: said.innerText,
                  under: said.getBoundingClientRect().top
                         >= rows[2].getBoundingClientRect().bottom,
                  over: said.getBoundingClientRect().bottom
                        <= rows[3].getBoundingClientRect().top};
        }""")
        assert "about line twelve" in seen["note"], seen
        assert seen["under"] and seen["over"], seen
        assert {"name": "about line twelve",
                "where": "long.py:12"} in page.evaluate(SAID_ROWS)


def test_the_send_bar_stands_only_on_the_review_tab_and_only_with_a_review(
        repo_page):
    """It is the transcript's send bar in shape, and on any other tab it
    would stand over a page that is not the review. With nothing written it
    has nothing to say; with only a word on the whole, nothing to send."""
    with opened(repo_page) as page:
        assert page.locator("#reviewbar").is_hidden()
        show_tab(page, "diff")
        page.wait_for_selector(".dline")
        assert page.locator("#reviewbar").is_hidden(), "no review yet"
        comment_on_first_line(page, "one thing")
        page.wait_for_selector("#reviewbar:not([hidden])")
        assert page.locator("#sendreview").is_enabled()
        for tab in ("files", "transcript"):
            show_tab(page, tab)
            assert page.locator("#reviewbar").is_hidden(), tab
        show_tab(page, "diff")
        page.wait_for_selector("#reviewbar:not([hidden])")

        page.evaluate("""() => { state.review.comments = [];
          state.review.overall = 'only this'; keepReview(); }""")
        page.wait_for_function("$('sendreview').disabled")
        assert page.locator("#reviewbar").is_visible()
        assert "nothing to send yet" in page.get_attribute(
            "#sendreview", "title")


def test_the_send_bar_stays_short_and_scrolls(repo_page):
    """The diff is what is read on this tab. The two boxes of the send bar
    grew to 40 and 30 per cent of the window, and on a notebook they took
    two fifths of it from the diff. Now four lines of the comment on the
    whole, five of the message, and then each scrolls."""
    with opened(repo_page, tab="diff") as page:
        page.set_viewport_size({"width": 1366, "height": 768})
        comment_on_first_line(page, "\n".join("line %d" % n for n in range(30)))
        page.wait_for_selector("#reviewbar:not([hidden]) #reviewsay")
        page.fill("#overall", "\n".join("word %d" % n for n in range(20)))
        page.wait_for_function("state.review.overall.startsWith('word 0')")
        got = page.evaluate("""() => ['overall', 'reviewsay'].map((id) => {
          const box = $(id);
          return [box.getBoundingClientRect().height,
                  box.scrollHeight > box.clientHeight];
        })""")
        (over, over_scrolls), (said, said_scrolls) = got
        assert over <= 4 * 18 + 14 + 1 and over_scrolls, got
        assert said <= 5 * 18 + 14 + 1 and said_scrolls, got


def test_what_is_sent_is_the_word_on_the_whole_over_what_the_bar_shows(
        repo_page):
    """The bar shows the comment on the whole review, which is typed, over
    the rest of the message, which is not: a comment is edited where it
    stands, so there is one text and one place it comes from. Send is the
    two, in that order, and nothing else."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "change this")
        page.wait_for_selector("#reviewbar:not([hidden]) #reviewsay")
        assert page.evaluate("$('reviewsay').readOnly") is True
        before = page.input_value("#reviewsay")
        page.evaluate("$('reviewsay').focus()")
        page.keyboard.type("typed over it")
        assert page.input_value("#reviewsay") == before

        page.fill("#overall", "OVERALL WORDS")
        page.wait_for_function("state.review.overall === 'OVERALL WORDS'")
        said = page.input_value("#reviewsay")
        assert "OVERALL" not in said and "change this" in said
        stub_send(page, [{"done": True}])
        page.click("#sendreview")
        page.wait_for_function("window.__sent.length === 1")
        assert page.evaluate("window.__sent[0]") == \
            "OVERALL WORDS\n\n" + said + "\n"


def test_the_message_is_what_to_do_with_one_section_per_place(repo_page):
    """The shape the agent gets: the reader's word on the whole, what to do,
    what to hand back, then `path:line` with the line quoted under it."""
    with opened(repo_page, tab="diff") as page:
        page.evaluate("""([one]) => {
          state.review.overall = "tidy these up";
          state.review.comments = [one];
        }""", [{"anchor": "a.py\n4", "quoted": "x = 1",
                "note": "use a better name"}])
        shown = page.evaluate("reviewText()")
        assert shown.startswith("tidy these up\n\n")
        assert "write one short entry per location" in shown
        assert "search for the quoted line" in shown
        assert "## a.py:4\n\n> x = 1\n\nuse a better name\n" in shown
        # Nothing about the diff: a comment is a place in a file.
        assert "no longer in the diff" not in shown


def test_a_review_with_no_word_on_the_whole_starts_with_what_to_do(repo_page):
    """There is no heading: a box for naming the task was one the reader
    never filled, and asked to be rid of."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "unnamed")
        shown = page.evaluate("reviewText()")
        assert shown.startswith(page.evaluate("REVIEW_HOW[0]") + "\n\n")
        assert "# Task" not in shown


def test_a_removed_line_is_not_offered_a_comment(repo_page):
    """A comment is a place in the file as it is now, and a removed line has
    no such place. It used to anchor to the old side — which the Files tab,
    where every line is a line of the file as it is, could never draw. Once
    the diff moved past it the comment was on no page at all, and was still
    sent."""
    root, _ = repo_page
    root.joinpath("code.py").write_text("print(2)\n")   # the line went away
    with opened(repo_page, tab="diff") as page:
        page.wait_for_selector(".dline.removed")
        assert page.locator(".dline.removed .addnote").count() == 0
        assert page.locator(".dline.added .addnote").count() > 0
        # And every anchor the page can make is a line of the file as it is.
        assert page.evaluate(
            "[...document.querySelectorAll('.dline .addnote')].length > 0")


def test_two_places_in_one_file_cannot_collide(repo_page):
    """`path:40` meant either side of the diff, so a comment on the old line 40
    and one on the new line 40 both printed as `## path:40`."""
    with opened(repo_page, tab="diff") as page:
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


def test_the_filter_narrows_what_is_shown_and_not_what_is_sent(repo_page):
    """The find box is shared with the other tabs, so a filter left over from
    finding a file is enough. It used to narrow the preview as well, so the
    message said one comment and the send carried two — quoted source the
    reader never saw, on its way into their terminal."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "about the code")
        path = page.evaluate("state.review.comments[0].anchor.split('\\n')[0]")
        add_comment(page, "elsewhere.md\n9", "a note never read",
                    quoted="a line never seen")
        page.wait_for_function(
            "document.querySelectorAll('.filelist.diff button.said')"
            ".length === 2")
        page.fill("#find", path)
        page.wait_for_function(
            "document.querySelectorAll('.filelist.diff button.said')"
            ".length === 1")
        assert page.evaluate(SAID_ROWS)[0]["name"] == "about the code"

        shown = page.input_value("#reviewsay")
        assert "elsewhere.md" in shown, "the message is the whole review"
        assert shown.rstrip("\n") == page.evaluate("reviewText()").rstrip("\n")
        stub_send(page, [{"done": True}])
        page.click("#sendreview")
        page.wait_for_function("window.__sent.length === 1")
        assert "a line never seen" in page.evaluate("window.__sent[0]")


# --- the committed section is HEAD, not the file on disk ---------------------


CLICK_COMMITTED = """(want) => {
  const pane = document.querySelector('.diffscroll');
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
    with opened(repo_page, tab="diff") as page:
        page.wait_for_function(
            "document.querySelectorAll('.diffhead.committed').length === 1")
        assert page.evaluate(CLICK_COMMITTED, "print(2)") == "clicked"
        page.wait_for_selector(".commentbox textarea")
        # print(2) is line 2 of HEAD and line 52 of the worktree.
        assert page.evaluate("state.writing") == "code.py\n52"


def test_one_line_in_both_sections_opens_one_comment_box(repo_page):
    """A file changed in both sections has the same worktree line twice, and
    two boxes were drawn for it. The later `focus()` won, so the keystrokes
    went to the box off screen — and saving the one the reader could see
    passed an empty note, which means delete. The comment was lost without a
    word."""
    repo, _ = repo_page
    code = repo / "code.py"
    code.write_text(code.read_text() + "print(3)\n")   # uncommitted, after it
    with opened(repo_page, tab="diff") as page:
        page.wait_for_function(
            "document.querySelectorAll('.diffhead.committed').length === 1")
        assert page.evaluate(CLICK_COMMITTED, "print(2)") == "clicked"
        page.wait_for_selector(".commentbox textarea")
        assert page.locator(".commentbox").count() == 1
        assert page.evaluate("state.writing") == "code.py\n2"

        page.fill(".commentbox textarea", "this is the note I typed")
        page.click(".commentbox button:text-is('save')")
        page.wait_for_selector(".comment")
        notes = page.evaluate(
            "state.review.comments.map((one) => one.note)")
        assert notes == ["this is the note I typed"]


def test_a_committed_line_follows_lines_added_above_it_since(repo_page):
    """A block of the committed half is kept while its own diff stands, but
    a comment on it is put where the line is on disk, and that is read off
    the uncommitted diff (`inWorktree`). The agent added lines above it
    without committing; the kept block anchored the comment as before, on
    whatever line now stands there."""
    repo, _ = repo_page
    with opened(repo_page, tab="diff") as page:
        page.wait_for_function(
            "document.querySelectorAll('.diffhead.committed').length === 1")
        code = repo / "code.py"
        code.write_text("".join(f"# {n}\n" for n in range(50)) + code.read_text())
        page.evaluate("loadDiff()")
        page.wait_for_function("""() => [...document.querySelectorAll('.dtext')]
          .some((cell) => cell.textContent === '# 49')""")
        assert page.evaluate(CLICK_COMMITTED, "print(2)") == "clicked"
        page.wait_for_selector(".commentbox textarea")
        assert page.evaluate("state.writing") == "code.py\n52"


def test_sending_a_review_leaves_the_next_session_alone(ws, served, repo_page,
                                                        tmp_path):
    """`tmux send-keys` takes long enough to press `j` in. Everything after the
    answer worked on whatever was current by then, so it blanked the **new**
    session's draft and removed its key from storage."""
    daemon, _ = served
    with opened(repo_page, tab="diff") as page:
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


def test_a_comment_box_on_one_tab_does_not_freeze_another(repo_page):
    """`holdingText` asked only whether a box was open somewhere. One left on
    the Diff tab froze the Files tab, which had no box on screen to close: the
    pane kept drawing the file the reader had already left."""
    with opened(repo_page, tab="diff") as page:
        page.locator(".dline .addnote").first.click(force=True)
        page.wait_for_selector(".commentbox textarea")

        # The Transcript tab opens no file, so nothing else can clear
        # it: leaving the tab the box was on is what has to.
        show_tab(page, "transcript")
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


def test_a_big_diff_file_stays_open_when_the_agent_saves(repo_page):
    """`open` was a local on the node `drawDiffFile` built, and `drawDiff`
    rebuilds the pane whenever anything is saved — so a file the reader
    expanded snapped shut on the next poll."""
    with opened(repo_page, tab="diff") as page:
        # Two lines is "big" here, so a small file behaves like a long
        # one and the test does not need a file of ten thousand.
        page.evaluate("BIG_LINES = 2; state.diffs.tag += '+'; draw();")
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

        page.evaluate("state.diffs.tag += '+'; draw();")   # as a save does
        assert page.evaluate(shown) == many


# --- where the buttons are, and what they look like --------------------------

def test_what_you_can_do_to_a_comment_sits_at_its_right_edge(repo_page):
    """The note is what a reader came for. The buttons are not, so they get
    out of its way: the note starts right after the icon that says whose it
    is, and `delete` ends at the block's right, on the note's own line. Take
    `flex-grow` off `.comment .words` and the buttons land right after the
    last word of the note instead."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "a thought worth reading")
        seen = page.evaluate("""() => {
          const box = document.querySelector('.comment');
          const icon = box.querySelector('svg.icon');
          const note = box.querySelector('.says');
          const all = box.querySelectorAll('.acts button');
          const last = all[all.length - 1].getBoundingClientRect();
          const its = box.getBoundingClientRect();
          const at = note.getBoundingClientRect();
          return {
            wide: its.width,
            iconFirst: icon.getBoundingClientRect().right <= at.left,
            afterIcon: at.left - icon.getBoundingClientRect().right,
            lastRight: its.right - last.right,
            sameLine: Math.abs(last.top - at.top) < 12,
          };
        }""")
        assert seen["wide"] > 200, seen
        assert seen["iconFirst"] and seen["afterIcon"] < 16, seen
        assert seen["lastRight"] < 20, seen
        assert seen["sameLine"], seen


def test_edit_and_delete_look_like_buttons(repo_page):
    """They were `.link` — text you have to find out is clickable. A button
    has an edge and a shape. Put either back to `.link` and the border goes
    to none, which is what this asks about."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "looks like what it is")
        # Both, on the comment where it stands: delete used to be on the
        # Review tab's copy of it only.
        seen = page.eval_on_selector_all(
            ".diffscroll .comment .acts button",
            """els => els.map((one) => {
                 const style = getComputedStyle(one);
                 return [one.textContent, style.borderTopWidth,
                         style.borderTopStyle, style.borderRadius];
               })""")
        assert [one[0] for one in seen] == ["edit", "delete"], seen
        for _, width, kind, round_ in seen:
            assert width != "0px" and kind == "solid", seen
            assert round_ != "0px", seen


def test_the_box_keeps_its_own_buttons_under_the_field_on_the_right(repo_page):
    """Save and cancel end where the field ends, and the one that does
    something is nearest that end. Drop `justify-content` from
    `.commentbox .buttons` and both slide to the left of the field."""
    with opened(repo_page, tab="diff") as page:
        page.locator(".dline .addnote").first.click(force=True)
        page.wait_for_selector(".commentbox textarea")
        seen = page.evaluate("""() => {
          const box = document.querySelector('.commentbox');
          const area = box.querySelector('textarea').getBoundingClientRect();
          const all = [...box.querySelectorAll('.buttons button')];
          const last = all[all.length - 1].getBoundingClientRect();
          return {
            names: all.map((one) => one.textContent),
            under: last.top >= area.bottom,
            gap: area.right - last.right,
          };
        }""")
        assert seen["names"] == ["cancel", "save"], seen
        assert seen["under"], seen
        assert abs(seen["gap"]) < 4, seen


def test_a_second_window_takes_up_what_the_first_one_kept(page_at):
    """A draft lives in this browser, and two windows on one session each
    held it in memory with nothing to tell one about the other. A review
    sent from one came back on the other's next keystroke, which wrote its
    stale copy -- sent comments and all -- over the storage the first had
    just cleared."""
    daemon, path = page_at
    with opened(path) as first:
        second = first.context.new_page()
        second.goto(path, wait_until="domcontentloaded")
        second.wait_for_selector(".row")
        second.wait_for_function("state.chosen === 's1'")
        first.evaluate("""() => {
          state.review.comments.push(
            { anchor: 'code.py\\n1', note: "first window's note", quote: 'x' });
          keepReview();
        }""")
        second.wait_for_function("state.review.comments.length === 1")
        first.evaluate("() => { state.review = blankReview(); keepReview(); }")
        second.wait_for_function("state.review.comments.length === 0")
        # And its next keystroke writes nothing that was sent.
        second.evaluate("() => { state.review.overall = 'x'; keepReview(); }")
        # Storage reaches another window a moment later, not at once.
        first.wait_for_function(
            "localStorage.getItem(REVIEW_KEY + 's1') !== null")
        kept = first.evaluate(
            "JSON.parse(localStorage.getItem(REVIEW_KEY + 's1'))")
        assert kept["comments"] == [], kept


def test_a_scroll_not_yet_reported_survives_the_file_being_read_again(long_page):
    """The browser reports a scroll a frame later, and the Files tab polls.
    A poll that brings the file again rebuilds the pane and puts back the
    place the last scroll event wrote down -- so a scroll whose event had not
    fired yet was undone, and the reader was sent back to where they had
    been. CI caught it as `..._survives_the_file_being_read_again` timing out
    on a loaded runner. This makes the order happen on purpose: the scroll
    and the rebuild in one task, where no scroll event can come between."""
    with opened(long_page) as page:
        open_file(page, "long.py")
        page.evaluate("""() => {
          const view = document.querySelector('.filescroll');
          view.scrollTop = view.scrollHeight;
          state.files.mtime += 1;
          draw();
        }""")
        page.wait_for_function(
            "(n) => [...document.querySelectorAll('.filebody .code .dline .ln')]"
            ".some((e) => e.textContent.trim() === String(n))",
            arg=conftest.LONG_LINES)


def test_another_sessions_scroller_is_not_read_as_this_ones_place(long_page,
                                                                   served, ws):
    """The rebuild reads the scroller before it empties the pane, and the
    pane still holds the last session's scroller the moment another is
    chosen. Two sessions on the same file: read without asking whose it
    is, the first one's place became the second one's."""
    repo, _ = long_page
    daemon, _ = served
    ws.append_event(conftest.event("SessionStart", sid="s2", cwd=str(repo),
                                   ts=time.time()))
    daemon.store.refresh()
    with opened(long_page) as page:
        page.wait_for_function("state.sessions.length === 2")
        page.evaluate("choose('s2')")
        open_file(page, "long.py")          # s2 reads it from the top
        page.wait_for_selector('.filescroll[data-drawn="s2"] .code .dline')
        page.evaluate("choose('s1')")
        open_file(page, "long.py")
        # s1's own scroller, not s2's still standing in the pane: that
        # one's listener ignores a scroll once s1 is chosen, and under
        # load `open_file` found its lines and returned before s1's came.
        page.wait_for_selector('.filescroll[data-drawn="s1"] .code .dline')
        scroll_to(page, 3000)
        page.wait_for_function("state.files.down > 3000 * 20")
        page.evaluate("choose('s2')")
        page.wait_for_function(
            "state.files.read && document.querySelector('.filescroll .code')")
        assert page.evaluate("state.files.down") < 21 * 10
        assert page.evaluate(
            "document.querySelector('.filescroll').scrollTop") < 21 * 10


def test_ctrl_enter_saves_a_comment_and_sends_the_review(repo_page):
    """Ctrl+Enter presses the button of the box it is typed in, in every box
    that keeps or sends something: the comment box had Escape and nothing
    else, so the key the reader used everywhere did nothing there. Cmd+Enter
    is the same key on a Mac."""
    with opened(repo_page, tab="diff") as page:
        page.locator(".dline .addnote").first.click(force=True)
        page.wait_for_selector(".commentbox textarea")
        page.fill(".commentbox textarea", "change this please")
        page.press(".commentbox textarea", "Control+Enter")
        page.wait_for_selector(".comment")
        assert "change this please" in page.locator(".comment").inner_text()
        assert page.locator(".commentbox").count() == 0
        stub_send(page, [{"done": True}])
        page.click("#overall")
        page.keyboard.type("cleanup")
        page.keyboard.press("Meta+Enter")
        page.wait_for_function("state.review.comments.length === 0")
        assert page.evaluate("window.__sent.length") == 1
        assert page.evaluate("window.__sent[0]").startswith("cleanup\n\n")


def test_ctrl_enter_in_the_whole_review_box_empties_it(repo_page):
    """Ctrl+Enter sends with the focus still in the box, and the bar leaves
    a box with the focus alone. So the sent words stayed in it, the bar
    stayed up, and what was typed next went into the state after them: the
    next review started with words already sent."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "change this")
        stub_send(page, [{"done": True}])
        page.click("#overall")
        page.keyboard.type("OVERALL WORD")
        page.keyboard.press("Control+Enter")
        page.wait_for_function("state.review.comments.length === 0")
        assert page.evaluate("window.__sent.length") == 1
        assert page.evaluate("state.review.overall") == ""
        assert page.input_value("#overall") == ""
        assert page.locator("#reviewbar").is_hidden()


def test_a_comment_the_diff_holds_is_never_commented_elsewhere(repo_page):
    """What the diff draws is worked out from the diff, not asked of the
    pane. The pane leaves out more: a comment being edited is a box with no
    anchor on it, a shut file draws no lines, and the find box takes files
    out. Asked of the pane, each of those moved the comment to "commented
    elsewhere" -- and one being edited stood there beside its own box."""
    elsewhere = "document.querySelectorAll('.diffhead.elsewhere').length"
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "on the diff")
        anchor = page.evaluate("state.review.comments[0].anchor")
        path = anchor.split("\n")[0]

        page.click(".diffscroll .comment button:text-is('edit')")
        page.wait_for_selector(".commentbox textarea")
        assert page.evaluate(elsewhere) == 0, "edited"
        page.click(".commentbox button:text-is('cancel')")
        page.wait_for_selector(".diffscroll .comment")

        # Shut by hand, then drawn again as a save does.
        head = f".dfile:has(.path:text-is('{path}')) > .name"
        page.click(head)
        page.evaluate("state.diffs.tag += '+'; draw();")
        page.wait_for_function(
            "document.querySelectorAll('.diffscroll .comment').length === 0")
        assert page.evaluate(elsewhere) == 0, "shut"
        # Its row still goes to it: the file opens under it.
        page.click(".filelist.diff button.said")
        page.wait_for_selector(".diffscroll .comment")
        assert page.evaluate(elsewhere) == 0

        page.fill("#find", "nothing is called this")
        page.wait_for_selector(".diffscroll .empty")
        assert page.evaluate(elsewhere) == 0, "found out"


def file_reads(page):
    """The file route's requests, as the page makes them."""
    asked = []
    page.on("request", lambda request: asked.append(request.url)
            if "/file?" in request.url else None)
    return asked


def test_a_file_no_diff_shows_is_read_once_not_on_every_diff(long_page):
    """Each diff that changed forgot every file read for "commented
    elsewhere", so while an agent worked each poll read them all again and
    drew the whole pane twice. A file the diff does not list cannot have
    changed, so what was read of it is kept."""
    with opened(long_page) as page:
        asked = file_reads(page)
        add_comment(page, "long.py\n12", "about line twelve",
                    quoted="line11 = 11")
        show_tab(page, "diff")
        card = ".diffscroll .dfile:has(.path:text-is('long.py'))"
        page.wait_for_selector(f"{card} .dline")
        assert len(asked) == 1, asked
        for _ in range(3):
            # A diff that changed, as a save by the agent brings one.
            page.evaluate("() => { state.diffs.tag = ''; loadDiff(); }")
            page.wait_for_function("state.diffs.tag !== ''")
            assert page.locator(f"{card} .dline").count() == 4
        assert len(asked) == 1, asked


def test_a_file_that_could_not_be_read_is_asked_for_again(long_page):
    """A read that failed was kept as an answer with no text, so the comment
    stood with its quoted line alone until the reader chose another
    session. Now the next draw asks again."""
    with opened(long_page) as page:
        asked = file_reads(page)
        first = []

        def once(route):
            if not first:
                first.append(route.request.url)
                route.abort()
            else:
                route.continue_()

        page.route("**/file?path=long.py*", once)
        add_comment(page, "long.py\n12", "about line twelve",
                    quoted="line11 = 11")
        show_tab(page, "diff")
        card = ".diffscroll .dfile:has(.path:text-is('long.py'))"
        page.wait_for_selector(f"{card} .comment .quoted")
        page.wait_for_function("!state.reviewFiles.has('long.py')")
        assert page.locator(f"{card} .dline").count() == 0
        # A diff that moved, as a save brings one: its tag moves.
        page.evaluate("() => { state.diffs.tag += '+'; draw(); }")
        page.wait_for_selector(f"{card} .dline")
        assert len(asked) == 2, asked


def test_the_bar_stays_while_the_word_on_the_whole_is_typed_away(repo_page):
    """A review that is only a word on the whole is a review, and emptying
    that word is not leaving it: the bar went with the caret still in it."""
    with opened(repo_page, tab="diff") as page:
        page.evaluate("""() => { state.review.overall = 'abc';
          keepReview(); }""")
        page.wait_for_selector("#reviewbar:not([hidden])")
        page.click("#overall")
        page.keyboard.press("Control+a")
        page.keyboard.press("Backspace")
        assert page.evaluate("state.review.overall") == ""
        assert page.evaluate("$('reviewbar').hidden") is False
        page.keyboard.press("Escape")
        page.evaluate("drawReviewBar()")
        assert page.evaluate("$('reviewbar').hidden") is True


BOX_TEXT = "document.querySelector('.commentbox textarea')?.value ?? null"


def test_a_click_on_the_tab_on_screen_keeps_a_half_written_comment(repo_page):
    """`showTab` cleared `state.writing` for the box on the tab being left.
    A click on the tab already shown, or its key, left nothing: the box
    stayed on screen, the guards said nothing was being written, and the
    next poll or pick rebuilt the diff and took the text with it."""
    with opened(repo_page, tab="diff") as page:
        page.locator(".dline .addnote").first.click(force=True)
        page.wait_for_selector(".commentbox textarea")
        page.fill(".commentbox textarea", "HALF WRITTEN NOTE")
        page.click(".tab[data-tab='diff']")
        page.evaluate("document.activeElement.blur()")
        page.keyboard.press("3")
        assert page.evaluate("state.tab") == "diff"
        # What a poll with a changed diff, or a pick, does next.
        page.evaluate("() => { state.diffs.tag += '+'; draw(); }")
        assert page.evaluate(BOX_TEXT) == "HALF WRITTEN NOTE"
        assert page.evaluate("state.writing") is not None


def test_another_comment_waits_while_a_box_holds_text(repo_page):
    """"+" on another line, and "edit" or "delete" on another comment, each
    rebuild the diff, and the box went with what was typed in it. Picks,
    the column switch and the base picker already wait and say why; these
    three do the same now."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "a saved one")
        page.locator(".dline .addnote").first.click(force=True)
        page.wait_for_selector(".commentbox textarea")
        page.fill(".commentbox textarea", "HALF WRITTEN NOTE")
        writing = page.evaluate("state.writing")
        spy_on_note(page)
        page.locator(".dline .addnote").first.click(force=True)
        assert page.evaluate(BOX_TEXT) == "HALF WRITTEN NOTE", "plus"
        page.click(".diffscroll .comment button:text-is('edit')")
        assert page.evaluate(BOX_TEXT) == "HALF WRITTEN NOTE", "edit"
        page.click(".diffscroll .comment button:text-is('delete')")
        assert page.evaluate(BOX_TEXT) == "HALF WRITTEN NOTE", "delete"
        assert page.evaluate("state.writing") == writing
        assert page.evaluate("state.review.comments.length") == 1
        assert page.evaluate("window.__said") == [
            "Save or cancel the comment first."] * 3


def test_a_comment_in_a_shut_file_is_gone_to_from_anywhere_in_the_pane(
        repo_page):
    """`goToComment` opens a file shut for its size and draws, and
    `drawDiff` then puts the old place back a frame later -- after the
    scroll to the comment. From the top it worked; from 1,500 px down the
    pane went back there, and only a second click went to it."""
    root, _ = repo_page
    root.joinpath("code.py").write_text(
        "".join(f"x{n} = {n}\n" for n in range(700)))
    root.joinpath("README.md").write_text(
        "".join(f"line {n}\n" for n in range(200)))
    in_view = """() => {
      const scroll = document.querySelector('.diffscroll');
      const one = [...scroll.querySelectorAll('.comment')].find(
        (node) => node.dataset.anchor === 'code.py\\n300');
      if (!one) return false;
      const at = one.getBoundingClientRect();
      const on = scroll.getBoundingClientRect();
      return at.top >= on.top && at.bottom <= on.bottom;
    }"""
    with opened(repo_page, tab="diff") as page:
        page.wait_for_selector(".dfile .why:text('hidden')")
        add_comment(page, "code.py\n300", "far down a shut file",
                    quoted="x299 = 299")
        assert page.locator(".diffscroll .comment").count() == 0
        page.evaluate(
            "document.querySelector('.diffscroll').scrollTop = 1500")
        page.wait_for_function(
            "document.querySelector('.diffscroll').scrollTop === 1500")
        page.click(".filelist.diff button.said")
        # Past the frame `drawDiff` puts its place back in.
        page.evaluate("""() => new Promise((done) =>
          requestAnimationFrame(() => requestAnimationFrame(done)))""")
        assert page.evaluate(in_view) is True


def test_a_comment_on_a_file_renamed_since_the_commit_goes_to_the_new_name(
        repo_page):
    """The branch committed `code.py`, and the agent moved it and did not
    commit. A comment on the committed half kept the old name, a file not
    on disk; the message sent that name, and the same line in the other
    half took a second comment. It is the file's name now."""
    root, _ = repo_page
    conftest.git_in(root, "mv", "code.py", "ringbuf.py")
    with opened(repo_page, tab="diff") as page:
        page.wait_for_function(
            "document.querySelectorAll('.diffhead.committed').length === 1")
        assert page.evaluate(CLICK_COMMITTED, "print(2)") == "clicked"
        page.wait_for_selector(".commentbox textarea")
        assert page.evaluate("state.writing") == "ringbuf.py\n2"
        page.fill(".commentbox textarea", "about print two")
        page.click(".commentbox button:text-is('save')")
        page.wait_for_selector(".diffscroll .comment")
        # The diff draws it, so it does not stand again at the foot.
        assert page.locator(".diffhead.elsewhere").count() == 0
        assert "## ringbuf.py:2" in page.evaluate("reviewText()")
        # The whole file too: its comment is about the file as it is.
        page.evaluate("""() => document.querySelector(
          '.diffhead.committed ~ .dfile .onFile .addnote').click()""")
        page.wait_for_function("state.writing === 'ringbuf.py\\n0'")
        page.keyboard.press("Escape")
        page.wait_for_selector(".commentbox", state="detached")
        # Its row goes to it with the old name's file shut: the file
        # is found by the name on disk.
        page.click(".diffhead.committed ~ .dfile > .name")
        page.evaluate("state.diffs.tag += '+'; draw();")
        page.wait_for_function(
            "document.querySelectorAll('.diffscroll .comment').length === 0")
        page.click(".filelist.diff button.said")
        page.wait_for_selector(".diffscroll .comment")


def test_a_comment_the_diff_shows_is_not_drawn_again_under_elsewhere(long_page):
    """A comment elsewhere stands with the lines round it, and those lines
    were drawn with every comment on them -- also one the diff above
    already shows. It stood twice, and "edit" on the lower copy opened the
    box on the upper one."""
    root, _ = long_page
    text = root.joinpath("long.py").read_text().split("\n")
    text[19] = "changed = 19"              # line 20, so the hunk starts at 17
    root.joinpath("long.py").write_text("\n".join(text))
    card = ".offdiff .dfile:has(.path:text-is('long.py'))"
    with opened(long_page) as page:
        show_tab(page, "diff")
        page.wait_for_selector(".dline")
        add_comment(page, "long.py\n16", "off the diff", quoted="line15 = 15")
        add_comment(page, "long.py\n17", "on the diff", quoted="line16 = 16")
        page.wait_for_selector(f"{card} .dline")
        # The slice round line 16 reaches line 17.
        assert "line16 = 16" in page.locator(f"{card} .dline").all_inner_texts()[-1]
        drawn = page.evaluate("""() => [...document.querySelectorAll(
          '.diffscroll .comment')].map((one) => one.dataset.anchor)""")
        assert sorted(drawn) == ["long.py\n16", "long.py\n17"], drawn
        assert page.locator(f"{card} .addnote").count() == 2, (
            "lines 14 and 15 are offered one; 17 is on the diff")


def test_a_file_elsewhere_that_was_said_to_be_missing_is_asked_for_again(
        long_page):
    """A timed-out `is_listed` answers `missing` with a 404, and that was
    kept as the file's lines: the comment stood with its quoted line alone,
    and nothing asked again until another session was chosen."""
    with opened(long_page) as page:
        asked = file_reads(page)
        first = []

        def once(route):
            if not first:
                first.append(route.request.url)
                route.fulfill(status=404, content_type="application/json",
                              body='{"missing": "that file is not in '
                                   'this worktree"}')
            else:
                route.continue_()

        page.route("**/file?path=long.py*", once)
        add_comment(page, "long.py\n12", "about line twelve",
                    quoted="line11 = 11")
        show_tab(page, "diff")
        card = ".diffscroll .dfile:has(.path:text-is('long.py'))"
        page.wait_for_selector(f"{card} .comment .quoted")
        page.wait_for_function("!state.reviewFiles.get('long.py')?.asking")
        assert not page.evaluate("!!state.reviewFiles.get('long.py')")
        # A diff that moved, as a save brings one: its tag moves.
        page.evaluate("() => { state.diffs.tag += '+'; draw(); }")
        page.wait_for_selector(f"{card} .dline")
        assert len(asked) == 2, asked


def test_a_comment_saved_while_the_review_is_on_its_way_is_kept(repo_page):
    """`tmux send-keys` takes a moment, and the review that stood when it
    came back was cleared -- with a comment saved in that moment, which
    was never sent."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "sent with the review")
        stub_send(page, [{"done": True}], delay=600)
        page.click("#sendreview")
        page.wait_for_function("window.__sent.length === 1")
        add_comment(page, "README.md\n1", "written while it went",
                    quoted="# The readme")
        page.wait_for_function("!sending.has(state.chosen)")
        page.wait_for_function(
            "!state.review.comments.some((one) => one.note"
            " === 'sent with the review')")
        assert [one["note"] for one in page.evaluate(
            "state.review.comments")] == ["written while it went"]
        assert "written while it went" not in page.evaluate("window.__sent[0]")


def test_send_waits_while_a_box_holds_text(repo_page):
    """Send cleared the review and closed the box, and a note typed into a
    box and never saved went with it, sent nowhere and said nowhere."""
    with opened(repo_page, tab="diff") as page:
        comment_on_first_line(page, "a saved one")
        stub_send(page, [{"done": True}])
        page.locator(".dline .addnote").first.click(force=True)
        page.wait_for_selector(".commentbox textarea")
        page.fill(".commentbox textarea", "HALF WRITTEN NOTE")
        spy_on_note(page)
        page.click("#sendreview")
        page.wait_for_timeout(300)     # proving that nothing is sent
        assert page.evaluate("window.__sent.length") == 0
        assert page.evaluate(BOX_TEXT) == "HALF WRITTEN NOTE"
        assert page.evaluate("state.review.comments.length") == 1
        assert page.evaluate("window.__said") == [
            "Save or cancel the comment first."]


def test_another_window_does_not_rebuild_a_box_that_is_open(repo_page):
    """A change from another window drew the tab again when the focus was
    not in a field. A box that was open with the focus elsewhere was built
    again from the stored note, and what was typed in it was lost."""
    with opened(repo_page, tab="diff") as first:
        second = first.context.new_page()
        second.goto(repo_page[1], wait_until="domcontentloaded")
        second.wait_for_selector(".row")
        second.wait_for_function("state.chosen === 's1'")
        first.locator(".dline .addnote").first.click(force=True)
        first.wait_for_selector(".commentbox textarea")
        first.fill(".commentbox textarea", "HALF WRITTEN NOTE")
        first.evaluate("document.activeElement.blur()")
        second.evaluate("""() => {
          state.review.comments.push({ anchor: 'README.md\\n1',
            note: "the second window's note", quoted: '# The readme' });
          keepReview();
        }""")
        first.wait_for_function("state.review.comments.length === 1")
        assert first.evaluate(BOX_TEXT) == "HALF WRITTEN NOTE"
        # Closed, the tab takes up what the other window kept.
        first.click(".commentbox button:text-is('cancel')")
        first.wait_for_function("""() => [...document.querySelectorAll(
          '.diffscroll .comment')].some(
            (one) => one.dataset.anchor === 'README.md\\n1')""")
