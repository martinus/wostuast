# wostuast — plan

`wostuast` ("wos tuast?" — Austrian for "what are you doing?") shows what your
coding agents are doing. It runs on your machine, watches Claude Code sessions,
and shows them in a browser tab: which agent needs you, what each one said,
what it changed, and what its terminal shows right now.

This file is the complete brief. Read it fully before you write code.

---

## 1. The one-paragraph version

You run several Claude Code agents, one per tmux window, each in its own git
worktree. The terminal is a good place to type and a bad place to read.
`wostuast` is the reading side. It never owns the agent process. It learns
what happens from Claude Code hooks, which append one JSON line per event to
a log file. A small Python daemon tails that log and serves one web page.
The page has a sidebar (one row per session, with state) and four tabs for the
selected session: Transcript, Files, Diff. Two actions go back to the
terminal, all through tmux: jump to the window, send text to the agent, and
capture the screen. Nothing else writes to the terminal.

## 2. Goals

1. Answer "who needs me?" in one glance, from another window or another room.
2. Render everything an agent writes as real Markdown: transcript, plan files,
   specs.
3. Show the diff of a worktree without opening an editor.
4. Stay small: one Python file, no daemon required to *record* events, no
   config file, one-line install, one-line uninstall.
5. Look so good that a screenshot makes people want it.

## 3. Non-goals

Do not build these. If a feature needs one of them, leave the feature out.

- Do not spawn, own, or wrap the agent process. tmux owns the PTY.
- Do not embed a terminal emulator (no xterm.js). The terminal is where the
  agent lives; this page is a window onto what it did, not a second one.
  A Peek tab showed a still capture of the pane for two milestones and was
  removed: the tmux window it copied was always one keystroke away.
- Do not approve permission prompts from the browser. The user approves in
  the terminal.
- Do not implement agent-to-agent messaging, teams, orchestration, cost
  tracking, or cache telemetry.
- Do not depend on `gra` or any worktree layout. A session is "an agent
  standing in a directory". Nothing more.
- Do not use Electron, Tauri, React, or a build step.
- Do not add Python dependencies beyond the standard library (3.10+).
- Do not vendor a JavaScript library into the single file. The two the page
  uses, `marked` and `highlight.js`, are fetched from a CDN and pinned by the
  hash of their bytes. Each must degrade to something readable when it does
  not arrive: Markdown is written to be read as plain text, and code reads
  well enough without colour.

## 4. How it works

```
 Claude Code ──hook──▶ wostuast hook ──append──▶ ~/.local/state/wostuast/events.jsonl
                                                          │
                          browser ◀──SSE/HTTP── wostuast serve ◀──tail──┘
                             │                       │
                             └──jump / send────────┴──▶ tmux (by pane id)
```

### 4.1 Events

`wostuast install` registers `wostuast hook` for these Claude Code hook events:
`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`,
`PostToolUseFailure`, `PermissionRequest`, `Notification`, `Stop`,
`SubagentStop`, `PreCompact`, `SessionEnd`.

`PermissionRequest` fires as the permission dialog appears. `Notification` says
the same thing, but Claude Code only sends it once you have been idle for six
seconds, and checks on a six second timer, so it arrives up to twelve seconds
late. Measured against a real session: the row still read `working` three
seconds after the dialog was up. A tool whose first job is "who needs me?"
cannot be twelve seconds behind, so wostuast listens for both.

Nothing fires when you answer the dialog. Saying Yes is only visible once the
tool finishes and `PostToolUse` arrives, so an approved `cmake --build` leaves
the row amber for as long as the build runs. That is a gap wostuast cannot
close from events, and it must not be papered over with a guess; the pane shows
what the pane is really doing.

Saying No sends no hook at all, so
wostuast cannot see a denial: the session keeps `needs_you`, which is still
true, because the agent is now waiting for you to say what to do instead. Only
the reason on the row is older than it looks. Do not invent an event that does
not exist; the pane itself is what settles "waiting for what".

`PermissionRequest` can decide a permission: Claude Code reads a decision out
of the hook's stdout. wostuast prints nothing, which means no decision, and the
dialog behaves as if wostuast were not installed. This is the one place where
the hook's silence is the difference between watching and acting, and the tests
assert it for this event by name.

`wostuast hook` reads the hook JSON from stdin, adds three fields, and appends
one line to the events file:

```json
{"ts": 1758100000.123, "pane": "%7", "pid": 48213,
 "hook_event_name": "Notification", "session_id": "…", "cwd": "…",
 "transcript_path": "…", "message": "…", "...": "everything Claude sent"}
```

- `pane` is `$TMUX_PANE` from the hook's environment. It is empty outside
  tmux. This is the only link to tmux, and it is free.
- `pid` is the Claude Code process, found by walking up from `$PPID` to the
  nearest ancestor named `claude`. `$PPID` itself is **not** the agent: Claude
  Code runs a command hook through a shell, and that shell dies with the hook,
  so using it showed every live session as killed seconds after it started.
  The raw `$PPID` is kept as `shell_pid`, because the log keeps what it is
  given. Where there is no `/proc` the pid is 0 and the session is simply never
  reported as killed; saying nothing beats saying something wrong.
  The daemon uses the pid to detect a session that was killed and sent no
  `SessionEnd`.
- The hook must exit 0 fast and must never block Claude. Wrap everything in
  try/except, and set a deadline, because a `try` cannot catch a wait: reading
  stdin blocks until the writer closes it, and a file lock can stall. If the
  file cannot be written, exit 0 anyway.
- The hook prints nothing. Claude Code reads a hook's stdout as its answer, and
  for `PreToolUse` that answer can allow or deny the tool. wostuast has no
  answer. This silence is the whole mechanism behind "never approve"; anything
  worth saying goes to the log file.
- Keep the raw payload. Do not strip fields; new hook fields must not break
  old versions.
- Handlers assign, they never accumulate. Folding the same event twice must
  give the same answer, because the daemon folds only the new tail of the log.
- The state directory is `0700` and its files are `0600`. The log holds every
  prompt, every command and every result.

The events file is append-only. `wostuast serve` reads it from the start on
launch, then follows it. Rotate when it passes 20 MB: rename to
`events.1.jsonl`, start fresh. Sessions that ended more than 7 days ago are
not shown.

### 4.2 The status line

Hooks do not carry the session name or the context usage. The Claude Code
status line does. `wostuast install` also registers `wostuast status` as the
`statusLine` command, but only when the user has none. It reads the status
payload from stdin, keeps the few useful fields in
`~/.local/state/wostuast/status/<session_id>.json`, and prints one short line
back to the terminal.

