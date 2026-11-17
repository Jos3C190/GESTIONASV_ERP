const express = require('express');
const { requireDteScope } = require('../middleware/apiKeyAuth');
const conexionHacienda = require('../services/conexionHacienda');

/**
 * Estado de la conexión con Hacienda y prueba de conexión (mejora 14).
 * Montado en /api/dte/conexion-hacienda, antes de las rutas /:codigoGeneracion.
 * Ninguna respuesta incluye credenciales ni contenido del certificado.
 */
const router = express.Router();

router.get('/', requireDteScope('read'), (req, res) => {
  res.json(conexionHacienda.estado());
});

router.post('/probar', requireDteScope('read'), async (req, res) => {
  const { estado, cuerpo } = await conexionHacienda.probarConexion();
  res.status(estado).json(cuerpo);
});

module.exports = router;
