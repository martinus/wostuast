"""The Files tab and the Diff tab, read from real repositories."""

from __future__ import annotations

import contextlib
import os
import pathlib
import subprocess
import time

import pytest

from conftest import git_in as git


class _Reading:
    """`os.scandir` is a context manager as well as an iterator, and the
    counting stand-in has to be both."""

    def __init__(self, walking):
        self.walking = walking

    def __iter__(self):
        return self.walking

    def __enter__(self):
        return self

    def __exit__(self, *gone):
        return False

    def close(self):
        self.walking.close()


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


def test_a_small_ignored_directory_is_listed(ws, seeded):
    """An agent writes its plan and its notes into an ignored directory, and
    that is the one ignored place a reader wants to read. git collapses such
    a directory to one entry and looks no further; wostuast walks it, as long
    as it is small enough to be a place somebody reads."""
    (seeded / ".gitignore").write_text("build/\n")
    (seeded / "build").mkdir()
    (seeded / "build" / "out.md").write_text("# out\n")
    tree = ws.worktree_files(str(seeded))
    paths = [one.path for one in tree.files]
    assert "build/out.md" in paths
    assert ".gitignore" in paths
    assert tree.skipped == []


def test_the_named_files_come_first(ws, seeded):
    (seeded / "PLAN.md").write_text("# plan\n")
    (seeded / "CLAUDE.md").write_text("# claude\n")
    paths = [one.path for one in ws.worktree_files(str(seeded)).files]
    assert paths[:3] == ["PLAN.md", "CLAUDE.md", "README.md"]


def test_the_order_sent_does_not_move_when_a_file_changes(ws, seeded):
    """The page holds these names between polls and asks for them again only
    when the tag has moved. An order that also depended on what had changed
    would move every time an agent saved anything, and the whole list would
    come down the wire again. Where a changed file sits in the list the reader
    sees is the page's business; tests/test_page.py holds that."""
    (seeded / "a-first-by-name.txt").write_text("quiet\n")
    git(seeded, "add", "."), git(seeded, "commit", "-qm", "quiet")
    before = [one.path for one in ws.worktree_files(str(seeded)).files]

    (seeded / "notes.md").write_text("# notes\n\ntouched\n")
    after = ws.worktree_files(str(seeded))
    assert [one.path for one in after.files] == before
    assert ws.listing_tag("\0".join(one.path for one in after.files)) == \
        ws.listing_tag("\0".join(before))
    # It is still marked, and its time is still read, so the page can lift it.
    touched = [one for one in after.files if one.path == "notes.md"][0]
    assert touched.changed is True
    assert touched.mtime > 0


def test_the_rest_are_sent_in_name_order(ws, seeded):
    (seeded / "a-first-by-name.txt").write_text("quiet\n")
    paths = [one.path for one in ws.worktree_files(str(seeded)).files]
    assert paths[0] == "README.md"                 # pinned, so it still wins
    assert paths[1:] == sorted(paths[1:])


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


def test_an_ignored_directory_too_big_to_walk_is_one_name(ws, seeded,
                                                          monkeypatch):
    """`node_modules` holds more files than the repository does, and it is not
    a place to browse. It comes back as its own name and nothing else, so the
    tree can draw one row saying so."""
    monkeypatch.setattr(ws, "IGNORED_MAX", 3)
    (seeded / ".gitignore").write_text("node_modules/\n")
    (seeded / "node_modules").mkdir()
    for index in range(5):
        (seeded / "node_modules" / f"m{index}.js").write_text("x")
    tree = ws.worktree_files(str(seeded))
    paths = [one.path for one in tree.files]
    assert not [one for one in paths if one.startswith("node_modules")]
    assert tree.skipped == ["node_modules"]


def test_one_folder_too_big_does_not_cost_the_rest_of_the_directory(
        ws, seeded, monkeypatch):
    """The whole point. `.oa-implement` holds a plan, some notes and a build
    root of a hundred thousand objects. The build root is one row; the plan
    and the notes are listed, because what is left of the directory fits."""
    monkeypatch.setattr(ws, "IGNORED_MAX", 3)
    (seeded / ".gitignore").write_text(".oa-implement/\n")
    (seeded / ".oa-implement" / "_build_root_c2").mkdir(parents=True)
    (seeded / ".oa-implement" / "notes").mkdir()
    (seeded / ".oa-implement" / "PLAN.md").write_text("# plan\n")
    (seeded / ".oa-implement" / "notes" / "one.md").write_text("# one\n")
    for index in range(20):
        (seeded / ".oa-implement" / "_build_root_c2" / f"o{index}.o").write_text("x")
    tree = ws.worktree_files(str(seeded))
    paths = [one.path for one in tree.files]
    assert ".oa-implement/PLAN.md" in paths
    assert ".oa-implement/notes/one.md" in paths
    assert not [one for one in paths if "_build_root_c2" in one]
    assert tree.skipped == [".oa-implement/_build_root_c2"]


