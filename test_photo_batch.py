"""Tests for preparing and filing a batch of card photos.

Run: python -m pytest test_photo_batch.py

The expensive mistake here is filing a picture onto the wrong card. That is not
a crash -- it is a listing showing somebody else's card, found out by a buyer.
So the matcher must refuse anything it cannot resolve to exactly one row, and
the front/back pairing must be visible before anything is written, because one
missing back silently shifts every pair after it.
"""

import json
import os
import subprocess
import sys

import pytest
from PIL import Image

import file_batch as fb
import photo_batch as pb


def shot(path, w=600, h=800, colour=(40, 40, 48)):
    im = Image.new("RGB", (w, h), (158, 158, 156))     # a grey tabletop
    im.paste(Image.new("RGB", (w // 3, h // 3), colour),
             (w // 3, h // 3))                          # a card on it
    im.save(path, "JPEG", quality=85)


@pytest.fixture
def shed(tmp_path):
    src = tmp_path / "scans"
    src.mkdir()
    for n in ("IMG_0001", "IMG_0002", "IMG_0003", "IMG_0004"):
        shot(str(src / (n + ".jpg")))
    return src, tmp_path


def prep(src, tmp, *args):
    r = subprocess.run([sys.executable, os.path.abspath("photo_batch.py"),
                        "prep", str(src), "--work", str(tmp / "w"),
                        "--out", str(tmp / "b.json")] + list(args),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout, json.load(open(tmp / "b.json", encoding="utf-8"))


# --- pairing ----------------------------------------------------------------

def test_shots_pair_front_then_back(shed):
    src, tmp = shed
    out, data = prep(src, tmp)
    cards = data["cards"]
    assert len(cards) == 2
    assert cards[0]["front"] == "IMG_0001" and cards[0]["back"] == "IMG_0002"
    assert cards[1]["front"] == "IMG_0003" and cards[1]["back"] == "IMG_0004"


def test_singles_does_not_pair(shed):
    src, tmp = shed
    _out, data = prep(src, tmp, "--singles")
    assert len(data["cards"]) == 4
    assert all(c["back"] is None for c in data["cards"])


def test_an_odd_count_is_called_out(shed):
    """One missing back shifts every pair after it, and nothing else would
    notice -- the photos would just be filed onto the wrong cards."""
    src, tmp = shed
    shot(str(src / "IMG_0005.jpg"))
    out, _data = prep(src, tmp)
    assert "odd number" in out


def test_the_pairing_is_printed_before_anything_is_written(shed):
    src, tmp = shed
    out, _ = prep(src, tmp)
    assert "IMG_0001" in out and "IMG_0002" in out
    assert "contact sheet" in out


def test_a_contact_sheet_is_produced(shed):
    src, tmp = shed
    prep(src, tmp)
    sheets = [f for f in os.listdir(tmp / "w") if f.startswith("sheet-")]
    assert sheets, os.listdir(tmp / "w")
    im = Image.open(os.path.join(tmp / "w", sheets[0]))
    assert im.size[0] > 1000, "a sheet too small to read names off is no use"


# --- matching ---------------------------------------------------------------

INV = [
    {"sku": "CRH-0036", "name": "Jack Bech", "parallel": "Silver",
     "num": "118", "insert": None},
    {"sku": "CRH-0039", "name": "Travis Hunter", "parallel": "Gold Ice",
     "num": "21", "insert": None},
    {"sku": "CRH-0062", "name": "Travis Hunter", "parallel": "Silver",
     "num": "21", "insert": None},
    {"sku": "CRH-0048", "name": "Harold Fannin Jr.", "parallel": "Gold Ice",
     "num": "3", "insert": "New Recruits"},
]


def test_the_parallel_separates_two_of_the_same_card():
    """Two Travis Hunter #21s differing only by parallel is the exact case
    that has to work, and the exact case a name-only match gets wrong."""
    assert [h["sku"] for h in pb.match(
        {"name": "Travis Hunter", "parallel": "Silver"}, INV)] == ["CRH-0062"]
    assert [h["sku"] for h in pb.match(
        {"name": "Travis Hunter", "parallel": "Gold Ice"}, INV)] == ["CRH-0039"]


def test_an_ambiguous_card_returns_them_all_rather_than_picking():
    got = pb.match({"name": "Travis Hunter"}, INV)
    assert len(got) == 2, [g["sku"] for g in got]


def test_a_card_that_is_not_there_matches_nothing():
    assert pb.match({"name": "Nobody Atall", "parallel": "Silver"}, INV) == []


def test_punctuation_and_case_do_not_stop_a_match():
    for spelling in ("Harold Fannin Jr.", "harold fannin jr", "HAROLD FANNIN JR"):
        assert [h["sku"] for h in pb.match(
            {"name": spelling, "parallel": "Gold Ice"}, INV)] == ["CRH-0048"]


def test_a_card_number_settles_what_the_parallel_cannot():
    got = pb.match({"name": "Travis Hunter", "num": "21"}, INV)
    assert len(got) == 2          # both are #21, so it stays ambiguous
    got = pb.match({"name": "Jack Bech", "num": "118"}, INV)
    assert [h["sku"] for h in got] == ["CRH-0036"]


# --- filing refuses what it cannot resolve ----------------------------------

def test_nothing_is_filed_for_an_unmatched_card(tmp_path):
    wb = tmp_path / "Card Run HQ - Master.xlsx"
    subprocess.run([sys.executable, "make_workbook.py", "--out", str(wb)],
                   check=True, capture_output=True)
    fb.add_rows(str(wb), [{"player": "Jack Bech", "parallel": "Silver",
                           "num": "118", "sport": "Football"}])
    batch = tmp_path / "b.json"
    batch.write_text(json.dumps({"work": str(tmp_path), "cards": [
        {"n": 1, "front": "nope", "back": None, "name": "Ghost Player",
         "parallel": "Silver"}]}), encoding="utf-8")

    r = subprocess.run([sys.executable, os.path.abspath("photo_batch.py"),
                        "file", str(batch), "--workbook", str(wb)],
                       capture_output=True, text=True)
    assert "NOT filed" in r.stdout
    assert "nothing in Inventory matches" in r.stdout
    assert "Nothing filed" in r.stdout


def test_a_dry_run_is_the_default(tmp_path):
    """--go exists so a mis-typed batch cannot write 60 wrong pictures."""
    src = open("photo_batch.py", encoding="utf-8").read()
    assert 'if not a.go:' in src
    assert '"--go"' in src or "'--go'" in src


def test_a_named_sku_wins_outright():
    """Two of the SAME card cannot be told apart by anything printed on
    either. This inventory holds a pair of Saquon Barkley #190 Silvers, and no
    amount of looking at the photo resolves that -- somebody has to say which,
    and this is where they say it."""
    inv = [{"sku": "CRH-0015", "name": "Saquon Barkley", "parallel": "Silver",
            "num": "190", "insert": None},
           {"sku": "CRH-0017", "name": "Saquon Barkley", "parallel": "Silver",
            "num": "190", "insert": None}]
    assert [h["sku"] for h in pb.match(
        {"name": "Saquon Barkley", "parallel": "Silver"}, inv)] == \
        ["CRH-0015", "CRH-0017"]
    assert [h["sku"] for h in pb.match(
        {"sku": "CRH-0017", "name": "Saquon Barkley"}, inv)] == ["CRH-0017"]


def test_a_named_sku_that_does_not_exist_matches_nothing():
    """It must not fall back to the name -- a typo'd SKU would then file onto
    whatever the name happened to hit."""
    inv = [{"sku": "CRH-0015", "name": "Saquon Barkley", "parallel": "Silver",
            "num": "190", "insert": None}]
    assert pb.match({"sku": "CRH-9999", "name": "Saquon Barkley"}, inv) == []


# --- the insert set, which the front announces in large letters -------------

SHEDEUR = [
    {"sku": "CRH-0001", "name": "Shedeur Sanders", "parallel": "Gold Ice",
     "num": "8", "insert": "Student Orientation"},
    {"sku": "CRH-0018", "name": "Shedeur Sanders", "parallel": "Gold Ice",
     "num": "II-SSS", "insert": "Instant Impact"},
    {"sku": "CRH-0019", "name": "Shedeur Sanders", "parallel": "Gold Ice",
     "num": "19", "insert": None},
]


def test_the_insert_separates_cards_the_parallel_cannot():
    """Three Shedeur Sanders Gold Ices. Name and parallel are identical on all
    three; the insert is printed across the front of two of them."""
    assert [h["sku"] for h in pb.match(
        {"name": "Shedeur Sanders", "parallel": "Gold Ice",
         "insert": "Student Orientation"}, SHEDEUR)] == ["CRH-0001"]
    assert [h["sku"] for h in pb.match(
        {"name": "Shedeur Sanders", "parallel": "Gold Ice",
         "insert": "Instant Impact"}, SHEDEUR)] == ["CRH-0018"]


def test_no_insert_named_means_the_base_card():
    """A front with no insert banner is the base card, and saying nothing
    should not leave it ambiguous against two inserts."""
    assert [h["sku"] for h in pb.match(
        {"name": "Shedeur Sanders", "parallel": "Gold Ice"},
        SHEDEUR)] == ["CRH-0019"]


def test_an_insert_that_matches_nothing_does_not_narrow_to_zero():
    """Better to report two candidates than to file nothing because the insert
    was spelled differently."""
    got = pb.match({"name": "Shedeur Sanders", "parallel": "Gold Ice",
                    "insert": "Signing Day"}, SHEDEUR)
    assert len(got) == 3
