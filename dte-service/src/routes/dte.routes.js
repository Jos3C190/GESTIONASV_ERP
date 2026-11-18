const issuerRegistry = require('../services/issuerRegistry');
const express = require('express');
const { db } = require('../db');
const { construirFactura, construirCCF } = require('../services/dteBuilder');
const { construirNotaCredito, construirNotaDebito, construirNotaRemision } = require('../services/dteBuilderNotas');
const {
  construirComprobanteRetencion,
  construirComprobanteLiquidacion,
  construirDocumentoContableLiquidacion,
  construirFacturaExportacion,
  construirFacturaSujetoExcluido,
  construirComprobanteDonacion,
} = require('../services/dteBuilderOtros');
const { generarPDF } = require('../services/representacionGraficaBuilder');
const { generarPDFEventoInvalidacion } = require('../services/representacionEventoInvalidacionBuilder');
const { leerLogoPdf } = require('../utils/logoPdf');
const { validarDte } = require('../validators/dteSchema');
const { sanitizarProfundo } = require('../utils/sanitizarDte');
const { fechaHoraSV } = require('../utils/fechaHoraSV');
const { generarNumeroControl, parsearNumeroControl } = require('../utils/numeroControl');
const firmadorClient = require('../services/firmadorClient');
const issuerContext = require('../services/issuerContext');
const { emitirSimulado, rechazoSimulado } = require('../services/simulatedEmissionProvider');
const haciendaClient = require('../services/haciendaClient');
const { AuthError } = require('../services/authService');
const transmisionService = require('../services/transmisionService');
const invalidacionService = require('../services/invalidacionService');
const contingenciaService = require('../services/contingenciaService');
const { clasificarConsultaDte } = require('../services/haciendaResponse');
const { construirArchivoDte } = require('../services/dteArtifact');
const logger = require('../utils/logger');
const { TIPO_DTE, MODELO_FACTURACION } = require('../config/catalogs');
const config = require('../config');
const { requireDteScope } = require('../middleware/apiKeyAuth');

const { asociarIdentidad } = require('../services/idempotency');
const conIdempotencia = require('../middleware/conIdempotencia');
const { escenarioSimulacion } = require('../middleware/escenarioSimulacion');

const router = express.Router();
// Multiemisor: un código de generación de otro emisor responde 404.
router.param('codigoGeneracion', require('../middleware/emisorSolicitud').propietarioDocumento);

function parsearObservaciones(valor) {
  try {
    return JSON.parse(valor || 'null');
  } catch {
    return null;
  }
}

function respuestaPersistidaDte(row) {
  const identidad = { codigoGeneracion: row.codigo_generacion, numeroControl: row.numero_control };
  if (row.estado === 'SIMULADO' && row.simulation_marker) {
    return {
      status: 201,
      body: { ...identidad, estado: 'SIMULADO', simulationMarker: row.simulation_marker, issuanceMode: 'SIMULATED' },
    };
  }
  if (['TRANSMITIDO', 'INVALIDADO'].includes(row.estado) && row.sello_recepcion) {
    return {
      status: 201,
      body: {
        ...identidad,
        estado: row.estado,
        selloRecepcion: row.sello_recepcion,
        respuestaHacienda: parsearObservaciones(row.observaciones) || undefined,
      },
    };
  }
  if (row.estado === 'RECHAZADO' && row.modo_emision === 'SIMULATED') {
    // Rechazo del escenario simulado: nunca se presenta como respuesta de Hacienda.
    return {
      status: 200,
      body: { ...identidad, estado: 'RECHAZADO', selloRecepcion: null, issuanceMode: 'SIMULATED', simulacion: parsearObservaciones(row.observaciones) || undefined },
    };
  }
  if (row.estado === 'RECHAZADO') {
    return {
      status: 200,
      body: {
        ...identidad,
        estado: 'RECHAZADO',
        selloRecepcion: row.sello_recepcion || null,
        respuestaHacienda: parsearObservaciones(row.observaciones) || undefined,
      },
    };
  }
  if (['PENDIENTE_REINTENTO', 'PENDIENTE_RECONCILIACION', 'RECONCILIACION'].includes(row.estado)) {
    return {
      status: 202,
      body: {
        ...identidad,
        estado: row.estado,
        mensaje: 'El documento ya tiene identidad y continúa en la cola de recuperación; no se emitirá otro DTE.',
      },
    };
  }
  if (['CONTINGENCIA', 'CONTINGENCIA_REPORTADA'].includes(row.estado)) {
    return {
      status: 202,
      body: {
        ...identidad,
        estado: row.estado,
        mensaje: 'El documento quedó en contingencia y se transmitirá cuando se restablezca la comunicación con Hacienda.',
      },
    };
  }
  return null;
}

/** Estados con identidad reservada que todavía pueden firmarse o transmitirse. */
const ESTADOS_REANUDABLES = ['PENDIENTE', 'ERROR_FIRMA', 'FIRMADO'];

