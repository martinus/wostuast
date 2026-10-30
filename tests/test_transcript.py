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
    assert kinds == ["prompt", "text", "tool", "tool", "text",
                     "divider", "divider"]


def test_a_prompt_keeps_its_text(parsed):
    got = parsed
    assert got.blocks[0].kind == "prompt"
    assert "substring search" in got.blocks[0].text


def test_thinking_is_never_a_block_even_with_text_in_it(parsed):
    """Claude Code keeps the text of most thoughts out of the transcript, so
    a switch to show them showed nothing most of the time, and the reader
    chose to drop them. The fixture's one thought has text, and is still
    left out, and its words are nowhere in what the page is handed."""
    got = parsed
    assert all(b.kind != "thinking" for b in got.blocks)
    assert not any("exact name" in b.text for b in got.blocks)


def test_a_thought_claude_code_shows_as_an_update_is_the_agents_words(ws):
    """Claude Code 2.1.306 writes what the agent tells the reader between
    its calls as a thought, on a record with `thinkingDisplay: "updates"`,
    and the console shows it. The page dropped every thought, and the
    reader saw "Let me measure the baseline." and never what the baseline
    was. A thought with text on such a record is the agent's words, in
    its place; one that is a signature only is still nothing."""
    got = ws.Transcript(str(FIXTURE.with_name("narration.jsonl")))
    got.read_new()
    said = [(b.kind, b.text.strip()) for b in got.blocks if b.kind != "tool"]
    assert said == [
        ("text", "Let me measure the baseline."),
        ("text", "The baseline shows 91.09% stability, so I will warm up the statics first."),
        ("text", "The warm-up brings stability to 95.70%. I am mapping the edges that still vary."),
    ]
    assert [b.kind for b in got.blocks] == ["text", "tool", "tool", "text", "tool", "text"]


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
    # and then updated when its result arrives, so nine touches in all. The
    # fixture's thought makes no block.
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


def test_a_call_keeps_its_whole_input_when_its_line_cuts_it(ws, tmp_path):
    """An opened call showed what it printed and never what ran: the line
    cuts a command at 60 characters and folds its lines into one (#619).
    The block keeps the whole command, as it is, secrets and all, which the
    reader chose; a line that says it all keeps nothing more."""
    long = "for f in *.py; do\n  python3 -m pytest \"$f\" -q --maxfail=1 || break\ndone"
    secret = "curl -u me:hunter22 https://example.com"
    tool = {"command": "x", "file_path": "/w/dir/a.py"}
    path = tmp_path / "t.jsonl"
    path.write_text("".join(json.dumps({
        "type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": f"c{at}", "name": name, "input": given}]},
    }) + "\n" for at, (name, given) in enumerate([
        ("Bash", {"command": long}),
        ("Bash", {"command": "make -j"}),
        ("Bash", {"command": secret}),
        ("Read", tool),
        ("mcp__db__query", {"sql": "select 1", "limit": 5}),
        ("mcp__db__query", {"sql": "select * from a_table_with_a_long_name "
                                   "where one = 1 and two = 2 and three = 3"}),
    ])))
    blocks = ws.Transcript(str(path), "/w/dir").read_new()
    assert [one.call for one in blocks] == [
        long, "", secret, "", "",
        '{\n  "sql": "select * from a_table_with_a_long_name where one = 1'
        ' and two = 2 and three = 3"\n}']
    # The line still hides the secret; only the opened call shows it.
    assert "hunter22" not in blocks[2].target
    assert "\n" not in blocks[0].target


def test_a_long_command_is_cut_and_says_how_much_is_left(ws):
    """A heredoc can carry a whole file: the page is sent `CALL_SHOWN`
    lines of it, and the count of the rest."""
    block = ws.Block(kind="tool", tool="Bash",
                     call="\n".join(f"line {n}" for n in range(ws.CALL_SHOWN + 7)))
    sent = ws.blocks_json([block])[0]["call"]
    assert sent.splitlines()[ws.CALL_SHOWN - 1] == f"line {ws.CALL_SHOWN - 1}"
    assert sent.endswith("… 7 more lines")


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
    blocks, run, _ = daemon.read_transcript("s1")
    assert [b.text for b in blocks] == ["one"]

    second = transcript_file("s2-elsewhere", [
        {"type": "assistant", "message": {"role": "assistant", "content": "two"}}])
    ws.append_event(conftest.event("SessionStart", sid="s1", cwd="/w/one",
                                   transcript_path=str(second),
                                   ts=time.time() + 1))
    daemon.store.refresh()
    blocks, later, _ = daemon.read_transcript("s1")
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
        ("command", "/reload-plugins")]


