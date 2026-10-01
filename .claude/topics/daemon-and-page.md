# The daemon and the page

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. Routes, the stream, the transcript's shape and the live slot.

- **Every route lives in `Serving`**, a module-level class that subclasses
  nothing. `make_server` mixes it with `BaseHTTPRequestHandler` and puts the
  daemon on that subclass, so a route reads `self.daemon`. The `http.server`
  import stays inside `make_server`: 10.8 ms for a bare interpreter against
  49.5 ms for one that has imported it, and **the hook pays for every import
  on every tool call**. `test_the_hook_does_not_import_what_it_does_not_need`
  fails if that slips.
- **`name` is a POST that writes no terminal.** It keeps a name in
  `names.json`, and the row shows no other: Claude Code hands the status
  line the name the session started with and `/rename` does not change it. `Store.rename` replaces the whole map rather than editing it,
  the trick `rows` plays: the HTTP thread writes, the fold thread reads. It
  pushes nothing — the rows are built from the names every pass, so the next
  one differs and goes out on its own.
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
- **A link to a turn is `#<session>/<seq>`, and `seq` is a place in one
  reading.** A session resumed from another directory counts from nought
  again, so an old link can name a turn that is no longer there. `landOnBlock`
  does nothing then, and that is the whole of the failure. It also wins over
  the usual landing at the foot of the transcript exactly once: `state.goToBlock`
  is cleared the moment it lands, or a live session would drag the reader back
  to it every second. **`#<session>` alone is the session on screen**:
  `choose` writes it with `replaceState`, which fires no `hashchange`, so a
  reload comes back to that session and not to the first row. **Only when
  the address names another session**: rewritten always, a link to one
  reply lost its `/<seq>` the moment it opened, and
  `test_a_reply_is_a_link_you_can_open_in_another_tab` went red.
  **`seq` is digits and nothing else** (`placeInHash`): `Number("")` is 0,
  so `#s1/` was a link to the first block, and `Number` takes " 3", "1e2"
  and "0x10" too. `test_a_link_to_a_block_is_digits_and_nothing_else`.
- **A session can be chosen before the session list exists.** The address bar
  holds a link at startup, so `choose` runs with `state.sessions` empty —
  `current()` is null and every tab draws its empty state. The `sessions`
  event draws again when the chosen session turns out to be real; without
  that, a linked page stayed empty until the reader clicked a row.
