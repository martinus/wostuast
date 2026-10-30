# State

The session's state: amber, questions and their keys, the permission
dialog, `/clear`, attention, pids and panes.

- **Amber means one thing: the agent cannot go on until you answer.** Not
  an idle `Notification`: nothing clears an idle prompt, and the row stayed
  amber for ever. **Drop a permission `Notification`, text too, once the
  session sent a `PermissionRequest`**: late, it re-raised an answered
  question. **A notification with no `notification_type` is read for the
  message that means a dialog, never assumed one**: `auth_success` went
  amber with nothing to clear it.
  - **A turn an API error ended is amber too** (`_on_stop_failure`):
    `StopFailure` comes instead of `Stop`, and the row read "working" over
    a stopped agent. The reason is `last_assistant_message`
    (`tests/fixtures/stop_failure.jsonl`), or `STOP_FAILURES` names the
    `error`. `doctor` flags an install that has not registered it.
    **A login ends every amber that asked for one, in every session, and
    those rows go to ready** (`Store.logged_in`, `Session.stopped_by`,
    `LOGIN_STOPS`, `auth_success`): `/login` sends no prompt and starts no
    call, so the row said "Please run /login" after the login worked, and
    the sessions share one login. A stop a login does not lift (a usage
    limit) stays, and so does a dialog.
    `test_an_api_error_ends_the_turn_and_says_why`,
    `test_an_api_error_with_no_words_is_named_by_its_kind`,
    `test_a_login_ends_every_amber_that_asked_for_one`.
- **A question is a question, not a permission.** `AskUserQuestion`
  carries it whole in `tool_input`; `tool_target`'s catch-all clipped it.
  **`read_ask` sends only what the page draws, field by field**: a row goes
  to every browser on every push. The row says `asks:`, not `permission:`.
- **`Session.asking` is cleared wherever the attention is, and only by its
  own `tool_use_id`** from `PreToolUse` (`PermissionRequest` has none):
  calls overlap, and a stale question's buttons type into a terminal that
  moved on. **Nor by another call of the batch in the ~90 ms before the
  dialog is up**: its `_clear_attention` left amber over no bar.
  `_on_pre_tool` and `_on_tool_failed` hold the ask across that gap.
  `test_another_call_before_the_dialog_does_not_take_the_question_away`.
