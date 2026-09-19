# CLAUDE.md

`wostuast` shows what your coding agents are doing. It watches Claude Code
sessions and serves one web page.

**Read `PLAN.md` first. It is the complete brief.** This file only says where
things are and how to work here. When the two disagree, `PLAN.md` wins.

## Layout

| Path | What it holds |
| --- | --- |
| `wostuast` | The whole program. One executable Python file. |
| `tests/` | pytest tests and recorded fixtures. |
| `tests/fixtures/README.md` | The Claude Code hook and status line payload fields. |
| `docs/mockups/` | The visual target for the page. Open them in a browser. |
| `PLAN.md` | The brief: goals, non-goals, design, milestones. |
| `README.md` | What a user reads. Keep it in step with the commands. |

## Run it

```
pytest -q                      # run before every commit (about 2 minutes)
pytest tests/test_page.py -q   # the page, in a real browser (skipped without one)
./wostuast doctor              # check the setup
./wostuast ls                  # list the sessions
```

Test against a throwaway home, never your own:

```
export HOME=/tmp/try WOSTUAST_STATE=/tmp/try/state CLAUDE_CONFIG_DIR=/tmp/try/claude
./wostuast install && ./wostuast ls
```

`WOSTUAST_STATE` and `CLAUDE_CONFIG_DIR` exist so tests get their own
directories. They are test seams, not user settings. Do not document them as
settings.

## Rules

- **One file, at the root.** All of the program lives in `wostuast`. The page,
  the CSS and the JavaScript become string constants at the end of it. Do not
  move it into `src/` or split it: the install one-liner curls that exact path,
  and a split would need a build step, which `PLAN.md` rules out.
- **Standard library only.** Python 3.10 or newer. No pip install.
- **No JavaScript library is vendored.** `marked` and `highlight.js` are
  fetched, through the one `fetchScript` function, and each carries the hash
  of its exact bytes. Any script on this page can `POST` to `/send`, which
  types into the user's terminal, so the hash is not optional and neither is
  `crossorigin`, which is what lets the browser check it. Each library must
  degrade to something readable: without `marked` the transcript is its own
  source as text, and without `highlight.js` code has no colour. Tests hold
  both fallbacks, and `tests/fixtures/marked.min.js` is what the page tests
  serve, so no test needs a network.
- **The page never trusts what an agent wrote.** Markdown is parsed into an
  inert `<template>`, scrubbed to an allowlist, and only then inserted. Values
  from events are set with `textContent`. Assigning to `innerHTML` first would
  fire an `onerror` before any scrub could run; that was a real bug, and
  `tests/test_page.py` is what keeps it fixed.
- **The `__main__` guard stays at the very end**, after `PAGE`. It used to sit
  before it, so running as a script started the daemon and `PAGE` was never
  assigned. Importing the module hid it.
- **Ask first** before adding a dependency, a file besides `wostuast` and
  `tests/`, or a tmux command beyond jump, send and peek.
- **Prefer deleting a feature over adding a config option.**
- **The hook must never block Claude Code.** `cmd_hook` wraps everything in
  try/except, runs under a deadline (`give_up_after`), and always exits 0. Keep
  all three. The deadline covers every wait at once, including a stdin that
  never closes and a file lock stalled on a network filesystem.
- **Never write to the terminal** except through the three tmux verbs. wostuast
  reads; the user types. `tmux_jump`, `tmux_send` and `tmux_peek` are the only
  commands it runs, and only the first two write anything. They look `run` up
  when they are called rather than taking it as a default, so a test of the
  route above them can put a fake tmux in its place — the only way to test
  them without a terminal to type into.
- **A newline sent to a terminal is Enter.** `tmux_send` wraps text that has
  one in the bracketed paste markers, so a message of several lines arrives as
  a paste and waits for the reader's own Enter. Without them a real shell ran
  the first line and left the second on the prompt. One line is sent as it
  always was: a program that does not understand the markers never sees them.
- **Every POST carries a token, and the page never builds HTML from a pane.**
  A cross-origin `fetch` may send a plain POST to a loopback port with no
  questions asked, and the effect here is `tmux send-keys` into a live
  terminal. So `allowed()` wants three things to agree: the Host, an Origin
  that is ours when there is one, and the token the daemon made at start and
  printed into the page. `ansi_runs` hands the page stretches of text with
  their colours, never markup, and the page sets each one with `textContent`:
  a pane holds whatever an agent ran.
