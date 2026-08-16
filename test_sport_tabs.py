"""Tests for the per-sport view tabs.

Run: python -m pytest test_sport_tabs.py

The point of these tabs is that they are VIEWS. If they ever became a second
place cards live, the damage is silent: file_batch.py takes the next SKU from
Inventory only, make_ebay_csv.py exports from Inventory only, and the Summary
and Audit tabs count Inventory only. A basketball card typed into a Basketball
tab would get a SKU another card already has, never reach an upload, and be
missing from every total, with nothing anywhere saying so.

So the tests that matter are: Inventory still holds every card, the export
still sees every card, and a tab somebody made by hand is never overwritten.
"""

import os
import subprocess
import sys

import pytest
from openpyxl import load_workbook

import file_batch as fb
import sport_tabs as st

CARDS = [
    {"player": "Shedeur Sanders", "year": 2025, "brand": "Prizm Draft Picks",
     "num": "8", "sport": "Football", "league": "NCAA", "cost": 1.26, "market": 12.5},
    {"player": "Victor Wembanyama", "year": 2024, "brand": "Prizm",
     "num": "136", "sport": "Basketball", "league": "NBA", "cost": 4.0, "market": 38.0},
    {"player": "Cooper Flagg", "year": 2025, "brand": "Prizm Draft Picks",
     "num": "1", "sport": "Basketball", "league": "NCAA", "cost": 3.5, "market": 22.0},
]


@pytest.fixture
def wb(tmp_path):
    out = tmp_path / "Card Run HQ - Master.xlsx"
    subprocess.run([sys.executable, "make_workbook.py", "--out", str(out)],
                   check=True, capture_output=True)
    fb.add_rows(str(out), [dict(c) for c in CARDS])
    return out


def run(wb, *args):
    r = subprocess.run([sys.executable, os.path.abspath("sport_tabs.py"),
                        "--workbook", str(wb)] + list(args),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def rows_on(wb, tab):
    ws = load_workbook(wb)[tab]
    hdr = [c.value for c in ws[2]]
    out = []
    for row in ws.iter_rows(min_row=3, values_only=True):
        if row[0]:
            out.append(dict(zip(hdr, row)))
    return out


# --- the split --------------------------------------------------------------

def test_a_tab_per_sport_in_use(wb):
    run(wb)
    names = load_workbook(wb).sheetnames
    assert "Basketball" in names
    assert "Football" in names


def test_each_tab_holds_only_its_own_sport(wb):
    run(wb)
    bball = rows_on(wb, "Basketball")
    assert {r["Player or card name"] for r in bball} == \
        {"Victor Wembanyama", "Cooper Flagg"}
    assert [r["Player or card name"] for r in rows_on(wb, "Football")] == \
        ["Shedeur Sanders"]


def test_add_makes_a_tab_before_there_are_any_cards(wb):
    """You want the tab when you start on a sport, not after."""
    out = run(wb, "--add", "Hockey")
    assert "Hockey" in load_workbook(wb).sheetnames
    assert rows_on(wb, "Hockey") == []
    assert "Hockey" in out


# --- the thing that must not happen -----------------------------------------

def test_inventory_still_holds_every_card(wb):
    """The views are copies. Inventory stays the one record."""
    run(wb)
    ws = load_workbook(wb)["Inventory"]
    skus = [r[0] for r in ws.iter_rows(min_row=2, values_only=True) if r[0]]
    assert skus == ["CRH-0001", "CRH-0002", "CRH-0003"]


def test_the_ebay_export_still_sees_every_card(wb, tmp_path):
    """If a sport tab ever became a real inventory, these would go missing."""
    run(wb)
    r = subprocess.run([sys.executable, "make_ebay_csv.py",
                        "--workbook", str(wb), "--out", str(tmp_path / "o.csv")],
                       capture_output=True, text=True)
    body = r.stdout + r.stderr
    assert "3 listings" in body, body


def test_the_next_sku_still_comes_from_inventory(wb):
    """A card added after the tabs exist must not reuse a number."""
    run(wb)
    added = fb.add_rows(str(wb), [{"player": "Travis Hunter", "sport": "Football"}])
    assert [e["sku"] for e in added] == ["CRH-0004"]


# --- rebuilding -------------------------------------------------------------

def test_running_it_twice_changes_nothing(wb):
    run(wb)
    before = load_workbook(wb).sheetnames
    run(wb)
    assert load_workbook(wb).sheetnames == before
    assert len(rows_on(wb, "Basketball")) == 2


def test_a_new_card_shows_up_on_the_next_run(wb):
    run(wb)
    fb.add_rows(str(wb), [{"player": "Ace Bailey", "sport": "Basketball"}])
    run(wb)
    assert len(rows_on(wb, "Basketball")) == 3


def test_a_tab_you_made_yourself_is_never_overwritten(wb):
    """Only sheets carrying the generated marker are replaced."""
    book = load_workbook(wb)
    mine = book.create_sheet("Basketball")
    mine["A1"] = "my own notes"
    mine["A2"] = "do not delete this"
    book.save(wb)

    out = run(wb)
    ws = load_workbook(wb)["Basketball"]
    assert ws["A1"].value == "my own notes"
    assert ws["A2"].value == "do not delete this"
    assert "left alone" in out


def test_the_tab_says_it_is_generated(wb):
    """Otherwise somebody types in it and loses the lot on the next run."""
    run(wb)
    ws = load_workbook(wb)["Basketball"]
    a1 = str(ws["A1"].value)
    assert a1.startswith("VIEW")
    assert "Do not type here" in a1


def test_list_reports_what_is_there(wb):
    run(wb)
    out = run(wb, "--list")
    assert "Basketball" in out and "Football" in out
    assert "2 card(s)" in out


def test_a_workbook_with_no_sports_says_so(tmp_path):
    out = tmp_path / "wb.xlsx"
    subprocess.run([sys.executable, "make_workbook.py", "--out", str(out)],
                   check=True, capture_output=True)
    r = subprocess.run([sys.executable, os.path.abspath("sport_tabs.py"),
                        "--workbook", str(out)], capture_output=True, text=True)
    assert r.returncode == 0
    assert "--add Basketball" in r.stdout
