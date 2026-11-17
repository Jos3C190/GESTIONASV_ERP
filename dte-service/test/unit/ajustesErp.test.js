/**
 * Ajustes del ERP (bloque V3b): condición, plazo, retención, percepción y
 * descuento global en el resumen. El DTE resultante debe validar contra el
 * schema oficial y cuadrar con los totales que calculó el ERP.
 */
const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { construirFactura, construirCCF } = require('../../src/services/dteBuilder');
const { validarDte } = require('../../src/validators/dteSchema');

const RECEPTOR_CCF = {
  nit: '06141804941099',
  nrc: '7654321',
  nombre: 'Cliente Empresa S.A.',
  codActividad: '62010',
  descActividad: 'Programación informática',
  direccion: { departamento: '06', municipio: '20', distrito: '01', complemento: 'Otra dirección' },
  telefono: '22223333',
  correo: 'cliente@empresa.com',
};

function error(fn) {
  try {
    fn();
  } catch (err) {
    return err.message;
  }
  return null;
}

describe('ajustes del ERP', () => {
  test('factura: el descuento global queda en el resumen y las líneas no cambian', () => {
    const items = [
      { descripcion: 'Pan dulce', cantidad: 2, precioUni: 56.5, ventaGravada: 113 },
      { descripcion: 'Pastel', cantidad: 1, precioUni: 113, ventaGravada: 113 },
    ];
    const { dte } = construirFactura({
      receptor: null,
      items,
      descuentoGlobal: { gravada: 22.6 },
      ajustes: { descuentoGlobalEnResumen: true },
      pago: { codigo: '01', montoPago: 203.4, referencia: null, numPagoElectronico: null },
    });
    assert.deepEqual(dte.cuerpoDocumento.map((l) => [l.montoDescu, l.ventaGravada]), [[0, 113], [0, 113]]);
    assert.equal(dte.resumen.descuGravada, 22.6);
    assert.equal(dte.resumen.totalDescu, 22.6);
    assert.equal(dte.resumen.subTotal, 203.4);
    assert.equal(dte.resumen.totalIva, 23.4);
    assert.equal(dte.resumen.totalPagar, 203.4);
    assert.equal(dte.resumen.porcentajeDescuento, 10);
    assert.equal(validarDte(dte).valido, true, JSON.stringify(validarDte(dte).errores));
  });

  test('CCF a crédito con retención: condición, plazo y total a pagar', () => {
    const { dte } = construirCCF({
      receptor: RECEPTOR_CCF,
      items: [{ descripcion: 'Harina', cantidad: 4, precioUni: 50, ventaGravada: 200 }],
      ajustes: { condicionOperacion: 2, plazoDias: 30, ivaRete: 2 },
      pago: { codigo: '99', montoPago: 224, referencia: null, numPagoElectronico: null },
    });
    assert.equal(dte.resumen.condicionOperacion, 2);
    assert.equal(dte.resumen.ivaRete, 2);
    assert.equal(dte.resumen.montoTotalOperacion, 226);
    assert.equal(dte.resumen.totalPagar, 224);
    assert.equal(dte.resumen.pagos[0].plazo, '01');
    assert.equal(dte.resumen.pagos[0].periodo, 30);
    assert.equal(validarDte(dte).valido, true, JSON.stringify(validarDte(dte).errores));
  });

  test('CCF con percepción y descuento global en el resumen', () => {
    const { dte } = construirCCF({
      receptor: RECEPTOR_CCF,
      items: [{ descripcion: 'Azúcar', cantidad: 10, precioUni: 22, ventaGravada: 220 }],
      descuentoGlobal: { gravada: 20 },
      ajustes: { descuentoGlobalEnResumen: true, ivaPerci: 2 },
    });
    assert.equal(dte.resumen.descuGravada, 20);
    assert.equal(dte.resumen.subTotal, 200);
    assert.equal(dte.resumen.tributos[0].valor, 26);
    assert.equal(dte.resumen.ivaPerci, 2);
    assert.equal(dte.resumen.totalPagar, 228);
    assert.equal(validarDte(dte).valido, true, JSON.stringify(validarDte(dte).errores));
  });

  test('rechaza ajustes que no siguen las reglas de Hacienda', () => {
    const ccf = (ajustes, items = [{ descripcion: 'X', cantidad: 1, precioUni: 200, ventaGravada: 200 }]) =>
      error(() => construirCCF({ receptor: RECEPTOR_CCF, items, ajustes }));
    assert.match(ccf({ ivaRete: 5 }), /retención/);
    assert.match(ccf({ ivaRete: 0.5 }, [{ descripcion: 'X', cantidad: 1, precioUni: 50, ventaGravada: 50 }]), /retención/);
    assert.match(ccf({ ivaPerci: 9 }), /percepción/);
    assert.match(ccf({ condicionOperacion: 2 }), /plazoDias/);
    assert.match(ccf({ condicionOperacion: 7 }), /condicionOperacion/);
    assert.match(
      error(() => construirFactura({ receptor: null, items: [{ descripcion: 'X', cantidad: 1, precioUni: 113, ventaGravada: 113 }], ajustes: { ivaPerci: 1 } })),
      /percepción/,
    );
    assert.match(
      error(() => construirFactura({
        receptor: null,
        items: [{ descripcion: 'X', cantidad: 1, precioUni: 113, ventaGravada: 113 }],
        descuentoGlobal: { gravada: 200 },
        ajustes: { descuentoGlobalEnResumen: true },
      })),
      /excede/,
    );
  });

  test('sin ajustes el comportamiento heredado no cambia', () => {
    const { dte } = construirFactura({
      receptor: null,
      items: [{ descripcion: 'X', cantidad: 1, precioUni: 113, ventaGravada: 113 }],
      descuentoGlobal: { gravada: 13 },
    });
    assert.equal(dte.cuerpoDocumento[0].montoDescu, 13);
    assert.equal(dte.resumen.descuGravada, 0);
    assert.equal(dte.resumen.condicionOperacion, 1);
  });
});
