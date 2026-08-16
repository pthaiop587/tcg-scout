"""Tests for the rip sheet.

Run: python -m pytest test_ripsheet.py

The sheet's whole job is to hand cards to the card desk. It writes lines in a
pipe-separated order and the desk reads them back by position -- f[0] is the
name, f[3] is the parallel, and nothing in either file says so out loud. Swap
two columns on one side only and there is no error: cards import happily with
the parallel in the condition slot and the worth in the quantity. So the first
test here reads the ORDER OUT OF hq.js and compares it, rather than restating
it, which is the only version of that test that can fail when it should.

The second thing worth guarding is that the page works with no network. It gets
opened on a phone, on a table, next to a pile of cards, quite possibly in a shop
with no signal. A stylesheet or font pulled from a CDN would leave it unreadable
exactly when it is needed.
"""

import re
import subprocess
import sys

import pytest

import ripsheet as rs


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    out = tmp_path_factory.mktemp("rip") / "sheet.html"
    r = subprocess.run([sys.executable, "ripsheet.py", "--out", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return out.read_text(encoding="utf-8")


# --- the contract with the card desk ----------------------------------------

def desk_field_order():
    """Pull the positional meaning of each f[N] out of the desk's parser."""
    js = open("hq.js", encoding="utf-8").read()
    block = js[js.index("const mnImp"):]
    block = block[:block.index("cdSave()")]

    order = {}
    # f[0] is checked for emptiness, the rest are read into named properties
    for prop, idx in re.findall(r"(\w+)\s*:\s*f\[(\d)\]", block):
        order[int(idx)] = prop
    for idx, expr in re.findall(r"f\[(\d)\]\s*\|\|\s*'([^']*)'", block):
        order.setdefault(int(idx), "?")
    # the ones that go through a variable first
    if re.search(r"cond\s*=\s*\(f\[4\]", block):
        order[4] = "c"
    if re.search(r"parseFloat\(f\[6\]\)", block):
        order[6] = "v"
    if re.search(r"f\[7\]", block):
        order[7] = "kind"
    if re.search(r"parseFloat\(f\[5\]\)", block):
        order[5] = "q"
    if re.search(r"!f\[0\]", block):
        order[0] = "n"
    return order


def test_the_desk_still_reads_eight_fields():
    o = desk_field_order()
    assert sorted(o) == [0, 1, 2, 3, 4, 5, 6, 7], o
    assert len(rs.PASTE_FIELDS) == 8


def test_field_order_matches_the_desk_position_by_position():
    """If either side is reordered, this is the test that goes red."""
    o = desk_field_order()
    expect = {0: "n", 1: "s", 2: "num", 3: "var", 4: "c", 5: "q", 6: "v",
              7: "kind"}
    assert o == expect, (
        "hq.js now reads the pasted line differently. ripsheet.PASTE_FIELDS "
        "and lineFor() in its JS must be reordered to match, or every card "
        "imported from a rip sheet lands with its columns shifted.")


def test_the_sheets_own_line_builder_uses_that_same_order():
    """lineFor() lives in a JS string, so read it the same way."""
    m = re.search(r"function lineFor\(p\)\{\s*return \[(.+?)\]", rs.JS,
                  re.S)
    assert m, "lineFor() has moved -- the order guard cannot see it"
    parts = [p.strip() for p in m.group(1).split(",")]
    assert parts[0].startswith("p.name")
    assert parts[1] == "p.set"
    assert parts[2].startswith("p.number")
    assert parts[3].startswith("p.variant")
    assert parts[4] == "'NM'"
    assert parts[5] == "'1'"
    assert parts[6].startswith("p.worth")
    assert parts[7] == "p.sport"


# --- it has to work on a phone with no signal -------------------------------

def test_nothing_is_fetched_from_the_network(page):
    for bad in ("http://", "https://", "//cdn", "<link", "@import"):
        assert bad not in page, "%r would break the sheet offline" % bad


def test_it_is_one_self_contained_file(page):
    assert "<style>" in page and "<script>" in page
    assert "src=" not in page


def test_it_says_it_saves_nothing(page):
    """It genuinely does not persist, so it has to say so before you close it."""
    assert "close the page" in page.lower() or "nothing is saved" in page.lower()


def test_it_does_not_pretend_to_know_prices(page):
    """Baked-in prices go stale and would be trusted. There are none."""
    assert "look up anything numbered" in page


# --- the content that earns its place ---------------------------------------

def test_every_line_can_be_ticked(page):
    n = sum(len(g["items"]) for s in rs.SETS for g in s["groups"])
    assert page.count('class="add"') == n
    assert n > 40


def test_each_button_carries_the_set_and_sport(page):
    """Otherwise the pasted line has an empty set column and the card is
    orphaned from the box it came out of."""
    for m in re.finditer(r'<button class="add"[^>]*>', page):
        tag = m.group(0)
        assert 'data-set="2026 Topps' in tag, tag
        assert 'data-sport="sports"' in tag, tag


def test_the_short_print_trap_is_spelled_out(page):
    """#697-700 look like base cards. This is the single most losable card in
    the box, so the sheet must name both versions."""
    for who in ("Kevin McGonigle", "JJ Wetherholt", "Carson Benge",
                "Justin Crawford"):
        assert who in page
    for standard in ("Bryan Reynolds", "Andre Pallante", "Jared Young",
                     "Freddie Freeman"):
        assert standard in page
    assert "#697" in page


def test_the_chrome_black_pack_warning_is_present(page):
    """A loose pack has had the guaranteed encased auto removed already."""
    assert "encased" in page
    assert "HOBBY BOX" in page


def test_serial_numbers_are_pointed_at_the_back_of_the_card(page):
    assert "back" in page.lower()


def test_asg_parallel_tiers_are_all_there(page):
    for tier in ("/99", "/50", "/25", "/10", "/5", "1/1"):
        assert tier in page


# --- the generator ----------------------------------------------------------

def test_one_set_at_a_time(tmp_path):
    out = tmp_path / "one.html"
    r = subprocess.run([sys.executable, "ripsheet.py", "--set", "asg",
                        "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    body = out.read_text(encoding="utf-8")
    assert "All-Star Game" in body
    assert "Chrome Black" not in body


def test_an_unknown_set_is_refused_by_name(tmp_path):
    r = subprocess.run([sys.executable, "ripsheet.py", "--set", "nope",
                        "--out", str(tmp_path / "x.html")],
                       capture_output=True, text=True)
    assert r.returncode != 0
    assert "asg" in r.stdout + r.stderr


def test_list_names_every_set():
    r = subprocess.run([sys.executable, "ripsheet.py", "--list"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    for s in rs.SETS:
        assert s["key"] in r.stdout


def test_markup_in_a_set_name_cannot_break_the_page():
    hostile = {"key": "x", "name": "<script>bad()</script>", "sub": "s",
               "set_line": "S", "sport": "sports",
               "groups": [{"title": "t", "items": [{"v": "a & b"}]}]}
    body = rs.render([hostile])
    assert "<script>bad()</script>" not in body
    assert "&lt;script&gt;" in body
    assert "a &amp; b" in body