/**
 * Un documento nunca transmitido que se reanuda otro día conserva su
 * identidad, pero su fecha de emisión debe ser la del envío real: Hacienda
 * solo admite un día de holgura (Manual Técnico 3.1). Si cambió el año, el
 * número de control se reserva en el correlativo del nuevo año. Los
 * documentos en modelo diferido conservan su fecha original (MF VIII).
 */
const actualizarFechaSiCorresponde = db.transaction((row, dte) => {
  if (dte.identificacion.tipoModelo !== MODELO_FACTURACION.PREVIO) return dte;
  const { fecha, hora, anio } = fechaHoraSV();
  if (dte.identificacion.fecEmi === fecha) return dte;

  const actualizado = structuredClone(dte);
  actualizado.identificacion.fecEmi = fecha;
  actualizado.identificacion.horEmi = hora;
  if (Number(dte.identificacion.fecEmi.slice(0, 4)) !== anio) {
    const partes = parsearNumeroControl(dte.identificacion.numeroControl);
    actualizado.identificacion.numeroControl = generarNumeroControl({ ...partes, anio });
  }
  const { valido, errores, schema } = validarDte(actualizado);
  if (!valido) {
    throw Object.assign(new Error('DTE_SCHEMA_INVALID'), {
      respuestaHttp: {
        status: 422,
        body: { error: `DTE inválido según ${schema || 'schema oficial'}`, code: 'DTE_SCHEMA_INVALID', detalles: errores },
      },
    });
  }
  db.prepare(
    `UPDATE dtes SET payload_json = ?, numero_control = ?, documento_firmado = NULL, estado = 'PENDIENTE',
     actualizado_en = datetime('now') WHERE codigo_generacion = ?`
  ).run(JSON.stringify(actualizado), actualizado.identificacion.numeroControl, row.codigo_generacion);
  logger.info({ codigoGeneracion: row.codigo_generacion }, 'Fecha de emisión actualizada antes de firmar un DTE nunca transmitido');
  return actualizado;
});

function respuestaDeTransmision(codigoGeneracion, numeroControl, resultado) {
  const identidad = { codigoGeneracion, numeroControl };
  switch (resultado.estado) {
    case 'TRANSMITIDO':
      return {
        status: 201,
        body: { ...identidad, estado: 'TRANSMITIDO', selloRecepcion: resultado.selloRecepcion, respuestaHacienda: resultado.respuesta },
      };
    case 'RECHAZADO':
      return { status: 200, body: { ...identidad, estado: 'RECHAZADO', selloRecepcion: null, respuestaHacienda: resultado.respuesta } };
    case 'ERROR_CONFIGURACION':
      // El documento sigue FIRMADO; la misma Idempotency-Key lo reanuda al corregir la configuración.
      return { status: 502, body: { ...identidad, estado: 'FIRMADO', error: resultado.mensaje, code: resultado.codigo } };
    default:
      return {
        status: 202,
        body: { ...identidad, estado: resultado.estado, mensaje: resultado.mensaje, respuestaHacienda: resultado.respuesta },
      };
  }
}

/**
 * Flujo común: construir -> validar contra schema oficial -> persistir ->
 * firmar -> transmitir con la política de reintentos del Manual Técnico
 * (transmisionService): sin respuesta se consulta antes de reenviar.
 *
 * Devuelve { status, body } EN VEZ de llamar a res.json() directamente —
 * así el wrapper de idempotencia (más abajo) puede guardar exactamente lo
 * que se respondió, sin importar por cuál rama haya salido esta función.
 */
