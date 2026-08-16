"""Move an existing workbook onto the current tab layout, keeping what is in it.

    python upgrade_workbook.py                 # say what it would do
    python upgrade_workbook.py --go            # actually do it

make_workbook.py --force builds a fresh workbook and throws away everything
typed into the old one, which is fine on day one and unusable afterwards. This
does the same rebuild and then carries the data across.

Rows are matched BY HEADER NAME, never by position. That is the whole point:
the layout gained five tabs and the columns moved, so copying cell A2 to cell
A2 would put a purchase date into a SKU column and nobody would notice until
an upload failed. A column that no longer exists is reported rather than
dropped in silence.

The old file is copied to a dated backup first, always, without being asked.
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime

from openpyxl import load_workbook

WORKBOOK = "Card Run HQ - Master.xlsx"

# Only tabs a person types into. Summary, Audit, Read me, Reference, Lists and
# the eBay upload are generated or fixed, so they come from the new build.
CARRY = ["Inventory", "Box log", "Sales", "Purchases", "Expenses", "Photos"]


def headers(ws):
    return [c.value for c in ws[1]]


def data_rows(ws):
    """Every row with something typed in it. Formulas are left behind -- the
    new sheet brings its own, and they will be the current ones."""
    hdr = headers(ws)
    out = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        rec = {}
        for name, value in zip(hdr, row):
            if not name or value in (None, ""):
                continue
            if isinstance(value, str) and value.startswith("="):
                continue
            rec[name] = value
        if rec:
            out.append(rec)
    return out


def first_free(ws, hdr):
    """The first row with nothing typed in it, ignoring formula columns."""
    r = 2
    while r <= ws.max_row:
        row = [ws.cell(row=r, column=i + 1).value for i in range(len(hdr))]
        typed = [v for v in row
                 if v not in (None, "") and not (isinstance(v, str) and v.startswith("="))]
        if not typed:
            return r
        r += 1
    return r


def main():
    p = argparse.ArgumentParser(
        description="Rebuild the workbook on the current layout, keeping the data.")
    p.add_argument("--workbook", default=WORKBOOK)
    p.add_argument("--go", action="store_true",
                   help="do it; without this it only says what it would do")
    a = p.parse_args()

    if not os.path.exists(a.workbook):
        sys.exit("no workbook at %s -- there is nothing to upgrade. "
                 "make_workbook.py builds a new one." % a.workbook)

    old = load_workbook(a.workbook)
    print("current file: %s" % a.workbook)
    print("  tabs: %s" % ", ".join(old.sheetnames))

    carried = {}
    for name in CARRY:
        if name in old.sheetnames:
            rows = data_rows(old[name])
            if rows:
                carried[name] = rows
    if carried:
        for name, rows in carried.items():
            print("  %-12s %d row(s) to carry over" % (name, len(rows)))
    else:
        print("  nothing typed in yet -- an upgrade would just be a rebuild.")

    if not a.go:
        print("\nThis was a dry run. Add --go to do it.")
        print("The old file will be copied to a dated backup first.")
        return 0

    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    backup = "%s (backup %s).xlsx" % (os.path.splitext(a.workbook)[0], stamp)
    shutil.copy(a.workbook, backup)
    print("\nbacked up to: %s" % backup)

    fresh = "%s.new.xlsx" % os.path.splitext(a.workbook)[0]
    subprocess.run([sys.executable, "make_workbook.py", "--out", fresh, "--force"],
                   check=True, capture_output=True)
    new = load_workbook(fresh)

    lost = {}
    for name, rows in carried.items():
        if name not in new.sheetnames:
            lost[name] = "the tab no longer exists"
            continue
        ws = new[name]
        hdr = headers(ws)
        col = {h: i + 1 for i, h in enumerate(hdr) if h}

        # A fresh workbook is not empty: make_workbook.py seeds the Box log
        # with the one box actually bought, straight off its receipt. Carrying
        # the old copy in on top of it puts the same box in twice, and the
        # cost-per-card figures then count it twice. So anything the new sheet
        # already has, identically, is left alone.
        already = [frozenset(rec.items()) for rec in data_rows(ws)]
        r = first_free(ws, hdr)
        skipped = 0

        for rec in rows:
            if frozenset(rec.items()) in already:
                skipped += 1
                continue
            for key, value in rec.items():
                if key not in col:
                    lost.setdefault(name, set())
                    if isinstance(lost[name], set):
                        lost[name].add(key)
                    continue
                ws.cell(row=r, column=col[key], value=value)
            r += 1
        print("carried %d row(s) into %s%s"
              % (len(rows) - skipped, name,
                 "" if not skipped else
                 " (%d already there, left alone)" % skipped))

    new.save(fresh)
    os.replace(fresh, a.workbook)
    print("\n%s is now on the current layout (%d tabs)."
          % (a.workbook, len(new.sheetnames)))

    if lost:
        print("\nCOLUMNS THAT NO LONGER EXIST -- the values are in the backup, "
              "not in the new file:")
        for tab, what in lost.items():
            print("   %s: %s" % (tab, what if isinstance(what, str)
                                 else ", ".join(sorted(what))))
    print("\nNext: python embed_photos.py   (fills the Photos tab from photos/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
