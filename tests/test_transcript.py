"""The transcript parser: the session's own jsonl, turned into blocks."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest

import conftest

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
    # Two dividers: the `summary` record an older Claude Code wrote, and the
    # `compact_boundary` a current one writes. The compact summary that
    # follows the boundary is not among them — see the test below.
    assert kinds == ["prompt", "thinking", "text", "tool", "tool", "text",
                     "divider", "divider"]


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
    """Two shapes, one divider. An older Claude Code wrote a `summary`
    record; a current one writes a `system` record whose subtype is
    `compact_boundary`, and no `summary` at all — measured over 31
    transcripts on three machines, where `summary` never appeared once."""
    got = parsed
    dividers = [b for b in got.blocks if b.kind == "divider"]
    assert len(dividers) == 2
    assert {b.text for b in dividers} == {"context compacted"}


def test_the_summary_carried_across_a_compaction_is_not_a_prompt(parsed):
    """Claude Code carries the conversation over a compaction in a `user`
    record with `isCompactSummary`. It went into the transcript as a prompt —
    thirteen thousand characters of machine text sitting there as though the
    reader had typed them. The divider says what happened; this is not a
    prompt and not anything else either."""
    got = parsed
    assert [b.kind for b in got.blocks].count("prompt") == 1
    assert not any("continued from a previous conversation" in b.text
                   for b in got.blocks)


def test_timestamps_are_read(parsed):
    got = parsed
    assert got.blocks[0].ts > 0
    spoken = [b for b in got.blocks if b.kind != "divider"]
    assert spoken[-1].ts >= got.blocks[0].ts


# --- following it as it grows ------------------------------------------------


def test_it_follows_without_re_reading(ws, tmp_path):
    path = tmp_path / "t.jsonl"
    shutil.copy(FIXTURE, path)
    transcript = ws.Transcript(str(path))
    first = transcript.read_new()
    # seven blocks, and two of them are touched twice: a tool call is created
    # and then updated when its result arrives, so nine touches in all
    assert len(transcript.blocks) == 8
    assert len(first) == 10
    assert transcript.read_new() == []

    with open(path, "a") as handle:
        handle.write(json.dumps({
            "type": "assistant", "timestamp": "2026-09-18T14:10:00.000Z",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "More."}]},
        }) + "\n")
    more = transcript.read_new()
    assert [b.text for b in more] == ["More."]
    assert len(transcript.blocks) == 9


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


# --- a transcript that started over -------------------------------------------


def lines(*texts):
    return "".join(json.dumps(
        {"type": "assistant", "message": {"role": "assistant", "content": t}}) + "\n"
        for t in texts)


def test_a_transcript_rewritten_under_its_name_is_not_drawn_twice(ws, tmp_path):
    """`Tail` starts over when the inode changes, which is right — but a
    reader that only appends then drew the whole file a second time on top of
    what it already held, and pushed every one of those to the page as new.

    Reproducing this needs a real inode change. An unlink and recreate may
    hand back the same inode, and then the reset never fires.
    """
    path = tmp_path / "t.jsonl"
    path.write_text(lines("one", "two"))
    reader = ws.Transcript(str(path))
    reader.read_new()
    assert [b.text for b in reader.blocks] == ["one", "two"]
    was = reader.run

    spare = tmp_path / "spare.jsonl"
    spare.write_text(lines("one", "two", "three"))
    spare.replace(path)                       # a new inode, as a rewrite makes

    changed = reader.read_new()
    assert [b.text for b in reader.blocks] == ["one", "two", "three"]
    assert [b.seq for b in reader.blocks] == [0, 1, 2]
    assert [b.text for b in changed] == ["one", "two", "three"]
    assert reader.run == was + 1, "the page has to be told it is a new reading"


def test_a_transcript_truncated_in_place_forgets_what_went(ws, tmp_path):
    """Same name, same inode, fewer bytes. The page used to go on showing text
    the file no longer held."""
    path = tmp_path / "t.jsonl"
    path.write_text(lines("aaaa", "bbbb"))
    reader = ws.Transcript(str(path))
    reader.read_new()
    path.write_text(lines("cc"))
    reader.read_new()
    assert [b.text for b in reader.blocks] == ["cc"]


def test_the_first_read_is_not_a_restart(ws, tmp_path):
    """Every reader starts with no file behind it. That is not a reset, and
    calling it one would bump the run on every session that ever opens."""
    path = tmp_path / "t.jsonl"
    path.write_text(lines("one"))
    reader = ws.Transcript(str(path))
    reader.read_new()
    assert reader.run == 0
    assert reader.tail.restarted is False


def test_a_new_reader_for_one_session_is_a_new_reading(ws, served, tmp_path,
                                                       transcript_file):
    """A session resumed from another directory writes under another name, so
    `seq` starts again. The page patches by index, so it has to be told."""
    daemon, _ = served
    first = transcript_file("s1", [
        {"type": "assistant", "message": {"role": "assistant", "content": "one"}}])
    ws.append_event(conftest.event("SessionStart", sid="s1", cwd="/w/one",
                                   transcript_path=str(first), ts=time.time()))
    daemon.store.refresh()
    blocks, run = daemon.read_transcript("s1")
    assert [b.text for b in blocks] == ["one"]

    second = transcript_file("s2-elsewhere", [
        {"type": "assistant", "message": {"role": "assistant", "content": "two"}}])
    ws.append_event(conftest.event("SessionStart", sid="s1", cwd="/w/one",
                                   transcript_path=str(second),
                                   ts=time.time() + 1))
    daemon.store.refresh()
    blocks, later = daemon.read_transcript("s1")
    assert [b.text for b in blocks] == ["two"]
    assert later > run


# --- the records Claude Code writes as though you had typed them -------------
#
# The shapes below are real, from a real transcript. One `/reload-plugins`
# arrives as three or four `user` records, none of which a person typed.


def user_record(text, when="2026-09-18T14:00:00.000Z"):
    return {"type": "user", "timestamp": when,
            "message": {"role": "user", "content": text}}


def test_a_slash_command_is_one_line_saying_what_was_run(ws, tmp_path):
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    blocks = reader.add(user_record(
        "<command-name>/reload-plugins</command-name>\n"
        "            <command-message>reload-plugins</command-message>\n"
        "            <command-args></command-args>"))
    assert [(one.kind, one.text) for one in blocks] == [
        ("prompt", "/reload-plugins")]


def test_a_slash_command_keeps_what_was_passed_to_it(ws, tmp_path):
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    blocks = reader.add(user_record(
        "<command-name>/plugin</command-name>"
        "<command-message>plugin</command-message>"
        "<command-args>install dt-mla</command-args>"))
    assert [one.text for one in blocks] == ["/plugin install dt-mla"]


def test_a_command_s_own_output_is_not_a_prompt(ws, tmp_path):
    """`(no content)` is not something anybody typed, and neither is the
    caveat Claude Code puts in front of a resumed conversation."""
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    for text in ("<local-command-stdout>(no content)</local-command-stdout>",
                 "<local-command-stdout>✔ Updated 1 marketplace"
                 "</local-command-stdout>",
                 "<local-command-caveat>Caveat: The messages below were"
                 " generated while a session was resumed."
                 "</local-command-caveat>"):
        assert reader.add(user_record(text)) == [], text


def test_the_harness_speaking_is_a_note_and_not_your_prompt(ws, tmp_path):
    """Real news, so it is shown — but nobody typed it, so it is not drawn
    as though they had."""
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    one, = reader.add(user_record(
        "<task-notification>Still waiting on the requirements analyst"
        "</task-notification>"))
    assert one.kind == "note"
    assert one.text == "Still waiting on the requirements analyst"

    two, = reader.add(user_record(
        "Another Claude session sent a message:\n\nthe repo sweep is in."))
    assert two.kind == "note"
    assert "the repo sweep is in." in two.text


#: What Claude Code writes when a message arrives while the agent is working
#: -- which is every message this page sends to a busy agent, so it is the
#: shape a reader of this program meets most. Header and footer verbatim from
#: a real transcript; the words between them are invented.
QUEUED = """<system-reminder>
The user sent a new message while you were working:
also creating a worktree would be slower, so many files to check out.
Is there a way to keep the corpus out of it?

