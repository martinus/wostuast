"""The Transcript tab: what an agent said, and what it may not do to this page.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations

import json
import time

import pytest

import conftest
from browser import (
    skip_without_browser,
    sync_playwright,
    open_page,
    show_tab,
    wait_for_map,
    wait_for_watching,
    daemon_transcript,
)

pytestmark = skip_without_browser

def test_the_page_draws_the_session(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            wait_for_map(page)
            assert page.locator(".row").count() == 1
            # The worktree leads the row; what Claude Code called the session
            # goes under it, because the name is often long and often vague
            # and it used to push the worktree off the end.
            place = page.locator(".row .name").inner_text()
            assert place and "A session" not in place
            assert "A session" in page.locator(".row .called").inner_text()
            assert page.title() == "wostuast"
            assert page.locator(".turn").count() >= 2
            # The model is a fact about the session, so it is in the tab that
            # holds those — not in a bar standing over every tab.
            show_tab(page, "session")
            page.wait_for_selector(".sessionbody dl")
            assert "Opus 5" in page.locator(".sessionbody").inner_text()
        finally:
            browser.close()


def test_hostile_markdown_cannot_run(page_at):
    """An agent that reads a nasty file must not be able to act on this page.
    The page shares an origin with the tmux verbs, so this is the whole game."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            # Without this the transcript may not have arrived, and a page
            # that drew nothing passes every assertion below vacuously.
            wait_for_map(page)
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


def test_only_a_block_that_has_just_arrived_slides_in(page_at):
    """A transcript is rebuilt whenever anything about it changes. Animating
    every block on every rebuild would make the tab shiver each time an agent
    ran a tool, so the slide is for a block nobody has seen before."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            assert page.locator(".fresh").count() == 0, "the history slid in too"
            blocks, run, _ = daemon.read_transcript("s1")
            one = dict(blocks[-1].__dict__)
            one.update(seq=len(blocks), kind="text", text="and one more thing")
            daemon.hub.send("transcript",
                            {"id": "s1", "run": run, "blocks": [one]},
                            session_id="s1")
            # In one question, so that a redraw cannot land between asking
            # whether it is there and asking how many there are.
            page.wait_for_function(
                "document.querySelectorAll('.fresh').length === 1")
            moving = ("() => getComputedStyle(document.querySelector('.turn'))"
                      ".animationName")
            assert page.evaluate(moving) == "none", "the whole history animates"
            # Drawing it again is not arriving again.
            page.evaluate("draw()")
            assert page.locator(".fresh").count() == 0
        finally:
            browser.close()


def test_expanding_a_tool_result_leaves_the_rest_alone(page_at):
    """It used to redraw the whole tab, which re-parsed every Markdown block
    and threw the reader to the bottom of the transcript."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            wait_for_map(page)
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


def test_the_session_the_page_picks_for_you_is_watched(page_at, ws):
    """The page auto-selects the first session. It used to set it without
    subscribing, so the stream stayed on watch="" and the transcript of the
    one session actually on screen never updated."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            # `open_page` returns on the first draw, which is the tab's frame:
            # the transcript is still in flight. Counting straight away read
            # nought turns on a loaded CI runner, and then the push delivered
            # the whole transcript at once -- `assert 3 == (0 + 1)`.
            wait_for_map(page)
            wait_for_watching(daemon)
            before = page.locator(".turn").count()
            assert page.locator(".row.chosen").count() == 1

            with open(daemon_transcript(daemon), "a") as handle:
                handle.write(json.dumps({
                    "type": "assistant", "timestamp": "2026-09-18T14:09:00.000Z",
                    "message": {"role": "assistant", "content": [
                        {"type": "text", "text": "A brand new line."}]}}) + "\n")
            daemon.tick()
            # For what the push carries, not for a length of time: a fixed
            # wait on a loaded runner is a wait that runs out.
            page.wait_for_function(
                "n => document.querySelectorAll('.turn').length === n",
                arg=before + 1)
            assert "A brand new line." in page.locator(".content").inner_text()
        finally:
            browser.close()


def test_the_same_blocks_arriving_twice_are_not_shown_twice(page_at):
    """A reconnected stream re-sends the transcript from the beginning, and the
    first fetch and the first push can carry the same block. Each block knows
    its place, so it lands in the same slot either way."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            wait_for_map(page)
            before = page.locator(".turn").count()
            assert before > 1
            blocks, run, _ = daemon.read_transcript("s1")
            daemon.hub.send("transcript",
                            {"id": "s1", "run": run,
                             "blocks": [dict(b.__dict__) for b in blocks]},
                            session_id="s1")
            page.wait_for_timeout(800)
            assert page.locator(".turn").count() == before
        finally:
            browser.close()


def test_a_rewritten_transcript_replaces_the_page_rather_than_doubling_it(page_at):
    """A `/clear`, a resume, any atomic rewrite: the file at the same name is
    a different file, and `seq` counts from nought again. Patched by index,
    the new blocks landed over the head of the old ones and the old tail hung
    on below — the reader saw a transcript that never happened.

    The push carries the reading it belongs to, so the page replaces what it
    holds instead of merging into it.
    """
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            wait_for_map(page)
            assert page.locator(".turn").count() > 1
            held = daemon_transcript(daemon)

            spare = held.parent / "rewritten.jsonl"
            spare.write_text(json.dumps({
                "type": "assistant", "timestamp": "2026-09-18T15:00:00.000Z",
                "message": {"role": "assistant", "content": [
                    {"type": "text", "text": "The only line now."}]}}) + "\n")
            spare.replace(held)          # a new inode, as a rewrite makes

            daemon.tick()
            page.wait_for_function(
                "document.querySelectorAll('.turn').length === 1")
            shown = page.locator(".content").inner_text()
            assert "The only line now." in shown
            assert "Do the thing." not in shown, "the old reading is still here"
        finally:
            browser.close()


def test_typing_narrows_the_list_and_leaves_the_transcript_whole(page_at):
    """The find box belongs to the list beside the transcript now. Taking
    turns out of the transcript took the conversation around a hit away with
    them, which is the thing you were reading it for. The hits are still
    marked where they stand."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            wait_for_map(page)
            everything = page.locator(".turn").count()
            rows = page.locator(".filelist.transcript button").count()

            page.locator("#find").fill("pytest")
            page.wait_for_function(
                "document.querySelectorAll('mark').length > 0")
            assert page.locator(".turn").count() == everything
            assert page.locator(".filelist.transcript button").count() < rows
            assert "pytest" in page.locator("mark").first.inner_text().lower()
            assert " of " in page.locator(".listnote").inner_text()

            page.locator("#find").fill("")
            page.wait_for_function(
                "document.querySelectorAll('mark').length === 0")
            assert page.locator(".turn").count() == everything
            assert page.locator(".filelist.transcript button").count() == rows
        finally:
            browser.close()


def test_a_search_that_matches_nothing_says_so(page_at):
    """In the list, which is what the box narrows. The transcript stays as it
    was: it is not what the question was about."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            wait_for_map(page)
            turns = page.locator(".turn").count()
            page.locator("#find").fill("zzzznotherezzzz")
            page.wait_for_selector(".filelist.transcript .nohits")
            assert "Nothing here matches" in \
                page.locator(".filelist.transcript").inner_text()
            assert page.locator(".filelist.transcript button").count() == 0
            assert page.locator(".turn").count() == turns
        finally:
            browser.close()


def test_searching_never_re_parses_what_an_agent_wrote(page_at):
    """Highlighting walks text nodes. A search that looks like markup must not
    become markup."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            wait_for_map(page)
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
            # The find box moves house when the transcript arrives and
            # `split` claims it, and a box that moves loses the focus on it:
            # the "j" then landed on the page as a key. Waiting for the map is
            # waiting for that move to have happened.
            wait_for_map(page)
            page.locator("#find").focus()
            page.keyboard.type("j")
            page.wait_for_timeout(150)
            assert page.locator("#find").input_value() == "j"
            assert page.evaluate("document.getElementById('help').open") is False
        finally:
            browser.close()


def test_without_marked_the_transcript_is_still_readable(page_at):
    """Markdown is written to be read as plain text, so a fetch that never
    arrives costs the rendering and nothing else. The tab is never blank."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at, with_marked=False)
        try:
            page.wait_for_timeout(700)
            assert page.evaluate("!!window.marked") is False
            said = page.locator(".prose").first.inner_text()
            assert said                       # there is text, not an empty box
            assert page.locator(".prose h1, .prose h2, .prose ul").count() == 0
            assert page.locator(".nohits").count() == 0
        finally:
            browser.close()


def test_marked_is_pinned_too(page_at):
    """Both fetched scripts carry the hash of their bytes. The page is served
    the real marked here, so this checks the pin as the browser does."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.wait_for_timeout(700)
            assert page.evaluate("!!window.marked") is True
            tag = page.locator("script[src*='marked']")
            assert tag.count() == 1
            assert tag.get_attribute("src").startswith("https://")
            assert tag.get_attribute("integrity").startswith("sha384-")
            assert tag.get_attribute("crossorigin") == "anonymous"
        finally:
            browser.close()


def append_blocks(daemon, texts):
    """Write assistant turns onto the session's transcript and push them."""
    with open(daemon_transcript(daemon), "a") as handle:
        for text in texts:
            handle.write(json.dumps({
                "type": "assistant", "timestamp": "2026-09-18T14:09:00.000Z",
                "message": {"role": "assistant",
                            "content": [{"type": "text", "text": text}]}}) + "\n")
    daemon.tick()


