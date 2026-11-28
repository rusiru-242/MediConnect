/**
 * R04 screenshot capture for the README (current R01 branding): the fraud review dialog and a support ticket.
 * Real admin web (127.0.0.1:5174) against the local UAT backend; synthetic data only; no decision is submitted.
 *   node docs/uat/release-preparation/r04/browser_capture_r04.mjs <playwright-core> <out-dir>
 * Requests to any other host are aborted. The UAT password is read from backend/uat.env and never printed.
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const [pwPath, outDir] = process.argv.slice(2);
const { chromium } = createRequire(import.meta.url)(pwPath);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
const PASSWORD = /^UAT_PASSWORD=(.*)$/m.exec(fs.readFileSync(path.join(ROOT, 'backend', 'uat.env'), 'utf8'))[1].trim();
const APP = 'http://127.0.0.1:5174';
const ALLOWED = new Set(['127.0.0.1:5174', '127.0.0.1:8001']);
fs.mkdirSync(outDir, { recursive: true });
const blocked = [];

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 950 } });
await context.route('**/*', (r) => {
  const u = new URL(r.request().url());
  if (u.protocol === 'data:' || u.protocol === 'blob:' || ALLOWED.has(u.host)) return r.continue();
  blocked.push(u.host);
  return r.abort();
});
const page = await context.newPage();
await page.goto(`${APP}/login`);
await page.locator('input[type="email"]').fill('uat.admin@uat.mediconnect.lk');
await page.locator('input[type="password"]').fill(PASSWORD);
await page.locator('button[type="submit"]').click();
await page.waitForURL(/dashboard/, { timeout: 20000 });

await page.goto(`${APP}/fraud-monitoring`);
await page.waitForTimeout(2500);
await page.getByText('Fraud Risk Center', { exact: false }).last().click();
await page.waitForTimeout(1500);
await page.getByRole('button', { name: 'Review' }).first().click();
await page.waitForTimeout(1500);
await page.screenshot({ path: path.join(outDir, 'r04_b01_fraud_review.png') });
await page.keyboard.press('Escape');

await page.goto(`${APP}/support-tickets`);
await page.waitForTimeout(2500);
const row = page.locator('tbody tr, [role="row"], li').filter({ hasText: 'TCK-' }).first();
if (await row.count()) { await row.click(); await page.waitForTimeout(2000); }
await page.screenshot({ path: path.join(outDir, 'r04_b02_support_ticket.png') });
console.log('captured; blocked', blocked.length);
await browser.close();
