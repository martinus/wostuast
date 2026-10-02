# Tab state

Each rule is a bug that already happened: the assertion in bold, why the
obvious alternative is wrong, then the symbols and the test that holds it.
`CLAUDE.md` is the map; its header says how to add a rule. What a session remembers, and who writes the places.

- **A session remembers the choices, never the caches.** `savePlace` and
  `usePlace`, into `state.visits` by session id: the tab, the open file and
  the place in it, the directories opened by hand, the expanded tool blocks
  and long messages (one set, `state.turns.open`), and diff files. Not the listing, the text or the diff — those are fetched
  again, because by the time the reader comes back they have moved, and they
  are also the big things: 52,799 names is 1.7 MB, per session. **The names
  are the exception, kept once per worktree** (`state.listings`, see the ssh
  tunnel bullet): they are the worktree's, not the session's, and are
  asked for again with their tag, so what comes back is only what moved. **Not
  `places`** — `state.files.places` is the list of things to go to, and one
  word for two ideas is how one of them gets shadowed.
- **`usePlace` writes onto a state that has just been blanked**, so every
  field it sets is one the `blank…()` already has. A session never visited
  keeps the blank. **What is kept is one table, `PLACE_FIELDS`**: bag,
  field, and how it is copied. `savePlace` and `usePlace` named every field
  by hand, twice, and only a test kept the two lists together; a field saved
  and not put back is silent, and reads as the feature half-working (#300).
  `test_what_a_session_keeps_is_what_comes_back` walks the table and checks
  that each field was set away from its blank, so a field the table forgot
  to copy back cannot hide behind the blank. Not `KEPT`, which is the
  Markdown scrub's.
- **`state.files.down` has one writer, and it is *this session's*
  scrollbar.** The `.filescroll` listener writes it as the reader moves, so
  `savePlace` reads a field and never asks the DOM. It used to ask, and so did
  `showTab` — and `choose` restores the place and *then* changes the tab, so
  `showTab`'s query found the outgoing session's pane and wrote its place over
  the one just restored. `drawFiles` puts the place back only once there is
  something under the bar: the first draw after a session is chosen has no
  text yet, and scrolling to nought there would be written straight back as
  the place. **And the listener knows whose pane it is on**: `.filescroll` is
  built for one session and outlives the moment another is chosen — leaving
  the Files tab does not rebuild it — so a scroll event still queued when
  `choose` runs arrives *after* `usePlace` and writes the old session's number
  over the new one's. It captures `state.chosen` where it is attached and
  writes nothing once that has moved. This only ever happens by itself on a
  loaded machine, so
  `test_a_scroll_left_over_from_another_session_is_not_its_place` dispatches
  the event on purpose rather than waiting for one.
  - **A rebuild reads the scroller first, once.** A browser reports a scroll
    a frame late, and a poll that brought the file again rebuilt the pane in
    between, so the place put back was the one before the scroll and the
    reader was sent back there. CI caught it as
    `test_a_comment_in_a_long_file_survives_the_file_being_read_again`
    timing out. `drawFiles` reads `.filescroll` before it empties the pane,
    and only one drawn for this session (`dataset.drawn`) and holding the
    same file: a pane still reading stands at nought, the scar above.
    `test_a_scroll_not_yet_reported_survives_the_file_being_read_again`
    puts the scroll and the rebuild in one task, where no event can come
    between; `test_another_sessions_scroller_is_not_read_as_this_ones_place`
    holds the session check.
- **A tab's state lives under its own name**, `state.files`, `state.turns`
  and `state.diffs`, each with one `blank…()` that builds an empty one.
  Choosing a session is then `state.files = blankFiles()` rather than eleven
  assignments that could forget the twelfth. **A new tab gets the same shape from the start**: the
  flat bag this came out of grew fifteen names in one scope for the Files tab
  alone, and nothing said which tab owned any of them.
- The shared chrome — `sessions`, `chosen`, `tab`, `find`, `pick`, `history`,
  `skew`, `open`, `stream` — stays flat. It belongs to no tab.
- **The Diff tab's are in `state.diffs` too** (`blankDiff`, #300): what it
  shows (`of`), the folders and files opened or shut, the lines revealed,
  the tag of the answer held, and the untracked file picked with its read.
  `choose` reset eighteen flat fields one by one. The untracked file's
  answer is held once, as `found`: its text and whether it is binary were
  copies of it, reset beside it in three places. `state.diff`, the
  daemon's answer, and `state.sides`, a setting, stay where they were.
- **The Diff tab's body is drawn again when one of its inputs moved**
  (`diffKey`): the session, the answer's tag, what is shown, the loose
  file and its read, the find box, the columns, and what was opened,
  revealed or fetched whole. A counter, `diffAt`, bumped by hand at seven
  places, stood for that, and a change that forgot the bump never drew
  (#301). `redrawCode` still clears the key for a redraw that is meant to
  go under an open comment box -- its save, its cancel. A test that wants
  "a new answer" moves the tag.
