"""The Files tab and the Diff tab, read from real repositories."""

from __future__ import annotations

import os
import subprocess

import pytest

from conftest import git_in as git


@pytest.fixture
def seeded(repo):
    """The shared repository, plus a second Markdown file and some code."""
    (repo / "notes.md").write_text("# notes\n")
    (repo / "code.py").write_text("print(1)\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "more")
    return repo


# --- the listing -------------------------------------------------------------


def test_every_file_is_listed_whatever_its_kind(ws, seeded):
    tree = ws.worktree_files(str(seeded))
    assert tree.root == str(seeded)
    assert sorted(one.path for one in tree.files) == [
        "README.md", "code.py", "notes.md"]
    assert tree.total == 3


def test_an_untracked_file_is_listed(ws, seeded):
    (seeded / "draft.md").write_text("# draft\n")
    paths = [one.path for one in ws.worktree_files(str(seeded)).files]
    assert "draft.md" in paths


def test_an_ignored_file_is_not_listed(ws, seeded):
    (seeded / ".gitignore").write_text("build/\n")
    (seeded / "build").mkdir()
    (seeded / "build" / "out.md").write_text("# out\n")
    paths = [one.path for one in ws.worktree_files(str(seeded)).files]
    assert "build/out.md" not in paths
    assert ".gitignore" in paths


def test_the_named_files_come_first(ws, seeded):
    (seeded / "PLAN.md").write_text("# plan\n")
    (seeded / "CLAUDE.md").write_text("# claude\n")
    paths = [one.path for one in ws.worktree_files(str(seeded)).files]
    assert paths[:3] == ["PLAN.md", "CLAUDE.md", "README.md"]


def test_a_changed_file_comes_before_an_untouched_one(ws, seeded):
    """The question this tool exists to answer is what the agent just did, so
    what it touched sorts above the rest of the repository."""
    (seeded / "a-first-by-name.txt").write_text("quiet\n")
    git(seeded, "add", "."), git(seeded, "commit", "-qm", "quiet")
    (seeded / "notes.md").write_text("# notes\n\ntouched\n")
    paths = [one.path for one in ws.worktree_files(str(seeded)).files]
    assert paths[0] == "README.md"          # pinned, so it still wins
    assert paths[1] == "notes.md"           # changed
    assert "a-first-by-name.txt" in paths[2:]


def test_the_newest_change_leads_the_changed_files(ws, seeded):
    (seeded / "notes.md").write_text("# notes\n\nfirst\n")
    (seeded / "code.py").write_text("print(2)\n")
    os.utime(seeded / "code.py", (2_000_000_000, 2_000_000_000))
    paths = [one.path for one in ws.worktree_files(str(seeded)).files]
    assert paths[:3] == ["README.md", "code.py", "notes.md"]   # pinned, then newest


def test_a_changed_file_says_so(ws, seeded):
    (seeded / "notes.md").write_text("# notes\n\ntouched\n")
    changed = {one.path: one.changed for one in ws.worktree_files(str(seeded)).files}
    assert changed["notes.md"] is True
    assert changed["code.py"] is False


def test_a_repository_past_the_ceiling_is_cut_and_says_so(ws, seeded, monkeypatch):
    monkeypatch.setattr(ws, "FILES_MAX", 2)
    for index in range(6):
        (seeded / f"f{index}.txt").write_text("x")
    tree = ws.worktree_files(str(seeded))
    assert len(tree.files) == 2
    assert tree.total == 9
    assert tree.cut is True


def test_a_repository_of_five_thousand_files_is_not_cut(ws, tmp_path):
    """The first version sent the first 5000 names of 52,799 and let the page
    search those. Typing `libcorrelation` then found 16 files and missed more
    than a thousand, because the thousand were never sent."""
    repo = tmp_path / "big"
    (repo / "deep" / "down").mkdir(parents=True)
    git(repo, "init", "-q", ".")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "T")
    for index in range(5200):
        (repo / f"f{index:05d}.txt").write_text("x")
    (repo / "deep" / "down" / "libcorrelation.h").write_text("x")
    git(repo, "add", "-A")

    tree = ws.worktree_files(str(repo))
    assert tree.cut is False
    assert len(tree.files) == tree.total == 5201
    # The one that sorts last is the one the cut used to throw away.
    assert "deep/down/libcorrelation.h" in [one.path for one in tree.files]


