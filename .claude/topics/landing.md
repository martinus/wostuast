# Landing a change: `main` and its ruleset

`CLAUDE.md` is the map; its header says how to add a rule. Read this
before you touch the jobs in `.github/workflows/tests.yml`, the ruleset,
or a merge that GitHub refuses.

**`main` is protected, and a push to it is refused.** A change lands through a
pull request, with every job in `.github/workflows/tests.yml` green. A
force-push to `main`, and a deletion of it, are refused too. The rule is a
GitHub ruleset, so it lives outside this repository and no test here can hold
it: `gh api repos/{owner}/{repo}/rulesets` is what answers what it says. Three
things about it are worth knowing before they surprise you.

- **It has no bypass actors, on purpose.** An agent pushes with the owner's
  token, so a bypass for the owner is a bypass for every agent, and the rule
  would be decorative. To land something without a pull request, set the
  ruleset's enforcement to `disabled`, push, and set it back — a deliberate
  act, which is the point.
- **It asks for no approving review, and that is not an oversight.** GitHub
  will not let you approve your own pull request, and this repository has one
  reviewer. One required approval would lock the owner out of their own
  repository, and it would read as a broken merge button rather than as a
  rule. Nought still forces the pull request, and still forces green.
- **The required checks are named one by one, so the matrix and the ruleset
  can drift.** Add a Python version to `tests.yml` and its job is not required
  until you add it to the ruleset. Take one out and the ruleset waits for a
  check that will never report, and then nothing can be merged at all. Change
  the matrix, change the ruleset. **The browser shards are the exception, and
  that is the whole reason the `browser` job exists**: it runs nothing, needs
  the shards, and reports under the name the rule asks for, so the shards can
  be renumbered without anyone touching the ruleset. It carries `if: always()`
  because a job its `needs` skipped reports neither pass nor fail, and a
  required check can read that as a pass — which would make a red shard
  mergeable. The `pytest` matrix has no such cover.
