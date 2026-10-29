# The reader's marks and the views

`Marks` (names, snoozes, unread, saved turns, reminders) and the views made
of them.

- **The reader's marks are one store, `Marks`** (#547): names and `over`,
  snoozes, seen-since, reminders, saved turns, and the folders added to a
  worktree (#624, `folders`, by the worktree's top, topics/files-tab).
  `Marks.load` reads the six files through `read_json` and one number
  check (`is_number`);
  `Marks.onto` is the one place they reach a `Session`; every writer takes
  the lock `naming`. Each mark once had its own reader and line in
  `settle`. A `Marks()` reads nothing, so a `Store` needs no files.
  `test_each_mark_survives_a_restart`,
  `test_a_broken_file_of_each_kind_is_no_marks`,
  `test_a_store_can_be_built_with_no_files`.
- **A snooze is a mark on one wait, not a state and not a timer** (#355).
  `Session.snoozed` holds while `snoozed_at` equals the wait's
  `attention_since`; any change of the wait ends it. **Not `settled`**: a
  second question with no turn between does not move it, so the snooze hid
  it (`test_a_second_question_in_the_same_wait_wakes_it_too`). A late
  `Notification` about the same wait must not wake it.
  **Every "who needs me" asks `needsYou`** (`BANDS`, `drawCounts`,
  `tabTitle`, `notifyAbout`), never `state === "needs_you"` alone. A
  snoozed row stands with the ready ones and says "snoozed"; the row and
  `ls --json` say `snoozed`, but the state stays `needs_you`, because
  `cmd_wait` must see the wait.
  **Only a session that needs you is snoozed**: on one at work it would
  hide the next question, so `verb_snooze` answers 409 and `toggleSnooze`
  says why. Snoozes live in `snoozed_path` (`Store.snooze`), shared by
  browsers and kept over a restart; the next write prunes a stale one. The
  POST touches no terminal and carries the token. `tests/test_store.py`,
  `test_a_snoozed_session_stops_saying_it_needs_you_until_it_asks_again`.
- **A saved turn is its session, its moment and the start of its words**
  (#377). `seq` is a place in one reading (topics/transcript, the link
  bullet): after a resume it landed on another block. So `Store.save` keys
  on `id` and `ts`; `landOnBlock` looks the moment up (`goToTs`) and lands
  nowhere rather than on the wrong block. The entry keeps
  `SAVED_PREVIEW` characters, so the list (`GET /api/saved`) reads no
  transcript; pushes carry only the count. `saved_entry` checks every
  entry, from disk or a POST.
  **A session a saved turn or a reminder points at is not forgotten**
  (#494, `Store.forget_quiet`). The history keeps a month,
  `SESSION_MAX_AGE`, as far as a start folds (`HISTORY_FOLDED`).
  `test_a_session_a_saved_turn_points_at_is_not_forgotten`.
  **Taking one off needs no session** (`POST_VERBS` gives `save` "";
  `verb_save` asks `known` only to save): else a forgotten session's entry
  could never go.
  - **The bookmark is in the turn's buttons, top right** (`putSave` into
    `.turnacts`, #522), after copy and "txt" (#527): in the name's column
    it moved the words. A saved one shows without hover
    (topics/transcript-look).
  - **Every block with a link has the bookmark, and its card draws it as
    the transcript does** (#403, #424): a prompt (`who: "me"`, in
    `.bubble.mine`, one rule with `.turn.mine .bubble`), an answer (no
    `who`, as Markdown), a `!` or slash command with its output
    (`who: "shell"`, `! cmd`), a harness message (`"system"`), by
    `SAVED_FACES` (`.feedentry .bubble.shell`, `.feedentry .bubble.aside`,
    `.feedwho.mine`, `.feedwho.claude`). `saved_entry` takes only
    `SAVED_WHO`.
    `test_a_command_and_a_system_message_are_saved_too`.
  `test_a_saved_turn_is_its_session_and_its_moment`,
  `test_an_answer_is_saved_and_opened_again_from_the_list`.
- **"All unreads" is the last answer of every unread session, asked for
  when it opens** (#376): `Session.last_answer`, from `Stop`'s
  `last_assistant_message` (topics/payloads), not read from transcripts.
  **Not on the row**: a row goes out on every change, and an answer runs
  to pages. **A `StopFailure` sets it to the error sentence**, else the
  feed showed the previous answer under the new time. `verb_last` cuts at
  `LAST_MAX`; `askLast` asks once a session. The feed covers the tabs
  (`state.feed`, `body.infeed`), newest first by `ended_at`;
  `drawFeedLink` redraws it every push. **While it is open nothing behind
  it is read** (`markSeen` returns).
  **Claude Code's own recap stands over the answer** (#662,
  `away_summary_in`, `putAway`, `.feedaway`), as the reader chose: the
  shortest way back in. Only one written at or after `ended_at`, or a
  recap of an older absence stood over a newer answer. It is read from the
  transcript's end (`tail_records`), when the card asks, never on the
  row; without the words Claude Code adds for its own terminal
  (`AWAY_SAID_TOO`). `test_claude_code_s_recap_is_taken_only_after_the_last_answer`,
  `test_the_last_answer_comes_with_the_recap_since`,
  `test_an_unread_card_says_what_happened_while_you_were_away`.
  `test_all_unreads_is_one_scroll_through_the_last_answers`,
  `test_a_turn_keeps_what_the_agent_said_last`,
  `test_a_turn_an_error_ended_keeps_the_error_not_the_answer_before`.
  **The views are four equal buttons in one row over the list**: Unread,
  Saved, Search, Commands (#411), icons with counts in badges (`viewLink`,
  `.views`, #391), always all there: links that came and went moved the
  list.
  **Each view is one entry of `VIEWS`** (#543): link, icon, word, count,
  title, what it asks on opening, its draw; `drawFeed`, `openFeed`,
  `drawFeedLink`, `drawViewTitle` and `toggleView` read it.
  `test_every_view_opens_draws_and_gives_the_session_back` walks it.
  **One row at any width** (`fitViews`, `VIEW_FITS`): the fullest form
  that fits, measured every draw and by a `ResizeObserver`, because a
  word's width is the reader's font's; equal shares (`flex: 1 1 0`), as
  the reader chose. **The row never shrinks** (`flex-shrink: 0`, #423): it
  clips, so as a flex item it shrank when the list scrolled and halved its
  words.
  `test_the_views_keep_their_height_when_the_list_scrolls`,
  `test_the_four_views_are_one_row_and_always_there`.
  - **A view stands in the tab row** (`drawViewTitle`, `#viewtitle`,
    #392). `#ctxslot`, `#modelpop` and `#jump` hide: they are the
    session's. **`#live` stays**: refusals are said there. **Escape leaves
    a view** (`leaveFeed`), unless it closed a dialog or menu first, or the
    filter box took it.
    - **A view looks like one and says how to leave** (#471, `.back`,
      `#viewclose`, `body.infeed`): the reader missed a faint hint. A
      button names where back goes (`rowName(current())`, in `fresh`'s
      key); a cross closes the view. **While a view stands, the chosen row
      looks plain and the grip does not open**: `openGrip` asks
      `state.feed`, and `openFeed` and `closeFeed` call it at once, because
      `gripWatch` fires a frame later and hid a broken call.
      `test_a_view_says_where_back_goes_and_closes_like_a_window`.
  - **Every entry is a card from one helper** (`putCard`, #393): edge in
    the session's `--hue`, repository, worktree and branch under the name
    (`.feedwhere`), actions `display: none` until hover. **A press on the
    card opens it**, but not one on a button, link or input, nor one that
    ends a selection. A test presses an action after `hover`, or
    Playwright waits for it for ever.
  - **The cards stand on a board** (`putBoard`, `layoutCards`, #404,
    #408): as many columns of `CARD_MIN` (480 px; 340 was too narrow,
    #403) as fit, each card under the shortest column, so the newest read
    across the top. **Placed by hand, not by CSS `columns`**, which fill
    one column first; the page order stays newest first. A
    `ResizeObserver` on the board and each card lays out on the next
    frame: a layout inside the observer loops. A long word breaks
    (`overflow-wrap`).
  - **Hover links on a card take no room** (#405): a `.link`'s
    `margin-top` grew the card 3 px and moved every card below;
    `.feedtop .link` drops it.
    `test_saved_turns_stand_in_columns_and_hold_still_on_hover`.
  - **A search excerpt drops its Markdown signs** (`unmarked`, #395)
    before hits are marked, so marks cannot drift. `__` stays: it is half
    of `__init__`. The `mark` is a tint of `--needs`; solid `--mark` made
    a page of blocks. `test_search_every_session_and_open_a_result`.
- **A reminder is the snooze's twin with a clock, and the clock is the
  page's** (#375): the snooze keeps no timer, so this is a second mark.
  The daemon keeps only the moment (`Store.remind`, `reminders_path`,
  under `naming`); the row carries `remind_at`. **"Due" is never a
  field**: a row must not change by itself (`row`'s rule). `reminderDue`
  and `reminderSet` compare with `serverNow`; `armReminders` wakes the
  page at the next one, which rings through `onSessions` (`notifyAbout`).
  - **`needsYou` asks it**: a reminder that came counts whatever the
    session does; one to come puts a waiting session aside (`.snoozed`).
    One that came wears amber (`.reminded`); opening the session ends it
    (`endReminder`, from `markSeen`).
  - **"not now" shows only where a snooze can hold**: a reminded row may
    wait for nothing. "later" stays.
  - **The time stands in the age's place, after a clock** (`.age.when`,
    #394), not in the word, where it took the name's room. One that came
    wears an amber pill (`.word.pill`).
  - **The choices are a small menu, in words, over the rows below**
    (`openReminders`, `REMIND_IN`, #394); absolute in the row (`.row` is
    `position: relative`), so no row moves. A press between choices stops
    there, or it chose the row. **They are Slack's** (#406,
    `remindMoment`), plus "Custom…" (`customReminder`). **Never the
    browser's date or time box**: it says "06:00 AM"; the reader asked for
    "22:10". Days are `dayName`'s; times are 24-hour text (`readTime`).
    **Custom stays open when the pointer leaves the row**; its Enter and
    Escape go no further, or Escape left a view and Enter opened a row. A
    past moment is said, not sent.
  - **The route refuses, never clips**: 0, or a moment within
    `REMIND_MOST` (31 days); a week was too short for Monday's on a Monday,
    and a custom day goes `REMIND_DAYS` ahead. `False` is 0 and 0 clears,
    so a bool is refused.
    `test_a_reminder_is_a_moment_in_the_next_month_or_nothing`.
  **A test sets a reminder far off, then near**: one 3 s away came due
  before a loaded machine drew the page. The second `remind` proves a push
  re-arms the timer.
  `test_a_reminder_puts_a_waiting_session_aside_until_it_comes`,
  `test_a_reminder_brings_a_ready_session_back_until_it_is_opened`,
  `test_later_offers_the_choices_and_keeps_the_one_picked`.
- **Unread is a mark on a finished turn, not a state** (#373).
  `Session.unread` is a turn that ended (`ended_at`, from `Stop` and
  `StopFailure`) after the session was last on screen (`seen_at`), or the
  reader's mark, `seen_at` -1. Kept in `seen_path` (`Store.see`). **The
  file has a floor**, its first write; a session not in it was seen then
  (`read_seen`). Without it, the first start lit every row.
  - **What is on screen in a visible window is read** (`markSeen`): on a
    choice, every push, and `visibilitychange`. **Except one marked unread
    while on screen** (`state.keptUnread`), until another is chosen, or
    the next push reads it again.
    `test_u_marks_the_session_on_screen_unread_until_another_is_chosen`.
  - **The route pushes nothing, as `name` does**: the next pass sends the
    row. A push on its way carries a row from before the mark, so
    `setUnread` looks the session up again after the answer. **A refusal
    takes the mark back**, or a dot the file never got stood until the next
    push. `test_a_mark_the_daemon_refused_is_taken_back_and_said`.
  - **A dot (`--done`), and the name bold** (#390). A dot test reads
    `content` as well as `width`: `getComputedStyle` gives a `::before`
    its width even when content is `none`. **Only a name with something to
    read is bold**: unread, needs you, a reminder that came, the chosen
    one; the rest are 500 in `--ink`. **A test of a row just left reads it
    after the daemon's next pass**: a push on its way may carry it bold,
    though `unread` is False.
  - `u` toggles the chosen one; the row's hover icons do too
    (topics/sidebar, #389). The tab's title says "2 unread ·".
  `test_a_turn_that_ends_after_the_reader_looked_is_unread`,
  `test_turns_that_ended_before_the_file_was_made_are_read`,
  `test_a_turn_that_ends_off_screen_is_unread_until_it_is_opened`.
