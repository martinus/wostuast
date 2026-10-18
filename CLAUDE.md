# CLAUDE.md

Only agents read this file and `.claude/topics/`. This file is the map, the
reuse index and the way of working; the rules are in `.claude/topics/`, one
file a subject, read only when you work on that subject.

**Read the rules file before you edit its part.** `python3 tests/where.py
NAME` says where a name is defined and which rules file to read (**Finding
code**). Read the whole file, not only the bullet grep found: the bullets
beside it are the same part's other rules. **Never `.claude/rules/`, and
never an `@` import**: Claude Code loads both at launch, and every rule
would cost context in every session.

**Nothing durable goes in machine-local memory.** The owner works from more
than one computer. A lesson goes in this file or `.claude/topics/`,
committed; a tool worth keeping goes in `tests/`. The scratchpad is for
this session's throwaway files.

**How a rule is written.** One bullet a rule, in this order:

1. the assertion, in bold: what to do, or never to do;
2. why, in one or two sentences: the failure the obvious alternative
   caused, or the reader's decision and what it rules out;
3. the symbols to grep, the test that holds it, and the issue (`#N`).

Leave out the story: who found it, when, after how many runs, what was
tried first; `git log --grep '#N'` keeps it. Keep a number only when it
sets a limit or proves the why. **A new scar goes into the bullet it
belongs to**: grep for the symbol first; the same kind of bug again adds
its test and a clause to that bullet. A new bullet is for a new kind of
bug. **Keep the why**: a rule without it is broken by the first agent that
thinks it knows better. **State no number a person must maintain; give the
command that answers it**: a stale fact is believed. A rule goes in the
file of its subject; a new subject is a new file, a row in **Rules**, and a
bracket on the headers of its code.

**This file and `.claude/topics/` are the only design document.** `PLAN.md`
was deleted when its milestones were done; `git show d440d2f:PLAN.md` is
history, never authority. Where these files and the tests disagree, the
tests are right, and the rule is fixed in the same commit.

## Where to look

For code, use **Finding code** below: the section header names the rules.
For anything else:

| About to | Read |
| --- | --- |
| add a feature, or take a request that bends what the program is | **Goals and non-goals** — a feature that needs a non-goal is left out |
| decide where new code goes: a route, a view, a field the page reads, a second reader of a fact | **Principles**, and the test that holds each one |
| write a helper, a colour or a CSS selector | **Before you write anything new** |
| use a hook or status-line field | topics/payloads, and `tests/fixtures/README.md` |
| write a test, or fix one red only under load | topics/testing — a test is not a test until you made it fail |
| run the tests before a push | **How to work here**, "Before the push" |
| draw the page, or a mockup the reader asked to see | topics/working: `tests/shot.py`, `tests/stage.py`, `tests/tour.py` |
| write an edit script for `wostuast`, set `WOSTUAST_WAIT`, run in the background, use a throwaway home | topics/working |
| change something the reader asked for | **How to work here** — a pull request, merged on green without asking |
| push to `main`, change the CI matrix or the ruleset | topics/landing |
| write a commit message, a pull request or a comment | **How to work here**, last bullet — no attribution lines |
| work the issue list, or reflect at a session's end | `.claude/skills/issues/SKILL.md`, or "do the issues" |
| choose how something is recorded, served or searched | topics/decisions |

## The program in five lines

