# CLAUDE.md

No human reads this file or `.claude/topics/`. This file is the map, the
reuse index and the way of working; the scars are in `.claude/topics/`, one
file a subject.

**Read the rules file before you edit its part.** **Where to look** names
it. `grep -rn <symbol> CLAUDE.md .claude/topics` finds the rule that names a
symbol. The rules were one file of 50,000 tokens, loaded at every start and
again after every compaction, so a long session spent its room on subjects
it never touched and compacted sooner. Split, a session loads the map and
reads the one subject it works on -- which only works if it does read it.
**Not `.claude/rules/`, whatever the name suggests**: Claude Code loads every
file there at launch, as it loads this one (code.claude.com/docs/en/memory,
"Rules without `paths` frontmatter are loaded at launch"), and a `paths:`
scope does not help, because every rule is about the one file `wostuast`.
Nothing here may be written as an `@` import either: that also loads it.

**Nothing durable goes in machine-local memory.** The owner works from more
than one computer: `~/.claude` memory and the scratchpad stay behind on the
machine. A lesson goes in this file or `.claude/topics/`, committed; a tool
worth keeping goes in `tests/`, as `shot.py` and `stage.py` did. The
scratchpad is for this session's throwaway files and nothing else.

**How a rule is written, and how to add one.** One bullet: the assertion
in bold, then why the obvious alternative is wrong, then the symbols to grep
and the test that holds it. Name the symbols in the rule itself, so `grep -rn
tmux_send .claude/topics` finds it. A rule goes in the file of its subject; a
new subject is a new file, and a row in **Where to look** and in the list
under **Rules**.

