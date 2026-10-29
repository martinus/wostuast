#!/usr/bin/env python3
"""Put pictures side by side, each under its label, in one PNG.

    python3 tests/pair.py OUT.png before=OLD.png after=NEW.png
                          [--clip X,Y,WIDTH,HEIGHT] [--scale 2]

Not a test. The reader says yes to a change of how the page looks on a
picture of before and after, in one PNG, labelled (topics/working). The
container has no PIL, and a script for it was written from nothing, and
mended twice, in one session (#650, #651). `--clip` is the part of each
picture shown, in its own pixels: a row of the sidebar, the transcript
pane. The pictures are drawn by Chromium, as every other picture here is.
"""

from __future__ import annotations

import argparse
import base64
import html
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def page(pictures: list[tuple[str, Path]], clip: tuple[int, int, int, int] | None) -> str:
    """The HTML of the pictures in a row, each under its label, cut to
    `clip` when one is given."""
    cells = []
    for label, path in pictures:
        data = base64.b64encode(path.read_bytes()).decode()
        image = f'<img src="data:image/png;base64,{data}"'
        if clip:
            x, y, width, height = clip
            image = (f'<div style="width:{width}px;height:{height}px;overflow:hidden">'
                     f'{image} style="display:block;margin:-{y}px 0 0 -{x}px"></div>')
        else:
            image += ' style="display:block">'
        cells.append(f"<figure><figcaption>{html.escape(label)}</figcaption>{image}</figure>")
    return ("<!doctype html><body style='margin:0;padding:12px;background:#111;color:#eee;"
            "font:15px sans-serif;display:flex;gap:24px;align-items:flex-start;width:max-content'>"
            "<style>figure{margin:0}figcaption{margin:0 0 8px}</style>"
            + "".join(cells) + "</body>")


def main(argv: list[str]) -> int:
    ask = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ask.add_argument("out")
    ask.add_argument("pictures", nargs="+", help="LABEL=PATH, in the order shown")
    ask.add_argument("--clip", type=lambda text: tuple(int(one) for one in text.split(",")))
    ask.add_argument("--scale", type=float, default=1)
    said = ask.parse_args(argv)
    pictures = []
    for one in said.pictures:
        label, _, path = one.partition("=")
        if not path:
            ask.error(f"{one}: give it as LABEL=PATH")
        pictures.append((label, Path(path)))

    sys.path.insert(0, str(HERE))
    # The tests' own Chromium: a second Playwright in a process that runs
    # one already refuses to start.
    from browser import shared_browser
    context = shared_browser().new_context(device_scale_factor=said.scale)
    try:
        shown = context.new_page()
        shown.set_content(page(pictures, said.clip))
        shown.wait_for_function("[...document.images].every((one) => one.complete)")
        shown.locator("body").screenshot(path=said.out)
    finally:
        context.close()
    print(said.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
