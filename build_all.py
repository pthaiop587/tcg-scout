"""Card Run HQ - tabbed dashboard generator.
Usage: python build_all.py <scratchdir> <out.html>
Re-runnable: this is what the daily refresh calls after pull_shelf.py."""
import json, io, math, os, sys, html

SP, OUT = sys.argv[1], sys.argv[2]
TODAY = __import__("datetime").date.today()
STAMP = TODAY.strftime("%d %b %Y")
HOME = (34.0975, -117.6484)
RADIUS = 20.0

shelf_data = json.load(io.open(f"{SP}/shelf.json", encoding="utf-8"))
stores     = json.load(io.open(f"{SP}/stores_clean.json", encoding="utf-8"))
lgs        = json.load(io.open(f"{SP}/lgs_clean.json", encoding="utf-8"))
esc = lambda s: html.escape(s or "")

# ------------------------------------------------------------------ shelf
def where(r):
    if r["age"] <= 0: return "preorder"
    if "pokemon center" in r["product"].lower(): return "online"
    return "store"

rows = sorted([{"g": r["game"], "s": r["set"], "p": r["product"], "r": r["retail"],
                "m": r["market"], "x": r["ratio"], "c": r["chase"], "cp": r["chasePrice"],
                "cr": r["chaseRarity"], "w": where(r)} for r in shelf_data["rows"]],
              key=lambda r: -r["x"])
shelf_rows = [r for r in rows if r["w"] == "store"]

chase = sorted([s for s in shelf_data["sets"] if s.get("chase")],
               key=lambda s: -s["chase"]["price"])
chase_rows = "".join(
    f'<tr><td>{esc(s["game"])} &middot; {esc(s["set"])}</td><td>{esc(s["chase"]["name"])}</td>'
    f'<td>{esc(s["chase"]["rarity"])}</td><td class="num mono">${s["chase"]["price"]:,.2f}</td></tr>'
    for s in chase[:14])

# ------------------------------------------------------------------ stores
BAD = ("distribution","optical","pharmacy","garden","gasoline","drive","auto",
       "vision","photo","outlet","mobile","neighborhood market","tire","hearing")
CHAINS = [("Target", lambda n: n=="target"),
          ("Walmart", lambda n: n in ("walmart","walmart supercenter")),
          ("Costco", lambda n: n in ("costco","costco wholesale")),
          ("Sam's Club", lambda n: n=="sam's club"),
          ("Best Buy", lambda n: n=="best buy"),
          ("GameStop", lambda n: n=="gamestop")]
def chain_of(name):
    n = name.strip().lower()
    if any(b in n for b in BAD): return None
    for lab, t in CHAINS:
        if t(n): return lab
    return None

pts = [{**s, "chain": c} for s in stores if (c := chain_of(s["name"])) and s["d"] <= RADIUS]
pts += [{**s, "chain": "Card shop"} for s in lgs
        if s["d"] <= RADIUS and s.get("shop") in ("games","collector","hobby")
        and "cardenas" not in s["name"].lower()]
pts.sort(key=lambda r: r["d"])

W = H = 700; PAD = 36
kx = math.cos(math.radians(HOME[0]))
def relxy(lat, lon): return (lon-HOME[1])*kx, -(lat-HOME[0])
span = max(max(abs(v) for v in relxy(p["lat"], p["lon"])) for p in pts) * 1.06
sc = (min(W,H)/2 - PAD) / span

COLOR = {"Target":"#CC0000","Walmart":"#0071CE","Costco":"#E32227","Sam's Club":"#0067A0",
         "Best Buy":"#F0C000","GameStop":"#7B1FA2","Card shop":"#0B7A4B"}
HUNT = {
 "Target":("Tue &amp; Fri, 12&ndash;3 AM","Locked TCG case behind the counter, plus the toy-aisle endcap. Elite Trainer Boxes, booster bundles, blisters, mini tins. Ask staff to open the case."),
 "Walmart":("Wed, 6&ndash;9 PM","Locked case in electronics or the card spinner near the registers. Same mix as Target. The 6&ndash;9 PM window is the one you can actually attend."),
 "Costco":("Irregular","Pallet drops in the seasonal aisle. Bulk multi-packs and big collection boxes only &mdash; no single ETBs. Cheapest per pack when it lands, gone same day."),
 "Sam's Club":("Irregular","Same pattern as Costco. Membership required."),
 "GameStop":("Release day","Preorders at retail &mdash; worth setting up a standing one. Also carries Bushiroad product, so this is where Palworld shows up."),
 "Best Buy":("Irregular","Thin selection, mostly online. Low priority on a run."),
 "Card shop":("Release day","<b>Preorders at retail &mdash; the single most reliable way to buy at MSRP.</b> Booster boxes, cases, and Bushiroad lines like Palworld. Phone ahead and get on the list."),
}

store_json = json.dumps([{
    "n": p["name"], "ch": p["chain"], "d": p["d"],
    "a": " ".join(x for x in [p.get("hn"), p.get("street")] if x),
    "c": p.get("city") or "", "lat": p["lat"], "lon": p["lon"],
    "x": round(W/2 + relxy(p["lat"], p["lon"])[0]*sc, 1),
    "y": round(H/2 + relxy(p["lat"], p["lon"])[1]*sc, 1),
} for p in pts], separators=(",", ":"))

rings = "".join(
    f'<circle cx="{W/2}" cy="{H/2}" r="{(r/69.0)*sc:.1f}" class="ring"/>'
    f'<text x="{W/2}" y="{H/2-(r/69.0)*sc+12:.1f}" class="ringlbl">{r} mi</text>'
    for r in (5,10,15,20))
chain_chips = "".join(
    f'<button class="chipbtn ck" data-chain="{c}" aria-pressed="true">'
    f'<i style="background:{COLOR[c]}"></i>{c}</button>'
    for c in sorted({p["chain"] for p in pts}, key=lambda c: -sum(1 for p in pts if p["chain"]==c)))
hunt_rows = "".join(
    f'<tr><td><span class="chip" style="background:{COLOR[c]}"></span>{c}</td>'
    f'<td class="win"><b>{HUNT[c][0]}</b></td><td class="wnote">{HUNT[c][1]}</td></tr>'
    for c in ["Card shop","Walmart","Target","Costco","GameStop","Sam's Club","Best Buy"]
    if any(p["chain"] == c for p in pts))
near3 = len([p for p in pts if p["d"] <= 3])
hobby_n = len([p for p in pts if p["chain"] == "Card shop"])

