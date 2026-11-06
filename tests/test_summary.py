"""The Summary tab's numbers (#622): where a session's tokens and time went."""

from __future__ import annotations

import json

import pytest

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
    # The tokens by what they cost, for the bar of the kinds (#688).
    assert got["weighted"] == {"output_tokens": 200.0}
    # The weight draws a turn's bar (#685), with no spend too.
    assert [one["weight"] for one in ws.summary_json(session, costs)["costly"]] == [150.0, 50.0]


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


def test_a_resume_the_cache_did_not_outlast_says_what_its_next_prompt_costs(ws):
    """Measured on 2.1.312: every resume's `SessionStart` says whether the
    cache likely expired, how many tokens the context is, and what caching
    them again costs (#664). Only an expired one is said, and the first
    prompt pays it."""
    store = ws.Store()
    resume = dict(source="resume", context_tokens=182_000, estimated_cache_write_usd=0.6731)
    store.fold([event("SessionStart", ts=1000.0, prompt_cache_likely_expired=False, **resume)])
    row = ws.row(store.sessions["s1"])
    assert (row["recache_usd"], row["recache_tokens"]) == (0.0, 0)
    store.fold([event("SessionStart", ts=2000.0, prompt_cache_likely_expired=True, **resume)])
    row = ws.row(store.sessions["s1"])
    assert (row["recache_usd"], row["recache_tokens"]) == (0.6731, 182_000)
    store.fold([event("UserPromptSubmit", ts=2010.0, prompt="go on")])
    assert ws.row(store.sessions["s1"])["recache_usd"] == 0.0


def test_the_cost_reader_reads_the_turns_the_whole_reader_does(ws, tmp_path):
    """The month's turns are read without the blocks (#698): only the lines
    that can hold a prompt or a reply's usage are parsed, and only a `user`
    record is made into blocks. The turns must come out as the whole
    reader's do, over every transcript the tests hold and one with each
    shape the filter must let through or keep out."""
    path = tmp_path / "s1.jsonl"
    path.write_text(records(
        record("you", 'what does "tool_result" mean?'),
        reply(record("tool", "ls", tool_id="t1"), "m1", output_tokens=10),
        record("result", "a b", tool_id="t1"),
        # A prompt beside a result, in one `user` record: read.
        {"type": "user", "timestamp": "2026-09-18T14:01:00.000Z", "message": {
            "role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t2", "content": "x"},
                {"type": "text", "text": "and now the tests"}]}},
        reply(record("claude", "ok"), "m2", output_tokens=20, cache_read_input_tokens=100)))
    for one in [path, *sorted(FIXTURES.glob("*.jsonl"))]:
        whole = ws.Transcript(str(one))
        whole.read_new()
        alone = ws.CostReader(one).read()
        assert ([(turn.said, turn.ts, turn.tokens, turn.weight, turn.replies)
                 for turn in alone.turns]
                == [(turn.said, turn.ts, turn.tokens, turn.weight, turn.replies)
                    for turn in whole.costs.turns]), one.name
    assert [turn.said for turn in ws.CostReader(path).read().turns] == [
        'what does "tool_result" mean?', "and now the tests"]
    # A tool's result with no text is most of the bytes, and is not parsed.
    assert not ws.may_cost(json.dumps(record("result", "a b")).encode())
    assert ws.may_cost(json.dumps(record("you", 'a "tool_result"')).encode())


def test_the_cost_reader_reads_on_and_starts_again_with_the_file(ws, tmp_path):
    """Asked every ten seconds, it reads only what is new; a transcript
    rewritten under its name starts its counts again, as the whole
    reader's do (`test_a_transcript_rewritten_starts_its_counts_again`)."""
    path = tmp_path / "s1.jsonl"
    path.write_text(records(record("you", "the old work"),
                            reply(record("claude", "ok"), "m1", output_tokens=900)))
    reader = ws.CostReader(path)
    assert [turn.said for turn in reader.read().turns] == ["the old work"]
    with path.open("a") as handle:
        handle.write(records(reply(record("claude", "more"), "m2", output_tokens=1)))
    assert [turn.replies for turn in reader.read().turns] == [2]
    path.unlink()
    path.write_text(records(record("you", "new"),
                            reply(record("claude", "ok"), "m3", output_tokens=1)))
    assert [turn.said for turn in reader.read().turns] == ["new"]
    path.unlink()
    path.write_text("")
    assert reader.read().turns == [], "a file rewritten to nothing"


