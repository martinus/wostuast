# The sidebar

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. The session list, its rows, the tab's title and icon, the settings menu.

- **It is grouped by state, and newest first inside a group.** The four
  groups are `BANDS`, most urgent first: needs you, working, ready, history.
  **Working sits above ready**, which is the reader's own order: an agent
  still going is something you may want to look in on, and one waiting at its
  prompt has finished with you. Ready was second for a while, on the reading
  that a session wanting a prompt is nearer to wanting you — it is not,
  because nothing about it is waiting.
  This supersedes the old rule that the list must never sort by state — that
  was written when sorting by state churned the list for nothing. A row
  arriving under "needs you" is the one thing this tool exists to say, and it
  only moves when a turn begins, ends, or stops on a question. **Inside a
  group the daemon's order stands**, which is by `Session.settled`, newest
  first.
- **`settled` is not `since`, and that is the whole point.** `since` is the
  last event, which for a working session moves every few seconds: two busy
  agents would swap places while you read them. `settled` is the moment the
  session last *became* what it is — a turn beginning, ending, or stopping on
  a question — which is when the row changes band anyway, so the list moves
  once rather than twice. It is stamped in one place, `Store.apply`, and only
  on a change: every handler assigns a state whether or not it is a new one,
  and `_on_pre_tool` writes "working" on every tool call. `_bury` is the one
  place outside `apply` that stamps it, because nothing reports being dead.
  **And once for a session nothing has stamped**: `SessionStart` is done to
  done, so `settled` fell back to the last event, and an idle notification
  moved a row that had not changed.
  `test_a_session_that_never_changed_state_keeps_its_place`.
  The worktree is the tiebreaker only. Sorting on `label` is still wrong, for
  the reason it always was: the name arrives from the status line a second
  after the session starts, and `/rename` changes it later.
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
  hide its next question before anybody saw it, so `Serving.snooze` answers
  409 and `toggleSnooze` says why. The snoozes are kept in `snoozed_path`,
  beside the names and written the same way (`Store.snooze`, under
  `naming`), so every browser shares them and a restart keeps them; an
  entry that no longer holds is pruned on the next write. Its POST touches
  no terminal, and carries the token as every POST does.
  `tests/test_store.py`, `test_a_snoozed_session_stops_saying_it_needs_you_until_it_asks_again`.
- **A saved turn is its session and its moment, and the start of its
  words** (#377). `seq` is a place in one reading (topics/daemon-and-page,
  the link bullet), so saving the same answer after a resume would make two
  entries, and "open" would land on another block: `Store.save` keys on
  `id` and `ts`, and `landOnBlock` looks the moment up (`goToTs`) and falls
  back on nothing, not on the wrong block. The entry keeps the first
  `SAVED_PREVIEW` characters, so the list (`GET /api/saved`, asked for when
  it opens; the pushes carry only the count) reads no transcript. Kept for
  a session gone from the list, without "open". `saved_entry` checks every
  entry, from the disk and from a POST alike. **Taking one off needs no
  session** (`POST_VERBS` gives `save` "", and `Serving.save` asks `known`
  only to save): registered "known", "done" on a turn of a forgotten
  session was a 404, and the entry could never go.
  - **The bookmark stands before the name** (`putSave`): the column is
    64 px and right-aligned. A word beside "copy" pushed "copy" out of it;
    after the name, an invisible bookmark moved "claude" out of line with
    the time; in the gap beside the words, it touched them.
  `test_a_saved_turn_is_its_session_and_its_moment`,
  `test_an_answer_is_saved_and_opened_again_from_the_list`.
