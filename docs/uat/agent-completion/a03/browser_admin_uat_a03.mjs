/**
 * A03 admin browser UAT: the real admin web app (Vite dev server, 127.0.0.1:5174) against the local UAT backend
 * (127.0.0.1:8001, mediconnect_uat), driven in the locally installed Chrome through playwright-core.
 *
 *   node docs/uat/agent-completion/a03/browser_admin_uat_a03.mjs <playwright-core> <out-dir> <refundId> <reviewRefundId> <appointmentId>
 *
 * refundId: the patient's cancellation refund created on the emulator (approved here, real Stripe test refund).
 * reviewRefundId: the pm_card_refundFail refund that Stripe failed after success (must show "Needs review").
 * Safety: every request to a host other than 127.0.0.1:5174 / 127.0.0.1:8001 is aborted and recorded. The UAT password
 * is read from backend/uat.env and never printed. Screenshots show synthetic UAT data only.
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const [pwPath, outDir, refundId, reviewRefundId, appointmentId] = process.argv.slice(2);
const require = createRequire(import.meta.url);
const { chromium } = require(pwPath);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
const PASSWORD = /^UAT_PASSWORD=(.*)$/m.exec(fs.readFileSync(path.join(ROOT, 'backend', 'uat.env'), 'utf8'))[1].trim();
const APP = 'http://127.0.0.1:5174';
const ALLOWED = new Set(['127.0.0.1:5174', '127.0.0.1:8001']);
const shots = path.join(outDir, 'browser');
fs.mkdirSync(shots, { recursive: true });

const steps = [];
const blocked = [];
const pageErrors = [];
function step(id, scenario, actual, ok) {
  steps.push({ id, scenario, actual, status: ok ? 'PASS' : 'FAIL' });
  console.log(ok ? 'PASS' : 'FAIL', id, scenario, '|', JSON.stringify(actual).slice(0, 240));
}

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 950 } });
await context.route('**/*', (route) => {
  const u = new URL(route.request().url());
  if (u.protocol === 'data:' || ALLOWED.has(u.host)) return route.continue();
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

// A03-U04 / C06 in the browser: the patient's emulator cancellation is approved here (real Stripe test refund)
await page.goto(`${APP}/refunds`);
await page.getByRole('button', { name: 'requested' }).click();
const row = page.getByTestId(`refund-row-${refundId}`);
await row.waitFor({ timeout: 20000 });
const rowText = await row.innerText();
await page.screenshot({ path: path.join(shots, 'a03_b01_refund_queue.png'), fullPage: true });
await row.getByRole('button', { name: 'Review' }).click();
await page.getByRole('button', { name: 'Approve refund' }).click();
const amount = page.getByLabel(/Amount to refund/);
const prefilled = await amount.inputValue();
let approvePosts = 0;
page.on('request', (r) => { if (r.method() === 'POST' && r.url().includes('/approve')) approvePosts += 1; });
const send = page.getByRole('button', { name: /Send refund to Stripe/ });
await page.screenshot({ path: path.join(shots, 'a03_b02_refund_approve_dialog.png') });
await send.dblclick();
await page.getByText(/succeeded in Stripe|pending in Stripe/).waitFor({ timeout: 30000 });
await page.screenshot({ path: path.join(shots, 'a03_b03_refund_succeeded.png') });
step('A03-U04a', 'Admin approves the patient refund from the browser (one request, Stripe result shown)',
  { rowSource: /Patient/i.test(rowText), prefilled, approvePosts }, approvePosts === 1 && /Patient/i.test(rowText));

// A03-BUG-009: a refund Stripe failed after success is visible and explained
await page.goto(`${APP}/refunds`);
await page.getByRole('button', { name: 'succeeded' }).click();
const flagged = page.getByTestId(`refund-review-${reviewRefundId}`);
await flagged.waitFor({ timeout: 20000 });
const flagText = await flagged.innerText();
await page.getByTestId(`refund-row-${reviewRefundId}`).getByRole('button', { name: 'View' }).click();
const alertText = await page.getByRole('alert').innerText();
await page.screenshot({ path: path.join(shots, 'a03_b04_refund_needs_review.png') });
step('A03-U04b', 'Refund that Stripe failed after success shows "Needs review" with an explanation',
  { flagText, alert: alertText.slice(0, 160) }, /Needs review/.test(flagText) && /has not changed any record/.test(alertText));
await page.keyboard.press('Escape');

// Reconciliation lists the review item (rule-based recommendation, not "AI")
await page.goto(`${APP}/reconciliation`);
await page.getByRole('button', { name: /Run Reconciliation Check/ }).click();
await page.getByText('REFUND_FAILED_AFTER_SUCCESS').first().waitFor({ timeout: 30000 });
const header = await page.locator('thead').first().innerText();
await page.getByText(reviewRefundId).first().scrollIntoViewIfNeeded();
await page.screenshot({ path: path.join(shots, 'a03_b05_reconciliation_refund_review.png'), fullPage: true });
step('A03-U03a', 'Reconciliation shows REFUND_FAILED_AFTER_SUCCESS with a rule-based recommendation',
  { listsRefund: (await page.getByText(reviewRefundId).count()) > 0, aiLabel: /AI Recommendation/.test(header) },
  (await page.getByText(reviewRefundId).count()) > 0 && !/AI Recommendation/.test(header));

// A03-U03: payment monitoring shows the emulator payment, its amount and the refund
await page.goto(`${APP}/payments`);
await page.waitForTimeout(2500);
const paymentsText = await page.locator('main').innerText();
await page.screenshot({ path: path.join(shots, 'a03_b06_payments_monitoring.png'), fullPage: true });
step('A03-U03b', 'Payment monitoring lists the LKR 3,500 payment and its refund',
  { hasAmount: /3,500/.test(paymentsText), hasRefunded: /Refunded/.test(paymentsText) },
  /3,500/.test(paymentsText) && /Refunded/.test(paymentsText));

// Cross-role: the admin appointment list shows the cancelled booking with its payment state
await page.goto(`${APP}/appointments`);
await page.waitForTimeout(2500);
const apptText = await page.locator('main').innerText();
await page.screenshot({ path: path.join(shots, 'a03_b07_admin_appointments.png'), fullPage: true });
step('A03-U03c', 'Admin appointments page loads with cancelled and refunded bookings', { hasCancelled: /CANCELLED|Cancelled/.test(apptText) },
  /CANCELLED|Cancelled/.test(apptText));

step('A03-B-SAFETY', 'No request left 127.0.0.1 and no page error', { blocked, pageErrors }, blocked.length === 0 && pageErrors.length === 0);
fs.writeFileSync(path.join(outDir, 'a03_browser_admin_uat.json'), JSON.stringify({ app: APP, backend: '127.0.0.1:8001',
  refundId, reviewRefundId, appointmentId, steps, blocked, pageErrors }, null, 1));
await browser.close();
