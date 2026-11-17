const { generarCodigoGeneracion } = require('../utils/codigoGeneracion');
const { generarNumeroControl } = require('../utils/numeroControl');
const { fechaHoraSV } = require('../utils/fechaHoraSV');
const { numeroALetras } = require('../utils/numeroALetras');
const { r2 } = require('./calculoFiscal');
const { TIPO_DTE, MODELO_FACTURACION, TIPO_TRANSMISION, CONDICION_OPERACION } = require('../config/catalogs');
const config = require('../config');

/**
 * Cada tipo de documento incluye un subconjunto distinto de campos
 * "opcionales pero required" en identificacion (confirmado inspeccionando
 * identificacion.required de cada schema real):
 *   - tipoContingencia/motivoContin: presentes en CR, FEX, FSE (y en NC/ND/NR)
 *   - fusion: presente en CL (y en NC/ND)
 *   - DCL no lleva ninguno de los dos
 */
function _construirIdentificacion({ tipoDte, version, incluirContingencia = false, incluirFusion = false }) {
  const codigoGeneracion = generarCodigoGeneracion();
  const { fecha, hora, anio } = fechaHoraSV();
  const numeroControl = generarNumeroControl({
    tipoDte,
    tipoEstablecimiento: config.emisor.tipoEstablecimiento,
    codEstablecimientoMH: config.emisor.codEstablecimientoMH,
    codPuntoVentaMH: config.emisor.codPuntoVentaMH,
    anio,
  });

  const identificacion = {
    version,
    ambiente: config.ambiente,
    tipoDte,
    numeroControl,
    codigoGeneracion,
    tipoModelo: MODELO_FACTURACION.PREVIO,
    tipoOperacion: TIPO_TRANSMISION.NORMAL,
    fecEmi: fecha,
    horEmi: hora,
    tipoMoneda: 'USD',
  };
  if (incluirContingencia) {
    identificacion.tipoContingencia = null;
    identificacion.motivoContin = null;
  }
  if (incluirFusion) {
    identificacion.fusion = null;
  }

  return { identificacion, codigoGeneracion, numeroControl };
}

function _direccionCompleta(direccion) {
  if (!direccion || !direccion.departamento || !direccion.municipio || !direccion.distrito || !direccion.complemento) {
    throw new Error('direccion incompleta: se requieren departamento, municipio, distrito y complemento');
  }
  return direccion;
}

// ============================================================================
// CR — Comprobante de Retención (tipoDte 07, schema fe-cr-v2.json, version 2)
// ============================================================================
/**
 * Documenta la retención de IVA (1% o 13%, CAT-006) que un contribuyente
 * "gran contribuyente" aplica a otro por sus compras. `retenciones` = lista
 * de documentos a los que se les retuvo: [{ tipoDte (CAT-002 del doc
 * original, ej "03"), tipoGeneracion (1|2), numeroDocumento, fechaEmision,
 * montoSujetoGrav, codigoRetencionMH (CAT-006), ivaRetenido, descripcion? }]
 *
 * El schema de agosto de 2026 renombró numDocumento a numeroDocumento; la
 * entrada acepta ambos nombres y el DTE sale con el nuevo.
 */
