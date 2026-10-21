# Writing a test that holds

How a test waits, why it goes red under load, and how to prove it guards.

**Run browser tests at up to twice the cores**: they wait more than they
compute, and are safe in parallel (port 0, own `tmp_path`, own Chromium).
On four cores the suite took 110 s at `-n 4`, 88 s at `-n 8`, 107 s at
`-n 12`. Tests with no browser are CPU-bound, so CI runs the matrix at
`-n auto`, the browser shards at `-n 8`.

**A daemon a test serves polls at 0.05 s**: `server.shutdown()` waits for
`serve_forever`'s loop, 451 ms a test at the default (54 s of
`test_serve.py`'s 79). `served`, `shot.py` and `stage.py` pass
`kwargs={"poll_interval": 0.05}`; any new serving fixture, as `page_at`,
is built on `served`, never on a `make_server`. A socket test sends
`Connection: close` rather than wait for an answer (#280); one that waits
for `LIST_FRESH` sets it to 0.

**Under `served`, git always says "main, clean"** (`stub_git` answers
`git_facts_many`). A test about git hands the real `git_facts` back in,
sets `GIT_MIN_INTERVAL` to 0 or clears `git_read`, ticks until the row
holds the fact, then opens the page; else it tests the stub (#607).
`test_a_merge_that_stopped_on_conflicts_counts_them_on_the_row`,
`test_a_worktree_git_has_not_finished_with_says_so`.

**A test that commits in a clone gives the clone an identity**: CI has no
global one, and `git clone` drops the `user.email` the `repo` fixture set,
so the commit fails in CI only. When a test commits somewhere new, run it
once with `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1`.

**A test that writes a fixed date hands the store that day as `now`**:
`store.refresh()` reads the clock, and `forget_quiet` drops a session
quiet for `SESSION_MAX_AGE`; `searched` in `tests/test_store.py` failed
two weeks after its date. Use `store.refresh(now=day + ...)`.

**A hook test runs the hook under a stand-in `claude`** (`as_claude` in
`conftest.py`, used by `run_installed(["hook"], …)`): `agent_pid` walks up
to the first Claude Code, under an agent one with stdin a pipe, so the
hook dropped the pane (`reads_terminal`). The stand-in is a symlink
`claude` to Python with a pty or pipe on stdin (`keys`).

**A fake of a call that never returns must raise** (`os.execv`,
`sys.exit`, `os._exit`): `test_update.py`'s recording `execv` fake let
`cmd_install` run on to `bring_up_to_date`. Raise the test's own
exception (`Handed`) and expect it with `pytest.raises`.

**The suite does not cover failure; write the failing case yourself.**
Most bugs a review of the whole file found were a failed git call shown
as an answer, or a race. When you change what calls git, touches a file,
or runs on more than one thread, nothing else will.

**Prove a test by breaking what it claims to guard, which is not always
the fix you wrote.** A test that `is_listed` is never cached removed the
file with `git rm`, so `target.is_file()` refused anyway; the break was
`is_listed` always saying yes. Ask what single change should make it red.

**`tests/perturb.py` does the breaking.** Each break in its JSON list
names the tests it turns red, and only those run. It puts the file back
after each, and on Ctrl-C or a `kill`. Read its last line: `GREEN` is a
break no test saw; "nothing ran" matched no test. Keep the list in the
scratchpad.
- **`HUNG` is a test with no time limit, not a proof.** A break gets
  `timeout` seconds (300); a `kill` after a hang ran no `finally` and left
  the break in `wostuast`. Give the test its own limit, as
  `test_a_fifo_named_like_a_skill_is_not_listed` joins a thread.
  `test_a_break_that_hangs_a_test_is_put_back_and_said`,
  `test_a_kill_puts_the_file_back`.
- **`perturb.py` proves red, never green: run a test green again after any
  edit to it.** A broken test is red for every break (#524).
- **It deletes the file's bytecode after every write**
  (`forget_bytecode`): Python reuses a `.pyc` while mtime in whole seconds
  and size match, so `SEND_MAX` then `POST_MAX` broken in one second ran
  the first break's code (#328). **A GREEN that is red alone is this, or a
  test leaning on another: run that break alone before believing either.**
  `test_no_bytecode_of_a_break_is_left_behind`.
- **A GREEN may be a break the new code cannot reach: put the old code
  back whole.** After #566 moved the fetch to `askWhole` (`revealLines`),
  `fetchWhole` put back into `withMore` stayed green; the old lines in
  full went red. A break is a regression somebody could write.
  - **Two edits are one break when the old code was both**: `perturb.py`
    takes one edit a break, so apply both by hand and restore from a copy.
    #577's stayed green with `fitPicks` gone from `onSessions`, since
    `choose()` calls it too (#573).
  - **The draw guard is installed before the page's first draw, not after
    `opened`** (#577): after, it missed `drawAsking` at load. `DRAW_GUARD`
    is an init script of every context (`fresh_context`) that installs
    itself at the page script's first top-level `addEventListener`;
    earlier, a function declaration would replace its wrapper. A function
    a test replaces after load is not watched.
- **A GREEN may be code nothing needs: delete the code, add no test**,
  when no input could tell the two apart: a push's list of `gone` rows
  said what the order says (#430, #431).
  - **Code that only makes a thing come sooner is tested inside a window
    shorter than what it shortcuts**: `respace` refetches the diff, which
    the poll does within five seconds (#449); `page.expect_request` with a
    1.5 s timeout tells them apart.
    - **An observer is such a later path, and its green is chance**:
      `gripWatch`, a `ResizeObserver`, redraws the grip a frame later, so
      a break of `openGrip` in `openFeed` was green once (#471). Ask what
      async path does it later, and run the break three times.
  - **`tests/page_coverage.py` asks the same of the whole page script**
    (#439): with `WOSTUAST_COVERAGE`, `cover` in `tests/browser.py` has
    Chromium count what each page ran. A function it names (`nextTheme`,
    an alert's `onclick`, `fromShebang`) is dead code or a missing test;
    ask which. `cover` wraps `new_page`, to count before the script runs.
    V8 names an arrow after its holder, so a name counts only on its own
    line. Not `coverage.py`: that would shadow the package.
    `test_page_coverage.py`.
    - **It is a ratchet in CI** (#579, its cost in the shards chosen in
      #590): `--check` fails on an unrun function not in `UNRUN_ALREADY`,
      an entry that runs now, or a run that recorded nothing. **It counts
      lines too** (#600): counting functions missed a write to
      `state.diffs.loose` in `drawDiff` behind an untaken `if`. The draw
      guard (`DRAW_EFFECTS_ALREADY`) sees only what runs, so a rare
      branch's write is found by reading (`/simplify`) and gets a test
      (#596,
      `test_an_untracked_file_picked_and_then_added_lets_go_of_the_pick`).
      An unrun line is its innermost function's (`unrun_by_function`) or
      `(top level)`'s; `--check` names lines past `UNRUN_LINES_ALREADY`
      (#604 to #607). An entry is only for a line that runs by timing, at
      most what three whole-suite runs left, with why (as in `drawBell`).
      A new page function needs a test that runs it, or an entry with why.
      - **Three green runs do not prove a line is run on purpose** (#609):
        a line red in CI gets its own test before it is ever an allowance:
        `test_esc_in_the_find_box_empties_it_and_leaves_it`.
      - **Patch for a while with `monkeypatch.context()`, never
        `monkeypatch.undo()`** (#624): the fixtures share the test's
        `monkeypatch`, and `undo` took theirs too; the daemon then lost its
        session, and a check after it passed by chance in #616.
      - **What a page ran before `page.reload()` may not count** (#625):
        `cover` takes the coverage as the context closes, and the old
        script's counts go once V8 collects it. A loaded CI runner does; a
        quiet machine may not, so it passed here and failed in CI, twice.
        Keep what a test means to cover on the page it ends on, and check
        what the browser keeps by reading `localStorage`, not by a reload.
    - **A branch no test runs is not dead because two tries missed it**
      (#600): `fillDiffBar`'s option for an unlisted pick looked
      unreachable, yet `loadDiff` keeps the pick when git fails. Try every
      writer of the state a branch reads in the real page;
      `test_a_commit_picked_is_named_when_git_does_not_answer_on_the_way_back`.
- **`page.evaluate` is not strict, and the page's script is**: a throw on
  writing a frozen session vanished (#435). Start a probe with
  `"use strict";`.
- **A GREEN on a style read after a click may be the hover's style**
  (`--edge-bright`, #396). `page.mouse.move` to an empty spot first.
- **A pointer that jumps from an element the page replaced fires no
  `mouseleave`** (#406). `page.hover` the new content, then move away.
- **A filtered run that prints nothing has not run**: a usage error
  leaves `grep -E "passed|failed"` empty. Filter for `error` too, or read
  the exit status.

**A test outside `tests/test_page_*` that drives a browser, or runs
`tests/shot.py`, `tests/stage.py` or `tests/tour.py`, carries
`@skip_without_browser`**: only CI's browser shards have Playwright
(`test_eval_runs_in_the_page_before_the_picture`). To see CI's view, put
a `playwright/__init__.py` that raises `ImportError` on `PYTHONPATH`:
every browser test must skip.

**Measure position with `getBoundingClientRect`, never `offsetTop`**: in
a positioned `.turn` it counts from the turn, and a broken scroll went
GREEN. **A scroll test needs content after what it scrolls past**, or the
browser cuts the scroll back
(`test_folding_from_the_foot_of_the_pane_keeps_the_message_in_sight`).

**Playwright.**
- **`fill` with a long many-line text takes for ever** (60 KB: over
  60 s): set `value` in `evaluate` and send one `input` event
  (`test_a_tall_send_box_says_how_much_it_holds`).
- A hover-only control (`.plus`) needs `click(force=True)`.
- **Wait for what the page has drawn, never a number of seconds.** A fixed
  wait only proves something did **not** happen: `stays(page, ms)`
  (#598). A frame a `ResizeObserver` or scroll handler needs is
  `frames(page)`. `test_a_browser_test_waits_a_time_only_to_prove_nothing_comes`
  fails on a `wait_for_timeout` in a page test.
- **A wait for an appearance asks for what was not there before the
  action**: after a click on `NOTES.md`, `.filebody .prose` held at once,
  from `README.md`; after `2`, wait for `.filelist.files`, as
  `.filelist.transcript` exists too. `NOTES_SHOWN` in `test_page_files.py`.
- Ask one question when a redraw could land between two:
  `wait_for_function("...length === 1")`, not `wait_for_selector` then
  `.count()`.
- **`evaluate` waits for a promise it is handed, with no timeout**:
  `page.evaluate("load()")` on a held request hung. Use
  `"() => { load(); }"`.
- One route handler holds the first request and answers the rest; never
  `unroute` with one held: it answers the held one itself. **Use
  `hold(page, pattern)` and `wait_until(page, check)` in
  `tests/browser.py`, never a copy**: a copied loop fell through into an
  `IndexError` naming no wait. Likewise `stub_send(page, answers, delay)`
  for `/send`, `write_records`, `comment_on_first_line` (#281).
- **A route handler runs only while Playwright waits**: `kept()` polling
  `settings.json` from Python starved `hold`. `page.expect_response(...)`
  first, then read the file
  (`test_two_quick_changes_reach_the_file_in_the_order_they_were_made`).
- **A reload after a setting waits for `kept()` first**: the page does not
  wait on the POST that writes a choice (#385,
  `test_the_tab_width_and_wrap_are_the_readers_and_are_remembered`).
- **A mark shown for a set time is recorded by the page, not waited for**:
  under load
  `test_a_code_block_copies_itself_from_a_button_that_shows_on_hover`
  missed the 1.4 s tick (`putCodeCopies`, `.copycode.done`); a
  `MutationObserver` set before the click keeps `window.__done`.

**A change a stream test expects goes out after the first event, never
after a sleep**: a loaded runner opened the stream of
`test_a_change_is_pushed` after the push. `read_events(..., then=change)`
changes once the first event is in; `stream` joins the hub before writing
it. **A stream test that floods waits for its first push**: a starved
stream thread lets the queue fill, and the stream rightly closes empty
(#363, a slow first `queue.get`,
`test_a_stream_too_slow_to_keep_up_is_closed_and_never_given_a_gap`).

**Two loaded runs at once find what CI shows now and then**:
`(python3 -m pytest -q -n 12 -rf F) & (python3 -m pytest -q -n 12 -rf F); wait`.
Do it before calling red luck, and on `main`, to tell whose.
- **A rule turned round has tests of the old one in other files: grep
  them all before the gate.** After #351, `test_the_page_draws_the_session`
  still asserted the old rule. `grep -rn` its values and its comments'
  phrases over `tests/`.
  - **A count in the page's own words is an old rule too**
    (`test_the_keys_nobody_pressed_are_gone`, #367). **Read every line the
    grep prints**: `| head` hid `test_page_tabs.py` (#411). **A setting
    added to the menu is such a count** (#449): after a change to
    `putSettings`, run
    `test_the_settings_say_what_is_chosen_and_change_it_in_place` and
    `test_every_settings_label_stands_level_with_what_it_names`
    (`len(gaps)`).
- **No test reaches the tmux it runs under.** `ws` points `TMUX` at a
  socket with no server in the test's folder (not `TMUX_TMPDIR`: too long
  a path for `test_tmux.py`). Page tests type `/rename` into pane `%1`
  (`conftest.event`'s default, #351), real inside the owner's tmux. A
  test that wants a real tmux starts its own with `-L` and sets `TMUX`
  after `ws`. **`tests/stage.py` and `tests/shot.py` set it too**: their
  `--type` reached the reader's `%7`.
  `test_no_test_reaches_the_tmux_it_runs_under`,
  `test_it_types_into_no_real_tmux`.
  - **Nor the real state directory: never `monkeypatch.undo()` in a test
    that uses `ws`**: `undo()` takes back `ws`'s patches too, so
    `test_the_fold_does_no_io` wrote `~/.local/state/wostuast/names.json`
    (#546). Use `with monkeypatch.context() as io:`.
- **A page hears a change only from `daemon.tick()`, not
  `daemon.store.refresh()`** (#422). Refresh before the page opens, tick
  after.
- **A deadline in the code under test starts after the page is open**: a
  loaded runner spent `APPROVE_WAIT` opening the page after
  `test_yes_and_dont_ask_again_is_a_choice_of_its_own` started
  `wait_for_yes` (#569). Start the thread inside `opened`, as
  `test_yes_shows_while_the_hook_waits_and_goes_to_it`.
  - **And end it with the test**: the `asking` fixture of
    `tests/test_approve.py` left `wait_for_yes` running into
    `test_it_waits_for_the_state_to_come` (#584). Its teardown writes the
    Yes and asserts the thread is gone.
- **In a browser test, `wait_for_watching(daemon)` comes before the first
  `daemon.tick()`**: `open_page` and `wait_for_map` do not prove the
  stream listens; `showTab` fetches *then* subscribes
  (`test_a_search_keeps_its_place_while_the_agent_works`,
  `test_the_top_of_the_transcript_is_a_place_too`,
  `test_a_rewritten_transcript_replaces_the_page_rather_than_doubling_it`).
  **A `daemon.hub.send` is that push too**
  (`test_only_a_block_that_has_just_arrived_slides_in`, #373). A test of
  what happens while nobody listens leaves the wait out, and says so.

**A page test opens its page with `with opened(where) as page:`, never by
hand**: a hand-written `sync_playwright` leaked a context when its
`close` was forgotten (#283). `tab="diff"` opens the Review tab; a second
page is `page.context.new_page()`. A test that needs the context first (a
permission, an init script, a held route) takes
`with own_context() as context:`, `context.new_page()` and
`load(page, where)`.

**`open_page` returns once the transcript has answered; `show_tab` is not
the tab's content arriving.** `open_page` waits for `state.turns.landed`
(`.turnbody` at the first frame went red); `wait="frame"` opts out, as a
request held before the page opens needs. `show_tab` waits only for the
frame, `wait_for_map(page, rows)` for rows. Else wait for what the page
has *written down*, such as `state.files.down`, not the DOM.
`test_open_page_returns_once_the_transcript_has_answered`.

An empty send box is the send starting, not landing: topics/send-and-keys
says how a test of a send waits.

**Never wait on the live slot: every push repaints it** (`paintLive`;
`note()` borrows it), so a word may be gone before a `wait_for_function`
sees it.
- **To hold what a key *says*, spy on `note`, not on `#live`.** A
  reassigned `note` proves that the key is bound to what speaks and what
  it said; calling the function proves only the second.
  `spy_on_note(page)` in `tests/browser.py` keeps the words in
  `window.__said`.
  **A refusal is not a note**: `said(answer)` writes `state.trouble`;
  wait for that.
- **To read the slot itself, read it in the same `evaluate` that writes
  it**: no push lands inside one `evaluate`.

**This scar keeps coming back: recognise its shape, not its names.** A
test reads `.turn`, `.prose`, `.who`, `state.turns.blocks` or the find
box on the line after the page opened, passes alone, and goes red under
load:
- an empty list read as "it drew nothing";
- `null.isConnected` or `undefined.ts` thrown out of an `evaluate`;
- a key that reached the page, not the find box: `split` moves the box
  when the transcript lands, and a moved box loses focus;
- a fixture's clock read after opening: `ago` counts seconds only in the
  first minute (`test_a_row_is_not_rebuilt_every_second`);
- the last session's drawing, still in the pane after `choose`, found by
  `open_file`: wait for `.filescroll[data-drawn="<session>"]`, or for a
  file only the new session changed
  (`test_another_sessions_diff_is_read_from_its_top`).
Three runs at `-n 12` of the files you changed turn them up; one is not
enough.