- **`Session.permission` is the dialog whole, and goes with the
  attention**: a request is judged on all of it. `read_permission` sends
  every input field, withheld past `PERMISSION_SHOWN`.
  `test_a_permission_request_reaches_the_page_whole`,
  `test_a_permission_is_read_whole_and_declined_with_a_reason`.
  - **A plan is read in the transcript, not here** (#372): the panel drew raw
    Markdown (topics/payloads). `plan_of` makes a block of kind `plan`, drawn
    by `markdown`; `read_permission` sends `plan: true` and no fields;
    `drawPermission` points at it, `lastPlan` scrolls there. The block keeps
    the call's `tool_use_id`, or a No's reason waits for ever
    (`call_answered`). The row shows the plan's title (`tool_target`).
    `test_a_plan_waiting_for_approval_is_pointed_at_not_copied`,
    `test_a_long_plan_is_not_withheld`,
    `test_a_plan_is_a_block_of_its_own_with_the_whole_markdown`,
    `test_a_plan_is_read_as_markdown_and_the_dialog_points_at_it`.
  - **Its `key` is when the dialog came up**, so a No for one dialog is
    refused once another is up. **Its `call` comes from `Session.calls` by
    `tool_summary`, empty when two match**: a `PermissionRequest` has no
    `tool_use_id`. `calls` is cleared at a turn's end and a new prompt: a
    call declined in the terminal never reports.
    `test_a_request_two_open_calls_could_be_has_no_call`.
  - **The daemon writes a `Declined` record of its own** once the
    transcript shows the decline, and `_on_declined` ends that dialog's
    wait: a No fires no hook. **A No in the terminal too**:
    `declined_in_terminal` writes one each tick (`where: "terminal"`) when
    the dialog's call's result is `REJECTED`, not any result (a Yes has
    one), and never for a session in `declining`, whose No the page
    records. It reads again that tick, so amber ends at once.
    `test_a_no_given_in_the_terminal_ends_the_wait`,
    `test_a_yes_in_the_terminal_is_not_taken_for_a_no`,
    `test_a_decline_seen_in_the_transcript_ends_the_wait`.
  - **The reader it makes does not stay for a week** (#294; `forget_gone`
    dropped it only with its session). It goes once no browser watches, no
    dialog is up (`Session.dialog`), and nothing asked for `READER_IDLE`.
    `Daemon.runs` keeps its run, so the next reader counts on: a reader
    back at run 0 could match a `have` the page held.
    `test_a_reader_nobody_needs_goes_and_its_run_counts_on`.
- **The question bar stands at the foot of every tab, and while it is up
  nothing else types** (#483, `drawAsking`, `whyNoText`, `cannot_type`'s
  `text`): the dialog takes digits and Enter. The views hide it
  (`body.infeed`). The send box and `#sendreview` hide, the model menu and a
  command are refused, and so is a send while `asking`. `whyNotTyped` stays
  what the bar asks, or it refuses its own answer. `drawHeader` calls
  `drawAsking`, so no call site forgets it.
  `test_a_question_stands_on_every_tab_and_nothing_else_types`,
  `test_no_text_is_typed_into_a_question`.
- **Claude Code's "Switch model?" dialog is a question too** (#626,
  `model_ask`, `ModelAsked`, `ModelAnswered`, `Daemon.model_answered`):
  no hook reports it (topics/payloads), and the reader's next message went
  into it. A send of `/model <name>` (`MODEL_SWITCH`, read off `typed`,
  not what arrived) to an agent at its prompt with a reply behind it
  (`replies_held`) writes `ModelAsked` from `press_send`'s `landed`,
  **before the send's answer goes out**, or a reader of the log after it
  found nothing. The fold makes an ask of `kind: "model"`, one
  single-choice question whose digit `ask_keys` presses.
  - **Nothing is typed until the question is folded**: a send in the tick's
    second went into the dialog, and its Enter said Yes. `model_pending`
    refuses text for `MODEL_PENDING` after the `/model`, until the session
    holds that ask. **Its answer is pressed once** (`model_pressed`).
  - **It ends by the next `/model` block in the transcript after
    `model_after`**, whatever it says, given on the page or in the
    terminal, or by a change of state. A moment was not enough: an earlier
    `/model`'s answer ended a new question while its dialog stood. A
    `/model` to the model in use asks nothing, measured; its answer comes
    at once and ends the question within a tick. `/model` typed in the
    terminal is not seen at all, nor one to a `waiting` agent.
  `test_a_model_switch_is_asked_on_the_page_and_answered_with_its_digit`,
  `test_a_model_question_holds_the_prompt_from_the_moment_it_is_typed`,
  `test_only_a_model_switch_as_it_is_typed_asks`,
  `test_a_model_switch_with_nothing_to_read_again_asks_nothing`,
  `test_a_model_question_is_asked_of_an_idle_agent_and_ended_by_its_own_answer`.