CALENDAR = [
    ("2026-08-21", "OP-17 Release Event Cards",              "One Piece"),
    ("2026-08-21", "2026 Topps Flagship Football",           "Sports"),
    ("2026-08-28", "OP-17 World&rsquo;s Strongest Warriors", "One Piece"),
    ("2026-09-10", "2026 Bowman Chrome Baseball",            "Sports"),
    ("2026-09-16", "ME: 30th Celebration",                   "Pok&eacute;mon"),
    ("2026-09-18", "Set Sail Deck Set &middot; $69.96",      "One Piece"),
    ("2026-10-02", "Illumineer&rsquo;s Quest: Great Hunny Rescue", "Lorcana"),
    ("2026-10-02", "30th Celebration tins / bundle / binder","Pok&eacute;mon"),
    ("2026-10-16", "Hyperia City",                           "Lorcana"),
    ("2026-10-30", "EB-05 Heroines Edition vol.2",           "One Piece"),
    ("2026-10-30", "<b>Legends Awaken (BP02)</b>",           "Palworld"),
    ("2026-11-06", "ME06 Mega Evolution: Delta Reign",       "Pok&eacute;mon"),
]
import datetime as _dt
def _days(iso):
    y,m,d = map(int, iso.split("-"))
    return (_dt.date(y,m,d) - TODAY).days
cal_rows = "".join(
    f'<tr><td class="mono">{_dt.date(*map(int,iso.split("-"))).strftime("%d %b")}</td>'
    f'<td>{name}</td><td>{line}</td>'
    f'<td class="num mono">{"+" if _days(iso)>=0 else ""}{_days(iso)}d</td></tr>'
    for iso, name, line in CALENDAR if _days(iso) >= -3)

def _dayslabel(iso):
    n = _days(iso)
    return f'{"+" if n>=0 else ""}{n}d'
def _datelabel(iso):
    return _dt.date(*map(int, iso.split("-"))).strftime("%d %b")

def topcard(r):
    ch = (f'<div class="ch">Best card in set &middot; <b>{esc(r["c"])}</b> '
          f'<span class="mono">${r["cp"]:,.0f}</span></div>') if r["c"] else ""
    return (f'<article class="card buy"><div class="pad">'
            f'<span class="game">{esc(r["g"])} &middot; {esc(r["s"])}</span>'
            f'<b class="pname">{esc(r["p"])}</b>'
            f'<div class="prices mono"><span class="tag">shelf</span>'
            f'<span class="rp">${r["r"]:,.2f}</span><span class="arrow">&rarr;</span>'
            f'<span class="tag">worth</span><span class="mp">${r["m"]:,.2f}</span>'
            f'<span class="xx">{r["x"]:.2f}&times;</span></div>{ch}</div></article>')
top_cards = "".join(topcard(r) for r in shelf_rows[:3])

CSS = io.open(f"{SP}/hq.css", encoding="utf-8").read()
JS  = io.open(f"{SP}/hq.js",  encoding="utf-8").read()

# Singles catalogue for the Card Desk tabs. Produced by
#   project tcg-lister\export_web_catalog.py
# from the Card Desk SQLite. Absent is fine -- the tab says so.
_cards_path = f"{SP}/cards.json"
if os.path.exists(_cards_path):
    CARDS_JSON = io.open(_cards_path, encoding="utf-8").read()
    _cards = json.loads(CARDS_JSON)
    CARD_N, SET_N = len(_cards["cards"]), len(_cards["sets"])
else:
    CARDS_JSON = '{"sets":[],"cards":[]}'
    CARD_N = SET_N = 0

# Thumbnails as data URIs. A published page's CSP blocks remote images, so the
# picture has to travel inside the page. Produced by tcg-lister\fetch_thumbs.py.
_thumbs_path = f"{SP}/thumbs.json"
if os.path.exists(_thumbs_path):
    THUMBS_JSON = io.open(_thumbs_path, encoding="utf-8").read()
    THUMB_N = len(json.loads(THUMBS_JSON))
else:
    THUMBS_JSON = "{}"
    THUMB_N = 0

JS  = JS.replace("__ROWS__", json.dumps(rows, separators=(",", ":"))) \
        .replace("__STORES__", store_json) \
        .replace("__COLOR__", json.dumps(COLOR)) \
        .replace("__HUNT__", json.dumps({k: v[1] for k, v in HUNT.items()})) \
        .replace("__CARDS__", CARDS_JSON) \
        .replace("__BUILT__", json.dumps(TODAY.isoformat())) \
        .replace("__THUMBS__", THUMBS_JSON)