def test_a_slash_command_keeps_what_was_passed_to_it(ws, tmp_path):
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    blocks = reader.add(user_record(
        "<command-name>/plugin</command-name>"
        "<command-message>plugin</command-message>"
        "<command-args>install dt-mla</command-args>"))
    assert [one.text for one in blocks] == ["/plugin install dt-mla"]


def test_a_command_s_own_output_is_not_a_prompt(ws, tmp_path):
    """`(no content)` is not something anybody typed, and neither is the
    caveat Claude Code puts in front of a resumed conversation: neither draws
    anything. An answer with no command before it is drawn as an answer."""
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    for text in ("<local-command-stdout>(no content)</local-command-stdout>",
                 "<local-command-caveat>Caveat: The messages below were"
                 " generated while a session was resumed."
                 "</local-command-caveat>"):
        assert reader.add(user_record(text)) == [], text
    alone, = reader.add(user_record(
        "<local-command-stdout>✔ Updated 1 marketplace</local-command-stdout>"))
    assert (alone.kind, alone.text, alone.result) == (
        "command", "", "✔ Updated 1 marketplace")


def test_a_slash_command_and_what_it_answered_are_one_block(ws, tmp_path):
    """`/model opus` typed from the page's send box changed the model, and the
    page showed the command and nothing of what it did: Claude Code's answer
    was dropped as plumbing. And a `/model` closed without a pick, or
    `/context`, came as `system` records the reader did not read at all.
    Measured on 2.1.283; the fixture is those records, with the paths and ids
    made up. `/context` writes colour codes, which a page would show as
    `[38;5;244m` litter."""
    import json
    from pathlib import Path
    fixture = Path(__file__).parent / "fixtures" / "local_command.jsonl"
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    for line in fixture.read_text().splitlines():
        reader.add(json.loads(line))
    shown = [(one.kind, one.text, one.result) for one in reader.blocks]
    kept, picked, context = shown
    assert kept == ("command", "/model", "Kept model as `Sonnet 5 (default)`")
    assert picked == ("command", "/model opus", "Set model to `Opus 5.5` and"
                      " saved as your default for new sessions")
    assert context[:2] == ("command", "/context")
    assert "Context Usage" in context[2] and "⛀" in context[2]
    assert "\x1b" not in context[2] and "[38;5" not in context[2]
    # The caveat draws nothing, and neither does the Markdown copy of the
    # answer Claude Code hands the agent straight after `/context`: the page
    # drew those numbers twice, the second time as raw Markdown.
    assert not any("## Context Usage" in (one.text or "") for one in reader.blocks)
    # A command that sends the agent a prompt -- `/init`, measured -- writes
    # it as an `isMeta` record with no answer before it. That one is shown.
    sent = ws.Transcript(str(tmp_path / "s.jsonl"))
    sent.add(user_record("<command-message>init</command-message>\n"
                         "<command-name>/init</command-name>"))
    body = dict(user_record("Please analyze this codebase."), isMeta=True)
    note, = sent.add(body)
    assert (note.kind, note.text) == ("note", "Please analyze this codebase.")
    # And only once: a second `isMeta` record after an answer is shown.
    again = ws.Transcript(str(tmp_path / "a.jsonl"))
    again.add(user_record("<command-name>/context</command-name>"))
    again.add(user_record("<local-command-stdout>grid</local-command-stdout>"))
    assert again.add(dict(user_record("the copy"), isMeta=True)) == []
    later, = again.add(dict(user_record("a hook's answer"), isMeta=True))
    assert later.kind == "note"
    # Only straight after: a prompt between them makes it a note again.
    between = ws.Transcript(str(tmp_path / "b.jsonl"))
    between.add(user_record("<command-name>/context</command-name>"))
    between.add(user_record("<local-command-stdout>grid</local-command-stdout>"))
    between.add(user_record("and now a prompt"))
    shown, = between.add(dict(user_record("a skill's body"), isMeta=True))
    assert shown.kind == "note"
    # An answer of "(no content)" has nothing to echo.
    empty = ws.Transcript(str(tmp_path / "e.jsonl"))
    empty.add(user_record("<command-name>/reload-plugins</command-name>"))
    empty.add(user_record("<local-command-stdout>(no content)</local-command-stdout>"))
    kept, = empty.add(dict(user_record("a skill's body"), isMeta=True))
    assert kept.kind == "note"
    # "(no content)" closes the command's block and draws nothing.
    quiet = ws.Transcript(str(tmp_path / "q.jsonl"))
    one, = quiet.add(user_record("<command-name>/reload-plugins</command-name>"
                                 "<command-message>reload-plugins"
                                 "</command-message><command-args></command-args>"))
    same, = quiet.add(user_record(
        "<local-command-stdout>(no content)</local-command-stdout>"))
    assert same is one and (one.result, one.answered) == ("", True)
    # An answer never lands in a block that already has one.
    other, = quiet.add(user_record(
        "<local-command-stdout>Reloaded 3 plugins</local-command-stdout>"))
    assert other is not one and other.text == ""
    # A command nobody typed -- another session's, or Claude Code's own -- is
    # the harness speaking, like any other words that are not the reader's.
    fresh = ws.Transcript(str(tmp_path / "f.jsonl"))
    theirs = fresh.user_block("<command-name>/compact</command-name>", 0.0, True)
    assert theirs.kind == "note"


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


