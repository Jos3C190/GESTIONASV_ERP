const app = require('./app');
const config = require('./config');
const logger = require('./utils/logger');
const retryQueue = require('./services/retryQueue');
const contingenciaService = require('./services/contingenciaService');
const correlativoStore = require('./services/correlativoStore');
const { db, obtenerSiguienteCorrelativo } = require('./db');

// IMPORTANTE: conecta el store de correlativos (usado por los dteBuilder*)
// con la implementación real respaldada en SQLite. Sin esto, el servidor
// usaría el proveedor en memoria por defecto (solo pensado para tests) y
// los correlativos se perderían en cada reinicio — nunca haría esto en
// producción sin este cableo.
correlativoStore.usar(obtenerSiguienteCorrelativo);

const server = app.listen(config.server.port, () => {
  logger.info(`Microservicio DTE escuchando en puerto ${config.server.port} (ambiente MH: ${config.emisor.ambiente})`);
  if (config.dteMode !== 'simulated' && config.security.apiKeyRecords.some((registro) => registro.scopes.includes('simulate'))) {
    // Sin efecto (las rutas de simulación no existen en este modo), pero indica una configuración mezclada.
    logger.warn(`Una API key tiene el scope simulate con DTE_MODE=${config.dteMode}; ese scope solo sirve en modo simulated`);
  }
});

// Worker cada 15 s: cola de reintentos (consultar/reenviar) y contingencia
// (sondeo de recuperación, Evento de Contingencia y cierre de ventanas). Un
// ciclo no empieza mientras el anterior sigue en curso.
const INTERVALO_MS = 15000;
let cicloEnCurso = false;
const intervaloReintentos = setInterval(() => {
  if (cicloEnCurso || config.dteMode === 'simulated') return;
  cicloEnCurso = true;
  retryQueue.procesarCola()
    .catch((err) => logger.error({ err }, 'Error procesando cola de reintentos'))
    .then(() => contingenciaService.procesar())
    .catch((err) => logger.error({ err }, 'Error procesando la contingencia'))
    .finally(() => { cicloEnCurso = false; });
}, INTERVALO_MS);

// ============================================================================
// Cierre ordenado (graceful shutdown)
// ============================================================================
// Sin esto, un `docker stop`/reinicio del contenedor (que manda SIGTERM) mata
// el proceso de golpe: puede cortar una petición HTTP a medias (ej. justo
// después de firmar pero antes de que la respuesta llegue al cliente, que
// entonces reintentaría y podría duplicar el DTE) y deja el archivo SQLite
// sin cerrar limpiamente.
let cerrando = false;

async function apagarOrdenadamente(señal) {
  if (cerrando) return; // ignora una segunda señal mientras ya se está cerrando
  cerrando = true;
  logger.info(`Señal ${señal} recibida, iniciando cierre ordenado...`);

  clearInterval(intervaloReintentos);

  // Si el cierre ordenado se cuelga (ej. una petición que nunca termina),
  // no te quedes esperando para siempre: fuerza la salida a los 10s.
  const timeoutForzado = setTimeout(() => {
    logger.error('El cierre ordenado no terminó a tiempo (10s); forzando salida');
    process.exit(1);
  }, 10000);
  timeoutForzado.unref(); // no mantiene el proceso vivo solo por este timer

  server.close((err) => {
    if (err) logger.error({ err }, 'Error al cerrar el servidor HTTP');
    else logger.info('Servidor HTTP cerrado (dejó de aceptar conexiones nuevas)');

    try {
      db.close();
      logger.info('Conexión a SQLite cerrada correctamente');
    } catch (errDb) {
      logger.error({ err: errDb }, 'Error al cerrar la conexión a SQLite');
    }

    clearTimeout(timeoutForzado);
    logger.info('Cierre ordenado completo');
    process.exit(0);
  });
}

process.on('SIGTERM', () => apagarOrdenadamente('SIGTERM'));
process.on('SIGINT', () => apagarOrdenadamente('SIGINT'));

// ============================================================================
// Errores no manejados a nivel de proceso
// ============================================================================
// Sin esto, una excepción async sin capturar (ej. un .then() sin .catch())
// puede tumbar el proceso sin dejar ningún rastro útil en el log, o peor,
// dejarlo corriendo en un estado indefinido. Se registra con detalle y se
// cierra el proceso a propósito — seguir corriendo después de una excepción
// no capturada es más riesgoso que reiniciar limpio (Docker/PM2/systemd
// deberían tener configurado el reinicio automático del contenedor/proceso).
process.on('uncaughtException', (err) => {
  logger.fatal({ err: err.message, stack: err.stack }, 'Excepción no capturada — el proceso va a cerrar');
  process.exit(1);
});

process.on('unhandledRejection', (reason) => {
  logger.fatal({ reason: reason instanceof Error ? reason.message : reason }, 'Promise rechazada sin manejar — el proceso va a cerrar');
  process.exit(1);
});

module.exports = server;
