# Git

How the daemon calls git, reads its answers and failures, and parses a
diff.

- **Work from the worktree root** (`worktree_root`): git prints
  root-relative paths from anywhere.
  - **Take only the newline off a path git prints, never `strip()`**:
    `/x/proj ` became another directory. `worktree_root` and `git_facts`
    do `rstrip("\n")`.
    `test_a_worktree_whose_path_ends_in_a_space_is_that_worktree`.
- **The daemon's git takes no lock.** `status` and `diff` refresh the index
  under `.git/index.lock`, so the agent's `git add` failed, and a git
  killed at its timeout left the lock behind. `run` sets
  `GIT_OPTIONAL_LOCKS=0` for every git, in one place. **`git diff` writes
  the index anyway** when a stat moved and the bytes did not, so `git_diff`
  also sets `diff.autoRefreshIndex=false`.
  `test_git_never_takes_the_index_lock_the_agent_needs`.
- **Inside a hunk only a line's first character matters; only `diff --git`
  and `@@` start something new.** A removed `-- a comment` is
  `--- a comment`, which read as a header and swallowed the hunk.
- **`run` reads bytes and decodes them itself, never `text=True`**: that
  made a lone CR a line break, and later lines were numbered one too high.
  A CRLF file's diff lines end in `\r`, as the Files tab's do.
  `test_a_carriage_return_inside_a_line_stays_in_that_line`.
- **Split a diff on `\n`, never with `splitlines()`**: it also splits on
  form feed, `\x1c`-`\x1e` and `\u0085`, which git leaves unescaped in
  source, and a comment anchored one line off.
- **A path out of a diff may be quoted; unquote it in one place**
  (`unquote_path`). `core.quotePath=false` still escapes a quote,
  backslash or control character, so `we"ird.txt` read as a rename.
  **A name holding a space ends in a TAB** on the `---` and `+++` lines;
  `parse_diff` takes one off.
  `test_a_name_with_a_space_is_the_name_the_files_tab_lists`. **A
  `diff --git` line that is not a rename splits in the middle**
  (`diff_header_paths`): splitting at the last ` b/` made
  `a/Plan b/logo.png b/Plan b/logo.png` a rename.
  `test_a_folder_ending_in_b_does_not_make_a_rename`.
  - **A file with no lines says it came or went only in its mode line**,
    so `name_change` called it modified. `parse_diff` reads
    `new file mode` and `deleted file mode`; `drawDiffFile` says "A new,
    empty file." or "The file was empty."
    `test_a_new_or_deleted_file_with_no_lines_is_added_or_deleted`,
    `test_a_new_or_deleted_file_with_no_lines_says_what_happened`.
  - **A path whose type changed is one entry, not two.** git writes a file
    that became a link as a deletion and an addition; two entries with one
    `data-key` sent clicks, `whole_file_diff` and comments to the wrong
    half. `join_type_change` makes one entry, status `typechange`,
    `old_kind`/`new_kind` from `MODE_KINDS`, one hunk; the page adds only
    `statusWord` ("FILE → LINK"). **Join only two adjacent halves of one
    path, of two kinds**: without `-B` git writes nothing else so.
    `test_a_file_that_became_a_link_is_one_entry`,
    `test_a_type_change_is_joined_only_where_git_writes_one`,
    `test_a_file_that_became_a_link_is_one_row_one_block_and_one_comment`.
- **A cut goes back to the last newline, and the cap counts bytes**
  (`FILE_MAX_BYTES`): a cut inside a `diff --git` line made a phantom
  rename, and a `len()` cap let four-byte characters through at four times
  the size.
