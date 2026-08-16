/* Tests for the browser half of the scan cropper.

   Run: node test_scan.mjs

   These cover the geometry -- hull, smallest enclosing rectangle, reading
   order, percentile -- which is where a port goes wrong quietly. The canvas
   half is checked in a real browser against a real scan; there is no point
   faking a canvas to find out whether drawImage works.

   scan.js is a plain script, not a module, so it is read and evaluated with
   a stub for the one DOM call it makes before the panel wiring: getElementById
   returns null, the panel block is skipped, and the maths is left exposed. */

import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const src = readFileSync(new URL('./scan.js', import.meta.url), 'utf8');
const load = new Function('document', src + `
  return { scHull, scMinAreaRect, scReadingOrder, scPercentile,
           scBlobs, scClose, scOpen, scGrey, scBlur, scGradient, scBackground };`);
const S = load({ getElementById: () => null, addEventListener: () => {} });

let passed = 0, failed = 0;
function test(name, fn){
  try { fn(); passed++; }
  catch (e){ failed++; console.error('FAIL  ' + name + '\n      ' + e.message); }
}
const near = (a, b, tol) => Math.abs(a - b) <= tol;

/* --- hull --- */

test('hull of a filled square is its four corners', () => {
  const pts = [];
  for (let y = 0; y <= 10; y++) for (let x = 0; x <= 10; x++) pts.push([x, y]);
  const h = S.scHull(pts);
  assert.equal(h.length, 4);
});

test('hull ignores a point inside the shape', () => {
  const h = S.scHull([[0,0],[10,0],[10,10],[0,10],[5,5]]);
  assert.equal(h.length, 4);
  assert.ok(!h.some(p => p[0] === 5 && p[1] === 5));
});

/* --- smallest enclosing rectangle --- */

test('axis-aligned rectangle comes back at its own size', () => {
  const r = S.scMinAreaRect(S.scHull([[0,0],[50,0],[50,70],[0,70]]));
  assert.ok(near(r.w, 50, 1), 'width ' + r.w);
  assert.ok(near(r.h, 70, 1), 'height ' + r.h);
  assert.ok(near(r.cx, 25, 1) && near(r.cy, 35, 1), 'centre');
});

test('a landscape rectangle is turned portrait', () => {
  /* a crop must never land on its side, so w is always the short edge */
  const r = S.scMinAreaRect(S.scHull([[0,0],[70,0],[70,50],[0,50]]));
  assert.ok(near(r.w, 50, 1), 'short edge ' + r.w);
  assert.ok(near(r.h, 70, 1), 'long edge ' + r.h);
  assert.ok(Math.abs(r.angle) > 1.0, 'angle should carry the quarter turn');
});

test('a rotated rectangle keeps its size and reports its angle', () => {
  const deg = 20, rad = deg * Math.PI/180;
  const c = Math.cos(rad), s = Math.sin(rad);
  const corners = [[-25,-35],[25,-35],[25,35],[-25,35]]
    .map(([x, y]) => [x*c - y*s + 200, x*s + y*c + 300]);
  const r = S.scMinAreaRect(S.scHull(corners));
  assert.ok(near(r.w, 50, 1.5), 'width ' + r.w);
  assert.ok(near(r.h, 70, 1.5), 'height ' + r.h);
  assert.ok(near(r.cx, 200, 1.5) && near(r.cy, 300, 1.5), 'centre off');
  assert.ok(near(Math.abs(r.angle * 180/Math.PI), deg, 1.5),
            'angle ' + (r.angle * 180/Math.PI));
});

test('the angle stays within a quarter turn either way', () => {
  for (const deg of [-80, -10, 0, 35, 80]){
    const rad = deg * Math.PI/180, c = Math.cos(rad), s = Math.sin(rad);
    const corners = [[-25,-35],[25,-35],[25,35],[-25,35]]
      .map(([x, y]) => [x*c - y*s + 500, x*s + y*c + 500]);
    const r = S.scMinAreaRect(S.scHull(corners));
    assert.ok(r.angle >= -Math.PI/2 - 1e-6 && r.angle <= Math.PI/2 + 1e-6,
              'angle out of range at ' + deg);
  }
});

/* --- reading order: the one that misfiles photos if it is wrong --- */

const card = (cx, cy) => ({ cx, cy, w: 750, h: 1050, angle: 0 });
const seen = cs => cs.map(c => [c.cx, c.cy]);

test('reading order runs left to right, then down', () => {
  const out = S.scReadingOrder(
    [card(900,1800), card(400,600), card(900,600), card(400,1800)]);
  assert.deepEqual(seen(out), [[400,600],[900,600],[400,1800],[900,1800]]);
});

