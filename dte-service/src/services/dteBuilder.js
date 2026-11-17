const { generarCodigoGeneracion } = require('../utils/codigoGeneracion');
const { generarNumeroControl } = require('../utils/numeroControl');
const { fechaHoraSV } = require('../utils/fechaHoraSV');
const { calcularVentasPorCategoria, validarLineas, aplicarDescuentoGlobal, r2, r8, HOLGURA } = require('./calculoFiscal');
const { numeroALetras } = require('../utils/numeroALetras');
const { TIPO_DTE, MODELO_FACTURACION, TIPO_TRANSMISION, CONDICION_OPERACION, TIPO_CONTINGENCIA, esCodigoValido } = require('../config/catalogs');
const config = require('../config');
const { validateIssuerV2 } = require('./issuerContractV2');

const TASA_IVA = 0.13;
const TRIBUTO_IVA = Object.freeze({ codigo: '20', descripcion: 'Impuesto al Valor Agregado 13%' });

function errorDeSolicitud(mensaje) {
  return Object.assign(new Error(mensaje), { code: 'INVALID_DTE_REQUEST' });
}

/**
 * Datos de contingencia para documentos generados en modelo diferido
 * (Manual Funcional VIII): tipoModelo 2, tipoOperacion 2, tipo CAT-005 y
 * motivo obligatorio cuando el tipo es 5. Sin contingencia: modelo previo.
 */
function _camposContingencia(contingencia) {
  if (!contingencia) {
    return { tipoModelo: MODELO_FACTURACION.PREVIO, tipoOperacion: TIPO_TRANSMISION.NORMAL, tipoContingencia: null, motivoContin: null };
  }
  const tipo = Number(contingencia.tipoContingencia);
  if (!Object.values(TIPO_CONTINGENCIA).includes(tipo)) throw errorDeSolicitud('tipoContingencia inválido (CAT-005)');
  const motivo = typeof contingencia.motivoContin === 'string' && contingencia.motivoContin.trim()
    ? contingencia.motivoContin.trim().slice(0, 500)
    : null;
  if (tipo === TIPO_CONTINGENCIA.OTRO && !motivo) throw errorDeSolicitud('motivoContin es obligatorio cuando tipoContingencia es 5');
  return { tipoModelo: MODELO_FACTURACION.DIFERIDO, tipoOperacion: TIPO_TRANSMISION.CONTINGENCIA, tipoContingencia: tipo, motivoContin: motivo };
}

/**
 * identificacion común a Factura y CCF. Fecha, hora y año del correlativo se
 * toman en hora de El Salvador para que el número de control pertenezca al
 * mismo año calendario que fecEmi.
 */
function _construirIdentificacion({ tipoDte, version, issuer = config.emisor, contingencia = null }) {
  const camposContingencia = _camposContingencia(contingencia);
  const codigoGeneracion = generarCodigoGeneracion();
  const { fecha, hora, anio } = fechaHoraSV();
  // Multiemisor: un emisor distinto del heredado del entorno lleva su propia serie
  // por NIT y ambiente; el heredado conserva la suya para no reiniciar números.
  const serieDelEmisor = issuer.nit !== config.emisor?.nit;
  const numeroControl = generarNumeroControl({
    tipoDte,
    tipoEstablecimiento: issuer.tipoEstablecimiento,
    codEstablecimientoMH: issuer.codEstablecimientoMH,
    codPuntoVentaMH: issuer.codPuntoVentaMH,
    anio,
    nit: serieDelEmisor ? issuer.nit : '',
    ambiente: serieDelEmisor ? config.ambiente : '',
  });

  const identificacion = {
    version,
    ambiente: config.ambiente,
    tipoDte,
    numeroControl,
    codigoGeneracion,
    ...camposContingencia,
    fecEmi: fecha,
    horEmi: hora,
    tipoMoneda: 'USD',
  };

  return { identificacion, codigoGeneracion, numeroControl };
}

