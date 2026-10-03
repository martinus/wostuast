"""`tests/perturb.py`, which proves a test by breaking what it guards.

It is a tool, not a test, so nothing else runs it: without these it could
stop working, and a tool that says "red" for a break no test saw is worse
than none -- it is believed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import perturb

HERE = Path(__file__).resolve().parent

MODULE = "def f():\n    # the answer\n    return 1\n"
TEST = "from mod import f\n\n\ndef test_f():\n    assert f() == 1\n\n\ndef test_other():\n    assert True\n"


def run(tmp_path: Path, breaks: list) -> subprocess.CompletedProcess:
    (tmp_path / "mod.py").write_text(MODULE)
    (tmp_path / "test_mod.py").write_text(TEST)
    (tmp_path / "breaks.json").write_text(json.dumps(breaks))
    return subprocess.run(
        [sys.executable, str(HERE / "perturb.py"), "breaks.json"],
        cwd=tmp_path, capture_output=True, text=True, timeout=120)


def test_a_break_a_test_sees_is_red_and_the_file_comes_back(tmp_path):
    done = run(tmp_path, [{"name": "wrong answer", "file": "mod.py",
                           "old": "return 1", "new": "return 2",
                           "tests": ["test_mod.py::test_f"]}])
    assert done.returncode == 0, done.stdout + done.stderr
    assert "red    1 failed, 0 passed" in done.stdout
    assert "1 of 1 breaks proven" in done.stdout
    assert (tmp_path / "mod.py").read_text() == MODULE


def test_a_break_no_test_sees_is_said_and_fails_the_run(tmp_path):
    done = run(tmp_path, [
        {"name": "comment", "file": "mod.py", "old": "the answer",
         "new": "an answer", "tests": ["test_mod.py"]},
        {"name": "nothing chosen", "file": "mod.py", "old": "return 1",
         "new": "return 2", "tests": ["test_mod.py", "-k", "no_such_test"]},
        {"name": "not there", "file": "mod.py", "old": "return 3",
         "new": "return 4", "tests": ["test_mod.py"]},
    ])
    assert done.returncode == 1
    lines = done.stdout.splitlines()
    assert "GREEN  2 passed" in lines[0]
    assert "nothing ran" in lines[1]
    assert "0 times, not once" in lines[2]
    assert "0 of 3 breaks proven" in done.stdout
    assert (tmp_path / "mod.py").read_text() == MODULE


def test_no_bytecode_of_a_break_is_left_behind(tmp_path):
    """Python runs a cached `.pyc` while the source's mtime in whole seconds
    and its size match, and a break that keeps the length keeps the size: a
    break, or the file put back, written in the same second as the one
    before ran the code of the one before. `SEND_MAX = 12000` and then
    `POST_MAX = 64 * 1024`, each six bytes shorter, said GREEN for the
    second. So no bytecode of a break may be left for the next run."""
    import importlib.util

    done = run(tmp_path, [{"name": "same length", "file": "mod.py",
                           "old": "return 1", "new": "return 2",
                           "tests": ["test_mod.py::test_f"]}])
    assert "red    1 failed" in done.stdout, done.stdout + done.stderr
    cached = Path(importlib.util.cache_from_source(str(tmp_path / "mod.py")))
    assert not cached.exists()


def test_only_the_summary_line_is_counted():
    printed = "3 passed in the log of a test\n1 failed, 4 passed in 0.52s\n"
    assert perturb.counts(printed) == (1, 4)
    assert perturb.counts("2 errors in 0.10s") == (2, 0)
    assert perturb.counts("no tests ran in 0.01s") == (0, 0)


HANG = "def test_hangs():\n    import time\n    time.sleep(3600)\n"


def test_a_break_that_hangs_a_test_is_put_back_and_said(tmp_path):
    """A break that makes a test wait for ever is a test with no time limit.
    It hung the run once, and was stopped with `kill`: the break stayed in
    `wostuast`. Now the run stops it, says so, and puts the file back."""
    (tmp_path / "test_hang.py").write_text(HANG)
    done = run(tmp_path, [{"name": "hangs", "file": "mod.py",
                           "old": "return 1", "new": "return 2",
                           "tests": ["test_hang.py"], "timeout": 2}])
    assert done.returncode == 1
    assert "HUNG   past 2 s" in done.stdout, done.stdout + done.stderr
    assert (tmp_path / "mod.py").read_text() == MODULE


def test_a_kill_puts_the_file_back(tmp_path):
    import signal
    import time

    (tmp_path / "mod.py").write_text(MODULE)
    (tmp_path / "test_hang.py").write_text(HANG)
    (tmp_path / "breaks.json").write_text(json.dumps(
        [{"name": "hangs", "file": "mod.py", "old": "return 1",
          "new": "return 2", "tests": ["test_hang.py"]}]))
    running = subprocess.Popen(
        [sys.executable, str(HERE / "perturb.py"), "breaks.json"],
        cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        until = time.monotonic() + 30
        while (tmp_path / "mod.py").read_text() == MODULE:
            assert time.monotonic() < until, "the break was never applied"
            time.sleep(0.05)
        time.sleep(0.5)  # pytest is running the hanging test now
        running.send_signal(signal.SIGTERM)
        running.wait(timeout=30)
    finally:
        running.kill()
    assert (tmp_path / "mod.py").read_text() == MODULE
