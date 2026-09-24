# CLAUDE.md

No human reads this file. It is the map, the reuse index, and the scars.

**How a rule is written here, and how to add one.** One bullet: the assertion
in bold, then why the obvious alternative is wrong, then the symbols to grep
and the test that holds it. Name the symbols in the rule itself, so `grep -n
tmux_send CLAUDE.md` finds it.

**Never cut the why to make this shorter.** The assertion says what to do; the
why is the only thing that stops the next agent doing the plausible wrong
thing again, and every one of these was written after something shipped
broken. This file is long because the program is subtle, and it is read by
something that can hold all of it at once.

**State no number a person would have to maintain.** Give the command that
answers it. Three numbers in here went stale by 40% before anybody noticed,
and a stale fact is worse than no fact: it is believed. **A measurement is
not that**: "2,500 lines took 144 ms" records an experiment somebody ran, and
it stays true. The rotting kind describes this repository as it is today —
how long the program is, how long the suite takes.

`PLAN.md` is the brief and wins where the two disagree. Read it when the
question is *what* or *why* — the goals, the non-goals, and section 12, which
is the decision log. This file is *where* and *how*.

## Where to look

Rules are grouped by what they are about. Find yours before editing, not
after the tests go red.

| About to touch | Read |
| --- | --- |
| `cmd_hook`, anything on the hook path | Safety, first two bullets. It must never print and never block. |
| a hook or status-line field name | **Do not guess payload fields**, and `tests/fixtures/README.md` |
| `tmux_send`, `tmux_jump`, `tmux_interrupt`, any `POST`, `allowed`, `origin_ours`, `Serving` | Safety: the token, localhost, what may reach a terminal |
| `answer`, `ask_keys`, `shows_preview`, `tmux_keys`, `askKeys`, `submitAsk`, `state.picked` | State: the question bar's bullets — the keys are measured |
| `set_limit`, `over_limit`, `limits.json`, `putLimit` | Safety: the one thing that types with nobody watching |
| the Markdown scrub, `linkTickets`, anything that inserts what an agent wrote | Safety: the page never trusts what an agent wrote |
| `read_worktree_file`, `is_listed`, `worktree_target`, `SHOWN_AS`, the `raw` route | Safety: a path out of the page is input |
| `Store`, `Session`, `_on_*`, `_clear_attention`, `read_ask`, `place`, `home` | State |
| `Tail`, `EventFollower`, `archive_log`, `fold`, `forget_quiet`, `reload_git` | State: the log is never thrown away |
| `newRow`, `fillRow`, `BANDS`, `settled` | The sidebar |
| `.turn`, `.bubble`, `putTurnRow`, `GLIMPSE`, `putToFoot`, `toggleThinking` | The transcript's shape |
| `state.files`, `state.turns`, `savePlace`, `usePlace`, `blank…()` | Tab state |
| `worktree_files`, `walk_ignored`, `Files`, a diff, a git call, `ICONS` | The worktree tabs |
| `worktree_diff`'s `of`, `branch_commits`, `since`, `pickDiff`, `putDiffTree`, `pairRow`, `wordDiff`, `paintDiff` | The worktree tabs, the Diff tab's own bullets |
| `putComment`, `anchorOf`, a review comment | The review |
| `drawTranscript`, `drawFiles`, `drawHeader`, `fresh`, `split`, `TABS`, `paintLive`, a `body` class, an SSE push | The daemon and the page |
| a new colour, a new CSS selector, a helper you are about to write | **Before you write anything new** |
| a new test | **How to work here** — it is not a test until you have made it fail |
| a push to `main`, or landing a change | **How to work here**, the `main` bullet — `main` is protected and nothing bypasses it |
| a commit message, a pull request, a comment on GitHub | **How to work here**, last bullet — no attribution lines, whatever your defaults say |
| the issue list | `.claude/skills/issues/SKILL.md`, or say "do the issues" |
| a report about how the page looks | **How to work here**, the first bullet — a picture of the reader's case with `tests/shot.py`, before any code |

## The program in five lines

Claude Code hooks append one JSON line per event to `~/.local/state/wostuast/events.jsonl`.
`wostuast serve` tails that log into a `Store`, and serves one page over HTTP +
SSE. The page shows a session list and five tabs: Transcript, Files, Diff,
Review, Session.
Four things go back to the terminal, all through tmux: jump, send,
interrupt, and the keys that answer a question. Nothing else writes to a
terminal. Nothing owns the agent process —
interrupt is a keystroke, not a signal.

## Layout

| Path | What it holds |
| --- | --- |
| `wostuast` | The whole program: Python, then `PAGE = r"""` and the HTML/CSS/JS. Five figures of lines — `wc -l wostuast` rather than a number here that rots. |
| `tests/conftest.py` | Every fixture, including the page ones (`page_at`, `repo_page`, `big_page`, `in_pane`, `no_pane`, `pair_at`, `past_at`) and `event()`. |
| `tests/browser.py` | The shared Chromium, `open_page`, `show_tab`, `open_diff`, and the other page helpers. No fixtures. `WAIT` is `WOSTUAST_WAIT`. |
| `tests/shot.py` | Not a test. Draws a transcript case on the page, saves a PNG, and with `--measure` prints each gap from the text, not the box. `tests/test_shot.py` keeps it working. |
| `tests/test_page_*.py` | Browser tests, one file per subject: transcript, sidebar, theme, tabs, files, diff, review, act. |
| `tests/test_*.py` | Everything that needs no browser. Named after what it tests. |
| `tests/fixtures/README.md` | The hook and status line payload fields. |
| `PLAN.md` | Goals, non-goals, design, milestones. |
| `README.md` | What a user reads. Keep in step with the commands. |
| `.claude/skills/issues/SKILL.md` | How to work the issue list: group, reproduce, ask, prove, review, merge on green, read the list again. Invoked as `/issues`, and by "do the issues". |
| `.github/workflows/tests.yml` | The only CI. A pytest matrix over 3.10–3.13, four sharded browser jobs, and an aggregator named `browser` that the branch rule requires. No job names a test file, and none may — naming one broke the browser job the moment a file was renamed, and the shards split on a hash of the test id for that reason. |

### Finding code in `wostuast`

Every section starts `# --- name: one line ---` (Python) or `// --- name ---`
(page). `grep -n "^# --- \|^// --- " wostuast` prints the whole map in one go.
Do that before grepping for a symbol.

Python: constants · log · event log · following files · **session model
(PLAN 4.3)** · transcript · git facts · **files and diffs** · status ·
settings.json · output helpers · ansi · **tmux verbs** · **the daemon** ·
commands · command line · the page.

Page: asking the daemon · dragging an edge · the two fetched scripts · colours ·
**the sidebar** · tab icon · notifications · **the transcript** · painting code ·
**the Files tab** · finding a file · the tree · a file too long to draw whole ·
how a file is drawn · **the Diff tab** · **the review** ·
keeping a review · **the Review tab** · the tabs · talking to the
daemon · keys.

## Before you write anything new

This list exists because each entry was re-implemented once already.

**Page helpers**

| Want | Call |
| --- | --- |
| "has this changed since I drew it?" | `fresh(box, which, key)` — do not hand-roll a `dataset` compare |
| make an element | `put(parent, tag, cls, text)` |
| scattered-letter match | `fuzzy(text, query)` → `{score, at}` or null |
| the items in a list whose path matches the find box | `hits(items, pathOf)` — keeps the caller's order; `pick(names)` is the same sorted best-first |
| walk a diff's lines with their numbers | `walkHunks(one, onHunk, onLine)` |
| the two-column tab frame | `split(box, tab, bodyClass)` → `[list, pane, note, foot]`; the list also carries the tab's name as a class |
| the rounds of a conversation | `rounds()`, `shownRounds()` (filtered), `glimpse(text)` |
| a review comment's identity | `anchorOf(path, side, line)`, `lineAnchor`, `commentAt` |
| "3 min ago" | `ago(when)` — `40s`, `4min`, `2h 15min`, `2d 6h`; two units once the first is coarse |
| one session's route | `apiUrl(id, what, query)` |
| the reader's ticket links in some text | `linkTickets(root)` — after any scrub |
| "15:48", and "21 Sep" when it was not today | `clock(when)`, `dayOf(when)` |
| text onto the clipboard, with the old way behind it | `copyToClipboard(text)` |
| which sessions are listed | `shownSessions()` (filter only) vs `listedSessions()` (what is on screen) |
| a file as rows, or a slice of one | `linesOf(text)`, then `asLines(path, lines, from)` |
| a binary file the browser can show | `putMedia(parent, path, found)` — `found.shown` is the daemon's answer |
| a folder or a page icon | `putIcon(parent, "dir" \| "dirOpen" \| "file")` — SVG, so not `put` |
| the places a reader can go | `state.files.places` — the names and the directories |
| bytes, or a date a person reads | `sizeOf(bytes)`, `whenOf(seconds)` |
| a diff's files in the order its tree reads | `treeOrder(found, pathOf)` — folders first at every level |
| which words of a changed line changed, and marking them | `wordDiff(was, now)` → two lists of runs or null, then `markWords(cell, runs)` |

**Python helpers**: `path_label`, `clip`, `run` (subprocess with a timeout),
`private_dir`/`private_file`, `safe_transcript`, `worktree_root`, `is_listed`,
`inside`, `ansi_runs`, `GONE_STATES`, `STATE_WORDS`.

**Test helpers**: `conftest.event(name, sid=..., **extra)` builds a hook event —
never hand-write the dict. `conftest.record(kind, text, ...)` builds a
transcript record — `you`, `claude`, `think`, `tool`, `result` — and
`conftest.records(...)` makes them the lines of a file; never hand-write
those either, because a hand-written one ended in a backslash and an `n`
rather than a newline and the reader waited on it for ever. `browser.py` has `open_page`, `show_tab`, `open_diff`,
`comment_on_first_line`, `two_rows`, `rgb`/`contrast`, `numbers`, `open_code`.

**CSS**: `.verb` (button; `.verb.quiet` is the same shape a size down, for a
button that only changes what is on screen), `.link` (small text button, now
only the file header's reading toggles), `.acts` (what you can do to a comment,
at its right edge), `.find`/`.findslot`,
`.empty`, `.nohits`, `.note`, `.dot`, `.comment`. **Every colour is a variable**
and a `:root` block is the only place a colour may be a number —
`test_every_colour_outside_the_palette_is_named` fails the build otherwise.
Derive a tint or a ring with `color-mix`, never by copying an rgb triple.

Three page functions are about matching and they are easy to confuse:
`matches` asks whether a transcript block matches, `matching` filters the file
tree, `hits` filters any list by path. Adding a fourth word for the idea is how
one of them gets shadowed — that happened, and the browser tests caught it as
fifty failures.

Before adding a CSS rule, grep for the selector. `.turn` already carried a slide
animation for four milestones while a second one was added on top of it;
`.row .dot` already had its transition. The review's hover button was given
`.plus`, which was already the green "+3" beside a changed file — so every
count on the page became an invisible 18×18 box, and a file that had gained
lines read as if it had only lost them. Nothing looked broken; the number was
simply not there.

## How to work here

```
python3 tests/shot.py case.txt out.png --measure  # a report about the page: look first, about 1 s
WOSTUAST_WAIT=5000 pytest tests/test_page_review.py -q -k name  # while working: a lost wait fails in 5 s
pytest tests/test_page_review.py -q # the subject you are changing. Do this first.
pytest -q -n auto                   # the gate, once, before the push. Needs pytest-xdist.
pytest -q                           # same result, about three times as long
pytest tests/test_state.py -q       # no browser, under a second
./wostuast doctor / ls / serve
```

**A report about how the page looks starts with a picture of the reader's
case, and ends with another one.** Write the case from their screenshot — a
few lines of `you:`, `claude:`, `think:`, `tool:` — run `tests/shot.py` with
`--measure`, and look at the PNG before reading any code. A spacing report
went round three times, and three pull requests, because every fix was
proven by a test measuring the box around each block, which said 6 px, while
the reader looked at the text, which stood 39 px from what came next. The
picture shows that in one look and `--measure` prints both numbers. It is
done when the new picture looks right, not when a test is green — then pin
it with a test that measures what the picture showed.

**Work in one file, then run the whole suite once.** While working, run the
one test and the one file, with `WOSTUAST_WAIT=5000`: a wait for something
that never comes then fails in five seconds rather than thirty, which is
three of them a minute and a half in one sitting. The full suite and the
three runs at `-n 12` below come once, before the push. `WOSTUAST_WAIT` is
for a desk, never CI: the 15 s and 30 s waits are what a loaded runner needs.

