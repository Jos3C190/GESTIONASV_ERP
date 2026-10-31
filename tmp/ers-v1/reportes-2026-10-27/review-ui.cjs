const { chromium } = require('C:/Users/rodri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' });
  try {
    for (const [name, theme, width] of [
      ['descargas-retaceo', 'light', 1280],
      ['descargas-retaceo', 'dark', 375],
      ['descargas-consolidado', 'light', 768],
      ['descargas-error', 'dark', 375]
    ]) {
      const page = await browser.newPage({ viewport: { width, height: 450 } });
      await page.goto(pathToFileURL(path.resolve('frontend/tmp-reports', `${name}-${theme}.html`)).href);
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({ path: path.resolve('tmp/ers-v1/reportes-2026-10-27', `${name}-${theme}-${width}.png`), fullPage: true });
      console.log(name, theme, width, 'horizontal overflow:', await page.evaluate(() => document.documentElement.scrollWidth > innerWidth));
      await page.close();
    }
  } finally { await browser.close(); }
})();
