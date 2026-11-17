/**
 * Interpretación semántica de las respuestas de Hacienda (Manual Técnico
 * v2.0, sección 4). Un HTTP 2xx no prueba aceptación: un DTE solo está
 * aceptado con estado PROCESADO y sello de recepción. Un rechazo llega como
 * HTTP 400 con estado RECHAZADO.
 */

function texto(valor) {
  return typeof valor === 'string' ? valor.trim() : '';
}

function sello(respuesta) {
  return texto(respuesta?.selloRecibido) || texto(respuesta?.selloRecepcion);
}

function detalle(respuesta) {
  return {
    codigoMsg: texto(respuesta?.codigoMsg) || null,
    descripcionMsg: texto(respuesta?.descripcionMsg) || texto(respuesta?.mensaje) || null,
    observaciones: Array.isArray(respuesta?.observaciones) ? respuesta.observaciones.filter((o) => texto(o)) : [],
  };
}

/**
 * Código 004 "[campo] YA EXISTE UN REGISTRO CON ESE VALOR": si el campo es
 * el código de generación, el documento ya fue recibido (por ejemplo, la
 * respuesta anterior se perdió) y se debe consultar para obtener su sello en
 * lugar de marcarlo rechazado.
 */
function esDuplicado(respuesta) {
  const { codigoMsg, descripcionMsg, observaciones } = detalle(respuesta);
  const mensajes = [descripcionMsg, ...observaciones].filter(Boolean).join(' ').toUpperCase();
  return ['004', '4'].includes(codigoMsg || '') || /YA EXISTE UN REGISTRO/.test(mensajes);
}

/** Resultado de recepción de un DTE: ACEPTADO | RECHAZADO | DUPLICADO | DESCONOCIDO. */
function clasificarRespuestaDte(respuesta) {
  const estado = texto(respuesta?.estado).toUpperCase();
  const selloRecepcion = sello(respuesta);

  if (estado === 'PROCESADO' && selloRecepcion) {
    return { resultado: 'ACEPTADO', estado, selloRecepcion, ...detalle(respuesta) };
  }
  if (estado === 'RECHAZADO') {
    return { resultado: esDuplicado(respuesta) ? 'DUPLICADO' : 'RECHAZADO', estado, selloRecepcion: selloRecepcion || null, ...detalle(respuesta) };
  }
  return {
    resultado: 'DESCONOCIDO',
    estado: estado || null,
    selloRecepcion: selloRecepcion || null,
    motivo: estado === 'PROCESADO' ? 'Respuesta PROCESADO sin sello de recepción' : 'Estado semántico no reconocido',
    ...detalle(respuesta),
  };
}

/**
 * Resultado de la consulta de un DTE (4.3.1): ACEPTADO | NO_ENCONTRADO |
 * RECHAZADO | DESCONOCIDO. "No existe" (código 014 o HTTP 404) significa que
 * Hacienda no recibió el documento y puede reenviarse.
 */
function clasificarConsultaDte({ httpStatus, data } = {}) {
  const estado = texto(data?.estado).toUpperCase();
  const selloRecepcion = sello(data);
  const { codigoMsg, descripcionMsg, observaciones } = detalle(data);
  const mensajes = [descripcionMsg, ...observaciones].filter(Boolean).join(' ').toUpperCase();

  if (estado === 'PROCESADO' && selloRecepcion) {
    return { resultado: 'ACEPTADO', estado, selloRecepcion, codigoMsg, descripcionMsg, fhProcesamiento: texto(data?.fhProcesamiento) || null };
  }
  if (httpStatus === 404 || ['014', '14'].includes(codigoMsg || '') || /NO EXISTE|NO SE ENCONTR/.test(mensajes) || (httpStatus < 300 && !data)) {
    return { resultado: 'NO_ENCONTRADO', estado: estado || null, codigoMsg, descripcionMsg };
  }
  if (estado === 'RECHAZADO') return { resultado: 'RECHAZADO', estado, codigoMsg, descripcionMsg };
  return { resultado: 'DESCONOCIDO', estado: estado || null, codigoMsg, descripcionMsg };
}

/**
 * Resultado de un evento. Invalidación (4.5): PROCESADO + sello. Contingencia
 * (4.4): RECIBIDO + sello. Cualquier otra respuesta no confirma el evento.
 */
function clasificarRespuestaEvento(respuesta, { estadoAceptado }) {
  const estado = texto(respuesta?.estado).toUpperCase();
  const selloRecepcion = sello(respuesta);
  if (estado === estadoAceptado && selloRecepcion) return { resultado: 'ACEPTADO', estado, selloRecepcion, ...detalle(respuesta) };
  if (estado === 'RECHAZADO') return { resultado: 'RECHAZADO', estado, selloRecepcion: null, ...detalle(respuesta) };
  return { resultado: 'DESCONOCIDO', estado: estado || null, selloRecepcion: selloRecepcion || null, ...detalle(respuesta) };
}

module.exports = { clasificarRespuestaDte, clasificarConsultaDte, clasificarRespuestaEvento, esDuplicado };
