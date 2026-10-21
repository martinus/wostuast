# Safety — the page can type into a terminal

The hook's answer, who may ask the daemon, what the page may trust, what a
path may reach. The rest: topics/safety-typing, topics/safety-install.

- **The hook prints one thing only: an allow for its own dialog, after the
  reader's Yes on the page.** Claude Code reads hook stdout as the answer
  to `PermissionRequest`: one stray `print()` in `cmd_hook` answers every
  dialog. Log to the log file. Never weaken the silence tests
  (`test_the_hook_says_nothing_to_a_permission_request`).
  **The hook binds the Yes to its dialog, never keys** (`approve`,
  `wait_for_yes`): keys land on whatever dialog is up, so a Yes for
  `git status` could approve a later `rm -rf`. The hook logs a nonce
  (`ask_id`, `ASK_SHAPE`) and waits holding a lock on
  `approvals/<ask>.wait`, made under its own name and renamed, so never
  seen unlocked. The daemon writes `<ask>.yes` only for the row's dialog
  (`key`), only while the hook holds its lock (`hook_waits`; a `.wait` not
  there yet may be mid-rename:
  `test_a_file_that_appears_while_the_daemon_looks_is_never_taken`), never
  while a No is on its way (`holding(no=True)`), and takes it back if
  unread after `APPROVE_SEEN`. The allow closes the terminal's dialog; an
  Escape there stops the hook (2.1.292, `tests/fixtures/README.md`).
  **It waits only while a daemon runs** (`daemon_running`), at most
  `APPROVE_WAIT`, **never for a question or a plan** (`NOT_APPROVED`):
  each would hold a process for nothing.
  **"Yes, and don't ask again" sends Claude Code's own suggestion, picked
  by its place, never a rule of ours** (`always_offered`, `allow_for`,
  `always_label`): the reader asked for the CLI's choices. The page sends
  `always: n`; the daemon checks the dialog offered `n` and writes
  `<ask>:<n>`; the hook allows with its own `permission_suggestions` entry
  `n` as `updatedPermissions`. Only allowing ones are offered (`addRules`
  with `behavior: allow`, `addDirectories`, `setMode` to `ALWAYS_MODES`),
  each its own choice; one not offered gets no answer, not a plain Yes.
  **A Yes's own record clears the amber** (`Approved`, `_on_approved`): no
  hook fires for a Yes. `tests/test_approve.py`,
  `test_yes_shows_while_the_hook_waits_and_goes_to_it`,
  `test_yes_and_dont_ask_again_is_a_choice_of_its_own`.
  - **Yes is green, No is red** (`.permyes`, `.permno`): the reader asked.
  - **A click picks, submit answers** (`state.permPick`, `permissionPick`,
    `submitPermission`), as on a question: a click straight to the hook
    was a Yes nobody could take back. The pick is kept by the dialog's key
    across a rebuild, and dies when the hook stops. The reason box shows
    only while No is picked, inside No's edge (`.permnogroup`). **A No
    waits for its reason** (`wordless`), as the reader asked, unless no
    reason can be typed or that No could never be given. Submit stands at
    the foot's right, on the question bar too.
