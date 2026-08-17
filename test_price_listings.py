"""Tests for the listing pricer.

Run: python -m pytest test_price_listings.py

The arithmetic is the whole point of the script, so it is tested without a
workbook. What matters is that a card which cannot pay its own postage never
comes back with an ask price, because that is the mistake the script exists to
prevent: a hundred and fifty listings that each lose money.
"""

import subprocess
import sys

import pytest
from openpyxl import load_workbook

import price_listings as pl

FEE, FIX, POST = 13.25, 0.30, 0.70


def card(sku="CRH-0001", raw=None, cost=1.26, market=None, status="Unlisted"):
    return {"row": 2, "sku": sku, "name": "A Card", "status": status,
            "cost": cost, "raw": raw, "market": market}


# --- the arithmetic ---------------------------------------------------------

def test_a_sale_is_not_the_sticker_price():
    """13.25% plus 30c plus postage. A dollar card sold for a dollar loses."""
    assert pl.net_of(1.00, FEE, FIX, POST) < 0
    assert pl.net_of(10.00, FEE, FIX, POST) == pytest.approx(7.675)


def test_the_floor_is_what_gets_the_cost_back():
    low = pl.floor_ask(1.26, FEE, FIX, POST)
    assert round(low, 2) == 2.61
    assert pl.net_of(low, FEE, FIX, POST) == pytest.approx(1.26)


def test_a_free_card_still_has_to_pay_postage():
    low = pl.floor_ask(0.0, FEE, FIX, POST)
    assert pl.net_of(low, FEE, FIX, POST) == pytest.approx(0.0)
    assert 1.10 < low < 1.20


def test_prices_end_in_99():
    assert pl.to_99(28.40) == 28.99
    assert pl.to_99(3.74) == 3.99
    assert pl.to_99(0.10) == 0.99
    assert pl.to_99(1.99) == 1.99, "already .99 should not jump a dollar"


# --- the decision -----------------------------------------------------------

def test_a_card_that_cannot_pay_its_postage_is_bulk_not_a_listing():
    r = pl.plan([card(raw=0.37)], FEE, FIX, POST, 1.25)[0]
    assert r["bulk"] is True
    assert r["ask"] is None
    assert "0.37" in r["why"]


def test_a_card_worth_listing_gets_an_ask_above_the_floor():
    r = pl.plan([card(raw=22.72, cost=0.64)], FEE, FIX, POST, 1.25)[0]
    assert r["ask"] == 28.99
    assert pl.net_of(r["ask"], FEE, FIX, POST) > 0.64


def test_the_ask_never_lands_below_the_floor_even_at_a_small_markup():
    """A markup of 1.0 on a card sitting exactly at the floor would price it
    at a loss once the fees come off."""
    r = pl.plan([card(raw=2.61)], FEE, FIX, POST, 1.0)[0]
    assert r["ask"] is not None
    assert pl.net_of(r["ask"], FEE, FIX, POST) >= 1.26


def test_a_card_with_no_price_is_never_guessed_at():
    r = pl.plan([card(raw=None)], FEE, FIX, POST, 1.25)[0]
    assert r["bulk"] is True and r["ask"] is None
    assert "no price" in r["why"]


def test_ignoring_the_cost_moves_the_line_but_not_below_break_even():
    dear = card(raw=1.40)
    assert pl.plan([dear], FEE, FIX, POST, 1.25)[0]["bulk"] is True
    loose = pl.plan([dear], FEE, FIX, POST, 1.25, ignore_cost=True)[0]
    assert loose["bulk"] is False
    assert pl.net_of(loose["ask"], FEE, FIX, POST) > 0


def test_market_value_is_rewritten_from_the_price_not_merely_filled():
    """It was set once, then 34 cards were re-priced and it kept the old
    number. James Cook read $10.56 against a real $0.37."""
    r = pl.plan([card(raw=0.37, market=10.56)], FEE, FIX, POST, 1.25)[0]
    assert r["market"] == 0.37
    assert r["was"] == 10.56


