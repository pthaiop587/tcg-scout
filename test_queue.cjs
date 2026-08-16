/* The review queue's contract, end to end in a real browser.

   Build first, then run:
     python build_all.py . card-run-hq.html
     node test_queue.cjs

   The rule the whole design rests on is that a dropped card is captured
   immediately but CANNOT reach My cards -- and so cannot reach an eBay
   export -- until somebody has confirmed what it is. Every check below is
   some version of that.

   Needs a scan to drop, so it makes one: a card on a blank sheet.            */

process.env.NODE_PATH = require('child_process').execSync('npm root -g').toString().trim();
require('module').Module._initPaths();

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');

const PAGE = 'card-run-hq.html';
const SCAN = path.join(require('os').tmpdir(), 'crh_test_scan.png');

const fails = [];
const check = (ok, msg) => { if (!ok) fails.push(msg); };

/* the paste box lives in a fold, so open it the way a person would */
async function openPaste(page){
  await page.evaluate(() => {
    const d = document.getElementById('sc-qpaste').closest('details');
    if (d && !d.open) d.querySelector('summary').click();
  });
  await page.waitForTimeout(120);
}

function makeScan(){
  /* a dark card on a pale sheet -- enough for the detector, no fixture to commit */
  const py = `
import numpy as np, cv2
page = np.full((3300,2550,3), 246, np.uint8)
page = (page + np.random.default_rng(0).normal(0,2,page.shape)).clip(0,255).astype(np.uint8)
card = np.full((1050,750,3), 60, np.uint8)
card[60:990, 60:690] = (200,170,90)
cv2.rectangle(card,(0,0),(749,1049),(30,30,30),6)
page[300:1350, 300:1050] = card
cv2.imwrite(r"${SCAN.replace(/\\/g, '\\\\')}", page)
`;
  execFileSync('python', ['-c', py]);
}

