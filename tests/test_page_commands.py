"""The Commands view (#367, #411): every skill and command your sessions
can run, to read and to put into a send box. A view, not a tab: most
commands belong to no session.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations

import time

import conftest
from browser import HOSTILE, opened, skip_without_browser, spy_on_note

pytestmark = skip_without_browser

ROWS = ("() => [...document.querySelectorAll('.filelist.commands .cmdrow .name')]"
        ".map((n) => n.textContent)")
HEADS = ("() => [...document.querySelectorAll('.filelist.commands .head')]"
         ".map((n) => n.textContent)")


def skill(base, name, about, body=""):
    """A skill under a `.claude` directory, as `tests/fixtures/commands` has."""
    folder = base / "skills" / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {about}\nargument-hint: [number]\n---\n{body}")


def ran(daemon, name):
    """The session's transcript says `/name` was run."""
    path = daemon.store.sessions["s1"].transcript_path
    with open(path, "a") as handle:
        handle.write(conftest.records(conftest.record(
            "you", f"<command-name>/{name}</command-name>"
                   f"<command-message>{name}</command-message>"
                   "<command-args></command-args>")))


def on_the_view(page, by_key=True):
    if by_key:
        page.keyboard.press("4")
    else:                       # the focus is in a box, where 4 is a 4
        page.click("#cmdlink")
    page.wait_for_function("state.feed === 'commands'")
    page.wait_for_selector(".filelist.commands .cmdrow")


def test_a_command_is_listed_read_and_put_into_the_send_box(ws, in_pane, tmp_path):
    """The list in its groups; the chosen one's hint and its text drawn as
    Markdown, through the scrub, because a skill in a worktree is a file
    any agent there can write; and "use" puts it into the send box on the
    Transcript tab and types nothing."""
    daemon, base, seen = in_pane
    skill(tmp_path / ".claude", "review-pr", "Review a pull request",
          "# Review\n\nCheck **every** file.\n\n" + HOSTILE)
    ran(daemon, "clear")
    with opened((None, base)) as page:
        on_the_view(page)
        # Yours and the built-ins first, then each project under its name,
        # and no tab: a tab belongs to one session (#411).
        project = page.evaluate("projectName(state.sessions[0])")
        assert project
        assert page.evaluate(HEADS) == ["built in, or no longer on disk", project]
        assert page.evaluate(ROWS) == ["/clear", "/review-pr"]
        assert page.locator(".tab[data-tab='commands']").count() == 0
        assert not page.is_visible(".tabs .tab")
        page.click(".cmdrow:has-text('/review-pr')")
        page.wait_for_selector(".cmdbody .prose h1")
        assert page.text_content(".cmdbody .cmdname") == "/review-pr"
        assert page.text_content(".cmdbody .cmdhint") == "[number]"
        assert page.text_content(".cmdbody .prose strong") == "every"
        # Asked of the DOM, not of `window.PWNED` alone: an `onerror`
        # fires later than this line runs.
        assert page.locator(".cmdbody [onerror], .cmdbody script,"
                            " .cmdbody a[href^='javascript']").count() == 0
        assert page.evaluate("window.PWNED") is None
        assert page.get_attribute(".cmdrow:has-text('/review-pr')", "class") \
            == "cmdrow chosen"
        page.click(".cmdhead .verb")
        page.wait_for_function("state.tab === 'transcript' && !state.feed")
        assert page.input_value("#say") == "/review-pr "
        assert page.evaluate("document.activeElement.id") == "say"
        assert not conftest.into_pane(seen)


def test_use_keeps_what_was_typed_and_replaces_a_command(ws, in_pane, tmp_path):
    """A draft stays, after the command; a command already at the start of
    the box is the one replaced, as the `/` list replaces one."""
    daemon, base, seen = in_pane
    skill(tmp_path / ".claude", "review-pr", "Review a pull request")
    with opened((None, base)) as page:
        page.fill("#say", "/clear the draft")
        on_the_view(page, by_key=False)
        page.click(".cmdrow:has-text('/review-pr')")
        page.wait_for_selector(".cmdhead .verb")
        page.click(".cmdhead .verb")
        page.wait_for_function("state.tab === 'transcript'")
        assert page.input_value("#say") == "/review-pr the draft"
        assert not conftest.into_pane(seen)


