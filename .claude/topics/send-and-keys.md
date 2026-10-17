# The send box and the keys

The send box and the question bar, a send that lands, completing a `/`, a rename, and the keys.

- **`name` keeps the page's name, and types `/rename` where it may**
  (`verb_name`, `type_rename`, #351). `/rename` fires no hook; the daemon
  hears of it from the status line's `session_name`, which is
  `customTitle ?? aiTitle` and follows at once (2.1.288,
  `tests/claude_pane.py`). It writes `custom-title` and `agent-name`
  records, starts no turn, and runs at once inside one, so a working
  session is typed into. Never typed into: one that needs you, one with a
  question on screen (`asking`, set just before the `PermissionRequest`),
  one `cannot_type` refuses; the name stays the page's, `kept_here` says
  why, `keepRename` notes it, and nothing types later. A name equal to the
  status line's is typed anyway: it can be stale. **It cannot see** a draft
  in the prompt box (submitted with the command) or an MCP form (only a
  late `Notification`); nor can a send. `Store.rename` replaces the whole
  map, as `rows` does: the HTTP thread writes, the fold thread reads. It
  pushes nothing; the next pass builds rows from the names.
- **The send box and the question bar start where the transcript does, the
  map running down beside them, by the grid, never by moving the bars into
  the pane**: a node that changes parents is rebuilt and loses unsubmitted
  picks and typed text; full width they sat under the map, and a
  `margin-left` left an undraggable corner. `.main` is a grid of the split
  tab's columns (`--side-w`, `--split-grip-w`); `.content` spans the rows
  under the tabs, the bars its last two; `.content.split` passes the grid
  on with `subgrid`, so map and grip span every row.
  - **The bars carry `position: relative`**: the positioned `.content.split`
    painted over them and took every click.
  - **`.tofoot` is a grid item in the pane's cell, not `position: absolute`
    against the box**: Chromium measured it from the whole subgrid box.
  `test_the_map_and_its_grip_run_down_beside_the_send_box`; the clicks:
  the question and send-box tests in `test_page_act.py`.
- **A send to an agent at its prompt is seen to land, or comes back**
  (#489, `press_send`'s `watch`, `prompt_landed`, `SEND_WAIT`,
  `TYPED_KINDS`, `seen: false`): with `/config` open the keys went into the
  dialog and the emptied box lost the message. With no `user` record at or
  after the typing, the daemon answers `seen: false` and the page puts the
  text back. **Only at its prompt, never a slash command**: a busy agent's
  message lands when taken, maybe minutes on, and a slash command may
  write nothing. No transcript, no watch. `in_pane`'s tmux writes the
  prompt, or every sending page test gets its text back.
  `test_a_send_claude_code_never_took_is_said_and_given_back`,
  `test_a_send_to_a_busy_agent_is_not_watched`.
  - **Up in an empty send box recalls what this browser sent** (`keepSent`,
    `recallSent`, `SENT_KEPT`, `wostuast-sent`); Down goes newer, then
    empty. Only while the box is empty or holds a recall: the reader's words
    keep the arrows for the caret. A send that came back is in the box, so
    not kept. `test_a_send_claude_code_did_not_take_comes_back_and_up_recalls_one`.
- **A tall send box says how much it holds, over the button** (`sizeSay`,
  `SAY_ROOM`, issue 332): at the end of a long log nothing shows its
  length. "2.4k lines", "112 KB" (`roughly`, `sizeOf`) in sans: the reader
  refused the fixed face and "2,400" (two rows).
  - **In a column with the button, `.sendside`, not over the bar**: over
    it, a wide size ran past the box. `.sendside > .verb` keeps the button
    32 px, level with the last line (`.say + .verb` no longer reaches it).
  - **From `fitSay`**, which every change passes: key, paste, the send that
    empties, the refusal that refills.
  `test_a_tall_send_box_says_how_much_it_holds`,
  `test_the_size_goes_when_the_send_box_empties`.
- **Ctrl+Enter (and Cmd+Enter) presses the button of its box**: send box,
  review comment, reason for a No, whole-review comment; the reader's usual
  key did nothing there. `submitOnCtrlEnter` only clicks, so the button's
  checks run and a disabled one ignores it. **The button stands level with
  the box's first line**: `.say { line-height: 18px }` makes a line 32 px,
  as `.say + .verb` is (it was 26 beside 32; `line-height: 1.5` 1.5 px off).
  `test_ctrl_enter_saves_a_comment_and_sends_the_review`,
  `test_ctrl_enter_sends_and_says_no_and_the_buttons_stand_level`.
  - **Every one of these boxes shows all it holds, its placeholder too**:
    `.say` and its placeholder wrap (`white-space: pre-wrap`), and an
    unsized one-row reason box cut "(optional)" and a long reason in half.
    `fitSay` sizes it (Chromium counts a placeholder in `scrollHeight`) by
    `getClientRects()`, since it is in no form. As wide as No's group
    (`.permnogroup .permwhy`), on its own row; `--fits` went with the old
    line of buttons.
    `test_the_reason_box_shows_its_placeholder_and_what_is_typed_whole`.
  - **The Enter that ends an IME composition is the input method's**
    (`composing`): taken, it sent half a message or kept half a name. Read
    `isComposing` (Chromium) and `keyCode` 229 (Safari, which sends it after
    the composition). It only stops a send, skipping none of its checks.
    `test_the_enter_that_ends_a_composition_sends_nothing`,
    `test_the_enter_that_ends_a_composition_keeps_no_name`.
- **A `/` at the start of the send box completes from files and
  transcripts, asked for each time the list opens** (#268). `Commands.of`:
  `skills/<name>/SKILL.md` and `commands/<name>.md` under `.claude` from
  the session's directory up to `worktree_root` (`project_dirs`, nearest
  first, both resolved: git gives the real path), then `claude_dir()`, then
  what `<command-name>` says ran in any transcript.
  - **Built-ins come from the transcripts, never a copied list**: `/clear`
    and `/compact` are in no file, and a list goes stale each release.
    `Commands.used` reads on from where it stopped (`Tail`), parses only
    lines with `<command-name>`, recounts a rewritten file.
  - **A mention is not a use**: `command_used` asks `read_user_text`, and an
    `isMeta` record is Claude Code's. A `system` `local_command` record is
    a use too.
  - **Not pushed with the row**: rows go out on every change and the list
    is kilobytes (the ssh rule). Fetched as `commands` when the list opens,
    dropped when it shuts (`closeSlash`), so a new skill shows next time.
  - **What no real machine showed is left out, not guessed**: a command in
    a subdirectory of `commands` (topics/payloads). `glob`, not `rglob`.
  - **A plugin's commands are read where Claude Code installed them**
    (#413, `plugin_dirs`, `enabled_plugins`, layout in topics/payloads),
    or they showed as built-ins with no file. Only when `enabledPlugins` has
    it on (yours, the project's `settings.json`, its `settings.local.json`,
    nearest last), and a project-scoped one only there. **Only a folder
    under `~/.claude/plugins` is read** (`inside`): no reader of the page
    chose the paths in Claude Code's list. `came: "plugin"`, "from your
    plugins". `test_a_plugins_commands_are_read_where_claude_code_installed_them`,
    `test_a_plugin_is_read_only_where_it_is_on`.
  - **The list's keys come first** (`slashKey`); Tab takes the chosen row.
    **Enter takes only a row the reader chose** (`enterTakes`): an arrow
    (`slash.moved`), or a word that starts the name and is not all of it.
    Always taking, it turned an unlisted `/doctor` into `/docs-to-review`
    and sent it, and a whole name took two Enters. Escape keeps the list
    shut (`slash.dismissed`) until the word is gone **or sent**:
    `sendTyped` fires no input event, and the next `/` opened nothing. A row
    takes on `mousedown` with `preventDefault`: a click's blur shuts the
    list first.
  - **A `/` after white space completes too, only what has a `file`**
    (#368, `slashSpot`, `drawSlash`): there Claude Code runs nothing but
    tells the model "the user's message contains /deploy, which is the name
    of a skill", for skills and command files, not built-ins (2.1.288,
    `tests/claude_pane.py`). Inside a word, nothing: `src/main.py`.
    `takeSlash` replaces the word in place.
    `test_a_slash_in_the_middle_of_a_message_completes_too`,
    `test_a_slash_inside_a_word_opens_nothing`.
  - **An answer for a box the reader left opens nothing**: `followSlash`
    checks focus and session after its fetch, or the list opens with no box.
  - **Commands is a view, not a tab** (#411, `toggleView`, key `4`): a tab
    is one session's, but most commands are none's (yours in `~/.claude`,
    the built-ins) and a project's are all its sessions'. `loadCommands`
    asks one session per worktree (`projectSessions`, on the row's `root`)
    by the existing routes; yours and built-ins once, then each project
    under `projectName` (repository, plus worktree when two share one).
    **A project's command is that project's**: rows are keyed by
    `commandKey` (session asked, name), as two may have `/deploy`. **"use"
    types into the chosen session when it can run the command, else into
    the session asked** (`useTarget`), and chooses it. Reading face, names
    too (#414).
  - **The view reads a command by its name** (#367, `drawCommands`,
    `verb_command`): nearest first in `Commands.defined`; the verb sends
    only the text, the rest is the list's entry (`commandOf`). Text without
    frontmatter: `after_front` asks `front_end`, as `front_matter` does
    (two splits drew a CR file's frontmatter as rules). **"use" fills the
    send box and types nothing** (`useCommand`): the reader chose that over
    a send button. **It and the `/` list put a command one way,
    `putCommand`**: a second spacing rule joined two lines. It keeps a draft
    after, replaces a command at the start, and where nothing can be typed
    says why (`whyNotTyped`). `tests/test_page_commands.py`.
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
  Tab sets, a pointer press clears). Always jumping left the keyboard
  unable to press anything, yet a clicked button keeps focus and Enter there
  is the jump. `:focus-visible` cannot tell: a key on a clicked button
  turns it on first. `test_enter_on_a_button_reached_by_keyboard_presses_it`.
  **A shortcut that acts blurs a button the pointer pressed; one
  `focusedByKey` reached keeps its ring**: else a dark ring stayed on the
  tab just left. `test_a_key_leaves_no_ring_on_a_tab_that_was_clicked`.
- **Few keys, none the reader never presses; one returns only when asked
  for.** `j` `k`, `n`, `r`, `t` went: unused, each hid the used `1` `2` `3`
  in `?` (`3` is the review). `test_the_keys_nobody_pressed_are_gone`.
  - **`b` was asked for** (#354, `goBack`, `state.before`): back to the
    session before, and again to return; kept by `choose` in
    `sessionStorage`, per browser tab like the address, so a reload keeps
    both. Follows a `/clear` (`cleared_into`). A forgotten or filtered-out
    session is not gone to, and `note` says why: an unseen row reads as the
    key doing nothing. `test_b_goes_back_to_the_session_before_and_again_returns`,
    `test_b_says_why_it_cannot_go_back`.
  - **From a box, Esc then the number; no Alt+number** (#470): in a box a
    number is typed, and the reader chose Esc because Chrome and Firefox on
    Linux take Alt+1-8 and a Mac types a symbol. Every box leaves on Esc
    (`#say` keeps its text; `#find`, `#pick` clear); `?` and the guide say
    so. `test_esc_leaves_a_box_and_a_number_then_picks_a_tab`.
