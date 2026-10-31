const { chromium } = require('C:/Users/rodri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' });
  const results = [];
  try {
    const files = fs.readdirSync('frontend/tmp-labels').filter(name => /^(papel-|retoque-).*\.html$/.test(name));
    for (const file of files) {
      const page = await browser.newPage({ viewport: { width: 800, height: 900 }, deviceScaleFactor: 3 });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(pathToFileURL(path.resolve('frontend/tmp-labels', file)).href);
      await page.evaluate(async () => { await document.fonts.ready; await Promise.all(Array.from(document.images, image => image.decode())); });
      const labels = await page.locator('.label').evaluateAll(elements => elements.map(label => ({
        width: label.clientWidth, height: label.clientHeight, scrollWidth: label.scrollWidth, scrollHeight: label.scrollHeight,
        fit: label.scrollWidth <= label.clientWidth + 1 && label.scrollHeight <= label.clientHeight + 1,
        traceAlignment: getComputedStyle(label.querySelector('.trace')).textAlign,
        text: label.innerText
      })));
      const name = file.replace('.html', '');
      fs.copyFileSync(path.join('frontend/tmp-labels', file), path.join(__dirname, file));
      await page.locator('.label').first().screenshot({ path: path.join(__dirname, name + '.png') });
      await page.pdf({ path: path.join(__dirname, name + '.pdf'), preferCSSPageSize: true, printBackground: true });
      results.push({ file, labels, errors });
      await page.close();
    }
    fs.writeFileSync(path.join(__dirname, 'qa-results.json'), JSON.stringify(results, null, 2));
    process.stdout.write(JSON.stringify(results.map(result => ({ file: result.file, fit: result.labels.every(label => label.fit), errors: result.errors }))));
    if (results.some(result => result.labels.some(label => !label.fit) || result.errors.length)) process.exitCode = 1;
  } finally { await browser.close(); }
})();
