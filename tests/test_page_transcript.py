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
    daemon_transcript,
)

pytestmark = skip_without_browser

def test_the_page_draws_the_session(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
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
            before = page.locator(".turn").count()
            assert page.locator(".row.chosen").count() == 1

            with open(daemon_transcript(daemon), "a") as handle:
                handle.write(json.dumps({
                    "type": "assistant", "timestamp": "2026-09-18T14:09:00.000Z",
                    "message": {"role": "assistant", "content": [
                        {"type": "text", "text": "A brand new line."}]}}) + "\n")
            daemon.tick()
            page.wait_for_timeout(1200)
            assert page.locator(".turn").count() == before + 1
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


def test_an_error_in_the_live_slot_gives_the_slot_back(page_at):
    """The slot says whether the stream is live. An error borrows it for four
    seconds and has to give it back — it used to assign itself back, so the
    word never returned."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.wait_for_function(
                "document.getElementById('live').textContent === 'live'")
            page.evaluate("said({error: 'no pane for this session'})")
            assert "no pane" in page.locator("#live").inner_text()
            page.wait_for_function(
                "document.getElementById('live').textContent === 'live'",
                timeout=15000)
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
            said = page.evaluate("""() => [
              glimpse("## A heading\\n\\nand then some"),
              glimpse("\\n\\n- a bullet first"),
              glimpse("**bold to start** and on"),
              glimpse("`code` first"),
              glimpse("x".repeat(80)),
              glimpse(""),
            ]""")
            assert said[:4] == ["A heading", "a bullet first",
                                "bold to start and on", "code first"]
            assert len(said[4]) == 44 and said[4].endswith("…")
            assert said[5] == ""
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


def test_at_most_forty_links_in_one_block(ws, page_at):
    """A pattern that matches everything would otherwise build a link per
    word. The cap is the daemon's number too."""
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
              box.textContent = Array.from({length: 100},
                                           (x, n) => 'T-' + n).join(' ');
              linkTickets(box);
              return box.querySelectorAll('a.ticket').length;
            }""")
            assert made == 40, made
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
