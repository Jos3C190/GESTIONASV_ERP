const { test, describe, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { generarPDF } = require('../../src/services/representacionGraficaBuilder');
const { construirFactura, construirCCF } = require('../../src/services/dteBuilder');
const {
  construirDocumentoContableLiquidacion,
  construirComprobanteRetencion,
  construirFacturaSujetoExcluido,
  construirComprobanteDonacion,
} = require('../../src/services/dteBuilderOtros');
const { construirNotaCredito } = require('../../src/services/dteBuilderNotas');
const correlativoStore = require('../../src/services/correlativoStore');
const { textoPorPagina, textoCompleto, coloresUsados, contarPaginas, contarApariciones } = require('./_pdfTexto');

// PNG RGBA de 1 × 1 píxel; fixture mínima, no depende de recursos remotos.
const logo = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACXBIWXMAAAPoAAAD6AG1e1JrAAAADUlEQVR4nGMQCVjwHwADhAIEWAExyQAAAABJRU5ErkJggg==', 'base64');
const direccion = { departamento: '06', municipio: '23', distrito: '14', complemento: 'Col. Escalón' };

function facturaConReceptor(items = [{ descripcion: 'Servicio de prueba', cantidad: 1, precioUni: 100, ventaGravada: 100 }]) {
  return construirFactura({
    receptor: { tipoDocumento: '13', numDocumento: '012345678', nombre: 'Cliente de Prueba', correo: 'c@p.com', direccion },
    items,
  }).dte;
}

function renderizar(dte, opciones = {}) {
  return generarPDF(dte, { selloRecepcion: 'SELLO-DE-PRUEBA', ambiente: dte.identificacion.ambiente, ...opciones });
}

describe('representacionGraficaBuilder.js', () => {
  beforeEach(() => {
    correlativoStore.reiniciarAMemoria();
  });

  test('genera un PDF (Buffer no vacío) para una Factura con receptor', async () => {
    const { dte } = construirFactura({
      receptor: { tipoDocumento: '13', numDocumento: '01234567-8', nombre: 'Cliente de Prueba', correo: 'c@p.com' },
      items: [{ descripcion: 'Servicio de prueba', cantidad: 1, precioUni: 100, ventaGravada: 100 }],
    });
    const buffer = await generarPDF(dte, { selloRecepcion: 'SELLO-DE-PRUEBA', ambiente: '00' });
    assert.ok(Buffer.isBuffer(buffer));
    assert.ok(buffer.length > 0);
  });

  test('genera un PDF también con receptor null (consumidor final)', async () => {
    const { dte } = construirFactura({
      receptor: null,
      items: [{ descripcion: 'Servicio de prueba', cantidad: 1, precioUni: 100, ventaGravada: 100 }],
    });
    const buffer = await generarPDF(dte, { selloRecepcion: 'SELLO-DE-PRUEBA', ambiente: '00' });
    assert.ok(Buffer.isBuffer(buffer));
    const texto = textoCompleto(buffer);
    assert.equal(contarApariciones(texto, 'Consumidor final'), 2, 'Debe figurar en el receptor y en RECIBE');
  });

  test('maneja el caso de cuerpoDocumento como OBJETO, no arreglo (DCL)', async () => {
    const { dte } = construirDocumentoContableLiquidacion({
      receptor: {
        nit: '06141804941099',
        nrc: '7654321',
        nombre: 'Afiliado de Prueba S.A.',
        telefono: '22223333',
        correo: 'a@p.com',
        direccion: { departamento: '06', municipio: '20', distrito: '01', complemento: 'Dir' },
        tipoEstablecimiento: '02',
        codActividad: '62010',
        descActividad: 'Programación informática',
      },
      datos: {
        periodoLiquidacionFechaInicio: '2026-06-01',
        periodoLiquidacionFechaFin: '2026-06-30',
        codLiquidacion: 'LIQ-1',
        cantidadDoc: 1,
        valorOperaciones: 100,
        montoSinPercepcion: null,
        descripSinPercepcion: null,
        subTotal: 100,
        iva: 13,
        montoSujetoPercepcion: 100,
        ivaPercibido: 2,
        comision: 0,
        porcentComision: 0,
        ivaComision: 0,
        liquidoApagar: 100,
        observaciones: null,
      },
      responsable: { nombEntrega: 'Juan', docuEntrega: '06141804941035', codEmpleado: null },
    });
    const buffer = await generarPDF(dte, { selloRecepcion: 'SELLO-DE-PRUEBA', ambiente: '00' });
    assert.ok(Buffer.isBuffer(buffer));
    const texto = textoCompleto(buffer);
    assert.match(texto, /DETALLE DE LA LIQUIDACIÓN/);
    assert.match(texto, /01 Jun 2026/);
    assert.match(texto, /LÍQUIDO A PAGAR:/);
    assert.match(texto, /CIEN 00\/100 DÓLARES/);
  });

  test('rechaza generar el PDF final si falta selloRecepcion', async () => {
    const { dte } = construirFactura({ receptor: null, items: [{ descripcion: 'X', cantidad: 1, precioUni: 10, ventaGravada: 10 }] });
    await assert.rejects(() => generarPDF(dte, { ambiente: '00' }), /sello de recepción/);
  });

  test('rechaza mezclar el ambiente vivo con el ambiente histórico del DTE', async () => {
    const { dte } = construirFactura({ receptor: null, items: [{ descripcion: 'X', cantidad: 1, precioUni: 10, ventaGravada: 10 }] });
    await assert.rejects(
      () => generarPDF(dte, { selloRecepcion: 'SELLO', ambiente: dte.identificacion.ambiente === '00' ? '01' : '00' }),
      /ambiente histórico/,
    );
  });

  test('genera representación simulada sin URL ni QR oficial', async () => {
    const { dte } = construirFactura({ receptor: null, items: [{ descripcion: 'X', cantidad: 1, precioUni: 10, ventaGravada: 10 }] });
    const buffer = await generarPDF(dte, {
      selloRecepcion: 'SIMULATED-1234567890',
      ambiente: dte.identificacion.ambiente,
      simulation: true,
    });
    assert.ok(buffer.length > 0);
    const crudo = buffer.toString('latin1');
    assert.doesNotMatch(crudo, /admin\.factura\.gob\.sv/);
    assert.doesNotMatch(crudo, /\/Subtype \/Image/, 'Sin logo, un simulado no debe incrustar imagen de QR');
    const texto = textoCompleto(buffer);
    assert.doesNotMatch(texto, /admin\.factura\.gob\.sv/);
    assert.match(texto, /Identificador simulado/);
    assert.match(texto, /SIN CÓDIGO QR/);
    assert.match(texto, /SIMULADO - SIN VALIDEZ FISCAL/);

    // Control positivo: el documento real sí lleva QR y enlace de consulta pública.
    const real = (await renderizar(dte)).toString('latin1');
    assert.match(real, /\/URI \(https:\/\/admin\.factura\.gob\.sv\/consultaPublica\?/);
    assert.match(real, /\/Subtype \/Image/);
  });

  test('usa papel Carta y dibuja todas las secciones del formato, con "-" en las vacías', async () => {
    const buffer = await renderizar(facturaConReceptor());
    assert.match(buffer.toString('latin1'), /\/MediaBox \[0 0 612 792\]/);
    const texto = textoCompleto(buffer);
    for (const etiqueta of [
      'DOCUMENTO TRIBUTARIO ELECTRÓNICO', 'FACTURA', 'Información del receptor', 'Venta a Cuenta de Terceros',
      'DOCUMENTO RELACIONADO', 'OTROS DOCUMENTOS ASOCIADOS', 'OBSERVACIONES', 'Total en Letras:', 'Sumas:',
      'TOTAL A PAGAR:', 'ENTREGA', 'RECIBE', 'Fecha de representación gráfica:', 'Página 1 de 1',
    ]) {
      assert.ok(texto.includes(etiqueta), `Falta "${etiqueta}"`);
    }
    assert.ok(texto.split('\n').filter((linea) => linea === '-').length >= 7, 'Terceros y tablas de referencia vacías muestran "-"');
  });

  test('traduce los códigos de catálogo a nombres legibles', async () => {
    const dte = facturaConReceptor([{ descripcion: 'Tela', cantidad: 2, precioUni: 5, ventaGravada: 10, uniMedida: 36 }]);
    const texto = textoCompleto(await renderizar(dte));
    assert.match(texto, /SAN SALVADOR CENTRO/);
    assert.match(texto, /^Libra$/m);
    assert.match(texto, /^Casa Matriz$/m);
    assert.match(texto, /^DUI$/m);
    assert.match(texto, /^01234567-8$/m);
    assert.match(texto, /^Contado$/m);
  });

  test('forma de pago 99 muestra el medio indicado en referencia, no la instrucción del catálogo', async () => {
    const { dte } = construirFactura({
      receptor: null,
      items: [{ descripcion: 'Producto', cantidad: 1, precioUni: 37, ventaGravada: 37 }],
      pago: { codigo: '99', montoPago: 37, referencia: 'Tarjeta Wompi 12345-1700000000-00001' },
    });
    const texto = textoCompleto(await renderizar(dte));
    assert.match(texto, /Otros \(Tarjeta Wompi 12345-1700000000-00001\)/);
    assert.doesNotMatch(texto, /se debe indicar el medio de pago/);
    assert.doesNotMatch(texto, /Ref\. Tarjeta Wompi/);

    const { dte: transferencia } = construirFactura({
      receptor: null,
      items: [{ descripcion: 'Producto', cantidad: 1, precioUni: 37, ventaGravada: 37 }],
      pago: { codigo: '05', montoPago: 37, referencia: 'BAC 004512' },
    });
    const textoTransferencia = textoCompleto(await renderizar(transferencia));
    assert.match(textoTransferencia, /Transferencia-Depósito Bancario/);
    assert.match(textoTransferencia, /Ref\. BAC 004512/);
  });

  test('imprime el IVA una sola vez: aditivo cuando se suma a la base (CCF)', async () => {
    const { dte } = construirCCF({
      receptor: { nit: '06141804941099', nrc: '7654321', nombre: 'Prueba S.A.', codActividad: '62010', descActividad: 'Programación informática', direccion, telefono: '22223333', correo: 'prueba@example.com' },
      items: [{ descripcion: 'Producto', cantidad: 1, precioUni: 10, ventaGravada: 10 }],
    });
    const texto = textoCompleto(await renderizar(dte));
    assert.equal(contarApariciones(texto, 'IVA 13%:'), 1);
    assert.doesNotMatch(texto, /Impuesto al Valor Agregado/);
    assert.doesNotMatch(texto, /\(informativo\)/);
  });

  test('la Factura presenta el IVA como informativo porque sus precios ya lo incluyen', async () => {
    // Manual Funcional XIV: en la Factura precio y venta gravada llevan el IVA
    // incluido; totalIva solo informa cuánto IVA contiene el total.
    const dte = facturaConReceptor();
    assert.equal(dte.resumen.totalPagar, dte.resumen.subTotal);
    const texto = textoCompleto(await renderizar(dte));
    assert.match(texto, /IVA 13% \(informativo\):/);
    assert.equal(contarApariciones(texto, 'IVA 13%:'), 0);
  });

  test('CCF con descuento por ítem y Factura en contingencia con cargo no afecto', async () => {
    const { dte: ccf } = construirCCF({
      receptor: { nit: '06141804941099', nrc: '7654321', nombre: 'Cliente Empresa S.A.', codActividad: '62010', descActividad: 'Programación informática', direccion, telefono: '22223333', correo: 'c@e.com' },
      items: [{ descripcion: 'Servicio', cantidad: 2, precioUni: 22.12, montoDescu: 4.42, ventaGravada: 39.82, ivaItem: 5.18 }],
    });
    const textoCcf = textoCompleto(await renderizar(ccf));
    assert.match(textoCcf, /^\$ 4\.42$/m);
    assert.equal(contarApariciones(textoCcf, 'IVA 13%:'), 1);
    assert.match(textoCcf, /^\$ 45\.00$/m, 'Total a pagar = 39.82 + 5.18');

    const { dte: factura } = construirFactura({
      receptor: null,
      items: [
        { descripcion: 'Producto', cantidad: 1, precioUni: 113, ventaGravada: 113 },
        { descripcion: 'Cargo por envío (courier)', cantidad: 1, uniMedida: 99, precioUni: 0, ventaGravada: 0, noGravado: 3.5 },
      ],
    }, { contingencia: { tipoContingencia: 5, motivoContin: 'Prueba de contingencia' } });
    const textoFactura = textoCompleto(await renderizar(factura));
    assert.match(textoFactura, /^Diferido$/m);
    assert.match(textoFactura, /^Contingencia$/m);
    assert.match(textoFactura, /Prueba de\s+contingencia/);
    assert.match(textoFactura, /Total otros montos no afectos:/);
    assert.match(textoFactura, /^\$ 116\.50$/m, 'Total a pagar = 113.00 + 3.50 no afecto');
    assert.match(textoFactura, /IVA 13% \(informativo\):/);
  });

  test('formatea la fecha de emisión y la de representación sin desfase de zona horaria', async () => {
    const dte = facturaConReceptor();
    const conFecha = { ...dte, identificacion: { ...dte.identificacion, fecEmi: '2026-09-28', horEmi: '14:03:20' } };
    const texto = textoCompleto(await renderizar(conFecha, { fechaRepresentacion: '2026-10-04' }));
    assert.match(texto, /28 Sep 2026 14:03:20/);
    assert.match(texto, /^04 Oct 2026$/m);
  });

  test('solo usa grises: negro, blanco y grises neutros en documento real, simulado y con logo', async () => {
    const dte = facturaConReceptor();
    const variantes = [
      await renderizar(dte),
      await renderizar(dte, { logoPngBuffer: logo }),
      await renderizar(dte, { simulation: true, selloRecepcion: 'SIMULATED-1', logoPngBuffer: logo }),
    ];
    for (const buffer of variantes) {
      const colores = coloresUsados(buffer);
      assert.ok(colores.length > 0);
      for (const [r, g, b] of colores) {
        assert.ok(r === g && g === b, `Color no monocromático: ${r} ${g} ${b}`);
      }
    }
  });

  test('pagina 40 ítems repitiendo la cabecera y sin partir el bloque final', async () => {
    const items = Array.from({ length: 40 }, (_, i) => ({
      descripcion: `Artículo ${i + 1}`, cantidad: 1, precioUni: 5, ventaGravada: 5, codigo: `SKU-${i + 1}`,
    }));
    const dte = facturaConReceptor(items);
    const antes = JSON.stringify(dte);
    const buffer = await renderizar(dte);
    assert.equal(JSON.stringify(dte), antes, 'El renderer no debe mutar el DTE');

    const paginas = textoPorPagina(buffer);
    assert.ok(paginas.length >= 2);
    assert.equal(contarPaginas(buffer), paginas.length);
    paginas.forEach((pagina, indice) => {
      assert.match(pagina, /^Descripción$/m, `La página ${indice + 1} debe repetir la cabecera de ítems`);
      assert.ok(pagina.includes(`Página ${indice + 1} de ${paginas.length}`));
      if (indice > 0) {
        assert.match(pagina, /FACTURA \(continuación\)/);
        assert.ok(pagina.includes(dte.identificacion.numeroControl));
      }
    });
    const texto = paginas.join('\n');
    assert.equal(contarApariciones(texto, 'TOTAL A PAGAR:'), 1);
    assert.equal(contarApariciones(texto, 'Sumas:'), 1);
    for (let i = 1; i <= 40; i += 1) assert.match(texto, new RegExp(`^Artículo ${i}$`, 'm'));
  });

  test('mantiene juntos la última fila, las sumas, los totales y las firmas para 20 a 34 ítems', async () => {
    for (let cantidad = 20; cantidad <= 34; cantidad += 1) {
      correlativoStore.reiniciarAMemoria();
      const items = Array.from({ length: cantidad }, (_, i) => ({ descripcion: `Ítem ${i + 1}`, cantidad: 1, precioUni: 1, ventaGravada: 1 }));
      const paginas = textoPorPagina(await renderizar(facturaConReceptor(items), { logoPngBuffer: logo }));
      const ultima = paginas[paginas.length - 1];
      for (const etiqueta of ['OBSERVACIONES', 'TOTAL A PAGAR:', 'Sumas:', 'ENTREGA', 'RECIBE', `Ítem ${cantidad}`]) {
        assert.ok(ultima.includes(etiqueta), `${cantidad} ítems: "${etiqueta}" debe estar en la última página`);
      }
      paginas.forEach((pagina, indice) => {
        assert.match(pagina, /^Ítem \d+$/m, `${cantidad} ítems: la página ${indice + 1} no debe quedar sin ítems`);
      });
    }
  });

  test('reemplaza caracteres fuera de WinAnsi sin perder las comillas tipográficas', async () => {
    const dte = facturaConReceptor([{ descripcion: 'Taza ☕ “especial” – edición', cantidad: 1, precioUni: 10, ventaGravada: 10 }]);
    const texto = textoCompleto(await renderizar(dte));
    assert.match(texto, /^Taza \? “especial” – edición$/m);
  });

  test('el CCF muestra NRC formateado, NIT del receptor e IVA percibido', async () => {
    const { dte } = construirCCF({
      receptor: { nit: '06141804941099', nrc: '7654321', nombre: 'Prueba S.A.', codActividad: '62010', descActividad: 'Programación informática', direccion, telefono: '22223333', correo: 'prueba@example.com' },
      items: [{ descripcion: 'Producto', cantidad: 1, precioUni: 10, ventaGravada: 10 }],
    });
    const texto = textoCompleto(await renderizar(dte));
    assert.match(texto, /COMPROBANTE DE CRÉDITO FISCAL/);
    assert.match(texto, /^765432-1$/m);
    assert.match(texto, /^0614-180494-109-9$/m);
    assert.match(texto, /IVA Percibido:/);
    assert.equal(contarApariciones(texto, 'IVA 13%:'), 1);
  });

  test('retención, sujeto excluido y donación muestran sus propios montos', async () => {
    const receptor = { tipoDocumento: '36', numDocumento: '06141804941099', nombre: 'Proveedor S.A.', codActividad: '62010', descActividad: 'Programación', direccion, telefono: '22223333', correo: 'p@e.com' };
    const retencion = construirComprobanteRetencion({
      receptor,
      retenciones: [{ tipoDte: '03', tipoGeneracion: 2, numeroDocumento: 'DTE-03-M001P001-000000000000009', fechaEmision: '2026-09-28', montoSujetoGrav: 100, codigoRetencionMH: '22', ivaRetenido: 1 }],
    }).dte;
    const textoRetencion = textoCompleto(await renderizar(retencion));
    assert.match(textoRetencion, /TOTAL IVA RETENIDO:/);
    assert.match(textoRetencion, /^Comprobante de crédito/m);
    assert.ok(contarApariciones(textoRetencion, '$ 1.00') >= 2);
    assert.ok(textoRetencion.includes('DTE-03-M001P001-000000000000009'));
    assert.match(textoRetencion, /IVA generado 13%:/);
    assert.match(textoRetencion, /^\$ 13\.00$/m);

    // Un comprobante guardado con el schema anterior (numDocumento) se sigue imprimiendo igual.
    const retencionAnterior = structuredClone(retencion);
    const lineaAnterior = retencionAnterior.cuerpoDocumento[0];
    lineaAnterior.numDocumento = lineaAnterior.numeroDocumento;
    delete lineaAnterior.numeroDocumento;
    assert.ok(textoCompleto(await renderizar(retencionAnterior)).includes('DTE-03-M001P001-000000000000009'));

    const sujetoExcluido = construirFacturaSujetoExcluido({
      receptor: { tipoDocumento: '13', numDocumento: '012345678', nombre: 'Proveedor informal', direccion },
      items: [{ descripcion: 'Compra de tela', cantidad: 3, precioUni: 4, compra: 12 }],
      reteRenta: 1.2,
    }).dte;
    const textoSujeto = textoCompleto(await renderizar(sujetoExcluido));
    assert.match(textoSujeto, /Información del sujeto excluido/);
    assert.match(textoSujeto, /^Compra$/m);
    assert.match(textoSujeto, /^\$ 10\.80$/m);
    assert.match(textoSujeto, /DIEZ 80\/100 DÓLARES/);

    const donacion = construirComprobanteDonacion({
      donante: { ...receptor, codDomiciliado: 1, codPais: '9300' },
      items: [{ tipoDonacion: 1, cantidad: 1, uniMedida: 99, descripcion: 'Aporte', valorUni: 50, valor: 50 }],
    }).dte;
    const textoDonacion = textoCompleto(await renderizar(donacion));
    assert.match(textoDonacion, /Información del donante/);
    assert.match(textoDonacion, /VALOR TOTAL:/);
    assert.match(textoDonacion, /^Efectivo$/m);
  });

  test('la Nota de Crédito muestra sus CCF relacionados con fecha y el documento que ajusta cada línea', async () => {
    const ccfA = '0A1B2C3D-4E5F-4061-8728-394A5B6C7D8E';
    const ccfB = '1F2E3D4C-5B6A-4798-8A9B-0C1D2E3F4A5B';
    const { dte } = construirNotaCredito({
      receptor: { tipoDocumento: '36', numDocumento: '06141804941099', nrc: '7654321', nombre: 'Cliente Empresa S.A.', codActividad: '62010', descActividad: 'Programación informática', direccion, telefono: '22223333', correo: 'c@e.com' },
      documentosRelacionados: [
        { tipoDocumento: '03', tipoGeneracion: 2, numeroDocumento: ccfA, fechaEmision: '2026-07-01' },
        { tipoDocumento: '03', tipoGeneracion: 2, numeroDocumento: ccfB, fechaEmision: '2026-08-15' },
      ],
      items: [
        { descripcion: 'Camiseta devuelta', cantidad: 1, precioUni: 20, ventaGravada: 20, numeroDocumento: ccfA },
        { descripcion: 'Rebaja de precio', cantidad: 1, precioUni: 5, ventaGravada: 5, numeroDocumento: ccfB },
      ],
      observaciones: 'Devolución parcial',
    });
    const texto = textoCompleto(await renderizar(dte));
    assert.match(texto, /^NOTA DE CRÉDITO$/m);
    assert.match(texto, /^DOCUMENTO RELACIONADO$/m);
    assert.match(texto, /^FECHA DE EMISIÓN$/m);
    assert.equal(contarApariciones(texto, 'Comprobante de crédito fiscal (Electrónico)'), 2);
    assert.match(texto, new RegExp(`^${ccfA}\n01 Jul 2026$`, 'm'));
    assert.match(texto, new RegExp(`^${ccfB}\n15 Ago 2026$`, 'm'));
    assert.match(texto, new RegExp(`^Camiseta devuelta\nDoc\. relacionado ${ccfA}$`, 'm'));
    assert.match(texto, new RegExp(`^Rebaja de precio\nDoc\. relacionado ${ccfB}$`, 'm'));
    assert.equal(contarApariciones(texto, 'IVA 13%:'), 1);
    assert.match(texto, /^\$ 3\.25$/m);
    assert.match(texto, /^\$ 28\.25$/m, 'Total = 25.00 + 3.25 de IVA');
    assert.match(texto, /VEINTIOCHO 25\/100 DÓLARES/);
    assert.match(texto, /^Devolución parcial$/m);
  });
});
