const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');

// Modo real de pruebas: lo que DEC-010 agrega para simulated no debe existir aquí.
process.env.DTE_MODE = 'hacienda-test';
require('../_setup');
const { db } = require('../../src/db');

const API_KEY = 'clave-de-prueba-para-tests';
let server;
let baseUrl;

before(async () => {
  const app = require('../../src/app');
  await new Promise((resolve) => {
    server = app.listen(0, () => {
      baseUrl = `http://127.0.0.1:${server.address().port}`;
      resolve();
    });
  });
});

after(() => server?.close());

function headers(extra = {}) {
  return { Authorization: `Bearer ${API_KEY}`, ...extra };
}

test('las rutas de simulación no existen fuera de simulated', async () => {
  const codigo = '00000000-0000-4000-8000-000000000000';
  for (const [method, path] of [
    ['GET', `/api/dte/simulacion/${codigo}/invalidacion`],
    ['POST', `/api/dte/simulacion/${codigo}/anular`],
    ['GET', `/api/dte/simulacion/eventos/${codigo}/json`],
  ]) {
    const response = await fetch(`${baseUrl}${path}`, {
      method,
      headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': 'boundary-simulacion-001' }),
      body: method === 'POST' ? '{}' : undefined,
    });
    assert.equal(response.status, 404, `${method} ${path}`);
    assert.equal((await response.json()).code, 'SIMULATION_ROUTES_DISABLED');
  }
});

test('el header de escenario se rechaza antes de tocar idempotencia, correlativos o identidad', async () => {
  const contar = () => ({
    dtes: db.prepare('SELECT COUNT(*) AS n FROM dtes').get().n,
    claves: db.prepare('SELECT COUNT(*) AS n FROM idempotency_keys').get().n,
    correlativo: db.prepare('SELECT COALESCE(SUM(ultimo), 0) AS n FROM correlativos').get().n,
  });
  const antes = contar();
  for (const [path, escenario] of [['/api/dte/v2/factura', 'success'], ['/api/dte/ccf', 'rejected'], ['/api/dte/00000000-0000-4000-8000-000000000000/anular', 'success']]) {
    const response = await fetch(`${baseUrl}${path}`, {
      method: 'POST',
      headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': `boundary-escenario-${escenario}`, 'X-DTE-Simulation-Scenario': escenario }),
      body: JSON.stringify({ receptor: null, items: [{ descripcion: 'X', cantidad: 1, precioUni: 10, ventaGravada: 10 }] }),
    });
    assert.equal(response.status, 400, path);
    assert.equal((await response.json()).code, 'SIMULATION_SCENARIO_NOT_ALLOWED');
  }
  assert.deepEqual(contar(), antes);
});

test('el health informa la simulación apagada y el bloqueo de egress inactivo', async () => {
  const health = await (await fetch(`${baseUrl}/api/health`)).json();
  assert.equal(health.dteMode, 'hacienda-test');
  assert.equal(health.simulatedFiscalEventsEnabled, false);
  assert.equal(health.egressGuard, 'inactive');
  assert.equal(health.blockedExternalCalls, 0);
  assert.notEqual(http.request.name, 'guardado', 'http.request no debe estar envuelto fuera de simulated');
});
