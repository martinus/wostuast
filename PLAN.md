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
selected session: Transcript, Files, Diff, Peek. Three actions go back to the
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
- Do not embed a terminal emulator (no xterm.js). "Peek" is a static capture.
- Do not approve permission prompts from the browser. The user approves in
  the terminal.
- Do not implement agent-to-agent messaging, teams, orchestration, cost
  tracking, or cache telemetry.
- Do not depend on `gra` or any worktree layout. A session is "an agent
  standing in a directory". Nothing more.
- Do not use Electron, Tauri, React, or a build step.
- Do not add Python dependencies beyond the standard library (3.10+).
  JavaScript libraries are allowed only when vendored into the single file.

## 4. How it works

```
 Claude Code ──hook──▶ wostuast hook ──append──▶ ~/.local/state/wostuast/events.jsonl
                                                          │
                          browser ◀──SSE/HTTP── wostuast serve ◀──tail──┘
                             │                       │
                             └──jump / send / peek───┴──▶ tmux (by pane id)
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

Nothing fires when you answer the dialog. Saying No sends no hook at all, so
wostuast cannot see a denial: the session keeps `needs_you`, which is still
true, because the agent is now waiting for you to say what to do instead. Only
the reason on the row is older than it looks. Do not invent an event that does
not exist; the Peek tab in milestone 4 is what settles "waiting for what".

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
| `Notification`, permission | `needs_you` | The same thing, up to 12 s later |
| `Notification`, idle | `needs_you` | `reason = "waiting for input"` |
| `Stop` | `done` | Agent finished its turn |
| `SubagentStop` | unchanged | Only update `last_event` |
| `PreCompact` | unchanged | Show a small "compacted" marker in the transcript |
| `SessionEnd` | `ended` | Row goes to the bottom, dimmed |
| pid gone (`kill -0` fails), checked every 5 s | `dead` | Same look as `ended`, label "killed" |

`needs_you` clears on the next `UserPromptSubmit` or `PostToolUse` for that
session. Show how long it has been waiting.

A `Notification` means `needs_you` when its `notification_type` is
`permission_prompt`, `idle_prompt` or `elicitation_dialog`. `auth_success` does
not. Older Claude Code versions send no type; read the message instead.

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
  - `GET /api/session/<id>/files` → every file in the worktree, each marked
    with whether git says it changed.
  - `GET /api/session/<id>/file?path=…` → one file's text, mtime and whether
    it is binary. The path must be a name git itself offers, and must stay
    inside the worktree.
  - `GET /api/session/<id>/diff` → parsed diff as JSON.
  - `GET /api/session/<id>/peek` → captured pane text.
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
   file to sit inside the worktree. The first check rules out `..`, an
   absolute path, an ignored file and a pathspec glob — git reads the name
   after `--`, so it can never be an option, and a glob comes back spelled
   differently from what was asked for. The second rules out a symbolic link
   that git tracks and that points somewhere else.

### 4.5 The tmux verbs

Only three tmux commands exist in the code. Each takes the pane id from the
session.

| Verb | Command | Notes |
| --- | --- | --- |
| jump | `tmux select-window -t <pane>` then `tmux select-pane -t <pane>` | Then run `$WOSTUAST_FOCUS` if set (a user command that raises the terminal window, e.g. a KWin script). |
| send | `tmux send-keys -t <pane> -l -- "<text>"` then `tmux send-keys -t <pane> Enter` | Escape nothing yourself; `-l` sends literally. Empty text is rejected. |
| peek | `tmux capture-pane -p -e -t <pane>` | Convert ANSI colors to HTML spans with a small hand-written converter. Poll once per second while the Peek tab is visible, never otherwise. |

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

List every file in the worktree: `git ls-files` plus untracked files not
ignored. Not Markdown only — you want to read the code the agent is writing,
not just the notes around it.

Find a file by typing, the way an editor's file picker does: the letters have
to turn up in the name in that order, but not next to each other, and the best
match sorts to the top. A run of letters, the start of a path segment and the
file's own name all score higher. The letters that matched are picked out in
the name.

Before anything is typed the order is three tiers: `PLAN.md`, `CLAUDE.md` and
`README.md`, then whatever the agent has changed with the newest first, then
the rest by name. A changed file carries a dot.

Render a Markdown file as Markdown and anything else as it is, in a monospace
block, with no syntax highlighting. A file with a NUL byte near the start is
binary; say so rather than showing it. Reload the open file when its mtime
changes and keep the scroll position.

Only a changed file is stat'ed. A repository holds tens of thousands of files
and tens of changed ones, so asking the disk about every file on every poll
would cost far more than the answer is worth.

### 4.8 Diff tab

Base = `origin/HEAD` if it exists, else `main`, else `master`. Show
`git diff <base>...HEAD` followed by uncommitted changes (`git diff HEAD`),
in two sections. Parse the unified diff yourself (files, hunks, lines). Render
with a file list on the left and hunks on the right, like the mockup. No
syntax highlighting in the first version. Large diffs: collapse files over
500 lines, expand on click.

## 5. The page

One HTML page, embedded in the Python file as a string. Vanilla JavaScript.
Markdown rendered in the browser with a vendored copy of `marked` (minified,
pinned version, license header kept). Everything else hand-written.

### 5.1 Layout

Follow `docs/mockups/transcript-tab.html` and `docs/mockups/diff-tab.html`.
Open them in a browser before you start. They are static HTML with inline
styles; use them as the visual target, not as code to copy.

```
┌──────────────────────────────────────────────────────────────┐
│ top bar: name · counts · "1 needs you · 1 working"            │
├──────────────┬───────────────────────────────────────────────┤
│ sessions     │ session header: label · branch · pane · state  │
│ (rows)       │ tabs: 1 Transcript  2 Files  3 Diff  4 Peek    │
│              │                                               │
│              │ tab content                                   │
│              │                                               │
│ key hints    │ send box (Transcript tab only)                │
└──────────────┴───────────────────────────────────────────────┘
```

Sidebar rows, top to bottom: `needs_you` first (oldest wait first), then
`working`, `done`, `starting`, then `ended`/`dead` dimmed. Each row:

- line 1: state dot, label (`repo/dirname`, monospace), state word
- line 2: branch, `↑n ↓n`, `● dirty` or `✓ clean`, `n files`
- line 3: the last event in words, e.g. `permission: Bash cmake --build`,
  `editing src/table.cpp`, `stopped 4 min ago`

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
  rendered prose. Load from Google Fonts with a `system-ui` /
  `ui-monospace` fallback stack, so the page still looks right offline.
- No gradients, no shadows except the soft ring on the needs-you dot, no
  icons except a few inline stroke SVGs, no emoji anywhere.
- Motion: a row that changes state fades its dot (200 ms). A new transcript
  block slides in 4 px (150 ms). The needs-you ring pulses slowly (2 s).
  Nothing else moves.
- Light theme: `prefers-color-scheme: light` gets an equivalent palette on
  `#f6f5f1`. Do it with CSS variables from the start so it is one block.