BODY = f'''<title>Card Run HQ</title>
<style>{CSS}</style>

<div class="topbar">
  <button class="menubtn" id="menuBtn" aria-label="Open navigation">&#9776;</button>
  <b id="barTitle">Drops</b>
</div>
<div class="scrim" id="scrim"></div>

<div class="app">
<nav class="sidebar" id="sidebar" role="tablist" aria-label="Sections" aria-orientation="vertical">
  <div class="brand"><b>Card Run HQ</b><span>Upland 91786 &middot; {STAMP}</span></div>

  <div class="navgroup">
    <p class="lbl">Buy &mdash; scouting</p>
    <button class="navlink" role="tab" id="t-drops" aria-controls="p-drops" aria-selected="true"><i></i>Drops</button>
    <button class="navlink" role="tab" id="t-shelf" aria-controls="p-shelf" aria-selected="false"><i></i>Shelf check</button>
    <button class="navlink" role="tab" id="t-map"   aria-controls="p-map"   aria-selected="false"><i></i>Map</button>
    <button class="navlink" role="tab" id="t-chase" aria-controls="p-chase" aria-selected="false"><i></i>Chase cards</button>
    <button class="navlink" role="tab" id="t-learn" aria-controls="p-learn" aria-selected="false"><i></i>Learn</button>
  </div>

  <div class="navgroup">
    <p class="lbl">Sell &mdash; my cards</p>
    <button class="navlink" role="tab" id="t-add"   aria-controls="p-add"   aria-selected="false"><i></i>Card desk</button>
  </div>

  <div class="navgroup">
    <p class="lbl">Sell &mdash; work it out</p>
    <button class="navlink" role="tab" id="t-sell"  aria-controls="p-sell"  aria-selected="false"><i></i>Price a card</button>
    <button class="navlink" role="tab" id="t-chan"  aria-controls="p-chan"  aria-selected="false"><i></i>Where to sell it</button>
    <button class="navlink" role="tab" id="t-rules" aria-controls="p-rules" aria-selected="false"><i></i>Pricing rules</button>
    <button class="navlink" role="tab" id="t-src"   aria-controls="p-src"   aria-selected="false"><i></i>Where prices come from</button>
    <button class="navlink" role="tab" id="t-plan"  aria-controls="p-plan"  aria-selected="false"><i></i>Build plan</button>
  </div>

  <div class="sidefoot">Buy side is a snapshot from {STAMP}.<br>Sell side calculates live in your browser.</div>
</nav>

<main class="wrap">
<header>
  <p class="lbl" style="margin:0">Sealed TCG scout &middot; Upland 91786 &middot; {STAMP}</p>
  <h1>Card Run HQ</h1>
  <p class="sub">Buying scout and selling desk, in one place.</p>
</header>

<!-- ============ DROPS ============ -->
<div role="tabpanel" id="p-drops" aria-labelledby="t-drops">
 <section>
  <h2>Next drops</h2>

  <article class="card buy">
   <div class="chead"><div class="ctitle"><span class="game">One Piece &middot; OP-17</span>
     <b>The World&rsquo;s Strongest Warriors</b><span><span class="pill buy">Preorder at retail</span></span></div>
    <div class="when"><span class="days mono">{_dayslabel("2026-08-28")}</span><span class="date mono">{_datelabel("2026-08-28")}</span></div></div>
   <div class="rows">
    <div class="row"><div class="rname">Booster Box <span class="lbl">24 packs</span></div>
     <div class="rnums mono"><span class="now">$366.33</span><br><span class="base">retail $119.76</span></div>
     <div class="bar"><div class="fill buy" style="width:76.5%"></div><div class="tick" style="left:25%"></div></div>
     <div class="barnote mono"><span>&#9650; retail</span><span><b>3.06&times;</b></span></div></div>
   </div>
   <p class="why"><b>Why buy:</b> trading <b>66% above</b> where OP-16 sits today, and OP-16 is already 1.84&times; retail. <b>Preorder at retail &mdash; do not pay $366.</b></p>
  </article>

  <article class="card watch">
   <div class="chead"><div class="ctitle"><span class="game">Pok&eacute;mon &middot; 30th anniversary</span>
     <b>ME: 30th Celebration</b><span><span class="pill watch">Wait &mdash; overheated</span></span></div>
    <div class="when"><span class="days mono">{_dayslabel("2026-09-16")}</span><span class="date mono">{_datelabel("2026-09-16")}</span></div></div>
   <div class="rows">
    <div class="row"><div class="rname">Pok&eacute;mon Center Elite Trainer Box</div>
     <div class="rnums mono"><span class="now">$529.15</span><br><span class="base">last set $128.20</span></div>
     <div class="bar"><div class="fill watch" style="width:100%"></div><div class="tick" style="left:24.2%"></div></div>
     <div class="barnote mono"><span>last set&rsquo;s level</span><span><b>4.13&times;</b> that</span></div></div>
   </div>
   <p class="why"><b>Why wait:</b> a normal ETB settles at <b>1.4&times;</b> retail. This asks <b>4.13&times;</b> the equivalent product on preorder guesses. Anniversary hype prices in early and often unwinds.</p>
  </article>

  <article class="card flag">
   <div class="chead"><div class="ctitle"><span class="game">Palworld &middot; Bushiroad</span>
     <b>Legends Awaken (BP02)</b><span><span class="pill flag">Watch &mdash; no price feed</span></span></div>
    <div class="when"><span class="days mono">{_dayslabel("2026-10-30")}</span><span class="date mono">{_datelabel("2026-10-30")}</span></div></div>
   <div class="rows">
    <div class="row"><div class="rname">Dawn of Palpagos box <span class="lbl">set 1, out 30 Jul</span></div>
     <div class="rnums mono"><span class="now">$165&ndash;200</span><br><span class="base">preorder was $44.99</span></div>
     <div class="bar"><div class="fill flag" style="width:82%"></div><div class="tick" style="left:22%"></div></div>
     <div class="barnote mono"><span>preorder level</span><span><b>unverified</b></span></div></div>
   </div>
   <p class="why"><b>Read this carefully.</b> Palworld has <b>no TCGplayer listing</b>, so none of it is scored automatically &mdash; these are hand-checked retailer prices and they conflict. Set 1 preordered around <b>$44.99</b>; retailers now ask <b>$164.99&ndash;$199.95</b>, and buyers reported it going from ~$50 to ~$150 after launch. Thin, volatile data.
   <br><br><b>What to do:</b> if you see Palworld at anywhere near $45, that is almost certainly worth taking. Don&rsquo;t trust a precise multiple. <b>Preorder BP02 &ldquo;Legends Awaken&rdquo; at retail</b> &mdash; GameStop and card shops carry Bushiroad.</p>
  </article>
 </section>

 <section>
  <h2>Confirmed calendar</h2>
  <div class="scroll"><table>
   <thead><tr><th>Date</th><th>Product</th><th>Line</th><th class="num">Out</th></tr></thead>
   <tbody>
{cal_rows}
   </tbody></table></div>
  <div class="note warn"><b>Palworld and sports are dates only.</b> Palworld has no TCGplayer listing and sports pricing is paywalled or singles-only, so neither is scored. Tracked, not priced.</div>
 </section>
</div>

<!-- ============ SHELF ============ -->
<div role="tabpanel" id="p-shelf" aria-labelledby="t-shelf" hidden>
 <section><div class="rule"><p class="big">The rule, in one line</p>
  <p><b>Buy anything at 2&times; or higher if it&rsquo;s priced at retail.</b> A 4&times; Elite Trainer Box costs $49.99 and is worth about $200. Below 1.5&times;, fees and shipping eat most of it. <b>Never pay above the shelf price shown.</b></p></div>
  <p class="srcline"><span class="agechip" data-priceage></span>
   <b>Shelf</b> is the verified MSRP &middot; <b>Worth</b> is the TCGplayer market price &middot;
   <b>Multiple</b> is worth &divide; shelf, which is the upcharge. <a href="#src">Full sources &rarr;</a></p>
 </section>
 <section><h2>Best things to find right now</h2>{top_cards}</section>
 <section>
  <h2>Search everything &mdash; {len(rows)} products</h2>
  <div class="tools">
   <input id="q" type="search" placeholder="Type what&rsquo;s on the shelf &mdash; prismatic, umbreon, fabled" autocomplete="off">
   <button class="chipbtn" id="f-store" aria-pressed="true">In stores only</button>
   <button class="chipbtn" id="f-buy" aria-pressed="false">2&times; and up</button>
   <span class="count" id="count"></span>
  </div>
  <div class="scroll"><table><thead><tr><th>Product</th><th>Where</th><th class="num">Shelf &middot; MSRP</th>
   <th class="num">Worth &middot; TCGplayer</th><th class="num">Upcharge</th><th>Buy at MSRP</th>
   <th>Best card in set</th></tr></thead>
   <tbody id="tb"></tbody></table></div>
  <div class="empty" id="empty" hidden>Nothing matches. Try a shorter word.</div>
 </section>
 <section>
  <div class="note warn"><b>A high multiple usually means it&rsquo;s already gone.</b> Prismatic Evolutions sits at 4&times; precisely because shelves got cleared. A &ldquo;grab it instantly if you see it&rdquo; list, not a shopping list.</div>
  <div class="note"><b>Where you can buy it.</b> <span class="wtag w-store">store</span> Target / Walmart / card shops. <span class="wtag w-online">online</span> Pok&eacute;mon Center only. <span class="wtag w-preorder">preorder</span> not released, price is a guess.</div>
 </section>
</div>

<!-- ============ MAP ============ -->
<div role="tabpanel" id="p-map" aria-labelledby="t-map" hidden>
 <section><div class="rule"><p class="big">{near3} card-selling stores inside 3 miles</p>
  <p>That density is the whole advantage. A sweep of everything under 3 miles is a <b>25-minute loop</b> &mdash; short enough to run on a restock morning, which is what actually gets you product at retail.</p></div></section>

 <section>
  <h2>Find a store</h2>
  <div class="tools">
   <input id="mq" type="search" placeholder="Search name, city or street &mdash; Upland, Foothill, Costco" autocomplete="off">
   <span class="count" id="mcount"></span>
  </div>
  <div class="tools" id="chainchips">{chain_chips}</div>
  <div class="tools" id="radchips">
   <span class="lbl" style="align-self:center">Within</span>
   <button class="chipbtn rad" data-r="3" aria-pressed="false">3 mi</button>
   <button class="chipbtn rad" data-r="5" aria-pressed="false">5 mi</button>
   <button class="chipbtn rad" data-r="10" aria-pressed="false">10 mi</button>
   <button class="chipbtn rad" data-r="20" aria-pressed="true">20 mi</button>
  </div>

  <div class="mapbox"><svg viewBox="0 0 {W} {H}" role="img" aria-label="Map of card-selling stores around Upland">
   {rings}
   <g id="dots"></g>
   <circle cx="{W/2}" cy="{H/2}" r="9" class="home"/>
   <circle cx="{W/2}" cy="{H/2}" r="2.5" fill="var(--ink)"/>
   <!-- labelled by ZIP, not "HOME" - this page is public, and a marker saying
        HOME over your own coordinates is a different thing to publish -->
   <text x="{W/2}" y="{H/2-15}" class="homelbl">91786</text>
  </svg></div>
  <p class="hint">Tap a store below to open directions. Filters change the map and the list together.</p>
  <div id="storelist" class="storelist"></div>
  <div class="empty" id="mempty" hidden>No stores match those filters.</div>
 </section>

 <section>
  <h2>What to hunt at each chain</h2>
  <div class="scroll"><table><thead><tr><th>Where</th><th>Restock</th><th>What to look for</th></tr></thead>
   <tbody>{hunt_rows}</tbody></table></div>
 </section>

 <section>
  <div class="note warn"><b>No live stock &mdash; blocked, not unfinished.</b> Target&rsquo;s inventory API returns 403 to any script, Walmart publishes no free per-store data, and Target.com&rsquo;s Pok&eacute;mon listings are third-party resellers marked &ldquo;not sold in stores&rdquo;. Use the Target app&rsquo;s own checker before driving.</div>
  <div class="note"><b>Card shops are under-mapped.</b> OpenStreetMap lists only {hobby_n} in range; the real number is higher. Worth phoning &mdash; a standing preorder is the most reliable way to buy at retail.</div>
 </section>
</div>

<!-- ============ CHASE ============ -->
<div role="tabpanel" id="p-chase" aria-labelledby="t-chase" hidden>
 <section><div class="teach"><h3>What a &ldquo;hit&rdquo; is</h3>
  <p>A <b>hit</b> is a valuable rare card pulled from a pack. The <b>chase card</b> is the most valuable card in a set &mdash; what people buy boxes hoping to find.</p>
  <ul><li><b>Pok&eacute;mon</b> &mdash; Special Illustration Rare, Mega Hyper Rare</li>
  <li><b>One Piece</b> &mdash; Manga, SEC, SP</li>
  <li><b>Lorcana</b> &mdash; Iconic, Enchanted</li></ul></div></section>
 <section><h2>Best card in each set</h2>
  <div class="scroll"><table><thead><tr><th>Set</th><th>Card</th><th>Rarity</th><th class="num">Worth</th></tr></thead>
  <tbody>{chase_rows}</tbody></table></div></section>
 <section>
  <div class="note warn"><b>The trap that costs beginners most.</b> A top Lorcana card is worth thousands and a box costs about $144, which makes opening it tempting.
   <ul><li><b>Don&rsquo;t.</b> Those cards turn up roughly once in many hundreds of packs.</li>
   <li>The chase price tells you <b>why the box is in demand</b> &mdash; not what a box returns.</li>
   <li><b>Selling sealed is the reliable trade.</b> Opening is gambling with a house edge.</li></ul></div>
  <div class="note"><b>Prices above ~$2,000 are thin.</b> Those cards trade a handful of times a year, so the marks move on very few sales.</div>
 </section>
</div>

<!-- ============ LEARN ============ -->
<div role="tabpanel" id="p-learn" aria-labelledby="t-learn" hidden>
 <section><h2>How this makes money</h2>
  <div class="teach"><ol class="steps">
   <li><div><b>Buy sealed product at retail (MSRP).</b> The sticker price at Target, Walmart, or a preorder at a card shop. This is the hard part.</div></li>
   <li><div><b>Some sets sell far above retail.</b> A One Piece box costs $119.76 and trades at $366.33 today.</div></li>
   <li><div><b>Resell it sealed &mdash; still shut.</b> You don&rsquo;t open it. That&rsquo;s the whole trade.</div></li>
  </ol><p style="margin-top:12px"><b>Your edge is access, not prediction.</b> Everyone sees these prices. Almost nobody can buy at retail.</p></div></section>

 <section><h2>The one number: the ratio</h2>
  <div class="teach"><p>Everywhere you see <b class="mono">3.06&times;</b> it means:</p>
   <p class="mono" style="background:var(--surface2);padding:9px 12px;border-radius:6px;font-size:12.5px">market price &divide; retail price &nbsp;=&nbsp; the ratio</p>
   <p><b>If I buy this at retail, what is it worth?</b></p>
   <div class="scale"><div class="scalebar"><div class="seg s1">UNDER 1.2&times;</div>
    <div class="seg s2">1.2&ndash;2&times;</div><div class="seg s3">OVER 2&times;</div></div>
    <div class="scalekey"><span>No margin</span><span>Normal</span><span>Strong demand</span></div></div>
   <ul><li><b class="mono">1.0&times;</b> &mdash; exactly retail. No profit.</li>
   <li><b class="mono">1.4&times;</b> &mdash; where a normal Pok&eacute;mon ETB settles. A baseline.</li>
   <li><b class="mono">3.0&times;</b> &mdash; real scarcity, or real hype.</li></ul>
   <p style="margin-top:10px"><b>Careful:</b> only profit if you actually buy at retail.</p></div></section>

 <section><h2>What one box earns</h2>
  <div class="teach"><h3>OP-17 booster box, bought at retail</h3>
   <div class="scroll" style="margin-top:8px"><table class="mono" style="min-width:340px"><tbody>
    <tr><td>Sells for (today)</td><td class="num">$366.33</td></tr>
    <tr><td>You paid retail</td><td class="num">&minus;$119.76</td></tr>
    <tr><td>eBay fees, ~13%</td><td class="num">&minus;$48.54</td></tr>
    <tr><td>Shipping, boxed</td><td class="num">&minus;$15.00</td></tr>
    <tr><td><b>Profit per box</b></td><td class="num"><b style="color:var(--buy)">&asymp; $183</b></td></tr>
   </tbody></table></div>
   <p style="margin-top:10px"><b>Two warnings.</b> That $366 is a preorder price on very few sales and will likely fall once boxes ship. And it only works if you buy at $119.76.</p></div></section>

 <section><h2>The pattern to act on</h2>
  <div class="scroll"><table class="mono"><thead><tr><th>Set</th><th>Game</th><th>Released</th>
   <th class="num">Box now</th><th class="num">&times; retail</th></tr></thead><tbody>
   <tr><td>OP-16 Time of Battle</td><td>One Piece</td><td>&minus;62d</td><td class="num">$220.44</td><td class="num">1.84&times;</td></tr>
   <tr><td>Wilds Unknown</td><td>Lorcana</td><td>&minus;97d</td><td class="num">$222.66</td><td class="num">1.55&times;</td></tr>
   <tr><td>Attack of the Vine!</td><td>Lorcana</td><td>&minus;27d</td><td class="num">$205.44</td><td class="num">1.43&times;</td></tr>
   <tr><td>ME04 Chaos Rising</td><td>Pok&eacute;mon</td><td>&minus;83d</td><td class="num">$189.99</td><td class="num">ETB 1.39&times;</td></tr>
   <tr><td>ME05 Pitch Black</td><td>Pok&eacute;mon</td><td>&minus;27d</td><td class="num">$174.25</td><td class="num">ETB 1.42&times;</td></tr>
  </tbody></table></div>
  <div class="note"><b>Older sets are worth more than newer ones.</b> Chaos Rising is 83 days old and beats Pitch Black at 27 days. Same in Lorcana.
   <p style="margin-top:7px">Sealed drifts <b>up</b> after release as shops sell through and nothing is reprinted.</p>
   <ul><li>Paying a preorder premium means buying at the most expensive moment.</li>
   <li>Buying <b>at retail on release day and holding</b> beats chasing preorder hype.</li></ul></div></section>

 <section><h2>What you&rsquo;re actually buying</h2>
  <div class="teach"><dl>
   <dt>Booster pack</dt><dd>A few random cards. Pok&eacute;mon 10, One Piece 12, Lorcana 12, <b>Palworld 7</b>.</dd>
   <dt>Booster box</dt><dd>A box of packs &mdash; Pok&eacute;mon 36, One Piece and Lorcana 24, <b>Palworld 12</b>. <b>The main resale unit.</b></dd>
   <dt>Case</dt><dd>Several booster boxes, usually 6&ndash;12. What shops buy from distributors.</dd>
   <dt>Elite Trainer Box (ETB)</dt><dd>Pok&eacute;mon only. ~9 packs plus sleeves, dice, storage box. The most common thing on a Target shelf.</dd>
   <dt>Illumineer&rsquo;s Trove</dt><dd>Lorcana&rsquo;s version of an ETB.</dd>
   <dt>Trial deck</dt><dd>Palworld&rsquo;s starter product &mdash; <i>Dawn of Palpagos</i> shipped two, Red&amp;Blue and Green&amp;Purple.</dd>
   <dt>MSRP</dt><dd>Retail price &mdash; the sticker. It never changes when a set gets hot. Anything above it is someone else&rsquo;s margin.</dd>
  </dl></div></section>
</div>

<!-- ============ SELL: PRICE A CARD ============ -->
<div role="tabpanel" id="p-sell" aria-labelledby="t-sell" hidden>
 <section>
  <h2>Price a card</h2>
  <div class="rule"><p class="big">The question this actually answers</p>
   <p>Not &ldquo;what is this card worth&rdquo; &mdash; <b>&ldquo;is it worth listing on its own?&rdquo;</b> eBay&rsquo;s fixed fees eat cheap singles alive. Everything under the floor belongs in a bulk lot instead.</p></div>

  <div class="calc">
   <div class="field"><label for="c-market">Market price (NM)</label>
    <input id="c-market" type="number" min="0" step="0.01" value="3.00" inputmode="decimal"></div>
   <div class="field"><label for="c-cond">Condition</label><select id="c-cond">
     <option value="NM" selected>Near Mint</option><option value="LP">Lightly Played</option>
     <option value="MP">Moderately Played</option><option value="HP">Heavily Played</option>
     <option value="DMG">Damaged</option></select></div>
   <div class="field"><label for="c-cost">Your cost</label>
    <input id="c-cost" type="number" min="0" step="0.01" value="0.30" inputmode="decimal"></div>
   <div class="field"><label for="c-ship">Buyer pays shipping</label>
    <input id="c-ship" type="number" min="0" step="0.01" value="1.00" inputmode="decimal"></div>
   <div class="field"><label for="c-store">eBay store</label><select id="c-store">
     <option value="none" selected>None &mdash; 250 free</option>
     <option value="basic">Basic &mdash; 1,000 free</option></select></div>
   <div class="field"><label for="c-vol">Listings this month</label>
    <input id="c-vol" type="number" min="0" step="10" value="100" inputmode="numeric"></div>
  </div>

  <div class="out">
   <div><span class="k">Ask</span><span class="v" id="o-ask">&mdash;</span></div>
   <div><span class="k">Tier</span><span class="v" id="o-tier">&mdash;</span></div>
   <div><span class="k">eBay takes</span><span class="v" id="o-fees">&mdash;</span></div>
   <div><span class="k">You net</span><span class="v" id="o-net">&mdash;</span></div>
  </div>

  <div class="verdict v-list" id="o-verdict">&mdash;</div>
 </section>

 <section><h2>Where every cent goes</h2>
  <div class="brk" id="o-brk"></div>
  <p class="hint">Postage flips to parcel above $20 &mdash; eBay Standard Envelope only covers cards under that.</p>
 </section>
</div>

<!-- ============ SELL: WHERE TO SELL IT ============ -->
<div role="tabpanel" id="p-chan" aria-labelledby="t-chan" hidden>
 <section>
  <h2>eBay or TCGplayer?</h2>
  <div class="rule"><p class="big">Same card, same ask, very different net</p>
   <p><b>eBay&rsquo;s fixed costs land on every card, because a cheap single IS its own order</b> &mdash; its own $0.30, its own envelope, its own insertion fee. On TCGplayer buyers fill a cart, so those same fixed costs split across the whole order. That gap is structural, not a rate difference.</p></div>

  <div class="calc">
   <div class="field"><label for="h-market">Market price (NM)</label>
    <input id="h-market" type="number" min="0" step="0.01" value="1.00" inputmode="decimal"></div>
   <div class="field"><label for="h-cond">Condition</label><select id="h-cond">
     <option value="NM" selected>Near Mint</option><option value="LP">Lightly Played</option>
     <option value="MP">Moderately Played</option><option value="HP">Heavily Played</option>
     <option value="DMG">Damaged</option></select></div>
   <div class="field"><label for="h-cost">Your cost</label>
    <input id="h-cost" type="number" min="0" step="0.01" value="0.00" inputmode="decimal"></div>
   <div class="field"><label for="h-order">Cards per TCG order</label>
    <input id="h-order" type="number" min="1" step="1" value="12" inputmode="numeric"></div>
   <div class="field"><label for="h-ship">Postage per TCG order</label>
    <input id="h-ship" type="number" min="0" step="0.01" value="1.00" inputmode="decimal"></div>
   <div class="field"><label for="h-vol">eBay listings this month</label>
    <input id="h-vol" type="number" min="0" step="10" value="300" inputmode="numeric"></div>
  </div>

  <div class="out">
   <div><span class="k">Ask, both channels</span><span class="v" id="h-ask">&mdash;</span></div>
   <div><span class="k">Tier</span><span class="v" id="h-tier">&mdash;</span></div>
  </div>

  <div class="vs">
   <div class="chan" id="e-box">
    <div class="hd"><span class="nm2">eBay</span><span class="badge"></span></div>
    <span class="big">&mdash;</span><span class="sub2">one card, one order</span>
    <div class="lines"></div>
   </div>
   <div class="chan" id="t-box">
    <div class="hd"><span class="nm2">TCGplayer</span><span class="badge"></span></div>
    <span class="big">&mdash;</span><span class="sub2">one of many in a cart</span>
    <div class="lines"></div>
   </div>
  </div>

  <div class="verdict v-list" id="h-verdict">&mdash;</div>
  <div class="note" id="h-cross">&mdash;</div>
 </section>

 <section><h2>Net is not the only axis</h2>
  <div class="note warn"><b>Read the comparison above carefully: TCGplayer wins on net almost everywhere.</b> That is a real result, not a bug &mdash; but net per sale is only half the question. <b>A card that nets $1 more and then sits unsold for six months is the worse card.</b> This calculator cannot see how fast something sells, and that is exactly where eBay earns its keep.</div>
  <div class="teach">
   <p><b>TCGplayer</b> &mdash; singles, and most of them. Better net, and buyers arrive already searching for a specific card by name.</p>
   <p><b>eBay</b> &mdash; the things TCGplayer will not list at all: <b>sealed product, graded slabs, and multi-card lots</b>. Also worth it for high-value singles, where a far bigger audience usually beats a dollar of fee difference.</p>
   <p><b>Bulk lot</b> &mdash; only what fails on <i>both</i>. Adding TCGplayer shrinks this pile a long way.</p>
   <p style="margin-bottom:0">The floor didn&rsquo;t disappear when TCGplayer arrived. It moved: a card is only lotted now when neither channel will carry it profitably.</p></div>
 </section>

 <section><h2>One card, one channel</h2>
  <div class="note warn"><b>Do not list the same physical card in both places.</b> Neither marketplace can be reached by API here, so nothing can pull a listing automatically when the other one sells. A double sale costs you a defect on eBay and a seller-level hit on TCGplayer. Card Desk allocates each copy to exactly one channel by default; overlap is opt-in, per card, and comes with a <b>Pull now</b> queue.</div>
 </section>

 <section><h2>Where the numbers come from</h2>
  <div class="teach">
   <p><b>TCGplayer, verified 2026:</b> 10.75% commission on Marketplace Seller levels 1&ndash;4 &mdash; up from 10.25% on 10 February 2026 &mdash; plus a 2.5% + $0.30 transaction fee on the whole order.</p>
   <p><b>eBay, verified 2026:</b> 13.25% final value fee, $0.30 per order at or under $10, $0.35 insertion past your free 250, eBay Standard Envelope $0.74&ndash;$1.32 for cards under $20.</p>
   <p style="margin-bottom:0"><b>Treat the TCGplayer side as modelled, not measured.</b> Order size is the dominant variable and it is a guess until real orders land. Postage is entered as a cost you absorb; TCGplayer shipping credits offset some of it, so the real figure is a little kinder than what is shown.</p></div>
 </section>
</div>

<!-- ============ SELL: PRICING RULES ============ -->
<div role="tabpanel" id="p-rules" aria-labelledby="t-rules" hidden>
 <section><h2>Tiered % of market</h2>
  <p class="hint">Cheap cards ask <i>above</i> market because the fees are fixed. Expensive cards ask <i>below</i> it to move.</p>
  <div class="scroll"><table><thead><tr><th>Market price</th><th class="num">Ask</th><th>Why</th></tr></thead>
   <tbody id="tierbody"></tbody></table></div>
 </section>

 <section><h2>Condition multipliers</h2>
  <div class="note warn"><b>The easiest way to lose money here.</b> TCGCSV market price is a <b>Near Mint</b> price. List a played card at the NM figure and you earn returns, refunds, and defects on your account.</div>
  <div class="scroll"><table><thead><tr><th>Condition</th><th class="num">Multiplier</th></tr></thead>
   <tbody id="condbody"></tbody></table></div>
 </section>

 <section><h2>The two guards</h2>
  <div class="teach">
   <p><b>Margin guard &mdash; cost &times; 1.15.</b> Never list below what you paid plus 15%.</p>
   <p><b>Net floor &mdash; $0.50.</b> Under this, the card routes to a bulk lot instead of a listing.</p>
   <p><b>.99 rounding.</b> $4.37 becomes $4.49. $12.10 becomes $11.99.</p>
   <p style="margin-bottom:0">They catch different failures, which is why there are two. The floor stops unprofitable <i>listings</i>. The margin guard stops selling <i>below cost</i>.</p></div>
 </section>

 <section><h2>Does an eBay Store pay for itself?</h2>
  <div class="calc">
   <div class="field"><label for="be-vol">Listings per month</label>
    <input id="be-vol" type="number" min="0" step="10" value="300" inputmode="numeric"></div>
   <div class="field"><label for="be-gross">Monthly gross sales</label>
    <input id="be-gross" type="number" min="0" step="50" value="1500" inputmode="decimal"></div>
  </div>
  <div class="out">
   <div><span class="k">No store, per month</span><span class="v" id="be-none">&mdash;</span></div>
   <div><span class="k">Basic store, per month</span><span class="v" id="be-basic">&mdash;</span></div>
  </div>
  <div class="verdict v-list" id="be-out">&mdash;</div>
  <p class="hint">No store: 250 free listings, then $0.35 each, 13.25% final value fee. Basic: ~$27.95/mo, 1,000 free listings, 12.35%.</p>
 </section>
</div>

<!-- ============ CARD DESK ============ -->
<div role="tabpanel" id="p-add" aria-labelledby="t-add" hidden>
 <section>
  <h2>Find a card</h2>
  <div class="searchbar">
   <input id="cd-q" type="search" autocomplete="off" spellcheck="false"
          placeholder="Type a card name &mdash; umbreon, charizard, elsa&hellip;">
   <button class="btn2" id="cd-clearq">Clear</button>
  </div>
  <p class="srcline"><span class="agechip" data-priceage></span>
   Every price here is the <b>TCGplayer market price</b>. There is no eBay price data
   anywhere in this dashboard. <a href="#src">Why, and what the eBay column means &rarr;</a></p>
  <p class="hint" id="cd-resnote"></p>
  <div id="cd-results" class="results"></div>
  <div class="added" id="cd-added"></div>

  <details class="fold">
   <summary>Know the set code? Type it instead</summary>
   <p>A set code and number jumps straight to one card, and you can bolt on condition, printing and quantity in one go:</p>
   <p class="shorthand"><code>pbl 86 *f nm x2</code></p>
   <div class="skey">
    <span><b>pbl</b> set code</span><span><b>86</b> number</span>
    <span><b>*f</b> foil &middot; <b>*rh</b> reverse</span>
    <span><b>nm lp mp hp dmg</b></span><span><b>x2</b> quantity</span>
   </div>
   <p class="hint">Everything after the code and number is optional. This is a shortcut, not a requirement &mdash; searching by name does the same job.</p>
  </details>
 </section>

 <section>
  <h2>My cards</h2>
  <div class="out">
   <div><span class="k">Lines</span><span class="v" id="cd-s-lines">0</span></div>
   <div><span class="k">Cards</span><span class="v" id="cd-s-qty">0</span></div>
   <div><span class="k">Market</span><span class="v" id="cd-s-mkt">$0.00</span></div>
   <div><span class="k">Best net</span><span class="v" id="cd-s-net">$0.00</span></div>
  </div>
  <p class="hint">Where they&rsquo;d go: <b id="cd-s-split">&mdash;</b></p>

  <div class="scroll"><table><thead><tr><th>Card</th><th>Qty</th><th>Condition</th>
   <th class="num">Market</th><th class="num">Ask</th><th class="num">Best net</th>
   <th>Route</th><th></th></tr></thead>
   <tbody id="cd-stock"></tbody></table>
   <div class="empty" id="cd-empty">Nothing here yet. Search for a card above and tap its price.</div></div>

  <div class="tools">
   <button class="btn2 go" id="cd-export" disabled>Export CSV</button>
   <button class="btn2" id="cd-wipe" disabled>Remove all</button>
   <span class="hint" id="cd-exmsg"></span>
  </div>
  <textarea id="cd-fallback" class="fallback" hidden readonly rows="8"></textarea>
  <div class="note" id="cd-status"></div>
 </section>

 <section>
  <div class="note warn"><b>This list and the desktop app are separate.</b> This one lives in your phone&rsquo;s browser. The desktop app holds the real database &mdash; the stock ledger, what each card cost you, where it is in the box, and the marketplace upload files. Sort here, export the CSV, bring it in. Prices here are frozen at {STAMP}; the desktop app pulls live ones.</div>
 </section>

 <details class="fold">
  <summary>Which sets are built into this page? <span class="hint" id="cd-setcount"></span></summary>
  <div class="scroll"><table><thead><tr><th>Code</th><th>Set</th><th>Game</th><th>Released</th></tr></thead>
   <tbody id="cd-sets"></tbody></table></div>
  <p class="hint">The desktop app can sync any set from TCGCSV. This page carries a snapshot of the recent ones so it keeps working with no signal.</p>
 </details>
</div>

<!-- ============ WHERE PRICES COME FROM ============ -->
<div role="tabpanel" id="p-src" aria-labelledby="t-src" hidden>
 <section>
  <h2>Where prices come from</h2>
  <div class="note warn"><b>There is one price source in this whole dashboard, and it is TCGplayer.</b> Nothing here is an eBay price. eBay&rsquo;s sold-price API has been closed to new developers since 2024 and its replacement is partner-only, so <b>no free eBay price data exists</b> for me to use.</div>
  <p><span class="agechip" data-priceage></span></p>
 </section>

 <section><h2>Every number on this dashboard</h2>
  <div class="scroll"><table><thead><tr><th>Number</th><th>Comes from</th><th>What it actually means</th></tr></thead>
   <tbody>
    <tr><td><b>Market</b></td><td><b>TCGCSV</b> &mdash; a free daily mirror of TCGplayer</td>
      <td>What the card is trading for on TCGplayer. Real, observed, per printing.</td></tr>
    <tr><td><b>Shelf</b> / MSRP</td><td>A <b>hand-checked table</b> in <span class="mono">pull_shelf.py</span></td>
      <td>The sticker price. Only filled in where it is verified per product type &mdash; blank rather than guessed.</td></tr>
    <tr><td><b>Multiple</b> <span class="mono">&times;</span></td><td>market &divide; MSRP</td>
      <td><b>The upcharge.</b> 1.4&times; is a normal resting point; 2&times;+ at retail is worth buying.</td></tr>
    <tr><td><b>Ask</b></td><td>Calculated here</td>
      <td>Market &times; the tier %, &times; a condition multiplier, floored at cost+15%, rounded to .99.</td></tr>
    <tr><td><b>Net on eBay</b></td><td>Calculated here</td>
      <td><b>Not an eBay price.</b> It is that same ask with eBay&rsquo;s published fees taken off.</td></tr>
    <tr><td><b>Net on TCGplayer</b></td><td>Calculated here</td>
      <td><b>Not a second price.</b> The same ask, with TCGplayer&rsquo;s fees taken off instead.</td></tr>
   </tbody></table></div>
  <div class="note"><b>So the two &ldquo;net&rdquo; columns are one price and two fee models.</b> They differ because eBay and TCGplayer charge differently &mdash; not because the card is worth different amounts in two places.</div>
 </section>

 <section><h2>Refreshing the prices</h2>
  <div class="note warn"><b>This page cannot refresh itself, and there is no button that could.</b> A published page is blocked from making requests to any outside server, tcgcsv.com included. A refresh button here would be a lie, so there isn&rsquo;t one. It is <b><span data-agedays>0</span> days</b> since these prices were pulled.</div>
  <div class="teach">
   <p><b>Ask Claude</b> &mdash; &ldquo;refresh the TCG dashboard&rdquo;. Takes about two minutes and republishes to this same address, so your bookmark keeps working.</p>
   <p style="margin-bottom:0"><b>Or run it yourself</b>, then ask me to republish:</p>
   <p class="mono" style="background:var(--surface2);padding:9px 12px;border-radius:6px;font-size:12px;margin-top:7px">cd "G:\\Claude\\project tcg-scout"<br>python pull_shelf.py shelf.json<br>python build_all.py . card-run-hq.html</p>
  </div>
  <div class="note"><b>The desktop app is different</b> &mdash; it pulls live from TCGCSV whenever you press sync, because it runs on your machine with no such restriction. Prices there are as fresh as your last sync.</div>
 </section>

 <section><h2>What is deliberately missing</h2>
  <div class="teach">
   <p><b>eBay sold comps.</b> Marketplace Insights is restricted to partners; the old Finding API was switched off in February 2025. Getting real eBay sold prices means paying a third party. Not worth it until the free path proves insufficient.</p>
   <p><b>Graded prices.</b> TCGplayer has none, so nothing here prices a slab.</p>
   <p style="margin-bottom:0"><b>Sports cards.</b> TCGplayer is trading-card-games only &mdash; no Topps or Panini category exists to read.</p></div>
 </section>
</div>

<!-- ============ SELL: BUILD PLAN ============ -->
<div role="tabpanel" id="p-plan" aria-labelledby="t-plan" hidden>
 <section><h2>What this page can and cannot do</h2>
  <div class="note"><b>Everything on the two tabs above runs live in your browser.</b> Scanning, inventory, and CSV export cannot &mdash; a published page has no scanner, no database, and is blocked from reaching tcgcsv.com. Those live in the local app.</div>
 </section>

 <section><h2>Build phases</h2>
  <div class="teach" style="display:flex;flex-direction:column;gap:14px">
   <div class="phase"><span class="pn">0</span><div><b>OCR spike.</b> Scan &rarr; split &rarr; identify, measured on a synthetic sheet first, then a real one. <b>Gate: report the hit rate before anything is built on top of it.</b></div></div>
   <div class="phase"><span class="pn">1</span><div><b>Core.</b> Catalog sync, database, batches, review queue, pricing, inventory tracker, CSV export.</div></div>
   <div class="phase"><span class="pn">2</span><div><b>Parsers.</b> eBay sales reports and collection-app exports. Closes the loop between predicted and actual net.</div></div>
   <div class="phase"><span class="pn">3</span><div><b>Lots.</b> The bulk-lot builder, so below-floor cards become sellable.</div></div>
   <div class="phase"><span class="pn">4</span><div><b>eBay API.</b> Photo upload straight to eBay, one-click publish. Removes the image-hosting step entirely.</div></div>
   <div class="phase"><span class="pn">5</span><div><b>Phone access.</b> cloudflared tunnel, so the dashboard works away from the desk.</div></div>
  </div>
 </section>

 <section><h2>Settled</h2>
  <div class="teach">
   <p><b>Capture &mdash; Brother MFC-L5850DW flatbed.</b> 24-bit colour, nine cards per sheet, driven from the app over WIA. About nine seconds a card.</p>
   <p><b>Never the document feeder.</b> The driver advertises a 14&Prime; range but that belongs to the ADF &mdash; rigid cards jam it and come out creased.</p>
   <p><b>Image hosting &mdash; this workstation.</b> eBay copies pictures to its own servers within 24 hours, so a temporary cloudflared tunnel is enough. No public repo, nothing permanent published.</p>
   <p style="margin-bottom:0"><b>Prices &mdash; TCGCSV.</b> Free, keyless, unlimited, and it covers singles as well as sealed.</p></div>
 </section>

 <section><h2>Still unknown</h2>
  <div class="note warn"><b>Scan-to-text accuracy has not been measured yet.</b> It depends on your cards and your scanner, not on anything research can settle. That is the entire reason phase 0 exists and gates the rest.</div>
 </section>
</div>

<footer class="mono">
 Prices &amp; sets: TCGCSV daily mirror of TCGplayer, pulled {STAMP} &middot; {len(shelf_data["sets"])} sets since Jan 2025.
 Locations: OpenStreetMap via Overpass, {int(RADIUS)} mi around 91786; straight-line distances.
 Palworld figures are hand-checked from retailers &mdash; no automated feed exists.
 Sell-side figures use published 2026 eBay rates; verify against your own invoice. Not investment advice.
</footer>
</main>
</div>
<script>{JS}</script>
'''

io.open(OUT, "w", encoding="utf-8").write(BODY)
print(f"wrote {OUT}\n  shelf={len(rows)} (store={len(shelf_rows)})  stores={len(pts)} "
      f"(<3mi={near3}, cardshops={hobby_n})  chase sets={len(chase)}")