def test_a_message_queued_while_the_agent_works_is_drawn(ws, tmp_path):
    """2.1.276 to 2.1.281 write a message typed into a busy agent as an
    `attachment` record, and no `user` record follows it -- read on this
    machine: eighteen queued prompts, none of them anywhere else. `add` read
    `user` and `assistant` only, so the page showed the agent answering a
    message that was not on it."""
    from conftest import record
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    one, = reader.add(record("queued", "and keep the old name as an alias"))
    assert (one.kind, one.text) == ("prompt", "and keep the old name as an alias")
    assert one.ts > 0
    # Another session's message, and a background task's news, are shown,
    # and never in the reader's rail.
    two, = reader.add(record("peer", "the sweep is done"))
    assert two.kind == "note"
    # By its origin alone, too: `isMeta` is not promised on every build.
    unmarked = record("peer", "the sweep is done")
    del unmarked["attachment"]["isMeta"]
    assert [one.kind for one in reader.add(unmarked)] == ["note"]
    three, = reader.add(record(
        "task", "<task-notification>Build finished</task-notification>"))
    assert (three.kind, three.text) == ("note", "Build finished")
    # A paste typed into a busy agent is a list of pieces.
    four, = reader.add({"type": "attachment", "timestamp": "2026-09-18T14:00:00Z",
                        "attachment": {"type": "queued_command",
                                       "commandMode": "prompt",
                                       "origin": {"kind": "human"},
                                       "prompt": [{"type": "text", "text": "see"},
                                                  {"type": "image"}]}})
    assert (four.kind, four.text) == ("prompt", "see")
    # Every other attachment stays out.
    assert reader.add({"type": "attachment",
                       "attachment": {"type": "todo_reminder", "prompt": "x"}}) == []


def test_what_claude_code_wrote_itself_is_never_your_prompt(ws, tmp_path):
    """`isMeta` marks a `user` record the harness wrote: a Stop hook's
    answer, a whole skill's body, "Continue from where you left off.". Each
    wore the reader's rail and opened a round on the map, named after it."""
    from conftest import record
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    for said in ("Stop hook feedback:\n[~/.claude/check.sh]: commit first",
                 "Continue from where you left off.",
                 "Base directory for this skill: /x\n\n# Do the thing"):
        one, = reader.add(record("meta", said))
        assert one.kind == "note", said
    assert reader.add(record("meta", "<system-reminder>x</system-reminder>")) == []
    # Claude Code writes both shapes of content, and an image's caption comes
    # as pieces.
    pieces = record("meta", "")
    pieces["message"]["content"] = [{"type": "text", "text": "[Image: a.png]"}]
    assert [one.kind for one in reader.add(pieces)] == ["note"]


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


# --- text that was pasted rather than typed ---------------------------------