async function emitir(tipoDte, builderFn, req) {
  const nitEmisor = req.dteIssuerNit ?? req.body?.emisor?.nit ?? config.emisor?.nit ?? null;
  try {
    issuerRegistry.exigirEmision(nitEmisor, tipoDte);
  } catch (error) {
    if (error instanceof issuerRegistry.IssuerError) {
      return { status: error.status, body: { error: error.message, code: error.code, tipoDte } };
    }
    throw error;
  }
  if (!config.security.allowedDocumentTypes.includes(tipoDte)) {
    return {
      status: 403,
      body: {
        error: `El tipo de DTE ${tipoDte} no está habilitado para este emisor`,
        code: 'DTE_DOCUMENT_TYPE_NOT_ALLOWED',
        tipoDte,
      },
    };
  }

  let dte, codigoGeneracion, numeroControl;
  let documentoFirmado = null;
  const identidadExistente = req.dteIdempotency?.codigoGeneracion;
  const escenario = issuerContext.simulado() ? req.dteSimulationScenario : null;
  if (escenario === 'validation-failed' && !identidadExistente) {
    // Escenario simulado (DEC-010): rechazo determinista previo a la identidad,
    // sin reservar correlativo; el backend lo deja en revisión manual.
    return {
      status: 400,
      body: { error: 'Validación rechazada por el escenario simulado validation-failed; no se reservó identidad', code: 'INVALID_DTE_REQUEST', simulacion: { escenario } },
    };
  }
  if (identidadExistente) {
    const row = db.prepare(
      `SELECT codigo_generacion, numero_control, tipo_dte, estado, payload_json, documento_firmado,
              simulation_marker, sello_recepcion, observaciones, modo_emision
       FROM dtes WHERE codigo_generacion = ?`
    ).get(identidadExistente);
    if (!row || row.tipo_dte !== tipoDte) {
      return {
        status: 409,
        body: { error: 'La identidad idempotente no está disponible; requiere conciliación antes de reemitir.', code: 'DTE_IDENTITY_REQUIRES_RECONCILIATION' },
      };
    }
    const resultadoPersistido = respuestaPersistidaDte(row);
    if (resultadoPersistido) return resultadoPersistido;
    if (!ESTADOS_REANUDABLES.includes(row.estado)) {
      return {
        status: 409,
        body: { error: 'El DTE ya tiene una identidad en un estado que requiere conciliación; no se reemitirá.', code: 'DTE_IDENTITY_REQUIRES_RECONCILIATION' },
      };
    }
    codigoGeneracion = row.codigo_generacion;
    const original = JSON.parse(row.payload_json);
    if (issuerContext.simulado()) {
      dte = original;
    } else {
      try {
        dte = actualizarFechaSiCorresponde(row, original);
      } catch (error) {
        if (error?.respuestaHttp) return error.respuestaHttp;
        throw error;
      }
    }
    numeroControl = dte.identificacion.numeroControl;
    // Una firma previa solo sirve si el documento no cambió.
    if (row.estado === 'FIRMADO' && dte === original) documentoFirmado = row.documento_firmado;
  } else {
    try {
      // Con una contingencia activa el documento nace en modelo diferido
      // (Manual Funcional VIII) y no se intenta transmitirlo hasta el evento.
      // La ventana es la del emisor y el establecimiento de la solicitud (V4a);
      // un emisor simulado también la tiene si su operador la activó.
      const ventana = contingenciaService.ventanaActiva({
        nit: issuerContext.actual().nit,
        establecimiento: contingenciaService.establecimientoDeSolicitud(req.body),
      });
      const opcionesBuilder = ventana ? { contingencia: contingenciaService.camposContingencia(ventana) } : {};
      const preparado = db.transaction(() => {
        let construido;
        try {
          construido = builderFn(req.body || {}, opcionesBuilder);
        } catch (errConstruccion) {
          // Lanzar dentro de la transacción revierte cualquier correlativo que
          // se hubiera reservado antes de detectar el error de negocio.
          throw Object.assign(new Error('DTE_PRE_EMISSION_REJECTED'), {
            respuestaHttp: {
              status: 400,
              body: { error: errConstruccion.message, code: errConstruccion.code || 'INVALID_DTE_REQUEST' },
            },
          });
        }

        const dteValidado = sanitizarProfundo(construido.dte);
        const { valido, errores, schema } = validarDte(dteValidado);
        if (!valido) {
          logger.warn({ errorCount: errores.length, codigoGeneracion: construido.codigoGeneracion, schema }, 'DTE no pasó validación contra el schema oficial');
          throw Object.assign(new Error('DTE_SCHEMA_INVALID'), {
            respuestaHttp: {
              status: 422,
              body: { error: `DTE inválido según ${schema || 'schema oficial'}`, code: 'DTE_SCHEMA_INVALID', detalles: errores },
            },
          });
        }

        db.prepare(
          `INSERT INTO dtes (codigo_generacion, numero_control, tipo_dte, estado, payload_json, modo_emision, simulation_run_id, nit)
           VALUES (?, ?, ?, 'PENDIENTE', ?, ?, ?, ?)`
        ).run(
          construido.codigoGeneracion,
          construido.numeroControl,
          tipoDte,
          JSON.stringify(dteValidado),
          issuerContext.actual().modo.toUpperCase().replace('-', '_'),
          issuerContext.simulado() ? config.simulation.runId : null,
          dteValidado.emisor?.nit ?? null,
        );
        asociarIdentidad(req.dteIdempotency?.clave, construido.codigoGeneracion);
        return { ...construido, dte: dteValidado };
      })();
      ({ dte, codigoGeneracion, numeroControl } = preparado);
    } catch (error) {
      if (error?.respuestaHttp) return error.respuestaHttp;
      throw error;
    }
  }

  if (issuerContext.simulado() && escenario === 'rejected') {
    const simulacion = rechazoSimulado();
    db.prepare(
      `UPDATE dtes SET estado = 'RECHAZADO', observaciones = ?, actualizado_en = datetime('now') WHERE codigo_generacion = ?`
    ).run(JSON.stringify(simulacion), codigoGeneracion);
    return {
      status: 200,
      body: { codigoGeneracion, numeroControl, estado: 'RECHAZADO', selloRecepcion: null, issuanceMode: 'SIMULATED', simulacion },
    };
  }

  if (issuerContext.simulado()) {
    const { documentoFirmado: firmaSimulada, simulationMarker } = emitirSimulado(dte);
    db.prepare(
      `UPDATE dtes SET documento_firmado = ?, simulation_marker = ?, estado = 'SIMULADO',
       actualizado_en = datetime('now') WHERE codigo_generacion = ?`
    ).run(firmaSimulada, simulationMarker, codigoGeneracion);
    const ventanaSimulada = dte.identificacion.tipoModelo === MODELO_FACTURACION.DIFERIDO
      ? contingenciaService.ventanaActiva({
        nit: issuerContext.actual().nit,
        establecimiento: contingenciaService.establecimientoDeDte(dte),
      })
      : null;
    if (ventanaSimulada) {
      contingenciaService.registrarEmisionEnContingencia(codigoGeneracion, ventanaSimulada);
      return {
        status: 202,
        body: {
          codigoGeneracion,
          numeroControl,
          estado: 'CONTINGENCIA',
          simulationMarker,
          issuanceMode: 'SIMULATED',
          mensaje: 'Documento simulado generado en contingencia; queda simulado al informar el evento.',
        },
      };
    }
    return {
      status: 201,
      body: { codigoGeneracion, numeroControl, estado: 'SIMULADO', simulationMarker, issuanceMode: 'SIMULATED' },
    };
  }

  if (!documentoFirmado) {
    try {
      documentoFirmado = await firmadorClient.firmarDocumento(dte);
    } catch (errFirma) {
      db.prepare(
        `UPDATE dtes SET estado = 'ERROR_FIRMA', observaciones = ?, actualizado_en = datetime('now')
         WHERE codigo_generacion = ?`
      ).run(errFirma.message, codigoGeneracion);

      return {
        status: 502,
        body: {
          codigoGeneracion,
          numeroControl,
          estado: 'ERROR_FIRMA',
          error: 'Fallo al firmar el documento',
          detalle: errFirma.message,
          // Certificado, contraseña o NIT del firmador: reintentar no lo corrige.
          ...(errFirma.configuracion ? { code: 'FIRMADOR_CONFIGURATION_ERROR' } : {}),
        },
      };
    }

    db.prepare(
      `UPDATE dtes SET documento_firmado = ?, estado = 'FIRMADO', actualizado_en = datetime('now')
       WHERE codigo_generacion = ?`
    ).run(documentoFirmado, codigoGeneracion);
  }

  if (dte.identificacion.tipoModelo === MODELO_FACTURACION.DIFERIDO) {
    const ventana = contingenciaService.ventanaActiva({
      nit: issuerContext.actual().nit,
      establecimiento: contingenciaService.establecimientoDeDte(dte),
    })
      || db.prepare(
        `SELECT c.* FROM contingencia_documentos d JOIN contingencias c ON c.id = d.contingencia_id WHERE d.codigo_generacion = ?`
      ).get(codigoGeneracion);
    if (ventana) {
      contingenciaService.registrarEmisionEnContingencia(codigoGeneracion, ventana);
      return {
        status: 202,
        body: {
          codigoGeneracion,
          numeroControl,
          estado: 'CONTINGENCIA',
          mensaje: 'Documento generado en contingencia (modelo diferido); se transmitirá después del Evento de Contingencia.',
        },
      };
    }
  }

  const resultado = await transmisionService.transmitir(codigoGeneracion);
  return respuestaDeTransmision(codigoGeneracion, numeroControl, resultado);
}