function _construirEmisor(issuer = config.emisor) {
  return {
    nit: issuer.nit,
    nrc: issuer.nrc,
    nombre: issuer.nombre,
    codActividad: issuer.codActividad,
    descActividad: issuer.descActividad,
    nombreComercial: issuer.nombreComercial,
    direccion: {
      departamento: issuer.direccion.departamento,
      municipio: issuer.direccion.municipio,
      distrito: issuer.direccion.distrito,
      complemento: issuer.direccion.complemento,
    },
    telefono: issuer.telefono,
    correo: issuer.correo,
    codEstable: Object.prototype.hasOwnProperty.call(issuer, 'codEstable') ? issuer.codEstable : issuer.codEstableInterno,
    codPuntoVenta: Object.prototype.hasOwnProperty.call(issuer, 'codPuntoVenta') ? issuer.codPuntoVenta : issuer.codPuntoVentaInterno,
  };
}

function _aplicarPago(resumen, pago) {
  if (!pago) return resumen;
  const codigo = pago.codigo === undefined || pago.codigo === null ? null : String(pago.codigo);
  if (codigo !== null && !esCodigoValido('CAT-017', codigo)) {
    throw errorDeSolicitud(`Código de forma de pago ${codigo} no existe en CAT-017`);
  }
  const montoPago = Number(pago.montoPago);
  if (!Number.isFinite(montoPago) || Math.round(montoPago * 100) !== Math.round(resumen.totalPagar * 100)) {
    throw errorDeSolicitud('El monto de pago no coincide con el total a pagar del DTE');
  }
  const referencia = pago.referencia == null ? null : String(pago.referencia).trim() || null;
  const numPagoElectronico = pago.numPagoElectronico == null ? null : String(pago.numPagoElectronico).trim() || null;
  if (referencia && referencia.length > 50) throw errorDeSolicitud('La referencia de pago excede 50 caracteres');
  if (numPagoElectronico && numPagoElectronico.length > 100) throw errorDeSolicitud('El número de pago electrónico excede 100 caracteres');

  return {
    ...resumen,
    pagos: [{ codigo, montoPago: r2(montoPago), referencia, plazo: null, periodo: null }],
    numPagoElectronico,
  };
}

function _lineaBase(item, indice) {
  return {
    numItem: indice + 1,
    tipoItem: item.tipoItem ?? 1, // CAT-011: 1=Bienes, 2=Servicios
    numeroDocumento: null,
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
  };
}

/** IVA contenido en una venta gravada con IVA incluido (8 decimales del cuerpo). */
function _ivaIncluido(ventaGravada) {
  return r8((ventaGravada * TASA_IVA) / (1 + TASA_IVA));
}

/**
 * Resumen de la Factura (consumidor final). Los precios y ventas incluyen
 * IVA (Manual Funcional XIV: el tributo 20 no aplica a FE y su código de
 * tributo va en null), así que:
 *   subTotal = subTotalVentas − descuentos globales (0: se prorratean)
 *   totalIva = Σ ivaItem (informativo, ya contenido en las ventas)
 *   montoTotalOperacion = subTotal
 *   totalPagar = montoTotalOperacion − ivaRete + totalNoGravado
 */
/**
 * Ajustes del ERP (bloque V3b). El ERP es dueño del cálculo fiscal: manda la
 * condición de la operación, la retención y la percepción que ya calculó, y
 * pide llevar el descuento global en el resumen (descuGravada, descuExenta,
 * descuNoSuj) en lugar de prorratearlo a las líneas. Cada valor se valida
 * contra las reglas de Hacienda antes de reservar el correlativo.
 *
 * Sin `ajustes` el comportamiento es el heredado.
 */
const CONDICIONES = Object.freeze([CONDICION_OPERACION.CONTADO, CONDICION_OPERACION.CREDITO, CONDICION_OPERACION.OTRO]);
const UMBRAL_RETENCION = 100; // CT arts. 162 y 163: desde $100 sin IVA.
const TASA_RETENCION = 0.01;