- **A `user` record is not always a prompt.** Claude Code writes its own:
  one `/reload-plugins` arrives as three or four records of tags, and
  `(no content)` was drawn as something the reader had typed.
  `read_user_text` reads one for what it is — a command becomes one line
  saying what was run, the resumed-session caveat is dropped, and a task notification or another session's message becomes a
  `note`, which is shown but never wears the reader's rail. **A record is
  only read as a command when there is nothing else on it**: a prompt really
  can hold `<command-name>` in it, because somebody asking about this very
  feature types one. **Nor is an interrupt**: every Escape that stops a turn
  makes Claude Code write `[Request interrupted by user]`, or `... for tool
  use]` after a declined dialog, as a `user` record -- and every decline
  from the page drew it as a prompt and named a round after it.
  `INTERRUPTED` makes the whole record, exactly, a note.
  `test_an_interrupt_claude_code_wrote_is_a_note_not_your_prompt`.
  - **A task notification is its summary and its result.** It is a block
    of fields -- `task-id`, `tool-use-id`, `output-file`, `status`,
    `summary`, and at times `note`, `result` and a `usage` of numbers --
    and the page took the outer tag off and drew the rest: 272 notes of
    tags on one machine, which `wostuast shapes` found. `task_note` keeps
    the summary and the result; a notification in a shape nobody has
    measured is shown as it came. **Another session's message is its
    words** (`AGENT_MESSAGE`): a header line in a `user` record and none
    in a queued one, the words in `<agent-message from=…>`, and after it a
    paragraph Claude Code writes to the agent about the sender. The header
    was guessed away in the first fixture, and `shapes` caught it on a real
    transcript: read the record, not its skeleton. Five shapes, measured on
    2.1.276 to 2.1.283, in `tests/fixtures/notes.jsonl`.
    `test_a_task_notification_and_another_sessions_message_read_as_words`.
  - **A `!` command is two records, and one block.** `!git up` writes
    `<bash-input>git up</bash-input>`, then
    `<bash-stdout>...</bash-stdout><bash-stderr>...</bash-stderr>` with `<`,
    `>` and `&` as HTML entities; neither is `isMeta`, so both were drawn
    as prompts, tags and `-&gt;` and all. `BASH_INPUT` makes a `shell`
    block, and `shell_output` puts what it printed into that block -- only
    one not yet answered, or two runs of one command merge -- with
    `html.unescape`, which is exact because the `&` was escaped too. Only
    a record that is the tag and nothing else, like `<command-name>`. The
    page draws it on the reader's rail in the fixed face, the output as
    text and `white-space: pre`, and the map names the round `! git up`.
    Measured on 2.1.282, `tests/fixtures/bash_mode.jsonl`.
    `test_a_command_run_with_a_bang_is_one_block_with_its_output`,
    `test_a_bang_command_is_drawn_with_its_output_in_the_fixed_face`.
  - **A slash command is one block with its answer, in the same shape.**
    `/model opus` sent from the send box changed the model and the page
    showed the command alone: its answer, "Set model to `Opus 5.5`", was
    dropped as plumbing, and no hook fires for a slash command, so nothing
    said what it did. `command_output` puts `<local-command-stdout>` into
    the command's `command` block, which the page draws as a `shell` one
    with its own `/` instead of a `!`. "(no content)" closes the block and
    draws nothing. **Two shapes, both read**: 2.1.283 writes `/model opus`
    as `user` records and `/model` closed without a pick, or `/context`, as
    `system` records with `subtype: local_command` and the text in
    `content` -- `Transcript.add` read no `system` record but the
    compaction's. **And the colour codes come off** (`ESCAPE_CODES`, then
    `CONTROL_CHARS`): `/context` draws its grid in them, measured. A command
    nobody typed is a note, like any other words that are not the reader's.
    **An `isMeta` record straight after an answer is the answer again**, as
    Markdown for the agent: `/context` writes one, and the page drew its
    numbers twice. `echo_of` drops it -- only straight after, only once, and
    not after "(no content)": `/init` sends its prompt as an `isMeta` record
    with no answer before it, measured, and that one is shown.
    `tests/fixtures/local_command.jsonl`. **`<local-command-stderr>` is
    not read yet, on purpose**: the 2.1.285 bundle writes one for a command
    that failed, with `commandOutcome` `failed`, but no record of it has
    been read on any machine, and `payloads.md` says a shape is recorded,
    never guessed. Record one before handling it.
    `test_a_slash_command_and_what_it_answered_are_one_block`,
    `test_a_slash_command_is_drawn_with_what_it_answered`.
- **`wostuast shapes` is how a new Claude Code shape is found before the
  reader finds it.** Every bug of this kind -- `!git up`, `/clear`,
  `/model`, paste tags on the row -- was reported as tags on the screen.
  `transcript_shapes` reads recent transcripts through `Transcript.add`
  itself and lists records and pieces it leaves out that are not on
  `SILENT_RECORDS`, and Claude Code's tags (`MACHINE_TAG_NAME`: a hyphen or
  an underscore, which typed HTML has not) left in a prompt, a note or a
  command. **A tag counts only when it is closed too, and in a prompt only
  when the prompt opens with it**: the reader's first run listed
  `<uint32_t>` out of C++, `<commit-hash>` placeholders out of skills, and
  two bug reports about this page that quoted tags after their own words. **Names and counts, never text**, so the output can go into a
  public issue as it is. **A name goes on `SILENT_RECORDS` only after a
  real record of it was read**: the queued message was an attachment
  nobody looked at. **It splits on `\n`, never `splitlines()`**: U+2028
  inside a string cut 17 records in half on the first machine it read, the
  diff scar again. Its first run found task notifications drawn with their
  inner tags and pasted images not drawn at all.
  `test_shapes_lists_what_the_page_cannot_show_and_never_the_text`,
  `test_shapes_reads_only_the_days_asked_for`.
