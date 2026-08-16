# Card Run HQ — runbook

## ⭐ PUBLIC URL, refreshes itself 4× a day (15 Aug 2026)

**https://pthaiop587.github.io/tcg-scout/**

Public, no login, works on any phone. **Bookmark this one** — it is the shopping URL.

A GitHub Action (`.github/workflows/refresh.yml`) runs at **6am, noon, 6pm and
midnight Pacific**, pulls fresh prices from TCGCSV, rebuilds and redeploys. Nothing on
your machine needs to be running, and I don't need to be involved.

- Force a refresh now: repo → **Actions → Refresh Card Run HQ → Run workflow**
- Or `gh workflow run refresh.yml --repo pthaiop587/tcg-scout`
- The build fails loudly if the page comes out under 300 KB, so a silently broken
  pull can't overwrite a good page with a stub.

⚠ **The repo is now PUBLIC** — that is what makes free Pages possible. The map marker
is labelled `91786` rather than `HOME` for that reason.

⚠ **GitHub disables scheduled workflows after 60 days of repository inactivity.** If
the dashboard ever stops updating, that is the first thing to check — pushing any
commit re-enables it.

### The private artifact still exists

https://claude.ai/code/artifact/b2545d8c-69cc-4284-bc6c-cda0b061e88f — same page, but
private, hand-republished, and under a CSP that blocks outside requests. The Pages URL
is better for everything except privacy.

---

## The master workbook and eBay uploads

`Card Run HQ - Master.xlsx` in this folder is the real record. It is
**gitignored on purpose** — the repo is public and the workbook holds the
inventory, what each box cost and what each card sold for. CI generates a
blank one for the dashboard's download link; your filled-in copy never leaves
this machine.

| Script | What it does |
|---|---|
| `python make_workbook.py` | Builds a fresh workbook. Refuses to overwrite without `--force`. |
| `python add_card.py --player "..." --year 2025 --brand "..." ...` | Appends one card to Inventory and assigns the next SKU. |
| `python make_ebay_csv.py` | Writes `ebay-upload-<date>.csv` from every Inventory row marked **Unlisted**, and rewrites the workbook's eBay upload tab to match. `--sku CRH-0001` for one card, `--all` to ignore status. |

### Before the first upload

eBay **retired File Exchange**. Bulk uploads now go through
**Seller Hub → Reports → Uploads**. The header row there is tied to your
account and to the template version, so a header copied out of documentation
can be rejected even when every value under it is correct.

1. Download the Trading Card Singles template from Seller Hub → Reports → Uploads.
2. Save it in this folder as `ebay-template.csv`.
3. Re-run `make_ebay_csv.py` — it conforms to that header column for column and
   prints which header it used. Without the file it says so plainly.
4. **Upload one card first** and read the results report before doing a batch.

### The codes that actually reject uploads

Category `261328` sports singles, `183050` non-sport singles, `183454` CCG.
Condition `2750` graded / `4000` ungraded — "Used" is no longer accepted for
cards. An ungraded card also needs `CD:Card Condition - (ID: 40001)`:
Near Mint or Better, Excellent, Very Good, Poor. All of it is written into the
workbook's **Reference** tab with sources.

### Photos

A bulk upload carries image *links*, not image files. Put photos in `photos/`
named after the SKU — `CRH-0001.jpg`, `CRH-0001-back.jpg` — and they publish
with the Pages site, which makes them valid eBay picture URLs. `PicURL` fills
itself in when a matching file exists.

---

## Scanning cards: a whole sheet in, one card out

The Brother scans a full page and writes it to `G:\Scans`, whatever is on the
glass. Nothing downstream wants a page.

