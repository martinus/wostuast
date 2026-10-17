# The daemon and the page

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. Routes, polling, the stream and its pushes, the tab frame, the find box, the context bar and the live slot.

- **Every route lives in `Serving`**, a module-level class that subclasses
  nothing. `make_server` mixes it with `BaseHTTPRequestHandler` and puts the
  daemon on that subclass, so a route reads `self.daemon`. The `http.server`
  import stays inside `make_server`: 10.8 ms for a bare interpreter against
  49.5 ms for one that has imported it, and **the hook pays for every import
  on every tool call**. `test_the_hook_does_not_import_what_it_does_not_need`
  fails if that slips.
- **Never write to the terminal** except through the four tmux verbs:
  `tmux_jump`, `tmux_send`, `tmux_interrupt` and `tmux_keys`. Each looks
  `run` up when called rather than taking it as a default, so a test can
  put a fake tmux in its place.
- **The Files and Diff tabs poll from the browser, and only while on screen.**
  `TABS` holds one entry per tab — draw, load, interval — so a new tab is one
  entry, not six edits. The daemon pushes the transcript and nothing else; it
  does not know which tab a browser is on, and that is why `Hub` stays small.
- **One lock around the transcript readers.** Two `read_new` calls at once move
  the byte offset twice, which looks like a shrinking file. **The push goes
  out under it too**: sent after the lock let go, a request thread's block 2
  could overtake the tick's block 1, and the page, which patches by index,
  never drew block 1. `Hub.send` only queues, so nothing waits on a socket
  there. `test_a_transcript_push_leaves_under_the_lock`.
- **There is one find box, and it must leave before its parent is cleared.** On a
  split tab it lives inside the content box, so a tab that empties that box
  destroys it and `$("find")` is null — `showTab` then throws before `load` and
  the page is broken until a reload. `draw()` takes it home when
  `box.dataset.tab` says another tab owns the box; `split()` takes it back. Two
  outages; `test_every_way_from_one_tab_to_another_works` watches for a third.
- **Ask the box which tab it holds, not `state.tab`.** `showTab` sets the name
  and then awaits `load()`, and for that whole await the box still holds the
  tab before it. A transcript push landing in the gap appended a turn as a
  fourth column of the Files tab. `draw()` had this right already.
- **A session can be chosen before the session list exists.** The address bar
  holds a link at startup, so `choose` runs with `state.sessions` empty —
  `current()` is null and every tab draws its empty state. The `sessions`
  event draws again when the chosen session turns out to be real; without
  that, a linked page stayed empty until the reader clicked a row.
