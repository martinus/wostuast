# Safety — the page can type into a terminal

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. The hook's answer, who may ask the daemon, what the page may trust, and what a path may reach. Two more files hold the rest of safety: `safety-typing.md` and `safety-install.md`.

- **The hook prints one thing only: an allow for the dialog it was called
  for, after the reader's Yes on the page.** Claude Code reads a hook's
  stdout as its answer, and we register `PermissionRequest`. One stray
  `print()` in `cmd_hook` answers every permission dialog for the user.
  Logging goes to the log file. Tests assert the silence by event name;
  never weaken them (`test_the_hook_says_nothing_to_a_permission_request`).
  **The Yes is bound to its dialog by the hook, never by keys** (`approve`,
  `wait_for_yes`): keys land on whichever dialog is up when they arrive,
  so a Yes typed for `git status` could approve an `rm -rf` that came up
  meanwhile. The hook writes a nonce of its own into its line of the log
  (`ask_id`, `ASK_SHAPE`), and waits holding a lock on
  `approvals/<ask>.wait`, taken under a name of its own and renamed, so
  the daemon never sees it unlocked. The daemon writes `<ask>.yes` holding
  the nonce, only for the dialog on the row (`key`), only while the hook
  holds its lock (`hook_waits`; a `.wait` that is not there yet is not
  one left behind, or the hook's rename between the look and the unlink
  lost it, `test_a_file_that_appears_while_the_daemon_looks_is_never_taken`),
  never while a No is on its way
  (`holding(no=True)`), and takes it back if the hook did not take it in
  `APPROVE_SEEN`. Measured on 2.1.292 (`tests/fixtures/README.md`): the
  allow closes the terminal's dialog and the call runs; an Escape in the
  terminal first stops the hook, whose lock goes with it.
  **It waits only while a daemon runs** (`daemon_running`), for at most
  `APPROVE_WAIT`, and **never for a question or a plan** (`NOT_APPROVED`):
  each costs a process held for nothing.
  **"Yes, and don't ask again" carries Claude Code's own suggestion, chosen
  by its place, never a rule the page or the daemon wrote** (`always_offered`,
  `allow_for`, `always_label`). The reader asked for the CLI's choices. The
  page sends `always: n`; the daemon checks `n` is one this dialog offered
  and writes `<ask>:<n>`; the hook takes suggestion `n` from its own
  `permission_suggestions` and answers allow with it as
  `updatedPermissions`. Only suggestions that allow -- `addRules` with
  `behavior: allow`, `addDirectories`, `setMode` to `ALWAYS_MODES` -- are
  offered; a choice the dialog was not offered gets no answer at all, not
  a plain Yes. Measured on 2.1.292: the allow with `Bash(npm test *)`
  wrote the same line to the project's `.claude/settings.local.json` as
  the CLI's option 2, and the next `npm test` was not asked. The CLI shows
  one option for several suggestions (`rm -rf build`: a folder and a
  mode) and applies only some of them, by a rule too long to copy; here
  each is a choice of its own.
  **A Yes's own record clears the amber** (`Approved`, `_on_approved`): no
  hook fires for a Yes. `tests/test_approve.py`,
  `test_yes_shows_while_the_hook_waits_and_goes_to_it`,
  `test_yes_and_dont_ask_again_is_a_choice_of_its_own`.
  - **Yes is green and No is red** (`.permyes`, `.permno`): they looked
    alike, and the reader asked for them told apart at a glance.
  - **A click picks, and submit answers** (`state.permPick`,
    `permissionPick`, `submitPermission`), as on a question. A click
    that went straight to the hook was a Yes nobody could take back -- a
    slip of the hand, or a page on a phone in a pocket -- and the reader
    asked for every prompt to work one way. The pick is kept by the
    dialog's key across a rebuild, as the reason is, and a Yes picked
    while the hook waited is no pick once it stops. The reason box shows
    only while No is picked, inside one edge with No (`.permnogroup`): it
    stood under the list, apart from the No it belongs to. **A No waits
    for its reason** (`wordless`), as the reader asked; not where no
    reason can be typed, or that No could never be given. Submit stands
    at the right of the foot, after what it does, on the question bar
    too. `test_yes_shows_while_the_hook_waits_and_goes_to_it`,
    `test_a_reason_half_written_survives_a_look_at_another_tab`.
