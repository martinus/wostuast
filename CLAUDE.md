# CLAUDE.md

Only an agent reads this file. It is the map, the reuse index, and the scars.
No greeting, no prose you can skip.

`PLAN.md` is the brief and wins when the two disagree. Read it first. This file
says where things are, what already exists, and which mistakes have already
been made here.

## The program in five lines

Claude Code hooks append one JSON line per event to `~/.local/state/wostuast/events.jsonl`.
`wostuast serve` tails that log into a `Store`, and serves one page over HTTP +
SSE. The page shows a session list and four tabs: Transcript, Files, Diff, Peek.
Three things go back to the terminal, all through tmux: jump, send, peek.
Nothing else writes to a terminal. Nothing owns the agent process.

## Layout

| Path | What it holds |
| --- | --- |
| `wostuast` | The whole program. 6600 lines. Python to `PAGE = r"""`, then HTML/CSS/JS. |
| `tests/conftest.py` | Every fixture, including the page ones (`page_at`, `repo_page`, `big_page`, `in_pane`, `no_pane`, `pair_at`, `past_at`) and `event()`. |
| `tests/browser.py` | The shared Chromium, `open_page`, `show_tab`, `open_diff`, and the other page helpers. No fixtures. |
| `tests/test_page_*.py` | Browser tests, one file per subject: transcript, sidebar, theme, tabs, files, diff, review, act. |
| `tests/test_*.py` | Everything that needs no browser. Named after what it tests. |
| `tests/fixtures/README.md` | The hook and status line payload fields. |
| `PLAN.md` | Goals, non-goals, design, milestones. |
| `README.md` | What a user reads. Keep in step with the commands. |
| `.github/workflows/tests.yml` | The only CI. A pytest matrix over 3.10–3.13, plus one job with a browser. Both run `pytest -q -n auto`; neither names a test file, and it should stay that way — naming one broke the browser job the moment a file was renamed. |

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
**the Files tab** · finding a file · the tree · **the Diff tab** · **the review** ·
keeping a review · has the line moved? · **the Peek tab** · talking to the
daemon · keys.

## Before you write anything new

This list exists because each entry was re-implemented once already.

**Page helpers**

| Want | Call |
| --- | --- |
| "has this changed since I drew it?" | `fresh(box, which, key)` — do not hand-roll a `dataset` compare |
| make an element | `put(parent, tag, cls, text)` |
| scattered-letter match | `fuzzy(text, query)` → `{score, at}` or null |
| walk a diff's lines with their numbers | `walkHunks(one, onHunk, onLine)` |
| the two-column tab frame | `split(box, tab, bodyClass)` → `[list, pane, note, foot]` |
| a review comment's identity | `anchorOf(path, side, line)`, `lineAnchor`, `commentAt` |
| "3 min ago" | `ago(when)` |
| which sessions are listed | `shownSessions()` (filter only) vs `listedSessions()` (what is on screen) |

**Python helpers**: `path_label`, `clip`, `run` (subprocess with a timeout),
`private_dir`/`private_file`, `safe_transcript`, `worktree_root`, `is_listed`,
`inside`, `ansi_runs`, `GONE_STATES`, `STATE_WORDS`.

**Test helpers**: `conftest.event(name, sid=..., **extra)` builds a hook event —
never hand-write the dict. `browser.py` has `open_page`, `show_tab`, `open_diff`,
`comment_on_first_line`, `two_rows`, `rgb`/`contrast`, `numbers`, `open_code`.

**CSS**: `.verb` (button), `.link` (small text button), `.find`/`.findslot`,
`.empty`, `.nohits`, `.note`, `.dot`, `.comment`. **Every colour is a variable**
and a `:root` block is the only place a colour may be a number —
`test_every_colour_outside_the_palette_is_named` fails the build otherwise.
Derive a tint or a ring with `color-mix`, never by copying an rgb triple.

