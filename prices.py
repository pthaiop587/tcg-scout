"""Look up what each card is worth raw, in a 9, and in a 10 -- and when one last sold.

    python prices.py --report            # match only; touch nothing
    python prices.py --limit 5           # try five, print what it found
    python prices.py --go                # fill the columns in

A price with no date beside it is the thing that loses money here. "$200" on a
PSA 10 reads as fact, but if the last one actually sold in April it is a
guess dressed as a number, and you will price a real card against it. So every
price column has a date column next to it, and the date is the date a card of
THAT grade last changed hands -- not the date this script ran.

Where the numbers come from: sportscardspro.com, which is the PriceCharting
family. Two kinds of page.

The set page lists every card and parallel with Ungraded, Grade 9 and PSA 10
side by side, so all three prices for all your cards come from one page load.
It lazy-loads as you scroll, so this scrolls until the row count stops moving.

The individual card page carries the sales themselves, dated, in tables under
#price_comparison. Those tables have no ids and no headings, and their ORDER is
the only thing separating ungraded from PSA 9 from PSA 10 -- which would break
silently the first time the site added a grade tier. So the grade is read out
of each listing's own title instead ("... PSA 10 #166"), and a row that names
no grade is a raw sale. Order is then only used as a cross-check.

The site blocks plain fetching, so this drives a real browser, one page at a
time with a pause between, which is what you would be doing by hand anyway. It
is roughly one page per card: slow, not heavy.

Nothing is written without --go, and --go never overwrites a price you typed
yourself unless you pass --overwrite.
"""

import argparse
import datetime as dt
import re
import sys
import time
from copy import copy

from openpyxl import load_workbook

WORKBOOK = "Card Run HQ - Master.xlsx"
BASE = "https://www.sportscardspro.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# The six columns this fills, in pairs. Appended to Inventory, never inserted:
# workbook_extra.py addresses Inventory by column letter.
PRICE_COLS = [
    ("Raw price", 11), ("Raw last sold", 12),
    ("PSA 9 price", 11), ("PSA 9 last sold", 13),
    ("PSA 10 price", 11), ("PSA 10 last sold", 14),
]
TIERS = ["raw", "psa9", "psa10"]
COL_OF = {"raw": ("Raw price", "Raw last sold"),
          "psa9": ("PSA 9 price", "PSA 9 last sold"),
          "psa10": ("PSA 10 price", "PSA 10 last sold")}

# Which console page a card lives on. Base cards and their parallels share one;
# named inserts get their own.
SET_SLUG = "football-cards-2025-panini-prizm-draft-picks"
INSERT_SLUG = {
    "student orientation": SET_SLUG + "-student-orientation",
    "fearless": SET_SLUG + "-fearless",
    "instant impact": SET_SLUG + "-instant-impact",
    "new recruits": SET_SLUG + "-new-recruits",
    "signing day": SET_SLUG + "-signing-day",
    "on campus": SET_SLUG + "-on-campus",
    "trophy hunting": SET_SLUG + "-trophy-hunting",
    "manga": SET_SLUG + "-manga",
}

