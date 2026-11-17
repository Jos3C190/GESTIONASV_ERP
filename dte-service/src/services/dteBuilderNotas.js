const { generarCodigoGeneracion } = require('../utils/codigoGeneracion');
const { generarNumeroControl } = require('../utils/numeroControl');
const { fechaHoraSV } = require('../utils/fechaHoraSV');
const { numeroALetras } = require('../utils/numeroALetras');
const {
  calcularVentasPorCategoria,
  aplicarDescuentoGlobal,
  validarLineas,
  prorratearCentavos,
  r2,
  HOLGURA,
} = require('./calculoFiscal');
const {
  errorDeSolicitud,
  _construirIdentificacion: _construirIdentificacionV2,
  _construirEmisor,
  TASA_IVA,
  TRIBUTO_IVA,
} = require('./dteBuilder');
const { validateIssuerV2 } = require('./issuerContractV2');
const { TIPO_DTE, MODELO_FACTURACION, TIPO_TRANSMISION, CONDICION_OPERACION, TIPO_DOCUMENTO_IDENTIFICACION } = require('../config/catalogs');
const config = require('../config');

function _construirIdentificacion({ tipoDte, version, incluirFusion = false }) {
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
    tipoContingencia: null,
    motivoContin: null,
    fecEmi: fecha,
    horEmi: hora,
    tipoMoneda: 'USD',
  };
  // NC, ND y CL exigen además el campo "fusion" (nullable) dentro de identificacion.
  if (incluirFusion) identificacion.fusion = null;

  return { identificacion, codigoGeneracion, numeroControl };
}

function _construirEmisorCompleto(extra = {}) {
  return {
    nit: config.emisor.nit,
    nrc: config.emisor.nrc,
    nombre: config.emisor.nombre,
    codActividad: config.emisor.codActividad,
    descActividad: config.emisor.descActividad,
    nombreComercial: config.emisor.nombreComercial,
    direccion: {
      departamento: config.emisor.direccion.departamento,
      municipio: config.emisor.direccion.municipio,
      distrito: config.emisor.direccion.distrito,
      complemento: config.emisor.direccion.complemento,
    },
    telefono: config.emisor.telefono,
    correo: config.emisor.correo,
    ...extra,
  };
}

/** Variante con codEstable/codPuntoVenta, para los tipos de DTE cuyo schema sí los define (NR, CR, CL, FEX, FSE, CD, DCL). */
function _construirEmisorConEstablecimiento(extra = {}) {
  return _construirEmisorCompleto({
    codEstable: config.emisor.codEstableInterno,
    codPuntoVenta: config.emisor.codPuntoVentaInterno,
    ...extra,
  });
}

/**
 * Receptor "contribuyente completo" — usado por NC, ND (siempre requieren
 * NRC porque corrigen un CCF previo entre contribuyentes).
 */
function _construirReceptorContribuyente(receptor) {
  const camposFaltantes = ['tipoDocumento', 'numDocumento', 'nombre', 'codActividad', 'descActividad', 'direccion', 'telefono', 'correo'].filter(
    (campo) => receptor?.[campo] === undefined
  );
  if (camposFaltantes.length) {
    throw new Error(`receptor incompleto: faltan los campos ${camposFaltantes.join(', ')}`);
  }
  return {
    tipoDocumento: receptor.tipoDocumento,
    numDocumento: receptor.numDocumento,
    nrc: receptor.nrc ?? null,
    nombre: receptor.nombre,
    codActividad: receptor.codActividad,
    descActividad: receptor.descActividad,
    nombreComercial: receptor.nombreComercial ?? null,
    direccion: receptor.direccion,
    telefono: receptor.telefono,
    correo: receptor.correo,
  };
}

/**
 * Documento Relacionado: SIEMPRE requerido (no nullable) en NC y ND porque
 * corrigen un DTE previo. `relacionado` = { tipoDocumento (CAT-002 del doc
 * original, ej "03" para CCF), tipoGeneracion (1=físico, 2=electrónico),
 * numeroDocumento (numeroControl o número físico del original), fechaEmision }
 */
