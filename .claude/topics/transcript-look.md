# The transcript: how it looks

Turns, Markdown, runs of tool calls, folds, the map, and gaps measured as
the reader sees them.

- **An edit opens onto what it changed, under the call that made it.** The
  reader turned down a diff column beside the tabs: it halved the diff's
  width. An `Edit` or `Write` answer carries `toolUseResult.structuredPatch`
  on the record, not the piece, so it goes to the record's one
  `tool_result`. `read_patch` keeps the hunks in the Diff tab's shape, at
  most `PATCH_SHOWN` lines, and none of `originalFile`, `content` or
  `gitDiff`: each is the file's size, on every edit. A `create`'s text is
  the change, split on `\n` only. **The counts come from the patch**: the
  strings carry the lines round the change. A failed call keeps none.
  `putToolDiff` draws it through `fillDiffFile` with `atEdit`: one column,
  no review `+`, no more of the file, since the numbers are the file's then,
  not now.
  `test_an_edit_keeps_what_it_changed_and_nothing_of_the_whole_file`,
  `test_a_long_change_is_cut_and_says_how_much_is_left`,
  `test_an_edit_opens_onto_what_it_changed`.
- **An opened call shows its whole input over what it printed** (#619,
  `call_text`, `Block.call`, `putCallText`): the line cuts a command at 60
  characters and folds its lines, and opened, a call showed only the
  answer. `call` is "" when the line already says it as it is, and a tool
  in `CALL_SAID` keeps none (a path, a pattern, a plan, an edit's change).
  A command is painted as `bash`, or `python` when Python runs it; any other
  input is JSON. **Opening a call fetches the highlighter** (`paintCall`),
  as opening a file does: the reader asked to read it. Cut at `CALL_SHOWN`
  lines on the wire, as a result is. **Whole, secrets and all**: the reader
  chose it (topics/safety). The colour replaces the text, so the find box
  marks it again.
  - **One card, the command on a ground of its own** (#631, `.toolcard`,
    `--cmd`): on one ground the reader could not see where the command
    ended and its output began. A rule between the two parts, and **each
    part copies itself** (`putCodeCopy`, the code block's button, in a box
    of its own, as a part scrolls and the button must not).
  `test_a_call_keeps_its_whole_input_when_its_line_cuts_it`,
  `test_an_opened_call_shows_its_whole_command_painted`.
- **A code block copies itself, from a box round it** (`putCodeCopies`,
  `.codebox`, `.copycode`). **The button is a child of the box, not the
  `pre`**: inside, a long line scrolls it away. **An icon, not the word**
  (`ICONS.copy`, then `ICONS.check`), so a search for "copy" does not mark
  every block. `markdown` adds it, so a Files tab document has it too.
  `test_a_code_block_copies_itself_from_a_button_that_shows_on_hover`.
- **A `note` is neither a round nor a reply**: `rounds()` takes only prompts
  and the agent's text, so the map is a map of the conversation. **A `plan`
  is a reply** (#372), named on the map by its title.
- **What the agent, the harness and the reader wrote is Markdown, and its
  text is one click away.** A `note` is `markdown` in `.bubble.prosebox`
  (#490), not a wall of `##` and `|`. Its `white-space` is normal:
  `.bubble`'s `pre-wrap` made the newlines between blocks blank lines.
  - **Every Markdown block has the Files tab's "txt"** (`putReadAs`, #493),
    kept in `state.turns.open` under `textKey`, so `forgetPlaces` forgets
    it. Lit, the block is `.source`, **and only its text changes** (#509):
    `.bubble` goes only on a prompt's and a note's. **Lit, the button stays
    put** (#510), or a second press misses.
  - **A prompt is Markdown too** (#500), with `breaks`
    (`markdown(..., true)`): without, a pasted log ran into one paragraph. A
    `!` or slash command stays as typed, in the fixed face.
  - `test_a_message_of_the_harness_is_markdown`,
    `test_a_block_shows_its_text_as_written_from_txt`,
    `test_a_prompt_is_markdown_in_its_own_box`.
  - **"context compacted" says when** (#499): the divider carries the
    record's `timestamp`, the line its `clock`, and `dayOf` when not today.
    `test_a_compaction_carries_its_moment`,
    `test_the_compaction_line_says_when`.
- **`.turn` has `align-items: flex-start`**: a flex item stretches to its
  row, so a tall `.who` left a one-line bubble's text over empty space.
  `test_a_one_line_message_sits_in_the_middle_of_its_block` compares the two
  gaps, not either number.
- **A group of tool calls belongs to the words above it: gaps 6 px above, 22
  below.** The agent says what it will do, then does it. **The CSS numbers
  are not the gaps**: margins collapse against `.turn`'s own 22, so above is
  22 + (−16), below max(5, 22). Change one and measure it.
  - **Two or more calls in a row are one line until the reader opens them**
    (#465, `foldRun`, `foldRuns`, `runOf`, `fillCallSum`, `.callrun`,
    `.callsum`, `RUN_FOLDS`), or the words are islands in a list of calls.
    The line counts the calls, names the most used tools, sums the edits'
    `+`/`−`, and counts the failures. **The line is one more `.turn.toolrow`
    before the calls, which stay flat siblings, never a box round them**:
    `patchTranscript` appends a block by index, and the gaps rest on `+`. A
    folded call is `hidden`; the gap tests measure the line shut and open.
    - **Which runs are open is `state.turns.open`, under `runKey`**: a mark
      on the node is lost on the next draw.
      `test_a_run_opened_stays_open_through_a_redraw`.
    - **Everything that reaches a call opens its run, or points at its
      line**: a find that matches, `landOnBlock` (a hidden node has nowhere
      to scroll), and the "new" line, which goes over the run.
    - **A call folded on arrival loses `fresh`**, or it slides in when shown
      later.
    - **A run of one is not folded**: its line would be as tall as the call.
    - **A run that forms round a call the reader opened is open** (#620,
      `openFormedRuns`): the reader opened the lone call to read it, the
      next call folded both, and the text went mid-read. Set in
      `mergeBlocks`, where blocks arrive, never in `foldRun` (a draw only
      reads). **Only a run that forms**: one the reader folded stays
      folded when it grows, an open call in it or not.
      `test_a_call_the_reader_opened_stays_open_when_the_next_call_comes`.
    - `test_calls_in_a_row_are_one_line_until_the_reader_opens_them`,
      `test_a_run_grows_as_its_calls_arrive`,
      `test_a_find_that_matches_a_folded_call_shows_its_run`,
      `test_landing_on_a_folded_call_opens_its_run`,
      `test_the_new_line_over_a_folded_call_stands_over_its_run`.
- **A message too long to read is drawn folded** (`foldedHead`,
  `putFoldBar`, issue 329), or a pasted log puts fifty screens between
  question and answer. Past `FOLD_LINES` or `FOLD_CHARS`, a prompt, note,
  reply or `!` output shows its first `FOLD_SHOWN` lines, faded, in a
  `.foldbox` over a `.foldbar` ("show all 2.4k lines · 188 KB", `roughly`);
  a short one has no box.
  - **Counted with `indexOf`, never a split**, as `lineCount` does: a split
    on every redraw is the cost the fold saves.
  - **A find that matches the message draws it whole**, or the hit is
    hidden. `test_a_search_opens_a_folded_message_where_it_matches`.
  - **Open, the bar is sticky at the pane's foot, at the right**, so a log
    folds from its middle; at the left it covered a line's start. **Folding
    calls `scrollIntoView`**, or the reader is left far below.
    `test_folding_from_the_foot_of_the_pane_keeps_the_message_in_sight`.
  - **The bar is in the sans face, and the count is "2.4k"**: the fixed face
    and "2,401" took two rows (issue 332).
  - **It opens through `state.turns.open`** (`PLACE_FIELDS`).
  - `test_a_long_message_is_drawn_folded_and_opens_and_folds_again`,
    `test_a_message_short_enough_is_drawn_as_it_always_was`.
- **Measure a gap from what the reader sees, not from the box.** Box to box
  said 6 px while the reader saw 39: `.who` set the height of every one-line
  turn.
  - **When a call comes next, the column may run down beside it**, as the
    call's `.who` is empty: `:has(+ .turn.toolrow)`. **The overhang is
    capped at 36 px**, what one call and its gap hold. **It carries
    `z-index`**, or the calls, later positioned siblings, cover it.
  - **A test that measures straight after a push waits for
    `document.getAnimations()` to be empty**: a sliding block is a stacking
    context for 0.15 s.
  - `test_a_group_of_calls_sits_under_the_line_that_announced_it` measures
    from the text; each of its five parts fails it.
- **What a turn can do is one row at its top right, out of the flow, and
  `.who` holds words only** (`.turnacts`, #520, #522): in `.who` the buttons
  sat on the next turn and took width a small screen needs. Copy, "txt" and
  bookmark, in the reader's order (#527). `.who` is 44 px with `nowrap`: a
  bold "14 Oct" broke at 40. **Each button is hidden, not removed**
  (`visibility`), so a lit one never moves (#510) and a saved bookmark
  stands where hover shows it. **The row has a ground only on hover**, or
  text shows between the buttons. The copy is the code block's icon, ticked
  by `flashOutcome`. **The day wears the time's colour and weight** (#519):
  "14 Oct 09:10" is one moment.
  `test_what_a_turn_can_do_is_one_row_at_its_top_right`,
  `test_a_day_wears_the_time_s_colour`.
  - **A saved bookmark keeps no room; it is a flag with no box** (#632,
    which turned #526 round on the reader's word): kept room made the text
    wrap further left the moment it was saved. Without the hover the flag
    stands alone over the first line's end (`.turn:not(:hover) > .turnacts
    > .save.on`). A lit "txt" needs none either: `.source` keeps its own.
    `test_a_saved_mark_moves_no_words`.
  - **The row's ground is the ground under it** (`--acts-ground`, #527): the
    prompt's tint (`--mine-soft`) is see-through, so the row lays it over
    `--bg` as a gradient, as the box does.
    `test_the_row_of_buttons_wears_the_ground_under_it` reads drawn pixels,
    as a ground is in no computed style.
- **A column may hang 10 px past its turn, no more**: the next prompt's rule
  is 12 px down (its `::before`, 26 − 14). A taller `.who` made the gaps
  seen 32 and 59 px, not the 22 and 26 meant.
  `test_the_gap_a_reader_sees_after_a_prompt_or_a_line_is_the_gap_meant`
  fails with a larger overhang.
- **The way back to the transcript's end hangs off the content box, and
  `split` builds it.** A new block carries the reader along only while
  `nearBottom`. `.tofoot` cannot be in `.turnbody`, whose children
  `drawTranscript` replaces. **So `split` returns `box.children[2]`, not
  `box.lastChild`**: the last child is this button. A round `.verb`
  mid-foot, `ICONS.down` alone as the reader asked, the words in `title` and
  `aria-label`. It sets `display`; the one `[hidden]` rule still hides it.
  `test_the_way_back_is_an_arrow_in_the_middle`.
- **`showToFoot` is handed both nodes; never look the button up.** It runs
  on every scroll event and push, and `box.querySelector(".tofoot")` walks
  the whole transcript first.
- **`GLIMPSE` must clear what the widest map column can show.**
  `.filelist .name` clips with an ellipsis; `GLIMPSE` only bounds what
  enters the DOM, and at 44 every row ended in a needless "…". **Measure it;
  do not divide**: at `dragWidth`'s cap of 700 px, 176 of the narrowest
  glyphs fit in the `--narrow` face, so 200 clears it.
- **The map wears the lists' face, and its rows stay close.** Every list on
  the left (map, file trees, comments) is `--narrow` at 13 px (#448), as the
  reader asked, with 1 px above and below a row.
  `test_the_map_wears_the_lists_face_and_a_prompt_is_round` compares the
  map's face with a bare `.filelist`'s, so the lists move together.
- **A round on the map does not fold, and a prompt is in bold** (#512). The
  fold, kept by `savePlace`, went on the reader's word. **Ask the reader
  before putting it back.**
  `test_a_round_on_the_map_does_not_fold_and_a_prompt_is_bold`.
- **The map marks where each day starts** (`mapDays`, `.mapday`, #512), over
  each day's first round by its own time, **only when the rounds span more
  than one day**. **Today is in `drawTurnList`'s redraw key**, or "Today"
  stays after midnight. `test_the_map_marks_where_each_day_starts`.
- **The map's icons say who spoke**: a prompt is `ICONS.person`, a reply
  `ICONS.robot` one step in, under the words it answers.
  `test_the_map_says_who_spoke_and_a_reply_stands_under_its_prompt`.
- **The find box narrows the map, never the transcript**: taking turns out
  took away the conversation round a hit. `onlyMatching` filters the map;
  `markHits` marks hits in place, or a hit scrolled past is missed.
- **One block redrawn alone is still marked.** `redrawBlock` is the
  Transcript tab's `fillDiffFile`: it does to a node all that
  `drawTranscript` does.
