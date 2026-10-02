# Writing a test that holds

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. How a browser test waits, why it goes red under load, and how
to prove it guards what it claims.

Most of the suite drives a real browser, so it waits far more than it computes:
four workers cut it to about a third, and the tests are safe in parallel —
every daemon binds port 0, every fixture has its own `tmp_path`, and each worker
launches a Chromium of its own. **Oversubscribing the cores pays, up to about
twice their number.** Measured on four cores over the whole suite: `-n 4` 110 s,
`-n 6` 96 s, `-n 8` 88 s, `-n 12` 107 s. Nothing timed out at 8, which
supersedes the older note here that more workers than cores only made things
worse — it stopped being true as the suite grew. The tests that run no browser
are the other shape, CPU-bound and slightly *slower* at `-n 8` (25.5 s against
24.5 s), so CI runs the matrix at `-n auto` and the browser shards at `-n 8`.

**A daemon a test serves polls at 0.05 s, not the default half second.**
`server.shutdown()` waits for `serve_forever`'s loop to look again, and
every test that serves pays that at its teardown: 451 ms each, measured,
which was 54 s of `test_serve.py`'s 79 s run alone. `served`, `shot.py`
and `stage.py` pass `kwargs={"poll_interval": 0.05}`; `page_at` is built
on `served` so it cannot fall behind. A new fixture that serves is built
on `served` too, never on a `make_server` of its own. Two socket tests
that waited five seconds for an answer that never came send
`Connection: close` (#280); a test that waits for `LIST_FRESH` sets it
to 0.

**A test that commits in a clone gives the clone an identity.** CI has no
global git identity, and `git clone` does not carry the `user.email` the
`repo` fixture sets locally, so a commit there fails with status 128 in CI
and passes on any desk that has one. Run the suite once with
`GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1` when a test commits
somewhere new.

**A fake of a call that never returns must raise.** `os.execv`,
`sys.exit` and `os._exit` end the code that calls them; a fake that only
records its arguments lets that code run on, into what the real call would
never reach. `test_update.py` faked `execv` in `cmd_install` that way, and
the install went on to `bring_up_to_date`, which wrote the checkout back
over the copy just fetched: the test went red on the file, for a reason no
real run has. The fake raises an exception of the test's own (`Handed`),
and the test expects it with `pytest.raises`.

**What the suite does not cover.** It drives the happy path thoroughly, in a
real browser. It says very little about what happens when something *fails*: of
the eight issues a full-file review filed, three were "a failed git call renders
as an answer", one a lock race between two HTTP threads, one a rotation race
between two hooks. Green is not evidence about those. When you change anything
that calls git, touches a file, or is reached from more than one thread, write
the failing case yourself — nothing else will.

**Prove a test earns its place — by breaking what it claims to guard, which is
not always the fix you just wrote.** Write the test, then perturb the thing it
is about and watch it fail. Two have slipped through here:

- One passed with its fix removed, because another line was saving the state it
  asserted.
- One claimed `is_listed` is never cached, and removed the file with `git rm` —
  which deletes it from disk, so the read was refused by `target.is_file()`
  whatever `is_listed` said. Reverting the cache would not have caught it. The
  perturbation that did was stubbing `is_listed` to always say yes.

Ask what single change should make this test go red. If that change is not the
one you make, the test is about something else than you think.

**`tests/perturb.py` does the breaking.** Each break in its JSON list names
the tests it should turn red, and only those run: the whole file for each
break cost 7 to 40 s a break, and one fix had twelve breaks. It puts the
file back after each, and on Ctrl-C. Read its last line, not its exit
status alone: `GREEN` is a break no test saw, and "nothing ran" is a
selection that matched no test, which passes for proof if nobody reads it.
Keep the breaks list in the scratchpad; it is about one fix.
- **It deletes the file's bytecode after every write** (`forget_bytecode`),
  the break and the file put back. Python runs a cached `.pyc` while the
  source's mtime in whole seconds and its size match, and two breaks in
  one second that change the size by the same count ran the first one's
  code: `SEND_MAX = 12000`, then `POST_MAX = 64 * 1024`, said GREEN for the
  second, which was red alone (#328). **A GREEN that is red alone is this,
  or a test that leans on another**: run that break by itself before you
  believe either. `test_no_bytecode_of_a_break_is_left_behind`.

**A test outside `tests/test_page_*` that drives a browser carries
`@skip_without_browser`** -- one that runs `tests/shot.py` or
`tests/stage.py` too. CI's pytest jobs have no Playwright, and only the
browser shards do; locally both are there, so nothing on the desk says it
is missing. `test_eval_runs_in_the_page_before_the_picture` went red on all
four Python versions in CI, after three green runs here. To see what that
job sees, put a `playwright/__init__.py` that raises `ImportError` in a
folder of the scratchpad and run the suite with that folder on
`PYTHONPATH`: every browser test must skip, and nothing may fail.

**Measure where something is with `getBoundingClientRect`, never
`offsetTop`**: a `.turn` is positioned, so `offsetTop` inside it counts
from the turn, and a test that scrolled to "the middle of the log" never
moved the pane -- its break went GREEN. **And a scroll test needs content
after what it scrolls past**: with a short transcript under it, the
browser cut the scroll back to the new end, and the message was in sight
by chance (`test_folding_from_the_foot_of_the_pane_keeps_the_message_in_sight`).

**Playwright.** **`fill` with a long text of many lines takes for ever**:
60 KB of short lines did not end in 60 s, while the page's own input
handler took 10 ms of it. Put a long text in as a paste does: set `value`
in `evaluate` and send one `input` event
(`test_a_tall_send_box_says_how_much_it_holds`). A hover-only control (`.plus`) needs `click(force=True)`. Wait
for what the page has drawn, never for a number of seconds; `wait_for_timeout`
is right only when proving something did **not** happen. Ask one question when a
redraw could land between two: `wait_for_function("...length === 1")`, not
`wait_for_selector` then `.count()`. **`evaluate` waits for a promise it is
handed**: `page.evaluate("load()")` with the request held by a route never
returned, and the test hung past every timeout, because `evaluate` has
none. Call it without returning it: `"() => { load(); }"`. And one route
handler that holds the first request and answers the rest, never
`unroute` with one held — it answers the held one itself. **That handler
and the wait for it are `hold(page, pattern)` and `wait_until(page,
check)` in `tests/browser.py`, never a copy.** Eight loops in four test
files waited their own way, `for _ in range(300): if held: break`, and
three of them broke out, asserted nothing, and ran on into `held[0]`: an
`IndexError` that named no wait; `wait_until` raises when time runs out. The same
holds for `stub_send(page, answers, delay)` (`/send` answered from a
list, or with no `answers` slowed and passed on), `write_records`
(transcript lines built by `conftest.record`) and `comment_on_first_line`
(#281). **A route handler runs only while Playwright waits.** `kept()`
waits for `settings.json` by polling it in Python, and nothing in that loop
gives Playwright a turn, so the `hold` handler that should let the second
POST through never ran and the test waited out its timeout. Wait with
`page.expect_response(...)` first, then read the file:
`test_two_quick_changes_reach_the_file_in_the_order_they_were_made` is the
shape. **A mark that
shows for a set time is written down by the page, not waited for**: the
copy button's tick (`putCodeCopies`, `.copycode.done`) lasts 1.4 s, and
`test_a_code_block_copies_itself_from_a_button_that_shows_on_hover` spent
longer than that under load on the steps between the click and its wait.
A `MutationObserver` set before the click keeps `window.__done`, and the
test waits for that.

**A change a stream test expects goes out after the first event, never
after a sleep.** `test_a_change_is_pushed` made its change from a thread
0.3 s after it started to connect. On a loaded CI runner the stream opened
after the push: it began on the new state, and the read waited for a second
event that never came. `read_events(..., then=change)` runs the change once
the first event is in, and `stream` joins the hub before it writes that
event, so nothing pushed after it is lost.
- **In a browser test, `wait_for_watching(daemon)` comes before the first
  `daemon.tick()`.** `open_page` and `wait_for_map` prove the fetch
  answered, not that the stream listens: `showTab` fetches and *then*
  subscribes, a tick in that gap pushes to nobody, and no fixture runs a
  ticker to push it again. Three transcript tests appended and ticked
  straight after `open_page` and went red at `-n 12` about one run in
  three, on `main` as well: `test_a_search_keeps_its_place_while_the_agent_works`,
  `test_the_top_of_the_transcript_is_a_place_too` and
  `test_a_rewritten_transcript_replaces_the_page_rather_than_doubling_it`.
  A test about what happens while nobody listens leaves the wait out on
  purpose, and says so.

**A page test opens its page with `with opened(where) as page:`, never by
hand.** 383 of 410 tests wrote out `sync_playwright`, `open_page`, `try` and
`finally: browser.close()`, a level deeper than the body needed, and one
that forgot the `close` leaked a context (#283). `opened` closes it
whatever the block raised; `tab="diff"` opens the Review tab and waits for
its first line. A second page is `page.context.new_page()`. A test that
needs the context before the page -- a permission, an init script, a
held route -- takes `with own_context() as context:`, then
`context.new_page()` and `load(page, where)`.

**`open_page` returns once the transcript has answered; `show_tab` is not
the tab's content arriving.** `open_page` waits for `state.turns.landed` --
an answer with blocks, with none, or a failure -- because three tests in one
session read `.turnbody` the moment the frame was drawn and went red under
load, each after its own fix. So the fix is the helper's, once:
`wait="frame"` is the opt-out, for a test about the page before that answer
(one that holds the request before the page opens needs it, or it waits
for ever). `show_tab` still waits only for the frame -- the document inside
the Files tab fills one fetch later -- and `wait_for_map(page, rows)` is
still the wait for rows on the map. For anything else, wait for what the
page has *written down*, not for what the DOM shows: a scroll event writes
`state.files.down` a frame after the scroller moves, and a test that
switched sessions in between saved the top.
`test_open_page_returns_once_the_transcript_has_answered` slows the
daemon's answer, so the gap is there every time.

- **An empty send box is the send starting, not landing.** `sendTyped`
  empties `#say` in the same call as the Enter, before the POST leaves --
  on purpose, so words typed meanwhile are not lost (topics/safety, "One
  send at a time"). `test_the_enter_that_ends_a_composition_sends_nothing`
  waited for the empty box and then read the fake tmux's `seen`: 20 runs in
  144 red at `-n 12`, every one with `seen` empty at the assert and both
  `send-keys` in it by the time pytest printed the fixture. Holding
  `**/send` for 300 ms makes it red every time. A comment above `sendTyped`
  still said the box cleared "only once the daemon says the text went in",
  which is where the wrong wait came from. Wait for the keys in `seen`
  (`wait_until`), then `sending.size === 0` -- the lock is let go in the
  same turn that puts a refused text back, so the box can be read after it.
  `test_the_send_box_types_into_the_terminal` slept 500 ms for the same
  thing and waits the same way now. The other half of the rule holds the
  other way round: because the box empties at once, a box still full right
  after a composing Enter is proof nothing was sent, with no sleep in it.

**To hold what a key *says*, spy on `note`, not on `#live`.** The slot is
repainted on every push and the stream is allowed to take a passing word
back, so reading it after a keypress is a race. Reassigning `note` in the
page and keeping every word in an array holds both halves at once: that the
key is bound to the thing that speaks, and what it said. Calling the function
directly instead proves only the second, and then nothing guards the binding.
`spy_on_note(page)` in `tests/browser.py` does the reassigning, into
`window.__said`; two test files each wrote it out for themselves.

**The live slot is repainted on every push, so read it in the same
`evaluate` that writes it.** `note()` borrows the slot and the stream is
allowed to take it back — that is what one painter means. A `wait_for_function`
asking whether the word is there can therefore run after a repaint and wait
out its timeout, which is a test of the machine's load and not of the page.
Writing and reading inside one `evaluate` has no gap in it: JavaScript is
single-threaded and no push can land in the middle of the call.

**This scar keeps coming back, so recognise its shape rather than its
names.** It has been six tests over three sittings, and every one of them read
`.turn`, `.prose`, `.who`, `state.turns.blocks` or the find box on the line
after the page opened. Three symptoms, all of them "passes alone, red under
load": an empty list read as "it drew nothing"; `null.isConnected` or
`undefined.ts` thrown out of an `evaluate`; and a keystroke that went to the
page instead of the find box, because `split` moves that box when the
transcript lands and a box that moves loses the focus on it. A fourth: a fixture's
clock read after the page opened. `ago` counts seconds only for an age's
first minute, a loaded CI runner took longer than that to open the page,
and `test_a_row_is_not_rebuilt_every_second` read "1min" twice — so it
starts the count itself with a fresh event. A fifth: a pane that still
holds the last session's drawing of the same file. After `choose`, the
Files tab shows the old session's scroller until the new text lands, so
`open_file` found lines and returned, and a scroll went to a scroller
whose listener belongs to another session -- 4 runs in 10 red at `-n 12`.
Wait for `.filescroll[data-drawn="<session>"]`. The Review tab has it
too: after `choose`, the pane holds the last session's diff until the new
one lands, and `test_another_sessions_diff_is_read_from_its_top` scrolled
that one -- 2 runs in 3 red at `-n 12` -- until it waited for a file only
the new session changed. Running the test
files you changed at `-n 12` three times over is what turns them up; once
is not enough.
