"""The shared browser, and the helpers every page test uses.

Playwright is imported only when a browser is actually asked for, because
`conftest` imports this module for its fixtures and the tests that need no
browser must still run without it.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import pytest

CHROMIUM = [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
]

def browser_path() -> str | None:
    for candidate in [os.environ.get("WOSTUAST_CHROME", "")] + CHROMIUM:
        if candidate and Path(candidate).exists():
            return candidate
    return None

# One Playwright and one browser for the whole file. Starting Playwright costs
# 0.43 s and launching Chromium 0.15 s, and there are fifty-odd tests here, so
# half a minute of every run went on starting the same two things again and
# again. A context costs 0.03 s and shares nothing — its own storage, its own
# cookies — so each test is still on its own.
_shared: list = []

def why_no_browser() -> str:
    """Empty when this machine can run the page tests, else the reason."""
    if browser_path() is None:
        return "no browser here"
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return "playwright is not installed"
    return ""


#: Every page test file carries this. The check runs once, at import.
skip_without_browser = pytest.mark.skipif(
    bool(why_no_browser()), reason=why_no_browser() or "a browser is here")


def shared_browser():
    if not _shared:
        from playwright.sync_api import sync_playwright as start_playwright
        play = start_playwright().start()
        _shared.append(play)
        _shared.append(play.chromium.launch(executable_path=browser_path(),
                                            args=["--no-sandbox"]))
    return _shared[1]

MARKED = Path(__file__).resolve().parent / "fixtures" / "marked.min.js"

#: How long any wait may take, in milliseconds, when `WOSTUAST_WAIT` says.
#: Unset, Playwright's own 30 s stands, and the waits here keep their 15 s:
#: a loaded CI runner needs them. Set it while working on one test --
#: `WOSTUAST_WAIT=5000 pytest tests/test_page_x.py -k name` -- and a wait
#: for something that never comes fails in five seconds, not thirty. Three of
#: those cost a minute and a half in one sitting.
WAIT = int(os.environ.get("WOSTUAST_WAIT") or 0) or None

# What each tab has drawn once its first answer has arrived. Waiting for the
# thing itself beats sleeping for long enough: it is both quicker and surer.
# The transcript shares the box with the two split tabs, so "the box has a
# child" is already true while the file columns are still standing in it. It
# has to have stopped being split as well.
DRAWN = {"transcript": ".turnbody > *", "files": ".filebody > *",
         "diff": ".diffbody > *", "commands": ".cmdbody > *"}

HOSTILE = (
    "Read from a README:\n\n"
    '<img src=x onerror="window.PWNED=1">\n'
    "<script>window.PWNED=2</script>\n"
    "[click me](javascript:window.PWNED=3)\n\n"
    "A fence needing a real `>`:\n\n```python\nif len(hits) > 1:\n    raise Ambiguous\n```\n"
)

def fresh_context(scheme="dark", with_marked=True):
    """A context of its own, with everything the page fetches answered from
    here, so that no test needs a network.

    marked gets the real bytes, which means the page's `integrity` hash is
    checked for real on every one of these tests. The highlighter is refused,
    which is what being offline looks like; the tests that want one hand the
    page a stand-in instead. The fonts are answered empty: a stylesheet in the
    head holds up the script after it, and no test looks at a typeface.
    """
    context = shared_browser().new_context(
        viewport={"width": 1440, "height": 900}, color_scheme=scheme)
    if WAIT:
        context.set_default_timeout(WAIT)
    context.route("**/marked.min.js", lambda route: route.fulfill(
        path=str(MARKED), content_type="application/javascript",
        headers={"access-control-allow-origin": "*"})
        if with_marked else route.abort())
    context.route("**/highlight.min.js", lambda route: route.abort())
    context.route("**/fonts.googleapis.com/**", lambda route: route.fulfill(
        status=200, content_type="text/css", body=""))
    return context

@contextmanager
def own_context(scheme="dark", with_marked=True):
    """`fresh_context`, closed when the block ends, whatever the block
    raised. For a test that needs the context before the page: a
    permission, an init script, a route, or two pages (#283)."""
    context = fresh_context(scheme, with_marked)
    try:
        yield context
    finally:
        context.close()

def open_page(where, scheme="dark", with_marked=True, wait="transcript"):
    """A fresh context on the shared browser. What comes back is the context,
    so a test that closes `browser` closes its own and nobody else's.

    It returns once the chosen session's transcript has answered -- with
    blocks, with none, or with a failure -- because a test that read the tab
    the moment the frame was drawn found `.turnbody` missing or empty on a
    loaded machine, and three such tests went red in one session, each
    after its own fix. `wait="frame"` returns at the first draw, for a test
    about what the page does before that answer."""
    browser = fresh_context(scheme, with_marked)
    page = browser.new_page()
    load(page, where, with_marked, wait)
    return browser, page

def load(page, where, with_marked=True, wait="transcript"):
    """Go to `where` in a page that is already open, and wait as
    `open_page` does."""
    url = where[1] if isinstance(where, tuple) else where
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector(".row", timeout=WAIT or 15000)
    # Wait for the first draw rather than for a length of time.
    ready = "document.querySelector('#content > *') !== null"
    if with_marked:
        ready = "!!window.marked && " + ready
    page.wait_for_function(ready, timeout=WAIT or 15000)
    if wait == "transcript":
        page.wait_for_function(
            "!state.chosen || state.tab !== 'transcript' || state.turns.landed",
            timeout=WAIT or 15000)

def wait_for_map(page, rows=1):
    """Wait for the map beside the transcript to have rows in it.

    `open_page` waits for the first draw, and the first draw is the tab's
    frame: the map fills one fetch later, when the transcript arrives. On a
    loaded machine that gap is real, and a test that asked straight away read
    an empty list as "the list drew nothing"."""
    page.wait_for_function(
        "n => document.querySelectorAll("
        "'.filelist.transcript button').length >= n", arg=rows, timeout=WAIT or 15000)

def show_tab(page, name):
    """Open a tab and wait for its first answer, not for a fixed time."""
    page.click(f".tab[data-tab='{name}']")
    page.wait_for_selector(DRAWN[name], timeout=WAIT or 15000)

def rgb(text):
    """The three numbers out of a computed `rgb(r, g, b)` or `rgba(...)`."""
    parts = text[text.index("(") + 1:text.index(")")].replace("/", " ").split(",")
    return [float(one.strip().rstrip("%")) for one in parts[:3]]

def contrast(front, back):
    """WCAG 2.1 contrast, so that "is this readable" is a number, not a look."""
    def light(colour):
        channels = []
        for value in rgb(colour):
            part = value / 255
            channels.append(part / 12.92 if part <= 0.03928
                            else ((part + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
    one, two = light(front), light(back)
    high, low = max(one, two), min(one, two)
    return (high + 0.05) / (low + 0.05)

def daemon_transcript(daemon):
    return daemon.transcript("s1").tail.path


def write_records(daemon, *made):
    """Records from `conftest.record`, onto the session's transcript, unread.

    Every test that wrote these by hand wrote the same JSON again; build
    them with `conftest.record` and write them here. `conftest` is imported
    here, not at the top: it imports this module for its fixtures."""
    import conftest

    with open(daemon_transcript(daemon), "a") as handle:
        handle.write(conftest.records(*made))


def wait_for_watching(daemon, session_id="s1", seconds=15):
    """Wait until the page's stream is listening to one session.

    `wait_for_map` proves the fetch answered; it does not prove the stream is
    subscribed, because `showTab` fetches and *then* calls `resubscribe`. A
    tick in that gap sends to nobody, and no fixture here runs a ticker, so
    the push never comes again and the test waits out its whole timeout.
    The daemon is the only side that knows, so this asks the daemon.
    """
    import time as _time

    until = _time.monotonic() + seconds
    while _time.monotonic() < until:
        if session_id in daemon.hub.watchers():
            return
        _time.sleep(0.02)
    raise AssertionError(f"the page never subscribed to {session_id}")

def settings(page, choice, value):
    """Open the settings menu at the end of the tab row, if it is shut, and
    press one of its choices: `colours`, `tabwidth`, `wrapping`, `sides`."""
    if page.locator("#setpop").is_hidden():
        page.click("#settings")
    page.click(f"#setpop .{choice} button[data-value='{value}']")


def kept(ws, key, want, seconds=15):
    """Wait until `settings.json` holds `want` under `key`. A choice is shown
    at once and written after, by a POST the page does not wait on, so the
    file is the thing to wait for, not the page."""
    import json as _json
    import time as _time

    until = _time.monotonic() + seconds
    held = None
    while _time.monotonic() < until:
        try:
            held = _json.loads(ws.config_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            held = None
        if isinstance(held, dict) and held.get(key) == want:
            return
        _time.sleep(0.02)
    raise AssertionError(f"settings.json never held {key}={want!r}: {held!r}")


def renew_stream(page, act):
    """Run `act` in the page, which opens a new stream, and wait until that
    stream has said its first word.

    `wait_for_watching` cannot see this: the daemon lists a closed stream
    until a write to it fails, so it answered at once, and the next push
    went to the dead socket. The page can: the first word sets `state.live`,
    and the opening comes in the same write."""
    page.evaluate(f"() => {{ state.live = ''; {act}; }}")
    page.wait_for_function("state.live === 'live'", timeout=WAIT or 15000)


def hold(page, pattern, how_many=1):
    """Hold the first `how_many` requests to `pattern`, let the rest through,
    and hand back the list the held ones land in. Never `unroute` with one
    held: it answers the held one itself (.claude/topics/testing.md,
    "Playwright")."""
    held = []
    page.route(pattern, lambda route: held.append(route)
               if len(held) < how_many else route.continue_())
    return held


def wait_until(page, check):
    """Let the page run until `check()` says yes, and fail when it never
    does. `wait_for_function` cannot see a Python list, and a sleep here
    would starve the route handler, which runs while the page waits."""
    for _ in range(750):
        if check():
            return
        page.wait_for_timeout(20)
    raise AssertionError("it never happened")


def stub_send(page, answers=None, delay=0):
    """`/send` after `delay` ms, with every text sent kept in
    `window.__sent`. Answered from `answers`, one per call and the last one
    again after that; with no `answers`, passed on to the daemon, so a send
    is slow but real."""
    page.evaluate("""([answers, delay]) => {
      window.__sent = [];
      const real = window.fetch;
      window.fetch = (url, opts) => {
        if (String(url).endsWith("/send")) {
          window.__sent.push(JSON.parse(opts.body).text);
          if (answers === null) {
            return new Promise((done) => setTimeout(
              () => done(real(url, opts)), delay));
          }
          const body = answers[Math.min(window.__sent.length, answers.length) - 1];
          return new Promise((done) => setTimeout(
            () => done(new Response(JSON.stringify(body))), delay));
        }
        return real(url, opts);
      };
    }""", [answers, delay])


def two_rows(page):
    page.wait_for_function("document.querySelectorAll('.row').length === 2")


def spy_on_note(page):
    """Every word `note` says, kept in `window.__said`. The live slot is
    repainted on every push, so reading `#live` after a keypress is a race;
    this is not (.claude/topics/testing.md, "spy on `note`")."""
    page.evaluate("""() => { window.__said = []; const real = note;
      note = (text, ...rest) => { window.__said.push(text);
                                  return real(text, ...rest); }; }""")

# --- line numbers -----------------------------------------------------------


def numbers(page, under):
    """The two line numbers of every row under a selector.

    They share one element, lined up with spaces: a diff row is monospace and
    already `white-space: pre`, so a flex box and an element per column would
    be three more nodes a line for nothing.
    """
    return page.eval_on_selector_all(
        under + " .dline .ln",
        """els => els.map((e) => [e.textContent.slice(0, 5).trim(),
                                  e.textContent.slice(5, 11).trim()])""")

# --- syntax highlighting ----------------------------------------------------

# The highlighter is fetched, not vendored, so every test here works whether
# or not the machine running it can reach a CDN: the page is handed a stand-in
# and the real download is never started.

#: A stand-in highlighter. The markup given stands for the file's first line
#: and the rest of the file follows verbatim, so the answer has exactly as many
#: lines as the file — which is what a real highlighter returns, and what the
#: page checks before it paints anything.
STUB = """hljsAsked = Promise.resolve({
  getLanguage: () => true,
  highlight: (text, how) => ({
    value: (%s) + text.slice(text.indexOf("\\n")),
  }),
});"""

def open_file(page, name="code.py"):
    """Open a file on the Files tab and wait for its rows.

    Waiting for what the page has drawn, rather than for a length of time, is
    why this is one helper and not four lines in every test.
    """
    show_tab(page, "files")
    page.click(f".filelist button:has-text('{name}')")
    page.wait_for_selector(".filebody .code .dline")


def open_code(page, stub, name="code.py"):
    """The same, with a stand-in highlighter in place first."""
    show_tab(page, "files")
    page.evaluate(STUB % stub)
    open_file(page, name)

# --- the review: milestone 7 stage 1 -----------------------------------------


@contextmanager
def opened(where, scheme="dark", with_marked=True, wait="transcript", *,
           tab=None):
    """A page on the shared browser, in a context of its own, closed when
    the block ends, whatever the block raised.

    `with opened(where) as page:` says what four lines and a level of
    indentation said in nearly every page test: `sync_playwright`,
    `open_page`, `try`, and `finally: browser.close()` (#283). A test that
    forgot the `close` leaked a context. The arguments after `where` are
    `open_page`'s. `tab="diff"` opens the Diff tab and waits for its first
    line. A second page is `page.context.new_page()`;
    a test that needs the context before the page uses `own_context` and
    `load`."""
    browser, page = open_page(where, scheme, with_marked, wait)
    try:
        if tab == "diff":
            show_tab(page, "diff")
            page.wait_for_selector(".dline")
        elif tab is not None:
            raise ValueError(f"opened() knows no tab {tab!r}")
        yield page
    finally:
        browser.close()

# --- the review: milestone 7 stage 2 -----------------------------------------


def _comment_with(page, plus, note):
    """Press the `+` given, write `note` and save it, waiting for each step.

    Every test that hand-rolled this skipped a wait, and the one that did was
    the one test that failed under a full parallel run.
    """
    plus.click(force=True)
    page.wait_for_selector(".commentbox textarea")
    page.fill(".commentbox textarea", note)
    page.click(".commentbox button:text-is('save')")
    page.wait_for_selector(".comment")


def comment_on_line(page, at, note):
    """Write a comment on the row at `at`."""
    _comment_with(page, page.locator(".dline").nth(at).locator(".addnote"), note)


def comment_on_first_line(page, note):
    """Write a comment on the first row that takes one."""
    _comment_with(page, page.locator(".dline .addnote").first, note)

def base_of(in_pane):
    return in_pane[1]


def code_text(page, under=".filebody .code"):
    """What a file body says, without the gutter or the `+` beside each line.

    The body is rows now, so its `inner_text` carries the line numbers and the
    comment buttons too. Only `.dtext` is the file.
    """
    return "\n".join(page.eval_on_selector_all(
        under + " .dline .dtext", "els => els.map((e) => e.textContent)"))
