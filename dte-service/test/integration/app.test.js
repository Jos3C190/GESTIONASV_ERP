/**
 * Tests de integración: requieren las dependencias reales instaladas
 * (`npm install`), a diferencia de test/unit/ que corren con dependencias
 * mínimas. Cubren solo los endpoints de SOLO LECTURA que no dependen de
 * Hacienda ni del firmador (esos requieren credenciales reales y se prueban
 * mejor con scripts/enviar-lote-certificacion.js contra el ambiente de
 * pruebas de verdad).
 */
const { test, describe, before, after } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

// Debe coincidir con MS_API_KEYS definida en test/setup-env.js
const API_KEY = 'clave-de-prueba-para-tests';

let server;
let baseUrl;

function authHeaders(extra = {}) {
  return { Authorization: `Bearer ${API_KEY}`, ...extra };
}

describe('Integración HTTP (requiere npm install)', () => {
  before(async () => {
    const app = require('../../src/app');
    await new Promise((resolve) => {
      server = app.listen(0, () => {
        baseUrl = `http://127.0.0.1:${server.address().port}`;
        resolve();
      });
    });
  });

  after(() => {
    server?.close();
  });

  test('GET /api/health responde 200 SIN necesitar API key (health checks de infraestructura)', async () => {
    const res = await fetch(`${baseUrl}/api/health`);
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.status, 'ok');
    assert.equal(body.checks.sqlite, 'ok');
  });

  test('GET /api/health responde 503 y status "degraded" si SQLite falla', async () => {
    const { db } = require('../../src/db');
    const prepareOriginal = db.prepare.bind(db);
    db.prepare = () => {
      throw new Error('SQLite caída (simulado)');
    };
    try {
      const res = await fetch(`${baseUrl}/api/health`);
      assert.equal(res.status, 503);
      const body = await res.json();
      assert.equal(body.status, 'degraded');
      assert.equal(body.checks.sqlite, 'error');
    } finally {
      db.prepare = prepareOriginal; // restaurar para no afectar otros tests
    }
  });

  describe('apiKeyAuth', () => {
    test('sin ninguna API key, responde 401', async () => {
      const res = await fetch(`${baseUrl}/api/catalogos`);
      assert.equal(res.status, 401);
    });

    test('con una API key incorrecta, responde 401', async () => {
      const res = await fetch(`${baseUrl}/api/catalogos`, { headers: authHeaders({ Authorization: 'Bearer key-incorrecta' }) });
      assert.equal(res.status, 401);
    });

    test('con la API key correcta vía "Authorization: Bearer", responde 200', async () => {
      const res = await fetch(`${baseUrl}/api/catalogos`, { headers: authHeaders() });
      assert.equal(res.status, 200);
    });

    test('con la API key correcta vía header "X-API-Key", también responde 200', async () => {
      const res = await fetch(`${baseUrl}/api/catalogos`, { headers: { 'X-API-Key': API_KEY } });
      assert.equal(res.status, 200);
    });

    test('protege también las rutas de /api/dte, no solo /api/catalogos', async () => {
      const res = await fetch(`${baseUrl}/api/dte/factura`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      assert.equal(res.status, 401);
    });
  });

  test('GET /api/catalogos lista los 33 catálogos', async () => {
    const res = await fetch(`${baseUrl}/api/catalogos`, { headers: authHeaders() });
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.length, 33);
  });

  test('GET /api/catalogos/CAT-013?q=san salvador filtra por texto', async () => {
    const res = await fetch(`${baseUrl}/api/catalogos/CAT-013?q=san salvador`, { headers: authHeaders() });
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.ok(body.entradas.length > 0);
    assert.ok(body.entradas.every((e) => e.valor.toLowerCase().includes('san salvador')));
  });

  test('GET /api/catalogos/CAT-008/departamento/06 devuelve los 19 distritos de San Salvador', async () => {
    const res = await fetch(`${baseUrl}/api/catalogos/CAT-008/departamento/06`, { headers: authHeaders() });
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.distritos.length, 19);
  });

  test('GET /api/catalogos/CAT-999 (inexistente) devuelve 404', async () => {
    const res = await fetch(`${baseUrl}/api/catalogos/CAT-999`, { headers: authHeaders() });
    assert.equal(res.status, 404);
  });

  test('POST /api/dte/factura sin items devuelve 400 (autenticado, pero body inválido)', async () => {
    const res = await fetch(`${baseUrl}/api/dte/factura`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json', 'Idempotency-Key': 'test-body-invalido' }),
      body: JSON.stringify({ receptor: null, items: [] }),
    });
    assert.equal(res.status, 400);
  });

  test('la Nota de Crédito queda bloqueada por la allowlist por defecto (01,03), también en v2', async () => {
    for (const ruta of ['nota-credito', 'v2/nota-credito']) {
      const res = await fetch(`${baseUrl}/api/dte/${ruta}`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json', 'Idempotency-Key': `test-tipo-bloqueado-${ruta.replace('/', '-')}` }),
        body: JSON.stringify({}),
      });
      assert.equal(res.status, 403, ruta);
      const body = await res.json();
      assert.equal(body.code, 'DTE_DOCUMENT_TYPE_NOT_ALLOWED');
      assert.equal(body.tipoDte, '05');
    }
  });
});
