# Fixtures

`events.jsonl` is one recorded run of a Claude Code session, one line per hook
event, in the shape `wostuast hook` writes.

The field names come from the hook payload schema of Claude Code 2.1.276, not
from guessing. The base payload of every hook event is:

    session_id, transcript_path, cwd, permission_mode, hook_event_name

Each event adds its own fields:

| Event | Extra fields |
| --- | --- |
| `SessionStart` | `source` (startup, resume, clear, compact), `agent_type`, `model` |
| `UserPromptSubmit` | `prompt` |
| `PreToolUse` | `tool_name`, `tool_input`, `tool_use_id` |
| `PostToolUse` | `tool_name`, `tool_input`, `tool_response`, `tool_use_id` |
| `PostToolUseFailure` | `tool_name`, `tool_input`, `tool_use_id`, `error`, `error_type`, `is_interrupt`, `is_timeout` |
| `PermissionRequest` | `tool_name`, `tool_input`, `permission_suggestions` |
| `Notification` | `message`, `title`, `notification_type` |
| `Stop` | `stop_hook_active` |
| `SubagentStop` | `stop_hook_active`, `agent_id`, `agent_transcript_path`, `agent_type` |
| `PreCompact` | `trigger` (manual, auto), `custom_instructions` |
| `SessionEnd` | `reason` (clear, logout, prompt_input_exit, other, bypass_permissions_disabled) |

`notification_type` is one of `permission_prompt`, `idle_prompt`,
`auth_success`, `elicitation_dialog`.

`/clear` sends two events, measured on 2.1.282: `SessionEnd` with `reason:
clear` for the old id, then `SessionStart` with `source: clear` for a new id
and a new `transcript_path`, about 0.1 s later. They carry the same `pane`
and `pid` and nothing that names each other. The new transcript opens with
the `/clear` command's own records.

A newer build adds `scratchpad_dir`, `prompt_id`, `effort` and `shell_pid`
to the base payload, and `permission_mode` reads `auto`. None of them is read,
and the log keeps them because it keeps whatever arrives: a field from a newer
Claude Code must never break an older wostuast.

`wostuast hook` adds three fields of its own: `ts`, `pane` and `pid`.

### A question the agent is stopped on

`AskUserQuestion` is a tool, so the whole of it arrives in `tool_input` --
every question, every option label and description. Read off a real log, one
ask sends three events:

| Order | Event | Carries |
| --- | --- | --- |
| 1 | `PreToolUse` | the questions, and `tool_use_id` |
| 2 | `PermissionRequest`, 90 ms later | the same questions, no `tool_use_id` |
| 3 | `Notification`, 6 s later | `permission_prompt`, "Claude needs your permission" |

`tool_input.questions` is a list, and one ask really does hold more than one
question. Each has `question`, `header`, `multiSelect` and `options`, and each
option has `label` and `description`. `read_ask` names those fields and keeps
nothing else.

### A message that arrives mid-turn

Sent to an agent that is working -- which is what this page's send box does --
Claude Code queues it into the running turn and writes one `user` record
holding three things:

```
<system-reminder>
The user sent a new message while you were working:
<the words that were typed>

This is how Claude Code surfaces messages the user sends mid-turn - within the
running turn, often alongside the next tool result, rather than as a separate
conversation turn. Address the message above as you continue this turn.
</system-reminder>
```

Header and footer read off a real transcript. `read_user_text` keeps the
middle.

**2.1.276 to 2.1.281 write it as an `attachment` record instead**, and no
`user` record follows. Shape, read off a real transcript:

```
{"type": "attachment", "timestamp": "…", "rendered": [...],
 "attachment": {"type": "queued_command", "prompt": "<the words>",
                "commandMode": "prompt", "origin": {"kind": "human"},
                "timestamp": "…", "source_uuid": "…"}}
```

`prompt` is a string, or a list of content pieces when an image came with
it. `origin.kind` is `human` for the reader, and `peer` for another session's
message, which also carries `isMeta: true`. `commandMode` is
`task-notification` for a background task's news, with no `origin`. Only
`queued_command` is read; every other attachment is left out. The records
around it are `queue-operation` lines: an `enqueue`, then a `remove`.

### A `user` record Claude Code wrote itself

`isMeta: true` on a `user` record means the harness wrote it: a Stop hook's
answer (`Stop hook feedback:`), a whole skill's body (`Base directory for
this skill:`), `Continue from where you left off.`, an image's caption. It
is drawn as a note, never as a prompt.

### A command run with `!`

`bash_mode.jsonl`, read off Claude Code 2.1.282 with invented text. Typing
`!git up` writes two `user` records, neither `isMeta`:

| Line | `message.content`, a plain string |
| --- | --- |
| the command | `<bash-input>git up</bash-input>`, exactly as typed, nothing escaped |
| its output | `<bash-stdout>...</bash-stdout><bash-stderr>...</bash-stderr>` |

The output has `<`, `>` and `&` written as `&lt;`, `&gt;` and `&amp;`, and
quotes left as they are. In the run this was read from, what the command
wrote to stderr was inside `<bash-stdout>`, and `<bash-stderr>` was empty.
The second line carries `turnOrigin: "human"`; the first does not.

### Two calls at once

Claude Code runs tools in parallel now and then. Measured on a real event log:
**one of 233 calls started while another was still open**, and both were
`Bash`. So a `PostToolUse` can arrive for one call while another is still
going — including while that other one has a permission dialog on screen.

`PreToolUse` and `PostToolUse` carry `tool_use_id`, which pairs a call with its
result. **`PermissionRequest` does not**, so a dialog cannot be paired to a
call exactly. It carries `tool_name` and `tool_input`, which is enough to tell
two different Bash commands apart and not enough to tell two runs of the same
one apart.

Both `PreToolUse` events come before the dialog: nothing new starts while one
is up. That is what separates "the agent moved on" from "the other call
finished" — see `_on_pre_tool`.

Saying No to a dialog fires no hook. Measured on 2.1.282: after Escape the
log ends at the `PermissionRequest` and its `Notification`, and the
transcript gets the call's result (`toolUseResult: "User rejected tool
use"`) and a `user` record `[Request interrupted by user for tool use]`.
When a dialog is declined, the daemon appends one record of its own to the
event log, once the transcript shows that result: `hook_event_name:
"Declined"`, with `session_id`, `ts`, `key` (the dialog, as
`Session.permission` names it) and `tool_use_id`. No hook writes it. It
carries `where: "terminal"` when the No was given in the pane rather than
from the page.