The status line runs on every redraw, so it never appends to the event log. It
overwrites one small file, which holds the latest value, not a history.

Kept fields: `session_name` (set by `/rename`), `model.display_name`,
`context_window.used_percentage`, `agent.name`, `version`. Everything else is
dropped.

Without the status line wostuast still works. Sessions then have no name and
no context percent.

### 4.3 Session state

One session per `session_id`. Derive state from events, in this order:

| Event | New state | Notes |
| --- | --- | --- |
| `SessionStart` | `starting` | Record `cwd`, `transcript_path`, `pane`, `pid` |
| `UserPromptSubmit` | `working` | Store the prompt as `last_prompt` |
| `PreToolUse` / `PostToolUse` | `working` | Store `last_tool` (name + short summary) |
| `PermissionRequest` | `needs_you` | At once, as the dialog appears |
| `PostToolUseFailure` | `working` | The tool ran and failed, was interrupted, or timed out |
| `Notification`, permission | `needs_you` | The same thing, up to 12 s later. Dropped once the session has sent a `PermissionRequest` |
| `Notification`, idle | `done` from `starting`, else unchanged | `reason = "waiting for input"`. It is sitting at its prompt, so it is not starting; it is not blocked either, so it is not amber. |
| `Stop` | `done` | Agent finished its turn |
| `SubagentStop` | unchanged | Only update `last_event` |
| `PreCompact` | unchanged | Show a small "compacted" marker in the transcript |
| `SessionEnd` | `ended` | Row goes to the bottom, dimmed |
| pid gone, checked every 5 s | `dead` | `kill -0` and the process still looking like the agent. A pid alone is not an identity: the numbers wrap, and a session that ended in the morning had its pid taken by something else by the evening, so the row said "done" all day for an agent that was gone. |
| `starting` for longer than 5 minutes | `done` | `SessionStart` is often the only event a session ever sends. Resume one and leave it and nothing follows until you type, so the row read "starting" a day later. |
| no pid, and quiet for 12 h | `dead` | `agent_pid` returns 0 where there is no `/proc` to walk, which on macOS is every session. One that cannot be checked is taken for gone once it has been quiet long enough. An agent left waiting overnight has a pid, and the pid is the answer for it. |

`needs_you` clears on the next `UserPromptSubmit` or `PostToolUse` for that
session. Show how long it has been waiting.

`needs_you` means one thing: the agent cannot go on until you answer. A
`Notification` means it when its `notification_type` is `permission_prompt` or
`elicitation_dialog`. `auth_success` does not, and neither does `idle_prompt`:
that one says the turn is over and the agent sits at its prompt, which `Stop`
already said. Nothing you do clears an idle prompt, so a row that went amber on
it stayed amber for the rest of the day. It sets the reason and leaves the
state alone. Older Claude Code versions send no type; read the message instead.

A permission `Notification` is dropped once the session has sent a
`PermissionRequest`, because from then on it is only ever the same news twelve
seconds late: either the dialog is still up and the row already says so, or it
was answered while the notification was on its way, and honouring it would
raise the alarm again for a question that is gone. That was the bug behind
"needs you never clears".

The label of a session is its `session_name` when the status line gave one,
else `repo/dirname`.

Each session also carries git facts, refreshed on every `Stop`, on
`PostToolUse` for `Edit`/`Write`/`MultiEdit`/`Bash`, and at most every 10 s:
`repo`, `branch`, `ahead`, `behind`, `dirty` (bool), `touched_files` (count of
changed files vs base).

`repo` is read from `--git-common-dir`, which points at the repository itself.
A hidden name means the repository is the directory above it, which covers both
`<repo>/.git` and the `<repo>/.bare` layout that worktrees are usually built
on. Otherwise the name is the directory's own, without a trailing `.git`.
Run git with `subprocess`, `-C cwd`, short timeouts, and never let a git error
crash the daemon.

### 4.4 The daemon

`wostuast serve [--port 7331] [--open]`

- Binds `127.0.0.1` only. Never bind other interfaces.
- `http.server` from the standard library, threaded.
- Routes:
  - `GET /` → the page.
  - `GET /api/sessions` → JSON list.
  - `GET /api/events` → Server-Sent Events. Push `session` updates and
    `transcript` deltas for the session the client watches.
  - `GET /api/session/<id>/transcript` → parsed transcript as JSON blocks.
  - `GET /api/session/<id>/files[?have=<tag>]` → every file in the worktree.
    The names come as one newline-joined string with a tag, and the changed
    ones come as a short list of their own. A request carrying the tag the
    daemon still holds gets that tag and the changed files back, and no
    names. The daemon keeps the listing between requests, because listing a
    large repository costs git real time.
  - `GET /api/session/<id>/file?path=…` → one file's text, mtime and whether
    it is binary. The path must be a name git itself offers, and must stay
    inside the worktree.
  - `GET /api/session/<id>/diff` → parsed diff as JSON.
  - `POST /api/session/<id>/jump`, `POST /api/session/<id>/send`
    (body: `{"text": "…"}`).
- Watch files with polling. Do not add inotify dependencies. Polling is fine
  at this scale. The Files and Diff tabs poll from the browser while they are
  on screen — every 2 s and every 5 s — and ask for nothing while the tab is
  hidden. Only the transcript is pushed, because only the transcript grows a
  line at a time.

#### 4.4.1 Rules for the HTTP surface

Decide these before writing the daemon, not after. `send` types into a
terminal, so the page is not an ordinary local page.

1. **Any website can reach a localhost port.** A cross-origin `fetch` with
   `text/plain` is a "simple request": the browser sends it with no preflight.
   The attacker cannot read the reply, and does not need to — the effect is
   `tmux send-keys` followed by Enter. So every `POST` needs a token that the
   daemon generates at start and prints into the page, plus a check that the
   `Origin` header is ours or absent. Without this, a page in another tab can
   type a command into your terminal. This is also how wostuast could end up
   approving a permission prompt: not through a button, but through someone
   else's page typing `y` into your pane.
2. **`marked` does not sanitize.** It dropped its `sanitize` option in
   version 5 and passes raw HTML through. An agent that reads a hostile README
   puts that HTML into the transcript. Escape HTML in the Markdown source
   before `marked` sees it, and use `textContent`, never `innerHTML`, for every
   value that came from an event: `label`, `branch`, `last_prompt`,
   `last_tool`, `reason`, `last_event`.
3. **`cwd` and `transcript_path` come from the log and are not trusted.** The
   transcript path is outside the worktree by design, so path confinement does
   not cover it: require it to resolve under the Claude config directory and to
   end in `.jsonl`. Require `cwd` to be an existing directory.
