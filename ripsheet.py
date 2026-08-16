"""Build a rip sheet: what to look for in a box, ticked off as you find it.

    python ripsheet.py                    # every set below
    python ripsheet.py --set asg          # just one
    python ripsheet.py --out "Rip sheet.html"

Opening a box and then typing the cards in from memory is where the money
leaks. Not because typing is slow, but because you do not know what you are
looking at while you are looking at it. A short print in this year's Series 2
is an ordinary-looking base card with an unexpected name on it; a parallel is
an ordinary-looking base card with a serial number on the BACK. Both go in the
bulk pile if nobody told you they were worth turning over.

So this writes a sheet you can stand a phone up next to while you sort. It is
one page, works offline, and knows three things a checklist normally does not:

  - the odds, so you can tell "I got unlucky" from "I missed it"
  - what a card LOOKS like, since you are sorting by eye, not by checklist
  - the traps, spelled out -- the numbers that are a short print this year

Ticking a line adds it to a list at the bottom, already carrying the set name,
the parallel and the sport, so all you type is the player. That list copies out
in the pipe-separated form the card desk's "Or paste a line" box reads, which
is what makes this a way in to the workbook rather than a second place cards
live. The sheet holds nothing itself -- close it and it is gone, by design.

Nothing here is a price. Prices move weekly and a number baked into a file in
August is a lie by October; what the sheet gives you is which cards are worth
looking up, which is the part that does not change.
"""

import argparse
import html
import json
import os
import sys

OUT = "Rip sheet.html"

# The pipe format the card desk's paste box reads. Kept here so a change to the
# desk's parser has one obvious other place to look.
PASTE_FIELDS = ["card", "set", "number", "variant", "condition", "qty",
                "worth", "sports or tcg"]

