# Writing a test that holds

How a browser test waits, why it goes red under load, and how to prove it guards what it claims.

**Oversubscribing the cores pays, up to about twice their number**: browser
tests wait more than they compute, and are safe in parallel (each daemon
binds port 0, each fixture has its own `tmp_path`, each worker its own
Chromium). Whole suite, four cores: `-n 4` 110 s, `-n 6` 96 s, `-n 8`
88 s, `-n 12` 107 s. Tests with no browser are CPU-bound and slower at
`-n 8` (25.5 s against 24.5 s), so CI runs the matrix at `-n auto`, the
browser shards at `-n 8`.

**A daemon a test serves polls at 0.05 s, not the default half second**:
`server.shutdown()` waits for `serve_forever`'s loop, 451 ms per serving
test (54 s of `test_serve.py`'s 79 s). `served`, `shot.py` and `stage.py`
pass `kwargs={"poll_interval": 0.05}`; `page_at` and any new serving
fixture are built on `served`, never on a `make_server` of their own. A
socket test that would wait five seconds for an answer sends
`Connection: close` (#280); one that waits for `LIST_FRESH` sets it to 0.

**Under `served`, git always says "main, clean"** (`stub_git` answers
`git_facts_many` so). A test about what git says hands the real
`git_facts` back in; the daemon reads again only after an event that
touches the tree, past `GIT_MIN_INTERVAL`: set that to 0 or clear
`git_read`, tick until the row holds the fact, then open the page; else
the test tests the stub (#607).
`test_a_merge_that_stopped_on_conflicts_counts_them_on_the_row`,
`test_a_worktree_git_has_not_finished_with_says_so`.

**A test that commits in a clone gives the clone an identity**: CI has no
global one and `git clone` drops the `user.email` the `repo` fixture set,
so the commit fails with status 128 in CI only. Run the suite once with
`GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1` when a test commits
somewhere new.

**A test that writes a fixed date hands the store that day as `now`**:
`store.refresh()` reads the clock and `forget_quiet` drops a session quiet
for `SESSION_MAX_AGE`, so `searched` in `tests/test_store.py`, with events
of 1 October, failed two weeks later with `KeyError:
's2'`, on `main` as on every branch. Use `store.refresh(now=day + ...)`.

**A hook test runs the hook under a stand-in `claude`** (`as_claude` in
`conftest.py`; `run_installed(["hook"], …)` does it): `agent_pid` walks up
to the first Claude Code, which under an agent is the agent, stdin a pipe,
so the hook dropped the pane (`reads_terminal`): red under an agent, green
in CI. The stand-in is a symlink `claude` to Python with a pty or pipe on
stdin (`keys`), so the hook finds the test's own agent.

**A fake of a call that never returns must raise** (`os.execv`,
`sys.exit`, `os._exit`): a recording fake lets the code run where it never
could. `test_update.py`'s `execv` fake in `cmd_install` ran on to
`bring_up_to_date`, which overwrote the fetched copy. Raise the test's own
exception (`Handed`) and expect it with `pytest.raises`.

**The suite does not cover failure; write the failing case yourself.** It
drives the happy path; of eight issues a full-file review filed, three were
a failed git call rendered as an answer, one a lock race between HTTP
threads, one a rotation race between hooks. When you change what calls
git, touches a file, or is reached from more than one thread, nothing else
will.

**Prove a test by breaking what it claims to guard, which is not always the
fix you wrote.** One test passed with its fix removed: another line saved
the state it asserted. One claimed `is_listed` is never cached but removed
the file with `git rm`, which deletes it from disk, so `target.is_file()`
refused the read whatever `is_listed` said;
stubbing `is_listed` to always say yes was the break. Ask what single
change should make it red; if you do not make that one, the test is about
something else.

**`tests/perturb.py` does the breaking.** Each break in its JSON list names
the tests it turns red, and only those run (a whole file cost 7 to 40 s a
break). It puts the file back after each, on Ctrl-C and on a `kill`. Read
its last line, not only its status: `GREEN` is a break no test saw;
"nothing ran" matched no test and passes for proof if unread. Keep the
breaks list in the scratchpad: it is about one fix.
- **`HUNG` is a test with no time limit, not a proof.** A break gets
  `timeout` seconds, 300 by default, then its tests are stopped and the
  file put back. A FIFO named like a skill hung the listing, the test and
  the run, and the `kill` then ran no `finally` and left the break in
`wostuast`.
  Give the test its own limit (a thread joined with a timeout, as
  `test_a_fifo_named_like_a_skill_is_not_listed`), so the break is red
  here and in CI. `test_a_break_that_hangs_a_test_is_put_back_and_said`,
  `test_a_kill_puts_the_file_back`.
- **`perturb.py` proves red, never green: run a test green again after any
  edit to it.** #524's hex test, tidied after passing, read text before the
  hex was drawn, and perturb said 4 of 4 red, as for any broken test. Edit,
  run green, then perturb.
- **It deletes the file's bytecode after every write** (`forget_bytecode`):
  Python reuses a `.pyc` while mtime in whole seconds and size match, so
  `SEND_MAX = 12000` then `POST_MAX = 64 * 1024` in one second ran the
  first break's code and said GREEN for the second (#328). **A GREEN that
  is red alone is this, or a test leaning on another: run that break alone
  before believing either.** `test_no_bytecode_of_a_break_is_left_behind`.
- **A GREEN may be a break the new code cannot reach: put the old code
  back whole.** After #566 moved the whole-file fetch to `askWhole`
  (called by `revealLines` before drawing), `fetchWhole` put back into
  `withMore` stayed green, since a whole file was always held; the old
  lines in full, the stale-file delete too, turned five tests red. A break
  is a regression somebody could write, not the smallest edit.
  - **Two edits are one break when the old code was both**: `perturb.py`
    takes one edit a break, so apply both by hand, run, and restore from a
    copy made first. #573's draw reset of the picks alone stayed green, as
    `fitPicks` had run; #577's stayed green with `fitPicks` gone from
    `onSessions`, since `choose()` calls it too, and went red with both.
    Put back all the old code lacked.
  - **The draw guard is installed before the page's first draw, not after
    `opened`** (#577): after, it missed a question drawn at load, and the
    old reset in `drawAsking` passed. `DRAW_GUARD` is an init script of
    every context (`fresh_context`), installing itself at the page script's
    first top-level `addEventListener`: before that the draws are
    undefined, and a function declaration replaces a wrapper set under its
    name. A function a test replaces after load is not watched.
- **A GREEN may be code nothing needs: delete the code, add no test.** A
  break removing the list of gone rows from a push stayed green: it said
  what the order says (a row that goes
  moves the order, which the page builds from, #431), so `gone` went. Ask
  whether any input could tell the two apart; a break no input can see is
  the same program (a new call never carries a kept id, #430): drop it.
  - **Code that only makes a thing come sooner is tested inside a window
    shorter than what it shortcuts**: `respace` refetches the diff when the
    whitespace setting changes, but the poll does within five seconds, so a
    wait for the diff stayed green (#449). `page.expect_request` with a
    1.5 s timeout around the click tells them apart.
    - **An observer is such a later path, and its green is chance**:
      `gripWatch`, a `ResizeObserver`, redraws the grip a frame later, so a
      break of `openGrip` in `openFeed` was green once, the call was
      deleted, and the test, reading the grip before the observer fired, went
      red next run (#471). Before deleting a call as dead, ask whether
      something async does it later, and run the break three times: a green
      that holds once is no proof.
  - **`tests/page_coverage.py` asks the same of the whole page script**
    (#439): it runs the browser tests with `WOSTUAST_COVERAGE`, and `cover`
    in `tests/browser.py` has Chromium count, by the DevTools protocol,
    what each page ran. Its first run named `nextTheme`, an alert's
    `onclick`, `fromShebang`: none dead, each untested. A function it names
    is dead code or a missing test; ask which first. On the tool: `cover`
    wraps the context's `new_page`, as counting must start before the
    script runs; V8 names an arrow after its holder, so a name counts only
    on the function's own line; it is not `coverage.py`, which would shadow
    the package on pytest's path. `test_page_coverage.py`.
    - **It is a ratchet in CI** (#579): `--check` fails on an unrun named
      function not in `UNRUN_ALREADY`, an entry that runs now, or a run
      that recorded nothing. The list started empty. The reader chose its
      cost in the shards (2.5 min a shard either way in CI, #590; 70 %
      slower locally) over an unrequired job of its own. **It counted
      functions, not the branches in them. So it counts lines too** (#600):
      functions missed a write to `state.diffs.loose` in
      `drawDiff` behind an untaken `if`, with `DRAW_EFFECTS_ALREADY` empty,
      found by `/simplify` reading: the draw guard sees only what runs, so
      a rare branch's write is found by reading and gets a test that takes
      it (#596,
      `test_an_untracked_file_picked_and_then_added_lets_go_of_the_pick`).
      Each unrun line is the innermost named function's
      (`unrun_by_function`) or `(top level)`'s; `--check` names lines past
      `UNRUN_LINES_ALREADY`, which started empty (#604 to #607). An entry
      is only for a line that runs by a run's timing, at most what three
      whole-suite runs left, with why (the "blocking alerts" note in
      `drawBell` ran by which context a run made, until a test asked for
      it).
      - **Three green runs do not prove a line is run on purpose**: the one
        test of Escape in the find box reached it only before the Files
        tab's hits came, and the list takes Escape once they have (#609). A line red in CI gets its own test before
        it is ever an allowance:
        `test_esc_in_the_find_box_empties_it_and_leaves_it`.
      A new page function needs a test that runs it, or an entry with why.
    - **A branch no test runs is not dead because two tries missed it**
      (#600): `fillDiffBar`'s option for a pick the list does not name was
      deleted as unreachable, yet a failed git answer on returning to a
      session keeps the pick (`loadDiff`) and draws with no list, and the
      picker read "all changes". List every writer of the state a branch
      reads and try each in the real page;
      `test_a_commit_picked_is_named_when_git_does_not_answer_on_the_way_back`.
- **`page.evaluate` is not strict, and the page's script is**: a throw on
  writing a frozen session vanished in an `evaluate` (#435). Start a probe
  with `"use strict";`.
- **A GREEN on a style read after a click may be the hover's style**: the
  pointer stays, and `:hover` (`--edge-bright`) stood in for the broken
  rule (#396). `page.mouse.move` to an empty spot first.
- **A pointer that jumps from an element the page replaced leaves
  nothing**: `page.mouse.move` off a form that replaced "Custom…" fired no
  `mouseleave`, so a close-on-leave break passed (#406). `page.hover` the
  new content, then move away.
- **A filtered run that prints nothing has not run**: a usage error
  (`--count 3`, an uninstalled plugin's flag) left
  `pytest ... | grep -E "passed|failed"` empty. Filter for `error` too, or
  read the exit status.

**A test outside `tests/test_page_*` that drives a browser, or runs
`tests/shot.py`, `tests/stage.py` or `tests/tour.py`, carries
`@skip_without_browser`**: only CI's browser shards have Playwright, so a
desk never shows it missing
(`test_eval_runs_in_the_page_before_the_picture` was red in CI on all
four Pythons). To see CI's view, put a `playwright/__init__.py` that raises
`ImportError` in a scratchpad folder on `PYTHONPATH`: every browser test
must skip, none fail.

**Measure position with `getBoundingClientRect`, never `offsetTop`**:
inside a positioned `.turn` it counts from the turn, so a scroll never
moved the pane and its break went GREEN. **A scroll test needs content
after what it scrolls past**, or the browser cuts the scroll back and the
target is in sight by chance
(`test_folding_from_the_foot_of_the_pane_keeps_the_message_in_sight`).

**Playwright.**
- **`fill` with a long many-line text takes for ever** (60 KB: over 60 s,
  the page's handler 10 ms): set `value` in `evaluate` and send one
  `input` event, as a paste does
  (`test_a_tall_send_box_says_how_much_it_holds`).
- A hover-only control (`.plus`) needs `click(force=True)`.
- **Wait for what the page has drawn, never a number of seconds**: a
  loaded runner draws later. A fixed wait only proves something did
  **not** happen: `stays(page, ms)` (#598). A frame a `ResizeObserver` or
  scroll handler needs is `frames(page)`, not 100 ms.
  `test_a_browser_test_waits_a_time_only_to_prove_nothing_comes` fails on a
  `wait_for_timeout` in a page test.
- **A wait for an appearance asks for what was not there before the
  action**: the Files tab opens on `README.md`, so `.filebody .prose` after
  clicking `NOTES.md` held at once; the Transcript tab has a `.filelist`
  too (`.filelist.transcript`), so after `2` wait for `.filelist.files`. A
  fixed 700 ms hid both until the whole suite. `NOTES_SHOWN` in
  `test_page_files.py`.
- Ask one question when a redraw could land between two:
  `wait_for_function("...length === 1")`, not `wait_for_selector` then
  `.count()`.
- **`evaluate` waits for a promise it is handed, with no timeout**:
  `page.evaluate("load()")` on a held request hung. Use
  `"() => { load(); }"`.
- One route handler holds the first request and answers the rest; never
  `unroute` with one held — it answers the held one itself. **That handler
  and its wait are `hold(page, pattern)` and `wait_until(page,
  check)` in `tests/browser.py`, never a copy**: copied loops
  (`for _ in range(300): if held: break`) fell through into `held[0]`, an
  `IndexError` naming no wait; `wait_until` raises on time-out. Likewise
  `stub_send(page, answers, delay)` (`/send` from a list, or with no
  `answers` slowed and passed on), `write_records` (lines from
  `conftest.record`), `comment_on_first_line` (#281).
- **A route handler runs only while Playwright waits**: `kept()` polling
  `settings.json` in Python starved the `hold` handler of the second POST.
  `page.expect_response(...)` first, then read the file, as
  `test_two_quick_changes_reach_the_file_in_the_order_they_were_made`.
- **A reload after a setting waits for `kept()` first**: the page writes a
  choice by a POST it does not wait on, and a reload before it lands loses
  it (#385,
  `test_the_tab_width_and_wrap_are_the_readers_and_are_remembered`; without
  the POST the reload shows the old value).
- **A mark shown for a set time is written down by the page, not waited
  for**: under load
  `test_a_code_block_copies_itself_from_a_button_that_shows_on_hover` missed
  the 1.4 s tick (`putCodeCopies`, `.copycode.done`). A `MutationObserver`
  set before the click keeps `window.__done`; wait for that.

**A change a stream test expects goes out after the first event, never
after a sleep**: `test_a_change_is_pushed` changed state 0.3 s after
connecting, and on a loaded runner the stream opened after the push and
waited for a second event. `read_events(..., then=change)` changes once
the first event is in; `stream` joins the hub before writing it, so
nothing after is lost. **A stream test that floods waits for its first
push to arrive**:
`test_a_stream_too_slow_to_keep_up_is_closed_and_never_given_a_gap`
pushed 60 before a starved stream thread ran, the queue filled, the stream
rightly closed with nothing written, and `numbers` was empty (#363; a
first `queue.get` delayed 2 s reproduces it). Push one, read it, then
flood.

**Two loaded runs at once find what CI shows now and then**:
`(python3 -m pytest -q -n 12 -rf F) & (python3 -m pytest -q -n 12 -rf F); wait`
failed in two rounds a test one run passed five times, and found a push
before the stream listened, a "slow" one-second daemon, a reminder three
seconds out. Do it before calling red luck, and on `main`, to tell whose.
- **A rule turned round has tests of the old one in other files: grep them
  all before the gate.** After #351 reversed "the row shows its place,
  never Claude Code's title", `test_the_page_draws_the_session` in another
  file still asserted it. `grep -rn` the old rule's words over `tests/`
  -- its value ("A session"), its comments' phrases ("not the row's",
  "never reaches") -- when the rule is rewritten, not when CI goes red.
  - **A count in the page's own words is an old rule too**: the fourth tab
    (#367) made "1 – 3" "1 – 4", and `test_the_keys_nobody_pressed_are_gone`
    asserted "1 – 3". Grep the page's words, not only the code's names.
    **Read every line the grep prints**: `| head` hid `test_page_tabs.py`
    counting four tabs (#411); `grep -c` or `-l` first, then each file.
    **A setting added to the menu is such a count**: two for #449 broke
    `test_the_settings_say_what_is_chosen_and_change_it_in_place` (the
    pressed choices, listed) and
    `test_every_settings_label_stands_level_with_what_it_names`
    (`len(gaps)`); run both after a change to `putSettings`.
- **No test reaches the tmux it runs under.** `ws` points `TMUX` at a
  socket in the test's folder with no server; a plain `tmux` talks to the
  server `TMUX` names. Not `TMUX_TMPDIR`: a socket path under `tmp_path`
  was too long for `test_tmux.py`'s server. Page tests rename in pane
  `%1` (`conftest.event`'s default), typing `/rename` (#351): inside the
  owner's tmux, `/rename …` went into their real `%1`. A test that wants a real
  tmux starts its own with `-L` and sets `TMUX` after `ws`, as
  `test_tmux.py`. **`tests/stage.py` and `tests/shot.py` set it too**: they
  serve `%7` without `ws`, and a `--type '#say=…'` reached the reader's
  `%7`. `test_no_test_reaches_the_tmux_it_runs_under`,
  `test_it_types_into_no_real_tmux`.
  - **Nor the real state directory: never `monkeypatch.undo()` in a test
    that uses `ws`**: `ws` patches the state through the same
  `monkeypatch`, and `undo()` takes back every patch, so
    `test_the_fold_does_no_io` wrote
    `~/.local/state/wostuast/names.json` (#546). Use
    `with monkeypatch.context() as io:`.
- **A page hears a change only from `daemon.tick()`;
  `daemon.store.refresh()` folds it and tells nobody**: a test that
  refreshed waited out its timeout for a push the daemon held (#422).
  Refresh before the page opens, tick after.
- **A deadline in the code under test starts after the page is open**:
  `test_yes_and_dont_ask_again_is_a_choice_of_its_own` started the hook
  (`wait_for_yes`) before `opened`, a loaded runner spent `APPROVE_WAIT`
  opening the page, and `wait_until(page, lambda: ws.hook_waits(ask))` was
  never true (#569; `test_yes_shows_while_the_hook_waits_and_goes_to_it`
  started it inside the `with`). Start a thread with its own deadline
  inside `opened`.
  - **And end it with the test**: the `asking` fixture of
    `tests/test_approve.py` left `wait_for_yes` waiting out a 20 s
    `APPROVE_WAIT` into the next tests, where
    `test_it_waits_for_the_state_to_come` patches `time.sleep` to not sleep
    and the old thread spun into twenty of its "steps" (#584). The teardown
    writes the hook's Yes and asserts the thread is gone.
- **In a browser test, `wait_for_watching(daemon)` comes before the first
  `daemon.tick()`**: `open_page` and `wait_for_map` prove the fetch
  answered, not that the stream listens; `showTab` fetches *then*
  subscribes, a tick between pushes to nobody, and nothing ticks again;
  these went red under load (`test_a_search_keeps_its_place_while_the_agent_works`,
  `test_the_top_of_the_transcript_is_a_place_too`,
  `test_a_rewritten_transcript_replaces_the_page_rather_than_doubling_it`).
  **A `daemon.hub.send` is that push too**
  (`test_only_a_block_that_has_just_arrived_slides_in`, #373). A test of
  what happens while nobody listens leaves the wait out, and says so.

**A page test opens its page with `with opened(where) as page:`, never by
hand**: hand-written `sync_playwright`, `open_page`, `try` and
`finally: browser.close()` nested every body, and a forgotten `close`
leaked a context (#283). `opened` closes it whatever the block raised;
`tab="diff"` opens the Review tab at its first line. A second page is
`page.context.new_page()`. A test that needs the context first (a
permission, an init script, a held route) takes
`with own_context() as context:`, then `context.new_page()` and
`load(page, where)`.

**`open_page` returns once the transcript has answered; `show_tab` is not
the tab's content arriving.** `open_page` waits for `state.turns.landed`
(blocks, none, or a failure), since reading `.turnbody` at the first frame
went red under load; `wait="frame"` opts out, for a test of the page
before that answer (needed when the request is held before the page opens,
or it waits for ever). `show_tab` waits only for the frame (the Files
tab's document fills one fetch later); `wait_for_map(page, rows)` waits for
rows. Otherwise wait for what the page has *written down*, not the DOM: a
scroll writes `state.files.down` a frame after the scroller moves, and a
session switch in between saved the top.
`test_open_page_returns_once_the_transcript_has_answered` slows the answer
three seconds (one was shorter than a first frame under two loaded runs).

- **An empty send box is the send starting, not landing**: `sendTyped`
  empties `#say` with the Enter, before the POST, so words typed meanwhile
  survive (topics/safety-typing, "One send at a time").
  `test_the_enter_that_ends_a_composition_sends_nothing` read the fake
  tmux's `seen` after the empty box, before the `send-keys` came (holding
  `**/send` 300 ms makes it red every time). Wait for the keys in `seen`
  (`wait_until`), then `sending.size === 0`: the lock goes in the same turn
  that puts a refused text back. `test_the_send_box_types_into_the_terminal`
  waits so too. Conversely, a box still full right after a composing Enter
  proves nothing was sent, with no sleep.

**To hold what a key *says*, spy on `note`, not on `#live`**: the slot is
repainted on every push and may lose a passing word, so reading it races.
A `note` reassigned to keep every word holds both that the key is bound to
what speaks and what it said; calling the function proves only the second.
`spy_on_note(page)` in `tests/browser.py` keeps them in `window.__said`.
**A refusal is not a note**: `said(answer)` writes `state.trouble`, which
`spy_on_note` never sees; wait for `state.trouble`.

**Read the live slot in the same `evaluate` that writes it**: `note()`
borrows it and every push repaints it (one painter), so a
`wait_for_function` for the word can wait out its timeout. JavaScript is
single-threaded: no push lands inside one `evaluate`.

**This scar keeps coming back: recognise its shape, not its names.** A test
reads `.turn`, `.prose`, `.who`, `state.turns.blocks` or the find box on
the line after the page opened, passes alone, and goes red under load:
- an empty list read as "it drew nothing";
- `null.isConnected` or `undefined.ts` thrown out of an `evaluate`;
- a key that reached the page, not the find box: `split` moves the box
  when the transcript lands, and a moved box loses focus;
- a fixture's clock read after opening: `ago` counts seconds only in the
  first minute, so `test_a_row_is_not_rebuilt_every_second` read "1min"
  twice on a slow open, and now starts the count with a fresh event;
- the last session's drawing still in the pane after `choose`: `open_file`
  found the old scroller's lines and scrolled another session's listener;
  wait for `.filescroll[data-drawn="<session>"]`. The Review tab too:
  `test_another_sessions_diff_is_read_from_its_top` waits for a file only
  the new session changed.
Three runs at `-n 12` of the files you changed turn them up; one is not
enough.
