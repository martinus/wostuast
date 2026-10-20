# Goals and non-goals

`CLAUDE.md`, **Goals and non-goals**, lists them; this file says what each
one means and why. Read it before you add a feature, or take a request
that bends what the program is.

Every feature is judged against these. When a request fights one, ask one
level up whether the goal bends, before building anything. A goal that bends
is rewritten here and in `CLAUDE.md` in the same pull request.

## Goals

The numbers are cited elsewhere; keep them.

1. Answer "who needs me?" in one glance, from another window or another room.
2. Render what an agent writes as real Markdown: the transcript, plan files,
   specs.
3. Show a worktree's changes without opening an editor.
4. Stay small: one Python file, the standard library, no daemon needed to
   *record* events, no config file needed to run, a one-line install and a
   one-line uninstall. Our `settings.json` is the one optional file: the
   settings menu writes it, nobody has to (`CLAUDE.md`, **Shape**, says
   why). The hook file `install` writes (`hook_path`) is no second source:
   `hook_source` copies it out of the one file, `uninstall` removes it, and
   it costs 33 ms an event against 131 for the whole program (#271).
5. Look good enough that a screenshot would sell it. **One ships** (#521):
   `docs/cover.png`, at the top of the README, drawn by `tests/tour.py` from
   made-up sessions, never real ones -- a picture of real agents is
   somebody's work. Draw it again when the page changes how it looks; the
   command is under the picture.

## Non-goals

If a feature needs one of these, leave the feature out.

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

## Status

All seven milestones are done: record, watch, read, fit, act, shine,
review. Nothing is planned. A candidate, not committed: collision watch
(two agents editing the same file in different worktrees — the daemon
already caches a changed-file map per worktree). A new feature starts at
the goals above.
