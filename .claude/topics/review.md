# The review

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. Comments, the review's send bar, and the draft.

- **A comment is anchored to what it is about** — the path and the line, with
  nought for the whole file — never to the node it was drawn on. The Diff tab is rebuilt from `state.diff` whenever the
  agent saves anything.
- **A comment is a place in a file, not a place in a diff.** There is no
  "gone" or "moved": the page used to work those out and send them as though
  the reader had written them, so a note on a file the agent never touched
  went out saying "this line is no longer in the diff". The message tells the
  agent to search for the quoted line instead.
- **The review is written, read back and sent on one tab, the diff's, and
  its label says Review.** A tab of its own held the message and the send
  button, and later a card per file with the hunks that held a comment; the
  reader used it only to press send, because the comments already stood in
  the diff where they were written. So the diff tab took what it had
  (`data-tab` is still `diff`, and so is the code):
  - **The tree lists the comments** under the files (`putCommentList`), as
    the transcript's map lists rounds: the note's first line and its
    `path:line`, and a click goes to it (`goToComment`), opening its file
    first when it is shut. **It scrolls a frame after the draw** that
    opened the file: `drawDiff` puts the reader's place back in a frame,
    so a scroll at once was undone, and from anywhere but the top only a
    second click went to the comment.
    `test_a_comment_in_a_shut_file_is_gone_to_from_anywhere_in_the_pane`.
    `delete review` stands on the heading and takes
    two presses. A comment is gone to here and never on the Files tab: the
    jump to a line there (`goToLine`, `lineTop`, `showLine`) went with the
    old tab, and nothing else asked for a line.
  - **Every comment is somewhere on the tab** (`putElsewhere`): one the diff
    does not draw -- written on the Files tab, on a file or a line no hunk
    holds, or on another commit than the one picked -- stands under
    "commented elsewhere" at the foot, with the lines round it read from
    disk. The message sends every comment, and a comment it sends that the
    reader cannot see on the tab is a comment sent unread.
    - **What the diff draws is worked out from the diff, never asked of the
      pane** (`diffAnchors`). The pane leaves out more: a comment being
      edited is a box with no anchor, a shut file draws no lines, and the
      find box takes files out. Asked of the pane, each moved a comment to
      "elsewhere", and one being edited stood there beside its own box.
    - **And the lines round a comment elsewhere draw nothing the diff
      draws** (`drawn` on the file `fillElsewhere` hands `fillDiffFile`,
      read in `putLineReview`). A slice reached a line the diff above
      showed with its own comment: the comment stood twice, and "edit" on
      the lower copy opened the box on the upper one.
      `test_a_comment_the_diff_shows_is_not_drawn_again_under_elsewhere`.
    - **The lines are read once, and only a changed file is read again.**
      `state.reviewFiles` is forgotten per file the new diff lists
      (`forgetChanged`) -- a file it does not list cannot have moved --
      and a read that failed is not kept. **A 404 is JSON too**:
      `readElsewhere` kept a `missing` answer, which a timed-out
      `is_listed` also gives, as a file with no lines, and asked no more.
      `test_a_file_elsewhere_that_was_said_to_be_missing_is_asked_for_again`. The lines arriving fill the
      section's own box (`.offdiff`, `fillElsewhere`), not the whole diff,
      and `paintSlices` paints a file once per read. Forgetting every
      file on every diff redrew the whole pane twice a poll while an
      agent worked, and the section jumped under the reader.
  - **The send bar is the only place a review is sent from** (`#reviewbar`,
    `drawReviewBar`), pinned under the pane like the transcript's and shown
    only on this tab and only while there is a review. On top a comment on
    the whole review, typed (`state.review.overall`); under it the message
    as it goes after that comment, `reviewText(false)`, in a box that
    cannot be edited -- a comment is edited where it stands; and **Send**.
    **Both boxes stay short and scroll**, four lines and five: at the send
    box's 40vh they took two fifths of a notebook's screen from the diff.
    `test_the_send_bar_stays_short_and_scrolls`.
    - **A send takes the sent words out of the whole-review box, with the
      focus in it or not.** `drawReviewBar` leaves the box alone while it
      has the focus, so the caret does not jump under the reader's typing.
      Ctrl+Enter sends from inside that box: the sent words stayed in it,
      the bar stayed up, and what was typed next went into
      `state.review.overall` after them, so the next review started with
      words already sent. `submitReview` sets the box from what `unsent`
      leaves, and blurs it when nothing is left, so the bar goes.
      `test_ctrl_enter_in_the_whole_review_box_empties_it`.
    The message is in view beside the button, which is what "the preview
    cannot be skipped" means now. `reviewText` is the message and has no
    heading: the reader asked for "# Review" to go, and the box for naming
    a task went before it, never filled. `blankReview` is an empty one.
- **A removed diff line gets no `+`.** It has no line in the file as it is, so
  there is nowhere for the comment to be drawn and nowhere to put it back. The
  anchor used to carry a side for this, and a comment on a removed line could
  not be shown on the Files tab at all — but was still sent.
- **The committed section's new side is HEAD, not the worktree.** `base...HEAD`
  stops at the last commit, so its line numbers are not the file's. A comment
  there is carried through the uncommitted section — which is exactly the map
  from HEAD to disk — by `inWorktree`, and a line that is no longer on disk
  gets no `+`, like a removed one. Anchoring to HEAD's number was wrong at the
  moment of writing, not because the file moved afterwards.
  **The name is carried too**: a file moved and not committed is listed
  there under its new name, and `laterFile` matches it on `old_path`, the
  name on HEAD's side. Matched on `path`, a comment kept a name not on
  disk, was sent with it, and the same line had a second anchor in the
  other half. `inWorktree` answers the path and the line, `pathNow` the
  path for a comment on the whole file, and `diffLineAnchor` is the one
  way a drawn line and `diffAnchors` make an anchor. `goToComment` finds
  the file by `pathNow` too, or a shut file under its old name stayed shut.
  `test_a_comment_on_a_file_renamed_since_the_commit_goes_to_the_new_name`.
