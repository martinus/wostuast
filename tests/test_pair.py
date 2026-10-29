"""`tests/pair.py`, before and after in one labelled PNG.

It is a tool, not a test, so nothing else runs it: without this it could
stop working and the first sign would be the next picture a reader waits
for.
"""

from __future__ import annotations

import base64
import struct

import pair
from browser import skip_without_browser

pytestmark = skip_without_browser

#: A PNG of 40 x 30 pixels, one colour, drawn once by Chromium.
SMALL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAACgAAAAeCAIAAADRv8uKAAAALUlEQVR4nOzNMQEAAAQAMIdowski"
    "pQhOz1ZgWdPxIeOJWCwWi8VisVgsFotvCwAA//9Ikgg3AAAABklEQVQDADK+Ae8KLkb2AAAAAElF"
    "TkSuQmCC")


def size(path):
    """A PNG's width and height, off its header."""
    return struct.unpack(">II", path.read_bytes()[16:24])


def test_two_pictures_stand_side_by_side_under_their_labels(tmp_path):
    """Two pictures make one wider than both together, and as tall as one
    with its label; `--clip` cuts each to the part asked for."""
    old, new = tmp_path / "old.png", tmp_path / "new.png"
    old.write_bytes(SMALL)
    new.write_bytes(SMALL)
    assert size(old) == (40, 30)
    out = tmp_path / "pair.png"
    assert pair.main([str(out), f"before={old}", f"after={new}"]) == 0
    width, height = size(out)
    assert width >= 2 * 40 and 30 < height < 30 + 80, (width, height)
    assert pair.main([str(out), f"before={old}", f"after={new}", "--clip", "0,0,10,10"]) == 0
    clipped = size(out)
    assert clipped[0] < width and clipped[1] < height, clipped
    assert "&lt;b&gt;" in pair.page([("<b>", old)], None)
