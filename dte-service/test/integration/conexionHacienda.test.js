/**
 * Tarjeta «Conexión con Hacienda» (mejora 14): estado de credenciales y
 * certificado y prueba de conexión contra un servidor HTTP que imita al
 * firmador y a la autenticación de Hacienda. Ninguna respuesta debe llevar
 * secretos: contraseñas, llave privada ni contenido del certificado.
 */
const { test, describe, before, after, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');

const NIT = '06141804941035';
const PASSWORD_API = 'clave-api-secreta-1234';
const PASSWORD_PRI = 'clave-privada-secreta-5678';
const LLAVE_PRIVADA = 'MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQ-LLAVE-PRIVADA-FALSA';
const CLAVE_HASH = 'a3f1c0ffee5d1e2b9c8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5';
const certDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cert-mh-'));
const DIA = 24 * 60 * 60 * 1000;

/** Certificado como lo entrega Hacienda: XML con llave pública, llave privada y vigencia. */
function certificadoXml({ nit = NIT, notAfter, notBefore = new Date(Date.now() - 365 * DIA) }) {
  return `<?xml version="1.0" encoding="UTF-8"?>
<CertificadoMH>
  <_id>${nit}</_id>
  <nit>${nit}</nit>
  <publicKey><keyType>PUBLIC</keyType><algorithm>RSA</algorithm><encodied>MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A-PUBLICA</encodied><format>X.509</format></publicKey>
  <privateKey><keyType>PRIVATE</keyType><algorithm>RSA</algorithm><encodied>${LLAVE_PRIVADA}</encodied><format>PKCS#8</format><clave>${CLAVE_HASH}</clave></privateKey>
  <activo>true</activo>
  <certificado><basicEstructure><validity><notBefore>${notBefore.toISOString()}</notBefore><notAfter>${notAfter.toISOString()}</notAfter></validity></basicEstructure></certificado>
</CertificadoMH>`;
}
const escribirCertificado = (contenido) => fs.writeFileSync(path.join(certDir, `${NIT}.crt`), contenido);

const RUTAS = { '/seguridad/auth': 'auth', '/firmardocumento/': 'firmar' };
const respuestas = { auth: [], firmar: [] };
const llamadas = [];
const json = (status, cuerpo) => (res) => { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(cuerpo)); };
const PREDETERMINADOS = {
  auth: json(200, { status: 'OK', body: { user: NIT, token: 'Bearer token-de-prueba' } }),
  firmar: json(200, { status: 'OK', body: 'eyJhbGciOiJSUzUxMiJ9.eyJwcnVlYmEiOnRydWV9.ZmlybWE' }),
};
const servidor = http.createServer((req, res) => {
  let datos = '';
  req.on('data', (fragmento) => { datos += fragmento; });
  req.on('end', () => {
    const ruta = RUTAS[req.url];
    if (!ruta) { res.writeHead(404); res.end(); return; }
    llamadas.push({ ruta, cuerpo: datos });
    (respuestas[ruta].shift() || PREDETERMINADOS[ruta])(res);
  });
});

let servidorApi;
let baseUrl;
let conexionHacienda;
const API = { Authorization: 'Bearer clave-de-prueba-para-tests' };
const leer = async () => (await fetch(`${baseUrl}/api/dte/conexion-hacienda`, { headers: API })).json();
async function probar() {
  conexionHacienda._reiniciarLimite();
  const res = await fetch(`${baseUrl}/api/dte/conexion-hacienda/probar`, { method: 'POST', headers: API });
  return { status: res.status, texto: await res.text() };
}
function sinSecretos(texto) {
  for (const secreto of [PASSWORD_API, PASSWORD_PRI, LLAVE_PRIVADA, CLAVE_HASH, 'CertificadoMH', 'privateKey']) {
    assert.equal(texto.includes(secreto), false, `la respuesta incluye un secreto: ${secreto}`);
  }
}

