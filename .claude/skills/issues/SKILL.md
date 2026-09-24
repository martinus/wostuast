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
the moment CI is green**, and only then. Nothing else is relaxed.

**This file is the order of the work. `CLAUDE.md` is the rules.** Where it
answers a question, it answers it here too, and it is not restated below —
one rule in two files is two rules that drift, which is a scar this
repository already carries about a list kept in two languages.

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

**Ask one level up when the request fights a goal or a non-goal** (`CLAUDE.md`,
**Goals and non-goals**). "Where should `links.json` live" hid the question
that mattered — whether a config file may exist at all — and goal 4 had said
no. If a goal has to bend, that is the question, and the goal is rewritten in
the same PR.

Stop and ask for: a new file outside `wostuast` and `tests/`, a dependency, a
new tmux verb (there are four: jump, send, interrupt, answer), anything that changes what the token or the
scrub protects, and any choice where two readings lead to different work.

Decide everything else yourself and say what you decided.

### 4. Build it

`CLAUDE.md` **Where to look** routes from what you are about to touch to the
rules for it. Read that row before editing, not after the tests go red.

Every test proved by perturbation — `CLAUDE.md` **How to work here** says how
and why. The part that catches people: read the count pytest prints, not the
colour. A test run under a `-k` that never selected it is a test you have not
run. `tests/perturb.py` runs each break against only the tests it names and
prints one line a break; its last line is the count to read.

### 5. Write the scar down in the same commit

| Where | What |
| --- | --- |
| `CLAUDE.md` | a rule the next agent needs, in the shape its header sets; a decision with no scar behind it goes in **Decisions without a scar behind them** |
| `tests/fixtures/README.md` | a payload shape, read off a real payload |
| `README.md` | anything a reader of the program sees |

The rule and the code that keeps it land together, or the rule is not true
yet. **Grep `CLAUDE.md` for the symbol before adding a bullet**: the same
kind of bug again goes into the bullet that already holds it, as its header
says. Add the symbol to `CLAUDE.md`'s **Where to look** table if the rule is
about code an agent would go looking for.

### 6. Review it when review is worth it

Judgement, not ceremony. A two-line fix needs neither.

- **`/code-review`** before opening a PR that touches the token, the tmux
  verbs, the scrub, a file read, or the hook — anything on the safety list in
  `CLAUDE.md` — or one whose diff runs past a few hundred lines.
- **`/simplify`** after a pass that added a lot of code, or that wrote a
  third spelling of something the codebase already had a word for. It has
  twice found real defects in code that was already merged.

Fix what they find before the PR goes up. Say which you ran.

### 7. The changed files under load, then push, then watch CI

`CLAUDE.md`, **How to work here**, "Before the push", is the list: the test
files you changed, three times at `-n 12`; every test with no browser; the
whole suite only when a shared part changed. Run them in the background and
write the rule and the pull request's text meanwhile. Green locally is
**not** the gate; CI is. It has caught two races no local run could: a
browser test that only fails on a loaded runner, and a failure message
wiped by a push a quiet machine never sends.

A red CI on a PR you opened is work now, not news. Re-diagnose and push again
until it is green. While CI runs, read the next issue and reproduce it —
reading only, the branch stays as CI saw it.

### 8. Merge, reset, and read the list again

Green means merge. Then reset the working branch onto `main`, and **read
every open issue again** — the reader files them while you work, and so do
you. The next pass starts from the list as it is now, not the list you
sorted an hour ago.

Stop watching the merged PR and cancel any check-in you armed for it.

## The pull request loop

The same calls every time. Each of these went wrong at least once, and a
wrong one costs a round trip, not a thought. Owner `martinus` and repo
`wostuast` go in separate fields — `martinus/wostuast` as the repo asked
for `martinus/martinus/wostuast`.

1. **Push**: `git push -u origin <branch>`.
2. **Create**: `create_pull_request` with head `<branch>`, base `main`, and
   the body. The server adds a footer and a session link to it.
3. **Take the footer off**: `update_pull_request` with the very same body,
   then `pull_request_read` method `get`, and read the body back. `CLAUDE.md`
   says why, in its last bullet of **How to work here**.
4. **Watch**: `subscribe_pr_activity`, and a `send_later` about six minutes
   out, because a green run may send no event.
5. **Read CI**: `pull_request_read` method `get_check_runs`. Done means every
   run completed and none failed, `browser` among them. For a red one:
   `actions_list` method `list_workflow_jobs` with the run id as
   `resource_id`, then `get_job_logs` with `job_id`, `return_content: true`,
   `tail_lines`. Every `actions_*` method takes its id as `resource_id`,
   and refuses without it.
6. **Merge**: `merge_pull_request` with `merge_method: "merge"`,
   `commit_title: "Merge pull request #<n> from martinus/<branch>"`, and
   `expectedHeadSha` from `git rev-parse HEAD` — all 40 characters; a short
   sha is refused. A 409 "Head branch was modified" means the head is not
   the one CI checked: read the checks again on the new head, never force.
7. **Let go**: `delete_trigger` the check-in, `unsubscribe_pr_activity`.
8. **Back onto main**: `git fetch origin main && git checkout -B <branch>
   origin/main`, then `git push -u origin <branch>`. The merge commit holds
   the branch's head, so this is a fast-forward and needs no force.

## While looping

- **A bug reported in prose outranks the issue list.** "The transcript looks
  weird" goes to the top: somebody is looking at it right now. Reproduce it,
  fix it, fold it into the pass you are on.
- **Something you find on the way**: if it is small, or it belongs to the
  code you are already changing, do it now — a fix one line from the one you
  are making is not widening the PR. Otherwise file an issue and leave it.
  Trivia is not an issue.
- **Never guess a payload, a browser, or a shape** — record a real event,
  drive a real Chromium, measure the box. `CLAUDE.md` **Do not guess payload
  fields** says where the recorded ones live.
- **Say what you left out, and why.** A pass that skipped something without
  saying so reads as a pass that finished.

## When it is over

Nothing open, `main` green. Say which issues closed in which PR, what you
filed, what you decided not to do, and anything still waiting on the reader.
