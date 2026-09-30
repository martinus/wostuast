"""git facts, read from a real repository in a temporary directory."""

from __future__ import annotations

import os
import subprocess

import pytest

from conftest import git_in as git


def test_a_clean_repository(ws, repo):
    facts = ws.git_facts(str(repo))
    assert facts.repo == "myrepo"
    assert facts.branch == "main"
    assert facts.dirty is False
    assert facts.touched_files == 0
    assert facts.ahead == 0 and facts.behind == 0


def test_a_dirty_repository_counts_its_files(ws, repo):
    (repo / "README.md").write_text("two\n")
    (repo / "b.txt").write_text("new\n")
    facts = ws.git_facts(str(repo))
    assert facts.dirty is True
    assert facts.touched_files == 2


def test_ahead_and_behind_come_from_the_upstream(ws, repo, tmp_path):
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(repo), str(clone)], check=True,
                   capture_output=True)
    git(clone, "config", "user.email", "t@example.com")
    git(clone, "config", "user.name", "T")
    (clone / "c.txt").write_text("c\n")
    git(clone, "add", "c.txt")
    git(clone, "commit", "-qm", "second")
    facts = ws.git_facts(str(clone))
    assert facts.ahead == 1
    assert facts.behind == 0


def test_a_worktree_keeps_the_name_of_its_repository(ws, repo, tmp_path):
    tree = tmp_path / "warmhare"
    git(repo, "worktree", "add", "-q", "-b", "feature/search", str(tree))
    facts = ws.git_facts(str(tree))
    assert facts.repo == "myrepo"
    assert facts.branch == "feature/search"
    assert ws.path_label(str(tree), facts.repo) == "myrepo/warmhare"


def test_the_remote_is_read_and_never_carries_a_password(ws, repo, tmp_path):
    """The row shows the remote on a hover, so it goes to the page -- and a
    remote URL can hold a user and a token. Both come out; the `git@host:`
    shape holds no secret and stays. A worktree reads its repository's."""
    git(repo, "remote", "add", "backup", "git@example.com:team/myrepo.git")
    assert ws.git_facts(str(repo)).remote == "git@example.com:team/myrepo.git"
    git(repo, "remote", "add", "origin",
        "https://me:ghp_secret@example.com/team/myrepo.git")
    tree = tmp_path / "warmhare"
    git(repo, "worktree", "add", "-q", "-b", "side", str(tree))
    for where in (repo, tree):
        facts = ws.git_facts(str(where))
        assert facts.remote == "https://example.com/team/myrepo.git"


def test_a_repository_with_no_remote_has_none(ws, repo, tmp_path):
    assert ws.git_facts(str(repo)).remote == ""
    assert ws.remote_url(str(tmp_path / "nowhere")) == ""
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "config").write_bytes(b"[remote \"origin\"\n\xff url")
    assert ws.remote_url(str(broken)) == ""


