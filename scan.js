/* ==================== card desk: scan drop + auto crop ====================
   The scanner returns a whole sheet with the cards somewhere on it. This
   finds each card, straightens it, and hands back one image per card --
   in the browser, so a phone photo goes through the same path as a scan.

   It is a port of crop_scans.py: same two signals, same filters, same
   reading order, so a card cropped here and a card cropped by the script
   come out the same. That file carries the reasoning for each threshold.

   What it deliberately does NOT do is work out which card it is. This page
   is static and published; it has no way to recognise a Prizm parallel. The
   crops are the handover point -- you save them, and identification happens
   where there is something that can actually read a card.
   ========================================================================= */

const SC_WORK = 1000;        /* detection runs on a shrunk copy */
const SC_EDGE_PCT = 92;      /* top slice of the gradient that counts as edge */
const SC_COLOUR_TOL = 22;    /* how far off the lid colour a pixel must be */
const SC_ASPECT_MIN = 0.55, SC_ASPECT_MAX = 0.95;
const SC_MIN_AREA = 0.010, SC_MAX_AREA = 0.85;
const SC_MIN_RECT = 0.80;
const SC_THUMB_W = 190;

function scGrey(d, n){
  const g = new Float32Array(n);
  for (let i = 0; i < n; i++){
    g[i] = 0.299 * d[i*4] + 0.587 * d[i*4+1] + 0.114 * d[i*4+2];
  }
  return g;
}

/* separable 1-4-6-4-1, the kernel cv2.GaussianBlur(5,5) uses */
function scBlur(src, w, h){
  const k = [1, 4, 6, 4, 1], tmp = new Float32Array(w*h), out = new Float32Array(w*h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++){
    let s = 0, t = 0;
    for (let i = -2; i <= 2; i++){
      const xx = x + i; if (xx < 0 || xx >= w) continue;
      s += src[y*w+xx] * k[i+2]; t += k[i+2];
    }
    tmp[y*w+x] = s / t;
  }
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++){
    let s = 0, t = 0;
    for (let i = -2; i <= 2; i++){
      const yy = y + i; if (yy < 0 || yy >= h) continue;
      s += tmp[yy*w+x] * k[i+2]; t += k[i+2];
    }
    out[y*w+x] = s / t;
  }
  return out;
}

/* Scharr gradient magnitude. Taking a percentile of this, rather than a
   fixed Canny threshold, is what catches a white border on a white lid --
   that line is worth only a few levels of grey. */
function scGradient(g, w, h){
  const mag = new Float32Array(w*h);
  for (let y = 1; y < h-1; y++) for (let x = 1; x < w-1; x++){
    const i = y*w+x;
    const tl=g[i-w-1], t=g[i-w], tr=g[i-w+1];
    const l =g[i-1],             r=g[i+1];
    const bl=g[i+w-1], b=g[i+w], br=g[i+w+1];
    const gx = 3*tl + 10*l + 3*bl - 3*tr - 10*r - 3*br;
    const gy = 3*tl + 10*t + 3*tr - 3*bl - 10*b - 3*br;
    mag[i] = Math.sqrt(gx*gx + gy*gy);
  }
  return mag;
}

function scPercentile(v, pct){
  let max = 0;
  for (let i = 0; i < v.length; i++) if (v[i] > max) max = v[i];
  if (max <= 0) return 0;
  const bins = new Int32Array(1024);
  for (let i = 0; i < v.length; i++) bins[Math.min(1023, (v[i]/max*1023)|0)]++;
  const want = v.length * pct / 100;
  let seen = 0;
  for (let b = 0; b < 1024; b++){
    seen += bins[b];
    if (seen >= want) return b / 1023 * max;
  }
  return max;
}

/* the lid, sampled from a ring round the edge of the page. Median, so one
   card pushed to the edge cannot drag the estimate off white. */
function scBackground(d, w, h){
  const band = Math.max(2, Math.round(Math.min(w, h) * 0.02));
  const out = [];
  for (let c = 0; c < 3; c++){
    const hist = new Int32Array(256);
    let n = 0;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++){
      if (y < band || y >= h-band || x < band || x >= w-band){
        hist[d[(y*w+x)*4+c]]++; n++;
      }
    }
    let seen = 0, med = 0;
    for (let v = 0; v < 256; v++){ seen += hist[v]; if (seen >= n/2){ med = v; break; } }
    out.push(med);
  }
  return out;
}

/* sliding max then min = a close. Square rather than elliptical, which at
   this radius is close enough and far cheaper. */
