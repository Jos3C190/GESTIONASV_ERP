const { db } = require('../db');
const config = require('../config');
const logger = require('../utils/logger');
const { fechaHoraSV, ahora } = require('../utils/fechaHoraSV');
const { fechaDeProcesamiento } = require('../utils/plazosFiscales');
const { validarDte, validarEvento } = require('../validators/dteSchema');
const { sanitizarProfundo } = require('../utils/sanitizarDte');
const { MODELO_FACTURACION, TIPO_TRANSMISION, TIPO_CONTINGENCIA } = require('../config/catalogs');
const { construirEventoContingencia } = require('./eventoContingenciaBuilder');
const firmadorClient = require('./firmadorClient');
const haciendaClient = require('./haciendaClient');
const { clasificarRespuestaEvento, clasificarConsultaDte, esDuplicado } = require('./haciendaResponse');
const { AuthError } = require('./authService');

/**
 * Operación en contingencia (Manual Funcional VIII, Manual Técnico 3.2/4.4).
 *
 * Momento 1: agotada la política de reintentos se abre una ventana y los
 *   documentos pasan a modelo diferido (tipoModelo 2, tipoOperacion 2,
 *   tipoContingencia y motivo de la ventana), con el mismo código, número y
 *   fecha. Mientras la ventana está activa, las emisiones nuevas nacen en
 *   diferido y no se intenta transmitirlas.
 * Momento 2: al restablecerse la comunicación (sondeo) o al cerrar una
 *   ventana forzada, se envía el Evento de Contingencia (máximo 1000
 *   documentos, dentro de las 24 h siguientes al cese) y se exige RECIBIDO
 *   con sello.
 * Momento 3: con el sello del evento, cada documento se transmite uno a uno
 *   dentro de las 72 h siguientes, sin cambiar sus campos de contingencia.
 */
const LIMITE_DOCUMENTOS = 1000;
const ESTADOS_DOCUMENTO_FINALES = ['TRANSMITIDO', 'RECHAZADO', 'INVALIDADO'];
const HORAS_PLAZO_EVENTO = 24;
const HORAS_PLAZO_TRANSMISION = 72;

class ContingenciaError extends Error {
  constructor(mensaje, codigo, status = 409) {
    super(mensaje);
    this.name = 'ContingenciaError';
    this.code = codigo;
    this.status = status;
  }
}

function ahoraIso() {
  return ahora().toISOString();
}

function isoDesdeSqlite(valor) {
  return new Date(`${String(valor).replace(' ', 'T')}Z`).toISOString();
}

function sumarHoras(iso, horas) {
  return new Date(new Date(iso).getTime() + horas * 3600000).toISOString();
}

function leerVentana(id) {
  return db.prepare('SELECT * FROM contingencias WHERE id = ?').get(id);
}

function ventanaActiva() {
  return db.prepare(`SELECT * FROM contingencias WHERE estado = 'ACTIVA'`).get() || null;
}

function ventanaDeDocumento(codigoGeneracion) {
  return db.prepare(
    `SELECT c.* FROM contingencia_documentos d JOIN contingencias c ON c.id = d.contingencia_id
     WHERE d.codigo_generacion = ?`
  ).get(codigoGeneracion) || null;
}

function leerDte(codigoGeneracion) {
  return db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(codigoGeneracion);
}

function leerEvento(codigoGeneracion) {
  return db.prepare('SELECT * FROM eventos WHERE codigo_generacion = ?').get(codigoGeneracion);
}

