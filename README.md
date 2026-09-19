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
done       Fix issue 142 · unordered_dense/calmpuma  fix/issue-142   ↑1 ✓     %11   4 min  stopped
working    Speed up the table render · oans          main            ●1       %9    4 s    Edit src/table.cpp

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

A session whose process wostuast cannot check — there is no `/proc` to look in,
which on macOS means every session — is taken for killed once it has been quiet
for twelve hours. One that can be checked is never buried for being quiet: an
agent waiting for you overnight is still there.

Ended and killed sessions fold away under a **history** bar that carries their
count; click it to open them, and that browser remembers. They are grey, to
read as over. They are still counted above the list, the filter still finds
them, and the one you are reading never disappears from the list.

The rest are sorted by name. Sorting by state
moved every row each time an agent started or finished a tool call, so the list
kept shifting under you. Which agent needs you is said by the colour, by the
counts under the list, and on the page by the `n` key.

### Keys

The page is worked from the keyboard. `?` shows this list without leaving it.

| Key | Does |
| --- | --- |
| `j` `k` | move down and up the session list |
| `n` | jump to the next session that needs you |
| `f` | filter the session list |
| `r` | submit the review you have written on the diff |
| `/` | find: text in the transcript, a file on the other tabs |
| `1` – `4` | Transcript, Files, Diff, Peek |
| `Enter` | jump to that agent's tmux pane |
| `s` | type into its terminal |
| `t` | show or hide the agent's thinking |
| `c` | colours: auto, light, dark |
| `Esc` | clear a box, or close the help |

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

This is on purpose, not an oversight. The page can type into
your tmux pane, and a port on the network that can type into a shell is not
something to leave one firewall rule away. wostuast also checks the `Host`
header, so a request for `http://your-server:7331/` is refused even if it
somehow arrives. The page shows a session list
on the left and the selected session's transcript on the right, and it updates
itself as the agents work: there is no reload button because there is nothing
to reload. A box above the session list filters it: type any letters from the
worktree, the session's name or the branch, and `f` puts the cursor there.

### Acting on a session

The page reads. Three things are the exception, and all three go through tmux:

**Jump** puts the cursor in that agent's pane — its window first, then the pane.
Press `Enter`, or the button beside the session name. Set `WOSTUAST_FOCUS` to a
command that raises your terminal window and jump runs that too; which command
does that is your window manager's business, not this program's.

**Send** types into the pane and presses Enter. Press `s` to get to the box.
`Enter` sends; `Shift`+`Enter` writes another line, and the box grows as you
fill it. A long line wraps rather than running off the side.

A message of several lines arrives as one message, not one per line. A newline
typed into a terminal *is* Enter, so wostuast wraps a multi-line message in the
bracketed paste markers, the same thing your terminal does when you paste. One
line is sent exactly as a single keystroke would be.

The box is cleared only once the daemon says the text went in: you typed it at
a terminal you cannot see, so losing it is not on. Empty text is refused,
because a bare Enter into an agent's prompt is a keystroke nobody asked for.
So is a session that has ended.

**Peek** is the fourth tab: a still picture of the pane, in the colours it is
showing, refreshed once a second while you are looking at it. It is not a
terminal and cannot become one — tmux owns the keyboard.

Both of the first two write to a live terminal, so the daemon will only do them
for a page it served itself. It makes a token when it starts, prints it into
the page, and refuses any `POST` that does not carry it back in a header of its
own. Another site can send this port a request; it cannot send one that acts.

A session that is not running under tmux has no pane, so it has none of these:
the buttons are not there, and the header says `not in tmux`.

### The tabs

**Transcript** is what the agent said and did, as it happens.

**Files** lists every file in the worktree: what git tracks, what is untracked,
and what `.gitignore` covers. An ignored directory such as `node_modules` is
left out whole, because walking it would cost more than any answer inside it.
An ignored file that sits among tracked files — a generated header — is listed
like any other.

Type in the box above the list to filter the tree — the branches that hold no
match fold away, and the ones that lead to one open up. It is a file picker,
not a filter on the names: the letters have to turn up in the name in that
order, but not next to each other, so `mbldr` finds `MetricBuilder.h`. One
letter of a longer query may be missing altogether, so `MetricsBuilder` finds
`MetricBuilder.h` too.

The name is what is searched. Spread across a long path the letters of a query
mean nothing — they will land in four directories at once and match a file you
have never heard of. A directory is found the same way when its own letters sit
together, so `libcorrelation` finds what is under it, and typing a slash
searches the whole path, so `tests/tsfi` finds `tests/test_files.py`.

