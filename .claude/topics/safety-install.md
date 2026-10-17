# Safety: what wostuast writes to the disk

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. Install and update, the hook and status files, Claude Code's `settings.json` and ours, the daemon's lock, the report and the list of files.

- **Our `settings.json` is written by the page, and by nothing else.**
  `config_path` puts it in `$XDG_CONFIG_HOME/wostuast/` or
  `~/.config/wostuast/`, where a person looks; `WOSTUAST_CONFIG` moves it
  for tests, a seam and never a setting. The start writes nothing there: it
  left an example `links.json` once, and the menu made that pointless.
  `POST /api/settings` is checked like the verbs -- the token, this machine,
  this user -- because any site can POST to a loopback port, and it writes
  a file of the reader's. **One writer at a time** (`config_lock`): a POST
  runs in its own thread, and two at once each wrote back their own change
  over the same read, the `POST /name` scar. **Every key is checked before
  anything is written** (`config_trouble`, the same check `load_config`
  reads with), so the page cannot write what the file would refuse.
  **A file that cannot be read is never written over** -- the reader may be
  halfway through an edit -- **and a key that is not ours stays**, as a
  hook event keeps its fields. Written whole with
  `write_atomic(private=True)`: the links say where the reader's tickets
  live. **Into the page it goes through `page_json`**, ASCII with `<`, `>`
  and `&` escaped, and the marks are replaced in one pass (`Serving.page`):
  a link is the reader's text, a `</script>` in it ended the script, a
  lone surrogate answered the page 500, and with one `replace` after
  another a link holding the token's mark would have had the token
  written into it. **Every check of a link is `link_trouble`**, the
  extra keys and the url's length too: two of them lived in `save_config`
  alone, so a hand-written link the POST would refuse loaded as good.
  `read_config` is the one reader, for loading and for saving. `test_a_change_is_written_and_keeps_what_it_did_not_touch`,
  `test_a_file_that_cannot_be_read_is_never_written_over`,
  `test_the_settings_in_the_page_cannot_end_its_script`,
  `test_a_setting_needs_the_token`.
  - **The old `links.json` is no longer read, and nothing moves it.** The
    reader chose no migration. `doctor` says the file is there and where
    the links go now, because a file that once made links and now does
    nothing gives no clue why.
    `test_doctor_says_the_old_links_file_is_no_longer_read`.
- **A `settings.json` that cannot be used is never silent.** "No links" and
  "your file is broken" looked identical — nothing on the page either way —
  and the only way to find out was `doctor`, which you had no reason to run.
  The first thing anybody writes by hand is `\d`, which is not a JSON
  escape, so the file never parses. `load_config` returns the usable
  settings, every link *as written* with its own `trouble` -- so the menu
  shows a bad one in red rather than dropping it from sight -- and what is
  wrong. `serve` prints it, the page as served and the push carry it, the page
  says it in the live slot, `doctor` says it. **The file is never repaired**: guessing at
  a backslash somebody meant is a worse surprise than the message. And the
  page adds its own trouble — a pattern Python compiled and this browser
  will not is only findable there, and `takeLinks` says both together.
  **On the slot it is `state.linkTrouble`, not `state.trouble`**: `said`
  clears the second on any answer that worked, so the first Enter took the
  message away for good, and the daemon's sentence about bad JSON is 150
  characters on a line that does not wrap. `paintLive` shows a few words,
  last of the four, with the whole of it in `title`.
