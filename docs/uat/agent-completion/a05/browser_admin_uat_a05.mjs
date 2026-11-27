/**
 * A05 admin browser UAT: the real admin web app (Vite dev server, 127.0.0.1:5174) against the local UAT backend
 * (127.0.0.1:8001, mediconnect_uat), driven in the locally installed Chrome through playwright-core.
 *
 *   node docs/uat/agent-completion/a05/browser_admin_uat_a05.mjs <playwright-core> <out-dir> fraud <assessmentId>
 *   node docs/uat/agent-completion/a05/browser_admin_uat_a05.mjs <playwright-core> <out-dir> reply <ticketId> <text>
 *   node docs/uat/agent-completion/a05/browser_admin_uat_a05.mjs <playwright-core> <out-dir> followup <ticketId> <text>
 *
 * fraud: the slot-hoarding signal raised by the backend worker is reviewed (evidence, history, human decisions); the
 *   modal is closed without recording a decision.
 * reply: the patient's emulator ticket is found, the suggested template is inserted, edited and explicitly sent once.
 * followup: the patient's emulator follow-up is visible to the administrator.
 * Safety: every request to a host other than 127.0.0.1:5174 / 127.0.0.1:8001 is aborted and recorded. The UAT password
 * is read from backend/uat.env and never printed. Screenshots show synthetic UAT data only.
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const [pwPath, outDir, mode, ref, text] = process.argv.slice(2);
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

if (mode === 'fraud') {
  await page.goto(`${APP}/monitoring`);
  await page.getByRole('button', { name: /Fraud Risk Center/ }).click();
  const row = page.locator('tr', { hasText: ref });
  await row.waitFor({ timeout: 20000 });
  const disclaimer = await page.getByText(/not proof of fraud/).innerText();
  await page.screenshot({ path: path.join(shots, 'a05_b01_fraud_signals.png'), fullPage: true });
  await row.getByRole('button', { name: 'Review' }).click();
  const modal = page.getByTestId('fraud-review-modal');
  const evidence = await modal.getByTestId('fraud-evidence').innerText();
  const history = await modal.getByTestId('fraud-history').innerText().catch(() => '');
  const buttons = await modal.getByRole('button').allInnerTexts();
  await page.screenshot({ path: path.join(shots, 'a05_b02_fraud_review_evidence.png') });
  step('A05-F10/F11', 'Admin sees the worker-raised signal with rule, threshold, observed value and slot evidence',
    { rowHasRule: /SLOT_HOARDING_ATTEMPT/.test(await row.innerText()), disclaimer: disclaimer.slice(0, 120),
      evidenceHasThreshold: /provisional/.test(evidence), evidenceSlots: (evidence.match(/Asia\/Colombo/g) || []).length,
      historyShown: /synthetic review note/.test(history) },
    /provisional/.test(evidence) && (evidence.match(/Asia\/Colombo/g) || []).length >= 4);
  step('A05-F12/F14', 'Only human review decisions are offered; none changes an account',
    { buttons }, buttons.some((b) => /Confirm finding \(human decision\)/.test(b)) &&
      !buttons.some((b) => /suspend|ban|refund|cancel appointment/i.test(b)));
  await modal.getByRole('button', { name: 'Cancel' }).click();
}

if (mode === 'reply' || mode === 'followup') {
  await page.goto(`${APP}/support-tickets`);
  const row = page.locator('tr', { hasText: ref });
  await row.waitFor({ timeout: 20000 });
  const flagged = await page.getByTestId(`awaiting-support-${ref}`).isVisible();
  await page.screenshot({ path: path.join(shots, `a05_b0${mode === 'reply' ? 3 : 7}_support_queue.png`), fullPage: true });
  await row.getByRole('button', { name: 'Respond' }).click();
  const thread = page.getByTestId('ticket-thread');
  await thread.waitFor({ timeout: 20000 });
  const threadText = await thread.innerText();
  if (mode === 'followup') {
    await page.screenshot({ path: path.join(shots, 'a05_b08_followup_visible.png') });
    step('A05-C12', 'Admin sees the patient follow-up in the same ticket, flagged as awaiting support',
      { flagged, hasFollowUp: threadText.includes(text) }, flagged && threadText.includes(text));
  } else {
    const box = page.getByLabel('Reply to the requester');
    const prefilled = await box.inputValue();
    await page.screenshot({ path: path.join(shots, 'a05_b04_ticket_with_template_card.png') });
    await page.getByRole('button', { name: 'Insert suggested reply' }).click();
    await page.waitForFunction(() => (document.querySelector('#supportReply')?.value || '').length > 20);
    const draft = await box.inputValue();
    await box.fill(`${draft.replace('Warm regards', 'Kind regards')}\n${text}`);
    await page.screenshot({ path: path.join(shots, 'a05_b05_reply_edited_before_send.png') });
    let replyPosts = 0;
    page.on('request', (r) => { if (r.method() === 'POST' && r.url().endsWith('/reply')) replyPosts += 1; });
    await page.getByRole('button', { name: 'Send reply' }).dblclick();
    await page.getByText(/Reply sent and ticket updated|already sent/).first().waitFor({ timeout: 20000 });
    await page.screenshot({ path: path.join(shots, 'a05_b06_reply_sent.png') });
    step('A05-C06/C07/C08/C09', 'Admin finds the emulator ticket, inserts the template, edits it and sends it explicitly',
      { flagged, prefilledBeforeInsert: prefilled, draftInserted: draft.length > 20, replyPosts,
        patientMessageShown: threadText.length > 0 },
      flagged && prefilled === '' && draft.length > 20 && replyPosts >= 1);
  }
}

step('A05-NET', 'No request left 127.0.0.1:5174 / 127.0.0.1:8001', { blocked: [...new Set(blocked)] }, blocked.length === 0);
step('A05-ERR', 'No uncaught page error', { pageErrors }, pageErrors.length === 0);
await browser.close();
const file = path.join(outDir, `a05_browser_admin_${mode}.json`);
fs.writeFileSync(file, JSON.stringify({ at: new Date().toISOString(), mode, ref, steps }, null, 1));
console.log('written', path.basename(file));