Before adding a CSS rule, grep for the selector. `.turn` already carried a slide
animation for four milestones while a second one was added on top of it;
`.row .dot` already had its transition.

## How to work here

```
pytest -q -n auto                   # 62 s. Before every commit. Needs pytest-xdist.
pytest -q                           # 190 s, same result, if xdist is not installed
pytest tests/test_page_review.py -q # the subject you are changing. Do this first.
pytest tests/test_state.py -q       # no browser, under a second
./wostuast doctor / ls / serve
```

Most of the suite drives a real browser, so it waits far more than it computes:
four workers cut it from 190 s to 62 s, and the tests are safe in parallel —
every daemon binds port 0, every fixture has its own `tmp_path`, and each worker
launches a Chromium of its own. More workers than cores starts to time out
rather than go faster. CI runs `-n auto` in both jobs.

Throwaway home, never your own:

```
export HOME=/tmp/try WOSTUAST_STATE=/tmp/try/state CLAUDE_CONFIG_DIR=/tmp/try/claude
```

`WOSTUAST_STATE` and `CLAUDE_CONFIG_DIR` are test seams, not user settings. Do
not document them as settings.

**Editing one 6600-line file.** Anchor on a unique string and assert you hit it
exactly once; a sloppy replace in a file this size fails silently. A small
Python script with `assert s.count(old) == 1` before every `replace` is the
reliable shape when making several edits at once.

**Prove a test earns its place.** Write the test, then revert the fix and watch
it fail. A test written here passed with its fix removed — another line was
saving the state it asserted — and it would have guarded nothing for ever.

**Playwright.** A hover-only control (`.plus`) needs `click(force=True)`. Wait
for what the page has drawn, never for a number of seconds; `wait_for_timeout`
is right only when proving something did **not** happen. Ask one question when a
redraw could land between two: `wait_for_function("...length === 1")`, not
`wait_for_selector` then `.count()`.

## Rules, each one a bug that already happened

### Shape

- **One file, at the root.** The install one-liner curls that exact path, and a
  split needs a build step, which `PLAN.md` rules out. Page, CSS and JS are
  string constants at the end of it.
- **Standard library only.** Python 3.10+. No pip install.
- **The `__main__` guard stays last**, after `PAGE`. Before it, running as a
  script started the daemon and `PAGE` was never assigned.
- **Ask first** before adding a dependency, a file outside `wostuast` and
  `tests/`, or a tmux command beyond jump, send and peek.
- **Prefer deleting a feature over adding a config option.**
- **No module-level mutable state.** The daemon owns a `Store` and a `Hub`. One
  thread writes the Store; readers take `rows`, replaced whole, so no lock.
- **Keep the raw payload.** Never strip fields from a hook event: a new field
  from a newer Claude Code must not break an older wostuast.

### Safety — the page can type into a terminal

- **Never approve a permission prompt.** Claude Code reads a hook's stdout as
  its answer, and we register `PermissionRequest`. One `print()` in `cmd_hook`
  answers a permission dialog for the user. Logging goes to the log file. Tests
  assert the silence by event name; never weaken them.
- **The hook must never block Claude Code.** try/except around everything,
  `give_up_after` deadline, always exit 0. Keep all three. The deadline covers
  every wait at once, including a stdin that never closes.
- **Every POST carries a token.** A cross-origin `fetch` may POST to a loopback
  port unasked, and the effect here is `tmux send-keys` into a live terminal.
  `allowed()` wants three things to agree: Host, an Origin that is ours when
  there is one, and the token printed into the page.
- **The daemon answers on localhost only.** Binding to 127.0.0.1 is not enough —
  a site can point its own name at 127.0.0.1. `Handler.ours()` checks Host.
- **The page never trusts what an agent wrote.** Markdown goes into an inert
  `<template>`, is scrubbed to an allowlist, and only then inserted. Values from
  events use `textContent`. Assigning `innerHTML` first fires `onerror` before
  any scrub runs — that was real.