def test_an_ignored_file_is_listed(ws, seeded):
    """A generated file among its sources is the ignored file people look
    for, and the tab used to leave it out entirely."""
    (seeded / ".gitignore").write_text("generated.h\n")
    (seeded / "generated.h").write_text("#pragma once\n")
    assert "generated.h" in [one.path for one in ws.worktree_files(str(seeded)).files]


def test_an_ignored_directory_is_not_walked(ws, seeded):
    """`node_modules` holds more files than the repository does. git collapses
    it to one entry ending in a slash, and a name nobody can open is dropped.
    """
    (seeded / ".gitignore").write_text("node_modules/\n")
    (seeded / "node_modules").mkdir()
    for index in range(5):
        (seeded / "node_modules" / f"m{index}.js").write_text("x")
    paths = [one.path for one in ws.worktree_files(str(seeded)).files]
    assert not [one for one in paths if one.startswith("node_modules")]


def test_a_listing_git_could_not_read_is_not_an_empty_worktree(ws, seeded):
    """Two seconds fits `git status` in a small worktree and nothing else.
    Over fifty thousand files the call timed out, nothing came back, and
    nothing drew as "this worktree holds no file that git knows about"."""
    def broken(args, **rest):
        return None if "ls-files" in args else ws.run(args, **rest)

    tree = ws.worktree_files(str(seeded), runner=broken)
    assert tree.failed is True
    assert tree.root


def test_a_listing_that_worked_is_not_marked_failed(ws, seeded):
    tree = ws.worktree_files(str(seeded))
    assert tree.failed is False
    assert tree.files


def test_one_failed_listing_still_returns_the_others(ws, seeded):
    """A short list with a warning beats no list at all."""
    def broken(args, **rest):
        return None if "--ignored" in args else ws.run(args, **rest)

    tree = ws.worktree_files(str(seeded))
    whole = [one.path for one in tree.files]
    partial = ws.worktree_files(str(seeded), runner=broken)
    assert partial.failed is True
    assert [one.path for one in partial.files] == whole


def test_the_listing_gets_its_own_timeout(ws, seeded):
    """The listing is the one git call whose cost grows with the repository."""
    seen = []

    def watch(args, **rest):
        seen.append(rest.get("timeout"))
        return ws.run(args, **rest)

    ws.worktree_files(str(seeded), runner=watch)
    assert ws.LIST_TIMEOUT > ws.RUN_TIMEOUT
    assert seen.count(ws.LIST_TIMEOUT) == 4    # three listings and the status


def test_a_pinned_name_deeper_in_the_tree_is_not_pinned(ws, seeded):
    (seeded / "docs").mkdir()
    (seeded / "docs" / "README.md").write_text("# deep\n")
    paths = [one.path for one in ws.worktree_files(str(seeded)).files]
    assert paths[0] == "README.md"
    assert "docs/README.md" in paths[1:]


def test_a_directory_that_is_not_a_repository_lists_nothing(ws, tmp_path):
    tree = ws.worktree_files(str(tmp_path))
    assert tree.root == "" and tree.files == []


def test_a_missing_directory_lists_nothing(ws):
    assert ws.worktree_files("/no/such/place").files == []


def test_a_listed_file_that_was_deleted_is_skipped(ws, seeded):
    (seeded / "notes.md").unlink()
    paths = [one.path for one in ws.worktree_files(str(seeded)).files]
    assert paths == ["README.md", "code.py"]


