# Decisions without a scar behind them

Each of these was chosen, not learned the hard way, so nothing above holds
it. The reason is the part to weigh before undoing one.

**Recording**

- **A hook appends to a file; it never makes a request.** The daemon need
  not be running for events to be kept, the hook stays a one-liner with no
  network in it, and the file is the history. `$TMUX_PANE` from the hook's
  environment is the pane, so there is no tmux discovery code at all.
- **The agent's pid is found by walking up from `$PPID` to the nearest
  ancestor named `claude`.** `$PPID` itself is the shell Claude Code runs a
  hook through, which dies with the hook: taking it for the agent showed
  every live session as killed seconds after it started. The raw one is kept
  as `shell_pid`, because the log keeps what it is given. `agent_pid`.
- **Two events announce a permission dialog, and both are listened to.**
  `PermissionRequest` fires as the dialog appears. `Notification` says the
  same, but only once you have been idle six seconds, checked on a
  six-second timer, so up to twelve seconds late — measured: the row still
  read `working` three seconds after the dialog was up.
- **What no hook reports is not guessed.** Nothing fires when a dialog is
  answered Yes, so an approved `cmake --build` leaves the row amber until its
  `PostToolUse`, for as long as the build runs. Saying No fires nothing at
  all. The row is left saying what is known; the pane is what settles it. Do
  not invent an event that does not exist. **The one record of our own is
  `Declined`**, and it is not a guess: the transcript showed the call
  rejected before it was written, whether the page pressed the Escape or
  the reader did in the terminal.
- **The status line writes one small file per session, and never the log.**
  It runs on every redraw, so an append would flood the log with nothing
  new. `install` never replaces a status line the user already has: it
  prints the line to add instead. Without one, sessions have no name, no
  context and no spend, and everything else works. `cmd_status`.

**Serving**

- **Polling, not inotify.** No dependency, and the scale is tens of files.
  The daemon polls the log and the transcripts; the Files and Diff tabs poll
  from the browser, and only while on screen.
