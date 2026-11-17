const { generarCodigoGeneracion } = require('../utils/codigoGeneracion');
const { fechaHoraSV } = require('../utils/fechaHoraSV');
const { fechaDelEventoInvalidacion } = require('../utils/plazosFiscales');
const { parsearNumeroControl } = require('../utils/numeroControl');
const { TIPO_ANULACION, TIPO_DOCUMENTO_IDENTIFICACION } = require('../config/catalogs');

/**
 * Evento de Invalidación (schema oficial v3/invalidacion-schema-v3.json) de
 * un DTE ya recibido por Hacienda, según el Manual Funcional v2.0 (VII):
 *
 * - Tipo 1 (error en la información) y 3 (otro): exigen el código del DTE
 *   que reemplaza al invalidado, ya transmitido y con sello, salvo que se
 *   invalide una Nota de Crédito (05) o un Comprobante de Liquidación (08).
 * - Tipo 2 (rescindir la operación): el reemplazo va en null.
 * - Emisor y receptor se copian del DTE invalidado (no de la configuración
 *   vigente); los códigos de establecimiento y punto de venta MH salen de su
 *   número de control, y el receptor de un CCF se identifica con 36 + NIT.
 * - La "Fecha del Evento" (identificacion.fecEmi) sigue plazosFiscales.js.
 */
const TIPOS_SIN_REEMPLAZO = new Set(['05', '08']);
const TIPOS_ANULACION_VALIDOS = new Set(Object.values(TIPO_ANULACION));
const TIPOS_DOCUMENTO_RESPONSABLE = new Set(Object.values(TIPO_DOCUMENTO_IDENTIFICACION));
const CODIGO_GENERACION_REGEX = /^[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}$/;

function errorSolicitud(mensaje) {
  return Object.assign(new Error(mensaje), { code: 'INVALID_INVALIDATION_REQUEST' });
}

function textoONull(valor) {
  return typeof valor === 'string' && valor.trim() ? valor.trim() : null;
}

function identificacionDe(persona, rol) {
  const nombre = textoONull(persona?.nombre);
  const tipo = textoONull(persona?.tipoDocumento);
  const numero = textoONull(persona?.numeroDocumento);
  if (!nombre || !tipo || !numero) {
    throw errorSolicitud(`Se requiere nombre, tipo y número de documento de quien ${rol} el evento`);
  }
  if (!TIPOS_DOCUMENTO_RESPONSABLE.has(tipo)) {
    throw errorSolicitud(`Tipo de documento de quien ${rol} el evento fuera del catálogo CAT-022: ${tipo}`);
  }
  if (tipo === TIPO_DOCUMENTO_IDENTIFICACION.DUI && !/^\d{8}-\d$/.test(numero)) {
    throw errorSolicitud(`El DUI de quien ${rol} el evento debe tener el formato 00000000-0`);
  }
  if (tipo === TIPO_DOCUMENTO_IDENTIFICACION.NIT && !/^(\d{9}|\d{14})$/.test(numero)) {
    throw errorSolicitud(`El NIT de quien ${rol} el evento debe tener 9 o 14 dígitos`);
  }
  if (nombre.length > 100 || numero.length > 20) {
    throw errorSolicitud(`Datos de quien ${rol} el evento demasiado largos`);
  }
  return { nombre, tipo, numero };
}

/** Receptor tal como figura en el DTE invalidado (null si la factura no lo detalla). */
function receptorDelDocumento(dte) {
  const receptor = dte.receptor ?? dte.sujetoExcluido ?? dte.donante ?? null;
  const contacto = {
    telefono: textoONull(receptor?.telefono),
    correo: textoONull(receptor?.correo),
  };
  if (!receptor) return { tipoDocumento: null, numDocumento: null, nombre: null, telefono: null, correo: null };
  if (receptor.nit) {
    return { tipoDocumento: TIPO_DOCUMENTO_IDENTIFICACION.NIT, numDocumento: receptor.nit, nombre: textoONull(receptor.nombre), ...contacto };
  }
  return {
    tipoDocumento: textoONull(receptor.tipoDocumento),
    numDocumento: textoONull(receptor.numDocumento),
    nombre: textoONull(receptor.nombre),
    ...contacto,
  };
}

/**
 * @param {object} p
 * @param {object} p.dte                     JSON del DTE invalidado (payload histórico).
 * @param {string} p.selloRecibido           Sello de recepción del DTE.
 * @param {object} p.motivo                  { tipoAnulacion, motivoAnulacion?, responsable, solicitante }
 *   responsable/solicitante = { nombre, tipoDocumento (CAT-022), numeroDocumento }
 * @param {string|null} p.codigoGeneracionReemplazo
 * @param {Date} [p.ahora]
 */