Most of the suite drives a real browser, so it waits far more than it computes:
four workers cut it to about a third, and the tests are safe in parallel —
every daemon binds port 0, every fixture has its own `tmp_path`, and each worker
launches a Chromium of its own. **Oversubscribing the cores pays, up to about
twice their number.** Measured on four cores over the whole suite: `-n 4` 110 s,
`-n 6` 96 s, `-n 8` 88 s, `-n 12` 107 s. Nothing timed out at 8, which
supersedes the older note here that more workers than cores only made things
worse — it stopped being true as the suite grew. The tests that run no browser
are the other shape, CPU-bound and slightly *slower* at `-n 8` (25.5 s against
24.5 s), so CI runs the matrix at `-n auto` and the browser shards at `-n 8`.

**What the suite does not cover.** It drives the happy path thoroughly, in a
real browser. It says very little about what happens when something *fails*: of
the eight issues a full-file review filed, three were "a failed git call renders
as an answer", one a lock race between two HTTP threads, one a rotation race
between two hooks. Green is not evidence about those. When you change anything
that calls git, touches a file, or is reached from more than one thread, write
the failing case yourself — nothing else will.

Throwaway home, never your own:

```
export HOME=/tmp/try WOSTUAST_STATE=/tmp/try/state CLAUDE_CONFIG_DIR=/tmp/try/claude
```

`WOSTUAST_STATE` and `CLAUDE_CONFIG_DIR` are test seams, not user settings. Do
not document them as settings.

**Editing one very large file.** Anchor on a unique string and assert you hit
it exactly once; a sloppy replace in a file of this size fails silently. A small
Python script with `assert s.count(old) == 1` before every `replace` is the
reliable shape when making several edits at once.

**Prove a test earns its place — by breaking what it claims to guard, which is
not always the fix you just wrote.** Write the test, then perturb the thing it
is about and watch it fail. Two have slipped through here:

- One passed with its fix removed, because another line was saving the state it
  asserted.
- One claimed `is_listed` is never cached, and removed the file with `git rm` —
  which deletes it from disk, so the read was refused by `target.is_file()`
  whatever `is_listed` said. Reverting the cache would not have caught it. The
  perturbation that did was stubbing `is_listed` to always say yes.

Ask what single change should make this test go red. If that change is not the
one you make, the test is about something else than you think.

**Playwright.** A hover-only control (`.plus`) needs `click(force=True)`. Wait
for what the page has drawn, never for a number of seconds; `wait_for_timeout`
is right only when proving something did **not** happen. Ask one question when a
redraw could land between two: `wait_for_function("...length === 1")`, not
`wait_for_selector` then `.count()`.

**A change a stream test expects goes out after the first event, never
after a sleep.** `test_a_change_is_pushed` made its change from a thread
0.3 s after it started to connect. On a loaded CI runner the stream opened
after the push: it began on the new state, and the read waited for a second
event that never came. `read_events(..., then=change)` runs the change once
the first event is in, and `stream` joins the hub before it writes that
event, so nothing pushed after it is lost.

**`open_page` returning is not the transcript arriving, and `show_tab` is not
the tab's content arriving.** Both wait for the frame — the map beside the
transcript, and the document inside the Files tab, fill one fetch later.
Abort `api/session/*/transcript` and the list is empty with the page otherwise
drawn, which is what a loaded CI runner looks like. `wait_for_map(page, rows)`
is the wait for the transcript; for anything else, wait for the element you
are about to read.

**To hold what a key *says*, spy on `note`, not on `#live`.** The slot is
repainted on every push and the stream is allowed to take a passing word
back, so reading it after a keypress is a race. Reassigning `note` in the
page and keeping every word in an array holds both halves at once: that the
key is bound to the thing that speaks, and what it said. Calling the function
directly instead proves only the second, and then nothing guards the binding.

**The live slot is repainted on every push, so read it in the same
`evaluate` that writes it.** `note()` borrows the slot and the stream is
allowed to take it back — that is what one painter means. A `wait_for_function`
asking whether the word is there can therefore run after a repaint and wait
out its timeout, which is a test of the machine's load and not of the page.
Writing and reading inside one `evaluate` has no gap in it: JavaScript is
single-threaded and no push can land in the middle of the call.

**This scar keeps coming back, so recognise its shape rather than its
names.** It has been six tests over three sittings, and every one of them read
`.turn`, `.prose`, `.who`, `state.turns.blocks` or the find box on the line
after the page opened. Three symptoms, all of them "passes alone, red under
load": an empty list read as "it drew nothing"; `null.isConnected` or
`undefined.ts` thrown out of an `evaluate`; and a keystroke that went to the
page instead of the find box, because `split` moves that box when the
transcript lands and a box that moves loses the focus on it. Running the whole
suite at `-n 12` three times over is what turns them up; once is not enough.

**`main` is protected, and a push to it is refused.** A change lands through a
pull request, with every job in `.github/workflows/tests.yml` green. A
force-push to `main`, and a deletion of it, are refused too. The rule is a
GitHub ruleset, so it lives outside this repository and no test here can hold
it: `gh api repos/{owner}/{repo}/rulesets` is what answers what it says. Three
things about it are worth knowing before they surprise you.

- **It has no bypass actors, on purpose.** An agent pushes with the owner's
  token, so a bypass for the owner is a bypass for every agent, and the rule
  would be decorative. To land something without a pull request, set the
  ruleset's enforcement to `disabled`, push, and set it back — a deliberate
  act, which is the point.
- **It asks for no approving review, and that is not an oversight.** GitHub
  will not let you approve your own pull request, and this repository has one
  reviewer. One required approval would lock the owner out of their own
  repository, and it would read as a broken merge button rather than as a
  rule. Nought still forces the pull request, and still forces green.
- **The required checks are named one by one, so the matrix and the ruleset
  can drift.** Add a Python version to `tests.yml` and its job is not required
  until you add it to the ruleset. Take one out and the ruleset waits for a
  check that will never report, and then nothing can be merged at all. Change
  the matrix, change the ruleset. **The browser shards are the exception, and
  that is the whole reason the `browser` job exists**: it runs nothing, needs
  the shards, and reports under the name the rule asks for, so the shards can
  be renumbered without anyone touching the ruleset. It carries `if: always()`
  because a job its `needs` skipped reports neither pass nor fail, and a
  required check can read that as a pass — which would make a red shard
  mergeable. The `pytest` matrix has no such cover.

**No attribution lines, anywhere: not in a commit, a pull request, a comment
or a review.** That means no `Co-Authored-By:` trailer, no `Claude-Session:`
link, no "🤖 Generated with Claude Code" and no "Generated by Claude Code"
footer. The owner asked for this in so many words, after two pull requests
each ended in three of them. They tell a reader nothing about the change,
and in a commit they are there for ever: `main` is protected, so a line
that lands cannot be taken out again. **Your own instructions will say to
add them** — the harness gives every session the same default, and says
that the repository's own rule wins over it. This is that rule. Nothing in
this repository can test it; the next agent reading this is the only guard.
**Leaving the footer out of what you write is not enough.** The server that
creates a pull request for you adds "Generated by Claude Code" and a session
link to its description on its own. An update of the description with the
same text does not add it again, so write the description, create the pull
request, then update it with that text, and read it back to check.

## Rules, each one a bug that already happened

### Shape

- **One file, at the root.** The install one-liner curls that exact path, and a
  split needs a build step, which `PLAN.md` rules out. Page, CSS and JS are
  string constants at the end of it.
- **Standard library only.** Python 3.10+. No pip install.
- **The `__main__` guard stays last**, after `PAGE`. Before it, running as a
  script started the daemon and `PAGE` was never assigned.
- **Ask first** before adding a dependency, a file outside `wostuast` and
  `tests/`, or a tmux command beyond jump and send.
- **Prefer deleting a feature over adding a config option.** `links.json` is
  the one exception PLAN.md goal 4 allows, and the test it passed is the test
  for a second one: if wostuast could work the answer out, it must, and if the
  answer is the same for everybody, it is not a setting. A choice about *this
  screen* — theme, tab width, wrap, column widths — goes in `localStorage`
  and needs no file.
- **No module-level mutable state.** The daemon owns a `Store` and a `Hub`. One
  thread writes the Store; readers take `rows`, replaced whole, so no lock.
  A *writer* that is not that thread does need one: `POST /name` runs in the
  request's own thread, and two at once built the new map from the same
  snapshot, so one name was lost and memory and the file disagreed about
  which. `write_atomic`'s temporary carries the thread as well as the pid, for
  the same reason — two threads of one process are as real as two processes.
- **Keep the raw payload.** Never strip fields from a hook event: a new field
  from a newer Claude Code must not break an older wostuast.

### Safety — the page can type into a terminal

- **Never approve a permission prompt.** Claude Code reads a hook's stdout as
  its answer, and we register `PermissionRequest`. One `print()` in `cmd_hook`
  answers a permission dialog for the user. Logging goes to the log file. Tests
  assert the silence by event name; never weaken them.
- **The hook must never block Claude Code.** try/except around everything,
  `give_up_after` deadline, always exit 0. Keep all three. The deadline covers
  every wait at once, including a stdin that never closes — **and it stays
  armed over the logging on the way out.** `log` opens and writes a file, and
  the failure being logged may be that the filesystem is not answering.
- **Every POST carries a token.** A cross-origin `fetch` may POST to a loopback
  port unasked, and the effect here is `tmux send-keys` into a live terminal.
  `allowed()` wants three things to agree: Host, an Origin that is ours when
  there is one, and the token printed into the page.
- **The daemon answers on localhost only.** Binding to 127.0.0.1 is not enough —
  a site can point its own name at 127.0.0.1. `Serving.ours()` checks Host, and
  a request without one is refused: an empty Host used to pass, which made the
  check skippable by leaving the header out.
- **A check must fail closed, and nothing may run outside the guard.** Both
  checks used to sit in front of the `try`, where `Origin: http://[::1` or one
  byte above 0x7f in the token header killed the thread — no status line, a
  traceback into the terminal running `serve`, from a request nobody had
  authenticated. They refuse a header they cannot read; `guarded()` catches
  the rest, and it wraps the whole of a request.
- **A body that is not read stays in the socket.** `asked()` refuses one over
  `POST_MAX`, and with keep-alive the rest of it was parsed as the next
  request: the daemon answered a `GET` written inside a refused POST's body,
  three answers on one connection. Refusing to read the body closes the
  connection. The handler has a socket timeout for the other half of it — a
  `Content-Length` announced and never sent held a thread for ever.
- **The page never trusts what an agent wrote.** Markdown goes into an inert
  `<template>`, is scrubbed to an allowlist, and only then inserted. Values from
  events use `textContent`. Assigning `innerHTML` first fires `onerror` before
  any scrub runs — that was real.
- **An autolink runs after the scrub, over text nodes, and checks its own
  href.** `linkTickets` builds one anchor at a time and never parses
  anything, so a `url` template can put text on the page and nothing else.
  `ticketUrl` tests for `http(s)` a second time, although `link_trouble`
  already refused anything else: the two sides are far apart and only one of
  them is the one that inserts. `links.json` is the reader's own file, in
  the state directory — never a per-worktree one, which an agent could write.
- **Nothing can time a regular expression out in a browser.** `risky_pattern`
  spots the one shape that backtracks catastrophically — a quantifier inside
  a quantified group — and `LINKS_MAX` caps the links in one block, and that
  is the whole of the defence. **`LINKS_MAX` lives in the page and nowhere
  else**: the daemon carried the same name and the same number and read it
  nowhere, because the page is the only side that makes a link — a copy that
  is not a second opinion is a second thing to forget. Raising it is a number
  somebody has measured, not a guess:
  `test_there_is_still_a_cap_on_the_links_in_one_block` builds 500 links out
  of 5,000 matching words and asserts the time. It is a heuristic; say so rather than implying
  the page is safe from a pattern somebody writes.
- **The page never builds HTML from a pane.** `ansi_runs` hands over stretches
  of text with colours, never markup.
- **What a `send` may be is counted in bytes, and tmux is what sets the
  number.** Bisected against tmux 3.4: `send-keys -t %0 -l -- <text>` takes
  16,341 bytes and refuses 16,342 with "command too long"; the same run with
  `ä`, two bytes in UTF-8, stops at 8,170, and by session name rather than
  pane id at 16,338 — the target comes out of the same budget. So a cap on
  `len()` lets three times the bytes through in Japanese and tmux refuses the
  lot. `SEND_MAX` is that cap and it is bytes; `test_the_cap_on_a_send_is_in_bytes`
  holds it. A long message is refused, never cut, and never split across two
  sends: a bracketed paste broken in half leaves the rest arriving as
  keystrokes, which is the scar below.