def test_a_directory_without_git_gives_empty_facts(ws, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    facts = ws.git_facts(str(plain))
    assert facts == ws.GitFacts()


def test_a_missing_directory_gives_empty_facts(ws):
    assert ws.git_facts("/does/not/exist") == ws.GitFacts()
    assert ws.git_facts("") == ws.GitFacts()


def test_a_failing_git_never_raises(ws):
    facts = ws.git_facts("/tmp", runner=lambda *a, **k: None)
    assert (facts.repo, facts.branch) == ("", "")


def test_a_git_that_does_not_answer_at_all_has_failed(ws, repo):
    """Every call timed out, so `paths` was None and `failed = bool(paths)`
    said the directory was simply not a repository. `reload_git` wrote the
    empty facts over the known ones and did not ask again, so an idle row
    lost its repository and branch until the next tool call."""
    facts = ws.git_facts(str(repo), runner=lambda *a, **k: None)
    assert facts.failed is True
    # The name alone went missing when `status` answered and `rev-parse`
    # did not -- and `status` answering says this is a repository.
    real = ws.run

    def runner(args, **rest):
        return None if "rev-parse" in args else real(args, **rest)

    assert ws.git_facts(str(repo), runner=runner).failed is True


def test_the_label_drops_a_repeated_repository_name(ws):
    assert ws.path_label("/home/m/gra", "gra") == "gra"
    assert ws.path_label("/home/m/gra/tallfrog", "gra") == "gra/tallfrog"
    assert ws.path_label("/home/m/gra/tallfrog/") == "tallfrog"
    assert ws.path_label("") == "?"


def test_the_status_header_is_read(ws):
    assert ws.parse_status_branch("## main") == ("main", 0, 0)
    assert ws.parse_status_branch("## main...origin/main") == ("main", 0, 0)
    assert ws.parse_status_branch("## main...origin/main [ahead 2]") == ("main", 2, 0)
    assert ws.parse_status_branch("## main...origin/main [behind 3]") == ("main", 0, 3)
    assert ws.parse_status_branch(
        "## feature/x...origin/feature/x [ahead 2, behind 1]") == ("feature/x", 2, 1)
    assert ws.parse_status_branch("## No commits yet on main") == ("main", 0, 0)
    # A detached HEAD is not on a branch, and this line used to assert that
    # the whole phrase was one — it recorded what happened rather than what
    # should. It went on the sidebar row as if it were a branch name.
    assert ws.parse_status_branch("## HEAD (no branch)") == ("", 0, 0)


def test_a_branch_with_dots_keeps_them(ws):
    assert ws.parse_status_branch("## release/1.2...origin/release/1.2") == ("release/1.2", 0, 0)


def test_behind_is_counted(ws, repo, tmp_path):
    clone = tmp_path / "behind"
    subprocess.run(["git", "clone", "-q", str(repo), str(clone)], check=True, capture_output=True)
    git(repo, "commit", "-qm", "second", "--allow-empty")
    git(clone, "fetch", "-q")
    facts = ws.git_facts(str(clone))
    assert facts.behind == 1
    assert facts.ahead == 0


def test_a_fresh_repository_without_commits(ws, tmp_path):
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    git(fresh, "init", "-q", "-b", "main")
    facts = ws.git_facts(str(fresh))
    assert facts.repo == "fresh"
    assert facts.branch == "main"
    assert facts.dirty is False


def test_facts_are_filled_for_every_session(ws, repo, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    sessions = [
        ws.Session(session_id="a", cwd=str(repo)),
        ws.Session(session_id="b", cwd=str(repo)),
        ws.Session(session_id="c", cwd=str(plain)),
        ws.Session(session_id="d", cwd=""),
    ]
    ws.add_git_facts(sessions)
    assert sessions[0].git.branch == "main"
    assert sessions[1].git is sessions[0].git or sessions[1].git.branch == "main"
    assert sessions[2].git == ws.GitFacts()
    assert sessions[3].git == ws.GitFacts()


def test_a_command_that_writes_invalid_utf8_does_not_raise(ws):
    """tmux capture-pane and git diff can both hand us bytes that are not UTF-8.
    `run` promises None on failure; it must not raise instead."""
    import sys

    code = r"import sys; sys.stdout.buffer.write(b'ok \xff\xfe bad\n')"
    out = ws.run([sys.executable, "-c", code])
    assert out is not None
    assert "ok" in out and "bad" in out


def test_a_command_that_fails_returns_none(ws):
    import sys

    assert ws.run([sys.executable, "-c", "raise SystemExit(3)"]) is None
    assert ws.run(["definitely-not-a-command-here"]) is None


def test_run_keeps_blank_lines(ws):
    """A command's output is handed back as it came. A file being read is a
    screen of text where a blank line carries meaning."""
    import sys

    assert ws.run([sys.executable, "-c", r"print('\n\na\n\n')"]) == "\n\na\n\n\n"


def test_a_bare_layout_keeps_the_project_name(ws, tmp_path):
    """The layout worktrees are usually built on: a bare repo in `<project>/.bare`
    with each worktree beside it. The repository is the directory above."""
    project = tmp_path / "oans"
    project.mkdir()
    bare = project / ".bare"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)],
                   check=True, capture_output=True)
    seed = tmp_path / "seed"
    subprocess.run(["git", "clone", "-q", str(bare), str(seed)], check=True,
                   capture_output=True)
    git(seed, "config", "user.email", "t@e.com")
    git(seed, "config", "user.name", "T")
    (seed / "README.md").write_text("1\n")
    git(seed, "add", "."), git(seed, "commit", "-qm", "first")
    git(seed, "push", "-q", "origin", "main")

    tree = project / "gladbird"
    subprocess.run(["git", "-C", str(bare), "worktree", "add", "-q", str(tree), "main"],
                   check=True, capture_output=True)
    facts = ws.git_facts(str(tree))
    assert facts.repo == "oans", f"got {facts.repo!r}"
    assert ws.path_label(str(tree), facts.repo) == "oans/gladbird"


# --- what a real git actually writes -----------------------------------------


def test_a_real_diff_of_a_quoted_name_matches_the_file_listing(ws, repo):
    """Hand-written diffs are only as right as the hand that wrote them. This
    one comes out of git, and the name it gives has to be the name `ls-files`
    gives — or the same line has two different anchors in the two tabs and a
    review comment lands on neither."""
    name = 'we"ird.txt'
    (repo / name).write_text("one\n")
    git(repo, "add", "--", name)
    git(repo, "commit", "-qm", "weird")
    (repo / name).write_text("two\n")

    text, cut = ws.git_diff(str(repo), ["HEAD"])
    assert cut is False
    assert text and 'diff --git "a/we' in text, "git did not quote it after all"
    one = ws.parse_diff(text)[0]
    assert one.path == name
    assert one.old_path == name
    assert one.status == "modified"
    listed = [one.path for one in ws.worktree_files(str(repo)).files]
    assert name in listed


