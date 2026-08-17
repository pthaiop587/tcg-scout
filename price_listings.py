"""Set Market value and Ask price from what the cards are actually worth.

    python price_listings.py              # say what it would do
    python price_listings.py --go         # write it in

WHY THIS EXISTS.

make_ebay_csv.py puts Ask price into StartPrice, and Ask price was empty on
every row. An export from that is a set of listings with no price, which eBay
will not take. Something has to decide the number, and "the guide price" is
not that number, because a sale is not the guide price:

    net = ask x (1 - fee%) - fee_fixed - postage

At eBay's 13.25% plus $0.30, and about $0.70 to send one card in a tracked
envelope, a card sold at $1.00 returns -13c. The seller pays to sell it. That
stays true up to about $1.15, and the card does not repay what it cost until
about $2.61. On a collection whose median card is worth a dollar that is not a
rounding detail -- it is the difference between a listing and a bulk lot, and
it applies to most of the rows.

So: cards that can carry their own postage get an Ask price. Cards that cannot
are marked for a bulk lot instead of being listed at a loss one at a time.

Market value is rewritten, not just filled. It was set once from the raw price
and then 34 LOT-001 cards turned out to be base rather than Silver and were
re-priced -- but re-pricing writes the price columns, not Market value, so it
sat there remembering the Silver. James Cook read $10.56 against a real price
of $0.37. Reading a stale number is worse than reading a blank one, because a
blank does not look like an answer.

Nothing is written without --go.
"""

import argparse
import math
import sys

from openpyxl import load_workbook

import inuse

WORKBOOK = "Card Run HQ - Master.xlsx"

# eBay's cut on a trading card, and what a plain tracked envelope costs.
# Both are arguments because both change, and a wrong postage figure moves
# the listing/bulk line for a hundred cards at once.
FEE_PCT = 13.25
FEE_FIXED = 0.30
POSTAGE = 0.70
MARKUP = 1.25
BULK = "Bulk"


def net_of(ask, fee_pct, fee_fixed, postage):
    """What actually lands in the bank from a sale at this price."""
    return ask * (1 - fee_pct / 100.0) - fee_fixed - postage


def floor_ask(cost, fee_pct, fee_fixed, postage):
    """The lowest price that gets the card's cost back after fees and postage."""
    return (cost + fee_fixed + postage) / (1 - fee_pct / 100.0)


def to_99(x):
    """Up to the next price ending in .99, which is what card listings use."""
    return math.ceil(round(x - 0.99, 6)) + 0.99


def num(x):
    return x if isinstance(x, (int, float)) else None


def plan(cards, fee_pct, fee_fixed, postage, markup, ignore_cost=False):
    """Decide each card's market value, ask price, and whether it is bulk.

    ignore_cost moves the line. By default a card has to repay what it cost
    before it earns its own listing. With ignore_cost it only has to beat the
    fees and the postage -- which is the right call if the money spent on the
    box is already gone and the choice is between some cash and none.

    Kept apart from the workbook so the arithmetic can be tested without one.
    """
    out = []
    for c in cards:
        row = dict(c, was=num(c.get("market")), market=None, ask=None,
                   bulk=False, why="")
        raw = num(c.get("raw"))
        if raw is None:
            row["bulk"] = True
            row["why"] = "no price found for it"
            out.append(row)
            continue
        row["market"] = raw
        cost = 0.0 if ignore_cost else (num(c.get("cost")) or 0.0)
        low = floor_ask(cost, fee_pct, fee_fixed, postage)
        if raw < low:
            row["bulk"] = True
            row["why"] = ("worth $%.2f; needs $%.2f to clear %s"
                          % (raw, low,
                             "fees and postage" if ignore_cost
                             else "cost and postage"))
            out.append(row)
            continue
        row["ask"] = round(max(to_99(raw * markup), to_99(low)), 2)
        out.append(row)
    return out


def read(ws, g):
    cards = []
    for r in range(2, ws.max_row + 1):
        sku = ws.cell(row=r, column=g["SKU"]).value
        if not sku:
            continue
        cards.append({
            "row": r, "sku": sku,
            "name": ws.cell(row=r, column=g["Player or card name"]).value,
            "status": str(ws.cell(row=r, column=g["Status"]).value or "").strip(),
            "cost": ws.cell(row=r, column=g["Cost each"]).value,
            "raw": ws.cell(row=r, column=g["Raw price"]).value,
            "market": ws.cell(row=r, column=g["Market value"]).value,
        })
    return cards