- **Never approve a permission prompt.** The user approves in the terminal.
  The hook prints nothing, and that silence is the mechanism: Claude Code reads
  a hook's stdout as its answer. We register `PermissionRequest`, which takes a
  decision to allow or deny straight from stdout, so one `print()` in
  `cmd_hook` does not just add noise: it answers a permission prompt for the
  user. Logging goes to the log file. Tests assert the silence for that event
  by name; never weaken them.
- **Amber means one thing: the agent cannot go on until you answer.** An idle
  `Notification` is not that — `Stop` already said the turn was over, and
  nothing you do clears an idle prompt, so a row that went amber on it stayed
  amber for ever. And a permission `Notification` is dropped once the session
  has sent a `PermissionRequest`: from then on it is the same news twelve
  seconds late, and honouring it raised the alarm again for a question you had
  already answered. Those two together were "needs you never clears".
- **The sidebar sorts by name.** Sorting by state moved every row each time an
  agent started or finished a tool call, so the list shifted under the reader.
  The colour, the counts and the `n` key answer "who needs me" without it.
- **Folding an event twice must change nothing.** Handlers assign and never
  accumulate, and `Store.apply` drops an event older than the session has
  already seen. A rotation makes the daemon read the archive again, so old
  events really do arrive after new ones.
- **A path out of the event log is input, not fact.** `transcript_path` goes
  through `safe_transcript`, which opens nothing outside the Claude config
  directory. `cwd` is used for git and for shortening paths, never to open a
  file the page asked for.
- **A path out of the page is input too.** `read_worktree_file` opens a file
  only when `is_listed` says git offers that exact name, and only when
  `inside` says the resolved path is still in the worktree. The first rules
  out `..` and an absolute path; the second rules out a tracked symbolic link
  that points elsewhere. Keep all three parts of the first one — the
  `:(literal)` prefix, the `--`, and comparing the answer to what was asked
  for. An ignored file is asked about the same way, `--others --ignored`,
  with all three parts again. Do not replace either check with a pattern that
  tries to spot a bad path.
- **Work from the worktree root, not from the agent's directory.** git
  reports a diff with root-relative paths whatever directory it ran in, so a
  session standing in a subdirectory gets a file list that does not agree
  with its own diff. `worktree_root` is the one place that answers this.
- **Inside a hunk, the first character of a line is the only thing that
  matters.** Removing `-- a comment` writes `--- a comment`. Read as a header
  it renamed the file and swallowed the rest of the hunk. Only `diff --git`
  and `@@` may start something new, because content always carries its own
  marker in front.
- **The Files tab lists every file, and only stats the changed ones.** A
  repository holds tens of thousands of files and tens of changed ones. The
  modification time is read to sort those few and to know when to read the
  open file again; asking the disk about all of them, every poll, is the
  mistake to avoid.
- **The daemon holds one listing per worktree, and the page holds the names.**
  `Files` keeps the answer for `LIST_FRESH` seconds and hands a stale one over
  at once while it is read again behind, so only a worktree nobody has asked
  about yet makes anyone wait. The names go with a tag; the browser sends the
  tag back and a listing that has not moved answers without them. That is
  1733 KB against 0.2 KB on a poll, so **the order the names are sent in must
  depend only on which files exist** — `in_order` is pinned-then-name for
  exactly that reason. Put a changed tier back into it and the tag moves every
  time an agent saves, and the saving is gone. The order the reader sees is
  the page's, and `dirFiles` is the only place that decides it.
- **The Files tab is a tree, and the tiers live inside it.** `dirFiles` orders
  each directory's own files — named, then changed newest first, then the rest
  — rather than listing them again in a section above the tree, which in a
  small repository is most of the list twice. `openDirs` opens a directory
  holding a change, because a closed tree cannot say what the agent just did,
  and `state.dirs` — one map of what the reader opened or closed by hand —
  wins over it, so the tree never fights the hand on it.
- **The page searches every name, or it says it cannot.** Sending the first
  five thousand of 52,799 names made `libcorrelation` find 16 files and miss
  a thousand. A search that sees part of the list gives a wrong answer that
  looks like a right one.
- **A git call that fails must not render as an empty answer.** The listing
  ran under the 2 s timeout every other git call uses, and a large repository
  timed out, and nothing came back, and nothing drew as "this worktree holds
  no file that git knows about". "No files" and "git did not answer" look the
  same and mean opposite things. The diff already had this fixed; the listing
  did not.
- **The daemon answers on localhost only.** Binding to 127.0.0.1 and sending no
  CORS header is not enough: a site can point its own name at 127.0.0.1 and the
  browser will then let it read us. `Handler.ours()` checks the Host header.