def test_a_search_keeps_its_place_while_the_agent_works(page_at):
    """A push used to draw the whole tab again whenever a filter was typed,
    and a draw ends at the top. On a live session that is once a second, so a
    search was unreadable: you scrolled down, the agent said something, and
    you were back at the top. Nothing is filtered out of the transcript any
    more, so a push appends — but the place still has to survive it."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            append_blocks(daemon, [f"pytest run {n}" for n in range(60)])
            page.wait_for_function(
                "document.querySelectorAll('.turn').length > 50")
            page.fill("#find", "pytest")
            page.wait_for_function("document.querySelectorAll('mark').length > 0")

            page.evaluate("document.querySelector('.turnbody').scrollTop = 600")
            was = page.evaluate("document.querySelector('.turnbody').scrollTop")
            assert was > 0, "the transcript is too short to scroll"

            append_blocks(daemon, ["pytest run 60"])
            page.wait_for_function(
                "document.querySelectorAll('.turn').length > 60")
            assert page.evaluate(
                "document.querySelector('.turnbody').scrollTop") == was
        finally:
            browser.close()


def test_expanding_a_tool_result_keeps_the_search_highlighted(page_at):
    """`redrawBlock` rebuilt the node but never marked it again, so the one
    block you clicked stopped being highlighted while every other match kept
    its `<mark>`."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.fill("#find", "pytest")
            page.wait_for_function("document.querySelectorAll('mark').length > 0")
            before = page.locator("mark").count()
            page.click(".tool")
            page.wait_for_selector(".tool-result")
            assert page.locator("mark").count() >= before
        finally:
            browser.close()


def test_a_working_stream_says_nothing_and_a_lost_one_says_so(page_at):
    """The slot read "live" on every page all day. A reader can see the page
    moving, so the word told nobody anything -- and a word that is always
    there is a word nobody reads, so "reconnecting" in the same place went
    unseen too. A working stream is silent; a lost one speaks."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.wait_for_function("state.live === 'live'")
            assert page.locator("#live").inner_text() == ""
            # What the page does when the stream drops, read in the same
            # evaluate that causes it: a push cannot land in between.
            said = page.evaluate("""() => { state.stream.onerror();
                return document.getElementById('live').textContent; }""")
            assert said == "reconnecting"
            # And with words in the find box too: both painters skipped the
            # slot then, so a drop said nothing and a reconnect left
            # "reconnecting" standing over a working page.
            said = page.evaluate("""() => { state.find = 'x';
                document.getElementById('live').textContent = '';
                state.stream.onerror();
                return document.getElementById('live').textContent; }""")
            assert said == "reconnecting"
        finally:
            browser.close()


def test_our_own_word_in_the_live_slot_gives_the_slot_back(page_at):
    """The slot says whether the stream is live. A passing word borrows it
    for four seconds and has to give it back — it used to assign itself
    back, so the word never returned."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.wait_for_function(
                "state.live === 'live' && document.getElementById('live').textContent === ''")
            # Written and read back inside one `evaluate`, because there is
            # no gap inside one: the stream repaints this slot on every push,
            # and it really is allowed to take the word back — `paintLive` is
            # one painter and the stream is one of the three things that want
            # it. A second question from Python can land after that repaint,
            # so asking twice tests the machine's load, not the page.
            said = page.evaluate(
                """() => { note('review sent');
                           return document.getElementById('live').textContent; }""")
            assert said == "review sent"
            page.wait_for_function(
                "state.live === 'live' && document.getElementById('live').textContent === ''",
                timeout=15000)
        finally:
            browser.close()


def test_a_failure_in_the_live_slot_stays_there(page_at):
    """It is not news that goes stale: it is a thing you asked for and did
    not get. Fading it left a strip reading "live" over a page where the
    thing you tried had not happened, and nothing said why."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.wait_for_function(
                "state.live === 'live' && document.getElementById('live').textContent === ''")
            page.evaluate("said({error: 'no pane for this session'})")
            assert "no pane" in page.locator("#live").inner_text()
            page.wait_for_timeout(4500)     # proving it did NOT go away
            assert "no pane" in page.locator("#live").inner_text()
            # The next thing that works gives the slot back.
            page.evaluate("said({done: true})")
            assert page.locator("#live").inner_text() == ""
        finally:
            browser.close()


def test_a_push_from_the_daemon_does_not_wipe_a_failure(ws, page_at):
    """The stream writes "live" into this slot on every push, which is about
    once a second while an agent works. A failure painted straight into it
    was gone before the reader looked up — the thing they most needed to
    read was the thing that lasted least. CI caught this one."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function(
                "state.live === 'live' && document.getElementById('live').textContent === ''")
            page.evaluate("said({error: 'no pane for this session'})")
            assert "no pane" in page.locator("#live").inner_text()

            # A push, which is what the daemon does whenever anything moves.
            daemon.hub.send("sessions", daemon.sessions_payload())
            page.wait_for_timeout(500)
            assert "no pane" in page.locator("#live").inner_text()
            # And the stream's own word is not lost either: it is underneath.
            page.evaluate("said({done: true})")
            assert page.locator("#live").inner_text() == ""
        finally:
            browser.close()


# --- copying a reply, linking to one, and saying which day it was ------------

def test_a_reply_older_than_today_says_which_day_it_was(page_at):
    """A transcript read the next morning is a column of bare times. The day
    the daemon thinks it is decides, not this browser's — `state.skew` is the
    difference, and every other age on the page is measured against it.

    Both halves are driven from the block's own timestamp, so the test says
    the same thing whatever day it is run on. Make `dayOf` return the date
    always and the first count stops being nought."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            wait_for_map(page)
            seen = page.evaluate("""() => {
              const was = state.skew;
              const ts = state.turns.blocks.find((one) => one && one.ts).ts;
              const at = (when) => {
                state.skew = when - Date.now() / 1000;
                drawTranscript($('content'));
                return [...document.querySelectorAll('.who .day')]
                         .map((one) => one.textContent);
              };
              const sameDay = at(ts + 600);
              const threeDaysOn = at(ts + 3 * 86400);
              state.skew = was;
              return {sameDay, threeDaysOn};
            }""")
            assert seen["sameDay"] == []
            assert seen["threeDaysOn"], seen
            # The block's own day, not today's.
            assert all(one == "18 Sep" for one in seen["threeDaysOn"]), seen
        finally:
            browser.close()


def test_a_reply_can_be_copied_as_the_markdown_it_was_written_in(page_at):
    """The page shows a reply drawn. What goes into a bug report or the next
    prompt is its source, which is why this copies `block.text` and not what
    is on screen. Copy the node's text instead and the fences go missing."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        browser.grant_permissions(["clipboard-read", "clipboard-write"])
        try:
            # The button is on hover, like the `+` on a diff line.
            page.locator(".turn.mine .copy").first.click(force=True)
            page.wait_for_selector(".turn.mine .copy:text-is('copied')")
            assert page.evaluate(
                "navigator.clipboard.readText()") == "Do the thing."

            # And the agent's answer, which is Markdown with a fence in it.
            page.locator(".turn:not(.mine) .copy").first.click(force=True)
            page.wait_for_function(
                """() => navigator.clipboard.readText()
                           .then((text) => text.includes('```python'))""")
            got = page.evaluate("navigator.clipboard.readText()")
            assert "<img src=x" in got, got      # the source, not the scrub
            assert "if len(hits) > 1:" in got, got
        finally:
            browser.close()


def test_a_reply_is_a_link_you_can_open_in_another_tab(page_at):
    """The name of every turn is an anchor, so the browser's own "open in a
    new tab" works on it and a click leaves the link in the address bar.
    Opening one lands on that block and says which it is.

    Take `landOnBlock` out of `drawTranscript` and the page opens at the foot
    of the transcript with nothing marked."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            wait_for_map(page)
            links = page.eval_on_selector_all(
                ".turn .self", "els => els.map((one) => one.getAttribute('href'))")
            assert links and all(one.startswith("#s1/") for one in links), links
            # The second turn: what Claude said.
            wanted = links[1]
        finally:
            browser.close()

    with sync_playwright() as play:
        browser, page = open_page(play, page_at[1] + wanted)
        try:
            # Landing is what clears the ask, so this is the durable half of
            # it. The mark is on a two-and-a-half second timer and a busy
            # machine can outlive one between two calls, so it is asked for
            # in a single round trip below.
            page.wait_for_function("state.turns.goTo === null")
            assert page.evaluate(
                "state.turns.blocks[Number(location.hash.split('/').pop())].kind"
            ) == "text"

            marked = page.evaluate("""(wanted) => {
              state.turns.goTo = Number(wanted.split('/').pop());
              drawTranscript($('content'));
              const one = document.querySelector('.turn.linked');
              return one && one.querySelector('.self').getAttribute('href');
            }""", wanted)
            assert marked == wanted
        finally:
            browser.close()


def test_a_link_to_a_block_this_session_no_longer_has_moves_nothing(page_at):
    """`seq` is a place in one reading of a transcript, not an identity: a
    session resumed from another directory counts from nought again. So a
    link is a pointer, not a promise, and the whole of its failure is that
    nothing moves."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at[1] + "#s1/900")
        try:
            blew_up = []
            page.on("pageerror", lambda error: blew_up.append(str(error)))
            page.wait_for_selector(".turn")
            # There is no block 900, so the draw must fall through to its
            # usual landing rather than reaching into an empty slot.
            page.evaluate("drawTranscript($('content'))")
            page.wait_for_timeout(300)      # proving something did not happen
            assert not blew_up, blew_up
            assert page.locator(".turn.linked").count() == 0
            assert page.evaluate("state.turns.goTo") == 900
        finally:
            browser.close()


