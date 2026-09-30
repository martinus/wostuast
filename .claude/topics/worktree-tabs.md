# The worktree tabs

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. git, the Files tab and the Review tab's diff.

- **Work from the worktree root, not the agent's directory.** git reports
  root-relative paths whatever directory it ran in. `worktree_root` answers this.
- **Inside a hunk, the first character of a line is the only thing that matters.**
  Removing `-- a comment` writes `--- a comment`; read as a header it renamed the
  file and swallowed the hunk. Only `diff --git` and `@@` may start something new.
- **`run` reads bytes and decodes them itself; it never reads text.**
  `subprocess.run(text=True)` reads with universal newlines, so a lone CR
  inside a line of a diff -- `b = 1\r c = 2` -- became a line break before
  `parse_diff` saw it: the hunk header grew a false context line, every line
  after it was numbered one too high, and the Files tab, which reads the
  bytes, disagreed. The scar below, by another road. A CRLF file's diff lines
  now end in `\r`, as the Files tab's always did.
  `test_a_carriage_return_inside_a_line_stays_in_that_line`.
- **Split a diff on `\n`, never with `splitlines()`.** It also breaks on a form
  feed, a vertical tab, `\x1c`-`\x1e` and `\u0085`, all legal inside a source
  line and none of them escaped by git — it only quotes paths. One form feed
  put every later line in the hunk one number too high, so the two tabs
  disagreed and a review comment anchored to a line nobody commented on.
- **A path out of a diff may be quoted, and must be unquoted.**
  `core.quotePath=false` only covers bytes above 0x80; a quote, a backslash or
  a control character is escaped whatever it says, and the `a/` prefix goes
  inside the quotes. `we"ird.txt` came out mangled, a plain edit read as a
  rename, and the name did not match what `ls-files -z` gives the Files tab —
  so one line had two anchors. `unquote_path` is the one place that undoes it.
  **And a name holding a space ends in a TAB** on the `---` and `+++` lines
  -- git adds it for GNU patch, unquoted -- so `foo bar.txt\t` was the Diff
  tab's name and `foo bar.txt` the Files tab's. `parse_diff` takes one
  trailing tab off; a name that really ends in one is quoted, so the one
  outside the quotes is always git's.
  `test_a_name_with_a_space_is_the_name_the_files_tab_lists`. **A `diff
  --git` line that is not a rename splits in the middle**: a binary or a mode
  change has no `---`/`+++` to put the name right, and the last ` b/` in
  `a/Plan b/logo.png b/Plan b/logo.png` made it a rename to `logo.png`.
  `diff_header_paths`, `test_a_folder_ending_in_b_does_not_make_a_rename`.
- **A cut goes back to the last newline, and the cap counts bytes.** A cut
  inside a `diff --git` line parsed as a file that does not exist, reported as
  a rename. `run` returns text, so a cap on `len()` counts code points and let
  a four-byte-character diff through at four times the size, while
  `FILE_MAX_BYTES` measures real bytes.
- **List every file, stat only the changed ones.** Tens of thousands of files,
  tens of changed ones. Asking the disk about all of them every poll is the
  mistake.
- **A wholly-ignored directory is walked by us, with a budget.** git's
  `--directory` collapses one into a single entry and looks no further, and
  dropping that entry left `.oa-implement` — a directory an agent writes its
  plan into, which is the one ignored place a reader wants — with no way in
  at all. `walk_ignored` lists it **only when what it holds fits in
  `IGNORED_MAX`**, counting what is under it and not counting a folder
  already left out, and it stops reading the moment it knows. So a build root
  of a hundred thousand objects costs 2,000 reads, comes back as one name in
  `Worktree.skipped`, and the plan beside it is listed because what is left
  of the directory then fits. Nothing is ever half-listed: a folder comes back
  whole or comes back as its own name. `node_modules` fails the same test and
  stays one row, which is what git's own rule was protecting.
  **The budget is an argument, not a default read at import**, or a test
  would have to build two thousand files to reach it.
  A link to a directory is neither followed nor listed: following it is a way
  round the budget and into a loop, and it is not a file.
- **`skipped` is not in the listing's tag.** The tag is a hash of the names,
  and a build root that appears adds none — every file in it is left out. So
  the page rebuilds the tree when the names move **or** when `skipped` does,
  and `buildTree(names, skipped)` makes an empty folder for each one: a
  directory holding nothing is a directory nothing above would create, and a
  folder the reader cannot see is the same silence as one that says nothing.
  Its row carries `.toobig` and does not open — a folder that opens onto
  nothing reads as broken. Its title promises nothing more: "opening one in
  it still works" was said, and no name in it is sent, so none can be found
  or kept open.
