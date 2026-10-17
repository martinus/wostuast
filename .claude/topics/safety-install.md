# Safety: what wostuast writes to the disk

Install and update, the hook and status files, Claude Code's `settings.json` and ours, the daemon's lock, the report and the list of files.

- **Our `settings.json` is written by the page, and by nothing else.**
  `config_path` puts it in `$XDG_CONFIG_HOME/wostuast/` or
  `~/.config/wostuast/`, where a person looks; `WOSTUAST_CONFIG` is a test
  seam, never a setting. The start writes nothing there (once an example
  `links.json`). `POST /api/settings` is checked like the verbs (token,
  this machine, this user): any site can POST to a loopback port. **One
  writer at a time** (`config_lock`): two POST threads wrote over each
  other, the `POST /name` scar. **Every key is checked before anything is
  written** (`config_trouble`, the check `load_config` reads with), so the
  page cannot write what the file would refuse. **A file that cannot be
  read is never written over** (the reader may be mid-edit), **and a key
  not ours stays**, as a hook event keeps its fields. Written with `write_atomic(private=True)`: links say
  where the reader's tickets live. **Into the page it goes through `page_json`** (ASCII, `<`,
  `>` and `&` escaped), the marks replaced in one pass (`Serving.page`): a
  link's `</script>` ended the script, a lone surrogate gave a 500, and
  one `replace` after another would write the token into a link holding
  the token's mark. **Every check of a link is `link_trouble`**, extra keys
  and url length too: checks in `save_config` alone let a bad hand-written
  link load. `read_config` is the one reader, for loading and saving.
  `test_a_change_is_written_and_keeps_what_it_did_not_touch`,
  `test_a_file_that_cannot_be_read_is_never_written_over`,
  `test_the_settings_in_the_page_cannot_end_its_script`,
  `test_a_setting_needs_the_token`.
  - **The old `links.json` is no longer read, and nothing moves it**: the
    reader chose no migration. `doctor` says it is there and where links go
    now, or nothing would explain the lost links.
    `test_doctor_says_the_old_links_file_is_no_longer_read`.
- **A `settings.json` that cannot be used is never silent**: "no links" and
  "broken file" looked the same, and the first hand-written `\d` is not a
  JSON escape. `load_config` returns the usable settings, every link *as
  written* with its own `trouble` (shown red in the menu, not hidden), and
  what is wrong; `serve`, the page, the push, the live slot and `doctor`
  all say it. **The file is never
  repaired**: a guessed backslash is a worse surprise than the message. The
  page adds its own trouble (a pattern Python compiles and the browser
  refuses), and `takeLinks` says both. **On the slot it is
  `state.linkTrouble`, not `state.trouble`**: `said` clears the second on
  any answer that worked, so the first Enter erased it. `paintLive` shows
  a few words, last of four, the whole in `title`: the line does not wrap.
- **`wostuast report` holds names, counts, sizes and timings, never the
  reader's text** (#323): it is handed to an agent and pasted into an
  issue. A value shows only when it is a name (`named`, `REPORT_NAME`) of a
  field `REPORT_KINDS` lists, plus `tool_name` without its MCP server
  (`tool_named`: the reader names it, often after a company); other fields
  count by key. The
  error log counts by the **builtin** exception a line names
  (`exception_named`), never its message, which holds paths and commands
  (a folder once ended in "Error"). Transcript labels pass `labelled`. `doctor`'s lines go through `private_paths`: home becomes
  `~`; wostuast's folders outside home `<state dir>` and the like
  (`XDG_STATE_HOME` can carry a user name); this copy `<this copy>`; any
  other absolute path `<path>`; anything quoted `'…'`, as a bad link
  pattern came back in a regex error. Swaps go longest first with home
  among them: a folder of ours holding home, swapped first, left the user
  name. A new section adds to `test_the_report_never_holds_the_readers_text`
  or `test_what_the_review_found_does_not_leak_either`, which put the
  reader's text everywhere it can stand.