const opcionesRevalidacionFiscal = { revalidarErrorPreIdentidad: true };
router.post('/factura', requireDteScope('issue'), escenarioSimulacion('emision'), conIdempotencia((req) => emitir(TIPO_DTE.FACTURA, (body, opciones) => construirFactura({ ...body, emisor: null }, opciones), req), opcionesRevalidacionFiscal));
router.post('/ccf', requireDteScope('issue'), escenarioSimulacion('emision'), conIdempotencia((req) => emitir(TIPO_DTE.COMPROBANTE_CREDITO_FISCAL, (body, opciones) => construirCCF({ ...body, emisor: null }, opciones), req), opcionesRevalidacionFiscal));
router.post('/v2/factura', requireDteScope('issue'), escenarioSimulacion('emision'), conIdempotencia((req) => emitir(TIPO_DTE.FACTURA, construirFactura, req), opcionesRevalidacionFiscal));
router.post('/v2/ccf', requireDteScope('issue'), escenarioSimulacion('emision'), conIdempotencia((req) => emitir(TIPO_DTE.COMPROBANTE_CREDITO_FISCAL, construirCCF, req), opcionesRevalidacionFiscal));
router.post('/v2/nota-credito', requireDteScope('issue'), escenarioSimulacion('emision'), conIdempotencia((req) => emitir(TIPO_DTE.NOTA_CREDITO, construirNotaCredito, req), opcionesRevalidacionFiscal));
router.post('/nota-remision', requireDteScope('issue'), conIdempotencia((req) => emitir(TIPO_DTE.NOTA_REMISION, construirNotaRemision, req)));
router.post('/nota-credito', requireDteScope('issue'), escenarioSimulacion('emision'), conIdempotencia((req) => emitir(TIPO_DTE.NOTA_CREDITO, (body, opciones) => construirNotaCredito({ ...body, emisor: null }, opciones), req), opcionesRevalidacionFiscal));
router.post('/nota-debito', requireDteScope('issue'), conIdempotencia((req) => emitir(TIPO_DTE.NOTA_DEBITO, construirNotaDebito, req)));
router.post(
  '/comprobante-retencion',
  requireDteScope('issue'),
  conIdempotencia((req) => emitir(TIPO_DTE.COMPROBANTE_RETENCION, construirComprobanteRetencion, req))
);
router.post(
  '/comprobante-liquidacion',
  requireDteScope('issue'),
  conIdempotencia((req) => emitir(TIPO_DTE.COMPROBANTE_LIQUIDACION, construirComprobanteLiquidacion, req))
);
router.post(
  '/documento-contable-liquidacion',
  requireDteScope('issue'),
  conIdempotencia((req) => emitir(TIPO_DTE.DOCUMENTO_CONTABLE_LIQUIDACION, construirDocumentoContableLiquidacion, req))
);
router.post(
  '/factura-exportacion',
  requireDteScope('issue'),
  conIdempotencia((req) => emitir(TIPO_DTE.FACTURA_EXPORTACION, construirFacturaExportacion, req))
);
router.post(
  '/factura-sujeto-excluido',
  requireDteScope('issue'),
  conIdempotencia((req) => emitir(TIPO_DTE.FACTURA_SUJETO_EXCLUIDO, construirFacturaSujetoExcluido, req))
);
router.post(
  '/comprobante-donacion',
  requireDteScope('issue'),
  conIdempotencia((req) => emitir(TIPO_DTE.COMPROBANTE_DONACION, construirComprobanteDonacion, req))
);