function construirComprobanteRetencion({ receptor, retenciones }) {
  const { identificacion, codigoGeneracion, numeroControl } = _construirIdentificacion({
    tipoDte: TIPO_DTE.COMPROBANTE_RETENCION,
    version: 2,
    incluirContingencia: true,
  });

  if (!Array.isArray(retenciones) || retenciones.length === 0) {
    throw new Error('Se requiere "retenciones" con al menos un documento retenido');
  }

  const cuerpoDocumento = retenciones.map((r, idx) => ({
    numItem: idx + 1,
    tipoDte: r.tipoDte,
    tipoGeneracion: r.tipoGeneracion,
    numeroDocumento: r.numeroDocumento ?? r.numDocumento,
    fechaEmision: r.fechaEmision,
    montoSujetoGrav: r.montoSujetoGrav,
    codigoRetencionMH: r.codigoRetencionMH,
    ivaRetenido: r.ivaRetenido,
    descripcion: r.descripcion ?? null,
  }));

  const totalSujetoRetencion = Number(retenciones.reduce((s, r) => s + r.montoSujetoGrav, 0).toFixed(2));
  const totalIvaRetenido = Number(retenciones.reduce((s, r) => s + r.ivaRetenido, 0).toFixed(2));
  // "IVA generado 13%" sobre el monto sujeto a retención (Normativa V2.0,
  // anexo II, campo 157). Es informativo: no cambia el IVA retenido.
  const totalIva = r2(totalSujetoRetencion * 0.13);

  const dte = {
    identificacion,
    emisor: {
      nit: config.emisor.nit,
      nrc: config.emisor.nrc,
      nombre: config.emisor.nombre,
      codActividad: config.emisor.codActividad,
      descActividad: config.emisor.descActividad,
      nombreComercial: config.emisor.nombreComercial,
      direccion: _direccionCompleta(config.emisor.direccion),
      codEstable: config.emisor.codEstableInterno,
      codPuntoVenta: config.emisor.codPuntoVentaInterno,
      telefono: config.emisor.telefono,
      correo: config.emisor.correo,
    },
    receptor: {
      tipoDocumento: receptor.tipoDocumento,
      numDocumento: receptor.numDocumento,
      nrc: receptor.nrc ?? null,
      nombre: receptor.nombre,
      codActividad: receptor.codActividad,
      descActividad: receptor.descActividad,
      nombreComercial: receptor.nombreComercial ?? null,
      direccion: _direccionCompleta(receptor.direccion),
      telefono: receptor.telefono,
      correo: receptor.correo,
    },
    cuerpoDocumento,
    resumen: {
      totalSujetoRetencion,
      totalIva,
      totalIvaRetenido,
      totalLetras: null,
      observaciones: null,
    },
    apendice: null,
  };

  return { dte, codigoGeneracion, numeroControl };
}

// ============================================================================
// CL — Comprobante de Liquidación (tipoDte 08, schema fe-cl-v2.json, v2)
// ============================================================================
/**
 * Usado por quien liquida operaciones de terceros (ej. una plataforma que
 * liquida a un afiliado). `liquidaciones` = documentos que se liquidan:
 * [{ tipoDte, tipoGeneracion, numeroDocumento, fechaEmision, ventaGravada,
 *    ventaNoSuj?, ventaExenta?, exportaciones?, observaciones? }]
 */
function construirComprobanteLiquidacion({ receptor, liquidaciones }) {
  const { identificacion, codigoGeneracion, numeroControl } = _construirIdentificacion({
    tipoDte: TIPO_DTE.COMPROBANTE_LIQUIDACION,
    version: 2,
    incluirFusion: true, // CL exige "fusion", pero NO tipoContingencia/motivoContin
  });

  if (!Array.isArray(liquidaciones) || liquidaciones.length === 0) {
    throw new Error('Se requiere "liquidaciones" con al menos un documento a liquidar');
  }

  const cuerpoDocumento = liquidaciones.map((l, idx) => {
    const ventaGravada = l.ventaGravada ?? 0;
    return {
      numItem: idx + 1,
      tipoDte: l.tipoDte,
      tipoGeneracion: l.tipoGeneracion,
      numeroDocumento: l.numeroDocumento,
      fechaEmision: l.fechaEmision,
      ventaNoSuj: l.ventaNoSuj ?? 0,
      ventaExenta: l.ventaExenta ?? 0,
      ventaGravada,
      exportaciones: l.exportaciones ?? 0,
      tributos: ventaGravada > 0 ? ['20'] : null,
      ivaItem: Number((ventaGravada * 0.13).toFixed(2)),
      observaciones: l.observaciones ?? null,
    };
  });

  const totalGravada = Number(liquidaciones.reduce((s, l) => s + (l.ventaGravada ?? 0), 0).toFixed(2));
  const totalExenta = Number(liquidaciones.reduce((s, l) => s + (l.ventaExenta ?? 0), 0).toFixed(2));
  const totalNoSuj = Number(liquidaciones.reduce((s, l) => s + (l.ventaNoSuj ?? 0), 0).toFixed(2));
  const totalExportacion = Number(liquidaciones.reduce((s, l) => s + (l.exportaciones ?? 0), 0).toFixed(2));
  // IMPORTANTE: se deriva de la SUMA de los ivaItem por línea (ya
  // redondeados arriba), no de totalGravada*0.13 por separado — evita el
  // desfase de redondeo (ver nota equivalente en dteBuilder.js).
  const ivaPerci = Number(cuerpoDocumento.reduce((s, l) => s + l.ivaItem, 0).toFixed(2));
  const subTotalVentas = Number((totalGravada + totalExenta + totalNoSuj + totalExportacion).toFixed(2));
  const total = Number((subTotalVentas + ivaPerci).toFixed(2));

  const dte = {
    identificacion,
    emisor: {
      nit: config.emisor.nit,
      nrc: config.emisor.nrc,
      nombre: config.emisor.nombre,
      codActividad: config.emisor.codActividad,
      descActividad: config.emisor.descActividad,
      nombreComercial: config.emisor.nombreComercial,
      direccion: _direccionCompleta(config.emisor.direccion),
      telefono: config.emisor.telefono,
      correo: config.emisor.correo,
      codEstable: config.emisor.codEstableInterno,
      codPuntoVenta: config.emisor.codPuntoVentaInterno,
    },
    receptor: {
      tipoDocumento: receptor.tipoDocumento,
      numDocumento: receptor.numDocumento,
      codDomiciliado: receptor.codDomiciliado ?? 1,
      nrc: receptor.nrc ?? null,
      nombre: receptor.nombre,
      codActividad: receptor.codActividad,
      descActividad: receptor.descActividad,
      nombreComercial: receptor.nombreComercial ?? null,
      direccion: _direccionCompleta(receptor.direccion),
      telefono: receptor.telefono,
      correo: receptor.correo,
    },
    cuerpoDocumento,
    resumen: {
      totalNoSuj,
      totalExenta,
      totalGravada,
      exportacion: totalExportacion,
      subTotalVentas,
      tributos: totalGravada > 0 ? [{ codigo: '20', descripcion: 'Impuesto al Valor Agregado 13%', valor: ivaPerci }] : null,
      montoTotalOperacion: total,
      ivaPerci,
      total,
      totalLetras: null,
      condicionOperacion: CONDICION_OPERACION.CONTADO,
      observaciones: null,
    },
    apendice: null,
  };

  return { dte, codigoGeneracion, numeroControl };
}

