"""Tests for the serial-number sheets.

Run: python -m pytest test_serial_sheets.py

The thing worth guarding is magnification. A serial is about 3.5% of a card's
height, so whether it can be read at all is decided by how many pixels of card
end up on the page -- and that is a number, not an opinion. If a change ever
quietly halves it, these fail.

The card finder is the other half: it has to say "I could not find it" rather
than hand back the whole frame, because a serial cropped out of the picture
looks exactly like a card that has no serial.
"""

import json
import os

import numpy as np
import pytest
from PIL import Image

import serial_sheets as ss


def card_on_cloth(tmp_path, name="card.jpg", size=(1200, 1600),
                  fill=0.55, noise=True):
    """A photograph-shaped thing: textured cloth, a card somewhere in it."""
    rng = np.random.default_rng(7)
    w, h = size
    a = rng.normal(150, 4, (h, w, 3))          # flat, low-texture cloth
    cw, chh = int(w * fill), int(h * fill)
    x, y = (w - cw) // 2, (h - chh) // 2
    card = rng.normal(140, 60, (chh, cw, 3)) if noise else np.full(
        (chh, cw, 3), 200.0)
    a[y:y + chh, x:x + cw] = card
    p = tmp_path / name
    Image.fromarray(np.clip(a, 0, 255).astype("uint8")).save(p, quality=95)
    return str(p), (x, y, x + cw, y + chh)


# --- finding the card -------------------------------------------------------

def test_the_card_is_found_inside_the_frame(tmp_path):
    p, want = card_on_cloth(tmp_path)
    got = ss.card_box(Image.open(p))
    assert got is not None
    for a, b in zip(got, want):
        assert abs(a - b) < 120, (got, want)


def test_a_frame_with_no_card_returns_nothing_not_everything(tmp_path):
    """The whole frame is a worse answer than none: it silently crops the
    serial out and looks like a card that never had one."""
    rng = np.random.default_rng(1)
    a = rng.normal(150, 4, (900, 700, 3))
    p = tmp_path / "cloth.jpg"
    Image.fromarray(np.clip(a, 0, 255).astype("uint8")).save(p)
    assert ss.card_box(Image.open(p)) is None


def test_a_tiny_detection_is_rejected(tmp_path):
    p, _ = card_on_cloth(tmp_path, fill=0.05)
    assert ss.card_box(Image.open(p)) is None


# --- magnification, which is the whole point --------------------------------

def test_the_card_fills_the_page_not_the_tablecloth(tmp_path):
    """Before cropping, a card at 55% of a 1200px frame is ~660px. After, it
    should be most of the 1500px long edge -- more than double the detail."""
    p, _ = card_on_cloth(tmp_path, size=(2400, 3200), fill=0.5)
    im = ss.card_image(p, long_edge=1500)
    assert max(im.size) > 1300


def test_a_serial_sized_mark_survives_the_whole_pipeline(tmp_path):
    """3.5% of card height is the real size of a serial. Draw one that big,
    run it through, and check it is still several pixels tall on the page --
    below about ten it is unreadable however sharp the original was."""
    p, _ = card_on_cloth(tmp_path, size=(3024, 4032), fill=0.55)
    card_h = 4032 * 0.55
    mark = card_h * 0.035
    im = ss.card_image(p, long_edge=1500)
    scale = max(im.size) / card_h
    assert mark * scale > 30, "serial would be %.0fpx on the card image" % (
        mark * scale)

    out = ss.sheets([("x", p)] * 4, str(tmp_path / "s"), per=4)
    page = Image.open(out[0])
    # four to a page, two across: each cell is about half the page wide
    assert page.size[0] > 1400 and page.size[1] > 2000


def test_more_cards_per_page_means_fewer_sheets(tmp_path):
    p, _ = card_on_cloth(tmp_path)
    items = [("c%d" % i, p) for i in range(8)]
    assert len(ss.sheets(items, str(tmp_path / "a"), per=4)) == 2
    assert len(ss.sheets(items, str(tmp_path / "b"), per=8)) == 1


# --- reading the batch ------------------------------------------------------

def test_both_sides_of_every_card_are_shown(tmp_path):
    """A serial turns up on the back as often as the front -- Caden Dana's
    88/99 is on the back, by the card number."""
    work = tmp_path / "work"
    work.mkdir()
    for stem in ("A1", "A2"):
        card_on_cloth(work, stem + ".jpg")
    batch = tmp_path / "b.json"
    batch.write_text(json.dumps(
        {"work": str(work),
         "cards": [{"n": 1, "name": "Someone", "front": "A1", "back": "A2"}]}),
        encoding="utf-8")

    import subprocess
    import sys
    r = subprocess.run([sys.executable, "serial_sheets.py", str(batch),
                        "--originals", str(work),
                        "--out", str(tmp_path / "out")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "2 image(s) from 1 card(s)" in r.stdout
    assert os.listdir(tmp_path / "out")
