# Safety: what reaches a terminal

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. Every text and key the page sends to a pane: one at a time, through a paste buffer, scrubbed, counted; a No, an interrupt, and what a refusal says.

- **One send at a time, per session -- and per pane.** A send to tmux takes long enough to
  press twice in, and a double-click on the review's send, or a second Enter
  in the send box, typed the text into the pane twice -- on two HTTP threads
  the text and the Enter of each can even interleave into one prompt.
  **Two sessions can stand in one pane** -- `claude -p` run from an
  agent's Bash tool inherits `TMUX_PANE` -- and a lock by session let a
  send to each go at once: their pastes and Enters made one prompt, 20
  times of 20 (#331). `claim` takes the pane too (`typing_panes`), and
  `release` gives it back. `test_two_sessions_in_one_pane_are_typed_into_one_at_a_time`.
  **A rename types too** (`type_rename`, #351): `/rename <name>` and Enter,
  through `holding` like a send, refused when the pane is held, never
  queued. The name goes through `clean_name` first -- one line, no
  controls, `NAME_MAX` -- because a newline in it was an Enter in the pane
  and the rest of the name a prompt. **And no backslash at its end**:
  Claude Code reads a backslash and Enter as a new line, so `/rename foo\`
  stayed in the box unsent and the reader's next message became the rest
  of the name. `test_a_rename_waits_for_nothing_already_being_typed`,
  `test_a_rename_is_typed_on_one_line`, `test_a_name_ending_in_a_backslash_loses_it`.
  `sending` holds the sessions a send is on its way to, and `submitReview`,
  `sendTyped`, `submitAsk` and `submitPermission` all go through it
  (`startSending`, `doneSending`). **Not "`submitAsk` disables its button",
  which this rule said until #226**: the button did not stay disabled. A
  click on an option ran `paintPicks`, which turned submit back on while
  the first answer's keys still went in `KEY_GAP` apart, and so did a look
  at another tab, which builds the bar again. A second submit made the pane
  read `3 1 2 2 Enter Enter`. Now `paintPicks` holds submit while anything
  is on its way to the session, and after its keys went in
  (`state.answered`), because the question stays until its
  `PostToolUse`, and a second set of keys lands on whatever the agent does
  next. `drawAsking` paints an unchanged bar, and a send starting or ending
  calls it, because an agent waiting on a question pushes nothing.
  **The send box empties the moment the text goes**, and a refusal
  puts it back in front of whatever was typed since. Clearing on the answer
  took the words typed while the send was on its way, which had gone
  nowhere; and a box still holding the sent text, edited meanwhile, sent it
  a second time. `test_a_double_click_sends_a_review_once`,
  `test_enter_twice_sends_once_and_keeps_what_came_after`,
  `test_a_refused_send_comes_back_in_front_of_what_was_typed_since`,
  `test_submit_stays_off_while_its_keys_go_in_and_after`,
  `test_submit_waits_for_a_message_on_its_way_and_comes_back`.
  - **The daemon holds the same rule, for every tab at once.** `sending`
    lives in one browser tab. Two tabs, or a tab and a script, ran two HTTP
    threads, and a tmux that takes a moment put "first", "second", Enter,
    Enter into the pane: one prompt of both. An answer's keys mixed with a
    send the same way. `Daemon.claim` takes the session for `send`,
    `answer` and `decline`, and `release` gives it back in a `finally`.
    The second one is refused with 409, never queued: it was asked for
    before the first landed, so what it would type into is not what its
    sender saw. `claim` also sets `declining` for a No, so a send is
    refused while a No is on its way.
    `test_two_sends_at_once_do_not_mix_in_the_pane`,
    `test_nothing_else_is_typed_while_an_answer_or_a_no_goes_in`.
    **The claims have a lock of their own, `typing_lock`, and the
    transcript readers another, `reading`** (#538). They were one
    `Daemon.lock`, and `read_transcript` reads the file while it holds
    it: the first read of a long transcript held back every send, answer
    and No. No method takes both. `test_a_slow_transcript_read_holds_back_no_send`.
- **A send goes through a paste buffer of its own, never through
  `send-keys -l`** (#328). `send-keys` took the text as an argument, and
  tmux 3.4 refuses a command over 16,341 bytes ("command too long";
  bisected, and 8,170 for `ä`, two bytes each), so a long log could not be
  sent at all. `tmux_send` runs `send-keys -X cancel`, then through
  `tmux_paste` `load-buffer -b <name> -` with the text on stdin and
  `paste-buffer -p -d -r -b <name> -t <pane>`, then the same for one
  carriage return, without `-p`. Each part is a scar or a measurement:
  - **`send-keys -X cancel` first, which leaves copy mode.** A pane scrolled
    back with the mouse wheel is in copy mode, and there a paste reached
    the program without the markers and the Enter was eaten by the mode: a
    real bash ran the first line of two, and the page said done. Found by
    an agent asked to break the promise. It fails for a pane in no mode,
    which is the usual answer, and the send goes on.
  - **`-r`, or every newline is Enter**: without it tmux pastes a newline
    as a carriage return. Measured in a raw pane.
  - **`-p`, so every send is one bracketed paste, one line too.** 100 KB on
    one line with no markers reached Claude Code 2.1.287 in pieces, read as
    several pastes with the Enter inside the last one: nothing was
    submitted, and the text sat on the prompt. With `-p` the same line went
    in five times of five, and logs of 310 KB and 930 KB each byte. `-p`
    adds the markers only for a program that asked (`ESC [ ? 2004 h`); one
    that did not cannot read them. **Not markers of our own**: they went
    on many lines only, and always.
  - **Enter is a pasted carriage return, not `send-keys Enter`.** Under
    `synchronize-panes` a key goes to every pane of the window and a paste
    only to its target -- measured -- so the other panes got a bare Enter,
    which runs whatever is on their prompt. Without `-p`, or the return is
    inside a paste and is only a new line.
  - **A name of its own for each paste**, `wostuast-<pid>-<random>`:
    buffers belong to the whole tmux server, and a named buffer is never
    the one a reader's own paste key takes.
  - **A failed paste deletes its buffer** (`delete-buffer`): tmux 3.4 keeps
    it, `-d` or not, when the pane is gone -- measured -- and after a
    failed load too, since one that ran out of time may have filled it.
    Nothing is pressed then.
  - **No escape at all.** stdin is not a command line, so a `;` at the end
    is a `;`. Through `send-keys` tmux read it as the end of a command, even
    after `-l --`: "use foo();" arrived as "use foo()", and the last `;`
    went as `\;`. Measure on a real pane before you change any of this; do
    not reason it out from tmux's source.
  `test_send_leaves_copy_mode_pastes_the_text_and_then_a_return`,
  `test_a_paste_that_fails_presses_nothing_and_leaves_no_buffer`, and in a
  real pane (they skip with no tmux): `test_what_arrives_is_what_was_written`,
  `test_a_long_text_arrives_whole_as_one_paste`,
  `test_a_program_that_did_not_ask_sees_no_markers`,
  `test_a_pane_in_copy_mode_still_gets_one_paste`,
  `test_synchronized_panes_get_no_enter_of_ours`,
  `test_no_buffer_is_left_behind`.
- **What a `send` may be is counted in bytes, and the agent sets the
  number, not tmux.** `SEND_MAX` is 1 MiB. Measured with Claude Code 2.1.287
  against a fake Messages API that kept each request: 1.36 MB arrived as
  the one user turn in 1.2 s, and 5 MB was refused by Claude Code itself,
  "Context limit reached". A megabyte is some 300,000 tokens, more than
  most models take. Bytes, because a cap on `len()` lets three times as
  much through in Japanese; `test_the_cap_on_a_send_is_in_bytes` holds it.
  **A long message is refused, never cut, and never split across two
  sends**: a paste broken in half leaves the rest arriving as keystrokes,
  which is the scar below. `POST_MAX` holds a body of `SEND_MAX` as JSON,
  six times over, for a log full of colour codes (`\u001b` is six bytes);
  `test_sending_more_than_fits_is_refused_not_cut` keeps it above
  `SEND_MAX`. The reason of a No goes through `tmux_send` and this cap too.
  **The cap counts what is pasted**, `typed(text)`: a log full of colour
  codes is smaller once they are out, and was refused for bytes that never
  go. `test_the_cap_counts_what_is_pasted_not_the_controls`.
- **A verb tmux refused says so, and says only what it knows.** `send` and
  `jump` both used to answer `{"done": false}` with no `error`, and `said`
  clears the slot for an answer that carries none — so the reader asked for
  something, did not get it, and read nothing at all. Every refusal on this
  path carries a message. **`send`'s message does not claim nothing landed**:
  `tmux_send` pastes the text and then presses Enter, and a failure on
  the Enter leaves the text sitting on the agent's prompt. "Nothing went in"
  would send the reader back to type it again, and it would arrive twice.
- **An empty body and a body that was refused is not the same answer.**
  `asked()` never reads a body over `POST_MAX`, so the route sees `{}` — and
  `send` refused it as "there is nothing to send", which is the opposite of
  what happened. `too_big` is set beside it, and cleared at the top of
  `asked()` rather than only set: with keep-alive one handler object serves
  every request on a connection. **Every route that reads `{}` as an answer
  checks it**: `name` did not, and read a 70,000-character paste as "take
  the name away" (#235). `answer` did not either, and said "that question
  is no longer waiting" about a question that was (#254). **So `Serving.route`
  refuses `too_big` itself, before any verb runs**, with the noun each
  `POST_VERBS` entry carries (#287): a new verb cannot forget it. The rename box
  has `maxLength` at `NAME_MAX` too,
  which `test_a_row_is_renamed_where_it_stands` holds in step. A body not
  read because its end is not known (`unread`) is refused in `Serving.route`,
  before any route sees it.
  **Every route is found before that check and after the others, in one
  place** (#545): `Serving.route` runs the checks in one order for every
  request, and `find_route` looks it up in `ROUTES`, `GET_VERBS` and
  `POST_VERBS`. The settings route wrote its own size check, and a new
  top-level route would have had to remember it.
  `test_every_route_refuses_what_it_must` walks the three tables: a foreign
  Host, a missing token, a body too large, for every route. **And a verb
  is a function, `verb_<name>`, never a method of the handler**:
  `http.server` sets `command`, `path`, `headers` and `request` on the
  handler for each request, and `self.command` hid the verb
  `Serving.command` on the instance; a verb named `path` would have broken
  every request. `test_no_verb_is_an_attribute_of_the_handler`. **A verb
  returns what it answers, `(code, payload)`, and `dispatch` sends it
  with the session's `id`**: only `refuse` added the `id`, and one
  refusal went round it. `raw` and `diff` send bytes and reply
  themselves. `test_every_verb_says_whose_answer_it_is`.
  `test_a_name_too_large_to_read_keeps_the_name_there_was`,
  `test_an_answer_too_large_to_read_says_that`,
  `test_a_body_that_is_not_read_is_not_taken_for_an_empty_one`.
- **Interrupt is Escape, and never Ctrl-C.** Claude Code's own
  documentation: Escape stops the current response or tool call mid-turn and
  "Claude keeps the work done so far"; Ctrl-C "interrupts a running
  operation", but "if nothing is running, the first press clears the prompt
  input and a second press exits Claude Code". A turn can end between deciding
  to stop a session and the key landing, so Ctrl-C is a race whose losing
  side is a session that quit. Escape on an idle prompt does
  nothing. `tmux_interrupt` pastes the one byte Escape is
  (`KEY_BYTES`, through `tmux_paste`, without `-p`), as `tmux_send` pastes
  its Enter -- not something that could go through `tmux_send`, which strips
  every byte below a space on purpose. **Pasted, never `send-keys
  Escape`**: under `synchronize-panes` a key goes to every pane of the
  window, and the Escape meant for one agent stopped every agent beside it
  (#331). Measured on 2.1.287: a pasted ESC closes a permission dialog with
  the same "Interrupted · What should Claude do instead?". **With `-S`
  where the tmux has it**: tmux 3.7 runs a paste through `vis(3)`, and
  the Escape arrived as the two characters `^[`, typed into the dialog;
  tmux 3.4 refuses `-S`, and the paste goes again without it. Found by an
  agent asked to break the promise, on a tmux 3.7 it built; a digit, Tab,
  Enter and every byte `tmux_send` lets through pass `vis(3)` unchanged.
  `test_a_tmux_that_refuses_dash_s_still_gets_one_escape`. Keys and the
  Escape leave copy mode first, as a send does. Measured:
  `send-keys C-c` puts 0x03 into a raw-mode app as a keystroke it reads, not
  as a signal. `test_interrupt_sends_escape_and_never_ctrl_c`,
  `test_synchronized_panes_get_no_answer_and_no_escape_of_ours`.
- **A No is Escape, and the reason is typed only once the transcript shows
  the dialog closed.** Measured against 2.1.282 in tmux, with a fake
  Messages API asking: Escape declines every permission dialog, where the
  number of "No" is 4 on a command and 3 on a file -- so a digit would be a
  guess. The agent then gets Claude Code's own "the user doesn't want to
  proceed", and whatever is typed next arrives in the same message, which
  is Claude Code's own way to say what to do instead. **But the cursor
  starts on "1. Yes", and a digit picks an option**, so a reason typed into
  a dialog still up can approve what was declined. Measured: Escape with
  the reason straight after is read in one burst as an Alt key, and the
  dialog stayed up. A pause does not fix it, because a busy Claude Code
  reads a burst. So `decline` presses Escape, then waits `DECLINE_WAIT` for
  the call's own result in the transcript (`call_answered`, through
  `Block.answered`, because a result can be empty) and types the reason
  only after. No proof, no reason, and no "declined" either: the page says
  the dialog was not seen to close. A dialog whose call cannot be named --
  two open calls reading the same -- gets Escape and no reason box. **A
  call that already has its result is refused**: the row stays amber after
  a Yes in the terminal, because no hook says Yes, and an Escape would stop
  whatever the agent went on to do. **An approved call still running cannot
  be told from a dialog still up** -- its result comes when it ends -- so
  there the Escape stops it, and the page says that before every press.
  **One decline at a time**: the page's `sending` guard, which the send box
  shares, and `Daemon.claim`, which sets `Daemon.declining`, for a second tab.
  **No is off while something else is on its way, and says so**
  (`paintDecline`), as submit on a question is: `submitPermission` refused
  then, and a No that could be pressed did nothing, with no word why. A
  No of its own is marked (`dataset.busy`) before it takes the guard, so
  the bar does not say it waits for itself. A reason half written is
  kept across a look at another tab (`state.declineWhy`), as the question
  bar keeps its picks.
  `test_a_decline_is_escape_then_the_reason_once_the_dialog_closed`,
  `test_a_reason_is_never_typed_into_a_dialog_not_seen_to_close`,
  `test_a_request_with_no_call_gets_escape_and_no_reason`,
  `test_a_request_answered_in_the_terminal_is_not_declined`,
  `test_a_decline_for_another_dialog_presses_nothing`,
  `test_a_decline_not_seen_to_close_does_not_say_declined`,
  `test_one_decline_at_a_time_per_session`,
  `test_a_no_waits_for_a_send_already_on_its_way`,
  `test_a_reason_half_written_survives_a_look_at_another_tab`.
  - **And no send goes into a dialog that is up.** The send box stayed on
    screen under a dialog, and `send` refused only a session that was
    over: "1" went in, then Enter, which is Yes. So `send` refuses while
    the row shows a dialog (`Session.dialog`: the permission while
    `needs_you`, the row's own test) and while a No is on its way. The page hides the send
    box in the same state, and the dialog's bar says where it went; the
    review's send is off and says why in its `title`. The daemon's refusal
    is the rule, and the page only saves the reader the round trip.
    **`answer` refuses in the same state** (#254): one batch of calls can
    hold a question and a command that asks for permission, and the
    answer's keys are digits and Enter. Whether Claude Code shows both at
    once was not measured; the refusal costs nothing when it does not.
    **One test, `cannot_type`, for `answer`, `decline` and `send`, and its
    twin `whyNotTyped` on the page for every control that types** (#287):
    over, then a dialog up (not for a No). Each verb and each control wrote
    its own, and they drifted: the review's send was offered into a session
    that was over, and the answer's submit into an open dialog, both of
    which the daemon refused. The claim is a `with` (`Daemon.holding`), so
    no verb can leave the session held.
    `test_the_review_is_not_offered_to_a_session_that_is_over`,
    `test_a_question_is_not_answered_into_a_permission_dialog`.
    `test_an_answer_never_goes_into_a_permission_dialog`,
    `test_a_send_never_answers_a_permission_dialog`,
    `test_no_send_goes_in_while_a_no_is_on_its_way`,
    `test_the_send_box_is_away_while_a_permission_dialog_is_up`,
    `test_the_review_is_not_sent_into_a_permission_dialog`.
- **A control that cannot work is disabled where it stands, and says why.**
  Everything on this page works with no tmux — the sidebar, all three tabs,
  alerts, the spend on the strip. The things that do not are the ones that
  type into a pane: jump, send, answering a question, a No and submitting a
  review. Jump (`#jump`) and the send box are simply absent for a session
  with no pane, and the review's submit has always refused. `paintPicks`
  enabled **submit** on a question and said `presses 1`, which is a promise
  of keystrokes into a terminal that does not exist. **Reading is not
  acting**: the question bar stays where it is. It is the press that is
  refused. Grep `whyNotTyped`. **`#jump` wears `.theme`, which sets `display`**,
  and the one `[hidden]` rule (`daemon-and-page.md`) is what hides it.
- **Nothing below a space reaches a terminal.** `tmux_send` strips control
  characters, keeping tab and newline. "Below a space" includes the C1 block
  above `\x7f` — NEL and CSI are controls, and U+2028 is a line break that
  `"\n" in text` does not see, so it went out unpasted. **So is every lone
  surrogate**: JSON can carry one, and `subprocess` hands an argument to
  tmux with `surrogateescape`, so U+DCC2 U+DC9B left as the bytes c2 9b,
  which is U+009B, CSI -- measured in a real pane. A high one made the
  encode fail, and the whole send with it. `CONTROL_CHARS` holds the
  range; `test_a_lone_surrogate_never_reaches_a_terminal`.
  A bracketed paste ends at `ESC [ 2 0 1 ~`,
  and a review quotes lines an agent wrote, so those bytes would end the paste
  and leave the rest arriving as keystrokes — with any newline as Enter. A
  person reading the preview cannot catch this; an escape byte is invisible.
- **A newline sent to a terminal is Enter.** Without the bracketed paste
  markers a real shell ran the first line. Every send is a paste with
  `-p`, which brings them; see the paste buffer bullet.
- **Anything printed to a terminal is scrubbed, like anything sent to one.**
  `ls`'s last column is a `Notification` message or a tool summary — text an
  agent wrote. `table` takes the control characters out, in the one place a
  row becomes a line; one of them set the terminal's title and reddened the
  rest of the output, and `len` counting the escape bytes made the columns
  wrong as well.
