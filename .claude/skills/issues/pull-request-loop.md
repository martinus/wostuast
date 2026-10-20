# The pull request loop

The calls that take a change from a pushed branch to a merged pull request
and the branch back on `main`, in order. Read it before you open, update
or merge a pull request, in a pass of `/issues` or alone.

The same calls every time; each went wrong at least once, and a wrong one
costs a round trip. **Owner `martinus` and repo `wostuast` go in separate
fields**: `martinus/wostuast` as the repo asked for
`martinus/martinus/wostuast`.

0. **Load the tools in one call**: `ToolSearch` with `select:mcp__github__create_pull_request,mcp__github__update_pull_request,mcp__github__pull_request_read,mcp__github__merge_pull_request,mcp__github__actions_list,mcp__github__get_job_logs,mcp__github__list_issues,mcp__github__issue_read,mcp__github__issue_write`
   and `max_results` 9. `subscribe_pr_activity`, `send_later` and
   `delete_trigger` are loaded already.
   - **When the github server did not connect, read through `gh api`, and
     wait for nothing**: the server can come back minutes later. The
     owner's issues are
     `gh api 'repos/martinus/wostuast/issues?state=open&per_page=100'
     --jq '.[] | select(.pull_request|not) | "\(.number) \(.user.login)"'`,
     then a body is `gh api repos/martinus/wostuast/issues/N --jq .body`
     for a number whose author was `martinus`; a check run is
     `gh api repos/martinus/wostuast/commits/<sha>/check-runs`. **Create,
     update and merge a pull request through the server once it is back**:
     the footer rule below is written for its calls.
1. **Push**: `git push -u origin <branch>`.
2. **Create**: `create_pull_request` with head `<branch>`, base `main`, and
   the body. The server adds a footer and a session link to it.
3. **Take the footer off**: `update_pull_request` with the very same body,
   then `pull_request_read` method `get`, and read the body back. `CLAUDE.md`
   says why, in its last bullet of **How to work here**. A comment on an
   issue gets the footer too: update it with its own text, and read it
   back. An issue's own body gets none (#271).
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
   sha is refused. Run the command and copy what it prints: a sha written
   from memory, even right in its first seven characters, gets the 409
   below. A 409 "Head branch was modified" means the head is not the one CI
   checked: read the checks again on the new head, never force.
7. **Close what it closed**: `list_issues`, and close each issue the pull
   request names with `issue_write` method `update`, `state: "closed"`,
   `state_reason: "completed"`. "Closes #N" in the body that created the
   pull request has left the issues open after the merge, so read the list,
   never assume. **Write `Closes #N` only for an issue the pull request
   finishes**: in a commit message GitHub does close it on the merge. A pull
   request that does part of an issue says "Does item 2 of #N", and the
   issue's body is rewritten to what is left, with why. **A quote counts
   too.** GitHub finds the keyword and a number anywhere in a body or a
   commit message: in quotes, in a table, in a story about a mistake. A
   quoted commit message in #318's body closed #301, meant to stay open.
   Name an issue you
   do not close by its number alone, never after "close", "fix" or
   "resolve" in any form.
8. **Let go**: `delete_trigger` the check-in, `unsubscribe_pr_activity`.
9. **Back onto main**: `git fetch origin main && git checkout -B <branch>
   origin/main`, then `git push -u origin <branch>`. The merge commit holds
   the branch's head, so this is a fast-forward and needs no force.
   - **A stack that lands in a row through the one branch skips this until
     its last pull request**: after each merge, `git checkout -B <branch>
     <next commit>` and push. The next commit is a child of the head just
     merged, so that is a fast-forward too, and its pull request shows only
     its own change. The session may push to one branch only, so the stack
     cannot go up side by side.
