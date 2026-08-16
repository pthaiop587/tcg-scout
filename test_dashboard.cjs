/* Smoke test for the built dashboard.

   Build first, then run:
     python build_all.py . card-run-hq.html
     node test_dashboard.cjs

   This exists because the page is one 6 MB generated file with twenty-odd
   panels in it, and the failures that matter are the silent ones -- a script
   error on a tab nobody opened, an id used twice so getElementById quietly
   returns the wrong element, a section that renders empty, a bookmark that
   stopped resolving after a reshuffle. None of those show up in a diff.        */

process.env.NODE_PATH = require('child_process').execSync('npm root -g').toString().trim();
require('module').Module._initPaths();

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const PAGE = 'card-run-hq.html';

/* Every hash that has ever been a tab. They must all still resolve, because
   the runbook tells you to bookmark them and several are linked in-page. A
   section that became a fold keeps its id, so the router finds it either way. */
const HASHES = ['add', 'sell', 'sheet', 'shelf', 'pc', 'log', 'map', 'ref',
                'src', 'learn', 'types', 'boxes', 'chase', 'shops', 'plan',
                'rules', 'chan', 'sport'];

const fails = [];
const check = (ok, msg) => { if (!ok) fails.push(msg); };

(async () => {
  if (!fs.existsSync(PAGE)) {
    console.error('no ' + PAGE + ' -- run: python build_all.py . ' + PAGE);
    process.exit(1);
  }

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  const jsErrors = [];
  page.on('pageerror', e => jsErrors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') jsErrors.push('console: ' + m.text()); });

  const url = 'file:///' + path.resolve(PAGE).replace(/\\/g, '/');
  await page.goto(url, { waitUntil: 'load' });

  /* opens on the tab the day starts with */
  const open = await page.evaluate(() =>
    [...document.querySelectorAll('[role="tabpanel"]')].filter(p => !p.hidden).map(p => p.id));
  check(open.length === 1, 'expected exactly one visible panel on load, got ' + open.length);
  check(open[0] === 'p-add', 'should open on Card desk, opened on ' + open[0]);

  /* every tab renders something, and exactly one at a time */
  const tabs = await page.evaluate(() =>
    [...document.querySelectorAll('[role="tab"]')].map(t => ({ id: t.id, panel: t.getAttribute('aria-controls') })));
  check(tabs.length <= 10, 'sidebar is back over 10 tabs (' + tabs.length + ') -- it was cut to 8 for a reason');

  for (const t of tabs) {
    await page.click('#' + t.id);
    await page.waitForTimeout(40);
    const r = await page.evaluate(pid => {
      const p = document.getElementById(pid);
      const vis = [...document.querySelectorAll('[role="tabpanel"]')].filter(x => !x.hidden);
      return { chars: p ? p.innerText.trim().length : -1, visible: vis.length };
    }, t.panel);
    check(r.chars > 40, t.panel + ' renders empty (' + r.chars + ' chars)');
    check(r.visible === 1, t.panel + ': ' + r.visible + ' panels visible at once');
  }

  /* duplicate ids: getElementById takes the first, so the second silently dies */
  const dupes = await page.evaluate(() => {
    const seen = new Set(), dup = new Set();
    document.querySelectorAll('[id]').forEach(e => seen.has(e.id) ? dup.add(e.id) : seen.add(e.id));
    return [...dup];
  });
  check(dupes.length === 0, 'duplicate ids: ' + dupes.join(', '));

  /* every documented bookmark still lands somewhere */
  for (const h of HASHES) {
    await page.goto(url + '#' + h);
    await page.waitForTimeout(80);
    const r = await page.evaluate(hash => {
      const vis = [...document.querySelectorAll('[role="tabpanel"]')].filter(p => !p.hidden);
      const el = document.getElementById(hash);
      return { n: vis.length, fold: el && el.tagName === 'DETAILS' ? el.open : null };
    }, h);
    check(r.n === 1, '#' + h + ' shows ' + r.n + ' panels');
    check(r.fold !== false, '#' + h + ' is a fold that did not open');
  }

  /* the scan drop zone is wired up and starts clean */
  await page.goto(url);
  check(await page.isVisible('#sc-drop'), 'scan drop zone missing from Card desk');
  check(!(await page.isVisible('#sc-tools')), 'crop buttons show before anything is dropped');

  check(jsErrors.length === 0, 'js errors: ' + jsErrors.join(' | '));

  await browser.close();

  if (fails.length) {
    console.error('FAILED -- ' + fails.length + ':');
    fails.forEach(f => console.error('  ' + f));
    process.exit(1);
  }
  console.log('ok -- dashboard: ' + tabs.length + ' tabs, ' + HASHES.length +
              ' bookmarks, no js errors, no duplicate ids');
})().catch(e => { console.error('FAILED', e); process.exit(1); });