def test_the_find_box_narrows_the_commands(ws, in_pane, tmp_path):
    daemon, base, _ = in_pane
    skill(tmp_path / ".claude", "review-pr", "Review a pull request")
    skill(tmp_path / ".claude", "deploy", "Deploy it")
    with opened((None, base)) as page:
        on_the_view(page)
        page.click("#find")
        page.keyboard.type("dep")
        page.wait_for_function(f"({ROWS})().length === 1")
        assert page.evaluate(ROWS) == ["/deploy"]
        assert page.text_content(".listnote").startswith("1 command of 2")


def test_a_built_in_says_no_file_describes_it(ws, in_pane):
    daemon, base, _ = in_pane
    ran(daemon, "compact")
    with opened((None, base)) as page:
        on_the_view(page)
        page.click(".cmdrow:has-text('/compact')")
        # Not the first `.note`: "reading…" is one too, and under load it
        # was the one read.
        page.wait_for_selector(".cmdbody .note:has-text('no file says what it does')")
        assert "Used 1 time." in page.text_content(".cmdbody .note")


def test_use_on_a_session_nothing_can_be_typed_into_says_why(ws, no_pane, tmp_path):
    """The send box is not there for it, so the view stays and says so."""
    daemon, base = no_pane
    skill(tmp_path / ".claude", "review-pr", "Review a pull request")
    with opened((None, base)) as page:
        spy_on_note(page)
        on_the_view(page)
        page.click(".cmdrow:has-text('/review-pr')")
        page.wait_for_selector(".cmdhead .verb")
        page.click(".cmdhead .verb")
        page.wait_for_function("window.__said.length > 0")
        assert "not in tmux" in page.evaluate("window.__said")[-1]
        assert page.evaluate("state.feed") == "commands"


def test_the_view_keeps_the_command_it_had_chosen(ws, in_pane, tmp_path):
    """Chosen, left for the session, and come back to: the same command,
    as a file stays open on the Files tab. `4` goes there and back, as the
    view's button does."""
    daemon, base, _ = in_pane
    skill(tmp_path / ".claude", "review-pr", "Review a pull request", "Body.\n")
    with opened((None, base)) as page:
        on_the_view(page)
        page.click(".cmdrow:has-text('/review-pr')")
        page.wait_for_selector(".cmdbody .prose")
        page.keyboard.press("4")
        page.wait_for_function("!state.feed && state.tab === 'transcript'")
        page.keyboard.press("4")
        page.wait_for_selector(".cmdbody .prose")
        assert page.text_content(".cmdbody .cmdname") == "/review-pr"


def test_a_project_command_is_used_in_a_session_of_that_project(ws, in_pane, tmp_path):
    """Each project's commands under its own name; "use" on one the chosen
    session cannot see goes to a session that can, and types there. The
    names are in the reading face, not the fixed one (#414)."""
    daemon, base, seen = in_pane
    skill(tmp_path / ".claude", "review-pr", "Review a pull request")
    other = tmp_path.parent / (tmp_path.name + "-other")
    (other / ".claude").mkdir(parents=True)
    skill(other / ".claude", "deploy", "Deploy it")
    ws.append_event(conftest.event("SessionStart", sid="s2", cwd=str(other),
                                   pane="%2", pid=1, ts=time.time()))
    daemon.store.refresh()
    with opened((None, base)) as page:
        page.wait_for_function("state.sessions.length === 2")
        page.click('.row[data-id="s1"]')
        page.wait_for_function("state.chosen === 's1'")
        on_the_view(page)
        page.wait_for_selector(".cmdrow:has-text('/deploy')")
        heads = page.evaluate(HEADS)
        assert len(heads) == 2 and heads[0] != heads[1], heads
        face = page.evaluate("""() => [getComputedStyle(document.querySelector(
            '.filelist.commands .cmdrow .name')).fontFamily,
            getComputedStyle(document.documentElement).getPropertyValue('--mono')]""")
        assert "mono" not in face[0].lower() and face[0] != face[1].strip(), face
        page.click(".cmdrow:has-text('/deploy')")
        page.wait_for_selector(".cmdhead .verb")
        assert "mono" not in page.evaluate(
            "getComputedStyle(document.querySelector('.cmdname')).fontFamily").lower()
        page.click(".cmdhead .verb")
        page.wait_for_function("state.chosen === 's2' && !state.feed")
        assert page.input_value("#say") == "/deploy "