function scMorph(mask, w, h, r, grow){
  const pass = (src, dst, horiz) => {
    const len = horiz ? w : h, other = horiz ? h : w;
    for (let o = 0; o < other; o++){
      for (let i = 0; i < len; i++){
        let v = grow ? 0 : 1;
        const lo = Math.max(0, i-r), hi = Math.min(len-1, i+r);
        for (let j = lo; j <= hi; j++){
          const s = horiz ? src[o*w+j] : src[j*w+o];
          if (grow ? s : !s){ v = grow ? 1 : 0; break; }
        }
        if (horiz) dst[o*w+i] = v; else dst[i*w+o] = v;
      }
    }
  };
  const a = new Uint8Array(w*h), b = new Uint8Array(w*h);
  pass(mask, a, true); pass(a, b, false);
  return b;
}
function scClose(m, w, h, r){ return scMorph(scMorph(m, w, h, r, true), w, h, r, false); }
function scOpen (m, w, h, r){ return scMorph(scMorph(m, w, h, r, false), w, h, r, true); }

/* every blob, as its pixel count and its outline */
function scBlobs(mask, w, h){
  const seen = new Uint8Array(w*h), out = [];
  const stack = new Int32Array(w*h);
  for (let s = 0; s < w*h; s++){
    if (!mask[s] || seen[s]) continue;
    let top = 0, area = 0;
    const pts = [];
    stack[top++] = s; seen[s] = 1;
    while (top > 0){
      const i = stack[--top], x = i % w, y = (i / w) | 0;
      area++;
      /* only the outline is needed for the hull, and keeping every pixel of
         a big blob is what would make this crawl on a 12 megapixel photo */
      if (x === 0 || y === 0 || x === w-1 || y === h-1 ||
          !mask[i-1] || !mask[i+1] || !mask[i-w] || !mask[i+w]) pts.push([x, y]);
      if (x > 0   && mask[i-1] && !seen[i-1]){ seen[i-1] = 1; stack[top++] = i-1; }
      if (x < w-1 && mask[i+1] && !seen[i+1]){ seen[i+1] = 1; stack[top++] = i+1; }
      if (y > 0   && mask[i-w] && !seen[i-w]){ seen[i-w] = 1; stack[top++] = i-w; }
      if (y < h-1 && mask[i+w] && !seen[i+w]){ seen[i+w] = 1; stack[top++] = i+w; }
    }
    if (area > 200) out.push({ area: area, pts: pts });
  }
  return out;
}

/* Andrew's monotone chain */
function scHull(pts){
  const p = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (p.length < 3) return p;
  const cross = (o, a, b) => (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0]);
  const lo = [];
  for (const q of p){
    while (lo.length >= 2 && cross(lo[lo.length-2], lo[lo.length-1], q) <= 0) lo.pop();
    lo.push(q);
  }
  const up = [];
  for (let i = p.length-1; i >= 0; i--){
    const q = p[i];
    while (up.length >= 2 && cross(up[up.length-2], up[up.length-1], q) <= 0) up.pop();
    up.push(q);
  }
  lo.pop(); up.pop();
  return lo.concat(up);
}

/* rotating calipers. One side of the smallest enclosing rectangle always
   lies along a hull edge, so trying every edge finds it. */
function scMinAreaRect(hull){
  let best = null;
  for (let i = 0; i < hull.length; i++){
    const a = hull[i], b = hull[(i+1) % hull.length];
    const ang = Math.atan2(b[1]-a[1], b[0]-a[0]);
    const cos = Math.cos(-ang), sin = Math.sin(-ang);
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const p of hull){
      const x = p[0]*cos - p[1]*sin, y = p[0]*sin + p[1]*cos;
      if (x < minX) minX = x; if (x > maxX) maxX = x;
      if (y < minY) minY = y; if (y > maxY) maxY = y;
    }
    const w = maxX-minX, h = maxY-minY;
    if (!best || w*h < best.area){
      const mx = (minX+maxX)/2, my = (minY+maxY)/2;
      const c = Math.cos(ang), s = Math.sin(ang);
      best = { area: w*h, w: w, h: h, angle: ang,
               cx: mx*c - my*s, cy: mx*s + my*c };
    }
  }
  if (!best) return null;
  if (best.w > best.h){                    /* force portrait */
    const t = best.w; best.w = best.h; best.h = t;
    best.angle += Math.PI/2;
  }
  while (best.angle >  Math.PI/2) best.angle -= Math.PI;
  while (best.angle < -Math.PI/2) best.angle += Math.PI;
  return best;
}

/* top row left to right, then the next row down. This is the order
   add_photos.py --assign files photos in, so a wrong order here puts a
   photo on the wrong card. Rows are banded, not assumed: two cards side by
   side are one row even when one sits a few millimetres higher. */
function scReadingOrder(cards){
  if (!cards.length) return [];
  const hs = cards.map(c => c.h).sort((a, b) => a - b);
  const band = hs[hs.length >> 1] * 0.5;
  const rows = [];
  cards.slice().sort((a, b) => a.cy - b.cy).forEach(c => {
    const row = rows.find(r => Math.abs(c.cy - r[0].cy) <= band);
    if (row) row.push(c); else rows.push([c]);
  });
  const out = [];
  rows.forEach(r => out.push.apply(out, r.sort((a, b) => a.cx - b.cx)));
  return out;
}