function _normalizarAjustes(ajustes, tipoDte) {
  if (!ajustes) return null;
  if (typeof ajustes !== 'object') throw errorDeSolicitud('"ajustes" debe ser un objeto');
  const condicion = ajustes.condicionOperacion ?? CONDICION_OPERACION.CONTADO;
  if (!CONDICIONES.includes(condicion)) throw errorDeSolicitud('condicionOperacion debe ser 1 (contado), 2 (crédito) o 3 (otro)');
  const plazoDias = ajustes.plazoDias ?? null;
  if (condicion === CONDICION_OPERACION.CREDITO && !(Number.isInteger(plazoDias) && plazoDias > 0 && plazoDias <= 365)) {
    throw errorDeSolicitud('Una venta a crédito requiere plazoDias entre 1 y 365');
  }
  const importe = (valor, nombre) => {
    const numero = valor ?? 0;
    if (typeof numero !== 'number' || !Number.isFinite(numero) || numero < 0) {
      throw errorDeSolicitud(`${nombre} debe ser un importe no negativo`);
    }
    return r2(numero);
  };
  const ivaPerci = importe(ajustes.ivaPerci, 'ivaPerci');
  if (ivaPerci > 0 && tipoDte !== TIPO_DTE.COMPROBANTE_CREDITO_FISCAL) {
    throw errorDeSolicitud('La percepción de IVA solo aplica al comprobante de crédito fiscal');
  }
  return {
    condicion,
    plazoDias: condicion === CONDICION_OPERACION.CREDITO ? plazoDias : null,
    ivaRete: importe(ajustes.ivaRete, 'ivaRete'),
    ivaPerci,
    descuentoEnResumen: ajustes.descuentoGlobalEnResumen === true,
  };
}

function _descuentosGlobales(descuentoGlobal, resumen) {
  const d = descuentoGlobal || {};
  const descuentos = {};
  for (const [campo, total, nombre] of [
    ['gravada', resumen.totalGravada, 'descuGravada'],
    ['exenta', resumen.totalExenta, 'descuExenta'],
    ['noSuj', resumen.totalNoSuj, 'descuNoSuj'],
  ]) {
    const monto = d[campo] ?? 0;
    if (typeof monto !== 'number' || !Number.isFinite(monto) || monto < 0) {
      throw errorDeSolicitud(`El descuento global de ${campo} debe ser un número no negativo`);
    }
    if (r2(monto) > r2(total) + 1e-9) throw errorDeSolicitud(`El descuento global de ${campo} excede el total de esa categoría`);
    descuentos[nombre] = r2(monto);
  }
  return descuentos;
}

/** Aplica los ajustes del ERP al resumen ya construido. */
function _aplicarAjustes(resumen, { tipoDte, ajustes, descuentoGlobal }) {
  if (!ajustes) return resumen;
  const esCCF = tipoDte === TIPO_DTE.COMPROBANTE_CREDITO_FISCAL;
  const ajustado = { ...resumen, condicionOperacion: ajustes.condicion };

  if (ajustes.descuentoEnResumen) {
    const descuentos = _descuentosGlobales(descuentoGlobal, resumen);
    const global = r2(descuentos.descuGravada + descuentos.descuExenta + descuentos.descuNoSuj);
    Object.assign(ajustado, descuentos);
    ajustado.totalDescu = r2(resumen.totalDescu + global);
    ajustado.subTotal = r2(resumen.subTotalVentas - global);
    ajustado.porcentajeDescuento = resumen.subTotalVentas > 0 ? r2((global / resumen.subTotalVentas) * 100) : 0;
  }

  const baseGravada = r2(ajustado.totalGravada - ajustado.descuGravada);
  // Base de la retención, sin IVA: en factura la venta gravada lo trae incluido.
  const baseSinIva = esCCF ? baseGravada : r2(baseGravada / (1 + TASA_IVA));
  if (esCCF) {
    const iva = r2(baseGravada * TASA_IVA);
    ajustado.tributos = ajustado.totalGravada > 0 ? [{ ...TRIBUTO_IVA, valor: iva }] : null;
    ajustado.montoTotalOperacion = r2(ajustado.subTotal + iva);
  } else {
    ajustado.totalIva = r2((baseGravada * TASA_IVA) / (1 + TASA_IVA));
    ajustado.montoTotalOperacion = ajustado.subTotal;
  }

  if (ajustes.ivaRete > 0) {
    const esperada = r2(baseSinIva * TASA_RETENCION);
    if (baseSinIva < UMBRAL_RETENCION || Math.abs(ajustes.ivaRete - esperada) > HOLGURA + 1e-9) {
      throw errorDeSolicitud(`La retención (${ajustes.ivaRete.toFixed(2)}) no corresponde al 1 % de la base sin IVA desde $100 (${esperada.toFixed(2)})`);
    }
  }
  if (ajustes.ivaPerci > 0 && (baseGravada < UMBRAL_RETENCION || ajustes.ivaPerci > r2(baseGravada * TASA_RETENCION) + HOLGURA + 1e-9)) {
    throw errorDeSolicitud('La percepción excede el 1 % de la base gravada o la base es menor de $100');
  }
  ajustado.ivaRete = ajustes.ivaRete;
  if (esCCF) ajustado.ivaPerci = ajustes.ivaPerci;
  const totalPagar = r2(ajustado.montoTotalOperacion + (esCCF ? ajustes.ivaPerci : 0) - ajustes.ivaRete + ajustado.totalNoGravado);
  if (totalPagar < 0) throw errorDeSolicitud('El total a pagar no puede ser negativo');
  ajustado.totalPagar = totalPagar;
  ajustado.totalLetras = numeroALetras(totalPagar);
  return ajustado;
}

