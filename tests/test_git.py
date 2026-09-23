"""git facts, read from a real repository in a temporary directory."""

from __future__ import annotations

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
    assert facts == ws.GitFacts()


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
    name. `status` runs under a two second timeout, which PLAN 4.7 already
    records as measured too short on a large worktree."""
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
