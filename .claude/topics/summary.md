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
  tokens do not: the hover of the turns' title says the shares grow with
  them.
- **The tab is one column, not a split tab** (`box.className`,
  `.summarybox`): under `content split` the summary stood in the list's
  narrow column. It takes the box as `split` does (`dataset.tab`, the find
  box sent home), or the next tab kept a frame that was gone.
- **The tab is the fourth, key `4`** (`TABS.summary`, `drawSummary`), as
  the reader chose; the Commands view moved to `5`. A costly turn is a link
  to it in the transcript (`goTo`, `goToTs`, as a saved turn's). It has
  no list column, so no find box: `finds` is empty.
  `test_the_summary_tab_says_where_the_tokens_went`.
- **A link to a turn or a call lands in the transcript beside the tab**
  (#728, `showInChat`), as the reader asked: the Transcript tab took them
  away from the numbers. The column opens if it was folded, and is filled
  again, so it lands: a
  column that shows the same blocks is left as it is (`paintChat`), and
  only a fill asks for a landing. A subagent's line still opens its own
  transcript on the Transcript tab: that is no place in this one.
  `test_the_tool_results_kept_in_context_link_to_their_calls`.
- **The tab is "Statistics": this session or all sessions this month, one
  at a time behind a switch** (#653, #723, `drawSummary`, `statsView`,
  `putStatsSwitch`, `putSession`, `putSpend`), as the reader chose from
  pictures: side by side, the reader could not see how the lists related
  or which mattered, and the month repeated the session's lists in another
  colour. This browser keeps the choice (`wostuast-stats`). Its key in the
  code stays `summary`.
  - **Both views have the same numbered parts, each with the question it
    answers** (`putSumPart`, `.sumgroup`, `.sumask`): what it cost, where
    the money went, where the time went. The month has no third: the
    status lines keep no time.
  - **A list's note is one short line, or none; the whole explanation is
    on a hover of its title** (`putSumNote`, `.sumtitle.explained`): notes
    of two and three lines over every list were most of what the tab said.
    A number the reader acts on, such as what all results kept in context
    cost, stays in the short line.
    `test_the_tool_results_kept_in_context_link_to_their_calls`.
  - **No list says again what another says**: "calls by tool" went, as
    time by tool counts each tool's calls; the subagents by kind went, as
    the line each subagent has says its kind. The daemon sends neither
    (`summary_json`), and `Costs` counts no calls by tool.
  - **At most two columns of cards, 1100 px wide** (#683, `.summary`,
    `.sumcards`, `putSumCard`): a line is read across without a long jump.
    The grid is `auto-fill`, so a narrow pane gets one column with no
    media query.
    `test_the_statistics_tab_uses_a_wide_screen`.
- **The session's time and tokens are charts, not tiles** (#688,
  `putSumClock`, `putSumKinds`, `TOKEN_KINDS`, `weighted`): the reader
  found three times and four token counts as plain numbers hard to read.
  The time is a line each with a bar on one scale, as time by tool reads:
  since it started, busy, the model worked. **Not one bar nested in
  another**: the reader could not read it at a first glance. The model's
  time counts subagents, so it can pass busy. The tokens are one bar in parts, each as wide as
  its share of what they cost, by `TOKEN_WEIGHTS` sent as `weighted`, so
  the weights stay in one place. **Shares, never dollars**: the status
  line's dollars hold the subagents, the transcript's tokens do not. The
  four colours are `--kind-1` to `--kind-4`, a set the dataviz palette
  validator passed for colour blindness on both surfaces; each block says
  its share where it has room, and a key names the kinds.
  `test_the_session_s_time_and_tokens_are_charts`.
- **Each subagent the daemon keeps is a line of its own** (#687,
  `putSumRuns`, `.sumcard.wide`, "subagents"): a line a kind said only
  how many ran, and it went (#723). The newest first: how long it ran ("running" while it
  runs), a bar on one scale, its kind, its task, its calls and tokens;
  its last words on the hover, and a click opens its own transcript
  (`openAgent`), as its line under the row does. They come from the row's
  `subagents`, the last `SUBAGENTS_HELD`, and a note says how many of
  `agents_ran` that is. The card spans the grid's row: in half a card a
  task was cut to its first words. **The tab's poll redraws it**: a row's
  push draws no tab, so a redraw key for the row's subagents did nothing.
  `test_each_subagent_is_a_line_that_opens_its_transcript`,
  `test_the_subagents_list_says_when_it_keeps_fewer_than_ran`.
- **A tool's result costs a part of every later reply that reads it,
  until the context goes** (#699, `Carry`, `ResultCost`, `carried_json`,
  `putSumCarried`), as the reader asked: to find the calls whose output
  stays in context, and make them smaller. A transcript says no result's
  tokens, but each reply says its whole context (`CONTEXT_KEYS`). So a
  result is its share, by characters, of how much the next reply's context
  grew past the reply before and that reply's own output: without the
  output, a `Write`'s content was its small result's. Each later reply
  costs it its part of that reply's context, at the weights the reply read
  it at, so a cache miss counts at 1.25. `read_sum` adds them up a reply
  at a time: a walk over each result still in context, at every reply, is
  replies times results. **The context goes at a compaction, and when a reply's
  context falls below `CONTEXT_FELL` of the one before**: a `/clear` can go
  on in the same file, with no record to say so. Measured on 16
  transcripts: tool results were 29 to 40 % of what a session spent, and
  the costliest were rule files read at the start. **A list goes to a call
  by its id** (`goToCall`), never by its moment: the calls of one reply
  share theirs, and `goToTs` found the first. Its card spans the row, as a
  command is a line.
  `test_a_tool_result_costs_each_later_reply_until_the_context_goes`,
  `test_the_tool_results_kept_in_context_link_to_their_calls`.
  - **The month has the list too, and what the results cost by tool**
    (`month_carried_json`, `putMonthCarried`), as the reader asked. A
    result is this month's when its call is, and its dollars are its share
    of its session's whole total, as a turn's are (`turn_share`). **The
    calls are the `Carry`'s own, from the replies** (`Carry.called`):
    `CostReader` makes no block of a call. **A line of results it does not
    parse gives its ids and its length from the bytes** (`arrived_unread`,
    `TOOL_USE_IDS`, `RAW_PER_CHAR`): parsing them was what made the whole
    reader 10 to 30 times slower. A line holds its result twice, escaped,
    so its bytes are a constant times its characters; the split among the
    results of one reply is near the whole reader's.
    **A call's target is read only for the lines shown** (`target`): every
    call's target hides its secrets (`clip_hidden`), and read for every
    call it made a month's reader half as slow again. A call that writes a
    file reads its path at once, so the text it writes is not kept.
    `test_the_cost_reader_reads_the_tool_results_the_whole_reader_does`,
    `test_the_month_s_tool_results_kept_in_context_and_by_tool` (both
    files), `test_the_daemon_reads_the_month_s_turns_of_the_sessions_it_keeps`.
- **Every list of the tab has a bar a line, drawn one way, `putSumBar`**
  (#685): time by tool, the costliest turns and the slowest calls, each
  as long as its share of the most in its list. A costly turn's bar is its weight, sent as `weight` in `costly`: its
  dollars are `None` when the status line says no cost. The bar takes
  the column after the number, so a call's tool goes before its target,
  and **a turn's tokens go on the line's hover**, as the reader chose:
  after the prompt, a long one cut them off.
  `test_the_costliest_turns_and_the_slowest_calls_have_bars`.
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
- **The month has the session's bar of what its tokens cost** (#722,
  `month_tokens_json`, `tokens_json`, `putSumKinds`), as the reader asked:
  under the month's two charts. Its tokens are those of the turns that
  began this month, of the sessions the daemon keeps, as for the costliest
  turns. **One function counts and weighs tokens by kind** (`tokens_json`),
  for the session and the month: the weights stay in one place.
  `test_the_month_s_tokens_are_its_turns_by_kind_and_by_what_they_cost`,
  `test_the_month_names_its_costliest_sessions_and_turns`.
- **The month names its costliest sessions and turns** (#698,
  `month_costly_json`, `putMonthSessions`, `putMonthTurns`), as the reader
  asked. A session's amount is how much its total grew this month
  (`month_spent`), from the status files. A turn's is its share of its
  session's whole total (`turn_share`, the one reader of a share, which the
  session's own list uses too), of the turns that began this month.
  **Only the sessions the daemon keeps give turns**: their transcripts are
  found through them, and a month quiet is when one goes
  (`SESSION_MAX_AGE`). A session the page no longer has is named, not
  linked. A turn links by its moment (`goToTs`), as its `seq` is not the
  whole reader's.
  - **The month's transcripts are read for their costs alone**
    (`CostReader`, `may_cost`): a whole reader keeps every block, tool
    results whole, and a month of them is too much to hold. It parses no
    tool's result without text, and makes blocks only of a `user` record,
    with the same `add` and `Costs.take`, so the turns are the same. On 30
    real transcripts the turns were the same and the read 10 to 30 times
    faster: 65 MB in 0.3 s. The readers are kept by path (`cost_readers`),
    read on from where they stopped, under `spend_lock`.
  - **Every list's bars are one colour, the session's and the month's**
    (#723): one view shows at a time, so no second colour has to say
    which a list is of. The month's own blue (#698) went with the two
    sections side by side.
  - **A hover or the focus on a line marks its days on both charts**
    (`markSpend`, a session's `days`, a turn's `day`), as the reader asked:
    a band behind each day it spent, its running total with its amount at
    the end, and its part of each column. Drawn into the charts, never into
    `state`. A redraw under a pointer that stays loses nothing: Chromium
    sends a new `mouseenter`.
  `test_the_cost_reader_reads_the_turns_the_whole_reader_does`,
  `test_the_cost_reader_reads_on_and_starts_again_with_the_file`,
  `test_the_month_s_costliest_sessions_and_turns`,
  `test_the_daemon_reads_the_month_s_turns_of_the_sessions_it_keeps`,
  `test_the_month_names_its_costliest_sessions_and_turns`.
- **The month's charts show the weekdays, and a tile counts the workdays
  left** (#684, `spendWeekday`, `workdaysLeft`, `.spendweekend`), as the
  reader asked, to see how many days of work the month still has: a
  letter under each day, a band behind each Saturday and Sunday, the
  dates under today, the 1st and each Monday, never two within three
  days. The workdays are Monday to Friday after today. **"At this pace"
  stays the average of all days**: the reader chose it over a pace by
  weekday.
  `test_the_month_s_charts_show_the_weekdays_and_the_workdays_left`.
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
