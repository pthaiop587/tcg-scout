"""Tests for putting the workbook onto the dashboard.

Run: python -m pytest test_export_inventory.py

The one that matters is that the published copy carries no money. The repo is
public; if cost or notes ever leak into inventory-public.json they are
readable by anyone with the URL, and a commit cannot be un-published.
"""

import json
import os
import shutil
import subprocess
import sys

import pytest
from PIL import Image

import export_inventory as ex
import file_batch as fb

CARDS = [
    {"player": "Shedeur Sanders", "year": 2025, "brand": "Panini Prizm Draft Picks",
     "insert": "Student Orientation", "parallel": "Gold Cracked Ice", "num": "8",
     "team": "Colorado Buffaloes", "rc": True, "cost": 6.50, "market": 12.50,
     "ask": 14.99, "lot": "LOT-001", "notes": "off the mega box"},
    {"player": "Jonah Coleman", "year": 2025, "brand": "Panini Prizm Draft Picks",
     "num": "169", "cost": 6.50, "ask": 7.99, "lot": "LOT-001",
     "unsure": ["market"]},
]


@pytest.fixture
def wb(tmp_path):
    out = tmp_path / "Card Run HQ - Master.xlsx"
    subprocess.run([sys.executable, "make_workbook.py", "--out", str(out)],
                   check=True, capture_output=True)
    fb.add_rows(str(out), [dict(c) for c in CARDS])
    return out


@pytest.fixture
def photos(tmp_path):
    d = tmp_path / "photos"
    d.mkdir()
    for name in ("CRH-0001.jpg", "CRH-0001-back.jpg"):
        Image.new("RGB", (750, 1050), (180, 140, 60)).save(d / name)
    return d


def export(wb, photos, cwd, publish=False):
    args = [sys.executable, os.path.abspath("export_inventory.py"),
            "--workbook", str(wb), "--photos", str(photos)]
    if publish:
        args.append("--publish")
    r = subprocess.run(args, capture_output=True, text=True, cwd=str(cwd))
    assert r.returncode == 0, r.stdout + r.stderr
    return r


# --- what comes out ---------------------------------------------------------

def test_every_card_comes_across(wb, photos, tmp_path):
    export(wb, photos, tmp_path)
    d = json.load(open(tmp_path / "inventory.json", encoding="utf-8"))
    assert len(d["cards"]) == 2
    first = d["cards"][0]
    assert first["sku"] == "CRH-0001"
    assert first["name"] == "Shedeur Sanders"
    assert first["num"] == "8"
    assert first["parallel"] == "Gold Cracked Ice"
    assert first["rc"] == "Yes"
    assert first["cost"] == 6.5


def test_a_card_with_an_unsure_field_shows_as_review(wb, photos, tmp_path):
    """It is the status the whole guard rests on, so the page must show it."""
    export(wb, photos, tmp_path)
    d = json.load(open(tmp_path / "inventory.json", encoding="utf-8"))
    by_sku = {c["sku"]: c for c in d["cards"]}
    assert by_sku["CRH-0002"]["status"] == "Review"
    assert by_sku["CRH-0001"]["status"] == "Unlisted"
    assert d["totals"]["review"] == 1


def test_totals_match_what_is_in_the_workbook(wb, photos, tmp_path):
    export(wb, photos, tmp_path)
    t = json.load(open(tmp_path / "inventory.json", encoding="utf-8"))["totals"]
    assert t["cards"] == 2
    assert t["cost"] == 13.00
    assert t["market"] == 12.50, "only one card has a market value"
    assert t["unlisted"] == 1


def test_photos_are_relative_so_they_load_in_both_places(wb, photos, tmp_path):
    """Absolute URLs pointed at the published site, which broke the
    thumbnails on the machine the photos were actually on."""
    export(wb, photos, tmp_path)
    d = json.load(open(tmp_path / "inventory.json", encoding="utf-8"))
    pics = d["cards"][0]["photos"]
    assert len(pics) == 2
    assert not any(p.startswith("http") for p in pics), pics
    assert pics[0].endswith("CRH-0001.jpg")
    assert pics[1].endswith("CRH-0001-back.jpg")


def test_a_card_with_no_photo_is_counted(wb, photos, tmp_path):
    export(wb, photos, tmp_path)
    d = json.load(open(tmp_path / "inventory.json", encoding="utf-8"))
    by_sku = {c["sku"]: c for c in d["cards"]}
    assert by_sku["CRH-0002"]["photos"] == []