/** Consulta el estado local (nuestra BD) de un DTE emitido. */
router.get('/:codigoGeneracion', requireDteScope('read'), (req, res) => {
  const row = db
    .prepare('SELECT codigo_generacion, numero_control, tipo_dte, estado, sello_recepcion, simulation_marker, modo_emision, creado_en FROM dtes WHERE codigo_generacion = ?')
    .get(req.params.codigoGeneracion);

  if (!row) return res.status(404).json({ error: 'DTE no encontrado' });
  res.json(row);
});

/** Devuelve el JSON fiscal que fue validado y transmitido. */
router.get('/:codigoGeneracion/json', requireDteScope('read'), (req, res) => {
  const row = db.prepare('SELECT payload_json, documento_firmado, sello_recepcion, simulation_marker, modo_emision, estado, codigo_generacion, numero_control FROM dtes WHERE codigo_generacion = ?').get(req.params.codigoGeneracion);
  if (!row) return res.status(404).json({ error: 'DTE no encontrado' });
  if (!['TRANSMITIDO', 'SIMULADO', 'CONTINGENCIA', 'CONTINGENCIA_REPORTADA', 'INVALIDADO'].includes(row.estado)) {
    return res.status(409).json({ error: 'El JSON entregable aún no está listo', estado: row.estado });
  }
  if (row.estado === 'TRANSMITIDO' && (!row.sello_recepcion || !String(row.sello_recepcion).trim())) {
    return res.status(409).json({ error: 'El JSON final requiere sello de recepción', estado: row.estado });
  }
  try {
    if (row.estado === 'SIMULADO') res.setHeader('X-DTE-Issuance-Mode', 'simulated');
    res.type('application/json').send(JSON.stringify(construirArchivoDte(row)));
  } catch (err) {
    logger.error({ err: err.message, codigoGeneracion: row.codigo_generacion }, 'No se pudo construir el archivo DTE canónico');
    return res.status(409).json({ error: 'El archivo DTE firmado aún no está completo', estado: row.estado });
  }
});

/** Devuelve el JWS firmado para archivado/auditoría interna. */
router.get('/:codigoGeneracion/documento-firmado', requireDteScope('read'), (req, res) => {
  const row = db.prepare('SELECT documento_firmado, estado FROM dtes WHERE codigo_generacion = ?').get(req.params.codigoGeneracion);
  if (!row) return res.status(404).json({ error: 'DTE no encontrado' });
  if (!row.documento_firmado) return res.status(409).json({ error: 'El documento firmado aún no está listo', estado: row.estado });
  res.json({ documentoFirmado: row.documento_firmado, estado: row.estado });
});

/**
 * Genera y descarga la representación gráfica (PDF) de un DTE.
 * Requiere que ya haya sido TRANSMITIDO (para incluir el sello de recepción
 * real en el documento; un DTE sin sello no debería entregarse al cliente).
 */
/**
 * Render privado con branding visual; no modifica ni vuelve a firmar el DTE.
 * El backend archiva los bytes devueltos y nunca usa el logo vigente para
 * regenerar documentos ya entregados.
 */