SETS = [
    {
        "key": "asg",
        "name": "2026 Topps Series 2 — All-Star Game Mega Box",
        "sub": "Philadelphia · $49.99 · 14 packs × 14 cards · 196 cards",
        "set_line": "2026 Topps Series 2 - All-Star Game",
        "sport": "sports",
        "warn": "No autographs and no relics in this product — don't rip it "
                "hunting a hit. Everything worth money here is either "
                "serial-numbered on the back or a short print hiding in plain "
                "sight.",
        "groups": [
            {
                "title": "Serial-numbered ASG parallels",
                "note": "The money. Turn the card OVER — the number is on "
                        "the back. Anything numbered is worth looking up "
                        "before it goes anywhere near a bulk pile.",
                "items": [
                    {"v": "Green ASG /99", "odds": "/99"},
                    {"v": "Gold ASG /50", "odds": "/50"},
                    {"v": "Orange ASG /25", "odds": "/25"},
                    {"v": "Black ASG /10", "odds": "/10"},
                    {"v": "Red ASG /5", "odds": "/5"},
                    {"v": "Platinum ASG 1/1", "odds": "1/1"},
                ],
            },
            {
                "title": "The short-print trap — cards #697 to #700",
                "note": "These four numbers carry two different players "
                        "depending on which version you got. If the name on "
                        "#697–700 is NOT Bryan Reynolds, Andre Pallante, "
                        "Jared Young or Freddie Freeman, you are holding the "
                        "short print. It looks like a base card. It is not.",
                "items": [
                    {"v": "Rookie SP", "odds": "#697–700",
                     "who": "Kevin McGonigle"},
                    {"v": "Rookie SP", "odds": "#697–700",
                     "who": "JJ Wetherholt"},
                    {"v": "Rookie SP", "odds": "#697–700",
                     "who": "Carson Benge"},
                    {"v": "Rookie SP", "odds": "#697–700",
                     "who": "Justin Crawford"},
                ],
            },
            {
                "title": "Unnumbered exclusives",
                "note": "Only in the mega box. Expect roughly 4–5 base ASG "
                        "and 2–3 of the 1991s across one box.",
                "items": [
                    {"v": "Base ASG parallel", "odds": "1:3 packs",
                     "look": "All-Star Game logo repeating in foil across the "
                             "background"},
                    {"v": "1991 Topps ASG", "odds": "1:5 packs",
                     "look": "the 1991 Topps design, 35 years on"},
                    {"v": "Holo Foil", "odds": "1:10 · ~1 per box"},
                    {"v": "Rainbow Foil", "odds": "1:10 · ~1 per box"},
                ],
            },
            {
                "title": "Rookies worth pulling out of the base",
                "note": "Base cards, so they look like the other 190. Worth "
                        "separating anyway — these are the names that "
                        "carry the set.",
                "items": [
                    {"v": "Base RC", "who": "Munetaka Murakami",
                     "look": "also has an SSP done as a 1992 Topps Gold Frank "
                             "Thomas homage — that one is the real chase"},
                    {"v": "Base RC", "who": "Roman Anthony"},
                    {"v": "Base RC", "who": "Trey Yesavage"},
                    {"v": "Base RC", "who": "Jac Caglianone"},
                    {"v": "Base RC", "who": "Tatsuya Imai"},
                    {"v": "Base RC", "who": "Bryce Eldridge"},
                ],
            },
            {
                "title": "Inserts",
                "note": "Common enough that most are a lot, not a listing. "
                        "Bundle them unless the name is big.",
                "items": [
                    {"v": "Stars of MLB", "odds": "1:2 packs"},
                    {"v": "Titans of the Game", "odds": "1:3 packs"},
                    {"v": "Glove Work", "odds": "1:6 packs"},
                    {"v": "Crooked Numbers", "odds": "insert"},
                ],
            },
        ],
    },
    {
        "key": "chromeblack",
        "name": "2026 Topps Chrome Black",
        "sub": "6 cards per pack · one parallel guaranteed in every pack",
        "set_line": "2026 Topps Chrome Black",
        "sport": "sports",
        "warn": "The guaranteed autograph in Chrome Black is the encased 13th "
                "card that comes with a HOBBY BOX — it is not inside the "
                "6-card packs. Loose single packs have had that card removed "
                "already. In the packs themselves autographs run about 1:7, so "
                "across 4 packs it is closer to a coin flip than a promise.",
        "groups": [
            {
                "title": "Refractor parallels",
                "note": "One per pack, guaranteed. Serial number on the back "
                        "— the colour alone does not tell you the tier.",
                "items": [
                    {"v": "Refractor /199", "odds": "/199"},
                    {"v": "Blue Refractor /150", "odds": "/150"},
                    {"v": "Green Refractor /99", "odds": "/99"},
                    {"v": "Purple Refractor /75", "odds": "/75"},
                    {"v": "Orange Refractor /25", "odds": "/25"},
                    {"v": "Rose Gold Refractor /10", "odds": "/10"},
                    {"v": "Red Refractor /5", "odds": "/5"},
                    {"v": "Superfractor 1/1", "odds": "1/1"},
                    {"v": "Mini Diamond Refractor", "odds": "/75 /50 /25"},
                    {"v": "Wave Refractor", "odds": "/75 /50 /25"},
                ],
            },
            {
                "title": "Autographs",
                "note": "About 1:7 packs for a pack-pulled auto. All of these "
                        "are numbered.",
                "items": [
                    {"v": "Chrome Black Autograph", "odds": "1:7 packs"},
                    {"v": "Ivory Autograph", "odds": "/50 or less",
                     "look": "36 cards in the set; the Ohtani 1/1 is the most "
                             "chased card in the product"},
                    {"v": "Paint It! Autograph", "odds": "/10",
                     "look": "19 cards, new this year"},
                    {"v": "Pitch Black Pairings dual auto", "odds": "/30",
                     "look": "two signatures on one card"},
                    {"v": "Super Futures Autograph", "odds": "numbered"},
                ],
            },
            {
                "title": "Inserts",
                "items": [
                    {"v": "Damascus", "odds": "short print, new"},
                    {"v": "Nocturnal", "odds": "insert"},
                    {"v": "Depth of Darkness", "odds": "insert"},
                    {"v": "Home Field Advantage", "odds": "insert, new"},
                ],
            },
            {
                "title": "Rookies worth separating",
                "note": "53 rookies on the checklist; these are the ones being "
                        "chased.",
                "items": [
                    {"v": "Base RC", "who": "Roman Anthony"},
                    {"v": "Base RC", "who": "Munetaka Murakami"},
                    {"v": "Base RC", "who": "Jac Caglianone"},
                    {"v": "Base RC", "who": "Bubba Chandler"},
                    {"v": "Base RC", "who": "Trey Yesavage"},
                    {"v": "Base RC", "who": "Nolan McLean"},
                    {"v": "Base RC", "who": "Jacob Misiorowski"},
                    {"v": "Base RC", "who": "Chase Burns"},
                    {"v": "Base RC", "who": "Kyle Teel"},
                    {"v": "Base RC", "who": "Sal Stewart"},
                ],
            },
        ],
    },
]


