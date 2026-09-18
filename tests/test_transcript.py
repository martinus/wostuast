"""The transcript parser: the session's own jsonl, turned into blocks."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "transcript.jsonl"


@pytest.fixture
def parsed(ws):
    """The recorded transcript, read through once."""
    transcript = ws.Transcript(str(FIXTURE), "/home/martin/oans/warmhare")
    transcript.read_new()
    return transcript


def test_the_recorded_transcript_reads_as_expected(parsed):
    got = parsed
    kinds = [b.kind for b in got.blocks]
    assert kinds == ["prompt", "thinking", "text", "tool", "tool", "text", "divider"]


def test_a_prompt_keeps_its_text(parsed):
    got = parsed
    assert got.blocks[0].kind == "prompt"
    assert "substring search" in got.blocks[0].text


def test_thinking_is_its_own_kind_so_the_page_can_hide_it(parsed):
    got = parsed
    thinking = [b for b in got.blocks if b.kind == "thinking"]
    assert len(thinking) == 1
    assert "exact name" in thinking[0].text


def test_assistant_text_is_kept_as_markdown(parsed):
    got = parsed
    text = [b for b in got.blocks if b.kind == "text"][0]
    assert text.text.startswith("## Plan")


def test_a_tool_call_is_one_block_with_its_target(parsed):
    got = parsed
    tools = [b for b in got.blocks if b.kind == "tool"]
    assert [b.tool for b in tools] == ["Write", "Bash"]
    assert tools[0].target == "PLAN.md"
    assert tools[1].target == "python3 -m pytest -q"


def test_a_result_is_attached_to_its_call(parsed):
    got = parsed
    tools = [b for b in got.blocks if b.kind == "tool"]
    assert "PLAN.md" in tools[0].result
    assert tools[1].result == "14 passed in 0.31s"
    assert tools[0].failed is False


def test_a_compaction_becomes_a_divider(parsed):
    got = parsed
    assert got.blocks[-1].kind == "divider"
    assert got.blocks[-1].text == "context compacted"


def test_timestamps_are_read(parsed):
    got = parsed
    assert got.blocks[0].ts > 0
    assert got.blocks[-2].ts >= got.blocks[0].ts


# --- following it as it grows ------------------------------------------------


def test_it_follows_without_re_reading(ws, tmp_path):
    path = tmp_path / "t.jsonl"
    shutil.copy(FIXTURE, path)
    transcript = ws.Transcript(str(path))
    first = transcript.read_new()
    # seven blocks, and two of them are touched twice: a tool call is created
    # and then updated when its result arrives, so nine touches in all
    assert len(transcript.blocks) == 7
    assert len(first) == 9
    assert transcript.read_new() == []

    with open(path, "a") as handle:
        handle.write(json.dumps({
            "type": "assistant", "timestamp": "2026-09-18T14:10:00.000Z",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "More."}]},
        }) + "\n")
    more = transcript.read_new()
    assert [b.text for b in more] == ["More."]
    assert len(transcript.blocks) == 8


def test_a_result_arriving_later_updates_the_same_block(ws, tmp_path):
    """The point of parsing as we go: a result lands in a line of its own."""
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps({
        "type": "assistant", "timestamp": "2026-09-18T14:00:00.000Z",
        "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "tu_9", "name": "Bash",
             "input": {"command": "make"}}]},
    }) + "\n")
    transcript = ws.Transcript(str(path))
    call = transcript.read_new()[0]
    assert call.result == ""

    with open(path, "a") as handle:
        handle.write(json.dumps({
            "type": "user", "timestamp": "2026-09-18T14:00:05.000Z",
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_9",
                 "is_error": True, "content": "make: *** No targets."}]},
        }) + "\n")
    touched = transcript.read_new()
    assert touched == [call], "the same block should come back, not a new one"
    assert call.failed is True
    assert "No targets" in call.result
    assert len(transcript.blocks) == 1


def test_a_half_written_line_is_not_parsed_twice(ws, tmp_path):
    path = tmp_path / "t.jsonl"
    line = json.dumps({"type": "assistant", "message": {"role": "assistant",
                                                        "content": "hello"}})
    path.write_text(line[:20])
    transcript = ws.Transcript(str(path))
    assert transcript.read_new() == []
    with open(path, "a") as handle:
        handle.write(line[20:] + "\n")
    assert len(transcript.read_new()) == 1
    assert len(transcript.blocks) == 1


def test_a_missing_transcript_is_empty(ws, tmp_path):
    transcript = ws.Transcript(str(tmp_path / "nothing.jsonl"))
    assert transcript.read_new() == []
    assert transcript.blocks == []


def test_lines_we_do_not_show_are_skipped(ws, tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in [
        {"type": "queue-operation", "operation": "enqueue"},
        {"type": "attachment", "attachment": {}},
        {"type": "system", "subtype": "hook"},
        {"type": "mode", "mode": "auto"},
        {"type": "last-prompt", "lastPrompt": "x"},
        {"type": "user", "message": {"role": "user", "content": "kept"}},
    ]) + "\n")
    transcript = ws.Transcript(str(path))
    blocks = transcript.read_new()
    assert [b.kind for b in blocks] == ["prompt"]
    assert blocks[0].text == "kept"


def test_broken_json_does_not_stop_it(ws, tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text('not json\n' + json.dumps(
        {"type": "user", "message": {"role": "user", "content": "kept"}}) + "\n")
    assert [b.text for b in ws.Transcript(str(path)).read_new()] == ["kept"]


# --- the per-tool summaries section 4.6 asks for ----------------------------


def test_an_edit_counts_the_lines_it_changes(ws):
    assert ws.edit_counts({"old_string": "a\nb\nc", "new_string": "a\nB\nc\nd"}) == (4, 3)
    assert ws.edit_counts({"new_string": "only"}) == (1, 0)
    assert ws.edit_counts({"content": "a\nb\n"}) == (2, 0)
    assert ws.edit_counts({}) == (0, 0)
    assert ws.edit_counts(None) == (0, 0)


def test_a_multi_edit_adds_its_edits_up(ws):
    counts = ws.edit_counts({"edits": [
        {"old_string": "a", "new_string": "b\nc"},
        {"old_string": "d\ne", "new_string": "f"},
    ]})
    assert counts == (3, 3)


def test_the_target_is_the_summary_without_the_tool_name(ws):
    cwd = "/w/dir"
    assert ws.tool_target("Read", {"file_path": "/w/dir/a.py"}, cwd) == "a.py"
    assert ws.tool_target("Bash", {"command": "make -j"}, cwd) == "make -j"
    assert ws.tool_target("Grep", {"pattern": "needle"}, cwd) == "needle"
    assert ws.tool_target("Mystery", {}, cwd) == ""


def test_an_edit_block_carries_its_counts(ws, tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps({
        "type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "e1", "name": "Edit", "input": {
                "file_path": "/w/dir/gra", "old_string": "a\nb\nc\nd",
                "new_string": "a\nB\nc"}}]},
    }) + "\n")
    block = ws.Transcript(str(path), "/w/dir").read_new()[0]
    assert block.tool == "Edit"
    assert block.target == "gra"
    assert (block.added, block.removed) == (3, 4)


def test_a_result_that_is_a_list_of_blocks(ws):
    assert ws.result_text([{"type": "text", "text": "one"}, "two"]) == "one\ntwo"
    assert ws.result_text("plain") == "plain"
    assert ws.result_text(None) == ""


def test_a_write_gets_no_line_counts(ws, tmp_path):
    """Section 4.6 asks for counts on an edit. A whole new file has none worth
    showing, and `Write PLAN.md +1` reads like a diff when it is not."""
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps({
        "type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "w1", "name": "Write",
             "input": {"file_path": "/w/dir/PLAN.md", "content": "# plan\n"}}]},
    }) + "\n")
    block = ws.Transcript(str(path), "/w/dir").read_new()[0]
    assert block.tool == "Write"
    assert block.target == "PLAN.md"
    assert (block.added, block.removed) == (0, 0)