function validarTipoYMotivo(tipoContingencia, motivo) {
  const tipo = Number(tipoContingencia);
  if (!Object.values(TIPO_CONTINGENCIA).includes(tipo)) {
    throw new ContingenciaError('tipoContingencia inválido (CAT-005)', 'INVALID_CONTINGENCY_REQUEST', 400);
  }
  const texto = typeof motivo === 'string' && motivo.trim() ? motivo.trim() : null;
  if (tipo === TIPO_CONTINGENCIA.OTRO && !texto) {
    throw new ContingenciaError('El tipo 5 (otro) exige describir el motivo de la contingencia', 'INVALID_CONTINGENCY_REQUEST', 400);
  }
  if (texto && texto.length > 500) throw new ContingenciaError('El motivo admite como máximo 500 caracteres', 'INVALID_CONTINGENCY_REQUEST', 400);
  return { tipo, motivo: texto };
}

function abrirVentana({ tipoContingencia, motivo = null, forzada = false, inicio = ahoraIso() }) {
  const datos = validarTipoYMotivo(tipoContingencia, motivo);
  try {
    const { lastInsertRowid } = db.prepare(
      `INSERT INTO contingencias (estado, tipo_contingencia, motivo, forzada, inicio) VALUES ('ACTIVA', ?, ?, ?, ?)`
    ).run(datos.tipo, datos.motivo, forzada ? 1 : 0, inicio);
    const ventana = leerVentana(lastInsertRowid);
    logger.error({ contingencia: ventana.id, tipo: datos.tipo, forzada }, 'Contingencia abierta: los DTE se generan en modelo diferido');
    return ventana;
  } catch (error) {
    // Índice único de ventana activa: otra emisión la abrió al mismo tiempo.
    const activa = ventanaActiva();
    if (activa) return activa;
    throw error;
  }
}

/** Campos de identificación que llevan los documentos generados en la ventana. */
function camposContingencia(ventana) {
  return { tipoContingencia: ventana.tipo_contingencia, motivoContin: ventana.motivo };
}

function cerrarVentana(id, fin = ahoraIso()) {
  const { changes } = db.prepare(
    `UPDATE contingencias SET estado = 'CERRADA', fin = ?, proximo_intento_evento = datetime('now'), actualizado_en = datetime('now')
     WHERE id = ? AND estado = 'ACTIVA'`
  ).run(fin, id);
  if (changes) logger.info({ contingencia: id }, 'Contingencia cerrada; se enviará el Evento de Contingencia');
  return leerVentana(id);
}

/**
 * Asocia un documento a la ventana. El inicio de la contingencia se ajusta al
 * documento más antiguo (con un minuto de margen) para que el periodo del
 * evento cubra su generación. Con 1000 documentos la ventana rota.
 */
function vincular(codigoGeneracion, ventana) {
  db.prepare('INSERT OR IGNORE INTO contingencia_documentos (contingencia_id, codigo_generacion) VALUES (?, ?)').run(ventana.id, codigoGeneracion);
  const dte = leerDte(codigoGeneracion);
  const generado = new Date(new Date(isoDesdeSqlite(dte.creado_en)).getTime() - 60000).toISOString();
  db.prepare(`UPDATE contingencias SET inicio = MIN(inicio, ?), actualizado_en = datetime('now') WHERE id = ?`).run(generado, ventana.id);
  const { total } = db.prepare('SELECT COUNT(*) AS total FROM contingencia_documentos WHERE contingencia_id = ?').get(ventana.id);
  if (total >= LIMITE_DOCUMENTOS && ventana.estado === 'ACTIVA') {
    cerrarVentana(ventana.id);
    abrirVentana({ tipoContingencia: ventana.tipo_contingencia, motivo: ventana.motivo, forzada: Boolean(ventana.forzada) });
  }
}

/** Documento recién emitido mientras la ventana está activa (ya nació en diferido). */
function registrarEmisionEnContingencia(codigoGeneracion, ventana) {
  db.transaction(() => {
    db.prepare(`UPDATE dtes SET estado = 'CONTINGENCIA', actualizado_en = datetime('now') WHERE codigo_generacion = ?`).run(codigoGeneracion);
    vincular(codigoGeneracion, ventana);
  })();
}

/**
 * Convierte a diferido un documento cuya transmisión no se logró. Conserva la
 * versión original por si Hacienda sí la había recibido. Si el firmador no
 * está disponible, el documento se firma antes de informar el evento.
 */
