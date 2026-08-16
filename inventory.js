/* ==================== My inventory ====================
   Renders whatever export_inventory.py pulled out of the workbook. The
   spreadsheet is the record; this is a view of it, and it is deliberately
   read-only -- there is no editing here, because two places to change a card
   is how the two stop agreeing.

   INVENTORY and INV_SOURCE are written into the page by build_all.py.
   INV_SOURCE says which file it found: "local" means the full export off Mr.
   P's own machine, cost and notes included; "published" means the subset he
   chose to put on a public site, with the money stripped out. The difference
   is worth showing rather than hiding -- a blank cost column should be
   explained, not left looking like missing data.                            */

(function () {
  const host = document.getElementById('inv-rows');
  if (!host) return;

  const data = (typeof INVENTORY === 'object' && INVENTORY) || {};
  const cards = data.cards || [];
  const money = !!data.money;
  const totals = data.totals || {};
  const source = (typeof INV_SOURCE === 'string' && INV_SOURCE) || '';

  const countEl = document.getElementById('inv-count');
  const tilesEl = document.getElementById('inv-tiles');
  const noteEl = document.getElementById('inv-note');
  const qEl = document.getElementById('inv-q');

  let filter = 'all';
  let sport = 'all';
  let term = '';

  const esc = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
  const cash = n => '$' + (Number(n) || 0).toFixed(2);

  /* ---- the empty case is a set of instructions, not a blank page ---- */
  if (!cards.length) {
    if (countEl) countEl.textContent = '';
    if (tilesEl) tilesEl.hidden = true;
    host.innerHTML =
      '<div class="note"><b>Nothing exported yet.</b> This tab shows what is in '
      + '<span class="mono">Card Run HQ - Master.xlsx</span>, but it only sees it '
      + 'once the workbook has been read out to a file the page can load:'
      + '<br><br><span class="mono">python export_inventory.py</span>'
      + '<br><span class="mono">python build_all.py . card-run-hq.html</span>'
      + '<br><br>Do that again whenever the workbook changes &mdash; the page is '
      + 'built once and does not go back to the spreadsheet on its own.</div>';
    return;
  }

  /* ---- the numbers along the top ---- */
  if (tilesEl) {
    const tile = (k, v) => '<div><span class="k">' + k + '</span>'
                         + '<span class="v">' + v + '</span></div>';
    let html = tile('Cards held', totals.cards != null ? totals.cards : '—');
    if (money) html += tile('At cost', cash(totals.cost));
    html += tile('At market', cash(totals.market));
    if (money && totals.market != null && totals.cost != null) {
      html += tile('Unrealised', cash(totals.market - totals.cost));
    }
    html += tile('Ready to list', totals.unlisted || 0);
    if (totals.listed) html += tile('Listed now', totals.listed);
    if (totals.sold) html += tile('Sold', totals.sold);
    if (money && totals.made) html += tile('Made on sales', cash(totals.made));
    if (totals.review) html += tile('Held for review', totals.review);
    tilesEl.innerHTML = html;
  }

  if (countEl) {
    countEl.textContent = cards.length + (cards.length === 1 ? ' row' : ' rows');
  }

  function status(card) {
    const s = card.status || '';
    const cls = s === 'Review' ? 'watch' : s === 'Sold' ? 'lot'
              : s === 'Listed' ? 'buy' : '';
    return '<span class="pill ' + cls + '">' + esc(s || '—') + '</span>';
  }

  function row(card) {
    const pic = (card.photos && card.photos[0])
      ? '<img class="invshot" src="' + esc(card.photos[0]) + '" alt="" loading="lazy">'
      : '<div class="invshot noshot">no photo</div>';

    const bits = [card.year, card.brand, card.insert, card.parallel]
      .filter(Boolean).join(' ');
    const badges = ['rc', 'auto', 'relic']
      .filter(k => String(card[k]).toLowerCase() === 'yes')
      .map(k => '<span class="pill">' + k.toUpperCase() + '</span>').join(' ');

    let cells =
      '<td>' + pic + '</td>'
      + '<td><b>' + esc(card.name || '—') + '</b>'
      + (card.num ? ' <span class="mono">#' + esc(card.num) + '</span>' : '')
      + (card.serial ? ' <span class="mono">/' + esc(card.serial) + '</span>' : '')
      + '<br><span class="setname">' + esc(bits || '—') + '</span>'
      + (badges ? '<br>' + badges : '') + '</td>'
      + '<td class="mono">' + esc(card.sku) + '</td>'
      + '<td>' + status(card) + '</td>'
      + '<td class="mono">' + esc(card.cond || '—') + '</td>'
      + '<td class="mono">' + (card.qty || 1) + '</td>';

    if (money) cells += '<td class="mono">' + (card.cost ? cash(card.cost) : '—') + '</td>';
    cells += '<td class="mono">' + (card.market ? cash(card.market) : '—') + '</td>'
           + '<td class="mono">' + (card.ask ? cash(card.ask) : '—') + '</td>';

    /* what actually happened to it: when it went up, when it went, and what
       it made. Blank until it is listed, which is most of them. */
    cells += '<td class="mono">' + esc(card.listed || '—') + '</td>'
           + '<td class="mono">' + esc(card.sold || '—') + '</td>';
    if (money) {
      cells += '<td class="mono">' + (card.soldfor ? cash(card.soldfor) : '—') + '</td>'
             + '<td class="mono">' + (card.profit ? cash(card.profit) : '—') + '</td>';
    }

    return '<tr>' + cells + '</tr>';
  }

  function matches(card) {
    if (filter !== 'all' && card.status !== filter) return false;
    if (sport !== 'all' && String(card.sport || '') !== sport) return false;
    if (!term) return true;
    return [card.name, card.brand, card.insert, card.parallel, card.num,
            card.sku, card.team, card.title]
      .some(v => String(v || '').toLowerCase().indexOf(term) >= 0);
  }

  function render() {
    const shown = cards.filter(matches);

    let head = '<tr><th>Photo</th><th>Card</th><th>SKU</th><th>Status</th>'
             + '<th>Cond</th><th>Qty</th>';
    if (money) head += '<th>Cost</th>';
    head += '<th>Market</th><th>Ask</th><th>Listed</th><th>Sold</th>';
    if (money) head += '<th>Sold for</th><th>Profit</th>';
    head += '</tr>';

    host.innerHTML = shown.length
      ? '<div class="scroll"><table><thead>' + head + '</thead><tbody>'
        + shown.map(row).join('') + '</tbody></table></div>'
      : '<p class="hint">Nothing matches that.</p>';

    if (noteEl) {
      const bits = [shown.length + ' of ' + cards.length + ' shown'];
      if (source === 'published') {
        bits.push('this page is showing the <b>published</b> export, so cost, '
                + 'notes and lot are deliberately not in it');
      } else if (source === 'local') {
        bits.push('this is the <b>full</b> export from your own machine');
      }
      noteEl.innerHTML = bits.join(' &middot; ');
    }
  }

  /* Sports only get their own row of buttons once there is more than one --
     a single "Football" button next to "Everything" is just noise. The
     workbook grows a read-only tab per sport at the same time; this is the
     same split, on the page. */
  const sports = Array.from(new Set(cards.map(c => String(c.sport || '').trim())
                                         .filter(Boolean))).sort();
  const sportHost = document.getElementById('inv-sports');
  if (sportHost && sports.length > 1) {
    sportHost.hidden = false;
    sportHost.innerHTML =
      '<span class="hint">Sport</span>'
      + ['all'].concat(sports).map(s =>
          '<button class="btn2' + (s === 'all' ? ' go' : '') + '" type="button" '
          + 'data-invs="' + esc(s) + '">' + esc(s === 'all' ? 'Every sport' : s)
          + '</button>').join('');
    sportHost.querySelectorAll('[data-invs]').forEach(b => {
      b.addEventListener('click', () => {
        sport = b.getAttribute('data-invs');
        sportHost.querySelectorAll('[data-invs]').forEach(x => x.classList.remove('go'));
        b.classList.add('go');
        render();
      });
    });
  }

  document.querySelectorAll('[data-invf]').forEach(b => {
    b.addEventListener('click', () => {
      filter = b.getAttribute('data-invf');
      document.querySelectorAll('[data-invf]').forEach(x => x.classList.remove('go'));
      b.classList.add('go');
      render();
    });
  });
  const first = document.querySelector('[data-invf="all"]');
  if (first) first.classList.add('go');

  if (qEl) {
    let t = null;
    qEl.addEventListener('input', () => {
      clearTimeout(t);
      t = setTimeout(() => { term = qEl.value.trim().toLowerCase(); render(); }, 110);
    });
  }
  const clear = document.getElementById('inv-clear');
  if (clear) clear.addEventListener('click', () => {
    qEl.value = ''; term = ''; render(); qEl.focus();
  });

  /* The command, on the clipboard. A page cannot run it -- browsers forbid
     a website executing anything on the machine reading it, which is exactly
     the rule you want everywhere else -- so the honest version is to hand it
     over ready to paste, and point at the .cmd file for one-click. */
  const copyBtn = document.getElementById('inv-copy');
  if (copyBtn) copyBtn.addEventListener('click', async () => {
    const cmd = 'python export_inventory.py\npython build_all.py . card-run-hq.html';
    const said = document.getElementById('inv-copied');
    const tell = t => { if (said) { said.textContent = t; setTimeout(() => { said.textContent = ''; }, 4000); } };
    try {
      await navigator.clipboard.writeText(cmd);
      tell('Copied — paste it into a terminal opened in your project folder.');
    } catch (e) {
      /* clipboard access needs a secure context; a page opened straight off
         disk is not one, so select the text instead of failing silently */
      const el = document.getElementById('inv-cmd');
      if (el && window.getSelection) {
        const r = document.createRange();
        r.selectNodeContents(el);
        const sel = window.getSelection();
        sel.removeAllRanges(); sel.addRange(r);
        tell('This browser will not let the page use the clipboard — the '
           + 'command is selected above, press Ctrl+C.');
      } else {
        tell('Could not copy. The command is written out above.');
      }
    }
  });

  render();
})();
