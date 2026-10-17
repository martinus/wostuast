# Landing a change: `main` and its ruleset

Read this before you touch the jobs in
`.github/workflows/tests.yml`, the ruleset, or a merge GitHub refuses.

**`main` is protected: a push, a force-push and a deletion are refused.** A
change lands through a pull request, with every job in
`.github/workflows/tests.yml` green. The rule is a GitHub ruleset outside
this repository, so no test here can hold it;
`gh api repos/{owner}/{repo}/rulesets` says what it says.

- **It has no bypass actors, on purpose.** An agent pushes with the owner's
  token, so a bypass for the owner is a bypass for every agent, and the rule
  would be decorative. To land something without a pull request, set the
  ruleset's enforcement to `disabled`, push, and set it back: a deliberate
  act, which is the point.
- **It asks for no approving review, on purpose.** GitHub will not let you
  approve your own pull request, and this repository has one reviewer: one
  required approval would lock the owner out, and read as a broken merge
  button rather than a rule. Nought still forces the pull request and green.
- **The required checks are named one by one, so change the matrix, change
  the ruleset.** A Python version added to `tests.yml` is not required until
  the ruleset names it; one taken out leaves the ruleset waiting for a check
  that never reports, and nothing can be merged.
  - **The browser shards are the exception: that is why the `browser` job
    exists.** It runs nothing, needs the shards, and reports under the name
    the rule asks for, so the shards can be renumbered without touching the
    ruleset. It carries `if: always()`: a job its `needs` skipped reports
    neither pass nor fail, a required check can read that as a pass, and a
    red shard would be mergeable. The `pytest` matrix has no such cover.
  - **`browser` also runs the one check that needs every browser test**
    (#579): each shard records what it ran of the page script
    (`WOSTUAST_COVERAGE`) and uploads it, and `browser` downloads all four
    and runs `tests/page_coverage.py --check`. **Each shard's files go into
    a folder of their own**: a file is named after its process, two runners
    can give two processes one number, and one shared folder would keep one
    of two such files.
