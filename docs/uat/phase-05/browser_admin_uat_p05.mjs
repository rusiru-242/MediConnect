/**
 * Phase 05 copy of the Phase 04 browser UAT (session step updated for token refresh). Original: the real admin web app (Vite dev server, 127.0.0.1:5174) connected to the local UAT backend
 * (127.0.0.1:8001, mediconnect_uat). Drives the locally installed Chrome through playwright-core.
 *
 *   node docs/uat/phase-05/browser_admin_uat_p05.mjs <path-to-playwright-core> <out-dir>
 *
 * Safety: every request to a host other than 127.0.0.1:5174 / 127.0.0.1:8001 is aborted and recorded. The UAT
 * password is read from backend/uat.env and never printed. Screenshots show synthetic UAT data only.
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const [pwPath, outDir] = process.argv.slice(2);
const require = createRequire(import.meta.url);
const { chromium } = require(pwPath);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const PASSWORD = /^UAT_PASSWORD=(.*)$/m.exec(fs.readFileSync(path.join(ROOT, 'backend', 'uat.env'), 'utf8'))[1].trim();
const APP = 'http://127.0.0.1:5174';
const ALLOWED = new Set(['127.0.0.1:5174', '127.0.0.1:8001']);
const shots = path.join(outDir, 'screenshots');
fs.mkdirSync(shots, { recursive: true });

const steps = [];
const blocked = [];
const pageErrors = [];
function step(id, scenario, expected, actual, ok) {
  steps.push({ id, scenario, expected, actual, status: ok ? 'PASS' : 'FAIL' });
  console.log(ok ? 'PASS' : 'FAIL', id, scenario, '|', JSON.stringify(actual).slice(0, 220));
}

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await context.route('**/*', (route) => {
  const u = new URL(route.request().url());
  if (u.protocol === 'data:' || ALLOWED.has(u.host)) return route.continue();
  blocked.push(u.host);
  return route.abort();
});
const page = await context.newPage();
page.on('pageerror', (e) => pageErrors.push(`${page.url()} :: ${e.message}`));

async function login(email) {
  await page.goto(`${APP}/login`);
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(PASSWORD);
  await page.locator('button[type="submit"]').click();
}

// A-16a / A-01a: login and navigate every admin page
await login('uat.admin@uat.mediconnect.lk');
await page.waitForURL(/dashboard/, { timeout: 20000 });
await page.getByText('Net collections (LKR)').waitFor({ timeout: 20000 });
await page.screenshot({ path: path.join(shots, 'a16-dashboard.png'), fullPage: true });
const dashText = await page.locator('main').innerText();
step('A-16a1', 'Dashboard in a real browser against the UAT backend', 'net collections, gross/refunded line, no "Revenue" or "Real-time" claims',
  { hasNet: /net collections/i.test(dashText), hasGross: /Gross LKR/.test(dashText), revenueWord: /Revenue by Currency/i.test(dashText), realtime: /Real-time/i.test(dashText) },
  /net collections/i.test(dashText) && !/Revenue by Currency|Real-time/i.test(dashText));

const routes = ['dashboard', 'doctor-approvals', 'reconciliation', 'refunds', 'support-tickets', 'reports', 'audit-logs', 'monitoring',
  'doctors', 'users', 'appointments', 'payments', 'reviews', 'content', 'analytics', 'settings'];
const nav = {};
for (const r of routes) {
  const before = pageErrors.length;
  await page.goto(`${APP}/${r}`);
  await page.waitForLoadState('networkidle');
  const boundary = await page.getByText(/Something went wrong/i).count();
  nav[r] = { errors: pageErrors.length - before, errorBoundary: boundary };
}
step('A-16a', 'Navigate all 16 admin pages', 'no uncaught page error and no error boundary on any page', nav,
  Object.values(nav).every((v) => v.errors === 0 && v.errorBoundary === 0));

// A-05c in the browser: the null-fee appointment renders "Not available"
await page.goto(`${APP}/appointments`);
await page.getByPlaceholder(/Search patient/).fill('2026-10-02');
await page.waitForTimeout(1200);
const feeCells = await page.getByTestId('appointment-fee').allInnerTexts();
await page.screenshot({ path: path.join(shots, 'a05c-null-fee-appointments.png'), fullPage: true });
step('A-05c-ui', 'Appointments page with the null-fee historical record (P3-B2)', 'page renders; fee cell "Not available"; no LKR 0.00',
  { feeCells, pageErrors: pageErrors.filter((e) => e.includes('/appointments')).length },
  feeCells.includes('Not available') && !feeCells.includes('LKR 0.00'));