def test_a_real_diff_of_a_form_feed_keeps_the_line_whole(ws, repo):
    """git emits four lines here; `splitlines()` made five of them."""
    (repo / "ff.txt").write_text("aaa\nbbb\x0c ccc\nddd\neee\n")
    git(repo, "add", "ff.txt")
    git(repo, "commit", "-qm", "ff")
    (repo / "ff.txt").write_text("aaa\nbbb\x0c ccc\nddd\nCHANGED\n")

    text, _ = ws.git_diff(str(repo), ["HEAD"])
    one = ws.parse_diff(text)[0]
    lines = one.hunks[0].lines
    assert [line.kind for line in lines] == [
        "context", "context", "context", "removed", "added"]
    assert lines[1].text == "bbb\x0c ccc"


def test_a_cut_diff_never_ends_inside_a_line(ws, monkeypatch):
    """The cut used to land wherever the count ran out. Inside a
    `diff --git` line it parsed as a file that does not exist, reported as a
    rename, at the bottom of the tab — `cut` says something was dropped, not
    that the last entry is fiction."""
    long_name = "a" * 400
    text = ("diff --git a/small.txt b/small.txt\n--- a/small.txt\n"
            "+++ b/small.txt\n@@ -1 +1 @@\n-one\n+two\n"
            f"diff --git a/{long_name} b/{long_name}\n")
    monkeypatch.setattr(ws, "DIFF_MAX_BYTES", 120)
    out, cut = ws.git_diff("/w", [], runner=lambda *a, **k: text)
    assert cut is True
    assert out.endswith("\n")
    assert [one.path for one in ws.parse_diff(out)] == ["small.txt"]


def test_the_diff_cap_counts_bytes(ws, monkeypatch):
    """`run` hands back text, so the cap counted code points and let a diff of
    four-byte characters through at about four times the size. The other cap,
    `FILE_MAX_BYTES`, measures real bytes."""
    text = "diff --git a/e.txt b/e.txt\n" + "".join(
        "+\U0001f600\U0001f600\U0001f600\U0001f600\n" for _ in range(80))
    monkeypatch.setattr(ws, "DIFF_MAX_BYTES", 600)
    out, cut = ws.git_diff("/w", [], runner=lambda *a, **k: text)
    assert cut is True
    assert len(out.encode("utf-8")) <= 600
    assert len(text) <= 600, "this text is under the cap in code points"
    assert len(text.encode("utf-8")) > 600, "and over it in bytes"


# --- a failed call is not an answer, and is not remembered as one ------------


def test_a_failed_status_is_not_a_clean_repository(ws, repo, monkeypatch):
    """The two used to be byte-identical: a `status` that timed out gave the
    same empty facts as a repository with nothing to report, minus the branch
    name. `status` runs under a two second timeout, which was measured too short
    on a large worktree."""
    real = ws.run

    def runner(args, **rest):
        if "status" in args:
            return None                 # as a timeout does
        return real(args, **rest)

    facts = ws.git_facts(str(repo), runner=runner)
    assert facts.failed is True
    assert facts.repo == "myrepo"       # the first call still answered
    good = ws.git_facts(str(repo))
    assert good.failed is False
    assert good.branch == "main"


def test_a_directory_that_is_not_a_repository_has_not_failed(ws, tmp_path):
    """`status` fails outside a repository too, and that is an answer."""
    facts = ws.git_facts(str(tmp_path))
    assert facts.failed is False
    assert facts.branch == "" and facts.repo == ""


def test_a_failed_read_is_asked_again_rather_than_kept(ws, repo, monkeypatch):
    """`reload_git` recorded the directory as read and assigned the empty
    facts over the good ones, so an idle session kept "no branch, clean" until
    a tool call happened to touch the tree. The row also renamed itself and
    jumped, because the sort key holds the repository name."""
    store = ws.Store()
    session = ws.Session(session_id="s1", cwd=str(repo))
    session.git = ws.GitFacts(repo="myrepo", branch="main")
    store.sessions["s1"] = session

    monkeypatch.setattr(ws, "git_facts_many",
                        lambda dirs: {d: ws.GitFacts(failed=True) for d in dirs})
    store.reload_git([session], 1000.0)
    assert session.git.branch == "main", "the failure was written over it"
    assert str(repo) in store.git_wanted, "and it will never be asked again"

    monkeypatch.setattr(ws, "git_facts_many",
                        lambda dirs: {d: ws.GitFacts(repo="myrepo", branch="side")
                                      for d in dirs})
    store.reload_git([session], 1000.0 + ws.GIT_MIN_INTERVAL)
    assert session.git.branch == "side"


def test_a_worktree_git_could_not_read_says_so(ws, repo, monkeypatch):
    """`worktree_root` gives "" both for "not a repository" and for "git did
    not answer", and the empty listing went out with `failed: false` — so the
    page drew "this worktree holds no file that git knows about" over a
    worktree it simply could not read."""
    tree = ws.worktree_files(str(repo), runner=lambda args, **rest: None)
    assert tree.failed is True
    assert tree.files == []

    # And a directory that is not a repository is not a failure: git answers,
    # it just has nothing to say about this place.
    nowhere = ws.worktree_files("/", runner=lambda args, **rest:
                                "git version 2.44.0" if "--version" in args else None)
    assert nowhere.failed is False


