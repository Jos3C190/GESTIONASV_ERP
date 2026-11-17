const express = require('express');
const { db } = require('../db');
const { requireDteScope } = require('../middleware/apiKeyAuth');
const conIdempotencia = require('../middleware/conIdempotencia');
const { escenarioSimulacion } = require('../middleware/escenarioSimulacion');
const proveedor = require('../services/simulatedInvalidationProvider');
const { generarPDFEventoInvalidacion } = require('../services/representacionEventoInvalidacionBuilder');
const { leerLogoPdf } = require('../utils/logoPdf');
const config = require('../config');
const logger = require('../utils/logger');

/**
 * Rutas de la invalidación SIMULADA (DEC-010). app.js las monta en
 * /api/dte/simulacion solo con DTE_MODE=simulated; en cualquier otro modo
 * responden 404. POST /api/dte/:codigo/anular sigue devolviendo 409 en
 * simulado: la invalidación ante Hacienda nunca se reutiliza aquí.
 */
const router = express.Router();

function normalizarMotivo(motivo) {
  if (!motivo || typeof motivo !== 'object') return motivo;
  return {
    tipoAnulacion: motivo.tipoAnulacion,
    motivoAnulacion: motivo.motivoAnulacion ?? null,
    responsable: motivo.responsable,
    solicitante: motivo.solicitante,
  };
}

function leerDte(codigoGeneracion) {
  return db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(codigoGeneracion);
}

router.get('/:codigoGeneracion/invalidacion', requireDteScope('simulate'), (req, res) => {
  const row = leerDte(req.params.codigoGeneracion);
  if (!row) return res.status(404).json({ error: 'DTE no encontrado' });
  if (row.estado !== 'SIMULADO' || !proveedor.esDocumentoSimulado(row)) {
    return res.status(409).json({ error: `El DTE no se puede invalidar en simulación en estado ${row.estado}`, code: 'DTE_NOT_INVALIDATABLE', estado: row.estado });
  }
  res.json(proveedor.vistaPrevia(row));
});

router.post(
  '/:codigoGeneracion/anular',
  requireDteScope('simulate'),
  escenarioSimulacion('invalidacion'),
  conIdempotencia(async (req) => {
    const row = leerDte(req.params.codigoGeneracion);
    if (!row) return { status: 404, body: { error: 'DTE no encontrado localmente' } };
    if (!proveedor.esDocumentoSimulado(row)) {
      return { status: 409, body: { error: 'Solo se invalidan en simulación documentos SIMULADO', code: 'DTE_NOT_INVALIDATABLE' } };
    }

    const escenario = req.dteSimulationScenario;
    const identidad = req.dteIdempotency?.codigoGeneracion;
    if (identidad) {
      const evento = proveedor.leerEvento(identidad);
      if (!evento || evento.tipo !== 'INVALIDACION' || evento.modo_emision !== 'SIMULATED' || evento.dte_codigo_generacion !== row.codigo_generacion) {
        return {
          status: 409,
          body: { error: 'La identidad idempotente no corresponde a un evento simulado de este DTE', code: 'DTE_IDENTITY_REQUIRES_RECONCILIATION' },
        };
      }
      return proveedor.aplicar(evento.codigo_generacion, { escenario });
    }

    const { evento, respuesta } = proveedor.preparar({
      row,
      motivo: normalizarMotivo(req.body?.motivo),
      codigoGeneracionReemplazo: req.body?.codigoGeneracionReemplazo ?? null,
      claveIdempotencia: req.dteIdempotency?.clave,
    });
    if (respuesta) return respuesta;
    return proveedor.aplicar(evento.codigo_generacion, { escenario });
  })
);

router.get('/eventos/:codigoGeneracion/json', requireDteScope('simulate'), (req, res) => {
  const evento = proveedor.leerEvento(req.params.codigoGeneracion);
  if (!evento || evento.modo_emision !== 'SIMULATED') return res.status(404).json({ error: 'Evento simulado no encontrado' });
  const archivo = proveedor.archivoEvento(evento);
  if (!archivo) return res.status(409).json({ error: 'El evento simulado no está aplicado', estado: evento.estado });
  res.setHeader('X-DTE-Issuance-Mode', 'simulated');
  res.type('application/json').send(JSON.stringify(archivo));
});

/** PDF del evento simulado, con la marca SIN VALIDEZ FISCAL. */
router.post('/eventos/:codigoGeneracion/pdf/render', requireDteScope('simulate'), async (req, res) => {
  const evento = proveedor.leerEvento(req.params.codigoGeneracion);
  if (!evento || evento.tipo !== 'INVALIDACION' || evento.modo_emision !== 'SIMULATED') {
    return res.status(404).json({ error: 'Evento simulado no encontrado' });
  }
  const archivo = proveedor.archivoEvento(evento);
  if (!archivo) return res.status(409).json({ error: 'El evento simulado no está aplicado', estado: evento.estado });
  const { logoPngBuffer, error: errorLogo } = leerLogoPdf(req.body);
  if (errorLogo) return res.status(422).json({ error: errorLogo });
  try {
    const bytes = await generarPDFEventoInvalidacion(archivo, { simulation: true, watermark: config.simulation.watermark, logoPngBuffer });
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('X-DTE-Issuance-Mode', 'simulated');
    return res.status(200).send(bytes);
  } catch (err) {
    logger.error({ err: err.message, codigoGeneracion: evento.codigo_generacion }, 'Fallo al generar el PDF del evento simulado');
    return res.status(500).json({ error: 'No se pudo generar la representación gráfica del evento simulado' });
  }
});

module.exports = router;