def test_the_walk_stops_at_the_budget_however_big_the_directory_is(ws,
                                                                   tmp_path,
                                                                   monkeypatch):
    """A build root of a hundred thousand objects must cost the budget in
    reads and not a hundred thousand, or the thing this walk was added for --
    browsing without waiting -- is the thing it breaks."""
    big = tmp_path / "build"
    big.mkdir()
    for index in range(500):
        (big / f"o{index}.o").write_text("x")

    read = 0
    real = os.scandir

    def counting(where):
        def walking():
            nonlocal read
            with real(where) as entries:
                for entry in entries:
                    read += 1
                    yield entry
        return contextlib.closing(_Reading(walking()))

    monkeypatch.setattr(os, "scandir", counting)
    names, skipped = ws.walk_ignored(str(tmp_path), "build", 10)
    assert names == [] and skipped == ["build"]
    # The budget, the entry that broke it, and nothing like five hundred.
    assert read <= 12, read


def test_a_directory_link_is_not_followed(ws, tmp_path):
    """It is a way round the budget and a way into a loop. The file it points
    at is listed where it really is."""
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "one.txt").write_text("one\n")
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "big.txt").write_text("big\n")
    (tmp_path / "build" / "out").symlink_to(tmp_path / "elsewhere")
    names, skipped = ws.walk_ignored(str(tmp_path), "build", 100)
    assert sorted(names) == ["build/one.txt"]
    assert skipped == []


def test_a_directory_that_cannot_be_read_is_not_a_failure(ws, tmp_path):
    """A generated directory can go while we are walking it, and a walk that
    raised would take the whole listing with it."""
    (tmp_path / "build").mkdir()
    names, skipped = ws.walk_ignored(str(tmp_path), "build/gone", 10)
    assert names == [] and skipped == []


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


def test_a_file_in_a_directory_too_big_to_list_is_still_readable(ws, seeded,
                                                                monkeypatch):
    """The listing and the guard answer different questions. One is "is this
    worth drawing", the other is "is this safe to open", and a file left out
    of a crowded folder is as safe as any other in the tree — so a link to
    one, or a file an agent has just touched, still opens."""
    monkeypatch.setattr(ws, "IGNORED_MAX", 3)
    (seeded / ".gitignore").write_text("build/\n")
    (seeded / "build").mkdir()
    for index in range(5):
        (seeded / "build" / f"out{index}.txt").write_text("out\n")
    tree = ws.worktree_files(str(seeded))
    paths = [one.path for one in tree.files]
    assert not [one for one in paths if one.startswith("build/")]
    assert "build/" not in paths
    assert tree.skipped == ["build"]
    assert ws.read_worktree_file(str(seeded), "build/out1.txt").text == "out\n"


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


def test_a_form_feed_inside_a_line_does_not_split_it(ws):
    """`str.splitlines()` breaks on a form feed, a vertical tab, `\x1c`-`\x1e`
    and `\u0085`. All of them are legal inside a source line and git does not
    escape any of them — it only quotes paths. Every line after one counted
    one too high, so the Diff tab's numbers were wrong, the Files tab (which
    splits on `\n`) disagreed with it, and a review comment anchored to a line
    nobody commented on."""
    text = ("diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n"
            "@@ -1,4 +1,4 @@\n aaa\n bbb\x0c ccc\n ddd\n-eee\n+CHANGED\n")
    one = ws.parse_diff(text)[0]
    lines = one.hunks[0].lines
    assert [line.kind for line in lines] == [
        "context", "context", "context", "removed", "added"]
    assert lines[1].text == "bbb\x0c ccc"
    assert one.added == 1 and one.removed == 1


def test_a_form_feed_does_not_double_a_removed_line(ws):
    """The same split, counted: `-alpha\x0cbeta` was two removed lines."""
    text = ("diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n"
            "@@ -1 +1 @@\n-alpha\x0c-beta\n+one\n")
    one = ws.parse_diff(text)[0]
    assert one.removed == 1
    assert one.hunks[0].lines[0].text == "alpha\x0c-beta"