function _construirDocumentoRelacionado(relacionado) {
  if (!relacionado) {
    throw new Error(
      'Se requiere "documentoRelacionado" (el CCF/DTE que esta Nota corrige): { tipoDocumento, tipoGeneracion, numeroDocumento, fechaEmision }'
    );
  }
  return [relacionado];
}

const MAX_DOCUMENTOS_RELACIONADOS = 50;
// CAT-007, tipo de generación del documento relacionado.
const TIPO_GENERACION = Object.freeze({ FISICO: 1, ELECTRONICO: 2 });
const CODIGO_GENERACION_REGEX = /^[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}$/;
const NIT_REGEX = /^(\d{9}|\d{14})$/;
const NRC_REGEX = /^\d{2,8}$/;
const CORREO_REGEX = /^[^\s@]+@[^\s@]+$/;
const FECHA_REGEX = /^\d{4}-\d{2}-\d{2}$/;
const MAX_OBSERVACIONES = 3000;

function _textoNoVacio(valor) {
  return typeof valor === 'string' && valor.trim().length > 0;
}

function _esFechaCalendario(valor) {
  if (typeof valor !== 'string' || !FECHA_REGEX.test(valor)) return false;
  const fecha = new Date(`${valor}T00:00:00Z`);
  return Number.isFinite(fecha.getTime()) && fecha.toISOString().slice(0, 10) === valor;
}

/**
 * Documentos relacionados de la NC (Normativa, anexo IV, campos 14 a 17):
 * de 1 a 50, todos CCF (03). Un CCF electrónico (tipoGeneracion 2) se
 * relaciona por su código de generación; uno físico (1), por su correlativo.
 * La fecha es la de emisión del CCF, que Hacienda contrasta con el original.
 */
function _validarDocumentosRelacionados(documentosRelacionados, fechaNota) {
  if (!Array.isArray(documentosRelacionados) || documentosRelacionados.length === 0) {
    throw errorDeSolicitud('Se requiere "documentosRelacionados" con al menos 1 CCF que la Nota de Crédito ajusta');
  }
  if (documentosRelacionados.length > MAX_DOCUMENTOS_RELACIONADOS) {
    throw errorDeSolicitud(`Una Nota de Crédito relaciona como máximo ${MAX_DOCUMENTOS_RELACIONADOS} documentos`);
  }
  const vistos = new Set();
  return documentosRelacionados.map((documento, indice) => {
    const posicion = indice + 1;
    if (documento?.tipoDocumento !== TIPO_DTE.COMPROBANTE_CREDITO_FISCAL) {
      throw errorDeSolicitud(`Documento relacionado ${posicion}: la Nota de Crédito solo ajusta Comprobantes de Crédito Fiscal (tipoDocumento "03")`);
    }
    const tipoGeneracion = Number(documento.tipoGeneracion);
    let numeroDocumento;
    if (tipoGeneracion === TIPO_GENERACION.ELECTRONICO) {
      numeroDocumento = typeof documento.numeroDocumento === 'string' ? documento.numeroDocumento.trim().toUpperCase() : '';
      if (!CODIGO_GENERACION_REGEX.test(numeroDocumento)) {
        throw errorDeSolicitud(`Documento relacionado ${posicion}: un CCF electrónico se relaciona por su código de generación (36 caracteres)`);
      }
    } else if (tipoGeneracion === TIPO_GENERACION.FISICO) {
      numeroDocumento = typeof documento.numeroDocumento === 'string' ? documento.numeroDocumento.trim() : '';
      if (!numeroDocumento || numeroDocumento.length > 36) {
        throw errorDeSolicitud(`Documento relacionado ${posicion}: un CCF físico se relaciona por su correlativo (1 a 36 caracteres)`);
      }
    } else {
      throw errorDeSolicitud(`Documento relacionado ${posicion}: tipoGeneracion debe ser 1 (físico) o 2 (electrónico)`);
    }
    if (!_esFechaCalendario(documento.fechaEmision)) {
      throw errorDeSolicitud(`Documento relacionado ${posicion}: fechaEmision debe ser una fecha AAAA-MM-DD`);
    }
    if (documento.fechaEmision > fechaNota) {
      throw errorDeSolicitud(`Documento relacionado ${posicion}: la fecha del CCF (${documento.fechaEmision}) es posterior a la de la Nota de Crédito (${fechaNota})`);
    }
    if (vistos.has(numeroDocumento)) {
      throw errorDeSolicitud(`Documento relacionado ${posicion}: el documento ${numeroDocumento} está repetido`);
    }
    vistos.add(numeroDocumento);
    return {
      tipoDocumento: TIPO_DTE.COMPROBANTE_CREDITO_FISCAL,
      tipoGeneracion,
      numeroDocumento,
      fechaEmision: documento.fechaEmision,
    };
  });
}

