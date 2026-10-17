# State

The session model, the log, and what the Files tab draws.

- **Amber means one thing: the agent cannot go on until you answer.** Not
  an idle `Notification`: `Stop` already ended the turn and nothing clears
  an idle prompt, so the row stayed amber for ever. **Drop a permission
  `Notification`, text too, once the session has sent a
  `PermissionRequest`**: it is the same news twelve seconds late, and
  re-raised the alarm for an answered question; its text alone left a
  "ready" row whose only line was the question. **A notification with no
  `notification_type` is read for the message that means a dialog, never
  assumed one**: `auth_success` went amber with nothing to clear it.
  - **A turn an API error ended is amber too** (`_on_stop_failure`): Claude
    Code fires `StopFailure` *instead of* `Stop`, and unregistered the row
    read "working" over a stopped agent. The reason is
    `last_assistant_message` (2.1.285, `tests/fixtures/stop_failure.jsonl`);
    `STOP_FAILURES` names an `error` without one. `doctor` flags an install
    that has not registered it.
    `test_an_api_error_ends_the_turn_and_says_why`,
    `test_an_api_error_with_no_words_is_named_by_its_kind`.
- **A question is a question, not a permission.** `AskUserQuestion`'s
  `PreToolUse` and `PermissionRequest` carry it whole in `tool_input`;
  `tool_target`'s catch-all clipped it to
  `AskUserQuestion {"questions": [{"question": "Approve the pla…`.
  **`read_ask` keeps what the page draws, named field by field**: a row goes
  to every browser on every push, so a field nobody reads must not go. The
  row says `asks:`, not `permission:`, which sent readers looking for
  another dialog.
- **`Session.asking` is cleared wherever the attention is, and only by its
  own `tool_use_id`**, read from `PreToolUse` (`PermissionRequest` has
  none): only the id proves *this* question was answered. Another call's
  `PostToolUse` is not an answer; calls overlap, and a stale question's
  buttons type into a terminal that moved on. **Nor is another call of the
  batch in the ~90 ms before the dialog is up**: it ran `_clear_attention`
  or set `asking` to `None`, amber over no bar, and `answer` refused.
  `_on_pre_tool` and `_on_tool_failed` hold the ask across that gap; a
  call starting *after* the dialog is the agent moving on.
  `test_another_call_before_the_dialog_does_not_take_the_question_away`.
