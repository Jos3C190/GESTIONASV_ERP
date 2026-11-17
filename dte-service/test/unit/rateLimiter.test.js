const { test, describe, beforeEach } = require('node:test');
const assert = require('node:assert/strict');

// Límite bajo a propósito para no tener que hacer 120 llamadas por test.
process.env.MS_RATE_LIMIT_MAX = '3';
process.env.MS_RATE_LIMIT_WINDOW_MS = '60000';
require('../_setup');

const rateLimiter = require('../../src/middleware/rateLimiter');

function fakeReq(apiKey = 'clave-de-prueba-para-tests') {
  return { headers: { authorization: `Bearer ${apiKey}` }, socket: { remoteAddress: '127.0.0.1' } };
}

function fakeRes() {
  const res = {
    statusCode: null,
    body: null,
    headers: {},
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(obj) {
      this.body = obj;
    },
    setHeader(k, v) {
      this.headers[k] = v;
    },
  };
  return res;
}

describe('rateLimiter.js', () => {
  beforeEach(() => {
    rateLimiter.reiniciar();
  });

  test('permite peticiones por debajo del límite', () => {
    const req = fakeReq();
    for (let i = 0; i < 3; i++) {
      const res = fakeRes();
      let llamoNext = false;
      rateLimiter(req, res, () => (llamoNext = true));
      assert.equal(llamoNext, true, `petición ${i + 1} debería pasar`);
    }
  });

  test('bloquea con 429 al superar el límite configurado', () => {
    const req = fakeReq();
    for (let i = 0; i < 3; i++) {
      rateLimiter(req, fakeRes(), () => {});
    }
    const res = fakeRes();
    let llamoNext = false;
    rateLimiter(req, res, () => (llamoNext = true));
    assert.equal(llamoNext, false);
    assert.equal(res.statusCode, 429);
    assert.ok(res.headers['Retry-After']);
  });

  test('lleva contadores independientes por API key', () => {
    const reqA = fakeReq('key-A');
    const reqB = fakeReq('key-B');
    for (let i = 0; i < 3; i++) rateLimiter(reqA, fakeRes(), () => {});

    // key-A ya agotó su límite...
    const resA = fakeRes();
    let llamoNextA = false;
    rateLimiter(reqA, resA, () => (llamoNextA = true));
    assert.equal(llamoNextA, false);

    // ...pero key-B todavía tiene su propio cupo intacto.
    const resB = fakeRes();
    let llamoNextB = false;
    rateLimiter(reqB, resB, () => (llamoNextB = true));
    assert.equal(llamoNextB, true);
  });

  test('mantiene el mismo cupo al cambiar entre Authorization y X-API-Key', () => {
    const reqBearer = fakeReq('key-equivalente');
    const reqHeader = { headers: { 'x-api-key': 'key-equivalente' }, socket: { remoteAddress: '127.0.0.1' } };
    for (let i = 0; i < 3; i++) rateLimiter(reqBearer, fakeRes(), () => {});

    const res = fakeRes();
    let llamoNext = false;
    rateLimiter(reqHeader, res, () => (llamoNext = true));
    assert.equal(llamoNext, false, 'ambos headers deben identificar al mismo consumidor');
    assert.equal(res.statusCode, 429);
  });

  test('reiniciar() limpia los contadores entre pruebas', () => {
    const req = fakeReq();
    for (let i = 0; i < 3; i++) rateLimiter(req, fakeRes(), () => {});
    rateLimiter.reiniciar();

    const res = fakeRes();
    let llamoNext = false;
    rateLimiter(req, res, () => (llamoNext = true));
    assert.equal(llamoNext, true, 'después de reiniciar, el cupo debe estar libre de nuevo');
  });
});