As of 15 Aug 2026 the profile is **TIFF single-page at 600 dpi** — the printer
offers no PNG at all — and `G:\ScanTools\tiff2png.py` watches the folder and
converts each one to **PNG** (5100 × 6600), moving the TIFF into
`_tiff-originals\`. Two things follow from that: a 33-megapixel page is fine,
the cropper takes about 0.6 s over one; and because the result is a PNG, scans
now **drop straight into Card desk** — the browser could never open the PDFs
the profile used to write.

### The normal run

```
python crop_scans.py --src "G:/Scans" --rotate 180
```

That reads every PDF (and image) in the folder, finds each card, straightens
it, and writes one JPEG per card into `photos/crops/`. Add `--move` once you
trust it and the source files clear themselves; add `--preview` to also get
the page back with green boxes round what it took, which is the fastest way
to see why a card was missed.

Then file the crops onto SKUs:

```
python add_photos.py --src photos/crops --assign CRH-0001,CRH-0002 --pairs
```

**Scan front, back, front, back** and `--pairs` maps them two at a time. The
crops are numbered top row left to right then the next row down, and
`--assign` files strictly in that order — so check the numbers before running
it. A miscount here puts one card's photo on another card's listing.

### `--rotate 180` is not a default, and should not be

Nothing about the shape of a card says which end is the top. The four scans
from 15 Aug all came out upside down because the cards went face down with
their tops pointing away from the operator — consistent, but consistent to
*that* habit. Scan one page, look at it, and set `--rotate` to match how you
actually load the glass. Options are 0, 90, 180, 270.

### The crop includes the toploader, deliberately

A card in a toploader measures 3 × 4 inches, not 2.5 × 3.5, because the
holder is what has the outer edge. Three ways of trimming to the card inside
were tried and all failed on the same thing: on a flatbed, "plastic beyond
the card" and "the card's own white border" are both a flat pale margin, so
nothing can reliably tell them apart. Guessing wrong shears the border off,
and border and centring are the first things a buyer inspects. A rim of
plastic costs nothing and shows the card is protected. If a particular batch
needs it, `--pad -40` trims a fixed 40 px off every side.

### Or drop them in the page

**Card desk → Drop your scans** does the same job in the browser for
JPEG/PNG — drag them in, click to choose, or paste with `Ctrl+V`. Each card
gets a tile with **Turn** (a quarter turn, for that one card) and **Not a
card** (drop a false positive); **Turn all round** flips the whole batch
180° in one click, which is the usual fix. **Save all crops** downloads them
numbered in the order shown.

PNG is what the scanner produces now, so this is the everyday path. It will
**not** open a **PDF** — nothing on the page can read one — so if the profile
ever goes back to PDF, those go through `crop_scans.py`. Use the script anyway
for a big folder: it is one command for the lot, and it does not ask the
browser to hold twenty 33-megapixel pages in memory at once.

It does not know *which* card it is;
the page is static and published, so it can no more recognise a Prizm
parallel than price one. Save the crops, then ask Claude to read them and
paste the lines back into **Or paste a line**.

### Tests

```
python -m pytest test_crop_scans.py     # 19, the script
node test_scan.mjs                      # 17, the browser geometry
python build_all.py . card-run-hq.html  # the dashboard test needs the build
node test_dashboard.cjs                 # every tab, every bookmark, no js errors
```

Both croppers must number cards identically, so the reading-order cases are
duplicated on purpose. `crop_scans.py` needs `opencv-python`, `numpy` and
`PyMuPDF`.

---

## After a workstation restart: do nothing

The dashboard is a **hosted page on claude.ai**. There is no local server, no
tunnel, no background process. A reboot changes nothing.

**Bookmark this on your phone:**
https://claude.ai/code/artifact/b2545d8c-69cc-4284-bc6c-cda0b061e88f

Nothing to start. Nothing to restart. It just loads.

## Layout — 8 tabs, three groups (cut down from 20 on 15 Aug 2026)

Navigation is a **left sidebar** on desktop and a **slide-in drawer** behind the
☰ button on mobile. It **opens on Card desk**, because that is what a working
day actually starts with.

| Group | Sections |
|---|---|
| **My cards** | Card desk · Price a card · Master spreadsheet |
| **Buying** | Shelf check · Price check anything · Box log · Map |
| **Reference** | How it all works |

### What changed and why

It was 20 tabs, and 10 of them were pure reading material with no input on
them at all — you could not find anything. They are now folds inside **How it
all works**: Learn, Box types & ROI, Box breakdowns, Chase cards, Online
shops, Where prices come from, Build plan. Three more that are really "what do
I charge and where" — Pricing rules, Where to sell it, Sports singles — became
folds inside **Price a card**, next to the calculator you use them with.

**Drops, Preorders and Restock windows were deleted.** Not folded — deleted.
Every date and price on them was typed into `build_all.py` by hand, so the
countdowns rendered live off data that nothing refreshes. A tab that looks
current and is not is worse than no tab. If release dates are wanted back they
need a feed behind them, not a list.

**No content was lost in the fold.** Every old `#hash` still works: the router
now falls back to finding the id anywhere on the page, switches to whichever
tab it now lives in, and opens the fold. So `#src`, `#learn`, `#types` and the
rest still land on the right thing from an old bookmark.

Every section deep-links, and now it works **from any section**, not just on a cold
load — tapping a bookmark while the page is already open switches to it:

```
…/b2545d8c-69cc-4284-bc6c-cda0b061e88f#shelf   in-aisle lookup
…/b2545d8c-69cc-4284-bc6c-cda0b061e88f#sell    price a card before you buy it
```

