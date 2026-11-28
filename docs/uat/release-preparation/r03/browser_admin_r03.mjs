/**
 * R03 admin browser verification in the real admin web app (Vite dev server 127.0.0.1:5174) against the local UAT
 * backend (127.0.0.1:8001, mediconnect_uat), in headless Chrome through playwright-core.
 *
 *   node docs/uat/release-preparation/r03/browser_admin_r03.mjs <playwright-core> <out-dir> <patient user id>
 *
 * For every page: screenshot, heading, page errors, error-boundary text, and whether a storage path, token or
 * profile-image file path is visible in the DOM. All picture requests are recorded; a request for the patient's
 * picture would be a privacy failure. A patient account must not get into the admin app.
 * Safety: requests to any host other than 127.0.0.1:5174 / 127.0.0.1:8001 are aborted and recorded. The UAT password
 * is read from backend/uat.env and never printed.
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const [pwPath, outDir, patientId] = process.argv.slice(2);
const require = createRequire(import.meta.url);
const { chromium } = require(pwPath);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
const PASSWORD = /^UAT_PASSWORD=(.*)$/m.exec(fs.readFileSync(path.join(ROOT, 'backend', 'uat.env'), 'utf8'))[1].trim();
const APP = 'http://127.0.0.1:5174';
const ALLOWED = new Set(['127.0.0.1:5174', '127.0.0.1:8001']);
const shots = path.join(outDir, 'browser');
fs.mkdirSync(shots, { recursive: true });

const PAGES = [
  ['b01', 'dashboard', 'Dashboard'], ['b02', 'doctors', 'Doctor management'],
  ['b03', 'doctor-verification', 'Doctor verification'], ['b04', 'appointments', 'Appointment monitoring'],
  ['b05', 'payments', 'Payment monitoring'], ['b06', 'refunds', 'Refund review'],
  ['b07', 'reconciliation', 'Reconciliation'], ['b08', 'fraud-monitoring', 'Fraud monitoring'],
  ['b09', 'support-tickets', 'Support tickets'], ['b10', 'monitoring', 'System and notification monitoring'],
  ['b11', 'audit-logs', 'Audit logs'], ['b12', 'analytics', 'Analytics'], ['b13', 'reports', 'Reports'],
];
const results = [];
const blocked = [];
const pictureRequests = [];

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 950 } });
await context.route('**/*', (route) => {
  const u = new URL(route.request().url());
  if (u.pathname.startsWith('/api/profile/pictures/')) pictureRequests.push(u.pathname.split('/').pop());
  if (u.protocol === 'data:' || u.protocol === 'blob:' || ALLOWED.has(u.host)) return route.continue();
  blocked.push(u.host);
  return route.abort();
});
const page = await context.newPage();
let errors = [];
page.on('pageerror', (e) => errors.push(e.message));

await page.goto(`${APP}/login`);
await page.locator('input[type="email"]').fill('uat.admin@uat.mediconnect.lk');
await page.locator('input[type="password"]').fill(PASSWORD);
await page.locator('button[type="submit"]').click();
await page.waitForURL(/dashboard/, { timeout: 20000 });

for (const [id, route, name] of PAGES) {
  errors = [];
  await page.goto(`${APP}/${route}`);
  try { await page.waitForLoadState('networkidle', { timeout: 15000 }); } catch { /* long-polling pages */ }
  await page.waitForTimeout(1500);
  if (route === 'doctors') {  // the list is paginated (15 rows); search for the doctor whose picture was uploaded in R03
    const search = page.locator('input[type="search"], input[placeholder*="Search" i]').first();
    if (await search.count()) { await search.fill('UAT Neuro'); await page.waitForTimeout(3000); }
  }
  const info = await page.evaluate(() => {
    const text = document.body.innerText || '';
    return {
      url: location.pathname,
      heading: (document.querySelector('h1, h2')?.textContent || '').trim().slice(0, 80),
      errorBoundary: /something went wrong|unexpected application error|failed to load/i.test(text),
      leaks: ['profile_images', 'uploads/', 'Bearer ', 'mongodb://', 'sk_test_', 'eyJ'].filter((s) => text.includes(s)),
      avatars: document.querySelectorAll('[data-testid="doctor-avatar-image"]').length,
      fallbacks: document.querySelectorAll('[data-testid="doctor-avatar-fallback"]').length,
      textLength: text.length,
    };
  });
  await page.screenshot({ path: path.join(shots, `r03_${id}_${route}.png`) });
  const ok = info.url === `/${route}` && !info.errorBoundary && info.leaks.length === 0 && errors.length === 0;
  results.push({ id, page: name, route, ...info, pageErrors: errors.slice(0, 3), status: ok ? 'PASS' : 'FAIL' });
  console.log(ok ? 'PASS' : 'FAIL', id, name, JSON.stringify(info).slice(0, 220), errors.slice(0, 1));
}

// A patient account must not get into the admin app.
const ctx2 = await browser.newContext({ viewport: { width: 1280, height: 800 } });
await ctx2.route('**/*', (r) => (ALLOWED.has(new URL(r.request().url()).host) ? r.continue() : r.abort()));
const p2 = await ctx2.newPage();
await p2.goto(`${APP}/login`);
await p2.locator('input[type="email"]').fill('uat.patient2@uat.mediconnect.lk');
await p2.locator('input[type="password"]').fill(PASSWORD);
await p2.locator('button[type="submit"]').click();
await p2.waitForTimeout(4000);
await p2.goto(`${APP}/doctors`);
await p2.waitForTimeout(2500);
const patientView = { url: new URL(p2.url()).pathname, sawDoctorTable: (await p2.locator('tbody tr').count()) > 0 };
await p2.screenshot({ path: path.join(shots, 'r03_b14_patient_account_refused.png') });

const patientPictureRequested = pictureRequests.includes(patientId);
const out = {
  at: new Date().toISOString(), pages: results, blockedRequests: blocked, pictureRequests: [...new Set(pictureRequests)],
  patientPictureRequested, patientAccount: { ...patientView, status: !patientView.sawDoctorTable && patientView.url !== '/doctors' ? 'PASS' : 'FAIL' },
};
fs.writeFileSync(path.join(outDir, 'r03_browser_admin.json'), JSON.stringify(out, null, 2));
console.log('patient account', JSON.stringify(out.patientAccount), '| patient picture requested', patientPictureRequested,
  '| blocked', blocked.length);
await browser.close();