def test_a_worktree_lists_its_own_files(ws, seeded, tmp_path):
    tree_dir = tmp_path / "side"
    git(seeded, "worktree", "add", "-q", str(tree_dir), "-b", "side")
    (tree_dir / "only-here.md").write_text("# here\n")
    paths = [one.path for one in ws.worktree_files(str(tree_dir)).files]
    assert "only-here.md" in paths
    assert ws.worktree_files(str(tree_dir)).root == str(tree_dir)


# --- reading one file --------------------------------------------------------


def test_a_listed_file_is_read(ws, seeded):
    found = ws.read_worktree_file(str(seeded), "README.md")
    assert found.text == "# readme\n\nhello\n"
    assert found.binary is False
    assert found.mtime > 0


def test_a_file_that_is_not_markdown_is_read_too(ws, seeded):
    assert ws.read_worktree_file(str(seeded), "code.py").text == "print(1)\n"


def test_a_binary_file_is_named_rather_than_shown(ws, seeded):
    (seeded / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\0\0binary")
    found = ws.read_worktree_file(str(seeded), "logo.png")
    assert found.binary is True
    assert found.text == ""


def test_a_file_git_ignores_can_be_read(ws, seeded):
    """The Files tab lists ignored files, so reading one has to be allowed.
    A generated header next to its sources is the file people look for."""
    (seeded / ".gitignore").write_text("generated.h\n")
    (seeded / "generated.h").write_text("#pragma once\n")
    found = ws.read_worktree_file(str(seeded), "generated.h")
    assert found is not None
    assert found.text == "#pragma once\n"


def test_a_pathspec_that_matches_another_name_is_refused(ws, seeded):
    """git reads the name as a pathspec, so a glob would match real files. The
    answer has to come back spelled exactly as it was asked for."""
    assert ws.read_worktree_file(str(seeded), "*.py") is None
    assert ws.read_worktree_file(str(seeded), ":(glob)**/*.md") is None
    assert ws.read_worktree_file(str(seeded), ":(exclude)code.py") is None


def test_a_real_name_holding_glob_characters_is_read(ws, seeded):
    """`report[1].csv` is a character class to git unless the pathspec says
    the name means itself. The tab listed the file and then refused it."""
    for name in ("report[1].csv", "a*star.txt", "back\\slash.txt"):
        (seeded / name).write_text("real: " + name)
        assert name in [one.path for one in ws.worktree_files(str(seeded)).files]
        found = ws.read_worktree_file(str(seeded), name)
        assert found is not None, name
        assert found.text == "real: " + name


def test_the_git_directory_is_not_readable(ws, seeded):
    assert ws.read_worktree_file(str(seeded), ".git/config") is None


def test_a_file_inside_an_ignored_directory_is_readable_but_not_listed(ws, seeded):
    """The listing collapses an ignored directory to keep node_modules out of
    it. The guard answers a different question — is this safe to open — and
    a file under an ignored directory is as safe as any other in the tree."""
    (seeded / ".gitignore").write_text("build/\n")
    (seeded / "build").mkdir()
    (seeded / "build" / "out.txt").write_text("out\n")
    paths = [one.path for one in ws.worktree_files(str(seeded)).files]
    assert "build/out.txt" not in paths
    assert "build/" not in paths
    assert ws.read_worktree_file(str(seeded), "build/out.txt").text == "out\n"


def test_a_path_that_climbs_out_is_refused(ws, seeded, tmp_path):
    (tmp_path / "secret.md").write_text("# secret\n")
    assert ws.read_worktree_file(str(seeded), "../secret.md") is None


def test_an_absolute_path_is_refused(ws, seeded, tmp_path):
    (tmp_path / "secret.md").write_text("# secret\n")
    assert ws.read_worktree_file(str(seeded), str(tmp_path / "secret.md")) is None


def test_a_link_that_leaves_the_worktree_is_refused(ws, seeded, tmp_path):
    outside = tmp_path / "secret.md"
    outside.write_text("# secret\n")
    (seeded / "link.md").symlink_to(outside)
    git(seeded, "add", "link.md")
    # git lists it, so the listing alone would hand it over; the resolved path
    # is what refuses it.
    assert "link.md" in [one.path for one in ws.worktree_files(str(seeded)).files]
    assert ws.read_worktree_file(str(seeded), "link.md") is None


def test_a_long_file_is_cut(ws, seeded, monkeypatch):
    monkeypatch.setattr(ws, "FILE_MAX_BYTES", 20)
    (seeded / "notes.md").write_text("x" * 100)
    found = ws.read_worktree_file(str(seeded), "notes.md").text
    assert found.startswith("x" * 20)
    assert "not shown" in found


def test_bytes_that_are_not_utf8_do_not_raise(ws, seeded):
    (seeded / "notes.md").write_bytes(b"# notes \xff\xfe\n")
    assert "# notes" in ws.read_worktree_file(str(seeded), "notes.md").text


# --- parsing a diff ----------------------------------------------------------

SAMPLE = """diff --git a/a.txt b/a.txt
index 1234567..89abcde 100644
--- a/a.txt
+++ b/a.txt
@@ -1,3 +1,4 @@ def head():
 one
-two
+TWO
+two and a half
 three
diff --git a/new.txt b/new.txt
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/new.txt
@@ -0,0 +1 @@
+fresh
"""


def test_a_diff_is_split_into_files_and_hunks(ws):
    files = ws.parse_diff(SAMPLE)
    assert [one.path for one in files] == ["a.txt", "new.txt"]
    first = files[0]
    assert first.status == "modified"
    assert first.added == 2 and first.removed == 1
    assert len(first.hunks) == 1
    assert first.hunks[0].header.startswith("@@ -1,3 +1,4 @@")
    kinds = [line.kind for line in first.hunks[0].lines]
    assert kinds == ["context", "removed", "added", "added", "context"]
    assert first.hunks[0].lines[0].text == "one"
    assert first.hunks[0].lines[2].text == "TWO"


def test_an_added_file_says_so(ws):
    files = ws.parse_diff(SAMPLE)
    assert files[1].status == "added"
    assert files[1].added == 1 and files[1].removed == 0


def test_a_deleted_file_keeps_its_name(ws):
    text = ("diff --git a/gone.txt b/gone.txt\n"
            "deleted file mode 100644\n"
            "--- a/gone.txt\n"
            "+++ /dev/null\n"
            "@@ -1 +0,0 @@\n"
            "-bye\n")
    one = ws.parse_diff(text)[0]
    assert one.status == "deleted"
    assert one.path == "gone.txt"
    assert one.removed == 1


def test_a_rename_without_changes_is_read_from_its_header(ws):
    text = ("diff --git a/old.txt b/new.txt\n"
            "similarity index 100%\n"
            "rename from old.txt\n"
            "rename to new.txt\n")
    one = ws.parse_diff(text)[0]
    assert one.status == "renamed"
    assert one.old_path == "old.txt" and one.path == "new.txt"
    assert one.hunks == []


def test_a_rename_is_read_from_the_rename_lines_when_the_header_lies(ws):
    """`diff --git a/x b/y` cannot be split when a name holds ` b/`, which is
    why git also writes `rename from` and `rename to`. Without those two
    branches this file comes out with both paths wrong."""
    text = ("diff --git a/x.txt b/y b/z.txt\n"
            "similarity index 100%\n"
            "rename from x.txt\n"
            "rename to y b/z.txt\n")
    one = ws.parse_diff(text)[0]
    assert one.old_path == "x.txt"
    assert one.path == "y b/z.txt"
    assert one.status == "renamed"


def test_a_removed_comment_is_not_read_as_a_file_header(ws):
    """Removing `-- a comment` writes `--- a comment`. Read as a header that
    renamed the file to "a comment" and swallowed the rest of the hunk."""
    text = ("diff --git a/q.sql b/q.sql\n--- a/q.sql\n+++ b/q.sql\n"
            "@@ -1,3 +1,3 @@\n"
            "-- drop the old table\n"
            "+++ keep the new one\n"
            " select 1\n")
    one = ws.parse_diff(text)[0]
    assert one.path == "q.sql" and one.old_path == "q.sql"
    assert one.status == "modified"
    assert one.removed == 1 and one.added == 1
    lines = one.hunks[0].lines
    assert [line.kind for line in lines] == ["removed", "added", "context"]
    assert lines[0].text == "- drop the old table"
    assert lines[1].text == "++ keep the new one"


def test_a_header_after_a_hunk_still_starts_the_next_file(ws):
    text = ("diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n"
            "@@ -1 +1 @@\n-one\n+two\n"
            "diff --git a/b.txt b/b.txt\n--- a/b.txt\n+++ b/b.txt\n"
            "@@ -1 +1 @@\n-three\n+four\n")
    assert [one.path for one in ws.parse_diff(text)] == ["a.txt", "b.txt"]


def test_a_binary_file_is_marked(ws):
    text = ("diff --git a/logo.png b/logo.png\n"
            "index 1111111..2222222 100644\n"
            "Binary files a/logo.png and b/logo.png differ\n")
    one = ws.parse_diff(text)[0]
    assert one.binary is True
    assert one.hunks == []


def test_a_line_that_starts_with_a_marker_outside_a_hunk_is_ignored(ws):
    # The index and mode lines sit between the header and the first @@.
    files = ws.parse_diff(SAMPLE)
    assert files[0].added == 2       # not three, counting `+++ b/a.txt`


def test_an_empty_context_line_is_kept(ws):
    text = ("diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n"
            "@@ -1,3 +1,3 @@\n one\n\n+two\n")
    lines = ws.parse_diff(text)[0].hunks[0].lines
    assert [line.kind for line in lines] == ["context", "context", "added"]
    assert lines[1].text == ""


def test_no_newline_at_end_of_file_is_passed_over(ws):
    text = ("diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n"
            "@@ -1 +1 @@\n-one\n\\ No newline at end of file\n+one\n")
    one = ws.parse_diff(text)[0]
    assert one.added == 1 and one.removed == 1
    assert len(one.hunks[0].lines) == 2


def test_nothing_before_the_first_file_header_is_read(ws):
    assert ws.parse_diff("warning: something\n+not a line\n") == []


def test_a_name_with_a_space_is_read_from_the_marker_lines(ws):
    text = ("diff --git a/my file.md b/my file.md\n"
            "--- a/my file.md\n+++ b/my file.md\n@@ -1 +1 @@\n-a\n+b\n")
    assert ws.parse_diff(text)[0].path == "my file.md"


# --- the whole report --------------------------------------------------------


def test_a_rename_keeps_the_old_name_whole(ws, seeded):
    """git writes the old name as a record of its own, with no status in front
    of it. Treating every record the same cut three characters off it."""
    git(seeded, "mv", "notes.md", "renamed_notes_file.md")
    changed = ws.changed_files(str(seeded))
    assert "renamed_notes_file.md" in changed
    assert "notes.md" in changed


def test_an_untracked_file_is_changed_too(ws, seeded):
    (seeded / "brand-new.txt").write_text("x")
    assert "brand-new.txt" in ws.changed_files(str(seeded))


def test_the_root_is_found_from_a_subdirectory(ws, seeded):
    (seeded / "deep" / "down").mkdir(parents=True)
    assert ws.worktree_root(str(seeded / "deep" / "down")) == str(seeded)


def test_a_session_in_a_subdirectory_sees_the_whole_worktree(ws, seeded):
    """git reports a diff with paths relative to the root whatever directory
    it ran in, so the file list beside it has to be root-relative too."""
    (seeded / "deep").mkdir()
    (seeded / "deep" / "here.txt").write_text("x")
    (seeded / "top.txt").write_text("y")
    report = ws.worktree_diff(str(seeded / "deep"))
    assert report.untracked == ["deep/here.txt", "top.txt"]
    tree = ws.worktree_files(str(seeded / "deep"))
    assert tree.root == str(seeded)
    assert "deep/here.txt" in [one.path for one in tree.files]


def test_a_diff_git_could_not_read_is_not_an_empty_diff(ws, seeded):
    """Saying "nothing changed" when git failed is the one answer a reader
    would act on, and it would be wrong."""
    def broken(args, **rest):
        return None if "diff" in args else ws.run(args, **rest)

    report = ws.worktree_diff(str(seeded), runner=broken)
    assert report.failed is True
    assert all(not section.files for section in report.sections)


def test_a_diff_that_worked_is_not_marked_failed(ws, seeded):
    (seeded / "notes.md").write_text("# notes\n\nchanged\n")
    assert ws.worktree_diff(str(seeded)).failed is False


def test_untracked_files_are_listed_in_name_order(ws, seeded):
    (seeded / "b.md").write_text("b")
    (seeded / "a.md").write_text("a")
    assert ws.untracked_files(str(seeded)) == ["a.md", "b.md"]


def test_a_directory_without_git_has_no_untracked_files(ws, tmp_path):
    assert ws.untracked_files(str(tmp_path)) == []


def test_the_base_falls_back_to_main(ws, seeded):
    assert ws.diff_base(str(seeded)) == "main"


def test_the_base_is_what_the_remote_says(ws, seeded, tmp_path):
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(seeded), str(clone)], check=True,
                   capture_output=True)
    assert ws.diff_base(str(clone)) == "origin/main"


