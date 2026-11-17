const pino = require('pino');
const config = require('../config');

const logger = pino({
  level: config.server.logLevel,
  redact: {
    // Nunca loguear credenciales ni claves privadas
    paths: [
      'req.headers.authorization',
      'req.headers.x-api-key',
      '*.passwordApi',
      '*.passwordPri',
      '*.pwd',
      '*.user',
    ],
    censor: '[REDACTADO]',
  },
});

module.exports = logger;