def test_a_quoted_path_comes_back_as_the_name_git_lists(ws):
    """`core.quotePath=false` only stops the quoting of bytes above 0x80. A
    path holding a quote, a backslash or a control character is quoted
    whatever that says, and the `a/` prefix goes inside the quotes — so
    `rpartition(" b/")` found nothing, the name was mangled, and a plain edit
    was reported as a rename because the two mangled sides differed."""
    text = ('diff --git "a/we\\"ird.txt" "b/we\\"ird.txt"\n'
            '--- "a/we\\"ird.txt"\n'
            '+++ "b/we\\"ird.txt"\n'
            "@@ -1 +1 @@\n-one\n+two\n")
    one = ws.parse_diff(text)[0]
    assert one.path == 'we"ird.txt'
    assert one.old_path == 'we"ird.txt'
    assert one.status == "modified"


def test_a_quoted_rename_keeps_both_names(ws):
    text = ('diff --git "a/back\\\\slash.txt" "b/we\\"ird.txt"\n'
            "similarity index 100%\n"
            'rename from "back\\\\slash.txt"\n'
            'rename to "we\\"ird.txt"\n')
    one = ws.parse_diff(text)[0]
    assert one.old_path == "back\\slash.txt"
    assert one.path == 'we"ird.txt'
    assert one.status == "renamed"


def test_an_octal_escape_in_a_path_is_one_byte(ws):
    """git writes a byte it will not print as `\\ooo`, one byte at a time, so
    two of them make one character."""
    assert ws.unquote_path(r'"a/\303\244.txt"') == "a/\u00e4.txt"
    assert ws.unquote_path(r'"a/tab\there"') == "a/tab\there"
    assert ws.unquote_path("plain.txt") == "plain.txt"
    assert ws.unquote_path('"unfinished') == '"unfinished'


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
    """git fails outside a repository, and `git_names` reports that as None.
    The caller above turns it into "nothing is untracked" only where it knows
    the directory is one — here it is the honest answer."""
    assert ws.untracked_files(str(tmp_path)) is None


def test_the_base_falls_back_to_main(ws, seeded):
    assert ws.diff_base(str(seeded)) == ("main", False)


def test_the_base_is_what_the_remote_says(ws, seeded, tmp_path):
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(seeded), str(clone)], check=True,
                   capture_output=True)
    assert ws.diff_base(str(clone)) == ("origin/main", False)


def test_a_repository_without_a_base_says_so(ws, tmp_path):
    root = tmp_path / "fresh"
    root.mkdir()
    git(root, "init", "-q", "-b", "wip")
    assert ws.diff_base(str(root)) == ("", False)


def test_an_origin_head_that_points_nowhere_is_not_the_base(ws, seeded, tmp_path):
    """The remote renamed its default branch and `fetch --prune` took the
    old one away: `origin/HEAD` still names `origin/master`, which is gone,
    and `symbolic-ref` prints it all the same. Taken as the base, every
    diff and log against it failed, and the tab said "git did not answer"
    for ever with `origin/main` right there."""
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(seeded), str(clone)], check=True,
                   capture_output=True)
    # A default branch that is none of the usual names is still the answer.
    git(clone, "update-ref", "refs/remotes/origin/trunk", "HEAD")
    git(clone, "symbolic-ref", "refs/remotes/origin/HEAD",
        "refs/remotes/origin/trunk")
    assert ws.diff_base(str(clone)) == ("origin/trunk", False)
    git(clone, "update-ref", "-d", "refs/remotes/origin/trunk")
    git(clone, "symbolic-ref", "refs/remotes/origin/HEAD",
        "refs/remotes/origin/master")
    assert ws.diff_base(str(clone)) == ("origin/main", False)
    # A clone carries no identity of its own, and CI has no global one.
    git(clone, "config", "user.email", "t@example.com")
    git(clone, "config", "user.name", "t")
    git(clone, "checkout", "-qb", "feat")
    (clone / "x.txt").write_text("x\n")
    git(clone, "add", ".")
    git(clone, "commit", "-qm", "x")
    report = ws.worktree_diff(str(clone))
    assert report.failed is False and report.base == "origin/main"
    assert [one.subject for one in report.commits] == ["x"]