# "Arch Manning [Gold Ice] #166", "Jaxson Dart #90 [RC]"
LABEL = re.compile(
    r"^(?P<name>.+?)\s*(?:\[(?P<par>[^\]]+)\]\s*)?#(?P<num>[\w.-]+)\s*"
    r"(?:\[RC\])?\s*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONEY = re.compile(r"\$\s*([\d,]+(?:\.\d{1,2})?)")

SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\.?$", re.I)


def norm(s):
    """A name two sources will agree on: no case, no punctuation, no suffix."""
    s = str(s or "").strip().lower()
    s = s.replace("&", "and")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = SUFFIX.sub("", s).strip()
    return s


def key(name, parallel, num):
    return (norm(name), norm(parallel), str(num or "").strip().lstrip("#"))


def money(txt):
    m = MONEY.search(str(txt or ""))
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def grade_of(title):
    """Which price tier a completed listing belongs to, from its own words.

    Read off the listing rather than off which table it sat in: the tables
    carry no ids, and a new grade tier appearing on the site would shift every
    index by one without anything failing."""
    t = " " + re.sub(r"\s+", " ", str(title or "")).lower() + " "
    if re.search(r"\b(psa|bgs|sgc|cgc|hga|tag)\s*10\b", t):
        return "psa10"
    if re.search(r"\bpsa\s*9(?!\s*\.)\b", t):
        return "psa9"
    # any other stated grade is a tier we do not track; not raw
    if re.search(r"\b(psa|bgs|sgc|cgc|hga|tag)\s*\d", t):
        return None
    if re.search(r"\b(graded|slab)\b", t):
        return None
    return "raw"


# --- the site ---------------------------------------------------------------

def harvest_console(pg, slug, settle=3):
    """Every card on a set page: label -> (link, ungraded, g9, psa10).

    The table lazy-loads, so scroll until the row count stops moving."""
    pg.goto("%s/console/%s" % (BASE, slug), wait_until="domcontentloaded",
            timeout=60000)
    pg.wait_for_timeout(2000)
    if not pg.locator("#games_table").count():
        return {}
    # The table appends as you reach the bottom. Stopping early is silent --
    # you get a partial index and cards "miss" for no visible reason, and not
    # the same ones twice. So: keep going until the count has held still for
    # several checks, with a hard ceiling so a broken page cannot spin here.
    seen, stable, spins = -1, 0, 0
    while stable < settle and spins < 400:
        spins += 1
        pg.keyboard.press("End")
        pg.mouse.wheel(0, 40000)
        pg.wait_for_timeout(650)
        n = pg.locator("#games_table tbody tr").count()
        if n == seen:
            stable += 1
        else:
            stable, seen = 0, n

    rows = pg.evaluate("""() => {
      const out = [];
      document.querySelectorAll('#games_table tbody tr').forEach(tr => {
        const td = tr.querySelectorAll('td');
        if (td.length < 5) return;
        const a = tr.querySelector('a');
        out.push({label: td[1].innerText.trim(),
                  href: a ? a.getAttribute('href') : '',
                  ungraded: td[2].innerText.trim(),
                  g9: td[3].innerText.trim(),
                  psa10: td[4].innerText.trim()});
      });
      return out;
    }""")

    idx, bynum, noname = {}, {}, {}
    for r in rows:
        m = LABEL.match(r["label"])
        if not m:
            continue
        nm, par, num = m.group("name"), m.group("par") or "", m.group("num")
        r["site_name"] = nm.strip()
        idx.setdefault(key(nm, par, num), r)
        # Insert sets number their cards differently from the base set
        # (#II-SSS, not #18), so keep a way in that ignores the number too.
        noname.setdefault((norm(nm), norm(par)), r)
        # Card number and parallel identify a card on their own inside a set.
        # The NAME is the part that gets mistyped, so keep a way in that does
        # not depend on it.
        bynum.setdefault((norm(par), str(num).strip().lstrip("#")), r)
    return {"byname": idx, "bynum": bynum, "noname": noname}


def slug(s):
    s = norm(s).replace(" ", "-")
    return re.sub(r"-+", "-", s).strip("-")


def card_url(set_slug, name, parallel, num):
    """The card page URL, built rather than looked up.

    The set page appends rows as you scroll and does not always finish, so an
    index built from it is missing a different handful every run. This does
    not depend on it."""
    bits = [slug(name)]
    if parallel:
        bits.append(slug(parallel))
    bits.append(str(num).strip().lstrip("#").lower())
    return "%s/game/%s/%s" % (BASE, set_slug, "-".join(bits))


def card_page(pg, url, delay):
    """Prices and the most recent sale date per tier, from one card page.

    Prices come from here rather than the set page so that a card missing from
    the index still gets its numbers, and so the two can never disagree."""
    r = pg.goto(url, wait_until="domcontentloaded", timeout=60000)
    if r is not None and r.status >= 400:
        time.sleep(delay)
        return None, {}
    pg.wait_for_timeout(1200)

    # PriceCharting inherits its field names from video games; these are the
    # ids the card grades actually land in.
    prices = pg.evaluate("""() => {
      const get = id => {
        const el = document.querySelector(id);
        return el ? el.innerText.trim() : '';
      };
      return {raw: get('#used_price'), psa9: get('#graded_price'),
              psa10: get('#manual_only_price')};
    }""")
    prices = {k: money(v) for k, v in prices.items()}

    rows = pg.evaluate("""() => {
      const out = [];
      document.querySelectorAll('#price_comparison table tr').forEach(tr => {
        const td = tr.querySelectorAll('td');
        if (td.length < 4) return;
        out.push({date: td[0].innerText.trim(),
                  title: td[2].innerText.trim(),
                  price: td[3].innerText.trim()});
      });
      return out;
    }""")

    best = {}
    for r in rows:
        d = r["date"].split("\n")[0].strip()
        if not DATE.match(d):
            continue
        g = grade_of(r["title"])
        if g and (g not in best or d > best[g]):
            best[g] = d
    time.sleep(delay)
    return prices, best


# --- the workbook -----------------------------------------------------------

def ensure_columns(ws):
    """Append any missing price column. Appending matters: workbook_extra.py
    addresses Inventory by letter, so an insert moves every formula."""
    hdr = [c.value for c in ws[1]]
    added = []
    for name, width in PRICE_COLS:
        if name in hdr:
            continue
        col = len(hdr) + 1
        c = ws.cell(row=1, column=col, value=name)
        base = ws.cell(row=1, column=1)
        # openpyxl hands back a StyleProxy, which cannot be assigned onward
        c.font = copy(base.font)
        c.fill = copy(base.fill)
        c.alignment = copy(base.alignment)
        from openpyxl.utils import get_column_letter
        ws.column_dimensions[get_column_letter(col)].width = width
        hdr.append(name)
        added.append(name)
    return hdr, added


def read_cards(ws, hdr, sport):
    g = {n: i for i, n in enumerate(hdr)}
    out = []
    for r in range(2, ws.max_row + 1):
        vals = [c.value for c in ws[r]]
        vals += [None] * (len(hdr) - len(vals))
        name = vals[g["Player or card name"]]
        if not name or not str(name).strip():
            continue
        if sport and str(vals[g.get("Sport or game", 0)] or "").strip().lower() \
                != sport.lower():
            continue
        out.append({
            "row": r, "name": str(name).strip(),
            "num": str(vals[g["Card #"]] or "").strip(),
            "parallel": str(vals[g["Parallel"]] or "").strip(),
            "insert": str(vals[g["Insert set"]] or "").strip(),
            "sku": vals[g["SKU"]],
        })
    return out


def main():
    p = argparse.ArgumentParser(
        description="Fill raw / PSA 9 / PSA 10 prices and last-sold dates.")
    p.add_argument("--workbook", default=WORKBOOK)
    p.add_argument("--sport", default="Football")
    p.add_argument("--limit", type=int, help="only the first N cards")
    p.add_argument("--delay", type=float, default=1.5,
                   help="seconds between card pages (default 1.5)")
    p.add_argument("--report", action="store_true",
                   help="match against the site and say what it found; no dates, no writing")
    p.add_argument("--go", action="store_true", help="write the values in")
    p.add_argument("--overwrite", action="store_true",
                   help="replace values already in the price columns")
    p.add_argument("--fix-names", action="store_true",
                   help="rewrite mistyped player names to the site's spelling")
    a = p.parse_args()

    wb = load_workbook(a.workbook)
    ws = wb["Inventory"]
    hdr, added = ensure_columns(ws)
    cards = read_cards(ws, hdr, a.sport)
    if a.limit:
        cards = cards[:a.limit]
    if not cards:
        sys.exit("no %s cards found in %s" % (a.sport, a.workbook))
    print("%d %s card(s)%s" % (len(cards), a.sport,
                               "; added columns: " + ", ".join(added) if added else ""))

    from playwright.sync_api import sync_playwright
    g = {n: i for i, n in enumerate(hdr)}
    found = missed = 0
    typos = []          # matched by number, but the name you typed differs

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(user_agent=UA)

        consoles = {}
        wanted = {(c["insert"] or "").strip().lower() for c in cards}
        for ins in sorted(wanted):
            slug = INSERT_SLUG.get(ins, SET_SLUG) if ins else SET_SLUG
            if slug in consoles:
                continue
            consoles[slug] = harvest_console(pg, slug)
            print("   set page %-58s %4d card(s)"
                  % (slug, len(consoles[slug].get("byname", {}))))

        for c in cards:
            ins = (c["insert"] or "").strip().lower()
            set_slug = INSERT_SLUG.get(ins, SET_SLUG) if ins else SET_SLUG
            order = [set_slug] + [s for s in consoles if s != set_slug]
            nk = key(c["name"], c["parallel"], c["num"])
            numk = (norm(c["parallel"]), str(c["num"]).strip().lstrip("#"))

            hit = None
            for s in order:
                hit = (consoles.get(s) or {}).get("byname", {}).get(nk)
                if hit:
                    break
            if not hit:                       # name mistyped: go by number
                for s in order:
                    hit = (consoles.get(s) or {}).get("bynum", {}).get(numk)
                    if hit:
                        break
                if hit:
                    typos.append((c["sku"], c["name"], hit["site_name"],
                                  c["parallel"], c["num"], c["row"]))
            if not hit:                       # insert numbering differs
                for s in order:
                    hit = (consoles.get(s) or {}).get("noname", {}).get(
                        (norm(c["name"]), norm(c["parallel"])))
                    if hit:
                        break

            if a.report:
                # fast sanity check: index only, no card pages
                if not hit:
                    missed += 1
                    print("   MISS %-9s %-22s %-10s #%s"
                          % (c["sku"], c["name"], c["parallel"], c["num"]))
                    continue
                found += 1
                print("   %-9s %-22s %-9s raw %-8s 9 %-8s 10 %s"
                      % (c["sku"], c["name"][:22], c["parallel"],
                         money(hit["ungraded"]), money(hit["g9"]),
                         money(hit["psa10"])))
                continue

            # The card page is the source of truth: it carries the dates, and
            # taking the prices from the same page means the two can never
            # disagree. The index is only consulted for a URL it may not have.
            urls = []
            if hit:
                h = hit["href"]
                urls.append(h if h.startswith("http") else BASE + h)
            urls.append(card_url(set_slug, c["name"], c["parallel"], c["num"]))
            if set_slug != SET_SLUG:
                urls.append(card_url(SET_SLUG, c["name"], c["parallel"],
                                     c["num"]))

            prices, dates = None, {}
            for u in urls:
                prices, dates = card_page(pg, u, a.delay)
                if prices and any(v is not None for v in prices.values()):
                    break
            if not prices or not any(v is not None for v in prices.values()):
                missed += 1
                print("   MISS %-9s %-22s %-10s #%s"
                      % (c["sku"], c["name"], c["parallel"], c["num"]))
                continue

            found += 1
            print("   %-9s %-22s %-9s raw %-8s 9 %-8s 10 %-8s  %s"
                  % (c["sku"], c["name"][:22], c["parallel"],
                     prices["raw"], prices["psa9"], prices["psa10"],
                     " ".join("%s=%s" % (t, dates.get(t, "-")) for t in TIERS)))

            if not a.go:
                continue
            for tier in TIERS:
                pcol, dcol = COL_OF[tier]
                cell = ws.cell(row=c["row"], column=g[pcol] + 1)
                if prices[tier] is not None and (a.overwrite or cell.value in (None, "")):
                    cell.value = prices[tier]
                    cell.number_format = '"$"#,##0.00'
                d = dates.get(tier)
                cell = ws.cell(row=c["row"], column=g[dcol] + 1)
                if d and (a.overwrite or cell.value in (None, "")):
                    cell.value = dt.date.fromisoformat(d)
                    cell.number_format = "yyyy-mm-dd"
        b.close()

    print("\nmatched %d, missed %d" % (found, missed))

    if typos:
        print("\n%d card(s) matched on number and parallel but the name you "
              "typed does not match the site.\nThe price is right -- the "
              "spelling is what matters, because an eBay title nobody\nsearches "
              "for is a card nobody finds:" % len(typos))
        print("   %-9s %-24s %-24s %s" % ("SKU", "you typed", "site has", "card"))
        for sku, mine, theirs, par, num, _row in typos:
            print("   %-9s %-24s %-24s %s #%s" % (sku, mine, theirs, par, num))
        if a.fix_names and a.go:
            col = g["Player or card name"] + 1
            for sku, mine, theirs, _par, _num, row in typos:
                ws.cell(row=row, column=col, value=theirs)
            print("   -> rewritten to the site's spelling.")
        elif not a.fix_names:
            print("   Add --fix-names (with --go) to correct them in place.")
    if a.go:
        wb.save(a.workbook)
        print("Saved %s. Run sport_tabs.py to push these onto the game tabs."
              % a.workbook)
    else:
        print("Nothing written. Add --go to fill the columns in.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
