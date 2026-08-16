/* The review queue's contract, end to end in a real browser.

   Build first, then run:
     python build_all.py . card-run-hq.html
     node test_queue.cjs

   Two rules hold the design up.

   One: a dropped card is captured immediately but goes nowhere on its own.
   It is not inventory until it has been through the workbook.

   Two: what the page hands over has to be exactly what file_batch.py expects
   -- the right field names, and a photo count per card that matches the
   pictures actually downloaded. If those drift, photos land on the wrong
   cards, and a wrong picture on a live listing is a return rather than a
   typo. So the batch file is checked field by field here.

   Needs a scan to drop, so it makes one.                                    */

process.env.NODE_PATH = require('child_process').execSync('npm root -g').toString().trim();
require('module').Module._initPaths();

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { execFileSync } = require('child_process');

const PAGE = 'card-run-hq.html';
const SCAN = path.join(os.tmpdir(), 'crh_test_scan.png');
const SCAN4 = path.join(os.tmpdir(), 'crh_test_scan4.png');

const fails = [];
const check = (ok, msg) => { if (!ok) fails.push(msg); };

/* Cards on a pale sheet, with grain on it. The grain is not decoration: a
   clean synthetic page hides the whole class of bug where the edge threshold
   is a share of the page rather than a judgement, and that bug shipped here
   once already. */
function makeScan(n, dest){
  n = n || 1;
  dest = dest || SCAN;
  const spots = [[300, 300], [1400, 300], [300, 1700], [1400, 1700]].slice(0, n);
  execFileSync('python', ['-c', `
import numpy as np, cv2
page = np.full((3300,2550,3), 246, np.uint8)
page = (page + np.random.default_rng(0).normal(0,2,page.shape)).clip(0,255).astype(np.uint8)
for i, (x, y) in enumerate(${JSON.stringify(spots)}):
    card = np.full((1050,750,3), 60, np.uint8)
    card[60:990, 60:690] = (200 - i*20, 170, 90 + i*20)
    cv2.rectangle(card,(0,0),(749,1049),(30,30,30),6)
    page[y:y+1050, x:x+750] = card
cv2.imwrite(r"${dest.replace(/\\/g, '\\\\')}", page)
`]);
}

async function openPaste(page){
  await page.evaluate(() => {
    const d = document.getElementById('sc-qpaste').closest('details');
    if (d && !d.open) d.querySelector('summary').click();
  });
  await page.waitForTimeout(120);
}

/* collect every file the page hands over during fn() */
async function catchDownloads(page, fn){
  const got = [];
  const on = async d => {
    got.push({ name: d.suggestedFilename(), path: await d.path() });
  };
  page.on('download', on);
  await fn();
  await page.waitForTimeout(1200);
  page.off('download', on);
  return got;
}

