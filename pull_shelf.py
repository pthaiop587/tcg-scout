"""Pull every set that could still be sitting on a retail shelf, with sealed
prices and the set's chase card. Output feeds the in-store lookup dashboard."""
import json, urllib.request, datetime, sys, re

BASE = "https://tcgcsv.com/tcgplayer"
CATS = {3: "Pokemon", 68: "One Piece", 71: "Lorcana"}
CUTOFF = "2025-01-01"          # ~19 months back: realistic shelf life
TODAY = datetime.date.today()
JUNK = ("pop series", "miscellaneous", "alternate art promos", "nintendo promos",
        "trainer kit", "blister exclusives", "first partner pack", "prerelease")

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
def msrp_for(game, name):
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
    return None

rows, sets_meta = [], []
for cat, game in CATS.items():
    groups = [g for g in get(f"{BASE}/{cat}/groups") if g.get("publishedOn")]
    groups = [g for g in groups if g["publishedOn"][:10] >= CUTOFF]
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
            if "code card" in nm.lower() or "don!!" in nm.lower():
                continue
            retail = msrp_for(game, nm)
            if not retail:
                continue
            rows.append({
                "game": game, "set": sname, "released": rel, "age": age,
                "product": nm, "retail": round(retail, 2), "market": round(mp, 2),
                "ratio": round(mp / retail, 2),
                "chase": chase["name"] if chase else None,
                "chasePrice": round(chase["price"], 2) if chase else None,
                "chaseRarity": chase["rarity"] if chase else None,
            })

rows.sort(key=lambda r: -r["ratio"])
json.dump({"rows": rows, "sets": sets_meta}, open(sys.argv[1], "w"), indent=1)
print(f"\nrows with verified retail: {len(rows)}   sets: {len(sets_meta)}", file=sys.stderr)