- **One listing per worktree, and the page holds the names.** `Files` keeps it
  for `LIST_FRESH` and serves a stale one while re-reading behind. Names go with
  a tag; a listing that has not moved answers without them — 1733 KB against
  0.2 KB. So **the order the names are sent in must depend only on which files
  exist**: `in_order` is pinned-then-name. Put a changed tier back into it and
  the tag moves on every save. The reader's order is the page's, in `dirFiles`.
- **An icon is measured against its box, not eyeballed.** `putIcon` draws
  into a `0 0 14 14` viewBox and an `svg` clips to its viewport, so a stroke
  -- 1.2 wide, reaching 0.6 past the line it is drawn on -- must end by 13.4.
  The page icon's bottom sat at 13.5 and lost its last tenth.
  `test_every_icon_fits_inside_its_box` measures every entry in `ICONS` with
  the page's own CSS. **And a shape that is not closed looks cut whether or
  not anything cut it**: `dirOpen` first ran the lid to x=12 and the floor to
  x=13 with nothing joining them, and read as a folder with its right side
  sliced off, although nothing was ever clipped. Draw it, look at it at 13 px,
  then measure it.
- **A folder row carries no triangle.** It stood where nothing stood on a
  file row, so a folder's name sat 9 px right of a file's at the same depth —
  and a file one level deeper lined up exactly with the folder above it, which
  is the one thing a tree must not do. `ICONS.dirOpen` says what the triangle
  said.
- **The list marks where the reader last went, `state.files.at`.** Not the
  open file: clicking a part of the path above a file that was already on
  screen scrolled nowhere and marked nothing, so the click read as broken.
  `at` is in the list's redraw key, or the mark does not move.
- **A path clipped at its start is a bidi trap.** `direction: rtl` puts the
  ellipsis at the front, which is what you want on a path — and moves a
  leading neutral character to the other end, so `.gitignore` drew as
  `gitignore.`. `unicode-bidi: plaintext` takes the direction from the first
  strong character instead. Never clip a path at its start without it.
- **The tree holds the tiers.** `dirFiles` orders each directory's own files —
  named, changed newest first, then the rest. `openDirs` opens a directory
  holding a change; `state.dirs` (what the reader opened by hand) wins over it.
- **Typing is "go to file", not a filter.** The tree never moves: where a file
  sits is half of what you know about it, and taking the tree apart was hiding
  that answer as a way of asking for it. `drawGoTo` opens a list under the
  box — files *and* directories, `pick`-ranked — and picking one opens it and
  reveals it. The list lives inside `.findslot` so `split`'s children keep
  their positions, and closing it clears its redraw key, or the same query
  typed twice matches the key and draws nothing.
- **A file is found by its name; the path is the fallback, and it must be
  tight.** `findPath` matches the basename first, then the whole path only when
  the matched letters span no more than `TIGHT` times the query length.
  Matching the whole path outright let "MetricsBuilder" land across 71
  characters and four directory names while missing the file meant. A slash in
  the query means you meant the path. `findPath` also forgives one letter of a
  five-plus query; `fuzzy` forgives none by default, because the session filter
  runs through it and a short haystack cannot afford it.
- **Search every name, or say you cannot.** Sending the first 5000 of 52,799 made
  a search find 16 files and miss a thousand: a wrong answer that looks right.
- **A git call that failed must not render as an empty answer.** "No files" and
  "git did not answer" look the same and mean opposite things. **Nor may a
  failure be remembered as one**: `Files.root_of` kept the empty string a
  timed-out `git rev-parse` returned, and one such moment left that worktree
  unreadable until the daemon was restarted. The same for `file`:
  `sniff_language` returns `None` for "it did not answer" and `""` for "it
  answered, and not with something we paint", and only the second is kept.
  `GitFacts.failed`, `Worktree.failed` and `DiffReport.failed` are how each
  answer says which it is. **On the page too**: `loadFiles` took a failed
  listing's short names as fact and closed the open file, its place and a
  comment half written on it; now the names held stand while `failed` is
  set, and only a listing that did not fail may say a file has gone. And a
  `missing` answer for the open file -- what a timed-out `is_listed` says
  too -- is never written in as its text: it was drawn as line 1, with a `+`
  that would anchor a comment to the real line 1. **With nothing read yet
  it is said** (`state.files.read`, `state.files.trouble`): a refused first
  read drew the header over an empty body, which is a file with nothing in
  it, for as long as the refusal lasted, and a fetch that failed drew
  nothing, so the file before stood under the name just picked.
  `test_a_first_read_that_failed_says_so_and_is_not_the_file`,
  `test_a_listing_git_failed_on_keeps_the_open_file`,
  `test_a_file_read_git_failed_on_is_not_drawn_as_its_text`; `reload_git` puts a failed directory back on the
  list rather than over what it already knew.
