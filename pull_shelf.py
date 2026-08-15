"""Pull every set that could still be sitting on a retail shelf, with sealed
prices and the set's chase card. Output feeds the in-store lookup dashboard."""
import json, urllib.request, datetime, sys, re

BASE = "https://tcgcsv.com/tcgplayer"
CATS = {3: "Pokemon", 68: "One Piece", 71: "Lorcana", 1: "Magic",
        # everything else on a GameStop / Target card wall
        2: "YuGiOh", 63: "Digimon", 79: "Star Wars Unlimited",
        80: "Dragon Ball Fusion World", 81: "Union Arena",
        86: "Gundam", 89: "Riftbound"}
CUTOFF = "2025-01-01"          # ~19 months back: realistic shelf life
# Magic prints far more sets than the others; a tighter window keeps the pull
# (and the 4x-daily CI build) from ballooning. Same for the newer additions.
CUTOFF_BY_GAME = {"Magic": "2026-01-01", "YuGiOh": "2025-06-01",
                  "Digimon": "2025-06-01", "Star Wars Unlimited": "2025-06-01",
                  "Dragon Ball Fusion World": "2025-06-01",
                  "Union Arena": "2025-06-01", "Gundam": "2025-06-01",
                  "Riftbound": "2025-06-01"}

# Games with a verified MSRP table below. Everything else comes through as
# market-price-only -- still useful in a shop, where you compare the market
# figure to the tag in front of you.
MSRP_GAMES = {"Pokemon", "One Piece", "Lorcana"}
TODAY = datetime.date.today()
JUNK = ("pop series", "miscellaneous", "alternate art promos", "nintendo promos",
        "trainer kit", "blister exclusives", "first partner pack", "prerelease",
        # Magic supplements that never sit on a retail shelf as sealed product
        "art series", "minigame", "substitute card", "source material",
        "tokens", "front cards", "the list")

def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "tcg-scout/0.3"})
            with urllib.request.urlopen(req, timeout=45) as r:
                d = json.loads(r.read().decode())
            return d.get("results", d) if isinstance(d, dict) else d
        except Exception:
            if i == tries - 1:
                raise
    return []

def ext(p, key):
    for e in (p.get("extendedData") or []):
        if e.get("name") == key:
            return e.get("value")
    return None

# --- retail price by product type. Only verified figures; None = don't claim one.
def msrp_for(game, name, set_name=""):
    n = name.lower()
    if "case" in n or ("display" in n and "mini tin display" not in n):
        return None                     # distributor units, not shelf items
    # multi-packs: a bundle of N units priced against one unit's retail is a lie
    if "[set of" in n or re.search(r"s \d+[- ]pack", n) or " + " in n:
        return None
    if game == "Pokemon":
        # Pokemon Center ETBs carry their own higher retail
        if "elite trainer box" in n:
            return 59.99 if "pokemon center" in n else 49.99
        if "booster bundle" in n:
            return 26.94                # Mega Evolution era
        if re.search(r"\bbooster box\b", n):
            return 179.64 if "pokemon center" in n else 143.64   # 36 packs
        if "mini tin display" in n:
            return 79.92                # 8-count
        if "mini tin" in n:
            return 9.99
        if "3 pack blister" in n or "3-pack blister" in n:
            return 13.99
        if "special tin" in n:
            return 24.99
        if "premium collection" in n and "ultra" not in n and "super" not in n:
            return 39.99
        if "super-premium collection" in n or "super premium collection" in n:
            return 89.99
        # Ultra-Premium Collection retail is a $119.99-169.99 range -> no claim
    if game == "One Piece":
        if re.search(r"\bbooster box\b", n) and "case" not in n:
            return 119.76          # 24 x 4.99
        if "booster pack" in n and "case" not in n and "sleeved" not in n:
            return 4.99
        if "starter deck" in n and "display" not in n and "case" not in n:
            return 11.99
    if game == "Lorcana":
        if re.search(r"\bbooster box\b", n) and "case" not in n:
            return 143.76          # 24 x 5.99
        if "booster pack" in n and "case" not in n and "sleeved" not in n:
            return 5.99
        if "illumineer's trove" in n and "case" not in n:
            return 49.99
    if game == "Magic":
        # Wizards stopped publishing MSRPs -- retailers set their own price, so
        # for Magic there is usually no sticker to divide by. Only products with
        # a genuine published list price get one; everything else comes through
        # with retail=None and is shown as market price only.
        if "draft night" in n:
            # Same box (12 Play + 1 Collector + 90 lands), two price points:
            # Universes Beyond carries a premium. Verified 15 Aug 2026 --
            # TMNT and The Hobbit at $119.99, Lorwyn Eclipsed at $89.99.
            return 119.99 if is_universes_beyond(set_name) else 89.99
    return None