# --- the map of the conversation ---------------------------------------------

def test_the_transcript_has_a_list_of_rounds_beside_it(page_at):
    """What you typed is a folder, what came back to it is what is in it.
    Tool calls are left out: there are hundreds of them in a real session —
    233 in one that was measured — and they are already in the transcript.
    Put `kind === "tool"` into `rounds` and the count goes up."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            wait_for_map(page, 2)
            seen = page.eval_on_selector_all(
                ".filelist.transcript button",
                """els => els.map((one) => [one.className.includes('dir'),
                                            one.querySelector('.name').textContent])""")
            assert seen == [[True, "Do the thing."],
                            [False, "Read from a README:"]], seen
            # The tool call in this fixture is in the transcript and not here.
            assert page.locator(".turn.toolrow").count() == 1
        finally:
            browser.close()


def append_rounds(daemon, many):
    """Whole rounds — a prompt and a long reply to it — so the transcript is
    taller than the pane and an early round is really off screen."""
    with open(daemon_transcript(daemon), "a") as handle:
        for n in range(many):
            handle.write(json.dumps({
                "type": "user", "timestamp": "2026-09-18T14:10:00.000Z",
                "message": {"role": "user", "content": f"round {n} please"}})
                + "\n")
            handle.write(json.dumps({
                "type": "assistant", "timestamp": "2026-09-18T14:11:00.000Z",
                "message": {"role": "assistant", "content": [
                    {"type": "text",
                     "text": f"answer {n}\n\n" + "filler line\n" * 12}]}})
                + "\n")
    daemon.tick()


def test_a_row_goes_to_its_place_in_the_transcript(page_at):
    """Clicking a row is the whole point of the list. It marks where you went
    as well, or clicking a row already on screen answers with nothing —
    which is how the same thing read as broken on the Files tab."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            # The first fetch, then the stream, then the rounds. Without the
            # first wait the fetch and the push interleave, and the page can
            # end up having drawn the transcript it asked for over the one it
            # was sent.
            wait_for_map(page)
            wait_for_watching(daemon)
            append_rounds(daemon, 12)
            page.wait_for_function(
                "document.querySelectorAll('.filelist.transcript button').length > 20")
            page.wait_for_function(
                """() => { const one = document.querySelector('.turnbody');
                           return one.scrollHeight > one.clientHeight + 400; }""")
            # The transcript opens at its foot, so an early round is off screen.
            page.click(".filelist.transcript button >> nth=0")
            page.wait_for_selector(".turn.linked")
            seen = page.evaluate("""() => {
              const pane = document.querySelector('.turnbody');
              const one = pane.querySelector('.turn.linked');
              const box = one.getBoundingClientRect();
              const on = pane.getBoundingClientRect();
              return {top: box.top - on.top, height: on.height,
                      at: state.turns.at,
                      marked: document.querySelectorAll(
                        '.filelist.transcript button.chosen').length};
            }""")
            assert 0 <= seen["top"] < seen["height"], seen
            assert seen["at"] == 0, seen
            assert seen["marked"] == 1, seen
        finally:
            browser.close()


def test_a_reply_row_says_enough_of_it_to_know_what_it_was(page_at):
    """The first line with anything on it, with Markdown's own marks taken
    off the front — a reply that opens with a heading would otherwise spend
    its first characters saying so."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            wait_for_map(page)          # the map has to exist to be measured
            seen = page.evaluate("""() => ({
              said: [
                glimpse("## A heading\\n\\nand then some"),
                glimpse("\\n\\n- a bullet first"),
                glimpse("**bold to start** and on"),
                glimpse("`code` first"),
                glimpse("x".repeat(80)),
                glimpse(""),
                glimpse("y".repeat(400)),
              ],
              cap: GLIMPSE,
              clips: getComputedStyle(
                document.querySelector('.filelist.transcript .name')).textOverflow,
            })""")
            said = seen["said"]
            assert said[:4] == ["A heading", "a bullet first",
                                "bold to start and on", "code first"]
            # A line the column has room for is handed over whole: the column
            # is what clips, with an ellipsis, at whatever width it has been
            # dragged to. 44 characters was narrower than the column at its
            # default width, so every row ended in a "…" the column had room
            # for and the number did not.
            assert said[4] == "x" * 80
            assert said[5] == ""
            assert seen["clips"] == "ellipsis", seen["clips"]
            # And a reply of several kilobytes is still bounded, because every
            # round puts one of these in the DOM. Measured: at the widest the
            # column can be dragged the name box is 639 px, which holds 49 of
            # the widest glyphs and 176 of the narrowest — so the cap has to
            # clear 176 or it becomes the clip again.
            assert seen["cap"] > 176, seen["cap"]
            assert len(said[6]) == seen["cap"] and said[6].endswith("…")
        finally:
            browser.close()


# --- the reader's own autolinks ----------------------------------------------

def test_a_ticket_id_becomes_a_link(ws, page_at, tmp_path):
    """The whole of #92: a pattern and a url in `links.json`, and a ticket id
    in what the agent wrote becomes a link to it."""
    ws.links_path().parent.mkdir(parents=True, exist_ok=True)
    ws.links_path().write_text(json.dumps([
        {"match": r"(OA|QSP)-(\d+)", "url": "https://tickets/browse/$1-$2"},
    ]), encoding="utf-8")
    daemon, path = page_at
    append_blocks(daemon, [
        "Fixed OA-73219 and QSP-52811.\n\n"
        "Not in code: `git log OA-11111` or\n\n```\nOA-22222\n```\n",
    ])
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function("state.links.length === 1")
            page.wait_for_selector(".prose a.ticket")
            seen = page.eval_on_selector_all(
                ".prose a.ticket",
                "els => els.map((one) => [one.textContent, one.href, one.target])")
            assert seen == [
                ["OA-73219", "https://tickets/browse/OA-73219", "_blank"],
                ["QSP-52811", "https://tickets/browse/QSP-52811", "_blank"],
            ], seen
            # A ticket id inside code is part of the command, not a link.
            assert page.locator("code a.ticket, pre a.ticket").count() == 0
            # The page holds this fixture's own fences too, so it is asked
            # for all of them rather than for the first.
            code = page.eval_on_selector_all(
                ".prose code, .prose pre", "els => els.map((o) => o.textContent)")
            assert any("OA-11111" in one for one in code), code
            assert any("OA-22222" in one for one in code), code
        finally:
            browser.close()


def test_a_ticket_id_in_your_own_prompt_is_a_link_too(ws, page_at):
    """A prompt is plain text, not Markdown, so it goes through the same
    walker rather than through `markdown`."""
    ws.links_path().parent.mkdir(parents=True, exist_ok=True)
    ws.links_path().write_text(json.dumps([
        {"match": r"OA-(\d+)", "url": "https://tickets/browse/OA-$1"},
    ]), encoding="utf-8")
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function("state.links.length === 1")
            made = page.evaluate("""() => {
              const box = document.createElement('div');
              box.textContent = 'please look at OA-4242 today';
              linkTickets(box);
              const one = box.querySelector('a.ticket');
              return one && [one.textContent, one.getAttribute('href'),
                             box.textContent];
            }""")
            assert made == ["OA-4242", "https://tickets/browse/OA-4242",
                            "please look at OA-4242 today"]
        finally:
            browser.close()


def test_a_links_file_the_daemon_cannot_use_says_so_on_the_session_tab(ws,
                                                                       page_at):
    """A file you wrote and got wrong must never look like a file you never
    wrote. Without this the page is identical either way: no links, no clue,
    and `doctor` is something you had no reason to run."""
    ws.links_path().parent.mkdir(parents=True, exist_ok=True)
    ws.links_path().write_text("not json at all", encoding="utf-8")
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            show_tab(page, "session")
            page.wait_for_selector(".sessionbody .trouble")
            said = page.inner_text(".sessionbody .trouble")
            assert "links.json" in said
            assert "not valid JSON" in said
        finally:
            browser.close()


def test_a_links_file_that_works_says_nothing(ws, page_at):
    """A note on every Session tab would be noise, and noise is not read."""
    ws.links_path().parent.mkdir(parents=True, exist_ok=True)
    ws.links_path().write_text(json.dumps([
        {"match": r"OA-(\d+)", "url": "https://tickets/$1"},
    ]), encoding="utf-8")
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function("state.links.length === 1")
            show_tab(page, "session")
            assert page.locator(".sessionbody .trouble").count() == 0
        finally:
            browser.close()


def test_a_pattern_this_browser_cannot_use_says_so_too(ws, page_at):
    """Python took the pattern and JavaScript will not -- the two dialects
    are close and not the same, so this one is only findable here, and it is
    the same silence if the page keeps it to itself."""
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            show_tab(page, "session")
            page.wait_for_selector(".sessionbody")
            # The answer is taken and the page asked in one go, with no
            # poll in between: the note has to arrive because `loadLinks`
            # redrew for it, not because something else happened to.
            said = page.evaluate("""async () => {
              // What the daemon serves, with a pattern Python compiles and
              // this browser does not: `(?P<x>)` is Python's alone.
              window.fetch = async () => ({json: async () => ({
                links: [{match: '(?P<id>OA-1)', url: 'https://tickets/'}],
                trouble: []})});
              await loadLinks();
              return [state.linkTrouble,
                      document.querySelector('.sessionbody .trouble')
                        ? document.querySelector('.sessionbody .trouble').innerText
                        : null];
            }""")
            trouble, drawn = said
            assert len(trouble) == 1 and "(?P<id>OA-1)" in trouble[0], trouble
            assert drawn and "(?P<id>OA-1)" in drawn, drawn
        finally:
            browser.close()


def test_a_pattern_can_never_put_an_element_on_the_page(ws, page_at):
    """It walks text nodes and builds one anchor at a time, with an href this
    side checks again — so a url template that is not http(s), or one that
    tries to be markup, produces text and no link."""
    ws.links_path().parent.mkdir(parents=True, exist_ok=True)
    ws.links_path().write_text(json.dumps([
        {"match": r"OA-(\d+)", "url": "https://tickets/$1"},
    ]), encoding="utf-8")
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function("state.links.length === 1")
            seen = page.evaluate("""() => {
              // A template the daemon would have refused, forced in here.
              state.links = [{re: /OA-(\\d+)/g, url: 'javascript:alert($1)'},
                             {re: /QSP-(\\d+)/g,
                              url: '"><img src=x onerror=alert(1)>$1'}];
              const box = document.createElement('div');
              box.textContent = 'OA-1 and QSP-2';
              linkTickets(box);
              return {links: box.querySelectorAll('a').length,
                      images: box.querySelectorAll('img').length,
                      text: box.textContent};
            }""")
            assert seen == {"links": 0, "images": 0, "text": "OA-1 and QSP-2"}
            assert page.evaluate("window.PWNED ?? null") is None
        finally:
            browser.close()


def test_a_block_of_many_ticket_ids_is_linked_all_the_way_down(ws, page_at):
    """A file of release notes went past the old cap of forty, and the links
    simply stopped halfway with nothing saying why."""
    ws.links_path().parent.mkdir(parents=True, exist_ok=True)
    ws.links_path().write_text(json.dumps([
        {"match": r"T-(\d+)", "url": "https://tickets/$1"},
    ]), encoding="utf-8")
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function("state.links.length === 1")
            made = page.evaluate("""() => {
              const box = document.createElement('div');
              box.textContent = Array.from({length: 400},
                                           (x, n) => 'T-' + n).join(' ');
              linkTickets(box);
              return box.querySelectorAll('a.ticket').length;
            }""")
            assert made == 400, made
        finally:
            browser.close()


def test_there_is_still_a_cap_on_the_links_in_one_block(ws, page_at):
    """A pattern that matches everything would otherwise build a link per
    word, and every one of them is a DOM node on a page that redraws. The
    number is the page's own and is sent nowhere."""
    ws.links_path().parent.mkdir(parents=True, exist_ok=True)
    ws.links_path().write_text(json.dumps([
        {"match": r"T-(\d+)", "url": "https://tickets/$1"},
    ]), encoding="utf-8")
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function("state.links.length === 1")
            seen = page.evaluate("""() => {
              const box = document.createElement('div');
              box.textContent = Array.from({length: 5000},
                                           (x, n) => 'T-' + n).join(' ');
              const at = performance.now();
              linkTickets(box);
              return [box.querySelectorAll('a.ticket').length,
                      performance.now() - at];
            }""")
            made, took = seen
            assert made == 500, made
            # Ten times the old cap, on the worst text there is: every word a
            # match. Measured so that raising the number again is a number
            # somebody has looked at, not a guess.
            assert took < 500, f"{took:.0f} ms to build {made} links"
        finally:
            browser.close()