- **`wostuast report` holds names, counts, sizes and timings, never the
  reader's text** (#323). It is made to be handed to an agent and pasted
  into an issue. A value is shown only when it is a name (`named`,
  `REPORT_NAME`), and only from the fields `REPORT_KINDS` lists, plus
  `tool_name`, whose MCP server is left out (`tool_named`: the reader
  names the server, often after a company); every other payload field is
  counted by its key alone. The error log is counted by the **builtin**
  exception a line names (`exception_named`), never by its message, which
  holds paths and commands: any capitalised word ending in "Error" was a
  folder's name once. The transcript section's labels pass `labelled`.
  `doctor`'s lines go in through `private_paths`: home becomes `~`,
  wostuast's own folders that are not under home become `<state dir>`
  and the like -- `XDG_STATE_HOME` can put the log anywhere, and that
  path can carry a user name -- this copy's path `<this copy>`, any other
  absolute path `<path>`, and anything quoted `'…'`, which is how a bad
  ticket-link pattern came back in a regular expression's error. The
  swaps go longest first with home among them: a folder of ours that
  holds home, replaced first, left the user name behind it. A review
  found six of these before it shipped. A new section adds to
  `test_the_report_never_holds_the_readers_text` or
  `test_what_the_review_found_does_not_leak_either`, which write the
  reader's text into every place it can stand.
