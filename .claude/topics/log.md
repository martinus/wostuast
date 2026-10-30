# Log

The event log: each line folded once and in order, `Tail`, archives, `seq`.

- **Fold every line of the log once, in written order; never drop an event
  for its `ts`.** Handlers assign, never accumulate. `Store.apply` once
  dropped events older than the session had seen, but hooks write out of
  order and clocks step back, and a lost `PermissionRequest` never goes
  amber. `append_event(record, stamp=True)` stamps under the lock; the
  place in the file keeps a repeat out.
  `test_two_hooks_that_raced_for_the_lock_are_both_folded`,
  `test_a_clock_stepped_back_does_not_stop_the_fold`,
  `test_a_hook_stamps_its_time_once_it_holds_the_lock`.
  - **`EventFollower.new_lines` opens the live file *before* it lists the
    archives**: a rotation links before it unlinks, so the listing names
    every older archive. It reads an unfinished one first, then lists
    again. The other order read a new live file before its archive.
    **An archive that cannot be read stops the pass**, retried up to
    `ARCHIVE_TRIES` (`Tail.whole`); marked finished, it was skipped. Only a
    pass that read none of it counts as a try.
    `test_a_rotation_in_the_middle_of_a_pass_is_read_once_and_in_order`,
    `test_a_rotation_just_after_the_listing_is_read_in_order`,
    `test_an_archive_that_could_not_be_opened_is_read_on_the_next_pass`,
    `test_an_archive_that_never_opens_is_given_up_in_the_end`,
    `test_an_archive_that_moves_is_not_given_up`.
  - **A failed listing is not an empty one** (#253): read as `[]`, an old
    archive came last and an answered dialog went amber again.
    `archived_events_paths` gives `None` for any error but a missing folder,
    and `new_lines` then reads nothing. **Each caller says what `None`
    means**: `archive_log` does not rotate, and the hook writes where it is
    (topics/safety, "A `flock` is on an inode"); `read_events` raises, and
    `ls` and `doctor` say so. The hook's deadline `TimeoutError`, an
    `OSError`, is no failed listing: it goes on out.
    `test_a_listing_that_fails_reads_nothing_until_it_works`,
    `test_a_listing_that_fails_does_not_bring_an_answered_dialog_back`,
    `test_a_rotation_with_no_listing_writes_the_event_where_it_is`,
    `test_the_hooks_deadline_in_the_listing_is_not_a_failed_listing`,
    `test_a_listing_that_fails_is_not_a_log_with_no_archives`.
  - **Read a file once, by device and inode, whatever its name** (#253): a
    rotation stopped between `os.link` and `os.unlink` leaves the live file
    under archive names too. `new_lines` skips the live file and those it
    finished (`done_files`). **Never check the live handle against
    `done_files`**: a reused inode would blind the follower. `log_handles`
    does the same for `read_events` and `measure_log`. `archive_log` takes
    a failed `unlink` as no rotation, so no event is lost.
    `test_a_rotation_cut_short_is_read_once`,
    `test_a_start_on_a_rotation_cut_short_reads_the_live_file_once`,
    `test_a_log_under_two_names_is_read_once`,
    `test_a_rotation_between_the_listing_and_the_live_file_is_read`.
- **The log is never thrown away, so nothing may hold it whole.**
  `archive_log` keeps every archive (`archived_events_paths`). A 200 MB
  year once took 641 MB. `Tail.lines` reads `TAIL_CHUNK` at a time, `fold`
  calls `forget_quiet` every `FORGET_EVERY` of the *log's* clock, and
  `reload_git` asks only about shown sessions, not `git_wanted` on all.
  `test_a_big_log_is_read_a_piece_at_a_time` (`tracemalloc`),
  `test_the_first_read_holds_the_history_not_all_of_it`,
  `test_git_is_asked_about_the_sessions_shown_and_no_others`.
  - **Forget by the last event, never the first**, so a running session
    keeps where it started. The test moves `cwd` after the start, or a
    session forgotten and remade looks right.
  - **A start folds only the last `HISTORY_FOLDED` (30 days)** (#430):
    all took 5.5 s at 240,000 events. `folded_long_ago` leaves older
    archives out in `EventFollower.new_lines` and `read_events`
    (`log_handles(recent=True)`), so the page and `ls` agree. An older
    session loses what only its start said (`home`, `first_prompt`): the
    reader chose that over a snapshot, a second way to one state.
    `measure_log` and `search_log` read every archive. **Never leave out an
    archive already begun, nor the live file.**
    `test_a_start_leaves_out_the_archives_older_than_the_window`.
  - **An empty piece is not the end of the file**: a line longer than
    `TAIL_CHUNK` gives nothing until it ends. The end is the size when the
    read starts.
  - **One event that raises costs only itself**: `Tail.lines` counts the
    piece before it hands out lines, and `Store.fold` catches per event.
    **So does a line that cannot be read**: `json_objects` skips
    `RecursionError` too, which a line nested too deep raises and which is
    no `ValueError`; it left the reader, outside the fold's catch.
    `test_one_event_that_cannot_be_folded_costs_only_itself`,
    `test_a_line_nested_too_deep_to_read_costs_only_itself`.
- **Take an archive's name with `os.link`, never `os.replace`**: the number
  comes from a listing, and `os.replace` overwrites what landed there
  meanwhile; it once lost every event (topics/safety, "A `flock` is on an
  inode"). `os.link` refuses a taken name. The
  follower hands its tail over by inode; by name it re-read 20 MB.
- **`Tail` starting over is news the reader must hear**: it restarts at 0
  when the file shrinks or its inode changes; an append-only reader drew
  the transcript twice. `Tail.restarted` says so; `Transcript` clears and
  bumps `run`. The event log's tail hands over instead.
- **`seq` is a place in one reading, not an identity**: `Daemon` builds a
  new reader when `transcript_path` changes, and `seq` restarts for the
  same id while the page patches by index. Every push and reply carries
  `run`; an unseen `run` replaces, never merges. Reproduce with a
  **rename**: an unlink and recreate may reuse the inode.
