/**
 * A diferencia del resto de test/integration/, este test NO requiere la app
 * vía `require()` — arranca `src/server.js` como un PROCESO REAL separado
 * (`child_process.spawn`) para probar el comportamiento que solo existe a
 * nivel de proceso: el cierre ordenado ante SIGTERM/SIGINT y el manejo de
 * errores no capturados. Esto no se puede probar llamando funciones dentro
 * del mismo proceso de test.
 *
 * Requiere las dependencias reales instaladas (`npm install`).
 */
const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path');

const ENV_BASE = {
  ...process.env,
  MH_NIT: '06141804941035',
  MH_NRC: '1234567',
  MH_NOMBRE: 'Mi Empresa de Pruebas S.A. de C.V.',
  MH_NOMBRE_COMERCIAL: 'Mi Empresa',
  MH_COD_ACTIVIDAD: '62010',
  MH_DESC_ACTIVIDAD: 'Programación informática',
  MH_TELEFONO: '22221111',
  MH_CORREO: 'facturacion@miempresa.com',
  MH_DIR_DEPARTAMENTO: '06',
  MH_DIR_MUNICIPIO: '23',
  MH_DIR_DISTRITO: '14',
  MH_DIR_COMPLEMENTO: 'Calle Principal #123, San Salvador',
  MH_PASSWORD_API: 'clave-api-de-prueba',
  MH_PASSWORD_PRI: 'clave-privada-de-prueba',
  MH_AMBIENTE: '00',
  MH_COD_ESTABLE_INTERNO: 'CASA',
  MH_COD_PUNTO_VENTA_INTERNO: '',
  MH_TIPO_ESTABLECIMIENTO: '02',
  MH_COD_ESTABLECIMIENTO: '001',
  MH_COD_PUNTO_VENTA: '001',
  MH_AUTH_URL: 'https://apitest.dtes.mh.gob.sv/seguridad/auth',
  MH_RECEPCION_URL: 'https://apitest.dtes.mh.gob.sv/fesv/recepciondte',
  MH_RECEPCION_LOTE_URL: 'https://apitest.dtes.mh.gob.sv/fesv/recepcionlote',
  MH_ANULACION_URL: 'https://apitest.dtes.mh.gob.sv/fesv/anulardte',
  MH_CONTINGENCIA_URL: 'https://apitest.dtes.mh.gob.sv/fesv/contingencia',
  MH_CONSULTA_URL: 'https://apitest.dtes.mh.gob.sv/fesv/recepcion/consultadte',
  MH_CONSULTA_LOTE_URL: 'https://apitest.dtes.mh.gob.sv/fesv/recepcion/consultadtelote',
  FIRMADOR_URL: 'http://localhost:8113/firmardocumento/',
  PORT: '0', // puerto aleatorio libre, no importa cuál para este test
  LOG_LEVEL: 'info', // necesitamos ver el log de arranque en stdout
  SQLITE_PATH: ':memory:',
  RETRY_MAX_ATTEMPTS: '5',
  RETRY_BASE_DELAY_MS: '2000',
  MS_API_KEYS: 'clave-de-prueba-para-tests',
};

function arrancarServidor() {
  const proc = spawn(process.execPath, [path.join(__dirname, '../../src/server.js')], {
    env: ENV_BASE,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  return proc;
}

function esperarHasta(proc, streamName, patron, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    let acumulado = '';
    const timeout = setTimeout(() => reject(new Error(`Timeout esperando "${patron}" en ${streamName}. Salida acumulada: ${acumulado}`)), timeoutMs);
    proc[streamName].on('data', (chunk) => {
      acumulado += chunk.toString();
      if (patron.test(acumulado)) {
        clearTimeout(timeout);
        resolve(acumulado);
      }
    });
  });
}

function esperarSalida(proc, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Timeout esperando que el proceso terminara')), timeoutMs);
    proc.on('exit', (code, signal) => {
      clearTimeout(timeout);
      resolve({ code, signal });
    });
  });
}

describe('server.js (proceso real, integración)', () => {
  test('arranca, responde a SIGTERM con cierre ordenado, y termina con código 0', async () => {
    const proc = arrancarServidor();
    try {
      await esperarHasta(proc, 'stdout', /escuchando en puerto/i);

      const inicioCierre = Date.now();
      proc.kill('SIGTERM');

      const { code, signal } = await esperarSalida(proc, 8000);
      const duracionCierre = Date.now() - inicioCierre;

      assert.equal(code, 0, `el proceso debería salir con código 0 (salió con code=${code}, signal=${signal})`);
      // Debe cerrar mucho antes del timeout forzado de 10s configurado en server.js.
      assert.ok(duracionCierre < 8000, `el cierre tardó ${duracionCierre}ms, sospechosamente cerca del timeout forzado`);
    } finally {
      if (!proc.killed) proc.kill('SIGKILL');
    }
  });

  test('responde a SIGINT igual que a SIGTERM', async () => {
    const proc = arrancarServidor();
    try {
      await esperarHasta(proc, 'stdout', /escuchando en puerto/i);
      proc.kill('SIGINT');
      const { code } = await esperarSalida(proc, 8000);
      assert.equal(code, 0);
    } finally {
      if (!proc.killed) proc.kill('SIGKILL');
    }
  });

  test('una segunda señal mientras ya está cerrando no revienta ni cuelga', async () => {
    const proc = arrancarServidor();
    try {
      await esperarHasta(proc, 'stdout', /escuchando en puerto/i);
      proc.kill('SIGTERM');
      proc.kill('SIGTERM'); // segunda señal inmediata, a propósito
      const { code } = await esperarSalida(proc, 8000);
      assert.equal(code, 0);
    } finally {
      if (!proc.killed) proc.kill('SIGKILL');
    }
  });
});