/** Con crédito, el pago lleva el plazo en días (CAT-018 código 01). */
function _plazoDelPago(resumen, ajustes) {
  if (!ajustes || ajustes.condicion !== CONDICION_OPERACION.CREDITO || !resumen.pagos) return resumen;
  return { ...resumen, pagos: resumen.pagos.map((pago) => ({ ...pago, plazo: '01', periodo: ajustes.plazoDias })) };
}

function _construirResumenFactura(items, cuerpoDocumento) {
  const totales = calcularVentasPorCategoria(items);
  const subTotalVentas = r2(totales.totalGravada + totales.totalExenta + totales.totalNoSuj);
  const subTotal = r2(subTotalVentas - totales.descuNoSuj - totales.descuExenta - totales.descuGravada);
  const totalIva = r2(cuerpoDocumento.reduce((suma, linea) => suma + linea.ivaItem, 0));
  const ivaRete = 0;
  const montoTotalOperacion = subTotal;
  const totalPagar = r2(montoTotalOperacion - ivaRete + totales.totalNoGravado);
  if (totalPagar < 0) throw errorDeSolicitud('El total a pagar no puede ser negativo');

  return {
    totalNoSuj: totales.totalNoSuj,
    totalExenta: totales.totalExenta,
    totalGravada: totales.totalGravada,
    subTotalVentas,
    descuNoSuj: totales.descuNoSuj,
    descuExenta: totales.descuExenta,
    descuGravada: totales.descuGravada,
    porcentajeDescuento: 0,
    totalDescu: totales.totalDescu,
    tributos: null,
    subTotal,
    ivaRete,
    montoTotalOperacion,
    totalNoGravado: totales.totalNoGravado,
    totalPagar,
    totalLetras: numeroALetras(totalPagar),
    totalIva,
    saldoFavor: 0,
    condicionOperacion: CONDICION_OPERACION.CONTADO,
    pagos: null,
    numPagoElectronico: null,
    observaciones: null,
  };
}

function _normalizarReceptorFactura(receptor) {
  if (!receptor) return null;
  const tipoDocumento = receptor.tipoDocumento ?? null;
  const numDocumento = receptor.numDocumento ?? null;
  if ((tipoDocumento === null) !== (numDocumento === null)) {
    throw errorDeSolicitud('El receptor debe informar tipoDocumento y numDocumento juntos, o ninguno de los dos');
  }
  return {
    tipoDocumento,
    numDocumento,
    nrc: receptor.nrc ?? null,
    nombre: receptor.nombre ?? null,
    codActividad: receptor.codActividad ?? null,
    descActividad: receptor.descActividad ?? null,
    direccion: receptor.direccion ?? null,
    telefono: receptor.telefono ?? null,
    correo: receptor.correo ?? null,
  };
}

/**
 * Factura Electrónica (tipoDte 01), schema oficial fe-f-v2.json (version 2).
 *
 * Contrato de líneas (IVA INCLUIDO): `precioUni`, `montoDescu` y las ventas
 * van con IVA y cumplen cantidad × precioUni − montoDescu = venta. `ivaItem`
 * se calcula siempre a partir de ventaGravada; un valor enviado por el
 * cliente se ignora para no transmitir un IVA inconsistente.
 *
 * `descuentoGlobal` (opcional) = { gravada?, exenta?, noSuj? } en dólares; se
 * prorratea a las líneas como descuento por ítem.
 */