async function convertirADiferido(codigoGeneracion, ventana, observaciones) {
  const row = leerDte(codigoGeneracion);
  const original = JSON.parse(row.payload_json);
  const yaDiferido = original.identificacion.tipoModelo === MODELO_FACTURACION.DIFERIDO;
  const diferido = structuredClone(original);
  if (!yaDiferido) {
    Object.assign(diferido.identificacion, {
      tipoModelo: MODELO_FACTURACION.DIFERIDO,
      tipoOperacion: TIPO_TRANSMISION.CONTINGENCIA,
      ...camposContingencia(ventana),
    });
    const { valido, errores } = validarDte(diferido);
    if (!valido) throw new Error(`El DTE convertido a contingencia no cumple el schema: ${JSON.stringify(errores).slice(0, 300)}`);
  }

  let documentoFirmado = yaDiferido ? row.documento_firmado : null;
  if (!documentoFirmado) {
    try {
      documentoFirmado = await firmadorClient.firmarDocumento(diferido);
    } catch (error) {
      logger.warn({ codigoGeneracion, err: error.message }, 'No se pudo firmar el DTE en contingencia; se firmará antes del evento');
    }
  }

  db.transaction(() => {
    db.prepare(
      `UPDATE dtes SET
         payload_original_json = CASE WHEN ? THEN payload_original_json ELSE COALESCE(payload_original_json, payload_json) END,
         documento_firmado_original = CASE WHEN ? THEN documento_firmado_original ELSE COALESCE(documento_firmado_original, documento_firmado) END,
         payload_json = ?, documento_firmado = ?, estado = 'CONTINGENCIA', observaciones = ?, reenvios = 0,
         actualizado_en = datetime('now')
       WHERE codigo_generacion = ?`
    ).run(yaDiferido ? 1 : 0, yaDiferido ? 1 : 0, JSON.stringify(diferido), documentoFirmado, observaciones, codigoGeneracion);
    vincular(codigoGeneracion, ventana);
  })();
}

/** CAT-005 según la falla: sin DNS o red, el problema es el internet del emisor. */
function tipoSegunFalla(detalle = {}) {
  if (detalle.tipoContingencia) return detalle.tipoContingencia;
  if (/ENOTFOUND|EAI_AGAIN|ENETUNREACH/.test(String(detalle.ultimoError || ''))) return TIPO_CONTINGENCIA.FALLA_INTERNET_EMISOR;
  return config.contingencia.tipoPorDefecto;
}

/**
 * Punto de entrada de la política de reintentos agotada (Manual Técnico 3.3).
 * Un documento ya informado en un evento con sello no abre otra contingencia:
 * se sigue intentando su transmisión dentro del plazo de 72 h.
 */
async function registrarFallaDeConectividad(codigoGeneracion, detalle = {}) {
  const transmisionService = require('./transmisionService');
  const vinculada = ventanaDeDocumento(codigoGeneracion);
  if (vinculada && ['REPORTADA', 'COMPLETADA'].includes(vinculada.estado)) {
    db.prepare(`UPDATE dtes SET estado = 'CONTINGENCIA_REPORTADA', reenvios = 0, actualizado_en = datetime('now') WHERE codigo_generacion = ?`)
      .run(codigoGeneracion);
    transmisionService.encolar(codigoGeneracion, 'TRANSMITIR', 'CONTINGENCIA', 300);
    return { estado: 'CONTINGENCIA_REPORTADA' };
  }
  if (vinculada) {
    db.prepare(`UPDATE dtes SET estado = 'CONTINGENCIA', actualizado_en = datetime('now') WHERE codigo_generacion = ?`).run(codigoGeneracion);
    return { estado: 'CONTINGENCIA' };
  }

  const dte = leerDte(codigoGeneracion);
  const ventana = ventanaActiva() || abrirVentana({
    tipoContingencia: tipoSegunFalla(detalle),
    inicio: new Date(new Date(isoDesdeSqlite(dte.creado_en)).getTime() - 60000).toISOString(),
  });
  const observaciones = JSON.stringify({ motivo: 'Sin comunicación con Hacienda tras la política de reintentos', detalle, contingencia: ventana.id });
  await convertirADiferido(codigoGeneracion, ventana, observaciones);
  logger.error({ codigoGeneracion, contingencia: ventana.id }, 'DTE en contingencia: Hacienda no respondió tras la política de reintentos');
  return { estado: 'CONTINGENCIA' };
}

