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

`wostuast hook` adds three fields of its own: `ts`, `pane` and `pid`.

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

Other line types appear and are ignored by the transcript tab: `summary`
(written when a session is compacted or resumed), `queue-operation`,
`attachment`, `system`, `mode`, `last-prompt` and `atis-latch`.