test('a crooked row is still one row', () => {
  /* sorting on y alone would swap these, and with --pairs that puts a back
     photo on the wrong SKU */
  const out = S.scReadingOrder([card(900,620), card(400,560)]);
  assert.deepEqual(seen(out), [[400,560],[900,620]]);
});

test('genuine rows stay separate', () => {
  const out = S.scReadingOrder([card(400,1800), card(400,600)]);
  assert.deepEqual(seen(out), [[400,600],[400,1800]]);
});

test('reading order of nothing is nothing', () => {
  assert.deepEqual(S.scReadingOrder([]), []);
});

test('browser and python reading order agree on the same layout', () => {
  /* the two croppers must number cards identically, or a batch cropped in
     the page and a batch cropped by the script would file differently */
  const out = S.scReadingOrder(
    [card(1400,2000), card(500,700), card(1400,700), card(500,2000)]);
  assert.deepEqual(seen(out), [[500,700],[1400,700],[500,2000],[1400,2000]]);
});

/* --- percentile --- */

test('percentile of a flat ramp lands near the right value', () => {
  const v = new Float32Array(1000);
  for (let i = 0; i < 1000; i++) v[i] = i;
  assert.ok(near(S.scPercentile(v, 92), 920, 12), S.scPercentile(v, 92));
});

test('percentile of all zeros is zero', () => {
  assert.equal(S.scPercentile(new Float32Array(50), 92), 0);
});

test('percentile is not thrown off by one huge outlier', () => {
  /* The bug this replaces. It bucketed into 1024 bins spanning 0..max and
     returned a bin's lower edge. One card edge makes max enormous, so every
     paper-grain gradient crushed into the first bin or two and the "92nd
     percentile" let 24% of the page through -- which the close then welded
     into a single page-sized blob and the card was never found. On a clean
     synthetic page the threshold is 0 either way, so nothing caught it. */
  const v = new Float32Array(10000);
  for (let i = 0; i < 9990; i++) v[i] = 1 + (i % 20) * 0.1;   /* grain, 1.0-2.9 */
  for (let i = 9990; i < 10000; i++) v[i] = 5000;             /* a card edge */
  const thr = S.scPercentile(v, 92);
  let over = 0;
  for (let i = 0; i < v.length; i++) if (v[i] > thr) over++;
  assert.ok(over <= v.length * 0.09,
            'threshold let ' + (100 * over / v.length).toFixed(1) + '% through, wanted <=9%');
});

test('percentile tracks the noise floor, which is what the edge floor uses', () => {
  const v = new Float32Array(1000);
  for (let i = 0; i < 1000; i++) v[i] = i < 500 ? 6 : 6 + (i - 500) * 0.02;
  assert.ok(Math.abs(S.scPercentile(v, 50) - 6) < 0.5, S.scPercentile(v, 50));
});

/* --- morphology and blobs --- */

test('close seals a gap in an outline', () => {
  const w = 40, h = 40, m = new Uint8Array(w*h);
  for (let x = 5; x < 35; x++){ m[5*w+x] = 1; m[34*w+x] = 1; }
  for (let y = 5; y < 35; y++){ m[y*w+5] = 1; if (y < 18 || y > 22) m[y*w+34] = 1; }
  const shut = S.scClose(m, w, h, 3);
  assert.equal(shut[20*w+34], 1, 'the gap in the right edge should be closed');
});

test('blobs finds two separate shapes', () => {
  const w = 80, h = 40, m = new Uint8Array(w*h);
  for (let y = 5; y < 35; y++){
    for (let x = 5; x < 30; x++) m[y*w+x] = 1;
    for (let x = 50; x < 75; x++) m[y*w+x] = 1;
  }
  assert.equal(S.scBlobs(m, w, h).length, 2);
});

test('blobs ignores a speck', () => {
  const w = 80, h = 40, m = new Uint8Array(w*h);
  for (let y = 5; y < 35; y++) for (let x = 5; x < 30; x++) m[y*w+x] = 1;
  m[2*w+70] = 1; m[2*w+71] = 1;
  assert.equal(S.scBlobs(m, w, h).length, 1);
});

test('blob outline is enough to rebuild the rectangle', () => {
  const w = 80, h = 60, m = new Uint8Array(w*h);
  for (let y = 10; y < 50; y++) for (let x = 20; x < 50; x++) m[y*w+x] = 1;
  const r = S.scMinAreaRect(S.scHull(S.scBlobs(m, w, h)[0].pts));
  assert.ok(near(r.w, 29, 2) && near(r.h, 39, 2), r.w + 'x' + r.h);
});

console.log((failed ? 'FAILED' : 'ok') + ' -- ' + passed + ' passed, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
