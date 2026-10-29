# Ways of working, read when the task needs them

A picture or mockup of the page, `WOSTUAST_WAIT`, background runs, a
throwaway home, and edit scripts for the one large file.

- **A report about how the page looks starts with a picture of the
  reader's case, and ends with another one.** A test of a block's box said
  6 px where the reader saw 39. Write the case from their screenshot
  (lines of `you:`, `claude:`, `think:`, `tool:`), run `tests/shot.py`
  with `--measure`, and look at the PNG before reading code. The Files
  or Review tab or the settings menu is `tests/stage.py`; the sidebar and
  the views, `tests/tour.py`. Never a script of your own: the scratchpad
  stays on the machine. **It is done when the new picture looks right,
  not when a test is green**; then pin it with a test that measures what
  the picture showed.
- **Draw a look change with text that runs to the edge, as well as a
  short case**: a bookmark drawn over short replies covered a long reply's
  first line (#526, #529). `tests/tour.py`'s transcript is the long case.
- **A mockup is drawn the same way**: `--eval` builds it inside the real
  page, with its real CSS; a standalone HTML file drifts from the page.
  - **`--eval` is handed to `page.evaluate`, so it is one expression**:
    put statements in `(() => { … })()`; a bare `const` drew nothing.
  - The next push undoes a `patchSession`, so a picture of a state the
    daemon does not hold patches on an interval.
  - **A view's card is asked for when the view opens**: `openFeed`, wait
    for its answer (`async`, `await` a timeout), then set
    `state.feedText` and `drawFeed($("content"))`. Set first, the answer
    replaced the made-up text (#662).
  - `drawHeader()` draws the bars over the transcript, not `draw()`.
  - `tour.py --hover SELECTOR` shows what only a hover shows: the tour
    moves the pointer, so a `mouseover` from `--eval` drew nothing.
- **Every tool keeps to its own home through `conftest.isolate(home)`**,
  called by each function that writes (`stage.serve`, `shot.serve`,
  `tour.make_sessions`, `scale.measure`), not only by `main`: a script
  calling `stage.serve` alone wrote into the real `~/.claude`. A new tool
  calls it too; `test_the_tools_write_nothing_outside_their_own_home`. A
  tool reads the checkout when it starts: run it again after an edit.
- **The picture before a change is the new tool on the old code**:
  `git worktree add --detach <dir> origin/main`, copy the new
  `tests/tour.py` (or `stage.py`) in, and run it there; only the new tool
  draws the new state (#422, #427).
- **Send the reader the picture, and wait for their yes, before the pull
  request**: a fix merged unseen came back still wrong. `SendUserFile` the
  PNG **from `pictures/` in the checkout** (in `.git/info/exclude`): one
  sent from the scratchpad after a restart arrived as nothing. **The main
  checkout's, not a worktree's**: the reader's app opens files under the
  main one only. Put before and after in one PNG, labelled:
  `tests/pair.py OUT before=OLD after=NEW --clip X,Y,W,H`. **While you wait, the stop hook asks for
  a commit and a push**: push the branch, which starts nothing, and open
  the pull request after the yes.
- **Work in one file, with `WOSTUAST_WAIT=5000`**, so a wait for what
  never comes fails in five seconds, not thirty. Never in CI: a loaded
  runner needs the 15 s and 30 s waits.
  - **Not for a test that waits on the Review tab's poll**, which comes
    every five seconds: run it without the variable.
  - **`tests/perturb.py` sets it to 5000 when unset**, so a break of such
    a test is red whatever it breaks: run
    `WOSTUAST_WAIT=30000 python3 tests/perturb.py …`, as for
    `test_an_untracked_file_picked_and_then_added_lets_go_of_the_pick`.
- **Edit nothing the tests read while they run in the background**, or
  the runs split across old and new code. Stop (`TaskStop`), edit, start
  again.
- **Run a long thing with `run_in_background`, and work while it runs.**
  A loop of `until grep …; sleep` holds the turn until the tool's time
  limit kills it. **A `&` inside the command is not that**: nothing wakes
  you, and you must find its process to stop it. Meanwhile write the rule
  and the pull request's text; while CI runs, reproduce the next issue,
  reading only.
- **Stop a process by its number, never by `pkill -f`**: the pattern is
  in the command line of the shell running `pkill`, which it killed. Find
  the number in one call (`/proc/*/cmdline`), `kill` it in the next.

Throwaway home, never your own, and a new one each time:

```
T=$(mktemp -d) && export HOME=$T WOSTUAST_STATE=$T/state CLAUDE_CONFIG_DIR=$T/claude WOSTUAST_CONFIG=$T/config
```

- **Commit in a shell that did not export it**: git reads its identity
  from `$HOME`, so the commit fails and nothing chained after it runs.
- **Never `rm -rf $HOME` to empty it, and never chain anything before a
  removal.** The safety check refuses it, and runs none of the command: a
  chained edit did not happen, and the tests passed on old code. A new
  `mktemp -d` needs no removal.
- **`WOSTUAST_STATE` and `CLAUDE_CONFIG_DIR` are test seams.** Do not
  document them as settings.

**Editing one very large file.** A sloppy replace in a file this size
fails silently. Use a small Python script with `assert s.count(old) == 1`
before every `replace`. Its scars:

- **Write its old and new text as raw strings, `r'''…'''`, when they hold
  a backslash**: `PAGE` is raw, and a plain `'''` turned `\\d` into `\d`
  (`NO-(d+)`). **Write the script with the Write tool, not a heredoc in
  Bash**, where `\\` reached the file as `\`.
  - **The Write tool writes `\uXXXX` as the character itself**: an anchor
    spelt `\u00b7` matched nothing. `grep -c u00b7 script.py` says
    whether it survived; build one with `chr(92) + "u00b7"`.
- **Chain the tests after the script with `&&`**, or a failed `assert`
  leaves them testing unchanged code. A pipe in the chain needs
  `set -o pipefail` (`CLAUDE.md`, "Before the push").
- **An offset taken before a replace is wrong after it**: #548's script
  cut by old offsets, and the file ended in `ield from`. Make a
  whole-file replace last, or find the offsets again.
- **A replace from one anchor to another deletes all between them**: one
  took `setReminder`, and the page still parsed. After such an edit,
  every line this prints is a function gone or added:
  `diff <(git show HEAD:wostuast | grep -o "^\(async \)\?function [a-zA-Z]*" | sort) <(grep -o "^\(async \)\?function [a-zA-Z]*" wostuast | sort)`
- **Cut a function past `LINES_MOST` with an edit script that asserts no
  comment line is lost or doubled, `#` and `//` both** (#578). A change
  that would pass the limit first moves the part it touches into a helper,
  with its comments and its tests green (`CLAUDE.md`, **Style**). Split by
  job, not by length (#548): `drawDiff` became `putDiffNotesAbove`,
  `putDiffNotesBelow`, `putDiffBlocks` and `putDiffPlace`. A part cut only
  to be under the limit is the same jobs in two places. A new function's
  own head comment is the only line that may be new.
- **Take a debug line out with an edit, never `git checkout <file>`**:
  that drops every change not committed, a new test too (#422).
- **Grep for a name before you define it**: a second top-level `def` or
  `function` silently replaces the first (`load_settings`).
  `test_no_name_is_defined_twice` runs with the tests that drive no
  browser; run those first, as they name a second `KEPT` in seconds.

## The tools in `tests/`

None is a test. Each is kept working by its own test file:
`tests/test_where.py`, `test_shot.py`, `test_stage.py`, `test_tour.py`,
`test_scale.py`, `test_claude_pane.py`, `test_page_coverage.py`,
`test_perturb.py`, `test_pair.py`.

- `tests/where.py`: with no name, the map of `wostuast`: each section's
  header, line and length. With names (`cmd_hook`, `Store.refresh`,
  `putFold`, `.row`), where each is defined, and the section header that
  names the rules to read. `tests/test_where.py` also holds that every
  header's rules file exists and no section passes `SECTION_MOST` lines.
- `tests/shot.py`: a transcript case as a PNG; `--measure` prints each
  gap from the text, not the box; `--eval JS` runs first.
- `tests/stage.py`: a repository with a branch of four commits, a change
  and a Markdown document, and any part of the page over it: `--tab`,
  `--commit N`, `--open PATH`, `--review`, `--settings JSON`, `--commands`
  (skills and used commands), `--merge` (the branch ends in a merge
  settled by hand), `--fresh` (a session with no prompt yet, so no
  transcript), then `--click`, `--type SELECTOR=TEXT` (and
  Enter), `--keys SELECTOR=TEXT` and `--eval JS` in order, and `--part`.
- `tests/tour.py`: six sessions, one in each state a row can be in, with
  saved turns and status lines; a PNG of each view: `transcript`, `later`,
  `unread`, `saved`, `search`, `permission`. `--view` picks; `--light`,
  `--width`, `--height`, `--eval JS` (or a file) and `--hover SELECTOR`
  apply before each picture.
- `tests/scale.py`: a synthetic history of `--sessions` and `--turns` in a
  throwaway home; prints one JSON line timing a start's fold, ticks, a
  push, a stream's opening, and with `--page` a redraw. Run it before and
  after a change to the fold, a row, the stream or the sidebar's draw
  (#430, #431).
- `tests/claude_pane.py`: a real Claude Code in a tmux pane, against a
  fake Messages API that keeps every request and can answer once with a
  tool call: `send`, `paste`, `ask`, `busy`, `turns`, `statuses`,
  `hooks`, `settings`, and `restart` (`--resume <id>` brings the session
  back). What Claude Code does is measured with it, not guessed
  (topics/payloads).
- `tests/page_coverage.py`: runs the browser tests (all, or those named)
  with `WOSTUAST_COVERAGE`, which `cover` in `tests/browser.py` reads,
  and prints the share of the page script's lines that ran and each
  named function that never did. `--lines` adds the lines, `--from DIR`
  reads a run again, and `--check` is the ratchet CI's `browser` job runs
  (topics/testing, "It is a ratchet in CI": `UNRUN_ALREADY`,
  `UNRUN_LINES_ALREADY`). **`--check --names A,B` over the changed test
  files says whether CI's check passes for the functions a pull request
  adds**: a line counts as run when any byte of it ran.
- `tests/pair.py`: pictures side by side, each under its label, in one
  PNG; `--clip` cuts each to one part. The before and after a look change
  waits on.
- `tests/perturb.py`: applies each break in a JSON list, runs only the
  tests it names, puts the file back, and prints red or GREEN a line.
