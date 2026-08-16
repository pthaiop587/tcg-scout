# Card Run HQ — runbook

## The dashboard is gone (16 Aug 2026)

Retired on request. The workbook is the whole system now: there is no page, no
public URL, no scheduled rebuild, and nothing to publish.

What went: `build_all.py`, `hq.js`, `hq.css`, `inventory.js`, `scan.js`,
`export_inventory.py`, `pull_shelf.py`, the data files they fed on
(`shelf.json`, `cards.json`, `boxes.json`, `lgs_clean.json`,
`stores_clean.json`, `thumbs.json`), their tests, and
`.github/workflows/refresh.yml` — which was the four-times-a-day rebuild and
the GitHub Pages deploy. Deleting that workflow file is what stops the site
updating.

All of it is in the git history. `git log --diff-filter=D --name-only` finds
the commit; nothing needs rewriting to bring it back.

What stayed: everything that touches the workbook. `make_workbook.py`,
`upgrade_workbook.py`, `workbook_extra.py`, `sport_tabs.py`, `autofill.py`,
`fill_blanks.py`, `prices.py`, `colleges.py`, `file_batch.py`, `add_card.py`,
`add_photos.py`, `embed_photos.py`, `make_ebay_csv.py`, `crop_scans.py` and
`ripsheet.py`.

`refresh.py` lost its last two steps and now only tidies the workbook — SKUs,
categories, game tabs. `Update dashboard.cmd` became **`Update workbook.cmd`**
to stop promising something it no longer does.

The published artifact at claude.ai is a separate thing and has to be deleted
from claude.ai; no script here can reach it.

## The 8am price check (16 Aug 2026)

A Windows scheduled task, **"Card Run HQ - daily price check"**, runs every day
at 08:00. It does two things in order:

1. `git pull` — no point checking prices with last week's code
2. `python prices.py --daily` — refresh raw / PSA 9 / PSA 10 for every card,
   record when each last sold and what that sale made, and report what moved

Roughly four minutes: one page per card with a pause between.

### The launcher lives outside the repo

`G:\Claude\card-run-daily.cmd`, **not** in the project folder. Its first act is
to `git pull` that folder, and a launcher sitting inside the thing it is
updating is one that can be overwritten halfway through doing it.

It is therefore not in version control. If it is ever lost, it is four lines:
`cd` to the project, `git pull`, `python prices.py --daily`.

### What it leaves behind

| File | What is in it |
|---|---|
| `price-check.log` | The audit, one block per run: what moved, by how much |
| `price_history.csv` | Every figure from every run — 180 rows a day, so this becomes a trend |
| `daily-update.log` | What `git pull` did, and the exit code |

Both of the first two are gitignored: they are about your cards and what they
cost.

### If it does nothing one morning

**The workbook was open in Excel.** `prices.py` refuses rather than racing
Excel for the file, exits non-zero, and the reason is in `daily-update.log`.
Close the workbook and double-click the launcher.

**The pull was blocked.** Usually an untracked file in the project folder with
the same name as one being pulled — git names it in `daily-update.log`. Move
or delete that file.

### Changing it

Task Scheduler, under that name. Any time you like; 08:00 was picked because
eBay sales settle overnight, so the movement you see with your coffee is
yesterday's.

## The master workbook and eBay uploads

`Card Run HQ - Master.xlsx` in this folder is the real record. It is
**gitignored on purpose** — the repo is public and the workbook holds the
inventory, what each box cost and what each card sold for. CI generates a
your filled-in copy never leaves this machine.

| Script | What it does |
|---|---|
| `python make_workbook.py` | Builds a fresh workbook: **10 tabs** — Read me, Inventory, eBay, and one per game. `--full` adds Purchases, Box log, Expenses, Sales, Photos, Summary, Audit, Reference. Refuses to overwrite without `--force`. |
| `python autofill.py --go` | Fills in what a hand-typed card can work out for itself: its **SKU**, and its **Category** from the sport. Never renumbers a card that has a SKU. |
| `python upgrade_workbook.py` | Moves an **existing** workbook onto the current layout **keeping what you typed**. Dry run by default; `--go` to do it. Backs up first, always. |
| `python embed_photos.py` | Rewrites the **Photos** tab from what is in `photos/`, thumbnails and all. Run it after adding photos. |
| `python sport_tabs.py` | Rebuilds a read-only tab per sport from Inventory. `--add Basketball` starts one before there are any cards; `--list` says what is there. |
| `python file_batch.py batch.json` | Files a whole scanned batch: a row per card with a SKU, photos onto those SKUs. |
| `python add_card.py --player "..." --year 2025 --brand "..." ...` | Appends one card to Inventory and assigns the next SKU. |
| `python make_ebay_csv.py` | Writes `ebay-upload-<date>.csv` from every Inventory row marked **Unlisted**, and rewrites the workbook's eBay upload tab to match. `--sku CRH-0001` for one card, `--all` to ignore status. |