- **A verb tmux refused says so, and says only what it knows.** `send` and
  `jump` both used to answer `{"done": false}` with no `error`, and `said`
  clears the slot for an answer that carries none — so the reader asked for
  something, did not get it, and read nothing at all. Every refusal on this
  path carries a message. **`send`'s message does not claim nothing landed**:
  `tmux_send` runs two commands, the text and then Enter, and a failure on
  the second leaves the text sitting on the agent's prompt. "Nothing went in"
  would send the reader back to type it again, and it would arrive twice.
- **An empty body and a body that was refused is not the same answer.**
  `asked()` never reads a body over `POST_MAX`, so the route sees `{}` — and
  `send` refused it as "there is nothing to send", which is the opposite of
  what happened. `too_big` is set beside it, and cleared at the top of
  `asked()` rather than only set: with keep-alive one handler object serves
  every request on a connection.
- **Interrupt is Escape, and never Ctrl-C.** Claude Code's own
  documentation: Escape stops the current response or tool call mid-turn and
  "Claude keeps the work done so far"; Ctrl-C "interrupts a running
  operation", but "if nothing is running, the first press clears the prompt
  input and a second press exits Claude Code". A turn can end between deciding
  to stop a session and the key landing, so Ctrl-C on an automatic limit is a
  race whose losing side is a session that quit. Escape on an idle prompt does
  nothing. `tmux_interrupt` is a key name, the shape of the `Enter` press
  `tmux_send` already makes — not something that could go through `tmux_send`,
  which strips every byte below a space on purpose. Measured: `send-keys C-c`
  puts 0x03 into a raw-mode app as a keystroke it reads, not as a signal.
  `test_interrupt_sends_escape_and_never_ctrl_c` holds it.
- **A spend limit is the one thing here that types with nobody watching, so
  it is guarded three ways and says so afterwards.** `over_limit` fires only
  for a session that is **working** (Escape into an idle prompt is a keystroke
  nobody asked for, and Escape while a permission dialog is up declines it —
  a decision, and not this one's to make), only **once** (`fired_at` is
  stamped before the key goes out, or the key lands again on every tick and
  the agent can never be let go), and only on a spend the status line
  **actually sent** (`None` is "not told", and stopping an agent over a number
  nobody sent is the worst of the three). Raising the limit clears `fired_at`,
  which is how a stopped session is released — otherwise the only way on would
  be deleting a file nobody told you about. The page says it in the Session
  panel, beside the box that set it, because "why did my agent stop" is asked
  there and not in the pane.
- **A control that cannot work is disabled where it stands, and says why.**
  Everything on this page works with no tmux — the log, the sidebar, all five
  tabs, alerts, the spend on the strip. The five things that do not are the
  five that type into a pane: jump, send, interrupt, answering a question and
  submitting a review. jump, send and stop are simply absent for a session
  with no pane, and the review's submit has always refused; two were offered
  anyway. `paintPicks` enabled **submit** on a question and said `presses 1`,
  which is a promise of keystrokes into a terminal that does not exist, and
  `putLimit` took a number and warned only once one had been typed, because
  its `!s.pane` aside sat behind `!s.spend_limit` in the chain. **Reading is
  not acting**: the question bar and the limit box both stay where they are,
  because the panel is where you go to find out what a session is. It is the
  press that is refused. Grep `canType` and `box.disabled`.
- **`limits.json` is not a second config file.** `PLAN.md` goal 4 allows one,
  `links.json`, because a human writes it in an editor. This is written by the
  page through a POST and read by the daemon, which is what `names.json`
  already is. **The daemon enforces it, not the browser**: a limit that holds
  only while a tab is open is a promise that breaks when you shut the laptop,
  and two open tabs would each fire their own.
- **The tick reads the rows again after a stop, and not with `or`.** A stop
  moves `fired_at` and the session's last event, both of which are in the row.
  `if moved or self.store.refresh()` short-circuits, so on a tick that had
  already changed something the second read never ran and the browsers heard
  about the stop a tick late. `test_a_tick_stops_a_session_that_has_gone_over`
  reads the row, not just the tmux call, for exactly this.
- **The limit box listens for `change`, never `input`.** On `input` the box
  posts $1 on the way to $12, and a session already past a dollar is stopped
  by a number the reader was still typing. The test spies on `tell` and
  asserts one call.
- **The limit box lives in `drawSession`'s kept half, and it is guarded
  twice.** `rest` is rebuilt on every four-second poll, and a rebuild under
  the hand is worse here than for the name: the node is *removed* rather than
  blurred, so `change` never fires and the number is not merely lost on
  screen, it is never stored. So it sits in its own part with its own narrow
  key — that is what keeps the poll's churn out. **And the key is skipped
  while the box has the focus**, because unlike the name this field has news
  of its own: a status line that starts reporting a spend, or a limit that
  has just fired, arriving mid-word. Two tests, because the two guards fail
  differently.
- **`over_limit` decides and writes inside one lock.** Reading the map
  outside `naming` and merging `limits.update(fired)` inside it is a race
  with `set_limit`: a raise that lands in between is overwritten with the old
  number and a fresh `fired_at`, and the Escape goes out anyway — the
  reader's release undone at the moment they made it.
- **The limit is armed again when the spend drops below it.** `/clear` puts
  `cost.total_cost_usd` back to nought, so without this one stop disarms the
  limit for the rest of the session and the agent runs without bound behind a
  box still showing a number. Only `set_limit` used to clear `fired_at`.
- **The box says what it will *actually* do.** `over_limit` skips a session
  with no pane and one whose status line has sent no spend, so "Escape into
  this pane when the spend passes it" is a promise this program cannot keep
  for either — and a reader told they are protected when they are not is the
  worst thing this feature could do. Each case says which it is.
- **Nothing below a space reaches a terminal.** `tmux_send` strips control
  characters, keeping tab and newline. "Below a space" includes the C1 block
  above `\x7f` — NEL and CSI are controls, and U+2028 is a line break that
  `"\n" in text` does not see, so it went out unpasted.
  A bracketed paste ends at `ESC [ 2 0 1 ~`,
  and a review quotes lines an agent wrote, so those bytes would end the paste
  and leave the rest arriving as keystrokes — with any newline as Enter. A
  person reading the preview cannot catch this; an escape byte is invisible.
- **A newline sent to a terminal is Enter.** Text with one is wrapped in the
  bracketed paste markers. Without them a real shell ran the first line.
- **A path out of the event log is input, not fact.** `transcript_path` goes
  through `safe_transcript`. `cwd` is used for git and for labels, never to open
  a file the page asked for.
- **A path out of the page is input too.** `worktree_target` opens a file only
  when `is_listed` says git offers that exact name and `inside` says the resolved
  path is still in the worktree. Keep all three parts of the first check — the
  `:(literal)` prefix, the `--`, and comparing the answer to what was asked for.
  Ignored files are asked the same way. Never swap either check for a pattern
  that tries to spot a bad path. **Both readers go through it**, so a new one
  cannot be given one check and not the other.
- **`serve` leaves an example `links.json` and never writes over one.**
  JSON has no comments, so the example is a working entry — and a
  deliberately inert one, because nobody's work has a ticket called
  `EXAMPLE-1`. A commented-out entry is not valid JSON and a broken one
  would be a line in `doctor` saying the file is wrong. It is written with
  `write_atomic(private=True)`, like everything else there, and a failure to
  write it never stops `serve`.
- **A `links.json` that cannot be used is never silent.** "No links" and
  "your file is broken" looked identical — nothing on the page either way —
  and the only way to find out was `doctor`, which you had no reason to run.
  The first thing anybody writes is `\d`, which is not a JSON escape, so the
  file never parses. `load_links` returns the usable entries *and* what is
  wrong with the rest; `read_links` is the wrapper for a caller with nowhere
  to put the trouble. `serve` prints it, `/api/links` carries it, the Session
  tab shows it, `doctor` says it. **The file is never repaired**: guessing at
  a backslash somebody meant is a worse surprise than the message. And the
  page adds its own trouble — a pattern Python compiled and this browser
  will not is only findable there. `state.linkTrouble` is in the Session
  tab's redraw key, or a late answer draws nothing.
- **The list of what may be shown lives in the daemon, once.** `SHOWN_AS` is
  read by `shown_as`, which the `raw` route enforces and which
  `read_worktree_file` reports as `FileText.shown` — so the page holds no
  copy of it and `putMedia` reads the answer. A second list in a second
  language drifts, and a mismatch is silent either way round: a picture that
  never arrives, or a file that is never offered. A name on that list is
  reported `binary` without being read at all, because its text is not text
  and the two-second poll would otherwise read half a megabyte off it for
  nothing.
- **`raw` is the one answer a browser may keep.** Every other reply carries
  `no-store`. Its address holds the file's mtime, so a written file is a
  different address; without the cache header the browser fetched the whole
  thing again on every tab switch, which is exactly what the mtime in the
  address was there to avoid.
- **The `raw` route may never serve a document.** It hands a worktree file to
  the browser as its own bytes, and the type comes from the end of the name,
  out of `SHOWN_AS` — pictures, video, sound, and nothing else. An SVG or an
  HTML file served from here would be a page an agent wrote, on the origin
  that holds the token, with a script in it able to read both. `nosniff` is on
  every answer for the same reason: a browser that guessed the type from the
  bytes would undo the list. Never add a type to `SHOWN_AS` that a browser
  will execute or navigate to.
- **The state directory is private.** `0700` dirs, `0600` files — and `0600`
  **at creation**, through `open_private`. A `chmod` after the first write
  leaves a window in which the file already holds a prompt and anyone on the
  machine can read it, and that window does not close if the process dies in
  it. The log holds every prompt and every command an agent ran.
- **The hooks and the status line run the installed copy, not the checkout,
  and `serve` says when the two differ.** `install` copies this file to
  `install_path()`. A reader who pulled and restarted `serve` had a page
  that could show the session's spend, beside a status line — run by the
  copy from the day before — that never wrote it down. The page showed no
  cost and nothing said why; the reader's own status line printed the
  number, so the payload plainly carried it. `install_behind` compares the
  bytes; `serve` prints it on the way up and `doctor` counts it as a
  problem. `test_doctor_and_serve_say_when_the_installed_copy_is_another_version`.
- **`settings.json` is the user's file, not ours.** `install` touches our hooks
  and nothing else: its permissions are kept (a fresh temporary takes the
  umask, so 0600 came back 0644, on a file that can hold API keys), and the
  write is fsynced, file and directory — Claude Code will not start without
  it. `uninstall` leaves a group it took nothing out of exactly as it was,
  including an empty one the user put there.
- **Anything printed to a terminal is scrubbed, like anything sent to one.**
  `ls`'s last column is a `Notification` message or a tool summary — text an
  agent wrote. `table` takes the control characters out, in the one place a
  row becomes a line; one of them set the terminal's title and reddened the
  rest of the output, and `len` counting the escape bytes made the columns
  wrong as well.
- **A `flock` is on an inode, not on a name.** Between opening the log and
  getting its lock, another hook can rotate it away — and then the lock is on
  the archive. A hook that did not notice renamed the fresh log on top of the
  archive: every event ever recorded, gone. `still_the_file` is that check, and
  `append_event` opens again when it fails.
- **An event must survive what is in it.** A lone surrogate — legal in a JS
  string, so reachable in a tool response — makes a strict UTF-8 encoder
  refuse the whole line. Surrogates are replaced; a `SessionStart` lost that
  way costs the session its cwd, pane and pid for good.
  Never write the escape for one in source, not even in a comment: in a normal
  string it is the character, and Python 3.13 will not put a module holding one
  in a bytecode cache. CI was green on four versions and red on the fifth, over
  a docstring. Build one with `chr(0xD800)`;
  `test_no_source_file_holds_a_lone_surrogate` catches the next one.

### State

- **Amber means one thing: the agent cannot go on until you answer.** An idle
  `Notification` is not that — `Stop` already said the turn was over, and nothing
  you do clears an idle prompt, so a row that went amber on it stayed amber for
  ever. A permission `Notification` is dropped once the session has sent a
  `PermissionRequest`: after that it is the same news twelve seconds late, and
  honouring it raised the alarm again for a question already answered — and
  dropping it means the text too, or the row reads "ready" with a permission
  question as its only line. A notification with no `notification_type` is
  read for the message that means a dialog, never assumed to be one:
  `auth_success` ("Logged in as …") took the row amber with nothing that
  could ever clear it.
