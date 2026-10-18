# Alerts

The two alerts, what an alert says, the counts, the tab's title and icon,
and the robot.

- **There are two alerts, not one switch.** Needs-you: the agent cannot go
  on without you. Finished: a turn you can read. One switch takes the
  unwanted one with the wanted. `alertsWanted()` reads both from our
  `settings.json`, whose shape the daemon checks (`config_trouble`). The
  browser's permission stays the browser's. **Needs-you is on the moment
  alerts are**: it is what this tool is for, so a browser that granted
  permission, under a file that says nothing, gets it unasked.
- **"Finished" is a change, not a state**: read as a state, `done` would be
  announced every push. `wasDoing` holds what each session did last pass,
  written **on every pass whatever the switches say**: a box ticked
  mid-turn still tells you when it stops, and a session that reached
  `done` unheard is no change waiting. `waiting` is the same for amber,
  filled **whenever the needs-you alert is not sent**, or switching it on
  announced every row gone amber meanwhile
  (`test_turning_needs_you_on_brings_no_backlog`). **Every alert says
  `renotify`**: a second alert with a session's tag replaces the first
  silently unless it asks (`test_every_alert_makes_itself_heard`). The
  test ticks the box mid-turn, or it passes with the recording moved
  inside the switch.
- **An alert says what, where, and in the colour of what** (`tellAbout`,
  #330): "needs you" and a bare `reason` said too little.
  - **What**: the question itself, from `asking` (`waitsFor`), since the
    `reason` names only its header; a permission's `reason`; for a
    finished session, the prompt it finished (`shown_prompt`).
  - **Where**: folder and branch, the row's second line.
  - **The tab's robot** (`iconPicture`, the one drawing `drawIcon` uses),
    amber for needs-you, grey for finished, **drawn at `ALERT_ICON`,
    192 px**: the system shows it at 64 px or more, and 32 blurred.
    `robotPicture` draws on 32 and scales.
  - **Needs-you stays until clicked or closed** (`requireInteraction`), or
    one that came while the reader was away said nothing. Finished goes on
    its own.
  - **Nothing the agent or the reader wrote goes out whole**: an alert can
    stand on a locked screen, so the prompt is `clip_hidden` to
    `PROMPT_SHOWN`, and a permission is its hidden `reason`, never the
    dialog's `fields`. **Once a prompt, not once a row**
    (`Session.prompt_shown`): `clip_hidden` costs 170 µs on 500
    characters, and rows are built for every session every tick.
  `test_an_alert_that_needs_you_says_what_and_where_and_stays`,
  `test_a_question_is_said_as_the_question`,
  `test_a_finished_agent_says_what_it_finished_and_goes`,
  `test_the_shown_prompt_is_worked_out_once_a_prompt`.
- **The counts are about every session.** `drawCounts` runs *before* the
  guard that asks whether the shown rows changed, or a session the filter
  hid went amber and reached no title, icon or alert. **The alerts are
  not a draw's at all** (#542): `onSessions` rings them where
  `state.sessions` is written -- the push, `patchSession`, the reminder
  timer -- with the review prune, the reminder timer and the unread view's
  `askLast`. Inside `drawSessions`, a filter typed or a row chosen could
  ring, arm, write and fetch. **No counts on the page**: "1 ready",
  "3 sessions" repeated the groups. The tab's title and icon, and the
  alerts, are what count.
  - **The title names who needs you, and leads with it** (`tabTitle`):
    "fix-login asks", "fix-login, api-retry +1 need you", else "2 working",
    "4 ready". A tab cuts its title's end, and "(1) needs you" did not say
    who. Names are `rowName`'s, so tab and list agree; **so are the
    alerts'** (`notifyAbout`): `label` named a session not in the list.
    `test_an_alert_names_the_session_as_its_row_does`.
  - **The icon is a robot, and the whole of it is the state**
    (`paintIcon`): the bar's own ink when nothing waits, green, amber. A
    dot did not say what the tab was. It is cut out, so the bar shows
    through.
  - **It follows the browser's light or dark, never the page's theme**
    (`tabBarIsDark`, the `--tab-*` colours, which no theme block sets): a
    light page in a dark browser put a dark robot on a dark bar. The media
    query's `change` redraws it.
  `test_the_tab_title_names_who_needs_you`,
  `test_the_tab_icon_is_a_robot_in_the_states_colour`,
  `test_the_tab_icon_says_the_state_in_the_bar_it_stands_in`,
  `test_the_tab_icon_follows_the_browser_and_not_the_page`.
  - **The same robot stands before the name, in the name's amber**
    (`drawLogo`, `.brand .logo`, `.brandname`), the reader's choice: the
    tab icon says the state. It reads the name's colour, so `showTheme`
    redraws it; drawn at 64, three times its size, to be sharp. Folded, it
    is all the head shows (`.foldsessions .sidebar-head`).
    `test_the_robot_stands_before_the_name_and_in_the_folded_strip`.
