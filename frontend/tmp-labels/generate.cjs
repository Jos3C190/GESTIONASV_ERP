const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const ts = require('typescript');
const QRCode = require('qrcode');
const JsBarcode = require('jsbarcode');
(async () => {
  const { Window } = await import('happy-dom');
  const document = new Window().document;
  global.document = document;
  const source = fs.readFileSync('src/lib/features/inventory/label-printing.ts', 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 }
  }).outputText;
  fs.writeFileSync('tmp-labels/renderer.mjs', compiled);
  const { buildLabelPrintDocument, LABEL_SIZES } = await import(pathToFileURL(path.resolve('tmp-labels/renderer.mjs')));
  const data = {
    product_internal_code: 'INT-004', product_name: 'Azúcar Glass Premium 10kg',
    handling_unit_code: 'HU-DD17851A961041B8',
    receipt_lot_code: 'LOT-COM-00027-DD3EB6A00CFDB48C49D4AED9BCCDAF3F5',
    manufacturer_lot_code: 'FAB-2026-10', received_on: '2026-10-28',
    quantity_base: '10', base_unit_symbol: 'cj', presentation_equivalence: null,
    expiry_date: '2027-02-01', notes: 'Mantener seco'
  };
  const url = 'https://gestionasv.example/inventory/trace#demo-label-token';
  const qr = await QRCode.toDataURL(url, { margin: 4, width: 512, errorCorrectionLevel: 'M' });
  fs.writeFileSync('tmp-labels/qr-dataurl.txt', qr);
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  JsBarcode(svg, data.product_internal_code, {
    format: 'CODE128B', displayValue: false, height: 52, width: 2,
    margin: 4, marginLeft: 20, marginRight: 20
  });
  svg.setAttribute('preserveAspectRatio', 'none');
  for (const content of ['full', 'qr', 'barcode']) {
    for (const [width_mm, height_mm] of LABEL_SIZES[content]) {
      fs.writeFileSync(`tmp-labels/papel-${content}-${width_mm}x${height_mm}.html`,
        buildLabelPrintDocument(data, { content, width_mm, height_mm }, qr, svg.outerHTML));
    }
  }
  fs.writeFileSync('tmp-labels/papel-dos-copias.html',
    buildLabelPrintDocument(data, { content: 'barcode', width_mm: 80, height_mm: 50 }, qr, svg.outerHTML, 2));
})();
