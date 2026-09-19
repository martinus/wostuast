"""Light and dark, contrast, and motion.

See tests/browser.py for the shared browser and the helpers."""

from __future__ import annotations


import pytest

import conftest
from browser import (
    skip_without_browser,
    sync_playwright,
    fresh_context,
    open_page,
    contrast,
)

pytestmark = skip_without_browser

def test_both_themes_are_readable(page_at):
    """PLAN.md section 5.2 asks for a light theme from the start."""
    with sync_playwright() as play:
        seen = {}
        for scheme in ("dark", "light"):
            browser, page = open_page(play, page_at, scheme)
            try:
                seen[scheme] = (
                    page.evaluate("getComputedStyle(document.body).backgroundColor"),
                    page.evaluate(
                        "getComputedStyle(document.querySelector('.prose pre code'))"
                        ".color"),
                )
            finally:
                browser.close()
        assert seen["dark"][0] != seen["light"][0], "the light theme did not apply"
        assert seen["dark"][1] != seen["light"][1], "code would be unreadable"


def test_a_search_hit_can_be_read_in_both_themes(page_at):
    """The mark sat on the amber with near-black text. In the light theme the
    amber is a dark brown, so near-black on it could not be read at all."""
    with sync_playwright() as play:
        for scheme in ("dark", "light"):
            browser, page = open_page(play, page_at, scheme)
            try:
                page.locator("#find").fill("pytest")
                page.wait_for_selector("mark")
                seen = page.evaluate(
                    "() => { const s = getComputedStyle(document.querySelector('mark'));"
                    " return [s.color, s.backgroundColor]; }")
                assert contrast(*seen) >= 4.5, f"{scheme}: {seen} is {contrast(*seen):.1f}:1"
            finally:
                browser.close()


def test_less_motion_stops_everything_moving(page_at):
    """One switch, so a reader who asked their system for less motion does not
    have to be told about each thing on this page that moves."""
    with sync_playwright() as play:
        browser, page = open_page(play, page_at)
        try:
            # In seconds, whatever unit the browser reports them in.
            moving = ("() => getComputedStyle(document.querySelector('.row'))"
                      ".transitionDuration.split(', ').map((one) => parseFloat(one))")
            assert max(page.evaluate(moving)) > 0.05
            page.emulate_media(reduced_motion="reduce")
            assert max(page.evaluate(moving)) < 0.01
        finally:
            browser.close()


def test_the_colours_can_be_switched_and_are_remembered(page_at):
    """The light values used to live inside a media query, so choosing light on
    a dark machine could not work at all."""
    daemon, path = page_at
    with sync_playwright() as play:
        browser = fresh_context(play)
        try:
            page = browser.new_page()
            page.goto(path, wait_until="domcontentloaded")
            page.wait_for_selector(".row", timeout=15000)
            dark = page.evaluate("getComputedStyle(document.body).backgroundColor")
            assert page.locator("#theme").inner_text() == "auto"

            page.locator("#theme").click()           # auto -> light
            page.wait_for_timeout(150)
            light = page.evaluate("getComputedStyle(document.body).backgroundColor")
            assert light != dark, "light on a dark machine did nothing"
            assert page.locator("#theme").inner_text() == "light"

            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector(".row", timeout=15000)
            assert page.evaluate(
                "getComputedStyle(document.body).backgroundColor") == light
            assert page.locator("#theme").inner_text() == "light"

            page.locator("#theme").click()           # light -> dark
            page.locator("#theme").click()           # dark -> auto
            page.wait_for_timeout(150)
            assert page.locator("#theme").inner_text() == "auto"
            assert page.evaluate(
                "getComputedStyle(document.body).backgroundColor") == dark
        finally:
            browser.close()
