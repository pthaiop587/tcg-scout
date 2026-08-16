"""One command: workbook in, dashboard out.

    python refresh.py          # export the workbook and rebuild the page
    python refresh.py --open   # ...and open it
    python refresh.py --publish   # also refresh the money-free public copy

Run this after typing into Card Run HQ - Master.xlsx. It does, in order:

    embed_photos.py      thumbnails into the workbook's Photos tab
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
NEEDED = {"Summary", "Purchases", "Expenses", "Photos", "Audit"}


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
    missing = NEEDED - tabs
    if missing:
        print("%s is on the old layout -- it has no %s tab."
              % (a.workbook, ", ".join(sorted(missing))))
        print("\nMove it across first. This keeps everything you have typed and "
              "writes a dated backup before it touches anything:")
        print("\n   python upgrade_workbook.py --go\n")
        print("Then run this again.")
        return 1

    if os.path.isdir("photos") and any(f.startswith("CRH-") for f in os.listdir("photos")):
        if not run([sys.executable, "embed_photos.py", "--workbook", a.workbook],
                   "embed_photos.py"):
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
