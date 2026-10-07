# State

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. The session model, the log, and what the Files tab draws.

- **Amber means one thing: the agent cannot go on until you answer.** An idle
  `Notification` is not that — `Stop` already said the turn was over, and nothing
  you do clears an idle prompt, so a row that went amber on it stayed amber for
  ever. A permission `Notification` is dropped once the session has sent a
  `PermissionRequest`: after that it is the same news twelve seconds late, and
  honouring it raised the alarm again for a question already answered — and
  dropping it means the text too, or the row reads "ready" with a permission
  question as its only line. A notification with no `notification_type` is
  read for the message that means a dialog, never assumed to be one:
  `auth_success` ("Logged in as …") took the row amber with nothing that
  could ever clear it.
  - **A turn an API error ended is amber too** (`_on_stop_failure`). Claude
    Code fires `StopFailure` *instead of* `Stop` -- a spend limit, a login,
    an overload -- and it was not registered: the row read "working" over
    an agent that had stopped, and the error stood in the transcript and
    nowhere in the log. The agent cannot go on until the reader acts, so it
    is amber, and the reason is Claude Code's own sentence,
    `last_assistant_message` in the payload recorded on 2.1.285
    (`tests/fixtures/stop_failure.jsonl`); `STOP_FAILURES` names an `error`
    that comes without one. An install from before has not registered it,
    and `doctor` says so.
    `test_an_api_error_ends_the_turn_and_says_why`,
    `test_an_api_error_with_no_words_is_named_by_its_kind`.
- **A question is a question, not a permission.** `AskUserQuestion` is a tool,
  so `PreToolUse` and then `PermissionRequest` carry the whole of it in
  `tool_input` -- every question, every option, every description. It used to
  fall to `tool_target`'s catch-all and reach the row as
  `AskUserQuestion {"questions": [{"question": "Approve the pla…`, clipped at
  eighty characters: everything the reader needed was in the payload and none
  of it reached them. `read_ask` keeps what the page draws, **named field by
  field**, because a row goes to every browser on every push and a field
  nobody read must not reach the page. The row says `asks:` and not
  `permission:` -- the word sent people looking for a dialog that asks
  something else.
- **`Session.asking` is cleared wherever the attention is, and by its own
  `tool_use_id`.** `PreToolUse` carries that id and `PermissionRequest` does
  not, so the ask is read from the first of the two: it is the only thing that
  says *this* question was answered. A `PostToolUse` for another call is not
  an answer -- two calls really do overlap -- and this stale question has
  buttons on it, which type a number into a terminal that has moved on.
  **Nor is another call of the same batch before the dialog is up.** The
  `PermissionRequest` comes about ninety milliseconds after the ask's own
  `PreToolUse`, and another call finishing, failing or starting in between
  ran `_clear_attention` or overwrote `asking` with `None`: the row went
  amber saying "asks: …" over no bar, and `answer` refused. `_on_pre_tool`
  and `_on_tool_failed` hold the ask across it; a call starting *after* the
  dialog is still the agent moving on.
  `test_another_call_before_the_dialog_does_not_take_the_question_away`.
