const { describe, it, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const Database = require('better-sqlite3');

const raiz = path.join(__dirname, '..', '..');

/** Abre src/db en un proceso aparte contra `archivo`, como al arrancar el servicio. */
function abrirConElServicio(archivo) {
  execFileSync(process.execPath, ['-e', "require('./test/setup-env'); require('./src/db').db.close()"], {
    cwd: raiz,
    env: { ...process.env, DTE_MODE: 'hacienda-test', SQLITE_PATH: archivo },
    stdio: 'pipe',
  });
}

describe('db/index.js: columnas de eventos para la invalidación simulada (DEC-010)', () => {
  let dir;
  let archivo;

  before(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dte-eventos-'));
    archivo = path.join(dir, 'dte.db');
    // Base como la dejaba el servicio antes de E1: eventos sin simulation_marker ni modo_emision.
    const antigua = new Database(archivo);
    antigua.exec(`
      CREATE TABLE dtes (
        codigo_generacion TEXT PRIMARY KEY,
        numero_control TEXT NOT NULL,
        tipo_dte TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'PENDIENTE',
        payload_json TEXT NOT NULL,
        documento_firmado TEXT,
        sello_recepcion TEXT,
        observaciones TEXT,
        intentos INTEGER NOT NULL DEFAULT 0,
        creado_en TEXT NOT NULL DEFAULT (datetime('now')),
        actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
        modo_emision TEXT NOT NULL DEFAULT 'HACIENDA_TEST'
      );
      CREATE TABLE eventos (
        codigo_generacion TEXT PRIMARY KEY,
        tipo TEXT NOT NULL,
        dte_codigo_generacion TEXT,
        estado TEXT NOT NULL DEFAULT 'PENDIENTE',
        payload_json TEXT NOT NULL,
        documento_firmado TEXT,
        sello_recepcion TEXT,
        respuesta_json TEXT,
        creado_en TEXT NOT NULL DEFAULT (datetime('now')),
        actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (dte_codigo_generacion) REFERENCES dtes(codigo_generacion)
      );
      INSERT INTO dtes (codigo_generacion, numero_control, tipo_dte, estado, payload_json, sello_recepcion, modo_emision)
        VALUES ('DTE-PROD', 'DTE-01-00000000-000000000000001', '01', 'INVALIDADO', '{}', 'SELLO-REAL', 'PRODUCTION');
      INSERT INTO eventos (codigo_generacion, tipo, dte_codigo_generacion, estado, payload_json, sello_recepcion)
        VALUES ('EVT-INVALIDACION', 'INVALIDACION', 'DTE-PROD', 'ACEPTADO', '{}', 'SELLO-EVENTO');
      INSERT INTO eventos (codigo_generacion, tipo, dte_codigo_generacion, estado, payload_json)
        VALUES ('EVT-CONTINGENCIA', 'CONTINGENCIA', NULL, 'ACEPTADO', '{}');
    `);
    antigua.close();
    abrirConElServicio(archivo);
  });

  after(() => {
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it('agrega simulation_marker y modo_emision sin tocar los datos existentes', () => {
    const db = new Database(archivo, { readonly: true });
    const columnas = new Set(db.pragma('table_info(eventos)').map((columna) => columna.name));
    assert.ok(columnas.has('simulation_marker'));
    assert.ok(columnas.has('modo_emision'));

    const invalidacion = db.prepare('SELECT * FROM eventos WHERE codigo_generacion = ?').get('EVT-INVALIDACION');
    assert.equal(invalidacion.estado, 'ACEPTADO');
    assert.equal(invalidacion.sello_recepcion, 'SELLO-EVENTO');
    assert.equal(invalidacion.simulation_marker, null);
    db.close();
  });

  it('hereda el modo del DTE y deja NULL los eventos sin DTE', () => {
    const db = new Database(archivo, { readonly: true });
    const modos = Object.fromEntries(
      db.prepare('SELECT codigo_generacion, modo_emision FROM eventos').all().map((fila) => [fila.codigo_generacion, fila.modo_emision])
    );
    assert.deepEqual(modos, { 'EVT-INVALIDACION': 'PRODUCTION', 'EVT-CONTINGENCIA': null });
    db.close();
  });

  it('es idempotente al volver a arrancar', () => {
    abrirConElServicio(archivo);
    const db = new Database(archivo, { readonly: true });
    const columnas = db.pragma('table_info(eventos)').map((columna) => columna.name);
    assert.equal(columnas.filter((nombre) => nombre === 'modo_emision').length, 1);
    assert.equal(db.prepare('SELECT modo_emision FROM eventos WHERE codigo_generacion = ?').get('EVT-INVALIDACION').modo_emision, 'PRODUCTION');
    db.close();
  });
});
