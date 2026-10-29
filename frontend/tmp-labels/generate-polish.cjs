const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const QRCode = require('qrcode');
const JsBarcode = require('jsbarcode');
(async () => {
  const { Window } = await import('happy-dom');
  const document = new Window().document;
  global.document = document;
  const { buildLabelPrintDocument } = await import(pathToFileURL(path.resolve('tmp-labels/renderer.mjs')));
  const qr = await QRCode.toDataURL('https://gestionasv.example/inventory/trace#demo-label-token', { margin: 4, width: 512, errorCorrectionLevel: 'M' });
  const data = {
    product_internal_code: 'ERS-LATE-B1B55D6D',
    product_name: 'Artículo demostración integral ERS-LATE-B1B55D6D',
    handling_unit_code: 'HU-RET-222B0730708C466E',
    receipt_lot_code: 'LOT-COM-00019-D88B7BDD4045D4013B47DACFD2A8B5843',
    manufacturer_lot_code: null, received_on: '2026-10-20',
    quantity_base: '1', base_unit_symbol: 'u', presentation_equivalence: null,
    expiry_date: null, notes: null
  };
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  JsBarcode(svg, data.product_internal_code, { format: 'CODE128B', displayValue: false, height: 52, width: 2, margin: 4, marginLeft: 20, marginRight: 20 });
  svg.setAttribute('preserveAspectRatio', 'none');
  for (const [content, width_mm, height_mm] of [['qr', 50, 70], ['barcode', 80, 50]]) {
    for (const [suffix, notes] of [['', null], ['-notas', 'Conservar en lugar fresco y seco, protegido de la humedad.']]) {
      fs.writeFileSync(`tmp-labels/retoque-${content}${suffix}.html`, buildLabelPrintDocument({ ...data, notes }, { content, width_mm, height_mm }, qr, svg.outerHTML));
    }
  }
})();
