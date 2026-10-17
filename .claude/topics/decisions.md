# Decisions without a scar behind them

Chosen, not learned from a bug. Weigh the reason before undoing one.

**Recording**

- **A hook appends to a file; it never makes a request.** Events are kept
  with no daemon running, the hook is a one-liner with no network, and the
  file is the history. The hook's `$TMUX_PANE` is the pane: no tmux
  discovery code.
- **The agent's pid is the nearest ancestor of `$PPID` named `claude`.**
  `$PPID` is the shell that runs the hook and dies with it: taken as the
  agent, every live session showed as killed seconds after it started. The
  raw one is kept as `shell_pid`; the log keeps what it is given.
  `agent_pid`.
- **Listen to both events that announce a permission dialog.**
  `PermissionRequest` fires as it appears. `Notification` fires after six
  idle seconds, checked on a six-second timer: up to twelve seconds late. The
  row read `working` three seconds after the dialog was up.
- **Never guess what no hook reports.** Nothing fires on a Yes, so an
  approved `cmake --build` leaves the row amber until its `PostToolUse`. A
  No fires nothing. The row says what is known; the pane settles it. Invent
  no event. **The one record of our own is `Declined`**, and it is no
  guess: the transcript shows the call rejected, whether the page or the
  reader in the terminal pressed Escape.
- **Search is a plain scan of the event log: no index, no transcript**
  (#379). The log holds the reader's prompts (`UserPromptSubmit`'s
  `prompt`) and each turn's last answer (`Stop`'s `last_assistant_message`),
  archives too; transcripts are many, long, and may be gone.
  A 20 MB log, the size it is archived at, took 130 to 340 ms a query, so a
  box that asks 250 ms after the last key needs no index, and goal 4 keeps
  SQLite out. `search_log` skips a line that cannot hold every ASCII word
  before parsing it; **a word that is not ASCII is matched in the parsed
  text only**, because a line may write it as an escape (`\u00dc`), which
  the raw check missed; **so is a word with a quote or a backslash**, which
  JSON escapes too. The excerpt is placed by the words as written, not
  their lower case, which can be longer. **A filter that cannot be read is
  refused, never dropped** (`ValueError`, said by the route): dropped,
  `before:yesterday` alone answered with the newest of everything. Filters
  are Slack's (`parse_search`): `in:`, `from:me`, `from:claude`, `before:`,
  `after:` (a day in the machine's zone, the reader's), `is:unread`. A
  result is the hook's stamp, a little after the transcript's, so "open"
  lands on the nearest block within a minute (`goToNear`), never on block 0
  by default. **A prompt is what `prompt_said` says it is**, as the fold
  reads it: only the reader's own, without its paste tags (#536).
  `test_search_takes_slacks_filters`, `test_search_reads_the_archives_too`,
  `test_search_every_session_and_open_a_result`.
- **The status line writes one small file per session, never the log.** It
  runs on every redraw: an append would flood the log with nothing new.
  `install` never replaces a user's status line; it prints the line to
  add. Without one, sessions lack name, context and spend; all
  else works. `cmd_status`.
