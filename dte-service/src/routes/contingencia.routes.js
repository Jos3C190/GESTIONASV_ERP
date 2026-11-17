const express = require('express');
const config = require('../config');
const contingenciaService = require('../services/contingenciaService');
const { requireDteScope } = require('../middleware/apiKeyAuth');
const { TIPO_DOCUMENTO_IDENTIFICACION } = require('../config/catalogs');

/**
 * Operación en contingencia (Manual Funcional VIII). Todas las acciones
 * requieren el scope `contingency`; el modo simulado no opera contingencias.
 */
const router = express.Router();

function manejar(accion) {
  return async (req, res) => {
    if (config.dteMode === 'simulated') {
      return res.status(409).json({ error: 'El modo simulado no opera contingencias ante Hacienda', code: 'CONTINGENCY_SIMULATED' });
    }
    try {
      const { status = 200, body } = await accion(req);
      return res.status(status).json(body);
    } catch (error) {
      if (error instanceof contingenciaService.ContingenciaError) {
        return res.status(error.status).json({ error: error.message, code: error.code });
      }
      throw error;
    }
  };
}

function responsableDeSolicitud(body) {
  const responsable = body?.responsable;
  if (!responsable) return undefined;
  const tipoDocumento = String(responsable.tipoDocumento ?? '').trim();
  if (!Object.values(TIPO_DOCUMENTO_IDENTIFICACION).includes(tipoDocumento)) {
    throw new contingenciaService.ContingenciaError('Tipo de documento del responsable fuera de CAT-022', 'INVALID_CONTINGENCY_REQUEST', 400);
  }
  return {
    nombre: String(responsable.nombre ?? '').trim(),
    tipoDocumento,
    numeroDocumento: String(responsable.numeroDocumento ?? '').trim(),
  };
}

function idDeVentana(req) {
  const id = Number.parseInt(req.params.id, 10);
  if (!Number.isInteger(id) || id <= 0) throw new contingenciaService.ContingenciaError('Contingencia no encontrada', 'CONTINGENCY_NOT_FOUND', 404);
  return id;
}

/** Ventanas activas, por informar o recientes, con sus plazos de 24 h y 72 h. */
router.get('/', requireDteScope('contingency'), manejar(async () => ({ body: contingenciaService.estadoGeneral() })));

/** Abre una contingencia forzada (solo pruebas de certificación en hacienda-test). */
router.post('/forzar', requireDteScope('contingency'), manejar(async (req) => ({
  status: 201,
  body: contingenciaService.forzar({ tipoContingencia: req.body?.tipoContingencia, motivoContingencia: req.body?.motivoContingencia ?? null }),
})));

/** Cierra la ventana (fin de la causa) y, si hay responsable, informa el evento. */
router.post('/:id/cerrar', requireDteScope('contingency'), manejar(async (req) => {
  const id = idDeVentana(req);
  contingenciaService.cerrar(id);
  const responsable = responsableDeSolicitud(req.body) ?? config.contingencia.responsable;
  if (!responsable) return { body: contingenciaService.estadoGeneral().ventanas.find((ventana) => ventana.id === id) };
  return { body: await contingenciaService.enviarEvento(id, { responsable }) };
}));

/** Envía (o reenvía) el Evento de Contingencia de una ventana cerrada. */
router.post('/:id/evento', requireDteScope('contingency'), manejar(async (req) => {
  const responsable = responsableDeSolicitud(req.body) ?? config.contingencia.responsable;
  return { body: await contingenciaService.enviarEvento(idDeVentana(req), { responsable }) };
}));

/** Encola la transmisión de los documentos informados que siguen pendientes. */
router.post('/:id/transmitir', requireDteScope('contingency'), manejar(async (req) => ({
  body: contingenciaService.transmitirPendientes(idDeVentana(req)),
})));

module.exports = router;