- **Picking types nothing; submit does**: a click into a terminal cannot be
  taken back. `state.picked` keeps the picks **with the ask's id**, so none
  goes to the next question, **and its shape**: an ask with no id matched
  the empty picks and threw.
  `test_a_question_with_no_id_does_not_stop_the_page`. Picks survive a
  look at another tab. **Picking never rebuilds the bar**
  (`paintPicks` only): a rebuild under the hand lands a click on the wrong
  option. Submit waits for every answer.
  - **The picks start again where a question arrives, never where it is
    drawn** (`fitPicks`, #573): `onSessions` and `choose` call it, since a
    draw writes no `state`. A second question comes in a push.
    `test_a_new_question_on_screen_starts_with_no_picks`.
- **A button that types into a terminal says what it types, before it is
  pressed**: submit says `presses 2, then 2 4 Tab, then Enter` (`askKeys`,
  a preview only). **The page sends picks, never keys**: `submitAsk` posts
  option numbers to `answer`; the daemon derives the keys (`ask_keys`),
  presses only digits, Tab and Enter (`tmux_keys`), and refuses an ask id
  no longer waiting. `test_the_page_says_the_keys_the_daemon_presses`.
  **Submit does not clear the question; the `PostToolUse` does**, or a
  missed keystroke hides a question still standing. Submit stays off
  meanwhile (`state.answered`); a bar that stays says to answer in the
  terminal (topics/safety-typing, "One send at a time").
  - **An answered question is kept by its ask id, outside
    `state.picked`**: a flag there (`state.picked.pressed`) was lost when
    `drawAsking` rebuilt the picks, and submit sent keys again.
    `paintPicks` reads `state.answered`; `forgetAnswered` drops ids no
    session asks, on every `sessions` push.
    `test_an_answered_question_stays_answered_after_a_look_at_another`.
- **The keys are Claude Code's dialog's, measured, never a guess.** On
  2.1.281: a digit answers a single-choice question and moves on; a
  multiple choice takes a digit per option, then Tab; a closing review
  takes Enter on "Submit answers". One single-choice question has no
  review, so Enter lands on the agent's prompt. `send` adds Enter, so it
  answered the wrong question.
  - **One key per tmux command, `KEY_GAP` between**: `24` at once is one
    read, which the dialog takes as no key.
  - **Each key an unbracketed paste of its bytes, never `send-keys`**
    (`KEY_BYTES`, #331): under `synchronize-panes` a key reaches every
    pane; bracketed, the dialog reads text.
    `test_keys_go_one_paste_each_and_only_the_answer_keys`.
  - **An ask the daemon could not keep whole is not answered**
    (`answerable`): keys go by position.
  - **A single-choice question with a `preview` on any option is another
    dialog**: a digit only moves the cursor, and Enter answers.
    `shows_preview` is Claude Code's own test (its `pU`); where it hangs on
    an invisible character's width, the ask is not answerable.
  - **When Claude Code changes its dialog, measure again; never read the
    keys off the minified source**: Tab is bound twice there.
- **The preview stands beside the options, as the dialog's box does.**
  `read_ask` sends it whole, never through `clip`, which folds a code box
  to one line; over `PREVIEW_UNREAD` it goes as `withheld` (`previewText`).
  A multiple choice sends none, as its dialog draws none. `paintPicks`
  fills the box for the pick. Under the options, it fell below the fold. A
  `pre` keeps spaces (`textContent`); a code fence round the whole comes
  off.
  `test_the_preview_stands_beside_the_options_and_follows_the_pick`.
- **A call starting clears the attention; a call finishing clears only its
  own**, the dialog's call, paired by `tool_summary`: two calls run at
  once, and the other's result turned a blocked agent green. Nothing starts
  while a dialog is up, so a `PreToolUse` means the agent moved on: the
  only sign of a denial. **A result reuses its call's summary** (`calls`,
  by `tool_use_id`): recomputing it was a fifth of a start's fold (#430).
  `test_a_result_reuses_its_calls_summary`.
  - **A subagent's call is not the agent moving on** (`mine_alone`, in
    `_on_pre_tool` and `_on_tool_failed`): subagents fire hooks under the
    agent's session id with an `agent_id` (#422, topics/payloads), and
    their `Read` cleared a question. Their calls feed only their line
    under the row (`note_subagent`), even a result of the dialog's command.
    `test_a_subagents_call_does_not_take_the_question_away`,
    `test_a_subagents_call_does_not_close_a_permission_dialog`.
