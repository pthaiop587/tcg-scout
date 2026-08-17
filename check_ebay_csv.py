"""Read an upload file back and say what eBay will refuse, before it does.

    python check_ebay_csv.py                       # newest ebay-upload-*.csv
    python check_ebay_csv.py ebay-upload-x.csv

WHY.

Seller Hub reports failures per row, hours later, in a results file, phrased
for a system rather than a person -- and a batch of 125 that comes back with
125 errors tells you almost nothing about which mistake you actually made.
Everything below is checkable here in a second, on the file you are about to
send.

It checks what can be known without eBay. It cannot know which item specifics
your categories mark as required -- that lives behind the API -- so a clean
run here means "nothing obviously wrong", not "this will be accepted".
"""

import argparse
import csv
import glob
import os
import re
import sys

TITLE_MAX = 80
PICS_MAX = 24


def rows_of(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def col(row, *names):
    """The first of these columns that the file actually has."""
    for n in names:
        for k in row:
            if k and k.strip().lower() == n.lower():
                return row[k]
    return None


def action_column(fieldnames):
    return next((f for f in fieldnames or [] if f and
                 f.strip().lower().startswith("action")), None)


def money(x):
    s = str(x or "").strip().replace("$", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def check(rows, fieldnames):
    """Every problem found, as (severity, sku, message)."""
    out = []
    seen = {}

    if not action_column(fieldnames):
        out.append(("STOP", "-", "no Action column -- eBay will not know "
                                 "whether to add or revise anything"))

    for i, r in enumerate(rows, start=2):
        sku = (col(r, "CustomLabel", "SKU") or "").strip() or "row %d" % i

        if sku in seen:
            out.append(("STOP", sku, "same CustomLabel as row %d; eBay keys "
                                     "revisions off it" % seen[sku]))
        else:
            seen[sku] = i

        title = (col(r, "Title") or "").strip()
        if not title:
            out.append(("STOP", sku, "no title"))
        elif len(title) > TITLE_MAX:
            out.append(("STOP", sku, "title is %d characters, %d over the "
                                     "limit" % (len(title),
                                                len(title) - TITLE_MAX)))

        if not (col(r, "Category", "CategoryID") or "").strip():
            out.append(("STOP", sku, "no category"))

        price = money(col(r, "StartPrice", "Price"))
        if price is None:
            out.append(("STOP", sku, "no start price"))
        elif price <= 0:
            out.append(("STOP", sku, "start price is %.2f" % price))

        qty = (col(r, "Quantity") or "").strip()
        if qty and not qty.isdigit():
            out.append(("STOP", sku, "quantity %r is not a number" % qty))

        if not (col(r, "ConditionID", "Condition") or "").strip():
            out.append(("WARN", sku, "no condition id"))

        pics = [p for p in (col(r, "PicURL", "PictureURL") or "").split("|")
                if p.strip()]
        if not pics:
            out.append(("WARN", sku, "no picture; the listing will be ignored "
                                     "by most buyers"))
        if len(pics) > PICS_MAX:
            out.append(("STOP", sku, "%d pictures, eBay takes %d"
                        % (len(pics), PICS_MAX)))
        for p in pics:
            if not p.strip().lower().startswith("https://"):
                out.append(("STOP", sku, "picture is not https: %s"
                            % p.strip()[:60]))
                break

        # Business Policies and the loose fields are mutually exclusive, and
        # an account set up for one rejects the other. Both filled is the
        # ambiguous case worth flagging; neither is a different problem.
        profiles = [col(r, n) for n in ("ShippingProfileName",
                                        "ReturnProfileName",
                                        "PaymentProfileName")]
        has_profile = any(str(x or "").strip() for x in profiles)
        loose = str(col(r, "ShippingService-1:Cost") or "").strip()
        if has_profile and loose:
            out.append(("WARN", sku, "has both a shipping profile and a loose "
                                     "shipping cost; eBay takes one or the "
                                     "other"))
        if not has_profile and not loose:
            out.append(("WARN", sku, "no postage at all: no shipping profile "
                                     "and no shipping cost"))
    return out


def main():
    p = argparse.ArgumentParser(
        description="Check an eBay upload file before you send it.")
    p.add_argument("path", nargs="?", help="default: newest ebay-upload-*.csv")
    a = p.parse_args()

    path = a.path
    if not path:
        found = sorted(glob.glob("ebay-upload-*.csv"))
        if not found:
            sys.exit("no ebay-upload-*.csv here -- run make_ebay_csv.py first")
        path = found[-1]
    if not os.path.exists(path):
        sys.exit("%s not found" % path)

    with open(path, newline="", encoding="utf-8-sig") as fh:
        fieldnames = csv.DictReader(fh).fieldnames
    rows = rows_of(path)
    problems = check(rows, fieldnames)

    stops = [x for x in problems if x[0] == "STOP"]
    warns = [x for x in problems if x[0] == "WARN"]
    print("%s -- %d row(s), %d column(s)" % (path, len(rows),
                                             len(fieldnames or [])))
    print("%d thing(s) eBay will refuse, %d worth a look\n"
          % (len(stops), len(warns)))

    for label, items in (("WILL BE REFUSED", stops), ("WORTH A LOOK", warns)):
        if not items:
            continue
        print(label)
        shown = {}
        for _sev, sku, msg in items:
            key = re.sub(r"\d+", "N", msg)
            shown.setdefault(key, []).append((sku, msg))
        for key, group in shown.items():
            sku, msg = group[0]
            extra = ("  (and %d more like it)" % (len(group) - 1)
                     if len(group) > 1 else "")
            print("   %-9s %s%s" % (sku, msg, extra))
        print()

    if not stops and not warns:
        print("Nothing obviously wrong.")
    print("This checks what can be known without eBay. Which item specifics "
          "your\ncategories require is only knowable through their API, so a "
          "clean run here\nis not a promise of acceptance.")
    return 1 if stops else 0


if __name__ == "__main__":
    sys.exit(main())
