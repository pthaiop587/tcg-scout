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

/* Same working size as crop_scans.py. Deliberately identical: the two are
   meant to find the same cards on the same page, and a different working
   resolution is a quiet way for them to disagree. */
const SC_WORK = 1200;
/* Top slice of the gradient that counts as edge. Same number as
   EDGE_PERCENTILE in crop_scans.py, and it has to stay that way.

   It was 92, which is far too generous once a scan has grain on it: 8% of a
   page is a lot of scattered speckle, the close welds it together, and a
   speck stuck to a card stretches its convex hull until the rectangularity
   test throws the card out -- four cards on a sheet went to none. 98 still
   finds a white border against a white lid, which is the faintest line this
   has to see.

   A floor at a multiple of the median gradient was tried and dropped: a
   multiple of the median is a different threshold here than in the script,
   because this downscale smooths more and the median ran about a third of
   the script's. A percentile picks a share, so both agree by construction. */
const SC_EDGE_PCT = 98;

/* A percentile alone is still not enough, in the other direction: it always
   admits its share, so a page with ONE card on it -- whose real edge is well
   under 2% of the page -- drags the threshold down into the paper grain, and
   a speck welded to the card stretches its convex hull until the
   rectangularity test throws the card out. One card found none while four
   found all four, which is a memorable way to be wrong.
   So the threshold also has a floor at a multiple of the median gradient,
   which reads the noise level: grain sits near it, a card edge is orders of
   magnitude above. Matches EDGE_NOISE_MULT in crop_scans.py. It does nothing
   there -- cv2's blur returns uint8, so those gradients tie heavily past the
   threshold already -- but it is kept in both so the two cannot drift. */
const SC_EDGE_NOISE = 20.0;
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

/* Exact enough to match numpy, which matters more than it sounds.

   This was a histogram of 1024 bins spread from 0 to the largest gradient on
   the page. A card edge is enormous next to paper grain, so on any real scan
   the maximum is huge, every noise gradient falls in the first bin or two,
   and returning a bin's lower edge let 24% of the page through where 8% was
   asked for. The close then welded that speckle into one page-sized blob and
   the card vanished. Clean synthetic pages hid it completely: with no noise
   the threshold is 0 either way.

   Sorting a sample and indexing into it has no such failure mode, and one
   sort of ~200k floats per image is nothing next to the gradient pass. */
