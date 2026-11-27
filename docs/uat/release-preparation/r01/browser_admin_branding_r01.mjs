/**
 * R01 admin branding capture: the real admin web app (Vite dev server, 127.0.0.1:5174) against the local UAT backend
 * (127.0.0.1:8001, mediconnect_uat), driven in the locally installed Chrome through playwright-core.
 *
 *   node docs/uat/release-preparation/r01/browser_admin_branding_r01.mjs <playwright-core> <out-dir> <before|after>
 *
 * Captures: login page, route loading state, dashboard sidebar + header (desktop), off-canvas sidebar (mobile width),
 * and the favicon declared by index.html (resolved, fetched and rendered at tab sizes, since headless screenshots do
 * not include the browser tab strip).
 * Safety: every request to a host other than 127.0.0.1:5174 / 127.0.0.1:8001 is aborted and recorded. The UAT password
 * is read from backend/uat.env and never printed. Screenshots show synthetic UAT data only.
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const [pwPath, outDir, label] = process.argv.slice(2);
const require = createRequire(import.meta.url);
const { chromium } = require(pwPath);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
const PASSWORD = /^UAT_PASSWORD=(.*)$/m.exec(fs.readFileSync(path.join(ROOT, 'backend', 'uat.env'), 'utf8'))[1].trim();
const APP = 'http://127.0.0.1:5174';
const ALLOWED = new Set(['127.0.0.1:5174', '127.0.0.1:8001']);
const shots = path.join(outDir, 'browser');
fs.mkdirSync(shots, { recursive: true });
const name = (n) => path.join(shots, `r01_${label}_${n}.png`);

const steps = [];
const blocked = [];
const pageErrors = [];
function step(id, scenario, actual, ok) {
  steps.push({ id, scenario, actual, status: ok ? 'PASS' : 'FAIL' });
  console.log(ok ? 'PASS' : 'FAIL', id, scenario, '|', JSON.stringify(actual).slice(0, 240));
}

const browser = await chromium.launch({ channel: 'chrome', headless: true });
async function newPage(viewport) {
  const context = await browser.newContext({ viewport });
  await context.route('**/*', (route) => {
    const u = new URL(route.request().url());
    if (u.protocol === 'data:' || ALLOWED.has(u.host)) return route.continue();
    blocked.push(u.host);
    return route.abort();
  });
  const page = await context.newPage();
  page.on('pageerror', (e) => pageErrors.push(`${page.url()} :: ${e.message}`));
  return page;
}

// 1. Login page (desktop) and document metadata
const page = await newPage({ width: 1440, height: 950 });
await page.goto(`${APP}/login`);
await page.locator('input[type="email"]').waitFor();
await page.screenshot({ path: name('b01_admin_login') });
const meta = await page.evaluate(() => ({
  title: document.title,
  icons: [...document.querySelectorAll('link[rel~="icon"], link[rel="apple-touch-icon"]')].map((l) => ({
    rel: l.rel, type: l.type, sizes: l.getAttribute('sizes'), href: l.href,
  })),
  brandImgs: [...document.querySelectorAll('img')].map((i) => ({
    alt: i.alt, w: i.getBoundingClientRect().width, h: i.getBoundingClientRect().height,
    natural: [i.naturalWidth, i.naturalHeight], complete: i.complete,
  })),
}));
step('B01', 'Admin login page renders with title and brand', meta, meta.title.includes('MediConnect'));