function construirEventoInvalidacion({ dte, selloRecibido, motivo, codigoGeneracionReemplazo = null, ahora } = {}) {
  const identificacion = dte?.identificacion;
  if (!identificacion?.codigoGeneracion || !identificacion.tipoDte || !identificacion.fecEmi || !dte.emisor) {
    throw errorSolicitud('Se requiere el JSON completo del DTE que se va a invalidar');
  }
  let establecimiento;
  try {
    establecimiento = parsearNumeroControl(identificacion.numeroControl);
  } catch {
    throw errorSolicitud('El número de control del DTE a invalidar no es válido');
  }
  if (typeof selloRecibido !== 'string' || selloRecibido.trim().length !== 40) {
    throw errorSolicitud('El DTE a invalidar no tiene un sello de recepción válido');
  }
  if (!motivo || typeof motivo !== 'object') throw errorSolicitud('Se requiere el motivo de la invalidación');

  const tipoDte = identificacion.tipoDte;
  const tipoAnulacion = Number(motivo.tipoAnulacion);
  if (!TIPOS_ANULACION_VALIDOS.has(tipoAnulacion)) {
    throw errorSolicitud('tipoAnulacion debe ser 1 (error en la información), 2 (rescindir la operación) o 3 (otro)');
  }

  const reemplazo = textoONull(codigoGeneracionReemplazo);
  const requiereReemplazo = tipoAnulacion !== TIPO_ANULACION.RESCINDIR_OPERACION && !TIPOS_SIN_REEMPLAZO.has(tipoDte);
  if (requiereReemplazo && !reemplazo) {
    throw errorSolicitud('Las invalidaciones tipo 1 y 3 requieren el código de generación del DTE que reemplaza al invalidado, ya transmitido con sello');
  }
  if (!requiereReemplazo && reemplazo) {
    throw errorSolicitud(tipoAnulacion === TIPO_ANULACION.RESCINDIR_OPERACION
      ? 'Al rescindir la operación (tipo 2) no se indica documento de reemplazo'
      : 'Las Notas de Crédito y Comprobantes de Liquidación se invalidan sin documento de reemplazo');
  }
  if (reemplazo && (!CODIGO_GENERACION_REGEX.test(reemplazo) || reemplazo === identificacion.codigoGeneracion)) {
    throw errorSolicitud('El código de generación del documento de reemplazo no es válido');
  }

  const motivoAnulacion = textoONull(motivo.motivoAnulacion);
  if (tipoAnulacion === TIPO_ANULACION.OTRO && !motivoAnulacion) {
    throw errorSolicitud('La invalidación tipo 3 (otro) requiere describir el motivo');
  }
  if (motivoAnulacion && motivoAnulacion.length > 200) throw errorSolicitud('El motivo admite como máximo 200 caracteres');

  const responsable = identificacionDe(motivo.responsable, 'realiza');
  const solicitante = identificacionDe(motivo.solicitante, 'solicita');

  const { fecha: hoy, hora } = fechaHoraSV(ahora);
  const fechaEvento = fechaDelEventoInvalidacion(tipoDte, identificacion.fecEmi, hoy);
  const codigoGeneracion = generarCodigoGeneracion(); // identidad propia del evento

  const evento = {
    identificacion: {
      version: 3,
      ambiente: identificacion.ambiente,
      codigoGeneracion,
      fecEmi: fechaEvento,
      horEmi: hora,
      fusion: null,
    },
    emisor: {
      nit: dte.emisor.nit,
      nombre: dte.emisor.nombre,
      codEstableMH: establecimiento.codEstableMH,
      codEstable: dte.emisor.codEstable ?? null,
      codPuntoVentaMH: establecimiento.codPuntoVentaMHCompleto,
      codPuntoVenta: dte.emisor.codPuntoVenta ?? null,
      telefono: dte.emisor.telefono,
      correo: dte.emisor.correo,
    },
    documento: {
      tipoDte,
      codigoGeneracion: identificacion.codigoGeneracion,
      selloRecibido: selloRecibido.trim(),
      numeroControl: identificacion.numeroControl,
      fecEmi: identificacion.fecEmi,
      codigoGeneracionR: reemplazo,
      ...receptorDelDocumento(dte),
    },
    motivo: {
      tipoAnulacion,
      motivoAnulacion,
      nombreResponsable: responsable.nombre,
      tipDocResponsable: responsable.tipo,
      numDocResponsable: responsable.numero,
      nombreSolicita: solicitante.nombre,
      tipDocSolicita: solicitante.tipo,
      numDocSolicita: solicitante.numero,
    },
  };

  return { evento, codigoGeneracion, requiereReemplazo };
}

module.exports = { construirEventoInvalidacion, TIPO_ANULACION, TIPOS_SIN_REEMPLAZO };
