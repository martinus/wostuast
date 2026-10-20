# Writing a rule

How a rule in `CLAUDE.md` or `.claude/topics/` is written, and where it
goes. Read this before you add, change or remove one.

- **One bullet a rule, in this order**: (1) the assertion, in bold: what
  to do, or never to do; (2) why, in one or two sentences: the failure the
  obvious alternative caused, or the reader's decision and what it rules
  out; (3) the symbols to grep, the test that holds it, and the issue
  (`#N`). **Keep the why**: a rule without it is broken by the first agent
  that thinks it knows better.
- **Bold only the assertion.** When many words are bold, none stands out,
  and the rule an agent needs is read as one more line.
- **Leave out the story**: who found it, when, after how many runs, what
  was tried first. `git log --grep '#N'` keeps it. Keep a number only when
  it sets a limit or proves the why.
- **A new scar goes into the bullet it belongs to.** Grep for the symbol
  first (`grep -rn SYMBOL CLAUDE.md .claude/topics`): the same kind of bug
  again adds its test and a clause to that bullet. A new bullet is for a
  new kind of bug. Two bullets that say one rule drift, and an agent then
  follows either one.
- **State no number a person must maintain; give the command that answers
  it**: a stale fact is believed.
- **Write in plain language** (ISO 24495, and ASD-STE100 in a pragmatic
  form): short sentences, one idea each, active voice, and one word for one
  thing. A second word for an idea is how `matches` was shadowed
  (topics/reuse).
- **`CLAUDE.md` holds only what every session needs**: the map, the goals,
  the principles, the way of working, **Shape** and **Style**. Claude Code
  loads it at every launch, and a long one makes an agent miss the rule
  that counts. Anthropic's target is under 200 lines;
  `test_claude_md_stays_short` holds it. Everything else goes in a topics
  file that a section header or **Where to look** routes to.
- **A rule goes in the file of its subject**; a new subject is a new file,
  a row in `CLAUDE.md`'s **Where to look**, and a bracket on the headers of
  its code.
  `test_every_rules_file_is_routed_to_and_every_route_is_a_file`.
- **A skill's `SKILL.md` stays under 500 lines, and its description says
  what it does and when to use it, in the third person**: the description
  is all an agent sees before it loads the skill. A part only some runs
  need goes in a file beside `SKILL.md`, linked from it, one level deep.
  `test_claude_md_stays_short`.
