const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
require('../setup-env');

const raiz = path.join(__dirname, '..', '..');

describe('invalidación simulada: aislamiento de los clientes de Hacienda (DEC-010)', () => {
  it('las rutas y el proveedor simulados no cargan haciendaClient, firmadorClient ni authService', () => {
    const script = `
      require('./test/setup-env');
      require('./src/routes/simulacion.routes');
      require('./src/services/egressGuard');
      const cargados = Object.keys(require.cache)
        .filter((archivo) => /(haciendaClient|firmadorClient|authService)\\.js$/.test(archivo))
        .map((archivo) => require('node:path').basename(archivo));
      process.stdout.write(JSON.stringify(cargados));
    `;
    const salida = execFileSync(process.execPath, ['-e', script], {
      cwd: raiz,
      env: {
        ...process.env,
        DTE_MODE: 'simulated',
        DTE_SIMULATION_ACKNOWLEDGED: 'true',
        DTE_SIMULATION_SQLITE_PATH: ':memory:',
        LOG_LEVEL: 'silent',
      },
      encoding: 'utf8',
    });
    assert.deepEqual(JSON.parse(salida), []);
  });
});

describe('egressGuard.esLoopback', () => {
  const { esLoopback } = require('../../src/services/egressGuard');

  it('acepta solo destinos de loopback', () => {
    for (const host of ['localhost', '127.0.0.1', '127.5.0.9', '::1', '[::1]', '::ffff:127.0.0.1', 'LOCALHOST']) {
      assert.equal(esLoopback(host), true, host);
    }
    for (const host of ['apitest.dtes.mh.gob.sv', 'api.dtes.mh.gob.sv', '10.0.0.5', '0.0.0.0', 'localhost.evil.test', '128.0.0.1', '', undefined]) {
      assert.equal(esLoopback(host), false, String(host));
    }
  });
});
