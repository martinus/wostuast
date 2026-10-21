# The daemon and the page

Routes, polling, the stream and its pushes, the tab frame, the find box,
the ssh tunnel, the context bar, the live slot, and the tab row: jump and
the loaders.

- **Every route lives in `Serving`**, a module-level class; `make_server`
  mixes it with `BaseHTTPRequestHandler` and sets `self.daemon`. **The
  `http.server` import stays inside `make_server`**: the hook pays for
  every import on every tool call (49.5 ms with it, 10.8 without).
  `test_the_hook_does_not_import_what_it_does_not_need`.
- **Write to a terminal only through the four tmux verbs**: `tmux_jump`,
  `tmux_send`, `tmux_interrupt`, `tmux_keys`. Each looks up `run` when
  called, so a test can fake tmux.
- **The Files and Diff tabs poll from the browser, only while on screen**:
  the daemon knows no browser's tab, so `Hub` stays small. `TABS` holds
  one entry per tab.
- **One lock around the transcript readers, and the push goes out under
  it.** Two `read_new` at once move the offset twice: a shrinking file.
  Sent after the lock, a request's block 2 overtook the tick's block 1,
  and the page, patching by index, lost block 1. `Hub.send` only queues.
  `test_a_transcript_push_leaves_under_the_lock`.
- **The one find box leaves before its parent is cleared**: else
  `$("find")` is null and `showTab` throws until a reload. `draw()` takes
  it home when `box.dataset.tab` names another tab; `split()` takes it
  back. `test_every_way_from_one_tab_to_another_works`.
- **Ask the box which tab it holds, not `state.tab`**: `showTab` sets the
  name, then awaits `load()` while the box holds the old tab, and a push
  appended a turn to the Files tab. `draw()` does it right.
- **A session can be chosen before the session list exists**: a link runs
  `choose` with `state.sessions` empty, so `current()` is null. The
  `sessions` event draws again once the session is real.
