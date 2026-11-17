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

module.exports = router;
