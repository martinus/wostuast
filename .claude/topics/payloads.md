# Do not guess payload fields

Hook and status line field names are in `tests/fixtures/README.md`. **Need
one that is not there? Record a real payload and add it to
`tests/fixtures/`. Never invent a name.**

- **The status line carries money.** It has `cost.total_cost_usd`,
  `cost.total_duration_ms`, `cost.total_api_duration_ms`, the lines added
  and removed, and `rate_limits.five_hour` / `seven_day` / `spend_limit`
  with a used percentage and a reset time. **One fixture is one sample:
  absence in it is not absence in the payload.** A brief that read
  `tests/fixtures/status.json`, then without `cost`, said there was no
  spend, and an issue was closed on it. To "does this payload carry X", a
  fixture can only say yes.
- **A report that carries a payload becomes a fixture before the fix.**
  Fixes built on a shape guessed from the reader's words came back
  (answering a question three times, the paste tags twice). Copy the record
  out of the report, put invented text in place of theirs, keep every field
  name and every level of nesting, save it under `tests/fixtures/`, and
  write the failing test against it first. **A report with no payload: ask
  for one before building**; the reader sends them when asked.
- **Recording one does not mean committing your conversation.** This
  repository is public: fixtures carry real field names in real shapes with
  invented text. Read a real payload, learn the shape, write the fixture.
- **Read more than one machine.** "A compaction writes a `summary` record"
  was false: 31 transcripts on three machines and two builds hold none. A
  current build writes a `system` record with `subtype: "compact_boundary"`,
  then a `user` record with `isCompactSummary` carrying the whole summary,
  which went into the transcript as a prompt because it is a `user` record.
  A claim about a payload is worth what its sample is worth.
