"""The Summary tab's numbers (#622): where a session's tokens and time went."""

from __future__ import annotations

import json

from conftest import FIXTURES, event, record, records


def reply(made, mid, **used):
    """A record of a reply, with its message id and what it used, as
    Claude Code writes every record of one reply."""
    made["message"]["id"] = mid
    made["message"]["usage"] = used
    return made


def test_a_reply_counts_once_and_a_turn_runs_from_prompt_to_prompt(ws, tmp_path):
    """One reply is a record a content block, each with the reply's whole
    `usage` (measured on 2.1.306): counted per record, a reply of three
    blocks cost three times. A turn is a prompt and every reply up to the
    next one; a tool is counted per call."""
    path = tmp_path / "s1.jsonl"
    path.write_text(records(
        record("you", "refactor the parser"),
        reply(record("think", "hmm"), "m1", input_tokens=10, output_tokens=100,
              cache_read_input_tokens=1000),
        reply(record("tool", "ls", tool_id="t1"), "m1", input_tokens=10, output_tokens=100,
              cache_read_input_tokens=1000),
        record("result", "a b", tool_id="t1"),
        reply(record("tool", "pwd", tool_id="t2"), "m2", input_tokens=5, output_tokens=7),
        record("result", "/w", tool_id="t2"),
        record("you", "now the tests"),
        reply(record("claude", "done"), "m3", input_tokens=1, output_tokens=2,
              cache_creation_input_tokens=40)))
    reader = ws.Transcript(str(path))
    reader.read_new()
    costs = reader.costs
    assert [turn.said for turn in costs.turns] == ["refactor the parser", "now the tests"]
    assert costs.turns[0].tokens == {"input_tokens": 15, "output_tokens": 107,
                                     "cache_read_input_tokens": 1000}
    assert costs.turns[0].replies == 2
    assert costs.turns[1].tokens == {"input_tokens": 1, "output_tokens": 2,
                                     "cache_creation_input_tokens": 40}
    assert costs.tools == {"Bash": 2}
    # Weighted as Anthropic prices them: output 5, a cache read a tenth.
    assert (costs.turns[0].weight, costs.turns[1].weight) == (650.0, 61.0)
    # The prompt's block, for a link to it.
    assert reader.blocks[costs.turns[1].seq].text == "now the tests"


def test_the_summary_shares_the_spend_out_by_weighted_tokens(ws, tmp_path):
    """The dollars are the status line's; each turn gets its share by its
    tokens, weighted as Anthropic prices them, the costliest first. The
    shares add up to the whole."""
    session = ws.Session(session_id="s1")
    session.status.cost_usd = 2.0
    costs = ws.Costs(turns=[
        ws.TurnCost(seq=0, said="small", tokens={"output_tokens": 10}, weight=50.0),
        ws.TurnCost(seq=4, said="big", tokens={"output_tokens": 30}, weight=150.0)])
    got = ws.summary_json(session, costs)
    assert [one["said"] for one in got["costly"]] == ["big", "small"]
    assert [one["usd"] for one in got["costly"]] == [1.5, 0.5]
    assert got["tokens"] == {"output_tokens": 40}
    session.status.cost_usd = None
    assert ws.summary_json(session, costs)["costly"][0]["usd"] is None, "no spend, no share"


def test_busy_is_prompt_to_end_and_an_interrupted_turn_ends_where_it_went_quiet(ws):
    """The status line's time is the session's whole life, idle hours too;
    busy is its turns. A turn the reader interrupts sends no `Stop`, so it
    ends at the last event it sent, not at the next prompt."""
    store = ws.Store()
    store.fold([event("SessionStart", ts=1000.0),
                event("UserPromptSubmit", ts=1100.0, prompt="go"),
                event("Stop", ts=1160.0),
                event("UserPromptSubmit", ts=2000.0, prompt="again"),
                event("PreToolUse", ts=2030.0, tool_name="Bash",
                      tool_input={"command": "sleep 9"}, tool_use_id="u1"),
                event("UserPromptSubmit", ts=5000.0, prompt="stop that"),
                event("PreToolUse", ts=5010.0, tool_name="Bash",
                      tool_input={"command": "ls"}, tool_use_id="u2")])
    session = store.sessions["s1"]
    assert session.busy == 60.0 + 30.0
    got = ws.summary_json(session, ws.Costs())
    assert got["busy"] == 100.0, "the turn still running counts to its last event"