- **The hook must never block Claude Code.** try/except around everything,
  a `give_up_after` deadline over every wait (a stdin that never closes
  too), always exit 0: keep all three. **Arm `LOG_TIMEOUT` again over the
  logging on the way out**, hook and status line: the failure may be the
  filesystem `log` writes to, and an alarm fires once.
  `test_a_failure_is_logged_under_a_deadline_even_after_a_timeout`. **An
  outer `try` catches that alarm too** (#235): between `log` and
  `stand_down` it gave a traceback and exit 1. `stand_down` is in a
  `finally`, so nothing is armed in the outer `except`.
  `test_an_alarm_after_the_log_returns_escapes_nothing`.
- **Every POST carries a token.** A cross-origin `fetch` may POST to a
  loopback port, and here that is `tmux send-keys` into a terminal.
  `allowed()` wants Host, an Origin that is ours when present, and the
  page's token.
- **No page of ours inside another page.** Framed, the page holds the
  token: an invisible frame over a decoy turned two clicks into an Escape
  in a pane. Token and Origin stop requests; only `X-Frame-Options: DENY`
  and `frame-ancestors 'none'`, which `reply` sends on every answer, stop
  clicks. `test_the_page_cannot_be_framed`.
- **The daemon answers on localhost only, and only to its own user and
  root.** A site can point its own name at 127.0.0.1, so `Serving.ours()`
  checks Host, and refuses a request with none.
  - **127.0.0.1 is open to every account**: as `nobody`, `GET /` gave the
    token and `!id` went into the owner's agent (#227). Only the uid keeps
    out users. On Linux `Serving.handle` reads the peer's owner from
    `/proc/net/tcp` and `/proc/net/tcp6` (`::ffff:127.0.0.1`), once a
    connection; `guarded` answers another uid 403 and `STRANGER` before
    any body, on every route. `socket_owner` matches both ends, never
    another connection from the same port.
  - **A line with no inode is nobody's** (`NO_INODE`, #254): the kernel
    shows it as uid 0, root, who is let in, so connect-send-close got past
    a `TIME_WAIT`-only skip. **Not "state `01` only"**: a half-closed
    owner is `05` with its uid and inode, and still reads.
  - **`another_user` refuses what it cannot prove, except on a machine
    with no table** (macOS; the guide says so). An empty table is not
    real: ours lists our listening socket. A missing line is read again,
    `PEER_READS` times: a table written a page at a time can skip one. An
    unreadable table refuses (another user can exhaust our files):
    `read_table` gives None only for a missing file; `handle` refuses on
    any exception.
  - **Read it in the connection's thread, never the accept loop**
    (`verify_request`): a read costs up to 92 ms, and every browser would
    wait.
  - **Root is let in too (`ROOT_UID`)**: WSL2's NAT relay and other
    forwarders run as root, and root can read the token anyway. The live
    test sets `ROOT_UID` to -1, as the suite may run as root.
    `test_root_is_let_in_too`. **WSL2's mirrored mode is not proven** (the
    guide says so): never let a missing line in to fix it.
  - **An ssh tunnel is the owner**: sshd opens it as the logged-in user
    (reasoned, not measured). The 403 says why.
  `test_a_socket_is_found_by_both_of_its_ends`,
  `test_a_client_on_an_ipv6_socket_is_found_in_tcp6`,
  `test_only_the_daemons_own_user_is_let_in`,
  `test_a_line_the_kernel_skipped_once_is_looked_for_again`,
  `test_a_connection_from_another_user_gets_nothing`,
  `test_a_table_that_cannot_be_read_refuses`,
  `test_a_socket_no_process_holds_is_nobodys`; with root and `setpriv`
  only: `test_a_real_request_from_another_user_is_refused`,
  `test_a_request_from_another_user_that_closed_first_is_refused`.
- **A check fails closed, and nothing runs outside the guard.**
  `Origin: http://[::1` or a byte above 0x7f in the token killed the
  thread before the `try`. Checks refuse what they cannot read;
  `guarded()` wraps the whole request.