/**
 * Receptor de la NC: el mismo contribuyente del CCF, identificado con NIT
 * (tipoDocumento 36). fe-nc-v4.json exige además NRC, actividad y dirección;
 * teléfono y correo admiten null, como en el CCF.
 */
function _contactoOpcional(valor, campo, { min, max, patron = null, formato = '' }) {
  if (valor === undefined || valor === null) return null;
  if (typeof valor !== 'string') throw errorDeSolicitud(`${campo} del receptor debe ser texto o null`);
  const texto = valor.trim();
  if (!texto) return null;
  if (texto.length < min || texto.length > max || (patron && !patron.test(texto))) {
    throw errorDeSolicitud(`${campo} del receptor debe tener de ${min} a ${max} caracteres${formato}`);
  }
  return texto;
}

function _validarReceptorNotaCredito(receptor) {
  if (!receptor || typeof receptor !== 'object') {
    throw errorDeSolicitud('Una Nota de Crédito requiere el receptor del CCF que ajusta');
  }
  if (receptor.tipoDocumento !== TIPO_DOCUMENTO_IDENTIFICACION.NIT || !NIT_REGEX.test(String(receptor.numDocumento ?? ''))) {
    throw errorDeSolicitud('El receptor de la Nota de Crédito se identifica con NIT: tipoDocumento "36" y numDocumento de 9 o 14 dígitos');
  }
  if (!NRC_REGEX.test(String(receptor.nrc ?? ''))) {
    throw errorDeSolicitud('El receptor de la Nota de Crédito requiere NRC (2 a 8 dígitos)');
  }
  const faltantes = ['nombre', 'codActividad', 'descActividad'].filter((campo) => !_textoNoVacio(receptor[campo]));
  const direccion = receptor.direccion;
  if (!direccion || ['departamento', 'municipio', 'distrito', 'complemento'].some((campo) => !_textoNoVacio(direccion[campo]))) {
    faltantes.push('direccion');
  }
  if (faltantes.length) {
    throw errorDeSolicitud(`Receptor de la Nota de Crédito incompleto: faltan ${faltantes.join(', ')}`);
  }
  const telefono = _contactoOpcional(receptor.telefono, 'telefono', { min: 8, max: 30 });
  const correo = _contactoOpcional(receptor.correo, 'correo', { min: 3, max: 100, patron: CORREO_REGEX, formato: ' y formato usuario@dominio' });
  return {
    tipoDocumento: receptor.tipoDocumento,
    numDocumento: String(receptor.numDocumento),
    nrc: String(receptor.nrc),
    nombre: receptor.nombre,
    codActividad: receptor.codActividad,
    descActividad: receptor.descActividad,
    nombreComercial: _textoNoVacio(receptor.nombreComercial) ? receptor.nombreComercial : null,
    direccion: {
      departamento: direccion.departamento,
      municipio: direccion.municipio,
      distrito: direccion.distrito,
      complemento: direccion.complemento,
    },
    telefono,
    correo,
  };
}