### 5.3 Attention

- Browser tab title: `(2) wostuast` when two sessions need you.
- Favicon: a dot in the state color of the most urgent session, drawn on a
  canvas at runtime.
- Desktop notification (Notification API, only after the user clicks
  "enable" once): "oans/warmhare needs you — Bash cmake --build".
- `n` jumps the selection to the next `needs_you` row.

### 5.4 Keyboard

`j`/`k` move, `Enter` jump to tmux, `1`–`4` tabs, `s` focus send box,
`Esc` leave send box, `n` next needs-you, `t` toggle thinking, `?` shows
this list. No key does anything while the send box has focus except `Esc`
and `Enter`.

### 5.5 Empty and error states

- No sessions yet: a short explainer with the install line and the hint
  "start a Claude Code session in tmux; it appears here".
- Session without pane: verbs hidden, note "not running in tmux".
- Transcript file missing: "transcript not found at <path>".
- Daemon stopped: the page shows a thin red bar "connection lost" and
  reconnects the SSE stream every 3 s.

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
  CSS, JS, vendored marked) as the last string constant.
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
4. **Act.** jump, send, Peek, attention (title, favicon, notification).
5. **Shine.** Light theme, motion, empty states, keyboard help, README with
   two screenshots and one short GIF, `docs/` in the same plain style as this
   file.

## 10. README

Write it in the style of the gra README: a one-line tagline, "a minute with
wostuast" (six commands), how it works in one diagram, install, commands,
then a reference section. Plain language, short sentences, no marketing
words. The first screenshot is the Transcript tab with one session in
`needs_you`, one `working`, one `done`.

## 11. Working agreement

- Read this file first. Then open the two mockups.
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
| Own diff renderer | Small, matches the design, no vendored library besides `marked`. |
| The Files and Diff tabs poll from the browser | Pushing them would need the daemon to know which tab each browser is on, and to remember what it last sent. Both tabs ask git for the whole answer anyway, so a request is the same work as a push. |
| The Files tab lists every file | Reading only the notes around the work is not reading the work. Markdown renders as Markdown, everything else as it is. |
| Finding a file is fuzzy, finding text is not | A path is a handle you half remember, so scattered letters should find it. Prose is read, so a search over it means what you typed. |
| Untracked files are named, not diffed | `git diff` shows nothing for them. Naming them is honest and costs one command; diffing each against nothing costs one command per file. |
| No approve button | Approving without seeing the pane is how directories get deleted. |
| No gra dependency | Works for any worktree layout; a `repo/dir` label is all gra would add. |
| Session name and context come from the status line | Hooks do not carry them. The status line payload has `session_name` and `used_percentage`, and costs one small file. |
| The status line writes one file per session, not events | It runs on every redraw. An append would flood the log with nothing new. |
| `install` never overwrites an existing status line | The status line is the user's own. wostuast prints the line to add instead. |

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