### The tabs

**The default is ten tabs**, which is all the day-to-day needs:

| Tab | What it is for |
|---|---|
| **Read me** | What every tab is, inside the file. |
| **Inventory** | **Every card, whatever the game.** One row each, and the only tab you type cards into. |
| **eBay** | The upload, written by `make_ebay_csv.py`. Do not type here. Holds only rows marked Unlisted. |
| **Costs** | **Everything you paid for** — boxes and packs, and the toploaders, sleeves, mailers and postage around them. |
| **Football, Basketball, Baseball, Pokemon, Palworld, One Piece, Disney** | One read-only view per game, rebuilt from Inventory. |

### Costs: one tab, split by Type

A trip that buys a blaster and a pack of sleeves is one receipt, so it is one
tab. The **Type** column is what keeps the distinction that matters:

- **Sealed box, Sealed case, Pack, Single card, Bulk lot** — money that turned
  into cards, and can be earned back.
- **Toploaders, Sleeves, Mailers, Boxes, Postage, Shipping, Fees, Equipment** —
  money that simply goes. This is what turns a gross profit into a real one,
  and it is the first thing forgotten.

Subtotal and Total paid work themselves out. Put the same **Lot ID** on a box
here and on the cards that came out of it and cost per card stops being a guess.

### Listed and sold live on the card's own row

The short layout has no Sales tab, so a card's whole life is one row:
**Listed on · eBay item # · Sold on · Sold for · Fees paid · Net · Profit**.
Net and Profit calculate themselves — Net is what the sale left after fees,
Profit is that less what the card cost. Set **Status** to Listed or Sold to
match; the eBay export only ever takes rows still marked Unlisted.

### Category fills itself in

**Sport or game** is a dropdown, and `autofill.py` derives **Category** from it
— Football, Basketball and Baseball are *Sports*; Pokemon, Palworld, One Piece
and Disney are *TCG*. `make_ebay_csv.py` picks the eBay category code off that
column, so a blank one lists the card under the wrong category.

It is written in rather than left as a formula on purpose: `make_ebay_csv.py`
reads the workbook with `data_only=True`, and a formula Excel has not
recalculated reads as empty. The listing would be miscategorised with nothing
looking wrong in the sheet.

`Lists` is hidden — it feeds the Graded-by dropdown, whose entries are too long
for an inline list. It is not a tab anybody sees.

**`--full` brings back the rest** when you want them: Purchases (buys with
receipts), Box log, Expenses, Sales, Photos, Summary and Audit. `upgrade_workbook.py --full`
moves an existing workbook onto that layout instead.

### Set "Sport or game" on every row

It is a dropdown, and it is what sorts a card onto its game tab and drives the
it onto its game tab. A card with it blank sits in Inventory and appears on
no game tab at all.

### A card typed by hand has no SKU

`file_batch.py` and `add_card.py` assign one; typing into the sheet does not.
A row without a SKU is **invisible** — `make_ebay_csv.py` cannot export it,
and `add_photos.py` has nothing to file a picture against. `refresh.py` runs
`autofill.py` every time for exactly that reason.
It only ever fills an empty cell, and never renumbers a card that has one,
because a SKU is what your photos and any live listing are named after.

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

## More than one sport

**There is still only one Inventory.** It has a **Sport or game** column with a
dropdown — Football, Basketball, Baseball, Hockey, Soccer, Pokemon, One Piece,
Lorcana, Magic, Other — and every card goes in it whatever the sport.

`sport_tabs.py` then builds a **read-only tab per sport**, so each can be looked
at on its own. `Update workbook.cmd` rebuilds them, and the
inventory grows a **Sport** filter row at the same time.

```
python sport_tabs.py --add Basketball    # start the tab before the first card
python sport_tabs.py                     # rebuild them all
python sport_tabs.py --list              # what is in there now
```

### When each card was logged

Every tab that holds rows shows a date, so you can tell what came in this week
from what has been sitting there.

| Tab | Column | Filled by |
|---|---|---|
| Inventory | `Date in` | `add_card.py` and `file_batch.py`, stamped on the day |
| The 7 game tabs | `Date in` | carried across from Inventory on every rebuild |
| Costs | `Date` | you, when you log the purchase |
| eBay | — | generated upload sheet; a column here breaks the upload |

The game tabs also carry `Listed on` and `Sold on`, so one game's whole run —
logged, listed, gone — reads across a single row.

**They are formatted, not just filled.** openpyxl hands a date back as a
datetime, and a cell with no number format shows it as a five-digit serial:
`46615` sitting in a row of cards reads as a card number at a glance.
`sport_tabs.DATES` lists the date columns and `build_tab` formats every one,
with a test asserting the format rather than just the value.

Existing rows already have their date — nothing needed backfilling.