def test_a_base_git_could_not_look_for_is_not_no_base(ws, seeded):
    """`for-each-ref` giving nothing because it failed was read as "no such
    names": the committed half went, the page said there was no default
    branch, and nothing said git had not answered."""
    def broken(args, **rest):
        return None if "for-each-ref" in args else ws.run(args, **rest)

    assert ws.diff_base(str(seeded), runner=broken) == ("", True)
    assert ws.worktree_diff(str(seeded), runner=broken).failed is True


def test_a_root_git_could_not_find_is_not_an_empty_worktree(ws, seeded):
    """With `--show-toplevel` timed out the report came back empty and
    unfailed, and the page said nothing had changed. `worktree_files` asks
    `git_answers` at that door already."""
    def stalled(args, **rest):
        return None
    report = ws.worktree_diff(str(seeded), runner=stalled)
    assert report.failed is True
    # And a directory that simply is not a repository is still an answer.
    assert ws.worktree_diff(str(seeded.parent)).failed is False


def test_a_repository_with_no_commit_yet_shows_what_is_staged(ws, tmp_path):
    """With no HEAD, `git log HEAD` and `git diff HEAD` fail -- which is git
    answering "there is no commit", not failing to answer. The tab said git
    did not answer on every poll, and the staged files were in neither list:
    not in the diff, and not untracked, because they are in the index."""
    root = tmp_path / "fresh"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "main.py").write_text("print(1)\n")
    git(root, "add", "main.py")
    report = ws.worktree_diff(str(root))
    assert report.failed is False
    uncommitted = [one for one in report.sections if one.name == "uncommitted"][0]
    assert [(one.path, one.status) for one in uncommitted.files] == [
        ("main.py", "added")]
    whole = ws.whole_file_diff(str(root), "uncommitted", "main.py")
    assert whole.failed is False and whole.file is not None


def test_a_carriage_return_inside_a_line_stays_in_that_line(ws, seeded):
    """`subprocess.run(text=True)` reads with universal newlines, so a lone
    CR became a line break before `parse_diff` saw it -- the form-feed scar,
    by another road. Every line after it was numbered one too high, and the
    Files tab, which reads the bytes, disagreed."""
    (seeded / "cr.txt").write_bytes(b"a\nb = 1\r c = 2\nc\nd\ne\ng\n")
    git(seeded, "add", ".")
    git(seeded, "commit", "-qm", "cr")
    (seeded / "cr.txt").write_bytes(b"a\nb = 1\r c = 2\nc\nd\ne\nG\n")
    report = ws.worktree_diff(str(seeded))
    one = [f for f in report.sections[-1].files if f.path == "cr.txt"][0]
    kinds = [line.kind for hunk in one.hunks for line in hunk.lines]
    assert kinds.count("added") == 1 and kinds.count("removed") == 1
    # Line 6 on disk, counted from the hunk's own header.
    start = int(one.hunks[0].header.split("+")[1].split(",")[0])
    before = [line.kind for line in one.hunks[0].lines].index("added")
    olds = [line for line in one.hunks[0].lines[:before] if line.kind != "added"]
    assert start + len([l for l in olds if l.kind == "context"]) == 6


def test_a_name_with_a_space_is_the_name_the_files_tab_lists(ws, seeded):
    """git writes a TAB after a `---`/`+++` name that holds a space, for GNU
    patch. It stayed on the path, so the Diff tab said `foo bar.txt\\t` and
    the Files tab `foo bar.txt`: one line with two anchors, and no hidden
    lines to show."""
    (seeded / "foo bar.txt").write_text("one\n")
    git(seeded, "add", ".")
    git(seeded, "commit", "-qm", "space")
    (seeded / "foo bar.txt").write_text("two\n")
    report = ws.worktree_diff(str(seeded))
    assert [one.path for one in report.sections[-1].files] == ["foo bar.txt"]
    assert report.sections[-1].files[0].status == "modified"
    assert ws.whole_file_diff(str(seeded), "uncommitted", "foo bar.txt").file


def test_a_folder_ending_in_b_does_not_make_a_rename(ws, seeded):
    """A binary change and a mode change have no `---`/`+++` lines, so the
    path is what the `diff --git` line gives -- and splitting it at the last
    ` b/` read `a/Plan b/logo.png b/Plan b/logo.png` as a rename to
    `logo.png`, at the root."""
    (seeded / "Plan b").mkdir()
    (seeded / "Plan b" / "logo.png").write_bytes(b"\x89PNG\x00\x01")
    (seeded / "Plan b" / "run.sh").write_text("echo\n")
    git(seeded, "add", ".")
    git(seeded, "commit", "-qm", "plan b")
    (seeded / "Plan b" / "logo.png").write_bytes(b"\x89PNG\x00\x02")
    (seeded / "Plan b" / "run.sh").chmod(0o755)
    report = ws.worktree_diff(str(seeded))
    got = sorted((one.path, one.old_path, one.status)
                 for one in report.sections[-1].files)
    assert got == [("Plan b/logo.png", "Plan b/logo.png", "modified"),
                   ("Plan b/run.sh", "Plan b/run.sh", "modified")], got


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