4. **`<id>` in a route is a dictionary key, never a path component.** Only
   `path=` is ever joined to a directory, and only through the one confinement
   function section 8 tests. That function does not try to spot a bad path: it
   asks git whether it offers that exact name, and then requires the resolved
   file to sit inside the worktree. The first check rules out `..` and an
   absolute path — git reads the name after `--` as a pathspec, never as an
   option, `:(literal)` in front of it stops the name meaning anything but
   itself, and the answer still has to come back spelled exactly as it was
   asked for. The second rules out a symbolic link that git tracks and that
   points somewhere else. An ignored file, which the Files tab now lists, is
   offered by a second question of exactly the same shape — `--others
   --ignored`, the same `--`, the same `:(literal)`, the same comparison —
   asked only when the first says no. Two exact questions, never one clever
   pattern.

### 4.5 The tmux verbs

Only two tmux commands exist in the code. Each takes the pane id from the
session. There were three: `capture-pane`, which fed the Peek tab, went
with it.

| Verb | Command | Notes |
| --- | --- | --- |
| jump | `tmux select-window -t <pane>` then `tmux select-pane -t <pane>` | Then run `$WOSTUAST_FOCUS` if set (a user command that raises the terminal window, e.g. a KWin script). |
| send | `tmux send-keys -t <pane> -l -- "<text>"` then `tmux send-keys -t <pane> Enter` | Escape nothing yourself; `-l` sends literally. Empty text is rejected. Control characters are stripped, keeping tab and newline: a paste ends at `ESC [ 2 0 1 ~`, and a review quotes lines an agent wrote. Text with a newline in it is wrapped in the bracketed paste markers, because a newline typed into a terminal *is* Enter: measured against a real shell, a two-line message ran its first line and left the second on the prompt. One line is sent as it always was, so a program that does not understand the markers never sees them. |

If `pane` is empty, hide the verbs for that session and show "not in tmux".

### 4.6 The transcript

Claude Code writes `~/.claude/projects/<escaped-cwd>/<session>.jsonl`. The
event carries the exact path. Parse it into blocks:

- `user` text → a prompt block.
- `assistant` text → a Markdown block.
- `assistant` `tool_use` → one collapsed line per call. Summaries:
  - `Read` → `Read path`
  - `Edit` / `MultiEdit` → `Edit path +added −removed` (count lines in
    `old_string` / `new_string`)
  - `Write` → `Write path`
  - `Bash` → `Bash command` and, once the result arrives, its first line
  - `Grep` / `Glob` → `Grep pattern` / `Glob pattern`
  - others → `ToolName` and the first 80 chars of the input
- `tool_result` → attached to its `tool_use`, shown when the line is expanded.
- `thinking` → hidden, with a toggle at the top of the tab ("show thinking").
- A compaction summary → a thin divider "context compacted".

Follow the file: remember the byte offset, read new lines, push them over SSE.
A partial trailing line is kept for the next read. Do not re-parse the whole
file on every change.

### 4.7 Files tab

**It lists every file.** What `git ls-files` tracks, plus untracked files that
.gitignore does not cover, plus ignored files that sit outside an ignored
directory. An ignored directory — `build`, `node_modules`, `.venv` — is one
entry in the tree, read from disk only when you open it. Walking it to name a
quarter of a million object files would cost more than any answer inside it.
A generated file next to its sources is the ignored file people look for, and
that one is listed like any other.

**The browser searches every name.** The first version sent the first five
thousand names and let the browser search those. In a repository of 52,799
files, typing `libcorrelation` found 16 files and missed more than a
thousand, because the thousand were never sent. A search that can only see
part of the list is not a search. Either the browser holds every name or the
tab says plainly that it does not.

**The daemon keeps the list; it is sent once.** Listing 52,201 files costs
git 324 ms, so the daemon keeps the answer and shares it. A stale one is
handed over at once and read again behind it, so only a worktree nobody has
asked about yet makes anyone wait. Asking again then costs 3 ms.

The names go to the browser as one NUL-separated string with a tag. The
browser asks with the tag it already holds, and a listing that has not moved
answers with that tag and the changed files alone: **1733 KB on the first
ask, 0.2 KB on every poll after it**.

**The order the names are sent in depends only on which files exist.** It is
the pinned names, then the rest by name: one sort and three names lifted. It cannot depend on what has
changed, or it would move every time an agent saved anything — every few
seconds — and the whole list would come down the wire again each time, which
is the saving gone. The page gets the changed names and their times, which is
tens of entries, and lifts them into the three tiers below itself. Measured:
after an agent edits a tracked file, the tag does not move and the poll is
still 0.2 KB.

**git failing must never read as an empty worktree.** The listing ran under
the same two second timeout as every other git call. Two seconds is not
enough for `ls-files` and `status` over fifty thousand files, so the call
returned nothing, and nothing rendered as "this worktree holds no file that
git knows about" — sometimes on opening the tab, sometimes not, which is what
made it look random. The listing gets the timeout a large repository needs,
and a timeout says it timed out. This is the same bug as a failed diff
reading as "nothing changed".

**A tree, until you type.** The left column is a directory tree, which is how
you read a repository you do not know. The indent carries the directory, so a
row only shows the last part of the name, which is the cure for the long ones.

The three tiers live **inside** the tree, not in a section above it, so no
file is ever listed twice: in each directory the named files come first,
then whatever changed with the newest first, then the rest by name. A changed
file carries a dot and so does every directory above it, so a closed branch
still says there is something new inside.

A directory holding a change opens itself, because a closed tree cannot
answer what the agent just did, and that is the question this tool exists to
answer. What the reader opens or closes wins over that, so the tree never
fights the hand on it.

Typing filters the tree; it does not replace it. A branch that holds no match
folds away and one that leads to a match opens up, so where a file sits is
still there to read — a flat list of matches throws that away, and where it
sits is half of what you know about it. Inside one directory the best match
leads; the directories keep their own order, because that is what a tree is.

The letters have to turn up in the path in that order but not next to each
other, a run of letters counts for far more than the same letters scattered,
the start of a path segment and the file's own name count extra. The letters
that matched are picked out on the row that owns them: a letter found in a
directory is marked on that directory, not on the file below it.

**Only what is on screen is built.** Every row is one height, so where you
are in the list is arithmetic rather than a measurement. The list builds the
rows in view and a little either side, and two spacers stand in for the rest
and hold the scrollbar where it belongs. Ten thousand matches then cost the
same as ten, and no answer has to be cut to keep the page quick. How many
matched, or why none did, goes in a strip above the list, where it is
readable without scrolling to the end of ten thousand rows.

