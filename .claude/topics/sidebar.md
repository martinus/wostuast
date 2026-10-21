# The sidebar

The groups, `settled`, children under a row, the top of the page, a row's
lines and icons, the chosen row, the grip, drags, folds, rows kept.

- **Group by state, newest first inside a group.** `BANDS`, most urgent
  first: needs you, working, waiting, ready, history (the reader's order: one at
  its prompt waits for nothing). A row moves only when a turn begins, ends
  or stops on a question, so the list does not churn. **Inside a group the
  daemon's order stands**: `Session.settled`, newest first.
- **`settled` is not `since`.** `since` moves every few seconds while
  working, and two busy agents swapped places as you read. `settled` is
  when the session last *became* what it is. Only `Store.apply` stamps it,
  and only on a change: `_on_pre_tool` writes "working" on every tool
  call. `_bury` is the one other place, because nothing reports being
  dead. **Stamp it once for a session nothing has stamped**: `SessionStart`
  is done to done, so an idle notification moved an unchanged row.
  `test_a_session_that_never_changed_state_keeps_its_place`. The worktree
  breaks ties. Never sort on `label`: it arrives a second after start, and
  `/rename` changes it.
- **What an agent starts is a line under its row, never a row** (#422): a
  `claude -p` from a Bash tool was a row that flashed by, counted as
  working then unread, and did not say whose it was. `fillKids` draws a
  line per running child -- a session whose `started_by` is this row
  (`kidsOf`), or an Agent-tool subagent in `subagents` -- then "N subagents
  ran", which unfolds the ended ones (`state.kidsOpen`). The daemon keeps
  the last `SUBAGENTS_HELD`; `agents_ran` counts them all.
  - **A child counts nowhere** (`topSessions`, `childIds`): not in the
    list, groups, tab title and icon, alerts or unread feed. A child whose
    parent the page does not hold is a row again.
  - **Never hide one that may need the reader**: a child with its own
    pane, one that waits, or one working under a parent that is over is a
    row, or its dialog had no row, title or alert. **The chosen child stays
    in sight when it ends.**
  - **A subagent's line says what it did** (#618, `Subagent.calls`,
    `said`, `tokens`, `note_agent_ended`, `agentStats`): "subagent" and a
    time said nothing. Once over, a second line under what it was asked
    (`.kidstats`): its kind, calls, tokens and how long it ran (`lasted`).
    Beside it, "general-purpose" took the narrow line and cut the numbers.
    Its last words are on the hover. Calls count its `PreToolUse`s only. Tokens come from the
    `<usage>` of the `<task-notification>` of its end (2.1.306), so a
    subagent in the foreground has none, and the line leaves them out.
    `test_a_subagent_says_what_it_did_and_what_it_cost`,
    `test_a_subagent_that_ran_says_its_kind_what_it_did_and_its_last_words`.
  - **A compaction's own agent is no subagent** (#637, `is_own_agent`):
    `/compact` fires a `SubagentStop` with an `agent_id`, an empty
    `agent_type` and nothing before it
    (`tests/fixtures/compact_agent.jsonl`). Each one stood under the row
    as "subagent", 0 calls, 0 s, and counted in "N subagents ran". One we
    already hold stays a subagent, whatever its end says.
    `test_a_compaction_s_own_agent_is_no_subagent`.
  - **A subagent's line opens its own transcript, read only** (#618,
    `openAgent`, `dropAgent`, `state.agent`, `read_agent`): in the
    Transcript tab, as the reader chose, under a bar that names it and goes
    back. **Its turns are `state.turns` while it is open, and the
    session's wait aside in `state.agent.held`**: drawn with the session's
    machinery, a click on one of its calls opened the session's block at
    that number, and its runs never folded. So the session's pushes are
    not heard meanwhile (`onTranscriptPush`), and its next load fetches
    them. Any `showTab` leaves it, so a turn link, a card or a command
    lands in the session's; a view open is closed. No buttons on its turns
    (`.agentview`), no send box (`transcriptShown`); its names link
    nowhere, and its first prompt is "task", the agent's words, not yours.
    `test_a_subagent_s_line_opens_its_own_transcript_read_only`,
    `test_a_running_subagent_s_transcript_follows_it`,
    `test_a_subagent_s_own_transcript_is_served_by_its_id`.
  - **Let go of what an Agent call asked for at a turn's edge**
    (`agent_asks`): a declined call fires no hook and a failed one starts
    nothing, so their descriptions named later subagents. A failed call
    drops its own. `test_a_call_that_started_nothing_names_no_subagent`.
  - **A subagent is over when the agent's `Stop` no longer lists it**
    (`end_unlisted_subagents`): one stopped with `x` in the agents panel
    sends no `SubagentStop`, only a `<task-notification>` prompt
    (`tests/fixtures/subagent_killed.jsonl`), and its line ran for days.
    Every agent `Stop` lists each running subagent in `background_tasks`,
    `agent_id` as `id`; any entry keeps one. Never a `SubagentStop`'s list:
    it still holds the one that stops. A `Stop` with no list ends nothing.
    `test_a_subagent_the_reader_stopped_is_over_at_the_next_stop`.
  - **A child's change must redraw its parent's row**: `drawSessions`
    skips the draw when the listed rows are unchanged, so the children go
    into its key. Its test waits until the parent's row is still: the
    unread mark's push redrew it by chance and hid the break.
  - **A press on a line or the fold stops there**, or it chose the row. A
    child session's line opens it (`choose`); a subagent's opens nothing.
  `test_what_a_session_started_stands_under_its_row`,
  `tests/test_subagents.py`.