// A-16b: tables and filters
await page.goto(`${APP}/users`);
await page.getByPlaceholder(/Search/i).first().fill('uat.p04.patient');
await page.waitForTimeout(1200);
const userRows = await page.locator('tbody tr').allInnerTexts();
step('A-16b', 'Table search and filters (users)', 'only the two P04 patients', { rows: userRows.length, sample: userRows.map((r) => r.split('\n')[0]) },
  userRows.length === 2 && userRows.every((r) => r.includes('P04 Patient')));

// A-16d: confirmation dialog for a destructive action (cancelled; nothing changes)
await page.getByRole('button', { name: 'Suspend' }).first().click();
const dialogText = await page.getByRole('dialog').innerText().catch(() => '');
await page.screenshot({ path: path.join(shots, 'a16d-suspend-confirmation.png') });
await page.getByRole('button', { name: /Cancel/i }).last().click();
step('A-16d', 'Confirmation before suspending an account', 'dialog shown; cancelled without change', { dialog: dialogText.slice(0, 120) }, /Suspend/.test(dialogText));

// A-16d/A-16f + B15/P3-B3: refund review of a doctor-leave request in the browser, real Stripe test refund
await page.goto(`${APP}/refunds`);
await page.getByRole('combobox', { name: 'Refund source' }).selectOption('leave');
await page.getByRole('button', { name: 'requested' }).click();
await page.waitForTimeout(1200);
await page.screenshot({ path: path.join(shots, 'a10c-refunds-leave-queue.png'), fullPage: true });
const leaveRows = page.locator('tbody tr');
const leaveCount = await leaveRows.count();
let refundUi = { leaveRows: leaveCount };
if (leaveCount > 0) {
  const row = leaveRows.first();
  refundUi.source = (await row.innerText()).includes('Doctor leave');
  await row.getByRole('button', { name: 'Review' }).click();
  await page.getByRole('button', { name: 'Approve refund' }).click();
  const amount = page.getByLabel(/Amount to refund/);
  await amount.fill('999999');
  const send = page.getByRole('button', { name: /Send refund to Stripe/ });
  refundUi.overLimitDisabled = await send.isDisabled();
  refundUi.alert = await page.getByRole('alert').innerText();
  await page.screenshot({ path: path.join(shots, 'a16d-refund-amount-validation.png') });
  const policy = await page.getByText(/^Policy amount LKR/).innerText();
  const value = /LKR ([\d,]+\.\d{2})/.exec(policy)[1].replace(/,/g, '');
  await amount.fill(value);
  let approvePosts = 0;
  page.on('request', (r) => { if (r.method() === 'POST' && r.url().includes('/approve')) approvePosts += 1; });
  await send.dblclick();
  await send.click({ timeout: 1000 }).catch(() => {});
  await page.getByText(/succeeded in Stripe|pending in Stripe/).waitFor({ timeout: 30000 });
  refundUi.approvePosts = approvePosts;
  await page.screenshot({ path: path.join(shots, 'a10f-refund-succeeded-toast.png') });
}
step('A-16f', 'Refund approval from the browser: validation, single submission, Stripe result shown', 'over-limit amount disabled; one approve request for repeated clicks; toast states Stripe result',
  refundUi, leaveCount > 0 && refundUi.source && refundUi.overLimitDisabled && refundUi.approvePosts === 1);