**A new scar goes into the bullet it belongs to, not beside it.** Grep for
the symbol first. A bullet is new only when the bug is a new kind; the same
kind again adds its test name and a sentence to the bullet that holds it,
as a nested item when it has a why of its own (the live slot and the
transcript's place are the shape). The skill writes a rule for every fix, and a file that
grows by one bullet a fix is read whole when it is read, and pushes a long
session into compaction sooner — eleven times in the session that wrote
this.

**Never cut the why to make this shorter.** The assertion says what to do; the
why is the only thing that stops the next agent doing the plausible wrong
thing again, and every one of these was written after something shipped
broken. The rules files are long because the program is subtle; they are
split so that each is read when it matters, not cut.

**State no number a person would have to maintain.** Give the command that
answers it. Three numbers in here went stale by 40% before anybody noticed,
and a stale fact is worse than no fact: it is believed. **A measurement is
not that**: "2,500 lines took 144 ms" records an experiment somebody ran, and
it stays true. The rotting kind describes this repository as it is today —
how long the program is, how long the suite takes.

**This file and `.claude/topics/` are the only design document, and they
have no senior.** There was a
`PLAN.md`: the brief the program was built from, which said it won where the
two disagreed. It was deleted once all seven milestones were done, because
parts of it had gone false and a false brief that outranks the rules is worse
than none. What still held moved here: **Goals and non-goals**, and
`.claude/topics/decisions.md`. `git show d440d2f:PLAN.md` prints
the old text. It is history and never authority: an old commit, issue or
comment that cites a section of `PLAN.md` -- or of this file before the
split -- is answered by these files, and where they and the tests disagree,
the tests are right and the rule is fixed in the same commit.

## Where to look

Find your row before editing, not after the tests go red. "topics/<subject>"
is `.claude/topics/<subject>.md`: read it, not only the bullet grep found, because the
bullets beside it are the same part's other scars.

| About to touch | Read |
| --- | --- |
| a new feature, or a request that bends what the program is | **Goals and non-goals** below — a feature that needs a non-goal is left out |
| `install`, `bring_up_to_date`, `fetch_newest`, `newest_program`, `runs_installed`, `own_version`, `unreadable`, `cmd_serve`'s start, `one_daemon`, `daemon_lock_path`, `save_settings`, `write_atomic`, `remove_status_line`, `then_of`, `shell_words` | topics/safety: Claude Code's `settings.json` is the user's file, not ours |
| `hook_source`, `HOOK_PARTS`, `HOOK_HEAD`, `hook_path`, `hook_command`, `is_hook_file`, `write_program`, `install_behind`, `hook_files_missing`, `program_files`, `GONE_VERBS`, `runs_hook_file`, `STATUS_PARTS`, `status_program_path`, `is_status_file`, `then_in` | topics/safety: the hooks run the installed copy, and the hook file is made from it |
| `config_path`, `load_config`, `save_config`, `config_payload`, `tell_config`, `page_json`, `POST /api/settings`, `keepSetting`, `takeSettings`, `putLinkRows`, `saveLinks` | topics/safety: our `settings.json`, written from the page; topics/sidebar for the menu |
| `cmd_hook`, anything on the hook path | topics/safety, first two bullets. It must never print and never block. |
| a hook or status-line field name | topics/payloads, and `tests/fixtures/README.md` |
| `session_json`, `cmd_wait`, `pick_session`, `wait_states`, `agent_pid`, `cmd_status`, the event log's shape, polling, a library, SQLite, the Agent SDK, stream-json, channels, an `http` hook, a hook decision, OpenTelemetry | topics/decisions |
| `tmux_send`, `SEND_MAX`, `POST_MAX`, `typing_trouble`, `tmux_jump`, `tmux_interrupt`, any `POST`, `allowed`, `origin_ours`, `Serving`, `reply`, `sending`, `startSending`, `claim`, `CONTROL_CHARS`, `another_user`, `socket_owner`, `asked`, `body_length`, `too_big` | topics/safety: the token, localhost, the uid of who connects, framing, what may reach a terminal |
| `answer`, `ask_keys`, `shows_preview`, `preview_kind`, `tmux_keys`, `askKeys`, `previewText`, `submitAsk`, `state.picked`, `state.answered`, `forgetAnswered` | topics/state: the question bar's bullets — the keys are measured |
| `decline`, `read_permission`, `call_answered`, `drawPermission`, `paintDecline`, `Session.permission`, `Session.dialog`, `cannot_type`, `whyNotTyped`, `Declined` | topics/safety: a No is Escape, and the reason waits for proof; topics/state for `Session.permission` |
| `plan_of`, `lastPlan`, a block of kind `plan`, `ExitPlanMode` | topics/state, the plan under `Session.permission`; topics/payloads for what the request carries |
| the Markdown scrub (`scrub`, `KEPT`, `textFor`, `safeLinks`), `linkTickets`, `linkOne`, `nextMatch`, anything that inserts what an agent wrote | topics/safety: the page never trusts what an agent wrote |
| `remote_url`, `config_entries`, `config_section`, `config_value`, `CONFIG_MAX`, `hide_secrets`, `clip_hidden`, `SECRET_SHAPES`, `tool_target` | topics/safety: a remote URL and a command reach the page without their secrets, and a long one costs no time |
| `build_report`, `named`, `tool_named`, `labelled`, `exception_named`, `REPORT_KINDS`, `private_paths`, `installed_files`, `cmd_files` | topics/safety: the report holds names and counts only, and one list of the files |
| `resume_command`, `drawResume`, `read_worktree_file`, `is_listed`, `worktree_target`, `inside`, `SHOWN_AS`, the `raw` route, `askFile`, `FileText.stamp` | topics/safety: a path out of the page is input |
| `Store`, `Session`, `_on_*`, `_clear_attention`, `read_ask`, `place`, `home`, `link_clear`, `followClear`, `Session.pane`, `Session.pid`, `reads_terminal`, `looks_like_claude` | topics/state |
| `Transcript.add`, `add_queued`, `user_block`, `read_user_text`, `isMeta`, `shell_output`, `command_output`, `putShell`, `transcript_shapes`, `SILENT_RECORDS`, `read_patch`, `putToolDiff`, `PATCH_SHOWN` | topics/daemon-and-page: what a `user` record really is, and the queued `attachment` |
| `Tail`, `EventFollower`, `archive_log`, `archived_events_paths`, `log_handles`, `append_event`'s `stamp`, `fold`, `forget_quiet`, `reload_git` | topics/state: the log is never thrown away, and every line is folded once, in order |
| `needsYou`, `toggleSnooze`, `Session.snoozed`, `snoozed_at`, `Store.snooze`, `snoozed_path`, `read_snoozed` | topics/sidebar: a snooze is a mark on one wait |
| `Session.unread`, `ended_at`, `seen_at`, `Store.see`, `seen_path`, `read_seen`, `setUnread`, `markSeen`, `keptUnread` | topics/sidebar: unread is a mark on a finished turn |
| `putNewLine`, `landOnNew`, `newSince`, `newDown`, `.newline` | topics/daemon-and-page: the "new" line, and where a transcript lands |
| `search_log`, `parse_search`, `search_day`, `SEARCH_MAX`, `SEARCH_FILTERS`, `drawSearch`, `runSearch`, `drawResults`, `goToNear` | topics/decisions: search is a scan of the event log |
| `saved_path`, `saved_entry`, `Store.save`, `SAVED_MAX`, `SAVED_PREVIEW`, `putSave`, `drawSaved`, `takeSaved`, `askSaved`, `goToTs` | topics/sidebar: a saved turn |
| `last_answer`, `Serving.last`, `LAST_MAX`, `askLast`, `drawFeed`, `openFeed`, `closeFeed`, `drawFeedLink`, `viewLink`, `drawViewTitle`, `leaveFeed`, `putCard`, `unmarked`, `state.feed`, `infeed` | topics/sidebar: "All unreads" |
| `remind_at`, `Store.remind`, `reminders_path`, `REMIND_MOST`, `reminderDue`, `reminderSet`, `armReminders`, `endReminder`, `serverNow`, `openReminders`, `REMIND_IN` | topics/sidebar: a reminder is the snooze's twin with a clock |
| `Session.title`, `first_prompt`, `Store.page_name`, `Store.over`, `Store.rename`, `clean_name`, `type_rename`, `read_name_entries`, `keepRename` | topics/sidebar, the name bullet; topics/daemon-and-page for `name`; topics/safety for the typing |
| `newRow`, `fillRow`, `setIcon`, `rowName`, `renameRow`, `BANDS`, `listedSessions`, `notifyAbout`, `dragWidth`, `settled`, `remote_url`, `openGrip`, `.row.chosen`, `tabTitle`, `paintIcon`, `iconPicture`, `tellAbout`, `waitsFor`, `shown_prompt`, `putSettings`, `paintSettings`, `drawBell`, `putChoice` | topics/sidebar |
| `.turn`, `.bubble`, `putTurnRow`, `GLIMPSE`, `putToFoot`, `putCodeCopies`, `foldedHead`, `putFoldBar` | topics/daemon-and-page: the transcript's shape |
| `Commands`, `command_used`, `front_matter`, `read_command`, `command_text`, `after_front`, `front_end`, `real_md`, `COMMAND_TEXT_MAX`, `drawCommands`, `useCommand`, `putCommand`, `commandOf`, `blankCommands`, `project_dirs`, `claude_dir`, `slashSpot`, `followSlash`, `takeSlash`, `slashKey`, `enterTakes`, `closeSlash`, `#slash`, `sizeSay`, `.sendside` | topics/daemon-and-page: completing a `/` in the send box, and its size; topics/safety for `COMMAND_SHAPE` |
| `state.files`, `state.turns`, `state.diffs`, `savePlace`, `usePlace`, `PLACE_FIELDS`, `blank…()`, `diffKey` | topics/tab-state |
| `git_facts_many`, `git_facts_or_failed`, `worktree_doing`, `own_git_dir`, `worktree_files`, `walk_ignored`, `Files`, `fillList`, `fuzzy`, `putName`, a diff, `parse_diff`, `join_type_change`, `statusWord`, a git call, `ICONS`, a file's drawing (`fillCode`, `CODE_WHOLE`, `PAINT_MAX`, `tooDenseToPaint`) | topics/worktree-tabs; topics/state for how a file is drawn |
| `worktree_diff`'s `of`, `base` and `held`, `Daemon.diffs`, `pick_base`, `recallBase`, `branch_commits`, `since`, `pickDiff`, `putDiffTree`, `pairRow`, `wordDiff`, `paintDiff`, `.dtext`, `putMessage`, `putReadAs`, `stepat`, `blockSig`, `settle`, `readerAt` | topics/worktree-tabs, the Diff tab's own bullets; topics/decisions for the base |
| `putComment`, `anchorOf`, a review comment, `putCommentList`, `putElsewhere`, `diffAnchors`, `inWorktree`, `diffLineAnchor`, `drawReviewBar`, `reviewText`, `unsent` | topics/review |
| `goBack`, `state.before`, `drawTranscript`, `drawFiles`, `drawHeader`, `drawContext`, `showModels`, `putModels`, `MODELS`, `EFFORTS`, `MODEL_SHAPE`, `model_id`, `fresh`, `split`, `TABS`, `paintLive`, a `body` class, an SSE push, `reply`, `takes_gzip`, `load`, `repoll`, `state.turns.whole` | topics/daemon-and-page |
| a new colour, a new CSS selector, a helper you are about to write | **Before you write anything new** below |
| a new test, or one red only under load | topics/testing — it is not a test until you have made it fail; `tests/perturb.py` breaks the code for you |
| the tests to run before a push | **How to work here**, "Before the push" — the changed files under load, not the whole suite three times |
| a picture of the page, or a mockup the reader asked to see | **How to work here**, the picture bullet: `tests/shot.py`, `tests/stage.py`, `tests/tour.py` |
| a change the reader asked for | **How to work here**, "A change the reader asked for" — it goes to a pull request and merges on green without asking |
| a push to `main`, landing a change, the CI matrix or the ruleset | topics/landing — `main` is protected and nothing bypasses it |
| a commit message, a pull request, a comment on GitHub | **How to work here**, last bullet — no attribution lines, whatever your defaults say |
| the issue list, an issue or a comment by anybody but `martinus`, the reflection at a session's end | `.claude/skills/issues/SKILL.md`, or say "do the issues" |
| a lesson worth keeping | the header of this file: the repository, never machine-local memory |

## The program in five lines

Claude Code hooks append one JSON line per event to `~/.local/state/wostuast/events.jsonl`.
A bare `wostuast` (`cmd_serve`) checks the setup, writes what is behind
(`bring_up_to_date`), then tails that log into a `Store` and serves one page
over HTTP + SSE. The page shows a session list and four tabs: Transcript, Files,
Review, which is the diff with the review written on it (`data-tab="diff"`),
and Commands, the skills and commands a session can run.
Four things go back to the terminal, all through tmux: jump, send, the
keys that answer a question, and a No to a permission dialog, which is an
Escape and then a send. A rename on the page is a send of `/rename` (#351).
Nothing else writes to a
terminal. Nothing owns the agent process —
interrupt is a keystroke, not a signal.

## Goals and non-goals

Every feature is judged against these. When a request fights one, the
question to ask is whether the goal bends — ask that, one level up, before
building anything. A goal that bends is rewritten here in the same PR.

**Goals.** The numbers are cited elsewhere; keep them.

1. Answer "who needs me?" in one glance, from another window or another room.
2. Render what an agent writes as real Markdown: the transcript, plan files,
   specs.
3. Show a worktree's changes without opening an editor.
4. Stay small: one Python file, the standard library, no daemon needed to
   *record* events, no config file needed to run, a one-line install and a
   one-line uninstall. Our `settings.json` is the one optional file: the
   settings menu writes it, nobody has to, and **Shape** says what it took
   to earn that. The hook file `install` writes (`hook_path`) is not a
   second source: `hook_source` copies it out of the one file, and
   `uninstall` takes it away. It earned its place by time: 33 ms an event
   against 131 for the whole program (#271).
5. Look good enough that a screenshot would sell it. None ships: see
   `README.md`, "No screenshots".

**Non-goals. If a feature needs one of these, leave the feature out.**

- **Owning the agent process.** Nothing here spawns, wraps or kills it; tmux
  owns the PTY. Typing into a pane is not owning it, which is why jump, send,
  the answer keys and a No's Escape are allowed and a signal is not.
- **A terminal emulator** (no xterm.js). A Peek tab showed a still capture of
  the pane for two milestones and was removed: the tmux window it copied was
  always one keystroke away. `capture-pane` went with it.
- **Approving a permission prompt from the browser.** No approve button, ever:
  approving without seeing the pane is how directories get deleted. And a
  dialog carries no id, so nothing can prove which one a press lands on.
  **Saying No is allowed, and nothing else is**: a wrong No is undone by
  saying what to do instead, a wrong Yes is not. The reader asked for this
  in so many words, with the options laid out, and this bullet was
  rewritten in the same PR. Answering an `AskUserQuestion` is not this: it
  is the agent's own question, and the page types nothing until the reader
  submits.
- **Agent-to-agent messaging, teams, orchestration, cache telemetry.** Showing
  the spend the status line sends is in; accounting is out. **So is a spend
  limit**: one shipped, the one thing here that typed into a terminal with
  nobody watching, and it went with the Session tab that set it -- ten rules
  and their tests for a box the reader never used. `git show` the commit
  that removed the Session tab before building one again.
- **Knowing a worktree layout.** A session is an agent standing in a
  directory, nothing more. No dependency on `gra`.
- **Electron, Tauri, React, or any build step**, a Python dependency outside
  the standard library, or a JavaScript library vendored into the file.
- **A review that goes anywhere but the agent.** No GitHub API, no pull
  request, no posting. It is pasted into the pane of the agent standing in
  that worktree, and the reader reads every byte of it first.

## Layout

| Path | What it holds |
| --- | --- |
| `wostuast` | The whole program: Python, then `PAGE = r"""` and the HTML/CSS/JS. Five figures of lines — `wc -l wostuast` rather than a number here that rots. |
| `tests/conftest.py` | Every fixture, including the page ones (`page_at`, `repo_page`, `big_page`, `in_pane`, `no_pane`, `pair_at`, `past_at`) and `event()`. |
| `tests/browser.py` | The shared Chromium, `opened`, `own_context`, `show_tab`, and the other page helpers. No fixtures. `WAIT` is `WOSTUAST_WAIT`. |
| `tests/shot.py` | Not a test. Draws a transcript case on the page, saves a PNG, and with `--measure` prints each gap from the text, not the box. `--eval JS` runs in the page first: a click, a scroll. `tests/test_shot.py` keeps it working. |
| `tests/stage.py` | Not a test. Makes a repository with a branch of four commits, a change and a Markdown document, and draws any part of the page over it to a PNG: `--tab`, `--commit N`, `--open PATH`, `--review`, `--settings JSON`, `--commands` (skills and used commands for the send box), then `--click`, `--type SELECTOR=TEXT` (and Enter), `--keys SELECTOR=TEXT` (no Enter) and `--eval JS` in order, and `--part`. `tests/test_stage.py` keeps it working. |
| `tests/tour.py` | Not a test. Five sessions, one in each state a row can be in -- unread with a plan, working, needing you, a reminder -- two saved answers, and a status line each; then a PNG of each view: `transcript`, `later` (the remind menu), `unread`, `saved`, `search`, `permission`. `--view` picks, `--light`, `--width`, `--height`, and `--eval JS` (or a file of it) before each picture, which is how a mockup of the sidebar or the views is drawn. `tests/test_tour.py` keeps it working. |
| `tests/claude_pane.py` | Not a test. A real Claude Code in a tmux pane of its own, against a fake Messages API that keeps every request and can answer once with a tool call: `send`, `paste`, `ask`, `busy` (a turn still running), `turns`, `statuses`, `hooks`, `settings`. How a question about what Claude Code does is measured, not guessed (topics/payloads). `tests/test_claude_pane.py` keeps the fake API working. |
| `tests/perturb.py` | Not a test. Applies each break in a JSON list, runs only the tests the break names, puts the file back, and prints red or GREEN a line. `tests/test_perturb.py` keeps it working. |
| `tests/test_page_*.py` | Browser tests, one file per subject: transcript, sidebar, theme, tabs, files, diff, review, act, commands. |
| `tests/test_*.py` | Everything that needs no browser. Named after what it tests. |
| `tests/fixtures/README.md` | The hook and status line payload fields. |
| `README.md` | What a user reads. Keep in step with the commands. |
| `ARCHITECTURE.md` | What a person reads to learn how the program works and why, with diagrams. It has no authority: where it and these rules or the tests disagree, they are right, and it is fixed in the same pull request. A change to what it draws -- a route, a state, a verb, a file on disk, a hook event -- updates it too. |
| `.claude/topics/*.md` | The rules, one file a subject: safety, state, sidebar, tab-state, worktree-tabs, review, daemon-and-page, testing, decisions, landing, payloads. **Where to look** routes to them. |
| `.claude/skills/issues/SKILL.md` | How to work the issue list: the owner's issues only, group, reproduce, ask, prove, review, merge on green, read the list again, then reflect on the session and land what is clear. Invoked as `/issues`, and by "do the issues". |
| `.github/workflows/tests.yml` | The only CI. A pytest matrix over 3.10–3.13, four sharded browser jobs, and an aggregator named `browser` that the branch rule requires. No job names a test file, and none may — naming one broke the browser job the moment a file was renamed, and the shards split on a hash of the test id for that reason. |

### Finding code in `wostuast`

Every section starts `# --- name: one line ---` (Python) or `// --- name ---`
(page). `grep -n "^# --- \|^// --- " wostuast` prints the whole map in one go.
Do that before grepping for a symbol.

Python: constants · log · event log · following files · **session model** ·
transcript · git facts · **files and diffs** · status ·
settings.json · output helpers · ansi · **tmux verbs** · **the daemon** ·
commands · command line · the page.

Page: asking the daemon · dragging an edge · the two fetched scripts · colours ·
**the sidebar** · the tab icon and title · notifications · **the transcript** · painting code ·
**the Files tab** · finding a file · the tree · a file too long to draw whole ·
how a file is drawn · **the Diff tab** · **the review** ·
keeping a review · **the review on the Review tab** · the Commands tab · the tabs ·
talking to the daemon · keys.

## Before you write anything new

This list exists because each entry was re-implemented once already.

**Page helpers**

| Want | Call |
| --- | --- |
| "has this changed since I drew it?" | `fresh(box, which, key)` — do not hand-roll a `dataset` compare |
| make an element | `put(parent, tag, cls, text)` — a button it makes is `type="button"` already |
| scattered-letter match | `fuzzy(text, query)` → `{score, at}` or null |
| the items in a list whose path matches the find box | `hits(items, pathOf)` — keeps the caller's order; `pick(names)` is the same sorted best-first |
| walk a diff's lines with their numbers | `walkHunks(one, onHunk, onLine)` |
| the two-column tab frame | `split(box, tab, bodyClass)` → `[list, pane, note, foot]`; the list also carries the tab's name as a class |
| the rounds of a conversation | `rounds()`, `shownRounds()` (filtered), `glimpse(text)` |
| a review comment's identity | `anchorOf(path, line)`, `lineAnchor`, `commentAt`; a line of a drawn diff, `diffLineAnchor` |
| "3 min ago" | `ago(when)` — `40s`, `4min`, `2h 15min`, `2d 6h`; two units once the first is coarse |
| one session's route | `apiUrl(id, what, query)` |
| the reader's ticket links in some text | `linkTickets(root)` — after any scrub |
| "15:48", and "21 Sep" when it was not today | `clock(when)`, `dayOf(when)` |
| text onto the clipboard, with the old way behind it | `copyToClipboard(text)` |
| a button that did its job says so for a moment | `flashOutcome(button, icon, title, done, saying, words)` — a tick in the working colour, then back; `words` for a button that is a word |
| which sessions are listed | `shownSessions()` (filter only) vs `listedSessions()` (what is on screen) |
| a file as rows, or a slice of one | `linesOf(text)`, then `asLines(path, lines, from)` |
| a binary file the browser can show | `putMedia(parent, path, found)` — `found.shown` is the daemon's answer |
| a folder or a page icon | `putIcon(parent, "dir" \| "dirOpen" \| "file")` — SVG, so not `put` |
| a choice of a few, one in force | `putChoice(parent, name, options, pick)`, then `paintChoice(group, value)` |
| Markdown or text, over what is read | `putReadAs(parent, asText, pick, textTitle)` |
| the places a reader can go | `state.files.places` — the names and the directories |
| bytes, or a date a person reads | `sizeOf(bytes)`, `whenOf(seconds)` |
| a count read at a glance, "2.4k" | `roughly(n)`; the lines of a text without splitting it, `lineCount(text)` |
| "1 file", "3 replies" | `counted(n, one, many)` — `counted` in Python too |
| this browser's storage, which may refuse | `stored(key)` → "" when nothing; `store(key, value)` forgets an empty one |
| a diff's files in the order its tree reads | `treeOrder(found, pathOf)` — folders first at every level |
| which words of a changed line changed, and marking them | `wordDiff(was, now)` → two lists of runs or null, then `markWords(cell, runs)` |

**Python helpers**: `path_label`, `clip`, `run` (subprocess with a timeout),
`private_dir`, `safe_transcript`, `worktree_root`, `is_listed`,
`inside`, `CONTROL_CHARS`, `ESCAPE_CODES`, `GONE_STATES`, `STATE_WORDS`.

**Test helpers**: `run_installed(["hook"], stdin)` runs the hook file or the
status file this checkout makes, as Claude Code does -- the hook under a
stand-in `claude` whose stdin is a terminal, or a pipe with `keys="pipe"`
(`as_claude`). `conftest.event(name, sid=..., **extra)` builds a hook event —
never hand-write the dict. **To call the program from a scratch script,
`sys.path.insert(0, "tests")` and `from conftest import wostuast`**: a
`SourceFileLoader` of its own, without the module in `sys.modules`, failed
at the first `@dataclass`. `conftest.record(kind, text, ...)` builds a
transcript record — `you`, `claude`, `think`, `tool`, `result` — and
`conftest.records(...)` makes them the lines of a file; never hand-write
those either, because a hand-written one ended in a backslash and an `n`
rather than a newline and the reader waited on it for ever. `conftest.said(args, rest)`
is what a runner that records keeps of one call, with the text that
`tmux_send` hands `load-buffer` on stdin; `conftest.typed(seen)` gives those
texts back, and `conftest.into_pane(seen)` every call that put something
into a pane. A runner that records `list(args)` alone has lost the text. `browser.py` has `opened` (`with opened(where) as page:`, and
`tab="diff"`), `own_context` and `load` for a test that needs the context
before the page, `show_tab`,
`comment_on_first_line`, `two_rows`, `rgb`/`contrast`, `numbers`, `open_code`,
`spy_on_note`.

**CSS**: `.verb` (button; `.verb.quiet` is the same shape a size down, for a
button that only changes what is on screen), `.choice` (one control in
parts, the part in force pressed: `putChoice` and `paintChoice` build and
paint it, the settings menu and `putReadAs` use it), `.link` (small text
button),
`.acts` (what you can do to a comment,
at its right edge), `.find`/`.findslot`,
`.empty`, `.nohits`, `.note`, `.comment`. **Every colour is a variable**
and a `:root` block is the only place a colour may be a number —
`test_every_colour_outside_the_palette_is_named` fails the build otherwise.
It reads an issue number in a CSS comment as a colour too: `(#333)` failed
it, so a comment in the CSS says `issue 333`.
Derive a tint or a ring with `color-mix`, never by copying an rgb triple.
**A control that shows on hover is `display: none` until then, or out of
the flow -- never `opacity: 0` in it**: invisible, it keeps its room. The
"unread" link cut long names short and the bookmark moved "claude" out of
line with its time, one after the other in one session (#373, #377).

Three page functions are about matching and they are easy to confuse:
`matches` asks whether a transcript block matches, `matching` filters the file
tree, `hits` filters any list by path. Adding a fourth word for the idea is how
one of them gets shadowed — that happened, and the browser tests caught it as
fifty failures.

Before adding a CSS rule, grep for the selector. `.turn` already carried a slide
animation for four milestones while a second one was added on top of it;
`.row .dot` already had its transition. The review's hover button was given
`.plus`, which was already the green "+3" beside a changed file — so every
count on the page became an invisible 18×18 box, and a file that had gained
lines read as if it had only lost them. Nothing looked broken; the number was
simply not there.

## How to work here

```
python3 tests/shot.py case.txt out.png --measure  # a report about the transcript: look first, about 1 s
python3 tests/stage.py out.png --commit 2 --review  # a report about the Review or Files tab (--tab files --open PATH)
python3 tests/tour.py out/ --view later --eval mock.js  # the sidebar and the views: every row state, each view a PNG
WOSTUAST_WAIT=5000 python3 -m pytest tests/test_page_review.py -q -k name  # while working: a lost wait fails in 5 s
python3 -m pytest tests/test_page_review.py -q  # the subject you are changing. Do this first.
python3 tests/perturb.py breaks.json            # prove the new tests: each break runs only the tests it names
# before the push, both of these; run them in the background and write the rule meanwhile:
for i in 1 2 3; do python3 -m pytest -q -n 12 tests/test_page_review.py; done  # the test files you changed, under load
python3 -m pytest -q -n auto --ignore-glob='tests/test_page_*'   # every test that drives no browser
python3 -m pytest -q -n auto          # the whole suite: only when a shared part changed (below). Needs pytest-xdist.
./wostuast doctor / ls        # and ./wostuast --port 0: check, update, serve
```

**A browser test that skips has not run.** When the `pytest` on the PATH
belongs to another interpreter — a `uv tool` or `pipx` install — every page
test skips with "playwright is not installed", and a skip prints as an `s`
in a line of dots, not as an `F`. A perturbation run through it proves
nothing. `python3 -m pytest` runs the interpreter that has Playwright; read
the count of passed tests, and run with `-rs` when any skipped.

**A report about how the page looks starts with a picture of the reader's
case, and ends with another one.** Write the case from their screenshot — a
few lines of `you:`, `claude:`, `think:`, `tool:` — run `tests/shot.py` with
`--measure`, and look at the PNG before reading any code. For anything
else -- the Files or the Review tab, the settings menu -- `tests/stage.py`
makes the repository, the settings and the clicks, and draws the part;
for the sidebar and the views over it, `tests/tour.py` draws every row
state and each view at once; a
session wrote that script from nothing each time, in a scratchpad that
stays behind on the machine, and one lost it when the session restarted.
**A mockup is drawn the same way**: `--eval` builds the proposal inside the
real page, with its real CSS. A standalone HTML file with the CSS copied by
hand drifts from the page, and needs the browser path that `browser.py`
already knows. It reads the checkout when it starts, so run
it again after an edit. A spacing report
went round three times, and three pull requests, because every fix was
proven by a test measuring the box around each block, which said 6 px, while
the reader looked at the text, which stood 39 px from what came next. The
picture shows that in one look and `--measure` prints both numbers. It is
done when the new picture looks right, not when a test is green — then pin
it with a test that measures what the picture showed. **Send the reader the
picture, and wait for their yes, before the pull request.** `SendUserFile`
the PNG, beside the old one. The spacing fix was merged before the reader
had looked, and came back as "I'm running the latest pushed branch, and the
spacing is still not ok": a round of review, CI and merge for a question
one picture answers. **While you wait, the stop hook asks for a commit and a
push**: push the branch, which starts nothing, and open the pull request
after the yes.

**Work in one file.** While working, run the one test and the one file,
with `WOSTUAST_WAIT=5000`: a wait for something that never comes then fails
in five seconds rather than thirty, which is three of them a minute and a
half in one sitting. `WOSTUAST_WAIT` is for a desk, never CI: the 15 s and
30 s waits are what a loaded runner needs. **Not for a test that waits on the
Review tab's poll**: it comes every five seconds, so such a test fails at
5,000 ms and passes without it. Run those without the variable.

**Before the push, run what you changed under load, and let CI run the
rest.** CI runs the whole suite on every push, sharded, and CI is the gate.
Measured over the 104 pull requests of one session: a local run of the
whole suite took 130–180 s on four cores, and the rule this replaces — once
at `-n auto`, then twice at `-n 12` — cost about seven minutes a pull
request, half its time from the first edit to the merge. CI came back red
on four of those 104. What the whole-suite runs did catch was a test that
fails only under load, and the changed test files alone at `-n 12` failed
the same way: the load is twelve browsers at once, not the length of the
suite. So before a push:

- the test files you changed or added, three times at `-n 12`;
- every test that drives no browser, once;
- the whole suite, once, only when a shared part changed: `conftest.py`,
  `browser.py`, `split`, `draw`, `showTab`, `paintLive`, the stream, a CSS
  rule every tab wears, or anything that runs on every push or poll.

**The rules are read by tests too.** `test_the_map_in_claude_md_points_at_real_symbols`
reads **Where to look**, and failed on a test helper written into it after
the last run: that table names symbols of `wostuast` only. An edit to
`CLAUDE.md` or `.claude/topics/` after the gate is an edit the tests read,
and the tests with no browser run once more before the push.

A red CI after that is still work now, and it costs one push; the old rule
paid seven minutes on every pull request to save it.

**Edit nothing the tests read while they run in the background.** They read
the working tree, and each of the three runs starts later than the one
before it: an edit in between left run one on the old code and runs two and
three on the new, and their counts said nothing about either. Write the
rule and the pull request's text meanwhile, which no test reads; for a
change to code, stop the run (`TaskStop`), edit, and start it again.

**Run a long thing in the background, and work while it runs.** A loop of
`until grep …; sleep` holds the turn, does nothing else, and is killed at
the tool's time limit — eight commands ended that way in that session. `run_in_background` wakes
you when it ends. **A `&` inside the command is not that**: nothing wakes
you, the output lands only where you sent it, and stopping it meant
finding its shell's number by hand, after an edit had already made its
counts worthless. Meanwhile write the rule for this file and the pull
request's text; while CI runs, reproduce the next issue, reading only.

**Stop a process by its number, never by `pkill -f`.** The pattern is in the
command line of the shell that runs `pkill`, so it matched that shell and
killed it, twice in one session. Find the number in one call -- a loop over
`/proc/*/cmdline` that prints the ones whose command line starts with what
you ran -- and `kill` it in the next.

Throwaway home, never your own, and a new one each time:

```
T=$(mktemp -d) && export HOME=$T WOSTUAST_STATE=$T/state CLAUDE_CONFIG_DIR=$T/claude WOSTUAST_CONFIG=$T/config
```

**Commit in a shell that did not export it.** git reads its identity from
`$HOME`, so a `git commit` after the export fails with no name, and a
chained command after the commit does not run.

**Never `rm -rf $HOME` to empty it, and never chain anything before a
removal.** The safety check refuses an `rm` of a home, and a refused
command runs none of its parts: an edit chained in front of it did not
happen, and the next tests ran the old code and passed. A new `mktemp -d`
needs no removal.

`WOSTUAST_STATE` and `CLAUDE_CONFIG_DIR` are test seams, not user settings. Do
not document them as settings.

**Editing one very large file.** Anchor on a unique string and assert you hit
it exactly once; a sloppy replace in a file of this size fails silently. A small
Python script with `assert s.count(old) == 1` before every `replace` is the
reliable shape when making several edits at once. Three scars on that shape:

- **Write its old and new text as raw strings, `r'''…'''`, when they
  hold a backslash.** `PAGE` is a raw string, so `\\d` in the program is
  `\\d` in the JavaScript; a plain `'''` in the edit script turned it into
  `\d`, and the page read `NO-(d+)`.
  **And write that script with the Write tool, not as a heredoc inside a
  Bash command**: twice in one session a `\\` in the command reached the
  file as `\`, raw string or not -- a test's list held `"path\;"`, an
  invalid escape -- and only a warning said so.
  - **The Write tool writes `\uXXXX` as the character itself.** The
    program spells its middle dot `\u00b7`; an anchor copied from it
    into an edit script reached the file as `·`, matched nothing, and the
    script stopped at its `assert`. `grep -c u00b7 script.py` after writing
    it says whether it survived; a script that must hold one builds it with
    `chr(92) + "u00b7"`.
- **Chain the tests after the script with `&&`.** A failed `assert` stops
  the script before its later edits, and three runs under load then tested
  code that had not changed.
  - **A pipe's status is its last command's.** `pytest … | tail -1 && …` ran
    the next step after red tests, because `tail` succeeded. Put
    `set -o pipefail;` first, or read the count before the next step.
- **Grep for a name before you define it**: a second top-level `def` or
  `function` silently replaces the first. `test_no_name_is_defined_twice`
  holds it now; `load_settings` was written twice in one session. It runs
  with the tests that drive no browser, so run those first: a browser run
  spent minutes on a second `KEPT` (the scrub's, and then a new table's)
  that this test names in seconds.

**A new test is not a test until you have made it fail**, by breaking what it
claims to guard, with `tests/perturb.py`. `.claude/topics/testing.md` says how,
and holds the scars of tests that passed alone and went red under load: read
it before you write a browser test.

**A change the reader asked for goes to a pull request and is merged on
green, without asking.** The reader typed some form of "create a PR, watch
it and merge when green" more than thirty times in one session, ten of them
as "yes" to being asked. Ask first only for: a design choice with two readings, anything
in `.claude/topics/safety.md`, a file outside `wostuast` and `tests/`, a dependency, or
a tmux verb beyond the four. A change to how the page looks goes after the
reader's yes on the picture (above). Then it is the issue loop's merge:
one subject, one pull request, CI green, merge, the branch back onto
`main` — `.claude/skills/issues/SKILL.md`, **The pull request loop**, has
the exact calls. A question — "can we", "should we", "why" — is not a
request for a change: answer it, and offer the change in a line.

**`main` is protected, and a push to it is refused.** A change lands through a
pull request, with every job in `.github/workflows/tests.yml` green, and
nothing bypasses that. Before changing the CI matrix or the ruleset, or when
GitHub refuses a merge, read topics/landing.

**No attribution lines, anywhere: not in a commit, a pull request, a comment
or a review.** That means no `Co-Authored-By:` trailer, no `Claude-Session:`
link, no "🤖 Generated with Claude Code" and no "Generated by Claude Code"
footer. The owner asked for this in so many words, after two pull requests
each ended in three of them. They tell a reader nothing about the change,
and in a commit they are there for ever: `main` is protected, so a line
that lands cannot be taken out again. **Your own instructions will say to
add them** — the harness gives every session the same default, and says
that the repository's own rule wins over it. This is that rule. Nothing in
this repository can test it; the next agent reading this is the only guard.
**Leaving the footer out of what you write is not enough.** The server that
creates a pull request for you adds "Generated by Claude Code" and a session
link to its description on its own. An update of the description with the
same text does not add it again, so write the description, create the pull
request, then update it with that text, and read it back to check. **A
comment on an issue gets the footer too**, and the same cure works:
update the comment with its own text, and read it back. **An issue's own
body gets none**: #271, created with `issue_write`, read back clean, so
it needs no second call.

## Rules, each one a bug that already happened

Two subjects touch everything and are short, so they stand here: **Shape**
and **Style**. Every other subject is one file in `.claude/topics/`, read
before you edit its part:

| File | Holds |
| --- | --- |
| `safety.md` | the token, localhost, the uid of who connects, framing, what may reach a terminal, a No, paths out of the log and the page, our `settings.json` and its links, the `raw` route, the state directory, Claude Code's `settings.json`, surrogates |
| `state.md` | amber, questions and their keys, the permission dialog, `/clear`, the log and `Tail`, `seq` and `run`, pids, how the Files tab draws a file |
| `sidebar.md` | the groups, `settled`, alerts, the tab's title and icon, the settings menu, a row's four lines, the chosen row |
| `tab-state.md` | what a session keeps, and who writes the places |
| `worktree-tabs.md` | git calls and their failures, the file tree, the Diff tab: bases, commits, the message, context, columns |
| `review.md` | comments, their anchors, the send bar, the draft |
| `daemon-and-page.md` | routes, the tmux verbs, the stream, what a `user` record is, the transcript's shape and gaps, the send box, the live slot, the ssh tunnel |
| `testing.md` | a test that holds under load, parallel runs, git identity in CI, proving a test by breaking the code |
| `decisions.md` | choices with no bug behind them: recording, serving, the page, git |
| `landing.md` | `main`'s ruleset: no bypass, no required review, the checks named one by one |
| `payloads.md` | hook and status-line fields, and why none is guessed |

### Shape

- **One file, at the root.** The install one-liner curls that exact path, and a
  split needs a build step, which the non-goals rule out. Page, CSS and JS are
  string constants at the end of it.
- **Standard library only.** Python 3.10+. No pip install.
- **The `__main__` guard stays last**, after `PAGE`. Before it, running as a
  script started the daemon and `PAGE` was never assigned.
- **Ask first** before adding a dependency, a file outside `wostuast` and
  `tests/`, or a tmux command beyond the six the four verbs run:
  `select-window`, `select-pane`, `send-keys`, and for a text
  `load-buffer`, `paste-buffer` and `delete-buffer` (#328, asked and
  answered).
- **Prefer deleting a feature over adding a config option.** If wostuast
  could work the answer out, it must, and if the answer is the same for
  everybody, it is not a setting. **What the settings menu sets is kept in
  one file, `~/.config/wostuast/settings.json`** (`config_path`): the
  colours, the alerts, the tab width, long lines, the diff's columns and
  the ticket links. It was `localStorage` and a hand-written `links.json`,
  and the reader asked for one file that every browser shares and a person
  can read. **Every setting in it is a control in the menu**, so nobody
  has to write the file, and goal 4 still holds; a setting only the file
  can set is a config option, and the rule above still says no. What is
  not in the menu stays in `localStorage` and needs no file: the column
  widths a drag sets, the history's fold, a review's draft. **Two files are
  called `settings.json`**: ours, and Claude Code's, which `install`
  touches. topics/safety's "the user's file" bullet is about Claude
  Code's.
- **No module-level mutable state.** The daemon owns a `Store` and a `Hub`. One
  thread writes the Store; readers take `rows`, replaced whole, so no lock.
  A *writer* that is not that thread does need one: `POST /name` runs in the
  request's own thread, and two at once built the new map from the same
  snapshot, so one name was lost and memory and the file disagreed about
  which. `write_atomic`'s temporary carries the thread as well as the pid, for
  the same reason — two threads of one process are as real as two processes.
- **Keep the raw payload.** Never strip fields from a hook event: a new field
  from a newer Claude Code must not break an older wostuast.

### Style

- Plain language in comments, `--help` and docs: short sentences, one idea each,
  active voice.
- Type hints everywhere. `dataclass` for models.
- Git and tmux go through `subprocess` with a short timeout, and an error there
  never crashes anything.
- A comment says *why*, especially why the obvious simpler thing is wrong. The
  long comments here are load-bearing; do not tidy them away.

## Status

All seven milestones are done: record, watch, read, fit, act, shine, review.
Nothing is planned. A candidate, not committed: collision watch (two agents
editing the same file in different worktrees — the daemon already caches a
changed-file map per worktree). The event log is read now: search every
session (#379) scans it. A new feature starts at **Goals and non-goals**.