/**
 * Sello que lleva la versión legible. En contingencia (V4a del ERP) el cliente
 * recibe el documento antes del sello (Manual Funcional VIII): se indica que está
 * pendiente y el PDF muestra el tipo y el motivo de la contingencia.
 */
const ESTADOS_EN_CONTINGENCIA = ['CONTINGENCIA', 'CONTINGENCIA_REPORTADA'];
const SELLO_PENDIENTE = 'Pendiente: documento generado en contingencia';

function datosRepresentacion(row) {
  const simulation = row.estado === 'SIMULADO' || row.modo_emision === 'SIMULATED';
  if (ESTADOS_EN_CONTINGENCIA.includes(row.estado)) return { simulation, sello: SELLO_PENDIENTE };
  if (!['TRANSMITIDO', 'SIMULADO'].includes(row.estado)) return null;
  return { simulation, sello: row.estado === 'SIMULADO' ? row.simulation_marker : row.sello_recepcion };
}

router.post('/:codigoGeneracion/pdf/render', requireDteScope('read'), async (req, res) => {
  const row = db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(req.params.codigoGeneracion);
  if (!row) return res.status(404).json({ error: 'DTE no encontrado' });
  const representacion = datosRepresentacion(row);
  if (!representacion) {
    return res.status(409).json({ error: `El PDF no está disponible en estado ${row.estado}` });
  }
  const { simulation, sello } = representacion;
  if (typeof sello !== 'string' || !sello.trim()) return res.status(409).json({ error: 'Falta sello o marcador simulado' });
  const { logoPngBuffer, error: errorLogo } = leerLogoPdf(req.body);
  if (errorLogo) return res.status(422).json({ error: errorLogo });
  try {
    const dte = JSON.parse(row.payload_json);
    if (dte.identificacion?.codigoGeneracion !== req.params.codigoGeneracion) {
      return res.status(409).json({ error: 'El código solicitado no coincide con el DTE histórico' });
    }
    const bytes = await generarPDF(dte, {
      selloRecepcion: sello,
      ambiente: dte.identificacion.ambiente,
      simulation,
      watermark: config.simulation.watermark,
      logoPngBuffer,
    });
    res.setHeader('Content-Type', 'application/pdf');
    if (simulation) res.setHeader('X-DTE-Issuance-Mode', 'simulated');
    return res.status(200).send(bytes);
  } catch (err) {
    logger.error({ err: err.message, codigoGeneracion: row.codigo_generacion }, 'Fallo al renderizar PDF con logo');
    return res.status(500).json({ error: 'No se pudo generar la representación gráfica' });
  }
});
router.get('/:codigoGeneracion/pdf', requireDteScope('read'), async (req, res) => {
  const row = db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(req.params.codigoGeneracion);
  if (!row) return res.status(404).json({ error: 'DTE no encontrado' });
  const representacion = datosRepresentacion(row);
  if (!representacion) {
    return res.status(409).json({ error: `El PDF no está disponible en estado ${row.estado}` });
  }
  const { simulation, sello: selloOMarcador } = representacion;
  if (typeof selloOMarcador !== 'string' || !selloOMarcador.trim()) {
    return res.status(409).json({ error: 'El DTE está transmitido pero aún no tiene sello de recepción; el PDF final no está disponible' });
  }

  try {
    const dte = JSON.parse(row.payload_json);
    // El ambiente sale del payload histórico, no de la configuración actual;
    // así cambiar test/prod no altera el QR de un documento ya emitido.
    const pdfBuffer = await generarPDF(dte, {
      selloRecepcion: selloOMarcador,
      ambiente: dte.identificacion.ambiente,
      simulation,
      watermark: config.simulation.watermark,
    });
    res.status(200);
    res.setHeader('Content-Type', 'application/pdf');
    if (simulation) res.setHeader('X-DTE-Issuance-Mode', 'simulated');
    res.setHeader('Content-Disposition', `inline; filename="${simulation ? 'SIMULADO-' : ''}${row.numero_control}.pdf"`);
    res.send(pdfBuffer);
  } catch (err) {
    logger.error({ err: err.message, codigoGeneracion: row.codigo_generacion }, 'Fallo al generar el PDF');
    res.status(500).json({ error: 'No se pudo generar la representación gráfica', detalle: err.message });
  }
});

/**
 * Las consultas a Hacienda (estado de un DTE o de un lote) no existen en modo
 * simulado: se rechazan antes de tocar `haciendaClient`, en vez de fallar por
 * no tener URL configurada.
 */
function responderConsultaSimulada(res) {
  return res.status(409).json({ error: 'El modo simulado no consulta a Hacienda', code: 'HACIENDA_QUERY_SIMULATED' });
}

/**
 * Consulta el resultado de un lote transmitido previamente (modelo en lote).
 * El lote puede traer DTE aceptados y rechazados mezclados: revisar ambos
 * arreglos de la respuesta.
 */