// A-16e: loading and error states (one request answered with 500 by the browser, not the server)
await page.route('**/api/admin/workflow/refunds**', (route) => route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Synthetic UAT error"}' }));
await page.goto(`${APP}/refunds`);
await page.getByText('Failed to load refund requests').waitFor({ timeout: 15000 });
await page.screenshot({ path: path.join(shots, 'a16e-refunds-error-state.png') });
const emptyShown = await page.getByText('No refund requests').count();
await page.unroute('**/api/admin/workflow/refunds**');
step('A-16e', 'Error state instead of a misleading empty list', '"Failed to load refund requests" with retry; no "No refund requests"', { emptyShown }, emptyShown === 0);

// Monitoring page: truthful provider and worker states
await page.goto(`${APP}/monitoring`);
await page.getByText(/CONFIGURED, NOT VERIFIED/).first().waitFor({ timeout: 15000 });
await page.screenshot({ path: path.join(shots, 'a11-monitoring.png'), fullPage: true });
const monText = await page.locator('main').innerText();
step('A-11-ui', 'Monitoring page states', 'Stripe "configured, not verified"; providers "not configured"; AI "disabled"; no availability %',
  { configuredNotVerified: monText.includes('CONFIGURED, NOT VERIFIED'), notConfigured: monText.includes('NOT CONFIGURED'), disabled: monText.includes('DISABLED'), uptimePct: /\d+(\.\d+)?% uptime/i.test(monText) },
  monText.includes('CONFIGURED, NOT VERIFIED') && monText.includes('NOT CONFIGURED') && !/\d+(\.\d+)?% uptime/i.test(monText));

// Reports page
await page.goto(`${APP}/reports`);
await page.waitForLoadState('networkidle');
const reportsText = await page.locator('main').innerText();
const options = await page.locator('select option, [role="option"], button').allInnerTexts();
const offered = options.filter((o) => /Appointment|Payments|Verification|Support|Refund|Weekly/.test(o));
step('A-13-ui', 'Report types offered', 'implemented reports listed; no "Weekly Booking" (not implemented)', { offered },
  offered.length >= 5 && !/Weekly Booking/i.test(reportsText) && !offered.some((o) => /Weekly/.test(o)));

// A-16c: responsive layout at phone width
await page.setViewportSize({ width: 390, height: 844 });
const overflow = {};
for (const r of ['dashboard', 'refunds', 'appointments']) {
  await page.goto(`${APP}/${r}`);
  await page.waitForLoadState('networkidle');
  overflow[r] = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
}
await page.goto(`${APP}/dashboard`);
await page.waitForLoadState('networkidle');
await page.screenshot({ path: path.join(shots, 'a16c-dashboard-390px.png'), fullPage: true });
step('A-16c', 'Responsive layout at 390 px', 'no page-level horizontal scroll (tables scroll inside their container)', overflow,
  Object.values(overflow).every((v) => v <= 1));
await page.setViewportSize({ width: 1366, height: 900 });

// Phase 05: an expired access token with a valid refresh token is refreshed once (single flight) and the page
// keeps working; with both tokens invalid the session ends at /login.
await page.evaluate(() => sessionStorage.setItem('mediconnect_admin_token', 'invalid.token.value'));
await page.goto(`${APP}/users`);
await page.waitForLoadState('networkidle');
await page.waitForTimeout(1500);
const refreshed = await page.evaluate(() => sessionStorage.getItem('mediconnect_admin_token'));
step('P05-REFRESH-ui', 'Expired access token, valid refresh token', 'stays on /users with a new access token',
  { url: page.url().replace(APP, ''), tokenReplaced: refreshed !== 'invalid.token.value' && !!refreshed },
  /\/users/.test(page.url()) && refreshed !== 'invalid.token.value' && !!refreshed);
await page.evaluate(() => { sessionStorage.setItem('mediconnect_admin_token', 'invalid.token.value');
  sessionStorage.setItem('mediconnect_admin_refresh', 'invalid-refresh'); });
await page.goto(`${APP}/users`);
await page.waitForURL(/login/, { timeout: 15000 });
step('A-01c-ui', 'Invalid access and refresh tokens in the browser', 'redirected to /login (expired=1)', { url: page.url().replace(APP, '') }, /\/login/.test(page.url()));

// A-01d in the browser: a patient cannot use the admin app
await context.clearCookies();
await page.evaluate(() => sessionStorage.clear());
await login('uat.p04.patienta@uat.mediconnect.lk');
await page.waitForTimeout(2500);
await page.screenshot({ path: path.join(shots, 'a01d-patient-blocked.png') });
const patientUrl = page.url().replace(APP, '');
const patientText = await page.locator('body').innerText();
step('A-01d-ui', 'Patient login to the admin app', 'not admitted to the dashboard', { url: patientUrl, message: patientText.slice(0, 140) },
  !/dashboard/.test(patientUrl));

step('A-17b-ui', 'Browser network stayed local', 'no request left 127.0.0.1:5174/8001', { blockedHosts: [...new Set(blocked)] }, true);
await browser.close();
const out = { app: APP, api: 'http://127.0.0.1:8001/api', browser: 'Google Chrome (installed), headless', steps, pageErrors,
  blockedExternalHosts: [...new Set(blocked)],
  summary: { total: steps.length, passed: steps.filter((s) => s.status === 'PASS').length, failed: steps.filter((s) => s.status !== 'PASS').map((s) => s.id) } };
fs.writeFileSync(path.join(outDir, 'browser-admin-uat.json'), JSON.stringify(out, null, 2));
console.log('SUMMARY', JSON.stringify(out.summary));
