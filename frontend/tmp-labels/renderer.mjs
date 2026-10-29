export const DEFAULT_LABEL_LAYOUT = {
    content: 'full',
    width_mm: 100,
    height_mm: 125
};
export const LABEL_CONTENT_NAMES = {
    full: 'Etiqueta completa',
    qr: 'Viñeta QR',
    barcode: 'Viñeta Code 128'
};
export const LABEL_SIZES = {
    full: [
        [80, 80],
        [100, 125],
        [100, 150]
    ],
    qr: [
        [50, 70],
        [60, 80],
        [80, 80]
    ],
    barcode: [
        [80, 50],
        [50, 50],
        [80, 80]
    ]
};
export const MINIMUM_LABEL_SIZES = {
    full: [80, 80],
    qr: [50, 60],
    barcode: [50, 50]
};
export function labelDataFromSnapshot(snapshot) {
    function required(key) {
        const value = snapshot[key];
        if (typeof value !== 'string' || !value.trim())
            throw new Error('La impresión no contiene todos los datos de la unidad. Actualiza la vista previa.');
        return value;
    }
    function optional(key) {
        return typeof snapshot[key] === 'string' ? snapshot[key] : null;
    }
    return {
        product_internal_code: required('product_internal_code'),
        product_name: required('product_name'),
        handling_unit_code: optional('handling_unit_code'),
        receipt_lot_code: required('receipt_lot_code'),
        manufacturer_lot_code: optional('manufacturer_lot_code'),
        received_on: required('received_on'),
        quantity_base: required('quantity_base'),
        base_unit_symbol: required('base_unit_symbol'),
        presentation_equivalence: optional('presentation_equivalence'),
        expiry_date: optional('expiry_date'),
        notes: optional('notes')
    };
}
export function labelCopiesIssue(copies) {
    const count = Number(copies);
    return !Number.isInteger(count) || count < 1 || count > 100
        ? 'Indica entre 1 y 100 copias.'
        : null;
}
export function labelDimensionIssue(layout, field) {
    const minimum = MINIMUM_LABEL_SIZES[layout.content][field === 'width_mm' ? 0 : 1];
    const value = layout[field];
    const name = field === 'width_mm' ? 'ancho' : 'alto';
    return !Number.isInteger(value) || value < minimum || value > 200
        ? `Indica un ${name} de ${minimum} a 200 mm, en milímetros enteros.`
        : null;
}
export function labelLayoutIssue(layout, code, qrModules) {
    const { content, width_mm: width, height_mm: height } = layout;
    if (!['full', 'qr', 'barcode'].includes(content))
        return 'Selecciona el contenido de la impresión.';
    const dimensionIssue = labelDimensionIssue(layout, 'width_mm') ?? labelDimensionIssue(layout, 'height_mm');
    if (dimensionIssue)
        return dimensionIssue;
    if (content !== 'qr') {
        if (!code || !/^[\x20-\x7E]+$/.test(code))
            return 'El código interno no puede representarse en Code 128. Usa una viñeta QR o revisa el código del producto.';
        const minimumWidth = Math.ceil((11 * (code.length + 2) + 13 + 20) * 0.25 + 4);
        if (width < minimumWidth)
            return `Este Code 128 necesita al menos ${minimumWidth} mm de ancho. Elige un tamaño mayor o una viñeta QR.`;
    }
    if (content !== 'barcode' && qrModules !== null) {
        const edge = content === 'qr' ? Math.min(32, width - 4, height - 30) : 24;
        if (edge / (qrModules + 8) < 0.3)
            return 'El QR necesita más espacio para este enlace. Usa una viñeta QR de mayor tamaño.';
    }
    return null;
}
function escapeHtml(value) {
    return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
}
// Dates belong to the receipt lot. Never derive them from the print date or SKU.
function labelDate(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})(?:$|T)/.exec(value);
    return match ? `${match[3]}/${match[2]}/${match[1]}` : value;
}
export function buildLabelPrintDocument(data, layout, qrDataUrl, barcodeSvg, copies = 1) {
    const issue = labelLayoutIssue(layout, data.product_internal_code, null);
    if (issue)
        throw new Error(issue);
    if ((data.notes?.length ?? 0) > 160)
        throw new Error('Las observaciones de la etiqueta admiten hasta 160 caracteres.');
    if (!Number.isInteger(copies) || copies < 1 || copies > 100)
        throw new Error('Indica entre 1 y 100 copias.');
    if (layout.content !== 'barcode' &&
        (!qrDataUrl || !/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(qrDataUrl))) {
        throw new Error('Espera a que termine de generarse el código QR.');
    }
    if (layout.content !== 'qr' && !barcodeSvg)
        throw new Error('Espera a que termine de generarse el código Code 128.');
    const qr = layout.content !== 'barcode'
        ? `<img class="qr-symbol" src="${qrDataUrl}" alt="QR de trazabilidad de la unidad" />`
        : '';
    // SVG comes exclusively from the local JsBarcode renderer, never from API HTML.
    const barcode = layout.content !== 'qr' ? `<div class="barcode">${barcodeSvg}</div>` : '';
    const identity = `<h1>${escapeHtml(data.product_name)}</h1>`;
    const code = `<p class="code">${escapeHtml(data.product_internal_code)}</p>`;
    const trace = `<div class="trace"><p class="lot">Lote: <strong>${escapeHtml(data.receipt_lot_code)}</strong></p>
    <p>Recepción: <strong>${escapeHtml(labelDate(data.received_on))}</strong></p>
    ${data.expiry_date ? `<p>Vencimiento: <strong>${escapeHtml(labelDate(data.expiry_date))}</strong></p>` : ''}
    ${data.handling_unit_code ? `<p class="unit">Unidad: ${escapeHtml(data.handling_unit_code)}</p>` : ''}</div>`;
    const notes = data.notes?.trim()
        ? `<p class="notes"><strong>Observaciones:</strong> ${escapeHtml(data.notes.trim())}</p>`
        : '';
    const field = (title, value, wide = false) => `<div${wide ? ' class="wide"' : ''}><dt>${title}</dt><dd>${escapeHtml(value)}</dd></div>`;
    let body;
    if (layout.content === 'qr')
        body = `${identity}${qr}${code}${trace}${notes}`;
    else if (layout.content === 'barcode')
        body = `${identity}${barcode}${code}${trace}${notes}`;
    else
        body = `
    <header><strong>GestionaSV · Inventario</strong><span>${escapeHtml(data.handling_unit_code ?? '')}</span></header>
    ${identity}${barcode}${code}${trace}
    <div class="details">${qr}<dl>
      ${field('Cantidad', `${data.quantity_base} ${data.base_unit_symbol}`, true)}
      ${field('Lote del fabricante', data.manufacturer_lot_code ?? 'No informado', true)}
    </dl></div>
    ${data.presentation_equivalence ? `<p class="presentation"><strong>Presentación y equivalencia</strong><br />${escapeHtml(data.presentation_equivalence)}</p>` : ''}${notes}`;
    const { width_mm: width, height_mm: height, content } = layout;
    const qrSize = content === 'qr' ? Math.min(32, width - 4, height - 30) : 24;
    const barcodeHeight = content === 'barcode' ? 12 : 10;
    const pages = Array.from({ length: copies }, () => `<article class="label label--${content}">${body}</article>`).join('');
    return `<!doctype html><html lang="es"><head><meta charset="utf-8" />
    <title>${escapeHtml(LABEL_CONTENT_NAMES[content])} · ${escapeHtml(data.product_internal_code)}</title>
    <style>
      @page { size: ${width}mm ${height}mm; margin: 0; }
      * { box-sizing: border-box; }
      html, body { margin: 0; padding: 0; color: #111; background: white; font-family: Arial, sans-serif; }
      .label { width: ${width}mm; height: ${height}mm; padding: 2mm; display: flex; flex-direction: column; gap: 1mm; overflow: hidden; break-after: page; page-break-after: always; }
      .label:last-child { break-after: auto; page-break-after: auto; }
      .label > * { flex-shrink: 0; }
      p, h1, dl, dd { margin: 0; }
      header { display: flex; justify-content: space-between; gap: 2mm; font-size: 2mm; border-bottom: 0.2mm solid #bbb; padding-bottom: 1mm; }
      header span { font-family: monospace; overflow-wrap: anywhere; }
      h1 { width: 100%; font-size: 3mm; line-height: 1.15; overflow-wrap: anywhere; }
      .barcode { width: 100%; height: ${barcodeHeight}mm; }
      .barcode svg { display: block; width: 100%; height: 100%; }
      .code { text-align: center; font: bold 2.4mm/1.1 monospace; overflow-wrap: anywhere; }
      .trace { width: 100%; font-size: 2.4mm; line-height: 1.2; overflow-wrap: anywhere; }
      .lot, .unit { font-family: monospace; }
      .qr-symbol { display: block; width: ${qrSize}mm; height: ${qrSize}mm; object-fit: contain; image-rendering: pixelated; }
      .details { display: grid; grid-template-columns: 24mm minmax(0, 1fr); gap: 2mm; align-items: start; }
      dl { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5mm; min-width: 0; }
      dl > div { min-width: 0; }
      .wide { grid-column: 1 / -1; }
      dt { font-size: 2mm; line-height: 1.15; color: #444; }
      dd { font-size: 2.2mm; line-height: 1.15; font-weight: bold; overflow-wrap: anywhere; }
      .presentation { border-top: 0.2mm solid #bbb; padding-top: 1mm; font-size: 2.1mm; line-height: 1.15; overflow-wrap: anywhere; }
      .notes { width: 100%; font-size: 2.2mm; line-height: 1.2; overflow-wrap: anywhere; }
      .label--qr, .label--barcode { align-items: center; justify-content: center; gap: 0.75mm; }
      .label--qr h1, .label--barcode h1 { text-align: center; text-wrap: balance; }
      .label--qr .trace, .label--barcode .trace { text-align: center; border-top: 0.2mm solid #bbb; padding-top: 0.8mm; }
      .label--qr .trace p + p, .label--barcode .trace p + p { margin-top: 0.5mm; }
      .label--qr .lot, .label--barcode .lot { font: 2mm/1.25 Arial, sans-serif; color: #444; }
      .label--qr .lot strong, .label--barcode .lot strong { display: block; margin-top: 0.35mm; color: #111; font: bold 2.25mm/1.2 monospace; }
      .label--qr .unit, .label--barcode .unit { font-size: 2.2mm; color: #333; }
      .code { width: 100%; }
    </style></head><body>${pages}</body></html>`;
}
export function assertLabelDocumentFits(document) {
    const labels = document.querySelectorAll('.label');
    if (!labels.length)
        throw new Error('No se pudo preparar la vista de impresión.');
    for (const label of labels) {
        if (label.scrollHeight > label.clientHeight + 1 || label.scrollWidth > label.clientWidth + 1) {
            throw new Error('El contenido no cabe en la medida elegida. Selecciona una etiqueta más grande o una viñeta con menos datos.');
        }
    }
}
export async function prepareLabelPrintWindow(target, html) {
    if (target.closed)
        throw new Error('La ventana de impresión se cerró. Vuelve a intentarlo.');
    target.document.open();
    target.document.write(html);
    target.document.close();
    await target.document.fonts?.ready;
    await Promise.all(Array.from(target.document.images, (image) => image.decode()));
    if (target.closed)
        throw new Error('La ventana de impresión se cerró. Vuelve a intentarlo.');
    assertLabelDocumentFits(target.document);
}
