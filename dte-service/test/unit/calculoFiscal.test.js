const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const {
  calcularVentasPorCategoria,
  calcularPorcentajeDescuento,
  aplicarDescuentoGlobal,
  validarLineas,
  redondear,
  prorratearCentavos,
} = require('../../src/services/calculoFiscal');

describe('calculoFiscal.js', () => {
  test('suma ventas por categoría y deja los descuentos globales del resumen en 0', () => {
    const r = calcularVentasPorCategoria([
      { ventaGravada: 90, montoDescu: 10 },
      { ventaExenta: 50 },
      { ventaNoSuj: 20 },
      { noGravado: 3.5 },
    ]);
    assert.equal(r.totalGravada, 90);
    assert.equal(r.totalExenta, 50);
    assert.equal(r.totalNoSuj, 20);
    assert.equal(r.totalNoGravado, 3.5);
    // descuGravada/Exenta/NoSuj son descuentos GLOBALES (Manual Funcional XVIII).
    assert.equal(r.descuGravada, 0);
    assert.equal(r.descuExenta, 0);
    assert.equal(r.descuNoSuj, 0);
    // totalDescu informa los descuentos por ítem.
    assert.equal(r.totalDescu, 10);
  });

  test('ignora líneas sin montoDescu (undefined se trata como 0)', () => {
    const r = calcularVentasPorCategoria([{ ventaGravada: 100 }]);
    assert.equal(r.totalDescu, 0);
  });

  test('redondea half-up como exige el Manual Funcional XXI (5.664→5.66, 5.665→5.67)', () => {
    assert.equal(redondear(5.664), 5.66);
    assert.equal(redondear(5.665), 5.67);
    assert.equal(redondear(5.666), 5.67);
    assert.equal(redondear(1.005), 1.01); // toFixed daría 1.00
    assert.equal(redondear(90.675), 90.68);
    assert.equal(redondear(1.87654321987654, 8), 1.87654322);
    assert.equal(redondear(3.555555554, 8), 3.55555555);
  });

  test('calcularPorcentajeDescuento reconstruye la base pre-descuento correctamente', () => {
    assert.equal(calcularPorcentajeDescuento(90, 10), 10);
    assert.equal(calcularPorcentajeDescuento(100, 0), 0);
    assert.equal(calcularPorcentajeDescuento(0, 0), 0);
  });
});

describe('validarLineas', () => {
  test('acepta la línea del ejemplo oficial: 10 × 11.00 − 10.00 = 100.00 (MF XVIII)', () => {
    assert.doesNotThrow(() => validarLineas([
      { descripcion: 'Camisas', cantidad: 10, precioUni: 11, montoDescu: 10, ventaGravada: 100 },
      { descripcion: 'Centros', cantidad: 15, precioUni: 5, montoDescu: 0, ventaGravada: 75 },
    ]));
  });

  test('acepta diferencias dentro de la holgura de ±0.01 (MF XXI)', () => {
    assert.doesNotThrow(() => validarLineas([
      { descripcion: 'Holgura', cantidad: 1.1219999999, precioUni: 2, ventaGravada: 2.25 },
    ]));
  });

  test('rechaza una línea donde cantidad × precio − descuento no coincide con la venta', () => {
    assert.throws(
      () => validarLineas([{ descripcion: 'Camiseta', cantidad: 2, precioUni: 19.91, montoDescu: 5, ventaGravada: 39.82 }]),
      (error) => error.code === 'INVALID_DTE_REQUEST' && /no coincide/.test(error.message),
    );
  });

  test('rechaza montos negativos y cantidades no positivas', () => {
    assert.throws(() => validarLineas([{ descripcion: 'X', cantidad: 0, precioUni: 1, ventaGravada: 0 }]), /cantidad/);
    assert.throws(() => validarLineas([{ descripcion: 'X', cantidad: 1, precioUni: -1, ventaGravada: 0 }]), /precioUni/);
    assert.throws(() => validarLineas([{ descripcion: 'X', cantidad: 1, precioUni: 1, montoDescu: -1, ventaGravada: 2 }]), /montoDescu/);
  });

  test('exige al menos una venta mayor a cero para cargos que no afectan la base (MF XII)', () => {
    assert.throws(
      () => validarLineas([{ descripcion: 'Envío', cantidad: 1, precioUni: 0, ventaGravada: 0, noGravado: 3.5 }]),
      /al menos una venta/,
    );
    assert.doesNotThrow(() => validarLineas([
      { descripcion: 'Producto', cantidad: 1, precioUni: 10, ventaGravada: 10 },
      { descripcion: 'Envío', cantidad: 1, precioUni: 0, ventaGravada: 0, noGravado: 3.5 },
    ]));
  });
});

describe('aplicarDescuentoGlobal', () => {
  test('sin descuentoGlobal (null), devuelve los items sin tocar', () => {
    const items = [{ ventaGravada: 100 }];
    assert.deepEqual(aplicarDescuentoGlobal(items, null), items);
  });

  test('reparte el descuento global proporcionalmente y lo suma a montoDescu', () => {
    const items = [
      { ventaGravada: 100, montoDescu: 5, descripcion: 'A' },
      { ventaGravada: 300, descripcion: 'B' },
    ];
    const resultado = aplicarDescuentoGlobal(items, { gravada: 40 });
    assert.equal(resultado[0].ventaGravada, 90);
    assert.equal(resultado[1].ventaGravada, 270);
    assert.equal(resultado[0].montoDescu, 15);
    assert.equal(resultado[1].montoDescu, 30);
  });

  test('el prorrateo suma exactamente el descuento global, sin perder centavos', () => {
    const items = [{ ventaGravada: 33.33 }, { ventaGravada: 33.33 }, { ventaGravada: 33.34 }];
    const resultado = aplicarDescuentoGlobal(items, { gravada: 10 });
    const descontado = resultado.reduce((suma, item) => suma + item.montoDescu, 0);
    assert.equal(redondear(descontado), 10);
  });

  test('reparte descuento global entre gravada/exenta/noSuj de forma independiente', () => {
    const items = [{ ventaGravada: 100 }, { ventaExenta: 100 }, { ventaNoSuj: 100 }];
    const resultado = aplicarDescuentoGlobal(items, { gravada: 10, exenta: 20, noSuj: 30 });
    assert.equal(resultado[0].ventaGravada, 90);
    assert.equal(resultado[1].ventaExenta, 80);
    assert.equal(resultado[2].ventaNoSuj, 70);
  });

  test('descarta el IVA por línea enviado cuando cambia la base gravada', () => {
    const resultado = aplicarDescuentoGlobal([{ ventaGravada: 100, ivaItem: 13 }, { ventaExenta: 10, ivaItem: 0 }], { gravada: 10 });
    assert.equal('ivaItem' in resultado[0], false);
    assert.equal('ivaItem' in resultado[1], false);
  });

  test('rechaza un descuento global mayor que la categoría', () => {
    assert.throws(() => aplicarDescuentoGlobal([{ ventaGravada: 10 }], { gravada: 11 }), /excede/);
  });

  test('no muta el arreglo original de items', () => {
    const items = [{ ventaGravada: 100 }];
    aplicarDescuentoGlobal(items, { gravada: 10 });
    assert.equal(items[0].ventaGravada, 100);
  });

  test('prorratearCentavos reparte por mayor residuo con suma exacta', () => {
    assert.deepEqual(prorratearCentavos(100, [1, 1, 1]), [34, 33, 33]);
    assert.deepEqual(prorratearCentavos(0, [1, 2]), [0, 0]);
  });
});
