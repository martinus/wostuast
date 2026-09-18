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
  libraries are allowed only when vendored into the single file.
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
- **Handlers assign, they never accumulate.** Folding the same event twice must
  give the same answer; milestone 2 folds only the new tail of the log.
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
- No global mutable state except one `Store`.
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
2. **Watch** — next. `serve`, the sidebar and the Transcript tab, live over SSE.
3. **Read** — Files tab and Diff tab.
4. **Act** — jump, send, Peek, attention.
5. **Shine** — light theme, motion, empty states, README.