def test_a_failed_untracked_listing_is_not_an_empty_one(ws, repo):
    """`git_names` reports a failure as None and it was collapsed to `[]`, so
    the Diff tab said nothing was untracked."""
    (repo / "loose.txt").write_text("new\n")
    real = ws.run

    def runner(args, **rest):
        if "ls-files" in args and "--others" in args and "--ignored" not in args:
            return None
        return real(args, **rest)

    report = ws.worktree_diff(str(repo), runner=runner)
    assert report.failed is True
    assert report.untracked == []

    good = ws.worktree_diff(str(repo))
    assert good.failed is False
    assert good.untracked == ["loose.txt"]


def test_a_detached_head_is_not_a_branch(ws, repo):
    """Measured against a real git: `## HEAD (no branch)`."""
    git(repo, "checkout", "--detach", "-q")
    facts = ws.git_facts(str(repo))
    assert facts.branch == ""
    assert facts.failed is False


# --- one commit at a time ----------------------------------------------------


def branch_of_three(repo):
    """`main` with one commit, and a branch with two more on top of it."""
    git(repo, "checkout", "-qb", "side")
    (repo / "README.md").write_text("# readme\n\nhello\nsecond\n")
    git(repo, "commit", "-qam", "two")
    (repo / "c.txt").write_text("c\n")
    git(repo, "add", "c.txt")
    git(repo, "commit", "-qm", "three: add c")


def test_the_diff_lists_the_branchs_own_commits_newest_first(ws, repo):
    branch_of_three(repo)
    report = ws.worktree_diff(str(repo))
    assert [one.subject for one in report.commits] == ["three: add c", "two"]
    assert report.recent is False
    assert all(len(one.sha) >= 40 and one.author == "T" and one.when > 0
               for one in report.commits)
    # Everything is still what it was: both halves, with nothing picked.
    assert report.of == ""
    assert [one.name for one in report.sections] == ["committed", "uncommitted"]


def test_one_commit_is_shown_against_its_parent_and_nothing_else(ws, repo):
    branch_of_three(repo)
    (repo / "README.md").write_text("# readme\n\nhello\nsecond\nthird\n")
    (repo / "loose.txt").write_text("new\n")
    two = ws.worktree_diff(str(repo)).commits[1]
    report = ws.worktree_diff(str(repo), of=two.sha)
    assert report.of == two.sha
    assert [one.name for one in report.sections] == ["commit"]
    files = report.sections[0].files
    assert [one.path for one in files] == ["README.md"]
    assert [line.text for line in files[0].hunks[0].lines
            if line.kind == "added"] == ["second"]
    # Not the uncommitted line, and not the untracked file: those are not
    # this commit's.
    assert report.untracked == []
    # The map from this commit to the file on disk, for anchoring comments.
    assert [one.path for one in report.since] == ["README.md"]
    assert [line.text for line in report.since[0].hunks[0].lines
            if line.kind == "added"] == ["third"]


def test_a_commit_the_page_names_is_used_only_if_git_listed_it(ws, repo):
    """The sha comes from the page, and the page is input. A name that is not
    on the list goes to git never, and the report says it has gone -- which is
    what an amend or a rebase looks like from the reader's chair."""
    branch_of_three(repo)
    asked = []
    real = ws.run

    def runner(args, **rest):
        asked.append(list(args))
        return real(args, **rest)

    for wanted in ("--output=/tmp/x", "HEAD~1", "0" * 40):
        asked.clear()
        report = ws.worktree_diff(str(repo), runner=runner, of=wanted)
        assert report.gone == wanted and report.of == ""
        assert [one.name for one in report.sections] == [
            "committed", "uncommitted"]
        assert not any(wanted in arg for args in asked for arg in args), wanted


def test_the_root_commit_is_shown_against_nothing(ws, repo):
    """It has no parent to be measured against; the empty tree stands in."""
    report = ws.worktree_diff(str(repo))
    assert report.recent is True          # on main: nothing of its own
    first = report.commits[-1]
    assert first.parent == ""
    shown = ws.worktree_diff(str(repo), of=first.sha)
    assert shown.failed is False
    assert [(one.path, one.status) for one in shown.sections[0].files] == [
        ("README.md", "added")]


def test_only_what_is_not_committed(ws, repo):
    branch_of_three(repo)
    (repo / "README.md").write_text("changed\n")
    (repo / "loose.txt").write_text("new\n")
    report = ws.worktree_diff(str(repo), of="uncommitted")
    assert report.of == "uncommitted"
    assert [one.name for one in report.sections] == ["uncommitted"]
    assert report.untracked == ["loose.txt"]


def test_a_commit_list_git_did_not_give_is_a_failure(ws, repo):
    real = ws.run

    def runner(args, **rest):
        return None if "log" in args else real(args, **rest)

    report = ws.worktree_diff(str(repo), runner=runner)
    assert report.failed is True
    assert report.commits == []


