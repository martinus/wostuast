# The transcript: how it looks

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. Turns, Markdown, runs of tool calls, folds, the map down the side, and gaps measured as the reader sees them.

- **An edit opens onto what it changed, under the call that made it.** The
  reader wanted the words and the change read together; a transcript column
  beside the tabs was pictured and turned down, because the diff lost half
  its width. The record answering an `Edit` or a `Write` carries
  `toolUseResult.structuredPatch` -- on the record, not on the piece, so it
  goes to the one `tool_result` a record holds -- and `read_patch` keeps its
  hunks in the Diff tab's shape, `PATCH_SHOWN` lines of them, and none of
  `originalFile`, `content` or `gitDiff`: the size of the file, on every
  edit, and every block goes to the page. A `create` has an empty patch and
  its text is the change, split on `\n` only. **The counts come from the
  patch**: from the strings an Edit said "+3 −2" for one line added,
  because the strings carry the lines round the change. A failed call keeps
  none. `putToolDiff` draws it through `fillDiffFile` with `atEdit`: one
  column whatever the Diff tab says, and no review `+` and no more of the
  file, because the numbers are the file's at that moment and not now.
  `test_an_edit_keeps_what_it_changed_and_nothing_of_the_whole_file`,
  `test_a_long_change_is_cut_and_says_how_much_is_left`,
  `test_an_edit_opens_onto_what_it_changed`.
- **A code block copies itself, from a box round it** (`putCodeCopies`,
  `.codebox`, `.copycode`). The reader asked for it: what an agent puts in
  a fence is most often a command or a file to take somewhere else, and
  selecting it by hand takes the line above with it. The button is a child
  of the box, not of the `pre`: inside, a long line scrolls it away with
  the code. It is an icon (`ICONS.copy`, then `ICONS.check` when the copy
  worked) and not the word, so a search for "copy" does not mark every
  block. It shows on the block's hover and on keyboard focus, as a reply's
  copy does on its turn. `markdown` adds it, so a document on the Files
  tab has it too.
  `test_a_code_block_copies_itself_from_a_button_that_shows_on_hover`.