- **A `/clear` is one conversation in two sessions, and the page follows
  it.** Claude Code ends the session (`reason: clear`) and starts a new id
  (`source: clear`) in the same pane and process. `link_clear` joins them
  in `Store.apply` by process, or by pane with no pid, within `CLEAR_GAP`,
  in either order. `followClear` follows `cleared_into` **once, only when
  the link appears while the page is open** (`state.cleared`): a reader
  who goes back stays. **A resume starts the link again**:
  `_on_session_start` resets `cleared_into` for any source but `clear` and
  `compact`, or a second `/clear` joined nothing. **The reader's name
  moves** out of `names.json`, not copied.
  `test_a_resumed_session_cleared_again_joins_the_new_one`,
  `test_a_clear_joins_the_session_it_ended_to_the_one_it_started`,
  `test_a_clear_is_not_joined_to_another_sessions_start`,
  `test_a_clear_with_no_pid_is_joined_by_its_pane`,
  `test_the_name_goes_with_a_clear_and_moves_once`,
  `test_a_clear_is_followed_and_a_reload_stays_on_it`,
  `test_a_reader_who_goes_back_to_a_cleared_session_stays_there`.
  - **A conversation the agents view moves to the background is joined the
    same way** (`link_move`): `←` reruns it in Claude Code's daemon as a fork
    with a new id (topics/payloads, `tests/fixtures/README.md`). The old
    session gets no `SessionEnd` and `mark_dead` never buries it. **Only the
    fork's command line names the old session**
    (`--fork-session --resume <old transcript>`): the hook reads it on
    `SessionStart` and writes `moved_from` (`background_start`) **only under
    the daemon's `bg-pty-host`**, as `background`: a fork typed at a terminal
    sends `source: "fork"` too, and its old session lives on. The old session
    ends with its subagents, and the name moves (`_move_name`). Linux only.
    - **The name moves in memory; `save_names` writes it after the fold**
      (#546, **Principles**, 1). **`names_moved` is kept until a write
      succeeds** (#593): cleared first, a failed write was never retried.
      `test_a_moved_name_that_could_not_be_written_is_written_later`.
    - **The agents view's own session has no row until given a task**
      (`untasked`, in `Store.visible`: `background`, no `moved_from`, not
      `prompted`), as the reader chose.
    `test_a_conversation_moved_to_the_background_is_one_row`,
    `test_a_fork_typed_at_a_terminal_ends_nothing`,
    `test_the_hook_says_which_session_a_background_fork_carries_on`,
    `tests/test_background.py`.
- **A state change clears the attention with it**: every handler that sets
  a state calls `_clear_attention`, or a resumed session kept the old
  question. **`_bury` is a change of state too**: its kept question's keys
  went into whatever the pane ran next. `answer` refuses a session in
  `GONE_STATES`. `test_a_session_that_dies_on_its_question_forgets_it`,
  `test_no_answer_goes_to_a_session_that_is_over`.
  - **A compaction is the exception**: its `SessionStart`
    (`source=compact`) comes mid-turn, so `_on_session_start` keeps
    "working". `test_a_compaction_in_the_middle_of_a_turn_does_not_end_it`.
  - **So is a `Stop` with a task still running in the background** (#447):
    Claude Code wakes the agent when it ends (`<task-notification>`,
    `TASK_ENDED`), and the row flickered ready. `running_tasks` reads
    `background_tasks` (`status: "running"`,
    `tests/fixtures/background_task.jsonl`); `_on_stop` keeps "working",
    says "waiting on: …", and sets no `ended_at`, so no unread or alert
    comes early. `waits_on_tasks` keeps an idle
    `Notification` off that line only: an interrupted turn sends no `Stop`.
    Its prompt is not `last_prompt`.
  - **Nor is another session's message the reader's** (`AGENT_SENT`,
    #482): a subagent's hand-back (`<agent-message from=…>`) as
    `first_prompt` named the session. **`prompt_said` alone tells them
    apart**, for search too (#536).
    `test_another_sessions_message_does_not_name_the_session`,
    `test_search_reads_a_prompt_as_the_fold_does`.
  - **A turn that waits only on a command is "waiting"** (#617, which
    turned #488 round, `waits_on_agents`): #488 ended the turn at the idle
    `Notification`, so a server did not hold a row green for hours, and
    the row went blue over an agent waiting on a build. Now the `Stop`
    sets "waiting", and the idle `Notification` changes nothing: no
    `ended_at`, no unread, no alert, until a `Stop` with nothing running
    (then "has finished", from waiting as from working). A server keeps a
    row waiting; the reader chose this. Waiting on a subagent stays green.
    `test_a_turn_that_leaves_a_task_running_is_not_over`,
    `test_a_subagent_in_the_background_holds_the_row_green_while_idle`,
    `test_an_idle_prompt_still_speaks_for_a_row_with_no_task`.
  - **The wait clock starts only when the wait does**: a second
    notification of one dialog reset it.
- **A pid is not an identity**: pids wrap, and a reused one kept a gone
  agent "done" all day. `pid_alive` asks `kill -0` *and*
  `looks_like_claude`, safely: a session has a pid only where `agent_pid`
  read /proc.
- **The row names a session by where it started, not where it stands**:
  `cwd` moves with the agent. `Session.home` is stamped by `SessionStart`
  (a resume really starts elsewhere), else only while unknown, **never by
  a compaction's** (`source=compact`), which comes mid-turn.
  `test_a_compaction_does_not_move_where_the_session_started`.
  `Session.place` is the one spelling, for the row, the label and
  `sort_sessions`. Git and the tabs ask about `cwd`. **The row shows the
  worktree's top** once git said (`GitFacts.root`); `place` stays, being a
  name.
- **A hook's empty `pane` and `pid` of 0 are news, not gaps**: `cmd_hook`
  writes both keys every event, and `Store.apply` takes a key that is
  there, empty or not. A kept pane after a resume outside tmux let
  `tmux_send` type into whatever held it; a kept pid let `mark_dead` bury
  the resumed session. **A record lacking the keys changes neither** (the
  daemon's `Declined`). An empty pane is "not in tmux" for `in_tmux`, the
  row, the page's `s.pane`, `ls` and `link_clear`.
  `test_a_resume_outside_tmux_takes_the_old_pane_and_pid_away`.
  - **An agent that reads no terminal has no pane** (`reads_terminal`, in
    `cmd_hook`): `TMUX_PANE` is inherited, so a Remote Control worker
    (`claude rc`) swallowed sends, and a `claude -p` typed into the prompt
    of the agent that ran it. **The test is the agent's stdin,
    `/proc/<pid>/fd/0`**: `/dev/pts/1` interactive, `pipe:[…]` for
    `claude -p`. A list of names (`CLAUDE_CODE_ENTRYPOINT`,
    `CLAUDE_CODE_ENVIRONMENT_KIND=bridge`) misses every new one. **Where
    nothing can be read, the pane stays** (no `/proc` on macOS). **The
    worker is found by its executable** (`looks_like_claude`): it runs as
    `~/.local/share/claude/versions/<version>`, so `agent_pid` passed over
    it. `/proc/<pid>/exe` in a `claude/versions` folder is Claude Code.
    `test_an_agent_that_reads_no_terminal_has_no_pane`,
    `test_reads_terminal_says_yes_unless_it_can_tell_no`,
    `test_a_remote_control_worker_is_the_agent_under_its_version_name`.
  - **Such an agent may have been run by another, and the hook says which**
    (#422): `started_by` is the next Claude Code up
    (`claude_from(parent_pid(pid))`; `claude_from` is in `HOOK_PARTS`), 0 for
    one reading a terminal. No payload names it (topics/payloads).
    `Store.parent_of` takes **only a session still running, the last heard
    from**: pids recur, and a `/clear` keeps its process. A child's child goes
    under the first row; an rc worker stays a row. **Every event with the key
    decides, and a pid is looked up once** (`started_pid`): linked for good, a
    `claude -p` resumed at a terminal (`claude --continue`) stayed hidden.
    **The walk has a `try` of its own**: a non-UTF-8 process name raised in
    `read_text` and lost the event.
    `test_a_child_resumed_at_a_terminal_is_nobody_s_child`,
    `test_a_walk_that_raises_loses_no_event`,
    `test_the_hook_names_the_agent_that_ran_a_claude_p`,
    `test_a_child_is_linked_only_to_a_session_still_running`,
    `test_a_child_s_child_stands_under_the_first_row`.
- **A session with no pid cannot be checked**: `agent_pid` returns 0
  without `/proc` (always on macOS), and such a session is gone after
  `QUIET_MAX`. **One with a pid is never buried for being quiet.**
