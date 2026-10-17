# The send box and the keys

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. The send box and the question bar, a send that lands, completing a `/`, a rename, and the keys.

- **`name` keeps the page's name, and types `/rename` where it may**
  (`verb_name`, `type_rename`, #351). This bullet said the status line
  kept the name a session started with and `/rename` did not change it;
  on 2.1.288 `session_name` is `customTitle ?? aiTitle` and follows a
  `/rename` at once (measured with `tests/claude_pane.py`). `/rename`
  fires no hook, so the status line is the only way the daemon hears of
  one. It writes a `custom-title` and an `agent-name` record with the same
  name. At the prompt it starts no turn; during a turn it is done at once
  and the turn goes on, so a working session is typed into. Not one that
  needs you, one with a question on screen (`asking`, set a moment before
  the `PermissionRequest`), and not one `cannot_type` refuses: the name is
  the page's alone then, and the answer's `kept_here` says why, which
  `keepRename` puts in a note. It waits for nothing to type later. A name
  equal to what the status line shows is typed all the same: the status
  line can be stale. **What it cannot see**: a draft in the prompt box,
  which the command goes after and submits as a prompt, and an MCP form,
  which shows only through a late `Notification`. A send has both too. `Store.rename` replaces the whole map rather than editing it,
  the trick `rows` plays: the HTTP thread writes, the fold thread reads. It
  pushes nothing — the rows are built from the names every pass, so the next
  one differs and goes out on its own.
- **The send box and the question bar start where the transcript does, and
  the map runs down beside them.** Both stand under a split tab's right
  half, and both used to run the whole width and under the map beside it — a
  column you never type into. A `margin-left` fixed that and left the map
  and its grip stopping short above them, with an empty corner under the map
  that nothing could drag. Now `.main` is a grid whose columns are the split
  tab's own — `--side-w`, `--split-grip-w`, the rest. `.content` spans every row
  under the tabs; the two bars take the third column of the last two rows,
  over it; and `.content.split` hands those rows and columns to its children
  with `subgrid`, so the map and the grip span every row and the pane only
  the first. **By the grid, not by moving them into the pane**: the question
  bar holds picks that have not been submitted and the send box holds what
  you are typing, and a node that changes parents is a node that is rebuilt.
  Two things this costs, both of them bugs that happened on the way in:
  - **The bars carry `position: relative`.** `.content.split` is positioned,
    and a positioned box paints over every sibling that is not, so it sat on
    top of both bars and took every click on an answer and into the box.
  - **`.tofoot` is a grid item in the pane's cell, not `position: absolute`
    against the box.** The box now runs down behind the send box, and an
    absolute child with a grid area was measured from the whole box, not
    the area — the box is a subgrid, and Chromium did not honour it.
  `test_the_map_and_its_grip_run_down_beside_the_send_box` holds the layout
  and the button; the question and send-box tests in `test_page_act.py` are
  what catch the clicks.
- **A send to an agent at its prompt is seen to land, or comes back**
  (#489, `press_send`'s `watch`, `prompt_landed`, `SEND_WAIT`,
  `TYPED_KINDS`, `seen: false`). With `/config` open in the terminal the
  keys went into the dialog, and the message was gone: the box had been
  emptied and nothing was said. Claude Code writes a prompt as a `user`
  record a few milliseconds after the Enter, so the daemon waits for one
  at or after the moment it typed, and without it answers `seen: false`
  and the page puts the text back. **Only an agent at its prompt, and not
  a slash command**: a message to a busy agent is queued and reaches the
  transcript when the agent takes it, which may be minutes on, and a
  slash command may open a dialog of its own and write nothing. A session
  with no transcript is not watched: there is nothing to ask. `in_pane`'s
  tmux writes the prompt, as Claude Code does, or every page test that
  sends would wait and see its text come back.
  `test_a_send_claude_code_never_took_is_said_and_given_back`,
  `test_a_send_to_a_busy_agent_is_not_watched`.
  - **Up in an empty send box brings back what this browser sent**
    (`keepSent`, `recallSent`, `SENT_KEPT`, `wostuast-sent`), as a shell's
    history does; Down goes newer, and past the newest to empty. Only
    while the box is empty or holds what Up brought back: the reader's own
    words keep their arrows for the caret. A send that came back is not
    kept, because it is in the box already.
    `test_a_send_claude_code_did_not_take_comes_back_and_up_recalls_one`.
- **The send box says how much it holds, over the send button, once it is
  tall enough to leave room there** (`sizeSay`, `SAY_ROOM`, issue 332). A
  box scrolled to the end of a long log shows its last screenful and
  nothing of how long it is. "2.4k lines" and "112 KB", `roughly` and
  `sizeOf`, in the sans face: the reader said no to the fixed face and to
  "2,400", which took two rows.
  - **In a column with the button, `.sendside`, not laid over the bar.**
    Laid over it, a size wider than the button ran over the edge of the
    box. The column widens instead, and the box gives way a few pixels.
    `.say + .verb` no longer reaches the button, so `.sendside > .verb`
    keeps it 32 px and level with the box's last line.
  - **From `fitSay`**, which every change of the box comes through: a key,
    a paste, the send that empties it, the refusal that puts it back.
  `test_a_tall_send_box_says_how_much_it_holds`,
  `test_the_size_goes_when_the_send_box_empties`.
- **Ctrl+Enter presses the button of the box it is typed in**, in every box
  that keeps or sends something: the send box, a review comment, the reason
  for a No, and the comment on the whole review in the review's send bar. The comment box had Escape and
  nothing else, and the send box left Ctrl out on purpose, so the key the
  reader used everywhere did nothing in either. `submitOnCtrlEnter` clicks
  the button and does nothing more, so whatever the button checks is
  checked, and a disabled one ignores the click. Cmd+Enter is the same key.
  **And the button stands level with the box's first line**:
  `.say { line-height: 18px }` makes one line 32 px whoever sizes the box,
  and `.say + .verb` is 32 px. It was 26 beside 32, and the reason box, at
  `line-height: 1.5`, stood 1.5 px taller than its button.
  `test_ctrl_enter_saves_a_comment_and_sends_the_review`,
  `test_ctrl_enter_sends_and_says_no_and_the_buttons_stand_level`.
  - **Every one of these boxes shows all it holds, its placeholder too.**
    A `.say` box wraps (`white-space: pre-wrap`), and so does its
    placeholder. The reason for a No was one row high and never sized:
    at 1,100 px its placeholder wrapped, and "(optional)" stood cut in
    half on a second row that did not show; a long reason did the same.
    `fitSay` sizes it now, as it sizes the send box and the review's two
    boxes, and Chromium counts an empty box's placeholder in
    `scrollHeight`. `fitSay` asks `getClientRects()`, not the box's form,
    because this box stands in none. The box is as wide as No's group
    (`.permnogroup .permwhy`), on a row of its own; it was at least as
    wide as its placeholder (`--fits`) while it stood in a line of
    buttons, and that went with the line.
    `test_the_reason_box_shows_its_placeholder_and_what_is_typed_whole`.
  - **The Enter that ends an IME composition is the input method's**
    (`composing`). In Japanese or Chinese, Enter picks the word; the send
    box and the rename box took it as the reader's, and could send half a
    message into a terminal or keep half a name. Chromium says so in
    `isComposing`. Safari sends that Enter after the composition has ended,
    and says so only in `keyCode` 229, so both are read. The guard only
    stops a send, so it takes nothing from the send box's checks.
    `test_the_enter_that_ends_a_composition_sends_nothing`,
    `test_the_enter_that_ends_a_composition_keeps_no_name`.
- **A `/` at the start of the send box completes from files and
  transcripts, asked for each time the list opens** (#268). `Commands.of`
  reads the skills (`skills/<name>/SKILL.md`) and command files
  (`commands/<name>.md`) under `.claude` in the session's directory and
  each parent up to `worktree_root` (`project_dirs`, nearest first, both
  resolved, because git hands back the real path), then the same under
  `claude_dir()`, then adds what `<command-name>` says was run in any
  known transcript. Six things in it are the shape on purpose:
  - **Built-ins come from the transcripts, never a copied list.** `/clear`
    and `/compact` are in no file, and a list of them goes stale with each
    Claude Code release. `Commands.used` reads each transcript on from where
    it stopped (`Tail`), parses only lines holding `<command-name>`, and
    starts a file's count again when the file is rewritten.
  - **A mention is not a use.** `command_used` asks `read_user_text`, so a
    prompt that only talks about `<command-name>` counts nothing, and an
    `isMeta` record is Claude Code's, not the reader's. A `system`
    `local_command` record is the other shape a command is written in.
  - **Not pushed with the row.** A row goes out on every change; the list is
    kilobytes (the ssh rule above). The page fetches `commands` when the
    list opens and drops it when it shuts (`closeSlash`), so a skill written
    a minute ago is in the next list.
  - **What is not known from a real machine is left out**, not guessed: a
    command file in a subdirectory of `commands`, whose name nobody has
    seen formed (topics/payloads). `glob`, not `rglob`.
  - **A plugin's commands are read where Claude Code installed them**
    (#413, `plugin_dirs`, `enabled_plugins`): they were listed as built
    in, "no file says what it does", though their files were on the disk.
    Measured, not guessed: the layout and the names in topics/payloads. A
    plugin counts only when `enabledPlugins` has it on -- yours, then the
    project's `settings.json`, then its `settings.local.json`, the nearest
    last -- and one installed for a project only in that project. **Only a
    folder under `~/.claude/plugins` is read**, by `inside`: the list is
    Claude Code's file, but a path in it is one no reader of the page
    chose. They are `came: "plugin"`, "from your plugins" on the page.
    `test_a_plugins_commands_are_read_where_claude_code_installed_them`,
    `test_a_plugin_is_read_only_where_it_is_on`.
  - **The list's keys come first** (`slashKey`). Tab always takes the
    chosen row. **Enter takes only a row the reader chose** (`enterTakes`):
    an arrow pressed (`slash.moved`), or a word that starts the name and is
    not all of it. Enter that always took turned `/doctor` -- a built-in
    never run, so not listed -- into `/docs-to-review` by scattered letters,
    and the next Enter sent the wrong command; and a whole name took two
    Enters. Escape shuts the list and is remembered (`slash.dismissed`)
    until the word is gone **or sent**: `sendTyped` empties the box with no
    input event, and the next `/` opened nothing. A row takes on
    `mousedown` with `preventDefault`: a click blurs the box first, and the
    blur shuts the list.
  - **A `/` after white space completes too, and there only what has a
    file** (#368, `slashSpot`). Measured on 2.1.288 with
    `tests/claude_pane.py`: a `/deploy` in the middle of a prompt is not
    run, but Claude Code adds a note for the model, "the user's message
    contains /deploy, which is the name of a skill", to call the Skill tool
    if asked -- for a skill and for a command file alike. A built-in is no
    skill, so `drawSlash` offers there only what has a `file`. A `/` that does
    not start the box or follow white space opens nothing: `src/main.py`.
    `takeSlash` replaces the word wherever it stands and keeps both sides.
    `test_a_slash_in_the_middle_of_a_message_completes_too`,
    `test_a_slash_inside_a_word_opens_nothing`.
  - **An answer for a box the reader left opens nothing.** `followSlash`
    checks the focus after its fetch, as it checks the session: the list
    opened over the transcript with no box to type into.
  - **Commands is a view, not a tab** (#411, `toggleView`, key `4`):
    a tab belongs to the chosen session, and most commands belong to no
    session -- yours in `~/.claude` and the built-ins -- while a project's
    belong to every session standing in it. So `loadCommands` asks one
    session of each worktree (`projectSessions`, keyed on the row's
    `root`) for its list, and lists yours and the built-ins once, then each
    project's under its name (`projectName`: the repository, and the
    worktree too when two share one). No route was added: the session
    routes already answer it. **A project's command is that project's**:
    two projects may each have a `/deploy`, so a row is picked by
    `commandKey`, the session asked and the name. **"use" types into the
    chosen session when it can run the command, and otherwise into the
    session the view asked** (`useTarget`), which it then chooses. The
    view is drawn in the reading face, the names too (#414).
  - **The Commands view shows the same list, and reads one by its name**
    (#367, `drawCommands`, `verb_command`). The one asked for is
    found among `Commands.defined`, nearest first as the list has them,
    and it sends only the text: the rest the tab shows is the list's
    entry (`commandOf`). Its text comes without its frontmatter
    (`after_front`, which asks `front_end` as `front_matter` does: one
    split on newlines and the other on every line ending, and a file with
    CR endings had its frontmatter drawn as rules). **"use" fills the send box
    and types nothing** (`useCommand`): the reader chose it, in so many
    words, over a button that sends. **It and the `/` list put a command
    the same way, `putCommand`**: "use" had its own rule for the space
    after it, and joined two lines into one. It keeps a draft after the
    command and replaces a command at the start; on a
    session nothing can be typed into it says why (`whyNotTyped`) and
    stays. `tests/test_page_commands.py`.
  `test_the_project_and_your_own_commands_are_read`,
  `test_what_the_transcripts_say_was_run_is_counted`,
  `test_a_transcript_is_read_on_from_where_it_stopped`,
  `test_a_slash_offers_the_commands_and_tab_takes_one`,
  `test_enter_takes_a_command_and_escape_keeps_the_list_shut`,
  `test_the_list_is_asked_for_each_time_it_opens`,
  `test_enter_sends_what_was_typed_unless_a_row_was_chosen`,
  `test_an_answer_for_a_box_that_was_left_opens_nothing`. `tests/stage.py
  --commands --keys '#say=/'` draws it.
- **Enter jumps, except on a button a keyboard reached.** The keys handler
  jumped to the pane from wherever the focus was, so a keyboard could press
  nothing on the page. But a click leaves the focus on the button it pressed,
  and Enter there has always been the jump key. `:focus-visible` cannot tell
  the two apart: a key pressed on a clicked button turns it on before the
  handler runs. `focusedByKey` can: Tab sets it, a pointer press clears it.
  `test_enter_on_a_button_reached_by_keyboard_presses_it` holds both halves.
  **The same turn-on draws a ring**: a key pressed after a click lights
  `:focus-visible` on the clicked button, so clicking Session and pressing
  1 left the browser's dark ring round Session, the tab just left. A
  shortcut that acts ends by blurring a button the pointer pressed; one
  `focusedByKey` reached keeps its ring.
  `test_a_key_leaves_no_ring_on_a_tab_that_was_clicked`.
- **Few keys, and none that the reader never presses.** `j` `k`, `n`, `r`
  and `t` went: the reader used `1` `2` `3`, and each unused key was a line
  in `?` that hid the ones in use. `3` is the review already. A key that is
  added again needs a reader who asked for it.
  `test_the_keys_nobody_pressed_are_gone`.
  - **`b` was asked for** (#354, `goBack`, `state.before`): back to the
    session chosen before, and again to return. `choose` keeps the one it
    leaves, in `sessionStorage` -- per browser tab, as the chosen one is in
    the address, so a reload keeps both. A `/clear` since is followed
    (`cleared_into`). A session forgotten, or hidden by the filter, is not
    gone to, and `note` says why: landing on a row the reader cannot see
    reads as the key doing nothing.
    `test_b_goes_back_to_the_session_before_and_again_returns`,
    `test_b_says_why_it_cannot_go_back`.
  - **From a box, Esc and then the number: no Alt+number** (#470). In a
    box a number is a letter typed, and the reader asked for Alt+1, 2, 3.
    Chrome and Firefox on Linux take Alt+1-8 for their own tabs, and on a
    Mac Alt+number types a symbol, so the reader chose Esc. Every box
    already left on Esc (`#say` keeps its text; `#find` and `#pick` are
    cleared), so the fix was to say so: `?` and the guide.
    `test_esc_leaves_a_box_and_a_number_then_picks_a_tab`.
