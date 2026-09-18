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
pytest -q                      # run before every commit
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
- **Standard library only.** Python 3.10 or newer. No pip install. JavaScript
  libraries are allowed only when vendored into the single file. Exactly one is
  vendored: `marked`, inside `PAGE`, with its licence header.
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
  reads; the user types.
- **Never approve a permission prompt.** The user approves in the terminal.
  The hook prints nothing, and that silence is the mechanism: Claude Code reads
  a hook's stdout as its answer. We register `PermissionRequest`, which takes a
  decision to allow or deny straight from stdout, so one `print()` in
  `cmd_hook` does not just add noise: it answers a permission prompt for the
  user. Logging goes to the log file. Tests assert the silence for that event
  by name; never weaken them.
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
4. **Fit** — next. The two worktree tabs, on a real repository. Four stages
   in order: correct, fast, room, read. `PLAN.md` section 9 lists what is in
   each one.
5. **Act** — jump, send, Peek. Attention (title, icon, notifications)
   arrived early, in milestone 2, because it was asked for.
6. **Shine** — light theme, motion, empty states, README.