**Reading a file.** Markdown renders as Markdown. Everything else is
monospace text with syntax highlighting, set on the page itself — no box, no
border, no second background — and numbered down a gutter beside it. The
numbers sit in their own element: they are not the file, so copying the code
does not take them, and the highlighter can rewrite everything to their right
without touching them. A diff numbers both sides the same way, working the
lines out from each hunk's `@@` header rather than sending them. The border made a shell script look like a
quotation inside a document that was not there, while a Markdown file, which
has no border, looked right.

**Only a changed file is stat'ed.** A repository holds tens of thousands of
files and tens of changed ones. The modification time is read to sort those
few and to know when to read the open file again; asking the disk about every
file, every poll, would cost far more than the answer is worth.

**Everything works from the top of the worktree, never from the agent's own
directory.** git reports a diff with paths relative to the root whatever
directory it ran in, so a session standing in a subdirectory would otherwise
get a file list and a diff that do not agree.

### 4.8 Diff tab

Base = `origin/HEAD` if it exists, else `main`, else `master`. Show
`git diff <base>...HEAD` followed by uncommitted changes (`git diff HEAD`),
in two sections. Parse the unified diff yourself (files, hunks, lines).

The left column is the same column as the Files tab: the same tree, the same
find box, the same windowed rows. One component, drawn from a different list.

**An untracked file can be selected.** It was named and nothing more, so it
was the one thing on the tab you could not click. git has no diff for a file
it does not track, but every line in it is new, so selecting one reads the
file through the same route the Files tab uses and shows it as one added
block. That is what the file is: an addition nobody has staged.

Large diffs: collapse files over 500 lines, expand on click (`BIG_LINES`, and
see 4.8.3). Diff lines are not painted; only a file being read is. The marker
is its own span, so the same could be done here, but it has not been.

**The path above a file is a way back into the tree.** Each part of it is
clickable, and a click opens the tree to that directory and moves the list to
it — fifty thousand rows is not something anyone scrolls to find where one
file sits. A filter is cleared first, because revealing something the filter
has taken out would show nothing. The parts are inline spans with text-node
separators, so the whole line is still one string to select and copy.

**A document can be read as its own source.** Markdown renders, which leaves
no line to hang a comment on: the paragraph you want to remark on came from a
line that is no longer on the page. A switch beside the path gives the lines
back, and then a document is reviewed like any other file. It holds across
files, because a reader who wants to review one document usually wants the
next one too, and it is forgotten with the worktree.

### 4.8.0 One renderer for a line

The Files tab and the Diff tab draw a line through `fillDiffFile`, and an
untracked file too. A file being read is a hunk of `plain` lines: no marker in
front, one number rather than two, no tint. Three ways to draw a line would be
three ways for them to drift apart.

It is what makes a review work in both tabs. A comment is anchored by path,
side and line, so a note left on line 42 of the diff is the same note on line
42 of the file, and both tabs show it.

The highlighter is given the **whole file** and its answer is cut into lines
afterwards, by `cutIntoLines`. A block comment or a long string only makes
sense whole; painting each line on its own gets them wrong. A span that
crosses a newline is closed at the end of the line and opened again on the
next. The cut walks the scrubbed fragment, never a string of HTML, and if it
ever returns a different number of lines than the file has, nothing is
painted — colour on the wrong lines is worse than none.

### 4.8.1 What language is this?

Three questions, most certain first, and the order matters.

1. **The name.** `Makefile` and `Dockerfile` whole; otherwise the suffix.
2. **The first line.** A script with no suffix says what it is in its shebang,
   and `wostuast` itself is one. `#!/usr/bin/env -S python3 -u` and
   `#!/usr/bin/python3.12` both resolve; an interpreter we do not know answers
   nothing.
3. **`file`, on the daemon.** Only when the first two came up empty, so it
   costs a subprocess when such a file is opened and never otherwise. It is the
   third and last command this program runs, after git and tmux, and a machine
   without it simply gets no answer.

`file` earns its place on one case the others cannot reach: source with no
suffix *and* no shebang — a Python module called `helper`. But its answers are
taken from a list, not trusted wholesale. **`text/x-c` is not on that list**:
libmagic uses it for anything C-shaped and calls Rust and Go C source, measured
on real files. A file with no suffix that is really C is rare; painting Rust as
C is a confident lie, and no paint beats a wrong one.

Nothing guesses from content beyond that list. `hljs.highlightAuto` would paint
more files and mislabel them with the same confidence.

### 4.8.2 A file too long to draw whole

Measured on a file of 76,000 short lines: 306,000 nodes and about a second to
build them, and cutting the highlighter's answer into lines another second and
a quarter on top. All of it is paid again every time the agent saves the file
being read, which is every few seconds while it is being worked on.

Above 2,000 lines only the rows on screen are built. Two spacers stand in for
the rows above and below, so the scrollbar is still the length of the whole
file. A redraw costs 5 ms rather than 1,200, and the count of nodes drops from
306,000 to about 650.

Such a file is not painted at all. The highlighter has to be given the whole
file to be right about a block comment or a long string, and cutting that
answer into 76,000 line fragments costs more than the rows did.

Below 2,000 lines nothing here runs. An ordinary file is drawn whole, so the
browser's own find still sees all of it and a copy is the whole file. That is
worth keeping, and it is why this starts at a length rather than always. The
page says which of the two a file got, because the reader would otherwise go
looking for the colour and the find and not find them.

A line with a comment under it is taller than a row, and a row's height is how
the window knows where it is. There are never many, so their heights are kept
one at a time: measured once the block has been drawn, guessed until then.

### 4.8.3 Two limits, one question

`BIG_LINES` and `CODE_WHOLE` both answer "this is more DOM than anyone asked
for". They answer it differently, and that is on purpose.

| | where | above the limit |
| --- | --- | --- |
| `BIG_LINES` = 500 | Diff tab | the file starts closed, and opens on a click |
| `CODE_WHOLE` = 2,000 | Files tab | the file is drawn a screenful at a time, and not coloured |

The Files tab windows **one file**, and its rows are a grid of one height that
the scrollbar can be read against. The Diff tab stacks **many files** in one
pane, each one collapsible and each a different height, so there is no grid to
read. Collapsing is the right answer where the reader is scanning many files
rather than reading one.

Neither limit should quietly become the other. A diff of one very long file
still builds every row when it is opened; if that turns up in real use it is
its own change, not a merge of these two.

### 4.9 Review

The Diff tab reads. A review is the reply, written where the code is.

