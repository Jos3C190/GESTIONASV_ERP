const { test, describe, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { db } = require('../../src/db');
const { reclamar, asociarIdentidad, guardarResultado, hashSolicitud } = require('../../src/services/idempotency');

describe('idempotency.js', () => {
  beforeEach(() => {
    db.exec('DELETE FROM idempotency_keys;');
  });

  test('sin clave (undefined), siempre debeSeguir=true', () => {
    assert.deepEqual(reclamar(undefined), { debeSeguir: true });
  });

  test('una clave nueva se puede reclamar (debeSeguir=true)', () => {
    const r = reclamar('key-nueva-1');
    assert.equal(r.debeSeguir, true);
  });

  test('una clave ya reclamada (PROCESANDO reciente) responde enCurso=true', () => {
    reclamar('key-en-curso');
    const r = reclamar('key-en-curso');
    assert.equal(r.debeSeguir, false);
    assert.equal(r.enCurso, true);
  });

  test('una clave ya COMPLETADA devuelve el resultado guardado, no vuelve a procesar', () => {
    reclamar('key-completa');
    guardarResultado('key-completa', 201, { codigoGeneracion: 'ABC-123' });

    const r = reclamar('key-completa');
    assert.equal(r.debeSeguir, false);
    assert.equal(r.existente.status_code, 201);
    assert.deepEqual(JSON.parse(r.existente.respuesta_json), { codigoGeneracion: 'ABC-123' });
  });

  test('rechaza reutilizar una key con un request distinto', () => {
    const hashA = hashSolicitud('POST', '/api/dte/factura', { items: [{ cantidad: 1 }] });
    const hashB = hashSolicitud('POST', '/api/dte/factura', { items: [{ cantidad: 2 }] });
    reclamar('key-request', hashA);
    guardarResultado('key-request', 400, { error: 'inválido' });
    const result = reclamar('key-request', hashB);
    assert.equal(result.debeSeguir, false);
    assert.equal(result.conflictoSolicitud, true);
  });

  test('revalida un 400 fiscal heredado solo con la misma clave, hash y sin identidad', () => {
    const key = 'key-400-heredada';
    const hash = hashSolicitud('POST', '/api/dte/v2/ccf', { pago: { montoPago: 29.49 } });
    db.prepare(
      `INSERT INTO idempotency_keys (clave, estado, request_hash, status_code, respuesta_json)
       VALUES (?, 'COMPLETADO', ?, 400, ?)`
    ).run(key, hash, JSON.stringify({ error: 'monto incorrecto', code: 'INVALID_DTE_REQUEST' }));

    const first = reclamar(key, hash, { revalidarErrorPreIdentidad: true });
    assert.equal(first.debeSeguir, true);
    assert.equal(first.existente.reintentos_validacion, 1);
    const stored = db.prepare('SELECT estado, reintentos_validacion FROM idempotency_keys WHERE clave = ?').get(key);
    assert.deepEqual(stored, { estado: 'PROCESANDO', reintentos_validacion: 1 });

    const concurrent = reclamar(key, hash, { revalidarErrorPreIdentidad: true });
    assert.equal(concurrent.debeSeguir, false);
    assert.equal(concurrent.enCurso, true);
  });

  test('un 400 no fiscal o sin request_hash permanece terminal', () => {
    reclamar('key-400-terminal');
    guardarResultado('key-400-terminal', 400, { error: 'bad request' }, { revalidarErrorPreIdentidad: true });
    const r = reclamar('key-400-terminal', null, { revalidarErrorPreIdentidad: true });
    assert.equal(r.debeSeguir, false);
    assert.equal(r.existente.estado, 'COMPLETADO');
  });

  test('el hash es estable aunque cambie el orden de las propiedades', () => {
    assert.equal(
      hashSolicitud('POST', '/api/dte/factura', { b: 2, a: { y: 1, x: 0 } }),
      hashSolicitud('POST', '/api/dte/factura', { a: { x: 0, y: 1 }, b: 2 })
    );
  });

  test('un 502 queda reintentable y conserva la identidad fiscal', () => {
    reclamar('key-retry');
    asociarIdentidad('key-retry', 'CODIGO-1');
    guardarResultado('key-retry', 502, { codigoGeneracion: 'CODIGO-1', error: 'firmador' });
    const stored = db.prepare('SELECT * FROM idempotency_keys WHERE clave = ?').get('key-retry');
    assert.equal(stored.estado, 'REINTENTABLE');
    assert.equal(stored.codigo_generacion, 'CODIGO-1');
    const retry = reclamar('key-retry');
    assert.equal(retry.debeSeguir, true);
    assert.equal(retry.existente.codigo_generacion, 'CODIGO-1');
  });

  test('un 202 queda pendiente y se reproduce sin ejecutar de nuevo', () => {
    reclamar('key-pending');
    guardarResultado('key-pending', 202, { codigoGeneracion: 'CODIGO-2', estado: 'PENDIENTE_REINTENTO' });
    const retry = reclamar('key-pending');
    assert.equal(retry.debeSeguir, false);
    assert.equal(retry.existente.estado, 'PENDIENTE');
    assert.equal(retry.existente.codigo_generacion, 'CODIGO-2');
  });

  test('claves distintas son completamente independientes entre sí', () => {
    reclamar('key-A');
    guardarResultado('key-A', 201, { codigoGeneracion: 'A' });

    const rB = reclamar('key-B');
    assert.equal(rB.debeSeguir, true); // key-B no se ve afectada por key-A
  });

  test('una clave PROCESANDO abandonada sin identidad requiere conciliación', () => {
    reclamar('key-abandonada');
    // Simula que quedó "vieja" retrocediendo su creado_en manualmente.
    db.prepare(`UPDATE idempotency_keys SET actualizado_en = datetime('now', '-1 hour') WHERE clave = ?`).run('key-abandonada');

    const r = reclamar('key-abandonada');
    assert.equal(r.debeSeguir, false);
    assert.equal(r.reconciliacionRequerida, true);
  });

  test('una clave PROCESANDO abandonada con identidad conserva el DTE al reclamarla', () => {
    reclamar('key-abandonada-con-identidad');
    asociarIdentidad('key-abandonada-con-identidad', 'CODIGO-ABANDONADO');
    db.prepare(`UPDATE idempotency_keys SET actualizado_en = datetime('now', '-1 hour') WHERE clave = ?`).run('key-abandonada-con-identidad');

    const r = reclamar('key-abandonada-con-identidad');
    assert.equal(r.debeSeguir, true);
    assert.equal(r.existente.codigo_generacion, 'CODIGO-ABANDONADO');
  });

  test('guardarResultado no revienta si se llama sin clave', () => {
    assert.doesNotThrow(() => guardarResultado(undefined, 200, {}));
  });
});
