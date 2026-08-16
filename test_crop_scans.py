"""Tests for the scan cropper.

Run: python -m pytest test_crop_scans.py

The one that matters most is reading order. add_photos.py --assign maps files
onto SKUs in filename order, so if the crops came out in whatever order the
contours were found, a batch would file photos onto the wrong cards -- and a
wrong photo on a listing is a return, not a typo.
"""

import numpy as np
import pytest

import crop_scans as cs

DPI = 300
PAGE = (int(11 * DPI), int(8.5 * DPI))       # letter, portrait, in pixels
CARD = (int(2.5 * DPI), int(3.5 * DPI))      # a card, w x h


def blank_page(shade=245):
    """A scanner lid: near white, with the noise a real one has."""
    page = np.full((PAGE[0], PAGE[1], 3), shade, np.uint8)
    noise = np.random.default_rng(0).normal(0, 2.0, page.shape)
    return np.clip(page.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def put_card(page, cx, cy, colour=(40, 90, 200), angle=0.0, size=CARD,
             border=False):
    """Draw a card centred at (cx, cy), optionally white-bordered."""
    import cv2

    rect = ((float(cx), float(cy)), (float(size[0]), float(size[1])), angle)
    box = cv2.boxPoints(rect).astype(np.int32)

    if border:
        # A white-bordered card: pale face, art inset. Pale but not identical
        # to the lid, and with the faint edge line a card sitting a millimetre
        # above the glass actually throws -- which is what the edge half of
        # card_mask exists to catch.
        cv2.fillPoly(page, [box], (252, 252, 252))
        cv2.polylines(page, [box], True, (205, 205, 205), 3)
        inner = cv2.boxPoints(
            ((float(cx), float(cy)),
             (size[0] * 0.78, size[1] * 0.72), angle)).astype(np.int32)
        cv2.fillPoly(page, [inner], colour)
    else:
        cv2.fillPoly(page, [box], colour)
        # texture, so it is not a flat blob no real card resembles
        inner = cv2.boxPoints(
            ((float(cx), float(cy)),
             (size[0] * 0.7, size[1] * 0.6), angle)).astype(np.int32)
        cv2.fillPoly(page, [inner], (230, 220, 210))
    return page


def centres(cards):
    return [(int(round(c.centre[0])), int(round(c.centre[1]))) for c in cards]


# --- reading order ----------------------------------------------------------

def make(cx, cy, w=CARD[0], h=CARD[1]):
    return cs.Card(((float(cx), float(cy)), (float(w), float(h)), 0.0), 1.0)


def test_reading_order_is_left_to_right_then_down():
    cards = [make(900, 1800), make(400, 600), make(900, 600), make(400, 1800)]
    assert centres(cs.reading_order(cards)) == [
        (400, 600), (900, 600), (400, 1800), (900, 1800)]


def test_reading_order_tolerates_a_crooked_row():
    """Two cards side by side, one nudged up. They are still one row.

    Sorting on y alone would put the higher card first and then jump back --
    which with --pairs would swap a front and a back onto the wrong SKUs.
    """
    cards = [make(900, 620), make(400, 560)]
    assert centres(cs.reading_order(cards)) == [(400, 560), (900, 620)]


def test_reading_order_separates_genuine_rows():
    cards = [make(400, 1800), make(400, 600)]
    assert centres(cs.reading_order(cards)) == [(400, 600), (400, 1800)]


def test_reading_order_of_nothing_is_nothing():
    assert cs.reading_order([]) == []


# --- geometry ---------------------------------------------------------------

def test_normalise_rect_makes_a_landscape_rect_portrait():
    (_, (w, h), angle) = cs.normalise_rect(((100, 100), (1050, 750), 0.0))
    assert (w, h) == (750, 1050)
    assert angle == pytest.approx(-90.0)


def test_normalise_rect_leaves_a_portrait_rect_alone():
    (_, (w, h), angle) = cs.normalise_rect(((100, 100), (750, 1050), 0.0))
    assert (w, h) == (750, 1050)
    assert angle == pytest.approx(0.0)


def test_order_corners_puts_top_left_first():
    pts = np.array([[10, 90], [10, 10], [90, 10], [90, 90]], np.float32)
    assert cs.order_corners(pts).tolist() == [
        [10, 10], [90, 10], [90, 90], [10, 90]]


def test_turn_180_is_reversible():
    img = np.random.default_rng(1).integers(0, 255, (7, 5, 3), dtype=np.uint8)
    assert np.array_equal(cs.turn(cs.turn(img, 180), 180), img)


def test_turn_90_swaps_the_sides():
    img = np.zeros((10, 4, 3), np.uint8)
    assert cs.turn(img, 90).shape[:2] == (4, 10)


def test_turn_rejects_a_diagonal():
    with pytest.raises(ValueError):
        cs.turn(np.zeros((4, 4, 3), np.uint8), 45)


# --- detection --------------------------------------------------------------

def test_finds_four_cards_in_reading_order():
    page = blank_page()
    put_card(page, 500, 700, (200, 60, 60))
    put_card(page, 1400, 700, (60, 160, 60))
    put_card(page, 500, 2000, (60, 60, 200))
    put_card(page, 1400, 2000, (160, 60, 160))

    cards = cs.detect_cards(page, DPI)
    assert len(cards) == 4
    xs = [c.centre[0] for c in cards]
    ys = [c.centre[1] for c in cards]
    assert xs[0] < xs[1] and xs[2] < xs[3]      # each row runs left to right
    assert ys[0] < ys[2] and ys[1] < ys[3]      # the top row comes first


def test_finds_a_card_that_is_slightly_crooked():
    page = blank_page()
    put_card(page, 1000, 1400, angle=6.0)
    cards = cs.detect_cards(page, DPI)
    assert len(cards) == 1
    assert cards[0].centre[0] == pytest.approx(1000, abs=25)
    assert cards[0].centre[1] == pytest.approx(1400, abs=25)


def test_a_white_bordered_card_is_found_whole_not_just_its_art():
    """The Topps case, and the reason card_mask looks at edges as well.

    A colour threshold alone sees only the art window and would cut the white
    border off -- the exact part a buyer checks for centring.
    """
    page = blank_page()
    put_card(page, 1000, 1400, border=True)
    cards = cs.detect_cards(page, DPI)
    assert len(cards) == 1
    w, h = cards[0].size
    assert w == pytest.approx(CARD[0], rel=0.12)
    assert h == pytest.approx(CARD[1], rel=0.12)


def test_dust_and_specks_are_not_cards():
    import cv2

    page = blank_page()
    put_card(page, 1000, 1400)
    cv2.circle(page, (300, 300), 18, (30, 30, 30), -1)
    cv2.rectangle(page, (1900, 2600), (1980, 2660), (90, 90, 90), -1)
    assert len(cs.detect_cards(page, DPI)) == 1


def test_the_page_itself_is_not_returned_as_a_card():
    """An empty sheet has nothing card-shaped on it, so nothing comes back."""
    assert cs.detect_cards(blank_page(), DPI) == []


def test_a_card_at_the_very_edge_still_reads_the_lid_correctly():
    """background_colour samples a ring, so a card in the corner -- which is
    how the real scans came in -- must not drag the estimate off white."""
    page = blank_page()
    put_card(page, CARD[0] // 2 + 10, CARD[1] // 2 + 10)
    assert len(cs.detect_cards(page, DPI)) == 1


# --- extraction -------------------------------------------------------------

def test_extract_straightens_a_crooked_card():
    page = blank_page()
    put_card(page, 1000, 1400, angle=8.0)
    card = cs.detect_cards(page, DPI)[0]
    crop = cs.extract(page, card)
    h, w = crop.shape[:2]
    assert w == pytest.approx(CARD[0], rel=0.1)
    assert h == pytest.approx(CARD[1], rel=0.1)
    assert h > w                                  # comes out portrait


def test_extract_pad_widens_the_crop():
    page = blank_page()
    put_card(page, 1000, 1400)
    card = cs.detect_cards(page, DPI)[0]
    plain = cs.extract(page, card)
    padded = cs.extract(page, card, pad=30)
    assert padded.shape[0] == plain.shape[0] + 60
    assert padded.shape[1] == plain.shape[1] + 60


def test_negative_pad_trims_the_crop():
    """The documented way to shave a toploader rim by hand."""
    page = blank_page()
    put_card(page, 1000, 1400)
    card = cs.detect_cards(page, DPI)[0]
    plain = cs.extract(page, card)
    trimmed = cs.extract(page, card, pad=-25)
    assert trimmed.shape[1] == plain.shape[1] - 50