// ============================================================================
// DCL — Documento Contable de Liquidación (tipoDte 09, schema fe-dcl-v2.json)
// ============================================================================
/**
 * A diferencia de los demás, "cuerpoDocumento" aquí es un OBJETO único (no
 * un arreglo) con los totales del período liquidado. `datos` debe traer los
 * campos de negocio (valorOperaciones, subTotal, iva, comisión, etc.) — este
 * documento resume matemática de comisiones que varía mucho por modelo de
 * negocio, así que NO se calcula automáticamente: se recibe ya calculado.
 */
function construirDocumentoContableLiquidacion({ receptor, datos, responsable }) {
  const { identificacion, codigoGeneracion, numeroControl } = _construirIdentificacion({
    tipoDte: TIPO_DTE.DOCUMENTO_CONTABLE_LIQUIDACION,
    version: 2, // DCL no lleva tipoContingencia/motivoContin ni fusion
  });

  const requeridos = [
    'periodoLiquidacionFechaInicio',
    'periodoLiquidacionFechaFin',
    'valorOperaciones',
    'subTotal',
    'iva',
    'montoSujetoPercepcion',
    'ivaPercibido',
    'comision',
    'porcentComision',
    'ivaComision',
    'liquidoApagar',
  ];
  const faltantes = requeridos.filter((campo) => datos?.[campo] === undefined);
  if (faltantes.length) {
    throw new Error(`"datos" incompleto para DCL: faltan ${faltantes.join(', ')}`);
  }
  if (!responsable || !responsable.nombEntrega || !responsable.docuEntrega) {
    throw new Error('Se requiere "responsable": { nombEntrega, docuEntrega, codEmpleado? }');
  }

  const dte = {
    identificacion,
    emisor: {
      nit: config.emisor.nit,
      nrc: config.emisor.nrc,
      nombre: config.emisor.nombre,
      codActividad: config.emisor.codActividad,
      descActividad: config.emisor.descActividad,
      nombreComercial: config.emisor.nombreComercial,
      telefono: config.emisor.telefono,
      correo: config.emisor.correo,
      direccion: _direccionCompleta(config.emisor.direccion),
      // Antes del schema de agosto de 2026 se llamaban codigo y puntoVenta.
      codEstable: config.emisor.codEstableInterno,
      codPuntoVenta: config.emisor.codPuntoVentaInterno,
    },
    receptor: {
      nit: receptor.nit,
      nrc: receptor.nrc,
      nombre: receptor.nombre,
      telefono: receptor.telefono,
      correo: receptor.correo,
      direccion: _direccionCompleta(receptor.direccion),
      tipoEstablecimiento: receptor.tipoEstablecimiento,
      codActividad: receptor.codActividad,
      descActividad: receptor.descActividad,
      nombreComercial: receptor.nombreComercial ?? null,
    },
    cuerpoDocumento: {
      periodoLiquidacionFechaInicio: datos.periodoLiquidacionFechaInicio,
      periodoLiquidacionFechaFin: datos.periodoLiquidacionFechaFin,
      codLiquidacion: datos.codLiquidacion ?? null,
      cantidadDoc: datos.cantidadDoc ?? null,
      valorOperaciones: datos.valorOperaciones,
      montoSinPercepcion: datos.montoSinPercepcion ?? null,
      descripSinPercepcion: datos.descripSinPercepcion ?? null,
      subTotal: datos.subTotal,
      iva: datos.iva,
      montoSujetoPercepcion: datos.montoSujetoPercepcion,
      ivaPercibido: datos.ivaPercibido,
      comision: datos.comision,
      porcentComision: datos.porcentComision,
      ivaComision: datos.ivaComision,
      liquidoApagar: datos.liquidoApagar,
      totalLetras: numeroALetras(datos.liquidoApagar),
      observaciones: datos.observaciones ?? null,
    },
    extension: {
      nombEntrega: responsable.nombEntrega,
      docuEntrega: responsable.docuEntrega,
      codEmpleado: responsable.codEmpleado ?? null,
    },
    apendice: null,
  };

  return { dte, codigoGeneracion, numeroControl };
}

