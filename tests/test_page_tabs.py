"""Moving between the four tabs.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations


import pytest

import conftest
from browser import (
    skip_without_browser,
    sync_playwright,
    DRAWN,
    open_page,
    show_tab,
)

pytestmark = skip_without_browser

def test_a_key_for_a_tab_that_does_not_exist_does_nothing(page_at):
    """`showTab` only takes a name TABS knows, so a key past the last tab
    changes nothing. There are four; there is no `5`."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            turns = page.locator(".turn").count()
            page.keyboard.press("5")
            page.wait_for_timeout(200)
            assert page.locator(".tab[data-tab='transcript']").get_attribute(
                "aria-selected") == "true"
            assert page.locator(".turn").count() == turns
        finally:
            browser.close()


def test_a_number_key_picks_a_tab_that_is_built(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            page.keyboard.press("2")
            page.wait_for_timeout(500)
            assert page.locator(".tab[data-tab='files']").get_attribute(
                "aria-selected") == "true"
            assert page.locator(".filelist").count() == 1
            page.keyboard.press("1")
            page.wait_for_timeout(500)
            assert page.locator(".turn").count() >= 2
        finally:
            browser.close()


def test_the_find_box_sits_above_the_file_list(repo_page):
    """One box, moved to where it is used. Two would be two values to keep in
    step, and `/` would have to guess which one it meant."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            assert page.eval_on_selector(
                "#find", "el => el.parentElement.id") == "findhome"
            show_tab(page, "files")
            assert page.eval_on_selector(
                "#find", "el => el.parentElement.className") == "findslot"
            assert page.eval_on_selector(
                "#find", "el => el.closest('.side') !== null")
            # and it goes back when a tab without a list is chosen
            show_tab(page, "transcript")
            assert page.eval_on_selector(
                "#find", "el => el.parentElement.id") == "findhome"
        finally:
            browser.close()


def test_the_find_box_keeps_focus_while_you_type(repo_page):
    """It is moved only when its parent is wrong. Re-homing it on every draw
    would detach it mid-keystroke and drop the caret."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.click("#find")
            page.keyboard.type("note", delay=60)
            page.wait_for_timeout(400)
            assert page.evaluate("document.activeElement.id") == "find"
            assert page.input_value("#find") == "note"
        finally:
            browser.close()


def test_the_diff_tab_gets_the_box_too(repo_page):
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "diff")
            assert page.eval_on_selector(
                "#find", "el => el.parentElement.className") == "findslot"
        finally:
            browser.close()


def test_a_tab_comes_back_after_visiting_the_transcript(repo_page):
    """The content box says which tab built it, and `split` rebuilds when that
    is another tab. The transcript emptied the box without saying so, and the
    next Files draw believed its columns were still there."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            for name in ("files", "diff"):
                show_tab(page, name)
                assert page.locator(".filelist button").count() > 0
                show_tab(page, "transcript")
                assert page.locator(".filelist").count() == 0
                show_tab(page, name)
                assert page.locator(".filelist button").count() > 0, name
                assert page.eval_on_selector(
                    "#find", "el => el.parentElement.className") == "findslot"
        finally:
            browser.close()


def test_every_tab_is_built(page_at):
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            for name in ("transcript", "files", "diff", "review"):
                assert not page.locator(f".tab[data-tab='{name}']").is_disabled()
        finally:
            browser.close()


# --- moving between tabs ----------------------------------------------------

def test_every_way_from_one_tab_to_another_works(repo_page):
    """There is one find box and it lives inside the content box on a split
    tab. A tab that empties that box without giving it back destroys it, and
    then `showTab` throws on the next `$("find")` — before it reaches `load`,
    so the tab never loads, and every switch after it throws as well. The page
    stayed broken until a reload. The Peek tab did exactly this before it
    was removed, and this test is what it left behind.
    """
    names = list(DRAWN)
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            blew_up = []
            page.on("pageerror", lambda error: blew_up.append(str(error)))
            for one in names:
                for other in names:
                    if one == other:
                        continue
                    show_tab(page, one)
                    show_tab(page, other)
                    assert page.locator(DRAWN[other]).count() > 0, \
                        f"{one} to {other} drew nothing"
                    assert not blew_up, blew_up
            # and the find box is still there, still working. On the Files
            # tab that means the list of places opens under it; the tree
            # behind it is not what answers.
            show_tab(page, "files")
            page.fill("#find", "code")
            page.wait_for_selector(".goto button")
            assert page.eval_on_selector_all(
                ".goto button", "els => els.map(e => e.title)") == ["code.py"]
            assert not blew_up, blew_up
        finally:
            browser.close()


def test_switching_tabs_faster_than_they_load_still_lands(repo_page):
    """Each tab asks the daemon and draws when the answer comes. Clicking
    through them faster than that must still leave the last one drawn."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            blew_up = []
            page.on("pageerror", lambda error: blew_up.append(str(error)))
            for name in ["files", "diff", "review", "transcript", "review",
                         "files", "transcript", "diff", "review", "files"]:
                page.click(f".tab[data-tab='{name}']")
                page.wait_for_timeout(110)      # quicker than a human, on purpose
            page.wait_for_selector(DRAWN["files"], timeout=15000)
            assert page.evaluate("$('content').dataset.tab") == "files"
            assert not blew_up, blew_up
        finally:
            browser.close()


def test_a_transcript_push_during_a_tab_switch_stays_out_of_the_other_tab(
        repo_page):
    """`showTab` sets `state.tab` and then awaits `load()`. During that await
    the box still belongs to the tab before it, and the push's guard read
    `state.tab` — so a turn was appended as a fourth column of the Files tab.

    `draw()` already asks the box which tab owns it. This does too."""
    with sync_playwright() as play:
        browser, page = open_page(play, repo_page)
        try:
            show_tab(page, "files")
            page.wait_for_selector(".filebody")
            before = page.evaluate(
                """() => [...document.getElementById('content').children]
                           .map((node) => node.className)""")

            # The exact pair an arriving transcript performs, in the window
            # where the tab has been picked and its body has not been drawn.
            page.evaluate("""() => {
              state.tab = 'transcript';
              patchTranscript([state.blocks.length]);
              state.tab = 'files';
            }""")
            after = page.evaluate(
                """() => [...document.getElementById('content').children]
                           .map((node) => node.className)""")
            assert after == before
        finally:
            browser.close()
