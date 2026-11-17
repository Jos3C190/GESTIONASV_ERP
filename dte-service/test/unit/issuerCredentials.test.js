const { test, describe, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
require('../_setup');

const { db } = require('../../src/db');
const credenciales = require('../../src/services/issuerCredentials');
const { certificadoPrueba } = require('../helpers/certificadoPrueba');

const NIT = '06142803901121';
const PRI = 'llave-privada-segura';

function datos(extra = {}) {
  return {
    passwordApi: 'clave-api',
    passwordPri: PRI,
    certificado: certificadoPrueba(NIT, PRI).toString('base64'),
    ...extra,
  };
}

function codigo(fn) {
  try {
    fn();
  } catch (error) {
    return error.code;
  }
  return null;
}

describe('credenciales de Hacienda por emisor', () => {
  beforeEach(() => {
    db.exec('DELETE FROM emisor_credenciales;');
    fs.rmSync(credenciales.rutaCertificado(NIT), { force: true });
  });

  test('guarda las contraseñas cifradas y el certificado para el firmador', () => {
    const estado = credenciales.guardar(NIT, datos());
    assert.equal(estado.configuradas, true);
    assert.equal(estado.certificadoPresente, true);
    assert.match(estado.certificadoSha256, /^[0-9a-f]{64}$/);
    assert.equal(JSON.stringify(estado).includes('clave-api'), false);

    const row = db.prepare('SELECT password_api, password_pri FROM emisor_credenciales WHERE nit = ?').get(NIT);
    assert.match(row.password_api, /^v1:/);
    assert.equal(row.password_api.includes('clave-api'), false);
    assert.equal(row.password_pri.includes(PRI), false);
    assert.deepEqual(credenciales.obtener(NIT), { passwordApi: 'clave-api', passwordPri: PRI });

    const archivo = fs.readFileSync(credenciales.rutaCertificado(NIT), 'utf8');
    assert.match(archivo, new RegExp(`<nit>${NIT}</nit>`));
  });

  test('rechaza un certificado de otro NIT, la contraseña privada equivocada y archivos que no lo son', () => {
    assert.equal(
      codigo(() => credenciales.guardar(NIT, datos({ certificado: certificadoPrueba('06140101900011', PRI).toString('base64') }))),
      'CERTIFICATE_NIT_MISMATCH',
    );
    assert.equal(codigo(() => credenciales.guardar(NIT, datos({ passwordPri: 'otra' }))), 'INVALID_PRIVATE_KEY_PASSWORD');
    assert.equal(
      codigo(() => credenciales.guardar(NIT, datos({ certificado: Buffer.from('<html/>').toString('base64') }))),
      'INVALID_CERTIFICATE',
    );
    assert.equal(codigo(() => credenciales.guardar(NIT, datos({ passwordApi: '' }))), 'INVALID_ISSUER_CREDENTIALS');
    assert.equal(credenciales.estado(NIT).configuradas, false);
    assert.equal(fs.existsSync(credenciales.rutaCertificado(NIT)), false);
  });

  test('sin certificado nuevo conserva el guardado y exige que la contraseña privada le corresponda', () => {
    credenciales.guardar(NIT, datos());
    const antes = credenciales.estado(NIT).certificadoSha256;
    const despues = credenciales.guardar(NIT, { passwordApi: 'nueva-api', passwordPri: PRI });
    assert.equal(despues.certificadoSha256, antes);
    assert.equal(credenciales.obtener(NIT).passwordApi, 'nueva-api');
    assert.equal(
      codigo(() => credenciales.guardar(NIT, { passwordApi: 'x', passwordPri: 'equivocada' })),
      'INVALID_PRIVATE_KEY_PASSWORD',
    );
  });

  test('eliminar borra las contraseñas y el certificado', () => {
    credenciales.guardar(NIT, datos());
    credenciales.eliminar(NIT);
    assert.equal(credenciales.obtener(NIT), null);
    assert.equal(credenciales.estado(NIT).certificadoPresente, false);
  });
});
