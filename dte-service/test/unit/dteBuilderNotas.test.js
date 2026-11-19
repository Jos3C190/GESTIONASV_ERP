const { test, describe, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
require('../_setup');

const { construirNotaCredito, construirNotaDebito, construirNotaRemision } = require('../../src/services/dteBuilderNotas');
const { validarDte } = require('../../src/validators/dteSchema');
const correlativoStore = require('../../src/services/correlativoStore');
const { ZONAS_DEL_PROCESO, usarZonaDelProceso, fijarInstante } = require('../_relojSV');

const ITEM_SIMPLE = { descripcion: 'Ítem de prueba', cantidad: 1, precioUni: 50, ventaGravada: 50 };

const RECEPTOR_CONTRIBUYENTE = {
  tipoDocumento: '36',
  numDocumento: '06141804941099',
  nrc: '7654321',
  nombre: 'Cliente Empresa S.A.',
  codActividad: '62010',
  descActividad: 'Programación informática',
  direccion: { departamento: '06', municipio: '20', distrito: '01', complemento: 'Otra dirección' },
  telefono: '22223333',
  correo: 'cliente@empresa.com',
};

// La Nota de Crédito relaciona el CCF electrónico por su código de generación.
const CODIGO_CCF = '0A1B2C3D-4E5F-4061-8728-394A5B6C7D8E';
const CCF_ELECTRONICO = { tipoDocumento: '03', tipoGeneracion: 2, numeroDocumento: CODIGO_CCF, fechaEmision: '2026-07-01' };
const OTRO_CCF = { tipoDocumento: '03', tipoGeneracion: 2, numeroDocumento: '1F2E3D4C-5B6A-4798-8A9B-0C1D2E3F4A5B', fechaEmision: '2026-07-15' };
const LINEA_NC = { descripcion: 'Camiseta devuelta', cantidad: 1, precioUni: 100, ventaGravada: 100, numeroDocumento: CODIGO_CCF };

function codigo(indice) {
  return `${String(indice).padStart(8, '0')}-0000-4000-8000-000000000000`;
}

function notaCredito(cambios = {}) {
  return { receptor: RECEPTOR_CONTRIBUYENTE, documentosRelacionados: [CCF_ELECTRONICO], items: [LINEA_NC], ...cambios };
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonicalize(item)]));
  return value;
}

function issuerV2(cambios = {}) {
  const canonical = { legalName: 'Emisor V2 de Notas S.A. de C.V.', tradeName: 'Emisor V2', nit: '06141804941035', nrc: '1234567', economicActivityCode: '62010', economicActivityDescription: 'Programación informática', activityCatalogVersion: 'CAT-019', address: { departmentCode: '06', departmentName: 'San Salvador', municipalityCode: '23', municipalityName: 'San Salvador Centro', districtCode: '14', districtName: 'San Salvador', complement: 'Dirección fiscal v2', geoCatalogVersion: 'GEO-1' }, phone: '22221111', email: 'notas-v2@example.test', establishmentType: '02', mhEstablishmentCode: '001', mhPointOfSaleCode: '001', internalEstablishmentCode: 'CASA', internalPointOfSaleCode: null, ...cambios };
  return { revisionId: 'revision-nc', snapshotSha256: crypto.createHash('sha256').update(JSON.stringify(canonicalize(canonical))).digest('hex'), nit: canonical.nit, nrc: canonical.nrc, nombre: canonical.legalName, nombreComercial: canonical.tradeName, codActividad: canonical.economicActivityCode, descActividad: canonical.economicActivityDescription, activityCatalogVersion: canonical.activityCatalogVersion, direccion: { departamento: '06', departmentName: 'San Salvador', municipio: '23', municipalityName: 'San Salvador Centro', distrito: '14', districtName: 'San Salvador', complemento: 'Dirección fiscal v2', geoCatalogVersion: 'GEO-1' }, telefono: canonical.phone, correo: canonical.email, tipoEstablecimiento: canonical.establishmentType, codEstablecimientoMH: canonical.mhEstablishmentCode, codPuntoVentaMH: canonical.mhPointOfSaleCode, codEstable: canonical.internalEstablishmentCode, codPuntoVenta: canonical.internalPointOfSaleCode };
}

