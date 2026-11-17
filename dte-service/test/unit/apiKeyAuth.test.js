const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const apiKeyAuth = require('../../src/middleware/apiKeyAuth');
const { requireDteScope } = apiKeyAuth;
const config = require('../../src/config');

function fakeRes() {
  const res = {
    statusCode: null,
    body: null,
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(obj) {
      this.body = obj;
    },
  };
  return res;
}

describe('apiKeyAuth.js', () => {
  test('rechaza con 401 cuando no hay ningún header de autenticación', () => {
    const req = { headers: {} };
    const res = fakeRes();
    let llamoNext = false;
    apiKeyAuth(req, res, () => (llamoNext = true));
    assert.equal(llamoNext, false);
    assert.equal(res.statusCode, 401);
  });

  test('acepta la key correcta vía "Authorization: Bearer <key>"', () => {
    const req = { headers: { authorization: 'Bearer clave-de-prueba-para-tests' } };
    const res = fakeRes();
    let llamoNext = false;
    apiKeyAuth(req, res, () => (llamoNext = true));
    assert.equal(llamoNext, true);
    assert.equal(res.statusCode, null);
  });

  test('acepta la key correcta vía header "X-API-Key"', () => {
    const req = { headers: { 'x-api-key': 'clave-de-prueba-para-tests' } };
    const res = fakeRes();
    let llamoNext = false;
    apiKeyAuth(req, res, () => (llamoNext = true));
    assert.equal(llamoNext, true);
  });

  test('rechaza una key de longitud distinta a la configurada', () => {
    const req = { headers: { 'x-api-key': 'corta' } };
    const res = fakeRes();
    let llamoNext = false;
    apiKeyAuth(req, res, () => (llamoNext = true));
    assert.equal(llamoNext, false);
    assert.equal(res.statusCode, 401);
  });

  test('rechaza una key de la MISMA longitud pero contenido incorrecto', () => {
    const correcta = 'clave-de-prueba-para-tests';
    const incorrecta = correcta.slice(0, -1) + 'X'; // mismo largo, último char distinto
    const req = { headers: { 'x-api-key': incorrecta } };
    const res = fakeRes();
    let llamoNext = false;
    apiKeyAuth(req, res, () => (llamoNext = true));
    assert.equal(llamoNext, false);
  });

  test('prioriza Authorization sobre X-API-Key si ambos vienen (usa el primero que encuentra)', () => {
    const req = {
      headers: {
        authorization: 'Bearer clave-de-prueba-para-tests',
        'x-api-key': 'esto-no-deberia-usarse',
      },
    };
    const res = fakeRes();
    let llamoNext = false;
    apiKeyAuth(req, res, () => (llamoNext = true));
    assert.equal(llamoNext, true);
  });

  test('no revienta con un header Authorization mal formado (sin "Bearer ")', () => {
    const req = { headers: { authorization: 'clave-de-prueba-para-tests' } };
    const res = fakeRes();
    assert.doesNotThrow(() => apiKeyAuth(req, res, () => {}));
    assert.equal(res.statusCode, 401);
  });

  test('deniega un scope que la API key no tiene', () => {
    const registro = config.security.apiKeyRecords[0];
    const originalScopes = registro.scopes;
    registro.scopes = ['read'];
    try {
      const req = { headers: { authorization: 'Bearer clave-de-prueba-para-tests' } };
      const res = fakeRes();
      apiKeyAuth(req, res, () => undefined);
      requireDteScope('issue')(req, res, () => undefined);
      assert.equal(res.statusCode, 403);
      assert.match(res.body.error, /issue/);
    } finally {
      registro.scopes = originalScopes;
    }
  });
});
