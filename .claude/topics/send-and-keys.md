# The send box and the keys

The send box and the question bar, a send that lands, completing a `/`, a
rename, and the keys.

- **`name` keeps the page's name, and types `/rename` where it may**
  (`verb_name`, `type_rename`, #351). `/rename` fires no hook and starts
  no turn; it writes `custom-title` and `agent-name` records, and the
  status line's `session_name` (`customTitle ?? aiTitle`) follows at once
  (`tests/claude_pane.py`). It runs at once, even in a working session.
  Never typed into: one that needs you, one with a question on screen
  (`asking`, set just before the `PermissionRequest`), one `cannot_type`
  refuses; there the name stays the page's, `kept_here`
  says why, `keepRename` notes it, and nothing types later. A name equal
  to the status line's is typed anyway: it can be stale. **It cannot
  see** a draft in the prompt box (submitted with the command) or an MCP
  form (only a late `Notification`); nor can a send. `Store.rename`
  replaces the whole map, as `rows` does (CLAUDE.md **Shape**), and
  pushes nothing.
- **The bars sit under the transcript, the map beside them, by the grid;
  never move them into the pane**: a node that changes parents is rebuilt
  and loses picks and typed text. `.main` is a grid of the split tab's
  columns (`--side-w`, `--split-grip-w`); `.content` spans the rows under
  the tabs, the bars its last two; `.content.split` passes the grid on
  with `subgrid`.
  - **The bars carry `position: relative`**: the positioned
    `.content.split` painted over them and took every click.
  - **`.tofoot` is a grid item in the pane's cell, never
    `position: absolute`**: Chromium measured it from the subgrid box.
  `test_the_map_and_its_grip_run_down_beside_the_send_box`; the clicks:
  the question and send-box tests in `test_page_act.py`.
- **A send to an agent at its prompt is seen to land, or comes back**
  (#489, `press_send`'s `watch`, `prompt_landed`, `SEND_WAIT`,
  `TYPED_KINDS`, `seen: false`): with `/config` open the keys went into
  the dialog and the message was lost. With no `user` record at or after
  the typing, the page puts the text back. **Only at its prompt, never a
  slash command, never without a transcript**: a busy agent takes a
  message later, and a slash command may write nothing. `in_pane`'s tmux
  writes the prompt, or every sending page test gets its text back.
  `test_a_send_claude_code_never_took_is_said_and_given_back`,
  `test_a_send_to_a_busy_agent_is_not_watched`.
  - **In a test, an empty send box is the send starting, not landing**:
    `sendTyped` empties `#say` before the POST (topics/safety-typing,
    "One send at a time"). Wait for the `send-keys` in `seen`
    (`wait_until`), then `sending.size === 0`; holding `**/send` 300 ms
    proves it. A box still full after a composing Enter proves no send.
    `test_the_enter_that_ends_a_composition_sends_nothing`,
    `test_the_send_box_types_into_the_terminal`.
  - **Up in an empty send box recalls what this browser sent**
    (`keepSent`, `recallSent`, `SENT_KEPT`, `wostuast-sent`); Down goes
    newer, then empty, only while the box holds no words of the reader's.
    A send that came back is not kept.
    `test_a_send_claude_code_did_not_take_comes_back_and_up_recalls_one`.
- **A tall send box says how much it holds** (`sizeSay`, `SAY_ROOM`,
  issue 332): "2.4k lines", "112 KB" (`roughly`, `sizeOf`), in sans, as
  the reader chose. It sits with the button in `.sendside`: over the bar
  it ran past the box. **`fitSay` sets it**; every change passes it.
  `test_a_tall_send_box_says_how_much_it_holds`,
  `test_the_size_goes_when_the_send_box_empties`.
- **Ctrl+Enter (and Cmd+Enter) presses the button of its box**: send box,
  review comment, reason for a No, whole-review comment.
  `submitOnCtrlEnter` only clicks, so the button's checks run. **The
  button stands level with the box's first line**:
  `.say { line-height: 18px }` makes a line 32 px, as the button is
  (`.say + .verb`; `.sendside > .verb` for the send box).
  `test_ctrl_enter_saves_a_comment_and_sends_the_review`,
  `test_ctrl_enter_sends_and_says_no_and_the_buttons_stand_level`.
  - **Every such box shows all it holds, its placeholder too**: `.say`
    wraps (`white-space: pre-wrap`), and `fitSay` sizes it by
    `getClientRects()`, since Chromium counts a placeholder in
    `scrollHeight`. The reason box is as wide as No's group
    (`.permnogroup .permwhy`), on its own row.
    `test_the_reason_box_shows_its_placeholder_and_what_is_typed_whole`.
  - **The Enter that ends an IME composition is the input method's**
    (`composing`): taken, it sent half a message or kept half a name.
    Read `isComposing` (Chromium) and `keyCode` 229 (Safari). It only
    stops a send. `test_the_enter_that_ends_a_composition_sends_nothing`,
    `test_the_enter_that_ends_a_composition_keeps_no_name`.
- **A `/` at the start of the send box completes from files and
  transcripts, asked for each time the list opens** (#268, `Commands.of`):
  `skills/<name>/SKILL.md` and `commands/<name>.md` under `.claude` from
  the session's directory up to `worktree_root` (`project_dirs`, nearest
  first, both resolved), then `claude_dir()`, then what `<command-name>`
  says ran in any transcript.
  - **Built-ins come from the transcripts, never a copied list**: `/clear`
    and `/compact` are in no file, and a list goes stale. `Commands.used`
    reads on from where it stopped (`Tail`), parses only lines with
    `<command-name>`, and recounts a rewritten file.
  - **A mention is not a use**: `command_used` asks `read_user_text`, and
    an `isMeta` record is Claude Code's. A `system` `local_command` record
    is a use.
  - **Not pushed with the row**: the list is kilobytes. It is fetched as
    `commands` when the list opens and dropped when it shuts
    (`closeSlash`).
  - **What no real machine showed is left out, not guessed**: a command
    in a subdirectory of `commands` (topics/payloads). `glob`, not
    `rglob`.
  - **A plugin's commands are read where Claude Code installed them**
    (#413, `plugin_dirs`, `enabled_plugins`, topics/payloads), only when
    `enabledPlugins` has it on (yours, the project's `settings.json`, its
    `settings.local.json`, nearest last); a project-scoped one only
    there. **Only a folder under `~/.claude/plugins` is read** (`inside`):
    the page's reader chose no path in Claude Code's list.
    `came: "plugin"`.
    `test_a_plugins_commands_are_read_where_claude_code_installed_them`,
    `test_a_plugin_is_read_only_where_it_is_on`.
  - **The list's keys come first** (`slashKey`); Tab takes the chosen
    row. **Enter takes only a row the reader chose** (`enterTakes`), by an
    arrow (`slash.moved`) or by a word that starts the name and is not all
    of it: always taking, it turned `/doctor` into `/docs-to-review`.
    Escape keeps the list shut (`slash.dismissed`) until the word is gone
    **or sent**: `sendTyped` fires no input event. A row takes on
    `mousedown` with `preventDefault`: a click's blur shuts the list.
  - **A `/` after white space completes only what has a `file`** (#368,
    `slashSpot`, `drawSlash`): there Claude Code tells the model of a
    skill or command file, never a built-in (`tests/claude_pane.py`).
    Inside a word, nothing: `src/main.py`. `takeSlash` replaces the word.
    `test_a_slash_in_the_middle_of_a_message_completes_too`,
    `test_a_slash_inside_a_word_opens_nothing`.
  - **`followSlash` checks focus and session after its fetch**: an answer
    for a box the reader left opens nothing.
  - **Commands is a view, not a tab** (#411, `toggleView`, key `4`): most
    commands belong to no one session. `loadCommands` asks one session per
    worktree (`projectSessions`, on the row's `root`); yours and built-ins
    once, then each project under `projectName`. **A project's command is
    that project's**: rows are keyed by `commandKey` (session, name), as
    two may have `/deploy`. **"use" types into the chosen session when it
    can run the command, else into the session asked** (`useTarget`).
    It uses the reading face, names too (#414).
  - **The view reads a command by its name** (#367, `drawCommands`,
    `verb_command`): nearest first in `Commands.defined`; the verb sends
    only the text (`commandOf`). `after_front` asks `front_end`, as
    `front_matter` does: two splits drew a CR file's frontmatter as rules.
    **"use" fills the send box and types nothing** (`useCommand`), as the
    reader chose. **It and the `/` list put a command one way,
    `putCommand`**: a second spacing rule joined two lines. It keeps a
    draft, replaces a command at the start, and says why where nothing can
    be typed (`whyNotTyped`). `tests/test_page_commands.py`.
  `test_the_project_and_your_own_commands_are_read`,
  `test_what_the_transcripts_say_was_run_is_counted`,
  `test_a_transcript_is_read_on_from_where_it_stopped`,
  `test_a_slash_offers_the_commands_and_tab_takes_one`,
  `test_enter_takes_a_command_and_escape_keeps_the_list_shut`,
  `test_the_list_is_asked_for_each_time_it_opens`,
  `test_enter_sends_what_was_typed_unless_a_row_was_chosen`,
  `test_an_answer_for_a_box_that_was_left_opens_nothing`;
  `tests/stage.py --commands --keys '#say=/'` draws it.
- **Enter jumps, except on a button a keyboard reached** (`focusedByKey`:
  Tab sets it, a pointer press clears it): a clicked button keeps focus,
  and Enter there is the jump; `:focus-visible` cannot tell them apart.
  `test_enter_on_a_button_reached_by_keyboard_presses_it`. **A shortcut
  that acts blurs a button the pointer pressed**, or a ring stays on the
  tab just left. `test_a_key_leaves_no_ring_on_a_tab_that_was_clicked`.
- **Few keys; one returns only when asked for**: `j` `k`, `n`, `r`, `t`
  went, unused, as each hid a used one (`1` `2` `3`) in `?`.
  `test_the_keys_nobody_pressed_are_gone`.
  - **`b` goes back to the session before, and again to return** (#354,
    `goBack`, `state.before`), kept by `choose` in `sessionStorage`, per
    browser tab. It
    follows a `/clear` (`cleared_into`). A forgotten or filtered-out
    session is not gone to, and `note` says why.
    `test_b_goes_back_to_the_session_before_and_again_returns`,
    `test_b_says_why_it_cannot_go_back`.
  - **From a box, Esc then the number; no Alt+number** (#470): in a box a
    number is typed, and browsers on Linux take Alt+1-8. Every box leaves
    on Esc (`#say` keeps its text; `#find`, `#pick` clear); `?` and the
    guide say so. `test_esc_leaves_a_box_and_a_number_then_picks_a_tab`.