def test_the_month_s_costliest_sessions_and_turns(ws):
    """A session's amount is how much its total grew this month; a turn's
    is its share of its session's whole total, of the turns that began this
    month (#698). A session that spent nothing this month is left out, and
    a turn of a session with no cost has no share."""
    import time

    def at(month, day):
        return time.mktime((2026, month, day, 12, 0, 0, 0, 0, -1))

    statuses = {
        "a": ws.Status(name="resumed", cost_usd=5.0,
                       days={"2026-09-30": 4.0, "2026-10-02": 5.0}),
        "b": ws.Status(name="new", cost_usd=3.0, days={"2026-10-03": 3.0}),
        "c": ws.Status(name="last month", cost_usd=2.0, days={"2026-09-20": 2.0}),
        "d": ws.Status(name="no cost", days={"2026-10-03": 1.0}),
    }
    costs = {
        "a": ws.Costs(turns=[ws.TurnCost(said="big", ts=at(10, 2), weight=50.0,
                                         tokens={"output_tokens": 10})]),
        "b": ws.Costs(turns=[ws.TurnCost(said="in September", ts=at(9, 30), weight=100.0),
                             ws.TurnCost(said="in October", ts=at(10, 3), weight=200.0)]),
        "d": ws.Costs(turns=[ws.TurnCost(said="unpriced", ts=at(10, 3), weight=9.0)]),
    }
    got = ws.month_costly_json(at(10, 3), statuses, costs)
    assert got["sessions"] == [{"id": "b", "name": "new", "usd": 3.0, "days": [0.0, 0.0, 3.0]},
                               {"id": "a", "name": "resumed", "usd": 1.0, "days": [0.0, 1.0, 0.0]},
                               {"id": "d", "name": "no cost", "usd": 1.0, "days": [0.0, 0.0, 1.0]}]
    # Its day marks it on the month's charts.
    assert [(one["id"], one["said"], one["usd"], one["day"]) for one in got["turns"]] == [
        ("a", "big", 5.0, 2), ("b", "in October", 2.0, 3)]
    assert got["turns"][0]["tokens"] == {"output_tokens": 10}
    assert got["turns"][0]["name"] == "resumed"


def test_the_daemon_reads_the_month_s_turns_of_the_sessions_it_keeps(ws, transcript_file):
    """`GET /api/spend` names the costliest sessions of the month, and the
    costliest turns of the sessions the daemon keeps, from their
    transcripts (#698). A session it does not keep is named, with no
    turns: its transcript is found only through it."""
    import time

    now = time.time()
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(now - 5))
    today = time.strftime("%Y-%m-%d")
    path = transcript_file("s1", [
        record("you", "the costly one", ts=stamp),
        reply(record("tool", "cat big", ts=stamp, tool_id="t1"), "m1", input_tokens=1000,
              output_tokens=900),
        record("result", "x" * 300, ts=stamp, tool_id="t1"),
        reply(record("claude", "ok", ts=stamp), "m2", cache_read_input_tokens=2000)])
    ws.append_event(event("SessionStart", ts=now, transcript_path=str(path)))
    ws.write_status("s1", ws.Status(name="kept", cost_usd=2.0, days={today: 2.0}))
    ws.write_status("gone", ws.Status(name="gone", cost_usd=7.0, days={today: 7.0}))
    daemon = ws.Daemon()
    daemon.store.refresh()
    got = daemon.spend(now)
    assert [(one["id"], one["usd"]) for one in got["sessions"]] == [("gone", 7.0), ("s1", 2.0)]
    assert [(one["id"], one["said"], one["usd"]) for one in got["turns"]] == [
        ("s1", "the costly one", 2.0)]
    assert got["days"][-1] == 9.0
    # And its tool results kept in context, from the same reading.
    assert [(one["call"], one["what"], one["tokens"]) for one in got["carried"]["results"]] \
        == [("t1", "cat big", 100)]
    # And its tokens by kind (#722), from the same reading.
    assert got["kinds"]["tokens"]["output_tokens"] == 900
    assert got["kinds"]["tokens"]["cache_read_input_tokens"] == 2000
    # Read on from where it stopped, by the same reader.
    reader = daemon.cost_readers[path]
    daemon.spend(now)
    assert daemon.cost_readers[path] is reader


