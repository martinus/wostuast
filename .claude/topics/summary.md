# The Statistics tab

Where a session's tokens and time went (#622), as the reader asked, "so I
can optimize my future sessions to produce less churn".

- **The dollars are the status line's, and a turn's share is its tokens'**
  (`summary_json`, `TOKEN_WEIGHTS`): the status line says only the
  session's total, Claude Code's own estimate. A turn is "about" that
  total by its tokens, weighted as Anthropic prices them: a cache read a
  tenth of an input token, a cache write 1.25, an output 5. No price is
  named, so a model priced otherwise moves the shares, never the total.
  `test_the_summary_shares_the_spend_out_by_weighted_tokens`.
- **A reply counts once, by its `message.id`** (`Costs.take`): measured on
  2.1.306, one reply is a record a content block, up to five, each with
  the reply's whole `usage`; counted per record, it cost three times.
  A turn runs from the reader's prompt (`Block.kind == "prompt"`) to the
  next. The reader keeps the counts as it reads (`Transcript.costs`), and
  starts them again with the blocks when the file is rewritten.
  `test_a_reply_counts_once_and_a_turn_runs_from_prompt_to_prompt`,
  `test_a_transcript_rewritten_starts_its_counts_again`.
- **Busy is prompt to end, not the status line's time** (`note_busy`,
  `Session.busy`): that is the session's whole life, idle hours too. A
  turn the reader interrupts sends no `Stop`, so it ends at its last
  event of work (`turn_last`, `BUSY_WORK`), not at the next prompt: an
  idle notification or a `SessionEnd` hours later counted the hours. An
  event older than the running turn is skipped. **It is a sum, where every
  handler assigns**, so a turn counts only past `busy_upto`: the same
  events read twice counted every turn twice
  (`test_folding_the_same_events_twice_gives_the_same_answer`).
  `test_busy_is_prompt_to_end_and_an_interrupted_turn_ends_where_it_went_quiet`,
  `test_only_work_moves_a_turn_s_end`.
- **The summary is built under the reader's lock, never copied**
  (`Daemon.summary`): a deep copy of the counts, every message id with
  them, cost 64 ms a poll on a long session.
- **The dollars hold the subagents' too**, which the main transcript's
  tokens do not: the note under the turns says the shares grow with them.
- **The tab is one column, not a split tab** (`box.className`,
  `.summarybox`): under `content split` the summary stood in the list's
  narrow column. It takes the box as `split` does (`dataset.tab`, the find
  box sent home), or the next tab kept a frame that was gone.
- **The tab is the fourth, key `4`** (`TABS.summary`, `drawSummary`), as
  the reader chose; the Commands view moved to `5`. A costly turn is a link
  to it in the transcript (`goTo`, `goToTs`, as a saved turn's). It has
  no list column, so no find box: `finds` is empty.
  `test_the_summary_tab_says_where_the_tokens_went`.
- **The tab is "Statistics", in two sections: this session, then all
  sessions this month** (#653, `drawSummary`, `putSpend`), as the reader
  asked; more about all sessions is to come there. Its key in the code
  stays `summary`.
- **A day's spend is how much each session's total grew that day**
  (`Status.days`, `note_day`, `spend_by_day`, `spend_json`, `GET
  /api/spend`). Measured on 2.1.312 with `tests/claude_pane.py`: a session
  id has one `total_cost_usd`, and it only grows; `/clear` starts a new id
  at nought, `--resume` carries the old total on. So the status file keeps
  the session's total at its last line of each local day, and the daemon
  sums the growth over all files. **The status line is the one writer**: a
  session seen first long after its start (its file dropped, then
  resumed) counts its whole total on that day. A status file is kept
  `STATUS_KEPT`, 40 days, so the 1st is still read on the 31st.
  - **A file from before the days gives its last total on its day**
    (`days_known`): without it, every session running at the upgrade
    booked its whole total that day.
  - **A file there and unreadable is not written over** (`kept_status`):
    today's total alone would take the month's days with it.
  - **Each file is parsed again only when its stamp moved**
    (`Daemon.spend_totals`, under `spend_lock`): every open tab asks every
    ten seconds.
  `test_a_day_s_spend_is_how_much_each_total_grew`,
  `test_the_month_s_spend_reads_every_status_file`,
  `test_the_status_file_keeps_the_days_it_cannot_read`,
  `test_a_status_file_is_read_again_only_when_it_changed`.
- **The allowance is shown, never enforced** (`allowance`, a setting in
  the menu's Page group, `putAllowance`): a spend limit is a non-goal
  (topics/goals). Two charts, never one with two scales: the running
  total with its pace to the month's end and the allowance across, then a
  column a day; a day's amount on hover (`putSpendHit`). A settings push
  redraws the tab (`takeSettings`), as the allowance is the one setting a
  tab draws from. **Text the box cannot read is no "none"**
  (`validity.badInput`: "$200" reads as ""), and an amount the daemon
  refuses is put back, in the box by hand: `paintSettings` leaves a
  focused box alone. **The word "allowance" says where it is changed**, on
  a hover (`ALLOWANCE_WHERE`), as the reader asked: on the tile, the
  chart's label, and the note when none is set.
  `test_the_statistics_tab_draws_the_month_against_the_allowance`.
- **A session's time goes by tool, and its slowest calls are kept**
  (#663, `note_tool_time`, `Session.tool_time`, `SlowCall`, `putSumTime`):
  from each call's `duration_ms`, the run alone, never the wait for a Yes
  (`tests/fixtures/README.md`). A failed call took its time too. **A
  subagent's calls are its own**: they run beside the agent's, and one
  second counted twice. **A sum, as `busy` is**: `tools_upto` and
  `tools_at` keep the same events read again from counting twice. **A
  slow call is a second or more** (`SLOW_LEAST`): eight reads of 0.1 s
  said nothing. One links to its block by when it began (`goToNear`, with
  `goTo = 0`, as a search result: the landing does nothing while `goTo`
  is null). `callTime` keeps tenths under 10 s and a build's seconds:
  `lasted` wrote "0s" and "1min".
  `test_a_session_s_time_goes_by_tool_and_its_slowest_calls_are_kept`,
  `test_the_statistics_tab_says_where_the_time_went_by_tool`.