- **What git has started and not finished is read off its files, in the
  worktree's own git folder**, at no git call (#357, `worktree_doing`,
  `own_git_dir`, `GitFacts.doing`, `GitFacts.conflicts`): `rebase-merge/`
  (`msgnum`, `end`), `rebase-apply/` (`rebasing`, `next`, `last`,
  `applying` for `git am`), `MERGE_HEAD`, `CHERRY_PICK_HEAD`,
  `REVERT_HEAD`, `BISECT_LOG`. **A linked worktree keeps them in the folder
  its `.git` file names.** **During a rebase `status` says
  `HEAD (no branch)`** (`parse_status_branch`), so `head-name` names the
  branch. Conflicts are `status`'s `UNMERGED` lines. Read only when git is
  read; the page test hands the real `git_facts` back in (topics/testing,
  "Under `served`").
  `test_a_rebase_says_how_far_and_keeps_its_branch`,
  `test_a_linked_worktree_is_read_in_its_own_git_folder`,
  `test_a_worktree_git_has_not_finished_with_says_so`.
- **A git call that failed is never drawn or remembered as an empty
  answer**: "no files" and "git did not answer" mean opposite things.
  `Files.root_of` once kept a timed-out empty root until a restart;
  `sniff_language` returns `None` for no answer and keeps only `""`.
  `GitFacts.failed`, `Worktree.failed` and `DiffReport.failed` say which;
  `reload_git` puts a failed directory back on the list, not over what it
  knew. **On the page too**: `loadFiles` keeps the names held while
  `failed` is set, as a failed listing closed the open file and a
  half-written comment. A `missing` answer (a timed-out `is_listed`) is
  never the file's text: its `+` would anchor to the real line 1. **With
  nothing read yet, say so** (`state.files.read`, `state.files.trouble`).
  `test_a_first_read_that_failed_says_so_and_is_not_the_file`,
  `test_a_listing_git_failed_on_keeps_the_open_file`,
  `test_a_file_read_git_failed_on_is_not_drawn_as_its_text`.
  - **An exception is a failure too, and one directory's stops no other**
    (#252): one raise in `git_facts_many`'s `pool.map` made `refresh`
    raise every tick, and `ls` crash. `git_facts_or_failed` turns it into
    `GitFacts(failed=True)` with `raised`; the `Store` logs it once a
    directory (`git_raised`), as it is asked every `GIT_MIN_INTERVAL`.
    `remote_url` never raises (topics/safety).
    `test_one_directory_that_raises_stops_no_other`.
  - **`pick_base` keeps a count only when git gave one**: a timed-out
    `%(ahead-behind)` kept as None in `Daemon.ranks` held the wrong base.
    Request threads share `ranks`, so read it with one `ranks.get(key)`:
    `key in ranks`, then `ranks[key]`, raised a KeyError between.
    `test_a_ranking_git_failed_on_is_not_kept`,
    `test_a_ranking_cleared_by_another_thread_is_not_an_error`.
- **`run` gives None both for "failed" and for "could not run"**, and
  outside a repository git fails, so empty alone is not failure. Tell them
  apart by a call that worked there, or `git_answers()` (`git --version`
  cannot fail in a working git), on the failure path only. **So
  `worktree_root` asks once, for every door** (#290): None is "git did not
  answer", "" is "not a repository", and a caller writes
  `failed = root is None`; `worktree_diff`, `whole_file_diff` and
  `git_facts` read a timed-out root as a clean worktree. `pick_base`
  returns `failed` when `for-each-ref` failed.
  `test_every_door_learns_from_the_root_which_kind_of_nothing_it_is`,
  `test_a_root_git_could_not_find_is_not_an_empty_worktree`,
  `test_a_base_git_could_not_look_for_is_not_no_base`,
  `test_a_git_that_does_not_answer_at_all_has_failed`.
  - **Exit 0 is no answer when git did not know the flag**: git before
    2.31 prints `--path-format=absolute` back. `git_facts` drops a line
    starting with `-` and makes a relative common directory absolute.
    `test_an_old_git_that_prints_path_format_back_keeps_the_repository`.
- **A repository with no commit yet is an answer, not a failure.**
  `has_head` is asked only when the log failed; the uncommitted half is
  measured against `empty_tree`, in `whole_file_diff` too.
  `test_a_repository_with_no_commit_yet_shows_what_is_staged`.
  - **So is a branch with no commit in common with its base** (an orphan,
    a shallow clone). `no_common_commit` asks `git merge-base`, which
    exits 1 for "none", so it passes `ok=(0, 1)`. **Never widen `run`'s
    default**: every other caller reads non-zero as failure. The committed
    half is left out and `DiffReport.unrelated` set; the branch's commits
    stay pickable, one at a shallow edge shown against the empty tree.
    `test_a_branch_with_no_commit_in_common_is_not_a_failure`,
    `test_a_branch_with_no_commit_in_common_says_so_and_not_that_git_failed`.
- **A commit the page names is used only if `branch_commits` listed it**:
  `?of=` is input, so `worktree_diff` hands git its own listed sha. One not
  listed comes back `gone`. **A log git failed on is not a commit gone**:
  it returns `failed`, and the page keeps its diff.
  `test_a_log_git_failed_on_is_not_a_commit_gone`,
  `test_a_commit_the_page_names_is_used_only_if_git_listed_it`.
  - **A base goes to git by its full name, `BaseChoice.ref`**: a branch
    named `--output=x` made `git diff` write to that file.
    `test_a_branch_named_like_an_option_never_reaches_git_as_one`.
  - **A revision is followed by `--`**, or a file named `HEAD` makes git
    refuse it every poll.
    `test_a_file_named_head_does_not_break_the_diff_tab`.
- **Every diff asks for `-U3` out loud** (`DIFF_CONTEXT`): the page reads
  fewer than three lines after a change as the file's end, and a reader's
  `diff.context` would break that.
  - **So is every other part of the output `parse_diff` reads**, in
    `git_diff`: `--src-prefix=a/ --dst-prefix=b/` (against
    `diff.mnemonicPrefix` and `diff.noprefix`), `-M` (against
    `diff.renames=copies`), `--no-textconv`.
    `test_the_readers_diff_settings_do_not_change_the_names`,
    `test_a_textconv_does_not_move_the_diffs_line_numbers`.
  - **A hunk ends when the lines its header counts have come**
    (`HUNK_COUNTS`): `diff.submodule=log` wrote headerless lines.
    `--submodule=short` pins git's default.
    `test_a_hunk_ends_when_the_lines_it_counts_have_come`,
    `test_a_submodule_is_its_own_file_and_its_log_is_not_lines_of_another`.
- **The row's count is the number of files the Files tab marks** (#550,
  #537): both parse `git status -z` in mode "all" through `git_status`;
  "normal" folds an untracked folder into "1 file" beside five dots. A
  failed reading is applied by `apply_git_facts` alone, never over what a
  session had, as `add_git_facts` (`ls`, `wait`) once did.
  `test_the_row_counts_the_changed_files_the_files_tab_marks`,
  `test_only_one_function_runs_git_status`.
  - **The tick never waits on git** (`GitReader`, #550): a slow
    `git status` in `reload_git` held every push. The daemon's `Store`
    reads behind (`GitReader(behind=True)`) and the next tick takes what
    came; a `busy` directory is not asked again. A `Store` built elsewhere,
    and a daemon ticked by hand (the `served` fixture, the picture tools:
    `daemon.store.git = ws.GitReader()`), reads at once, so `ls`, a fold
    test and a page test see facts on the same tick.
    `test_a_slow_git_holds_back_no_push`.
    - **What reads at once reads with the same timeout** (#592, #535):
      the tick's two seconds failed on an un-ignored virtualenv. So
      `git_status`, `git_facts` and `git_facts_many` take no timeout;
      they use `LIST_TIMEOUT`. A parameter is a value a caller can leave
      wrong, and two did.
      `test_git_status_has_the_time_a_full_listing_needs`.
