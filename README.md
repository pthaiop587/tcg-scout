# tcg-scout

Tooling around **Card Run HQ - Master.xlsx**, a trading-card resale inventory:
what came out of which box, what it cost, what it is worth, and what it sold
for. Sports and TCG in one workbook.

The workbook is the whole system. It is **gitignored on purpose** — this repo
is public and the workbook holds the inventory, what each box cost and what
each card sold for.

> There was a dashboard: a generated page with price scouting, a card desk and
> a scan queue, published to an artifact and rebuilt four times a day by
> GitHub Actions. It was retired on 16 Aug 2026 and everything it needed was
> deleted. It is all in the git history —
> `git log --diff-filter=D --name-only` finds the commit.

## After you type into the workbook

```bash
python refresh.py            # or double-click "Update workbook.cmd"
```

Gives a SKU and a Category to anything typed by hand, then rebuilds the
per-game tabs from Inventory. Safe to run every time: it only ever fills empty
cells and never renumbers a card that already has a SKU.

## The scripts

| File | Purpose |
|---|---|
| `make_workbook.py` | Builds a fresh workbook. 11 tabs by default; `--full` adds Purchases, Box log, Expenses, Sales, Photos, Summary, Audit. |
| `upgrade_workbook.py` | Moves an existing workbook onto the current layout **keeping what you typed**. Dry run by default; backs up first, always. |
| `workbook_extra.py` | The tabs beyond Inventory — Costs, Summary, Audit, Reference — and their formulas. |
| `refresh.py` | The three tidy-up steps in the right order. |
| `autofill.py` | Fills a hand-typed row's **SKU** and its **Category** from the sport. |
| `sport_tabs.py` | A read-only tab per game, rebuilt from Inventory. Keeps anything typed onto one instead of deleting it. |
| `fill_blanks.py` | Copies a box's shared details from one row you filled in properly to the rest. Empty cells only. |
| `prices.py` | Looks up raw / PSA 9 / PSA 10 prices **and when one last sold**, from sportscardspro.com. |
| `colleges.py` | Reads a school out of a listing title. Longest-match, so "Texas A&M" beats "Texas". |
| `file_batch.py` | Files a whole scanned batch: a row per card with a SKU, photos onto those SKUs. |
| `add_card.py` | Appends one card and assigns the next SKU. |
| `crop_scans.py` | A scanned page of cards in, one straightened card per file out. |
| `add_photos.py` / `embed_photos.py` | File card photos against SKUs; put thumbnails in the Photos tab. |
| `make_ebay_csv.py` | Writes `ebay-upload-<date>.csv` from every row marked **Unlisted**. |
| `ripsheet.py` | Builds `Rip sheet.html`: what to look for in a box, ticked off as you sort, copied straight into Inventory. |

## Tests

```bash
python -m pytest test_crop_scans.py test_file_batch.py test_workbook.py \
                 test_sport_tabs.py test_ripsheet.py test_fill_blanks.py
```

## Two things that will bite

**Inventory is addressed by column letter** in `workbook_extra.py`. New columns
go on the **end**; inserting one silently moves every formula.

**A game tab is a view.** `sport_tabs.py` rebuilds it from Inventory on every
run. Type into Inventory, not onto a game tab — though since 16 Aug 2026 the
rebuild checks first and keeps anything it cannot account for as
`Football (typed on)` rather than deleting it.
