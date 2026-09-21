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

Header and footer read off a real transcript. A build that writes it as an
`attachment` record instead is ignored by the Transcript tab, which reads
`user` and `assistant` only. `read_user_text` keeps the middle.

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

`status.json` is one status line payload, in the shape the `statusLine`
command receives on stdin.

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

Other line types appear and are ignored: `queue-operation`, `attachment`,
`mode`, `last-prompt`, `atis-latch`, `cost-state`, `permission-mode`,
`ai-title`, `pr-link`, `bridge-session`, `file-history-snapshot` and
`file-history-delta`. A `system` record other than a compact boundary is
ignored too.
