# Before you write anything new

The reuse index: the helpers, test helpers and CSS classes that exist, and
the CSS rules. Read it before you write a helper, a colour or a CSS
selector. Each entry here was written a second time once already.

## Page helpers

In the page script's "page helpers" section unless named:

| Want | Call |
| --- | --- |
| "has this changed since I drew it?" | `fresh(box, which, key)` — never a hand-rolled `dataset` compare |
| change a session on the page | `patchSession(id, fields)` — never a write in place: sessions are frozen and compared by object |
| make an element | `put(parent, tag, cls, text)` — a button it makes is `type="button"` |
| scattered-letter match | `fuzzy(text, query)` → `{score, at}` or null |
| the items whose path matches the find box | `hits(items, pathOf)` keeps the order; `pick(names)` sorts best first |
| walk a diff's lines with their numbers | `walkHunks(one, onHunk, onLine)` |
| the two-column tab frame | `split(box, tab, bodyClass)` → `[list, pane, note, foot]` |
| the rounds of a conversation | `rounds()`, `glimpse(text)` |
| a review comment's identity | `anchorOf(path, line)`, `lineAnchor`, `commentAt`; a drawn diff line, `diffLineAnchor` |
| "3 min ago" | `ago(when)` — `40s`, `4min`, `2h 15min`, `2d 6h` |
| one session's route | `apiUrl(id, what, query)` |
| the reader's ticket links in some text | `linkTickets(root)` — after any scrub |
| "15:48", and "21 Sep" when not today | `clock(when)`, `dayOf(when)` |
| text onto the clipboard | `copyToClipboard(text)` |
| a button that did its job says so | `flashOutcome(button, icon, title, done, saying, words)` |
| which sessions are listed | `shownSessions()` (filter only) vs `listedSessions()` (on screen) |
| a file as rows, or a slice of one | `linesOf(text)`, then `asLines(path, lines, from)` |
| a binary file the browser can show | `putMedia(parent, path, found)` |
| a folder or a page icon | `putIcon(parent, "dir" \| "dirOpen" \| "file")` — SVG, so not `put` |
| a choice of a few, one in force | `putChoice(parent, name, options, pick)`, `paintChoice(group, value)` |
| Markdown or text, over what is read | `putReadAs(parent, asText, pick, textTitle)` |
| one button lit while what it says is on | `paintToggle(button, on)` |
| the places a reader can go | `state.files.places` |
| bytes, or a date a person reads | `sizeOf(bytes)`, `whenOf(seconds)` |
| a count read at a glance, "2.4k"; a text's lines without splitting | `roughly(n)`, `lineCount(text)` |
| "1 file", "3 replies" | `counted(n, one, many)` — in Python too |
| this browser's storage, which may refuse | `stored(key)` → "" when nothing; `store(key, value)` |
| a diff's files in the order its tree reads | `treeOrder(found, pathOf)` |
| which words of a changed line changed | `wordDiff(was, now)`, then `markWords(cell, runs)` |
| cards in as many columns as fit | `putBoard(parent, cls)`, `putCard`, then `layoutCards(board)` |

Three page functions match, and are easy to confuse: `matches` (a
transcript block), `matching` (the file tree), `hits` (any list by path). A
fourth word for the idea is how one of them got shadowed, and fifty browser
tests failed.

## Python helpers

`path_label`, `clip`, `run` (a subprocess with a timeout), `private_dir`,
`safe_transcript`, `worktree_root`, `is_listed`, `inside`,
`CONTROL_CHARS`, `ESCAPE_CODES`, `GONE_STATES`, `STATE_WORDS`.

## Test helpers

- `tests/conftest.py` holds every fixture, the page ones too (`page_at`,
  `repo_page`, `big_page`, `in_pane`, `no_pane`, `pair_at`, `past_at`),
  and `event()`. `tests/browser.py` holds the shared Chromium and the page
  helpers below, and no fixtures; its `WAIT` is `WOSTUAST_WAIT`.
- `run_installed(["hook"], stdin)` runs the hook or status file this
  checkout makes, as Claude Code does (`as_claude`; `keys="pipe"` for a
  pipe).
- **Never hand-write a hook event**: `conftest.event(name, sid=...,
  **extra)` builds one as the log holds it, `conftest.bare_event` one with
  only the fields named, as Claude Code hands it to the hook.
  `test_no_test_writes_a_hook_event_by_hand` fails on one `EVENTS_BY_HAND`
  does not hold (#599).
- **Never hand-write a transcript record**: use `conftest.record(kind,
  text, ...)` and `conftest.records(...)`. One ended in a backslash and an
  `n`, and the reader waited for ever.
- **To call the program from a scratch script, `sys.path.insert(0,
  "tests")` and `from conftest import wostuast`**: a loader of your own
  fails at the first `@dataclass`.
- A runner that records keeps `conftest.said(args, rest)`, with the text
  `tmux_send` hands `load-buffer`; `conftest.typed(seen)` and
  `conftest.into_pane(seen)` read it.
- In `browser.py`: `opened` (`with opened(where) as page:`, `tab="diff"`),
  `own_context`, `load`, `show_tab`, `comment_on_first_line`, `two_rows`,
  `rgb`/`contrast`, `numbers`, `open_code`, `stays` (the one fixed wait:
  proving nothing comes), `frames`, `pixels` and `spy_on_note`.

## CSS

`.verb` (a button; `.verb.quiet` a size down, for one that only changes
what is on screen), `.choice` (`putChoice`), `.toggle` (`paintToggle`),
`.link`, `.acts`, `.find`/`.findslot`, `.empty`, `.nohits`, `.note`,
`.comment`.

- **Every colour is a variable; a `:root` block is the only place a colour
  is a number**: `test_every_colour_outside_the_palette_is_named`. It reads
  an issue number in a CSS comment as a colour too, so CSS comments say
  `issue 333`, never `(#333)`. Derive a tint with `color-mix`, never a
  copied rgb triple.
- **The fixed face is for machine text only** (#448): code, a diff, a file,
  a command, the send and find boxes, a sha, a key. A time, a count, a
  name, a button, a tab's title, a note is `--sans`, with `tabular-nums`
  where digits must not dance; every list on the left is `--narrow`.
  `test_the_fixed_face_is_for_machine_text_only`.
- **A control that shows on hover is `display: none` until then, or out of
  the flow -- never `opacity: 0` in it**: it kept its room, cut long names
  short and moved "claude" out of line (#373, #377).
- **Grep for a selector before adding a CSS rule.** A class in use takes
  the new rule's look too: `.plus` was already the green "+3" beside a
  changed file, and every count became an invisible box; `.tab` was the
  tab row's button, and its padding doubled every first tab in code.
