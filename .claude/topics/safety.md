# Safety — the page can type into a terminal

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. What may reach a terminal, what may be read, and who may ask.

- **Never approve a permission prompt.** Claude Code reads a hook's stdout as
  its answer, and we register `PermissionRequest`. One `print()` in `cmd_hook`
  answers a permission dialog for the user. Logging goes to the log file. Tests
  assert the silence by event name; never weaken them.
- **The hook must never block Claude Code.** try/except around everything,
  `give_up_after` deadline, always exit 0. Keep all three. The deadline covers
  every wait at once, including a stdin that never closes — **and it stays
  armed over the logging on the way out.** `log` opens and writes a file, and
  the failure being logged may be that the filesystem is not answering.
  **Armed again, not merely left**: an alarm fires once, so when the failure
  *is* the timeout nothing was armed at all, and the status line cancelled
  its alarm before it logged. Both arm `LOG_TIMEOUT` over the logging.
  `test_a_failure_is_logged_under_a_deadline_even_after_a_timeout`.
- **Every POST carries a token.** A cross-origin `fetch` may POST to a loopback
  port unasked, and the effect here is `tmux send-keys` into a live terminal.
  `allowed()` wants three things to agree: Host, an Origin that is ours when
  there is one, and the token printed into the page.
- **No page of ours inside another page.** Framed by another origin, the
  page is still our origin and holds the token, so every POST it makes
  passes `allowed()` -- and an invisible frame over a decoy turned two clicks
  into an Escape in an agent's pane, shown with a real browser. The token and
  the Origin check stop another site's *requests*; only `X-Frame-Options:
  DENY` and `frame-ancestors 'none'`, which `reply` sends on every answer,
  stop its *clicks*. `test_the_page_cannot_be_framed`.
- **One send at a time, per session.** `tmux send-keys` takes long enough to
  press twice in, and a double-click on the review's send, or a second Enter
  in the send box, typed the text into the pane twice -- on two HTTP threads
  the text and the Enter of each can even interleave into one prompt.
  `sending` holds the sessions a send is on its way to, and `submitReview`,
  `sendTyped`, `submitAsk` and `submitDecline` all go through it
  (`startSending`, `doneSending`). **Not "`submitAsk` disables its button",
  which this rule said until #226**: the button did not stay disabled. A
  click on an option ran `paintPicks`, which turned submit back on while
  the first answer's keys still went in `KEY_GAP` apart, and so did a look
  at another tab, which builds the bar again. A second submit made the pane
  read `3 1 2 2 Enter Enter`. Now `paintPicks` holds submit while anything
  is on its way to the session, and after its keys went in
  (`state.picked.pressed`), because the question stays until its
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
- **The daemon answers on localhost only.** Binding to 127.0.0.1 is not enough —
  a site can point its own name at 127.0.0.1. `Serving.ours()` checks Host, and
  a request without one is refused: an empty Host used to pass, which made the
  check skippable by leaving the header out.
- **A check must fail closed, and nothing may run outside the guard.** Both
  checks used to sit in front of the `try`, where `Origin: http://[::1` or one
  byte above 0x7f in the token header killed the thread — no status line, a
  traceback into the terminal running `serve`, from a request nobody had
  authenticated. They refuse a header they cannot read; `guarded()` catches
  the rest, and it wraps the whole of a request.
- **A body that is not read stays in the socket.** `asked()` refuses one over
  `POST_MAX`, and with keep-alive the rest of it was parsed as the next
  request: the daemon answered a `GET` written inside a refused POST's body,
  three answers on one connection. Refusing to read the body closes the
  connection. The handler has a socket timeout for the other half of it — a
  `Content-Length` announced and never sent held a thread for ever.
- **The page never trusts what an agent wrote.** Markdown goes into an inert
  `<template>`, is scrubbed to an allowlist, and only then inserted. Values from
  events use `textContent`. Assigning `innerHTML` first fires `onerror` before
  any scrub runs — that was real.
- **An autolink runs after the scrub, over text nodes, and checks its own
  href.** `linkTickets` builds one anchor at a time and never parses
  anything, so a `url` template can put text on the page and nothing else.
  `ticketUrl` tests for `http(s)` a second time, although `link_trouble`
  already refused anything else: the two sides are far apart and only one of
  them is the one that inserts. `links.json` is the reader's own file, in
  the state directory — never a per-worktree one, which an agent could write.
- **Nothing can time a regular expression out in a browser.** `risky_pattern`
  spots the one shape that backtracks catastrophically — a quantifier inside
  a quantified group — and `LINKS_MAX` caps the links in one block, and that
  is the whole of the defence. **`LINKS_MAX` lives in the page and nowhere
  else**: the daemon carried the same name and the same number and read it
  nowhere, because the page is the only side that makes a link — a copy that
  is not a second opinion is a second thing to forget. Raising it is a number
  somebody has measured, not a guess:
  `test_there_is_still_a_cap_on_the_links_in_one_block` builds 500 links out
  of 5,000 matching words and asserts the time. It is a heuristic; say so rather than implying
  the page is safe from a pattern somebody writes.