- **A question is a question, not a permission.** `AskUserQuestion` is a tool,
  so `PreToolUse` and then `PermissionRequest` carry the whole of it in
  `tool_input` -- every question, every option, every description. It used to
  fall to `tool_target`'s catch-all and reach the row as
  `AskUserQuestion {"questions": [{"question": "Approve the pla…`, clipped at
  eighty characters: everything the reader needed was in the payload and none
  of it reached them. `read_ask` keeps what the page draws, **named field by
  field**, because a row goes to every browser on every push and a field
  nobody read must not reach the page. The row says `asks:` and not
  `permission:` -- the word sent people looking for a dialog that asks
  something else.
- **`Session.asking` is cleared wherever the attention is, and by its own
  `tool_use_id`.** `PreToolUse` carries that id and `PermissionRequest` does
  not, so the ask is read from the first of the two: it is the only thing that
  says *this* question was answered. A `PostToolUse` for another call is not
  an answer -- two calls really do overlap -- and this stale question has
  buttons on it, which type a number into a terminal that has moved on.
- **The question bar belongs to the Transcript tab, at its foot.** It is not
  the bar `PLAN.md` took away: that one stood over every tab saying the
  branch, the pane, the model and the state, all of which the chosen row says
  one column to the left, at 56 px on every tab for ever. This stands in one
  place, over the send box, because the transcript ends at its foot and
  answering is sending. The row still goes amber from any tab, which is what
  the row is for. It reads `state.tab`, like the send box, because it is
  chrome outside the content box and is drawn after `showTab` has set the
  name. `drawAsking` is called from `drawHeader`, so a fifth call site cannot
  forget it.
- **Picking types nothing; submit does.** A click that went straight into a
  terminal was a click you could not take back, on a page you may have opened
  on a phone in a pocket. `state.picked` holds the indexes picked for each
  question -- one for a single-choice question, any number for a
  multiple-choice one -- **with the ask's id**, so a pick made for one question is never submitted for the
  next, and it survives a look at another tab -- the bar is built again when
  it comes back, and half an answer lost that way is a page you cannot trust
  with the other half. `paintPicks` is everything that changes on a click, so
  picking never rebuilds the bar: a rebuild under the hand is how a click
  lands on the wrong option. Submit waits until every question has an answer,
  because the agent asks them one after the other.
- **A button that types into a terminal says what it types, before it is
  pressed.** Each option carries its number, and the submit says `presses 2,
  then 2 4 Tab, then Enter` -- `askKeys` on the page, which is only the
  preview. **The page sends picks, never keys**: `submitAsk` posts the
  option numbers to `answer`, and the daemon works the keys out from the
  question it holds (`ask_keys`) and presses those (`tmux_keys`): digits,
  Tab and Enter and nothing else, refused for an ask id that is no longer
  the one waiting. `test_the_page_says_the_keys_the_daemon_presses` holds
  the preview and the presses together. **It does not clear the question**:
  that happens when the daemon sees the `PostToolUse`, because clearing on
  the click would hide a question a missed keystroke left standing.
- **The keys are Claude Code's dialog's, measured, and never a finger's
  guess.** Against 2.1.281 in tmux, with a fake Messages API asking: a digit
  answers a single-choice question **and moves on**; a multiple-choice
  question takes a digit per option, each a tick, and then Tab; after the
  last question a review stands with "Submit answers" under the cursor and
  takes Enter -- except after one single-choice question, which has none,
  where an Enter would land on the agent's prompt. This page used to send
  each number through `send`, which presses Enter after it: the Enter
  answered the next question with the option under the cursor, `2` on the
  review is Cancel, and a multiple-choice question ticked a second option
  and was never submitted. **One key per tmux command, with `KEY_GAP`
  between**: `24` written at once arrives as one read, which the dialog
  takes as no key at all, measured -- the ticks were lost and it moved on.
  **An ask the daemon could not keep whole is not answered** (`answerable`):
  keys go by position, so a question or option left out would move every
  key after it. **A single-choice question with a `preview` on any option
  is another dialog**: the options stand beside a box, a digit only moves
  the cursor, and Enter answers and moves on. The page pressed `3` alone
  there, so the reader's answer sat under the cursor and nothing was sent.
  `shows_preview` is Claude Code's own test for a preview it draws (its
  `pU`), and where that hangs on the width of an invisible character the
  ask is not answerable, because the keys would be a guess. A screen reader
  turns the layout off, and nothing in the payload says so. When Claude Code changes its dialog, measure it again the
  same way; do not read the new keys off the minified source, where Tab is
  bound twice and which binding wins is not written down.
- **A call starting clears the attention; a call finishing only clears its
  own.** Claude Code runs two tools at once now and then — one of 233 calls on
  a real machine started while another was still open, both of them `Bash`.
  Both `PreToolUse` events come before the dialog, so the other call reports
  back while it is on screen, and clearing on that turned the row green while
  the agent sat blocked. A `PreToolUse` is different: nothing new starts while
  a dialog is up, so one says the agent moved on — which is the only sign of a
  denial, because saying No fires no hook at all. `PermissionRequest` carries
  no `tool_use_id`, so the pairing goes by `tool_summary`; two runs of the same
  command at the same moment cannot be told apart, and nothing in the payload
  can.
- **A state change clears the attention with it.** Every handler that sets a
  state calls `_clear_attention` — `SessionStart` did not, so a session killed
  at its dialog and resumed came back "ready" with the old permission question
  under it. And the wait clock only starts when the wait does: a second
  notification about the same dialog moved it, so a row that had waited a
  minute said it had waited none.
- **Folding an event twice must change nothing.** Handlers assign, never
  accumulate; `Store.apply` drops an event older than the session has seen. A
  log rotation really does deliver old events after new ones.
- **`Session.log` and `Session.counts` are the two things that accumulate**,
  and the rule that makes them safe is **strictly newer**: `apply` drops what
  is *older* than the session has seen, but an event with the very same `ts`
  folds again and a rotation re-delivers the newest one. They are appended
  under `ts > last_ts`, which is asked once, before `last_ts` moves. Two
  events in one instant cost the log the second of them and nothing else. The
  log is bounded (`SESSION_LOG_MAX`); the counts are the whole story.
- **The log is never thrown away, so nothing may hold it whole.** Every
  archive is kept (`archive_log`, `archived_events_paths`), and a year of
  heavy use is a few hundred megabytes. Three things grew with it, measured on
  a 200 MB log shaped like a year, 1,873 sessions: `Tail` read the whole rest
  of a file in one `read()` and kept it twice over, 641 MB resident; the fold
  built a `Session` for every one of those sessions and `visible()` forgot the
  quiet ones only after it, 80 KB each; and `git_wanted` kept the directory
  of every tree-touching event ever folded, so the first refresh ran git on a
  year of worktrees, deleted ones included. Now `Tail.lines` reads
  `TAIL_CHUNK` at a time, `fold` calls `forget_quiet` every `FORGET_EVERY` of
  the *log's* clock, and `reload_git` asks only about a directory a shown
  session is in: 28 MB, flat. **Forget by the last event, never the first**:
  a session that started a year ago and is still going keeps where it
  started, and the test that holds it moves the session's `cwd` after its
  start, because every event carries one and a session forgotten and made
  again would otherwise look exactly right. **An empty piece is not the end
  of the file**: a line longer than `TAIL_CHUNK` gives nothing until one
  ends it, so the end is the size the file had when the read began.
  `test_a_big_log_is_read_a_piece_at_a_time` measures what is held with
  `tracemalloc`; `test_the_first_read_holds_a_week_of_sessions_not_all_of_them`
  and `test_git_is_asked_about_the_sessions_shown_and_no_others` hold the other
  two.
- **An archive's name is taken with `os.link`, never `os.replace`.** The next
  number comes from a listing and is then used, and `os.replace` puts the log
  on top of anything that landed on that name in between, silently — the scar
  below, where a rename over the one archive lost every event ever recorded.
  `os.link` refuses a taken name and costs one more try. The follower knows
  the file that has just become an archive by its inode and hands its tail
  over, place and all, because a tail that only knew names read all 20 MB of
  it again on every rotation.
- **`Tail` starting over is news the reader has to hear.** It restarts at
  offset 0 when the file shrinks or its inode changes, which is right — but a
  reader that only appends then drew the whole transcript a second time on top
  of what it held, and after a truncate went on showing text the file no
  longer had. `Tail.restarted` says so; `Transcript` clears and bumps `run`.
  The event log needs none of this, because `Store.apply` drops what it has
  seen.
- **`seq` is a place in one reading, not an identity.** The page patches by
  index, and `Daemon` builds a new reader whenever `transcript_path` changes —
  a session resumed from another directory, so `seq` counts from nought for
  the same session id. Every push and every reply carries `run`; a `run` the
  page has not seen replaces what it holds rather than being merged into it.
  Reproduce either one with a **rename**: an unlink and recreate may hand back
  the same inode, and then nothing restarts and the bug does not appear.
- **A pid is not an identity.** The numbers wrap. `pid_alive` asks `kill -0`
  *and* `looks_like_claude`, because a session that ended in the morning had
  its pid taken by something else by the evening and the row said "done" all
  day for an agent that was gone. Safe to read /proc there: a session only has
  a pid where `agent_pid` could read /proc in the first place.
- **A file over `CODE_WHOLE` lines is drawn a window at a time, and not
  painted.** Measured whole, in a browser, drawing and painting: 2,500 lines
  144 ms, 5,000 280 ms, 10,000 774 ms, 40,000 2.8 s — and it is paid again on
  every save of the file being read. `CODE_WHOLE` is 5,000, which covers a
  hand-written source file, which is what a reader is looking at. It was 2,000
  and an ordinary file lost its colour for nothing. `fillCode` builds the rows
  on screen between two spacers; a redraw costs 5 ms. **Below that length
  nothing changes**, so an ordinary file keeps the browser's own find and a
  copy of the whole thing, and the page says which of the two you got.
- **On the Files tab the pane scrolls sideways, not the rows.** A scroller on
  `.dlines` put the horizontal bar under the last line of the file, where in a
  file of any length nobody ever scrolls to. The pane scrolls both ways, so the
  bar is at the bottom of the screen — and the place the reader had scrolled to
  carries over across a window move for free, because `.filescroll` is not
  rebuilt for a window move. **The Diff
  tab keeps its scroller on `.dlines`**, because it stacks many files in one
  pane and a bar at the bottom of the screen would belong to whichever block
  happened to be under it. The override sits beside `.dlines`, not behind
  `.filebody`, so the two are read together.
- **The file header stands outside the scroller.** `.filebody` is a flex
  column of two: `.where`, which does not move, and `.filescroll`, which
  does. The header used to be `position: sticky` inside the scroller, which
  keeps it in view but not out of the scrollbar's way — the bar ran the whole
  height of the pane, beside a line that never scrolls. Everything that
  scrolls the file scrolls `.filescroll`: `fillCode`, `lineTop`, `showLine`,
  and the place a redraw puts back.
- **`.filescroll` is built with the file, so a different file starts at its
  top.** The pane used to be the scroller and outlived the file in it, so the
  next file opened wherever the last one had been read to. `same` is the other
  half of that: it is what refuses to carry the old place over.
- **A tab's empty state is inset by whatever its body does not inset**, and
  that is a wart, not a design. The Review tab's body has padding, the Files
  tab's children have it, the Diff tab's body has none at all — a diff's rows
  run to the edge — so `.diffscroll > .empty` brings its own. Three spellings of
  one idea. One inset on `.empty` itself would be the mechanism; it is not
  done because two of the five empty states sit in `.content` rather than in a
  `*body` and would move with it. When a fourth spelling is needed, do that
  instead of adding one. A margin, not a padding, either way: the block has to
  move, and a padded box still starts at the edge.
- **Wrapping and windowing cannot both be on.** A windowed file's rows are a
  grid the scrollbar is read against, and a wrapped row is not one row tall.
  The CSS is what enforces it — `:not(.windowed)` — rather than a ternary in
  one function and a promise in two comments. The control being disabled is a
  courtesy on top of that.
- **How a file is drawn is the reader's, and lives in this browser.** Tab width
  and wrap are about this screen and these eyes, not about a session, so they
  go in `localStorage` like the theme — not a config option, which `PLAN.md`
  rules out anyway. Both live on the root element, so the cascade obeys them and **neither
  control rebuilds anything** — `redrawCode` clears the key that guards an
  open comment box, so a preference that redrew took half a written comment
  with it. `recallReading` checks the shape of what comes back.
