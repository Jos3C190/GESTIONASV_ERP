/**
 * Tests de integración end-to-end de las rutas de DTE. Levanta el servidor
 * Express real contra una base SQLite real (en memoria) y mockea SOLO las
 * llamadas de red externas (firmador y Hacienda), que es la frontera
 * correcta para un test de integración: todo el código propio (rutas,
 * builders, validadores, cola de reintentos, SQL) corre de verdad.
 *
 * Requiere las dependencias reales instaladas (`npm install`).
 */
const { test, describe, before, beforeEach, after } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
require('../_setup');

const { db, obtenerSiguienteCorrelativo } = require('../../src/db');
const correlativoStore = require('../../src/services/correlativoStore');
const firmadorClient = require('../../src/services/firmadorClient');
const haciendaClient = require('../../src/services/haciendaClient');
const { hashSolicitud } = require('../../src/services/idempotency');
const { AuthError } = require('../../src/services/authService');
const { FirmadorError } = firmadorClient;
const { usarReloj } = require('../../src/utils/fechaHoraSV');
const { textoCompleto } = require('../unit/_pdfTexto');

correlativoStore.usar(obtenerSiguienteCorrelativo);

let server;
let baseUrl;
let autoIdempotencySequence = 0;

// Debe coincidir con MS_API_KEYS definida en test/setup-env.js
const API_KEY = 'clave-de-prueba-para-tests';