- **A remote URL reaches the page without its user and password.** A row's
  hover shows where the repository is fetched from, and a URL can hold
  `me:token@`. `remote_url` takes out what stands before the `@` of a URL,
  and reads the config file rather than asking git: a third git run on every
  poll for a line that almost never changes. `git@host:path` holds no secret
  and stays. `test_the_remote_is_read_and_never_carries_a_password`.
  - **Read the value the way git reads it** (`config_value`). git takes
    `url = "https://me:tok@host/r.git"`, and `git config` writes the quotes
    itself around a value that holds `;` or `#`. `configparser` kept them,
    `urlsplit` then found no scheme, and the token went to the page whole.
    **Then `hide_secrets` runs over the result** as a second guard, for a
    shape the first one does not see: a URL inside the URL is not in its
    netloc. `test_a_quoted_remote_url_carries_no_password`,
    `test_a_password_the_url_parse_missed_is_hidden_all_the_same`.
  - **A key with no `=` is git's "true", not an error.** Without
    `allow_no_value`, one `fsmonitor` line under `[core]` made the whole
    file a parse error, and the remote came back empty.
    `test_a_key_without_a_value_does_not_hide_the_remote`.
- **A one-line summary of a command hides what looks like a credential.**
  The row's last line is a command as the agent ran it, and `curl -s -u
  me:token` stood on a screen that is shared and screenshotted. `tool_target`
  runs `hide_secrets` -- a user and password in a URL, `-u user:pass`,
  credential headers, `Bearer …`, a name that says secret `=` a value,
  `--password x`, and tokens known by their shape -- and it runs it
  **before the cut**: a URL cut before its `@` no longer looks like one with
  a password, and its first half stood on the row. The name is kept, so the
  reader still knows what was there. Every one-line summary goes through it:
  the row, `ls`, a tool call's line in the transcript.
  The permission bar does not: a request is judged on all of it. It catches
  the shapes it knows, and a secret in another shape still shows -- say so
  rather than implying the page is safe from them.
  `test_a_summary_hides_what_looks_like_a_credential`,
  `test_a_secret_reaches_no_row_or_ls_but_the_dialog_stays_whole`.
- **The page never builds HTML from what a program printed.** A `!`
  command's output and a slash command's answer reach it as text, and
  `putShell` puts them in a `pre` as text: a program can print `<img>`.
- **What a `send` may be is counted in bytes, and tmux is what sets the
  number.** Bisected against tmux 3.4: `send-keys -t %0 -l -- <text>` takes
  16,341 bytes and refuses 16,342 with "command too long"; the same run with
  `ä`, two bytes in UTF-8, stops at 8,170, and by session name rather than
  pane id at 16,338 — the target comes out of the same budget. So a cap on
  `len()` lets three times the bytes through in Japanese and tmux refuses the
  lot. `SEND_MAX` is that cap and it is bytes; `test_the_cap_on_a_send_is_in_bytes`
  holds it. A long message is refused, never cut, and never split across two
  sends: a bracketed paste broken in half leaves the rest arriving as
  keystrokes, which is the scar below.
- **A `;` at the end of a send goes as `\;`.** tmux reads an argument that
  ends in `;` as the end of a command, and it does so before `-l` and `--`
  count. Measured on tmux 3.4 with a raw `cat` in the pane: "use foo();"
  arrived as "use foo()", ";" as nothing but the Enter, and "path\;" as
  "path;". `tmux_send` sends the last `;` as `\;`, and tmux turns that back
  into one `;`. It is the one escape `tmux_send` makes, because every other
  escape of ours arrives as characters. A `;` anywhere else is only a `;`,
  and a text with a newline ends in the paste marker, so it needs nothing.
  The reason of a No goes through `tmux_send` too.
  `test_a_semicolon_at_the_end_is_sent_as_tmux_reads_it`, and
  `test_what_arrives_is_what_was_written`, which reads the bytes out of a
  real pane (it skips where there is no tmux). Measure again on a real pane
  before you change this: do not reason it out from tmux's source.
- **A verb tmux refused says so, and says only what it knows.** `send` and
  `jump` both used to answer `{"done": false}` with no `error`, and `said`
  clears the slot for an answer that carries none — so the reader asked for
  something, did not get it, and read nothing at all. Every refusal on this
  path carries a message. **`send`'s message does not claim nothing landed**:
  `tmux_send` runs two commands, the text and then Enter, and a failure on
  the second leaves the text sitting on the agent's prompt. "Nothing went in"
  would send the reader back to type it again, and it would arrive twice.
- **An empty body and a body that was refused is not the same answer.**
  `asked()` never reads a body over `POST_MAX`, so the route sees `{}` — and
  `send` refused it as "there is nothing to send", which is the opposite of
  what happened. `too_big` is set beside it, and cleared at the top of
  `asked()` rather than only set: with keep-alive one handler object serves
  every request on a connection.
- **Interrupt is Escape, and never Ctrl-C.** Claude Code's own
  documentation: Escape stops the current response or tool call mid-turn and
  "Claude keeps the work done so far"; Ctrl-C "interrupts a running
  operation", but "if nothing is running, the first press clears the prompt
  input and a second press exits Claude Code". A turn can end between deciding
  to stop a session and the key landing, so Ctrl-C is a race whose losing
  side is a session that quit. Escape on an idle prompt does
  nothing. `tmux_interrupt` is a key name, the shape of the `Enter` press
  `tmux_send` already makes — not something that could go through `tmux_send`,
  which strips every byte below a space on purpose. Measured: `send-keys C-c`
  puts 0x03 into a raw-mode app as a keystroke it reads, not as a signal.
  `test_interrupt_sends_escape_and_never_ctrl_c` holds it.
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
  shares, and `Daemon.claim`, which sets `Daemon.declining`, for a second tab. A reason half written is
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
    the row shows a dialog (`needs_you` and `Session.permission`, the
    row's own test) and while a No is on its way. The page hides the send
    box in the same state, and the dialog's bar says where it went; the
    review's send is off and says why in its `title`. The daemon's refusal
    is the rule, and the page only saves the reader the round trip.
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
  refused. Grep `canType`. **`#jump` wears `.theme`, which sets `display`**,
  so `.theme[hidden]` puts the browser's rule back: the `.sendbar` scar.
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
- **A newline sent to a terminal is Enter.** Text with one is wrapped in the
  bracketed paste markers. Without them a real shell ran the first line.
