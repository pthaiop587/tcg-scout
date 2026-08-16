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
| `python make_workbook.py` | Builds a fresh workbook, 12 tabs. Refuses to overwrite without `--force`. |
| `python upgrade_workbook.py` | Moves an **existing** workbook onto the current layout **keeping what you typed**. Dry run by default; `--go` to do it. Backs up first, always. |
| `python embed_photos.py` | Rewrites the **Photos** tab from what is in `photos/`, thumbnails and all. Run it after adding photos. |
| `python export_inventory.py` | Puts the Inventory tab onto the dashboard's **My inventory** tab. `--publish` also writes the money-free copy for the public site. |
| `python file_batch.py batch.json` | Files a whole scanned batch: a row per card with a SKU, photos onto those SKUs. |
| `python add_card.py --player "..." --year 2025 --brand "..." ...` | Appends one card to Inventory and assigns the next SKU. |
| `python make_ebay_csv.py` | Writes `ebay-upload-<date>.csv` from every Inventory row marked **Unlisted**, and rewrites the workbook's eBay upload tab to match. `--sku CRH-0001` for one card, `--all` to ignore status. |

### The 12 tabs

| Tab | What it is for |
|---|---|
| **Summary** | Spent, held, sold, and whether it is working. All formulas — nothing typed. |
| **Audit** | What to fix before it costs you. All live counts. Zero down the column = clean. |
| **Inventory** | Every card, one row. The master; everything else reads from it. |
| **eBay upload** | Written by `make_ebay_csv.py`. Do not type here. |
| **Purchases** | Every buy **with its receipt** — boxes, singles, lots, supplies. |
| **Box log** | What came *out* of a box, against what it cost. |
| **Expenses** | Toploaders, mailers, postage, subscriptions — the costs that are not a card. |
| **Sales** | What sold and what was left after fees. |
| **Photos** | Which cards have a picture, **with the picture in it**. |
| **Reference** | The eBay codes, with sources. |
| **Lists** | Dropdown sources. Leave it alone. |
| **Read me** | The same thing you are reading, inside the file. |

**Lot ID is the thread.** Put the same code on the Purchases row, the Box log
row and every Inventory row that came out of that box, and cost per card stops
being a guess — which is what makes the Summary's profit figure mean anything.

**The Audit tab is worth reading before every upload run.** It catches the
things that are cheap to fix now and expensive to hear about from a buyer: a
card held for Review, one about to list at a price of nothing or with no
photo, a title over eBay's 80 characters, a purchase with no receipt, a card
that sold but is still marked in stock — which is how a card gets listed
twice.

### Photos: what is in the workbook and what is not

`embed_photos.py` puts a **thumbnail** in the Photos tab and a **URL** in the
column next to it, and they do different jobs. The thumbnail is for you —
scroll the tab and see the stock. The URL is what eBay fetches, because eBay
will not take an embedded picture; `PicURL` has to be a public https address.

So **the image files do not travel with the workbook.** They live in `photos/`
and are published with the site. Downloading the .xlsx gives you the
spreadsheet and the links; the links only resolve once the photos have been
pushed. That is also what keeps the file small — a hundred cards at full
resolution would be a 200 MB spreadsheet nobody can open.

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

## Seeing the workbook on the dashboard

The page does **not** read the workbook. It is built once from files on disk,
so typing a card into the spreadsheet changes nothing until you export and
rebuild:

```
   (type into Card Run HQ - Master.xlsx)
python export_inventory.py
python build_all.py . card-run-hq.html
```

Then **My inventory** shows every card with its photo, status, condition,
quantity, cost, market and ask, with a search box and filters for ready-to-list,
held-for-review, listed and sold. The tiles across the top are the same
arithmetic as the workbook's Summary, so the two agree.

### Two exports, and the difference is your privacy

`inventory.json` is **everything** — cost, notes, lot. It is **gitignored**, so
it stays on this machine and only a build done here shows it. CI has never seen
your workbook and cannot: that is gitignored too.

`export_inventory.py --publish` additionally writes `inventory-public.json`,
which carries what a card *is* — name, set, number, parallel, condition,
quantity, status, photo, market — and **not** what you paid, what it sold for,
your notes, or the lot. That file is committed and served with the site, so
treat everything in it as readable by anyone with the URL. Commit it to
publish; delete it to stop.

The build prefers the local file and falls back to the published one, and the
page says which it is looking at — so a blank cost column reads as "deliberately
not published" rather than missing data.

**Photo paths are relative** (`photos/CRH-0001.jpg`) so the thumbnails load both
in the copy built here and on the live site. eBay is the one consumer that needs
a full public https address, and `make_ebay_csv.py` builds those itself.

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

### Or drop them in the page — the review queue

**Card desk → Drop your scans** does the same job in the browser for PNG and
JPEG — drag them in, click to choose, or paste with `Ctrl+V`. PNG is what the
scanner produces now, so this is the everyday path.

Every card found goes straight onto a **review queue** under the drop zone.
It is captured immediately and kept — the queue survives closing the tab — but
**it goes nowhere on its own.** Nothing on the queue is inventory until it has
been through the workbook.

