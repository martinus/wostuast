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
wostuast serve       # start the daemon and serve the page
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

`wostuast serve` reads that file, follows it, and serves one page. It also
reads each agent's worktree with git, for the Files and Diff tabs; it only ever
reads. Three actions go back to the terminal, all through tmux: jump to the
window, send text to the agent, and capture the screen. Nothing else writes to
the terminal, and nothing approves a permission prompt for you.

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
| `wostuast serve` | Start the daemon and serve the page on 127.0.0.1. |

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

## The page

```
wostuast serve --open
```

It listens on `127.0.0.1:7331` and nowhere else.

### Reading it from another computer

Opening a firewall port does not work, because nothing is listening on an
address other machines can reach. Forward the port over SSH instead:

```
ssh -N -L 7331:127.0.0.1:7331 you@your-server
```

Leave that running and open `http://127.0.0.1:7331` on your own computer. The
traffic is carried by SSH, and the server exposes nothing new.

This is on purpose, not an oversight. From milestone 5 the page can type into
your tmux pane, and a port on the network that can type into a shell is not
something to leave one firewall rule away. wostuast also checks the `Host`
header, so a request for `http://your-server:7331/` is refused even if it
somehow arrives. The page shows a session list
on the left and the selected session's transcript on the right, and it updates
itself as the agents work: there is no reload button because there is nothing
to reload.

It sends no request back that changes anything, so nothing on that page can act
on your behalf. Jump, send and peek arrive in milestone 5.

### The tabs

**Transcript** is what the agent said and did, as it happens.

**Files** lists every file in the worktree: what git tracks, what is untracked,
and what `.gitignore` covers. An ignored directory such as `node_modules` is
left out whole, because walking it would cost more than any answer inside it.
An ignored file that sits among tracked files — a generated header — is listed
like any other.

Type in the box above the list to find one, the way an editor's file picker
does: the letters have to turn up in the name in that order, but not next to
each other, so `tsfi` finds `tests/test_files.py`. The best match sorts to the
top and the letters that matched are picked out. Press `/` to get to the box,
`Esc` to clear it. Every name in the repository is searched, however many
there are.

Before you type, the order is `PLAN.md`, `CLAUDE.md` and `README.md`, then
whatever the agent has changed with the newest first, then the rest by name.
A changed file carries a dot.

A Markdown file is rendered; anything else is shown as it is, without syntax
highlighting. A binary file is named, not shown. The open file is read again
within a couple of seconds of the agent changing it, and you keep your place
in it.

**Diff** shows the change in two halves: what the branch has committed against
`origin/HEAD` (or `main`, or `master`), and what is not committed yet. A file
list on the left says how much each one moved; clicking a name jumps to it. A
file with more than 500 changed lines starts closed, so a large diff still
opens at once. git has no diff for an untracked file, so picking one shows it
as a single added block: every line in it is new.

The same box does all three. It sits above the list on Files and Diff, and at
the right of the tab strip for the transcript, where it searches for the text
you typed rather than matching scattered letters.

The page renders what an agent wrote, and an agent may have read a hostile
file. So Markdown is parsed into an inert document, cut down to an allowlist of
elements, and only then shown; raw HTML is displayed as text rather than obeyed.
There are tests in a real browser for exactly this.

Each session is coloured by what it is doing: the row carries the colour, not
just a dot, so a list of nine reads at a glance. The tab title and the icon say
the same thing, so a background tab still tells you.

**alerts** in the top right asks your browser to tell you when an agent starts
waiting. It asks for permission only when you press it, never on its own, and
it tells you once per session rather than every second.

The button beside it switches the colours: **auto**, which follows your
system, then **light**, then **dark**. The choice stays in that browser. `c`
does the same from the keyboard.

Type in the box at the right of the tab strip, or press `/`, to find text in
the transcript. It shows only the parts that match and marks the words, and
counts what it kept. `Esc` clears it.

## Status

Milestones 1 to 3 of [`PLAN.md`](PLAN.md) are done: wostuast records your
sessions, lists them in the terminal, and serves a live page with the
transcript, the worktree's files and its diff. Milestone 4 makes those two
tabs fit a large repository. Jump, send and peek come in milestone 5.

`PLAN.md` is the complete brief. [`CLAUDE.md`](CLAUDE.md) says how to work in
this repository.

## License

MIT. See [LICENSE](LICENSE).