- **`Serving.route` runs one order of checks for every request** (#545):
  `ours`, `allowed`, then `asked`; `find_route` (`ROUTES`, `GET_VERBS`,
  `POST_VERBS`) runs after those and before the size check: a route with
  its own size check is one a new route forgets. **A POST that may not
  act is refused before its body is read**, and the connection closes:
  `POST_MAX` is megabytes, and any site can POST.
  `test_a_post_that_may_not_act_is_refused_before_its_body_is_read`;
  `test_every_route_refuses_what_it_must` walks the three tables: foreign
  Host, no token, too large.
  - **An empty body and a refused body are different answers.** `asked()`
    never reads a body over `POST_MAX`, so routes saw `{}`: `send` said
    "nothing to send", `name` cleared the name (#235), `answer` said the
    question no longer waited (#254). **Every route that reads `{}` as an
    answer checks it.** `too_big` marks it, cleared at the top of
    `asked()`, as one keep-alive handler serves a whole connection.
    **`Serving.route` refuses `too_big` and `unread` (a body whose end is
    not known) before any verb runs**, with the noun each `POST_VERBS`
    entry carries (#287). The rename box's `maxLength` is `NAME_MAX` too
    (`test_a_row_is_renamed_where_it_stands`).
    `test_a_name_too_large_to_read_keeps_the_name_there_was`,
    `test_an_answer_too_large_to_read_says_that`,
    `test_a_body_that_is_not_read_is_not_taken_for_an_empty_one`.
  - **A verb is a function `verb_<name>`, never a handler method**:
    `http.server` sets `command`, `path`, `headers`, `request` per request,
    and `self.command` hid `Serving.command`.
    `test_no_verb_is_an_attribute_of_the_handler`. **A verb returns
    `(code, payload)`, and `dispatch` sends it with the session's `id`**:
    when only `refuse` added it, a refusal reached the wrong session.
    `raw` and `diff` send bytes and reply themselves.
    `test_every_verb_says_whose_answer_it_is`.
- **A body not read stays in the socket, so the connection closes.** Kept
  alive, the rest of a refused body was served as the next request: a
  `GET` inside it. A socket timeout ends a `Content-Length` never sent.
  **So does every body whose end is not known** (#235): `body_length`
  gives None for `Transfer-Encoding`, a `Content-Length` not plain digits
  (`int()` takes " -5", "5_0"), two that disagree, or more than 18 digits
  (#254: `isdigit()` passed 5,000, `int()` refused, and the 500 kept the
  connection), and `asked()` closes. `Serving.route` closes for a GET
  with any body. A chunk line is answered as HTTP/0.9, with no status
  line, so `only_one_answer` checks nothing follows the first body.
  **`guarded` closes on every 500**: a failed request may leave its body.
  `test_a_body_that_is_not_read_does_not_frame_the_next_request`,
  `test_a_length_too_long_to_be_a_number_is_not_read`,
  `test_a_request_that_fails_closes_its_connection`.
- **The page never trusts what an agent wrote.** Markdown goes into an
  inert `<template>`, is scrubbed to an allowlist, then inserted; event
  values use `textContent`. `innerHTML` fires `onerror` before a scrub.
  - **The scrub keeps three attributes, each checked on its value**
    (`KEPT`, a `Map` of `Map`s): `href` on `A`, for `safeLinks`; `start`
    on `OL`, 1–9 digits, rewritten; `align` on `TH`/`TD`, `left`, `center`
    or `right`. No new tag, scheme or free-text attribute. Without `start`,
    a list split by a fence read 1, 1, 1. **A `Map`, not an object**:
    `constructor` passed as the object's own. `.prose th, .prose td` sets
    `text-align: left`, so `.prose [align=…]` restores `align`.
  - **A task box and a picture become text** (`textFor`; `INPUT` and
    `IMG` have none, so done and not done read the same): ☑ or ☐, and the
    `alt`, as inert text nodes. Class `task` (`.prose li.task`) replaces
    the bullet and is added after the item's attributes are taken, so an
    agent's `class="task"` goes.
  - **A `#` link is its words** (`safeLinks`): headings lose their ids,
    and `goToLink` read `#install` as a session. Only `http(s)` links
    (`LINKABLE`); else an `a` without `href`.
  - **A skill's frontmatter is an agent's text** (any agent can write a
    worktree's `SKILL.md`): `read_command` reads `FRONT_MAX` bytes, three
    keys; a name must be `COMMAND_SHAPE`, as it goes via the send box into
    a terminal; the page sets parts with `put`.
    `test_a_name_that_is_not_a_command_is_left_out`.
  - **Its text is read by name, never by path** (#367, `verb_command`,
    `command_text`): `~/.claude` is outside every worktree, and a path
    from the page is input. Only a file of the list is read
    (`Commands.defined`, no transcripts). **It must be a real `.md`,
    checked where the list is made** (`real_md` in `read_command`) and
    again in `command_text`: a link `leak.md` in `.claude/commands/` can
    point at a key, a FIFO `SKILL.md` holds a thread for ever, and checked
    only at read, `/leak` was listed. Not
    "inside `.claude`": a commands folder may link to dotfiles. At most
    `COMMAND_TEXT_MAX`, through the scrub.
    `test_a_command_that_links_to_a_secret_is_not_read`,
    `test_a_fifo_named_like_a_skill_is_not_listed`,
    `test_a_folder_of_commands_linked_from_elsewhere_is_read`.
  `test_markdown_keeps_task_boxes_step_numbers_sides_and_picture_words`;
  `test_the_scrub_keeps_only_values_it_has_checked` hand-feeds a hostile
  `start`, `align`, `img onerror` and `javascript:`, as marked escapes raw
  HTML.
- **An autolink runs after the scrub, over text nodes, and checks its own
  href.** `linkTickets` builds anchors and parses nothing, so a `url`
  template puts only text. `ticketUrl` checks `http(s)` though
  `link_trouble` did: only it inserts. Links live in the reader's own
  `settings.json`, never a per-worktree file an agent can write. **A
  pattern that can match nothing still makes its links** (`nextMatch`):
  `exec` gives `(PROJ-)?\d*` an empty match first, and `linkOne` silently
  made none. An empty match steps on by one; do not refuse such patterns.
  `linkOne` keeps each pattern's next match: one walk of the text.
  `test_a_pattern_that_can_match_nothing_still_makes_its_links`.
- **Nothing can time a regular expression out in a browser.** The whole
  defence is heuristic, `risky_pattern` (a quantifier in a quantified
  group) and `LINKS_MAX` a block: say so. **`LINKS_MAX` lives in the page
  only**, which alone makes links. Raise it only by measuring:
  `test_there_is_still_a_cap_on_the_links_in_one_block`.
- **A remote URL reaches the page without its user and password**
  (`me:token@`). `remote_url` cuts what precedes the `@`, read from the
  config file, not a third git run each poll. `git@host:path` stays.
  `test_the_remote_is_read_and_never_carries_a_password`.
  - **Read it by git's rules, never with `configparser`**
    (`config_entries`, `config_section`, `config_value`, after git's
    `config.c`); each difference leaked or broke. It kept the quotes of
    `url = "https://me:tok@host/r.git"`, so `urlsplit` saw no scheme; it
    refused a bare key (git's "true"), emptying the remote;
    `allow_no_value` (#252) raised AttributeError before 3.13 out of
    `git_facts` and every tick (topics/git); a continuing `\` split
    `https://me:pw\` + `@host/r.git`.
    - **Read**: `[section]`, `[section "sub"]`, `[section.sub]`; section
      and key in any case; `key = value`, a bare key (None), a key on the
      header's line; `#` and `;` comments outside quotes; double quotes;
      `\"`, `\\`, `\n`, `\t`, `\b`; a `\` at line end. What git refuses
      gives None and remote "". **Never raises**: non-UTF-8 is replaced,
      and a file over `CONFIG_MAX` is not read (a megabyte of bare keys
      cost the tick thread 0.5 s).
    - **Left out, as none moves an `@`**: `[include]`, `includeIf`,
      `insteadOf`; other whitespace in a value stays; a NUL ends no value.
    - **A remote's first `url` is shown**, as `git remote get-url` does;
      `origin`, else the first remote with one.
    - **Only `<git_dir>/config`**: guessing `<dir>/config` read a project
      file `config` at the worktree's top; when only `--show-toplevel`
      answered, `git_facts` gives `<top>/.git`.
    **Then `hide_secrets` runs over it**: a URL inside a URL is not in the
    netloc. `test_the_config_is_read_as_git_reads_it` (against
    `git config --list`, 400 random files),
    `test_a_quoted_remote_url_carries_no_password`,
    `test_a_password_the_url_parse_missed_is_hidden_all_the_same`,
    `test_a_key_without_a_value_does_not_hide_the_remote`,
    `test_a_bare_key_then_an_indented_line_stops_nothing`,
    `test_a_url_continued_on_the_next_line_carries_no_password`,
    `test_the_first_url_of_a_remote_is_the_one_shown`,
    `test_a_config_git_refuses_or_too_big_gives_no_remote`,
    `test_the_top_of_the_worktree_is_not_read_as_its_config`.
- **A one-line summary of a command hides what looks like a credential,
  before the cut**: a row showed `curl -s -u me:token` on a shared screen.
  `tool_target` runs `hide_secrets` (URL passwords, `-u user:pass`,
  credential headers, `Bearer …`, a secret-named `=` value,
  `--password x`, token shapes), keeping the name, for every one-line
  summary: row, `ls`, transcript call line. Not the permission bar: a
  request is judged whole. **Nor a call the reader opened** (#619,
  `call_text`): the reader chose to see it whole, as its output is shown.
  Unknown shapes still show; say so.
  `test_a_summary_hides_what_looks_like_a_credential`,
  `test_a_secret_reaches_no_row_or_ls_but_the_dialog_stays_whole`.
  - **A long command costs the summary no time**: `[\w.-]*token[\w.-]*=`
    in `SECRET_SHAPES` backtracked 3.3 s on 20 KB, on the fold's thread.
    Stars are `{0,64}`, a scheme `{0,31}`; `clip_hidden` gives the
    patterns what `clip` keeps plus `SECRET_REACH`, since an `@` or `=`
    after the cut can mark a secret before it. **Before the cut, never
    after.** A name over 64 characters before its keyword is missed.
    `remote_url` uses it at `REMOTE_SHOWN`.
    `test_a_long_word_costs_a_summary_no_time`,
    `test_a_remote_of_a_megabyte_costs_the_tick_no_time` (CPU time),
    `test_a_secret_is_hidden_as_far_as_the_row_can_show`.
    - **A quoted value may end at the text's end** (#254): the cut can
      fall inside `API_TOKEN="…"`. `"[^"]*(?:"|\Z)`, `'[^']*(?:'|\Z)`; no
      other shape wants a closing quote.
      `test_a_quoted_secret_cut_by_the_clip_is_hidden_to_the_end`.
    - **A shape skips text without its needed character**: bounded,
      `TOKEN=` still cost 0.21 s on 20 KB. Its entry names `"="`, checked
      with `in`. Its test inputs start with `= `, or the skip hides its
      stars from the test.
- **The page never builds HTML from what a program printed**: `putShell`
  puts a `!` command's output and a slash command's answer in a `pre` as
  text.
- **A path out of the event log is input, not fact.** `transcript_path`
  goes through `safe_transcript`; `cwd` is for git and labels, never to
  open a file the page asked for.
  - **A line handed to the reader to run is quoted, every part, and typed
    nowhere** (#352, `resume_command`, `drawResume`):
    `cd <home> && claude --resume <id>`, for the reader to copy. Every
    part goes through `shlex.quote`; an id not `[\w-]+`, or a folder with
    a control character (tab and newline too, unlike `CONTROL_CHARS`),
    gives no line. Starting the agent is a non-goal. `claude --resume`
    finds a session only from its start folder, so `cd` to `home`, never
    `cwd`; a config folder not `~/.claude` adds `CLAUDE_CONFIG_DIR=`.
    `test_every_part_is_quoted_and_a_control_character_gives_no_line`,
    `test_a_session_that_is_over_offers_the_line_that_brings_it_back`.
- **A path out of the page is input too.** `worktree_target` opens a file
  only when `is_listed` says git offers that exact name and `inside` says
  its resolved path is in the worktree. Keep the first check's three
  parts: `:(literal)`, `--`, and comparing the answer with the ask;
  ignored files too. Never swap either check for a bad-path pattern.
  **Both readers go through it.** **A link loop is not inside, and not an
  error**: `Path.resolve` raises RuntimeError up to 3.12, so `inside`
  catches it with OSError; **on 3.13 `resolve` returns a link**, so
  `inside` refuses when `is_symlink()`.
  `test_a_link_loop_is_not_inside_and_is_not_an_error`.
  - **A place from the page is one the daemon listed** (#616,
    `place_of`, `NOT_A_PLACE`): the `place` a Files or Review route names
    is compared with `places_for`, the repositories git found for folders
    the session's own events named, and the path used is the daemon's,
    never the page's. Anything else is a 404, before any git run. The read
    inside a place goes through `worktree_target` as before. **Before a
    pick only `rev-parse` runs there**, which runs nothing a config names;
    `status` and `ls-files` run once the reader picks it, as the reader
    chose (#616).
    `test_another_repository_the_agent_worked_in_is_a_place_of_its_own`.
  - **Nothing inside a `.git` is read**: a tracked
    `notes.md -> ../.git/config` showed a remote's token. `worktree_target`
    refuses a real path with a `.git` part in any case (`.GIT/config` is
    `.git/config` on a case-blind filesystem); an outside git directory is
    `inside`'s. `test_a_link_into_the_git_directory_is_refused`.
  - **A refused read says why, and the refusal stands** (`why_unread`,
    #515): a venv's `bin/python` is listed and refused, and "not in this
    worktree" contradicted the list. Asked only after the refusal, it
    opens nothing: the link's own text, or its end outside the tree; into
    `.git`, only that. A name git does not offer gets the old words.
    `test_a_link_out_of_the_worktree_says_where_it_goes`,
    `test_a_link_out_of_the_worktree_is_refused_with_where_it_goes`.
- **The list of what may be shown lives in the daemon, once**: `SHOWN_AS`,
  via `shown_as`, enforced by `raw`, reported by `read_worktree_file` as
  `FileText.shown` for `putMedia`; a second list drifts. A listed name is
  `binary` unread, or the poll reads half a megabyte for nothing.
- **`raw` is the one answer a browser may keep**; all others carry
  `no-store`. Its address holds the mtime, so a change is a new address.
- **The `raw` route never serves a document.** Types come from the name,
  out of `SHOWN_AS`: pictures, video, sound. An SVG or HTML file would be
  an agent's page on the token's origin. `nosniff` on every answer, or a
  guessed type undoes the list. Never add to `SHOWN_AS` a type a browser
  executes or navigates to.
- **The state directory is private**: `0700` dirs, `0600` files, `0600`
  **at creation** via `open_private`; a later `chmod` leaves a window onto
  every prompt. **Every command makes it via `private_dir`**; `doctor` and
  the start ask `state_dir_trouble`. A bare `mkdir` in `doctor` left it
  0755 (#285). `test_doctor_makes_the_state_directory_private`.
- **A `flock` is on an inode, not on a name**: rotated between open and
  lock, the lock is on the archive, and renaming over it lost every event.
  `still_the_file` checks, and `append_event` reopens. **It belongs to the
  open file, not the process**: a second `open` under the lock waits for
  ever, so `append_event` reopens only when `archive_log` moved the log
  (#253). `test_a_rotation_with_no_listing_writes_the_event_where_it_is`.
- **An event must survive what is in it.** A lone surrogate (legal in JS)
  makes a strict encoder drop the line, and a lost `SessionStart` loses
  the cwd, pane and pid for good. Surrogates are replaced. **A transcript
  carries them too** (`json.loads` makes them real). Everything out is
  `wire_json`, sent by `wire_bytes` with `"replace"`: `reply_json`,
  `Hub.send`, `answer_tag`, both `stream` writes (#289). `page_json` is
  the other road, ASCII, inside the page.
  `test_a_lone_surrogate_in_a_transcript_breaks_nothing`,
  `test_a_lone_surrogate_in_the_sessions_breaks_no_stream`. **No number
  JSON cannot hold**: `float` and `json.loads` read "nan", `NaN` and
  `1e999`, and `json.dumps` of them broke `JSON.parse` on every push
  (#235). `to_float` gives nought.
  `test_a_number_that_is_not_finite_never_reaches_the_page`. **Never write
  a surrogate's escape in source, even in a comment**: Python 3.13 will
  not cache that module. Use `chr(0xD800)`;
  `test_no_source_file_holds_a_lone_surrogate`.
