const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/rodri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const dir='C:/Developer/GESTIONASV_ERP/tmp/block5-review';fs.mkdirSync(dir,{recursive:true});
const privateData=fs.readFileSync('C:/Users/rodri/AppData/Local/Temp/gestionasv-rodrigo-molina-bodega-20261023.txt','utf8');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce',timezoneId:'America/El_Salvador'});
 const errors=[],downloads=[],calls=[];let mutations=0;
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().includes('/api/v1/inventory/')&&r.method()!=='GET')mutations++;});
 try{
  const deadline=Date.now()+240000;while(true){try{if((await page.request.get('http://localhost:5173/login',{timeout:10000})).ok())break;}catch{}if(Date.now()>deadline)throw new Error('Frontend readiness timeout');await new Promise(r=>setTimeout(r,2000));}
  await page.goto('http://localhost:5173/login',{waitUntil:'networkidle',timeout:90000});
  await page.locator('#login').fill(privateData.match(/^Usuario: (.+)$/m)[1].trim());await page.locator('#password').fill(privateData.match(/^Contraseña: (.+)$/m)[1].trim());
  await page.getByRole('button',{name:'Iniciar sesión'}).click();await page.waitForURL('**/companies');await page.getByRole('button').filter({hasText:'Grupo Lorena'}).first().click();await page.waitForURL('**/inventory');
  await page.goto('http://localhost:5173/inventory/kardex',{waitUntil:'networkidle'});
  await page.getByRole('button',{name:'Producto',exact:true}).click();await page.getByRole('dialog').locator('[data-product-result]').first().waitFor();
  const chocolate=page.getByRole('dialog').locator('[data-product-result]').filter({hasText:'Chocolate'});await (await chocolate.count()?chocolate.first():page.getByRole('dialog').locator('[data-product-result]').first()).click();
  await page.getByRole('region',{name:'Identificación y reportes de la consulta'}).waitFor({timeout:30000});
  assert.equal(await page.getByRole('tab',{name:'Valoración',exact:true}).count(),0);
  assert.equal(await page.getByRole('tab',{name:'Conciliación',exact:true}).count(),0);
  const dl=page.waitForEvent('download');await page.getByRole('button',{name:'Descargar PDF',exact:true}).click();const file=await dl;await file.saveAs(`${dir}/operator-physical.pdf`);downloads.push(file.suggestedFilename());
  await page.screenshot({path:`${dir}/operator-physical-light-1440.png`,fullPage:true});
  // Financial views use a labelled visual fixture. Actual administrator/export RBAC is verified by E2E.
  const fixture={context:{company_name:'Grupo Lorena, S.A. de C.V.',nit:'1217-060102-101-1',nrc:'Pendiente de verificación',product_name:'Azúcar Glass Premium 10kg',sku:'PRD-AZU-004',base_unit_symbol:'cj'},inventory_item_id:'visual-item',setting:{currency:'USD',opened_at:'2026-10-01T06:00:00Z',opening_reference:'CORTE-DEMO'},period_from:'2026-10-01',period_to:'2026-10-29',opening_known:true,opening_quantity:'0',opening_value:'0',closing_known:true,closing_quantity:'30',closing_value:'500',period_value_change:'500',entries:[],page:1,page_size:25,total:3};
  fixture.entries=[[5,50,5,50,'10'],[10,150,15,200,'13.333333'],[15,300,30,500,'16.666667']].map(([qty,value,bqty,bval,avg],i)=>({id:`entry-${i}`,sequence:i+1,kind:'receipt',quantity_base:String(qty),source_value:String(value),source_reference:`purchase-receipt:visual-${i}`,document_reference:`COM-000${27+i}`,operator:'compras.lorena',receipt_lot_code:`LOT-COM-000${27+i}`,applied_unit_cost:String(value/qty),original_entry_id:null,movement_line_id:null,purchase_detail_id:null,retaceo_id:null,operational_date:`2026-10-${27+i}`,accounting_date:`2026-10-${27+i}`,posted_at:`2026-10-${27+i}T15:00:00Z`,posted_by:'visual-user',inventory_delta:String(value),balance_quantity:String(bqty),balance_value:String(bval),average_unit_cost:avg,cost_breakdown:[]}));
  const recon={context:{...fixture.context,product_name:null,sku:null,base_unit_symbol:null},valuation_enabled:true,currency:'USD',as_of:'2026-10-29',generated_at:'2026-10-29T16:00:00Z',balance_known:true,inventory_value:'500',reconciled_items:1,discrepant_items:0,unvalued_items:0,items:[{inventory_item_id:'visual-item',product_name:fixture.context.product_name,sku:fixture.context.sku,base_unit_symbol:'cj',physical_quantity:'30',valued_quantity:'30',quantity_difference:'0',inventory_value:'500',average_unit_cost:'16.666667'}],page:1,page_size:50,total:1};
  await page.route('**/api/v1/inventory/kardex/reconciliation?*',async route=>{calls.push(new URL(route.request().url()).search);await route.fulfill({json:recon});});
  await page.route('**/api/v1/inventory/kardex/valuation?*',route=>route.fulfill({json:fixture}));
  await page.evaluate(async()=>{const {permissions}=await import('/src/lib/stores/permissions.svelte.ts');const {branch}=await import('/src/lib/stores/branch.svelte.ts');branch.configure({...branch.context,access_all_branches:true,last_branch_id:null});branch.select(null);permissions.set(['inventory:read','inventory:valuation'],false);});
  await page.getByRole('tab',{name:'Conciliación',exact:true}).click();await page.getByRole('button',{name:/Ver Kardex de Azúcar/}).first().click();await page.getByText('3 evento(s) · Página 1 de 1').waitFor();
  for(const [width,theme] of [[1440,'light'],[768,'light'],[375,'dark']]){
   await page.setViewportSize({width,height:1000});await page.evaluate(t=>document.documentElement.setAttribute('data-theme',t),theme);await page.getByRole('heading',{name:'Kardex',exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:`${dir}/valuation-visual-fixture-${width}-${theme}.png`,fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.locator('[role="tabpanel"] :is(table,article):visible').last().scrollIntoViewIfNeeded();await page.screenshot({path:`${dir}/valuation-history-${width}-${theme}.png`,fullPage:true});
  }
  await page.getByRole('tab',{name:'Conciliación',exact:true}).click();await page.getByLabel('Producto o código').fill('Azúcar');await page.getByRole('button',{name:'Consultar corte',exact:true}).click();await page.getByRole('region',{name:'Identificación y reportes de la consulta'}).waitFor();await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Consultar corte'&&!b.disabled));
  assert(calls.some(q=>q.includes('q=Az%C3%BAcar')));
  for(const [width,theme] of [[1440,'light'],[768,'dark'],[375,'light']]){
   await page.setViewportSize({width,height:1000});await page.evaluate(t=>document.documentElement.setAttribute('data-theme',t),theme);await page.getByRole('heading',{name:'Kardex',exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:`${dir}/reconciliation-visual-fixture-${width}-${theme}.png`,fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.getByRole('button',{name:/Ver Kardex de Azúcar/}).first().scrollIntoViewIfNeeded();await page.screenshot({path:`${dir}/reconciliation-result-${width}-${theme}.png`,fullPage:true});
  }
  await page.route('**/api/v1/inventory/kardex/reconciliation?*',route=>route.fulfill({status:503,json:{message:'No se pudo consultar la conciliación.'}}));await page.getByRole('button',{name:'Consultar corte',exact:true}).click();await page.getByRole('alert').waitFor();await page.screenshot({path:`${dir}/reconciliation-error-375.png`,fullPage:true});assert.equal(await page.getByRole('button',{name:'Descargar PDF',exact:true}).count(),0);
  assert.equal(mutations,0);assert.equal(errors.length,0,errors.join('\n'));fs.writeFileSync(`${dir}/result.json`,JSON.stringify({ok:true,errors,downloads,calls,mutations,financialViewsVisualFixture:true},null,2));
 }catch(e){await page.screenshot({path:`${dir}/failure.png`,fullPage:true});fs.writeFileSync(`${dir}/result.json`,JSON.stringify({ok:false,error:e.message,errors,mutations},null,2));process.exitCode=1;}finally{await browser.close();}
})();
