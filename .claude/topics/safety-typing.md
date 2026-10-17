# Safety: what reaches a terminal

Every text and key the page sends to a pane: one at a time, through a paste buffer, scrubbed, counted; a No, an interrupt, what a refusal says.

- **One send at a time, per session and per pane.** A double-click or a
  second Enter typed a text twice, and two threads interleave texts and
  Enters into one prompt. **Two sessions can share a pane** (`claude -p`
  inherits `TMUX_PANE`), and a lock by session merged their sends (#331):
  `claim` takes the pane too (`typing_panes`); `release` gives it back.
  `test_two_sessions_in_one_pane_are_typed_into_one_at_a_time`.
  **A rename types too** (`type_rename`, #351): `/rename <name>` and Enter,
  through `holding` like a send, refused when the pane is held, never
  queued. `clean_name` makes it one line, no controls, `NAME_MAX`: a newline was
  an Enter. **And no backslash at its end**: backslash-Enter is a new line,
  so `/rename foo\` stayed unsent and the next message joined the name.
  `test_a_rename_waits_for_nothing_already_being_typed`,
  `test_a_rename_is_typed_on_one_line`,
  `test_a_name_ending_in_a_backslash_loses_it`.
  `sending` holds the sessions a send is on its way to; `submitReview`,
  `sendTyped`, `submitAsk` and `submitPermission` all go through it
  (`startSending`, `doneSending`). **Not "`submitAsk` disables its button"**
  (#226): `paintPicks`, on a pick or a tab switch, turned submit back on while
  keys went in `KEY_GAP` apart (`3 1 2 2 Enter Enter`). `paintPicks` keeps
  submit off while anything is on its way, and after the keys
  (`state.answered`): the question stays until its `PostToolUse`, and more
  keys land on the agent's next step. `drawAsking` repaints when a send
  starts or ends, as a waiting agent pushes nothing.
  **The send box empties the moment the text goes**, and a refusal puts it
  back before what was typed since: clearing on the answer lost new words,
  and a box still holding the text sent it twice.
  `test_a_double_click_sends_a_review_once`,
  `test_enter_twice_sends_once_and_keeps_what_came_after`,
  `test_a_refused_send_comes_back_in_front_of_what_was_typed_since`,
  `test_submit_stays_off_while_its_keys_go_in_and_after`,
  `test_submit_waits_for_a_message_on_its_way_and_comes_back`.
  - **The daemon holds the same rule, for every tab at once**: `sending` is
    one tab's, and two tabs or a script mixed two sends into one prompt, or
    an answer's keys with a send.
    `Daemon.claim` takes the session for `send`, `answer` and `decline`;
    `release` gives it back in a `finally`. The second is refused with 409,
    never queued: what it would type into is not what its sender saw.
    `claim` sets `declining` for a No, so a send is refused meanwhile.
    `test_two_sends_at_once_do_not_mix_in_the_pane`,
    `test_nothing_else_is_typed_while_an_answer_or_a_no_goes_in`.
    **The claims have their own lock, `typing_lock`, and the transcript
    readers another, `reading`** (#538): with one `Daemon.lock`,
    `read_transcript` of a long file held back every send. No method takes
    both.
    `test_a_slow_transcript_read_holds_back_no_send`.
- **A send goes through a paste buffer of its own, never through
  `send-keys -l`** (#328): tmux 3.4 refuses a command over 16,341 bytes
  (8,170 of `ä`), so a long log could not be sent.
  `tmux_send` runs `send-keys -X cancel`, then via `tmux_paste`
  `load-buffer -b <name> -` with the text on stdin and
  `paste-buffer -p -d -r -b <name> -t <pane>`, then one carriage return
  the same way without `-p`. Measure on a real pane before changing any
  part, never reason from tmux's source:
  - **`send-keys -X cancel` first, to leave copy mode**: in copy mode the
    paste lost its markers and the mode ate the Enter; bash ran one line of
    two. It fails in no mode, as usual, and the send goes on.
  - **`-r`**, or tmux pastes every newline as Enter.
  - **`-p`, so every send is one bracketed paste, one line too**: 100 KB
    on one line without markers reached Claude Code as several pastes,
    unsubmitted; with `-p`, 930 KB arrived whole. `-p` adds markers only
    for a program that asked (`ESC [ ? 2004 h`); one that did not cannot
    read them. **Not markers of our own**: they went on many lines only,
    and always.
  - **Enter is a pasted carriage return, not `send-keys Enter`**: under
    `synchronize-panes` a key reaches every pane of the window, a paste
    only its target; the others got an Enter that runs their prompt.
    Without `-p`, or the return is a new line inside a paste.
  - **A name of its own for each paste**, `wostuast-<pid>-<random>`:
    buffers are server-wide, and the reader's paste key never takes a
    named one.
  - **A failed paste deletes its buffer** (`delete-buffer`) and presses
    nothing: tmux 3.4 keeps it, `-d` or not, when the pane is gone, and a
    load that timed out may have filled it.
  - **No escaping at all**: stdin is no command line. Through `send-keys`,
    even after `-l --`, a final `;` ended the command ("use foo();"
    arrived without it) and `\;` went in.
  `test_send_leaves_copy_mode_pastes_the_text_and_then_a_return`,
  `test_a_paste_that_fails_presses_nothing_and_leaves_no_buffer`; in a real
  pane (skipped without tmux): `test_what_arrives_is_what_was_written`,
  `test_a_long_text_arrives_whole_as_one_paste`,
  `test_a_program_that_did_not_ask_sees_no_markers`,
  `test_a_pane_in_copy_mode_still_gets_one_paste`,
  `test_synchronized_panes_get_no_enter_of_ours`,
  `test_no_buffer_is_left_behind`.
- **A `send`'s size is counted in bytes, and the agent sets the number,
  not tmux.** `SEND_MAX` is 1 MiB: 1.36 MB arrived as one turn, and Claude
  Code itself refused 5 MB. Bytes, as `len()` lets three times as much
  Japanese through (`test_the_cap_on_a_send_is_in_bytes`). **A long
  message is refused, never cut or split across sends**: half a paste
  arrives as keystrokes. `POST_MAX` holds a `SEND_MAX` body as JSON six
  times over (`\u001b` is six bytes);
  `test_sending_more_than_fits_is_refused_not_cut` keeps it above
  `SEND_MAX`. A No's reason goes through `tmux_send` and this cap too.
  **The cap counts what is pasted**, `typed(text)`, not stripped colour codes. `test_the_cap_counts_what_is_pasted_not_the_controls`.
- **A verb tmux refused says so, and says only what it knows.** `send` and
  `jump` answered `{"done": false}` with no `error`, and `said` cleared the
  slot: the reader saw nothing. Every refusal here carries a message.
  **`send`'s message never claims nothing landed**: a failed Enter leaves
  the pasted text on the prompt, and "nothing went in" would have it sent
  twice.
- **An empty body and a refused body are different answers.** `asked()`
  never reads a body over `POST_MAX`, so routes saw `{}`. **Every route
  that reads `{}` as an answer checks it**: `send` said
  "nothing to send", `name` cleared the name (#235), `answer` said the
  question no longer waited (#254). `too_big` marks it, cleared at the top
  of `asked()`, as one keep-alive handler serves a whole connection. **`Serving.route` refuses
  `too_big` before any verb runs**, with the noun each `POST_VERBS` entry
  carries (#287), so no new verb can forget. The rename box's `maxLength`
  is `NAME_MAX` too (`test_a_row_is_renamed_where_it_stands`). A body not
  read because its end is not known (`unread`) is refused there too.
  **Every route is found after the other checks and before that one, in
  one place** (#545): `Serving.route` runs one order of checks for every
  request, and `find_route` looks in `ROUTES`, `GET_VERBS`, `POST_VERBS`;
  a route with its own size check is one a new route forgets.
  `test_every_route_refuses_what_it_must` walks the three tables: foreign
  Host, no token, too large. **A verb is a function `verb_<name>`, never a
  handler method**: `http.server` sets `command`, `path`, `headers`,
  `request` per request, and `self.command` hid `Serving.command`.
  `test_no_verb_is_an_attribute_of_the_handler`. **A verb returns
  `(code, payload)`, and `dispatch` sends it with the session's `id`**:
  only `refuse` added it, and one refusal went round. `raw` and `diff`
  send bytes and reply themselves.
  `test_every_verb_says_whose_answer_it_is`,
  `test_a_name_too_large_to_read_keeps_the_name_there_was`,
  `test_an_answer_too_large_to_read_says_that`,
  `test_a_body_that_is_not_read_is_not_taken_for_an_empty_one`.
- **Interrupt is Escape, and never Ctrl-C.** Escape stops a turn and
  keeps the work; Ctrl-C on an idle prompt clears it and a second exits
  (Claude Code's documentation). A turn can end before the key lands, so
  Ctrl-C can quit the session; Escape idle does nothing. `send-keys C-c` is
  a key 0x03, not a signal. `tmux_interrupt` pastes
  Escape's one byte (`KEY_BYTES`, via `tmux_paste`, no `-p`), not via
  `tmux_send`, which strips bytes below a space. **Pasted, never `send-keys
  Escape`**: under `synchronize-panes` it stopped every agent in the window
  (#331). A pasted ESC closes a permission dialog too (2.1.287). **With
  `-S` where tmux has it**: tmux 3.7 runs pastes through `vis(3)`, and
  Escape arrived as `^[`; tmux 3.4 refuses `-S`, so it pastes again
  without. A digit, Tab, Enter and every byte `tmux_send` passes go through
  `vis(3)` unchanged. Keys and the Escape leave copy mode first.
  `test_a_tmux_that_refuses_dash_s_still_gets_one_escape`,
  `test_interrupt_sends_escape_and_never_ctrl_c`,
  `test_synchronized_panes_get_no_answer_and_no_escape_of_ours`.
- **A No is Escape, and the reason is typed only once the transcript shows
  the dialog closed.** Escape declines every dialog, where the No's digit
  varies (4 or 3) and would be a guess; the next text joins the agent's "doesn't want to
  proceed" as Claude Code's own "what to do instead". **But the cursor
  starts on "1. Yes" and a digit picks**, so a reason typed into a dialog
  still up can approve it; Escape and text in one burst read as an Alt
  key, and no pause helps a busy Claude Code. So `decline` presses Escape, waits
  `DECLINE_WAIT` for the call's result in the transcript (`call_answered`,
  via `Block.answered`, as a result can be empty), and only then types the
  reason. No proof: no reason, no "declined"; the page says it was not
  seen to close. A dialog whose call cannot be named (two open
  calls alike) gets Escape and no reason box. **A call that has its result
  is refused**: a Yes in the terminal leaves the row amber (no hook says
  Yes), and Escape would stop the agent's next step. **An approved call
  still running looks like an open dialog**, so Escape stops it; the page
  says so before every press. **One decline at a time**: the page's
  `sending` guard, shared with the send box, and `Daemon.claim`, setting
  `Daemon.declining`, for a second tab. **No is off while something else
  is on its way, and says so** (`paintDecline`): a refused
  `submitPermission` did nothing, silently. Its own No is marked (`dataset.busy`) before it
  takes the guard, so it does not wait for itself. A half-written reason is
  kept across tabs (`state.declineWhy`).
  `test_a_decline_is_escape_then_the_reason_once_the_dialog_closed`,
  `test_a_reason_is_never_typed_into_a_dialog_not_seen_to_close`,
  `test_a_request_with_no_call_gets_escape_and_no_reason`,
  `test_a_request_answered_in_the_terminal_is_not_declined`,
  `test_a_decline_for_another_dialog_presses_nothing`,
  `test_a_decline_not_seen_to_close_does_not_say_declined`,
  `test_one_decline_at_a_time_per_session`,
  `test_a_no_waits_for_a_send_already_on_its_way`,
  `test_a_reason_half_written_survives_a_look_at_another_tab`.
  - **And no send goes into a dialog that is up**: "1" then Enter is Yes.
    `send` refuses while the row shows a dialog (`Session.dialog`: the
    permission while `needs_you`) and while a No is on its way. The page
    hides the send box (the dialog's bar says where), and the review's
    send is off, why in its `title`; the daemon's refusal is the rule, the
    page only saves a round trip. **`answer` refuses the
    same** (#254): one batch can hold a question and a permission, and the
    answer's keys are digits and Enter. **One test, `cannot_type`, for
    `answer`, `decline` and `send`, and its twin `whyNotTyped` on the page
    for every control that types** (#287): over, then a dialog up (not for
    a No); separate copies drifted and offered what the daemon refused. The
    claim is a `with` (`Daemon.holding`), so no verb leaves it held.
    `test_the_review_is_not_offered_to_a_session_that_is_over`,
    `test_a_question_is_not_answered_into_a_permission_dialog`,
    `test_an_answer_never_goes_into_a_permission_dialog`,
    `test_a_send_never_answers_a_permission_dialog`,
    `test_no_send_goes_in_while_a_no_is_on_its_way`,
    `test_the_send_box_is_away_while_a_permission_dialog_is_up`,
    `test_the_review_is_not_sent_into_a_permission_dialog`.
- **A control that cannot work is disabled where it stands, and says why.**
  Everything works with no tmux except what types into a pane: jump, send,
  an answer, a No, a review's submit. Jump (`#jump`) and the send box are
  absent with no pane; `paintPicks` once offered submit, "`presses 1`",
  into no terminal. **Reading is not acting**: the question bar stays, and
  only the press is refused. Grep `whyNotTyped`. **`#jump` wears `.theme`,
  which sets `display`**, so the one `[hidden]` rule (`daemon-and-page.md`)
  is what hides it.
- **Nothing below a space reaches a terminal.** `tmux_send` strips control
  characters except tab and newline, including the C1 block above `\x7f`
  (NEL, CSI) and U+2028, a line break `"\n" in text` misses. **And every
  lone surrogate**: `subprocess` passes them to tmux with
  `surrogateescape`, so U+DCC2 U+DC9B became c2 9b, CSI, in a real pane,
  and a high one failed the whole send. `CONTROL_CHARS` holds the range;
  `test_a_lone_surrogate_never_reaches_a_terminal`. A review quotes agent
  text, and `ESC [ 2 0 1 ~` ends a bracketed paste, leaving the rest as
  keystrokes, newlines as Enter; an escape byte is invisible in a preview.
- **A newline sent to a terminal is Enter.** Without bracketed paste
  markers a real shell ran the first line. Every send pastes with `-p`; see
  the paste buffer bullet.
- **Anything printed to a terminal is scrubbed, like anything sent to
  one.** `ls`'s last column is agent text (a `Notification` or a tool
  summary); one control set the terminal title and reddened the output,
  and `len` miscounted columns. `table`, where a row becomes a line, takes
  them out.
