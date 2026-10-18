# The settings menu

`putSettings`, `paintSettings`, the quick settings beside the code, the
ticket links rows. topics/safety-install holds the file it writes.

- **Every setting is one menu** (`putSettings`, `paintSettings`,
  `#setpop`): colours, the two alerts, tab width, long lines, the diff's
  columns, ticket links, and the file's path at its foot (`#settingspath`,
  with a copy button), not a bell, a colours button and a Review-bar menu.
  **Four groups** -- Page, Code,
  Review, Links -- each a soft card with a bold title (`.setgroup`,
  `.settitle`). A group is a subgrid, so every label stands in one column.
  `test_the_settings_stand_in_four_titled_groups`.
- **Five settings are also beside the code they change** (`putQuick`,
  `QUICK`): the diff's columns, whitespace and code width at the Review
  bar's right end; the marks, code width and long lines on the open file's
  line. Whitespace means nothing on one file, so there it is the marks
  (#486, `keepMarks`, the `marks` icon).
  `test_the_marks_are_one_click_beside_a_file`. The menu still holds every
  setting.
  - **One button each, lit while its setting is on** (`.toggle`,
    `aria-pressed`), so one click switches it: an icon that shows the
    state cannot say if it is the state now or after a click. Icons only,
    words in `aria-label` and, with ": on" or ": off", in `title`: with
    words the Review bar ran out of room at 1366 px. The menu keeps words.
  - **They are the menu's settings, not copies**: `paintSettings` paints
    the menu's `.choice` and every `.toggle` from `settingsNow`, and a
    click paints at once (`keepWidth`, `keepWrap`, `keepSides`,
    `keepSpace`), not on the push a second later over the ssh tunnel.
  - **The lit look is a rule of its own after `.verb.quiet`**: inside the
    choices' rule, `.verb.quiet` won and a lit button looked unlit. The
    test compares the two grounds.
  `test_the_review_bar_carries_the_columns_and_the_width`,
  `test_the_file_line_carries_the_width_and_wrap_beside_the_code`,
  `test_a_button_beside_the_code_shows_its_choice_before_the_file_answers`.
  - **Every line's right-hand controls end on one line** (`--line-end`,
    24 px, the tab row's own): the Review bar, the commit message's md /
    txt, a file's card, the Files tab's file line. In the scrolling pane
    `--line-end-in` subtracts its bar (`scrollbar-gutter: stable` on
    `.diffscroll`, measured by `measureScrollbar` in such a pane: an empty
    `overflow: scroll` box said 0 px).
    The read-as control is one button, "txt", lit as these are.
    `test_every_right_hand_control_ends_on_one_line`,
    `test_the_file_line_ends_where_the_tab_row_ends`.
- **Labels are one word** ("tab", "lines", "diff", "links"), for room.
  **One face, `--sans`, labels and buttons too**: a url in the fixed face
  made the menu as wide as the longest link.
- **A choice is shown at once, then kept** (`keepSetting`,
  `POST /api/settings`), and **made so by the push** (`takeSettings` on the
  `settings` event), which every open page gets, the sender too. A hand
  edit arrives the same way (`tell_config`).
  - **The POST's answer carries no settings**, only `done` and the
    `refused` links: pushes go out in the order the file was written, under
    `config_lock`, but an answer on another connection landed before an
    older push and was undone by it.
  - **Changes go one at a time, each after the last was answered**
    (`settingsSent`): two quick clicks were two POSTs, the first landed
    second, and the file kept the older choice.
    `test_two_quick_changes_reach_the_file_in_the_order_they_were_made`.
  - A change of the diff's columns from the file waits while a comment is
    written (`takeSides`), as `keepSides` does. The menu reads tab width
    and wrap from the settings (`readingWanted`), never off the root.
  - **A test that changes a setting twice waits for each one's push**, or
    the first push puts the old value back (#439, #606). It wraps
    `takeSettings` and waits for the word it expects.
    `test_the_c_key_steps_through_the_colours`,
    `test_the_colours_can_be_switched_and_are_remembered`.
- **The ticket links are rows in the menu, saved on leave or Enter**
  (`putLinkRow`, `saveLinks`, `putLinkRows`): saving each keystroke linked
  half a pattern. A row is "find", a regular expression, and "link"; under
  it, the first match on the page and where it goes (`paintExamples`, when
  the menu opens and after a save, never on a push: it reads the whole
  page), or why it is not saved, in red, on its box (`sayLink`,
  `data-bad`). The daemon names the box as `field` (`trouble_field`): read
  from the message's words, the wrong box went red.
  - **The page checks only what only it can**: a half row, and a pattern
    this browser will not compile (`linkProblem`). The rest is
    `link_trouble` in the daemon; `save_config` keeps the good links and
    names the bad by index (`refused`), so one mistake costs no other link.
  - **The rows are the file's when the menu opens, and the reader's while
    it is open** (`putLinkRows`, from `showSettings`): a push never
    rebuilds them. A rebuild lost red, half-filled and new rows, and guards
    for each way a push could land still failed under load.
    `test_a_link_that_cannot_be_used_is_red_and_the_others_are_kept`.
  - **The rows span the whole Links group, and both boxes reach the row's
    right edge** (`.linkedit`, `.linkrow`, `.linkdrop`), so "remove" stands
    under the boxes. The menu
    has a set width (`width` on `.setpop`) and columns `max-content 1fr`:
    two `max-content` columns put every setting far from its label, and
    `minmax(0, 1fr)` with no width folded the controls to a word a line.
    `test_the_link_boxes_take_the_whole_width_of_the_links_group`,
    `test_the_settings_stand_in_four_titled_groups`.
- **Read the outside click from the click's path** (`composedPath`), not
  from where its target is now: × takes its own row off the page, and the
  menu shut. **And from where the press began** (`pressedOn`, #485): a
  selection let go outside the menu is a click on `body`. The model menu
  does the same. `test_a_selection_that_ends_outside_the_menu_keeps_it_open`.
- **The colours buttons wear the colours they give** (`--light-bg`,
  `--dark-ink` and the rest, in the first `:root`, which the theme blocks
  read for `--bg` and `--ink`), so they read the same in either theme.
- **Each label stands on the first line of what it names**: the grid
  lines up baselines; padding left "alerts" 5 px low.
  `test_every_settings_label_stands_level_with_what_it_names`.
- **Alerts off is a mark on the button** (`.offmark`, `data-alerts`, set
  by `drawBell`): off was what the old bell said at a glance. A choice
  changes the page in place: colours and reading on the root, columns
  through `keepSides`. The alert boxes keep their ids for `setAlert`. `c`
  still cycles the colours (`nextTheme`).
  `test_the_settings_say_what_is_chosen_and_change_it_in_place`,
  `test_the_alert_panel_shuts_from_anywhere`,
  `test_alerts_are_off_until_you_ask`.