- **Port 7331**, on 127.0.0.1 only (`DEFAULT_PORT`, `BIND_HOST`).
  `--port 0` lets the system pick a free port, and `serve` prints the one
  the socket has (`server_address`), in the address and in the `ssh -L`
  line: it printed `:0` in both. `port_number` checks the range in
  argparse, because a port out of range reached `bind` as an
  `OverflowError`, which is not an `OSError`, and `serve` died with a
  traceback (#235). `test_serve_says_the_port_it_got_when_asked_for_any`,
  `test_serve_refuses_a_port_that_is_not_one_without_a_traceback`.
- **No SQLite.** `sqlite3` is in the standard library and imports faster
  than `json`, so it is not a dependency question. The write path is: one
  short-lived hook writing one row took 2 ms, and 32 at once 20 ms median
  and 183 ms at worst, against 0.1 ms and 4 ms for an append under `flock` —
  on the one path that must never block. As an index only the daemon writes,
  it would buy a faster start and nothing a feature needs: a plain scan of
  400 MB for a word takes 0.38 s. A checkpoint of the folded state buys the
  same faster start without a schema, when the start is slow enough to
  matter.

**The page**

- **Markdown renders in the browser; the diff parser is our own.** The
  standard library has no Markdown renderer, and the browser is the best one
  available. A diff is small to parse and is drawn in our own shapes.
- **Syntax highlighting earned a second library.** Code with no colour is the
  one place where plain costs more than it saves. `highlight.js` is asked for
  when the first file that is not Markdown opens or the Diff tab first draws
  a diff, never on load, so a day of reading transcripts never fetches it.
  `hljsReady`.
- **A path is found by scattered letters; text is found as typed.** A path is
  a handle half remembered. Prose is read, so a search over it means what was
  typed. `fuzzy`, `findPath`, `matches`.
- **A long list builds only the rows on screen.** Every row is one height,
  so where the reader is is arithmetic; ten thousand matches then cost the
  same as ten, and no answer is cut to stay quick.
- **Column widths are the reader's.** Both edges drag, the width is kept in
  this browser, and a double-click puts it back. The alternative was a config
  option.
- **The look: a sibling of tmux — dark, quiet, precise.** IBM Plex Mono for
  chrome and code, Plex Sans for prose, Plex Sans Condensed for file names,
  which are long (`--mono`, `--sans`, `--narrow`), each with a system
  fallback so the page reads offline. No emoji anywhere. Icons are inline
  stroke SVG in `ICONS`. Amber (`--needs`) is the colour of "needs you", and
  the light theme is the same variables on a light ground.
- **State reaches the page by one channel: the push.** An answer to a POST
  says only what the push cannot -- whether it worked, and what was
  refused. Two channels carry the same state on two connections, and they
  land in either order: a settings answer landed before an older push and
  was undone by it, and three guards and a numbering of the pushes were
  built before the second channel was taken out (`keepSetting`,
  `tell_config`; topics/sidebar has the scar).
- **What the reader is typing is the reader's until they close it.** A push
  never rebuilds a box, a row or a list that the reader is editing; it is
  drawn from the state again when it opens (`putLinkRows` from
  `showSettings`, the rename box in `fillRow`). Guarding each way a push can
  land misses the next way; owning the box does not.
- **A review is written on the page and sent as one message.** The
  alternative is what this tool replaced: read here, switch to the terminal,
  retype from memory. One message reaches the agent as one thought rather
  than four interruptions.

**Git**

- **A branch's work is measured against the branch it was cut from, found
  by counting.** A backport is cut from a release branch and goes back into
  it, and measured against `origin/HEAD` it showed every commit the release
  carries and main does not as the agent's. `pick_base` counts every branch
  against HEAD, `%(ahead-behind:HEAD)` (git 2.41), and ranks by the fewest
  of HEAD's commits it lacks, then `origin/HEAD` and `BASE_NAMES`, then the
  fewest it has that HEAD lacks -- in that order, or a colleague's branch
  cut at the same point was named over main, which had moved on further.
  **A branch holding all of HEAD is never the base**, the default one
  aside: a child branch, a backup, a detached HEAD's own branch, a copy
  under another name, local `main` ahead of `origin/main` each counted
  nought missing and won, with nothing to show. The default stays, so an
  agent on the default branch with everything pushed is measured against
  it and the picker lists the last `COMMITS_RECENT` of HEAD, because those
  are what it did. The branch's own copy on a remote is left out by name,
  **so a git that cannot say the name does not rank**: `symbolic-ref HEAD`
  gives None for a timeout as for a detached HEAD, and with the name lost
  the copy lacked only the commits not pushed yet and won.
  `rev-parse --abbrev-ref HEAD`, asked only then, says `HEAD` for a
  detached one; when it fails too, the usual names stand in.
  `test_a_branch_git_could_not_name_is_not_measured_against_its_own_copy`.
  `origin/HEAD` is only a name to prefer, never taken on its word: a remote
  that renamed its default branch leaves it naming a branch `fetch --prune`
  took away (`test_an_origin_head_that_points_nowhere_is_not_the_base`). A
  git that cannot count falls back to those names in turn; with none, the
  Diff tab shows only what is not committed and says so.
  `test_a_backport_is_measured_against_the_branch_it_was_cut_from`,
  `test_a_branch_that_holds_all_of_head_is_never_the_base`,
  `test_unpushed_work_on_main_is_measured_against_the_remote`,
  `test_a_branch_cut_at_the_same_point_is_not_named_over_main`,
  `test_a_git_that_cannot_rank_falls_back_to_the_usual_names`.
- **The count is kept, because it walks history.** Measured on 150,000
  commits and 3,000 branches: 1.3 to 1.6 s, against `RUN_TIMEOUT`'s two,
  on every five-second poll. `Daemon.ranks` keeps it under HEAD and a
  listing of every ref with its commit, which is cheap, so it is counted
  again only when one moves, and under `DIFF_TIMEOUT`.
  `test_the_ranking_is_counted_once_while_nothing_moves`.
- **And the reader can pick it**, in the Diff tab's second `select`, kept in
  this browser for the worktree (`BASE_KEY`, `recallBase`, `baseHome`) --
  keyed on `GitFacts.root`, never `cwd`, which moves with every `cd` the
  agent makes. It goes as `?base=` and **is used only if git listed that
  exact name**, checked against the cheap listing and not the count, so a
  count git could not finish never drops it; a pick is always on the list.
  The page asks for a whole file against `state.diff.base`, the base the
  diff was drawn on, never the pick: with nothing picked the daemon would
  find one again, and a different answer drew another base's lines between
  these hunks. **An answer for a base the reader has moved from does not
  land**: `loadDiff` drops it when `recallBase()` has changed while it was
  out, or a poll's late answer put the found base's diff under a picker
  naming another. `test_a_diff_asked_for_before_the_base_was_picked_does_not_land`,
  `test_a_base_the_page_names_is_used_only_if_git_listed_it`,
  `test_a_pick_stands_when_the_ranking_cannot_be_counted`,
  `test_the_base_can_be_picked_and_is_kept_for_the_worktree`,
  `test_a_whole_file_is_asked_for_against_the_base_the_diff_was_drawn_on`.