- **`Stop` carries `last_assistant_message`** on 2.1.288 (measured with
  `tests/claude_pane.py`, `tests/fixtures/stop_answer.jsonl`): the agent's
  last words in the turn, and `background_tasks` and `session_crons`. The
  2.1.276 fixture has only `stop_hook_active`. The feed reads it (#376); an older build that sends none shows "open it".
- **The session's name** (#351, read from the 2.1.288 binary and measured).
  Claude Code shows `agentName || customTitle || aiTitle || summary || first prompt || … || sessionId.slice(0, 8)`
  (its `fq`). The status line's `session_name` is `customTitle ?? aiTitle`
  (`Nf`, `WK`). `/rename` writes `{"type":"custom-title","customTitle":…}`
  and `{"type":"agent-name","agentName":…}` with the same name, fires no
  hook, and both records are written again at the end of every turn. No
  `ai-title` record was seen: `claude_pane.py` sets
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`, and this machine's remote
  sessions are named by `/rename`. Its shape, from the binary, is
  `{"type":"ai-title","aiTitle":…}`; nothing here reads it from a
  transcript, because the status line hands it over.
- **A `/command` in the middle of a prompt is not run** (#368, 2.1.288): it
  reaches the model as words, and Claude Code adds a system note that the
  message contains the name of a skill and that the Skill tool runs it. A
  command file counts as a skill there; a built-in does not.
- **Measure a live Claude Code against a fake Messages API, with
  `tests/claude_pane.py`**: a home of its own, a fake key, the API on
  127.0.0.1, a status line and hooks that keep what they are handed; no
  login and nothing of the owner's. It runs in a cloud session too, and
  measured a long paste in the prompt (#328), a dialog's keys (#331), what a
  typed `/model` writes and the status line's `effort` (#337, #338).
  - **"What does X do while a turn runs" is `busy(seconds)`**: a turn that
    runs a Bash `sleep`, still running when it returns (#351). `sleep` asks
    for no permission, even in manual mode, so a wait for its dialog let the
    turn end first; `wait_for_turns(2)` waits for the request after the
    tool's result.
  - **What only the owner's `~/.claude` holds is the owner's to take.**
    Listing it, or the environment, is refused as credential exploration,
    and the refusal covers every other way to the same answer. Write the
    probe as a short script into the issue, say what its output answers, and
    leave the issue open for the result; #266 holds the shape.
  - **Measure a layout of `~/.claude` in a home of its own instead**: for
    #413, `ClaudePane(setup=...)` ran `claude plugin marketplace add` and
    `claude plugin install` on a marketplace of one plugin written for the
    purpose, before Claude Code started.
- **A plugin, as 2.1.289 installs it** (#413).
  `plugins/installed_plugins.json` is
  `{"version": 2, "plugins": {"demo@mk": [{"scope": "user", "installPath": ".../plugins/cache/mk/demo/1.0.0", "version", "installedAt", "lastUpdated"}]}}`;
  one installed with `--scope project` carries `"projectPath"`. The files
  are copied under `installPath`: `commands/hello.md`,
  `skills/greet/SKILL.md`. `settings.json` gets
  `"enabledPlugins": {"demo@mk": true}`, and
  `claude plugin disable --scope project` writes `false` into the project's
  `.claude/settings.json`. **The names**: the completion list shows
  `/demo:hello  (demo) Say hello`; the transcript records
  `<command-name>/demo:hello</command-name>`; and `/greet`, typed, ran as
  `/demo:greet`, its text opening "Base directory for this skill:" and the
  marketplace's own folder for a marketplace that is a directory.
- **A plan's approval is a `PermissionRequest` for `ExitPlanMode`, and the
  plan is in its `tool_input`** (measured on 2.1.288 with
  `ClaudePane(mode="plan")`). Do not trust the tool's schema here: it takes
  no plan -- the model writes the plan to `~/.claude/plans/<slug>.md` with
  `Write` and calls `ExitPlanMode` with `{}` -- yet Claude Code fills
  `tool_input` with `plan` (the file's Markdown, whole) and `planFilePath`,
  in `PreToolUse`, in `PermissionRequest`, and in the transcript's own
  `tool_use` record. The path is announced earlier, in an `attachment` of
  `type: "plan_mode"` with `planFilePath` and `planExists`. The dialog
  offers "Yes, and use auto mode", "Yes, manually approve edits" and "Tell
  Claude what to change". Escape closes it, fires no hook, writes the usual
  `tool_result` with `is_error` and `toolUseResult: "User rejected tool use"`,
  and leaves the prompt in plan mode: so `decline` works on a plan as on any
  tool, and a reason typed after it reaches the agent still planning. No
  `Notification` came in the six seconds the dialog was up. `plan_of` reads
  it; `tests/fixtures/plan_events.jsonl` and `plan_transcript.jsonl` are the
  recording; topics/state says what the page does with it (#372).
- **A conversation the agents view moves to the background is read off a
  real run** (`tests/fixtures/README.md`, "A conversation moved to the
  background"; 2.1.292). The fork's `SessionStart` says `source: "fork"`
  and nothing that names the session it carries on, and the old one gets no
  `SessionEnd`. Only the process does: the fork runs under the daemon's
  `bg-pty-host` as `--fork-session --resume <old transcript>`, which is why
  the hook writes `background` and `moved_from` (`background_start`).
  Measured with `ClaudePane(setup=…)` running `wostuast install` into its
  home, and `send-keys Left` on the empty prompt.
- **What an agent starts is read off a real run, not the docs** (#422,
  `tests/fixtures/README.md`, "What an agent starts"). A subagent of the
  Agent tool fires its hooks under its agent's session id, with
  `agent_id`: as a session it would be a row nobody asked for, and its tool
  calls already move the agent's own row. A `claude -p` is a session of its
  own whose payload and environment name only itself: `CLAUDE_CODE_SESSION_ID`
  in the Bash tool is the agent's, and the child overwrites it, so a hook
  that read it got the child's own id. Only the process tree joins them,
  which is why the hook writes `started_by` (`claude_from`) and why it is
  Linux only. Measured on `ClaudePane`: `ask("Agent", …)`, then
  `api.next_call` set again once `wait_for_turns` sees the call, so the
  subagent's own first request gets a tool call too.