let ultimoSondeo = 0;

/** Con una ventana automática activa, comprueba si Hacienda vuelve a responder. */
async function sondearRecuperacion({ forzar = false } = {}) {
  const ventana = ventanaActiva();
  if (!ventana || ventana.forzada) return null;
  if (!forzar && Date.now() - ultimoSondeo < config.contingencia.sondeoMs) return null;
  ultimoSondeo = Date.now();
  const documento = db.prepare(
    `SELECT t.codigo_generacion, t.tipo_dte FROM contingencia_documentos d JOIN dtes t ON t.codigo_generacion = d.codigo_generacion
     WHERE d.contingencia_id = ? ORDER BY t.creado_en LIMIT 1`
  ).get(ventana.id);
  if (!documento) return null;
  try {
    await haciendaClient.consultarDte({ nitEmisor: config.emisor.nit, tdte: documento.tipo_dte, codigoGeneracion: documento.codigo_generacion });
  } catch (error) {
    const sinComunicacion = (error instanceof haciendaClient.HaciendaError && error.transitorio)
      || (error instanceof AuthError && !error.credenciales)
      || !(error instanceof haciendaClient.HaciendaError || error instanceof AuthError);
    if (sinComunicacion) return null;
  }
  return cerrarVentana(ventana.id);
}

function programarReintentoEvento(ventana, mensaje) {
  const intentos = ventana.intentos_evento + 1;
  const segundos = Math.min(1800, 60 * 2 ** Math.min(intentos - 1, 5));
  db.prepare(
    `UPDATE contingencias SET intentos_evento = ?, ultimo_error = ?, proximo_intento_evento = datetime('now', '+' || ? || ' seconds'),
     actualizado_en = datetime('now') WHERE id = ?`
  ).run(intentos, String(mensaje).slice(0, 500), segundos, ventana.id);
}

function documentosDeVentana(ventanaId, estados = null) {
  const filtro = estados ? `AND t.estado IN (${estados.map(() => '?').join(',')})` : '';
  return db.prepare(
    `SELECT t.* FROM contingencia_documentos d JOIN dtes t ON t.codigo_generacion = d.codigo_generacion
     WHERE d.contingencia_id = ? ${filtro} ORDER BY t.creado_en`
  ).all(ventanaId, ...(estados || []));
}

/** Documentos convertidos tras intentar el modelo previo: si Hacienda los tenía, se restauran. */
async function reconciliarConvertidos(ventana) {
  const convertidos = documentosDeVentana(ventana.id, ['CONTINGENCIA']).filter((dte) => dte.payload_original_json);
  for (const dte of convertidos) {
    const consulta = clasificarConsultaDte(await haciendaClient.consultarDte({
      nitEmisor: config.emisor.nit, tdte: dte.tipo_dte, codigoGeneracion: dte.codigo_generacion,
    }));
    if (consulta.resultado !== 'ACEPTADO') continue;
    db.transaction(() => {
      db.prepare(
        `UPDATE dtes SET payload_json = payload_original_json, documento_firmado = documento_firmado_original, estado = 'TRANSMITIDO',
           sello_recepcion = ?, fecha_sello = ?, observaciones = ?, actualizado_en = datetime('now')
         WHERE codigo_generacion = ?`
      ).run(consulta.selloRecepcion, fechaDeProcesamiento(consulta.fhProcesamiento) || fechaHoraSV().fecha, JSON.stringify(consulta), dte.codigo_generacion);
      db.prepare('DELETE FROM contingencia_documentos WHERE codigo_generacion = ?').run(dte.codigo_generacion);
    })();
    logger.info({ codigoGeneracion: dte.codigo_generacion }, 'Hacienda ya tenía el DTE: se restaura la versión transmitida y sale de la contingencia');
  }
}