- **There are five states, not six.** "starting" was ready told in a way
  that went stale. `SessionStart` sets `done`, whose word is "ready".
  **"waiting" is a turn over with a command still running in the
  background** (#617, topics/state): blue said ready over an agent waiting
  on a build. Its colour is `--waiting`, violet: a teal between green and blue was
  hard to tell from both, so the reader chose violet. It counts
  in the title and icon after working, and is no alert.
  - **A command in the background is a line under its row** (`Shell`,
    `note_shells`, `kidsOf`, `.kid.shell`): from its call's result
    (`backgroundTaskId`), kept while each `Stop` lists it as a running
    `shell`, gone at its `<task-notification>` (`TASK_ID`) or `SessionEnd`.
    A subagent's own command is not the row's.
    `test_a_command_in_the_background_is_kept_until_it_ends`,
    `test_a_waiting_row_has_its_own_group_colour_and_lines`.
- **The fold is not a filter.** The filter still counts and searches the
  folded history, and the chosen row is never missing from its list.
- **There is no bar across the top.** The name and version head the
  session list (`.sidebar-head`, as tall as `.tabs`, so the rules under
  them are one line); the settings are one icon at the tab row's end, its
  words in `aria-label` and `title`. The version is `own_version`: the day
  the running file was written (for a copy `install` fetched, its commit's
  day, UTC) and the start of its SHA-256, the bytes `install_behind`
  compares -- never a number raised by hand. `--version` prints the same
  (#344). **No strip of keys under the rows**: `?` shows them in full.
  `test_the_session_list_ends_with_its_rows`,
  `test_the_tabs_start_at_the_top_and_the_name_heads_the_session_list`,
  `test_the_page_says_which_copy_is_running`.
  - **The two find boxes stand on one line, and a fold button is a bare
    icon** (#469, `.find`, `.findslot > .fold`, `.sidebar-head`): no box, a
    ring on hover, 17 px, unlike the find box. `.find`'s edge is
    `--edge-bright`, which both grounds show; `--edge` was the list's own.
    `test_the_find_boxes_stand_on_one_line_and_the_fold_is_a_bare_icon`.
- **What a row offers is icons in the age's place, on its hover** (#389):
  a moon for "not now" and a sun to wake it, a clock for "later" and one
  struck through to cancel, a dot for "unread" (`.act`, `setIcon`,
  `ICONS`). Words cut long names short. **The age goes while they show**
  (`.age.swap`), and `margin: -3px 0` keeps the row's height. **Not there
  at all until the hover** (`display: none`, never `opacity: 0`), **the
  moon too**: "snoozed" marks the row, and `z` needs no pointer. `setIcon`
  keeps the kind in `data-icon` for a test.
  `test_the_row_offers_unread_on_a_read_row_only`,
  `test_a_snoozed_session_stops_saying_it_needs_you_until_it_asks_again`.
- **A row says what nothing else on the page says, in the same four lines
  on every row**: the name, with the time beside it; repository and
  worktree, with remote and path on hover; the branch, git's counts at the
  right edge; what the agent does or asks, only while it does.
  - **Not the state**: edge, tint and group say it. Only a finished row
    keeps the word, because "ended" and "killed" share a group and a grey.
  - **The name is the one Claude Code shows** (`rowName`, `Session.title`,
    #351): the reader's from the page while newer, then the status line's
    `session_name` (`customTitle ?? aiTitle`), then the first prompt that
    is not a command (`first_prompt`), then `place`. A page rename reaches
    Claude Code as `/rename`, so both show one name.
    **A typed name bridges; a name nothing was typed for stands**
    (`Marks.page_name`). A name typed as `/rename` is kept with Claude
    Code's name just before (`Marks.over`) and shown until that moves. A
    name nothing could be typed for, or one a `/clear` moves
    (`link_clear`), stands until the reader changes it. **Never "last
    wins" against the terminal**: the status line does not say when a name
    was set, so a stale one dropped the reader's rename; so did an empty
    `over` read as Claude Code's first guess. **`page_name` never writes**:
    `settle` runs in `ls` and `wait` too, each with its own copy of the
    names. `Store.rename`, the one writer, prunes a typed name Claude Code
    took.
    `test_a_typed_name_stands_until_claude_codes_moves`,
    `test_a_name_nothing_was_typed_for_stands_until_the_reader_changes_it`,
    `test_reading_the_names_writes_nothing`.
    **The name is sans**, or it is half as wide again; the age stays
    fixed, so digits do not dance.
  - **A ticket in the name, worktree or branch is a link**
    (`linkTickets`), rewritten only when its text or `state.links` changed
    (`fresh` on `slot`, `where`, `two`): `fillRow` runs every push, and a
    link rebuilt mid-click loses the click. A click on a link chooses
    nothing; a double-click starts no rename. `renameRow` forgets the
    name's key, or the name stays empty after the box goes.
    **`state.linksKey` is in `drawSessions`' key**, and **`takeLinks`
    calls `drawSessions`**: a changed pattern changes no count and may come
    after the last push. `test_a_ticket_in_a_rows_name_or_branch_is_a_link`.
  - **The git line is one line**: only the branch takes an ellipsis, or
    "✓ clean" broke over two lines. It sets `display: flex`, and the one
    `[hidden]` rule still hides it (topics/daemon-and-page).
  - **A name is changed where it stands** (`renameRow`), by double-click
    or `e`. `fillRow` leaves a name with a box in it alone; `drawSessions`
    gives a moved row its focus and caret back. Enter on the unchanged name
    keeps nothing, or the row would stop following its worktree.
  `test_a_row_says_its_name_where_it_is_its_branch_and_when`,
  `test_the_git_line_is_one_line_and_its_counts_stand_at_the_right`,
  `test_a_row_is_renamed_where_it_stands`.
- **The chosen row is a tab of what stands beside the list**, as in a
  browser: a faint ring had to be looked for. It runs to the grip, its
  ground fades from the state's colour into `--meet`, and the grip opens
  where they meet. **It is the strongest row** (#396): `--hue` (set with
  `--soft` on every state) at 34 % in `--meet` over half its width, a 1 px
  line round it at 55 %, a 6 px edge with 2 px less padding. A
  half-transparent tint faded into grey made it the palest row. **No
  shadow**: it does not show on dark, and lifts a tab off its page. **Its
  line is as wide as other rows' own** (1 px, transparent on theirs), so
  the grip opens over its whole height (`openGrip`); 2 px lines in
  `--edge` vanished on the list. **Every row runs to the line**: cards
  with four round corners read as buttons.
  - **A chosen row is never see-through** (#427): a finished row has
    `opacity: .72`, and chosen it was grey; `.row.ended:not(.chosen)`.
    `test_a_chosen_finished_row_is_as_whole_as_any_chosen_row`.
  - **The list wears `--edge`, the grip's colour, and a split tab's own
    list wears `--meet`**, so the grip is the list's edge and the map
    stands apart without a line. `--meet` is `--panel`, set on `.body`.
  - **The chosen row has only the gradient, mixed into opaque `--meet`**:
    the state tints are half transparent, and on the list's ground it came
    out unlike its group. `test_a_row_shows_its_state_in_its_colour` reads
    the first row, chosen or not.
  - **It stands in by the grip's width** (`calc(4px + var(--grip-w))`).
  - **The grip is outside the scrolling list, so `openGrip` tells it where
    the row is** (`--gap-top`, `--gap-bottom`): after every `drawSessions`
    (a row arriving above scrolls nothing), on scroll, on resize, and from
    a `ResizeObserver` on the chosen row.
  - **The list's scrollbar shows only under the pointer**: between row and
    grip it cut the tab from its content.
  - **Its outline turns into the content's edge and runs on down it**
    (#407): ending square, it was two lines stopping for no reason. A
    quarter circle of `--flare` turns the line upright, `--meet` inside the
    curve, and a 1 px `--gap-line` runs above and below. **All of it is
    the grip's own background** under `#grip.open`: the list clips what a
    row draws outside it. **A corner only where the row's end is in
    view** (`flaretop`, `flarebottom`). A test reads `pixels`: a gradient
    is in no computed style.
    - **Mix the line from the row's `--hue`, never read its border**
      (`--gap-hue`, #416): the border fades in over .2 s, so it was read
      nearly transparent; a custom property does not transition. A test
      that reads a colour after a choice waits for `getAnimations()` to be
      empty.
      `test_the_outline_keeps_its_colour_when_another_row_is_chosen`.
    - **Fade only the grip's colour** (`transition: background-color` on
      `.grip`): with `transition: background`, the `background-position`
      computed from the custom property slid, and lagged every scroll.
      `test_the_opening_in_the_grip_never_slides_into_place` asks
      `getAnimations()` in the frame of the change, so load cannot end the
      transition first.
  `test_the_chosen_row_is_a_tab_of_the_content_beside_it`,
  `test_the_chosen_row_turns_into_the_content_s_edge`.
- **A fill must not depend on how tall a row turns out to be**:
  `box-shadow: inset` left an untinted stripe in a tall chosen row. Use
  `linear-gradient` layers over the state's `--soft`.
- **A drag on an edge starts only on the main button, and ends every way a
  press can end** (`dragWidth`): a right-click's menu takes the
  `pointerup`, so the column followed the mouse with `body.dragging` on,
  and a touch taken for a scroll ends in `pointercancel`. So the grip
  captures the pointer, and `pointercancel` and `lostpointercapture` end
  the drag. Headless Chromium sends neither; the test sends them by hand.
  `test_a_drag_on_an_edge_starts_only_by_hand_and_always_stops`.
  - **One drag for a width and a height** (`dragEdge`; `dragWidth`, and
    `dragHeight` for the send bar's top edge, #442), so no edge forgets
    capture or an end. The height (`--say-h`, `--reviewsay-h`) is the least
    the box is: as a cap only, a drag on an empty box did nothing. **Not
    the most** (#453): a Shift-Enter line did not grow it. It grows to 40vh
    or the dragged height, whichever is taller. A double-click gives the
    box back to `fitSay`.
    `test_the_send_box_is_as_tall_as_its_edge_is_dragged`,
    `test_the_review_is_as_tall_as_the_bars_edge_is_dragged`.
  - **An edge between two grounds draws no line, and its handle is wider
    than it** (#443): lines that looked alike made the page busy. The grip
    is `--split-grip-w` wide; its `::after`, 3 px wider each side, is the
    handle, faintly amber under the pointer (`.hgrip` is the send bar's).
    `test_the_maps_edge_draws_no_line_and_drags_from_beside_it`,
    `test_a_line_between_two_grounds_is_not_drawn`.
- **A column folds to a strip that holds only its button** (#464, `FOLDS`,
  `putFold`, `paintFold`, `unfold`, `folded`, `#sessionfold`, `.fold`,
  `body.foldsessions`, `body.foldlist`, `--fold-w`): on a laptop the two
  lists took 615 of 1366 px.
  - **A class on `body`, never on the column**: `split` rebuilds a split
    tab's list on every switch, and the grip and `.main`'s grid must know.
    The list column folds on all three tabs, as `--side-w` is one.
  - **The button stands in the column's `.findslot`, put first by CSS**
    (`order: -1`, #492): `homeFind` appends `#find` to the slot. **Folded
    or open, it stands in one place** (`--fold-in`), so a second press
    needs no move. **Each fold's rule names its own column** (#504):
    `.foldlist .findslot > .fold` hit the session list's slot too; use
    `.foldlist .content.split > .side > .findslot`.
    `test_a_fold_button_stays_where_it_was_pressed`.
  - **A folded column's edge drags nothing** (`pointer-events: none`).
  - **`f` and `/` unfold the column they type into**: a `display: none`
    column takes no focus.
  - **No `openGrip` on a fold**: `gripWatch` sees the chosen row hide and
    return; a call there stayed green under `tests/perturb.py`.
  - **Folded, every session is a tile, and the tiles are the rows**
    (`markRow`, `tileTitle`, `data-name`, `.foldsessions #rows`): one
    button hid who needs you, and a second list would need its own clicks,
    order and pushes. The name runs up the tile
    (`writing-mode: vertical-rl`, then `rotate(180deg)`) on its state's
    colour, with the unread dot; two letters across told one repository's
    sessions apart only by colour. A click chooses, `j` `k` move; the
    chosen tile looks like the chosen row, and the grip opens beside it.
    **On hover, the row whole, over the tile** (`tileCard`, `#tilecard`,
    #491): a `cloneNode` of the row, so it says what the row says. No row
    carries a `title` (`tileTitle`), or the browser's would cover the card.
    Nothing on the card is pressed: the tile is.
    **A long name fades at its end (`mask-image`), never "…"**, which took
    three letters' room.
    **Anchor the rules on `#rows`**: a class-only rule lost to
    `.row .line1` and `.row.chosen`, and drew every row's text over the
    content.
  - Kept in `localStorage` (`wostuast-fold-sessions`, `wostuast-fold-list`)
    as a width is: not a setting in the menu.
  `test_each_column_folds_away_and_comes_back`,
  `test_the_list_column_folds_on_every_split_tab`,
  `test_a_key_into_a_folded_column_brings_it_back`,
  `test_a_folded_session_list_is_a_tile_for_each_session` (the card too).
- **Rows are kept and filled in again, never rebuilt**, or a row does not
  fade into its new colour and the needs-you pulse stops mid-cycle.
  `newRow` builds every part once, empty; `fillRow` reaches them by
  position; a row moves only when its place changed, because
  `appendChild` on an attached node is a remove and an insert.
  - **Filled only when what it shows changed** (#431): its session and
    children by object (`row.filledWith`), page facts such as the choice
    and the links by their text (`dataset.sig`). Filling 500 rows took
    34 ms a push.
  - **By object, because a session is never changed in place** (#435):
    every session the page holds is frozen, and `patchSession` is the one
    way to change one. **A session that reads the same stays the same
    object** (`takeSessions`, `sameOrNew`), or a stream's opening made
    every row new. **`opened` fails any test whose page wrote a frozen
    session.** `test_a_session_is_changed_only_by_patch_session`.
  - **A choice changes no session**, so it is in the signature, or the row
    chosen before kept its look. **A change no row's data shows goes
    through `redrawRows`**, which clears every signature: a closed rename
    box left its name empty. **`tickAges` reads the ages off the page**
    (`.age[data-since]`), so a row left alone still ticks.
    `test_a_push_fills_only_the_rows_it_changed`,
    `test_a_row_is_renamed_where_it_stands`.