You read the diff, leave a comment on a line or on a whole file, read on,
leave another, and press Submit when the review is finished. wostuast turns
the comments into one message and sends it to the agent through the send verb.
That is the GitHub review loop with the agent in the place of the author, and
without the trip back to the terminal to retype from memory what you just
read.

**A comment is one note on one place.** A line of the diff, or a file. A line
comment quotes its line; a file comment does not. Every comment can be edited
and deleted until the review is submitted. There is no comment on a range of
lines in this milestone: one line, or the whole file.

**The drafts live in the browser, not in the daemon.** A review is yours until
you submit it, and the daemon serves the same page to every browser, so a
draft it held would be a draft everyone could read. `localStorage`, keyed by
session, survives a reload — which a review written over ten minutes needs —
and costs the daemon nothing. The daemon learns a review exists at the moment
it is sent, and not before.

**An anchor is the path, the side, the line number and the text of that
line.** The agent keeps working while you read, so the diff can move under a
half-written review. A comment whose line no longer holds the text it was
written against is marked stale, still shows the line it quoted, and is still
sent. Nothing is silently dropped, and nothing is silently moved onto the
wrong line.

**The preview is the message, and it is where the review is approved.** Submit
opens a panel holding the exact text the agent will receive. The only thing
you can type into it is the overall note, which is the review's comment on
itself; a line comment is edited where the line is, so there is one text and
one place it comes from. Cancel goes back with everything kept. The message is
plain, and reads as well in a terminal as on the page:

```
Review: 4 comments on 3 files.

<the overall note, when there is one>

src/table.cpp:112
> const auto n = rows.size();
This underflows when rows is empty. Use a signed type.

src/table.cpp:180
> for (auto& r : rows) {
Can this take a span instead?

docs/PLAN.md
Keep the heading order.
```

**A person reads every byte before it goes.** A quoted line is text an agent
wrote, and it is about to be pasted into a terminal. The preview is where that
is caught, which is why Submit is the only way a review leaves the page and
why the preview cannot be skipped. It is the same rule as "never approve a
permission prompt": the person decides.

**Nothing new writes to the terminal.** Submit calls the send verb with the
composed text. That text has newlines in it, so it travels as a bracketed
paste and waits for the reader's own Enter, exactly as a typed message does,
and the POST carries the token like every other one. A session with no pane
can be reviewed but not submitted: Submit is disabled and says "not in tmux",
the way the other verbs already do.

**The review never leaves this machine.** No GitHub API, no pull request, no
posting anywhere. It goes to the agent standing in that worktree. That is the
whole of it.

## 5. The page

One HTML page, embedded in the Python file as a string. Vanilla JavaScript.
Markdown is rendered in the browser by `marked`, fetched and pinned as 5.2
describes. Everything else is hand-written.

### 5.1 Layout

The page itself is the visual target. It was built against two static mockups,
which were right for milestone 2 and four milestones out of date by the time
milestone 7 landed — a target nobody updates stops being a target and becomes
a wrong answer that looks authoritative. They are deleted. Section 5.2 holds
the design in words, which is the form that has kept up.

Two column edges can be dragged: between the sidebar and the body, and
between a tab's file column and what it shows. Path names are long, and no
width chosen here is the right one for every repository. The width goes into
a CSS variable, so a column that is rebuilt keeps it, and into this browser's
storage, so a reload does too. A double-click on the edge puts it back.

```
┌──────────────────────────────────────────────────────────────┐
│ top bar: name · counts · "1 needs you · 1 working"            │
├──────────────┬───────────────────────────────────────────────┤
│ sessions     │ session header: label · branch · pane · state  │
│ (rows)       │ tabs: 1 Transcript  2 Files  3 Diff           │
│              │                                               │
│              │ tab content                                   │
│              │                                               │
│ key hints    │ send box (Transcript tab only)                │
└──────────────┴───────────────────────────────────────────────┘
```

Sidebar rows are sorted by worktree, with `ended` and `dead` last and dimmed.
Sorting by state moved every row each time an agent started or finished a tool
call, so the list kept shifting under the reader. Which agent needs you is said
by the amber tint, by the counts in the top bar and by the `n` key, none of
which need the order.

By the worktree, not by the session's name: the worktree is what the row shows
first, and it is the one thing about a session that cannot change. A name
arrives from the status line a second after the session starts, and `/rename`
changes it later, so a list ordered by name jumps under the reader for the
very reason this order exists.

`ended` and `dead` go under a **history** bar, which carries their count and
folds them away; folded is the default, and the choice is kept in that
browser. A week of finished sessions above the two you are working with is a
list you stop reading. They are grey through and through, rather than keeping
the colour of the state they stopped in, which read as though something were
still going on there. Two things always open the history: a filter with
anything typed in it, because a search that sees half the sessions gives a
wrong answer that looks like a right one, and the session you are reading,
which is never missing from the list it is chosen in. The counts in the top
bar still count them: the fold is not a filter.

Above the rows is a filter box. It matches the same way the Files tab does, on
scattered letters, over the worktree, the session's name and the branch, so
`ofd` finds `oans/fastduck`. The counts in the top bar stay about every
session: "who needs me" must not change because you typed in a box, so they
are drawn before the check that asks whether the shown rows moved — behind it,
a session the filter hides could go amber and reach nothing. Each row:

- line 1: state dot, `repo/dirname` in bright monospace, state word
- line 2: the session's own name, smaller and muted, when the status line
  gave one
- line 3: branch, `↑n ↓n`, `● dirty` or `✓ clean`, `n files`
- line 4: the last event in words, e.g. `permission: Bash cmake --build`,
  `editing src/table.cpp`, `stopped 4 min ago`

Where the agent is standing is the headline, and its name comes second. The
two used to share one string, `name · repo/dirname`, and the name — which
Claude Code writes from the first prompt, so it is often long and often
vague — pushed the worktree off the end of the row. The row answers "which
worktree?" first, because that is the one fact you cannot get anywhere else
on the page.

Your words and Claude's are told apart at a glance: your turn carries a
coloured rail down its left edge and a face of its own, Claude's is plain
prose on the page. Both were bubbles of the same grey, set apart only by a
small word in a narrow column, and in a long transcript that is not enough
to find where you last spoke.

### 5.2 Design

The target is "a sibling of tmux": dark, quiet, precise, and alive.

- Background `#14151a`, panels `#191a20`, raised `#1f2129`, selected
  `#262834`, borders `#2a2c36`.
- Text `#d6d8e0`, bright `#f3f4f8`, muted `#8b8f9e`, faint `#6f7385`.
- State colors: needs you `#e0a642` (amber, the only warm color), working
  `#6bbf8a`, done `#5b9bd5`, idle/ended outline only. Diff added
  `rgba(107,191,138,.14)` + `#9fe0b8`, removed `rgba(217,119,87,.14)` +
  `#f0a08a`.