- **`run` gives None for "the command failed" and for "it could not run".**
  Outside a repository git *fails*, so an empty answer is not by itself a
  failure. Two ways to tell them apart: another call that already worked on
  the same directory (`git_facts` knows it is a repository because
  `rev-parse` answered), or `git_answers()`, which asks `git --version` — it
  cannot fail inside a working git, and stalls on the same stalled machine.
  Only in the failure path, so a repository never pays for it. **Every door
  that reads an empty answer asks**: `worktree_files` did, and
  `worktree_diff`, `whole_file_diff` and `git_facts` did not -- a timed-out
  `--show-toplevel` came back as a worktree with nothing changed, and a
  stalled `git_facts` wrote empty facts over the known ones. `diff_base`
  returns whether `for-each-ref` failed beside the base, because "no such
  names" is said on the page as a fact.
  `test_a_root_git_could_not_find_is_not_an_empty_worktree`,
  `test_a_base_git_could_not_look_for_is_not_no_base`,
  `test_a_git_that_does_not_answer_at_all_has_failed`.
- **A repository with no commit yet is an answer, not a failure.** `git init`
  leaves no HEAD, so `git log HEAD` and `git diff HEAD` fail, and the tab
  said git did not answer on every poll -- while the staged files were in
  neither list, being in the index and so not untracked. `has_head` is asked
  only when the log failed, and the uncommitted half is then measured
  against `empty_tree`, in `whole_file_diff` too.
  `test_a_repository_with_no_commit_yet_shows_what_is_staged`.
- **The Diff tab says what each half is a diff of, in words.** The headings
  were `origin/main...HEAD` and "not committed yet" — precise, and readable
  only if you already know what three dots mean, so nobody could tell whether
  the tab showed the last commit, the branch, the worktree, or some of each.
  `DiffSection.about` carries the sentence, the daemon builds it with the base
  named in it, the pane draws it under the heading and the list carries it as
  a `title`. **And when there is no base the committed half is missing
  altogether**, which used to look like a tab that simply had less in it: the
  pane says so, and names what git was asked for.
- **A commit the page names is used only if `branch_commits` listed it.**
  The sha arrives in `?of=` and the page is input, so `worktree_diff` looks
  it up in its own list and hands git the listed one, never the string it
  was sent. One that is not there — an agent amended or rebased — comes back
  as `gone` with all changes, and the pane says why. **A log git failed on
  is not a commit gone**: the list was empty, the sha not in it, and the
  pane said "probably amended or rebased away" and dropped the pick. It
  returns `failed` with no section, and the page keeps the diff it holds
  (`test_a_log_git_failed_on_is_not_a_commit_gone`).
  `test_a_commit_the_page_names_is_used_only_if_git_listed_it` sends
  `--output=` and `HEAD~1` and asserts neither reaches an argv.