- **The hook must never block Claude Code.** try/except around everything,
  `give_up_after` deadline, always exit 0. Keep all three. The deadline covers
  every wait at once, including a stdin that never closes — **and it stays
  armed over the logging on the way out.** `log` opens and writes a file, and
  the failure being logged may be that the filesystem is not answering.
  **Armed again, not merely left**: an alarm fires once, so when the failure
  *is* the timeout nothing was armed at all, and the status line cancelled
  its alarm before it logged. Both arm `LOG_TIMEOUT` over the logging.
  `test_a_failure_is_logged_under_a_deadline_even_after_a_timeout`.
  **And an outer `try` catches that alarm too** (#235): it can fire after
  `log` returns and before `stand_down` cancels it, and there it was
  outside every `try` -- a traceback on stderr, and exit 1 from a hook.
  `stand_down` is in a `finally`, and an alarm fires once, so nothing is
  armed when the outer `except` runs.
  `test_an_alarm_after_the_log_returns_escapes_nothing`.
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
- **The daemon answers on localhost only, and only to its own user and
  root.** Binding to 127.0.0.1 is not enough — a site can point its own
  name at 127.0.0.1. `Serving.ours()` checks Host, and a request without
  one is refused: an empty Host used to pass, which made the check
  skippable by leaving the header out.
  - **127.0.0.1 is open to every account on the machine.** `GET /` gave the
    page, token and all, to anybody who asked. A review of the whole file
    showed it: as `nobody`, it read every transcript and sent `!id` into
    the owner's agent (issue #227). The Host, Origin and token checks keep
    out other *sites*; only the uid keeps out other *users*. On Linux,
    `Serving.handle` reads the owner of the other end of the connection out
    of `/proc/net/tcp`, once per connection, and `guarded` answers every
    request from another uid with 403 and `STRANGER`, before it reads a
    byte of a body: the page, the stream, every route. `socket_owner`
    matches both ends, so another connection from the same port is never
    taken for this one. It reads `/proc/net/tcp6` too, because a client on
    an IPv6 socket reaches 127.0.0.1 as `::ffff:127.0.0.1`.
  - **A line with no inode is nobody's** (`NO_INODE`, #254). No process
    holds that socket, and the kernel lists it as uid 0, which is root's,
    and root is let in. The first rule skipped only `TIME_WAIT`, and
    another user got past it: connect, send a request, close. Measured as
    `nobody` on 6.18: open, the line is `01 uid 65534`; closed, `05 uid 0
    inode 0`. With the daemon under load the table is read after the
    close, and the request was served. **Not "state `01` only"**: a
    client that shuts down only its write half is `05` too, with its own
    uid and inode, and it can still read the answer, so that rule refuses
    the owner for nothing. A socket with no inode cannot read an answer,
    so refusing it costs the owner nothing. `TIME_WAIT` lines have no
    inode either, so one test covers both.
  - **`another_user` refuses whatever it cannot prove, except a machine
    with no table.** No table at all is macOS, and stays as it was: the
    guide says so. An empty table is not a real one either, because a real one
    lists our own listening socket, and nobody else can empty it.
    Everything else that is not our uid or root's is a no. A line that is
    not there: the other end is open as long as the connection is, so that
    is not normal -- but the kernel writes the table a page at a time and
    resumes by position, so a table that changes during the read can skip
    a line, and it is read `PEER_READS` times first. Measured: no miss in
    300 reads with four threads opening and closing connections. A table
    that is there and cannot be read: running out of files is something
    another user can cause, so `read_table` gives None only for a file that
    is not there, and `handle` refuses on any exception.
  - **In the connection's thread, never in the accept loop.** The kernel
    writes the whole table on every read: 6 ms at 4,400 lines, 10 ms at
    6,400, 92 ms at 69,000 (most of them `TIME_WAIT`), and the search
    after it is a tenth of that. In `verify_request` every browser would
    wait for it. A keep-alive connection pays it once.
  - **Root is let in too (`ROOT_UID`).** In WSL2's default NAT mode, a
    Windows browser reaches 127.0.0.1 in the Linux VM through a relay that
    runs as root inside the VM, so a check for our own uid alone refused the
    owner there; other forwarders that run as root do the same. Root gains
    nothing: it can read the token, the state files and every transcript
    already, and it can attach to the daemon itself. The live test sets
    `ROOT_UID` to -1, because the suite may run as root.
    `test_root_is_let_in_too`. **WSL2's mirrored mode is not proven**: a
    Windows browser's socket may not be in Linux's table at all, and then
    the owner is refused every time. There was no WSL to measure on, and
    the guide says so. Do not let a missing line in to fix it: that is the
    hole the rules above close.
  - **An ssh tunnel is the owner.** sshd opens the forwarded connection from
    the session process, which runs as the user who logged in, and a socket
    belongs to the user that made it. Reasoned from OpenSSH's privilege
    separation, not measured: the machine that wrote this had no sshd. A
    browser run as another account is refused, and the 403 says why.
  `test_a_socket_is_found_by_both_of_its_ends`,
  `test_a_client_on_an_ipv6_socket_is_found_in_tcp6`,
  `test_only_the_daemons_own_user_is_let_in`,
  `test_a_line_the_kernel_skipped_once_is_looked_for_again`,
  `test_a_connection_from_another_user_gets_nothing`,
  `test_a_table_that_cannot_be_read_refuses`,
  `test_a_socket_no_process_holds_is_nobodys`, and two that need root and
  `setpriv` and skip without them, because CI runs as a normal user:
  `test_a_real_request_from_another_user_is_refused`, and
  `test_a_request_from_another_user_that_closed_first_is_refused`, which
  makes the table read late so that it comes after the close every time.
- **A check must fail closed, and nothing may run outside the guard.** Both
  checks used to sit in front of the `try`, where `Origin: http://[::1` or one
  byte above 0x7f in the token header killed the thread — no status line, a
  traceback into the terminal running `wostuast`, from a request nobody had
  authenticated. They refuse a header they cannot read; `guarded()` catches
  the rest, and it wraps the whole of a request.
- **A POST that may not act is refused before its body is read**
  (`Serving.route`: `ours`, then `allowed`, then `asked`). `POST_MAX` is
  megabytes since a send may be a long log, and any site in the reader's
  browser can POST to us: read first, it made the daemon read and parse
  that much for a request it then refused. The body stays in the socket, so
  the connection closes.
  `test_a_post_that_may_not_act_is_refused_before_its_body_is_read`.
- **A body that is not read stays in the socket.** `asked()` refuses one over
  `POST_MAX`, and with keep-alive the rest of it was parsed as the next
  request: the daemon answered a `GET` written inside a refused POST's body,
  three answers on one connection. Refusing to read the body closes the
  connection. The handler has a socket timeout for the other half of it — a
  `Content-Length` announced and never sent held a thread for ever.
  **The same for every body whose end is not known** (#235): a chunked POST
  was read as length 0, and a GET's body is never read, and with keep-alive
  the request written inside either was answered as the next one.
  `body_length` gives None for a `Transfer-Encoding`, a `Content-Length`
  that is not plain digits (`int()` takes " -5" and "5_0"), and two that
  disagree; `asked()` then closes the connection, and so does `Serving.route` for a GET
  with any body at all. A test counts status lines no more: a chunk's size
  line, read as a request, is answered as HTTP/0.9, which has none, so
  `only_one_answer` checks that nothing follows the first answer's body.
  `test_a_body_that_is_not_read_does_not_frame_the_next_request`.
  **Nor a length of more than 18 digits** (#254). `isdigit()` took 5,000
  digits, `int()` refused them (Python reads no number of more than 4,300
  digits), and `guarded` answered 500 and kept the connection: the bytes
  after the headers were answered as the next request. So `body_length`
  refuses the length before `int()` sees it, and **`guarded` closes the
  connection on every 500** as well, because a request that fails half
  way may leave its body in the socket.
  `test_a_length_too_long_to_be_a_number_is_not_read`,
  `test_a_request_that_fails_closes_its_connection`.
- **The page never trusts what an agent wrote.** Markdown goes into an inert
  `<template>`, is scrubbed to an allowlist, and only then inserted. Values from
  events use `textContent`. Assigning `innerHTML` first fires `onerror` before
  any scrub runs — that was real.
  - **The scrub keeps three attributes, and each passes a test on its
    value** (`KEPT`, a `Map` of `Map`s). `href` on `A`, which `safeLinks`
    then decides on; `start` on `OL`, one to nine digits, written again
    from the number; `align` on `TH` and `TD`, only `left`, `center` or
    `right`. No new tag, no new URL scheme, and no attribute that holds
    free text. The scrub took every attribute before, and that took the
    meaning with it: steps split by a code fence are three lists, and read
    1, 1, 1; a column of numbers stood to the left. **A `Map`, not an
    object**: an attribute named `constructor` found the function every
    object has, passed its "test", and stayed. **`.prose th, .prose td`
    sets `text-align: left`**, and a rule in a style sheet wins over
    `align`, so `.prose [align=…]` puts it back.
  - **A task box and a picture become text, not nothing** (`textFor`). An
    element the scrub refuses becomes its own text, and `INPUT` and `IMG`
    have none: done and not done read the same, and "see ![the
    diagram](x.png)" read "see  here". A checkbox is ☑ or ☐, a picture is
    its `alt`. Both are text nodes, so neither loads or runs anything.
    **The box stands where the bullet stood**, as on GitHub: "• ☑ done"
    was two marks for one item. The scrub gives the item the class `task`
    (`.prose li.task` hides the bullet), and gives it after the item's own
    attributes were taken, so an agent's `class="task"` on an item with no
    box does not stay. The class is ours and says nothing an agent wrote.
  - **A `#` link is its words** (`safeLinks`). The scrub takes the ids off
    headings, so the link has nowhere to go in the text. As a link it
    opened a second copy of this page in a new tab, and `goToLink` read
    `#install` as a session. Only `http(s)` is a link now (`LINKABLE`);
    anything else keeps its `a` with no `href`, as before.
  - **A skill's frontmatter is an agent's text too**: a `SKILL.md` in a
    worktree is a file any agent there can write. `read_command` reads
    `FRONT_MAX` bytes and keeps three keys; a name must be
    `COMMAND_SHAPE`, because a taken name goes into the send box and from
    there into a terminal; the page sets every part with `put`.
    `test_a_name_that_is_not_a_command_is_left_out`.
  - **And its whole text is read by name, never by path** (#367,
    `verb_command`, `command_text`). `~/.claude` is outside every
    worktree, so the Files tab's route may not read it, and a path from
    the page is input. The page names a command from the list it was
    sent; only a file that list holds is read (`Commands.defined`, the
    files alone, no transcripts). **And the file must be a real `.md`,
    asked where the list is made** (`real_md` in `read_command`): an
    agent can write a link named `leak.md` into its worktree's
    `.claude/commands/` that points at a key, or a FIFO named `SKILL.md`
    that held the request thread for ever. Asked only when the text was
    read, the send box listed `/leak` and the tab called it unreadable.
    Asked again in `command_text`, as the link can be swapped in between.
    Not "inside `.claude`": your own commands folder may be a link into
    a dotfiles repository. At most `COMMAND_TEXT_MAX`, and drawn through
    the scrub, as every agent's text is.
    `test_a_command_that_links_to_a_secret_is_not_read`,
    `test_a_fifo_named_like_a_skill_is_not_listed`,
    `test_a_folder_of_commands_linked_from_elsewhere_is_read`.
  `test_markdown_keeps_task_boxes_step_numbers_sides_and_picture_words`,
  `test_the_scrub_keeps_only_values_it_has_checked`, which feeds the scrub
  a hostile `start`, `align`, `img onerror` and `javascript:` by hand,
  because marked escapes raw HTML before the scrub sees it.
- **An autolink runs after the scrub, over text nodes, and checks its own
  href.** `linkTickets` builds one anchor at a time and never parses
  anything, so a `url` template can put text on the page and nothing else.
  `ticketUrl` tests for `http(s)` a second time, although `link_trouble`
  already refused anything else: the two sides are far apart and only one of
  them is the one that inserts. The links are in the reader's own
  `settings.json`, in their configuration directory — never a per-worktree
  file, which an agent could write.
  **A pattern that can match nothing still makes its links** (`nextMatch`).
  `(PROJ-)?\d*` matches nothing at every place that is not a ticket, and
  `exec` gives that empty match first. `linkOne` took it for no match, so
  the pattern made no links, and neither the page nor `doctor` said why.
  An empty match now moves the search on by one. Refusing such a pattern
  instead was the other choice, and it is worse: whether a pattern *can*
  match nothing cannot be asked of it simply, and this one works as
  written once the empty matches are stepped over. `linkOne` keeps each
  pattern's next match until it is passed, so the step costs one walk of
  the text, not one a link.
  `test_a_pattern_that_can_match_nothing_still_makes_its_links`.
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
  - **Read the file by git's own rules, never with `configparser`**
    (`config_entries`, `config_section`, `config_value`, after git's
    `config.c`). `configparser` is a different syntax, and each difference
    was a bug. It kept the quotes of `url = "https://me:tok@host/r.git"`
    (`git config` writes them itself around a value that holds `;` or `#`),
    so `urlsplit` found no scheme and the token went to the page whole. It
    refused a key with no `=`, which is git's "true", and the remote came
    back empty; `allow_no_value` fixed that and made it worse (#252): a
    key with no `=`, then a line indented further, is a continuation of a
    value that is None to it, and it raised AttributeError before Python
    3.13, out of `git_facts` and out of every tick (`worktree-tabs.md`,
    "A git call that failed"). And it kept the `\` that continues a value
    onto the next line, so `https://me:pw\` + `@host/r.git` lost its `@`,
    and neither guard found the password.
    - **What the reader does**: `[section]`, `[section "sub"]` and the old
      `[section.sub]`; the section and the key in any case, the quoted
      subsection as written; `key = value`, a key with no `=` (value
      None), a key on the header's line; `#` and `;` comments outside
      quotes; double quotes; the escapes `\"`, `\\`, `\n`, `\t`, `\b`;
      a `\` at the end of a line that joins the next one. A file git
      refuses -- an unknown escape, a quote still open at the end of the
      line, a header that ends on its line -- gives None, and the remote
      "". **It never raises**: bytes that are not UTF-8 are replaced, and
      a file over `CONFIG_MAX` is not read, because it is read on the tick
      thread (measured: a megabyte of bare keys, the worst shape, 0.5 s of
      CPU; a megabyte-long URL 0.01 s).
    - **What it leaves out**: `[include]` and `includeIf` are not
      followed, and `insteadOf` is not applied: a hover that shows the
      file's own line is still true. Whitespace other than a space inside
      a value is kept, where git 2.43 turns each into a space; a NUL ends
      git's value and not this one. None of them moves a URL's `@`.
    - **The first `url` of a remote is the one shown**: git fetches from
      it (`git remote get-url`). `configparser` kept the last. `origin`,
      or else the first remote with a URL.
    - **Only `<git_dir>/config` is read.** `remote_url` tried
      `<dir>/config`, then `<dir>/.git/config`, and when only
      `--show-toplevel` answered `git_facts` gave it the top of the
      worktree, so a file of the project named `config` was read as the
      repository's. `git_facts` now gives it `<top>/.git` then.
    **Then `hide_secrets` runs over the result** as a second guard, for a
    shape the first one does not see: a URL inside the URL is not in its
    netloc. `test_the_config_is_read_as_git_reads_it` compares every entry
    with `git config --list` on hand-made files and 400 seeded random
    ones; `test_a_quoted_remote_url_carries_no_password`,
    `test_a_password_the_url_parse_missed_is_hidden_all_the_same`,
    `test_a_key_without_a_value_does_not_hide_the_remote`,
    `test_a_bare_key_then_an_indented_line_stops_nothing`,
    `test_a_url_continued_on_the_next_line_carries_no_password`,
    `test_the_first_url_of_a_remote_is_the_one_shown`,
    `test_a_config_git_refuses_or_too_big_gives_no_remote`,
    `test_the_top_of_the_worktree_is_not_read_as_its_config`.
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
  - **A long command costs the summary no time.** `SECRET_SHAPES` had
    `[\w.-]*token[\w.-]*=`, and two stars round a part that can fail try
    every split of a word: 1,600 characters of `a.token.` took 1 s, 20 KB
    of `abcdefghi.` 3.3 s, and 8,000 characters two minutes. It ran on the
    one thread that folds every event, and again on every start, because
    the log is never thrown away. Those two stars are `{0,64}` now, and a
    URL's scheme `{0,31}` (1.3 s over 20 KB of `a.` before), and
    `clip_hidden` gives the patterns only the start of the text: what
    `clip` keeps and `SECRET_REACH` characters past it, because a URL's
    `@` or a name's `=` can stand after the cut with the secret before it
    on the row. A text shorter than that is hidden whole, as before.
    **Still hidden before the cut, never after**: that is the scar above.
    A name with more than 64 characters before its keyword is no longer
    seen. `remote_url` goes through `clip_hidden` too, at `REMOTE_SHOWN`:
    it is read on the tick thread, and an agent can write any line into a
    config. `test_a_long_word_costs_a_summary_no_time` and
    `test_a_remote_of_a_megabyte_costs_the_tick_no_time` count CPU time,
    not the clock, so a loaded machine does not fail them;
    `test_a_secret_is_hidden_as_far_as_the_row_can_show`.
    - **So a quoted value may end at the end of the text** (#254). The
      cut can fall inside the quotes of `API_TOKEN="…"`, and the `TOKEN=`
      shape wanted the closing quote: nothing matched, and the row showed
      the secret's start. Its quoted values are `"[^"]*(?:"|\Z)` and
      `'[^']*(?:'|\Z)` now, so a quote that is not closed is hidden to
      the end, cut or not. No other shape in `SECRET_SHAPES` wants a
      closing quote. `test_a_quoted_secret_cut_by_the_clip_is_hidden_to_the_end`.
    - **Bounded was not cheap enough: a shape with a needed character is
      skipped without it.** The `TOKEN=` shape tries a keyword at each of
      64 places after every word boundary, and 20 KB of `a.` still cost
      0.21 s of CPU on a CI runner, over the test's 0.2 s. It cannot match
      without `=`, so its entry names `"="` and `hide_secrets` skips it
      when the text has none: `in` runs in C. The test's inputs for that
      shape start with `= `, or the skip would hide its stars from the
      test.
- **The page never builds HTML from what a program printed.** A `!`
  command's output and a slash command's answer reach it as text, and
  `putShell` puts them in a `pre` as text: a program can print `<img>`.
- **A path out of the event log is input, not fact.** `transcript_path` goes
  through `safe_transcript`. `cwd` is used for git and for labels, never to open
  a file the page asked for.
  - **A line handed to the reader to run is quoted, every part, and
    typed nowhere** (#352, `resume_command`, `drawResume`). A session that
    is over shows `cd <home> && claude --resume <id>` where the send box
    stood, to copy. The folder and the id came out of an event, and the
    reader runs the line: each part goes through `shlex.quote`, an id that
    is not `[\w-]+` gives no line, and so does a folder with a control
    character -- `CONTROL_CHARS` keeps a tab and a newline, being for text
    typed into a terminal, so those are refused by name. Starting the
    agent is a non-goal; the page only copies. `claude --resume` finds a
    session only from the folder it started in (measured, 2.1.288), so the
    `cd` is to `home`, never `cwd`; a transcript under another config folder
    than `~/.claude` puts `CLAUDE_CONFIG_DIR=` in front.
    `test_every_part_is_quoted_and_a_control_character_gives_no_line`,
    `test_a_session_that_is_over_offers_the_line_that_brings_it_back`.
- **A path out of the page is input too.** `worktree_target` opens a file only
  when `is_listed` says git offers that exact name and `inside` says the resolved
  path is still in the worktree. Keep all three parts of the first check — the
  `:(literal)` prefix, the `--`, and comparing the answer to what was asked for.
  Ignored files are asked the same way. Never swap either check for a pattern
  that tries to spot a bad path. **Both readers go through it**, so a new one
  cannot be given one check and not the other. **A link loop is not inside
  anything, and not an error**: `Path.resolve` raises RuntimeError on one
  up to Python 3.12, and `inside` caught only OSError, so a tracked
  `a -> b`, `b -> a` answered 500. It catches both. **On 3.13 `resolve`
  raises nothing**: it hands back the path as far as it got, which is still
  a link and is inside the root, so the catch alone passed on 3.12 and was
  red on CI's 3.13 job. A path resolved to its end is never a link, so
  `inside` also asks `is_symlink()` of what `resolve` gave.
  `test_a_link_loop_is_not_inside_and_is_not_an_error`.
  - **And nothing inside a `.git` is read, though it is in the worktree.**
    git lists a tracked link, `notes.md -> ../.git/config`, and never what
    it points at, so both checks passed and the Files tab showed the
    config, with a remote's token in it. `worktree_target` refuses a real
    path with any part named `.git`, in any case: a filesystem that ignores
    case opens `.GIT/config` as `.git/config`. A git directory outside the
    worktree is `inside`'s to refuse.
    `test_a_link_into_the_git_directory_is_refused`.
  - **A refused read says why, and the refusal stands** (`why_unread`,
    #515). A venv's `bin/𝜋thon` and `bin/python` are links to the
    system's Python: listed, and refused by `inside` as they must be. The
    route said "that file is not in this worktree" of a file the reader
    could see in the list. `why_unread` is asked only after the refusal,
    opens nothing, and says where the link goes -- the link's own text,
    which git stores as its content, or the end of it outside the tree. A
    link into `.git` says only that. A name git does not offer still gets
    the old words, so the reason gives away nothing the name did not.
    `test_a_link_out_of_the_worktree_says_where_it_goes`,
    `test_a_link_out_of_the_worktree_is_refused_with_where_it_goes`.
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
  **Every command makes that directory through `private_dir`**, and `doctor`
  and the start ask `state_dir_trouble` whether they can write it. `doctor`
  had its own probe with a bare `mkdir`, so on a new machine the directory
  stood at the umask, 0755, until a hook ran (#285).
  `test_doctor_makes_the_state_directory_private`.
- **A `flock` is on an inode, not on a name.** Between opening the log and
  getting its lock, another hook can rotate it away — and then the lock is on
  the archive. A hook that did not notice renamed the fresh log on top of the
  archive: every event ever recorded, gone. `still_the_file` is that check, and
  `append_event` opens again when it fails. **And it belongs to the open
  file, not to the process**: a second `open` of the log in the hook that
  holds its lock waits for ever. So `append_event` opens the fresh log only
  when `archive_log` says it moved the old one, and otherwise writes into
  the file it holds (#253).
  `test_a_rotation_with_no_listing_writes_the_event_where_it_is`.
- **An event must survive what is in it.** A lone surrogate — legal in a JS
  string, so reachable in a tool response — makes a strict UTF-8 encoder
  refuse the whole line. Surrogates are replaced; a `SessionStart` lost that
  way costs the session its cwd, pane and pid for good.
  **And a transcript carries them too**, where no hook replaces them:
  `json.loads` turns the escape Claude Code wrote into a real one, and a
  strict encode refused the whole answer -- the transcript answered 500 on
  every request, and a push wrote an HTTP 500 into the middle of the stream.
  Everything that leaves the daemon is written by `wire_json` and goes out
  through `wire_bytes`, which encodes with `"replace"`: `reply_json`,
  `Hub.send`, `answer_tag` and both writes of `stream`. They were three
  spellings, and the stream's opening was the one left strict (#289).
  `page_json` is the other road out, ASCII, because it stands inside the
  page. `test_a_lone_surrogate_in_a_transcript_breaks_nothing`,
  `test_a_lone_surrogate_in_the_sessions_breaks_no_stream`.
  **And no number JSON cannot hold**: `float` takes "nan" and "inf", and
  `json.loads` makes them out of `NaN` and `1e999`. `json.dumps` then
  wrote `NaN` into a sessions push, and the page's `JSON.parse` threw on
  every one (#235). `to_float` gives nought for a number that is not
  finite. `test_a_number_that_is_not_finite_never_reaches_the_page`.
  Never write the escape for one in source, not even in a comment: in a normal
  string it is the character, and Python 3.13 will not put a module holding one
  in a bytecode cache. CI was green on four versions and red on the fifth, over
  a docstring. Build one with `chr(0xD800)`;
  `test_no_source_file_holds_a_lone_surrogate` catches the next one.
