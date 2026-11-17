const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const etiquetas = require('../../src/utils/etiquetasCatalogo');

describe('etiquetasCatalogo.js', () => {
  test('desambigua municipios con código repetido usando el departamento', () => {
    assert.equal(etiquetas.nombreMunicipio('06', '23'), 'SAN SALVADOR CENTRO');
    assert.equal(etiquetas.nombreMunicipio('05', '23'), 'LA LIBERTAD NORTE');
    assert.equal(etiquetas.nombreMunicipio('08', '23'), 'LA PAZ OESTE');
  });

  test('compara el prefijo del departamento sin tildes ni eñes distintas', () => {
    assert.equal(etiquetas.nombreMunicipio('14', '20'), 'LA UNION SUR');
    assert.equal(etiquetas.nombreMunicipio('09', '10'), 'CABAÑAS ESTE');
    assert.equal(etiquetas.nombreMunicipio('01', '14'), 'AHUACHAPAN CENTRO');
  });

  test('devuelve el código crudo si el municipio o distrito no existe', () => {
    assert.equal(etiquetas.nombreMunicipio('06', '99'), '99');
    assert.equal(etiquetas.nombreDistrito('06', '99'), '99');
    assert.equal(etiquetas.nombreMunicipio('06', null), null);
  });

  test('resuelve distritos dentro de su departamento', () => {
    assert.equal(etiquetas.nombreDistrito('06', '14'), 'SAN SALVADOR');
    assert.equal(etiquetas.nombreDistrito('01', '01'), 'AHUACHAPÁN');
  });

  test('arma una dirección legible con los nombres de catálogo', () => {
    assert.equal(
      etiquetas.direccionLegible({ departamento: '06', municipio: '23', distrito: '14', complemento: 'Col. Escalón' }),
      'Col. Escalón, SAN SALVADOR, SAN SALVADOR CENTRO, SAN SALVADOR',
    );
    assert.equal(etiquetas.direccionLegible(null), null);
    assert.equal(etiquetas.direccionLegible({}), null);
  });

  test('quita las llamadas a notas al pie de CAT-014', () => {
    assert.equal(etiquetas.nombreUnidadMedida(59), 'Unidad');
    assert.equal(etiquetas.nombreUnidadMedida(99), 'Otra');
    assert.equal(etiquetas.nombreUnidadMedida('22'), 'Galón');
    assert.equal(etiquetas.nombreUnidadMedida(12345), '12345');
  });

  test('deduce el tipo de establecimiento desde el número de control', () => {
    assert.equal(etiquetas.tipoEstablecimientoDesdeNumeroControl('DTE-01-M001P001-000000012794542'), 'Casa Matriz');
    assert.equal(etiquetas.tipoEstablecimientoDesdeNumeroControl('DTE-03-S002P001-000000000000001'), 'Sucursal');
    assert.equal(etiquetas.tipoEstablecimientoDesdeNumeroControl('DTE-01-X001P001-000000000000001'), null);
    assert.equal(etiquetas.tipoEstablecimientoDesdeNumeroControl(undefined), null);
  });

  test('traduce los catálogos simples que usa el PDF', () => {
    assert.equal(etiquetas.nombreTipoDocumentoIdentificacion('13'), 'DUI');
    assert.equal(etiquetas.nombreFormaPago('01'), 'Billetes y monedas');
    assert.equal(etiquetas.nombreTipoDte('03'), 'Comprobante de crédito fiscal');
    assert.equal(etiquetas.nombreCondicionOperacion(1), 'Contado');
    assert.equal(etiquetas.nombreTipoGeneracion(2), 'Electrónico');
    assert.equal(etiquetas.nombreFormaPago(null), null);
  });
});
