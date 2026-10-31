const { chromium } = require('C:/Users/rodri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const company = '0a7303f6-64a5-428c-a829-c2b09966fefd';
const warehouse = { id:'warehouse-1', company_id:company, code:'BM-001', name:'Bodega Matriz Grupo Lorena', is_central:true, is_active:true };
const unit = {id:'unit-1',code:'HU-51F4EAD782F64CE1',company_id:company,warehouse_id:warehouse.id,location_id:'receiving',inventory_item_id:'item-1',inventory_lot_detail_id:'detail-1',
 product_name:'Azúcar Glass Premium 10kg',product_sku:'PRD-AZU-004',base_unit_symbol:'cj',quantity_base:'50',phase:'place',measurement_status:'verified',measurement_source:'manual',label_confirmed:true,
 lot_code:null,receipt_lot_code:'LOT-COM-00028-65B89DA483ED4E549EF65C724C914081',received_at:'2026-10-28T14:30:00Z',stock_status:'quarantine',closed_at:null,
 actual_gross_weight_kg:500,actual_volume_m3:1,actual_length_m:null,actual_width_m:null,actual_height_m:null,occupied_weight_kg:500,occupied_volume_m3:1};
const units=[unit,{...unit,id:'unit-2',code:'HU-9218F4A69AD14571',product_name:'Caja de Cartón para Pastel 12 pulgadas',quantity_base:'200',phase:'measure',measurement_status:'incomplete',label_confirmed:false},{...unit,id:'unit-3',code:'HU-08425AF7DA0245EA',product_name:'Café Tostado y Molido 1kg',quantity_base:'15',phase:'label',label_confirmed:false}];
const paged = items => ({items,meta:{total:items.length,page:1,pages:1,size:10}});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const results=[];
 try {
  for(const [theme,width] of [['light',1280],['dark',1280],['light',768],['dark',375],['light',375]]) {
   const page=await browser.newPage({viewport:{width,height:950}});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(({theme,company})=>{localStorage.setItem('erp-theme',theme);sessionStorage.setItem('erp_active_company',JSON.stringify({id:company,name:'Grupo Lorena',commercial_name:'Grupo Lorena',logo:null}));sessionStorage.setItem('erp_permissions',JSON.stringify(['inventory:read','inventory:warehouse_receipts','inventory:receive','inventory:move','warehouses.view','locations.view']));sessionStorage.setItem('erp_is_superuser','false');},{theme,company});
   let mode='list';
   await page.route('**/api/v1/**',async route=>{
    const url=new URL(route.request().url());
    let body={};let status=200;
    if(url.pathname.endsWith('/inventory/preparation')) {if(mode==='loading')await new Promise(resolve=>setTimeout(resolve,1800));if(mode==='error'){status=503;body={message:'No se pudo conectar con la bodega. Reintenta la consulta.'};}else body=paged(mode==='empty'?[]:units);}
    else if(url.pathname.endsWith('/place')) { mode='empty';body={action:'place',handling_unit_id:unit.id,prepared_unit_id:unit.id,quantity_base:'50',movement_id:'movement-1'}; }
    else if(url.pathname.endsWith('/warehouses/'+warehouse.id)) body=warehouse;
    else if(url.pathname.endsWith('/warehouses')) body=paged([warehouse]);
    else if(url.pathname.endsWith('/warehouse-receipts')) body=paged([]);
    else if(url.pathname.includes('handling-units')) body=paged([]);
    else {status=400;body={message:'Operación no prevista en la evidencia visual.'};}
    await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
   });
   await page.goto('http://localhost:5173/qa-preparation?warehouse_id=warehouse-1',{waitUntil:'domcontentloaded',timeout:90000});
   await page.getByRole('button',{name:/Azúcar Glass Premium/}).waitFor({timeout:40000});
   await page.getByRole('button',{name:/Azúcar Glass Premium/}).click();
   await page.getByLabel(/Código de unidad o producto/).fill(unit.code);
   await page.getByLabel(/Código de unidad o producto/).press('Enter');
   const scannerFocus=await page.getByLabel(/Cantidad a ubicar/).evaluate(el=>el===document.activeElement);
   const placeholders=await page.locator('input[placeholder]').evaluateAll(elements=>elements.map(el=>{
    const rgb=color=>color.match(/[\d.]+/g).slice(0,3).map(Number);
    const lum=color=>rgb(color).map(x=>{x/=255;return x<=0.04045?x/12.92:((x+0.055)/1.055)**2.4;}).reduce((sum,x,i)=>sum+x*[0.2126,0.7152,0.0722][i],0);
    const fg=getComputedStyle(el,'::placeholder').color,bg=getComputedStyle(el).backgroundColor;
    const a=lum(fg),b=lum(bg);return {placeholder:el.placeholder,color:fg,background:bg,ratio:(Math.max(a,b)+0.05)/(Math.min(a,b)+0.05)};
   }));
   if(placeholders.some(p=>p.ratio<4.5))throw new Error('Placeholder contrast: '+JSON.stringify(placeholders));
   await page.screenshot({path:path.join(__dirname,`ubicacion-${theme}-${width}.png`),fullPage:true});
   results.push({theme,width,overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),scannerFocus,placeholders,errors});
   if(width===375 && theme==='dark') {
    await page.getByLabel(/Cantidad a ubicar/).fill('30');
    await page.getByLabel(/Cantidad a ubicar/).press('Enter');
    if(!await page.getByRole('button',{name:'Preparar porción',exact:true}).evaluate(el=>el===document.activeElement))throw new Error('Partial focus');
    await page.screenshot({path:path.join(__dirname,'porcion-dark-375.png'),fullPage:true});
    await page.getByRole('button',{name:'← Volver a pendientes',exact:true}).click();
    await page.getByRole('button',{name:/Caja de Cartón/}).click();
    await page.getByLabel(/Cantidad a ubicar/).press('Enter');
    if(!await page.getByLabel('Peso bruto (kg)').evaluate(el=>el===document.activeElement))throw new Error('Measurement focus');
    await page.getByRole('button',{name:'Confirmar medidas',exact:true}).click();
    await page.screenshot({path:path.join(__dirname,'medidas-error-dark-375.png'),fullPage:true});
    await page.getByLabel('Peso bruto (kg)').fill('5');
    if(await page.getByRole('alert').count())throw new Error('Stale validation');
    await page.getByRole('button',{name:'← Volver a pendientes',exact:true}).click();
    await page.getByRole('button',{name:/Café Tostado/}).click();await page.getByLabel(/Cantidad a ubicar/).press('Enter');
    if(!await page.getByRole('button',{name:'Revisar y colocar etiqueta',exact:true}).evaluate(el=>el===document.activeElement))throw new Error('Label focus');
    await page.getByRole('button',{name:'← Volver a pendientes',exact:true}).click();
    await page.getByRole('button',{name:/Azúcar Glass Premium/}).click();await page.getByLabel(/Código de unidad o producto/).fill(unit.code);await page.getByLabel(/Cantidad a ubicar/).press('Enter');
    if(!await page.getByLabel(/Código de ubicación/).evaluate(el=>el===document.activeElement))throw new Error('Location focus');
    await page.getByLabel(/Código de ubicación/).fill('A02-R01-N01-P01');await page.getByRole('button',{name:'Confirmar ubicación e ingresar',exact:true}).click();await page.getByText(/50 cj ingresaron/).waitFor();
    await page.screenshot({path:path.join(__dirname,'ingreso-success-dark-375.png'),fullPage:true});
    mode='empty';await page.getByRole('button',{name:'Actualizar',exact:true}).click();await page.getByText('No hay unidades pendientes').waitFor();
    await page.screenshot({path:path.join(__dirname,'vacio-dark-375.png'),fullPage:true});
    mode='error';await page.getByRole('button',{name:'Actualizar',exact:true}).click();await page.getByRole('alert').waitFor();
    await page.screenshot({path:path.join(__dirname,'red-error-dark-375.png'),fullPage:true});
    mode='list';await page.getByRole('button',{name:'Reintentar',exact:true}).click();await page.getByRole('button',{name:/Azúcar Glass Premium/}).waitFor();
    mode='loading';await page.getByRole('button',{name:'Actualizar',exact:true}).click();await page.getByLabel('Cargando pendientes').waitFor();await page.screenshot({path:path.join(__dirname,'cargando-dark-375.png'),fullPage:true});await page.getByRole('button',{name:/Azúcar Glass Premium/}).waitFor();
   }
   await page.close();
  }
  fs.writeFileSync(path.join(__dirname,'qa-results.json'),JSON.stringify(results,null,2));
  process.stdout.write(JSON.stringify(results));
  if(results.some(r=>r.overflow||!r.scannerFocus||r.errors.length))process.exitCode=1;
 } finally {await browser.close();}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