// ============================================================================
// FEX — Factura de Exportación (tipoDte 11, schema fe-fex-v3.json, v3)
// ============================================================================
/**
 * `emisorExport` = { tipoItemExpor (CAT catálogo de tipo de exportación,
 * integer), recintoFiscal (CAT-027), tipoRegimen (CAT-033), regimen (CAT-028) }
 * `receptor` = comprador extranjero: { nombre, tipoDocumento, numDocumento,
 * descActividad, nombreComercial?, codPais (CAT-020), nombrePais,
 * complemento, tipoPersona (CAT-029), telefono?, correo? }
 */
function construirFacturaExportacion({ receptor, items, emisorExport, resumenExtra = {} }) {
  if (!Array.isArray(items) || items.length === 0) throw new Error('Se requiere "items" con al menos 1 línea');
  const { identificacion, codigoGeneracion, numeroControl } = _construirIdentificacion({
    tipoDte: TIPO_DTE.FACTURA_EXPORTACION,
    version: 3,
    incluirContingencia: true,
  });

  const camposEmisorExport = ['tipoItemExpor', 'recintoFiscal', 'tipoRegimen', 'regimen'];
  const faltantesEmisor = camposEmisorExport.filter((c) => emisorExport?.[c] === undefined);
  if (faltantesEmisor.length) {
    throw new Error(`"emisorExport" incompleto: faltan ${faltantesEmisor.join(', ')}`);
  }

  const camposReceptor = ['nombre', 'tipoDocumento', 'numDocumento', 'descActividad', 'codPais', 'nombrePais', 'complemento', 'tipoPersona'];
  const faltantesReceptor = camposReceptor.filter((c) => receptor?.[c] === undefined);
  if (faltantesReceptor.length) {
    throw new Error(`"receptor" incompleto para FEX: faltan ${faltantesReceptor.join(', ')}`);
  }

  const cuerpoDocumento = items.map((item, idx) => ({
    numItem: idx + 1,
    tipoItem: item.tipoItem ?? 1,
    numeroDocumento: null,
    cantidad: item.cantidad,
    codigo: item.codigo ?? null,
    codTributo: item.codTributo ?? null,
    uniMedida: item.uniMedida ?? 59,
    descripcion: item.descripcion,
    precioUni: item.precioUni,
    montoDescu: item.montoDescu ?? 0,
    ventaGravada: item.ventaGravada,
    tributos: null, // Exportaciones gravan IVA al 0% (CAT-015 código C3); ver resumen.tributos si aplica
    noGravado: item.noGravado ?? 0,
  }));

  const totalGravada = Number(items.reduce((s, i) => s + i.ventaGravada, 0).toFixed(2));

  const dte = {
    identificacion,
    documentoRelacionado: null,
    emisor: {
      nit: config.emisor.nit,
      nrc: config.emisor.nrc,
      nombre: config.emisor.nombre,
      codActividad: config.emisor.codActividad,
      descActividad: config.emisor.descActividad,
      nombreComercial: config.emisor.nombreComercial,
      direccion: _direccionCompleta(config.emisor.direccion),
      telefono: config.emisor.telefono,
      correo: config.emisor.correo,
      codEstable: config.emisor.codEstableInterno,
      codPuntoVenta: config.emisor.codPuntoVentaInterno,
      tipoItemExpor: emisorExport.tipoItemExpor,
      recintoFiscal: emisorExport.recintoFiscal,
      tipoRegimen: emisorExport.tipoRegimen,
      regimen: emisorExport.regimen,
    },
    receptor: {
      nombre: receptor.nombre,
      tipoDocumento: receptor.tipoDocumento,
      numDocumento: receptor.numDocumento,
      descActividad: receptor.descActividad,
      nombreComercial: receptor.nombreComercial ?? null,
      codPais: receptor.codPais,
      nombrePais: receptor.nombrePais,
      complemento: receptor.complemento,
      tipoPersona: receptor.tipoPersona,
      telefono: receptor.telefono ?? null,
      correo: receptor.correo ?? null,
    },
    otrosDocumentos: null,
    ventaTercero: null,
    compraTercero: null,
    cuerpoDocumento,
    resumen: {
      totalGravada,
      descuGravada: 0,
      porcentajeDescuento: 0,
      totalDescu: 0,
      seguro: resumenExtra.seguro ?? 0,
      flete: resumenExtra.flete ?? 0,
      tributos: null,
      montoTotalOperacion: totalGravada,
      totalNoGravado: 0,
      totalNoOnerosas: 0,
      totalPagar: totalGravada,
      totalLetras: null,
      saldoFavor: 0,
      condicionOperacion: CONDICION_OPERACION.CONTADO,
      pagos: null,
      codIncoterms: resumenExtra.codIncoterms ?? null,
      descIncoterms: resumenExtra.descIncoterms ?? null,
      numPagoElectronico: null,
      observaciones: null,
    },
    apendice: null,
  };

  return { dte, codigoGeneracion, numeroControl };
}