/**
 * IVA de la NC por línea y total, con la regla de holgura del CCF
 * (`_ivaCCF` en dteBuilder.js): el IVA informado por línea (`ivaItem`, el que
 * se acreditó del CCF) se respeta si su suma queda a ±0.01 del 13 % de la
 * base gravada. Sin IVA por línea, el 13 % de la base se reparte entre las
 * líneas gravadas en centavos exactos, para que Σ totalIva = total.
 */
function _ivaNotaCredito(lineas, baseGravada) {
  const esperado = r2(baseGravada * TASA_IVA);
  const esGravada = (item) => (item.ventaGravada ?? 0) > 0;
  const gravadas = lineas.filter(esGravada);
  const conIva = gravadas.filter((item) => item.ivaItem !== undefined && item.ivaItem !== null);

  if (conIva.length === 0) {
    const centavos = prorratearCentavos(Math.round(esperado * 100), lineas.map((item) => (esGravada(item) ? Math.round(item.ventaGravada * 100) : 0)));
    return { porLinea: centavos.map((valor) => valor / 100), total: esperado };
  }
  if (conIva.length !== gravadas.length) {
    throw errorDeSolicitud('El IVA de la Nota de Crédito debe informarse en todas las líneas gravadas o en ninguna');
  }
  if (conIva.some((item) => typeof item.ivaItem !== 'number' || !Number.isFinite(item.ivaItem) || item.ivaItem < 0)) {
    throw errorDeSolicitud('El IVA por línea de la Nota de Crédito debe ser un importe no negativo');
  }
  const porLinea = lineas.map((item) => (esGravada(item) ? r2(item.ivaItem) : 0));
  const total = r2(porLinea.reduce((suma, valor) => suma + valor, 0));
  if (Math.abs(total - esperado) > HOLGURA + 1e-9) {
    throw errorDeSolicitud(`El IVA informado (${total.toFixed(2)}) difiere del 13 % de la base gravada (${esperado.toFixed(2)}) en más de 0.01`);
  }
  return { porLinea, total };
}

function _normalizarObservaciones(observaciones) {
  if (observaciones === undefined || observaciones === null) return null;
  if (typeof observaciones !== 'string') throw errorDeSolicitud('observaciones debe ser texto');
  const texto = observaciones.trim();
  if (texto.length > MAX_OBSERVACIONES) throw errorDeSolicitud(`observaciones excede ${MAX_OBSERVACIONES} caracteres`);
  return texto || null;
}

/**
 * Nota de Crédito Electrónica (tipoDte 05), schema oficial fe-nc-v4.json
 * (version 4). Ajusta uno o varios CCF (03) del mismo receptor: devolución,
 * rebaja o corrección de precio.
 *
 * Contrato de líneas (SIN IVA, como el CCF): `precioUni`, `montoDescu` y
 * ventas netas acreditadas que cumplen cantidad × precioUni − montoDescu =
 * venta; `ivaItem` opcional con el IVA que se acredita en la línea, y
 * `numeroDocumento` con el documento relacionado que la línea ajusta.
 *
 * Resumen (sin descuentos globales, que el esquema no tiene):
 *   tributo 20 = totalIva = Σ totalIva por línea (holgura ±0.01)
 *   montoTotalOperacion = subTotalVentas + IVA
 *   totalPagar = montoTotalOperacion + totalNoGravado
 *
 * Toda validación ocurre antes de reservar el número de control. El plazo de
 * 3 meses y el saldo del CCF los controla el backend, que conoce los CCF.
 */
