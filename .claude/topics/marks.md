# The reader's marks and the views

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. `Marks`: names, snoozes, unread, saved turns and reminders, and the views made of them: All unreads and Saved.

- **The reader's marks are one store, `Marks`** (#547): the names and
  `over`, the snoozes, what was seen and since when, the reminders, the
  saved turns. `Marks.load` reads the five files, each through `read_json`
  and one number check (`is_number`); `Marks.onto` is the one place they
  reach a `Session`; `naming` is the one lock every writer takes. Each
  mark had its reader, its own copy of the number check, and its own line
  in `settle`, and a sixth would have copied the shape again. A `Marks()`
  reads nothing, so a `Store` can be made with no files.
  `test_each_mark_survives_a_restart`,
  `test_a_broken_file_of_each_kind_is_no_marks`,
  `test_a_store_can_be_built_with_no_files`.
- **A snooze is a mark on one wait, not a state and not a timer** (#355).
  `Session.snoozed` holds while the session still waits on what it waited
  on when the reader said "not now": `snoozed_at` is that wait's
  `attention_since`. An answer, a turn that ends, a new question -- any
  change -- ends it, so there is no timer to set and no setting for one.
  **Not `settled`**: a second question with no turn between leaves the
  session in the one state, so `settled` did not move and the snooze held
  over a question the reader had not seen.
  `test_a_second_question_in_the_same_wait_wakes_it_too`. A late
  `Notification` about the same wait moves neither, and must not wake it.
  **Every answer to "who needs me" asks `needsYou`** -- `BANDS`,
  `drawCounts` and the tab's icon it picks, `tabTitle` and `notifyAbout` -- and
  never `state === "needs_you"` on its own: one that asks the state still
  shouts about a session the reader put aside, and the page then says two
  things. A snoozed row stands with the ready ones, in their colour, and
  its first line says "snoozed". The row and `ls --json` say `snoozed`; the
  state stays `needs_you`, because the session does still wait, and a
  script that waits on it (`cmd_wait`) must still see that.
  **Only a session that needs you is snoozed**: snoozing one at work would
  hide its next question before anybody saw it, so `verb_snooze` answers
  409 and `toggleSnooze` says why. The snoozes are kept in `snoozed_path`,
  beside the names and written the same way (`Store.snooze`, under
  `naming`), so every browser shares them and a restart keeps them; an
  entry that no longer holds is pruned on the next write. Its POST touches
  no terminal, and carries the token as every POST does.
  `tests/test_store.py`, `test_a_snoozed_session_stops_saying_it_needs_you_until_it_asks_again`.
- **A saved turn is its session and its moment, and the start of its
  words** (#377). `seq` is a place in one reading (topics/transcript,
  the link bullet), so saving the same answer after a resume would make two
  entries, and "open" would land on another block: `Store.save` keys on
  `id` and `ts`, and `landOnBlock` looks the moment up (`goToTs`) and falls
  back on nothing, not on the wrong block. The entry keeps the first
  `SAVED_PREVIEW` characters, so the list (`GET /api/saved`, asked for when
  it opens; the pushes carry only the count) reads no transcript. Kept for
  a session gone from the list, without "open". **A session a saved turn
  or a reminder points at is not forgotten** (#494, `Store.forget_quiet`),
  and the history keeps a month, `SESSION_MAX_AGE`, as far as a start folds
  (`HISTORY_FOLDED`): it kept a week, and the reader's history shrank under
  saved turns that then opened nothing. After a restart a saved turn older
  than the fold still has no session.
  `test_a_session_a_saved_turn_points_at_is_not_forgotten`. `saved_entry` checks every
  entry, from the disk and from a POST alike. **Taking one off needs no
  session** (`POST_VERBS` gives `save` "", and `verb_save` asks `known`
  only to save): registered "known", "done" on a turn of a forgotten
  session was a 404, and the entry could never go.
  - **The bookmark stands in the turn's row of buttons, at its top right**
    (`putSave` into `.turnacts`, #522), last of copy, "txt" and save (#527). In
    the name's column it moved the words: beside "copy" it pushed "copy"
    out, after the name an invisible one moved "claude" out of line with
    the time, and before it the column had to be 64 px. A saved one shows
    without the hover, where the hover shows it (topics/transcript-look).
  - **A prompt the reader typed is saved too** (#403), and its entry
    carries `who: "me"`; an answer carries no `who`, so every entry kept
    before prompts could be saved is still an answer, and `saved_entry`
    refuses any other value. **The card draws it as the transcript
    does**: a prompt in the reader's bluish box (`.bubble.mine`, one rule
    with `.turn.mine .bubble`), an answer as Markdown, and "you" or
    "claude" in the two names' colours (`.feedwho.mine`,
    `.feedwho.claude`). The first version had one face for both, and the
    reader asked for this: out of its transcript a prompt read like an
    answer.
  - **Every block with a link has the bookmark** (#424): a `!` or slash
    command with what it printed (`who: "shell"`, kept as `! cmd` and its
    output, as the transcript shows them), and a message of the harness
    (`"system"`). Prompts alone was the first reading of #403, and the
    reader asked for the rest by name. The card draws each as the
    transcript does: the command in the reader's box in the fixed face
    (`.feedentry .bubble.shell`), the harness's words in the dashed box
    (`.feedentry .bubble.aside`), named by `SAVED_FACES`. `saved_entry`
    takes only the names in `SAVED_WHO`.
    `test_a_command_and_a_system_message_are_saved_too`.
  `test_a_saved_turn_is_its_session_and_its_moment`,
  `test_an_answer_is_saved_and_opened_again_from_the_list`.
- **"All unreads" is the last answer of every unread session, asked for
  when it opens** (#376). The text is `Session.last_answer`, from the
  `Stop` hook's `last_assistant_message` (topics/payloads) -- not read out
  of each transcript, and **not on the row**: a row goes out on every
  change, and an answer can run to pages. `verb_last` hands one over,
  cut at `LAST_MAX`, and `askLast` asks once a session while the feed is
  open. The feed stands in place of the tabs (`state.feed`, `body.infeed`),
  newest first by the row's `ended_at`; `drawFeedLink` redraws it on every
  push, so a session read elsewhere leaves it. **Its way in is one of four
  equal buttons in a row over the list** -- Unread, Saved, Search and
  Commands (#411), each with an icon, the counts in badges (`viewLink`,
  `.views`, #391) -- and all four always there: three lines in three
  styles took a hundred pixels, came and went with their counts and moved
  the list, and "search every session" read as a second filter box.
  **Each view is one entry of `VIEWS`** (#543): its link, icon, word and
  count, its name in the tab row, what it asks for as it opens, and its
  draw. `drawFeed`, `openFeed`, `drawFeedLink`, `drawViewTitle` and
  `toggleView` read the table; `state.feed` was asked in 25 places and
  the toggle written four times, so a fifth view meant ten edits.
  `test_every_view_opens_draws_and_gives_the_session_back` walks it.
  **One row at any width the list is dragged to** (`fitViews`,
  `VIEW_FITS`): the fullest form that fits -- icon, word and count; then
  word and count; then icon and count, the word in the title -- measured
  on every draw and from a `ResizeObserver`, because a word's width is the
  reader's fonts'. A fourth button in one row cut each word to its first
  letter ("U…"), and two rows of two were drawn and refused. The four
  share the row equally (`flex: 1 1 0`), and the row stands 6 px in: the
  reader asked for both. **The row never shrinks** (`flex-shrink: 0`,
  #423): it clips what overflows it, and a flex item that does may shrink
  below its content, so a list long enough to scroll took its overflow
  out of the row and cut its words in half -- 3 px of 13.
  `test_the_views_keep_their_height_when_the_list_scrolls`.
  `test_the_four_views_are_one_row_and_always_there`.
  - **A view stands in the tab row** (`drawViewTitle`, `#viewtitle`,
    #392): its name where the tabs were, and `#ctxslot`, `#modelpop` and
    `#jump` hidden, because the chosen session's model, context, spend and
    jump are not the view's. The heading inside the content said the name
    a second time and is gone. **`#live` stays**: a refusal of "mark read"
    or "done" is said there. **Escape leaves a view** (`leaveFeed`), unless
    it closed a dialog or a menu first, or the filter box took it; there
    was no key for it, though the title says "esc".
    - **A view is marked as one, and says how to leave** (#471, `.back`,
      `#viewclose`, `body.infeed`). "esc · back to the session", faint
      beside the name, was the one way out, and the reader did not see
      that a view stood over the tabs. The bar wears the list's ground, a
      button names the session back goes to (`rowName(current())`, in
      `fresh`'s key so a rename redraws it), and a cross at the bar's end
      closes the view. **The chosen row looks as any row while a view
      stands there, and the grip does not open beside it**: the view is
      not that row's. `openGrip` asks `state.feed`, and `openFeed` and
      `closeFeed` call it at once -- the row's `gripWatch` fires a frame
      later, and a break of the call in `openFeed` stayed green by that
      chance once. A popup over the dimmed page was drawn and turned down:
      it hid the list, and "who needs me" with it.
      `test_a_view_says_where_back_goes_and_closes_like_a_window`.
  - **Every entry is a card, drawn by one helper** (`putCard`, #393): the
    edge in its session's colour (`--hue`, as the row's), the repository,
    worktree and branch under the name (`.feedwhere`), the actions only
    on its hover, `display: none` until then. **A press on the card opens
    it**, as "open" does, but not one on a button, a link or an input, and
    not one that ends a selection: a reader copying a line from an answer
    left the view. Three views each built their entries by hand; one
    helper keeps them alike. A test presses an action after `hover`:
    Playwright waits for a button that is not drawn and never presses it.
  - **The cards stand on a board, as Google Keep's notes** (`putBoard`,
    `layoutCards`, #404, #408): as many columns of at least `CARD_MIN` as
    fit -- 480 px: at 340 a card held a few words a line, and the reader
    saw too little of it (#403) -- each card under the shortest column, so the newest stand along the
    top and read across. One column of 90ch at the left left most of a wide
    screen empty, in all three views. **Placed by hand, not by CSS
    `columns`**: those fill the first column down before the next, so the
    newest were all at the left. The cards keep their order in the page, so
    a test and the keys meet them newest first. A `ResizeObserver` on the
    board and on each card lays out again on the next frame -- a card grows
    when its code is painted, the board when the window does -- and a
    layout inside the observer itself is the loop the browser complains
    of. A word too long for the card breaks in it (`overflow-wrap`): a path
    ran out of the card.
  - **The links on a card's hover take no room** (#405): a `.link` carries
    `margin-top`, and in the card's top line, aligned on the baseline, it
    made the line 3 px taller, so the card grew and every card under it
    moved down. `.feedtop .link` takes the margin off.
  `test_saved_turns_stand_in_columns_and_hold_still_on_hover`.
  - **A search excerpt is text without its Markdown signs** (`unmarked`,
    #395): a fence, a bold and a code tick are dropped on the page, and the
    hits are marked after, on what is shown, so a hit's place cannot drift.
    `__` is kept: it is half of `__init__`. Its `mark` is a tint of
    `--needs`, not the find box's solid `--mark`, which made a page of
    results a page of blocks.
  `test_all_unreads_is_one_scroll_through_the_last_answers`,
  `test_search_every_session_and_open_a_result`. **While it is open nothing
  is read from behind it** (`markSeen` returns): the chosen session's tabs
  are covered. Choosing a session closes it, the one on screen too.
  **A `StopFailure` sets it too**, to Claude Code's sentence about the
  error: kept from the turn before, the feed showed that turn's answer
  under the new time.
  `test_all_unreads_is_one_scroll_through_the_last_answers`,
  `test_a_turn_keeps_what_the_agent_said_last`,
  `test_a_turn_an_error_ended_keeps_the_error_not_the_answer_before`.
- **A reminder is the snooze's twin with a clock, and the clock is the
  page's** (#375). The snooze has no timer on purpose; the reader asked
  for one by name -- Slack's "remind me in 20 min, 1 h, 3 h, tomorrow" --
  and it is a second mark, not a change to the snooze. The daemon keeps
  only the moment (`Store.remind`, `reminders_path`, under `naming`), and
  the row carries it as `remind_at`. **"Due" is never a field**: a row must
  not change by itself (`row`'s rule), so `reminderDue` and `reminderSet`
  compare it with `serverNow`, and `armReminders` wakes the page at the
  next one, which rings it through `onSessions` (`notifyAbout`) and draws
  again.
  - **`needsYou` asks it**: a reminder that has come counts whatever the
    session does; one still to come puts a waiting session aside, with the
    snooze's colours (`.snoozed`). One that has come wears the amber
    (`.reminded`) and the word "reminder", and its alert says "the reminder
    you set". Opening the session ends it (`endReminder`, from `markSeen`).
  - **"not now" only where a snooze can hold**: on a row a reminder brought
    back the session may wait for nothing, and the daemon refuses the
    snooze. "later" stays, to put it off again.
  - **The time stands in the age's place, not in the word**: "until
    20:23" beside the name took the name's room. **After a clock**
    (`.age.when`, #394): "at 09:55" alone did not say it was a reminder,
    and it stays on the hover, because it says when the row comes back.
    One that has come wears its word as an amber pill (`.word.pill`).
  - **The choices are a small menu over the rows below** (`openReminders`,
    `REMIND_IN`), in whole words with a "Remind me" head: four grey
    abbreviations in a line of their own were missed (#394). Absolute in
    the row (`.row` is `position: relative`), so opening it moves no row;
    a press on it between the choices stops there, or it chose the row.
    **They are Slack's** (#406): 30 minutes, 1 and 3 hours, tomorrow and
    Monday at 08:00 (`remindMoment`; on a Monday, "Monday" is next
    week's), and "Custom…" (`customReminder`): a list of days, today
    first, and a box for the time, the next full hour. **Neither is the
    browser's own date or time box**: those write as the browser's
    language does, and the reader saw "10/05/2026" and "06:00 AM" and
    asked for "22:10". The days are `dayName`'s ("Wed 7 Oct"), and the
    time is text on a 24-hour clock (`readTime`: "22:10", "2210", "9").
    **Custom stays open when the pointer leaves the row**: a list's
    open options stand outside the row, and going to them closed it. It closes on its button, Enter, Escape
    -- which go no further, or Escape left a view and Enter opened a row
    -- and a press anywhere else. A moment past is said in the menu, not
    sent.
  - **The route refuses, never clips**: 0, or a moment in the next 31 days
    (`REMIND_MOST`). A week was too short: "Monday at 08:00" on a Monday
    morning is 7 days and more, and the reader asked for a custom day,
    which goes to `REMIND_DAYS` (30) ahead. `False` is 0 to Python and 0
    clears, so a bool is refused as a bool.
    `test_a_reminder_is_a_moment_in_the_next_month_or_nothing`.
  **A test sets a reminder far off, then near**: 3 s from now came before
  a loaded machine had drawn the page, and the first look found it due --
  red twice under two runs at once. The second `remind` and its push are
  also what proves a push sets the page's timer again.
  `test_a_reminder_puts_a_waiting_session_aside_until_it_comes`,
  `test_a_reminder_brings_a_ready_session_back_until_it_is_opened`,
  `test_later_offers_the_choices_and_keeps_the_one_picked`.
- **Unread is a mark on a finished turn, as a snooze is a mark on a wait,
  and it is no state either** (#373). `Session.unread` is a turn that
  ended (`ended_at`, stamped by `Stop` and `StopFailure`) after the reader
  last had the session on screen (`seen_at`), or a mark the reader set:
  `seen_at` -1. They are kept in `seen_path`, beside the snoozes and
  written the same way (`Store.see`, under `naming`), so every browser
  agrees. **The file has a floor**, the moment it was first written, and
  a session not in it was seen then (`read_seen`): without one, the first
  start lit up every row that had ever ended a turn.
  - **What is on screen in a window the reader can see is read**
    (`markSeen`): on a choice, on every push, and when the window comes
    back (`visibilitychange`). **Except the one marked unread while on
    screen** (`state.keptUnread`), until another is chosen: "I looked,
    but I am not done with it" is the whole point of the mark, and a push
    a second later read it again. `test_u_marks_the_session_on_screen_unread_until_another_is_chosen`.
  - **The route pushes nothing, as `name` does**: the next pass builds the
    row from the file and sends it. A full push already on its way carries
    a row built before the mark, so `setUnread` finds the session again
    after the answer instead of writing to the one it started with. **A
    refusal takes the mark back**: the row changes before the answer, and
    a dot for a mark the file never got stood until the next push.
    `test_a_mark_the_daemon_refused_is_taken_back_and_said`.
  - **A dot, and the name bold** (#390). The dot is the colour of a turn
    that is done (`--done`), and what is seen from across a room. A test of
    the dot reads `content` as well as `width`: `getComputedStyle` gives
    the declared width of a `::before` whose content is `none`, and a dot
    nobody can see passed. **Only a name with something to read is bold**:
    unread, needing you, a reminder that came, the chosen one; the rest
    are 500 in `--ink`. Every name was bold, and the dot alone told the
    rows apart. **A test that reads a row the reader just left reads it
    after the daemon's next pass**: a push on its way can carry that row
    as it was before the page read it -- unread, so bold -- and only the
    next pass sends it read. Under load it was bold three runs in six,
    with the daemon's own `unread` already False.
  - "Unread" on a read row is a dot icon on its hover (#389), and `u`
    toggles the chosen one. The tab's title says "2 unread ·" after the
    sessions that need you.
  `test_a_turn_that_ends_after_the_reader_looked_is_unread`,
  `test_turns_that_ended_before_the_file_was_made_are_read`,
  `test_a_turn_that_ends_off_screen_is_unread_until_it_is_opened`.