def find(key):
    for s in SETS:
        if s["key"] == key:
            return s
    sys.exit("no set called %r -- try: %s"
             % (key, ", ".join(s["key"] for s in SETS)))


CSS = """
:root{--bg:#f6f7f9;--surface:#fff;--surface2:#eef0f4;--line:#d7dbe2;
 --ink:#171a1f;--dim:#5c6472;--accent:#1f6feb;--warn:#8a5a00;
 --warnbg:#fff6e0;--good:#0a7d4f}
:root:not([data-theme=light]){}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
 --bg:#0f1216;--surface:#171b21;--surface2:#1e242c;--line:#2c333d;
 --ink:#e8ebf0;--dim:#97a1b0;--accent:#5a9bff;--warn:#ffc861;
 --warnbg:#2a2113;--good:#4ad395}}
:root[data-theme=dark]{--bg:#0f1216;--surface:#171b21;--surface2:#1e242c;
 --line:#2c333d;--ink:#e8ebf0;--dim:#97a1b0;--accent:#5a9bff;--warn:#ffc861;
 --warnbg:#2a2113;--good:#4ad395}
*{box-sizing:border-box}
body{margin:0;padding:0 14px 90px;background:var(--bg);color:var(--ink);
 font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:820px;margin:0 auto}
h1{font-size:19px;margin:20px 0 3px}
.sub{color:var(--dim);font-size:13px;margin:0 0 16px}
h2{font-size:15px;margin:26px 0 2px}
.note{color:var(--dim);font-size:13px;margin:0 0 10px}
.warn{background:var(--warnbg);border:1px solid var(--warn);color:var(--warn);
 border-radius:8px;padding:11px 13px;font-size:13.5px;margin:14px 0 4px}
.grp{background:var(--surface);border:1px solid var(--line);border-radius:10px;
 overflow:hidden;margin-bottom:6px}
.row{display:flex;align-items:center;gap:10px;padding:9px 12px;
 border-top:1px solid var(--line)}
.row:first-child{border-top:0}
.row .v{font-weight:600;font-size:14px}
.row .who{font-weight:600;font-size:14px}
.row .od{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;
 color:var(--dim);background:var(--surface2);border-radius:5px;padding:1px 7px;
 white-space:nowrap}
.row .lk{color:var(--dim);font-size:12.5px;flex:1 1 100%;margin-top:2px}
.row .mid{flex:1;min-width:0;display:flex;flex-wrap:wrap;gap:4px 9px;
 align-items:baseline}
.add{border:1px solid var(--line);background:var(--surface2);color:var(--ink);
 border-radius:7px;font-size:18px;line-height:1;width:34px;height:31px;
 cursor:pointer;flex:none}
.add:hover{border-color:var(--accent);color:var(--accent)}
#got{position:sticky;bottom:0;background:var(--surface);
 border:1px solid var(--line);border-radius:10px;padding:12px;margin-top:22px;
 box-shadow:0 -6px 22px rgba(0,0,0,.13)}
#got h2{margin:0 0 8px}
.pull{display:flex;gap:6px;align-items:center;margin-bottom:6px;flex-wrap:wrap}
.pull input{background:var(--bg);border:1px solid var(--line);color:var(--ink);
 border-radius:6px;padding:6px 8px;font-size:13px;min-width:0}
.pull .p-name{flex:2 1 150px}
.pull .p-num,.pull .p-worth{flex:0 1 78px}
.pull .p-var{flex:1 1 130px}
.pull .rm{border:0;background:none;color:var(--dim);cursor:pointer;
 font-size:17px;padding:0 5px}
.pull .rm:hover{color:#d1495b}
.btn{border:1px solid var(--line);background:var(--surface2);color:var(--ink);
 border-radius:8px;padding:8px 14px;font-size:13.5px;cursor:pointer}
.btn.go{background:var(--accent);border-color:var(--accent);color:#fff}
.msg{color:var(--good);font-size:12.5px;margin-left:9px}
.empty{color:var(--dim);font-size:13px}
textarea{width:100%;background:var(--bg);color:var(--ink);
 border:1px solid var(--line);border-radius:7px;padding:9px;font-size:12px;
 font-family:ui-monospace,Menlo,Consolas,monospace;margin-top:8px}
.fmt{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11.5px;
 color:var(--dim);background:var(--surface2);border-radius:6px;padding:7px 9px;
 overflow-x:auto;white-space:nowrap}
footer{color:var(--dim);font-size:12.5px;margin:26px 0 0}
"""