- Fonts: `IBM Plex Mono` for chrome, labels, code; `IBM Plex Sans` for
  rendered prose; `IBM Plex Sans Condensed` for file names, which are long
  and which a monospace face wastes room on. Load from Google Fonts with a
  `system-ui` / `ui-monospace` fallback stack, so the page still looks right
  offline.
- Two libraries, both fetched, neither vendored: `marked` renders the
  transcript and `highlight.js` paints code. Together they are 157 KB against
  a 175 KB program — the program would be nearly twice the size to carry
  them, for a one-line install that curls it. The page already fetches its
  fonts, and already looks right without them. wostuast also watches an agent
  that cannot run without a network, so a page that wants one costs almost
  nothing.
  - **Pinned.** `integrity` holds the hash of the exact bytes, and
    `crossorigin="anonymous"` is what lets the browser check it. Any script on
    this page can `POST` to `/send`, which types into your terminal, so an
    unpinned script from someone else's server would be a way into it. A CDN
    that has been tampered with gets you the fallback below, never other code.
    One function adds both tags, so there is one place a hash could go
    missing.
  - **Each degrades to something readable.** Without `marked` the transcript
    is the Markdown source as text, which is what Markdown is for. Without
    `highlight.js` code is code without colour. Neither ever leaves a tab
    blank, and a test holds each fallback.
  - **Asked for at the right moment.** `marked` goes out as the page starts,
    because the transcript is the tab it opens on, and the transcript is drawn
    as text first and again as Markdown when it lands. `highlight.js` waits
    until the first file that is not Markdown is opened, so reading
    transcripts all day reaches it never.
  - **Neither is trusted.** Both outputs go into an inert `<template>` and are
    cut down to an allowlist before they are inserted — elements for
    `marked`, text and the highlighter's own `span` classes for
    `highlight.js`. The page does not trust a library more than it trusts the
    agent.
  The syntax colours are ours, written against the palette in this section.
  Their stylesheets are not fetched.
- No gradients, no shadows except the soft ring on the needs-you dot, no
  icons except a few inline stroke SVGs, no emoji anywhere.
- Motion: a row that changes state fades its dot (200 ms). A new transcript
  block slides in 4 px (150 ms). The needs-you ring pulses slowly (2 s).
  Nothing else moves. All three need the node to outlive the change, so the
  sidebar keeps its rows and fills them in again rather than building them
  afresh, and a block slides in only where a block arrives — never on a
  redraw, or the tab would shiver each time an agent ran a tool. One
  `prefers-reduced-motion` block turns off all three at once. "Never on a
  redraw" is the part that is easy to get wrong: the slide sat on `.turn`
  itself for a long time, so the whole history slid every time the transcript
  was rebuilt, and moving a row with `appendChild` takes it out of the
  document and back, which can cancel the animation on it.
- Light theme: `prefers-color-scheme: light` gets an equivalent palette on
  `#f6f5f1`. Do it with CSS variables from the start so it is one block. Every
  colour is a variable, including the ones that are easy to forget: the ring
  around the needs-you dot, the tint on the chosen row, the warning colour of
  a full context window and of a dropped connection, and the search hit. That
  last one is why: the hit sat on the amber with near-black text, and the
  light theme's amber is a dark brown, so a hit could not be read at all.
  A search hit has to reach 4.5:1 against its background in both themes, and
  a test says so in numbers rather than by eye. A second test reads the
  stylesheet and fails on any colour written outside a `:root` block, which is
  the rule that catches the next one. A tint or a ring is derived from its
  colour with `color-mix`, so it cannot be left behind at the old hue.

### 5.3 Attention

- Browser tab title: `(2) wostuast` when two sessions need you.
- Favicon: a dot in the state color of the most urgent session, drawn on a
  canvas at runtime.
- Desktop notification (Notification API, only after the user clicks
  "enable" once): "oans/warmhare needs you — Bash cmake --build".
- `n` jumps the selection to the next `needs_you` row.

### 5.4 Keyboard

`j`/`k` move, `Enter` jump to tmux, `1`–`4` tabs, `s` focus send box,
`Esc` leave send box, `n` next needs-you, `f` filter the session list,
`r` open the review, `t` toggle thinking, `?` shows this list. No key does anything while the send box has focus except `Esc`
and `Enter`.

### 5.5 Empty and error states

- No sessions yet: a short explainer with the install line and the hint
  "start a Claude Code session in tmux; it appears here".
- Session without pane: verbs hidden, note "not running in tmux".
- Transcript file missing: "transcript not found at <path>".
- Daemon stopped: the page shows a thin red bar "connection lost" and
  reconnects the SSE stream every 3 s.
- Review with no comments: no Submit button. The button appears with the
  first comment and carries the count, so "is there a review waiting" is
  answered by whether the button is there.

## 6. Command line

```
wostuast install       # install to ~/.local/bin, register hooks in ~/.claude/settings.json
wostuast uninstall     # remove hooks; leave the events file
wostuast hook          # the hook entry point (stdin JSON → events file)
wostuast status        # the status line entry point (stdin JSON → status file)
wostuast serve         # start the daemon; --open opens the browser
wostuast ls            # one table of sessions in the terminal, same data as the sidebar
wostuast doctor        # check: tmux present, hooks registered, events file writable
```

`install` edits `~/.claude/settings.json` in place: parse, add hook entries
that are not there yet, write back with the original indentation. Never
remove entries that are not ours. It also sets `statusLine`, but only when the
user has none; otherwise it prints the line to add by hand. `uninstall` removes
only entries whose command is ours. Both print what they changed.

The install one-liner, like gra:

```
python3 -c "$(curl -fsLS https://raw.githubusercontent.com/martinus/wostuast/main/wostuast)" install
```

## 7. Code shape

- One file, `wostuast`, Python 3.10+, executable, `#!/usr/bin/env python3`.
- Order inside the file: constants, log, event log, session model, git facts,
  status line, settings.json, output helpers, transcript parser, diff parser,
  ANSI converter, tmux verbs, HTTP server, CLI, then the embedded page (HTML,
  CSS, JS) as the last string constant.
- Every module-level section starts with a comment that says what it does
  in one line.
- Type hints everywhere. `dataclass` for `Session`, `Event`, `Block`,
  `DiffFile`, `Hunk`.
- No module-level mutable state. The daemon owns exactly two objects: a
  `Store` for what the sessions are doing, and a registry of connected
  browsers. They have different lifetimes, so they are not one object.