- **Hooks, not an SDK, a stream, Remote Control or OpenTelemetry** (#267).
  **The Agent SDK and `claude -p --output-format stream-json --input-format stream-json`**
  have the richest stream and answer a permission by callback
  (`canUseTool`), but wostuast would have to start and own the agent
  process, a non-goal, and neither attaches to the reader's interactive
  sessions in tmux. **`--permission-prompt-tool`** works with `claude -p`
  only, never interactively. **Remote Control** is for a person on a phone
  or another browser; it gives a program nothing to read or call. **OpenTelemetry** is configured by the owner's company, not
  the owner, so wostuast cannot point it anywhere (the owner, on #267).
  Still open: channels and hook decisions, the next two bullets.
- **Channels wait until they leave the research preview** (the owner's
  choice, #265). A channel is an MCP server the session starts over stdio.
  It can push text in, and with `claude/channel/permission` it gets each
  tool approval with a `request_id` and can answer that one: a No bound to
  one dialog, which tmux keys cannot give (CLAUDE.md, the non-goal "A Yes the reader
  did not give, or one that keys carry"). Against it: every session must start with
  `--dangerously-load-development-channels` (a warning dialog) or an
  allowlisted plugin; organisations must enable it; text arrives as a
  `<channel>` tag, not a typed prompt, so slash commands fail and "send"
  would change meaning; `AskUserQuestion` is not relayed, so its keys stay;
  it is a way into the terminal beyond the four tmux verbs, so
  topics/safety's ask-first applies; and the relay can say allow, which the
  page once was never to send (a Yes now goes through the hook,
  topics/safety). **Look again when the preview ends**; a prototype behind
  the flag is then the first step.
- **The hook stays a command that appends to the log.** An `http` hook
  (#266) saves a process per event but records nothing while the daemon is
  down, breaking the first bullet here and goal 4. A process, 200 runs, a
  real `PreToolUse` payload, four cores, Python 3.11: `python3 wostuast hook`
  119 ms median, 155 ms p95; `python3 -c pass` 13 ms; `sh -c 'cat >> file'`
  4 ms. 58 ms was `compile()` of the 17,206-line file, since a script run
  directly gets no bytecode cache; imported with a `.pyc` it took 65 ms.
  **#271 fixed it with a file of the hook's own functions** (`hook_source`,
  topics/safety): 33 ms median against 131, 45 ms p95; of the 33, 13 is the
  interpreter, about 12 `json`, `pathlib` and `re`, 3 compiling. A shell
  hook would be 4 ms but needs `jq` for the JSON and `flock` for the lock,
  and macOS has neither `flock` nor `/proc` for the agent's pid; the owner
  chose the file.
- **A `PermissionRequest` hook that waits for the reader's Yes is adopted**
  (topics/safety, first bullet): its `allow` is bound to its own dialog,
  which keys never are, and the reader asked for Yes once the page showed
  the whole request. A `deny` the same way would be an id for a No; not
  built, because Escape has its proof already. **A waiting
  `PermissionRequest` hook does not hold the terminal** (#266, the script
  is in the issue). Measured by the owner on Claude Code 2.1.286 with a hook
  that slept 30 s: the dialog was on screen 5 s and 15 s into the wait, as
  without the hook; an Escape in the terminal 15 s in answered it at once
  ("User rejected write") and stopped the hook (its log has `start`, no
  `end`). The first answer wins, and a hook still waiting for the page dies
  when the terminal answers. On 2.1.292 an allow after the wait closed the
  dialog and the call ran.

**For a script**

- **`ls --json` prints `session_json`, a promise, never `row`** (#353).
  `row` is the page's and changes with it; a script reading it would break
  on the next pull request. `session_json` only grows: a field is added,
  never renamed or removed without a new `JSON_VERSION`. Times are moments,
  never "3min". docs/GUIDE.md lists every field;
  `test_ls_json_keeps_its_shape` and
  `test_the_json_fields_are_the_ones_readme_lists` hold both lists to it.
  **What both say comes from one place** (#540): the worktree is
  `worktree_path`, git's facts `git_fields`;
  `test_the_row_and_ls_json_say_the_same_of_a_session` holds them equal.
- **`wait` reads the log as the daemon does, and needs no daemon** (#356,
  `cmd_wait`): a `Store` and its `EventFollower`, folded every `WAIT_STEP`,
  reading only what was appended. It types nothing, so a script typing the
  next prompt after it is the reader's, not orchestration of ours. **It
  follows a `/clear`** (`cleared_into`), as the page does; else a wait on a
  session that cleared ends in "ended", exit 1. `pick_session` finds a name:
  id, start of the id, name, place, the first that fits; two that fit the
  same way are refused, both named. Exit 124 at `--timeout`, as
  `timeout(1)`. `test_it_waits_for_the_state_to_come`,
  `test_a_clear_is_followed_into_the_session_it_became`.

**Serving**

- **Polling, not inotify.** No dependency; the scale is tens of files. The
  daemon polls the log and transcripts; the Files and Diff tabs poll from
  the browser, only while on screen.
- **Port 7331, on 127.0.0.1 only** (`DEFAULT_PORT`, `BIND_HOST`).
  `--port 0` lets the system pick, and the start prints the port the socket
  got (`server_address`) in the address and the `ssh -L` line; it had
  printed `:0` in both. `port_number` checks the range in argparse: a port
  out of range reached `bind` as an `OverflowError`, not an `OSError`, and
  `serve` died with a traceback (#235).
  `test_serve_says_the_port_it_got_when_asked_for_any`,
  `test_serve_refuses_a_port_that_is_not_one_without_a_traceback`.
- **No SQLite.** `sqlite3` is standard library and imports faster than
  `json`; the write path is the question. One short-lived hook writing one
  row took 2 ms, 32 at once 20 ms median and 183 ms worst, against 0.1 ms
  and 4 ms for an append under `flock`, on the one path that must never
  block. As an index only the daemon writes, it buys a faster start and
  nothing a feature needs: a plain scan of 400 MB for a word takes 0.38 s.
  A checkpoint of the folded state buys the same start without a schema,
  when the start is slow enough to matter.

**The page**

- **Markdown renders in the browser; the diff parser is our own.** The
  standard library has no Markdown renderer, and the browser is the best
  one. A diff is small to parse and drawn in our own shapes.
- **Syntax highlighting earned a second library.** Code without colour is
  the one place plain costs more than it saves. `highlight.js` is fetched
  when the first non-Markdown file opens or the Diff tab first draws a
  diff, never on load, so a day of reading transcripts never fetches it.
  `hljsReady`.
- **A path is found by scattered letters; text is found as typed.** A path
  is a handle half remembered; prose is read, so a search means what was
  typed. `fuzzy`, `findPath`, `matches`.
- **A long list builds only the rows on screen.** Every row is one height,
  so the place is arithmetic: ten thousand matches cost what ten do, and no
  answer is cut to stay quick.
- **Column widths are the reader's.** Both edges drag, the width is kept in
  this browser, a double-click puts it back. The alternative was a config
  option.
- **The look: a sibling of tmux -- dark, quiet, precise.** IBM Plex Mono for
  machine text only -- code, a diff, a command, the boxes -- Plex Sans for
  chrome and prose (#448), Plex Sans Condensed for file names, which are
  long, and every list on the left (`--mono`, `--sans`, `--narrow`), each with a system
  fallback so the page reads offline. No emoji anywhere. Icons are inline
  stroke SVG in `ICONS`. Amber (`--needs`) means "needs you"; the light
  theme is the same variables on a light ground.
- **State reaches the page by one channel: the push.** A POST's answer says
  only what the push cannot: whether it worked, what was refused. Two
  channels for one state land in either order: a settings answer landed
  before an older push and was undone by it; it took three guards and a
  numbering of pushes (`keepSetting`, `tell_config`; topics/sidebar has the
  scar).
- **The transcript keeps its two channels, a GET and the push.** It is the
  one state that comes both ways: the GET is the snapshot, the push what
  came after, and guards order them (`state.turns.early`, `told`,
  `TRANSCRIPT_RETRY`; topics/transcript holds their scars). The stream
  alone would drop the guards, but needs its own zlib on SSE to keep
  "nothing big goes twice" over ssh, and rewrites the most delicate part of
  the page. The guards work and are tested, so the owner closed #295 as not
  planned. **Read #295 before proposing it again.**
- **What the reader is typing is the reader's until they close it.** A push
  never rebuilds a box, row or list being edited; it is drawn from state
  again when it opens (`putLinkRows` from `showSettings`, the rename box in
  `fillRow`). Guarding each way a push can land misses the next way; owning
  the box does not.
- **A review is written on the page and sent as one message.** The
  alternative, reading here and retyping in the terminal from memory, is
  what this tool replaced. One message reaches the agent as one thought,
  not four interruptions.

**Git**

- **A branch's work is measured against the branch it was cut from, found
  by counting.** A backport is cut from a release branch and goes back to
  it; against `origin/HEAD`, every commit the release has and main lacks
  showed as the agent's. `pick_base` counts every branch against HEAD,
  `%(ahead-behind:HEAD)` (git 2.41), and ranks by fewest of HEAD's commits
  lacking, then `origin/HEAD` and `BASE_NAMES`, then fewest it has that
  HEAD lacks -- in that order, or a colleague's branch cut at the same
  point was named over main, which had moved further.
  `test_a_backport_is_measured_against_the_branch_it_was_cut_from`,
  `test_unpushed_work_on_main_is_measured_against_the_remote`,
  `test_a_branch_cut_at_the_same_point_is_not_named_over_main`.
  - **A branch holding all of HEAD is never the base**, the default one
    aside: a child branch, a backup, a detached HEAD's own branch, a copy
    under another name, local `main` ahead of `origin/main` each lacked
    nought and won, showing nothing. The default stays, so an agent on it
    with everything pushed is measured against it, and the picker lists the
    last `COMMITS_RECENT` of HEAD, which are what it did.
    `test_a_branch_that_holds_all_of_head_is_never_the_base`.
  - The branch's own copy on a remote is left out by name, **so a git that
    cannot say the name does not rank**: `symbolic-ref HEAD` gives None for
    a timeout as for a detached HEAD, and without the name the copy lacked
    only the unpushed commits and won. `rev-parse --abbrev-ref HEAD`, asked
    only then, says `HEAD` for a detached one; if it fails too, the usual
    names stand in.
    `test_a_branch_git_could_not_name_is_not_measured_against_its_own_copy`.
  - **`origin/HEAD` is only a name to prefer, never taken on its word**: a
    remote that renamed its default branch leaves it naming a branch
    `fetch --prune` took away
    (`test_an_origin_head_that_points_nowhere_is_not_the_base`). A git that
    cannot count falls back to those names in turn; with none, the Diff tab
    shows only what is uncommitted and says so.
    `test_a_git_that_cannot_rank_falls_back_to_the_usual_names`.
- **The count is kept, because it walks history.** On 150,000 commits and
  3,000 branches it took 1.3 to 1.6 s, against `RUN_TIMEOUT`'s two, on
  every five-second poll. `Daemon.ranks` keeps it under HEAD and a cheap
  listing of every ref with its commit, and counts again, under
  `DIFF_TIMEOUT`, only when one moves.
  `test_the_ranking_is_counted_once_while_nothing_moves`.
- **The reader can pick the base** in the Diff tab's second `select`, kept
  in this browser for the worktree (`BASE_KEY`, `recallBase`, `baseHome`),
  keyed on `GitFacts.root`, never `cwd`, which moves with every `cd` of the
  agent. It goes as `?base=` and **is used only if git listed that exact
  name**, checked against the cheap listing, not the count, so a count git
  could not finish never drops it; a pick is always on the list.
  `test_a_base_the_page_names_is_used_only_if_git_listed_it`,
  `test_a_pick_stands_when_the_ranking_cannot_be_counted`,
  `test_the_base_can_be_picked_and_is_kept_for_the_worktree`.
  - **A whole file is asked for against `state.diff.base`**, the base the
    diff was drawn on, never the pick: with nothing picked the daemon finds
    one again, and a different answer drew another base's lines between
    these hunks.
    `test_a_whole_file_is_asked_for_against_the_base_the_diff_was_drawn_on`.
  - **An answer for a base the reader has moved from does not land**:
    `loadDiff` drops it when `recallBase()` changed while it was out; a
    poll's late answer had put the found base's diff under a picker naming
    another. `test_a_diff_asked_for_before_the_base_was_picked_does_not_land`.
