const { generarCodigoGeneracion } = require('../utils/codigoGeneracion');
const { fechaHoraSV } = require('../utils/fechaHoraSV');
const { parsearNumeroControl } = require('../utils/numeroControl');
const { TIPO_CONTINGENCIA, TIPO_DOCUMENTO_IDENTIFICACION } = require('../config/catalogs');

/**
 * Evento de Contingencia (schema oficial v4/contingencia-schema-v4.json,
 * Manual Funcional VIII). Se transmite una vez superada la causa que impidió
 * transmitir, informando de 1 a 1000 documentos generados en modelo diferido;
 * su tipo y motivo deben coincidir con los de esos documentos.
 *
 * @param {object} p
 * @param {Array<{tipoDte: string, codigoGeneracion: string}>} p.documentos
 * @param {object} p.emisor          Emisor de los documentos: { nit, nombre, telefono, correo, numeroControl }
 *                                   (establecimiento y punto de venta MH salen del número de control).
 * @param {{fInicio, hInicio, fFin, hFin}} p.periodo  Inicio y fin reales de la contingencia (hora de El Salvador).
 * @param {number} p.tipoContingencia CAT-005.
 * @param {string|null} p.motivoContingencia  Obligatorio si el tipo es 5 (máximo 500 caracteres).
 * @param {{nombre, tipoDocumento, numeroDocumento}} p.responsable  Responsable del establecimiento.
 * @param {string} p.ambiente
 * @param {Date} [p.ahora]
 */
function construirEventoContingencia({ documentos, emisor, periodo, tipoContingencia, motivoContingencia = null, responsable, ambiente, ahora } = {}) {
  if (!Array.isArray(documentos) || documentos.length === 0) {
    throw new Error('El Evento de Contingencia requiere al menos un documento');
  }
  if (documentos.length > 1000) {
    throw new Error('El schema oficial permite máximo 1000 documentos por Evento de Contingencia');
  }
  const faltantesPeriodo = ['fInicio', 'fFin', 'hInicio', 'hFin'].filter((campo) => !periodo?.[campo]);
  if (faltantesPeriodo.length) throw new Error(`Periodo de contingencia incompleto: faltan ${faltantesPeriodo.join(', ')}`);
  if (`${periodo.fFin} ${periodo.hFin}` < `${periodo.fInicio} ${periodo.hInicio}`) {
    throw new Error('El fin de la contingencia no puede ser anterior a su inicio');
  }

  const tipo = Number(tipoContingencia);
  if (!Object.values(TIPO_CONTINGENCIA).includes(tipo)) throw new Error('tipoContingencia inválido (CAT-005)');
  const motivo = typeof motivoContingencia === 'string' && motivoContingencia.trim() ? motivoContingencia.trim() : null;
  if (tipo === TIPO_CONTINGENCIA.OTRO && !motivo) throw new Error('motivoContingencia es obligatorio cuando tipoContingencia es 5 (otro)');
  if (motivo && motivo.length > 500) throw new Error('motivoContingencia admite como máximo 500 caracteres');

  const nombreResponsable = responsable?.nombre?.trim();
  const tipoDocResponsable = responsable?.tipoDocumento?.trim();
  const numeroDocResponsable = responsable?.numeroDocumento?.trim();
  if (!nombreResponsable || !tipoDocResponsable || !numeroDocResponsable) {
    throw new Error('Se requiere el responsable del establecimiento: nombre, tipo y número de documento');
  }
  if (!Object.values(TIPO_DOCUMENTO_IDENTIFICACION).includes(tipoDocResponsable)) {
    throw new Error(`Tipo de documento del responsable fuera de CAT-022: ${tipoDocResponsable}`);
  }
  if (tipoDocResponsable === TIPO_DOCUMENTO_IDENTIFICACION.DUI && !/^\d{8}-\d$/.test(numeroDocResponsable)) {
    throw new Error('El DUI del responsable debe tener el formato 00000000-0');
  }
  if (tipoDocResponsable === TIPO_DOCUMENTO_IDENTIFICACION.NIT && !/^(\d{9}|\d{14})$/.test(numeroDocResponsable)) {
    throw new Error('El NIT del responsable debe tener 9 o 14 dígitos');
  }

  const establecimiento = parsearNumeroControl(emisor?.numeroControl);
  const codigoGeneracion = generarCodigoGeneracion(); // identidad propia del evento
  const { fecha, hora } = fechaHoraSV(ahora);

  const evento = {
    identificacion: {
      version: 4,
      ambiente,
      codigoGeneracion,
      fTransmision: fecha,
      hTransmision: hora,
    },
    emisor: {
      nit: emisor.nit,
      nombre: emisor.nombre,
      nombreResponsable,
      tipoDocResponsable,
      numeroDocResponsable,
      tipoEstablecimiento: establecimiento.tipoEstablecimiento,
      codEstableMH: establecimiento.codEstableMH,
      codPuntoVentaMH: establecimiento.codPuntoVentaMHCompleto,
      telefono: emisor.telefono,
      correo: emisor.correo,
    },
    detalleDTE: documentos.map((documento, indice) => ({
      noItem: indice + 1,
      tipoDoc: documento.tipoDte,
      codigoGeneracion: documento.codigoGeneracion,
    })),
    motivo: {
      fInicio: periodo.fInicio,
      fFin: periodo.fFin,
      hInicio: periodo.hInicio,
      hFin: periodo.hFin,
      tipoContingencia: tipo,
      motivoContingencia: motivo,
    },
  };

  return { evento, codigoGeneracion };
}

module.exports = { construirEventoContingencia };