def test_a_merge_is_shown_against_its_first_parent(ws, repo):
    branch_of_three(repo)
    git(repo, "checkout", "-q", "main")
    (repo / "m.txt").write_text("m\n")
    git(repo, "add", "m.txt")
    git(repo, "commit", "-qm", "on main")
    git(repo, "checkout", "-q", "side")
    git(repo, "merge", "-q", "--no-edit", "main")
    merge = ws.worktree_diff(str(repo)).commits[0]
    assert merge.merge is True
    shown = ws.worktree_diff(str(repo), of=merge.sha)
    assert [one.path for one in shown.sections[0].files] == ["m.txt"]
    assert "merge" in shown.sections[0].about


def test_one_commit_carries_its_whole_message(ws, repo):
    """The subject is the line that says least; the why is in the body."""
    git(repo, "checkout", "-qb", "side")
    (repo / "README.md").write_text("changed\n")
    git(repo, "commit", "-qam", "Change the readme",
        "-m", "Because the old one said nothing.\n\n- a list\n- kept as lines")
    report = ws.worktree_diff(str(repo))
    shown = ws.worktree_diff(str(repo), of=report.commits[0].sha)
    assert shown.body == ("Because the old one said nothing.\n\n"
                          "- a list\n- kept as lines")
    # Only for the commit shown: everything else is not one commit.
    assert report.body == ""


# --- more of a file, between its changes ------------------------------------


def long_file(repo, name="long.txt", lines=120):
    (repo / name).write_text("".join(f"line {n}\n" for n in range(1, lines + 1)))
    git(repo, "add", name)
    git(repo, "commit", "-qm", "long")


def change(repo, name, *numbers):
    rows = (repo / name).read_text().splitlines()
    for number in numbers:
        rows[number - 1] = f"changed {number}"
    (repo / name).write_text("\n".join(rows) + "\n")


def test_a_whole_file_is_every_line_of_the_side_the_half_shows(ws, repo):
    """The committed half's new side is HEAD, so its whole file is HEAD's,
    not the disk's; the uncommitted half's is the disk's."""
    git(repo, "checkout", "-qb", "side")
    long_file(repo)
    change(repo, "long.txt", 30)
    git(repo, "commit", "-qam", "thirty")
    change(repo, "long.txt", 90)
    committed = ws.whole_file_diff(str(repo), "committed", "long.txt")
    lines = [line for hunk in committed.file.hunks for line in hunk.lines]
    assert len([one for one in lines if one.kind != "removed"]) == 120
    texts = [one.text for one in lines if one.kind != "removed"]
    assert "changed 30" in texts and "line 90" in texts   # HEAD, not the disk
    uncommitted = ws.whole_file_diff(str(repo), "uncommitted", "long.txt")
    texts = [one.text for hunk in uncommitted.file.hunks for one in hunk.lines
             if one.kind != "removed"]
    assert "changed 90" in texts and len(texts) == 120


def test_a_whole_file_of_one_commit_asks_git_only_for_a_listed_one(ws, repo):
    git(repo, "checkout", "-qb", "side")
    long_file(repo)
    sha = ws.worktree_diff(str(repo)).commits[0].sha
    assert ws.whole_file_diff(str(repo), "commit", "long.txt", of=sha).file
    asked = []
    real = ws.run

    def runner(args, **rest):
        asked.append(list(args))
        return real(args, **rest)

    for wanted in ("HEAD~1", "--output=/tmp/x", "0" * 40):
        asked.clear()
        found = ws.whole_file_diff(str(repo), "commit", "long.txt", of=wanted,
                                   runner=runner)
        assert found.file is None
        assert not any(wanted in arg for args in asked for arg in args), wanted
    # A section that is not one of the three is refused before git is asked.
    asked.clear()
    assert ws.whole_file_diff(str(repo), "--cached", "long.txt",
                              runner=runner).file is None
    assert not any("diff" in args for args in asked)


def test_a_renamed_file_is_whole_only_with_both_names(ws, repo):
    long_file(repo)
    git(repo, "mv", "long.txt", "moved.txt")
    change(repo, "moved.txt", 60)
    git(repo, "add", "-A")
    found = ws.whole_file_diff(str(repo), "uncommitted", "moved.txt",
                               old_path="long.txt")
    assert found.file is not None and found.file.status == "renamed"
    assert sum(len(hunk.lines) for hunk in found.file.hunks) == 121


def test_the_diff_says_three_lines_of_context_whatever_the_reader_set(ws, repo):
    """The page reads fewer than three lines after the last change as the
    end of the file. A reader's `diff.context = 1` would have made every
    file look as though it ended one line after its last change."""
    long_file(repo)
    git(repo, "config", "diff.context", "1")
    change(repo, "long.txt", 50)
    lines = ws.worktree_diff(str(repo)).sections[-1].files[0].hunks[0].lines
    assert [one.kind for one in lines].count("context") == 6


# --- what the reader's git and odd names must not change ---------------------