JS = """
var PULLS = [];

function esc(s){ return String(s == null ? '' : s); }

function addPull(setLine, sport, variant, who){
  PULLS.push({set:setLine, sport:sport, variant:variant || '',
              name:who || '', number:'', worth:''});
  draw();
  var box = document.getElementById('got');
  var last = box.querySelectorAll('.pull .p-name');
  if (last.length) last[last.length - 1].focus();
}

function draw(){
  var body = document.getElementById('pulls');
  if (!PULLS.length){
    body.innerHTML = '<div class="empty">Nothing yet. Tick a line above as ' +
      'you find it and it lands here.</div>';
    document.getElementById('out').value = '';
    return;
  }
  body.innerHTML = '';
  PULLS.forEach(function(p, i){
    var d = document.createElement('div');
    d.className = 'pull';
    d.innerHTML =
      '<input class="p-name"  placeholder="player"   value="' + esc(p.name) + '">' +
      '<input class="p-var"   placeholder="parallel" value="' + esc(p.variant) + '">' +
      '<input class="p-num"   placeholder="card #"   value="' + esc(p.number) + '">' +
      '<input class="p-worth" placeholder="worth"    value="' + esc(p.worth) + '">' +
      '<button class="rm" title="remove">&times;</button>';
    var ins = d.querySelectorAll('input');
    var keys = ['name','variant','number','worth'];
    ins.forEach(function(el, k){
      el.addEventListener('input', function(){
        PULLS[i][keys[k]] = el.value;
        writeOut();
      });
    });
    d.querySelector('.rm').addEventListener('click', function(){
      PULLS.splice(i, 1);
      draw();
    });
    body.appendChild(d);
  });
  writeOut();
}

/* card | set | number | variant | condition | qty | worth | sports or tcg */
function lineFor(p){
  return [p.name || '?', p.set, p.number || '', p.variant || '',
          'NM', '1', p.worth || '', p.sport].join(' | ');
}

function writeOut(){
  document.getElementById('out').value =
    PULLS.map(lineFor).join('\\n');
}

document.addEventListener('click', function(e){
  var b = e.target.closest('.add');
  if (!b) return;
  addPull(b.dataset.set, b.dataset.sport, b.dataset.variant, b.dataset.who);
});

document.getElementById('copy').addEventListener('click', function(){
  var ta = document.getElementById('out');
  if (!ta.value){ tell('Nothing to copy yet.'); return; }
  ta.select();
  var ok = false;
  try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
  if (navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(ta.value).then(function(){
      tell('Copied \\u2014 paste it into the card desk.');
    }, function(){
      tell(ok ? 'Copied \\u2014 paste it into the card desk.'
              : 'Select the box and copy by hand.');
    });
    return;
  }
  tell(ok ? 'Copied \\u2014 paste it into the card desk.'
          : 'Select the box and copy by hand.');
});

document.getElementById('clear').addEventListener('click', function(){
  if (!PULLS.length) return;
  PULLS = [];
  draw();
  tell('Cleared.');
});

var t;
function tell(m){
  var el = document.getElementById('msg');
  el.textContent = m;
  clearTimeout(t);
  t = setTimeout(function(){ el.textContent = ''; }, 3200);
}

draw();
"""