# --- the listings the daemon holds ------------------------------------------


def test_one_listing_is_shared_rather_than_read_again(ws, seeded):
    """Asking git costs a third of a second over fifty thousand files, and the
    tab asks again every couple of seconds."""
    asked = []

    def count(args, **rest):
        asked.append(args)
        return ws.run(args, **rest)

    files = ws.Files()
    first = files.of(str(seeded), runner=count)
    assert first.tree.files
    listings = len([one for one in asked if "ls-files" in one])
    assert listings == 3           # tracked, untracked, ignored

    again = files.of(str(seeded), runner=count)
    assert again is first
    assert len([one for one in asked if "ls-files" in one]) == listings


def test_a_stale_listing_is_handed_over_and_read_again_behind(ws, seeded):
    """Only a worktree nobody has asked about yet makes anyone wait."""
    files = ws.Files()
    first = files.of(str(seeded))
    root = ws.worktree_root(str(seeded))
    files.held[root].read_at -= ws.LIST_FRESH + 1

    (seeded / "later.md").write_text("later\n")
    stale = files.of(str(seeded))
    assert stale is first          # the old answer, handed over at once
    for _ in range(60):
        time.sleep(0.1)
        if files.held[root] is not first:
            break
    names = [one.path for one in files.held[root].tree.files]
    assert "later.md" in names, "it was not read again behind"


def test_the_tag_follows_the_names_and_not_the_changes(ws, seeded):
    files = ws.Files()
    first = files.of(str(seeded))
    root = ws.worktree_root(str(seeded))

    # Changing a file that is already listed leaves the names alone.
    (seeded / "notes.md").write_text("# notes\n\nedited\n")
    files.held[root].read_at -= ws.LIST_FRESH + 1
    with files.gate(root):
        touched = files.read(root, ws.run)
    assert touched.tag == first.tag
    assert "notes.md" in [one.path for one in touched.tree.files if one.changed]

    # Adding one moves it.
    (seeded / "brand-new.md").write_text("new\n")
    with files.gate(root):
        added = files.read(root, ws.run)
    assert added.tag != first.tag


def test_a_listing_nobody_asks_about_is_dropped(ws, seeded):
    files = ws.Files()
    files.of(str(seeded))
    assert files.held
    files.forget(older_than=1000.0)      # nothing is that old yet
    assert files.held
    files.forget(older_than=0.0)
    assert not files.held


# --- what `file` makes of a name that gives nothing away ---------------------