- **`Session.permission` is the dialog whole, for the page, and it goes
  with the attention.** The row said it clipped to one line; a request is
  judged on all of it, so `read_permission` sends every field of the input
  (past `PERMISSION_SHOWN` it is withheld and the page points at the pane).
  - **A plan is the exception: it is read in the transcript, not here**
    (#372). `ExitPlanMode`'s request carries the plan whole (topics/payloads),
    and the panel drew it as Markdown source in a `pre`, cut off, and
    withheld a plan past `PERMISSION_SHOWN` -- which real plans pass. So
    `plan_of` makes the call a block of kind `plan` in the transcript, drawn
    by `markdown` and its scrub like any reply, and `read_permission` sends
    `plan: true` and no fields; `drawPermission` says "It asks to start on
    the plan above" and `lastPlan` scrolls to it. The block keeps the
    call's `tool_use_id`, or a No's reason would wait for ever for a result
    no block takes (`call_answered`). The row reads the plan's title
    (`tool_target`), not `{"plan": "# …`. A call with no plan stays a tool
    row. `test_a_plan_waiting_for_approval_is_pointed_at_not_copied`,
    `test_a_long_plan_is_not_withheld`,
    `test_a_plan_is_a_block_of_its_own_with_the_whole_markdown`,
    `test_a_plan_is_read_as_markdown_and_the_dialog_points_at_it`.
  Its `key` is the moment the dialog came up, so a No meant for one dialog
  is refused once another is up. Its `call` comes from `Session.calls`, the
  calls started and not finished, matched by `tool_summary` -- the
  `PermissionRequest` carries no id -- and it is empty when two match.
  `calls` is cleared at a turn's end and a new prompt, because a call
  declined in the terminal never reports back, and left there it made the
  next same call two matches. **The daemon writes a `Declined` record of
  its own** into the event log once the transcript shows the decline, and
  `_on_declined` ends the wait for that one dialog: saying No fires no
  hook, and the row stayed amber over an agent back at its prompt. **A No
  in the terminal too**: `declined_in_terminal` looks, each tick, for the
  call of every dialog up, and writes the record (`where: "terminal"`) when
  its result is `REJECTED` -- not for any result, because a Yes has one
  too and its `PostToolUse` says so, and not for a session in `declining`,
  whose No the page is pressing and records itself. Read again on the same
  tick, so the row goes out no longer amber.
  - **The reader it makes does not stay for a week** (#294). Each dialog
    made a reader, watched or not, and `forget_gone` dropped one only when
    its session left the `Store`: the daemon held every transcript of the
    week, tool results whole. Now a reader goes once no browser watches its
    session, no dialog is up (`Session.dialog`), and nothing has asked for
    it for `READER_IDLE` -- not at once, because the page fetches before it
    subscribes. Its run is kept in `Daemon.runs`, and the next reader of
    that session counts on from it: one that began at run 0 again could
    match a `have` the page still held for the old one, and the tab would
    stand on blocks the file no longer ends with.
    `test_a_reader_nobody_needs_goes_and_its_run_counts_on`.
  `test_a_no_given_in_the_terminal_ends_the_wait`,
  `test_a_yes_in_the_terminal_is_not_taken_for_a_no`,
  `test_a_permission_request_reaches_the_page_whole`,
  `test_a_request_two_open_calls_could_be_has_no_call`,
  `test_a_decline_seen_in_the_transcript_ends_the_wait`,
  `test_a_permission_is_read_whole_and_declined_with_a_reason`.
- **The question bar belongs to the Transcript tab, at its foot.** It is not
  the header bar that was taken away (`review.md` says why that went):
  this stands in one place, over the send box, because the
  transcript ends at its foot and answering is sending. The row still goes amber from any tab, which is what
  the row is for. It reads `state.tab`, like the send box, because it is
  chrome outside the content box and is drawn after `showTab` has set the
  name. `drawAsking` is called from `drawHeader`, so a fifth call site cannot
  forget it.
- **Picking types nothing; submit does.** A click that went straight into a
  terminal was a click you could not take back, on a page you may have opened
  on a phone in a pocket. `state.picked` holds the indexes picked for each
  question -- one for a single-choice question, any number for a
  multiple-choice one -- **with the ask's id**, so a pick made for one question is never submitted for the
  next, **and with its shape**: an ask with no id (a `PreToolUse` with no
  `tool_use_id`) matched the empty picks the page starts with, `paintPicks`
  read a pick list that was not there, and the throw took `drawHeader` and
  the first transcript load with it
  (`test_a_question_with_no_id_does_not_stop_the_page`). It survives a look at another tab -- the bar is built again when
  it comes back, and half an answer lost that way is a page you cannot trust
  with the other half. `paintPicks` is everything that changes on a click, so
  picking never rebuilds the bar: a rebuild under the hand is how a click
  lands on the wrong option. Submit waits until every question has an answer,
  because the agent asks them one after the other.
- **A button that types into a terminal says what it types, before it is
  pressed.** Each option carries its number, and the submit says `presses 2,
  then 2 4 Tab, then Enter` -- `askKeys` on the page, which is only the
  preview. **The page sends picks, never keys**: `submitAsk` posts the
  option numbers to `answer`, and the daemon works the keys out from the
  question it holds (`ask_keys`) and presses those (`tmux_keys`): digits,
  Tab and Enter and nothing else, refused for an ask id that is no longer
  the one waiting. `test_the_page_says_the_keys_the_daemon_presses` holds
  the preview and the presses together. **It does not clear the question**:
  that happens when the daemon sees the `PostToolUse`, because clearing on
  the click would hide a question a missed keystroke left standing. Submit
  stays off meanwhile (`state.answered`), and the bar says to answer
  in the terminal if the question stays: `safety.md`, "One send at a time".
  - **An answered question is kept by its ask id, outside
    `state.picked`.** The picks are one for the whole page, and a flag in
    them (`state.picked.pressed`) did not survive a look at another
    session with a question: `drawAsking` built the picks again for that
    question, and again with the flag off for the first one on the way
    back. After a new pick, submit was on for a question whose keys had
    gone in. `state.answered` holds the ids whose keys went in, per ask and
    so per session, and `paintPicks` reads it. `forgetAnswered` drops an id
    no session still asks, on every `sessions` push.
    `test_an_answered_question_stays_answered_after_a_look_at_another`.
- **The keys are Claude Code's dialog's, measured, and never a finger's
  guess.** Against 2.1.281 in tmux, with a fake Messages API asking: a digit
  answers a single-choice question **and moves on**; a multiple-choice
  question takes a digit per option, each a tick, and then Tab; after the
  last question a review stands with "Submit answers" under the cursor and
  takes Enter -- except after one single-choice question, which has none,
  where an Enter would land on the agent's prompt. This page used to send
  each number through `send`, which presses Enter after it: the Enter
  answered the next question with the option under the cursor, `2` on the
  review is Cancel, and a multiple-choice question ticked a second option
  and was never submitted. **One key per tmux command, with `KEY_GAP`
  between**: `24` written at once arrives as one read, which the dialog
  takes as no key at all, measured -- the ticks were lost and it moved on.
  **Each key a paste of its bytes, never `send-keys`** (`KEY_BYTES`,
  #331): under `synchronize-panes` a key went to every pane of the window,
  and a digit and an Enter on another agent's prompt can answer or approve
  something there. Unbracketed, or the dialog reads text. Measured on
  2.1.287: a pasted "2" picked the second option, and "1", "3", Tab, Enter
  the first and third of a multiple choice, as `send-keys` did.
  `test_keys_go_one_paste_each_and_only_the_answer_keys`.
  **An ask the daemon could not keep whole is not answered** (`answerable`):
  keys go by position, so a question or option left out would move every
  key after it. **A single-choice question with a `preview` on any option
  is another dialog**: the options stand beside a box, a digit only moves
  the cursor, and Enter answers and moves on. The page pressed `3` alone
  there, so the reader's answer sat under the cursor and nothing was sent.
  `shows_preview` is Claude Code's own test for a preview it draws (its
  `pU`), and where that hangs on the width of an invisible character the
  ask is not answerable, because the keys would be a guess. A screen reader
  turns the layout off, and nothing in the payload says so. When Claude Code changes its dialog, measure it again the
  same way; do not read the new keys off the minified source, where Tab is
  bound twice and which binding wins is not written down.
- **The preview stands beside the options, and shows what the dialog's box
  shows.** An agent puts the thing a choice is about -- a code sketch, a
  layout -- in an option's `preview`, and the page drew the labels and
  descriptions and none of it. `read_ask` sends each option's text whole,
  never through `clip`, which folds every line of a code box into one; a
  preview over `PREVIEW_UNREAD` goes only as `withheld`, and the page says
  Claude Code's own sentence for it, and "No preview available" for an
  option with none (`previewText`). A multiple-choice question sends no
  preview, because its dialog draws none. The box follows the pick, which
  types nothing, so clicking through is how to read them; before a pick it
  shows the first, where the dialog's cursor starts. `paintPicks` fills it,
  so a pick rebuilds nothing. **Beside, not under**: under the options it
  stood below the bar's 40vh fold, and a preview you have to scroll to is
  one you choose without. It is `textContent` in a `pre`, because a layout
  drawn in text is nothing without its spaces; one code fence round the
  whole comes off, as the dialog's Markdown takes it off.
  `test_the_preview_stands_beside_the_options_and_follows_the_pick`.
- **A call starting clears the attention; a call finishing only clears its
  own.** Claude Code runs two tools at once now and then — one of 233 calls on
  a real machine started while another was still open, both of them `Bash`.
  Both `PreToolUse` events come before the dialog, so the other call reports
  back while it is on screen, and clearing on that turned the row green while
  the agent sat blocked. A `PreToolUse` is different: nothing new starts while
  a dialog is up, so one says the agent moved on — which is the only sign of a
  denial, because saying No fires no hook at all. `PermissionRequest` carries
  no `tool_use_id`, so the pairing goes by `tool_summary`; two runs of the same
  command at the same moment cannot be told apart, and nothing in the payload
  can. **A result reuses its call's summary** (`calls`, by `tool_use_id`):
  it carries the very input its call did, and making the summary again,
  secrets hidden, was a fifth of a start's fold (#430). Not lazily, at the
  row: the pairing above compares summaries as they are folded.
  `test_a_result_reuses_its_calls_summary`.
  - **A subagent's call is not the agent moving on** (`mine_alone`, in
    `_on_pre_tool` and `_on_tool_failed`). A subagent of the Agent tool
    fires its hooks under its agent's session id, with an `agent_id`
    (#422, topics/payloads). One still running started a `Read` while its
    agent's question was up: the question left the page a second after it
    came, and the row went green over a dialog still up in the terminal. A
    dialog's No went the same way. Its calls still feed its line under the
    row (`note_subagent`); they no longer touch the agent's attention, not
    even a result of the dialog's very command, which the pairing by
    summary would take for the dialog's own.
    `test_a_subagents_call_does_not_take_the_question_away`,
    `test_a_subagents_call_does_not_close_a_permission_dialog`.
- **A `/clear` is one conversation in two sessions, and the page follows
  it.** Claude Code ends the session (`reason: clear`) and starts another
  (`source: clear`) with a new id and a new transcript, in the same pane and
  the same process, a tenth of a second apart -- measured on 2.1.282. The
  page stayed on the session that had ended, showing the old transcript, and
  a reload then opened on the first row, the new one: the reader took the
  transcript for broken, and the old conversation for lost. `link_clear`
  joins the two in `Store.apply` by the process, or by the pane where there
  is no pid, within `CLEAR_GAP`, in either order -- the two hooks are
  separate processes. The row carries `cleared_into`, and `followClear`
  chooses it **once, when the link appears while the page is open**:
  `state.cleared` holds what it has seen, so a reader who goes back to read
  the old one is not sent on again, and a link already there when the page
  opened was not made under anybody's eyes. **A resume starts the link
  again**: `_on_session_start` resets `cleared_into` for any source but
  `clear` and `compact`. Session A, cleared into B and then resumed, kept
  B, and `link_clear` joins only a session with none, so a second `/clear`
  joined A to nothing and the page did not follow.
  `test_a_resumed_session_cleared_again_joins_the_new_one`.
  **The reader's name moves with
  it**, out of `names.json` and not copied, so the old row falls back to
  where it was; the log folds again on a restart and finds nothing to move.
  `test_a_clear_joins_the_session_it_ended_to_the_one_it_started`,
  `test_a_clear_is_not_joined_to_another_sessions_start`,
  `test_a_clear_with_no_pid_is_joined_by_its_pane`,
  `test_the_name_goes_with_a_clear_and_moves_once`,
  `test_a_clear_is_followed_and_a_reload_stays_on_it`,
  `test_a_reader_who_goes_back_to_a_cleared_session_stays_there`.
  - **A conversation the agents view moves to the background is joined
    the same way, by what the hook read** (`link_move`). `←` on an empty
    prompt runs the conversation again in Claude Code's daemon as a fork,
    with a new id (topics/payloads, `tests/fixtures/README.md`). The old
    session gets no `SessionEnd`, and its process lives on as the agents
    view, so `mark_dead` never buried it: the reader saw three rows for one
    conversation -- the old one, ready for ever; the fork, with the same
    transcript up to the move; and the agents view's own session.
    **Nothing in a payload or a transcript names the old session**: only
    the fork's command line, `--fork-session --resume <old transcript>`.
    So the hook reads it, on `SessionStart` only, and writes `moved_from`
    (`background_start`). **Only under the daemon's `bg-pty-host`**,
    written as `background`: a fork typed at a terminal sends `source:
    "fork"` too, and its old session lives on in its own pane. The old
    session ends ("background"), its subagents with it -- the fork starts
    again those that go on -- the page follows `cleared_into`, and the name
    moves (`_move_name`, shared with `link_clear`). Linux only, as
    `started_by` is. The old row's pane now shows the agents view, and an
    ended row is never typed into; the fork has no pane.
    **The agents view's own session has no row until it is given a task**
    (`untasked`, in `Store.visible`): `background`, no `moved_from`, and no
    prompt yet (`prompted`). The reader chose this. A line written before
    the hook wrote the key is a session at a terminal, as it was.
    `test_a_conversation_moved_to_the_background_is_one_row`,
    `test_a_fork_typed_at_a_terminal_ends_nothing`,
    `test_the_hook_says_which_session_a_background_fork_carries_on`,
    `tests/test_background.py`.
- **A state change clears the attention with it.** Every handler that sets a
  state calls `_clear_attention` — `SessionStart` did not, so a session killed
  at its dialog and resumed came back "ready" with the old permission question
  under it. **`_bury` is a change of state too**: nothing reports a death,
  so it is the one made outside the handlers, and it kept the question, with
  its buttons, whose keys went into whatever the pane ran next -- `2 1 Enter`
  into a new agent submits "21". `answer` refuses a session in
  `GONE_STATES` as well, for whatever a row still carries.
  `test_a_session_that_dies_on_its_question_forgets_it`,
  `test_no_answer_goes_to_a_session_that_is_over`.
  **A compaction is the exception**: an auto compaction fires
  `SessionStart` with `source=compact` in the middle of a turn, and the
  agent goes on. Setting "done" moved the row to ready, fired "has
  finished", and the row went to ready under a working agent.
  `_on_session_start` keeps "working" for it.
  `test_a_compaction_in_the_middle_of_a_turn_does_not_end_it`.
  **So is a `Stop` with a task still running in the background** (#447).
  The agent waits for it, and Claude Code wakes it with a prompt of its own
  when the task ends (`<task-notification>`, `TASK_ENDED`): the row went to
  ready, said "has finished", and went green again a moment later.
  `running_tasks` reads `background_tasks` (measured on 2.1.291, only
  `status: "running"` counted, `tests/fixtures/background_task.jsonl`);
  `_on_stop` keeps "working", says "waiting on: …", and sets no `ended_at`,
  so neither the unread mark nor the alert comes before the real end.
  `waits_on_tasks` keeps an idle `Notification` off that line, and only
  there: a turn an interrupt ended sends no `Stop`, and its idle prompt is
  still news. The notification's prompt is not the reader's, so it is not
  `last_prompt`, which the alert quotes. **The reader chose this knowing the
  cost**: a server started in the background keeps the row green until it
  ends. `test_a_turn_that_leaves_a_task_running_is_not_over`,
  `test_an_idle_prompt_still_speaks_for_a_row_with_no_task`.
  **And the wait clock only starts when the wait does**: a second
  notification about the same dialog moved it, so a row that had waited a
  minute said it had waited none.
- **Every line of the log is folded once, in the order it was written, and
  no event is dropped for its `ts`.** Handlers assign, never accumulate.
  `Store.apply` used to drop an event older than its session had seen, to
  skip an archive read a second time after a rotation, and it dropped real
  events too. The hook stamped `ts` before it took the lock, so of two
  hooks of one session at once the one that stamped later could write
  first -- one line in 120, with four real hooks at once -- and a lost
  `PermissionRequest` is a row that never goes amber. A clock stepped back
  by NTP or a VM resume dropped every event of every session until real
  time caught up. Now `append_event(record, stamp=True)` stamps `ts` under
  the lock, so new lines and their `ts` agree, and a repeat is kept out by
  its place in the file, not by its time. A log written before holds lines
  out of `ts` order; they fold in line order.
  `test_two_hooks_that_raced_for_the_lock_are_both_folded`,
  `test_a_clock_stepped_back_does_not_stop_the_fold`,
  `test_a_hook_stamps_its_time_once_it_holds_the_lock`.
  - **So `EventFollower.new_lines` never reads a line twice or out of
    order**: the time check hid both. It opens the live file *before* it
    lists the archives. A rotation links the archive before it unlinks the
    live name, so a listing taken after the open names every archive older
    than the open file; one not finished is read first, and the loop looks
    again. The listing used to be taken once a pass. At the start the fold
    reads a year of archives for seconds, a hook rotated meanwhile, and the
    new live file was read before the archive that came before it: an open
    question with no bar. **An archive that cannot be read stops the pass**
    and is tried again on the next, up to `ARCHIVE_TRIES` (`Tail.whole`).
    It used to be marked finished at the first failed `open` -- EMFILE, say
    -- and skipped until the daemon started again. **Only a pass that read
    none of it counts as a try**: an archive on a slow disk that gives a
    piece and then fails is moving, and it was given up after ten passes
    all the same.
    `test_a_rotation_in_the_middle_of_a_pass_is_read_once_and_in_order`,
    `test_a_rotation_just_after_the_listing_is_read_in_order`,
    `test_an_archive_that_could_not_be_opened_is_read_on_the_next_pass`,
    `test_an_archive_that_never_opens_is_given_up_in_the_end`,
    `test_an_archive_that_moves_is_not_given_up`.
  - **A listing that fails is not a listing with no archives**
    (#253). `archived_events_paths` gave `[]` for every error. A daemon
    short of descriptors read the live file as if no archive waited: the
    live tail started on the new file, and on the next pass the archive of
    the old file came from its top, after the newer events. A permission
    dialog already answered came back amber, with a No button on it. Now
    the listing gives None for any error but a missing folder, and
    `new_lines` then reads nothing, not even the live file, until a
    listing works. **Every caller says what None means to it**:
    `archive_log` does not rotate, and the hook writes its event into the
    file it holds -- a second `open` of the log waits on its own `flock`,
    because the lock belongs to the open file and not to the process;
    `read_events` raises, and `ls` and `doctor` say they cannot read the
    log. The hook's deadline is a `TimeoutError`, which is an `OSError`,
    and it is not a failed listing: it goes on out.
    `test_a_listing_that_fails_reads_nothing_until_it_works`,
    `test_a_listing_that_fails_does_not_bring_an_answered_dialog_back`,
    `test_a_rotation_with_no_listing_writes_the_event_where_it_is`,
    `test_the_hooks_deadline_in_the_listing_is_not_a_failed_listing`,
    `test_a_listing_that_fails_is_not_a_log_with_no_archives`.
  - **A file is read once, by its device and inode, whatever it is
    called** (#253). A rotation stopped between its `os.link` and its
    `os.unlink` -- the hook's deadline, a crash, an unlink that failed --
    leaves the live file under an archive name too, and the next rotation
    gives it a third. Read by name, the running follower read it again
    from its top, and every start and every `ls` read it twice. So
    `new_lines` does not read the newest archives that are the file its
    live handle holds (that file is still the live log, and the hooks still
    write to it), and it finishes without a read an archive whose file it
    finished under another name (`done_files`). The handover by inode is
    unchanged: the live tail goes to the first archive name of its file.
    **The live handle is not checked against `done_files`**: the live name
    only ever gets a new file, so a finished inode comes back as the live
    file only when an archive was deleted and its inode used again, and a
    follower that skipped it would be blind until a restart.
    `log_handles` does the same for `read_events` and `measure_log`, and
    it opens the live file *before* it lists the archives, like
    `new_lines`: listed first, a rotation in between left the newest
    archive out. `archive_log` takes a failed `unlink` as no rotation, so
    the hook's event is not lost.
    `test_a_rotation_cut_short_is_read_once`,
    `test_a_start_on_a_rotation_cut_short_reads_the_live_file_once`,
    `test_a_log_under_two_names_is_read_once`,
    `test_a_rotation_between_the_listing_and_the_live_file_is_read`.
- **The log is never thrown away, so nothing may hold it whole.** Every
  archive is kept (`archive_log`, `archived_events_paths`), and a year of
  heavy use is a few hundred megabytes. Three things grew with it, measured on
  a 200 MB log shaped like a year, 1,873 sessions: `Tail` read the whole rest
  of a file in one `read()` and kept it twice over, 641 MB resident; the fold
  built a `Session` for every one of those sessions and `visible()` forgot the
  quiet ones only after it, 80 KB each; and `git_wanted` kept the directory
  of every tree-touching event ever folded, so the first refresh ran git on a
  year of worktrees, deleted ones included. Now `Tail.lines` reads
  `TAIL_CHUNK` at a time, `fold` calls `forget_quiet` every `FORGET_EVERY` of
  the *log's* clock, and `reload_git` asks only about a directory a shown
  session is in: 28 MB, flat. **Forget by the last event, never the first**:
  a session that started weeks ago and is still going keeps where it
  started, and the test that holds it moves the session's `cwd` after its
  start, because every event carries one and a session forgotten and made
  again would otherwise look exactly right.
  - **A start folds the last `HISTORY_FOLDED` (30 days) of the log, not
    all of it** (#430): an archive last written before that is left out,
    by its file's time (`folded_long_ago`), in `EventFollower.new_lines`
    and in `read_events` (`log_handles(recent=True)`), so the page and
    `ls` agree. Every start folded every archive and grew with the whole
    history -- 5.5 s at 240,000 events, about 22 us an event. **So "keeps
    where it started" holds for 30 days, not a year**: a session that has
    run longer loses, after a restart, what its start alone said (`home`,
    `first_prompt`). The reader chose that, and the window, from three
    options; a snapshot of the folded state was the exact one, and the
    costlier: a second way to the same state, thrown away by every update.
    The archives stay: `measure_log` counts them and `search_log` reads
    them. **Never one already begun, and never the live file**: a tail
    handed over at a rotation was written just now.
    `test_a_start_leaves_out_the_archives_older_than_the_window`. **An empty piece is not the end
  of the file**: a line longer than `TAIL_CHUNK` gives nothing until one
  ends it, so the end is the size the file had when the read began.
  **One event that raises costs only itself**: `Tail.lines` counts the
  whole piece as read before it hands out a line, so an exception leaving
  the fold threw away every event after it in that piece, on every start.
  `Store.fold` catches per event and logs it.
  `test_one_event_that_cannot_be_folded_costs_only_itself`.
  `test_a_big_log_is_read_a_piece_at_a_time` measures what is held with
  `tracemalloc`; `test_the_first_read_holds_a_week_of_sessions_not_all_of_them`
  and `test_git_is_asked_about_the_sessions_shown_and_no_others` hold the other
  two.
- **An archive's name is taken with `os.link`, never `os.replace`.** The next
  number comes from a listing and is then used, and `os.replace` puts the log
  on top of anything that landed on that name in between, silently — the scar
  in `safety.md` ("A `flock` is on an inode"), where a rename over the one
  archive lost every event ever recorded.
  `os.link` refuses a taken name and costs one more try. The follower knows
  the file that has just become an archive by its inode and hands its tail
  over, place and all, because a tail that only knew names read all 20 MB of
  it again on every rotation.
- **`Tail` starting over is news the reader has to hear.** It restarts at
  offset 0 when the file shrinks or its inode changes, which is right — but a
  reader that only appends then drew the whole transcript a second time on top
  of what it held, and after a truncate went on showing text the file no
  longer had. `Tail.restarted` says so; `Transcript` clears and bumps `run`.
  The event log never lets its tail start over on a file it can still read
  on: the follower hands the tail to the archive, place and all (above).
- **`seq` is a place in one reading, not an identity.** The page patches by
  index, and `Daemon` builds a new reader whenever `transcript_path` changes —
  a session resumed from another directory, so `seq` counts from nought for
  the same session id. Every push and every reply carries `run`; a `run` the
  page has not seen replaces what it holds rather than being merged into it.
  Reproduce either one with a **rename**: an unlink and recreate may hand back
  the same inode, and then nothing restarts and the bug does not appear.
- **A pid is not an identity.** The numbers wrap. `pid_alive` asks `kill -0`
  *and* `looks_like_claude`, because a session that ended in the morning had
  its pid taken by something else by the evening and the row said "done" all
  day for an agent that was gone. Safe to read /proc there: a session only has
  a pid where `agent_pid` could read /proc in the first place.
- **A file over `CODE_WHOLE` lines is drawn a window at a time, and not
  painted.** Measured whole, in a browser, drawing and painting: 2,500 lines
  144 ms, 5,000 280 ms, 10,000 774 ms, 40,000 2.8 s — and it is paid again on
  every save of the file being read. `CODE_WHOLE` is 5,000, which covers a
  hand-written source file, which is what a reader is looking at. It was 2,000
  and an ordinary file lost its colour for nothing. `fillCode` builds the rows
  on screen between two spacers; a redraw costs 5 ms. **Below that length
  nothing changes**, so an ordinary file keeps the browser's own find and a
  copy of the whole thing, and the page says which of the two you got.
  - **A long file of long lines is drawn whole and not painted.** A
    minified bundle of 500 KB is one line, so `CODE_WHOLE` let it through,
    and highlight.js held the page for 1.2 s on one machine and 4 s on
    another, on every save of a watch build: sidebar, alerts and stream
    all stopped. The cost follows the highlighted answer, and code on long
    lines is dense: 90 KB of a bundle cost about as much as 290 KB of
    hand-written code in 5,000 lines. So `tooDenseToPaint` refuses a text over
    `PAINT_MAX` characters that has a line over `LONG_LINE`. **Not a cap on
    the characters alone**: 10 of 25 ordinary source files of 2,000 to
    5,000 lines in the standard library are over 100 KB, and they would
    have lost their colour -- the scar `CODE_WHOLE` carries from 2,000.
    `paintedLines` asks, so the Files tab, a diff and a slice all keep to
    it, and `drawFiles` says so in the note a windowed file shows.
    `test_a_bundle_on_one_line_is_not_coloured_and_says_so`.
- **On the Files tab the pane scrolls sideways, not the rows.** A scroller on
  `.dlines` put the horizontal bar under the last line of the file, where in a
  file of any length nobody ever scrolls to. The pane scrolls both ways, so the
  bar is at the bottom of the screen — and the place the reader had scrolled to
  carries over across a window move for free, because `.filescroll` is not
  rebuilt for a window move. **The Diff
  tab keeps its scroller on `.dlines`**, because it stacks many files in one
  pane and a bar at the bottom of the screen would belong to whichever block
  happened to be under it. The override sits beside `.dlines`, not behind
  `.filebody`, so the two are read together.
- **The file header stands outside the scroller.** `.filebody` is a flex
  column of two: `.where`, which does not move, and `.filescroll`, which
  does. The header used to be `position: sticky` inside the scroller, which
  keeps it in view but not out of the scrollbar's way — the bar ran the whole
  height of the pane, beside a line that never scrolls. Everything that
  scrolls the file scrolls `.filescroll`: `fillCode`, `lineTop`, `showLine`,
  and the place a redraw puts back.
- **The file body's redraw key holds the session.** Two sessions in one
  worktree land on the same file with the same mtime, and a key of the path
  and the mtime alone kept the first one's `.filescroll` for the second --
  whose listener writes nothing once another session is chosen. Its place
  was never kept, and a windowed file never filled: blank space.
  `test_two_sessions_on_one_file_each_get_their_own_scroller`.
- **A comment's box is its line, not rows.** `lineAt` counted the pixels of
  a tall comment as rows, so a reader scrolled into one taller than eight
  rows got a window that began past the screen and saw nothing.
  `test_a_tall_comment_in_a_windowed_file_is_a_line_not_rows`.
- **`.filescroll` is built with the file, so a different file starts at its
  top.** The pane used to be the scroller and outlived the file in it, so the
  next file opened wherever the last one had been read to. `same` is the other
  half of that: it is what refuses to carry the old place over.
- **A tab's empty state is inset by whatever its body does not inset**, and
  that is a wart, not a design. The Files tab's children have padding, the
  Diff tab's body has none at all — a diff's rows run to the edge — so
  `.diffscroll > .empty` brings its own. Two spellings of one idea. One inset on `.empty` itself would be the mechanism; it is not
  done because two of the five empty states sit in `.content` rather than in a
  `*body` and would move with it. When a fourth spelling is needed, do that
  instead of adding one. A margin, not a padding, either way: the block has to
  move, and a padded box still starts at the edge.
- **Wrapping and windowing cannot both be on.** A windowed file's rows are a
  grid the scrollbar is read against, and a wrapped row is not one row tall.
  The CSS is what enforces it — `:not(.windowed)` — rather than a ternary in
  one function and a promise in two comments. The control being disabled is a
  courtesy on top of that.
- **How a file is drawn is the reader's, and is kept in our `settings.json`.**
  Tab width and wrap are about these eyes, not about a session, so they are
  the menu's, like the theme (`tab_width`, `long_lines`). Both live on the
  root element, so the cascade obeys them and **neither
  control rebuilds anything** — `redrawCode` clears the key that guards an
  open comment box, so a preference that redrew took half a written comment
  with it. `readingWanted` falls back to the default for anything the file
  does not answer. **The
  controls are the settings menu's**, one place for the Files and the Review
  tabs; a windowed file, which cannot wrap, says "too long to wrap" while
  wrap is on, and the CSS shows it (`.nowrap`), so nothing is rebuilt.
- **`BIG_LINES` and `CODE_WHOLE` answer one question in two shapes**. The Diff tab closes a long file; the Files tab windows one. A diff
  stacks many files of differing height in one pane, so it has no grid for a
  scrollbar to be read against. Do not quietly make either into the other.
- **`CODE_H` is the row height in pixels and `.dlines` must set the same
  number.** A grid the scrollbar is read against cannot be `line-height: 1.65`.
  `.code.windowed .dlines` drops its padding for the same reason.
- **A slice of a file says which line it starts at.** `asLines(path, lines,
  from)` and `hunk.from`, which `walkHunks` reads when there is no `@@`
  header. A slice that thought it started at line one would anchor every
  comment in it to the wrong place.
- **Which file the pane holds is asked of the pane** (`pane.dataset.file`),
  never of the redraw key: `redrawCode` clears that key, so opening a comment
  box made the open file look like a new one — and in a windowed file that put
  the window back at the top, where the comment box it had just opened was not.
- **One renderer for a line, in `fillDiffFile`.** The Files tab, the Diff tab
  and an untracked file all go through it — `unifiedRow` and `pairRow` are
  its two shapes, and `putLineReview` is the one place either puts a `+`; a file being read is a hunk of
  `plain` lines. That is what makes a review work in both tabs — line 42 has
  the same anchor either way — and why there are not three ways to draw a line
  that drift apart.
- **The highlighter gets the whole file; `cutIntoLines` cuts the answer up.**
  A block comment or a long string only makes sense whole, so painting line by
  line gets them wrong. A span crossing a newline is closed and reopened on the
  next line. The cut walks the scrubbed fragment, never a string of HTML, and
  a line count that disagrees with the file paints nothing: colour on the wrong
  lines is worse than none.
  **So no CR goes into the highlighter** (`paintedLines`). The HTML
  parser in `paintedInto` reads CR LF, and a lone CR, as a line break, so a
  file saved on Windows had one line more than rows, and the page painted
  none of it, with no word why. Rows are cut on LF only, so no line moves.
  **A CR that ends a line goes, and one inside a line becomes a space,
  never nothing.** A line ends before an LF or at the end of the text: a
  hunk's side is its lines joined, so its last one stops on a bare CR, and
  a space there was one character more than the row. CSS draws a CR in the
  plain row as a space. Taken out, `a\rb` -- progress
  output in a log -- read `ab` once coloured, and on the Review tab every
  word mark after the CR stood one place late, because `wordDiff` counts
  the CR. A space keeps the length and what the reader sees.
  The Files tab, each side of a hunk on the Review tab, and a file shown in
  part all paint through `paintedLines`, so the one line covers the three.
  `test_a_file_with_a_carriage_return_is_painted`,
  `test_a_diff_of_a_file_with_windows_line_ends_is_painted`,
  `test_a_lone_carriage_return_keeps_the_word_marks_in_place`.
- **Reading the open file asks git twice and `file` once — and two of those
  are remembered.** The Files tab polls every two seconds, so the answers that
  cannot have changed must not be asked again: `Files.root_of` holds where the
  worktree starts, `Files.language_of` holds what `file` said, keyed on the
  path with its mtime and size. **`is_listed` is never cached**: it is the
  check that git still offers this name, and a remembered yes would let a file
  be read after it was taken out of the tree.
- **What language is this? Three questions, most certain first**:
  the name, then the shebang, then `file` on the daemon — asked only when the
  first two came up empty, so a suffix never pays for a subprocess. `file` is
  the third and last command this program runs, after git and tmux.
  Its answers come from `BY_MIME`, a list, not wholesale. **`text/x-c` is not
  on that list**: libmagic uses it for anything C-shaped and calls Rust and Go
  C source, measured. No paint beats a wrong one, and nothing here guesses from
  content beyond that list.
- **A fill must not depend on how tall a row turns out to be.** The chosen row
  used `box-shadow: inset 0 0 0 40px`, which fills inward from each edge, so a
  row with a name, a branch and a reason on it had an untinted stripe down its
  middle. A `linear-gradient` background layer covers any height and sits over
  the state's own colour instead of replacing it. The chosen row's fade is
  such layers too, over `--soft`, which each state sets.
- **What the row says a session is, is where it started, not where it
  stands.** `cwd` is in every hook payload and Claude Code moves it the
  moment the agent changes directory, so a row reading `repo/dir` renamed
  itself to `repo/src` mid-turn — and the worktree is the one fact on that
  row you cannot read anywhere else on the page. `Session.home` is stamped by
  `SessionStart`, because a resumed session really does start somewhere else,
  and otherwise only while nothing is known yet. **Not by a compaction's
  `SessionStart`** (`source=compact`): an auto compaction sends one in the
  middle of a turn, with the directory the agent has walked to, and the row
  renamed itself from `richpalm` to `src`.
  `test_a_compaction_does_not_move_where_the_session_started`. `Session.place` is the one
  spelling of the question, and the row, the label and `sort_sessions`'s
  tiebreaker all go through it — three call sites built the same string by
  hand before, which is three chances for one of them to answer differently.
  `cwd` is still what git, the Files tab and the Diff tab are asked about:
  it is where the agent is, which is the right question for those. **The
  row's worktree is the top of the worktree** once git has said where that
  is (`GitFacts.root`), so a session started in `src` still reads
  `richpalm`; `place` stays where it started, because it is a name.
- **A hook's empty `pane` and its `pid` of 0 are news, not gaps.** `cmd_hook`
  writes both keys on every event. `Store.apply` took a pane only when
  there was one, so a session that ran in `%5`, ended, and was resumed in
  a plain terminal kept `%5`: the page offered jump, send and an answer,
  and `tmux_send` typed into whatever `%5` held by then -- a shell, which
  runs the text, or another agent. After a tmux restart the ids start again
  at `%0`, so the old one can name any pane. A kept pid made `mark_dead`
  bury the resumed session as killed. Now a key that is there is taken,
  empty or not, and a pane that is not a pane id is taken as none. **A
  record that lacks the keys changes neither**: the daemon's own `Declined`
  carries neither. Everything that asks "is it in tmux" reads the empty
  pane as no: `in_tmux`, the row, the page's `s.pane`, `ls`, `link_clear`.
  `test_a_resume_outside_tmux_takes_the_old_pane_and_pid_away`.
  - **An agent that reads no terminal has no pane** (`reads_terminal`,
    in `cmd_hook`). `TMUX_PANE` is inherited by everything started in a
    pane. A Remote Control session (`claude rc`) is a worker, `claude
    --print --sdk-url … --input-format stream-json`, spawned with
    `stdio: ["pipe","pipe","pipe"]` (read off the 2.1.287 binary): it
    took the pane `claude rc` ran in, and every send went into the rc
    screen and was gone. A `claude -p` from an agent's Bash tool took the
    agent's pane, and a send went into that agent's prompt. **The test is
    the agent's stdin, `/proc/<pid>/fd/0`**: measured, an interactive
    session read `/dev/pts/1`, a `claude -p` a `pipe:[…]`. Not
    `CLAUDE_CODE_ENTRYPOINT` (`cli` against `sdk-cli`): a list of names
    that keep their pane is wrong for every name not on it yet. Not
    `CLAUDE_CODE_ENVIRONMENT_KIND=bridge` either, which rc sets: it names
    one of the two cases. **Where nothing can be read, the pane stays**: no
    pid, no `/proc` (macOS), so there an rc session is still typed into.
    The page needed nothing new: an empty pane is "not in tmux" already.
    **The worker is found by its executable, not only its name**
    (`looks_like_claude`): Claude Code's installer keeps each version at
    `~/.local/share/claude/versions/<version>` behind the `claude` link, and
    rc starts the worker from that real path, so it is called `2.1.287`.
    `agent_pid` passed over it to `claude rc`, which reads the pane, and on
    the owner's machine send stayed on after the first fix; this container's
    Claude Code is `/opt/claude-code/bin/claude`, so the measurement here
    could not show it. `/proc/<pid>/exe` in a `claude/versions` folder is
    Claude Code, whatever the process is called.
    `test_an_agent_that_reads_no_terminal_has_no_pane`,
    `test_reads_terminal_says_yes_unless_it_can_tell_no`,
    `test_a_remote_control_worker_is_the_agent_under_its_version_name`.
  - **Such an agent may have been run by another one, and the hook says
    which** (#422): `started_by` is the next Claude Code above it
    (`claude_from(parent_pid(pid))`), and 0 for an agent that reads a
    terminal, which pays nothing for the walk. Nothing in a `claude -p`'s
    payload or environment names its agent (topics/payloads). The store
    turns the pid into a session (`Store.parent_of`): **only one still
    running, and the last heard from** -- a pid comes round again, and a
    `/clear` keeps its process -- and a child's child goes under the first
    row, because the page draws a child as a line and a line has none. An
    rc worker's `started_by` is `claude rc`, which has no session, so it
    stays a row. `claude_from` is in `HOOK_PARTS`.
    **Every event that carries the key decides, and a pid is looked up
    once** (`started_pid`): linked for good, a `claude -p` resumed later
    at a terminal (`claude --continue` takes the newest session of the
    folder) stayed hidden under its old parent while its dialog waited;
    looked up on every event, each event of an rc worker scanned every
    session. **The walk has a `try` of its own**: a process name above
    that is not UTF-8 raised in `read_text`, and the event was lost, not
    only the link. `test_a_child_resumed_at_a_terminal_is_nobody_s_child`,
    `test_a_walk_that_raises_loses_no_event`.
    `test_the_hook_names_the_agent_that_ran_a_claude_p`,
    `test_a_child_is_linked_only_to_a_session_still_running`,
    `test_a_child_s_child_stands_under_the_first_row`.
- **A session with no pid cannot be checked.** `agent_pid` returns 0 where there
  is no `/proc` — on macOS, always. Such a session is taken for gone after
  `QUIET_MAX`. One with a pid is never buried for being quiet.
