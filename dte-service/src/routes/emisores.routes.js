/**
 * Registro de emisores (alcance `issuers`). Lo usa el ERP para dar de alta,
 * actualizar o desactivar cada empresa como emisor.
 */
const express = require('express');
const { requireDteScope } = require('../middleware/apiKeyAuth');
const issuerRegistry = require('../services/issuerRegistry');
const issuerCredentials = require('../services/issuerCredentials');

const router = express.Router();

function responder(res, fn) {
  try {
    return fn();
  } catch (error) {
    if (error instanceof issuerRegistry.IssuerError || error instanceof issuerCredentials.CredentialsError) {
      return res.status(error.status).json({ error: error.message, code: error.code });
    }
    throw error;
  }
}

router.get('/', requireDteScope('issuers'), (req, res) => {
  res.json({ emisores: issuerRegistry.listar() });
});

router.get('/:nit', requireDteScope('issuers'), (req, res) => {
  const registro = issuerRegistry.obtener(req.params.nit);
  if (!registro) return res.status(404).json({ error: 'Emisor no registrado', code: 'ISSUER_NOT_FOUND' });
  return res.json(registro);
});

router.put('/:nit', requireDteScope('issuers'), (req, res) =>
  responder(res, () => res.json(issuerRegistry.registrar(req.params.nit, req.body)))
);

/**
 * Prueba de conexión del emisor (V3d): autenticación con Hacienda y firma de un
 * documento de prueba con su certificado. No emite ni consume números de control.
 */
router.post('/:nit/probar', requireDteScope('issuers'), async (req, res) => {
  try {
    return res.json(await require('../services/issuerConnectionTest').probar(issuerRegistry.normalizarNit(req.params.nit)));
  } catch (error) {
    if (error instanceof issuerRegistry.IssuerError) {
      return res.status(error.status).json({ error: error.message, code: error.code });
    }
    throw error;
  }
});

/**
 * Contingencia por emisor y establecimiento (V4a), alcance `contingency`. El ERP
 * la consulta y la opera por empresa; cada ventana es de un establecimiento.
 */
const contingenciaService = require('../services/contingenciaService');
const issuerContext = require('../services/issuerContext');

function conContingencia(accion) {
  return async (req, res) => {
    const registro = issuerRegistry.obtener(req.params.nit);
    if (!registro) return res.status(404).json({ error: 'Emisor no registrado', code: 'ISSUER_NOT_FOUND' });
    try {
      const { status = 200, body } = await issuerContext.conEmisor(registro.nit, () => accion(req, registro));
      return res.status(status).json(body);
    } catch (error) {
      if (error instanceof contingenciaService.ContingenciaError) {
        return res.status(error.status).json({ error: error.message, code: error.code });
      }
      throw error;
    }
  };
}

function idDeVentana(req, registro) {
  const id = Number.parseInt(req.params.id, 10);
  if (!Number.isInteger(id) || id <= 0) {
    throw new contingenciaService.ContingenciaError('Contingencia no encontrada', 'CONTINGENCY_NOT_FOUND', 404);
  }
  return contingenciaService.ventanaDeEmisor(registro.nit, id).id;
}

function establecimientoDeSolicitud(body) {
  const establecimiento = typeof body?.establecimiento === 'string' ? body.establecimiento.trim() : '';
  if (!establecimiento || establecimiento.length > 10) {
    throw new contingenciaService.ContingenciaError(
      'Indica el código del establecimiento (hasta 10 caracteres)',
      'INVALID_CONTINGENCY_REQUEST',
      400,
    );
  }
  return establecimiento;
}

/** Ventanas del emisor: activas, por informar o recientes, con sus plazos. */
router.get('/:nit/contingencias', requireDteScope('contingency'), conContingencia(async (req, registro) => ({
  body: contingenciaService.estadoGeneral({ nit: registro.nit }),
})));

/** El operador activa la contingencia de un establecimiento (falla que el servicio no ve). */
router.post('/:nit/contingencias', requireDteScope('contingency'), conContingencia(async (req, registro) => ({
  status: 201,
  body: contingenciaService.forzar({
    clave: { nit: registro.nit, establecimiento: establecimientoDeSolicitud(req.body) },
    tipoContingencia: req.body?.tipoContingencia,
    motivoContingencia: req.body?.motivoContingencia ?? null,
    manual: true,
  }),
})));

/** Cierra la ventana y, si hay responsable (enviado o registrado), informa el evento. */
router.post('/:nit/contingencias/:id/cerrar', requireDteScope('contingency'), conContingencia(async (req, registro) => ({
  body: await contingenciaService.cerrarEInformar(idDeVentana(req, registro), {
    responsable: contingenciaService.responsableDeSolicitud(req.body),
  }),
})));

/** Envía (o reenvía) el Evento de Contingencia de una ventana cerrada. */
router.post('/:nit/contingencias/:id/evento', requireDteScope('contingency'), conContingencia(async (req, registro) => ({
  body: await contingenciaService.enviarEvento(idDeVentana(req, registro), {
    responsable: contingenciaService.responsableDeSolicitud(req.body),
  }),
})));

/** Encola la transmisión de los documentos informados que siguen pendientes. */
router.post('/:nit/contingencias/:id/transmitir', requireDteScope('contingency'), conContingencia(async (req, registro) => ({
  body: contingenciaService.transmitirPendientes(idDeVentana(req, registro)),
})));

module.exports = router;
