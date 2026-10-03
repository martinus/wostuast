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
  - **The name is the reader's, and until they give one, `place`**
    (`rowName`). Never the title Claude Code writes from the first prompt:
    `/rename` does not reach it, so it went stale beside the branch -- a
    row named after one ticket over a branch named after another. The
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
  reader chose each part from pictures. **Its outline is the other rows'
  own**: it had top and bottom lines of 2 px in `--edge`, chosen while the
  list had another ground, and once the list wore `--edge` they could not be
  seen and cut the corner of the state's edge on the left. So the grip opens
  over the row's whole height, border and all (`openGrip`).
  **Every row runs to the line**, as a tab behind the chosen one: cards with
  four round corners read as buttons.
  - **The list wears the grip's colour (`--edge`), and a split tab's own
    list -- the map, a file tree -- wears `--meet`.** The grip then reads
    as the list's edge, which only the chosen row crosses, and the map
    stands apart from the page without a line. `--meet` is `--panel`,
    set on `.body`, because every tab is split now; the map's ground, the fade's end and the grip's
    opening all read it, so the row flows into what is there.
  - **The chosen row has no ground of its own.** The state tints are half
    transparent: on the list's old ground under it, it came out brighter
    in the light and darker in the dark than the rows of its own group,
    and the reader saw it.
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
