---
name: issues
description: Work every open GitHub issue to done — grouped into PRs by subject, each merged when CI is green, re-reading the issue list after every merge. Use when the reader says "do the issues", "work the issues", or asks to keep going until nothing is left.
argument-hint: "[optional: an issue number or subject to start with]"
---

# Do the issues

Read every open issue, finish them all, stop when nothing is left.

**One subject is one PR.** The loop does not move on until that PR is merged
and the issue list has been read again.

Saying "do the issues" is the permission to merge: **merge a PR of your own
the moment CI is green**, and only then. Nothing else in this repository's
rules is relaxed — `CLAUDE.md` still wins on every question it answers, and
`PLAN.md` wins over `CLAUDE.md`.

## One pass

### 1. Read them all, then group

`list_issues`, every open one, before touching anything. Group by **what they
touch**, not by number: four issues about the sidebar are one PR, and two
issues about one function are one commit. A PR that closes four related
issues beats four PRs that conflict in the same 9,000-line file.

Order so that a change others build on goes first, and a change that moves a
lot of code goes before the fiddly ones that would be rewritten by it.

Say the grouping and the order before starting it. One line each.

### 2. Reproduce before you fix

Every bug this repository has had was **not** what the report said it was.

| Reported | Actually |
| --- | --- |
| "the ticket links do not work" | `\d` is not a JSON escape, so the file never parsed |
| "the open-folder icon is cut off" | nothing clipped it — the shape had no right side |
| "I could not send any text, in no sessions" | `body.lost` matched `.lost { display: none }` and took the whole page with it |

Measure it, print it, render it and look at it. A browser question is
answered by driving a browser; a payload question by reading a real payload;
a shape question by `getBBox`. **A fix for a cause you guessed is a second
bug on top of the first.**

### 3. Ask before you build, never after

Two or three options, each carrying its real cost, one marked recommended.
A design question answered after the code is written is a question you
answered yourself.

**Ask one level up when the request fights `PLAN.md`.** "Where should
`links.json` live" hid the question that mattered — whether a config file may
exist at all — and the plan had said no. If a goal has to bend, that is the
question, and the plan gets amended in the same PR.

Stop and ask for: a new file outside `wostuast` and `tests/`, a dependency, a
tmux verb beyond jump and send, anything that changes what the token or the
scrub protects, and any choice where two readings lead to different work.

Decide everything else yourself and say what you decided.

### 4. Build it, and prove every test by perturbation

Break the thing the test claims to guard and watch it go red. A test that
passes against its own perturbation is not a test. Two have slipped through
here, and a third slipped through recently because the `-k` filter it was run
under never selected it — read the count, not the colour.

### 5. Write the scar down in the same commit

| Where | What |
| --- | --- |
| `CLAUDE.md` | a rule the next agent needs |
| `PLAN.md` §12 | a decision and why it earned its exception |
| `tests/fixtures/README.md` | a payload shape, read off a real one |
| `README.md` | anything a reader of the program sees |

The rule and the code that keeps it land together, or the rule is not true
yet.

### 6. Review it when review is worth it

Judgement, not ceremony. A two-line fix needs neither.

- **`/code-review`** before opening a PR that touches the token, the tmux
  verbs, the scrub, a file read, or the hook — anything on the safety list in
  `CLAUDE.md` — or one whose diff runs past a few hundred lines.
- **`/simplify`** after a pass that added a lot of code, or that wrote a
  third spelling of something the codebase already had a word for. It has
  twice found real defects in code that was already merged.

Fix what they find before the PR goes up. Say which you ran.

### 7. Full suite, then push, then watch CI

`pytest -q -n auto` — about 110 s, so there is no excuse. Green locally is
**not** the gate; CI is. It has caught two races no local run could: a
browser test that only fails on a loaded runner, and a failure message wiped
by a push a quiet machine never sends.

A red CI on a PR you opened is work now, not news. Re-diagnose and push again
until it is green. Never skip, disable or quarantine a test to get there.

### 8. Merge, reset, and read the list again

Green means merge. Then reset the working branch onto `main`, and **read
every open issue again** — the reader files them while you work, and so do
you. The next pass starts from the list as it is now, not the list you
sorted an hour ago.

Stop watching the merged PR and cancel any check-in you armed for it.

## While looping

- **A bug reported in prose outranks the issue list.** "The transcript looks
  weird" goes to the top: somebody is looking at it right now. Reproduce it,
  fix it, fold it into the pass you are on.
- **Something you find on the way**: if it is small, or it belongs to the
  code you are already changing, do it now — a fix one line from the one you
  are making is not widening the PR. Otherwise file an issue and leave it.
  Trivia is not an issue.
- **Never guess a payload, a browser, or a shape.** Record a real event, read
  a real transcript, drive a real Chromium, measure the box.
- **Say what you left out, and why.** A pass that skipped something without
  saying so reads as a pass that finished.

## When it is over

Nothing open, `main` green. Say which issues closed in which PR, what you
filed, what you decided not to do, and anything still waiting on the reader.