- **The page never builds HTML from a pane.** `ansi_runs` hands over stretches
  of text with colours, never markup.
- **Nothing below a space reaches a terminal.** `tmux_send` strips control
  characters, keeping tab and newline. A bracketed paste ends at `ESC [ 2 0 1 ~`,
  and a review quotes lines an agent wrote, so those bytes would end the paste
  and leave the rest arriving as keystrokes — with any newline as Enter. A
  person reading the preview cannot catch this; an escape byte is invisible.
- **A newline sent to a terminal is Enter.** Text with one is wrapped in the
  bracketed paste markers. Without them a real shell ran the first line.
- **A path out of the event log is input, not fact.** `transcript_path` goes
  through `safe_transcript`. `cwd` is used for git and for labels, never to open
  a file the page asked for.
- **A path out of the page is input too.** `read_worktree_file` opens a file only
  when `is_listed` says git offers that exact name and `inside` says the resolved
  path is still in the worktree. Keep all three parts of the first check — the
  `:(literal)` prefix, the `--`, and comparing the answer to what was asked for.
  Ignored files are asked the same way. Never swap either check for a pattern
  that tries to spot a bad path.
- **The state directory is private.** `0700` dirs, `0600` files. The log holds
  every prompt and every command an agent ran.

### State

- **Amber means one thing: the agent cannot go on until you answer.** An idle
  `Notification` is not that — `Stop` already said the turn was over, and nothing
  you do clears an idle prompt, so a row that went amber on it stayed amber for
  ever. A permission `Notification` is dropped once the session has sent a
  `PermissionRequest`: after that it is the same news twelve seconds late, and
  honouring it raised the alarm again for a question already answered.
- **Folding an event twice must change nothing.** Handlers assign, never
  accumulate; `Store.apply` drops an event older than the session has seen. A
  log rotation really does deliver old events after new ones.
- **A pid is not an identity.** The numbers wrap. `pid_alive` asks `kill -0`
  *and* `looks_like_claude`, because a session that ended in the morning had
  its pid taken by something else by the evening and the row said "done" all
  day for an agent that was gone. Safe to read /proc there: a session only has
  a pid where `agent_pid` could read /proc in the first place.
- **"starting" is the first few minutes, not the first day.** `SessionStart` is
  often the only event a session ever sends — resume one and leave it and
  nothing follows until you type. `mark_idle` settles it to `done` after
  `STARTING_MAX`, and an idle notification says the same sooner.
- **One renderer for a line, in `fillDiffFile`.** The Files tab, the Diff tab
  and an untracked file all go through it; a file being read is a hunk of
  `plain` lines. That is what makes a review work in both tabs — line 42 has
  the same anchor either way — and why there are not three ways to draw a line
  that drift apart.
- **The highlighter gets the whole file; `cutIntoLines` cuts the answer up.**
  A block comment or a long string only makes sense whole, so painting line by
  line gets them wrong. A span crossing a newline is closed and reopened on the
  next line. The cut walks the scrubbed fragment, never a string of HTML, and
  a line count that disagrees with the file paints nothing: colour on the wrong
  lines is worse than none.
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
- **A session with no pid cannot be checked.** `agent_pid` returns 0 where there
  is no `/proc` — on macOS, always. Such a session is taken for gone after
  `QUIET_MAX`. One with a pid is never buried for being quiet.

### The sidebar

- **It sorts by worktree.** Sorting by state moved every row on every tool call.
  Sorting by `label` is no better: the name arrives from the status line a second
  after the session starts and `/rename` changes it later.
- **The fold is not a filter.** Finished sessions fold under the history bar, but
  they are still counted, the filter still searches them, and the chosen one is
  never missing from the list it is chosen in.
- **The counts are about every session.** `drawCounts` runs *before* the guard
  that asks whether the shown rows changed — behind it, a session the filter
  hides could go amber and reach the title, icon and notification: none of them.