- **One comment, drawn one way.** `putComment` builds it everywhere: a
  person icon, the note in the prose face, and edit and delete in `.acts` at
  the right, faint until the pointer is on it, on a faint tint of the
  reader's colour. It had a blue bar down its left and a box round it, and
  the reader called it ugly and chose this from pictures. `full` adds the
  quoted line, for a comment whose line is not drawn above it. The Review
  tab used to reach into the node it got back and append its own buttons,
  so the two drifted. **The words are `.says`, not `.note`**: `.note` is
  the page's quiet line in a pane, mono and padded, and the reader's words
  stood in the code's face. **The icon has no size of its
  own**: `.comment .icon` gives it 14 px, and a picture without that rule
  showed a person the height of the comment.
- **One anchor, one comment box.** A file in both sections shows the same line
  twice. Two boxes meant the later `focus()` took the keystrokes to a box off
  screen, and saving the visible one passed an empty note — which means
  delete, so the comment was lost in silence.
- **`state.writing` must not outlive its box.** It is cleared when the file or
  the tab it was on goes away, and the guards ask the DOM (`writingIn`) rather
  than the flag: a box open on another tab froze a tab that had nothing on
  screen to close. **Nor may it go before its box**: `showTab` cleared it
  for the tab already on screen too -- a click on its label, or `3` --
  and the box stood with no flag, so the guards let the next poll or pick
  rebuild the diff and take what was typed. It is cleared only when the
  tab changes.
  `test_a_click_on_the_tab_on_screen_keeps_a_half_written_comment`.
- **What the reader opened lives outside the node.** `state.diffOpen`, like the
  transcript's `state.open`. A `let open` inside `drawDiffFile` was thrown away
  on every rebuild, so a big file snapped shut each time the agent saved.
  **It is keyed by `moreKey`**, what is shown, the half and the path: by the
  path alone, a file shut in one half shut in the other on the next save,
  and the choice followed the reader to every commit picked.
  `test_a_file_shut_in_one_half_stays_open_in_the_other`.
- **An async answer belongs to the session that asked.** `submitReview` blanked
  whatever review was current when `tmux send-keys` returned, and removed its
  key from storage. The sent review is cleared by its own id. **And only
  what was sent is cleared** (`unsent`, from a copy taken before the send):
  a comment saved while `send-keys` ran was cleared with the rest and never
  sent. `test_a_comment_saved_while_the_review_is_on_its_way_is_kept`.
- **There is no Session tab, and no bar over the tabs.** The bar said the
  branch, the pane, the model and the state -- three of which the chosen row
  says one column to the left, at a cost of 56 pixels on every tab. The tab
  that took its place held the whole path, the counts, the session's own
  event log, the rate-limit windows, a spend limit and a stop button, and the
  reader used it for one thing: jump. Jump is an icon at the end of the tab
  row (`#jump`, `ICONS.terminal`), beside the model and the context bar; the
  name is changed on the row; the rest went. `drawHeader` is the send box,
  the review's send bar, the question bar, the context strip and jump, and
  nothing else.
  - **A jump that went says so** (`jumpToPane`, `flashOutcome`): the
    button ticks in the working colour for a moment and the live slot says
    "jumped to" and the row's name. The jump happens in another window,
    often on another screen, and a press that worked looked like a key that
    did nothing; the reader asked for a sign. A refused jump shows tmux's
    error and never ticks, not even for a moment.
    `test_a_jump_says_it_went_and_a_failed_one_does_not`. `JUMP_TITLE` is
    defined above the start-up line that reads it: a `const` read earlier
    stops the whole page.
- **Every tab has a loader, and a tab switch goes through it**, not through
  `draw`. A tab that fetched nothing once said `load: null` and `load()`
  drew for it, because an empty loader left the page showing the tab
  before. That tab went; a new one that fetches nothing gives a loader
  that draws.
- **The diff does not rebuild while a comment box is open.** It would take what
  is being typed with it, and move the code the comment is about.
  **Every control that rebuilds waits and says why** (`busyWriting`): a
  pick, the column switch, the base picker, and also "+" on another line,
  "edit" and "delete" on another comment, and Send. Those four did not,
  and the box went with its text -- Send's without a word, into a review
  that did not hold it. Waiting, rather than saving the box first, is how
  the others already behave, and a box may hold half a sentence nobody
  meant to send. **The `storage` event waits too**: it drew the tab when
  the focus was not in a field, and a box open with the focus elsewhere
  was built again from the stored note. Closing the box draws the tab.
  `test_another_comment_waits_while_a_box_holds_text`,
  `test_send_waits_while_a_box_holds_text`,
  `test_another_window_does_not_rebuild_a_box_that_is_open`.
- **The draft lives in the browser.** A review is yours until you submit it, and
  the daemon serves every browser the same page. `recallReview` checks the shape
  of what comes back: storage is not a place to trust blindly. **Two windows
  of one browser share it, so each listens for the other's `storage`
  event**: each held the draft in memory, and a review sent from one came
  back on the other's next keystroke, which wrote its stale copy -- sent
  comments and all -- over the storage the first had just cleared. The tab
  is drawn again only when nothing is being typed into it. A test of two
  windows waits for a write to arrive: `localStorage` reaches another
  renderer a moment later, not at once.
  `test_a_second_window_takes_up_what_the_first_one_kept`.
- **The preview cannot be skipped**, and it is not editable. A quoted line is
  text an agent wrote, about to be pasted into a terminal. One text, one place it
  comes from.