async function asegurarFirmas(ventana) {
  for (const dte of documentosDeVentana(ventana.id, ['CONTINGENCIA']).filter((fila) => !fila.documento_firmado)) {
    const documentoFirmado = await firmadorClient.firmarDocumento(JSON.parse(dte.payload_json));
    db.prepare(`UPDATE dtes SET documento_firmado = ?, actualizado_en = datetime('now') WHERE codigo_generacion = ?`).run(documentoFirmado, dte.codigo_generacion);
  }
}

function periodoDeVentana(ventana) {
  const inicio = fechaHoraSV(new Date(ventana.inicio));
  const fin = fechaHoraSV(new Date(ventana.fin));
  return { fInicio: inicio.fecha, hInicio: inicio.hora, fFin: fin.fecha, hFin: fin.hora };
}

function crearEvento(ventana, documentos, responsable) {
  const primero = JSON.parse(documentos[0].payload_json);
  const { evento, codigoGeneracion } = construirEventoContingencia({
    documentos: documentos.map((dte) => ({ tipoDte: dte.tipo_dte, codigoGeneracion: dte.codigo_generacion })),
    emisor: { ...primero.emisor, numeroControl: primero.identificacion.numeroControl },
    periodo: periodoDeVentana(ventana),
    tipoContingencia: ventana.tipo_contingencia,
    motivoContingencia: ventana.motivo,
    responsable,
    ambiente: primero.identificacion.ambiente,
  });
  const limpio = sanitizarProfundo(evento);
  const { valido, errores } = validarEvento('contingencia', limpio);
  if (!valido) throw new Error(`Evento de contingencia inválido según el schema oficial: ${JSON.stringify(errores).slice(0, 300)}`);
  db.transaction(() => {
    db.prepare(`INSERT INTO eventos (codigo_generacion, tipo, estado, payload_json) VALUES (?, 'CONTINGENCIA', 'PENDIENTE', ?)`)
      .run(codigoGeneracion, JSON.stringify(limpio));
    db.prepare(`UPDATE contingencias SET evento_codigo_generacion = ?, actualizado_en = datetime('now') WHERE id = ?`).run(codigoGeneracion, ventana.id);
  })();
  return leerEvento(codigoGeneracion);
}

function actualizarEvento(codigoGeneracion, cambios) {
  const columnas = Object.keys(cambios);
  db.prepare(`UPDATE eventos SET ${columnas.map((c) => `${c} = ?`).join(', ')}, actualizado_en = datetime('now') WHERE codigo_generacion = ?`)
    .run(...columnas.map((c) => cambios[c]), codigoGeneracion);
}

/**
 * Momento 2: informa la ventana cerrada con un Evento de Contingencia. Es
 * idempotente: reenvía el mismo evento firmado hasta obtener RECIBIDO con
 * sello y, con él, encola la transmisión de cada documento (Momento 3).
 */