function construirNotaCredito({ emisor = null, receptor, items, documentosRelacionados, observaciones = null }, { contingencia = null } = {}) {
  const issuer = emisor ? validateIssuerV2(emisor) : config.emisor;
  const relacionados = _validarDocumentosRelacionados(documentosRelacionados, fechaHoraSV().fecha);
  const receptorNormalizado = _validarReceptorNotaCredito(receptor);
  if (!Array.isArray(items) || items.length === 0) throw errorDeSolicitud('Se requiere "items" con al menos 1 línea');
  validarLineas(items);

  const numerosRelacionados = new Map(relacionados.map((documento) => [documento.numeroDocumento.toUpperCase(), documento.numeroDocumento]));
  const documentoDeLinea = items.map((item, indice) => {
    const numero = typeof item.numeroDocumento === 'string' ? numerosRelacionados.get(item.numeroDocumento.trim().toUpperCase()) : undefined;
    if (!numero) {
      throw errorDeSolicitud(`Línea ${indice + 1}: numeroDocumento debe ser uno de los documentos relacionados de la Nota de Crédito`);
    }
    return numero;
  });
  const sinLineas = relacionados.find((documento) => !documentoDeLinea.includes(documento.numeroDocumento));
  if (sinLineas) {
    throw errorDeSolicitud(`El documento relacionado ${sinLineas.numeroDocumento} no tiene líneas en la Nota de Crédito`);
  }

  const totales = calcularVentasPorCategoria(items);
  const subTotalVentas = r2(totales.totalGravada + totales.totalExenta + totales.totalNoSuj);
  const iva = _ivaNotaCredito(items, totales.totalGravada);
  const montoTotalOperacion = r2(subTotalVentas + iva.total);
  const totalPagar = r2(montoTotalOperacion + totales.totalNoGravado);
  if (totalPagar < 0) throw errorDeSolicitud('El total de la Nota de Crédito no puede ser negativo');
  const observacionesNormalizadas = _normalizarObservaciones(observaciones);

  const cuerpoDocumento = items.map((item, indice) => ({
    numItem: indice + 1,
    tipoItem: item.tipoItem ?? 1, // CAT-011: 1=Bienes, 2=Servicios
    numeroDocumento: documentoDeLinea[indice],
    cantidad: item.cantidad,
    codigo: item.codigo ?? null,
    codTributo: item.codTributo ?? null,
    uniMedida: item.uniMedida ?? 59, // CAT-014: 59 = Unidad
    descripcion: item.descripcion,
    precioUni: item.precioUni,
    montoDescu: item.montoDescu ?? 0,
    ventaNoSuj: item.ventaNoSuj ?? 0,
    ventaExenta: item.ventaExenta ?? 0,
    ventaGravada: item.ventaGravada ?? 0,
    tributos: (item.ventaGravada ?? 0) > 0 ? [TRIBUTO_IVA.codigo] : null,
    noGravado: item.noGravado ?? 0,
    ivaPerci: 0,
    totalIva: iva.porLinea[indice],
    ivaRete: 0,
  }));

  const resumen = {
    totalNoSuj: totales.totalNoSuj,
    totalExenta: totales.totalExenta,
    totalGravada: totales.totalGravada,
    subTotalVentas,
    totalDescu: totales.totalDescu,
    tributos: totales.totalGravada > 0 ? [{ ...TRIBUTO_IVA, valor: iva.total }] : null,
    montoTotalOperacion,
    ivaPerci: 0,
    totalIva: iva.total,
    ivaRete: 0,
    totalNoGravado: totales.totalNoGravado,
    totalPagar,
    totalLetras: numeroALetras(totalPagar),
    condicionOperacion: CONDICION_OPERACION.CONTADO,
    observaciones: observacionesNormalizadas,
    codigoRetencionMH: null,
  };

  const { identificacion, codigoGeneracion, numeroControl } = _construirIdentificacionV2({
    tipoDte: TIPO_DTE.NOTA_CREDITO,
    version: 4,
    issuer,
    contingencia,
  });
  // fe-nc-v4.json exige "fusion" y no admite codEstable/codPuntoVenta en el
  // emisor; el número de control sí lleva los códigos MH del emisor.
  identificacion.fusion = null;
  const emisorNota = _construirEmisor(issuer);
  delete emisorNota.codEstable;
  delete emisorNota.codPuntoVenta;

  const dte = {
    identificacion,
    documentoRelacionado: relacionados,
    emisor: emisorNota,
    receptor: receptorNormalizado,
    ventaTercero: null,
    cuerpoDocumento,
    resumen,
    apendice: null,
  };

  return { dte, codigoGeneracion, numeroControl };
}