def test_file_names_a_language_the_suffix_could_not(ws, repo):
    """A Python module with no shebang and no suffix. The name says nothing and
    the first line says nothing, so `file` is the only thing left that knows."""
    (repo / "helper").write_text("import os\n\n\nclass Thing:\n    def go(self):\n"
                                 "        return {'a': 1}\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "a module")
    found = ws.read_worktree_file(str(repo), "helper")
    assert found is not None
    assert found.language == "python"


def test_a_suffix_is_never_asked_about(ws, repo):
    """`file` is a subprocess. A name that already answers must not pay for it,
    so the runner is watched rather than the answer."""
    (repo / "code.py").write_text("print(1)\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "py")
    asked = []

    def watched(cmd, **rest):
        asked.append(cmd)
        return ws.run(cmd, **rest)

    found = ws.read_worktree_file(str(repo), "code.py", runner=watched)
    assert found is not None and found.language == ""
    assert not any(cmd[0] == "file" for cmd in asked), "a suffix paid for a subprocess"


def test_rust_and_go_are_not_called_c(ws, repo):
    """Measured: libmagic answers `text/x-c` for both, and for C. Painting Rust
    as C is a confident lie, and no paint beats a wrong one. A real C file with
    no suffix is rare; a Rust one mislabelled would be read wrong."""
    (repo / "rusty").write_text('fn main() {\n    println!("hi");\n}\n')
    (repo / "gopher").write_text('package main\n\nimport "fmt"\n\n'
                                 'func main() { fmt.Println("x") }\n')
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "two")
    for name in ("rusty", "gopher"):
        found = ws.read_worktree_file(str(repo), name)
        assert found is not None
        assert found.language == "", f"{name} was given a language it is not"


def test_a_machine_without_file_simply_gets_no_answer(ws):
    """Two kinds of nothing, told apart. Both paint nothing on the page; only
    one of them is worth asking again."""
    nowhere = pathlib.Path("/etc/hostname")
    # It did not answer.
    assert ws.sniff_language(nowhere, runner=lambda cmd: None) is None
    assert ws.sniff_language(nowhere, runner=lambda cmd: "") is None
    # It answered, and the answer is not one we paint.
    assert ws.sniff_language(
        nowhere, runner=lambda cmd: "application/x-unknown-thing") == ""


def test_a_shebang_is_not_worth_a_subprocess(ws, repo):
    """The page reads a shebang itself, and a shebang is the common shape for
    a file with no suffix. Asking `file` about one forks for an answer already
    in hand — and the open file is re-read on every poll."""
    (repo / "runme").write_text("#!/usr/bin/env python3\nimport os\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "a script")
    asked = []

    def watched(cmd, **rest):
        asked.append(cmd)
        return ws.run(cmd, **rest)

    found = ws.read_worktree_file(str(repo), "runme", runner=watched)
    assert found is not None and found.language == ""
    assert not any(cmd[0] == "file" for cmd in asked), "a shebang paid for a fork"


# --- what reading the open file costs -----------------------------------------


def counting(ws, seen):
    """A runner that records the command and then really runs it."""
    real = ws.run

    def run(args, **rest):
        seen.append(str(args[0]))
        return real(args, **rest)

    return run


def test_reading_the_open_file_asks_once_per_version_of_it(ws, repo):
    """The Files tab asks every two seconds. Three processes per ask — two git
    and one `file` — is ninety a minute for one reader sitting on one file.
    Two of the three answer questions that cannot have changed."""
    (repo / "deploy").write_text("import os\n")     # no suffix, and no shebang
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "seed")
    held = ws.Files()
    seen = []
    run = counting(ws, seen)

    ws.read_worktree_file(str(repo), "deploy", runner=run, held=held)
    first = list(seen)
    assert sum(one == "file" for one in first) == 1

    seen.clear()
    for _ in range(4):
        ws.read_worktree_file(str(repo), "deploy", runner=run, held=held)
    assert "file" not in seen, "`file` was asked again for the same bytes"
    assert len(seen) == 4, f"one process per poll, not {len(seen) / 4}"


def test_a_name_git_does_not_offer_is_refused_however_often_it_is_asked(ws, repo):
    """`is_listed` is the check that the page asked for a name git offers, and
    it is the one thing here that is never remembered.

    The file has to stay on disk for this to mean anything. An earlier version
    used `git rm`, which deletes it as well — so the read was refused by
    `target.is_file()` and the test passed with `is_listed` stubbed to yes. It
    guarded nothing.

    `.git/config` is the honest case, and it is the one that matters: it is on
    disk, it is inside the worktree so `inside` lets it through, and it can
    hold credentials. `is_listed` is the only thing between the page and it.
    An ignored file is not the case to use — the Files tab lists those, so git
    does offer them.
    """
    held = ws.Files()
    seen = []
    run = counting(ws, seen)

    assert (repo / ".git" / "config").is_file(), "there is something to refuse"
    for _ in range(3):
        assert ws.read_worktree_file(str(repo), ".git/config",
                                     runner=run, held=held) is None
    # Asked every time, not answered from something remembered.
    assert sum(one == "git" for one in seen) >= 3


def test_a_git_failure_is_not_remembered_as_an_answer(ws, repo):
    """`git rev-parse` has a two second timeout, and a busy machine can pass
    it. Keeping the empty answer meant one such moment left the worktree
    unreadable until the daemon was restarted."""
    (repo / "a.txt").write_text("hi\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "seed")
    held = ws.Files()
    real = ws.run
    failed = []

    def flaky(args, **rest):
        if "rev-parse" in args and not failed:
            failed.append(1)               # one timeout, and then git is fine
            return None
        return real(args, **rest)

    assert ws.read_worktree_file(str(repo), "a.txt", runner=flaky, held=held) is None
    found = ws.read_worktree_file(str(repo), "a.txt", runner=flaky, held=held)
    assert found is not None, "one failed call, and the worktree stayed broken"
    assert found.text == "hi\n"


def test_file_not_answering_is_asked_again_next_time(ws, repo):
    """"`file` said nothing we paint" and "`file` did not answer" look the same
    on the page and are not the same thing to remember."""
    (repo / "deploy").write_text("import os\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "seed")
    held = ws.Files()
    real = ws.run
    asked = []

    def flaky(args, **rest):
        if args[0] == "file":
            asked.append(1)
            return None if len(asked) == 1 else "text/x-shellscript"
        return real(args, **rest)

    ws.read_worktree_file(str(repo), "deploy", runner=flaky, held=held)
    found = ws.read_worktree_file(str(repo), "deploy", runner=flaky, held=held)
    assert len(asked) == 2, "a call that failed was remembered as an answer"
    assert found.language == "bash"


def test_a_file_that_changes_is_asked_about_again(ws, repo):
    (repo / "deploy").write_text("import os\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "seed")
    held = ws.Files()
    seen = []
    run = counting(ws, seen)

    ws.read_worktree_file(str(repo), "deploy", runner=run, held=held)
    seen.clear()
    time.sleep(0.02)
    (repo / "deploy").write_text("#!/bin/sh\necho other\n")
    ws.read_worktree_file(str(repo), "deploy", runner=run, held=held)
    # This one has a shebang, so nothing asks `file` at all — the page reads
    # it. Give it one without, and the answer is asked for again.
    time.sleep(0.02)
    (repo / "deploy").write_text("import sys\nimport os\n")
    seen.clear()
    ws.read_worktree_file(str(repo), "deploy", runner=run, held=held)
    assert "file" in seen, "different bytes are a different question"


def test_the_remembered_answers_do_not_grow_without_end(ws):
    held = ws.Files()
    for n in range(ws.LANGS_KEPT + 20):
        held.langs[f"/w/f{n}\n0\n0"] = ""
    # An answer, not a failure: a call that did not answer is never kept, so
    # it would never reach the eviction at all.
    held.language_of(pathlib.Path("/w/new"), 1.0, 1,
                     lambda args, **rest: "text/x-shellscript")
    assert len(held.langs) <= ws.LANGS_KEPT


# --- a file the page shows as it is ------------------------------------------


def test_a_picture_comes_back_as_its_own_bytes(ws, seeded):
    import conftest
    raw = conftest.tiny_png()
    (seeded / "logo.png").write_bytes(raw)
    git(seeded, "add", "."), git(seeded, "commit", "-qm", "logo")
    found = ws.read_worktree_bytes(str(seeded), "logo.png")
    assert found == (raw, "image/png")


def test_the_type_comes_from_the_name_and_nothing_else(ws, seeded):
    """The list is what this route will serve, and it is read off the end of
    the name. Reading the bytes to decide instead would let a file an agent
    wrote pick its own type on the origin that holds the token."""
    import conftest
    (seeded / "shot.png").write_bytes(b"GIF89a" + conftest.tiny_png())
    git(seeded, "add", "."), git(seeded, "commit", "-qm", "shot")
    found = ws.read_worktree_bytes(str(seeded), "shot.png")
    assert found is not None and found[1] == "image/png"


def test_only_a_name_on_the_list_is_served(ws, seeded):
    """Everything else is refused outright — an SVG among them, because it is
    a document: a script inside one served from this origin could read the
    page and the token in it."""
    for name, body in (("page.html", b"<b>hi</b>"), ("draw.svg", b"<svg/>"),
                       ("notes.txt", b"words"), ("blob.bin", b"\0\0")):
        (seeded / name).write_bytes(body)
    git(seeded, "add", "."), git(seeded, "commit", "-qm", "sundry")
    for name in ("page.html", "draw.svg", "notes.txt", "blob.bin"):
        assert ws.read_worktree_bytes(str(seeded), name) is None, name


def test_the_same_two_checks_guard_the_bytes(ws, seeded, tmp_path):
    """It goes through `worktree_target`, like every other read, so a name
    git does not offer and a path out of the worktree are refused here too.
    Open the path directly instead and all four of these come back."""
    import conftest
    raw = conftest.tiny_png()
    (seeded / ".git" / "hidden.png").write_bytes(raw)   # git offers no name here
    (tmp_path / "secret.png").write_bytes(raw)
    seeded.joinpath("out.png").symlink_to(tmp_path / "secret.png")
    git(seeded, "add", "-A"), git(seeded, "commit", "-qm", "a link out")
    for name in (".git/hidden.png", "../secret.png", "/etc/hosts.png",
                 "out.png", "nothere.png"):
        assert ws.read_worktree_bytes(str(seeded), name) is None, name


def test_a_picture_too_big_to_show_is_not_read(ws, seeded, monkeypatch):
    """The daemon reads a file whole, and a worktree can hold a gigabyte of
    video."""
    import conftest
    monkeypatch.setattr(ws, "SHOWN_MAX_BYTES", 32)
    (seeded / "logo.png").write_bytes(conftest.tiny_png())   # 69 bytes
    git(seeded, "add", "."), git(seeded, "commit", "-qm", "logo")
    assert ws.read_worktree_bytes(str(seeded), "logo.png") is None
    monkeypatch.setattr(ws, "SHOWN_MAX_BYTES", 4096)
    assert ws.read_worktree_bytes(str(seeded), "logo.png") is not None


def test_a_log_git_failed_on_is_not_a_commit_gone(ws, seeded):
    """`branch_commits` giving None emptied the list, the picked sha was not
    in it, and the report said `gone`: the pane read "probably amended or
    rebased away", and the pick was dropped for good."""
    git(seeded, "checkout", "-qb", "feat")
    (seeded / "x.txt").write_text("x\n")
    git(seeded, "add", ".")
    git(seeded, "commit", "-qm", "x")
    sha = ws.worktree_diff(str(seeded)).commits[0].sha

    def broken(args, **rest):
        return None if "log" in args else ws.run(args, **rest)

    report = ws.worktree_diff(str(seeded), runner=broken, of=sha)
    assert report.failed is True
    assert report.gone == ""


def backport(seeded):
    """`release` cut from main, each moved on, and `fix` cut from release.
    The release branch carries a commit main does not, which is what makes
    main the wrong base: against it, that commit reads as the agent's."""
    git(seeded, "branch", "release")
    (seeded / "later.txt").write_text("on main after the release\n")
    git(seeded, "add", ".")
    git(seeded, "commit", "-qm", "main moves on")
    git(seeded, "checkout", "-q", "release")
    (seeded / "hotfix.txt").write_text("only on the release branch\n")
    git(seeded, "add", ".")
    git(seeded, "commit", "-qm", "release hotfix")
    git(seeded, "checkout", "-qb", "fix", "release")
    (seeded / "fix.txt").write_text("the backported fix\n")
    git(seeded, "add", ".")
    git(seeded, "commit", "-qm", "the fix")


def test_a_backport_is_measured_against_the_branch_it_was_cut_from(ws, seeded):
    """Measured against `main`, a branch cut from a release branch showed
    every commit the release lacks as though the agent had made it."""
    backport(seeded)
    report = ws.worktree_diff(str(seeded))
    assert report.base == "release" and report.base_auto == "release"
    assert [one.subject for one in report.commits] == ["the fix"]
    committed = [one for one in report.sections if one.name == "committed"][0]
    assert [one.path for one in committed.files] == ["fix.txt"]
    assert report.bases[:2] == ["release", "main"], report.bases
    # Picked by the reader, main shows the release's own commit too.
    against_main = ws.worktree_diff(str(seeded), base="main")
    assert [one.subject for one in against_main.commits] == [
        "the fix", "release hotfix"]


def test_a_base_the_page_names_is_used_only_if_git_listed_it(ws, seeded):
    """The pick arrives in `?base=` and the page is input: a name git did
    not list never reaches an argv."""
    backport(seeded)
    assert ws.worktree_diff(str(seeded), base="main").base == "main"
    seen = []

    def spy(args, **rest):
        seen.append(list(args))
        return ws.run(args, **rest)

    for asked in ("--output=/tmp/x", "HEAD~1", "release;rm"):
        report = ws.worktree_diff(str(seeded), runner=spy, base=asked)
        assert report.base == "release", asked
        assert not any(asked in part for argv in seen for part in argv), asked


def test_a_git_that_cannot_rank_falls_back_to_the_usual_names(ws, seeded):
    """`%(ahead-behind)` needs git 2.41. Before that the base is what it
    always was: `origin/HEAD` if it points at something, then the usual
    names."""
    backport(seeded)

    def old(args, **rest):
        if any("ahead-behind" in part for part in args):
            return None
        return ws.run(args, **rest)

    assert ws.diff_base(str(seeded), runner=old) == ("main", False)