# Universes Beyond = licensed crossover sets, priced above standard Magic.
UB_SETS = ("teenage mutant ninja turtles", "the hobbit", "marvel super heroes",
           "star trek", "final fantasy", "spider-man", "avatar", "assassin's creed",
           "fallout", "doctor who", "jurassic world", "warhammer")

def is_universes_beyond(set_name):
    s = (set_name or "").lower()
    return any(u in s for u in UB_SETS)

rows, sets_meta = [], []
for cat, game in CATS.items():
    groups = [g for g in get(f"{BASE}/{cat}/groups") if g.get("publishedOn")]
    # TCGCSV sometimes stamps publishedOn with the crawl time instead of a
    # release date (19/217 Pokemon groups, all POP Series). Real release dates
    # are exactly midnight; drop the artifacts rather than let them look new.
    groups = [g for g in groups if g["publishedOn"].endswith("T00:00:00")]
    groups = [g for g in groups if g["publishedOn"][:10] >= CUTOFF_BY_GAME.get(game, CUTOFF)]
    groups = [g for g in groups if not any(j in g["name"].lower() for j in JUNK)]
    groups.sort(key=lambda g: g["publishedOn"])
    print(f"{game}: {len(groups)} sets", file=sys.stderr)

    for g in groups:
        gid, sname = g["groupId"], g["name"]
        try:
            prods = get(f"{BASE}/{cat}/{gid}/products")
            prices = get(f"{BASE}/{cat}/{gid}/prices")
        except Exception as e:
            print(f"  !! {sname}: {e}", file=sys.stderr); continue

        pm = {}
        for r in prices:
            mp = r.get("marketPrice")
            if mp and mp > pm.get(r["productId"], 0):
                pm[r["productId"]] = mp

        chase, best = None, 0.0
        for p in prods:
            mp = pm.get(p["productId"])
            if not mp or ext(p, "Number") is None:
                continue
            if mp > best:
                best, chase = mp, {"name": p["name"], "price": mp,
                                   "rarity": ext(p, "Rarity")}

        rel = g["publishedOn"][:10]
        y, m, d = map(int, rel.split("-"))
        age = (TODAY - datetime.date(y, m, d)).days
        sets_meta.append({"game": game, "set": sname, "released": rel,
                          "age": age, "chase": chase})

        for p in prods:
            mp = pm.get(p["productId"])
            if not mp or ext(p, "Number") is not None:
                continue
            nm = p["name"]
            nl = nm.lower()
            if "code card" in nl or "don!!" in nl:
                continue
            # Distributor units, not things you find on a shelf. The MSRP table
            # already returns None for these, but Magic rows are allowed through
            # without an MSRP, so they need an explicit gate.
            if "case" in nl or "[set of" in nl or "master" in nl:
                continue
            retail = msrp_for(game, nm, sname)
            # No verified MSRP is still worth showing for Magic, where Wizards
            # publishes none: market price plus links beats omitting the product.
            # Everywhere else a missing MSRP means we could not verify it, and a
            # row with no sticker and no ratio would just be noise.
            if not retail and game in MSRP_GAMES:
                continue
            rows.append({
                "game": game, "set": sname, "released": rel, "age": age,
                "product": nm,
                "retail": round(retail, 2) if retail else None,
                "market": round(mp, 2),
                "ratio": round(mp / retail, 2) if retail else None,
                "chase": chase["name"] if chase else None,
                "chasePrice": round(chase["price"], 2) if chase else None,
                "chaseRarity": chase["rarity"] if chase else None,
            })

rows.sort(key=lambda r: (r["ratio"] is None, -(r["ratio"] or 0)))
json.dump({"rows": rows, "sets": sets_meta}, open(sys.argv[1], "w"), indent=1)
_priced = sum(1 for r in rows if r["ratio"] is not None)
print(f"\nrows: {len(rows)}  ({_priced} with a verified MSRP, "
      f"{len(rows)-_priced} market-price-only)   sets: {len(sets_meta)}", file=sys.stderr)