This is how Claude Code surfaces messages the user sends mid-turn \u2014 within the running turn, often alongside the next tool result, rather than as a separate conversation turn. Address the message above as you continue this turn.
</system-reminder>"""


def test_a_message_sent_to_a_busy_agent_is_drawn_as_what_you_typed(ws, tmp_path):
    """Every message this page sends to a working agent comes back wrapped:
    a header naming it, a footer explaining it to the agent, both inside a
    `<system-reminder>`. All three went into the transcript as though the
    reader had typed them."""
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    one, = reader.add(user_record(QUEUED))
    assert one.kind == "prompt"
    assert one.text == (
        "also creating a worktree would be slower, so many files to check out."
        "\nIs there a way to keep the corpus out of it?")
    assert "while you were working" not in one.text
    assert "system-reminder" not in one.text


def test_a_queued_message_of_several_lines_keeps_all_of_them(ws, tmp_path):
    """The words between the two lines are the whole of what was typed, and
    a message sent from this page is often a paragraph."""
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    one, = reader.add(user_record(QUEUED.replace(
        "Is there a way to keep the corpus out of it?",
        "one\n\ntwo\n\nthree")))
    assert one.text.endswith("one\n\ntwo\n\nthree")


def test_a_prompt_that_talks_about_the_wrapper_is_still_a_prompt(ws, tmp_path):
    """Somebody asking about this very feature pastes the wrapper into the
    box — which is exactly how this bug was reported. Two things keep such a
    prompt whole: the header has to open the record, and the footer has to be
    there. Drop either and the question is answered with its own quotation.
    """
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    quoted = (
        "why does wostuast show this? e.g.\n"
        "The user sent a new message while you were working:\n"
        "my message\n\n"
        "This is how Claude Code surfaces messages the user sends mid-turn"
        " \u2014 within the running turn.\n"
        "is that Claude Code or you?")
    half = ("The user sent a new message while you were working:\n"
            "is that line yours or Claude Code's?")
    for typed in (
        quoted,                                     # the header does not open it
        half,                                       # no footer, so no wrapper
        "why does 'The user sent a new message while you were working:' show"
        " up in my transcript?",
        "The user sent a new message while you were working: is that from"
        " Claude Code or from wostuast?",
    ):
        one, = reader.add(user_record(typed))
        assert (one.kind, one.text) == ("prompt", typed), typed


def test_a_system_reminder_on_its_own_is_not_a_prompt(ws, tmp_path):
    """It is written to the agent, not by the reader. Shown as a prompt it
    put a paragraph of machine instructions in the reader's own rail."""
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    assert reader.add(user_record(
        "<system-reminder>The file has been read. Do not read it again."
        "</system-reminder>")) == []


def test_a_prompt_that_talks_about_a_command_is_still_a_prompt(ws, tmp_path):
    """Somebody asking about this very feature types `<command-name>` into
    the box. Only a record with nothing else on it is a command.

    Drop the "and nothing else" check and this prompt becomes the single
    word it is asking about.
    """
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    typed = ("why does <command-name>/reload-plugins</command-name> show up"
             " in my transcript?")
    one, = reader.add(user_record(typed))
    assert one.kind == "prompt"
    assert one.text == typed


def test_a_real_prompt_is_left_alone(ws, tmp_path):
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    one, = reader.add(user_record("Do the thing, please."))
    assert (one.kind, one.text) == ("prompt", "Do the thing, please.")