- **A message sent to a busy agent comes back wrapped, and the wrapper is not
  yours.** Claude Code queues it into the running turn and writes a header
  (`The user sent a new message while you were working:`), the words typed,
  and a footer explaining the queueing to the agent -- all inside a
  `<system-reminder>`. It is a `user` record, so all three were drawn as the
  reader's own prompt, and the map named the round after the header. This is
  the shape a reader of *this* program meets most, because every message this
  page sends to a working agent takes it. `QUEUED` keeps the middle.
  **Order matters**: the reminder tags come off first (`strip_reminder`), and
  the message is pulled out *before* `MACHINE_TAG` runs -- `system-reminder`
  is on that list now, so stripping first would take the message with it.
  The header must open the record and the footer must be there, or a person
  quoting the wrapper to ask about it -- which is how this was reported --
  gets their question answered with its own quotation.
- **Pasted text comes off Claude Code's paste tags, by Claude Code's own
  rules.** A Claude Code that keeps a paste apart from what was typed writes
  it into the record after the typed text as two newlines,
  `<pasted_content id="1da8">`, the text, and `</pasted_content id="1da8">`
  -- and its own screen takes them off again. This page drew them, so every
  review sent from here came back as a block of tags under two empty lines,
  and the map named the round after the tag: a review has newlines, so it
  is always a paste. `unwrap_pastes` is a port of the reader in its bundle
  (`Pct`): four lowercase hex digits, the same on both tags, each tag on its
  own line, up to two newlines either side belonging to the wrapper, and
  anything else left as typed -- a person asking about the tag types one.
  It runs first in `read_user_text`, so a paste inside a queued message
  comes off too. **And in `_on_prompt`**: the hook hands over the prompt as
  Claude Code wrote it, so the row read `prompt: <pasted_content
  id="3400"> I got...` while the transcript beside it was clean.
  `test_the_row_shows_a_pasted_prompt_without_its_tags`. Measured on 2.1.281, which does not wrap on this machine:
  a feature switch decides, so the shape comes from its source and the
  reader's record, not from a run here.
- **A message queued while the agent works is an `attachment`, and it is
  read.** 2.1.276 to 2.1.281 write it as a `queued_command` attachment and
  no `user` record follows -- counted on a real machine: eighteen queued
  prompts, not one anywhere else. `Transcript.add` read `user` and
  `assistant` only, so the page showed the agent answering words that were
  not on it, and this page's own send box is how most of them are typed.
  `add_queued` reads it through `read_user_text`; `origin.kind` human is a
  prompt, a peer's message or a task's news a note, and every other
  attachment stays out. **One with no `commandMode` is a note**, and stays
  one until such a record is read: 441 read on one machine, 2.1.276 to
  2.1.285, all carried it. A note is still shown, and the reader's rail on
  words that are not theirs is the worse mistake.
  `test_a_message_queued_while_the_agent_works_is_drawn`.
