# The sidebar

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. The groups, `settled`, alerts, the tab's title and icon, the settings menu, a row's lines and icons, the chosen row, columns that drag and fold.

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
- **What an agent starts is a line under its row, never a row** (#422).
  A `claude -p` an agent ran from its Bash tool was a row of its own: it
  came and went in a second, counted as working and then unread, and
  nothing said whose it was. The reader chose lines from pictures.
  `fillKids` draws one line for each child still running -- a session
  whose `started_by` is this row (`kidsOf`), or a subagent of the Agent
  tool in `subagents` -- then "N subagents ran", which unfolds the ended
  ones (`state.kidsOpen`). The daemon keeps the last `SUBAGENTS_HELD` of
  the Agent tool's, and `agents_ran` counts them all.
  - **A child counts nowhere** (`topSessions`, `childIds`): not in the
    list, the groups, the tab's title and icon, the alerts or the unread
    feed. A child whose parent the page does not hold is a row again.
  - **Never hide one that may need the reader**: a child with a pane of
    its own, or one that waits, is a row, and so is one still working
    under a parent that is over -- its line stood under a folded history.
    A review found the first: a hidden session's dialog had no row, no
    title and no alert. **And the chosen child stays in sight when it
    ends**, folded or not: the chosen session is never hidden from the
    list it is chosen in.
  - **What an Agent call asked for is let go at a turn's edge**
    (`agent_asks`): a call declined in its dialog fires no hook, and one
    that failed starts nothing, so their descriptions named the next
    subagent and every one after it. A failed call drops its own.
    `test_a_call_that_started_nothing_names_no_subagent`.
  - **A subagent is over when the agent's `Stop` no longer lists it**
    (`end_unlisted_subagents`). Waiting for `SubagentStop` alone left a
    line running for days: a subagent the reader stops with `x` in the
    agents panel sends none (measured on 2.1.292,
    `tests/fixtures/subagent_killed.jsonl`). Its end comes back as a
    `<task-notification>` prompt with `<status>killed</status>`, and the
    `Stop` of that turn lists it no more. Every `Stop` of the agent lists
    each subagent still running in `background_tasks`, with the
    subagent's `agent_id` as `id`, so a subagent that `Stop` does not
    list is over, however it ended. Any entry keeps one, whatever its
    status. Only the agent's own `Stop`: a `SubagentStop` carries a list
    too, and the subagent that stops is still in it. A `Stop` with no list
    (an older build) ends nothing.
    `test_a_subagent_the_reader_stopped_is_over_at_the_next_stop`.
  - **A child's change must redraw its parent's row**: `drawSessions`
    skips the draw when the listed rows did not change, and a child is in
    none, so the children go into its key. A test of that waits until the
    parent's row is still (its unread mark landed and came back): the
    mark's push redrew the row by chance, and the break went unseen.
  - **A press on a line or on the fold stops there**: the row chose itself
    under it. A child session's line opens it (`choose`); the Agent tool's
    subagents have no transcript the page reads.
  `test_what_a_session_started_stands_under_its_row`,
  `tests/test_subagents.py`.
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
    amber for needs-you, grey for finished. **Drawn at `ALERT_ICON`, 192
    px, never the tab's 32**: the system shows an alert's picture at 64
    px or more, and the reader saw the 32 blown up into a blur.
    `robotPicture` draws the one drawing on 32 and scales it to any size.
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
  **The alerts are not a draw's at all** (#542): `onSessions` rings them,
  where `state.sessions` is written -- the push, `patchSession`, the
  reminder timer -- with the review prune, the reminder timer and the
  unread view's `askLast`. Inside `drawSessions`, one draw of the sidebar
  -- a filter typed, a row chosen -- could ring, arm, write and fetch.
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
  - **The same robot stands before the name, in the name's amber**
    (`drawLogo`, `.brand .logo`, `.brandname`): the reader asked for it,
    and chose the brand's colour over the state's -- the tab icon already
    says the state. It reads the name's colour, so `showTheme` draws it
    again; it is drawn at 64, three times its size, to be sharp. Folded,
    it is all the head shows (`.foldsessions .sidebar-head`).
    `test_the_robot_stands_before_the_name_and_in_the_folded_strip`.
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
  - **The two find boxes stand on one line, and a fold button is a bare
    icon** (issue 469, `.find`, `.findslot > .fold`, `.sidebar-head`).
    They looked alike but not quite: the head's 8 px margin put the filter
    box lower, and `.find`'s edge was `--edge`, the session list's own
    ground, so on the list it had none. The edge is `--edge-bright` now,
    which both grounds show. The fold buttons were boxes the height of the
    find box, its twins with another edge; the reader chose them clearly
    different -- no box, a ring on the hover, the icon 17 px.
    `test_the_find_boxes_stand_on_one_line_and_the_fold_is_a_bare_icon`.
  - **Every setting is one menu** (`putSettings`, `paintSettings`,
    `#setpop`): the colours, the two alerts, the tab width, long lines, the
    diff's columns and the ticket links, with the path of the file that
    keeps them at its foot (`#settingspath`, and a button that copies it).
    It was a bell, a colours button, a menu on the Review bar and two links
    over every file, and the reader chose one menu from pictures. **It
    stands in four groups** -- Page, Code, Review, Links -- each a soft
    card with a bold title (`.setgroup`, `.settitle`), chosen from pictures
    once the menu had grown long, over capital headings, names in a column
    of their own, tabs, and bare lines. A group is a subgrid, so every
    label still stands in one column.
    `test_the_settings_stand_in_four_titled_groups`.
    **Five settings are also beside the code they change** (`putQuick`,
    `QUICK`): the diff's columns, whitespace and the code's width at the
    Review bar's right end, the marks, the code's width and long lines on
    the open file's line -- the ones the reader changes while reading.
    The marks came there for #486, which asked for the Review bar's
    whitespace button on a file: a change of whitespace means nothing on
    one file, so beside it the button is the marks (`keepMarks`, the
    `marks` icon). `test_the_marks_are_one_click_beside_a_file`. The menu
    still holds every setting: the reader weighed taking them out of it and
    kept one place where all of them are.
    **One button each, lit while its setting is on** (`.toggle`,
    `aria-pressed`), so one click switches it: it was a pair, one icon a
    side, and the reader asked for one click, and chose this from pictures
    over an icon that shows the state -- that one cannot say whether it is
    the state now or the one a click gives. The menu keeps its parts with
    words. Icons only, the words in `aria-label` and, with ": on" or
    ": off", in `title`: with words the Review bar ran out of room on a
    notebook, which is why the columns went into the menu at first. They
    are the menu's settings, not copies: `paintSettings` paints the menu's
    `.choice` and every `.toggle` from `settingsNow`, and a click paints
    at once (`keepWidth`, `keepWrap`, `keepSides`, `keepSpace`), not when
    the push comes, which over the ssh tunnel is a second later. **The
    lit look is a rule of its own after `.verb.quiet`**: added to the
    choices' rule above it, `.verb.quiet` -- as strong, and later -- won
    it back, and a lit button looked like any other; the test compares
    the two grounds.
    `test_the_review_bar_carries_the_columns_and_the_width`,
    `test_the_file_line_carries_the_width_and_wrap_beside_the_code`,
    `test_a_button_beside_the_code_shows_its_choice_before_the_file_answers`.
    - **Every line's right-hand controls end on one line** (`--line-end`,
      24 px, the tab row's own): the Review bar, the commit message's
      md / txt, a file's card, the Files tab's file line. They stood 16,
      20, 24 and 26 px in, and the reader saw it at once. What stands in
      the scrolling pane uses `--line-end-in`, which takes off the room
      the pane keeps for its bar (`scrollbar-gutter: stable` on
      `.diffscroll`, measured by `measureScrollbar` the same way: an empty
      `overflow: scroll` box said 0 px in Chromium while the pane kept
      15). The read-as control is one button, "txt", which the reader
      asked for, lit as the buttons beside the code are.
      `test_every_right_hand_control_ends_on_one_line`,
      `test_the_file_line_ends_where_the_tab_row_ends`.
    **The labels are one word** -- "tab", "lines", "diff", "links", not "tab
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
    **So a test that changes a setting twice waits for each one's push**
    before the next change: the push of the first came after the second
    press of `c`, put "dark" back over "auto", and the third press started
    from there, once in four runs under load (#439). It wraps
    `takeSettings` and waits for the word it expects;
    `test_the_c_key_steps_through_the_colours`. The colours test chose
    "dark" and then "system" without that wait, and CI read "dark" (#606);
    `test_the_colours_can_be_switched_and_are_remembered` waits now.
  - **The ticket links are rows in the menu, saved on leave or Enter**
    (`putLinkRow`, `saveLinks`, `putLinkRows`): the reader chose that over a
    save button and over saving each keystroke, which linked half a
    pattern for a moment. Each row is "find", a regular expression, and
    "link"; under it, the first match on the page and where it goes
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
    **The rows span the whole Links group, and both boxes reach the
    row's right edge** (`.linkedit`, `.linkrow`, `.linkdrop`): the reader
    asked for more room to write a pattern and a url in. So the group has
    no label in the column of labels -- its title names it -- the button
    that takes a row out is "remove", on the line under the boxes, where an
    × beside the first box took its room, and the second box's word is
    "link", not "link to". The menu has a set width (`width` on
    `.setpop`) and its columns are `max-content 1fr`: with two
    `max-content` columns the wide rows spread their width over both, and
    every other setting stood far from its label. With `minmax(0, 1fr)`
    and no width, the menu, placed absolutely and shrunk to fit, folded
    the controls to one word a line.
    `test_the_link_boxes_take_the_whole_width_of_the_links_group`,
    `test_the_settings_stand_in_four_titled_groups`.
    **The outside click is read from the click's path**
    (`composedPath`), not from where its target is now: × takes its own
    row out, its target then had no place on the page, and the menu shut.
    **And from where the press began** (`pressedOn`, #485): a text
    selected in a link box and let go outside the menu is a click on
    `body`, and the menu shut under the reader. A press that began inside
    is inside, for the model menu too.
    `test_a_selection_that_ends_outside_the_menu_keeps_it_open`. **The colours
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
    (`Marks.page_name`). A name the page typed as `/rename` is kept with
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
  - **A chosen row is never see-through** (#427): a finished row is faded
    (`opacity: .72`), and was faded when chosen too, so its fade ended on a
    grey mix of the list's ground and its edge stood out where it meets
    the content. `.row.ended:not(.chosen)` fades the others only, and the
    chosen one's name is bright, as on any chosen row.
    `test_a_chosen_finished_row_is_as_whole_as_any_chosen_row`.
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
  - **Its outline turns into the content's edge and runs on down it**
    (#407): it ended square at the end of the list, two lines that stopped
    for no reason. Where the row meets the grip, a quarter circle of
    `--flare` turns the line upright, and the ground inside the curve is
    `--meet`, so the row widens into the content as a tab into its page;
    above and below, a 1 px line in the row's own colour (`--gap-line`)
    runs down the content's edge.
    - **The line is mixed from the row's `--hue`, never read off its
      border** (`--gap-hue`, #416): the border fades in over .2 s, and read
      at a choice it was all but transparent, so every click left the line
      and the corners colourless until the next push drew them again. A
      custom property does not transition. A test that reads a colour
      after a choice waits for `getAnimations()` to be empty, and reads
      nothing a push could have refreshed.
      `test_the_outline_keeps_its_colour_when_another_row_is_chosen`.
    - **Only the grip's colour fades, never its layers**
      (`transition: background-color` on `.grip`): with `transition:
      background`, a custom property still does not transition, but the
      `background-position` computed from it does. A pointer that left
      the grip slid the corners and the line down from its top to the
      row, and the reader saw the row's outline flicker; every scroll
      moved them a step behind the row.
      `test_the_opening_in_the_grip_never_slides_into_place` asks
      `getAnimations()` in the same frame as the change, so a loaded
      runner cannot end the transition before it reads. The reader chose it from a picture over
    the corners alone. **All of it is the grip's own background**, layers
    under `#grip.open`: the list scrolls and clips whatever a row draws
    outside it. The circle's middle stands 3 px into the list, so the
    curve starts on the row's line and ends upright on the content's edge;
    the 6 px between two rows leave no room for a larger one, and a radius
    of the grip's 5 px could not be seen. **A corner only where the row's
    end is in view** (`flaretop`, `flarebottom`), and no line at all when
    the row is out of the list. A test of it reads pixels (`pixels`):
    the shape of a gradient is in no computed style.
  `test_the_chosen_row_is_a_tab_of_the_content_beside_it`,
  `test_the_chosen_row_turns_into_the_content_s_edge`.
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
  - **One drag for a width and a height** (`dragEdge`; `dragWidth`, and
    `dragHeight` for the send bar's top edge, #442): the capture and the
    ends above are in one place, so a third edge cannot forget them. The
    height goes on the root as `--say-h` or `--reviewsay-h`, kept like a
    width, and it is the least the box is, empty or full: as a cap only, a
    drag on an empty send box did nothing. **It is not the most** (#453):
    as both, a Shift and Enter added a line the box did not grow for. It
    grows to 40vh or the dragged height, whichever is taller. A
    double-click gives the box back to `fitSay`. `test_the_send_box_is_as_tall_as_its_edge_is_dragged`,
    `test_the_review_is_as_tall_as_the_bars_edge_is_dragged`.
  - **An edge between two grounds draws no line, and its handle is wider
    than it** (#443). A split tab's grip was a bar of 5 px in `--edge`,
    then a line of one pixel, and the reader found the page busy with
    lines that all looked alike: the column, the send bar's top, the line
    under the find box and another 27 px below it. The list's ground and
    the pane's part them, so the grip is `--split-grip-w` wide and draws
    nothing, and its `::after`, three pixels wider each side, is the
    handle, faintly amber under the pointer (`.hgrip` is the send bar's).
    Before a new line, ask whether a ground already draws it.
    `test_the_maps_edge_draws_no_line_and_drags_from_beside_it`,
    `test_a_line_between_two_grounds_is_not_drawn`.
- **A column folds to a strip that holds only its button** (#464, `FOLDS`,
  `putFold`, `paintFold`, `unfold`, `folded`, `#sessionfold`, `.fold`,
  `body.foldsessions`, `body.foldlist`, `--fold-w`). On a laptop the session
  list and a split tab's list took 615 of 1366 px. The reader chose a button
  on each column over one for both and over folding by width alone.
  - **It is a class on `body`, never on the column**: `split` builds a
    split tab's list again on every switch, and the sidebar's grip and
    `.main`'s grid columns must know too. The list column is one for the
    three tabs, as `--side-w` is, so it folds on all three.
  - **The button stands in the column's `.findslot`, ordered before the
    find box by CSS** (`order: -1`, #492): `homeFind` appends `#find` to
    the slot, so the markup is no guide. It stood after the box, and the
    reader asked for it at the column's left, in both columns, once the
    Files tab's funnel stood beside it. **Folded or open, it stands in one
    place** (`--fold-in` from the column's edge, and as far from the box):
    it is pressed to fold and again to unfold, and the pointer has not
    moved. The open slot's padding is taken back by the button's margin;
    the strip no longer centres it. Its middle is the box's middle.
    **Each fold's rule names its own column** (#504): `.foldlist
    .findslot > .fold` matched the session list's slot too, so folding the
    list beside the transcript moved the session list's button and
    narrowed its filter box. `.foldlist .content.split > .side > .findslot`.
    `test_a_fold_button_stays_where_it_was_pressed`.
  - **A folded column's edge drags nothing** (`pointer-events: none`): a
    drag set a width nobody could see.
  - **`f` and `/` unfold the column they type into**: nothing is focused
    in a column with `display: none`, so the key did nothing.
  - **No `openGrip` on a fold**: the chosen row hides and comes back with
    its list, and `gripWatch` observes it. A call there stayed green under
    `tests/perturb.py` and was taken out.
  - **Folded, every session is a tile, and the tiles are the rows**
    (`markRow`, `tileTitle`, `data-name`, `.foldsessions #rows`). A
    strip with one button hid who needs you and every other session; the
    reader asked for them, clickable. CSS draws each row as a tile as tall
    as a row, its name turned up it (`writing-mode: vertical-rl`, then
    `rotate(180deg)`, read bottom to top) on its state's colour, and the
    unread dot. **On the hover, the row whole, in the tile's own place**
    (`tileCard`, `#tilecard`, #491): the name, where it stands, its state
    and its line, as the open list draws them, over the tile and the page,
    and at least as tall as the tile. Beside the strip it was a second tab
    next to the first, and the reader asked for the one tab opened out. It was the name alone in `title`, after a wait, and the
    reader asked for the whole row; the card is a copy of the row
    (`cloneNode`), so it says what the row says and is drawn in one place,
    and no row carries a title any more (`tileTitle`), or the browser's
    would stand on the card. Nothing on it is pressed: the tile is. Two
    letters across the tile told two sessions of one repository apart only
    by colour; the reader asked for the name turned, a row tall. **A name
    too long fades out at its end (`mask-image`), never an ellipsis**:
    "…" took three letters' room, and the reader asked for the fade. The
    name's box is the tile's whole length, so the fade covers its last
    16 px and a short name never reaches it. A click
    chooses, `j` `k` move, and every push fills a tile as it fills a row.
    A second list would need its own clicks, order and pushes. The
    chosen tile wears the chosen row's gradient, edge and line (the
    reader asked), runs to the grip, and the grip opens beside it.
    **The rules are anchored on `#rows`**: a class-only rule lost to
    `.row .line1` and `.row.chosen`, later in the file at the same
    weight, and the folded strip drew every row's text over the content.
  - Kept in `localStorage` (`wostuast-fold-sessions`, `wostuast-fold-list`)
    as a width is: it is not a setting in the menu.
  `test_each_column_folds_away_and_comes_back`,
  `test_the_list_column_folds_on_every_split_tab`,
  `test_a_key_into_a_folded_column_brings_it_back`,
  `test_a_folded_session_list_is_a_tile_for_each_session`, which holds
  the card too.
- **Rows are kept and filled in again, never rebuilt.** A row can only fade
  into its new colour if it is the same row, and the needs-you pulse can
  only finish a cycle if its row outlives the change. `newRow` builds every part once, empty; `fillRow` reaches
  them by position; a row moves only when its place changed, because
  `appendChild` on an attached node is a remove and an insert.
  - **And filled only when what it shows changed** (#431): its session
    and its children by object (`row.filledWith`), and the page facts a
    row shows by their text (`dataset.sig`) -- the choice, the links, the
    reminder's word, time and due, the fold of its subagents. Filling all
    500 rows took 34 ms on every push. **By object, because a session is
    never changed in place** (#435): every session the page holds is
    frozen, and `patchSession` is the one way to change one, by a new
    object. Four places wrote one in place -- a rename, a reminder, a
    snooze, an unread mark -- and the first version of this compared each
    row's JSON to see them. **A session that reads the same stays the same
    object** (`takeSessions`, `sameOrNew`): a stream's opening carries
    every row, the first push after a daemon starts names every row, and a
    patch that changes nothing changes nothing; each made every row new.
    **`opened` fails any test whose page wrote a frozen session**, so the
    whole browser suite holds the rule.
    `test_a_session_is_changed_only_by_patch_session`. **A choice changes no
    session**, and a read row gets no push, so the choice is in the
    signature or the row chosen before kept its look. **A change no row's
    data shows goes through `redrawRows`**, which clears every signature
    -- a closed rename box left its name empty. **The ages are read off
    the page** (`tickAges` reads `.age[data-since]`), so a row left alone
    still ticks.
    `test_a_push_fills_only_the_rows_it_changed`,
    `test_a_row_is_renamed_where_it_stands`.
