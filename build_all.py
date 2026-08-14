"""Card Run HQ - tabbed dashboard generator.
Usage: python build_all.py <scratchdir> <out.html>
Re-runnable: this is what the daily refresh calls after pull_shelf.py."""
import json, io, math, sys, html

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
JS  = JS.replace("__ROWS__", json.dumps(rows, separators=(",", ":"))) \
        .replace("__STORES__", store_json) \
        .replace("__COLOR__", json.dumps(COLOR)) \
        .replace("__HUNT__", json.dumps({k: v[1] for k, v in HUNT.items()}))

BODY = f'''<title>Card Run HQ</title>
<style>{CSS}</style>
<div class="wrap">
<header>
  <p class="lbl" style="margin:0">Sealed TCG scout &middot; Upland 91786 &middot; {STAMP}</p>
  <h1>Card Run HQ</h1>
  <p class="sub">What&rsquo;s dropping, what to grab off a shelf, where to drive, and how any of it makes money.</p>
</header>

<div class="tabs" role="tablist" aria-label="Sections">
  <button class="tab" role="tab" id="t-drops" aria-controls="p-drops" aria-selected="true">Drops</button>
  <button class="tab" role="tab" id="t-shelf" aria-controls="p-shelf" aria-selected="false">Shelf check</button>
  <button class="tab" role="tab" id="t-map"   aria-controls="p-map"   aria-selected="false">Map</button>
  <button class="tab" role="tab" id="t-chase" aria-controls="p-chase" aria-selected="false">Chase cards</button>
  <button class="tab" role="tab" id="t-learn" aria-controls="p-learn" aria-selected="false">Learn</button>
</div>

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
  <p><b>Buy anything at 2&times; or higher if it&rsquo;s priced at retail.</b> A 4&times; Elite Trainer Box costs $49.99 and is worth about $200. Below 1.5&times;, fees and shipping eat most of it. <b>Never pay above the shelf price shown.</b></p></div></section>
 <section><h2>Best things to find right now</h2>{top_cards}</section>
 <section>
  <h2>Search everything &mdash; {len(rows)} products</h2>
  <div class="tools">
   <input id="q" type="search" placeholder="Type what&rsquo;s on the shelf &mdash; prismatic, umbreon, fabled" autocomplete="off">
   <button class="chipbtn" id="f-store" aria-pressed="true">In stores only</button>
   <button class="chipbtn" id="f-buy" aria-pressed="false">2&times; and up</button>
   <span class="count" id="count"></span>
  </div>
  <div class="scroll"><table><thead><tr><th>Product</th><th>Where</th><th class="num">Shelf</th>
   <th class="num">Worth</th><th class="num">Multiple</th><th>Best card in set</th></tr></thead>
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
   <text x="{W/2}" y="{H/2-15}" class="homelbl">HOME</text>
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

<footer class="mono">
 Prices &amp; sets: TCGCSV daily mirror of TCGplayer, pulled {STAMP} &middot; {len(shelf_data["sets"])} sets since Jan 2025.
 Locations: OpenStreetMap via Overpass, {int(RADIUS)} mi around 91786; straight-line distances.
 Palworld figures are hand-checked from retailers &mdash; no automated feed exists. Not investment advice.
</footer>
</div>
<script>{JS}</script>
'''

io.open(OUT, "w", encoding="utf-8").write(BODY)
print(f"wrote {OUT}\n  shelf={len(rows)} (store={len(shelf_rows)})  stores={len(pts)} "
      f"(<3mi={near3}, cardshops={hobby_n})  chase sets={len(chase)}")