- **`isMeta` is Claude Code speaking, never the reader.** A Stop hook's
  answer, a whole skill's body, "Continue from where you left off.", an
  image's caption: each came as a `user` record with `isMeta`, wore the
  reader's rail, and opened a round on the map named after it. `user_block`
  turns what would be a prompt into a note, for a string and for pieces
  alike. `test_what_claude_code_wrote_itself_is_never_your_prompt`.
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
  conversation.
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
- **Thinking is never drawn, and the daemon never makes it a block.**
  Claude Code keeps the text of most thoughts out of the transcript: 4,274
  of 4,785 thinking blocks on one machine were a signature and nothing
  else. A `t` that showed them showed nothing most of the time and read as
  broken, even after it said so in the live slot; the reader chose to drop
  thoughts and the key. `Transcript` returns no block for a `thinking`
  piece, so nothing on the page can count, draw or search one. It also
  ended a CSS workaround: a hidden thought was still a sibling to `+`, and
  `pastThought`, `markNext` and the `past-tool`, `past-words` and
  `next-tool` classes stood in for it. With no thoughts the plain `+` and
  `:has(+ ...)` rules are right again.
  `test_thinking_is_never_a_block_even_with_text_in_it`,
  `test_a_thought_between_two_tool_calls_leaves_no_trace`.
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
- **The copy button stands on the time's line, and a column may hang 10 px
  past its turn.** On a line of its own the button made `.who` 55 px tall,
  taller than a line of text (22) or a prompt's bubble (45), so the gap a
  reader saw was 32 px after a prompt and 59 after a one-line reply before
  a prompt, where 22 and 26 were meant. `.who .stamp` holds the time and the
  button; the column is 35 px now, 51 with a day. What is still past the
  words hangs into the gap: 10 px, because the rule over the next prompt is
  12 px down (its `::before`, 26 − 14) and the next turn's name 25. More
  than that runs the column into the rule. `next-tool` allows 36 where a
  call comes next, whose column is empty.
  `test_the_gap_a_reader_sees_after_a_prompt_or_a_line_is_the_gap_meant`
  measures from the bubble and the text, and fails with the button back on
  its own line or with a larger overhang.
- **The send box and the question bar start where the transcript does, and
  the map runs down beside them.** Both stand under a split tab's right
  half, and both used to run the whole width and under the map beside it — a
  column you never type into. A `margin-left` fixed that and left the map
  and its grip stopping short above them, with an empty corner under the map
  that nothing could drag. Now `.main` is a grid whose columns are the split
  tab's own — `--side-w`, `--grip-w`, the rest. `.content` spans every row
  under the tabs; the two bars take the third column of the last two rows,
  over it; and `.content.split` hands those rows and columns to its children
  with `subgrid`, so the map and the grip span every row and the pane only
  the first. **By the grid, not by moving them into the pane**: the question
  bar holds picks that have not been submitted and the send box holds what
  you are typing, and a node that changes parents is a node that is rebuilt.
  Two things this costs, both of them bugs that happened on the way in:
  - **The bars carry `position: relative`.** `.content.split` is positioned,
    and a positioned box paints over every sibling that is not, so it sat on
    top of both bars and took every click on an answer and into the box.
  - **`.tofoot` is a grid item in the pane's cell, not `position: absolute`
    against the box.** The box now runs down behind the send box, and an
    absolute child with a grid area was measured from the whole box, not
    the area — the box is a subgrid, and Chromium did not honour it.
  `test_the_map_and_its_grip_run_down_beside_the_send_box` holds the layout
  and the button; the question and send-box tests in `test_page_act.py` are
  what catch the clicks.
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
  arrow, so it carries a `[hidden]` rule, the `.sendbar` shape again.
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
  The map now wears the transcript's face at 14 px, which is wider in every
  glyph, so the measurement still holds; a narrower face would not.
- **The map is set like the transcript beside it.** The same face, size and
  line height as `.prose`, and 1 px above and below a row, so a row comes
  about every line. It had the file lists' condensed face at 13 px and a row
  every 29 px, and read as a different page. The file lists keep the
  condensed face, because a path wants the width.
  `test_the_map_is_set_like_the_transcript_and_a_prompt_is_round` compares
  the computed styles, not the numbers, so a change to the transcript's type
  carries the map with it or fails.
- **A round on the map folds from its chevron, and only from its chevron.**
  The row has two jobs: the whole of it goes to that place in the transcript,
  which is what the map is for, and the chevron alone folds. Folding on any
  click would mean you could not read a round without closing it.
  `state.turns.shut` is in `drawTurnList`'s redraw key — the shape of the
  conversation has not changed when you fold one, only what is shown of it,
  so without it a click redraws nothing — and in `savePlace`/`usePlace`,
  because it is a choice. **A second target on a row has to say so**:
  nothing else in this list has two, so the round carries `aria-expanded`
  and the chevron its own `title`, turns down while the round is open, and
  alone changes colour under the pointer. It carries no `cursor`, because
  the row is a button and already sets one. There is no keyboard route to
  folding yet, and that is a gap, not a decision.