def test_a_row_of_the_map_is_one_line(page_at):
    """`.filelist button` is a block, because a Diff tab row carries a second
    line of counts under its name. A row that is one line has to say so — the
    icon sat above the text otherwise, which is what it did when this list
    first shipped. Take the `display: flex` off and the two stack again."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            wait_for_map(page)
            seen = page.evaluate("""() => [...document.querySelectorAll(
              '.filelist.transcript button')].map((one) => {
                const icon = one.querySelector('.icon').getBoundingClientRect();
                const name = one.querySelector('.name').getBoundingClientRect();
                return {sameLine: Math.abs(icon.top - name.top) < 8,
                        after: name.left > icon.right,
                        tall: one.getBoundingClientRect().height};
              })""")
            assert seen, "the list drew nothing"
            for one in seen:
                assert one["sameLine"] and one["after"], one
                assert one["tall"] < 40, one
        finally:
            browser.close()


def test_a_message_sent_to_a_busy_agent_reads_as_what_you_typed(ws, page_at):
    """Every message this page sends to a working agent comes back wrapped in
    a header, a footer and a `<system-reminder>`, and all three were drawn as
    though the reader had typed them. The map beside the transcript carried
    the header as the name of the round."""
    daemon, path = page_at
    typed = ("also creating a worktree would be slower, so many files.\n"
             "Is there a way to keep the corpus out of it?")
    with open(daemon_transcript(daemon), "a") as handle:
        handle.write(json.dumps({
            "type": "user", "timestamp": "2026-09-18T14:21:00.000Z",
            "message": {"role": "user", "content":
                        "<system-reminder>\n"
                        "The user sent a new message while you were working:\n"
                        + typed + "\n\n"
                        "This is how Claude Code surfaces messages the user"
                        " sends mid-turn \u2014 within the running turn, often"
                        " alongside the next tool result, rather than as a"
                        " separate conversation turn. Address the message above"
                        " as you continue this turn.\n"
                        "</system-reminder>"}}) + "\n")
    daemon.tick()
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function(
                """() => [...document.querySelectorAll('.turn.mine')]
                     .some((one) => one.innerText.includes('the corpus'))""")
            seen = page.evaluate("""() => ({
              mine: [...document.querySelectorAll('.turn.mine')]
                      .map((one) => one.innerText),
              rows: [...document.querySelectorAll('.filelist.transcript button')]
                      .map((one) => one.title),
            })""")
            said = [one for one in seen["mine"] if "corpus" in one][0]
            assert "while you were working" not in said, said
            assert "system-reminder" not in said, said
            assert "mid-turn" not in said, said
            assert "so many files" in said and "keep the corpus" in said
            # The map names the round by what was typed, not by the wrapper.
            assert not [one for one in seen["rows"]
                        if "while you were working" in one], seen["rows"]
        finally:
            browser.close()


def test_a_note_is_not_drawn_as_something_you_typed(ws, page_at, tmp_path):
    """A background task finishing is real news and nobody typed it. It used
    to wear your rail and your tint, and it filled the map beside the
    transcript with rows for things you never said."""
    daemon, path = page_at
    with open(daemon_transcript(daemon), "a") as handle:
        for text in (
            "<task-notification>The sweep is done</task-notification>",
            "<command-name>/reload-plugins</command-name>"
            "<command-message>reload-plugins</command-message>"
            "<command-args></command-args>",
            "<local-command-stdout>(no content)</local-command-stdout>",
        ):
            handle.write(json.dumps({
                "type": "user", "timestamp": "2026-09-18T14:20:00.000Z",
                "message": {"role": "user", "content": text}}) + "\n")
    daemon.tick()
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_selector(".turn.aside")
            seen = page.evaluate("""() => ({
              notes: [...document.querySelectorAll('.turn.aside')]
                       .map((one) => one.innerText.replace(/\\s+/g, ' ').trim()),
              mine: [...document.querySelectorAll('.turn.mine')]
                      .map((one) => one.innerText.replace(/\\s+/g, ' ').trim()),
              rows: [...document.querySelectorAll('.filelist.transcript button')]
                      .map((one) => one.title),
            })""")
            # The harness speaking is a note, not a prompt.
            assert any("The sweep is done" in one for one in seen["notes"]), seen
            assert not any("task-notification" in one for one in seen["notes"]), seen
            assert not any("sweep" in one for one in seen["mine"]), seen
            # The command is one line, and its output is nowhere.
            assert any("/reload-plugins" == one for one in seen["rows"]), seen
            assert not any("no content" in one for one in seen["rows"]), seen
            assert not any("command-message" in one for one in seen["rows"]), seen
            # And a note is not a round and not a reply.
            assert not any("sweep" in one for one in seen["rows"]), seen
        finally:
            browser.close()


# --- the way back to the end -------------------------------------------------

def test_the_way_back_to_the_end_is_offered_only_when_it_would_do_something(page_at):
    """A new block carries you along only while you are near the foot, which
    is right — but once that stopped, nothing said how to start again, and on
    a long transcript the scrollbar is a sliver."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            wait_for_map(page)
            wait_for_watching(daemon)
            append_rounds(daemon, 12)
            page.wait_for_function(
                """() => { const one = document.querySelector('.turnbody');
                           return one.scrollHeight > one.clientHeight + 400; }""")
            # It opens at the foot, so there is nowhere to go.
            page.wait_for_selector(".tofoot", state="hidden")

            page.eval_on_selector(".turnbody", "el => el.scrollTop = 0")
            page.wait_for_selector(".tofoot", state="visible")
            page.click(".tofoot")
            page.wait_for_selector(".tofoot", state="hidden")
            assert page.evaluate(
                """() => { const one = document.querySelector('.turnbody');
                    return one.scrollHeight - one.scrollTop - one.clientHeight; }"""
            ) < 80
        finally:
            browser.close()


