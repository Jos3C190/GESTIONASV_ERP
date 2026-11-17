const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { construirFactura, construirCCF } = require('../../src/services/dteBuilder');
const { validarDte } = require('../../src/validators/dteSchema');
const correlativoStore = require('../../src/services/correlativoStore');
const { usarReloj } = require('../../src/utils/fechaHoraSV');
const { ZONAS_DEL_PROCESO, BORDES_DIA_SV, usarZonaDelProceso, fijarInstante } = require('../_relojSV');

// Factura: precio y venta CON IVA (113 = 100 + 13 de IVA incluido).
const ITEM_FACTURA = { descripcion: 'Servicio de prueba', cantidad: 1, precioUni: 113, ventaGravada: 113 };
// CCF: precio y venta SIN IVA.
const ITEM_CCF = { descripcion: 'Servicio de prueba', cantidad: 1, precioUni: 100, ventaGravada: 100 };

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

// Pedido del escenario de evidencia de la auditoría: 2 camisetas de $25 y una
// taza de $12.50 (precios con IVA), cupón del 10 % y envío de $3.50.
const PEDIDO_FACTURA = [
  { descripcion: 'Camiseta', cantidad: 2, precioUni: 25, montoDescu: 5, ventaGravada: 45 },
  { descripcion: 'Taza', cantidad: 1, precioUni: 12.5, montoDescu: 1.25, ventaGravada: 11.25 },
  { tipoItem: 2, descripcion: 'Servicio de entrega', cantidad: 1, precioUni: 3.5, ventaGravada: 0, ventaNoSuj: 3.5 },
];
const PEDIDO_CCF = [
  { descripcion: 'Camiseta', cantidad: 2, precioUni: 22.12, montoDescu: 4.42, ventaGravada: 39.82, ivaItem: 5.18 },
  { descripcion: 'Taza', cantidad: 1, precioUni: 11.07, montoDescu: 1.11, ventaGravada: 9.96, ivaItem: 1.29 },
  { tipoItem: 2, descripcion: 'Servicio de entrega', cantidad: 1, precioUni: 3.5, ventaGravada: 0, ventaNoSuj: 3.5 },
];

function cumpleFormulaPorLinea(dte) {
  return dte.cuerpoDocumento.every((linea) => {
    const ventas = linea.ventaGravada + linea.ventaExenta + linea.ventaNoSuj;
    return Math.abs(linea.cantidad * linea.precioUni - linea.montoDescu - ventas) <= 0.01;
  });
}

