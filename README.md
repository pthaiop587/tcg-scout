# tcg-scout

Generates **Card Run HQ** — a sealed-TCG scouting dashboard for Pokémon,
One Piece and Disney Lorcana, centred on ZIP 91786.

## Daily run

```bash
python pull_shelf.py shelf.json     # fetch TCGCSV -> prices + chase cards
python build_all.py . card-run-hq.html
```

Then republish `card-run-hq.html` to the existing artifact URL.

## Files

| File | Purpose |
|---|---|
| `pull_shelf.py` | Pulls TCGCSV (free TCGplayer mirror). Sets since 2025-01-01. Computes market ÷ retail per product, plus each set's chase card. |
| `build_all.py` | Renders the 5-tab dashboard from `shelf.json` + store data. |
| `hq.css` / `hq.js` | Page styles and interactivity, kept separate so the generator has no brace-escaping issues. |
| `stores_clean.json` | 198 retail locations near 91786 (OpenStreetMap/Overpass). Rarely changes — not re-fetched daily. |
| `lgs_clean.json` | Local game/hobby shops from the same source. |

## Retail prices are verified, never estimated

`msrp_for()` only returns a figure that was checked against a source.
Anything unverified returns `None` and the product is **excluded** rather
than shown with a guessed ratio. Known values:

- Pokémon ETB $49.99 · Pokémon Center ETB $59.99 · booster box $143.64 ·
  booster bundle $26.94 · mini tin $9.99 · 3-pack blister $13.99
- One Piece booster box $119.76 (24 × $4.99) · pack $4.99 · starter deck $11.99
- Lorcana booster box $143.76 (24 × $5.99) · pack $5.99 · Trove $49.99

## Traps already handled — don't reintroduce these

- **Multi-packs.** `[Set of 6]` / `Mini Tins 5-Pack` priced against a single
  unit's retail produced fake 17× ratios. Excluded.
- **Cases and displays** are distributor units, not shelf items. Excluded.
- **Legacy backfill sets.** TCGCSV's `publishedOn` is a placeholder for old
  groups — POP Series 1–9 and "Miscellaneous" all report today's date. Filtered
  via `JUNK`, or the calendar claims nine sets drop today.
- **TCIN length does not identify first-party Target stock.** `A-93165397` is
  8 digits and still a third-party reseller.

## Not covered, and why

- **Palworld** (Bushiroad) — no TCGplayer category exists, so no price feed.
  Hand-tracked in the Drops tab only.
- **Sports cards** — every price source is paywalled, blocked, or singles-only.
  Calendar only.
- **Live store stock** — Target's inventory API returns 403 to scripts and
  Walmart publishes no free per-store data. The map shows locations, not stock.