# --- folding a round on the map ----------------------------------------------

def test_a_round_folds_shut_from_its_icon_and_the_rest_of_the_row_still_goes(page_at):
    """The row has two jobs. Folding on any click would mean you could not
    read a round without closing it."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            wait_for_map(page, 2)
            count = "document.querySelectorAll('.filelist.transcript button').length"
            rows = "() => " + count
            before = page.evaluate(rows)
            assert before >= 2, before

            page.click(".filelist.transcript button.dir >> nth=0 >> .icon")
            page.wait_for_function("n => " + count + " < n", arg=before)
            folded = page.evaluate(rows)

            # The name still goes to that place, and does not unfold it.
            page.click(".filelist.transcript button.dir >> nth=0 >> .name")
            page.wait_for_selector(".turn.linked")
            assert page.evaluate(rows) == folded

            page.click(".filelist.transcript button.dir >> nth=0 >> .icon")
            page.wait_for_function("n => " + count + " === n", arg=before)
        finally:
            browser.close()


# --- what the agent was thinking ---------------------------------------------

def test_showing_thinking_says_what_it_did(page_at):
    """The key worked from the day it shipped and read as broken anyway: most
    transcripts hold no thinking at all, so it changed nothing on screen and
    nothing said why."""
    daemon, path = page_at
    with open(daemon_transcript(daemon), "a") as handle:
        handle.write(json.dumps({
            "type": "assistant", "timestamp": "2026-09-18T14:20:01.000Z",
            "message": {"role": "assistant", "content": [
                {"type": "thinking", "thinking": "Let me weigh this up.",
                 "signature": "sig"},
                {"type": "text", "text": "Right."}]}}) + "\n")
    daemon.tick()
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function(
                "() => document.querySelectorAll('.turn.thinking').length === 1")
            assert page.locator(".turn.thinking").is_hidden()
            # Every word the page passes to `note`, kept where the stream
            # cannot repaint it. Reading `#live` after a keypress is a race —
            # a push is allowed to take a passing word back — and asserting
            # on the key rather than on `toggleThinking()` is the only way to
            # hold that `t` is bound to the thing that speaks.
            page.evaluate("""() => { window.__said = [];
              const real = note;
              note = (text) => { window.__said.push(text); real(text); }; }""")

            page.keyboard.press("t")
            page.wait_for_selector(".turn.thinking", state="visible")
            page.keyboard.press("t")
            page.wait_for_selector(".turn.thinking", state="hidden")
            assert page.evaluate("window.__said") == [
                "showing 1 thought", "hiding 1 thought"]
        finally:
            browser.close()


def test_a_transcript_with_nothing_thought_aloud_says_so(page_at):
    """Nothing on screen changes, so the slot is the only thing that can say
    the key was heard."""
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            wait_for_map(page)
            assert page.locator(".turn.thinking").count() == 0
            # Read back inside the call that writes it: the stream repaints
            # this slot on every push and is allowed to take the word back,
            # so a separate wait tests the machine's load, not the page.
            said = page.evaluate(
                """() => { toggleThinking();
                           return document.getElementById('live').textContent; }""")
            assert "nothing was thought aloud" in said, said
        finally:
            browser.close()


# --- how the transcript is laid out ------------------------------------------

def test_a_one_line_message_sits_in_the_middle_of_its_block(page_at):
    """`.who` carries a name, a day, a time and a copy button — 71 px of them
    — and a stretched bubble is as tall as that whatever is in it. One line
    then sat 14 px below the top with 41 px under it."""
    daemon, path = page_at
    with open(daemon_transcript(daemon), "a") as handle:
        handle.write(json.dumps({
            "type": "user", "timestamp": "2026-09-18T14:20:00.000Z",
            "message": {"role": "user", "content": "do the issues"}}) + "\n")
    daemon.tick()
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function(
                """() => [...document.querySelectorAll('.turn.mine .bubble')]
                          .some((b) => b.textContent.includes('do the issues'))""")
            seen = page.evaluate("""() => {
              const box = [...document.querySelectorAll('.turn.mine .bubble')]
                .find((b) => b.textContent.includes('do the issues'));
              const range = document.createRange();
              range.selectNodeContents(box);
              const text = range.getBoundingClientRect();
              const bubble = box.getBoundingClientRect();
              return {above: text.top - bubble.top,
                      below: bubble.bottom - text.bottom,
                      who: box.parentElement.querySelector('.who')
                              .getBoundingClientRect().height,
                      bubble: bubble.height};
            }""")
            # Within a pixel: the glyph box is not the line box, and no amount
            # of padding makes those two the same number.
            assert abs(seen["above"] - seen["below"]) <= 2, seen
            # And it is the column beside it that used to decide the height.
            assert seen["bubble"] < seen["who"], seen
        finally:
            browser.close()


def test_a_group_of_tool_calls_belongs_to_the_words_above_it(page_at):
    """Measured, the gaps used to be 16 px above and 16 px below — exactly
    equal, so the group read as belonging to neither, and to the reply below
    it, which is the thing you next want to read."""
    daemon, path = page_at
    with open(daemon_transcript(daemon), "a") as handle:
        handle.write(json.dumps({
            "type": "assistant", "timestamp": "2026-09-18T14:20:01.000Z",
            "message": {"role": "assistant", "content": [
                {"type": "text", "text": "First I will look around."}]}}) + "\n")
        for n in range(3):
            handle.write(json.dumps({
                "type": "assistant", "timestamp": "2026-09-18T14:20:02.000Z",
                "message": {"role": "assistant", "content": [
                    {"type": "tool_use", "id": f"t{n}", "name": "Bash",
                     "input": {"command": f"ls dir{n}"}}]}}) + "\n")
        handle.write(json.dumps({
            "type": "assistant", "timestamp": "2026-09-18T14:20:03.000Z",
            "message": {"role": "assistant", "content": [
                {"type": "text", "text": "Now I know what is there."}]}}) + "\n")
    daemon.tick()
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function(
                """() => [...document.querySelectorAll('.turnbody .turn')]
                    .some((t) => t.innerText.includes('Now I know'))""")
            seen = page.evaluate("""() => {
              const all = [...document.querySelectorAll('.turnbody .turn')];
              const at = all.findIndex((t) => t.innerText.includes('ls dir0'));
              const box = (n) => all[n].getBoundingClientRect();
              return {above: box(at).top - box(at - 1).bottom,
                      below: box(at + 3).top - box(at + 2).bottom};
            }""")
            assert seen["above"] < seen["below"], seen
        finally:
            browser.close()


def test_hidden_thinking_between_two_tool_calls_does_not_stack_them(page_at):
    """A thinking block is hidden, but CSS still counts it as the sibling
    before the next block. So a tool row after one read as "the first call
    after some words" and was pulled up 16 px, onto the tool row above it:
    two commands drawn on top of each other. The first fix went the other
    way: a call after words and a thought lost its pull-up, and stood 22 px
    under the words it belonged to. An agent thinks between calls, and
    between saying what it will do and doing it."""
    daemon, path = page_at

    def said(kind, text, **rest):
        return conftest.records(conftest.record(
            kind, text, ts="2026-09-18T14:20:02.000Z", **rest))

    with open(daemon_transcript(daemon), "a") as handle:
        handle.write(said("claude", "First I will look around."))
        for n in range(3):
            handle.write(said("think", f"Now dir{n}."))
            handle.write(said("tool", f"ls dir{n}", tool_id=f"t{n}"))
        handle.write(said("think", "That is all of them."))
        handle.write(said("claude", "Now I know what is there."))
    daemon.tick()
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function(
                """() => [...document.querySelectorAll('.turnbody .turn')]
                    .some((t) => t.innerText.includes('Now I know'))""")
            gaps = """() => {
              const shown = [...document.querySelectorAll('.turnbody .turn')]
                .filter((t) => t.getClientRects().length)
                .map((t) => t.getBoundingClientRect());
              return shown.slice(1).map((box, n) => box.top - shown[n].bottom);
            }"""
            hidden = page.evaluate(gaps)
            assert min(hidden) >= 0, hidden
            # The words, the three calls, the reply: the group sits under
            # the words that said what it would do, and apart from the reply
            # below it -- the same gaps as with no thought between them.
            above, *between, below = hidden[-4:]
            assert above < below, hidden
            assert max(between) < below, hidden
            page.evaluate("document.body.classList.add('show-thinking')")
            shown = page.evaluate(gaps)
            assert min(shown) >= 0, shown
            # Shown, each thought is the words a call belongs to.
            assert max(shown[-7:-2:2]) < min(shown[-6:-1:2]), shown
            assert len(shown) > len(hidden), (hidden, shown)
        finally:
            browser.close()


def test_a_group_of_calls_sits_under_the_line_that_announced_it(page_at):
    """Measured from the text, not from the box around it. `.who` -- a name,
    a time, the copy button -- is taller than one line of text, so it set the
    height of the turn: the calls stood 39 px under the words that announced
    them, and only 22 above the reply after them. Every test before this one
    measured box to box and said 6.

    The words and the calls arrive in two pushes, the way a live session
    sends them, so the words are already drawn when the page learns that a
    call comes next. And a column allowed to run down beside the calls must
    not run into the next one, which is tested where it is longest: a day
    line, one line of text, one call."""
    daemon, path = page_at
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

    def said(kind, text, ts=now, **rest):
        return conftest.records(conftest.record(kind, text, ts=ts, **rest))

    def tick_until(words):
        daemon.tick()
        page.wait_for_function(
            """(words) => [...document.querySelectorAll('.turnbody .turn')]
                .some((t) => t.innerText.includes(words))""", arg=words)

    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.set_viewport_size({"width": 1500, "height": 900})
            wait_for_map(page)
            wait_for_watching(daemon)
            with open(daemon_transcript(daemon), "a") as handle:
                handle.write(said("claude", "Now the tests for the split:"))
            tick_until("the split")
            with open(daemon_transcript(daemon), "a") as handle:
                for n in range(3):
                    handle.write(said("think", f"Now dir{n}."))
                    handle.write(said("tool", f"ls dir{n}", tool_id=f"t{n}"))
                handle.write(said("claude", "They all pass."))
                old = "2026-09-18T14:30:00.000Z"
                handle.write(said("claude", "One more look.", ts=old))
                handle.write(said("tool", "ls again", ts=old, tool_id="t9"))
                handle.write(said("claude", "Done.", ts=old))
            tick_until("Done.")
            # A block that has just arrived slides in, and while it moves it
            # is a stacking context of its own: nothing inside it can stand
            # over a later block, and it is 4 px from where it will rest.
            page.wait_for_function("() => !document.getAnimations().length")
            seen = """() => {
              const shown = [...document.querySelectorAll('.turnbody .turn')]
                .filter((t) => t.getClientRects().length);
              const box = (one) => one.getBoundingClientRect();
              const at = shown.findIndex((t) => t.innerText.includes('the split'));
              const words = shown[at];
              const calls = shown.slice(at + 1).filter(
                (t) => t.classList.contains('toolrow')).slice(0, 3);
              const reply = shown.find((t) => t.innerText.includes('all pass'));
              // What each name column shows, top to bottom, and where the
              // next one starts. The copy button is part of it, because a
              // hover shows it.
              const columns = shown.map((t) => t.querySelector('.who'))
                .filter((who) => who.children.length);
              const clash = columns.slice(1).map((who, n) =>
                box(who.firstElementChild).top
                  - box(columns[n].lastElementChild).bottom);
              const copy = words.querySelector('.copy');
              const c = box(copy);
              // Over the whole button, not its middle: the middle can fall
              // in the gap between two calls, and then nothing covers it.
              const hit = [0.2, 0.5, 0.8].every((y) => [0.2, 0.5, 0.8].every(
                (x) => copy.contains(document.elementFromPoint(
                  c.left + c.width * x, c.top + c.height * y))));
              // Thoughts shown, the block above the first call is a thought.
              const over = shown[shown.indexOf(calls[0]) - 1];
              return {
                above: box(calls[0]).top - box(over.lastElementChild).bottom,
                below: box(reply).top - box(calls[2]).bottom,
                clash, copyHit: hit,
              };
            }"""
            hidden = page.evaluate(seen)
            assert hidden["above"] <= 8, hidden
            assert hidden["below"] >= 20, hidden
            assert min(hidden["clash"]) >= 0, hidden
            assert hidden["copyHit"], hidden
            page.evaluate("document.body.classList.add('show-thinking')")
            shown = page.evaluate(seen)
            assert shown["above"] <= 8, shown
            assert min(shown["clash"]) >= 0, shown
        finally:
            browser.close()


def test_showing_the_thoughts_keeps_the_reader_where_they_were(page_at):
    """`t` shows the thoughts or hides them, and nothing else. The pane kept
    its scroll offset in pixels while blocks appeared or went above it, so
    the view jumped: at the foot of a transcript you read reply 21, one press
    later thought 6, and a second press reply 5. It read as a switch that
    showed some messages and then others. The block at the top of the view
    stays there, and a reader at the foot stays at the foot."""
    daemon, path = page_at
    made = []
    for n in range(40):
        made += [conftest.record("claude", f"Reply number {n}."),
                 conftest.record("think", f"Thought {n}.\nA second line.\n"
                                          "And a third."),
                 conftest.record("tool", f"ls {n}", tool_id=f"t{n}")]
    with open(daemon_transcript(daemon), "a") as handle:
        handle.write(conftest.records(*made))
    daemon.tick()
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.set_viewport_size({"width": 1400, "height": 700})
            wait_for_map(page, 40)
            page.wait_for_function(
                """() => [...document.querySelectorAll('.turnbody .turn')]
                    .some((t) => t.innerText.includes('Reply number 39'))""")
            # What the reader sees: the first block, thoughts aside, whose
            # bottom is inside the pane, and how far from the top it stands.
            seen = """() => {
              const pane = document.querySelector('.turnbody');
              const top = pane.getBoundingClientRect().top;
              const first = [...pane.querySelectorAll('.turn:not(.thinking)')]
                .find((t) => t.getBoundingClientRect().bottom > top);
              return {first: first.innerText.replace(/\\s+/g, ' ').slice(-20),
                      at: Math.round(first.getBoundingClientRect().top - top),
                      foot: pane.scrollHeight - pane.scrollTop
                            - pane.clientHeight < 2};
            }"""
            for where in ("the middle", "the foot"):
                page.evaluate(
                    "(y) => { const p = document.querySelector('.turnbody');"
                    " p.scrollTop = y === 'the foot' ? p.scrollHeight"
                    " : p.scrollHeight / 2; }", where)
                before = page.evaluate(seen)
                for press in ("shown", "hidden"):
                    page.keyboard.press("t")
                    now = page.evaluate(seen)
                    if where == "the foot":
                        assert now["foot"], (where, press, before, now)
                    else:
                        assert now["first"] == before["first"], (where, press,
                                                                 before, now)
                        assert abs(now["at"] - before["at"]) <= 1, (
                            where, press, before, now)
        finally:
            browser.close()


def test_the_map_is_set_like_the_transcript_and_a_prompt_is_round(page_at):
    """The map names what stands beside it, so it wears the same type: face,
    size and line height. It had the lists' condensed face at 13 px and a row
    every 29 px, and read as a different page. And a prompt's bubble is
    rounded at all four corners -- it was square on the left, by the rail."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            wait_for_map(page)
            seen = page.evaluate("""() => {
              const style = (sel) => getComputedStyle(document.querySelector(sel));
              const text = style('.turnbody .prose'), row = style(
                '.filelist.transcript button');
              const rows = [...document.querySelectorAll(
                '.filelist.transcript button')].map((b) => b.getBoundingClientRect());
              const bubble = style('.turn.mine .bubble');
              return {
                text: [text.fontFamily, text.fontSize, text.lineHeight],
                row: [row.fontFamily, row.fontSize, row.lineHeight],
                pitch: rows[1].top - rows[0].top,
                line: parseFloat(text.lineHeight),
                corners: [bubble.borderTopLeftRadius, bubble.borderBottomLeftRadius,
                          bubble.borderTopRightRadius, bubble.borderBottomRightRadius],
              };
            }""")
            assert seen["row"] == seen["text"], seen
            assert seen["pitch"] <= seen["line"] + 4, seen
            assert "0px" not in seen["corners"], seen
        finally:
            browser.close()


