# Do not guess payload fields

What hooks, the status line and transcripts carry, and how to find out.

- **Take a field name from `tests/fixtures/README.md`, or record a real
  payload into `tests/fixtures/`. Never invent one.**
- **One fixture is one sample: absence in it is not absence in the
  payload.** A brief read `tests/fixtures/status.json`, then without
  `cost`, said there was no spend; an issue was closed on it. The status
  line carries `cost.total_cost_usd`, `cost.total_duration_ms`,
  `cost.total_api_duration_ms`, the lines added and removed, and
  `rate_limits.five_hour` / `seven_day` / `spend_limit` with a used
  percentage and a reset time.
- **A report that carries a payload becomes a fixture before the fix.**
  Fixes built on a shape guessed from the reader's words came back. Keep
  every field name and level of nesting, put invented text in place of
  theirs, save it under `tests/fixtures/`, and write the failing test
  against it first. **No payload in the report: ask for one first.**
- **Never commit a real conversation**: this repository is public.
- **Read more than one machine.** "A compaction writes a `summary` record"
  was false. A current build writes a `system` record with `subtype:
  "compact_boundary"`, then a `user` record with `isCompactSummary`
  holding the summary, which showed as a prompt because it is a `user`
  record.
- **`Stop` carries `last_assistant_message`** on 2.1.288
  (`tests/fixtures/stop_answer.jsonl`), with `background_tasks` and
  `session_crons`; 2.1.276 sends only `stop_hook_active`. The feed reads it
  (#376); with none it shows "open it".
- **The session's name** (#351, read from the 2.1.288 binary). Claude Code
  shows `agentName || customTitle || aiTitle || summary || first prompt ||
  … || sessionId.slice(0, 8)`. The status line's `session_name` is
  `customTitle ?? aiTitle`. `/rename` writes
  `{"type":"custom-title","customTitle":…}` and
  `{"type":"agent-name","agentName":…}`, fires no hook, and both are
  written again at the end of every turn. No `{"type":"ai-title",
  "aiTitle":…}` record was seen (`claude_pane.py` sets
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`); the status line hands it
  over, so nothing reads it from a transcript.
- **A `/command` in the middle of a prompt is not run** (#368, 2.1.288):
  the model gets words, and a note that the Skill tool runs that skill. A
  command file counts as a skill there; a built-in does not.
- **Measure a live Claude Code against a fake Messages API with
  `tests/claude_pane.py`**: its own home and a fake key, nothing of the
  owner's; it runs in a cloud session too (#328, #331, #337, #338).
  - **"What does X do while a turn runs" is `busy(seconds)`**: a Bash
    `sleep` still running when it returns (#351). `sleep` asks no
    permission, so a wait for its dialog let the turn end first;
    `wait_for_turns(2)` waits for the request after the tool's result.
  - **What only the owner's `~/.claude` holds is the owner's to take.**
    Listing it or the environment is refused as credential exploration,
    by any route. Put a probe script in the issue, say what its output
    answers, and leave the issue open; #266 holds the shape.
  - **Measure a layout of `~/.claude` in a home of its own**:
    `ClaudePane(setup=...)` installs a plugin written for the purpose
    before Claude Code starts (#413).
- **A plugin, as 2.1.289 installs it** (#413).
  `plugins/installed_plugins.json` is
  `{"version": 2, "plugins": {"demo@mk": [{"scope": "user", "installPath": ".../plugins/cache/mk/demo/1.0.0", "version", "installedAt", "lastUpdated"}]}}`;
  `--scope project` adds `"projectPath"`. Under `installPath`:
  `commands/hello.md`, `skills/greet/SKILL.md`. `settings.json` gets
  `"enabledPlugins": {"demo@mk": true}`; `claude plugin disable --scope
  project` writes `false` into the project's `.claude/settings.json`.
  **The names**: completion shows `/demo:hello  (demo) Say hello`; the
  transcript records `<command-name>/demo:hello</command-name>`; a typed
  `/greet` ran as `/demo:greet`, its text opening "Base directory for this
  skill:".
- **A plan's approval is a `PermissionRequest` for `ExitPlanMode`, with
  the plan in its `tool_input`** (2.1.288, `ClaudePane(mode="plan")`). The
  model writes `~/.claude/plans/<slug>.md` and calls the tool with `{}`,
  as its schema says, yet Claude Code fills `tool_input` with
  `plan` (the file's whole Markdown) and `planFilePath`, in `PreToolUse`,
  `PermissionRequest` and the transcript's `tool_use`. Escape fires no
  hook, writes a `tool_result` with `is_error` and `toolUseResult: "User
  rejected tool use"`, and stays in plan mode: `decline` works on a plan as
  on any tool. `plan_of`; `tests/fixtures/plan_events.jsonl`,
  `plan_transcript.jsonl`; topics/state says what the page does (#372).
- **A conversation moved to the background is read off a real run**
  (`tests/fixtures/README.md`, 2.1.292). The fork's `SessionStart` says
  `source: "fork"` and names no session it carries on; the old one gets no
  `SessionEnd`. Only the process tells: the fork runs under `bg-pty-host`
  as `--fork-session --resume <old transcript>`, so the hook writes
  `background` and `moved_from` (`background_start`).
- **What an agent starts is read off a real run, not the docs** (#422,
  `tests/fixtures/README.md`). A subagent of the Agent tool fires hooks
  under its agent's session id, with `agent_id`; as a session it would be
  a row nobody asked for. A `claude -p` is a session of its own, and
  overwrites `CLAUDE_CODE_SESSION_ID`, so a hook reading it got the
  child's id. Only the process tree joins them: the hook writes
  `started_by` (`claude_from`), Linux only. Measured with `ask("Agent", …)`,
  setting `api.next_call` again once `wait_for_turns` sees the call.
