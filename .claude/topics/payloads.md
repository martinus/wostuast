# Do not guess payload fields

Hook and status line field names are in `tests/fixtures/README.md`. Need one
that is not there? Record a real payload and add it to `tests/fixtures/`. Do not
invent a name.

**The status line carries money, and this file used to say it did not.** The
payload has `cost.total_cost_usd`, `cost.total_duration_ms`,
`cost.total_api_duration_ms`, the lines added and removed, and
`rate_limits.five_hour` / `seven_day` / `spend_limit` with a used percentage
and a reset time. The design brief this repository used to carry asserted the opposite for a
while, and
an issue was closed down to one line on it. The assertion came from reading
`tests/fixtures/status.json`, which at the time had no `cost` in it — **one
fixture is one sample, and absence in it is not absence in the payload.** A
reader whose own status line showed the spend is what corrected it. When the
question is "does this payload carry X", the fixture can only say yes.

**A report that carries a payload becomes a fixture before the fix.**
Answering a question came back three times and the paste tags twice, each
first fixed against a shape guessed from the reader's words. Copy the record
out of the report, put invented text in place of theirs, keep every field
name and every level of nesting, save it under `tests/fixtures/`, and write
the failing test against it first. A report with no payload: ask for one
before building — the reader has sent them when asked.

**Recording one does not mean committing your conversation.** Both fixtures
carry real field names in real shapes with invented text, because this
repository is public. Read a real payload, learn the shape, write the fixture.

**And read more than one machine.** "A compaction writes a `summary` record"
held for years and was false: 31 transcripts across three machines and two
builds hold not one. A current build writes a `system` record with
`subtype: "compact_boundary"`, then a `user` record with `isCompactSummary`
carrying the whole summary — which went into the transcript as a prompt,
because it is a `user` record. A claim about a payload is worth what the
sample behind it is worth.

**A measurement that needs a live Claude Code session, or the owner's
`~/.claude`, is the owner's to take.** A cloud session has no login for a
nested Claude Code, and listing `~/.claude` or the environment there is
refused as credential exploration -- and the refusal covers every other
way to the same answer. Write the probe as a short script into the
issue, say what its output answers, and leave the issue open for the
result: #266 holds the shape. Plugin skills (#268) are not read for the
same reason.
