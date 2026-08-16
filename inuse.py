"""Refuse to write to a workbook Excel currently has open.

Every script here that changes the workbook does the same three things: load it,
work, save it. The work in the middle can take a while -- prices.py spends about
four minutes fetching pages between the load and the save.

If Excel has the file open across that gap, one of two saves wins and the other
is silently gone. It does not matter which order they happen in:

  - Excel saves during the gap, then the script saves the copy it loaded
    four minutes ago -- your typing is overwritten.
  - The script saves, then you press Ctrl+S in an Excel that has been holding a
    copy from before -- the script's work is overwritten.

Neither reports an error. Both look like the other side simply forgot.

This has already cost real work once, on 16 Aug 2026, so it is not a warning in
a runbook any more. Excel drops a lock file beside the workbook while it has it
open, named "~$" plus the workbook's name. If that file is there, the scripts
stop before touching anything.

You can type in the workbook as much as you like. This only asks that Excel is
not holding it at the moment a script writes to it.
"""

import os
import sys


def lockfile(workbook):
    """The file Excel drops beside a workbook it has open."""
    folder, name = os.path.split(os.path.abspath(workbook))
    return os.path.join(folder, "~$" + name)


def is_open(workbook):
    return os.path.exists(lockfile(workbook))


def refuse_if_open(workbook, doing="change"):
    """Stop, with something worth reading, if Excel has the workbook."""
    if not is_open(workbook):
        return
    name = os.path.basename(workbook)
    sys.exit(
        "\n%s is open in Excel, so this will not %s it.\n"
        "\n"
        "Not to be awkward: this script loads the workbook, works, then saves\n"
        "it back. If Excel saves in between, one of the two copies wins and\n"
        "the other is gone with no error. That has happened here before.\n"
        "\n"
        "Save your work, close the workbook, and run this again. Nothing has\n"
        "been changed.\n" % (name, doing))