/**
 * Nota de Débito Electrónica (tipoDte 06, schema fe-nd-v4.json).
 * Estructuralmente casi idéntica a la Nota de Crédito (agrega cargos en vez
 * de restarlos), pero el schema exige "numPagoElectronico" en el resumen.
 */
function construirNotaDebito({ receptor, items, relacionado, descuentoGlobal = null }) {
  if (!Array.isArray(items) || items.length === 0) throw new Error('Se requiere "items" con al menos 1 línea');
  items = aplicarDescuentoGlobal(items, descuentoGlobal);
  const { identificacion, codigoGeneracion, numeroControl } = _construirIdentificacion({
    tipoDte: TIPO_DTE.NOTA_DEBITO,
    version: 4,
    incluirFusion: true,
  });

  const cuerpoDocumento = items.map((item, idx) => {
    const ivaLinea = Number((item.ventaGravada * 0.13).toFixed(2));
    return {
      numItem: idx + 1,
      tipoItem: item.tipoItem ?? 1,
      numeroDocumento: relacionado?.numeroDocumento ?? null,
      codigo: item.codigo ?? null,
      codTributo: item.codTributo ?? null,
      descripcion: item.descripcion,
      cantidad: item.cantidad,
      uniMedida: item.uniMedida ?? 59,
      precioUni: item.precioUni,
      montoDescu: item.montoDescu ?? 0,
      ventaNoSuj: item.ventaNoSuj ?? 0,
      ventaExenta: item.ventaExenta ?? 0,
      ventaGravada: item.ventaGravada,
      tributos: item.ventaGravada > 0 ? ['20'] : null,
      noGravado: item.noGravado ?? 0,
      ivaPerci: 0,
      totalIva: ivaLinea,
      ivaRete: 0,
    };
  });

  const { totalGravada, totalExenta, totalNoSuj, totalDescu } = calcularVentasPorCategoria(items);
  const subTotalVentas = Number((totalGravada + totalExenta + totalNoSuj).toFixed(2));
  // IMPORTANTE: se deriva de la SUMA de los totalIva por línea (ya
  // redondeados arriba), no de totalGravada*0.13 por separado — evita el
  // desfase de redondeo (ver nota equivalente en dteBuilder.js).
  const totalIva = Number(cuerpoDocumento.reduce((s, i) => s + i.totalIva, 0).toFixed(2));
  const totalPagar = Number((subTotalVentas + totalIva).toFixed(2));

  const resumen = {
    totalNoSuj,
    totalExenta,
    totalGravada,
    subTotalVentas,
    totalDescu,
    tributos: [{ codigo: '20', descripcion: 'Impuesto al Valor Agregado 13%', valor: totalIva }],
    ivaPerci: 0,
    totalIva,
    ivaRete: 0,
    montoTotalOperacion: totalPagar,
    totalNoGravado: 0,
    totalPagar,
    totalLetras: null,
    condicionOperacion: CONDICION_OPERACION.CONTADO,
    numPagoElectronico: null,
    observaciones: null,
    codigoRetencionMH: null,
  };

  const dte = {
    identificacion,
    documentoRelacionado: _construirDocumentoRelacionado(relacionado),
    emisor: _construirEmisorCompleto(),
    receptor: _construirReceptorContribuyente(receptor),
    ventaTercero: null,
    cuerpoDocumento,
    resumen,
    apendice: null,
  };

  return { dte, codigoGeneracion, numeroControl };
}