async function enviarEvento(ventanaId, { responsable = config.contingencia.responsable } = {}) {
  let ventana = leerVentana(ventanaId);
  if (!ventana) throw new ContingenciaError('Contingencia no encontrada', 'CONTINGENCY_NOT_FOUND', 404);
  if (ventana.estado === 'ACTIVA') {
    throw new ContingenciaError('La contingencia sigue activa: ciérrala cuando se restablezca la comunicación', 'CONTINGENCY_STILL_ACTIVE');
  }
  if (['REPORTADA', 'COMPLETADA'].includes(ventana.estado)) return resumenVentana(ventana);
  if (!responsable) {
    throw new ContingenciaError(
      'Se requiere el responsable del establecimiento (MH_RESPONSABLE_* o en la solicitud) para el evento',
      'CONTINGENCY_RESPONSIBLE_REQUIRED',
      400,
    );
  }

  let evento = ventana.evento_codigo_generacion ? leerEvento(ventana.evento_codigo_generacion) : null;
  try {
    if (!evento || ['RECHAZADO', 'CONCILIACION'].includes(evento.estado)) {
      await reconciliarConvertidos(ventana);
      await asegurarFirmas(ventana);
      const documentos = documentosDeVentana(ventana.id, ['CONTINGENCIA']);
      if (documentos.length === 0) {
        db.prepare(`UPDATE contingencias SET estado = 'COMPLETADA', actualizado_en = datetime('now') WHERE id = ?`).run(ventana.id);
        return resumenVentana(leerVentana(ventana.id));
      }
      evento = crearEvento(ventana, documentos, responsable);
    }
    if (!evento.documento_firmado) {
      const documentoFirmado = await firmadorClient.firmarDocumento(JSON.parse(evento.payload_json));
      actualizarEvento(evento.codigo_generacion, { documento_firmado: documentoFirmado, estado: 'FIRMADO' });
      evento = leerEvento(evento.codigo_generacion);
    }
  } catch (error) {
    programarReintentoEvento(ventana, error.message);
    return { ...resumenVentana(leerVentana(ventana.id)), error: error.message };
  }

  let respuesta;
  try {
    respuesta = await haciendaClient.transmitirContingencia({ nit: config.emisor.nit, documentoFirmado: evento.documento_firmado });
  } catch (error) {
    if (error instanceof haciendaClient.HaciendaError && !error.transitorio) {
      actualizarEvento(evento.codigo_generacion, { estado: 'RECHAZADO', respuesta_json: JSON.stringify({ httpStatus: error.httpStatus, respuesta: error.haciendaResponse }) });
      db.prepare(`UPDATE contingencias SET ultimo_error = ?, proximo_intento_evento = NULL, actualizado_en = datetime('now') WHERE id = ?`)
        .run(error.message, ventana.id);
    } else {
      programarReintentoEvento(ventana, error.message);
    }
    return { ...resumenVentana(leerVentana(ventana.id)), error: error.message };
  }

  const clasificacion = clasificarRespuestaEvento(respuesta, { estadoAceptado: 'RECIBIDO' });
  if (clasificacion.resultado === 'ACEPTADO') {
    const transmisionService = require('./transmisionService');
    const documentos = documentosDeVentana(ventana.id, ['CONTINGENCIA']);
    db.transaction(() => {
      actualizarEvento(evento.codigo_generacion, { estado: 'ACEPTADO', sello_recepcion: clasificacion.selloRecepcion, respuesta_json: JSON.stringify(respuesta) });
      db.prepare(
        `UPDATE contingencias SET estado = 'REPORTADA', evento_sello = ?, evento_sello_en = ?, ultimo_error = NULL,
         proximo_intento_evento = NULL, actualizado_en = datetime('now') WHERE id = ?`
      ).run(clasificacion.selloRecepcion, ahoraIso(), ventana.id);
      for (const dte of documentos) {
        db.prepare(`UPDATE dtes SET estado = 'CONTINGENCIA_REPORTADA', reenvios = 0, actualizado_en = datetime('now') WHERE codigo_generacion = ?`)
          .run(dte.codigo_generacion);
        transmisionService.encolar(dte.codigo_generacion, 'TRANSMITIR', 'CONTINGENCIA');
      }
    })();
    logger.info({ contingencia: ventana.id, documentos: documentos.length }, 'Evento de Contingencia recibido; se transmiten los documentos');
    return resumenVentana(leerVentana(ventana.id));
  }

  const mensaje = [clasificacion.descripcionMsg, ...(clasificacion.observaciones || [])].filter(Boolean).join(' | ') || 'Respuesta no concluyente';
  if (clasificacion.resultado === 'RECHAZADO') {
    const estado = esDuplicado(respuesta) ? 'CONCILIACION' : 'RECHAZADO';
    actualizarEvento(evento.codigo_generacion, { estado, respuesta_json: JSON.stringify(respuesta) });
    db.prepare(`UPDATE contingencias SET ultimo_error = ?, proximo_intento_evento = NULL, actualizado_en = datetime('now') WHERE id = ?`)
      .run(mensaje.slice(0, 500), ventana.id);
    logger.error({ contingencia: ventana.id, mensaje }, 'Hacienda rechazó el Evento de Contingencia; corrige y reenvía dentro de 24 h');
  } else {
    actualizarEvento(evento.codigo_generacion, { estado: 'SIN_CONFIRMAR', respuesta_json: JSON.stringify(respuesta) });
    programarReintentoEvento(ventana, mensaje);
  }
  return { ...resumenVentana(leerVentana(ventana.id)), error: mensaje };
}