## The two sides behave differently — this matters

- **Buy side is a snapshot.** Frozen at whatever date the page was last built.
- **Sell side calculates live.** The pricing tools run in your browser, so they are
  correct whenever you open the page. Nothing to refresh.

## Card desk on your phone

One tab. **Type a card name**, tap the price of the printing you have, done.

- **5,280 cards across 37 sets are baked in** (Pokémon, One Piece, Lorcana) with
  thumbnails, so it works with no connection at all.
- Results show set, number and rarity, and a separate price chip per printing — which
  is how you tell a Poke Ball Umbreon from a Master Ball one.
- Quantity and condition are edited on the row afterwards. Nothing to memorise.
- **Set codes are optional.** `pbl 86 *f nm x2` still jumps straight to one card, and
  it's folded away under *"Know the set code?"* — a shortcut, not the way in.
- Stock is saved in **that browser's localStorage** and survives a reload.
- **Export CSV** hands you the file through the artifact download capability. If `.csv`
  isn't permitted it falls back to `.csv.txt` — rename it.

> Redesigned 15 Aug 2026. The first version made you type a set code you could only
> find in a 37-row table further down the page. Searching by name removed the problem
> rather than documenting it.

⚠ **This is a second, separate stock list.** It does not sync with the desktop app's
database. Use it for sorting away from the desk, export, and bring the CSV in. Prices
here are a snapshot from the build date; the desktop app pulls live.

**To refresh the embedded catalogue:**

```powershell
cd "G:\Claude\project tcg-lister"
python export_web_catalog.py 20        # writes ..\project tcg-scout\cards.json
cd "G:\Claude\project tcg-scout"
python build_all.py . card-run-hq.html
```

Scanning, the stock ledger, cost basis, locations and marketplace CSV generation stay
in the local app — a published page has no scanner, no real database, and is blocked
from reaching tcgcsv.com. See `G:\Claude\project tcg-lister\RUNBOOK.md`.

---

## To refresh the prices

The page is a **snapshot** — it does not update itself. Prices are from the day it
was last built. Two ways to get fresh numbers.

### Option A — ask Claude (easiest)

> "Refresh the TCG dashboard"

Takes ~2 minutes. Claude runs both scripts from `G:\Claude\project tcg-scout\`
and republishes to the same URL.

### Option B — run it yourself

```powershell
cd "G:\Claude\project tcg-scout"
python pull_shelf.py shelf.json          # ~3-6 min, ~140 requests to tcgcsv.com
python build_all.py . card-run-hq.html
```

That produces `card-run-hq.html` locally. Open it in a browser to view. To get it
back onto the phone-accessible URL, Claude has to republish it — the Artifact tool
is the only thing that can write to that address.

---

## Why there is no automatic daily refresh

Tested and proven impossible on 2026-08-14, twice:

- Scripts in a secret gist → sandbox returned `EGRESS_BLOCKED`
- Scripts in an attached repo → repo cloned fine, then
  `Tunnel connection failed: 403 Forbidden` on **tcgcsv.com**

**Anthropic's cloud sandbox only whitelists package registries** (pypi, npm,
crates, golang) and anthropic.com. It cannot reach tcgcsv.com at all, so no cloud
agent can ever pull the price data.

Routine `trig_01QJVEiYAbtJGwE5BoApNqSS` exists but is **disabled on purpose** —
enabled, it would push a failure notification every morning. Leave it off.

---

## Where everything lives

| Thing | Location |
|---|---|
| Live dashboard | https://claude.ai/code/artifact/b2545d8c-69cc-4284-bc6c-cda0b061e88f |
| Scripts (local) | `G:\Claude\project tcg-scout\` |
| Scripts (offsite) | https://github.com/pthaiop587/tcg-scout — private |
| Design + findings | `SPEC.md` in this folder |
| Memory notes | `_memory\shared\project\tcg-scout.md` and two `reference\` notes |

`shelf.json` is the last data pull — safe to delete, it regenerates.

---

## Two things still open

**Store stock retest — 16 Sep.** Live per-store inventory is unproven. Target's API
403s scripts and every Pokémon listing on Target.com was a third-party reseller
marked "not sold in stores", so there was nothing first-party to test against.
The 30th Celebration launch on 16 Sep is the first moment real first-party SKUs
exist. Retest then.

**Call the card shops.** OpenStreetMap only maps 9 in a 20-mile radius; the real
number is higher. A standing preorder at a card shop is the most reliable way to
buy at MSRP — and MSRP is the only price where any of this makes money.
