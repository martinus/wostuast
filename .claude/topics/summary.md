# The Summary tab

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
