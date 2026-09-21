# wostuast

*"wos tuast?"* — Austrian for *"what are you doing?"*

You run several Claude Code agents, one per tmux window. The terminal is a good
place to type and a bad place to read. **wostuast is the reading side:** one
page that says which agent needs you, what each one said, and what it changed.

```
wostuast ls

STATE      SESSION                                   BRANCH          CHANGES  PANE  AGE    LAST
needs you  Add substring search · oans/warmhare      feature/search  ↑2 ●5    %7    38s    permission: Bash cmake --build build -j
working    Speed up the table render · oans          main            ●1       %9    4s     Edit src/table.cpp
ready      Fix issue 142 · unordered_dense/calmpuma  fix/issue-142   ↑1 ✓     %11   4min   stopped

1 needs you · 1 working · 1 ready
```

## Why

**You see which agent needs you, and what it is asking.** The list is grouped
by state, most urgent first, newest inside each group. The browser tab title
and icon say it too, so a background tab still tells you. When an agent stops
to ask you something, the question and every answer stand at the foot of the
transcript: pick one, change your mind, and press submit — wostuast presses
those numbers in its terminal, and says which before you press it.

**You review its work like a pull request.** Hover any line — in the diff or in
a file you are reading — click the `+`, write what you want changed. The
comments collect into one review, and you send the whole thing to the agent as
a single message. A comment belongs to a line, not to a tab: one left on line
42 of the diff is there on line 42 of the file.

**You read the worktree without leaving the page.** Every file git knows
about, what an agent generated into an ignored directory, the diff against the
branch point, and your own ticket ids turned into links. Quick on a large
repository: fifty-odd thousand files cost 1.7 MB once and 200 bytes on every
check after it, and a build directory of a hundred thousand objects is one row
that says so rather than a wait.

**It never owns the agent.** tmux does. wostuast reads; exactly two things go
back to the terminal, jump and send, and it never answers a permission prompt
for you.

**One file, no dependencies.** Python 3.10+, standard library only. `curl` it
and run it. The recording side is a hook that appends one JSON line and exits,
so the daemon need not be running for anything to be kept.

**Local only, on purpose.** It binds `127.0.0.1` and checks the `Host` header,
and every write carries a token it printed into the page. A port that can type
into your shell is not something to leave one firewall rule away.

## Install

```
python3 -c "$(curl -fsLS https://raw.githubusercontent.com/martinus/wostuast/main/wostuast)" install
```

That writes `~/.local/bin/wostuast` and adds its hooks to
`~/.claude/settings.json`, touching nothing else in the file. Restart your
Claude Code sessions so they pick the hooks up, then:

```
wostuast doctor      # check the setup and say what is missing
wostuast serve --open
```

To read it from another machine, forward the port over SSH — opening a firewall
port does not work, because nothing is listening on an address other machines
can reach:

```
ssh -N -L 7331:127.0.0.1:7331 you@your-server
```

## The page

Five tabs, one session at a time. It updates itself; there is no reload button
because there is nothing to reload. Each session remembers where you left it —
the tab, the open file, the place in it.

| Tab | Holds |
| --- | --- |
| **Transcript** | What the agent said and did, with a map of the conversation beside it: a row per thing you typed and the replies under it. Click a row to go there. |
| **Files** | Every file in the worktree as a tree, with syntax highlighting, pictures shown as pictures, and go-to-file by scattered letters — `mbldr` finds `MetricBuilder.h`. An ignored directory an agent generated into is in the tree too; a folder with thousands of files in it is one row saying it is not listed. |
| **Diff** | What the branch has committed against `origin/HEAD`, and what is not committed yet. |
| **Review** | The comments you have written, as one task to send. |
| **Session** | Everything about this one: worktree, branch, model, context, pane, and its own event log. It is the only place a session is renamed. |

### Keys

`?` shows this list without leaving the page.

| Key | Does |
| --- | --- |
| `j` `k` | move down and up the session list |
| `n` | jump to the next session that needs you |
| `f` | filter the session list |
| `/` | find: a turn, or a file |
| `r` | the review you have written |
| `1` – `5` | Transcript, Files, Diff, Review, Session |
| `Enter` | jump to that agent's tmux pane |
| `s` | type into its terminal |
| `t` | show or hide the agent's thinking |
| `c` | colours: auto, light, dark |
| `Esc` | clear a box, or close the help |

Jump puts the cursor in that agent's pane. Set `WOSTUAST_FOCUS` to a command
that raises your terminal window and jump runs that too — which command does
that is your window manager's business, not this program's.

## Commands

| Command | What it does |
| --- | --- |
| `wostuast install` | Copy to `~/.local/bin` and register the hooks and the status line. |
| `wostuast uninstall` | Remove our hooks and our status line. Keep the event log. |
| `wostuast ls` | List the sessions, in the order of the page's sidebar. |
| `wostuast doctor` | Check python, the state directory, the log, the hooks, tmux. |
| `wostuast serve` | Start the daemon and serve the page on 127.0.0.1. |
| `wostuast hook` / `status` | Claude Code calls these. You do not. |

`install` also registers `wostuast status` as your Claude Code status line, but
only if you have none — hooks carry neither the session name nor the context
usage, and the status line carries both. Without it wostuast still works;
sessions then have no name and no context percent.

## Files

| Path | Holds |
| --- | --- |
| `~/.local/bin/wostuast` | The program. One file. |
| `~/.local/state/wostuast/events.jsonl` | Every event, one JSON object per line. Rotates at 20 MB. |
| `~/.local/state/wostuast/status/<session>.json` | The latest status of one session. |
| `~/.local/state/wostuast/wostuast.log` | What went wrong, if anything. Rotates at 5 MB. |
| `~/.local/state/wostuast/links.json` | Your own ticket links, if you want any. |
| `~/.claude/settings.json` | Where the hooks are registered. |

### Ticket links

If your work has ticket ids in it, they can become links. `serve` leaves an
example `links.json` the first time it runs, so editing it is all there is:

```json
[
  {"match": "(OA|QSP)-(\\d+)", "url": "https://tickets.example.com/browse/$1-$2"}
]
```

`match` is a regular expression, `url` is where a match goes, and `$1` to `$9`
are its groups. **Double every backslash**: this is JSON, so a `\d` has to be
written `\\d`.

A file wostuast cannot use is never silent. `serve` says what is wrong the
moment you restart it, the Session tab shows the same line, and `doctor` says
it too — so a link that does nothing is never a mystery. Keep patterns simple:
nothing in a browser can stop a regular expression once it starts.

This is the one file you write. Everything else under
`~/.local/state/wostuast/` is written by the program.

## No screenshots

A screenshot of this page is a screenshot of somebody's agents, and made-up
ones would show a tool nobody is using. Run `wostuast serve --open` instead:
one command, and it shows you your own.

## Status

All seven milestones of [`PLAN.md`](PLAN.md) are done, and `PLAN.md` is the
complete brief — the design, the reasoning and what was deliberately left out.
[`CLAUDE.md`](CLAUDE.md) says how to work in this repository.

## License

MIT. See [LICENSE](LICENSE).
