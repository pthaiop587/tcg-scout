/* ---------------- sidebar nav ---------------- */
const tabs    = Array.from(document.querySelectorAll('[role="tab"]'));
const sideEl  = document.getElementById('sidebar');
const scrimEl = document.getElementById('scrim');
const titleEl = document.getElementById('barTitle');

function closeNav(){
  if(!sideEl) return;
  sideEl.classList.remove('open');
  if(scrimEl) scrimEl.classList.remove('on');
}
function openNav(){
  if(!sideEl) return;
  sideEl.classList.add('open');
  if(scrimEl) scrimEl.classList.add('on');
}
function show(id){
  tabs.forEach(t => {
    const on = t.id === id;
    t.setAttribute('aria-selected', on ? 'true' : 'false');
    const panel = document.getElementById(t.getAttribute('aria-controls'));
    if(panel) panel.hidden = !on;
    if(on && titleEl) titleEl.textContent = t.dataset.title || t.textContent.trim();
  });
  try { history.replaceState(null, '', '#' + id.slice(2)); } catch(e){}
  closeNav();
  window.scrollTo(0, 0);
}
tabs.forEach(t => t.addEventListener('click', () => show(t.id)));
const listEl = document.querySelector('[role="tablist"]');
if(listEl) listEl.addEventListener('keydown', e => {
  const i = tabs.indexOf(document.activeElement);
  if (i < 0) return;
  let n = null;
  if (e.key === 'ArrowDown'  || e.key === 'ArrowRight') n = (i + 1) % tabs.length;
  if (e.key === 'ArrowUp'    || e.key === 'ArrowLeft')  n = (i - 1 + tabs.length) % tabs.length;
  if (e.key === 'Home') n = 0;
  if (e.key === 'End')  n = tabs.length - 1;
  if (n === null) return;
  e.preventDefault(); tabs[n].focus(); show(tabs[n].id);
});
const menuBtn = document.getElementById('menuBtn');
if(menuBtn) menuBtn.addEventListener('click', () =>
  sideEl.classList.contains('open') ? closeNav() : openNav());
if(scrimEl) scrimEl.addEventListener('click', closeNav);
document.addEventListener('keydown', e => { if(e.key === 'Escape') closeNav(); });

/* price-age chips are on several tabs; stamp them once the DOM exists */
setTimeout(() => { try { stampPriceAge(); } catch(e){} }, 0);

function showFromHash(fallback){
  const h = (location.hash || '').slice(1);
  const id = document.getElementById('t-' + h) ? 't-' + h : fallback;
  if (id) show(id);
}
/* respond to hash changes too, not just first load - the runbook documents
   bookmarking straight to a section, and that must work from any tab */
window.addEventListener('hashchange', () => showFromHash(null));
showFromHash(tabs[0].id);

const esc = s => (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]);
const money = n => '$' + n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});

/* ---------------- where to buy it at MSRP ----------------
   Deep links into each retailer's own search. No API, no key, nothing to
   break -- and no live stock, because none of these publish it (Target 403s
   scripts outright). One tap each instead of one tap plus typing.        */
const RETAILERS = [
  {k:'Target',   s:'T',  u:q => 'https://www.target.com/s?searchTerm=' + q},
  {k:'Walmart',  s:'W',  u:q => 'https://www.walmart.com/search?q=' + q},
  {k:'Best Buy', s:'BB', u:q => 'https://www.bestbuy.com/site/searchpage.jsp?st=' + q},
  {k:'GameStop', s:'GS', u:q => 'https://www.gamestop.com/search/?q=' + q},
  {k:'Pokemon Center', s:'PC', pokemonOnly:true,
   u:q => 'https://www.pokemoncenter.com/search/' + q},
];

/* What it actually sells for, checked by hand.
   eBay's sold-price APIs are all shut to us -- Marketplace Insights is
   partner-only, Finding was switched off in Feb 2025, and Browse needs an
   eBay Partner Network contract. A sold-listings URL needs none of that, so
   the honest version of "check eBay" is one tap into the real thing. */
const CHECKERS = [
  {k:'eBay sold prices', s:'eBay sold', hot:true,
   u:q => 'https://www.ebay.com/sch/i.html?_nkw=' + q + '&LH_Sold=1&LH_Complete=1&_sop=13'},
  {k:'TCGplayer', s:'TCGplayer', tcgOnly:true,
   u:q => 'https://www.tcgplayer.com/search/all/product?q=' + q},
  {k:'SportsCardsPro price guide', s:'SportsCardsPro', sportsOnly:true,
   u:q => 'https://www.sportscardspro.com/search-products?q=' + q + '&type=prices'},
];