# --- the workbook -----------------------------------------------------------

def build(tmp_path, rows):
    wb = tmp_path / "Card Run HQ - Master.xlsx"
    subprocess.run([sys.executable, "make_workbook.py", "--out", str(wb)],
                   check=True, capture_output=True)
    book = load_workbook(wb)
    # A fresh workbook has no price columns; prices.py appends them on its
    # first run, and this script reads them.
    import prices
    prices.ensure_columns(book["Inventory"])
    ws = book["Inventory"]
    hdr = [c.value for c in ws[1]]
    g = {n: i + 1 for i, n in enumerate(hdr) if n}
    for i, d in enumerate(rows, start=2):
        for k, val in d.items():
            ws.cell(row=i, column=g[k]).value = val
    book.save(wb)
    return wb


def run(wb, *args):
    r = subprocess.run([sys.executable, "price_listings.py", "--workbook",
                        str(wb)] + list(args), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def inv(wb):
    ws = load_workbook(wb, data_only=True)["Inventory"]
    hdr = [c.value for c in ws[1]]
    g = {n: i + 1 for i, n in enumerate(hdr) if n}
    out = {}
    for r in range(2, ws.max_row + 1):
        sku = ws.cell(row=r, column=g["SKU"]).value
        if sku:
            out[sku] = {n: ws.cell(row=r, column=i).value
                        for n, i in g.items()}
    return out


ROWS = [
    {"SKU": "CRH-0001", "Player or card name": "Arch Manning",
     "Status": "Unlisted", "Cost each": 1.26, "Raw price": 20.30},
    {"SKU": "CRH-0002", "Player or card name": "James Cook",
     "Status": "Unlisted", "Cost each": 1.26, "Raw price": 0.37,
     "Market value": 10.56},
    {"SKU": "CRH-0003", "Player or card name": "Basic Energy",
     "Status": "Review", "Cost each": 0.64},
]


def test_a_dry_run_changes_nothing(tmp_path):
    wb = build(tmp_path, ROWS)
    out = run(wb)
    assert "Nothing written" in out
    assert inv(wb)["CRH-0001"]["Ask price"] is None
    assert inv(wb)["CRH-0002"]["Market value"] == 10.56


def test_go_prices_the_good_one_and_bulks_the_rest(tmp_path):
    wb = build(tmp_path, ROWS)
    run(wb, "--go")
    got = inv(wb)
    assert got["CRH-0001"]["Ask price"] == 25.99
    assert got["CRH-0002"]["Ask price"] is None
    assert got["CRH-0002"]["Status"] == "Bulk"


def test_the_stale_market_value_is_corrected(tmp_path):
    wb = build(tmp_path, ROWS)
    out = run(wb, "--go")
    assert "stale" in out
    assert inv(wb)["CRH-0002"]["Market value"] == 0.37


def test_a_review_row_is_left_for_the_person_it_is_waiting_on(tmp_path):
    """Pricing it would bury the question that put it on Review."""
    wb = build(tmp_path, ROWS)
    run(wb, "--go")
    got = inv(wb)["CRH-0003"]
    assert got["Status"] == "Review"
    assert got["Ask price"] is None


def test_no_bulk_leaves_status_alone(tmp_path):
    wb = build(tmp_path, ROWS)
    run(wb, "--go", "--no-bulk")
    assert inv(wb)["CRH-0002"]["Status"] == "Unlisted"


def test_the_export_skips_what_was_marked_bulk(tmp_path):
    """The whole point of the Bulk status: make_ebay_csv exports Unlisted
    rows, so a card that cannot pay its postage never reaches a listing."""
    wb = build(tmp_path, ROWS)
    run(wb, "--go")
    out = tmp_path / "e.csv"
    r = subprocess.run([sys.executable, "make_ebay_csv.py", "--workbook",
                        str(wb), "-o", str(out)], capture_output=True,
                       text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    body = out.read_text(encoding="utf-8")
    assert "CRH-0001" in body
    assert "CRH-0002" not in body