// ============================================================================
// FSE — Factura de Sujeto Excluido (tipoDte 14, schema fe-fse-v2.json, v2)
// ============================================================================
/**
 * Documenta compras hechas a alguien NO inscrito como contribuyente (sector
 * informal / persona natural sin negocio) — no hay IVA, solo posible
 * retención de renta. `items` = [{ descripcion, cantidad, precioUni, compra }]
 */
function construirFacturaSujetoExcluido({ receptor, items, reteRenta = 0 }) {
  if (!Array.isArray(items) || items.length === 0) throw new Error('Se requiere "items" con al menos 1 línea');
  const { identificacion, codigoGeneracion, numeroControl } = _construirIdentificacion({
    tipoDte: TIPO_DTE.FACTURA_SUJETO_EXCLUIDO,
    version: 2,
    incluirContingencia: true,
  });

  const cuerpoDocumento = items.map((item, idx) => ({
    numItem: idx + 1,
    tipoItem: item.tipoItem ?? 1,
    cantidad: item.cantidad,
    codigo: item.codigo ?? null,
    uniMedida: item.uniMedida ?? 59,
    descripcion: item.descripcion,
    precioUni: item.precioUni,
    montoDescu: item.montoDescu ?? 0,
    compra: item.compra,
  }));

  const totalCompra = Number(items.reduce((s, i) => s + i.compra, 0).toFixed(2));
  const totalPagar = Number((totalCompra - reteRenta).toFixed(2));

  const dte = {
    identificacion,
    emisor: {
      nit: config.emisor.nit,
      nrc: config.emisor.nrc,
      nombre: config.emisor.nombre,
      codActividad: config.emisor.codActividad,
      descActividad: config.emisor.descActividad,
      direccion: _direccionCompleta(config.emisor.direccion),
      telefono: config.emisor.telefono,
      codEstable: config.emisor.codEstableInterno,
      codPuntoVenta: config.emisor.codPuntoVentaInterno,
      correo: config.emisor.correo,
    },
    receptor: {
      tipoDocumento: receptor.tipoDocumento,
      numDocumento: receptor.numDocumento,
      nombre: receptor.nombre,
      codActividad: receptor.codActividad ?? null,
      descActividad: receptor.descActividad ?? null,
      direccion: _direccionCompleta(receptor.direccion),
      telefono: receptor.telefono ?? null,
      correo: receptor.correo ?? null,
    },
    cuerpoDocumento,
    resumen: {
      totalCompra,
      descu: 0,
      totalDescu: 0,
      subTotal: totalCompra,
      reteRenta,
      totalPagar,
      totalLetras: null,
      condicionOperacion: CONDICION_OPERACION.CONTADO,
      pagos: null,
      observaciones: null,
    },
    apendice: null,
  };

  return { dte, codigoGeneracion, numeroControl };
}