- **`BIG_LINES` and `CODE_WHOLE` answer one question in two shapes** (PLAN
  4.8.3). The Diff tab closes a long file; the Files tab windows one. A diff
  stacks many files of differing height in one pane, so it has no grid for a
  scrollbar to be read against. Do not quietly make either into the other.
- **`CODE_H` is the row height in pixels and `.dlines` must set the same
  number.** A grid the scrollbar is read against cannot be `line-height: 1.65`.
  `.code.windowed .dlines` drops its padding for the same reason.
- **A slice of a file says which line it starts at.** `asLines(path, lines,
  from)` and `hunk.from`, which `walkHunks` reads when there is no `@@`
  header. A slice that thought it started at line one would anchor every
  comment in it to the wrong place.
- **Which file the pane holds is asked of the pane** (`pane.dataset.file`),
  never of the redraw key: `redrawCode` clears that key, so opening a comment
  box made the open file look like a new one — and in a windowed file that put
  the window back at the top, where the comment box it had just opened was not.
- **One renderer for a line, in `fillDiffFile`.** The Files tab, the Diff tab
  and an untracked file all go through it — `unifiedRow` and `pairRow` are
  its two shapes, and `putLineReview` is the one place either puts a `+`; a file being read is a hunk of
  `plain` lines. That is what makes a review work in both tabs — line 42 has
  the same anchor either way — and why there are not three ways to draw a line
  that drift apart.
- **The highlighter gets the whole file; `cutIntoLines` cuts the answer up.**
  A block comment or a long string only makes sense whole, so painting line by
  line gets them wrong. A span crossing a newline is closed and reopened on the
  next line. The cut walks the scrubbed fragment, never a string of HTML, and
  a line count that disagrees with the file paints nothing: colour on the wrong
  lines is worse than none.
- **Reading the open file asks git twice and `file` once — and two of those
  are remembered.** The Files tab polls every two seconds, so the answers that
  cannot have changed must not be asked again: `Files.root_of` holds where the
  worktree starts, `Files.language_of` holds what `file` said, keyed on the
  path with its mtime and size. **`is_listed` is never cached**: it is the
  check that git still offers this name, and a remembered yes would let a file
  be read after it was taken out of the tree.
- **What language is this? Three questions, most certain first** (PLAN 4.8.1):
  the name, then the shebang, then `file` on the daemon — asked only when the
  first two came up empty, so a suffix never pays for a subprocess. `file` is
  the third and last command this program runs, after git and tmux.
  Its answers come from `BY_MIME`, a list, not wholesale. **`text/x-c` is not
  on that list**: libmagic uses it for anything C-shaped and calls Rust and Go
  C source, measured. No paint beats a wrong one, and nothing here guesses from
  content beyond that list.
- **A fill must not depend on how tall a row turns out to be.** The chosen row
  used `box-shadow: inset 0 0 0 40px`, which fills inward from each edge, so a
  row with a name, a branch and a reason on it had an untinted stripe down its
  middle. A `linear-gradient` background layer covers any height and sits over
  the state's own colour instead of replacing it.
- **What the row says a session is, is where it started, not where it
  stands.** `cwd` is in every hook payload and Claude Code moves it the
  moment the agent changes directory, so a row reading `repo/dir` renamed
  itself to `repo/src` mid-turn — and the worktree is the one fact on that
  row you cannot read anywhere else on the page. `Session.home` is stamped by
  `SessionStart`, because a resumed session really does start somewhere else,
  and otherwise only while nothing is known yet. `Session.place` is the one
  spelling of the question, and the row, the label and `sort_sessions`'s
  tiebreaker all go through it — three call sites built the same string by
  hand before, which is three chances for one of them to answer differently.
  `cwd` is still what git, the Files tab and the Diff tab are asked about:
  it is where the agent is, which is the right question for those.
- **A session with no pid cannot be checked.** `agent_pid` returns 0 where there
  is no `/proc` — on macOS, always. Such a session is taken for gone after
  `QUIET_MAX`. One with a pid is never buried for being quiet.

### The sidebar

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
  The worktree is the tiebreaker only. Sorting on `label` is still wrong, for
  the reason it always was: the name arrives from the status line a second
  after the session starts, and `/rename` changes it later.
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
  not. `alertsWanted()` holds both, in `localStorage` like the theme, and
  checks the shape of what comes back — storage survives across versions and
  anything can be in it. The older single key is read once so a reader who
  had alerts on keeps them. **Needs-you is on the moment alerts are**: it is
  what this tool exists to say, so a browser that has already granted
  permission and stored nothing gets it without asking.
- **"Finished" is a change, not a state.** `done` is where a session sits
  between turns, so a rule reading the state would say it again on every
  push. `wasDoing` holds what each session was doing last pass, and it is
  written **on every pass whatever the switches say**: ticking the box while
  an agent is working still tells you when it stops, and a session that
  reached `done` while nobody was listening is already at `done` rather than
  a change waiting to be announced. `waiting` is the same promise for amber.
  A test that only turns the switch on *after* a turn ends proves neither —
  it passes with the recording moved inside the switch. The one that bites
  ticks the box mid-turn.
- **The counts are about every session.** `drawCounts` runs *before* the guard
  that asks whether the shown rows changed — behind it, a session the filter
  hides could go amber and reach the title, icon and notification: none of them.
- **Rows are kept and filled in again, never rebuilt.** A dot can only fade if it
  is the same dot, and the needs-you ring can only finish a cycle if its row
  outlives the change. `newRow` builds every part once, empty; `fillRow` reaches
  them by position; a row moves only when its place changed, because
  `appendChild` on an attached node is a remove and an insert.

### Tab state

- **A session remembers the choices, never the caches.** `savePlace` and
  `usePlace`, into `state.visits` by session id: the tab, the open file and
  the place in it, the directories opened by hand, the expanded tool blocks
  and diff files. Not the listing, the text or the diff — those are fetched
  again, because by the time the reader comes back they have moved, and they
  are also the big things: 52,799 names is 1.7 MB, per session. **Not
  `places`** — `state.files.places` is the list of things to go to, and one
  word for two ideas is how one of them gets shadowed.
- **`usePlace` writes onto a state that has just been blanked**, so every
  field it sets is one `blankFiles` already has. A session never visited keeps
  the blank. The two lists are named by hand and
  `test_what_a_session_keeps_is_what_comes_back` is what stops them drifting:
  a field saved and not put back is silent, and reads as the feature
  half-working.
- **`state.files.down` has one writer, and it is *this session's*
  scrollbar.** The `.filescroll` listener writes it as the reader moves, so
  `savePlace` reads a field and never asks the DOM. It used to ask, and so did
  `showTab` — and `choose` restores the place and *then* changes the tab, so
  `showTab`'s query found the outgoing session's pane and wrote its place over
  the one just restored. `drawFiles` puts the place back only once there is
  something under the bar: the first draw after a session is chosen has no
  text yet, and scrolling to nought there would be written straight back as
  the place. **And the listener knows whose pane it is on**: `.filescroll` is
  built for one session and outlives the moment another is chosen — leaving
  the Files tab does not rebuild it — so a scroll event still queued when
  `choose` runs arrives *after* `usePlace` and writes the old session's number
  over the new one's. It captures `state.chosen` where it is attached and
  writes nothing once that has moved. This only ever happens by itself on a
  loaded machine, so
  `test_a_scroll_left_over_from_another_session_is_not_its_place` dispatches
  the event on purpose rather than waiting for one.
- **A tab's state lives under its own name**, `state.files` and
  `state.turns`, each with one `blank…()` that builds an empty one. Choosing a session is then
  `state.files = blankFiles()` rather than eleven assignments that could
  forget the twelfth. **A new tab gets the same shape from the start**: the
  flat bag this came out of grew fifteen names in one scope for the Files tab
  alone, and nothing said which tab owned any of them.
- The shared chrome — `sessions`, `chosen`, `tab`, `find`, `pick`, `history`,
  `skew`, `open`, `stream` — stays flat. It belongs to no tab.
- The Diff tab's own fields are still flat. They move when something touches
  them anyway, not as churn of their own.

### The worktree tabs

- **Work from the worktree root, not the agent's directory.** git reports
  root-relative paths whatever directory it ran in. `worktree_root` answers this.
- **Inside a hunk, the first character of a line is the only thing that matters.**
  Removing `-- a comment` writes `--- a comment`; read as a header it renamed the
  file and swallowed the hunk. Only `diff --git` and `@@` may start something new.
- **Split a diff on `\n`, never with `splitlines()`.** It also breaks on a form
  feed, a vertical tab, `\x1c`-`\x1e` and `\u0085`, all legal inside a source
  line and none of them escaped by git — it only quotes paths. One form feed
  put every later line in the hunk one number too high, so the two tabs
  disagreed and a review comment anchored to a line nobody commented on.
- **A path out of a diff may be quoted, and must be unquoted.**
  `core.quotePath=false` only covers bytes above 0x80; a quote, a backslash or
  a control character is escaped whatever it says, and the `a/` prefix goes
  inside the quotes. `we"ird.txt` came out mangled, a plain edit read as a
  rename, and the name did not match what `ls-files -z` gives the Files tab —
  so one line had two anchors. `unquote_path` is the one place that undoes it.
- **A cut goes back to the last newline, and the cap counts bytes.** A cut
  inside a `diff --git` line parsed as a file that does not exist, reported as
  a rename. `run` returns text, so a cap on `len()` counts code points and let
  a four-byte-character diff through at four times the size, while
  `FILE_MAX_BYTES` measures real bytes.
- **List every file, stat only the changed ones.** Tens of thousands of files,
  tens of changed ones. Asking the disk about all of them every poll is the
  mistake.
- **A wholly-ignored directory is walked by us, with a budget.** git's
  `--directory` collapses one into a single entry and looks no further, and
  dropping that entry left `.oa-implement` — a directory an agent writes its
  plan into, which is the one ignored place a reader wants — with no way in
  at all. `walk_ignored` lists it **only when what it holds fits in
  `IGNORED_MAX`**, counting what is under it and not counting a folder
  already left out, and it stops reading the moment it knows. So a build root
  of a hundred thousand objects costs 2,000 reads, comes back as one name in
  `Worktree.skipped`, and the plan beside it is listed because what is left
  of the directory then fits. Nothing is ever half-listed: a folder comes back
  whole or comes back as its own name. `node_modules` fails the same test and
  stays one row, which is what git's own rule was protecting.
  **The budget is an argument, not a default read at import**, or a test
  would have to build two thousand files to reach it.
  A link to a directory is neither followed nor listed: following it is a way
  round the budget and into a loop, and it is not a file.
- **`skipped` is not in the listing's tag.** The tag is a hash of the names,
  and a build root that appears adds none — every file in it is left out. So
  the page rebuilds the tree when the names move **or** when `skipped` does,
  and `buildTree(names, skipped)` makes an empty folder for each one: a
  directory holding nothing is a directory nothing above would create, and a
  folder the reader cannot see is the same silence as one that says nothing.
  Its row carries `.toobig` and does not open — a folder that opens onto
  nothing reads as broken.
- **One listing per worktree, and the page holds the names.** `Files` keeps it
  for `LIST_FRESH` and serves a stale one while re-reading behind. Names go with
  a tag; a listing that has not moved answers without them — 1733 KB against
  0.2 KB. So **the order the names are sent in must depend only on which files
  exist**: `in_order` is pinned-then-name. Put a changed tier back into it and
  the tag moves on every save. The reader's order is the page's, in `dirFiles`.
- **An icon is measured against its box, not eyeballed.** `putIcon` draws
  into a `0 0 14 14` viewBox and an `svg` clips to its viewport, so a stroke
  -- 1.2 wide, reaching 0.6 past the line it is drawn on -- must end by 13.4.
  The page icon's bottom sat at 13.5 and lost its last tenth.
  `test_every_icon_fits_inside_its_box` measures every entry in `ICONS` with
  the page's own CSS. **And a shape that is not closed looks cut whether or
  not anything cut it**: `dirOpen` first ran the lid to x=12 and the floor to
  x=13 with nothing joining them, and read as a folder with its right side
  sliced off, although nothing was ever clipped. Draw it, look at it at 13 px,
  then measure it.
- **A folder row carries no triangle.** It stood where nothing stood on a
  file row, so a folder's name sat 9 px right of a file's at the same depth —
  and a file one level deeper lined up exactly with the folder above it, which
  is the one thing a tree must not do. `ICONS.dirOpen` says what the triangle
  said.
- **The list marks where the reader last went, `state.files.at`.** Not the
  open file: clicking a part of the path above a file that was already on
  screen scrolled nowhere and marked nothing, so the click read as broken.
  `at` is in the list's redraw key, or the mark does not move.
