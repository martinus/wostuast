# The review

Comments, the review's send bar, and the draft.

- **A comment is anchored to what it is about -- the path and the line,
  nought for the whole file -- never to the node it was drawn on**: the
  Diff tab is rebuilt from `state.diff` whenever the agent saves.
- **A comment is a place in a file, not in a diff; there is no "gone" or
  "moved".** The page once worked those out and sent them as the reader's
  words: a note on a file the agent never touched said "this line is no
  longer in the diff". The message tells the agent to search for the
  quoted line.
- **The review is written, read back and sent on one tab, the diff's,
  labelled Review** (`data-tab` and the code still say `diff`). A tab of
  its own was used only to press send: the comments already stood in the
  diff.
  - **The tree lists the comments** under the files (`putCommentList`):
    first line and `path:line`; a click goes to it (`goToComment`), opening
    a shut file first. **It scrolls a frame after the draw that opened the
    file**: `putDiffPlace` restores the reader's place in a frame and undid
    an immediate scroll. `test_a_comment_in_a_shut_file_is_gone_to_from_anywhere_in_the_pane`.
    `delete review` is on the heading and takes two presses. A comment is
    gone to here, never on the Files tab: `goToLine`, `lineTop`, `showLine`
    went with the old tab, and nothing else asked for a line.
  - **Every comment is somewhere on the tab** (`putElsewhere`): one the
    diff does not draw (written on the Files tab, on a line no hunk holds,
    on another commit) stands under "commented elsewhere", with its lines
    read from disk. The message sends every comment; one not on the tab is
    sent unread.
    - **What the diff draws is worked out from the diff, never asked of the
      pane** (`diffAnchors`): the pane also drops a comment being edited, a
      shut file's lines and files the find box hides, and each moved a
      comment to "elsewhere".
    - **The lines round a comment elsewhere draw nothing the diff draws**
      (`drawn` on the file `fillElsewhere` hands `fillDiffFile`, read in
      `putLineReview`): else the comment stood twice, and "edit" below
      opened the box above.
      `test_a_comment_the_diff_shows_is_not_drawn_again_under_elsewhere`.
    - **The lines are read once; only a changed file is read again.**
      `state.reviewFiles` forgets each file the new diff lists
      (`forgetChanged`); an unlisted file cannot have moved. A failed read
      is not kept. **A 404 is JSON too**: `readElsewhere` kept a `missing`
      answer (a timed-out `is_listed` gives one) as a file with no lines, and
      never asked again.
      `test_a_file_elsewhere_that_was_said_to_be_missing_is_asked_for_again`.
      Lines fill the section's own box (`.offdiff`, `fillElsewhere`), and
      `paintSlices` paints a file once per read: redrawing the pane twice a
      poll made the section jump. **Asked for on each answer of the diff**
      (`askElsewhere`, from `loadDiff`, #566), **never with no comment**
      (#594): it walked every line (`diffAnchors`) every five seconds for
      nothing. `test_a_review_with_no_comment_walks_no_diff`.
  - **The send bar is the only place a review is sent from** (`#reviewbar`,
    `drawReviewBar`), pinned under the pane, only on this tab and only
    while there is a review: the whole-review comment
    (`state.review.overall`), the message after it, `reviewText(false)`,
    and **Send**. **The message is the preview: it cannot be skipped, and it
    is not editable** (a comment is edited where it stands): a quoted line
    is agent text about to be pasted into a terminal. One text, one source.
    **Both boxes stay short and scroll**, four lines and five: at 40vh they
    took two fifths of a notebook screen.
    `test_the_send_bar_stays_short_and_scrolls`.
    - **A send takes the sent words out of the whole-review box, focused or
      not.** `drawReviewBar` leaves a focused box alone, so the caret does
      not jump; after a Ctrl+Enter there, sent words stayed and began the
      next review. `submitReview` sets the box from what `unsent` leaves,
      and blurs it when empty, so the bar goes.
      `test_ctrl_enter_in_the_whole_review_box_empties_it`.
    `reviewText` has no heading: the reader asked for "# Review"
    to go, and the task-name box went too. `blankReview` is an empty one.
- **A removed diff line gets no `+`**: it has no line in the file, so the
  comment can be neither drawn nor put back. One anchored with a side was
  invisible on the Files tab and still sent.
- **The committed section's new side is HEAD, not the worktree**:
  `base...HEAD` line numbers are not the file's, so anchoring to them was
  wrong when written. `inWorktree` carries a comment through the
  uncommitted section, the map from HEAD to disk; a line gone from disk
  gets no `+`. **The name is carried too**: a moved, uncommitted file is
  listed under its new name, and `laterFile` matches on `old_path`, HEAD's
  side. Matched on `path`, a comment was sent with a name not on disk, and
  the line had a second anchor. `inWorktree` gives path and line, `pathNow`
  the path for a whole-file comment; `diffLineAnchor` is the one way a
  drawn line and `diffAnchors` make an anchor. `goToComment` finds the file
  by `pathNow`, or a shut file under its old name stayed shut.
  `test_a_comment_on_a_file_renamed_since_the_commit_goes_to_the_new_name`.
- **One comment, drawn one way: `putComment`, everywhere.** A person icon,
  the note in the prose face, edit and delete in `.acts` at the right,
  faint until hovered, on a faint tint of the reader's colour: the reader
  chose it from pictures over a blue bar and a box. `full` adds the quoted
  line, for a comment whose line is not drawn above. A Review tab that
  appended its own buttons drifted from the rest. **The words are `.says`,
  not `.note`**: `.note` is the pane's mono, padded quiet line. **The icon
  has no size of its own**: `.comment .icon` gives it 14 px; without it the
  person was as tall as the comment.
- **One anchor, one comment box**: a file in both sections shows a line
  twice, the later `focus()` took keys to a box off screen, and saving the
  visible one passed an empty note, which deletes: the comment was lost.
- **`state.writing` must not outlive its box, nor go before it.** Clear it
  when its file or tab goes, and let the guards ask the DOM (`writingIn`),
  not the flag: a box open on another tab froze a tab with nothing to
  close. Clear it only when the tab changes: `showTab` cleared it for the
  tab on screen (a click on its label, or `3`), and the next poll or pick
  rebuilt the diff and took the text.
  `test_a_click_on_the_tab_on_screen_keeps_a_half_written_comment`.
- **What the reader opened lives outside the node**: `state.diffOpen`,
  like the transcript's `state.open`. A `let open` inside `drawDiffFile`
  was lost on each rebuild, and a big file snapped shut at every save.
  **Keyed by `moreKey`** (what is shown, the half, the path): by path
  alone, shutting a file in one half shut it in the other and followed the
  reader to every commit. `test_a_file_shut_in_one_half_stays_open_in_the_other`.
- **An async answer belongs to the session that asked**: `submitReview`
  blanked whichever review was current when `tmux send-keys` returned, and
  its storage key; the sent review is cleared by its own id. **Only what
  was sent is cleared** (`unsent`, from a copy taken before the send): a
  comment saved during `send-keys` was lost.
  `test_a_comment_saved_while_the_review_is_on_its_way_is_kept`.
- **There is no Session tab, and no bar over the tabs.** The bar said
  branch, pane, model and state, three of them on the chosen row, for 56
  pixels on every tab; the tab after it was used only to jump, and the
  rest went. Jump is an icon at the end of the tab row (`#jump`,
  `ICONS.terminal`), beside the model and the context bar; the name is
  changed on the row. `drawHeader` is the send box, the review's send bar,
  the question bar, the context strip and jump, and nothing else.
  - **A jump that went says so** (`jumpToPane`, `flashOutcome`): a tick in
    the working colour, and the live slot says "jumped to" and the row's
    name. It lands in another window, so a working press looked like
    nothing; the reader asked for a sign. A refused jump shows tmux's error
    and never ticks. `test_a_jump_says_it_went_and_a_failed_one_does_not`.
    `JUMP_TITLE` is defined above the start-up line that reads it: a
    `const` read earlier stops the whole page.
- **Every tab has a loader, and a tab switch goes through it, not
  `draw`**: an empty loader left the tab before on screen (so a tab that
  fetched nothing had `load: null` and `load()` drew for it). A new tab
  that fetches nothing gives a loader that draws.
- **The diff does not rebuild while a comment box is open**: it takes the
  text and moves the code. **Every control that rebuilds waits and says
  why** (`busyWriting`): a pick, the column switch, the base picker, "+" on
  another line, "edit" and "delete" on another comment, and Send; else the
  box went with its text, Send's silently, and a silent no-op reads as
  broken. Wait, never save the box first:
  it may hold half a sentence nobody meant to send. **The `storage` event
  waits too**: it rebuilt a box open with focus elsewhere from the stored
  note. Closing the box draws the tab.
  `test_another_comment_waits_while_a_box_holds_text`,
  `test_send_waits_while_a_box_holds_text`,
  `test_another_window_does_not_rebuild_a_box_that_is_open`.
- **The draft lives in the browser**: a review is yours until you submit
  it, and every browser gets the same page. `recallReview` checks the
  shape of what storage returns: never trust it blindly. **Each window
  listens for the other's `storage` event**: each held the draft in
  memory, and a review sent from one came back on the other's next
  keystroke, written over the cleared storage. The tab redraws only when
  nothing is being typed. A two-window test waits for the write:
  `localStorage` reaches another renderer a moment later.
  `test_a_second_window_takes_up_what_the_first_one_kept`.