Claude Code hooks append one JSON line per event to `~/.local/state/wostuast/events.jsonl`.
A bare `wostuast` (`cmd_serve`) checks the setup, writes what is behind
(`bring_up_to_date`), then tails that log into a `Store` and serves one page
over HTTP + SSE. The page shows a session list and three tabs: Transcript,
Files, and Review, which is the diff with the review written on it
(`data-tab="diff"`). Four views stand over the tabs, for every session at
once: Unread, Saved, Search, and Commands (#411). Four things go back to the
terminal, all through tmux: jump, send, the keys that answer a question, and
a No to a permission dialog, which is an Escape and then a send. A rename is
a send of `/rename` (#351). A Yes to a permission dialog is no key at all:
the dialog's own hook waits for it and answers allow for that dialog alone
(`approve`). Nothing else writes to a terminal. Nothing owns the agent
process — interrupt is a keystroke, not a signal.

## Goals and non-goals

Every feature is judged against these. When a request fights one, ask one
level up whether the goal bends, before building anything. A goal that bends
is rewritten here in the same pull request.

**Goals.** The numbers are cited elsewhere; keep them.

1. Answer "who needs me?" in one glance, from another window or another room.
2. Render what an agent writes as real Markdown: the transcript, plan files,
   specs.
3. Show a worktree's changes without opening an editor.
4. Stay small: one Python file, the standard library, no daemon needed to
   *record* events, no config file needed to run, a one-line install and a
   one-line uninstall. Our `settings.json` is the one optional file: the
   settings menu writes it, nobody has to (**Shape** says why). The hook
   file `install` writes (`hook_path`) is no second source: `hook_source`
   copies it out of the one file, `uninstall` removes it, and it costs
   33 ms an event against 131 for the whole program (#271).
5. Look good enough that a screenshot would sell it. **One ships** (#521):
   `docs/cover.png`, at the top of the README, drawn by `tests/tour.py` from
   made-up sessions, never real ones -- a picture of real agents is
   somebody's work. Draw it again when the page changes how it looks; the
   command is under the picture.

**Non-goals. If a feature needs one of these, leave the feature out.**

- **Owning the agent process.** Nothing spawns, wraps or kills it; tmux
  owns the PTY. Typing into a pane is not owning it: jump, send, the answer
  keys and a No's Escape are allowed, a signal is not.
- **A terminal emulator** (no xterm.js). A Peek tab that showed a still
  capture of the pane was removed, with `capture-pane`: the real pane is one
  keystroke away.
- **A Yes the reader did not give, or one that keys carry.** The page says
  Yes only as the reader's click, and only through that dialog's own hook
  (`approve`, `wait_for_yes`): keys land on whichever dialog is up, and the
  hook's allow on its own dialog only (topics/safety, first bullet). **"Yes,
  and don't ask again" is Claude Code's own suggestion, never a rule of
  ours** (`always_offered`, `allow_for`). No mode that turns every prompt
  off, no plan, no question. An `AskUserQuestion` is the agent's own
  question: the page types nothing until the reader submits.
- **Agent-to-agent messaging, teams, orchestration, cache telemetry.**
  Showing the spend the status line sends is in; accounting is out. **So is
  a spend limit**: one shipped, typed into a terminal with nobody watching,
  and went with the Session tab that set it.
- **Knowing a worktree layout.** A session is an agent standing in a
  directory, nothing more. No dependency on `gra`.
- **Electron, Tauri, React, or any build step**, a Python dependency outside
  the standard library, or a JavaScript library vendored into the file.
- **A review that goes anywhere but the agent.** No GitHub API, no pull
  request, no posting. It is pasted into the pane of the agent in that
  worktree, and the reader reads every byte of it first.

## Principles

Five, each held by a test. A goal says what the program is for; a principle
says where its code goes. They came from a review of the whole file (#535):
its bugs were each one fact with two homes. A change that cannot keep one
says so in its pull request, and names the principle.

1. **Data flows one way**: events, then the fold, then rows, then the wire,
   then the page. The fold does no I/O: file, git and `/proc` reads happen
   at the edges, in the named steps of `Store.refresh` (`follow`, `settle`,
   `reload_git`, `render`), and a write the fold needs waits until it is
   done (`save_names`). A change of state is `become`.
   `test_the_fold_does_no_io`,
   `test_the_guard_folds_every_handler_and_both_links`.
2. **Each shape the page receives is defined in one place**: the wire
   section (`row`, `blocks_json`, `session_json`, `wire_fields`, the
   `EVENTS`). Its head comment names the five dataclasses that go out whole;
   anything else is written key by key.
   `test_a_block_sends_only_the_fields_it_names`,
   `test_the_page_reads_only_session_fields_the_row_sends`,
   `test_the_page_listens_for_every_event_the_stream_sends`,
   `test_the_row_and_ls_json_say_the_same_of_a_session`,
   `test_only_the_wire_section_turns_a_dataclass_into_json`.
3. **A draw only reads state.** Only code that loads data or handles a click
   changes `state`; what a change to the sessions does besides drawing is
   `onSessions`. `DRAW_GUARD` in `tests/browser.py`, an init script of every
   context, wraps `paint` and every `draw…` but `draw`, and fails on a
   fetch, alert, storage write or change to `state` (deep, and from a timer
   it set) not in `DRAW_EFFECTS_ALREADY` (#573, #577). Every browser test
   that opens a page with `opened` checks it. Every field of `state` is
   declared in its literal: `test_every_field_of_the_pages_state_is_declared`.
   **`draw()` is `paint`, then `land`** (#573): a mark of where to go -- a
   link to a block, a file asked for, the "new" line -- is used up once
   landed on, by each tab's own land in `TABS` (`landTranscript`,
   `landFiles`, `landDiff`). A build leaves what its land needs on the pane
   (`toLand`); the Review tab lands once a build, not on every push.
4. **Every extension point is a table**: hook handlers (`_HANDLERS`),
   session verbs (`GET_VERBS`, `POST_VERBS`), tabs (`TABS`), views
   (`VIEWS`), routes (`ROUTES`). A test walks the table, so a new entry is
   tested without anyone writing its test:
   `test_every_view_opens_draws_and_gives_the_session_back`,
   `test_every_route_refuses_what_it_must`.
5. **One reader for each fact.** Where two parts read the same fact, they
   call one function: `prompt_said` for a prompt, `git_status` for
   `git status`, `apply_git_facts` for a reading of git, `getJson` for an
   answer of the daemon. `test_search_reads_a_prompt_as_the_fold_does`,
   `test_only_get_json_calls_fetch`,
   `test_the_row_counts_the_changed_files_the_files_tab_marks`,
   `test_only_one_function_runs_git_status`.

**How a test holds a principle, strongest first**: a test that walks a
table; a differential test that gives two readers one hard case (write it
first and see it fail); a guard at run time, which checks only the paths
the tests run, so it comes with a test that each path is run; a static
check of the source's form, which moving code satisfies.

**A ratchet is a list of known breaks that may only get shorter**, like
`LONGER_ALREADY`. It stops the code sliding back and cleans nothing. So
**a guard lands in the pull request of the refactor that empties most of
its list**, never alone before it; **each entry says why it is there**, in a
comment; and **a pull request that adds an entry says why in its
description** -- adding one is the cheapest way to turn a red test green.

## Layout

| Path | What it holds |
| --- | --- |
| `wostuast` | The whole program: Python, then `PAGE = r"""` and the HTML/CSS/JS. `wc -l wostuast` for its size. |
| `tests/conftest.py` | Every fixture, including the page ones (`page_at`, `repo_page`, `big_page`, `in_pane`, `no_pane`, `pair_at`, `past_at`) and `event()`. |
| `tests/browser.py` | The shared Chromium, `opened`, `own_context`, `show_tab` and the other page helpers. No fixtures. `WAIT` is `WOSTUAST_WAIT`. |
| `tests/where.py`, `shot.py`, `stage.py`, `tour.py`, `scale.py`, `claude_pane.py`, `page_coverage.py`, `perturb.py` | Tools, not tests; each has a `tests/test_<name>.py`. topics/working, "The tools in `tests/`", says what each does. |
| `tests/test_page_*.py` | Browser tests, one file a subject. |
| `tests/test_*.py` | Everything that needs no browser, named after what it tests. |
| `tests/fixtures/README.md` | The hook and status line payload fields. |
| `README.md` | What a user reads first. Short on purpose (#521): a detail goes in the guide. |
| `docs/GUIDE.md` | Everything a user can look up. Keep it in step with the commands. |
| `ARCHITECTURE.md` | How the program works, for a person. No authority: where it and the rules or tests disagree, they are right and it is fixed in the same pull request. A change to a route, a state, a verb, a file on disk or a hook event updates it. |
| `.claude/topics/*.md` | The rules, one file a subject (**Rules**). |
| `.claude/skills/issues/SKILL.md` | How to work the issue list, invoked as `/issues` or "do the issues". |
| `.github/workflows/tests.yml` | The only CI: pytest over 3.10–3.13, four sharded browser jobs, and `browser`, the aggregator the branch rule requires. It fails on page code no shard ran (#579, #600). The shards split on a hash of the test id, so no job names a test file. |

## Finding code

`wostuast` is cut into sections by header lines: `# --- ` in the Python,
`/* --- ` in the page's CSS, `// --- ` in its script. A header says what
its section holds and ends with the rules to read, in brackets:

```
# --- the hook: cmd_hook runs on every event; it never prints and never blocks [topics/safety]
```

```
python3 tests/where.py                  # the map: each section, its line, its length
python3 tests/where.py cmd_hook Store.refresh putFold .row   # where each is defined, and what to read
```

Run the map before reading code: one call gives every part and its rules.
**New code goes into the section of its job, and a new part gets a header
of its own, with its brackets.** A section past `SECTION_MOST` lines is
split by job, with a header each. `tests/test_where.py` holds that every
bracket names a rules file that exists and that no section grows past the
limit; `test_every_rules_file_is_routed_to_and_every_route_is_a_file`
holds that every rules file is named by a header or by **Where to look**.

## Before you write anything new

Each entry here was written a second time once already.

**Page helpers**, in the page script's "page helpers" section unless named:

| Want | Call |
| --- | --- |
| "has this changed since I drew it?" | `fresh(box, which, key)` — never a hand-rolled `dataset` compare |
| change a session on the page | `patchSession(id, fields)` — never a write in place: sessions are frozen and compared by object |
| make an element | `put(parent, tag, cls, text)` — a button it makes is `type="button"` |
| scattered-letter match | `fuzzy(text, query)` → `{score, at}` or null |
| the items whose path matches the find box | `hits(items, pathOf)` keeps the order; `pick(names)` sorts best first |
| walk a diff's lines with their numbers | `walkHunks(one, onHunk, onLine)` |
| the two-column tab frame | `split(box, tab, bodyClass)` → `[list, pane, note, foot]` |
| the rounds of a conversation | `rounds()`, `glimpse(text)` |
| a review comment's identity | `anchorOf(path, line)`, `lineAnchor`, `commentAt`; a drawn diff line, `diffLineAnchor` |
| "3 min ago" | `ago(when)` — `40s`, `4min`, `2h 15min`, `2d 6h` |
| one session's route | `apiUrl(id, what, query)` |
| the reader's ticket links in some text | `linkTickets(root)` — after any scrub |
| "15:48", and "21 Sep" when not today | `clock(when)`, `dayOf(when)` |
| text onto the clipboard | `copyToClipboard(text)` |
| a button that did its job says so | `flashOutcome(button, icon, title, done, saying, words)` |
| which sessions are listed | `shownSessions()` (filter only) vs `listedSessions()` (on screen) |
| a file as rows, or a slice of one | `linesOf(text)`, then `asLines(path, lines, from)` |
| a binary file the browser can show | `putMedia(parent, path, found)` |
| a folder or a page icon | `putIcon(parent, "dir" \| "dirOpen" \| "file")` — SVG, so not `put` |
| a choice of a few, one in force | `putChoice(parent, name, options, pick)`, `paintChoice(group, value)` |
| Markdown or text, over what is read | `putReadAs(parent, asText, pick, textTitle)` |
| one button lit while what it says is on | `paintToggle(button, on)` |
| the places a reader can go | `state.files.places` |
| bytes, or a date a person reads | `sizeOf(bytes)`, `whenOf(seconds)` |
| a count read at a glance, "2.4k"; a text's lines without splitting | `roughly(n)`, `lineCount(text)` |
| "1 file", "3 replies" | `counted(n, one, many)` — in Python too |
| this browser's storage, which may refuse | `stored(key)` → "" when nothing; `store(key, value)` |
| a diff's files in the order its tree reads | `treeOrder(found, pathOf)` |
| which words of a changed line changed | `wordDiff(was, now)`, then `markWords(cell, runs)` |
| cards in as many columns as fit | `putBoard(parent, cls)`, `putCard`, then `layoutCards(board)` |

Three page functions match, and are easy to confuse: `matches` (a
transcript block), `matching` (the file tree), `hits` (any list by path). A
fourth word for the idea is how one of them got shadowed, and fifty browser
tests failed.

**Python helpers**: `path_label`, `clip`, `run` (a subprocess with a
timeout), `private_dir`, `safe_transcript`, `worktree_root`, `is_listed`,
`inside`, `CONTROL_CHARS`, `ESCAPE_CODES`, `GONE_STATES`, `STATE_WORDS`.

**Test helpers.** `run_installed(["hook"], stdin)` runs the hook or status
file this checkout makes, as Claude Code does (`as_claude`; `keys="pipe"`
for a pipe). **Never hand-write a hook event**: `conftest.event(name,
sid=..., **extra)` builds one as the log holds it, `conftest.bare_event` one
with only the fields named, as Claude Code hands it to the hook;
`test_no_test_writes_a_hook_event_by_hand` fails on one `EVENTS_BY_HAND`
does not hold (#599). **Never hand-write a transcript record**:
`conftest.record(kind, text, ...)` and `conftest.records(...)` -- one ended
in a backslash and an `n`, and the reader waited for ever. **To call the
program from a scratch script, `sys.path.insert(0, "tests")` and `from
conftest import wostuast`**: a loader of your own fails at the first
`@dataclass`. A runner that records keeps `conftest.said(args, rest)`, with
the text `tmux_send` hands `load-buffer`; `conftest.typed(seen)` and
`conftest.into_pane(seen)` read it. In `browser.py`: `opened`
(`with opened(where) as page:`, `tab="diff"`), `own_context`, `load`,
`show_tab`, `comment_on_first_line`, `two_rows`, `rgb`/`contrast`,
`numbers`, `open_code`, `stays` (the one fixed wait: proving nothing
comes), `frames`, `pixels` and `spy_on_note`.

**CSS**: `.verb` (a button; `.verb.quiet` a size down, for one that only
changes what is on screen), `.choice` (`putChoice`), `.toggle`
(`paintToggle`), `.link`, `.acts`, `.find`/`.findslot`, `.empty`,
`.nohits`, `.note`, `.comment`.

- **Every colour is a variable; a `:root` block is the only place a colour
  is a number**: `test_every_colour_outside_the_palette_is_named`. It reads
  an issue number in a CSS comment as a colour too, so CSS comments say
  `issue 333`, never `(#333)`. Derive a tint with `color-mix`, never a
  copied rgb triple.
- **The fixed face is for machine text only** (#448): code, a diff, a file,
  a command, the send and find boxes, a sha, a key. A time, a count, a
  name, a button, a tab's title, a note is `--sans`, with `tabular-nums`
  where digits must not dance; every list on the left is `--narrow`.
  `test_the_fixed_face_is_for_machine_text_only`.
- **A control that shows on hover is `display: none` until then, or out of
  the flow -- never `opacity: 0` in it**: it kept its room, cut long names
  short and moved "claude" out of line (#373, #377).
- **Grep for a selector before adding a CSS rule.** A class in use takes
  the new rule's look too: `.plus` was already the green "+3" beside a
  changed file, and every count became an invisible box; `.tab` was the
  tab row's button, and its padding doubled every first tab in code.

## How to work here

```
python3 tests/where.py                          # the map of the program, and the rules of each part
python3 tests/shot.py case.txt out.png --measure  # a report about the transcript: look first
python3 tests/stage.py out.png --commit 2 --review  # the Review or Files tab (--tab files --open PATH)
python3 tests/tour.py out/ --view later --eval mock.js  # the sidebar and the views
python3 tests/scale.py --sessions 500 --page    # how a start, a tick, a push and a redraw scale
WOSTUAST_WAIT=5000 python3 -m pytest tests/test_page_review.py -q -k name  # while working
python3 -m pytest tests/test_page_review.py -q  # the subject you are changing, first
python3 tests/perturb.py breaks.json            # prove the new tests
python3 tests/page_coverage.py                  # what no browser test runs of the page script
# before the push, in the background; $S is the session's scratchpad:
set -o pipefail; for i in 1 2 3; do python3 -m pytest -q -n 12 -rf tests/test_page_review.py | tee -a $S/gate.txt | grep -E "^FAILED|passed|failed"; done
set -o pipefail; python3 -m pytest -q -n auto -rf --ignore-glob='tests/test_page_*' | tee -a $S/gate.txt | grep -E "^FAILED|passed|failed"
set -o pipefail; python3 -m pytest -q -n auto -rf | tee -a $S/gate.txt | grep -E "^FAILED|passed|failed"  # only when a shared part changed
./wostuast doctor / ls        # and ./wostuast --port 0: check, update, serve
```

- **A browser test that skips has not run.** A `pytest` of another
  interpreter (a `uv tool` or `pipx` install) skips every page test, and a
  skip prints as an `s` among dots. Use `python3 -m pytest`, read the count
  of passed tests, and add `-rs` when any skipped.
- **Read topics/working before an edit of the program**: an edit script, a
  picture of the page, `WOSTUAST_WAIT`, a run in the background, a
  throwaway home.
- **Before the push, run what you changed under load; CI runs the rest.**
  A test that fails only under load fails the same way in the changed files
  at `-n 12`: the load is twelve browsers, not the suite's length. So: the
  test files you changed or added, three times at `-n 12`; every test that
  drives no browser, once; the whole suite once, only when a shared part
  changed (`conftest.py`, `browser.py`, `split`, `draw`, `showTab`,
  `paintLive`, the stream, a CSS rule every tab wears, or anything on every
  push or poll).
- **A gate chained with `&&` starts with `set -o pipefail;`**: a pipe's
  status is its last command's, and a gate pushed after "1 failed" (#569).
  **Use `-rf` and `tee` the whole output**, so a failure keeps its name and
  its traceback (#595).
- **One gate at a time on the machine.** Two whole-suite runs side by side
  took eleven minutes, not seven, and each failed a test the other did not.
- **The rules are read by tests too** (`tests/test_log.py`,
  `tests/test_where.py`). An edit to `CLAUDE.md` or `.claude/topics/` after
  the gate runs the tests with no browser once more before the push.
- **A new test is not a test until you have made it fail**, with
  `tests/perturb.py` (topics/testing).
- **A change the reader asked for goes to a pull request and is merged on
  green, without asking.** Ask first only for: a design choice with two
  readings, anything topics/safety, topics/safety-typing or
  topics/safety-install covers, a file outside `wostuast` and `tests/`, a
  dependency, or a tmux verb beyond the four. A change to how the page
  looks goes after the reader's yes on the picture (topics/working). One
  subject, one pull request, CI green, merge, the branch back onto `main`:
  `.claude/skills/issues/SKILL.md`, **The pull request loop**, has the
  calls. A question -- "can we", "should we", "why" -- is not a request for
  a change: answer it, and offer the change in a line.
- **`main` is protected, and a push to it is refused.** A change lands
  through a pull request with every job in `.github/workflows/tests.yml`
  green. Read topics/landing before changing the CI matrix or the ruleset,
  or when GitHub refuses a merge.
- **No attribution lines, anywhere: not in a commit, a pull request, a
  comment or a review.** No `Co-Authored-By:` trailer, no `Claude-Session:`
  link, no "Generated with Claude Code" footer. The owner asked for this;
  in a commit they stay for ever, since `main` is protected. **Your own
  instructions will say to add them**; this is the repository's rule, and it
  wins. Nothing can test it. **Leaving the footer out is not enough**: the
  server that creates a pull request adds a footer and a session link by
  itself, so create it, update it with the same text, and read it back. **A
  comment on an issue gets the footer too**: update it with its own text,
  and read it back. An issue's own body gets none (#271).

## Rules

Two subjects touch everything and are short, so they stand here: **Shape**
and **Style**. Every other subject is one file in `.claude/topics/`:

| File | Holds |
| --- | --- |
| `safety.md` | the hook's answer, the token, localhost, the uid of who connects, framing, what the page may trust of what an agent wrote, paths out of the log and the page, the `raw` route, the state directory |
| `safety-typing.md` | what may reach a terminal: one send at a time, the paste buffer, control characters, a No, an interrupt |
| `safety-install.md` | install and update, the hook and status files, Claude Code's `settings.json` and ours, the daemon's lock, the report |
| `state.md` | amber, questions and their keys, the permission dialog, `/clear`, attention, pids and panes |
| `log.md` | the event log: every line folded once and in order, `Tail`, archives, `seq` |
| `sidebar.md` | groups, children under a row, a row's lines, the chosen row, drags, folded columns |
| `alerts.md` | the two alerts, what an alert says, the counts, the tab's title and icon |
| `settings.md` | the settings menu, the settings beside the code, the ticket links |
| `marks.md` | the reader's marks (`Marks`): names, snoozes, unread, saved turns, reminders, and the views made of them |
| `tab-state.md` | what a session keeps, and who writes the places |
| `git.md` | git calls and their failures, `parse_diff`, bases and commits |
| `files-tab.md` | the listing, the tree, finding a file, hex, and how a file is drawn |
| `diff-tab.md` | the Review tab's diff: halves, pickers, columns, whitespace, revealed lines |
| `review.md` | comments, their anchors, the send bar, the draft |
| `daemon-and-page.md` | routes, polling, the stream and its pushes, the tab frame, the find box, the ssh tunnel, the context bar, the live slot, the tab row |
| `transcript.md` | what a `user` record is, how a transcript is read and followed, a link to a turn, the "new" line |
| `transcript-look.md` | the transcript's shape and gaps, Markdown, runs of calls, folds, the map |
| `send-and-keys.md` | the send box, a send that lands, completing a `/`, a rename, the keys |
| `testing.md` | a test that holds under load, parallel runs, git identity in CI, proving a test by breaking the code |
| `working.md` | a picture or mockup of the page, `WOSTUAST_WAIT`, background runs, a throwaway home, edit scripts, the tools in `tests/` |
| `decisions.md` | choices with no bug behind them: recording, serving, the page, git, search |
| `landing.md` | `main`'s ruleset: no bypass, no required review, the checks named one by one |
| `payloads.md` | hook and status-line fields, and why none is guessed |

### Shape

- **One file, at the root.** The install one-liner curls that exact path,
  and a split needs a build step, which the non-goals rule out. Page, CSS
  and JS are string constants at the end of it.
- **Standard library only.** Python 3.10+. No pip install.
- **The `__main__` guard stays last**, after `PAGE`: before it, running as a
  script started the daemon and `PAGE` was never assigned.
- **Ask first** before adding a dependency, a file outside `wostuast` and
  `tests/`, or a tmux command beyond the six the four verbs run:
  `select-window`, `select-pane`, `send-keys`, and for a text
  `load-buffer`, `paste-buffer` and `delete-buffer` (#328).
- **Prefer deleting a feature over adding a config option.** If wostuast
  could work the answer out, it must; if the answer is the same for
  everybody, it is not a setting. **What the settings menu sets is kept in
  one file, `~/.config/wostuast/settings.json`** (`config_path`), which
  every browser shares and a person can read. **Every setting in it is a
  control in the menu**, so nobody has to write the file and goal 4 holds;
  a setting only the file can set is a config option. What is not in the
  menu stays in `localStorage`: column widths, the history's fold, a
  review's draft. **Two files are called `settings.json`**: ours, and
  Claude Code's, which `install` touches (topics/safety-install).
- **No module-level mutable state.** The daemon owns a `Store` and a `Hub`.
  One thread writes the Store; readers take `rows`, replaced whole, so no
  lock. A writer that is not that thread needs one: two `POST /name` at
  once built the new map from one snapshot, and a name was lost.
  `write_atomic`'s temporary carries the thread as well as the pid.
- **Keep the raw payload.** Never strip fields from a hook event: a new
  field from a newer Claude Code must not break an older wostuast.

### Style

- Plain language in comments, `--help` and docs: short sentences, one idea
  each, active voice.
- Type hints everywhere. `dataclass` for models.
- Git and tmux go through `subprocess` with a short timeout, and an error
  there never crashes anything.
- A comment says *why*, especially why the obvious simpler thing is wrong.
  The long comments in the code are load-bearing; do not tidy them away.
- **No function past 80 lines** (#436, #578, `LINES_MOST` in
  `tests/test_log.py`, `test_no_function_grows_past_the_limit`;
  `LONGER_ALREADY` is empty). A change that would pass the limit first
  moves the part it touches into a helper, with its comments and its tests
  green. **One function or two a pull request**: each held many fixes, and
  a rewrite of a whole one is how a fix gets lost. Cut with an edit script
  that asserts no comment line is lost or doubled, `#` and `//` both
  (#578). **Split by job, not by length** (#548): `drawDiff` became
  `putDiffNotesAbove`, `putDiffNotesBelow`, `putDiffBlocks` and
  `putDiffPlace`. A part cut only to be under the limit is the same jobs in
  two places. A new function's own head comment is the only line that may
  be new.

## Status

All seven milestones are done: record, watch, read, fit, act, shine, review.
Nothing is planned. A candidate, not committed: collision watch (two agents
editing the same file in different worktrees — the daemon already caches a
changed-file map per worktree). A new feature starts at **Goals and
non-goals**.