def test_the_gap_a_reader_sees_after_a_prompt_or_a_line_is_the_gap_meant(page_at):
    """Measured from what is drawn, not from the box. The name column carried
    the copy button on a line of its own and stood 55 px tall -- taller than a
    line of text or a prompt's bubble -- so it set the height of the turn: 32
    px after a prompt where 22 was meant, 59 after a one-line reply before a
    prompt where 26 was. And no column may reach the rule over the next
    prompt, or the next turn's name."""
    daemon, path = page_at
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    old = "2026-09-18T14:30:00.000Z"
    with open(daemon_transcript(daemon), "a") as handle:
        handle.write(conftest.records(
            conftest.record("you", "Give me the command.", ts=now),
            conftest.record("claude", "Run this one.", ts=now),
            conftest.record("you", "And then?", ts=now),
            conftest.record("you", "An old prompt.", ts=old),
            conftest.record("claude", "An old reply.", ts=old)))
    daemon.tick()
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function(
                """() => [...document.querySelectorAll('.turnbody .turn')]
                    .some((t) => t.innerText.includes('An old reply'))""")
            page.wait_for_function("() => !document.getAnimations().length")
            seen = page.evaluate("""() => {
              const box = (one) => one.getBoundingClientRect();
              const turn = (words) => [...document.querySelectorAll(
                '.turnbody .turn')].find((t) => t.innerText.includes(words));
              const gap = (a, b) => box(turn(b)).top
                - box(turn(a).lastElementChild).bottom;
              const who = (words) => box(turn(words).querySelector('.who'));
              const stamp = turn('Give me').querySelector('.stamp');
              return {
                afterPrompt: gap('Give me', 'Run this one'),
                beforePrompt: gap('Run this one', 'And then'),
                afterOldPrompt: gap('An old prompt', 'An old reply'),
                // The rule over a prompt is its ::before, 14 px above it.
                toRule: box(turn('And then')).top - 14 - who('Run this one').bottom,
                // One line, with the button in it, not a second line under.
                copyOnTimeLine: !!stamp.querySelector('.copy')
                                && box(stamp).height < 20,
              };
            }""")
            assert seen["afterPrompt"] <= 23, seen
            assert seen["beforePrompt"] <= 30, seen
            assert seen["afterOldPrompt"] <= 23, seen
            assert seen["toRule"] >= 1, seen
            assert seen["copyOnTimeLine"], seen
        finally:
            browser.close()