describe('dteBuilderNotas.js', () => {
  beforeEach(() => {
    correlativoStore.reiniciarAMemoria();
  });

  describe('construirNotaCredito (contrato v2)', () => {
    test('genera un DTE que valida contra fe-nc-v4.json', () => {
      const { dte } = construirNotaCredito(notaCredito());
      const { valido, errores, schema } = validarDte(dte);
      assert.equal(valido, true, JSON.stringify(errores));
      assert.equal(schema, 'Nota de Crédito Electrónica');
      assert.equal(dte.identificacion.tipoDte, '05');
      assert.equal(dte.identificacion.version, 4);
      assert.equal(dte.identificacion.fusion, null);
    });

    test('relaciona el CCF por su código de generación y su fecha, y cada línea lleva el documento que ajusta', () => {
      const { dte } = construirNotaCredito(notaCredito({
        documentosRelacionados: [{ ...CCF_ELECTRONICO, numeroDocumento: CCF_ELECTRONICO.numeroDocumento.toLowerCase() }],
      }));
      assert.deepEqual(dte.documentoRelacionado, [CCF_ELECTRONICO]);
      assert.deepEqual(dte.cuerpoDocumento.map((linea) => linea.numeroDocumento), [CODIGO_CCF]);
    });

    test('calcula el resumen: IVA en el tributo 20 y en totalIva, total = subtotal + IVA + no gravado', () => {
      const { dte } = construirNotaCredito(notaCredito({
        items: [
          { ...LINEA_NC, montoDescu: 1, precioUni: 21, ventaGravada: 20 },
          { descripcion: 'Envío no afecto', cantidad: 1, precioUni: 0, ventaGravada: 0, noGravado: 2.5, numeroDocumento: CODIGO_CCF },
        ],
        observaciones: '  Devolución parcial del pedido 1234  ',
      }));
      const { resumen } = dte;
      assert.equal(resumen.totalGravada, 20);
      assert.equal(resumen.subTotalVentas, 20);
      assert.equal(resumen.totalDescu, 1);
      assert.deepEqual(resumen.tributos, [{ codigo: '20', descripcion: 'Impuesto al Valor Agregado 13%', valor: 2.6 }]);
      assert.equal(resumen.totalIva, 2.6);
      assert.equal(resumen.montoTotalOperacion, 22.6);
      assert.equal(resumen.totalNoGravado, 2.5);
      assert.equal(resumen.totalPagar, 25.1);
      assert.equal(resumen.totalLetras, 'VEINTICINCO 10/100 DÓLARES');
      assert.equal(resumen.observaciones, 'Devolución parcial del pedido 1234');
      assert.deepEqual(dte.cuerpoDocumento.map((linea) => linea.tributos), [['20'], null]);
      assert.deepEqual(dte.cuerpoDocumento.map((linea) => linea.totalIva), [2.6, 0]);
      assert.equal(validarDte(dte).valido, true);
    });

    test('sin IVA por línea reparte el 13 % de la base en centavos exactos', () => {
      const { dte } = construirNotaCredito(notaCredito({
        items: [
          { ...LINEA_NC, descripcion: 'A', precioUni: 33.33, ventaGravada: 33.33 },
          { ...LINEA_NC, descripcion: 'B', precioUni: 33.33, ventaGravada: 33.33 },
          { ...LINEA_NC, descripcion: 'C', precioUni: 33.34, ventaGravada: 33.34 },
        ],
      }));
      const sumaLineas = Number(dte.cuerpoDocumento.reduce((s, i) => s + i.totalIva, 0).toFixed(2));
      assert.equal(dte.resumen.totalIva, 13);
      assert.equal(sumaLineas, 13);
    });

    test('respeta el IVA acreditado por línea dentro de la holgura de ±0.01 y rechaza el que la excede', () => {
      const items = [
        { ...LINEA_NC, descripcion: 'A', precioUni: 22.12, ventaGravada: 22.12, ivaItem: 2.87 },
        { ...LINEA_NC, descripcion: 'B', precioUni: 22.12, ventaGravada: 22.12, ivaItem: 2.88 },
      ];
      // 13 % de 44.24 = 5.75; el CCF cobró 2.87 + 2.88 = 5.75.
      const { dte } = construirNotaCredito(notaCredito({ items }));
      assert.deepEqual(dte.cuerpoDocumento.map((linea) => linea.totalIva), [2.87, 2.88]);
      assert.equal(dte.resumen.totalIva, 5.75);

      const holgura = construirNotaCredito(notaCredito({ items: [{ ...LINEA_NC, ivaItem: 13.01 }] })).dte;
      assert.equal(holgura.resumen.totalIva, 13.01);
      assert.equal(holgura.resumen.totalPagar, 113.01);

      assert.throws(() => construirNotaCredito(notaCredito({ items: [{ ...LINEA_NC, ivaItem: 13.02 }] })), /difiere del 13/);
      assert.throws(
        () => construirNotaCredito(notaCredito({ items: [{ ...items[0] }, { ...items[1], ivaItem: undefined }] })),
        /todas las líneas gravadas/,
      );
    });

    test('ajusta varios CCF en una sola nota, con el documento de cada línea', () => {
      const fisico = { tipoDocumento: '03', tipoGeneracion: 1, numeroDocumento: 'CCF-000123', fechaEmision: '2026-08-15' };
      const { dte } = construirNotaCredito(notaCredito({
        documentosRelacionados: [CCF_ELECTRONICO, OTRO_CCF, fisico],
        items: [
          { ...LINEA_NC, descripcion: 'Del primero', numeroDocumento: CODIGO_CCF },
          { ...LINEA_NC, descripcion: 'Del segundo', numeroDocumento: OTRO_CCF.numeroDocumento },
          { ...LINEA_NC, descripcion: 'Del físico', numeroDocumento: 'CCF-000123' },
        ],
      }));
      assert.equal(dte.documentoRelacionado.length, 3);
      assert.deepEqual(dte.cuerpoDocumento.map((linea) => linea.numeroDocumento), [CODIGO_CCF, OTRO_CCF.numeroDocumento, 'CCF-000123']);
      assert.equal(dte.resumen.totalPagar, 339);
      assert.equal(validarDte(dte).valido, true);
    });

    test('valida los documentos relacionados: de 1 a 50 CCF, código de 36 caracteres, fecha y sin repetidos', () => {
      const casos = [
        [undefined, /documentosRelacionados/],
        [[], /documentosRelacionados/],
        [Array.from({ length: 51 }, () => CCF_ELECTRONICO), /máximo 50/],
        [[{ ...CCF_ELECTRONICO, tipoDocumento: '01' }], /solo ajusta Comprobantes de Crédito Fiscal/],
        [[{ ...CCF_ELECTRONICO, tipoDocumento: '07' }], /solo ajusta Comprobantes de Crédito Fiscal/],
        [[{ ...CCF_ELECTRONICO, numeroDocumento: 'DTE-03-M001P001-000000000000001' }], /código de generación/],
        [[{ ...CCF_ELECTRONICO, tipoGeneracion: 3 }], /tipoGeneracion/],
        [[{ ...CCF_ELECTRONICO, tipoGeneracion: 1, numeroDocumento: '' }], /correlativo/],
        [[{ ...CCF_ELECTRONICO, fechaEmision: '01/07/2026' }], /AAAA-MM-DD/],
        [[{ ...CCF_ELECTRONICO, fechaEmision: '2026-02-30' }], /AAAA-MM-DD/],
        [[{ ...CCF_ELECTRONICO, fechaEmision: '2999-01-01' }], /posterior/],
        [[CCF_ELECTRONICO, { ...CCF_ELECTRONICO, numeroDocumento: CODIGO_CCF.toLowerCase() }], /repetido/],
      ];
      for (const [documentosRelacionados, error] of casos) {
        assert.throws(
          () => construirNotaCredito(notaCredito({ documentosRelacionados })),
          (e) => e.code === 'INVALID_DTE_REQUEST' && error.test(e.message),
          String(error),
        );
      }
    });

    test('acepta exactamente 50 documentos relacionados', () => {
      const documentosRelacionados = Array.from({ length: 50 }, (_, i) => ({ ...CCF_ELECTRONICO, numeroDocumento: codigo(i) }));
      const items = documentosRelacionados.map((documento) => ({ ...LINEA_NC, precioUni: 1, ventaGravada: 1, numeroDocumento: documento.numeroDocumento }));
      const { dte } = construirNotaCredito(notaCredito({ documentosRelacionados, items }));
      assert.equal(dte.documentoRelacionado.length, 50);
      assert.equal(validarDte(dte).valido, true);
    });

    test('exige el receptor contribuyente del CCF: NIT (tipo 36), NRC, actividad y dirección', () => {
      const casos = [
        [null, /receptor/],
        [{ ...RECEPTOR_CONTRIBUYENTE, tipoDocumento: '13', numDocumento: '01234567-8' }, /NIT/],
        [{ ...RECEPTOR_CONTRIBUYENTE, numDocumento: '0614-180494-109-9' }, /NIT/],
        [{ ...RECEPTOR_CONTRIBUYENTE, nrc: null }, /NRC/],
        [{ ...RECEPTOR_CONTRIBUYENTE, codActividad: '' }, /codActividad/],
        [{ ...RECEPTOR_CONTRIBUYENTE, descActividad: undefined }, /descActividad/],
        [{ ...RECEPTOR_CONTRIBUYENTE, direccion: { departamento: '06', municipio: '20' } }, /direccion/],
        [{ ...RECEPTOR_CONTRIBUYENTE, telefono: '2222' }, /telefono.*8 a 30/],
        [{ ...RECEPTOR_CONTRIBUYENTE, telefono: 22223333 }, /telefono.*texto o null/],
        [{ ...RECEPTOR_CONTRIBUYENTE, correo: 'sin-arroba' }, /correo.*usuario@dominio/],
        [{ ...RECEPTOR_CONTRIBUYENTE, correo: `${'x'.repeat(95)}@e.com` }, /correo/],
      ];
      for (const [receptor, error] of casos) {
        assert.throws(
          () => construirNotaCredito(notaCredito({ receptor })),
          (e) => e.code === 'INVALID_DTE_REQUEST' && error.test(e.message),
          String(error),
        );
      }
    });

    test('acepta un receptor sin teléfono ni correo, como el CCF que ajusta', () => {
      for (const [telefono, correo] of [[null, null], ['', '  '], [undefined, undefined]]) {
        const { dte } = construirNotaCredito(notaCredito({ receptor: { ...RECEPTOR_CONTRIBUYENTE, telefono, correo } }));
        assert.equal(dte.receptor.telefono, null);
        assert.equal(dte.receptor.correo, null);
        assert.equal(validarDte(dte).valido, true, JSON.stringify(validarDte(dte).errores));
      }
      const { dte } = construirNotaCredito(notaCredito({ receptor: { ...RECEPTOR_CONTRIBUYENTE, telefono: ' 2222-3333 ', correo: ' cliente@empresa.com ' } }));
      assert.equal(dte.receptor.telefono, '2222-3333');
      assert.equal(dte.receptor.correo, 'cliente@empresa.com');
    });

    test('cada línea debe ajustar uno de los documentos relacionados, y cada documento debe tener líneas', () => {
      assert.throws(
        () => construirNotaCredito(notaCredito({ items: [{ ...LINEA_NC, numeroDocumento: undefined }] })),
        /Línea 1: numeroDocumento/,
      );
      assert.throws(
        () => construirNotaCredito(notaCredito({ items: [{ ...LINEA_NC, numeroDocumento: OTRO_CCF.numeroDocumento }] })),
        /Línea 1: numeroDocumento/,
      );
      assert.throws(
        () => construirNotaCredito(notaCredito({ documentosRelacionados: [CCF_ELECTRONICO, OTRO_CCF] })),
        /no tiene líneas/,
      );
    });

    test('valida las líneas con las reglas del CCF', () => {
      assert.throws(() => construirNotaCredito(notaCredito({ items: [] })), /items/);
      assert.throws(
        () => construirNotaCredito(notaCredito({ items: [{ ...LINEA_NC, ventaGravada: 90 }] })),
        (e) => e.code === 'INVALID_DTE_REQUEST' && /no coincide con la venta/.test(e.message),
      );
      assert.throws(() => construirNotaCredito(notaCredito({ observaciones: 'x'.repeat(3001) })), /observaciones/);
    });

    test('repite la retención del CCF: 1 % del gravado de la nota, aunque sea menor de $100 (Manual Funcional, ejemplo NCE con retención)', () => {
      const { dte } = construirNotaCredito(notaCredito({ items: [{ ...LINEA_NC, precioUni: 90, ventaGravada: 90 }], ajustes: { retencionIva: true } }));
      assert.equal(dte.resumen.ivaRete, 0.9);
      assert.deepEqual(dte.cuerpoDocumento.map((linea) => linea.ivaRete), [0.9]);
      assert.equal(dte.resumen.ivaPerci, 0);
      assert.equal(dte.resumen.totalPagar, 100.8);
      assert.equal(validarDte(dte).valido, true);
    });

    test('reparte la retención y la percepción entre las líneas gravadas en centavos exactos', () => {
      const { dte } = construirNotaCredito(notaCredito({
        items: [
          { ...LINEA_NC, descripcion: 'A', precioUni: 33.33, ventaGravada: 33.33 },
          { ...LINEA_NC, descripcion: 'B', precioUni: 33.33, ventaGravada: 33.33 },
          { ...LINEA_NC, descripcion: 'C', precioUni: 0, ventaGravada: 0, ventaExenta: 0, noGravado: 5 },
        ],
        ajustes: { retencionIva: true, percepcionIva: true },
      }));
      assert.equal(dte.resumen.ivaRete, 0.67);
      assert.equal(dte.resumen.ivaPerci, 0.67);
      assert.equal(Number(dte.cuerpoDocumento.reduce((s, i) => s + i.ivaRete, 0).toFixed(2)), 0.67);
      assert.equal(dte.cuerpoDocumento[2].ivaRete, 0);
      assert.throws(() => construirNotaCredito(notaCredito({ ajustes: { retencionIva: 'sí' } })), /retencionIva debe ser true o false/);
    });

    test('ningún error de la solicitud reserva número de control', () => {
      let reservas = 0;
      correlativoStore.usar(() => { reservas += 1; return reservas; });
      const invalidas = [
        { documentosRelacionados: [] },
        { receptor: { ...RECEPTOR_CONTRIBUYENTE, nrc: null } },
        { items: [{ ...LINEA_NC, ventaGravada: 90 }] },
        { items: [{ ...LINEA_NC, numeroDocumento: OTRO_CCF.numeroDocumento }] },
        { items: [{ ...LINEA_NC, ivaItem: 20 }] },
        { observaciones: 42 },
      ];
      for (const cambios of invalidas) {
        assert.throws(() => construirNotaCredito(notaCredito(cambios)), (e) => e.code === 'INVALID_DTE_REQUEST');
      }
      assert.throws(() => construirNotaCredito(notaCredito(), { contingencia: { tipoContingencia: 5 } }), /motivoContin/);
      assert.equal(reservas, 0);

      const { numeroControl } = construirNotaCredito(notaCredito());
      assert.equal(reservas, 1);
      assert.ok(numeroControl.endsWith('000000000000001'));
    });

    test('en contingencia usa modelo diferido y transmisión por contingencia', () => {
      const { dte } = construirNotaCredito(notaCredito(), { contingencia: { tipoContingencia: 5, motivoContin: 'Falla del proveedor de internet' } });
      assert.equal(dte.identificacion.tipoModelo, 2);
      assert.equal(dte.identificacion.tipoOperacion, 2);
      assert.equal(dte.identificacion.tipoContingencia, 5);
      assert.equal(dte.identificacion.motivoContin, 'Falla del proveedor de internet');
      assert.equal(validarDte(dte).valido, true);
    });

    test('con el emisor del .env, el emisor no lleva codEstable/codPuntoVenta (fe-nc-v4.json no los admite)', () => {
      const { dte } = construirNotaCredito(notaCredito());
      assert.equal(dte.emisor.nit, '06141804941035');
      assert.equal('codEstable' in dte.emisor, false);
      assert.equal('codPuntoVenta' in dte.emisor, false);
      assert.ok(dte.identificacion.numeroControl.startsWith('DTE-05-M001P001-'));
    });

    test('con el emisor v2 usa el snapshot del panel y sus códigos MH en el número de control', () => {
      const emisor = issuerV2({ mhEstablishmentCode: '002', mhPointOfSaleCode: '003' });
      const { dte } = construirNotaCredito(notaCredito({ emisor }));
      assert.equal(dte.emisor.nombre, emisor.nombre);
      assert.equal(dte.emisor.correo, emisor.correo);
      assert.deepEqual(Object.keys(dte.emisor).sort(), ['codActividad', 'correo', 'descActividad', 'direccion', 'nit', 'nombre', 'nombreComercial', 'nrc', 'telefono']);
      assert.ok(dte.identificacion.numeroControl.startsWith('DTE-05-M002P003-'));
      assert.equal(validarDte(dte).valido, true);

      assert.throws(() => construirNotaCredito(notaCredito({ emisor: { ...emisor, nombre: 'Alterado' } })), (e) => e.code === 'ISSUER_HASH_MISMATCH');
    });
  });

  describe('construirNotaDebito (contrato v2)', () => {
    const CARGO = { descripcion: 'Intereses por mora', cantidad: 1, precioUni: 50, ventaGravada: 50, numeroDocumento: CODIGO_CCF };
    const notaDebito = (cambios = {}) => ({ receptor: RECEPTOR_CONTRIBUYENTE, documentosRelacionados: [CCF_ELECTRONICO], items: [CARGO], ...cambios });

    test('genera un DTE que valida contra fe-nd-v4.json, con numPagoElectronico y el CCF relacionado', () => {
      const { dte } = construirNotaDebito(notaDebito());
      const { valido, errores, schema } = validarDte(dte);
      assert.equal(valido, true, JSON.stringify(errores));
      assert.equal(schema, 'Nota de Débito Electrónica');
      assert.equal(dte.identificacion.tipoDte, '06');
      assert.equal(dte.identificacion.fusion, null);
      assert.equal(dte.resumen.numPagoElectronico, null);
      assert.deepEqual(dte.documentoRelacionado, [CCF_ELECTRONICO]);
      assert.equal(dte.resumen.totalPagar, 56.5);
    });

    test('valida relacionados y receptor con los mensajes de la Nota de Débito', () => {
      assert.throws(() => construirNotaDebito(notaDebito({ documentosRelacionados: [] })), /que la Nota de Débito ajusta/);
      assert.throws(
        () => construirNotaDebito(notaDebito({ documentosRelacionados: [{ ...CCF_ELECTRONICO, tipoDocumento: '01' }] })),
        /la Nota de Débito solo ajusta Comprobantes de Crédito Fiscal/,
      );
      assert.throws(() => construirNotaDebito(notaDebito({ receptor: { ...RECEPTOR_CONTRIBUYENTE, nrc: null } })), /receptor de la Nota de Débito requiere NRC/);
    });

    test('con el emisor v2 y en contingencia', () => {
      const emisor = issuerV2();
      const { dte } = construirNotaDebito(notaDebito({ emisor }), { contingencia: { tipoContingencia: 5, motivoContin: 'Falla del proveedor de internet' } });
      assert.ok(dte.identificacion.numeroControl.startsWith('DTE-06-M001P001-'));
      assert.equal(dte.identificacion.tipoModelo, 2);
      assert.equal('codEstable' in dte.emisor, false);
      assert.equal(validarDte(dte).valido, true);
    });

    test('repite la retención y la percepción del CCF', () => {
      const { dte } = construirNotaDebito(notaDebito({ ajustes: { retencionIva: true, percepcionIva: true } }));
      assert.equal(dte.resumen.ivaRete, 0.5);
      assert.equal(dte.resumen.ivaPerci, 0.5);
      assert.equal(dte.resumen.totalPagar, 56.5);
      assert.equal(validarDte(dte).valido, true);
    });
  });

  describe('construirNotaRemision', () => {
    test('genera un DTE que valida contra fe-nr-v4.json', () => {
      const { dte } = construirNotaRemision({ receptor: RECEPTOR_CONTRIBUYENTE, items: [ITEM_SIMPLE], bienTitulo: '04' });
      const { valido, errores } = validarDte(dte);
      assert.equal(valido, true, JSON.stringify(errores));
    });

    test('normaliza bienTitulo numérico a string de 2 dígitos', () => {
      const { dte } = construirNotaRemision({ receptor: RECEPTOR_CONTRIBUYENTE, items: [ITEM_SIMPLE], bienTitulo: 4 });
      assert.equal(dte.receptor.bienTitulo, '04');
      assert.equal(typeof dte.receptor.bienTitulo, 'string');
    });

    test('lanza error descriptivo si falta bienTitulo', () => {
      assert.throws(
        () => construirNotaRemision({ receptor: RECEPTOR_CONTRIBUYENTE, items: [ITEM_SIMPLE], bienTitulo: null }),
        /bienTitulo/
      );
    });

    test('documentoRelacionado es opcional (a diferencia de NC/ND)', () => {
      const { dte } = construirNotaRemision({ receptor: RECEPTOR_CONTRIBUYENTE, items: [ITEM_SIMPLE], bienTitulo: '04' });
      assert.equal(dte.documentoRelacionado, null);
      assert.equal(validarDte(dte).valido, true);
    });
  });

  for (const zona of ZONAS_DEL_PROCESO) {
    test(`fecEmi y horEmi en hora de El Salvador a las 20:00 SV con el proceso en ${zona}`, (t) => {
      usarZonaDelProceso(t, zona);
      fijarInstante(t, '2026-10-10T02:00:00.000Z');
      const { dte } = construirNotaCredito(notaCredito());
      assert.equal(dte.identificacion.fecEmi, '2026-10-09');
      assert.equal(dte.identificacion.horEmi, '20:00:00');
    });
  }
});
