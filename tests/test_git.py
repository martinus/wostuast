"""git facts, read from a real repository in a temporary directory."""

from __future__ import annotations

import subprocess

import pytest


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True,
                   capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "myrepo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    (root / "a.txt").write_text("one\n")
    git(root, "add", "a.txt")
    git(root, "commit", "-qm", "first")
    return root


def test_a_clean_repository(ws, repo):
    facts = ws.git_facts(str(repo))
    assert facts.repo == "myrepo"
    assert facts.branch == "main"
    assert facts.dirty is False
    assert facts.touched_files == 0
    assert facts.ahead == 0 and facts.behind == 0


def test_a_dirty_repository_counts_its_files(ws, repo):
    (repo / "a.txt").write_text("two\n")
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
    """peek renders a terminal screen, where blank lines carry meaning."""
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
    (seed / "a.txt").write_text("1\n")
    git(seed, "add", "."), git(seed, "commit", "-qm", "first")
    git(seed, "push", "-q", "origin", "main")

    tree = project / "gladbird"
    subprocess.run(["git", "-C", str(bare), "worktree", "add", "-q", str(tree), "main"],
                   check=True, capture_output=True)
    facts = ws.git_facts(str(tree))
    assert facts.repo == "oans", f"got {facts.repo!r}"
    assert ws.path_label(str(tree), facts.repo) == "oans/gladbird"