/* retailers list the product, not the set - drop set prefixes and punctuation */
function buyQuery(product, game){
  const t = (product || '')
    .replace(/\[[^\]]*\]/g, ' ')
    .replace(/\([^)]*\)/g, ' ')
    .replace(/[^\w\s&']/g, ' ')
    .replace(/\s+/g, ' ').trim();
  return encodeURIComponent(((game || '') + ' ' + t).trim());
}

function buyLinks(product, game){
  const q = buyQuery(product, game);
  const pk = /pok/i.test(game || '');
  return '<span class="buys">' + RETAILERS
    .filter(r => !r.pokemonOnly || pk)
    .map(r => '<a class="buylink" href="' + r.u(q) + '" target="_blank" rel="noopener nofollow" ' +
              'title="Search ' + r.k + '">' + r.s + '</a>').join('') + '</span>';
}

/* "what is it really worth" links - works for sports, where no free feed exists */
function checkLinks(product, game){
  const q = buyQuery(product, game);
  const sports = /sport|topps|panini|bowman/i.test(game || '');
  return '<span class="buys">' + CHECKERS
    .filter(c => (!c.tcgOnly || !sports) && (!c.sportsOnly || sports))
    .map(c => '<a class="buylink' + (c.hot ? ' hot' : '') + '" href="' + c.u(q) +
              '" target="_blank" rel="noopener nofollow" title="' + c.k + '">' +
              c.s + '</a>').join('') + '</span>';
}

/* ================= BOX LOG =================
   Every box bought, what it cost, what came back. Kept in this browser, same
   as the card desk -- no db capability exists for a published page, but
   localStorage does. Export to CSV before you rely on it living forever.   */
const LG_KEY = 'boxlog.v1';
let LOG = [];
let LG_PERSISTS = false, LG_EDIT = null;

function lgLoad(){
  try { const r = localStorage.getItem(LG_KEY); LG_PERSISTS = true;
        LOG = r ? (JSON.parse(r).rows || []) : []; }
  catch(e){ LG_PERSISTS = false; LOG = []; }
}
function lgSave(){
  if (!LG_PERSISTS) return;
  try { localStorage.setItem(LG_KEY, JSON.stringify({rows: LOG, at: Date.now()})); }
  catch(e){ LG_PERSISTS = false; }
}

const lgBody = document.getElementById('lg-body');
if (lgBody) {
  lgLoad();
  const $ = i => document.getElementById(i);
  const m = v => (v < 0 ? '\u2212$' : '$') + Math.abs(v).toFixed(2);
  const num = (el, d) => { const v = parseFloat(el.value); return isFinite(v) ? v : d; };
  const cost = r => r.paid * r.qty;
  const net  = r => r.rec - cost(r);

  /* Product suggestions come from the breakdown library so the two line up.
     Deferred: BOXES is declared below this block and `typeof` on a const in
     its temporal dead zone throws rather than returning "undefined". */
  setTimeout(() => {
    const pl = $('lg-prods');
    if (pl && Array.isArray(BOXES))
      pl.innerHTML = BOXES.map(b => '<option value="' + esc(b.name) + '">').join('');
  }, 0);

  function lgRender(){
    const spent = LOG.reduce((a, r) => a + cost(r), 0);
    const rec   = LOG.reduce((a, r) => a + r.rec, 0);
    const qty   = LOG.reduce((a, r) => a + r.qty, 0);
    $('lg-n').textContent = qty;
    $('lg-spent').textContent = m(spent);
    $('lg-rec').textContent = m(rec);
    $('lg-net').textContent = m(rec - spent);
    $('lg-net').style.color = rec - spent >= 0 ? 'var(--buy)' : 'var(--skip)';
    $('lg-roi').textContent = spent ? Math.round((rec - spent) / spent * 100) + '%' : '\u2014';
    $('lg-roi').style.color = rec >= spent ? 'var(--buy)' : 'var(--skip)';

    lgBody.innerHTML = LOG.map((r, i) => {
      const n = net(r), roi = cost(r) ? Math.round(n / cost(r) * 100) : 0;
      const tone = r.status === 'sealed' ? 'flag' : (n >= 0 ? 'buy' : 'skip');
      return '<tr><td class="mono">' + esc(r.bought || '') + '</td>' +
        '<td><b>' + esc(r.prod) + '</b>' + (r.qty > 1 ? ' <span class="pill">\u00d7' + r.qty + '</span>' : '') + '</td>' +
        '<td>' + esc(r.store || '') + '</td>' +
        '<td class="num mono">' + m(cost(r)) + '</td>' +
        '<td class="num mono">' + m(r.rec) + '</td>' +
        '<td class="num mono" style="color:' + (n >= 0 ? 'var(--buy)' : 'var(--skip)') + '">' + m(n) + '</td>' +
        '<td class="num mono">' + (r.status === 'sealed' ? '\u2014' : roi + '%') + '</td>' +
        '<td><span class="pill ' + tone + '">' + esc(r.status) + '</span></td>' +
        '<td class="wnote">' + esc(r.hits || '') + '</td>' +
        '<td class="num"><button class="linkbtn" data-ed="' + i + '">edit</button>' +
        '<button class="linkbtn" data-del="' + i + '">del</button></td></tr>';
    }).join('');
    $('lg-empty').hidden = LOG.length > 0;
    $('lg-export').disabled = $('lg-wipe').disabled = !LOG.length;

    /* rollups -- the reason this beats a pile of receipts */
    const roll = (key, into) => {
      const g = {};
      LOG.forEach(r => {
        const k = (r[key] || '(not recorded)').trim() || '(not recorded)';
        g[k] = g[k] || {spent:0, rec:0, n:0};
        g[k].spent += cost(r); g[k].rec += r.rec; g[k].n += r.qty;
      });
      const rows = Object.entries(g).sort((a,b) => (b[1].rec-b[1].spent) - (a[1].rec-a[1].spent));
      $(into).innerHTML = rows.length ? rows.map(([k, v]) => {
        const n = v.rec - v.spent, roi = v.spent ? Math.round(n / v.spent * 100) : 0;
        return '<article class="card ' + (n >= 0 ? 'buy' : 'skip') + '"><div class="pad">' +
          '<b class="pname">' + esc(k) + '</b>' +
          '<div class="prices mono"><span class="tag">' + v.n + ' box' + (v.n===1?'':'es') + '</span>' +
          '<span class="tag">spent</span><span class="rp">' + m(v.spent) + '</span>' +
          '<span class="arrow">\u2192</span><span class="tag">back</span>' +
          '<span class="mp">' + m(v.rec) + '</span><span class="xx">' + roi + '%</span></div>' +
          '</div></article>';
      }).join('') : '<p class="hint">Log a few boxes and this fills in.</p>';
    };
    roll('store', 'lg-bystore');
    roll('prod', 'lg-byprod');

    const sl = $('lg-stores');
    if (sl) sl.innerHTML = [...new Set(LOG.map(r => r.store).filter(Boolean))]
      .map(s => '<option value="' + esc(s) + '">').join('');

    const sn = $('lg-status-note');
    sn.className = 'note' + (LG_PERSISTS ? '' : ' warn');
    sn.innerHTML = LG_PERSISTS
      ? 'Saved in this browser. <b>Export the CSV periodically</b> \u2014 clearing site data would take it with it.'
      : '<b>This browser is blocking storage.</b> Nothing here will survive the tab closing \u2014 export before you go.';

    lgBody.querySelectorAll('[data-del]').forEach(b => b.onclick = () => {
      if (!confirm('Delete this row?')) return;
      LOG.splice(+b.dataset.del, 1); lgSave(); lgRender();
    });
    lgBody.querySelectorAll('[data-ed]').forEach(b => b.onclick = () => {
      const r = LOG[+b.dataset.ed];
      $('lg-date').value = r.bought; $('lg-prod').value = r.prod; $('lg-store').value = r.store;
      $('lg-paid').value = r.paid; $('lg-qty').value = r.qty; $('lg-status').value = r.status;
      $('lg-rec-in').value = r.rec; $('lg-hits').value = r.hits || '';
      LG_EDIT = +b.dataset.ed;
      $('lg-add').textContent = 'Save changes'; $('lg-cancel').hidden = false;
      $('lg-form-wrap').open = true;
      $('lg-form-wrap').scrollIntoView({block:'start'});
    });
  }

  function lgReset(){
    LG_EDIT = null;
    $('lg-add').textContent = 'Add to log'; $('lg-cancel').hidden = true;
    ['lg-prod','lg-store','lg-paid','lg-hits'].forEach(i => $(i).value = '');
    $('lg-qty').value = 1; $('lg-rec-in').value = 0; $('lg-status').value = 'sealed';
  }

  $('lg-add').addEventListener('click', () => {
    const prod = $('lg-prod').value.trim();
    if (!prod){ $('lg-msg').textContent = 'Give it a product name first.'; return; }
    const row = {bought: $('lg-date').value, prod, store: $('lg-store').value.trim(),
                 paid: num($('lg-paid'), 0), qty: Math.max(1, Math.round(num($('lg-qty'), 1))),
                 status: $('lg-status').value, rec: num($('lg-rec-in'), 0),
                 hits: $('lg-hits').value.trim()};
    if (LG_EDIT !== null) LOG[LG_EDIT] = row; else LOG.unshift(row);
    lgSave(); lgReset(); lgRender();
    $('lg-msg').textContent = LG_PERSISTS ? 'Saved.' : 'Added \u2014 but NOT saved, export before closing.';
    setTimeout(() => { $('lg-msg').textContent = ''; }, 3000);
  });
  $('lg-cancel').addEventListener('click', lgReset);

  $('lg-wipe').addEventListener('click', () => {
    if (!confirm('Delete the entire box log?')) return;
    LOG = []; lgSave(); lgRender();
  });

  $('lg-export').addEventListener('click', async () => {
    const rows = [['bought','product','where','qty','paid_each','total_cost',
                   'recovered','net','roi_pct','status','hits']];
    LOG.forEach(r => rows.push([r.bought, r.prod, r.store, r.qty, r.paid.toFixed(2),
      cost(r).toFixed(2), r.rec.toFixed(2), net(r).toFixed(2),
      cost(r) ? Math.round(net(r)/cost(r)*100) : '', r.status, r.hits || '']));
    const csv = rows.map(r => r.map(v => {
      const t = String(v == null ? '' : v);
      return /[",\n]/.test(t) ? '"' + t.replace(/"/g,'""') + '"' : t;
    }).join(',')).join('\n');
    const msg = $('lg-exmsg'); msg.textContent = 'Preparing\u2026';
    const stamp = new Date().toISOString().slice(0,10);
    try {
      const dl = await window.claude.use('downloads');
      if (!dl) throw {code:'unavailable'};
      try { await dl.save({filename:'box-log-' + stamp + '.csv', data:csv}); msg.textContent = 'Saved.'; }
      catch(err){
        if (err && err.code === 'extension_not_enabled'){
          await dl.save({filename:'box-log-' + stamp + '.csv.txt', data:csv});
          msg.textContent = 'Saved as .txt \u2014 rename it to .csv.';
        } else if (err && err.code === 'declined'){ msg.textContent = 'Cancelled.'; }
        else throw err;
      }
    } catch(err){
      msg.textContent = 'Downloads unavailable here \u2014 copy the text below.';
      const ta = $('lg-fallback'); ta.hidden = false; ta.value = csv; ta.select();
    }
  });

  if (!$('lg-date').value) $('lg-date').valueAsDate = new Date();
  lgRender();
}

/* ================= BOX BREAKDOWNS =================
   A searchable library rather than a tab per product -- adding a box is a line
   in boxes.json. Every claim here is sourced; anything unverified is left out
   rather than estimated.                                                    */
const BOXES = __BOXES__;

const bxEl = document.getElementById('bx-q');
if (bxEl) {
  const li = (arr, cls) => arr && arr.length
    ? '<ul class="bxlist ' + (cls || '') + '">' + arr.map(x => '<li>' + x + '</li>').join('') + '</ul>' : '';

  function bxCard(b){
    const paid = b.paid != null
      ? '<span class="pill buy">you paid $' + b.paid.toFixed(2) + '</span>' : '';
    const chase = (b.chase || []).map(c =>
      '<tr><td class="mono">' + esc(c.n) + '</td><td><b>' + esc(c.p) + '</b></td>' +
      '<td class="wnote">' + c.note + '</td></tr>').join('');
    const vals = (b.values || []).map(v =>
      '<tr><td><b>' + esc(v[0]) + '</b></td><td class="wnote">' + v[1] + '</td></tr>').join('');
    const q = encodeURIComponent(b.name.replace(/[^\w\s]/g, ' ').replace(/\s+/g, ' ').trim());
    return '<article class="card ' + (b.tone || 'flag') + '"><div class="pad">' +
      '<div class="shophead"><b class="pname">' + esc(b.name) + '</b>' + paid + '</div>' +
      '<div class="shopmeta"><span><b>' + esc(b.cat) + '</b></span>' +
        '<span>' + b.config + '</span>' +
        (b.prices ? '<span>' + esc(b.prices) + '</span>' : '') + '</div>' +

      (b.guaranteed && b.guaranteed.length
        ? '<div class="bxh">Guaranteed in every box</div>' + li(b.guaranteed, 'good') : '') +
      (b.typical && b.typical.length
        ? '<div class="bxh">Typical contents</div>' + li(b.typical) : '') +
      (chase ? '<div class="bxh">Worth pulling out</div><div class="scroll"><table>' +
        '<thead><tr><th>#</th><th>Card</th><th>Why</th></tr></thead><tbody>' +
        chase + '</tbody></table></div>' : '') +
      (vals ? '<div class="bxh">What things are worth</div><div class="scroll"><table><tbody>' +
        vals + '</tbody></table></div>' : '') +
      (b.notin && b.notin.length
        ? '<div class="bxh warnh">Not in this box</div>' + li(b.notin, 'bad') : '') +
      (b.verdict ? '<div class="bxh">Verdict</div><p class="shopnote">' + b.verdict + '</p>' : '') +

      '<div class="linkrow">' +
        '<a class="buylink hot" target="_blank" rel="noopener nofollow" href="' +
          'https://www.ebay.com/sch/i.html?_nkw=' + q + '&LH_Sold=1&LH_Complete=1&_sop=13">eBay sold</a>' +
        '<a class="buylink" target="_blank" rel="noopener nofollow" href="' +
          'https://www.pricecharting.com/search-products?q=' + q + '&type=prices">PriceCharting</a>' +
        '<a class="buylink" target="_blank" rel="noopener nofollow" href="' +
          'https://www.cardboardconnection.com/?s=' + q + '">Odds &amp; checklist</a>' +
      '</div></div></article>';
  }

  const bxRender = () => {
    const t = bxEl.value.trim().toLowerCase();
    const hits = BOXES.filter(b => !t ||
      (b.name + ' ' + b.cat + ' ' + (b.verdict || '')).toLowerCase().includes(t));
    const out = document.getElementById('bx-out');
    out.innerHTML = hits.length
      ? hits.map(bxCard).join('')
      : '<p class="hint">Nothing matches. Ask me to add it &mdash; a new box is one entry in ' +
        '<span class="mono">boxes.json</span>, not a new tab.</p>';
  };
  let bxT = null;
  bxEl.addEventListener('input', () => { clearTimeout(bxT); bxT = setTimeout(bxRender, 110); });
  document.getElementById('bx-clear').addEventListener('click', () => {
    bxEl.value = ''; bxRender(); bxEl.focus();
  });
  bxRender();
}

/* ================= PRICE CHECK =================
   Type anything -- including things this dashboard has never heard of, like a
   sports mega box -- and get every price source in one tap, plus the local
   breakdown when it IS something we know about.

   PriceCharting is the one site that covers TCG, sports AND sealed boxes in a
   single free guide. Verified 15 Aug 2026: its TMNT Draft Night reads $81.22
   against this dashboard's $79.79, which is a useful independent check.       */
const PTYPES = __PTYPES__;

const SOURCES = [
  {k:'PriceCharting', d:'Everything: TCG, sports, sealed, graded', hot:true,
   u:q => 'https://www.pricecharting.com/search-products?q=' + q + '&type=prices'},
  {k:'eBay sold', d:'What it actually sold for, last 90 days', hot:true,
   u:q => 'https://www.ebay.com/sch/i.html?_nkw=' + q + '&LH_Sold=1&LH_Complete=1&_sop=13'},
  {k:'TCGplayer', d:'The TCG market price this dashboard uses',
   u:q => 'https://www.tcgplayer.com/search/all/product?q=' + q},
  {k:'SportsCardsPro', d:'Sports only \u2014 PSA, BGS and raw',
   u:q => 'https://www.sportscardspro.com/search-products?q=' + q + '&type=prices'},
  {k:'130point', d:'Sold comps across eBay, Goldin and PWCC',
   u:q => 'https://130point.com/sales/'},
  {k:'Cardboard Connection', d:'Box contents, odds and checklists',
   u:q => 'https://www.cardboardconnection.com/?s=' + q},
];

function typeOf(name){
  const n = (name || '').toLowerCase();
  for (const p of PTYPES){ if (new RegExp(p.re).test(n)) return p; }
  return null;
}

const pcEl = document.getElementById('pc-q');
if (pcEl) {
  const money2 = v => (v < 0 ? '\u2212$' : '$') + Math.abs(v).toFixed(2);
  let pcT = null;
  const render = () => {
    const raw = pcEl.value.trim();
    const box = document.getElementById('pc-out');
    if (raw.length < 2){
      box.innerHTML = '<p class="hint">Type a product name \u2014 a box, a tin, a single, ' +
        'a sports mega box, anything. It does not have to be something this page tracks.</p>';
      return;
    }
    const q = encodeURIComponent(raw);
    let html = '<div class="srcgrid">' + SOURCES.map(s =>
      '<a class="srccard' + (s.hot ? ' hot' : '') + '" href="' + s.u(q) +
      '" target="_blank" rel="noopener nofollow"><b>' + esc(s.k) + '</b>' +
      '<span>' + esc(s.d) + '</span></a>').join('') + '</div>';

    /* does the local catalogue know this thing? */
    const t = raw.toLowerCase();
    const hits = ROWS.filter(r => (r.p + ' ' + r.s + ' ' + r.g).toLowerCase().includes(t))
                     .slice(0, 6);
    if (hits.length){
      html += '<h2 style="margin-top:20px">What this page already knows ' +
              '<span class="hint">' + hits.length + ' match' + (hits.length===1?'':'es') + '</span></h2>';
      html += hits.map(r => {
        const pt = typeOf(r.p);
        const st = pt && pt.st;
        const up = r.x != null
          ? '<span class="tag">shelf</span><span class="rp">' + money(r.r) + '</span>' +
            '<span class="arrow">\u2192</span><span class="tag">worth</span>' +
            '<span class="mp">' + money(r.m) + '</span><span class="xx">' + r.x.toFixed(2) + '\u00d7</span>'
          : '<span class="tag">market</span><span class="mp">' + money(r.m) + '</span>' +
            '<span class="xx">no published MSRP</span>';
        const tone = r.x == null ? 'flag' : (r.x >= 2 ? 'buy' : (r.x >= 1.5 ? 'watch' : 'skip'));
        const typeInfo = pt
          ? '<div class="shopmeta"><span><b>Type</b> ' + esc(pt.t) + '</span>' +
            (st ? '<span><b>Typical net</b> ' + money2(st.net) + '</span>' +
                  '<span><b>Return</b> ' + Math.round(st.pct) + '%</span>' +
                  '<span><b>Sample</b> ' + st.n + '</span>' : '') + '</div>' +
            '<p class="shopnote">' + pt.blurb + '</p>'
          : '';
        return '<article class="card ' + tone + '"><div class="pad">' +
          '<span class="game">' + esc(r.g) + ' \u00b7 ' + esc(r.s) + '</span>' +
          '<b class="pname">' + esc(r.p) + '</b>' +
          '<div class="prices mono">' + up + '</div>' + typeInfo +
          '<div class="linkrow">' + buyLinks(r.p, r.g) + checkLinks(r.p, r.g) + '</div>' +
          '</div></article>';
      }).join('');
    } else {
      html += '<div class="note" style="margin-top:16px"><b>Not in this page\u2019s catalogue.</b> ' +
        'That is expected for sports and for anything outside the eleven games tracked here \u2014 ' +
        'the links above still work on it.</div>';
    }
    box.innerHTML = html;
  };
  pcEl.addEventListener('input', () => { clearTimeout(pcT); pcT = setTimeout(render, 130); });
  document.getElementById('pc-clear').addEventListener('click', () => {
    pcEl.value = ''; render(); pcEl.focus();
  });
  /* deferred: render() reads ROWS, which is declared further down this file and
     would still be in its temporal dead zone if called inline */
  setTimeout(render, 0);
}

/* ================= RESTOCK WINDOWS =================
   Researched 15 Aug 2026, converted from Eastern to Pacific because every
   guide quotes ET and he is in Upland. days: 0=Sun .. 6=Sat, null = any weekday.
   Times are local Pacific, 24h.                                            */
const DROPS = [
  {n:'Pok\u00e9mon Center', days:[1,2,3,4,5], from:7.0, to:10.25, peak:8.0,
   note:'Queue opens somewhere in this band, most often around <b>8am</b>. The old ' +
        '"Tuesday and Thursday" rule is wrong \u2014 2026 data has Wednesday as the ' +
        'busiest day by far. Surprise restocks hit any weekday.', tone:'buy'},
  {n:'Target.com', days:[0,1,2,3,4,5,6], from:22.0, to:24.0,
   note:'Overnight, when their distribution centres process inventory and site ' +
        'traffic is low. Sells out in <b>under two minutes</b>.', tone:'watch'},
  {n:'Walmart.com', days:[3], from:17.0, to:19.0,
   note:'Wednesday evening \u2014 about <b>87%</b> of drops land Wednesday. Gone in ' +
        'seconds. Note this is the evening, not the morning most guides claim.', tone:'watch'},
  {n:'GameStop.com', days:null, from:null, to:null,
   note:'No fixed window \u2014 it drops when distributor allocation arrives. But it ' +
        'stays live <b>5\u201320 minutes</b> instead of under two, which makes it the ' +
        'one you can realistically catch by hand.', tone:'buy'},
  {n:'Best Buy', days:null, from:null, to:null,
   note:'<b>Invitation lottery.</b> No window to watch and no speed advantage to be ' +
        'had \u2014 request an invite on the product page and wait for the draw.', tone:'flag'},
];

const dropBox = document.getElementById('dropwins');
if (dropBox) {
  const DAYN = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  const hhmm = h => {
    const H = Math.floor(h) % 24, M = Math.round((h - Math.floor(h)) * 60);
    const ap = H < 12 ? 'am' : 'pm', h12 = H % 12 === 0 ? 12 : H % 12;
    return h12 + (M ? ':' + String(M).padStart(2, '0') : '') + ap;
  };
  /* hours until the next time this window opens, in the viewer's own clock */
  function nextOpen(d){
    if (d.from === null || !d.days) return null;
    const now = new Date();
    for (let add = 0; add < 8; add++){
      const c = new Date(now); c.setDate(now.getDate() + add);
      if (!d.days.includes(c.getDay())) continue;
      c.setHours(Math.floor(d.from), Math.round((d.from % 1) * 60), 0, 0);
      if (c > now) return (c - now) / 3600000;
    }
    return null;
  }
  const label = hrs => hrs == null ? '' :
    hrs < 1 ? Math.round(hrs * 60) + ' min' :
    hrs < 24 ? Math.round(hrs) + ' hr' : Math.round(hrs / 24) + ' days';

  const render = () => {
    dropBox.innerHTML = DROPS.map(d => {
      const when = d.from === null
        ? '<span class="tag">no fixed window</span>'
        : '<span class="tag">' + (d.days.length === 7 ? 'daily'
            : d.days.length === 5 ? 'weekdays' : d.days.map(x => DAYN[x]).join(', ')) +
          '</span><span class="mp">' + hhmm(d.from) + ' \u2013 ' + hhmm(d.to) + '</span>' +
          (d.peak ? '<span class="tag">peak</span><span class="rp">' + hhmm(d.peak) + '</span>' : '');
      const nx = nextOpen(d);
      const cd = nx == null ? '' : '<span class="xx">in ' + label(nx) + '</span>';
      return '<article class="card ' + d.tone + '"><div class="pad">' +
        '<b class="pname">' + d.n + '</b>' +
        '<div class="prices mono">' + when + cd + '</div>' +
        '<p class="shopnote">' + d.note + '</p></div></article>';
    }).join('');
  };
  render();
  setInterval(render, 60000);   /* keep the countdowns honest */
}

/* ---- fill the per-card link rows on the tiered shelf lists ---- */
document.querySelectorAll('.linkrow[data-links]').forEach(el => {
  el.innerHTML = buyLinks(el.dataset.links, el.dataset.game) +
                 checkLinks(el.dataset.links, el.dataset.game);
});

/* ---- things we track but cannot price: sports, Palworld ---- */
const UNPRICED = __UNPRICED__;
const upBody = document.getElementById('unpriced');
if (upBody) {
  upBody.innerHTML = UNPRICED.map(u =>
    '<tr><td class="mono">' + esc(u.d) + '<br><span class="setname">' +
      (u.days >= 0 ? '+' + u.days : u.days) + 'd</span></td>' +
    '<td>' + u.n + '</td><td>' + esc(u.l) + '</td>' +
    '<td>' + buyLinks(u.n.replace(/<[^>]+>/g, ''), u.l) + '</td>' +
    '<td>' + checkLinks(u.n.replace(/<[^>]+>/g, ''), u.l) + '</td></tr>').join('')
    || '<tr><td colspan="5" class="setname">Nothing upcoming.</td></tr>';
}

/* ---------------- shelf search ---------------- */
const ROWS = __ROWS__;
const tb=document.getElementById('tb'), q=document.getElementById('q'),
      cnt=document.getElementById('count'), empty=document.getElementById('empty'),
      fStore=document.getElementById('f-store'), fBuy=document.getElementById('f-buy');
function renderShelf(){
  const term=q.value.trim().toLowerCase();
  const onlyStore=fStore.getAttribute('aria-pressed')==='true';
  const onlyBuy=fBuy.getAttribute('aria-pressed')==='true';
  const list=ROWS.filter(r=>{
    if(onlyStore && r.w!=='store') return false;
    if(onlyBuy && !(r.x >= 2)) return false;   /* null ratio is not "2x and up" */
    if(!term) return true;
    return (r.p+' '+r.s+' '+r.g+' '+(r.c||'')).toLowerCase().indexOf(term)>-1;
  });
  cnt.textContent=list.length+' of '+ROWS.length+' shown';
  empty.hidden=list.length>0;
  tb.innerHTML=list.map(r=>{
    /* Magic has no published MSRP, so r.x and r.r are null there */
    const hasMsrp = r.x != null;
    const cls = !hasMsrp ? 'x-lo' : (r.x>=2?'x-hi':(r.x>=1.5?'x-mid':'x-lo'));
    const ch=r.c ? '<b>'+esc(r.c)+'</b><br>'+money(r.cp)+(r.cr?' &middot; '+esc(r.cr):'')
                 : '<span style="opacity:.55">not listed yet</span>';
    return '<tr><td><div class="prod">'+esc(r.p)+'</div><div class="setname">'+esc(r.g)+' &middot; '+esc(r.s)+'</div></td>'
      +'<td><span class="wtag w-'+r.w+'">'+r.w+'</span></td>'
      +'<td class="num mono">'+(hasMsrp?money(r.r):'<span style="opacity:.45">none</span>')+'</td>'
      +'<td class="num mono">'+money(r.m)+'</td>'
      +'<td class="num mono xcell '+cls+'">'
        +(hasMsrp?r.x.toFixed(2)+'&times;':'<span style="opacity:.45">&mdash;</span>')+'</td>'
      +'<td>'+buyLinks(r.p, r.g)+'</td>'
      +'<td>'+checkLinks(r.p, r.g)+'</td>'
      +'<td class="chasecell mono">'+ch+'</td></tr>';
  }).join('');
}
const tog=b=>{b.setAttribute('aria-pressed',b.getAttribute('aria-pressed')==='true'?'false':'true');renderShelf();};
q.addEventListener('input',renderShelf);
fStore.addEventListener('click',()=>tog(fStore));
fBuy.addEventListener('click',()=>tog(fBuy));
renderShelf();

/* ---------------- interactive map ---------------- */
const STORES = __STORES__;
const COLOR  = __COLOR__;
const HUNT   = __HUNT__;
const dotsG=document.getElementById('dots'), mq=document.getElementById('mq'),
      mcount=document.getElementById('mcount'), mempty=document.getElementById('mempty'),
      slist=document.getElementById('storelist');
const chainBtns=Array.from(document.querySelectorAll('#chainchips .ck'));
const radBtns=Array.from(document.querySelectorAll('#radchips .rad'));

/* draw every dot once; filtering just toggles a class */
dotsG.innerHTML = STORES.map((s,i)=>
  '<circle cx="'+s.x+'" cy="'+s.y+'" r="'+(s.ch==='Card shop'?7:5.5)+'" '
  +'fill="'+COLOR[s.ch]+'" class="dot" data-i="'+i+'">'
  +'<title>'+esc(s.n)+' &#183; '+s.d+' mi</title></circle>').join('');
const dotEls = Array.from(dotsG.children);

function activeChains(){
  return chainBtns.filter(b=>b.getAttribute('aria-pressed')==='true')
                  .map(b=>b.dataset.chain);
}
function activeRadius(){
  const on = radBtns.find(b=>b.getAttribute('aria-pressed')==='true');
  return on ? parseFloat(on.dataset.r) : 20;
}
function renderMap(){
  const term=mq.value.trim().toLowerCase();
  const chains=activeChains(), rad=activeRadius();
  const keep=new Set();
  STORES.forEach((s,i)=>{
    if(chains.indexOf(s.ch)<0) return;
    if(s.d>rad) return;
    if(term && (s.n+' '+s.a+' '+s.c+' '+s.ch).toLowerCase().indexOf(term)<0) return;
    keep.add(i);
  });
  dotEls.forEach((el,i)=>el.classList.toggle('off', !keep.has(i)));
  const list=STORES.map((s,i)=>({s,i})).filter(o=>keep.has(o.i));
  mcount.textContent=list.length+' of '+STORES.length+' stores';
  mempty.hidden=list.length>0;
  slist.innerHTML=list.slice(0,60).map(o=>{
    const s=o.s;
    const addr=[s.a, s.c].filter(Boolean).join(', ') || 'address not mapped';
    const url='https://www.google.com/maps/search/?api=1&query='+s.lat+','+s.lon;
    return '<a class="st" href="'+url+'" target="_blank" rel="noopener">'
      +'<span class="swatch" style="background:'+COLOR[s.ch]+'"></span>'
      +'<span class="body"><span class="nm">'+esc(s.ch)+'</span>'
      +'<span class="ad">'+esc(addr)+'</span>'
      +'<span class="hunt">'+HUNT[s.ch]+'</span></span>'
      +'<span><span class="mi">'+s.d+' mi</span><span class="go">Directions &rarr;</span></span></a>';
  }).join('');
}
mq.addEventListener('input',renderMap);
chainBtns.forEach(b=>b.addEventListener('click',()=>{
  b.setAttribute('aria-pressed', b.getAttribute('aria-pressed')==='true'?'false':'true');
  renderMap();
}));
radBtns.forEach(b=>b.addEventListener('click',()=>{
  radBtns.forEach(o=>o.setAttribute('aria-pressed','false'));
  b.setAttribute('aria-pressed','true');
  renderMap();
}));
renderMap();

/* ---------------- sell: pricing + fee engine ----------------
   Mirrors SPEC.md 7.6 exactly. Change one, change the other.   */
const TIERS = [
  {max:2.00,  pct:130, note:'fees dominate &mdash; ask high or lot it'},
  {max:5.00,  pct:115, note:''},
  {max:20.00, pct:105, note:''},
  {max:100.00,pct:98,  note:''},
  {max:null,  pct:92,  note:'move value fast'}
];
const COND = {NM:1.00, LP:0.85, MP:0.70, HP:0.55, DMG:0.35};
const CONDNAME = {NM:'Near Mint', LP:'Lightly Played', MP:'Moderately Played',
                  HP:'Heavily Played', DMG:'Damaged'};
const MARGIN_GUARD = 1.15;   /* never list below cost x 1.15 */
const FLOOR_NET    = 0.50;   /* below this net, route to a bulk lot */
const STORES_TIER  = {
  none : {fvf:0.1325, allow:250,  sub:0},
  basic: {fvf:0.1235, allow:1000, sub:27.95}
};

/* 4.37 -> 4.49, 12.10 -> 11.99 */
function psych99(x){
  let v = Math.round(x*2)/2 - 0.01;
  return v < 0.49 ? 0.49 : v;
}
function tierFor(market){
  for(const t of TIERS){ if(t.max === null || market < t.max) return t; }
  return TIERS[TIERS.length-1];
}
function priceCard(o){
  const tier  = tierFor(o.market);
  const base  = o.market * tier.pct / 100;
  const adj   = base * (COND[o.cond] !== undefined ? COND[o.cond] : 1);
  const guard = Math.max(adj, o.cost * MARGIN_GUARD);
  const ask   = psych99(guard);
  const gross = ask + o.ship;
  const fvf   = gross * o.fvf;
  const order = gross <= 10 ? 0.30 : 0.40;
  const post  = ask < 20 ? o.ese : o.parcel;
  const ins   = o.vol > o.allow ? 0.35 : 0;
  const net   = gross - fvf - order - post - ins - o.cost;
  return {tier, base, adj, guard, ask, gross, fvf, order, post, ins, net,
          guarded: guard > adj + 1e-9};
}

const calcEls = ['c-market','c-cond','c-cost','c-ship','c-store','c-vol']
                  .map(id => document.getElementById(id));
if (calcEls.every(Boolean)) {
  const [mkI, cdI, coI, shI, stI, vlI] = calcEls;
  const num = (el, dflt) => { const v = parseFloat(el.value); return isFinite(v) && v >= 0 ? v : dflt; };

  function renderCalc(){
    const st = STORES_TIER[stI.value] || STORES_TIER.none;
    const r  = priceCard({
      market: num(mkI, 0), cond: cdI.value, cost: num(coI, 0),
      ship:   num(shI, 0), vol: num(vlI, 0),
      fvf: st.fvf, allow: st.allow, ese: 0.85, parcel: 4.50
    });
    const m = n => '$' + n.toFixed(2);
    document.getElementById('o-ask').textContent = m(r.ask);
    document.getElementById('o-fees').textContent = m(r.fvf + r.order + r.ins);
    const netEl = document.getElementById('o-net');
    netEl.textContent = m(r.net);
    netEl.style.color = r.net >= FLOOR_NET ? 'var(--buy)' : (r.net > 0 ? 'var(--watch)' : 'var(--skip)');
    document.getElementById('o-tier').textContent = r.tier.pct + '%';

    const v = document.getElementById('o-verdict');
    if (r.net >= FLOOR_NET){
      v.className = 'verdict v-list';
      v.innerHTML = '<b>List it individually</b>Nets ' + m(r.net) +
        ', clearing the ' + m(FLOOR_NET) + ' floor.';
    } else if (r.net > 0){
      v.className = 'verdict v-lot';
      v.innerHTML = '<b>Send it to a bulk lot</b>Only nets ' + m(r.net) +
        ' &mdash; under the ' + m(FLOOR_NET) + ' floor. Technically positive, but not worth the handling.';
    } else {
      v.className = 'verdict v-bad';
      v.innerHTML = '<b>Bulk lot &mdash; this one loses money</b>Nets ' + m(r.net) +
        '. Listing it individually costs you more than it returns.';
    }

    const ln = (k, val, neg) => '<div class="ln' + (neg ? ' neg' : '') + '"><span>' + k +
                                '</span><span>' + (neg ? '&minus;' : '') + m(Math.abs(val)) + '</span></div>';
    let rows = '';
    rows += ln('Market price (Near Mint)', num(mkI,0));
    rows += ln('&times; tier ' + r.tier.pct + '%', r.base);
    rows += ln('&times; ' + (CONDNAME[cdI.value]||cdI.value) + ' ' + COND[cdI.value].toFixed(2) + '&times;', r.adj);
    if (r.guarded) rows += ln('&uarr; margin guard (cost &times; 1.15)', r.guard);
    rows += ln('Ask, rounded to .99', r.ask);
    rows += ln('+ buyer-paid shipping', num(shI,0));
    rows += ln('Final value fee', r.fvf, true);
    rows += ln('Per-order fee', r.order, true);
    rows += ln('Postage (' + (r.ask < 20 ? 'eBay Standard Envelope' : 'parcel') + ')', r.post, true);
    rows += ln(r.ins ? 'Insertion fee (past your free ' + STORES_TIER[stI.value].allow + ')'
                     : 'Insertion fee (within free allowance)', r.ins, r.ins > 0);
    rows += ln('Your cost basis', num(coI,0), true);
    rows += ln('Net in your pocket', r.net);
    document.getElementById('o-brk').innerHTML = rows;
  }
  calcEls.forEach(el => { el.addEventListener('input', renderCalc); el.addEventListener('change', renderCalc); });
  renderCalc();

  /* tier table rendered from the same constants, so they cannot drift */
  const tb2 = document.getElementById('tierbody');
  if (tb2) tb2.innerHTML = TIERS.map((t,i) => {
    /* tiers are exclusive of their max, so show the real top of each band */
    const lo = (i === 0 ? 0 : TIERS[i-1].max).toFixed(2);
    const band = t.max === null ? '$' + lo + ' and up'
                                : '$' + lo + ' &ndash; $' + (t.max - 0.01).toFixed(2);
    return '<tr><td class="mono">' + band + '</td><td class="num mono"><b>' + t.pct +
           '%</b></td><td>' + (t.note || '&mdash;') + '</td></tr>';
  }).join('');
  const cb = document.getElementById('condbody');
  if (cb) cb.innerHTML = Object.keys(COND).map(k =>
    '<tr><td><b>' + k + '</b> &middot; ' + CONDNAME[k] + '</td><td class="num mono">' +
    COND[k].toFixed(2) + '&times;</td></tr>').join('');
}

/* ---------------- sell: which channel ----------------
   TCGplayer verified 2026: 10.75% commission (L1-L4, up from 10.25% on
   10 Feb 2026) + 2.5% + $0.30 transaction fee, charged PER ORDER.
   The per-order part is the whole story - see SPEC.md 2.               */
const TCG = {commission:0.1075, txnPct:0.025, txnFlat:0.30};

function tcgNet(o){
  const commission = o.ask * TCG.commission;
  const txnPct     = o.ask * TCG.txnPct;
  const txnFlat    = TCG.txnFlat / o.orderSize;   /* amortised across the order */
  const ship       = o.shipPerOrder / o.orderSize;
  return {commission, txnPct, txnFlat, ship,
          net: o.ask - commission - txnPct - txnFlat - ship - o.cost};
}

/* eBay with shipping passed through to the buyer at cost, which is what a real
   seller does. A flat buyer-paid $1 would unfairly penalise eBay on a $100 card
   that actually ships as a $4.50 parcel.
   Top level so the channel tab and the card desk share one implementation. */
function ebaySide(market, cond, cost, vol){
  const st = STORES_TIER.none;
  const r = priceCard({market, cond, cost, ship: 0, vol,
                       fvf: st.fvf, allow: st.allow, ese: 0.85, parcel: 4.50});
  const gross = r.ask + r.post;
  const fvf   = gross * st.fvf;
  const order = gross <= 10 ? 0.30 : 0.40;
  const net   = gross - fvf - order - r.post - r.ins - cost;
  return {...r, gross, fvf, order, net};
}

/* one card -> the better channel and its net */
function routeCard(market, cond, cost, vol, orderSize, shipPerOrder){
  const e = ebaySide(market, cond, cost, vol);
  const t = tcgNet({ask: e.ask, cost, orderSize, shipPerOrder});
  const best = Math.max(e.net, t.net);
  const decision = best < FLOOR_NET ? 'lot' : (t.net >= e.net ? 'tcgplayer' : 'ebay');
  return {ask: e.ask, tier: e.tier, ebay: e, tcg: t, best, decision};
}

const chEls = ['h-market','h-cond','h-cost','h-order','h-ship','h-vol']
                .map(id => document.getElementById(id));
if (chEls.every(Boolean)) {
  const [mk, cd, co, or_, sh, vl] = chEls;
  const n = (el, d) => { const v = parseFloat(el.value); return isFinite(v) && v >= 0 ? v : d; };
  /* negatives read as -$0.01, never $-0.01 */
  const m = x => (x < 0 ? '-$' : '$') + Math.abs(x).toFixed(2);

  function renderChannels(){
    const market = n(mk, 0), cost = n(co, 0);
    const orderSize = Math.max(1, Math.round(n(or_, 1))), shipPerOrder = n(sh, 1.00), vol = n(vl, 0);

    /* same ask on both sides - identical rule, identical market price.
       any difference in net is purely the fee structures.                */
    const e = ebaySide(market, cd.value, cost, vol);
    const t = tcgNet({ask: e.ask, cost, orderSize, shipPerOrder});

    document.getElementById('h-ask').textContent = m(e.ask);
    document.getElementById('h-tier').textContent = e.tier.pct + '%';

    const paint = (pfx, net, lines, win) => {
      const box = document.getElementById(pfx + '-box');
      box.className = 'chan' + (win ? ' win' : '');
      box.querySelector('.big').textContent = m(net);
      box.querySelector('.big').style.color = net >= FLOOR_NET ? 'var(--buy)'
                                            : (net > 0 ? 'var(--watch)' : 'var(--skip)');
      const badge = box.querySelector('.badge');
      badge.textContent = win ? 'Best net' : '';
      badge.style.display = win ? '' : 'none';   /* an empty badge still draws a pill */
      box.querySelector('.lines').innerHTML = lines.map(l =>
        '<div class="li' + (l[2] ? ' tot' : '') + '"><span>' + l[0] +
        '</span><span>' + l[1] + '</span></div>').join('');
    };

    const eWin = e.net >= t.net;
    paint('e', e.net, [
      ['Ask + ' + m(e.post) + ' shipping, buyer pays', m(e.gross)],
      ['Final value fee 13.25%', '&minus;' + m(e.fvf)],
      ['Order fee &mdash; this card IS the order', '&minus;' + m(e.order)],
      ['Postage', '&minus;' + m(e.post)],
      ['Insertion', e.ins ? '&minus;' + m(e.ins) : m(0)],
      ['Cost basis', '&minus;' + m(cost)],
      ['Net', m(e.net), true]
    ], eWin);
    paint('t', t.net, [
      ['Ask', m(e.ask)],
      ['Commission 10.75%', '&minus;' + m(t.commission)],
      ['Transaction 2.5%', '&minus;' + m(t.txnPct)],
      ['$0.30 order fee &divide; ' + orderSize, '&minus;' + m(t.txnFlat)],
      ['Postage &divide; ' + orderSize, '&minus;' + m(t.ship)],
      ['Cost basis', '&minus;' + m(cost)],
      ['Net', m(t.net), true]
    ], !eWin);

    const best = Math.max(e.net, t.net);
    const v = document.getElementById('h-verdict');
    const diff = Math.abs(e.net - t.net);
    if (best < FLOOR_NET){
      v.className = 'verdict v-lot';
      v.innerHTML = '<b>Bulk lot &mdash; neither channel clears the floor</b>Best is ' +
        m(best) + ', under ' + m(FLOOR_NET) + '. This is the card the lot builder exists for.';
    } else if (eWin){
      v.className = 'verdict v-list';
      v.innerHTML = '<b>List it on eBay</b>Nets ' + m(e.net) + ', which is ' + m(diff) +
        ' better than TCGplayer at an order size of ' + orderSize + '.';
    } else {
      v.className = 'verdict v-list';
      v.innerHTML = '<b>List it on TCGplayer</b>Nets ' + m(t.net) + ', which is ' + m(diff) +
        ' better than eBay &mdash; because the fixed fees split across ' + orderSize + ' cards instead of landing on one.';
    }

    /* The useful question is not "at what price" but "at what basket size".
       Order size is the variable that actually moves, so scan that.        */
    let flip = null;
    for (let k = 1; k <= 40; k++){
      if (tcgNet({ask: e.ask, cost, orderSize: k, shipPerOrder}).net >= e.net){ flip = k; break; }
    }
    const cross = document.getElementById('h-cross');
    if (flip === null){
      cross.className = 'note warn';
      cross.innerHTML = '<b>eBay wins at any realistic basket size for this card.</b> Even a 40-card ' +
        'TCGplayer order does not catch it &mdash; send this one to eBay.';
    } else if (flip === 1){
      cross.className = 'note';
      cross.innerHTML = '<b>TCGplayer wins even on a single-card order.</b> There is no basket size ' +
        'at which eBay is the better net for this card.';
    } else {
      cross.className = 'note';
      cross.innerHTML = 'TCGplayer overtakes eBay once an order carries <b>' + flip + ' cards or more</b>. ' +
        'Below that, eBay nets more. Your typical basket is the number that decides it &mdash; ' +
        'reconciliation will replace this guess with your real average.';
    }
  }
  chEls.forEach(el => { el.addEventListener('input', renderChannels); el.addEventListener('change', renderChannels); });
  renderChannels();
}

/* ================= CARD DESK =================
   One screen. Search a card by name, tap it, done. No set codes to look up,
   no modifiers to learn, no staging step. Shorthand still works for anyone
   who knows it, but nothing requires it.
   Stock lives in this browser; the real app is local (see RUNBOOK.md).   */
const CATALOG = __CARDS__;
const BUILT = __BUILT__;
const CD_KEY = 'carddesk.v1';

/* How old is this snapshot? Every price on the page is frozen at build time --
   a published page is blocked from reaching tcgcsv.com, so it cannot refresh
   itself. Say so rather than let a stale number look live. */
function priceAgeDays(){
  const d = Math.floor((Date.now() - Date.parse(BUILT + 'T00:00:00')) / 86400000);
  return isFinite(d) && d >= 0 ? d : 0;
}
function stampPriceAge(){
  const days = priceAgeDays();
  const label = days === 0 ? 'today' : days === 1 ? 'yesterday' : days + ' days ago';
  const cls = days <= 2 ? 'fresh' : days <= 7 ? 'aging' : 'stale';
  document.querySelectorAll('[data-priceage]').forEach(el => {
    el.className = 'agechip ' + cls;
    el.innerHTML = '<b>TCGplayer</b> prices, pulled ' + label;
  });
  document.querySelectorAll('[data-agedays]').forEach(el => { el.textContent = days; });
}

/* remote images are blocked by the published page's CSP -- they work in the
   local preview and simply vanish online, rather than leaving broken icons */
function imgFallback(){
  document.querySelectorAll('img[data-thumb]').forEach(im => {
    if (im.dataset.wired) return;
    im.dataset.wired = '1';
    im.addEventListener('error', () => { im.closest('.thumbwrap')?.classList.add('nothumb'); });
  });
}
const CD_CONDS = ['NM', 'LP', 'MP', 'HP', 'DMG'];
const CD_CONDNAME = {NM:'Near Mint', LP:'Lightly Played', MP:'Moderately Played',
                     HP:'Heavily Played', DMG:'Damaged'};
const CD_PRINT = {f:'Holofoil', foil:'Holofoil', holo:'Holofoil', h:'Holofoil',
                  rh:'Reverse Holofoil', rev:'Reverse Holofoil',
                  n:'Normal', normal:'Normal'};
const CD_COND_TOK = {nm:'NM', m:'NM', mint:'NM', lp:'LP', mp:'MP', hp:'HP',
                     dmg:'DMG', d:'DMG', poor:'DMG'};

/* Thumbnails ride inside the page as data URIs -- the published page's CSP
   blocks remote images, so a CDN URL would silently show nothing. A handful of
   products have no image on the CDN at all; those return null and the slot is
   dropped rather than left as a broken box. */
const THUMBS = __THUMBS__;
const cdSetOf = c => CATALOG.sets[c.s] || {n:'', a:'', g:''};
const cdThumb = c => THUMBS[c.i] || null;
const cdM = n => '$' + n.toFixed(2);

/* ---- search: a name, or the old shorthand, in one box ---- */
function cdShorthand(q){
  const toks = q.trim().split(/\s+/).filter(Boolean);
  if (toks.length < 2) return null;
  const out = {set:toks[0], number:null, printing:null, condition:'NM', qty:1};
  let sawNumber = false;
  for (const tok of toks.slice(1)){
    const low = tok.toLowerCase();
    if (low[0] === '*' && CD_PRINT[low.slice(1)]){ out.printing = CD_PRINT[low.slice(1)]; continue; }
    let m = low.match(/^(?:x(\d{1,4})|(\d{1,4})x)$/);
    if (m){ out.qty = +(m[1] || m[2]); continue; }
    if (CD_COND_TOK[low]){ out.condition = CD_COND_TOK[low]; continue; }
    if (!sawNumber && /^\d{1,4}(\/\d{1,4})?[a-z]?$/.test(low)){ out.number = tok; sawNumber = true; continue; }
  }
  return out.number ? out : null;
}

function cdVariants(n){
  const head = String(n).split('/')[0];
  return [...new Set([String(n), head, head.replace(/^0+/, '') || '0', head.padStart(3,'0')])];
}

function cdSearch(q){
  q = (q || '').trim();
  if (q.length < 2) return {mode:'idle', hits:[]};

  const sh = cdShorthand(q);
  if (sh){
    const code = sh.set.toLowerCase();
    const hits = [];
    CATALOG.cards.forEach((c, i) => {
      const s = cdSetOf(c);
      if ((s.a || '').toLowerCase() !== code && !s.n.toLowerCase().startsWith(code)) return;
      const num = c['#'] || '';
      const want = cdVariants(sh.number);
      if (want.includes(num) || want.includes(num.split('/')[0])) hits.push(i);
    });
    if (hits.length) return {mode:'code', hits, pre: sh};
    return {mode:'code-miss', hits:[], pre: sh};
  }

  const t = q.toLowerCase();
  const starts = [], contains = [];
  for (let i = 0; i < CATALOG.cards.length; i++){
    const n = CATALOG.cards[i].n.toLowerCase();
    const at = n.indexOf(t);
    if (at === 0) starts.push(i);
    else if (at > 0) contains.push(i);
    if (starts.length + contains.length > 400) break;
  }
  return {mode:'name', hits: starts.concat(contains).slice(0, 40),
          more: Math.max(0, starts.length + contains.length - 40)};
}

/* ---- storage ---- */
let CD_STOCK = [];
let CD_PERSISTS = false;

function cdLoad(){
  try {
    const raw = localStorage.getItem(CD_KEY);
    CD_PERSISTS = true;
    CD_STOCK = raw ? (JSON.parse(raw).cards || []) : [];
  } catch(e){ CD_PERSISTS = false; CD_STOCK = []; }
}
function cdSave(){
  if (!CD_PERSISTS) return;
  try { localStorage.setItem(CD_KEY, JSON.stringify({cards: CD_STOCK, at: Date.now()})); }
  catch(e){ CD_PERSISTS = false; cdStatus(); }
}
function cdStatus(){
  const el = document.getElementById('cd-status');
  if (!el) return;
  el.className = 'note' + (CD_PERSISTS ? '' : ' warn');
  el.innerHTML = CD_PERSISTS
    ? 'Stock is saved in this browser and will still be here next time. It is <b>separate from the desktop app</b> \u2014 export the CSV to move it across.'
    : '<b>This browser is blocking storage.</b> Anything you add here disappears when the tab closes \u2014 export before you go.';
}

/* ---- pricing, using the settings on "Where to sell it" ---- */
function cdSettings(){
  const g = (id, d) => { const el = document.getElementById(id);
    const v = el ? parseFloat(el.value) : NaN; return isFinite(v) && v >= 0 ? v : d; };
  return {vol: g('h-vol', 300), orderSize: Math.max(1, Math.round(g('h-order', 12))),
          ship: g('h-ship', 1.00)};
}
function cdPrice(market, cond){
  const s = cdSettings();
  return routeCard(market, cond, 0, s.vol, s.orderSize, s.ship);
}
const cdBadge = d => d === 'tcgplayer' ? '<span class="pill buy">TCGplayer</span>'
                   : d === 'ebay'      ? '<span class="pill flag">eBay</span>'
                                       : '<span class="pill watch">Bulk lot</span>';

/* ---- results ---- */
function cdRenderResults(){
  const box = document.getElementById('cd-results');
  const note = document.getElementById('cd-resnote');
  if (!box) return;
  const q = document.getElementById('cd-q').value;
  const r = cdSearch(q);

  if (r.mode === 'idle'){
    box.innerHTML = '';
    note.innerHTML = 'Start typing a card name \u2014 <b>umbreon</b>, <b>charizard</b>, <b>pikachu</b>.';
    return;
  }
  if (!r.hits.length){
    box.innerHTML = '';
    note.innerHTML = r.mode === 'code-miss'
      ? 'No card <b>#' + esc(r.pre.number) + '</b> in a set called <b>' + esc(r.pre.set) + '</b>. Try the card\u2019s name instead.'
      : 'Nothing matches <b>' + esc(q.trim()) + '</b>. Only the ' +
        CATALOG.sets.length + ' sets listed below are built into this page.';
    return;
  }

  note.innerHTML = r.mode === 'code'
    ? 'Matched by set and number. Tap a price to add it.'
    : r.hits.length + ' match' + (r.hits.length === 1 ? '' : 'es') +
      (r.more ? ' (showing the first 40 \u2014 keep typing to narrow it)' : '') +
      ' \u2014 tap a price to add it.';

  box.innerHTML = r.hits.map(i => {
    const c = CATALOG.cards[i], s = cdSetOf(c);
    const chips = Object.keys(c.p).map(pr =>
      '<button class="printchip" data-add="' + i + '" data-pr="' + esc(pr) + '">' +
        '<span class="pn">' + esc(pr.replace('Reverse Holofoil','Reverse').replace('Holofoil','Foil')) +
        '</span><span class="pp">' + cdM(c.p[pr]) + '</span></button>').join('');
    const th = cdThumb(c);
    return '<div class="hit">' +
      (th ? '<span class="thumbwrap"><img loading="lazy" data-thumb src="' + th + '" alt=""></span>'
          : '<span class="thumbwrap noart" aria-hidden="true">?</span>') +
      '<div class="hitmain"><div class="hitname">' + esc(c.n) + '</div>' +
      '<div class="hitmeta">' + esc(s.n) + ' \u00b7 #' + esc(c['#']) +
        (c.r ? ' \u00b7 ' + esc(c.r) : '') + '</div>' +
      '<div class="chips">' + chips + '</div></div></div>';
  }).join('');

  box.querySelectorAll('[data-add]').forEach(b => b.addEventListener('click', () => {
    cdAdd(+b.dataset.add, b.dataset.pr, r.pre);
  }));
  imgFallback();
}

/* ---- add / edit stock ---- */
function cdAdd(idx, printing, pre){
  const cond = (pre && pre.condition) || 'NM';
  const qty  = (pre && pre.qty) || 1;
  const hit = CD_STOCK.find(e => e.i === idx && e.pr === printing && e.c === cond);
  if (hit) hit.q += qty;
  else CD_STOCK.unshift({i: idx, pr: printing, c: cond, q: qty});
  cdSave(); cdRenderStock();

  const c = CATALOG.cards[idx];
  const msg = document.getElementById('cd-added');
  msg.textContent = (hit ? 'Another ' : 'Added ') + c.n + (qty > 1 ? ' x' + qty : '');
  msg.classList.add('show');
  clearTimeout(cdAdd._t);
  cdAdd._t = setTimeout(() => msg.classList.remove('show'), 2200);
}

function cdRenderStock(){
  const tb = document.getElementById('cd-stock');
  if (!tb) return;
  let mkt = 0, net = 0, qty = 0;
  const split = {tcgplayer:0, ebay:0, lot:0};

  tb.innerHTML = CD_STOCK.map((e, i) => {
    const c = CATALOG.cards[e.i];
    if (!c) return '';
    const s = cdSetOf(c);
    const market = c.p[e.pr];
    const p = cdPrice(market, e.c);
    mkt += market * e.q; net += p.best * e.q; qty += e.q;
    split[p.decision] += e.q;
    const conds = CD_CONDS.map(k =>
      '<option value="' + k + '"' + (k === e.c ? ' selected' : '') + '>' + k + '</option>').join('');
    return '<tr>' +
      '<td><div class="srow">' +
        (cdThumb(c) ? '<span class="thumbwrap sm"><img loading="lazy" data-thumb src="' +
          cdThumb(c) + '" alt=""></span>' : '') +
        '<div><b>' + esc(c.n) + '</b><br><span class="setname">' + esc(s.a || s.n) +
        ' \u00b7 #' + esc(c['#']) + ' \u00b7 ' + esc(e.pr) + '</span></div></div></td>' +
      '<td><div class="qty"><button class="qbtn" data-dec="' + i + '">\u2212</button>' +
        '<span class="mono">' + e.q + '</span>' +
        '<button class="qbtn" data-inc="' + i + '">+</button></div></td>' +
      '<td><select class="condsel" data-cond="' + i + '">' + conds + '</select></td>' +
      '<td class="num mono">' + cdM(market) + '</td>' +
      '<td class="num mono">' + cdM(p.ask) + '</td>' +
      '<td class="num mono">' + cdM(p.best) + '</td>' +
      '<td>' + cdBadge(p.decision) + '</td>' +
      '<td class="num"><button class="linkbtn" data-rm="' + i + '">remove</button></td></tr>';
  }).join('');

  document.getElementById('cd-empty').hidden = CD_STOCK.length > 0;
  document.getElementById('cd-s-lines').textContent = CD_STOCK.length;
  document.getElementById('cd-s-qty').textContent = qty;
  document.getElementById('cd-s-mkt').textContent = cdM(mkt);
  document.getElementById('cd-s-net').textContent = cdM(net);
  document.getElementById('cd-s-split').textContent =
    split.tcgplayer + ' TCGplayer \u00b7 ' + split.ebay + ' eBay \u00b7 ' + split.lot + ' bulk lot';
  document.getElementById('cd-export').disabled = !CD_STOCK.length;
  document.getElementById('cd-wipe').disabled = !CD_STOCK.length;

  tb.querySelectorAll('[data-inc]').forEach(b => b.onclick = () => {
    CD_STOCK[+b.dataset.inc].q++; cdSave(); cdRenderStock(); });
  tb.querySelectorAll('[data-dec]').forEach(b => b.onclick = () => {
    const e = CD_STOCK[+b.dataset.dec];
    if (--e.q < 1) CD_STOCK.splice(+b.dataset.dec, 1);
    cdSave(); cdRenderStock(); });
  tb.querySelectorAll('[data-rm]').forEach(b => b.onclick = () => {
    CD_STOCK.splice(+b.dataset.rm, 1); cdSave(); cdRenderStock(); });
  tb.querySelectorAll('[data-cond]').forEach(sel => sel.onchange = () => {
    CD_STOCK[+sel.dataset.cond].c = sel.value; cdSave(); cdRenderStock(); });
  imgFallback();
}

function cdCsv(){
  const rows = [['sku','set','set_code','card','number','rarity','printing',
                 'condition','qty','market_usd','ask_usd','best_net_usd','route']];
  CD_STOCK.forEach((e, i) => {
    const c = CATALOG.cards[e.i]; if (!c) return;
    const s = cdSetOf(c), market = c.p[e.pr], p = cdPrice(market, e.c);
    rows.push(['CD-W' + (i + 1), s.n, s.a || '', c.n, c['#'], c.r || '', e.pr, e.c,
               e.q, market.toFixed(2), p.ask.toFixed(2), p.best.toFixed(2), p.decision]);
  });
  return rows.map(r => r.map(v => {
    const t = String(v);
    return /[",\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t;
  }).join(',')).join('\n');
}

/* ---- wiring ---- */
if (document.getElementById('cd-q')) {
  cdLoad(); cdStatus();

  const q = document.getElementById('cd-q');
  let qt = null;
  q.addEventListener('input', () => { clearTimeout(qt); qt = setTimeout(cdRenderResults, 110); });
  document.getElementById('cd-clearq').addEventListener('click', () => {
    q.value = ''; cdRenderResults(); q.focus();
  });

  document.getElementById('cd-wipe').addEventListener('click', () => {
    if (!confirm('Remove everything saved in this browser?')) return;
    CD_STOCK = []; cdSave(); cdRenderStock();
  });

  document.getElementById('cd-export').addEventListener('click', async () => {
    const btn = document.getElementById('cd-export');
    const msg = document.getElementById('cd-exmsg');
    btn.disabled = true; msg.textContent = 'Preparing\u2026';
    const csv = cdCsv();
    const stamp = new Date().toISOString().slice(0, 10);
    try {
      const dl = await window.claude.use('downloads');
      if (!dl) throw {code: 'unavailable'};
      try {
        await dl.save({filename: 'card-desk-' + stamp + '.csv', data: csv});
        msg.textContent = 'Saved.';
      } catch (err) {
        if (err && err.code === 'extension_not_enabled'){
          await dl.save({filename: 'card-desk-' + stamp + '.csv.txt', data: csv});
          msg.textContent = 'Saved as .txt \u2014 rename it to .csv.';
        } else if (err && err.code === 'declined'){ msg.textContent = 'Cancelled.'; }
        else { throw err; }
      }
    } catch (err) {
      msg.textContent = 'Downloads are not available here \u2014 copy the text below.';
      const ta = document.getElementById('cd-fallback');
      ta.hidden = false; ta.value = csv; ta.select();
    } finally {
      btn.disabled = false;
      setTimeout(() => { if (msg.textContent === 'Saved.') msg.textContent = ''; }, 3500);
    }
  });

  ['h-vol','h-order','h-ship'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', cdRenderStock);
  });

  const setsBody = document.getElementById('cd-sets');
  if (setsBody && CATALOG.sets){
    setsBody.innerHTML = CATALOG.sets.map(s =>
      '<tr><td><b>' + esc(s.a || '\u2014') + '</b></td><td>' + esc(s.n) +
      '</td><td>' + esc(s.g) + '</td><td class="mono">' + esc(s.d) + '</td></tr>').join('');
    document.getElementById('cd-setcount').textContent =
      CATALOG.sets.length + ' sets \u00b7 ' + CATALOG.cards.length.toLocaleString() + ' cards';
  }

  cdRenderResults(); cdRenderStock();
}

/* ================= SPORTS SINGLES: COMC vs eBAY =================
   Sports has no TCGplayer, so a single cannot ride in a shared cart the way a
   Pokemon single does -- it carries eBay's fixed costs alone. COMC is the
   nearest equivalent: ship a box once, they photograph, list and fulfil.
   Fees verified 15 Aug 2026: 5% transaction, 10% cash-out, ~$0.50-1 to submit. */
const SPF = {fvf:0.1325, orderLo:0.30, orderHi:0.40, insert:0.35, post:0.85,
             comcTxn:0.05, comcCash:0.10};

function ebaySingle(p, cost, buyerPays, insertion){
  const shipIn = buyerPays ? SPF.post : 0;
  const gross = p + shipIn;
  let fee = gross * SPF.fvf + (gross <= 10 ? SPF.orderLo : SPF.orderHi);
  if (insertion) fee += SPF.insert;
  return gross - fee - SPF.post - cost;
}
function comcSingle(p, cost, sub, cashOut){
  let pr = p * (1 - SPF.comcTxn) - sub;
  if (cashOut) pr *= (1 - SPF.comcCash);
  return pr - cost;
}
/* price at which the two paths cross, for the current settings */
function comcCrossover(cost, buyerPays, insertion, sub, cashOut){
  let lo = 0, hi = 400;
  for (let i = 0; i < 60; i++){
    const mid = (lo + hi) / 2;
    if (comcSingle(mid, cost, sub, cashOut) > ebaySingle(mid, cost, buyerPays, insertion))
      lo = mid; else hi = mid;
  }
  return hi;
}

const spEls = ['sp-price','sp-cost','sp-qty','sp-sub','sp-min'].map(i => document.getElementById(i));
if (spEls.every(Boolean)) {
  const [pI, cI, qI, subI, minI] = spEls;
  const buyerI = document.getElementById('sp-buyer');
  const cashI  = document.getElementById('sp-cash');
  const insI   = document.getElementById('sp-ins');
  const n = (el, d) => { const v = parseFloat(el.value); return isFinite(v) && v >= 0 ? v : d; };
  const m = v => (v < 0 ? '\u2212$' : '$') + Math.abs(v).toFixed(2);

  function renderSports(){
    const p = n(pI, 0), cost = n(cI, 0), qty = Math.max(1, Math.round(n(qI, 1)));
    const sub = n(subI, 0.75), mins = n(minI, 5);
    const buyerPays = buyerI.value === 'yes';
    const cashOut = cashI.value === 'cash';
    const insertion = insI.value === 'yes';

    const e = ebaySingle(p, cost, buyerPays, insertion);
    const c = comcSingle(p, cost, sub, cashOut);
    const hours = qty * mins / 60;
    const rate = hours > 0 ? (e * qty) / hours : 0;
    const cross = comcCrossover(cost, buyerPays, insertion, sub, cashOut);

    document.getElementById('sp-ebay').textContent = m(e);
    document.getElementById('sp-comc').textContent = m(c);
    document.getElementById('sp-ebay-all').textContent = m(e * qty);
    document.getElementById('sp-comc-all').textContent = m(c * qty);
    document.getElementById('sp-hours').textContent = hours.toFixed(1) + ' hr';
    document.getElementById('sp-rate').textContent = m(rate) + '/hr';
    for (const [id, v] of [['sp-ebay', e], ['sp-comc', c]])
      document.getElementById(id).style.color =
        v <= 0 ? 'var(--skip)' : (v < 1 ? 'var(--watch)' : 'var(--buy)');

    const v = document.getElementById('sp-verdict');
    if (e <= 0 && c <= 0){
      v.className = 'verdict v-bad';
      v.innerHTML = '<b>Do not list this card anywhere</b>Both routes lose money at ' +
        m(p) + '. This is bulk \u2014 dollar box, a throw-in, or sold by weight.';
    } else if (c > e){
      v.className = 'verdict v-list';
      v.innerHTML = '<b>COMC \u2014 ' + m(c) + ' vs ' + m(e) + ' on eBay</b>' +
        'And you ship once instead of ' + qty + ' times. eBay only overtakes COMC above ' +
        m(cross) + ' a card.';
    } else {
      v.className = 'verdict v-list';
      v.innerHTML = '<b>eBay \u2014 ' + m(e) + ' vs ' + m(c) + ' on COMC</b>' +
        'Above ' + m(cross) + ' a card eBay wins on fees. Worth the handling at this price.';
    }

    const lab = document.getElementById('sp-labour');
    if (rate < 15 && e > 0){
      lab.className = 'note warn';
      lab.innerHTML = '<b>The fees are not the problem here \u2014 the clock is.</b> Listing, ' +
        'packing and posting ' + qty + ' cards yourself is about <b>' + hours.toFixed(1) +
        ' hours</b> for ' + m(e * qty) + ', or <b>' + m(rate) + ' an hour</b>. ' +
        'COMC costs more in fees and takes all of that off you.';
    } else {
      lab.className = 'note';
      lab.innerHTML = '<b>' + hours.toFixed(1) + ' hours</b> of listing and posting for ' +
        m(e * qty) + ' \u2014 about <b>' + m(rate) + ' an hour</b> on the eBay route. ' +
        'COMC trades some of that margin for none of the work.';
    }
  }
  [...spEls, buyerI, cashI, insI].forEach(el => {
    el.addEventListener('input', renderSports); el.addEventListener('change', renderSports);
  });
  renderSports();
}

/* ---------------- sell: store break-even ---------------- */
const beVol = document.getElementById('be-vol'), beGross = document.getElementById('be-gross');
if (beVol && beGross) {
  function renderBE(){
    const N = Math.max(0, parseInt(beVol.value, 10) || 0);
    const G = Math.max(0, parseFloat(beGross.value) || 0);
    const none  = Math.max(0, N - 250)  * 0.35 + G * 0.1325;
    const basic = 27.95 + Math.max(0, N - 1000) * 0.35 + G * 0.1235;
    const diff  = none - basic;
    const m = n => '$' + n.toFixed(2);
    document.getElementById('be-none').textContent  = m(none);
    document.getElementById('be-basic').textContent = m(basic);
    const out = document.getElementById('be-out');
    if (diff > 0){
      out.className = 'verdict v-list';
      out.innerHTML = '<b>A Basic Store saves you ' + m(diff) + '/mo</b>At ' + N +
        ' listings and ' + m(G) + ' gross, the subscription pays for itself.';
    } else {
      out.className = 'verdict v-lot';
      out.innerHTML = '<b>Stay storeless &mdash; a Store would cost you ' + m(-diff) + '/mo extra</b>At ' +
        N + ' listings and ' + m(G) + ' gross, you are better off on the free 250.';
    }
  }
  [beVol, beGross].forEach(el => el.addEventListener('input', renderBE));
  renderBE();
}
