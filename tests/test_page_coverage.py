"""What the tests reach of the page script (#439): `tests/browser.py`
records it when `WOSTUAST_COVERAGE` is set, and `tests/page_coverage.py`
merges and reports it.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations

import re

import browser
import page_coverage
from browser import opened, skip_without_browser

pytestmark = skip_without_browser


def test_the_coverage_names_what_ran_and_what_never_did(page_at, tmp_path, monkeypatch, capsys):
    """A page that never drew a diff never ran `wordDiff`, and the report
    names it at its line in `wostuast`; a second page that called it adds
    to what the first wrote, and the name goes. The first page alone runs
    `fromShebang`, so a second page written over the first is seen too.
    What other tests of this worker reached is put aside first, or a run of
    the tool itself would find `wordDiff` already run."""
    folder = tmp_path / "coverage"
    monkeypatch.setenv("WOSTUAST_COVERAGE", str(folder))
    monkeypatch.setattr(browser, "_reached", {})
    with opened(page_at) as page:
        page.wait_for_function("state.sessions.length > 0")
        page.evaluate("languageOf('bin/run', '#!/bin/sh', null)")
    first = page_coverage.merge(folder)
    named = {name: did for name, _end, did in first["functions"].values()}
    assert named["drawSessions"] is True
    assert named["fromShebang"] is True
    assert named["wordDiff"] is False
    program = page_coverage.PROGRAM.read_text()
    said = page_coverage.report(first, program)
    ran, counted = map(int, re.match(r"page script: (\d+) of (\d+) lines ran", said[0]).groups())
    assert 0 < ran < counted
    line = next(int(hit[1]) for one in said
                if (hit := re.match(r"  wostuast:(\d+)  wordDiff  ", one)))
    assert program.split("\n")[line - 1].startswith("function wordDiff(")
    # Each name stands on its line: V8 names an arrow after what holds it,
    # and the `PLACE_FIELDS` list's three arrows were listed by its name.
    for hit in filter(None, (re.match(r"  wostuast:(\d+)  (\S+)  ", one) for one in said)):
        assert hit[2] in program.split("\n")[int(hit[1]) - 1], hit[0]

    with opened(page_at) as page:
        page.evaluate("wordDiff('a b', 'a c')")
    second = page_coverage.merge(folder)
    assert {name: did for name, _end, did in second["functions"].values()}["wordDiff"] is True
    # Added to, not written over: the second page never ran `fromShebang`.
    assert second["ran"] > first["ran"]
    assert page_coverage.main(["--from", str(folder)]) == 0
    assert "  wordDiff  " not in capsys.readouterr().out


def test_the_check_fails_on_a_function_no_test_runs(monkeypatch):
    """`--check` (#579) names a function that never ran unless
    `UNRUN_ALREADY` holds it, names an entry that runs now, and fails a
    run that recorded nothing: a shard whose upload went missing must not
    pass with every function unseen."""
    text = "const state = {};\nfunction ran() {}\nfunction idle() {}\n"
    # What ran is every byte before `idle`: its lines alone never ran.
    merged = {"text": text, "ran": set(range(text.index("function idle"))), "functions": {
        text.index("function ran"): ["ran", text.index("function idle") - 1, True],
        text.index("function idle"): ["idle", len(text) - 1, False]}}
    said = page_coverage.check(merged)
    assert len(said) == 1 and said[0].startswith("idle: no browser test runs it")
    monkeypatch.setattr(page_coverage, "UNRUN_ALREADY", frozenset({"idle"}))
    assert page_coverage.check(merged) == []
    monkeypatch.setattr(page_coverage, "UNRUN_ALREADY", frozenset({"idle", "ran"}))
    assert page_coverage.check(merged) == [
        "ran: a test runs it now, so it comes off UNRUN_ALREADY"]
    assert page_coverage.check({"text": "", "ran": set(), "functions": {}})


def test_the_check_counts_the_lines_a_function_that_ran_left_unrun(monkeypatch):
    """A function that ran is not all run (#600): its lines that never ran
    are counted for the innermost named function that holds each -- an
    unnamed handler's for the function it is written in -- and one in no
    function for the top level. Past its allowance, it fails, and says
    which lines."""
    text = ("const state = {};\n"
            "function some() {\n"
            "  if (a) {\n"
            "    b();\n"
            "  }\n"
            "  on(() => {\n"
            "    c();\n"
            "  });\n"
            "  const inner = () => {\n"
            "    e();\n"
            "  };\n"
            "}\n"
            "d();\n")
    def at(piece):
        return text.index(piece)
    lines = text.split("\n")
    ran = set()
    for number in (0, 1, 2, 4, 5, 7, 8, 10, 11):  # all but b(), c(), e() and d()
        start = sum(len(one) + 1 for one in lines[:number])
        ran.update(range(start, start + len(lines[number])))
    merged = {"text": text, "ran": ran, "functions": {
        at("function some"): ["some", at("d();") - 1, True],
        at("() => {"): ["", at("  });") + 3, True],
        at("() => {\n    e"): ["inner", at("  };") + 3, True]}}
    assert page_coverage.unrun_by_function(merged) == {
        "some": [3, 6], "inner": [9], "(top level)": [12]}
    said = page_coverage.check(merged)
    assert said == [
        "(top level): 1 lines no browser test runs, and UNRUN_LINES_ALREADY allows 0: wostuast:13",
        "inner: 1 lines no browser test runs, and UNRUN_LINES_ALREADY allows 0: wostuast:10",
        "some: 2 lines no browser test runs, and UNRUN_LINES_ALREADY allows 0:"
        " wostuast:4, wostuast:7"], said
    allowed = {"some": 2, "inner": 1, "(top level)": 1}
    monkeypatch.setattr(page_coverage, "UNRUN_LINES_ALREADY", allowed)
    assert page_coverage.check(merged) == []
    monkeypatch.setattr(page_coverage, "UNRUN_LINES_ALREADY", {**allowed, "some": 1})
    assert page_coverage.check(merged) == [
        "some: 2 lines no browser test runs, and UNRUN_LINES_ALREADY allows 1:"
        " wostuast:4, wostuast:7"]



def test_nothing_is_recorded_unless_asked(page_at, tmp_path, monkeypatch):
    """Without `WOSTUAST_COVERAGE` a context is Playwright's own: no
    DevTools session, no file, nothing a test could trip on."""
    monkeypatch.delenv("WOSTUAST_COVERAGE", raising=False)
    with opened(page_at) as page:
        assert "new_page" not in vars(page.context)