function construirFactura({ emisor = null, receptor, items, descuentoGlobal = null, pago = null, ajustes = null }, { contingencia = null } = {}) {
  const issuer = emisor ? validateIssuerV2(emisor) : config.emisor;
  if (!Array.isArray(items) || items.length === 0) throw errorDeSolicitud('Se requiere "items" con al menos 1 línea');
  const ajustesErp = _normalizarAjustes(ajustes, TIPO_DTE.FACTURA);
  const lineas = ajustesErp?.descuentoEnResumen ? items : aplicarDescuentoGlobal(items, descuentoGlobal);
  validarLineas(lineas);

  const cuerpoDocumento = lineas.map((item, indice) => ({
    ..._lineaBase(item, indice),
    tributos: null,
    psv: item.psv ?? 0,
    noGravado: item.noGravado ?? 0,
    ivaItem: _ivaIncluido(item.ventaGravada ?? 0),
  }));

  const receptorNormalizado = _normalizarReceptorFactura(receptor);
  // Toda validación de negocio, incluido el pago, ocurre antes de reservar el
  // correlativo: un pago no conciliado no consume Número de Control.
  const resumen = _plazoDelPago(
    _aplicarPago(
      _aplicarAjustes(_construirResumenFactura(lineas, cuerpoDocumento), { tipoDte: TIPO_DTE.FACTURA, ajustes: ajustesErp, descuentoGlobal }),
      pago,
    ),
    ajustesErp,
  );
  const { identificacion, codigoGeneracion, numeroControl } = _construirIdentificacion({
    tipoDte: TIPO_DTE.FACTURA,
    version: 2,
    issuer,
    contingencia,
  });

  const dte = {
    identificacion,
    documentoRelacionado: null,
    emisor: _construirEmisor(issuer),
    receptor: receptorNormalizado,
    otrosDocumentos: null,
    ventaTercero: null,
    cuerpoDocumento,
    resumen,
    apendice: null,
  };

  return { dte, codigoGeneracion, numeroControl };
}

/**
 * IVA del CCF: se respeta el IVA asignado al pedido (Σ ivaItem enviado por el
 * cliente) para que el total coincida con lo cobrado, siempre que esté dentro
 * de la holgura de ±0.01 respecto del 13 % de la base gravada. Sin IVA por
 * línea se calcula sobre la base.
 */
function _ivaCCF(lineas, baseGravada) {
  const esperado = r2(baseGravada * TASA_IVA);
  const gravadas = lineas.filter((item) => (item.ventaGravada ?? 0) > 0);
  const conIva = gravadas.filter((item) => item.ivaItem !== undefined && item.ivaItem !== null);
  if (conIva.length === 0) return esperado;
  if (conIva.length !== gravadas.length) {
    throw errorDeSolicitud('El IVA del CCF debe informarse en todas las líneas gravadas o en ninguna');
  }
  if (conIva.some((item) => typeof item.ivaItem !== 'number' || !Number.isFinite(item.ivaItem) || item.ivaItem < 0)) {
    throw errorDeSolicitud('El IVA por línea del CCF debe ser un importe no negativo');
  }
  const informado = r2(conIva.reduce((suma, item) => suma + item.ivaItem, 0));
  if (Math.abs(informado - esperado) > HOLGURA + 1e-9) {
    throw errorDeSolicitud(`El IVA informado (${informado.toFixed(2)}) difiere del 13 % de la base gravada (${esperado.toFixed(2)}) en más de 0.01`);
  }
  return informado;
}

/**
 * Resumen del CCF (precios sin IVA):
 *   subTotal = subTotalVentas − descuentos globales (0: se prorratean)
 *   tributo 20 = 13 % de (totalGravada − descuGravada), holgura ±0.01
 *   montoTotalOperacion = subTotal + tributos
 *   totalPagar = montoTotalOperacion + ivaPerci − ivaRete + totalNoGravado
 * `ivaPerci` es IVA percibido (no aplica al checkout) y queda en 0.
 */