def test_the_month_s_tokens_are_its_turns_by_kind_and_by_what_they_cost(ws):
    """The reader asked for the session's bar of what its tokens cost, for
    the whole month (#722): the tokens of the turns that began this month,
    of every session the daemon keeps, by kind, and weighed as a session's
    are. A turn of last month counts nothing."""
    import time

    now = time.time()
    turn = ws.TurnCost
    costs = {"s1": ws.Costs(turns=[
                 turn(ts=now, tokens={"output_tokens": 100, "input_tokens": 10}),
                 turn(ts=now - 40 * 86400, tokens={"output_tokens": 7000})]),
             "s2": ws.Costs(turns=[
                 turn(ts=now, tokens={"output_tokens": 20, "cache_read_input_tokens": 3000}),
                 turn(ts=0.0, tokens={"output_tokens": 9000})])}
    got = ws.month_tokens_json(now, costs)
    assert got["tokens"] == {"output_tokens": 120, "input_tokens": 10,
                             "cache_read_input_tokens": 3000}
    assert got["weighted"] == {key: round(count * ws.TOKEN_WEIGHTS[key], 1)
                               for key, count in got["tokens"].items()}
    # As a session's are weighed: one place holds the weights.
    session = ws.tokens_json(costs["s2"].turns[:1])
    assert session["weighted"]["output_tokens"] == got["weighted"]["output_tokens"] * 20 / 120


def test_what_the_context_cost_splits_into_the_start_the_results_and_the_rest(ws, tmp_path):
    """The reader asked why a cache read was 72 % of what a session spent
    and its tool results 28 %: every reply reads its whole context again,
    and the results are one part of it. The start every reply reads again
    is the smallest context any reply read, at each reply's own weights;
    the results cost what `Carry` counts for them; the conversation is the
    rest of what reading the context cost."""
    path = tmp_path / "s1.jsonl"
    path.write_text(records(
        record("you", "look around"),
        # 1000 tokens of context, read in full: a weight of 1 a token.
        reply(record("tool", "cat big", tool_id="t1"), "m1", input_tokens=1000,
              output_tokens=100),
        record("result", "x" * 300, tool_id="t1"),
        # 1700 from the cache, a tenth each: the result is the 600 it grew
        # past the 1000 before and that reply's 100 out.
        reply(record("claude", "read it"), "m2", cache_read_input_tokens=1700)))
    got = ws.CostReader(path).read().carry.parts()
    # The start: 1000 tokens at 1, then at a tenth. The result: 600 at a
    # tenth. All read: 1000 + 170; the conversation is what is left.
    assert got == {"start": 1100.0, "results": 60.0, "conversation": 10.0,
                   "start_tokens": 1000}
    # Each reply's context and its results, for the chart reply by reply.
    assert [point[:2] for point in ws.CostReader(path).read().carry.points] == [(1000, 0), (1700, 600)]
    reader = ws.Transcript(str(path))
    reader.read_new()
    store = ws.Store()
    store.fold([event("SessionStart", ts=1000.0, transcript_path=str(path))])
    assert ws.summary_json(store.sessions["s1"], reader.costs)["read"] == got


def test_the_month_s_tokens_are_split_by_what_they_were_for_as_a_session_s(ws, tmp_path):
    """The reader asked for the session's list of what the tokens were for,
    for the month too: the turns that began this month, of every session
    the daemon keeps, each with its own start. A turn of last month counts
    nothing; a month of one session is that session's split."""
    def session(name, stamp):
        path = tmp_path / f"{name}.jsonl"
        path.write_text(records(
            record("you", "look around", ts=stamp),
            reply(record("tool", "cat big", tool_id="t1", ts=stamp), "m1",
                  input_tokens=1000, output_tokens=100),
            record("result", "x" * 300, tool_id="t1", ts=stamp),
            reply(record("claude", "read it", ts=stamp), "m2",
                  cache_read_input_tokens=1700)))
        return ws.CostReader(path).read()

    now = ws.parse_timestamp("2026-09-18T14:00:00.000Z")
    this = session("s1", "2026-09-18T14:00:00.000Z")
    old = session("s2", "2026-08-01T14:00:00.000Z")
    got = ws.month_tokens_json(now, {"s1": this, "s2": old})["read"]
    whole = this.carry.parts()
    assert got == {key: whole[key] for key in ("start", "results", "conversation")}
    assert got == {"start": 1100.0, "results": 60.0, "conversation": 10.0}


