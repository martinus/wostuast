# Ways of working, read when the task needs them

A picture or mockup of the page, `WOSTUAST_WAIT`, background runs and
stopping them, a throwaway home, and edit scripts for the one large file.

- **A report about how the page looks starts with a picture of the reader's
  case, and ends with another one.** A test of each block's box said 6 px
  while the reader saw the text 39 px from the next; the picture shows that
  at a glance, and `--measure` prints both numbers. Write the case from their screenshot (a
  few lines of `you:`, `claude:`, `think:`, `tool:`), run `tests/shot.py`
  with `--measure`, and look at the PNG before reading code. For the
  Files or Review tab or the settings menu, `tests/stage.py` makes the
  repository, the settings and the clicks, and draws the part; for the
  sidebar and the views, `tests/tour.py` draws every row state and each
  view. Use these, not a script of your own: a scratchpad stays behind on
  the machine, and one was lost on a restart. **It is done when the new
  picture looks right, not when a test is green**; then pin it with a test
  that measures what the picture showed.
- **Draw a look change with text that runs to the edge, as well as a short
  case.** A saved bookmark at a turn's top right (#526), drawn over short
  replies, stood on a reply's first line in real-length text (#521's
  cover); #529 fixed it after the merge. `tests/tour.py`'s transcript is
  the long case.
- **A mockup is drawn the same way**: `--eval` builds the proposal inside
  the real page, with its real CSS. A standalone HTML file with hand-copied
  CSS drifts from the page, and needs the browser path `browser.py` already
  knows.
  - **`--eval` is handed to `page.evaluate`, so it is one expression**:
    statements go in `(() => { … })()`; a list of them with a `const` drew
    nothing and said nothing.
  - A change to a session is undone by the next push (`patchSession` then a
    push), so a picture of a state the daemon does not hold keeps patching
    on an interval.
  - The bars over the transcript (the question, the send box) are drawn by
    `drawHeader()`, not `draw()`.
  - `tour.py --hover SELECTOR` is for what only a hover shows: a `mouseover`
    from `--eval` drew nothing, because the tour moves the pointer itself.
- **Every tool keeps to its own home, through `conftest.isolate(home)`**,
  called by each function that writes (`stage.serve`, `shot.serve`,
  `tour.make_sessions`, `scale.measure`), not only by its `main`: a script
  calling `stage.serve` alone wrote the command fixtures into the real
  `~/.claude`. A new tool
  calls it too; `test_the_tools_write_nothing_outside_their_own_home` holds
  the four. A tool reads the checkout when it starts: run it again after an
  edit.