- **`Session.permission` is the dialog whole, for the page, and goes with
  the attention**: a request is judged on all of it. `read_permission`
  sends every input field, withheld past `PERMISSION_SHOWN` (the page
  points at the pane). `test_a_permission_request_reaches_the_page_whole`,
  `test_a_permission_is_read_whole_and_declined_with_a_reason`.
  - **A plan is the exception: it is read in the transcript, not here**
    (#372): `ExitPlanMode` carries it whole (topics/payloads), real plans
    pass `PERMISSION_SHOWN`, and the panel drew raw Markdown in a cut-off
    `pre`.
    `plan_of` makes a block of kind `plan`, drawn by `markdown` and its
    scrub; `read_permission` sends `plan: true` and no fields;
    `drawPermission` says "It asks to start on the plan above", and
    `lastPlan` scrolls to it. The block keeps the call's `tool_use_id`, or a
    No's reason waits for ever (`call_answered`). The row shows the plan's
    title (`tool_target`), not `{"plan": "# …`; no plan, a tool row.
    `test_a_plan_waiting_for_approval_is_pointed_at_not_copied`,
    `test_a_long_plan_is_not_withheld`,
    `test_a_plan_is_a_block_of_its_own_with_the_whole_markdown`,
    `test_a_plan_is_read_as_markdown_and_the_dialog_points_at_it`.
  - **Its `key` is when the dialog came up**, so a No for one dialog is
    refused once another is up. **Its `call` comes from `Session.calls` by
    `tool_summary`, empty when two match**: `PermissionRequest` has no
    `tool_use_id`, so two identical commands at one moment cannot be told
    apart. `calls` is cleared at a turn's end and a new prompt: a call
    declined in the terminal never reports back, and made the next same
    call two matches. `test_a_request_two_open_calls_could_be_has_no_call`.
  - **The daemon writes a `Declined` record of its own** once the
    transcript shows the decline, and `_on_declined` ends that one dialog's
    wait: a No fires no hook. **A No in the terminal too**: each tick,
    `declined_in_terminal` writes it (`where: "terminal"`) for a dialog up
    whose call's result is `REJECTED`, not any result (a Yes has one), and
    never for a session in `declining`, whose No the page records. It reads
    again on that tick, so the row goes out no longer amber.
    `test_a_no_given_in_the_terminal_ends_the_wait`,
    `test_a_yes_in_the_terminal_is_not_taken_for_a_no`,
    `test_a_decline_seen_in_the_transcript_ends_the_wait`.
  - **The reader it makes does not stay for a week** (#294): `forget_gone`
    dropped one only with its session from the `Store`. A reader goes once
    no browser watches, no dialog is up (`Session.dialog`), and nothing has
    asked for `READER_IDLE` (the page fetches before it subscribes). Its run
    is kept in `Daemon.runs` and the next reader counts on: one back at run
    0 could match a `have` the page held, standing on blocks the file no
    longer ends with. `test_a_reader_nobody_needs_goes_and_its_run_counts_on`.
- **The question bar stands at the foot of every tab, and while it is up
  nothing else types** (#483, `drawAsking`, `whyNoText`, `cannot_type`'s
  `text`): on one tab only, send was pressed for submit, and the review's
  send stood under an unseen question. The views still hide it
  (`body.infeed`); the send box is away; `#sendreview` is hidden, not only
  off; the model menu and a command are refused; the daemon refuses a send
  while `asking`, as a question's dialog takes digits and Enter.
  `whyNotTyped` stays what the bar asks, or it refuses its own answer.
  `drawHeader` calls `drawAsking`, so a fifth call site cannot forget it.
  `test_a_question_stands_on_every_tab_and_nothing_else_types`,
  `test_no_text_is_typed_into_a_question`.
- **Picking types nothing; submit does**: a click into a terminal cannot be
  taken back, from a phone in a pocket too. `state.picked` keeps each
  question's picks **with the ask's id**, so no pick is submitted for the
  next question, **and with its shape**: an ask with no id (`PreToolUse`
  without `tool_use_id`) matched the empty picks, and the throw took
  `drawHeader` and the first transcript load down
  (`test_a_question_with_no_id_does_not_stop_the_page`). Picks survive a
  look at another tab: half an answer lost is a page nobody trusts.
  **Picking never rebuilds the bar** (`paintPicks` is all a click changes):
  a rebuild under the hand lands a click on the wrong option. Submit waits
  for every answer, as the agent asks them one after the other.
  - **The picks start again where a question arrives, never where it is
    drawn** (`fitPicks`, #573): `onSessions` and `choose` call it, and
    `drawAsking` only reads `state.picked`, since a draw writes no `state`.
    A second question on screen comes in a push, with no `choose`.
    `test_a_new_question_on_screen_starts_with_no_picks`.
- **A button that types into a terminal says what it types, before it is
  pressed**: each option shows its number, and submit says `presses 2,
  then 2 4 Tab, then Enter` -- `askKeys`, a preview only. **The
  page sends picks, never keys**: `submitAsk` posts option numbers to
  `answer`; the daemon derives the keys from its own question (`ask_keys`)
  and presses only digits, Tab and Enter (`tmux_keys`), refused for an ask
  id no longer waiting. `test_the_page_says_the_keys_the_daemon_presses`.
  **Submit does not clear the question; the `PostToolUse` does**, or a
  missed keystroke hides a question still standing. Submit stays off
  meanwhile (`state.answered`), and the bar says to answer in the terminal
  if it stays (`safety-typing.md`, "One send at a time").
  - **An answered question is kept by its ask id, outside
    `state.picked`**: a flag in the page-wide picks
    (`state.picked.pressed`) was lost when `drawAsking` rebuilt them for
    another session, re-enabling submit for keys already sent.
    `state.answered` holds the ids, `paintPicks` reads it, and
    `forgetAnswered` drops ids no session asks, on every `sessions` push.
    `test_an_answered_question_stays_answered_after_a_look_at_another`.
- **The keys are Claude Code's dialog's, measured, never a guess.** On
  2.1.281, in tmux against a fake Messages API: a digit answers a
    single-choice question **and moves on**; a multiple choice takes a digit
  per option to tick, then Tab; a closing
  review takes Enter on "Submit answers", but one single-choice question
  has no review, so Enter lands on the agent's prompt. Numbers through
  `send`, which adds Enter, answered the next question, hit Cancel (`2` on
  the review), and never submitted a multiple choice.
  - **One key per tmux command, `KEY_GAP` between**: `24` at once is one
    read, which the dialog takes as no key (measured).
  - **Each key an unbracketed paste of its bytes, never `send-keys`**
    (`KEY_BYTES`, #331): under `synchronize-panes` a key reaches every
    pane, and can answer or approve on another agent's prompt; bracketed,
    the dialog reads text. Pasted keys answer as `send-keys` did (2.1.287).
    `test_keys_go_one_paste_each_and_only_the_answer_keys`.
  - **An ask the daemon could not keep whole is not answered**
    (`answerable`): keys go by position, so a missing question or option
    shifts every key after it.
  - **A single-choice question with a `preview` on any option is another
    dialog**: a digit only moves the cursor and Enter answers, so `3` alone
    sent nothing. `shows_preview` is Claude Code's own test (its `pU`);
    where it hangs on an invisible character's width, the ask is not
    answerable: the keys would be a guess. A screen reader turns the layout
    off, and no payload says so.
  - **When Claude Code changes its dialog, measure again; never read the
    keys off the minified source**: Tab is bound twice there, and which
    wins is not written down.
- **The preview stands beside the options, and shows what the dialog's box
  shows**: an option's `preview` holds what the choice is about. `read_ask`
  sends it whole, never through `clip`, which folds a code box to one line;
  over `PREVIEW_UNREAD` it goes as `withheld`, with Claude Code's own
  sentence, and none reads "No preview available" (`previewText`). A
  multiple choice sends none: its dialog draws none. The box follows the
  pick (the first before one, as the cursor starts); `paintPicks` fills it,
  rebuilding nothing. **Beside, not under**: under, it fell below the bar's
  40vh fold, and is chosen without. `textContent` in a `pre` keeps a
  layout's spaces; one code fence round the whole comes off, as in the
  dialog. `test_the_preview_stands_beside_the_options_and_follows_the_pick`.
- **A call starting clears the attention; a call finishing clears only its
  own**: the dialog's call, paired by `tool_summary` (the `Session.permission`
  item). Two tools do run at once (1 in 233 calls measured, both `Bash`),
  both `PreToolUse` before the dialog, so the other's result turned the row
  green over a blocked agent. Nothing starts while a dialog is up, so a
  `PreToolUse` means the agent moved on: the only sign of a denial (the
  `Declined` item says why). **A result reuses its call's summary**
  (`calls`, by `tool_use_id`): recomputing it, secrets hidden, was a fifth
  of a start's fold (#430). Not lazily at the row: the pairing compares
  summaries during the fold. `test_a_result_reuses_its_calls_summary`.
  - **A subagent's call is not the agent moving on** (`mine_alone`, in
    `_on_pre_tool` and `_on_tool_failed`): subagents fire hooks under the
    agent's session id with an `agent_id` (#422, topics/payloads), and a
    subagent's `Read` cleared a question, or a No, still up. Its calls feed
    only its line under the row (`note_subagent`), even a result of the
    dialog's very command, which pairing by summary would take as its own.
    `test_a_subagents_call_does_not_take_the_question_away`,
    `test_a_subagents_call_does_not_close_a_permission_dialog`.
- **A `/clear` is one conversation in two sessions, and the page follows
  it.** Claude Code ends the session (`reason: clear`) and starts a new id
  (`source: clear`) in the same pane and process, 0.1 s apart (2.1.282);
  left on the ended one, the conversation looked lost. `link_clear` joins
  them in `Store.apply` by process, or by pane with no pid, within
  `CLEAR_GAP`, in either order. `followClear` follows the row's
  `cleared_into` **once, only when the link appears while the page is
  open** (`state.cleared`): a reader who goes back stays, and an older link
  was made under nobody's eyes. **A resume starts the link again**:
  `_on_session_start` resets `cleared_into` for any source but `clear` and
  `compact`, since `link_clear` joins only a session with none, and a
  second `/clear` joined nothing. **The reader's name moves**, out of
  `names.json`, not copied; a restart's fold finds nothing to move.
  `test_a_resumed_session_cleared_again_joins_the_new_one`,
  `test_a_clear_joins_the_session_it_ended_to_the_one_it_started`,
  `test_a_clear_is_not_joined_to_another_sessions_start`,
  `test_a_clear_with_no_pid_is_joined_by_its_pane`,
  `test_the_name_goes_with_a_clear_and_moves_once`,
  `test_a_clear_is_followed_and_a_reload_stays_on_it`,
  `test_a_reader_who_goes_back_to_a_cleared_session_stays_there`.
  - **A conversation the agents view moves to the background is joined the
    same way, by what the hook read** (`link_move`): `←` on an empty prompt
    reruns it in Claude Code's daemon as a fork with a new id
    (topics/payloads, `tests/fixtures/README.md`), the old session gets no
    `SessionEnd` and lives on as the agents view, and `mark_dead` never
    buries it: three rows for one conversation. **Only the fork's command
    line names the old session** (`--fork-session --resume <old transcript>`):
    the hook reads it on `SessionStart` only and writes `moved_from`
    (`background_start`), **only under the daemon's `bg-pty-host`**, as
    `background`: a fork typed at a terminal sends `source: "fork"` too,
    and its old session lives on. The old session ends ("background") with
    its subagents, the page follows `cleared_into`, the name moves
    (`_move_name`, shared with `link_clear`). Linux only, as `started_by`.
    An ended row is never typed into; the fork has no pane.
    - **The name moves in memory; `save_names` writes it once the fold is
      done** (#546): the fold, replay included, does no I/O.
      **`names_moved` is kept until a write succeeds** (#593): cleared
      first, a failed write was never retried, and a restart put the name
      back. `test_a_moved_name_that_could_not_be_written_is_written_later`.
    - **The agents view's own session has no row until given a task**
      (`untasked`, in `Store.visible`: `background`, no `moved_from`, not
      `prompted`). The reader chose this. A line from before the key is a
      terminal session.
    `test_a_conversation_moved_to_the_background_is_one_row`,
    `test_a_fork_typed_at_a_terminal_ends_nothing`,
    `test_the_hook_says_which_session_a_background_fork_carries_on`,
    `tests/test_background.py`.
- **A state change clears the attention with it**: every handler that sets
  a state calls `_clear_attention`; `SessionStart` did not, and a resumed
  session kept the old question. **`_bury` is a change of state too**, the
  one outside the handlers: its kept question's keys went into whatever
  the pane ran next (`2 1 Enter` submits "21"). `answer` also refuses a
  session in `GONE_STATES`.
  `test_a_session_that_dies_on_its_question_forgets_it`,
  `test_no_answer_goes_to_a_session_that_is_over`.
  - **A compaction is the exception**: its `SessionStart`
    (`source=compact`) comes mid-turn and the agent goes on, so
    `_on_session_start` keeps "working"; "done" put a working agent at
    ready and fired "has finished".
    `test_a_compaction_in_the_middle_of_a_turn_does_not_end_it`.
  - **So is a `Stop` with a task still running in the background** (#447):
    Claude Code wakes the agent with its own prompt when the task ends
    (`<task-notification>`, `TASK_ENDED`), so the row flickered ready.
    `running_tasks` reads `background_tasks` (2.1.291: only
    `status: "running"`, `tests/fixtures/background_task.jsonl`); `_on_stop`
    keeps "working", says "waiting on: …", and sets no `ended_at`, so no
    unread or alert comes early. `waits_on_tasks` keeps an idle
    `Notification` off that line only: an interrupted turn sends no `Stop`,
    and its idle prompt is news. The notification's prompt is not
    `last_prompt`, which the alert quotes.
  - **Nor is another session's message the reader's** (`AGENT_SENT`, #482):
    a subagent's hand-back (`<agent-message from=…>`) as `first_prompt`
    named the session in the row, the title and the alert; it is the latest
    event only. `test_another_sessions_message_does_not_name_the_session`.
    **`prompt_said` alone tells both apart**, and search asks it too
    (#536): reading `prompt` itself, search took them for the reader's.
    `test_search_reads_a_prompt_as_the_fold_does`.
  - **A task holds the row green only until Claude Code says the prompt is
    idle, when all it waits on is a command** (#488, `waits_on_agents`):
    under "green until it ends" (#447), a server or watch loop held a row
    green for hours. The idle `Notification` (a minute after the `Stop`)
    ends the turn: ready, `ended_at`, "in the background: …"; a wake turns
    it green again. Waiting on a subagent, the agent's next step, stays
    green. The reader chose this from a real session (every `Stop` listed a
    `shell` task) over ready at the `Stop` and green until the end.
    `test_a_turn_that_leaves_a_task_running_is_not_over`,
    `test_a_subagent_in_the_background_holds_the_row_green_while_idle`,
    `test_an_idle_prompt_still_speaks_for_a_row_with_no_task`.
  - **The wait clock starts only when the wait does**: a second
    notification of one dialog reset a minute's wait to none.
- **Every line of the log is folded once, in written order, and no event is
  dropped for its `ts`.** Handlers assign, never accumulate. Dropping
  events older than the session had seen (`Store.apply`) dropped real
  ones: hooks stamped before the lock and wrote out of order (1 line in
  120, four hooks at once), and a lost `PermissionRequest` never goes
  amber; a clock stepped back dropped all until it caught up.
  `append_event(record, stamp=True)` stamps under the lock; a repeat is
  kept out by its place in the file. Old logs fold in line order.
  `test_two_hooks_that_raced_for_the_lock_are_both_folded`,
  `test_a_clock_stepped_back_does_not_stop_the_fold`,
  `test_a_hook_stamps_its_time_once_it_holds_the_lock`.
  - **So `EventFollower.new_lines` never reads a line twice or out of
    order**: it opens the live file *before* listing archives. A rotation
    links before it unlinks, so that listing names every archive older than
    the open file; it reads an unfinished one first and lists again. One
    listing a pass read a new live file before its archive: an open
    question with no bar. **An archive that cannot be read stops the pass**
    and is retried, up to `ARCHIVE_TRIES` (`Tail.whole`); marked finished at
    a failed `open`, it was skipped until a restart. **Only a pass that read
    none of it counts as a try**: one that gives a piece is moving.
    `test_a_rotation_in_the_middle_of_a_pass_is_read_once_and_in_order`,
    `test_a_rotation_just_after_the_listing_is_read_in_order`,
    `test_an_archive_that_could_not_be_opened_is_read_on_the_next_pass`,
    `test_an_archive_that_never_opens_is_given_up_in_the_end`,
    `test_an_archive_that_moves_is_not_given_up`.
  - **A listing that fails is not a listing with no archives** (#253): with
    `[]` from `archived_events_paths`, an archive was read after newer
    events and an answered dialog came back amber. It gives None for any
    error but a missing folder, and `new_lines` then reads nothing, the
    live file included, until a listing works. **Every caller says what
    None means**: `archive_log` does not rotate and the hook writes into the
    file it holds (topics/safety, "A `flock` is on an inode", says why);
    `read_events` raises, and `ls` and `doctor` say they
    cannot read the log. The hook's deadline `TimeoutError` is an `OSError`
    but no failed listing: it goes on out.
    `test_a_listing_that_fails_reads_nothing_until_it_works`,
    `test_a_listing_that_fails_does_not_bring_an_answered_dialog_back`,
    `test_a_rotation_with_no_listing_writes_the_event_where_it_is`,
    `test_the_hooks_deadline_in_the_listing_is_not_a_failed_listing`,
    `test_a_listing_that_fails_is_not_a_log_with_no_archives`.
  - **A file is read once, by device and inode, whatever its name** (#253):
    a rotation stopped between `os.link` and `os.unlink` leaves the live
    file under archive names too, read twice by name. `new_lines` skips the
    newest archives that are its live handle's file (still the live log,
    still written), and those whose file
    it finished under another name (`done_files`); the live tail hands over
    by inode. **The live handle is not checked against `done_files`**: a
    finished inode is live again only when reused after a delete, and
    skipping it would blind the follower. `log_handles` does the same for
    `read_events` and `measure_log`, and also opens the live file before it
    lists: the other order missed the newest archive. `archive_log` takes a
    failed `unlink` as no rotation, so the hook's event is not lost.
    `test_a_rotation_cut_short_is_read_once`,
    `test_a_start_on_a_rotation_cut_short_reads_the_live_file_once`,
    `test_a_log_under_two_names_is_read_once`,
    `test_a_rotation_between_the_listing_and_the_live_file_is_read`.
- **The log is never thrown away, so nothing may hold it whole.** Every
  archive is kept (`archive_log`, `archived_events_paths`). On a 200 MB
  year of 1,873 sessions, `Tail` held 641 MB from one `read()`, the fold
  kept a `Session` for every one until `visible()`, and `git_wanted` ran
  git on a year of worktrees. `Tail.lines` reads `TAIL_CHUNK` at a time,
  `fold` calls `forget_quiet` every `FORGET_EVERY` of the *log's* clock,
  and `reload_git` asks only about shown sessions: 28 MB, flat.
  `test_a_big_log_is_read_a_piece_at_a_time` (`tracemalloc`),
  `test_the_first_read_holds_the_history_not_all_of_it`,
  `test_git_is_asked_about_the_sessions_shown_and_no_others`.
  - **Forget by the last event, never the first**, so a running session
    keeps where it started. The test moves `cwd` after the start, or a
    session forgotten and remade would look exactly right.
  - **A start folds the last `HISTORY_FOLDED` (30 days), not all** (#430):
    older archives are left out by file time (`folded_long_ago`) in
    `EventFollower.new_lines` and `read_events`
    (`log_handles(recent=True)`), so the page and `ls` agree. Folding all
    took 5.5 s at 240,000 events (22 us each) and grew. **So a session
    older than 30 days loses, after a restart, what only its start said**
    (`home`, `first_prompt`): the reader chose that and the window over a
    snapshot of the fold, exact but a second way to one state, thrown away
    by every update. `measure_log` and `search_log` still read the
    archives. **Never leave out one already begun, nor the live file**: a
    tail handed over at a rotation is new.
    `test_a_start_leaves_out_the_archives_older_than_the_window`.
  - **An empty piece is not the end of the file**: a line longer than
    `TAIL_CHUNK` gives nothing until it ends; the end is the size at the
    read's start.
  - **One event that raises costs only itself**: `Tail.lines` counts the
    piece read before handing out lines, so a raise lost the rest of it on
    every start. `Store.fold` catches and logs per event.
    `test_one_event_that_cannot_be_folded_costs_only_itself`.
- **An archive's name is taken with `os.link`, never `os.replace`**: the
  number comes from a listing, and `os.replace` silently overwrites what
  landed there meanwhile; a rename over the one archive lost every event
  (`safety.md`, "A `flock` is on an inode"). `os.link` refuses a taken
  name, at one more try. The follower hands its tail to the new archive by
  inode, place and all; by name it re-read 20 MB every rotation.
- **`Tail` starting over is news the reader must hear**: it restarts at
  offset 0 when the file shrinks or its inode changes, and an append-only
  reader drew the transcript twice, or kept truncated text.
  `Tail.restarted` says so; `Transcript` clears and bumps `run`. The event
  log's tail never starts over on a readable file: it hands over (above).
- **`seq` is a place in one reading, not an identity**: `Daemon` builds a
  new reader when `transcript_path` changes (a resume elsewhere), and `seq`
  restarts for the same id while the page patches by index. Every push and
  reply carries `run`; an unseen `run` replaces, never merges. Reproduce
  with a **rename**: an unlink and recreate may reuse the inode and hide it.
- **A pid is not an identity**: pids wrap, and a reused one kept a gone
  agent "done" all day. `pid_alive` asks `kill -0` *and*
  `looks_like_claude`. Reading /proc there is safe: a session has a pid
  only where `agent_pid` read /proc.
- **A file over `CODE_WHOLE` lines is drawn a window at a time, and not
  painted.** Measured whole, per save: 2,500 lines 144 ms, 5,000 280 ms,
  10,000 774 ms, 40,000 2.8 s. `CODE_WHOLE` is 5,000, enough for
  hand-written source; 2,000 took ordinary files' colour. `fillCode` builds
  the visible rows between two spacers (5 ms a redraw). **Below it nothing
  changes**: browser find and copy-all work, and the page says which you
  got.
  - **A long file of long lines is drawn whole and not painted**: a 500 KB
    one-line bundle froze the page 1.2 to 4 s per save of a watch build,
    since cost follows density (90 KB of bundle ≈ 290 KB of hand-written
    code). `tooDenseToPaint` refuses over `PAINT_MAX` characters with a line
    over `LONG_LINE`. **Never a cap on characters alone**: 10 of 25
    standard-library files of 2,000 to 5,000 lines exceed 100 KB, and
    would lose their colour.
    `paintedLines` asks, for the Files tab, a diff and a slice; `putFileCode`
    says so in a windowed file's note.
    `test_a_bundle_on_one_line_is_not_coloured_and_says_so`.
- **On the Files tab the pane scrolls sideways, not the rows**: on `.dlines`
  the bar sat under the file's last line, never reached. On the pane it is
  at the screen's bottom, and the place survives a window move, since
  `.filescroll` is not rebuilt. **The Diff tab keeps its scroller on
  `.dlines`**: its pane stacks files, and a bottom bar would belong to
  whichever block was under it. The override sits beside `.dlines`, not
  behind `.filebody`.
- **The file header stands outside the scroller**: `.filebody` is a flex
  column of `.where` and `.filescroll`; a `position: sticky` header inside
  ran the bar beside a line that never scrolls. Everything that scrolls the
  file scrolls `.filescroll`: `fillCode`, `lineTop`, `showLine`, a redraw.
- **The file body's redraw key holds the session**: two sessions on one
  file and mtime shared the first's `.filescroll`, whose listener stops
  for another session: the place was lost and a windowed file stayed blank.
  `test_two_sessions_on_one_file_each_get_their_own_scroller`.
- **A comment's box is its line, not rows**: `lineAt` counted a tall
  comment's pixels as rows, and the window began past the screen.
  `test_a_tall_comment_in_a_windowed_file_is_a_line_not_rows`.
- **`.filescroll` is built with the file, so a different file starts at its
  top**: a pane scroller kept the last file's place. `same` refuses to
  carry the old place over.
- **A tab's empty state is inset by whatever its body does not inset**, a
  wart: the Files tab's children pad, the Diff body does not, so
  `.diffscroll > .empty` brings its own. An inset on `.empty` itself is the
  mechanism, not done since two of five empty states sit in `.content`, not
  a `*body`, and would move with it. **At a fourth spelling, do that
  instead of adding one.** A margin, not a padding: a padded box still
  starts at the edge.
- **Wrapping and windowing cannot both be on**: a windowed file's rows are
  the scrollbar's grid, and a wrapped row is not one row tall. CSS enforces
  it (`:not(.windowed)`); the disabled control is courtesy.
- **How a file is drawn is the reader's, kept in our `settings.json`**: tab
  width, wrap and code width are about the eyes, not a session
  (`tab_width`, `long_lines`, `code_width`). `data-code` on the root sets
  `font-stretch` on `.dlines` and `.hunk`, which wear `--code-face`, Noto
  Sans Mono: one face in two widths, as the reader asked (Plex Mono has no
  narrow one); nothing else changes. **The face's variable is not
  `--code`**, a code block's ground colour, which the name took. On the
  root, **no control rebuilds anything**: `redrawCode` clears the key
  guarding an open comment box, losing half a comment. `readingWanted`
  falls back to the default for what the file lacks. **The controls are
    the settings menu's**, for the Files and Review tabs; a windowed file says
  "too long to wrap" while wrap
  is on, by CSS (`.nowrap`).
- **`BIG_LINES` and `CODE_WHOLE` answer one question in two shapes; never
  quietly make one the other**: the Diff tab closes a long file, as stacked
  files give no scrollbar grid; the Files tab windows one.
- **`CODE_H` is the row height in pixels and `.dlines` must set the same
  number**: a scrollbar grid cannot be `line-height: 1.65`.
  `.code.windowed .dlines` drops its padding for the same reason.
- **A slice of a file says which line it starts at**: `asLines(path, lines,
  from)` and `hunk.from`, which `walkHunks` reads when there is no `@@`
  header; otherwise every comment in it anchors to the wrong line.
- **Which file the pane holds is asked of the pane** (`pane.dataset.file`),
  never of the redraw key: `redrawCode` clears it, so a comment box made
  the file look new and a windowed file jumped to its top.
- **One renderer for a line, in `fillDiffFile`**: the Files tab, the Diff
  tab and an untracked file (`unifiedRow` and `pairRow`; `putLineReview`
  the one place either puts a `+`; a file read is `plain` lines), so line
  42 has one anchor in both tabs and three drawings cannot drift.
- **The highlighter gets the whole file; `cutIntoLines` cuts the answer
  up**: block comments and long strings paint wrong line by line. A span
  crossing a newline is closed and reopened. The cut walks the scrubbed
  fragment, never HTML text, and a line count off from the file paints
  nothing: wrong colour is worse than none.
  - **So no CR goes into the highlighter** (`paintedLines`): `paintedInto`'s
    HTML parser breaks at CR LF and lone CR, so Windows files had a line
    too many and went unpainted. Rows cut on LF only. **A CR ending a line
    goes; one inside becomes a space, never nothing**: a hunk side's last
    line can end on a bare CR, where a space was one too many; removed
    inside, `a\rb` read `ab` and word marks after it slipped, since
    `wordDiff` counts the CR. CSS draws a plain row's CR as a space. Files,
    both hunk sides and a part file all paint through `paintedLines`.
    `test_a_file_with_a_carriage_return_is_painted`,
    `test_a_diff_of_a_file_with_windows_line_ends_is_painted`,
    `test_a_lone_carriage_return_keeps_the_word_marks_in_place`.
- **Reading the open file asks git twice and `file` once, and two of those
  are remembered**, as the Files tab polls every two seconds:
  `Files.root_of` (the worktree's top), `Files.language_of` (keyed on
  path, mtime and size). **`is_listed` is never cached**: it checks that
  git still offers the name, and a remembered yes
  reads a file taken out of the tree.
- **What language is this? Three questions, most certain first**: the name,
  the shebang, then `file` on the daemon only if both are empty, so a
  suffix never costs a subprocess. `file` is the third and last command run,
  after git and tmux; its answers come from the `BY_MIME` list only.
  **`text/x-c` is not on it**: libmagic calls Rust and Go C (measured). No
  paint beats a wrong one; nothing guesses from content beyond that list.
- **A fill must not depend on how tall a row turns out to be**:
  `box-shadow: inset 0 0 0 40px` left an untinted stripe in a tall chosen
  row. A `linear-gradient` layer covers any height over the state's own
  colour; the chosen row's fade is such layers over `--soft`, which each
  state sets.
- **The row names a session by where it started, not where it stands**:
  `cwd` moves with the agent (`repo/dir` became `repo/src` mid-turn), and
  the worktree is on no other part of the page. `Session.home` is stamped
  by `SessionStart` (a resume really starts elsewhere), else only while
  unknown. **Never by a compaction's `SessionStart`** (`source=compact`):
  it comes mid-turn, and `richpalm` became `src`.
  `test_a_compaction_does_not_move_where_the_session_started`.
  `Session.place` is the one spelling, for the row, the label and
  `sort_sessions`'s tiebreaker; hand-built copies could disagree. Git and
  the Files and Diff tabs ask about `cwd`, where the agent is. **The row's
  worktree is the worktree's top** once git said (`GitFacts.root`), so a
  start in `src` reads `richpalm`; `place` stays, being a name.
- **A hook's empty `pane` and `pid` of 0 are news, not gaps**: `cmd_hook`
  writes both keys every event, and `Store.apply` takes a key that is
  there, empty or not (a non-pane-id is none). A kept `%5` after a resume
  outside tmux let `tmux_send` type into whatever held it (a shell runs the
  text), and ids restart at `%0` with tmux; a kept pid let `mark_dead`
  bury the resumed session. **A record lacking the keys changes neither**
  (the daemon's `Declined`). An empty pane is "not in tmux" for `in_tmux`,
  the row, the page's `s.pane`, `ls` and `link_clear`.
  `test_a_resume_outside_tmux_takes_the_old_pane_and_pid_away`.
  - **An agent that reads no terminal has no pane** (`reads_terminal`, in
    `cmd_hook`): `TMUX_PANE` is inherited, so a Remote Control worker
    (`claude rc` spawns
    `claude --print --sdk-url … --input-format stream-json` with piped
    stdio, per the 2.1.287 binary) swallowed sends, and a `claude -p` from
    an agent's Bash tool typed into that agent's prompt. **The test is the
    agent's stdin, `/proc/<pid>/fd/0`**: `/dev/pts/1` interactive,
    `pipe:[…]` for `claude -p` (measured). Not `CLAUDE_CODE_ENTRYPOINT`
    (`cli` against `sdk-cli`): a name list is wrong for every new name; not
    `CLAUDE_CODE_ENVIRONMENT_KIND=bridge`, which names only rc. **Where
    nothing can be read, the pane stays** (no pid, no `/proc` on macOS);
    the page needs nothing new, as an empty pane is "not in tmux" already.
    **The worker is found by its executable, not only its name**
    (`looks_like_claude`): the installer keeps
    `~/.local/share/claude/versions/<version>` behind the `claude` link, so
    the worker is called `2.1.287`, and `agent_pid` passed over it to
        `claude rc`, which reads the pane, so send stayed on; an install at
    `/opt/claude-code/bin/claude` cannot show
    it. `/proc/<pid>/exe` in a `claude/versions` folder is Claude Code.
    `test_an_agent_that_reads_no_terminal_has_no_pane`,
    `test_reads_terminal_says_yes_unless_it_can_tell_no`,
    `test_a_remote_control_worker_is_the_agent_under_its_version_name`.
  - **Such an agent may have been run by another, and the hook says which**
    (#422): `started_by` is the next Claude Code up
    (`claude_from(parent_pid(pid))`; `claude_from` is in `HOOK_PARTS`), 0
    for one reading a
    terminal, which skips the walk; no `claude -p` payload or environment
    names its agent (topics/payloads). `Store.parent_of` takes **only a
    session still running, the last heard from**: pids recur, and a
    `/clear` keeps its process. A child's child goes under the first row: a
    child is a line, and a line has none. An rc worker's `started_by` is
    `claude rc`, no session, so it stays a row. **Every event with the key
    decides, and a pid is looked up once** (`started_pid`): linked for good,
    a `claude -p` resumed at a terminal (`claude --continue`) stayed hidden
    while its dialog waited; looked up each event, rc events scanned every
    session. **The walk has a `try` of its own**: a non-UTF-8 process name
    raised in `read_text` and lost the event.
    `test_a_child_resumed_at_a_terminal_is_nobody_s_child`,
    `test_a_walk_that_raises_loses_no_event`,
    `test_the_hook_names_the_agent_that_ran_a_claude_p`,
    `test_a_child_is_linked_only_to_a_session_still_running`,
    `test_a_child_s_child_stands_under_the_first_row`.
- **A session with no pid cannot be checked**: `agent_pid` returns 0
  without `/proc` (always on macOS), and such a session is gone after
  `QUIET_MAX`. **One with a pid is never buried for being quiet.**
