# wostuast

*"wos tuast?"* — Austrian for *"what are you doing?"* It shows what your coding
agents are doing.

You run several Claude Code agents, one per tmux window. The terminal is a good
place to type and a bad place to read. `wostuast` is the reading side: which
agent needs you, what each one said, what it changed, and what its terminal
shows right now.

It runs on your machine. It never owns the agent process; tmux does.

## A minute with wostuast

```
wostuast install     # register the hooks in ~/.claude/settings.json
wostuast doctor      # check the setup and say what is missing
wostuast ls          # one row per session
wostuast serve       # start the daemon and serve the page (milestone 2)
wostuast status      # the status line entry point; Claude Code calls this
wostuast uninstall   # remove the hooks; keep the event log
```

`wostuast ls` prints one row per session:

```
STATE      SESSION                                   BRANCH          CHANGES  PANE  AGE    LAST
needs you  Add substring search · oans/warmhare      feature/search  ↑2 ●5    %7    38 s   permission: Bash cmake --build build -j
working    Speed up the table render · oans          main            ●1       %9    4 s    Edit src/table.cpp
done       Fix issue 142 · unordered_dense/calmpuma  fix/issue-142   ↑1 ✓     %11   4 min  stopped

1 needs you · 1 working · 1 done
```

A session is named after its first prompt, and `/rename` changes that name. The
worktree is shown next to it, because the name alone does not say where an
agent is standing. A session with no name is just its worktree.

## How it works

```
 Claude Code ──hook──▶ wostuast hook ──append──▶ ~/.local/state/wostuast/events.jsonl
                                                          │
                          browser ◀──SSE/HTTP── wostuast serve ◀──tail──┘
                             │                       │
                             └──jump / send / peek───┴──▶ tmux (by pane id)
```

Claude Code calls a hook on every event. The hook appends one JSON line to a
file and exits. That is the whole recording side: the daemon need not run, and
the file is a history you can read with any tool.

`wostuast serve` reads that file, follows it, and serves one page. Three
actions go back to the terminal, all through tmux: jump to the window, send
text to the agent, and capture the screen. Nothing else writes to the terminal,
and nothing approves a permission prompt for you.

## Install

```
python3 -c "$(curl -fsLS https://raw.githubusercontent.com/martinus/wostuast/main/wostuast)" install
```

This writes `~/.local/bin/wostuast` and registers the hooks in
`~/.claude/settings.json`. It adds only its own entries and keeps the file's
indent width. An object you wrote on one line comes back spread over several,
because the file is rewritten from parsed JSON; nothing else changes. Restart
your Claude Code sessions so they pick up the hooks.

Then check it:

```
wostuast doctor
```

To remove it:

```
wostuast uninstall   # removes the hooks
rm ~/.local/bin/wostuast
```

`uninstall` leaves the event log alone. Delete
`~/.local/state/wostuast/` yourself if you want it gone.

Python 3.10 or newer. No other dependency. tmux is optional: without it you
still see every session, but jump, send and peek stay hidden.

## Commands

| Command | What it does |
| --- | --- |
| `wostuast install` | Copy to `~/.local/bin` and register the hooks and the status line. |
| `wostuast uninstall` | Remove our hooks and our status line. Keep the event log. |
| `wostuast hook` | The hook entry point. Reads a hook payload from stdin. |
| `wostuast status` | The status line entry point. Reads a status payload from stdin. |
| `wostuast ls` | List the sessions, in the order of the page's sidebar. |
| `wostuast doctor` | Check python, the state directory, the log, the hooks, tmux. |
| `wostuast serve` | Start the daemon and serve the page. Arrives in milestone 2. |

You call `install`, `uninstall`, `ls` and `doctor`. Claude Code calls `hook`
and `status`.

## Reference

### Session states

| State | Means |
| --- | --- |
| `needs you` | The agent waits for a permission or for your input. |
| `working` | The agent is running a tool or thinking. |
| `done` | The agent finished its turn. |
| `starting` | The session just started. |
| `ended` | The session ended. |
| `killed` | The process is gone, without an end event. |

`needs you` rows come first, the longest wait on top. Ended and killed rows go
to the bottom.

### Files

| Path | Holds |
| --- | --- |
| `~/.local/bin/wostuast` | The program. One file. |
| `~/.local/state/wostuast/events.jsonl` | Every event, one JSON object per line. Rotates at 20 MB. |
| `~/.local/state/wostuast/status/<session>.json` | The latest status of one session. |
| `~/.local/state/wostuast/wostuast.log` | What went wrong, if anything. Rotates at 5 MB. |
| `~/.claude/settings.json` | Where the hooks are registered. |

### The status line

Hooks carry neither the session name nor the context usage. The Claude Code
status line carries both. So `install` also registers `wostuast status` as your
`statusLine` command — but only when you have none. If you already have one,
`install` keeps it and prints the line to add by hand.

Without the status line wostuast still works. Sessions then have no name and no
context percent.

Claude Code names a session after its first prompt, and `/rename` changes that
name. wostuast reads the name and never writes it.

## Status

Milestone 1 of [`PLAN.md`](PLAN.md) is done: wostuast records your sessions and
shows them in the terminal. `serve` and the page come in milestone 2, and the
screenshots come with them.

`PLAN.md` is the complete brief. [`CLAUDE.md`](CLAUDE.md) says how to work in
this repository.

## License

MIT. See [LICENSE](LICENSE).
