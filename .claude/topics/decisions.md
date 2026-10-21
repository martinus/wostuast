# Decisions without a scar behind them

Choices, not lessons from a bug. Weigh the reason before undoing one.

**Recording**

- **A hook appends to a file; it never makes a request.** Events are kept
  with no daemon, the hook needs no network, and the file is the history.
  The hook's `$TMUX_PANE` is the pane: no tmux discovery.
- **The agent's pid is the nearest ancestor of `$PPID` named `claude`.**
  `$PPID` is the hook's shell, which dies with it: every live session showed
  as killed. The log keeps it as `shell_pid`. `agent_pid`.
- **Listen to both events that announce a permission dialog.**
  `Notification` comes up to twelve seconds after `PermissionRequest`; the
  row read `working` with the dialog up.
- **Never guess what no hook reports.** Nothing fires on a Yes or a No, so
  an approved `cmake --build` stays amber until its `PostToolUse`; the pane
  settles it. **The one record of our own is `Declined`**, proved by the
  transcript (topics/state, "The daemon writes a `Declined` record").
- **Search is a plain scan of the event log: no index, no transcript**
  (#379). The log holds the prompts (`UserPromptSubmit`'s `prompt`) and
  each turn's last answer (`Stop`'s `last_assistant_message`), archives
  too; transcripts may be gone. A 20 MB log, the size it is archived at,
  took 130 to 340 ms a query, and goal 4 keeps SQLite out.
  - `search_log` skips a line that cannot hold every ASCII word before it
    parses it. **A word not ASCII, or with a quote or backslash, is matched
    in the parsed text only**: JSON escapes it (`Ü`). The excerpt is
    placed by the words as written; their lower case can be longer.
  - **A filter that cannot be read is refused, never dropped**
    (`ValueError`, said by the route): dropped, `before:yesterday` returned
    the newest of everything. Slack's filters (`parse_search`): `in:`,
    `from:me`, `from:claude`, `before:`, `after:` (a day in the machine's
    zone), `is:unread`.
  - A result carries the hook's stamp, a little after the transcript's, so
    "open" lands on the nearest block within a minute (`goToNear`), never
    on block 0. **A prompt is what `prompt_said` says**, as the fold reads
    it: the reader's own, without paste tags (#536).
  `test_search_takes_slacks_filters`, `test_search_reads_the_archives_too`,
  `test_search_every_session_and_open_a_result`.
- **The status line writes one small file per session, never the log.** It
  runs on every redraw. `install` never replaces a user's status line; it
  prints the line to add. Without one, sessions lack name, context and
  spend. `cmd_status`.