// 2. Favicon: fetch every declared icon and render it at tab sizes
const icons = [];
for (const icon of meta.icons) {
  const res = await page.request.get(icon.href);
  icons.push({ ...icon, status: res.status(), contentType: res.headers()['content-type'], bytes: (await res.body()).length });
}
step('B02', 'Declared favicons resolve', icons, icons.length > 0 && icons.every((i) => i.status === 200 && /^image\//.test(i.contentType || '')));
const fav = await newPage({ width: 520, height: 140 });
await fav.goto(`${APP}/login`);
await fav.evaluate((list) => {
  document.body.innerHTML = '';
  document.body.style.cssText = 'margin:0;font:13px system-ui;display:flex;gap:0;';
  for (const [bg, fg] of [['#dee1e6', '#202124'], ['#35363a', '#e8eaed']]) {
    const strip = document.createElement('div');
    strip.style.cssText = `background:${bg};color:${fg};padding:16px;display:flex;flex-direction:column;gap:10px;width:260px`;
    for (const i of list) {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:8px';
      row.innerHTML = `<img src="${i.href}" width="16" height="16"><img src="${i.href}" width="32" height="32"><span>${i.sizes || i.type || i.rel}</span>`;
      strip.appendChild(row);
    }
    document.body.appendChild(strip);
  }
}, meta.icons);
await fav.waitForTimeout(400);
await fav.screenshot({ path: name('b02_favicon_render') });

// 3. Route loading state (initial auth check is shown while /auth/me is pending; delay it to capture)
const slow = await newPage({ width: 1440, height: 950 });
await slow.goto(`${APP}/login`);
await slow.locator('input[type="email"]').fill('uat.admin@uat.mediconnect.lk');
await slow.locator('input[type="password"]').fill(PASSWORD);
await slow.locator('button[type="submit"]').click();
await slow.waitForURL(/dashboard/, { timeout: 20000 });
// Delay the lazily loaded page module so the Suspense route fallback stays on screen long enough to capture.
await slow.route(/\/src\/pages\/DashboardPage\.tsx/, async (route) => { await new Promise((r) => setTimeout(r, 3000)); return route.continue(); });
await slow.goto(`${APP}/dashboard`);
await slow.getByText(/Loading administrative module/).waitFor({ timeout: 2500 }).catch(() => {});
await slow.screenshot({ path: name('b03_admin_module_loading') });
const moduleText = (await slow.locator('main').innerText().catch(() => '')).trim();
step('B03', 'In-layout module loading state captured (sidebar brand visible)', moduleText.slice(0, 120), /Loading administrative module/.test(moduleText));
// Full-screen route fallback: shown while a lazily loaded top-level route (here /unauthorized) is fetched.
await slow.route(/\/src\/pages\/UnauthorizedPage\.tsx/, async (route) => { await new Promise((r) => setTimeout(r, 3000)); return route.continue(); });
await slow.goto(`${APP}/unauthorized`);
await slow.getByText(/Loading MediConnect Admin/).waitFor({ timeout: 2500 }).catch(() => {});
await slow.screenshot({ path: name('b03b_admin_route_loading') });
const routeText = (await slow.locator('body').innerText()).trim();
step('B03b', 'Full-screen route loading state captured', routeText.slice(0, 120), /^Loading MediConnect Admin/.test(routeText));

// 4. Dashboard with sidebar and header (desktop)
await page.locator('input[type="email"]').fill('uat.admin@uat.mediconnect.lk');
await page.locator('input[type="password"]').fill(PASSWORD);
await page.locator('button[type="submit"]').click();
await page.waitForURL(/dashboard/, { timeout: 20000 });
await page.waitForTimeout(1500);
await page.screenshot({ path: name('b04_admin_dashboard') });
await page.screenshot({ path: name('b05_admin_sidebar_brand_zoom'), clip: { x: 0, y: 0, width: 420, height: 140 } });
const brand = await page.evaluate(() => {
  const aside = document.querySelector('aside');
  const img = aside?.querySelector('img');
  const r = img?.getBoundingClientRect();
  return { sidebarText: aside?.innerText.slice(0, 40), img: img ? { alt: img.alt, w: r.width, h: r.height, natural: [img.naturalWidth, img.naturalHeight] } : null };
});
step('B04', 'Dashboard sidebar brand renders', brand, /MediConnect/.test(brand.sidebarText || ''));

// 5. Mobile width: off-canvas sidebar opened
const mobile = await newPage({ width: 390, height: 844 });
await mobile.goto(`${APP}/login`);
await mobile.screenshot({ path: name('b06_admin_login_mobile') });
await mobile.locator('input[type="email"]').fill('uat.admin@uat.mediconnect.lk');
await mobile.locator('input[type="password"]').fill(PASSWORD);
await mobile.locator('button[type="submit"]').click();
await mobile.waitForURL(/dashboard/, { timeout: 20000 });
await mobile.waitForTimeout(1200);
const opener = mobile.getByRole('button', { name: /open sidebar|menu/i }).first();
if (await opener.count()) await opener.click();
await mobile.waitForTimeout(500);
await mobile.screenshot({ path: name('b07_admin_sidebar_mobile') });
const overflow = await mobile.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
step('B05', 'Mobile width: sidebar opens, no horizontal overflow', { overflow }, overflow <= 0);

await browser.close();
const result = { label, steps, meta, icons, brand, blockedRequests: blocked, pageErrors };
fs.writeFileSync(path.join(outDir, `r01_browser_${label}.json`), JSON.stringify(result, null, 2));
console.log('blocked', blocked.length, 'pageErrors', pageErrors.length);