#: A review sent from the Review tab, as the reader's Claude Code wrote it:
#: every review has newlines, so every one is a paste, and a Claude Code that
#: keeps pastes apart writes it after the (empty) typed text, two newlines,
#: and a tag. The shape is from 2.1.281's own source, `icn` and `tLt`.
REVIEW = "# Task: review\n\nWhen you are done, write one short entry.\n\n" \
         "## native/log.0.log:1\n\n> 2026-09-23 07:37:45.749 UTC info\n\n" \
         "remove the untracked files"


def pasted(body, paste_id="1da8"):
    return (f'<pasted_content id="{paste_id}">\n{body}\n'
            f'</pasted_content id="{paste_id}">\n')


def test_a_pasted_review_is_drawn_without_its_tags(ws, tmp_path):
    """It came back as `<pasted_content id="1da8">`, the review, and the
    closing tag, under two empty lines. Claude Code's own screen takes the
    tags off; this page did not."""
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    one, = reader.add(user_record("\n\n" + pasted(REVIEW)))
    assert one.kind == "prompt"
    assert one.text == REVIEW


def test_a_paste_stands_as_its_own_paragraph_among_typed_words(ws, tmp_path):
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    one, = reader.add(user_record(
        "look at this\n\n" + pasted("line one\nline two", "0a0b")
        + "\nand fix it"))
    assert one.text == "look at this\n\nline one\nline two\n\nand fix it"
    two, = reader.add(user_record(
        pasted("first", "aaaa") + pasted("second", "bbbb")))
    assert two.text == "first\n\nsecond"


def test_a_paste_inside_a_queued_message_comes_off_too(ws, tmp_path):
    """The two wrappers meet: a review sent while the agent works is a
    paste inside a queued message."""
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    one, = reader.add(user_record(QUEUED.replace(
        "Is there a way to keep the corpus out of it?",
        pasted("the review\nin two lines"))))
    assert one.kind == "prompt"
    assert "pasted_content" not in one.text
    assert one.text.endswith("the review\nin two lines")


@pytest.mark.parametrize("text", [
    '<pasted_content id="1DA8">\nx\n</pasted_content id="1DA8">',   # not its id
    '<pasted_content id="1da">\nx\n</pasted_content id="1da">',
    '<pasted_content id="1da8">x</pasted_content id="1da8">',        # not its lines
    '<pasted_content id="1da8">\nx with no closing tag',
    '<pasted_content id="1da8">\nx\n</pasted_content id="2db9">',    # not its pair
])
def test_what_is_not_claude_codes_paste_is_left_as_it_was_typed(ws, text):
    """Somebody asking about this very tag types one, and that is a prompt.
    Only the exact shape Claude Code writes -- the rules of its own reader
    -- comes off."""
    assert ws.unwrap_pastes(text) == text


def test_an_interrupt_claude_code_wrote_is_a_note_not_your_prompt(ws, tmp_path):
    """Escape makes Claude Code write "[Request interrupted by user for tool
    use]" as a `user` record -- measured on 2.1.282, once for every decline.
    It wore the reader's rail and named a round on the map. A prompt that
    quotes it is still a prompt."""
    for said, shown in (("[Request interrupted by user for tool use]",
                         "Interrupted during a tool call."),
                        ("[Request interrupted by user]", "Interrupted.")):
        assert ws.read_user_text(said) == ("note", shown)
    asked = "why does it say [Request interrupted by user] here?"
    assert ws.read_user_text(asked) == ("prompt", asked)


def test_a_command_run_with_a_bang_is_one_block_with_its_output(ws, tmp_path):
    """`!git up` in Claude Code writes two `user` records, neither `isMeta`:
    `<bash-input>` and then `<bash-stdout>`/`<bash-stderr>`, the output with
    `<`, `>` and `&` as HTML entities. Both were drawn as prompts, tags and
    entities and all. Measured on 2.1.282; the fixture is that shape."""
    import json
    from pathlib import Path
    fixture = Path(__file__).parent / "fixtures" / "bash_mode.jsonl"
    command, printed = [json.loads(line) for line in fixture.read_text().splitlines()]
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    one, = reader.add(command)
    assert (one.kind, one.text, one.result) == ("shell", "git up", "")
    # The output goes into the command's block: one thing to read.
    same, = reader.add(printed)
    assert same is one and len(reader.blocks) == 1
    assert "-> origin/OLD-1-remove-a-flag" in one.result
    assert "origin/OLD-2-a & b <draft>" in one.result
    assert "&gt;" not in one.result and "<bash-" not in one.result
    # An entity that was printed is printed: Claude Code escaped the `&`.
    reader.add(command)
    literal = dict(printed, message={"role": "user", "content":
        "<bash-stdout>&amp;lt;b&amp;gt; stays</bash-stdout>"
        "<bash-stderr>fatal: no remote</bash-stderr>"})
    two, = reader.add(literal)
    assert two.result == "&lt;b&gt; stays\nfatal: no remote"
    # Output with no command before it stands alone, and never lands in a
    # block that already has its own.
    three, = reader.add(literal)
    assert three is not two and (three.kind, three.text) == ("shell", "")
    # A prompt that only mentions the tag is a prompt.
    asked = dict(command, message={"role": "user", "content":
        "why does <bash-input>ls</bash-input> show up as a prompt?"})
    four, = reader.add(asked)
    assert four.kind == "prompt"


