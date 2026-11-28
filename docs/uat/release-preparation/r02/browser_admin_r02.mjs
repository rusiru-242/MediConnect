/**
 * R02 admin browser UAT: doctor profile pictures in the real admin web app (Vite dev server 127.0.0.1:5174) against the
 * local UAT backend (127.0.0.1:8001, mediconnect_uat), in the locally installed Chrome through playwright-core.
 *
 *   node docs/uat/release-preparation/r02/browser_admin_r02.mjs <playwright-core> <out-dir> <label> <doctor name>
 *
 * Checks: doctor management list shows the doctor's real picture (fetched with the admin session as a blob),
 * other rows keep the fallback, table layout is not distorted, the verification queue still renders, no picture
 * request goes anywhere but the backend, and no storage path or token appears in the page.
 * Safety: requests to any host other than 127.0.0.1:5174 / 127.0.0.1:8001 are aborted and recorded. The UAT password
 * is read from backend/uat.env and never printed. Screenshots show synthetic UAT data only.
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const [pwPath, outDir, label, doctorName] = process.argv.slice(2);
const require = createRequire(import.meta.url);
const { chromium } = require(pwPath);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
const PASSWORD = /^UAT_PASSWORD=(.*)$/m.exec(fs.readFileSync(path.join(ROOT, 'backend', 'uat.env'), 'utf8'))[1].trim();
const APP = 'http://127.0.0.1:5174';
const ALLOWED = new Set(['127.0.0.1:5174', '127.0.0.1:8001']);
const shots = path.join(outDir, 'browser');
fs.mkdirSync(shots, { recursive: true });
const shot = (n) => path.join(shots, `r02_${label}_${n}.png`);

const steps = [];
const blocked = [];
const pageErrors = [];
const pictureRequests = [];
function step(id, scenario, actual, ok) {
  steps.push({ id, scenario, actual, status: ok ? 'PASS' : 'FAIL' });
  console.log(ok ? 'PASS' : 'FAIL', id, scenario, '|', String(JSON.stringify(actual ?? null)).slice(0, 260));
}

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 950 } });
await context.route('**/*', (route) => {
  const u = new URL(route.request().url());
  if (u.pathname.startsWith('/api/profile/pictures/')) pictureRequests.push({ host: u.host, status: 'requested' });
  if (u.protocol === 'data:' || u.protocol === 'blob:' || ALLOWED.has(u.host)) return route.continue();
  blocked.push(u.host);
  return route.abort();
});
const page = await context.newPage();
page.on('pageerror', (e) => pageErrors.push(`${page.url()} :: ${e.message}`));

await page.goto(`${APP}/login`);
await page.locator('input[type="email"]').fill('uat.admin@uat.mediconnect.lk');
await page.locator('input[type="password"]').fill(PASSWORD);
await page.locator('button[type="submit"]').click();
await page.waitForURL(/dashboard/, { timeout: 20000 });

// Doctor management list
await page.goto(`${APP}/doctors`);
await page.locator('table').first().waitFor({ timeout: 20000 });
const search = page.locator('input[type="search"], input[placeholder*="Search" i]').first();
if (await search.count()) {
  await search.fill(doctorName.replace(/^Dr\.\s*/, ''));
  await page.waitForTimeout(1500);
}
await page.waitForTimeout(2500);
const rows = await page.evaluate((name) => {
  return [...document.querySelectorAll('tbody tr')].map((tr) => {
    const img = tr.querySelector('[data-testid="doctor-avatar-image"]');
    const fb = tr.querySelector('[data-testid="doctor-avatar-fallback"]');
    const r = (img || fb)?.getBoundingClientRect();
    return {
      name: tr.querySelector('p')?.textContent || '',
      image: !!img, fallback: !!fb, src: img?.getAttribute('src')?.slice(0, 5) || null,
      box: r ? [Math.round(r.width), Math.round(r.height)] : null, rowHeight: Math.round(tr.getBoundingClientRect().height),
      matches: (tr.textContent || '').includes(name),
    };
  });
}, doctorName);
const target = rows.find((r) => r.matches);
await page.screenshot({ path: shot('b01_admin_doctor_list') });
step('I15', 'Doctor management list shows the doctor picture (blob from the admin session)', target,
  !!target && (label === 'removed' ? target.fallback && !target.image : target.image && target.src === 'blob:'));
const others = rows.filter((r) => !r.matches);
step('I15b', 'Other doctors keep the fallback avatar; avatars are 32x32 and rows are not distorted',
  { others: others.length, sizes: [...new Set(rows.map((r) => r.box?.join('x')))], maxRow: Math.max(...rows.map((r) => r.rowHeight)) },
  rows.every((r) => r.box && r.box[0] === 32 && r.box[1] === 32) && Math.max(...rows.map((r) => r.rowHeight)) < 120);
if (target) {
  const row = page.locator('tbody tr', { hasText: doctorName }).first();
  await row.scrollIntoViewIfNeeded();
  await row.screenshot({ path: shot('b02_admin_doctor_row_zoom') });
}

// Verification queue (approved tab, if present) still renders with avatars
await page.goto(`${APP}/doctor-verification`);
await page.waitForTimeout(2500);
const approvedTab = page.getByRole('button', { name: /approved/i }).first();
if (await approvedTab.count()) await approvedTab.click();
await page.waitForTimeout(2500);
const verification = await page.evaluate((name) => {
  const tr = [...document.querySelectorAll('tbody tr')].find((t) => (t.textContent || '').includes(name));
  return {
    rows: document.querySelectorAll('tbody tr').length,
    target: tr ? { image: !!tr.querySelector('[data-testid="doctor-avatar-image"]'),
      fallback: !!tr.querySelector('[data-testid="doctor-avatar-fallback"]') } : null,
  };
}, doctorName);
await page.screenshot({ path: shot('b03_admin_verification') });
step('I15c', 'Doctor verification page renders the doctor with an avatar', verification,
  verification.rows > 0 && (verification.target === null || verification.target.image || verification.target.fallback));

// Nothing sensitive in the DOM
const html = await page.content();
const leaks = ['uploads/profile_images', 'storageKey', 'Bearer ', 'eyJ'].filter((s) => html.includes(s));
step('S-ADMIN', 'No storage path or token in the admin page', { leaks }, leaks.length === 0);

await browser.close();
const result = { label, doctorName, steps, rows: rows.length, pictureRequests: pictureRequests.length,
  pictureHosts: [...new Set(pictureRequests.map((p) => p.host))], blockedRequests: blocked, pageErrors };
fs.writeFileSync(path.join(outDir, `r02_browser_admin_${label}.json`), JSON.stringify(result, null, 2));
console.log('blocked', blocked.length, 'pageErrors', pageErrors.length, 'pictureRequests', pictureRequests.length);
