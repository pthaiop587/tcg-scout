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


def test_each_button_carries_a_set_and_a_sport(page):
    """Otherwise the pasted line has an empty set column and the card is
    orphaned from the box it came out of."""
    seen = set()
    for m in re.finditer(r'<button class="add"[^>]*>', page):
        tag = m.group(0)
        s = re.search(r'data-set="([^"]*)"', tag)
        k = re.search(r'data-sport="([^"]*)"', tag)
        assert s and s.group(1), tag
        assert k and k.group(1) in ("sports", "tcg"), tag
        seen.add(k.group(1))
    assert seen == {"sports", "tcg"}, (
        "both kinds of set should be on the sheet; got %s" % seen)


def test_a_pokemon_card_is_never_flagged_as_sports(page):
    """The last column decides the eBay category and the workbook's Category.
    A Pokemon card sent over as 'sports' lists under the wrong category with
    nothing looking wrong anywhere."""
    for m in re.finditer(r'<button class="add"[^>]*>', page):
        tag = m.group(0)
        st = re.search(r'data-set="([^"]*)"', tag).group(1)
        kind = re.search(r'data-sport="([^"]*)"', tag).group(1)
        if "Pokemon" in st or "Pokémon" in st:
            assert kind == "tcg", tag
        else:
            assert kind == "sports", tag


def test_the_sport_flag_agrees_with_autofills_category_map():
    """autofill.py decides Sports vs TCG from the game name. The rip sheet
    decides it from a hand-set field. They must not drift apart."""
    import autofill
    checked = 0
    for s in rs.SETS:
        hay = (s["set_line"] + " " + s["name"]).lower()
        for game, cat in autofill.CATEGORY_OF.items():
            if game in hay:
                want = "tcg" if cat == "TCG" else "sports"
                assert s["sport"] == want, (
                    "%s is %s to autofill.py but %r on the rip sheet"
                    % (s["name"], cat, s["sport"]))
                checked += 1
                break
    assert checked, "no set matched autofill's map -- the guard is asleep"


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


def test_the_pokemon_secret_rare_tell_is_spelled_out(page):
    """Sorting by card number finds every chase in the set in one pass. It is
    the most useful thing to know and nothing on the card says it."""
    assert "CARD NUMBER" in page
    assert "/084" in page


def test_prizm_draft_picks_are_not_called_rookie_cards(page):
    """A Draft Picks card is a college pre-rookie. Listing one as an RC earns
    a return, and it is the most common mistake with this set."""
    assert "not NFL rookie cards" in page
    assert "pre-rookie" in page


def test_the_pokemon_chases_are_named(page):
    for who in ("Mega Darkrai ex", "Mega Tyranitar ex", "Mega Absol ex"):
        assert who in page


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
