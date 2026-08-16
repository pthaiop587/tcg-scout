"""Tests for the open-in-Excel guard.

Run: python -m pytest test_inuse.py

This exists because the failure it prevents already happened. A script loads the
workbook, works for minutes, then saves; if Excel writes in that gap, one copy
wins silently. So the test that matters is not that the guard works in the
abstract -- it is that EVERY script which saves the workbook actually calls it.
A guard wired into nine scripts out of ten is a guard you trust and should not.
"""

import glob
import os
import re
import subprocess
import sys

import pytest

import inuse

# Every script that loads the workbook and saves it back.
WRITERS = [
    "autofill.py", "sport_tabs.py", "prices.py", "fill_blanks.py",
    "refresh.py", "make_ebay_csv.py", "add_card.py", "embed_photos.py",
    "add_photos.py", "upgrade_workbook.py", "file_batch.py",
    "make_workbook.py",
]


def test_the_lock_file_is_the_one_excel_actually_writes(tmp_path):
    """Excel names it "~$" plus the workbook's name, beside the workbook."""
    wb = tmp_path / "Card Run HQ - Master.xlsx"
    assert inuse.lockfile(str(wb)) == str(tmp_path / "~$Card Run HQ - Master.xlsx")


def test_a_closed_workbook_is_not_flagged(tmp_path):
    wb = tmp_path / "book.xlsx"
    wb.write_bytes(b"x")
    assert not inuse.is_open(str(wb))
    inuse.refuse_if_open(str(wb))      # must not raise


def test_an_open_workbook_stops_the_run(tmp_path):
    wb = tmp_path / "book.xlsx"
    wb.write_bytes(b"x")
    (tmp_path / "~$book.xlsx").write_bytes(b"lock")
    assert inuse.is_open(str(wb))
    with pytest.raises(SystemExit) as e:
        inuse.refuse_if_open(str(wb))
    msg = str(e.value)
    assert "open in Excel" in msg
    assert "Nothing has\nbeen changed" in msg


def test_it_says_what_to_do_about_it(tmp_path):
    """An error that does not say the fix just makes people run it again."""
    wb = tmp_path / "book.xlsx"
    wb.write_bytes(b"x")
    (tmp_path / "~$book.xlsx").write_bytes(b"lock")
    with pytest.raises(SystemExit) as e:
        inuse.refuse_if_open(str(wb))
    assert "close the workbook" in str(e.value).lower()


# --- the part that actually protects anything -------------------------------

@pytest.mark.parametrize("script", WRITERS)
def test_every_writer_checks_before_it_writes(script):
    src = open(script, encoding="utf-8").read()
    assert "import inuse" in src, "%s does not import the guard" % script
    assert "inuse.refuse_if_open" in src, "%s never calls the guard" % script


def test_no_writer_was_missed():
    """Anything that calls wb.save() and is not on the list is unguarded, and
    nobody would notice until it ate somebody's afternoon."""
    missed = []
    for path in sorted(glob.glob("*.py")):
        if path.startswith("test_") or path in ("inuse.py", "colleges.py"):
            continue
        src = open(path, encoding="utf-8").read()
        saves = re.search(r"\.save\(", src)
        if saves and path not in WRITERS and "inuse.refuse_if_open" not in src:
            missed.append(path)
    assert not missed, (
        "these save a workbook but never check whether Excel has it: %s"
        % ", ".join(missed))


def test_the_guard_actually_stops_a_real_script(tmp_path):
    """End to end: build a workbook, pretend Excel has it, run autofill."""
    wb = tmp_path / "Card Run HQ - Master.xlsx"
    subprocess.run([sys.executable, "make_workbook.py", "--out", str(wb)],
                   check=True, capture_output=True)
    before = wb.read_bytes()
    (tmp_path / "~$Card Run HQ - Master.xlsx").write_bytes(b"lock")

    r = subprocess.run([sys.executable, "autofill.py", "--workbook", str(wb),
                        "--go"], capture_output=True, text=True)
    assert r.returncode != 0
    assert "open in Excel" in (r.stdout + r.stderr)
    assert wb.read_bytes() == before, "the workbook was written anyway"
