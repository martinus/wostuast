# CLAUDE.md

Only agents read this file and `.claude/topics/`. This file is the map, the
reuse index and the way of working; the rules are in `.claude/topics/`, one
file a subject.

**Read the rules file before you edit its part.** **Where to look** names
it; `grep -rn <symbol> CLAUDE.md .claude/topics` finds the rule that names a
symbol. A session loads this map and reads only the subject it works on: the
rules were one file of 50,000 tokens, loaded at every start and after every
compaction. **Never `.claude/rules/`, and never an `@` import**: Claude Code
loads both at launch (code.claude.com/docs/en/memory, "Rules without `paths`
frontmatter are loaded at launch"), and a `paths:` scope does not help,
because every rule is about the one file `wostuast`.

**Nothing durable goes in machine-local memory.** The owner works from more
than one computer; `~/.claude` memory and the scratchpad stay on the
machine. A lesson goes in this file or `.claude/topics/`, committed; a tool
worth keeping goes in `tests/`, as `shot.py` and `stage.py` did. The
scratchpad is for this session's throwaway files.

**How a rule is written.** Only agents read these files: write for one
that finds a rule by grep and acts on it. One bullet a rule, in this order:

1. the assertion, in bold: what to do, or never to do;
2. why, in one or two sentences: the failure the obvious alternative
   caused, or the reader's decision and what it rules out;
3. the symbols to grep, the test that holds it, and the issue (`#N`).

Leave out the story: who found it, in which session, after how many runs,
what was tried first. `git log --grep '#N'` and the issue keep that. Keep a
number only when it sets a limit or proves the why. Name the symbols in the
rule itself, so `grep -rn tmux_send .claude/topics` finds it. A rule goes in
the file of its subject; a new subject is a new file, a row in **Where to
look** and one in the list under **Rules**.

**A new scar goes into the bullet it belongs to.** Grep for the symbol
first. The same kind of bug again adds its test name and a clause to that
bullet, or a nested item when it has a why of its own. A new bullet is for
a new kind of bug. Every fix writes a rule, so a file that grows by a
story a fix is soon too long to read whole.

**Keep the why, cut the story.** The why stops the next agent from making
the plausible wrong fix again; the story does not. A rule without its why
is broken by the first agent that thinks it knows better.

**State no number a person would have to maintain; give the command that
answers it.** A stale fact is believed: three numbers here once went 40%
stale unnoticed. A measurement ("2,500 lines took 144 ms") is not that: it
records an experiment, and stays true.

**This file and `.claude/topics/` are the only design document.** `PLAN.md`,
the brief the program was built from, was deleted once its seven milestones
were done: parts had gone false, and it outranked the rules. What still held
is **Goals and non-goals** and `.claude/topics/decisions.md`;
`git show d440d2f:PLAN.md` is history, never authority. An old commit, issue
or comment that cites `PLAN.md`, or this file before the split, is answered
by these files. Where they and the tests disagree, the tests are right, and
the rule is fixed in the same commit.

## Where to look

Find your row before editing, not after the tests go red. "topics/<subject>"
is `.claude/topics/<subject>.md`: read the whole file, not only the bullet
grep found; the bullets beside it are the same part's other rules.

| About to touch | Read |
| --- | --- |
| a new feature, or a request that bends what the program is | **Goals and non-goals** below — a feature that needs a non-goal is left out |
| where new code goes: a route, a view, a field the page reads, a second way to read a fact | **Principles** below, and the test that holds each one |
| `install`, `bring_up_to_date`, `setup_checks`, `SETUP_CHECKS`, `Check`, `SetupFacts`, `START_FIRST`, `START_AFTER`, `fetch_newest`, `newest_program`, `runs_installed`, `own_version`, `unreadable`, `cmd_serve`'s start, `one_daemon`, `daemon_lock_path`, `save_settings`, `write_atomic`, `remove_status_line`, `then_of`, `shell_words` | topics/safety-install: Claude Code's `settings.json` is the user's file, not ours |
| `hook_source`, `HOOK_PARTS`, `HOOK_HEAD`, `hook_path`, `hook_command`, `is_hook_file`, `write_program`, `install_behind`, `hook_files_missing`, `program_files`, `GONE_VERBS`, `runs_hook_file`, `STATUS_PARTS`, `status_program_path`, `is_status_file`, `then_in` | topics/safety-install: the hooks run the installed copy, and the hook file is made from it |
| `config_path`, `load_config`, `save_config`, `config_payload`, `tell_config`, `page_json`, `POST /api/settings`, `keepSetting`, `takeSettings`, `putLinkRows`, `saveLinks` | topics/safety-install: our `settings.json`, written from the page; topics/sidebar for the menu |
| `cmd_hook`, anything on the hook path | topics/safety, first two bullets. It must never print and never block. |
| a hook or status-line field name | topics/payloads, and `tests/fixtures/README.md` |
| `session_json`, `cmd_wait`, `pick_session`, `wait_states`, `agent_pid`, `cmd_status`, the event log's shape, polling, a library, SQLite, the Agent SDK, stream-json, channels, an `http` hook, a hook decision, OpenTelemetry | topics/decisions |
| `getJson`, `ask`, `post`, a fetch of the page | topics/daemon-and-page: the page asks the daemon one way |
| `ROUTES`, `find_route`, `Serving.route`, `Serving.dispatch`, `Answer`, a `verb_` function, `POST_MAX`, any `POST`, `allowed`, `origin_ours`, `Serving`, `reply`, `another_user`, `socket_owner`, `asked`, `body_length`, `too_big` | topics/safety: the token, localhost, the uid of who connects, framing |
| `tmux_send`, `SEND_MAX`, `typing_trouble`, `prompt_landed`, `whyNoText`, `recallSent`, `tmux_jump`, `tmux_interrupt`, `sending`, `startSending`, `claim`, `typing_lock`, `CONTROL_CHARS` | topics/safety-typing: what may reach a terminal, one send at a time |
| `answer`, `fitPicks`, `ask_keys`, `shows_preview`, `preview_kind`, `tmux_keys`, `askKeys`, `previewText`, `submitAsk`, `state.picked`, `state.answered`, `forgetAnswered` | topics/state: the question bar's bullets — the keys are measured |
| `decline`, `read_permission`, `call_answered`, `drawPermission`, `paintDecline`, `Session.permission`, `Session.dialog`, `cannot_type`, `whyNotTyped`, `Declined` | topics/safety-typing: a No is Escape, and the reason waits for proof; topics/state for `Session.permission` |
| `approve`, `give_yes`, `wait_for_yes`, `hook_waits`, `lock_held`, `daemon_running`, `always_offered`, `allow_for`, `always_label`, `ALWAYS_MODES`, `approvals_dir`, `ALLOW`, `NOT_APPROVED`, `APPROVE_WAIT`, `ASK_SHAPE`, `submitPermission`, `permissionPick`, `Approved` | topics/safety, its first bullet: the hook says allow only for its own dialog, after the reader's Yes |
| `plan_of`, `lastPlan`, a block of kind `plan`, `ExitPlanMode` | topics/state, the plan under `Session.permission`; topics/payloads for what the request carries |
| the Markdown scrub (`scrub`, `KEPT`, `textFor`, `safeLinks`), `linkTickets`, `linkOne`, `nextMatch`, anything that inserts what an agent wrote | topics/safety: the page never trusts what an agent wrote |
| `remote_url`, `config_entries`, `config_section`, `config_value`, `CONFIG_MAX`, `hide_secrets`, `clip_hidden`, `SECRET_SHAPES`, `tool_target` | topics/safety: a remote URL and a command reach the page without their secrets, and a long one costs no time |
| `build_report`, `named`, `tool_named`, `labelled`, `exception_named`, `REPORT_KINDS`, `private_paths`, `installed_files`, `cmd_files` | topics/safety-install: the report holds names and counts only, and one list of the files |
| `resume_command`, `drawResume`, `read_worktree_file`, `why_unread`, `is_listed`, `worktree_target`, `inside`, `SHOWN_AS`, the `raw` route, `askFile`, `FileText.stamp` | topics/safety: a path out of the page is input |
| `Store`, `Session`, `_on_*`, `become`, `save_names`, `_clear_attention`, `running_tasks`, `TASK_ENDED`, `read_ask`, `place`, `home`, `link_clear`, `link_move`, `background_start`, `untasked`, `followClear`, `Session.pane`, `Session.pid`, `reads_terminal`, `looks_like_claude` | topics/state |
| `Transcript.add`, `add_queued`, `user_block`, `read_user_text`, `isMeta`, `shell_output`, `command_output`, `putShell`, `transcript_shapes`, `SILENT_RECORDS`, `read_patch`, `putToolDiff`, `PATCH_SHOWN` | topics/transcript: what a `user` record really is, and the queued `attachment` |
| `Tail`, `EventFollower`, `archive_log`, `archived_events_paths`, `log_handles`, `HISTORY_FOLDED`, `folded_long_ago`, `append_event`'s `stamp`, `fold`, `forget_quiet`, `reload_git` | topics/state: the log is never thrown away, and every line is folded once, in order |
| `needsYou`, `toggleSnooze`, `Session.snoozed`, `snoozed_at`, `Store.snooze`, `snoozed_path`, `read_snoozed` | topics/marks: a snooze is a mark on one wait |
| `Marks`, `Marks.load`, `Marks.onto`, `read_json`, `read_moments`, `is_number`, a sixth kind of mark | topics/marks: the reader's marks are one store; `tests/test_marks.py` walks every kind |
| `Session.unread`, `ended_at`, `seen_at`, `Store.see`, `seen_path`, `read_seen`, `setUnread`, `markSeen`, `keptUnread` | topics/marks: unread is a mark on a finished turn |
| `putNewLine`, `landOnNew`, `paint`, `land`, `landTranscript`, `landFiles`, `landDiff`, `toLand`, `newSince`, `newDown`, `.newline` | topics/transcript: the "new" line, and where a transcript lands |
| `search_log`, `prompt_said`, `parse_search`, `search_day`, `SEARCH_MAX`, `SEARCH_FILTERS`, `drawSearch`, `runSearch`, `drawResults`, `goToNear` | topics/decisions: search is a scan of the event log |
| `saved_path`, `saved_entry`, `Store.save`, `SAVED_MAX`, `SAVED_PREVIEW`, `putSave`, `drawSaved`, `takeSaved`, `askSaved`, `goToTs` | topics/marks: a saved turn |
| `last_answer`, `verb_last`, `LAST_MAX`, `askLast`, `drawFeed`, `openFeed`, `closeFeed`, `VIEWS`, `toggleView`, `drawUnread`, `drawFeedLink`, `viewLink`, `fitViews`, `VIEW_FITS`, `drawViewTitle`, `leaveFeed`, `putCard`, `unmarked`, `state.feed`, `infeed`, `putBoard`, `layoutCards`, `CARD_MIN` | topics/marks: "All unreads" |
| `remind_at`, `Store.remind`, `reminders_path`, `REMIND_MOST`, `reminderDue`, `reminderSet`, `armReminders`, `endReminder`, `serverNow`, `openReminders`, `REMIND_IN`, `remindMoment`, `customReminder`, `REMIND_DAYS`, `dayName`, `readTime` | topics/marks: a reminder is the snooze's twin with a clock |
| `Session.title`, `first_prompt`, `Marks.page_name`, `Marks.over`, `Store.rename`, `clean_name`, `type_rename`, `read_name_entries`, `keepRename` | topics/marks, the store of names; topics/send-and-keys for `name`; topics/safety-typing for the typing |
| `fillKids`, `kidsOf`, `putKid`, `topSessions`, `childIds`, `Subagent`, `note_subagent`, `end_subagents`, `SUBAGENTS_HELD`, `Store.parent_of`, `claude_from`, `started_by` | topics/sidebar: what an agent starts is a line under its row; topics/state for the hook's `started_by` |
| `onSessions`, `askUnread`, a draw that fetches, rings or writes, the draw guard in tests/browser.py | **Principles**, 3; topics/sidebar, "The counts are about every session" |
| `newRow`, `fillRow`, `setIcon`, `rowName`, `renameRow`, `BANDS`, `listedSessions`, `notifyAbout`, `dragWidth`, `dragHeight`, `dragEdge`, `putFold`, `paintFold`, `unfold`, `FOLDS`, `markRow`, `tileTitle`, `tileCard`, `settled`, `remote_url`, `openGrip`, `.row.chosen`, `tabTitle`, `paintIcon`, `iconPicture`, `robotPicture`, `drawLogo`, `ALERT_ICON`, `tellAbout`, `waitsFor`, `shown_prompt`, `putSettings`, `paintSettings`, `putQuick`, `QUICK`, `settingsNow`, `keepWidth`, `keepWrap`, `measureScrollbar`, `drawBell`, `putChoice` | topics/sidebar |
| `.turn`, `.bubble`, `.turnacts`, `putCopy`, `putTurnRow`, `mapDays`, `GLIMPSE`, `putToFoot`, `putCodeCopies`, `foldedHead`, `putFoldBar`, `foldRun`, `runOf`, `fillCallSum`, `RUN_FOLDS` | topics/transcript-look: the transcript's shape; a run of calls is one line |
| `Commands`, `command_used`, `front_matter`, `read_command`, `command_text`, `after_front`, `front_end`, `real_md`, `COMMAND_TEXT_MAX`, `drawCommands`, `useCommand`, `putCommand`, `commandOf`, `blankCommands`, `plugin_dirs`, `enabled_plugins`, `commandKey`, `projectSessions`, `projectName`, `useTarget`, `toggleView`, `project_dirs`, `claude_dir`, `slashSpot`, `followSlash`, `takeSlash`, `slashKey`, `enterTakes`, `closeSlash`, `#slash`, `sizeSay`, `.sendside` | topics/send-and-keys: completing a `/` in the send box, and its size; topics/safety for `COMMAND_SHAPE` |
| `state.files`, `state.turns`, `state.diffs`, `savePlace`, `usePlace`, `PLACE_FIELDS`, `blank…()`, `diffKey` | topics/tab-state |
| `git_facts_many`, `git_facts_or_failed`, `GitReader`, `worktree_doing`, `own_git_dir`, `worktree_files`, `walk_ignored`, `written_since`, `hex_dump`, `hexWide`, `onlyChanged`, `openDirs`, `dirsWithChanges`, `git_status`, `apply_git_facts`, `Files`, `fillList`, `fuzzy`, `putName`, a diff, `parse_diff`, `join_type_change`, `statusWord`, a git call, `ICONS`, a file's drawing (`fillCode`, `CODE_WHOLE`, `PAINT_MAX`, `tooDenseToPaint`) | topics/worktree-tabs; topics/state for how a file is drawn |
| `worktree_diff`'s `of`, `base` and `held`, `DiffBuild`, `branch_log`, `one_commit`, `committed_half`, `Daemon.diffs`, `pick_base`, `list_refs`, `head_branch`, `ahead_behind`, `rank_bases`, `recallBase`, `branch_commits`, `since`, `pickDiff`, `putDiffTree`, `pairRow`, `wordDiff`, `paintDiff`, `markSpaces`, `SPACE_ARGS`, `openInFiles`, `.dtext`, `putMessage`, `putReadAs`, `stepat`, `blockSig`, `settle`, `readerAt` | topics/worktree-tabs, the Diff tab's own bullets; topics/decisions for the base |
| `putComment`, `anchorOf`, a review comment, `putCommentList`, `putElsewhere`, `diffAnchors`, `inWorktree`, `diffLineAnchor`, `drawReviewBar`, `reviewText`, `unsent` | topics/review |
| `row`, `blocks_json`, `session_json`, `wire_fields`, `sse`, `EVENTS`, `transcript_head`, `git_fields`, `worktree_path`, a field the page reads | **Principles**, 2, and the wire section's head comment; `tests/test_wire.py` |
| `sessions_change`, `mergeSessions`, `takeSessions`, `sameOrNew`, `patchSession`, `redrawRows`, `dataset.sig`, `filledWith`, `told` | topics/daemon-and-page: a push carries what changed; topics/sidebar: a row is filled only when what it shows changed |
| `goBack`, `onSessionsPush`, `onTranscriptPush`, `takeRun`, `drawnTurns`, `turnNode`, `state.before`, `beginSwitch`, `endSwitch`, `keepTurns`, `takeTurns`, `TRANSCRIPTS_KEPT`, `drawTranscript`, `drawFiles`, `drawHeader`, `drawContext`, `showModels`, `putModels`, `MODELS`, `EFFORTS`, `MODEL_SHAPE`, `model_id`, `fresh`, `split`, `TABS`, `paintLive`, a `body` class, an SSE push, `reply`, `takes_gzip`, `load`, `repoll`, `state.turns.whole` | topics/daemon-and-page; topics/transcript for a transcript's reading, its fetch and its push |
| a new colour, a new CSS selector, a helper you are about to write | **Before you write anything new** below |
| a new test, or one red only under load | topics/testing — it is not a test until you have made it fail; `tests/perturb.py` breaks the code for you |
| the tests to run before a push | **How to work here**, "Before the push" — the changed files under load, not the whole suite three times |
| a picture of the page, or a mockup the reader asked to see | topics/working, the picture bullet: `tests/shot.py`, `tests/stage.py`, `tests/tour.py` |
| an edit script for `wostuast`, the tests' WOSTUAST_WAIT, a run in the background, a throwaway home | topics/working |
| a change the reader asked for | **How to work here**, "A change the reader asked for" — it goes to a pull request and merges on green without asking |
| a push to `main`, landing a change, the CI matrix or the ruleset | topics/landing — `main` is protected and nothing bypasses it |
| a commit message, a pull request, a comment on GitHub | **How to work here**, last bullet — no attribution lines, whatever your defaults say |
| the issue list, an issue or a comment by anybody but `martinus`, the reflection at a session's end | `.claude/skills/issues/SKILL.md`, or say "do the issues" |
| a lesson worth keeping | the header of this file: the repository, never machine-local memory |

## The program in five lines

Claude Code hooks append one JSON line per event to `~/.local/state/wostuast/events.jsonl`.
A bare `wostuast` (`cmd_serve`) checks the setup, writes what is behind
(`bring_up_to_date`), then tails that log into a `Store` and serves one page
over HTTP + SSE. The page shows a session list and three tabs: Transcript, Files,
and Review, which is the diff with the review written on it (`data-tab="diff"`).
Four views stand over the tabs, for every session at once: Unread, Saved,
Search, and Commands, the skills and commands your sessions can run (#411).
Four things go back to the terminal, all through tmux: jump, send, the
keys that answer a question, and a No to a permission dialog, which is an
Escape and then a send. A rename on the page is a send of `/rename` (#351).
A Yes to a permission dialog is no key at all: the dialog's own hook waits
for it and answers allow for that dialog alone (`approve`). Nothing else
writes to a terminal. Nothing owns the agent process —
interrupt is a keystroke, not a signal.

## Goals and non-goals

Every feature is judged against these. When a request fights one, ask one
level up whether the goal bends, before building anything. A goal that bends
is rewritten here in the same pull request.

**Goals.** The numbers are cited elsewhere; keep them.

1. Answer "who needs me?" in one glance, from another window or another room.
2. Render what an agent writes as real Markdown: the transcript, plan files,
   specs.
3. Show a worktree's changes without opening an editor.
4. Stay small: one Python file, the standard library, no daemon needed to
   *record* events, no config file needed to run, a one-line install and a
   one-line uninstall. Our `settings.json` is the one optional file: the
   settings menu writes it, nobody has to (**Shape** says why it is allowed).
   The hook file `install` writes (`hook_path`) is no second source:
   `hook_source` copies it out of the one file, `uninstall` removes it, and
   it costs 33 ms an event against 131 for the whole program (#271).
5. Look good enough that a screenshot would sell it. **One ships** (#521):
   `docs/cover.png`, at the top of the README, drawn by `tests/tour.py` from
   made-up sessions, never real ones -- a picture of real agents is
   somebody's work. Draw it again when the page changes how it looks; the
   command is under the picture.

**Non-goals. If a feature needs one of these, leave the feature out.**

- **Owning the agent process.** Nothing here spawns, wraps or kills it; tmux
  owns the PTY. Typing into a pane is not owning it: jump, send, the answer
  keys and a No's Escape are allowed, a signal is not.
- **A terminal emulator** (no xterm.js). A Peek tab that showed a still
  capture of the pane was removed: the real pane is one keystroke away.
  `capture-pane` went with it.
- **A Yes the reader did not give, or one that keys carry.** The page says
  Yes only as the reader's click, and only through that dialog's own hook
  (`approve`, `wait_for_yes`): keys land on whichever dialog is up, and the
  hook's allow on its own dialog only (topics/safety, first bullet, says
  how). The reader asked for Yes once the page showed the whole request, and
  chose the hook. **"Yes, and don't ask again" is Claude Code's own
  suggestion, never a rule of ours** (`always_offered`, `allow_for`; the
  same bullet). No mode that turns every prompt off, no plan, no question. An
  `AskUserQuestion` is the agent's own question: the page types nothing until
  the reader submits.
- **Agent-to-agent messaging, teams, orchestration, cache telemetry.** Showing
  the spend the status line sends is in; accounting is out. **So is a spend
  limit**: one shipped, typed into a terminal with nobody watching, and went
  with the Session tab that set it. `git show` the commit that removed the
  Session tab before building one again.
- **Knowing a worktree layout.** A session is an agent standing in a
  directory, nothing more. No dependency on `gra`.
- **Electron, Tauri, React, or any build step**, a Python dependency outside
  the standard library, or a JavaScript library vendored into the file.
- **A review that goes anywhere but the agent.** No GitHub API, no pull
  request, no posting. It is pasted into the pane of the agent standing in
  that worktree, and the reader reads every byte of it first.

## Principles

Five, each held by a test. A goal says what the program is for; a principle
says where its code goes, so a new feature lands in the one place made for
it. They came from a review of the whole file (#535): its bugs were each one
fact with two homes. A change that cannot keep one says so in its pull
request, and names the principle.

1. **Data flows one way**: events, then the fold, then rows, then the wire,
   then the page. The fold does no I/O: file, git and `/proc` reads happen at
   the edges, in the named steps of `Store.refresh` (`follow`, `settle`,
   `reload_git`, `render`), and a write the fold needs waits until it is done
   (`save_names`). A change of state is `become`. `test_the_fold_does_no_io`
   folds an event of every handler with I/O made to fail;
   `test_the_guard_folds_every_handler_and_both_links` holds that it is given
   every path.
2. **Each shape the page receives is defined in one place**: the wire
   section (`row`, `blocks_json`, `session_json`, `wire_fields`, the
   `EVENTS`). Its head comment names the five dataclasses that go out whole;
   anything else is written key by key.
   `test_a_block_sends_only_the_fields_it_names`,
   `test_the_page_reads_only_session_fields_the_row_sends`,
   `test_the_page_listens_for_every_event_the_stream_sends`,
   `test_the_row_and_ls_json_say_the_same_of_a_session`,
   `test_only_the_wire_section_turns_a_dataclass_into_json`.
3. **A draw only reads state.** Only code that loads data or handles a click
   changes `state`; what a change to the sessions does besides drawing is
   `onSessions`. `DRAW_GUARD` in `tests/browser.py` -- an init script of every
   context, so the draws at load count too (#577) -- wraps `paint` and every
   `draw…` but `draw`, records each fetch, alert, storage write and change to
   `state` they make (four levels deep, into each array, `Set` and `Map`, and
   from a timer they set when it fires, #573), and fails on one not in
   `DRAW_EFFECTS_ALREADY`, a ratchet #573 emptied. Every browser test that
   opens a page with `opened` checks it. Every field of `state` is declared
   in its literal: `test_every_field_of_the_pages_state_is_declared`.
   **`draw()` is two steps, `paint` and then `land`** (#573), as
   `Store.refresh`'s are: a mark of where to go -- a link to a block, a file
   asked for, the "new" line -- is used up once landed on, and that write is
   the land's, each tab's own in `TABS` (`landTranscript`, `landFiles`,
   `landDiff`). A build leaves what its land needs on the pane (`toLand`); the
   Review tab lands once a build, not on every push.
4. **Every extension point is a table**: hook handlers (`_HANDLERS`), session
   verbs (`GET_VERBS`, `POST_VERBS`), tabs (`TABS`), views (`VIEWS`), routes
   (`ROUTES`). A test walks the table, so a new entry is tested without
   anyone writing its test:
   `test_every_view_opens_draws_and_gives_the_session_back`,
   `test_every_route_refuses_what_it_must`.
5. **One reader for each fact.** Where two parts read the same fact, they
   call one function: `prompt_said` for a prompt, `git_status` for
   `git status`, `apply_git_facts` for a reading of git, `getJson` for an
   answer of the daemon. `test_search_reads_a_prompt_as_the_fold_does`,
   `test_only_get_json_calls_fetch`,
   `test_the_row_counts_the_changed_files_the_files_tab_marks`,
   `test_only_one_function_runs_git_status`.

**How a test holds a principle, strongest first.** A test that walks a
table checks each entry. A differential test gives two readers of one fact
one hard case and asks that they agree; write it first and see it fail. A
guard at run time -- a fold with I/O made to fail, a draw that records its
fetches -- checks only the paths the tests run, so it comes with a test that
each path is run. A static check of the source's form is the weakest: moving
code satisfies it.

**A ratchet is a list of known breaks that may only get shorter**, like
`LONGER_ALREADY`. It stops the code sliding back, and cleans nothing:
`LONGER_ALREADY` gained and lost no entry in its first eleven days, and
`drawSessions` stood at exactly its limit. So:

- **A guard lands in the pull request of the refactor that empties most of
  its list**, never alone before it: a list of thirty breaks nobody works on
  is noise.
- **Each entry says why it is there**, in a comment beside it or above the
  list.
- **A pull request that adds an entry says why in its description.** Adding
  one is the cheapest way to turn a red test green, and the diff is the only
  thing that shows it.

## Layout

| Path | What it holds |
| --- | --- |
| `wostuast` | The whole program: Python, then `PAGE = r"""` and the HTML/CSS/JS. Five figures of lines — `wc -l wostuast` rather than a number here that rots. |
| `tests/conftest.py` | Every fixture, including the page ones (`page_at`, `repo_page`, `big_page`, `in_pane`, `no_pane`, `pair_at`, `past_at`) and `event()`. |
| `tests/browser.py` | The shared Chromium, `opened`, `own_context`, `show_tab`, and the other page helpers. No fixtures. `WAIT` is `WOSTUAST_WAIT`. |
| `tests/shot.py`, `stage.py`, `tour.py`, `scale.py`, `claude_pane.py`, `page_coverage.py`, `perturb.py` | Tools, not tests. topics/working, "The tools in `tests/`", says what each does and takes. Each has a `tests/test_<name>.py` that keeps it working. |
| `tests/test_page_*.py` | Browser tests, one file per subject: transcript, sidebar, theme, tabs, files, diff, review, act, commands. |
| `tests/test_*.py` | Everything that needs no browser. Named after what it tests. |
| `tests/fixtures/README.md` | The hook and status line payload fields. |
| `README.md` | What a user reads first: what wostuast is, why, how to install it, and a short tour. Short on purpose (#521): a detail goes in the guide. |
| `docs/GUIDE.md` | Everything a user can look up: each part of the page, the keys, the settings, the commands, `ls --json`, the files, safety, the FAQ. Keep in step with the commands. |
| `docs/cover.png` | The README's picture: `tests/tour.py`'s transcript view, made-up sessions. |
| `ARCHITECTURE.md` | What a person reads to learn how the program works and why, with diagrams. It has no authority: where it and these rules or the tests disagree, they are right, and it is fixed in the same pull request. A change to what it draws -- a route, a state, a verb, a file on disk, a hook event -- updates it too. |
| `.claude/topics/*.md` | The rules, one file a subject: safety, safety-typing, safety-install, state, sidebar, marks, tab-state, worktree-tabs, review, daemon-and-page, transcript, transcript-look, send-and-keys, testing, working, decisions, landing, payloads. **Where to look** routes to them. |
| `.claude/skills/issues/SKILL.md` | How to work the issue list: the owner's issues only, group, reproduce, ask, prove, review, merge on green, read the list again, then reflect on the session and land what is clear. Invoked as `/issues`, and by "do the issues". |
| `.github/workflows/tests.yml` | The only CI: a pytest matrix over 3.10–3.13, four sharded browser jobs that record what they ran of the page script, and `browser`, the aggregator the branch rule requires. It fails on a red shard, and on page code no shard ran (#579, #600). No job names a test file: naming one broke the browser job when a file was renamed, so the shards split on a hash of the test id. |

### Finding code in `wostuast`

Every section starts `# --- name: one line ---` (Python) or `// --- name ---`
(page). `grep -n "^# --- \|^// --- " wostuast` prints the whole map; run it
before grepping for a symbol.

## Before you write anything new

This list exists because each entry was re-implemented once already.

**Page helpers**

| Want | Call |
| --- | --- |
| "has this changed since I drew it?" | `fresh(box, which, key)` — do not hand-roll a `dataset` compare |
| change a session on the page | `patchSession(id, fields)` — never a write in place: every session is frozen, and the sidebar compares them by object |
| make an element | `put(parent, tag, cls, text)` — a button it makes is `type="button"` already |
| scattered-letter match | `fuzzy(text, query)` → `{score, at}` or null |
| the items in a list whose path matches the find box | `hits(items, pathOf)` — keeps the caller's order; `pick(names)` is the same sorted best-first |
| walk a diff's lines with their numbers | `walkHunks(one, onHunk, onLine)` |
| the two-column tab frame | `split(box, tab, bodyClass)` → `[list, pane, note, foot]`; the list also carries the tab's name as a class |
| the rounds of a conversation | `rounds()`, `glimpse(text)` |
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
| Markdown or text, over what is read | `putReadAs(parent, asText, pick, textTitle)` — a "txt" toggle |
| one button lit while what it says is on | `paintToggle(button, on)` — the title says on or off |
| the places a reader can go | `state.files.places` — the names and the directories |
| bytes, or a date a person reads | `sizeOf(bytes)`, `whenOf(seconds)` |
| a count read at a glance, "2.4k" | `roughly(n)`; the lines of a text without splitting it, `lineCount(text)` |
| "1 file", "3 replies" | `counted(n, one, many)` — `counted` in Python too |
| this browser's storage, which may refuse | `stored(key)` → "" when nothing; `store(key, value)` forgets an empty one |
| a diff's files in the order its tree reads | `treeOrder(found, pathOf)` — folders first at every level |
| which words of a changed line changed, and marking them | `wordDiff(was, now)` → two lists of runs or null, then `markWords(cell, runs)` |
| cards in as many columns as fit, newest along the top | `putBoard(parent, cls)`, `putCard` into it, then `layoutCards(board)` |

**Python helpers**: `path_label`, `clip`, `run` (subprocess with a timeout),
`private_dir`, `safe_transcript`, `worktree_root`, `is_listed`,
`inside`, `CONTROL_CHARS`, `ESCAPE_CODES`, `GONE_STATES`, `STATE_WORDS`.

**Test helpers**: `run_installed(["hook"], stdin)` runs the hook file or the
status file this checkout makes, as Claude Code does -- the hook under a
stand-in `claude` whose stdin is a terminal, or a pipe with `keys="pipe"`
(`as_claude`). `conftest.event(name, sid=..., **extra)` builds a hook event
as the log holds it, with a `cwd`, a `pane`, a `pid` and a `ts`;
`conftest.bare_event` builds one with only the fields named, as Claude Code
hands it to the hook, and an event that must carry no pane. Never hand-write
the dict: `test_no_test_writes_a_hook_event_by_hand` fails on one that
`EVENTS_BY_HAND` does not hold (#599). **To call the program from a scratch
script, `sys.path.insert(0, "tests")` and `from conftest import wostuast`**:
a `SourceFileLoader` of its own, without the module in `sys.modules`, fails at
the first `@dataclass`. `conftest.record(kind, text, ...)` builds a
transcript record -- `you`, `claude`, `think`, `tool`, `result` -- and
`conftest.records(...)` makes them the lines of a file; never hand-write
those either: one ended in a backslash and an `n` rather than a newline, and
the reader waited on it for ever. `conftest.said(args, rest)` is what a
runner that records keeps of one call, with the text `tmux_send` hands
`load-buffer` on stdin; `conftest.typed(seen)` gives those texts back, and
`conftest.into_pane(seen)` every call that put something into a pane. A
runner that records `list(args)` alone has lost the text. `browser.py` has
`opened` (`with opened(where) as page:`, and `tab="diff"`), `own_context` and
`load` for a test that needs the context before the page, `show_tab`,
`comment_on_first_line`, `two_rows`, `rgb`/`contrast`, `numbers`,
`open_code`, `stays` (the one fixed wait: proving that nothing comes),
`frames` (the next frames a page draws), `pixels` (the colours a
`page.screenshot` drew: a gradient's shape is in no computed style), and
`spy_on_note`.

**CSS**: `.verb` (button; `.verb.quiet` is the same shape a size down, for a
button that only changes what is on screen), `.choice` (one control in parts,
the part in force pressed: `putChoice` and `paintChoice`; the settings menu
uses it), `.toggle` (one button lit while what it says is on: `paintToggle`;
`putQuick` and `putReadAs` use it), `.link` (small text button), `.acts` (what
you can do to a comment, at its right edge), `.find`/`.findslot`, `.empty`,
`.nohits`, `.note`, `.comment`. **Every colour is a variable**, and a `:root`
block is the only place a colour may be a number:
`test_every_colour_outside_the_palette_is_named`. It reads an issue number
in a CSS comment as a colour too, so a comment in the CSS says `issue 333`,
never `(#333)`. Derive a tint or a ring with `color-mix`, never by copying an
rgb triple. **The fixed face is for machine text only** (#448): code, a diff,
a file, a command, the send and find boxes, a sha, a key. A time, a count, a
name, a button, a tab's title, a note is `--sans`, with `tabular-nums` where
digits must not dance; every list on the left is `--narrow`. The `:root`
comment by `--narrow` says it once;
`test_the_fixed_face_is_for_machine_text_only` holds it. **A control that
shows on hover is `display: none` until then, or out of the flow -- never
`opacity: 0` in it**: invisible, it keeps its room, and cut long names short
and moved "claude" out of line with its time (#373, #377).

Three page functions are about matching, and they are easy to confuse:
`matches` asks whether a transcript block matches, `matching` filters the
file tree, `hits` filters any list by path. A fourth word for the idea is how
one of them gets shadowed: that happened, and failed fifty browser tests.

**Before adding a CSS rule, grep for the selector.** A class already in use
takes the new rule's look too: `.turn` got a second slide animation;
`.plus`, given to the review's hover button, was already the green "+3"
beside a changed file, and every count became an invisible 18×18 box; `.tab`,
given to the empty mark before a tab in code, was the tab row's button, and
its 24 px of padding doubled every first tab. `.row .dot` already had its
transition.

## How to work here

```
python3 tests/shot.py case.txt out.png --measure  # a report about the transcript: look first, about 1 s
python3 tests/stage.py out.png --commit 2 --review  # a report about the Review or Files tab (--tab files --open PATH)
python3 tests/tour.py out/ --view later --eval mock.js  # the sidebar and the views: every row state, each view a PNG
python3 tests/scale.py --sessions 500 --page  # how a start, a tick, a push and a redraw scale: before and after
WOSTUAST_WAIT=5000 python3 -m pytest tests/test_page_review.py -q -k name  # while working; topics/working says when not
python3 -m pytest tests/test_page_review.py -q  # the subject you are changing. Do this first.
python3 tests/perturb.py breaks.json            # prove the new tests: each break runs only the tests it names
python3 tests/page_coverage.py                  # what no browser test runs of the page script: the browser suite, once
# before the push, both of these, in the background ("Before the push", below,
# says what each flag is for). $S is the session's scratchpad:
set -o pipefail; for i in 1 2 3; do python3 -m pytest -q -n 12 -rf tests/test_page_review.py | tee -a $S/gate.txt | grep -E "^FAILED|passed|failed"; done
set -o pipefail; python3 -m pytest -q -n auto -rf --ignore-glob='tests/test_page_*' | tee -a $S/gate.txt | grep -E "^FAILED|passed|failed"
set -o pipefail; python3 -m pytest -q -n auto -rf | tee -a $S/gate.txt | grep -E "^FAILED|passed|failed"  # the whole suite: only when a shared part changed (below)
./wostuast doctor / ls        # and ./wostuast --port 0: check, update, serve
```

**A browser test that skips has not run.** When the `pytest` on the PATH
belongs to another interpreter -- a `uv tool` or `pipx` install -- every page
test skips with "playwright is not installed", and a skip prints as an `s` in
a line of dots, not as an `F`. `python3 -m pytest` runs the interpreter that
has Playwright; read the count of passed tests, and run with `-rs` when any
skipped. A perturbation run through a skipping `pytest` proves nothing.

**Read topics/working before a task it covers**: a picture or a mockup of
the page, `WOSTUAST_WAIT` and the Review tab's poll, a run in the background
and stopping one, a throwaway home, and an edit script for `wostuast` -- so
before almost any edit of the program.

**Before the push, run what you changed under load, and let CI run the
rest.** CI runs the whole suite on every push, sharded, and CI is the gate.
What a local whole-suite run catches is a test that fails only under load,
and the changed test files alone at `-n 12` fail the same way: the load is
twelve browsers at once, not the length of the suite. Three whole-suite runs
cost about seven minutes a pull request. So before a push:

- the test files you changed or added, three times at `-n 12`;
- every test that drives no browser, once;
- the whole suite, once, only when a shared part changed: `conftest.py`,
  `browser.py`, `split`, `draw`, `showTab`, `paintLive`, the stream, a CSS
  rule every tab wears, or anything that runs on every push or poll.

**A gate chained with `&&` starts with `set -o pipefail;`**: a pipe's status
is its last command's: `pytest … | tail -1 && …` committed and pushed after
"1 failed", because `tail` succeeded (#569). **Use `-rf`, never `tail -1` alone**, so a failure
has a name once the run is over, and **`tee` the whole output first**: `-rf`
gives the name and one clipped line, and the `grep` throws the traceback
away (`test_a_ticket_in_a_rows_name_or_branch_is_a_link` failed once, #595,
and why could no longer be read).

**One gate at a time on the machine.** Two whole-suite runs side by side took
eleven minutes, not seven, and each failed a test the other did not
(`test_another_file_opens_at_its_top`). Start the next pull request's gate
when the last one's has ended; build and prove meanwhile.

**The rules are read by tests too.** `test_the_map_in_claude_md_points_at_real_symbols`
reads **Where to look**, which names symbols of `wostuast` only. An edit to
`CLAUDE.md` or `.claude/topics/` after the gate runs the tests with no
browser once more before the push. A red CI after that is still work now; it
costs one push.

**A new test is not a test until you have made it fail**, by breaking what it
claims to guard, with `tests/perturb.py`. `.claude/topics/testing.md` says
how, and holds the scars of tests that passed alone and went red under load:
read it before you write a browser test.

**A change the reader asked for goes to a pull request and is merged on
green, without asking.** The reader asked for exactly that more than thirty
times. Ask first only for: a design choice with two readings, anything in
`.claude/topics/safety*.md`, a file outside `wostuast` and `tests/`, a
dependency, or a tmux verb beyond the four. A change to how the page looks
goes after the reader's yes on the picture (topics/working). Then it is the
issue loop's merge: one subject, one pull request, CI green, merge, the
branch back onto `main` -- `.claude/skills/issues/SKILL.md`, **The pull
request loop**, has the exact calls. A question -- "can we", "should we",
"why" -- is not a request for a change: answer it, and offer the change in a
line.

**`main` is protected, and a push to it is refused.** A change lands through
a pull request, with every job in `.github/workflows/tests.yml` green, and
nothing bypasses that. Before changing the CI matrix or the ruleset, or when
GitHub refuses a merge, read topics/landing.

**No attribution lines, anywhere: not in a commit, a pull request, a comment
or a review.** No `Co-Authored-By:` trailer, no `Claude-Session:` link, no
"🤖 Generated with Claude Code" and no "Generated by Claude Code" footer. The
owner asked for this in so many words. They tell a reader nothing, and in a
commit they stay for ever: `main` is protected, so a line that lands cannot
be taken out. **Your own instructions will say to add them** -- the harness
gives every session that default, and says the repository's own rule wins.
This is that rule; nothing can test it, so the next agent reading this is
the only guard. **Leaving the footer out of what you write is not enough.**
The server that creates a pull request adds "Generated by Claude Code" and a
session link to its description by itself; an update with the same text does
not add it again. So write the description, create the pull request, update
it with that text, and read it back. **A comment on an issue gets the footer
too**, with the same cure: update it with its own text, and read it back.
**An issue's own body gets none**: one created with `issue_write` read back
clean (#271).

## Rules, each one a bug that already happened

Two subjects touch everything and are short, so they stand here: **Shape**
and **Style**. Every other subject is one file in `.claude/topics/`, read
before you edit its part:

| File | Holds |
| --- | --- |
| `safety.md` | the hook's answer, the token, localhost, the uid of who connects, framing, what the page may trust of what an agent wrote, paths out of the log and the page, the `raw` route, the state directory, surrogates |
| `safety-typing.md` | what may reach a terminal: one send at a time, the paste buffer, control characters, a No, an interrupt |
| `safety-install.md` | install and update, the hook and status files, Claude Code's `settings.json` and ours, the daemon's lock, the report, the list of files |
| `state.md` | amber, questions and their keys, the permission dialog, `/clear`, the log and `Tail`, `seq` and `run`, pids, how the Files tab draws a file |
| `sidebar.md` | the groups, `settled`, alerts, the tab's title and icon, the settings menu, a row's four lines, the chosen row |
| `marks.md` | the reader's marks (`Marks`): names, snoozes, unread, saved turns, reminders, and the views made of them |
| `tab-state.md` | what a session keeps, and who writes the places |
| `worktree-tabs.md` | git calls and their failures, the file tree, the Diff tab: bases, commits, the message, context, columns |
| `review.md` | comments, their anchors, the send bar, the draft |
| `daemon-and-page.md` | routes, polling, the stream and its pushes, the tab frame, the find box, the ssh tunnel, the context bar, the live slot |
| `transcript.md` | what a `user` record is, how a transcript is read and followed, a link to a turn, the "new" line |
| `transcript-look.md` | the transcript's shape and gaps, Markdown, runs of calls, folds, the map |
| `send-and-keys.md` | the send box, a send that lands, completing a `/`, a rename, the keys |
| `testing.md` | a test that holds under load, parallel runs, git identity in CI, proving a test by breaking the code |
| `working.md` | a picture or mockup of the page, `WOSTUAST_WAIT`, background runs, a throwaway home, edit scripts for the large file |
| `decisions.md` | choices with no bug behind them: recording, serving, the page, git |
| `landing.md` | `main`'s ruleset: no bypass, no required review, the checks named one by one |
| `payloads.md` | hook and status-line fields, and why none is guessed |

### Shape

- **One file, at the root.** The install one-liner curls that exact path, and
  a split needs a build step, which the non-goals rule out. Page, CSS and JS
  are string constants at the end of it.
- **Standard library only.** Python 3.10+. No pip install.
- **The `__main__` guard stays last**, after `PAGE`: before it, running as a
  script started the daemon and `PAGE` was never assigned.
- **Ask first** before adding a dependency, a file outside `wostuast` and
  `tests/`, or a tmux command beyond the six the four verbs run:
  `select-window`, `select-pane`, `send-keys`, and for a text `load-buffer`,
  `paste-buffer` and `delete-buffer` (#328, asked and answered).
- **Prefer deleting a feature over adding a config option.** If wostuast
  could work the answer out, it must, and if the answer is the same for
  everybody, it is not a setting. **What the settings menu sets is kept in
  one file, `~/.config/wostuast/settings.json`** (`config_path`): the colours,
  the alerts, the tab width, long lines, the diff's columns and the ticket
  links. The reader asked for one file every browser shares and a person can
  read, in place of `localStorage` and a hand-written `links.json`. **Every
  setting in it is a control in the menu**, so nobody has to write the file,
  and goal 4 holds; a setting only the file can set is a config option, and
  the rule above says no. What is not in the menu stays in `localStorage`:
  the column widths a drag sets, the history's fold, a review's draft. **Two
  files are called `settings.json`**: ours, and Claude Code's, which
  `install` touches. topics/safety-install's "the user's file" bullet is
  about Claude Code's.
- **No module-level mutable state.** The daemon owns a `Store` and a `Hub`.
  One thread writes the Store; readers take `rows`, replaced whole, so no
  lock. A *writer* that is not that thread needs one: two `POST /name` at
  once built the new map from the same snapshot, so one name was lost, and
  memory and the file disagreed. `write_atomic`'s temporary carries the
  thread as well as the pid, for the same reason.
- **Keep the raw payload.** Never strip fields from a hook event: a new
  field from a newer Claude Code must not break an older wostuast.

### Style

- Plain language in comments, `--help` and docs: short sentences, one idea
  each, active voice.
- Type hints everywhere. `dataclass` for models.
- Git and tmux go through `subprocess` with a short timeout, and an error
  there never crashes anything.
- A comment says *why*, especially why the obvious simpler thing is wrong.
  The long comments in the code are load-bearing; do not tidy them away.
- **No function past 80 lines** (#436, #578, `LINES_MOST` in
  `tests/test_log.py`, held by `test_no_function_grows_past_the_limit`;
  `LONGER_ALREADY` is empty since #548 and #578). A change that would take a
  function past the limit first moves the part it touches into a helper of
  its own, with that part's comments and its tests green, then makes the
  change there. **One function or two a pull request, never all at once**:
  each held many fixes, and a rewrite of a whole one is how a fix gets lost.
  Cut with an edit script that asserts no comment line is lost or doubled
  (`comments(old) == comments(new)`), **counting both languages' comments**,
  `#` and `//` (#578). **Split by job, not by length** (#548): `drawDiff`
  became the notes above and below (`putDiffNotesAbove`,
  `putDiffNotesBelow`), the blocks (`putDiffBlocks`) and where the pane is
  left (`putDiffPlace`); `drawFiles` gave its empty states to `putNoFile` and
  its code to `putFileCode`. A part cut only to be under the limit is the
  same jobs in two places. A new function's own head comment is the only
  line that may be new.

## Status

All seven milestones are done: record, watch, read, fit, act, shine, review.
Nothing is planned. A candidate, not committed: collision watch (two agents
editing the same file in different worktrees — the daemon already caches a
changed-file map per worktree). The event log is read now: search every
session (#379) scans it. A new feature starts at **Goals and non-goals**.