def test_the_context_chart_gets_every_reply_or_an_even_few(ws):
    """A long session has thousands of replies, and a chart a few hundred
    pixels wide shows no more: every `every`-th reply, and the last, no
    more than `CONTEXT_POINTS`."""
    carry = ws.Carry(points=[(1000 + at, at, at // 100) for at in range(1000)], least=1000)
    got = ws.context_json(carry)
    assert (got["every"], got["replies"], got["least"]) == (4, 1000, 1000)
    assert got["points"][0] == [1000, 0] and got["points"][-1] == [1999, 999]
    assert len(got["points"]) <= ws.CONTEXT_POINTS
    few = ws.context_json(ws.Carry(points=[(5, 1, 0), (6, 2, 0)], least=5))
    assert few["points"] == [[5, 1], [6, 2]] and few["every"] == 1


def test_the_context_chart_says_where_each_turn_begins(ws):
    """The reader asked to see the turns on the chart: each turn's first
    point, and its prompt for a hover and a link. A turn with no reply, as
    the third here, has none; neither has one none of whose replies is
    kept."""
    turns = [ws.TurnCost(seq=at, said=f"Step {at}.", ts=float(at)) for at in range(4)]
    carry = ws.Carry(points=[(5, 0, 0), (6, 0, 0), (7, 1, 1), (8, 1, 1), (9, 1, 1), (9, 2, 3)],
                     least=5)
    got = ws.context_json(carry, turns)["turns"]
    assert [(one["at"], one["turn"], one["said"]) for one in got] == [
        (0, 0, "Step 0."), (2, 1, "Step 1."), (5, 3, "Step 3.")]
    assert got[1]["seq"] == 1 and got[1]["ts"] == 1.0
    long = ws.Carry(points=[(1000 + at, 0, at // 10) for at in range(1000)], least=1000)
    kept = ws.context_json(long, [ws.TurnCost() for _ in range(100)])
    begins = [one["at"] for one in kept["turns"]]
    assert begins == sorted(set(begins)) and len(begins) == 100


def test_a_tool_result_costs_each_later_reply_until_the_context_goes(ws, tmp_path):
    """A result's tokens are its share, by its characters, of how much the
    next reply's context grew past the reply before and that reply's own
    output; every later reply reads it again, at that reply's weights. A
    compaction ends that, and so does a context that fell with no record
    to say so: a `/clear` that went on in the same file."""
    path = tmp_path / "s1.jsonl"
    path.write_text(records(
        record("you", "look around"),
        reply(record("tool", "cat big", tool_id="t1"), "m1", input_tokens=1000,
              output_tokens=100),
        record("result", "x" * 300, tool_id="t1"),
        # 1000 + 100 out + 600 for the result; half of it from the cache.
        reply(record("tool", "cat small", tool_id="t2"), "m2", cache_read_input_tokens=1100,
              cache_creation_input_tokens=600, output_tokens=50),
        record("result", "y" * 200, tool_id="t2"),
        # Words beside it, as Claude Code's own reminders come: half the 400.
        record("meta", "n" * 200),
        reply(record("claude", "read both"), "m3", cache_read_input_tokens=2150),
        {"type": "system", "subtype": "compact_boundary",
         "timestamp": "2026-09-18T14:00:00.000Z"},
        # A compaction of a small context, that fell less than a fall.
        reply(record("tool", "cat third", tool_id="t3"), "m4", input_tokens=1900),
        record("result", "z" * 30, tool_id="t3"),
        reply(record("claude", "after the compaction"), "m5", cache_read_input_tokens=2200),
        reply(record("claude", "after a /clear"), "m6", cache_read_input_tokens=200),
        reply(record("claude", "still after it"), "m7", cache_read_input_tokens=300)))
    reader = ws.Transcript(str(path))
    reader.read_new()
    carry = reader.costs.carry
    got = {one.what: (round(one.tokens), *carry.weighed(one)) for one in carry.results}
    # m2 read 1700 tokens at (110 + 750) / 1700 a token, m3 at a tenth.
    assert got["cat big"] == (600, pytest.approx(600 * (860 / 1700 + 0.1)), 2), \
        "m2 and m3 read it, and no reply after the compaction"
    assert got["cat small"] == (200, pytest.approx(20.0), 1)
    # m5 read it; m6's context fell to a quarter, so m6 and m7 did not.
    assert got["cat third"] == (300, pytest.approx(30.0), 1)
    session = ws.Session(session_id="s1")
    session.status.cost_usd = 3.0
    sent = ws.summary_json(session, reader.costs)["carried"]
    assert [one["what"] for one in sent["results"]] == ["cat big", "cat third", "cat small"]
    total = sum(turn.weight for turn in reader.costs.turns)
    big = sent["results"][0]
    assert big["usd"] == ws.turn_share(3.0, 600 * (860 / 1700 + 0.1), total)
    assert big["kept"] is False and big["replies"] == 2 and big["tokens"] == 600
    assert sent["share"] == round((600 * (860 / 1700 + 0.1) + 20 + 30) / total, 4)
    # The link goes to the call's block.
    assert big["call"] == "t1"


def test_the_cost_reader_reads_the_tool_results_the_whole_reader_does(ws, tmp_path):
    """The month's tool results kept in context are read without the
    blocks: a line of results with no text is not parsed, so its id is
    read from the bytes and its length is the line's (`RAW_PER_CHAR`). The
    calls, their targets and the replies that read them come out as the
    whole reader's, and the tokens near them."""
    path = tmp_path / "s1.jsonl"
    path.write_text(records(
        record("you", "look around"),
        reply(record("tool", "cat big", tool_id="t1"), "m1", input_tokens=1000,
              output_tokens=100),
        reply(record("tool", "notes.md", tool="Read", tool_id="t2"), "m1",
              input_tokens=1000, output_tokens=100),
        # Its target is read at once: the text it writes is not kept.
        reply(record("tool", "notes.md", tool="Edit", tool_id="t4"), "m1",
              input_tokens=1000, output_tokens=100),
        record("result", "x" * 3000, tool_id="t1"),
        record("result", "y" * 1000, tool_id="t2"),
        record("result", "e" * 1000, tool_id="t4"),
        reply(record("tool", "ls", tool_id="t3"), "m2", cache_read_input_tokens=3100,
              output_tokens=50),
        # A result with a text part is parsed, as it can hold a prompt.
        {"type": "user", "timestamp": "2026-09-18T14:01:00.000Z", "message": {
            "role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t3",
                 "content": [{"type": "text", "text": "z" * 400}]}]}},
        reply(record("claude", "ok"), "m3", cache_read_input_tokens=3300)))
    for one in [path, *sorted(FIXTURES.glob("*.jsonl"))]:
        whole = ws.Transcript(str(one))
        whole.read_new()
        alone = ws.CostReader(one).read()

        def read(carry):
            return [(it.call, it.tool, it.target(), carry.weighed(it)[1], it.tokens)
                    for it in carry.results]

        got, want = read(alone.carry), read(whole.costs.carry)
        assert [it[:4] for it in got] == [it[:4] for it in want], one.name
        for mine, theirs in zip(got, want):
            assert mine[4] == pytest.approx(theirs[4], rel=0.3), (one.name, mine, theirs)
    got = {it.call: (it.tool, it.target(), it.tokens)
           for it in ws.CostReader(path).read().carry.results}
    # 2000 more, three fifths of it the biggest result's; a line's own
    # fields make the smaller ones a little larger.
    assert got == {"t1": ("Bash", "cat big", pytest.approx(1200, rel=0.05)),
                   "t2": ("Read", "notes.md", pytest.approx(400, rel=0.1)),
                   "t4": ("Edit", "notes.md", pytest.approx(400, rel=0.1)),
                   "t3": ("Bash", "ls", 150)}


def test_the_month_s_tool_results_kept_in_context_and_by_tool(ws):
    """The reader asked for the month what the session's list says: the
    tool results that cost the most while they stayed in context, of all
    sessions kept, and what they cost by tool. Each is its share of its
    session's whole total, as a turn's is; a call of last month is left
    out, and a session with no cost gives no share."""
    import time

    def at(month, day):
        return time.mktime((2026, month, day, 12, 0, 0, 0, 0, -1))

    def costs(*results):
        held = ws.Costs(turns=[ws.TurnCost(ts=at(10, 1), weight=1000.0)])
        for call, tool, ts, weight in results:
            held.carry.results.append(ws.ResultCost(call=call, tool=tool, ts=ts, what=call,
                                                    tokens=weight * 10, weight=weight,
                                                    replies=4, gone=True))
        return held

    statuses = {"a": ws.Status(name="first", cost_usd=10.0),
                "b": ws.Status(name="second", cost_usd=2.0),
                "d": ws.Status(name="no cost")}
    got = ws.month_carried_json(at(10, 3), statuses, {
        "a": costs(("a1", "Bash", at(10, 2), 100.0), ("a2", "Read", at(10, 3), 300.0),
                   ("a0", "Bash", at(9, 30), 500.0)),
        "b": costs(("b1", "Bash", at(10, 1), 250.0)),
        "d": costs(("d1", "Bash", at(10, 2), 900.0))})
    assert [(one["id"], one["call"], one["usd"], one["day"], one["tokens"], one["replies"])
            for one in got["results"]] == [("a", "a2", 3.0, 3, 3000, 4),
                                           ("a", "a1", 1.0, 2, 1000, 4),
                                           ("b", "b1", 0.5, 1, 2500, 4)]
    assert got["results"][0]["what"] == "a2" and got["results"][0]["name"] == "first"
    assert got["tools"] == [{"tool": "Read", "usd": 3.0, "calls": 1, "tokens": 3000},
                            {"tool": "Bash", "usd": 1.5, "calls": 2, "tokens": 3500}]
    assert got["usd"] == 4.5