`status.json` is one status line payload, in the shape the `statusLine`
command receives on stdin. The numbers in it are invented; the field names are
not. The fields wostuast reads or might read:

| Field | Holds |
| --- | --- |
| `session_id`, `session_name` | the id, and the name `/rename` sets |
| `model.display_name` | "Opus 5" |
| `context_window.used_percentage` | how full the window is, 0 to 100 |
| `cost.total_cost_usd` | what this session has spent, **estimated client-side at list price** — Claude Code says it may differ from the bill, and it resets to 0 on `/clear` |
| `cost.total_duration_ms`, `cost.total_api_duration_ms` | wall-clock time, and time spent waiting on the API |
| `cost.total_lines_added`, `cost.total_lines_removed` | lines changed |
| `rate_limits.five_hour`, `rate_limits.seven_day` | `used_percentage` and `resets_at` for a claude.ai Pro or Max subscription |
| `rate_limits.spend_limit` | the same two fields behind a Claude apps gateway; its percentage can go **above 100** |
| `agent.name`, `version` | which agent, which Claude Code |

**`cost` and `rate_limits` were missed once already, and the cost of missing
them was a decision.** The design brief this repository used to carry said "money is in no
payload" for a while, written from this fixture when this fixture had no `cost` in it — and
issue #101 was closed down to one line on the strength of it. A reader with a
status line on another machine said otherwise and was right. `rate_limits`
appears only for claude.ai Pro and Max subscribers, or behind a gateway, and
only after the first API response, and each window disappears once its
`resets_at` passes — so its absence proves nothing about a payload either.
The lesson is the one at the top of this file and in `CLAUDE.md`: a claim about
a payload is worth what the sample behind it is worth, and one fixture is one
sample.

## transcript.jsonl

One session transcript, in the shape Claude Code writes to
`~/.claude/projects/<escaped-cwd>/<session-id>.jsonl`. The `transcript_path` of
every hook event points at such a file.

The keys below were read off a real transcript written by Claude Code 2.1.276,
not guessed. The text in the fixture is invented, because this repository is
public and a real transcript holds the user's own conversation.

One JSON object per line. The lines the Transcript tab cares about have
`type` of `user` or `assistant`, and carry:

    parentUuid, uuid, timestamp, sessionId, cwd, gitBranch, version, message

`message.content` is either a plain string (a typed prompt) or a list of
content blocks. The block types and their keys:

| `type` | Keys | Shown as |
| --- | --- | --- |
| `text` | `text` | a prompt block, or rendered Markdown |
| `thinking` | `thinking`, `signature` | hidden, behind the "show thinking" toggle |
| `tool_use` | `id`, `name`, `input`, `caller` | one collapsed line, summarised per tool |
| `tool_result` | `tool_use_id`, `content`, `is_error` | attached to its `tool_use` |

`tool_result.content` is a string in the common case and may also be a list of
blocks. `tool_use.name` and `tool_use.input` hold what the hook payload calls
`tool_name` and `tool_input`, so `tool_summary` reads both without changing.

### A compaction

Measured over 31 transcripts on three machines, two different builds: **no
`summary` record appears anywhere**. The schema still lists it, and this
fixture still holds one, because an older Claude Code wrote them — what one
meant there (a session compacted *or* resumed) was never settled, and no build
in use writes one to settle it with.

A current build writes a compaction as two lines, in this order:

| Line | Keys that matter |
| --- | --- |
| `type: "system"` | `subtype: "compact_boundary"`, `content: "Conversation compacted"`, `compactMetadata` |
| `type: "user"` | `isCompactSummary: true`, `isVisibleInTranscriptOnly: true`, and `message.content` as a plain string |

`compactMetadata` holds `trigger` (manual, auto — the same two words as
`PreCompact`), `preTokens`, `durationMs`, `preCompactDiscoveredTools` and
`preservedSegment`. The `user` line carries the whole summary: 13,644
characters in the one this was read from. It is a `user` record and it is not
a prompt — drawing it as one put that much machine text in the transcript as
though the reader had typed it.

Other line types appear and are ignored: `queue-operation`, an `attachment`
that is not a `queued_command`,
`mode`, `last-prompt`, `atis-latch`, `cost-state`, `permission-mode`,
`ai-title`, `pr-link`, `bridge-session`, `file-history-snapshot` and
`file-history-delta`. A `system` record other than a compact boundary is
ignored too.