- One thread writes to the `Store`; request threads only read. Readers read a
  finished snapshot, which is also what tells the daemon which rows changed.
- `Session` holds what the page shows. Byte offsets and file mtimes belong to
  whatever is following the file, not to the session.
- Log to `~/.local/state/wostuast/wostuast.log`, plain text, rotated at 5 MB.

## 8. Tests

`tests/` with pytest. Fixtures are real files: a recorded events log, a
recorded transcript JSONL, a recorded `git diff` output, a recorded
`capture-pane -e` output. Test:

- state machine: every transition in the table in 4.3, plus "pid gone".
- transcript parser: each tool summary, thinking hidden, partial trailing
  line, compaction marker.
- diff parser: multiple files, renames, binary files, empty diff.
- ANSI converter: colors, bold, reset, unknown sequences dropped.
- path confinement: `..`, absolute paths, symlinks out of the worktree.
- `install`/`uninstall`: settings.json round-trips unchanged except our
  entries.
- status line: the payload is read, the name and context survive, a session id
  never escapes the status directory.
- git facts: a clean repository, a dirty one, ahead and behind, a worktree.
- the file listing: every name reaches the page, a tag that has not moved
  sends no names again, a git call that times out answers "git did not
  answer" and never an empty list, an ignored file is listed and an ignored
  directory is one entry.
- finding a file: a query that matches a thousand names in a repository of
  fifty thousand returns a thousand, not the first few that fit in a cut
  list.

The server is tested with `http.client` against a started instance on a
random port. tmux is not required for tests: the three verbs are one
function each that takes a command runner, and tests pass a fake runner.

## 9. Milestones

Commit at the end of each milestone. Each one leaves a working tool.

1. **Record.** `hook`, `install`, `uninstall`, `doctor`, `ls`. Run a real
   Claude session and check that `ls` shows it, with the right state.
2. **Watch.** `serve`, the page with sidebar and Transcript tab, live over
   SSE. This is the first thing worth a screenshot.
3. **Read.** Files tab and Diff tab.
4. **Fit.** The Files and Diff tabs, on a real repository. Milestone 3 was
   built and judged against this repository, which holds 26 files. The first
   large one it met — 52,799 files — showed that four things were wrong and
   four more were cramped. Four stages, in this order, each one leaving a
   working tool.

   1. **Correct.** The search sees every name, not the first five thousand.
      git running out of time says so instead of reading as an empty
      worktree. An untracked file on the Diff tab can be selected. Ignored
      files are listed. Nothing here is about speed or looks; it is about
      answers that are wrong today.
   2. **Fast.** The daemon keeps the listing and sends it once, with a tag.
      The browser builds only the rows on screen. The tab opens at once on a
      repository of any size, and typing never waits for the network.
   3. **Room.** Drag the sidebar edge and the file column edge. File names in
      a condensed face. No border around a file that is not Markdown.
   4. **Read.** A directory tree instead of a flat list, with the tiers
      inside it. Syntax highlighting. Your words told apart from Claude's.
      The worktree name in front on the sidebar row.

5. **Act.** jump, send, attention (title, favicon, notification). A Peek tab
   was part of this and has since been removed.
   The first two are the only things this program does that a terminal can
   feel, which is why every `POST` carries the token of section 4.4.1.
6. **Shine.** Light theme, motion, empty states, keyboard help, README.

   No screenshots and no GIF. A screenshot of this page is a screenshot of
   somebody's agents; made-up ones would show a tool nobody is using, and a
   GIF would need a recorder this program does not have and must not grow.
   The README says to run `serve --open`, which takes one command and shows
   the reader their own.

7. **Review.** Reply to a diff from the page, the way a pull request is
   reviewed, with the agent in the place of the author. Section 4.9 is the
   spec. Three stages, each one leaving a working tool.

   1. **Mark.** A comment on a line, and a comment on a file. Drawn where it
      belongs, edited and deleted in place. Nothing is sent yet, so this stage
      can be judged on its own: is commenting while reading pleasant enough
      that you would do it?

      Two things this stage settles. A comment is anchored by what it is
      about — path, side, line — and never by the node it was drawn on,
      because the diff is rebuilt from scratch every time the agent saves
      anything. And the diff does not rebuild while a comment box is open:
      that would take what is being typed with it, and would move the code
      the comment is about while it is being written. Clearing the box and
      saving is how a comment goes away, so there is no delete to find.
   2. **Send.** The preview, the overall note, Submit, and the send itself. A
      review reaches the agent. This is the milestone's point, and the first
      stage that changes anything outside the browser.

      It is also where the control characters go. A bracketed paste ends at
      `ESC [ 2 0 1 ~`, and a review quotes lines an agent wrote, so a file
      holding those bytes would close the paste early and leave the rest
      arriving as keystrokes — with any newline among them as Enter. An
      escape byte is invisible in a preview, so a person reading the message
      cannot be the thing that catches it. `tmux_send` strips them, which is
      the one place every route to a terminal passes through.
   3. **Keep.** Drafts survive a reload. A comment whose line has moved says
      so rather than pointing at whatever is there now.

      What comes back out of a browser's storage is checked before it is
      drawn: a comment of the wrong shape is left out. A review for a session
      the daemon no longer lists is swept up once, when the first list
      arrives, because storage outlives any one page.

      Three answers, not two. A comment is **here**, or **moved** — its line
      is there but no longer says what the comment was written against — or
      **gone**, its line no longer in the diff at all. A gone comment is
      drawn under the diff rather than dropped, with the line it quoted, and
      it is still sent. A comment nobody could check is not marked, and an
      unmarked comment counts as here: the Diff tab may not have been opened
      at all, and silence beats a guess.

## 10. README

Write it in the style of the gra README: a one-line tagline, "a minute with
wostuast" (six commands), how it works in one diagram, install, commands,
then a reference section. Plain language, short sentences, no marketing
words. The reference section lists the keys, so the page can be worked
without opening it first.

## 11. Working agreement

- Read this file first. Then run `serve --open` and look at the page.
- Ask before adding any dependency, any file besides `wostuast` and
  `tests/`, or any tmux command beyond the three in 4.5.
- Prefer deleting a feature over adding a config option.
- Keep the plain-language style of this file in code comments, `--help`
  text, and docs: short sentences, one idea per sentence, active voice.
- When you are unsure how Claude Code formats a hook payload or a
  transcript line, record a real one and add it to `tests/fixtures/`.
  Do not guess field names.
- Run `pytest -q` before every commit.

## 12. Decisions taken, and why