/**
 * Nota de Remisión Electrónica (tipoDte 04, schema fe-nr-v4.json).
 * Documenta el TRASLADO de bienes (no siempre implica venta) — por eso el
 * receptor exige "bienTitulo" (CAT-025: depósito/propiedad/consignación/
 * traslado/otros) y el emisor exige codEstable/codPuntoVenta no-nulos.
 * documentoRelacionado es OPCIONAL aquí (a diferencia de NC/ND).
 */
function construirNotaRemision({ receptor, items, bienTitulo, relacionado = null }) {
  if (!Array.isArray(items) || items.length === 0) throw new Error('Se requiere "items" con al menos 1 línea');
  const { identificacion, codigoGeneracion, numeroControl } = _construirIdentificacion({
    tipoDte: TIPO_DTE.NOTA_REMISION,
    version: 4,
  });

  if (!bienTitulo) {
    throw new Error('Se requiere "bienTitulo" (CAT-025): 01 Depósito, 02 Propiedad, 03 Consignación, 04 Traslado, 05 Otros');
  }
  // El schema oficial exige bienTitulo como STRING (ej. "04"), no número.
  const bienTituloStr = String(bienTitulo).padStart(2, '0');

  const camposFaltantes = ['tipoDocumento', 'numDocumento', 'nombre', 'codActividad', 'descActividad', 'direccion', 'telefono', 'correo'].filter(
    (campo) => receptor?.[campo] === undefined
  );
  if (camposFaltantes.length) {
    throw new Error(`receptor incompleto: faltan los campos ${camposFaltantes.join(', ')}`);
  }

  const cuerpoDocumento = items.map((item, idx) => ({
    numItem: idx + 1,
    tipoItem: item.tipoItem ?? 1,
    numeroDocumento: relacionado?.numeroDocumento ?? null,
    codigo: item.codigo ?? null,
    codTributo: item.codTributo ?? null,
    descripcion: item.descripcion,
    cantidad: item.cantidad,
    uniMedida: item.uniMedida ?? 59,
    precioUni: item.precioUni,
    montoDescu: item.montoDescu ?? 0,
    ventaNoSuj: item.ventaNoSuj ?? 0,
    ventaExenta: item.ventaExenta ?? 0,
    ventaGravada: item.ventaGravada,
    tributos: item.ventaGravada > 0 ? ['20'] : null,
  }));

  const totalGravada = Number(items.reduce((s, i) => s + i.ventaGravada, 0).toFixed(2));

  const resumen = {
    totalNoSuj: 0,
    totalExenta: 0,
    totalGravada,
    subTotalVentas: totalGravada,
    descuNoSuj: 0,
    descuExenta: 0,
    descuGravada: 0,
    porcentajeDescuento: 0,
    totalDescu: 0,
    tributos: totalGravada > 0 ? [{ codigo: '20', descripcion: 'Impuesto al Valor Agregado 13%', valor: Number((totalGravada * 0.13).toFixed(2)) }] : null,
    subTotal: totalGravada,
    montoTotalOperacion: totalGravada,
    totalLetras: null,
    observaciones: null,
  };

  const dte = {
    identificacion,
    documentoRelacionado: relacionado ? [relacionado] : null,
    emisor: _construirEmisorConEstablecimiento(),
    receptor: {
      tipoDocumento: receptor.tipoDocumento,
      numDocumento: receptor.numDocumento,
      nrc: receptor.nrc ?? null,
      nombre: receptor.nombre,
      codActividad: receptor.codActividad,
      descActividad: receptor.descActividad,
      nombreComercial: receptor.nombreComercial ?? null,
      direccion: receptor.direccion,
      telefono: receptor.telefono,
      correo: receptor.correo,
      bienTitulo: bienTituloStr,
    },
    ventaTercero: null,
    cuerpoDocumento,
    resumen,
    apendice: null,
  };

  return { dte, codigoGeneracion, numeroControl };
}

module.exports = { construirNotaCredito, construirNotaDebito, construirNotaRemision };
