# The sidebar

The groups, `settled`, alerts, the tab's title and icon, the settings menu, a row's lines and icons, the chosen row, columns that drag and fold.

- **Group by state, newest first inside a group.** The four groups are
  `BANDS`, most urgent first: needs you, working, ready, history. **Working
  sits above ready**, the reader's order: an agent still going may want a
  look; one at its prompt is done with you, and nothing about it waits.
  This supersedes "never sort by state", which held while sorting churned
  the list: a row moves only when a turn begins, ends or stops on a
  question, and a row arriving under "needs you" is what this tool exists
  to say. **Inside a group the daemon's order stands**: `Session.settled`,
  newest first.
- **`settled` is not `since`.** `since` is the last event and moves every
  few seconds while working, so two busy agents swapped places as you read.
  `settled` is when the session last *became* what it is -- a turn
  beginning, ending, or stopping on a question -- when the row changes band
  anyway, so it moves once. It is stamped in one place, `Store.apply`, and
  only on a change: every handler assigns a state, new or not, and
  `_on_pre_tool` writes "working" on every tool call. `_bury` is the one
  place outside `apply` that stamps it, because nothing reports being dead.
  **And once for a session nothing has stamped**: `SessionStart` is done to
  done, so `settled` fell back to the last event and an idle notification
  moved an unchanged row.
  `test_a_session_that_never_changed_state_keeps_its_place`. The worktree
  is the tiebreaker only. Never sort on `label`: the name arrives from the
  status line a second after start, and `/rename` changes it later.