(async () => {
  if (!fs.existsSync(PAGE)) {
    console.error('no ' + PAGE + ' -- run: python build_all.py . ' + PAGE);
    process.exit(1);
  }
  makeScan(1, SCAN);
  makeScan(4, SCAN4);

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1500, height: 1000 },
                                         acceptDownloads: true });
  const page = await ctx.newPage();
  const jsErrors = [];
  page.on('pageerror', e => jsErrors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') jsErrors.push('console: ' + m.text()); });

  const url = 'file:///' + path.resolve(PAGE).replace(/\\/g, '/');
  await page.goto(url, { waitUntil: 'load' });

  const scratch = () => page.evaluate(() => CD_STOCK.length);
  const queue = () => page.evaluate(() => SC_QUEUE.length);
  const confirmOff = () => page.evaluate(() =>
    document.getElementById('sc-qconfirm').disabled);
  const saveOff = () => page.evaluate(() =>
    document.getElementById('sc-tofile').disabled);

  check(await scratch() === 0, 'the scratchpad should start empty in a fresh profile');

  /* --- capture ---------------------------------------------------------- */
  await page.setInputFiles('#sc-file', SCAN);
  await page.waitForSelector('.qrow', { timeout: 30000 });
  await page.waitForTimeout(300);

  check(await queue() === 1, 'the dropped card should be on the queue');
  check(await page.isVisible('#sc-qwrap'), 'the queue should appear');
  check(await confirmOff(), 'Confirm should be off while the card has no name');
  check(await saveOff(), 'Save for the workbook should be off with nothing checked');

  /* --- an unsure field blocks confirming --------------------------------- */
  await openPaste(page);
  await page.fill('#sc-qpaste',
    'Shedeur Sanders | 2025 Panini Prizm Draft Picks | 8 | ?Gold Cracked Ice | NM | 1 | 12.50 | sports');
  await page.click('#sc-qfill');
  await page.waitForTimeout(250);

  const filled = await page.evaluate(() => SC_QUEUE[0]);
  check(filled.n === 'Shedeur Sanders', 'name did not come through: ' + filled.n);
  check(filled.var === 'Gold Cracked Ice', 'the ? should be stripped off the value');
  check(filled.v === 12.5, 'worth did not parse, got ' + filled.v);
  check(filled.c === 'Near Mint or Better',
        'NM should map to the workbook wording, got ' + filled.c);
  check(filled.kind === 'Sports', 'category did not parse, got ' + filled.kind);
  check(JSON.stringify(filled.flags) === '["var"]', 'flags should be ["var"]');
  check(await page.locator('.qrow .qfields .unsure').count() === 1, 'the unsure field should be amber');
  check(await confirmOff(), 'CONFIRM WAS ON WHILE A FIELD WAS STILL UNSURE');

  await page.click('.unsurebtn');
  await page.waitForTimeout(200);
  check(!(await confirmOff()), 'Confirm should be on once nothing is unsure');

  /* --- confirming is a tick, not a filing -------------------------------- */
  await page.click('#sc-qconfirm');
  await page.waitForTimeout(300);
  check(await page.evaluate(() => !!SC_QUEUE[0].ok), 'the card should be marked checked');
  check(await scratch() === 0,
        'A CHECKED CARD REACHED THE SCRATCHPAD -- confirming must not file anything');
  check(await queue() === 1, 'a checked card stays on the queue until it is saved');
  check(!(await saveOff()), 'Save for the workbook should be on once something is checked');

  /* --- the handover to file_batch.py ------------------------------------- */
  const got = await catchDownloads(page, () => page.click('#sc-tofile'));
  const pics = got.filter(g => /\.jpg$/i.test(g.name));
  const batch = got.find(g => g.name === 'batch.json');

  check(pics.length === 1, 'should have handed over 1 picture, got ' + pics.length);
  check(pics[0] && pics[0].name === 'crh-001.jpg',
        'pictures must be numbered so filename order is queue order, got '
        + (pics[0] && pics[0].name));
  check(!!batch, 'no batch.json was handed over');

  if (batch) {
    const b = JSON.parse(fs.readFileSync(batch.path, 'utf8'));
    check(Array.isArray(b.cards) && b.cards.length === 1,
          'batch.json should hold 1 card, got ' + JSON.stringify(b).slice(0, 120));
    const c = b.cards[0];
    check(c.player === 'Shedeur Sanders', 'player: ' + c.player);
    check(c.brand === '2025 Panini Prizm Draft Picks', 'brand: ' + c.brand);
    check(c.num === '8', 'num: ' + c.num);
    check(c.parallel === 'Gold Cracked Ice', 'parallel: ' + c.parallel);
    check(c.condition === 'Near Mint or Better', 'condition: ' + c.condition);
    check(c.category === 'Sports', 'category: ' + c.category);
    check(c.qty === 1, 'qty: ' + c.qty);
    check(c.market === 12.5, 'market: ' + c.market);
    check(c.photos === 1, 'PHOTO COUNT MUST MATCH THE PICTURES SENT, got ' + c.photos);
    check(!c.unsure, 'nothing was left unsure, so unsure should be absent: ' + JSON.stringify(c.unsure));

    /* every key must be one file_batch.py accepts, or it exits rather than files */
    const known = ['player', 'year', 'brand', 'insert', 'parallel', 'num', 'serial',
                   'team', 'sport', 'league', 'category', 'condition', 'grader',
                   'grade', 'cert', 'qty', 'cost', 'market', 'ask', 'source', 'lot',
                   'notes', 'rc', 'auto', 'relic', 'unsure', 'photos'];
    const stray = Object.keys(c).filter(k => known.indexOf(k) < 0);
    check(stray.length === 0, 'batch.json has field(s) file_batch.py rejects: ' + stray);
  }

  check(await page.evaluate(() => !!SC_QUEUE[0].filed), 'a saved card should be marked saved');
  await page.click('#sc-clearfiled');
  await page.waitForTimeout(250);
  check(await queue() === 0, 'Clear saved should take the saved card off the queue');

  /* --- a card with no worth is handed over as unsure ---------------------- */
  await page.setInputFiles('#sc-file', SCAN);
  await page.waitForSelector('.qrow', { timeout: 30000 });
  await page.waitForTimeout(300);
  await openPaste(page);
  await page.fill('#sc-qpaste', 'Jonah Coleman | 2025 Panini Prizm Draft Picks | 169 | | NM | 1 | | sports');
  await page.click('#sc-qfill');
  await page.waitForTimeout(250);
  await page.click('#sc-qconfirm');
  await page.waitForTimeout(250);
  const got2 = await catchDownloads(page, () => page.click('#sc-tofile'));
  const b2 = got2.find(g => g.name === 'batch.json');
  if (b2) {
    const c = JSON.parse(fs.readFileSync(b2.path, 'utf8')).cards[0];
    check(Array.isArray(c.unsure) && c.unsure.indexOf('market') >= 0,
          'a card with no worth must be flagged unsure so it files as Review, got '
          + JSON.stringify(c.unsure));
    check(c.market === undefined, 'no worth means no market value, got ' + c.market);
  }
  await page.click('#sc-clearfiled');
  await page.waitForTimeout(250);

  /* --- typing the shared bits once --------------------------------------- */
  await page.evaluate(() => { SC_QUEUE = []; SC_BATCH = {}; scQSave(); render(); });
  await page.setInputFiles('#sc-file', SCAN);
  await page.waitForSelector('.qrow', { timeout: 30000 });
  await page.waitForTimeout(300);

  await page.evaluate(() => {
    SC_BATCH = { year: '2025', s: 'Panini Prizm Draft Picks', insert: 'Student Orientation',
                 team: 'Colorado Buffaloes', league: 'NCAA', sport: 'Football',
                 kind: 'Sports', c: 'Excellent', source: 'Target Upland', lot: 'LOT-001' };
    SC_QUEUE[0].n = 'Shedeur Sanders'; SC_QUEUE[0].num = '8'; SC_QUEUE[0].v = 12.5;
    SC_QUEUE[0].flags = [];
    scQSave(); render();
  });
  await page.click('#sc-qconfirm');
  await page.waitForTimeout(250);
  const gotB = await catchDownloads(page, () => page.click('#sc-tofile'));
  const bB = gotB.find(g => g.name === 'batch.json');
  if (bB) {
    const c = JSON.parse(fs.readFileSync(bB.path, 'utf8')).cards[0];
    check(c.year === '2025', 'year should be inherited from the batch, got ' + c.year);
    check(c.brand === 'Panini Prizm Draft Picks', 'brand inherited: ' + c.brand);
    check(c.insert === 'Student Orientation', 'insert inherited: ' + c.insert);
    check(c.team === 'Colorado Buffaloes', 'team inherited: ' + c.team);
    check(c.league === 'NCAA', 'league inherited: ' + c.league);
    check(c.sport === 'Football', 'sport inherited: ' + c.sport);
    check(c.source === 'Target Upland', 'source inherited: ' + c.source);
    check(c.lot === 'LOT-001', 'lot inherited: ' + c.lot);
    check(c.condition === 'Excellent', 'condition inherited: ' + c.condition);
    check(c.player === 'Shedeur Sanders' && c.num === '8', 'the per-card bits should survive');
  }
  await page.click('#sc-clearfiled');
  await page.waitForTimeout(250);

  /* a value typed on the card beats the batch */
  await page.setInputFiles('#sc-file', SCAN);
  await page.waitForSelector('.qrow', { timeout: 30000 });
  await page.waitForTimeout(300);
  await page.evaluate(() => {
    SC_QUEUE[0].n = 'Jonah Coleman'; SC_QUEUE[0].num = '169'; SC_QUEUE[0].v = 6;
    SC_QUEUE[0].s = '2025 Panini Prizm Draft Picks Base';   /* override */
    SC_QUEUE[0].c = 'Poor';                                  /* override */
    SC_QUEUE[0].flags = []; scQSave(); render();
  });
  await page.click('#sc-qconfirm');
  await page.waitForTimeout(250);
  const gotO = await catchDownloads(page, () => page.click('#sc-tofile'));
  const bO = gotO.find(g => g.name === 'batch.json');
  if (bO) {
    const c = JSON.parse(fs.readFileSync(bO.path, 'utf8')).cards[0];
    check(c.brand === '2025 Panini Prizm Draft Picks Base',
          'A CARD\'S OWN SET MUST BEAT THE BATCH, got ' + c.brand);
    check(c.condition === 'Poor', 'a card\'s own condition must win, got ' + c.condition);
    check(c.year === '2025', 'unset fields still inherit, got ' + c.year);
  }
  await page.click('#sc-clearfiled');
  await page.waitForTimeout(250);

  /* --- editing a checked card un-checks it -------------------------------- */
  await page.setInputFiles('#sc-file', SCAN);
  await page.waitForSelector('.qrow', { timeout: 30000 });
  await page.waitForTimeout(300);
  await page.evaluate(() => {
    SC_QUEUE[0].n = 'Travis Hunter'; SC_QUEUE[0].num = '3'; SC_QUEUE[0].v = 30;
    SC_QUEUE[0].flags = []; scQSave(); render();
  });
  await page.click('#sc-qconfirm');
  await page.waitForTimeout(250);
  check(await page.evaluate(() => !!SC_QUEUE[0].ok), 'should be checked before the edit');

  await page.locator('.qrow .qfields input').first().fill('Travis Hunter Jr');
  await page.waitForTimeout(300);
  check(await page.evaluate(() => !SC_QUEUE[0].ok),
        'EDITING A CHECKED CARD MUST UN-CHECK IT, or "checked" means nothing');
  check(await saveOff(), 'Save should go off again once nothing is checked');

  /* --- the audit ---------------------------------------------------------- */
  const warn = () => page.locator('.qwarn').first().textContent();
  await page.evaluate(() => {
    SC_BATCH = {}; SC_QUEUE[0].s = ''; SC_QUEUE[0].num = ''; SC_QUEUE[0].v = 0;
    scQSave(); render();
  });
  await page.waitForTimeout(250);
  const w1 = await warn();
  check(/no set or brand/.test(w1), 'should warn about a missing set: ' + w1);
  check(/no card number/.test(w1), 'should warn about a missing number: ' + w1);
  check(/no worth/.test(w1), 'should warn that it will file as Review: ' + w1);
  check(/no year/.test(w1), 'should warn about a missing year: ' + w1);

  /* two rows that are the same card -- usually a front and back come apart */
  await page.setInputFiles('#sc-file', SCAN);
  await page.waitForTimeout(2500);
  await page.evaluate(() => {
    SC_QUEUE.forEach(e => { e.n = 'Shedeur Sanders'; e.s = 'Prizm'; e.num = '8'; e.var = 'Gold'; });
    scQSave(); render();
  });
  await page.waitForTimeout(250);
  const w2 = await page.locator('.qwarn').allTextContents();
  check(w2.some(t => /same card as/.test(t)),
        'two identical rows should be flagged as a possible split front/back: ' + w2.join(' | '));

  await page.evaluate(() => { SC_QUEUE = []; SC_BATCH = {}; scQSave(); render(); });

  /* --- a card logged now, photographed later ------------------------------ */
  await page.evaluate(() => { SC_QUEUE = []; SC_BATCH = {}; scQSave(); render(); });
  await page.click('#sc-blank');
  await page.waitForTimeout(300);
  check(await page.locator('.qrow').count() === 1, 'the blank card should be a row');
  check(await page.locator('.noshot').count() === 1, 'it should show a "no picture" placeholder');
  check(await page.locator('.qacts').first().locator('button').nth(1).textContent()
        === 'Add picture', 'a card with no picture should offer Add picture');

  await page.evaluate(() => {
    SC_BATCH = { year: '2025', s: 'Panini Prizm', sport: 'Football', kind: 'Sports' };
    SC_QUEUE[0].n = 'Travis Hunter'; SC_QUEUE[0].num = '3'; SC_QUEUE[0].v = 40;
    scQSave(); render();
  });
  await page.click('#sc-qconfirm');
  await page.waitForTimeout(250);
  const gotN = await catchDownloads(page, () => page.click('#sc-tofile'));
  check(gotN.filter(g => /\.jpg$/i.test(g.name)).length === 0,
        'a card with no picture should hand over no pictures');
  const bN = gotN.find(g => g.name === 'batch.json');
  if (bN) {
    const c = JSON.parse(fs.readFileSync(bN.path, 'utf8')).cards[0];
    check(c.photos === 0, 'photos must be 0 so file_batch.py expects none, got ' + c.photos);
    check(c.player === 'Travis Hunter' && c.year === '2025',
          'the typed card should still carry its details and the batch ones');
  }

  /* attaching the picture later replaces the placeholder rather than adding a card */
  await page.evaluate(() => { SC_QUEUE = []; SC_BATCH = {}; scQSave(); render(); });
  await page.click('#sc-blank');
  await page.waitForTimeout(250);
  await page.locator('.qacts').first().getByText('Add picture').click();
  await page.setInputFiles('#sc-add', SCAN);
  await page.waitForTimeout(3000);
  check(await page.locator('.qrow').count() === 1,
        'adding the picture later must not make a second card');
  check(await page.locator('.noshot').count() === 0, 'the placeholder should be gone');
  check(await page.evaluate(() => SC_QUEUE.length) === 1,
        'the empty stand-in should have been dropped, got ' + await page.evaluate(() => SC_QUEUE.length));

  await page.evaluate(() => { SC_QUEUE = []; SC_BATCH = {}; scQSave(); render(); });

  /* --- persistence ------------------------------------------------------- */
  await page.setInputFiles('#sc-file', SCAN);
  await page.waitForSelector('.qrow', { timeout: 30000 });
  await page.evaluate(() => { SC_QUEUE[0].n = 'Travis Hunter'; scQSave(); });
  await page.reload({ waitUntil: 'load' });
  await page.waitForTimeout(400);
  check(await queue() === 1, 'the queue should survive a reload');
  check(await page.evaluate(() => SC_QUEUE[0].n) === 'Travis Hunter',
        'the details should survive a reload');
  check(await page.isVisible('#sc-lost'), 'should warn that the full-size picture is gone');

  /* --- front and back ---------------------------------------------------- */
  const p2 = await ctx.newPage();
  p2.on('pageerror', e => jsErrors.push('pageerror(pairs): ' + e.message));
  p2.on('console', m => { if (m.type() === 'error') jsErrors.push('console(pairs): ' + m.text()); });
  await p2.goto(url, { waitUntil: 'load' });
  const clear = () => p2.evaluate(() => { SC_QUEUE = []; SC_PAIRS = false; scQSave(); render(); });

  await clear();
  await p2.setInputFiles('#sc-file', SCAN4);
  await p2.waitForSelector('.qrow', { timeout: 40000 });
  await p2.waitForTimeout(400);
  check(await p2.evaluate(() => SC_QUEUE.length) === 4, 'the 4-card sheet should give 4 pictures');
  check(await p2.locator('.qrow').count() === 4, 'unpaired, 4 pictures should be 4 rows');

  await p2.check('#sc-pairs');
  await p2.waitForTimeout(300);
  check(await p2.locator('.qrow').count() === 2, 'PAIRED, 4 PICTURES SHOULD BE 2 CARDS');
  check(await p2.locator('.qshot').count() === 4, 'each paired row should show both sides');

  await openPaste(p2);
  await p2.fill('#sc-qpaste',
    'Shedeur Sanders | 2025 Panini Prizm Draft Picks | 8 | Gold Cracked Ice | NM | 1 | 12.50 | sports\n' +
    'Jonah Coleman | 2025 Panini Prizm Draft Picks | 169 | Gold Cracked Ice | NM | 1 | 6 | sports');
  await p2.click('#sc-qfill');
  await p2.waitForTimeout(300);
  const names = await p2.evaluate(() => SC_QUEUE.map(e => e.n));
  check(names[0] === 'Shedeur Sanders' && names[2] === 'Jonah Coleman',
        'a line per card should land on the FRONT of each pair, got ' + JSON.stringify(names));
  check(names[1] === '' && names[3] === '', 'a back is not a card of its own');

  await p2.click('#sc-qconfirm');
  await p2.waitForTimeout(300);
  const got3 = await catchDownloads(p2, () => p2.click('#sc-tofile'));
  const pics3 = got3.filter(g => /\.jpg$/i.test(g.name));
  const b3 = got3.find(g => g.name === 'batch.json');
  check(pics3.length === 4, 'a paired batch should hand over 4 pictures, got ' + pics3.length);
  check(pics3.map(g => g.name).join(',') === 'crh-001.jpg,crh-002.jpg,crh-003.jpg,crh-004.jpg',
        'pictures must be numbered front, back, front, back: ' + pics3.map(g => g.name));
  if (b3) {
    const cards = JSON.parse(fs.readFileSync(b3.path, 'utf8')).cards;
    check(cards.length === 2, 'a paired batch is 2 cards, got ' + cards.length);
    check(cards.every(c => c.photos === 2),
          'each paired card should claim 2 photos, got ' + cards.map(c => c.photos));
    check(cards.reduce((a, c) => a + c.photos, 0) === pics3.length,
          'THE PHOTO COUNTS MUST ADD UP TO THE PICTURES SENT');
  }

  /* --- two sides, whatever order they arrive in -------------------------- */
  const p3 = await ctx.newPage();
  p3.on('pageerror', e => jsErrors.push('pageerror(join): ' + e.message));
  p3.on('console', m => { if (m.type() === 'error') jsErrors.push('console(join): ' + m.text()); });
  await p3.goto(url, { waitUntil: 'load' });
  const clear3 = () => p3.evaluate(() => { SC_QUEUE = []; SC_PAIRS = false; scQSave(); render(); });

  await clear3();
  await p3.setInputFiles('#sc-file', SCAN);
  await p3.waitForSelector('.qrow', { timeout: 30000 });
  await p3.waitForTimeout(300);
  await p3.locator('.qacts').first().getByText('Add back').click();
  await p3.setInputFiles('#sc-add', SCAN);
  await p3.waitForTimeout(3000);
  check(await p3.evaluate(() => SC_QUEUE.length) === 2, 'the back should be added as a picture');
  check(await p3.locator('.qrow').count() === 1,
        'ADD BACK MADE A SECOND CARD instead of a second picture on the same one');
  check(await p3.locator('.qrow').first().locator('.qshot').count() === 2,
        'both sides should show on the card');

  await clear3();
  await p3.setInputFiles('#sc-file', SCAN);
  await p3.waitForSelector('.qrow', { timeout: 30000 });
  await p3.waitForTimeout(2000);
  await p3.setInputFiles('#sc-file', SCAN);
  await p3.waitForTimeout(3000);
  check(await p3.locator('.qrow').count() === 2, 'two separate uploads start as two cards');
  await p3.locator('.qrow').nth(1).getByText('Join to 1').click();
  await p3.waitForTimeout(300);
  check(await p3.locator('.qrow').count() === 1, 'JOIN DID NOT MERGE the two into one card');
  await p3.locator('.qacts').first().getByText('Split').click();
  await p3.waitForTimeout(300);
  check(await p3.locator('.qrow').count() === 2, 'split should give two cards back');

  check(jsErrors.length === 0, 'js errors: ' + jsErrors.join(' | '));

  await browser.close();
  fs.unlinkSync(SCAN);
  fs.unlinkSync(SCAN4);

  if (fails.length) {
    console.error('FAILED -- ' + fails.length + ':');
    fails.forEach(f => console.error('  ' + f));
    process.exit(1);
  }
  console.log('ok -- review queue: capture, flag, check, hand over to the workbook; '
            + 'nothing files itself, and batch.json matches the pictures sent');
})().catch(e => { console.error('FAILED', e); process.exit(1); });