def test_the_status_line_s_time_and_lines_are_kept(ws):
    """The status line's `cost` says how long the session ran, how long the
    model worked, and the lines its edits added and removed (#622)."""
    payload = json.loads((FIXTURES / "status.json").read_text())
    status = ws.status_from_payload(payload, now=1.0)
    assert (status.wall_ms, status.api_ms, status.lines_added, status.lines_removed) == (
        2730000, 411000, 156, 23)


def test_a_transcript_rewritten_starts_its_counts_again(ws, tmp_path):
    """A transcript rewritten under its own name -- a `/clear`, a resume --
    is another reading: its blocks start again, and so must what its turns
    used, or the old turns stood beside the new ones."""
    path = tmp_path / "s1.jsonl"
    path.write_text(records(record("you", "the old work"),
                            reply(record("claude", "ok"), "m1", output_tokens=900)))
    reader = ws.Transcript(str(path))
    reader.read_new()
    path.unlink()
    path.write_text(records(record("you", "new"),
                            reply(record("claude", "ok"), "m2", output_tokens=1)))
    reader.read_new()
    assert [turn.said for turn in reader.costs.turns] == ["new"]


def test_only_work_moves_a_turn_s_end(ws):
    """An interrupted turn sends no `Stop`, and an idle notification, a
    resume or a `SessionEnd` hours later counted the hours: only work moves
    its end, and a `SessionEnd` ends it there. A `Stop` older than the
    running turn, written late, ends nothing of it."""
    store = ws.Store()
    store.fold([event("SessionStart", ts=1000.0),
                event("UserPromptSubmit", ts=1100.0, prompt="go"),
                event("PreToolUse", ts=1105.0, tool_name="Bash",
                      tool_input={"command": "ls"}, tool_use_id="u1"),
                event("Notification", ts=1165.0, message="Claude is waiting for your input",
                      notification_type="idle_prompt"),
                event("SessionEnd", ts=11900.0, reason="other")])
    assert store.sessions["s1"].busy == 5.0
    store = ws.Store()
    store.fold([event("SessionStart", ts=1000.0),
                event("UserPromptSubmit", ts=1100.0, prompt="go"),
                event("UserPromptSubmit", ts=1110.0, prompt="again"),
                event("Stop", ts=1109.9),
                event("PreToolUse", ts=1150.0, tool_name="Bash",
                      tool_input={"command": "ls"}, tool_use_id="u1"),
                event("Stop", ts=1160.0)])
    assert store.sessions["s1"].busy == 50.0


def test_a_session_s_time_goes_by_tool_and_its_slowest_calls_are_kept(ws):
    """Each call's `duration_ms` (#663), the run alone and never the wait
    for a Yes (measured on 2.1.312), adds to its tool's time; a failed call
    took its time too. A subagent's calls are its own. A call under a
    second is no slow call, and a slow one begins at its end less its time.
    The same events read again count nothing twice."""
    calls = [event("PostToolUse", ts=1100.0, tool_name="Bash", tool_use_id="u1",
                   tool_input={"command": "make test"}, duration_ms=96_400),
             event("PostToolUse", ts=1100.0, tool_name="Read", tool_use_id="u2",
                   tool_input={"file_path": "/w/a.c"}, duration_ms=40),
             event("PostToolUseFailure", ts=1150.0, tool_name="Bash", tool_use_id="u3",
                   tool_input={"command": "make -j8"}, duration_ms=2_500, error="exit 2"),
             event("PostToolUse", ts=1160.0, tool_name="Grep", tool_use_id="u4",
                   agent_id="a1", agent_type="Explore", tool_input={"pattern": "x"},
                   duration_ms=9_000),
             event("PostToolUse", ts=1170.0, tool_name="Read", tool_use_id="u5",
                   tool_input={"file_path": "/w/b.c"})]
    store = ws.Store()
    store.fold([event("SessionStart", ts=1000.0), *calls])
    store.fold(calls)
    got = ws.summary_json(store.sessions["s1"], ws.Costs())
    assert got["tool_time"] == [{"tool": "Bash", "calls": 2, "seconds": 98.9},
                                {"tool": "Read", "calls": 1, "seconds": 0.04}]
    assert got["slow"] == [
        {"tool": "Bash", "what": "make test", "seconds": 96.4, "began": 1003.6},
        {"tool": "Bash", "what": "make -j8", "seconds": 2.5, "began": 1147.5}]
