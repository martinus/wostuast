# The worktree tabs: git, the Files tab and the Review tab's diff

- **Work from the worktree root, not the agent's directory**
  (`worktree_root`): git prints root-relative paths from anywhere.
  - **Take only the newline off a path git prints, never `strip()`.**
    `/x/proj ` became `/x/proj`: nothing listed, or another repository.
    `worktree_root` and `git_facts` do `rstrip("\n")`.
    `test_a_worktree_whose_path_ends_in_a_space_is_that_worktree`.
- **The daemon's git takes no lock.** `status` and `diff` refresh the index
  under `.git/index.lock`: the agent's `git add` failed on it, and a git
  killed at its timeout (SIGKILL) left it, failing every `git add` and
  `git commit` until deleted. `run` sets `GIT_OPTIONAL_LOCKS=0` for every
  git, in one place so no new call forgets it. **`git diff` writes the index whatever
  `GIT_OPTIONAL_LOCKS` says** when a file's stat moved and its bytes did
  not (measured, git 2.43): `git_diff` also sets
  `diff.autoRefreshIndex=false`, with the same diff.
  `test_git_never_takes_the_index_lock_the_agent_needs` (it also shows a
  plain `git status` writes the index).
- **Inside a hunk, only a line's first character matters; only
  `diff --git` and `@@` start something new.** Removing `-- a comment`
  writes `--- a comment`, which as a header renamed the file and swallowed
  the hunk.
- **`run` reads bytes and decodes them itself; it never reads text.**
  `subprocess.run(text=True)` turned a lone CR (`b = 1\r c = 2`) into a
  line break before `parse_diff`, numbering later lines one too high
  against the Files tab. A CRLF file's diff lines end in `\r`, as the Files
  tab's do. `test_a_carriage_return_inside_a_line_stays_in_that_line`.
- **Split a diff on `\n`, never with `splitlines()`.** That also splits on
  form feed, vertical tab, `\x1c`-`\x1e` and `\u0085`, legal in source
  and unescaped by git (it quotes only paths): one form feed shifted every later line, and a review comment
  anchored to the wrong one.
