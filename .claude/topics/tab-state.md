# Tab state: what a session remembers, and who writes the places

- **A session remembers the choices, never the caches.** `savePlace` and
  `usePlace` keep in `state.visits`, by session id: the tab, the open file
  and its place, the directories opened by hand, the expanded tool blocks
  and long messages (one set, `state.turns.open`), and diff files. The
  listing, the text and the diff are fetched again: they have moved by the
  time the reader is back, and they are big (52,799 names is 1.7 MB a
  session). **The names are the exception, kept once per worktree**
  (`state.listings`, see the ssh tunnel bullet): they are the worktree's,
  and asked for again with their tag, so only what moved comes back. **Not
  `places`**: `state.files.places` is the list of things to go to, and one
  word for two ideas gets one shadowed.
- **`usePlace` writes onto a state just blanked, so every field it sets is
  one the `blank…()` has.** A session never visited keeps the blank. **What
  is kept is one table, `PLACE_FIELDS`**: bag, field, how it is copied.
  Named by hand in `savePlace` and `usePlace`, a field saved and not put
  back was silent, and read as the feature half-working (#300).
  `test_what_a_session_keeps_is_what_comes_back` walks the table and sets
  each field away from its blank, so a field not copied back cannot hide
  behind the blank. Not `KEPT`: that is the Markdown scrub's.
- **`state.files.down` has one writer: *this session's* scrollbar.** The
  `.filescroll` listener writes it; `savePlace` reads the field, never the
  DOM. `showTab` read the DOM, and since `choose` restores the place *then*
  changes the tab, it wrote the outgoing session's place over the one just
  restored. `drawFiles` puts the place back only once there is something
  under the bar: nought on the first, empty draw would be written back as
  the place. **The listener knows whose pane it is on**: `.filescroll`
  outlives a change of session (leaving the Files tab does not rebuild
  it), so a scroll event queued when `choose` runs lands after `usePlace`
  and writes the old session's number over the new one's. It captures
  `state.chosen` when attached and writes nothing once that moved. Only a
  loaded machine does this by itself, so
  `test_a_scroll_left_over_from_another_session_is_not_its_place`
  dispatches the event on purpose.
  - **A rebuild reads the scroller first, once.** A browser reports a
    scroll a frame late; a poll that rebuilt the pane in between put back
    the place before the scroll
    (`test_a_comment_in_a_long_file_survives_the_file_being_read_again`).
    `drawFiles` reads `.filescroll` before emptying the pane, only one drawn
    for this session (`dataset.drawn`) holding the same file: a pane still
    reading stands at nought. **It reads into `place`, never into `state`**
    (#573): a draw only reads state; the new scroller's listener writes the
    place once it is put back, so the scrollbar stays the one writer.
    `test_a_scroll_not_yet_reported_survives_the_file_being_read_again`
    (scroll and rebuild in one task),
    `test_another_sessions_scroller_is_not_read_as_this_ones_place`.
- **A tab's state lives under its own name**, `state.files`, `state.turns`,
  `state.diffs`, each with one `blank…()`: choosing a session is
  `state.files = blankFiles()`, not eleven assignments that could forget a
  twelfth. **A new tab gets this shape from the start**: the flat bag grew
  fifteen names for the Files tab alone, none saying whose. The Commands
  view (#367, #411) is `state.commands` and `blankCommands()`; it is no
  tab, so no session keeps a command and it has no row of `PLACE_FIELDS`
  (`test_what_a_session_keeps_is_what_comes_back` names every row).
- **The shared chrome stays flat**: `sessions`, `chosen`, `tab`, `find`,
  `pick`, `history`, `skew`, `open`, `stream`. It belongs to no tab.
- **The Diff tab's are in `state.diffs` too** (`blankDiff`, #300): what it
  shows (`of`), the folders and files opened or shut, the lines revealed,
  the answer's tag, the untracked file picked and its read. `choose` had
  reset eighteen flat fields one by one. The untracked file's answer is
  held once, as `found`: its text and binary flag were copies, reset in
  three places. `state.diff` (the daemon's answer) and `state.sides` (a
  setting) stay where they were.
- **The Diff tab's body is drawn again when one of its inputs moved**
  (`diffKey`): the session, the answer's tag, what is shown, the loose file
  and its read, the find box, the columns, what was opened, revealed or
  fetched whole. A counter, `diffAt`, bumped by hand in seven places, stood
  for that, and a change that forgot the bump never drew (#301). `redrawCode` still clears
  the key for a redraw meant to go under an open comment box (its save,
  its cancel). A test that wants "a new answer" moves the tag.
