const fs = require('node:fs');
const assert = require('node:assert/strict');
const { chromium } = require('C:/Users/rodri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const dir = 'C:/Developer/GESTIONASV_ERP/tmp/warehouse-movements';
fs.mkdirSync(dir,{recursive:true});
const privateData = fs.readFileSync('C:/Users/rodri/AppData/Local/Temp/gestionasv-rodrigo-molina-bodega-20261023.txt','utf8');
(async()=>{
  const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:900},reducedMotion:'reduce',timezoneId:'Asia/Tokyo'});
  const errors=[], requests=[], contrast=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.url().includes('/movements?')) requests.push({url:new URL(r.url()).pathname+new URL(r.url()).search,status:r.status()});});
  try {
    const deadline = Date.now() + 180000;
    while (true) {
      try {
        const ready = await page.request.get('http://localhost:5173/login', {timeout:10000});
        if (ready.status() === 200) break;
      } catch {}
      if (Date.now() > deadline) throw new Error('Frontend not ready after restart');
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
    await page.goto('http://localhost:5173/login',{waitUntil:'networkidle',timeout:90000});
    await page.locator('#login').fill(privateData.match(/^Usuario: (.+)$/m)[1].trim());
    await page.locator('#password').fill(privateData.match(/^Contraseña: (.+)$/m)[1].trim());
    await page.getByRole('button',{name:'Iniciar sesión'}).click();
    await page.waitForURL('**/companies',{timeout:60000});
    await page.getByRole('button').filter({hasText:'Grupo Lorena'}).first().click();
    await page.waitForURL('**/inventory',{timeout:60000});
    const nav=page.getByRole('navigation',{name:'Tareas de bodega'});
    await nav.getByRole('button',{name:'Movimientos',exact:true}).click({timeout:45000});
    const panel=page.getByRole('region',{name:'Movimientos de esta bodega'});
    await panel.locator('article').first().waitFor({timeout:60000});
    await panel.getByLabel('Producto, SKU o unidad').focus();
    await page.keyboard.press('Tab');
    assert(await panel.getByLabel('Desde',{exact:true}).evaluate(e=>e===document.activeElement),'Keyboard navigation');
    await panel.getByText('Más filtros:',{exact:false}).click();
    await panel.getByLabel('Producto, SKU o unidad').fill('Chocolate');
    await panel.getByLabel('Tipo de movimiento',{exact:true}).selectOption('receipt');
    await panel.getByLabel('Sentido',{exact:true}).selectOption('incoming');
    const response=page.waitForResponse(r=>r.url().includes('/movements?')&&new URL(r.url()).searchParams.get('q')==='Chocolate');
    await panel.getByRole('button',{name:'Consultar',exact:true}).click();
    assert.equal((await response).status(),200);
    await panel.getByText('Consultando movimientos…',{exact:true}).waitFor({state:'hidden'});
    assert(requests.at(-1).url.includes('movement_type=receipt'),'Type filter sent');
    assert(requests.at(-1).url.includes('direction=incoming'),'Direction filter sent');
    assert((await panel.getByRole('list',{name:'Filtros aplicados'}).innerText()).includes('Tipo: Recepción'));
    assert(!/USD|Costo promedio|Valoración/.test(await panel.innerText()));
    for(const theme of ['light','dark']) {
      contrast.push(...await page.evaluate(async theme=>{
        document.documentElement.setAttribute('data-theme',theme);
        const {movementTypeLabel}=await import('/src/lib/features/inventory/movement-presentation.ts');
        const surface=document.createElement('div');surface.className='bg-surface';document.body.append(surface);
        const rgb=value=>value.match(/[\d.]+/g).map(Number);
        const lum=values=>values.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
        const base=rgb(getComputedStyle(surface).backgroundColor);
        const results=['receipt','putaway','transfer','pick','shipment','adjustment_in','adjustment_out','reversal'].map(type=>{
          const style=movementTypeLabel(type),el=document.createElement('span');el.className=`${style.color} ${style.bg}`;el.textContent=style.label;surface.append(el);
          const fg=rgb(getComputedStyle(el).color),bg=rgb(getComputedStyle(el).backgroundColor);
          const blended=bg.slice(0,3).map((v,i)=>v*(bg[3]??1)+base[i]*(1-(bg[3]??1)));
          const a=lum(fg),b=lum(blended),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
          return {theme,type,ratio:Math.round(ratio*100)/100};
        });surface.remove();return results;
      },theme));
    }
    assert(contrast.every(v=>v.ratio>=4.5),'All movement badges pass AA');
    for(const [width,theme] of [[1280,'light'],[375,'dark'],[768,'light']]) {
      await page.setViewportSize({width,height:1000});
      await page.evaluate(t=>document.documentElement.setAttribute('data-theme',t),theme);
      await panel.scrollIntoViewIfNeeded();
      await page.screenshot({path:`${dir}/movements-${theme}-${width}.png`,fullPage:true});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow');
      if(width===375){
        await panel.locator('article').first().scrollIntoViewIfNeeded();
        await page.screenshot({path:`${dir}/results-dark-375.png`,fullPage:true});
        await panel.locator('footer').scrollIntoViewIfNeeded();
        await page.screenshot({path:`${dir}/pagination-dark-375.png`,fullPage:true});
      }
    }
    await panel.getByLabel('Desde',{exact:true}).fill('2026-12-01');
    await panel.getByRole('button',{name:'Consultar',exact:true}).click();
    assert((await panel.getByRole('alert').innerText()).includes('Desde'));
    await panel.getByRole('button',{name:'Limpiar filtros'}).click();
    await panel.locator('article').first().waitFor();
    const firstDate=await panel.locator('article time').first().getAttribute('datetime');
    const expectedDate=new Intl.DateTimeFormat('es-SV',{timeZone:'America/El_Salvador',dateStyle:'short',timeStyle:'short'}).format(new Date(firstDate));
    await panel.getByRole('button',{name:/Ver detalle de/}).first().click();
    await page.getByRole('dialog').waitFor();
    assert((await page.getByRole('dialog').innerText()).includes(expectedDate),'Modal uses SV time outside SV browser zone');
    await page.setViewportSize({width:375,height:1000});
    await page.evaluate(()=>document.documentElement.setAttribute('data-theme','dark'));
    await page.screenshot({path:`${dir}/detail-dark-375.png`,fullPage:true});
    assert(await page.getByRole('dialog').evaluate(e=>e.scrollWidth<=e.clientWidth),'Modal does not overflow');
    await page.evaluate(()=>document.documentElement.setAttribute('data-theme','light'));
    await page.setViewportSize({width:768,height:1000});
    await page.screenshot({path:`${dir}/detail.png`,fullPage:true});
    await page.getByRole('dialog').getByRole('button',{name:'Cerrar',exact:true}).last().click();
    await page.setViewportSize({width:375,height:1000});
    // Verify empty/error states without creating any operational data.
    await panel.getByLabel('Producto, SKU o unidad').fill('SIN-COINCIDENCIA-PRUEBA');
    await panel.getByRole('button',{name:'Consultar',exact:true}).click();
    await panel.getByText('No hay movimientos con estos filtros').waitFor();
    await panel.getByText('No hay movimientos con estos filtros').scrollIntoViewIfNeeded();
    await page.screenshot({path:`${dir}/empty.png`,fullPage:true});
    await page.route('**/inventory/warehouses/*/movements?**',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Servicio temporalmente no disponible'})}));
    await panel.getByRole('button',{name:'Consultar',exact:true}).click();
    await panel.getByRole('button',{name:'Reintentar consulta'}).waitFor();
    await panel.getByRole('button',{name:'Reintentar consulta'}).scrollIntoViewIfNeeded();
    await page.screenshot({path:`${dir}/error.png`,fullPage:true});
    await page.unroute('**/inventory/warehouses/*/movements?**');
    await panel.getByRole('button',{name:'Reintentar consulta'}).click();
    await panel.getByText('No hay movimientos con estos filtros').waitFor();
    fs.writeFileSync(`${dir}/result.json`,JSON.stringify({ok:true,requests,errors,contrast},null,2));
    process.stdout.write(JSON.stringify({ok:true,requests,errors,contrast}));
  } catch(e) {
    await page.screenshot({path:`${dir}/failure.png`,fullPage:true});
    process.stdout.write(JSON.stringify({ok:false,error:e.message,requests,errors}));
    process.exitCode=1;
  } finally {await browser.close();}
})();
