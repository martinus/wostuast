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

@contextmanager
def sync_playwright():
    """The shared browser, in the shape the tests already ask for it."""
    yield shared_browser()

MARKED = Path(__file__).resolve().parent / "fixtures" / "marked.min.js"

# What each tab has drawn once its first answer has arrived. Waiting for the
# thing itself beats sleeping for long enough: it is both quicker and surer.
# The transcript shares the box with the two split tabs, so "the box has a
# child" is already true while the file columns are still standing in it. It
# has to have stopped being split as well.
DRAWN = {"transcript": "#content:not(.split) > *", "files": ".filebody > *",
         "diff": ".diffbody > *", "peek": ".peek"}

HOSTILE = (
    "Read from a README:\n\n"
    '<img src=x onerror="window.PWNED=1">\n'
    "<script>window.PWNED=2</script>\n"
    "[click me](javascript:window.PWNED=3)\n\n"
    "A fence needing a real `>`:\n\n```python\nif len(hits) > 1:\n    raise Ambiguous\n```\n"
)

def fresh_context(play, scheme="dark", with_marked=True):
    """A context of its own, with everything the page fetches answered from
    here, so that no test needs a network.

    marked gets the real bytes, which means the page's `integrity` hash is
    checked for real on every one of these tests. The highlighter is refused,
    which is what being offline looks like; the tests that want one hand the
    page a stand-in instead. The fonts are answered empty: a stylesheet in the
    head holds up the script after it, and no test looks at a typeface.
    """
    context = play.new_context(viewport={"width": 1440, "height": 900},
                               color_scheme=scheme)
    context.route("**/marked.min.js", lambda route: route.fulfill(
        path=str(MARKED), content_type="application/javascript",
        headers={"access-control-allow-origin": "*"})
        if with_marked else route.abort())
    context.route("**/highlight.min.js", lambda route: route.abort())
    context.route("**/fonts.googleapis.com/**", lambda route: route.fulfill(
        status=200, content_type="text/css", body=""))
    return context

def open_page(play, where, scheme="dark", with_marked=True):
    """A fresh context on the shared browser. What comes back is the context,
    so a test that closes `browser` closes its own and nobody else's."""
    url = where[1] if isinstance(where, tuple) else where
    browser = fresh_context(play, scheme, with_marked)
    page = browser.new_page()
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector(".row", timeout=15000)
    # Wait for the first draw rather than for a length of time.
    ready = "document.querySelector('#content > *') !== null"
    if with_marked:
        ready = "!!window.marked && " + ready
    page.wait_for_function(ready, timeout=15000)
    return browser, page

def show_tab(page, name):
    """Open a tab and wait for its first answer, not for a fixed time."""
    page.click(f".tab[data-tab='{name}']")
    page.wait_for_selector(DRAWN[name], timeout=15000)

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

def two_rows(page):
    page.wait_for_function("document.querySelectorAll('.row').length === 2")

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

STUB = """hljsAsked = Promise.resolve({
  getLanguage: () => true,
  highlight: (text, how) => ({ value: %s }),
});"""

def open_code(page, stub, name="code.py"):
    """Put a stand-in highlighter in place, then open a file that is not
    Markdown."""
    show_tab(page, "files")
    page.evaluate(STUB % stub)
    page.click(f".filelist button:has-text('{name}')")
    page.wait_for_timeout(400)

# --- the review: milestone 7 stage 1 -----------------------------------------


def open_diff(play, where):
    """The Diff tab of a real repository, drawn."""
    browser, page = open_page(play, where)
    show_tab(page, "diff")
    page.wait_for_selector(".dline")
    return browser, page

# --- the review: milestone 7 stage 2 -----------------------------------------


def comment_on_first_line(page, note):
    page.locator(".dline .plus").first.click(force=True)
    page.wait_for_selector(".commentbox textarea")
    page.fill(".commentbox textarea", note)
    page.click(".commentbox .verb")
    page.wait_for_selector(".comment")

def base_of(in_pane):
    return in_pane[1]
