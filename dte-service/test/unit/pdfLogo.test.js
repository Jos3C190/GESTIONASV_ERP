const { test } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { generarPDF } = require('../../src/services/representacionGraficaBuilder');
const { construirFactura, construirCCF } = require('../../src/services/dteBuilder');
const correlativoStore = require('../../src/services/correlativoStore');
const { contarPaginas, textoCompleto } = require('./_pdfTexto');

// PNG RGBA de 1 × 1 píxel; fixture mínima, no depende de recursos remotos.
const logo = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACXBIWXMAAAPoAAAD6AG1e1JrAAAADUlEQVR4nGMQCVjwHwADhAIEWAExyQAAAABJRU5ErkJggg==', 'base64');

test('Factura 01 admite logo visual opcional sin modificar el JSON fiscal', async () => {
  correlativoStore.reiniciarAMemoria();
  const { dte } = construirFactura({ receptor: null, items: [{ descripcion: 'Producto', cantidad: 1, precioUni: 10, ventaGravada: 10 }] });
  const before = JSON.stringify(dte);
  const pdf = await generarPDF(dte, { selloRecepcion: 'SELLO-TEST', ambiente: dte.identificacion.ambiente, logoPngBuffer: logo });
  assert.equal(pdf.subarray(0, 4).toString(), '%PDF');
  assert.equal(JSON.stringify(dte), before);
});

test('Comprobante 03 admite el mismo logo y conserva el DTE intacto', async () => {
  correlativoStore.reiniciarAMemoria();
  const { dte } = construirCCF({
    receptor: { nit: '06141804941099', nrc: '7654321', nombre: 'Prueba S.A.', codActividad: '62010', descActividad: 'Programación informática', direccion: { departamento: '06', municipio: '20', distrito: '01', complemento: 'San Salvador' }, telefono: '22223333', correo: 'prueba@example.com' },
    items: [{ descripcion: 'Producto', cantidad: 1, precioUni: 10, ventaGravada: 10 }],
  });
  const before = JSON.stringify(dte);
  const pdf = await generarPDF(dte, { selloRecepcion: 'SELLO-TEST', ambiente: dte.identificacion.ambiente, logoPngBuffer: logo });
  assert.equal(pdf.subarray(0, 4).toString(), '%PDF');
  assert.equal(contarPaginas(pdf), 1, 'Un CCF corto con logo y QR debe caber en una página');
  assert.equal(JSON.stringify(dte), before);
});

test('Factura con receptor completo, logo, QR y dirección larga cabe en una página', async () => {
  correlativoStore.reiniciarAMemoria();
  const direccion = {
    departamento: '06', municipio: '23', distrito: '14',
    complemento: 'Calle El Mirador entre 87 y 89 Av. Norte, Local Ofi-19-01B, Edificio Torre Futura, complejo World Trade Center, Colonia Escalón',
  };
  const { dte } = construirFactura({
    receptor: { tipoDocumento: '13', numDocumento: '012345678', nombre: 'Cliente con nombre extenso de prueba', correo: 'cliente@example.com', telefono: '77778888', direccion },
    // Factura: precio y venta con el IVA incluido (11.30 = 10.00 + 1.30 de IVA).
    items: [{ descripcion: 'Producto', cantidad: 1, precioUni: 11.3, ventaGravada: 11.3, ivaItem: 1.3, codigo: 'cmf3k2v0x0001abcd' }],
    pago: { codigo: '03', montoPago: 11.3, referencia: 'ORD-2026-000123' },
  });
  const pdf = await generarPDF(dte, { selloRecepcion: 'SELLO-TEST', ambiente: dte.identificacion.ambiente, logoPngBuffer: logo });
  assert.equal(contarPaginas(pdf), 1);
});

test('Factura simulada con logo conserva la marca de simulación en una sola página', async () => {
  correlativoStore.reiniciarAMemoria();
  const { dte } = construirFactura({ receptor: null, items: [{ descripcion: 'Producto', cantidad: 1, precioUni: 10, ventaGravada: 10 }] });
  const pdf = await generarPDF(dte, {
    selloRecepcion: 'SIMULATED-1234567890', ambiente: dte.identificacion.ambiente, simulation: true, logoPngBuffer: logo,
  });
  assert.equal(contarPaginas(pdf), 1);
  assert.match(textoCompleto(pdf), /SIMULADO - SIN VALIDEZ FISCAL/);
});