- **The picture before a change is the new tool on the old code**:
  `git worktree add --detach <dir> origin/main`, copy the new
  `tests/tour.py` (or `stage.py`) in, and run it there. The new state the
  change draws (children under a row, a finished session) is in the new
  tool only, so the old tool cannot draw "before" (#422, #427).
- **Send the reader the picture, and wait for their yes, before the pull
  request.** A fix merged before the reader looked came back still wrong: a
  round of review, CI and merge for a question one picture answers.
  `SendUserFile` the PNG **from `pictures/` in the checkout**, kept out of
  git by `.git/info/exclude`: the app opens files in the working directory,
  and pictures sent from the scratchpad after a restart arrived as nothing.
  Put before and after in one PNG, each labelled. **While you wait, the stop
  hook asks for a commit and a push**: push the branch, which starts
  nothing, and open the pull request after the yes.
- **Work in one file, with `WOSTUAST_WAIT=5000`.** Run the one test and the
  one file: a wait for something that never comes fails in five seconds,
  not thirty. `WOSTUAST_WAIT` is for a desk, never CI: a loaded runner needs
  the 15 s and 30 s waits.
  - **Not for a test that waits on the Review tab's poll**: it comes every
    five seconds, so such a test fails at 5,000 ms and passes without it.
    Run those without the variable.
  - **`tests/perturb.py` sets it to 5000 when unset**, so a break of such a
    test is red whatever the break does, and proves nothing: run
    `WOSTUAST_WAIT=30000 python3 tests/perturb.py …`, as for
    `test_an_untracked_file_picked_and_then_added_lets_go_of_the_pick`.
- **Edit nothing the tests read while they run in the background.** They
  read the working tree and each run starts later than the last, so an edit
  between them splits the runs across old and new code, and the counts say
  nothing about either. Meanwhile write the rule and the pull request's
  text, which no test reads; to change code, stop the run (`TaskStop`),
  edit, and start it again.
- **Run a long thing in the background, and work while it runs.** A loop of
  `until grep …; sleep` holds the turn, does nothing else, and is killed at
  the tool's time limit; `run_in_background` wakes you when it ends. **A
  `&` inside the command is not that**: nothing wakes you, the output lands
  only where you sent it, and stopping it means finding its shell's number
  by hand. Meanwhile write the rule and the pull request's text; while CI
  runs, reproduce the next issue, reading only.
- **Stop a process by its number, never by `pkill -f`.** The pattern is in
  the command line of the shell running `pkill`, so it killed that shell.
  Find the number in one call (a loop over `/proc/*/cmdline` printing those
  whose command line starts with what you ran) and `kill` it in the next.

Throwaway home, never your own, and a new one each time:

```
T=$(mktemp -d) && export HOME=$T WOSTUAST_STATE=$T/state CLAUDE_CONFIG_DIR=$T/claude WOSTUAST_CONFIG=$T/config
```

- **Commit in a shell that did not export it.** git reads its identity from
  `$HOME`: a `git commit` after the export fails with no name, and a command
  chained after it does not run.
- **Never `rm -rf $HOME` to empty it, and never chain anything before a
  removal.** The safety check refuses an `rm` of a home, and a refused
  command runs none of its parts: an edit chained in front did not happen,
  and the tests then ran the old code and passed. A new `mktemp -d` needs no
  removal.
- **`WOSTUAST_STATE` and `CLAUDE_CONFIG_DIR` are test seams, not user
  settings.** Do not document them as settings.

**Editing one very large file.** Anchor on a unique string and assert you
hit it exactly once: a sloppy replace in a file this size fails silently.
For several edits, a small Python script with `assert s.count(old) == 1`
before every `replace` is the reliable shape. Its scars:

- **Write its old and new text as raw strings, `r'''…'''`, when they hold a
  backslash.** `PAGE` is a raw string, so `\\d` in the program is `\\d` in
  the JavaScript; a plain `'''` turned it into `\d`, and the page read
  `NO-(d+)`. **And write the script with the Write tool, not as a heredoc in
  a Bash command**: a `\\` in the command reached the file as `\`, raw
  string or not (a test's list held `"path\;"`, an invalid escape), and only
  a warning said so.
  - **The Write tool writes `\uXXXX` as the character itself.** An anchor
    copied from the program's middle dot, spelt `\u00b7`, reached the script
    as `·`, matched nothing, and stopped it at its `assert`.
    `grep -c u00b7 script.py` after writing says whether it survived; a
    script that must hold one builds it with `chr(92) + "u00b7"`.
- **Chain the tests after the script with `&&`.** A failed `assert` stops
  the script before its later edits, and the runs then tested unchanged
  code. A pipe in that chain needs `set -o pipefail` (`CLAUDE.md`, "Before
  the push", says why).
- **An offset taken before a replace is wrong after it.** An edit script
  for #548 took a function's start and end, changed the imports at the top,
  then cut by the old offsets: the cut landed short, and the file ended in
  `ield from`. Make every whole-file replace last, or find the offsets again
  after it.
- **A replace from one anchor to another deletes all between them.** A
  slice from `dayValue` to the next function's comment took `setReminder`
  with it, and only the reminder tests, failing as if elsewhere, said so:
  the page still parsed and no name was defined twice. After
  such an edit, compare the names defined before and after; every line this
  prints is a function gone or added:
  `diff <(git show HEAD:wostuast | grep -o "^\(async \)\?function [a-zA-Z]*" | sort) <(grep -o "^\(async \)\?function [a-zA-Z]*" wostuast | sort)`
- **Take a debug line out with an edit, never with `git checkout <file>`**:
  that drops every change not committed with it, and took a new test
  written beside two `print`s (#422). Commit first, or edit the lines out.
- **Grep for a name before you define it**: a second top-level `def` or
  `function` silently replaces the first (`load_settings` was written
  twice). `test_no_name_is_defined_twice` holds it and runs with the tests
  that drive no browser, so run those first: they name a second `KEPT` in
  seconds, where a browser run spent minutes.

## The tools in `tests/`

None is a test. They stood in `CLAUDE.md`'s Layout table, loaded at every start.

- `tests/shot.py`: Not a test. Draws a transcript case on the page, saves a PNG, and with `--measure` prints each gap from the text, not the box. `--eval JS` runs in the page first: a click, a scroll. `tests/test_shot.py` keeps it working.
- `tests/stage.py`: Not a test. Makes a repository with a branch of four commits, a change and a Markdown document, and draws any part of the page over it to a PNG: `--tab`, `--commit N`, `--open PATH`, `--review`, `--settings JSON`, `--commands` (skills and used commands for the send box), then `--click`, `--type SELECTOR=TEXT` (and Enter), `--keys SELECTOR=TEXT` (no Enter) and `--eval JS` in order, and `--part`. `tests/test_stage.py` keeps it working.
- `tests/tour.py`: Not a test. Six sessions, one in each state a row can be in -- unread with a plan, working with subagents under it, needing you, a reminder, over -- saved turns of each kind, and a status line each; then a PNG of each view: `transcript`, `later` (the remind menu), `unread`, `saved`, `search`, `permission`. `--view` picks, `--light`, `--width`, `--height`, `--eval JS` (or a file of it) and `--hover SELECTOR` before each picture, which is how a mockup of the sidebar or the views is drawn. `tests/test_tour.py` keeps it working.
- `tests/scale.py`: Not a test. Writes a synthetic history of `--sessions` and `--turns` into a throwaway home and prints one line of JSON: the first fold of a start, a quiet tick, a tick after one event, a push and a stream's opening, and with `--page` one push's redraw in Chromium. Run it before and after a change to the fold, a row, the stream or the sidebar's draw (#430, #431). `tests/test_scale.py` keeps it working.
- `tests/claude_pane.py`: Not a test. A real Claude Code in a tmux pane of its own, against a fake Messages API that keeps every request and can answer once with a tool call: `send`, `paste`, `ask`, `busy` (a turn still running), `turns`, `statuses`, `hooks`, `settings`. How a question about what Claude Code does is measured, not guessed (topics/payloads). `tests/test_claude_pane.py` keeps the fake API working.
- `tests/page_coverage.py`: Not a test. Runs the browser tests -- all, or the ones named -- with `WOSTUAST_COVERAGE` set, so that `cover` in `tests/browser.py` has Chromium count what each page ran of the page script, and prints the share of its lines that ran and each named function that never did, at its line in `wostuast`. `--lines` adds the lines, `--from DIR` reads a run again, and `--check` fails on a named function that never ran and is not in `UNRUN_ALREADY`, a ratchet that started empty (#579), and on one whose lines that never ran are more than `UNRUN_LINES_ALREADY` allows it, naming them (#600); CI's `browser` job runs it over the four shards. A function it names is dead code or a test nobody wrote (topics/testing). `tests/test_page_coverage.py` keeps it working.
- `tests/perturb.py`: Not a test. Applies each break in a JSON list, runs only the tests the break names, puts the file back, and prints red or GREEN a line. `tests/test_perturb.py` keeps it working.
