const { test, describe, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const {
  construirComprobanteRetencion,
  construirComprobanteLiquidacion,
  construirDocumentoContableLiquidacion,
  construirFacturaExportacion,
  construirFacturaSujetoExcluido,
  construirComprobanteDonacion,
} = require('../../src/services/dteBuilderOtros');
const { validarDte } = require('../../src/validators/dteSchema');
const correlativoStore = require('../../src/services/correlativoStore');
const { ZONAS_DEL_PROCESO, usarZonaDelProceso, fijarInstante } = require('../_relojSV');

const DIRECCION = { departamento: '06', municipio: '20', distrito: '01', complemento: 'Dirección de prueba' };

beforeEach(() => {
  correlativoStore.reiniciarAMemoria();
});

describe('construirComprobanteRetencion', () => {
  const receptorRetencion = {
    tipoDocumento: '36',
    numDocumento: '06141804941099',
    nrc: '7654321',
    nombre: 'Proveedor de Prueba S.A.',
    codActividad: '62010',
    descActividad: 'Programación informática',
    direccion: DIRECCION,
    telefono: '22223333',
    correo: 'proveedor@prueba.com',
  };
  const retencionValida = {
    tipoDte: '03',
    tipoGeneracion: 2,
    numeroDocumento: 'DTE-03-M001P001-000000000000001',
    fechaEmision: '2026-07-01',
    montoSujetoGrav: 100,
    codigoRetencionMH: '22',
    ivaRetenido: 1,
    descripcion: 'Retención de prueba',
  };

  test('genera un DTE que valida contra fe-cr-v2.json', () => {
    const { dte } = construirComprobanteRetencion({ receptor: receptorRetencion, retenciones: [retencionValida] });
    const { valido, errores } = validarDte(dte);
    assert.equal(valido, true, JSON.stringify(errores));
    assert.equal(dte.identificacion.tipoDte, '07');
    assert.equal(dte.cuerpoDocumento[0].numeroDocumento, 'DTE-03-M001P001-000000000000001');
  });

  test('acepta el nombre anterior numDocumento y emite numeroDocumento (schema de agosto de 2026)', () => {
    const { numeroDocumento, ...retencionAnterior } = retencionValida;
    const { dte } = construirComprobanteRetencion({
      receptor: receptorRetencion,
      retenciones: [{ ...retencionAnterior, numDocumento: numeroDocumento }],
    });
    assert.equal(validarDte(dte).valido, true);
    assert.equal(dte.cuerpoDocumento[0].numeroDocumento, numeroDocumento);
    assert.equal('numDocumento' in dte.cuerpoDocumento[0], false);
  });

  test('totalIva es el IVA generado 13% sobre el monto sujeto y no cambia el IVA retenido (Normativa, campo 157)', () => {
    const { dte } = construirComprobanteRetencion({
      receptor: receptorRetencion,
      retenciones: [retencionValida, { ...retencionValida, numeroDocumento: 'DTE-03-M001P001-000000000000002', montoSujetoGrav: 50.5, ivaRetenido: 0.51 }],
    });
    assert.equal(dte.resumen.totalSujetoRetencion, 150.5);
    assert.equal(dte.resumen.totalIva, 19.57);
    assert.equal(dte.resumen.totalIvaRetenido, 1.51);
  });

  test('lanza error si no se proveen retenciones', () => {
    assert.throws(() => construirComprobanteRetencion({ receptor: {}, retenciones: [] }), /retenciones/);
  });
});

describe('construirComprobanteLiquidacion', () => {
  test('genera un DTE que valida contra fe-cl-v2.json', () => {
    const { dte } = construirComprobanteLiquidacion({
      receptor: {
        tipoDocumento: '36',
        numDocumento: '06141804941099',
        codDomiciliado: 1,
        nrc: '7654321',
        nombre: 'Afiliado de Prueba S.A.',
        codActividad: '62010',
        descActividad: 'Programación informática',
        direccion: DIRECCION,
        telefono: '22223333',
        correo: 'afiliado@prueba.com',
      },
      liquidaciones: [
        {
          tipoDte: '01',
          tipoGeneracion: 2,
          numeroDocumento: 'DTE-01-M001P001-000000000000001',
          fechaEmision: '2026-07-01',
          ventaGravada: 100,
        },
      ],
    });
    const { valido, errores } = validarDte(dte);
    assert.equal(valido, true, JSON.stringify(errores));
    assert.equal(dte.identificacion.tipoDte, '08');
  });

  test('resumen.ivaPerci coincide con la suma de ivaItem por línea, no con un cálculo independiente', () => {
    const { dte } = construirComprobanteLiquidacion({
      receptor: {
        tipoDocumento: '36',
        numDocumento: '06141804941099',
        codDomiciliado: 1,
        nrc: '7654321',
        nombre: 'Afiliado de Prueba S.A.',
        codActividad: '62010',
        descActividad: 'Programación informática',
        direccion: DIRECCION,
        telefono: '22223333',
        correo: 'afiliado@prueba.com',
      },
      liquidaciones: [
        { tipoDte: '01', tipoGeneracion: 2, numeroDocumento: 'DTE-01-M001P001-000000000000001', fechaEmision: '2026-07-01', ventaGravada: 33.33 },
        { tipoDte: '01', tipoGeneracion: 2, numeroDocumento: 'DTE-01-M001P001-000000000000002', fechaEmision: '2026-07-01', ventaGravada: 33.33 },
        { tipoDte: '01', tipoGeneracion: 2, numeroDocumento: 'DTE-01-M001P001-000000000000003', fechaEmision: '2026-07-01', ventaGravada: 33.34 },
      ],
    });
    const sumaLineas = Number(dte.cuerpoDocumento.reduce((s, i) => s + i.ivaItem, 0).toFixed(2));
    assert.equal(dte.resumen.ivaPerci, sumaLineas);
    assert.equal(dte.resumen.ivaPerci, 12.99);
  });
});

describe('construirDocumentoContableLiquidacion', () => {
  const datosValidos = {
    periodoLiquidacionFechaInicio: '2026-06-01',
    periodoLiquidacionFechaFin: '2026-06-30',
    codLiquidacion: 'LIQ-TEST',
    cantidadDoc: 1,
    valorOperaciones: 100,
    montoSinPercepcion: null,
    descripSinPercepcion: null,
    subTotal: 100,
    // OJO: el schema oficial exige iva e ivaPercibido > 0 (exclusiveMinimum),
    // no simplemente >= 0 — un DCL con IVA cero es rechazado por Hacienda.
    iva: 13,
    montoSujetoPercepcion: 100,
    ivaPercibido: 2,
    comision: 0,
    porcentComision: 0,
    ivaComision: 0,
    liquidoApagar: 100,
    observaciones: null,
  };
  const receptorValido = {
    nit: '06141804941099',
    nrc: '7654321',
    nombre: 'Afiliado de Prueba S.A.',
    telefono: '22223333',
    correo: 'afiliado@prueba.com',
    direccion: DIRECCION,
    tipoEstablecimiento: '02',
    codActividad: '62010',
    descActividad: 'Programación informática',
  };
  const responsableValido = { nombEntrega: 'Encargado de Prueba', docuEntrega: '06141804941035', codEmpleado: null };

  test('genera un DTE que valida contra fe-dcl-v2.json', () => {
    const { dte } = construirDocumentoContableLiquidacion({ receptor: receptorValido, datos: datosValidos, responsable: responsableValido });
    const { valido, errores } = validarDte(dte);
    assert.equal(valido, true, JSON.stringify(errores));
    assert.equal(dte.identificacion.tipoDte, '09');
  });

  test('el emisor usa codEstable y codPuntoVenta (schema de agosto de 2026)', () => {
    const { dte } = construirDocumentoContableLiquidacion({ receptor: receptorValido, datos: datosValidos, responsable: responsableValido });
    assert.ok('codEstable' in dte.emisor);
    assert.ok('codPuntoVenta' in dte.emisor);
    assert.equal('codigo' in dte.emisor, false);
    assert.equal('puntoVenta' in dte.emisor, false);
  });

  test('cuerpoDocumento.totalLetras se genera automáticamente y no es null (el schema lo exige como string)', () => {
    const { dte } = construirDocumentoContableLiquidacion({ receptor: receptorValido, datos: datosValidos, responsable: responsableValido });
    assert.equal(typeof dte.cuerpoDocumento.totalLetras, 'string');
    assert.ok(dte.cuerpoDocumento.totalLetras.length > 0);
  });

  test('lanza error si faltan campos requeridos en "datos"', () => {
    const { liquidoApagar, ...datosIncompletos } = datosValidos;
    assert.throws(
      () => construirDocumentoContableLiquidacion({ receptor: receptorValido, datos: datosIncompletos, responsable: responsableValido }),
      /liquidoApagar/
    );
  });

  test('lanza error si falta "responsable"', () => {
    assert.throws(
      () => construirDocumentoContableLiquidacion({ receptor: receptorValido, datos: datosValidos, responsable: null }),
      /responsable/
    );
  });
});

describe('construirFacturaExportacion', () => {
  test('genera un DTE que valida contra fe-fex-v3.json', () => {
    const { dte } = construirFacturaExportacion({
      receptor: {
        nombre: 'Foreign Buyer LLC',
        tipoDocumento: '37',
        numDocumento: '99999999',
        descActividad: 'Software',
        codPais: 'US',
        nombrePais: 'Estados Unidos',
        complemento: '123 Main St',
        tipoPersona: 2,
        correo: 'buyer@foreign.com',
      },
      items: [{ descripcion: 'Servicio de exportación', cantidad: 1, precioUni: 100, ventaGravada: 100 }],
      emisorExport: { tipoItemExpor: 2, recintoFiscal: null, tipoRegimen: null, regimen: null },
    });
    const { valido, errores } = validarDte(dte);
    assert.equal(valido, true, JSON.stringify(errores));
    assert.equal(dte.identificacion.tipoDte, '11');
  });

  test('lanza error si falta un campo requerido de emisorExport', () => {
    assert.throws(
      () =>
        construirFacturaExportacion({
          receptor: { nombre: 'X', tipoDocumento: '37', numDocumento: '1', descActividad: 'Y', codPais: 'US', nombrePais: 'EEUU', complemento: 'Z', tipoPersona: 2 },
          items: [{ descripcion: 'Item', cantidad: 1, precioUni: 1, ventaGravada: 1 }],
          emisorExport: { tipoItemExpor: 2 }, // faltan recintoFiscal/tipoRegimen/regimen
        }),
      /emisorExport/
    );
  });
});

describe('construirFacturaSujetoExcluido', () => {
  test('genera un DTE que valida contra fe-fse-v2.json', () => {
    const { dte } = construirFacturaSujetoExcluido({
      receptor: { tipoDocumento: '13', numDocumento: '01234567-8', nombre: 'Vendedor Informal', direccion: DIRECCION },
      items: [{ descripcion: 'Maíz', cantidad: 10, precioUni: 5, compra: 50 }],
      reteRenta: 5,
    });
    const { valido, errores } = validarDte(dte);
    assert.equal(valido, true, JSON.stringify(errores));
    assert.equal(dte.identificacion.tipoDte, '14');
  });

  test('resta la retención de renta del total a pagar', () => {
    const { dte } = construirFacturaSujetoExcluido({
      receptor: { tipoDocumento: '13', numDocumento: '01234567-8', nombre: 'Vendedor Informal', direccion: DIRECCION },
      items: [{ descripcion: 'Maíz', cantidad: 10, precioUni: 5, compra: 50 }],
      reteRenta: 5,
    });
    assert.equal(dte.resumen.totalCompra, 50);
    assert.equal(dte.resumen.totalPagar, 45);
  });

  for (const zona of ZONAS_DEL_PROCESO) {
    test(`fecEmi y horEmi en hora de El Salvador a las 20:00 SV con el proceso en ${zona}`, (t) => {
      usarZonaDelProceso(t, zona);
      fijarInstante(t, '2026-10-10T02:00:00.000Z');
      const { dte } = construirFacturaSujetoExcluido({
        receptor: { tipoDocumento: '13', numDocumento: '01234567-8', nombre: 'Vendedor Informal', direccion: DIRECCION },
        items: [{ descripcion: 'Maíz', cantidad: 10, precioUni: 5, compra: 50 }],
      });
      assert.equal(dte.identificacion.fecEmi, '2026-10-09');
      assert.equal(dte.identificacion.horEmi, '20:00:00');
    });
  }
});

describe('construirComprobanteDonacion', () => {
  test('genera un DTE que valida contra fe-cd-v2.json', () => {
    const { dte } = construirComprobanteDonacion({
      donante: {
        tipoDocumento: '13',
        numDocumento: '01234567-8',
        nombre: 'Juan Donante',
        codActividad: '62010',
        descActividad: 'Programación informática',
        direccion: DIRECCION,
        telefono: '22223333',
        correo: 'donante@example.com',
        codDomiciliado: 1,
        codPais: 'SV',
      },
      items: [{ tipoDonacion: 1, cantidad: 1, uniMedida: 59, descripcion: 'Donación en efectivo', tipoDepreciacion: 0, valorUni: 50, valor: 50 }],
    });
    const { valido, errores } = validarDte(dte);
    assert.equal(valido, true, JSON.stringify(errores));
    assert.equal(dte.identificacion.tipoDte, '15');
  });

  test('el "emisor" es quien recibe la donación y el "receptor" es el donante (particularidad del schema)', () => {
    const { dte } = construirComprobanteDonacion({
      donante: {
        tipoDocumento: '13',
        numDocumento: '01234567-8',
        nombre: 'Juan Donante',
        codActividad: '62010',
        descActividad: 'Programación informática',
        direccion: DIRECCION,
        telefono: '22223333',
        correo: 'donante@example.com',
        codDomiciliado: 1,
        codPais: 'SV',
      },
      items: [{ tipoDonacion: 1, cantidad: 1, uniMedida: 59, descripcion: 'Donación', tipoDepreciacion: 0, valorUni: 50, valor: 50 }],
    });
    assert.equal(dte.receptor.nombre, 'Juan Donante');
    assert.notEqual(dte.emisor.nombre, 'Juan Donante');
  });

  test('lanza error si falta un campo requerido del donante', () => {
    assert.throws(
      () => construirComprobanteDonacion({ donante: { nombre: 'Incompleto' }, items: [{ tipoDonacion: 1, cantidad: 1, uniMedida: 59, descripcion: 'X', valorUni: 1, valor: 1 }] }),
      /donante/
    );
  });
});