def test_a_task_notification_and_another_sessions_message_read_as_words(ws, tmp_path):
    """`wostuast shapes` found 272 task notes drawn with `<task-id>`,
    `<output-file>` and `<usage>` in them, and every message from another
    session drawn inside its `<agent-message>` tag with the paragraph
    Claude Code writes to the agent after it. A task note is its summary and
    its result; a message is the words sent. The fixture is the five shapes
    measured on 2.1.276 to 2.1.283, with made-up text."""
    import json
    from pathlib import Path
    fixture = Path(__file__).parent / "fixtures" / "notes.jsonl"
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    shown = []
    for line in fixture.read_text().splitlines():
        shown += [(one.kind, one.text) for one in reader.add(json.loads(line))]
    full, short, queued, sent, sent_queued = shown
    done = ('Background command "Run the test suite" completed (exit code 0)'
            "\n\n412 passed in 31.2s")
    assert full == ("note", done) and queued == ("note", done)
    assert short == ("note", 'Task "watch the build" was stopped')
    words = "From another session:\n\nThe migration script is written and its tests pass."
    assert sent == ("note", words) and sent_queued == ("note", words)
    for _, text in shown:
        assert "<" not in text and "other Claude session" not in text
    # A notification in a shape nobody has measured is shown as it came.
    odd = ws.read_user_text("<task-notification><phase>3</phase></task-notification>")
    assert odd == ("note", "<phase>3</phase>")


def test_an_edit_keeps_what_it_changed_and_nothing_of_the_whole_file(ws, tmp_path):
    """The record that answers an Edit or a Write carries the change as
    Claude Code measured it -- `toolUseResult.structuredPatch`, hunks with
    the file's line numbers at that moment -- beside the whole old file, the
    whole new one and a git diff of all of it. The transcript shows the
    change under the call, so the block keeps the hunks in the Diff tab's
    shape and none of the rest: a session edits hundreds of times, and every
    block goes to the page. Measured on 2.1.278, `tests/fixtures/edits.jsonl`."""
    fixture = Path(__file__).parent / "fixtures" / "edits.jsonl"
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    for line in fixture.read_text().splitlines():
        reader.add(json.loads(line))
    edit, created, rewritten, failed = reader.blocks
    assert edit.patch == [{
        "header": "@@ -1,5 +1,6 @@",
        "lines": [{"kind": "context", "text": "def total(items):"},
                  {"kind": "added", "text": '    """The sum of the prices, in cents."""'},
                  {"kind": "context", "text": "    return sum(items)"},
                  {"kind": "context", "text": ""},
                  {"kind": "context", "text": ""}]}]
    assert edit.patch_more == 0
    # The counts are the change's: one line added. Counted from the strings,
    # which carry the lines round the change too, it said +3 -2.
    assert (edit.added, edit.removed) == (1, 0)
    assert (created.added, created.removed) == (3, 0)
    assert (rewritten.added, rewritten.removed) == (1, 1)
    # A new file has no patch of its own: its text is the change.
    assert created.patch == [{
        "header": "@@ -0,0 +1,3 @@",
        "lines": [{"kind": "added", "text": "# Notes"},
                  {"kind": "added", "text": ""},
                  {"kind": "added", "text": "Prices are in cents."}]}]
    assert [line["kind"] for line in rewritten.patch[0]["lines"]] == [
        "context", "context", "removed", "added"]
    assert rewritten.patch[0]["header"] == "@@ -5,3 +5,3 @@"
    # An edit that did not happen changed nothing.
    assert failed.failed and failed.patch == []
    # Nothing of the whole file reaches the page.
    sent = json.dumps(ws.blocks_json(reader.blocks))
    assert "whole file, never kept" not in sent
    assert "0.2\\n" not in sent and "originalFile" not in sent


