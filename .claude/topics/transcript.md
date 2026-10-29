# The transcript: what it reads and where it lands

What a transcript record is and how it is read, a link to a turn, the "new"
line, and a fetch against a push.

- **A link to a turn is `#<session>/<seq>`; `seq` is a place in one
  reading.** An old link may name a gone turn; `landOnBlock` then does
  nothing. **It wins over the foot once**: `state.turns.goTo` clears on
  landing, or a live session drags the reader back every second. **It runs
  in `landTranscript`, after `paint`** (#573): the clearing is a write, and
  a draw only reads `state`.
  - **`#<session>` alone is the session on screen**: `choose` writes it with
    `replaceState` (no `hashchange`), so a reload returns to it, **but only
    when the address names another session**: else a reply's link lost its
    `/<seq>`. `test_a_reply_is_a_link_you_can_open_in_another_tab`.
  - **`seq` is digits only** (`placeInHash`): `Number("")` is 0, and
    `Number` takes " 3", "1e2", "0x10".
    `test_a_link_to_a_block_is_digits_and_nothing_else`.
- **Coming back to a session lands on a "new" line over the first block not
  seen** (#374). `state.turns.newSince` is the row's `seen_at` (#373), taken
  once by `markSeen` *before* it reads the session, or a turn that ends
  under the reader's eyes gets a line. `undefined` is "not taken yet",
  `null` "no line", so a row that arrives late still gets it. It is in
  `blankTurns`, not `PLACE_FIELDS`: a visit's news is not kept.
  - **`putNewLine` puts the line on every draw, as the sibling before the
    block's node, never inside it**, so `redrawBlock` keeps it;
    `patchTranscript` puts it when the first new block is pushed.
  - **It says since when** (#398): "new since 08:27", with the day when not
    today (`newSince`, `clock`, `dayOf`). **A test sets the last look before
    the page opens**: an open page marks the session seen.
  - **`landOnNew` lands again on each draw until the reader scrolls**
    (`newDown`): the Markdown draw, once `marked` arrives, is much taller
    than the text draw. A link (`goTo`) wins.
  - **A prompt right under it, or under "context compacted", draws no rule
    of its own** (#496, `:is(.divider, .newline) + .turn.mine`), or two
    rules stand together.
    `test_a_prompt_under_the_compaction_line_draws_no_rule_of_its_own`.
  - **A test of "at the top" has two bounds** (`AT_TOP`): `top < 20` passed
    with the line far above the pane.
    `test_coming_back_lands_on_a_line_over_the_first_turn_not_seen`,
    `test_the_line_holds_when_marked_comes_late`,
    `test_the_line_stays_and_lets_the_reader_scroll_away`,
    `test_a_turn_that_ends_while_you_watch_draws_no_line`.
- **A `user` record is not always a prompt.** Claude Code writes its own,
  and `(no content)` was drawn as the reader's. `read_user_text` reads each
  for what it is: a command is one line that says what ran, the
  resumed-session caveat goes, and a task notification or another session's
  message is a `note`, never on the reader's rail. **A record is a command
  only when nothing else is on it**: a prompt can quote `<command-name>`.
  **An interrupt is a note** (`INTERRUPTED`): a record of exactly
  `[Request interrupted by user]` (or `... for tool use]`) follows each
  Escape, and each No from the page drew a prompt.
  `test_an_interrupt_claude_code_wrote_is_a_note_not_your_prompt`.
  - **A task notification is its `summary` and its `result`** (`task_note`;
    the other fields: `task-id`, `tool-use-id`, `output-file`, `status`,
    `note`, `usage`). A shape not measured is shown as it came. **Another
    session's message is its words** (`AGENT_MESSAGE`): a header line in a
    `user` record, none in a queued one, the words in
    `<agent-message from=…>`, then a paragraph about the sender. **Read a
    real record, not a guess**: the first fixture guessed the header away.
    `tests/fixtures/notes.jsonl`.
    `test_a_task_notification_and_another_sessions_message_read_as_words`.
  - **A `!` command is two records and one block.** `<bash-input>`, then
    `<bash-stdout>`/`<bash-stderr>` with `<`, `>`, `&` as entities; neither
    is `isMeta`. `BASH_INPUT` makes a `shell` block; `shell_output` adds the
    output with `html.unescape`, only to a block not yet answered, or two
    runs merge. A record counts only when it is the tag alone. The output is
    drawn in `white-space: pre`. `tests/fixtures/bash_mode.jsonl`.
    `test_a_command_run_with_a_bang_is_one_block_with_its_output`,
    `test_a_bang_command_is_drawn_with_its_output_in_the_fixed_face`.
  - **A slash command is one block with its answer**: no hook fires for one.
    `command_output` puts `<local-command-stdout>` into the `command` block,
    drawn as a `shell` one with `/`; "(no content)" closes it. **Both shapes
    are read**: `user` records, and `system` records
    (`subtype: local_command`, text in `content`) for `/context` or a
    `/model` closed without a pick. **Colour codes come off**
    (`ESCAPE_CODES`, then `CONTROL_CHARS`). A command nobody typed is a
    note.
    - **An `isMeta` record straight after an answer is the answer again**,
      for the agent. `echo_of` drops it only straight after, once, and never
      after "(no content)": `/init`'s prompt is an `isMeta` record with no
      answer before it. `tests/fixtures/local_command.jsonl`.
    - **`<local-command-stderr>` is not read until a real one is recorded**
      (`commandOutcome` `failed`): topics/payloads says a shape is recorded,
      never guessed.
    - `test_a_slash_command_and_what_it_answered_are_one_block`,
      `test_a_slash_command_is_drawn_with_what_it_answered`.
- **`wostuast report`'s transcript section (was `wostuast shapes`, #323)
  finds a new Claude Code shape before the reader does**: each such bug
  (`/clear`, `/model`, `!git up`) reached the reader as tags on screen.
  `transcript_shapes` reads recent transcripts through `Transcript.add` and
  lists records and pieces left out and not on `SILENT_RECORDS`, and Claude
  Code tags (`MACHINE_TAG_NAME`: a hyphen or underscore) left in a prompt,
  note or command.
  - **A tag counts only when closed too, and in a prompt only when the
    prompt opens with it**: else C++'s `<uint32_t>` counted.
  - **Names and counts, never text**, so the output can go into a public
    issue.
  - **A name goes on `SILENT_RECORDS` only after a real record of it was
    read**: the queued message was an attachment nobody had looked at.
  - **It splits on `\n`, never `splitlines()`**: U+2028 cut records in half.
  - `test_the_report_lists_what_the_page_cannot_show_and_never_the_text`,
    `test_the_report_reads_only_the_days_asked_for`.
- **A message sent to a busy agent comes back wrapped, and the wrapper is
  not the reader's** (`QUEUED` keeps the middle). It is a
  `<system-reminder>`: a header
  (`The user sent a new message while you were working:`), the words, a
  footer to the agent. **Order matters**: `strip_reminder` first, and the
  message is pulled out *before* `MACHINE_TAG`, whose list holds
  `system-reminder`. **The header must open the record and the footer be
  there**, or a reader quoting the wrapper loses their question.
- **Pasted text comes off Claude Code's paste tags, by Claude Code's own
  rules** (`unwrap_pastes`, a port of the bundle's `Pct`):
  `<pasted_content id="1da8">` with four lowercase hex digits, the same on
  both tags, each on its own line, up to two newlines either side belonging
  to the wrapper; anything else stays as typed. It runs first in
  `read_user_text`, **and in `_on_prompt`**: the hook gets the prompt as
  written. `test_the_row_shows_a_pasted_prompt_without_its_tags`.
- **A message queued while the agent works is an `attachment`, and it is
  read.** A `queued_command` attachment comes with no `user` record, and the
  agent answered words not on the page. `add_queued` reads it through
  `read_user_text`: `origin.kind` human is a prompt, a peer's message or a
  task's news a note; other attachments stay out. **One with no
  `commandMode` is a note**: the reader's rail on words not theirs is the
  worse mistake. `test_a_message_queued_while_the_agent_works_is_drawn`.
- **`isMeta` is Claude Code speaking, never the reader**: a Stop hook's
  answer, a skill's body, an image's caption. `user_block` makes them notes,
  for a string and for pieces.
  `test_what_claude_code_wrote_itself_is_never_your_prompt`.
- **Thinking is never a block.** Most thoughts are a signature only, and the
  reader dropped them. `Transcript` returns no block for a `thinking` piece,
  so nothing counts, draws or searches one, and `+` and `:has(+ ...)` rules
  hold: a hidden thought was still a sibling.
  `test_thinking_is_never_a_block_even_with_text_in_it`,
  `test_a_thought_between_two_tool_calls_leaves_no_trace`.
  - **But a thought the console shows is the agent's words, a `text`
    block.** 2.1.306 writes what the agent tells the reader between its
    calls as a thought, on a record with `thinkingDisplay: "updates"`; the
    page had "Let me measure" and never what it measured. Only such a
    record, and only with text: one with a signature only is nothing.
    `tests/fixtures/narration.jsonl`,
    `test_a_thought_claude_code_shows_as_an_update_is_the_agents_words`.
- **Everything keyed on `seq` is forgotten together, in `forgetPlaces`.** A
  rewritten transcript leaves `state.turns.open` and `state.turns.at` on
  other blocks. **`run` is kept with a session's places**, or `usePlace`
  makes every return look like a rewrite. **The forgetting is guarded on
  `run !== -1`**: that is every first load, and `goTo` from the address
  comes before it. **The guard is one function, `takeRun`** (#544), for the
  fetch (`loadTranscript`) and the push (`onTranscriptPush`).
  `test_a_reading_that_has_not_changed_forgets_nothing`,
  `test_a_rewritten_transcript_forgets_what_was_chosen_by_seq`.
- **A transcript fetch merges what was pushed while it was out.** The daemon
  snapshots under its lock and answers after, so a tick can push the next
  block first, and a block is never pushed twice. `state.turns.early` keeps
  those pushes; they go over the snapshot by `seq`. **The list is the
  fetch's ticket; only the newest fetch lands**: an older one answering last
  put its snapshot back. **A push from another `run` makes the snapshot
  stale, and it is fetched again.**
  `test_a_block_pushed_while_the_transcript_is_fetched_is_kept`,
  `test_only_the_newest_transcript_fetch_lands`,
  `test_a_fetch_older_than_a_pushed_reading_is_asked_again`.
- **A stream opens by saying which `version` of the transcript the daemon
  holds** (`transcript_held`): a tick before the stream joins the hub sends
  to nobody. `Serving.stream` sends it after joining; the page fetches when
  it holds less, or keeps it in `state.turns.told` for the fetch that is
  out. **`version`, never a block count**: a tool result goes into its
  call's block, so the count stays. `Transcript.version` moves on every read
  that changes something. **The opening is decided before anything is
  written, and goes in one write**: the socket is unbuffered, so a page that
  saw `sessions` could start a tick first.
  `test_a_stream_decides_its_opening_before_it_says_anything`,
  `test_a_block_read_while_no_stream_was_open_is_fetched`,
  `test_a_tool_result_read_while_no_stream_was_open_is_fetched`.
  - **In a test, after `resubscribe` or `choose`, call `renew_stream`**:
    `wait_for_watching` does not cover a stream just replaced, which the
    daemon lists until a write fails.
  - **The opening carries the settings too**, read under `config_lock` once
    the stream is in the hub: otherwise only `tell_config` pushes them, and
    a change before a new stream joined reached nobody
    (`test_a_ticket_in_a_rows_name_or_branch_is_a_link`, #595).
    `read_events` skips a `settings` event unless asked.
    `test_a_stream_opens_with_the_settings`.
  - **A stream too slow for its pushes is closed, never given a gap.**
    Dropping the oldest message at `CLIENT_BACKLOG` lost a block the page's
    `version` then passed, and a fetch got `same`. The first message
    `Client.put` cannot keep sets `Client.lost`, empties the queue, and
    `stream` closes without writing again: anything sent after the lost push
    would carry the page past it. The browser reconnects and fetches (#235).
    `test_a_stream_too_slow_to_keep_up_is_closed_and_never_given_a_gap`,
    `test_a_push_the_stream_could_not_keep_is_fetched_after_it_closes`.
- **A failed transcript fetch is not an empty transcript.** When `ask` gives
  null, what is held stays, an empty tab says it could not read, and it
  retries after `TRANSCRIPT_RETRY`. **One timer, `state.transcriptRetry`,
  cleared by every fetch**: each tab switch started its own loop
  (`test_failing_fetches_keep_one_retry_not_one_each`). **A push with
  nothing held is placed by `seq`**: assigned whole, it put block 3 at index
  0. `test_a_transcript_fetch_that_fails_keeps_what_is_held`.
- **A session with nothing said yet says where it stands** (#651, #654,
  `putFreshStart`, `paintFresh`): one grey line, and "Nothing said yet."
  flush against the map's edge, was all a fresh session showed. A heading,
  one sentence, and a card of the row's own lines (`fillRowPlace`,
  `fillRowGit`, the one reader of those facts) with the path. **`paintFresh`
  runs in `drawHeader`**, on every push: `drawTranscript` has no redraw key,
  and git's facts come a tick after the session. The map says nothing then;
  only a find gets its "Nothing here matches." **Not for a subagent's
  view** (`state.agent`): the facts would be the session's.
  `test_a_session_nothing_was_said_in_says_where_it_stands`,
  `test_a_running_subagent_s_transcript_follows_it`.
- **`drawTranscript` has no redraw key, on purpose.** The live path is
  `patchTranscript`, which appends; each full draw wants the blocks rebuilt.
  A key would also leave an arriving block's `fresh` class on for ever.
  `test_only_a_block_that_has_just_arrived_slides_in`.
  - **The drawn nodes live on the pane, not in `state.turns`** (#573):
    `pane.nodes`, one per block, and `pane.heads`. **The pane says which
    transcript it was drawn from** (`drawnFrom`, read via `drawnTurns`,
    `turnNode`): after `choose` it holds the last session's nodes until the
    fetch lands, so `patchTranscript` redraws a pane drawn from other turns.
    `test_a_push_after_a_switch_patches_no_node_of_the_last_session`.
- **`state.turns.down` is read before the pane is emptied**:
  `replaceChildren` scrolls to nought, and the listener would record it. The
  listener is attached once per pane (`pane.dataset.watched`).
  - **It writes only for the session whose blocks the pane holds**
    (`pane.dataset.session`), or a scroll before the new blocks land is the
    new session's place, as with `.filescroll`. **An empty draw claims no
    session**, or its scroll to nought is the place of a session whose fetch
    failed.
    `test_a_scroll_left_over_from_another_transcript_is_not_its_place`,
    `test_a_failed_fetch_does_not_take_a_sessions_place`.
  - **`null` is "no place kept"; nought is the very top**: one number for
    both sent a reader at the top to the foot.
    `test_the_top_of_the_transcript_is_a_place_too`.
  - **The foot is `null` too, never its pixels**: the text draw's foot fell
    short once Markdown drew taller. `nearBottom` decides.
    `test_a_first_load_lands_at_the_foot_when_marked_comes_late`.
  - **The map keeps its own place across a rebuild** (`drawTurnList`): at
    its foot or new to the session it lands at its foot; scrolled up, it
    stays. `list.dataset.session` says whose map it was.
    `test_the_map_keeps_its_place_when_a_round_arrives`.
- **The search redraws the whole tab, so it has to put the reader back.**
  `drawTranscript` ends at the foot, right for a session with no kept place:
  the agent's last words are what the reader came for.
