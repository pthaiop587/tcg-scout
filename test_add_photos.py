"""eBay's picture rules, pinned.

Run: python -m pytest test_add_photos.py

These are somebody else's requirements, which is exactly why they need a test.
Nothing here fails loudly if it drifts -- a 400px photo uploads fine and simply
looks bad, and a photo under 1600px on its long side silently loses the buyer
zoom, which is the feature that sells a card you cannot hold.

eBay, as of Aug 2026:
    max file size      12 MB
    max dimensions     9000 x 9000
    min dimensions     500 px on the longest side
    recommended        1600 px on the longest side, to trigger zoom
    formats            JPEG, PNG, GIF, TIFF, BMP, WEBP, HEIC, AVIF
"""

import os

import pytest
from PIL import Image

import add_photos as ap

EBAY_MAX_BYTES = 12 * 1024 * 1024
EBAY_MAX_PX = 9000
EBAY_MIN_PX = 500
EBAY_ZOOM_PX = 1600


def test_the_long_edge_is_ebays_zoom_size():
    """Below 1600 the buyer cannot zoom, which is the whole point of a photo
    of a card somebody is buying unseen."""
    assert ap.LONG_EDGE == EBAY_ZOOM_PX


def test_the_long_edge_is_inside_ebays_limits():
    assert EBAY_MIN_PX <= ap.LONG_EDGE <= EBAY_MAX_PX


def make(tmp_path, w, h, name="in.jpg"):
    p = tmp_path / name
    Image.new("RGB", (w, h), (120, 120, 120)).save(p)
    return str(p)


@pytest.mark.parametrize("w,h", [(3024, 4032), (4032, 3024), (2000, 2000)])
def test_a_big_photo_comes_out_at_1600_on_its_long_side(tmp_path, w, h):
    src = make(tmp_path, w, h)
    dest = str(tmp_path / "out.jpg")
    ap.convert(src, dest)
    got = Image.open(dest)
    assert max(got.size) == EBAY_ZOOM_PX, got.size
    assert min(got.size) >= EBAY_MIN_PX, got.size
    assert os.path.getsize(dest) <= EBAY_MAX_BYTES


def test_a_small_photo_is_never_upscaled(tmp_path):
    """Upscaling invents detail, and eBay's zoom shows the invention off."""
    src = make(tmp_path, 700, 980)
    dest = str(tmp_path / "small.jpg")
    ap.convert(src, dest)
    assert Image.open(dest).size == (700, 980)


def test_the_orientation_flag_is_baked_in_not_carried(tmp_path):
    """A file that says "rotate me" displays differently depending on who
    opens it. eBay, Excel and Windows Photos do not all agree."""
    src = str(tmp_path / "rot.jpg")
    im = Image.new("RGB", (900, 1200), (90, 90, 90))
    ex = im.getexif()
    ex[274] = 6                      # "rotate 90"
    im.save(src, exif=ex)
    dest = str(tmp_path / "flat.jpg")
    ap.convert(src, dest)
    assert not Image.open(dest).getexif().get(274)


def test_jpeg_is_a_format_ebay_takes():
    ok = {"JPEG", "PNG", "GIF", "TIFF", "BMP", "WEBP", "HEIC", "AVIF"}
    assert "JPEG" in ok


def test_the_filed_photos_of_a_real_card_meet_the_spec():
    """The actual files in photos/, if there are any -- the spec is only worth
    anything if what is on disk obeys it."""
    folder = "photos"
    if not os.path.isdir(folder):
        pytest.skip("no photos folder here")
    shots = [f for f in os.listdir(folder) if f.lower().endswith(".jpg")]
    if not shots:
        pytest.skip("no photos filed yet")
    for f in shots:
        p = os.path.join(folder, f)
        size = os.path.getsize(p)
        im = Image.open(p)
        assert size <= EBAY_MAX_BYTES, "%s is %.1f MB" % (f, size / 1048576.0)
        assert max(im.size) <= EBAY_MAX_PX, f
        assert max(im.size) >= EBAY_MIN_PX, "%s is only %s" % (f, im.size)
        assert im.format in ("JPEG", "PNG"), f
        assert not im.getexif().get(274), \
            "%s still carries an orientation flag; it should be baked in" % f