def main():
    p = argparse.ArgumentParser(
        description="Set Market value and Ask price from the looked-up price.")
    p.add_argument("--workbook", default=WORKBOOK)
    p.add_argument("--fee-pct", type=float, default=FEE_PCT,
                   help="eBay's percentage cut (default %.2f)" % FEE_PCT)
    p.add_argument("--fee-fixed", type=float, default=FEE_FIXED,
                   help="per-order fee (default %.2f)" % FEE_FIXED)
    p.add_argument("--postage", type=float, default=POSTAGE,
                   help="what one card costs to send (default %.2f)" % POSTAGE)
    p.add_argument("--markup", type=float, default=MARKUP,
                   help="ask this multiple of the guide price (default %.2f)"
                        % MARKUP)
    p.add_argument("--ignore-cost", action="store_true",
                   help="list anything that beats fees and postage, even if "
                        "it does not repay what the card cost")
    p.add_argument("--no-bulk", action="store_true",
                   help="leave Status alone on cards that cannot pay their "
                        "own postage")
    p.add_argument("--go", action="store_true", help="write the values in")
    a = p.parse_args()

    inuse.refuse_if_open(a.workbook)
    wb = load_workbook(a.workbook)
    ws = wb["Inventory"]
    hdr = [c.value for c in ws[1]]
    g = {n: i + 1 for i, n in enumerate(hdr) if n}
    for need in ("SKU", "Status", "Cost each", "Raw price", "Market value",
                 "Ask price"):
        if need not in g:
            sys.exit("no %s column in %s" % (need, a.workbook))

    cards = read(ws, g)
    # A Review row is waiting on a person. Pricing it would bury the question.
    held = [c for c in cards if c["status"].lower() == "review"]
    live = [c for c in cards if c["status"].lower() != "review"]

    rows = plan(live, a.fee_pct, a.fee_fixed, a.postage, a.markup,
                a.ignore_cost)
    priced = [r for r in rows if r["ask"] is not None]
    bulk = [r for r in rows if r["bulk"]]
    # Market value that already held a number and is about to hold a different
    # one. Worth printing before writing: a figure that moves on its own is
    # how a stale one hides.
    moved = [r for r in rows if r["market"] is not None
             and r["was"] is not None and abs(r["was"] - r["market"]) > 0.005]

    print("%d card(s): %d priced to list, %d for a bulk lot, %d held on Review"
          % (len(cards), len(priced), len(bulk), len(held)))
    print("assuming eBay takes %.2f%% + $%.2f and postage is $%.2f"
          % (a.fee_pct, a.fee_fixed, a.postage))
    print("a card earns its own listing if it clears %s\n"
          % ("fees and postage (--ignore-cost)" if a.ignore_cost
             else "fees, postage AND what it cost"))

    if moved:
        print("Market value was stale on %d row(s) -- rewriting from the "
              "current price:" % len(moved))
        for r in sorted(moved, key=lambda x: -abs(x["was"] - x["market"]))[:6]:
            print("   %-9s %-22s %6.2f -> %6.2f"
                  % (r["sku"], str(r["name"])[:22], r["was"], r["market"]))
        if len(moved) > 6:
            print("   ... and %d more" % (len(moved) - 6))
        print()

    print("priced to list:")
    for r in sorted(priced, key=lambda x: -x["ask"]):
        print("   %-9s %-24s guide %6.2f  ask %6.2f  net %6.2f"
              % (r["sku"], str(r["name"])[:24], r["market"], r["ask"],
                 net_of(r["ask"], a.fee_pct, a.fee_fixed, a.postage)))

    worth = sum(r["market"] for r in bulk if r["market"])
    print("\nbulk lot: %d card(s), $%.2f of guide value between them"
          % (len(bulk), worth))
    print("   sold one at a time they would lose money on postage alone.")

    if not a.go:
        print("\nNothing written. Add --go.")
        return

    for r in rows:
        if r["market"] is not None:
            ws.cell(row=r["row"], column=g["Market value"]).value = r["market"]
        if r["ask"] is not None:
            ws.cell(row=r["row"], column=g["Ask price"]).value = r["ask"]
        elif r["bulk"] and not a.no_bulk:
            ws.cell(row=r["row"], column=g["Status"]).value = BULK
    wb.save(a.workbook)
    print("\nSaved %s." % a.workbook)
    print("make_ebay_csv.py exports Unlisted rows, so the %d bulk card(s) "
          "stay out of it." % (0 if a.no_bulk else len(bulk)))


if __name__ == "__main__":
    main()