**Confirm** on a card means only "I have looked at this one". It is off until
the card has a name and nothing on it is still amber. **Save for the workbook**
then downloads the pictures plus a `batch.json` naming every checked card, and:

```
   move the crh-*.jpg into photos/crops, batch.json beside the workbook
python file_batch.py batch.json
python make_ebay_csv.py
```

That is what gives a card a SKU, files its photos onto that SKU, and turns it
into a listing. **The workbook is the inventory** — it is the only thing here
that can be edited properly and the only thing that can produce an eBay upload.

| Button | What it does |
|---|---|
| **Confirm** | mark this card checked; off until it has a name and no amber |
| **Save for the workbook** | download the pictures and `batch.json` for every checked card |
| **Clear saved** | take the handed-over cards off the queue |
| **Add back** | attach another picture — the other side — to *this* card |
| **Join to N** | make this card the back of the one above it |
| **Split** | break a two-picture card back into two |
| **Turn** / **Turn all round** | rotate a card, or the whole batch 180° |
| **Save all crops** | download every picture without filing anything |
| **Remove** / **Clear queue** | drop cards off the queue without adding them |

The pictures are named `crh-001.jpg`, `crh-002.jpg` … in the order shown, front
before back, because `file_batch.py` hands them out in filename order using
each card's `photos` count. **The counts have to add up.** One picture out and
every card after it gets somebody else's photo, so a mismatch files nothing at
all and says what it found.

### The "Pricing scratchpad" is not your inventory

What used to be **My cards** is now labelled that way on purpose. It is fine
for working out what a pile is worth while you are standing in a shop, but a
card in it can only be nudged up and down by quantity, nothing else can be
edited, and its CSV is a pricing worksheet rather than an eBay upload. Nothing
in it reaches eBay. Scanned cards go to the workbook instead.

### The path with no data entry at all

This is the one to use. You scan, you say "new scans", and nothing else is
typed by hand:

```
python crop_scans.py --src "G:/Scans" --rotate 180
      (Claude reads photos/crops and writes batch.json)
python file_batch.py batch.json
python make_ebay_csv.py
```

`file_batch.py` adds a row per card with its own SKU, renames the crops onto
those SKUs — front and back together when the batch file says `"pairs": true`
— and leaves the export ready. `batch.example.json` in this folder is the
format; every field maps to an Inventory column and an unknown one is an
error rather than a silent drop.

**What can actually be read off a card.** Name, set and card number are
printed on it, so those come back every time. The **parallel does not** — a
Silver Prizm does not say "Silver" anywhere, so it is judged from the colour
and pattern, and a serial number is what usually settles it. **Value cannot be
read at all**: sports singles have no free price feed, so it needs eBay sold
comps, not a picture.

**So the Review gate.** Any card carrying an `"unsure"` field is filed with
Status **Review** and a `CHECK:` note saying which fields, and
`make_ebay_csv.py` exports only **Unlisted**. An uncertain card therefore
cannot reach a live listing until you open the workbook, settle the field and
change the status yourself. The guard sits at the export, which is the
boundary that matters — not in a browser you might not be using.

### Or hand a batch to the page instead

If you would rather work in Card desk, drop the scans there and paste what
Claude worked out into **Paste what Claude worked out**. One line per card
*in the order shown*:

```
card | set | number | parallel | condition | qty | worth | sports or tcg
```

A `?` in front of a value makes that field **amber**, and **Confirm stays off
until you have dealt with it** — type a correction, or press *looks right* to
accept it. Same guard, different place.

**Two sides of one card.** Every picture starts as its own card. There are
three ways to say two of them are the same card, and they cover every order
the pictures can arrive in:

| | |
|---|---|
| **Add back** | on a card, then pick the picture. Works whatever order they were uploaded in, or if they came from different scans. |
| **Join to N** | on a card, to make it the back of the one above. For when you already uploaded both separately. |
| **Scanned front and back in order** | pairs the whole list off, 1 with 2, 3 with 4. For a batch scanned front, back, front, back in one go. |

**Split** undoes any of them. A card with two pictures asks for one set of
details, confirms as **one** row in My cards, and takes both pictures with it.
Grouping is by an id each picture carries, not by its position, so joining and
splitting never disturbs the rest of the list.

### Two things worth knowing

**The full-size picture is session-only.** The queue stores each card's
details and a thumbnail, which is what survives a reload; the full-resolution
crop lives in memory only, because a dozen of them would blow the browser's
storage quota. After a reload the details are all still there and still
confirmable, but *Save crop* is greyed out and the page says so. If you want
the photos, save them in the same sitting — or use `crop_scans.py`, which
writes real files to disk and never has this problem.

**A PDF will not open here.** Nothing on the page can read one. If the scanner
profile ever goes back to PDF, put those through `crop_scans.py`. Use the
script for a big folder anyway: one command for the lot, and it does not ask
the browser to hold twenty 33-megapixel pages at once.

### Tests

```
python -m pytest test_crop_scans.py test_file_batch.py test_workbook.py test_export_inventory.py
node test_scan.mjs                      # 19, the browser geometry
python build_all.py . card-run-hq.html  # the dashboard test needs the build
node test_dashboard.cjs                 # every tab, every bookmark, no js errors
node test_queue.cjs                     # the review queue, capture to confirm
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