function scDetect(img){
  const scale = Math.min(1, SC_WORK / Math.max(img.width, img.height));
  const w = Math.max(1, Math.round(img.width * scale));
  const h = Math.max(1, Math.round(img.height * scale));
  const cv = document.createElement('canvas');
  cv.width = w; cv.height = h;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  cx.drawImage(img, 0, 0, w, h);
  const d = cx.getImageData(0, 0, w, h).data, n = w*h;

  const mag = scGradient(scBlur(scGrey(d, n), w, h), w, h);
  const thr = scPercentile(mag, SC_EDGE_PCT);
  const bg  = scBackground(d, w, h);

  const mask = new Uint8Array(n);
  for (let i = 0; i < n; i++){
    const diff = Math.max(Math.abs(d[i*4]   - bg[0]),
                          Math.abs(d[i*4+1] - bg[1]),
                          Math.abs(d[i*4+2] - bg[2]));
    mask[i] = (mag[i] > thr || diff > SC_COLOUR_TOL) ? 1 : 0;
  }

  const r = Math.max(1, Math.round(Math.min(w, h) * 0.012));
  const shut = scOpen(scClose(mask, w, h, r), w, h, 2);

  const page = w*h, found = [];
  scBlobs(shut, w, h).forEach(blob => {
    const rect = scMinAreaRect(scHull(blob.pts));
    if (!rect || rect.w < 1 || rect.h < 1) return;
    const area = rect.w * rect.h;
    if (area < page*SC_MIN_AREA || area > page*SC_MAX_AREA) return;
    const ar = rect.w / rect.h;
    if (ar < SC_ASPECT_MIN || ar > SC_ASPECT_MAX) return;
    if (blob.area / area < SC_MIN_RECT) return;
    found.push({ cx: rect.cx/scale, cy: rect.cy/scale,
                 w: rect.w/scale, h: rect.h/scale, angle: rect.angle });
  });
  return scReadingOrder(found);
}

/* pull one card off the page, straightened. maxW renders a small preview
   instead of the full crop, so twenty cards on screen stay cheap. */
function scExtract(img, rect, turns, maxW){
  let w = Math.round(rect.w), h = Math.round(rect.h), k = 1;
  if (maxW && w > maxW){ k = maxW / w; w = Math.round(w*k); h = Math.round(h*k); }

  const cv = document.createElement('canvas');
  cv.width = w; cv.height = h;
  const g = cv.getContext('2d');
  g.scale(k, k);
  g.translate(rect.w/2, rect.h/2);
  g.rotate(-rect.angle);
  g.translate(-rect.cx, -rect.cy);
  g.drawImage(img, 0, 0);

  const q = (((turns || 0) % 4) + 4) % 4;
  if (q === 0) return cv;
  const out = document.createElement('canvas');
  const flip = q % 2 === 1;
  out.width = flip ? h : w; out.height = flip ? w : h;
  const o = out.getContext('2d');
  o.translate(out.width/2, out.height/2);
  o.rotate(q * Math.PI/2);
  o.drawImage(cv, -w/2, -h/2);
  return out;
}

/* ---------------- the panel ---------------- */

