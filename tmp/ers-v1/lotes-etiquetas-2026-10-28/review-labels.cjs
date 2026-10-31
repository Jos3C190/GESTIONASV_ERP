const { chromium } = require('C:/Users/rodri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const dir = __dirname;
(async () => {
  const browser = await chromium.launch({ headless:true, executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' });
  try {
    const results = [];
    for (const file of fs.readdirSync('frontend/tmp-labels').filter(x => x.startsWith('papel-') && x.endsWith('.html'))) {
      const page = await browser.newPage({viewport:{width:800,height:900},deviceScaleFactor:3});
      await page.goto(pathToFileURL(path.resolve('frontend/tmp-labels', file)).href);
      await page.evaluate(() => Promise.all(Array.from(document.images, x => x.decode())));
      const fits = await page.locator('.label').evaluateAll(labels => labels.map(label => ({
        width:label.clientWidth,height:label.clientHeight,scrollWidth:label.scrollWidth,scrollHeight:label.scrollHeight,
        fit: label.scrollWidth <= label.clientWidth+1 && label.scrollHeight <= label.clientHeight+1,
        text:label.innerText
      })));
      const name = file.replace('.html','');
      await page.locator('.label').first().screenshot({path:path.join(dir, name+'.png')});
      await page.pdf({path:path.join(dir,name+'.pdf'),preferCSSPageSize:true,printBackground:true});
      results.push({file,fits});
      await page.close();
    }
    for (const [theme,width] of [['light',1280],['dark',375],['light',768]]) {
      const page = await browser.newPage({viewport:{width,height:900}});
      const errors=[];page.on('pageerror',error=>errors.push(error.message));
      page.on('console',msg=>{if(msg.type()==='error')errors.push(msg.text())});
      await page.goto(`http://localhost:5173/qa-label-preview?theme=${theme}`);
      await page.locator('#hu-label-content').waitFor({timeout:15000}).catch(async error=>{
        process.stderr.write(JSON.stringify({errors,body:(await page.locator('body').innerText()).slice(0,1000)}));throw error;
      });
      for (const content of ['full','qr','barcode']) {
        await page.locator('#hu-label-content').selectOption(content);
        await page.getByLabel(/Observaciones de la etiqueta/).fill('Mantener seco');
        await page.getByRole('button',{name:'Imprimir etiqueta',exact:true}).waitFor();
        await page.waitForFunction(() => !Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Imprimir etiqueta')?.disabled);
        await page.locator('dialog').screenshot({path:path.join(dir,`dialog-${content}-${theme}-${width}.png`)});
        results.push({dialog:content,theme,width,overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),errors});
      }
      await page.close();
    }
    {
      const page=await browser.newPage({viewport:{width:1280,height:900}});
      await page.goto('http://localhost:5173/qa-label-preview');
      const copies=page.locator('#handling-unit-label-copies');
      await copies.fill('0');
      const issue=await page.locator('#hu-label-copies-issue').innerText();
      const invalid=await copies.getAttribute('aria-invalid');
      const disabled=await page.getByRole('button',{name:'Imprimir etiqueta',exact:true}).isDisabled();
      if(invalid!=='true'||!disabled)throw new Error('Local copy validation failed');
      await page.locator('dialog').screenshot({path:path.join(dir,'dialog-copias-invalidas.png')});
      await copies.fill('1');
      const popupPromise=page.waitForEvent('popup');
      await page.getByRole('button',{name:'Abrir vista a tamaño real'}).click();
      const popup=await popupPromise;
      await popup.locator('.label').waitFor();
      results.push({localValidation:issue,invalid,disabled,enlargedPreview:await popup.locator('.label').count()});
      await popup.close();
      await page.locator('#hu-label-size').selectOption('custom');
      await page.locator('#hu-label-width').fill('24');
      const dimensionsInvalid=await page.locator('#hu-label-width').getAttribute('aria-invalid');
      const dimensionsDescription=await page.locator('#hu-label-width').getAttribute('aria-describedby');
      if(dimensionsInvalid!=='true'||dimensionsDescription!=='hu-label-width-issue')throw new Error('Dimension association failed');
      await page.locator('dialog').screenshot({path:path.join(dir,'dialog-medidas-invalidas.png')});
      await page.locator('#hu-label-width').fill('100');
      await page.getByRole('button',{name:'Invalidar enlaces públicos',exact:true}).click();
      const cancelFocused=await page.evaluate(()=>document.activeElement?.id==='qr-revoke-cancel');
      await page.getByRole('button',{name:'Cancelar',exact:true}).click();
      const focusReturned=await page.evaluate(()=>document.activeElement?.id==='qr-revoke-trigger');
      if(!cancelFocused||!focusReturned)throw new Error('Revocation focus failed');
      results.push({dimensionsInvalid,dimensionsDescription,cancelFocused,focusReturned});
      await page.close();
    }
    {
      const page=await browser.newPage({viewport:{width:375,height:900}});
      await page.goto('http://localhost:5173/qa-label-preview?blocked&theme=dark');
      await page.getByRole('alert').waitFor();
      results.push({blockedRetaceo:await page.getByRole('button',{name:'Imprimir etiqueta',exact:true}).isDisabled()});
      await page.locator('dialog').screenshot({path:path.join(dir,'dialog-retaceo-pendiente.png')});
      await page.close();
    }
    fs.writeFileSync(path.join(dir,'qa-results.json'),JSON.stringify(results,null,2));
    process.stdout.write(JSON.stringify(results.map(x=>x.file?{file:x.file,fit:x.fits.every(y=>y.fit)}:x)));
  } finally { await browser.close(); }
})();