- **One commit's comments go through `since`, as the committed half's go
  through the uncommitted one.** The commit's new side is that commit, not
  the disk, so its line numbers are not the file's. `since` is `git diff
  <sha> -- <its files>` and `inWorktree` reads it when a commit is shown.
  Only the commit's own files: the diff to the disk of a whole repository is
  what every later commit cost. Drop it and a comment on `print(2)` anchors
  to line 2 when fifty lines stand above it — the scar the committed half
  already had.
- **The picker is built once with the pane, and refilled only when the
  commits change.** A `select` whose options are replaced closes if it is
  open, and the tab polls every five seconds. `fresh(bar, "key", …)` guards
  it. Picking and the column switch both rebuild the diff, so both refuse
  while a comment box is open and say so (`busyWriting`) — a rebuild takes
  what is typed, and a switch that silently did nothing reads as broken.
  **Between older and newer, "5 / 9"** (`.stepat`): which commit, oldest
  first, so the branch's first commit is 1. **And another commit is read
  from its top**: `drawDiff` keeps the place only when `scroll.dataset.of`
  says the same diff is drawn again, and says nought otherwise -- a pane
  emptied and refilled in one task keeps its offset, so the next commit
  opened where the last had been read to.
  `test_the_older_and_newer_buttons_step_through_the_commits`,
  `test_another_commit_is_read_from_its_top`.
- **The pane reads in the tree's order, not git's.** `treeOrder` puts
  folders first at every level, and both the list and the pane go through
  it, so the two read the same way down. git's order is plain path order,
  which put `README.md` above `src/a.py` in the pane and below it in the
  tree.
- **The file clicked in the tree keeps the mark while it is on screen.**
  `markDiffFile` marks the block under the top of the pane, and the last
  file of a diff can never scroll to the top — there is nothing under it —
  so a click on it marked the file above. `scroll.picked` wins until it
  leaves the screen.
- **A diff is painted one side of one hunk at a time, and the word marks go
  back on after.** Each side of a hunk is text that makes sense in order;
  the whole file is not available here, and a row on its own gets every
  multi-line string wrong. Painting replaces what a cell holds, so
  `paintDiff` calls `markWords` again from `cell.words`. Take that out and
  the marks go the moment the colour arrives, which nothing but
  `test_the_diff_is_painted_and_keeps_its_word_marks` would notice offline.
- **Lines hidden between changes come from the same diff with the whole
  file as context, never from reading the file.** `whole_file_diff` is the
  section's own `git diff` with `-U1000000` and the path as a literal
  pathspec after `--`, so the lines are the side the half shows — HEAD for
  the branch's work, the commit for one commit, the disk for what is not
  committed — and the section picks its arguments from three fixed ones.
  Reading the file from disk would put the disk's lines into the committed
  half, which is HEAD's. A commit is used only when `branch_commits` lists
  it, as everywhere else. `test_a_whole_file_is_every_line_of_the_side_the_half_shows`.
- **What the reader revealed is kept as line numbers, and the whole file
  against the hunks it came with.** `state.diffMore` holds `[from, to]`
  runs by `moreKey` — what is shown, the half, the path — because one
  commit's line 40 is not another's. `state.diffWhole` keeps each whole file
  with `hunkSig` of the diff it belongs to, and `withMore` drops it the
  moment the hunks move: the agent saves, and a kept file would put old
  lines between new changes. `test_shown_lines_come_again_from_the_file_as_it_now_is`.
  **A whole file that failed, or came back cut, is kept against draws but
  not against a click**: kept through one, every later click on a band
  added a range, drew, and showed and said nothing. `revealLines` lets it
  go. `test_a_whole_file_that_failed_is_asked_for_again_on_a_click`.
- **Every diff asks git for `-U3` out loud.** The page reads fewer than
  three lines after the last change as the end of the file and offers no
  more below it; a reader's `diff.context` would move that line and hide
  the offer on every file. `DIFF_CONTEXT` is the number on both sides.
- **A diff stands on `--sheet`, not on `--code`, and it is white in the
  light.** Its file header stands on it too: a colour of its own, darker
  than the code, read as a bar rather than the top of the file. On the code ground, `#eceae3`, an unchanged line stood at a
  contrast of 4.29 — under the 4.5 body text needs — and the card read as a
  brown box darker than the page around it. `--code` stays what it is for a
  code block inside prose. `test_a_diff_in_the_light_is_on_white_and_reads`.
- **A commit picked shows its whole message, and only that commit's is
  asked for.** `DiffReport.body` is `git show -s --format=%b` for the one
  commit shown, not a field of every `Commit`: a hundred bodies on every
  poll would be sent for the one being read. **A paragraph's lines are
  joined (`reflow`) and the window wraps them**: a git body is wrapped by
  hand at about 72 columns, and drawn as it stood, in a box 80 characters
  wide, it broke there whatever the window. A list item, an indented line
  and a trailer (`Refs: OA-1`) keep their own line, because there the break
  is the meaning; it stays `pre-wrap` in the fixed face for them. The whole
  heading goes through `linkTickets`, so a ticket in the subject is a link
  too. `test_a_commit_message_wraps_at_the_window_and_links_its_tickets`.
  **It is drawn as Markdown, and the text is one click away**
  (`putMessage`, `MESSAGE_KEY`): an agent writes its messages in Markdown,
  and the tab drew the source; the reader asked for both. A line `reflow`
  keeps is a hard break in the Markdown too, or a trailer ran into the line
  above it. The click fills the message again and nothing else, because a
  rebuild takes a comment half written. Without `marked` it is the text,
  and the control is not there.
  - **The control is the Files tab's, and stands where that one does**
    (`putReadAs`): "Markdown | text", with icons, at the right end of the
    line that names what is read -- the subject here, the path there. The
    reader asked for the two to look and feel the same, and chose the place.
    `.diffhead.commit` is a grid so the control can stand in the subject's
    line while the subject stays the head's first child, which the tests
    read.
  `test_a_commit_message_is_markdown_and_its_text_is_one_click_away`,
  `test_a_document_is_read_as_markdown_or_text_from_the_right_of_its_path`.