- **"All unreads" is the last answer of every unread session, asked for
  when it opens** (#376). The text is `Session.last_answer`, from the
  `Stop` hook's `last_assistant_message` (topics/payloads) -- not read out
  of each transcript, and **not on the row**: a row goes out on every
  change, and an answer can run to pages. `Serving.last` hands one over,
  cut at `LAST_MAX`, and `askLast` asks once a session while the feed is
  open. The feed stands in place of the tabs (`state.feed`, `body.infeed`),
  newest first by the row's `ended_at`; `drawFeedLink` redraws it on every
  push, so a session read elsewhere leaves it. **Its way in is one of three
  equal buttons in a row over the list** -- Unread, Saved, Search, each
  with an icon, the counts in badges (`viewLink`, `.views`, #391) -- and
  all three always there: three lines in three styles took a hundred
  pixels, came and went with their counts and moved the list, and
  "search every session" read as a second filter box.
  `test_the_three_views_are_one_row_and_always_there`.
  - **A view stands in the tab row** (`drawViewTitle`, `#viewtitle`,
    #392): its name where the tabs were, and `#ctxslot`, `#modelpop` and
    `#jump` hidden, because the chosen session's model, context, spend and
    jump are not the view's. The heading inside the content said the name
    a second time and is gone. **`#live` stays**: a refusal of "mark read"
    or "done" is said there. **Escape leaves a view** (`leaveFeed`), unless
    it closed a dialog or a menu first, or the filter box took it; there
    was no key for it, though the title says "esc".
  - **Every entry is a card, drawn by one helper** (`putCard`, #393): the
    edge in its session's colour (`--hue`, as the row's), the repository,
    worktree and branch under the name (`.feedwhere`), the actions only
    on its hover, `display: none` until then. **A press on the card opens
    it**, as "open" does, but not one on a button, a link or an input, and
    not one that ends a selection: a reader copying a line from an answer
    left the view. Three views each built their entries by hand; one
    helper keeps them alike. A test presses an action after `hover`:
    Playwright waits for a button that is not drawn and never presses it.
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
  next one and draws again, which rings it through `notifyAbout`.
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
  - **The route refuses, never clips**: 0, or a moment in the next week
    (`REMIND_MOST`). `False` is 0 to Python and 0 clears, so a bool is
    refused as a bool. `test_a_reminder_is_a_moment_in_the_next_week_or_nothing`.
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
- **There are four states, not five.** "starting" is gone: it was the first
  few minutes of a session that had said nothing else, which is the same as
  being ready, told in a way that went stale. `SessionStart` sets `done`, and
  `mark_idle` and `STARTING_MAX` went with it. The word for `done` is "ready".
- **The fold is not a filter.** Finished sessions fold under the history bar, but
  they are still counted, the filter still searches them, and the chosen one is
  never missing from the list it is chosen in.
- **There are two alerts, and they are not one switch.** An agent that needs
  you cannot go on without you; an agent that has finished is a turn you can
  read. One switch would mean taking the one you want with the one you do
  not. `alertsWanted()` reads both from our `settings.json`, like the
  theme, whose shape the daemon has checked (`config_trouble`). The
  browser's permission stays the browser's. **Needs-you is on the moment
  alerts are**: it is what this tool exists to say, so a browser that has
  already granted permission, under a file that says nothing, gets it
  without asking.
- **"Finished" is a change, not a state.** `done` is where a session sits
  between turns, so a rule reading the state would say it again on every
  push. `wasDoing` holds what each session was doing last pass, and it is
  written **on every pass whatever the switches say**: ticking the box while
  an agent is working still tells you when it stops, and a session that
  reached `done` while nobody was listening is already at `done` rather than
  a change waiting to be announced. `waiting` is the same promise for amber
  -- **whenever the needs-you alert is not sent**, not only while alerts are
  not allowed: filled on that path alone, ticking the one switch back on
  said every row that had gone amber meanwhile
  (`test_turning_needs_you_on_brings_no_backlog`). **And every alert says
  `renotify`**: one tag per session means a second alert replaces the
  first, and a replacement makes no sound and shows no banner unless it
  asks to (`test_every_alert_makes_itself_heard`).
  A test that only turns the switch on *after* a turn ends proves neither —
  it passes with the recording moved inside the switch. The one that bites
  ticks the box mid-turn.
- **An alert says what, where, and in the colour of what** (`tellAbout`,
  issue 330). It said "needs you" and the bare `reason`, with no picture,
  and went away on its own. Now:
  - **What**: the question itself, from `asking` (`waitsFor`) -- the
    `reason` names only its header -- or the `reason` of a permission; for
    a finished session, the prompt it finished (`shown_prompt`).
  - **Where**: the folder and the branch, the row's second line.
  - **The tab's robot** (`iconPicture`, the one drawing `drawIcon` uses),
    amber for needs-you, grey for finished.
  - **Needs-you stays until it is clicked or closed**
    (`requireInteraction`): one that went while the reader was in another
    room said nothing to them. Finished goes on its own: nothing waits.
  - **Nothing the agent or the reader wrote goes out whole.** An alert can
    stand on a locked screen, so the prompt is `clip_hidden` to
    `PROMPT_SHOWN`, and a permission is the `reason`, hidden already --
    never the dialog's `fields`. **Once a prompt, not once a row**:
    `clip_hidden` costs 170 µs on 500 characters, and a row is built for
    every session on every tick; at the prompt event every prompt of a long
    log paid it again at start. `Session.prompt_shown` keeps it with the
    prompt it was made from.
  `test_an_alert_that_needs_you_says_what_and_where_and_stays`,
  `test_a_question_is_said_as_the_question`,
  `test_a_finished_agent_says_what_it_finished_and_goes`,
  `test_the_shown_prompt_is_worked_out_once_a_prompt`.
- **The counts are about every session.** `drawCounts` runs *before* the guard
  that asks whether the shown rows changed — behind it, a session the filter
  hides could go amber and reach the title, icon and notification: none of them.
  **They are not on the page itself**: a strip over it said "1 ready" and
  "3 sessions" beside groups that already said so, and the reader asked for
  the room. The browser tab's title and icon, and the alerts, are what count.
  - **The title names who needs you, and leads with it** (`tabTitle`):
    "fix-login asks", "fix-login, api-retry +1 need you", or else "2
    working", "4 ready". A tab cuts its title's end off, and it said "(1)
    needs you" -- leaving you to look for whom -- and "wostuast" alone over
    four agents sitting ready. The names are `rowName`'s, so the tab and the
    list agree. **So are the alerts'** (`notifyAbout`): they used `label`,
    which leads with the title Claude Code writes, and so named a session
    that was not in the list.
    `test_an_alert_names_the_session_as_its_row_does`.
  - **The icon is a robot, and the whole of it is the state**
    (`paintIcon`): the bar's own ink when nothing waits, because "ready" is
    not news, green, amber. The reader chose it from pictures. It was a dot
    in the state's colour, and "ready" was the blue of the Jira and
    Bitbucket tabs beside it; a dot said nothing about what the tab was.
    Then a robot over a status line in the state's colour, and the line was
    too thin to see in a tab bar. One eye is big and one small, for a look
    that doubts a little, over a wide, quiet smile -- all cut out, so either
    bar shows through them.
  - **It follows the browser's light or dark, never the page's theme**
    (`tabBarIsDark`, the `--tab-*` colours, which no theme block sets). It
    stands in the browser's tab bar: painted from the page's palette, a page
    set to light in a dark browser put a dark robot on a dark bar. The
    media query's `change` redraws it, whatever the page's theme is.
  `test_the_tab_title_names_who_needs_you`,
  `test_the_tab_icon_is_a_robot_in_the_states_colour`,
  `test_the_tab_icon_says_the_state_in_the_bar_it_stands_in`,
  `test_the_tab_icon_follows_the_browser_and_not_the_page`.
- **There is no bar across the top.** The name and the version head the
  session list (`.sidebar-head`, as tall as `.tabs`, so the two rules under
  them are one line), and the settings are one icon at the end of the tab
  row, its words in `aria-label` and `title`. The version is
  `own_version`: the day the running file was written -- for a copy
  `install` fetched, the day of its commit, in UTC -- and the start of its
  SHA-256: never a number to raise by hand, and the same bytes
  `install_behind` compares. `--version` prints the same (#344).
  `test_the_tabs_start_at_the_top_and_the_name_heads_the_session_list`,
  `test_the_page_says_which_copy_is_running`.
  - **Every setting is one menu** (`putSettings`, `paintSettings`,
    `#setpop`): the colours, the two alerts, the tab width, long lines, the
    diff's columns and the ticket links, with the path of the file that
    keeps them at its foot (`#settingspath`, and a button that copies it).
    It was a bell, a colours button, a menu on the Review bar and two links
    over every file, and the reader chose one menu from pictures. **The
    labels are one word** -- "tab", "lines", "diff", "links", not "tab
    width", "long lines", "diff columns", "ticket links" -- because the
    reader asked for the room. **It is
    one proportional face, `--sans`, labels and buttons too**: the reader
    asked, because a url in the fixed face made the menu as wide as the
    longest link. **A choice is shown at once, then kept** (`keepSetting`,
    `POST /api/settings`), and **made so by the push** (`takeSettings` on
    the `settings` event). **The POST's answer carries no settings**, only
    `done` and the `refused` links: the pushes go out in the order the file
    was written, under `config_lock`, and an answer that carried the
    settings came on another connection, landed before an older push, and
    was undone by it. A numbering of the pushes was tried for that and
    taken out again: one line needs no numbers. Every open page gets the
    push, the one that made the change too, and a hand edit of the file
    arrives the same way (`tell_config`). A change of the diff's columns from the file waits
    while a comment is being written (`takeSides`), as `keepSides` does.
    **The changes go one at a time, each after the last was answered**
    (`settingsSent`): two quick clicks were two POSTs on two connections,
    the first landed after the second, and the file kept the older choice
    -- which the push then put back on the page. The two-switches test
    went red that way under load. The menu reads the tab width and the
    wrap from the settings (`readingWanted`), never back off the root.
    `test_two_quick_changes_reach_the_file_in_the_order_they_were_made`.
  - **The ticket links are rows in the menu, saved on leave or Enter**
    (`putLinkRow`, `saveLinks`, `putLinkRows`): the reader chose that over a
    save button and over saving each keystroke, which linked half a
    pattern for a moment. Each row is "find", a regular expression, and
    "link to"; under it, the first match on the page and where it goes
    (`paintExamples`, when the menu opens and after a save, never on a
    push, because it reads the text of the whole page), or why it is not
    saved, in red, with the box it is about (`sayLink`, `data-bad`, the
    `field` the daemon names with `trouble_field` -- read from the
    message's words, the wrong box went red when a pattern held them). **The page checks only what only it can**: a
    half row, and a pattern this browser will not compile (`linkProblem`).
    The rest is `link_trouble` in the daemon, once; `save_config` keeps
    the good links, leaves out the bad and names them by index
    (`refused`), so one mistake does not cost the other links. **The rows
    are the file's when the menu opens, and the reader's while it is open**
    (`putLinkRows`, from `showSettings`): a push never rebuilds them. A
    rebuild took a red row, a half-filled one and an empty new one, none
    of which is in any file; three guards each covered one way a push
    could land (a save on its way, this page's own write, an older push
    after an answer), the last was red one run in three at `-n 12`, and
    the guards still missed the empty row.
    `test_a_link_that_cannot_be_used_is_red_and_the_others_are_kept`.
    **The outside click is read from the click's path**
    (`composedPath`), not from where its target is now: × takes its own
    row out, its target then had no place on the page, and the menu shut. **The colours
    buttons wear the colours they give** (`--light-bg`, `--dark-ink` and
    the rest, in the first `:root`, which the theme blocks read for `--bg`
    and `--ink`), so they read the same in either theme. **Each label
    stands on the first line of what it names**: the grid lines up
    baselines, because a padding that lined a label up with a button left
    "alerts" 5 px under the first checkbox.
    `test_every_settings_label_stands_level_with_what_it_names`. **Alerts off is a mark on
    the button** (`.offmark`, `data-alerts`, set by `drawBell`): off was
    the one thing the bell said at a glance. A choice changes the page in
    place: the colours and reading are on the root, the columns go through
    `keepSides`. The alert boxes keep their ids, so `setAlert` works as it
    did. `c` still cycles the colours (`nextTheme`).
    `test_the_settings_say_what_is_chosen_and_change_it_in_place`,
    `test_the_alert_panel_shuts_from_anywhere`,
    `test_alerts_are_off_until_you_ask`. **Nor a strip of keys under
  the rows**: it said in two cramped lines what `?` shows in full, and the
  reader asked for it to go. `test_the_session_list_ends_with_its_rows`.
- **What a row offers is icons in the age's place, on its hover** (#389):
  a moon for "not now" and a sun to wake it, a clock for "later" and the
  clock struck through to cancel, a dot for "unread" (`.act`, `setIcon`,
  `ICONS`). As words, "later unread" and "not now" cut long names short,
  and "not now" broke over two lines at a narrow width. **The age goes
  while they show** (`.age.swap`, set only on a row that offers any),
  and they are `margin: -3px 0` because 22 px is taller than the line:
  the row keeps its height. They still take a little of the name's room
  where the age was short ("3s"): less than 60 px, where the words took
  nearly twice that. **Not there at all until the hover** (`display:
  none`, not `opacity: 0`): invisible, a link took its room, and a long
  name was cut short for it. **The snooze's moon is hover-only too**, as
  the others are; the word "snoozed" says a snoozed row, and `z` works
  without the pointer. `setIcon` keeps the kind in `data-icon`, which is
  what a test reads. `test_the_row_offers_unread_on_a_read_row_only`,
  `test_a_snoozed_session_stops_saying_it_needs_you_until_it_asks_again`.
- **A row says what nothing else on the page says, in four lines that are
  the same on every row.** The reader chose each line. The name; the
  repository and the worktree, with the remote and the path on a hover; the
  branch with what git counts at the right edge; what the agent is doing or
  asks, only while it is doing or asking. The time stands beside the name.
  - **Not the state.** The row's edge, its tint and the group it stands in
    said it, and a word at the top, "waiting for input" at the foot and a
    dot said it three more times. Only a finished row keeps the word,
    because "ended" and "killed" share one group and one grey. The pulse
    that was the dot's is the needs-you row's own now.
  - **The name is the one Claude Code shows** (`rowName`, `Session.title`,
    #351): the reader's from the page while it is the newer one, then the
    status line's `session_name` (`customTitle ?? aiTitle`), then the first
    prompt that is not a command (`first_prompt`), then `place`. **This
    reversed a rule**: the row showed `place` until the reader named it,
    because Claude Code's title was written once from the first prompt and
    went stale beside the branch -- a row named after one ticket over a
    branch named after another. The reader asked for one name in both
    places, and a rename on the page reaches Claude Code now, by `/rename`,
    so a stale title is one keystroke from right. The row's second line
    still says where it stands.
    **A typed name bridges; a name nothing was typed for stands**
    (`Store.page_name`). A name the page typed as `/rename` is kept with
    Claude Code's name just before (`Store.over`) and shown until that
    moves: then the status line carries ours, or a later terminal
    `/rename`. The bridge is long -- at an idle prompt Claude Code runs the
    status line again only at the next turn. A name nothing could be typed
    for is the page's alone and stands until the reader changes it, and so
    is the one a `/clear` moves (`link_clear`): Claude Code does not carry
    a `/rename` into the new session. **"Last wins" against the terminal
    was built and taken out**: the status line says what the name is, not
    when it was set, and with the stale status above a rename made before
    the page's looked like one made after it and dropped the reader's. An
    empty `over` taken as "Claude Code's first guess" swallowed a real
    `/rename` the same way. **`page_name` never writes**: `settle` runs in
    `ls` and `wait` as well, each with its own copy of the names, and one
    that wrote the file lost a name the daemon had just been given.
    `Store.rename`, the one writer, prunes a typed name Claude Code took.
    `test_a_typed_name_stands_until_claude_codes_moves`,
    `test_a_name_nothing_was_typed_for_stands_until_the_reader_changes_it`,
    `test_reading_the_names_writes_nothing`.
    **It wears the sans face**: in the fixed
    face it was half as wide again as the lines under it, and the reader
    said so. The age beside it stays fixed, so its digits do not dance.
  - **A ticket in the name, the worktree or the branch is a link**, by
    `linkTickets`: a branch is most often named after its ticket. Each part
    is written again only when its text or `state.links` changed (`fresh`
    on `slot`, `where`, `two`): `fillRow` runs on every push, and a link
    rebuilt between the press and the release is a click that never
    happens. A click on a link chooses nothing, and a double-click on one
    does not start a rename. `renameRow` forgets the name's key, or the name
    stays empty after the box goes. **`state.linksKey` is in
    `drawSessions`' key, not the count**: a pattern changed in the menu
    left the count where it was, and the rows kept the old links. And
    **`takeLinks` calls `drawSessions` itself**: the links can change after
    the last push of the sessions -- the reader adds one -- and then nothing
    drew the rows again. Alone the test passed; under load it was red three
    runs in three. `test_a_ticket_in_a_rows_name_or_branch_is_a_link`.
  - **The git line is one line.** Everything on it keeps its width but the
    branch, which gives way with an ellipsis: "✓ clean" shrank with it and
    broke over two lines. It sets `display: flex`, and the one `[hidden]`
    rule hides it all the same (`daemon-and-page.md`).
  - **A name is changed where it stands** (`renameRow`), by a double-click
    or `e`. The row is filled again on every push, so `fillRow` leaves a
    name with a box in it alone; and a row that moves loses the focus, so
    `drawSessions` gives it back with the caret where it was. Enter on the
    name the box came with keeps nothing, or the row would stop following
    its worktree for good.
  `test_a_row_says_its_name_where_it_is_its_branch_and_when`,
  `test_the_git_line_is_one_line_and_its_counts_stand_at_the_right`,
  `test_a_row_is_renamed_where_it_stands`.
- **The chosen row is a tab of what stands beside the list, as in a
  browser.** A faint ring marked it, and the reader had to look for it. It
  runs through the list's padding to the grip, its ground fades from the
  state's colour into `--meet`, and the grip opens where they meet. The
  reader chose each part from pictures.
  **It is the strongest row in the list** (#396): its state's colour (`--hue`,
  set with `--soft` on every state) at 34 % in `--meet`, held to half its
  width before the fade, a 1 px line round it in that colour at 55 %, and a
  6 px edge with 2 px less padding, so its text stands where it would.
  It faded from the half-transparent tint into grey before, the one row
  with less colour than the rest, and the reader could not find it. **A
  shadow was drawn and refused**: on the dark ground it does not show, and
  it lifts a tab off what it belongs to. **Its line is as wide as the other
  rows' own** (1 px, transparent on theirs): it had lines of 2 px in
  `--edge`, which could not be seen once the list wore `--edge` and cut the
  corner of the state's edge on the left. So the grip opens over the row's
  whole height, border and all (`openGrip`).
  **Every row runs to the line**, as a tab behind the chosen one: cards with
  four round corners read as buttons.
  - **The list wears the grip's colour (`--edge`), and a split tab's own
    list -- the map, a file tree -- wears `--meet`.** The grip then reads
    as the list's edge, which only the chosen row crosses, and the map
    stands apart from the page without a line. `--meet` is `--panel`,
    set on `.body`, because every tab is split now; the map's ground, the fade's end and the grip's
    opening all read it, so the row flows into what is there.
  - **The chosen row has no ground colour of its own, only the gradient**,
    and the gradient mixes into `--meet`, which is opaque. The state tints
    are half transparent: laid on the list's old ground, it came out
    brighter in the light and darker in the dark than the rows of its own
    group, and the reader saw it. `test_a_row_shows_its_state_in_its_colour`
    reads whichever row comes first, chosen or not, so it holds both.
  - **It stands in from the other rows by the grip's width**
    (`calc(4px + var(--grip-w))`), as it crosses the grip on the right.
    It stood out to the left first; the reader asked for this.
  - **The grip is outside the list that scrolls, so `openGrip` tells it
    where the row is**, as `--gap-top` and `--gap-bottom`: after every
    `drawSessions`, on the list's scroll, on a resize, and from a
    `ResizeObserver` on the chosen row. Only the part the list shows opens
    it, and nothing when the row is out of view. The draw is the one that
    a row arriving above the chosen one needs: nothing scrolls and nothing
    changes size.
  - **The list's scrollbar shows only while the pointer is on it.** A bar
    stands between the row and the grip, and cut the tab from its content
    in both themes. The wheel scrolls without it.
  `test_the_chosen_row_is_a_tab_of_the_content_beside_it`.
- **A drag on an edge starts only on the main button, and ends every way a
  press can end** (`dragWidth`, for the session list's edge and every split
  tab's). It started on any button and ended only on `pointerup`. A
  right-click opens the context menu on Linux and macOS, the menu takes the
  `pointerup`, and the column then followed the mouse with no button held,
  with `body.dragging` on, until the next click. A touch the browser takes
  for a scroll ends in `pointercancel`, not `pointerup`. So the grip
  captures the pointer, and `pointercancel` and `lostpointercapture` end
  the drag too. A headless browser opens no menu, and Chromium driven by
  Playwright sends no lost capture of its own, so the test sends those
  events by hand.
  `test_a_drag_on_an_edge_starts_only_by_hand_and_always_stops`.
- **Rows are kept and filled in again, never rebuilt.** A row can only fade
  into its new colour if it is the same row, and the needs-you pulse can
  only finish a cycle if its row outlives the change. `newRow` builds every part once, empty; `fillRow` reaches
  them by position; a row moves only when its place changed, because
  `appendChild` on an attached node is a remove and an insert.
