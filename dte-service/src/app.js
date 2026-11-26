const express = require('express');
const helmet = require('helmet');
const pinoHttp = require('pino-http');
const logger = require('./utils/logger');
const config = require('./config');
const egressGuard = require('./services/egressGuard');
const dteRoutes = require('./routes/dte.routes');
const contingenciaRoutes = require('./routes/contingencia.routes');
const healthRoutes = require('./routes/health.routes');
const catalogosRoutes = require('./routes/catalogos.routes');
const apiKeyAuth = require('./middleware/apiKeyAuth');
const rateLimiter = require('./middleware/rateLimiter');
const { rechazarEscenarioNoAdmitido } = require('./middleware/escenarioSimulacion');
const { relojDemostracion } = require('./middleware/relojDemostracion');
const { contextoEmisor, emisorSolicitud } = require('./middleware/emisorSolicitud');

// En simulated ninguna conexión saliente es legítima (DEC-010, plan §7).
if (config.dteMode === 'simulated') egressGuard.activar();

const app = express();

app.use(helmet());
app.use(express.json({ limit: '2mb' }));
app.use(pinoHttp({ logger }));

// /api/health queda público a propósito (health checks de infraestructura,
// balanceadores de carga, Docker healthcheck, etc. normalmente no mandan
// credenciales). No expone nada sensible.
app.use('/api', healthRoutes);

// Todo lo demás requiere API key y respeta el límite de peticiones (el
// orden importa: primero se autentica, LUEGO se limita por esa identidad).
// Antes de las rutas /:codigoGeneracion para que "contingencia" no se tome como un código.
app.use('/api/dte/contingencia', apiKeyAuth, rateLimiter, emisorSolicitud, rechazarEscenarioNoAdmitido, contingenciaRoutes);
// Estado y prueba de la conexión con Hacienda (mejora 14), sin secretos.
app.use('/api/dte/conexion-hacienda', apiKeyAuth, rateLimiter, rechazarEscenarioNoAdmitido, require('./routes/conexion.routes'));
// La invalidación simulada solo existe en simulated; en otro modo la ruta no
// se monta y responde 404 para que nunca alcance el router real.
if (config.dteMode === 'simulated') {
  app.use('/api/dte/simulacion', apiKeyAuth, rateLimiter, emisorSolicitud, rechazarEscenarioNoAdmitido, require('./routes/simulacion.routes'));
} else {
  app.use('/api/dte/simulacion', (req, res) => {
    res.status(404).json({ error: 'Las rutas de simulación solo existen con DTE_MODE=simulated', code: 'SIMULATION_ROUTES_DISABLED' });
  });
}
// Registro de emisores (multiemisor): lo administra el ERP con el alcance `issuers`.
app.use('/api/emisores', apiKeyAuth, rateLimiter, require('./routes/emisores.routes'));
app.use('/api/dte', apiKeyAuth, rateLimiter, emisorSolicitud, contextoEmisor, rechazarEscenarioNoAdmitido, relojDemostracion, dteRoutes);
app.use('/api/catalogos', apiKeyAuth, rateLimiter, catalogosRoutes);

// Manejador de errores centralizado
app.use((err, req, res, next) => {
  req.log?.error(err);
  res.status(500).json({ error: 'Error interno del microservicio' });
});

module.exports = app;
