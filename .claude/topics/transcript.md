# The transcript: what it reads and where it lands

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. What Claude Code writes in a transcript and how it is read, a link to a turn, the "new" line, and a fetch against the push.

- **A link to a turn is `#<session>/<seq>`, and `seq` is a place in one
  reading.** A session resumed from another directory counts from nought
  again, so an old link can name a turn that is no longer there. `landOnBlock`
  does nothing then, and that is the whole of the failure. It also wins over
  the usual landing at the foot of the transcript exactly once: `state.turns.goTo`
  is cleared the moment it lands, or a live session would drag the reader back
  to it every second. **It runs in `landTranscript`, after `paint`**, never in
  the draw (#573): the clearing is a write, and a draw only reads `state`. **`#<session>` alone is the session on screen**:
  `choose` writes it with `replaceState`, which fires no `hashchange`, so a
  reload comes back to that session and not to the first row. **Only when
  the address names another session**: rewritten always, a link to one
  reply lost its `/<seq>` the moment it opened, and
  `test_a_reply_is_a_link_you_can_open_in_another_tab` went red.
  **`seq` is digits and nothing else** (`placeInHash`): `Number("")` is 0,
  so `#s1/` was a link to the first block, and `Number` takes " 3", "1e2"
  and "0x10" too. `test_a_link_to_a_block_is_digits_and_nothing_else`.
- **Coming back to a session lands on a "new" line, over the first block
  after the reader last had it on screen** (#374), as Slack opens a
  channel. `state.turns.newSince` is the row's `seen_at` (#373), taken
  once by `markSeen` *before* it reads the session: taken after, it was
  now, and a turn that ends while the reader watches would have drawn a
  line over itself. `undefined` is not taken yet, `null` no line, so a
  session whose row arrives after the choice still gets it. It is a field
  of `blankTurns` and not of `PLACE_FIELDS`: a visit's news is not kept.
  - **`putNewLine` puts the line on every draw**, as a sibling before the
    block's node and not inside it, so `redrawBlock` leaves it standing,
    and `patchTranscript` puts it when the first block after arrives in a
    push of its own.
  - **It says since when** (#398): "new since 08:27", and the day before
    the time when it was not today -- `newSince`, through `clock` and
    `dayOf`. "new" alone did not say how much was missed. A test reads the
    reader's last look *before* the page opens: once open, the page has
    marked the session read, and `store.seen` holds now.
  - **`landOnNew` lands again on a draw the reader has not scrolled
    since** (`newDown`): the transcript is drawn as text and then as
    Markdown, much taller, and a landing only once left the pixel offset of
    the first draw, with the line near the foot. A link (`goTo`) wins. A
    line that cannot reach the top -- too little after it -- stands where
    the end of the pane lets it, which is right.
  - **A prompt right under it, or under "context compacted", draws no
    rule of its own** (#496, `:is(.divider, .newline) + .turn.mine`):
    each is a rule already, and the prompt's `::before` drew a second a few
    pixels lower. A sibling selector, so `putNewLine` must keep the line
    the block's sibling just before it.
    `test_a_prompt_under_the_compaction_line_draws_no_rule_of_its_own`.
  **A test of "at the top" has two bounds** (`AT_TOP`): `top < 20` passed
  with the landing taken out, because the line stood 470 px *above* the
  pane. `test_coming_back_lands_on_a_line_over_the_first_turn_not_seen`,
  `test_the_line_holds_when_marked_comes_late`,
  `test_the_line_stays_and_lets_the_reader_scroll_away`,
  `test_a_turn_that_ends_while_you_watch_draws_no_line`.
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
- **`wostuast report`'s transcript section (it was `wostuast shapes`, #323)
  is how a new Claude Code shape is found before the reader finds it.** Every bug of this kind -- `!git up`, `/clear`,
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
- **Everything keyed on `seq` is forgotten together, in `forgetPlaces`.**
  `seq` is a place in one reading, not an identity, so a transcript rewritten
  under its own name leaves `state.turns.open` and `state.turns.at`
  pointing at different blocks. There were three once, two of them wrong
  before the third was added, which is the moment to give them one place.
  **`run` is therefore one of the things a session keeps**: `usePlace` putting
  the choices back without the reading they belong to would make every return
  to a session look like a rewrite. And the forgetting is guarded on
  `run !== -1` — "none held yet" is every first load, and `goTo` is set from
  the address bar before that load, so forgetting there threw away the link
  the page had just been opened on. **That guard is `takeRun`, one
  function** (#544): the fetch (`loadTranscript`) and the push
  (`onTranscriptPush`) each wrote it, with comments that differed.
  `test_a_reading_that_has_not_changed_forgets_nothing`,
  `test_a_rewritten_transcript_forgets_what_was_chosen_by_seq`.
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
  - **The opening carries the settings too**, after the sessions and the
    transcript, read under `config_lock` once the stream is in the hub.
    A page has its settings from its load and then only from
    `tell_config`'s pushes, and choosing a row opens a new stream: a
    change made before that stream joined went to nobody, and the page
    kept the old links until the next change.
    `test_a_ticket_in_a_rows_name_or_branch_is_a_link` was red by chance
    on it twice, once in #595's gate. `read_events` passes over a
    `settings` event unless asked, so a count of sessions stays a count
    of sessions. `test_a_stream_opens_with_the_settings`.
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
  - **The nodes drawn live on the pane, not in `state`** (#573):
    `pane.nodes`, a node for each block, and `pane.heads`, the line over
    each run of calls. They are what was drawn, and `drawTranscript`
    wrote them into `state.turns`, which principle 3 forbids a draw.
    **The pane says which transcript it was drawn from** (`drawnFrom`,
    read through `drawnTurns` and `turnNode`): `choose` blanks
    `state.turns` and keeps the pane, which holds the last session's
    nodes until the fetch lands, and a push in that gap is patched at
    once. `patchTranscript` draws the whole tab again for a pane drawn
    from other turns; when `blankTurns` held the nodes, blanking them did
    this without saying so.
    `test_a_push_after_a_switch_patches_no_node_of_the_last_session`.
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
