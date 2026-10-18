# The review

Comments, their anchors, the review's send bar, and the draft.

- **A comment is anchored to its path and line (nought for the whole
  file), never to the node it was drawn on**: the Diff tab is rebuilt from
  `state.diff` whenever the agent saves.
- **A comment is a place in a file, not in a diff; there is no "gone" or
  "moved".** The page's guesses went out as the reader's words. The
  message tells the agent to search for the quoted line.
- **The review is written, read and sent on the diff's tab, labelled
  Review** (`data-tab` and the code say `diff`): a tab of its own was used
  only to press send.
  - **The tree lists the comments** (`putCommentList`, `path:line`); a
    click goes to one (`goToComment`), opening a shut file first, and
    **scrolls a frame after that draw**: `putDiffPlace` restores the place
    in a frame and undid an immediate scroll.
    `test_a_comment_in_a_shut_file_is_gone_to_from_anywhere_in_the_pane`.
    `delete review` is on the heading and takes two presses.
  - **Every comment is somewhere on the tab** (`putElsewhere`): one the
    diff does not draw stands under "commented elsewhere", its lines read
    from disk. The message sends every comment.
    - **What the diff draws is worked out from the diff, never asked of
      the pane** (`diffAnchors`): the pane leaves out a comment being
      edited, shut files and files the find box hides.
    - **The lines round a comment elsewhere draw nothing the diff draws**
      (`drawn`, from `fillElsewhere` to `fillDiffFile`, read in
      `putLineReview`), or the comment stands twice.
      `test_a_comment_the_diff_shows_is_not_drawn_again_under_elsewhere`.
    - **The lines are read once; only a changed file is read again**
      (`state.reviewFiles`, `forgetChanged`). A failed read is not kept.
      **A 404 is JSON too**: `readElsewhere` kept a `missing` answer (a
      timed-out `is_listed`) as an empty file for ever.
      `test_a_file_elsewhere_that_was_said_to_be_missing_is_asked_for_again`.
      Lines fill the section's own box (`.offdiff`), and `paintSlices`
      paints a file once a read, or the section jumps. **Asked for on each
      answer of the diff** (`askElsewhere`, from `loadDiff`, #566), **never
      with no comment** (#594): it walked every line every poll for
      nothing. `test_a_review_with_no_comment_walks_no_diff`.
  - **The send bar is the only place a review is sent from** (`#reviewbar`,
    `drawReviewBar`), under the pane, on this tab, while there is a
    review: the whole-review comment (`state.review.overall`), the message
    (`reviewText(false)`), and **Send**. **The message is the preview: it
    cannot be skipped or edited**: a quoted line is agent text about to be
    pasted into a terminal. **Both boxes stay short and scroll**: at 40vh
    they filled a notebook screen.
    `test_the_send_bar_stays_short_and_scrolls`.
    - **A send empties the sent words from the whole-review box, focused
      or not**: `drawReviewBar` leaves a focused box alone, so after
      Ctrl+Enter they began the next review. `submitReview` sets it from
      what `unsent` leaves.
      `test_ctrl_enter_in_the_whole_review_box_empties_it`.
    `reviewText` has no heading and no task name, as the reader asked.
    `blankReview` is an empty one.
- **A removed diff line gets no `+`**: it has no line in the file, so the
  comment could be neither drawn on the Files tab nor put back.
- **The committed section's new side is HEAD, not the worktree**:
  `base...HEAD` line numbers are not the file's. `inWorktree` maps a
  comment through the uncommitted section to disk; a line gone from disk
  gets no `+`. **The name is carried too**: `laterFile` matches a moved
  file on `old_path`, HEAD's side; on `path`, a comment went out under a
  name not on disk. `inWorktree` gives path and line, `pathNow` a
  whole-file comment's path; `diffLineAnchor` is the one way a drawn line
  and `diffAnchors` make an anchor. `goToComment` finds the file by
  `pathNow`, or a renamed shut file stayed shut.
  `test_a_comment_on_a_file_renamed_since_the_commit_goes_to_the_new_name`.
- **One comment, drawn one way: `putComment`, everywhere**: a person icon,
  the note in the prose face, edit and delete in `.acts`, on a faint tint
  of the reader's colour, as the reader chose. `full` adds the quoted line
  where it is not drawn above. A tab with its own buttons drifted. **The
  words are `.says`, not `.note`**, the pane's mono quiet line. **The icon
  has no size of its own**: `.comment .icon` gives it 14 px.
- **One anchor, one comment box**: a line shown in both sections got two,
  `focus()` went to the one off screen, and saving the visible one sent an
  empty note, which deletes.
- **`state.writing` must not outlive its box, nor go before it.** Clear it
  when its file or tab goes, and let guards ask the DOM (`writingIn`), not
  the flag: a stale flag froze a tab. Clear it only when the tab changes:
  a `showTab` to the tab on screen (a click, or `3`) cleared it, and the
  next poll took the text.
  `test_a_click_on_the_tab_on_screen_keeps_a_half_written_comment`.
- **What the reader opened lives outside the node**, in
  `state.diffs.open` (as `state.turns.open`): kept in `drawDiffFile`, it
  was lost at each rebuild. **Keyed by `moreKey`** (what is shown, the
  half, the path): by path alone, shutting a file shut it in the other
  half and on every commit.
  `test_a_file_shut_in_one_half_stays_open_in_the_other`.
- **An async answer belongs to the session that asked**: `submitReview`
  clears the sent review by its own id, not whichever is current when
  `tmux send-keys` returns. **Only what was sent is cleared** (`unsent`,
  from a copy taken before the send), or a comment saved meanwhile is
  lost. `test_a_comment_saved_while_the_review_is_on_its_way_is_kept`.
- **The diff does not rebuild while a comment box is open**: it takes the
  text. **Every control that rebuilds waits and says why** (`busyWriting`):
  a pick, the columns, the base, "+", "edit" and "delete" elsewhere, and
  Send; a silent no-op reads as broken. Never save the box first: it may
  hold half a sentence. **The `storage` event waits too.** Closing the box
  draws the tab.
  `test_another_comment_waits_while_a_box_holds_text`,
  `test_send_waits_while_a_box_holds_text`,
  `test_another_window_does_not_rebuild_a_box_that_is_open`.
- **The draft lives in the browser** until it is sent. `recallReview`
  checks the shape of what storage returns. **Each window listens for the
  other's `storage` event**: a review sent from one came back with the
  other's next keystroke. The tab redraws only when nothing is typed. A
  two-window test waits: `localStorage` reaches another renderer late.
  `test_a_second_window_takes_up_what_the_first_one_kept`.