- **A path clipped at its start is a bidi trap.** `direction: rtl` puts the
  ellipsis at the front, which is what you want on a path — and moves a
  leading neutral character to the other end, so `.gitignore` drew as
  `gitignore.`. `unicode-bidi: plaintext` takes the direction from the first
  strong character instead. Never clip a path at its start without it.
- **The tree holds the tiers.** `dirFiles` orders each directory's own files —
  named, changed newest first, then the rest. `openDirs` opens a directory
  holding a change; `state.dirs` (what the reader opened by hand) wins over it.
- **Typing is "go to file", not a filter.** The tree never moves: where a file
  sits is half of what you know about it, and taking the tree apart was hiding
  that answer as a way of asking for it. `drawGoTo` opens a list under the
  box — files *and* directories, `pick`-ranked — and picking one opens it and
  reveals it. The list lives inside `.findslot` so `split`'s children keep
  their positions, and closing it clears its redraw key, or the same query
  typed twice matches the key and draws nothing.
- **A file is found by its name; the path is the fallback, and it must be
  tight.** `findPath` matches the basename first, then the whole path only when
  the matched letters span no more than `TIGHT` times the query length.
  Matching the whole path outright let "MetricsBuilder" land across 71
  characters and four directory names while missing the file meant. A slash in
  the query means you meant the path. `findPath` also forgives one letter of a
  five-plus query; `fuzzy` forgives none by default, because the session filter
  runs through it and a short haystack cannot afford it.
- **Search every name, or say you cannot.** Sending the first 5000 of 52,799 made
  a search find 16 files and miss a thousand: a wrong answer that looks right.
- **A git call that failed must not render as an empty answer.** "No files" and
  "git did not answer" look the same and mean opposite things. **Nor may a
  failure be remembered as one**: `Files.root_of` kept the empty string a
  timed-out `git rev-parse` returned, and one such moment left that worktree
  unreadable until the daemon was restarted. The same for `file`:
  `sniff_language` returns `None` for "it did not answer" and `""` for "it
  answered, and not with something we paint", and only the second is kept.
  `GitFacts.failed`, `Worktree.failed` and `DiffReport.failed` are how each
  answer says which it is; `reload_git` puts a failed directory back on the
  list rather than over what it already knew.
- **`run` gives None for "the command failed" and for "it could not run".**
  Outside a repository git *fails*, so an empty answer is not by itself a
  failure. Two ways to tell them apart: another call that already worked on
  the same directory (`git_facts` knows it is a repository because
  `rev-parse` answered), or `git_answers()`, which asks `git --version` — it
  cannot fail inside a working git, and stalls on the same stalled machine.
  Only in the failure path, so a repository never pays for it.
- **The Diff tab says what each half is a diff of, in words.** The headings
  were `origin/main...HEAD` and "not committed yet" — precise, and readable
  only if you already know what three dots mean, so nobody could tell whether
  the tab showed the last commit, the branch, the worktree, or some of each.
  `DiffSection.about` carries the sentence, the daemon builds it with the base
  named in it, the pane draws it under the heading and the list carries it as
  a `title`. **And when there is no base the committed half is missing
  altogether**, which used to look like a tab that simply had less in it: the
  pane says so, and names what git was asked for.
- **A commit the page names is used only if `branch_commits` listed it.**
  The sha arrives in `?of=` and the page is input, so `worktree_diff` looks
  it up in its own list and hands git the listed one, never the string it
  was sent. One that is not there — an agent amended or rebased — comes back
  as `gone` with all changes, and the pane says why.
  `test_a_commit_the_page_names_is_used_only_if_git_listed_it` sends
  `--output=` and `HEAD~1` and asserts neither reaches an argv.
- **One commit's comments go through `since`, as the committed half's go
  through the uncommitted one.** The commit's new side is that commit, not
  the disk, so its line numbers are not the file's. `since` is `git diff
  <sha> -- <its files>` and `inWorktree` reads it when a commit is shown.
  Only the commit's own files: the diff to the disk of a whole repository is
  what every later commit cost. Drop it and a comment on `print(2)` anchors
  to line 2 when fifty lines stand above it — the scar the committed half
  already had.
- **The picker is built once with the pane, and refilled only when the
  commits change.** A `select` whose options are replaced closes if it is
  open, and the tab polls every five seconds. `fresh(bar, "key", …)` guards
  it. Picking and the column switch both rebuild the diff, so both refuse
  while a comment box is open and say so (`busyWriting`) — a rebuild takes
  what is typed, and a switch that silently did nothing reads as broken.
- **The pane reads in the tree's order, not git's.** `treeOrder` puts
  folders first at every level, and both the list and the pane go through
  it, so the two read the same way down. git's order is plain path order,
  which put `README.md` above `src/a.py` in the pane and below it in the
  tree.
- **The file clicked in the tree keeps the mark while it is on screen.**
  `markDiffFile` marks the block under the top of the pane, and the last
  file of a diff can never scroll to the top — there is nothing under it —
  so a click on it marked the file above. `scroll.picked` wins until it
  leaves the screen.
- **A diff is painted one side of one hunk at a time, and the word marks go
  back on after.** Each side of a hunk is text that makes sense in order;
  the whole file is not available here, and a row on its own gets every
  multi-line string wrong. Painting replaces what a cell holds, so
  `paintDiff` calls `markWords` again from `cell.words`. Take that out and
  the marks go the moment the colour arrives, which nothing but
  `test_the_diff_is_painted_and_keeps_its_word_marks` would notice offline.
- **Lines hidden between changes come from the same diff with the whole
  file as context, never from reading the file.** `whole_file_diff` is the
  section's own `git diff` with `-U1000000` and the path as a literal
  pathspec after `--`, so the lines are the side the half shows — HEAD for
  the branch's work, the commit for one commit, the disk for what is not
  committed — and the section picks its arguments from three fixed ones.
  Reading the file from disk would put the disk's lines into the committed
  half, which is HEAD's. A commit is used only when `branch_commits` lists
  it, as everywhere else. `test_a_whole_file_is_every_line_of_the_side_the_half_shows`.
- **What the reader revealed is kept as line numbers, and the whole file
  against the hunks it came with.** `state.diffMore` holds `[from, to]`
  runs by `moreKey` — what is shown, the half, the path — because one
  commit's line 40 is not another's. `state.diffWhole` keeps each whole file
  with `hunkSig` of the diff it belongs to, and `withMore` drops it the
  moment the hunks move: the agent saves, and a kept file would put old
  lines between new changes. `test_shown_lines_come_again_from_the_file_as_it_now_is`.
- **Every diff asks git for `-U3` out loud.** The page reads fewer than
  three lines after the last change as the end of the file and offers no
  more below it; a reader's `diff.context` would move that line and hide
  the offer on every file. `DIFF_CONTEXT` is the number on both sides.
- **A diff stands on `--sheet`, not on `--code`, and it is white in the
  light.** Its file header stands on it too: a colour of its own, darker
  than the code, read as a bar rather than the top of the file. On the code ground, `#eceae3`, an unchanged line stood at a
  contrast of 4.29 — under the 4.5 body text needs — and the card read as a
  brown box darker than the page around it. `--code` stays what it is for a
  code block inside prose. `test_a_diff_in_the_light_is_on_white_and_reads`.
- **A commit picked shows its whole message, and only that commit's is
  asked for.** `DiffReport.body` is `git show -s --format=%b` for the one
  commit shown, not a field of every `Commit`: a hundred bodies on every
  poll would be sent for the one being read. It is drawn `pre-wrap` in the
  fixed face, because a git body is wrapped by hand.
- **Two columns wrap; one column scrolls.** A pair of halves cannot share a
  sideways scrollbar, and two bars drift apart, so `.dlines.sides` hides the
  overflow and the halves wrap. The `+` is on the new half only — a comment
  is about the file as it is — and a side with no line is hatched, not
  closed up, so the columns stay level.
- **The two changed-file counts are about different things, and stay that
  way.** The sidebar's comes from `git status` in git's default untracked
  mode, which collapses a wholly-untracked directory into one entry; the
  Files tab dots each name, from `--untracked-files=all`. So five new files in
  a new directory read as "1 file" beside five dots. The cheap call is on the
  tick thread under a two second timeout, and the thorough one is not — that
  is the reason, and it is worth more than the two numbers agreeing.
- **A split tab keeps its two columns and redraws one at a time.** `split()`
  builds them once, `fresh()` decides what changed, both reading the DOM. One key
  over the whole tab re-rendered the file you were reading every two seconds.
- **`.listnote` is one clipped line.** Anything with height goes in the `sidefoot`
  slot. A button put in the count strip could not be clicked at all.
- **`drawLooseFile` builds a synthetic file object.** Everything `fillDiffFile`
  reads must be in it. `path` was missing, so every untracked file's comments
  anchored to `undefined`.

### The review

- **A comment is anchored to what it is about** — the path and the line, with
  nought for the whole file — never to the node it was drawn on. The Diff tab is rebuilt from `state.diff` whenever the
  agent saves anything.
- **A comment is a place in a file, not a place in a diff.** There is no
  "gone" or "moved": the page used to work those out and send them as though
  the reader had written them, so a note on a file the agent never touched
  went out saying "this line is no longer in the diff". The message tells the
  agent to search for the quoted line instead.
- **A goTo is a place, not a path.** `state.files.goTo` moves the list to a
  file and `state.files.goToLine` moves the body to a line in it. A windowed
  file is arithmetic (`lineTop`, through `heightOf` — a commented line is
  taller than a row, and assuming otherwise landed the target off screen), a
  file drawn whole scrolls to the row, and a document is switched to its
  lines — it has no line 4 to go to otherwise.
- **The Review tab is the only place a review is sent from**, and the message
  stands above the send button, not editable. `drawReview` is the tab,
  `reviewText` is the message, `blankReview` is an empty one.
- **A removed diff line gets no `+`.** It has no line in the file as it is, so
  there is nowhere for the comment to be drawn and nowhere to put it back. The
  anchor used to carry a side for this, and a comment on a removed line could
  not be shown on the Files tab at all — but was still sent.
- **The committed section's new side is HEAD, not the worktree.** `base...HEAD`
  stops at the last commit, so its line numbers are not the file's. A comment
  there is carried through the uncommitted section — which is exactly the map
  from HEAD to disk — by `inWorktree`, and a line that is no longer on disk
  gets no `+`, like a removed one. Anchoring to HEAD's number was wrong at the
  moment of writing, not because the file moved afterwards.
- **One comment, drawn one way.** `putComment` builds it everywhere; the
  Review tab passes `full`, which adds the quoted line — there is no code
  above it there — and the delete button, which only that tab offers. The
  Review tab used to reach into the node it got back and append both, so the
  two drifted. Its buttons go in `.acts`, at the right edge, out of the note's
  way; the comment box's own go under the field, at the same edge.
- **One anchor, one comment box.** A file in both sections shows the same line
  twice. Two boxes meant the later `focus()` took the keystrokes to a box off
  screen, and saving the visible one passed an empty note — which means
  delete, so the comment was lost in silence.
- **`state.writing` must not outlive its box.** It is cleared when the file or
  the tab it was on goes away, and the guards ask the DOM (`writingIn`) rather
  than the flag: a box open on another tab froze a tab that had nothing on
  screen to close.
- **What the reader opened lives outside the node.** `state.diffOpen`, like the
  transcript's `state.open`. A `let open` inside `drawDiffFile` was thrown away
  on every rebuild, so a big file snapped shut each time the agent saved.
- **An async answer belongs to the session that asked.** `submitReview` blanked
  whatever review was current when `tmux send-keys` returned, and removed its
  key from storage. The sent review is cleared by its own id.
- **The Session tab is where everything about one session lives**, and the
  only place it is named. There was a bar over every tab saying the branch,
  the pane, the model and the state — three of which the chosen row says one
  column to the left, at a cost of 56 pixels on every tab. What it said that
  the row does not is in the tab: the whole path, the context bar, the counts,
  and the session's own event log. `drawHeader` is what is left, and all it
  does now is the send box.
- **The name box is built once and the rest is rebuilt around it.**
  `drawSession` keeps two children for this reason: the panel is polled, and a
  rebuild under a box being typed in takes what is in it — the rule the review
  keeps for its comments, in a second place.
- **A tab that fetches nothing says `load: null`**, and the shared `load()`
  draws for it. A tab switch goes through `load`, not `draw`, so an empty
  loader left the page showing the tab before.
- **The diff does not rebuild while a comment box is open.** It would take what
  is being typed with it, and move the code the comment is about.
