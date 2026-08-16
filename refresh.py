"""One command: workbook in, dashboard out.

    python refresh.py          # export the workbook and rebuild the page
    python refresh.py --open   # ...and open it
    python refresh.py --publish   # also refresh the money-free public copy

Run this after typing into Card Run HQ - Master.xlsx. It does, in order:

    autofill.py         SKU and Category for anything typed in by hand
    embed_photos.py      thumbnails into the workbook's Photos tab
    sport_tabs.py        a read-only tab per sport, rebuilt from Inventory
    export_inventory.py  the Inventory tab out to JSON
    build_all.py         the page rebuilt around it

Each of those is still a script you can run on its own; this exists because
running three in the right order every time is exactly the kind of thing that
stops getting done. Double-click "Update dashboard.cmd" and it runs this.

It refuses to guess about two things. If the workbook is on the old layout it
stops and tells you the one command that moves it across without losing what
you typed -- rebuilding over the top would throw the data away. And it never
writes the public export unless asked, because that one goes on a public site.
"""

import argparse
import os
import subprocess
import sys
import webbrowser

WORKBOOK = "Card Run HQ - Master.xlsx"
PAGE = "card-run-hq.html"
# The old layout called the upload tab "eBay upload" and had no per-game tabs.
# That rename is the cleanest thing to test for -- checking for Summary or
# Photos would wrongly reject the short layout, which does not have them.
OLD_NAME = "eBay upload"
NEW_NAME = "eBay"


def run(args, why):
    print("\n> %s" % " ".join(args[1:]))
    r = subprocess.run([sys.executable] + args[1:], capture_output=True, text=True)
    out = (r.stdout or "").strip()
    if out:
        print("\n".join("   " + l for l in out.splitlines()))
    if r.returncode != 0:
        err = (r.stderr or "").strip()
        print("\n%s failed:" % why)
        print("\n".join("   " + l for l in (err or "no output").splitlines()))
        return False
    return True


def workbook_tabs(path):
    from openpyxl import load_workbook
    return set(load_workbook(path, read_only=True).sheetnames)


def main():
    p = argparse.ArgumentParser(
        description="Export the workbook and rebuild the dashboard.")
    p.add_argument("--workbook", default=WORKBOOK)
    p.add_argument("--out", default=PAGE)
    p.add_argument("--publish", action="store_true",
                   help="also refresh inventory-public.json, which is committed "
                        "and served publicly WITHOUT cost, notes or lot")
    p.add_argument("--open", action="store_true", help="open the page afterwards")
    a = p.parse_args()

    if not os.path.exists(a.workbook):
        print("There is no %s here." % a.workbook)
        print("Build one with:  python make_workbook.py")
        return 1

    tabs = workbook_tabs(a.workbook)
    if NEW_NAME not in tabs:
        print("%s is on the old layout -- its upload tab is still called "
              "\"%s\"." % (a.workbook, OLD_NAME))
        print("\nMove it across first. This keeps everything you have typed and "
              "writes a dated backup before it touches anything:")
        print("\n   python upgrade_workbook.py --go\n")
        print("Then run this again.")
        return 1

    # the Photos tab only exists in the --full layout, so this step is skipped
    # rather than failed when it is not there
    if ("Photos" in tabs and os.path.isdir("photos")
            and any(f.startswith("CRH-") for f in os.listdir("photos"))):
        if not run([sys.executable, "embed_photos.py", "--workbook", a.workbook],
                   "embed_photos.py"):
            return 1

    # A card typed straight into Inventory has no SKU, and without one it is
    # invisible to the eBay export, to photo filing and to the dashboard. This
    # only ever fills an EMPTY cell and never renumbers a card that has one, so
    # it is safe to do every run -- and doing it every run is the point, since
    # the failure it prevents is sixty cards silently not existing.
    if not run([sys.executable, "autofill.py", "--workbook", a.workbook, "--go"],
               "autofill.py"):
        return 1

    # a read-only tab per sport, rebuilt from Inventory each time
    if not run([sys.executable, "sport_tabs.py", "--workbook", a.workbook],
               "sport_tabs.py"):
        return 1

    args = [sys.executable, "export_inventory.py", "--workbook", a.workbook]
    if a.publish:
        args.append("--publish")
    if not run(args, "export_inventory.py"):
        return 1

    if not run([sys.executable, "build_all.py", ".", a.out], "build_all.py"):
        return 1

    print("\nDone. %s is rebuilt around what is in the workbook." % a.out)
    if not a.publish:
        print("Your costs and notes are in this copy and nowhere else -- "
              "inventory.json is gitignored.")
    else:
        print("inventory-public.json was refreshed too. Commit it to publish; "
              "it holds no cost, notes or lot.")

    if a.open:
        webbrowser.open("file:///" + os.path.abspath(a.out).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