- **Hooks, not an SDK, a stream, Remote Control or OpenTelemetry** (#267).
  The Agent SDK and `claude -p --output-format stream-json` answer a
  permission by callback (`canUseTool`), but wostuast would have to own the
  agent, a non-goal, and neither attaches to sessions in tmux.
  `--permission-prompt-tool` is `claude -p` only. Remote Control gives a
  program nothing to call. The owner's company configures OpenTelemetry.
- **Channels wait until they leave the research preview** (#265). With
  `claude/channel/permission` a channel gets a No bound to one dialog
  (`request_id`), which keys cannot give. Against: each session needs
  `--dangerously-load-development-channels` or an allowlisted plugin; text
  arrives as a `<channel>` tag, so slash commands fail; `AskUserQuestion`
  is not relayed; and it is a way into the terminal beyond the four tmux
  verbs (topics/safety's ask-first). **Look again when the preview ends.**
- **The hook stays a command that appends to the log.** An `http` hook
  (#266) records nothing while the daemon is down: against the first
  bullet and goal 4. The cost was compiling the whole file, 119 ms an
  event; **#271 cut it to 33 ms with a file of the hook's own functions**
  (`hook_source`, topics/safety-install). A shell hook needs `jq` and
  `flock`, and macOS has neither `flock` nor `/proc`.
- **A `PermissionRequest` hook that waits for the reader's Yes is
  adopted** (topics/safety, first bullet): its `allow` is bound to its own
  dialog, which keys never are. No `deny` that way: Escape has its proof.
  **A waiting hook does not hold the terminal** (#266 holds the script):
  an Escape in the terminal answers the dialog and ends the hook; an allow
  after a wait still runs the call. The first answer wins.

**For a script**

- **`ls --json` prints `session_json`, a promise, never `row`** (#353).
  `row` changes with the page. `session_json` only grows: no field is
  renamed or removed without a new `JSON_VERSION`. Times are moments, never
  "3min". docs/GUIDE.md lists every field. **Both read one place** (#540):
  `worktree_path`, `git_fields`. `test_ls_json_keeps_its_shape`,
  `test_the_json_fields_are_the_ones_the_guide_lists`,
  `test_the_row_and_ls_json_say_the_same_of_a_session`.
- **`wait` reads the log as the daemon does, and needs no daemon** (#356,
  `cmd_wait`): a `Store` and its `EventFollower`, folded every
  `WAIT_STEP`. It types nothing, so a script that types after it is not
  our orchestration. **It follows a `/clear`** (`cleared_into`); else a
  wait on a cleared session ends "ended", exit 1. `pick_session` takes an
  id, its start, a name or a place; two that fit the same way are refused,
  both named. Exit 124 at `--timeout`, as `timeout(1)`.
  `test_it_waits_for_the_state_to_come`,
  `test_a_clear_is_followed_into_the_session_it_became`.

**Serving**

- **Polling, not inotify.** No dependency; tens of files. The daemon polls
  the log and transcripts, the tabs poll from the browser
  (topics/daemon-and-page).
- **Port 7331, on 127.0.0.1 only** (`DEFAULT_PORT`, `BIND_HOST`). With
  `--port 0` the start prints the port the socket got (`server_address`),
  not `:0`. `port_number` checks the range in argparse: out of range,
  `bind` raised `OverflowError` and `serve` died with a traceback (#235).
  `test_serve_says_the_port_it_got_when_asked_for_any`,
  `test_serve_refuses_a_port_that_is_not_one_without_a_traceback`.
- **No SQLite.** 32 hooks writing a row at once took up to 183 ms, against
  4 ms for an append under `flock`, on the path that must never block. As
  a daemon's index it buys only a faster start: a scan of 400 MB takes
  0.38 s. A checkpoint of the folded state would buy that without a schema.

**The page**

- **Markdown renders in the browser; the diff parser is our own.** The
  standard library has no Markdown renderer; a diff is small to parse.
- **Syntax highlighting earned a second library.** `highlight.js` loads
  when the first non-Markdown file opens, the Diff tab first draws, or a
  call is opened onto its command (#619), never on load. `hljsReady`.
- **A path is found by scattered letters; text is found as typed.** A path
  is half remembered; prose means what was typed. `fuzzy`, `findPath`,
  `matches`.
- **A long list builds only the rows on screen.** Every row is one height,
  so ten thousand matches cost what ten do, and no answer is cut short.
- **Column widths are the reader's.** Both edges drag, the width is kept in
  this browser, a double-click resets it. The alternative was a config
  option.
- **The look: a sibling of tmux, dark, quiet and precise.** IBM Plex Mono
  for machine text only, Plex Sans for chrome and prose (#448), Plex Sans
  Condensed for file names and every list on the left (`--mono`, `--sans`,
  `--narrow`), each with a system fallback. No emoji. Icons are inline
  stroke SVG in `ICONS`. Amber (`--needs`) means "needs you"; the light
  theme is the same variables on a light ground.
- **State reaches the page by one channel: the push.** A POST's answer says
  only whether it worked or what was refused. Two channels for one state
  land in either order (`keepSetting`, `tell_config`; topics/settings).
- **The transcript keeps its two channels, a GET and the push.** The GET is
  the snapshot, the push what came after; guards order them
  (`state.turns.early`, `told`, `TRANSCRIPT_RETRY`; topics/transcript).
  The push alone needs its own zlib on SSE and a rewrite of the page's most
  delicate part. **Read #295, closed as not planned, before proposing it.**
- **What the reader is typing is the reader's until they close it.** A push
  never rebuilds a box, row or list being edited; it is drawn from state
  when it opens (`putLinkRows` from `showSettings`, the rename box in
  `fillRow`). A guard per way a push lands misses the next way.
- **A review is written on the page and sent as one message**: one
  thought to the agent, not four interruptions, and not retyped from
  memory.

**Git**

- **A branch's work is measured against the branch it was cut from, found
  by counting.** Against `origin/HEAD`, a backport showed every commit its
  release branch has and main lacks. `pick_base` counts every branch with
  `%(ahead-behind:HEAD)` (git 2.41) and ranks by fewest of HEAD's commits
  lacking, then `origin/HEAD` and `BASE_NAMES`, then fewest it has that
  HEAD lacks; another order named a colleague's branch over main.
  `test_a_backport_is_measured_against_the_branch_it_was_cut_from`,
  `test_unpushed_work_on_main_is_measured_against_the_remote`,
  `test_a_branch_cut_at_the_same_point_is_not_named_over_main`.
  - **A branch holding all of HEAD is never the base**, the default one
    aside: a child branch or a backup lacked nought and won, showing
    nothing. On the default, the picker lists HEAD's last `COMMITS_RECENT`.
    `test_a_branch_that_holds_all_of_head_is_never_the_base`.
  - **A git that cannot name the branch does not rank**: its remote copy is
    left out by name, and unnamed it won. `symbolic-ref HEAD` gives None
    for a timeout too, so `rev-parse --abbrev-ref HEAD` is asked; if that
    fails, the usual names stand in.
    `test_a_branch_git_could_not_name_is_not_measured_against_its_own_copy`.
  - **`origin/HEAD` is a name to prefer, never taken on its word**: after a
    rename it names a branch `fetch --prune` removed
    (`test_an_origin_head_that_points_nowhere_is_not_the_base`). A git that
    cannot count falls back to the names; with none, the Diff tab shows
    only what is uncommitted and says so.
    `test_a_git_that_cannot_rank_falls_back_to_the_usual_names`.
- **The count is kept, because it walks history.** On 150,000 commits and
  3,000 branches it took 1.3 to 1.6 s, against `RUN_TIMEOUT`'s two.
  `Daemon.ranks` keeps it under HEAD and a cheap listing of every ref, and
  counts again under `DIFF_TIMEOUT` only when one moves.
  `test_the_ranking_is_counted_once_while_nothing_moves`.
- **The reader can pick the base** in the Diff tab's second `select`, kept
  per worktree in this browser (`BASE_KEY`, `recallBase`, `baseHome`),
  keyed on `GitFacts.root`, never `cwd`, which moves with every `cd`. It
  goes as `?base=` and **is used only if git listed that exact name**, in
  the cheap listing, not the count, so a count git could not finish never
  drops it. `test_a_base_the_page_names_is_used_only_if_git_listed_it`,
  `test_a_pick_stands_when_the_ranking_cannot_be_counted`,
  `test_the_base_can_be_picked_and_is_kept_for_the_worktree`.
  - **A whole file is asked for against `state.diff.base`**, the base the
    diff was drawn on, never the pick: the daemon may find another, and
    drew its lines between these hunks.
    `test_a_whole_file_is_asked_for_against_the_base_the_diff_was_drawn_on`.
  - **An answer for a base the reader has left does not land**: `loadDiff`
    drops it when `recallBase()` changed while it was out.
    `test_a_diff_asked_for_before_the_base_was_picked_does_not_land`.