- **The map's icons say who spoke; the chevron says what folds.** A folder
  and a page said "a round holds replies", which is the list's shape and not
  what a row is, so a prompt is `ICONS.person` and a reply `ICONS.robot`.
  The fold moved to `ICONS.chevron` so that the icon saying who spoke is not
  also a button. **The chevron and its gap are one tree step, 13 px**
  (`margin-right: -5px` on `.fold`), so a reply's robot stands exactly under
  the person it answers; measured, not eyeballed. The chevron stays
  `--ink-faint`, which takes a rule as specific as the one colouring the
  person, or it turns `--mine` with it.
- **Everything keyed on `seq` is forgotten together, in `forgetPlaces`.**
  `seq` is a place in one reading, not an identity, so a transcript rewritten
  under its own name leaves `state.turns.open`, `state.turns.shut` and
  `state.turns.at` all pointing at different blocks. Two of those were wrong
  before the third was added, which is the moment to give them one place.
  **`run` is therefore one of the things a session keeps**: `usePlace` putting
  the choices back without the reading they belong to would make every return
  to a session look like a rewrite. And the forgetting is guarded on
  `run !== -1` — "none held yet" is every first load, and `goTo` is set from
  the address bar before that load, so forgetting there threw away the link
  the page had just been opened on.
- **Ctrl+Enter presses the button of the box it is typed in**, in every box
  that keeps or sends something: the send box, a review comment, the reason
  for a No, and the comment on the whole review in the review's send bar. The comment box had Escape and
  nothing else, and the send box left Ctrl out on purpose, so the key the
  reader used everywhere did nothing in either. `submitOnCtrlEnter` clicks
  the button and does nothing more, so whatever the button checks is
  checked, and a disabled one ignores the click. Cmd+Enter is the same key.
  **And the button stands level with the box's first line**:
  `.say { line-height: 18px }` makes one line 32 px whoever sizes the box,
  and `.say + .verb` is 32 px. It was 26 beside 32, and the reason box, at
  `line-height: 1.5`, stood 1.5 px taller than its button.
  `test_ctrl_enter_saves_a_comment_and_sends_the_review`,
  `test_ctrl_enter_sends_and_says_no_and_the_buttons_stand_level`.
  - **Every one of these boxes shows all it holds, its placeholder too.**
    A `.say` box wraps (`white-space: pre-wrap`), and so does its
    placeholder. The reason for a No was one row high and never sized:
    at 1,100 px its placeholder wrapped, and "(optional)" stood cut in
    half on a second row that did not show; a long reason did the same.
    `fitSay` sizes it now, as it sizes the send box and the review's two
    boxes, and Chromium counts an empty box's placeholder in
    `scrollHeight`. `fitSay` asks `getClientRects()`, not the box's form,
    because this box stands in none. And `.permsend .permwhy` is at least
    as wide as its placeholder (`--fits`, set from the placeholder's
    length), so the box takes a row of its own rather than wrap it.
    Narrower than about 900 px, the reading column itself is narrower
    than the placeholder; that is the layout's limit, not the box's.
    `test_the_reason_box_shows_its_placeholder_and_what_is_typed_whole`.
  - **The Enter that ends an IME composition is the input method's**
    (`composing`). In Japanese or Chinese, Enter picks the word; the send
    box and the rename box took it as the reader's, and could send half a
    message into a terminal or keep half a name. Chromium says so in
    `isComposing`. Safari sends that Enter after the composition has ended,
    and says so only in `keyCode` 229, so both are read. The guard only
    stops a send, so it takes nothing from the send box's checks.
    `test_the_enter_that_ends_a_composition_sends_nothing`,
    `test_the_enter_that_ends_a_composition_keeps_no_name`.
