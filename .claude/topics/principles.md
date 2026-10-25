# The principles, and the tests that hold them

`CLAUDE.md`, **Principles**, names the five; this file says what each
means in the code and which tests hold it. Read it before you decide where
new code goes: a route, a view, a field the page reads, a second reader of
a fact.

A goal says what the program is for; a principle says where its code goes.
They came from a review of the whole file (#535): its bugs were each one
fact with two homes. A change that cannot keep one says so in its pull
request, and names the principle.

1. **Data flows one way**: events, then the fold, then rows, then the wire,
   then the page. The fold does no I/O: file, git and `/proc` reads happen
   at the edges, in the named steps of `Store.refresh` (`follow`, `settle`,
   `reload_git`, `render`), and a write the fold needs waits until it is
   done (`save_names`). A change of state is `become`.
   `test_the_fold_does_no_io`,
   `test_the_guard_folds_every_handler_and_both_links`.
2. **Each shape the page receives is defined in one place**: the wire
   section (`row`, `blocks_json`, `session_json`, `wire_fields`, the
   `EVENTS`). Its head comment names the five dataclasses that go out whole;
   anything else is written key by key.
   `test_a_block_sends_only_the_fields_it_names`,
   `test_the_page_reads_only_session_fields_the_row_sends`,
   `test_the_page_listens_for_every_event_the_stream_sends`,
   `test_the_row_and_ls_json_say_the_same_of_a_session`,
   `test_only_the_wire_section_turns_a_dataclass_into_json`.
3. **A draw only reads state.** Only code that loads data or handles a click
   changes `state`; what a change to the sessions does besides drawing is
   `onSessions`. `DRAW_GUARD` in `tests/browser.py`, an init script of every
   context, wraps `paint` and every `draw…` but `draw`, and fails on a
   fetch, alert, storage write or change to `state` (deep, and from a timer
   it set) not in `DRAW_EFFECTS_ALREADY` (#573, #577). Every browser test
   that opens a page with `opened` checks it. Every field of `state` is
   declared in its literal: `test_every_field_of_the_pages_state_is_declared`.
   **`draw()` is `paint`, then `land`** (#573): a mark of where to go -- a
   link to a block, a file asked for, the "new" line -- is used up once
   landed on, by each tab's own land in `TABS` (`landTranscript`,
   `landFiles`, `landDiff`). A build leaves what its land needs on the pane
   (`toLand`); the Review tab lands once a build, not on every push.
4. **Every extension point is a table**: hook handlers (`_HANDLERS`),
   session verbs (`GET_VERBS`, `POST_VERBS`), tabs (`TABS`), views
   (`VIEWS`), routes (`ROUTES`). A test walks the table, so a new entry is
   tested without anyone writing its test:
   `test_every_view_opens_draws_and_gives_the_session_back`,
   `test_every_route_refuses_what_it_must`.
5. **One reader for each fact.** Where two parts read the same fact, they
   call one function: `prompt_said` for a prompt, `git_status` for
   `git status`, `apply_git_facts` for a reading of git, `getJson` for an
   answer of the daemon. `test_search_reads_a_prompt_as_the_fold_does`,
   `test_only_get_json_calls_fetch`,
   `test_the_row_counts_the_changed_files_the_files_tab_marks`,
   `test_only_one_function_runs_git_status`.

**How a test holds a principle, strongest first**: a test that walks a
table; a differential test that gives two readers one hard case (write it
first and see it fail); a guard at run time, which checks only the paths
the tests run, so it comes with a test that each path is run; a static
check of the source's form, which moving code satisfies. **The rules of
`CLAUDE.md`'s Shape and Style that the form shows are held in
`tests/test_shape.py`**: the standard library only, the `__main__` guard
last, the six tmux commands, a timeout on every process, type hints, no
signal, no module-level name changed, and no script without its hash
(`PAGE_ADDRESSES`).

**The ratchet** (`CLAUDE.md`, **Principles**): a list of known breaks that
may only get shorter, like `LONGER_ALREADY`, `EVENTS_BY_HAND` and
`DRAW_EFFECTS_ALREADY`. It stops the code sliding back and cleans nothing.
So **a guard lands in the pull request of the refactor that empties most of
its list**, never alone before it; **each entry says why it is there**, in
a comment; and **a pull request that adds an entry says why in its
description**: adding one is the cheapest way to turn a red test green.
