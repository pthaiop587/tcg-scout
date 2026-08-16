"""Tests for the rip sheet.

Run: python -m pytest test_ripsheet.py

The sheet's whole job is to hand cards to the workbook. It copies six cells,
tab separated, and you paste them onto the Year cell of an Inventory row --
which only works because those six columns sit next to each other, in that
order, on that tab. Reorder Inventory and there is no error: every pasted card
lands with the parallel in the insert column and the name in the parallel. So
the first test reads the real order out of make_workbook.py and compares,
rather than restating it, which is the only version that can fail when it
should.

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


# --- the contract with the workbook ----------------------------------------

def test_the_six_columns_are_contiguous_on_the_inventory_tab():
    """The sheet copies six tab-separated cells and you paste them onto the
    Year cell. That only works if those six sit next to each other, in that
    order, on Inventory. Reorder Inventory and the paste silently puts the
    parallel in the insert column -- so read the real order and compare."""
    import make_workbook as mw

    names = [n for n, _w in mw.INVENTORY_COLS]
    first = names.index(rs.FIRST_COL)
    assert names[first:first + len(rs.INVENTORY_COLS)] == rs.INVENTORY_COLS, (
        "Inventory's columns have moved. ripsheet.INVENTORY_COLS must match "
        "the run starting at %r, or every pasted card lands shifted."
        % rs.FIRST_COL)


def test_the_line_builder_emits_those_six_in_that_order():
    """lineFor() lives in a JS string, so read it rather than trusting it."""
    m = re.search(r"function lineFor\(p\)\{\s*return \[(.+?)\]", rs.JS, re.S)
    assert m, "lineFor() has moved -- the order guard cannot see it"
    parts = [x.strip() for x in m.group(1).split(",")]
    assert len(parts) == len(rs.INVENTORY_COLS) == 6
    assert parts[0] == "p.year"
    assert parts[1] == "p.brand"
    assert parts[2] == "''"                    # Insert set, left for you
    assert parts[3].startswith("p.variant")
    assert parts[4].startswith("p.name")
    assert parts[5].startswith("p.number")


def test_it_is_tab_separated_not_pipes():
    """Excel splits a paste on tabs. A pipe would land the whole row in one
    cell, which looks like it worked until you scroll right."""
    assert "join('\t')" in rs.JS
    assert "' | '" not in rs.JS


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


def test_it_says_where_to_paste(page):
    """A copy button with no destination is a dead end."""
    assert "Year" in page and "Inventory" in page


def test_it_does_not_pretend_to_know_prices(page):
    """Baked-in prices go stale and would be trusted. There are none."""
    assert "look up anything numbered" in page


# --- the content that earns its place ---------------------------------------

def test_every_line_can_be_ticked(page):
    n = sum(len(g["items"]) for s in rs.SETS for g in s["groups"])
    assert page.count('class="add"') == n
    assert n > 40


def test_each_button_carries_a_set_and_a_sport(page):
    """Otherwise the pasted row has an empty year or set column and the card is
    orphaned from the box it came out of."""
    seen = set()
    for m in re.finditer(r'<button class="add"[^>]*>', page):
        tag = m.group(0)
        y = re.search(r'data-year="([^"]*)"', tag)
        s = re.search(r'data-brand="([^"]*)"', tag)
        k = re.search(r'data-sport="([^"]*)"', tag)
        assert y and y.group(1).isdigit(), tag
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
        st = re.search(r'data-brand="([^"]*)"', tag).group(1)
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
        hay = (s["brand"] + " " + s["name"]).lower()
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
               "year": "2026", "brand": "S", "sport": "sports",
               "groups": [{"title": "t", "items": [{"v": "a & b"}]}]}
    body = rs.render([hostile])
    assert "<script>bad()</script>" not in body
    assert "&lt;script&gt;" in body
    assert "a &amp; b" in body
