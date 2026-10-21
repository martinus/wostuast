# The Diff tab

The Review tab's diff: files, halves, commits, pickers, columns, redraws.
Comments are topics/review; git is topics/git.

- **One file of a diff stands apart from the next** (#525, `.dfile`): 28
  px between cards, the header (`.dfile > .name`, `.openfile`) on
  `--raised`, the path bold. On the code's `--sheet`, files ran together;
  the reader chose the raised ground from pictures. Tool diffs wear the
  card too (`.dfile.tooldiff`).
  `test_one_file_stands_apart_from_the_next`.
- **Each half says what it is a diff of, in words**
  (`DiffSection.about`, built by the daemon with the base named):
  `origin/main...HEAD` left nobody sure what was shown. **With no base,
  the pane says the committed half is missing**, and what git was asked.
- **One commit's comments go through `since`**, as the committed half's go
  through the uncommitted one: a commit's new side is the commit, not the
  disk. `since` is `git diff <sha> -- <its files>`, read by `inWorktree`;
  only its own files, as a whole-repository diff costs every later commit.
- **The picker is built once with the pane and refilled only when the
  commits change** (`fresh(bar, "key", …)`): a `select` whose options are
  replaced closes, and the tab polls. Picking and the column switch wait
  while a comment box is open (`busyWriting`; topics/review). **Older and
  newer step through "5 / 9"** (`.stepat`, oldest first), one control
  (`.choice.stepper`, arrows with words in `title` and `aria-label`) the
  reader chose from pictures. **Another commit, or another session's
  diff, is read from its top**: `drawDiff` keeps the place only when
  `scroll.dataset.of` says the same diff, keyed on `state.chosen` and
  `of`.
  `test_the_older_and_newer_buttons_step_through_the_commits`,
  `test_another_commit_is_read_from_its_top`,
  `test_another_sessions_diff_is_read_from_its_top`.
- **A merge is shown by what it changed by hand** (#621, `merge_by_hand`,
  `DiffReport.merge`, `putMergeAs`): against its first parent it showed the
  other branch's whole work and no sign of what the merge did. `git show
  --remerge-diff` (`git_diff(..., remerge=True)`; `git diff` has no such
  option) merges again, conflicts and all, and shows what the commit holds
  that differs; a clean merge shows nothing and says so. "all it brought
  in" (`state.diffs.merge`, `merge=all`) is the first parent again. **The
  hidden lines come from the same diff** (`whole_file_diff`, `merged_all`):
  the conflict's lines are no lines of the first parent's diff. A git
  before 2.36 refuses it: `merge` is "old", the head says why, no switch.
  The picker says "merge ·" before the subject.
  `test_a_merge_is_shown_by_what_it_changed_by_hand_or_all_it_brought_in`,
  `test_a_merge_settled_by_hand_shows_how`,
  `test_a_git_that_cannot_show_a_merge_by_hand_shows_all_and_says_why`,
  `test_a_merge_is_marked_and_shown_by_hand_or_whole`.
- **The pane reads in the tree's order, not git's** (`treeOrder`, folders
  first at every level).
- **The file clicked in the tree keeps the mark while it is on screen**
  (`scroll.picked`): `markDiffFile` marks the block under the pane's top,
  which the last file never reaches.
- **A diff is painted one side of one hunk at a time, and the word marks
  go back on after**: a lone row gets every multi-line string wrong, and a
  paint replaces the cell, so `paintDiff` calls `markWords` again.
  `test_the_diff_is_painted_and_keeps_its_word_marks`.
  - **A word is split by code point** (`WORD` has the `u` flag), or a
    changed emoji is marked half.
    `test_an_emoji_that_changed_is_marked_whole`.
- **Lines hidden between changes come from the same diff with the whole
  file as context, never from the file on disk** (`whole_file_diff`,
  `WHOLE_CONTEXT`, the path a literal pathspec after `--`): the lines must
  be the half's side, HEAD, the commit or the disk. Read from disk, HEAD's
  half got the disk's lines. A commit is used only when `branch_commits`
  lists it. `test_a_whole_file_is_every_line_of_the_side_the_half_shows`.
- **What the reader revealed is kept as line numbers, and the whole file
  against the hunks it came with**: `state.diffs.more` holds `[from, to]`
  runs by `moreKey` (what is shown, the half, the path); `state.diffs.whole`
  keeps each file with its `hunkSig`, and `withMore` drops it when the
  hunks move. `test_shown_lines_come_again_from_the_file_as_it_now_is`.
  **Another base keeps them** (`keepBase`). **A whole file that failed or
  came back cut is asked for again on a click** (`revealLines`).
  `test_a_whole_file_that_failed_is_asked_for_again_on_a_click`.
- **A diff stands on `--sheet`, white in the light, not on `--code`**: on
  `--code` an unchanged line had contrast 4.29, under 4.5. `--code` is for
  a code block in prose. `test_a_diff_in_the_light_is_on_white_and_reads`.
- **A commit picked shows its whole message, asked for that commit only**
  (`DiffReport.body`, `git show -s --format=%b`), not sent with every
  `Commit` every poll. **`reflow` joins a paragraph's lines** and the
  window wraps them; a list item, an indented line and a trailer keep
  their line (`pre-wrap`). The heading goes through `linkTickets`.
  `test_a_commit_message_wraps_at_the_window_and_links_its_tickets`.
  **The title is a box of its own** (`.subject`, #445): a grid or flex
  item drops its leading space ("OA-123this").
  `test_a_ticket_at_the_start_of_a_subject_keeps_the_space_after_it`.
  **It is Markdown, and the text is one click away** (`putMessage`,
  `MESSAGE_KEY`); a line `reflow` keeps is a hard break there too. The
  click refills only the message, as a rebuild loses a half-written
  comment. Without `marked` it is the text, with no control.
  - **The control is the Files tab's `putReadAs`**: one "txt" button
    (`paintToggle`) at the right of the line naming what is read, as the
    reader asked. `.diffhead.commit` is a grid so the subject stays the
    head's first child, which the tests read.
    `test_a_commit_message_is_markdown_and_its_text_is_one_click_away`,
    `test_a_document_is_read_as_markdown_or_text_from_the_right_of_its_path`.
- **The pickers say what they hold, in the narrow face**: "all changes"
  counts the branch's own commits. "against" stands beside the branch
  picker, which does not shrink, as a branch name must read whole.
  `test_the_pickers_say_how_many_commits_and_stand_apart_from_against`.
- **Two columns wrap; one column scrolls unless the reader wraps it**: two
  halves cannot share a sideways scrollbar, so `.dlines.sides` wraps. The
  `+` is on the new half only; a side with no line is hatched, so the
  columns stay level.
  - **The tint is the half's, never the row's** (#444, `pairRow`):
    `.dline.pair.added` and `.removed` draw no ground, or the hatched half
    is tinted. `test_a_line_with_no_counterpart_tints_its_own_half_only`.
  - **A comment stands under the half its `+` is on** (#446,
    `.dlines.sides > .onLine`).
    `test_in_two_columns_a_comment_stands_under_the_new_half`.
  - **A line's text is a box of its own** (`.dline .dtext`), or a tab is
    measured from the row's start; a wrapped rest then stands under its
    text, on the Files tab too.
  - **One column is a grid of one `auto` track** (`.dlines:not(.sides)`,
    `minmax(100%, max-content)`): a pane-wide row cut a line's colour when
    scrolled. `.onLine` is sticky and 680 px at most.
  - **How the diff is drawn is in the settings menu** (`putSettings`): the
    column switch on the bar cramped it. The bar's buttons are
    topics/settings's (`putQuick`).
  - **Whitespace is two settings, and only one asks git** (#449):
    `diff_space` "hide" is `git diff -w` (`SPACE_ARGS`), sent as
    `space=hide` on the diff *and* the whole-file route; `Daemon.diffs`
    keys by it, and `respace` asks at once. `space_marks` asks nobody:
    `markSpaces` wraps each tab and line-end space in `.ws`, shown by
    `data-marks`. **It runs wherever a line is drawn or painted**, after
    the word marks (`unifiedRow`, `pairRow`, `paintDiff`, `paintLines`,
    `paintSlices`). **A tab is never wrapped**: the mark is an empty
    `.ws.tabmark` before it. **The mark is not `.tab`**, whose 24 px of
    padding ran a tab to the next stop at width 2 or the narrow
    `code_width`.
    `test_a_tab_in_a_diff_line_is_a_whole_tab_from_where_the_text_starts`
    (width 2; tests wait for the mark `attached`, as it is empty),
    `test_a_change_of_whitespace_alone_is_left_out_when_asked`,
    `test_a_change_of_whitespace_alone_goes_and_comes_back`,
    `test_a_tab_and_spaces_at_the_end_are_marked_when_asked`.
  - **A file opens on the Files tab from beside its header**
    (`openInFiles`, `.openfile`, #449): a button holds no other button.
    `.dfile:has(> .openfile)` is a grid.
    `test_a_file_in_the_diff_opens_on_the_files_tab`.
  `test_scrolled_sideways_every_line_keeps_its_colour`,
  `test_a_long_line_wraps_under_its_own_text_in_one_column`,
  `test_the_settings_say_what_is_chosen_and_change_it_in_place`.
- **A split tab keeps its two columns and redraws one at a time**:
  `split()` builds them once, `fresh()` decides what changed. One key over
  the whole tab re-rendered the file being read every two seconds.
  - **The Diff pane redraws one file at a time**: rebuilding every file
    drew the one being read plain, behind `hljsReady`, and it jumped. The
    pane is built in a fragment; a file whose `blockSig` is unchanged keeps
    its block, `settle` places blocks without moving a kept one, and
    `readerAt` holds the top block when a file above grows. **`blockSig`
    is everything the block is drawn from that `diffKey` does not cover**:
    the diff, its open, more and whole state, `BIG_LINES`, the half, the
    session, the columns, and for a commit its file in the later diff
    (`laterFile`, as `inWorktree` anchors there). Comments are not in it:
    `redrawCode` empties the key, and `again` draws all. **`putReview`
    looks for an open `.commentbox` under its own root too**, as a pane
    built apart is not in `document`.
    `test_a_save_to_another_file_leaves_the_one_being_read_alone`,
    `test_a_file_that_grows_above_leaves_the_reader_where_they_were`,
    `test_one_line_in_both_sections_opens_one_comment_box`,
    `test_a_committed_line_follows_lines_added_above_it_since`.
- **`drawLooseFile` builds a synthetic file; everything `fillDiffFile`
  reads must be in it**: without `path`, comments anchored to `undefined`.
- **An untracked file's text is read by `readLoose`, and only text is its
  text**: a failed fetch drew "This file is empty.", a `missing` answer
  one line with a `+`. An unread file says why, and `loadDiff` asks every
  poll until it is read. **`loadDiff` lets a gone file go, where the
  answer is taken** (#542), never in `drawDiff`, a draw. `loosePick` keeps
  a draw from showing a pick the diff does not list.
  `test_an_untracked_file_picked_and_then_added_lets_go_of_the_pick`,
  `test_an_untracked_file_is_read_again_when_its_session_comes_back`,
  `test_an_untracked_file_that_could_not_be_read_says_so`,
  `test_an_untracked_file_git_would_not_list_is_not_its_one_line`.
