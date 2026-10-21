# The Files tab

The listing and the tree, find, icons, hex, and how a file is drawn.

- **List every file; stat only the changed ones.** Tens of thousands of
  files, tens changed: statting all of them every poll is the mistake.
- **Another repository the agent worked in is a place of its own** (#616,
  `note_dirs`, `Session.dirs`, `Serving.places_for`, `place_of`,
  `#placepick`): an agent that worked in two repositories showed one, as
  the Files and Review tabs read the worktree it started in. The fold keeps
  the folders the agent stood in (`cwd`) or touched a file in (an absolute
  path in a call's input), the latest last, `DIRS_HELD` of them. Git turns
  them into repositories only when the page asks `places`, as the fold does
  no I/O; a folder that is in no repository is none. The picker beside the
  tabs shows when there are two, and every Files and Review route reads
  it through `apiUrl` (`PLACED`).
  - **The own place is the repository the agent stands in, else the one it
    started in** (`own_place`): the tabs read `cwd` before #616, and a `cd`
    out of every repository left them empty under a picker that named the
    own one.
  - **A pick drops what was held and draws at once** (`pickPlace`), as a
    change of session does: the old listing stood under the new name until
    the answer came. **An answer asked under another place is dropped**
    (`ask`): one in flight put the other repository's diff under the own
    one's name, with a `+` on its lines. **A listing is kept under its
    place** (`listingRoot`), or another repository's names stood in every
    session of the own worktree.
  - **A place the daemon no longer lists is left for the own one**
    (`askPlaces`): after `DIRS_HELD` other folders it is refused, and every
    route said 404 under a picker that had hidden itself.
  - **A folder in no repository is asked about once a minute**
    (`Files.root_kept`, `NO_REPO_KEPT`): each request that named a place
    asked git about all of them, up to `DIRS_HELD` processes a poll.
  `test_another_repository_the_agent_worked_in_is_a_place_of_its_own`,
  `test_the_folders_an_agent_worked_in_are_kept_the_latest_last`,
  `test_another_repository_the_agent_worked_in_is_one_pick_away`.
- **A wholly-ignored directory is walked by us, within a budget**
  (`walk_ignored`): git's `--directory` makes it one entry, and dropping
  that hid the agent's plan folder. It is listed **only when it fits in
  `IGNORED_MAX`**, else it becomes one name in `Worktree.skipped`, never
  half. The walk stops as soon as it knows. **The budget is an argument,
  not a default read at import**, or a test needs two thousand files.
  **A link to a directory is neither followed nor listed**: it escapes the
  budget and loops.
  - **A walked file written since the session began is changed** (#492,
    `FileEntry.walked`, `Listing.written`, `written_since`): git says
    nothing of ignored files, so the plan had no dot. "Since" is the
    **first session in the worktree** the daemon holds
    (`Serving.first_here`, #506), as one listing serves all its sessions.
    **An ignored file git names by itself is stat'ed too, up to
    `IGNORED_MAX`** (`loose` in `worktree_files`): a folder whose
    `.gitignore` is `*`, `!.gitignore` is no ignored folder to git, so
    the walk never sees it.
    `test_a_folder_that_ignores_itself_counts_what_was_written_in_it`,
    `test_a_file_written_in_an_ignored_folder_since_the_worktree_began_is_changed`.
- **`skipped` is not in the listing's tag**, so the page rebuilds the tree
  when the names **or** `skipped` move. `buildTree(names, skipped)` makes
  an empty folder for each, as an unseen folder is silence; its row is
  `.toobig`, does not open, and its title promises nothing.
- **One listing per worktree, and the page holds the names.** `Files`
  keeps it for `LIST_FRESH` and serves a stale one while re-reading
  behind. An unmoved listing answers with its tag alone (0.2 KB, not
  1733 KB). So **the order the names are sent in depends only on which
  files exist** (`in_order`), or the tag moves every save; the reader's
  order is the page's, in `dirFiles`.
  - **A listing held is handed over without the gate**: the read behind
    holds it for up to four git calls. `Files.of` reads `held` under
    `lock`, takes the gate only when nothing is held, then looks again.
    `test_a_stale_listing_does_not_wait_for_the_read_behind_it`,
    `test_two_first_asks_read_git_once`.
  - **The untracked names are `status`'s `??` records, and the three
    listings run at once** (#293): `ls-files --others` beside `status`
    walked the worktree twice. `status_names` gives changed and untracked;
    `worktree_files` runs it with the tracked and ignored listings in a
    `ThreadPoolExecutor`. `failed` is set if any gives None.
    `test_the_untracked_names_are_the_ones_status_gives`.
- **An icon is measured against its box**: `putIcon` draws in a clipping
  `0 0 14 14` viewBox, so a 1.2-wide stroke ends by 13.4.
  `test_every_icon_fits_inside_its_box` measures every `ICONS` entry. **A
  shape that is not closed looks cut anyway** (`dirOpen`): look at it at
  13 px, then measure.
- **What changed is bold, and the funnel shows it alone** (#492,
  `onlyChanged`, `putOnlyChanged`, `.onlychanged`): a dot was easy to
  miss. Bold is for `.filelist.files` only, not the transcript's map. The
  funnel keeps `state.files.marked` and `state.files.changed` in
  `treeRows`, and is in the list's redraw key, or a click draws nothing.
  It is kept in `localStorage`; `split` rebuilds the slot, so `drawFiles`
  puts it back. `test_what_changed_is_bold_and_the_funnel_shows_it_alone`.
- **A binary file is its hex on the Files tab** (#487, `hex_dump`,
  `HEX_MAX_BYTES`, `FileText.hex`, `state.files.hex`, `.code.hexdump`): the
  first 64 KB as `xxd` draws them, a dot for every byte not printable
  ASCII, so nothing in it acts on a page or terminal. The answer stays
  `binary` for `readLoose` and the Review tab. No colour and no `+`.
  `test_a_binary_file_is_read_as_hex_for_the_files_tab`,
  `test_a_binary_file_is_drawn_as_hex`.
  - **A hex row is as wide as the pane has room for** (`hexWide`, #524):
    the daemon sends 16 bytes a row, and the page, which alone knows the
    width, joins two or four when they fit. Called in `drawFiles`.
    `test_a_hex_row_is_as_wide_as_the_pane_has_room_for`.
- **A folder row carries no triangle**: it pushed a folder's name right of
  a file's at the same depth. `ICONS.dirOpen` says open instead.
- **The list marks where the reader last went (`state.files.at`), not the
  open file**, or a click on a path part above it showed nothing. `at` is
  in the list's redraw key.
- **Never clip a path at its start without `unicode-bidi: plaintext`**:
  `direction: rtl` alone drew `.gitignore` as `gitignore.`.
- **The tree holds the tiers**: `dirFiles` orders a directory's files
  named, changed newest first, then the rest. **A directory holding a
  change stays shut and counts them** (#517, `openDirs`,
  `dirsWithChanges`, `.nchanged`): a busy agent opened the whole tree.
  `state.files.marked` maps a folder to its changed files at any depth.
  **The funnel still opens them**, and what the reader opened or shut by
  hand (`state.files.dirs`) wins over both.
  `test_a_directory_holding_a_change_stays_shut_and_counts_them`,
  `test_a_directory_stays_as_the_hand_left_it`.
- **Typing is "go to file", not a filter**: where a file sits in the tree
  is half of what you know of it. `drawGoTo` lists files and directories
  under the box, `pick`-ranked, in `.findslot` so `split`'s children keep
  their places. Closing it clears its redraw key.
- **A file is found by its name; the path is a tight fallback.**
  `findPath` matches the whole path only when the letters span at most
  `TIGHT` times the query, or "MetricsBuilder" spread over four
  directories. A slash in the query means the path. `findPath` forgives
  one letter of a five-plus query; `fuzzy`, which filters sessions, none.
  - **A mark is a place in the name as written, and a whole character**:
    "İ" lower-cases to two code units. `unlowered` maps places back;
    `putName` takes a whole code point, not `text[index]`.
    `test_go_to_marks_the_letters_it_matched_in_any_script`.
- **The tree's window is as tall as the list, and a resize fills it**:
  `fillList` takes the rows shown plus eight at each end, never fewer than
  `ROWS_SHOWN`, and a `ResizeObserver` calls it, as a taller window sends
  no scroll event. `test_a_tall_file_tree_is_drawn_to_its_foot`.
- **Search every name, or say you cannot**: the first 5000 of 52,799 names
  missed a thousand files, a wrong answer that looks right.
- **`.listnote` is one clipped line**; anything taller goes in the
  `sidefoot` slot, as a button in the count strip could not be clicked.
- **A file over `CODE_WHOLE` lines is drawn a window at a time, and not
  painted**: drawn whole, 10,000 lines took 774 ms a save. `fillCode`
  builds the visible rows between two spacers. Below it browser find and
  copy-all work, and the page says which you got.
  - **A dense file is drawn whole and not painted** (`tooDenseToPaint`:
    over `PAINT_MAX` characters with a line over `LONG_LINE`): a 500 KB
    one-line bundle froze the page for seconds. **Never a cap on
    characters alone**: many standard-library files exceed 100 KB.
    `paintedLines` asks; `putFileCode` says so in a windowed file's note.
    `test_a_bundle_on_one_line_is_not_coloured_and_says_so`.
- **The Files pane scrolls sideways, not the rows**: on `.dlines` the bar
  sat under the last line. **The Diff tab keeps its scroller on
  `.dlines`**, as its pane stacks files. The override sits beside
  `.dlines`, not behind `.filebody`.
- **The file header stands outside the scroller**: `.filebody` is a flex
  column of `.where` and `.filescroll`. Everything that scrolls the file
  scrolls `.filescroll`: `fillCode`, `putFilePlace`, a redraw.
- **The file body's redraw key holds the session**: two sessions on one
  file shared one `.filescroll`, whose listener ignores another session.
  `test_two_sessions_on_one_file_each_get_their_own_scroller`.
- **A comment's box is its line, not rows** (`lineAt`), or the window
  began past the screen.
  `test_a_tall_comment_in_a_windowed_file_is_a_line_not_rows`.
- **`.filescroll` is built with the file, so another file starts at its
  top**; the place carries over only for the same file and session.
- **A tab's empty state is inset by whatever its body does not inset**, a
  wart: `.diffscroll > .empty` brings its own margin. **At a fourth
  spelling, inset `.empty` itself instead**, moving the two in `.content`.
  A margin, not a padding: a padded box still starts at the edge.
- **Wrapping and windowing cannot both be on**: a windowed file's rows are
  the scrollbar's grid. CSS enforces it (`:not(.windowed)`).
- **How a file is drawn is the reader's, in our `settings.json`**
  (`tab_width`, `long_lines`, `code_width`), set from the settings menu
  for the Files and Review tabs. `data-code` sets `font-stretch` on
  `.dlines` and `.hunk`, in `--code-face` (Noto Sans Mono, as Plex Mono
  has no narrow width). **Not `--code`**, which is a code block's ground.
  **No control rebuilds anything**: `redrawCode` would lose a half-written
  comment. `readingWanted` falls back to the default. A windowed file
  says "too long to wrap" by CSS (`.nowrap`).
- **`BIG_LINES` and `CODE_WHOLE` answer one question in two shapes; never
  quietly make one the other**: the Diff tab closes a long file, as
  stacked files give no scrollbar grid; the Files tab windows it.
- **`CODE_H` is the row height in pixels, and `.dlines` sets the same
  number**: a scrollbar grid cannot be `line-height: 1.65`.
  `.code.windowed .dlines` drops its padding for the same reason.
- **A slice of a file says which line it starts at** (`asLines(path,
  lines, from)`, `hunk.from`, read by `walkHunks`), or its comments anchor
  to the wrong line.
- **Ask the pane which file it holds** (`pane.dataset.file`), never the
  redraw key: `redrawCode` clears that, and a windowed file jumped to its
  top.
- **One renderer for a line, in `fillDiffFile`** (`unifiedRow`, `pairRow`,
  `putLineReview` the one place that puts a `+`), for the Files tab, the
  Diff tab and an untracked file, so line 42 has one anchor in both tabs.
- **The highlighter gets the whole file; `cutIntoLines` cuts the answer
  up**: block comments paint wrong line by line. The cut walks the
  scrubbed fragment, never HTML text, and a line count that differs from
  the file paints nothing: wrong colour is worse than none.
  - **No CR goes into the highlighter** (`paintedLines`): `paintedInto`'s
    HTML parser breaks at CR, and Windows files went unpainted. **A CR
    ending a line goes; one inside becomes a space**, or the word marks
    after it slip (`wordDiff` counts the CR). Every paint goes through
    `paintedLines`. `test_a_file_with_a_carriage_return_is_painted`,
    `test_a_diff_of_a_file_with_windows_line_ends_is_painted`,
    `test_a_lone_carriage_return_keeps_the_word_marks_in_place`.
- **Reading the open file remembers `Files.root_of` and
  `Files.language_of`** (path, mtime, size), as the tab polls every two
  seconds. **`is_listed` is never cached**: a remembered yes reads a file
  taken out of the tree.
- **A file's language is its name, then its shebang, then `file`**, only
  if both are empty, so a suffix never costs a subprocess. `file` is the
  last command the daemon runs, after git and tmux. Its answer
  counts only through `BY_MIME`; **`text/x-c` is not on it**, as libmagic
  calls Rust and Go C. No paint beats a wrong one.