- **`installed_files` is the one list of what wostuast puts on the disk**,
  for `wostuast files` and the report (#321). A new file goes on it, and in
  the guide's Files table (`docs/GUIDE.md`); `test_every_file_wostuast_writes_is_listed`
  calls every `*_path()` and `*_dir()` of the program and fails on one it
  does not find there.
- **One daemon a state directory, held by a lock, not by the port.** A
  second start on another port ran beside the first (#320): both appended
  a `Declined` for the same dialog, two renames at once could lose one,
  and "one send at a time" (`claim`) holds within one daemon, so two
  pages on two daemons could type into one pane together. `cmd_serve`
  takes `one_daemon`'s `flock` on `daemon_lock_path()` after
  `state_dir_trouble` and **before `bring_up_to_date`**, so a second start
  writes nothing; `serve_page` runs under it and lets go on every way out.
  `flock`, not a pid file: the kernel lets go when the process dies, so a
  `kill -9` leaves no lock a start would have to clear or guess about.
  The file says the pid and, once bound, the page's address (`say_who`),
  which is what the second start prints. Only `BlockingIOError` means
  "held": any other `flock` error, a file system with no locks, is said as
  itself, never as a daemon that runs
  (`test_a_lock_that_cannot_be_taken_is_not_a_daemon_that_runs`). Tests that call `cmd_serve` get
  their own state directory, so they never meet each other's lock.
  `test_a_second_start_says_where_the_first_runs_and_changes_nothing`,
  `test_a_daemon_that_died_leaves_no_lock_behind`.
- **The hooks and the status line run the installed copy, not the checkout,
  and a start mends it when the two differ.** `install` copies this file to
  `install_path()`. A reader who pulled and restarted `serve` had a page
  that could show the session's spend, beside a status line — run by the
  copy from the day before — that never wrote it down. The page showed no
  cost and nothing said why; the reader's own status line printed the
  number, so the payload plainly carried it. `install_behind` compares the
  bytes, and `doctor` counts it as a problem. **A bare `wostuast` writes
  what is behind before it serves** (#275, `bring_up_to_date`): the
  program, the hook file, the hooks and the status line -- and nothing
  that is already right. Claude Code's `settings.json` is saved only when
  its parsed content changed, because a start runs every day and the file
  is the user's (the bullet below). A file it cannot read stops the start,
  in red, before anything is served -- in one line (`unreadable`): the
  path with `~`, and for broken JSON only its line and column. The
  parser's own words ran past the edge of the terminal and named the
  place twice. `test_a_settings_file_that_holds_no_object_is_said_once`.
  `test_doctor_says_and_a_start_mends_an_installed_copy_of_another_version`,
  `test_a_start_with_nothing_behind_writes_nothing`,
  `test_a_start_stops_on_a_settings_file_it_cannot_read`.
  - **`doctor`, the start and `report` read one table of checks**
    (`SETUP_CHECKS`, `setup_checks`, `Check`, #549). The checks were
    written twice, in `doctor_checks` and in the start, and the words had
    drifted: "tmux not found;" in one and "tmux not found:" in the other,
    the state directory with its full path and with `~`, one settings line
    a problem or one for all. A check is a function of `SetupFacts`, which
    reads Claude Code's `settings.json` once -- one `doctor` loaded it
    three times -- and gives a `Check` or None. A start makes the ones in
    `START_FIRST` before it writes anything and `START_AFTER` once the
    hooks are up to date, and prints each that is not ok with its `start`
    mark; it does not make the others, because `bring_up_to_date` mends
    what they would find. A new check is a row, and the start's lists name
    it if a start should say it.
    `test_every_check_says_the_same_in_doctor_and_at_a_start`.
    - **A start's checks are brief, and said in the start's order**
      (#591, from the review of #535's session). One table made the
      start count the event log as `doctor` does (`measure_log`), which
      reads every archive -- the cost #430 had kept off the start -- to
      print nothing when all is well; `SetupFacts.brief` lets
      `check_events` only ask whether the log exists. And `setup_checks`
      ran the table's order, so a start said a state directory it cannot
      write before tmux was missing; it follows `only` now.
      `test_a_start_reads_no_archive_of_the_log`,
      `test_a_start_says_its_checks_in_its_own_order`.
  - **The hooks run a file made from the program, never a copy kept by
    hand** (#271). `hook_source` takes the definitions named in
    `HOOK_PARTS` out of the program's source with `ast`, between
    `HOOK_HEAD` and `HOOK_TAIL`, and `install` writes it to `hook_path`
    with `write_program` -- through `write_atomic`, as the program is,
    because a hook may be reading it. It had a temp-and-rename of its own,
    whose name lacked the thread that `write_atomic`'s carries (#285). A
    start builds the hook once: `bring_up_to_date` hands what it built to
    `install_behind`, which parsed the whole program a second time.
    `test_a_start_builds_the_hook_once`.
  - **The status line runs a file made the same way, `status.py`**
    (#286): `STATUS_PARTS` between `STATUS_HEAD` and `STATUS_TAIL`, built
    by `program_files` in the same parse as the hook file. It ran the whole
    program on every redraw, 127 ms against about 45. **Not in the hook
    file**: it needs `dataclasses`, whose 8 ms every hook event would have
    paid. It reads `--then` with `then_in`, not argparse. A status line of
    ours in the old shape, `wostuast status [--then …]`, is moved to it by
    `add_status_line`, with the user's line kept; `is_ours`, `then_of`,
    `remove_status_line`, `hook_files_missing`, `install_behind` and
    `uninstall` know both shapes. **A part is copied from its first
    decorator**: `ast` puts a class at its `class` line, and `Status` came
    out with no `@dataclass` and took no arguments.
    `test_the_status_file_defines_every_name_it_uses`,
    `test_the_status_file_keeps_the_session_and_prints_its_line`,
    `test_an_old_status_line_of_ours_is_moved_to_the_status_file`,
    `test_install_points_the_status_line_at_the_status_file`. So `cmd_hook` and everything it calls are
    written once, and the hook's tests run the hook file itself
    (`run_installed` in `conftest.py` makes it with `program_files`). **A part
    left out is a NameError on every event that nobody sees**: the hook
    catches everything and may say nothing. `hook_source` refuses a name
    it cannot find, and `test_the_hook_file_defines_every_name_it_uses`
    checks every global each function reads with `symtable`. A new helper
    on the hook's path goes into `HOOK_PARTS`, or that test goes red.
    `install_behind` says when the file is not what this version writes,
    and when a file the settings name is not there or cannot run
    (`hook_files_missing`): `is_ours` knows the command by its shape, so
    the hooks still looked registered while every event was lost;
    `add_hooks` moves an old `wostuast hook` entry to the file where it
    stands, and only that way round (`is_hook_file`).
    - **The verbs `wostuast hook` and `wostuast status` are gone (#322), and
      a gone verb exits 1, never 2** (`GONE_VERBS`). An entry from before
      the hook file still calls one until its session restarts, and Claude
      Code reads exit 2 from a hook as "block": argparse's "invalid choice"
      would have refused the tool call or thrown the prompt away. 1 is an
      error it shows and goes on from. `doctor` counts only an entry that
      runs the hook file (`runs_hook_file`), never the old shape `is_ours`
      still knows for moving and removing it.
      `test_hook_and_status_are_gone_and_never_block`,
      `test_doctor_counts_an_entry_from_before_the_hook_file_as_missing`.
    `test_the_hook_file_records_an_event_and_says_nothing`,
    `test_the_hook_file_loads_little`,
    `test_an_old_install_is_moved_to_the_hook_file_in_place`,
    `test_doctor_says_when_the_hook_file_is_not_this_versions`,
    `test_doctor_says_when_the_hook_file_is_gone`.
- **`install` fetches the newest only as the installed copy, pinned to a
  commit, and installs nothing that is not the program** (#345,
  `fetch_newest`, `newest_program`, `runs_installed`). **Only the installed
  copy and the one-line install fetch**: `./wostuast install` in a checkout
  installs the checkout, or the branch being tried is replaced by `main`
  the moment it is installed. **An installed copy that is a symlink is not
  the installed copy**: it resolved to the checkout it points at, and the
  rename would have put `main` in the link's place. A bare start never fetches: the reader chose
  `install` alone, and a start that went to the network paid its time,
  or a timeout offline, every day. **The bytes come from the commit's SHA
  (`RAW_AT`), never from raw `main`**: `COMMITS_URL` names the last commit
  that changed the file, raw `main` is cached for five minutes, and the
  file and the date would then be of two commits. The SHA goes into a URL,
  so it must be forty hex digits. **What came back must start as the
  program and compile**: a 404 page or half a file would be written over
  the program that every hook runs. **The new copy runs its own install**
  (`os.execv` with `install --fetched`), because the hook file is built
  from the program that builds it, and the old one would build the old
  hooks. **Keep `--fetched`, hidden, for ever**: it is the older copy that
  passes it, to a newer one. **The one-line install hands over even when
  nothing changed**: it has no file, so `bring_up_to_date` would take raw
  `main` (`self_source`) and could write a cached, older program over the
  one just fetched. **A fetch that fails says why in one line and
  the install goes on** with the copy it has: no network is no reason to
  leave the hooks unregistered. The file takes the commit's time
  (`os.utime`), so `own_version` says the day the program was made.
  `test_newest_program_fetches_the_file_at_the_commit_it_names`,
  `test_newest_program_refuses_what_is_not_the_program`,
  `test_the_installed_copy_fetches_the_newest_and_hands_over_to_it`,
  `test_the_copy_install_hands_over_to_installs_and_never_fetches`,
  `test_a_fetch_that_fails_says_why_and_installs_this_copy`,
  `test_a_checkout_installs_itself_and_never_fetches`,
  `test_a_link_to_a_checkout_is_not_the_installed_copy`,
  `test_the_one_line_install_hands_over_even_to_the_same_copy`.
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
  - **`uninstall` gives back a status line it wrapped** (#234). `install`
    tells a user with a line of their own to write
    `wostuast status --then '<theirs>'`, `is_ours` counts that line as
    ours, and `uninstall` deleted the whole entry, their command with it.
    `remove_status_line` puts `<theirs>` back as the command and keeps the
    entry's other keys. `then_of` reads `--then` as the shell and argparse
    do: `shell_words`, then `--then X`, `--then=X`, or a short form such as
    `--th`, the last one winning. A line a shell cannot split is left alone.
    **`shell_words` is `shlex` and one more step** (#254): inside double
    quotes a shell drops the backslash before `$`, a backquote, `"`, `\`
    and a newline, and `shlex` drops it only before `"` and `\`. So
    `--then "echo \$HOME"` came back as `echo \$HOME`. `QUOTED_PARTS`
    finds the double-quoted parts and `DOUBLE_QUOTED` takes the rest off,
    pair by pair from the left. A single-quoted line, which `install`
    writes, comes back exactly.
    `test_uninstall_puts_back_the_status_line_it_wrapped`,
    `test_uninstall_removes_a_plain_status_line_and_leaves_one_it_cannot_read`,
    `test_a_double_quoted_status_line_comes_back_as_a_shell_reads_it`.