def render_row(s, it):
    e = html.escape
    bits = []
    who = it.get("who", "")
    if who:
        bits.append('<span class="who">%s</span>' % e(who))
    if it.get("v"):
        cls = "od" if who else "v"
        bits.append('<span class="%s">%s</span>' % (cls, e(it["v"])))
    if it.get("odds"):
        bits.append('<span class="od">%s</span>' % e(it["odds"]))
    if it.get("look"):
        bits.append('<span class="lk">%s</span>' % e(it["look"]))
    return (
        '<div class="row">'
        '<button class="add" title="I pulled one" '
        'data-set="%s" data-sport="%s" data-variant="%s" data-who="%s">+</button>'
        '<div class="mid">%s</div>'
        '</div>'
    ) % (e(s["set_line"]), e(s["sport"]), e(it.get("v", "")), e(who),
         "".join(bits))


def render(sets):
    e = html.escape
    out = []
    out.append("<!doctype html><html lang=en><head><meta charset=utf-8>")
    out.append('<meta name=viewport content="width=device-width,'
               'initial-scale=1">')
    out.append("<title>Rip sheet</title><style>%s</style></head><body>" % CSS)
    out.append('<div class="wrap">')

    for s in sets:
        out.append("<h1>%s</h1>" % e(s["name"]))
        out.append('<p class="sub">%s</p>' % e(s["sub"]))
        if s.get("warn"):
            out.append('<div class="warn">%s</div>' % e(s["warn"]))
        for g in s["groups"]:
            out.append("<h2>%s</h2>" % e(g["title"]))
            if g.get("note"):
                out.append('<p class="note">%s</p>' % e(g["note"]))
            out.append('<div class="grp">')
            for it in g["items"]:
                out.append(render_row(s, it))
            out.append("</div>")

    out.append('<div id="got"><h2>What I pulled</h2>')
    out.append('<div id="pulls"></div>')
    out.append('<div style="margin-top:9px">')
    out.append('<button class="btn go" id="copy">Copy paste lines</button> ')
    out.append('<button class="btn" id="clear">Clear</button>')
    out.append('<span class="msg" id="msg"></span></div>')
    out.append('<p class="fmt" style="margin-top:10px">%s</p>'
               % e(" | ".join(PASTE_FIELDS)))
    out.append('<textarea id="out" rows="4" readonly '
               'placeholder="lines appear here"></textarea>')
    out.append("</div>")

    out.append('<footer>Paste these into the card desk under '
               '<b>Or paste a line</b>. Nothing is saved here — close the '
               'page and it is gone, so copy before you leave. '
               'No prices are baked in: look up anything numbered before you '
               'price it.</footer>')
    out.append("</div>")
    out.append("<script>%s</script>" % JS)
    out.append("</body></html>")
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(
        description="Build a tickable rip sheet for a box you are opening.")
    p.add_argument("--set", action="append", dest="keys",
                   help="only this set (repeatable); default is all")
    p.add_argument("--out", default=OUT)
    p.add_argument("--list", action="store_true", help="show what is known")
    a = p.parse_args()

    if a.list:
        for s in SETS:
            n = sum(len(g["items"]) for g in s["groups"])
            print("%-14s %-52s %2d lines" % (s["key"], s["name"], n))
        return 0

    sets = [find(k) for k in a.keys] if a.keys else SETS
    body = render(sets)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(body)

    print("Wrote %s" % os.path.abspath(a.out))
    for s in sets:
        n = sum(len(g["items"]) for g in s["groups"])
        print("   %-52s %2d lines to look for" % (s["name"], n))
    print("\nOpen it next to you while you sort. Tick a line as you find it, "
          "type the player,\nthen Copy paste lines and paste them into the "
          "card desk's \"Or paste a line\" box.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