- **The draft lives in the browser.** A review is yours until you submit it, and
  the daemon serves every browser the same page. `recallReview` checks the shape
  of what comes back: storage is not a place to trust blindly.
- **The preview cannot be skipped**, and it is not editable. A quoted line is
  text an agent wrote, about to be pasted into a terminal. One text, one place it
  comes from.

### The daemon and the page

- **Every route lives in `Serving`**, a module-level class that subclasses
  nothing. `make_server` mixes it with `BaseHTTPRequestHandler` and puts the
  daemon on that subclass, so a route reads `self.daemon`. The `http.server`
  import stays inside `make_server`: 10.8 ms for a bare interpreter against
  49.5 ms for one that has imported it, and **the hook pays for every import
  on every tool call**. `test_the_hook_does_not_import_what_it_does_not_need`
  fails if that slips.
- **`name` is a POST that writes no terminal.** It keeps a name in
  `names.json` and wins over the one the status line sent, because Claude Code
  hands the status line the name the session started with and `/rename` does
  not change it. `Store.rename` replaces the whole map rather than editing it,
  the trick `rows` plays: the HTTP thread writes, the fold thread reads. It
  pushes nothing — the rows are built from the names every pass, so the next
  one differs and goes out on its own.
- **Never write to the terminal** except through the two tmux verbs.
  `tmux_jump` and `tmux_send` look `run` up when called rather than
  taking it as a default, so a test can put a fake tmux in its place.
- **The Files and Diff tabs poll from the browser, and only while on screen.**
  `TABS` holds one entry per tab — draw, load, interval — so a new tab is one
  entry, not six edits. The daemon pushes the transcript and nothing else; it
  does not know which tab a browser is on, and that is why `Hub` stays small.
- **One lock around the transcript readers.** Two `read_new` calls at once move
  the byte offset twice, which looks like a shrinking file.
- **There is one find box, and it must leave before its parent is cleared.** On a
  split tab it lives inside the content box, so a tab that empties that box
  destroys it and `$("find")` is null — `showTab` then throws before `load` and
  the page is broken until a reload. `draw()` takes it home when
  `box.dataset.tab` says another tab owns the box; `split()` takes it back. Two
  outages; `test_every_way_from_one_tab_to_another_works` watches for a third.
- **Ask the box which tab it holds, not `state.tab`.** `showTab` sets the name
  and then awaits `load()`, and for that whole await the box still holds the
  tab before it. A transcript push landing in the gap appended a turn as a
  fourth column of the Files tab. `draw()` had this right already.
- **A link to a turn is `#<session>/<seq>`, and `seq` is a place in one
  reading.** A session resumed from another directory counts from nought
  again, so an old link can name a turn that is no longer there. `landOnBlock`
  does nothing then, and that is the whole of the failure. It also wins over
  the usual landing at the foot of the transcript exactly once: `state.goToBlock`
  is cleared the moment it lands, or a live session would drag the reader back
  to it every second.
- **A session can be chosen before the session list exists.** The address bar
  holds a link at startup, so `choose` runs with `state.sessions` empty —
  `current()` is null and every tab draws its empty state. The `sessions`
  event draws again when the chosen session turns out to be real; without
  that, a linked page stayed empty until the reader clicked a row.
- **A `user` record is not always a prompt.** Claude Code writes its own:
  one `/reload-plugins` arrives as three or four records of tags, and
  `(no content)` was drawn as something the reader had typed.
  `read_user_text` reads one for what it is — a command becomes one line
  saying what was run, its output and the resumed-session caveat are
  dropped, and a task notification or another session's message becomes a
  `note`, which is shown but never wears the reader's rail. **A record is
  only read as a command when there is nothing else on it**: a prompt really
  can hold `<command-name>` in it, because somebody asking about this very
  feature types one.
- **A message sent to a busy agent comes back wrapped, and the wrapper is not
  yours.** Claude Code queues it into the running turn and writes a header
  (`The user sent a new message while you were working:`), the words typed,
  and a footer explaining the queueing to the agent -- all inside a
  `<system-reminder>`. It is a `user` record, so all three were drawn as the
  reader's own prompt, and the map named the round after the header. This is
  the shape a reader of *this* program meets most, because every message this
  page sends to a working agent takes it. `QUEUED` keeps the middle.
  **Order matters**: the reminder tags come off first (`strip_reminder`), and
  the message is pulled out *before* `MACHINE_TAG` runs -- `system-reminder`
  is on that list now, so stripping first would take the message with it.
  The header must open the record and the footer must be there, or a person
  quoting the wrapper to ask about it -- which is how this was reported --
  gets their question answered with its own quotation.
- **Pasted text comes off Claude Code's paste tags, by Claude Code's own
  rules.** A Claude Code that keeps a paste apart from what was typed writes
  it into the record after the typed text as two newlines,
  `<pasted_content id="1da8">`, the text, and `</pasted_content id="1da8">`
  -- and its own screen takes them off again. This page drew them, so every
  review sent from here came back as a block of tags under two empty lines,
  and the map named the round after the tag: a review has newlines, so it
  is always a paste. `unwrap_pastes` is a port of the reader in its bundle
  (`Pct`): four lowercase hex digits, the same on both tags, each tag on its
  own line, up to two newlines either side belonging to the wrapper, and
  anything else left as typed -- a person asking about the tag types one.
  It runs first in `read_user_text`, so a paste inside a queued message
  comes off too. Measured on 2.1.281, which does not wrap on this machine:
  a feature switch decides, so the shape comes from its source and the
  reader's record, not from a run here.
- **A `note` is neither a round nor a reply.** `rounds()` takes prompts and
  the agent's text and nothing else, so the map stays a map of the
  conversation.
- **A `.turn` lays out from the top, not stretched.** `.who` carries a name,
  a day, a time and a copy button — 71 px of them, measured — and a flex item
  stretches to its row by default, so a one-line bubble was 71 px tall with
  the text 14 px from the top and 41 px of nothing under it. It read as text
  that is not centred; it was a block that is not the size of its contents.
  `align-items: flex-start` on `.turn` is the whole fix, and
  `test_a_one_line_message_sits_in_the_middle_of_its_block` compares the two
  gaps rather than either number.
- **A group of tool calls belongs to the words above it.** The agent says
  what it is about to do and then does it. The gaps were 16 px above and
  16 px below — exactly equal, measured — so the group read as belonging to
  neither, and to the reply below it, which is the thing you next want to
  read. They are 6 and 22 now. **The numbers in the CSS are not the gaps**:
  the margins collapse against `.turn`'s own 22, so above is 22 + (−16) and
  below is max(5, 22). Change one and measure it; do not read it off.
- **A hidden thinking block is still a sibling.** `display: none` takes it
  off the screen and not out of `+`. An agent thinks between two calls, and
  between saying what it will do and doing it. With `+` alone, a call after
  a thought was pulled up 16 px onto the call above it. The first fix only
  looked at the thought, and put a call 22 px under the words it belonged
  to. The block that decides is the one *before* the thought, and CSS cannot
  find it: `pastThought` does, and `blockNode` marks each turn `past-tool` or
  `past-words`. With thinking hidden the CSS reads those classes; with it
  shown, `+` is right, because the thought is then the block before. A
  wrapper per run of calls would not help: the thoughts stand between the
  calls. `test_hidden_thinking_between_two_tool_calls_does_not_stack_them`
  measures the gaps in both modes, and each of the four rules fails it.
- **Measure a gap from what the reader sees, not from the box.** Three
  rounds of this fix measured turn box to turn box, got 6 px each time, and
  the reader still saw 39. `.who` — a name, a time, the copy button, and a
  day when it was not today — was 55 px on one day and 71 across two, and
  one line of text is 22, so the column set the height of every one-line
  turn.
  When a call comes next, the column may run down beside it: the call's own
  `.who` is empty. `next-tool` says so while thoughts are hidden, and
  `markNext` sets it again on the block before when a block arrives, because
  that answer looks forward and a later push changes it. The overhang is
  capped at 36 px, which is what one call and the gap after it can hold;
  more ran the column into the next turn's name. It carries `z-index`, or the
  calls — later, positioned siblings — cover the copy button. And a block
  sliding in is a stacking context for 0.15 s, so a test that measures
  straight after a push waits for `document.getAnimations()` to be empty.
  `test_a_group_of_calls_sits_under_the_line_that_announced_it` measures from
  the text, and each of its five parts fails it.
- **The copy button stands on the time's line, and a column may hang 10 px
  past its turn.** On a line of its own the button made `.who` 55 px tall,
  taller than a line of text (22) or a prompt's bubble (45), so the gap a
  reader saw was 32 px after a prompt and 59 after a one-line reply before
  a prompt, where 22 and 26 were meant. `.who .stamp` holds the time and the
  button; the column is 35 px now, 51 with a day. What is still past the
  words hangs into the gap: 10 px, because the rule over the next prompt is
  12 px down (its `::before`, 26 − 14) and the next turn's name 25. More
  than that runs the column into the rule. `next-tool` allows 36 where a
  call comes next, whose column is empty.
  `test_the_gap_a_reader_sees_after_a_prompt_or_a_line_is_the_gap_meant`
  measures from the bubble and the text, and fails with the button back on
  its own line or with a larger overhang.
- **The send box and the question bar start where the transcript does, and
  the map runs down beside them.** Both stand under a split tab's right
  half, and both used to run the whole width and under the map beside it — a
  column you never type into. A `margin-left` fixed that and left the map
  and its grip stopping short above them, with an empty corner under the map
  that nothing could drag. Now `.main` is a grid whose columns are the split
  tab's own — `--side-w`, `--grip-w`, the rest. `.content` spans every row
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
- **The way back to the end of the transcript hangs off the content box, and
  `split` builds it.** A new block carries you along only while `nearBottom`,
  which is right, and nothing said how to start following again. `.tofoot`
  cannot live inside `.turnbody`, whose children `drawTranscript` replaces
  wholesale, so it is a child of the box — built by `split`, like every other
  part of the frame, because building it in `drawTranscript` put half of the
  box's positional contract in another function. **That is why `split`
  returns `box.children[2]` and not `box.lastChild`**: the last child is this
  button. It is a `.verb`, which is where its height, padding, border,
  background, type and hover come from; `.tofoot` holds only what makes it
  float, and needs no `[hidden]` rule because `.verb` sets no `display`.
- **`showToFoot` is handed both nodes, and this is not a nicety.** It runs on
  every scroll event — dozens of times in one gesture — and on every pushed
  block. `box.querySelector(".tofoot")` is a pre-order walk that reaches the
  button only after crossing the whole transcript: on a long one, a hundred
  thousand nodes visited to set one boolean. Every caller already holds the
  button and the pane.
- **`GLIMPSE` is not where the map's preview ends.** `.filelist .name` clips
  with an ellipsis at whatever width the column has been dragged to;
  `GLIMPSE` only bounds what goes into the DOM for a reply that may be
  kilobytes long. It was 44, narrower than the column at its default width,
  so every row ended in a "…" the column had room for and the number did not.
  **It has to clear what the widest possible column can show**, or it is the
  clip again. Measured at `dragWidth`'s cap of 700 px, where the name box is
  639 px: 49 of the widest glyphs and 176 of the narrowest. The list was a
  condensed sans, so the thin end sets it — a number reasoned out from
  monospace character widths came to 120 and would have clipped a line of
  narrow letters, which is the bug being fixed. Measure it; do not divide.
  The map now wears the transcript's face at 14 px, which is wider in every
  glyph, so the measurement still holds; a narrower face would not.
- **The map is set like the transcript beside it.** The same face, size and
  line height as `.prose`, and 1 px above and below a row, so a row comes
  about every line. It had the file lists' condensed face at 13 px and a row
  every 29 px, and read as a different page. The file lists keep the
  condensed face, because a path wants the width.
  `test_the_map_is_set_like_the_transcript_and_a_prompt_is_round` compares
  the computed styles, not the numbers, so a change to the transcript's type
  carries the map with it or fails.
- **A round on the map folds from its icon, and only from its icon.** The row
  has two jobs: the whole of it goes to that place in the transcript, which is
  what the map is for, and the icon alone folds. Folding on any click would
  mean you could not read a round without closing it. `state.turns.shut` is
  in `drawTurnList`'s redraw key — the shape of the conversation has not
  changed when you fold one, only what is shown of it, so without it a click
  redraws nothing — and in `savePlace`/`usePlace`, because it is a choice.
  **A second target on a row has to say so**: nothing else in this list has
  two, so the round carries `aria-expanded` and the icon its own `title`, and
  the icon alone changes colour under the pointer. It carries no `cursor`,
  because the row is a button and already sets one. There is no keyboard
  route to folding yet, and that is a gap, not a decision.