def test_the_send_box_starts_where_the_transcript_does(page_at):
    """It stood under the map beside the transcript as well, which is a column
    you never type into."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            wait_for_map(page)
            seen = page.evaluate("""() => {
              const box = (sel) =>
                document.querySelector(sel).getBoundingClientRect();
              return {bar: box('#sendbar').left, pane: box('.turnbody').left,
                      side: box('.side').right};
            }""")
            assert abs(seen["bar"] - seen["pane"]) <= 1, seen
            assert seen["bar"] > seen["side"], seen
        finally:
            browser.close()


def test_a_rewritten_transcript_forgets_what_was_chosen_by_seq(page_at):
    """`seq` is a place in one reading, not an identity. A transcript
    rewritten under its own name counts from nought again, so the expanded
    tool results, the folded rounds and the marked row all point at different
    blocks. Three things keyed the same way, forgotten in one place."""
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            wait_for_map(page)
            seen = page.evaluate("""() => {
              state.turns.run = 4;
              state.turns.open = new Set([2]);
              state.turns.shut = new Set([0]);
              state.turns.at = 2;
              const same = (run) => {
                forgetPlaces();     // what a run change calls
                return [state.turns.open.size, state.turns.shut.size,
                        state.turns.at];
              };
              return same();
            }""")
            assert seen == [0, 0, None], seen
        finally:
            browser.close()


def test_a_reading_that_has_not_changed_forgets_nothing(page_at):
    """Two things must not look like a rewrite. `-1` is "none held yet",
    which is every first load — and `goTo` is set from the address bar before
    the transcript is fetched, so forgetting there threw away the link the
    page had just been opened on. And a session coming back keeps its place,
    which is why `run` is one of the things `savePlace` writes down."""
    _, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            wait_for_map(page)
            seen = page.evaluate("""async () => {
              const out = {};
              // A first load, with a link pending from the address bar.
              state.turns.run = -1;
              state.turns.goTo = 2;
              state.turns.open = new Set([1]);
              await loadTranscript();
              out.first = [state.turns.open.size, state.turns.run];

              // The same reading again: nothing has been rewritten.
              state.turns.open = new Set([1]);
              state.turns.shut = new Set([0]);
              await loadTranscript();
              out.again = [state.turns.open.size, state.turns.shut.size];

              // A reading that really did change.
              state.turns.run = 99;
              await loadTranscript();
              out.rewritten = [state.turns.open.size, state.turns.shut.size,
                               state.turns.at];
              return out;
            }""")
            # The link survived the first load, whatever `run` came back.
            assert seen["first"][0] == 1, seen
            assert seen["again"] == [1, 1], seen
            assert seen["rewritten"] == [0, 0, None], seen
        finally:
            browser.close()


def test_a_round_on_the_map_says_whether_it_is_folded(page_at):
    """A second target on a row is not something a reader can be expected to
    find, and `.icon` is decoration everywhere else in this list."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            wait_for_map(page, 2)
            row = ".filelist.transcript button.dir >> nth=0"
            assert page.locator(row).get_attribute("aria-expanded") == "true"
            assert "fold" in page.locator(row + " >> .icon").get_attribute("title")
            page.click(row + " >> .icon")
            page.wait_for_function(
                """() => document.querySelector('.filelist.transcript button.dir')
                          .getAttribute('aria-expanded') === 'false'""")
            assert "open" in page.locator(row + " >> .icon").get_attribute("title")
        finally:
            browser.close()


def test_a_push_that_beats_the_first_fetch_forgets_nothing(page_at):
    """The stream and the fetch race, and on a busy machine the push wins.
    `run` is then still -1 with nothing held, so replacing the blocks is
    right and forgetting the reader's place is not — it threw away a link
    the page had opened on whenever the two arrived in that order."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            wait_for_map(page)
            wait_for_watching(daemon)
            # Exactly the state a push-before-fetch lands on: nothing held,
            # and a place the address bar has already asked for.
            page.evaluate("""() => {
              state.turns.run = -1;
              state.turns.at = 2;
              state.turns.open = new Set([1]);
            }""")
            with open(daemon_transcript(daemon), "a") as handle:
                handle.write(json.dumps({
                    "type": "assistant",
                    "timestamp": "2026-09-18T14:30:00.000Z",
                    "message": {"role": "assistant", "content": [
                        {"type": "text", "text": "Pushed."}]}}) + "\n")
            daemon.tick()
            page.wait_for_function(
                "() => state.turns.run !== -1")
            # At its own `seq`, not packed at nought: a push carries only the
            # blocks that changed.
            assert page.evaluate(
                "state.turns.blocks.findIndex(b => b && b.text === 'Pushed.')") > 0
            assert page.evaluate("state.turns.at") == 2
            assert page.evaluate("state.turns.open.size") == 1
        finally:
            browser.close()


# --- the fetch and the stream race ---------------------------------------------


def hold_next_transcript(page, how_many=1):
    """Hold the next transcript requests, and let the ones after them go.
    The answer is built when `fetch()` is called on a held one, which is the
    moment the daemon takes its snapshot. `unroute` would answer a held
    request itself, so the route stays until the test is done."""
    held = []

    def hold(route):
        if len(held) < how_many:
            held.append(route)
        else:
            route.continue_()

    page.route("**/transcript", hold)
    return held


def wait_for_request(page, held):
    for _ in range(500):
        if held:
            return held[0]
        page.wait_for_timeout(20)
    raise AssertionError("the page never asked for the transcript")


def test_a_block_pushed_while_the_transcript_is_fetched_is_kept(page_at):
    """The daemon takes the GET's snapshot, lets go of its lock, and writes
    the answer; a tick in between pushes the next block, and a push is small
    and gets there first. `loadTranscript` then put the older snapshot in
    place wholesale: the block was gone, the next one landed after a hole,
    and a text block is never pushed twice."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            wait_for_map(page)
            wait_for_watching(daemon)
            show_tab(page, "session")
            held = hold_next_transcript(page)
            page.click('.tab[data-tab="transcript"]')
            route = wait_for_request(page, held)
            answer = route.fetch()                   # the snapshot, taken now
            count = page.evaluate("state.turns.blocks.length")
            append_blocks(daemon, ["Pushed while the answer was on its way."])
            page.wait_for_function(f"state.turns.blocks.length > {count}")
            route.fulfill(response=answer)
            page.unroute("**/transcript")
            page.wait_for_function(
                """() => [...document.querySelectorAll('.turn')].some(
                     one => one.innerText.includes('on its way'))""")
            assert page.evaluate(
                "state.turns.blocks.every(Boolean)"), "a hole in the blocks"
        finally:
            browser.close()


def test_a_transcript_fetch_that_fails_keeps_what_is_held(page_at):
    """`ask` gives null for a fetch that failed, and the page drew that as
    "Nothing in this transcript yet.", forgot the reader's places, and asked
    no more -- the tab polls nothing. The next push, carrying only the block
    that changed, was then put at index 0 as though it were the whole."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            wait_for_map(page)
            wait_for_watching(daemon)
            before = page.evaluate("document.querySelectorAll('.turn').length")
            page.evaluate("state.turns.open = new Set([1])")
            show_tab(page, "session")
            page.route("**/transcript", lambda route: route.abort())
            page.click('.tab[data-tab="transcript"]')
            page.wait_for_timeout(300)             # the failed answer is in
            page.unroute("**/transcript")
            assert page.evaluate(
                "document.querySelectorAll('.turn').length") == before
            assert page.evaluate("state.turns.open.size") == 1
            # It asks again by itself: the tab polls nothing.
            page.wait_for_function("state.turns.failed === false")
            # With nothing held, it says it could not read it -- not that
            # there is nothing.
            said = page.evaluate("""() => {
              const blocks = state.turns.blocks;
              state.turns.blocks = []; state.turns.failed = true; draw();
              const text = document.querySelector('.turnbody').innerText;
              state.turns.blocks = blocks; state.turns.failed = false; draw();
              return text;
            }""")
            assert "could not be read" in said, said
            # And a push lands at its own place.
            count = page.evaluate("state.turns.blocks.length")
            append_blocks(daemon, ["After the failure."])
            page.wait_for_function(
                """() => [...document.querySelectorAll('.turn')].some(
                     one => one.innerText.includes('After the failure.'))""")
            assert page.evaluate(
                f"state.turns.blocks[{count}].text") == "After the failure."
        finally:
            browser.close()


def test_a_block_read_while_no_stream_was_open_is_fetched(page_at):
    """A tick between the fetch's snapshot and the stream joining the hub
    sends to nobody, and so does one while a dropped stream reconnects. The
    stream now opens by saying how long the transcript is, and the page
    fetches what it is missing."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            wait_for_map(page)
            wait_for_watching(daemon)
            page.evaluate("""() => { state.stream.close(); state.stream = null;
                                     state.streamUrl = ''; }""")
            append_blocks(daemon, ["Said while nobody listened."])
            page.evaluate("resubscribe()")
            page.wait_for_function(
                """() => [...document.querySelectorAll('.turn')].some(
                     one => one.innerText.includes('nobody listened'))""")

            # And when the stream says so while a fetch is on its way, the
            # fetch's older snapshot is not the last word.
            show_tab(page, "session")
            held = hold_next_transcript(page)
            page.click('.tab[data-tab="transcript"]')
            route = wait_for_request(page, held)
            answer = route.fetch()                   # the snapshot, taken now
            page.evaluate("""() => { state.stream.close(); state.stream = null;
                                     state.streamUrl = ''; }""")
            append_blocks(daemon, ["Said while the fetch was out."])
            page.evaluate("resubscribe()")
            page.wait_for_function("state.turns.told !== null")
            route.fulfill(response=answer)
            page.unroute("**/transcript")
            page.wait_for_function(
                """() => [...document.querySelectorAll('.turn')].some(
                     one => one.innerText.includes('the fetch was out'))""")
        finally:
            browser.close()


