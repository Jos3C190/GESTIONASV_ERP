const { generarCodigoGeneracion } = require('../utils/codigoGeneracion');
const { generarNumeroControl } = require('../utils/numeroControl');
const { fechaHoraSV } = require('../utils/fechaHoraSV');
const { numeroALetras } = require('../utils/numeroALetras');
const {
  calcularVentasPorCategoria,
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
function _validarDocumentosRelacionados(documentosRelacionados, fechaNota, nombre = 'Nota de Crédito') {
  if (!Array.isArray(documentosRelacionados) || documentosRelacionados.length === 0) {
    throw errorDeSolicitud(`Se requiere "documentosRelacionados" con al menos 1 CCF que la ${nombre} ajusta`);
  }
  if (documentosRelacionados.length > MAX_DOCUMENTOS_RELACIONADOS) {
    throw errorDeSolicitud(`Una ${nombre} relaciona como máximo ${MAX_DOCUMENTOS_RELACIONADOS} documentos`);
  }
  const vistos = new Set();
  return documentosRelacionados.map((documento, indice) => {
    const posicion = indice + 1;
    if (documento?.tipoDocumento !== TIPO_DTE.COMPROBANTE_CREDITO_FISCAL) {
      throw errorDeSolicitud(`Documento relacionado ${posicion}: la ${nombre} solo ajusta Comprobantes de Crédito Fiscal (tipoDocumento "03")`);
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
      throw errorDeSolicitud(`Documento relacionado ${posicion}: la fecha del CCF (${documento.fechaEmision}) es posterior a la de la ${nombre} (${fechaNota})`);
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

function _validarReceptorNota(receptor, nombre = 'Nota de Crédito') {
  if (!receptor || typeof receptor !== 'object') {
    throw errorDeSolicitud(`Una ${nombre} requiere el receptor del CCF que ajusta`);
  }
  if (receptor.tipoDocumento !== TIPO_DOCUMENTO_IDENTIFICACION.NIT || !NIT_REGEX.test(String(receptor.numDocumento ?? ''))) {
    throw errorDeSolicitud(`El receptor de la ${nombre} se identifica con NIT: tipoDocumento "36" y numDocumento de 9 o 14 dígitos`);
  }
  if (!NRC_REGEX.test(String(receptor.nrc ?? ''))) {
    throw errorDeSolicitud(`El receptor de la ${nombre} requiere NRC (2 a 8 dígitos)`);
  }
  const faltantes = ['nombre', 'codActividad', 'descActividad'].filter((campo) => !_textoNoVacio(receptor[campo]));
  const direccion = receptor.direccion;
  if (!direccion || ['departamento', 'municipio', 'distrito', 'complemento'].some((campo) => !_textoNoVacio(direccion[campo]))) {
    faltantes.push('direccion');
  }
  if (faltantes.length) {
    throw errorDeSolicitud(`Receptor de la ${nombre} incompleto: faltan ${faltantes.join(', ')}`);
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
function _ivaNota(lineas, baseGravada, nombre = 'Nota de Crédito') {
  const esperado = r2(baseGravada * TASA_IVA);
  const esGravada = (item) => (item.ventaGravada ?? 0) > 0;
  const gravadas = lineas.filter(esGravada);
  const conIva = gravadas.filter((item) => item.ivaItem !== undefined && item.ivaItem !== null);

  if (conIva.length === 0) {
    const centavos = prorratearCentavos(Math.round(esperado * 100), lineas.map((item) => (esGravada(item) ? Math.round(item.ventaGravada * 100) : 0)));
    return { porLinea: centavos.map((valor) => valor / 100), total: esperado };
  }
  if (conIva.length !== gravadas.length) {
    throw errorDeSolicitud(`El IVA de la ${nombre} debe informarse en todas las líneas gravadas o en ninguna`);
  }
  if (conIva.some((item) => typeof item.ivaItem !== 'number' || !Number.isFinite(item.ivaItem) || item.ivaItem < 0)) {
    throw errorDeSolicitud(`El IVA por línea de la ${nombre} debe ser un importe no negativo`);
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

// Retención y percepción de las notas: la misma tasa del CCF (1 %, CT arts.
// 162 y 163) sobre el gravado de la nota, sin el umbral de $100, porque la
// nota ajusta una operación que ya lo cumplió (Manual Funcional V2.0,
// ejemplo «Ajuste con NCE a CCFE con Descuento Global y Retención»).
const TASA_RETENCION_NOTA = 0.01;

function _normalizarAjustesNota(ajustes) {
  if (ajustes === undefined || ajustes === null) return { retencion: false, percepcion: false };
  if (typeof ajustes !== 'object') throw errorDeSolicitud('"ajustes" debe ser un objeto');
  for (const campo of ['retencionIva', 'percepcionIva']) {
    if (ajustes[campo] !== undefined && typeof ajustes[campo] !== 'boolean') {
      throw errorDeSolicitud(`ajustes.${campo} debe ser true o false`);
    }
  }
  return { retencion: ajustes.retencionIva === true, percepcion: ajustes.percepcionIva === true };
}

/** 1 % del gravado de la nota, repartido entre las líneas gravadas en centavos exactos. */
function _unoPorCiento(lineas, baseGravada, aplica) {
  if (!aplica) return { porLinea: lineas.map(() => 0), total: 0 };
  const total = r2(baseGravada * TASA_RETENCION_NOTA);
  const centavos = prorratearCentavos(Math.round(total * 100), lineas.map((item) => Math.round(Math.max(0, item.ventaGravada ?? 0) * 100)));
  return { porLinea: centavos.map((valor) => valor / 100), total };
}

const NOTAS = Object.freeze({
  [TIPO_DTE.NOTA_CREDITO]: { nombre: 'Nota de Crédito', extraResumen: {} },
  [TIPO_DTE.NOTA_DEBITO]: { nombre: 'Nota de Débito', extraResumen: { numPagoElectronico: null } },
});

/**
 * Nota de Crédito (05, fe-nc-v4.json) o de Débito (06, fe-nd-v4.json),
 * versión 4. Ajusta uno o varios CCF (03) del mismo receptor: la NC por
 * devolución, rebaja o corrección de precio; la ND por cargos que aumentan
 * el valor y el impuesto del CCF (CT art. 110).
 *
 * Contrato de líneas (SIN IVA, como el CCF): `precioUni`, `montoDescu` y
 * ventas netas que cumplen cantidad × precioUni − montoDescu = venta;
 * `ivaItem` opcional con el IVA de la línea, y `numeroDocumento` con el
 * documento relacionado que la línea ajusta.
 *
 * `ajustes` = { retencionIva, percepcionIva }: si el CCF retuvo o percibió,
 * la nota repite la regla con el 1 % de su gravado, por línea y en el resumen.
 *
 * Resumen (sin descuentos globales, que el esquema no tiene):
 *   tributo 20 = totalIva = Σ totalIva por línea (holgura ±0.01)
 *   montoTotalOperacion = subTotalVentas + IVA
 *   totalPagar = montoTotalOperacion + ivaPerci − ivaRete + totalNoGravado
 *
 * Toda validación ocurre antes de reservar el número de control. El plazo y
 * el saldo del CCF los controla el backend, que conoce los CCF.
 */
function _construirNota(tipoDte, { emisor = null, receptor, items, documentosRelacionados, observaciones = null, ajustes = null }, { contingencia = null } = {}) {
  const { nombre, extraResumen } = NOTAS[tipoDte];
  const issuer = emisor ? validateIssuerV2(emisor) : config.emisor;
  const relacionados = _validarDocumentosRelacionados(documentosRelacionados, fechaHoraSV().fecha, nombre);
  const receptorNormalizado = _validarReceptorNota(receptor, nombre);
  const ajustesNota = _normalizarAjustesNota(ajustes);
  if (!Array.isArray(items) || items.length === 0) throw errorDeSolicitud('Se requiere "items" con al menos 1 línea');
  validarLineas(items);

  const numerosRelacionados = new Map(relacionados.map((documento) => [documento.numeroDocumento.toUpperCase(), documento.numeroDocumento]));
  const documentoDeLinea = items.map((item, indice) => {
    const numero = typeof item.numeroDocumento === 'string' ? numerosRelacionados.get(item.numeroDocumento.trim().toUpperCase()) : undefined;
    if (!numero) {
      throw errorDeSolicitud(`Línea ${indice + 1}: numeroDocumento debe ser uno de los documentos relacionados de la ${nombre}`);
    }
    return numero;
  });
  const sinLineas = relacionados.find((documento) => !documentoDeLinea.includes(documento.numeroDocumento));
  if (sinLineas) {
    throw errorDeSolicitud(`El documento relacionado ${sinLineas.numeroDocumento} no tiene líneas en la ${nombre}`);
  }

  const totales = calcularVentasPorCategoria(items);
  const subTotalVentas = r2(totales.totalGravada + totales.totalExenta + totales.totalNoSuj);
  const iva = _ivaNota(items, totales.totalGravada, nombre);
  const retencion = _unoPorCiento(items, totales.totalGravada, ajustesNota.retencion);
  const percepcion = _unoPorCiento(items, totales.totalGravada, ajustesNota.percepcion);
  const montoTotalOperacion = r2(subTotalVentas + iva.total);
  const totalPagar = r2(montoTotalOperacion + percepcion.total - retencion.total + totales.totalNoGravado);
  if (totalPagar < 0) throw errorDeSolicitud(`El total de la ${nombre} no puede ser negativo`);
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
    ivaPerci: percepcion.porLinea[indice],
    totalIva: iva.porLinea[indice],
    ivaRete: retencion.porLinea[indice],
  }));

  const resumen = {
    totalNoSuj: totales.totalNoSuj,
    totalExenta: totales.totalExenta,
    totalGravada: totales.totalGravada,
    subTotalVentas,
    totalDescu: totales.totalDescu,
    tributos: totales.totalGravada > 0 ? [{ ...TRIBUTO_IVA, valor: iva.total }] : null,
    montoTotalOperacion,
    ivaPerci: percepcion.total,
    totalIva: iva.total,
    ivaRete: retencion.total,
    totalNoGravado: totales.totalNoGravado,
    totalPagar,
    totalLetras: numeroALetras(totalPagar),
    condicionOperacion: CONDICION_OPERACION.CONTADO,
    ...extraResumen,
    observaciones: observacionesNormalizadas,
    codigoRetencionMH: null,
  };

  const { identificacion, codigoGeneracion, numeroControl } = _construirIdentificacionV2({
    tipoDte,
    version: 4,
    issuer,
    contingencia,
  });
  // fe-nc-v4.json y fe-nd-v4.json exigen "fusion" y no admiten
  // codEstable/codPuntoVenta en el emisor; el número de control sí lleva los
  // códigos MH del emisor.
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

/** Nota de Crédito Electrónica (05). Ver `_construirNota`. */
function construirNotaCredito(solicitud, opciones = {}) {
  return _construirNota(TIPO_DTE.NOTA_CREDITO, solicitud, opciones);
}

/** Nota de Débito Electrónica (06): cargos sobre el CCF. Ver `_construirNota`. */
function construirNotaDebito(solicitud, opciones = {}) {
  return _construirNota(TIPO_DTE.NOTA_DEBITO, solicitud, opciones);
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
