# The reader's marks and the views

`Marks`: names, snoozes, unread, saved turns, reminders, and the views made of them: All unreads and Saved.

- **The reader's marks are one store, `Marks`** (#547): names and `over`,
  snoozes, seen-since, reminders, saved turns. `Marks.load` reads the five
  files, each through `read_json` and one number check (`is_number`);
  `Marks.onto` is the one place they reach a `Session`; `naming` is the one
  lock every writer takes. Each mark had its own reader, number check and
  line in `settle`, and a sixth would have copied them. A `Marks()` reads
  nothing, so a `Store` needs no files.
  `test_each_mark_survives_a_restart`,
  `test_a_broken_file_of_each_kind_is_no_marks`,
  `test_a_store_can_be_built_with_no_files`.
- **A snooze is a mark on one wait, not a state and not a timer** (#355).
  `Session.snoozed` holds while the session waits on what it waited on at
  "not now": `snoozed_at` is that wait's `attention_since`. Any change -- an
  answer, a turn's end, a new question -- ends it, so there is no timer and
  no setting. **Not `settled`**: a second question with no turn between
  leaves the state as it was, so `settled` did not move and the snooze hid
  an unseen question (`test_a_second_question_in_the_same_wait_wakes_it_too`).
  A late `Notification` about the same wait moves neither and must not wake
  it.
  **Every answer to "who needs me" asks `needsYou`** (`BANDS`, `drawCounts`
  and the tab's icon, `tabTitle`, `notifyAbout`), never
  `state === "needs_you"` alone: that shouts about a session the reader put aside, and
  the page says two things. A snoozed row stands with the ready ones, in
  their colour; its first line says "snoozed". The row and `ls --json` say
  `snoozed`; the state stays `needs_you`, because the session still waits
  and `cmd_wait` must see that.
  **Only a session that needs you is snoozed**: snoozing one at work would
  hide its next question unseen, so `verb_snooze` answers 409 and
  `toggleSnooze` says why. Snoozes live in `snoozed_path`, written as the
  names are (`Store.snooze`, under `naming`), so every browser shares them
  and a restart keeps them; a stale entry is pruned on the next write. Its
  POST touches no terminal and carries the token.
  `tests/test_store.py`, `test_a_snoozed_session_stops_saying_it_needs_you_until_it_asks_again`.
- **A saved turn is its session, its moment and the start of its words**
  (#377). `seq` is a place in one reading (topics/transcript, the link
  bullet): after a resume it made a second entry and "open" landed on
  another block. So `Store.save` keys on `id` and `ts`, and `landOnBlock`
  looks the moment up (`goToTs`) and falls back on nothing, never the wrong
  block. The entry keeps the first `SAVED_PREVIEW` characters, so the list
  (`GET /api/saved`, asked for on opening; pushes carry only the count)
  reads no transcript. An entry whose session left the list stays, without
  "open". `saved_entry` checks every entry, from disk or a POST.
  **A session a saved turn or a reminder points at is not forgotten**
  (#494, `Store.forget_quiet`), and the history keeps a month,
  `SESSION_MAX_AGE`, as far as a start folds (`HISTORY_FOLDED`): at a week,
  saved turns opened nothing. A saved turn older than the fold still has no
  session after a restart.
  `test_a_session_a_saved_turn_points_at_is_not_forgotten`.
  **Taking one off needs no session** (`POST_VERBS` gives `save` "";
  `verb_save` asks `known` only to save): registered "known", "done" on a
  forgotten session was a 404 and the entry could never go.
  - **The bookmark stands in the turn's row of buttons, top right**
    (`putSave` into `.turnacts`, #522), after copy and "txt" (#527). In the
    name's column it moved the words wherever it stood, or needed a 64 px
    column. A saved one shows without the hover, where the
    hover shows it (topics/transcript-look).
  - **A prompt the reader typed is saved too** (#403), with `who: "me"`. An
    answer has no `who`, so every older entry is an answer; `saved_entry`
    refuses any other value. **The card draws it as the transcript does**,
    as the reader asked (a prompt read like an answer): a prompt in the
    bluish box (`.bubble.mine`, one rule with `.turn.mine .bubble`), an
    answer as Markdown, "you" or "claude" in the names' colours
    (`.feedwho.mine`, `.feedwho.claude`).
  - **Every block with a link has the bookmark** (#424), as the reader asked
    by name: a `!` or slash command with its output (`who: "shell"`, kept
    as `! cmd` and its output), and a harness message (`"system"`). The
    card draws each as the transcript does: the command in the reader's box
    in the fixed face (`.feedentry .bubble.shell`), the harness's words in
    the dashed box (`.feedentry .bubble.aside`), by `SAVED_FACES`.
    `saved_entry` takes only names in `SAVED_WHO`.
    `test_a_command_and_a_system_message_are_saved_too`.
  `test_a_saved_turn_is_its_session_and_its_moment`,
  `test_an_answer_is_saved_and_opened_again_from_the_list`.
- **"All unreads" is the last answer of every unread session, asked for
  when it opens** (#376). The text is `Session.last_answer`, from the
  `Stop` hook's `last_assistant_message` (topics/payloads), not read from
  each transcript, and **not on the row**: a row goes out on every change,
  and an answer runs to pages. **A `StopFailure` sets it too**, to Claude
  Code's error sentence: else the feed showed the turn before's answer
  under the new time. `verb_last` hands one over, cut at `LAST_MAX`;
  `askLast` asks once a session while the feed is open. The feed replaces
  the tabs (`state.feed`, `body.infeed`), newest first by `ended_at`;
  `drawFeedLink` redraws it every push, so a session read elsewhere leaves
  it. **While it is open nothing is read from behind it** (`markSeen`
  returns): the tabs are covered. Choosing a session closes it, the one on
  screen too.
  `test_all_unreads_is_one_scroll_through_the_last_answers`,
  `test_a_turn_keeps_what_the_agent_said_last`,
  `test_a_turn_an_error_ended_keeps_the_error_not_the_answer_before`.
  **Its way in is one of four equal buttons in a row over the list**:
  Unread, Saved, Search, Commands (#411), each an icon, counts in badges
  (`viewLink`, `.views`, #391), all four always there. Three links in three
  styles took 100 px and moved the list as counts came and went, and search
  read as a second filter box.
  **Each view is one entry of `VIEWS`** (#543): link, icon, word, count,
  name in the tab row, what it asks for on opening, its draw. `drawFeed`,
  `openFeed`, `drawFeedLink`, `drawViewTitle` and `toggleView` read the
  table: before, a fifth view meant ten edits.
  `test_every_view_opens_draws_and_gives_the_session_back` walks it.
  **One row at any list width** (`fitViews`, `VIEW_FITS`): the fullest form
  that fits -- icon, word, count; word, count; icon, count with the word in
  the title -- measured every draw and by a `ResizeObserver`, since a
  word's width is the reader's font's. A fourth button cut each word to "U…";
  two rows of two were refused. The reader chose equal shares
  (`flex: 1 1 0`) and the row 6 px in. **The row never shrinks**
  (`flex-shrink: 0`, #423): it clips its overflow, so as a flex item it shrank below its
  content when the list scrolled, and cut its words in half.
  `test_the_views_keep_their_height_when_the_list_scrolls`,
  `test_the_four_views_are_one_row_and_always_there`.
  - **A view stands in the tab row** (`drawViewTitle`, `#viewtitle`, #392):
    its name where the tabs were; `#ctxslot`, `#modelpop` and `#jump`
    hidden, because the session's model, context, spend and jump are not
    the view's. No heading in the content: it said the name twice. **`#live`
    stays**: a refusal of "mark read" or "done" is said there. **Escape
    leaves a view** (`leaveFeed`), unless it closed a dialog or menu first,
    or the filter box took it.
    - **A view is marked as one, and says how to leave** (#471, `.back`,
      `#viewclose`, `body.infeed`): a faint "esc · back to the session" was
      the one way out, and the reader did not see a view over the tabs. The bar
      wears the list's ground, a button names where back goes
      (`rowName(current())`, in `fresh`'s key so a rename redraws it), and
      a cross at its end closes the view. **While a view stands, the chosen
      row looks as any row and the grip does not open**: the view is not
      that row's. `openGrip` asks `state.feed`; `openFeed` and `closeFeed`
      call it at once, because the row's `gripWatch` fires a frame later
      and hid a broken call. A popup over the dimmed page was refused: it
      hid the list, and who needs you.
      `test_a_view_says_where_back_goes_and_closes_like_a_window`.
  - **Every entry is a card, drawn by one helper** (`putCard`, #393), so
    three views stay alike: the edge in its session's colour (`--hue`), the
    repository, worktree and branch under the name (`.feedwhere`), actions
    only on hover, `display: none` until then. **A press on the card opens
    it**, but not one on a button, link or input, nor one that ends a
    selection: copying a line left the view. A test presses an action after
    `hover`: Playwright waits for an undrawn button and never presses it.
  - **The cards stand on a board, as Google Keep's notes** (`putBoard`,
    `layoutCards`, #404, #408): as many columns of at least `CARD_MIN`
    (480 px; 340 showed too little, #403) as fit, each card under the
    shortest column, so the newest read across the top. One 90ch column
    left a wide screen empty. **Placed by hand, not by CSS `columns`**:
    those fill one column down first, so the newest were all at the left.
    The page order stays newest first, for tests and keys. A
    `ResizeObserver` on the board and each card lays out on the next frame
    (a card grows when its code paints, the board with the window); a layout
    inside the observer loops. A long word breaks (`overflow-wrap`): a path
    ran out of the card.
  - **The links on a card's hover take no room** (#405): a `.link`'s
    `margin-top` on the card's baseline-aligned top line made the card 3 px
    taller and moved every card below. `.feedtop .link` drops it.
    `test_saved_turns_stand_in_columns_and_hold_still_on_hover`.
  - **A search excerpt is text without its Markdown signs** (`unmarked`,
    #395): fences, bold and code ticks are dropped first, and hits are
    marked on what is shown, so they cannot drift. `__` stays: it is half of
    `__init__`. Its `mark` is a tint of `--needs`; the find box's solid
    `--mark` made the results a page of blocks.
    `test_search_every_session_and_open_a_result`.
- **A reminder is the snooze's twin with a clock, and the clock is the
  page's** (#375). The snooze has no timer on purpose; the reader asked for
  Slack's reminders by name, so it is a second mark, not a change to the
  snooze. The daemon keeps only the moment (`Store.remind`,
  `reminders_path`, under `naming`); the row carries `remind_at`. **"Due" is
  never a field**: a row must not change by itself (`row`'s rule), so
  `reminderDue` and `reminderSet` compare with `serverNow`, and
  `armReminders` wakes the page at the next one, which rings through
  `onSessions` (`notifyAbout`) and draws again.
  - **`needsYou` asks it**: a reminder that came counts whatever the session
    does; one to come puts a waiting session aside, in the snooze's colours
    (`.snoozed`). One that came wears amber (`.reminded`) and the word
    "reminder"; its alert says "the reminder you set". Opening the session
    ends it (`endReminder`, from `markSeen`).
  - **"not now" only where a snooze can hold**: a row a reminder brought
    back may wait for nothing, and the daemon refuses the snooze. "later"
    stays, to put it off again.
  - **The time stands in the age's place, not in the word**: "until 20:23"
    took the name's room. **After a clock** (`.age.when`, #394): "at 09:55"
    alone did not say reminder; it stays on hover, as it says when the row
    returns. One that came wears its word as an amber pill (`.word.pill`).
  - **The choices are a small menu over the rows below** (`openReminders`,
    `REMIND_IN`), in whole words under "Remind me": four grey abbreviations
    on their own line were missed (#394). Absolute in the row (`.row` is
    `position: relative`), so it moves no row; a press between choices
    stops there, or it chose the row. **They are Slack's** (#406): 30
    minutes, 1 and 3 hours, tomorrow and Monday at 08:00 (`remindMoment`; on
    a Monday, next week's), and "Custom…" (`customReminder`): days from
    today, and a time box at the next full hour. **Neither is the browser's
    date or time box**: those follow the browser's language ("06:00 AM"),
    and the reader asked for "22:10". Days are `dayName`'s ("Wed 7 Oct");
    the time is 24-hour text (`readTime`: "22:10", "2210", "9"). **Custom
    stays open when the pointer leaves the row**: a list's open options
    stand outside it. It closes on its button, Enter, Escape -- which go no
    further, or Escape left a view and Enter opened a row -- and a press
    elsewhere. A past moment is said in the menu, not sent.
  - **The route refuses, never clips**: 0, or a moment in the next 31 days
    (`REMIND_MOST`). A week was too short for "Monday at 08:00" on a Monday
    morning, and a custom day goes `REMIND_DAYS` (30) ahead. `False` is 0 to
    Python and 0 clears, so a bool is refused.
    `test_a_reminder_is_a_moment_in_the_next_month_or_nothing`.
  **A test sets a reminder far off, then near**: one 3 s away came due
  before a loaded machine drew the page. The second `remind` and its push
  also prove a push re-arms the page's timer.
  `test_a_reminder_puts_a_waiting_session_aside_until_it_comes`,
  `test_a_reminder_brings_a_ready_session_back_until_it_is_opened`,
  `test_later_offers_the_choices_and_keeps_the_one_picked`.
- **Unread is a mark on a finished turn, as a snooze is on a wait, and no
  state either** (#373). `Session.unread` is a turn that ended (`ended_at`,
  stamped by `Stop` and `StopFailure`) after the reader last had the
  session on screen (`seen_at`), or the reader's mark: `seen_at` -1. Kept
  in `seen_path`, written as the snoozes are (`Store.see`, under `naming`),
  so every browser agrees. **The file has a floor**, the moment it was
  first written, and a session not in it was seen then (`read_seen`):
  without it, the first start lit every row that ever ended a turn.
  - **What is on screen in a visible window is read** (`markSeen`): on a
    choice, every push, and when the window returns (`visibilitychange`).
    **Except one marked unread while on screen** (`state.keptUnread`),
    until another is chosen: "I looked, but I am not done" is the mark's
    point, and the next push read it again.
    `test_u_marks_the_session_on_screen_unread_until_another_is_chosen`.
  - **The route pushes nothing, as `name` does**: the next pass sends the
    row from the file. A full push on its way carries a row built before
    the mark, so `setUnread` finds the session again after the answer,
    not the object it started with. **A refusal takes the mark back**: the
    row changes before the answer, and a dot the file never got stood
    until the next push.
    `test_a_mark_the_daemon_refused_is_taken_back_and_said`.
  - **A dot, and the name bold** (#390). The dot is `--done`, seen across a
    room. A dot test reads `content` as well as `width`: `getComputedStyle`
    gives a `::before` its declared width even when content is `none`, so
    an invisible dot passed. **Only a name with something to read is
    bold**: unread, needs you, a reminder that came, the chosen one; the
    rest are 500 in `--ink`. With every name bold, only the dot told rows
    apart. **A test of a row the reader just left reads it after the
    daemon's next pass**: a push on its way can carry it as before the read
    -- bold -- though the daemon's `unread` is already False.
  - `u` toggles the chosen one; the row's own way is its hover icons
    (topics/sidebar, #389). The tab's title says "2 unread ·" after who
    needs you.
  `test_a_turn_that_ends_after_the_reader_looked_is_unread`,
  `test_turns_that_ended_before_the_file_was_made_are_read`,
  `test_a_turn_that_ends_off_screen_is_unread_until_it_is_opened`.
