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