const scDropEl = document.getElementById('sc-drop');
if (scDropEl) {
  const fileEl  = document.getElementById('sc-file');
  const outEl   = document.getElementById('sc-out');
  const msgEl   = document.getElementById('sc-msg');
  const countEl = document.getElementById('sc-count');
  const toolsEl = document.getElementById('sc-tools');
  let queue = [];

  const say = t => { if (msgEl) msgEl.textContent = t; };

  function stem(name){
    return (name || 'scan').replace(/\.[^.]+$/, '').replace(/[^\w-]+/g, '-');
  }

  function render(){
    outEl.innerHTML = '';
    queue.forEach((card, i) => {
      const tile = document.createElement('div');
      tile.className = 'sctile';

      const cv = scExtract(card.img, card.rect, card.turns, SC_THUMB_W);
      cv.className = 'scshot';
      tile.appendChild(cv);

      const name = document.createElement('div');
      name.className = 'scname';
      name.textContent = (i+1) + '. ' + card.name;
      tile.appendChild(name);

      const row = document.createElement('div');
      row.className = 'scrow';

      const rot = document.createElement('button');
      rot.className = 'btn2'; rot.type = 'button';
      rot.textContent = 'Turn';
      rot.title = 'Rotate this card a quarter turn';
      rot.addEventListener('click', () => { card.turns++; render(); });
      row.appendChild(rot);

      const del = document.createElement('button');
      del.className = 'btn2'; del.type = 'button';
      del.textContent = 'Not a card';
      del.addEventListener('click', () => { queue.splice(i, 1); render(); });
      row.appendChild(del);

      tile.appendChild(row);
      outEl.appendChild(tile);
    });

    if (countEl){
      countEl.textContent = queue.length
        ? queue.length + (queue.length === 1 ? ' card' : ' cards') + ' ready'
        : '';
    }
    if (toolsEl) toolsEl.hidden = !queue.length;
  }

  function loadImage(file){
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload  = () => { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('unreadable')); };
      img.src = url;
    });
  }

  async function take(files){
    const list = Array.from(files || []);
    if (!list.length) return;

    const pdfs = list.filter(f => /\.pdf$/i.test(f.name) || f.type === 'application/pdf');
    const imgs = list.filter(f => f.type.startsWith('image/'));

    if (pdfs.length && !imgs.length){
      say('That is a PDF, which is what the scanner writes. The page cannot open '
        + 'one -- run  python crop_scans.py --src "G:/Scans" --rotate 180  and drop '
        + 'the crops it makes into photos/crops here, or scan to JPEG instead.');
      return;
    }
    if (!imgs.length){ say('No images in that -- drop JPEG or PNG files.'); return; }
    if (pdfs.length) say(pdfs.length + ' PDF skipped; use crop_scans.py for those.');

    scDropEl.classList.add('busy');
    let added = 0, blank = 0;
    for (const file of imgs){
      say('Reading ' + file.name + '...');
      let img;
      try { img = await loadImage(file); }
      catch (e){ say('Could not read ' + file.name); continue; }

      /* yields to the browser so the drop zone can repaint mid-batch */
      await new Promise(r => setTimeout(r, 0));
      const rects = scDetect(img);
      if (!rects.length){ blank++; continue; }
      rects.forEach(rect => {
        queue.push({ img: img, rect: rect, turns: 0, name: stem(file.name) });
        added++;
      });
    }
    scDropEl.classList.remove('busy');
    render();

    let note = 'Found ' + added + (added === 1 ? ' card' : ' cards') + '.';
    if (blank) note += ' ' + blank + (blank === 1 ? ' image' : ' images')
                    + ' had nothing card-shaped on it.';
    if (added) note += ' Check the order and which way up they are, then save.';
    say(note);
  }

  function download(canvas, name){
    return new Promise(resolve => {
      canvas.toBlob(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = name;
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => { URL.revokeObjectURL(url); resolve(); }, 150);
      }, 'image/jpeg', 0.95);
    });
  }

  /* --- wiring --- */

  scDropEl.addEventListener('click', () => fileEl && fileEl.click());
  scDropEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); fileEl && fileEl.click(); }
  });
  if (fileEl) fileEl.addEventListener('change', () => {
    take(fileEl.files); fileEl.value = '';
  });

  ['dragenter', 'dragover'].forEach(ev =>
    scDropEl.addEventListener(ev, e => {
      e.preventDefault(); e.stopPropagation();
      scDropEl.classList.add('over');
    }));
  ['dragleave', 'drop'].forEach(ev =>
    scDropEl.addEventListener(ev, e => {
      e.preventDefault(); e.stopPropagation();
      scDropEl.classList.remove('over');
    }));
  scDropEl.addEventListener('drop', e => take(e.dataTransfer.files));

  /* paste, so a phone screenshot goes straight in */
  document.addEventListener('paste', e => {
    const panel = document.getElementById('p-add');
    if (!panel || panel.hidden) return;
    const items = e.clipboardData && e.clipboardData.files;
    if (items && items.length) take(items);
  });

  const rotAll = document.getElementById('sc-rotall');
  if (rotAll) rotAll.addEventListener('click', () => {
    queue.forEach(c => c.turns += 2);
    render();
    say('Turned every card half way round.');
  });

  const clearEl = document.getElementById('sc-clear');
  if (clearEl) clearEl.addEventListener('click', () => {
    queue = []; render(); say('Cleared.');
  });

  const saveEl = document.getElementById('sc-save');
  if (saveEl) saveEl.addEventListener('click', async () => {
    if (!queue.length) return;
    saveEl.disabled = true;
    /* numbered in the order shown, because that is the order
       add_photos.py --assign will read them back in */
    for (let i = 0; i < queue.length; i++){
      const card = queue[i];
      const n = String(i+1).padStart(2, '0');
      say('Saving ' + (i+1) + ' of ' + queue.length + '...');
      await download(scExtract(card.img, card.rect, card.turns),
                     card.name + '-' + n + '.jpg');
    }
    saveEl.disabled = false;
    say('Saved ' + queue.length + '. They are in your downloads folder, numbered '
      + 'in the order above -- move them to photos/crops and file them with '
      + 'add_photos.py --assign.');
  });

  render();
}
