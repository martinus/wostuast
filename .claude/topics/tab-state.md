# Tab state

What a session remembers when the reader leaves it, and who writes the
places.

- **A session remembers the choices, never the caches.** `savePlace` and
  `usePlace` keep in `state.visits`, by session id: the tab, the open file
  and its place, directories opened by hand, expanded blocks
  (`state.turns.open`), diff files. Listings, texts and diffs are fetched
  again: they move meanwhile, and are big (52,799 names is 1.7 MB).
  **Except the names, kept once per worktree** (`state.listings`,
  topics/daemon-and-page, the ssh tunnel bullet) and asked for with their
  tag. **Not `places`**: that is `state.files.places`, and one word for two
  ideas gets one shadowed.
- **`usePlace` writes onto a state just blanked, so every field it sets is
  one the `blank…()` has.** **What is kept is one table, `PLACE_FIELDS`**
  (bag, field, how copied): named by hand, a field was saved and never put
  back (#300). `test_what_a_session_keeps_is_what_comes_back` sets each
  field away from its blank, so a field not copied back cannot hide. Not
  `KEPT`: that is the Markdown scrub's.
- **`state.files.down` has one writer: this session's `.filescroll`
  listener**; `savePlace` reads the field, never the DOM. `choose`
  restores the place, then changes the tab, so a `showTab` reading the DOM
  wrote the old session's place over it. `drawFiles` puts the place back
  only once something is under the bar, or an empty draw's nought is
  saved. **The listener captures `state.chosen` and writes nothing once it
  moved**: `.filescroll` outlives a change of session, so a queued scroll
  lands after `usePlace`.
  `test_a_scroll_left_over_from_another_session_is_not_its_place`
  dispatches it on purpose.
  - **A rebuild reads the scroller first, once**: a scroll is reported a
    frame late, and a rebuild in between lost it
    (`test_a_comment_in_a_long_file_survives_the_file_being_read_again`).
    `drawFiles` reads `.filescroll` before emptying the pane, only if
    drawn for this session (`dataset.drawn`) with the same file. **It reads
    into `place`, never `state`** (#573): a draw only reads state.
    `test_a_scroll_not_yet_reported_survives_the_file_being_read_again`,
    `test_another_sessions_scroller_is_not_read_as_this_ones_place`.
- **A tab's state lives under its own name** (`state.files`,
  `state.turns`, `state.diffs`), each with one `blank…()`, so choosing a
  session is `state.files = blankFiles()` and forgets no field. **A new tab
  gets this shape from the start**: the flat bag had fifteen Files names,
  none saying whose. The Commands view (#367, #411) is `state.commands`
  and `blankCommands()`; no tab, so no row of `PLACE_FIELDS`
  (`test_what_a_session_keeps_is_what_comes_back` names every row).
- **The shared chrome stays flat**: `sessions`, `chosen`, `tab`, `find`,
  `pick`, `history`, `skew`, `stream`.
- **The Diff tab's are in `state.diffs`** (`blankDiff`, #300): what it
  shows (`of`), folders and files opened or shut, lines revealed, the
  answer's tag, the untracked file and its read, held once as `found`.
  `state.diff` (the daemon's answer) and `state.sides` (a setting) stay
  flat.
- **The Diff tab's body is redrawn when one of its inputs moved**
  (`diffKey`): session, tag, what is shown, the loose file and its read,
  find box, columns, what was opened, revealed or fetched whole. A counter
  bumped by hand was forgotten, and the change never drew (#301).
  `redrawCode` clears the key for a redraw under an open comment box. A
  test that wants "a new answer" moves the tag.