function _construirResumenCCF(lineas) {
  const totales = calcularVentasPorCategoria(lineas);
  const subTotalVentas = r2(totales.totalGravada + totales.totalExenta + totales.totalNoSuj);
  const subTotal = r2(subTotalVentas - totales.descuNoSuj - totales.descuExenta - totales.descuGravada);
  const baseGravada = r2(totales.totalGravada - totales.descuGravada);
  const iva = _ivaCCF(lineas, baseGravada);
  const ivaPerci = 0;
  const ivaRete = 0;
  const montoTotalOperacion = r2(subTotal + iva);
  const totalPagar = r2(montoTotalOperacion + ivaPerci - ivaRete + totales.totalNoGravado);
  if (totalPagar < 0) throw errorDeSolicitud('El total a pagar no puede ser negativo');

  return {
    totalNoSuj: totales.totalNoSuj,
    totalExenta: totales.totalExenta,
    totalGravada: totales.totalGravada,
    subTotalVentas,
    descuNoSuj: totales.descuNoSuj,
    descuExenta: totales.descuExenta,
    descuGravada: totales.descuGravada,
    porcentajeDescuento: 0,
    totalDescu: totales.totalDescu,
    tributos: totales.totalGravada > 0 ? [{ ...TRIBUTO_IVA, valor: iva }] : null,
    subTotal,
    ivaPerci,
    ivaRete,
    montoTotalOperacion,
    totalNoGravado: totales.totalNoGravado,
    totalPagar,
    totalLetras: numeroALetras(totalPagar),
    saldoFavor: 0,
    condicionOperacion: CONDICION_OPERACION.CONTADO,
    pagos: null,
    numPagoElectronico: null,
    observaciones: null,
  };
}

/**
 * Comprobante de Crédito Fiscal (tipoDte 03), schema oficial fe-ccf-v4.json
 * (version 4). El receptor siempre requiere NIT + NRC.
 *
 * Contrato de líneas (SIN IVA): `precioUni`, `montoDescu` y ventas netas que
 * cumplen cantidad × precioUni − montoDescu = venta; `ivaItem` opcional con
 * el IVA asignado a cada línea (no se transmite en el cuerpo).
 */
function construirCCF({ emisor = null, receptor, items, descuentoGlobal = null, pago = null, ajustes = null }, { contingencia = null } = {}) {
  const issuer = emisor ? validateIssuerV2(emisor) : config.emisor;
  if (!Array.isArray(items) || items.length === 0) throw errorDeSolicitud('Se requiere "items" con al menos 1 línea');
  if (!receptor || !receptor.nit || !receptor.nrc) {
    throw errorDeSolicitud('Un CCF requiere receptor.nit y receptor.nrc (schema fe-ccf-v4.json los exige como no-nulos)');
  }
  const ajustesErp = _normalizarAjustes(ajustes, TIPO_DTE.COMPROBANTE_CREDITO_FISCAL);
  const lineas = ajustesErp?.descuentoEnResumen ? items : aplicarDescuentoGlobal(items, descuentoGlobal);
  validarLineas(lineas);

  const cuerpoDocumento = lineas.map((item, indice) => ({
    ..._lineaBase(item, indice),
    tributos: (item.ventaGravada ?? 0) > 0 ? [TRIBUTO_IVA.codigo] : null,
    psv: item.psv ?? 0,
    noGravado: item.noGravado ?? 0,
  }));
  // El CCF solo reserva identidad cuando las líneas, el receptor fiscal y el
  // pago ya cuadran. Los errores deterministas previos no avanzan correlativos.
  const resumen = _plazoDelPago(
    _aplicarPago(
      _aplicarAjustes(_construirResumenCCF(lineas), {
        tipoDte: TIPO_DTE.COMPROBANTE_CREDITO_FISCAL, ajustes: ajustesErp, descuentoGlobal,
      }),
      pago,
    ),
    ajustesErp,
  );
  const { identificacion, codigoGeneracion, numeroControl } = _construirIdentificacion({
    tipoDte: TIPO_DTE.COMPROBANTE_CREDITO_FISCAL,
    version: 4,
    issuer,
    contingencia,
  });

  const dte = {
    identificacion,
    documentoRelacionado: null,
    emisor: _construirEmisor(issuer),
    receptor: {
      nit: receptor.nit,
      nrc: receptor.nrc,
      nombre: receptor.nombre,
      codActividad: receptor.codActividad,
      descActividad: receptor.descActividad,
      nombreComercial: receptor.nombreComercial ?? null,
      direccion: receptor.direccion,
      telefono: receptor.telefono ?? null,
      correo: receptor.correo ?? null,
    },
    otrosDocumentos: null,
    ventaTercero: null,
    cuerpoDocumento,
    resumen,
    apendice: null,
  };

  return { dte, codigoGeneracion, numeroControl };
}

module.exports = {
  construirFactura,
  construirCCF,
  // Piezas compartidas con la Nota de Crédito (dteBuilderNotas.js).
  errorDeSolicitud,
  _camposContingencia,
  _construirIdentificacion,
  _construirEmisor,
  TASA_IVA,
  TRIBUTO_IVA,
};