/** Encola la transmisión de los documentos ya informados que siguen pendientes. */
function transmitirPendientes(ventanaId) {
  const ventana = leerVentana(ventanaId);
  if (!ventana) throw new ContingenciaError('Contingencia no encontrada', 'CONTINGENCY_NOT_FOUND', 404);
  if (!['REPORTADA', 'COMPLETADA'].includes(ventana.estado)) {
    throw new ContingenciaError('El evento de contingencia aún no tiene sello de recepción', 'CONTINGENCY_NOT_REPORTED');
  }
  const transmisionService = require('./transmisionService');
  const pendientes = documentosDeVentana(ventana.id, ['CONTINGENCIA_REPORTADA']);
  for (const dte of pendientes) transmisionService.encolar(dte.codigo_generacion, 'TRANSMITIR', 'CONTINGENCIA');
  return { encolados: pendientes.length };
}

function completarVentanas() {
  const reportadas = db.prepare(`SELECT id FROM contingencias WHERE estado = 'REPORTADA'`).all();
  for (const { id } of reportadas) {
    const marcadores = ESTADOS_DOCUMENTO_FINALES.map(() => '?').join(',');
    const { pendientes } = db.prepare(
      `SELECT COUNT(*) AS pendientes FROM contingencia_documentos d JOIN dtes t ON t.codigo_generacion = d.codigo_generacion
       WHERE d.contingencia_id = ? AND t.estado NOT IN (${marcadores})`
    ).get(id, ...ESTADOS_DOCUMENTO_FINALES);
    if (pendientes === 0) {
      db.prepare(`UPDATE contingencias SET estado = 'COMPLETADA', actualizado_en = datetime('now') WHERE id = ?`).run(id);
      logger.info({ contingencia: id }, 'Contingencia completada: todos sus documentos tienen respuesta de Hacienda');
    }
  }
}

/** Ciclo periódico (server.js): sondeo, eventos pendientes y cierre de ventanas. */
async function procesar() {
  await sondearRecuperacion();
  if (config.contingencia.responsable) {
    const listas = db.prepare(
      `SELECT id FROM contingencias WHERE estado = 'CERRADA' AND proximo_intento_evento IS NOT NULL AND proximo_intento_evento <= datetime('now')`
    ).all();
    for (const { id } of listas) {
      try {
        await enviarEvento(id);
      } catch (error) {
        logger.error({ contingencia: id, err: error.message }, 'No se pudo enviar el Evento de Contingencia');
      }
    }
  }
  completarVentanas();
}