router.get('/lote/:codigoLote', requireDteScope('read'), async (req, res) => {
  if (issuerContext.simulado()) return responderConsultaSimulada(res);
  try {
    const respuesta = await haciendaClient.consultarLoteDte(req.params.codigoLote);
    res.json(respuesta);
  } catch (err) {
    res.status(502).json({ error: 'No se pudo consultar el lote', detalle: err.message });
  }
});

/**
 * Evento de Invalidación de un DTE recibido (Manual Funcional v2.0, VII).
 * El evento se construye con los datos del DTE histórico y se persiste con
 * identidad propia: un reintento con la misma Idempotency-Key reenvía el
 * mismo evento. El DTE pasa a INVALIDADO solo con PROCESADO + sello.
 *
 * Body: {
 *   motivo: { tipoAnulacion: 1|2|3, motivoAnulacion?,
 *             responsable: { nombre, tipoDocumento, numeroDocumento },
 *             solicitante: { nombre, tipoDocumento, numeroDocumento } },
 *   codigoGeneracionReemplazo?: string   // obligatorio en tipos 1 y 3
 * }
 * Se aceptan también los campos planos del contrato anterior
 * (nombreResponsable, tipDocResponsable, numDocResponsable, ...Solicita).
 */
function normalizarMotivo(motivo) {
  if (!motivo || typeof motivo !== 'object') return motivo;
  return {
    tipoAnulacion: motivo.tipoAnulacion,
    motivoAnulacion: motivo.motivoAnulacion ?? null,
    responsable: motivo.responsable ?? {
      nombre: motivo.nombreResponsable, tipoDocumento: motivo.tipDocResponsable, numeroDocumento: motivo.numDocResponsable,
    },
    solicitante: motivo.solicitante ?? {
      nombre: motivo.nombreSolicita, tipoDocumento: motivo.tipDocSolicita, numeroDocumento: motivo.numDocSolicita,
    },
  };
}

router.post(
  '/:codigoGeneracion/anular',
  requireDteScope('invalidate'),
  conIdempotencia(async (req) => {
    if (issuerContext.simulado()) {
      return { status: 409, body: { error: 'Los documentos simulados no se invalidan ante Hacienda' } };
    }
    const row = db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(req.params.codigoGeneracion);
    if (!row) return { status: 404, body: { error: 'DTE no encontrado localmente' } };

    const identidad = req.dteIdempotency?.codigoGeneracion;
    if (identidad) {
      const evento = invalidacionService.leerEvento(identidad);
      if (!evento || evento.tipo !== 'INVALIDACION' || evento.dte_codigo_generacion !== row.codigo_generacion) {
        return {
          status: 409,
          body: { error: 'La identidad idempotente no corresponde a un evento de invalidación de este DTE', code: 'DTE_IDENTITY_REQUIRES_RECONCILIATION' },
        };
      }
      return invalidacionService.transmitir(evento.codigo_generacion);
    }

    const { evento, plazo, respuesta } = invalidacionService.preparar({
      row,
      motivo: normalizarMotivo(req.body?.motivo),
      codigoGeneracionReemplazo: req.body?.codigoGeneracionReemplazo ?? null,
      claveIdempotencia: req.dteIdempotency?.clave,
    });
    if (respuesta) return respuesta;
    return invalidacionService.transmitir(evento.codigo_generacion, { plazo });
  })
);

/** Fecha del evento, plazo y reglas de reemplazo antes de invalidar. */
router.get('/:codigoGeneracion/invalidacion', requireDteScope('read'), (req, res) => {
  const row = db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(req.params.codigoGeneracion);
  if (!row) return res.status(404).json({ error: 'DTE no encontrado' });
  if (row.estado !== 'TRANSMITIDO' || !row.sello_recepcion) {
    return res.status(409).json({ error: `El DTE no se puede invalidar en estado ${row.estado}`, code: 'DTE_NOT_INVALIDATABLE', estado: row.estado });
  }
  res.json(invalidacionService.vistaPrevia(row));
});

/** Eventos fiscales registrados para un DTE. */
router.get('/:codigoGeneracion/eventos', requireDteScope('read'), (req, res) => {
  const eventos = db.prepare(
    `SELECT codigo_generacion, tipo, estado, sello_recepcion, payload_json, creado_en, actualizado_en
     FROM eventos WHERE dte_codigo_generacion = ? ORDER BY creado_en`
  ).all(req.params.codigoGeneracion);
  res.json(eventos.map((evento) => ({
    codigoGeneracion: evento.codigo_generacion,
    tipo: evento.tipo,
    estado: evento.estado,
    selloRecepcion: evento.sello_recepcion,
    fechaEvento: JSON.parse(evento.payload_json).identificacion.fecEmi,
    creadoEn: evento.creado_en,
    actualizadoEn: evento.actualizado_en,
  })));
});

