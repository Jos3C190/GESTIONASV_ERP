const express = require('express');
const { db } = require('../db');
const config = require('../config');
const egressGuard = require('../services/egressGuard');
const router = express.Router();

/**
 * Antes esto solo confirmaba "el proceso está vivo" (siempre respondía
 * "ok" sin comprobar nada). Ahora verifica que SQLite responda de verdad —
 * la dependencia más crítica y más barata de chequear en cada request. NO
 * verifica el firmador ni Hacienda a propósito: son llamadas de red lentas
 * y este endpoint lo consultan probes de infraestructura cada pocos
 * segundos; si Hacienda está caída eso NO significa que este microservicio
 * esté "no saludable" (para eso existe el estado CONTINGENCIA, que es una
 * situación esperada y manejada, no una falla del propio servicio).
 */
router.get('/health', (req, res) => {
  const egress = egressGuard.estado();
  const salud = {
    status: 'ok',
    timestamp: new Date().toISOString(),
    dteMode: config.dteMode,
    haciendaCallsEnabled: config.dteMode !== 'simulated',
    firmadorEnabled: config.dteMode !== 'simulated',
    simulatedFiscalEventsEnabled: config.dteMode === 'simulated',
    egressGuard: egress.activo ? 'active' : 'inactive',
    blockedExternalCalls: egress.bloqueadas,
    checks: {},
  };

  try {
    db.prepare('SELECT 1').get();
    salud.checks.sqlite = 'ok';
  } catch (err) {
    salud.checks.sqlite = 'error';
    salud.status = 'degraded';
  }

  const codigo = salud.status === 'ok' ? 200 : 503;
  res.status(codigo).json(salud);
});

module.exports = router;