def test_git_never_takes_the_index_lock_the_agent_needs(ws, repo):
    """`status` and `diff` write a refreshed index back under
    `.git/index.lock`. The daemon runs them just after an agent's tool
    call, when the agent runs `git add`, and a `status` killed at its
    timeout left the lock for good. So no git of the daemon writes the
    index. The last line shows the file on disk did need a refresh."""
    for index in range(20):
        (repo / f"f{index}.txt").write_text(f"{index}\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "files")
    for index in range(20):
        os.utime(repo / f"f{index}.txt", (1, 1))    # same bytes, other stat
    (repo / "README.md").write_text("changed\n")
    index = repo / ".git" / "index"
    before = index.read_bytes()
    assert ws.git_facts(str(repo)).dirty is True
    assert ws.changed_files(str(repo)) == {"README.md"}
    report = ws.worktree_diff(str(repo))
    assert [one.path for one in report.sections[-1].files] == ["README.md"]
    assert index.read_bytes() == before
    assert not (repo / ".git" / "index.lock").exists()
    subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                   check=True, capture_output=True)
    assert index.read_bytes() != before


def test_an_old_git_that_prints_path_format_back_keeps_the_repository(
        ws, repo, tmp_path):
    """git before 2.31 does not fail on `--path-format=absolute`: it prints
    the flag back, exits 0, and gives the common directory relative to where
    it ran. That line was the repository's name, and every row read
    `--path-format=absolute/<dir>`. This git (2.43 here) does the same for a
    flag it does not know, which is what the stand-in copies."""
    shown = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--path-formatx=absolute",
         "--git-common-dir"], capture_output=True, text=True, check=True)
    assert shown.stdout.splitlines()[0] == "--path-formatx=absolute"
    git(repo, "remote", "add", "origin", "https://example.com/team/myrepo.git")

    def old(args, **rest):
        args = list(args)
        if "--path-format=absolute" not in args:
            return ws.run(args, **rest)
        out = ws.run([one for one in args if one != "--path-format=absolute"],
                     **rest)
        return None if out is None else "--path-format=absolute\n" + out

    (repo / "src" / "deeper").mkdir(parents=True)
    for where in (repo, repo / "src" / "deeper"):
        facts = ws.git_facts(str(where), runner=old)
        assert facts.repo == "myrepo", where
        assert facts.root == str(repo)
        assert facts.remote == "https://example.com/team/myrepo.git"


def test_the_readers_diff_settings_do_not_change_the_names(ws, repo):
    """`diff.mnemonicPrefix` wrote `c/` and `w/`, so every file read as a
    rename; `diff.noprefix` wrote no prefix, so `b/c.py` lost its folder;
    `diff.renames=copies` made a copy read as a rename of its source."""
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("x\n")
    (repo / "b").mkdir()
    (repo / "b" / "c.py").write_text("c\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "code")
    (repo / "src" / "a.py").write_text("y\n")
    (repo / "b" / "c.py").write_text("d\n")
    (repo / "src" / "copy.py").write_text("x\n")
    git(repo, "add", ".")
    for key, value in (("diff.mnemonicPrefix", "true"), ("diff.noprefix", "true"),
                       ("diff.renames", "copies")):
        git(repo, "config", key, value)
        files = ws.worktree_diff(str(repo)).sections[-1].files
        assert sorted((one.path, one.old_path, one.status) for one in files) == [
            ("b/c.py", "b/c.py", "modified"),
            ("src/a.py", "src/a.py", "modified"),
            ("src/copy.py", "", "added")], key
        git(repo, "config", "--unset", key)


def test_a_submodule_is_its_own_file_and_its_log_is_not_lines_of_another(
        ws, repo, tmp_path):
    """`diff.submodule=log` writes `Submodule sub a..b:` and `  > message`
    lines with no header of their own. They were read as context lines of
    the file before, which then had an eleventh line out of ten."""
    inner = tmp_path / "inner"
    inner.mkdir()
    git(inner, "init", "-q", "-b", "main")
    git(inner, "config", "user.email", "t@example.com")
    git(inner, "config", "user.name", "T")
    (inner / "x").write_text("x\n")
    git(inner, "add", ".")
    git(inner, "commit", "-qm", "first in the submodule")
    (repo / "a.txt").write_text("".join(f"{n}\n" for n in range(1, 11)))
    git(repo, "-c", "protocol.file.allow=always", "submodule", "add", "-q",
        str(inner), "sub")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "with a submodule")
    (inner / "x").write_text("y\n")
    git(inner, "commit", "-qam", "a message in the submodule")
    git(repo / "sub", "-c", "protocol.file.allow=always", "pull", "-q")
    with (repo / "a.txt").open("a") as handle:
        handle.write("11\n")
    git(repo, "config", "diff.submodule", "log")
    files = {one.path: one for one in ws.worktree_diff(str(repo)).sections[-1].files}
    assert sorted(files) == ["a.txt", "sub"]
    lines = [line for hunk in files["a.txt"].hunks for line in hunk.lines]
    assert [line.text for line in lines] == ["8", "9", "10", "11"]
    assert files["sub"].status == "modified"