- **The Files and Diff tabs poll from the browser, and only while on screen.**
  `TABS` in the page holds one entry per tab — how to draw it, how to load it,
  and how often to ask again — so a new tab is one entry, not six edits. The
  daemon pushes the transcript and nothing else: it does not know which tab a
  browser is on, and keeping it that way is why `Hub` stays small.
- **There is one find box, and it must leave before its parent is cleared.**
  It lives where it is used, which on a split tab is inside the content box, so
  a tab that empties that box destroys it along with every listener on it — and
  then `$("find")` is null and `showTab` throws before it reaches `load`, which
  is a page broken until a reload. `draw()` takes it home whenever
  `box.dataset.tab` says another tab owns the box, which is exactly when a tab
  is about to rebuild, and `split()` takes it back. Asking the DOM rather than
  a flag means a new tab cannot forget; moving it on a same-tab redraw would
  blur the box mid-word. This has caused two outages, and
  `test_every_way_from_one_tab_to_another_works` is what watches for a third.
- **A split tab keeps its two columns and redraws one at a time.** `split()`
  builds them once and `fresh()` decides what changed, both reading the DOM
  rather than a field in `state`. One key over the whole tab meant an agent
  saving any Markdown re-rendered the file you were reading, every two
  seconds, and lost your place in it.
- **One lock around the transcript readers.** The tick thread and request
  threads both read them; two `read_new` calls at once move the byte offset
  twice, which looks like a shrinking file and re-reads everything.
- **The state directory is private.** `0700` for directories, `0600` for files,
  via `private_dir` and `private_file`. The log holds every prompt and every
  command an agent ran.
- **Keep the raw payload.** Do not strip fields from a hook event. A new field
  from a newer Claude Code must not break an older wostuast.
- **The sidebar keeps its rows and fills them in again.** Rebuilding the list
  threw away the one thing the motion is for: a dot can only fade into its new
  colour if it is the same dot, and the needs-you ring can only finish a cycle
  if its row outlives the change that started it. `newRow` builds every part
  once, empty; `fillRow` reaches them by position. A transcript block slides in
  only where a block arrives, in `patchTranscript`, never on a redraw.
- **Every colour on the page is a variable.** A hard-coded one is right in one
  theme and wrong in the other, and the ones that are easy to forget are the
  ring, the row tint, the warnings and the search hit. The hit was near-black
  on amber, which in the light theme is near-black on dark brown. A test puts
  a number on it: 4.5:1 in both themes.
- **The page tests share one browser and wait for things, not for seconds.**
  Starting Playwright costs 0.43 s and launching Chromium 0.15 s, so doing
  both per test spent half a minute on nothing; each test gets its own
  context instead, which costs 0.03 s and shares no storage. `open_page` and
  `show_tab` wait for what the page has drawn. A `wait_for_timeout` is only
  right when the test has to prove something did **not** happen.

## Style

- Plain language in code comments, `--help` text and docs: short sentences,
  one idea per sentence, active voice. Same as `PLAN.md`.
- Type hints everywhere. `dataclass` for the models.
- Every section of `wostuast` starts with a `# --- name: one line ---` comment.
- No module-level mutable state. The daemon owns a `Store` for what the agents
  are doing and a `Hub` for the browsers listening. One thread writes the
  Store; readers take `rows`, which is replaced whole, so there is no lock.
- Git and tmux run through `subprocess` with a short timeout, and an error
  there never crashes anything.

## Do not guess payload fields

The hook and status line field names are written down in
`tests/fixtures/README.md`. When you need a field that is not there, record a
real payload and add it to `tests/fixtures/`. Do not invent a name.

## Milestones

From `PLAN.md` section 9. Commit at the end of each one, and leave a working
tool behind.

1. **Record** — done. `hook`, `status`, `install`, `uninstall`, `doctor`, `ls`.
2. **Watch** — done. `serve`, the sidebar and the Transcript tab, live over SSE.
3. **Read** — done. Files tab and Diff tab.
4. **Fit** — done. The two worktree tabs, on a real repository. Four stages:
   correct, fast, room, read. `PLAN.md` section 9 lists what is in each one.
5. **Act** — done. jump, send, Peek. Attention (title, icon, notifications)
   arrived early, in milestone 2, because it was asked for.
6. **Shine** — done. Light theme, motion, empty states, keyboard help,
   README. No screenshots: `PLAN.md` section 9 says why.
7. **Review** — next. Comment on a diff line or a file, then submit the whole
   review to the agent as one message. `PLAN.md` section 4.9 is the spec;
   three stages: mark, send, keep.