def test_a_scroll_left_over_from_another_transcript_is_not_its_place(pair_at):
    """`.turnbody` keeps the last session's blocks until the new ones land,
    and its listener wrote any scroll into the new session's place -- one
    the browser fires itself when the send box goes away and the pane grows.
    The `.filescroll` scar, without its guard."""
    daemon, path = pair_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function("document.querySelectorAll('.row').length === 2")
            page.evaluate("choose('s1')")
            wait_for_map(page)
            wait_for_watching(daemon)
            append_blocks(daemon, [f"line {n}" for n in range(60)])
            page.wait_for_function(
                "document.querySelectorAll('.turn').length > 50")
            down = page.evaluate("""() => {
              choose('s2');
              const pane = document.querySelector('.turnbody');
              pane.scrollTop = 40;
              pane.dispatchEvent(new Event('scroll'));
              return [pane.scrollTop, state.turns.down];
            }""")
            assert down[0] == 40, "the pane did not scroll, so this proves nothing"
            assert down[1] in (None, 0), down
        finally:
            browser.close()


def test_the_top_of_the_transcript_is_a_place_too(page_at):
    """`down` was 0 both for "no place kept" and for "at the very top", and a
    draw reads the first as "go to the foot". A reader at the top was thrown
    to the foot on every key typed in the find box."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            append_blocks(daemon, [f"pytest run {n}" for n in range(60)])
            page.wait_for_function(
                "document.querySelectorAll('.turn').length > 50")
            page.evaluate("""() => {
              const pane = document.querySelector('.turnbody');
              pane.scrollTop = 0;
              pane.dispatchEvent(new Event('scroll'));
            }""")
            page.fill("#find", "pytest")
            page.wait_for_function("document.querySelectorAll('mark').length > 0")
            assert page.evaluate(
                "document.querySelector('.turnbody').scrollTop") == 0
        finally:
            browser.close()


def write_records(daemon, *made):
    """Records from `conftest.record`, onto the session's transcript, unread."""
    with open(daemon_transcript(daemon), "a") as handle:
        handle.write(conftest.records(*made))


def has_text(text):
    return ("() => state.turns.blocks.some(b => b && b.text === "
            + json.dumps(text) + ")")


def test_a_tool_result_read_while_no_stream_was_open_is_fetched(page_at):
    """A tool result is written into its call's block, so the number of
    blocks does not move, and a stream that opened on a count saw nothing
    missing. It opens on `version`, which moves with every change read."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            wait_for_map(page)
            wait_for_watching(daemon)
            write_records(daemon, conftest.record("tool", "make", tool_id="t9"))
            daemon.tick()
            page.wait_for_function(
                "state.turns.blocks.some(b => b && b.tool_use_id === 't9')")
            page.evaluate("""() => { state.stream.close(); state.stream = null;
                                     state.streamUrl = ''; }""")
            write_records(daemon, conftest.record("result", "BUILD DONE",
                                                  tool_id="t9"))
            daemon.read_transcript("s1")          # read, and sent to nobody
            page.evaluate("resubscribe()")
            page.wait_for_function(
                """() => state.turns.blocks.some(
                     b => b && b.tool_use_id === 't9'
                          && (b.result || '').includes('BUILD DONE'))""")
        finally:
            browser.close()


def test_a_fetch_older_than_a_pushed_reading_is_asked_again(page_at):
    """The transcript was rewritten while a fetch was out: the push brought
    the new reading, and then the fetch put the old one back and forgot the
    reader's places for it."""
    import os
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            wait_for_map(page)
            wait_for_watching(daemon)
            show_tab(page, "session")
            held = hold_next_transcript(page)
            page.click('.tab[data-tab="transcript"]')
            route = wait_for_request(page, held)
            answer = route.fetch()               # the old reading
            where = daemon_transcript(daemon)
            spare = str(where) + ".new"
            with open(spare, "w") as handle:
                handle.write(conftest.records(
                    conftest.record("claude", "A WHOLLY NEW READING")))
            os.replace(spare, where)             # a new inode: a new run
            daemon.tick()
            page.wait_for_function(has_text("A WHOLLY NEW READING"))
            run = page.evaluate("state.turns.run")
            route.fulfill(response=answer)
            page.wait_for_function(
                f"""() => state.turns.early === null && state.turns.run === {run}
                     && document.querySelector('.turnbody').innerText
                          .includes('WHOLLY NEW')""")
        finally:
            browser.close()


def test_only_the_newest_transcript_fetch_lands(page_at):
    """A quick Transcript-Session-Transcript put two fetches out. The push
    went into the second one's list; the first, answering last, put its
    older snapshot back without it -- and a text block is never pushed
    twice."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            wait_for_map(page)
            wait_for_watching(daemon)
            show_tab(page, "session")
            held = hold_next_transcript(page, 2)
            page.click('.tab[data-tab="transcript"]')
            first = wait_for_request(page, held)
            older = first.fetch()
            page.click('.tab[data-tab="session"]')
            page.click('.tab[data-tab="transcript"]')
            for _ in range(500):
                if len(held) > 1:
                    break
                page.wait_for_timeout(20)
            second = held[1]
            newer = second.fetch()
            write_records(daemon, conftest.record("claude", "PUSHED BETWEEN"))
            daemon.tick()
            page.wait_for_function(has_text("PUSHED BETWEEN"))
            second.fulfill(response=newer)
            page.wait_for_function("state.turns.early === null")
            first.fulfill(response=older)
            page.unroute("**/transcript")
            page.wait_for_timeout(500)           # proving it did not go
            assert page.evaluate(has_text("PUSHED BETWEEN"))
        finally:
            browser.close()


def test_failing_fetches_keep_one_retry_not_one_each(page_at):
    """Every tab switch into a failing fetch started a two-second loop of its
    own, and they never stopped: four switches, four loops, and when the
    daemon came back each asked for the whole transcript at once."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            wait_for_map(page)
            asked = []
            page.route("**/transcript",
                       lambda route: (asked.append(1), route.abort()))
            for _ in range(4):
                page.click('.tab[data-tab="session"]')
                page.click('.tab[data-tab="transcript"]')
                page.wait_for_timeout(100)
            before = len(asked)
            page.wait_for_timeout(4500)          # proving it did not happen
            assert len(asked) - before <= 3, len(asked) - before
        finally:
            browser.close()


def test_a_failed_fetch_does_not_take_a_sessions_place(page_at, ws,
                                                        transcript_file,
                                                        tmp_path):
    """An empty draw took the last session's scrolled blocks away, the
    scrollbar fell to nought, and that scroll was written as the place of
    the session whose fetch had failed: it came back at the top."""
    daemon, path = page_at
    other = tmp_path.parent / "second"
    other.mkdir(exist_ok=True)
    kept = transcript_file("s2", [conftest.record("claude", f"s2 line {n}")
                                  for n in range(80)])
    ws.append_event(conftest.event("SessionStart", sid="s2", cwd=str(other),
                                   pane="%9", pid=2, ts=time.time(),
                                   transcript_path=str(kept)))
    daemon.store.refresh()
    scroll = """(to) => { const pane = document.querySelector('.turnbody');
                          pane.scrollTop = to;
                          pane.dispatchEvent(new Event('scroll')); }"""
    showing = """(text) => document.querySelector('.turnbody')
                             .innerText.includes(text)"""
    with sync_playwright() as play:
        browser, page = open_page(play, path)
        try:
            page.wait_for_function("document.querySelectorAll('.row').length === 2")
            page.evaluate("choose('s1')")
            wait_for_map(page)
            wait_for_watching(daemon)
            append_blocks(daemon, [f"s1 line {n}" for n in range(80)])
            page.wait_for_function(showing, arg="s1 line 79")
            page.evaluate("choose('s2')")
            page.wait_for_function(showing, arg="s2 line 79")
            page.evaluate(scroll, 600)
            page.wait_for_function("state.turns.down === 600")
            page.evaluate("choose('s1')")
            page.wait_for_function(showing, arg="s1 line 79")
            page.evaluate(scroll, 900)
            page.route("**/transcript", lambda route: route.abort())
            page.evaluate("choose('s2')")
            page.wait_for_function("state.turns.failed === true")
            page.wait_for_timeout(300)           # the scroll event is in
            page.unroute("**/transcript")
            assert page.evaluate("state.turns.down") == 600
            page.wait_for_function("state.turns.failed === false")
            page.wait_for_function(
                "document.querySelector('.turnbody').scrollTop === 600")
        finally:
            browser.close()