- **The pickers say what they hold, in the narrow face.** "all changes"
  carries the count of the branch's own commits -- not the recent ones on
  the default branch, which are no part of it. "against" stands beside the
  branch picker, not in each option, and the branch picker does not shrink:
  "against main" was cut to "against ma", and a branch name is read whole
  where a commit subject can be cut and still be known.
  `test_the_pickers_say_how_many_commits_and_stand_apart_from_against`.
- **Two columns wrap; one column scrolls unless the reader wraps it.** A
  pair of halves cannot share a sideways scrollbar, and two bars drift
  apart, so `.dlines.sides` hides the overflow and the halves wrap. The `+`
  is on the new half only — a comment is about the file as it is — and a
  side with no line is hatched, not closed up, so the columns stay level.
  - **The line's text is a box of its own** (`.dline .dtext`, an inline
    block; a flex item when wrapped). In one row with the numbers and the
    sign, a tab was measured from the start of the row: a line indented by
    one tab stood one space in after the `+`. A wrapped line's rest then
    stands under its text, not under the numbers -- on the Files tab too.
  - **One column is a grid of one `auto` track** (`.dlines:not(.sides)`):
    a row is `min-width: max-content`, and a block row was only as wide as
    the pane, so scrolled sideways a short line's colour stopped at the
    pane's edge. `minmax(100%, max-content)` does not do it: the track never
    grows past the pane. A comment stays readable in it because `.onLine`
    is sticky and 680 px at most.
  - **How the diff is drawn is in the settings menu** (`sidebar.md`,
    `putSettings`): the columns, the tab width and long lines. The Review
    bar was cramped on a notebook with the column switch alone in it.
  `test_a_tab_in_a_diff_line_is_a_whole_tab_from_where_the_text_starts`,
  `test_scrolled_sideways_every_line_keeps_its_colour`,
  `test_a_long_line_wraps_under_its_own_text_in_one_column`,
  `test_the_settings_say_what_is_chosen_and_change_it_in_place`.
- **The two changed-file counts are about different things, and stay that
  way.** The sidebar's comes from `git status` in git's default untracked
  mode, which collapses a wholly-untracked directory into one entry; the
  Files tab dots each name, from `--untracked-files=all`. So five new files in
  a new directory read as "1 file" beside five dots. The cheap call is on the
  tick thread under a two second timeout, and the thorough one is not — that
  is the reason, and it is worth more than the two numbers agreeing.
- **A split tab keeps its two columns and redraws one at a time.** `split()`
  builds them once, `fresh()` decides what changed, both reading the DOM. One key
  over the whole tab re-rendered the file you were reading every two seconds.
- **`.listnote` is one clipped line.** Anything with height goes in the `sidefoot`
  slot. A button put in the count strip could not be clicked at all.
- **`drawLooseFile` builds a synthetic file object.** Everything `fillDiffFile`
  reads must be in it. `path` was missing, so every untracked file's comments
  anchored to `undefined`.
- **An untracked file's text is read by `readLoose`, and only text is its
  text.** A fetch that failed was drawn as "This file is empty.", and a
  `missing` answer -- a timed-out `is_listed` gives one -- as the file's one
  added line, with a `+`. Both were kept, and a click on the name did
  nothing, it being the name already picked. And coming back to a session
  put the pick back and not the text, and nothing asked for it: "reading…"
  for ever. Now an unread file says why, and `loadDiff` asks again on every
  poll until it is read; one that really went leaves `untracked` and is let
  go. `test_an_untracked_file_is_read_again_when_its_session_comes_back`,
  `test_an_untracked_file_that_could_not_be_read_says_so`,
  `test_an_untracked_file_git_would_not_list_is_not_its_one_line`.