- **A path out of a diff may be quoted, and must be unquoted**
  (`unquote_path`, the one place). `core.quotePath=false` covers only bytes
  above 0x80; a quote, backslash or control character is still escaped,
  `a/` inside the quotes, so `we"ird.txt` read as a rename and differed
  from the `ls-files -z` name: two anchors for one line. **A name holding
  a space ends in a TAB** on the `---` and `+++` lines (git's, unquoted):
  `parse_diff` takes one trailing tab off, or `foo bar.txt\t` is not the
  Files tab's `foo bar.txt`; a name truly ending in one is quoted.
  `test_a_name_with_a_space_is_the_name_the_files_tab_lists`. **A
  `diff --git` line that is not a rename splits in the middle**
  (`diff_header_paths`): a binary or mode change has no `---`/`+++` to fix
  the name, and the last ` b/` in `a/Plan b/logo.png b/Plan b/logo.png`
  made a rename to `logo.png`.
  `test_a_folder_ending_in_b_does_not_make_a_rename`.
  - **A file with no lines says it came or went only in its mode line.**
    An empty or binary new or deleted file has no `---`/`+++`, and
    `diff --git` names it twice, so `name_change` called it modified.
    `parse_diff` reads `new file mode` and `deleted file mode`;
    `drawDiffFile` says "A new, empty file." or "The file was empty.";
    "did not change" is for a mode change.
    `test_a_new_or_deleted_file_with_no_lines_is_added_or_deleted`,
    `test_a_new_or_deleted_file_with_no_lines_says_what_happened`.
  - **A path whose type changed is one entry, not two.** git writes a file
    that became a link (or back, or a submodule) as a deletion,
    `deleted file mode 100644`, then an addition, `new file mode
    120000` (`T` in `--name-status`). Two entries sharing one `data-key`
    marked both rows, sent clicks to the second block, gave
    `whole_file_diff` the first half, and put a file comment on both.
    `join_type_change` makes one entry, status `typechange`, `old_kind`
    and `new_kind` from `MODE_KINDS` ("file", "link", "submodule"), one
    hunk `@@ -1,N +1,M @@` (old lines out, new in), so the page adds only
    a label, `statusWord` ("FILE → LINK"), in a modified file's colour. A
    `+` on new lines with disk numbers, none on removed (`review.md`).
    **Only two adjacent halves of one path, of two kinds, are joined**:
    without `-B`, which `git_diff` does not pass, git writes nothing else
    so. A binary half has no lines; the other's are drawn. `git status`
    gives one `T` record, so the row count and the dots need nothing.
    `test_a_file_that_became_a_link_is_one_entry`,
    `test_a_type_change_is_joined_only_where_git_writes_one`,
    `test_a_file_that_became_a_link_is_one_row_one_block_and_one_comment`.
- **A cut goes back to the last newline, and the cap counts bytes.** A cut
  inside a `diff --git` line parsed as a nonexistent file, shown as a
  rename. `run` returns text, so a `len()` cap counts code points and
  passes four-byte characters at four times the size; `FILE_MAX_BYTES`
  counts bytes.
- **List every file, stat only the changed ones.** Tens of thousands of
  files, tens changed: statting all every poll is the mistake.
- **A wholly-ignored directory is walked by us, with a budget.** git's
  `--directory` collapses it to one entry, and dropping that hid
  `.oa-implement`, the agent's plan folder, the one ignored place a reader
  wants. `walk_ignored` lists it **only when what it holds fits in
  `IGNORED_MAX`**, not counting a folder already left out, and stops as
  soon as it knows: a build root of a hundred thousand objects costs 2,000
  reads, becomes one name in `Worktree.skipped`, and the plan beside it is
  listed. A folder comes back whole or as its own name, never half;
  `node_modules` stays one row. **The budget is an argument, not a default
  read at import**, or a test needs two thousand files. **A link to a
  directory is neither followed nor listed**: that gets round the budget
  and into a loop, and it is not a file.
  - **A walked file written since the session began is changed** (#492,
    `FileEntry.walked`, `Listing.written`, `written_since`): git says
    nothing of ignored files, so the plan had no dot, its folder never
    opened itself, and "changed only" hid it. Walked files are stat'ed;
    the route, not the listing, picks those since the **first session in
    the worktree** the daemon holds (`Serving.first_here`, #506), as one
    listing serves all its sessions and the asker's own start missed an
    earlier session's files. The reader chose this over the branch's first
    commit, a git call a listing. **An ignored file git names by itself is
    stat'ed too, up to `IGNORED_MAX` of them** (#506, `loose` in
    `worktree_files`): a folder that ignores itself (a `.gitignore` of
    `*`, `!.gitignore`) is no ignored folder to git, so git names each
    file, the walk never sees them, and only the `.gitignore` was marked.
    The cap is for a build's objects beside their sources.
    `test_a_folder_that_ignores_itself_counts_what_was_written_in_it`,
    `test_a_file_written_in_an_ignored_folder_since_the_worktree_began_is_changed`.
- **`skipped` is not in the listing's tag**, which hashes the names, and a
  build root adds none: the page rebuilds the tree when the names **or**
  `skipped` move. `buildTree(names, skipped)` makes an empty folder for
  each, since nothing above creates it and an unseen folder is silence.
  Its row carries `.toobig` and does not open (onto nothing reads as
  broken), and its title promises nothing: no name in it is sent.
- **One listing per worktree, and the page holds the names.** `Files` keeps
  it for `LIST_FRESH`, serving a stale one while re-reading behind. Names
  go with a tag, and an unmoved listing answers without them (0.2 KB, not
  1733 KB). So **the order the names are sent in must depend only on which
  files exist**: `in_order` is pinned-then-name, or a changed tier moves
  the tag every save. The reader's order is the page's, in `dirFiles`.
  - **A listing held is handed over without the gate.** The read behind
    holds the root's gate for up to four git calls at `LIST_TIMEOUT`, and
    taking the gate first made a poll wait seconds holding an HTTP thread
    (with `ls-files` slowed). `Files.of` reads `held` under `lock`, takes
    the gate only when nothing is held, then looks again, so two first
    asks read git once.
    `test_a_stale_listing_does_not_wait_for_the_read_behind_it` (git held
    by an event, not a sleep), `test_two_first_asks_read_git_once`.
  - **The untracked names are `status`'s `??` records, and the three calls
    run at once** (#293): `ls-files --others --exclude-standard` beside
    `status --untracked-files=all` walked the worktree twice for the same
    names (measured equal with a rename, a nested repository, and names
    with a space, tab or quote). `status_names` gives changed and
    untracked; `worktree_files` runs it with the tracked and ignored
    listings in a `ThreadPoolExecutor` (138 ms in sequence on fifty
    thousand files, about 56 at once). `failed` is set if any gives None.
    `test_the_untracked_names_are_the_ones_status_gives`.
- **An icon is measured against its box, not eyeballed.** `putIcon` draws
  in a `0 0 14 14` viewBox and an `svg` clips to it, so a 1.2-wide stroke
  must end by 13.4; at 13.5 an icon lost its edge.
  `test_every_icon_fits_inside_its_box` measures every `ICONS` entry with
  the page's CSS. **A shape that is not closed looks cut whether or not
  anything cut it** (`dirOpen`'s unjoined lid and floor). Draw it, look at
  it at 13 px, then measure it.
- **What changed is bold, and the funnel shows it alone** (#492,
  `onlyChanged`, `putOnlyChanged`, `.onlychanged`): a dot was easy to miss
  in a long tree. Bold is the Files tab's tree only (`.filelist.files`,
  not the transcript's map, which wears the same rows). The funnel, after
  the find box, keeps the folders in `state.files.marked` and files in
  `state.files.changed` in `treeRows`, and is in the list's redraw key, or
  a click draws nothing. It is per browser, in `localStorage`, like the
  folds; `split` rebuilds the slot on every switch, so `drawFiles` puts it
  back. `test_what_changed_is_bold_and_the_funnel_shows_it_alone`.
- **One file of a diff stands apart from the next** (#525, `.dfile`): 28 px
  between cards, the header (`.dfile > .name`, `.openfile` beside it) on
  `--raised`, the path bold at 14 px; on the code's `--sheet`, close
  together, one file ran into the next. Tool diffs in the transcript wear
  the card with their own margin (`.dfile.tooldiff`). **This reverses the
  older rule** that the header stands on the code's ground, lest it "read
  as a bar rather than as the top of the file": the reader asked for it to
  stand out and chose the raised ground from pictures in both schemes.
  `test_one_file_stands_apart_from_the_next`.
- **A binary file is its hex on the Files tab** (#487, `hex_dump`,
  `HEX_MAX_BYTES`, `FileText.hex`, `state.files.hex`, `.code.hexdump`):
  the first 64 KB as `xxd` draws them, a dot for each byte that is not
  printable ASCII, so nothing in it acts on a page or terminal. The answer
  stays `binary`: `readLoose` reads untracked files by that route, and the
  Review tab still says "binary". Rows with no colour and no `+`: there is
  no text to comment on. `test_a_binary_file_is_read_as_hex_for_the_files_tab`,
  `test_a_binary_file_is_drawn_as_hex`.
  - **A hex row is as wide as the pane has room for** (`hexWide`, #524):
    16 bytes made a narrow column. The daemon still sends `xxd`'s 16; the
    page, which alone knows the pane's width, joins two or four rows when
    32 or 64 fit without a sideways scroll in the code face (16k bytes are
    56k + 11 characters, the gutter about 110 px). The short last row is
    padded to line up; the note after is not a row. Called in `drawFiles`.
    `test_a_hex_row_is_as_wide_as_the_pane_has_room_for`.
- **A folder row carries no triangle**: it shifted a folder's name right of
  a file's at the same depth, lining a deeper file up with its folder,
  which a tree must never do. `ICONS.dirOpen` says it instead.
- **The list marks where the reader last went, `state.files.at`, not the
  open file**, or a click on a path part above a file already on screen
  did nothing visible and read as broken. `at` is in the list's redraw
  key, or the mark does not move.
- **A path clipped at its start is a bidi trap: never clip one without
  `unicode-bidi: plaintext`.** `direction: rtl` puts the ellipsis in front
  but moves a leading neutral character to the end (`.gitignore` drew as
  `gitignore.`); `plaintext` takes the first strong character's direction.
- **The tree holds the tiers.** `dirFiles` orders a directory's files:
  named, changed newest first, the rest. **A directory holding a change
  does not open itself; it counts them** (#517, `openDirs`,
  `dirsWithChanges`, `.nchanged`): the reader asked for the tree shut, as
  a busy agent opened all of it. `state.files.marked` maps a folder to its
  changed files at any depth; the count stands at its right edge, where a
  file has its dot (`:not(.dir)`). **The funnel still opens them**: it
  asks for the changes alone. What the reader opened or shut by hand
  (`state.dirs`) wins over both.
  `test_a_directory_holding_a_change_stays_shut_and_counts_them`,
  `test_a_directory_stays_as_the_hand_left_it`.
- **Typing is "go to file", not a filter.** The tree never moves: where a
  file sits is half of what you know of it. `drawGoTo` lists files *and*
  directories under the box, `pick`-ranked; a pick opens and reveals one.
  The list lives in `.findslot` so `split`'s children keep their places,
  and closing it clears its redraw key, or the same query again draws
  nothing.
- **A file is found by its name; the path is the fallback, and it must be
  tight.** `findPath` matches the basename, then the whole path only when
  the matched letters span at most `TIGHT` times the query: the whole path
  outright spread "MetricsBuilder" over four directories and missed the
  file. A slash in the query means the path. `findPath` forgives one
  letter of a five-plus query; `fuzzy` forgives none by default, as the
  session filter runs through it and a short haystack cannot afford it.
  - **A mark is a place in the name as written, and a whole character.**
    `fuzzy` searches the lower-cased name, and "İ" lower-cases to two code
    units, so `notes` lit "btes." in `İstanbul-notes.md`. `unlowered` maps
    places back only when lengths differ, so an ordinary name pays
    nothing. `putName` takes a whole code point, not `text[index]`, half
    an emoji. `test_go_to_marks_the_letters_it_matched_in_any_script`.
- **The tree's window is as tall as the list, and a resize fills it.** A
  fixed `ROWS_SHOWN` (80 rows) left space under the last row on a tall or
  zoomed-out screen. `fillList` takes the rows the list shows plus eight
  at each end, never fewer than `ROWS_SHOWN`; a taller window sends no
  scroll event, so a `ResizeObserver` calls `fillList` too.
  `test_a_tall_file_tree_is_drawn_to_its_foot`.
- **Search every name, or say you cannot.** The first 5000 of 52,799 found
  16 files and missed a thousand: a wrong answer that looks right.
- **What git has started and not finished is read off its files, in the
  worktree's own git folder** (#357, `worktree_doing`, `own_git_dir`,
  `GitFacts.doing`, `GitFacts.conflicts`), at no git call. Measured on git
  2.43: a rebase leaves `rebase-merge/` (`msgnum`, `end`) or, with
  `--apply`, `rebase-apply/` (`rebasing`, `next`, `last`); `git am` that
  folder with `applying`; a merge `MERGE_HEAD`, a cherry-pick
  `CHERRY_PICK_HEAD`, a revert `REVERT_HEAD`, a bisect `BISECT_LOG`. **A
  linked worktree keeps them in its own folder**, named by its `.git` file
  (`gitdir: …/.git/worktrees/<name>`), not the repository's. **During a
  rebase `status` says `HEAD (no
  branch)`**, which `parse_status_branch` rightly reads as no branch, and
  the row hid its second line: `head-name` names the branch. Conflicts are
  `status`'s `UNMERGED` lines. **Read only when git is read**, after an
  event that can touch the tree: a rebase begun by hand shows after the
  agent's next one. Page tests stub git (`stub_git`), so the page's test
  passes the real `git_facts`.
  `test_a_rebase_says_how_far_and_keeps_its_branch`,
  `test_a_linked_worktree_is_read_in_its_own_git_folder`,
  `test_a_worktree_git_has_not_finished_with_says_so`.
- **A git call that failed must not render as an empty answer**: "no
  files" and "git did not answer" mean opposite things. **Nor may a failure
  be remembered as one**: `Files.root_of` kept a timed-out
  `git rev-parse`'s empty string, unreadable until a restart. `file` too:
  `sniff_language` returns `None` for "no answer" and `""` for "nothing we
  paint", and keeps only the second. `GitFacts.failed`, `Worktree.failed`
  and `DiffReport.failed` say which; `reload_git` puts a failed directory
  back on the list, not over what it knew. **On the page too**:
  `loadFiles` took a failed listing's names as fact and closed the open
  file, its place and a half-written comment; the names held stand while
  `failed` is set, and only a listing that did not fail says a file went.
  A `missing` answer for the open file (also a timed-out `is_listed`'s) is
  never its text: as line 1, its `+` anchors a comment to the real line 1.
  **With nothing read yet it is said** (`state.files.read`,
  `state.files.trouble`), or a refused first read draws an empty file and
  a failed fetch leaves the last file under the new name.
  `test_a_first_read_that_failed_says_so_and_is_not_the_file`,
  `test_a_listing_git_failed_on_keeps_the_open_file`,
  `test_a_file_read_git_failed_on_is_not_drawn_as_its_text`.
  - **An exception is a failure too, and one directory's stops no other**
    (#252). `git_facts` raised for one directory (`remote_url` on a config
    `configparser` could not read), took the batch out of `pool.map` in
    `git_facts_many`, and `refresh` raised every tick before replacing the
    rows: no session's row moved or appeared, and `ls` crashed.
    `git_facts_or_failed` makes it `GitFacts(failed=True)`, the error in
    `raised`, asked again after the cool-down. The `Store` logs it once a
    directory (`git_raised`), since a failure is asked every
    `GIT_MIN_INTERVAL`. The first guard: `remote_url` never raises
    (`safety.md`). `test_one_directory_that_raises_stops_no_other`.
  - **`pick_base` keeps a count only when git gave one.** A timed-out
    `%(ahead-behind)` kept in `Daemon.ranks` as None held the fallback base
    (`main` for a branch cut from `release`) until HEAD or a ref moved.
    Request threads share `ranks`: `key in ranks` then `ranks[key]` raised
    KeyError (a 500) when another thread cleared it between; one
    `ranks.get(key)` has no gap. `test_a_ranking_git_failed_on_is_not_kept`,
    `test_a_ranking_cleared_by_another_thread_is_not_an_error`.
- **`run` gives None for "the command failed" and for "it could not run".**
  Outside a repository git *fails*, so empty alone is not failure. Tell
  them apart by a call that already worked there (`git_facts` trusts
  `rev-parse`), or `git_answers()`, which asks `git --version`: it cannot
  fail in a working git and stalls on a stalled machine. Only in the
  failure path, so a repository never pays. **Every door that reads an
  empty answer asks**: doors that did not (`worktree_diff`,
  `whole_file_diff`, `git_facts`) read a timed-out `--show-toplevel` as a
  clean worktree, and wrote empty facts over known ones. **So
  `worktree_root` asks it, once, for every door** (#290): None is "git did
  not answer", "" is "not a repository", and a caller writes
  `failed = root is None`. `git_facts` still asks for itself, from
  `rev-parse` and `status` together. `pick_base` returns whether
  `for-each-ref` failed (`failed`), as the page states "no such names" as
  a fact. `test_every_door_learns_from_the_root_which_kind_of_nothing_it_is`,
  `test_a_root_git_could_not_find_is_not_an_empty_worktree`,
  `test_a_base_git_could_not_look_for_is_not_no_base`,
  `test_a_git_that_does_not_answer_at_all_has_failed`.
  - **An exit status of 0 is not an answer either, when git did not know
    the flag**: `rev-parse` prints it back and exits 0. git before 2.31
    lacks `--path-format=absolute`, so rows read
    `--path-format=absolute/<dir>` and no remote was found. `git_facts`
    drops a line starting with `-`, and makes a relative common directory
    absolute against `cwd`.
    `test_an_old_git_that_prints_path_format_back_keeps_the_repository`.
- **A repository with no commit yet is an answer, not a failure.**
  `git init` leaves no HEAD, so `git log HEAD` and `git diff HEAD` fail:
  the tab said git did not answer, and staged files showed nowhere.
  `has_head` is asked only when the log failed; the uncommitted half is
  then measured against `empty_tree`, in `whole_file_diff` too.
  `test_a_repository_with_no_commit_yet_shows_what_is_staged`.
  - **So is a branch with no commit in common with its base** (an orphan
    `gh-pages`, a shallow clone cut before the branch):
    `git diff base...HEAD` fails with "no merge base", and the tab said git
    did not answer, for ever. `no_common_commit` asks `git merge-base`,
    which exits 1 for "none" and 128 for failure; `run` gives None for
    both, so it passes `ok=(0, 1)`. **Never widen `run`'s default**: every
    other caller reads non-zero as failure. The committed half is left out,
    `DiffReport.unrelated` set, and a note says why, as with no base. The
    branch's commits (`base..HEAD`) are all the clone holds, each still
    pickable; one at a shallow edge has no parent there and is shown
    against the empty tree, as `git show` does.
    `test_a_branch_with_no_commit_in_common_is_not_a_failure`,
    `test_a_branch_with_no_commit_in_common_says_so_and_not_that_git_failed`.
- **The Diff tab says what each half is a diff of, in words**:
  `origin/main...HEAD` and "not committed yet" left nobody sure whether it
  showed the last commit, the branch or the worktree. `DiffSection.about`
  carries the sentence, built by the daemon with the base named, drawn
  under the heading and as the list's `title`. **When there is no base the
  committed half is missing**, which looked like a tab with less in it:
  the pane says so, and names what git was asked for.
- **A commit the page names is used only if `branch_commits` listed it.**
  The sha in `?of=` is input, so `worktree_diff` hands git its own listed
  one, never the string sent. One not listed (amended or rebased) comes
  back `gone` with all changes, and the pane says why. **A log git failed
  on is not a commit gone**, or the pane says "probably amended or rebased
  away" and drops the pick: it returns `failed` with no section, and the
  page keeps its diff (`test_a_log_git_failed_on_is_not_a_commit_gone`).
  `test_a_commit_the_page_names_is_used_only_if_git_listed_it` sends
  `--output=` and `HEAD~1` and asserts neither reaches an argv.
  - **A base goes to git by its full name, `BaseChoice.ref`, starting
    `refs/`.** A listed name is not safe: git takes
    `update-ref refs/heads/--output=x`, `pick_base` offered `--output=x`,
    and `git diff --output=x...HEAD` wrote the diff to that file (the name
    may hold a `/`). The picker and headings show the short name.
    `test_a_branch_named_like_an_option_never_reaches_git_as_one`.
  - **A revision is followed by `--`**, or a file named `HEAD` at the top,
    even untracked, makes git refuse `HEAD` as "both revision and
    filename" and fails the tab every poll. git never checks a range
    (`a..b`) so; a test holds the single names, `HEAD` and the sha
    `git show` gets. `test_a_file_named_head_does_not_break_the_diff_tab`.
- **One commit's comments go through `since`, as the committed half's go
  through the uncommitted one**: a commit's new side is the commit, not
  the disk, so a comment on `print(2)` would anchor to line 2 when fifty
  lines stand above it. `since` is `git diff
  <sha> -- <its files>` and `inWorktree` reads it when a commit is shown;
  only its own files, as a whole repository's diff to disk costs every
  later commit.
- **The picker is built once with the pane, and refilled only when the
  commits change** (`fresh(bar, "key", …)`): a `select` whose options are
  replaced closes, and the tab polls every five seconds. Picking and the
  column switch rebuild the diff, so both refuse, and say so, while a
  comment box is open (`busyWriting`): a rebuild takes what is typed, and
  a silent no-op reads as broken. **Between older and newer, "5 / 9"**
  (`.stepat`), oldest first, so the first commit is 1. The three are one control
  (`.choice.stepper`): two arrows with words in `title` and `aria-label`,
  the count between with no button; the reader chose it from pictures
  over two word buttons, which matched nothing on the bar. **Another
  commit is read from its top**: `drawDiff` keeps the place only when
  `scroll.dataset.of` says the same diff is drawn again, else nought, as a
  pane refilled in one task keeps its offset. **The same diff is the same
  session's**: `of` is "" for all changes everywhere, so the key is
  `state.chosen` and `of`.
  `test_the_older_and_newer_buttons_step_through_the_commits`,
  `test_another_commit_is_read_from_its_top`,
  `test_another_sessions_diff_is_read_from_its_top`.
- **The pane reads in the tree's order, not git's** (`treeOrder`, folders
  first at every level, for list and pane): git's put `README.md` above
  `src/a.py` in the pane and below it in the tree.
- **The file clicked in the tree keeps the mark while it is on screen**
  (`scroll.picked`): `markDiffFile` marks the block under the pane's top,
  which a diff's last file never reaches, so its click marked the file
  above.
- **A diff is painted one side of one hunk at a time, and the word marks go
  back on after.** A hunk's side reads in order, the whole file is not at
  hand, and a lone row gets every multi-line string wrong. Painting
  replaces the cell, so `paintDiff` calls `markWords` again from
  `cell.words`, or the marks vanish with the colour; offline only
  `test_the_diff_is_painted_and_keeps_its_word_marks` notices.
  - **A word is split by code point, not by UTF-16 unit** (`WORD` has the
    `u` flag), or a changed emoji is marked half and draws two broken
    glyphs. `test_an_emoji_that_changed_is_marked_whole`.
- **Lines hidden between changes come from the same diff with the whole
  file as context, never from reading the file.** `whole_file_diff` is the
  section's own `git diff` with `-U1000000` and the path as a literal
  pathspec after `--`, from three fixed argument sets, so the lines are
  the half's side: HEAD for the branch's work, the commit for one commit,
  the disk for what is uncommitted. Read from disk, the committed half (HEAD's) got the
  disk's lines. A commit is used only when `branch_commits` lists it.
  `test_a_whole_file_is_every_line_of_the_side_the_half_shows`.
- **What the reader revealed is kept as line numbers, and the whole file
  against the hunks it came with.** `state.diffMore` holds `[from, to]`
  runs by `moreKey` (what is shown, the half, the path), as one commit's
  line 40 is not another's. `state.diffWhole` keeps each whole file with
  its diff's `hunkSig`; `withMore` drops it when the hunks move, or a save
  puts old lines between new changes.
  `test_shown_lines_come_again_from_the_file_as_it_now_is`. **Another base
  keeps them** (`keepBase`): no base moves HEAD's or the disk's lines, and
  clearing would close what was opened in the uncommitted half. **A whole
  file that failed, or came back cut, is kept against draws but not
  against a click** (`revealLines` lets it go), or each later click on a
  band shows nothing.
  `test_a_whole_file_that_failed_is_asked_for_again_on_a_click`.
- **Every diff asks git for `-U3` out loud** (`DIFF_CONTEXT`, the number on
  both sides): the page reads under three lines after the last change as
  the file's end, and a reader's `diff.context` would hide "more below" on
  every file.
  - **So is every other part of the output `parse_diff` reads**, in
    `git_diff`, as a reader's config changes each: `diff.mnemonicPrefix`
    (`c/`, `w/`) made every file a rename and `diff.noprefix` lost
    `b/c.py`'s folder (`--src-prefix=a/ --dst-prefix=b/`);
    `diff.renames=copies` made a copy a rename (`-M`); a `textconv` in
    `.gitattributes` gave lines the Files tab does not read
    (`--no-textconv`). `test_the_readers_diff_settings_do_not_change_the_names`,
    `test_a_textconv_does_not_move_the_diffs_line_numbers`.
  - **A hunk ends when the lines its header counts have come**
    (`HUNK_COUNTS`), whatever git writes next: `diff.submodule=log` wrote
    headerless `  > message` lines, read as the previous file's context.
    `--submodule=short` pins git's default, a submodule as its own file.
    `test_a_hunk_ends_when_the_lines_it_counts_have_come`,
    `test_a_submodule_is_its_own_file_and_its_log_is_not_lines_of_another`.
- **A diff stands on `--sheet`, not on `--code`, and it is white in the
  light.** The file header stands on `--raised` (#525). On
  `#eceae3`, the code ground, an unchanged line had contrast 4.29 (body
  text needs 4.5) and the card was a brown box. `--code` stays for a code
  block in prose. `test_a_diff_in_the_light_is_on_white_and_reads`.
- **A commit picked shows its whole message, and only that commit's is
  asked for**: `DiffReport.body`, `git show -s --format=%b` for the commit
  shown, not a field of every `Commit` sent every poll. **A paragraph's
  lines are joined (`reflow`) and the window wraps them**: a body wrapped
  by hand near 72 columns broke there in a box 80 wide whatever the
  window. A list item, an indented line and a trailer (`Refs: OA-1`) keep
  their line, as there the break is the meaning (`pre-wrap`, fixed face).
  The heading goes through `linkTickets`.
  `test_a_commit_message_wraps_at_the_window_and_links_its_tickets`.
  **The title is a box of its own** (`.subject`, #445): in the grid
  `.diffhead.commit`, the pieces `linkTickets` cut became grid items, and
  a grid item drops its leading space ("OA-123this"); so does any text put
  straight into a grid or flex box.
  `test_a_ticket_at_the_start_of_a_subject_keeps_the_space_after_it`.
  **It is drawn as Markdown, and the text is one click away**
  (`putMessage`, `MESSAGE_KEY`): agents write Markdown, and the reader
  asked for both. A line `reflow` keeps is a hard break in the Markdown
  too, or a trailer joins the line above. The click refills only the
  message, as a rebuild takes a half-written comment. Without `marked` it
  is the text, with no control.
  - **The control is the Files tab's, and stands where that one does**
    (`putReadAs`): one button, "txt", lit while the text shows
    (`paintToggle`), at the right end of the line naming what is read. The
    reader asked for one click and for the two to look and feel the same,
    and chose the place. `.diffhead.commit` is a grid so the control
    shares the subject's line while the subject stays the head's first
    child, which the tests read.
  `test_a_commit_message_is_markdown_and_its_text_is_one_click_away`,
  `test_a_document_is_read_as_markdown_or_text_from_the_right_of_its_path`.
- **The pickers say what they hold, in the narrow face.** "all changes"
  counts the branch's own commits, not the default branch's recent ones.
  "against" stands beside the branch picker, not in each option, and that
  picker does not shrink: a branch name must read whole ("against ma"
  did not), where a cut commit subject is still known.
  `test_the_pickers_say_how_many_commits_and_stand_apart_from_against`.
- **Two columns wrap; one column scrolls unless the reader wraps it.** Two
  halves cannot share a sideways scrollbar, and two drift apart, so
  `.dlines.sides` hides the overflow and wraps. The `+` is on the new half
  only (a comment is about the file as it is); a side with no line is
  hatched, not closed up, so the columns stay level.
  - **The tint is the half's, never the row's** (#444): `pairRow` names a
    row by kind, so a line with no counterpart made an `added` or
    `removed` row whose tint crossed the hatched half too, louder than a
    change. `.dline.pair.added` and `.removed` draw no
    ground. `test_a_line_with_no_counterpart_tints_its_own_half_only`.
  - **A comment stands under the half its `+` is on** (#446,
    `.dlines.sides > .onLine`), not as a note on the line that went.
    `test_in_two_columns_a_comment_stands_under_the_new_half`.
  - **The line's text is a box of its own** (`.dline .dtext`, an inline
    block; a flex item when wrapped), or a tab is measured from the row's
    start and a line indented by one tab stands one space after the `+`. A wrapped line's rest then stands under its
    text, on the Files tab too.
  - **One column is a grid of one `auto` track** (`.dlines:not(.sides)`):
    rows are `min-width: max-content`, and a block row as wide as the pane
    cut a short line's colour at its edge when scrolled;
    `minmax(100%, max-content)` never grows past the pane. A comment stays
    readable because `.onLine` is sticky and 680 px at most.
  - **How the diff is drawn is in the settings menu** (`sidebar.md`,
    `putSettings`): columns, tab width, long lines; the column switch
    alone, in words, cramped the Review bar on a notebook. The bar holds
    three buttons, columns, whitespace and the code's width, each lit while
    on (`putQuick`) and fitting at 1366 px; they set the menu's settings.
  - **Whitespace is two settings, and only one asks git** (#449).
    `diff_space` "hide" is `git diff -w` (`SPACE_ARGS`), sent as
    `space=hide` on the diff *and* the whole-file route, as the lines
    between changes must come from the same diff; `Daemon.diffs` keys the
    branch's answer by it, or the other choice's came back. A change asks
    at once (`respace` drops the tag and the whole files). `space_marks`
    asks nobody: `markSpaces` always wraps each tab and each line-end space
    in `.ws`, and `data-marks` on the root shows a faint mark, as the tab
    width is the cascade's. **It runs wherever a line's text is drawn or
    painted**, after the word marks (`unifiedRow`, `pairRow`, `paintDiff`,
    `paintLines`, `paintSlices`), since a paint replaces the cell. **A tab
    is never wrapped**: the mark is an empty `.ws.tabmark` before it, as a
    tab in its own span drew three columns of four. **The mark is not
    `.tab`**: that rule's 24 px of padding hid in a four-column stop of
    Plex Mono (30 px) but ran each first tab to the next stop at a width of
    2 or the narrow width (`code_width`, 24 px for four).
    `test_a_tab_in_a_diff_line_is_a_whole_tab_from_where_the_text_starts`
    asserts a width of 2; tests wait for the mark `attached`, as an empty
    mark is not visible.
    `test_a_change_of_whitespace_alone_is_left_out_when_asked`,
    `test_a_change_of_whitespace_alone_goes_and_comes_back`,
    `test_a_tab_and_spaces_at_the_end_are_marked_when_asked`.
  - **A file opens on the Files tab from its header** (`openInFiles`,
    `.openfile`, #449), beside it, not in it: a button holds no other.
    `.dfile:has(> .openfile)` is a grid so the button shares the header's
    row and sticks with it. `test_a_file_in_the_diff_opens_on_the_files_tab`.
  `test_scrolled_sideways_every_line_keeps_its_colour`,
  `test_a_long_line_wraps_under_its_own_text_in_one_column`,
  `test_the_settings_say_what_is_chosen_and_change_it_in_place`.
- **The row's count is the number of files the Files tab marks** (#550):
  both read `git status` through one parser, `git_status`, in mode "all",
  one entry a file. "normal" folds an untracked folder into one ("1 file"
  beside five dots); it was used for the tick's two-second timeout
  (measured: 50,000 untracked files, 4 ms "normal", 55 "all"). Before #537
  the row also parsed without `-z`, counting a rename as one. A failed
  reading is applied by `apply_git_facts` alone, never over what a session
  had: `add_git_facts` (for `ls` and `wait`) wrote it, `reload_git` did
  not. `test_the_row_counts_the_changed_files_the_files_tab_marks`,
  `test_only_one_function_runs_git_status`.
  - **The tick never waits on git** (`GitReader`, #550): `git_facts_many`
    in the tick (`reload_git`) let a slow `git status` hold every push and
    event up to its timeout. The daemon's `Store` reads behind
    (`GitReader(behind=True)`, `LIST_TIMEOUT`) and the next tick takes
    what came; the cool-down starts at the ask, and a directory still read
    (`busy`) is not asked again. A `Store` built elsewhere reads at once, so
    `ls` and a fold test see facts on the same tick. **So does a daemon
    ticked by hand**: the `served` fixture and the picture tools call
    `tick` with no loop, so they set `daemon.store.git = ws.GitReader()`,
    or `test_a_worktree_git_has_not_finished_with_says_so` waits for a row
    no tick draws and the tour draws rows with no branch.
    `test_a_slow_git_holds_back_no_push`.
    - **What reads at once reads with the same timeout** (#592, #535):
      `add_git_facts` (`ls`, `wait`) and a `GitReader` without `behind`
      gave the tick's two seconds to a status listing every untracked file,
      so an un-ignored virtualenv failed and `ls` showed no branch. **So
      `git_status` takes no timeout**: it uses `LIST_TIMEOUT`, and
      `git_facts` and `git_facts_many` take none either. A parameter is a
      value each caller can leave wrong, and two did.
      `test_git_status_has_the_time_a_full_listing_needs`.
- **A split tab keeps its two columns and redraws one at a time**:
  `split()` builds them once, `fresh()` decides from the DOM what changed.
  One key over the whole tab re-rendered the file being read every two
  seconds.
  - **The Diff pane redraws one file at a time.** Past `fresh`, a
    `drawDiff` that rebuilt every file drew the one being read plain on
    any save and repainted it behind `hljsReady` and a timer: it lost
    colour and word marks, and jumped. The pane is built in a fragment, a
    file whose `blockSig` is unchanged keeps its block, and `settle` places
    blocks without moving a kept one (out and back in lost its sideways
    scroll); `readerAt` holds the top block where it stood when a file
    above grew. **`blockSig` is everything the block is drawn from that
    `diffKey` does not cover**: the file's diff, its open, more and whole
    state, `BIG_LINES` (two tests move it), the half, the session, the
    columns, and for a commit's block its file in the diff after
    (`laterFile`), as a comment there sits where the line is on disk
    (`inWorktree`) and a kept block anchored one off. Comments are not in
    it: `redrawCode` empties the key, and `again` draws all. **A box built
    apart from the page is not in `document`**: `putReview` looked only
    there for an open `.commentbox`, so a line in both sections got two;
    it also asks the root it is built under.
    `test_a_save_to_another_file_leaves_the_one_being_read_alone`,
    `test_a_file_that_grows_above_leaves_the_reader_where_they_were`,
    `test_one_line_in_both_sections_opens_one_comment_box`,
    `test_a_committed_line_follows_lines_added_above_it_since`.
- **`.listnote` is one clipped line.** Anything with height goes in the
  `sidefoot` slot: a button in the count strip could not be clicked.
- **`drawLooseFile` builds a synthetic file object; everything
  `fillDiffFile` reads must be in it.** Without `path`, every untracked
  file's comments anchored to `undefined`.
- **An untracked file's text is read by `readLoose`, and only text is its
  text.** A failed fetch drew "This file is empty.", a `missing` answer (a
  timed-out `is_listed`) one added line with a `+`, and both stuck, as a
  click on the picked name did nothing; back on a session, the pick
  returned without its text, "reading…" for ever. An unread file says why,
  and `loadDiff` asks every poll until it is read; one that went leaves
  `untracked` and is let go. **`loadDiff` lets it go, where the answer is
  taken** (#542): in `drawDiff` it was a write in a draw no test reached,
  unseen by the draw guard. `loosePick` keeps a draw from showing a pick
  the diff on screen does not list.
  `test_an_untracked_file_picked_and_then_added_lets_go_of_the_pick`,
  `test_an_untracked_file_is_read_again_when_its_session_comes_back`,
  `test_an_untracked_file_that_could_not_be_read_says_so`,
  `test_an_untracked_file_git_would_not_list_is_not_its_one_line`.
