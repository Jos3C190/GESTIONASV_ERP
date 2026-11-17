const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { construirUrlConsultaPublica } = require('../../src/utils/qrConsultaPublica');

describe('qrConsultaPublica.js', () => {
  test('construye la URL exacta confirmada en el Manual v2.0 sección 5', () => {
    const url = construirUrlConsultaPublica({
      ambiente: '00',
      codigoGeneracion: '00000000-0000-0000-0000-000000000000',
      fechaEmi: '2026-07-19',
    });
    assert.equal(
      url,
      'https://admin.factura.gob.sv/consultaPublica?ambiente=00&codGen=00000000-0000-0000-0000-000000000000&fechaEmi=2026-07-19'
    );
  });

  test('usa el dominio y path correctos sin importar el ambiente', () => {
    const url = construirUrlConsultaPublica({ ambiente: '01', codigoGeneracion: 'ABC', fechaEmi: '2026-01-01' });
    assert.ok(url.startsWith('https://admin.factura.gob.sv/consultaPublica?'));
    assert.match(url, /ambiente=01/);
  });
});