/** Archivo del evento aceptado (JSON firmado + sello) para entregar o archivar. */
router.get('/eventos/:codigoGeneracion/json', requireDteScope('read'), (req, res) => {
  const evento = invalidacionService.leerEvento(req.params.codigoGeneracion);
  if (!evento) return res.status(404).json({ error: 'Evento no encontrado' });
  const archivo = invalidacionService.archivoEvento(evento);
  if (!archivo) return res.status(409).json({ error: 'El evento aún no tiene sello de recepción', estado: evento.estado });
  res.type('application/json').send(JSON.stringify(archivo));
});

/**
 * PDF del evento de invalidación aceptado (representación del JSON sellado,
 * logo opcional como en /pdf/render). El backend archiva los bytes.
 */
router.post('/eventos/:codigoGeneracion/pdf/render', requireDteScope('read'), async (req, res) => {
  const evento = invalidacionService.leerEvento(req.params.codigoGeneracion);
  if (!evento || evento.tipo !== 'INVALIDACION') return res.status(404).json({ error: 'Evento de invalidación no encontrado' });
  const archivo = invalidacionService.archivoEvento(evento);
  if (!archivo) return res.status(409).json({ error: 'El evento aún no tiene sello de recepción', estado: evento.estado });
  const { logoPngBuffer, error: errorLogo } = leerLogoPdf(req.body);
  if (errorLogo) return res.status(422).json({ error: errorLogo });
  try {
    const bytes = await generarPDFEventoInvalidacion(archivo, { logoPngBuffer });
    res.setHeader('Content-Type', 'application/pdf');
    return res.status(200).send(bytes);
  } catch (err) {
    logger.error({ err: err.message, codigoGeneracion: evento.codigo_generacion }, 'Fallo al generar el PDF del evento');
    return res.status(500).json({ error: 'No se pudo generar la representación gráfica del evento' });
  }
});

/**
 * Vuelve a consultar un documento que quedó en RECONCILIACION (respuesta no
 * concluyente o credenciales corregidas). Solo encola una consulta del mismo
 * código: nunca reenvía sin confirmar antes que Hacienda no lo tiene.
 */
router.post('/:codigoGeneracion/reconciliar', requireDteScope('issue'), (req, res) => {
  const row = db.prepare('SELECT estado FROM dtes WHERE codigo_generacion = ?').get(req.params.codigoGeneracion);
  if (!row) return res.status(404).json({ error: 'DTE no encontrado' });
  if (row.estado !== 'RECONCILIACION') {
    return res.status(409).json({ error: `El DTE no está en reconciliación (estado ${row.estado})`, code: 'DTE_NOT_IN_RECONCILIATION', estado: row.estado });
  }
  db.prepare(`UPDATE dtes SET estado = 'PENDIENTE_RECONCILIACION', actualizado_en = datetime('now') WHERE codigo_generacion = ?`)
    .run(req.params.codigoGeneracion);
  transmisionService.encolar(req.params.codigoGeneracion, 'CONSULTAR', 'SIN_RESPUESTA');
  res.status(202).json({ codigoGeneracion: req.params.codigoGeneracion, estado: 'PENDIENTE_RECONCILIACION' });
});

/** Consulta el estado directamente contra Hacienda (fuente de verdad). */
router.get('/:codigoGeneracion/hacienda', requireDteScope('read'), async (req, res) => {
  if (issuerContext.simulado()) return responderConsultaSimulada(res);
  const row = db.prepare('SELECT tipo_dte FROM dtes WHERE codigo_generacion = ?').get(req.params.codigoGeneracion);
  if (!row) return res.status(404).json({ error: 'DTE no encontrado localmente' });

  try {
    // NOTA: el servicio de consulta de Hacienda es POST, no GET
    // (confirmado en Manual Tecnológico v2.0, sección 4.3.1).
    const { httpStatus, data } = await haciendaClient.consultarDte({
      nitEmisor: issuerContext.actual().nit,
      tdte: row.tipo_dte,
      codigoGeneracion: req.params.codigoGeneracion,
    });
    const observaciones = Array.isArray(data?.observaciones) ? data.observaciones.filter((o) => typeof o === 'string' && o.trim()) : [];
    res.json({ ...clasificarConsultaDte({ httpStatus, data }), observaciones, httpStatus, respuestaHacienda: data });
  } catch (err) {
    res.status(502).json({ ...errorConsultaHacienda(err), detalle: err.message });
  }
});

/**
 * Error de una consulta a Hacienda con un código estable para el panel:
 * credenciales rechazadas, Hacienda sin respuesta o solicitud rechazada.
 */
function errorConsultaHacienda(err) {
  if (err instanceof AuthError || err?.tipo === 'AUTENTICACION') {
    return { error: 'Hacienda rechazó las credenciales del sistema', code: 'HACIENDA_AUTH_ERROR' };
  }
  if (err?.tipo === 'SOLICITUD') return { error: 'Hacienda rechazó la consulta', code: 'HACIENDA_REQUEST_REJECTED' };
  return { error: 'Hacienda no respondió', code: 'HACIENDA_UNAVAILABLE' };
}

module.exports = router;
