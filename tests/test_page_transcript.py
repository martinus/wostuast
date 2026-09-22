"""The Transcript tab: what an agent said, and what it may not do to this page.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations

import json

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
            blocks, run = daemon.read_transcript("s1")
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
            blocks, run = daemon.read_transcript("s1")
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


def test_our_own_word_in_the_live_slot_gives_the_slot_back(page_at):
    """The slot says whether the stream is live. A passing word borrows it
    for four seconds and has to give it back — it used to assign itself
    back, so the word never returned."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.wait_for_function(
                "document.getElementById('live').textContent === 'live'")
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
                "document.getElementById('live').textContent === 'live'",
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
                "document.getElementById('live').textContent === 'live'")
            page.evaluate("said({error: 'no pane for this session'})")
            assert "no pane" in page.locator("#live").inner_text()
            page.wait_for_timeout(4500)     # proving it did NOT go away
            assert "no pane" in page.locator("#live").inner_text()
            # The next thing that works gives the slot back.
            page.evaluate("said({done: true})")
            assert page.locator("#live").inner_text() == "live"
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
                "document.getElementById('live').textContent === 'live'")
            page.evaluate("said({error: 'no pane for this session'})")
            assert "no pane" in page.locator("#live").inner_text()

            # A push, which is what the daemon does whenever anything moves.
            daemon.hub.send("sessions", daemon.sessions_payload())
            page.wait_for_timeout(500)
            assert "no pane" in page.locator("#live").inner_text()
            # And the stream's own word is not lost either: it is underneath.
            page.evaluate("said({done: true})")
            assert page.locator("#live").inner_text() == "live"
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
            assert page.evaluate("state.turns.at") == 2
            assert page.evaluate("state.turns.open.size") == 1
        finally:
            browser.close()
