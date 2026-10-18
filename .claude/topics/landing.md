# Landing a change: `main` and its ruleset

Read before you touch the jobs in `.github/workflows/tests.yml`, the
ruleset, or a merge GitHub refuses.

**`main` is protected: a push, a force-push and a deletion are refused.** A
change lands through a pull request, with every job in
`.github/workflows/tests.yml` green. The ruleset lives outside this
repository, so no test here holds it; `gh api repos/{owner}/{repo}/rulesets`
shows it.

- **It has no bypass actors, on purpose.** An agent pushes with the owner's
  token, so a bypass for the owner is one for every agent. To land without
  a pull request, set the ruleset's enforcement to `disabled`, push, and set
  it back: a deliberate act.
- **It asks for no approving review, on purpose.** Nobody can approve their
  own pull request, and there is one reviewer: a required approval would
  lock the owner out. Nought still forces the pull request and green.
- **The required checks are named one by one: change the matrix, change
  the ruleset.** A Python version added to `tests.yml` is not required
  until the ruleset names it; one taken out leaves the ruleset waiting for
  a check that never reports, and nothing merges.
  - **The `browser` job exists so the browser shards can change without
    the ruleset.** It runs nothing, needs the shards, and reports under the
    name the rule asks for. It carries `if: always()`: a job its `needs`
    skipped reports neither pass nor fail, a required check can read that
    as a pass, and a red shard would be mergeable. The `pytest` matrix has
    no such cover.
  - **`browser` also runs the check that needs every browser test** (#579):
    each shard records what it ran of the page script (`WOSTUAST_COVERAGE`)
    and uploads it; `browser` downloads all four and runs
    `tests/page_coverage.py --check`. **Each shard's files go into a folder
    of their own**: a file is named after its process, two runners can give
    two processes one number, and a shared folder would keep one of them.