- **`installed_files` is the one list of what wostuast puts on the disk**,
  for `wostuast files` and the report (#321). A new file goes on it and in
  the Files table of `docs/GUIDE.md`; `test_every_file_wostuast_writes_is_listed`
  calls every `*_path()` and `*_dir()` and fails on one not there.
- **One daemon a state directory, held by a lock, not by the port.** A
  second start on another port ran beside the first (#320): two `Declined`
  for one dialog, lost renames, and `claim` holds only within one daemon,
  so two pages could type into one pane. `cmd_serve` takes `one_daemon`'s `flock` on
  `daemon_lock_path()` after `state_dir_trouble` and **before
  `bring_up_to_date`**, so a second start writes nothing; `serve_page` runs
  under it and lets go on every way out. `flock`, not a pid file: the
  kernel frees it on `kill -9`. The file holds the pid and then the
  address (`say_who`), for a second start to print. Only `BlockingIOError` means "held"; any other `flock` error (a
  file system with no locks) is said as itself
  (`test_a_lock_that_cannot_be_taken_is_not_a_daemon_that_runs`). Tests
  calling `cmd_serve` get their own state directory.
  `test_a_second_start_says_where_the_first_runs_and_changes_nothing`,
  `test_a_daemon_that_died_leaves_no_lock_behind`.
- **The hooks and the status line run the installed copy, not the checkout,
  and a start mends it when the two differ.** `install` copies this file to
  `install_path()`; after a pull, the page waited for spend that the old
  copy's status line never wrote, silently.
  `install_behind` compares the bytes, and `doctor` counts it a problem.
  **A bare `wostuast` writes what is behind before it serves** (#275,
  `bring_up_to_date`): program, hook file, hooks, status line, and nothing
  already right. Claude Code's `settings.json` is saved only when its
  parsed content changed: a start runs daily, and the file is the user's.
  A file it cannot read stops the start in red before serving, in one line
  (`unreadable`): the path with `~`, for bad JSON only line and column; the
  parser's own words overran the terminal.
  `test_a_settings_file_that_holds_no_object_is_said_once`,
  `test_doctor_says_and_a_start_mends_an_installed_copy_of_another_version`,
  `test_a_start_with_nothing_behind_writes_nothing`,
  `test_a_start_stops_on_a_settings_file_it_cannot_read`.
  - **`doctor`, the start and `report` read one table of checks**
    (`SETUP_CHECKS`, `setup_checks`, `Check`, #549): copies in
    `doctor_checks` and the start drifted. A check is a function of
    `SetupFacts`, which reads Claude Code's `settings.json` once (`doctor`
    read it three times), giving a
    `Check` or None. A start
    makes `START_FIRST` before writing and `START_AFTER` once the hooks are
    up to date, printing each not ok with its `start` mark; it skips the
    rest, as `bring_up_to_date` mends what they find. A new check is a row,
    named in the start's lists if a start should say it.
    `test_every_check_says_the_same_in_doctor_and_at_a_start`.
    - **A start's checks are brief, and said in the start's order** (#591,
      after #535): counting the log like `doctor` (`measure_log`) read every
      archive, a cost #430 kept off the start; `SetupFacts.brief` lets
      `check_events` only ask if the log exists. `setup_checks` follows
      `only`, not the table's order.
      `test_a_start_reads_no_archive_of_the_log`,
      `test_a_start_says_its_checks_in_its_own_order`.
  - **The hooks run a file made from the program, never a copy kept by
    hand** (#271). `hook_source` takes the definitions in `HOOK_PARTS`
    from the program's source with `ast`, between `HOOK_HEAD` and
    `HOOK_TAIL`; `install` writes it to `hook_path` with `write_program`,
    through `write_atomic` as a hook may be reading it (a temp-and-rename
    of its own lacked the thread in the name, #285). A start builds the
    hook once: `bring_up_to_date` hands it to `install_behind`, which
    parsed the whole program again. `test_a_start_builds_the_hook_once`. So `cmd_hook` and
    all it calls are written once, and the hook's tests run the hook file
    itself (`run_installed` in `conftest.py`, made with `program_files`).
    **A part left out is a NameError on every event that nobody sees**:
    the hook catches everything and says nothing. `hook_source` refuses a
    name it cannot find, and `test_the_hook_file_defines_every_name_it_uses`
    checks every global each function reads with `symtable`; a new helper
    on the hook's path goes into `HOOK_PARTS`. `install_behind` says when
    the file is not this version's, or a file the settings name is missing
    or cannot run (`hook_files_missing`): `is_ours` knows the command by
    shape, so hooks looked registered while every event was lost.
    `add_hooks` moves an old `wostuast hook` entry to the file in place,
    and only that way round (`is_hook_file`).
    `test_the_hook_file_records_an_event_and_says_nothing`,
    `test_the_hook_file_loads_little`,
    `test_an_old_install_is_moved_to_the_hook_file_in_place`,
    `test_doctor_says_when_the_hook_file_is_not_this_versions`,
    `test_doctor_says_when_the_hook_file_is_gone`.
    - **The verbs `wostuast hook` and `wostuast status` are gone (#322),
      and a gone verb exits 1, never 2** (`GONE_VERBS`): an entry from
      before the hook file calls one until its session restarts, and
      Claude Code reads exit 2 as "block": argparse's "invalid choice"
      would refuse the tool call or drop the prompt; 1 is an error it shows
      and goes on from. `doctor` counts only an entry that runs the hook file
      (`runs_hook_file`), never the old shape `is_ours` still knows for
      moving and removing it.
      `test_hook_and_status_are_gone_and_never_block`,
      `test_doctor_counts_an_entry_from_before_the_hook_file_as_missing`.
  - **The status line runs a file made the same way, `status.py`** (#286):
    `STATUS_PARTS` between `STATUS_HEAD` and `STATUS_TAIL`, built by
    `program_files` in the hook file's parse. The whole program cost 127 ms
    a redraw against about 45. **Not in the hook file**: its `dataclasses`
    would cost every hook event 8 ms. It reads `--then` with `then_in`,
    not argparse. `add_status_line` moves an old line of ours,
    `wostuast status [--then …]`, to it, keeping the user's line; `is_ours`,
    `then_of`, `remove_status_line`, `hook_files_missing`, `install_behind`
    and `uninstall` know both shapes. **A part is copied from its first
    decorator**: `ast` puts a class at its `class` line, and `Status` lost
    its `@dataclass`.
    `test_the_status_file_defines_every_name_it_uses`,
    `test_the_status_file_keeps_the_session_and_prints_its_line`,
    `test_an_old_status_line_of_ours_is_moved_to_the_status_file`,
    `test_install_points_the_status_line_at_the_status_file`.
- **`install` fetches the newest only as the installed copy, pinned to a
  commit, and installs nothing that is not the program** (#345,
  `fetch_newest`, `newest_program`, `runs_installed`). **Only the installed
  copy and the one-line install fetch**: `./wostuast install` in a checkout
  installs the checkout, or a branch being tried becomes `main`. **An
  installed copy that is a symlink is not the installed copy**: it resolves
  to a checkout, and the rename would put `main` in the link's place. **A
  bare start never fetches**: the reader chose `install` alone, as a start
  would pay the network, or an offline timeout, daily. **The bytes come
  from the commit's SHA (`RAW_AT`), never raw `main`**: `COMMITS_URL` names
  the last commit of the file, raw `main` is cached five minutes, and file
  and date would be of two commits. The SHA goes into a URL, so it must be
  forty hex digits. **What came back must start as the program and
  compile**: a 404 page or half a file would replace what every hook runs.
  **The new copy runs its own install** (`os.execv` with
  `install --fetched`): the old program builds old hooks. **Keep `--fetched`, hidden, for ever**: older copies
  pass it to newer ones. **The one-line install hands over even when
  nothing changed**: with no file, `bring_up_to_date` would take raw `main`
  (`self_source`) and could write a cached, older program over the one
  just fetched. **A failed fetch says why in one
  line and the install goes on** with its own copy: no network is no
  reason to leave hooks unregistered. The file takes the commit's time
  (`os.utime`), so `own_version` gives the day it was made.
  `test_newest_program_fetches_the_file_at_the_commit_it_names`,
  `test_newest_program_refuses_what_is_not_the_program`,
  `test_the_installed_copy_fetches_the_newest_and_hands_over_to_it`,
  `test_the_copy_install_hands_over_to_installs_and_never_fetches`,
  `test_a_fetch_that_fails_says_why_and_installs_this_copy`,
  `test_a_checkout_installs_itself_and_never_fetches`,
  `test_a_link_to_a_checkout_is_not_the_installed_copy`,
  `test_the_one_line_install_hands_over_even_to_the_same_copy`.
- **`settings.json` is the user's file, not ours.** `install` touches our
  hooks and nothing else. Its permissions are kept (a fresh temporary took
  the umask: 0600 came back 0644, on API keys). The write is fsynced, file
  and directory: Claude Code will not start without it. `uninstall` leaves a group it took nothing from exactly as it was,
  an empty one too. **A link is written through, not over**: dotfile
  managers keep it as a link into a repository, and a rename over the link
  cut the repository off. `save_settings` resolves the path
  first, so temporary and rename sit beside the real file. **The temporary
  is 0600 from the moment it exists**: `write_atomic` narrowing it after
  left a 0644 copy of the API keys in `~/.claude`, for good if `install`
  died. `open_private` keeps the same rule for an append; a stale temporary
  of the same name is unlinked first, as `O_TRUNC` keeps its mode.
  `test_a_settings_file_that_is_a_link_stays_a_link`,
  `test_the_settings_are_never_on_disk_where_others_can_read_them`,
  `test_a_temporary_left_by_a_writer_that_died_is_not_trusted`.
  - **`uninstall` gives back a status line it wrapped** (#234): `install`
    tells a user with a line of their own to write
    `wostuast status --then '<theirs>'`, which `is_ours` counts as ours,
    and `uninstall` deleted their command with it. `remove_status_line`
    puts `<theirs>` back as the command and keeps the entry's other keys.
    `then_of` reads `--then` as a shell and argparse do: `shell_words`,
    then `--then X`, `--then=X`, or a short form such as `--th`, the last
    winning. A line a shell cannot split is left alone. **`shell_words` is
    `shlex` and one more step** (#254): in double quotes a shell drops the
    backslash before `$`, a backquote, `"`, `\` and a newline, `shlex` only
    before `"` and `\`, so `--then "echo \$HOME"` came back as
    `echo \$HOME`. `QUOTED_PARTS` finds the double-quoted parts and
    `DOUBLE_QUOTED` strips the rest, pair by pair from the left. A
    single-quoted line, as `install` writes, comes back exactly.
    `test_uninstall_puts_back_the_status_line_it_wrapped`,
    `test_uninstall_removes_a_plain_status_line_and_leaves_one_it_cannot_read`,
    `test_a_double_quoted_status_line_comes_back_as_a_shell_reads_it`.