- **Each push has its own handler**, `onSessionsPush` and
  `onTranscriptPush` (#544); `resubscribe` only opens the stream.
- **A list of one-line rows joins the one rule that groups them**
  (`.fixed`, `.diff`, `.transcript`), never a copy: `.filelist button` is
  a block, so without it the icon sits a line above the text.
- **A `sessions` push carries what changed, never every row** (#431,
  `sessions_change`, `mergeSessions`): new or changed rows, and the id
  order when it moved. Every row was 111 KB a push at 100 sessions. A
  stream opens with every row (`sessions_payload`). **Safe only because a
  stream has no gaps**: one that cannot keep a push closes
  (topics/transcript). A push says "these rows now read so", so pushes
  queued behind a newer opening still end right. Only the tick writes
  `told`. `test_a_push_carries_only_what_changed`,
  `test_a_push_fills_only_the_rows_it_changed`.
- **The page is read over an ssh tunnel, so nothing big goes twice**: at
  200 KiB/s, 53,000 file names took 20 s.
  - **`reply` gzips text** (`takes_gzip`, `PACKED_KINDS`, `PACK_MIN`),
    never a `raw` picture. The import is inside `reply`, for the hook. An
    `Accept-Encoding` it cannot read is a no.
  - **The transcript fetch says what it holds** (`?have=<run>.<version>`),
    and the daemon answers `same`. **Only `state.turns.whole` may send
    it**: pushes are pieces with the daemon's version, so pushes gathered
    on another tab came back `same` and showed pieces. Any gap clears
    `whole`; only a landed fetch sets it.
  - **The Review tab's poll is answered `same` while the diff stands**
    (`answer_tag`, `state.diffTag`). The tag hashes the answer itself, so
    nothing drawn is left out. It goes only while `diffTag` holds one;
    whatever drops the answer empties it. A `same` still reaches the
    untracked file's retry in `loadDiff`. The tag is the only comparison
    (#291). **The answer is written once**: `wire_json` writes the fields
    in place and hashes those bytes; `asdict` and two `dumps` took 431 of
    715 ms a poll.
  - **What a branch committed is kept** (`Daemon.diffs`, `worktree_diff`'s
    `held`) under the base's sha and HEAD's, from `pick_base`'s listing
    (`BaseChoice.head`, `tip`): `git diff <base>...HEAD` moves only with
    those. Only what git gave whole is kept, as `ranks` keeps only a count
    git gave; the uncommitted part is read every time.
    `test_a_branch_that_did_not_move_is_not_diffed_again`.
  - **The open file goes back as a `stamp`** (`FileText.stamp`: mtime in
    ns, size); one that still has it is answered `same` unread (#292),
    only after `worktree_target` asks `is_listed`. **One reader of that
    answer, `askFile`**: a `missing` taken for text was a bug in each of
    `loadFiles`, `readLoose`, `readElsewhere`.
    `test_a_file_that_did_not_move_is_not_sent_again`,
    `test_a_file_nobody_touched_is_not_sent_again`.
  - **File names are kept per worktree** (`keepListing`, `adoptListing`,
    `state.listings`, by `worktree_path`), not fetched on each switch.
  - **The last sessions' transcripts are kept** (`keepTurns`,
    `takeTurns`, `state.heldTurns`, `TRANSCRIPTS_KEPT`), drawn at once
    (`drewHeld` in `loadTranscript`), and the fetch carries `have`. **A
    `same` after that draw draws nothing**: a rebuild cost 70-90 ms. Only
    a `whole` reading is kept. **`keepTurns` runs before `state.chosen`
    moves**: after, the old transcript was drawn under the new session,
    as two sessions often sit at the same run and version.
    `test_a_session_gone_back_to_is_drawn_from_what_the_page_kept`,
    `test_the_page_keeps_the_last_transcripts_and_no_more`.
  - **`load` clears the last tab's poll timer first**, and re-arms only
    the loaded tab's. Cleared after (`repoll`), the Files poll refetched
    the Transcript tab, and a late Files load armed the next tab's timer.
  - **A test matches the transcript route with `TRANSCRIPT`**: the glob
    `**/transcript` matches no query.
  - Tests: `test_text_is_packed_for_a_client_that_takes_gzip`,
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
  (`beginSwitch`, `endSwitch`, `body.switching`, `data-loading`): an old
  drawing over a slow tunnel read as done. `showTab` begins it, `draw`
  ends it; between, the old content is dimmed and takes no click. **Not
  at once**, or every switch flickers.
  `test_a_slow_switch_says_it_is_loading_and_a_quick_one_says_nothing`.
- **The page asks the daemon one way: `getJson`, the one `fetch`** (#541):
  with four (`ask`, `post`, `runSearch`, `askSaved`), each caller picked
  one. It gives `{ok, body}` or `{ok: false, body: null, why}`; `ask`
  (null) and `post` (an `{error}`) stay on top. `wanted` gives null for an
  answer no longer wanted. **A loader whose check reads its own state
  keeps that check after `ask`**: null from `ask` means only "no answer",
  not "too late". `test_only_get_json_calls_fetch`,
  `test_the_page_asks_the_daemon_one_way`.
- **Set both `color-scheme` and `scrollbar-color`, once on `:root`**:
  without `color-scheme` a dark page had a bright system scrollbar and
  form controls. `scrollbar-color` is `--edge-bright` on no track.
- **Every tab says what its find box is for, in `TABS.finds`**, beside
  `draw`, `load`, `poll`: a ternary in `showTab` offered "find a file" on
  a tab with no files. `TAB_KEYS` is `Object.keys(TABS)`.
- **`hidden` is one rule, `[hidden] { display: none !important; }`; never
  write another** (#296): any rule that sets `display` beats the
  browser's own (the `.sendbar` scar), and an `X[hidden]` per control
  (`#jump`, `.theme`, the find box) is one forgotten.
  `test_hidden_is_one_rule`.
- **A class put on `body` is never a class an element wears**:
  `stream.onerror` put `lost` on `body`, `.lost { display: none }` hid a
  bar, and the page vanished on every stream hiccup. Body states are
  `offline` and `outdated`; the bars are `.lost` and `.stale`.
  `test_no_state_on_the_body_can_make_the_page_vanish`; **a new state
  goes in its list**.
- **A restarted daemon leaves every open page dead, and the page says
  so.** `Daemon.__init__` makes a fresh token; the stream reconnects, so
  the page looks alive while every send is refused. `stale_page()` only
  words a refusal `allowed()` already made: a caller failing
  `origin_ours` learns nothing new. Only a reload clears the bar.
- **The strip's spend says in its `title` that it is an estimate**:
  Claude Code computes `cost.total_cost_usd` at list price and zeroes it
  on `/clear`. **`None` is "not said", `0` is "spent nothing"**: an
  API-key session gets no `cost`, so `drawContext` tests for null.
- **Never shadow `money`**: an element named `money` in `drawContext` puts
  the call `money()` in the temporal dead zone, a `ReferenceError` on
  every draw. Same scar as `matches` / `matching` / `hits`.
- **A tab's name never wraps** (#397): `.tabs` is a query container, as
  the sidebar moves its room. At ≤760 px `.tabkey` goes; at ≤560 px the
  context bar and spend step aside. **The test needs the model, context
  and cost in the row** (`page_at` writes them): an empty row fits.
  `test_the_tab_names_stay_on_one_line_in_a_narrow_window`.
- **The context bar is its own slot, never in `#live`**: a fifth writer
  for `#live` is the race the next bullet ends. `drawHeader` calls
  `drawContext`, which redraws only when the number moves; `putContext`
  builds it. No `context_pct`, no bar: nought reads as an empty window.
  **The model stands left of the bar**, in its redraw key: `/model`
  changes the window mid-session. `tests/shot.py` writes a status line
  for it.
  `test_the_model_stands_left_of_the_context_bar`.
  - **The effort follows it, "Opus 5.5 · high"** (issue 337), from
    `effort.level`, in the same redraw key.
  - **The two are a button that opens `#modelpop`** (`showModels`,
    `putModels`, issue 338): aliases (`MODELS`), full ids the sessions ran
    (`model_id`, kept a week), and efforts (`EFFORTS`). A pick types
    `/model <name>` or `/effort <level>` through `send`. **It says the
    pick becomes Claude Code's default too**: `/model` writes its
    `settings.json`, `/effort` its `modelSettings`. The reader chose this
    over Claude Code's own menu.
  - **Never press an alias; press the full id**: an alias names whatever
    this Claude Code maps it to.
  - **A full id passes `MODEL_SHAPE`**, as a command's name passes
    `COMMAND_SHAPE`: the page types it into a terminal.
  - **Off where nothing can be typed** (`whyNotTyped`), saying why.
  - Tests: `test_the_model_says_its_effort_and_a_pick_types_the_command`,
    `test_an_older_model_is_offered_by_its_full_id`,
    `test_a_model_with_no_effort_offers_none`,
    `test_the_model_menu_shuts_and_types_nothing_it_cannot`.
- **Only `paintLive` assigns to `#live`.** It weighs `state.live` (the
  stream), `state.trouble` (asked for, not got), `state.linkTrouble` (the
  reader's file unusable) and `note`, which borrows the slot for 4 s. With
  four writers, the stream's word on every push wiped a failure. **It runs
  whatever the find box holds**: else a drop went unsaid.
  - **A working stream says nothing**: a word always there is never read.
    A test asks `state.live`, not the slot.
    `test_a_working_stream_says_nothing_and_a_lost_one_says_so`.
  - **`said` is the daemon's answer and stays; `note` is ours and fades**:
    a faded refusal left a calm strip over a dead page. **A send that
    worked calls `said` before its `note`**, or the old refusal came back.
    `test_a_review_that_goes_through_clears_an_earlier_refusal`.
- **The transcript can stand beside the Files or Review tab** (#625,
  `chatShown`, `paintChat`, `turnsHost`, `#chat`, `body.sidechat`): a
  fourth column of `.main` on the right, as the reader chose from pictures
  (on the left it parted the file list from its session). `t` or
  `#chatbtn`; this browser keeps it (`wostuast-chat`), as a fold. Never
  over a view or beside the Transcript tab itself.
  - **Every reader of the drawn transcript asks `turnsHost()`**, never
    `$("content")`: a push patched a pane nobody saw. `patchTranscript`,
    `drawnTurns`, `loadTranscript`'s `onScreen`, `markSeen`.
  - **The question bar, the send box and the resume line are moved into
    the column** (`carryBars`), never built again: left in `.main`'s rows
    they kept an empty strip under the tab's pane. They go back before
    `#reviewbar`.
  - **The column loads the transcript once** (`load`, `!state.turns.whole`):
    the pushes keep it, and the Files tab's poll must not fetch it again.
  - **It folds nothing; its own edge gives the room** (#641, `.chatgrip`,
    `--chat-w`, `CHAT_LEAST`): turning it on folded the session list, and
    the reader wanted the list. Its left edge drags its width, as the
    session column's does; dragged left, it grows (`dragEdge` with
    `-clientX`).
    `test_the_transcript_column_is_as_wide_as_its_edge_is_dragged`.
  - **Its head's rule lines up with the bar beside it** (`fitChatHead`, in
    `land`): it stood 4 px above the commit picker's, and the reader saw it.
    Measured, not set: Review's bar and the Files tab's path (which wraps)
    differ. `test_the_transcript_column_s_head_lines_up_with_the_bars_beside_it`.
  `test_the_transcript_stands_beside_the_review_and_follows_the_agent`,
  `test_the_transcript_is_never_beside_itself`.
- **No JavaScript library is vendored.** `marked` and `highlight.js` come
  through `fetchScript`, pinned by the hash of their bytes, with
  `crossorigin`: any script here can POST to `/send`. **Each degrades**:
  no `marked`, plain text; no `highlight.js`, no colour. Page tests serve
  `tests/fixtures/marked.min.js`, so none needs a network.
- **Only three things move**: a row fades on a state change, a new
  transcript block slides in 4 px, the needs-you row pulses. "New" is
  arriving in `patchTranscript`, never a redraw. One
  `prefers-reduced-motion` block stops it all.
- **There is no Session tab, and no bar over the tabs**: it cost 56 px on
  every tab for what the row shows. Jump is an icon at the end of the tab
  row (`#jump`, `ICONS.terminal`); the name is changed on the row.
  `drawHeader` is the send box, the review's send bar, the question bar,
  the context strip and jump, and nothing else.
  - **A jump that went says so** (`jumpToPane`, `flashOutcome`): a tick,
    and the live slot says "jumped to" and the row's name; it lands in
    another window, so it looked like nothing. A refused jump shows tmux's
    error and never ticks.
    `test_a_jump_says_it_went_and_a_failed_one_does_not`. `JUMP_TITLE`
    stands above the start-up line that reads it: a `const` read earlier
    stops the page.
- **Every tab has a loader, and a tab switch goes through it, not
  `draw`**: an empty loader left the old tab on screen. A tab that fetches
  nothing gives a loader that draws.