def test_a_repository_without_a_base_says_so(ws, tmp_path):
    root = tmp_path / "fresh"
    root.mkdir()
    git(root, "init", "-q", "-b", "wip")
    assert ws.diff_base(str(root)) == ""


def test_the_branch_work_and_the_uncommitted_work_are_apart(ws, seeded):
    git(seeded, "checkout", "-qb", "side")
    (seeded / "notes.md").write_text("# notes\n\ncommitted\n")
    git(seeded, "commit", "-qam", "second")
    (seeded / "README.md").write_text("# readme\n\nchanged but not committed\n")

    report = ws.worktree_diff(str(seeded))
    assert report.base == "main"
    committed, uncommitted = report.sections
    assert committed.name == "committed"
    assert [one.path for one in committed.files] == ["notes.md"]
    assert uncommitted.name == "uncommitted"
    assert [one.path for one in uncommitted.files] == ["README.md"]


def test_an_untracked_file_is_named_rather_than_left_out(ws, seeded):
    (seeded / "brand-new.md").write_text("# new\n")
    report = ws.worktree_diff(str(seeded))
    assert report.untracked == ["brand-new.md"]
    assert all(not section.files for section in report.sections)


def test_only_so_many_untracked_files_are_named(ws, seeded, monkeypatch):
    monkeypatch.setattr(ws, "UNTRACKED_SHOWN", 3)
    for index in range(10):
        (seeded / f"f{index}.md").write_text("x")
    assert len(ws.worktree_diff(str(seeded)).untracked) == 3


def test_a_diff_that_is_too_long_is_cut(ws, seeded, monkeypatch):
    monkeypatch.setattr(ws, "DIFF_MAX_BYTES", 200)
    (seeded / "notes.md").write_text("\n".join(f"line {n}" for n in range(500)))
    report = ws.worktree_diff(str(seeded))
    assert report.cut is True


def test_a_directory_without_git_reports_nothing(ws, tmp_path):
    report = ws.worktree_diff(str(tmp_path))
    assert report.base == ""
    assert [one.path for section in report.sections for one in section.files] == []


def test_a_missing_directory_reports_nothing(ws):
    assert ws.worktree_diff("/no/such/place").sections == []


def test_a_repository_without_commits_does_not_raise(ws, tmp_path):
    root = tmp_path / "fresh"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "a.md").write_text("# a\n")
    report = ws.worktree_diff(str(root))
    assert report.untracked == ["a.md"]