// ============================================================================
// CD — Comprobante de Donación (tipoDte 15, schema fe-cd-v2.json, v2)
// ============================================================================
/**
 * OJO: en este documento el "emisor" es la entidad que RECIBE la donación
 * (ej. una ONG) y el "receptor" es el DONANTE — confirmado por el schema.
 * `items` = [{ tipoDonacion (CAT-026: 1 Efectivo, 2 Bien, 3 Servicio),
 * cantidad, codigo?, uniMedida, descripcion, tipoDepreciacion, valorUni, valor }]
 */
function construirComprobanteDonacion({ donante, items, otrosDocumentos = [{ codDocAsociado: null, descDocumento: null, detalleDocumento: null }] }) {
  if (!Array.isArray(items) || items.length === 0) throw new Error('Se requiere "items" con al menos 1 línea');
  const { identificacion, codigoGeneracion, numeroControl } = _construirIdentificacion({
    tipoDte: TIPO_DTE.COMPROBANTE_DONACION,
    version: 2, // CD no lleva tipoContingencia/motivoContin ni fusion
  });

  const camposDonante = ['tipoDocumento', 'numDocumento', 'nombre', 'codActividad', 'descActividad', 'direccion', 'telefono', 'correo', 'codDomiciliado', 'codPais'];
  const faltantes = camposDonante.filter((c) => donante?.[c] === undefined);
  if (faltantes.length) {
    throw new Error(`"donante" incompleto: faltan ${faltantes.join(', ')}`);
  }

  const cuerpoDocumento = items.map((item, idx) => ({
    numItem: idx + 1,
    tipoDonacion: item.tipoDonacion,
    cantidad: item.cantidad,
    codigo: item.codigo ?? null,
    uniMedida: item.uniMedida,
    descripcion: item.descripcion,
    tipoDepreciacion: item.tipoDepreciacion ?? 0,
    valorUni: item.valorUni,
    valor: item.valor,
  }));

  const valorTotal = Number(items.reduce((s, i) => s + i.valor, 0).toFixed(2));

  const dte = {
    identificacion,
    receptor: {
      tipoDocumento: donante.tipoDocumento,
      numDocumento: donante.numDocumento,
      nrc: donante.nrc ?? null,
      nombre: donante.nombre,
      codActividad: donante.codActividad,
      descActividad: donante.descActividad,
      direccion: _direccionCompleta(donante.direccion),
      telefono: donante.telefono,
      correo: donante.correo,
      codDomiciliado: donante.codDomiciliado,
      codPais: donante.codPais,
    },
    emisor: {
      tipoDocumento: config.emisor.tipoDocumentoOrganizacion ?? '36',
      numDocumento: config.emisor.nit,
      nrc: config.emisor.nrc,
      nombre: config.emisor.nombre,
      codActividad: config.emisor.codActividad,
      descActividad: config.emisor.descActividad,
      nombreComercial: config.emisor.nombreComercial,
      direccion: _direccionCompleta(config.emisor.direccion),
      telefono: config.emisor.telefono,
      correo: config.emisor.correo,
      codEstable: config.emisor.codEstableInterno,
      codPuntoVenta: config.emisor.codPuntoVentaInterno,
    },
    cuerpoDocumento,
    resumen: {
      valorTotal,
      totalLetras: null,
      pagos: null,
    },
    otrosDocumentos,
    apendice: null,
  };

  return { dte, codigoGeneracion, numeroControl };
}

module.exports = {
  construirComprobanteRetencion,
  construirComprobanteLiquidacion,
  construirDocumentoContableLiquidacion,
  construirFacturaExportacion,
  construirFacturaSujetoExcluido,
  construirComprobanteDonacion,
};
