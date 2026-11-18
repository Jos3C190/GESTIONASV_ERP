import { chromium } from '@playwright/test';
import * as path from 'path';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const htmlPath = path.resolve(process.cwd(), '../../reuniones-docs-erp/INFORME_TERCER_COMPUTO_ERP.html');
  const pdfPath = path.resolve(process.cwd(), '../../reuniones-docs-erp/INFORME_TERCER_COMPUTO_ERP.pdf');
  
  await page.goto(`file://${htmlPath}`, { waitUntil: 'networkidle' });
  await page.pdf({
    path: pdfPath,
    format: 'A4',
    printBackground: true,
    margin: { top: '10mm', bottom: '10mm', left: '10mm', right: '10mm' }
  });
  
  await browser.close();
  console.log('PDF Generated Successfully at:', pdfPath);
})();