- **Everything keyed on `seq` is forgotten together, in `forgetPlaces`.**
  `seq` is a place in one reading, not an identity, so a transcript rewritten
  under its own name leaves `state.turns.open`, `state.turns.shut` and
  `state.turns.at` all pointing at different blocks. Two of those were wrong
  before the third was added, which is the moment to give them one place.
  **`run` is therefore one of the things a session keeps**: `usePlace` putting
  the choices back without the reading they belong to would make every return
  to a session look like a rewrite. And the forgetting is guarded on
  `run !== -1` — "none held yet" is every first load, and `goTo` is set from
  the address bar before that load, so forgetting there threw away the link
  the page had just been opened on.
- **`t` says what it did.** The key worked from the day it shipped and read
  as broken anyway: most transcripts hold no thinking at all, so pressing it
  changed nothing on screen and nothing said why. A key whose effect can be
  invisible has to use the live slot; `toggleThinking` counts the blocks and
  says so, including when there are none.
- **`t` never moves the reader.** The pane kept its scroll offset in pixels
  while thoughts came and went above it, so three looks at one place showed
  reply 21, thought 6 and reply 5 — and the reader took it for a switch that
  showed some messages and then others. `toggleThinking` notes the first
  block in view that is not a thought, and where it stood, and puts it back
  there; a reader at the foot stays at the foot.
  `test_showing_the_thoughts_keeps_the_reader_where_they_were` does both.
- **A row of a list is one line, and `.filelist button` is a block.** A
  list whose rows are one line says so in the one rule that groups them —
  `.fixed` for the file tree, `.diff` for the Diff tab's tree, `.transcript`
  for the map. Without it the icon sits on a line of its own above the text,
  which is how the map first shipped. The Diff tab's tree was a third copy
  of the rule before it joined the group; a fourth list joins it too.
- **The find box narrows the list, never the transcript.** Taking turns out
  of the transcript took the conversation around a hit with them, which is
  what you were reading it for. `shownRounds` filters the left bar;
  `markHits` still marks what matched where it stands, because a hit you
  scroll past unmarked is a hit you miss.
- **`drawTranscript` has no redraw key, on purpose.** The live path is
  `patchTranscript`, which appends. Getting to a full draw means a tab
  switch, a session, or a keystroke in the find box, and every one of those
  really does want the blocks built again. A key there would also leave an
  arriving block's `fresh` class on it for ever: drawing a block again is not
  the block arriving again, and
  `test_only_a_block_that_has_just_arrived_slides_in` says so.
- **`state.turns.down` is read before the pane is emptied.**
  `replaceChildren` puts the scrollbar back to nought and the scroll listener
  would write that down as the place the reader was. The listener is attached
  once per pane, guarded by `pane.dataset.watched`, because `drawTranscript`
  runs many times over one pane and `split` only rebuilds it on a tab change.
- **The search redraws the whole tab, so it has to put the reader back.**
  `drawTranscript` ends at the foot of the transcript, which is where a
  session with no kept place belongs — the last thing the agent said is the
  thing you came for.
- **One block redrawn on its own still has to be marked.** `redrawBlock` is the
  Transcript tab's `fillDiffFile`: everything `drawTranscript` does to a node
  it must do too, or the block you touched loses what the others keep.
- **A scrollbar is the browser's, so the page has to tell it which way round
  it is.** Without `color-scheme` a dark page carried the system's bright bar
  down every column — measured: `color-scheme: normal` and
  `scrollbar-color: auto` in both themes. Both properties are set and both
  are needed: `scrollbar-color` is the exact hue, taken from the same
  `--edge-bright` every other edge on this page uses and with a transparent
  track so it shows what it lies on; `color-scheme` is what a browser that
  ignores the first falls back to, and it is also what puts the form controls
  right — the search box's clear button, the send box's own bar.
  `scrollbar-color` is inherited, so `:root` is the only place it is said.
- **A tab that cannot use the find box does not show one**, and `TABS.finds`
  is where that lives — the placeholder was a ternary in `showTab` naming
  three tabs, so the two it did not name got whatever the last arm said, and
  the Session tab offered "find a file" for a list it does not have. One
  entry per tab, like `draw`, `load` and `poll`. **`.findhome` needs
  `[hidden] { display: none }`** for the reason `.sendbar` does — it sets
  `display: flex`, which beats the browser's own rule for the attribute —
  and that is the third time this shape has caught something here. Its
  `margin-left: auto` is also what pushes the live slot to the far end of the
  tab bar, so `.findhome[hidden] + .live` takes that over or the slot comes
  to rest against the last tab.
- **A class the page puts on `body` is never the class an element wears.**
  `stream.onerror` did `classList.add("lost")`, and the rule hiding the bar
  until it was wanted was `.lost { display: none }` — which `body` then
  matched itself. **The whole page went to `display: none` the moment the
  stream hiccupped**, and came back when it reconnected or when the reader
  pressed F5, so from the outside it read as a page that had simply stopped
  working. The states are `offline` and `outdated` now; the bars stay `.lost`
  and `.stale`. `test_no_state_on_the_body_can_make_the_page_vanish` names
  every state the page sets and asserts the page is still there under each,
  and under all of them at once — a new state belongs in that list.
- **A restarted `serve` leaves every open page dead, and only the page can
  say so.** The token is made fresh in `Daemon.__init__` and printed into
  the page, so a restart leaves every browser holding one this daemon has
  never heard of. The stream is a GET and reconnects, so the sidebar goes on
  moving and the page looks alive while every send, every jump and every
  answered question is refused — in every session at once, because the token
  belongs to the daemon and not to a session. `stale_page()` picks the
  *wording* of a refusal `allowed()` has already made; it changes no
  decision, and a caller that fails `origin_ours` is told nothing it did not
  already know. The page raises a bar that only a reload clears, which is
  right anyway: after an upgrade its JavaScript is old too.
- **The strip carries what the session has spent, and says it is an
  estimate.** Claude Code works `cost.total_cost_usd` out on the client at
  list price, says it may differ from the bill, and resets it to nought on
  `/clear`. The caveat rides on the number as a `title`, because it is read
  once and the strip has no width for a sentence. `None` is "the status line
  did not say" and `0` is "it spent nothing": a session on an API key gets no
  `cost` at all, and `$0.00` for it would be a number nobody measured — so
  `drawContext` tests for null rather than defaulting. The rate-limit windows
  go in the Session tab instead, where there is room to name the window and
  when it resets; each is independently absent, and one that is missing is
  drawn as nothing, never as nought.
- **`money` is a name on both sides, and shadowing it is a `ReferenceError`.**
  `drawContext` calls the page's `money()` and then builds an element for what
  it returned. Naming that element `money` puts the call above it in the
  temporal dead zone — a page that throws on every draw, from a line that
  reads perfectly. Same scar as `matches` / `matching` / `hits`.
- **The context bar is its own slot, beside `#live` and never in it.**
  `paintLive` is the one writer of that slot and three things already want it
  — what the stream is doing, something you asked for and did not get, and a
  passing word over both. A fourth would be the race that rule was written
  after. `drawContext` is called from `drawHeader`, so it arrives with
  everything else a push carries and no fifth call site can forget it, and it
  redraws only when the number moves — the push is about once a second and
  the number is not. `putContext` builds it for the strip and for the Session
  tab, because they draw the same thing. A session whose status line is not
  registered has no `context_pct` and gets no bar: nought would read as an
  empty window rather than as no answer.
  **The model stands left of the bar**, because the percentage is a
  percentage of that model's window and `/model` changes it mid-session.
  It is part of the same redraw key. `tests/shot.py` writes a status line
  for its session, so a picture of the strip has all three in it.
  `test_the_model_stands_left_of_the_context_bar`.
- **A working stream says nothing.** The slot read "live" on every page all
  day. A reader can see the page moving, so the word told nobody anything,
  and a word that is always there is a word nobody reads — "reconnecting"
  in the same place went unseen too. `state.live` still holds "live";
  `paintLive` only does not paint it, so a test that wants to know the
  stream is up asks `state.live`, not the slot.
  `test_a_working_stream_says_nothing_and_a_lost_one_says_so` holds both
  halves.
- **`said` is the daemon's answer and it stays; `note` is our own word and it
  fades.** "Review sent" goes stale in four seconds. "That did not come from
  this page" is about something you asked for and did not get, and fading it
  left a strip reading "live" over a page where nothing worked — which is
  exactly how the restart above went unexplained.
- **One painter for the live slot, and three things that want it.**
  `state.live` is what the stream is doing, `state.trouble` is something you
  asked for and did not get, and `note` borrows the slot over both for four
  seconds. `paintLive` decides; nothing else assigns to `#live`. Four writers
  raced before it: the stream writes "live" on every push, about once a
  second while an agent works, so a failure written straight into the slot
  was wiped within a second — the thing the reader most needed to read was
  the thing that lasted least. **CI caught that**, not the browser tests I
  had just written: the assertion was three lines below a
  `wait_for_timeout(4500)` and passed locally because nothing was pushing.
- **No JavaScript library is vendored.** `marked` and `highlight.js` are fetched
  through the one `fetchScript`, each pinned by the hash of its bytes, with
  `crossorigin` so the browser checks it. Any script on this page can POST to
  `/send`. Each must degrade: without `marked` the transcript is its own source
  as text, without `highlight.js` code has no colour. Tests hold both fallbacks,
  and `tests/fixtures/marked.min.js` is what the page tests serve, so no test
  needs a network.
- **Motion** (PLAN 5.2): a dot fades on a state change, a *new* transcript block
  slides in 4 px, the needs-you ring pulses. Nothing else moves. "New" means
  arriving in `patchTranscript` — never a redraw. One `prefers-reduced-motion`
  block turns all of it off.

### Style

- Plain language in comments, `--help` and docs: short sentences, one idea each,
  active voice.
- Type hints everywhere. `dataclass` for models.
- Git and tmux go through `subprocess` with a short timeout, and an error there
  never crashes anything.
- A comment says *why*, especially why the obvious simpler thing is wrong. The
  long comments here are load-bearing; do not tidy them away.

## Do not guess payload fields

Hook and status line field names are in `tests/fixtures/README.md`. Need one
that is not there? Record a real payload and add it to `tests/fixtures/`. Do not
invent a name.

**The status line carries money, and this file used to say it did not.** The
payload has `cost.total_cost_usd`, `cost.total_duration_ms`,
`cost.total_api_duration_ms`, the lines added and removed, and
`rate_limits.five_hour` / `seven_day` / `spend_limit` with a used percentage
and a reset time. `PLAN.md` section 12 asserted the opposite for a while, and
an issue was closed down to one line on it. The assertion came from reading
`tests/fixtures/status.json`, which at the time had no `cost` in it — **one
fixture is one sample, and absence in it is not absence in the payload.** A
reader whose own status line showed the spend is what corrected it. When the
question is "does this payload carry X", the fixture can only say yes.

**Recording one does not mean committing your conversation.** Both fixtures
carry real field names in real shapes with invented text, because this
repository is public. Read a real payload, learn the shape, write the fixture.

**And read more than one machine.** "A compaction writes a `summary` record"
held for years and was false: 31 transcripts across three machines and two
builds hold not one. A current build writes a `system` record with
`subtype: "compact_boundary"`, then a `user` record with `isCompactSummary`
carrying the whole summary — which went into the transcript as a prompt,
because it is a `user` record. A claim about a payload is worth what the
sample behind it is worth.

## Milestones

`PLAN.md` section 9. Commit at the end of each, leave a working tool behind.

1. **Record** — done. `hook`, `status`, `install`, `uninstall`, `doctor`, `ls`.
2. **Watch** — done. `serve`, sidebar, Transcript tab, live over SSE.
3. **Read** — done. Files tab and Diff tab.
4. **Fit** — done. Both worktree tabs on a real repository: correct, fast, room, read.
5. **Act** — done. jump, send. Attention arrived early, in milestone 2.
   Peek was part of this and was removed once it had earned nothing.
6. **Shine** — done. Light theme, motion, empty states, keyboard help, README.
   No screenshots; `PLAN.md` section 9 says why.
7. **Review** — done. Comment on a diff line or a file, submit the whole review
   to the agent as one message. `PLAN.md` 4.9 is the spec. Stages: mark, send, keep.

Nothing is planned past 7. Candidates, not committed: collision watch (two
agents editing the same file in different worktrees — the daemon already caches
a changed-file map per worktree), and something over the event log, which is a
local history of every prompt and tool call nobody is reading yet.