describe('dteBuilder.js', () => {
  beforeEach(() => {
    correlativoStore.reiniciarAMemoria();
  });
  afterEach(() => {
    usarReloj(null);
  });

  describe('construirFactura (IVA incluido)', () => {
    test('genera un DTE que valida contra el schema oficial fe-f-v2.json', () => {
      const { dte } = construirFactura({ receptor: null, items: [ITEM_FACTURA] });
      const { valido, errores } = validarDte(dte);
      assert.equal(valido, true, JSON.stringify(errores));
      assert.equal(dte.identificacion.tipoDte, '01');
      assert.equal(dte.identificacion.version, 2);
      assert.equal(dte.receptor, null);
    });

    test('no agrega el tributo 20: el IVA va incluido y totalIva es informativo (MF XIV)', () => {
      const { dte } = construirFactura({ receptor: null, items: [ITEM_FACTURA] });
      assert.equal(dte.cuerpoDocumento[0].tributos, null);
      assert.equal(dte.cuerpoDocumento[0].ivaItem, 13);
      assert.equal(dte.resumen.tributos, null);
      assert.equal(dte.resumen.totalIva, 13);
      assert.equal(dte.resumen.subTotal, 113);
      assert.equal(dte.resumen.montoTotalOperacion, 113);
      assert.equal(dte.resumen.totalPagar, 113);
      assert.equal(dte.resumen.totalLetras, 'CIENTO TRECE 00/100 DÓLARES');
    });

    test('calcula totalIva desde las ventas aunque el redondeo por línea difiera', () => {
      const { dte } = construirFactura({
        receptor: null,
        items: [
          { descripcion: 'A', cantidad: 1, precioUni: 33.33, ventaGravada: 33.33 },
          { descripcion: 'B', cantidad: 1, precioUni: 33.33, ventaGravada: 33.33 },
          { descripcion: 'C', cantidad: 1, precioUni: 33.34, ventaGravada: 33.34 },
        ],
      });
      assert.equal(dte.resumen.totalIva, 11.5); // 100 × 0.13 / 1.13 = 11.504…
      assert.equal(dte.resumen.totalPagar, 100);
    });

    test('ignora un ivaItem enviado y lo recalcula desde la venta gravada', () => {
      const { dte } = construirFactura({ receptor: null, items: [{ ...ITEM_FACTURA, ivaItem: 99 }] });
      assert.equal(dte.cuerpoDocumento[0].ivaItem, 13);
    });

    test('ventas mixtas con descuento por ítem: subTotal sin descuentos globales y total = suma de ventas', () => {
      const { dte } = construirFactura({
        receptor: null,
        items: [
          { descripcion: 'Gravado con descuento', cantidad: 1, precioUni: 100, ventaGravada: 90, montoDescu: 10 },
          { descripcion: 'Exento', cantidad: 1, precioUni: 50, ventaGravada: 0, ventaExenta: 50 },
          { descripcion: 'No sujeto', cantidad: 1, precioUni: 20, ventaGravada: 0, ventaNoSuj: 20 },
        ],
      });
      assert.equal(dte.resumen.totalGravada, 90);
      assert.equal(dte.resumen.totalExenta, 50);
      assert.equal(dte.resumen.totalNoSuj, 20);
      assert.equal(dte.resumen.descuGravada, 0);
      assert.equal(dte.resumen.totalDescu, 10);
      assert.equal(dte.resumen.subTotalVentas, 160);
      assert.equal(dte.resumen.subTotal, 160);
      assert.equal(dte.resumen.totalIva, 10.35); // IVA contenido en los 90 gravados
      assert.equal(dte.resumen.totalPagar, 160);
      assert.equal(validarDte(dte).valido, true);
    });

    test('escenario de evidencia: cupón + envío cuadran por línea y el total es el cobrado', () => {
      const pago = { codigo: '99', montoPago: 59.75, referencia: 'Tarjeta Wompi 6F1C2D3E', numPagoElectronico: null };
      const { dte } = construirFactura({ receptor: null, items: PEDIDO_FACTURA, pago });
      assert.equal(cumpleFormulaPorLinea(dte), true);
      assert.equal(dte.resumen.totalGravada, 56.25);
      assert.equal(dte.resumen.totalNoSuj, 3.5);
      assert.equal(dte.resumen.descuGravada, 0);
      assert.equal(dte.resumen.totalDescu, 6.25);
      assert.equal(dte.resumen.subTotal, 59.75);
      assert.equal(dte.resumen.totalIva, 6.47);
      assert.equal(dte.resumen.totalPagar, 59.75);
      assert.equal(dte.resumen.pagos[0].codigo, '99');
      assert.equal(validarDte(dte).valido, true);
    });

    test('rechaza líneas que no cumplen cantidad × precio − descuento = venta, antes de reservar correlativo', () => {
      let reservas = 0;
      correlativoStore.usar(() => { reservas += 1; return reservas; });
      assert.throws(
        () => construirFactura({ receptor: null, items: [{ descripcion: 'Camiseta', cantidad: 2, precioUni: 19.91, montoDescu: 5, ventaGravada: 39.82 }] }),
        (error) => error.code === 'INVALID_DTE_REQUEST',
      );
      assert.equal(reservas, 0);
    });

    test('cargos que no afectan la base se suman al total a pagar (MF XII)', () => {
      const { dte } = construirFactura({
        receptor: null,
        items: [
          ITEM_FACTURA,
          { tipoItem: 2, descripcion: 'Cargo por envío (courier)', cantidad: 1, uniMedida: 99, precioUni: 0, ventaGravada: 0, noGravado: 3.5 },
        ],
      });
      assert.equal(dte.resumen.totalNoGravado, 3.5);
      assert.equal(dte.resumen.subTotal, 113);
      assert.equal(dte.resumen.totalPagar, 116.5);
      assert.equal(dte.cuerpoDocumento[1].noGravado, 3.5);
      assert.equal(validarDte(dte).valido, true);
    });

    test('descuentoGlobal se transmite como descuento por ítem prorrateado', () => {
      const { dte } = construirFactura({
        receptor: null,
        items: [
          { descripcion: 'A', cantidad: 1, precioUni: 100, ventaGravada: 100 },
          { descripcion: 'B', cantidad: 1, precioUni: 300, ventaGravada: 300 },
        ],
        descuentoGlobal: { gravada: 40 },
      });
      assert.equal(dte.cuerpoDocumento[0].ventaGravada, 90);
      assert.equal(dte.cuerpoDocumento[1].ventaGravada, 270);
      assert.equal(dte.cuerpoDocumento[0].montoDescu, 10);
      assert.equal(dte.resumen.descuGravada, 0);
      assert.equal(dte.resumen.totalDescu, 40);
      assert.equal(dte.resumen.totalPagar, 360);
      assert.equal(cumpleFormulaPorLinea(dte), true);
      assert.equal(validarDte(dte).valido, true);
    });

    test('regresión: montos con representación binaria imprecisa (131.70) no son rechazados por Ajv', () => {
      const { dte } = construirFactura({
        receptor: null,
        items: [
          { descripcion: 'Gravado', cantidad: 1, precioUni: 90, ventaGravada: 90 },
          { descripcion: 'Exento', cantidad: 1, precioUni: 41.7, ventaGravada: 0, ventaExenta: 41.7 },
        ],
      });
      const { valido, errores } = validarDte(dte);
      assert.equal(valido, true, JSON.stringify(errores));
    });

    test('exige tipoDocumento y numDocumento del receptor juntos', () => {
      assert.throws(() => construirFactura({ receptor: { nombre: 'X', tipoDocumento: '13' }, items: [ITEM_FACTURA] }), /juntos/);
    });

    test('acepta formas de pago de CAT-017 y rechaza códigos ajenos o montos que no cuadran', () => {
      const { dte } = construirFactura({ receptor: null, items: [ITEM_FACTURA], pago: { codigo: '05', montoPago: 113, referencia: 'TRANSFER-123' } });
      assert.deepEqual(dte.resumen.pagos, [{ codigo: '05', montoPago: 113, referencia: 'TRANSFER-123', plazo: null, periodo: null }]);
      assert.throws(() => construirFactura({ receptor: null, items: [ITEM_FACTURA], pago: { codigo: '07', montoPago: 113 } }), /CAT-017/);
      assert.throws(() => construirFactura({ receptor: null, items: [ITEM_FACTURA], pago: { codigo: '01', montoPago: 112 } }), /no coincide/);
    });

    test('devuelve codigoGeneracion y numeroControl consistentes con el DTE armado', () => {
      const { dte, codigoGeneracion, numeroControl } = construirFactura({ receptor: null, items: [ITEM_FACTURA] });
      assert.equal(dte.identificacion.codigoGeneracion, codigoGeneracion);
      assert.equal(dte.identificacion.numeroControl, numeroControl);
    });

    test('rechaza items vacíos con un mensaje claro', () => {
      assert.throws(() => construirFactura({ receptor: null, items: [] }), /items/);
    });
  });

  describe('fecha, hora y correlativo en hora de El Salvador', () => {
    test('a las 23:30 del último día del mes la fecha sigue siendo ese día (no la de UTC)', () => {
      usarReloj(() => new Date('2026-11-01T05:30:00Z')); // 31-oct 23:30 en El Salvador
      const { dte } = construirFactura({ receptor: null, items: [ITEM_FACTURA] });
      assert.equal(dte.identificacion.fecEmi, '2026-10-31');
      assert.equal(dte.identificacion.horEmi, '23:30:00');
    });

    test('el correlativo usa el año de la fecha de emisión salvadoreña', () => {
      const anios = [];
      correlativoStore.usar((tipoDte, anio) => { anios.push(anio); return 1; });
      usarReloj(() => new Date('2027-01-01T05:59:59Z')); // 31-dic-2026 23:59:59 en El Salvador
      const { dte } = construirFactura({ receptor: null, items: [ITEM_FACTURA] });
      assert.equal(dte.identificacion.fecEmi, '2026-12-31');
      assert.deepEqual(anios, [2026]);
    });
  });

  describe('identificación en contingencia (MF VIII)', () => {
    test('usa modelo diferido y transmisión por contingencia con el tipo CAT-005', () => {
      const { dte } = construirFactura({ receptor: null, items: [ITEM_FACTURA] }, { contingencia: { tipoContingencia: 1 } });
      assert.equal(dte.identificacion.tipoModelo, 2);
      assert.equal(dte.identificacion.tipoOperacion, 2);
      assert.equal(dte.identificacion.tipoContingencia, 1);
      assert.equal(dte.identificacion.motivoContin, null);
      assert.equal(validarDte(dte).valido, true);
    });

    test('exige motivo cuando el tipo de contingencia es 5', () => {
      assert.throws(() => construirFactura({ receptor: null, items: [ITEM_FACTURA] }, { contingencia: { tipoContingencia: 5 } }), /motivoContin/);
    });
  });

  describe('construirCCF (sin IVA)', () => {
    test('genera un DTE que valida contra el schema oficial fe-ccf-v4.json', () => {
      const { dte } = construirCCF({ receptor: RECEPTOR_CCF, items: [ITEM_CCF] });
      const { valido, errores } = validarDte(dte);
      assert.equal(valido, true, JSON.stringify(errores));
      assert.equal(dte.identificacion.tipoDte, '03');
      assert.equal(dte.identificacion.version, 4);
    });

    test('informa el IVA en el tributo 20 y no como IVA percibido', () => {
      const { dte } = construirCCF({ receptor: RECEPTOR_CCF, items: [ITEM_CCF] });
      assert.deepEqual(dte.cuerpoDocumento[0].tributos, ['20']);
      assert.equal(dte.resumen.tributos[0].codigo, '20');
      assert.equal(dte.resumen.tributos[0].valor, 13);
      assert.equal(dte.resumen.ivaPerci, 0);
      assert.equal(dte.resumen.subTotal, 100);
      assert.equal(dte.resumen.montoTotalOperacion, 113);
      assert.equal(dte.resumen.totalPagar, 113);
      assert.equal(dte.resumen.totalLetras, 'CIENTO TRECE 00/100 DÓLARES');
      assert.equal('totalIva' in dte.resumen, false);
      assert.equal('ivaItem' in dte.cuerpoDocumento[0], false);
    });

    test('escenario de evidencia: líneas netas cuadran y se conserva el IVA cobrado', () => {
      const pago = { codigo: '99', montoPago: 59.75, referencia: 'Tarjeta Wompi 6F1C2D3E' };
      const { dte } = construirCCF({ receptor: RECEPTOR_CCF, items: PEDIDO_CCF, pago });
      assert.equal(cumpleFormulaPorLinea(dte), true);
      assert.equal(dte.resumen.totalGravada, 49.78);
      assert.equal(dte.resumen.descuGravada, 0);
      assert.equal(dte.resumen.totalDescu, 5.53);
      assert.equal(dte.resumen.subTotal, 53.28);
      assert.equal(dte.resumen.tributos[0].valor, 6.47);
      assert.equal(dte.resumen.totalPagar, 59.75);
      assert.equal(validarDte(dte).valido, true);
    });

    test('ejemplo oficial MF XVIII: descuento global de 77.50 sobre 775.00 → base 697.50 e IVA 90.68', () => {
      const { dte } = construirCCF({
        receptor: RECEPTOR_CCF,
        items: [
          { descripcion: 'Camisas/gris', cantidad: 10, precioUni: 11, montoDescu: 10, ventaGravada: 100 },
          { descripcion: 'Centros', cantidad: 15, precioUni: 5, ventaGravada: 75 },
          { descripcion: 'Jeans', cantidad: 25, precioUni: 21, montoDescu: 25, ventaGravada: 500 },
          { descripcion: 'Cinturón', cantidad: 5, precioUni: 20, ventaGravada: 100 },
        ],
        descuentoGlobal: { gravada: 77.5 },
      });
      assert.equal(dte.resumen.totalGravada, 697.5);
      assert.equal(dte.resumen.subTotal, 697.5);
      assert.equal(dte.resumen.tributos[0].valor, 90.68);
      assert.equal(dte.resumen.montoTotalOperacion, 788.18);
      assert.equal(cumpleFormulaPorLinea(dte), true);
      assert.equal(validarDte(dte).valido, true);
    });

    test('rechaza un IVA informado que difiere más de 0.01 del 13 % de la base', () => {
      assert.throws(
        () => construirCCF({ receptor: RECEPTOR_CCF, items: [{ ...ITEM_CCF, ivaItem: 13.02 }] }),
        /difiere del 13/,
      );
    });

    test('rechaza IVA explícito incompleto entre líneas gravadas', () => {
      const items = [
        { descripcion: 'Con IVA', cantidad: 1, precioUni: 10, ventaGravada: 10, ivaItem: 1.3 },
        { descripcion: 'Sin IVA informado', cantidad: 1, precioUni: 10, ventaGravada: 10 },
      ];
      assert.throws(() => construirCCF({ receptor: RECEPTOR_CCF, items }), /todas las líneas gravadas/);
    });

    test('exige receptor con NIT y NRC', () => {
      assert.throws(() => construirCCF({ receptor: { nombre: 'Sin NIT' }, items: [ITEM_CCF] }), /nit.*nrc|nrc.*nit/i);
      assert.throws(() => construirCCF({ receptor: null, items: [ITEM_CCF] }));
    });

    test('rechaza un pago no conciliado antes de reservar correlativo fiscal', () => {
      let reservas = 0;
      correlativoStore.usar(() => { reservas += 1; return reservas; });
      const items = [
        { descripcion: 'Producto', cantidad: 1, precioUni: 22.12, ventaGravada: 22.12, ivaItem: 2.87 },
        { descripcion: 'Servicio de entrega', cantidad: 1, precioUni: 4.5, ventaGravada: 0, ventaNoSuj: 4.5 },
      ];
      assert.throws(() => construirCCF({ receptor: RECEPTOR_CCF, items, pago: { codigo: '05', montoPago: 29.48 } }), /no coincide/);
      assert.equal(reservas, 0);
      construirCCF({ receptor: RECEPTOR_CCF, items, pago: { codigo: '05', montoPago: 29.49 } });
      assert.equal(reservas, 1);
    });
  });

  test('Factura y CCF llevan correlativos independientes entre sí', () => {
    const f1 = construirFactura({ receptor: null, items: [ITEM_FACTURA] });
    const c1 = construirCCF({ receptor: RECEPTOR_CCF, items: [ITEM_CCF] });
    assert.ok(f1.numeroControl.endsWith('000000000000001'));
    assert.ok(c1.numeroControl.endsWith('000000000000001'));
  });

  describe('fecEmi y horEmi en hora de El Salvador (UTC-6), sin importar la zona del proceso', () => {
    const constructores = {
      Factura: () => construirFactura({ receptor: null, items: [ITEM_FACTURA] }),
      CCF: () => construirCCF({ receptor: RECEPTOR_CCF, items: [ITEM_CCF] }),
    };

    for (const [nombre, construir] of Object.entries(constructores)) {
      for (const zona of ZONAS_DEL_PROCESO) {
        for (const borde of BORDES_DIA_SV) {
          test(`${nombre} a las ${borde.hora} SV (${borde.utc}) con el proceso en ${zona}`, (t) => {
            usarZonaDelProceso(t, zona);
            fijarInstante(t, borde.utc);
            const { dte } = construir();
            assert.equal(dte.identificacion.fecEmi, borde.fecha);
            assert.equal(dte.identificacion.horEmi, borde.hora);
            assert.equal(validarDte(dte).valido, true);
          });
        }
      }
    }

    test('el 31 de diciembre a las 20:00 SV, el correlativo del Número de Control usa el año de fecEmi', (t) => {
      usarZonaDelProceso(t, 'UTC');
      fijarInstante(t, '2027-01-01T02:00:00.000Z');
      const anios = [];
      correlativoStore.usar((tipoDte, anio) => {
        anios.push(anio);
        return 1;
      });
      const { dte } = construirFactura({ receptor: null, items: [ITEM_FACTURA] });
      assert.equal(dte.identificacion.fecEmi, '2026-12-31');
      assert.equal(dte.identificacion.horEmi, '20:00:00');
      assert.deepEqual(anios, [2026]);
    });
  });
});
