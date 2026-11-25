const { generarCodigoGeneracion } = require('../utils/codigoGeneracion');
const { fechaHoraSV } = require('../utils/fechaHoraSV');
const { numeroALetras } = require('../utils/numeroALetras');
const { parsearNumeroControl } = require('../utils/numeroControl');
const { validarLineas, prorratearCentavos, r2, HOLGURA } = require('./calculoFiscal');
const { TIPO_DTE } = require('../config/catalogs');

/**
 * Evento de Retorno (tipo 18 de CAT-002, schema oficial v1/fe-eret-v1.json)
 * sobre una Factura Electrónica (01) con sello (Normativa 2.0, regla 13.3;
 * Manual Funcional v2.0, sección X).
 *
 * - Emisor, receptor y documento relacionado se copian de la factura guardada:
 *   el evento ajusta esa operación y no la configuración vigente.
 * - Las líneas las manda el ERP, que conoce el saldo de cada línea entre
 *   retornos: número de línea de la factura, cantidad devuelta y montos (con IVA
 *   incluido, como la factura). Aquí se valida que no pasen de la línea y que
 *   cantidad × precio − descuento cuadre con la venta (holgura ±0.01).
 * - El retorno no es un descuento: solo devolución por cantidad.
 * - La retención de IVA (1 %) se repite si la factura la tuvo, sobre lo gravado
 *   sin IVA del evento.
 */
const TIPO_EVENTO_RETORNO = TIPO_DTE.EVENTO_RETORNO; // '18'
const TASA_IVA = 0.13;
const TASA_RETENCION = 0.01;
const MONTOS = ['montoDescu', 'ventaNoSuj', 'ventaExenta', 'ventaGravada', 'ivaItem'];

function errorSolicitud(mensaje) {
  return Object.assign(new Error(mensaje), { code: 'INVALID_RETURN_REQUEST' });
}

function textoONull(valor) {
  return typeof valor === 'string' && valor.trim() ? valor.trim() : null;
}

/** Receptor de la factura en la sección "documento" del evento (null si la factura no lo detalla). */
function documentoDelReceptor(dte) {
  const receptor = dte.receptor;
  if (!receptor) return null;
  return {
    tipoDocumento: textoONull(receptor.tipoDocumento),
    numDocumento: textoONull(receptor.numDocumento),
    nombre: textoONull(receptor.nombre),
    codPais: null,
    nombrePais: null,
    telefono: textoONull(receptor.telefono),
    correo: textoONull(receptor.correo),
  };
}

function lineasDelEvento(dte, items, codigoFactura) {
  if (!Array.isArray(items) || items.length === 0) {
    throw errorSolicitud('El evento de retorno requiere al menos una línea devuelta');
  }
  const lineasFactura = new Map((dte.cuerpoDocumento || []).map((linea) => [linea.numItem, linea]));
  const vistas = new Set();
  return items.map((item, indice) => {
    const numero = Number(item?.numItem);
    const linea = lineasFactura.get(numero);
    if (!linea) throw errorSolicitud(`Línea ${indice + 1}: la factura no tiene la línea ${item?.numItem}`);
    if (vistas.has(numero)) throw errorSolicitud(`Línea ${indice + 1}: la línea ${numero} de la factura se repite`);
    vistas.add(numero);
    const cantidad = Number(item.cantidad);
    if (!Number.isFinite(cantidad) || cantidad <= 0 || cantidad > linea.cantidad + 1e-9) {
      throw errorSolicitud(`Línea ${indice + 1}: la cantidad devuelta debe ser mayor que cero y no pasar de lo vendido (${linea.cantidad})`);
    }
    const montos = {};
    for (const campo of MONTOS) {
      const valor = item[campo] === undefined || item[campo] === null ? 0 : Number(item[campo]);
      if (!Number.isFinite(valor) || valor < 0) {
        throw errorSolicitud(`Línea ${indice + 1}: ${campo} debe ser un importe no negativo`);
      }
      // El descuento puede traer la parte prorrateada del descuento global de la factura: lo
      // controla la cuadratura cantidad × precio − descuento = venta.
      if (campo !== 'montoDescu' && valor > (linea[campo] ?? 0) + HOLGURA + 1e-9) {
        throw errorSolicitud(`Línea ${indice + 1}: ${campo} (${valor.toFixed(2)}) pasa de lo facturado en la línea ${numero}`);
      }
      montos[campo] = valor;
    }
    return {
      numItem: indice + 1,
      tipoItem: linea.tipoItem,
      codigoGeneracion: codigoFactura,
      cantidad,
      precioUni: linea.precioUni,
      descripcion: linea.descripcion,
      codigo: linea.codigo ?? null,
      uniMedida: linea.uniMedida,
      montoDescu: montos.montoDescu,
      codTributo: null,
      ventaNoSuj: montos.ventaNoSuj,
      ventaExenta: montos.ventaExenta,
      ventaGravada: montos.ventaGravada,
      compra: 0,
      tributos: null,
      psv: 0,
      ivaItem: montos.ivaItem,
      noGravado: 0,
      seguro: 0,
      flete: 0,
      ivaRete: 0,
      reteRenta: 0,
    };
  });
}

