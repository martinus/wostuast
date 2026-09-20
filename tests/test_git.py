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
    assert ws.parse_status_branch("## HEAD (no branch)") == ("HEAD (no branch)", 0, 0)


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