- **A path out of the event log is input, not fact.** `transcript_path` goes
  through `safe_transcript`. `cwd` is used for git and for labels, never to open
  a file the page asked for.
- **A path out of the page is input too.** `worktree_target` opens a file only
  when `is_listed` says git offers that exact name and `inside` says the resolved
  path is still in the worktree. Keep all three parts of the first check — the
  `:(literal)` prefix, the `--`, and comparing the answer to what was asked for.
  Ignored files are asked the same way. Never swap either check for a pattern
  that tries to spot a bad path. **Both readers go through it**, so a new one
  cannot be given one check and not the other.
  - **And nothing inside a `.git` is read, though it is in the worktree.**
    git lists a tracked link, `notes.md -> ../.git/config`, and never what
    it points at, so both checks passed and the Files tab showed the
    config, with a remote's token in it. `worktree_target` refuses a real
    path with any part named `.git`, in any case: a filesystem that ignores
    case opens `.GIT/config` as `.git/config`. A git directory outside the
    worktree is `inside`'s to refuse.
    `test_a_link_into_the_git_directory_is_refused`.
- **`serve` leaves an example `links.json` and never writes over one.**
  JSON has no comments, so the example is a working entry — and a
  deliberately inert one, because nobody's work has a ticket called
  `EXAMPLE-1`. A commented-out entry is not valid JSON and a broken one
  would be a line in `doctor` saying the file is wrong. It is written with
  `write_atomic(private=True)`, like everything else there, and a failure to
  write it never stops `serve`.
- **A `links.json` that cannot be used is never silent.** "No links" and
  "your file is broken" looked identical — nothing on the page either way —
  and the only way to find out was `doctor`, which you had no reason to run.
  The first thing anybody writes is `\d`, which is not a JSON escape, so the
  file never parses. `load_links` returns the usable entries *and* what is
  wrong with the rest; `read_links` is the wrapper for a caller with nowhere
  to put the trouble. `serve` prints it, `/api/links` carries it, the page
  says it in the live slot, `doctor` says it. **The file is never repaired**: guessing at
  a backslash somebody meant is a worse surprise than the message. And the
  page adds its own trouble — a pattern Python compiled and this browser
  will not is only findable there, and `loadLinks` says both together.
  **On the slot it is `state.linkTrouble`, not `state.trouble`**: `said`
  clears the second on any answer that worked, so the first Enter took the
  message away for good, and the daemon's sentence about bad JSON is 150
  characters on a line that does not wrap. `paintLive` shows a few words,
  last of the four, with the whole of it in `title`.
- **The list of what may be shown lives in the daemon, once.** `SHOWN_AS` is
  read by `shown_as`, which the `raw` route enforces and which
  `read_worktree_file` reports as `FileText.shown` — so the page holds no
  copy of it and `putMedia` reads the answer. A second list in a second
  language drifts, and a mismatch is silent either way round: a picture that
  never arrives, or a file that is never offered. A name on that list is
  reported `binary` without being read at all, because its text is not text
  and the two-second poll would otherwise read half a megabyte off it for
  nothing.