describe('Conexión con Hacienda', () => {
  before(async () => {
    await new Promise((resolve) => servidor.listen(0, '127.0.0.1', resolve));
    const base = `http://127.0.0.1:${servidor.address().port}`;
    Object.assign(process.env, {
      DTE_ALLOW_NON_OFFICIAL_MH_HOSTS: 'true',
      MH_AUTH_URL: `${base}/seguridad/auth`,
      FIRMADOR_URL: `${base}/firmardocumento/`,
      MH_PASSWORD_API: PASSWORD_API,
      MH_PASSWORD_PRI: PASSWORD_PRI,
      MH_CERT_PATH: certDir,
      MH_TIMEOUT_MS: '250',
    });
    require('../_setup');
    conexionHacienda = require('../../src/services/conexionHacienda');
    const app = require('../../src/app');
    await new Promise((resolve) => {
      servidorApi = app.listen(0, '127.0.0.1', () => {
        baseUrl = `http://127.0.0.1:${servidorApi.address().port}`;
        resolve();
      });
    });
  });

  after(() => {
    servidorApi?.close();
    servidor.close();
    fs.rmSync(certDir, { recursive: true, force: true });
  });

  beforeEach(() => {
    respuestas.auth.length = 0;
    respuestas.firmar.length = 0;
    llamadas.length = 0;
  });

  test('sin certificado: credenciales configuradas, certificado no disponible y nada secreto', async () => {
    const res = await fetch(`${baseUrl}/api/dte/conexion-hacienda`, { headers: API });
    const texto = await res.text();
    assert.equal(res.status, 200);
    sinSecretos(texto);
    const estado = JSON.parse(texto);
    assert.equal(estado.ambienteEtiqueta, 'Pruebas de Hacienda');
    assert.equal(estado.ambiente, '00');
    assert.deepEqual(estado.credenciales, { aplica: true, MH_NIT: true, MH_PASSWORD_API: true, MH_PASSWORD_PRI: true, FIRMADOR_URL: true, faltan: [] });
    assert.equal(estado.certificado.estado, 'NO_DISPONIBLE');
    const sinClave = await fetch(`${baseUrl}/api/dte/conexion-hacienda`);
    assert.equal(sinClave.status, 401);
  });

  test('certificado vigente, por vencer, vencido, de otro NIT e ilegible', async () => {
    escribirCertificado(certificadoXml({ notAfter: new Date(Date.now() + 200 * DIA) }));
    let estado = await leer();
    assert.equal(estado.certificado.estado, 'VIGENTE');
    assert.equal(estado.certificado.nit, NIT);
    assert.equal(estado.certificado.coincideConNitConfigurado, true);
    assert.ok(estado.certificado.diasParaVencer >= 199);

    escribirCertificado(certificadoXml({ notAfter: new Date(Date.now() + 10 * DIA) }));
    estado = await leer();
    assert.equal(estado.certificado.estado, 'POR_VENCER');
    assert.ok(estado.certificado.diasParaVencer <= 10);

    escribirCertificado(certificadoXml({ notAfter: new Date(Date.now() - DIA) }));
    const texto = await (await fetch(`${baseUrl}/api/dte/conexion-hacienda`, { headers: API })).text();
    sinSecretos(texto);
    assert.equal(JSON.parse(texto).certificado.estado, 'VENCIDO');

    escribirCertificado(certificadoXml({ nit: '06140101001019', notAfter: new Date(Date.now() + 200 * DIA) }));
    assert.equal((await leer()).certificado.coincideConNitConfigurado, false);

    escribirCertificado('esto no es un certificado');
    assert.equal((await leer()).certificado.estado, 'ILEGIBLE');
  });

  test('prueba de conexión correcta: firma de prueba y autenticación, sin transmitir nada', async () => {
    escribirCertificado(certificadoXml({ notAfter: new Date(Date.now() + 200 * DIA) }));
    const { status, texto } = await probar();
    assert.equal(status, 200);
    sinSecretos(texto);
    const cuerpo = JSON.parse(texto);
    assert.equal(cuerpo.ok, true);
    assert.equal(cuerpo.mensaje, 'Conexión correcta');
    assert.deepEqual(cuerpo.pasos.map((paso) => [paso.paso, paso.codigo]), [['firmador', 'OK'], ['hacienda', 'OK']]);
    assert.deepEqual(llamadas.map((llamada) => llamada.ruta), ['firmar', 'auth']);
    // El último acceso exitoso queda registrado.
    const estado = await leer();
    assert.equal(estado.ultimoAccesoExitoso.tipo, 'autenticacion');
    assert.ok(Date.now() - Date.parse(estado.ultimoAccesoExitoso.en) < 60_000);
  });

  test('credenciales inválidas, Hacienda caída y certificado inválido, con mensajes en español', async () => {
    respuestas.auth.push(json(200, { status: 'ERROR', message: 'Usuario o contraseña incorrectos' }));
    let { texto } = await probar();
    sinSecretos(texto);
    let cuerpo = JSON.parse(texto);
    assert.equal(cuerpo.ok, false);
    assert.equal(cuerpo.codigo, 'CREDENCIALES_INVALIDAS');
    assert.match(cuerpo.mensaje, /rechazó el usuario \(NIT\) o la contraseña del API/);

    respuestas.auth.push((res) => { res.destroy(); });
    cuerpo = JSON.parse((await probar()).texto);
    assert.equal(cuerpo.codigo, 'HACIENDA_NO_RESPONDE');
    assert.equal(cuerpo.mensaje, 'Hacienda no responde.');

    respuestas.firmar.push(json(200, { status: 'ERROR', body: { codigo: '803', mensaje: ['No existe llave pública o contraseña incorrecta'] } }));
    ({ texto } = await probar());
    sinSecretos(texto);
    cuerpo = JSON.parse(texto);
    assert.equal(cuerpo.codigo, 'CERTIFICADO_INVALIDO');
    assert.match(cuerpo.mensaje, /Certificado inválido: la contraseña de la llave privada/);
  });

  test('límite: una prueba cada 30 s', async () => {
    const primera = await probar();
    assert.equal(primera.status, 200);
    const segunda = await fetch(`${baseUrl}/api/dte/conexion-hacienda/probar`, { method: 'POST', headers: API });
    assert.equal(segunda.status, 429);
    assert.equal((await segunda.json()).code, 'CONNECTION_TEST_TOO_SOON');
  });

  test('lectura directa del certificado: XML de Hacienda y fechas en milisegundos', () => {
    const datos = conexionHacienda.leerDatosCertificado(certificadoXml({ notAfter: new Date('2027-03-01T00:00:00Z') }).replace(/<notAfter>[^<]+<\/notAfter>/, '<notAfter>1803859200000</notAfter>'));
    assert.equal(datos.nit, NIT);
    assert.equal(datos.validoHasta.toISOString(), '2027-03-01T00:00:00.000Z');
    assert.equal(conexionHacienda.leerDatosCertificado('<CertificadoMH><nit>1</nit></CertificadoMH>'), null);
  });
});