def test_a_long_change_is_cut_and_says_how_much_is_left(ws, tmp_path):
    """A Write over a file sends a patch over all of it, and one of 500 lines
    is not something to read under a tool call: the Diff tab is for that.
    The block keeps `PATCH_SHOWN` lines and counts the rest, and a line of
    the file that holds a line break of its own is still one line."""
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    reader.add(conftest.record("tool", "/w/big.py", tool="Write", tool_id="w"))
    many = [f"+line {n}" for n in range(500)]
    body = conftest.record("result", "ok", tool_id="w")
    body["toolUseResult"] = {"type": "update", "structuredPatch": [
        {"oldStart": 1, "oldLines": 0, "newStart": 1, "newLines": 500, "lines": many}]}
    reader.add(body)
    block, = reader.blocks
    assert sum(len(h["lines"]) for h in block.patch) == ws.PATCH_SHOWN
    assert block.patch_more == 500 - ws.PATCH_SHOWN
    assert block.added == 500       # every line, and not only those kept
    # A result that failed changed nothing, whatever its record carries.
    refused = ws.Transcript(str(tmp_path / "r.jsonl"))
    refused.add(conftest.record("tool", "/w/a.py", tool="Edit", tool_id="e"))
    said = conftest.record("result", "not found", tool_id="e")
    said["message"]["content"][0]["is_error"] = True
    said["toolUseResult"] = {"structuredPatch": [
        {"oldStart": 1, "oldLines": 1, "newStart": 1, "newLines": 1, "lines": ["-a", "+b"]}]}
    refused.add(said)
    assert refused.blocks[0].patch == [] and refused.blocks[0].failed
    # A new file's text is split on newlines only, as a diff is.
    fresh = ws.Transcript(str(tmp_path / "f.jsonl"))
    fresh.add(conftest.record("tool", "/w/new.txt", tool="Write", tool_id="n"))
    made = conftest.record("result", "ok", tool_id="n")
    made["toolUseResult"] = {"type": "create", "structuredPatch": [],
                             "content": "one still one\ntwo\n"}
    fresh.add(made)
    assert [line["text"] for line in fresh.blocks[0].patch[0]["lines"]] == [
        "one still one", "two"]


def test_a_plan_is_a_block_of_its_own_with_the_whole_markdown(ws):
    """`ExitPlanMode` was a tool row: its input as JSON, cut at 80
    characters. It is the plan's own Markdown now, whole, and it keeps the
    call's id, so the rejection Escape writes still marks it answered --
    that is the proof a No's reason waits for (`call_answered`)."""
    path = conftest.FIXTURES / "plan_transcript.jsonl"
    # A result hands its call back again, changed: one block a place.
    read = ws.Transcript(str(path), "/w/repo/dir").read_new()
    blocks = list({one.seq: one for one in read}.values())
    plans = [one for one in blocks if one.kind == "plan"]
    assert len(plans) == 1, [one.kind for one in blocks]
    plan = plans[0]
    assert plan.text.startswith("# Fix the race in the cache\n")
    assert "| cache.py | lock |" in plan.text
    assert plan.tool == "ExitPlanMode" and plan.tool_use_id == "toolu_exit1"
    assert plan.answered and plan.failed
    # The Write that made the plan file is still the tool row it was.
    assert [one.tool for one in blocks if one.kind == "tool"] == ["Write"]