- **`raw` is the one answer a browser may keep.** Every other reply carries
  `no-store`. Its address holds the file's mtime, so a written file is a
  different address; without the cache header the browser fetched the whole
  thing again on every tab switch, which is exactly what the mtime in the
  address was there to avoid.
- **The `raw` route may never serve a document.** It hands a worktree file to
  the browser as its own bytes, and the type comes from the end of the name,
  out of `SHOWN_AS` — pictures, video, sound, and nothing else. An SVG or an
  HTML file served from here would be a page an agent wrote, on the origin
  that holds the token, with a script in it able to read both. `nosniff` is on
  every answer for the same reason: a browser that guessed the type from the
  bytes would undo the list. Never add a type to `SHOWN_AS` that a browser
  will execute or navigate to.
- **The state directory is private.** `0700` dirs, `0600` files — and `0600`
  **at creation**, through `open_private`. A `chmod` after the first write
  leaves a window in which the file already holds a prompt and anyone on the
  machine can read it, and that window does not close if the process dies in
  it. The log holds every prompt and every command an agent ran.
- **The hooks and the status line run the installed copy, not the checkout,
  and `serve` says when the two differ.** `install` copies this file to
  `install_path()`. A reader who pulled and restarted `serve` had a page
  that could show the session's spend, beside a status line — run by the
  copy from the day before — that never wrote it down. The page showed no
  cost and nothing said why; the reader's own status line printed the
  number, so the payload plainly carried it. `install_behind` compares the
  bytes; `serve` prints it on the way up and `doctor` counts it as a
  problem. `test_doctor_and_serve_say_when_the_installed_copy_is_another_version`.
- **`settings.json` is the user's file, not ours.** `install` touches our hooks
  and nothing else: its permissions are kept (a fresh temporary takes the
  umask, so 0600 came back 0644, on a file that can hold API keys), and the
  write is fsynced, file and directory — Claude Code will not start without
  it. `uninstall` leaves a group it took nothing out of exactly as it was,
  including an empty one the user put there. **A link is written through,
  not over**: dotfile managers keep this file as a link into a repository,
  and the rename replaced the link with a plain file, so the repository
  never had the hooks and its later edits never reached Claude Code.
  `save_settings` resolves the path first, so the temporary and the rename
  are beside the real file. **And the temporary is 0600 from the moment it
  exists**: `write_atomic` wrote it at the umask and narrowed it after, so
  a 0644 copy of a file holding API keys stood in `~/.claude`, which is not
  private -- for good, if `install` died in between. The rule
  `open_private` keeps for an append; a stale temporary of the same name is
  unlinked first, because `O_TRUNC` would keep its mode.
  `test_a_settings_file_that_is_a_link_stays_a_link`,
  `test_the_settings_are_never_on_disk_where_others_can_read_them`,
  `test_a_temporary_left_by_a_writer_that_died_is_not_trusted`.
- **Anything printed to a terminal is scrubbed, like anything sent to one.**
  `ls`'s last column is a `Notification` message or a tool summary — text an
  agent wrote. `table` takes the control characters out, in the one place a
  row becomes a line; one of them set the terminal's title and reddened the
  rest of the output, and `len` counting the escape bytes made the columns
  wrong as well.
- **A `flock` is on an inode, not on a name.** Between opening the log and
  getting its lock, another hook can rotate it away — and then the lock is on
  the archive. A hook that did not notice renamed the fresh log on top of the
  archive: every event ever recorded, gone. `still_the_file` is that check, and
  `append_event` opens again when it fails.
- **An event must survive what is in it.** A lone surrogate — legal in a JS
  string, so reachable in a tool response — makes a strict UTF-8 encoder
  refuse the whole line. Surrogates are replaced; a `SessionStart` lost that
  way costs the session its cwd, pane and pid for good.
  **And a transcript carries them too**, where no hook replaces them:
  `json.loads` turns the escape Claude Code wrote into a real one, and a
  strict encode refused the whole answer -- the transcript answered 500 on
  every request, and a push wrote an HTTP 500 into the middle of the stream.
  Everything that leaves the daemon encodes with `"replace"`: `reply_json`
  and `stream`. `test_a_lone_surrogate_in_a_transcript_breaks_nothing`.
  Never write the escape for one in source, not even in a comment: in a normal
  string it is the character, and Python 3.13 will not put a module holding one
  in a bytecode cache. CI was green on four versions and red on the fifth, over
  a docstring. Build one with `chr(0xD800)`;
  `test_no_source_file_holds_a_lone_surrogate` catches the next one.