- **What an agent starts is a line under its row, never a row** (#422). A
  `claude -p` from an agent's Bash tool was a row that came and went in a
  second, counted as working then unread, and did not say whose it was; the
  reader chose lines from pictures. `fillKids` draws a line per child still
  running -- a session whose `started_by` is this row (`kidsOf`), or an
  Agent-tool subagent in `subagents` -- then "N subagents ran", which
  unfolds the ended ones (`state.kidsOpen`). The daemon keeps the last
  `SUBAGENTS_HELD` Agent-tool subagents; `agents_ran` counts them all.
  - **A child counts nowhere** (`topSessions`, `childIds`): not in the
    list, groups, tab title and icon, alerts or unread feed. A child whose
    parent the page does not hold is a row again.
  - **Never hide one that may need the reader**: a child with its own pane,
    or one that waits, is a row, and so is one still working under a parent
    that is over (its line stood under a folded history). A hidden
    session's dialog had no row, title or alert. **The chosen child stays in
    sight when it ends**, folded or not: the chosen session is never hidden
    from its list.
  - **What an Agent call asked for is let go at a turn's edge**
    (`agent_asks`): a call declined in its dialog fires no hook and a failed
    one starts nothing, so their descriptions named every later subagent. A
    failed call drops its own.
    `test_a_call_that_started_nothing_names_no_subagent`.
  - **A subagent is over when the agent's `Stop` no longer lists it**
    (`end_unlisted_subagents`). `SubagentStop` alone left a line running for
    days: a subagent stopped with `x` in the agents panel sends none
    (measured on 2.1.292, `tests/fixtures/subagent_killed.jsonl`); its end
    comes as a `<task-notification>` prompt with `<status>killed</status>`.
    Every agent `Stop` lists each running subagent in `background_tasks`,
    its `agent_id` as `id`, so one not listed is over, however it ended. Any
    entry keeps one, whatever its status. Only the agent's own `Stop`: a
    `SubagentStop`'s list still holds the one that stops. A `Stop` with no
    list (an older build) ends nothing.
    `test_a_subagent_the_reader_stopped_is_over_at_the_next_stop`.
  - **A child's change must redraw its parent's row**: `drawSessions` skips
    the draw when the listed rows are unchanged, and a child is in none, so
    the children go into its key. Its test waits until the parent's row is
    still (its unread mark landed and came back): the mark's push redrew
    the row by chance and hid the break.
  - **A press on a line or the fold stops there**, or the row under it was
    chosen. A child session's line opens it (`choose`); Agent-tool
    subagents have no transcript the page reads.
  `test_what_a_session_started_stands_under_its_row`,
  `tests/test_subagents.py`.
- **There are four states, not five.** "starting", the first minutes of a
  session that said nothing else, is ready told in a way that went stale.
  `SessionStart` sets `done`; `mark_idle` and `STARTING_MAX` are gone. The
  word for `done` is "ready".
- **The fold is not a filter.** Finished sessions fold under the history
  bar, but are still counted and searched by the filter, and the chosen one
  is never missing from its list.
- **There are two alerts, not one switch.** Needs-you: the agent cannot go
  on without you. Finished: a turn you can read. One switch takes the
  unwanted one with the wanted. `alertsWanted()` reads both from our
  `settings.json`, like the theme, whose shape the daemon checked
  (`config_trouble`). The browser's permission stays the browser's.
  **Needs-you is on the moment alerts are**: it is what this tool exists to
  say, so a browser that already granted permission, under a file that
  says nothing, gets it without asking.
- **"Finished" is a change, not a state.** `done` is where a session sits
  between turns; read as a state it would be announced every push.
  `wasDoing` holds what each session did last pass, written **on every pass
  whatever the switches say**: ticking the box mid-turn still tells you
  when it stops, and a session that reached `done` unheard is no change
  waiting to be announced. `waiting` is the same for amber, filled
  **whenever the needs-you alert is not sent**, not only while alerts are
  not allowed: filled on that path alone, switching it back on announced
  every row gone amber meanwhile
  (`test_turning_needs_you_on_brings_no_backlog`). **Every alert says
  `renotify`**: with one tag per session a second alert replaces the first,
  and a replacement makes no sound or banner unless it asks
  (`test_every_alert_makes_itself_heard`). The test ticks the box
  mid-turn: one that turns it on *after* a turn ends passes with the
  recording moved inside the switch.
- **An alert says what, where, and in the colour of what** (`tellAbout`,
  issue 330): "needs you" and the bare `reason`, no picture, gone on its
  own, said too little.
  - **What**: the question itself, from `asking` (`waitsFor`) -- the
    `reason` names only its header -- or a permission's `reason`; for a
    finished session, the prompt it finished (`shown_prompt`).
  - **Where**: folder and branch, the row's second line.
  - **The tab's robot** (`iconPicture`, the one drawing `drawIcon` uses),
    amber for needs-you, grey for finished. **Drawn at `ALERT_ICON`, 192
    px, never the tab's 32**: the system shows it at 64 px or more, and 32
    blurred. `robotPicture` draws the one drawing on 32 and scales it.
  - **Needs-you stays until clicked or closed** (`requireInteraction`): one
    that went while the reader was away said nothing. Finished goes on its
    own: nothing waits.
  - **Nothing the agent or the reader wrote goes out whole**: an alert can
    stand on a locked screen, so the prompt is `clip_hidden` to
    `PROMPT_SHOWN`, and a permission is its `reason`, hidden already --
    never the dialog's `fields`. **Once a prompt, not once a row**:
    `clip_hidden` costs 170 µs on 500 characters, rows are built for every
    session every tick, and at start every prompt of a long log paid it.
    `Session.prompt_shown` keeps it with its prompt.
  `test_an_alert_that_needs_you_says_what_and_where_and_stays`,
  `test_a_question_is_said_as_the_question`,
  `test_a_finished_agent_says_what_it_finished_and_goes`,
  `test_the_shown_prompt_is_worked_out_once_a_prompt`.
- **The counts are about every session.** `drawCounts` runs *before* the
  guard that asks whether the shown rows changed: behind it, a session the
  filter hid could go amber and reach no title, icon or notification.
  **The alerts are not a draw's at all** (#542): `onSessions` rings them
  where `state.sessions` is written -- the push, `patchSession`, the
  reminder timer -- with the review prune, the reminder timer and the
  unread view's `askLast`. Inside `drawSessions`, a sidebar draw (a filter
  typed, a row chosen) could ring, arm, write and fetch. **The counts are
  not on the page itself**: a strip of "1 ready", "3 sessions" repeated the
  groups, and the reader asked for the room. The tab's title and icon, and
  the alerts, are what count.
  - **The title names who needs you, and leads with it** (`tabTitle`):
    "fix-login asks", "fix-login, api-retry +1 need you", else "2 working",
    "4 ready". A tab cuts its title's end; "(1) needs you" left you to look
    for whom, and "wostuast" alone said nothing over four ready agents.
    Names are `rowName`'s, so tab and list agree. **So are the alerts'**
    (`notifyAbout`): `label` leads with Claude Code's title and named a
    session not in the list.
    `test_an_alert_names_the_session_as_its_row_does`.
  - **The icon is a robot, and the whole of it is the state**
    (`paintIcon`): the bar's own ink when nothing waits ("ready" is not
    news), green, amber. The reader chose it from pictures over a dot in
    the state's colour (it did not say what the tab was, and "ready" blue
    matched the Jira and Bitbucket tabs) and over a robot on a status line
    (too thin in a tab bar). One eye big, one small, a look that doubts a
    little, over a wide, quiet smile -- all cut out, so either bar shows
    through.
  - **It follows the browser's light or dark, never the page's theme**
    (`tabBarIsDark`, the `--tab-*` colours, which no theme block sets): it
    stands in the browser's tab bar, and from the page's palette a light
    page in a dark browser put a dark robot on a dark bar. The media
    query's `change` redraws it, whatever the page's theme.
  `test_the_tab_title_names_who_needs_you`,
  `test_the_tab_icon_is_a_robot_in_the_states_colour`,
  `test_the_tab_icon_says_the_state_in_the_bar_it_stands_in`,
  `test_the_tab_icon_follows_the_browser_and_not_the_page`.
  - **The same robot stands before the name, in the name's amber**
    (`drawLogo`, `.brand .logo`, `.brandname`): the reader asked, and chose
    the brand's colour over the state's, which the tab icon says. It reads
    the name's colour, so `showTheme` redraws it; drawn at 64, three times
    its size, to be sharp. Folded, it is all the head shows
    (`.foldsessions .sidebar-head`).
    `test_the_robot_stands_before_the_name_and_in_the_folded_strip`.