# --- the published copy: this is the one that matters -----------------------

def test_publish_writes_no_money(wb, photos, tmp_path):
    export(wb, photos, tmp_path, publish=True)
    d = json.load(open(tmp_path / "inventory-public.json", encoding="utf-8"))
    assert d["money"] is False
    for card in d["cards"]:
        for banned in ("cost", "notes", "lot"):
            assert banned not in card, \
                "%s reached the PUBLIC export for %s" % (banned, card["sku"])


def test_publish_still_says_what_the_card_is(wb, photos, tmp_path):
    """Stripping the money must not strip the point of the tab."""
    export(wb, photos, tmp_path, publish=True)
    d = json.load(open(tmp_path / "inventory-public.json", encoding="utf-8"))
    c = d["cards"][0]
    for key in ("sku", "name", "brand", "num", "parallel", "cond", "qty",
                "status", "photos", "market"):
        assert key in c, key
    assert c["name"] == "Shedeur Sanders"


def test_nothing_public_is_written_without_the_flag(wb, photos, tmp_path):
    """Publishing is a decision, so it takes a flag."""
    export(wb, photos, tmp_path)
    assert os.path.exists(tmp_path / "inventory.json")
    assert not os.path.exists(tmp_path / "inventory-public.json")


def test_the_private_list_covers_every_money_field():
    """A new money column in FIELDS must be added to PRIVATE deliberately."""
    money_ish = {k for k in ex.FIELDS.values()
                 if k in ("cost", "notes", "lot")}
    assert money_ish <= ex.PRIVATE


# --- a workbook with nothing in it ------------------------------------------

def test_an_empty_workbook_says_so_rather_than_writing_nothing(tmp_path):
    out = tmp_path / "wb.xlsx"
    subprocess.run([sys.executable, "make_workbook.py", "--out", str(out)],
                   check=True, capture_output=True)
    r = subprocess.run([sys.executable, os.path.abspath("export_inventory.py"),
                        "--workbook", str(out)],
                       capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode == 0
    assert "no cards" in r.stdout
    assert not os.path.exists(tmp_path / "inventory.json")


def test_a_missing_workbook_is_a_clear_error(tmp_path):
    r = subprocess.run([sys.executable, os.path.abspath("export_inventory.py"),
                        "--workbook", str(tmp_path / "nope.xlsx")],
                       capture_output=True, text=True)
    assert r.returncode != 0
    assert "no workbook" in (r.stdout + r.stderr)


# --- the one-command refresh ------------------------------------------------

def test_refresh_refuses_an_old_workbook_rather_than_rebuilding_over_it(tmp_path):
    """make_workbook --force would throw the data away, so refresh must stop
    and point at the upgrade instead of doing something destructive."""
    import shutil as sh
    old = tmp_path / "Card Run HQ - Master.xlsx"
    # a 7-tab workbook is what "old" means: no Summary, Purchases, Photos...
    from openpyxl import Workbook
    w = Workbook()
    for name in ("Read me", "Inventory", "eBay upload", "Box log", "Sales",
                 "Reference", "Lists"):
        w.create_sheet(name)
    w.remove(w["Sheet"])
    w.save(old)

    r = subprocess.run([sys.executable, os.path.abspath("refresh.py"),
                        "--workbook", str(old)],
                       capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode == 1
    assert "old layout" in r.stdout
    assert "upgrade_workbook.py --go" in r.stdout


def test_refresh_says_what_to_do_when_there_is_no_workbook(tmp_path):
    r = subprocess.run([sys.executable, os.path.abspath("refresh.py"),
                        "--workbook", str(tmp_path / "nope.xlsx")],
                       capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode == 1
    assert "make_workbook.py" in r.stdout


def test_refresh_does_not_publish_unless_asked(wb, photos, tmp_path):
    """The public copy goes on a public site, so it never happens by default."""
    sh_page = tmp_path / "card-run-hq.html"
    r = subprocess.run([sys.executable, os.path.abspath("refresh.py"),
                        "--workbook", str(wb), "--out", str(sh_page)],
                       capture_output=True, text=True, cwd=str(tmp_path))
    # build_all needs its data files, so it may fail at the last step -- what
    # matters is that no public export was written on the way
    assert not os.path.exists(tmp_path / "inventory-public.json"), r.stdout