def test_a_file_that_became_a_link_is_one_entry(ws, repo):
    """git writes a type change as a deletion and an addition of the same
    path. Two entries shared one key in the list, a click on either went to
    the second, `whole_file_diff` found the first, and a comment on the file
    stood on both. #241. A committed one each way, and one not committed
    from an empty file, whose old side has no lines."""
    (repo / "notes.txt").write_text("one\ntwo\nthree\n")
    os.symlink("README.md", repo / "was-link")
    (repo / "empty").write_text("")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "three to change")
    git(repo, "checkout", "-qb", "side")
    (repo / "notes.txt").unlink()
    os.symlink("README.md", repo / "notes.txt")
    (repo / "was-link").unlink()
    (repo / "was-link").write_text("now\na file\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "types")
    (repo / "empty").unlink()
    os.symlink("notes.txt", repo / "empty")
    report = ws.worktree_diff(str(repo), base="main")
    committed, uncommitted = report.sections

    def shown(one):
        return (one.path, one.old_path, one.status, one.old_kind,
                one.new_kind, one.added, one.removed,
                [(hunk.header, [line.kind for line in hunk.lines])
                 for hunk in one.hunks])

    assert [shown(one) for one in committed.files] == [
        ("notes.txt", "notes.txt", "typechange", "file", "link", 1, 3,
         [("@@ -1,3 +1,1 @@", ["removed"] * 3 + ["added"])]),
        ("was-link", "was-link", "typechange", "link", "file", 2, 1,
         [("@@ -1,1 +1,2 @@", ["removed", "added", "added"])]),
    ]
    assert [shown(one) for one in uncommitted.files] == [
        ("empty", "empty", "typechange", "file", "link", 1, 0,
         [("@@ -0,0 +1,1 @@", ["added"])]),
    ]
    # The whole file of each is that one entry, not its first half.
    whole = ws.whole_file_diff(str(repo), "committed", "notes.txt", base="main")
    assert shown(whole.file) == shown(committed.files[0])
    whole = ws.whole_file_diff(str(repo), "uncommitted", "empty")
    assert shown(whole.file) == shown(uncommitted.files[0])
    # One commit shown alone joins them too, and its map to the disk reads
    # the path once.
    sha = report.commits[0].sha
    one = ws.worktree_diff(str(repo), of=sha, base="main")
    assert [each.path for each in one.sections[0].files] == ["notes.txt", "was-link"]
    assert [each.status for each in one.sections[0].files] == ["typechange"] * 2


def test_a_file_named_head_does_not_break_the_diff_tab(ws, repo):
    """git refuses `HEAD` as "both revision and filename" when a file of
    that name stands at the top of the worktree, and the tab failed on
    every poll. The `--` after the revisions says no file is meant. A range
    (`a..b`) is never checked, so `HEAD` and a commit shown alone are what
    needs it: here both have a file of their name."""
    branch_of_three(repo)
    (repo / "HEAD").write_text("not a revision\n")
    (repo / "README.md").write_text("changed\n")
    report = ws.worktree_diff(str(repo), base="main")
    assert report.failed is False
    assert [one.subject for one in report.commits] == ["three: add c", "two"]
    assert [one.name for one in report.sections] == ["committed", "uncommitted"]
    assert report.sections[-1].files[0].path == "README.md"
    assert "HEAD" in report.untracked
    sha = report.commits[0].sha
    (repo / sha).write_text("not a commit\n")
    one = ws.worktree_diff(str(repo), of=sha)
    assert one.failed is False and one.body == ""
    assert [each.path for each in one.sections[0].files] == ["c.txt"]
    git(repo, "checkout", "-qf", "main")
    recent = ws.worktree_diff(str(repo))
    assert recent.failed is False and recent.recent is True
    assert [each.subject for each in recent.commits] == ["first"]


def test_a_branch_named_like_an_option_never_reaches_git_as_one(ws, repo):
    """git takes `update-ref refs/heads/--output=pwned`. Its short name went
    into `git diff --output=pwned...HEAD`, and git wrote the diff into a
    file. git is given the full name; the reader still sees the short one."""
    branch_of_three(repo)
    git(repo, "update-ref", "refs/heads/--output=pwned", "main")
    seen = []

    def spy(args, **rest):
        seen.append(list(args))
        return ws.run(args, **rest)

    report = ws.worktree_diff(str(repo), runner=spy, base="--output=pwned")
    assert report.base == "--output=pwned" and report.failed is False
    assert [one.subject for one in report.commits] == ["three: add c", "two"]
    assert [one.path for one in report.sections[0].files] == ["README.md", "c.txt"]
    whole = ws.whole_file_diff(str(repo), "committed", "c.txt", runner=spy,
                               base="--output=pwned")
    assert whole.failed is False and whole.file.path == "c.txt"
    whole = ws.whole_file_diff(str(repo), "commit", "c.txt", runner=spy,
                               of=report.commits[0].sha, base="--output=pwned")
    assert whole.failed is False and whole.file.path == "c.txt"
    assert not any(part.startswith("--output") for argv in seen for part in argv)
    assert not [one for one in repo.iterdir() if "pwned" in one.name]


def test_a_worktree_whose_path_ends_in_a_space_is_that_worktree(ws, tmp_path):
    """`strip()` took the space off `/x/proj `, so the tab read nothing --
    or, with `/x/proj` there too, the other repository."""
    for name, text in (("proj", "the other one\n"), ("proj ", "this one\n")):
        root = tmp_path / name
        root.mkdir()
        git(root, "init", "-q", "-b", "main")
        (root / "notes.md").write_text(text)
        git(root, "add", ".")
    spaced = str(tmp_path / "proj ")
    assert ws.worktree_root(spaced) == spaced
    assert ws.git_facts(spaced).root == spaced
    assert ws.read_worktree_file(spaced, "notes.md").text == "this one\n"


def test_a_textconv_does_not_move_the_diffs_line_numbers(ws, repo):
    """`git diff` applies a `textconv` from `.gitattributes` unless told not
    to. Its lines were those of the converted text, one header line more
    here, and not the lines the Files tab reads."""
    (repo / ".gitattributes").write_text("*.dat diff=up\n")
    (repo / "d.dat").write_text("a\nb\nc\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "data")
    git(repo, "config", "diff.up.textconv",
        "sh -c 'printf \"a header\\n\"; cat \"$1\"' -")
    (repo / "d.dat").write_text("a\nB\nc\n")
    hunk = ws.worktree_diff(str(repo)).sections[-1].files[0].hunks[0]
    assert hunk.header.startswith("@@ -1,3 +1,3 @@")
    assert [line.text for line in hunk.lines] == ["a", "b", "B", "c"]


def test_a_quoted_remote_url_carries_no_password(ws, repo):
    """git reads `url = "…"` without its quotes, and `git config` writes
    them itself around a value holding `;` or `#`. `configparser` kept
    them, `urlsplit` then found no scheme, and the token went to the page."""
    git(repo, "remote", "add", "origin", "https://example.com/x.git")
    config = repo / ".git" / "config"
    plain = config.read_text()
    for written, wanted in (
            ('"https://me:ghp_secret@github.com/a/b.git"',
             "https://github.com/a/b.git"),
            ('"https://me:ghp_secret@github.com/a/\\"b\\".git" ; mine',
             'https://github.com/a/"b".git')):
        config.write_text(plain.replace("https://example.com/x.git", written))
        assert ws.git_facts(str(repo)).remote == wanted, written
    git(repo, "config", "remote.origin.url",
        "https://me:ghp_secret@github.com/a/b.git;v2")
    assert '"' in config.read_text()
    assert ws.git_facts(str(repo)).remote == "https://github.com/a/b.git;v2"


def test_a_password_the_url_parse_missed_is_hidden_all_the_same(ws, repo):
    """The second guard: a URL inside the URL is not in its netloc, so the
    first one does not see it."""
    git(repo, "remote", "add", "origin",
        "https://proxy.example.com/?to=https://me:ghp_secret@github.com/a.git")
    remote = ws.git_facts(str(repo)).remote
    assert "ghp_secret" not in remote and "me:" not in remote
    assert remote.startswith("https://proxy.example.com/")


def test_a_remote_of_a_megabyte_costs_the_tick_no_time(ws, repo):
    """The remote is read on the tick thread, and an agent can write any
    line into the config. A megabyte of `a.token.` took the secret patterns
    8.5 s whole; the hover shows the start of it, and only that is looked
    at. What is left is reading the file, which `config_value` does a
    character at a time: 0.23 s for the megabyte, and linear. CPU time, so
    a loaded machine does not fail it, and a second, so a slow one does
    not."""
    import time

    git(repo, "remote", "add", "origin", "https://example.com/x.git")
    config = repo / ".git" / "config"
    config.write_text(config.read_text().replace(
        "https://example.com/x.git", "https://example.com/" + "a.token." * 125_000))
    start = time.process_time()
    remote = ws.remote_url(str(repo / ".git"))
    assert time.process_time() - start < 1.0
    assert remote.startswith("https://example.com/a.token.")
    assert len(remote) <= ws.REMOTE_SHOWN


def test_a_key_without_a_value_does_not_hide_the_remote(ws, repo):
    """git reads a key alone on a line, `fsmonitor` under `[core]` say, as
    true. `configparser` called it an error, and the remote came back
    empty. A made-up key here, so git starts nothing for it."""
    git(repo, "remote", "add", "origin", "https://example.com/team/myrepo.git")
    config = repo / ".git" / "config"
    config.write_text(config.read_text().replace("[core]", "[core]\n\tsparse", 1))
    assert git_value(repo, "core.sparse") == "true"
    assert ws.git_facts(str(repo)).remote == "https://example.com/team/myrepo.git"


def git_value(repo, key):
    return subprocess.run(["git", "-C", str(repo), "config", "--type=bool", key],
                          capture_output=True, text=True, check=True).stdout.strip()