| Decision | Reason |
| --- | --- |
| Hooks write a file, not an HTTP request | The daemon need not be running; hooks stay a one-liner; the file is a history. |
| Pane id from `$TMUX_PANE` in the hook | No tmux discovery code. Three commands is all the tmux knowledge there is. |
| Polling instead of inotify | No dependency; scale is ten files. |
| Markdown in the browser | The browser is the best Markdown renderer available; Python stdlib has none. |
| Own diff renderer | Small, matches the design, and one less library to fetch. |
| The Files and Diff tabs poll from the browser | Pushing them would need the daemon to know which tab each browser is on, and to remember what it last sent. Both tabs ask git for the whole answer anyway, so a request is the same work as a push. |
| The Files tab lists every file | Reading only the notes around the work is not reading the work. Markdown renders as Markdown, everything else as it is. |
| Finding a file is fuzzy, finding text is not | A path is a handle you half remember, so scattered letters should find it. Prose is read, so a search over it means what you typed. |
| A file is found by its name, not by its whole path | Scattered over 100 characters a subsequence means nothing: "MetricsBuilder" matched `.../odin/agent/metrics/jmx/MBeanSubscriptionBuilder.java` across 71 characters and four directory names, and did not match `MetricBuilder.h`, which is what was meant. A directory can still be searched, but only when its letters sit together, and a slash in the query says you meant the path. |
| One letter of a file query may be wrong | Hiding the file you meant over a stray `s` is worse than showing it a little lower down. Only for five letters or more, and only for files: the session haystack is a short line of text, where forgiving a letter matches half the list. |
| One find box, moved to where it is used | Above the list on a tab that has one, in the tab strip for the transcript. Two boxes would be two values to keep in step, and `/` would have to guess which one it meant. |
| An untracked file opens as one added block | `git diff` shows nothing for it, so it was named and left unclickable — the one thing on the tab you could not open. Every line in it is new, and the file route already reads it. |
| No approve button | Approving without seeing the pane is how directories get deleted. |
| A review is composed in the page and sent as one message | The alternative is what the tool replaced: read here, switch to the terminal, retype from memory. One message also reaches the agent as one thought, rather than as four interruptions. |
| Draft comments live in `localStorage` | A review is yours until you submit it, and the daemon serves every browser the same page. Keeping drafts there would show them to everyone and would make the daemon hold state it has no other reason to hold. |
| The preview cannot be skipped | A quoted line is text an agent wrote, about to be pasted into a terminal. The preview is where a person reads it. Same rule as the permission prompt: the person decides. |
| A comment whose line moved is marked, not dropped | The agent keeps working while you read. Dropping the comment loses your work; moving it to the same line number points it at different code. Saying so does neither. |
| No gra dependency | Works for any worktree layout; a `repo/dir` label is all gra would add. |
| Session name and context come from the status line | Hooks do not carry them. The status line payload has `session_name` and `used_percentage`, and costs one small file. |
| The status line writes one file per session, not events | It runs on every redraw. An append would flood the log with nothing new. |
| `install` never overwrites an existing status line | The status line is the user's own. wostuast prints the line to add instead. |
| The browser holds every name, or says it does not | A search over the first five thousand of 52,799 names found 16 files and missed a thousand. A partial search gives a wrong answer and looks like a right one. |
| The listing is sent once, with a tag | Names change rarely; which files changed moves every few seconds. Sending them together made every poll cost the whole repository: 1733 KB against the 0.2 KB it costs now. |
| The order sent is not the order read | An order that depended on what had changed would move whenever an agent saved anything, and the tag with it, and the whole list would come down the wire again. The page holds the names and lifts the few that moved. |
| A stale listing is served, then read again behind | Waiting on git while an answer sits in hand helps nobody. Only a worktree nobody has asked about yet makes anyone wait, and that is once. |
| The listing gets its own timeout | Two seconds fits `git status` in a small worktree and nothing else. A shared timeout is a shared limit, and the tabs do not share a size. |
| A git failure never renders as an empty answer | "No files" and "git did not answer" look the same and mean opposite things. This was already true of the diff; the listing had the same hole. |
| An ignored directory is one entry | `node_modules` holds more files than the repository does. Naming it and reading it when opened costs nothing; walking it costs everything. An ignored file outside one is listed like any other, because that is the ignored file people look for. |
| A tree by default, a flat list while typing | A tree is how you read a repository you do not know, and its indent carries the directory, so a row shows only the last part. A match list has no tree to sit in. |
| Only the rows on screen are built | Ten thousand buttons cost ten thousand buttons. A window over a fixed row height costs the same for ten matches and ten thousand, so no answer has to be cut to stay quick. |
| Column widths belong to the reader | Paths are long, screens differ, and the alternative to a drag handle is a config option, which this file prefers to delete. |
| The tiers live inside the tree | A section above the tree would list the changed files twice, which in a small repository is most of the list twice. Ordering each directory's own files says the same thing and says it once. |
| A directory with a change opens itself | A closed tree cannot answer what the agent just did. What the reader opens or closes wins, so it never fights the hand on it. |
| Your words carry a rail and a tint | Both turns were grey blocks told apart by one small word in a narrow column, which is not enough to find where you last spoke in a long transcript. |
| The worktree leads the sidebar row | It is the one fact you cannot read anywhere else on the page. The name Claude Code writes from the first prompt is often long and often vague, and it pushed the worktree off the end. |
| Syntax highlighting is worth a second library | Reading code with no colour is the one place where "plain" costs more than it saves. |
| Nothing is vendored | `marked` and `highlight.js` are 157 KB against a 175 KB program. Carrying them would nearly double the file the install one-liner curls, and the page already fetches its fonts. |
| Both are pinned by hash | Any script on this page can type into your terminal through `/send`. `integrity` means a CDN that has been tampered with gets you the fallback rather than other code. |
| Both fall back to something readable | Markdown reads as text and code reads without colour, so a page that cannot reach a CDN is degraded, never broken. This is what makes fetching them acceptable at all. |

## 13. Questions, answered

1. **Port.** 7331 by default.
2. **Label.** `name · repo/dirname`, and just `repo/dirname` when there is no
   name. Never the full path. Claude Code titles a session from its first
   prompt, so nearly every session has a name; showing only the name loses
   which worktree the agent stands in, which is exactly what you need when
   several are running.
3. **Send.** Works for `done`. Hidden for `ended` and `dead`.
4. **Session names.** `/rename` sets one, and only the status line sees it.
   wostuast cannot rename a session from outside: the only way back into the
   terminal is `tmux send-keys`, and typing `/rename` into a live agent would
   break whatever the user is doing. So wostuast reads the name and never
   writes it.
5. **Context percent.** The status line carries it. Show it when the status
   line is registered, and leave the field out when it is not.