(async () => {
  if (!fs.existsSync(PAGE)) {
    console.error('no ' + PAGE + ' -- run: python build_all.py . ' + PAGE);
    process.exit(1);
  }
  makeScan();

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1500, height: 1000 } });
  const page = await ctx.newPage();
  const jsErrors = [];
  page.on('pageerror', e => jsErrors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') jsErrors.push('console: ' + m.text()); });

  const url = 'file:///' + path.resolve(PAGE).replace(/\\/g, '/');
  await page.goto(url, { waitUntil: 'load' });

  const stock = () => page.evaluate(() => CD_STOCK.length);
  const queue = () => page.evaluate(() => SC_QUEUE.length);
  const confirmOff = () => page.evaluate(() =>
    document.getElementById('sc-qconfirm').disabled);

  check(await stock() === 0, 'My cards should start empty in a fresh profile');

  /* --- drop --- */
  await page.setInputFiles('#sc-file', SCAN);
  await page.waitForSelector('.qrow', { timeout: 30000 });
  await page.waitForTimeout(300);

  check(await queue() === 1, 'the dropped card should be on the queue, got ' + await queue());
  check(await stock() === 0, 'A DROPPED CARD REACHED MY CARDS WITHOUT BEING CONFIRMED');
  check(await page.isVisible('#sc-qwrap'), 'queue section should appear once a card is on it');
  check(await confirmOff(), 'Confirm should be off while the card has no name');

  /* --- a row with no name cannot be confirmed --- */
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('.qacts .btn2')].find(x => x.textContent === 'Confirm');
    b.click();                      /* disabled, so this must do nothing */
  });
  check(await stock() === 0, 'a nameless card was confirmed into My cards');

  /* --- fill from a paste with one field flagged --- */
  await openPaste(page);
  await page.fill('#sc-qpaste',
    'Shedeur Sanders | 2025 Prizm Draft Picks | 8 | ?Gold Cracked Ice | NM | 1 | 12.50 | sports');
  await page.click('#sc-qfill');
  await page.waitForTimeout(250);

  const filled = await page.evaluate(() => SC_QUEUE[0]);
  check(filled.n === 'Shedeur Sanders', 'name did not come through: ' + filled.n);
  check(filled.var === 'Gold Cracked Ice', 'the ? should be stripped off the value, got ' + filled.var);
  check(filled.v === 12.5, 'worth did not parse, got ' + filled.v);
  check(filled.q === 1, 'qty did not parse, got ' + filled.q);
  check(filled.kind === 'sports', 'kind did not parse, got ' + filled.kind);
  check(JSON.stringify(filled.flags) === '["var"]', 'flags should be ["var"], got ' + JSON.stringify(filled.flags));
  check(await page.locator('.qfields .unsure').count() === 1, 'the unsure field should be amber');
  check(await confirmOff(), 'CONFIRM WAS ON WHILE A FIELD WAS STILL MARKED UNSURE');

  /* --- clearing the flag is what unlocks it --- */
  await page.click('.unsurebtn');
  await page.waitForTimeout(200);
  check(await page.evaluate(() => SC_QUEUE[0].flags.length) === 0, 'flag did not clear');
  check(!(await confirmOff()), 'Confirm should be on once nothing is unsure');

  /* --- confirm --- */
  await page.click('#sc-qconfirm');
  await page.waitForTimeout(300);
  check(await stock() === 1, 'the confirmed card should be in My cards, got ' + await stock());
  check(await queue() === 0, 'the confirmed card should leave the queue');
  check(!(await page.isVisible('#sc-qwrap')), 'queue section should go away when empty');

  const card = await page.evaluate(() => CD_STOCK[0]);
  check(card.manual === 1, 'confirmed card should be a manual row');
  check(card.n === 'Shedeur Sanders' && card.num === '8' && card.var === 'Gold Cracked Ice',
        'confirmed card lost fields: ' + JSON.stringify(card));
  check(card.c === 'NM' && card.q === 1 && card.v === 12.5,
        'confirmed card has wrong condition/qty/value: ' + JSON.stringify(card));
  check(card.kind === 'sports', 'confirmed card routed wrong: ' + card.kind);

  /* --- the queue survives a reload, still outside My cards --- */
  await page.setInputFiles('#sc-file', SCAN);
  await page.waitForSelector('.qrow', { timeout: 30000 });
  await openPaste(page);
  await page.fill('#sc-qpaste', 'Jonah Coleman | 2025 Prizm Draft Picks | 169 | | NM | 1 | 8 | sports');
  await page.click('#sc-qfill');
  await page.waitForTimeout(250);

  await page.reload({ waitUntil: 'load' });
  await page.waitForTimeout(400);
  check(await queue() === 1, 'the queue should survive a reload, got ' + await queue());
  check(await stock() === 1, 'a reload must not push queued cards into My cards');
  const kept = await page.evaluate(() => SC_QUEUE[0]);
  check(kept.n === 'Jonah Coleman', 'the details should survive a reload, got ' + kept.n);
  check(!!kept.thumb && kept.thumb.startsWith('data:image'), 'the thumbnail should survive a reload');
  check(await page.locator('.qrow').count() === 1, 'the queue should render after a reload');

  /* the full-size picture is session-only, and the page should say so */
  check(await page.isVisible('#sc-lost'), 'should warn that the full-size picture did not survive');
  const saveOff = await page.evaluate(() =>
    [...document.querySelectorAll('.qacts .btn2')].find(x => x.textContent === 'Save crop').disabled);
  check(saveOff, 'Save crop should be off when the full-size picture is gone');
  check(!(await confirmOff()), 'a reloaded row with a name and no flags should still confirm');

  check(jsErrors.length === 0, 'js errors: ' + jsErrors.join(' | '));

  await browser.close();
  fs.unlinkSync(SCAN);

  if (fails.length) {
    console.error('FAILED -- ' + fails.length + ':');
    fails.forEach(f => console.error('  ' + f));
    process.exit(1);
  }
  console.log('ok -- review queue: capture, flag, confirm, persist; nothing reaches My cards unconfirmed');
})().catch(e => { console.error('FAILED', e); process.exit(1); });