/**
 * @param {object} p
 * @param {object} p.dte   JSON de la factura (payload guardado).
 * @param {Array}  p.items [{ numItem (línea de la factura), cantidad, montoDescu, ventaNoSuj, ventaExenta, ventaGravada, ivaItem }]
 * @param {object|null} [p.contingencia] { tipoContingencia, motivoContin }
 * @param {Date} [p.ahora]
 */
function construirEventoRetorno({ dte, items, contingencia = null, ahora } = {}) {
  const identificacion = dte?.identificacion;
  if (!identificacion?.codigoGeneracion || !dte.emisor || !Array.isArray(dte.cuerpoDocumento)) {
    throw errorSolicitud('Se requiere el JSON completo de la factura a la que se aplica el retorno');
  }
  if (identificacion.tipoDte !== TIPO_DTE.FACTURA) {
    throw errorSolicitud('El evento de retorno del ERP se aplica a una Factura Electrónica (01)');
  }
  let establecimiento;
  try {
    establecimiento = parsearNumeroControl(identificacion.numeroControl);
  } catch {
    throw errorSolicitud('El número de control de la factura no es válido');
  }

  const cuerpoDocumento = lineasDelEvento(dte, items, identificacion.codigoGeneracion);
  validarLineas(cuerpoDocumento);

  const suma = (campo) => r2(cuerpoDocumento.reduce((total, linea) => total + linea[campo], 0));
  const totalNoSuj = suma('ventaNoSuj');
  const totalExenta = suma('ventaExenta');
  const totalGravada = suma('ventaGravada');
  const totalIva = suma('ivaItem');
  const subTotalVentas = r2(totalNoSuj + totalExenta + totalGravada);

  // La factura retuvo IVA (gran contribuyente): el retorno repite el 1 % sobre lo gravado sin IVA.
  const retuvo = Number(dte.resumen?.ivaRete1 ?? dte.resumen?.ivaRete ?? 0) > 0;
  const baseGravada = r2(totalGravada / (1 + TASA_IVA));
  const ivaRete = retuvo ? r2(baseGravada * TASA_RETENCION) : 0;
  if (ivaRete > 0) {
    const centavos = prorratearCentavos(Math.round(ivaRete * 100), cuerpoDocumento.map((linea) => Math.round(linea.ventaGravada * 100)));
    cuerpoDocumento.forEach((linea, indice) => { linea.ivaRete = centavos[indice] / 100; });
  }
  const montoTotalOperacion = subTotalVentas; // IVA incluido, como la factura
  const totalPagar = r2(montoTotalOperacion - ivaRete);

  const { fecha, hora } = fechaHoraSV(ahora);
  const codigoGeneracion = generarCodigoGeneracion();
  const enContingencia = Boolean(contingencia);
  const evento = {
    identificacion: {
      version: 1,
      ambiente: identificacion.ambiente,
      tipoModelo: enContingencia ? 2 : 1,
      tipoOperacion: enContingencia ? 2 : 1,
      tipoEvento: TIPO_EVENTO_RETORNO,
      tipoContingencia: enContingencia ? Number(contingencia.tipoContingencia) : null,
      motivoContin: enContingencia ? textoONull(contingencia.motivoContin) : null,
      codigoGeneracion,
      fecEmi: fecha < identificacion.fecEmi ? identificacion.fecEmi : fecha,
      horEmi: hora,
      fusion: null,
      tipoMoneda: 'USD',
    },
    documentoRelacionado: [
      { tipoDocumento: TIPO_DTE.FACTURA, codigoGeneracion: identificacion.codigoGeneracion, fechaEmision: identificacion.fecEmi },
    ],
    emisor: {
      nit: dte.emisor.nit,
      nombre: dte.emisor.nombre,
      codEstableMH: establecimiento.codEstableMH,
      codEstable: dte.emisor.codEstable ?? null,
      codPuntoVentaMH: establecimiento.codPuntoVentaMHCompleto,
      codPuntoVenta: dte.emisor.codPuntoVenta ?? null,
      recintoFiscal: null,
      tipoRegimen: null,
      regimen: null,
      tipoItemExpor: null,
    },
    documento: documentoDelReceptor(dte),
    ventaTercero: null,
    compraTercero: null,
    cuerpoDocumento,
    resumen: {
      totalNoSuj,
      totalExenta,
      totalGravada,
      totalCompraExcluidos: 0,
      subTotalVentas,
      tributos: null,
      totalSeguro: null,
      totalFlete: null,
      montoTotalOperacion,
      ivaRete,
      reteRenta: 0,
      totalNoGravado: 0,
      totalPagar,
      totalLetras: numeroALetras(totalPagar),
      totalNoOnerosas: 0,
      totalIva,
      saldoFavor: 0,
    },
    apendice: null,
  };
  return { evento, codigoGeneracion };
}

module.exports = { construirEventoRetorno, TIPO_EVENTO_RETORNO };
