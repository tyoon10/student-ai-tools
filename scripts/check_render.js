/**
 * Render check for the published offer grid.
 *
 * Two rendering bugs shipped before this existed, and neither was visible from
 * the generated markup:
 *   1. .markdown-body img (0,1,1) outranked the logo rule, so every logo
 *      rendered at intrinsic size.
 *   2. A blank line inside <script> ended markdown's raw-HTML block, closing the
 *      tag early and letting smartypants rewrite quotes, which threw a syntax
 *      error and left the filters inert.
 *   3. The site never loads its box-sizing reset, so padding and border were
 *      added on top of height:100% and every card overlapped the row below.
 *
 * Checking that the markup exists proves none of these. Only a browser does.
 *
 *   npm install playwright && npx playwright install chromium
 *   node scripts/check_render.js [url]
 */
const { chromium } = require('playwright');

const URL = process.argv[2] || 'https://twyoon.com/writings/student-ai-tools';
const fail = [];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const jsErrors = [];
  page.on('pageerror', e => jsErrors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') jsErrors.push(m.text()); });
  await page.goto(URL, { waitUntil: 'networkidle' });

  if (jsErrors.length) fail.push(`JS errors: ${jsErrors.join(' | ')}`);

  const logo = await page.locator('.offercard__logo').first().boundingBox();
  if (Math.round(logo.width) !== 32 || Math.round(logo.height) !== 32)
    fail.push(`logo is ${Math.round(logo.width)}x${Math.round(logo.height)}, expected 32x32`);

  if (!(await page.locator('.offergrid__controls').isVisible()))
    fail.push('filter controls are not visible');

  const geom = await page.evaluate(() => {
    const cards = [...document.querySelectorAll('.offercard')].map(li => ({
      name: li.querySelector('.offercard__name').textContent.trim(),
      li: li.getBoundingClientRect(), a: li.querySelector('a').getBoundingClientRect(),
    }));
    const spill = cards.filter(c => c.a.height > c.li.height + 1).map(c => c.name);
    const overlaps = [];
    for (let i = 0; i < cards.length; i++)
      for (let j = i + 1; j < cards.length; j++) {
        const A = cards[i].a, B = cards[j].a;
        if (Math.min(A.right, B.right) - Math.max(A.left, B.left) > 1 &&
            Math.min(A.bottom, B.bottom) - Math.max(A.top, B.top) > 1)
          overlaps.push(`${cards[i].name} x ${cards[j].name}`);
      }
    return { n: cards.length, spill, overlaps };
  });
  if (geom.spill.length) fail.push(`content overflows its card: ${geom.spill.slice(0, 4).join(', ')}`);
  if (geom.overlaps.length) fail.push(`cards overlap: ${geom.overlaps.slice(0, 4).join(', ')}`);

  const shown = () => page.evaluate(() =>
    [...document.querySelectorAll('.offercard')].filter(c => !c.hidden).length);
  const total = await shown();
  await page.locator('[data-filter="coding"]').click();
  const filtered = await shown();
  if (filtered === total || filtered === 0) fail.push(`category filter did nothing (${total} -> ${filtered})`);
  await page.locator('[data-filter="all"]').click();
  await page.locator('input[data-search]').fill('notion');
  await page.waitForTimeout(120);
  if (await shown() !== 1) fail.push(`search for "notion" matched ${await shown()}, expected 1`);
  await page.locator('input[data-search]').fill('');
  await page.locator('input[data-free]').check();
  await page.waitForTimeout(120);
  const free = await shown();
  if (free === 0 || free === total) fail.push(`free-only filter did nothing (${free}/${total})`);

  await browser.close();
  if (fail.length) {
    console.error('RENDER CHECK FAILED');
    fail.forEach(f => console.error('  - ' + f));
    process.exit(1);
  }
  console.log(`render check passed: ${geom.n} cards, no overlap, filters working`);
})();