The best match sorts to the top and the letters that matched are picked out. Press `/` to get to the box,
`Esc` to clear it. Every name in the repository is searched, however many
there are.

Before you type it is a tree. In each directory the order is `PLAN.md`,
`CLAUDE.md` and `README.md` first, then whatever the agent has changed with
the newest first, then the rest by name. A changed file carries a dot, and so
does every directory above it, so a closed branch still says there is
something new inside. A directory holding a change opens itself; if you close
it, it stays closed. The strip above the list says how many files there are,
or how many matched what you typed.

The list is quick on a large repository because it does very little. wostuast
asks git once and shares the answer for a few seconds, and the browser keeps
the names and asks only whether they have moved — in a repository of 52,201
files that is 1.7 MB the first time and 200 bytes on every check after it.
Only the rows you can see are built, so scrolling through ten thousand
matches costs what ten would.

A Markdown file is rendered; anything else is shown as code, with syntax
highlighting — a file with no suffix is read from its shebang, and failing that
from what `file` makes of it, so a Python script called `deploy` is painted like
one — line numbers down a gutter beside it, and no box around it. The
numbers are not part of the file, so copying the code does not take them. A binary file is named, not shown. The open
file is read again within a couple of seconds of the agent changing it, and you
keep your place in it.

The page fetches two scripts and nothing else: `marked`, which renders the
Markdown, and `highlight.js`, which paints the code. Neither is inside
`wostuast` — together they are 157 KB against a 175 KB program, and the install
one-liner curls that program. Each `<script>` tag carries the hash of the exact
bytes, because any script on this page could type into your terminal through
the send box, so a CDN that has been tampered with gets you the fallback rather
than someone else's code.

Both fall back. Without `marked` the transcript is its own Markdown source as
text, which is what Markdown is for. Without `highlight.js` the code is the
same code without the colour. Nothing goes blank.

Both column edges can be dragged — the one beside the sessions and the one
beside the file list. Double-click an edge to put it back. Your browser
remembers where you left them.

**Peek** is what the pane shows right now. wostuast never turns it into markup:
the daemon hands the page stretches of text with their colours and the page
sets each one as text, because a pane holds whatever an agent happened to run.

**Diff** shows the change in two halves: what the branch has committed against
`origin/HEAD` (or `main`, or `master`), and what is not committed yet. A file
list on the left says how much each one moved; clicking a name jumps to it. A
file with more than 500 changed lines starts closed, so a large diff still
opens at once. Each line carries the number it has on each side — a removed
line has none on the new side and an added one has none on the old side — and
those numbers are not copied with the diff either. git has no diff for an untracked file, so picking one shows it
as a single added block: every line in it is new.

**Reviewing.** Hover any line, on the Diff tab or in a file you are reading,
and a `+` appears in the gutter.
Click it, write what you want changed, and save. A file takes a comment of its
own at the end of its diff, for what is about the file rather than a line.
Clearing a comment and saving is how it goes away.

A comment belongs to a line, not to a tab: one left on line 42 of the diff is
there on line 42 of the file, and the other way round. So you can review a
change through its diff, or read a whole file and comment anywhere in it.

The comments collect into a review. "Submit review" under the file list — it
appears with the first comment and counts them — opens a preview of the exact
message the agent will be sent, with one box for a note about the review as a
whole. Send it and it arrives in that agent's prompt as one paste. Cancel
keeps everything. `r` opens the preview from the keyboard.

Some of that message is text the agent wrote, and it is about to be pasted
into your terminal, which is why the preview cannot be skipped. Control
characters are stripped on the way out, because an escape byte is invisible in
a preview and a paste ends at one.

A review is kept in your browser until you send it, so a reload does not lose
it. The agent keeps working while you read, so a comment whose line has since
changed says so and keeps the line it was written against, and one whose line
has gone is shown under the diff rather than dropped. Both are still sent, and
the message says which is which.

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

Milestones 1 to 6 of [`PLAN.md`](PLAN.md) are done. wostuast records your
sessions, lists them in the terminal, and serves a live page with the
transcript, the worktree's files and its diff, and it can jump to a pane, type
into it and show you what it holds.

Milestone 7 is done too: review a diff from the page the way you review a pull
request, and send the whole review to the agent in one go.

There are no screenshots here. A screenshot of this page is a screenshot of
somebody's agents, and made-up ones would show a tool nobody is using. Run
`wostuast serve --open` instead: it takes one command and shows you your own.

`PLAN.md` is the complete brief. [`CLAUDE.md`](CLAUDE.md) says how to work in
this repository.

## License

MIT. See [LICENSE](LICENSE).
