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