- **A `/` at the start of the send box completes from files and
  transcripts, asked for each time the list opens** (#268). `Commands.of`
  reads the skills (`skills/<name>/SKILL.md`) and command files
  (`commands/<name>.md`) under `.claude` in the session's directory and
  each parent up to `worktree_root` (`project_dirs`, nearest first, both
  resolved, because git hands back the real path), then the same under
  `claude_dir()`, then adds what `<command-name>` says was run in any
  known transcript. Six things in it are the shape on purpose:
  - **Built-ins come from the transcripts, never a copied list.** `/clear`
    and `/compact` are in no file, and a list of them goes stale with each
    Claude Code release. `Commands.used` reads each transcript on from where
    it stopped (`Tail`), parses only lines holding `<command-name>`, and
    starts a file's count again when the file is rewritten.
  - **A mention is not a use.** `command_used` asks `read_user_text`, so a
    prompt that only talks about `<command-name>` counts nothing, and an
    `isMeta` record is Claude Code's, not the reader's. A `system`
    `local_command` record is the other shape a command is written in.
  - **Not pushed with the row.** A row goes out on every change; the list is
    kilobytes (the ssh rule above). The page fetches `commands` when the
    list opens and drops it when it shuts (`closeSlash`), so a skill written
    a minute ago is in the next list.
  - **What is not known from a real machine is left out**, not guessed:
    plugin skills, whose place on disk nobody has read, and a command file
    in a subdirectory of `commands`, whose name nobody has seen formed
    (topics/payloads). `glob`, not `rglob`.
  - **The list's keys come first** (`slashKey`). Tab always takes the
    chosen row. **Enter takes only a row the reader chose** (`enterTakes`):
    an arrow pressed (`slash.moved`), or a word that starts the name and is
    not all of it. Enter that always took turned `/doctor` -- a built-in
    never run, so not listed -- into `/docs-to-review` by scattered letters,
    and the next Enter sent the wrong command; and a whole name took two
    Enters. Escape shuts the list and is remembered (`slash.dismissed`)
    until the word is gone **or sent**: `sendTyped` empties the box with no
    input event, and the next `/` opened nothing. A row takes on
    `mousedown` with `preventDefault`: a click blurs the box first, and the
    blur shuts the list.
  - **An answer for a box the reader left opens nothing.** `followSlash`
    checks the focus after its fetch, as it checks the session: the list
    opened over the transcript with no box to type into.
  `test_the_project_and_your_own_commands_are_read`,
  `test_what_the_transcripts_say_was_run_is_counted`,
  `test_a_transcript_is_read_on_from_where_it_stopped`,
  `test_a_slash_offers_the_commands_and_tab_takes_one`,
  `test_enter_takes_a_command_and_escape_keeps_the_list_shut`,
  `test_the_list_is_asked_for_each_time_it_opens`,
  `test_enter_sends_what_was_typed_unless_a_row_was_chosen`,
  `test_an_answer_for_a_box_that_was_left_opens_nothing`. `tests/stage.py
  --commands --keys '#say=/'` draws it.
- **Enter jumps, except on a button a keyboard reached.** The keys handler
  jumped to the pane from wherever the focus was, so a keyboard could press
  nothing on the page. But a click leaves the focus on the button it pressed,
  and Enter there has always been the jump key. `:focus-visible` cannot tell
  the two apart: a key pressed on a clicked button turns it on before the
  handler runs. `focusedByKey` can: Tab sets it, a pointer press clears it.
  `test_enter_on_a_button_reached_by_keyboard_presses_it` holds both halves.
  **The same turn-on draws a ring**: a key pressed after a click lights
  `:focus-visible` on the clicked button, so clicking Session and pressing
  1 left the browser's dark ring round Session, the tab just left. A
  shortcut that acts ends by blurring a button the pointer pressed; one
  `focusedByKey` reached keeps its ring.
  `test_a_key_leaves_no_ring_on_a_tab_that_was_clicked`.
- **Few keys, and none that the reader never presses.** `j` `k`, `n`, `r`
  and `t` went: the reader used `1` `2` `3`, and each unused key was a line
  in `?` that hid the ones in use. `3` is the review already. A key that is
  added again needs a reader who asked for it.
  `test_the_keys_nobody_pressed_are_gone`.
- **A row of a list is one line, and `.filelist button` is a block.** A
  list whose rows are one line says so in the one rule that groups them —
  `.fixed` for the file tree, `.diff` for the Diff tab's tree, `.transcript`
  for the map. Without it the icon sits on a line of its own above the text,
  which is how the map first shipped. The Diff tab's tree was a third copy
  of the rule before it joined the group; a fourth list joins it too.
- **The find box narrows the list, never the transcript.** Taking turns out
  of the transcript took the conversation around a hit with them, which is
  what you were reading it for. `shownRounds` filters the left bar;
  `markHits` still marks what matched where it stands, because a hit you
  scroll past unmarked is a hit you miss.
- **A transcript fetch merges what was pushed while it was out.** The
  daemon takes the GET's snapshot under its lock and writes the answer after
  letting go, so a tick can push the next block first, and a push is small
  and wins. `loadTranscript` put the older snapshot in place wholesale: the
  block was gone, the next one landed after a hole, and a text block is
  never pushed twice. `state.turns.early` keeps the pushes that land while
  a fetch is out, and they go over the snapshot by `seq`. **The list is the
  fetch's ticket, and only the newest fetch lands**: two were out after a
  quick Transcript-Session-Transcript, the pushes went into the second one's
  list, and the first, answering last, put its older snapshot back. **A push
  from another `run` makes the snapshot stale**, and it is asked for again:
  the transcript was rewritten while the answer was out, and put in place
  the answer showed a reading the file no longer held.
  `test_a_block_pushed_while_the_transcript_is_fetched_is_kept`,
  `test_only_the_newest_transcript_fetch_lands`,
  `test_a_fetch_older_than_a_pushed_reading_is_asked_again`.
- **A stream opens by saying which `version` of the transcript the daemon
  holds.** A tick between a fetch's snapshot and the stream joining the hub
  sends to nobody, and so does one while a dropped stream reconnects, or
  one into a stream the browser closed and the hub has not noticed yet --
  `wait_for_watching` exists in the tests for exactly that gap. **It cannot
  see a stream the page has just replaced**: the daemon lists the closed one
  until a write to it fails, so it answers at once and the next push goes
  to the dead socket. After `resubscribe` or `choose`, a test goes through
  `renew_stream`, which waits for the new stream's first word.
  `Serving.stream` sends it (`transcript_held`) after joining, so what is
  read after it is pushed and what was read before it is counted; the page
  fetches when it holds less, or keeps it in `state.turns.told` for the
  fetch that is out. **`version` and never a count of blocks**: a tool
  result is written into its call's block, so the count stays still and a
  result read with no stream open was never asked for. `Transcript.version`
  moves on every read that changed something, and every push and answer
  carries it. **The opening is decided before anything is written, and
  both go in one write**: the socket is not buffered, so a reader that saw
  `sessions` could make its change -- a tick that starts reading the
  transcript -- before the stream asked, and got an opening it would not
  have got a moment earlier, in front of the block it waited for. CI red
  by chance, once. `test_a_stream_decides_its_opening_before_it_says_anything`,
  `test_a_block_read_while_no_stream_was_open_is_fetched`,
  `test_a_tool_result_read_while_no_stream_was_open_is_fetched`.
  - **A stream too slow for its pushes is closed, never given a gap.**
    `Client.put` dropped the oldest message when `CLIENT_BACKLOG` were
    queued, and said nothing. A push is only the blocks that changed, so
    the page lost a block and took the newer pushes; its `version` passed
    the lost one, a fetch was answered `same`, and a reconnect's opening
    was not ahead. Measured with a small receive window: pushes 3, 4 and 6
    to 11 never came, and the stream went on. Now the first message it
    cannot keep sets `Client.lost`, empties the queue, and `stream` closes
    without writing another. **Closing only on the next write is not
    enough**: whatever went out after the lost push would carry the page
    past it again. The browser reconnects behind the daemon, and the
    opening makes it fetch (#235).
    `test_a_stream_too_slow_to_keep_up_is_closed_and_never_given_a_gap`,
    `test_a_push_the_stream_could_not_keep_is_fetched_after_it_closes`.
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
    It is sent only while `diffRaw` holds an answer -- every place that
    drops the answer empties that -- and a `same` still reaches the retry of
    an untracked file's read at the end of `loadDiff`.
  - **The file names are kept per worktree, not per session**
    (`keepListing`, `adoptListing`, `state.listings`, by `worktree_path`):
    a session choice blanked them, so every switch -- to another session in
    the same worktree, or back -- fetched every name again.
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
- **A failed transcript fetch is not an empty transcript.** `ask` gives
  null, and the page drew "Nothing in this transcript yet.", forgot the
  reader's places, and asked no more, because the tab polls nothing. Now
  what is held stays, an empty tab says it could not read the transcript,
  and it asks again after `TRANSCRIPT_RETRY` -- **one timer**,
  `state.transcriptRetry`, cleared by every fetch: each tab switch into a
  failing fetch started a loop of its own, and when the daemon came back
  each asked for the whole transcript at once
  (`test_failing_fetches_keep_one_retry_not_one_each`). **And a push with nothing held
  is placed by `seq`**: it carries only the blocks that changed, and
  assigned whole it put block 3 at index 0 as though it were the lot.
  `test_a_transcript_fetch_that_fails_keeps_what_is_held`.
- **`drawTranscript` has no redraw key, on purpose.** The live path is
  `patchTranscript`, which appends. Getting to a full draw means a tab
  switch, a session, or a keystroke in the find box, and every one of those
  really does want the blocks built again. A key there would also leave an
  arriving block's `fresh` class on it for ever: drawing a block again is not
  the block arriving again, and
  `test_only_a_block_that_has_just_arrived_slides_in` says so.
- **`state.turns.down` is read before the pane is emptied.**
  `replaceChildren` puts the scrollbar back to nought and the scroll listener
  would write that down as the place the reader was. The listener is attached
  once per pane, guarded by `pane.dataset.watched`, because `drawTranscript`
  runs many times over one pane and `split` only rebuilds it on a tab change.
  **It writes only for the session whose blocks the pane holds**
  (`pane.dataset.session`): `choose` leaves the last session's blocks in
  place until the new ones land, and a scroll in between -- one the browser
  fires itself when the send box goes and the pane grows -- became the new
  session's place. The `.filescroll` scar, repeated without its guard.
  **An empty draw claims no session**: it takes the last session's scrolled
  blocks away, the bar falls to nought, and that scroll became the place
  of a session whose fetch had failed.
  `test_a_scroll_left_over_from_another_transcript_is_not_its_place`,
  `test_a_failed_fetch_does_not_take_a_sessions_place`.
  **`null` is "no place kept", and nought is the very top**: one number for
  both threw a reader at the top to the foot on every key typed in the find
  box. `test_the_top_of_the_transcript_is_a_place_too`.
  - **And the foot is `null` too, never its pixels.** A first load draws
    the transcript as text and again as Markdown once `marked` arrives,
    much taller; the listener had written the first draw's foot as a
    number, and the second draw put it back thousands of pixels short of
    the latest reply. `nearBottom` decides.
  - **The map keeps its own place across a rebuild**, which `drawTurnList`
    does for every round that arrives: emptying a list puts its scrollbar
    at the top. At its foot, or new to the session, it lands at its foot;
    scrolled up, it stays. `list.dataset.session` says whose map it was.
  `test_a_first_load_lands_at_the_foot_when_marked_comes_late` holds
  `marked` until the text draw is done;
  `test_the_map_keeps_its_place_when_a_round_arrives`.
- **The search redraws the whole tab, so it has to put the reader back.**
  `drawTranscript` ends at the foot of the transcript, which is where a
  session with no kept place belongs — the last thing the agent said is the
  thing you came for.
- **One block redrawn on its own still has to be marked.** `redrawBlock` is the
  Transcript tab's `fillDiffFile`: everything `drawTranscript` does to a node
  it must do too, or the block you touched loses what the others keep.
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
  a tab that hides the box; one that needs to must bring back a
  `.findhome[hidden]` rule, the `.sendbar` scar.
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
- **A restarted `serve` leaves every open page dead, and only the page can
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
    exactly how a restarted `serve` went unexplained. **So a send that worked
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