- **Rows are kept and filled in again, never rebuilt.** A dot can only fade if it
  is the same dot, and the needs-you ring can only finish a cycle if its row
  outlives the change. `newRow` builds every part once, empty; `fillRow` reaches
  them by position; a row moves only when its place changed, because
  `appendChild` on an attached node is a remove and an insert.

### The worktree tabs

- **Work from the worktree root, not the agent's directory.** git reports
  root-relative paths whatever directory it ran in. `worktree_root` answers this.
- **Inside a hunk, the first character of a line is the only thing that matters.**
  Removing `-- a comment` writes `--- a comment`; read as a header it renamed the
  file and swallowed the hunk. Only `diff --git` and `@@` may start something new.
- **List every file, stat only the changed ones.** Tens of thousands of files,
  tens of changed ones. Asking the disk about all of them every poll is the
  mistake.
- **One listing per worktree, and the page holds the names.** `Files` keeps it
  for `LIST_FRESH` and serves a stale one while re-reading behind. Names go with
  a tag; a listing that has not moved answers without them — 1733 KB against
  0.2 KB. So **the order the names are sent in must depend only on which files
  exist**: `in_order` is pinned-then-name. Put a changed tier back into it and
  the tag moves on every save. The reader's order is the page's, in `dirFiles`.
- **The tree holds the tiers.** `dirFiles` orders each directory's own files —
  named, changed newest first, then the rest. `openDirs` opens a directory
  holding a change; `state.dirs` (what the reader opened by hand) wins over it.
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
  "git did not answer" look the same and mean opposite things.
- **A split tab keeps its two columns and redraws one at a time.** `split()`
  builds them once, `fresh()` decides what changed, both reading the DOM. One key
  over the whole tab re-rendered the file you were reading every two seconds.
- **`.listnote` is one clipped line.** Anything with height goes in the `sidefoot`
  slot. A button put in the count strip could not be clicked at all.
- **`drawLooseFile` builds a synthetic file object.** Everything `fillDiffFile`
  reads must be in it. `path` was missing, so every untracked file's comments
  anchored to `undefined`.

### The review

- **A comment is anchored to what it is about** — path, side, line — never to the
  node it was drawn on. The Diff tab is rebuilt from `state.diff` whenever the
  agent saves anything.
- **The diff does not rebuild while a comment box is open.** It would take what
  is being typed with it, and move the code the comment is about.
- **The draft lives in the browser.** A review is yours until you submit it, and
  the daemon serves every browser the same page. `recallReview` checks the shape
  of what comes back: storage is not a place to trust blindly.
- **The preview cannot be skipped**, and it is not editable. A quoted line is
  text an agent wrote, about to be pasted into a terminal. One text, one place it
  comes from.

### The daemon and the page

- **Never write to the terminal** except through the three tmux verbs.
  `tmux_jump`, `tmux_send`, `tmux_peek` look `run` up when called rather than
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

## Milestones

`PLAN.md` section 9. Commit at the end of each, leave a working tool behind.

1. **Record** — done. `hook`, `status`, `install`, `uninstall`, `doctor`, `ls`.
2. **Watch** — done. `serve`, sidebar, Transcript tab, live over SSE.
3. **Read** — done. Files tab and Diff tab.
4. **Fit** — done. Both worktree tabs on a real repository: correct, fast, room, read.
5. **Act** — done. jump, send, Peek. Attention arrived early, in milestone 2.
6. **Shine** — done. Light theme, motion, empty states, keyboard help, README.
   No screenshots; `PLAN.md` section 9 says why.
7. **Review** — done. Comment on a diff line or a file, submit the whole review
   to the agent as one message. `PLAN.md` 4.9 is the spec. Stages: mark, send, keep.

Nothing is planned past 7. Candidates, not committed: collision watch (two
agents editing the same file in different worktrees — the daemon already caches
a changed-file map per worktree), and something over the event log, which is a
local history of every prompt and tool call nobody is reading yet.
