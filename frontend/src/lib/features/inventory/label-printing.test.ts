import JsBarcode from 'jsbarcode';
import { describe, expect, it } from 'vitest';
import {
  buildLabelPrintDocument,
  labelDataFromSnapshot,
  labelLayoutIssue,
  LABEL_SIZES,
  type LabelPrintData
} from './label-printing';

const data: LabelPrintData = {
  product_internal_code: 'INT-004',
  product_name: 'Azúcar Glass Premium 10kg',
  handling_unit_code: 'HU-0123456789',
  receipt_lot_code: 'LOT-COM-00027-DD3EB6A00CFDB48C49D4AED9BCCDAF3F5',
  manufacturer_lot_code: 'FAB-20',
  received_on: '2026-10-28',
  quantity_base: '10',
  base_unit_symbol: 'cj',
  presentation_equivalence: null,
  expiry_date: '2027-02-01'
};

function barcode(code = data.product_internal_code) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  JsBarcode(svg, code, { format: 'CODE128B', displayValue: false, margin: 20 });
  return svg.outerHTML;
}

describe('inventory labels with visible receipt identity', () => {
  it.each(['full', 'qr', 'barcode'] as const)(
    'prints product, lot and receipt/expiry dates in %s without changing their source',
    (content) => {
      const [width, height] = LABEL_SIZES[content][0];
      const html = buildLabelPrintDocument(
        data,
        { content, width_mm: width, height_mm: height },
        'data:image/png;base64,AA==',
        barcode(),
        2
      );
      const doc = new DOMParser().parseFromString(html, 'text/html');
      const labels = doc.querySelectorAll('.label');
      expect(labels).toHaveLength(2);
      for (const label of labels) {
        expect(label.textContent).toContain(data.product_name);
        expect(label.textContent).toContain(data.product_internal_code);
        expect(label.textContent).toContain(data.receipt_lot_code);
        expect(label.textContent).toContain('28/10/2026');
        expect(label.textContent).toContain('01/02/2027');
        expect(label.textContent).toContain(data.handling_unit_code);
        expect(label.querySelectorAll('svg')).toHaveLength(content === 'qr' ? 0 : 1);
        expect(label.querySelectorAll('img')).toHaveLength(content === 'barcode' ? 0 : 1);
      }
    }
  );

  it('escapes optional notes and keeps nonperishable labels free of invented dates', () => {
    const html = buildLabelPrintDocument(
      { ...data, expiry_date: null, notes: '<script>alert(1)</script> & mantener seco' },
      { content: 'barcode', width_mm: 80, height_mm: 80 },
      null,
      barcode()
    );
    const doc = new DOMParser().parseFromString(html, 'text/html');
    expect(doc.querySelector('script')).toBeNull();
    expect(doc.body.textContent).toContain('<script>alert(1)</script> & mantener seco');
    expect(doc.body.textContent).not.toContain('Vencimiento:');
    expect(() =>
      buildLabelPrintDocument(
        { ...data, notes: 'x'.repeat(161) },
        { content: 'barcode', width_mm: 80, height_mm: 80 },
        null,
        barcode()
      )
    ).toThrow('160 caracteres');
  });

  it('distinguishes two receipts of the same product and reuses the saved receipt on reprint', () => {
    const snapshot = { ...data, received_on: '2026-09-02', notes: 'Mantener seco' };
    const saved = labelDataFromSnapshot(snapshot);
    const html = buildLabelPrintDocument(
      saved,
      { content: 'barcode', width_mm: 80, height_mm: 80 },
      null,
      barcode()
    );
    expect(html).toContain('02/09/2026');
    expect(html).toContain('Mantener seco');
    const other = buildLabelPrintDocument(
      { ...data, receipt_lot_code: 'LOT-COM-00028' },
      { content: 'barcode', width_mm: 80, height_mm: 80 },
      null,
      barcode()
    );
    expect(other).toContain('LOT-COM-00028');
    expect(other).not.toContain(data.receipt_lot_code);
  });

  it('rejects undersized stock, incompatible codes, and dense QR layouts', () => {
    expect(
      labelLayoutIssue({ content: 'qr', width_mm: 25, height_mm: 35 }, 'INT-004', 49)
    ).toContain('ancho de 50');
    expect(
      labelLayoutIssue({ content: 'barcode', width_mm: 50, height_mm: 25 }, 'INT-004', null)
    ).toContain('alto de 50');
    expect(
      labelLayoutIssue({ content: 'barcode', width_mm: 80, height_mm: 50 }, 'AZÚCAR', null)
    ).toContain('no puede representarse');
    expect(
      labelLayoutIssue({ content: 'qr', width_mm: 50, height_mm: 70 }, 'AZÚCAR', 177)
    ).toContain('más espacio');
    expect(
      labelLayoutIssue({ content: 'barcode', width_mm: 50, height_mm: 50 }, 'X'.repeat(50), null)
    ).toContain('necesita al menos');
  });
});
