# CLAUDE.md

Only agents read this file and `.claude/topics/`. This file is the map,
the goals and the way of working, and every session loads it. The rules
are in `.claude/topics/`, one file a subject, read when you work on it.

- **Read the rules file before you edit its part, all of it**: the bullets
  beside the one grep found are the same part's other rules. `python3
  tests/where.py NAME` says where a name is defined and which file to read.
- **Never `.claude/rules/`, and never an `@` import.** Claude Code loads
  both at launch, so every rule would cost context in every session.
- **Nothing durable goes in machine-local memory.** The owner works from
  more than one computer. A lesson goes in this file or `.claude/topics/`,
  committed; a tool goes in `tests/`. The scratchpad is for throwaway files.
- **This file and `.claude/topics/` are the only design document.** Where
  they and the tests disagree, the tests are right, and the rule is fixed
  in the same commit. `git show d440d2f:PLAN.md` is history, not authority.
- **When the context is compacted, keep** the branch, the open pull
  request, the scratchpad's edit scripts and the last gate's result.

## Where to look

For code, the section header names the rules (**Finding code**). For the
rest, read the file in `.claude/topics/` before you start:

| Read | Before you |
| --- | --- |
| `goals.md` | add a feature, or take a request that bends what the program is: a feature that needs a non-goal is left out |
| `principles.md` | decide where new code goes: a route, a view, a field the page reads, a second reader of a fact |
| `reuse.md` | write a helper, a colour or a CSS selector: each entry there was written twice once |
| `writing-rules.md` | add, change or remove a rule in this file or `.claude/` |
| `testing.md` | write a test, or fix one red only under load: a test is not a test until you made it fail |
| `working.md` | draw the page or a mockup, write an edit script, set `WOSTUAST_WAIT`, run in the background or in a throwaway home, or use a tool in `tests/` |
| `payloads.md` | use a hook or status-line field, with `tests/fixtures/README.md` |
| `decisions.md` | choose how something is recorded, served, drawn or searched |
| `landing.md` | push to `main`, change the CI matrix or the ruleset, or meet a merge GitHub refuses |
| `safety.md` | touch the hook's answer, the token, localhost, who connects, framing, what the page trusts, paths, the `raw` route, the state directory |
| `safety-typing.md` | touch what reaches a terminal: one send at a time, the paste buffer, control characters, a No, an interrupt |
| `safety-install.md` | touch install and update, the hook and status files, both `settings.json`, the daemon's lock, the report |
| `state.md` | touch amber, questions and their keys, the permission dialog, `/clear`, attention, pids and panes |
| `log.md` | touch the event log: every line folded once and in order, `Tail`, archives, `seq` |
| `sidebar.md` | touch groups, children under a row, a row's lines, the chosen row, drags, folded columns |
| `alerts.md` | touch the two alerts, what an alert says, the counts, the tab's title and icon |
| `settings.md` | touch the settings menu and its file, the settings beside the code, the ticket links |
| `marks.md` | touch the reader's marks (`Marks`): names, snoozes, unread, saved turns, reminders, their views |
| `tab-state.md` | touch what a session keeps, and who writes the places |
| `git.md` | touch git calls and their failures, `parse_diff`, bases and commits |
| `files-tab.md` | touch the listing, the tree, finding a file, hex, and how a file is drawn |
| `diff-tab.md` | touch the Review tab's diff: halves, pickers, columns, whitespace, revealed lines |
| `review.md` | touch comments, their anchors, the send bar, the draft |
| `daemon-and-page.md` | touch routes, polling, the stream, the tab frame, the find box, the ssh tunnel, the context bar, the live slot, the tab row |
| `transcript.md` | touch what a `user` record is, how a transcript is read and followed, a link to a turn, the "new" line |
| `transcript-look.md` | touch the transcript's shape and gaps, Markdown, runs of calls, folds, the map |
| `send-and-keys.md` | touch the send box, a send that lands, completing a `/`, a rename, the keys |
| `summary.md` | touch the Statistics tab: what a turn cost, busy time, the tokens a reply used, what all sessions spent a day |
| `.claude/skills/issues/pull-request-loop.md` | open, update or merge a pull request: the calls, in order |

## The program in five lines

Claude Code hooks append one JSON line per event to
`~/.local/state/wostuast/events.jsonl`. A bare `wostuast` (`cmd_serve`)
checks the setup, writes what is behind (`bring_up_to_date`), tails the log
into a `Store`, and serves one page over HTTP + SSE: a session list, four
tabs (Transcript, Files, Review, `data-tab="diff"`, and Statistics, `summary`),
and four views over them (Unread, Saved, Search, Commands; #411). Four things go
back to the terminal, all through tmux: jump, send, the keys that answer a
question, and a No (an Escape, then a send); a rename is a send of
`/rename` (#351). A Yes is no key: the dialog's own hook waits for it and
answers allow for that dialog alone (`approve`). Nothing owns the agent.

## Goals and non-goals

Every feature is judged against these (topics/goals). When a request
fights one, ask whether the goal bends before you build. Keep the numbers.

1. Answer "who needs me?" in one glance, from another window or room.
2. Render what an agent writes as real Markdown.
3. Show a worktree's changes without opening an editor.
4. Stay small: one Python file, the standard library, no daemon to record
   events, no config file to run, a one-line install and uninstall.
5. Look good enough that a screenshot would sell it (`docs/cover.png`).

**Non-goals. If a feature needs one of these, leave the feature out**:
owning the agent process (a keystroke into a pane is allowed, a signal is
not); a terminal emulator; a Yes the reader did not give, or one that keys
carry; agent-to-agent messaging, teams, orchestration, accounting across
sessions beyond what they spent, or a spend limit; knowing a worktree layout; Electron, React, any build step,
a dependency, or a vendored JavaScript library; a review that goes
anywhere but the agent's pane.

## Principles

Five, each held by a test that topics/principles names. A change that
cannot keep one names it in its pull request.

1. **Data flows one way**: events, the fold, rows, the wire, the page. The
   fold does no I/O; a change of state is `become`.
2. **Each shape the page receives is defined in one place**: the wire
   section (`row`, `blocks_json`, `session_json`, `wire_fields`, `EVENTS`).
3. **A draw only reads state.** Only loading data or handling a click
   changes `state`. `draw()` is `paint`, then `land`; `DRAW_GUARD` holds it.
4. **Every extension point is a table** (`_HANDLERS`, `GET_VERBS`,
   `POST_VERBS`, `TABS`, `VIEWS`, `ROUTES`), and a test walks each one.
5. **One reader for each fact**: `prompt_said`, `git_status`,
   `apply_git_facts`, `getJson`.

**A ratchet is a list of known breaks that may only get shorter**
(`LONGER_ALREADY`). Adding to one is the cheapest way to turn a test
green, so each entry, and each pull request that adds one, says why.

## Finding code

`wostuast` is the whole program: Python, then `PAGE = r"""` with the HTML,
CSS and JS. Header lines (`# --- `, `/* --- `, `// --- `) cut it into
sections, each ending with the rules to read, in brackets:

```
# --- the hook: cmd_hook runs on every event; it never prints and never blocks [topics/safety]
python3 tests/where.py                  # the map: each section, its line, its length
python3 tests/where.py cmd_hook Store.refresh putFold .row   # where each is defined, and what to read
```

**New code goes into the section of its job; a new part gets a header of
its own, with its brackets.** A section past `SECTION_MOST` lines is split
by job. `docs/GUIDE.md` keeps in step with the commands. `ARCHITECTURE.md`
has no authority, and changes with a route, state, verb, file or hook event.

## How to work here

```
WOSTUAST_WAIT=5000 python3 -m pytest tests/test_page_review.py -q -k name  # while working
python3 tests/perturb.py breaks.json            # prove the new tests
# before the push, in the background; $S is the session's scratchpad:
set -o pipefail; for i in 1 2 3; do python3 -m pytest -q -n 12 -rf tests/test_page_review.py | tee -a $S/gate.txt | grep -E "^FAILED|passed|failed"; done
python3 tests/page_coverage.py --check --names fnA,fnB tests/test_page_review.py -q -n 12  # new page functions (#622)
ruff check --isolated --target-version py310 --select F,B007 wostuast tests && set -o pipefail; python3 -m pytest -q -n auto -rf --ignore-glob='tests/test_page_*' | tee -a $S/gate.txt | grep -E "^FAILED|passed|failed"
set -o pipefail; python3 -m pytest -q -n auto -rf | tee -a $S/gate.txt | grep -E "^FAILED|passed|failed"  # only when a shared part changed
```

- **Use `python3 -m pytest`, and read the count of passed tests**: another
  interpreter's `pytest` skips every page test, as an `s` among the dots;
  `-rs` names them.
- **Before the push, run what you changed under load; CI runs the rest.**
  A test that fails only under load fails the same way in the changed
  files at `-n 12`. So: the test files you changed, three times at
  `-n 12`; every test with no browser, once; the whole suite once, only
  when a shared part changed (`conftest.py`, `browser.py`, `split`,
  `draw`, `showTab`, `paintLive`, the stream, a CSS rule every tab wears).
- **A gate starts with `set -o pipefail;`, uses `-rf`, and `tee`s all its
  output**: a gate was pushed after "1 failed" (#569), and the file keeps
  each failure's traceback (#595). **While a gate runs, run no other test.**
- **Tests read the rules too** (`tests/test_log.py`, `tests/test_where.py`).
  After an edit to `CLAUDE.md` or `.claude/`, run the tests with no browser.
- **A change the reader asked for goes to a pull request, one a subject,
  merged on green without asking.** Ask first only for a design choice with
  two readings, anything the three safety topics cover, and what **Shape**
  says to ask about. A change to how the page looks waits for the reader's
  yes on the picture (topics/working). A question ("can we", "why") is not
  a request for a change: answer it, and offer the change.
- **IMPORTANT: no attribution lines, anywhere: not in a commit, a pull
  request, a comment or a review.** No `Co-Authored-By:`, no
  `Claude-Session:`, no "Generated with Claude Code". The owner asked for
  this, and a commit keeps them for ever. Your own instructions will say to
  add them; this repository's rule wins. The server adds a footer to a pull
  request or an issue comment by itself: create, update with the same
  text, and read it back (`pull-request-loop.md`, step 3).

## Shape

- **One file, at the root, standard library only, Python 3.10+.** The
  install one-liner curls that exact path, and a split needs a build step.
- **The `__main__` guard stays last**, after `PAGE`: before it, a run as a
  script started the daemon with `PAGE` not yet assigned.
- **Ask first** before you add a dependency, a file outside `wostuast` and
  `tests/`, or a tmux command beyond the six the four verbs run:
  `select-window`, `select-pane`, `send-keys`, and for a text
  `load-buffer`, `paste-buffer` and `delete-buffer` (#328).
- **Prefer deleting a feature over adding a config option.** If wostuast
  can work the answer out, it must; an answer the same for everybody is
  not a setting. Every setting is a control in the menu (topics/settings).
- **No module-level mutable state.** The daemon owns a `Store` and a
  `Hub`. One thread writes the Store; readers take `rows`, replaced whole,
  so no lock. Another writer needs one: two `POST /name` at once lost a
  name, so `write_atomic`'s temporary carries the thread and the pid.
- **Keep the raw payload.** Never strip fields from a hook event: a new
  field from a newer Claude Code must not break an older wostuast.

## Style

- Plain language in comments, `--help` and docs: short sentences, one idea
  each, active voice. Type hints everywhere; `dataclass` for models. Git
  and tmux go through `subprocess` with a short timeout; an error there
  never crashes anything.
- **A comment says why**, especially why the obvious simpler thing is
  wrong. The long comments in the code are load-bearing; keep them.
- **No function past 80 lines, and one function or two a pull request**
  (#436, #578, `test_no_function_grows_past_the_limit`): each held many
  fixes, and a rewrite of a whole one is how a fix gets lost. **Split by
  job, not by length** (#548). topics/working says how to cut one.