- **Each push has a handler of its own**, `onSessionsPush` and
  `onTranscriptPush` (#544): `resubscribe` opens the stream and nothing
  more. It held all three inline and was past the 100-line limit.
- **A row of a list is one line, and `.filelist button` is a block.** A
  list whose rows are one line says so in the one rule that groups them —
  `.fixed` for the file tree, `.diff` for the Diff tab's tree, `.transcript`
  for the map. Without it the icon sits on a line of its own above the text,
  which is how the map first shipped. The Diff tab's tree was a third copy
  of the rule before it joined the group; a fourth list joins it too.
- **A `sessions` push carries what changed, never every row** (#431,
  `sessions_change`, `mergeSessions`): the rows new or different since
  the last push, and the order of the ids whenever it moved -- a row that
  went moves it, so there is no list of the gone. Every change sent every
  row: 111 KB a push at 100 sessions, about once a second while agents
  work, over the tunnel uncompressed. A stream still opens with every row
  (`sessions_payload`). **Safe only because a stream has no gaps** (the
  bullet above): a push it cannot keep closes it. And a push says "these
  rows now read so", so pushes queued behind an opening newer than some of
  them still end on the newest rows. Only the tick writes `told`.
  `test_a_push_carries_only_what_changed`,
  `test_a_push_fills_only_the_rows_it_changed`.
- **The page is read over an ssh tunnel, so nothing big goes twice.** At
  200 KiB/s the first look at a Files tab of 53,000 files took twenty
  seconds, and the way back to the Transcript tab five. Three causes, three
  fixes, each measured with Chromium's own throttle:
  - **`reply` packs text with gzip** (`takes_gzip`, `PACKED_KINDS`,
    `PACK_MIN`): 2.5 MB of names went as 109 KB. Only text: a picture from
    `raw` is packed already. The import is inside `reply`, for the hook's
    sake, and an `Accept-Encoding` it cannot read is a no.
  - **The transcript fetch says what it holds** (`?have=<run>.<version>`),
    and the daemon answers `same` with no blocks. **Only `state.turns.whole`
    may send it**: pushes alone are pieces, and their version is the
    daemon's own. A session chosen on another tab gathers pushes before any
    fetch, and a stream that opens on more than is held has lost pushes.
    Either named as what is held came back `same` and the tab showed the
    pieces. Any gap clears `whole`; only a fetch that lands sets it.
  - **The Review tab's poll is answered `same` while the diff stands**
    (`answer_tag`, `state.diffTag`): the whole diff came every five seconds.
    The tag is a hash of the answer itself, so nothing the page draws can be
    left out of it, and a tag sent for another question can never match.
    It is sent only while `diffTag` holds one -- every place that drops
    the answer empties it -- and a `same` still reaches the retry of an
    untracked file's read at the end of `loadDiff`. The whole text was kept
    beside the tag (`diffRaw`) as a second comparison, megabytes for a large
    diff; the tag is the one now (#291). **And the answer is written once**:
    `wire_json` writes a dataclass's fields where they stand, the tag is a
    hash of those bytes, and the tag is set into them before the last
    brace. `asdict` and two `dumps` were 431 of the 715 ms a poll of a
    2,500-file branch cost.
  - **What a branch committed is kept** (`Daemon.diffs`, `worktree_diff`'s
    `held`), under the base's sha and HEAD's, which `pick_base` reads from
    the listing it makes anyway (`BaseChoice.head`, `tip`). The log and
    `git diff <base>...HEAD` ran on every poll for an answer that moves only
    when one of the two does. Only what git gave whole is kept, as `ranks`
    keeps only a count git gave; what is not committed is read every time.
    `test_a_branch_that_did_not_move_is_not_diffed_again`.
  - **The open file goes back as a `stamp`** (`FileText.stamp`, the mtime in
    nanoseconds and the size), and a file that still has it is answered
    `same` before it is read (#292): the Files tab was sent up to 512 KB
    every two seconds to throw away. Only after `worktree_target`, which asks
    `is_listed` every time. One reader of that route's answer, `askFile`: a
    `missing` taken for the text was a bug three times, once in each of
    `loadFiles`, `readLoose` and `readElsewhere`.
    `test_a_file_that_did_not_move_is_not_sent_again`,
    `test_a_file_nobody_touched_is_not_sent_again`.
  - **The file names are kept per worktree, not per session**
    (`keepListing`, `adoptListing`, `state.listings`, by `worktree_path`):
    a session choice blanked them, so every switch -- to another session in
    the same worktree, or back -- fetched every name again.
  - **The transcripts of the last sessions are kept too** (`keepTurns`,
    `takeTurns`, `state.heldTurns`, `TRANSCRIPTS_KEPT`): every return to a
    session fetched its whole transcript, 869 KB for 704 blocks, measured;
    now it is drawn at once from what is kept (`drewHeld` in
    `loadTranscript`) and the fetch carries `have`, answered `same` in 51
    bytes. A `same` after that draw draws nothing again: it rebuilt every
    block, 70 to 90 ms. Only a `whole` reading is kept, as only it may
    send `have`. **`keepTurns` runs before `state.chosen` moves**: after
    it, the last session's transcript was kept under the new id and drawn
    at once under the new session's name -- and the daemon answered `same`,
    because two sessions are both at run 0, version 1 often enough.
    `test_a_session_gone_back_to_is_drawn_from_what_the_page_kept`,
    `test_the_page_keeps_the_last_transcripts_and_no_more`.
  - **`load` clears the last tab's poll timer first**, and re-arms one
    only for the tab it loaded. Only `repoll` cleared it, after the load:
    the Files tab's two-second poll fired into the Transcript tab while its
    fetch was out and fetched it all again; and a Files load still out at
    the switch armed the next tab's timer on its way out.
  A test that holds the transcript route matches it with `TRANSCRIPT`, a
  pattern that takes a query: the glob `**/transcript` does not, and held
  nothing once `?have=` was there.
  `test_text_is_packed_for_a_client_that_takes_gzip`,
  `test_a_picture_is_never_packed`,
  `test_a_transcript_the_page_holds_whole_is_not_sent_again`,
  `test_coming_back_to_the_transcript_fetches_only_what_moved`,
  `test_pushes_gathered_on_another_tab_are_not_taken_for_the_whole`,
  `test_a_stream_that_opened_on_more_off_the_tab_fetches_it_whole`,
  `test_the_last_tabs_poll_does_not_fetch_the_transcript_again`,
  `test_a_load_that_ends_after_the_switch_sets_no_timer`,
  `test_a_diff_the_page_holds_is_not_sent_again`,
  `test_a_poll_of_a_diff_that_stands_is_answered_short`,
  `test_another_session_in_the_worktree_does_not_fetch_its_names_again`.
- **A switch not drawn within `SWITCH_SHOWN` says it is loading**
  (`beginSwitch`, `endSwitch`, `body.switching`, `data-loading`). The box
  is built from what comes back, so it held the last session's or tab's
  drawing until then, and over a slow tunnel the reader took that for the
  switch done. `showTab` begins it, `draw` ends it, and in between the old
  content is dimmed, takes no click, and a label says "loading <session>
  · <tab>…". **Not at once**: a switch drawn sooner shows nothing, or every
  switch would flicker; the test checks at half the delay.
  `test_a_slow_switch_says_it_is_loading_and_a_quick_one_says_nothing`.
- **The page asks the daemon one way: `getJson`, the one `fetch`** (#541).
  It was four -- `ask` gave null, `post` an `{error}`, `runSearch` and
  `askSaved` each a try of their own -- and each new caller picked one.
  `getJson` gives `{ok, body}`, or `{ok: false, body: null, why}` when the
  daemon did not answer; `ask` and `post` keep their own answers on top of
  it, because many callers read them. Its `wanted` drops an answer the
  reader no longer wants by giving null; a loader whose check reads its
  own state -- the session, the base, a ticket -- keeps that check after
  `ask`, because a null from `ask` must keep meaning "no answer" and not
  also "too late". `test_only_get_json_calls_fetch`,
  `test_the_page_asks_the_daemon_one_way`.
- **A scrollbar is the browser's, so the page has to tell it which way round
  it is.** Without `color-scheme` a dark page carried the system's bright bar
  down every column — measured: `color-scheme: normal` and
  `scrollbar-color: auto` in both themes. Both properties are set and both
  are needed: `scrollbar-color` is the exact hue, taken from the same
  `--edge-bright` every other edge on this page uses and with a transparent
  track so it shows what it lies on; `color-scheme` is what a browser that
  ignores the first falls back to, and it is also what puts the form controls
  right — the search box's clear button, the send box's own bar.
  `scrollbar-color` is inherited, so `:root` is the only place it is said.
- **Every tab says what its find box is for, in `TABS.finds`.** The
  placeholder was a ternary in `showTab` naming three tabs, so the two it did
  not name got whatever the last arm said, and a tab with no list offered
  "find a file" for a list it did not have. One entry per tab, like `draw`,
  `load` and `poll`, and `TAB_KEYS` is `Object.keys(TABS)`, so a new tab is
  that one entry. Every tab is split and has a list, so there is no longer
  a tab that hides the box.
- **`hidden` hides, whatever else an element sets: one rule,
  `[hidden] { display: none !important; }`** (#296). A rule that sets
  `display` beats the browser's own rule for the attribute, so the send
  box never went away -- the `.sendbar` scar -- and twelve controls each
  carried an `X[hidden]` of their own after it: `#jump` (`.theme`), the
  row's lines, the arrow to the foot, the find box, the settings menu.
  One forgotten is a control that will not go. Never write another;
  `test_hidden_is_one_rule` fails on one.
- **A class the page puts on `body` is never the class an element wears.**
  `stream.onerror` did `classList.add("lost")`, and the rule hiding the bar
  until it was wanted was `.lost { display: none }` — which `body` then
  matched itself. **The whole page went to `display: none` the moment the
  stream hiccupped**, and came back when it reconnected or when the reader
  pressed F5, so from the outside it read as a page that had simply stopped
  working. The states are `offline` and `outdated` now; the bars stay `.lost`
  and `.stale`. `test_no_state_on_the_body_can_make_the_page_vanish` names
  every state the page sets and asserts the page is still there under each,
  and under all of them at once — a new state belongs in that list.
- **A restarted daemon leaves every open page dead, and only the page can
  say so.** The token is made fresh in `Daemon.__init__` and printed into
  the page, so a restart leaves every browser holding one this daemon has
  never heard of. The stream is a GET and reconnects, so the sidebar goes on
  moving and the page looks alive while every send, every jump and every
  answered question is refused — in every session at once, because the token
  belongs to the daemon and not to a session. `stale_page()` picks the
  *wording* of a refusal `allowed()` has already made; it changes no
  decision, and a caller that fails `origin_ours` is told nothing it did not
  already know. The page raises a bar that only a reload clears, which is
  right anyway: after an upgrade its JavaScript is old too.
- **The strip carries what the session has spent, and says it is an
  estimate.** Claude Code works `cost.total_cost_usd` out on the client at
  list price, says it may differ from the bill, and resets it to nought on
  `/clear`. The caveat rides on the number as a `title`, because it is read
  once and the strip has no width for a sentence. `None` is "the status line
  did not say" and `0` is "it spent nothing": a session on an API key gets no
  `cost` at all, and `$0.00` for it would be a number nobody measured — so
  `drawContext` tests for null rather than defaulting.
- **`money` is a name on both sides, and shadowing it is a `ReferenceError`.**
  `drawContext` calls the page's `money()` and then builds an element for what
  it returned. Naming that element `money` puts the call above it in the
  temporal dead zone — a page that throws on every draw, from a line that
  reads perfectly. Same scar as `matches` / `matching` / `hits`.
- **A tab's name never wraps, and the tab row asks itself how wide it is**
  (#397): `.tabs` is a query container, because the sidebar's width moves
  its room as much as the window's does. At 760 px or less the keys'
  numbers (`.tabkey`) go -- the key still works and the tab's title names
  it -- and at 560 px or less the context bar and the spend step aside.
  At 1024 px "1 Transcript" broke over two lines and the cost was cut by
  the icons. The tabs have no icons to fall back on. A test of it needs
  the status line's model, context and cost in the row (`page_at` writes
  them): an empty row fits without any of this.
  `test_the_tab_names_stay_on_one_line_in_a_narrow_window`.
- **The context bar is its own slot, beside `#live` and never in it.**
  `paintLive` is the one writer of that slot and four things already want it
  — what the stream is doing, something you asked for and did not get, a
  `settings.json` that cannot be used, and a passing word over them. A fifth
  would be the race that rule was written after. `drawContext` is called from `drawHeader`, so it arrives with
  everything else a push carries and no fifth call site can forget it, and it
  redraws only when the number moves — the push is about once a second and
  the number is not. `putContext` builds it. A session whose status line is not
  registered has no `context_pct` and gets no bar: nought would read as an
  empty window rather than as no answer.
  **The model stands left of the bar**, because the percentage is a
  percentage of that model's window and `/model` changes it mid-session.
  It is part of the same redraw key. `tests/shot.py` writes a status line
  for its session, so a picture of the strip has all three in it.
  `test_the_model_stands_left_of_the_context_bar`.
  - **The effort stands after it, "Opus 5.5 · high"** (issue 337):
    `effort.level` of the status line, measured on 2.1.287 -- `/effort`
    moves it, and Haiku has none, so then nothing is shown. In the redraw
    key with the model.
  - **The two are a button that opens `#modelpop`** (`showModels`,
    `putModels`, issue 338): the aliases (`MODELS`), the full ids the
    sessions on the page ran (`model_id` of each row, the daemon keeps a
    week), and the efforts (`EFFORTS`) while the session has one. A pick is
    typed as `/model <name>` or `/effort <level>` through `send`, and the
    menu shuts. **It says that Claude Code makes the choice the default for
    new sessions too**: measured on 2.1.287, a typed `/model sonnet` writes
    `"model": "sonnet"` into Claude Code's own `settings.json`, and a typed
    `/effort` its `modelSettings`; only its menu in the terminal offers
    "this session only". The reader chose this over opening that menu.
  - **An alias is pressed never; the full id is.** An alias names the
    newest of a family as this Claude Code maps it -- `opus` gave Opus 5.5
    and `/model claude-opus-5` gave Opus 5, measured -- so which one the
    session runs is only known by its id.
  - **A full id reaches the page through `MODEL_SHAPE`**, since the page
    types it into a terminal, as `COMMAND_SHAPE` holds a command's name.
  - **Off where nothing can be typed** (`whyNotTyped`), saying why, and
    Escape and a click elsewhere shut it, as they shut the settings.
  `test_the_model_says_its_effort_and_a_pick_types_the_command`,
  `test_an_older_model_is_offered_by_its_full_id`,
  `test_a_model_with_no_effort_offers_none`,
  `test_the_model_menu_shuts_and_types_nothing_it_cannot`.
- **One painter for the live slot, and four things that want it.**
  `state.live` is what the stream is doing, `state.trouble` is something you
  asked for and did not get, `state.linkTrouble` is the reader's own file
  that cannot be used, and `note` borrows the slot over all three for four
  seconds. `paintLive` decides; nothing else assigns to `#live`. Four writers
  raced before it: the stream writes "live" on every push, about once a
  second while an agent works, so a failure written straight into the slot
  was wiped within a second — the thing the reader most needed to read was
  the thing that lasted least. **CI caught that**, not the browser tests I
  had just written: the assertion was three lines below a
  `wait_for_timeout(4500)` and passed locally because nothing was pushing.
  **`paintLive` is called whatever the find box holds.** Both stream
  handlers skipped it while it held text, a guard with nothing left to
  guard: a drop said nothing, and a reconnect left "reconnecting" standing
  over a working page. Two more rules for the slot:
  - **A working stream says nothing.** The slot read "live" on every page all
    day. A reader can see the page moving, so the word told nobody anything,
    and a word that is always there is a word nobody reads — "reconnecting"
    in the same place went unseen too. `state.live` still holds "live";
    `paintLive` only does not paint it, so a test that wants to know the
    stream is up asks `state.live`, not the slot.
    `test_a_working_stream_says_nothing_and_a_lost_one_says_so` holds both
    halves.
  - **`said` is the daemon's answer and it stays; `note` is our own word and it
    fades.** "Review sent" goes stale in four seconds. "That did not come from
    this page" is about something you asked for and did not get, and fading it
    left a strip reading "live" over a page where nothing worked — which is
    exactly how a restarted daemon went unexplained. **So a send that worked
    calls `said` before its `note`**: the note only borrowed the slot, and when
    it faded the refusal before it came back over a review that had gone
    through. `test_a_review_that_goes_through_clears_an_earlier_refusal`.
- **No JavaScript library is vendored.** `marked` and `highlight.js` are fetched
  through the one `fetchScript`, each pinned by the hash of its bytes, with
  `crossorigin` so the browser checks it. Any script on this page can POST to
  `/send`. Each must degrade: without `marked` the transcript is its own source
  as text, without `highlight.js` code has no colour. Tests hold both fallbacks,
  and `tests/fixtures/marked.min.js` is what the page tests serve, so no test
  needs a network.
- **Motion**: a row fades on a state change, a *new* transcript block
  slides in 4 px, the needs-you row pulses. Nothing else moves. "New" means
  arriving in `patchTranscript` — never a redraw. One `prefers-reduced-motion`
  block turns all of it off.