function scPercentile(v, pct){
  const n = v.length;
  if (!n) return 0;
  const stride = Math.max(1, Math.floor(n / 200000));
  const s = new Float32Array(Math.ceil(n / stride));
  let j = 0;
  for (let i = 0; i < n; i += stride) s[j++] = v[i];
  const sample = j === s.length ? s : s.subarray(0, j);
  sample.sort();
  const idx = Math.min(sample.length - 1,
                       Math.max(0, Math.round((sample.length - 1) * pct / 100)));
  return sample[idx];
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

/* Shrink to the working size by halving, not in one jump.
   cv2.resize INTER_AREA averages every source pixel that lands in a target
   pixel, so shrinking a scan 2.5x also divides its sensor noise by about the
   same. One canvas drawImage does not: it samples a handful of neighbours,
   noise comes through nearly intact, and on a lossless 600 dpi PNG that was
   enough to swamp the gradient percentile -- the mask turned to speckle, the
   close welded it into one page-sized blob, and the card was never found.
   The python cropper coped with the same page because of INTER_AREA alone.
   Repeated halving is the canvas equivalent: each step averages 4 pixels. */
function scFit(img, maxEdge){
  const scale = Math.min(1, maxEdge / Math.max(img.width, img.height));
  const fw = Math.max(1, Math.round(img.width * scale));
  const fh = Math.max(1, Math.round(img.height * scale));

  let cur = img, w = img.width, h = img.height;
  while (w > fw * 2){
    const nw = Math.max(fw, Math.round(w / 2)), nh = Math.max(fh, Math.round(h / 2));
    const step = document.createElement('canvas');
    step.width = nw; step.height = nh;
    const g = step.getContext('2d', { willReadFrequently: true });
    g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
    g.drawImage(cur, 0, 0, nw, nh);
    cur = step; w = nw; h = nh;
  }
  const out = document.createElement('canvas');
  out.width = fw; out.height = fh;
  const g = out.getContext('2d', { willReadFrequently: true });
  g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
  g.drawImage(cur, 0, 0, fw, fh);
  return { canvas: out, scale: scale };
}

function scDetect(img){
  const fit = scFit(img, SC_WORK);
  const scale = fit.scale;
  const w = fit.canvas.width, h = fit.canvas.height;
  const cx = fit.canvas.getContext('2d', { willReadFrequently: true });
  const d = cx.getImageData(0, 0, w, h).data, n = w*h;

  const mag = scGradient(scBlur(scGrey(d, n), w, h), w, h);
  const thr = Math.max(scPercentile(mag, SC_EDGE_PCT),
                       SC_EDGE_NOISE * scPercentile(mag, 50));
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

/* ---------------- the review queue ----------------
   Every card you drop lands here, not in My cards. That separation is the
   whole point: a crop is pixels, and a listing needs a name, a set, a number
   and a parallel that nothing on a static page can read off the picture. So
   the card is captured the moment it is scanned, and stays captured, but it
   cannot reach My cards -- and therefore cannot reach an eBay export -- until
   somebody has actually confirmed what it is.

   A row is confirmable when it has a name and nothing on it is still marked
   uncertain. Claude marks a field uncertain by prefixing it with ? in the
   paste, and the amber clears when you either edit the field or tick it.   */

const SC_QKEY = 'carddesk.queue.v1';
const SC_QTHUMB = 150;                 /* px wide; ~8 KB each in storage */

/* These are the workbook's own columns and the workbook's own wording, on
   purpose. The condition list is eBay's four rather than the collector's
   NM/LP/MP/HP/DMG, because eBay's four is what a listing actually carries and
   translating between them on the way out would quietly coarsen every card. */
const SC_CONDS = ['Near Mint or Better', 'Excellent', 'Very Good', 'Poor'];
const SC_FIELDS = [
  { k: 'n',    label: 'Card',      ph: 'Shedeur Sanders' },
  { k: 's',    label: 'Set',       ph: '2025 Panini Prizm Draft Picks' },
  { k: 'num',  label: 'Number',    ph: '8' },
  { k: 'var',  label: 'Parallel',  ph: 'Gold Cracked Ice' },
  { k: 'c',    label: 'Condition', sel: SC_CONDS },
  { k: 'q',    label: 'Qty',       num: true },
  { k: 'v',    label: 'Worth ea',  num: true, ph: '0.00' }
];

/* Everything that is the same for every card out of one box, pack or stack.
   Typing the year, the brand and the set on all twelve cards of a rip is the
   bulk of the work and none of it is per-card information. These are filled
   in once; a card inherits any of them it has not been given itself, so a
   mixed stack can still override the set on a single row. */
const SC_BATCH_FIELDS = [
  { k: 'year',   label: 'Year',        ph: '2025' },
  { k: 's',      label: 'Set / brand', ph: 'Panini Prizm Draft Picks', wide: true },
  { k: 'insert', label: 'Insert set',  ph: 'Student Orientation' },
  { k: 'team',   label: 'Team',        ph: 'Colorado Buffaloes' },
  { k: 'league', label: 'League',      sel: ['', 'NCAA', 'NFL', 'NBA', 'MLB', 'NHL', 'MLS', 'WWE', 'UFC'] },
  { k: 'sport',  label: 'Sport / game', ph: 'Football' },
  { k: 'kind',   label: 'Category',    sel: ['Sports', 'TCG', 'Non-sport'] },
  { k: 'c',      label: 'Condition',   sel: SC_CONDS },
  { k: 'source', label: 'Bought from', ph: 'Target Upland' },
  { k: 'lot',    label: 'Lot ID',      ph: 'LOT-001' }
];

/* queue field -> the name file_batch.py knows it by */
const SC_TO_BATCH = {
  n: 'player', s: 'brand', num: 'num', var: 'parallel',
  c: 'condition', q: 'qty', v: 'market', kind: 'category',
  year: 'year', insert: 'insert', team: 'team', league: 'league',
  sport: 'sport', source: 'source', lot: 'lot'
};

let SC_BATCH = {};

/* a card as it will actually be filed: its own values, then the batch's */
function scMerged(entry){
  const out = {};
  SC_BATCH_FIELDS.forEach(f => {
    const v = SC_BATCH[f.k];
    if (v !== undefined && v !== '') out[f.k] = v;
  });
  Object.keys(entry || {}).forEach(k => {
    if (SC_TO_BATCH[k] === undefined) return;
    const v = entry[k];
    if (v !== undefined && v !== '' && !(k === 'v' && !v)) out[k] = v;
  });
  return out;
}

/* what an old queue, or a paste written the collector's way, gets turned into */
const SC_COND_ALIAS = {
  NM: 'Near Mint or Better', MINT: 'Near Mint or Better',
  LP: 'Excellent', MP: 'Very Good', HP: 'Poor', DMG: 'Poor', DAMAGED: 'Poor'
};
function scCond(v){
  const s = String(v || '').trim();
  if (SC_CONDS.indexOf(s) >= 0) return s;
  return SC_COND_ALIAS[s.toUpperCase()] || 'Near Mint or Better';
}

let SC_QUEUE = [];
let SC_QPERSISTS = false;
/* Front, back, front, back is how a batch comes off a flatbed, so two crops
   are usually one card. With this on the queue pairs them up and asks for one
   set of details per card instead of two -- and confirms one card, not two.
   It is the same idea as add_photos.py --pairs, at the other end of the run. */
let SC_PAIRS = false;
const SC_FULL = new Map();     /* id -> {img, rect}; session only, never stored */

function scQLoad(){
  try {
    const raw = localStorage.getItem(SC_QKEY);
    SC_QPERSISTS = true;
    const saved = raw ? JSON.parse(raw) : {};
    SC_QUEUE = saved.queue || [];
    SC_PAIRS = !!saved.pairs;
    SC_BATCH = saved.batch || {};
    /* a queue stored before grouping was explicit has no card ids on it */
    if (SC_QUEUE.some(e => !e.card)){
      if (SC_PAIRS) scPairUp(); else scUnpair();
    }
  } catch (e){ SC_QPERSISTS = false; SC_QUEUE = []; SC_PAIRS = false; SC_BATCH = {}; }
}

/* The queue as CARDS rather than pictures.

   Grouping is by an explicit id each picture carries, not by its position.
   Position was the first attempt and it only ever worked for one shape of
   batch -- front, back, front, back, all dropped at once. Upload the two
   sides one at a time, or in any other order, and there was no way to say
   "this is the back of that one". An id can be assigned however you like:
   in pairs down the list, or one picture at a time onto a card you point at. */
function scGroups(){
  const byCard = new Map();
  SC_QUEUE.forEach(e => {
    const k = e.card || e.id;
    if (!byCard.has(k)) byCard.set(k, []);
    byCard.get(k).push(e);
  });
  return Array.from(byCard.values());
}

/* pair them off down the list: 1+2, 3+4, ... */
function scPairUp(){
  SC_QUEUE.forEach((e, i) => {
    e.card = SC_QUEUE[i - (i % 2)].id;
  });
}
function scUnpair(){
  SC_QUEUE.forEach(e => { e.card = e.id; });
}

function scQSave(){
  if (!SC_QPERSISTS) return;
  try { localStorage.setItem(SC_QKEY,
    JSON.stringify({ queue: SC_QUEUE, pairs: SC_PAIRS, batch: SC_BATCH,
                     at: Date.now() })); }
  catch (e){
    /* quota, almost certainly the thumbnails. Say so rather than failing mute. */
    SC_QPERSISTS = false;
    const m = document.getElementById('sc-msg');
    if (m) m.textContent = 'This browser will not store any more of the queue '
      + '(it is full). Confirm or clear some cards, and save your crops now.';
  }
}

let scUid = 0;
function scNewId(){ return 'q' + Date.now().toString(36) + (scUid++).toString(36); }

function scThumb(img, rect, turns){
  return scExtract(img, rect, turns, SC_QTHUMB).toDataURL('image/jpeg', 0.7);
}

const scReady = e => !!(e.n || '').trim() && !(e.flags && e.flags.length);

let scAttachTo = null;    /* which card an "Add back" picture belongs to */

const scDropEl = document.getElementById('sc-drop');
if (scDropEl) {
  const fileEl  = document.getElementById('sc-file');
  const wrapEl  = document.getElementById('sc-qwrap');
  const listEl  = document.getElementById('sc-queue');
  const msgEl   = document.getElementById('sc-msg');
  const countEl = document.getElementById('sc-qcount');

  const say = t => { if (msgEl) msgEl.textContent = t; };
  const stem = n => (n || 'scan').replace(/\.[^.]+$/, '').replace(/[^\w-]+/g, '-');

  /* ---- rendering ---- */

  function fieldEl(entry, f){
    const wrap = document.createElement('div');
    wrap.className = 'field';
    const lab = document.createElement('label');
    lab.textContent = f.label;
    wrap.appendChild(lab);

    let input;
    if (f.sel){
      input = document.createElement('select');
      /* A blank first option meaning "whatever the batch says". Without it a
         card is created already holding a condition, that counts as its own
         value, and it silently beats anything set for the whole batch. */
      const inh = SC_BATCH[f.k];
      const blank = document.createElement('option');
      blank.value = '';
      blank.textContent = (inh || f.sel[0]) + (inh ? ' — from batch' : '');
      input.appendChild(blank);
      f.sel.forEach(o => {
        const opt = document.createElement('option');
        opt.value = o; opt.textContent = o;
        input.appendChild(opt);
      });
      input.value = entry[f.k] || '';
      if (!entry[f.k] && inh) input.classList.add('inherited');
    } else {
      input = document.createElement('input');
      if (f.num){ input.type = 'number'; input.min = '0'; input.step = f.k === 'q' ? '1' : '0.5'; }
      /* an empty field shows what it will inherit from the batch strip, so
         you can see the set is filled in without it being typed on every row */
      const inherited = SC_BATCH[f.k];
      input.placeholder = (inherited !== undefined && inherited !== '')
        ? inherited : (f.ph || '');
      if (inherited) input.classList.add('inherited');
      input.value = entry[f.k] === 0 && f.k === 'v' ? '' : (entry[f.k] ?? '');
    }

    const flagged = (entry.flags || []).includes(f.k);
    if (flagged) input.classList.add('unsure');

    input.addEventListener('input', () => {
      entry[f.k] = f.num ? (parseFloat(input.value) || 0) : input.value;
      /* editing a field is the same statement as ticking it: you looked */
      if ((entry.flags || []).includes(f.k)){
        entry.flags = entry.flags.filter(x => x !== f.k);
        input.classList.remove('unsure');
      }
      /* and a card you have just edited is no longer a card you have checked,
         or "checked" would mean nothing */
      if (entry.ok){ entry.ok = false; entry.filed = false; }
      scQSave(); renderFoot();
    });
    input.addEventListener('change', () => {
      if (entry.ok){ entry.ok = false; entry.filed = false; }
      scQSave(); renderRows();
    });
    wrap.appendChild(input);

    if (flagged){
      const tick = document.createElement('button');
      tick.type = 'button'; tick.className = 'unsurebtn';
      tick.textContent = 'looks right';
      tick.title = 'Clear the amber without changing the value';
      tick.addEventListener('click', () => {
        entry.flags = entry.flags.filter(x => x !== f.k);
        scQSave(); render();
      });
      wrap.appendChild(tick);
    }
    return wrap;
  }

  function rowEl(group, i, warnings){
    /* the first picture of a card carries its details; a back is just
       another photo of the same card */
    const entry = group[0];
    const row = document.createElement('div');
    row.className = 'qrow' + (scReady(entry) ? ' ready' : '')
      + (entry.ok ? ' ok' : '') + (entry.filed ? ' filed' : '');

    const left = document.createElement('div');
    left.className = 'qleft';
    const shots = document.createElement('div');
    shots.className = 'qshots';
    const withPics = group.filter(e => e.thumb);
    if (!withPics.length){
      /* a card typed in before its photograph exists -- the row is the card,
         the picture catches up later */
      const ph = document.createElement('div');
      ph.className = 'qshot noshot';
      ph.textContent = 'no picture yet';
      shots.appendChild(ph);
    } else {
      withPics.forEach((e, k) => {
        const im = document.createElement('img');
        im.className = 'qshot' + (withPics.length > 1 ? ' pair' : '');
        im.src = e.thumb;
        im.alt = 'card ' + (i + 1) + (withPics.length > 1 ? (k ? ' back' : ' front') : '');
        im.title = withPics.length > 1 ? (k ? 'back' : 'front') : '';
        shots.appendChild(im);
      });
    }
    left.appendChild(shots);
    const cap = document.createElement('div');
    cap.className = 'scname';
    cap.textContent = (i + 1) + '. ' + entry.src
      + (group.length > 1 ? ' (front + back)' : '');
    left.appendChild(cap);
    row.appendChild(left);

    const mid = document.createElement('div');
    const fields = document.createElement('div');
    fields.className = 'qfields';
    SC_FIELDS.forEach(f => fields.appendChild(fieldEl(entry, f)));
    mid.appendChild(fields);

    if (warnings && warnings.length){
      const w = document.createElement('p');
      w.className = 'qwarn';
      w.textContent = 'Check: ' + warnings.join(' · ');
      mid.appendChild(w);
    }
    row.appendChild(mid);

    const acts = document.createElement('div');
    acts.className = 'qacts';
    const has = group.every(e => SC_FULL.has(e.id));
    const many = group.length > 1;

    const btn = (text, title, fn, cls) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'btn2' + (cls ? ' ' + cls : '');
      b.textContent = text; if (title) b.title = title;
      b.addEventListener('click', fn);
      acts.appendChild(b);
      return b;
    };

    const conf = btn(entry.ok ? 'Checked' : 'Confirm',
      entry.ok ? 'Press again to un-check it'
               : 'Mark this card checked and ready for the workbook',
      () => {
        if (entry.ok){ entry.ok = false; entry.filed = false; scQSave(); render(); }
        else confirmOne(group);
      }, entry.ok ? '' : 'go');
    conf.disabled = !entry.ok && !scReady(entry);
    if (!entry.ok){
      if (!(entry.n || '').trim()) conf.title = 'Needs a card name first';
      else if ((entry.flags || []).length) conf.title = 'Clear the amber fields first';
    }

    /* the answer to "how do I upload the back of THIS card" -- point at the
       card, pick the picture, done, whatever order they arrived in */
    btn(!group.some(e => e.thumb) ? 'Add picture' : (many ? 'Add another' : 'Add back'),
        'Upload a picture for this card', () => {
      scAttachTo = entry.card || entry.id;
      const addEl = document.getElementById('sc-add');
      if (addEl) addEl.click();
    });

    /* and the other half of it: two sides already uploaded as two cards,
       which is what happens if you drop them one at a time */
    if (i > 0 && !many) btn('Join to ' + i, 'Make this the back of the card above', () => {
      const prev = scGroups()[i - 1];
      const key = prev[0].card || prev[0].id;
      group.forEach(e => { e.card = key; });
      SC_PAIRS = false;
      scQSave(); render();
      say('Joined — one card with two pictures now.');
    });

    if (many) btn('Split', 'Treat these as separate cards again', () => {
      group.forEach(e => { e.card = e.id; });
      SC_PAIRS = false;
      scQSave(); render();
      say('Split — those are two cards again.');
    });

    const turn = btn(many ? 'Turn both' : 'Turn', 'Rotate a quarter turn', () => {
      group.forEach(e => {
        const full = SC_FULL.get(e.id);
        if (!full) return;
        e.turns = (e.turns || 0) + 1;
        e.thumb = scThumb(full.img, full.rect, e.turns);
      });
      scQSave(); render();
    });
    turn.disabled = !group.some(e => SC_FULL.has(e.id));

    const save = btn(many ? 'Save both' : 'Save crop',
                     'Download the full-size picture', async () => {
      for (let k = 0; k < group.length; k++){
        const full = SC_FULL.get(group[k].id);
        if (!full) continue;
        await download(scExtract(full.img, full.rect, group[k].turns),
                       cropName(group[k]));
      }
    });
    save.disabled = !group.some(e => SC_FULL.has(e.id));
    if (!has) save.title = 'The full-size picture was only in this session. '
      + 'Drop the scan again to save it.';

    btn('Remove', 'Take it off the queue without adding it', () => {
      SC_QUEUE = SC_QUEUE.filter(x => group.indexOf(x) < 0);
      group.forEach(e => SC_FULL.delete(e.id));
      scQSave(); render();
    });

    row.appendChild(acts);
    return row;
  }

  /* Numbered by position in the queue, not by card, so a paired batch comes
     out front, back, front, back -- which is the order
     add_photos.py --assign --pairs reads them back in. */
  function cropName(entry){
    const n = SC_QUEUE.filter(e => e.thumb).indexOf(entry) + 1;
    return (entry.src || 'card') + '-' + String(n).padStart(2, '0') + '.jpg';
  }

  function renderFoot(){
    const groups = scGroups();
    const ready = groups.filter(g => scReady(g[0]) && !g[0].ok).length;
    const ok = groups.filter(g => g[0].ok).length;
    const filed = groups.filter(g => g[0].filed).length;
    if (countEl){
      countEl.textContent = groups.length
        ? groups.length + (groups.length === 1 ? ' card' : ' cards')
          + ' \u00b7 ' + ok + ' checked' + (filed ? ' \u00b7 ' + filed + ' saved' : '')
        : '';
    }
    const c = document.getElementById('sc-qconfirm');
    if (c){
      c.disabled = !ready;
      c.textContent = ready ? 'Check ' + ready + ' off' : 'Check all ready';
    }
    const t = document.getElementById('sc-tofile');
    if (t){
      t.disabled = !ok;
      t.textContent = ok ? 'Save ' + ok + ' for the workbook' : 'Save for the workbook';
    }
    const cf = document.getElementById('sc-clearfiled');
    if (cf){ cf.hidden = !filed; cf.textContent = 'Clear ' + filed + ' saved'; }
    const odd = document.getElementById('sc-odd');
    if (odd) odd.hidden = !(SC_PAIRS && groups.some(g => g.length === 1));
  }

  /* the "same for every card" strip. Rebuilt only when it is empty, so
     typing in it does not tear the field you are typing in out from under you. */
  function renderBatch(){
    const host = document.getElementById('sc-batch');
    if (!host || host.childNodes.length) return;
    SC_BATCH_FIELDS.forEach(f => {
      const wrap = document.createElement('div');
      wrap.className = 'field' + (f.wide ? ' wide' : '');
      const lab = document.createElement('label');
      lab.textContent = f.label;
      wrap.appendChild(lab);
      let input;
      if (f.sel){
        input = document.createElement('select');
        f.sel.forEach(o => {
          const opt = document.createElement('option');
          opt.value = o; opt.textContent = o || '—';
          if (String(SC_BATCH[f.k] || '') === o) opt.selected = true;
          input.appendChild(opt);
        });
      } else {
        input = document.createElement('input');
        input.placeholder = f.ph || '';
        input.value = SC_BATCH[f.k] || '';
      }
      input.addEventListener('input', () => {
        SC_BATCH[f.k] = input.value;
        scQSave(); renderRows();
      });
      input.addEventListener('change', () => {
        SC_BATCH[f.k] = input.value;
        scQSave(); renderRows();
      });
      wrap.appendChild(input);
      host.appendChild(wrap);
    });
  }

  function renderRows(){
    if (!listEl) return;
    const groups = scGroups();
    const warns = scAudit(groups);
    listEl.innerHTML = '';
    groups.forEach((g, i) => listEl.appendChild(rowEl(g, i, warns[i])));
    renderFoot();
  }

  function render(){
    if (wrapEl) wrapEl.hidden = !SC_QUEUE.length;
    const pairEl = document.getElementById('sc-pairs');
    if (pairEl) pairEl.checked = SC_PAIRS;
    renderBatch();
    if (!listEl) return;
    renderRows();

    const lost = SC_QUEUE.filter(e => !SC_FULL.has(e.id)).length;
    const warn = document.getElementById('sc-lost');
    if (warn){
      warn.hidden = !lost;
      warn.textContent = lost + (lost === 1 ? ' card on this list kept' : ' cards on this list kept')
        + ' its details but not its full-size picture \u2014 that only lives in the '
        + 'session it was dropped in. The details are safe; drop the scan again if '
        + 'you still need the photo for a listing.';
    }
  }

  /* ---- confirming ---- */

  /* Confirming means "I have checked this one", nothing more. It used to
     push the card into My cards, which was a dead end: that list can only be
     edited by nudging a quantity up and down, and its CSV is a pricing
     worksheet, not an eBay upload. The workbook is the record and the only
     thing that can produce a real listing, so a confirmed card waits here to
     be filed into it instead. */
  function confirmOne(group){
    const entry = group[0];
    if (!scReady(entry)) return;
    entry.ok = true;
    scQSave(); render();
  }

  /* the card as file_batch.py wants it: its own values over the batch's */
  function batchCard(group){
    const e = group[0];
    const m = scMerged(e);
    const card = { photos: group.filter(x => SC_FULL.has(x.id)).length };

    Object.keys(m).forEach(k => {
      const name = SC_TO_BATCH[k];
      if (!name) return;
      let v = m[k];
      if (k === 'q') v = Math.max(1, Math.round(parseFloat(v) || 1));
      else if (k === 'v'){ v = parseFloat(v); if (!(v > 0)) return; }
      else if (typeof v === 'string') v = v.trim();
      if (v === '' || v === undefined || v === null) return;
      card[name] = v;
    });

    if (!card.qty) card.qty = 1;
    if (!card.condition) card.condition = SC_CONDS[0];
    if (!card.category) card.category = 'Sports';

    const unsure = (e.flags || []).map(f => SC_TO_BATCH[f]).filter(Boolean);
    if (card.market === undefined) unsure.push('market');
    if (unsure.length) card.unsure = Array.from(new Set(unsure));
    return card;
  }

  /* Things worth a second look before a card becomes a listing. These are
     warnings, not blocks -- the odd card really does have no number, and
     being nagged about it is better than being stopped. The duplicate check
     is the one that catches a real mistake: two rows with the same player,
     set, number and parallel usually means a front and a back came apart
     and are about to be filed as two separate cards. */
  function scAudit(groups){
    const seen = new Map();
    groups.forEach((g, i) => {
      const m = scMerged(g[0]);
      const key = [m.n, m.s, m.num, m.var].map(x => String(x || '').trim().toLowerCase()).join('|');
      if (!m.n) return;
      if (!seen.has(key)) seen.set(key, []);
      seen.get(key).push(i + 1);
    });

    return groups.map((g, i) => {
      const e = g[0], m = scMerged(e), out = [];
      if (!String(m.s || '').trim()) out.push('no set or brand');
      if (!String(m.num || '').trim()) out.push('no card number');
      if (!(parseFloat(m.v) > 0)) out.push('no worth — it will file as Review');
      if (!m.year) out.push('no year');
      if (m.kind === 'TCG' && /foot|basket|base|hockey|soccer/i.test(String(m.sport || '')))
        out.push('category is TCG but the sport is a sport');
      if (m.kind === 'Sports' && !String(m.sport || '').trim())
        out.push('no sport');
      if (parseFloat(m.q) > 1 && String(m.var || '').match(/\/\s*\d/))
        out.push('serial numbered but qty is more than 1');
      if (g.length > 2) out.push(g.length + ' pictures on one card');

      const key = [m.n, m.s, m.num, m.var].map(x => String(x || '').trim().toLowerCase()).join('|');
      const dupes = (seen.get(key) || []).filter(n => n !== i + 1);
      if (m.n && dupes.length)
        out.push('same card as ' + dupes.map(n => '#' + n).join(', ')
                 + ' — is one of them a back?');
      return out;
    });
  }

  /* ---- taking files ---- */

  function loadImage(file){
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload  = () => { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('unreadable')); };
      img.src = url;
    });
  }

  /* targetCard attaches whatever is found to a card already on the queue,
     which is how a back gets onto its front when the two were not uploaded
     together in the right order */
  async function take(files, targetCard){
    const list = Array.from(files || []);
    if (!list.length) return;

    const pdfs = list.filter(f => /\.pdf$/i.test(f.name) || f.type === 'application/pdf');
    const imgs = list.filter(f => f.type.startsWith('image/'));

    if (pdfs.length && !imgs.length){
      say('That is a PDF. Nothing here can read one \u2014 the scanner writes PNG now, '
        + 'or run  python crop_scans.py --src "G:/Scans" --rotate 180  for a folder.');
      return;
    }
    if (!imgs.length){ say('No images in that \u2014 drop PNG or JPEG files.'); return; }
    if (pdfs.length) say(pdfs.length + ' PDF skipped; use crop_scans.py for those.');

    scDropEl.classList.add('busy');
    let added = 0, blank = 0;
    for (const file of imgs){
      say('Reading ' + file.name + '\u2026');
      let img;
      try { img = await loadImage(file); }
      catch (e){ say('Could not read ' + file.name); continue; }

      await new Promise(r => setTimeout(r, 0));   /* let the page repaint */
      const rects = scDetect(img);
      if (!rects.length){ blank++; continue; }

      rects.forEach(rect => {
        const id = scNewId();
        SC_FULL.set(id, { img: img, rect: rect });
        SC_QUEUE.push({
          id: id, card: targetCard || id,
          src: stem(file.name), turns: 0, thumb: scThumb(img, rect, 0),
          /* blank, not defaulted -- a value here would beat the batch strip */
          kind: '', n: '', s: '', num: '', var: '', c: '', q: 1, v: 0,
          flags: [], at: Date.now()
        });
        added++;
      });
    }
    scDropEl.classList.remove('busy');
    if (targetCard && added){
      /* the empty stand-in has done its job now a real picture is here */
      SC_QUEUE = SC_QUEUE.filter(e => !(e.card === targetCard && !e.thumb));
    }
    if (SC_PAIRS && !targetCard) scPairUp();
    scQSave(); render();

    if (targetCard){
      say(added
        ? 'Added ' + added + (added === 1 ? ' more picture' : ' more pictures')
          + ' to that card. It is still one card.'
        : 'Nothing card-shaped in that image, so nothing was added.');
      return;
    }

    let note = 'Found ' + added + (added === 1 ? ' card' : ' cards')
             + ' and put ' + (added === 1 ? 'it' : 'them') + ' on the review queue.';
    if (blank) note += ' ' + blank + (blank === 1 ? ' image' : ' images')
                    + ' had nothing card-shaped on it.';
    if (added) note += ' Nothing is in My cards yet \u2014 fill in what each one is, then confirm.';
    say(note);
  }

  function downloadText(text, name){
    const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
    const a = document.createElement('a');
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 200);
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

  /* ---- wiring ---- */

  scDropEl.addEventListener('click', () => fileEl && fileEl.click());
  scDropEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); fileEl && fileEl.click(); }
  });
  if (fileEl) fileEl.addEventListener('change', () => { take(fileEl.files); fileEl.value = ''; });

  const addEl = document.getElementById('sc-add');
  if (addEl) addEl.addEventListener('change', () => {
    const to = scAttachTo;
    scAttachTo = null;
    take(addEl.files, to);
    addEl.value = '';
  });

  ['dragenter', 'dragover'].forEach(ev => scDropEl.addEventListener(ev, e => {
    e.preventDefault(); e.stopPropagation(); scDropEl.classList.add('over');
  }));
  ['dragleave', 'drop'].forEach(ev => scDropEl.addEventListener(ev, e => {
    e.preventDefault(); e.stopPropagation(); scDropEl.classList.remove('over');
  }));
  scDropEl.addEventListener('drop', e => take(e.dataTransfer.files));

  document.addEventListener('paste', e => {
    const panel = document.getElementById('p-add');
    if (!panel || panel.hidden) return;
    const t = e.target;
    if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;   /* let a real paste be a paste */
    const items = e.clipboardData && e.clipboardData.files;
    if (items && items.length) take(items);
  });

  const onEarly = (id, fn) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', fn);
  };
  onEarly('sc-blank', () => {
    const id = scNewId();
    SC_QUEUE.push({
      id: id, card: id, src: 'typed', turns: 0, thumb: '',
      kind: '', n: '', s: '', num: '', var: '', c: '', q: 1, v: 0,
      flags: [], at: Date.now()
    });
    scQSave(); render();
    say('Added a card with no picture. Fill it in, and use "Add picture" on it '
      + 'whenever you get round to photographing it.');
  });

  const on = (id, fn) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', fn);
    return el;
  };

  on('sc-rotall', () => {
    let done = 0;
    SC_QUEUE.forEach(e => {
      const full = SC_FULL.get(e.id);
      if (!full) return;
      e.turns = (e.turns || 0) + 2;
      e.thumb = scThumb(full.img, full.rect, e.turns);
      done++;
    });
    scQSave(); render();
    say(done ? 'Turned ' + done + ' round.' : 'Nothing here still has its full-size picture to turn.');
  });

  on('sc-qconfirm', () => {
    const ready = scGroups().filter(g => scReady(g[0]) && !g[0].ok);
    if (!ready.length) return;
    ready.forEach(confirmOne);
    say('Checked ' + ready.length + '. Now press "Save for the workbook" and '
      + 'run file_batch.py \u2014 that is what puts them in the spreadsheet.');
  });

  /* The handover. Downloads the pictures, numbered so filename order is the
     order shown here, then a batch file naming each card and how many of
     those pictures are its own. file_batch.py reads the two together. */
  on('sc-tofile', async () => {
    const groups = scGroups().filter(g => g[0].ok);
    if (!groups.length){ say('Nothing confirmed yet \u2014 check a card first.'); return; }

    const btn = document.getElementById('sc-tofile');
    btn.disabled = true;
    const cards = [];
    let n = 0, missing = 0;
    for (const g of groups){
      for (const e of g){
        const full = SC_FULL.get(e.id);
        if (!full){ missing++; continue; }
        n++;
        say('Saving picture ' + n + '\u2026');
        await download(scExtract(full.img, full.rect, e.turns),
                       'crh-' + String(n).padStart(3, '0') + '.jpg');
      }
      cards.push(batchCard(g));
    }
    downloadText(JSON.stringify({ cards: cards }, null, 2), 'batch.json');
    btn.disabled = false;

    groups.forEach(g => { g[0].filed = true; });
    scQSave(); render();

    say('Saved ' + n + ' picture' + (n === 1 ? '' : 's') + ' and batch.json for '
      + cards.length + ' card' + (cards.length === 1 ? '' : 's') + '. '
      + (missing ? missing + ' picture(s) were gone from this session and are not in it. ' : '')
      + 'Move the crh-*.jpg files into photos/crops, put batch.json beside the '
      + 'workbook, then run:  python file_batch.py batch.json  and  '
      + 'python make_ebay_csv.py');
  });

  on('sc-clearfiled', () => {
    const gone = scGroups().filter(g => g[0].filed);
    if (!gone.length) return;
    const ids = new Set();
    gone.forEach(g => g.forEach(e => ids.add(e.id)));
    SC_QUEUE = SC_QUEUE.filter(e => !ids.has(e.id));
    ids.forEach(id => SC_FULL.delete(id));
    scQSave(); render();
    say('Cleared ' + gone.length + ' filed card' + (gone.length === 1 ? '' : 's')
      + ' off the queue.');
  });

  on('sc-save', async () => {
    const have = SC_QUEUE.filter(e => SC_FULL.has(e.id));
    if (!have.length){ say('No full-size pictures left in this session to save.'); return; }
    const btn = document.getElementById('sc-save');
    btn.disabled = true;
    for (let i = 0; i < have.length; i++){
      const e = have[i];
      say('Saving ' + (i + 1) + ' of ' + have.length + '\u2026');
      const full = SC_FULL.get(e.id);
      await download(scExtract(full.img, full.rect, e.turns), cropName(e));
    }
    btn.disabled = false;
    say('Saved ' + have.length + ', numbered in the order shown. Move them to '
      + 'photos/crops, then either  python file_batch.py batch.json  to let '
      + 'Claude file the lot, or  add_photos.py --assign'
      + (SC_PAIRS ? ' --pairs' : '') + '  to do it yourself.');
  });

  /* pairing changes what counts as a card, so the whole list redraws */
  const pairEl = document.getElementById('sc-pairs');
  if (pairEl) pairEl.addEventListener('change', () => {
    SC_PAIRS = pairEl.checked;
    if (SC_PAIRS) scPairUp(); else scUnpair();
    scQSave(); render();
    say(SC_PAIRS
      ? 'Paired off down the list: 1 with 2, 3 with 4. If any pair is wrong, '
        + 'Split it and use Add back on the right card.'
      : 'Unpaired — every picture is its own card again.');
  });

  on('sc-clear', () => {
    if (!SC_QUEUE.length) return;
    if (!window.confirm('Throw away all ' + SC_QUEUE.length + ' card'
        + (SC_QUEUE.length === 1 ? '' : 's') + ' on the review queue? '
        + 'Anything already confirmed into My cards stays.')) return;
    SC_QUEUE = []; SC_FULL.clear(); scQSave(); render(); say('Queue cleared.');
  });

  /* Claude cannot write to this browser, so a batch it worked out arrives as
     a paste. One line per card in the order shown; ? marks a field it is not
     sure of, which comes through amber and blocks Confirm until you look. */
  on('sc-qfill', () => {
    const ta = document.getElementById('sc-qpaste');
    const lines = ta.value.split('\n').map(s => s.trim()).filter(Boolean);
    if (!lines.length){ say('Nothing to fill from.'); return; }
    if (!SC_QUEUE.length){ say('Drop some scans first \u2014 this fills the queue in order.'); return; }

    /* one line per CARD, not per picture -- so with pairs on, line 2 is the
       second card, not the back of the first */
    const groups = scGroups();
    let n = 0, unsure = 0;
    lines.forEach((line, i) => {
      const g = groups[i];
      if (!g) return;
      const e = g[0];
      const cells = line.split('|').map(s => s.trim());
      const keys = ['n', 's', 'num', 'var', 'c', 'q', 'v', 'kind'];
      e.flags = [];
      keys.forEach((k, j) => {
        let val = cells[j];
        if (val === undefined || val === '') return;
        if (val.charAt(0) === '?'){ val = val.slice(1).trim(); e.flags.push(k); unsure++; }
        if (k === 'q') e.q = Math.max(1, Math.round(parseFloat(val) || 1));
        else if (k === 'v') e.v = Math.max(0, parseFloat(val) || 0);
        else if (k === 'c') e.c = scCond(val);
        else if (k === 'kind'){
          e.kind = /tcg/i.test(val) ? 'TCG'
                 : /non.?sport/i.test(val) ? 'Non-sport' : 'Sports';
        }
        else e[k] = val;
      });
      n++;
    });
    ta.value = '';
    scQSave(); render();
    say('Filled ' + n + ' of ' + groups.length + '.'
      + (unsure ? ' ' + unsure + ' field' + (unsure === 1 ? '' : 's')
                + ' came through marked unsure \u2014 they are amber, and Confirm '
                + 'stays off until you have looked at each one.' : '')
      + (lines.length > groups.length
         ? ' ' + (lines.length - groups.length) + ' extra line(s) ignored.' : ''));
  });

  scQLoad();
  if (!SC_QPERSISTS) say('This browser is blocking storage, so the review queue '
    + 'will not survive a reload. Confirm as you go.');
  render();
}
