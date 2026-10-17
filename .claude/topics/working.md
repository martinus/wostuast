# Ways of working, read when the task needs them

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. A picture or a
mockup of the page, `WOSTUAST_WAIT`, a run in the background and how to stop
it, a throwaway home, and edit scripts for the one large file. They stood in
`CLAUDE.md`, loaded at every start, for tasks most sessions never do.

**A report about how the page looks starts with a picture of the reader's
case, and ends with another one.** Write the case from their screenshot — a
few lines of `you:`, `claude:`, `think:`, `tool:` — run `tests/shot.py` with
`--measure`, and look at the PNG before reading any code. For anything
else -- the Files or the Review tab, the settings menu -- `tests/stage.py`
makes the repository, the settings and the clicks, and draws the part;
for the sidebar and the views over it, `tests/tour.py` draws every row
state and each view at once; a
session wrote that script from nothing each time, in a scratchpad that
stays behind on the machine, and one lost it when the session restarted.
**Draw a look change with text that runs to the edge, as well as a short
case.** #526 put a saved bookmark at a turn's top right, drawn over replies
of a few words; the cover picture of #521, real-length text, showed it
standing on the words of a reply's first line, and #529 fixed it after the
merge. `tests/tour.py`'s transcript is the long case, ready-made.
**A mockup is drawn the same way**: `--eval` builds the proposal inside the
real page, with its real CSS. **`--eval` is handed to `page.evaluate`, so it
is one expression**: statements go in `(() => { … })()`, and a list of them
with a `const` drew nothing and said nothing. A change to a session is undone
by the next push (`patchSession` then a push), so a picture of a state the
daemon does not hold keeps patching on an interval; and the bars over the
transcript -- the question, the send box -- are drawn by `drawHeader()`,
not `draw()`. `tour.py --hover SELECTOR` is for what only a hover shows: a
`mouseover` sent from `--eval` drew nothing, because the tour moves the
pointer itself. A standalone HTML file with the CSS copied by
hand drifts from the page, and needs the browser path that `browser.py`
already knows. **Every tool keeps to its own home, through `conftest.isolate(home)`**,
called by each function that writes -- `stage.serve`, `shot.serve`,
`tour.make_sessions`, `scale.measure` -- not only by its `main`: a script that called
`stage.serve` by itself wrote the command fixtures into the real
`~/.claude`, and the session's own skill list showed them. A new tool
calls it too; `test_the_tools_write_nothing_outside_their_own_home`
holds the four. It reads the checkout when it starts, so run
it again after an edit. A spacing report
went round three times, and three pull requests, because every fix was
proven by a test measuring the box around each block, which said 6 px, while
the reader looked at the text, which stood 39 px from what came next. The
picture shows that in one look and `--measure` prints both numbers. It is
done when the new picture looks right, not when a test is green — then pin
it with a test that measures what the picture showed. **The picture before a change is the new tool on the old code**:
`git worktree add --detach <dir> origin/main`, copy the new `tests/tour.py`
(or `stage.py`) into it, and run it there. The new state the change
draws -- children under a row, a finished session -- is in the new tool
only, so the old tool cannot draw "before" (#422, #427). **Send the reader the
picture, and wait for their yes, before the pull request.** `SendUserFile`
the PNG, beside the old one, **from `pictures/` in the checkout**, kept out
of git by `.git/info/exclude`: the app opens files in the working
directory, and pictures sent from the scratchpad after the session
restarted reached the reader as nothing ("I do not see any pictures").
Put before and after in one PNG, each labelled, so one look compares
them. The spacing fix was merged before the reader
had looked, and came back as "I'm running the latest pushed branch, and the
spacing is still not ok": a round of review, CI and merge for a question
one picture answers. **While you wait, the stop hook asks for a commit and a
push**: push the branch, which starts nothing, and open the pull request
after the yes.

**Work in one file.** While working, run the one test and the one file,
with `WOSTUAST_WAIT=5000`: a wait for something that never comes then fails
in five seconds rather than thirty, which is three of them a minute and a
half in one sitting. `WOSTUAST_WAIT` is for a desk, never CI: the 15 s and
30 s waits are what a loaded runner needs. **Not for a test that waits on the
Review tab's poll**: it comes every five seconds, so such a test fails at
5,000 ms and passes without it. Run those without the variable. **And
`tests/perturb.py` sets it to 5000 when it is not set**, so a break of
such a test is red whatever the break does, and the red proves nothing:
run it as `WOSTUAST_WAIT=30000 python3 tests/perturb.py …`, as the proof
of `test_an_untracked_file_picked_and_then_added_lets_go_of_the_pick` did.

**Edit nothing the tests read while they run in the background.** They read
the working tree, and each of the three runs starts later than the one
before it: an edit in between left run one on the old code and runs two and
three on the new, and their counts said nothing about either. Write the
rule and the pull request's text meanwhile, which no test reads; for a
change to code, stop the run (`TaskStop`), edit, and start it again.

**Run a long thing in the background, and work while it runs.** A loop of
`until grep …; sleep` holds the turn, does nothing else, and is killed at
the tool's time limit — eight commands ended that way in that session. `run_in_background` wakes
you when it ends. **A `&` inside the command is not that**: nothing wakes
you, the output lands only where you sent it, and stopping it meant
finding its shell's number by hand, after an edit had already made its
counts worthless. Meanwhile write the rule for this file and the pull
request's text; while CI runs, reproduce the next issue, reading only.

**Stop a process by its number, never by `pkill -f`.** The pattern is in the
command line of the shell that runs `pkill`, so it matched that shell and
killed it, twice in one session. Find the number in one call -- a loop over
`/proc/*/cmdline` that prints the ones whose command line starts with what
you ran -- and `kill` it in the next.

Throwaway home, never your own, and a new one each time:

```
T=$(mktemp -d) && export HOME=$T WOSTUAST_STATE=$T/state CLAUDE_CONFIG_DIR=$T/claude WOSTUAST_CONFIG=$T/config
```

**Commit in a shell that did not export it.** git reads its identity from
`$HOME`, so a `git commit` after the export fails with no name, and a
chained command after the commit does not run.

**Never `rm -rf $HOME` to empty it, and never chain anything before a
removal.** The safety check refuses an `rm` of a home, and a refused
command runs none of its parts: an edit chained in front of it did not
happen, and the next tests ran the old code and passed. A new `mktemp -d`
needs no removal.

`WOSTUAST_STATE` and `CLAUDE_CONFIG_DIR` are test seams, not user settings. Do
not document them as settings.

**Editing one very large file.** Anchor on a unique string and assert you hit
it exactly once; a sloppy replace in a file of this size fails silently. A small
Python script with `assert s.count(old) == 1` before every `replace` is the
reliable shape when making several edits at once. Three scars on that shape:

- **Write its old and new text as raw strings, `r'''…'''`, when they
  hold a backslash.** `PAGE` is a raw string, so `\\d` in the program is
  `\\d` in the JavaScript; a plain `'''` in the edit script turned it into
  `\d`, and the page read `NO-(d+)`.
  **And write that script with the Write tool, not as a heredoc inside a
  Bash command**: twice in one session a `\\` in the command reached the
  file as `\`, raw string or not -- a test's list held `"path\;"`, an
  invalid escape -- and only a warning said so.
  - **The Write tool writes `\uXXXX` as the character itself.** The
    program spells its middle dot `\u00b7`; an anchor copied from it
    into an edit script reached the file as `·`, matched nothing, and the
    script stopped at its `assert`. `grep -c u00b7 script.py` after writing
    it says whether it survived; a script that must hold one builds it with
    `chr(92) + "u00b7"`.
- **Chain the tests after the script with `&&`.** A failed `assert` stops
  the script before its later edits, and three runs under load then tested
  code that had not changed. A pipe in that chain needs `set -o pipefail`:
  the bullet under "Before the push" says why.
- **An offset taken before a replace is wrong after it.** An edit
  script for #548 found a function's start and end, then changed the
  imports at the top, then cut by the offsets it held: the cut landed
  short, and the file ended in `ield from`. Make every whole-file replace
  last, or find the offsets again after it.
- **A replace from one anchor to another deletes all that stands between
  them.** A slice from `dayValue` to the next function's comment took
  `setReminder` with it; the page still parsed, no name was defined twice,
  and only the reminder tests, failing in a way that pointed elsewhere,
  said so. After such an edit, compare the names defined before and after:
  `diff <(git show HEAD:wostuast | grep -o "^\(async \)\?function [a-zA-Z]*" | sort) <(grep -o "^\(async \)\?function [a-zA-Z]*" wostuast | sort)`
  -- every line it prints is a function gone or added.
- **Take a debug line out with an edit, never with `git checkout <file>`**:
  that takes every change not committed with it. Two `print`s were taken
  out of a test file that way, and the new test written beside them went
  too (#422); it was written a second time from memory. Commit first, or
  edit the lines out.
- **Grep for a name before you define it**: a second top-level `def` or
  `function` silently replaces the first. `test_no_name_is_defined_twice`
  holds it now; `load_settings` was written twice in one session. It runs
  with the tests that drive no browser, so run those first: a browser run
  spent minutes on a second `KEPT` (the scrub's, and then a new table's)
  that this test names in seconds.