/** Contingencia forzada para las pruebas de certificación (solo hacienda-test con permiso explícito). */
function forzar({ tipoContingencia, motivoContingencia = null }) {
  if (!config.contingencia.forzadaPermitida) {
    throw new ContingenciaError('La contingencia forzada solo está disponible en hacienda-test con DTE_ALLOW_FORCED_CONTINGENCY=true', 'CONTINGENCY_FORCE_DISABLED', 403);
  }
  if (ventanaActiva()) throw new ContingenciaError('Ya hay una contingencia activa', 'CONTINGENCY_ALREADY_ACTIVE');
  return resumenVentana(abrirVentana({ tipoContingencia, motivo: motivoContingencia, forzada: true }));
}

function cerrar(ventanaId) {
  const ventana = leerVentana(ventanaId);
  if (!ventana) throw new ContingenciaError('Contingencia no encontrada', 'CONTINGENCY_NOT_FOUND', 404);
  if (ventana.estado !== 'ACTIVA') return resumenVentana(ventana);
  return resumenVentana(cerrarVentana(ventana.id));
}

function resumenVentana(ventana) {
  const documentos = documentosDeVentana(ventana.id);
  const contar = (estados) => documentos.filter((dte) => estados.includes(dte.estado)).length;
  const evento = ventana.evento_codigo_generacion ? leerEvento(ventana.evento_codigo_generacion) : null;
  const ahoraActual = ahoraIso();
  const eventoLimite = ventana.fin ? sumarHoras(ventana.fin, HORAS_PLAZO_EVENTO) : null;
  const transmisionLimite = ventana.evento_sello_en ? sumarHoras(ventana.evento_sello_en, HORAS_PLAZO_TRANSMISION) : null;
  return {
    id: ventana.id,
    estado: ventana.estado,
    tipoContingencia: ventana.tipo_contingencia,
    motivo: ventana.motivo,
    forzada: Boolean(ventana.forzada),
    inicio: ventana.inicio,
    fin: ventana.fin,
    documentos: {
      total: documentos.length,
      enContingencia: contar(['CONTINGENCIA']),
      pendientesDeTransmitir: contar(['CONTINGENCIA_REPORTADA', 'PENDIENTE_RECONCILIACION', 'PENDIENTE_REINTENTO', 'RECONCILIACION']),
      transmitidos: contar(['TRANSMITIDO', 'INVALIDADO']),
      rechazados: contar(['RECHAZADO']),
    },
    evento: evento
      ? { codigoGeneracion: evento.codigo_generacion, estado: evento.estado, selloRecepcion: evento.sello_recepcion, selloEn: ventana.evento_sello_en }
      : null,
    plazos: {
      eventoLimite,
      eventoVencido: Boolean(eventoLimite && !ventana.evento_sello && ahoraActual > eventoLimite),
      transmisionLimite,
      transmisionVencida: Boolean(transmisionLimite && ventana.estado === 'REPORTADA' && ahoraActual > transmisionLimite),
    },
    ultimoError: ventana.ultimo_error,
    proximoIntentoEvento: ventana.proximo_intento_evento,
  };
}

/** Estado para el panel: ventanas abiertas o recientes con plazos. */
function estadoGeneral() {
  const ventanas = db.prepare(
    `SELECT * FROM contingencias WHERE estado <> 'COMPLETADA'
     UNION ALL SELECT * FROM (SELECT * FROM contingencias WHERE estado = 'COMPLETADA' ORDER BY id DESC LIMIT 5)
     ORDER BY id DESC`
  ).all();
  return {
    activa: Boolean(ventanaActiva()),
    forzadaPermitida: config.contingencia.forzadaPermitida,
    responsableConfigurado: Boolean(config.contingencia.responsable),
    ventanas: ventanas.map(resumenVentana),
  };
}

module.exports = {
  ContingenciaError,
  ventanaActiva,
  camposContingencia,
  registrarEmisionEnContingencia,
  registrarFallaDeConectividad,
  sondearRecuperacion,
  enviarEvento,
  transmitirPendientes,
  completarVentanas,
  procesar,
  forzar,
  cerrar,
  estadoGeneral,
  _reiniciarSondeo: () => { ultimoSondeo = 0; },
};