async function post(path, body, headersExtra = {}) {
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${API_KEY}`, ...headersExtra };
  if (!Object.prototype.hasOwnProperty.call(headersExtra, 'Idempotency-Key')) {
    autoIdempotencySequence += 1;
    headers['Idempotency-Key'] = `test-auto-${autoIdempotencySequence}`;
  } else if (headers['Idempotency-Key'] === null) {
    delete headers['Idempotency-Key'];
  }
  const res = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  return { status: res.status, body: await res.json() };
}

async function get(path) {
  const res = await fetch(`${baseUrl}${path}`, { headers: { Authorization: `Bearer ${API_KEY}` } });
  return { status: res.status, body: await res.json() };
}

const SELLO_EVENTO = 'SELLO-EVENTO-001'.padEnd(40, 'X');

const FACTURA_VALIDA = {
  receptor: null,
  // Factura: precio y venta con IVA incluido (113 = 100 + 13).
  items: [{ descripcion: 'Servicio de prueba', cantidad: 1, precioUni: 113, ventaGravada: 113 }],
  pago: { codigo: '05', montoPago: 113, referencia: 'TRANSFER-INTEGRATION', numPagoElectronico: null },
};

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonicalize(item)]));
  }
  return value;
}

function CCF_V2_VALIDO() {
  const canonical = {
    legalName: 'Emisor fixture DTE S.A. de C.V.', tradeName: 'Emisor fixture', nit: process.env.MH_NIT,
    nrc: '1234567', economicActivityCode: '62010', economicActivityDescription: 'Programación informática',
    activityCatalogVersion: 'CAT-019',
    address: {
      departmentCode: '06', departmentName: 'San Salvador', municipalityCode: '23',
      municipalityName: 'San Salvador Centro', districtCode: '14', districtName: 'San Salvador',
      complement: 'Dirección fixture', geoCatalogVersion: 'GEO-TEST',
    },
    phone: '22221111', email: 'emisor-fixture@example.test', establishmentType: '02',
    mhEstablishmentCode: '001', mhPointOfSaleCode: '001', internalEstablishmentCode: 'CASA',
    internalPointOfSaleCode: null,
  };
  const snapshotSha256 = crypto.createHash('sha256').update(JSON.stringify(canonicalize(canonical))).digest('hex');
  return {
    emisor: {
      revisionId: 'revision-ccf-fixture', snapshotSha256, nit: canonical.nit, nrc: canonical.nrc,
      nombre: canonical.legalName, nombreComercial: canonical.tradeName, codActividad: canonical.economicActivityCode,
      descActividad: canonical.economicActivityDescription, activityCatalogVersion: canonical.activityCatalogVersion,
      direccion: {
        departamento: '06', departmentName: 'San Salvador', municipio: '23', municipalityName: 'San Salvador Centro',
        distrito: '14', districtName: 'San Salvador', complemento: 'Dirección fixture', geoCatalogVersion: 'GEO-TEST',
      },
      telefono: canonical.phone, correo: canonical.email, tipoEstablecimiento: '02',
      codEstablecimientoMH: '001', codPuntoVentaMH: '001', codEstable: 'CASA', codPuntoVenta: null,
    },
    receptor: {
      nit: '06141804941099', nrc: '7654321', nombre: 'Cliente fixture S.A. de C.V.', nombreComercial: null,
      codActividad: '62010', descActividad: 'Programación informática',
      direccion: { departamento: '06', municipio: '23', distrito: '14', complemento: 'Dirección cliente fixture' },
      telefono: '22223333', correo: 'cliente-fixture@example.test',
    },
    items: [
      { tipoItem: 1, codigo: 'ITEM-CCF', cantidad: 1, descripcion: 'Producto fixture', precioUni: 22.12, ventaGravada: 22.12, ventaNoSuj: 0, ivaItem: 2.87, montoDescu: 0 },
      { tipoItem: 2, codigo: null, cantidad: 1, descripcion: 'Servicio de entrega', precioUni: 4.5, ventaGravada: 0, ventaNoSuj: 4.5, ivaItem: 0, montoDescu: 0 },
    ],
    descuentoGlobal: null,
    pago: { codigo: null, montoPago: 29.49, referencia: '0abac760-e642-46e0-b658-0f526957b88a', numPagoElectronico: '0abac760-e642-46e0-b658-0f526957b88a' },
  };
}

describe('Emisión de DTE end-to-end (integración, requiere npm install)', () => {
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

  beforeEach(() => {
    autoIdempotencySequence = 0;
    db.exec('DELETE FROM cola_reintentos; DELETE FROM contingencia_documentos; DELETE FROM contingencias; DELETE FROM eventos; DELETE FROM dtes; DELETE FROM correlativos; DELETE FROM idempotency_keys;');
    firmadorClient.firmarDocumento = async () => 'JWS.FIRMADO.FALSO';
    // El schema oficial exige selloRecibido de EXACTAMENTE 40 caracteres.
    haciendaClient.transmitirDte = async () => ({ estado: 'PROCESADO', selloRecibido: 'SELLO-FALSO-001'.padEnd(40, 'X') });
  });

  test('POST /api/dte/factura: camino feliz completo (construir -> firmar -> transmitir)', async () => {
    const { status, body } = await post('/api/dte/factura', FACTURA_VALIDA);
    assert.equal(status, 201);
    assert.equal(body.estado, 'TRANSMITIDO');
    assert.equal(body.selloRecepcion, 'SELLO-FALSO-001'.padEnd(40, 'X'));
    assert.match(body.numeroControl, /^DTE-01-/);

    const row = db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(body.codigoGeneracion);
    assert.equal(row.estado, 'TRANSMITIDO');
    assert.equal(row.sello_recepcion, 'SELLO-FALSO-001'.padEnd(40, 'X'));
  });

  describe('Idempotency-Key', () => {
    test('sin Idempotency-Key rechaza la emisión antes de crear identidad', async () => {
      const result = await post('/api/dte/factura', FACTURA_VALIDA, { 'Idempotency-Key': null });
      assert.equal(result.status, 400);
      assert.match(result.body.error, /Idempotency-Key es obligatoria/i);
      assert.equal(db.prepare('SELECT COUNT(*) as n FROM dtes').get().n, 0);
    });

    test('con la MISMA Idempotency-Key, la segunda llamada devuelve el mismo resultado sin crear un DTE nuevo', async () => {
      const clave = 'idem-key-001';
      const r1 = await post('/api/dte/factura', FACTURA_VALIDA, { 'Idempotency-Key': clave });
      const r2 = await post('/api/dte/factura', FACTURA_VALIDA, { 'Idempotency-Key': clave });

      assert.equal(r1.status, r2.status);
      assert.deepEqual(r1.body, r2.body);
      assert.equal(r1.body.codigoGeneracion, r2.body.codigoGeneracion);

      const count = db.prepare('SELECT COUNT(*) as n FROM dtes').get();
      assert.equal(count.n, 1, 'solo debe existir UN DTE en la base, no dos');
    });

    test('Idempotency-Keys distintas sí generan DTE distintos', async () => {
      const r1 = await post('/api/dte/factura', FACTURA_VALIDA, { 'Idempotency-Key': 'idem-key-A' });
      const r2 = await post('/api/dte/factura', FACTURA_VALIDA, { 'Idempotency-Key': 'idem-key-B' });
      assert.notEqual(r1.body.codigoGeneracion, r2.body.codigoGeneracion);
    });

    test('también funciona para respuestas de error (400), no solo éxitos', async () => {
      const clave = 'idem-key-error';
      const r1 = await post('/api/dte/factura', { receptor: null, items: [] }, { 'Idempotency-Key': clave });
      const r2 = await post('/api/dte/factura', { receptor: null, items: [] }, { 'Idempotency-Key': clave });
      assert.equal(r1.status, 400);
      assert.deepEqual(r1.body, r2.body);
      const stored = db.prepare('SELECT estado, reintentos_validacion FROM idempotency_keys WHERE clave = ?').get(clave);
      assert.deepEqual(stored, { estado: 'VALIDACION_REINTENTABLE', reintentos_validacion: 1 });
    });

    test('revalida un 400 CCF v2 heredado y crea una sola identidad para el mismo cuerpo', async () => {
      const clave = 'idem-key-ccf-cache-400';
      const payload = CCF_V2_VALIDO();
      const requestHash = hashSolicitud('POST', '/api/dte/v2/ccf', payload);
      db.prepare(
        `INSERT INTO idempotency_keys (clave, estado, request_hash, status_code, respuesta_json)
         VALUES (?, 'COMPLETADO', ?, 400, ?)`
      ).run(clave, requestHash, JSON.stringify({ error: 'El monto de pago no coincide con el total a pagar del DTE', code: 'INVALID_DTE_REQUEST' }));

      const first = await post('/api/dte/v2/ccf', payload, { 'Idempotency-Key': clave });
      assert.equal(first.status, 201, JSON.stringify(first.body));
      assert.equal(first.body.estado, 'TRANSMITIDO');
      assert.equal(first.body.numeroControl.endsWith('000000000000001'), true);
      assert.equal(db.prepare('SELECT COUNT(*) AS n FROM dtes').get().n, 1);

      const second = await post('/api/dte/v2/ccf', payload, { 'Idempotency-Key': clave });
      assert.equal(second.status, 201);
      assert.equal(second.body.codigoGeneracion, first.body.codigoGeneracion);
      const stored = db.prepare('SELECT estado, status_code, reintentos_validacion FROM idempotency_keys WHERE clave = ?').get(clave);
      assert.deepEqual(stored, { estado: 'COMPLETADO', status_code: 201, reintentos_validacion: 1 });
      assert.equal(db.prepare('SELECT COUNT(*) AS n FROM dtes').get().n, 1);
    });

    test('rechaza la misma key cuando cambia el request', async () => {
      const clave = 'idem-key-request-distinto';
      const r1 = await post('/api/dte/factura', FACTURA_VALIDA, { 'Idempotency-Key': clave });
      const r2 = await post(
        '/api/dte/factura',
        { ...FACTURA_VALIDA, items: [{ ...FACTURA_VALIDA.items[0], precioUni: 200, ventaGravada: 200 }] },
        { 'Idempotency-Key': clave }
      );
      assert.equal(r1.status, 201);
      assert.equal(r2.status, 409);
      assert.match(r2.body.error, /solicitud diferente/i);
      assert.equal(db.prepare('SELECT COUNT(*) AS n FROM dtes').get().n, 1);
    });

    test('reintenta un fallo de firma con el mismo código y número de control', async () => {
      const clave = 'idem-key-firma-retry';
      let intentosFirma = 0;
      firmadorClient.firmarDocumento = async () => {
        intentosFirma += 1;
        if (intentosFirma === 1) throw new Error('Firmador temporalmente no disponible');
        return 'JWS.FIRMADO.FALSO';
      };

      const r1 = await post('/api/dte/factura', FACTURA_VALIDA, { 'Idempotency-Key': clave });
      const r2 = await post('/api/dte/factura', FACTURA_VALIDA, { 'Idempotency-Key': clave });
      assert.equal(r1.status, 502);
      assert.equal(r2.status, 201);
      assert.equal(r2.body.codigoGeneracion, r1.body.codigoGeneracion);
      assert.equal(r2.body.numeroControl, r1.body.numeroControl);
      assert.equal(db.prepare('SELECT COUNT(*) AS n FROM dtes').get().n, 1);
      assert.equal(intentosFirma, 2);
    });

    test('credenciales de Hacienda rechazadas: 502 de configuración y la misma key reanuda sin volver a firmar', async () => {
      const clave = 'idem-key-credenciales';
      let firmas = 0;
      firmadorClient.firmarDocumento = async () => {
        firmas += 1;
        return 'JWS.FIRMADO.FALSO';
      };
      haciendaClient.transmitirDte = async () => {
        throw new AuthError('Hacienda rechazó la autenticación: credenciales inválidas', { credenciales: true });
      };

      const r1 = await post('/api/dte/factura', FACTURA_VALIDA, { 'Idempotency-Key': clave });
      assert.equal(r1.status, 502);
      assert.equal(r1.body.code, 'HACIENDA_AUTH_CONFIGURATION_ERROR');
      assert.equal(r1.body.estado, 'FIRMADO');
      const row = db.prepare('SELECT estado, documento_firmado FROM dtes WHERE codigo_generacion = ?').get(r1.body.codigoGeneracion);
      assert.equal(row.estado, 'FIRMADO');
      assert.equal(db.prepare('SELECT COUNT(*) AS n FROM cola_reintentos').get().n, 0, 'no es una caída de Hacienda: no entra a la cola');

      haciendaClient.transmitirDte = async () => ({ estado: 'PROCESADO', selloRecibido: 'SELLO-FALSO-001'.padEnd(40, 'X') });
      const r2 = await post('/api/dte/factura', FACTURA_VALIDA, { 'Idempotency-Key': clave });
      assert.equal(r2.status, 201);
      assert.equal(r2.body.estado, 'TRANSMITIDO');
      assert.equal(r2.body.codigoGeneracion, r1.body.codigoGeneracion);
      assert.equal(firmas, 1, 'el documento firmado y sin cambios se reutiliza');
    });

    test('un error de configuración del firmador (803/809/812) se identifica con su código', async () => {
      firmadorClient.firmarDocumento = async () => {
        throw new FirmadorError('El firmador rechazó la solicitud (803): contraseña incorrecta', { codigo: '803', configuracion: true });
      };
      const { status, body } = await post('/api/dte/factura', FACTURA_VALIDA);
      assert.equal(status, 502);
      assert.equal(body.code, 'FIRMADOR_CONFIGURATION_ERROR');
      assert.equal(body.estado, 'ERROR_FIRMA');
      assert.match(body.detalle, /803/);
    });

    test('al reanudar otro día actualiza fecEmi/horEmi y vuelve a firmar con la misma identidad', async () => {
      const clave = 'idem-key-otro-dia';
      const firmados = [];
      firmadorClient.firmarDocumento = async (dte) => {
        firmados.push(structuredClone(dte));
        if (firmados.length === 1) throw new Error('Firmador temporalmente no disponible');
        return 'JWS.FIRMADO.FALSO';
      };

      usarReloj(() => new Date('2026-10-14T20:00:00Z')); // 14:00 en El Salvador
      const r1 = await post('/api/dte/factura', FACTURA_VALIDA, { 'Idempotency-Key': clave });
      usarReloj(() => new Date('2026-10-16T15:30:00Z')); // 09:30 dos días después
      const r2 = await post('/api/dte/factura', FACTURA_VALIDA, { 'Idempotency-Key': clave });
      usarReloj();

      assert.equal(r1.status, 502);
      assert.equal(r2.status, 201);
      assert.equal(r2.body.codigoGeneracion, r1.body.codigoGeneracion);
      assert.equal(r2.body.numeroControl, r1.body.numeroControl, 'mismo año: conserva el número de control');
      assert.equal(firmados[0].identificacion.fecEmi, '2026-10-14');
      assert.equal(firmados[1].identificacion.fecEmi, '2026-10-16');
      assert.equal(firmados[1].identificacion.horEmi, '09:30:00');
      const payload = JSON.parse(db.prepare('SELECT payload_json FROM dtes WHERE codigo_generacion = ?').get(r1.body.codigoGeneracion).payload_json);
      assert.equal(payload.identificacion.fecEmi, '2026-10-16', 'el payload persistido es el que se firmó');
    });

    test('al reanudar en otro año reserva un número de control del correlativo del nuevo año', async () => {
      const clave = 'idem-key-otro-anio';
      let fallarFirma = false;
      firmadorClient.firmarDocumento = async () => {
        if (fallarFirma) {
          fallarFirma = false;
          throw new Error('Firmador temporalmente no disponible');
        }
        return 'JWS.FIRMADO.FALSO';
      };

      usarReloj(() => new Date('2027-01-01T05:50:00Z')); // 31-dic-2026 23:50 en El Salvador
      await post('/api/dte/factura', FACTURA_VALIDA); // consume el correlativo 1 de 2026
      fallarFirma = true;
      const r1 = await post('/api/dte/factura', FACTURA_VALIDA, { 'Idempotency-Key': clave });
      usarReloj(() => new Date('2027-01-01T06:10:00Z')); // 1-ene-2027 00:10
      const r2 = await post('/api/dte/factura', FACTURA_VALIDA, { 'Idempotency-Key': clave });
      usarReloj();

      assert.equal(r1.status, 502);
      assert.equal(r2.status, 201);
      assert.equal(r2.body.codigoGeneracion, r1.body.codigoGeneracion);
      assert.match(r1.body.numeroControl, /-000000000000002$/);
      assert.match(r2.body.numeroControl, /-000000000000001$/, 'el correlativo se reinicia en el año nuevo');
      const row = db.prepare('SELECT numero_control, payload_json FROM dtes WHERE codigo_generacion = ?').get(r1.body.codigoGeneracion);
      assert.equal(row.numero_control, r2.body.numeroControl);
      assert.equal(JSON.parse(row.payload_json).identificacion.fecEmi, '2027-01-01');
    });

    test('una petición con la misma key mientras la primera "sigue en curso" responde 409', async () => {
      const clave = 'idem-key-en-curso';
      // Reclama la key manualmente, simulando que otra petición ya la tomó
      // y todavía no terminó (sin llamar a guardarResultado()).
      const { reclamar } = require('../../src/services/idempotency');
      reclamar(clave);

      const { status, body } = await post('/api/dte/factura', FACTURA_VALIDA, { 'Idempotency-Key': clave });
      assert.equal(status, 409);
      assert.match(body.error, /en curso/i);
    });
  });

  test('POST /api/dte/factura sin items responde 400 y no toca la base', async () => {
    const { status } = await post('/api/dte/factura', { receptor: null, items: [] });
    assert.equal(status, 400);
    const count = db.prepare('SELECT COUNT(*) as n FROM dtes').get();
    assert.equal(count.n, 0);
  });

  test('si el schema oficial rechaza el DTE, revierte correlativo e identidad fiscal', async () => {
    const invalid = await post('/api/dte/factura', {
      receptor: null,
      items: [{ descripcion: 'x'.repeat(1501), cantidad: 1, precioUni: 113, ventaGravada: 113 }],
      pago: { codigo: '05', montoPago: 113, referencia: 'SCHEMA-INVALID' },
    });
    assert.equal(invalid.status, 422);
    assert.equal(invalid.body.code, 'DTE_SCHEMA_INVALID');
    assert.equal(db.prepare('SELECT COUNT(*) AS n FROM correlativos').get().n, 0);
    assert.equal(db.prepare('SELECT COUNT(*) AS n FROM dtes').get().n, 0);

    const valid = await post('/api/dte/factura', FACTURA_VALIDA);
    assert.equal(valid.status, 201);
    assert.equal(valid.body.numeroControl.endsWith('000000000000001'), true);
    assert.equal(db.prepare('SELECT COUNT(*) AS n FROM correlativos').get().n, 1);
  });

  test('POST /api/dte/ccf sin receptor.nit/nrc responde 400 (el builder lo rechaza antes de firmar)', async () => {
    const { status, body } = await post('/api/dte/ccf', { receptor: { nombre: 'Sin NIT' }, items: FACTURA_VALIDA.items });
    assert.equal(status, 400);
    assert.match(body.error, /nit|nrc/i);
  });

  test('si el firmador falla, responde 502 y el DTE queda en estado ERROR_FIRMA', async () => {
    firmadorClient.firmarDocumento = async () => {
      throw new Error('Firmador no disponible (simulado)');
    };
    const { status } = await post('/api/dte/factura', FACTURA_VALIDA);
    assert.equal(status, 502);

    const row = db.prepare('SELECT * FROM dtes').get();
    assert.equal(row.estado, 'ERROR_FIRMA');
    assert.match(row.observaciones, /Firmador no disponible/);
  });

  test('si Hacienda no responde, el DTE queda en reconciliación y se consulta antes de reenviar (no se pierde)', async () => {
    haciendaClient.transmitirDte = async () => {
      throw new Error('Timeout de Hacienda (simulado)');
    };
    const { status, body } = await post('/api/dte/factura', FACTURA_VALIDA);
    assert.equal(status, 202);
    assert.equal(body.estado, 'PENDIENTE_RECONCILIACION');

    const row = db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(body.codigoGeneracion);
    assert.equal(row.estado, 'PENDIENTE_RECONCILIACION');
    assert.equal(row.documento_firmado, 'JWS.FIRMADO.FALSO', 'el documento firmado no debe perderse aunque falle la transmisión');

    const cola = db.prepare('SELECT * FROM cola_reintentos WHERE codigo_generacion = ?').all(body.codigoGeneracion);
    assert.equal(cola.length, 1);
    assert.equal(cola[0].accion, 'CONSULTAR', 'el documento pudo haber llegado: primero se consulta (Manual Técnico 3.3)');
  });

  test('si Hacienda rechaza, el DTE queda RECHAZADO y no se reintenta ni se marca transmitido', async () => {
    // haciendaClient devuelve el cuerpo del HTTP 400 en lugar de lanzar.
    haciendaClient.transmitirDte = async () => ({ estado: 'RECHAZADO', codigoMsg: '020', descripcionMsg: 'DTE rechazado (simulado)' });
    const { status, body } = await post('/api/dte/factura', FACTURA_VALIDA);
    assert.equal(status, 200);
    assert.equal(body.estado, 'RECHAZADO');

    const row = db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(body.codigoGeneracion);
    assert.equal(row.estado, 'RECHAZADO');
    assert.equal(row.sello_recepcion, null);
    assert.equal(db.prepare('SELECT COUNT(*) as n FROM cola_reintentos WHERE codigo_generacion = ?').get(body.codigoGeneracion).n, 0);
  });

  test('si Hacienda responde "ya existe" (004) sobre el mismo código, consulta para recuperar el sello', async () => {
    haciendaClient.transmitirDte = async () => ({
      estado: 'RECHAZADO',
      codigoMsg: '004',
      descripcionMsg: '[identificacion.codigoGeneracion] YA EXISTE UN REGISTRO CON ESE VALOR',
    });
    const { status, body } = await post('/api/dte/factura', FACTURA_VALIDA);
    assert.equal(status, 202);
    assert.equal(body.estado, 'PENDIENTE_RECONCILIACION');
    const cola = db.prepare('SELECT * FROM cola_reintentos WHERE codigo_generacion = ?').get(body.codigoGeneracion);
    assert.equal(cola.accion, 'CONSULTAR');
    assert.equal(cola.motivo, 'DUPLICADO');
  });

  test('si Hacienda responde PROCESADO sin sello, queda en reconciliación y consulta el mismo código', async () => {
    haciendaClient.transmitirDte = async () => ({ estado: 'PROCESADO' });
    const { status, body } = await post('/api/dte/factura', FACTURA_VALIDA);
    assert.equal(status, 202);
    assert.equal(body.estado, 'PENDIENTE_RECONCILIACION');

    const row = db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(body.codigoGeneracion);
    assert.equal(row.estado, 'PENDIENTE_RECONCILIACION');
    const cola = db.prepare('SELECT * FROM cola_reintentos WHERE codigo_generacion = ?').get(body.codigoGeneracion);
    assert.equal(cola.accion, 'CONSULTAR');
  });

  test('GET /api/dte/:codigoGeneracion devuelve el estado local tras emitir', async () => {
    const { body: emitido } = await post('/api/dte/factura', FACTURA_VALIDA);
    const { status, body } = await get(`/api/dte/${emitido.codigoGeneracion}`);
    assert.equal(status, 200);
    assert.equal(body.estado, 'TRANSMITIDO');
    assert.equal(body.numero_control, emitido.numeroControl);
  });

  test('GET /api/dte/:codigoGeneracion/json devuelve el archivo canónico con firma y sello', async () => {
    const { body: emitido } = await post('/api/dte/factura', FACTURA_VALIDA);
    const { status, body } = await get(`/api/dte/${emitido.codigoGeneracion}/json`);
    assert.equal(status, 200);
    assert.equal(body.identificacion.codigoGeneracion, emitido.codigoGeneracion);
    assert.equal(body.firmaElectronica, 'JWS.FIRMADO.FALSO');
    assert.equal(body.selloRecibido, 'SELLO-FALSO-001'.padEnd(40, 'X'));
  });

  test('GET /api/dte/:codigoGeneracion con un código inexistente responde 404', async () => {
    const { status } = await get('/api/dte/00000000-0000-0000-0000-000000000000');
    assert.equal(status, 404);
  });

  describe('GET /api/dte/:codigoGeneracion/pdf', () => {
    test('genera un PDF para un DTE en estado TRANSMITIDO', async () => {
      const { body: emitido } = await post('/api/dte/factura', FACTURA_VALIDA);
      const res = await fetch(`${baseUrl}/api/dte/${emitido.codigoGeneracion}/pdf`, {
        headers: { Authorization: `Bearer ${API_KEY}` },
      });
      assert.equal(res.status, 200);
      assert.match(res.headers.get('content-type'), /application\/pdf/);
      const buffer = Buffer.from(await res.arrayBuffer());
      assert.ok(buffer.length > 0);
    });

    test('responde 409 si el DTE todavía no está TRANSMITIDO', async () => {
      haciendaClient.transmitirDte = async () => {
        throw new Error('Timeout simulado');
      };
      const { body: emitido } = await post('/api/dte/factura', FACTURA_VALIDA); // queda PENDIENTE_RECONCILIACION
      const res = await fetch(`${baseUrl}/api/dte/${emitido.codigoGeneracion}/pdf`, {
        headers: { Authorization: `Bearer ${API_KEY}` },
      });
      assert.equal(res.status, 409);
    });

    test('responde 409 si está TRANSMITIDO pero no tiene sello de recepción', async () => {
      const { body: emitido } = await post('/api/dte/factura', FACTURA_VALIDA);
      db.prepare('UPDATE dtes SET sello_recepcion = NULL WHERE codigo_generacion = ?').run(emitido.codigoGeneracion);
      const res = await fetch(`${baseUrl}/api/dte/${emitido.codigoGeneracion}/pdf`, {
        headers: { Authorization: `Bearer ${API_KEY}` },
      });
      assert.equal(res.status, 409);
      const body = await res.json();
      assert.match(body.error, /sello de recepción/);
    });

    test('responde 404 si el DTE no existe', async () => {
      const res = await fetch(`${baseUrl}/api/dte/00000000-0000-0000-0000-000000000000/pdf`, {
        headers: { Authorization: `Bearer ${API_KEY}` },
      });
      assert.equal(res.status, 404);
    });
  });

  describe('POST /api/dte/:codigoGeneracion/anular', () => {
    // Contrato plano anterior (sigue aceptado); tipo 2 = rescindir, sin reemplazo.
    const motivo = {
      tipoAnulacion: 2,
      motivoAnulacion: 'Anulación de prueba',
      nombreResponsable: 'Juan Pérez',
      tipDocResponsable: '13',
      numDocResponsable: '01234567-8',
      nombreSolicita: 'Juan Pérez',
      tipDocSolicita: '13',
      numDocSolicita: '01234567-8',
    };

    test('anula exitosamente un DTE en estado TRANSMITIDO', async () => {
      const { body: emitido } = await post('/api/dte/factura', FACTURA_VALIDA);

      haciendaClient.anularDte = async () => ({ estado: 'PROCESADO', selloRecibido: SELLO_EVENTO, codigoMsg: '001', descripcionMsg: 'Invalidación Recibida y Procesada' });

      const { status, body } = await post(`/api/dte/${emitido.codigoGeneracion}/anular`, { motivo });
      assert.equal(status, 200);
      assert.ok(body.codigoGeneracionEvento);

      const row = db.prepare('SELECT estado FROM dtes WHERE codigo_generacion = ?').get(emitido.codigoGeneracion);
      assert.equal(row.estado, 'INVALIDADO');
    });

    test('con Idempotency-Key, reintentar la anulación devuelve el mismo resultado (no falla con 409 "ya invalidado")', async () => {
      const { body: emitido } = await post('/api/dte/factura', FACTURA_VALIDA);
      haciendaClient.anularDte = async () => ({ estado: 'PROCESADO', selloRecibido: SELLO_EVENTO, codigoMsg: '001', descripcionMsg: 'Invalidación Recibida y Procesada' });

      const clave = 'idem-anular-001';
      const r1 = await post(`/api/dte/${emitido.codigoGeneracion}/anular`, { motivo }, { 'Idempotency-Key': clave });
      const r2 = await post(`/api/dte/${emitido.codigoGeneracion}/anular`, { motivo }, { 'Idempotency-Key': clave });

      assert.equal(r1.status, 200);
      assert.deepEqual(r1.body, r2.body); // la segunda NO reprocesa; devuelve exactamente lo mismo
    });

    test('no marca INVALIDADO si Hacienda rechaza el evento o no devuelve sello', async () => {
      const { body: emitido } = await post('/api/dte/factura', FACTURA_VALIDA);

      haciendaClient.anularDte = async () => ({ estado: 'RECHAZADO', codigoMsg: '020', descripcionMsg: 'Fuera de plazo' });
      const rechazado = await post(`/api/dte/${emitido.codigoGeneracion}/anular`, { motivo });
      assert.equal(rechazado.status, 422);
      assert.equal(rechazado.body.code, 'INVALIDATION_REJECTED');

      haciendaClient.anularDte = async () => ({ estado: 'PROCESADO', codigoMsg: '001' });
      const sinSello = await post(`/api/dte/${emitido.codigoGeneracion}/anular`, { motivo });
      assert.equal(sinSello.status, 502);
      assert.equal(sinSello.body.code, 'INVALIDATION_UNCONFIRMED');

      const row = db.prepare('SELECT estado FROM dtes WHERE codigo_generacion = ?').get(emitido.codigoGeneracion);
      assert.equal(row.estado, 'TRANSMITIDO');
    });

    test('responde 404 si el DTE no existe localmente', async () => {
      const { status } = await post('/api/dte/00000000-0000-0000-0000-000000000000/anular', { motivo });
      assert.equal(status, 404);
    });

    test('responde 409 si el DTE no está en estado TRANSMITIDO', async () => {
      haciendaClient.transmitirDte = async () => {
        throw new Error('Timeout simulado');
      };
      const { body: emitido } = await post('/api/dte/factura', FACTURA_VALIDA); // queda PENDIENTE_RECONCILIACION

      const { status, body } = await post(`/api/dte/${emitido.codigoGeneracion}/anular`, { motivo });
      assert.equal(status, 409);
      assert.match(body.error, /TRANSMITIDO/);
    });

    test('responde 400 si tipoAnulacion=1 no trae codigoGeneracionReemplazo', async () => {
      const { body: emitido } = await post('/api/dte/factura', FACTURA_VALIDA);
      const { status, body } = await post(`/api/dte/${emitido.codigoGeneracion}/anular`, {
        motivo: { ...motivo, tipoAnulacion: 1 },
      });
      assert.equal(status, 400);
      assert.match(body.error, /reemplaza/);
    });

    test('tipo 1 con documento de reemplazo transmitido: el evento lo referencia y queda archivado', async () => {
      const { body: original } = await post('/api/dte/factura', FACTURA_VALIDA);
      const { body: reemplazo } = await post('/api/dte/factura', FACTURA_VALIDA);
      let enviado;
      haciendaClient.anularDte = async (datos) => {
        enviado = datos;
        return { estado: 'PROCESADO', selloRecibido: SELLO_EVENTO, codigoMsg: '001' };
      };

      const { status, body } = await post(`/api/dte/${original.codigoGeneracion}/anular`, {
        motivo: {
          tipoAnulacion: 1,
          responsable: { nombre: 'Juan Pérez', tipoDocumento: '13', numeroDocumento: '01234567-8' },
          solicitante: { nombre: 'Ana López', tipoDocumento: '36', numeroDocumento: '06141804941035' },
        },
        codigoGeneracionReemplazo: reemplazo.codigoGeneracion,
      });
      assert.equal(status, 200, JSON.stringify(body));
      assert.equal(body.estado, 'INVALIDADO');
      assert.equal(body.selloRecepcionEvento, SELLO_EVENTO);
      assert.ok(Number.isInteger(enviado.idEnvio) && enviado.idEnvio <= 2147483647);
      assert.equal(enviado.version, 3);

      const res = await fetch(`${baseUrl}/api/dte/eventos/${body.codigoGeneracionEvento}/json`, { headers: { Authorization: `Bearer ${API_KEY}` } });
      assert.equal(res.status, 200);
      const archivo = await res.json();
      assert.equal(archivo.documento.codigoGeneracion, original.codigoGeneracion);
      assert.equal(archivo.documento.codigoGeneracionR, reemplazo.codigoGeneracion);
      assert.equal(archivo.selloRecibido, SELLO_EVENTO);
      assert.equal(archivo.firmaElectronica, 'JWS.FIRMADO.FALSO');

      const renderEvento = (cuerpo) => fetch(`${baseUrl}/api/dte/eventos/${body.codigoGeneracionEvento}/pdf/render`, {
        method: 'POST', headers: { Authorization: `Bearer ${API_KEY}`, 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo),
      });
      const pdf = await renderEvento({});
      assert.equal(pdf.status, 200);
      assert.equal(pdf.headers.get('content-type'), 'application/pdf');
      const textoPdf = textoCompleto(Buffer.from(await pdf.arrayBuffer()));
      assert.match(textoPdf, /EVENTO DE INVALIDACIÓN/);
      assert.ok(textoPdf.includes(SELLO_EVENTO));
      assert.ok(textoPdf.includes(reemplazo.codigoGeneracion));
      assert.doesNotMatch(textoPdf, /SIN VALIDEZ FISCAL/);
      assert.equal((await renderEvento({ logoPngBase64: 'xx', logoSha256: 'yy' })).status, 422);

      const eventos = await get(`/api/dte/${original.codigoGeneracion}/eventos`);
      assert.deepEqual(eventos.body.map((evento) => [evento.tipo, evento.estado]), [['INVALIDACION', 'ACEPTADO']]);

      const otraVez = await post(`/api/dte/${original.codigoGeneracion}/anular`, { motivo });
      assert.equal(otraVez.status, 409);
      assert.equal(otraVez.body.code, 'DTE_ALREADY_INVALIDATED');
      assert.equal(otraVez.body.codigoGeneracionEvento, body.codigoGeneracionEvento);
    });

    test('el documento de reemplazo debe estar transmitido con sello', async () => {
      const { body: original } = await post('/api/dte/factura', FACTURA_VALIDA);
      haciendaClient.transmitirDte = async () => {
        throw new Error('Timeout simulado');
      };
      const { body: pendiente } = await post('/api/dte/factura', FACTURA_VALIDA);
      const { status, body } = await post(`/api/dte/${original.codigoGeneracion}/anular`, {
        motivo: { ...motivo, tipoAnulacion: 1 },
        codigoGeneracionReemplazo: pendiente.codigoGeneracion,
      });
      assert.equal(status, 409);
      assert.equal(body.code, 'INVALIDATION_REPLACEMENT_NOT_READY');
    });

    test('sin respuesta de Hacienda, la misma key reenvía el mismo evento y otra key no crea un segundo', async () => {
      const { body: emitido } = await post('/api/dte/factura', FACTURA_VALIDA);
      let firmas = 0;
      firmadorClient.firmarDocumento = async () => {
        firmas += 1;
        return 'JWS.EVENTO.FIRMADO';
      };
      let envios = 0;
      haciendaClient.anularDte = async () => {
        envios += 1;
        if (envios === 1) throw new Error('Timeout simulado');
        return { estado: 'PROCESADO', selloRecibido: SELLO_EVENTO };
      };

      const clave = 'idem-anular-reanudable';
      const primero = await post(`/api/dte/${emitido.codigoGeneracion}/anular`, { motivo }, { 'Idempotency-Key': clave });
      assert.equal(primero.status, 502);
      assert.equal(primero.body.code, 'INVALIDATION_NO_RESPONSE');

      const otraClave = await post(`/api/dte/${emitido.codigoGeneracion}/anular`, { motivo });
      assert.equal(otraClave.status, 409);
      assert.equal(otraClave.body.code, 'INVALIDATION_IN_PROGRESS');

      const segundo = await post(`/api/dte/${emitido.codigoGeneracion}/anular`, { motivo }, { 'Idempotency-Key': clave });
      assert.equal(segundo.status, 200, JSON.stringify(segundo.body));
      assert.equal(segundo.body.codigoGeneracionEvento, primero.body.codigoGeneracionEvento);
      assert.equal(firmas, 1, 'el evento firmado se reutiliza');
      assert.equal(envios, 2);
      assert.equal(db.prepare('SELECT estado FROM dtes WHERE codigo_generacion = ?').get(emitido.codigoGeneracion).estado, 'INVALIDADO');
    });

    test('vista previa y plazo: una Factura con sello de hace más de 3 meses ya no se invalida', async () => {
      const { body: emitido } = await post('/api/dte/factura', FACTURA_VALIDA);
      const previa = await get(`/api/dte/${emitido.codigoGeneracion}/invalidacion`);
      assert.equal(previa.status, 200);
      assert.equal(previa.body.tipoDte, '01');
      assert.equal(previa.body.plazo.regla, 'TRES_MESES_DESDE_SELLO');
      assert.equal(previa.body.plazo.vencido, false);
      assert.deepEqual(previa.body.reemplazoRequeridoEnTipos, [1, 3]);

      db.prepare(`UPDATE dtes SET fecha_sello = date('now', '-4 months') WHERE codigo_generacion = ?`).run(emitido.codigoGeneracion);
      let llamadas = 0;
      haciendaClient.anularDte = async () => {
        llamadas += 1;
        return { estado: 'PROCESADO', selloRecibido: SELLO_EVENTO };
      };
      const { status, body } = await post(`/api/dte/${emitido.codigoGeneracion}/anular`, { motivo });
      assert.equal(status, 422);
      assert.equal(body.code, 'INVALIDATION_DEADLINE_EXCEEDED');
      assert.equal(llamadas, 0);
    });
  });

  test('GET /api/dte/:codigoGeneracion/hacienda delega en haciendaClient.consultarDte y clasifica la respuesta', async () => {
    const { body: emitido } = await post('/api/dte/factura', FACTURA_VALIDA);
    haciendaClient.consultarDte = async ({ codigoGeneracion }) => ({
      httpStatus: 200,
      data: { estado: 'PROCESADO', codigoGeneracion, selloRecibido: SELLO_EVENTO },
    });

    const { status, body } = await get(`/api/dte/${emitido.codigoGeneracion}/hacienda`);
    assert.equal(status, 200);
    assert.equal(body.resultado, 'ACEPTADO');
    assert.equal(body.selloRecepcion, SELLO_EVENTO);
    assert.equal(body.respuestaHacienda.codigoGeneracion, emitido.codigoGeneracion);

    haciendaClient.consultarDte = async () => ({ httpStatus: 404, data: null });
    const noExiste = await get(`/api/dte/${emitido.codigoGeneracion}/hacienda`);
    assert.equal(noExiste.status, 200);
    assert.equal(noExiste.body.resultado, 'NO_ENCONTRADO');

    // Observaciones de Hacienda y errores con código estable para el panel.
    haciendaClient.consultarDte = async ({ codigoGeneracion }) => ({
      httpStatus: 200,
      data: { estado: 'PROCESADO', codigoGeneracion, selloRecibido: SELLO_EVENTO, observaciones: ['Observación de prueba', ''] },
    });
    assert.deepEqual((await get(`/api/dte/${emitido.codigoGeneracion}/hacienda`)).body.observaciones, ['Observación de prueba']);
    haciendaClient.consultarDte = async () => { throw new AuthError('Usuario o clave inválidos', { credenciales: true }); };
    const credenciales = await get(`/api/dte/${emitido.codigoGeneracion}/hacienda`);
    assert.equal(credenciales.status, 502);
    assert.equal(credenciales.body.code, 'HACIENDA_AUTH_ERROR');
    haciendaClient.consultarDte = async () => { throw new haciendaClient.HaciendaError('Hacienda no respondió (ETIMEDOUT)', { tipo: 'RED' }); };
    const caida = await get(`/api/dte/${emitido.codigoGeneracion}/hacienda`);
    assert.equal(caida.status, 502);
    assert.equal(caida.body.code, 'HACIENDA_UNAVAILABLE');
  });

  test('POST /api/dte/:codigoGeneracion/reconciliar vuelve a consultar un DTE en RECONCILIACION', async () => {
    haciendaClient.transmitirDte = async () => ({ estado: 'PROCESADO' });
    const { body: emitido } = await post('/api/dte/factura', FACTURA_VALIDA);
    db.prepare(`UPDATE dtes SET estado = 'RECONCILIACION' WHERE codigo_generacion = ?`).run(emitido.codigoGeneracion);
    db.prepare('DELETE FROM cola_reintentos').run();

    const { status, body } = await post(`/api/dte/${emitido.codigoGeneracion}/reconciliar`, {});
    assert.equal(status, 202);
    assert.equal(body.estado, 'PENDIENTE_RECONCILIACION');
    const cola = db.prepare('SELECT * FROM cola_reintentos WHERE codigo_generacion = ?').get(emitido.codigoGeneracion);
    assert.equal(cola.accion, 'CONSULTAR', 'nunca reenvía sin consultar');

    const otraVez = await post(`/api/dte/${emitido.codigoGeneracion}/reconciliar`, {});
    assert.equal(otraVez.status, 409);
    assert.equal(otraVez.body.code, 'DTE_NOT_IN_RECONCILIATION');
  });

  test('GET /api/dte/lote/:codigoLote delega en haciendaClient.consultarLoteDte', async () => {
    haciendaClient.consultarLoteDte = async (codigoLote) => ({ procesados: [], rechazados: [], codigoLote });
    const { status, body } = await get('/api/dte/lote/LOTE-FALSO-123');
    assert.equal(status, 200);
    assert.equal(body.codigoLote, 'LOTE-FALSO-123');
  });
});
