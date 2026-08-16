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

## After a workstation restart: do nothing

The dashboard is a **hosted page on claude.ai**. There is no local server, no
tunnel, no background process. A reboot changes nothing.

**Bookmark this on your phone:**
https://claude.ai/code/artifact/b2545d8c-69cc-4284-bc6c-cda0b061e88f

Nothing to start. Nothing to restart. It just loads.

## Layout — left sidebar, two groups (rebuilt 14 Aug 2026)

The horizontal tab strip is gone. Navigation is a **left sidebar** on desktop and a
**slide-in drawer** behind the ☰ button on mobile, split into two groups:

| Group | Sections |
|---|---|
| **Buy — scouting** | Drops · Shelf check · Map · Chase cards · Learn |
| **Sell — my cards** | Card desk |
| **Sell — work it out** | Price a card · Where to sell it · Pricing rules · Build plan |

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
