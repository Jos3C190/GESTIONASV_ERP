const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { rutaSqlite } = require('../../src/config/sqlitePath');
const config = require('../../src/config');

describe('sqlitePath.js', () => {
  test('hacienda-test y production usan SQLITE_PATH', () => {
    for (const DTE_MODE of ['hacienda-test', 'production']) {
      assert.equal(rutaSqlite({ DTE_MODE, SQLITE_PATH: '/app/data/dte.db', DTE_SIMULATION_SQLITE_PATH: '/app/data/sim.db' }), '/app/data/dte.db');
    }
  });

  test('la simulación usa su propio archivo aunque SQLITE_PATH exista', () => {
    assert.equal(
      rutaSqlite({ DTE_MODE: ' Simulated ', SQLITE_PATH: '/app/data/dte.db', DTE_SIMULATION_SQLITE_PATH: '/app/data/dte-simulation.db' }),
      '/app/data/dte-simulation.db',
    );
  });

  test('valores por defecto relativos al directorio de trabajo', () => {
    assert.equal(rutaSqlite({}), './data/dte.db');
    assert.equal(rutaSqlite({ DTE_MODE: 'simulated' }), './data/dte-simulation.db');
  });

  test('el arranque abre la misma ruta que respalda scripts/backup-sqlite.js', () => {
    assert.equal(config.db.path, rutaSqlite(process.env));
  });
});