- **There is no bar across the top.** The name and version head the
  session list (`.sidebar-head`, as tall as `.tabs`, so the rules under them
  are one line); the settings are one icon at the tab row's end, its words
  in `aria-label` and `title`. The version is `own_version`: the day the
  running file was written (for a copy `install` fetched, its commit's day,
  in UTC) and the start of its SHA-256 -- never a number raised by hand,
  and the same bytes `install_behind` compares. `--version` prints the same
  (#344). **Nor a strip of keys under the rows**: it said in two cramped
  lines what `?` shows in full, and the reader asked for it to go.
  `test_the_session_list_ends_with_its_rows`,
  `test_the_tabs_start_at_the_top_and_the_name_heads_the_session_list`,
  `test_the_page_says_which_copy_is_running`.
  - **The two find boxes stand on one line, and a fold button is a bare
    icon** (issue 469, `.find`, `.findslot > .fold`, `.sidebar-head`). The
    head's 8 px margin put the filter box lower, and `.find`'s edge,
    `--edge`, was the list's own ground, so it had none there; it is
    `--edge-bright`, which both grounds show. The reader chose fold buttons
    clearly unlike the find box: no box, a ring on hover, the icon 17 px.
    `test_the_find_boxes_stand_on_one_line_and_the_fold_is_a_bare_icon`.
  - **Every setting is one menu** (`putSettings`, `paintSettings`,
    `#setpop`): colours, the two alerts, tab width, long lines, the diff's
    columns, ticket links, and the file's path at its foot (`#settingspath`,
    with a copy button). The reader chose one menu from pictures over a
    bell, a colours button, a Review-bar menu and two links over every file.
    **It stands in four groups** -- Page, Code, Review, Links -- each a soft
    card with a bold title (`.setgroup`, `.settitle`), chosen from pictures
    over capital headings, a names column, tabs and bare lines. A group is a
    subgrid, so every label stands in one column.
    `test_the_settings_stand_in_four_titled_groups`.
    **Five settings are also beside the code they change** (`putQuick`,
    `QUICK`), the ones changed while reading: the diff's columns, whitespace
    and code width at the Review bar's right end; the marks, code width and
    long lines on the open file's line. The marks are there for #486, which
    asked for whitespace on a file: whitespace means nothing on one file,
    so there the button is the marks (`keepMarks`, the `marks` icon).
    `test_the_marks_are_one_click_beside_a_file`. The menu still holds every
    setting: the reader kept one place for all.
    **One button each, lit while its setting is on** (`.toggle`,
    `aria-pressed`), so one click switches it. The reader asked for one
    click over a pair of icons, and chose this from pictures over an icon
    showing the state, which cannot say if it is the state now or after a
    click. The menu keeps its parts with words. Icons only, words in
    `aria-label` and, with ": on" or ": off", in `title`: with words the
    Review bar ran out of room on a notebook; icons fit at 1366 px. They are
    the menu's settings,
    not copies: `paintSettings` paints the menu's `.choice` and every
    `.toggle` from `settingsNow`, and a click paints at once (`keepWidth`,
    `keepWrap`, `keepSides`, `keepSpace`), not on the push, a second later
    over the ssh tunnel. **The lit look is a rule of its own after
    `.verb.quiet`**: inside the choices' rule above it, `.verb.quiet` (as
    strong, and later) won, and a lit button looked unlit; the test compares
    the two grounds.
    `test_the_review_bar_carries_the_columns_and_the_width`,
    `test_the_file_line_carries_the_width_and_wrap_beside_the_code`,
    `test_a_button_beside_the_code_shows_its_choice_before_the_file_answers`.
    - **Every line's right-hand controls end on one line** (`--line-end`,
      24 px, the tab row's own): the Review bar, the commit message's md /
      txt, a file's card, the Files tab's file line; they stood at four
      insets. In the scrolling pane `--line-end-in` subtracts the
      pane's room for its bar (`scrollbar-gutter: stable` on
      `.diffscroll`, measured by `measureScrollbar` the same way: an empty
      `overflow: scroll` box said 0 px in Chromium while the pane kept 15).
      The read-as control is one button, "txt", as the reader asked, lit as
      the buttons beside the code.
      `test_every_right_hand_control_ends_on_one_line`,
      `test_the_file_line_ends_where_the_tab_row_ends`.
    **Labels are one word** ("tab", "lines", "diff", "links"), for room, as
    the reader asked. **One proportional face, `--sans`, labels and buttons
    too**, as the reader asked: a url in the fixed face made the menu as
    wide as the longest link. **A choice is shown at once, then kept**
    (`keepSetting`, `POST /api/settings`), and **made so by the push**
    (`takeSettings` on the `settings` event). **The POST's answer carries no
    settings**, only `done` and the `refused` links: pushes go out in the
    order the file was written, under `config_lock`, while an answer comes
    on another connection, landed before an older push and was undone by
    it. Numbered pushes were tried and removed: one line needs no numbers.
    Every open page gets the push, the one that made the change too, and a
    hand edit arrives the same way (`tell_config`). A change of the diff's
    columns from the file waits while a comment is written (`takeSides`), as
    `keepSides` does. **Changes go one at a time, each after the last was
    answered** (`settingsSent`): two quick clicks were two POSTs on two
    connections, the first landed second, and the file -- then, by the push,
    the page -- kept the older choice. The menu reads tab width and wrap
    from the settings (`readingWanted`), never off the root.
    `test_two_quick_changes_reach_the_file_in_the_order_they_were_made`.
    **So a test that changes a setting twice waits for each one's push**
    before the next change, or the first push lands after the second change
    and puts the old value back (#439, #606). It wraps `takeSettings` and
    waits for the word it expects. `test_the_c_key_steps_through_the_colours`,
    `test_the_colours_can_be_switched_and_are_remembered`.
  - **The ticket links are rows in the menu, saved on leave or Enter**
    (`putLinkRow`, `saveLinks`, `putLinkRows`): the reader chose that over a
    save button and over saving each keystroke, which linked half a pattern.
    A row is "find", a regular expression, and "link"; under it, the first
    match on the page and where it goes (`paintExamples`, when the menu
    opens and after a save, never on a push, as it reads the whole page's
    text), or why it is not saved, in red, on its box (`sayLink`,
    `data-bad`, the `field` the daemon names with `trouble_field`: read
    from the message's words, the wrong box went red when a pattern held
    them). **The page checks only what only it can**: a half row, and a
    pattern this browser will not compile (`linkProblem`). The rest is
    `link_trouble` in the daemon, once; `save_config` keeps the good links,
    leaves out the bad and names them by index (`refused`), so one mistake
    costs no other link. **The rows are the file's when the menu opens, and
    the reader's while it is open** (`putLinkRows`, from `showSettings`): a
    push never rebuilds them. A rebuild lost red, half-filled and empty new
    rows, none in any file; guards per way a push could land still failed
    (red one run in three at `-n 12`).
    `test_a_link_that_cannot_be_used_is_red_and_the_others_are_kept`.
    **The rows span the whole Links group, and both boxes reach the row's
    right edge** (`.linkedit`, `.linkrow`, `.linkdrop`): the reader asked
    for room for a pattern and a url. So the group has no label in the
    labels column (its title names it); "remove" stands under the boxes (an
    × beside the first box took its room); the second box's word is "link",
    not "link to". The menu has a set width (`width` on `.setpop`) and
    columns `max-content 1fr`: with two `max-content` columns the wide rows
    spread over both and every other setting stood far from its label; with
    `minmax(0, 1fr)` and no width, the absolutely placed, shrink-to-fit
    menu folded the controls to one word a line.
    `test_the_link_boxes_take_the_whole_width_of_the_links_group`,
    `test_the_settings_stand_in_four_titled_groups`.
    **The outside click is read from the click's path** (`composedPath`),
    not from where its target is now: × takes its own row out, its target
    leaves the page, and the menu shut. **And from where the press began**
    (`pressedOn`, #485): a selection in a link box let go outside the menu
    is a click on `body`, and the menu shut. A press that began inside is
    inside, for the model menu too.
    `test_a_selection_that_ends_outside_the_menu_keeps_it_open`.
    **The colours buttons wear the colours they give** (`--light-bg`,
    `--dark-ink` and the rest, in the first `:root`, which the theme blocks
    read for `--bg` and `--ink`), so they read the same in either theme.
    **Each label stands on the first line of what it names**: the grid
    lines up baselines, because padding left "alerts" 5 px under the first
    checkbox. `test_every_settings_label_stands_level_with_what_it_names`.
    **Alerts off is a mark on the button** (`.offmark`, `data-alerts`, set
    by `drawBell`): off was the one thing the bell said at a glance. A
    choice changes the page in place: colours and reading on the root,
    columns through `keepSides`. The alert boxes keep their ids, so
    `setAlert` works as it did. `c` still cycles the colours (`nextTheme`).
    `test_the_settings_say_what_is_chosen_and_change_it_in_place`,
    `test_the_alert_panel_shuts_from_anywhere`,
    `test_alerts_are_off_until_you_ask`.
- **What a row offers is icons in the age's place, on its hover** (#389): a
  moon for "not now" and a sun to wake it, a clock for "later" and the clock
  struck through to cancel, a dot for "unread" (`.act`, `setIcon`,
  `ICONS`). As words they cut long names short, and "not now" broke over
  two lines when narrow. **The age goes while they show** (`.age.swap`,
  only on a row that offers any), and they are `margin: -3px 0` because 22
  px is taller than the line: the row keeps its height. Where the age was
  short ("3s") they take under 60 px of the name's room, half what words
  took. **Not there at all until the hover** (CLAUDE.md's CSS rule:
  `display: none`, never `opacity: 0`). **The snooze's moon is hover-only too**: the word "snoozed" marks
  the row, and `z` works without the pointer. `setIcon` keeps the kind in
  `data-icon`, which a test reads.
  `test_the_row_offers_unread_on_a_read_row_only`,
  `test_a_snoozed_session_stops_saying_it_needs_you_until_it_asks_again`.
- **A row says what nothing else on the page says, in four lines that are
  the same on every row**, each the reader's choice: the name; repository
  and worktree, with remote and path on hover; the branch with git's counts
  at the right edge; what the agent does or asks, only while it does. The
  time stands beside the name.
  - **Not the state.** Edge, tint and group say it; a word at the top,
    "waiting for input" at the foot and a dot said it three more times.
    Only a finished row keeps the word, because "ended" and "killed" share
    one group and one grey. The dot's pulse is now the needs-you row's own.
  - **The name is the one Claude Code shows** (`rowName`, `Session.title`,
    #351): the reader's from the page while it is newer, then the status
    line's `session_name` (`customTitle ?? aiTitle`), then the first prompt
    that is not a command (`first_prompt`), then `place`. **This reversed a
    rule** that showed `place` until the reader named it, because Claude
    Code's title went stale beside the branch. The reader asked for one name
    in both places; a page rename reaches Claude Code by `/rename`, so a
    stale title is a keystroke from right. The second line still says where
    it stands.
    **A typed name bridges; a name nothing was typed for stands**
    (`Marks.page_name`). A name the page typed as `/rename` is kept with
    Claude Code's name just before (`Marks.over`) and shown until that
    moves: then the status line carries ours, or a later terminal
    `/rename`. The bridge is long: at an idle prompt the status line runs
    again only next turn. A name nothing could be typed for is the page's
    alone and stands until the reader changes it, as does one a `/clear`
    moves (`link_clear`): Claude Code does not carry a `/rename` into the
    new session. **"Last wins" against the terminal was built and
    removed**: the status line says what the name is, not when it was set,
    so a stale status made an earlier rename look later and dropped the
    reader's. An empty `over` taken as "Claude Code's first guess"
    swallowed a real `/rename` the same way. **`page_name` never writes**:
    `settle` runs in `ls` and `wait` too, each with its own copy of the
    names, and one that wrote lost a name the daemon had just been given.
    `Store.rename`, the one writer, prunes a typed name Claude Code took.
    `test_a_typed_name_stands_until_claude_codes_moves`,
    `test_a_name_nothing_was_typed_for_stands_until_the_reader_changes_it`,
    `test_reading_the_names_writes_nothing`.
    **It wears the sans face**: fixed, it was half as wide again as the
    lines under it. The age beside it stays fixed, so digits do not dance.
  - **A ticket in the name, worktree or branch is a link** (`linkTickets`):
    a branch is most often named after its ticket. Each part is rewritten
    only when its text or `state.links` changed (`fresh` on `slot`,
    `where`, `two`): `fillRow` runs every push, and a link rebuilt between
    press and release is a lost click. A click on a link chooses nothing; a
    double-click on one starts no rename. `renameRow` forgets the name's
    key, or the name stays empty after the box goes. **`state.linksKey` is
    in `drawSessions`' key, not the count**: a pattern changed in the menu
    left the count unchanged and the rows kept old links. **`takeLinks`
    calls `drawSessions` itself**: links can change after the last sessions
    push, and then nothing redrew the rows.
    `test_a_ticket_in_a_rows_name_or_branch_is_a_link`.
  - **The git line is one line.** All on it keeps its width but the branch,
    which takes an ellipsis: "✓ clean" shrank with it and broke over two
    lines. It sets `display: flex`, and the one `[hidden]` rule still hides
    it (`daemon-and-page.md`).
  - **A name is changed where it stands** (`renameRow`), by double-click or
    `e`. The row is refilled every push, so `fillRow` leaves a name with a
    box in it alone; a moved row loses focus, so `drawSessions` gives it
    back with the caret in place. Enter on the name the box came with keeps
    nothing, or the row would stop following its worktree for good.
  `test_a_row_says_its_name_where_it_is_its_branch_and_when`,
  `test_the_git_line_is_one_line_and_its_counts_stand_at_the_right`,
  `test_a_row_is_renamed_where_it_stands`.
- **The chosen row is a tab of what stands beside the list, as in a
  browser**: a faint ring had to be looked for. It runs through the list's
  padding to the grip, its ground fades from the state's colour into
  `--meet`, and the grip opens where they meet; the reader chose each part
  from pictures.
  **It is the strongest row in the list** (#396): its state's colour
  (`--hue`, set with `--soft` on every state) at 34 % in `--meet`, held to
  half its width before the fade, a 1 px line round it in that colour at
  55 %, and a 6 px edge with 2 px less padding, so its text stands where
  it would. Fading the half-transparent tint into grey made it the palest
  row, and it could not be found. **A shadow was refused**: it does not
  show on the dark ground, and lifts a tab off what it belongs to. **Its
  line is as wide as the other rows' own** (1 px, transparent on theirs):
  2 px lines in `--edge` vanished once the list wore `--edge`, and cut the
  corner of the state's edge. So the grip opens over the row's whole
  height, border and all (`openGrip`).
  **Every row runs to the line**, as a tab behind the chosen one: cards with
  four round corners read as buttons.
  - **A chosen row is never see-through** (#427): a finished row is faded
    (`opacity: .72`); chosen and faded, it ended on a grey mix and its edge
    stood out against the content. `.row.ended:not(.chosen)` fades the
    others only; the chosen one's name is bright, as on any chosen row.
    `test_a_chosen_finished_row_is_as_whole_as_any_chosen_row`.
  - **The list wears the grip's colour (`--edge`), and a split tab's own
    list -- the map, a file tree -- wears `--meet`.** The grip then reads as
    the list's edge, crossed only by the chosen row, and the map stands
    apart without a line. `--meet` is `--panel`, set on `.body`, as every
    tab is split; the map's ground, the fade's end and the grip's opening
    all read it, so the row flows into what is there.
  - **The chosen row has no ground colour of its own, only the gradient**,
    mixed into the opaque `--meet`. The state tints are half transparent: on
    the list's old ground it came out brighter in light and darker in dark
    than its group. `test_a_row_shows_its_state_in_its_colour` reads the
    first row, chosen or not, so it holds both.
  - **It stands in from the other rows by the grip's width**
    (`calc(4px + var(--grip-w))`), as it crosses the grip on the right; the
    reader chose this over standing out to the left.
  - **The grip is outside the scrolling list, so `openGrip` tells it where
    the row is**, as `--gap-top` and `--gap-bottom`: after every
    `drawSessions`, on the list's scroll, on resize, and from a
    `ResizeObserver` on the chosen row. Only the shown part opens it,
    nothing when the row is out of view. The draw covers a row arriving
    above the chosen one: nothing scrolls or resizes then.
  - **The list's scrollbar shows only while the pointer is on it**: between
    row and grip it cut the tab from its content in both themes. The wheel
    scrolls without it.
  - **Its outline turns into the content's edge and runs on down it**
    (#407): ending square at the list's end, it was two lines stopping for
    no reason. Where the row meets the grip, a quarter circle of `--flare`
    turns the line upright and the ground inside the curve is `--meet`, so
    the row widens into the content as a tab into its page; above and
    below, a 1 px line in the row's colour (`--gap-line`) runs down the
    content's edge. The reader chose it from a picture over the corners
    alone. **All of it is the grip's own background**, layers under
    `#grip.open`: the list scrolls and clips what a row draws outside it.
    The circle's middle stands 3 px into the list, so the curve starts on
    the row's line and ends upright on the content's edge; the 6 px between
    rows leave no room for more, and the grip's 5 px radius could not be
    seen. **A corner only where the row's end is in view** (`flaretop`,
    `flarebottom`), no line when the row is out of the list. A test reads
    pixels (`pixels`): a gradient's shape is in no computed style.
    - **The line is mixed from the row's `--hue`, never read off its
      border** (`--gap-hue`, #416): the border fades in over .2 s, so read
      at a choice it was nearly transparent, and every click left line and
      corners colourless until the next push. A custom property does not
      transition. A test reading a colour after a choice waits for
      `getAnimations()` to be empty, and reads nothing a push could refresh.
      `test_the_outline_keeps_its_colour_when_another_row_is_chosen`.
    - **Only the grip's colour fades, never its layers**
      (`transition: background-color` on `.grip`): with
      `transition: background`, the custom property does not transition but
      the `background-position` computed from it does, so leaving the grip
      slid corners and line down to the row (a flicker), and every scroll
      moved them a step behind.
      `test_the_opening_in_the_grip_never_slides_into_place` asks
      `getAnimations()` in the same frame as the change, so a loaded runner
      cannot end the transition first.
  `test_the_chosen_row_is_a_tab_of_the_content_beside_it`,
  `test_the_chosen_row_turns_into_the_content_s_edge`.
- **A drag on an edge starts only on the main button, and ends every way a
  press can end** (`dragWidth`, for the session list's edge and every split
  tab's). On Linux and macOS a right-click's context menu takes the
  `pointerup`, and the column followed the mouse with no button held,
  `body.dragging` on, until the next click. A touch the browser takes for a
  scroll ends in `pointercancel`, not `pointerup`. So the grip captures the
  pointer, and `pointercancel` and `lostpointercapture` end the drag too.
  Headless Chromium opens no menu and, under Playwright, sends no lost
  capture, so the test sends those events by hand.
  `test_a_drag_on_an_edge_starts_only_by_hand_and_always_stops`.
  - **One drag for a width and a height** (`dragEdge`; `dragWidth`, and
    `dragHeight` for the send bar's top edge, #442): capture and ends live
    in one place, so a third edge cannot forget them. The height goes on the
    root as `--say-h` or `--reviewsay-h`, kept like a width, and is the
    least the box is, empty or full: as a cap only, a drag on an empty send
    box did nothing. **It is not the most** (#453): as both, Shift and Enter
    added a line the box did not grow for. It grows to 40vh or the dragged
    height, whichever is taller. A double-click gives the box back to
    `fitSay`. `test_the_send_box_is_as_tall_as_its_edge_is_dragged`,
    `test_the_review_is_as_tall_as_the_bars_edge_is_dragged`.
  - **An edge between two grounds draws no line, and its handle is wider
    than it** (#443): the page was busy with lines that all looked alike.
    The two grounds already part list and pane, so the grip is
    `--split-grip-w` wide and draws nothing; its `::after`, 3 px wider each
    side, is the handle, faintly amber under the pointer (`.hgrip` is the
    send bar's). Before a new line, ask whether a ground already draws it.
    `test_the_maps_edge_draws_no_line_and_drags_from_beside_it`,
    `test_a_line_between_two_grounds_is_not_drawn`.
- **A column folds to a strip that holds only its button** (#464, `FOLDS`,
  `putFold`, `paintFold`, `unfold`, `folded`, `#sessionfold`, `.fold`,
  `body.foldsessions`, `body.foldlist`, `--fold-w`). On a laptop the session
  list and a split tab's list took 615 of 1366 px. The reader chose a button
  on each column over one for both and over folding by width alone.
  - **It is a class on `body`, never on the column**: `split` rebuilds a
    split tab's list on every switch, and the sidebar's grip and `.main`'s
    grid columns must know too. The list column is one for the three tabs,
    as `--side-w` is, so it folds on all three.
  - **The button stands in the column's `.findslot`, ordered before the find
    box by CSS** (`order: -1`, #492): `homeFind` appends `#find` to the
    slot, so the markup is no guide. The reader asked for it at the column's
    left, in both columns. **Folded or open, it stands in one place**
    (`--fold-in` from the column's edge, and as far from the box): it is
    pressed to fold and again to unfold without moving the pointer. The
    button's margin takes back the open slot's padding; the strip no longer
    centres it. Its middle is the box's middle. **Each fold's rule names its
    own column** (#504): `.foldlist .findslot > .fold` matched the session
    list's slot too, so folding the list beside the transcript moved the
    session list's button and narrowed its filter box.
    `.foldlist .content.split > .side > .findslot`.
    `test_a_fold_button_stays_where_it_was_pressed`.
  - **A folded column's edge drags nothing** (`pointer-events: none`): a
    drag set a width nobody could see.
  - **`f` and `/` unfold the column they type into**: nothing is focused in
    a column with `display: none`, so the key did nothing.
  - **No `openGrip` on a fold**: the chosen row hides and returns with its
    list, and `gripWatch` observes it. A call there stayed green under
    `tests/perturb.py` and was removed.
  - **Folded, every session is a tile, and the tiles are the rows**
    (`markRow`, `tileTitle`, `data-name`, `.foldsessions #rows`): a strip
    with one button hid who needs you; the reader asked for every session,
    clickable. A second list would need its own clicks, order and pushes.
    CSS draws each row as a tile as tall as a row, its name turned up it
    (`writing-mode: vertical-rl`, then `rotate(180deg)`, read bottom to top)
    on its state's colour, with the unread dot; the reader chose the turned
    name over two letters across, which told sessions of one repository
    apart only by colour. A click chooses, `j` `k` move, and every push
    fills a tile as a row. The chosen tile wears the chosen row's gradient,
    edge and line (the reader asked), runs to the grip, and the grip opens
    beside it.
    **On hover, the row whole, in the tile's own place** (`tileCard`,
    `#tilecard`, #491): name, where it stands, state and line, as the open
    list draws them, over the tile and the page, at least as tall as the
    tile. The reader asked for the whole row over the name alone in `title`
    after a wait, and for the one tab opened out over a second tab beside
    the strip. The card is a copy of the row (`cloneNode`), so it says what
    the row says and is drawn in one place; no row carries a title any more
    (`tileTitle`), or the browser's would stand on the card. Nothing on it
    is pressed: the tile is.
    **A name too long fades out at its end (`mask-image`), never an
    ellipsis**: "…" took three letters' room, and the reader asked for the
    fade. The name's box is the tile's whole length, so the fade covers its
    last 16 px and a short name never reaches it.
    **The rules are anchored on `#rows`**: a class-only rule lost to
    `.row .line1` and `.row.chosen`, later at the same weight, and the
    folded strip drew every row's text over the content.
  - Kept in `localStorage` (`wostuast-fold-sessions`, `wostuast-fold-list`)
    as a width is: it is not a setting in the menu.
  `test_each_column_folds_away_and_comes_back`,
  `test_the_list_column_folds_on_every_split_tab`,
  `test_a_key_into_a_folded_column_brings_it_back`,
  `test_a_folded_session_list_is_a_tile_for_each_session` (the card too).
- **Rows are kept and filled in again, never rebuilt.** A row fades into its
  new colour, and the needs-you pulse finishes a cycle, only if the row
  outlives the change. `newRow` builds every part once, empty; `fillRow`
  reaches them by position; a row moves only when its place changed,
  because `appendChild` on an attached node is a remove and an insert.
  - **And filled only when what it shows changed** (#431): its session and
    children by object (`row.filledWith`), the page facts it shows by their
    text (`dataset.sig`) -- the choice, the links, the reminder's word, time
    and due, its subagents' fold. Filling all 500 rows took 34 ms every
    push. **By object, because a session is never changed in place**
    (#435): every session the page holds is frozen, and `patchSession` is
    the one way to change one, by a new object; four in-place writers (a
    rename, a reminder, a snooze, an unread mark) had forced a JSON compare
    of each row. **A session that reads the same stays the same object**
    (`takeSessions`, `sameOrNew`): a stream's opening, the first push after
    a daemon start, and a patch that changes nothing each made every row
    new. **`opened` fails any test whose page wrote a frozen session**, so
    the whole browser suite holds the rule.
    `test_a_session_is_changed_only_by_patch_session`. **A choice changes no
    session**, and a read row gets no push, so the choice is in the
    signature, or the row chosen before kept its look. **A change no row's
    data shows goes through `redrawRows`**, which clears every signature: a
    closed rename box left its name empty. **The ages are read off the
    page** (`tickAges` reads `.age[data-since]`), so a row left alone still
    ticks. `test_a_push_fills_only_the_rows_it_changed`,
    `test_a_row_is_renamed_where_it_stands`.
