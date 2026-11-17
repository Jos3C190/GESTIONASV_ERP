const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');

process.env.DTE_MODE = 'simulated';
process.env.DTE_SIMULATION_ACKNOWLEDGED = 'true';
process.env.DTE_SIMULATION_SQLITE_PATH = ':memory:';
process.env.DTE_SIMULATION_RUN_ID = 'conexion-simulada';
process.env.DTE_AUTHORIZED_ISSUER_NITS = '06141804941035';
process.env.MS_AUTH_DESHABILITADA = 'false';
require('../_setup');

let servidor;
let baseUrl;
const API = { Authorization: 'Bearer clave-de-prueba-para-tests' };

before(async () => {
  const app = require('../../src/app');
  await new Promise((resolve) => {
    servidor = app.listen(0, '127.0.0.1', () => {
      baseUrl = `http://127.0.0.1:${servidor.address().port}`;
      resolve();
    });
  });
});
after(() => servidor?.close());

test('simulado: la tarjeta lo dice y la prueba no contacta a Hacienda ni al firmador', async () => {
  const egressGuard = require('../../src/services/egressGuard');
  const bloqueadasAntes = egressGuard.estado().bloqueadas;
  const estado = await (await fetch(`${baseUrl}/api/dte/conexion-hacienda`, { headers: API })).json();
  assert.equal(estado.modo, 'simulated');
  assert.equal(estado.ambienteEtiqueta, 'Simulado');
  assert.deepEqual(estado.credenciales, { aplica: false, faltan: [] });
  assert.equal(estado.certificado.estado, 'NO_APLICA');
  assert.equal(estado.nitConfigurado, null);
  const prueba = await fetch(`${baseUrl}/api/dte/conexion-hacienda/probar`, { method: 'POST', headers: API });
  assert.equal(prueba.status, 200);
  const cuerpo = await prueba.json();
  assert.equal(cuerpo.simulado, true);
  assert.equal(cuerpo.mensaje, 'Modo simulado: no hay conexión con Hacienda');
  assert.equal(egressGuard.estado().bloqueadas, bloqueadasAntes, 'ninguna llamada externa');
});