### Typing on a game tab no longer loses it

On 16 Aug 2026 a batch of listing entries was typed onto the **Football** tab
and the next `sport_tabs.py` run destroyed them. The tab said *"do not type
here"* in A1 and that was the entire safeguard — a sign, not a lock. The loss
was silent: the script did exactly what it was told.

It now checks before it deletes. Anything on a generated tab that Inventory
cannot account for counts as typed by hand:

- a value past the columns the script writes
- a row whose SKU is not in Inventory at all
- a cell edited to differ from the Inventory row it was copied from

If it finds any, the sheet is **renamed to `Football (typed on)` and kept**,
the view is rebuilt alongside it, and the run says what it found and where.
Move what you want into Inventory, then delete the kept sheet.

**Type listings into Inventory, not onto a game tab.** `Listed on`,
`eBay item #` and `Sold on` are Inventory columns; the game tabs show them but
are rebuilt from Inventory every refresh.

### Why views and not separate inventories

Everything downstream reads the **Inventory** tab and only that: `file_batch.py`
takes the next SKU from it, `make_ebay_csv.py` exports from it, Summary and
Audit count it.

Type a basketball card into a tab of its own and it gets a SKU another card
already has, **never reaches an eBay upload**, and is missing from every total —
silently, because nothing is looking for a second inventory. So the sport tabs
are copies, marked *"VIEW — generated from Inventory. Do not type here."*, and
rebuilt from it every run. Anything typed into one is overwritten next time.

A tab you made yourself is never touched: only sheets carrying that marker get
replaced, so a hand-made "Basketball" sheet is left exactly as it is.

*(A live `FILTER()` formula would have been nicer than regenerating. It was
tried and dropped — it does not survive a recalculation outside the newest
Excel, so the tab would read "none" on a perfectly good workbook.)*

---

## Scanning cards: a whole sheet in, one card out

The Brother scans a full page and writes it to `G:\Scans`, whatever is on the
glass. Nothing downstream wants a page.

As of 15 Aug 2026 the profile is **TIFF single-page at 600 dpi** — the printer
offers no PNG at all — and `G:\ScanTools\tiff2png.py` watches the folder and
converts each one to **PNG** (5100 × 6600), moving the TIFF into
`_tiff-originals\`. Two things follow from that: a 33-megapixel page is fine,
the cropper takes about 0.6 s over one; and a PNG is what `crop_scans.py`
wants, which a PDF was not.

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

## Opening a box: the rip sheet

```
python ripsheet.py                 # every set it knows
python ripsheet.py --set asg       # just one
python ripsheet.py --list          # what it knows
```

Writes `Rip sheet.html` — one self-contained page, no network, fine on a phone
next to the pile. It lists what is actually worth pulling out of a box, with
the odds and with what the card *looks like*, because you sort by eye and not
by checklist. Tick a line as you find it, type the player, then **Copy paste
lines**, then click the **Year** cell on the first empty Inventory row and
paste — all six columns land at once.

It holds nothing. Close it and it is gone — copy before you leave. That is
deliberate: a second place cards live is the one thing this project keeps
refusing to build.

### It cannot go on a sport tab

The obvious home for a checklist is the Baseball tab, and that is exactly wrong.
Those tabs are views — `sport_tabs.py` rewrites them from Inventory on every
refresh, so a checklist typed there survives until the next `Update workbook`
and then does not. The sheet is a separate page for that reason.

### The field order is a real contract

The sheet writes `card | set | number | variant | condition | qty | worth |
sports or tcg` and `hq.js` reads it back **by position**. Nothing in either file
announces that. Reorder one side and there is no error — cards import with the
parallel sitting in the condition column and the worth in the quantity.
`test_ripsheet.py` reads the order out of `hq.js` and compares, rather than
restating it, so it can actually fail when it should.

### The last column decides the category

`sports` or `tcg` is the eighth field, and it is what puts a card under the
right eBay category and the right `Category` in the workbook. A Pokémon card
sent over as `sports` lists in the wrong place with nothing looking wrong
anywhere. Each set on the sheet carries its own flag, and a test cross-checks
those against `autofill.py`'s `CATEGORY_OF` so the two cannot drift.

### No prices are baked in

On purpose. A number written into a file in August is a lie by October. The
sheet tells you *which* cards are worth looking up — that part does not go
stale — and leaves the price to you.

### Tests

```
python -m pytest test_crop_scans.py test_file_batch.py test_workbook.py test_sport_tabs.py test_ripsheet.py test_fill_blanks.py
node test_scan.mjs                      # 19, the browser geometry
node test_queue.cjs                     # the review queue, capture to confirm
```

Both croppers must number cards identically, so the reading-order cases are
duplicated on purpose. `crop_scans.py` needs `opencv-python`, `numpy` and
`PyMuPDF`.

---

## Where everything lives

| Thing | Location |
|---|---|
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