- **A `note` is neither a round nor a reply.** `rounds()` takes prompts and
  the agent's text and nothing else, so the map stays a map of the
  conversation. **A `plan` is a reply** (#372): it is the agent's words, and
  the map names it by its title.
- **What the agent, the harness and the reader wrote is Markdown, and its
  text is one click away.** A `note` was text
  in its dashed box, and a subagent's report read as a wall of `##` and
  `|` (#490): it is `markdown` inside `.bubble.prosebox`, whose `white-space`
  is normal, because `.bubble`'s `pre-wrap` made the newlines between the
  blocks blank lines. Every block drawn as Markdown has the Files tab's
  "txt" (`putReadAs`, #493), kept in `state.turns.open` under `textKey`, so
  `forgetPlaces` forgets it with the rest; lit, the block is `.source`,
  **and only its text changes** (#509): an answer's source stood in a
  bordered box, a look of its own, while a prompt's kept its box; now
  `.bubble` goes only on a prompt's and a note's. **Lit, the button stands
  where it stood** (#510): it stepped 6 px in, and a second press missed. **It stands at the block's top right, out of the flow**
  (`.turnacts`): under the time it stood on the next turn's name after a
  one-line reply, and on the time's line it ran past `.who`'s 64 px into
  the pane's edge, which cut it. **A prompt is Markdown too** (#500):
  the reader asked for it by default, after a first round that kept it as
  typed. It is drawn with `breaks` (`markdown(..., true)`), as a chat box
  and a GitHub comment draw it: without, a log pasted into a prompt ran
  together into one paragraph, and the fold's count of lines was 1. A `!`
  or slash command stays as typed, in the fixed face.
  `test_a_message_of_the_harness_is_markdown`,
  `test_a_block_shows_its_text_as_written_from_txt`,
  `test_a_prompt_is_markdown_in_its_own_box`.
  - **"context compacted" says when** (#499): the divider block carries the
    record's `timestamp`, and the line its `clock`, with `dayOf` when it
    was not today, as the "new" line says since when.
    `test_a_compaction_carries_its_moment`, `test_the_compaction_line_says_when`.
- **A `.turn` lays out from the top, not stretched.** `.who` carries a name,
  a day, a time and a copy button — 71 px of them, measured — and a flex item
  stretches to its row by default, so a one-line bubble was 71 px tall with
  the text 14 px from the top and 41 px of nothing under it. It read as text
  that is not centred; it was a block that is not the size of its contents.
  `align-items: flex-start` on `.turn` is the whole fix, and
  `test_a_one_line_message_sits_in_the_middle_of_its_block` compares the two
  gaps rather than either number.
- **A group of tool calls belongs to the words above it.** The agent says
  what it is about to do and then does it. The gaps were 16 px above and
  16 px below — exactly equal, measured — so the group read as belonging to
  neither, and to the reply below it, which is the thing you next want to
  read. They are 6 and 22 now. **The numbers in the CSS are not the gaps**:
  the margins collapse against `.turn`'s own 22, so above is 22 + (−16) and
  below is max(5, 22). Change one and measure it; do not read it off.
  - **Two calls or more in a row are one line until the reader opens them**
    (#465, `foldRun`, `foldRuns`, `runOf`, `fillCallSum`, `.callrun`,
    `.callsum`, `RUN_FOLDS`). One sentence, ten calls, one sentence, nine:
    the words were islands in a list nobody reads. The line counts the
    calls, names the tools most used first, adds up the edits' `+`/`−` and
    says how many failed. **The calls stay flat siblings and the line is
    one more `.turn.toolrow` in front of them**, never a box round them:
    `patchTranscript` appends a block by its index, and the gaps above rest
    on `+` between turns. A folded call is `hidden`; the rules for its gaps
    hold for the line, shut or open, and the gap tests measure both.
    - **Which runs are open is `state.turns.open`, under `runKey`**, beside
      the opened calls, so a session keeps it and a rewrite forgets it. A
      mark on the node was lost on the next draw, and a keystroke in the
      find box is one. `test_a_run_opened_stays_open_through_a_redraw`.
    - **Everything that reaches a call opens its run, or points at its
      line**: a find that matches one (the folded message's scar),
      `landOnBlock` (a hidden node has no place to scroll to), and the
      "new" line, which goes over the run's line, not under it.
    - **A call folded on arrival loses `fresh`**: shown later, it slid in
      then, and the gap test measured it 4 px off mid-slide.
    - A run of one is not folded: its line would be as tall as the call.
    `test_calls_in_a_row_are_one_line_until_the_reader_opens_them`,
    `test_a_run_grows_as_its_calls_arrive`,
    `test_a_find_that_matches_a_folded_call_shows_its_run`,
    `test_landing_on_a_folded_call_opens_its_run`,
    `test_the_new_line_over_a_folded_call_stands_over_its_run`.
- **A message too long to read is drawn folded** (`foldedHead`,
  `putFoldBar`, issue 329). A log pasted into a prompt ran to 140 KB, and the
  transcript drew all of it: fifty screens between the question and its
  answer. Past `FOLD_LINES` or `FOLD_CHARS` a prompt, a note, a reply or a
  `!` command's output shows its first `FOLD_SHOWN` lines, faded, in a
  `.foldbox` with a `.foldbar` under it ("show all 2.4k lines · 188 KB",
  `roughly`); a short one is drawn as it always was, with no box. Each part
  is a scar or the reader's word:
  - **Counted with `indexOf`, never a split**: a split of 140 KB on every
    redraw is what the fold saves. `lineCount` is the same.
  - **A find that matches the message draws it whole**, or the hit is in
    the part nobody can see. `test_a_search_opens_a_folded_message_where_it_matches`.
  - **Open, the bar is sticky at the foot of the pane, at the right**, so a
    reader folds the log from its middle and not from its end, 2,000 lines
    down; at the left it covered the start of a line. Folding then calls
    `scrollIntoView`, or the reader was left far under what was left of it.
    `test_folding_from_the_foot_of_the_pane_keeps_the_message_in_sight`.
  - **The bar is in the sans face, and the count is "2.4k"**: the reader
    said no to the fixed face and to "2,401", which took two rows over the
    send button (issue 332).
  - **It opens through `state.turns.open`**, the set a tool call opens
    with, so a session keeps it (`PLACE_FIELDS`).
  `test_a_long_message_is_drawn_folded_and_opens_and_folds_again`,
  `test_a_message_short_enough_is_drawn_as_it_always_was`.
- **Measure a gap from what the reader sees, not from the box.** Three
  rounds of this fix measured turn box to turn box, got 6 px each time, and
  the reader still saw 39. `.who` — a name, a time, the copy button, and a
  day when it was not today — was 55 px on one day and 71 across two, and
  one line of text is 22, so the column set the height of every one-line
  turn.
  When a call comes next, the column may run down beside it: the call's own
  `.who` is empty. `:has(+ .turn.toolrow)` says so, and answers again by
  itself when a block arrives. The overhang is
  capped at 36 px, which is what one call and the gap after it can hold;
  more ran the column into the next turn's name. It carries `z-index`, or the
  calls — later, positioned siblings — cover the copy button. And a block
  sliding in is a stacking context for 0.15 s, so a test that measures
  straight after a push waits for `document.getAnimations()` to be empty.
  `test_a_group_of_calls_sits_under_the_line_that_announced_it` measures from
  the text, and each of its five parts fails it.
- **What a turn can do is one row at its top right, and `.who` holds words
  only** (`.turnacts`, #520, #522). The copy, the "txt" and the bookmark
  stand there in that order, the reader's (#527); a lit one never moves
  (#510), because a hidden one keeps its room. In
  `.who` the bookmark and the "copy" word held the column at 64 px, room a
  small screen needs for the text; it is 44 now, the width of "system", with
  `nowrap`, because a bold "14 Oct" broke in two at 40. **Each button is
  hidden, not taken away** (`visibility`): the row is out of the flow, so a
  hidden one takes no room from the text, and a saved bookmark, shown
  without the hover, stands where the hover shows it. **The row has a
  ground only on the hover**: without it, the text showed through the 4 px
  between two buttons. The copy is the code block's icon, and `flashOutcome`
  ticks it. The day wears the time's colour and weight (#519): "14 Oct
  09:10" is one moment, and faint it read as a note.
  `test_what_a_turn_can_do_is_one_row_at_its_top_right`,
  `test_a_day_wears_the_time_s_colour`.
  - **A turn with a mark that stays keeps the row's room on its right**
    (`.turn:has(> .turnacts > :is(.on, [aria-pressed="true"]))`). A saved
    bookmark shows without the hover, and stood on the words of a reply
    whose first line ran to the edge: the cover picture of #521 showed it,
    after #526 had merged. Only such a turn: every turn keeping 92 px would
    take back what the narrow column gave. `test_a_saved_mark_stands_on_no_words`.
  - **The row's ground is the ground under it** (`--acts-ground`, #527). On
    a prompt it was the page's dark `--bg`, which showed between the
    buttons over the box's tint. The tint (`--mine-soft`) is see-through,
    so the row lays it over `--bg` as a gradient, as the box does; the tint
    alone would be the page showing through, and the tint over the box would
    be twice the tint. `test_the_row_of_buttons_wears_the_ground_under_it`
    reads the drawn pixels, because a ground is in no computed style.
- **A column may hang 10 px past its turn.** On a line of its own under the
  time, the copy button once made `.who` 55 px tall, taller than a line of
  text (22) or a prompt's bubble (45), so the gap a reader saw was 32 px
  after a prompt and 59 after a one-line reply before a prompt, where 22
  and 26 were meant. What is still past the
  words hangs into the gap: 10 px, because the rule over the next prompt is
  12 px down (its `::before`, 26 − 14) and the next turn's name 25. More
  than that runs the column into the rule. `next-tool` allows 36 where a
  call comes next, whose column is empty.
  `test_the_gap_a_reader_sees_after_a_prompt_or_a_line_is_the_gap_meant`
  measures from the bubble and the text, and fails with a larger
  overhang.
- **The way back to the end of the transcript hangs off the content box, and
  `split` builds it.** A new block carries you along only while `nearBottom`,
  which is right, and nothing said how to start following again. `.tofoot`
  cannot live inside `.turnbody`, whose children `drawTranscript` replaces
  wholesale, so it is a child of the box — built by `split`, like every other
  part of the frame, because building it in `drawTranscript` put half of the
  box's positional contract in another function. **That is why `split`
  returns `box.children[2]` and not `box.lastChild`**: the last child is this
  button. It is a `.verb`, which is where its border, background and hover
  come from; `.tofoot` makes it a round button in the middle of the pane's
  foot with `ICONS.down` in it, the words in `title` and `aria-label` --
  the reader asked for the arrow alone. It sets `display` to centre the
  arrow; the one `[hidden]` rule hides it all the same (below).
  `test_the_way_back_is_an_arrow_in_the_middle`.
- **`showToFoot` is handed both nodes, and this is not a nicety.** It runs on
  every scroll event — dozens of times in one gesture — and on every pushed
  block. `box.querySelector(".tofoot")` is a pre-order walk that reaches the
  button only after crossing the whole transcript: on a long one, a hundred
  thousand nodes visited to set one boolean. Every caller already holds the
  button and the pane.
- **`GLIMPSE` is not where the map's preview ends.** `.filelist .name` clips
  with an ellipsis at whatever width the column has been dragged to;
  `GLIMPSE` only bounds what goes into the DOM for a reply that may be
  kilobytes long. It was 44, narrower than the column at its default width,
  so every row ended in a "…" the column had room for and the number did not.
  **It has to clear what the widest possible column can show**, or it is the
  clip again. Measured at `dragWidth`'s cap of 700 px, where the name box is
  639 px: 49 of the widest glyphs and 176 of the narrowest. The list was a
  condensed sans, so the thin end sets it — a number reasoned out from
  monospace character widths came to 120 and would have clipped a line of
  narrow letters, which is the bug being fixed. Measure it; do not divide.
  The map wears the lists' condensed face again (#448), the face this was
  measured in, so 200 still clears the 176 narrowest; a narrower face would
  not.
- **The map wears the lists' face, and its rows stay close.** Every list
  down the left -- the map, the file trees, the comments -- is `--narrow`
  at 13 px, the one face (#448): set like the transcript at 14 px, it read
  as a different page beside the Files and the Review tabs' lists, and the
  reader asked for one. That reversed an older rule, which had set it like
  the transcript because the lists' 29 px rows read as another page: the
  rows keep 1 px above and below, so a row still comes about every line.
  `test_the_map_wears_the_lists_face_and_a_prompt_is_round` compares the
  map's computed face with a bare `.filelist`'s, so the lists move together.
- **A round on the map does not fold, and a prompt is in bold** (#512).
  A chevron in front of each prompt folded its replies away, with
  `state.turns.shut` in the redraw key and in `savePlace`. The reader never
  used it, and it held every row of the map one tree step to the right. The
  row has one job now: the whole of it goes to that place in the
  transcript. The reader's own words are in bold, so they stand out from
  the replies under them. Before a fold is put back, ask the reader: it was
  taken out on their word.
  `test_a_round_on_the_map_does_not_fold_and_a_prompt_is_bold`.
- **The map marks where each day starts** (`mapDays`, `.mapday`, #512). A
  long session was a column of prompts, and nothing said where one day
  ended. A line names the day a round starts on -- "Today", "Yesterday",
  "Fri 18 Sep" -- over the first round of each day, by the round's own
  time, so a round that ran past midnight stays under the day it was asked
  on. **Only when the rounds span more than one day**: a "Today" over a
  session of one afternoon is a line of nothing. The day of today is in
  `drawTurnList`'s redraw key, or "Today" stays on the lines after
  midnight. `test_the_map_marks_where_each_day_starts`.
- **The map's icons say who spoke.** A folder and a page said "a round
  holds replies", which is the list's shape and not what a row is, so a
  prompt is `ICONS.person` and a reply `ICONS.robot`, one tree step in, so
  it stands under the words it answers.
  `test_the_map_says_who_spoke_and_a_reply_stands_under_its_prompt`.