def test_a_plan_call_with_no_plan_stays_a_tool_row(ws, tmp_path):
    """An older Claude Code, or one that sent nothing: no plan, no block."""
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps({
        "type": "assistant", "timestamp": "2026-10-03T17:30:30.000Z",
        "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "ExitPlanMode", "input": {}}]}}) + "\n")
    [block] = ws.Transcript(str(path)).read_new()
    assert block.kind == "tool" and block.tool == "ExitPlanMode"


def test_a_compaction_carries_its_moment(ws, tmp_path):
    """The line says when the agent forgot (#499)."""
    reader = ws.Transcript(str(tmp_path / "t.jsonl"))
    made = reader.add({"type": "system", "subtype": "compact_boundary",
                       "timestamp": "2026-09-18T14:22:00.000Z"})
    assert made[0].kind == "divider"
    assert made[0].ts == ws.parse_timestamp("2026-09-18T14:22:00.000Z")


def pr_record(number=12, url="https://github.com/o/r/pull/12", repo="o/r"):
    """A `pr-link` record in the shape Claude Code's schema gives (2.1.312):
    no real one was measured, as the owner chose (#661)."""
    return {"type": "pr-link", "sessionId": "s1", "prNumber": number, "prUrl": url,
            "prRepository": repo, "timestamp": "2026-10-29T18:00:00.000Z"}


def test_a_pr_link_is_taken_only_as_a_number_and_a_web_address(ws):
    """The page makes a link of it, so only http(s), with no user or
    password, and a number that is a number (topics/safety)."""
    assert ws.pr_link_of(pr_record()) == ws.PrLink(12, "https://github.com/o/r/pull/12", "o/r")
    for wrong in (pr_record(url="javascript:alert(1)"), pr_record(url="file:///etc/passwd"),
                  pr_record(url="ftp://github.com/o/r/pull/1"),
                  pr_record(url="https://me:token@github.com/o/r/pull/1"),
                  pr_record(url="https://github.com/o/r/pull/1 x"),
                  pr_record(number="12"), pr_record(number=True), pr_record(number=0),
                  {**pr_record(), "type": "summary"}, "pr-link"):
        assert ws.pr_link_of(wrong) is None, wrong


def test_the_last_pr_link_in_a_transcript_s_end_stands(ws, tmp_path):
    """Claude Code writes it again and again, and the last one stands. Only
    the end is read: a line cut in two by it is skipped."""
    path = tmp_path / "s1.jsonl"
    path.write_text(conftest.records(
        conftest.record("you", "open the pull request"),
        pr_record(7, "https://github.com/o/r/pull/7"),
        conftest.record("claude", "x" * (ws.TAIL_READ // 2)),
        pr_record(9, "https://github.com/o/r/pull/9"),
        conftest.record("claude", "done")))
    assert ws.pr_link_in(path).number == 9
    path.write_text(json.dumps(pr_record(3)) + "\n" + "y" * ws.TAIL_READ + "\n")
    assert ws.pr_link_in(path) is None, "only the end is read"
    assert ws.pr_link_in(tmp_path / "gone.jsonl") is None


def test_a_session_is_given_its_pull_request_behind_the_fold(ws, transcript_file, monkeypatch):
    """Read as git is, a step of `refresh` and never the fold: a few
    transcripts a refresh, each again only when it changed."""
    path = transcript_file("s1", [pr_record()])
    ws.append_event(conftest.event("SessionStart", ts=time.time(), transcript_path=str(path)))
    store = ws.Store()
    assert store.refresh() is True
    assert store.rows[0]["pr"] == {"number": 12, "url": "https://github.com/o/r/pull/12",
                                   "repo": "o/r"}
    read = []
    monkeypatch.setattr(ws, "pr_link_in", lambda path: read.append(path) or None)
    store.refresh()
    assert read == [], "looked at again only after PR_EVERY"
    monkeypatch.setattr(ws, "PR_EVERY", 0.0)
    store.refresh()
    assert read == [], "unchanged: not read again"
    with path.open("a") as handle:
        handle.write("\n")
    assert store.refresh() is True and len(read) == 1
    assert store.rows[0]["pr"] is None


def test_a_refresh_reads_only_so_many_transcripts(ws, transcript_file, monkeypatch):
    """A start with a month of sessions read every tail before the first
    push: a few a refresh, the rest on the next."""
    for n in range(5):
        path = transcript_file(f"s{n}", [pr_record(n + 1)])
        ws.append_event(conftest.event("SessionStart", sid=f"s{n}", ts=time.time(),
                                       transcript_path=str(path)))
    monkeypatch.setattr(ws, "PR_READS_A_TICK", 2)
    store = ws.Store()
    store.refresh()
    assert sum(1 for one in store.rows if one["pr"]) == 2
    store.refresh()
    assert sum(1 for one in store.rows if one["pr"]) == 4


def reply(at, tokens=250_000, ttl="1h", **more):
    """An assistant record with the `usage` Claude Code writes: the context
    it sent, mostly read from the cache, and what it wrote to which cache.
    Measured on 2.1.314: `cache_creation` splits the write by lifetime."""
    written = {"ephemeral_1h_input_tokens": 3000 if ttl in ("1h", "both") else 0,
               "ephemeral_5m_input_tokens": 3000 if ttl in ("5m", "both") else 0}
    usage = {"input_tokens": 10, "cache_read_input_tokens": tokens - 3010,
             "cache_creation_input_tokens": 3000 if ttl else 0, "output_tokens": 50,
             "cache_creation": written if ttl else {}}
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(at))
    return {"type": "assistant", "timestamp": stamp, "isSidechain": False,
            "message": {"role": "assistant", "usage": usage,
                        "content": [{"type": "text", "text": "done"}]}, **more}


def test_idle_compaction_comes_54_minutes_after_a_long_conversation_s_last_request(ws, tmp_path):
    """Claude Code 2.1.314 compacts a conversation of 200,000 tokens or more
    at nine tenths of its 1-hour cache's life after the last request, before
    the cache expires (its code; not measured). The last reply of the
    conversation itself counts: a subagent's and one that used no API come
    after it here, and are not it."""
    path = tmp_path / "s1.jsonl"
    last = 1_800_000_000.0
    sidechain = {**reply(last + 60), "isSidechain": True}
    synthetic = reply(last + 90)
    synthetic["message"]["usage"] = {"input_tokens": 0, "output_tokens": 0}
    path.write_text(conftest.records(reply(last - 600), reply(last), sidechain, synthetic))
    assert ws.idle_compact_at(ws.last_request_in(path)) == last + 54 * 60

    def due(**how):
        path.write_text(conftest.records(reply(last, **how)))
        return ws.idle_compact_at(ws.last_request_in(path))

    assert due(tokens=200_000) == last + 54 * 60
    assert due(tokens=199_999) == 0.0, "too small to compact"
    assert due(ttl="5m") == 0.0, "a 5-minute cache is gone before"
    assert due(ttl="both") == 0.0, "a 5-minute write wins, as in Claude Code"
    assert due(ttl="") == 0.0, "no cache written, no lifetime known"
    assert ws.last_request_in(tmp_path / "gone.jsonl") is None


def test_a_session_is_given_its_idle_compaction_behind_the_fold(ws, transcript_file):
    """Read with the pull request, and never once the reader turned it off
    with `"idleCompaction": false`, which Claude Code's notice names."""
    last = float(int(time.time()) - 60)      # the stamp keeps whole seconds
    path = transcript_file("s1", [reply(last)])
    ws.append_event(conftest.event("SessionStart", ts=time.time(), transcript_path=str(path)))
    store = ws.Store()
    store.refresh()
    assert store.rows[0]["idle_compact_at"] == round(last + 54 * 60, 3)
    ws.settings_path().write_text(json.dumps({"idleCompaction": False}))
    store = ws.Store()
    store.refresh()
    assert store.rows[0]["idle_compact_at"] == 0


def recap(text, at):
    """An `away_summary` record in the shape Claude Code's schema gives
    (2.1.312): no real one was measured, as the owner chose (#662)."""
    stamp = (time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(at))
             + f".{int(at % 1 * 1000):03d}Z")
    return {"type": "system", "subtype": "away_summary", "content": text,
            "timestamp": stamp, "uuid": "u1", "isMeta": False}


def test_claude_code_s_recap_is_taken_only_after_the_last_answer(ws, tmp_path):
    """The last recap in the transcript's end, written at or after the
    turn's end; without the words Claude Code adds for its own terminal."""
    path = tmp_path / "s1.jsonl"
    ended = 1_800_000_000.0
    path.write_text(conftest.records(
        recap("Before the answer.", ended - 60),
        conftest.record("claude", "The answer."),
        recap("Built **the cache**. (disable recaps in /config)", ended + 10),
        # After it, and none of them a recap: another record that names
        # one, an empty one, and one whose words are no text.
        {**recap("Not a recap.", ended + 12), "subtype": "turn_duration",
         "after": "away_summary"},
        recap(" ", ended + 13), {**recap("x", ended + 14), "content": 3}))
    assert ws.away_summary_in(path, ended) == {"text": "Built **the cache**.",
                                               "at": ended + 10}
    assert ws.away_summary_in(path, ended + 11) is None, "older than the answer"
    assert ws.away_summary_in(tmp_path / "gone.jsonl", 0.0) is None
